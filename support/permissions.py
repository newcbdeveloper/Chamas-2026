from django.core.exceptions import PermissionDenied
from functools import wraps


def can_view_all_tickets(user):
    """
    Check if user can view all support tickets
    
    Args:
        user: User object
        
    Returns:
        Boolean
    """
    return user.is_staff or user.is_superuser


def can_assign_tickets(user):
    """
    Check if user can assign tickets to other admins
    
    Args:
        user: User object
        
    Returns:
        Boolean
    """
    return user.is_staff or user.is_superuser


def can_respond_to_tickets(user):
    """
    Check if user can respond to support tickets
    
    Args:
        user: User object
        
    Returns:
        Boolean
    """
    return user.is_staff or user.is_superuser


def can_change_ticket_status(user):
    """
    Check if user can change ticket status
    
    Args:
        user: User object
        
    Returns:
        Boolean
    """
    return user.is_staff or user.is_superuser


def can_view_ticket(user, ticket):
    """
    Check if user can view specific ticket
    
    Args:
        user: User object
        ticket: SupportTicket object
        
    Returns:
        Boolean
    """
    # Users can view their own tickets
    if ticket.user == user:
        return True
    
    # Admins can view all tickets
    if user.is_staff or user.is_superuser:
        return True
    
    return False


def can_close_ticket(user, ticket):
    """
    Check if user can close a ticket
    Only admins can close tickets, users cannot
    
    Args:
        user: User object
        ticket: SupportTicket object
        
    Returns:
        Boolean
    """
    return user.is_staff or user.is_superuser


def can_reopen_ticket(user, ticket):
    """
    Check if user can reopen a closed ticket
    Users can reopen their own tickets within 7 days of closure
    
    Args:
        user: User object
        ticket: SupportTicket object
        
    Returns:
        Boolean
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Admins can always reopen
    if user.is_staff or user.is_superuser:
        return True
    
    # Users can reopen their own tickets within 7 days
    if ticket.user == user and ticket.is_closed:
        if ticket.closed_at:
            days_since_closed = (timezone.now() - ticket.closed_at).days
            return days_since_closed <= 7
    
    return False


def can_send_internal_notes(user):
    """
    Check if user can send internal notes (admin-only messages)
    
    Args:
        user: User object
        
    Returns:
        Boolean
    """
    return user.is_staff or user.is_superuser


# Decorators

def admin_required(function):
    """
    Decorator to require admin permissions
    """
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("You do not have permission to access this page.")
        return function(request, *args, **kwargs)
    return wrap


def ticket_owner_or_admin_required(function):
    """
    Decorator to require ticket ownership or admin permissions
    Ticket must be passed as 'ticket' in kwargs or retrieved by ticket_id
    """
    @wraps(function)
    def wrap(request, *args, **kwargs):
        from .models import SupportTicket
        
        # Try to get ticket from kwargs
        ticket = kwargs.get('ticket')
        
        # If not in kwargs, try to get by ticket_id
        if not ticket:
            ticket_id = kwargs.get('ticket_id')
            if ticket_id:
                try:
                    ticket = SupportTicket.objects.get(id=ticket_id)
                except SupportTicket.DoesNotExist:
                    raise PermissionDenied("Ticket not found.")
        
        # Check permissions
        if not can_view_ticket(request.user, ticket):
            raise PermissionDenied("You do not have permission to view this ticket.")
        
        # Add ticket to kwargs for the view
        kwargs['ticket'] = ticket
        
        return function(request, *args, **kwargs)
    return wrap


def can_assign_ticket_to_user(user):
    """
    Check if a user can be assigned tickets
    Only staff members can be assigned tickets
    
    Args:
        user: User object
        
    Returns:
        Boolean
    """
    return user.is_staff


def get_available_assignees():
    """
    Get list of users who can be assigned tickets
    
    Returns:
        QuerySet of User objects
    """
    from django.contrib.auth.models import User
    return User.objects.filter(is_staff=True, is_active=True).order_by('first_name', 'last_name')


def check_ticket_access(user, ticket):
    """
    Comprehensive access check for a ticket
    Raises PermissionDenied if no access
    
    Args:
        user: User object
        ticket: SupportTicket object
        
    Returns:
        Boolean or raises PermissionDenied
    """
    if not can_view_ticket(user, ticket):
        raise PermissionDenied(
            "You do not have permission to access this ticket. "
            "If you believe this is an error, please contact support."
        )
    return True


def is_ticket_admin(user):
    """
    Check if user is a ticket admin (can perform admin actions)
    
    Args:
        user: User object
        
    Returns:
        Boolean
    """
    # For now, any staff member is a ticket admin
    # You can expand this to check for specific groups/permissions
    return user.is_staff or user.is_superuser


def get_admin_users():
    """
    Get all users who can act as support admins
    
    Returns:
        QuerySet of User objects
    """
    from django.contrib.auth.models import User
    return User.objects.filter(
        is_staff=True,
        is_active=True
    ).order_by('first_name', 'last_name')