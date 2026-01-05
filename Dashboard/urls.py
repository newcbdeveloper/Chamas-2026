from django.http import JsonResponse
from django.urls import path
from . import views


urlpatterns=[
path('', views.Dashboard, name='Dashboard'),
path('Settings', views.Setting, name='Setting'),
path('all_notifications', views.all_notifications, name='all_notifications'),

path('joinchamas', views.joinchamas, name='joinchamas'),
path('mychamas', views.mychamas, name='mychamas'),
path('manage_chamas', views.manage_chamas, name='manage_chamas'),
path('setting_security', views.setting_security, name='setting_security'),
path('stats_page1', views.stats_page1, name='stats_page1'),
path('stats_page_2/<category_name>', views.stats_page_2, name='stats_page_2'),
path('stats_page_3/<category_name>', views.stats_page_3, name='stats_page_3'),
path('paypal', views.payment_paypal, name='paypal'),
path('paypal_payment_success', views.paypal_payment_success,name='paypal_paymentcomplete'),

]