from datetime import date
from dateutil.relativedelta import relativedelta

from django.contrib.auth.models import User
from django.db import models

# Create your models here.
from django.utils.timezone import now

class Mpesa_deposit_details(models.Model):



    merchant_id = models.CharField(max_length=2000, null=True, blank=True,verbose_name='Merchant ID')
    checkout_id = models.CharField(max_length=2000, null=True, blank=True,verbose_name='Check Out ID')
    result_code = models.CharField(max_length=2000, null=True, blank=True,verbose_name='Result Code')
    pay_amount = models.FloatField(null=True, blank=True,verbose_name='Amount Paid')
    phone = models.CharField(max_length=2000, null=True, blank=True,verbose_name='Phone')

    inserted_on = models.DateField(default=now, null=True, blank=True)
    updated_on = models.DateField(default=now, null=True, blank=True)

    def __str__(self):
        return self.phone

    class Meta:
        verbose_name = 'Mpesa Transactions History'







from django.db import models

# Create your models here.
