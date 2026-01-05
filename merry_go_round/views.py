# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Prefetch
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from django.urls import reverse
from .models import MGRWallet, MGRTransaction
from .wallet_services import WalletService, MainWalletIntegrationService
from django.db.models.functions import Round

from .models import (
    Round, RoundMembership, Contribution, Payout,
    Invitation, UserProfile, RoundMessage, Notification
)
from .forms import (
    RoundCreationForm, JoinRoundForm, InvitationForm,
    ContributionConfirmForm, RoundMessageForm, RoundFilterForm,
    PayoutPositionForm, RoundUpdateForm, BulkInvitationForm,
    NationalIDInvitationForm # Import the new form
)
from .services import (
    RoundService, ContributionService, PayoutService,
    InvitationService, NotificationService
)

import logging
logger = logging.getLogger(__name__)



# ============================================
# HELPER FUNCTION FOR USER DISPLAY NAME
# ============================================
def get_user_display_name(user):
    """
    Get user display name as: FirstName LastInitial
    Example: "John D."
    """
    if user.first_name:
        last_initial = f"{user.last_name[0]}." if user.last_name else ""
        return f"{user.first_name} {last_initial}".strip()
    return user.username


@login_required
def dashboard(request):
    """Main dashboard view - FIXED template rendering"""
    # Get or create user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get user's active rounds
    active_memberships = RoundMembership.objects.filter(
        user=request.user,
        status__in=['active', 'pending']
    ).select_related('round').prefetch_related(
        Prefetch('contributions', queryset=Contribution.objects.order_by('-due_date'))
    )
    
    # Add display names to memberships
    for membership in active_memberships:
        membership.display_name = get_user_display_name(membership.user)
    
    # Get completed memberships
    completed_memberships = RoundMembership.objects.filter(
        user=request.user,
        status='completed'
    ).select_related('round').order_by('-round__end_date')[:5]
    
    for membership in completed_memberships:
        membership.display_name = get_user_display_name(membership.user)
    
    # Calculate dashboard statistics
    total_contributed = profile.total_contributions
    total_interest = RoundMembership.objects.filter(
        user=request.user
    ).aggregate(total=Sum('interest_earned'))['total'] or Decimal('0.00')
    
    # Get upcoming contributions
    upcoming_contributions = Contribution.objects.filter(
        membership__user=request.user,
        status='pending',
        due_date__gte=timezone.now().date()
    ).select_related('membership__round').order_by('due_date')[:5]
    
    # Get upcoming payouts
    upcoming_payouts = Payout.objects.filter(
        recipient_membership__user=request.user,
        status='scheduled'
    ).select_related('round').order_by('scheduled_date')[:5]
    
    # Get recent notifications
    recent_notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]
    
    unread_count = NotificationService.get_unread_count(request.user)
    
    # Get pending invitations
    from authentication.models import Profile 
    try:
        user_auth_profile = Profile.objects.get(owner=request.user)
        pending_invites = Invitation.objects.filter(
            Q(invitee_national_id=user_auth_profile.NIC_No) |
            Q(invitee_email=request.user.email) |
            Q(invitee_phone=user_auth_profile.phone),
            status='pending'
        ).select_related('round', 'inviter')[:5]
    except Profile.DoesNotExist:
        pending_invites = Invitation.objects.filter(
            invitee_email=request.user.email,
            status='pending'
        ).select_related('round', 'inviter')[:5]

    # Check for newly completed rounds
    today = timezone.now().date()
    newly_completed_round = RoundMembership.objects.filter(
        user=request.user,
        status='completed',
        round__end_date=today
    ).select_related('round').first()

    context = {
        'profile': profile,
        'active_memberships': active_memberships,
        'completed_memberships': completed_memberships,
        'total_contributed': total_contributed,
        'total_interest': total_interest,
        'completed_rounds': profile.completed_rounds,
        'trust_score': profile.trust_score,
        'upcoming_contributions': upcoming_contributions,
        'upcoming_payouts': upcoming_payouts,
        'recent_notifications': recent_notifications,
        'unread_count': unread_count,
        'pending_invites': pending_invites,
        'newly_completed_round': newly_completed_round,
    }
    
    
    return render(request, 'merry_go_round/dashboard.html', context)


# Replace the join_round function in views.py with this corrected version

@login_required
def join_round(request):
    """View for browsing and joining public rounds"""
    # Get filter form
    filter_form = RoundFilterForm(request.GET or None)
    
    # Base queryset - public rounds only
    rounds = Round.objects.filter(
        round_type='public',
        status__in=['open', 'active']
    ).annotate(
        members_count=Count('memberships')
    ).select_related('creator')
    
    # Apply filters
    if filter_form.is_valid():
        # Contribution amount filter
        amount_range = filter_form.cleaned_data.get('contribution_amount')
        if amount_range:
            if amount_range == '0-500':
                rounds = rounds.filter(contribution_amount__gte=100, contribution_amount__lte=500)
            elif amount_range == '500-1000':
                rounds = rounds.filter(contribution_amount__gt=500, contribution_amount__lte=1000)
            elif amount_range == '1000-5000':
                rounds = rounds.filter(contribution_amount__gt=1000, contribution_amount__lte=5000)
            elif amount_range == '5000-10000':
                rounds = rounds.filter(contribution_amount__gt=5000, contribution_amount__lte=10000)
            elif amount_range == '10000+':
                rounds = rounds.filter(contribution_amount__gt=10000)
        
        # Frequency filter
        frequency = filter_form.cleaned_data.get('frequency')
        if frequency:
            rounds = rounds.filter(frequency=frequency)
        
        # Trust score filter
        trust_score = filter_form.cleaned_data.get('min_trust_score')
        if trust_score:
            if trust_score == '0-30':
                rounds = rounds.filter(min_trust_score__gte=0, min_trust_score__lte=30)
            elif trust_score == '30-50':
                rounds = rounds.filter(min_trust_score__gt=30, min_trust_score__lte=50)
            elif trust_score == '50-70':
                rounds = rounds.filter(min_trust_score__gt=50, min_trust_score__lte=70)
            elif trust_score == '70-100':
                rounds = rounds.filter(min_trust_score__gt=70)
        
        # Status filter
        status = filter_form.cleaned_data.get('status')
        if status:
            rounds = rounds.filter(status=status)
        
        # Search filter
        search = filter_form.cleaned_data.get('search')
        if search:
            rounds = rounds.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
    
    # Get user's current memberships to exclude already joined rounds
    user_round_ids = RoundMembership.objects.filter(
        user=request.user
    ).values_list('round_id', flat=True)
    
    rounds = rounds.exclude(id__in=user_round_ids)
    
    # Pagination
    paginator = Paginator(rounds, 12)  # 12 rounds per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # FIXED: Use the correct method name for accurate interest calculation
    for round_obj in page_obj:
        total_cycles = round_obj.calculate_total_cycles()
        total_contribution = round_obj.contribution_amount * total_cycles
        
        # Use the accurate method with after-tax calculation
        round_obj.projected_interest = round_obj.get_accurate_projected_interest_after_tax(total_contribution)
        round_obj.total_expected = total_contribution + round_obj.projected_interest
        
        # First contribution required (not total commitment)
        round_obj.first_contribution_required = round_obj.contribution_amount
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
    }
    
    return render(request, 'merry_go_round/join_round.html', context)


