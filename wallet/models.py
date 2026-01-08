from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid

class MainWallet(models.Model):
    """
    Main ChamaSpace Wallet - Central financial hub for all user transactions
    One wallet per user that manages funds for MGR, Goals, and other apps
    """
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('frozen', 'Frozen'),
        ('suspended', 'Suspended'),
        ('closed', 'Closed'),
    )
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='main_wallet'
    )
    
    # Balance fields
    balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total balance (available + locked)"
    )
    available_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Balance available for use/withdrawal"
    )
    locked_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Balance locked for pending operations"
    )
    
    # Currency support (future-proofing)
    currency = models.CharField(
        max_length=3,
        default='KES',
        help_text="ISO 4217 currency code"
    )
    
    # Wallet status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Wallet operational status"
    )
    
    # Lifetime statistics
    total_deposited = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount deposited (all time)"
    )
    total_withdrawn = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount withdrawn (all time)"
    )
    
    # Soft deletion
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag for audit trail"
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_transaction_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Main Wallet"
        verbose_name_plural = "Main Wallets"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(balance__gte=0),
                name='wallet_balance_non_negative'
            ),
        ]
    
    def __str__(self):
        return f"{self.user.username}'s Wallet - {self.currency} {self.balance}"
    
    def clean(self):
        """Validate balance invariant: balance = available + locked"""
        super().clean()
        expected_balance = self.available_balance + self.locked_balance
        if abs(self.balance - expected_balance) > Decimal('0.01'):  # Allow 1 cent tolerance
            raise ValidationError(
                f"Balance invariant violated: balance ({self.balance}) != "
                f"available ({self.available_balance}) + locked ({self.locked_balance})"
            )
    
    def save(self, *args, **kwargs):
        """Enforce balance invariant on save"""
        self.full_clean()  # This calls clean() to validate
        super().save(*args, **kwargs)
    
    def is_active(self):
        """Check if wallet is active and can perform transactions"""
        return self.status == 'active' and not self.is_deleted
    
    def freeze(self, reason=None):
        """Freeze wallet (prevent all transactions)"""
        self.status = 'frozen'
        self.save()
        return True
    
    def unfreeze(self):
        """Unfreeze wallet"""
        self.status = 'active'
        self.save()
        return True
    
    def soft_delete(self):
        """Soft delete wallet (audit trail preserved)"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.status = 'closed'
        self.save()
        return True
    
    # NOTE: add_funds(), deduct_funds(), lock_funds(), unlock_funds() 
    # are now handled in services.py using F-expressions for atomic updates


class WalletTransaction(models.Model):
    """
    Records all wallet transactions for audit trail and history
    """
    TRANSACTION_TYPES = (
        ('mpesa_deposit', 'M-Pesa Deposit'),
        ('mpesa_withdraw', 'M-Pesa Withdrawal'),
        ('transfer_to_mgr', 'Transfer to MGR Wallet'),
        ('transfer_from_mgr', 'Transfer from MGR Wallet'),
        ('transfer_to_goals', 'Transfer to Goals'),
        ('transfer_from_goals', 'Transfer from Goals'),
        ('lock', 'Funds Locked'),
        ('unlock', 'Funds Unlocked'),
        ('adjustment', 'Admin Adjustment'),
        ('migration', 'Balance Migration'),
        ('reversal', 'Transaction Reversal'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    )
    
    RELATED_APP_CHOICES = (
        ('mgr', 'Merry-Go-Round'),
        ('goals', 'Wekeza Goals'),
        ('chamaz', 'Chamaz'),
        ('system', 'System'),
    )
    
    # Transaction identification
    reference_number = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        help_text="Unique transaction reference"
    )
    
    # Idempotency key (prevents duplicate processing)
    idempotency_key = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Client-provided or M-Pesa receipt for idempotent operations"
    )
    
    wallet = models.ForeignKey(
        MainWallet, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    
    # Transaction details
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]  # Must be positive
    )
    
    # Currency
    currency = models.CharField(
        max_length=3,
        default='KES',
        help_text="ISO 4217 currency code"
    )
    
    # Balance tracking
    balance_before = models.DecimalField(max_digits=15, decimal_places=2)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # External references
    mpesa_receipt_number = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        db_index=True,
        help_text="M-Pesa transaction receipt"
    )
    related_app = models.CharField(
        max_length=20, 
        choices=RELATED_APP_CHOICES, 
        null=True, 
        blank=True
    )
    
    # Additional info
    description = models.TextField(blank=True, null=True)
    metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Additional transaction data (Goal ID, Round ID, etc.)"
    )
    
    # Admin fields
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_transactions',
        help_text="Admin who processed this transaction"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Wallet Transaction"
        verbose_name_plural = "Wallet Transactions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['idempotency_key']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['status']),
            models.Index(fields=['mpesa_receipt_number']),
        ]
    
    def __str__(self):
        return f"{self.reference_number} - {self.get_transaction_type_display()} - {self.currency} {self.amount}"
    
    def clean(self):
        """Validate transaction amount is positive"""
        super().clean()
        if self.amount <= 0:
            raise ValidationError("Transaction amount must be greater than zero")
    
    def save(self, *args, **kwargs):
        # 1. Generate reference_number FIRST – before any validation
        if not self.reference_number:
            self.reference_number = self.generate_reference_number()

        # 2. Set completed_at if status is completed
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()

        # 3. Now validate (reference_number is no longer blank)
        self.full_clean()

        # 4. Finally save
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_reference_number():
        """Generate unique transaction reference"""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4().hex)[:8].upper()
        return f"CSTXN-{timestamp}-{unique_id}"
    
    def mark_completed(self):
        """Mark transaction as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, reason=None):
        """Mark transaction as failed"""
        self.status = 'failed'
        if reason:
            self.description = f"{self.description}\nFailed: {reason}" if self.description else f"Failed: {reason}"
        self.save()


