# models.py
from django.contrib.auth.models import User
from django.db import models
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.utils import timezone

class Goal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='User')
    SAVING_TYPES = (
        ('regular', 'Regular Saving'),
        ('fixed', 'Fixed Saving'),
    )

    name = models.CharField(max_length=1000, blank=True, null=True)
    is_active = models.CharField(max_length=100, default='Yes')
    saving_type = models.CharField(max_length=10, choices=SAVING_TYPES)
    goal_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    amount_to_save_per_notification = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    target_months = models.PositiveIntegerField(blank=True, null=True)
    reminder_frequency = models.CharField(max_length=10, choices=(
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
    ), blank=True, null=True)
    payment_frequency = models.CharField(max_length=10, choices=(
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
    ), blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    end_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    notification_date = models.DateField(blank=True, null=True)
    goal_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    goal_profit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    milestone_50_shown = models.BooleanField(default=False)
    milestone_75_shown = models.BooleanField(default=False)

    def percentage(self):
        """Calculate goal progress percentage."""
        try:
            # PRIORITY 1: If goal_amount is set, calculate based on balance vs target
            if self.goal_amount and self.goal_amount > 0:
                percentage = (self.goal_balance / self.goal_amount) * 100
                if percentage > 100:
                    return 100
                return int(percentage)
            
            # PRIORITY 2: If no goal_amount but has dates, calculate based on time
            elif self.start_date and self.end_date:
                today = timezone.now().date()
                
                if today < self.start_date:
                    return 0
                
                if today > self.end_date:
                    return 100
                
                total_days = (self.end_date - self.start_date).days
                elapsed_days = (today - self.start_date).days
                
                if total_days > 0:
                    percentage = (elapsed_days / total_days) * 100
                    return int(min(percentage, 100))
                
                return 0
            
            # PRIORITY 3: No goal_amount and no dates - show minimal progress if has balance
            else:
                if self.goal_balance > 0:
                    return 25  # Show some progress to indicate activity
                return 0
        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating percentage for goal {self.id}: {str(e)}")
            return 0

    def calculate_month_difference(self):
        if self.end_date:
            today = timezone.now().date()
            difference = self.end_date - today
            if difference.days > 0:
                return difference.days
            else:
                return 0
        return 0
    
    def clean(self):
        """Validate goal dates - ONLY for new goals or when dates are being changed"""
        super().clean()
        today = timezone.now().date()
        
        # Get the original object from database if it exists
        if self.pk:
            try:
                original = Goal.objects.get(pk=self.pk)
                # Only validate dates if they're being changed
                start_date_changed = original.start_date != self.start_date
                end_date_changed = original.end_date != self.end_date
            except Goal.DoesNotExist:
                # New object, validate everything
                start_date_changed = True
                end_date_changed = True
        else:
            # New object, validate everything
            start_date_changed = True
            end_date_changed = True
        
        # Validate start_date ONLY if it's being changed
        if start_date_changed and self.start_date and self.start_date < today:
            raise ValidationError({
                'start_date': 'Start date cannot be in the past. Please select today or a future date.'
            })
        
        # Validate end_date ONLY if it's being changed
        if end_date_changed and self.end_date:
            if self.end_date < today:
                raise ValidationError({
                    'end_date': 'End date cannot be in the past. Please select today or a future date.'
                })
            
            # Ensure end_date is after start_date
            if self.start_date and self.end_date <= self.start_date:
                raise ValidationError({
                    'end_date': 'End date must be after the start date.'
                })
        
        # CRITICAL: Validate for fixed goals - must have end_date
        if self.saving_type == 'fixed' and not self.end_date:
            raise ValidationError({
                'end_date': 'Fixed saving goals must have an end date.'
            })
    
    def save(self, *args, **kwargs):
        """Enforce validation on save - but skip validation if explicitly requested"""
        # Allow bypassing validation with skip_validation=True
        skip_validation = kwargs.pop('skip_validation', False)
        
        if not skip_validation:
            self.full_clean()
        
        super().save(*args, **kwargs)
    
    def is_goal_completed(self):
        """Check if goal is completed (either by amount or date)"""
        today = timezone.now().date()
        
        if self.goal_amount and self.goal_balance >= self.goal_amount:
            return True
        
        if self.saving_type == 'fixed' and self.end_date and today > self.end_date:
            return True
        
        return False
    
    def can_withdraw(self):
        """
        Check if withdrawal is allowed
        
        Rules:
        - Regular goals: Can ALWAYS withdraw
        - Fixed goals: Can withdraw when EITHER:
            1. End date has been reached OR passed, OR
            2. Target goal amount has been achieved (if goal_amount is set)
        """
        today = timezone.now().date()
        
        if self.saving_type == 'regular':
            return True
        
        if self.saving_type == 'fixed':
            if self.end_date and today >= self.end_date:
                return True
            
            if self.goal_amount and self.goal_balance >= self.goal_amount:
                return True
            
            return False
        
        return True



class Deposit(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_withdraw = models.CharField(max_length=10, blank=True, null=True, default='No')
    deposit_date = models.DateTimeField(default=timezone.now)

    def calculate_future_value(self):
        # Get the user's wallet
        now = timezone.now()
        interest_value = Interest_Rate.objects.get(pk=1)
        interest_rate = Decimal('0.0')
        if self.goal.saving_type == 'fixed':
            interest_rate = interest_value.fixed_deposit
        if self.goal.saving_type == 'regular':
            interest_rate = interest_value.regular_deposit
        daily_interest_rate = Decimal(interest_rate) / 365

        delta = relativedelta(now, self.deposit_date)

        # Calculate the total months elapsed using floating-point division
        days_difference = delta.years * 365 + delta.months * 30 + delta.days

        # Calculate the future value using Decimal type for more accuracy
        future_value = self.amount * (1 + daily_interest_rate) ** Decimal(days_difference)

        return round(Decimal(future_value) - (self.amount), 2)


class Goal_Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    goal_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    saving_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    saving_profit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    group_goal_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)


class ExpressSaving(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now)
    evaluation_date = models.DateField(blank=True, null=True)
    
    # ✅ OLD FIELD: Keep for backward compatibility and interest calculation
    is_withdraw = models.CharField(max_length=100, blank=True, null=True, default='No')
    
    # ✅ NEW FIELD: Explicit transaction type for display
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]
    transaction_type = models.CharField(
        max_length=20, 
        choices=TRANSACTION_TYPE_CHOICES,
        default='deposit'  # Default to deposit for existing records
    )

    def calculate_future_value_express_saving(self):
        # Only calculate interest for deposits that haven't been withdrawn
        if self.transaction_type == 'deposit' and self.is_withdraw == 'No':
            now = timezone.now()
            interest_value = Interest_Rate.objects.get(pk=1)
            delta = relativedelta(now, self.created_at)
            days_difference = delta.years * 365 + delta.months * 30 + delta.days
            daily_interest_rate = Decimal(interest_value.regular_deposit) / 365
            future_value = self.amount * (1 + daily_interest_rate) ** Decimal(days_difference)
            return Decimal(future_value) - (self.amount)
        return Decimal('0.00')


