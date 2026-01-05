"""
Create this file: merry_go_round/management/commands/mgr_reset_round.py

This command completely resets a round to its initial state
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from merry_go_round.models import (
    Round, RoundMembership, Contribution, Payout, 
    MGRWallet, MGRTransaction
)
from merry_go_round.services import ContributionService, PayoutService
from merry_go_round.wallet_services import WalletService


class Command(BaseCommand):
    help = 'Reset a round to initial state and regenerate schedules'

    def add_arguments(self, parser):
        parser.add_argument(
            '--round-name',
            type=str,
            help='Round name to reset',
        )
        parser.add_argument(
            '--round-id',
            type=str,
            help='Round ID (UUID) to reset',
        )
        parser.add_argument(
            '--fund-wallets',
            action='store_true',
            help='Automatically ensure wallets have sufficient funds',
        )
        parser.add_argument(
            '--start-tomorrow',
            action='store_true',
            help='Set start date to tomorrow (default)',
            default=True,
        )

    def handle(self, *args, **options):
        round_name = options.get('round_name')
        round_id = options.get('round_id')
        fund_wallets = options.get('fund_wallets')
        
        # Find the round
        try:
            if round_id:
                round_obj = Round.objects.get(id=round_id)
            elif round_name:
                round_obj = Round.objects.get(name__iexact=round_name)
            else:
                self.stdout.write(self.style.ERROR('Please specify --round-name or --round-id'))
                return
        except Round.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Round not found'))
            return
        except Round.MultipleObjectsReturned:
            self.stdout.write(self.style.ERROR(f'Multiple rounds found with name "{round_name}"'))
            rounds = Round.objects.filter(name__icontains=round_name)
            for r in rounds:
                self.stdout.write(f'  - {r.name} (ID: {r.id})')
            return
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('  ROUND RESET'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        self.stdout.write(f'Round: {round_obj.name}')
        self.stdout.write(f'ID: {round_obj.id}')
        self.stdout.write(f'Status: {round_obj.status}')
        self.stdout.write(f'Members: {round_obj.current_members}')
        self.stdout.write(f'Model: {round_obj.get_payout_model_display()}')
        
        # Get memberships
        memberships = RoundMembership.objects.filter(round=round_obj)
        self.stdout.write(f'\nMembers: {", ".join([m.user.username for m in memberships])}')
        
        # Show what will be deleted
        contrib_count = Contribution.objects.filter(membership__round=round_obj).count()
        payout_count = Payout.objects.filter(round=round_obj).count()
        
        self.stdout.write(f'\n⚠️  This will:')
        self.stdout.write(f'  1. Delete {contrib_count} contributions')
        self.stdout.write(f'  2. Delete {payout_count} payouts')
        self.stdout.write(f'  3. Unlock all funds from memberships')
        self.stdout.write(f'  4. Reset membership stats')
        if fund_wallets:
            self.stdout.write(f'  5. Ensure wallets have sufficient funds')
        self.stdout.write(f'  6. Regenerate contribution schedule')
        self.stdout.write(f'  7. Regenerate payout schedule')
        self.stdout.write(f'  8. Set new start date')
        
        response = input('\nProceed? (yes/no): ')
        
        if response.lower() != 'yes':
            self.stdout.write(self.style.WARNING('Aborted.'))
            return
        
        self.stdout.write('\n' + '='*70)
        self.stdout.write('RESETTING...')
        self.stdout.write('='*70 + '\n')
        
        with transaction.atomic():
            # Step 1: Delete contributions and payouts
            Contribution.objects.filter(membership__round=round_obj).delete()
            Payout.objects.filter(round=round_obj).delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {contrib_count} contributions'))
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {payout_count} payouts'))
            
            # Step 2: Unlock funds and reset memberships
            for membership in memberships:
                if membership.locked_amount > 0:
                    try:
                        WalletService.unlock_all_funds_for_round(membership.user, round_obj)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Unlocked KES {membership.locked_amount} for {membership.user.username}'
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠ Could not unlock funds for {membership.user.username}: {str(e)}'
                            )
                        )
                
                # Reset membership
                membership.locked_amount = Decimal('0.00')
                membership.total_contributed = Decimal('0.00')
                membership.interest_earned = Decimal('0.00')
                membership.contributions_made = 0
                membership.contributions_missed = 0
                membership.has_received_payout = False
                membership.payout_received_date = None
                membership.payout_amount = Decimal('0.00')
                membership.status = 'active'
                membership.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Reset membership for {membership.user.username}')
                )
            
            # Step 3: Fund wallets if requested
            if fund_wallets:
                self.stdout.write('\n' + '-'*70)
                self.stdout.write('FUNDING WALLETS')
                self.stdout.write('-'*70 + '\n')
                
                for membership in memberships:
                    wallet = MGRWallet.objects.get(user=membership.user)
                    
                    # Calculate total needed for all cycles
                    total_cycles = round_obj.calculate_total_cycles()
                    total_needed = round_obj.contribution_amount * total_cycles
                    
                    # Add buffer for next contribution reservations
                    total_needed += round_obj.contribution_amount
                    
                    current = wallet.available_balance
                    
                    self.stdout.write(f'{membership.user.username}:')
                    self.stdout.write(f'  Current: KES {current}')
                    self.stdout.write(f'  Needed: KES {total_needed}')
                    
                    if current < total_needed:
                        shortfall = total_needed - current
                        wallet.balance += shortfall
                        wallet.available_balance += shortfall
                        wallet.total_deposited += shortfall
                        wallet.save()
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Added KES {shortfall}'))
                    else:
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Sufficient'))
            
            # Step 4: Lock first contributions
            self.stdout.write('\n' + '-'*70)
            self.stdout.write('LOCKING FIRST CONTRIBUTIONS')
            self.stdout.write('-'*70 + '\n')
            
            for membership in memberships:
                try:
                    WalletService.reserve_next_contribution(
                        membership.user,
                        round_obj,
                        round_obj.contribution_amount
                    )
                    
                    membership.locked_amount = round_obj.contribution_amount
                    membership.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Locked KES {round_obj.contribution_amount} for {membership.user.username}'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Failed to lock funds for {membership.user.username}: {str(e)}'
                        )
                    )
            
            # Step 5: Reset round dates
            self.stdout.write('\n' + '-'*70)
            self.stdout.write('SETTING NEW DATES')
            self.stdout.write('-'*70 + '\n')
            
            round_obj.start_date = timezone.now().date() + timedelta(days=1)
            round_obj.next_contribution_date = round_obj.start_date
            
            total_cycles = round_obj.calculate_total_cycles()
            cycle_days = round_obj.get_cycle_duration_days()
            round_obj.end_date = round_obj.start_date + timedelta(days=total_cycles * cycle_days)
            
            round_obj.total_pool = Decimal('0.00')
            round_obj.total_interest_earned = Decimal('0.00')
            round_obj.status = 'active'
            round_obj.save()
            
            self.stdout.write(f'Start Date: {round_obj.start_date}')
            self.stdout.write(f'End Date: {round_obj.end_date}')
            self.stdout.write(f'Total Cycles: {total_cycles}')
            self.stdout.write(f'Cycle Duration: {cycle_days} days')
            
            # Step 6: Regenerate contribution schedule
            self.stdout.write('\n' + '-'*70)
            self.stdout.write('GENERATING CONTRIBUTION SCHEDULE')
            self.stdout.write('-'*70 + '\n')
            
            for membership in memberships:
                ContributionService.generate_contribution_schedule(membership)
                
                contributions = Contribution.objects.filter(
                    membership=membership
                ).order_by('cycle_number')
                
                self.stdout.write(f'\n{membership.user.username}:')
                for contrib in contributions:
                    self.stdout.write(f'  Cycle {contrib.cycle_number}: Due {contrib.due_date}')
            
            # Step 7: Regenerate payout schedule
            self.stdout.write('\n' + '-'*70)
            self.stdout.write('GENERATING PAYOUT SCHEDULE')
            self.stdout.write('-'*70 + '\n')
            
            PayoutService.generate_payout_schedule(round_obj)
            
            payouts = Payout.objects.filter(round=round_obj).order_by('payout_cycle')
            for payout in payouts:
                self.stdout.write(
                    f'  Cycle {payout.payout_cycle}: '
                    f'{payout.recipient_membership.user.username} - '
                    f'{payout.scheduled_date}'
                )
        
        # Success summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('✓ RESET COMPLETE!'))
        self.stdout.write('='*70 + '\n')
        
        self.stdout.write('\nNext steps to test:')
        self.stdout.write('  1. python manage.py mgr_fastforward --round-name="' + round_obj.name + '" --days=0 --max-contributions=2 --direction=backward')
        self.stdout.write('  2. python manage.py mgr_simulate --verbose')
        self.stdout.write('  3. Check that BOTH users have contributions processed')
        self.stdout.write('\n')