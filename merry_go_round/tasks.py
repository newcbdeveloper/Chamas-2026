# merry_go_round/tasks.py - COMPLETE CELERY TASK SUITE

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Sum, Count
from datetime import timedelta, date
import logging
from django.urls import reverse
from decimal import Decimal

from .models import (
    Round, RoundMembership, Contribution, Payout, 
    UserProfile, Invitation, Notification
)
from .services import (
    ContributionService, PayoutService, TrustScoreService, 
    InterestService, NotificationService, RoundService
)
from .wallet_services import WalletService

logger = logging.getLogger(__name__)


# ========================================
# DAILY CONTRIBUTION PROCESSING
# ========================================

@shared_task(name='mgr.auto_process_contributions')
def auto_process_due_contributions():
    """
    Process all contributions due today
    
    Priority: HIGH
    Schedule: Daily at 6:00 AM
    
    This task:
    1. Finds all contributions with status='pending' and due_date=today
    2. Processes each from locked wallet funds
    3. Auto-reserves next contribution after successful payment
    4. Sends notifications for failures
    """
    logger.info("=" * 80)
    logger.info("TASK: auto_process_due_contributions - STARTED")
    logger.info("=" * 80)
    
    today = timezone.now().date()
    due_contributions = Contribution.objects.filter(
        status='pending',
        due_date=today
    ).select_related(
        'membership__user', 
        'membership__round'
    )
    
    processed_count = 0
    failed_count = 0
    
    for contribution in due_contributions:
        try:
            # Process the contribution (does NOT send notification internally)
            ContributionService.process_contribution(contribution)
            processed_count += 1
            
            # Send ONE complete success notification HERE
            NotificationService.create_contribution_success(
                user=contribution.membership.user,
                round=contribution.membership.round,
                amount=contribution.amount,
                cycle_number=contribution.cycle_number
            )
            
            logger.info(
                f" Processed: User {contribution.membership.user.username}, "
                f"Round {contribution.membership.round.name}, "
                f"Amount KES {contribution.amount}"
            )
            
        except ValueError as e:
            # Payment failed - mark and notify
            contribution.status = 'failed'
            contribution.save()
            failed_count += 1
            
            logger.warning(
                f"⚠️ Failed: {contribution.membership.user.username} - {str(e)}"
            )
            
            # Send ONE failure notification
            wallet = WalletService.get_or_create_wallet(contribution.membership.user)
            NotificationService.create_insufficient_balance_alert(
                user=contribution.membership.user,
                round=contribution.membership.round,
                required_amount=contribution.amount,
                current_balance=wallet.available_balance
            )
    
    logger.info(f"✅ COMPLETED: {processed_count} processed, {failed_count} failed")
    
    return {
        'processed': processed_count,
        'failed': failed_count
    }

@shared_task(name='mgr.mark_missed_contributions')
def mark_missed_contributions():
    """
    Mark overdue contributions as 'missed'
    
    Priority: HIGH
    Schedule: Daily at 7:00 AM (after processing)
    
    This task:
    1. Finds contributions past due date with status 'pending'/'failed'
    2. Marks them as 'missed'
    3. Updates trust scores
    4. Sends notifications
    """
    logger.info("TASK: mark_missed_contributions - STARTED")
    
    today = timezone.now().date()
    overdue = Contribution.objects.filter(
        status__in=['pending', 'failed'],
        due_date__lt=today,
        membership__round__status='active'
    ).select_related(
        'membership__user', 
        'membership__round'
    )
    
    missed_count = 0
    
    for contribution in overdue:
        # Double-check round status
        if contribution.membership.round.status != 'active':
            continue
            
        try:
            contribution.mark_as_missed()
            missed_count += 1
            
            NotificationService.create_missed_payment_notification(
                user=contribution.membership.user,
                round=contribution.membership.round,
                cycle_number=contribution.cycle_number
            )
            
            logger.info(f"Marked missed: {contribution.membership.user.username}, Cycle {contribution.cycle_number}")
            
        except Exception as e:
            logger.error(f"Error marking missed: {str(e)}")
    
    logger.info(f" COMPLETED: {missed_count} contributions marked as missed")
    
    return {'missed_count': missed_count}


