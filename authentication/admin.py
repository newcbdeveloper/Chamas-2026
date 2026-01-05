from django.contrib import admin

# Register your models here.
from .models import Profile,Payment_Method,How_did_you_find,Gender,chamas_members,frequency_of_contri,no_of_cycle,amount_per_contribution
# Register your models here.
admin.site.register(Profile)
admin.site.register(Payment_Method)
admin.site.register(How_did_you_find)
admin.site.register(Gender)
admin.site.register(chamas_members)
admin.site.register(frequency_of_contri)
admin.site.register(no_of_cycle)
admin.site.register(amount_per_contribution)