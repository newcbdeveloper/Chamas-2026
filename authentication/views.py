from django.shortcuts import render, redirect
from django.http import HttpResponse
from .services.auth_service import AuthManager
from .services.password_service import PasswordService
from .services.firebase_service import FirebaseService
from .services.account_service import AccountService

# Auth views

def Login(request): return AuthManager.login_view(request)

def login_token(request): return AuthManager.initiate_token_login(request)

def login_otp(request): return AuthManager.token_login(request)

def Sign_Up(request): return AuthManager.signup(request)

# views.py or auth_service.py
def signup(request):
    if request.method == "GET":
        from chamas.models import How_did_you_find
        return render(request, 'Sign_up.html', {
            'How_did_you_finds': How_did_you_find.objects.all()
        })

    elif request.method == "POST":
        # Get ALL data at once
        nic_no = request.POST.get('nic_no')
        fname = request.POST.get('fname')
        lname = request.POST.get('lname')
        password = request.POST.get('password')
        phone_no = request.POST.get('phone_no')
        email = request.POST.get('email', '')
        how_find_us = request.POST.get('how_find_us', '')
        sex = request.POST.get('sex', '')

        # Validate
        if not all([nic_no, fname, lname, password, phone_no]):
            messages.error(request, "All required fields must be filled.")
            from chamas.models import How_did_you_find
            return render(request, 'Sign_up.html', {
                'How_did_you_finds': How_did_you_find.objects.all()
            })

        # Generate OTP
        import random
        otp = str(random.randint(100000, 999999))

        # Store in session
        request.session['signup_data'] = {
            'nic_no': nic_no,
            'fname': fname,
            'lname': lname,
            'password': password,
            'phone_no': phone_no,
            'email': email,
            'how_find_us': how_find_us,
            'sex': sex,
            'otp': otp
        }

        # TODO: send_otp(phone_no, otp)
        print(f"OTP: {otp} for {phone_no}")

        return redirect('verify_otp')

def verify_otp(request): return AuthManager.complete_signup(request)

def Logout(request): return AuthManager.logout_view(request)

# Password reset views

def forget_password(request): return PasswordService.forget_password(request)

def reset_password(request): return PasswordService.reset_password(request)

def update_password(request): return PasswordService.update_password(request)

# Firebase JS view

def showFirebaseJS(request): return FirebaseService.serve_firebase_js(request)

# Account deletion view

def delete_account(request): return AccountService.delete_account(request)