# ========================================
# REMINDER TASKS
# ========================================

@shared_task(name='mgr.send_contribution_reminders')
def send_contribution_reminders():
    """
    Send reminders for contributions due tomorrow
    
    Priority: MEDIUM
    Schedule: Daily at 8:00 AM
    
    Checks if funds are reserved and sends appropriate reminder
    """
    logger.info("TASK: send_contribution_reminders - STARTED")
    
    tomorrow = timezone.now().date() + timedelta(days=1)
    upcoming = Contribution.objects.filter(
        status='pending',
        due_date=tomorrow
    ).select_related(
        'membership__user', 
        'membership__round', 
        'membership'
    )
    
    reminded_count = 0
    needs_deposit_count = 0
    
    for contribution in upcoming:
        membership = contribution.membership
        wallet = WalletService.get_or_create_wallet(membership.user)
        
        # Check if funds are reserved
        if membership.locked_amount >= contribution.amount:
            # Standard reminder - funds ready
            NotificationService.create_contribution_reminder(
                user=membership.user,
                round=membership.round,
                contribution=contribution,
                days_until_due=1
            )
            reminded_count += 1
        else:
            # Urgent - need to deposit
            shortfall = contribution.amount - membership.locked_amount
            NotificationService.create_insufficient_balance_alert(
                user=membership.user,
                round=membership.round,
                required_amount=contribution.amount,
                current_balance=membership.locked_amount
            )
            needs_deposit_count += 1
        
        logger.info(f"Reminder sent: {membership.user.username}")
    
    logger.info(
        f"✅ COMPLETED: {reminded_count} reminders, "
        f"{needs_deposit_count} need deposits"
    )
    
    return {
        'reminded': reminded_count,
        'needs_deposit': needs_deposit_count
    }


@shared_task(name='mgr.send_advance_reminders')
def send_advance_reminders():
    """
    Send 3-day advance reminders
    
    Priority: LOW
    Schedule: Daily at 9:00 AM
    """
    logger.info("TASK: send_advance_reminders - STARTED")
    
    three_days_ahead = timezone.now().date() + timedelta(days=3)
    upcoming = Contribution.objects.filter(
        status='pending',
        due_date=three_days_ahead
    ).select_related('membership__user', 'membership__round')
    
    sent_count = 0
    
    for contribution in upcoming:
        NotificationService.create_contribution_reminder(
            user=contribution.membership.user,
            round=contribution.membership.round,
            contribution=contribution,
            days_until_due=3
        )
        sent_count += 1
    
    logger.info(f"✅ COMPLETED: {sent_count} advance reminders sent")
    
    return {'sent': sent_count}


@shared_task(name='mgr.send_reservation_reminders')
def send_reservation_reminders():
    """
    Remind users to reserve funds for upcoming contributions
    
    Priority: MEDIUM
    Schedule: Daily at 9:30 AM
    """
    logger.info("TASK: send_reservation_reminders - STARTED")
    
    three_days_ahead = timezone.now().date() + timedelta(days=3)
    today = timezone.now().date()
    
    upcoming = Contribution.objects.filter(
        status='pending',
        due_date__gte=today,
        due_date__lte=three_days_ahead
    ).select_related('membership__user', 'membership__round', 'membership')
    
    reminded_count = 0
    
    for contribution in upcoming:
        membership = contribution.membership
        
        # Check if reservation needed
        if membership.needs_reservation():
            wallet = WalletService.get_or_create_wallet(membership.user)
            shortfall = contribution.amount - membership.locked_amount
            
            NotificationService.create_insufficient_balance_alert(
                user=membership.user,
                round=membership.round,
                required_amount=contribution.amount,
                current_balance=wallet.available_balance
            )
            reminded_count += 1
            
            logger.info(
                f"Reservation reminder: {membership.user.username}, "
                f"Shortfall: KES {shortfall}"
            )
    
    logger.info(f"✅ COMPLETED: {reminded_count} reservation reminders sent")
    
    return {'reminded': reminded_count}


# ========================================
# PAYOUT PROCESSING
# ========================================

