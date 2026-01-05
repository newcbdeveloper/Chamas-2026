# merry_go_round/management/commands/simulate_time_passage.py
import logging
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from freezegun import freeze_time
from decimal import Decimal
from django.db.models import Sum
import pytz

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Simulate the passage of time to complete all rounds within a given period'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Number of days to simulate (default: 365)',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date in YYYY-MM-DD format (default: today)',
        )
        parser.add_argument(
            '--step-days',
            type=int,
            default=1,
            help='Days to advance per simulation step (default: 1)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each step',
        )
        parser.add_argument(
            '--fix-existing',
            action='store_true',
            help='Create missing RoundCompletionStats for already completed rounds',
        )

    def handle(self, *args, **options):
        days = options['days']
        step_days = options['step_days']
        verbose = options['verbose']
        fix_existing = options['fix_existing']
        
        # FIRST: Fix any existing completed rounds without stats
        if fix_existing:
            self.fix_existing_completed_rounds()
        
        # Determine start date (make it timezone aware)
        if options['start_date']:
            start_date = timezone.make_aware(
                timezone.datetime.fromisoformat(options['start_date'])
            )
        else:
            start_date = timezone.now()
        
        # Set to start of day
        start_date = start_date.replace(hour=6, minute=0, second=0, microsecond=0)

        end_date = start_date + timedelta(days=days)
        current_datetime = start_date

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🚀 Starting time simulation:\n"
                f"   From: {start_date.date()}\n"
                f"   To:   {end_date.date()}\n"
                f"   Step: {step_days} day(s)\n"
                f"   Total steps: {days // step_days}\n"
                f"   Timezone: {timezone.get_current_timezone_name()}\n"
            )
        )

        # Begin time simulation
        with freeze_time(start_date) as frozen:
            step = 0
            while current_datetime <= end_date:
                step += 1
                current_date = current_datetime.date()
                
                if verbose:
                    self.stdout.write(
                        self.style.WARNING(f"\n📅 Step {step}: Simulating {current_date}")
                    )
                else:
                    if step % 10 == 0:
                        self.stdout.write(f"Progress: Day {current_date} ({step}/{days // step_days})")

                try:
                    # Import models here to avoid issues
                    from merry_go_round.models import (
                        Contribution, Round, RoundMembership, Payout,
                        UserProfile, MGRTransaction, RoundCompletionStats
                    )
                    from merry_go_round.wallet_services import WalletService
                    
                    # ========================================
                    # 1. PROCESS CONTRIBUTIONS DUE TODAY OR OVERDUE
                    # ========================================
                    if verbose:
                        self.stdout.write("   🔄 Processing due contributions...")
                    
                    # FIXED: Process ALL contributions due on or before today
                    due_contributions = Contribution.objects.filter(
                        status='pending',
                        due_date__lte=current_date  # CHANGED: Use __lte instead of =
                    ).select_related(
                        'membership__user', 
                        'membership__round'
                    )
                    
                    processed_count = 0
                    failed_count = 0
                    
                    for contribution in due_contributions:
                        try:
                            wallet = WalletService.get_or_create_wallet(contribution.membership.user)
                            
                            # FIXED: Check total balance (not just available) since we're simulating
                            if wallet.balance >= contribution.amount:
                                # Set payment date to due date (not current date) for accurate interest
                                contribution.payment_date = timezone.make_aware(
                                    timezone.datetime.combine(contribution.due_date, timezone.datetime.min.time())
                                )
                                
                                # Process the contribution
                                txn = WalletService.process_contribution(contribution)
                                
                                # Update contribution
                                contribution.status = 'completed'
                                contribution.wallet_transaction = txn
                                contribution.save()
                                
                                # Update membership
                                membership = contribution.membership
                                membership.total_contributed += contribution.amount
                                membership.contributions_made += 1
                                membership.save()
                                
                                # Update user profile
                                profile = membership.user.mgr_profile
                                profile.total_contributions += contribution.amount
                                profile.save()
                                
                                # Initialize interest tracking
                                contribution.days_in_escrow = 0
                                contribution.interest_accrued = Decimal('0.00')
                                contribution.save()
                                
                                processed_count += 1
                                
                                if verbose:
                                    self.stdout.write(f"      ✅ Processed: {contribution.membership.user.username}, Cycle {contribution.cycle_number}, KES {contribution.amount}")
                            else:
                                contribution.status = 'failed'
                                contribution.save()
                                failed_count += 1
                                
                                if verbose:
                                    self.stdout.write(f"      ❌ Failed: {contribution.membership.user.username}, insufficient funds")
                        except Exception as e:
                            contribution.status = 'failed'
                            contribution.save()
                            failed_count += 1
                            if verbose:
                                self.stdout.write(f"      ❌ Error: {str(e)}")
                    
                    # ========================================
                    # 2. MARK MISSED CONTRIBUTIONS
                    # ========================================
                    if verbose:
                        self.stdout.write("   🔄 Marking missed contributions...")
                    
                    overdue = Contribution.objects.filter(
                        status__in=['pending', 'failed'],
                        due_date__lt=current_date,
                        membership__round__status='active'
                    )
                    
                    missed_count = 0
                    for contribution in overdue:
                        contribution.mark_as_missed()
                        missed_count += 1
                    
                    # ========================================
                    # 3. CALCULATE DAILY INTEREST FOR COMPLETED CONTRIBUTIONS
                    # ========================================
                    if verbose:
                        self.stdout.write("   🔄 Calculating daily interest...")
                    
                    # Get all completed contributions in active rounds
                    completed_contributions = Contribution.objects.filter(
                        status='completed',
                        membership__round__status='active',
                        payment_date__isnull=False
                    ).select_related('membership__round')
                    
                    interest_updated = 0
                    for contribution in completed_contributions:
                        # Calculate days in escrow up to current date
                        days_held = (current_date - contribution.payment_date.date()).days
                        
                        if days_held >= 0:
                            round_obj = contribution.membership.round
                            daily_rate = round_obj.interest_rate / Decimal('365.00') / Decimal('100.00')
                            total_interest = contribution.amount * daily_rate * Decimal(str(days_held))
                            
                            contribution.days_in_escrow = days_held
                            contribution.interest_accrued = total_interest
                            contribution.save()
                            
                            interest_updated += 1
                    
                    # Update membership interest totals
                    if interest_updated > 0:
                        active_memberships = RoundMembership.objects.filter(
                            round__status='active'
                        )
                        for membership in active_memberships:
                            membership.interest_earned = Contribution.objects.filter(
                                membership=membership,
                                status='completed'
                            ).aggregate(total=Sum('interest_accrued'))['total'] or Decimal('0.00')
                            membership.save()
                        
                        # Update round total interest
                        active_rounds = Round.objects.filter(status='active')
                        for round_obj in active_rounds:
                            round_obj.total_interest_earned = RoundMembership.objects.filter(
                                round=round_obj
                            ).aggregate(total=Sum('interest_earned'))['total'] or Decimal('0.00')
                            round_obj.save()
                    
                    # ========================================
                    # 4. CHECK IF ROUNDS SHOULD BE MARKED COMPLETE
                    # ========================================
                    if verbose:
                        self.stdout.write("   🔄 Checking for rounds to complete...")
                    
                    active_rounds = Round.objects.filter(status='active')
                    rounds_to_complete = []
                    
                    for round_obj in active_rounds:
                        should_complete = False
                        
                        # Check 1: End date reached or passed
                        if round_obj.end_date and round_obj.end_date <= current_date:
                            should_complete = True
                        
                        # Check 2: All contributions completed
                        total_expected_contributions = Contribution.objects.filter(
                            membership__round=round_obj
                        ).count()
                        
                        completed_contributions_count = Contribution.objects.filter(
                            membership__round=round_obj,
                            status='completed'
                        ).count()
                        
                        if total_expected_contributions > 0 and completed_contributions_count >= total_expected_contributions:
                            should_complete = True
                        
                        if should_complete:
                            rounds_to_complete.append(round_obj)
                    
                    # Mark rounds as completed (but don't process payouts yet)
                    for round_obj in rounds_to_complete:
                        round_obj.status = 'completed'
                        if not round_obj.end_date:
                            round_obj.end_date = current_date
                        round_obj.save()
                        
                        if verbose:
                            self.stdout.write(f"      ✅ Marked complete: {round_obj.name}")
                    
                    # ========================================
                    # 5. PROCESS PAYOUTS FOR COMPLETED ROUNDS (AFTER INTEREST ACCRUAL)
                    # ========================================
                    if verbose:
                        self.stdout.write("   🔄 Processing payouts for completed rounds...")
                    
                    # Get rounds completed at least 1 day ago (to allow final interest accrual)
                    yesterday = current_date - timedelta(days=1)
                    completed_rounds = Round.objects.filter(
                        status='completed',
                        end_date__lte=yesterday
                    )
                    
                    payout_count = 0
                    for round_obj in completed_rounds:
                        # Check if payouts already processed
                        if Payout.objects.filter(round=round_obj, status='completed').exists():
                            continue
                        
                        # Get all scheduled payouts
                        scheduled_payouts = Payout.objects.filter(
                            round=round_obj,
                            status='scheduled'
                        ).select_related('recipient_membership__user')
                        
                        for payout in scheduled_payouts:
                            try:
                                membership = payout.recipient_membership
                                actual_contributed = membership.total_contributed
                                
                                if actual_contributed == 0:
                                    payout.status = 'failed'
                                    payout.notes = 'No contributions made'
                                    payout.save()
                                    continue
                                
                                # Recalculate interest based on ACTUAL contributions
                                completed_contributions = Contribution.objects.filter(
                                    membership=membership,
                                    status='completed'
                                ).order_by('payment_date')
                                
                                total_interest = Decimal('0.00')
                                for contrib in completed_contributions:
                                    if contrib.payment_date:
                                        # Use the already calculated interest
                                        total_interest += contrib.interest_accrued
                                
                                # Apply tax
                                from constance import config
                                tax_rate = Decimal(str(config.MGR_TAX_RATE)) / Decimal('100.00')
                                tax_amount = total_interest * tax_rate
                                net_interest = total_interest - tax_amount
                                
                                # Update payout
                                payout.principal_amount = actual_contributed
                                payout.interest_amount = net_interest
                                payout.amount = actual_contributed + net_interest
                                payout.notes = (
                                    f'Recalculated based on actual contributions. '
                                    f'Gross interest: KES {total_interest:.2f}, '
                                    f'Tax: KES {tax_amount:.2f} ({config.MGR_TAX_RATE}%), '
                                    f'Net interest: KES {net_interest:.2f}'
                                )
                                payout.status = 'completed'
                                payout.payout_date = current_datetime
                                payout.save()
                                
                                # Credit wallet
                                wallet = WalletService.get_or_create_wallet(membership.user)
                                wallet.balance += payout.amount
                                wallet.available_balance += payout.amount
                                wallet.save()
                                
                                # Create transaction
                                MGRTransaction.objects.create(
                                    wallet=wallet,
                                    transaction_type='payout',
                                    amount=payout.amount,
                                    balance_before=wallet.balance - payout.amount,
                                    balance_after=wallet.balance,
                                    status='completed',
                                    related_round=payout.round,
                                    related_payout=payout,
                                    description=f'Payout from {payout.round.name}'
                                )
                                
                                # Update membership
                                membership.has_received_payout = True
                                membership.payout_received_date = current_date
                                membership.payout_amount = payout.amount
                                membership.interest_earned = net_interest
                                membership.save()
                                
                                payout_count += 1
                                if verbose:
                                    self.stdout.write(
                                        f"      ✅ Payout: {membership.user.username}, "
                                        f"Principal: KES {actual_contributed}, "
                                        f"Interest: KES {net_interest}, "
                                        f"Total: KES {payout.amount}"
                                    )
                                    
                            except Exception as e:
                                if verbose:
                                    self.stdout.write(f"      ❌ Payout failed: {str(e)}")
                                logger.exception("Payout processing error")
                        
                        # CRITICAL: Always freeze statistics after processing payouts
                        # Even if some payouts failed, we need to record what happened
                        try:
                            self.freeze_round_statistics(round_obj, current_date, verbose)
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"      ❌ Failed to freeze stats: {e}"))
                        
                        # Update memberships
                        memberships = RoundMembership.objects.filter(round=round_obj, status='active')
                        for membership in memberships:
                            membership.status = 'completed'
                            
                            # Unlock remaining funds
                            if membership.locked_amount > 0:
                                WalletService.unlock_all_funds_for_round(membership.user, round_obj)
                                membership.locked_amount = Decimal('0.00')
                            
                            membership.save()
                            
                            # Update profile
                            profile = membership.user.mgr_profile
                            profile.completed_rounds += 1
                            profile.update_trust_score()
                    
                    # ========================================
                    # 6. UPDATE TRUST SCORES
                    # ========================================
                    if step % 7 == 0:  # Weekly
                        if verbose:
                            self.stdout.write("   🔄 Updating trust scores...")
                        
                        profiles = UserProfile.objects.all()
                        for profile in profiles:
                            profile.update_trust_score()
                    
                    # ========================================
                    # SUMMARY FOR THIS DAY
                    # ========================================
                    if verbose or processed_count > 0 or payout_count > 0:
                        self.stdout.write(self.style.SUCCESS(
                            f"   📊 Day {current_date} summary:\n"
                            f"      • Contributions: {processed_count} processed, {failed_count} failed\n"
                            f"      • Missed contributions: {missed_count}\n"
                            f"      • Interest updated: {interest_updated}\n"
                            f"      • Payouts: {payout_count}\n"
                            f"      • Rounds marked complete: {len(rounds_to_complete)}"
                        ))
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  ❌ Error on {current_date}: {e}")
                    )
                    logger.exception("Simulation error")

                # Advance time
                current_datetime += timedelta(days=step_days)
                frozen.move_to(current_datetime)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎉 Time simulation completed!\n"
                f"All rounds within {days} days should now be finalized.\n"
            )
        )
        
        # Show final statistics
        self.show_final_statistics()

    def freeze_round_statistics(self, round_obj, completion_date, verbose=False):
        """
        CRITICAL: Freeze round statistics at completion time
        This creates the RoundCompletionStats record
        """
        from merry_go_round.models import RoundCompletionStats, Payout
        from constance import config
        
        if verbose:
            self.stdout.write(f"      🔒 Freezing statistics for {round_obj.name}...")
        
        # Check if already exists
        if hasattr(round_obj, 'completion_snapshot'):
            if verbose:
                self.stdout.write(f"      ℹ️  Stats already frozen")
            return
        
        # Calculate FINAL round-level statistics
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
        
        # Reverse-calculate gross interest and tax
        tax_rate_percent = config.MGR_TAX_RATE
        tax_rate_decimal = Decimal(str(tax_rate_percent)) / 100
        
        if total_net_interest > 0:
            total_gross_interest = total_net_interest / (1 - tax_rate_decimal)
            total_tax = total_gross_interest - total_net_interest
        else:
            total_gross_interest = Decimal('0.00')
            total_tax = Decimal('0.00')
        
        completion_pct = (total_principal / total_expected * 100) if total_expected > 0 else 0
        
        # Create frozen stats record
        stats, created = RoundCompletionStats.objects.get_or_create(
            round=round_obj,
            defaults={
                'total_expected_contributions': total_expected,
                'total_actual_contributions': total_principal,
                'completion_percentage': completion_pct,
                'total_gross_interest': total_gross_interest,
                'total_tax_deducted': total_tax,
                'total_net_interest': total_net_interest,
                'total_paid_out': total_paid_out,
                'interest_rate_used': round_obj.interest_rate,
                'tax_rate_used': tax_rate_percent,
            }
        )
        
        if verbose:
            action = "Created" if created else "Updated"
            self.stdout.write(
                f"      🔒 {action} frozen stats: "
                f"Expected={total_expected:.2f}, "
                f"Actual={total_principal:.2f}, "
                f"Net Interest={total_net_interest:.2f}"
            )

    def fix_existing_completed_rounds(self):
        """
        Fix completed rounds that don't have RoundCompletionStats
        """
        from merry_go_round.models import Round, RoundCompletionStats
        
        self.stdout.write(self.style.WARNING("\n🔧 Checking for completed rounds without stats..."))
        
        completed_rounds = Round.objects.filter(status='completed')
        fixed_count = 0
        
        for round_obj in completed_rounds:
            # Check if stats exist
            if not hasattr(round_obj, 'completion_snapshot'):
                try:
                    self.freeze_round_statistics(round_obj, round_obj.end_date, verbose=True)
                    fixed_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"   ❌ Failed to create stats for {round_obj.name}: {e}")
                    )
        
        if fixed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Created stats for {fixed_count} completed rounds\n")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("✅ All completed rounds have stats\n")
            )

    def show_final_statistics(self):
        """Show comprehensive final statistics"""
        from merry_go_round.models import Round, Contribution, Payout, RoundCompletionStats
        from django.contrib.auth.models import User
        
        self.stdout.write("\n📊 FINAL STATISTICS:")
        self.stdout.write("="*60)
        
        # Round stats
        self.stdout.write("\n📄 ROUNDS:")
        self.stdout.write(f"   Active rounds: {Round.objects.filter(status='active').count()}")
        self.stdout.write(f"   Completed rounds: {Round.objects.filter(status='completed').count()}")
        self.stdout.write(f"   Rounds with frozen stats: {RoundCompletionStats.objects.count()}")
        
        # Contribution stats
        self.stdout.write("\n💰 CONTRIBUTIONS:")
        total_contributions = Contribution.objects.count()
        completed = Contribution.objects.filter(status='completed').count()
        missed = Contribution.objects.filter(status='missed').count()
        pending = Contribution.objects.filter(status='pending').count()
        self.stdout.write(f"   Total: {total_contributions}")
        self.stdout.write(f"   Completed: {completed} ({completed/total_contributions*100:.1f}%)")
        self.stdout.write(f"   Missed: {missed} ({missed/total_contributions*100:.1f}%)")
        self.stdout.write(f"   Pending: {pending}")
        
        # Payout stats
        self.stdout.write("\n💸 PAYOUTS:")
        completed_payouts = Payout.objects.filter(status='completed')
        if completed_payouts.exists():
            total_payout = completed_payouts.aggregate(total=Sum('amount'))['total'] or 0
            total_interest = completed_payouts.aggregate(total=Sum('interest_amount'))['total'] or 0
            total_principal = completed_payouts.aggregate(total=Sum('principal_amount'))['total'] or 0
            
            self.stdout.write(f"   Total payouts: {completed_payouts.count()}")
            self.stdout.write(f"   Total paid out: KES {total_payout:,.2f}")
            self.stdout.write(f"   Principal: KES {total_principal:,.2f}")
            self.stdout.write(f"   Interest: KES {total_interest:,.2f}")
            
            # Show top recipients
            top_recipients = User.objects.filter(
                round_memberships__received_payouts__status='completed'
            ).annotate(
                total_received=Sum('round_memberships__received_payouts__amount')
            ).order_by('-total_received')[:5]
            
            if top_recipients.exists():
                self.stdout.write("\n🏆 TOP RECIPIENTS:")
                for i, user in enumerate(top_recipients, 1):
                    if user.total_received:
                        self.stdout.write(f"   {i}. {user.username}: KES {user.total_received:,.2f}")
        
        self.stdout.write("\n" + "="*60)