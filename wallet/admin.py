
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from django.utils import timezone
from decimal import Decimal
import json

from .models import MainWallet, WalletTransaction, PendingTransfer
from .services import AdminWalletService


from django.contrib import admin, messages as admin_messages
from django.utils.html import format_html
from .services import MpesaIntegrationService
import logging


from .services import WalletService
from notifications.models import UserNotificationHistory
from django.db.models import F

import csv
from django.http import HttpResponse



logger = logging.getLogger(__name__)



@admin.register(MainWallet)
class MainWalletAdmin(admin.ModelAdmin):
    """
    Admin interface for Main Wallets
    """
    list_display = [
        'user_link',
        'balance_display',
        'available_balance_display',
        'locked_balance_display',
        'status_badge',
        'currency',
        'last_transaction_date',
        'created_at',
    ]
    
    list_filter = [
        'status',
        'currency',
        'is_deleted',
        'created_at',
        'last_transaction_date',
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
    ]
    
    readonly_fields = [
        'user',
        'balance',
        'available_balance',
        'locked_balance',
        'total_deposited',
        'total_withdrawn',
        'created_at',
        'updated_at',
        'last_transaction_date',
        'transaction_summary',
        'recent_transactions_display',
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Balance Information', {
            'fields': (
                'balance',
                'available_balance',
                'locked_balance',
                'currency',
            )
        }),
        ('Status', {
            'fields': ('status', 'is_deleted', 'deleted_at')
        }),
        ('Statistics', {
            'fields': (
                'total_deposited',
                'total_withdrawn',
                'transaction_summary',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'last_transaction_date',
            )
        }),
        ('Recent Transactions', {
            'fields': ('recent_transactions_display',),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'freeze_selected_wallets',
        'unfreeze_selected_wallets',
        'export_wallet_summary',
    ]
    
    def user_link(self, obj):
        """Link to user's change page"""
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def balance_display(self, obj):
        """Display balance with color coding"""
        color = 'green' if obj.balance > 0 else 'red'
        return format_html(
            '<strong style="color: {};">{} {}</strong>',
            color,
            obj.currency,
            obj.balance
        )
    balance_display.short_description = 'Total Balance'
    
    def available_balance_display(self, obj):
        """Display available balance"""
        return format_html(
            '<span style="color: green;">{} {}</span>',
            obj.currency,
            obj.available_balance
        )
    available_balance_display.short_description = 'Available'
    
    def locked_balance_display(self, obj):
        """Display locked balance"""
        if obj.locked_balance > 0:
            return format_html(
                '<span style="color: orange;">{} {}</span>',
                obj.currency,
                obj.locked_balance
            )
        return format_html('<span style="color: gray;">0.00</span>')
    locked_balance_display.short_description = 'Locked'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'active': 'green',
            'frozen': 'orange',
            'suspended': 'red',
            'closed': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        
        badge = f'<span style="background-color: {color}; color: white; padding: 3px 10px; border-radius: 3px;">{obj.status.upper()}</span>'
        
        if obj.is_deleted:
            badge += ' <span style="background-color: red; color: white; padding: 3px 10px; border-radius: 3px;">DELETED</span>'
        
        return format_html(badge)
    status_badge.short_description = 'Status'
    
    def transaction_summary(self, obj):
        """Display transaction summary"""
        transactions = WalletTransaction.objects.filter(wallet=obj, status='completed')
        
        total_count = transactions.count()
        deposits = transactions.filter(
            transaction_type__in=['mpesa_deposit', 'transfer_from_mgr', 'transfer_from_goals']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        withdrawals = transactions.filter(
            transaction_type__in=['mpesa_withdraw', 'transfer_to_mgr', 'transfer_to_goals']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        html = f"""
        <div style="background: #f5f5f5; padding: 15px; border-radius: 5px;">
            <p><strong>Total Transactions:</strong> {total_count}</p>
            <p><strong>Total Deposits:</strong> <span style="color: green;">{obj.currency} {deposits}</span></p>
            <p><strong>Total Withdrawals:</strong> <span style="color: red;">{obj.currency} {withdrawals}</span></p>
            <p><strong>Net Flow:</strong> {obj.currency} {deposits - withdrawals}</p>
        </div>
        """
        return format_html(html)
    transaction_summary.short_description = 'Transaction Summary'
    
    def recent_transactions_display(self, obj):
        """Display recent transactions"""
        transactions = WalletTransaction.objects.filter(wallet=obj).order_by('-created_at')[:10]
        
        if not transactions:
            return format_html('<p>No transactions yet</p>')
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f0f0f0;"><th>Date</th><th>Type</th><th>Amount</th><th>Status</th><th>Reference</th></tr>'
        
        for txn in transactions:
            color = 'green' if txn.transaction_type in ['mpesa_deposit', 'transfer_from_mgr', 'transfer_from_goals'] else 'red'
            html += f'''
            <tr style="border-bottom: 1px solid #ddd;">
                <td>{txn.created_at.strftime('%Y-%m-%d %H:%M')}</td>
                <td>{txn.get_transaction_type_display()}</td>
                <td style="color: {color};">{txn.currency} {txn.amount}</td>
                <td>{txn.status}</td>
                <td><a href="/admin/wallet/wallettransaction/{txn.pk}/change/">{txn.reference_number}</a></td>
            </tr>
            '''
        
        html += '</table>'
        return format_html(html)
    recent_transactions_display.short_description = 'Recent Transactions'
    
    def freeze_selected_wallets(self, request, queryset):
        """Freeze selected wallets"""
        count = 0
        for wallet in queryset:
            if wallet.status == 'active':
                wallet.freeze()
                count += 1
        
        self.message_user(request, f'{count} wallet(s) frozen successfully.')
    freeze_selected_wallets.short_description = 'Freeze selected wallets'
    
    def unfreeze_selected_wallets(self, request, queryset):
        """Unfreeze selected wallets"""
        count = 0
        for wallet in queryset:
            if wallet.status == 'frozen':
                wallet.unfreeze()
                count += 1
        
        self.message_user(request, f'{count} wallet(s) unfrozen successfully.')
    unfreeze_selected_wallets.short_description = 'Unfreeze selected wallets'
    
    def export_wallet_summary(self, request, queryset):
        """Export wallet summary as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="wallet_summary.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Username', 'Email', 'Balance', 'Available', 'Locked',
            'Total Deposited', 'Total Withdrawn', 'Status', 'Created'
        ])
        
        for wallet in queryset:
            writer.writerow([
                wallet.user.username,
                wallet.user.email,
                wallet.balance,
                wallet.available_balance,
                wallet.locked_balance,
                wallet.total_deposited,
                wallet.total_withdrawn,
                wallet.status,
                wallet.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_wallet_summary.short_description = 'Export wallet summary (CSV)'
    
    def has_delete_permission(self, request, obj=None):
        """Prevent hard deletion of wallets"""
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    """
    Admin interface for Wallet Transactions
    """
    list_display = [
        'reference_number',
        'user_link',
        'transaction_type_badge',
        'amount_display',
        'status_badge',
        'related_app',
        'created_at',
    ]
    
    list_filter = [
        'transaction_type',
        'status',
        'related_app',
        'currency',
        'created_at',
        'completed_at',
    ]
    
    search_fields = [
        'reference_number',
        'idempotency_key',
        'mpesa_receipt_number',
        'wallet__user__username',
        'wallet__user__email',
        'description',
    ]
    
    readonly_fields = [
        'reference_number',
        'idempotency_key',
        'wallet',
        'transaction_type',
        'amount',
        'currency',
        'balance_before',
        'balance_after',
        'status',
        'mpesa_receipt_number',
        'related_app',
        'description',
        'metadata_display',
        'created_at',
        'updated_at',
        'completed_at',
        'processed_by',
    ]
    
    fieldsets = (
        ('Transaction Details', {
            'fields': (
                'reference_number',
                'idempotency_key',
                'wallet',
                'transaction_type',
                'amount',
                'currency',
            )
        }),
        ('Balance Information', {
            'fields': (
                'balance_before',
                'balance_after',
            )
        }),
        ('Status & Processing', {
            'fields': (
                'status',
                'processed_by',
            )
        }),
        ('External References', {
            'fields': (
                'mpesa_receipt_number',
                'related_app',
            )
        }),
        ('Additional Information', {
            'fields': (
                'description',
                'metadata_display',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'completed_at',
            )
        }),
    )
    
    actions = [
        'mark_as_completed',
        'mark_as_failed',
        'export_transactions',
    ]
    
    def user_link(self, obj):
        """Link to wallet's user"""
        url = reverse('admin:auth_user_change', args=[obj.wallet.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.wallet.user.username)
    user_link.short_description = 'User'
    
    def transaction_type_badge(self, obj):
        """Display transaction type as badge"""
        colors = {
            'mpesa_deposit': 'green',
            'mpesa_withdraw': 'blue',
            'transfer_to_mgr': 'orange',
            'transfer_from_mgr': 'teal',
            'transfer_to_goals': 'purple',
            'transfer_from_goals': 'indigo',
            'lock': 'gray',
            'unlock': 'lightgray',
            'adjustment': 'red',
            'migration': 'brown',
        }
        
        color = colors.get(obj.transaction_type, 'gray')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_transaction_type_display()
        )
    transaction_type_badge.short_description = 'Type'
    
    def amount_display(self, obj):
        """Display amount with color coding"""
        # Credit transactions (money in)
        if obj.transaction_type in ['mpesa_deposit', 'transfer_from_mgr', 'transfer_from_goals', 'unlock']:
            color = 'green'
            sign = '+'
        # Debit transactions (money out)
        else:
            color = 'red'
            sign = '-'
        
        return format_html(
            '<strong style="color: {};">{}{} {}</strong>',
            color,
            sign,
            obj.currency,
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        """Display status as badge"""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'reversed': 'gray',
        }
        
        color = colors.get(obj.status, 'gray')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def metadata_display(self, obj):
        """Display metadata as formatted JSON"""
        if not obj.metadata:
            return format_html('<p style="color: gray;">No metadata</p>')
        
        formatted = json.dumps(obj.metadata, indent=2)
        return format_html('<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px;">{}</pre>', formatted)
    metadata_display.short_description = 'Metadata'
    
    def mark_as_completed(self, request, queryset):
        """Mark selected transactions as completed"""
        count = queryset.update(
            status='completed',
            completed_at=timezone.now()
        )
        self.message_user(request, f'{count} transaction(s) marked as completed.')
    mark_as_completed.short_description = 'Mark as completed'
    
    def mark_as_failed(self, request, queryset):
        """Mark selected transactions as failed"""
        count = queryset.update(status='failed')
        self.message_user(request, f'{count} transaction(s) marked as failed.')
    mark_as_failed.short_description = 'Mark as failed'
    
    def export_transactions(self, request, queryset):
        """Export transactions as CSV"""
                
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Reference', 'User', 'Type', 'Amount', 'Currency', 
            'Status', 'Balance Before', 'Balance After', 'Date', 'M-Pesa Receipt'
        ])
        
        for txn in queryset:
            writer.writerow([
                txn.reference_number,
                txn.wallet.user.username,
                txn.get_transaction_type_display(),
                txn.amount,
                txn.currency,
                txn.status,
                txn.balance_before,
                txn.balance_after,
                txn.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                txn.mpesa_receipt_number or 'N/A'
            ])
        
        return response
    export_transactions.short_description = 'Export transactions (CSV)'
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of transaction records"""
        return False
    
    def has_add_permission(self, request):
        """Prevent manual creation of transactions (use services)"""
        return False


@admin.register(PendingTransfer)
class PendingTransferAdmin(admin.ModelAdmin):
    """
    Enhanced admin interface for Pending Transfers with M-Pesa integration
    """
    list_display = [
        'id',
        'user_link',
        'transfer_type_badge',
        'amount_display',
        'phone_number_display',  # NEW
        'kyc_status_display',    # NEW
        'status_badge',
        'auto_approved_badge',   # NEW
        'initiated_at',
    ]
    
    list_filter = [
        'transfer_type',
        'status',
        'auto_approved',         # NEW
        'initiated_at',
    ]
    
    search_fields = [
        'wallet__user__username',
        'wallet__user__email',
        'destination_app',
        'approval_notes',
    ]
    
    readonly_fields = [
        'wallet',
        'transfer_type',
        'amount',
        'destination_app',
        'destination_id',
        'wallet_transaction',
        'password_verified_at',
        'auto_approved',
        'initiated_at',
        'completed_at',
        'metadata_display',
        'transaction_link',  # NEW
    ]
    
    fields = [
        'wallet',
        'transfer_type',
        'amount',
        'destination_app',
        'destination_id',
        'status',
        'auto_approved',
        'password_verified_at',
        'wallet_transaction',
        'transaction_link',   # NEW
        'approved_by',
        'approval_notes',
        'initiated_at',
        'completed_at',
        'metadata_display',
    ]
    
    actions = [
        'approve_and_process_transfers',  # CHANGED
        'reject_transfers',
    ]
    
    # Show only pending transfers by default
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('status__exact'):
            # Default to showing pending transfers
            return qs.filter(status='pending')
        return qs
    
    def user_link(self, obj):
        """Link to wallet's user"""
        url = reverse('admin:auth_user_change', args=[obj.wallet.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.wallet.user.username)
    user_link.short_description = 'User'
    
    def transfer_type_badge(self, obj):
        """Display transfer type as badge"""
        colors = {
            'to_mgr': 'orange',
            'from_mgr': 'teal',
            'to_goals': 'purple',
            'from_goals': 'indigo',
            'mpesa_withdraw': 'blue',  # ADDED
        }
        
        color = colors.get(obj.transfer_type, 'gray')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_transfer_type_display()
        )
    transfer_type_badge.short_description = 'Type'
    
    def amount_display(self, obj):
        """Display amount"""
        return format_html('<strong>KES {}</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    
    def phone_number_display(self, obj):
        """Display phone number from metadata - NEW"""
        phone = obj.metadata.get('phone_number', '—')
        return format_html('<span style="font-family: monospace;">{}</span>', phone)
    phone_number_display.short_description = 'Phone Number'
    
    def kyc_status_display(self, obj):
        """Display KYC verification status - NEW"""
        from user_dashboard.kyc_utils import is_kyc_verified
        is_verified = is_kyc_verified(obj.wallet.user)
        
        if is_verified:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Verified</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Not Verified</span>'
            )
    kyc_status_display.short_description = 'KYC'
    
    def status_badge(self, obj):
        """Display status as badge"""
        colors = {
            'awaiting_password': 'gray',      # NEW
            'pending': 'orange',
            'approved': 'blue',
            'processing': 'lightblue',
            'completed': 'green',
            'rejected': 'red',
            'failed': 'darkred',
        }
        
        color = colors.get(obj.status, 'gray')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def auto_approved_badge(self, obj):
        """Show if transfer was auto-approved - NEW"""
        if obj.auto_approved:
            return format_html(
                '<span style="background-color: #e3f2fd; color: #1976d2; '
                'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
                'AUTO</span>'
            )
        return '—'
    auto_approved_badge.short_description = 'Auto'
    
    def transaction_link(self, obj):
        """Link to the wallet transaction - NEW"""
        if obj.wallet_transaction:
            url = reverse('admin:wallet_wallettransaction_change', 
                         args=[obj.wallet_transaction.pk])
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                url,
                obj.wallet_transaction.reference_number
            )
        return '—'
    transaction_link.short_description = 'Transaction Reference'
    
    def metadata_display(self, obj):
        """Display metadata as formatted JSON"""
        if not obj.metadata:
            return format_html('<p style="color: gray;">No metadata</p>')
        
        formatted = json.dumps(obj.metadata, indent=2)
        return format_html('<pre style="background: #f5f5f5; padding: 10px; border-radius: 5px;">{}</pre>', formatted)
    metadata_display.short_description = 'Metadata'
    
    def approve_and_process_transfers(self, request, queryset):
        """
        ENHANCED: Approve and immediately process M-Pesa withdrawals
        This triggers actual M-Pesa B2C disbursement
        """
                
        # Filter to only pending transfers
        pending_transfers = queryset.filter(
            status='pending',
            transfer_type='mpesa_withdraw'
        )
        
        if not pending_transfers.exists():
            self.message_user(
                request, 
                "No pending M-Pesa withdrawals selected.",
                level=admin_messages.WARNING
            )
            return
        
        approved_count = 0
        failed_count = 0
        
        for transfer in pending_transfers:
            try:
                # Step 1: Mark as approved
                transfer.approve(request.user, "Approved via admin action")
                
                # Step 2: Process M-Pesa disbursement
                phone_number = transfer.metadata.get('phone_number')
                
                if not phone_number:
                    transfer.fail(reason="No phone number in metadata")
                    failed_count += 1
                    logger.error(f"No phone number for pending transfer #{transfer.id}")
                    continue
                
                # Call the M-Pesa processing service
                success, message = MpesaIntegrationService.process_approved_withdrawal(
                    pending_transfer=transfer,
                    phone_number=phone_number
                )
                
                if success:
                    approved_count += 1
                    logger.info(f"Admin approved and processed withdrawal #{transfer.id}")
                    
                    # Update linked transaction status to completed
                    if transfer.wallet_transaction:
                        transfer.wallet_transaction.status = 'completed'
                        transfer.wallet_transaction.completed_at = timezone.now()
                        transfer.wallet_transaction.save()
                    
                    # Send notification to user
                    try:
                        UserNotificationHistory.objects.create(
                            user=transfer.wallet.user,
                            notification_title='Withdrawal Approved & Processed',
                            notification_body=(
                                f'Your withdrawal of KES {transfer.amount} has been approved '
                                f'and sent to {phone_number}. Check your M-Pesa shortly.'
                            )
                        )
                    except Exception as e:
                        logger.error(f"Failed to send notification: {e}")
                else:
                    failed_count += 1
                    logger.error(
                        f"M-Pesa processing failed for transfer #{transfer.id}: {message}"
                    )
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing transfer #{transfer.id}: {str(e)}")
        
        # Show summary message
        if approved_count > 0:
            self.message_user(
                request,
                f'{approved_count} withdrawal(s) approved and sent to M-Pesa successfully.',
                level=admin_messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                f'{failed_count} withdrawal(s) failed to process. Check logs for details.',
                level=admin_messages.ERROR
            )
    
    approve_and_process_transfers.short_description = 'Approve & Send to M-Pesa'

    def reject_transfers(self, request, queryset):
        """
        ENHANCED: Reject transfers and refund locked funds
        """
        
        
        pending_transfers = queryset.filter(status='pending')
        
        if not pending_transfers.exists():
            self.message_user(
                request,
                "No pending transfers selected.",
                level=admin_messages.WARNING
            )
            return
        
        refunded_count = 0
        failed_count = 0
        
        for transfer in pending_transfers:
            try:
                user = transfer.wallet.user
                amount = transfer.amount
                
                # Mark as rejected
                transfer.reject(request.user, "Rejected via admin action")
                
                # CRITICAL: Refund the locked funds back to available balance
                if transfer.wallet_transaction:
                    # Create refund transaction
                    refund_txn = WalletTransaction.objects.create(
                        wallet=transfer.wallet,
                        transaction_type='reversal',
                        amount=amount,
                        currency='KES',
                        balance_before=transfer.wallet.balance,
                        balance_after=transfer.wallet.balance + amount,
                        status='completed',
                        description=f"Refund for rejected withdrawal (Ref: {transfer.wallet_transaction.reference_number})",
                        metadata={
                            'original_transaction': transfer.wallet_transaction.reference_number,
                            'pending_transfer_id': transfer.id,
                            'reason': 'admin_rejection'
                        },
                        related_app='system',
                        completed_at=timezone.now()
                    )
                    
                    # Refund the funds using atomic F-expressions
                    MainWallet.objects.filter(pk=transfer.wallet.pk).update(
                        available_balance=F('available_balance') + amount,
                        balance=F('balance') + amount,
                        total_withdrawn=F('total_withdrawn') - amount,  # Reverse the withdrawal stat
                        last_transaction_date=timezone.now(),
                        updated_at=timezone.now()
                    )
                    
                    # Update original transaction status
                    transfer.wallet_transaction.status = 'reversed'
                    transfer.wallet_transaction.save()
                    
                    # Refresh wallet to verify refund
                    transfer.wallet.refresh_from_db()
                    
                    refunded_count += 1
                    logger.info(
                        f"Refunded KES {amount} for rejected transfer #{transfer.id}. "
                        f"New balance: KES {transfer.wallet.available_balance}"
                    )
                    
                    # Notify user
                    try:
                        UserNotificationHistory.objects.create(
                            user=user,
                            notification_title='Withdrawal Rejected - Funds Refunded',
                            notification_body=(
                                f'Your withdrawal request of KES {amount} was not approved. '
                                f'The full amount has been returned to your available balance. '
                                f'Refund reference: {refund_txn.reference_number}'
                            )
                        )
                    except Exception as e:
                        logger.error(f"Failed to send notification: {e}")
                else:
                    logger.warning(f"No transaction found for pending transfer #{transfer.id}")
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error rejecting transfer #{transfer.id}: {str(e)}\n{traceback.format_exc()}")
        
        # Summary messages
        if refunded_count > 0:
            self.message_user(
                request,
                f'{refunded_count} transfer(s) rejected and refunded successfully.',
                level=admin_messages.SUCCESS
            )
        
        if failed_count > 0:
            self.message_user(
                request,
                f'{failed_count} transfer(s) failed to process. Check logs for details.',
                level=admin_messages.ERROR
            )

    reject_transfers.short_description = 'Reject & Refund to User'
    