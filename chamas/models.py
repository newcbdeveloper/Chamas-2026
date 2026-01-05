from datetime import timedelta,datetime
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import ROUND_HALF_UP, Decimal
from dateutil.relativedelta import relativedelta


# Create your models here
class ChamaType(models.Model):
    name = models.CharField(max_length=55)

    def __str__(self):
        return self.name

class Chama(models.Model):
    name = models.CharField(max_length=55)
    type = models.ForeignKey(ChamaType,on_delete=models.SET_NULL,related_name='type',null=True)
    created_on = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,related_name='group',null=True)
    start_date = models.DateField()

    def __str__(self):
        return self.name
    
class Role(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name
    
class ChamaMember(models.Model):
    name = models.CharField(max_length=55)
    email = models.EmailField()
    mobile = models.CharField(max_length=25)
    member_since = models.DateTimeField(default=timezone.now)
    group = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name ='member')
    role = models.ForeignKey(Role,on_delete = models.SET_NULL,related_name='member',null=True)
    member_id = models.CharField(max_length=25,blank=True,null=True)
    user = models.ForeignKey(User,on_delete = models.SET_NULL,related_name = 'membership',  null=True, blank=True)
    active = models.BooleanField(default=True)
    profile = models.ImageField(blank=True,null=True)

    class Meta:
        unique_together = ('user', 'group',)
        
    def total_contributions(self):
        tot = 0.00
        for record in self.member_records.all():
            tot += float(record.amount_paid)

        return tot
    
    def total_loans(self):
        tot = 0.00
        return self.loans.count()

    def __str__(self):
        return f'{self.name} - {self.mobile}'


#contributions model
class Contribution(models.Model):
    name = models.CharField(max_length=55)
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    description = models.TextField()
    start_date = models.DateField(null=True)
    chama = models.ForeignKey(Chama,on_delete = models.CASCADE,related_name='contributions')

    def __str__(self):
        return self.name

    
    
class ContributionRecord(models.Model):
    contribution = models.ForeignKey(Contribution,on_delete = models.CASCADE,related_name='records')
    date_created = models.DateTimeField()
    amount_expected = models.DecimalField(max_digits=10,decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10,decimal_places=2)
    balance = models.DecimalField(max_digits=10,decimal_places=2)
    member = models.ForeignKey(ChamaMember,on_delete=models.SET_NULL,related_name='member_records',null=True)
    chama = models.ForeignKey(Chama,on_delete=models.SET_NULL,related_name='contribution_records',  null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.member.name} - {self.date_created}'
    
    def fine_count(self):
        """Return the number of times this contribution record has been fined"""
        return self.fines.count()
    

#--------------------------------------
class LoanType(models.Model):
    type_id = models.CharField(max_length=45)
    name = models.CharField(max_length=45)
    max_loan_amount = models.IntegerField()
    max_due = models.IntegerField(default=0)
    grace_period = models.IntegerField()
    late_fine = models.IntegerField()
    intrest_rate = models.IntegerField()
    description = models.TextField()
    schedule = models.CharField(max_length=55,default='monthly')
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name='loan_types')

    def __str__(self):
        return f'{self.name} - {self.type_id}'
    
