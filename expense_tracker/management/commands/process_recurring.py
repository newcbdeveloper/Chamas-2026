# expense_tracker/management/commands/process_recurring.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from expense_tracker.models import RecurringTransaction


class Command(BaseCommand):
    help = 'Process recurring transactions and generate all pending instances (including backfill)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating transactions',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Only process recurring transactions for a specific user ID',
        )
        parser.add_argument(
            '--max-instances',
            type=int,
            default=100,
            help='Maximum number of instances to generate per recurring transaction (safety limit)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        user_id = options.get('user_id')
        max_instances = options['max_instances']
        today = timezone.now().date()

        # Build queryset
        queryset = RecurringTransaction.objects.filter(
            is_active=True,
            auto_generate=True,
            next_occurrence__lte=today  # due or overdue
        ).select_related('user', 'category')

        if user_id:
            queryset = queryset.filter(user_id=user_id)

        total_created = 0
        deactivated_count = 0

        for recurring in queryset:
            # Skip if end_date is passed (deactivate if not already)
            if recurring.end_date and today > recurring.end_date:
                if not dry_run:
                    recurring.is_active = False
                    recurring.save(update_fields=['is_active'])
                deactivated_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Deactivated recurring '{recurring}' (end date {recurring.end_date} passed)"
                    )
                )
                continue

            # ✅ Use generate_all_pending_instances for backfill + current
            if dry_run:
                # Estimate how many would be created
                current = recurring.next_occurrence
                cutoff = recurring.end_date if recurring.end_date and recurring.end_date < today else today
                count = 0
                while current <= cutoff and count < max_instances:
                    # Just count, don't create
                    current = recurring.calculate_next_occurrence(current_date=current)
                    count += 1
                if count > 0:
                    self.stdout.write(
                        f"[DRY RUN] Would generate {count} transaction(s) for '{recurring}' "
                        f"(from {recurring.next_occurrence} to {cutoff})"
                    )
                total_created += count
            else:
                # 🔥 Actual generation with backfill
                created = recurring.generate_all_pending_instances(max_instances=max_instances)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Generated {created} transaction(s) for '{recurring}' (user: {recurring.user.username})"
                        )
                    )
                total_created += created

        # Summary
        summary = []
        if total_created:
            action = 'Would generate' if dry_run else 'Generated'
            summary.append(f"{action} {total_created} transaction(s)")
        if deactivated_count:
            summary.append(f"Deactivated {deactivated_count} expired recurring(s)")
        if not summary:
            summary = ["No recurring transactions to process"]

        self.stdout.write(self.style.SUCCESS(" | ".join(summary)))