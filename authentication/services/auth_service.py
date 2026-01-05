import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from .otp_service import OTPService
from .password_service import PasswordService
from .account_service import AccountService

class AuthManager:
    @staticmethod
    def login_view(request):
        if request.method == 'POST':
            Username = request.POST.get('un')
            Password = request.POST.get('password')
            profile = OTPService.get_profile_by_nic(Username)
            if profile is None:
                messages.error(request, 'User with this ID No. not found!')
                return render(request, 'Login.html')
            user = authenticate(username=Username, password=Password)
            if user and user.is_active:
                login(request, user)
                return redirect('user_dashboard:home')
            messages.error(request, 'Invalid credentials or account inactive')
            return redirect('Login')
        return render(request, 'Login.html')

    @staticmethod
    def initiate_token_login(request):
        if request.method == 'POST':
            search_str = json.loads(request.body).get('searchText')
            request.session['search_str'] = search_str
            return redirect('login_otp')
        return redirect('Login')

    @staticmethod
    def token_login(request):
        return OTPService.verify_login_otp(request)

    @staticmethod
    def signup(request):
        return OTPService.handle_signup(request)

    @staticmethod
    def complete_signup(request):
        return OTPService.verify_signup_otp(request)

    @staticmethod
    def signup_step2(request):
        username = request.session.get('mobile')
        from authentication.models import Gender, Payment_Method, How_did_you_find, Profile
        from django.contrib.auth.models import User
        Genders = Gender.objects.all()
        Payment_Methods = Payment_Method.objects.all()
        How_did_you_finds = How_did_you_find.objects.all()
        context = {'Genders': Genders, 'Payment_Methods': Payment_Methods, 'How_did_you_finds': How_did_you_finds}
        if request.method == 'POST':
            users = User.objects.filter(username=username).first()
            if not users:
                messages.error(request, 'User does not exist, please Sign Up')
                return redirect('Sign_up')
            profile = Profile.objects.get(owner=users)
            users.email = request.POST.get('email')
            profile.gender = request.POST.get('Sex')
            profile.payment_method = request.POST.get('payment_gateway')
            profile.how_did_you_find = request.POST.get('how_find_us')
            users.is_active = True
            users.save()
            profile.save()
            messages.success(request, 'Account Created Successfully')
            return redirect('Login')
        return render(request, 'Sign_Up2.html', context)

    @staticmethod
    def logout_view(request):
        logout(request)
        messages.info(request, 'You have been Logged Out')
        return redirect('Login')