from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
# Create your models here.
class UserBankDetails(models.Model):
    iban = models.CharField(max_length=50, null=True, blank=True)
    bank_name = models.CharField(max_length=50, null=True, blank=True)
    swift_code = models.CharField(max_length=50, null=True, blank=True)
    branch_id = models.CharField(max_length=50, null=True, blank=True)
    account_no = models.CharField(max_length=50, null=True, blank=True)
    bank_country = models.CharField(max_length=50, null=True, blank=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)


class UserMoneyWithDrawalStatus(models.Model):
    withdrawal_amount = models.CharField(max_length=50)
    Withdrawal_request_date=models.DateField(default=now, null=True, blank=True, db_column='Withdrawal_request_date')
    status = models.CharField(max_length=50, null=True, blank=True)
    withraw_for = models.CharField(max_length=50, null=True, blank=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)