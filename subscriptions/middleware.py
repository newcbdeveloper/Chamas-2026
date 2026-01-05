from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from .models import SubscriptionPlan, ChamaSubscription
from chamas.models import Chama

from .utils import get_chama_id
import re

class SubscriptionMiddleware(MiddlewareMixin):

    def get_currect_subscription(self, chama, plan):
        chama_subscription = None
        try:
            chama_subscription = ChamaSubscription.objects.filter(
                chama=chama,
                plan=plan
            ).latest('id')
        except ChamaSubscription.DoesNotExist:
            chama_subscription = None  
        return chama_subscription

    def process_request(self, request):
        if request.method != 'GET':
            return

        if not request.user.is_authenticated:
            return
        
        unrestricted_paths = {
            '/subscriptions/plans/',
            '/subscriptions/subscribe/',
            '/subscriptions/success/',
        }

        if request.path in unrestricted_paths:
            return
        
        restricted_pattern = re.compile(r'^/chamas-bookeeping/[^/]+/\d+/$')
        unrestricted_dashboard_pattern = re.compile(r'^/chamas-bookeeping/chama-dashboard/\d+/$')

        if not restricted_pattern.match(request.path) or unrestricted_dashboard_pattern.match(request.path):
            return
        
        chama_id = get_chama_id(request)
        print("get_chama_id")
        print(chama_id)

        chama = Chama.objects.get(id=chama_id)
        plan = SubscriptionPlan.objects.first()

        chamasubscription = self.get_currect_subscription(chama, plan)
        print(chamasubscription)
        
        if chama and chamasubscription and chamasubscription.is_active():
            return
        
        request.session['chama_id'] = chama_id

        return redirect(reverse('subscription_plans'))


