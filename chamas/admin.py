from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Chama)
admin.site.register(ChamaMember)
admin.site.register(ChamaType)
admin.site.register(Contribution)
admin.site.register(ContributionRecord)
admin.site.register(Expense)
admin.site.register(LoanType)
admin.site.register(LoanItem)
admin.site.register(FineItem)
admin.site.register(FineType)
admin.site.register(Saving)
admin.site.register(Investment)
admin.site.register(Income)
admin.site.register(Document)
admin.site.register(CashflowReport)
admin.site.register(Role)
admin.site.register(SavingType)
admin.site.register(NotificationItem)

