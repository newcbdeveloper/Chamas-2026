# payment_integration/views.py

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
import requests
from requests.auth import HTTPBasicAuth
import json
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
#from Dashboard.models import *
from notifications.models import UserNotificationHistory
from .models import *
from twilio.rest import Client
from django.conf import settings
from authentication.models import *
from .mpesa_credentials import MpesaAccessToken, LipanaMpesaPpassword, get_mpesa_access_token
from decimal import Decimal  # <--- ADD THIS IMPORT
import logging  # <--- ADD THIS IMPORT

logger = logging.getLogger(__name__)  # <--- ADD THIS LINE


def send_mpesa_success_sms(mobile, body):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # response = client.messages.create( body=body,to=mobile, from_=settings.TWILIO_PHONE_NUMBER)
    return None


def getAccessToken(request):
    consumer_key = 'yHXpR8eVq0HWdaft5QgNCDjjfYklT3HX'
    consumer_secret = '3awmu3uigWx5ATnH'
    api_URL = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'

    r = requests.get(api_URL, auth=HTTPBasicAuth(consumer_key, consumer_secret))
    mpesa_access_token = json.loads(r.text)
    validated_mpesa_access_token = mpesa_access_token['access_token']

    return HttpResponse(validated_mpesa_access_token)


def lipa_na_mpesa_online(request):
    x = Profile.objects.get(owner=request.user)
    context = {'phone_number': x.phone}
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        Phone_no_input = x.phone
        without_plus_cellno = Phone_no_input[1:]

        print('Line no 47 without plus cell no is:', without_plus_cellno)

        phone = int(''.join(filter(str.isdigit, without_plus_cellno)))

        access_token = get_mpesa_access_token()
        api_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        headers = {"Authorization": "Bearer %s" % access_token}
        request_data = {
            "BusinessShortCode": LipanaMpesaPpassword.Business_short_code,
            "Password": LipanaMpesaPpassword.decode_password,
            "Timestamp": LipanaMpesaPpassword.lipa_time,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": LipanaMpesaPpassword.Business_short_code,
            "PhoneNumber": phone,
            "CallBackURL": LipanaMpesaPpassword.callback_url,
            "AccountReference": "chamabora",
            "TransactionDesc": "chamabora stk push"
        }

        try:
            response = requests.post(api_url, json=request_data, headers=headers)
            data = response.json()
            print('value of data is:', data)
            if data['ResponseCode'] == "0":
                return redirect('stk_push_success')
            else:
                print('Failed:', data)
                return redirect('stk_push_fail')
        except Exception as e:
            print('STKPush Error:', e)
            return redirect('stk_push_fail')
            
    return render(request, 'add no.html', context)


def stk_push_success(request):
    x = Profile.objects.get(owner=request.user)
    context = {'phone_number': x.phone}
    return render(request, 'stk_push_success.html', context)


def stk_push_fail(request):
    x = Profile.objects.get(owner=request.user)
    context = {'phone_number': x.phone}
    return render(request, 'stk_push_fail.html', context)


@csrf_exempt
def callback(request):
    """
    M-Pesa callback function - Updated to support DUAL WALLET SYSTEM
    Updates both OLD wallet (Dashboard.models.Wallet) and NEW wallet (wallet.models.MainWallet)
    """
    mpesa_body = request.body.decode('utf-8')

    j = json.loads(mpesa_body)
    merchant_id = j['Body']['stkCallback']['MerchantRequestID']
    checkout_id = j['Body']['stkCallback']['CheckoutRequestID']
    result_code = j['Body']['stkCallback']['ResultCode']
    pay_amount = j['Body']['stkCallback']['CallbackMetadata']['Item'][0]['Value']
    phone = j['Body']['stkCallback']['CallbackMetadata']['Item'][4]['Value']
    Date = j['Body']['stkCallback']['CallbackMetadata']['Item'][3]['Value']
    
    print('value of data after json set at line 105 callback url', merchant_id, checkout_id, result_code, pay_amount, Date, phone)
    
    phone_number = '+' + str(phone)
    print('Phone number line 101 is:', phone_number)

    # Save M-Pesa body for debugging
    mpesa_body_test.objects.create(body=mpesa_body, description='Saved via callback url').save()
    
    body = 'You successfully deposit ' + str(pay_amount) + ' ksh into your ChamaSpace Wallet and your transaction id is ' + str(merchant_id)

    print('Line no 106 called')
    send_mpesa_success_sms(phone_number, body)

    print('Line no 108 called', result_code)
    
    if result_code == 0:
        if not Mpesa_deposit_details.objects.filter(merchant_id=merchant_id).exists():
            print('Line no 111 called')

            # Save M-Pesa deposit details
            Mpesa_deposit_details.objects.create(
                merchant_id=merchant_id,
                checkout_id=checkout_id,
                result_code=result_code,
                pay_amount=pay_amount,
                phone=phone_number
            ).save()
            
            # Get user profile
            user_profile = Profile.objects.get(phone=phone_number)
            print('Line no 117 called - User profile found:', user_profile.owner.username)
            
            # ============================================
            # STEP 1: UPDATE OLD WALLET (For backwards compatibility)
            # ============================================
            if not Wallet.objects.filter(user_id=user_profile.owner).exists():
                print('Line no 119: Creating OLD wallet')
                Wallet.objects.create(
                    user_id=user_profile.owner,
                    available_for_withdraw=pay_amount,
                    description='Deposit via Mpesa'
                ).save()
            else:
                print('Line no 123: Updating OLD wallet')
                obj = Wallet.objects.get(user_id=user_profile.owner)
                obj.available_for_withdraw += int(pay_amount)
                print('Line no 127: Old wallet balance updated to', obj.available_for_withdraw)
                obj.description = 'Deposit via Mpesa'
                obj.save()

            # ============================================
            # STEP 2: UPDATE NEW MAIN WALLET
            # ============================================
            try:
                from wallet.services import MpesaIntegrationService
                
                print('Line no 135: Processing deposit to NEW Main Wallet')
                
                MpesaIntegrationService.process_mpesa_deposit(
                    user=user_profile.owner,
                    amount=Decimal(str(pay_amount)),
                    mpesa_receipt=merchant_id,
                    phone_number=phone_number
                )
                
                print('Line no 140: ✅ NEW Main Wallet updated successfully')
                logger.info(f"M-Pesa deposit processed: {merchant_id} for user {user_profile.owner.username}")
                
            except ImportError as ie:
                # Wallet app not yet migrated - this is OK during transition
                print(f'Line no 145: ⚠️ New wallet app not migrated yet: {str(ie)}')
                logger.warning(f"New wallet not ready (migrations pending): {str(ie)}")
                
            except Exception as e:
                # Other errors - log but don't fail the callback
                print(f'Line no 150: ❌ Error updating new wallet: {str(e)}')
                logger.error(f"Failed to update new wallet for {merchant_id}: {str(e)}")
                # Continue - old wallet still works
                
            # Create notification
            UserNotificationHistory.objects.create(
                user=user_profile.owner, 
                notification_title='You successfully deposit ' + str(pay_amount), 
                notification_body=body
            )
            
            print('Line no 160: Callback processing completed')
        else:
            print('Line no 162: Duplicate transaction detected, skipping')
            pass
    else:
        # Failed transaction
        body = 'You did not successfully deposit ' + str(pay_amount) + ' .shell into your Chama Wallet. Please try again.'
        print('Line no 166: Transaction failed')
        send_mpesa_success_sms(phone_number, body)

    return HttpResponse("success")


