from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import SupportTicket, SupportMessage, TicketAssignment, TicketAuditLog


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ('sender_type', 'sender', 'message', 'created_at', 'attachment')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class TicketAssignmentInline(admin.TabularInline):
    model = TicketAssignment
    extra = 0
    readonly_fields = ('assigned_to', 'assigned_by', 'assigned_at', 'notes')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class TicketAuditLogInline(admin.TabularInline):
    model = TicketAuditLog
    extra = 0
    readonly_fields = ('action', 'performed_by', 'notes', 'ip_address', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        'reference_number',
        'user_link',
        'subject_short',
        'category_badge',
        'status_badge',
        'priority_badge',
        'assigned_to',
        'created_at',
        'last_message_at',
        'view_in_support_dashboard', 
    )
    
    list_filter = (
        'status',
        'priority',
        'category',
        'assigned_to',
        'created_at',
    )
    
    search_fields = (
        'reference_number',
        'subject',
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
    )
    
    readonly_fields = (
        'id',
        'reference_number',
        'created_at',
        'updated_at',
        'resolved_at',
        'closed_at',
        'last_message_at',
        'user_unread_count',
        'admin_unread_count',
    )
    
    fieldsets = (
        ('Ticket Information', {
            'fields': (
                'id',
                'reference_number',
                'user',
                'category',
                'subject',
                'status',
                'priority',
            )
        }),
        ('Assignment', {
            'fields': (
                'assigned_to',
                'assigned_at',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'resolved_at',
                'closed_at',
                'last_message_at',
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'last_message_by',
                'user_unread_count',
                'admin_unread_count',
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [SupportMessageInline, TicketAssignmentInline, TicketAuditLogInline]
    
    def view_in_support_dashboard(self, obj):
        url = reverse('support:admin_ticket_detail', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank" style="'
            'background-color: #28a745; color: white; padding: 4px 8px; '
            'border-radius: 4px; text-decoration: none; font-size: 0.85em;">'
            '💬 Open Chat</a>',
            url
        )
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'User'
    
    def subject_short(self, obj):
        return obj.subject[:50] + '...' if len(obj.subject) > 50 else obj.subject
    subject_short.short_description = 'Subject'
    
    def category_badge(self, obj):
        colors = {
            'wallet': '#3498db',
            'deposits': '#2ecc71',
            'withdrawals': '#e74c3c',
            'kyc': '#f39c12',
            'mgr': '#9b59b6',
            'goals': '#1abc9c',
            'bookkeeping': '#34495e',
            'suspicious': '#e67e22',
            'general': '#95a5a6',
        }
        color = colors.get(obj.category, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_category_display()
        )

    category_badge.short_description = 'Category'
    
    def status_badge(self, obj):
        colors = {
            'open': '#2ecc71',
            'pending': '#f39c12',
            'resolved': '#3498db',
            'closed': '#95a5a6',
        }
        color = colors.get(obj.status, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def priority_badge(self, obj):
        colors = {
            'low': '#95a5a6',
            'medium': '#3498db',
            'high': '#f39c12',
            'urgent': '#e74c3c',
        }
        color = colors.get(obj.priority, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display().upper()
        )
    priority_badge.short_description = 'Priority'
    
    def save_model(self, request, obj, form, change):
        if change:
            # Track status changes
            old_obj = SupportTicket.objects.get(pk=obj.pk)
            if old_obj.status != obj.status:
                TicketAuditLog.objects.create(
                    ticket=obj,
                    action='status_changed',
                    performed_by=request.user,
                    notes=f"Status changed from {old_obj.get_status_display()} to {obj.get_status_display()}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
            
            # Track assignment changes
            if old_obj.assigned_to != obj.assigned_to:
                obj.assigned_at = timezone.now()
                TicketAssignment.objects.create(
                    ticket=obj,
                    assigned_to=obj.assigned_to,
                    assigned_by=request.user,
                    notes=f"Assigned via Django Admin"
                )
                TicketAuditLog.objects.create(
                    ticket=obj,
                    action='assigned',
                    performed_by=request.user,
                    notes=f"Assigned to {obj.assigned_to.get_full_name()}",
                    ip_address=request.META.get('REMOTE_ADDR')
                )
        
        super().save_model(request, obj, form, change)


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_link',
        'sender_type',
        'sender',
        'message_short',
        'is_internal',
        'created_at',
    )
    
    list_filter = (
        'sender_type',
        'is_internal',
        'created_at',
    )
    
    search_fields = (
        'ticket__reference_number',
        'message',
        'sender__username',
    )
    
    readonly_fields = (
        'id',
        'ticket',
        'sender_type',
        'sender',
        'created_at',
    )
    
    def ticket_link(self, obj):
        url = reverse('admin:support_supportticket_change', args=[obj.ticket.id])
        return format_html('<a href="{}">{}</a>', url, obj.ticket.reference_number)
    ticket_link.short_description = 'Ticket'
    
    def message_short(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_short.short_description = 'Message'


@admin.register(TicketAssignment)
class TicketAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_link',
        'assigned_to',
        'assigned_by',
        'assigned_at',
    )
    
    list_filter = (
        'assigned_to',
        'assigned_by',
        'assigned_at',
    )
    
    search_fields = (
        'ticket__reference_number',
        'assigned_to__username',
        'assigned_by__username',
    )
    
    readonly_fields = (
        'id',
        'ticket',
        'assigned_to',
        'assigned_by',
        'assigned_at',
    )
    
    def ticket_link(self, obj):
        url = reverse('admin:support_supportticket_change', args=[obj.ticket.id])
        return format_html('<a href="{}">{}</a>', url, obj.ticket.reference_number)
    ticket_link.short_description = 'Ticket'


@admin.register(TicketAuditLog)
class TicketAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_link',
        'action',
        'performed_by',
        'created_at',
    )
    
    list_filter = (
        'action',
        'performed_by',
        'created_at',
    )
    
    search_fields = (
        'ticket__reference_number',
        'notes',
    )
    
    readonly_fields = (
        'id',
        'ticket',
        'action',
        'performed_by',
        'notes',
        'ip_address',
        'created_at',
    )
    
    def ticket_link(self, obj):
        url = reverse('admin:support_supportticket_change', args=[obj.ticket.id])
        return format_html('<a href="{}">{}</a>', url, obj.ticket.reference_number)
    ticket_link.short_description = 'Ticket'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False