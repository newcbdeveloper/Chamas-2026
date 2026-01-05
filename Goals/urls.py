from django.http import JsonResponse
from django.urls import path
from . import views

app_name = 'goals'

urlpatterns = [
    # Dashboard
    path('', views.my_goals, name='wekeza_dashboard'),  # Main entry point
    #path('chamas_dashboard/', views.goals_dashboard, name='goals_dashboard'),

    # Personal goals
    path('create_personal_goals/', views.create_personal_goals, name='create_personal_goals'),
    path('goal_details/<int:id>/', views.goal_details, name='goal_details'),
    path('delete_goal/', views.delete_goal, name='delete_goal'),
    path('edit_goal/', views.edit_goal, name='edit_goal'),
    path('personal_goal_statement/<int:id>/', views.personal_goal_statement, name='personal_goal_statement'),

    # Express savings
    path('express_saving/', views.express_saving, name='express_saving'),
    path('add_funds_to_goal/<int:id>/', views.add_funds_to_goal, name='add_funds_to_goal'),
    path('express_saving_dashboard/', views.express_saving_dashboard, name='express_saving_dashboard'),
    path('express_saving_summary/<int:id>/', views.express_saving_summary, name='express_saving_summary'),
    path('express_statement/<str:username>/', views.express_statement, name='express_statement'),

    # Group goals
    path('create_group_goal/', views.create_group_goal, name='create_group_goal'),
    path('group_goal_details/<int:id>/', views.group_goal_details, name='group_goal_details'),
    path('exit_group_goal/', views.exit_group_goal, name='exit_group_goal'),
    path('delete_group_goal/', views.delete_group_goal, name='delete_group_goal'),
    path('add_members/<int:details>/', views.add_members, name='add_members'),
    path('add_funds_to_group_goal/', views.add_funds_to_group_goal, name='add_funds_to_group_goal'),
    path('send_invitations/', views.send_invitations, name='send_invitations'),
    path('goal_statement/<int:id>/', views.goal_statement, name='goal_statement'),
    path('edit_group_goal/', views.edit_group_goal, name='edit_group_goal'),

    # Withdraw amount
    path('withdraw_money_express_saving/', views.withdraw_money_express_saving, name='withdraw_money_express_saving'),
    path('withdraw_money_personal_goal/', views.withdraw_money_personal_goal, name='withdraw_money_personal_goal'),
    path('withdraw_money_group_goal/', views.withdraw_money_group_goal, name='withdraw_money_group_goal'),
    #path('add_account/', views.add_account, name='add_account'),
]