from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # User-facing routes
    path('', views.my_tickets, name='my_tickets'),
    path('create/', views.create_ticket, name='create_ticket'),
    path('ticket/<uuid:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('ticket/<uuid:ticket_id>/send-message/', views.send_message, name='send_message'),
    
    # Admin routes
    path('admin/tickets/', views.admin_tickets_list, name='admin_tickets_list'),
    path('admin/ticket/<uuid:ticket_id>/', views.admin_ticket_detail, name='admin_ticket_detail'),
    path('admin/ticket/<uuid:ticket_id>/assign/', views.assign_ticket, name='assign_ticket'),
    path('admin/ticket/<uuid:ticket_id>/update-status/', views.update_ticket_status, name='update_ticket_status'),
    path('admin/ticket/<uuid:ticket_id>/respond/', views.admin_respond, name='admin_respond'),
    path('admin/ticket/<uuid:ticket_id>/internal-note/', views.add_internal_note, name='add_internal_note'),
    
    # API endpoints (for AJAX)
    path('api/messages/<uuid:ticket_id>/', views.api_get_messages, name='api_get_messages'),
    path('api/send-message/', views.api_send_message, name='api_send_message'),
    path('api/mark-read/<uuid:ticket_id>/', views.api_mark_messages_read, name='api_mark_read'),
]