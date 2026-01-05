
from celery import shared_task
from django.core.management import call_command
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal
import logging

from Goals.models import Goal, Interest_Rate
from authentication.models import Profile
from notifications.models import UserFcmTokens
from notifications.utils import send_sms, send_notif

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, name='goals.send_goal_reminders')
def send_goal_reminders_task(self):
    """
    Scheduled task: Send reminders to users for their active personal goals.
    Runs daily at 9:00 AM via Celery Beat.
    
    Uses payment_frequency as the primary trigger for reminders.
    """
    try:
        logger.info(f"🔔 Starting goal reminders processing at {timezone.now()}")
        
        today = timezone.now().date()
        
        # Get all active goals that are due for a reminder
        active_goals = Goal.objects.filter(
            is_active='Yes'
        ).select_related('user').prefetch_related('user__profile')
        
        total_processed = 0
        reminders_sent = 0
        errors = 0
        
        for goal in active_goals:
            total_processed += 1
            
            try:
                # Determine the effective reminder frequency
                # PRIORITY: payment_frequency overrides reminder_frequency
                effective_frequency = goal.payment_frequency or goal.reminder_frequency
                
                if not effective_frequency:
                    logger.debug(f"Goal {goal.id} ({goal.name}): No reminder frequency set, skipping")
                    continue
                
                # Check if reminder should be sent today
                should_send = _should_send_reminder(goal, today, effective_frequency)
                
                if should_send:
                    success = _send_reminder_notification(goal)
                    
                    if success:
                        reminders_sent += 1
                        
                        # Update next notification date
                        goal.notification_date = _calculate_next_notification_date(
                            today, effective_frequency
                        )
                        goal.save(skip_validation=True)
                        
                        logger.info(
                            f"✓ Sent reminder for goal: {goal.name} (ID: {goal.id}, "
                            f"User: {goal.user.username}, Frequency: {effective_frequency})"
                        )
                    else:
                        errors += 1
                        logger.warning(f"✗ Failed to send reminder for goal: {goal.name} (ID: {goal.id})")
                        
            except Exception as e:
                errors += 1
                logger.error(f"Error processing goal {goal.id}: {str(e)}", exc_info=True)
        
        # Log summary
        logger.info(
            f"✅ Goal reminders processing completed. "
            f"Processed: {total_processed}, Sent: {reminders_sent}, Errors: {errors}"
        )
        
        return {
            'total_processed': total_processed,
            'reminders_sent': reminders_sent,
            'errors': errors,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"❌ Failed to process goal reminders: {exc}", exc_info=True)
        # Retry with exponential backoff (60s, 120s, 240s)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


def _should_send_reminder(goal, today, frequency):
    """
    Determine if a reminder should be sent today based on frequency.
    
    Args:
        goal: Goal instance
        today: Current date
        frequency: 'daily', 'weekly', or 'monthly'
    
    Returns:
        bool: True if reminder should be sent
    """
    # If notification_date is not set, initialize it
    if not goal.notification_date:
        goal.notification_date = _calculate_next_notification_date(
            goal.start_date or today, frequency
        )
        goal.save(skip_validation=True)
        return False
    
    # Send reminder if today is on or after the notification date
    return today >= goal.notification_date


def _calculate_next_notification_date(current_date, frequency):
    """
    Calculate the next notification date based on frequency.
    
    Args:
        current_date: Starting date
        frequency: 'daily', 'weekly', or 'monthly'
    
    Returns:
        date: Next notification date
    """
    from datetime import timedelta
    
    if frequency == 'daily':
        return current_date + timedelta(days=1)
    elif frequency == 'weekly':
        return current_date + timedelta(weeks=1)
    elif frequency == 'monthly':
        # Add approximately 30 days for monthly
        return current_date + timedelta(days=30)
    else:
        # Default to weekly if frequency is unknown
        logger.warning(f"Unknown frequency '{frequency}', defaulting to weekly")
        return current_date + timedelta(weeks=1)


def _send_reminder_notification(goal):
    """
    Send reminder notification via SMS and push notification.
    
    Args:
        goal: Goal instance
    
    Returns:
        bool: True if at least one notification method succeeded
    """
    try:
        user_profile = Profile.objects.get(owner=goal.user)
        
        # Build reminder message
        message = _build_reminder_message(goal)
        
        sms_success = False
        push_success = False
        
        # Send SMS
        try:
            send_sms(user_profile.phone, 'Goal Reminder 💰', message)
            sms_success = True
            logger.debug(f"SMS sent for goal {goal.id}")
        except Exception as e:
            logger.error(f"SMS failed for goal {goal.id}: {str(e)}")
        
        # Send push notification
        try:
            fcm_tokens = UserFcmTokens.objects.filter(user=goal.user).order_by('-token')[:1]
            send_notif(
                fcm_tokens, 
                None, 
                True, 
                True, 
                "💰 Time to Save!", 
                message, 
                None, 
                False, 
                goal.user
            )
            push_success = True
            logger.debug(f"Push notification sent for goal {goal.id}")
        except Exception as e:
            logger.error(f"Push notification failed for goal {goal.id}: {str(e)}")
        
        # Return True if at least one method succeeded
        return sms_success or push_success
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {goal.user.username}")
        return False
    except Exception as e:
        logger.error(f"Failed to send reminder for goal {goal.id}: {str(e)}", exc_info=True)
        return False


