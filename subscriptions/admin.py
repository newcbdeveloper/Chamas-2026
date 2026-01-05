from django.contrib import admin
from .models import *
admin.site.register(ChamaSubscription)
admin.site.register(PaymentDetail)

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'trial_duration', 'grace_period']
    search_fields = ['name']

@admin.register(Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ['name', 'rate']
    search_fields = ['name']