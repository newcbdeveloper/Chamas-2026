from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from datetime import timedelta, date
from decimal import Decimal
import random
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
import string
import hashlib
from django.contrib import messages
from .models import (
    Round, RoundMembership, Contribution, Payout,
    Invitation, UserProfile, Notification, RoundMessage
)
from .wallet_services import WalletService


import logging
logger = logging.getLogger(__name__)


class RoundService:
    """Service for managing round operations"""
    
    @staticmethod
    @transaction.atomic
    def create_round(user, form_data):
        """Create a new savings round"""
        from constance import config

        round_obj = Round.objects.create(
            name=form_data['name'],
            description=form_data.get('description', ''),
            round_type=form_data['round_type'],
            payout_model=form_data['payout_model'],
            contribution_amount=form_data['contribution_amount'],
            frequency=form_data['frequency'],
            max_members=form_data['max_members'],
            min_trust_score=form_data.get('min_trust_score', 30),
            interest_rate=form_data.get('interest_rate', config.MGR_DEFAULT_INTEREST_RATE),
            creator=user,
            status='open' if form_data['round_type'] == 'public' else 'draft'
        )
        
        # Creator automatically joins their own round
        RoundService.add_member_to_round(round_obj, user)
        
        # Create system message
        RoundMessage.objects.create(
            round=round_obj,
            sender=user,
            message_type='system',
            subject='Round Created',
            content=f'Welcome to {round_obj.name}! This round has been created and is now accepting members.'
        )
        
        return round_obj
    
    @staticmethod
    @transaction.atomic
    def add_member_to_round(round_obj, user, payout_position=None):
        """Add a user as a member to a round"""
        # Get or create user profile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        
        # Check if already a member
        if RoundMembership.objects.filter(round=round_obj, user=user).exists():
            raise ValueError("User is already a member of this round")
        
        # Check if round is full
        if round_obj.is_full():
            raise ValueError("This round is full")
        
        # Check trust score
        if profile.trust_score < round_obj.min_trust_score:
            raise ValueError(f"Trust score too low. Required: {round_obj.min_trust_score}, Current: {profile.trust_score}")
        
        # CHANGED: Only reserve the FIRST contribution amount (just-in-time approach)
        try:
            WalletService.reserve_next_contribution(user, round_obj, round_obj.contribution_amount)
        except ValueError as e:
            raise ValueError(f"Insufficient wallet balance for first contribution: {str(e)}")
        
        # Assign payout position for rotational rounds
        if round_obj.payout_model == 'rotational' and payout_position is None:
            # Auto-assign next available position
            existing_positions = RoundMembership.objects.filter(
                round=round_obj
            ).values_list('payout_position', flat=True)
            
            for pos in range(1, round_obj.max_members + 1):
                if pos not in existing_positions:
                    payout_position = pos
                    break
        
        # Create membership with only first contribution locked
        membership = RoundMembership.objects.create(
            round=round_obj,
            user=user,
            payout_position=payout_position,
            trust_score_at_join=profile.trust_score,
            status='active',
            expected_contributions=round_obj.get_total_commitment_amount(),
            locked_amount=round_obj.contribution_amount  # CHANGED: Only first contribution
        )
        
        # Update round member count
        round_obj.current_members = F('current_members') + 1
        round_obj.save()
        round_obj.refresh_from_db()
        
        # Check if round should auto-start when full
        if round_obj.status in ['draft', 'open'] and round_obj.current_members == round_obj.max_members:
            # Round is now full - auto-start it
            RoundService.start_round(round_obj)
        elif round_obj.status == 'draft' and round_obj.current_members >= 2:
            # For private rounds, change from draft to open when we have 2+ members
            if round_obj.round_type == 'private':
                round_obj.status = 'open'
                round_obj.save()
        
        # Create notification for new member
        NotificationService.create_notification(
            user=user,
            round=round_obj,
            notification_type='funds_locked',
            title=f'Joined {round_obj.name}',
            message=f'You have successfully joined {round_obj.name}. KES {round_obj.contribution_amount} has been reserved for your first contribution.'
        )
        
        return membership
    
    @staticmethod
    @transaction.atomic
    def start_round(round_obj):
        """
        Start a round and generate contribution schedule
        
        CORRECTED: End date is ONE PERIOD after last contribution
        - If last contribution is on day X, end date is on day X + cycle_days
        - This ensures ALL contributions earn interest
        """
        if round_obj.status not in ['draft', 'open']:
            raise ValueError("Round cannot be started from current status")
        
        if not round_obj.can_start():
            raise ValueError("Round needs at least 2 members to start")
        
        # Set start date
        round_obj.start_date = timezone.now().date() + timedelta(days=1)  # Start tomorrow
        round_obj.status = 'active'
        round_obj.next_contribution_date = round_obj.start_date
        
        # Calculate end date
        total_cycles = round_obj.calculate_total_cycles()
        cycle_days = round_obj.get_cycle_duration_days()
        
        # CORRECTED FORMULA:
        # If we have N cycles, contributions happen at:
        # Day 0 (start), Day cycle_days, Day 2*cycle_days, ..., Day (N-1)*cycle_days
        # 
        # The last contribution is at day (N-1)*cycle_days
        # End date should be ONE PERIOD LATER: (N-1)*cycle_days + cycle_days = N*cycle_days
        #
        # So: end_date = start_date + (total_cycles * cycle_days)
        
        round_obj.end_date = round_obj.start_date + timedelta(days=total_cycles * cycle_days)
        
        round_obj.save()
        
        logger.info(
            f"Round '{round_obj.name}' starting: "
            f"Start: {round_obj.start_date}, "
            f"End: {round_obj.end_date}, "
            f"Total cycles: {total_cycles}, "
            f"Cycle days: {cycle_days}, "
            f"Duration: {total_cycles * cycle_days} days"
        )
        
        # Generate contribution schedule for all members
        memberships = RoundMembership.objects.filter(round=round_obj)
        for membership in memberships:
            ContributionService.generate_contribution_schedule(membership)
        
        # Generate payout schedule
        PayoutService.generate_payout_schedule(round_obj)
        
        # Notify all members
        for membership in memberships:
            NotificationService.create_notification(
                user=membership.user,
                round=round_obj,
                notification_type='round_started',
                title=f'{round_obj.name} Has Started!',
                message=f'The round has started. First contribution is due on {round_obj.start_date}. Final contribution on {round_obj.start_date + timedelta(days=(total_cycles - 1) * cycle_days)}. Round ends {round_obj.end_date}.'
            )
        
        # Create system message
        RoundMessage.objects.create(
            round=round_obj,
            sender=round_obj.creator,
            message_type='system',
            subject='Round Started',
            content=f'This round has officially started! First contributions are due on {round_obj.start_date}. The round runs for {total_cycles} cycles and ends on {round_obj.end_date}.',
            is_pinned=True
        )
        
        return round_obj
    
    @staticmethod
    def get_available_payout_positions(round_obj):
        """Get list of available payout positions for rotational rounds"""
        if round_obj.payout_model != 'rotational':
            return []
        
        taken_positions = set(RoundMembership.objects.filter(
            round=round_obj
        ).values_list('payout_position', flat=True))
        
        return [pos for pos in range(1, round_obj.max_members + 1) if pos not in taken_positions]
    
    @staticmethod
    @transaction.atomic
    def complete_round(round_obj):
        """
        Complete a round and FREEZE all statistics
        """
        round_obj.status = 'completed'
        round_obj.end_date = timezone.now().date()
        round_obj.save()
        
        # Calculate FINAL round-level statistics
        total_cycles = round_obj.calculate_total_cycles()
        total_expected = round_obj.contribution_amount * round_obj.max_members * total_cycles
        
        # Get actual totals from all payouts (what was REALLY paid)
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
        
        # Reverse-calculate gross interest and tax from net interest
        from constance import config
        tax_rate_percent = config.MGR_TAX_RATE
        tax_rate_decimal = Decimal(str(tax_rate_percent)) / 100
        
        if total_net_interest > 0:
            total_gross_interest = total_net_interest / (1 - tax_rate_decimal)
            total_tax = total_gross_interest - total_net_interest
        else:
            total_gross_interest = Decimal('0.00')
            total_tax = Decimal('0.00')
        
        completion_pct = (total_principal / total_expected * 100) if total_expected > 0 else 0
        
        # FREEZE these statistics forever
        from .models import RoundCompletionStats
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
        
        # Update memberships and unlock funds
        memberships = RoundMembership.objects.filter(round=round_obj, status='active')
        for membership in memberships:
            membership.status = 'completed'
            
            if membership.locked_amount > 0:
                WalletService.unlock_all_funds_for_round(membership.user, round_obj)
                membership.locked_amount = 0
            
            membership.save()
            
            profile = membership.user.mgr_profile
            profile.completed_rounds += 1
            profile.update_trust_score()
        
        logger.info(
            f"✅ Round '{round_obj.name}' completed and stats frozen: "
            f"Expected: {total_expected}, Actual: {total_principal}, "
            f"Net Interest: {total_net_interest}, Tax: {total_tax}"
        )
            
    
    @staticmethod
    @transaction.atomic
    def cancel_round(round_obj):
        """Cancel a round and unlock all funds"""
        round_obj.status = 'cancelled'
        round_obj.save()
        
        # Unlock funds for all members using the new method
        memberships = RoundMembership.objects.filter(round=round_obj)
        for membership in memberships:
            if membership.locked_amount > 0:
                WalletService.unlock_all_funds_for_round(membership.user, round_obj)
            
            membership.status = 'removed'
            membership.locked_amount = 0  # Reset locked amount
            membership.save()


