import datetime
from dateutil.relativedelta import relativedelta
import json
from decimal import Decimal
from decimal import InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from notifications.models import UserFcmTokens
from decimal import Decimal, ROUND_HALF_UP
import traceback
from notifications.utils import *
from authentication.models import Profile
from notifications.models import UserNotificationHistory
from django.contrib.sites.shortcuts import get_current_site
from pyment_withdraw.models import UserMoneyWithDrawalStatus, UserBankDetails
from django.db.models import Sum, Q, Count
from .models import (
    ExpressSaving, Goal, Deposit, GroupGoal, GroupGoalMember,
    GroupGoalActivites, GroupGoalMember_contribution,
    Goal_Wallet, Interest_Rate, tax_Rate
)
from django.template.loader import get_template
from io import BytesIO
import xhtml2pdf.pisa as pisa
import logging
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# NEW: Use ONLY MainWallet and GoalsIntegrationService
from wallet.services import GoalsIntegrationService
from wallet.models import MainWallet

logger = logging.getLogger(__name__)


def calculate_future_value_express(obj):
    """Calculate interest only for deposits that are still active"""
    total_amount = Decimal('0')
    now = timezone.now()
    for self in obj:
        #Only calculate for deposits that haven't been withdrawn
        if self.transaction_type == 'deposit' and self.is_withdraw == 'No':
            interest_value = Interest_Rate.objects.get(pk=1)
            delta = relativedelta(now, self.created_at)
            days_difference = delta.years * 365 + delta.months * 30 + delta.days
            daily_interest_rate = Decimal(interest_value.regular_deposit) / 365
            future_value = self.amount * (1 + daily_interest_rate) ** Decimal(days_difference)
            total_amount += Decimal(future_value) - Decimal(self.amount)
    return round(total_amount, 2)


def calculate_future_goals(obj, goal_info):
    interest_value = Interest_Rate.objects.get(pk=1)
    interest_rate = Decimal(0.0)
    if goal_info.saving_type == 'fixed':
        interest_rate = interest_value.fixed_deposit
    elif goal_info.saving_type == 'regular':
        interest_rate = interest_value.regular_deposit

    total_amount = Decimal('0')
    now = timezone.now()
    for self in obj:
        if self.is_withdraw == 'No':
            delta = relativedelta(now, self.deposit_date)
            days_difference = delta.years * 365 + delta.months * 30 + delta.days
            daily_interest_rate = Decimal(interest_rate) / 365
            future_value = self.amount * (1 + Decimal(daily_interest_rate)) ** Decimal(days_difference)
            total_amount += Decimal(future_value) - self.amount
    return round(total_amount, 2)


def calculate_future_group_goals(obj):
    total_amount = Decimal('0')
    now = timezone.now()
    for self in obj:
        if self.is_withdraw == 'No':
            interest_value = Interest_Rate.objects.get(pk=1)
            delta = relativedelta(now, self.created_at)
            days_difference = delta.years * 365 + delta.months * 30 + delta.days
            daily_interest_rate = Decimal(interest_value.fixed_deposit) / 365
            future_value = self.amount * (1 + daily_interest_rate) ** Decimal(days_difference)
            total_amount += Decimal(future_value) - self.amount
    return round(total_amount, 2)


