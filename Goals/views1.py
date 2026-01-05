import datetime
from dateutil.relativedelta import relativedelta
import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from notifications.models import UserFcmTokens
from notifications.utils import *
# Create your views here.
from authentication.models import *
from notifications.models import *
from django.contrib.sites.shortcuts import get_current_site
from pyment_withdraw.models import *
from django.db.models import Sum
#from Dashboard.models import *
from .models import *
from django.template.loader import get_template
from django.db.models import Q
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
import xhtml2pdf.pisa as pisa
import logging

# NEW: Import wallet services
try:
    from wallet.services import GoalsIntegrationService
    WALLET_SERVICE_AVAILABLE = True
except ImportError:
    WALLET_SERVICE_AVAILABLE = False
    
logger = logging.getLogger(__name__)  # <--- ADD THIS

def calculate_future_value_express(obj):
    # Get the user's wallet
    total_amount = Decimal(0)
    now = timezone.now()
    for self in obj:
        if self.is_withdraw == 'No':
            interest_value = Interest_Rate.objects.get(pk=1)


            delta = relativedelta(now, self.created_at)

            # Calculate the total months elapsed using floating-point division
            days_difference = delta.years * 365 + delta.months * 30 + delta.days
            daily_interest_rate = Decimal(interest_value.regular_deposit) / 365


            # Calculate the future value using Decimal type for more accuracy
            future_value = self.amount * (1 + daily_interest_rate) ** Decimal(days_difference)
            print('Line no 31', self.amount, days_difference, future_value)
            total_amount += Decimal(future_value) - Decimal(self.amount)

    return round(total_amount, 2)





def calculate_future_goals(obj, goal_info):
    interest_value = Interest_Rate.objects.get(pk=1)
    interest_rate = Decimal(0.0)
    if goal_info.saving_type == 'fixed':
        interest_rate = interest_value.fixed_deposit
    if goal_info.saving_type == 'regular':
        interest_rate = interest_value.regular_deposit


    total_amount = Decimal(0)
    now = timezone.now()
    for self in obj:
        if self.is_withdraw == 'No':
            delta = relativedelta(now, self.deposit_date)

            # Calculate the total months elapsed using floating-point division
            days_difference = delta.years * 365 + delta.months * 30 + delta.days
            daily_interest_rate = Decimal(interest_rate) / 365

            # Calculate the future value using Decimal type for more accuracy
            future_value = self.amount * (1 + Decimal(daily_interest_rate)) ** Decimal(days_difference)

            total_amount += Decimal(future_value) - (self.amount)


    return round(total_amount, 2)


def calculate_future_group_goals(obj):
    total_amount = Decimal(0)
    now = timezone.now()
    for self in obj:
        if self.is_withdraw == 'No':
            delta = relativedelta(now, self.created_at)
            interest_value = Interest_Rate.objects.get(pk=1)

            # Calculate the total months elapsed using floating-point division
            days_difference = delta.years * 365 + delta.months * 30 + delta.days
            daily_interest_rate = Decimal(interest_value.fixed_deposit) / 365


            # Calculate the future value using Decimal type for more accuracy
            future_value = self.amount * (1 + daily_interest_rate) ** Decimal(days_difference)
            print('Line no 69 group goal', self.amount, days_difference, future_value)
            total_amount += Decimal(future_value) - (self.amount)

    return round(total_amount, 2)



def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None


