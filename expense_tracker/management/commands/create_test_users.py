from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from expense_tracker.models import Category, Transaction, UserPreferences
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta, date
import random


class Command(BaseCommand):
    help = 'Create test users with sample data for local testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=3,
            help='Number of test users to create (default: 3)',
        )
        parser.add_argument(
            '--with-data',
            action='store_true',
            help='Create sample transactions for test users',
        )
        parser.add_argument(
            '--id-start',
            type=int,
            default=30000000,
            help='Starting national ID number (default: 30000000)',
        )

    def handle(self, *args, **options):
        count = options['count']
        with_data = options['with_data']
        id_start = options['id_start']
        
        self.stdout.write(self.style.WARNING(
            '\n⚠️  This command creates test users for LOCAL DEVELOPMENT ONLY'
        ))
        self.stdout.write(self.style.WARNING(
            '   Do NOT run this in production!\n'
        ))
        
        # Create test users
        test_users = []
        for i in range(count):
            # ✅ NATIONAL ID AS USERNAME (8-digit numeric, realistic Kenyan format)
            national_id = str(id_start + i)
            email = f'user{national_id}@example.com'
            password = 'testpass123'  # Simple password for testing
            
            # Optional: realistic Kenyan names
            first_names = ["John", "Mary", "David", "Grace", "Peter", "Wanja", "Otieno", "Amina"]
            last_names = ["Kamau", "Wangari", "Omondi", "Njeri", "Mwangi", "Akinyi", "Ochieng", "Hassan"]
            
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            
            # Check if user already exists
            if User.objects.filter(username=national_id).exists():
                self.stdout.write(
                    self.style.WARNING(f'User ID {national_id} already exists, skipping...')
                )
                user = User.objects.get(username=national_id)
            else:
                # ✅ Create user with NATIONAL ID as username
                user = User.objects.create_user(
                    username=national_id,      # ← National ID
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created user: {national_id} ({first_name} {last_name})')
                )
            
            test_users.append(user)
            
            # Create default categories for user
            self.create_default_categories(user)
            
            # Create sample data if requested
            if with_data:
                self.create_sample_data(user)
        
        # Display login credentials
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('TEST USER CREDENTIALS (National ID = Username)'))
        self.stdout.write(self.style.SUCCESS('='*60))
        for i, user in enumerate(test_users):
            national_id = user.username
            self.stdout.write(
                f'\nUser {i+1}:'
                f'\n  National ID (Username): {national_id}'
                f'\n  Name: {user.get_full_name()}'
                f'\n  Email: {user.email}'
                f'\n  Password: testpass123'
            )
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Successfully created {len(test_users)} test user(s)'
        ))
        
        if with_data:
            self.stdout.write(self.style.SUCCESS(
                '✓ Sample transactions and data added'
            ))
        
        self.stdout.write(self.style.WARNING(
            '\n⚠️  Remember to delete these users before deploying to production!'
        ))
        self.stdout.write(self.style.NOTICE(
            '\n💡 Tip: Log in at /dev-login/ or use the main login form with National ID + password.'
        ))
    
    def create_default_categories(self, user):
        """Create default categories for a user"""
        # Expense categories
        expense_categories = [
            {'name': 'Food & Dining', 'icon': '🍽️', 'color': '#e74c3c'},
            {'name': 'Transportation', 'icon': '🚗', 'color': '#3498db'},
            {'name': 'Shopping', 'icon': '🛒', 'color': '#9b59b6'},
            {'name': 'Entertainment', 'icon': '🎬', 'color': '#e67e22'},
            {'name': 'Bills & Utilities', 'icon': '💡', 'color': '#f39c12'},
            {'name': 'Healthcare', 'icon': '🏥', 'color': '#1abc9c'},
            {'name': 'Rent', 'icon': '🏠', 'color': '#34495e'},
        ]
        
        # Income categories
        income_categories = [
            {'name': 'Salary', 'icon': '💼', 'color': '#27ae60'},
            {'name': 'Business', 'icon': '📊', 'color': '#16a085'},
            {'name': 'Freelance', 'icon': '💻', 'color': '#8e44ad'},
        ]
        
        # Create expense categories
        for cat_data in expense_categories:
            Category.objects.get_or_create(
                name=cat_data['name'],
                type='expense',
                user=user,
                defaults={
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'is_default': False,
                }
            )
        
        # Create income categories
        for cat_data in income_categories:
            Category.objects.get_or_create(
                name=cat_data['name'],
                type='income',
                user=user,
                defaults={
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'is_default': False,
                }
            )
    
    def create_sample_data(self, user):
        """Create sample transactions for testing"""
        # Get categories
        expense_categories = list(Category.objects.filter(user=user, type='expense'))
        income_categories = list(Category.objects.filter(user=user, type='income'))
        
        if not expense_categories or not income_categories:
            return
        
        today = timezone.now().date()
        
        # ✅ Add UserPreferences (so dashboard doesn’t crash)
        UserPreferences.objects.get_or_create(
            user=user,
            defaults={
                'default_currency': 'KES',
                'date_format': 'YYYY-MM-DD',
                'theme': 'light',
                'notifications_enabled': True,
            }
        )
        
        # Create 1 income transaction (e.g., monthly salary ~1st of month)
        salary_date = date(today.year, today.month, 1)
        Transaction.objects.create(
            user=user,
            type='income',
            category=income_categories[0],  # Salary
            amount=Decimal('65000.00'),
            description='Monthly Salary',
            date=salary_date,
            time=timezone.now().time()
        )
        
        # Create realistic expense pattern (~20 expenses over 30 days)
        expense_descriptions = [
            "Groceries at Naivas", "Matatu fare", "M-Pesa charges", 
            "Airtime purchase", "Lunch at cafe", "Electricity bill",
            "Pharmacy", "Clothes at Eastleigh", "Boda fare", "Dinner with friends"
        ]
        
        for i in range(20):
            days_ago = random.randint(0, 29)
            date_val = today - timedelta(days=days_ago)
            amount = Decimal(str(round(random.uniform(50, 5000), 2)))
            desc = random.choice(expense_descriptions)
            
            Transaction.objects.create(
                user=user,
                type='expense',
                category=random.choice(expense_categories),
                amount=amount,
                description=desc,
                date=date_val,
                time=timezone.now().time()
            )
        
        self.stdout.write(f'  ✓ Created sample data for {user.username}')