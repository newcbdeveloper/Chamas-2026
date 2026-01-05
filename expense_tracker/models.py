from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta


class Category(models.Model):
    """
    Categories for organizing transactions (both income and expenses)
    """
    CATEGORY_TYPES = (
        ('income', 'Income'),
        ('expense', 'Expense'),
    )
    
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=CATEGORY_TYPES)
    icon = models.CharField(max_length=50, default='💰')  # Emoji or icon class
    color = models.CharField(max_length=7, default='#3498db')  # Hex color code
    is_default = models.BooleanField(default=False)  # System default categories
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='custom_categories'
    )  # Null for default categories, filled for custom ones
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['type', 'name']
        unique_together = ['name', 'type', 'user']
    
    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"
    
    @classmethod
    def get_user_categories(cls, user, category_type=None):
        """Get all categories available to a user (default + custom)"""
        query = cls.objects.filter(
            models.Q(is_default=True) | models.Q(user=user)
        )
        if category_type:
            query = query.filter(type=category_type)
        return query.distinct()

    @classmethod
    def create_default_categories(cls):
        """
        Create global default categories (shared across all users).
        Safe to call multiple times — uses get_or_create.
        """
        defaults = [
            # === 🛒 Expense Categories (26) ===
            {'name': 'Groceries', 'type': 'expense', 'icon': '🛒', 'color': '#e74c3c'},
            {'name': 'Dining Out', 'type': 'expense', 'icon': '🍽️', 'color': '#d35400'},
            {'name': 'Transport', 'type': 'expense', 'icon': '🚗', 'color': '#3498db'},
            {'name': 'Fuel', 'type': 'expense', 'icon': '⛽', 'color': '#2980b9'},
            {'name': 'Public Transit', 'type': 'expense', 'icon': '🚆', 'color': '#1abc9c'},
            {'name': 'Rideshare/Taxi', 'type': 'expense', 'icon': '🚖', 'color': '#27ae60'},
            {'name': 'Utilities', 'type': 'expense', 'icon': '💡', 'color': '#9b59b6'},
            {'name': 'Electricity', 'type': 'expense', 'icon': '⚡', 'color': '#8e44ad'},
            {'name': 'Water', 'type': 'expense', 'icon': '💧', 'color': '#3498db'},
            {'name': 'Internet & Phone', 'type': 'expense', 'icon': '📶', 'color': '#2980b9'},
            {'name': 'Rent/Mortgage', 'type': 'expense', 'icon': '🏠', 'color': '#34495e'},
            {'name': 'Home Maintenance', 'type': 'expense', 'icon': '🔧', 'color': '#7f8c8d'},
            {'name': 'Healthcare', 'type': 'expense', 'icon': '🏥', 'color': '#e67e22'},
            {'name': 'Pharmacy/Meds', 'type': 'expense', 'icon': '💊', 'color': '#d35400'},
            {'name': 'Insurance', 'type': 'expense', 'icon': '🛡️', 'color': '#2c3e50'},
            {'name': 'Entertainment', 'type': 'expense', 'icon': '🎬', 'color': '#f39c12'},
            {'name': 'Streaming Services', 'type': 'expense', 'icon': '📺', 'color': '#c0392b'},
            {'name': 'Shopping', 'type': 'expense', 'icon': '🛍️', 'color': '#e67e22'},
            {'name': 'Education', 'type': 'expense', 'icon': '📚', 'color': '#16a085'},
            {'name': 'Personal Care', 'type': 'expense', 'icon': '🧴', 'color': '#e91e63'},
            {'name': 'Gifts & Donations', 'type': 'expense', 'icon': '💝', 'color': '#9b59b6'},
            {'name': 'Travel & Vacation', 'type': 'expense', 'icon': '✈️', 'color': '#3498db'},
            {'name': 'Childcare', 'type': 'expense', 'icon': '👶', 'color': '#2ecc71'},
            {'name': 'Pets', 'type': 'expense', 'icon': '🐶', 'color': '#9b59b6'},
            {'name': 'Subscriptions', 'type': 'expense', 'icon': '📫', 'color': '#8e44ad'},
            {'name': 'Taxes', 'type': 'expense', 'icon': '🧾', 'color': '#2c3e50'},
            
            # === 💰 Income Categories (10) ===
            {'name': 'Salary', 'type': 'income', 'icon': '💼', 'color': '#27ae60'},
            {'name': 'Freelance/Contract', 'type': 'income', 'icon': '✍️', 'color': '#2980b9'},
            {'name': 'Business Revenue', 'type': 'income', 'icon': '📊', 'color': '#16a085'},
            {'name': 'Investment Income', 'type': 'income', 'icon': '📈', 'color': '#8e44ad'},
            {'name': 'Dividends', 'type': 'income', 'icon': '💵', 'color': '#2c3e50'},
            {'name': 'Rental Income', 'type': 'income', 'icon': '🏘️', 'color': '#3498db'},
            {'name': 'Gifts Received', 'type': 'income', 'icon': '🎁', 'color': '#e67e22'},
            {'name': 'Refunds & Rebates', 'type': 'income', 'icon': '↩️', 'color': '#1abc9c'},
            {'name': 'Side Hustle', 'type': 'income', 'icon': '🚴', 'color': '#e74c3c'},
            {'name': 'Interest Income', 'type': 'income', 'icon': '🏦', 'color': '#27ae60'},
        ]

        for cat in defaults:
            cls.objects.get_or_create(
                name=cat['name'],
                type=cat['type'],
                is_default=True,
                defaults={
                    'icon': cat['icon'],
                    'color': cat['color'],
                    'user': None,  # Critical: global defaults have no owner
                }
            )


