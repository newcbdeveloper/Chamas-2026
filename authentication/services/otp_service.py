import random
import json
import http.client
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from notifications.models import UserFcmTokens
from notifications.utils import send_notif
from authentication.models import Profile
from pyment_withdraw.models import UserBankDetails
from django.db import transaction
from wallet.services import WalletService  # NEW: Import new wallet service

from django.contrib import messages
from django.contrib.auth.models import User
from authentication.models import Profile

class OTPService:
    @staticmethod
    def send_otp(mobile, otp):
        try:
            if mobile.startswith('+'):
                mobile = mobile[1:]
            base_url = settings.INFOBIP_API_BASE_URL
            endpoint = "/whatsapp/1/message/template"
            headers = {
                "Authorization": f"App {settings.INFOBIP_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "messages": [{
                    "from": "254791638574",
                    "to": mobile,
                    "content": {
                        "templateName": "chamaspace_template",
                        "templateData": {"body": {"placeholders": [otp]}, "buttons": [{"type": "URL", "parameter": otp}]},
                        "language": "en_GB"
                    }
                }]
            }
            conn = http.client.HTTPSConnection(base_url)
            conn.request("POST", endpoint, json.dumps(payload), headers)
            response = conn.getresponse()
            data = response.read()
            if response.status == 200:
                resp = json.loads(data.decode())
                status = resp.get("messages", [{}])[0].get("status", {}).get("groupName")
                return "200" if status in ("DELIVERED", "PENDING") else "500"
            return "500"
        except Exception:
            return "500"

    @staticmethod
    def get_profile_by_nic(nic):
        return Profile.objects.filter(NIC_No=nic).first()

    @staticmethod
    def handle_signup(request):
        if request.method == 'POST':
            nic = request.POST.get('nic_no')
            fname = request.POST.get('fname')
            lname = request.POST.get('lname')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            password = request.POST.get('password')
            referral = request.POST.get('referral_code', '')

            if not all([nic, fname, lname, email, phone, password]):
                messages.error(request, 'All fields are required')
                return redirect('Sign_up')

            if User.objects.filter(username=nic).exists():
                messages.error(request, 'Account with this NIC already exists')
                return redirect('Sign_up')

            if Profile.objects.filter(phone=phone).exists():
                messages.error(request, 'Account with this phone already exists')
                return redirect('Sign_up')

            otp = str(random.randint(1000, 9999))
            status = OTPService.send_otp(phone, otp)
            if status != "200":
                messages.error(request, 'Failed to send OTP. Please try again.')
                return redirect('Sign_up')

            request.session['signup_data'] = {
                'nic': nic,
                'fname': fname,
                'lname': lname,
                'email': email,
                'phone': phone,
                'password': password,
                'referral': referral,
                'otp': otp
            }
            return redirect('verify_signup_otp')

        return render(request, 'Sign_up.html')

    @staticmethod
    def verify_signup_otp(request):
        if request.method == 'POST':
            user_otp = request.POST.get('otp')
            data = request.session.get('signup_data')
            if not data:
                messages.error(request, 'Session expired')
                return redirect('Sign_up')
            if user_otp == data['otp']:
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(
                            first_name=data['fname'],
                            last_name=data['lname'],
                            username=data['nic'],
                            email=data['email'],
                            password=data['password']
                        )
                        profile = Profile.objects.create(
                            owner=user,
                            NIC_No=data['nic'],
                            phone=data['phone'],
                            referral_code=data['referral']
                        )
                        # NEW: Create new MainWallet using service (replaces old Wallet)
                        WalletService.get_or_create_wallet(user)
                        
                        # Drop obsolete: No Peer_to_Peer_Wallet (not needed)
                        # Drop obsolete: No Saving_Wallet (handled by new wallet or MGR mini-wallet)
                        
                        # Keep this as-is
                        UserBankDetails.objects.create(user_id=user)
                except Exception as e:  # Broader catch for any creation issues
                    messages.error(request, 'Account creation failed. Please try again.')
                    return redirect('Sign_up')

                del request.session['signup_data']
                login(request, user)
                return redirect('Login')
            messages.error(request, 'Invalid OTP')
        return render(request, 'Verify_OTP.html')

    @staticmethod
    def verify_login_otp(request):
        if request.method == 'POST':
            otp = request.POST.get('2facode')
            mobile = request.session.get('mobile')
            data = request.session
            profile = Profile.objects.filter(phone=mobile).first()
            if otp == profile.otp:
                user = authenticate(username=data['Username'], password=data['Password'])
                login(request, user)
                token = data['search_str']
                send_notif(token, None, True, True, "Successfully Login", "Welcome!", None, False, user)
                UserFcmTokens.objects.create(user=user, token=token)
                return redirect('user_dashboard:home')
            messages.error(request, 'Invalid OTP')
        return render(request, 'Login_otp.html')