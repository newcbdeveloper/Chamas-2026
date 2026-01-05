from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from .models import (
    Category, Transaction, Budget, RecurringTransaction, 
    UserPreferences, Insight
)
from .utils import calculate_summary, get_category_breakdown


class CategoryModelTest(TestCase):
    """Test Category model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_category_creation(self):
        """Test creating a category"""
        category = Category.objects.create(
            name='Test Category',
            type='expense',
            user=self.user,
            icon='💰',
            color='#3498db'
        )
        self.assertEqual(str(category), 'Test Category (Expense)')
    
    def test_get_user_categories(self):
        """Test getting user categories"""
        # Create user categories
        Category.objects.create(
            name='Custom Expense',
            type='expense',
            user=self.user
        )
        
        # Get all expense categories for user
        categories = Category.get_user_categories(self.user, 'expense')
        self.assertTrue(categories.filter(name='Custom Expense').exists())


class TransactionModelTest(TestCase):
    """Test Transaction model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Food',
            type='expense',
            user=self.user
        )
    
    def test_transaction_creation(self):
        """Test creating a transaction"""
        transaction = Transaction.objects.create(
            user=self.user,
            type='expense',
            category=self.category,
            amount=Decimal('1500.00'),
            description='Lunch',
            date=timezone.now().date()
        )
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.amount, Decimal('1500.00'))
    
    def test_signed_amount(self):
        """Test signed_amount property"""
        # Income should be positive
        income = Transaction.objects.create(
            user=self.user,
            type='income',
            amount=Decimal('5000.00'),
            date=timezone.now().date()
        )
        self.assertEqual(income.signed_amount, Decimal('5000.00'))
        
        # Expense should be negative
        expense = Transaction.objects.create(
            user=self.user,
            type='expense',
            amount=Decimal('1000.00'),
            date=timezone.now().date()
        )
        self.assertEqual(expense.signed_amount, Decimal('-1000.00'))


class BudgetModelTest(TestCase):
    """Test Budget model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Food',
            type='expense',
            user=self.user
        )
        self.budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('10000.00'),
            period='monthly'
        )
    
    def test_budget_creation(self):
        """Test creating a budget"""
        self.assertEqual(self.budget.amount, Decimal('10000.00'))
        self.assertEqual(self.budget.period, 'monthly')
    
    def test_get_spent_amount(self):
        """Test calculating spent amount"""
        # Create some transactions
        Transaction.objects.create(
            user=self.user,
            type='expense',
            category=self.category,
            amount=Decimal('3000.00'),
            date=timezone.now().date()
        )
        Transaction.objects.create(
            user=self.user,
            type='expense',
            category=self.category,
            amount=Decimal('2000.00'),
            date=timezone.now().date()
        )
        
        spent = self.budget.get_spent_amount()
        self.assertEqual(spent, Decimal('5000.00'))
    
    def test_get_percentage_used(self):
        """Test calculating percentage used"""
        # Create transaction
        Transaction.objects.create(
            user=self.user,
            type='expense',
            category=self.category,
            amount=Decimal('5000.00'),
            date=timezone.now().date()
        )
        
        percentage = self.budget.get_percentage_used()
        self.assertEqual(percentage, 50.0)


class UtilsTest(TestCase):
    """Test utility functions"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Food',
            type='expense',
            user=self.user
        )
    
    def test_calculate_summary(self):
        """Test calculate_summary function"""
        today = timezone.now().date()
        
        # Create transactions
        Transaction.objects.create(
            user=self.user,
            type='income',
            amount=Decimal('50000.00'),
            date=today
        )
        Transaction.objects.create(
            user=self.user,
            type='expense',
            category=self.category,
            amount=Decimal('15000.00'),
            date=today
        )
        
        summary = calculate_summary(self.user, today, today)
        
        self.assertEqual(summary['income'], Decimal('50000.00'))
        self.assertEqual(summary['expenses'], Decimal('15000.00'))
        self.assertEqual(summary['balance'], Decimal('35000.00'))
    
    def test_get_category_breakdown(self):
        """Test get_category_breakdown function"""
        today = timezone.now().date()
        
        # Create transactions
        Transaction.objects.create(
            user=self.user,
            type='expense',
            category=self.category,
            amount=Decimal('3000.00'),
            date=today
        )
        Transaction.objects.create(
            user=self.user,
            type='expense',
            category=self.category,
            amount=Decimal('2000.00'),
            date=today
        )
        
        breakdown = get_category_breakdown(self.user, 'expense', today, today)
        
        self.assertEqual(len(breakdown), 1)
        self.assertEqual(breakdown[0]['category'], 'Food')
        self.assertEqual(breakdown[0]['amount'], Decimal('5000.00'))


class ViewsTest(TestCase):
    """Test views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Food',
            type='expense',
            user=self.user
        )
    
    def test_dashboard_requires_login(self):
        """Test that dashboard requires authentication"""
        response = self.client.get(reverse('expense_tracker:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_dashboard_view(self):
        """Test dashboard view"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('expense_tracker:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'expense_tracker/dashboard.html')
    
    def test_transaction_create(self):
        """Test creating a transaction via view"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(reverse('expense_tracker:transaction_create'), {
            'type': 'expense',
            'category': self.category.id,
            'amount': '1500.00',
            'description': 'Test transaction',
            'date': timezone.now().date(),
            'time': timezone.now().time(),
        })
        
        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)
        
        # Check transaction was created
        self.assertTrue(
            Transaction.objects.filter(
                user=self.user,
                description='Test transaction'
            ).exists()
        )


class RecurringTransactionTest(TestCase):
    """Test RecurringTransaction model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Salary',
            type='income',
            user=self.user
        )
    
    def test_calculate_next_occurrence_monthly(self):
        """Test calculating next occurrence for monthly frequency"""
        recurring = RecurringTransaction.objects.create(
            user=self.user,
            type='income',
            category=self.category,
            amount=Decimal('50000.00'),
            frequency='monthly',
            start_date=timezone.now().date(),
            next_occurrence=timezone.now().date()
        )
        
        original_date = recurring.next_occurrence
        next_date = recurring.calculate_next_occurrence()
        
        # Should be roughly 30 days later (accounting for month length)
        days_difference = (next_date - original_date).days
        self.assertTrue(28 <= days_difference <= 31)
    
    def test_generate_transaction(self):
        """Test generating a transaction from recurring template"""
        recurring = RecurringTransaction.objects.create(
            user=self.user,
            type='income',
            category=self.category,
            amount=Decimal('50000.00'),
            description='Monthly salary',
            frequency='monthly',
            start_date=timezone.now().date(),
            next_occurrence=timezone.now().date()
        )
        
        original_next = recurring.next_occurrence
        transaction = recurring.generate_transaction()
        
        # Check transaction was created
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('50000.00'))
        self.assertEqual(transaction.is_recurring, True)
        
        # Check next_occurrence was updated
        recurring.refresh_from_db()
        self.assertNotEqual(recurring.next_occurrence, original_next)