class PendingTransfer(models.Model):
    """
    Tracks pending transfers between main wallet and other apps
    Used for async operations and manual approval workflows
    
    ENHANCED FOR WITHDRAWAL SECURITY:
    - Password verification tracking
    - Auto-approval for amounts under threshold
    - Enhanced status tracking
    """
    TRANSFER_TYPES = (
        ('to_mgr', 'To MGR Wallet'),
        ('from_mgr', 'From MGR Wallet'),
        ('to_goals', 'To Goals'),
        ('from_goals', 'From Goals'),
        ('mpesa_withdraw', 'M-Pesa Withdrawal'),
    )
    
    STATUS_CHOICES = (
        ('awaiting_password', 'Awaiting Password Verification'),
        ('pending', 'Pending Admin Approval'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),
    )
    
    wallet = models.ForeignKey(
        MainWallet, 
        on_delete=models.CASCADE, 
        related_name='pending_transfers'
    )
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPES)
    amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    destination_app = models.CharField(max_length=50)
    destination_id = models.IntegerField(
        null=True, 
        blank=True,
        help_text="ID of Goal, Round, etc."
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='awaiting_password'
    )
    
    # Related transaction
    wallet_transaction = models.ForeignKey(
        WalletTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_transfer'
    )
    # Unique UUID reference for the pending transfer
    reference_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="UUID reference for the Daraja's OriginatorConversationID"
    )
    
    # ENHANCED SECURITY FIELDS
    requires_password_verification = models.BooleanField(
        default=True,
        help_text="Whether this transfer requires password verification"
    )
    password_verified_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp when password was verified"
    )
    auto_approved = models.BooleanField(
        default=False,
        help_text="True if transfer was auto-approved (amount under threshold)"
    )
    
    # Approval workflow
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_transfers'
    )
    approval_notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional data
    metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Includes phone_number, withdrawal_method, KYC status, etc."
    )
    # Raw JSON response from M-Pesa callback (B2C ResultURL)
    raw_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw JSON response received from the M-Pesa callback"
    )
    
    class Meta:
        verbose_name = "Pending Transfer"
        verbose_name_plural = "Pending Transfers"
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['wallet', 'status']),
            models.Index(fields=['-initiated_at']),
            models.Index(fields=['status', 'auto_approved']),
            models.Index(fields=['amount']),  # For filtering by threshold
        ]
    
    def __str__(self):
        return f"{self.get_transfer_type_display()} - KES {self.amount} - {self.status}"
    
    def is_password_verified(self):
        """Check if password has been verified"""
        return self.password_verified_at is not None
    
    def requires_admin_approval(self):
        """Check if this transfer requires admin approval"""
        # Amounts over KES 2,000 require admin approval
        APPROVAL_THRESHOLD = Decimal('2000.00')
        return self.amount > APPROVAL_THRESHOLD
    
    def can_auto_approve(self):
        """Check if this transfer can be auto-approved"""
        return (
            self.is_password_verified() and 
            not self.requires_admin_approval() and
            self.status in ['awaiting_password', 'pending']
        )
    
    def verify_password(self):
        """Mark password as verified and update status"""
        self.password_verified_at = timezone.now()
        self.requires_password_verification = False
        
        # If amount is under threshold, auto-approve
        if self.can_auto_approve():
            self.status = 'approved'
            self.auto_approved = True
            self.approval_notes = "Auto-approved (amount under KES 2,000 threshold)"
        else:
            # Otherwise, set to pending admin approval
            self.status = 'pending'
            self.auto_approved = False
        
        self.save()
    
    def approve(self, admin_user, notes=None):
        """Approve the transfer (admin action)"""
        self.status = 'approved'
        self.approved_by = admin_user
        if notes:
            self.approval_notes = notes
        else:
            self.approval_notes = f"Approved by admin: {admin_user.username}"
        self.save()
    
    def reject(self, admin_user, reason):
        """Reject the transfer (admin action)"""
        self.status = 'rejected'
        self.approved_by = admin_user
        self.approval_notes = reason
        self.save()
    
    def complete(self):
        """Mark transfer as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def fail(self, reason=None):
        """Mark transfer as failed"""
        self.status = 'failed'
        if reason:
            self.approval_notes = f"{self.approval_notes}\n\nFailed: {reason}" if self.approval_notes else f"Failed: {reason}"
        self.save()
    
    def get_status_display_with_icon(self):
        """Get status with appropriate icon for display"""
        status_icons = {
            'awaiting_password': '🔐',
            'pending': '⏳',
            'approved': '✅',
            'processing': '⚙️',
            'completed': '✔️',
            'rejected': '❌',
            'failed': '⚠️',
        }
        icon = status_icons.get(self.status, '•')
        return f"{icon} {self.get_status_display()}"
    
    def get_approval_type_display(self):
        """Get human-readable approval type"""
        if self.auto_approved:
            return "Auto-approved (under threshold)"
        elif self.approved_by:
            return f"Manually approved by {self.approved_by.username}"
        else:
            return "Pending approval"