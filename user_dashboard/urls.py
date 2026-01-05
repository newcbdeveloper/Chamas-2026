# user_dashboard/urls.py
from django.urls import path, include
from . import views

app_name = 'user_dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('settings/', views.settings, name='settings'),
    path('notifications/', views.all_notifications, name='all_notifications'),

    # KYC verification
    path('kyc/', include('user_dashboard.kyc_urls')),

    # Notification actions - FIXED: All these functions are now in views.py
    path('notifications/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/delete/', views.delete_notification, name='delete_notification'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),
    path('notifications/remind-later/', views.remind_later, name='remind_later'),
    path('notifications/dismiss/', views.dismiss_notification, name='dismiss_notification'),
    path('notifications/expanded/', views.get_urgent_notifications_expanded, name='get_urgent_expanded'),
]