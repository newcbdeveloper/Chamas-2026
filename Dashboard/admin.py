from django.contrib import admin

# Register your models here.
from .models import *

class ChamasAdmin(admin.ModelAdmin):
    list_display = ('name', 'No_of_people','frequency_of_contribution','contribution_turn','amount','status','category_id','active','start_date','end_date','contribution_date', 'user_id','Awarded','Award_turn')

# class user_joined_chamasAdmin(admin.ModelAdmin):
#     list_display = ('chamas_id', 'user_id','Awarded','Award_turn')

admin.site.register(Chamas,ChamasAdmin)
# admin.site.register(user_joined_chamas,user_joined_chamasAdmin)

class contributionAdmin(admin.ModelAdmin):
    list_display = ('chamas_id', 'user_id','amount','fined_amount','inserted_on','updated_on')
class transactionAdmin(admin.ModelAdmin):
    list_display = ('chamas_id', 'user_id','amount','description','inserted_on','updated_on')
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user_id','available_for_withdraw','pending_clearence','withdrawal','description','inserted_on','updated_on')
admin.site.register(Category)
admin.site.register(contribution,contributionAdmin)
admin.site.register(Transection,transactionAdmin)
admin.site.register(Wallet,WalletAdmin)

admin.site.register(mpesa_body_test)