from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
from django.urls import reverse


class UserProfile(models.Model):
    """Extended user profile for merry-go-round specific data"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mgr_profile')
    trust_score = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Trust score from 0-100 based on payment history"
    )
    total_contributions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Total amount contributed across all rounds"
    )
    completed_rounds = models.IntegerField(
        default=0,
        help_text="Number of successfully completed rounds"
    )
    missed_payments = models.IntegerField(
        default=0,
        help_text="Total number of missed payments"
    )
    phone_number = models.CharField(max_length=15, blank=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mgr_user_profile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username} - Trust Score: {self.trust_score}"

    def update_trust_score(self):
        """Recalculate trust score based on payment history"""
        total_cycles = self.completed_rounds * 12  # Approximate cycles
        if total_cycles == 0:
            self.trust_score = 50
        else:
            success_rate = ((total_cycles - self.missed_payments) / total_cycles) * 100
            self.trust_score = max(0, min(100, int(success_rate)))
        self.save()


class MGRWallet(models.Model):
    """Merry-Go-Round mini wallet for each user"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mgr_wallet')
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Total wallet balance"
    )
    available_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Available balance (not locked in rounds)"
    )
    locked_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Balance locked in active rounds"
    )
    total_deposited = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Total amount deposited from main wallet"
    )
    total_withdrawn = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Total amount withdrawn to main wallet"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mgr_wallet'
        verbose_name = 'MGR Wallet'
        verbose_name_plural = 'MGR Wallets'

    def __str__(self):
        return f"{self.user.username} - Balance: KES {self.balance}"

    def has_sufficient_balance(self, amount):
        """Check if available balance is sufficient"""
        return self.available_balance >= amount

    def lock_funds(self, amount, reason=""):
        """Lock funds for a round"""
        if self.available_balance >= amount:
            self.available_balance -= amount
            self.locked_balance += amount
            self.save()
            return True
        return False

    def unlock_funds(self, amount):
        """Unlock funds (e.g., when round is completed or cancelled)"""
        self.locked_balance -= amount
        self.available_balance += amount
        self.save()

    def add_funds(self, amount):
        """Add funds to wallet"""
        self.balance += amount
        self.available_balance += amount
        self.save()

    def deduct_funds(self, amount):
        """Deduct funds from wallet"""
        if self.available_balance >= amount:
            self.balance -= amount
            self.available_balance -= amount
            self.save()
            return True
        return False


