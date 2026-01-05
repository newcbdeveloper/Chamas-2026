from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import SupportTicket, SupportMessage, TicketAuditLog
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=SupportTicket)
def ticket_created_handler(sender, instance, created, **kwargs):
    """
    Handle actions when a new ticket is created
    """
    if created:
        # Create audit log for ticket creation
        TicketAuditLog.objects.create(
            ticket=instance,
            action='created',
            performed_by=instance.user,
            notes=f"Ticket created with subject: {instance.subject}"
        )
        
        logger.info(
            f"New support ticket created: {instance.reference_number} "
            f"by user {instance.user.username}"
        )
        
        # Send notification to user confirming ticket creation
        from notifications.models import UserNotificationHistory
        UserNotificationHistory.objects.create(
            user=instance.user,
            notification_title='Support Ticket Created',
            notification_body=(
                f'Your support ticket {instance.reference_number} has been created. '
                f'Our team will respond as soon as possible. '
                f'You can track your ticket status in the Support section.'
            ),
            purpose='support'
        )


@receiver(post_save, sender=SupportMessage)
def message_sent_handler(sender, instance, created, **kwargs):
    """
    Handle actions when a new message is sent
    """
    if created:
        # Only process non-internal messages
        if not instance.is_internal:
            # If admin sent message, notify user
            if instance.sender_type == 'admin':
                try:
                    from notifications.models import UserNotificationHistory
                    UserNotificationHistory.objects.create(
                        user=instance.ticket.user,
                        notification_title=f'New Reply: {instance.ticket.reference_number}',
                        notification_body=(
                            f'Support has replied to your ticket "{instance.ticket.subject}". '
                            f'Click to view the response.'
                        ),
                        purpose='support'
                    )
                    
                    logger.info(
                        f"Admin reply notification sent for ticket {instance.ticket.reference_number}"
                    )
                except Exception as e:
                    logger.error(f"Failed to send admin reply notification: {str(e)}")
            
            # If user sent message, notify admins (if ticket is assigned)
            elif instance.sender_type == 'user' and instance.ticket.assigned_to:
                try:
                    from notifications.models import UserNotificationHistory
                    UserNotificationHistory.objects.create(
                        user=instance.ticket.assigned_to,
                        notification_title=f'New Message: {instance.ticket.reference_number}',
                        notification_body=(
                            f'User {instance.ticket.user.get_full_name()} replied to ticket '
                            f'"{instance.ticket.subject}".'
                        ),
                        purpose='support'
                    )
                    
                    logger.info(
                        f"User message notification sent to admin for ticket {instance.ticket.reference_number}"
                    )
                except Exception as e:
                    logger.error(f"Failed to send user message notification: {str(e)}")


@receiver(post_save, sender=SupportTicket)
def ticket_status_changed_handler(sender, instance, created, **kwargs):
    """
    Handle ticket status changes
    """
    if not created:
        # Check if status changed to resolved or closed
        if instance.status == 'resolved' and instance.resolved_at:
            try:
                from notifications.models import UserNotificationHistory
                UserNotificationHistory.objects.create(
                    user=instance.user,
                    notification_title=f'Ticket Resolved: {instance.reference_number}',
                    notification_body=(
                        f'Your support ticket "{instance.subject}" has been marked as resolved. '
                        f'If you need further assistance, you can reopen this ticket within 7 days.'
                    ),
                    purpose='support'
                )
                
                logger.info(f"Ticket resolved notification sent for {instance.reference_number}")
            except Exception as e:
                logger.error(f"Failed to send resolution notification: {str(e)}")
        
        elif instance.status == 'closed' and instance.closed_at:
            try:
                from notifications.models import UserNotificationHistory
                UserNotificationHistory.objects.create(
                    user=instance.user,
                    notification_title=f'Ticket Closed: {instance.reference_number}',
                    notification_body=(
                        f'Your support ticket "{instance.subject}" has been closed. '
                        f'Thank you for using ChamaSpace support.'
                    ),
                    purpose='support'
                )
                
                logger.info(f"Ticket closed notification sent for {instance.reference_number}")
            except Exception as e:
                logger.error(f"Failed to send closure notification: {str(e)}")


@receiver(post_save, sender=SupportTicket)
def ticket_assigned_handler(sender, instance, created, **kwargs):
    """
    Handle ticket assignment
    """
    if not created and instance.assigned_to:
        # Check if this is a new assignment
        try:
            from .models import TicketAssignment
            latest_assignment = instance.assignments.first()
            
            # If the latest assignment is very recent (within 5 seconds), it's likely a new assignment
            if latest_assignment:
                time_diff = (timezone.now() - latest_assignment.assigned_at).total_seconds()
                
                if time_diff < 5:
                    # Send notification to assigned admin
                    try:
                        from notifications.models import UserNotificationHistory
                        UserNotificationHistory.objects.create(
                            user=instance.assigned_to,
                            notification_title=f'Ticket Assigned: {instance.reference_number}',
                            notification_body=(
                                f'You have been assigned ticket "{instance.subject}" '
                                f'from {instance.user.get_full_name()}. '
                                f'Priority: {instance.get_priority_display()}'
                            ),
                            purpose='support'
                        )
                        
                        logger.info(
                            f"Assignment notification sent for ticket {instance.reference_number} "
                            f"to {instance.assigned_to.username}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send assignment notification: {str(e)}")
        except Exception as e:
            logger.error(f"Error in assignment handler: {str(e)}")