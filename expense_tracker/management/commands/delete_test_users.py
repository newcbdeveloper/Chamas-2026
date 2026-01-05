from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction


class Command(BaseCommand):
    help = 'Delete test users created for local testing (before deployment)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of test users',
        )
        parser.add_argument(
            '--id-start',
            type=int,
            default=30000000,
            help='Minimum national ID to consider as test user (default: 30000000)',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.ERROR(
                    '\n⚠️  This will DELETE test users with NATIONAL ID >= 30000000'
                    '\n   Run with --confirm flag to proceed'
                    '\n   Example: python manage.py delete_test_users --confirm\n'
                )
            )
            self.stdout.write(
                self.style.NOTICE(
                    '💡 Tip: Use --id-start=35000000 to target specific ranges.'
                )
            )
            return
        
        id_start = options['id-start']
        
        # ✅ Find users with numeric usernames >= id_start (assumed test users)
        # Exclude superusers to avoid accidental admin deletion
        test_users = User.objects.filter(
            username__regex=r'^\d+$',          # Only numeric usernames
            username__gte=str(id_start),        # ≥ starting ID (e.g., 30000000)
        ).exclude(
            is_superuser=True                   # Never delete real admins
        ).order_by('username')
        
        count = test_users.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING(
                f'No test users found with ID ≥ {id_start}.'
            ))
            return
        
        # Display users to be deleted
        self.stdout.write(self.style.WARNING('\nThe following test users will be deleted:'))
        for user in test_users:
            self.stdout.write(
                f'  - ID: {user.username} | Name: {user.get_full_name()} | Email: {user.email}'
            )
        
        self.stdout.write(self.style.ERROR(
            f'\n⚠️  About to delete {count} test user(s) and ALL their related data (transactions, budgets, etc.)!'
        ))
        
        # Safety confirmation
        confirm = input('Type "DELETE" to confirm: ')
        
        if confirm == 'DELETE':
            with transaction.atomic():  # Ensures full rollback on error
                deleted_count = 0
                for user in test_users:
                    username = user.username
                    full_name = user.get_full_name()
                    user.delete()
                    deleted_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Deleted {username} ({full_name})')
                    )
            
            self.stdout.write(self.style.SUCCESS(
                f'\n✨ Successfully deleted {deleted_count} test user(s) and all associated data.'
            ))
            self.stdout.write(self.style.NOTICE(
                '\n✅ Safe to deploy now — no test credentials remain.'
            ))
        else:
            self.stdout.write(self.style.WARNING('\n🚫 Deletion cancelled.'))