"""
Improved simulation command that properly manages wallet states
Place in: merry_go_round/management/commands/mgr_simulate_lifecycle.py
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal

from merry_go_round.models import (
    Round, RoundMembership, Contribution, Payout, 
    UserProfile, MGRWallet
)
from merry_go_round.services import ContributionService, PayoutService
from merry_go_round.wallet_services import WalletService


class Command(BaseCommand):
    help = 'Simulate a complete round lifecycle with proper wallet management'

    def add_arguments(self, parser):
        parser.add_argument(
            '--round-id',
            type=str,
            required=True,
            help='Round ID to simulate'
        )
        parser.add_argument(
            '--auto-fund',
            action='store_true',
            help='Automatically add funds to wallets when needed'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        round_id = options['round_id']
        auto_fund = options['auto_fund']
        verbose = options['verbose']
        
        try:
            round_obj = Round.objects.get(id=round_id)
        except Round.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Round {round_id} not found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*70}'))
        self.stdout.write(self.style.SUCCESS(f'  ROUND LIFECYCLE SIMULATION'))
        self.stdout.write(self.style.SUCCESS(f'  Round: {round_obj.name}'))
        self.stdout.write(self.style.SUCCESS(f'  Model: {round_obj.get_payout_model_display()}'))
        self.stdout.write(self.style.SUCCESS(f'  Members: {round_obj.current_members}'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}\n'))
        
        if round_obj.status != 'active':
            self.stdout.write(self.style.ERROR('Round is not active. Start it first.'))
            return
        
        # Get all contributions ordered by cycle
        total_cycles = round_obj.calculate_total_cycles()
        memberships = RoundMembership.objects.filter(round=round_obj)
        
        self.stdout.write(self.style.WARNING(f'Total cycles to process: {total_cycles}\n'))
        
        # Process each cycle
        for cycle in range(1, total_cycles + 1):
            self.stdout.write(self.style.WARNING(f'\n--- CYCLE {cycle} ---'))
            
            contributions = Contribution.objects.filter(
                membership__round=round_obj,
                cycle_number=cycle,
                status='pending'
            ).select_related('membership__user')
            
            if not contributions.exists():
                self.stdout.write(self.style.WARNING(f'No pending contributions for cycle {cycle}'))
                continue
            
            # Check wallet balances BEFORE processing
            if auto_fund:
                self.ensure_sufficient_funds(contributions, round_obj, verbose)
            
            # Process each contribution
            processed = 0
            failed = 0
            
            for contribution in contributions:
                user = contribution.membership.user
                wallet = MGRWallet.objects.get(user=user)
                
                if verbose:
                    self.stdout.write(
                        f'  Processing {user.username}: '
                        f'Locked={wallet.locked_balance}, '
                        f'Available={wallet.available_balance}'
                    )
                
                try:
                    with transaction.atomic():
                        # Process the contribution
                        ContributionService.process_contribution(contribution)
                        processed += 1
                        
                        if verbose:
                            contribution.refresh_from_db()
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'    ✓ Processed KES {contribution.amount} '
                                    f'(Status: {contribution.status})'
                                )
                            )
                        
                except Exception as e:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(f'    ✗ Failed: {str(e)}')
                    )
                    
                    # Mark as failed
                    contribution.status = 'failed'
                    contribution.save()
            
            self.stdout.write(
                f'\nCycle {cycle} Summary: '
                f'Processed={processed}, Failed={failed}'
            )
            
            # Check if any payouts are due for this cycle (rotational)
            if round_obj.payout_model == 'rotational':
                self.process_rotational_payouts(round_obj, cycle, verbose)
        
        # Check if round should be completed
        if round_obj.payout_model == 'marathon':
            self.stdout.write(self.style.WARNING('\n--- COMPLETING MARATHON ROUND ---'))
            self.complete_marathon_round(round_obj, verbose)
        
        # Final summary
        self.show_final_summary(round_obj)
    
    def ensure_sufficient_funds(self, contributions, round_obj, verbose):
        """Ensure all users have sufficient funds for current + next contribution"""
        
        for contribution in contributions:
            user = contribution.membership.user
            wallet = MGRWallet.objects.get(user=user)
            
            # Calculate needed amount
            # Current contribution should be locked already
            # Need available funds for NEXT contribution
            next_contribution = Contribution.objects.filter(
                membership=contribution.membership,
                cycle_number=contribution.cycle_number + 1,
                status='pending'
            ).first()
            
            if next_contribution:
                needed_available = next_contribution.amount
                current_available = wallet.available_balance
                
                if current_available < needed_available:
                    shortfall = needed_available - current_available
                    
                    # Auto-deposit
                    wallet.balance += shortfall
                    wallet.available_balance += shortfall
                    wallet.total_deposited += shortfall
                    wallet.save()
                    
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  [AUTO-FUND] Added KES {shortfall} to {user.username}\'s wallet'
                            )
                        )
    
    def process_rotational_payouts(self, round_obj, cycle, verbose):
        """Process payouts for rotational model"""
        
        payouts = Payout.objects.filter(
            round=round_obj,
            payout_cycle=cycle,
            status='scheduled'
        )
        
        for payout in payouts:
            try:
                with transaction.atomic():
                    PayoutService.process_payout(payout)
                    
                    if verbose:
                        payout.refresh_from_db()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ Payout to {payout.recipient_membership.user.username}: '
                                f'KES {payout.amount}'
                            )
                        )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'  ✗ Payout failed for {payout.recipient_membership.user.username}: {str(e)}'
                    )
                )
    
    def complete_marathon_round(self, round_obj, verbose):
        """Complete a marathon round and process all payouts"""
        
        from merry_go_round.services import RoundService
        
        try:
            # Set end date to today
            round_obj.end_date = timezone.now().date()
            round_obj.save()
            
            # Complete the round
            RoundService.complete_round(round_obj)
            
            # Process payouts
            payouts = Payout.objects.filter(round=round_obj)
            
            for payout in payouts:
                try:
                    if payout.status != 'completed':
                        PayoutService.process_payout(payout)
                    
                    if verbose:
                        payout.refresh_from_db()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ Final payout to {payout.recipient_membership.user.username}: '
                                f'KES {payout.amount} '
                                f'(Principal: {payout.principal_amount}, '
                                f'Interest: {payout.interest_amount})'
                            )
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ✗ Payout failed: {str(e)}'
                        )
                    )
            
            self.stdout.write(self.style.SUCCESS('\n✓ Round completed successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to complete round: {str(e)}'))
    
    def show_final_summary(self, round_obj):
        """Show final summary of the round"""
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*70}'))
        self.stdout.write(self.style.SUCCESS('  FINAL SUMMARY'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}\n'))
        
        memberships = RoundMembership.objects.filter(round=round_obj)
        
        for membership in memberships:
            contributions = Contribution.objects.filter(membership=membership)
            completed = contributions.filter(status='completed').count()
            missed = contributions.filter(status='missed').count()
            
            payout = Payout.objects.filter(
                recipient_membership=membership,
                status='completed'
            ).first()
            
            self.stdout.write(f'\n{membership.user.username}:')
            self.stdout.write(f'  Contributions: {completed}/{contributions.count()} completed')
            self.stdout.write(f'  Missed: {missed}')
            self.stdout.write(f'  Total Contributed: KES {membership.total_contributed}')
            self.stdout.write(f'  Interest Earned: KES {membership.interest_earned}')
            
            if payout:
                self.stdout.write(f'  Final Payout: KES {payout.amount}')
            
            wallet = MGRWallet.objects.get(user=membership.user)
            self.stdout.write(f'  Wallet Balance: KES {wallet.balance}')
            self.stdout.write(f'  Locked: KES {wallet.locked_balance}')
        
        self.stdout.write(f'\n{"="*70}\n')


# Usage:
# python manage.py mgr_simulate_lifecycle --round-id=<uuid> --auto-fund --verbose