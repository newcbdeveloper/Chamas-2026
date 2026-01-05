from django.urls import path
from . import views


urlpatterns=[

path('add_bank_details', views.add_account, name='add_bank_details'),
path('with_drawal_money', views.withdraw_money, name='with_drawal_money'),





]