class MGRTransaction(models.Model):
    """Transaction records for MGR wallet"""
    
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit from Main Wallet'),
        ('withdraw', 'Withdraw to Main Wallet'),
        ('contribution', 'Round Contribution'),
        ('payout', 'Round Payout'),
        ('lock', 'Funds Locked'),
        ('unlock', 'Funds Unlocked'),
        ('interest', 'Interest Earned'),
        ('refund', 'Refund'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(MGRWallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Balance snapshots
    balance_before = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Related records
    related_round = models.ForeignKey('Round', on_delete=models.SET_NULL, null=True, blank=True)
    related_contribution = models.ForeignKey('Contribution', on_delete=models.SET_NULL, null=True, blank=True)
    related_payout = models.ForeignKey('Payout', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Integration with main wallet
    main_wallet_reference = models.CharField(max_length=100, blank=True, help_text="Reference from main ChamaSpace wallet")
    
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mgr_transaction'
        ordering = ['-created_at']
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'

    def __str__(self):
        return f"{self.wallet.user.username} - {self.get_transaction_type_display()} - KES {self.amount}"


class Round(models.Model):
    """Main model for a savings round/group"""
    
    ROUND_TYPE_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
    ]
    
    MODEL_CHOICES = [
        ('marathon', 'Marathon'),
        ('rotational', 'Rotational'),
    ]
    
    FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open for Joining'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    round_type = models.CharField(max_length=10, choices=ROUND_TYPE_CHOICES, default='public')
    payout_model = models.CharField(max_length=15, choices=MODEL_CHOICES, default='marathon')
    contribution_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('100.00'))],
        help_text="Amount each member contributes per cycle"
    )
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='monthly')
    max_members = models.IntegerField(
        validators=[MinValueValidator(2), MaxValueValidator(100)],
        help_text="Maximum number of members allowed"
    )
    current_members = models.IntegerField(default=0)
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=12.00,
        help_text="Annual interest rate percentage"
    )
    
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rounds')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    next_contribution_date = models.DateField(null=True, blank=True)
    
    total_pool = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_interest_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    min_trust_score = models.IntegerField(
        default=30,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum trust score required to join"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mgr_round'
        ordering = ['-created_at']
        verbose_name = 'Round'
        verbose_name_plural = 'Rounds'

    def __str__(self):
        return f"{self.name} ({self.get_round_type_display()} - {self.get_payout_model_display()})"

    def is_full(self):
        """Check if round has reached maximum members"""
        return self.current_members >= self.max_members

    def can_start(self):
        """Check if round can start (has minimum 2 members)"""
        return self.current_members >= 2

    def get_cycle_duration_days(self):
        """Return number of days per contribution cycle"""
        if self.frequency == 'weekly':
            return 7
        elif self.frequency == 'biweekly':
            return 14
        else:  # monthly
            return 30

    def calculate_total_cycles(self):
        """Calculate total number of contribution cycles"""
        if self.payout_model == 'marathon':
            return self.max_members  # One cycle per member
        else:
            return self.max_members  # Rotational also runs for max_members cycles

    
    def get_accurate_projected_interest(self, member_contributions=None):
        """
            CORRECTED: Calculate projected interest based on ACTUAL contribution schedule
            
            Key insight: End date is ONE PERIOD after last contribution!
            - Monthly round: Last contribution earns 30 days of interest
            - Weekly round: Last contribution earns 7 days of interest
            - Biweekly round: Last contribution earns 14 days of interest
            
            Formula: days_held = end_date - contribution_date
            
            Args:
                member_contributions: If None, uses contribution_amount * total_cycles
                
            Returns:
                Decimal: Projected gross interest (before tax)
            """
        if member_contributions is None:
            total_cycles = self.calculate_total_cycles()
            member_contributions = self.contribution_amount * total_cycles
        
        # Calculate interest for each contribution cycle
        cycle_days = self.get_cycle_duration_days()
        total_cycles = self.calculate_total_cycles()
        daily_rate = self.interest_rate / 365 / 100
        
        # CRITICAL: End date is ONE PERIOD after last contribution
        # So if we have 10 cycles, the end date is at day (10 * cycle_days)
        # And contributions happen at days 0, cycle_days, 2*cycle_days, ... (total_cycles-1)*cycle_days
        
        total_interest = Decimal('0.00')
        
        # For Marathon model: All contributions held until end date
        if self.payout_model == 'marathon':
            # End date is total_cycles * cycle_days from start
            # (because we go one period beyond the last contribution)
            end_day = total_cycles * cycle_days
            
            for cycle in range(1, total_cycles + 1):
                # This contribution is made on day: (cycle - 1) * cycle_days
                contribution_day = (cycle - 1) * cycle_days
                
                # Days held = end_date - contribution_date
                days_held = end_day - contribution_day
                
                # Interest for this contribution
                contribution_interest = (
                    self.contribution_amount * 
                    Decimal(str(daily_rate)) * 
                    Decimal(str(days_held))
                )
                
                total_interest += contribution_interest
                
                # Debug logging (optional)
                # print(f"Cycle {cycle}: Contribution day {contribution_day}, End day {end_day}, Days held {days_held}, Interest {contribution_interest}")
        
        # For Rotational model: Contributions held until member's payout turn
        elif self.payout_model == 'rotational':
            # In rotational, each member gets paid on their turn
            # For simplicity in projection, we'll assume mid-position
            # (In reality, this depends on payout_position which we don't know yet)
            
            # Average payout position would be middle of the cycle
            avg_payout_cycle = (total_cycles + 1) / 2
            payout_day = avg_payout_cycle * cycle_days
            
            for cycle in range(1, total_cycles + 1):
                contribution_day = (cycle - 1) * cycle_days
                
                # Days held until payout
                days_held = max(0, payout_day - contribution_day)
                
                contribution_interest = (
                    self.contribution_amount * 
                    Decimal(str(daily_rate)) * 
                    Decimal(str(days_held))
                )
                
                total_interest += contribution_interest
        
        return round(total_interest, 2)

    def get_total_commitment_amount(self):
        """Calculate total amount a member needs to commit for the entire round"""
        return self.contribution_amount * self.calculate_total_cycles()
    
    def get_next_contribution_amount(self):
        """Get amount needed for next contribution (just-in-time approach)"""
        return self.contribution_amount
    def get_tax_rate(self):
        """Get current tax rate from config"""
        from constance import config
        return config.MGR_TAX_RATE
    
    def get_accurate_projected_interest_after_tax(self, member_contributions=None):
        """
        Calculate projected NET interest (after tax) for a member's contributions
        
        Args:
            member_contributions: Total amount contributed
            
        Returns:
            Net interest after tax deduction
        """
        # Calculate gross interest
        gross_interest = self.get_accurate_projected_interest(member_contributions)
        
        # Calculate tax
        from constance import config
        tax_rate = config.MGR_TAX_RATE / 100
        tax_amount = gross_interest * Decimal(str(tax_rate))
        
        # Net interest
        net_interest = gross_interest - tax_amount
        
        return round(net_interest, 2)
    
    
    def get_accurate_payout_breakdown(self, member_contributions=None):
        """
        CORRECTED: Get complete payout breakdown with accurate projections
        
        Returns:
            Dict with principal, gross_interest, tax, net_interest, total
        """
        if member_contributions is None:
            total_cycles = self.calculate_total_cycles()
            member_contributions = self.contribution_amount * total_cycles
        
        gross_interest = self.get_accurate_projected_interest(member_contributions)
        
        from constance import config
        tax_rate = config.MGR_TAX_RATE / 100
        tax_amount = gross_interest * Decimal(str(tax_rate))
        
        net_interest = gross_interest - tax_amount
        total_payout = member_contributions + net_interest
        
        return {
            'principal': member_contributions,
            'gross_interest': round(gross_interest, 2),
            'tax_amount': round(tax_amount, 2),
            'tax_rate_percent': config.MGR_TAX_RATE,
            'net_interest': round(net_interest, 2),
            'total_payout': round(total_payout, 2),
            'calculation_method': 'accurate_schedule_based'
        }
    def get_projected_interest_by_contribution(self):
        """
        CORRECTED: Get detailed projection showing interest for each contribution
        Useful for displaying to users
        
        Returns:
            List of dicts with cycle number, contribution_date, days_held, and interest_earned
        """
        cycle_days = self.get_cycle_duration_days()
        total_cycles = self.calculate_total_cycles()
        daily_rate = self.interest_rate / 365 / 100
        
        projection = []
        
        if self.payout_model == 'marathon':
            # End date is ONE PERIOD after last contribution
            end_day = total_cycles * cycle_days
            
            for cycle in range(1, total_cycles + 1):
                contribution_day = (cycle - 1) * cycle_days
                days_held = end_day - contribution_day
                
                interest = (
                    self.contribution_amount * 
                    Decimal(str(daily_rate)) * 
                    Decimal(str(days_held))
                )
                
                projection.append({
                    'cycle': cycle,
                    'amount': self.contribution_amount,
                    'contribution_day': contribution_day,
                    'days_held': days_held,
                    'interest_earned': round(interest, 2)
                })
        
        elif self.payout_model == 'rotational':
            # For rotational, need payout position which varies by member
            # This is just a general projection
            for cycle in range(1, total_cycles + 1):
                contribution_day = (cycle - 1) * cycle_days
                # Assume payout at this member's turn
                payout_day = cycle * cycle_days
                days_held = payout_day - contribution_day
                
                interest = (
                    self.contribution_amount * 
                    Decimal(str(daily_rate)) * 
                    Decimal(str(days_held))
                )
                
                projection.append({
                    'cycle': cycle,
                    'amount': self.contribution_amount,
                    'contribution_day': contribution_day,
                    'days_held': days_held,
                    'interest_earned': round(interest, 2)
                })
        
        return projection



class RoundMembership(models.Model):
    """Tracks user membership in rounds"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('defaulted', 'Defaulted'),
        ('completed', 'Completed'),
        ('removed', 'Removed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='round_memberships')
    
    payout_position = models.IntegerField(
        null=True,
        blank=True,
        help_text="Position in payout rotation (for rotational model)"
    )
    trust_score_at_join = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Trust score when member joined"
    )
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Financial tracking
    total_contributed = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    interest_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    expected_contributions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    locked_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Amount locked in user's wallet for this round"
    )
    
    contributions_made = models.IntegerField(default=0)
    contributions_missed = models.IntegerField(default=0)
    
    has_received_payout = models.BooleanField(default=False)
    payout_received_date = models.DateField(null=True, blank=True)
    payout_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    join_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mgr_round_membership'
        unique_together = ['round', 'user']
        ordering = ['payout_position', 'join_date']
        verbose_name = 'Round Membership'
        verbose_name_plural = 'Round Memberships'

    def __str__(self):
        return f"{self.user.username} in {self.round.name}"

    def get_contribution_percentage(self):
        """Calculate percentage of expected contributions made"""
        if self.expected_contributions == 0:
            return 0
        return (self.total_contributed / self.expected_contributions) * 100

    def is_up_to_date(self):
        """Check if member has made all expected contributions"""
        return self.total_contributed >= self.expected_contributions
    
    def needs_reservation(self):
        """Check if member needs to deposit funds for next contribution"""
        # Get next pending contribution
        from django.utils import timezone
        next_contribution = self.contributions.filter(
            status='pending',
            due_date__gte=timezone.now().date()
        ).order_by('due_date').first()
        
        if next_contribution:
            # Check if this contribution is already reserved
            return self.locked_amount < next_contribution.amount
        return False
    
    def get_next_contribution_due(self):
        """Get the next pending contribution"""
        from django.utils import timezone
        return self.contributions.filter(
            status='pending',
            due_date__gte=timezone.now().date()
        ).order_by('due_date').first()


class Contribution(models.Model):
    """Individual contribution records"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('missed', 'Missed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(RoundMembership, on_delete=models.CASCADE, related_name='contributions')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    cycle_number = models.IntegerField(help_text="Contribution cycle number")
    due_date = models.DateField()
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Wallet-based payment (no M-Pesa needed)
    wallet_transaction = models.ForeignKey(
        MGRTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contribution_record'
    )
    payment_date = models.DateTimeField(null=True, blank=True)
    
    interest_accrued = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    days_in_escrow = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mgr_contribution'
        ordering = ['due_date', 'cycle_number']
        unique_together = ['membership', 'cycle_number']
        verbose_name = 'Contribution'
        verbose_name_plural = 'Contributions'

    def __str__(self):
        return f"{self.membership.user.username} - Cycle {self.cycle_number} - {self.amount}"

    def mark_as_missed(self):
        """Mark contribution as missed after due date"""
        if self.status == 'pending' and self.due_date < timezone.now().date():
            self.status = 'missed'
            self.save()
            
            # Update membership
            membership = self.membership
            membership.contributions_missed += 1
            membership.save()
            
            # Update user profile
            profile = membership.user.mgr_profile
            profile.missed_payments += 1
            profile.update_trust_score()

    def calculate_interest(self):
        """Calculate interest accrued on this contribution"""
        if self.status == 'completed' and self.payment_date:
            daily_rate = self.membership.round.interest_rate / 365 / 100
            days = self.days_in_escrow
            self.interest_accrued = self.amount * Decimal(str(daily_rate)) * Decimal(str(days))
            self.save()


class Payout(models.Model):
    """Payout records for members"""
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='payouts')
    recipient_membership = models.ForeignKey(
        RoundMembership,
        on_delete=models.CASCADE,
        related_name='received_payouts'
    )
    
    payout_cycle = models.IntegerField(help_text="Cycle number for this payout")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    scheduled_date = models.DateField()
    payout_date = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='scheduled')
    
    # Wallet-based payout
    wallet_transaction = models.ForeignKey(
        MGRTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payout_record'
    )
    
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mgr_payout'
        ordering = ['scheduled_date', 'payout_cycle']
        verbose_name = 'Payout'
        verbose_name_plural = 'Payouts'

    def __str__(self):
        return f"Payout to {self.recipient_membership.user.username} - {self.amount}"

    def process_payout(self):
        """Process the payout to the recipient"""
        if self.status == 'scheduled':
            self.status = 'processing'
            self.save()
            # Payment processing logic handled by WalletService
            self.status = 'completed'
            self.payout_date = timezone.now()
            self.save()
            
            # Update membership
            membership = self.recipient_membership
            membership.has_received_payout = True
            membership.payout_received_date = self.payout_date.date()
            membership.payout_amount = self.amount
            membership.save()