class ContributionService:
    """Service for managing contributions"""
    
    @staticmethod
    @transaction.atomic
    def generate_contribution_schedule(membership):
        """Generate all contributions for a membership"""
        round_obj = membership.round
        total_cycles = round_obj.calculate_total_cycles()
        cycle_days = round_obj.get_cycle_duration_days()
        
        current_date = round_obj.start_date
        
        for cycle in range(1, total_cycles + 1):
            Contribution.objects.create(
                membership=membership,
                amount=round_obj.contribution_amount,
                cycle_number=cycle,
                due_date=current_date,
                status='pending'
            )
            
            current_date = current_date + timedelta(days=cycle_days)
    
    @staticmethod
    @transaction.atomic
    def process_contribution(contribution):
        """
        Process a contribution payment from wallet
        
        FIXED: Removed duplicate notification - let tasks.py handle it
        """
        if contribution.status == 'completed':
            raise ValueError("Contribution already processed")
        
        try:
            # Process payment from wallet
            txn = WalletService.process_contribution(contribution)
            
            # Update user profile
            profile = contribution.membership.user.mgr_profile
            profile.total_contributions += contribution.amount
            profile.save()
            
            # Reserve funds for the NEXT contribution
            next_contribution = Contribution.objects.filter(
                membership=contribution.membership,
                status='pending'
            ).order_by('due_date').first()
            
            if next_contribution:
                try:
                    # Reserve the next contribution amount
                    WalletService.reserve_next_contribution(
                        contribution.membership.user,
                        contribution.membership.round,
                        next_contribution.amount
                    )
                    
                    # Update membership locked amount
                    membership = contribution.membership
                    membership.locked_amount += next_contribution.amount
                    membership.save()
                    
                    logger.info(
                        f"Auto-reserved KES {next_contribution.amount} for next contribution "
                        f"(Cycle {next_contribution.cycle_number}) for user {contribution.membership.user.username}"
                    )
                    
                except ValueError as e:
                    # If reservation fails, send notification but don't fail the current contribution
                    logger.warning(
                        f"Failed to reserve next contribution for {contribution.membership.user.username}: {str(e)}"
                    )
                    # REMOVED: Duplicate notification here
                    # This will be handled by the task that calls this function
            
            # REMOVED: Success notification here
            # Let the calling function (task or view) handle notification
            # This prevents duplicate notifications
            
            # Start calculating interest
            ContributionService.start_interest_accrual(contribution)
            
            return contribution
            
        except ValueError as e:
            contribution.status = 'failed'
            contribution.save()
            raise ValueError(f"Payment failed: {str(e)}")
    
    @staticmethod
    def start_interest_accrual(contribution):
        """
        CORRECTED: Start tracking interest accrual for a contribution
        
        Uses actual date calculation: days = end_date - payment_date
        """
        round_obj = contribution.membership.round
        
        if round_obj.payout_model == 'marathon':
            # Interest accrues until end of round
            if round_obj.end_date:
                days_to_payout = (round_obj.end_date - contribution.payment_date.date()).days
            else:
                # Fallback: calculate expected end date
                total_cycles = round_obj.calculate_total_cycles()
                cycle_days = round_obj.get_cycle_duration_days()
                expected_end = round_obj.start_date + timedelta(days=total_cycles * cycle_days)
                days_to_payout = (expected_end - contribution.payment_date.date()).days
        else:
            # Rotational: Interest accrues until member's payout turn
            payout = Payout.objects.filter(
                round=round_obj,
                recipient_membership=contribution.membership
            ).first()
            
            if payout:
                days_to_payout = (payout.scheduled_date - contribution.payment_date.date()).days
            else:
                days_to_payout = 0
        
        contribution.days_in_escrow = max(0, days_to_payout)
        contribution.calculate_interest()
        
        logger.debug(
            f"Interest accrual started: "
            f"Contribution cycle {contribution.cycle_number}, "
            f"Payment: {contribution.payment_date.date()}, "
            f"Days in escrow: {contribution.days_in_escrow}"
        )
    
    @staticmethod
    @transaction.atomic
    def auto_process_due_contributions():
        """Auto-process contributions that are due (run daily)"""
        today = timezone.now().date()
        due_contributions = Contribution.objects.filter(
            status='pending',
            due_date=today
        ).select_related('membership__user')
        
        for contribution in due_contributions:
            try:
                ContributionService.process_contribution(contribution)
            except ValueError as e:
                # Mark as failed and notify user
                contribution.status = 'failed'
                contribution.save()
                
                NotificationService.create_notification(
                    user=contribution.membership.user,
                    round=contribution.membership.round,
                    notification_type='insufficient_balance',
                    title='Contribution Failed',
                    message=f'Your contribution of KES {contribution.amount} failed: {str(e)}'
                )
    
    @staticmethod
    @transaction.atomic
    def mark_missed_contributions():
        """Mark overdue contributions as missed (run daily)"""
        today = timezone.now().date()
        overdue = Contribution.objects.filter(
            status__in=['pending', 'failed'],
            due_date__lt=today
        )
        
        for contribution in overdue:
            contribution.mark_as_missed()
            
            # Notify user
            NotificationService.create_notification(
                user=contribution.membership.user,
                round=contribution.membership.round,
                notification_type='contribution_reminder',
                title='Missed Contribution',
                message=f'You missed the contribution for cycle {contribution.cycle_number}. Please ensure sufficient wallet balance.'
            )
    
    @staticmethod
    def send_contribution_reminders():
        """Send reminders for upcoming contributions (run daily)"""
        tomorrow = timezone.now().date() + timedelta(days=1)
        upcoming = Contribution.objects.filter(
            status='pending',
            due_date=tomorrow
        ).select_related('membership__user', 'membership__round')
        
        for contribution in upcoming:
            NotificationService.create_notification(
                user=contribution.membership.user,
                round=contribution.membership.round,
                notification_type='contribution_reminder',
                title='Contribution Due Tomorrow',
                message=f'Your contribution of KES {contribution.amount} will be auto-processed tomorrow. Ensure sufficient wallet balance.'
            )



