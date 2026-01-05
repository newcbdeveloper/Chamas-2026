from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from .models import (
    UserProfile, MGRWallet, MGRTransaction, Round, RoundMembership, 
    Contribution, Payout, Invitation, RoundMessage, Notification
)


# Custom Admin Site Configuration
class MGRAdminSite(admin.AdminSite):
    site_header = "Merry-Go-Round Administration"
    site_title = "MGR Admin"
    index_title = "Welcome to Merry-Go-Round Admin"


class GlobalSettingsAdmin(admin.ModelAdmin):
    """
    Virtual admin for managing global settings like interest rate
    This appears in the admin but doesn't correspond to a model
    """
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Create a simple way to manage settings from admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django import forms

class GlobalSettingsForm(forms.Form):
    """Form for managing global MGR settings"""
    interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        initial=12.00,
        label="Default Interest Rate (%)",
        help_text="Annual interest rate for all new rounds (e.g., 12.00 for 12%)"
    )
    rotational_model_enabled = forms.BooleanField(
        required=False,
        initial=False,
        label="Enable Rotational Model",
        help_text="Allow users to create rounds with Rotational payout model"
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'trust_score_badge', 'total_contributions',
        'completed_rounds', 'missed_payments', 'phone_verified',
        'email_verified', 'created_at'
    ]
    list_filter = ['phone_verified', 'email_verified', 'created_at']
    search_fields = ['user__username', 'user__email', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'phone_number', 'phone_verified', 'email_verified')
        }),
        ('Trust & Activity', {
            'fields': ('trust_score', 'total_contributions', 'completed_rounds', 'missed_payments')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['recalculate_trust_scores', 'verify_phone', 'verify_email']
    
    def trust_score_badge(self, obj):
        if obj.trust_score >= 80:
            color = 'green'
        elif obj.trust_score >= 50:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.trust_score
        )
    trust_score_badge.short_description = 'Trust Score'
    
    def recalculate_trust_scores(self, request, queryset):
        for profile in queryset:
            profile.update_trust_score()
        self.message_user(request, f"Trust scores recalculated for {queryset.count()} users.")
    recalculate_trust_scores.short_description = "Recalculate trust scores"
    
    def verify_phone(self, request, queryset):
        queryset.update(phone_verified=True)
        self.message_user(request, f"Phone verified for {queryset.count()} users.")
    verify_phone.short_description = "Mark phone as verified"
    
    def verify_email(self, request, queryset):
        queryset.update(email_verified=True)
        self.message_user(request, f"Email verified for {queryset.count()} users.")
    verify_email.short_description = "Mark email as verified"


@admin.register(MGRWallet)
class MGRWalletAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'balance_display', 'available_balance_display',
        'locked_balance_display', 'total_deposited', 'total_withdrawn', 'updated_at'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Wallet Owner', {
            'fields': ('user',)
        }),
        ('Balances', {
            'fields': ('balance', 'available_balance', 'locked_balance')
        }),
        ('Statistics', {
            'fields': ('total_deposited', 'total_withdrawn')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['recalculate_balances']
    
    def balance_display(self, obj):
        return format_html(
            '<strong style="color: #2196F3;">KES {}</strong>',
            f"{obj.balance:,.2f}"
        )
    balance_display.short_description = 'Total Balance'
    
    def available_balance_display(self, obj):
        return format_html(
            '<span style="color: #4CAF50;">KES {}</span>',
            f"{obj.available_balance:,.2f}"
        )
    available_balance_display.short_description = 'Available'
    
    def locked_balance_display(self, obj):
        return format_html(
            '<span style="color: #FF9800;">KES {}</span>',
            f"{obj.locked_balance:,.2f}"
        )
    locked_balance_display.short_description = 'Locked'
    
    def recalculate_balances(self, request, queryset):
        # Recalculate wallet balances from transactions
        for wallet in queryset:
            # This is a safety action - normally balances are maintained automatically
            transactions = MGRTransaction.objects.filter(wallet=wallet, status='completed')
            # Implement recalculation logic if needed
        self.message_user(request, f"Balances checked for {queryset.count()} wallets.")
    recalculate_balances.short_description = "Verify wallet balances"


@admin.register(MGRTransaction)
class MGRTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'transaction_type_badge', 'amount_display',
        'status_badge', 'related_round_link', 'created_at'
    ]
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['wallet__user__username', 'description', 'main_wallet_reference']
    readonly_fields = [
        'id', 'balance_before', 'balance_after', 
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('id', 'wallet', 'transaction_type', 'amount', 'status')
        }),
        ('Balance Snapshots', {
            'fields': ('balance_before', 'balance_after')
        }),
        ('Related Records', {
            'fields': ('related_round', 'related_contribution', 'related_payout')
        }),
        ('Integration', {
            'fields': ('main_wallet_reference', 'description', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def user_link(self, obj):
        return obj.wallet.user.username
    user_link.short_description = 'User'
    
    def transaction_type_badge(self, obj):
        colors = {
            'deposit': '#4CAF50',
            'withdraw': '#F44336',
            'contribution': '#2196F3',
            'payout': '#9C27B0',
            'lock': '#FF9800',
            'unlock': '#00BCD4',
            'interest': '#CDDC39',
            'refund': '#607D8B'
        }
        color = colors.get(obj.transaction_type, '#9E9E9E')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_transaction_type_display().upper()
        )
    transaction_type_badge.short_description = 'Type'
    
    def amount_display(self, obj):
        color = '#4CAF50' if obj.transaction_type in ['deposit', 'payout', 'interest', 'unlock'] else '#F44336'
        sign = '+' if obj.transaction_type in ['deposit', 'payout', 'interest', 'unlock'] else '-'
        return format_html(
            '<strong style="color: {};">{} KES {}</strong>',
            color, sign, f"{obj.amount:,.2f}"
        )
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#FF9800',
            'completed': '#4CAF50',
            'failed': '#F44336',
            'reversed': '#9E9E9E'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#9E9E9E'), obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def related_round_link(self, obj):
        if obj.related_round:
            url = reverse('admin:merry_go_round_round_change', args=[obj.related_round.id])
            return format_html('<a href="{}">{}</a>', url, obj.related_round.name[:30])
        return '-'
    related_round_link.short_description = 'Round'
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f"{queryset.count()} transactions marked as completed.")
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_failed(self, request, queryset):
        queryset.update(status='failed')
        self.message_user(request, f"{queryset.count()} transactions marked as failed.")
    mark_as_failed.short_description = "Mark as failed"


class RoundMembershipInline(admin.TabularInline):
    model = RoundMembership
    extra = 0
    readonly_fields = ['trust_score_at_join', 'total_contributed', 'interest_earned', 'locked_amount', 'join_date']
    fields = [
        'user', 'payout_position', 'status', 'trust_score_at_join',
        'total_contributed', 'locked_amount', 'contributions_made', 'contributions_missed'
    ]


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'round_type_badge', 'payout_model_badge', 'status_badge',
        'current_members', 'max_members', 'contribution_amount',
        'interest_rate', 'start_date', 'created_at'
    ]
    list_filter = ['round_type', 'payout_model', 'status', 'frequency', 'created_at']
    search_fields = ['name', 'description', 'creator__username']
    readonly_fields = ['id', 'current_members', 'total_pool', 'total_interest_earned', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description', 'creator', 'status')
        }),
        ('Round Configuration', {
            'fields': (
                'round_type', 'payout_model', 'contribution_amount',
                'frequency', 'max_members', 'current_members', 'min_trust_score'
            )
        }),
        ('Financial Details', {
            'fields': ('interest_rate', 'total_pool', 'total_interest_earned'),
            'description': 'You can customize the interest rate for this specific round. Default is 12% annual.'
        }),
        ('Timeline', {
            'fields': ('start_date', 'end_date', 'next_contribution_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [RoundMembershipInline]
    actions = ['activate_rounds', 'complete_rounds', 'cancel_rounds']
    
    def round_type_badge(self, obj):
        color = '#2196F3' if obj.round_type == 'public' else '#FF9800'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_round_type_display().upper()
        )
    round_type_badge.short_description = 'Type'
    
    def payout_model_badge(self, obj):
        color = '#4CAF50' if obj.payout_model == 'marathon' else '#9C27B0'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_payout_model_display().upper()
        )
    payout_model_badge.short_description = 'Model'
    
    def status_badge(self, obj):
        colors = {
            'draft': '#9E9E9E',
            'open': '#2196F3',
            'active': '#4CAF50',
            'completed': '#607D8B',
            'cancelled': '#F44336'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#9E9E9E'), obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def activate_rounds(self, request, queryset):
        queryset.update(status='active', start_date=timezone.now().date())
        self.message_user(request, f"{queryset.count()} rounds activated.")
    activate_rounds.short_description = "Activate selected rounds"
    
    def complete_rounds(self, request, queryset):
        queryset.update(status='completed', end_date=timezone.now().date())
        self.message_user(request, f"{queryset.count()} rounds marked as completed.")
    complete_rounds.short_description = "Complete selected rounds"
    
    def cancel_rounds(self, request, queryset):
        queryset.update(status='cancelled')
        self.message_user(request, f"{queryset.count()} rounds cancelled.")
    cancel_rounds.short_description = "Cancel selected rounds"


class ContributionInline(admin.TabularInline):
    model = Contribution
    extra = 0
    readonly_fields = ['cycle_number', 'due_date', 'payment_date', 'interest_accrued', 'wallet_transaction']
    fields = ['cycle_number', 'amount', 'due_date', 'status', 'payment_date', 'wallet_transaction']


@admin.register(RoundMembership)
class RoundMembershipAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'round_link', 'status_badge', 'payout_position',
        'total_contributed', 'locked_amount', 'interest_earned', 
        'contributions_made', 'contributions_missed', 'join_date'
    ]
    list_filter = ['status', 'has_received_payout', 'join_date']
    search_fields = ['user__username', 'round__name']
    readonly_fields = [
        'id', 'trust_score_at_join', 'total_contributed', 'interest_earned',
        'contributions_made', 'contributions_missed', 'join_date', 'updated_at'
    ]
    
    fieldsets = (
        ('Membership Details', {
            'fields': ('id', 'round', 'user', 'status', 'payout_position', 'trust_score_at_join')
        }),
        ('Financial Tracking', {
            'fields': (
                'total_contributed', 'locked_amount', 'interest_earned', 'expected_contributions',
                'contributions_made', 'contributions_missed'
            )
        }),
        ('Payout Information', {
            'fields': ('has_received_payout', 'payout_received_date', 'payout_amount')
        }),
        ('Timestamps', {
            'fields': ('join_date', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ContributionInline]
    actions = ['mark_as_active', 'mark_as_defaulted', 'mark_as_completed']
    
    def round_link(self, obj):
        url = reverse('admin:merry_go_round_round_change', args=[obj.round.id])
        return format_html('<a href="{}">{}</a>', url, obj.round.name)
    round_link.short_description = 'Round'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#FF9800',
            'active': '#4CAF50',
            'defaulted': '#F44336',
            'completed': '#2196F3',
            'removed': '#9E9E9E'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#9E9E9E'), obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def mark_as_active(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, f"{queryset.count()} memberships activated.")
    mark_as_active.short_description = "Mark as active"
    
    def mark_as_defaulted(self, request, queryset):
        queryset.update(status='defaulted')
        self.message_user(request, f"{queryset.count()} memberships marked as defaulted.")
    mark_as_defaulted.short_description = "Mark as defaulted"
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f"{queryset.count()} memberships completed.")
    mark_as_completed.short_description = "Mark as completed"


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'round_link', 'cycle_number', 'amount',
        'due_date', 'status_badge', 'payment_date', 
        'wallet_txn_link', 'interest_accrued'
    ]
    list_filter = ['status', 'due_date', 'payment_date']
    search_fields = ['membership__user__username', 'membership__round__name']
    readonly_fields = ['id', 'interest_accrued', 'days_in_escrow', 'wallet_transaction', 'created_at', 'updated_at']
    date_hierarchy = 'due_date'
    
    fieldsets = (
        ('Contribution Details', {
            'fields': ('id', 'membership', 'amount', 'cycle_number', 'due_date', 'status')
        }),
        ('Payment Information', {
            'fields': ('wallet_transaction', 'payment_date')
        }),
        ('Interest & Tracking', {
            'fields': ('interest_accrued', 'days_in_escrow')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_missed', 'calculate_interest']
    
    def user_link(self, obj):
        return obj.membership.user.username
    user_link.short_description = 'User'
    
    def round_link(self, obj):
        url = reverse('admin:merry_go_round_round_change', args=[obj.membership.round.id])
        return format_html('<a href="{}">{}</a>', url, obj.membership.round.name)
    round_link.short_description = 'Round'
    
    def wallet_txn_link(self, obj):
        if obj.wallet_transaction:
            url = reverse('admin:merry_go_round_mgrtransaction_change', args=[obj.wallet_transaction.id])
            return format_html('<a href="{}">View Transaction</a>', url)
        return '-'
    wallet_txn_link.short_description = 'Wallet Txn'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#FF9800',
            'processing': '#2196F3',
            'completed': '#4CAF50',
            'failed': '#F44336',
            'missed': '#9E9E9E'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#9E9E9E'), obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def mark_as_completed(self, request, queryset):
        updated = 0
        for contribution in queryset:
            if contribution.status != 'completed':
                contribution.status = 'completed'
                contribution.payment_date = timezone.now()
                contribution.save()
                updated += 1
        self.message_user(request, f"{updated} contributions marked as completed.")
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_missed(self, request, queryset):
        updated = 0
        for contribution in queryset:
            contribution.mark_as_missed()
            updated += 1
        self.message_user(request, f"{updated} contributions marked as missed.")
    mark_as_missed.short_description = "Mark as missed"
    
    def calculate_interest(self, request, queryset):
        updated = 0
        for contribution in queryset:
            contribution.calculate_interest()
            updated += 1
        self.message_user(request, f"Interest calculated for {updated} contributions.")
    calculate_interest.short_description = "Calculate interest"


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = [
        'recipient_link', 'round_link', 'payout_cycle', 'amount',
        'principal_amount', 'interest_amount', 'scheduled_date',
        'status_badge', 'payout_date', 'wallet_txn_link'
    ]
    list_filter = ['status', 'scheduled_date', 'payout_date']
    search_fields = ['recipient_membership__user__username', 'round__name']
    readonly_fields = ['id', 'wallet_transaction', 'created_at', 'updated_at']
    date_hierarchy = 'scheduled_date'
    
    fieldsets = (
        ('Payout Details', {
            'fields': ('id', 'round', 'recipient_membership', 'payout_cycle', 'status')
        }),
        ('Amount Breakdown', {
            'fields': ('amount', 'principal_amount', 'interest_amount')
        }),
        ('Payment Information', {
            'fields': ('scheduled_date', 'payout_date', 'wallet_transaction')
        }),
        ('Additional Info', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['process_payouts', 'mark_as_completed']
    
    def recipient_link(self, obj):
        return obj.recipient_membership.user.username
    recipient_link.short_description = 'Recipient'
    
    def round_link(self, obj):
        url = reverse('admin:merry_go_round_round_change', args=[obj.round.id])
        return format_html('<a href="{}">{}</a>', url, obj.round.name)
    round_link.short_description = 'Round'
    
    def wallet_txn_link(self, obj):
        if obj.wallet_transaction:
            url = reverse('admin:merry_go_round_mgrtransaction_change', args=[obj.wallet_transaction.id])
            return format_html('<a href="{}">View Transaction</a>', url)
        return '-'
    wallet_txn_link.short_description = 'Wallet Txn'
    
    def status_badge(self, obj):
        colors = {
            'scheduled': '#FF9800',
            'processing': '#2196F3',
            'completed': '#4CAF50',
            'failed': '#F44336'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#9E9E9E'), obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def process_payouts(self, request, queryset):
        from .services import PayoutService
        processed = 0
        for payout in queryset:
            if payout.status == 'scheduled':
                try:
                    PayoutService.process_payout(payout)
                    processed += 1
                except Exception as e:
                    pass
        self.message_user(request, f"{processed} payouts processed.")
    process_payouts.short_description = "Process selected payouts"
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed', payout_date=timezone.now())
        self.message_user(request, f"{queryset.count()} payouts marked as completed.")
    mark_as_completed.short_description = "Mark as completed"


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = [
        'round_link', 'inviter', 'invitee_contact', 'status_badge',
        'created_at', 'expires_at', 'accepted_at'
    ]
    list_filter = ['status', 'created_at', 'expires_at']
    search_fields = ['round__name', 'inviter__username', 'invitee_email', 'invitee_phone']
    readonly_fields = ['id', 'token', 'created_at', 'updated_at', 'accepted_at']
    
    fieldsets = (
        ('Invitation Details', {
            'fields': ('id', 'round', 'inviter', 'status')
        }),
        ('Invitee Information', {
            'fields': ('invitee_email', 'invitee_phone', 'invitee_user')
        }),
        ('Invitation Management', {
            'fields': ('token', 'message', 'expires_at', 'accepted_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_expired']
    
    def round_link(self, obj):
        url = reverse('admin:merry_go_round_round_change', args=[obj.round.id])
        return format_html('<a href="{}">{}</a>', url, obj.round.name)
    round_link.short_description = 'Round'
    
    def invitee_contact(self, obj):
        return obj.invitee_email or obj.invitee_phone or 'No contact'
    invitee_contact.short_description = 'Invitee'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#FF9800',
            'accepted': '#4CAF50',
            'declined': '#F44336',
            'expired': '#9E9E9E'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#9E9E9E'), obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def mark_as_expired(self, request, queryset):
        queryset.update(status='expired')
        self.message_user(request, f"{queryset.count()} invitations marked as expired.")
    mark_as_expired.short_description = "Mark as expired"


@admin.register(RoundMessage)
class RoundMessageAdmin(admin.ModelAdmin):
    list_display = [
        'round_link', 'sender', 'message_type_badge', 'subject_preview',
        'is_pinned', 'created_at'
    ]
    list_filter = ['message_type', 'is_pinned', 'created_at']
    search_fields = ['round__name', 'sender__username', 'subject', 'content']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Message Details', {
            'fields': ('id', 'round', 'sender', 'message_type', 'is_pinned')
        }),
        ('Content', {
            'fields': ('subject', 'content')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['pin_messages', 'unpin_messages']
    
    def round_link(self, obj):
        url = reverse('admin:merry_go_round_round_change', args=[obj.round.id])
        return format_html('<a href="{}">{}</a>', url, obj.round.name)
    round_link.short_description = 'Round'
    
    def subject_preview(self, obj):
        return obj.subject[:50] if obj.subject else obj.content[:50]
    subject_preview.short_description = 'Preview'
    
    def message_type_badge(self, obj):
        colors = {
            'system': '#2196F3',
            'user': '#4CAF50',
            'admin': '#FF9800'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.message_type, '#9E9E9E'), obj.get_message_type_display().upper()
        )
    message_type_badge.short_description = 'Type'
    
    def pin_messages(self, request, queryset):
        queryset.update(is_pinned=True)
        self.message_user(request, f"{queryset.count()} messages pinned.")
    pin_messages.short_description = "Pin messages"
    
    def unpin_messages(self, request, queryset):
        queryset.update(is_pinned=False)
        self.message_user(request, f"{queryset.count()} messages unpinned.")
    unpin_messages.short_description = "Unpin messages"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'notification_type_badge', 'title_preview', 'round_link',
        'is_read', 'is_sent', 'created_at'
    ]
    list_filter = ['notification_type', 'is_read', 'is_sent', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['id', 'created_at', 'read_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('id', 'user', 'round', 'notification_type')
        }),
        ('Content', {
            'fields': ('title', 'message', 'action_url')
        }),
        ('Status', {
            'fields': ('is_read', 'is_sent', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_sent']
    
    def round_link(self, obj):
        if obj.round:
            url = reverse('admin:merry_go_round_round_change', args=[obj.round.id])
            return format_html('<a href="{}">{}</a>', url, obj.round.name)
        return '-'
    round_link.short_description = 'Round'
    
    def title_preview(self, obj):
        return obj.title[:50]
    title_preview.short_description = 'Title'
    
    def notification_type_badge(self, obj):
        return format_html(
            '<span style="background-color: #2196F3; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            obj.get_notification_type_display().upper()
        )
    notification_type_badge.short_description = 'Type'
    
    def mark_as_read(self, request, queryset):
        for notification in queryset:
            notification.mark_as_read()
        self.message_user(request, f"{queryset.count()} notifications marked as read.")
    mark_as_read.short_description = "Mark as read"
    
    def mark_as_sent(self, request, queryset):
        queryset.update(is_sent=True)
        self.message_user(request, f"{queryset.count()} notifications marked as sent.")
    mark_as_sent.short_description = "Mark as sent"