@shared_task(name='mgr.process_due_payouts')
def process_due_payouts():
    """
    Process all scheduled payouts for today
    
    Priority: HIGH
    Schedule: Daily at 10:00 AM
    
    Handles both Marathon and Rotational models with eligibility checks
    """
    logger.info("TASK: process_due_payouts - STARTED")
    
    today = timezone.now().date()
    due_payouts = Payout.objects.filter(
        status='scheduled',
        scheduled_date__lte=today
    ).select_related(
        'recipient_membership__user', 
        'round'
    )
    
    processed_count = 0
    failed_count = 0
    deferred_count = 0
    
    for payout in due_payouts:
        try:
            membership = payout.recipient_membership
            
            # For Rotational: Check eligibility
            if payout.round.payout_model == 'rotational':
                if not membership.is_up_to_date():
                    # Defer payout
                    logger.warning(
                        f" Deferred: {membership.user.username} "
                        f"not up to date with contributions"
                    )
                    
                    # Send deferred notification
                    NotificationService.create_notification(
                        user=membership.user,
                        round=payout.round,
                        notification_type='payout_scheduled',
                        title=f'⏸️ Payout Delayed - {payout.round.name}',
                        message=(
                            f'Your payout is delayed because you have missed contributions. '
                            f'Please catch up to receive your payout of KES {payout.amount:,.2f}.'
                        ),
                        action_url=reverse('merry_go_round:round_detail', kwargs={'round_id': payout.round.id})
                    )
                    deferred_count += 1
                    continue
            
            # Process payout (does NOT send notification internally)
            PayoutService.process_payout(payout)
            processed_count += 1
            
            # Extract tax info from payout notes
            tax_info = None
            if payout.notes and 'Tax deducted' in payout.notes:
                # Parse tax amount from notes like "Tax deducted: KES 180.00 (15%)"
                import re
                match = re.search(r'KES ([\d,]+\.?\d*)', payout.notes)
                tax_amount = Decimal(match.group(1).replace(',', '')) if match else Decimal('0')
                
                tax_info = {
                    'principal': payout.principal_amount,
                    'net_interest': payout.interest_amount,
                    'tax_amount': tax_amount,
                    'tax_deducted': payout.notes
                }
            
            # Send ONE complete notification with tax breakdown
            title = f" Payout Received - {payout.round.name}"
            
            if tax_info and tax_info['tax_amount'] > 0:
                # Show detailed breakdown including tax
                message = (
                    f"Congratulations! Your payout from {payout.round.name} has been processed.\n\n"
                    f" Total Received: KES {payout.amount:,.2f}\n"
                    f" Breakdown:\n"
                    f"  • Principal: KES {tax_info['principal']:,.2f}\n"
                    f"  • Interest (after tax): KES {tax_info['net_interest']:,.2f}\n"
                    f"  • Tax Deducted: KES {tax_info['tax_amount']:,.2f}\n\n"
                    f"The funds are now in your MGR wallet."
                )
            else:
                # Simple message (no tax or zero tax)
                message = (
                    f"Congratulations! You have received your payout of KES {payout.amount:,.2f} "
                    f"from {payout.round.name}. The funds are now in your MGR wallet."
                )
            
            NotificationService.create_notification(
                user=membership.user,
                round=payout.round,
                notification_type='payout_received',
                title=title,
                message=message,
                action_url=reverse('merry_go_round:wallet_dashboard')
            )
            
            logger.info(
                f" Payout processed: {membership.user.username}, "
                f"Amount: KES {payout.amount}"
            )
            
        except Exception as e:
            failed_count += 1
            logger.error(f"❌ Payout failed: {str(e)}")
    
    logger.info(
        f" COMPLETED: {processed_count} processed, "
        f"{failed_count} failed, {deferred_count} deferred"
    )
    
    return {
        'processed': processed_count,
        'failed': failed_count,
        'deferred': deferred_count
    }


# ========================================
# INTEREST & SCORING
# ========================================

@shared_task(name='mgr.calculate_daily_interest')
def calculate_daily_interest():
    """
    Calculate daily interest for all active contributions
    
    Priority: MEDIUM
    Schedule: Daily at 11:59 PM
    """
    logger.info("TASK: calculate_daily_interest - STARTED")
    
    InterestService.calculate_daily_interest()
    
    logger.info("✅ COMPLETED: Daily interest calculated")
    
    return {'status': 'completed'}