class Transaction(models.Model):
    """
    Individual income or expense transaction
    """
    TRANSACTION_TYPES = (
        ('income', 'Income'),
        ('expense', 'Expense'),
    )
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='transactions'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    description = models.CharField(max_length=255, blank=True)
    date = models.DateField(default=timezone.now)
    time = models.TimeField(default=timezone.now)
    is_recurring = models.BooleanField(default=False)
    recurring_transaction = models.ForeignKey(
        'RecurringTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_transactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-time']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'type']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        sign = '+' if self.type == 'income' else '-'
        return f"{sign}KSh {self.amount} - {self.category.name if self.category else 'Uncategorized'}"
    
    @property
    def signed_amount(self):
        """Return amount with appropriate sign"""
        return self.amount if self.type == 'income' else -self.amount


class RecurringTransaction(models.Model):
    """
    Template for recurring income or expenses
    """
    FREQUENCY_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    )
    
    TRANSACTION_TYPES = (
        ('income', 'Income'),
        ('expense', 'Expense'),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recurring_transactions'
    )
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recurring_transactions'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    description = models.CharField(max_length=255, blank=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)  # Optional end date
    next_occurrence = models.DateField()
    is_active = models.BooleanField(default=True)
    auto_generate = models.BooleanField(
        default=True,
        help_text="Automatically create transactions on schedule"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['next_occurrence']
    
    def __str__(self):
        return f"{self.get_frequency_display()} - {self.category.name if self.category else 'Uncategorized'}"

    def calculate_next_occurrence(self, current_date=None):
        """
        Calculate next occurrence from a given date.
        If current_date is None, uses self.next_occurrence.
        Handles month/year boundaries robustly.
        """
        if current_date is None:
            current_date = self.next_occurrence

        if self.frequency == 'daily':
            return current_date + timedelta(days=1)
        elif self.frequency == 'weekly':
            return current_date + timedelta(weeks=1)
        elif self.frequency == 'biweekly':
            return current_date + timedelta(weeks=2)
        elif self.frequency == 'monthly':
            # Add one month
            month = current_date.month + 1
            year = current_date.year
            if month > 12:
                month = 1
                year += 1
            try:
                return current_date.replace(year=year, month=month)
            except ValueError:
                # E.g., Jan 31 → Feb 28/29
                next_month = month + 1
                next_year = year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                return current_date.replace(year=next_year, month=next_month, day=1) - timedelta(days=1)
        elif self.frequency == 'quarterly':
            month = current_date.month + 3
            year = current_date.year
            while month > 12:
                month -= 12
                year += 1
            try:
                return current_date.replace(year=year, month=month)
            except ValueError:
                next_month = month + 1
                next_year = year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                return current_date.replace(year=next_year, month=next_month, day=1) - timedelta(days=1)
        elif self.frequency == 'yearly':
            try:
                return current_date.replace(year=current_date.year + 1)
            except ValueError:
                # Feb 29 → Feb 28 next year
                try:
                    return current_date.replace(year=current_date.year + 1, month=2, day=28)
                except ValueError:
                    # fallback: March 1
                    return current_date.replace(year=current_date.year + 1, month=3, day=1)
        return current_date

    def generate_transaction(self, occurrence_date=None):
        """
        Create a single transaction for a specific occurrence date.
        If no date given, uses self.next_occurrence and updates next_occurrence.
        """
        if occurrence_date is None:
            occurrence_date = self.next_occurrence

        transaction = Transaction.objects.create(
            user=self.user,
            type=self.type,
            category=self.category,
            amount=self.amount,
            description=self.description,
            date=occurrence_date,
            time=timezone.now().time(),
            is_recurring=True,
            recurring_transaction=self
        )

        # Only advance next_occurrence if we processed the *scheduled* one
        if occurrence_date == self.next_occurrence:
            self.next_occurrence = self.calculate_next_occurrence(current_date=occurrence_date)
            self.save(update_fields=['next_occurrence', 'updated_at'])

        return transaction

    def generate_all_pending_instances(self, max_instances=100):
        """
        Generate all missed and current transactions up to today.
        Respects start_date, end_date, is_active, auto_generate.
        Safe for backfilling (e.g., start_date = 2025-01-01, today = 2025-11-10).
        
        Returns: number of transactions created.
        """
        if not (self.is_active and self.auto_generate):
            return 0

        today = timezone.now().date()
        current = self.next_occurrence

        # Cap to prevent runaway loops (e.g., daily backfill over 10 years)
        created_count = 0

        # Determine cutoff: min(today, end_date) if end_date set
        cutoff = self.end_date if self.end_date and self.end_date < today else today

        # Generate in order
        while current <= cutoff and created_count < max_instances:
            # Avoid duplicates: check if transaction already exists for this date
            exists = Transaction.objects.filter(
                recurring_transaction=self,
                date=current
            ).exists()
            if not exists:
                self.generate_transaction(occurrence_date=current)
                created_count += 1

            # Move to next
            current = self.calculate_next_occurrence(current_date=current)

        # Update next_occurrence (even if capped)
        self.next_occurrence = current
        self.save(update_fields=['next_occurrence', 'updated_at'])

        return created_count


class Budget(models.Model):
    """
    Budget limits for categories
    """
    PERIOD_CHOICES = (
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='budgets',
        limit_choices_to={'type': 'expense'}  # Only expense categories can have budgets
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default='monthly')
    start_date = models.DateField(default=timezone.now)
    rollover_enabled = models.BooleanField(
        default=False,
        help_text="Carry unused budget to next period"
    )
    rollover_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    is_active = models.BooleanField(default=True)
    alert_threshold = models.IntegerField(
        default=80,
        help_text="Alert when spending reaches this percentage (0-100)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'category', 'period']
        ordering = ['category__name']
    
    def __str__(self):
        return f"{self.category.name} - KSh {self.amount} ({self.get_period_display()})"
    
    def get_spent_amount(self, start_date=None, end_date=None):
        """Calculate total spent in this category for the current period"""
        if not start_date:
            start_date = self.get_period_start()
        if not end_date:
            end_date = self.get_period_end()
        
        spent = Transaction.objects.filter(
            user=self.user,
            category=self.category,
            type='expense',
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        return spent
    
    def get_remaining_amount(self):
        """Calculate remaining budget"""
        total_budget = self.amount + self.rollover_amount
        spent = self.get_spent_amount()
        return total_budget - spent
    
    def get_percentage_used(self):
        """Calculate percentage of budget used"""
        total_budget = self.amount + self.rollover_amount
        if total_budget == 0:
            return 0
        spent = self.get_spent_amount()
        return min((spent / total_budget) * 100, 100)
    
    def get_period_start(self):
        """Get the start date of the current budget period"""
        today = timezone.now().date()
        
        if self.period == 'weekly':
            days_since_start = (today - self.start_date).days
            weeks_passed = days_since_start // 7
            return self.start_date + timedelta(weeks=weeks_passed)
        else:  # monthly
            # Calculate how many months have passed
            months_diff = (today.year - self.start_date.year) * 12 + (today.month - self.start_date.month)
            
            try:
                return self.start_date.replace(
                    year=self.start_date.year + months_diff // 12,
                    month=((self.start_date.month - 1 + months_diff) % 12) + 1,
                    day=self.start_date.day
                )
            except ValueError:
                # Handle day overflow (e.g., Jan 31 → Feb 28/29)
                next_month = ((self.start_date.month - 1 + months_diff) % 12) + 2
                next_year = self.start_date.year + months_diff // 12
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                return self.start_date.replace(year=next_year, month=next_month, day=1) - timedelta(days=1)
    
    def get_period_end(self):
        """Get the end date of the current budget period"""
        start = self.get_period_start()
        
        if self.period == 'weekly':
            return start + timedelta(days=6)
        else:  # monthly
            # Last day of the month
            next_month = start.month + 1
            next_year = start.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            
            return start.replace(year=next_year, month=next_month, day=1) - timedelta(days=1)
    
    def should_alert(self):
        """Check if user should be alerted about budget usage"""
        return self.get_percentage_used() >= self.alert_threshold


class UserPreferences(models.Model):
    """
    User-specific settings and preferences
    """
    CURRENCY_CHOICES = (
        ('KSh', 'Kenyan Shilling'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    )
    
    DATE_FORMAT_CHOICES = (
        ('%d/%m/%Y', 'DD/MM/YYYY'),
        ('%m/%d/%Y', 'MM/DD/YYYY'),
        ('%Y-%m-%d', 'YYYY-MM-DD'),
    )
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='expense_preferences'
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='KSh')
    date_format = models.CharField(max_length=20, choices=DATE_FORMAT_CHOICES, default='%d/%m/%Y')
    show_insights = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    budget_alerts = models.BooleanField(default=True)
    weekly_summary = models.BooleanField(default=True)
    theme = models.CharField(max_length=20, default='light', choices=(('light', 'Light'), ('dark', 'Dark')))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'User Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.username}"


class Insight(models.Model):
    """
    AI-generated insights about spending patterns
    """
    INSIGHT_TYPES = (
        ('increase', 'Spending Increase'),
        ('decrease', 'Spending Decrease'),
        ('budget_warning', 'Budget Warning'),
        ('savings', 'Savings Opportunity'),
        ('trend', 'Spending Trend'),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='insights'
    )
    type = models.CharField(max_length=20, choices=INSIGHT_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='insights'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"