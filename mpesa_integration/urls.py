from django.urls import path
from . import views

urlpatterns = [


    path('access/token', views.getAccessToken, name='get_mpesa_access_token'),
    path('load_money', views.lipa_na_mpesa_online, name='load_money'),
    path('stk_push_success', views.stk_push_success, name='stk_push_success'),
    path('stk_push_fail', views.stk_push_fail, name='stk_push_fail'),
    path('register', views.register_urls, name="register_mpesa_validation"),
    path('confirmation', views.confirmation, name="confirmation"),
    path('validation', views.validation, name="validation"),
    path('callback', views.callback, name="callback"),


    path('test_mpesa_body', views.test_mpesa_body , name="test_mpesa_body"),



]

