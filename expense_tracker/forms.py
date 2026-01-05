from django import forms
from django.core.exceptions import ValidationError
from .models import Transaction, Category, Budget, RecurringTransaction, UserPreferences
from decimal import Decimal


class TransactionForm(forms.ModelForm):
    """Form for creating and editing transactions"""
    
    class Meta:
        model = Transaction
        fields = ['type', 'category', 'amount', 'description', 'date', 'time']
        widgets = {
            'type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'transaction-type'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control',
                'id': 'transaction-category'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter description (optional)'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter categories based on user
        if self.user:
            self.fields['category'].queryset = Category.get_user_categories(self.user)
        
        # Update category choices based on transaction type if instance exists
        if self.instance and self.instance.pk:
            self.fields['category'].queryset = Category.get_user_categories(
                self.user, 
                self.instance.type
            )
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise ValidationError('Amount must be greater than zero.')
        return amount


class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""
    
    class Meta:
        model = Category
        fields = ['name', 'type', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Category name'
            }),
            'type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '💰 (emoji or icon class)'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        category_type = self.cleaned_data.get('type')
        
        # Check for duplicate category names for this user and type
        if self.user:
            existing = Category.objects.filter(
                name__iexact=name,
                type=category_type,
                user=self.user
            )
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f'You already have a {category_type} category named "{name}".')
        
        return name


class BudgetForm(forms.ModelForm):
    """Form for creating and editing budgets"""
    
    class Meta:
        model = Budget
        fields = ['category', 'amount', 'period', 'start_date', 'rollover_enabled', 'alert_threshold']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'period': forms.Select(attrs={
                'class': 'form-control'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'rollover_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'alert_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'placeholder': '80'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Only show expense categories
        if self.user:
            self.fields['category'].queryset = Category.get_user_categories(
                self.user, 
                'expense'
            )
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        period = cleaned_data.get('period')
        
        # Check for existing budget with same category and period
        if self.user and category and period:
            existing = Budget.objects.filter(
                user=self.user,
                category=category,
                period=period,
                is_active=True
            )
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(
                    f'You already have an active {period} budget for {category.name}.'
                )
        
        return cleaned_data


class RecurringTransactionForm(forms.ModelForm):
    """Form for creating and editing recurring transactions"""
    
    class Meta:
        model = RecurringTransaction
        fields = [
            'type', 'category', 'amount', 'description', 
            'frequency', 'start_date', 'end_date', 'auto_generate'
        ]
        widgets = {
            'type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Monthly rent, Weekly salary'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'auto_generate': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter categories
        if self.user:
            self.fields['category'].queryset = Category.get_user_categories(self.user)
        
        # Make end_date optional
        self.fields['end_date'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise ValidationError('End date must be after start date.')
        
        return cleaned_data


class UserPreferencesForm(forms.ModelForm):
    """Form for user preferences/settings"""
    
    class Meta:
        model = UserPreferences
        fields = [
            'currency', 'date_format', 'theme',
            'show_insights', 'email_notifications', 
            'budget_alerts', 'weekly_summary'
        ]
        widgets = {
            'currency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'date_format': forms.Select(attrs={
                'class': 'form-control'
            }),
            'theme': forms.Select(attrs={
                'class': 'form-control'
            }),
            'show_insights': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'email_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'budget_alerts': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'weekly_summary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class DateRangeForm(forms.Form):
    """Form for filtering by date range"""
    
    PERIOD_CHOICES = (
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('this_week', 'This Week'),
        ('last_week', 'Last Week'),
        ('this_month', 'This Month'),
        ('last_month', 'Last Month'),
        ('this_year', 'This Year'),
        ('custom', 'Custom Range'),
    )
    
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        period = cleaned_data.get('period')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if period == 'custom':
            if not start_date or not end_date:
                raise ValidationError('Both start and end dates are required for custom range.')
            if end_date < start_date:
                raise ValidationError('End date must be after start date.')
        
        return cleaned_data