def calculate_analytics_data(user):
    """
    Calculate comprehensive analytics for the user's goals
    """
    analytics = {
        'total_saved': Decimal('0.00'),
        'total_interest_earned': Decimal('0.00'),
        'average_monthly_savings': Decimal('0.00'),
        'goal_completion_rate': 0,
        'savings_streak': 0,
        'total_goals': 0,
        'completed_goals': 0,
        'active_goals': 0,
        'total_personal_goals': 0,
        'total_group_goals': 0,
        'active_personal_goals': 0,
        'active_group_goals': 0,
        'completed_personal_goals': 0,
        'completed_group_goals': 0,
    }
    
    # Get all user's personal goals
    all_personal_goals = Goal.objects.filter(user=user)
    
    # Get all group goals (creator or member)
    all_group_goals = GroupGoal.objects.filter(
        Q(creator=user) | Q(groupgoalmember__user=user)
    ).distinct()
    
    # Calculate personal goals statistics
    analytics['total_personal_goals'] = all_personal_goals.count()
    analytics['active_personal_goals'] = all_personal_goals.filter(is_active='Yes').count()
    analytics['completed_personal_goals'] = all_personal_goals.filter(is_active='No').count()
    
    # Calculate group goals statistics
    analytics['total_group_goals'] = all_group_goals.count()
    analytics['active_group_goals'] = all_group_goals.filter(is_active='Yes').count()
    analytics['completed_group_goals'] = all_group_goals.filter(is_active='No').count()
    
    # Calculate total goals across both types
    analytics['total_goals'] = analytics['total_personal_goals'] + analytics['total_group_goals']
    analytics['active_goals'] = analytics['active_personal_goals'] + analytics['active_group_goals']
    analytics['completed_goals'] = analytics['completed_personal_goals'] + analytics['completed_group_goals']
    
    # Calculate total saved across all goals
    # Personal Goals
    personal_saved = sum(
        goal.goal_balance for goal in all_personal_goals if goal.is_active == 'Yes'
    )
    personal_interest = sum(
        goal.goal_profit for goal in all_personal_goals if goal.is_active == 'Yes'
    )
    
    # Express Saving
    wallet = Goal_Wallet.objects.filter(user=user).first()
    if wallet:
        express_saved = wallet.saving_balance
        express_interest = wallet.saving_profit
    else:
        express_saved = Decimal('0.00')
        express_interest = Decimal('0.00')
    
    # Group Goals (user's contributions)
    group_contributions = GroupGoalMember_contribution.objects.filter(
        user=user, 
        is_withdraw='No'
    )
    group_saved = sum(contrib.amount for contrib in group_contributions)
    group_interest = sum(
        contrib.calculate_future_value_group_goal() for contrib in group_contributions
    )
    
    # Total calculations
    analytics['total_saved'] = personal_saved + express_saved + group_saved
    analytics['total_interest_earned'] = personal_interest + express_interest + group_interest
    
    # Goal completion rate
    if analytics['total_goals'] > 0:
        analytics['goal_completion_rate'] = int(
            (analytics['completed_goals'] / analytics['total_goals']) * 100
        )
    
    # Average monthly savings calculation
    twelve_months_ago = timezone.now() - relativedelta(months=12)
    
    personal_deposits = Deposit.objects.filter(
        goal__user=user,
        deposit_date__gte=twelve_months_ago
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    express_deposits = ExpressSaving.objects.filter(
        user=user,
        created_at__gte=twelve_months_ago
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    group_deposits = GroupGoalMember_contribution.objects.filter(
        user=user,
        created_at__gte=twelve_months_ago
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    total_deposits = personal_deposits + express_deposits + group_deposits
    
    # Calculate months with activity
    months_active = set()
    
    for deposit in Deposit.objects.filter(goal__user=user, deposit_date__gte=twelve_months_ago):
        months_active.add((deposit.deposit_date.year, deposit.deposit_date.month))
    
    for saving in ExpressSaving.objects.filter(user=user, created_at__gte=twelve_months_ago):
        months_active.add((saving.created_at.year, saving.created_at.month))
    
    for contrib in GroupGoalMember_contribution.objects.filter(user=user, created_at__gte=twelve_months_ago):
        months_active.add((contrib.created_at.year, contrib.created_at.month))
    
    if len(months_active) > 0:
        analytics['average_monthly_savings'] = total_deposits / len(months_active)
    
    # Calculate savings streak (consecutive months with deposits)
    current_date = timezone.now().date()
    streak = 0
    checking_date = current_date.replace(day=1)
    
    while True:
        month_start = checking_date
        month_end = (checking_date + relativedelta(months=1)) - relativedelta(days=1)
        
        # Check if there were any deposits this month
        has_personal = Deposit.objects.filter(
            goal__user=user,
            deposit_date__date__gte=month_start,
            deposit_date__date__lte=month_end
        ).exists()
        
        has_express = ExpressSaving.objects.filter(
            user=user,
            created_at__date__gte=month_start,
            created_at__date__lte=month_end
        ).exists()
        
        has_group = GroupGoalMember_contribution.objects.filter(
            user=user,
            created_at__date__gte=month_start,
            created_at__date__lte=month_end
        ).exists()
        
        if has_personal or has_express or has_group:
            streak += 1
            checking_date = checking_date - relativedelta(months=1)
        else:
            break
        
        # Stop after checking 24 months to prevent infinite loops
        if streak >= 24:
            break
    
    analytics['savings_streak'] = streak
    
    return analytics

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None


@login_required(login_url='Login')
def my_goals(request):
    """
    Dashboard view showing all user's goals with up-to-date interest calculations.
    
    This view recalculates interest earned on all deposits each time it loads,
    ensuring users see current values including accumulated interest.
    """
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    all_express_savings = ExpressSaving.objects.filter(user=request.user).order_by('-created_at')
    all_goals = Goal.objects.filter(user=request.user).order_by('-created_at')
    
    # ========================================
    # PERSONAL GOALS: Recalculate interest earned
    # ========================================
    for goal in all_goals:
        if goal.is_active == 'Yes':
            # Get all deposits that haven't been withdrawn
            all_deposits = Deposit.objects.filter(goal=goal, is_withdraw='No')
            
            # Calculate total interest earned on all deposits
            # This uses compound interest based on:
            # - Regular goals: 6% per annum
            # - Fixed goals: 10% per annum
            interest_earned = calculate_future_goals(all_deposits, goal)
            
            # Update the goal's interest amount
            goal.goal_profit = interest_earned
            goal.save(skip_validation=True)
    
    # Separate completed and in-progress goals
    complete_goals = []
    progressing_goals = []
    for item in all_goals:
        if item.is_active == 'No':
            complete_goals.append(item)
        else:
            progressing_goals.append(item)
    
    # ========================================
    # GROUP GOALS: Recalculate interest earned
    # ========================================
    all_group_goal = GroupGoal.objects.filter(
        Q(creator=request.user) | Q(groupgoalmember__user=request.user)
    ).distinct().order_by('-created_at')
    
    for group_goal in all_group_goal:
        if group_goal.is_active == 'Yes':
            # Get all contributions that haven't been withdrawn
            all_contributions = GroupGoalMember_contribution.objects.filter(
                group_goal=group_goal, 
                is_withdraw='No'
            )
            
            # Calculate total interest earned on all contributions
            # Group goals use fixed deposit rate (10% per annum)
            interest_earned = calculate_future_group_goals(all_contributions)
            
            # Calculate total contributions (principal)
            total_contributions = sum(Decimal(contrib.amount) for contrib in all_contributions)
            
            # Update the group goal's interest and achieved amount
            group_goal.profit = interest_earned
            group_goal.achieved_amount = total_contributions + interest_earned
            group_goal.save(skip_validation=True)
    
    # Separate completed and in-progress group goals
    group_complete_goals = []
    group_progressing_goals = []
    for item in all_group_goal:
        if item.is_active == 'No':
            if item not in group_complete_goals:
                group_complete_goals.append(item)
        else:
            if item not in group_progressing_goals:
                group_progressing_goals.append(item)

    # ========================================
    # EXPRESS SAVING: Recalculate interest earned
    # ========================================
    my_wallet, created = Goal_Wallet.objects.get_or_create(user=request.user)
    
    # Calculate total interest earned on all express savings
    all_active_express_savings = ExpressSaving.objects.filter(
        user=request.user, 
        is_withdraw='No'
    )
    express_interest_earned = calculate_future_value_express(all_active_express_savings)
    
    # Update wallet with current interest
    my_wallet.saving_profit = express_interest_earned
    my_wallet.goal_balance = my_wallet.saving_balance + my_wallet.saving_profit
    my_wallet.save()
    
    # ========================================
    # ADDITIONAL DATA
    # ========================================
    total_complete = len(group_complete_goals) + len(complete_goals)
    main_wallet = MainWallet.objects.get(user=request.user)
    
    # Calculate comprehensive analytics
    analytics = calculate_analytics_data(request.user)

    context = {
        'user_profile': user_profile,
        'user_notifications': user_notifications,
        'all_express_savings': all_express_savings,
        'all_group_goal': all_group_goal,
        'main_wallet': main_wallet,
        'my_wallet': my_wallet,
        'complete_goals': complete_goals,
        'progressing_goals': progressing_goals,
        'group_complete_goals': group_complete_goals,
        'group_progressing_goals': group_progressing_goals,
        'interest_rate': Interest_Rate.objects.get(pk=1),
        'total_complete': total_complete,
        'analytics': analytics,
    }
    return render(request, 'Goals/wekeza_dashboard.html', context)

@login_required(login_url='Login')
def goals_dashboard(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    all_express_savings = ExpressSaving.objects.filter(user=request.user).order_by('-created_at')
    all_goals_active = Goal.objects.filter(user=request.user).order_by('-created_at')
    complete_goals = []
    progressing_goals = []
    for item in all_goals_active:
        goal_percentage = item.percentage()
        if goal_percentage == 100:
            complete_goals.append(item)
        else:
            progressing_goals.append(item)
    all_group_goal = GroupGoal.objects.filter(creator=request.user).order_by('-created_at')
    context = {
        'user_profile': user_profile,
        'user_notifications': user_notifications,
        'all_express_savings': all_express_savings,
        'complete_goals': complete_goals,
        'progressing_goals': progressing_goals,
        'all_group_goal': all_group_goal
    }
    return render(request, 'Goals/wekeza_dashboard.html', context)



def exit_group_goal(request):
    if request.method == 'POST':
        goal_group_id = request.POST.get('goal_group_id')
        user_profile = Profile.objects.get(owner=request.user)
        x = GroupGoal.objects.get(pk=goal_group_id)
        y = GroupGoalMember.objects.get(user=request.user, group_goal=x)
        y.delete()
        send_sms(user_profile.phone, 'Group Exit', 'Successfully exit your  goal ' + x.goal_name)
        search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
        send_notif(search_str, None, True, True, "Group Exit", 'Successfully exit goal ' + x.goal_name, None, False, request.user)
        messages.success(request, 'Group exit successfully.')
        return redirect('user_dashboard:home')


def delete_group_goal(request):
    if request.method == 'POST':
        goal_group_id = request.POST.get('goal_id')
        x = GroupGoal.objects.get(pk=goal_group_id)
        x.delete()
        return JsonResponse({'success': '1'})


@login_required(login_url='Login')
def express_saving_dashboard(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    all_express_savings = ExpressSaving.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(all_express_savings, 10)  # 10 transactions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    result = calculate_future_value_express(all_express_savings)
    my_wallet, created = Goal_Wallet.objects.get_or_create(user=request.user)
    my_wallet.saving_profit = result
    my_wallet.save()
    my_wallet.goal_balance = my_wallet.saving_balance + my_wallet.saving_profit
    my_wallet.save()
    tax_rate_amount = tax_Rate.objects.get(pk=1)
    Fv_after_tax = (Decimal(my_wallet.saving_balance) + Decimal(my_wallet.saving_profit)) - (
                Decimal(my_wallet.saving_profit) * tax_rate_amount.tax_rate_value)
    
    # ✅ GET EXPRESS SAVING RATE (uses regular_deposit rate)
    intrest_rate = Interest_Rate.objects.get(pk=1)
    express_rate = intrest_rate.regular_deposit * 100  # Express saving uses regular rate
    
    context = {
        'user_profile': user_profile,
        'user_notifications': user_notifications,
        'all_express_savings': all_express_savings,
        'my_wallet': my_wallet,
        'Fv_after_tax': Fv_after_tax,
        'page_obj': page_obj,
        'intrest_value': express_rate  # ✅ Already passed, just documenting
    }
    return render(request, 'new/express_saving_dashboard.html', context)


@login_required(login_url='Login')
def express_saving(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    main_wallet = MainWallet.objects.get(user=request.user)

    if request.method == 'POST':
        amount = Decimal(request.POST['amount'])
        try:
            GoalsIntegrationService.transfer_to_goals(
                user=request.user,
                amount=amount,
                goal_type='express_saving',
                goal_id=None
            )
        except Exception as e:
            logger.warning(f"Express saving deposit failed: {str(e)}")
            return JsonResponse({'success': '2'})

        # Create deposit with explicit transaction_type
        express_saving = ExpressSaving.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='deposit',  #Explicit type
            is_withdraw='No'  # Active deposit earning interest
        )
        
        wallet, _ = Goal_Wallet.objects.get_or_create(user=request.user)
        wallet.saving_balance += amount
        wallet.save()

        try:
            send_sms(user_profile.phone, 'Important Alert',
                     'Successfully deposit ' + str(amount) + 'Ksh to express saving.')
            search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
            send_notif(search_str, None, True, True, "Congratulation",
                       'Successfully deposit ' + str(amount) + ' Ksh to express saving.',
                       None, False, request.user)
        except Exception as e:
            logger.error(f"Notification failed: {e}")

        logger.info(f"Express saving: {amount} by {request.user.username}")
        return JsonResponse({'success': '1'})

    context = {
        'user_profile': user_profile,
        'user_notifications': user_notifications,
    }
    return render(request, 'express_saving.html', context)


@login_required(login_url='Login')
def express_saving_summary(request, express_saving_id):
    express_saving = ExpressSaving.objects.get(pk=express_saving_id)
    interest_rate = 0.06  # Change this to the desired interest rate

    future_value = calculate_future_value([express_saving], interest_rate,
                                          12)  # Assuming the express saving is for 12 months

    return render(request, 'express_saving_summary.html',
                  {'express_saving': express_saving, 'future_value': future_value})



# Key sections to update in views.py

@login_required(login_url='Login')
def create_personal_goals(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    
    # ✅ GET CURRENT INTEREST RATES
    interest_rates = Interest_Rate.objects.get(pk=1)
    regular_rate = interest_rates.percent_regular_deposit()  # Returns percentage (e.g., 6.0)
    fixed_rate = interest_rates.percent_fixed_deposit()      # Returns percentage (e.g., 10.0)
    
    if request.method == 'POST':
        saving_type_added = request.POST.get('saving_type_input', 'regular')
        goal_title = request.POST.get('goal_title')
        is_saving_or_goal = request.POST.get('is_saving_or_goal')
        just_want_to_save = request.POST.get('just_want_to_save')
        reminder_frequency = request.POST.get('reminder_frequency')
        select_payment_frequency = request.POST.get('select_payment_frequency')
        
        # Get and clean date inputs
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        
        # CRITICAL FIX: Validate fixed goals BEFORE creating the object
        if saving_type_added == 'fixed':
            if not end_date:
                return JsonResponse({
                    'success': '0', 
                    'error': 'Fixed saving goals must have an end date.'
                })
            
            # Additional validation: end_date must be after start_date
            if start_date and end_date:
                from datetime import datetime
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                if end_dt <= start_dt:
                    return JsonResponse({
                        'success': '0',
                        'error': 'End date must be after the start date.'
                    })
        
        # For regular goals with "just want to save" checked, end_date should be None
        if saving_type_added == 'regular' and just_want_to_save == 'on':
            end_date = None
        
        # Create the goal
        goal = Goal.objects.create(
            user=request.user,
            name=goal_title,
            saving_type=saving_type_added,
            reminder_frequency=reminder_frequency,
            payment_frequency=select_payment_frequency,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
        )
        
        # Set amounts
        is_saving_or_goal = request.POST.get('is_saving_or_goal')

        if is_saving_or_goal == 'on':
            goal.goal_amount = None
            try:
                amount_to_save_str = request.POST.get('amount_to_save', '').strip()
                if amount_to_save_str:
                    goal.amount_to_save_per_notification = Decimal(amount_to_save_str)
                else:
                    goal.amount_to_save_per_notification = None
            except (ValueError, InvalidOperation):
                goal.amount_to_save_per_notification = None
        else:
            try:
                target_amount_str = request.POST.get('target_amount', '').strip()
                if target_amount_str and target_amount_str != '0' and target_amount_str != '0.00':
                    goal.goal_amount = Decimal(target_amount_str)
                else:
                    goal.goal_amount = None
                
                amount_to_save_str = request.POST.get('amount_to_save', '').strip()
                if amount_to_save_str:
                    goal.amount_to_save_per_notification = Decimal(amount_to_save_str)
                else:
                    goal.amount_to_save_per_notification = None
            except (ValueError, InvalidOperation) as e:
                logger.error(f"Error converting target_amount: {e}")
                goal.goal_amount = None
                goal.amount_to_save_per_notification = None

        # Set notification date based on frequency
        if reminder_frequency == 'monthly':
            goal.notification_date = timezone.now().date() + relativedelta(months=1)
        elif reminder_frequency == 'weekly':
            goal.notification_date = timezone.now().date() + relativedelta(weeks=1)
        elif reminder_frequency == 'daily':
            goal.notification_date = timezone.now().date() + relativedelta(days=1)

        try:
            goal.save()
        except ValidationError as e:
            logger.error(f"Goal validation error: {e}")
            return JsonResponse({'success': '0', 'error': str(e)})

        # Send notifications
        try:
            send_sms(user_profile.phone, 'Congratulations', 'You have successfully started your new goal ' + goal_title)
            search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
            send_notif(search_str, None, True, True, "Congratulation",
                       'You have successfully started your new goal ' + goal_title,
                       None, False, request.user)
        except Exception as e:
            logger.error(f"Notification failed in create_personal_goals: {e}")

        return JsonResponse({'success': '1', 'goal_id': goal.id})

    context = {
        'user_profile': user_profile, 
        'user_notifications': user_notifications,
        'regular_rate': regular_rate,  # ✅ Pass to template
        'fixed_rate': fixed_rate       # ✅ Pass to template
    }
    return render(request, 'creat_personal_goals.html', context)


@login_required(login_url='Login')
def goal_details(request, id):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    goal_info = Goal.objects.get(pk=id)
    all_deposits = Deposit.objects.filter(goal=goal_info).order_by('-deposit_date')
    
    if goal_info.is_active == 'Yes':
        if goal_info.end_date and timezone.now().date() > goal_info.end_date:
            pass
        else:
            result = calculate_future_goals(all_deposits, goal_info)
            goal_info.goal_profit = result
            goal_info.save(skip_validation=True)

    tax_rate_amount = tax_Rate.objects.get(pk=1)
    Fv_after_tax = (Decimal(goal_info.goal_balance) + Decimal(goal_info.goal_profit)) - (
                Decimal(goal_info.goal_profit) * tax_rate_amount.tax_rate_value)

    # UPDATED: Use the model's can_withdraw method
    can_withdraw = 'Yes' if goal_info.can_withdraw() else 'No'

    # ============ Milestone Detection ============
    show_50_milestone = False
    show_75_milestone = False
    
    # Check for 50% milestone
    if goal_info.percentage() >= 49 and goal_info.percentage() <= 51:
        if not goal_info.milestone_50_shown:
            show_50_milestone = True
            goal_info.milestone_50_shown = True
            goal_info.save(skip_validation=True)
    
    # Check for 75% milestone
    if goal_info.percentage() >= 74 and goal_info.percentage() <= 76:
        if not goal_info.milestone_75_shown:
            show_75_milestone = True
            goal_info.milestone_75_shown = True
            goal_info.save(skip_validation=True)
    
    # Add withdrawal reason message for display
    withdrawal_message = ""
    if can_withdraw == 'No':
        if goal_info.saving_type == 'fixed':
            if goal_info.end_date:
                days_remaining = (goal_info.end_date - timezone.now().date()).days
                if goal_info.goal_amount and goal_info.goal_balance < goal_info.goal_amount:
                    amount_remaining = goal_info.goal_amount - goal_info.goal_balance
                    withdrawal_message = f"Fixed goal: Cannot withdraw until end date ({days_remaining} days remaining) OR goal amount is reached (KES {amount_remaining} remaining)."
                else:
                    withdrawal_message = f"Fixed goal: Cannot withdraw until end date ({days_remaining} days remaining)."

    interest_value = Interest_Rate.objects.get(pk=1)
    if goal_info.saving_type == 'fixed':
        interest_value = interest_value.fixed_deposit * 100
    else:
        interest_value = interest_value.regular_deposit * 100

    context = {
        'user_profile': user_profile,
        'user_notifications': user_notifications,
        'goal_info': goal_info,
        'all_deposits': all_deposits,
        'can_withdraw': can_withdraw,
        'withdrawal_message': withdrawal_message,
        'Fv_after_tax': Fv_after_tax,
        'interest_rate': interest_value,
        'show_50_milestone': show_50_milestone,  # NEW LINE
        'show_75_milestone': show_75_milestone,  # NEW LINE
    }

    return render(request, 'new/goal_details.html', context)


@login_required(login_url='Login')
def add_funds_to_goal(request, id):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    goal_info = Goal.objects.get(pk=id)

    if request.method == 'POST':
        amount = Decimal(request.POST['add_money'])
        try:
            GoalsIntegrationService.transfer_to_goals(
                user=request.user,
                amount=amount,
                goal_type='personal_goal',
                goal_id=goal_info.id
            )
        except Exception as e:
            logger.warning(f"Personal goal deposit failed: {str(e)}")
            return JsonResponse({'success': '2'})

        Deposit.objects.create(goal=goal_info, amount=amount)
        goal_info.goal_balance += amount
        goal_info.save(skip_validation=True)

        #Check if goal is now achieved after this deposit
        is_goal_achieved = False
        if goal_info.goal_amount and goal_info.goal_balance >= goal_info.goal_amount:
            is_goal_achieved = True
            achievement_message = (
                f" Congratulations! You've achieved your goal '{goal_info.name}'! "
                f"You've saved KES {goal_info.goal_balance} and reached your target of KES {goal_info.goal_amount}. "
                f"You can now withdraw your funds anytime."
            )
            
            try:
                send_sms(user_profile.phone, 'Goal Achieved!', achievement_message)
                search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Goal Achieved! 🎉", achievement_message, None, False, request.user)
            except Exception as e:
                logger.error(f"Achievement notification failed: {e}")

        # Send regular deposit notification (only if goal not achieved, to avoid double notifications)
        if not is_goal_achieved:
            try:
                send_sms(user_profile.phone, 'Congratulations',
                         'You have successfully deposited ' + str(amount) + 'Ksh to your ' + goal_info.name)
                search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Congratulation",
                           'Successfully deposit ' + str(amount) + 'Ksh to your ' + goal_info.name,
                           None, False, request.user)
            except Exception as e:
                logger.error(f"Notification failed: {e}")

        logger.info(f"Personal goal deposit: {amount} for goal {goal_info.id}")
        return JsonResponse({'success': '1'})

    context = {
        'user_profile': user_profile,
        'user_notifications': user_notifications,
        'goal_info': goal_info,
    }
    return render(request, 'add_funds_to_goal.html', context)


@login_required(login_url='Login')
def create_group_goal(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    
    # ✅ GET CURRENT INTEREST RATES
    interest_rates = Interest_Rate.objects.get(pk=1)
    regular_rate = interest_rates.percent_regular_deposit()
    fixed_rate = interest_rates.percent_fixed_deposit()
    
    if request.method == 'POST':
        saving_type_added = request.POST.get('saving_type_input')
        goal_title = request.POST.get('goal_name')
        goal_mission = request.POST.get('goal_mission')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        target_amount = Decimal(request.POST['target_amount'])
        goal = GroupGoal.objects.create(
            creator=request.user,
            goal_name=goal_title,
            goal_description=goal_mission,
            saving_type=saving_type_added,
            start_date=start_date,
            end_date=end_date,
            target_amount=target_amount
        )
        GroupGoalMember.objects.create(user=request.user, group_goal=goal)
        domain = get_current_site(request).domain
        ref_url = 'https://' + domain + '/goals/add_members/' + str(goal.id)
        goal.shareable_link = ref_url
        goal.save()
        return JsonResponse({'success': '1', 'goal_id': goal.id})

    context = {
        'user_profile': user_profile, 
        'user_notifications': user_notifications,
        'regular_rate': regular_rate,  # ✅ Pass to template
        'fixed_rate': fixed_rate       # ✅ Pass to template
    }
    return render(request, 'create_group_goal.html', context)


# Add this to your views.py in the group_goal_details function
# Replace the existing group_goal_details function with this updated version

@login_required(login_url='Login')
def group_goal_details(request, id):
    if not GroupGoalMember.objects.filter(user=request.user, group_goal_id=id).exists():
        return redirect('user_dashboard:home')

    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    goal_info = GroupGoal.objects.get(pk=id)
    all_deposits = GroupGoalMember_contribution.objects.filter(group_goal=goal_info).order_by('-created_at')
    
    # ✅ FIX 1: Get user contributions with proper profile picture handling
    user_total_contributions = all_deposits.values(
        'user__id',
        'user__first_name', 
        'user__last_name', 
        'user__profile__phone',
        'user__username'
    ).annotate(total_amount=Sum('amount')).order_by('user')
    
    # ✅ Add profile objects to each contribution entry
    for contrib in user_total_contributions:
        try:
            user_obj = User.objects.get(id=contrib['user__id'])
            contrib['profile'] = Profile.objects.get(owner=user_obj)
        except (User.DoesNotExist, Profile.DoesNotExist):
            contrib['profile'] = None

    # ✅ FIX 2: Calculate PRINCIPAL (total contributions without interest)
    total_principal = sum(float(d.amount) for d in all_deposits if d.is_withdraw == 'No')
    
    # Calculate interest earned
    if goal_info.is_active == 'Yes' and goal_info.end_date and goal_info.end_date > timezone.now().date():
        interest_earned = calculate_future_group_goals(all_deposits)
        goal_info.profit = interest_earned
    else:
        interest_earned = goal_info.profit
    
    # ✅ Update achieved_amount to be ONLY principal
    goal_info.achieved_amount = Decimal(total_principal)
    goal_info.save(skip_validation=True)
    
    # ✅ Calculate "Available for Withdrawal" (principal + interest after tax)
    tax_rate_amount = tax_Rate.objects.get(pk=1)
    tax_on_interest = Decimal(interest_earned) * tax_rate_amount.tax_rate_value
    available_for_withdrawal = Decimal(total_principal) + Decimal(interest_earned) - tax_on_interest

    interest_value = Interest_Rate.objects.get(pk=1)
    if goal_info.saving_type == 'fixed':
        interest_value = interest_value.fixed_deposit * 100
    else:
        interest_value = interest_value.regular_deposit * 100

    # ============  Milestone Detection for Group Goals ============
    show_50_milestone = False
    show_75_milestone = False
    
    # Check for 50% milestone
    if goal_info.percentage() >= 49 and goal_info.percentage() <= 51:
        if not goal_info.milestone_50_shown:
            show_50_milestone = True
            goal_info.milestone_50_shown = True
            goal_info.save(skip_validation=True)
    
    # Check for 75% milestone
    if goal_info.percentage() >= 74 and goal_info.percentage() <= 76:
        if not goal_info.milestone_75_shown:
            show_75_milestone = True
            goal_info.milestone_75_shown = True
            goal_info.save(skip_validation=True)
    

    context = {
        'user_profile': user_profile,
        'user_notifications': user_notifications,
        'goal_info': goal_info,
        'all_members': all_deposits,
        'group_activites': GroupGoalActivites.objects.filter(group_goal=goal_info).order_by('-created_at'),
        'user_total_contributions': user_total_contributions,
        'total_principal': total_principal,
        'available_for_withdrawal': available_for_withdrawal,
        'interest_earned': interest_earned,
        'interest_value': interest_value,
        'show_50_milestone': show_50_milestone,  #  NEW LINE to show milestones
        'show_75_milestone': show_75_milestone,  #  NEW LINE to show milestones
        'today': timezone.now().date(),
    }
    return render(request, 'new/group_goal_details.html', context)


@login_required(login_url='Login')
def add_members(request, details):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    goal_info = GroupGoal.objects.get(pk=details)

    if request.method == 'POST':
        if not GroupGoalMember.objects.filter(user=request.user, group_goal=goal_info).exists():
            content = f"{request.user.first_name} {request.user.last_name} joined this goal"
            GroupGoalMember.objects.create(user=request.user, group_goal=goal_info)
            GroupGoalActivites.objects.create(user=request.user, group_goal=goal_info, content=content)
            try:
                send_sms(user_profile.phone, 'Important Alert', 'Successfully joined ' + goal_info.goal_name)
                search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Congratulation",
                           'Successfully joined ' + goal_info.goal_name, None, False, request.user)
            except Exception as e:
                logger.error(f"Notification failed in add_members: {e}")
            return redirect('goals:group_goal_details', goal_info.id)
        else:
            messages.error(request, 'You are already in the group')
            return redirect('goals:group_goal_details', goal_info.id)

    all_members = GroupGoalMember.objects.filter(group_goal=goal_info)
    context = {
        'user_profile': user_profile,
        'user_notifications': user_notifications,
        'goal_info': goal_info,
        'all_members': all_members,
        'members_count': len(all_members)
    }
    return render(request, 'add_members_to_group_goal.html', context)


@login_required(login_url='Login')
def add_funds_to_group_goal(request):
    if request.method == 'POST':
        goal_id = int(request.POST['goal_id'])
        amount = Decimal(request.POST['amount'])
        user_profile = Profile.objects.get(owner=request.user)
        goal_info = GroupGoal.objects.get(pk=goal_id)

        try:
            GoalsIntegrationService.transfer_to_goals(
                user=request.user,
                amount=amount,
                goal_type='group_goal',
                goal_id=goal_info.id
            )
        except Exception as e:
            logger.warning(f"Group goal deposit failed: {str(e)}")
            return JsonResponse({'success': '2'})

        GroupGoalMember_contribution.objects.create(
            group_goal=goal_info,
            amount=amount,
            user=request.user
        )
        GroupGoalActivites.objects.create(
            user=request.user,
            group_goal=goal_info,
            content=f"{request.user.first_name} {request.user.last_name} made a deposit of Kshs: {amount} to the group goal."
        )
        goal_info.achieved_amount += amount
        goal_info.save(skip_validation=True)

        # Check if group goal is now achieved
        is_goal_achieved = False
        if goal_info.achieved_amount >= goal_info.target_amount:
            is_goal_achieved = True
            achievement_message = (
                f"Group Goal Achieved! '{goal_info.goal_name}' has reached its target of KES {goal_info.target_amount}! "
                f"Total saved: KES {goal_info.achieved_amount}. Great work team!"
            )
            
            # Notify all group members
            all_members = GroupGoalMember.objects.filter(group_goal=goal_info)
            for member in all_members:
                try:
                    member_profile = Profile.objects.get(owner=member.user)
                    send_sms(member_profile.phone, 'Group Goal Achieved!', achievement_message)
                    search_str = UserFcmTokens.objects.filter(user=member.user).order_by('-token')[:1]
                    send_notif(search_str, None, True, True, "Group Goal Achieved! 🎉", achievement_message, None, False, member.user)
                except Exception as e:
                    logger.error(f"Member notification failed: {e}")

        # Send regular deposit notification (only if not achieved)
        if not is_goal_achieved:
            try:
                send_sms(user_profile.phone, 'Important Alert',
                         f"Successfully deposit {amount}Ksh to your {goal_info.goal_name}")
                search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Congratulation",
                           f"Successfully deposit {amount} Ksh to your {goal_info.goal_name}",
                           None, False, request.user)
            except Exception as e:
                logger.error(f"Notification failed: {e}")

        logger.info(f"Group goal deposit: {amount} for goal {goal_info.id}")
        return JsonResponse({'success': '1'})

    return JsonResponse({'success': '0'})


#def add_account(request):
    if request.method == "POST":
        iban = request.POST.get('iban')
        bank_name = request.POST.get('routing')
        swift_code = request.POST.get('swiftcode')
        branch_id = request.POST.get('branchID')
        account_no = request.POST.get('accountNO')
        bank_country = request.POST.get('bank_country', None)
        user = request.user
        UserBankDetails.objects.create(
            iban=iban,
            bank_name=bank_name,
            swift_code=swift_code,
            branch_id=branch_id,
            account_no=account_no,
            bank_country=bank_country,
            user_id=user
        )
        messages.success(request, 'Account saved successfully.')
        return redirect('express_saving_dashboard')
    else:
        return render(request, 'new/add_bank_details.html')



@login_required(login_url='Login')
def withdraw_money_express_saving(request):
    """
    Withdraw all funds from Express Saving to Main Wallet
     Creates a NEW withdrawal transaction with explicit type
     Marks deposits as 'withdrawn' WITHOUT changing their type
    """
    if request.method == 'POST':
        user = request.user
        user_profile = Profile.objects.get(owner=user)
        
        try:
            # Get wallet and calculate total with interest
            x = Goal_Wallet.objects.get(user=user)
            tax_rate_amount = tax_Rate.objects.get(pk=1)
            
            # Calculate amount after tax
            Fv_after_tax = (Decimal(x.saving_balance) + Decimal(x.saving_profit)) - (
                Decimal(x.saving_profit) * tax_rate_amount.tax_rate_value
            )
            
            # Round to 2 decimal places
            Fv_after_tax = Fv_after_tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            if Fv_after_tax <= 0:
                return JsonResponse({
                    'success': '0',
                    'message': 'No funds available for withdrawal'
                })
            
            #  Create a NEW withdrawal transaction record with explicit type
            ExpressSaving.objects.create(
                user=user,
                amount=Fv_after_tax,
                transaction_type='withdrawal',  # Explicit type
                is_withdraw='Yes',  # Mark as withdrawn (for consistency)
                created_at=timezone.now(),
                evaluation_date=timezone.now().date()
            )
            
            # Mark all active DEPOSITS as withdrawn (stops interest calculation)
            # BUT their transaction_type remains 'deposit'!
            ExpressSaving.objects.filter(
                user=user,
                transaction_type='deposit',  # Only update deposits
                is_withdraw='No'  # Only active ones
            ).update(
                is_withdraw='Yes',  # Stop earning interest
                evaluation_date=timezone.now().date()
            )
            
            # Transfer to Main Wallet
            GoalsIntegrationService.receive_from_goals(
                user=user,
                amount=Fv_after_tax,
                goal_type='express_saving',
                goal_id=None,
                goal_reference=f"express-withdraw-{user.id}-{timezone.now().timestamp()}"
            )
            
            # Reset Goal_Wallet balances
            x.saving_balance = Decimal('0.00')
            x.saving_profit = Decimal('0.00')
            x.goal_balance = Decimal('0.00')
            x.save()
            
            # Send notifications
            message = (
                f"Successfully withdrawn KES {Fv_after_tax} from Express Saving to your Main Wallet. "
                f"You can now withdraw to M-Pesa or use for other ChamaSpace features."
            )
            
            try:
                send_sms(user_profile.phone, 'Withdrawal Successful', message)
                search_str = UserFcmTokens.objects.filter(user=user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Withdrawal Successful", message, None, False, user)
            except Exception as e:
                logger.error(f"Notification failed: {e}")
            
            logger.info(f"Express saving withdrawal: {Fv_after_tax} for user {user.username}")
            
            return JsonResponse({
                'success': '1',
                'amount': str(Fv_after_tax),
                'message': message
            })
            
        except Exception as e:
            logger.error(f"Express saving withdrawal error: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({
                'success': '0',
                'message': f'Withdrawal failed: {str(e)}'
            })
    
    return JsonResponse({'success': '0', 'message': 'Invalid request method'})


@login_required(login_url='Login')
def withdraw_money_personal_goal(request):
    """
    Withdraw all funds from Personal Goal to Main Wallet
    
    WITHDRAWAL RULES:
    - Regular goals: Can ALWAYS withdraw anytime
    - Fixed goals: Can withdraw ONLY when EITHER:
        1. End date has been reached OR passed, OR
        2. Target goal amount has been achieved (if goal_amount is set)
    """
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        user = request.user
        user_profile = Profile.objects.get(owner=user)
        
        try:
            goal_info = Goal.objects.get(pk=goal_id, user=user)
            today = timezone.now().date()
            
            # STEP 1: Check if withdrawal is allowed based on goal type
            can_withdraw = False
            denial_reasons = []
            
            if goal_info.saving_type == 'regular':
                # Regular goals: Can ALWAYS withdraw
                can_withdraw = True
                logger.info(f"Regular goal {goal_id}: Withdrawal allowed (regular goals have no restrictions)")
            
            elif goal_info.saving_type == 'fixed':
                # Fixed goals: Check BOTH conditions, allow if EITHER is met
                
                # CONDITION 1: Check if end date has been reached or passed
                end_date_reached = False
                if goal_info.end_date:
                    if today >= goal_info.end_date:
                        end_date_reached = True
                        can_withdraw = True
                        logger.info(f"Fixed goal {goal_id}: End date condition MET (today={today}, end_date={goal_info.end_date})")
                    else:
                        days_remaining = (goal_info.end_date - today).days
                        denial_reasons.append(f"End date not reached (still {days_remaining} days remaining until {goal_info.end_date})")
                        logger.info(f"Fixed goal {goal_id}: End date condition NOT met ({days_remaining} days remaining)")
                else:
                    denial_reasons.append("No end date set")
                    logger.warning(f"Fixed goal {goal_id}: No end date set (this shouldn't happen for fixed goals)")
                
                # CONDITION 2: Check if target amount has been achieved
                target_reached = False
                if goal_info.goal_amount:
                    if goal_info.goal_balance >= goal_info.goal_amount:
                        target_reached = True
                        can_withdraw = True
                        logger.info(f"Fixed goal {goal_id}: Target amount condition MET (balance={goal_info.goal_balance}, target={goal_info.goal_amount})")
                    else:
                        amount_remaining = goal_info.goal_amount - goal_info.goal_balance
                        denial_reasons.append(f"Target amount not achieved (KES {amount_remaining:.2f} remaining to reach KES {goal_info.goal_amount})")
                        logger.info(f"Fixed goal {goal_id}: Target amount condition NOT met (KES {amount_remaining:.2f} remaining)")
                else:
                    denial_reasons.append("No target amount set")
                    logger.info(f"Fixed goal {goal_id}: No target amount set")
                
                # If NEITHER condition is met, deny withdrawal
                if not can_withdraw:
                    error_msg = (
                        f"❌ Withdrawal Not Allowed for Fixed Goal\n\n"
                        f"Fixed goals can be withdrawn when EITHER condition is met:\n"
                        f"1️⃣ End date is reached, OR\n"
                        f"2️⃣ Target amount is achieved\n\n"
                        f"Current Status:\n"
                        f"{chr(10).join(['• ' + reason for reason in denial_reasons])}\n\n"
                        f"Please wait until one of these conditions is satisfied."
                    )
                    logger.warning(f"Fixed goal {goal_id}: Withdrawal DENIED - {'; '.join(denial_reasons)}")
                    return JsonResponse({
                        'success': '0',
                        'message': error_msg
                    })
                else:
                    logger.info(f"Fixed goal {goal_id}: Withdrawal ALLOWED (at least one condition met)")
            
            # STEP 2: Calculate withdrawal amount (with tax deduction on profit)
            tax_rate_amount = tax_Rate.objects.get(pk=1)
            
            # Total before tax
            total_before_tax = goal_info.goal_balance + goal_info.goal_profit
            
            # Tax only applies to profit
            tax_on_profit = goal_info.goal_profit * tax_rate_amount.tax_rate_value
            
            # Final amount after tax
            Fv_after_tax = total_before_tax - tax_on_profit
            
            # Round to 2 decimal places
            Fv_after_tax = Fv_after_tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            logger.info(f"Goal {goal_id} withdrawal calculation: Balance={goal_info.goal_balance}, Profit={goal_info.goal_profit}, Tax={tax_on_profit}, Final={Fv_after_tax}")
            
            # Check if there are actually funds to withdraw
            if Fv_after_tax <= 0:
                return JsonResponse({
                    'success': '0',
                    'message': 'No funds available for withdrawal. Please deposit funds first.'
                })
            
            # STEP 3: Mark all deposits as withdrawn
            deposits_updated = Deposit.objects.filter(goal=goal_info, is_withdraw='No').update(is_withdraw='Yes')
            logger.info(f"Goal {goal_id}: Marked {deposits_updated} deposits as withdrawn")
            
            # STEP 4: Transfer funds to Main Wallet
            try:
                GoalsIntegrationService.receive_from_goals(
                    user=user,
                    amount=Fv_after_tax,
                    goal_type='personal_goal',
                    goal_id=goal_info.id,
                    goal_reference=f"goal-withdraw-{goal_info.id}-{timezone.now().timestamp()}"
                )
                logger.info(f"Goal {goal_id}: Successfully transferred KES {Fv_after_tax} to Main Wallet")
            except Exception as e:
                logger.error(f"Goal {goal_id}: Transfer to Main Wallet FAILED - {str(e)}")
                return JsonResponse({
                    'success': '0',
                    'message': f'Transfer to Main Wallet failed: {str(e)}'
                })
            
            # STEP 5: Reset goal balances and mark as inactive
            goal_info.goal_profit = Decimal('0.00')
            goal_info.goal_balance = Decimal('0.00')
            goal_info.is_active = 'No'
            goal_info.save(skip_validation=True)
            logger.info(f"Goal {goal_id}: Reset balances and marked as inactive")
            
            # STEP 6: Build success message with completion reason
            completion_reason = ""
            if goal_info.saving_type == 'fixed':
                if target_reached and end_date_reached:
                    completion_reason = " (Both target amount AND end date achieved! 🎉)"
                elif target_reached:
                    completion_reason = " (Target amount achieved! 🎯)"
                elif end_date_reached:
                    completion_reason = " (End date reached 📅)"
            
            message = (
                f"Withdrawal Successful!\n\n"
                f"KES {Fv_after_tax} has been withdrawn from goal '{goal_info.name}'{completion_reason}\n\n"
                f"The funds are now in your Main Wallet. You can:\n"
                f"• Withdraw to M-Pesa\n"
                f"• Use for other ChamaSpace features\n"
                f"• Transfer to another goal"
            )
            
            # STEP 7: Send notifications
            try:
                send_sms(user_profile.phone, 'Withdrawal Successful', message)
                search_str = UserFcmTokens.objects.filter(user=user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Withdrawal Successful", message, None, False, user)
                logger.info(f"Goal {goal_id}: Notifications sent successfully")
            except Exception as e:
                logger.error(f"Goal {goal_id}: Notification failed - {e}")
            
            logger.info(f"Personal goal withdrawal COMPLETED: KES {Fv_after_tax} for goal {goal_info.id} by user {user.username}")
            
            return JsonResponse({
                'success': '1',
                'amount': str(Fv_after_tax),
                'message': message
            })
            
        except Goal.DoesNotExist:
            logger.error(f"Goal {goal_id} not found for user {user.username}")
            return JsonResponse({
                'success': '0',
                'message': 'Goal not found or you do not have permission to access it.'
            })
        except Exception as e:
            logger.error(f"Personal goal withdrawal error for goal {goal_id}: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({
                'success': '0',
                'message': f'Withdrawal failed: {str(e)}'
            })
    
    return JsonResponse({'success': '0', 'message': 'Invalid request method'})


@login_required(login_url='Login')
def withdraw_money_group_goal(request):
    """
    Withdraw all funds from Group Goal to Main Wallet (Creator only)
    
    WITHDRAWAL RULES:
    - Only the CREATOR can initiate withdrawal
    - Regular goals: Can ALWAYS withdraw anytime
    - Fixed goals: Can withdraw ONLY when EITHER:
        1. End date has been reached OR passed, OR
        2. Target amount has been achieved
    """
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        user = request.user
        
        try:
            goal_info = GroupGoal.objects.get(pk=goal_id)
            today = timezone.now().date()
            
            # STEP 1: Verify that only creator can withdraw
            if goal_info.creator != user:
                logger.warning(f"Group goal {goal_id}: User {user.username} attempted withdrawal but is not creator")
                return JsonResponse({
                    'success': '0',
                    'message': '❌ Only the group goal creator can initiate withdrawals. Please contact the goal creator.'
                })
            
            # STEP 2: Check if withdrawal is allowed based on goal type
            can_withdraw = False
            denial_reasons = []
            
            if goal_info.saving_type == 'regular':
                # Regular goals: Can ALWAYS withdraw
                can_withdraw = True
                logger.info(f"Regular group goal {goal_id}: Withdrawal allowed (regular goals have no restrictions)")
            
            elif goal_info.saving_type == 'fixed':
                # Fixed goals: Check BOTH conditions, allow if EITHER is met
                
                # CONDITION 1: Check if end date has been reached or passed
                end_date_reached = False
                if goal_info.end_date:
                    if today >= goal_info.end_date:
                        end_date_reached = True
                        can_withdraw = True
                        logger.info(f"Fixed group goal {goal_id}: End date condition MET (today={today}, end_date={goal_info.end_date})")
                    else:
                        days_remaining = (goal_info.end_date - today).days
                        denial_reasons.append(f"End date not reached (still {days_remaining} days remaining until {goal_info.end_date})")
                        logger.info(f"Fixed group goal {goal_id}: End date condition NOT met ({days_remaining} days remaining)")
                else:
                    denial_reasons.append("No end date set")
                    logger.warning(f"Fixed group goal {goal_id}: No end date set (this shouldn't happen for fixed goals)")
                
                # CONDITION 2: Check if target amount has been achieved
                target_reached = False
                if goal_info.target_amount:
                    if goal_info.achieved_amount >= goal_info.target_amount:
                        target_reached = True
                        can_withdraw = True
                        logger.info(f"Fixed group goal {goal_id}: Target amount condition MET (achieved={goal_info.achieved_amount}, target={goal_info.target_amount})")
                    else:
                        amount_remaining = goal_info.target_amount - goal_info.achieved_amount
                        denial_reasons.append(f"Target amount not achieved (KES {amount_remaining:.2f} remaining to reach KES {goal_info.target_amount})")
                        logger.info(f"Fixed group goal {goal_id}: Target amount condition NOT met (KES {amount_remaining:.2f} remaining)")
                else:
                    denial_reasons.append("No target amount set")
                    logger.info(f"Fixed group goal {goal_id}: No target amount set")
                
                # If NEITHER condition is met, deny withdrawal
                if not can_withdraw:
                    error_msg = (
                        f"❌ Withdrawal Not Allowed for Fixed Group Goal\n\n"
                        f"Fixed group goals can be withdrawn when EITHER condition is met:\n"
                        f"1️⃣ End date is reached, OR\n"
                        f"2️⃣ Target amount is achieved\n\n"
                        f"Current Status:\n"
                        f"{chr(10).join(['• ' + reason for reason in denial_reasons])}\n\n"
                        f"Please wait until one of these conditions is satisfied."
                    )
                    logger.warning(f"Fixed group goal {goal_id}: Withdrawal DENIED - {'; '.join(denial_reasons)}")
                    return JsonResponse({
                        'success': '0',
                        'message': error_msg
                    })
                else:
                    logger.info(f"Fixed group goal {goal_id}: Withdrawal ALLOWED (at least one condition met)")
            
            # STEP 3: Calculate withdrawal amount (with tax deduction on profit)
            tax_rate_amount = tax_Rate.objects.get(pk=1)
            
            # Total before tax
            total_before_tax = goal_info.achieved_amount
            
            # Tax only applies to profit
            tax_on_profit = goal_info.profit * tax_rate_amount.tax_rate_value
            
            # Final amount after tax
            Fv_after_tax = total_before_tax - tax_on_profit
            
            # Round to 2 decimal places
            Fv_after_tax = Fv_after_tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            logger.info(f"Group goal {goal_id} withdrawal calculation: Achieved={goal_info.achieved_amount}, Profit={goal_info.profit}, Tax={tax_on_profit}, Final={Fv_after_tax}")
            
            # Check if there are actually funds to withdraw
            if Fv_after_tax <= 0:
                return JsonResponse({
                    'success': '0',
                    'message': 'No funds available for withdrawal. Please ensure members have contributed.'
                })
            
            # STEP 4: Mark all contributions as withdrawn
            contributions_updated = GroupGoalMember_contribution.objects.filter(
                group_goal=goal_info, 
                is_withdraw='No'
            ).update(is_withdraw='Yes')
            logger.info(f"Group goal {goal_id}: Marked {contributions_updated} contributions as withdrawn")
            
            # STEP 5: Transfer funds to Creator's Main Wallet
            try:
                GoalsIntegrationService.receive_from_goals(
                    user=user,
                    amount=Fv_after_tax,
                    goal_type='group_goal',
                    goal_id=goal_info.id,
                    goal_reference=f"group-withdraw-{goal_info.id}-{timezone.now().timestamp()}"
                )
                logger.info(f"Group goal {goal_id}: Successfully transferred KES {Fv_after_tax} to creator's Main Wallet")
            except Exception as e:
                logger.error(f"Group goal {goal_id}: Transfer to Main Wallet FAILED - {str(e)}")
                return JsonResponse({
                    'success': '0',
                    'message': f'Transfer to Main Wallet failed: {str(e)}'
                })
            
            # STEP 6: Build completion reason message
            completion_reason = ""
            if goal_info.saving_type == 'fixed':
                if target_reached and end_date_reached:
                    completion_reason = " (Both target amount AND end date achieved! 🎉)"
                elif target_reached:
                    completion_reason = " (Target amount achieved! 🎯)"
                elif end_date_reached:
                    completion_reason = " (End date reached 📅)"
            
            # STEP 7: Send notification to creator
            creator_profile = Profile.objects.get(owner=goal_info.creator)
            creator_msg = (
                f"Group Goal Withdrawal Successful!\n\n"
                f"KES {Fv_after_tax} has been withdrawn from group goal '{goal_info.goal_name}'{completion_reason}\n\n"
                f"The funds are now in your Main Wallet. You can:\n"
                f"• Withdraw to M-Pesa\n"
                f"• Use for other ChamaSpace features\n"
                f"• Transfer to another goal"
            )
            
            try:
                send_sms(creator_profile.phone, 'Withdrawal Successful', creator_msg)
                search_str = UserFcmTokens.objects.filter(user=user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Withdrawal Successful", creator_msg, None, False, user)
                logger.info(f"Group goal {goal_id}: Creator notification sent successfully")
            except Exception as e:
                logger.error(f"Group goal {goal_id}: Creator notification failed - {e}")
            
            # STEP 8: Notify all group members about the withdrawal
            members = GroupGoalMember.objects.filter(group_goal=goal_info).exclude(user=user)
            logger.info(f"Group goal {goal_id}: Notifying {members.count()} members about withdrawal")
            
            for member in members:
                try:
                    member_profile = Profile.objects.get(owner=member.user)
                    member_msg = (
                        f"📢 Group Goal Completed!\n\n"
                        f"{goal_info.creator.first_name} {goal_info.creator.last_name} has withdrawn funds from group goal "
                        f"'{goal_info.goal_name}'{completion_reason}\n\n"
                        f"Total withdrawn: KES {Fv_after_tax}\n"
                        f"The goal is now complete. Thank you for participating!"
                    )
                    send_sms(member_profile.phone, 'Group Goal Completed', member_msg)
                    search_str = UserFcmTokens.objects.filter(user=member.user).order_by('-token')[:1]
                    send_notif(search_str, None, True, True, "Group Goal Completed", member_msg, None, False, member.user)
                except Exception as e:
                    logger.error(f"Group goal {goal_id}: Member {member.user.username} notification failed - {e}")
            
            # STEP 9: Reset goal balances and mark as inactive
            goal_info.profit = Decimal('0.00')
            goal_info.achieved_amount = Decimal('0.00')
            goal_info.is_active = 'No'
            goal_info.save(skip_validation=True)
            logger.info(f"Group goal {goal_id}: Reset balances and marked as inactive")
            
            logger.info(f"✅ Group goal withdrawal COMPLETED: KES {Fv_after_tax} for goal {goal_info.id} by creator {user.username}")
            
            return JsonResponse({
                'success': '1',
                'amount': str(Fv_after_tax),
                'message': creator_msg
            })
            
        except GroupGoal.DoesNotExist:
            logger.error(f"Group goal {goal_id} not found")
            return JsonResponse({
                'success': '0',
                'message': 'Group goal not found or you do not have permission to access it.'
            })
        except Exception as e:
            logger.error(f"Group goal withdrawal error for goal {goal_id}: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({
                'success': '0',
                'message': f'Withdrawal failed: {str(e)}'
            })
    
    return JsonResponse({'success': '0', 'message': 'Invalid request method'})

def delete_goal(request):
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        try:
            Goal.objects.get(pk=goal_id).delete()
            return JsonResponse({'success': '1'})
        except Goal.DoesNotExist:
            return JsonResponse({'success': '0', 'message': 'Goal not found'})
        except Exception as e:
            logger.error(f"Delete goal error: {e}")
            return JsonResponse({'success': '0', 'message': str(e)})


def edit_goal(request):
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        goal_title = request.POST.get('goal_title')
        goal_info = Goal.objects.get(pk=goal_id)
        goal_info.name = goal_title
        goal_info.save(skip_validation=True)
        return redirect('goals:goal_details', goal_id)


def edit_group_goal(request):
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        goal_title = request.POST.get('goal_title')
        goal_info = GroupGoal.objects.get(pk=goal_id)
        goal_info.goal_name = goal_title
        goal_info.save(skip_validation=True)
        return redirect('goals:group_goal_details', goal_id)


@login_required(login_url='Login')
def send_invitations(request):
    if request.method == 'POST':
        try:
            goal_id = request.POST.get('goal_id')
            Phone_no_input = str(request.POST.get('nic'))
            without_zero_cellno = Phone_no_input[1:]
            Phone_no = '+254' + without_zero_cellno
            group_goal_info = GroupGoal.objects.get(pk=goal_id)
            domain = get_current_site(request).domain
            ref_url = 'https://' + domain + '/goals/add_members/' + str(group_goal_info.id)

            if Profile.objects.filter(phone=Phone_no).exists():
                receiver_profile = Profile.objects.get(phone=Phone_no)
                msg = f"You have been invited by {request.user.first_name} {request.user.last_name} to join a group goal titled {group_goal_info.goal_name}. <a href='{ref_url}'>Click here to join now</a>."
                send_sms(receiver_profile.phone, 'Invitation', msg)
                search_str = UserFcmTokens.objects.filter(user=receiver_profile.owner).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Invitation", msg, None, False, receiver_profile.owner)
            else:
                msg = f"You have been invited by {request.user.first_name} {request.user.last_name} to join a group goal titled {group_goal_info.goal_name}. If you don't have an account yet, please visit www.chamaspace.com to create an account. After creating an account, click the following link to join: {ref_url}."
                send_sms(Phone_no, 'Invitation', msg)

            return JsonResponse({'success': '1'})
        except Exception as e:
            logger.error(f"Invitation sending failed: {e}")
            return JsonResponse({'success': '0'})


# --- PDF STATEMENT VIEWS (KEPT AS-IS, NO WALLET LOGIC) ---

def goal_statement(request, id):
    if GroupGoalMember.objects.filter(user=request.user, group_goal_id=id).exists():
        user_profile = Profile.objects.get(owner=request.user)
        goal_info = GroupGoal.objects.get(pk=id)
        all_deposits = GroupGoalMember_contribution.objects.filter(group_goal=goal_info).order_by('-created_at')
        user_total_contributions = all_deposits.values(
            'user__first_name', 'user__last_name', 'user__profile__phone', 'user__profile__picture'
        ).annotate(total_amount=Sum('amount')).order_by('user')
        context = {
            'user_total_contributions': user_total_contributions,
            'goal_info': goal_info
        }
        pdf = render_to_pdf('new/group_goal_statement.html', context)
        return HttpResponse(pdf, content_type='application/pdf')
    else:
        return redirect('user_dashboard:home')


def personal_goal_statement(request, id):
    user_profile = Profile.objects.get(owner=request.user)
    goal_info = Goal.objects.get(pk=id)
    all_deposits = Deposit.objects.filter(goal=goal_info).order_by('-deposit_date')
    context = {
        'all_deposits': all_deposits,
        'goal_info': goal_info,
        'user_profile': user_profile
    }
    pdf = render_to_pdf('new/personal_goal_statement.html', context)
    return HttpResponse(pdf, content_type='application/pdf')


def express_statement(request, username):
    user_profile = Profile.objects.get(owner=request.user)
    all_express_savings = ExpressSaving.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'all_express_savings': all_express_savings,
        'user_profile': user_profile
    }
    pdf = render_to_pdf('new/express_statement.html', context)
    return HttpResponse(pdf, content_type='application/pdf')