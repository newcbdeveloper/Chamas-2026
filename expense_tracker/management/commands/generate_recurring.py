
from django.core.management.base import BaseCommand
from expense_tracker.utils import generate_recurring_transactions

class Command(BaseCommand):
    help = 'Generate pending recurring transactions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Only generate for specific user ID'
        )
        parser.add_argument(
            '--max',
            type=int,
            default=100,
            help='Max instances per recurring transaction (default: 100)'
        )

    def handle(self, *args, **options):
        user_id = options['user_id']
        max_instances = options['max']

        self.stdout.write(
            self.style.NOTICE(f'Generating recurring transactions (max={max_instances})...')
        )

        try:
            count = generate_recurring_transactions(
                user_id=user_id,
                max_instances_per_recurring=max_instances
            )
            self.stdout.write(
                self.style.SUCCESS(f'Successfully generated {count} transaction(s).')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )
            raise