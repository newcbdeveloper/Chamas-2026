from django.db import models

# Create your models here.
from django.contrib.auth.models import User


class Payment_Method(models.Model):
    name = models.CharField(max_length=255)


    def __str__(self):
        return self.name



class Gender(models.Model):
    name = models.CharField(max_length=255)


    def __str__(self):
        return self.name



class How_did_you_find(models.Model):
    name = models.CharField(max_length=255)


    def __str__(self):
        return self.name


class chamas_members(models.Model):
    Numbers_of_memebrs = models.CharField(max_length=225)

    def __str__(self):
     return self.Numbers_of_memebrs


class frequency_of_contri(models.Model):
    frequency_of_contribution = models.CharField(max_length=255)

    def __str__(self):
        return self.frequency_of_contribution

class no_of_cycle(models.Model):
    no_of_cycle = models.CharField(max_length=225)

    def __str__(self):
        return self.no_of_cycle
class amount_per_contribution(models.Model):
    amount_per_contribution = models.CharField(max_length=225)

    def __str__(self):
        return self.amount_per_contribution



class Profile(models.Model):
    owner=models.OneToOneField(User,on_delete=models.CASCADE)
    phone = models.CharField(max_length=25, blank=True, unique=True, null=True)
    NIC_No=models.CharField(max_length=25,unique=True,blank=True,null=True, db_column='NIC_No')
    physical_address=models.CharField(max_length=40,blank=True,null=True)
    picture = models.ImageField(upload_to='ProfileImages', blank=True)
    # No_of_chamas_memebrs=models.CharField(max_length=225,blank=True,null=True)
    # frequency_of_contribution=models.CharField(max_length=225,blank=True,null=True)
    # amount_per_contribution=models.CharField(max_length=225,blank=True,null=True)
    # no_of_cycles=models.CharField(max_length=225,blank=True,null=True)
    payment_method=models.CharField(max_length=225,blank=True,null=True)
    how_did_you_find=models.CharField(max_length=225,blank=True,null=True)
    gender=models.CharField(max_length=25,blank=True,null=True)
    otp = models.CharField(max_length=6,blank=True,null=True)

    def __str__(self):
        return self.NIC_No if self.NIC_No else str(self.owner)



@property
def image_url(self):
    if self.picture and hasattr(self.picture, 'url'):
        return self.picture.url

