from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from chamas.models import ChamaMember

class AccountService:
    @staticmethod
    @login_required(login_url='/user/login/')
    def delete_account(request):
        user = request.user
        ChamaMember.objects.filter(user=user).update(user=None)
        user.delete()
        messages.success(request, 'We are sad to see you leave')
        return redirect('Sign_up')