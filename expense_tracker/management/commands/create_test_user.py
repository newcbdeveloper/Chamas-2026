# expense_tracker/management/commands/create_test_user.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from expense_tracker.models import Category, Transaction, UserPreferences
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta, date
import random

# Import cross-app models safely
try:
    from authentication.models import Profile
except ImportError:
    Profile = None

try:
    from Dashboard.models import Wallet, Peer_to_Peer_Wallet, Saving_Wallet
    from pyment_withdraw.models import UserBankDetails
except ImportError:
    Wallet = Peer_to_Peer_Wallet = Saving_Wallet = UserBankDetails = None

try:
    from wallet.models import MainWallet
except ImportError:
    MainWallet = None


class Command(BaseCommand):
    help = 'Create test users with specified wallet balances and sample data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=3,
            help='Number of test users to create',
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
            help='Starting national ID number',
        )
        # Added balance argument
        parser.add_argument(
            '--balance',
            type=float,
            default=150000.0,
            help='Initial balance for the wallets (default: 150000)',
        )

    def handle(self, *args, **options):
        count = options['count']
        with_data = options['with_data']
        id_start = options['id_start']
        initial_balance = Decimal(str(options['balance']))
        
        self.stdout.write(self.style.WARNING(
            f'\n🚀 Setting up {count} test users with KES {initial_balance:,.2f} balance...'
        ))

        for i in range(count):
            national_id = str(id_start + i)
            username = national_id
            
            # Generate a unique phone based on the ID to avoid collisions
            # Using 71 followed by the last 8 digits of the national ID
            unique_phone = f'+25471{national_id[-7:]}' 
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': f'Test_{i}',
                    'last_name': 'User',
                    'email': f'testuser{national_id}@example.com'
                }
            )
            
            if created:
                user.set_password('testpass123')
                user.save()
            
            # 1. Authentication Profile
            if Profile:
                # We use get_or_create on 'owner'. If it's a new user, 
                # we provide the unique_phone in defaults.
                Profile.objects.get_or_create(
                    owner=user, 
                    defaults={
                        'NIC_No': national_id, 
                        'phone': unique_phone  # <--- FIX: This is now unique per ID
                    }
                )
 

            # 2. LEGACY DASHBOARD WALLETS (Updated with initial_balance)
            if Wallet:
                w, _ = Wallet.objects.get_or_create(user_id=user)
                w.available_for_withdraw = initial_balance
                w.save()
                
            if Peer_to_Peer_Wallet:
                p2p, _ = Peer_to_Peer_Wallet.objects.get_or_create(user_id=user)
                p2p.available_balance = initial_balance
                p2p.save()
                
            if Saving_Wallet:
                sw, _ = Saving_Wallet.objects.get_or_create(user_id=user)
                sw.available_balance = initial_balance
                sw.save()

            if UserBankDetails:
                UserBankDetails.objects.get_or_create(user_id=user)

            # 3. NEW WALLET APP - MainWallet (Updated with initial_balance)
            if MainWallet:
                mw, _ = MainWallet.objects.get_or_create(user=user)
                mw.balance = initial_balance
                mw.available_balance = initial_balance
                mw.currency = 'KES'
                mw.status = 'active'
                mw.save()

            # 4. User Preferences
            UserPreferences.objects.get_or_create(user=user)

            # 5. Optional Sample Data
            if with_data:
                self.create_sample_data(user)
            
            status_msg = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f'✓ {status_msg} user {username} with balance {initial_balance:,.2f}'))

    def create_sample_data(self, user):
        """Creates sample categories and a few transactions"""
        cat, _ = Category.objects.get_or_create(name='General', type='expense', user=user)
        inc, _ = Category.objects.get_or_create(name='Salary', type='income', user=user)
        
        Transaction.objects.create(
            user=user, 
            type='income', 
            category=inc, 
            amount=Decimal('150000.00'), 
            date=timezone.now().date(), 
            description='Initial Test Balance Deposit'
        )

#To run this Command and create users with 150k balance

#python manage.py create_test_user --count 2 --id-start 30000005

#To create users with a different balance (e.g., 50,000):

#python manage.py create_test_user --count 1 --id-start 30000010 --balance 50000