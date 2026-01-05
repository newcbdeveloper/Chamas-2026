from django.db import models
from chamas.models import *

# Create your models here.
class BotContribution(models.Model):
    submitted_contribution = models.TextField()
    retrieved_contribution = models.ForeignKey(Contribution,on_delete = models.CASCADE,related_name='_botrecords')
    date_created = models.DateTimeField(auto_now_add=True)
    amount_paid = models.DecimalField(max_digits=10,decimal_places=2)
    submitted_member = models.TextField()
    submitted_chama = models.TextField()
    retrieved_chama = models.ForeignKey(Chama,on_delete=models.SET_NULL,related_name='bot_contribution_records',  null=True, blank=True)
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name='chama_bot_contributions',null=True,blank=True)
    member_id = models.TextField(null=True)
    approved = models.BooleanField(default=False)
    record = models.ForeignKey(ContributionRecord,on_delete=models.CASCADE,related_name='contribution_records',null=True,blank=True)
    sender = models.TextField(default="",blank=True)


    def __str__(self):
        return f'{self.submitted_member} - {self.date_created}'
    
class ContributionFraud(models.Model):
    record = models.ForeignKey(BotContribution,related_name="bot_fraud",on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.record.sender}"
    

class BotFine(models.Model):
    member = models.TextField()
    amount_paid = models.DecimalField(max_digits=10,decimal_places=2)
    submitted_chama = models.TextField()
    retrieved_chama = models.ForeignKey(Chama,on_delete=models.SET_NULL,related_name='bot_fine_records',  null=True, blank=True)
    edited_fine = models.ForeignKey(FineItem,on_delete=models.SET_NULL,related_name='bot_updates',null=True,blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name='chama_bot_fines',null=True,blank=True)
    approved = models.BooleanField(default=False)
    sender = models.TextField(default="")

    def __str__(self):
        return f'{self.member} - {self.date_created}'
    
class FineFraud(models.Model):
    record = models.ForeignKey(BotFine,on_delete=models.CASCADE,related_name="bot_fraud")

    def __str__(self):
        return f'{self.record.sender}'
    
class BotLoan(models.Model):
    member = models.TextField()
    amount_paid = models.DecimalField(max_digits=10,decimal_places=2)
    submitted_chama = models.TextField()
    retrieved_chama = models.ForeignKey(Chama,on_delete=models.SET_NULL,related_name='bot_loan_records',  null=True, blank=True)
    updated_loan = models.ForeignKey(LoanItem,on_delete=models.SET_NULL,related_name='bot_updates',null=True,blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name='chama_bot_loans',null=True,blank=True)
    approved = models.BooleanField(default=False)
    sender = models.TextField(default="")

    def __str__(self):
        return f'{self.member} - {self.date_created}'
    
class LoanFraud(models.Model):
    record = models.ForeignKey(BotLoan,on_delete=models.CASCADE,related_name="bot_fraud")

    def __str__(self):
        return f"{self.record.sender}"
    
class BotMember(models.Model):
    name = models.TextField()
    email = models.EmailField()
    id_number = models.TextField()
    phone = models.TextField()
    role = models.TextField()
    chama_name = models.TextField()
    member = models.ForeignKey(ChamaMember,related_name="bot_members",on_delete=models.SET_NULL,null=True,blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    chama = models.ForeignKey(Chama,related_name="bot_members",on_delete=models.CASCADE,null=True,default=None)
    sender = models.TextField(default="")

    def __str__(self):
        return f'{self.name} - {self.id_number}'
    
class MemberFraud(models.Model):
    record = models.ForeignKey(BotMember,on_delete=models.CASCADE,related_name="bot_fraud")

    def __str__(self):
        return f"{self.record.sender}"


