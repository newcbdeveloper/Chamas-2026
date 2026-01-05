import datetime
from dateutil.relativedelta import relativedelta
import json

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

from .models import *


@login_required(login_url='Login')
def Dashboard(request):
    user_profile = Profile.objects.get(owner=request.user)

    user_active_chamas = Chamas.objects.filter(user_id=request.user, status='active')


    user_pending_chamas = Chamas.objects.filter(user_id=request.user, status='pending')
    p_to_p_wallet=Peer_to_Peer_Wallet.objects.get(user_id=user_profile.owner)
    saving_wallet=Saving_Wallet.objects.get(user_id=user_profile.owner)



    user_wallet = Wallet.objects.get(user_id=request.user)

    contribution_amount = contribution.objects.filter(user_id=request.user)
    Total_contribution=0
    for item in contribution_amount:
        Total_contribution += item.amount
        


    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]

    context = {'user_profile': user_profile,'user_notifications':user_notifications,'user_active_chamas':user_active_chamas,'user_pending_chamas':user_pending_chamas,'Total_contribution':Total_contribution,'user_wallet':user_wallet,'p_to_p_wallet':p_to_p_wallet,'saving_wallet':saving_wallet}
    return render(request, 'dashboard2.html', context)



@login_required(login_url='Login')
def all_notifications(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')

    context = {'user_profile': user_profile,'user_notifications':user_notifications}
    return render(request, 'all_notifications.html', context)





@login_required(login_url='Login')
def Setting(request):
    user = request.user
    user_profile = Profile.objects.get(owner=user)
    user_notifications = UserNotificationHistory.objects.filter(user=user).order_by('-created_at')[:6]

    if request.method == 'POST':
        # Get and clean form data
        fname = request.POST.get('firstname', '').strip()
        lname = request.POST.get('lastname', '').strip()
        email = request.POST.get('Email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()

        # Update only if field is not empty
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
        return redirect('Setting')

    context = {
        'user_profile': user_profile,
        'user_notifications': user_notifications
    }
    return render(request, 'settings.html', context)

@login_required(login_url='Login')
def setting_security(request):
    user_profile = Profile.objects.get(owner=request.user)
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()  # assuming you have this field

        if new_password and new_password == confirm_password:
            request.user.set_password(new_password)
            request.user.save()
            
            messages.success(request, 'Password updated successfully. Please login with your new password.')
            return redirect('Login')
        else:
            messages.error(request, 'Passwords do not match or are empty.')

    # This runs for GET requests (and failed POSTs)
    context = {'user_profile': user_profile}
    return render(request, 'settings-security.html', context)


@login_required(login_url='Login')
def joinchamas(request):
    no_chamas_members = chamas_members.objects.all()
    frequency_of_contribution = frequency_of_contri.objects.all()
    amount_per_contributions = amount_per_contribution.objects.all()
    no_of_cycles = no_of_cycle.objects.all()
    user_profile = Profile.objects.get(owner=request.user)

    joined_chamas = Chamas.objects.filter(active='No',status='joined')

    context = {'joined_chamas':joined_chamas,'no_chamas_members': no_chamas_members, 'frequency_of_contribution': frequency_of_contribution,
               'amount_per_contributions': amount_per_contributions, 'no_of_cycles': no_of_cycles,
               'user_profile': user_profile}
    
    if request.method == 'POST':
        Numbers_of_chamas_members = request.POST.get('Numbers_of_chamas_members')
        frequency = request.POST.get('frequency')
        frequencyforcategory = frequency[0]
        amount = request.POST.get('amount')

        contribution_turn = request.POST.get('contribution_turn')
        category = Numbers_of_chamas_members + frequencyforcategory + amount
        awardturnforchamastwo = int(Numbers_of_chamas_members) - int(contribution_turn)


        if not Category.objects.filter(name=category).exists():
            x = Category.objects.create(name=category,members=Numbers_of_chamas_members,frequency=frequency,amount=amount)
            x.save()
            print(category + 'saved successfully')

        cat = Category.objects.get(name=category)
        print('cat is',cat)

        members = Chamas.objects.filter(status='joined', category_id__name=cat.name)
        waiting_memebrs_list = []

        user = User.objects.get(username=request.user.username)
        if not Wallet.objects.filter(user_id=user_profile.owner).exists():

            Wallet.objects.create(user_id=user_profile.owner, available_for_withdraw=0.0,
                                  description='Wallet created on join chama request').save()
        x = Wallet.objects.get(user_id=request.user)

        if float(amount)*2 > x.available_for_withdraw:
            txt='You have not sufficent amount in your wallet to join this chama.Minimum KES '+ str(float(amount)*2) + ' amount must be in your wallet.Please Load money into your wallet first to proceed.'
            messages.warning(request, txt)
            return redirect('manage_chamas')
        else:


            if len(members) == 0:
                name = ''
                y = Chamas.objects.create(name=name, No_of_people=Numbers_of_chamas_members,
                                          frequency_of_contribution=frequency, contribution_turn=contribution_turn,
                                          status='joined', category_id=cat, active='No',amount=amount,Awarded='No',user_id=user,Award_turn=Numbers_of_chamas_members)

                y.save()
                Chamas.objects.filter(pk=y.id).update(name=str(y.category_id.name) + str(y.id))
                # joining chamas 2 code starts from here

                h = Chamas.objects.create(name=name, No_of_people=Numbers_of_chamas_members,
                                          frequency_of_contribution=frequency, contribution_turn=contribution_turn,
                                          status='joined', category_id=cat, active='No',amount=amount,Awarded='No',user_id=user,Award_turn=Numbers_of_chamas_members)

                h.save()
                Chamas.objects.filter(pk=h.id).update(name=str(h.category_id.name) + str(h.id))

                x.available_for_withdraw-=float(amount)*2
                #add transaction record also here
                x.save()
                messages.success(request,'You have successfully joined chamas. We will notify you when chama starts')
                return redirect('manage_chamas')
            else:

                for item in members:
                    waiting_memebrs_list.append(item.name)
                    print('List for chamas names:', waiting_memebrs_list)

                chamas_one_name = waiting_memebrs_list[-1]
                chamas_two_name = waiting_memebrs_list[-2]

                print('Chamas one name is:', chamas_one_name)
                print('Chamas two name is:', chamas_two_name)

                if len(members) == ((int(Numbers_of_chamas_members) * 2) - 2):

                    geting_award_turn_of_all_users_one = Chamas.objects.filter(status='joined', name=chamas_one_name)
                    geting_award_turn_of_all_users_two = Chamas.objects.filter(status='joined', name=chamas_two_name)
                    award_turn_of_all_users_one = []
                    award_turn_of_all_users_two = []

                    for x in geting_award_turn_of_all_users_one:
                        award_turn_of_all_users_one.append(int(x.Award_turn))

                    print('line 259 award turn of all user chama one is=', award_turn_of_all_users_one)
                    for x in geting_award_turn_of_all_users_two:
                        award_turn_of_all_users_two.append(int(x.Award_turn))
                    print('line 259 award turn of all user chama two is=', award_turn_of_all_users_two)

                    missing_awardturns_chama_one = list(
                        set(range(max(award_turn_of_all_users_one) + 1)) - set(award_turn_of_all_users_one))
                    missing_awardturns_chama_two = list(
                        set(range(max(award_turn_of_all_users_two) + 1)) - set(award_turn_of_all_users_two))

                    print('missing award turn for chama one is=', missing_awardturns_chama_one)
                    print('missing award turn for chama two is=', missing_awardturns_chama_two)
                    if missing_awardturns_chama_one[0] > 0:
                        award_turn_for_chama_one = missing_awardturns_chama_one[0]
                    else:
                        award_turn_for_chama_one = missing_awardturns_chama_one[1]
                    print('Award turn assing for chama One=', award_turn_for_chama_one)

                    award_turn_for_chama_two = missing_awardturns_chama_two[-1] - missing_awardturns_chama_two[0]
                    print('Award turn assing for chama Two=', award_turn_for_chama_two)

                    # Setting of award turn ends here
                    end_date = datetime.date.today()
                    contribution_date = datetime.date.today()

                    if frequency == 'Monthly':
                        end_date = datetime.date.today() + relativedelta(months=int(Numbers_of_chamas_members))
                        contribution_date = datetime.date.today() + relativedelta(months=1)
                    if frequency == 'Weekly':
                        end_date = datetime.date.today() + relativedelta(weeks=int(Numbers_of_chamas_members))
                        contribution_date = datetime.date.today() + relativedelta(weeks=1)
                    if frequency == 'Bi-Weekly':
                        end_date = datetime.date.today() + relativedelta(days=14 * int(Numbers_of_chamas_members))
                        contribution_date = datetime.date.today() + relativedelta(days=14)

                    y = Chamas.objects.create(name=chamas_one_name, No_of_people=Numbers_of_chamas_members,
                                              frequency_of_contribution=frequency, contribution_turn=contribution_turn,
                                              status='active', category_id=cat, active='Yes', amount=amount,
                                              Awarded='No', user_id=user, Award_turn=award_turn_for_chama_one,start_date = datetime.date.today(),end_date=end_date,contribution_date=contribution_date)

                    y.save()

                    # code to join chamas 2 starts from here
                    q = Chamas.objects.create(name=chamas_two_name, No_of_people=Numbers_of_chamas_members,
                                              frequency_of_contribution=frequency, contribution_turn=contribution_turn,
                                              status='active', category_id=cat, active='Yes', amount=amount,
                                              Awarded='No', user_id=user, Award_turn=award_turn_for_chama_two,start_date = datetime.date.today(),end_date=end_date,contribution_date=contribution_date)

                    q.save()
                    x = Wallet.objects.get(user_id=request.user)
                    x.available_for_withdraw -= float(amount) * 2

                    # add transaction record also here
                    x.save()

                    phone_data_of_current_user = Profile.objects.get(owner=request.user)

                    #sending sms and notification to the user
                    send_sms(phone_data_of_current_user.phone, 'Important Alert','Congratulation your chama is starts now')
                    search_str = UserFcmTokens.objects.filter(user=request.user).order_by('-token')[:1]
                    send_notif(search_str, None, True, True, "Congratulation",
                               "Your chama starts now, please check My Chamas",
                               None, False,
                               request.user)

                    for item in members:

                        item.status = 'active'

                        item.start_date = datetime.date.today()
                        item.active = 'Yes'

                        item.end_date = end_date
                        item.contribution_date = contribution_date


                        item.save()

                        phone_data_allpending = Profile.objects.get(owner=item.user_id)
                        send_sms(phone_data_allpending.phone, 'Congratulation',
                                 'Your chamas started Now, please check My Chamas ')
                        search_str = UserFcmTokens.objects.filter(user=item.user_id).order_by('-token')[:1]
                        send_notif(search_str, None, True, True, "Congratulation",
                                   "Your chamas started Now, please check My Chamas",
                                   None, False,
                                   item.user_id)

                    messages.warning(request, 'Congratulations, You joined chamas')
                    return redirect('manage_chamas')
                else:
                    #setting award turn code starts from here
                    geting_award_turn_of_all_users_one = Chamas.objects.filter(status='joined', name=chamas_one_name)
                    geting_award_turn_of_all_users_two = Chamas.objects.filter(status='joined', name=chamas_two_name)
                    award_turn_of_all_users_one=[]
                    award_turn_of_all_users_two=[]

                    for x in geting_award_turn_of_all_users_one:
                        award_turn_of_all_users_one.append(int(x.Award_turn))

                    print('line 259 award turn of all user chama one is=',award_turn_of_all_users_one)
                    for x in geting_award_turn_of_all_users_two:
                        award_turn_of_all_users_two.append(int(x.Award_turn))
                    print('line 259 award turn of all user chama two is=',award_turn_of_all_users_two)

                    missing_awardturns_chama_one = list(set(range(max(award_turn_of_all_users_one) + 1)) - set(award_turn_of_all_users_one))
                    missing_awardturns_chama_two = list(set(range(max(award_turn_of_all_users_two) + 1)) - set(award_turn_of_all_users_two))

                    print('missing award turn for chama one is=',missing_awardturns_chama_one)
                    print('missing award turn for chama two is=',missing_awardturns_chama_two)
                    if missing_awardturns_chama_one[0]>0:
                        award_turn_for_chama_one=missing_awardturns_chama_one[0]
                    else:
                        award_turn_for_chama_one = missing_awardturns_chama_one[1]
                    print('Award turn assing for chama One=',award_turn_for_chama_one)

                    award_turn_for_chama_two=missing_awardturns_chama_two[-1]-missing_awardturns_chama_two[0]
                    print('Award turn assing for chama Two=', award_turn_for_chama_two)

                    #Setting of award turn ends here



                    y = Chamas.objects.create(name=chamas_one_name, No_of_people=Numbers_of_chamas_members,
                                              frequency_of_contribution=frequency, contribution_turn=contribution_turn,
                                              status='joined', category_id=cat, active='No',amount=amount,Awarded='No',user_id=user,Award_turn=award_turn_for_chama_one)

                    y.save()



                    # code to join chamas 2 starts from here
                    q = Chamas.objects.create(name=chamas_two_name, No_of_people=Numbers_of_chamas_members,
                                              frequency_of_contribution=frequency, contribution_turn=contribution_turn,
                                              status='joined', category_id=cat, active='No',amount=amount,Awarded='No',user_id=user,Award_turn=award_turn_for_chama_two)

                    q.save()
                    x = Wallet.objects.get(user_id=request.user)
                    x.available_for_withdraw-= float(amount)*2

                    # add transaction record also here
                    x.save()


                    messages.success(request, 'You have successfully joined chamas. We will notify you when chama starts')
                    return redirect('manage_chamas')


    return render(request, 'join-chama.html', context)

@login_required(login_url='Login')
def mychamas(request):
    pre_reg=Chamas.objects.filter(user_id=request.user)
    user_profile = Profile.objects.get(owner=request.user)
    user_active_chamas = Chamas.objects.filter(user_id=request.user, status='active')

    context = {'user_profile': user_profile,'pre_reg':pre_reg,'user_active_chamas':user_active_chamas}
    return render(request, 'my-chamas.html', context)

@login_required(login_url='Login')
def manage_chamas(request: object):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]
    user_wallet = Wallet.objects.get(user_id=request.user)

    # context = {'user_profile': user_profile, 'user_notifications': user_notifications}


    user_active_chamas = Chamas.objects.filter(user_id=request.user, status='active')
    contribution_amount = contribution.objects.filter(user_id=request.user)
    Total_contribution = 0
    for item in contribution_amount:
        Total_contribution += item.amount

    context = {'user_profile': user_profile, 'user_notifications': user_notifications,'user_active_chamas':user_active_chamas,'Total_contribution':Total_contribution,'user_wallet':user_wallet}
    return render(request, 'manage_chamas.html', context)

@login_required(login_url='Login')
def payment_paypal(request):
    user_profile = Profile.objects.get(owner=request.user)
    user_notifications = UserNotificationHistory.objects.filter(user=request.user).order_by('-created_at')[:6]

    context = {'user_profile': user_profile, 'user_notifications': user_notifications}
    if request.method == 'POST':


        user_active_chamas = request.POST.get('user_active_chamas')
        print('user active chamas name',user_active_chamas)
        if user_active_chamas =='Select':
            print('line no 312 insiede if')
        chamas_data = Chamas.objects.get(name=user_active_chamas, user_id=request.user)


        context={'chamas_data':chamas_data,'user_profile': user_profile, 'user_notifications': user_notifications}
        return render(request, 'paypal.html', context)

    return render(request, 'paypal.html',context)



def paypal_payment_success(request):
    if request.method == 'POST':
        try:
            chamas_name = request.POST.get('name')
            print('line no 422 ', chamas_name)


            chamas_data=Chamas.objects.get(name=chamas_name,user_id=request.user)
            x = Wallet.objects.get(user_id=request.user)

            if float(chamas_data.amount) < x.available_for_withdraw:
                x.available_for_withdraw -= float(chamas_data.amount)
                x.save()


                y=contribution.objects.create(chamas_id=chamas_data,user_id=request.user,amount=chamas_data.amount)
                y.save()
                z = Transection.objects.create(chamas_id=chamas_data, user_id=request.user, amount=chamas_data.amount)
                z.save()


                messages.warning(request, 'Contribution added successfully.')
                return redirect('Dashboard')
            else:
                messages.warning(request, 'You have not sufficent amount in your wallet to pay this chama contribution')
                return redirect('manage_chamas')



        except Exception as e:
            print(e)
            messages.warning(request, 'Payment could not proceed successfuly')
            return redirect('manage_chamas')



@login_required(login_url='Login')
def stats_page1(request):
    user_profile = Profile.objects.get(owner=request.user)
    category = Category.objects.all()
    count_list = []

    for item in category:
        data_dict = {}
        waiting_members = Chamas.objects.filter(category_id=item.id, status='waiting').count()
        pending_members = Chamas.objects.filter(category_id=item.id, status='pending').count()
        joined_members = Chamas.objects.filter(category_id=item.id, status='active').count()

        data_dict['pending_members'] = pending_members
        data_dict['waiting_members'] = waiting_members
        data_dict['joined_members'] = joined_members
        data_dict['category_name'] = item.name
        count_list.append(data_dict)

    # print(count_list)

    context = {'user_profile': user_profile, 'category': category, 'count_list': count_list}

    return render(request, 'stats_page1.html', context)

@login_required(login_url='Login')
def stats_page_2(request, category_name):
    user_profile = Profile.objects.get(owner=request.user)

    final_list = []
    l = Chamas.objects.filter(category_id__name=category_name, status='waiting')
    m = Chamas.objects.filter(category_id__name=category_name, status='pending')
    n = Chamas.objects.filter(category_id__name=category_name, status='active')
    print('active chamas',n)
    for item in n:
        data = {}
        data["active"] = item
        final_list.append(data)
    if len(m) > len(l):
        for i in m:
            data = {}
            data["pending"] = i
            final_list.append(data)
        for i in range(len(l)):
            final_list[i]["waiting"] = l[i]
        print(final_list)
    else:
        for i in l:
            data = {}
            data["waiting"] = i
            final_list.append(data)
        for i in range(len(m)):
            final_list[i]["waiting"] = m[i]


    context = {'user_profile': user_profile, 'final_result': final_list}
    return render(request, 'stats_page2.html', context)


@login_required(login_url='Login')
def stats_page_3(request, category_name):
    user_profile = Profile.objects.get(owner=request.user)
    joined = Chamas.objects.filter(name=category_name, status='joined')


    context = {'user_profile': user_profile, 'final_result': joined}
    return render(request, 'stats_page3.html', context)
