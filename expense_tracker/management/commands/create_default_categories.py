from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from expense_tracker.models import Category


class Command(BaseCommand):
    help = 'Create default categories for all users or a specific user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Create categories for specific user',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Create categories for all users',
        )

    def handle(self, *args, **options):
        # Default expense categories
        default_expense_categories = [
            {'name': 'Food & Dining', 'icon': '🍽️', 'color': '#e74c3c'},
            {'name': 'Transportation', 'icon': '🚗', 'color': '#3498db'},
            {'name': 'Shopping', 'icon': '🛒', 'color': '#9b59b6'},
            {'name': 'Entertainment', 'icon': '🎬', 'color': '#e67e22'},
            {'name': 'Bills & Utilities', 'icon': '💡', 'color': '#f39c12'},
            {'name': 'Healthcare', 'icon': '🏥', 'color': '#1abc9c'},
            {'name': 'Education', 'icon': '📚', 'color': '#2ecc71'},
            {'name': 'Rent', 'icon': '🏠', 'color': '#34495e'},
            {'name': 'Personal Care', 'icon': '💅', 'color': '#e91e63'},
            {'name': 'Groceries', 'icon': '🛍️', 'color': '#ff5722'},
            {'name': 'Insurance', 'icon': '🛡️', 'color': '#607d8b'},
            {'name': 'Other Expenses', 'icon': '💰', 'color': '#95a5a6'},
        ]
        
        # Default income categories
        default_income_categories = [
            {'name': 'Salary', 'icon': '💼', 'color': '#27ae60'},
            {'name': 'Business', 'icon': '📊', 'color': '#16a085'},
            {'name': 'Investments', 'icon': '📈', 'color': '#2980b9'},
            {'name': 'Freelance', 'icon': '💻', 'color': '#8e44ad'},
            {'name': 'Gifts', 'icon': '🎁', 'color': '#c0392b'},
            {'name': 'Refunds', 'icon': '💵', 'color': '#00bcd4'},
            {'name': 'Other Income', 'icon': '💵', 'color': '#27ae60'},
        ]
        
        # Get users
        if options['username']:
            try:
                users = [User.objects.get(username=options['username'])]
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User "{options["username"]}" not found')
                )
                return
        elif options['all']:
            users = User.objects.all()
        else:
            self.stdout.write(
                self.style.ERROR('Please specify --username <username> or --all')
            )
            return
        
        total_created = 0
        
        for user in users:
            created_for_user = 0
            
            # Create expense categories
            for cat_data in default_expense_categories:
                category, created = Category.objects.get_or_create(
                    name=cat_data['name'],
                    type='expense',
                    user=user,
                    defaults={
                        'icon': cat_data['icon'],
                        'color': cat_data['color'],
                        'is_default': False,
                    }
                )
                if created:
                    created_for_user += 1
            
            # Create income categories
            for cat_data in default_income_categories:
                category, created = Category.objects.get_or_create(
                    name=cat_data['name'],
                    type='income',
                    user=user,
                    defaults={
                        'icon': cat_data['icon'],
                        'color': cat_data['color'],
                        'is_default': False,
                    }
                )
                if created:
                    created_for_user += 1
            
            if created_for_user > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created {created_for_user} categories for {user.username}'
                    )
                )
                total_created += created_for_user
            else:
                self.stdout.write(
                    f'All categories already exist for {user.username}'
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Total categories created: {total_created}')
        )