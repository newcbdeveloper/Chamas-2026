# user_dashboard/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.db import models
from django.utils import timezone
from django.utils.timesince import timesince
from django.db.models import Q
from datetime import timedelta
import datetime
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from notifications.models import UserNotificationHistory, DismissedNotification
import logging

# Model imports
from authentication.models import Profile
from wallet.models import MainWallet, WalletTransaction
from Goals.models import Goal
from merry_go_round.models import Invitation, Contribution, RoundMembership

# Service imports
from wallet.services import WalletService

# KYC imports
from .kyc_utils import get_kyc_status

logger = logging.getLogger(__name__)


@login_required(login_url='Login')
def home(request):
    try:
        profile = Profile.objects.get(owner=request.user)
    except Profile.DoesNotExist:
        profile = None

    # Greeting
    hour = datetime.datetime.now().hour
    greeting = "Good Night"
    if 5 <= hour < 12:
        greeting = "Good Morning"
    elif 12 <= hour < 17:
        greeting = "Good Afternoon"
    elif 17 <= hour < 21:
        greeting = "Good Evening"
    
    # Last Login Logic
    last_login = request.user.last_login
    if last_login:
        now = timezone.now()
        time_diff = now - last_login
        if time_diff.total_seconds() < 60:
            last_login_display = "Just now"
        else:
            last_login_display = timesince(last_login) + " ago"
        last_login_exact = last_login.strftime("%b %d, %Y at %I:%M %p")
    else:
        last_login_display = "First time login"
        last_login_exact = ""

    # Get dismissed notification IDs to filter them out
    dismissed_ids = set(
        DismissedNotification.objects.filter(
            user=request.user
        ).exclude(
            action='snoozed',
            snooze_until__gt=timezone.now()
        ).values_list('notification_id', flat=True)
    )

    # Notifications (exclude dismissed ones that are from UserNotificationHistory)
    notifications = UserNotificationHistory.objects.filter(
        user=request.user
    ).exclude(
        id__in=[int(nid.replace('notif_', '')) for nid in dismissed_ids if nid.startswith('notif_')]
    ).order_by('-created_at')[:10]

    # Wallet balance
    wallet_balance = 0
    wallet_currency = 'KES'
    try:
        summary = WalletService.get_wallet_summary(request.user)
        wallet_balance = summary.get('available_balance', 0)
        wallet_currency = summary.get('currency', 'KES')
    except Exception as e:
        print(f"[Wallet] Error fetching balance: {e}")

    wallet = MainWallet.objects.filter(user=request.user).first()
    latest_transaction = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at').first()

    # Goals Data
    active_goals = Goal.objects.filter(user=request.user, is_active='Yes')
    active_goals_count = active_goals.count()
    total_saved = active_goals.aggregate(Sum('goal_balance'))['goal_balance__sum'] or 0

    # Pending Invitations - Filter out dismissed ones
    pending_invitations = []
    
    if profile:
        invitation_query = Q(status='pending')
        
        if profile.NIC_No:
            invitation_query &= Q(invitee_national_id=profile.NIC_No)
        
        email_phone_query = Q()
        if request.user.email:
            email_phone_query |= Q(invitee_email=request.user.email)
        if profile.phone:
            email_phone_query |= Q(invitee_phone=profile.phone)
        
        if email_phone_query:
            invitation_query |= (Q(status='pending') & email_phone_query)
        
        all_invitations = Invitation.objects.filter(
            invitation_query
        ).select_related('round', 'inviter').distinct()
        
        # Filter out dismissed invitations
        pending_invitations = [
            invite for invite in all_invitations 
            if f'invitation_{invite.id}' not in dismissed_ids
        ]
        
        print(f"[DEBUG] Found {len(pending_invitations)} pending invitations (after filtering dismissed)")
    else:
        all_invitations = Invitation.objects.filter(
            invitee_email=request.user.email,
            status='pending'
        ).select_related('round', 'inviter')
        
        # Filter out dismissed invitations
        pending_invitations = [
            invite for invite in all_invitations 
            if f'invitation_{invite.id}' not in dismissed_ids
        ]
    
    # Next Contribution Due - Check if dismissed
    next_contribution = None
    potential_contribution = Contribution.objects.filter(
        membership__user=request.user,
        status='pending',
        due_date__gte=timezone.now().date()
    ).order_by('due_date').first()
    
    if potential_contribution:
        contribution_id = f'contribution_{potential_contribution.id}'
        if contribution_id not in dismissed_ids:
            next_contribution = potential_contribution

    # KYC status
    kyc_status = get_kyc_status(request.user)

    context = {
        'profile': profile,
        'greeting': greeting,
        'notifications': notifications,
        'wallet_balance': wallet_balance,
        'wallet_currency': wallet_currency,
        'last_login_display': last_login_display,
        'last_login_exact': last_login_exact,
        'latest_transaction': latest_transaction,
        'active_goals_count': active_goals_count,
        'total_saved_goals': total_saved,
        'pending_invitations': pending_invitations,
        'next_contribution': next_contribution,
        'kyc_status': kyc_status,
    }
    return render(request, 'user_dashboard/home.html', context)


