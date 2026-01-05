from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import logging

from .models import SupportTicket, SupportMessage, TicketAssignment, TicketAuditLog
from .utils import sanitize_message, get_user_ip, detect_urgent_keywords

logger = logging.getLogger(__name__)


class TicketService:
    """
    Core service for ticket operations
    Handles ticket creation, assignment, status changes, etc.
    """
    
    @staticmethod
    @transaction.atomic
    def create_ticket(user, category, subject, initial_message, attachment=None, request=None):
        """
        Create a new support ticket
        
        Args:
            user: User object
            category: Ticket category
            subject: Ticket subject
            initial_message: First message content
            attachment: Optional file attachment
            request: HTTP request object (for IP logging)
            
        Returns:
            SupportTicket object
        """
        # Sanitize the message
        try:
            sanitize_message(initial_message)
        except ValidationError as e:
            raise e
        
        # Auto-detect priority based on message content
        priority = 'medium'
        if detect_urgent_keywords(initial_message):
            priority = 'urgent'
        elif category in ['suspicious', 'withdrawals', 'wallet']:
            priority = 'high'
        
        # Create the ticket
        ticket = SupportTicket.objects.create(
            user=user,
            category=category,
            subject=subject,
            priority=priority,
            status=SupportTicket.STATUS_OPEN
        )
        
        # Create the initial message
        message = SupportMessage.objects.create(
            ticket=ticket,
            sender_type=SupportMessage.SENDER_TYPE_USER,
            sender=user,
            message=initial_message,
            attachment=attachment
        )
        
        # Create audit log
        ip_address = get_user_ip(request) if request else None
        TicketAuditLog.objects.create(
            ticket=ticket,
            action='created',
            performed_by=user,
            notes=f"Ticket created: {subject}",
            ip_address=ip_address
        )
        
        logger.info(
            f"Ticket created: {ticket.reference_number} by user {user.username}, "
            f"category: {category}, priority: {priority}"
        )
        
        return ticket
    
    @staticmethod
    @transaction.atomic
    def add_message(ticket, sender_user, message_text, attachment=None, is_admin=False, is_internal=False):
        """
        Add a message to a ticket
        
        Args:
            ticket: SupportTicket object
            sender_user: User sending the message
            message_text: Message content
            attachment: Optional file attachment
            is_admin: Boolean indicating if sender is admin
            is_internal: Boolean for internal admin notes
            
        Returns:
            SupportMessage object
        """
        # Sanitize message (unless it's internal)
        if not is_internal:
            try:
                sanitize_message(message_text)
            except ValidationError as e:
                raise e
        
        # Determine sender type
        sender_type = SupportMessage.SENDER_TYPE_ADMIN if is_admin else SupportMessage.SENDER_TYPE_USER
        
        # Create message
        message = SupportMessage.objects.create(
            ticket=ticket,
            sender_type=sender_type,
            sender=sender_user,
            message=message_text,
            attachment=attachment,
            is_internal=is_internal
        )
        
        # Update ticket status if user replied to pending ticket
        if not is_admin and ticket.status == SupportTicket.STATUS_PENDING:
            ticket.status = SupportTicket.STATUS_OPEN
            ticket.save()
        
        logger.info(
            f"Message added to ticket {ticket.reference_number} by "
            f"{'admin' if is_admin else 'user'} {sender_user.username}"
        )
        
        return message
    
    @staticmethod
    @transaction.atomic
    def assign_ticket(ticket, assigned_to, assigned_by, notes="", request=None):
        """
        Assign a ticket to an admin
        
        Args:
            ticket: SupportTicket object
            assigned_to: User to assign ticket to
            assigned_by: User performing the assignment
            notes: Optional assignment notes
            request: HTTP request object
            
        Returns:
            TicketAssignment object
        """
        # Update ticket
        ticket.assigned_to = assigned_to
        ticket.assigned_at = timezone.now()
        ticket.save()
        
        # Create assignment record
        assignment = TicketAssignment.objects.create(
            ticket=ticket,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            notes=notes
        )
        
        # Create audit log
        ip_address = get_user_ip(request) if request else None
        TicketAuditLog.objects.create(
            ticket=ticket,
            action='assigned',
            performed_by=assigned_by,
            notes=f"Assigned to {assigned_to.get_full_name()}. {notes}",
            ip_address=ip_address
        )
        
        logger.info(
            f"Ticket {ticket.reference_number} assigned to {assigned_to.username} "
            f"by {assigned_by.username}"
        )
        
        return assignment
    
    @staticmethod
    @transaction.atomic
    def update_status(ticket, new_status, admin_user, notes="", request=None):
        """
        Update ticket status
        
        Args:
            ticket: SupportTicket object
            new_status: New status value
            admin_user: Admin user performing the update
            notes: Optional notes
            request: HTTP request object
            
        Returns:
            Updated SupportTicket object
        """
        old_status = ticket.status
        ticket.status = new_status
        
        # Set timestamps for resolved/closed
        if new_status == SupportTicket.STATUS_RESOLVED:
            ticket.resolved_at = timezone.now()
        elif new_status == SupportTicket.STATUS_CLOSED:
            ticket.closed_at = timezone.now()
        
        ticket.save()
        
        # Create audit log
        ip_address = get_user_ip(request) if request else None
        TicketAuditLog.objects.create(
            ticket=ticket,
            action='status_changed',
            performed_by=admin_user,
            notes=f"Status changed from {old_status} to {new_status}. {notes}",
            ip_address=ip_address
        )
        
        logger.info(
            f"Ticket {ticket.reference_number} status changed from {old_status} "
            f"to {new_status} by {admin_user.username}"
        )
        
        return ticket
    
    @staticmethod
    def get_user_context(user):
        """
        Get comprehensive user context for admin view
        Includes wallet, KYC, MGR, and goals data
        
        Args:
            user: User object
            
        Returns:
            Dictionary with user context
        """
        context = {
            'user': user,
            'wallet': None,
            'kyc_status': None,
            'active_mgr_rounds': [],
            'active_goals': [],
            'recent_transactions': [],
        }
        
        # Get wallet data
        try:
            from wallet.models import MainWallet
            from wallet.services import WalletService
            
            wallet = MainWallet.objects.filter(user=user).first()
            if wallet:
                summary = WalletService.get_wallet_summary(user)
                context['wallet'] = {
                    'balance': wallet.balance,
                    'available_balance': wallet.available_balance,
                    'locked_balance': wallet.locked_balance,
                    'status': wallet.status,
                    'total_deposited': summary.get('total_deposited', 0),
                    'total_withdrawn': summary.get('total_withdrawn', 0),
                }
        except Exception as e:
            logger.error(f"Error fetching wallet data: {str(e)}")
        
        # Get KYC status
        try:
            from user_dashboard.kyc_utils import get_kyc_status
            context['kyc_status'] = get_kyc_status(user)
        except Exception as e:
            logger.error(f"Error fetching KYC status: {str(e)}")
        
        # Get active MGR rounds
        try:
            from merry_go_round.models import RoundMembership
            memberships = RoundMembership.objects.filter(
                user=user,
                status='active'
            ).select_related('round')[:5]
            
            context['active_mgr_rounds'] = [
                {
                    'round_name': m.round.name,
                    'contribution_amount': m.round.contribution_amount,
                    'frequency': m.round.get_frequency_display(),
                }
                for m in memberships
            ]
        except Exception as e:
            logger.error(f"Error fetching MGR data: {str(e)}")
        
        # Get active goals
        try:
            from Goals.models import Goal
            goals = Goal.objects.filter(user=user, is_active='Yes')[:5]
            
            context['active_goals'] = [
                {
                    'name': g.name,
                    'balance': g.goal_balance,
                    'target': g.goal_amount,
                    'percentage': g.percentage(),
                }
                for g in goals
            ]
        except Exception as e:
            logger.error(f"Error fetching goals data: {str(e)}")
        
        # Get recent transactions
        try:
            from wallet.models import WalletTransaction
            transactions = WalletTransaction.objects.filter(
                wallet__user=user
            ).order_by('-created_at')[:5]
            
            context['recent_transactions'] = [
                {
                    'type': t.get_transaction_type_display(),
                    'amount': t.amount,
                    'status': t.status,
                    'date': t.created_at,
                    'description': t.description,
                }
                for t in transactions
            ]
        except Exception as e:
            logger.error(f"Error fetching transactions: {str(e)}")
        
        return context
    
    @staticmethod
    def mark_messages_as_read(ticket, user_type='user'):
        """
        Mark all unread messages as read for user or admin
        
        Args:
            ticket: SupportTicket object
            user_type: 'user' or 'admin'
        """
        if user_type == 'user':
            # Mark admin messages as read by user
            SupportMessage.objects.filter(
                ticket=ticket,
                sender_type=SupportMessage.SENDER_TYPE_ADMIN,
                read_by_user=False
            ).update(read_by_user=True)
            
            # Reset user unread count
            ticket.user_unread_count = 0
            ticket.save()
            
        else:  # admin
            # Mark user messages as read by admin
            SupportMessage.objects.filter(
                ticket=ticket,
                sender_type=SupportMessage.SENDER_TYPE_USER,
                read_by_admin=False
            ).update(read_by_admin=True)
            
            # Reset admin unread count
            ticket.admin_unread_count = 0
            ticket.save()