def _build_reminder_message(goal):
    """
    Build a personalized reminder message.
    
    Args:
        goal: Goal instance
    
    Returns:
        str: Formatted reminder message
    """
    frequency_text = {
        'daily': 'daily',
        'weekly': 'this week',
        'monthly': 'this month'
    }
    
    freq = goal.payment_frequency or goal.reminder_frequency or 'regularly'
    freq_display = frequency_text.get(freq, freq)
    
    # Calculate progress
    progress_pct = goal.percentage()
    
    # Base message
    message = f"Hi {goal.user.first_name}! 👋\n\n"
    message += f"Reminder: It's time to save towards your goal '{goal.name}' ({freq_display}).\n\n"
    
    # Add suggested amount if available
    if goal.amount_to_save_per_notification and goal.amount_to_save_per_notification > 0:
        message += f"💵 Suggested amount: KES {goal.amount_to_save_per_notification:,.2f}\n"
    
    # Add progress information
    if goal.goal_amount:
        remaining = goal.goal_amount - goal.goal_balance
        message += f"📊 Progress: {progress_pct}% complete\n"
        message += f"💰 Saved: KES {goal.goal_balance:,.2f} / KES {goal.goal_amount:,.2f}\n"
        if remaining > 0:
            message += f"🎯 Remaining: KES {remaining:,.2f}\n"
    else:
        message += f"💰 Current savings: KES {goal.goal_balance:,.2f}\n"
    
    # Add days remaining if applicable
    if goal.end_date:
        days_left = goal.calculate_month_difference()
        if days_left > 0:
            message += f"⏰ Days remaining: {days_left}\n"
    
    # Add interest rate info
    message += f"\n{_get_interest_rate_text(goal)}\n"
    
    # Motivational closing based on progress
    if progress_pct >= 75:
        message += "\n🎯 You're almost there! Keep going!"
    elif progress_pct >= 50:
        message += "\n💪 Great progress! You're halfway there!"
    elif progress_pct >= 25:
        message += "\n🌟 You're doing great! Keep it up!"
    else:
        message += "\n🚀 Every contribution counts! Stay consistent!"
    
    message += "\n\n📱 Log in to ChamaSpace to make your contribution."
    
    return message


def _get_interest_rate_text(goal):
    """
    Get interest rate information text.
    
    Args:
        goal: Goal instance
    
    Returns:
        str: Interest rate description
    """
    try:
        interest_rates = Interest_Rate.objects.get(pk=1)
        if goal.saving_type == 'fixed':
            rate = interest_rates.percent_fixed_deposit()
            return f"📈 Earning {rate}% interest p.a. (Fixed Saving)"
        else:
            rate = interest_rates.percent_regular_deposit()
            return f"📈 Earning {rate}% interest p.a. (Regular Saving)"
    except Interest_Rate.DoesNotExist:
        logger.warning("Interest_Rate object not found")
        return "📈 Earning competitive interest rates"
    except Exception as e:
        logger.error(f"Error fetching interest rate: {str(e)}")
        return "📈 Earning competitive interest rates"


# ==================== OPTIONAL: Manual Trigger Task ====================

@shared_task(name='goals.send_single_goal_reminder')
def send_single_goal_reminder(goal_id):
    """
    Send a reminder for a specific goal (can be triggered manually).
    
    Args:
        goal_id: ID of the goal to send reminder for
    
    Returns:
        dict: Result of the reminder sending
    """
    try:
        goal = Goal.objects.select_related('user').get(pk=goal_id, is_active='Yes')
        
        success = _send_reminder_notification(goal)
        
        if success:
            logger.info(f"✓ Manual reminder sent for goal: {goal.name} (ID: {goal_id})")
            return {
                'success': True,
                'goal_id': goal_id,
                'goal_name': goal.name,
                'message': 'Reminder sent successfully'
            }
        else:
            logger.warning(f"✗ Failed to send manual reminder for goal: {goal.name} (ID: {goal_id})")
            return {
                'success': False,
                'goal_id': goal_id,
                'message': 'Failed to send reminder'
            }
            
    except Goal.DoesNotExist:
        logger.error(f"Goal {goal_id} not found or not active")
        return {
            'success': False,
            'goal_id': goal_id,
            'message': 'Goal not found or not active'
        }
    except Exception as e:
        logger.error(f"Error sending manual reminder for goal {goal_id}: {str(e)}", exc_info=True)
        return {
            'success': False,
            'goal_id': goal_id,
            'message': str(e)
        }