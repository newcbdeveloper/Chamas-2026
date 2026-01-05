from django.urls import path
from . import views

app_name = 'merry_go_round'

urlpatterns = [
    # Main pages
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_alt'),
    
    # Wallet management
    path('wallet/', views.wallet_dashboard, name='wallet_dashboard'),
    path('wallet/deposit/', views.deposit_to_wallet, name='deposit_to_wallet'),
    path('wallet/withdraw/', views.withdraw_from_wallet, name='withdraw_from_wallet'),
    path('wallet/transaction/<uuid:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    path('wallet/statistics/', views.wallet_statistics, name='wallet_statistics'),
    
    # Wallet AJAX actions
    path('wallet/quick-deposit/', views.quick_deposit, name='quick_deposit'),
    path('wallet/quick-withdraw/', views.quick_withdraw, name='quick_withdraw'),
    
    # Round browsing and joining
    path('join/', views.join_round, name='join_round'),
    path('join/<uuid:round_id>/', views.join_round_action, name='join_round_action'),
    path('round/<uuid:round_id>/check-balance/', views.check_balance_for_round, name='check_balance_for_round'),
    
    # Round creation and management Two separate routes:
    
    path('round/<uuid:round_id>/', views.round_detail, name='round_detail'),
    path('round/<uuid:round_id>/completed/', views.round_complete_detail, name='round_complete_detail'),

    path('create/', views.create_round, name='create_round'),
    path('my-rounds/', views.my_rounds, name='my_rounds'),
    
    # Round actions
    path('round/<uuid:round_id>/start/', views.start_round_action, name='start_round'),
    path('round/<uuid:round_id>/message/', views.post_message, name='post_message'),
    
    # Invitations
    path('round/<uuid:round_id>/invite/', views.send_invitation, name='send_invitation'),
    path('accept_invitation/<str:token>/', views.accept_invitation, name='accept_invitation'),
    path('invitation/<str:token>/review/', views.review_invitation, name='review_invitation'),

    # NEW: Enhanced invitation endpoints
    path('api/lookup-member/', views.api_lookup_member, name='api_lookup_member'),
    path('api/round/<uuid:round_id>/send-batch-invitations/', views.api_send_batch_invitations, name='api_send_batch_invitations'),
    path('api/round/<uuid:round_id>/shareable-link/', views.api_get_shareable_link, name='api_get_shareable_link'),
    path('join-link/<uuid:round_id>/', views.join_via_link, name='join_via_link'),
    path('join-link/<uuid:round_id>/confirm/', views.confirm_join_via_link, name='confirm_join_via_link'),

    #Delete completed round
    path('round/<uuid:round_id>/delete-completed/', views.delete_completed_round, name='delete_completed_round'),

    
    # Contributions
    path('contribution/<uuid:contribution_id>/pay/', views.make_contribution, name='make_contribution'),
    path('contributions/history/', views.contribution_history, name='contribution_history'),
    
    # Payouts
    path('payouts/history/', views.payout_history, name='payout_history'),
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<uuid:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    
    # API endpoints (for AJAX)
    path('api/round/<uuid:round_id>/', views.get_round_data, name='api_round_data'),
    path('api/user/stats/', views.get_user_stats, name='api_user_stats'),
    path('api/wallet/balance/', views.api_wallet_balance, name='api_wallet_balance'),
    path('api/wallet/transactions/', views.api_recent_transactions, name='api_recent_transactions'),
    
    # Notification actions
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/<uuid:notification_id>/delete/', views.delete_notification, name='delete_notification'),
    
    # Delete a round that hasn't started
    path('round/<uuid:round_id>/delete/', views.delete_round, name='delete_round'),

    # API endpoints for modals
    path('api/payout/<uuid:payout_id>/', views.get_payout_data, name='api_payout_data'),

    # Add these URL patterns to the existing merry_go_round/urls.py file
    
    # Add to the urlpatterns list:

    # Wallet transfers between Main Wallet and MGR Wallet
    path('wallet/transfer-from-main/', views.transfer_from_main_wallet, name='transfer_from_main'),
    path('wallet/transfer-to-main/', views.transfer_to_main_wallet, name='transfer_to_main'),
    
    # AJAX transfer actions
    path('wallet/quick-transfer-from-main/', views.quick_transfer_from_main, name='quick_transfer_from_main'),
    path('wallet/quick-transfer-to-main/', views.quick_transfer_to_main, name='quick_transfer_to_main'),
]