class LoanItem(models.Model):
    member = models.ForeignKey(ChamaMember,on_delete=models.SET_NULL,related_name='loans',null=True)
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    total_amount_to_be_paid = models.DecimalField(max_digits = 10,decimal_places=2,null=True,default=0.00)
    balance = models.DecimalField(max_digits=10,decimal_places=2,null=True)
    intrest_rate = models.IntegerField(null=True)
    start_date = models.DateTimeField(null=True)
    end_date = models.DateTimeField(null=True)
    total_paid = models.DecimalField(max_digits=10,decimal_places=2,null=True)
    status = models.CharField(max_length=50,default='application')
    last_updated = models.DateTimeField(default=timezone.now)
    type = models.ForeignKey(LoanType,on_delete=models.SET_NULL,related_name='loan_records',null=True)
    applied_on = models.DateTimeField(default=timezone.now)
    chama = models.ForeignKey(Chama,on_delete=models.SET_NULL,related_name='loans',default='',null=True)
    schedule = models.CharField(max_length=55,default='monthly')
    due = models.IntegerField(default=0)
    next_due = models.DateTimeField(null=True)

    def __str__(self):
        return f'{self.member.name} - {self.amount}'
    
    def calc_tot_amount_to_be_paid(self):
        if self.schedule == 'monthly':

            r = Decimal(self.type.intrest_rate) / Decimal(100)
            r = r / Decimal(12)
            P = Decimal(self.amount)
            n = Decimal(self.due)

            try:
                A = P * (r * (Decimal(1) + r) ** n) / ((Decimal(1) + r) ** n - Decimal(1))
            except Exception as e:
                print(e)
            tot = A * n
            self.total_amount_to_be_paid = tot.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            self.balance = tot.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

            self.next_due = self.start_date + relativedelta(days=30)
            self.save()

        elif self.schedule == 'weekly':
            r = Decimal(self.type.intrest_rate) / Decimal(100)
            r = r / Decimal(12)

            P = Decimal(self.amount)
            n = Decimal(self.due)/Decimal(4)

            try:
                A = P * (r * (Decimal(1) + r) ** n) / ((Decimal(1) + r) ** n - Decimal(1))
            except Exception as e:
                print(e)

            sub_tot = A / Decimal(4)
            tot = sub_tot * Decimal(self.due)
            self.total_amount_to_be_paid = tot.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            self.balance = tot.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

            self.next_due = self.start_date + relativedelta(days=7)
            self.save()

    def next_due_amount(self):
        tot_amount = self.total_amount_to_be_paid
        return tot_amount/self.due

    def calc_next_date(self):
        if self.schedule == 'weeks':
            self.next_due =self.next_due + relativedelta(days=7)
            self.save()

        elif self.schedule == 'months':
            self.next_due = self.next_due + relativedelta(days=30)
            self.save()

        return self.next_due
            
        
class FineType(models.Model):
    name = models.CharField(max_length=55)
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    description = models.TextField()
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name='fine_types')

    def __str__(self):
        return f'fine:{self.name} - loan:{self.loan_type.name}'
    

class FineItem(models.Model):
    member = models.ForeignKey(ChamaMember,on_delete=models.SET_NULL,related_name='fines',null=True)
    fine_type = models.ForeignKey(FineType,on_delete=models.SET_NULL,related_name='fine_items',null=True)
    loan_amount = models.DecimalField(max_digits=10,decimal_places=2,null=True)
    loan_balance = models.DecimalField(max_digits=10,decimal_places=2,null=True)
    fine_amount = models.DecimalField(max_digits=10,decimal_places=2)
    paid_fine_amount = models.DecimalField(max_digits=10,decimal_places=2)
    fine_balance = models.DecimalField(max_digits=10,decimal_places=2)
    status = models.CharField(max_length=55,default='active')
    created = models.DateTimeField(default = timezone.now)
    last_updated = models.DateTimeField(default=timezone.now)
    loan = models.ForeignKey(LoanItem,on_delete=models.SET_NULL,related_name = 'fines',default='',null=True)
    contribution = models.ForeignKey(Contribution,on_delete=models.SET_NULL,related_name='fines',null=True)
    contribution_record = models.ForeignKey(ContributionRecord,on_delete=models.SET_NULL,related_name='fines',null=True,blank=True)
    forLoan = models.BooleanField(default=False, db_column='forLoan')
    forContribution = models.BooleanField(default=False, db_column='forContribution')
    contribution_balance = models.DecimalField(decimal_places=2,max_digits=10,null=True)

    def __str__(self):
        return self.member.name 
    


#--------------------------------------------
class Expense(models.Model):
    name = models.CharField(max_length=55)
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    description = models.TextField()
    created_on = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(ChamaMember,on_delete=models.SET_NULL,related_name='chama_expenses',null=True)
    chama = models.ForeignKey(Chama,on_delete=models.SET_NULL,related_name = 'expenses',null=True)

    def __str__(self):
        return self.name

