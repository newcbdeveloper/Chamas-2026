
# wallet/urls.py
from django.urls import path
from . import views

app_name = 'wallet'



#goals alerts
#path('goal_contribution_alert/', views.goal_contribution_alert, name='goal_contribution_alert'),

#path('wallet_index/', views.wallet_index, name='wallet_index'),


urlpatterns = [
    # Main dashboard
    path('', views.wallet_dashboard, name='wallet_dashboard'),
    
    # Deposit
    path('deposit/', views.deposit_via_mpesa, name='deposit_mpesa'),
    path('deposit/success/', views.stk_push_success, name='stk_push_success'),
    path('deposit/failed/', views.stk_push_fail, name='stk_push_fail'),
    
    # Withdrawal
    path('withdraw/', views.withdraw_via_mpesa, name='withdraw_mpesa'),
    path('withdraw/verify/<int:pending_id>/', views.verify_withdrawal_password, name='verify_withdrawal_password'),  
    
    # Transactions
    path('transactions/', views.transaction_history, name='transaction_history'),
    path('transactions/<int:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    
    # API endpoints
    path('api/balance/', views.api_wallet_balance, name='api_balance'),
    path('api/transactions/', views.api_recent_transactions, name='api_transactions'),
    
    # Manual transfers (for testing)
    path('transfer/mgr/', views.transfer_to_mgr, name='transfer_to_mgr'),
    path('transfer/goals/', views.transfer_to_goals, name='transfer_to_goals'),
]