class GroupGoal(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_goals')
    SAVING_TYPES = (
        ('regular', 'Regular Saving'),
        ('fixed', 'Fixed Saving'),
    )
    end_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    achieved_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    saving_type = models.CharField(max_length=10, choices=SAVING_TYPES)
    goal_name = models.CharField(max_length=100, blank=True, null=True)
    goal_description = models.CharField(max_length=100, blank=True, null=True)
    shareable_link = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.CharField(max_length=100, default='Yes')
    reminder_frequency = models.CharField(max_length=10, choices=(
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
    ), blank=True, null=True)
    payment_frequency = models.CharField(max_length=10, choices=(
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
    ), blank=True, null=True)
    status = models.CharField(max_length=20, choices=(('ongoing', 'Ongoing'), ('achieved', 'Achieved')), default='ongoing')
    created_at = models.DateTimeField(auto_now_add=True)

    # NEW milestone FIELDS
    milestone_50_shown = models.BooleanField(default=False)
    milestone_75_shown = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.creator.username}'s Group Goal - {self.target_amount}"

    def percentage(self):
        try:
            percentage = (float(self.achieved_amount) / float(self.target_amount)) * 100
            if percentage > 100:
                return 100
            return int(percentage)
        except Exception as e:
            return 0

    def calculate_month_difference(self):
        if self.end_date:
            today = timezone.now().date()
            difference = self.end_date - today
            if difference.days > 0:
                return difference.days
            else:
                return 0
        return 0
    
    def clean(self):
        """Validate group goal dates - ONLY for new goals or when dates are being changed"""
        super().clean()
        today = timezone.now().date()
        
        # Get the original object from database if it exists
        if self.pk:
            try:
                original = GroupGoal.objects.get(pk=self.pk)
                # Only validate dates if they're being changed
                start_date_changed = original.start_date != self.start_date
                end_date_changed = original.end_date != self.end_date
            except GroupGoal.DoesNotExist:
                # New object, validate everything
                start_date_changed = True
                end_date_changed = True
        else:
            # New object, validate everything
            start_date_changed = True
            end_date_changed = True
        
        # Validate start_date ONLY if it's being changed
        if start_date_changed and self.start_date and self.start_date < today:
            raise ValidationError({
                'start_date': 'Start date cannot be in the past.'
            })
        
        # Validate end_date ONLY if it's being changed
        if end_date_changed and self.end_date:
            if self.end_date < today:
                raise ValidationError({
                    'end_date': 'End date cannot be in the past.'
                })
            
            if self.start_date and self.end_date <= self.start_date:
                raise ValidationError({
                    'end_date': 'End date must be after the start date.'
                })
    
    def save(self, *args, **kwargs):
        """Enforce validation on save - but skip validation if explicitly requested"""
        # Allow bypassing validation with skip_validation=True
        skip_validation = kwargs.pop('skip_validation', False)
        
        if not skip_validation:
            self.full_clean()
        
        super().save(*args, **kwargs)
    
    def is_goal_completed(self):
        """Check if group goal is completed"""
        today = timezone.now().date()
        
        if self.achieved_amount >= self.target_amount:
            return True
        
        if self.saving_type == 'fixed' and self.end_date and today > self.end_date:
            return True
        
        return False
    
    def can_withdraw(self):
        """Check if withdrawal is allowed"""
        today = timezone.now().date()
        
        if self.saving_type == 'regular':
            return True
        
        if self.saving_type == 'fixed':
            if self.end_date and today > self.end_date:
                return True
            if self.achieved_amount >= self.target_amount:
                return True
            return False
        
        return False