#----------------------------------------------------
class SavingType(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return str(self.name)
    
class Saving(models.Model):
    owner = models.ForeignKey(ChamaMember,on_delete = models.SET_NULL,related_name ='savings',null=True)
    chama = models.ForeignKey(Chama,related_name='savings',on_delete=models.CASCADE)
    forGroup = models.BooleanField(default=False, db_column='forGroup')
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    saving_type = models.ForeignKey(SavingType,on_delete=models.SET_NULL,related_name='savings',null=True)
    date = models.DateTimeField(default=timezone.now)

#------------------------------------------------------
class Investment(models.Model):
    name = models.CharField(max_length=55)
    chama = models.ForeignKey(Chama,on_delete=models.SET_NULL,related_name='investments',  null=True, blank=True)
    owner = models.ForeignKey(ChamaMember,on_delete=models.SET_NULL,related_name='investments',null=True, blank=True)
    date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    user_date = models.DateField(default=timezone.now)
    forGroup = models.BooleanField(default=False, db_column='forGroup')

    def __str__(self):
        return self.name
    
class Income(models.Model):
    name = models.CharField(max_length=55)
    date = models.DateTimeField(default=timezone.now)
    owner = models.ForeignKey(ChamaMember,on_delete=models.SET_NULL,related_name='incomes',null=True)
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name='incomes')
    forGroup = models.BooleanField(default=False, db_column='forGroup')
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    user_date = models.DateField(default=timezone.now)
    investment = models.ForeignKey(Investment,on_delete=models.CASCADE,related_name='incomes')

    def __str__(self):
        return self.name

#-----------------------------------------------------------
class NotificationType(models.Model):
    name = models.CharField(max_length=50)
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name='notification_types')
    description = models.TextField()

    def __str__(self):
        return self.name
    
class NotificationItem(models.Model):
    member = models.ForeignKey(ChamaMember,on_delete=models.SET_NULL,related_name='notifications',  null=True, blank=True)
    message = models.TextField()
    date = models.DateTimeField(default=timezone.now)
    type = models.ForeignKey(NotificationType,on_delete=models.SET_NULL,related_name='notifications',null=True)
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name='notifications')
    forGroup = models.BooleanField(db_column='forGroup')

    def __Str__(self):
        return f'{self.member.name}  - {self.type.name} - {self.type}'
    
class Document(models.Model):
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    upload_date = models.DateTimeField(auto_now_add=True)
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name = 'documents')
    file_type = models.CharField(max_length=10, blank=True, null=True)  # Stores file extension like 'pdf', 'xlsx', etc.
    file_size = models.BigIntegerField(blank=True, null=True)  # Stores file size in bytes

    def __str__(self):
        return self.name
    
    def get_file_type(self):
        """Returns the file extension based on the file name"""
        if hasattr(self, 'file_type') and self.file_type:
            return self.file_type
        if self.file and self.file.name:
            return self.file.name.split('.')[-1].lower()
        return 'unknown'
    
    def get_file_icon(self):
        """Returns appropriate icon class based on file type"""
        file_type = self.get_file_type().lower()
        if file_type in ['pdf']:
            return 'bx-file-pdf'
        elif file_type in ['xls', 'xlsx', 'csv']:
            return 'bx-spreadsheet'
        elif file_type in ['doc', 'docx']:
            return 'bx-file-doc'
        elif file_type in ['jpg', 'jpeg', 'png', 'gif']:
            return 'bx-image'
        else:
            return 'bx-file-blank'
    
    def get_formatted_size(self):
        """Returns human readable file size"""
        if not hasattr(self, 'file_size') or not self.file_size:
            # Fallback: try to get size from file field
            try:
                if self.file and hasattr(self.file, 'size'):
                    size = float(self.file.size)
                else:
                    return 'Unknown size'
            except:
                return 'Unknown size'
        else:
            size = float(self.file_size)
        
        # Create a copy to avoid modifying the original
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

class CashflowReport(models.Model):
    object_date = models.DateTimeField()
    member = models.ForeignKey(ChamaMember,on_delete = models.SET_NULL,related_name='cashflow_reports',null=True)
    type = models.CharField(max_length=25)
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    chama = models.ForeignKey(Chama,on_delete=models.CASCADE,related_name='cashflow_reports')
    forGroup = models.BooleanField(db_column='forGroup')
    date_created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        if self.member:
            message = f'{self.member.name} - {self.type} - {self.date_created.strftime("%d/%m/%Y %H:%M%S")}'
        else:
            message = f'Group - {self.type} - {self.date_created.strftime("%d/%m/%Y %H:%M%S")}'

        return message
    



