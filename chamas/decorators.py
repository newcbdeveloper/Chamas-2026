from django.shortcuts import render, redirect

from chamas.models import Chama
from subscriptions.models import ChamaSubscription


def is_user_chama_member(function):
    def wrap(request, *args, **kwargs):
        chama = Chama.objects.get(pk=kwargs['chama_id'])
        user = request.user
        if chama.member.filter(user=user).exists():
            try:
                subscription = ChamaSubscription.objects.filter(chama=chama).latest('end_date')
                if not subscription.is_active():
                    return redirect('subscription_chama', chama_id=kwargs['chama_id'])
            except Exception as e:
                print(e)
                pass
            return function(request, *args, **kwargs)
        else:
            return render(request, 'chamas/not_chama_member.html')
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


