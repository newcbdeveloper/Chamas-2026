from datetime import date
from dateutil.relativedelta import relativedelta

from django.contrib.auth.models import User
from django.db import models

# Create your models here.
from django.utils.timezone import now


class Category(models.Model):
    name = models.CharField(max_length=225, null=True, blank=True,verbose_name = "Category Name")
    members = models.CharField(max_length=225, null=True, blank=True,verbose_name = "Members")
    frequency = models.CharField(max_length=225, null=True, blank=True,verbose_name = "Frequency")
    amount = models.CharField(max_length=225, null=True, blank=True,verbose_name = "Amount")
    description = models.CharField(max_length=225, null=True, blank=True,verbose_name = "Category Details")
    inserted_on = models.DateField(default=now,null=True, blank=True ,verbose_name = "Inserted On")
    updated_on = models.DateField(default=now,null=True, blank=True,verbose_name = "Updated On")
    def __str__(self):
        return self.name



class Chamas(models.Model):
    category_id = models.ForeignKey(Category,on_delete=models.CASCADE ,verbose_name = "Category Name")

    name = models.CharField(max_length=700, null=True, blank=True ,verbose_name = "Chamas Name")
    amount = models.CharField(max_length=700, null=True, blank=True ,verbose_name = "Chamas Amount")

    No_of_people = models.CharField(max_length=225,verbose_name = "No. of People",db_column='No_of_people')
    frequency_of_contribution = models.CharField(max_length=225,verbose_name = "Frequency of Contribution")

    contribution_turn = models.CharField(max_length=225, null=True, blank=True,verbose_name = "Contribution Turn")
    end_date = models.DateField(null=True, blank=True,verbose_name = "Chamas End Date")
    start_date = models.DateField(null=True, blank=True,verbose_name = "Chamas Start Date")
    contribution_date = models.DateField(null=True, blank=True,verbose_name = "Contribution Date")
    status = models.CharField(max_length=225 ,verbose_name = "Chamas Status")
    active = models.CharField(max_length=225 ,verbose_name = "Is Active")
    user_id = models.ForeignKey(User,on_delete=models.CASCADE ,verbose_name = "User Name")
    Awarded = models.CharField(max_length=225,null=True, blank=True, db_column='Awarded')
    Award_turn = models.CharField(max_length=225,null=True, blank=True,verbose_name = "Award Turn",db_column='Award_turn')
    inserted_on = models.DateField(default=now,null=True, blank=True,verbose_name = "Inserted On")
    updated_on = models.DateField(default=now,null=True, blank=True,verbose_name = "Updated On")

    # subscription = models.OneToOneField(ChamaSubscription, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name

    def get_progress(self):
        try:
            return (date.today() - self.start_date) / (self.end_date - self.start_date) * 100
        except:
            return 0.0

    def remaining_user_numbers(self):
        members = Chamas.objects.filter(status='joined', active='No' ,category_id__name=self.category_id.name).count()

        return int(int(self.No_of_people) - members)+1

    def joined_user_numbers(self):
        members = Chamas.objects.filter(status='joined', active='No' ,category_id__name=self.category_id.name).count()

        return int(members)-1



    @property
    def get_progress_percentage(self):
        progress=(date.today() - self.start_date) / (self.end_date - self.start_date) *100
        return progress
    

   








class contribution(models.Model):
    chamas_id = models.ForeignKey(Chamas,on_delete=models.CASCADE,verbose_name = "Chamas Name")
    user_id = models.ForeignKey(User,on_delete=models.CASCADE,verbose_name = "User Name")
    amount = models.FloatField(null=True, blank=True,verbose_name = "Amount")
    fined_amount = models.FloatField(null=True, blank=True,verbose_name = "Fined Amount")
    inserted_on = models.DateField(default=now,null=True, blank=True,verbose_name = "Inserted On")
    updated_on = models.DateField(default=now,null=True, blank=True,verbose_name = "Updated On")


class Transection(models.Model):
    chamas_id = models.ForeignKey(Chamas,on_delete=models.CASCADE)
    user_id = models.ForeignKey(User,on_delete=models.CASCADE)
    # transaction_id = models.CharField(max_length=2000, null=True, blank=True)
    amount = models.FloatField(null=True, blank=True)
    description = models.CharField(max_length=225,null=True, blank=True)
    inserted_on = models.DateField(default=now,null=True, blank=True)
    updated_on = models.DateField(default=now,null=True, blank=True)

class Wallet(models.Model):
    chamas_id = models.ForeignKey(Chamas,on_delete=models.SET_NULL,null=True, blank=True)
    user_id = models.ForeignKey(User,on_delete=models.CASCADE)

    available_for_withdraw = models.FloatField(null=True, blank=True)
    pending_clearence = models.FloatField(null=True, blank=True)
    withdrawal = models.FloatField(null=True, blank=True)
    description = models.CharField(max_length=2000,null=True, blank=True)
    inserted_on = models.DateField(default=now,null=True, blank=True)
    updated_on = models.DateField(default=now,null=True, blank=True)


class Saving_Wallet(models.Model):

    user_id = models.ForeignKey(User,on_delete=models.CASCADE)

    available_balance = models.FloatField(null=True, blank=True)

    description = models.CharField(max_length=2000,null=True, blank=True)
    inserted_on = models.DateField(default=now,null=True, blank=True)
    updated_on = models.DateField(default=now,null=True, blank=True)


class Peer_to_Peer_Wallet(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)

    available_balance = models.FloatField(null=True, blank=True)

    description = models.CharField(max_length=2000, null=True, blank=True)
    inserted_on = models.DateField(default=now, null=True, blank=True)
    updated_on = models.DateField(default=now, null=True, blank=True)

class Notification(models.Model):
    chamas_id = models.ForeignKey(Chamas,on_delete=models.CASCADE,verbose_name = "Chamas Name")
    user_id = models.ForeignKey(User,on_delete=models.CASCADE,verbose_name = "User Name")
    notification_text = models.CharField(max_length=225,null=True, blank=True,verbose_name = "Notification Title")
    description = models.CharField(max_length=225,null=True, blank=True,verbose_name = "Notification Details")
    inserted_on = models.DateField(default=now,null=True, blank=True,verbose_name = "Inserted On")
    updated_on = models.DateField(default=now,null=True, blank=True,verbose_name = "Updated On")



class mpesa_body_test(models.Model):

    body = models.CharField(max_length=3000,null=True, blank=True,verbose_name = "Body is")
    description = models.CharField(max_length=3000,null=True, blank=True,verbose_name = "Description")
    inserted_on = models.DateField(default=now,null=True, blank=True,verbose_name = "Inserted On")
    updated_on = models.DateField(default=now,null=True, blank=True,verbose_name = "Updated On")