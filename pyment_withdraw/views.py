from django.shortcuts import render, redirect

from .models import UserBankDetails,User,UserMoneyWithDrawalStatus
from notifications.models import UserFcmTokens
from notifications.utils import *
# Create your views here.
from authentication.models import *
#from Dashboard.models import *


# Create your views here.




def add_account(request):
    if request.method == "POST":
        iban = request.POST.get('iban')
        bank_name = request.POST.get('routing')
        swift_code = request.POST.get('swiftcode')
        branch_id = request.POST.get('branchID')
        account_no = request.POST.get('accountNO')
        bank_country = request.POST.get('bank_country', None)
        user = User.objects.get(username=request.user)
        print(iban,bank_name,swift_code,branch_id,account_no,bank_country,user)
        x=UserBankDetails.objects.create(
            iban=iban,
            bank_name=bank_name,
            swift_code=swift_code,
            branch_id=branch_id,
            account_no=account_no,
            bank_country=bank_country,
            user_id=user

        )
        x.save()
        return redirect('with_drawal_money')

    else:
        return render(request, 'add_bank_details.html')


def withdraw_money(request):
    user = User.objects.get(username=request.user)
    if UserBankDetails.objects.filter(user_id=user).exists():
        x=Wallet.objects.get(user_id=request.user)


        user_with_draw_amount =x.available_for_withdraw
        UserMoneyWithDrawalStatus.objects.create(
            withdrawal_amount=user_with_draw_amount,
            status = "Pending...User request For Withdraw money",
            user_id = user

        ).save()
        x.available_for_withdraw-=user_with_draw_amount
        x.pending_clearence=user_with_draw_amount
        x.save()
        phone_data_allpending = Profile.objects.get(owner=user)
        send_sms(phone_data_allpending.phone, 'Congratulation',
                 'Your payment withdraw request received, it will take 5 business working day to make transactional successfull ')
        print('sms sent to user for withdraw')
        search_str = UserFcmTokens.objects.filter(user=user).order_by('-token')[:1]
        send_notif(search_str, None, True, True, "Important Alert",
                   "Your payment withdraw request received, it will take 5 business working day to make transactional successfull",
                   None, False,
                   user)
        print('notitification sent to user for withdraw')

        # subtract balance from chamabora user account


        # redirect with success message
        return render(request, 'withdrawsuccess.html')


    else:

        return render(request, 'add_bank_details.html')

