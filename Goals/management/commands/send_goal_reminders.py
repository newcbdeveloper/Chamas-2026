
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from Goals.models import Goal
from authentication.models import Profile
from notifications.models import UserFcmTokens
from notifications.utils import send_sms, send_notif
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send reminders to users for their active personal goals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually sending notifications (for testing)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No notifications will be sent'))
        
        # Get all active goals
        active_goals = Goal.objects.filter(is_active='Yes').select_related('user')
        
        total_processed = 0
        reminders_sent = 0
        errors = 0
        
        self.stdout.write(f'\nProcessing {active_goals.count()} active goals...\n')
        
        for goal in active_goals:
            total_processed += 1
            
            try:
                # Determine the effective reminder frequency
                # PRIORITY: payment_frequency overrides reminder_frequency
                effective_frequency = goal.payment_frequency or goal.reminder_frequency
                
                if not effective_frequency:
                    logger.info(f"Goal {goal.id} ({goal.name}): No reminder frequency set, skipping")
                    continue
                
                # Check if reminder should be sent today
                should_send = self._should_send_reminder(goal, today, effective_frequency)
                
                if should_send:
                    if not dry_run:
                        success = self._send_reminder(goal)
                        if success:
                            reminders_sent += 1
                            # Update next notification date
                            goal.notification_date = self._calculate_next_notification_date(
                                today, effective_frequency
                            )
                            goal.save(skip_validation=True)
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Sent reminder for goal: {goal.name} (User: {goal.user.username})'
                                )
                            )
                        else:
                            errors += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f'✗ Failed to send reminder for goal: {goal.name}'
                                )
                            )
                    else:
                        reminders_sent += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f'[DRY RUN] Would send reminder for: {goal.name} '
                                f'(Frequency: {effective_frequency})'
                            )
                        )
                        
            except Exception as e:
                errors += 1
                logger.error(f"Error processing goal {goal.id}: {str(e)}")
                self.stdout.write(
                    self.style.ERROR(f'✗ Error processing goal {goal.id}: {str(e)}')
                )
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'\nSummary:'))
        self.stdout.write(f'Total goals processed: {total_processed}')
        self.stdout.write(f'Reminders sent: {reminders_sent}')
        self.stdout.write(f'Errors: {errors}')
        self.stdout.write('='*60 + '\n')

    def _should_send_reminder(self, goal, today, frequency):
        """
        Determine if a reminder should be sent today based on frequency
        """
        # If notification_date is not set, initialize it
        if not goal.notification_date:
            goal.notification_date = self._calculate_next_notification_date(
                goal.start_date or today, frequency
            )
            goal.save(skip_validation=True)
            return False
        
        # Send reminder if today is on or after the notification date
        return today >= goal.notification_date

    def _calculate_next_notification_date(self, current_date, frequency):
        """
        Calculate the next notification date based on frequency
        """
        if frequency == 'daily':
            return current_date + timedelta(days=1)
        elif frequency == 'weekly':
            return current_date + timedelta(weeks=1)
        elif frequency == 'monthly':
            # Add approximately 30 days for monthly
            return current_date + timedelta(days=30)
        else:
            # Default to weekly if frequency is unknown
            return current_date + timedelta(weeks=1)

    def _send_reminder(self, goal):
        """
        Send reminder notification via SMS and push notification
        """
        try:
            user_profile = Profile.objects.get(owner=goal.user)
            
            # Build reminder message
            message = self._build_reminder_message(goal)
            
            # Send SMS
            try:
                send_sms(user_profile.phone, 'Goal Reminder', message)
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
            except Exception as e:
                logger.error(f"Push notification failed for goal {goal.id}: {str(e)}")
            
            logger.info(f"Reminder sent for goal {goal.id} ({goal.name})")
            return True
            
        except Profile.DoesNotExist:
            logger.error(f"Profile not found for user {goal.user.username}")
            return False
        except Exception as e:
            logger.error(f"Failed to send reminder for goal {goal.id}: {str(e)}")
            return False

    def _build_reminder_message(self, goal):
        """
        Build a personalized reminder message
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
        message = f"Hi {goal.user.first_name}! \n\n"
        message += f"Reminder: It's time to save towards your goal '{goal.name}' ({freq_display}).\n\n"
        
        # Add suggested amount if available
        if goal.amount_to_save_per_notification and goal.amount_to_save_per_notification > 0:
            message += f"Suggested amount: KES {goal.amount_to_save_per_notification}\n"
        
        # Add progress information
        if goal.goal_amount:
            remaining = goal.goal_amount - goal.goal_balance
            message += f"Progress: {progress_pct}% complete\n"
            message += f"Saved: KES {goal.goal_balance} / KES {goal.goal_amount}\n"
            if remaining > 0:
                message += f"Remaining: KES {remaining}\n"
        else:
            message += f"Current savings: KES {goal.goal_balance}\n"
        
        # Add days remaining if applicable
        if goal.end_date:
            days_left = goal.calculate_month_difference()
            if days_left > 0:
                message += f"Days remaining: {days_left}\n"
        
        # Add interest rate info
        message += f"\n{self._get_interest_rate_text(goal)}\n"
        
        # Motivational closing
        if progress_pct >= 75:
            message += "\n You're almost there! Keep going!"
        elif progress_pct >= 50:
            message += "\n💪 Great progress! You're halfway there!"
        elif progress_pct >= 25:
            message += "\n You're doing great! Keep it up!"
        else:
            message += "\n Every contribution counts! Stay consistent!"
        
        message += "\n\nLog in to ChamaSpace to make your contribution."
        
        return message

    def _get_interest_rate_text(self, goal):
        """
        Get interest rate information text
        """
        from Goals.models import Interest_Rate
        
        try:
            interest_rates = Interest_Rate.objects.get(pk=1)
            if goal.saving_type == 'fixed':
                rate = interest_rates.percent_fixed_deposit()
                return f"Earning {rate}% interest p.a. (Fixed Saving)"
            else:
                rate = interest_rates.percent_regular_deposit()
                return f"Earning {rate}% interest p.a. (Regular Saving)"
        except:
            return "Earning competitive interest rates"