class GroupGoalMember(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group_goal = models.ForeignKey(GroupGoal, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.group_goal}"


class GroupGoalActivites(models.Model):
    group_goal = models.ForeignKey(GroupGoal, on_delete=models.CASCADE)
    content = models.CharField(max_length=1000, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.group_goal}"


class GroupGoalMember_contribution(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group_goal = models.ForeignKey(GroupGoal, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created_at = models.DateTimeField(auto_now_add=True, editable=True)
    evaluation_date = models.DateField(blank=True, null=True)
    is_withdraw = models.CharField(max_length=10, blank=True, null=True, default='No')

    def __str__(self):
        return f"{self.user.username} - {self.group_goal}"
    
    def calculate_future_value_group_goal(self):
        """Calculate future value for group goal contribution"""
        now = timezone.now()
        
        delta = relativedelta(now, self.created_at)
        interest_value = Interest_Rate.objects.get(pk=1)

        # Calculate the total days elapsed
        days_difference = delta.years * 365 + delta.months * 30 + delta.days
        daily_interest_rate = Decimal(interest_value.fixed_deposit) / 365

        # Initialize as Decimal, not float - THIS IS THE FIX
        total_amount = Decimal('0.0')
        
        # Calculate the future value using Decimal type for accuracy
        future_value = self.amount * (1 + daily_interest_rate) ** Decimal(days_difference)
        total_amount += Decimal(future_value) - (self.amount)

        return round(total_amount, 2)


class Interest_Rate(models.Model):
    regular_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0.06)
    fixed_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0.08)

    def percent_regular_deposit(self):
        return round(self.regular_deposit * 100, 2)
    
    def percent_fixed_deposit(self):
        return round(self.fixed_deposit * 100, 2)


class tax_Rate(models.Model):
    tax_rate_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.20)