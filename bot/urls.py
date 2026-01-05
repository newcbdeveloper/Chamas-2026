from django.urls import path
from . import views

app_name = 'bot'
urlpatterns = [
    path('webhook/',views.receive_message,name='infobip_webhook'),
    path('reports/<int:chama_id>/',views.bot_records,name='bot-records'),
    path('contributions/approve/<int:chama_id>/',views.approve_contribution,name='approve-contribution'),
    path('contributions/reject/<int:chama_id>/',views.flag_contribution,name='flag-contribution'),

    path('loans/approve/<int:chama_id>/',views.approve_loan,name='approve-loan'),
    path('loans/reject/<int:chama_id>/',views.flag_loan,name='flag-loan'),
    path('fines/approve/<int:chama_id>/',views.approve_fine,name='approve-fine'),
    path('fines/reject/<int:chama_id>/',views.flag_fine,name='flag-fine'),
    path('members/approve/<int:chama_id>/',views.approve_member,name='approve-member'),
    path('members/reject/<int:chama_id>/',views.flag_member,name='flag-member')

]