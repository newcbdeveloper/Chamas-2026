from django.db import models
from django.contrib.auth.models import User
from django.db.models import ExpressionWrapper, F, FloatField
from django.utils import timezone
from datetime import timedelta
from chamas.models import Chama

class PaymentDetail(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    mpesa_receipt_number = models.CharField(max_length=100, null=True)
    checkout_request_id = models.CharField(max_length=500, null=True)
    chama_subscription = models.ForeignKey("ChamaSubscription", on_delete=models.SET_NULL, blank=True, null=True)
    transaction_date = models.DateTimeField(null=True)
    phone_number = models.CharField(max_length=20, null=True)
    result_desc = models.CharField(max_length=255, null=True)
    payment_status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ], default='PENDING')
    possible_duplicate = models.BooleanField(default=False) 
class Tax(models.Model):
    name = models.CharField(max_length=100,blank=True,null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2,default=0.20, help_text="Tax rate as a percentage")

    def __str__(self):
        return f"{self.name} ({self.rate}%)"

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, default="Standard Plan")
    period_name = models.CharField(max_length=100, blank=True, null=True, default="year")
    price = models.DecimalField(max_digits=6, decimal_places=2, default=2000.00)
    trial_duration = models.DurationField(default=timedelta(days=14))
    period_duration = models.DurationField(default=timedelta(days=365))
    grace_period = models.DurationField(default=timedelta(days=2))
    taxes = models.ManyToManyField(Tax, related_name='subscription_plans_tax', blank=True)
    def __str__(self):
        return self.name

    def get_total_amount(self):
        plan_price = float(self.price)
        all_tax = float(0.0)
        taxes = self.taxes.all().annotate(tax_price=ExpressionWrapper(F('rate') * plan_price,
                                                                      output_field=FloatField()
                                                                      ))
        for tax in taxes:
            all_tax = all_tax + (plan_price * float(tax.rate))
        return plan_price + round(all_tax,0)

class ChamaSubscription(models.Model):
    chama = models.ForeignKey(Chama, on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    payment_details = models.ForeignKey(PaymentDetail, on_delete=models.SET_NULL,blank=True, null=True)
    phone = models.CharField(max_length=25, blank=True, null=True)

    def __str__(self):
        return f'{self.chama.name} - {self.plan.name} - {self.user.username if self.user else ""}'

    def is_active(self):
        now = timezone.now()
        return now < self.end_date + self.plan.grace_period

    def is_trial(self):
        now = timezone.now()
        return now < self.start_date + self.plan.trial_duration and (self.end_date - now).days < self.plan.trial_duration.days

    def remaining_trial_days(self):
        if self.is_trial():
            return (self.start_date + self.plan.trial_duration - timezone.now()).days
        return 0