class PayoutService:
    """Service for managing payouts - WITH TAX DEDUCTION ON INTEREST"""
    
    @staticmethod
    def calculate_tax_on_interest(interest_amount):
        """
        Calculate withholding tax on interest earned
        
        Args:
            interest_amount: Decimal amount of interest earned
            
        Returns:
            Decimal tax amount
        """
        from constance import config
        tax_rate = config.MGR_TAX_RATE / 100  # Convert percentage to decimal
        tax_amount = interest_amount * Decimal(str(tax_rate))
        return round(tax_amount, 2)
    
    @staticmethod
    @transaction.atomic
    def generate_payout_schedule(round_obj):
        """Generate payout schedule for a round"""
        if round_obj.payout_model == 'marathon':
            PayoutService._generate_marathon_payouts(round_obj)
        else:
            PayoutService._generate_rotational_payouts(round_obj)
    
    @staticmethod
    def _generate_marathon_payouts(round_obj):
        """
        Generate payouts for marathon model (all at end)
        UPDATED: Creates SCHEDULED payouts - actual amounts calculated at completion
        """
        memberships = RoundMembership.objects.filter(round=round_obj)
        
        # For marathon, we create PLACEHOLDER payouts
        # Actual amounts will be calculated when round completes
        total_cycles = round_obj.calculate_total_cycles()
        expected_contribution_per_member = round_obj.contribution_amount * total_cycles
        
        for membership in memberships:
            # Calculate EXPECTED payout (for display purposes only)
            expected_interest = round_obj.get_accurate_projected_interest(expected_contribution_per_member)
            tax_amount = PayoutService.calculate_tax_on_interest(expected_interest)
            expected_net_interest = expected_interest - tax_amount
            expected_total = expected_contribution_per_member + expected_net_interest
            
            Payout.objects.create(
                round=round_obj,
                recipient_membership=membership,
                payout_cycle=total_cycles,
                amount=expected_total,  # This is EXPECTED - will be recalculated
                principal_amount=expected_contribution_per_member,
                interest_amount=expected_net_interest,
                scheduled_date=round_obj.end_date,
                status='scheduled',
                notes=f'Expected payout (will be adjusted based on actual contributions). Expected tax: KES {tax_amount} ({round_obj.get_tax_rate()}%)'
            )
            
            logger.info(
                f"Marathon payout SCHEDULED for {membership.user.username}: "
                f"Expected Principal: KES {expected_contribution_per_member}, "
                f"Expected Interest (after tax): KES {expected_net_interest}"
            )
    
    @staticmethod
    def _generate_rotational_payouts(round_obj):
        """
        Generate payouts for rotational model (turn-based)
        UPDATED: Deduct tax from interest
        """
        memberships = RoundMembership.objects.filter(round=round_obj).order_by('payout_position')
        
        cycle_days = round_obj.get_cycle_duration_days()
        payout_date = round_obj.start_date
        total_per_cycle = round_obj.contribution_amount * round_obj.max_members
        
        for cycle, membership in enumerate(memberships, start=1):
            # Calculate gross interest (before tax)
            days_to_payout = (payout_date - round_obj.start_date).days
            daily_rate = round_obj.interest_rate / 365 / 100
            gross_interest = total_per_cycle * Decimal(str(daily_rate)) * Decimal(str(days_to_payout))
            
            # Calculate tax on interest
            tax_amount = PayoutService.calculate_tax_on_interest(gross_interest)
            
            # Net interest after tax
            net_interest = gross_interest - tax_amount
            
            # Total payout = Principal + Net Interest (after tax)
            total_payout = total_per_cycle + net_interest
            
            Payout.objects.create(
                round=round_obj,
                recipient_membership=membership,
                payout_cycle=cycle,
                amount=total_payout,  # Principal + Net Interest
                principal_amount=total_per_cycle,
                interest_amount=net_interest,  # After tax
                scheduled_date=payout_date,
                status='scheduled',
                notes=f'Tax deducted: KES {tax_amount} ({round_obj.get_tax_rate()}%)'
            )
            
            logger.info(
                f"Rotational payout scheduled for {membership.user.username}: "
                f"Position {cycle}, Gross Interest: KES {gross_interest}, "
                f"Tax: KES {tax_amount}, Net Interest: KES {net_interest}"
            )
            
            payout_date = payout_date + timedelta(days=cycle_days)
    
    
    @staticmethod
    @transaction.atomic
    def recalculate_and_process_marathon_payout(payout):
        """
        FIXED: Recalculate marathon payout based on ACTUAL contributions
        and process it - now correctly calculates ALL contribution interest
        """
        membership = payout.recipient_membership
        round_obj = payout.round
        
        # Get ACTUAL total contributed by this member
        actual_contributed = membership.total_contributed
        
        if actual_contributed == 0:
            payout.status = 'failed'
            payout.notes = 'No contributions made - payout cancelled'
            payout.amount = Decimal('0.00')
            payout.principal_amount = Decimal('0.00')
            payout.interest_amount = Decimal('0.00')
            payout.save()
            logger.warning(f"No payout for {membership.user.username} - no contributions made")
            return None
        
        # Calculate interest based on ACTUAL contributions
        completed_contributions = Contribution.objects.filter(
            membership=membership,
            status='completed'
        ).order_by('payment_date')
        
        total_interest_earned = Decimal('0.00')
        
        # CRITICAL FIX: Ensure end_date is set correctly
        if not round_obj.end_date:
            round_obj.end_date = timezone.now().date()
            round_obj.save()
        
        for contribution in completed_contributions:
            if contribution.payment_date:
                # Calculate days this contribution was in escrow
                days_in_escrow = (round_obj.end_date - contribution.payment_date.date()).days
                days_in_escrow = max(0, days_in_escrow)
                
                # Calculate interest for this contribution
                daily_rate = round_obj.interest_rate / 365 / 100
                contribution_interest = (
                    contribution.amount * 
                    Decimal(str(daily_rate)) * 
                    Decimal(str(days_in_escrow))
                )
                
                # CRITICAL: Update the contribution record
                contribution.days_in_escrow = days_in_escrow
                contribution.interest_accrued = contribution_interest
                contribution.save()
                
                total_interest_earned += contribution_interest
                
                logger.info(
                    f"Contribution #{contribution.cycle_number}: "
                    f"Amount=KES {contribution.amount}, "
                    f"PaymentDate={contribution.payment_date.date()}, "
                    f"EndDate={round_obj.end_date}, "
                    f"DaysInEscrow={days_in_escrow}, "
                    f"Interest=KES {contribution_interest:.2f}"
                )
        
        # Apply tax to TOTAL interest
        tax_amount = PayoutService.calculate_tax_on_interest(total_interest_earned)
        net_interest = total_interest_earned - tax_amount
        
        # Calculate final payout
        final_payout = actual_contributed + net_interest
        
        # Update payout record
        payout.principal_amount = actual_contributed
        payout.interest_amount = net_interest
        payout.amount = final_payout
        payout.notes = (
            f'Recalculated based on actual contributions. '
            f'Gross interest: KES {total_interest_earned:.2f}, '
            f'Tax: KES {tax_amount:.2f} ({round_obj.get_tax_rate()}%), '
            f'Net interest: KES {net_interest:.2f}'
        )
        payout.save()
        
        logger.info(
            f"RECALCULATED Marathon payout for {membership.user.username}: "
            f"Principal: KES {actual_contributed}, "
            f"Gross Interest: KES {total_interest_earned:.2f}, "
            f"Tax: KES {tax_amount:.2f}, "
            f"Net Interest: KES {net_interest:.2f}, "
            f"TOTAL: KES {final_payout:.2f}"
        )
        
        # Now process the payout
        try:
            txn = WalletService.process_payout(payout)
            return payout
        except Exception as e:
            payout.status = 'failed'
            payout.notes = f'Processing failed: {str(e)}'
            payout.save()
            raise
        
    @staticmethod
    @transaction.atomic
    def process_payout(payout):
            """
        Process a scheduled payout
            
            For MARATHON rounds: Recalculates based on actual contributions first
            For ROTATIONAL rounds: Processes as-is (already based on cycle)
            
            FIXED: Removed notification - let calling task handle it
            """
            if payout.status != 'scheduled':
                raise ValueError("Payout is not in scheduled status")
            
            # NEW: For marathon rounds, recalculate based on actual contributions
            if payout.round.payout_model == 'marathon':
                return PayoutService.recalculate_and_process_marathon_payout(payout)
            
            # For rotational rounds, process normally
            try:
                txn = WalletService.process_payout(payout)
                return payout
                
            except Exception as e:
                payout.status = 'failed'
                payout.notes = f'Processing failed: {str(e)}'
                payout.save()
                raise    
        
    @staticmethod
    def process_due_payouts():
            """Process all payouts that are due today (run daily)"""
            today = timezone.now().date()
            due_payouts = Payout.objects.filter(
                status='scheduled',
                scheduled_date__lte=today
            ).select_related('recipient_membership__user', 'round')
            
            for payout in due_payouts:
                try:
                    PayoutService.process_payout(payout)
                except Exception as e:
                    # Already handled in process_payout
                    logger.error(f"Failed to process payout {payout.id}: {str(e)}")
                    pass