class Invitation(models.Model):
    """Invitations for private rounds - ENHANCED"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    
    LOOKUP_TYPE_CHOICES = [
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('national_id', 'National ID'),
        ('link', 'Shareable Link'),  # NEW
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='invitations')
    inviter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    
    # Contact methods
    invitee_email = models.EmailField(blank=True)
    invitee_phone = models.CharField(max_length=15, blank=True)
    invitee_national_id = models.CharField(max_length=20, blank=True)
    invitee_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_invitations',
        null=True,
        blank=True
    )
    
    # NEW: Track lookup method used
    lookup_type = models.CharField(max_length=15, choices=LOOKUP_TYPE_CHOICES, default='email')
    
    # Invitation details
    token = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True)
    
    # Dates
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)  # NEW
    
    # NEW: Track notification delivery
    sms_sent = models.BooleanField(default=False)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    notification_sent = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Action URL for easy access
    action_url = models.CharField(max_length=500, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mgr_invitation'
        ordering = ['-created_at']
        verbose_name = 'Invitation'
        verbose_name_plural = 'Invitations'

    def __str__(self):
        contact = self.invitee_email or self.invitee_phone or self.invitee_national_id or 'Link'
        return f"Invitation to {contact} for {self.round.name}"

    def is_expired(self):
        """Check if invitation has expired"""
        return timezone.now() > self.expires_at

    def accept(self, user):
        """Accept the invitation"""
        if self.status == 'pending' and not self.is_expired():
            self.status = 'accepted'
            self.invitee_user = user
            self.accepted_at = timezone.now()
            self.save()
            return True
        return False
    
    def decline(self, user):
        """Decline the invitation"""
        if self.status == 'pending':
            self.status = 'declined'
            self.invitee_user = user
            self.declined_at = timezone.now()
            self.save()
            return True
        return False
    
    def get_shareable_link(self, request):
        """Generate shareable invitation link"""
        return request.build_absolute_uri(
            reverse('merry_go_round:review_invitation', kwargs={'token': self.token})
        )



class RoundMessage(models.Model):
    """Messages/updates within a round"""
    
    MESSAGE_TYPE_CHOICES = [
        ('system', 'System'),
        ('user', 'User'),
        ('admin', 'Admin'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='round_messages')
    
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='user')
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    
    is_pinned = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mgr_round_message'
        ordering = ['-is_pinned', '-created_at']
        verbose_name = 'Round Message'
        verbose_name_plural = 'Round Messages'

    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"


class Notification(models.Model):
    """User notifications for merry-go-round activities"""
    
    NOTIFICATION_TYPE_CHOICES = [
        ('contribution_due', 'Contribution Due'),
        ('contribution_reminder', 'Contribution Reminder'),
        ('payment_received', 'Payment Received'),
        ('payout_scheduled', 'Payout Scheduled'),
        ('payout_received', 'Payout Received'),
        ('round_started', 'Round Started'),
        ('round_completed', 'Round Completed'),
        ('invitation_received', 'Invitation Received'),
        ('member_joined', 'Member Joined'),
        ('member_defaulted', 'Member Defaulted'),
        ('insufficient_balance', 'Insufficient Balance'),
        ('funds_locked', 'Funds Locked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mgr_notifications')
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    
    action_url = models.CharField(max_length=500, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'mgr_notification'
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"{self.user.username} - {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
class RoundCompletionStats(models.Model):
    """
    NEW MODEL: Store immutable completion statistics for completed rounds
    This prevents stats from changing when admin updates interest/tax rates
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.OneToOneField(
        'Round', 
        on_delete=models.CASCADE, 
        related_name='completion_snapshot'
    )
    
    # Frozen round-level stats (these NEVER change after completion)
    total_expected_contributions = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Total amount that should have been collected"
    )
    total_actual_contributions = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Total amount actually collected"
    )
    completion_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Percentage of target reached"
    )
    
    # Frozen interest/tax calculations
    total_gross_interest = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Total interest earned before tax"
    )
    total_tax_deducted = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Total tax deducted from interest"
    )
    total_net_interest = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Total interest after tax"
    )
    total_paid_out = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Total amount paid to all members"
    )
    
    # Frozen rates used at completion time
    interest_rate_used = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Interest rate that was applied"
    )
    tax_rate_used = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Tax rate that was applied"
    )
    
    # Metadata
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'mgr_round_completion_stats'
        verbose_name = 'Round Completion Stats'
        verbose_name_plural = 'Round Completion Stats'
    
    def __str__(self):
        return f"Completion stats for {self.round.name}"            