@shared_task(name='mgr.update_trust_scores')
def update_trust_scores():
    """
    Recalculate trust scores for all users
    
    Priority: LOW
    Schedule: Daily at 11:00 PM
    """
    logger.info("TASK: update_trust_scores - STARTED")
    
    TrustScoreService.update_all_trust_scores()
    
    logger.info("✅ COMPLETED: Trust scores updated")
    
    return {'status': 'completed'}


# ========================================
# ROUND LIFECYCLE MANAGEMENT
# ========================================

@shared_task(name='mgr.check_and_complete_rounds')
def check_and_complete_rounds():
    """
    UPDATED: Check for rounds that should be completed
    NEW LOGIC: 
    1. Mark round as completed
    2. Wait one day for final interest accrual
    3. Next day: Recalculate payouts and process them
    
    This ensures the LAST contribution earns interest!
    
    Priority: HIGH
    Schedule: Daily at 12:00 AM (midnight)
    """
    logger.info("TASK: check_and_complete_rounds - STARTED")
    
    today = timezone.now().date()
    rounds_to_check = Round.objects.filter(status='active')
    
    marked_complete_count = 0
    
    for round_obj in rounds_to_check:
        should_complete = False
        reason = ""
        
        # Check 1: End date passed
        if round_obj.end_date and round_obj.end_date <= today:
            should_complete = True
            reason = f"End date ({round_obj.end_date}) reached"
        
        # Check 2: Marathon - All members finished contributions
        if round_obj.payout_model == 'marathon':
            total_cycles = round_obj.calculate_total_cycles()
            memberships = RoundMembership.objects.filter(round=round_obj)
            
            all_cycles_complete = True
            for membership in memberships:
                completed_count_member = Contribution.objects.filter(
                    membership=membership,
                    status='completed'
                ).count()
                
                total_expected = Contribution.objects.filter(
                    membership=membership
                ).count()
                
                member_done = (
                    completed_count_member >= total_expected or
                    (round_obj.end_date and round_obj.end_date <= today)
                )
                
                if not member_done:
                    all_cycles_complete = False
                    break
            
            if all_cycles_complete:
                should_complete = True
                reason = "All member contribution cycles completed"
        
        # Check 3: Rotational - all cycles done
        if round_obj.payout_model == 'rotational':
            total_cycles = round_obj.calculate_total_cycles()
            memberships = RoundMembership.objects.filter(round=round_obj)
            
            all_done = True
            for membership in memberships:
                completed = Contribution.objects.filter(
                    membership=membership,
                    status='completed'
                ).count()
                
                if completed < total_cycles:
                    all_done = False
                    break
            
            if all_done:
                should_complete = True
                reason = "All rotational cycles completed"
        
        if should_complete:
            try:
                logger.info(f"🏁 Marking round complete: {round_obj.name} - Reason: {reason}")
                
                # ==================================================
                # NEW: Just mark as completed - DON'T process payouts yet
                # ==================================================
                round_obj.status = 'completed'
                round_obj.end_date = today
                round_obj.save()
                
                # Update memberships to completed status
                memberships = RoundMembership.objects.filter(round=round_obj, status='active')
                memberships.update(status='completed')
                
                marked_complete_count += 1
                
                logger.info(
                    f"✅ Round '{round_obj.name}' marked as completed. "
                    f"Payouts will be processed tomorrow to allow final interest accrual."
                )
                
            except Exception as e:
                logger.error(f"❌ Failed to mark round complete {round_obj.name}: {str(e)}")
    
    logger.info(f"✅ COMPLETED: {marked_complete_count} rounds marked as completed")
    
    return {'marked_complete': marked_complete_count}


# Add this to your merry_go_round/tasks.py
# Replace the process_completed_round_payouts function with this version