class InvitationService:
    """Enhanced service for managing invitations"""
    
    @staticmethod
    def generate_token():
        """Generate a unique invitation token"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    
    @staticmethod
    def generate_unique_round_link_token(round_obj):
        """
        Generate a unique shareable link token for the round
        This is different from individual invitation tokens
        """
        # Create a persistent token for the round's shareable link
        base_token = f"{round_obj.id}-{round_obj.name.lower().replace(' ', '-')}"
        return hashlib.md5(base_token.encode()).hexdigest()[:16]
    
    @staticmethod
    @transaction.atomic
    def lookup_member(lookup_type, lookup_value):
        """
        NEW: Lookup a member by National ID or Phone Number
        
        Returns:
            dict with user info if found, None otherwise
        """
        from authentication.models import Profile
        
        try:
            if lookup_type == 'national_id':
                profile = Profile.objects.select_related('owner', 'owner__mgr_profile').get(
                    NIC_No=lookup_value
                )
            elif lookup_type == 'phone':
                # Normalize phone format
                phone = lookup_value.strip().replace(' ', '').replace('-', '')
                if phone.startswith('0'):
                    phone = '+254' + phone[1:]
                
                profile = Profile.objects.select_related('owner', 'owner__mgr_profile').get(
                    phone=phone
                )
            else:
                return None
            
            # Get MGR profile for trust score
            try:
                mgr_profile = profile.owner.mgr_profile
                trust_score = mgr_profile.trust_score
                completed_rounds = mgr_profile.completed_rounds
            except UserProfile.DoesNotExist:
                trust_score = 50  # Default
                completed_rounds = 0
            
            # Get user's full name
            full_name = profile.owner.get_full_name() or profile.owner.username
            
            return {
                'user_id': profile.owner.id,
                'lookup_value': lookup_value,
                'name': full_name,
                'phone': profile.phone,
                'national_id': profile.NIC_No,
                'trust_score': trust_score,
                'completed_rounds': completed_rounds,
                'avatar': ''.join([n[0].upper() for n in full_name.split()[:2]])
            }
            
        except Profile.DoesNotExist:
            return None
    
    @staticmethod
    @transaction.atomic
    def create_invitation(round_obj, inviter, invitee_data, message='', request=None):
        """
        NEW: Create an invitation with enhanced tracking
        
        Args:
            round_obj: Round object
            inviter: User sending the invitation
            invitee_data: Dict with lookup_type, lookup_value, and optional user_id
            message: Personal message
            request: HTTP request for generating URLs
        
        Returns:
            Invitation object
        """
        if round_obj.round_type != 'private':
            raise ValueError("Can only send invitations to private rounds")
        
        if round_obj.is_full():
            raise ValueError("Round is full")
        
        # Generate token
        token = InvitationService.generate_token()
        expires_at = timezone.now() + timedelta(days=7)
        
        # Determine lookup type and set appropriate field
        lookup_type = invitee_data.get('lookup_type')
        lookup_value = invitee_data.get('lookup_value')
        
        invitation_fields = {
            'round': round_obj,
            'inviter': inviter,
            'token': token,
            'message': message,
            'expires_at': expires_at,
            'status': 'pending',
            'lookup_type': lookup_type,
        }
        
        # Set the appropriate contact field
        if lookup_type == 'national_id':
            invitation_fields['invitee_national_id'] = lookup_value
        elif lookup_type == 'phone':
            invitation_fields['invitee_phone'] = lookup_value
        elif lookup_type == 'email':
            invitation_fields['invitee_email'] = lookup_value
        
        # If we have the user object, set it
        if 'user_id' in invitee_data:
            try:
                invitation_fields['invitee_user'] = User.objects.get(id=invitee_data['user_id'])
            except User.DoesNotExist:
                pass
        
        # Create invitation
        invitation = Invitation.objects.create(**invitation_fields)
        
        # Generate action URL
        if request:
            invitation.action_url = request.build_absolute_uri(
                reverse('merry_go_round:review_invitation', kwargs={'token': token})
            )
            invitation.save()
        
        return invitation
    
    @staticmethod
    @transaction.atomic
    def send_invitation_notifications(invitation):
        """
        NEW: Send both in-app notification and SMS for invitation
        
        Returns:
            dict with success status for each notification type
        """
        result = {
            'notification_sent': False,
            'sms_sent': False,
            'errors': []
        }
        
        # Get recipient user
        recipient = invitation.invitee_user
        
        if not recipient:
            # Try to find user by contact info
            from authentication.models import Profile
            try:
                if invitation.invitee_national_id:
                    profile = Profile.objects.get(NIC_No=invitation.invitee_national_id)
                    recipient = profile.owner
                elif invitation.invitee_phone:
                    profile = Profile.objects.get(phone=invitation.invitee_phone)
                    recipient = profile.owner
            except Profile.DoesNotExist:
                result['errors'].append('Recipient not found in system')
                return result
        
        # 1. Send in-app notification
        try:
            inviter_name = invitation.inviter.get_full_name() or invitation.inviter.username
            
            NotificationService.create_notification(
                user=recipient,
                notification_type='invitation_received',
                title=f"🎉 New Invitation: {invitation.round.name}",
                message=(
                    f"{inviter_name} has invited you to join the savings round '{invitation.round.name}'.\n\n"
                    f"💰 Contribution: KES {invitation.round.contribution_amount:,.0f} {invitation.round.get_frequency_display()}\n"
                    f"👥 Members: {invitation.round.current_members}/{invitation.round.max_members}\n"
                    f"📊 Model: {invitation.round.get_payout_model_display()}\n\n"
                    f"Review and accept the invitation now!"
                ),
                round=invitation.round,
                action_url=invitation.action_url
            )
            
            invitation.notification_sent = True
            invitation.notification_sent_at = timezone.now()
            result['notification_sent'] = True
            
        except Exception as e:
            result['errors'].append(f'Notification failed: {str(e)}')
            logger.error(f"Failed to send in-app notification: {str(e)}")
        
        # 2. Send SMS
        try:
            from authentication.models import Profile
            from notifications.utils import send_sms
            
            # Get recipient phone
            try:
                profile = Profile.objects.get(owner=recipient)
                phone = profile.phone
                
                inviter_name = invitation.inviter.get_full_name() or invitation.inviter.username
                
                sms_message = (
                    f"ChamaSpace: {inviter_name} invited you to join '{invitation.round.name}'. "
                    f"Contribute KES {invitation.round.contribution_amount:,.0f} {invitation.round.get_frequency_display()}. "
                    f"Review invitation: {invitation.action_url}"
                )
                
                # Send SMS
                send_sms(phone, "Round Invitation", sms_message)
                
                invitation.sms_sent = True
                invitation.sms_sent_at = timezone.now()
                result['sms_sent'] = True
                
            except Profile.DoesNotExist:
                result['errors'].append('Recipient profile not found for SMS')
            except Exception as sms_error:
                result['errors'].append(f'SMS failed: {str(sms_error)}')
                logger.error(f"Failed to send SMS: {str(sms_error)}")
        
        except ImportError:
            result['errors'].append('SMS service not available')
        
        # Save invitation status
        invitation.save()
        
        return result
    
    @login_required
    def send_invitation(request, round_id):
        """
        ENHANCED: Complete invitation interface with lookup, batch sending, and shareable links
        """
        round_obj = get_object_or_404(Round, id=round_id)
        
        # Check permissions
        if round_obj.creator != request.user:
            messages.error(request, 'Only the round creator can send invitations.')
            return redirect('merry_go_round:round_detail', round_id=round_id)
        
        if round_obj.round_type != 'private':
            messages.error(request, 'Invitations are only for private rounds.')
            return redirect('merry_go_round:round_detail', round_id=round_id)
        
        members_needed = max(0, round_obj.max_members - round_obj.current_members)
        
        # Get shareable link
        invitation_link = InvitationService.get_round_shareable_link(round_obj, request)
        
        # Get pending invitations with reminder info
        pending_invitations = Invitation.objects.filter(
            round=round_obj,
            status='pending'
        ).order_by('-created_at')
        
        # Calculate days since invitation
        for invite in pending_invitations:
            days_ago = (timezone.now() - invite.created_at).days
            invite.days_ago = days_ago
            invite.needs_reminder = days_ago >= 1
        
        context = {
            'round': round_obj,
            'pending_invitations': pending_invitations,
            'members_needed': members_needed,
            'invitation_link': invitation_link,
        }
        
        return render(request, 'merry_go_round/send_invitation.html', context)
    
    @staticmethod
    @transaction.atomic
    def send_batch_invitations(round_obj, inviter, invitation_list, message='', request=None):
        """
        NEW: Send multiple invitations at once
        
        Args:
            round_obj: Round object
            inviter: User sending invitations
            invitation_list: List of dicts with invitation data
            message: Personal message
            request: HTTP request
        
        Returns:
            dict with counts of successful/failed invitations
        """
        results = {
            'successful': 0,
            'failed': 0,
            'invitations': [],
            'errors': []
        }
        
        for invitee_data in invitation_list:
            try:
                # Check if already invited or member
                lookup_type = invitee_data.get('lookup_type')
                lookup_value = invitee_data.get('lookup_value')
                
                # Check for existing invitation
                existing = None
                if lookup_type == 'national_id':
                    existing = Invitation.objects.filter(
                        round=round_obj,
                        invitee_national_id=lookup_value,
                        status='pending'
                    ).first()
                elif lookup_type == 'phone':
                    existing = Invitation.objects.filter(
                        round=round_obj,
                        invitee_phone=lookup_value,
                        status='pending'
                    ).first()
                
                if existing:
                    results['failed'] += 1
                    results['errors'].append(f"{lookup_value}: Already invited")
                    continue
                
                # Create invitation
                invitation = InvitationService.create_invitation(
                    round_obj=round_obj,
                    inviter=inviter,
                    invitee_data=invitee_data,
                    message=message,
                    request=request
                )
                
                # Send notifications
                notification_result = InvitationService.send_invitation_notifications(invitation)
                
                results['successful'] += 1
                results['invitations'].append({
                    'invitation_id': str(invitation.id),
                    'lookup_value': lookup_value,
                    'notifications': notification_result
                })
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{invitee_data.get('lookup_value')}: {str(e)}")
                logger.error(f"Failed to create invitation: {str(e)}")
        
        return results
    
    @staticmethod
    def get_round_shareable_link(round_obj, request):
        """
        NEW: Generate or retrieve the shareable link for a round
        """
        return request.build_absolute_uri(
            reverse('merry_go_round:join_via_link', kwargs={'round_id': round_obj.id})
        )  

    
    @staticmethod
    @transaction.atomic
    def accept_invitation(invitation, user):
        """
        Accept an invitation and join the round
        
        Args:
            invitation: Invitation object
            user: User accepting the invitation
            
        Returns:
            RoundMembership object
            
        Raises:
            ValueError: If invitation cannot be accepted
        """
        # Check if invitation is expired
        if invitation.is_expired():
            raise ValueError("This invitation has expired")
        
        # Check if invitation is pending
        if invitation.status != 'pending':
            raise ValueError("This invitation is not available")
        
        # Check if user already a member
        if RoundMembership.objects.filter(round=invitation.round, user=user).exists():
            raise ValueError("You are already a member of this round")
        
        # Check if round is full
        if invitation.round.is_full():
            raise ValueError("This round is full")
        
        # Mark invitation as accepted
        invitation.status = 'accepted'
        invitation.invitee_user = user
        invitation.accepted_at = timezone.now()
        invitation.save()
        
        # Add user to round
        try:
            membership = RoundService.add_member_to_round(invitation.round, user)
            
            # Notify inviter of acceptance
            NotificationService.create_notification(
                user=invitation.inviter,
                notification_type='member_joined',
                title=f'Invitation Accepted - {invitation.round.name}',
                message=(
                    f'{user.get_full_name() or user.username} has accepted your invitation '
                    f'to join {invitation.round.name}.'
                ),
                round=invitation.round,
                action_url=reverse('merry_go_round:round_detail', kwargs={'round_id': invitation.round.id})
            )
            
            logger.info(
                f"User {user.username} accepted invitation {invitation.id} "
                f"and joined round {invitation.round.name}"
            )
            
            return membership
            
        except ValueError as e:
            # If adding to round fails, revert invitation status
            invitation.status = 'pending'
            invitation.invitee_user = None
            invitation.accepted_at = None
            invitation.save()
            raise ValueError(f"Failed to join round: {str(e)}")
    
    @staticmethod
    @transaction.atomic
    def decline_invitation(invitation, user):
        """
        Decline an invitation
        
        Args:
            invitation: Invitation object
            user: User declining the invitation
            
        Returns:
            Boolean indicating success
        """
        if invitation.status != 'pending':
            raise ValueError("This invitation is not available")
        
        # Mark invitation as declined
        invitation.status = 'declined'
        invitation.invitee_user = user
        invitation.declined_at = timezone.now()
        invitation.save()
        
        # Notify inviter of decline
        NotificationService.create_notification(
            user=invitation.inviter,
            notification_type='member_defaulted',
            title=f'Invitation Declined - {invitation.round.name}',
            message=(
                f'{user.get_full_name() or user.username} has declined your invitation '
                f'to join {invitation.round.name}.'
            ),
            round=invitation.round,
            action_url=reverse('merry_go_round:send_invitation', kwargs={'round_id': invitation.round.id})
        )
        
        logger.info(
            f"User {user.username} declined invitation {invitation.id} "
            f"for round {invitation.round.name}"
        )
        
        return True
    
    
#  UPDATE the NotificationService class to send notifications to both main dashboard and MGR dashboard

#  ENHANCED NOTIFICATION SERVICE

class NotificationService:
    """
    FIXED: Enhanced service for managing notifications - sends to BOTH systems
    1. MGR app's Notification model (for MGR-specific views)
    2. Main dashboard's UserNotificationHistory (for unified dashboard)
    """
    
    @staticmethod
    @transaction.atomic
    def create_notification(user, notification_type, title, message, round=None, action_url=''):
        """
        Create a notification for a user in BOTH systems
        
        FIXED: Removed metadata field that doesn't exist in UserNotificationHistory
        """
        from notifications.models import UserNotificationHistory
        from .models import Notification
        
        # 1. Create MGR-specific notification (for MGR app views)
        mgr_notification = Notification.objects.create(
            user=user,
            round=round,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url=action_url
        )
        
        # 2. Create main dashboard notification (for unified dashboard)
        dashboard_notification = None
        try:
            # FIXED: UserNotificationHistory doesn't have metadata field
            # Store MGR info in the message body instead
            enhanced_message = message
            if action_url:
                enhanced_message += f"\n\n[View Details]({action_url})"
            
            dashboard_notification = UserNotificationHistory.objects.create(
                user=user,
                notification_title=title,
                notification_body=enhanced_message,
                purpose='mgr',  # This is the key for filtering MGR notifications
            )
            logger.info(f" Sent MGR notification to both systems for {user.username}: {title}")
        except Exception as e:
            logger.error(f"❌ Failed to send to dashboard: {str(e)}")
        
        # 3. Send SMS and push notifications (if enabled)
        try:
            from authentication.models import Profile
            from notifications.models import UserFcmTokens
            from notifications.utils import send_sms, send_notif
            
            # Get user profile for phone
            profile = Profile.objects.get(owner=user)
            
            # Send SMS (if enabled in settings)
            try:
                send_sms(profile.phone, title, message)
            except Exception as sms_error:
                logger.warning(f"SMS failed: {str(sms_error)}")
            
            # Send push notification (if user has FCM tokens)
            try:
                fcm_tokens = UserFcmTokens.objects.filter(user=user).order_by('-token')[:1]
                if fcm_tokens.exists():
                    send_notif(
                        fcm_token=fcm_tokens,
                        mobile_number=profile.phone,
                        send_message=True,
                        send_notif=True,
                        title=title,
                        message=message,
                        data={'action_url': action_url} if action_url else None,
                        multi_user=False,
                        user=user
                    )
            except Exception as push_error:
                logger.warning(f"Push notification failed: {str(push_error)}")
            
        except Profile.DoesNotExist:
            logger.warning(f"Profile not found for user {user.username} - skipping SMS/push")
        except Exception as e:
            logger.warning(f"Failed to send SMS/push for MGR notification: {str(e)}")
        
        return mgr_notification, dashboard_notification
    
    @staticmethod
    def create_contribution_reminder(user, round, contribution, days_until_due):
        """
        Send reminder about upcoming contribution
        
        Args:
            user: User object
            round: Round object
            contribution: Contribution object
            days_until_due: Number of days until due
        """
        if days_until_due == 1:
            title = f" Contribution Due Tomorrow - {round.name}"
            message = (
                f"Your contribution of KES {contribution.amount:,.2f} is due tomorrow "
                f"({contribution.due_date.strftime('%b %d')}). "
                f"Please ensure you have sufficient balance in your MGR wallet."
            )
        elif days_until_due == 3:
            title = f" Upcoming Contribution - {round.name}"
            message = (
                f"Reminder: Your contribution of KES {contribution.amount:,.2f} is due in {days_until_due} days "
                f"({contribution.due_date.strftime('%b %d')}). "
                f"Reserve funds now to avoid late payment."
            )
        else:
            title = f" Contribution Reminder - {round.name}"
            message = (
                f"Your contribution of KES {contribution.amount:,.2f} is due in {days_until_due} days "
                f"({contribution.due_date.strftime('%b %d')})."
            )
        
        action_url = reverse('merry_go_round:wallet_dashboard')
        
        return NotificationService.create_notification(
            user=user,
            notification_type='contribution_reminder',
            title=title,
            message=message,
            round=round,
            action_url=action_url
        )
    
    @staticmethod
    def create_insufficient_balance_alert(user, round, required_amount, current_balance):
        """
        Alert user about insufficient balance
        """
        shortfall = required_amount - current_balance
        
        title = f" Insufficient Balance - {round.name}"
        message = (
            f"Your MGR wallet balance (KES {current_balance:,.2f}) is insufficient "
            f"for your next contribution (KES {required_amount:,.2f}). "
            f"Please deposit KES {shortfall:,.2f} to avoid missing your payment."
        )
        
        action_url = reverse('merry_go_round:transfer_from_main_wallet')
        
        return NotificationService.create_notification(
            user=user,
            notification_type='insufficient_balance',
            title=title,
            message=message,
            round=round,
            action_url=action_url
        )
    
    @staticmethod
    def create_contribution_success(user, round, amount, cycle_number):
        """
        Notify user of successful contribution
        """
        title = f" Contribution Processed - {round.name}"
        message = (
            f"Your contribution of KES {amount:,.2f} for cycle {cycle_number} "
            f"has been successfully processed. Thank you for staying on track!"
        )
        
        action_url = reverse('merry_go_round:round_detail', kwargs={'round_id': round.id})
        
        return NotificationService.create_notification(
            user=user,
            notification_type='payment_received',
            title=title,
            message=message,
            round=round,
            action_url=action_url
        )
    
    @staticmethod
    def create_payout_notification(user, round, amount, payout_type='received', tax_info=None):
        """
        Notify user about payout with tax breakdown
        
        Args:
            user: User object
            round: Round object
            amount: Total payout amount (after tax)
            payout_type: 'received' or 'scheduled'
            tax_info: Dict with principal, net_interest, tax_deducted
        """
        if payout_type == 'received':
            title = f"💰 Payout Received - {round.name}"
            
            if tax_info:
                message = (
                    f"Congratulations! Your payout from {round.name} has been processed.\n\n"
                    f" Total Received: KES {amount:,.2f}\n"
                    f" Breakdown:\n"
                    f"  • Principal: KES {tax_info['principal']:,.2f}\n"
                    f"  • Interest (after tax): KES {tax_info['net_interest']:,.2f}\n"
                    f"  • {tax_info['tax_deducted']}\n\n"
                    f"The funds are now in your MGR wallet."
                )
            else:
                message = (
                    f"Congratulations! You have received your payout of KES {amount:,.2f} "
                    f"from {round.name}. The funds are now in your MGR wallet."
                )
        else:
            title = f" Payout Scheduled - {round.name}"
            message = (
                f"Your payout of KES {amount:,.2f} from {round.name} has been scheduled "
                f"and will be processed soon."
            )
        
        action_url = reverse('merry_go_round:wallet_dashboard')
        
        return NotificationService.create_notification(
            user=user,
            notification_type='payout_received' if payout_type == 'received' else 'payout_scheduled',
            title=title,
            message=message,
            round=round,
            action_url=action_url
        )
    
    @staticmethod
    def create_round_started_notification(user, round, first_due_date):
        """
        Notify when round starts
        """
        title = f"🎉 Round Started - {round.name}"
        message = (
            f"The round {round.name} has officially started! "
            f"Your first contribution of KES {round.contribution_amount:,.2f} "
            f"is due on {first_due_date.strftime('%B %d, %Y')}."
        )
        
        action_url = reverse('merry_go_round:round_detail', kwargs={'round_id': round.id})
        
        return NotificationService.create_notification(
            user=user,
            notification_type='round_started',
            title=title,
            message=message,
            round=round,
            action_url=action_url
        )
    #This is already handled in Tasks.py, no need to send two duplicate notification
    #@staticmethod
    #def create_round_completed_notification(user, round, total_earned):
        """
        Notify when round completes
        """
        title = f"🎊 Round Completed - {round.name}"
        message = (
            f"Congratulations! {round.name} has been completed successfully. "
            f"You earned a total of KES {total_earned:,.2f} (principal + interest). "
            f"Thank you for your participation!"
        )
        
        action_url = reverse('merry_go_round:round_detail', kwargs={'round_id': round.id})
        
        return NotificationService.create_notification(
            user=user,
            notification_type='round_completed',
            title=title,
            message=message,
            round=round,
            action_url=action_url
        )
    
    @staticmethod
    def create_missed_payment_notification(user, round, cycle_number):
        """
        Notify about missed payment
        """
        title = f"⚠️ Missed Contribution - {round.name}"
        message = (
            f"You missed your contribution for cycle {cycle_number} in {round.name}. "
            f"This will affect your trust score and you will earn zero interest on this payment. "
            f"Please ensure sufficient funds for your next contribution."
        )
        
        action_url = reverse('merry_go_round:wallet_dashboard')
        
        return NotificationService.create_notification(
            user=user,
            notification_type='contribution_reminder',
            title=title,
            message=message,
            round=round,
            action_url=action_url
        )
    
    @staticmethod
    def create_invitation_notification(invitee_user, inviter, round):
        """
        Notify about round invitation
        """
        title = f"📨 Invitation to Join - {round.name}"
        message = (
            f"{inviter.get_full_name() or inviter.username} has invited you to join "
            f"the savings round '{round.name}'. "
            f"Contribution: KES {round.contribution_amount:,.2f} {round.get_frequency_display()}."
        )
        
        # Note: action_url will be set when invitation is created with token
        
        return NotificationService.create_notification(
            user=invitee_user,
            notification_type='invitation_received',
            title=title,
            message=message,
            round=round,
            action_url=''  # Will be updated with invitation token
        )
    
    @staticmethod
    def mark_all_as_read(user):
        """Mark all notifications as read for a user"""
        from .models import Notification
        
        Notification.objects.filter(user=user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
    
    @staticmethod
    def get_unread_count(user):
        """Get count of unread notifications"""
        from .models import Notification
        
        return Notification.objects.filter(user=user, is_read=False).count()
    
    @staticmethod
    def create_weekly_summary_notification(user, stats):
        """
        Send weekly summary to user
        
        Args:
            user: User object
            stats: Dict with keys like 'contributions_made', 'amount_contributed', etc.
        """
        contributions = stats.get('contributions_made', 0)
        amount = stats.get('amount_contributed', 0)
        trust_score = stats.get('trust_score', 0)
        
        title = "📊 Weekly MGR Summary"
        message = (
            f"This week you made {contributions} contribution(s) "
            f"totaling KES {amount:,.2f}. "
            f"Your trust score is {trust_score}. Keep up the great work!"
        )
        
        action_url = reverse('merry_go_round:dashboard')
        
        return NotificationService.create_notification(
            user=user,
            notification_type='member_joined',  # Using generic type
            title=title,
            message=message,
            round=None,
            action_url=action_url
        )


class TrustScoreService:
    """Service for calculating and managing trust scores"""
    
    @staticmethod
    def calculate_trust_score(user_profile):
        """Calculate trust score based on payment history"""
        memberships = RoundMembership.objects.filter(user=user_profile.user)
        
        if not memberships.exists():
            return 50  # Default score for new users
        
        # Calculate metrics
        total_contributions = Contribution.objects.filter(
            membership__in=memberships
        ).count()
        
        completed_contributions = Contribution.objects.filter(
            membership__in=memberships,
            status='completed'
        ).count()
        
        missed_contributions = Contribution.objects.filter(
            membership__in=memberships,
            status='missed'
        ).count()
        
        if total_contributions == 0:
            return 50
        
        # Calculate score
        completion_rate = (completed_contributions / total_contributions) * 100
        
        # Penalties for missed payments
        penalty = missed_contributions * 5  # 5 points per missed payment
        
        # Bonus for completed rounds
        bonus = user_profile.completed_rounds * 2  # 2 points per completed round
        
        score = completion_rate - penalty + bonus
        score = max(0, min(100, int(score)))  # Clamp between 0-100
        
        return score
    
    @staticmethod
    def update_all_trust_scores():
        """Update trust scores for all users (run periodically)"""
        profiles = UserProfile.objects.all()
        
        for profile in profiles:
            old_score = profile.trust_score
            new_score = TrustScoreService.calculate_trust_score(profile)
            
            if old_score != new_score:
                profile.trust_score = new_score
                profile.save()


class InterestService:
    """Service for calculating interest"""
    
    @staticmethod
    def calculate_daily_interest():
        """Calculate and update interest for all active contributions (run daily)"""
        active_rounds = Round.objects.filter(status='active')
        
        for round_obj in active_rounds:
            contributions = Contribution.objects.filter(
                membership__round=round_obj,
                status='completed'
            )
            
            for contribution in contributions:
                # Increment days in escrow
                contribution.days_in_escrow += 1
                contribution.calculate_interest()
                
                # Update membership interest
                membership = contribution.membership
                membership.interest_earned = Contribution.objects.filter(
                    membership=membership,
                    status='completed'
                ).aggregate(total=Sum('interest_accrued'))['total'] or Decimal('0.00')
                membership.save()
        
        # Update round totals
        for round_obj in active_rounds:
            round_obj.total_interest_earned = RoundMembership.objects.filter(
                round=round_obj
            ).aggregate(total=Sum('interest_earned'))['total'] or Decimal('0.00')
            round_obj.save()
    
    @staticmethod
    def get_projected_interest(contribution_amount, annual_rate, days):
        """Calculate projected interest for a given amount and duration"""
        daily_rate = annual_rate / 365 / 100
        interest = contribution_amount * Decimal(str(daily_rate)) * Decimal(str(days))
        return round(interest, 2)