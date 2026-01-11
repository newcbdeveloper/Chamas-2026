from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """
    Admin interface for managing contact form submissions.
    """
    
    list_display = [
        'id',
        'name',
        'email',
        'subject',
        'created_at_formatted',
        'status_badge',
        'ip_address'
    ]
    
    list_filter = [
        'is_resolved',
        'created_at',
        'resolved_at'
    ]
    
    search_fields = [
        'name',
        'email',
        'subject',
        'message',
        'ip_address'
    ]
    
    readonly_fields = [
        'name',
        'email',
        'subject',
        'message',
        'created_at',
        'ip_address',
        'resolved_at',
        'resolved_by'
    ]
    
    fieldsets = (
        ('Message Details', {
            'fields': ('name', 'email', 'subject', 'message')
        }),
        ('Status', {
            'fields': ('is_resolved', 'resolved_at', 'resolved_by')
        }),
        ('Metadata', {
            'fields': ('created_at', 'ip_address'),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    actions = ['mark_as_resolved', 'mark_as_unresolved']
    
    change_list_template = "admin/contact/contactmessage/change_list.html"
    
    def created_at_formatted(self, obj):
        """Format the created_at timestamp."""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_formatted.short_description = 'Submitted'
    created_at_formatted.admin_order_field = 'created_at'
    
    def status_badge(self, obj):
        """Display a colored badge for the status."""
        if obj.is_resolved:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px; font-weight: bold;">RESOLVED</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 3px 10px; '
                'border-radius: 3px; font-size: 11px; font-weight: bold;">PENDING</span>'
            )
    status_badge.short_description = 'Status'
    
    def mark_as_resolved(self, request, queryset):
        """Bulk action to mark messages as resolved."""
        count = 0
        for message in queryset:
            if not message.is_resolved:
                message.mark_as_resolved(user=request.user)
                count += 1
        
        self.message_user(
            request,
            f'{count} message(s) marked as resolved.'
        )
    mark_as_resolved.short_description = 'Mark selected as resolved'
    
    def mark_as_unresolved(self, request, queryset):
        """Bulk action to mark messages as unresolved."""
        updated = queryset.update(
            is_resolved=False,
            resolved_at=None,
            resolved_by=None
        )
        
        self.message_user(
            request,
            f'{updated} message(s) marked as unresolved.'
        )
    mark_as_unresolved.short_description = 'Mark selected as unresolved'
    
    def has_add_permission(self, request):
        """Disable adding messages through admin (only through contact form)."""
        return False
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('resolved_by')