@shared_task(name='mgr.process_completed_round_payouts')
def process_completed_round_payouts():
    """
    NEW TASK: Process payouts for rounds completed yesterday
    This runs AFTER interest has accrued for one more day
    
    Priority: HIGH
    Schedule: Daily at 1:00 AM (one hour after completion check)
    
    FIXED: Always creates RoundCompletionStats, even if payouts fail
    """
    logger.info("="*80)
    logger.info("TASK: process_completed_round_payouts - STARTED")
    logger.info("="*80)
    
    yesterday = timezone.now().date() - timedelta(days=1)
    
    # Find rounds that were marked completed yesterday
    newly_completed_rounds = Round.objects.filter(
        status='completed',
        end_date=yesterday
    ).prefetch_related('memberships')
    
    processed_count = 0
    
    for round_obj in newly_completed_rounds:
        # CRITICAL: Check if stats already exist
        from merry_go_round.models import RoundCompletionStats
        if hasattr(round_obj, 'completion_snapshot'):
            logger.info(f"Stats already exist for {round_obj.name}, skipping")
            continue
        
        try:
            logger.info(f"📄 Processing payouts for completed round: {round_obj.name}")
            
            # Calculate FINAL round-level statistics
            total_cycles = round_obj.calculate_total_cycles()
            total_expected = round_obj.contribution_amount * round_obj.max_members * total_cycles
            
            payout_success_count = 0
            payout_fail_count = 0
            
            # For marathon rounds: Recalculate and process payouts
            if round_obj.payout_model == 'marathon':
                payouts = Payout.objects.filter(
                    round=round_obj,
                    status='scheduled'
                )
                
                for payout in payouts:
                    try:
                        # Recalculate based on ACTUAL contributions with FULL interest
                        PayoutService.process_payout(payout)
                        payout_success_count += 1
                        logger.info(f"  ✅ Payout processed for {payout.recipient_membership.user.username}")
                    except Exception as e:
                        payout_fail_count += 1
                        logger.error(f"  ❌ Failed payout for {payout.recipient_membership.user.username}: {str(e)}")
            
            # For rotational rounds: Process any remaining payouts
            elif round_obj.payout_model == 'rotational':
                remaining_payouts = Payout.objects.filter(
                    round=round_obj,
                    status='scheduled'
                )
                
                for payout in remaining_payouts:
                    try:
                        PayoutService.process_payout(payout)
                        payout_success_count += 1
                    except Exception as e:
                        payout_fail_count += 1
                        logger.error(f"  ❌ Failed payout: {str(e)}")
            
            logger.info(f"Payouts: {payout_success_count} succeeded, {payout_fail_count} failed")
            
            # ====================================================================
            # CRITICAL: ALWAYS CREATE STATS - Even if some payouts failed
            # ====================================================================
            try:
                # Get actual totals from completed payouts (only successful ones)
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
                
                # FREEZE statistics forever
                stats = RoundCompletionStats.objects.create(
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
                
                logger.info(
                    f"🔒 FROZEN STATS CREATED for '{round_obj.name}': "
                    f"Expected: {total_expected}, Actual: {total_principal}, "
                    f"Net Interest: {total_net_interest}, Tax: {total_tax}"
                )
                
            except Exception as stats_error:
                logger.error(f"❌ CRITICAL: Failed to create frozen stats for {round_obj.name}: {stats_error}")
                # Don't fail the whole task, continue with cleanup
            
            # Unlock any remaining locked funds
            memberships = RoundMembership.objects.filter(round=round_obj)
            for membership in memberships:
                if membership.locked_amount > 0:
                    WalletService.unlock_all_funds_for_round(membership.user, round_obj)
                    membership.locked_amount = 0
                    membership.save()
                
                # Update trust scores
                profile = membership.user.mgr_profile
                profile.completed_rounds += 1
                profile.update_trust_score()
                
                # Send completion notification
                total_expected_user = round_obj.contribution_amount * round_obj.calculate_total_cycles()
                total_actual_user = membership.total_contributed
                completion_pct_user = (total_actual_user / total_expected_user * 100) if total_expected_user > 0 else 0
                
                title = f"🎊 Round Completed - {round_obj.name}"
                
                if completion_pct_user >= 100:
                    message = (
                        f"Congratulations! {round_obj.name} has been completed successfully.\n\n"
                        f"📊 You completed all {membership.contributions_made} contributions!\n"
                        f"💰 Total Contributed: KES {membership.total_contributed:,.2f}\n"
                        f"📈 Interest Earned: KES {membership.interest_earned:,.2f}\n\n"
                        f"Your payout has been processed. Thank you for your participation!"
                    )
                else:
                    message = (
                        f"{round_obj.name} has been completed.\n\n"
                        f"📊 Your Performance:\n"
                        f"  • Contributions Made: {membership.contributions_made}\n"
                        f"  • Total Contributed: KES {membership.total_contributed:,.2f}\n"
                        f"  • Completion Rate: {completion_pct_user:.0f}%\n"
                        f"  • Interest Earned: KES {membership.interest_earned:,.2f}\n\n"
                        f"Your payout has been adjusted based on actual contributions."
                    )
                
                NotificationService.create_notification(
                    user=membership.user,
                    round=round_obj,
                    notification_type='round_completed',
                    title=title,
                    message=message,
                    action_url=reverse('merry_go_round:round_detail', kwargs={'round_id': round_obj.id})
                )
            
            processed_count += 1
            
            logger.info(f"✅ Round '{round_obj.name}' processing complete")
            
        except Exception as e:
            logger.error(f"❌ Failed to process payouts for {round_obj.name}: {str(e)}")
            logger.exception("Full error trace:")
    
    logger.info(f"✅ COMPLETED: {processed_count} round payouts processed")
    
    return {'processed': processed_count}

# ========================================
# WEEKLY SUMMARIES
# ========================================

@shared_task(name='mgr.send_weekly_summary')
def send_weekly_summary():
    """
    Send weekly summary to all active users
    
    Priority: LOW
    Schedule: Every Monday at 8:00 AM
    """
    logger.info("TASK: send_weekly_summary - STARTED")
    
    # Get all users with active memberships
    active_users = UserProfile.objects.filter(
        user__round_memberships__status='active'
    ).distinct()
    
    sent_count = 0
    week_ago = timezone.now().date() - timedelta(days=7)
    
    for profile in active_users:
        try:
            # Calculate weekly stats
            weekly_contributions = Contribution.objects.filter(
                membership__user=profile.user,
                status='completed',
                payment_date__date__gte=week_ago
            )
            
            contributions_count = weekly_contributions.count()
            total_amount = weekly_contributions.aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            if contributions_count > 0:
                stats = {
                    'contributions_made': contributions_count,
                    'amount_contributed': total_amount,
                    'trust_score': profile.trust_score
                }
                
                NotificationService.create_weekly_summary_notification(
                    user=profile.user,
                    stats=stats
                )
                sent_count += 1
                
        except Exception as e:
            logger.error(f"Failed weekly summary for {profile.user.username}: {str(e)}")
    
    logger.info(f"✅ COMPLETED: {sent_count} summaries sent")
    
    return {'sent': sent_count}


# ========================================
# CLEANUP TASKS
# ========================================

@shared_task(name='mgr.cleanup_expired_invitations')
def cleanup_expired_invitations():
    """
    Mark expired invitations
    
    Priority: LOW
    Schedule: Daily at 2:00 AM
    """
    logger.info("TASK: cleanup_expired_invitations - STARTED")
    
    now = timezone.now()
    expired = Invitation.objects.filter(
        status='pending',
        expires_at__lt=now
    )
    
    expired_count = expired.update(status='expired')
    
    logger.info(f"✅ COMPLETED: {expired_count} invitations expired")
    
    return {'expired': expired_count}


# ========================================
# EMERGENCY TASKS (Manual Trigger)
# ========================================

@shared_task(name='mgr.emergency_process_all_pending')
def emergency_process_all_pending():
    """
    Emergency task to process ALL pending contributions
    (Manual trigger only - use with caution)
    """
    logger.warning("⚠️ EMERGENCY TASK: Processing ALL pending contributions")
    
    pending = Contribution.objects.filter(
        status='pending',
        due_date__lte=timezone.now().date()
    )
    
    processed = 0
    failed = 0
    
    for contribution in pending:
        try:
            ContributionService.process_contribution(contribution)
            processed += 1
        except:
            failed += 1
    
    logger.warning(f"⚠️ EMERGENCY COMPLETED: {processed} processed, {failed} failed")
    
    return {'processed': processed, 'failed': failed}


@shared_task(name='mgr.recalculate_all_interest')
def recalculate_all_interest():
    """
    Recalculate interest for all contributions
    (Manual trigger only - use for corrections)
    """
    logger.warning("⚠️ RECALCULATION: All interest")
    
    contributions = Contribution.objects.filter(status='completed')
    count = 0
    
    for contribution in contributions:
        contribution.calculate_interest()
        count += 1
    
    logger.warning(f"⚠️ RECALCULATION COMPLETED: {count} contributions updated")
    
    return {'recalculated': count}

@shared_task(name='mgr.send_invitation_reminders')
def send_invitation_reminders():
    """
    Send reminders for pending invitations after 1 day
    
    Priority: MEDIUM
    Schedule: Daily at 10:00 AM
    
    - Reminds invitees about pending invitations
    - Sends after 1 day, 3 days, and 5 days
    """
    logger.info("TASK: send_invitation_reminders - STARTED")
    
    now = timezone.now()
    
    # Find invitations needing reminders (1, 3, or 5 days old)
    one_day_ago = now - timedelta(days=1)
    three_days_ago = now - timedelta(days=3)
    five_days_ago = now - timedelta(days=5)
    
    # Get pending invitations
    pending_invitations = Invitation.objects.filter(
        status='pending',
        expires_at__gt=now  # Not expired yet
    ).select_related('round', 'inviter')
    
    reminded_count = 0
    
    for invitation in pending_invitations:
        days_old = (now - invitation.created_at).days
        
        # Send reminder at 1, 3, and 5 days
        if days_old in [1, 3, 5]:
            # Check if we already sent this specific reminder
            recent_reminder = Notification.objects.filter(
                round=invitation.round,
                notification_type='invitation_received',
                created_at__gte=now - timedelta(hours=12),  # Within last 12 hours
                message__icontains=f'Day {days_old}'
            ).exists()
            
            if not recent_reminder:
                # Determine recipient
                recipient_user = None
                
                if invitation.invitee_user:
                    recipient_user = invitation.invitee_user
                elif invitation.invitee_national_id:
                    try:
                        from authentication.models import Profile
                        profile = Profile.objects.get(NIC_No=invitation.invitee_national_id)
                        recipient_user = profile.owner
                    except:
                        pass
                elif invitation.invitee_email:
                    from django.contrib.auth.models import User
                    try:
                        recipient_user = User.objects.get(email=invitation.invitee_email)
                    except:
                        pass
                
                if recipient_user:
                    # Get inviter display name
                    inviter_name = invitation.inviter.get_full_name() or invitation.inviter.username
                    
                    # Create urgency-based message
                    if days_old == 1:
                        title = f" Reminder: Invitation to {invitation.round.name}"
                        urgency = "You have a pending invitation!"
                    elif days_old == 3:
                        title = f" Reminder: Invitation Expiring Soon"
                        urgency = "Don't miss out! Review your invitation soon."
                    else:  # 5 days
                        title = f" Urgent: Invitation Expires in 2 Days!"
                        urgency = "Last chance to join this round!"
                    
                    message = (
                        f"{urgency}\n\n"
                        f"{inviter_name} invited you to join '{invitation.round.name}' {days_old} days ago. "
                        f"The invitation expires on {invitation.expires_at.strftime('%B %d, %Y')}.\n\n"
                        f" Contribution: KES {invitation.round.contribution_amount:,.0f} {invitation.round.get_frequency_display()}\n"
                        f" Members: {invitation.round.current_members}/{invitation.round.max_members}\n\n"
                        f"Review and respond to the invitation now!"
                    )
                    
                    NotificationService.create_notification(
                        user=recipient_user,
                        notification_type='invitation_received',
                        title=title,
                        message=message,
                        round=invitation.round,
                        action_url=reverse('merry_go_round:review_invitation', kwargs={'token': invitation.token})
                    )
                    
                    reminded_count += 1
                    logger.info(
                        f" Sent day-{days_old} reminder for invitation to "
                        f"{recipient_user.username} for round {invitation.round.name}"
                    )
    
    logger.info(f" COMPLETED: {reminded_count} invitation reminders sent")
    
    return {'reminded': reminded_count}


@shared_task(name='mgr.notify_expired_invitations')
def notify_expired_invitations():
    """
    Notify inviters when their invitations expire without response
    
    Priority: LOW
    Schedule: Daily at 11:00 AM
    """
    logger.info("TASK: notify_expired_invitations - STARTED")
    
    now = timezone.now()
    
    # Find invitations that expired in the last 24 hours
    yesterday = now - timedelta(days=1)
    
    newly_expired = Invitation.objects.filter(
        status='pending',
        expires_at__lt=now,
        expires_at__gte=yesterday
    ).select_related('round', 'inviter')
    
    notified_count = 0
    
    for invitation in newly_expired:
        # Mark as expired
        invitation.status = 'expired'
        invitation.save()
        
        # Notify inviter
        recipient_info = (
            invitation.invitee_email or 
            invitation.invitee_phone or 
            f"ID {invitation.invitee_national_id}" or
            "Unknown"
        )
        
        NotificationService.create_notification(
            user=invitation.inviter,
            notification_type='member_defaulted',
            title=f" Invitation Expired - {invitation.round.name}",
            message=(
                f"Your invitation to {recipient_info} for '{invitation.round.name}' has expired without response.\n\n"
                f"You can send a new invitation or invite other members to reach your target of "
                f"{invitation.round.max_members} members. "
                f"Current members: {invitation.round.current_members}/{invitation.round.max_members}"
            ),
            round=invitation.round,
            action_url=reverse('merry_go_round:send_invitation', kwargs={'round_id': invitation.round.id})
        )
        
        notified_count += 1
        logger.info(
            f"⏰ Notified {invitation.inviter.username} about expired invitation "
            f"for round {invitation.round.name}"
        )
    
    logger.info(f" COMPLETED: {notified_count} expiry notifications sent")
    
    return {'notified': notified_count}


@shared_task(name='mgr.check_pending_invitations_quota')
def check_pending_invitations_quota():
    """
    Alert round creators when they're close to losing quorum due to pending invitations
    
    Priority: MEDIUM
    Schedule: Daily at 9:00 AM
    """
    logger.info("TASK: check_pending_invitations_quota - STARTED")
    
    from .models import Round
    
    # Find rounds that are open/draft with pending invitations
    rounds_with_invitations = Round.objects.filter(
        status__in=['draft', 'open']
    ).prefetch_related('invitations')
    
    alerted_count = 0
    
    for round_obj in rounds_with_invitations:
        pending_count = round_obj.invitations.filter(status='pending').count()
        current_members = round_obj.current_members
        max_members = round_obj.max_members
        
        # Calculate available spots
        committed_spots = current_members + pending_count
        available_spots = max_members - committed_spots
        
        # Alert if we're running low on responses
        if pending_count > 0 and available_spots < 2:
            # Check if we already sent this alert recently
            recent_alert = Notification.objects.filter(
                user=round_obj.creator,
                round=round_obj,
                notification_type='member_defaulted',
                created_at__gte=timezone.now() - timedelta(days=2),
                message__icontains='pending invitations'
            ).exists()
            
            if not recent_alert:
                NotificationService.create_notification(
                    user=round_obj.creator,
                    notification_type='member_defaulted',
                    title=f"⚠️ Action Needed: {round_obj.name}",
                    message=(
                        f"You have {pending_count} pending invitation(s) that haven't been responded to.\n\n"
                        f"📊 Status:\n"
                        f"  • Confirmed Members: {current_members}\n"
                        f"  • Pending Invitations: {pending_count}\n"
                        f"  • Target: {max_members} members\n"
                        f"  • Available Spots: {available_spots}\n\n"
                        f"💡 Tip: Follow up with invited members or send new invitations to reach quorum!"
                    ),
                    round=round_obj,
                    action_url=reverse('merry_go_round:send_invitation', kwargs={'round_id': round_obj.id})
                )
                
                alerted_count += 1
                logger.info(
                    f"⚠️ Alerted {round_obj.creator.username} about pending invitations "
                    f"for round {round_obj.name}"
                )
    
    logger.info(f"✅ COMPLETED: {alerted_count} quota alerts sent")
    
    return {'alerted': alerted_count}