class NotificationService:
    """
    Service for sending notifications related to support tickets
    """
    
    @staticmethod
    def notify_user(user, title, body):
        """
        Send notification to user
        
        Args:
            user: User object
            title: Notification title
            body: Notification body
        """
        try:
            from notifications.models import UserNotificationHistory
            UserNotificationHistory.objects.create(
                user=user,
                notification_title=title,
                notification_body=body,
                purpose='support'
            )
            logger.info(f"Notification sent to user {user.username}: {title}")
        except Exception as e:
            logger.error(f"Failed to send notification to user: {str(e)}")
    
    @staticmethod
    def notify_admin(admin_user, title, body):
        """
        Send notification to admin
        
        Args:
            admin_user: Admin user object
            title: Notification title
            body: Notification body
        """
        try:
            from notifications.models import UserNotificationHistory
            UserNotificationHistory.objects.create(
                user=admin_user,
                notification_title=title,
                notification_body=body,
                purpose='support'
            )
            logger.info(f"Notification sent to admin {admin_user.username}: {title}")
        except Exception as e:
            logger.error(f"Failed to send notification to admin: {str(e)}")
    
    @staticmethod
    def send_ticket_created_notification(ticket):
        """
        Send notification when ticket is created
        """
        NotificationService.notify_user(
            ticket.user,
            'Support Ticket Created',
            f'Your support ticket {ticket.reference_number} has been created. '
            f'Our team will respond as soon as possible.'
        )
    
    @staticmethod
    def send_admin_reply_notification(ticket, admin_name):
        """
        Send notification when admin replies
        """
        NotificationService.notify_user(
            ticket.user,
            f'New Reply: {ticket.reference_number}',
            f'{admin_name} has replied to your ticket "{ticket.subject}". '
            f'Click to view the response.'
        )
    
    @staticmethod
    def send_ticket_resolved_notification(ticket):
        """
        Send notification when ticket is resolved
        """
        NotificationService.notify_user(
            ticket.user,
            f'Ticket Resolved: {ticket.reference_number}',
            f'Your support ticket "{ticket.subject}" has been marked as resolved. '
            f'If you need further assistance, you can reopen this ticket within 7 days.'
        )
    
    @staticmethod
    def send_ticket_closed_notification(ticket):
        """
        Send notification when ticket is closed
        """
        NotificationService.notify_user(
            ticket.user,
            f'Ticket Closed: {ticket.reference_number}',
            f'Your support ticket "{ticket.subject}" has been closed. '
            f'Thank you for using ChamaSpace support.'
        )