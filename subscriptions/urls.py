from django.urls import path
from . import views

urlpatterns = [
    path('plans/<int:chama_id>/', views.subscription_chama, name='subscription_chama'),
    path('plans/', views.subscription_plans, name='subscription_plans'),
    path('start-trial', views.start_trial, name='start_trial'),
    path('subscribe/', views.subscribe, name='subscribe'),

    path('mpesa-express/', views.mpesa_express, name='mpesa_express'),
    path('lnmo-callback/', views.lnmo_callback, name='lnmo_callback'),
    path('subscription-waiting/', views.subscription_waiting, name='subscription_waiting'),

    path('lipa_na_mpesa/', views.lipa_na_mpesa_online, name='lipa_na_mpesa'),

    path('processing/', views.subscription_waiting, name='subscription_waiting'),
    path('processing/<str:signature>', views.subscription_waiting, name='subscription_waiting_with_signature'),

    path('processing/<str:signature>/status/', views.subscription_status, name='subscription_status'),
    path('success/', views.subscription_success, name='subscription_success'),

    path('failed/', views.subscription_error, name='subscription_error'),
    path('failed/<str:error>', views.subscription_error, name='subscription_failed'),
    path('webhook/<str:signature>', views.subscription_webhook, name='subscription_webhook'),
]


