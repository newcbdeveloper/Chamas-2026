import random
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from .otp_service import OTPService

class PasswordService:
    @staticmethod
    def forget_password(request):
        if request.method == 'POST':
            username = request.POST.get('un')
            profile = OTPService.get_profile_by_nic(username)
            if not profile:
                messages.error(request, 'User not found with this NIC')
                return render(request, 'forget-password.html')
            otp = str(random.randint(1000, 9999))
            if OTPService.send_otp(profile.phone, otp) == '200':
                request.session.update({'otp': otp, 'mobile': profile.phone, 'Username': username})
                return redirect('reset_password')
            messages.error(request, 'Failed to send verification code')
        return render(request, 'forget-password.html')

    @staticmethod
    def reset_password(request):
        otp = request.session.get('otp')
        if request.method == 'POST':
            if request.POST.get('2facode') == otp:
                return redirect('update_password')
            messages.error(request, 'Invalid verification code')
        return render(request, 'reset_password_otp.html')

    @staticmethod
    def update_password(request):
        username = request.session.get('Username')
        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            user = User.objects.get(username=username)
            user.set_password(new_password)
            user.save()
            messages.info(request, 'Password updated successfully')
            return redirect('Login')
        return render(request, 'update_password.html')