@login_required
@require_http_methods(["POST"])
def join_round_action(request, round_id):
    """Handle joining a round"""
    round_obj = get_object_or_404(Round, id=round_id)
    
    form = JoinRoundForm(request.POST, user=request.user)
    
    if form.is_valid():
        try:
            membership = RoundService.add_member_to_round(round_obj, request.user)
            messages.success(request, f'Successfully joined {round_obj.name}!')
            return redirect('merry_go_round:round_detail', round_id=round_obj.id)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('merry_go_round:join_round')
    else:
        for error in form.errors.values():
            messages.error(request, error)
        return redirect('merry_go_round:join_round')


@login_required
def create_round(request):
    """View for creating a new round"""
    # Get or create user profile
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = RoundCreationForm(request.POST)
        
        if form.is_valid():
            try:
                round_obj = RoundService.create_round(request.user, form.cleaned_data)
                messages.success(request, f'Round "{round_obj.name}" created successfully!')
                return redirect('merry_go_round:round_detail', round_id=round_obj.id)
            except Exception as e:
                messages.error(request, f'Error creating round: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = RoundCreationForm()
    
    context = {
        'form': form,
        'profile': profile,
    }
    
    return render(request, 'merry_go_round/create_round.html', context)


#@login_required
#def round_detail(request, round_id):
    """
    FIXED: Ensure completion_stats are available for banner display
    """
    round_obj = get_object_or_404(Round, id=round_id)
    
    # Check if user is a member
    try:
        user_membership = RoundMembership.objects.get(round=round_obj, user=request.user)
        is_member = True
    except RoundMembership.DoesNotExist:
        user_membership = None
        is_member = False
    
    # Only members can view private rounds
    if round_obj.round_type == 'private' and not is_member:
        messages.error(request, 'You do not have access to this round.')
        return redirect('merry_go_round:dashboard')
    
    # Get all memberships with display names
    memberships = RoundMembership.objects.filter(
        round=round_obj
    ).select_related('user').order_by('payout_position', 'join_date')
    
    for membership in memberships:
        membership.display_name = get_user_display_name(membership.user)
    
    # Get user's contributions if member
    user_contributions = None
    next_contribution = None
    if is_member:
        user_contributions = Contribution.objects.filter(
            membership=user_membership
        ).order_by('-cycle_number')
        
        next_contribution = Contribution.objects.filter(
            membership=user_membership,
            status='pending'
        ).order_by('due_date').first()
    
    # Get round messages
    messages_list = RoundMessage.objects.filter(
        round=round_obj
    ).select_related('sender').order_by('-is_pinned', '-created_at')[:20]
    
    for msg in messages_list:
        msg.sender_display = get_user_display_name(msg.sender)
    
    # Get payout schedule with display names
    payouts = Payout.objects.filter(round=round_obj).order_by('payout_cycle')
    for payout in payouts:
        payout.recipient_display = get_user_display_name(payout.recipient_membership.user)
    
    # Message form
    message_form = RoundMessageForm()
    
    # Calculate progress
    progress_percentage = 0
    completion_stats = None
    
    if round_obj.status == 'active':
        total_cycles = round_obj.calculate_total_cycles()
        total_expected = round_obj.contribution_amount * round_obj.max_members * total_cycles
        progress_percentage = (round_obj.total_pool / total_expected * 100) if total_expected > 0 else 0
    
    elif round_obj.status == 'completed':
        # ==========================================
        # FIXED: Get frozen stats for EVERYONE (not just members)
        # ==========================================
        from .models import RoundCompletionStats
        
        try:
            # Get frozen round-level stats
            frozen_stats = RoundCompletionStats.objects.get(round=round_obj)
            
            # Build base completion stats from frozen data (for banner display)
            completion_stats = {
                # Round-level stats (always available)
                'total_expected': frozen_stats.total_expected_contributions,
                'total_actual': frozen_stats.total_actual_contributions,
                'completion_percentage': frozen_stats.completion_percentage,
                'total_paid_out': frozen_stats.total_paid_out,
                'total_gross_interest': frozen_stats.total_gross_interest,
                'total_net_interest': frozen_stats.total_net_interest,
                'total_tax_deducted': frozen_stats.total_tax_deducted,
                'tax_rate_percent': frozen_stats.tax_rate_used,
                'interest_rate_percent': frozen_stats.interest_rate_used,
                'is_partial_completion': frozen_stats.completion_percentage < 100,
                'shortfall': max(0, frozen_stats.total_expected_contributions - frozen_stats.total_actual_contributions),
            }
            
            # If user is a member, add their personal stats
            if user_membership:
                # Get user's ACTUAL payout
                user_payout = Payout.objects.filter(
                    round=round_obj,
                    recipient_membership=user_membership,
                    status='completed'
                ).first()
                
                if user_payout:
                    # Use actual payout values
                    user_paid_out = user_payout.amount
                    user_principal_received = user_payout.principal_amount
                    user_net_interest = user_payout.interest_amount
                    
                    # Calculate gross interest from net using FROZEN tax rate
                    tax_rate_decimal = frozen_stats.tax_rate_used / 100
                    if user_net_interest > 0:
                        user_gross_interest = user_net_interest / (1 - tax_rate_decimal)
                        user_tax = user_gross_interest - user_net_interest
                    else:
                        user_gross_interest = Decimal('0.00')
                        user_tax = Decimal('0.00')
                else:
                    # No payout yet
                    user_paid_out = Decimal('0.00')
                    user_principal_received = Decimal('0.00')
                    user_net_interest = Decimal('0.00')
                    user_gross_interest = Decimal('0.00')
                    user_tax = Decimal('0.00')
                
                # Calculate user's completion percentage
                total_cycles = round_obj.calculate_total_cycles()
                user_expected = round_obj.contribution_amount * total_cycles
                user_actual = user_membership.total_contributed
                user_completion_pct = (user_actual / user_expected * 100) if user_expected > 0 else 0
                user_shortfall = user_expected - user_actual
                
                # Add user-specific stats to completion_stats
                completion_stats.update({
                    # User-specific overrides
                    'user_total_expected': user_expected,
                    'user_total_actual': user_actual,
                    'user_completion_percentage': user_completion_pct,
                    'user_paid_out': user_paid_out,
                    'principal_received': user_principal_received,
                    'interest_received': user_net_interest,
                    'user_gross_interest': user_gross_interest,
                    'user_tax_deducted': user_tax,
                    'contributions_made': user_membership.contributions_made,
                    'contributions_missed': user_membership.contributions_missed,
                    'user_shortfall': user_shortfall,
                    'is_partial_completion': user_completion_pct < 100,
                })
        
        except RoundCompletionStats.DoesNotExist:
            # Fallback for old completed rounds (before frozen stats)
            logger.warning(f"No frozen stats for completed round {round_obj.id} - calculating live")
            
            # Calculate live stats as fallback
            total_cycles = round_obj.calculate_total_cycles()
            total_expected = round_obj.contribution_amount * round_obj.max_members * total_cycles
            
            # Get actual totals
            completed_payouts = Payout.objects.filter(
                round=round_obj,
                status='completed'
            ).aggregate(
                total_paid=Sum('amount'),
                total_principal=Sum('principal_amount'),
                total_interest=Sum('interest_amount')
            )
            
            total_paid_out = completed_payouts['total_paid'] or Decimal('0.00')
            total_principal = completed_payouts['total_principal'] or Decimal('0.00')
            total_net_interest = completed_payouts['total_interest'] or Decimal('0.00')
            
            # Calculate gross interest and tax
            from constance import config
            tax_rate_percent = config.MGR_TAX_RATE
            tax_rate_decimal = Decimal(str(tax_rate_percent)) / 100
            
            if total_net_interest > 0:
                total_gross_interest = total_net_interest / (1 - tax_rate_decimal)
                total_tax = total_gross_interest - total_net_interest
            else:
                total_gross_interest = Decimal('0.00')
                total_tax = Decimal('0.00')
            
            completion_pct = (total_principal / total_expected * 100) if total_expected > 0 else 0
            
            completion_stats = {
                'total_expected': total_expected,
                'total_actual': total_principal,
                'completion_percentage': completion_pct,
                'total_paid_out': total_paid_out,
                'total_gross_interest': total_gross_interest,
                'total_net_interest': total_net_interest,
                'total_tax_deducted': total_tax,
                'tax_rate_percent': tax_rate_percent,
                'interest_rate_percent': round_obj.interest_rate,
                'is_partial_completion': completion_pct < 100,
                'shortfall': max(0, total_expected - total_principal),
            }
            
            # Add user stats if member
            if user_membership:
                user_payout = Payout.objects.filter(
                    round=round_obj,
                    recipient_membership=user_membership,
                    status='completed'
                ).first()
                
                if user_payout:
                    completion_stats.update({
                        'user_total_actual': user_membership.total_contributed,
                        'principal_received': user_payout.principal_amount,
                        'interest_received': user_payout.interest_amount,
                        'user_paid_out': user_payout.amount,
                        'contributions_made': user_membership.contributions_made,
                    })
        
        progress_percentage = completion_stats['completion_percentage'] if completion_stats else 0
    
    context = {
        'round': round_obj,
        'is_member': is_member,
        'user_membership': user_membership,
        'memberships': memberships,
        'user_contributions': user_contributions,
        'next_contribution': next_contribution,
        'messages_list': messages_list,
        'message_form': message_form,
        'payouts': payouts,
        'progress_percentage': progress_percentage,
        'is_creator': request.user == round_obj.creator,
        'completion_stats': completion_stats,  # Now available for everyone!
    }
    
    return render(request, 'merry_go_round/round_detail.html', context)

@login_required
def round_detail(request, round_id):
    """
    ACTIVE/PENDING ROUND VIEW - Shows current progress and actions
    Redirects to round_complete_detail if round is completed
    """
    round_obj = get_object_or_404(Round, id=round_id)
    
    # REDIRECT completed rounds to dedicated view
    if round_obj.status == 'completed':
        return redirect('merry_go_round:round_complete_detail', round_id=round_id)
    
    # Check if user is a member
    try:
        user_membership = RoundMembership.objects.get(round=round_obj, user=request.user)
        is_member = True
    except RoundMembership.DoesNotExist:
        user_membership = None
        is_member = False
    
    # Only members can view private rounds
    if round_obj.round_type == 'private' and not is_member:
        messages.error(request, 'You do not have access to this round.')
        return redirect('merry_go_round:dashboard')
    
    # Get all memberships with display names
    memberships = RoundMembership.objects.filter(
        round=round_obj
    ).select_related('user').order_by('payout_position', 'join_date')
    
    for membership in memberships:
        membership.display_name = get_user_display_name(membership.user)
    
    # Get user's contributions if member
    user_contributions = None
    next_contribution = None
    if is_member:
        user_contributions = Contribution.objects.filter(
            membership=user_membership
        ).order_by('-cycle_number')
        
        next_contribution = Contribution.objects.filter(
            membership=user_membership,
            status='pending'
        ).order_by('due_date').first()
    
    # Get round messages
    messages_list = RoundMessage.objects.filter(
        round=round_obj
    ).select_related('sender').order_by('-is_pinned', '-created_at')[:20]
    
    for msg in messages_list:
        msg.sender_display = get_user_display_name(msg.sender)
    
    # Get payout schedule with display names
    payouts = Payout.objects.filter(round=round_obj).order_by('payout_cycle')
    for payout in payouts:
        payout.recipient_display = get_user_display_name(payout.recipient_membership.user)
    
    # Message form
    message_form = RoundMessageForm()
    
    # Calculate progress for active rounds
    progress_percentage = 0
    if round_obj.status == 'active':
        total_cycles = round_obj.calculate_total_cycles()
        total_expected = round_obj.contribution_amount * round_obj.max_members * total_cycles
        progress_percentage = (round_obj.total_pool / total_expected * 100) if total_expected > 0 else 0
    
    context = {
        'round': round_obj,
        'is_member': is_member,
        'user_membership': user_membership,
        'memberships': memberships,
        'user_contributions': user_contributions,
        'next_contribution': next_contribution,
        'messages_list': messages_list,
        'message_form': message_form,
        'payouts': payouts,
        'progress_percentage': progress_percentage,
        'is_creator': request.user == round_obj.creator,
    }
    
    return render(request, 'merry_go_round/round_detail.html', context)


@login_required
def round_complete_detail(request, round_id):
    """
    COMPLETE ROUND VIEW - Shows frozen stats and celebration UI
    This view is ONLY for completed rounds
    """
    round_obj = get_object_or_404(Round, id=round_id, status='completed')
    
    # Check if user is a member
    try:
        user_membership = RoundMembership.objects.get(round=round_obj, user=request.user)
        is_member = True
    except RoundMembership.DoesNotExist:
        user_membership = None
        is_member = False
    
    # Only members can view private rounds
    if round_obj.round_type == 'private' and not is_member:
        messages.error(request, 'You do not have access to this round.')
        return redirect('merry_go_round:dashboard')
    
    # Get frozen completion stats (REQUIRED for completed rounds)
    from .models import RoundCompletionStats
    
    try:
        frozen_stats = RoundCompletionStats.objects.get(round=round_obj)
    except RoundCompletionStats.DoesNotExist:
        # This shouldn't happen, but handle gracefully
        messages.warning(request, 'Completion statistics not yet available for this round.')
        return redirect('merry_go_round:dashboard')
    
    # Build round-level completion data
    completion_data = {
        # Round-level frozen stats
        'round': {
            'total_expected': frozen_stats.total_expected_contributions,
            'total_actual': frozen_stats.total_actual_contributions,
            'completion_percentage': frozen_stats.completion_percentage,
            'total_paid_out': frozen_stats.total_paid_out,
            'total_gross_interest': frozen_stats.total_gross_interest,
            'total_net_interest': frozen_stats.total_net_interest,
            'total_tax_deducted': frozen_stats.total_tax_deducted,
            'tax_rate_percent': frozen_stats.tax_rate_used,
            'interest_rate_percent': frozen_stats.interest_rate_used,
            'is_partial_completion': frozen_stats.completion_percentage < 100,
            'shortfall': max(0, frozen_stats.total_expected_contributions - frozen_stats.total_actual_contributions),
        }
    }
    
    # Get all memberships with display names
    memberships = RoundMembership.objects.filter(
        round=round_obj
    ).select_related('user').order_by('payout_position', 'join_date')
    
    for membership in memberships:
        membership.display_name = get_user_display_name(membership.user)
        
        # Add payout information
        membership.payout_info = Payout.objects.filter(
            round=round_obj,
            recipient_membership=membership,
            status='completed'
        ).first()
    
    # If user is a member, get their personal stats
    user_stats = None
    user_contributions = None
    
    if is_member and user_membership:
        # Get user's payout
        user_payout = Payout.objects.filter(
            round=round_obj,
            recipient_membership=user_membership,
            status='completed'
        ).first()
        
        if user_payout:
            # Calculate user's gross interest from net
            tax_rate_decimal = frozen_stats.tax_rate_used / 100
            user_net_interest = user_payout.interest_amount
            
            if user_net_interest > 0:
                user_gross_interest = user_net_interest / (1 - tax_rate_decimal)
                user_tax = user_gross_interest - user_net_interest
            else:
                user_gross_interest = Decimal('0.00')
                user_tax = Decimal('0.00')
        else:
            user_gross_interest = Decimal('0.00')
            user_net_interest = Decimal('0.00')
            user_tax = Decimal('0.00')
        
        # Calculate user's completion rate
        total_cycles = round_obj.calculate_total_cycles()
        user_expected = round_obj.contribution_amount * total_cycles
        user_actual = user_membership.total_contributed
        user_completion_pct = (user_actual / user_expected * 100) if user_expected > 0 else 0
        
        user_stats = {
            'expected_total': user_expected,
            'actual_contributed': user_actual,
            'completion_percentage': user_completion_pct,
            'contributions_made': user_membership.contributions_made,
            'contributions_missed': user_membership.contributions_missed,
            'gross_interest': user_gross_interest,
            'net_interest': user_net_interest,
            'tax_deducted': user_tax,
            'total_payout': user_payout.amount if user_payout else Decimal('0.00'),
            'shortfall': max(0, user_expected - user_actual),
            'is_partial': user_completion_pct < 100,
        }
        
        # Get user's contribution history
        user_contributions = Contribution.objects.filter(
            membership=user_membership
        ).order_by('cycle_number')
    
    # Get round messages
    messages_list = RoundMessage.objects.filter(
        round=round_obj
    ).select_related('sender').order_by('-is_pinned', '-created_at')[:20]
    
    for msg in messages_list:
        msg.sender_display = get_user_display_name(msg.sender)
    
    # Get all payouts
    payouts = Payout.objects.filter(round=round_obj).order_by('payout_cycle')
    for payout in payouts:
        payout.recipient_display = get_user_display_name(payout.recipient_membership.user)
    
    # Message form (if member)
    message_form = RoundMessageForm() if is_member else None
    
    context = {
        'round': round_obj,
        'is_member': is_member,
        'user_membership': user_membership,
        'is_creator': request.user == round_obj.creator,
        'completion_data': completion_data,
        'user_stats': user_stats,
        'memberships': memberships,
        'user_contributions': user_contributions,
        'payouts': payouts,
        'messages_list': messages_list,
        'message_form': message_form,
        'frozen_at': frozen_stats.completed_at,
    }
    
    return render(request, 'merry_go_round/round_complete_detail.html', context)

@login_required
def my_rounds(request):
    """View showing all user's rounds - FIXED to exclude removed memberships"""
    memberships = RoundMembership.objects.filter(
        user=request.user
    ).exclude(
        status='removed'  # ADDED: Exclude removed memberships
    ).select_related('round').order_by('-join_date')
    
    # Categorize rounds
    active_rounds = [m for m in memberships if m.round.status == 'active']
    pending_rounds = [m for m in memberships if m.round.status in ['draft', 'open']]
    completed_rounds = [m for m in memberships if m.round.status == 'completed']
    
    context = {
        'active_rounds': active_rounds,
        'pending_rounds': pending_rounds,
        'completed_rounds': completed_rounds,
    }
    
    return render(request, 'merry_go_round/my_rounds.html', context)

@login_required
@require_http_methods(["POST"])
def delete_completed_round(request, round_id):
    """
    NEW: Allow users to delete their completed rounds from their view
    """
    round_obj = get_object_or_404(Round, id=round_id)
    
    # Check if user is a member
    try:
        membership = RoundMembership.objects.get(
            round=round_obj,
            user=request.user,
            status='completed'
        )
    except RoundMembership.DoesNotExist:
        return JsonResponse({
            'error': 'You are not a member of this round or it is not completed'
        }, status=403)
    
    # Check if round is actually completed
    if round_obj.status != 'completed':
        return JsonResponse({
            'error': 'Can only delete completed rounds'
        }, status=400)
    
    try:
        # Don't actually delete the round - just hide it from user's view
        # by marking membership as 'removed'
        membership.status = 'removed'
        membership.save()
        
        messages.success(request, f'Round "{round_obj.name}" removed from your completed rounds.')
        return JsonResponse({
            'success': True,
            'message': f'Round "{round_obj.name}" removed successfully',
            'redirect_url': reverse('merry_go_round:my_rounds')
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def post_message(request, round_id):
    """Post a message to a round"""
    round_obj = get_object_or_404(Round, id=round_id)
    
    # Check if user is a member
    if not RoundMembership.objects.filter(round=round_obj, user=request.user).exists():
        return JsonResponse({'error': 'Not a member'}, status=403)
    
    form = RoundMessageForm(request.POST)
    
    if form.is_valid():
        message = form.save(commit=False)
        message.round = round_obj
        message.sender = request.user
        message.message_type = 'user'
        message.save()
        
        return JsonResponse({
            'success': True,
            'message': {
                'sender': request.user.username,
                'content': message.content,
                'subject': message.subject,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M')
            }
        })
    
    return JsonResponse({'error': 'Invalid form'}, status=400)


@login_required
@require_http_methods(["POST"])
def make_contribution(request, contribution_id):
    """Process a contribution payment"""
    contribution = get_object_or_404(Contribution, id=contribution_id)
    
    # Check if user owns this contribution
    if contribution.membership.user != request.user:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    form = ContributionConfirmForm(request.POST)
    
    if form.is_valid():
        try:
            # Here you would integrate with M-Pesa STK Push
            # For now, simulate with a transaction ID
            transaction_id = f'TXN-{timezone.now().timestamp()}'
            
            ContributionService.process_contribution(
                contribution,
                transaction_id,
                form.cleaned_data['payment_method']
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Contribution processed successfully',
                'transaction_id': transaction_id
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid form'}, status=400)


@login_required
def send_invitation(request, round_id):
    """
    ENHANCED: Complete invitation interface with lookup, batch sending, and shareable links
    """
    round_obj = get_object_or_404(Round, id=round_id)
    
    # Check permissions
    if round_obj.creator != request.user:
        messages.error(request, 'Only the round creator can send invitations.')
        return redirect('merry_go_round:round_detail', round_id=round_id)
    
    if round_obj.round_type != 'private':
        messages.error(request, 'Invitations are only for private rounds.')
        return redirect('merry_go_round:round_detail', round_id=round_id)
    
    members_needed = max(0, round_obj.max_members - round_obj.current_members)
    
    # FIXED: Generate shareable link properly
    invitation_link = request.build_absolute_uri(
        reverse('merry_go_round:join_via_link', kwargs={'round_id': round_obj.id})
    )
    
    # Get pending invitations with reminder info
    pending_invitations = Invitation.objects.filter(
        round=round_obj,
        status='pending'
    ).order_by('-created_at')
    
    # Calculate days since invitation
    for invite in pending_invitations:
        days_ago = (timezone.now() - invite.created_at).days
        invite.days_ago = days_ago
        invite.needs_reminder = days_ago >= 1
    
    context = {
        'round': round_obj,
        'pending_invitations': pending_invitations,
        'members_needed': members_needed,
        'invitation_link': invitation_link,
    }
    
    return render(request, 'merry_go_round/send_invitation.html', context)


@login_required
def review_invitation(request, token):
    """
    NEW: Review invitation - Accept or Decline
    """
    invitation = get_object_or_404(Invitation, token=token)
    
    if invitation.is_expired():
        messages.error(request, 'This invitation has expired.')
        return redirect('merry_go_round:dashboard')
    
    if invitation.status != 'pending':
        messages.error(request, 'This invitation is no longer valid.')
        return redirect('merry_go_round:dashboard')
    
    # Verify invitation is for current user
    from authentication.models import Profile
    try:
        current_user_profile = Profile.objects.get(owner=request.user)
        
        is_for_user = (
            (invitation.invitee_national_id and 
             invitation.invitee_national_id == current_user_profile.NIC_No) or
            (invitation.invitee_email and 
             invitation.invitee_email == request.user.email) or
            (invitation.invitee_phone and 
             invitation.invitee_phone == current_user_profile.phone)
        )
        
        if not is_for_user:
            messages.error(request, 'This invitation is not for your account.')
            return redirect('merry_go_round:dashboard')
    except Profile.DoesNotExist:
        pass
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'accept':
            try:
                membership = InvitationService.accept_invitation(invitation, request.user)
                messages.success(request, f'Successfully joined {invitation.round.name}!')
                return redirect('merry_go_round:round_detail', round_id=invitation.round.id)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('merry_go_round:dashboard')
        
        elif action == 'decline':
            invitation.status = 'declined'
            invitation.save()
            
            # Notify inviter
            NotificationService.create_notification(
                user=invitation.inviter,
                notification_type='member_defaulted',
                title=f'Invitation Declined - {invitation.round.name}',
                message=f'{get_user_display_name(request.user)} declined your invitation to join {invitation.round.name}.',
                round=invitation.round,
                action_url=reverse('merry_go_round:send_invitation', kwargs={'round_id': invitation.round.id})
            )
            
            messages.info(request, 'You have declined the invitation.')
            return redirect('merry_go_round:dashboard')
    
    # Calculate round details
    round_obj = invitation.round
    total_commitment = round_obj.get_total_commitment_amount()
    first_contribution = round_obj.contribution_amount
    projected_interest = round_obj.get_accurate_projected_interest_after_tax(total_commitment)
    
    context = {
        'invitation': invitation,
        'round': round_obj,
        'inviter_name': get_user_display_name(invitation.inviter),
        'total_commitment': total_commitment,
        'first_contribution': first_contribution,
        'projected_interest': projected_interest,
        'total_return': total_commitment + projected_interest,
    }
    
    return render(request, 'merry_go_round/review_invitation.html', context)


@login_required
def accept_invitation(request, token):
    """Accept an invitation and join a round"""
    invitation = get_object_or_404(Invitation, token=token)
    
    if invitation.is_expired():
        messages.error(request, 'This invitation has expired.')
        return redirect('merry_go_round:dashboard')
    
    if invitation.status != 'pending':
        messages.error(request, 'This invitation is no longer valid.')
        return redirect('merry_go_round:dashboard')
    
    # NEW: Check if invitation is for National ID and matches current user
    if invitation.invitee_national_id:
        # This is a National ID invitation
        from authentication.models import Profile
        try:
            # Get the current user's profile
            current_user_profile = Profile.objects.get(owner=request.user)
            # Check if the invitation's NIC_No matches the current user's NIC_No
            if current_user_profile.NIC_No != invitation.invitee_national_id:
                 messages.error(request, 'This invitation is not intended for your account.')
                 return redirect('merry_go_round:dashboard')
        except Profile.DoesNotExist:
            messages.error(request, 'Your account profile is missing. Please contact support.')
            return redirect('merry_go_round:dashboard')
    
    # Proceed with acceptance (works for email/phone or verified NIC invitations)
    try:
        membership = InvitationService.accept_invitation(invitation, request.user)
        messages.success(request, f'Successfully joined {invitation.round.name}!')
        return redirect('merry_go_round:round_detail', round_id=invitation.round.id)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('merry_go_round:dashboard')
    
@login_required
@require_http_methods(["POST"])
def api_lookup_member(request):
        """
        NEW: API endpoint for member lookup by National ID or Phone
        """
        lookup_type = request.POST.get('lookup_type')
        lookup_value = request.POST.get('lookup_value')
        
        if not lookup_type or not lookup_value:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        # Perform lookup
        member_data = InvitationService.lookup_member(lookup_type, lookup_value)
        
        if member_data:
            return JsonResponse({
                'success': True,
                'member': member_data
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Member not found in ChamaSpace'
            }, status=404)


@login_required
@require_http_methods(["POST"])
def api_send_batch_invitations(request, round_id):
        """
        NEW: API endpoint for sending batch invitations
        """
        round_obj = get_object_or_404(Round, id=round_id)
        
        # Check permissions
        if round_obj.creator != request.user:
            return JsonResponse({'error': 'Only creator can send invitations'}, status=403)
        
        if round_obj.round_type != 'private':
            return JsonResponse({'error': 'Can only send invitations to private rounds'}, status=400)
        
        try:
            import json
            invitation_data = json.loads(request.POST.get('invitation_data', '[]'))
            message = request.POST.get('message', '')
            
            if not invitation_data:
                return JsonResponse({'error': 'No invitations to send'}, status=400)
            
            # Send batch invitations
            results = InvitationService.send_batch_invitations(
                round_obj=round_obj,
                inviter=request.user,
                invitation_list=invitation_data,
                message=message,
                request=request
            )
            
            return JsonResponse({
                'success': True,
                'results': results,
                'message': f"Sent {results['successful']} invitation(s)"
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid invitation data'}, status=400)
        except Exception as e:
            logger.error(f"Batch invitation error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)    


@login_required
def api_get_shareable_link(request, round_id):
        """
        NEW: API endpoint to get shareable invitation link
        """
        round_obj = get_object_or_404(Round, id=round_id)
        
        # Check permissions - only members or creator can get link
        is_member = RoundMembership.objects.filter(round=round_obj, user=request.user).exists()
        is_creator = round_obj.creator == request.user
        
        if not (is_member or is_creator):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        shareable_link = InvitationService.get_round_shareable_link(round_obj, request)
        
        return JsonResponse({
            'success': True,
            'link': shareable_link,
            'round': {
                'name': round_obj.name,
                'contribution_amount': str(round_obj.contribution_amount),
                'frequency': round_obj.get_frequency_display(),
                'members': f"{round_obj.current_members}/{round_obj.max_members}",
                'payout_model': round_obj.get_payout_model_display(),
            }
        })


@login_required
def join_via_link(request, round_id):
        """
        NEW: Join a round via shareable link
        """
        round_obj = get_object_or_404(Round, id=round_id)
        
        # Check if already a member
        existing_membership = RoundMembership.objects.filter(
            round=round_obj, 
            user=request.user
        ).first()
        
        if existing_membership:
            messages.info(request, 'You are already a member of this round.')
            return redirect('merry_go_round:round_detail', round_id=round_id)
        
        # For private rounds via link, show review page
        if round_obj.round_type == 'private':
            # Calculate round details
            total_commitment = round_obj.get_total_commitment_amount()
            first_contribution = round_obj.contribution_amount
            projected_interest = round_obj.get_accurate_projected_interest_after_tax(total_commitment)
            
            context = {
                'round': round_obj,
                'total_commitment': total_commitment,
                'first_contribution': first_contribution,
                'projected_interest': projected_interest,
                'total_return': total_commitment + projected_interest,
                'via_link': True,
            }
            
            return render(request, 'merry_go_round/join_via_link.html', context)
        
        # For public rounds, redirect to normal join flow
        return redirect('merry_go_round:join_round')


@login_required
@require_http_methods(["POST"])
def confirm_join_via_link(request, round_id):
        """
        NEW: Confirm joining via shareable link
        """
        round_obj = get_object_or_404(Round, id=round_id)
        
        try:
            # Add user to round
            membership = RoundService.add_member_to_round(round_obj, request.user)
            
            # Notify creator
            NotificationService.create_notification(
                user=round_obj.creator,
                notification_type='member_joined',
                title=f"New Member via Link: {round_obj.name}",
                message=f"{get_user_display_name(request.user)} joined '{round_obj.name}' via shareable link.",
                round=round_obj,
                action_url=reverse('merry_go_round:round_detail', kwargs={'round_id': round_id})
            )
            
            messages.success(request, f'Successfully joined {round_obj.name}!')
            return JsonResponse({
                'success': True,
                'redirect_url': reverse('merry_go_round:round_detail', kwargs={'round_id': round_id})
            })
            
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)   


@login_required
def notifications(request):
    """View all notifications with filtering"""
    filter_type = request.GET.get('filter', 'all')
    
    # Base queryset
    notifications_list = Notification.objects.filter(user=request.user)
    
    # Apply filter
    if filter_type == 'unread':
        notifications_list = notifications_list.filter(is_read=False)
    elif filter_type == 'invitation':
        notifications_list = notifications_list.filter(notification_type='invitation_received')
    
    notifications_list = notifications_list.order_by('-created_at')
    
    # Get counts
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    invitation_count = Notification.objects.filter(
        user=request.user, 
        notification_type='invitation_received',
        is_read=False
    ).count()
    
    # Pagination
    paginator = Paginator(notifications_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'unread_count': unread_count,
        'invitation_count': invitation_count,
    }
    
    return render(request, 'merry_go_round/notifications.html', context)


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def delete_notification(request, notification_id):
    """Delete a notification"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def start_round_action(request, round_id):
    """Start a round (creator only)"""
    round_obj = get_object_or_404(Round, id=round_id)
    
    if round_obj.creator != request.user:
        return JsonResponse({'error': 'Only creator can start round'}, status=403)
    
    try:
        RoundService.start_round(round_obj)
        return JsonResponse({
            'success': True,
            'message': 'Round started successfully!'
        })
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def contribution_history(request):
    """View all user's contribution history"""
    contributions = Contribution.objects.filter(
        membership__user=request.user
    ).select_related('membership__round').order_by('-due_date')
    
    # Statistics
    total_paid = contributions.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    total_missed = contributions.filter(status='missed').count()
    
    # Add missing context variables
    total_rounds = RoundMembership.objects.filter(user=request.user).count()
    
    total_interest = RoundMembership.objects.filter(
        user=request.user
    ).aggregate(total=Sum('interest_earned'))['total'] or Decimal('0.00')
    
    # Calculate completion rate
    total_contributions = contributions.count()
    completed_contributions = contributions.filter(status='completed').count()
    completion_rate = (completed_contributions / total_contributions * 100) if total_contributions > 0 else 0
    
    # Calculate average contribution
    average_contribution = total_paid / completed_contributions if completed_contributions > 0 else Decimal('0.00')
    
    # Completed rounds count
    completed_rounds = RoundMembership.objects.filter(
        user=request.user,
        status='completed'
    ).count()
    
    # Pagination
    paginator = Paginator(contributions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_paid': total_paid,
        'total_missed': total_missed,
        'total_rounds': total_rounds,
        'total_interest': total_interest,
        'completion_rate': completion_rate,
        'average_contribution': average_contribution,
        'completed_rounds': completed_rounds,
    }
    
    return render(request, 'merry_go_round/contribution_history.html', context)


@login_required
def payout_history(request):
    """View all user's payout history"""
    payouts = Payout.objects.filter(
        recipient_membership__user=request.user
    ).select_related('round').order_by('-scheduled_date')
    
    # Statistics
    total_received = payouts.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    total_interest = payouts.filter(status='completed').aggregate(
        total=Sum('interest_amount')
    )['total'] or Decimal('0.00')
    
    # Pagination
    paginator = Paginator(payouts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_received': total_received,
        'total_interest': total_interest,
    }
    
    return render(request, 'merry_go_round/payout_history.html', context)


# API-style views for AJAX requests

@login_required
def get_round_data(request, round_id):
    """Get round data as JSON"""
    round_obj = get_object_or_404(Round, id=round_id)
    
    # Check access
    if round_obj.round_type == 'private':
        if not RoundMembership.objects.filter(round=round_obj, user=request.user).exists():
            return JsonResponse({'error': 'Access denied'}, status=403)
    
    data = {
        'id': str(round_obj.id),
        'name': round_obj.name,
        'description': round_obj.description,
        'type': round_obj.round_type,
        'model': round_obj.payout_model,
        'contribution_amount': str(round_obj.contribution_amount),
        'frequency': round_obj.frequency,
        'current_members': round_obj.current_members,
        'max_members': round_obj.max_members,
        'status': round_obj.status,
        'total_pool': str(round_obj.total_pool),
        'total_interest': str(round_obj.total_interest_earned),
    }
    
    return JsonResponse(data)


@login_required
def get_user_stats(request):
    """Get user statistics as JSON"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    active_rounds = RoundMembership.objects.filter(
        user=request.user,
        status='active'
    ).count()
    
    pending_contributions = Contribution.objects.filter(
        membership__user=request.user,
        status='pending'
    ).count()
    
    data = {
        'trust_score': profile.trust_score,
        'total_contributions': str(profile.total_contributions),
        'completed_rounds': profile.completed_rounds,
        'active_rounds': active_rounds,
        'pending_contributions': pending_contributions,
    }
    
    return JsonResponse(data)


@login_required
def get_payout_data(request, payout_id):
    """Get payout details as JSON"""
    payout = get_object_or_404(Payout, id=payout_id, recipient_membership__user=request.user)
    
    data = {
        'round_name': payout.round.name,
        'amount': str(payout.amount),
        'principal': str(payout.principal_amount),
        'interest': str(payout.interest_amount),
        'cycle': payout.payout_cycle,
        'scheduled_date': payout.scheduled_date.strftime('%B %d, %Y'),
        'payout_date': payout.payout_date.strftime('%B %d, %Y %H:%M') if payout.payout_date else None,
    }
    
    return JsonResponse(data)


# ========================================
# WALLET VIEWS 
# ========================================


@login_required
def wallet_dashboard(request):
    """MGR Wallet dashboard view"""
    # Get wallet summary
    summary = WalletService.get_wallet_summary(request.user)
    
    # Get all transactions with pagination
    all_transactions = MGRTransaction.objects.filter(
        wallet=summary['wallet']
    ).order_by('-created_at')
    
    # Filter by transaction type if specified
    txn_type = request.GET.get('type')
    if txn_type:
        all_transactions = all_transactions.filter(transaction_type=txn_type)
    
    # Pagination
    paginator = Paginator(all_transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'wallet': summary['wallet'],
        'recent_transactions': summary['recent_transactions'],
        'total_contributions': summary['total_contributions'],
        'total_payouts': summary['total_payouts'],
        'total_interest': summary['total_interest'],
        'page_obj': page_obj,
        'selected_type': txn_type,
    }
    
    return render(request, 'merry_go_round/wallet.html', context)


@login_required
def deposit_to_wallet(request):
    """Deposit funds from main wallet to MGR wallet"""
    wallet = WalletService.get_or_create_wallet(request.user)
    
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
            
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount')
                return redirect('merry_go_round:wallet_dashboard')
            
            # TODO: Verify main wallet balance
            # has_balance = MainWalletIntegrationService.verify_main_wallet_balance(
            #     request.user, amount
            # )
            # if not has_balance:
            #     messages.error(request, 'Insufficient balance in main wallet')
            #     return redirect('merry_go_round:wallet_dashboard')
            
            # Process deposit
            reference = MainWalletIntegrationService.transfer_to_mgr_wallet(
                request.user, amount
            )
            
            messages.success(
                request, 
                f'Successfully deposited KES {amount:,.2f} to your MGR wallet'
            )
            
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Deposit failed: {str(e)}')
        
        return redirect('merry_go_round:wallet_dashboard')
    
    context = {
        'wallet': wallet,
    }
    
    return render(request, 'merry_go_round/deposit.html', context)


@login_required
def withdraw_from_wallet(request):
    """Withdraw funds from MGR wallet to main wallet"""
    wallet = WalletService.get_or_create_wallet(request.user)
    
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
            
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount')
                return redirect('merry_go_round:wallet_dashboard')
            
            if amount > wallet.available_balance:
                messages.error(
                    request, 
                    f'Insufficient available balance. You have KES {wallet.available_balance:,.2f} available'
                )
                return redirect('merry_go_round:wallet_dashboard')
            
            # Process withdrawal
            reference = MainWalletIntegrationService.transfer_from_mgr_wallet(
                request.user, amount
            )
            
            messages.success(
                request, 
                f'Successfully withdrawn KES {amount:,.2f} to your main wallet'
            )
            
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Withdrawal failed: {str(e)}')
        
        return redirect('merry_go_round:wallet_dashboard')
    
    context = {
        'wallet': wallet,
    }
    
    return render(request, 'merry_go_round/withdraw.html', context)


@login_required
def transaction_detail(request, transaction_id):
    """View transaction details"""
    wallet = WalletService.get_or_create_wallet(request.user)
    transaction = get_object_or_404(
        MGRTransaction, 
        id=transaction_id, 
        wallet=wallet
    )
    
    context = {
        'transaction': transaction,
        'wallet': wallet,
    }
    
    return render(request, 'merry_go_round/transaction_detail.html', context)


@login_required
@require_http_methods(["POST"])
def quick_deposit(request):
    """Quick deposit via AJAX"""
    try:
        amount = Decimal(request.POST.get('amount', 0))
        
        if amount <= 0:
            return JsonResponse({'error': 'Invalid amount'}, status=400)
        
        # Process deposit
        reference = MainWalletIntegrationService.transfer_to_mgr_wallet(
            request.user, amount
        )
        
        # Get updated wallet balance
        wallet = WalletService.get_or_create_wallet(request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Deposited KES {amount:,.2f}',
            'new_balance': str(wallet.balance),
            'available_balance': str(wallet.available_balance),
            'reference': reference
        })
        
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Deposit failed'}, status=500)


@login_required
@require_http_methods(["POST"])
def quick_withdraw(request):
    """Quick withdraw via AJAX"""
    try:
        amount = Decimal(request.POST.get('amount', 0))
        wallet = WalletService.get_or_create_wallet(request.user)
        
        if amount <= 0:
            return JsonResponse({'error': 'Invalid amount'}, status=400)
        
        if amount > wallet.available_balance:
            return JsonResponse({
                'error': f'Insufficient balance. Available: KES {wallet.available_balance:,.2f}'
            }, status=400)
        
        # Process withdrawal
        reference = MainWalletIntegrationService.transfer_from_mgr_wallet(
            request.user, amount
        )
        
        # Get updated wallet balance
        wallet.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'message': f'Withdrawn KES {amount:,.2f}',
            'new_balance': str(wallet.balance),
            'available_balance': str(wallet.available_balance),
            'reference': reference
        })
        
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Withdrawal failed'}, status=500)


@login_required
def wallet_statistics(request):
    """Wallet statistics - FIXED template rendering"""
    wallet = WalletService.get_or_create_wallet(request.user)
    
    # Calculate statistics
    transactions = MGRTransaction.objects.filter(wallet=wallet, status='completed')
    
    stats = {
        'deposits': {
            'count': transactions.filter(transaction_type='deposit').count(),
            'total': transactions.filter(transaction_type='deposit').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        },
        'withdrawals': {
            'count': transactions.filter(transaction_type='withdraw').count(),
            'total': transactions.filter(transaction_type='withdraw').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        },
        'contributions': {
            'count': transactions.filter(transaction_type='contribution').count(),
            'total': transactions.filter(transaction_type='contribution').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        },
        'payouts': {
            'count': transactions.filter(transaction_type='payout').count(),
            'total': transactions.filter(transaction_type='payout').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        },
        'interest': {
            'count': transactions.filter(transaction_type='interest').count(),
            'total': transactions.filter(transaction_type='interest').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        },
    }
    
    # Get monthly transaction summary
    from django.db.models.functions import TruncMonth
    monthly_data = transactions.annotate(
        month=TruncMonth('created_at')
    ).values('month', 'transaction_type').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-month')[:12]
    
    context = {
        'wallet': wallet,
        'stats': stats,
        'monthly_data': monthly_data,
    }
    
    return render(request, 'merry_go_round/wallet_statistics.html', context)


# API endpoint for wallet balance
@login_required
def api_wallet_balance(request):
    """Get current wallet balance as JSON"""
    wallet = WalletService.get_or_create_wallet(request.user)
    
    data = {
        'balance': str(wallet.balance),
        'available_balance': str(wallet.available_balance),
        'locked_balance': str(wallet.locked_balance),
        'total_deposited': str(wallet.total_deposited),
        'total_withdrawn': str(wallet.total_withdrawn),
    }
    
    return JsonResponse(data)


# API endpoint for recent transactions
@login_required
def api_recent_transactions(request):
    """Get recent transactions as JSON"""
    wallet = WalletService.get_or_create_wallet(request.user)
    limit = int(request.GET.get('limit', 10))
    
    transactions = MGRTransaction.objects.filter(
        wallet=wallet,
        status='completed'
    ).order_by('-created_at')[:limit]
    
    data = {
        'transactions': [
            {
                'id': str(txn.id),
                'type': txn.transaction_type,
                'type_display': txn.get_transaction_type_display(),
                'amount': str(txn.amount),
                'balance_after': str(txn.balance_after),
                'description': txn.description,
                'created_at': txn.created_at.isoformat(),
                'status': txn.status,
            }
            for txn in transactions
        ]
    }
    
    return JsonResponse(data)


# Check if user has sufficient balance for round
@login_required
def check_balance_for_round(request, round_id):
    """Check if user has sufficient balance to join a round - UPDATED for just-in-time approach"""
    from .models import Round
    
    round_obj = get_object_or_404(Round, id=round_id)
    wallet = WalletService.get_or_create_wallet(request.user)
    
    # CHANGED: Only check for FIRST contribution, not total commitment
    required_amount = round_obj.contribution_amount  # Just the first one!
    has_sufficient = wallet.has_sufficient_balance(required_amount)
    
    data = {
        'has_sufficient': has_sufficient,
        'required_amount': str(required_amount),
        'available_balance': str(wallet.available_balance),
        'shortfall': str(max(0, required_amount - wallet.available_balance)),
        'message': f'You need KES {required_amount} for your first contribution.' if not has_sufficient else 'You have sufficient balance to join!'
    }
    
    return JsonResponse(data)

@login_required
@require_http_methods(["POST"])
def delete_round(request, round_id):
    """Delete a round that hasn't started (creator only)"""
    round_obj = get_object_or_404(Round, id=round_id)
    
    # Check permissions
    if round_obj.creator != request.user:
        return JsonResponse({'error': 'Only the creator can delete this round'}, status=403)
    
    # Check if round can be deleted
    if round_obj.status not in ['draft', 'open']:
        return JsonResponse({
            'error': 'Cannot delete a round that has already started or been completed'
        }, status=400)
    
    try:
        # Cancel the round (this unlocks all funds)
        RoundService.cancel_round(round_obj)
        
        # Actually delete it
        round_name = round_obj.name
        round_obj.delete()
        
        messages.success(request, f'Round "{round_name}" has been deleted and all locked funds released.')
        return JsonResponse({
            'success': True,
            'message': f'Round "{round_name}" deleted successfully',
            'redirect_url': reverse('merry_go_round:my_rounds')
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
# Add these functions to the existing merry_go_round/views.py file

# ========================================
# WALLET TRANSFER VIEWS (Add to existing views.py)
# ========================================

@login_required
def transfer_from_main_wallet(request):
    """Transfer funds from Main Wallet to MGR Wallet"""
    wallet = WalletService.get_or_create_wallet(request.user)
    
    # Get Main Wallet balance
    try:
        from wallet.services import WalletService as MainWalletService
        main_balance_info = MainWalletService.get_wallet_balance(request.user)
        main_available = main_balance_info['available_balance']
    except:
        main_available = Decimal('0.00')
    
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
            
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount')
                return redirect('merry_go_round:wallet_dashboard')
            
            if amount > main_available:
                messages.error(
                    request,
                    f'Insufficient balance in Main Wallet. Available: KES {main_available:,.2f}'
                )
                return redirect('merry_go_round:wallet_dashboard')
            
            # Process transfer
            txn = WalletService.deposit_from_main_wallet(
                user=request.user,
                amount=amount
            )
            
            messages.success(
                request,
                f'Successfully transferred KES {amount:,.2f} from Main Wallet to MGR Wallet'
            )
            
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Transfer failed: {str(e)}')
        
        return redirect('merry_go_round:wallet_dashboard')
    
    context = {
        'wallet': wallet,
        'main_available': main_available,
    }
    
    return render(request, 'merry_go_round/transfer_from_main.html', context)


@login_required
def transfer_to_main_wallet(request):
    """Transfer funds from MGR Wallet to Main Wallet"""
    wallet = WalletService.get_or_create_wallet(request.user)
    
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
            
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount')
                return redirect('merry_go_round:wallet_dashboard')
            
            if amount > wallet.available_balance:
                messages.error(
                    request,
                    f'Insufficient available balance. You have KES {wallet.available_balance:,.2f} available'
                )
                return redirect('merry_go_round:wallet_dashboard')
            
            # Process transfer
            txn = WalletService.withdraw_to_main_wallet(
                user=request.user,
                amount=amount
            )
            
            messages.success(
                request,
                f'Successfully transferred KES {amount:,.2f} from MGR Wallet to Main Wallet'
            )
            
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Transfer failed: {str(e)}')
        
        return redirect('merry_go_round:wallet_dashboard')
    
    context = {
        'wallet': wallet,
    }
    
    return render(request, 'merry_go_round/transfer_to_main.html', context)


@login_required
@require_http_methods(["POST"])
def quick_transfer_from_main(request):
    """Quick transfer from Main Wallet via AJAX"""
    try:
        amount = Decimal(request.POST.get('amount', 0))
        
        if amount <= 0:
            return JsonResponse({'error': 'Invalid amount'}, status=400)
        
        # Check Main Wallet balance
        try:
            from wallet.services import WalletService as MainWalletService
            main_balance_info = MainWalletService.get_wallet_balance(request.user)
            
            if main_balance_info['available_balance'] < amount:
                return JsonResponse({
                    'error': f'Insufficient balance in Main Wallet. Available: KES {main_balance_info["available_balance"]:,.2f}'
                }, status=400)
        except:
            return JsonResponse({'error': 'Unable to verify Main Wallet balance'}, status=400)
        
        # Process transfer
        txn = WalletService.deposit_from_main_wallet(
            user=request.user,
            amount=amount
        )
        
        # Get updated wallet balance
        wallet = WalletService.get_or_create_wallet(request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Transferred KES {amount:,.2f} from Main Wallet',
            'new_balance': str(wallet.balance),
            'available_balance': str(wallet.available_balance),
            'reference': str(txn.id)
        })
        
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Transfer failed'}, status=500)


@login_required
@require_http_methods(["POST"])
def quick_transfer_to_main(request):
    """Quick transfer to Main Wallet via AJAX"""
    try:
        amount = Decimal(request.POST.get('amount', 0))
        wallet = WalletService.get_or_create_wallet(request.user)
        
        if amount <= 0:
            return JsonResponse({'error': 'Invalid amount'}, status=400)
        
        if amount > wallet.available_balance:
            return JsonResponse({
                'error': f'Insufficient balance. Available: KES {wallet.available_balance:,.2f}'
            }, status=400)
        
        # Process transfer
        txn = WalletService.withdraw_to_main_wallet(
            user=request.user,
            amount=amount
        )
        
        # Get updated wallet balance
        wallet.refresh_from_db()
        
        return JsonResponse({
            'success': True,
            'message': f'Transferred KES {amount:,.2f} to Main Wallet',
            'new_balance': str(wallet.balance),
            'available_balance': str(wallet.available_balance),
            'reference': str(txn.id)
        })
        
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Transfer failed'}, status=500)    