@login_required(login_url='Login')
def goals_dashboard(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    all_express_savings = ExpressSaving.objects.filter(user=request.user).order_by('-created_at')



    all_goals_active = Goal.objects.filter(user=request.user).order_by('-created_at')
    print('Lenth of goals:',len(all_goals_active))
    complete_goals = []
    progressing_goals = []

    for item in all_goals_active:

        goal_percentage = item.percentage()
        if goal_percentage == 100:
            complete_goals.append(item)
        else:
            progressing_goals.append(item)




    all_group_goal = GroupGoal.objects.filter(creator=request.user).order_by('-created_at')

    context = {'user_profile': user_profile, 'user_notifications': user_notifications,
               'all_express_savings': all_express_savings,
               'complete_goals': complete_goals,'progressing_goals':progressing_goals,
               'all_group_goal': all_group_goal
               }

    return render(request, 'Goals/wekeza_dashboard.html', context)


@login_required(login_url='Login')
def my_goals(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    all_express_savings = ExpressSaving.objects.filter(user=request.user).order_by('-created_at')

    all_goals = Goal.objects.filter(user=request.user).order_by('-created_at')
    complete_goals = []
    progressing_goals = []

    for item in all_goals:


        if item.is_active == 'No':
            complete_goals.append(item)
        else:
            progressing_goals.append(item)
    all_group_goal = GroupGoal.objects.filter(
        Q(creator=request.user) | Q(groupgoalmember__user=request.user)
    ).order_by('-created_at')

    group_complete_goals = []
    group_progressing_goals = []

    for item in all_group_goal:


        if item.is_active == 'No':
            if item not in group_complete_goals:
                group_complete_goals.append(item)


        else:
            if item not in group_progressing_goals:
                group_progressing_goals.append(item)
    total_complete=len(group_complete_goals)+len(complete_goals)


    user_wallet = Wallet.objects.get(user_id=request.user)
    my_wallet, created = Goal_Wallet.objects.get_or_create(user=request.user)

    # ADD THIS: Get new Main Wallet
    try:
        from wallet.models import MainWallet
        main_wallet = MainWallet.objects.get(user=request.user)
    except:
        main_wallet = None  # Fallback if not migrated yet


    context = {
        'user_profile': user_profile, 
        'user_notifications': user_notifications,
        'all_express_savings': all_express_savings,
        'all_group_goal': all_group_goal,
        'user_wallet': user_wallet,  # Old wallet (for compatibility)
        'main_wallet': main_wallet,   # NEW: Main wallet
        'my_wallet': my_wallet,
        'complete_goals': complete_goals,
        'progressing_goals': progressing_goals,
        'group_complete_goals': group_complete_goals,
        'group_progressing_goals': group_progressing_goals,
        'interest_rate': Interest_Rate.objects.get(pk=1),
        'total_complete': total_complete
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
        send_notif(search_str, None, True, True, "Group Exit", 'Successfully exit goal ' + x.goal_name,
                   None, False,
                   request.user)
        messages.success(request, 'Group exit successfully.')
        return redirect('user_dashboard:home')


def delete_group_goal(request):
    if request.method == 'POST':
        goal_group_id = request.POST.get('goal_id')
        x = GroupGoal.objects.get(pk=goal_group_id)

        x.delete()

        response = {'success': '1'}
        print('Group Goal deleted Now:', response)
        return JsonResponse(response)


@login_required(login_url='Login')
def express_saving_dashboard(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    all_express_savings = ExpressSaving.objects.filter(user=request.user).order_by('-created_at')
    result = calculate_future_value_express(all_express_savings)
    print('Line 69 result is:', result)
    my_wallet, created = Goal_Wallet.objects.get_or_create(user=request.user)
    my_wallet.saving_profit = result

    my_wallet.save()
    my_wallet.goal_balance = my_wallet.saving_balance + my_wallet.saving_profit
    my_wallet.save()
    tax_rate_amount=tax_Rate.objects.get(pk=1)
    Fv_after_tax = (Decimal(my_wallet.saving_balance) + Decimal(my_wallet.saving_profit)) - (
                Decimal(my_wallet.saving_profit) * tax_rate_amount.tax_rate_value)
    intrest_rate=Interest_Rate.objects.get(pk=1)


    context = {'user_profile': user_profile, 'user_notifications': user_notifications,
               'all_express_savings': all_express_savings,
               'my_wallet': my_wallet,
               'Fv_after_tax': Fv_after_tax,'intrest_value':intrest_rate.regular_deposit*100

               }
    return render(request, 'new/express_saving_dashboard.html', context)


@login_required(login_url='Login')
def express_saving(request):
    """
    Express saving deposit - UPDATED to use Main Wallet
    """
    user_profile = Profile.objects.get(owner=request.user)
    user_wallet = Wallet.objects.get(user_id=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    
    if request.method == 'POST':
        amount = Decimal(request.POST['amount'])
        
        if user_wallet.available_for_withdraw >= amount:
            # Create express saving record
            express_saving = ExpressSaving.objects.create(
                user=request.user, 
                amount=amount, 
                is_withdraw='No'
            )
            express_saving.save()
            
            # ============================================
            # STEP 1: Deduct from OLD wallet (backwards compatibility)
            # ============================================
            user_wallet.available_for_withdraw -= float(amount)
            user_wallet.save()
            print('Amount deducted from old wallet:', amount)
            
            # ============================================
            # STEP 2: Try to use NEW Main Wallet
            # ============================================
            if WALLET_SERVICE_AVAILABLE:
                try:
                    GoalsIntegrationService.transfer_to_goals(
                        user=request.user,
                        amount=amount,
                        goal_type='express_saving',
                        goal_id=express_saving.id
                    )
                    print('✅ Amount transferred via NEW Main Wallet')
                    logger.info(f"Express saving deposit: {amount} for user {request.user.username}")
                except Exception as e:
                    print(f'⚠️ New wallet transfer failed: {str(e)}')
                    logger.warning(f"Failed to use new wallet for express saving: {str(e)}")
                    # Old wallet already deducted, so continue
            
            # Update the Goal wallet balance
            wallet, _ = Goal_Wallet.objects.get_or_create(user=request.user)
            wallet.saving_balance += amount
            wallet.save()
            
            try:
                send_sms(user_profile.phone, 'Important Alert',
                         'Successfully deposit ' + str(amount) + 'Ksh to express saving.')
                search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Congratulation",
                           'Successfully deposit ' + str(amount) + ' Ksh to express saving.',
                           None, False,
                           request.user)
            except Exception as e:
                print('Line no 141 exception is:', e)
                pass

            response = {'success': '1'}
            print('Response being returning is:', response)
            return JsonResponse(response)
        else:
            response = {'success': '2'}
            print('Response being returning is:', response)
            return JsonResponse(response)

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


@login_required(login_url='Login')
def create_personal_goals(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    if request.method == 'POST':
        saving_type_added = request.POST.get('saving_input_type')

        goal_title = request.POST.get('goal_title')

        is_saving_or_goal = request.POST.get('is_saving_or_goal')
        just_want_to_save = request.POST.get('just_want_to_save')

        reminder_frequency = request.POST.get('reminder_frequency')
        select_payment_frequency = request.POST.get('select_payment_frequency')

        print('Line no 130', saving_type_added, goal_title, is_saving_or_goal, just_want_to_save,
              reminder_frequency, select_payment_frequency)

        goal = Goal.objects.create(user=request.user, name=goal_title, saving_type=saving_type_added,
                                   reminder_frequency=reminder_frequency,
                                   payment_frequency=select_payment_frequency,
                                   )

        if is_saving_or_goal == None:
            try:
                goal.goal_amount = Decimal(request.POST['target_amount'])
                goal.amount_to_save_per_notification = Decimal(request.POST['amount_to_save'])
            except:
                goal.goal_amount = 0.0
                goal.amount_to_save_per_notification = 0.0
        else:
            goal.amount_to_save_per_notification = Decimal(request.POST['amount_to_save'])

        if just_want_to_save == 'on':
            goal.start_date = request.POST.get('start_date')





        else:
            goal.start_date = request.POST.get('start_date')
            goal.end_date = request.POST.get('end_date')

        if reminder_frequency == 'monthly':

            goal.notification_date=date.today() + relativedelta(months=1)
        if reminder_frequency == 'weekly':
            goal.notification_date = date.today() + relativedelta(weeks=1)
        if reminder_frequency == 'daily':
            goal.notification_date = date.today() + relativedelta(days=1)


        goal.save()
        try:
            send_sms(user_profile.phone, 'Congratulations', 'You have successfully started your new goal ' + goal_title)
            search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
            send_notif(search_str, None, True, True, "Congratulation",
                       'You have successfully started your new goal ' + goal_title,
                       None, False,
                       request.user)
        except Exception as e:
            print('Line no 202 exception is:', e)
            pass

        response = {'success': '1', 'goal_id': goal.id}
        print('Response being returning is after goal created is:', response)
        return JsonResponse(response)

    context = {'user_profile': user_profile, 'user_notifications': user_notifications,
               }
    return render(request, 'creat_personal_goals.html', context)


@login_required(login_url='Login')
def goal_details(request, id):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    goal_info = Goal.objects.get(pk=id)
    all_deposits = Deposit.objects.filter(goal=goal_info).order_by('-deposit_date')

    if goal_info.is_active == 'Yes':
        print('Line no 360 on personal goal',goal_info.end_date)

        if  goal_info.end_date!=None and date.today() > goal_info.end_date:

            print('Line no 364 in personal goals, goal end date has been passed ,, no interest being calculated.',)
            pass
        else:

            result = calculate_future_goals(all_deposits, goal_info)
            print('Line no 369 in personal goal value of result is: ',result)

            goal_info.goal_profit = result
            goal_info.save()
    # {{goal_info.goal_balance | add: goal_info.goal_profit}}
    tax_rate_amount = tax_Rate.objects.get(pk=1)

    Fv_after_tax = (Decimal(goal_info.goal_balance) + Decimal(goal_info.goal_profit)) - (
                Decimal(goal_info.goal_profit) * tax_rate_amount.tax_rate_value)

    can_withdraw = ''
    try:

        if goal_info.saving_type == 'fixed' and goal_info.end_date > date.today():
            can_withdraw = 'No'
        else:
            can_withdraw = 'Yes'
    except:
        can_withdraw = 'Yes'

    interest_rate=''

    interest_value = Interest_Rate.objects.get(pk=1)
    if goal_info.saving_type == 'fixed':
        interest_value = interest_value.fixed_deposit * 100
    if goal_info.saving_type == 'regular':
        interest_value = interest_value.regular_deposit * 100

    context = {'user_profile': user_profile, 'user_notifications': user_notifications, 'goal_info': goal_info,
               'all_deposits': all_deposits, 'can_withdraw': can_withdraw, 'Fv_after_tax': Fv_after_tax,'interest_rate':interest_value
               }
    return render(request, 'new/goal_details.html', context)


@login_required(login_url='Login')
def add_funds_to_goal(request, id):
    """
    Add funds to personal goal - UPDATED to use Main Wallet
    """
    user_profile = Profile.objects.get(owner=request.user)
    user_wallet = Wallet.objects.get(user_id=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    goal_info = Goal.objects.get(pk=id)

    if request.method == 'POST':
        amount = Decimal(request.POST['add_money'])
        
        if user_wallet.available_for_withdraw >= amount:
            # Create deposit record
            Deposit.objects.create(goal=goal_info, amount=amount).save()

            # ============================================
            # STEP 1: Deduct from OLD wallet (backwards compatibility)
            # ============================================
            user_wallet.available_for_withdraw -= float(amount)
            user_wallet.save()
            print('Amount deducted from old wallet:', amount)
            
            # ============================================
            # STEP 2: Try to use NEW Main Wallet
            # ============================================
            if WALLET_SERVICE_AVAILABLE:
                try:
                    GoalsIntegrationService.transfer_to_goals(
                        user=request.user,
                        amount=amount,
                        goal_type='personal_goal',
                        goal_id=goal_info.id
                    )
                    print('✅ Amount transferred via NEW Main Wallet')
                    logger.info(f"Personal goal deposit: {amount} for goal {goal_info.id}")
                except Exception as e:
                    print(f'⚠️ New wallet transfer failed: {str(e)}')
                    logger.warning(f"Failed to use new wallet for personal goal: {str(e)}")
                    # Old wallet already deducted, so continue
            
            # Update the goal balance
            goal_info.goal_balance += amount
            goal_info.save()
            
            try:
                send_sms(user_profile.phone, 'Congratulations',
                         'You have successfully deposited ' + str(amount) + 'Ksh to your ' + goal_info.name)
                search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Congratulation",
                           'Successfully deposit ' + str(amount) + 'Ksh to your ' + goal_info.name,
                           None, False,
                           request.user)
            except Exception as e:
                print('Line no 249 exception is:', e)
                pass

            response = {'success': '1'}
            print('Response being returning from add amount to goal is:', response)
            return JsonResponse(response)
        else:
            response = {'success': '2'}
            print('Response being returning from add amount to goal is:', response)
            return JsonResponse(response)

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
    if request.method == 'POST':
        saving_type_added = request.POST.get('saving_type_input')

        goal_title = request.POST.get('goal_name')
        goal_mission = request.POST.get('goal_mission')
        start_date = request.POST.get('start_date')

        end_date = request.POST.get('end_date')

        target_amount = Decimal(request.POST['target_amount'])

        goal = GroupGoal.objects.create(creator=request.user, goal_name=goal_title, goal_description=goal_mission,
                                        saving_type=saving_type_added, start_date=start_date,
                                        end_date=end_date, target_amount=target_amount)
        GroupGoalMember.objects.create(user=request.user, group_goal=goal).save()
        domain = get_current_site(request).domain
        ref_url = 'http://' + domain + '/goals/add_members/' + str(goal.id)
        goal.shareable_link = ref_url

        goal.save()

        response = {'success': '1', 'goal_id': goal.id}
        print('Response being returning is after goal created is:', response)
        return JsonResponse(response)

    context = {'user_profile': user_profile, 'user_notifications': user_notifications,
               }
    return render(request, 'create_group_goal.html', context)


@login_required(login_url='Login')
def group_goal_details(request, id):
    if GroupGoalMember.objects.filter(user=request.user).exists():
        user_profile = Profile.objects.get(owner=request.user)
        user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
        goal_info = GroupGoal.objects.get(pk=id)
        all_members = GroupGoalMember.objects.filter(group_goal=goal_info)
        group_activites = GroupGoalActivites.objects.filter(group_goal=goal_info).order_by('-created_at')
        all_deposits = GroupGoalMember_contribution.objects.filter(group_goal=goal_info).order_by('-created_at')
        user_total_contributions = all_deposits.values('user__first_name', 'user__last_name', 'user__profile__phone',
                                            'user__profile__picture','user__username',).annotate(total_amount=Sum('amount')).order_by('user')
        total_amount_contribution=0.0
        for item in all_deposits:
            total_amount_contribution+=float(item.amount)
        if goal_info.is_active == 'Yes' and goal_info.end_date > date.today():
            result = calculate_future_group_goals(all_deposits)

            goal_info.profit = result
            goal_info.achieved_amount = float(total_amount_contribution) + float(goal_info.profit)
            goal_info.save()

        tax_rate_amount = tax_Rate.objects.get(pk=1)
        Fv_after_tax = (Decimal(goal_info.achieved_amount) ) - (
                Decimal(goal_info.profit) * tax_rate_amount.tax_rate_value)
        interest_value = Interest_Rate.objects.get(pk=1)
        if goal_info.saving_type == 'fixed':
            interest_value = interest_value.fixed_deposit * 100
        if goal_info.saving_type == 'regular':
            interest_value = interest_value.regular_deposit * 100




        context = {'user_profile': user_profile, 'user_notifications': user_notifications, 'goal_info': goal_info,
                   'all_members': all_deposits, 'group_activites': group_activites,
                   'user_total_contributions': user_total_contributions,'Fv_after_tax':Fv_after_tax,'interest_value':interest_value
                   }
        return render(request, 'new/group_goal_details.html', context)
    else:
        return redirect('user_dashboard:home')
def goal_statement(request, id):
    if GroupGoalMember.objects.filter(user=request.user).exists():
        user_profile = Profile.objects.get(owner=request.user)

        goal_info = GroupGoal.objects.get(pk=id)

        all_deposits = GroupGoalMember_contribution.objects.filter(group_goal=goal_info).order_by('-created_at')

        user_total_contributions = all_deposits.values('user__first_name', 'user__last_name', 'user__profile__phone','user__profile__picture').annotate(
            total_amount=Sum('amount')).order_by('user')
        context = { 'user_total_contributions': user_total_contributions,'goal_info':goal_info}

        pdf = render_to_pdf('new/group_goal_statement.html',context)
        return HttpResponse(pdf, content_type='application/pdf')

    else:
        return redirect('user_dashboard:home')
def personal_goal_statement(request, id):

        user_profile = Profile.objects.get(owner=request.user)

        goal_info = Goal.objects.get(pk=id)
        all_deposits = Deposit.objects.filter(goal=goal_info).order_by('-deposit_date')


        context = { 'all_deposits': all_deposits,'goal_info':goal_info,'user_profile':user_profile}

        pdf = render_to_pdf('new/personal_goal_statement.html',context)
        return HttpResponse(pdf, content_type='application/pdf')
def express_statement(request, username):

        user_profile = Profile.objects.get(owner=request.user)

        all_express_savings = ExpressSaving.objects.filter(user=request.user).order_by('-created_at')



        context = { 'all_express_savings':all_express_savings,'user_profile':user_profile}

        pdf = render_to_pdf('new/express_statement.html',context)
        return HttpResponse(pdf, content_type='application/pdf')




@login_required(login_url='Login')
def add_members(request, details):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    goal_info = GroupGoal.objects.get(pk=details)
    all_members = GroupGoalMember.objects.filter(group_goal=goal_info)

    if request.method == 'POST':

        if not GroupGoalMember.objects.filter(user=request.user,group_goal=goal_info).exists():
            print('Line no 523 inside not exist of add members:')
            content=str(request.user.first_name) + ' ' + str(request.user.last_name) + ' joined this goal'

            GroupGoalMember.objects.create(user=request.user, group_goal=goal_info).save()
            GroupGoalActivites.objects.create(user=request.user, group_goal=goal_info,
                                              content=content).save()
            print('User joined this group successfully.',goal_info.goal_name)

            try:
                send_sms(user_profile.phone, 'Important Alert',
                         'Successfully joined ' + goal_info.goal_name)
                search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Congratulation",
                           'Successfully joined ' + goal_info.goal_name,
                           None, False,
                           request.user)
            except Exception as e:
                print('Line no 397 exception is:', e)
                pass
        else:
            messages.error(request, ' You are already in the group')
            return redirect('group_goal_details', goal_info.id)

        return redirect('group_goal_details', goal_info.id)

    context = {'user_profile': user_profile, 'user_notifications': user_notifications, 'goal_info': goal_info,
               'all_members': all_members, 'members_count': len(all_members)
               }
    return render(request, 'add_members_to_group_goal.html', context)


@login_required(login_url='Login')
def add_funds_to_group_goal(request):
    """
    Add funds to group goal - UPDATED to use Main Wallet
    """
    if request.method == 'POST':
        goal_id = Decimal(request.POST['goal_id'])
        amount = Decimal(request.POST['amount'])
        user_profile = Profile.objects.get(owner=request.user)
        user_wallet = Wallet.objects.get(user_id=request.user)
        
        if user_wallet.available_for_withdraw >= amount:
            goal_info = GroupGoal.objects.get(pk=goal_id)
            
            # Create contribution record
            GroupGoalMember_contribution.objects.create(
                group_goal=goal_info, 
                amount=amount, 
                user=request.user
            ).save()
            
            # Create activity record
            GroupGoalActivites.objects.create(
                user=request.user, 
                group_goal=goal_info,
                content=request.user.first_name + ' ' + request.user.last_name + 
                        ' made a deposit of Kshs: ' + str(amount) + ' to the group goal.'
            ).save()

            # ============================================
            # STEP 1: Deduct from OLD wallet (backwards compatibility)
            # ============================================
            user_wallet.available_for_withdraw -= float(amount)
            user_wallet.save()
            print('Amount deducted from old wallet:', amount)
            
            # ============================================
            # STEP 2: Try to use NEW Main Wallet
            # ============================================
            if WALLET_SERVICE_AVAILABLE:
                try:
                    GoalsIntegrationService.transfer_to_goals(
                        user=request.user,
                        amount=amount,
                        goal_type='group_goal',
                        goal_id=goal_info.id
                    )
                    print('✅ Amount transferred via NEW Main Wallet')
                    logger.info(f"Group goal deposit: {amount} for goal {goal_info.id}")
                except Exception as e:
                    print(f'⚠️ New wallet transfer failed: {str(e)}')
                    logger.warning(f"Failed to use new wallet for group goal: {str(e)}")
                    # Old wallet already deducted, so continue
            
            # Update the goal balance
            goal_info.achieved_amount += amount
            goal_info.save()
            
            try:
                send_sms(user_profile.phone, 'Important Alert',
                         'Successfully deposit ' + str(amount) + 'Ksh to your ' + goal_info.goal_name)
                search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Congratulation",
                           'Successfully deposit ' + str(amount) + ' Ksh to your ' + goal_info.goal_name,
                           None, False,
                           request.user)
            except Exception as e:
                print('Line no 389 exception is:', e)
                pass

            response = {'success': '1'}
            print('Response being returning is:', response)
            return JsonResponse(response)
        else:
            response = {'success': '2'}
            print('Response being returning is:', response)
            return JsonResponse(response)


def add_account(request):
    if request.method == "POST":
        iban = request.POST.get('iban')
        bank_name = request.POST.get('routing')
        swift_code = request.POST.get('swiftcode')
        branch_id = request.POST.get('branchID')
        account_no = request.POST.get('accountNO')
        bank_country = request.POST.get('bank_country', None)
        user = User.objects.get(username=request.user)
        print(iban, bank_name, swift_code, branch_id, account_no, bank_country, user)
        x = UserBankDetails.objects.create(
            iban=iban,
            bank_name=bank_name,
            swift_code=swift_code,
            branch_id=branch_id,
            account_no=account_no,
            bank_country=bank_country,
            user_id=user

        )
        x.save()
        messages.success(request, 'Account save successfully.')
        return redirect('express_saving_dashboard')

    else:
        return render(request, 'new/add_bank_details.html')


def withdraw_money_express_saving(request):
    """
    Withdraw from express saving - UPDATED to credit Main Wallet
    """
    if request.method == 'POST':
        user = User.objects.get(username=request.user)
        
        if UserBankDetails.objects.filter(user_id=user).exists():
            x = Goal_Wallet.objects.get(user=request.user)
            tax_rate_amount = tax_Rate.objects.get(pk=1)

            Fv_after_tax = (Decimal(x.saving_balance) + Decimal(x.saving_profit)) - (
                        Decimal(x.saving_profit) * tax_rate_amount.tax_rate_value)
            
            transactions = ExpressSaving.objects.filter(user=request.user, is_withdraw='No')
            for item in transactions:
                item.is_withdraw = 'Yes'
                item.save()

            # Create withdrawal request
            UserMoneyWithDrawalStatus.objects.create(
                withdrawal_amount=Fv_after_tax,
                status="Pending...User request For Withdraw money from express saving",
                withraw_for="Express saving",
                user_id=user
            ).save()
            
            # Reset Goal Wallet
            x.saving_balance = 0.0
            x.saving_profit = 0.0
            x.goal_balance = 0.0
            x.save()
            
            # ============================================
            # STEP 1: Credit OLD wallet (backwards compatibility)
            # ============================================
            user_wallet = Wallet.objects.get(user_id=request.user)
            user_wallet.available_for_withdraw += float(Fv_after_tax)
            user_wallet.save()
            print('Amount credited to old wallet:', Fv_after_tax)
            
            # ============================================
            # STEP 2: Try to credit NEW Main Wallet
            # ============================================
            if WALLET_SERVICE_AVAILABLE:
                try:
                    GoalsIntegrationService.receive_from_goals(
                        user=request.user,
                        amount=Fv_after_tax,
                        goal_type='express_saving',
                        goal_id=None,
                        goal_reference=f"express-withdraw-{user.id}-{timezone.now().timestamp()}"
                    )
                    print('✅ Amount credited via NEW Main Wallet')
                    logger.info(f"Express saving withdrawal: {Fv_after_tax} for user {user.username}")
                except Exception as e:
                    print(f'⚠️ New wallet credit failed: {str(e)}')
                    logger.warning(f"Failed to credit new wallet from express saving: {str(e)}")
                    # Old wallet already credited, so continue
            
            # Send notifications
            phone_data_allpending = Profile.objects.get(owner=user)
            send_sms(phone_data_allpending.phone, 'Congratulation',
                     'Your payment withdraw request received. We are processing the transaction, and you will receive a confirmation once it is successfully completed.')
            print('sms sent to user for withdraw')
            
            search_str = UserFcmTokens.objects.filter(user=user).order_by('-token')[:1]
            send_notif(search_str, None, True, True, "Congratulation",
                       "Your payment withdraw request received. We are processing the transaction, and you will receive a confirmation once it is successfully completed.",
                       None, False,
                       user)
            print('notification sent to user for withdraw')

            response = {'success': '1'}
            print('Response being returning is:', response)
            return JsonResponse(response)
        else:
            response = {'success': '0'}
            print('Response being returning is:', response)
            return JsonResponse(response)

def withdraw_money_personal_goal(request):
    """
    Withdraw from personal goal - UPDATED to credit Main Wallet
    """
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        user = User.objects.get(username=request.user)

        if UserBankDetails.objects.filter(user_id=user).exists():
            goal_info = Goal.objects.get(pk=goal_id)
            all_deposits = Deposit.objects.filter(goal=goal_info).order_by('-deposit_date')
            tax_rate_amount = tax_Rate.objects.get(pk=1)

            Fv_after_tax = (Decimal(goal_info.goal_balance) + Decimal(goal_info.goal_profit)) - (
                    Decimal(goal_info.goal_profit) * tax_rate_amount.tax_rate_value)

            for item in all_deposits:
                item.is_withdraw = 'Yes'
                item.save()

            # Create withdrawal request
            UserMoneyWithDrawalStatus.objects.create(
                withdrawal_amount=Fv_after_tax,
                status="Pending...User request For Withdraw money from personal goal",
                withraw_for="Personal Goal of title " + str(goal_info.name),
                user_id=user
            ).save()

            # Reset goal
            goal_info.goal_profit = 0.0
            goal_info.goal_balance = 0.0
            goal_info.is_active = 'No'
            goal_info.save()
            
            # ============================================
            # STEP 1: Credit OLD wallet (backwards compatibility)
            # ============================================
            user_wallet = Wallet.objects.get(user_id=request.user)
            user_wallet.available_for_withdraw += float(Fv_after_tax)
            user_wallet.save()
            print('Amount credited to old wallet:', Fv_after_tax)
            
            # ============================================
            # STEP 2: Try to credit NEW Main Wallet
            # ============================================
            if WALLET_SERVICE_AVAILABLE:
                try:
                    GoalsIntegrationService.receive_from_goals(
                        user=request.user,
                        amount=Fv_after_tax,
                        goal_type='personal_goal',
                        goal_id=goal_info.id,
                        goal_reference=f"goal-withdraw-{goal_info.id}-{timezone.now().timestamp()}"
                    )
                    print('✅ Amount credited via NEW Main Wallet')
                    logger.info(f"Personal goal withdrawal: {Fv_after_tax} for goal {goal_info.id}")
                except Exception as e:
                    print(f'⚠️ New wallet credit failed: {str(e)}')
                    logger.warning(f"Failed to credit new wallet from personal goal: {str(e)}")
                    # Old wallet already credited, so continue

            # Send notifications
            phone_data_allpending = Profile.objects.get(owner=user)
            send_sms(phone_data_allpending.phone, 'Congratulation',
                     'Your payment withdraw request received. We are processing the transaction, and you will receive a confirmation once it is successfully completed.')
            print('sms sent to user for withdraw')
            
            search_str = UserFcmTokens.objects.filter(user=user).order_by('-token')[:1]
            send_notif(search_str, None, True, True, "Important Alert",
                       "Your payment withdraw request received. We are processing the transaction, and you will receive a confirmation once it is successfully completed.",
                       None, False,
                       user)
            print('notification sent to user for withdraw')

            response = {'success': '1'}
            print('Response being returning is:', response)
            return JsonResponse(response)
        else:
            response = {'success': '0'}
            print('Response being returning is:', response)
            return JsonResponse(response)
        

def withdraw_money_group_goal(request):
    """
    Withdraw from group goal - UPDATED to credit Main Wallet
    """
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        print('Goal id inside withdraw request:', goal_id)
        user = User.objects.get(username=request.user)
        
        if UserBankDetails.objects.filter(user_id=user).exists():
            goal_info = GroupGoal.objects.get(pk=goal_id)
            all_deposits = GroupGoalMember_contribution.objects.filter(group_goal=goal_info).order_by('-created_at')
            tax_rate_amount = tax_Rate.objects.get(pk=1)

            Fv_after_tax = (Decimal(goal_info.achieved_amount)) - (
                    Decimal(goal_info.profit) * tax_rate_amount.tax_rate_value)

            for item in all_deposits:
                item.is_withdraw = 'Yes'
                item.save()

            # Create withdrawal request
            UserMoneyWithDrawalStatus.objects.create(
                withdrawal_amount=Fv_after_tax,
                status="Pending...User request For Withdraw money from group goal",
                withraw_for="Group Goal of title " + str(goal_info.goal_name),
                user_id=user
            ).save()
            
            # ============================================
            # STEP 1: Credit OLD wallet (backwards compatibility)
            # ============================================
            user_wallet = Wallet.objects.get(user_id=request.user)
            user_wallet.available_for_withdraw += float(Fv_after_tax)
            user_wallet.save()
            print('Amount credited to old wallet:', Fv_after_tax)
            
            # ============================================
            # STEP 2: Try to credit NEW Main Wallet
            # ============================================
            if WALLET_SERVICE_AVAILABLE:
                try:
                    GoalsIntegrationService.receive_from_goals(
                        user=request.user,
                        amount=Fv_after_tax,
                        goal_type='group_goal',
                        goal_id=goal_info.id,
                        goal_reference=f"group-withdraw-{goal_info.id}-{timezone.now().timestamp()}"
                    )
                    print('✅ Amount credited via NEW Main Wallet')
                    logger.info(f"Group goal withdrawal: {Fv_after_tax} for goal {goal_info.id}")
                except Exception as e:
                    print(f'⚠️ New wallet credit failed: {str(e)}')
                    logger.warning(f"Failed to credit new wallet from group goal: {str(e)}")
                    # Old wallet already credited, so continue

            # Send notifications to creator
            phone_data_allpending = Profile.objects.get(owner=goal_info.creator)
            send_sms(phone_data_allpending.phone, 'Congratulation',
                     'We receive withdraw request for goal title ' + str(goal_info.goal_name) + 
                     ' of amount Kshs: ' + str(goal_info.achieved_amount) + 
                     ' We are processing the transaction, and you will receive a confirmation once it is successfully completed.')

            search_str = UserFcmTokens.objects.filter(user=user).order_by('-token')[:1]
            send_notif(search_str, None, True, True, "Congratulation",
                       'We receive withdraw request for goal title ' + str(goal_info.goal_name) + 
                       ' of amount ' + str(goal_info.achieved_amount) + 
                       ' We are processing the transaction, and you will receive a confirmation once it is successfully completed.',
                       None, False,
                       user)
            
            # Notify all members
            x = GroupGoalMember.objects.filter(group_goal=goal_info)
            for item in x:
                phone_data_allpending = Profile.objects.get(owner=item.user)
                send_sms(phone_data_allpending.phone, 'Congratulation',
                         str(goal_info.creator.first_name) + ' You have submitted a withdrawal request for the goal  ' + 
                         str(goal_info.goal_name) + ' Your available balance on My Account has been updated.')

                search_str = UserFcmTokens.objects.filter(user=item.user).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Congratulation",
                           str(goal_info.creator.username) + ' You have submitted a withdrawal request for the goal ' + 
                           str(goal_info.goal_name) + ' Your available balance on My Account has been updated.',
                           None, False,
                           user)

            # Reset goal
            goal_info.goal_profit = 0.0
            goal_info.achieved_amount = 0.0
            goal_info.is_active = 'No'
            goal_info.save()

            response = {'success': '1'}
            print('Response being returning is from group goal withdrawal request:', response)
            return JsonResponse(response)
        else:
            response = {'success': '0'}
            print('Response being returning is from group goal withdrawal request:', response)
            return JsonResponse(response)

def delete_goal(request):
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        print('Goal id inside withdraw request:', goal_id)
        user = User.objects.get(username=request.user)
        goal_info = Goal.objects.get(pk=goal_id)
        goal_info.delete()
        response = {'success': '1'}
        print('Goal deleted Now:', response)
        return JsonResponse(response)
def edit_goal(request):
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        goal_title = request.POST.get('goal_title')


        goal_info = Goal.objects.get(pk=goal_id)
        goal_info.name=goal_title
        goal_info.save()


        return redirect('goal_details', goal_id)
def edit_group_goal(request):
    if request.method == 'POST':
        goal_id = request.POST.get('goal_id')
        goal_title = request.POST.get('goal_title')


        goal_info = GroupGoal.objects.get(pk=goal_id)
        goal_info.goal_name=goal_title
        goal_info.save()


        return redirect('group_goal_details', goal_id)

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
                print('Line no 777',group_goal_info,receiver_profile)




                invitation_message = (
                    f'You have been invited by {request.user.first_name} {request.user.last_name} '
                    f'to join a group goal titled {group_goal_info.goal_name}. '
                    f'<a  href="{ref_url}">Click here to join now</a>.'
                )

                send_sms(receiver_profile.phone, 'Invitation',
                         invitation_message)

                search_str = UserFcmTokens.objects.filter(user=receiver_profile.owner).order_by('-token')[:1]
                send_notif(search_str, None, True, True, "Invitation",
                           invitation_message,
                           None, False,
                           receiver_profile.owner)
                print('Invitation sent to a chamaspace user on his account')

                response = {'success': '1'}

                return JsonResponse(response)
            else:

                invitation_message2 = (
                    f'You have been invited by {request.user.first_name} {request.user.last_name} '
                    f'to join a group goal titled {group_goal_info.goal_name}. '
                    f'If you don\'t have an account yet, please visit www.chamaspace.com to create an account. '
                    f'After creating an account, click the following link to join the invited group: {ref_url}. '
                    f'(Note: this link is only active after you have an account on www.chamaspace.com)'
                )

                send_sms(Phone_no, 'Invitation',
                         invitation_message2)
                print('Invitation sent to a non user on his phone')

                response = {'success': '1'}

                return JsonResponse(response)
        except Exception as e:
            print('Exception in invitation sending:', e)

            response = {'success': '0'}
            print('Response being returning is:', response)
            return JsonResponse(response)





