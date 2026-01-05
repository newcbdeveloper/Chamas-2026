# merry_go_round/management/commands/freeze_completed_rounds.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from decimal import Decimal
from merry_go_round.models import Round, RoundCompletionStats, Payout
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Freeze statistics for all completed rounds that don\'t have frozen stats yet'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be frozen without actually saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))
        
        # Find completed rounds without frozen stats
        completed_rounds = Round.objects.filter(
            status='completed'
        ).exclude(
            completion_snapshot__isnull=False
        )
        
        count = completed_rounds.count()
        self.stdout.write(f'Found {count} completed rounds without frozen stats')
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✅ All completed rounds already have frozen stats'))
            return
        
        frozen_count = 0
        failed_count = 0
        
        for round_obj in completed_rounds:
            try:
                with transaction.atomic():
                    # Calculate statistics based on ACTUAL payouts
                    total_cycles = round_obj.calculate_total_cycles()
                    total_expected = round_obj.contribution_amount * round_obj.max_members * total_cycles
                    
                    # Get actual totals from completed payouts
                    completed_payouts = Payout.objects.filter(
                        round=round_obj,
                        status='completed'
                    ).aggregate(
                        total_paid=Sum('amount'),
                        total_principal=Sum('principal_amount'),
                        total_interest=Sum('interest_amount')
                    )
                    
                    total_paid_out = completed_payouts['total_paid'] or Decimal('0.00')
                    total_principal = completed_payouts['total_principal'] or Decimal('0.00')
                    total_net_interest = completed_payouts['total_interest'] or Decimal('0.00')
                    
                    # Get current tax rate
                    from constance import config
                    tax_rate_percent = config.MGR_TAX_RATE
                    tax_rate_decimal = Decimal(str(tax_rate_percent)) / 100
                    
                    # Reverse-calculate gross interest from net
                    if total_net_interest > 0:
                        total_gross_interest = total_net_interest / (1 - tax_rate_decimal)
                        total_tax = total_gross_interest - total_net_interest
                    else:
                        total_gross_interest = Decimal('0.00')
                        total_tax = Decimal('0.00')
                    
                    completion_pct = (total_principal / total_expected * 100) if total_expected > 0 else 0
                    
                    if not dry_run:
                        # Create frozen stats
                        RoundCompletionStats.objects.create(
                            round=round_obj,
                            total_expected_contributions=total_expected,
                            total_actual_contributions=total_principal,
                            completion_percentage=completion_pct,
                            total_gross_interest=total_gross_interest,
                            total_tax_deducted=total_tax,
                            total_net_interest=total_net_interest,
                            total_paid_out=total_paid_out,
                            interest_rate_used=round_obj.interest_rate,
                            tax_rate_used=tax_rate_percent
                        )
                    
                    frozen_count += 1
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'{"[DRY RUN] Would freeze" if dry_run else "✅ Frozen"}: '
                            f'{round_obj.name} - '
                            f'Expected: KES {total_expected}, '
                            f'Actual: KES {total_principal}, '
                            f'Net Interest: KES {total_net_interest}'
                        )
                    )
                    
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Failed to freeze {round_obj.name}: {str(e)}'
                    )
                )
                logger.error(f'Failed to freeze round {round_obj.id}: {str(e)}')
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Total rounds processed: {count}'))
        self.stdout.write(self.style.SUCCESS(f'  Successfully frozen: {frozen_count}'))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f'  Failed: {failed_count}'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('This was a DRY RUN - no changes were saved'))
            self.stdout.write(self.style.WARNING('Run without --dry-run to actually freeze the stats'))