from django.contrib import admin

# Register your models here.
from .models import *

admin.site.register(ExpressSaving)
admin.site.register(Goal_Wallet)
admin.site.register(Goal)
admin.site.register(Deposit)
admin.site.register(Interest_Rate)
admin.site.register(GroupGoal)
admin.site.register(GroupGoalMember_contribution)
admin.site.register(tax_Rate)