@csrf_exempt
def register_urls(request):
    access_token = get_mpesa_access_token()
    api_url = "https://api.safaricom.co.ke/mpesa/c2b/v2/registerurl"
    headers = {"Authorization": "Bearer %s" % access_token}
    options = {
        "ShortCode": LipanaMpesaPpassword.Business_short_code,
        "ResponseType": "Completed",
        "ConfirmationURL": "https://chamaspace.com/load_money/confirmation",
        "ValidationURL": "https://chamaspace.com/load_money/validation"
    }
    response = requests.post(api_url, json=options, headers=headers)
    return HttpResponse(response.text)


@csrf_exempt
def validation(request):
    context = {
        "ResultCode": 0,
        "ResultDesc": "Accepted"
    }
    return JsonResponse(dict(context))


@csrf_exempt
def confirmation(request):
    mpesa_body = request.body.decode('utf-8')
    mpesa_body_test.objects.create(body=mpesa_body, description='Saved via Confirmation url').save()
    merchant_id = mpesa_body["Body"]["stkCallback"]["MerchantRequestID"]
    checkout_id = mpesa_body["Body"]["stkCallback"]["CheckoutRequestID"]
    result_code = mpesa_body["Body"]["stkCallback"]["ResultCode"]
    pay_amount = mpesa_body["Body"]["stkCallback"]["CallbackMetadata"]["Item"][0]["Value"]
    phone = mpesa_body["Body"]["stkCallback"]["CallbackMetadata"]["Item"][4]["Value"]
    Date = mpesa_body["Body"]["stkCallback"]["CallbackMetadata"]["Item"][3]["Value"]
    
    body = 'You successfully deposit ' + '' + pay_amount + 'Ksh into your ChamaSpace Wallet and your transaction id is' + merchant_id
    phone_number = '+' + phone
    send_mpesa_success_sms(phone_number, body)

    return HttpResponse("success")


def test_mpesa_body(request):
    mpesa_body = request.body.decode('utf-8')
    j = json.loads(mpesa_body)
    merchant_id = j['Body']['stkCallback']['MerchantRequestID']
    checkout_id = j['Body']['stkCallback']['CheckoutRequestID']
    result_code = j['Body']['stkCallback']['ResultCode']
    pay_amount = j['Body']['stkCallback']['CallbackMetadata']['Item'][0]['Value']
    phone = j['Body']['stkCallback']['CallbackMetadata']['Item'][4]['Value']
    Date = j['Body']['stkCallback']['CallbackMetadata']['Item'][3]['Value']
    
    print('value of data after json set,', merchant_id, checkout_id, result_code, pay_amount, Date, phone)

    phone_number = '+' + str(phone)
    print('Line no 195 value of phone_number is:', phone_number)

    user_profile = Profile.objects.get(phone=phone_number)
    Phone_no_input = user_profile.phone
    without_zero_cellno = Phone_no_input[1:]
    phone123 = int(without_zero_cellno)
    print('Line no 205', phone123)

    obj = Wallet.objects.get(user_id=user_profile.owner)
    print('Line no 199', obj.available_for_withdraw, obj.description)

    return None