@login_required(login_url='Login')
@require_http_methods(["POST"])
def dismiss_notification(request):
    """
    Dismiss a notification permanently.
    Works for both system-generated notifications (invitations, contributions, etc.)
    and UserNotificationHistory notifications.
    """
    try:
        notification_id = request.POST.get('notification_id')
        
        if not notification_id:
            return JsonResponse({'success': False, 'error': 'Missing notification ID'}, status=400)
        
        # Determine notification type from ID prefix
        if notification_id.startswith('contribution_'):
            notif_type = 'contribution'
        elif notification_id.startswith('invitation_'):
            notif_type = 'invitation'
        elif notification_id.startswith('goal_reminder_'):
            notif_type = 'goal_reminder'
        elif notification_id.startswith('low_balance'):
            notif_type = 'low_balance'
        elif notification_id.startswith('notif_'):
            notif_type = 'user_notification'
        else:
            notif_type = 'system'
        
        # Create or update dismissal record
        dismissed, created = DismissedNotification.objects.get_or_create(
            user=request.user,
            notification_id=notification_id,
            defaults={
                'notification_type': notif_type,
                'action': 'dismissed'
            }
        )
        
        if not created:
            # Update existing record
            dismissed.action = 'dismissed'
            dismissed.dismissed_at = timezone.now()
            dismissed.snooze_until = None
            dismissed.save()
        
        logger.info(f"User {request.user.username} dismissed notification {notification_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Notification dismissed successfully'
        })
    
    except Exception as e:
        logger.error(f"Error dismissing notification: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='Login')
@require_http_methods(["POST"])
def mark_notification_read(request):
    """Mark a single notification as read (soft dismiss)"""
    try:
        notification_id = request.POST.get('notification_id')
        
        if not notification_id:
            return JsonResponse({'success': False, 'error': 'Missing notification ID'}, status=400)
        
        # For UserNotificationHistory notifications, we can add a read flag if needed
        # For now, treat it similar to dismiss but with 'read' action
        if notification_id.startswith('notif_') or notification_id.startswith('info_'):
            notif_id = notification_id.replace('notif_', '').replace('info_', '')
            # Just mark as success, actual read tracking can be added later
            return JsonResponse({
                'success': True,
                'message': 'Notification marked as read'
            })
        
        # For system notifications, mark as read
        notif_type = 'system'
        if notification_id.startswith('contribution_'):
            notif_type = 'contribution'
        elif notification_id.startswith('invitation_'):
            notif_type = 'invitation'
        elif notification_id.startswith('goal_reminder_'):
            notif_type = 'goal_reminder'
        elif notification_id.startswith('low_balance'):
            notif_type = 'low_balance'
        
        DismissedNotification.objects.get_or_create(
            user=request.user,
            notification_id=notification_id,
            defaults={
                'notification_type': notif_type,
                'action': 'dismissed'
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read'
        })
    
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='Login')
@require_http_methods(["POST"])
def delete_notification(request):
    """Delete a notification permanently"""
    try:
        notification_id = request.POST.get('notification_id')
        
        if not notification_id:
            return JsonResponse({'success': False, 'error': 'Missing notification ID'}, status=400)
        
        # For UserNotificationHistory, actually delete the record
        if notification_id.startswith('notif_') or notification_id.startswith('info_'):
            notif_id = notification_id.replace('notif_', '').replace('info_', '')
            try:
                notification = UserNotificationHistory.objects.get(
                    id=notif_id,
                    user=request.user
                )
                notification.delete()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Notification deleted successfully'
                })
            except UserNotificationHistory.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)
        
        # For system notifications, mark as deleted
        notif_type = 'system'
        if notification_id.startswith('contribution_'):
            notif_type = 'contribution'
        elif notification_id.startswith('invitation_'):
            notif_type = 'invitation'
        elif notification_id.startswith('goal_reminder_'):
            notif_type = 'goal_reminder'
        elif notification_id.startswith('low_balance'):
            notif_type = 'low_balance'
        
        DismissedNotification.objects.update_or_create(
            user=request.user,
            notification_id=notification_id,
            defaults={
                'notification_type': notif_type,
                'action': 'deleted'
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Notification deleted successfully'
        })
    
    except Exception as e:
        logger.error(f"Error deleting notification: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='Login')
@require_http_methods(["POST"])
def remind_later(request):
    """Set reminder for later (snooze notification)"""
    try:
        notification_id = request.POST.get('notification_id')
        snooze_hours = int(request.POST.get('snooze_hours', 24))
        
        if not notification_id:
            return JsonResponse({'success': False, 'error': 'Missing notification ID'}, status=400)
        
        # Determine notification type
        notif_type = 'system'
        if notification_id.startswith('contribution_'):
            notif_type = 'contribution'
        elif notification_id.startswith('invitation_'):
            notif_type = 'invitation'
        elif notification_id.startswith('goal_reminder_'):
            notif_type = 'goal_reminder'
        elif notification_id.startswith('low_balance'):
            notif_type = 'low_balance'
        
        snooze_until = timezone.now() + timedelta(hours=snooze_hours)
        
        DismissedNotification.objects.update_or_create(
            user=request.user,
            notification_id=notification_id,
            defaults={
                'notification_type': notif_type,
                'action': 'snoozed',
                'snooze_until': snooze_until
            }
        )
        
        logger.info(f"User {request.user.username} snoozed {notification_id} until {snooze_until}")
        
        return JsonResponse({
            'success': True,
            'message': f'Reminder set for {snooze_hours} hours from now'
        })
    
    except Exception as e:
        logger.error(f"Error setting reminder: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



@login_required(login_url='Login')
def settings(request):
    user = request.user
    try:
        user_profile = Profile.objects.get(owner=user)
    except Profile.DoesNotExist:
        messages.error(request, "Profile not found. Please contact support.")
        return redirect('user_dashboard:home')
    
    # Get KYC status
    kyc_status = get_kyc_status(user)

    notifications = UserNotificationHistory.objects.filter(
        user=user
    ).order_by('-created_at')[:6]

    if request.method == 'POST':
        section = request.POST.get('section', 'personal')

        if section == 'personal':
            # === Handle Personal Info Update ===
            fname = request.POST.get('firstname', '').strip()
            lname = request.POST.get('lastname', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()
            address = request.POST.get('address', '').strip()

            if fname:
                user.first_name = fname
            if lname:
                user.last_name = lname
            if email:
                user.email = email
            if phone:
                user_profile.phone = phone
            if address:
                user_profile.physical_address = address
            if 'upload' in request.FILES:
                user_profile.picture = request.FILES['upload']

            user.save()
            user_profile.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('user_dashboard:settings')  # Stays on same tab via JS, but safe redirect

        elif section == 'password':
            # === Handle Password Change ===
            current_password = request.POST.get('current_password', '').strip()
            new_password = request.POST.get('new_password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()

            if not user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            elif not new_password:
                messages.error(request, 'New password cannot be empty.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)  # Keeps user logged in
                messages.success(request, 'Password updated successfully!')
                return redirect('user_dashboard:settings')

    context = {
        'user_profile': user_profile,
        'user_notifications': notifications,
        'kyc_status': kyc_status,
    }
    return render(request, 'user_dashboard/settings.html', context)

@login_required(login_url='Login')
def all_notifications(request):
    """
    Enhanced notifications view with intelligent triage zones:
    - Zone 1: Action Required (Urgent Stack) - Requires user action
    - Zone 2: Recent Activity (Daily Log) - Informational updates
    - Zone 3: Informational - Low-priority system messages
    
    FIXED: Goal reminders now properly appear in Urgent zone
    """
    try:
        user_profile = Profile.objects.get(owner=request.user)
    except Profile.DoesNotExist:
        user_profile = None

    # Get filter parameters
    filter_category = request.GET.get('category', 'all')
    search_query = request.GET.get('search', '')
    show_all_urgent = request.GET.get('show_all_urgent', 'false') == 'true' 

    # ✅ NEW: Get dismissed notifications to filter them out
    dismissed_ids = set(
        DismissedNotification.objects.filter(
            user=request.user
        ).exclude(
            action='snoozed',
            snooze_until__gt=timezone.now()  # Don't exclude if snooze expired
        ).values_list('notification_id', flat=True)
    )

    # ========================================
    # ZONE 1: ACTION REQUIRED (URGENT)
    # ========================================
    urgent_notifications = []
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    # 1. Pending MGR Contributions
    try:
        pending_contributions = Contribution.objects.filter(
            membership__user=request.user,
            status='pending',
            due_date__lte=tomorrow
        ).select_related('membership__round').order_by('due_date')[:20]
        
        for idx, contribution in enumerate(pending_contributions, 1):
            notification_id = f'contribution_{contribution.id}'

            # ✅ Skip if dismissed
            if notification_id in dismissed_ids:
                continue

            days_overdue = (today - contribution.due_date).days
            
            if days_overdue > 0:
                urgency_text = f"OVERDUE by {days_overdue} day(s)"
            elif contribution.due_date == today:
                urgency_text = "DUE TODAY"
            else:
                urgency_text = "DUE TOMORROW"
            
            urgent_notifications.append({
                'id': f'contribution_{contribution.id}',
                'type': 'contribution',
                'title': f'Pending Contribution #{idx}',
                'time_ago': f'{days_overdue}D AGO' if days_overdue > 0 else urgency_text,
                'category': 'MGR',
                'description': f'Automated reminder for your {contribution.membership.round.get_frequency_display()} group contribution. Cycle {contribution.cycle_number} is awaiting payment.',
                'amount': contribution.amount,
                'action_url': f'/merry-go-round/wallet/',
                'contribution_id': contribution.id,
                'urgency_level': 'critical' if days_overdue > 0 else 'high'
            })
    except Exception as e:
        print(f"Error fetching contributions: {e}")
    
    # 2. Pending Round Invitations
    try:
        pending_invites = Invitation.objects.filter(
            Q(invitee_national_id=user_profile.NIC_No) |
            Q(invitee_email=request.user.email) |
            Q(invitee_phone=user_profile.phone),
            status='pending'
        ).select_related('round', 'inviter').order_by('-created_at')[:10]
        
        for invite in pending_invites:
            notification_id = f'invitation_{invite.id}'
            
            # ✅ Skip if dismissed
            if notification_id in dismissed_ids:
                continue

            days_ago = (timezone.now() - invite.created_at).days
            expires_in = (invite.expires_at - timezone.now()).days if invite.expires_at else 7
            
            urgent_notifications.append({
                'id': f'invitation_{invite.id}',
                'type': 'invitation',
                'title': f'Invitation to {invite.round.name}',
                'time_ago': f'{days_ago}D AGO',
                'category': 'MGR',
                'description': f'{invite.inviter.get_full_name() or invite.inviter.username} invited you to join. Expires in {expires_in} days.',
                'amount': invite.round.contribution_amount,
                'action_url': f'/merry-go-round/invitation/{invite.token}/',
                'invitation_token': invite.token,
                'invitation_id': invite.id,
                'urgency_level': 'medium'
            })
    except Exception as e:
        print(f"Error fetching invitations: {e}")
    
    # 3. Low Wallet Balance Warnings
    try:
        from merry_go_round.wallet_services import WalletService

        notification_id = 'low_balance_mgr'
        
        # ✅ Only check if not dismissed
        if notification_id not in dismissed_ids:
            active_memberships = RoundMembership.objects.filter(
                user=request.user,
                status='active'
            ).select_related('round')
        
        if active_memberships.exists():
            mgr_wallet = WalletService.get_or_create_wallet(request.user)
            
            next_contribution = Contribution.objects.filter(
                membership__user=request.user,
                status='pending'
            ).order_by('due_date').first()
            
            if next_contribution:
                required = next_contribution.amount
                shortfall = max(0, required - mgr_wallet.available_balance)
                
                if shortfall > 0:
                    urgent_notifications.append({
                        'id': 'low_balance_mgr',
                        'type': 'low_balance',
                        'title': 'Low MGR Wallet Balance',
                        'time_ago': 'NOW',
                        'category': 'MGR',
                        'description': f'Your MGR wallet balance is insufficient for your next contribution. Top up KES {shortfall:.2f} to avoid missing payments.',
                        'amount': shortfall,
                        'action_url': '/merry-go-round/wallet/',
                        'urgency_level': 'high'
                    })
    except Exception as e:
        print(f"Error checking wallet balance: {e}")
    
    # 4. ✅ FIXED: Goal Reminders from UserNotificationHistory
    try:
        # Keywords that indicate this is a goal reminder notification
        goal_reminder_keywords = [
            'reminder', 'time to save', 'make your contribution',
            'suggested amount', 'progress:', 'days remaining',
            "it's time to save", 'earning', 'interest p.a.'
        ]
        
        # Get recent notifications from UserNotificationHistory
        recent_user_notifications = UserNotificationHistory.objects.filter(
            user=request.user,
            created_at__gte=timezone.now() - timedelta(days=7)  # Last 7 days
        ).order_by('-created_at')
        
        for notif in recent_user_notifications:
            notification_id = f'goal_reminder_{notif.id}'
            
            # ✅ Skip if dismissed
            if notification_id in dismissed_ids:
                continue

            # Check if this is a goal reminder based on keywords
            title_lower = notif.notification_title.lower()
            body_lower = notif.notification_body.lower()
            
            is_goal_reminder = any(
                keyword in title_lower or keyword in body_lower 
                for keyword in goal_reminder_keywords
            )
            
            if is_goal_reminder:
                days_ago = (timezone.now() - notif.created_at).days
                hours_ago = int((timezone.now() - notif.created_at).total_seconds() / 3600)
                
                # Extract goal name from title
                goal_name = notif.notification_title
                if 'Reminder:' in goal_name:
                    goal_name = goal_name.split('Reminder:')[1].strip()
                if "It's time to save" in goal_name:
                    goal_name = goal_name.split("It's time to save towards your goal")[0].strip()
                
                # Try to extract suggested amount from body
                suggested_amount = 0
                if 'Suggested amount: KES' in notif.notification_body:
                    try:
                        amount_str = notif.notification_body.split('Suggested amount: KES')[1].split()[0]
                        suggested_amount = float(amount_str.replace(',', ''))
                    except:
                        suggested_amount = 0
                
                # Try to find matching goal by name
                goal_id = None
                try:
                    for goal in Goal.objects.filter(user=request.user, is_active='Yes'):
                        # Check if goal name appears in notification
                        if goal.name.lower() in title_lower or goal.name.lower() in body_lower:
                            goal_id = goal.id
                            break
                except Exception as goal_error:
                    print(f"Error finding goal: {goal_error}")
                
                # Determine time display
                if hours_ago < 1:
                    time_ago = "NOW"
                elif hours_ago < 24:
                    time_ago = f"{hours_ago}H AGO"
                else:
                    time_ago = f"{days_ago}D AGO"
                
                # Create shortened description
                description = notif.notification_body
                if len(description) > 150:
                    description = description[:150] + '...'
                
                urgent_notifications.append({
                    'id': f'goal_reminder_{notif.id}',
                    'type': 'goal_reminder',
                    'title': f'Savings Reminder: {goal_name[:30]}...' if len(goal_name) > 30 else f'Savings Reminder: {goal_name}',
                    'time_ago': time_ago,
                    'category': 'Goals',
                    'description': description,
                    'amount': suggested_amount,
                    'action_url': f'/goals/goal_details/{goal_id}/' if goal_id else '/goals/',
                    'goal_id': goal_id,
                    'notification_id': notif.id,
                    'urgency_level': 'medium'
                })
                
                print(f"✅ Added goal reminder to urgent: {goal_name[:30]}")
    except Exception as e:
        print(f"Error fetching goal reminders: {e}")
        import traceback
        traceback.print_exc()
    
    # Sort urgent notifications by urgency level and time
    urgency_order = {'critical': 0, 'high': 1, 'medium': 2}
    urgent_notifications.sort(key=lambda x: (urgency_order.get(x['urgency_level'], 3), x['time_ago']))
    
    print(f"📊 Total urgent notifications: {len(urgent_notifications)}")

    # ========================================
    # SLICE URGENT NOTIFICATIONS 
    # ========================================
    urgent_count = len(urgent_notifications)
    
    if show_all_urgent:
        # Show all urgent notifications
        displayed_urgent = urgent_notifications
        urgent_remaining = 0
    else:
        # Show only first 3
        displayed_urgent = urgent_notifications[:3]
        urgent_remaining = max(0, urgent_count - 3)
    
    # ========================================
    # ZONE 2: RECENT ACTIVITY (DAILY LOG)
    # ========================================
    
    recent_activity = UserNotificationHistory.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Apply search filter
    if search_query:
        recent_activity = recent_activity.filter(
            Q(notification_title__icontains=search_query) |
            Q(notification_body__icontains=search_query)
        )
    
    # Keywords for categorizing into recent activity (cashflow/transactions)
    RECENT_ACTIVITY_KEYWORDS = {
        'payout': ['payout', 'received', 'disbursed', 'credited'],
        'deposit': ['deposit', 'top up', 'added funds', 'transferred in'],
        'withdrawal': ['withdraw', 'withdrawal', 'transferred out'],
        'contribution': ['contribution processed', 'payment successful', 'contribution complete'],
        'round_started': ['round started', 'round has started', 'officially started'],
        'goal_started': ['goal created', 'new goal', 'goal started'],
    }
    
    # Build Q object for recent activity filtering
    recent_q = Q()
    for category, keywords in RECENT_ACTIVITY_KEYWORDS.items():
        for keyword in keywords:
            recent_q |= Q(notification_title__icontains=keyword)
            recent_q |= Q(notification_body__icontains=keyword)
    
    # Apply category filter
    if filter_category != 'all':
        category_keywords = {
            'deposits': ['deposit', 'top up', 'added funds', 'credited'],
            'withdrawals': ['withdraw', 'withdrawal', 'disbursed', 'transferred out'],
            'goals': ['goal', 'target', 'saving', 'express'],
            'mgr': ['merry', 'round', 'contribution', 'payout', 'mgr'],
        }
        
        if filter_category in category_keywords:
            filter_q = Q()
            for keyword in category_keywords[filter_category]:
                filter_q |= Q(notification_title__icontains=keyword)
                filter_q |= Q(notification_body__icontains=keyword)
            
            recent_activity = recent_activity.filter(filter_q)
    
    # Filter to only "recent activity" types
    recent_activity = recent_activity.filter(recent_q)
    
    # ✅ CRITICAL: Exclude notifications that are already in urgent (to avoid duplicates)
    URGENT_KEYWORDS = [
        'pending', 'due', 'reminder', 'invitation', 'low balance', 'insufficient',
        'time to save', 'make your contribution', 'suggested amount', 'overdue',
        "it's time to save", 'earning', 'interest p.a.'
    ]
    for keyword in URGENT_KEYWORDS:
        recent_activity = recent_activity.exclude(
            Q(notification_title__icontains=keyword) |
            Q(notification_body__icontains=keyword)
        )
    
    recent_activity = recent_activity[:50]
    
    # ========================================
    # ZONE 3: INFORMATIONAL
    # ========================================
    
    all_notifications = UserNotificationHistory.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Exclude urgent
    for keyword in URGENT_KEYWORDS:
        all_notifications = all_notifications.exclude(
            Q(notification_title__icontains=keyword) |
            Q(notification_body__icontains=keyword)
        )
    
    # Exclude recent activity
    informational = all_notifications.exclude(recent_q)
    
    # Apply search and category filters
    if search_query:
        informational = informational.filter(
            Q(notification_title__icontains=search_query) |
            Q(notification_body__icontains=search_query)
        )
    
    informational = informational[:20]
    
    # ========================================
    # CALCULATE COUNTS
    # ========================================
    
    urgent_count = len(urgent_notifications)
    
    all_notifications_for_count = UserNotificationHistory.objects.filter(user=request.user)
    
    category_counts = {
        'all': all_notifications_for_count.count(),
        'deposits': all_notifications_for_count.filter(
            Q(notification_title__icontains='deposit') |
            Q(notification_body__icontains='deposit') |
            Q(notification_title__icontains='top up') |
            Q(notification_body__icontains='credited')
        ).count(),
        'withdrawals': all_notifications_for_count.filter(
            Q(notification_title__icontains='withdraw') |
            Q(notification_body__icontains='withdraw') |
            Q(notification_title__icontains='disbursed')
        ).count(),
        'goals': all_notifications_for_count.filter(
            Q(notification_title__icontains='goal') |
            Q(notification_body__icontains='goal') |
            Q(notification_title__icontains='saving') |
            Q(notification_body__icontains='express')
        ).count(),
        'mgr': all_notifications_for_count.filter(
            Q(notification_title__icontains='merry') |
            Q(notification_title__icontains='round') |
            Q(notification_body__icontains='contribution') |
            Q(notification_body__icontains='payout')
        ).count(),
    }
    
    context = {
        'user_profile': user_profile,
        
        # Zone 1: Urgent (Action Required)
        'urgent_notifications': displayed_urgent,
        'urgent_count': urgent_count,
        'urgent_remaining': urgent_remaining,
        'show_all_urgent': show_all_urgent,  
        
        # Zone 2: Recent Activity
        'user_notifications': recent_activity,
        
        # Zone 3: Informational
        'informational_notifications': informational,
        
        # Filter state
        'filter_category': filter_category,
        'search_query': search_query,
        'category_counts': category_counts,
        
        # Time helpers
        'today': timezone.now().date(),
        'yesterday': timezone.now().date() - timedelta(days=1),
    }
    
    return render(request, 'user_dashboard/all_notifications.html', context)


def get_notification_category(notification):
    """Determine notification category based on title and body"""
    title_lower = notification.notification_title.lower()
    body_lower = notification.notification_body.lower()
    
    if hasattr(notification, 'purpose') and notification.purpose == 'mgr':
        return 'mgr'
    
    if any(word in title_lower or word in body_lower for word in ['withdraw', 'disburs', 'transferred out']):
        return 'withdrawals'
    elif any(word in title_lower or word in body_lower for word in ['deposit', 'top up', 'credited', 'added funds']):
        return 'deposits'
    elif any(word in title_lower or word in body_lower for word in ['merry', 'round', 'contribution', 'payout', 'mgr']):
        return 'mgr'
    elif any(word in title_lower or word in body_lower for word in ['goal', 'target', 'saving', 'express']):
        return 'goals'
    else:
        return 'other'



@login_required(login_url='Login')
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    try:
        count = UserNotificationHistory.objects.filter(user=request.user).count()
        
        return JsonResponse({
            'success': True,
            'message': f'Marked {count} notifications as read'
        })
    
    except Exception as e:
        logger.error(f"Error marking all as read: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='Login')
@require_http_methods(["GET"])
def get_urgent_notifications_expanded(request):
    """Get all urgent notifications (for expanding the urgent stack)"""
    try:
        return JsonResponse({
            'success': True,
            'message': 'Expanded view not yet implemented',
            'html': '<p>All urgent notifications will appear here</p>'
        })
    
    except Exception as e:
        logger.error(f"Error getting expanded urgent notifications: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)