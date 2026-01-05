from django.contrib import admin

# Register your models here.
from .models import *
class UserBankDetailsAdmin(admin.ModelAdmin):
    list_display = ('iban', 'bank_name','swift_code','branch_id','account_no','bank_country','user_id')
admin.site.register(UserBankDetails,UserBankDetailsAdmin)


class UserMoneyWithDrawalStatusAdmin(admin.ModelAdmin):
    list_display = ('withdrawal_amount', 'Withdrawal_request_date','status','user_id')
admin.site.register(UserMoneyWithDrawalStatus,UserMoneyWithDrawalStatusAdmin)
