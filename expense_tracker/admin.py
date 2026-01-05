from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Transaction, RecurringTransaction, Budget, UserPreferences, Insight


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'icon_display', 'color_display', 'is_default', 'user']
    list_filter = ['type', 'is_default']
    search_fields = ['name', 'user__username']
    list_per_page = 25
    
    def icon_display(self, obj):
        return format_html('<span style="font-size: 20px;">{}</span>', obj.icon)
    icon_display.short_description = 'Icon'
    
    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; padding: 5px 15px; color: white; border-radius: 3px;">{}</span>',
            obj.color,
            obj.color
        )
    color_display.short_description = 'Color'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'category', 'amount_display', 'date', 'time', 'is_recurring']
    list_filter = ['type', 'is_recurring', 'date', 'category']
    search_fields = ['user__username', 'description', 'category__name']
    date_hierarchy = 'date'
    list_per_page = 50
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('user', 'type', 'category', 'amount', 'description')
        }),
        ('Date & Time', {
            'fields': ('date', 'time')
        }),
        ('Recurring', {
            'fields': ('is_recurring', 'recurring_transaction')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_display(self, obj):
        color = 'green' if obj.type == 'income' else 'red'
        sign = '+' if obj.type == 'income' else '-'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} KSh {:,.2f}</span>',
            color,
            sign,
            obj.amount
        )
    amount_display.short_description = 'Amount'


@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'category', 'amount', 'frequency', 'next_occurrence', 'is_active']
    list_filter = ['type', 'frequency', 'is_active']
    search_fields = ['user__username', 'description', 'category__name']
    list_per_page = 25
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('user', 'type', 'category', 'amount', 'description')
        }),
        ('Recurrence Settings', {
            'fields': ('frequency', 'start_date', 'end_date', 'next_occurrence', 'is_active', 'auto_generate')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_recurring', 'deactivate_recurring']
    
    def activate_recurring(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} recurring transaction(s) activated.')
    activate_recurring.short_description = 'Activate selected recurring transactions'
    
    def deactivate_recurring(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} recurring transaction(s) deactivated.')
    deactivate_recurring.short_description = 'Deactivate selected recurring transactions'


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'amount', 'period', 'usage_display', 'is_active']
    list_filter = ['period', 'is_active', 'rollover_enabled']
    search_fields = ['user__username', 'category__name']
    list_per_page = 25
    readonly_fields = ['created_at', 'updated_at', 'spent_amount', 'remaining_amount', 'percentage_used']
    
    fieldsets = (
        ('Budget Details', {
            'fields': ('user', 'category', 'amount', 'period')
        }),
        ('Settings', {
            'fields': ('start_date', 'rollover_enabled', 'rollover_amount', 'alert_threshold', 'is_active')
        }),
        ('Current Status', {
            'fields': ('spent_amount', 'remaining_amount', 'percentage_used'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def spent_amount(self, obj):
        return f"KSh {obj.get_spent_amount():,.2f}"
    spent_amount.short_description = 'Spent This Period'
    
    def remaining_amount(self, obj):
        remaining = obj.get_remaining_amount()
        color = 'green' if remaining > 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">KSh {:,.2f}</span>',
            color,
            remaining
        )
    remaining_amount.short_description = 'Remaining'
    
    def percentage_used(self, obj):
        percentage = obj.get_percentage_used()
        if percentage < 50:
            color = 'green'
        elif percentage < 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color,
            percentage
        )
    percentage_used.short_description = 'Usage %'
    
    def usage_display(self, obj):
        percentage = obj.get_percentage_used()
        if percentage < 50:
            color = '#27ae60'  # Green
        elif percentage < 80:
            color = '#f39c12'  # Orange
        else:
            color = '#e74c3c'  # Red
        
        return format_html(
            '<div style="width: 100px; background-color: #ecf0f1; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; height: 20px; text-align: center; color: white; font-size: 11px; line-height: 20px;">'
            '{:.0f}%'
            '</div></div>',
            min(percentage, 100),
            color,
            percentage
        )
    usage_display.short_description = 'Usage'


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'currency', 'date_format', 'theme', 'email_notifications', 'budget_alerts']
    list_filter = ['currency', 'theme', 'email_notifications', 'budget_alerts']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'title', 'category', 'is_read', 'created_at']
    list_filter = ['type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    date_hierarchy = 'created_at'
    list_per_page = 50
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'category')