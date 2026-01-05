
"""
Template tags and filters for KYC verification status.

Usage in templates:
    {% load kyc_tags %}
    
    {% if user|is_kyc_verified %}
        <button>Withdraw Funds</button>
    {% else %}
        <button disabled>Verify Account First</button>
    {% endif %}
"""

from django import template
from django.contrib.auth.models import User

register = template.Library()


@register.filter
def is_kyc_verified(user):
    """
    Check if a user is KYC verified.
    
    Usage:
        {% if user|is_kyc_verified %}
            Verified content here
        {% endif %}
    
    Args:
        user: Django User instance
    
    Returns:
        bool: True if verified, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        from user_dashboard.kyc_utils import is_kyc_verified as check_verified
        return check_verified(user)
    except Exception:
        return False


@register.filter
def kyc_status(user):
    """
    Get the KYC verification status for a user.
    
    Usage:
        {{ user|kyc_status }}
        
    Returns: 'not_started', 'pending', 'approved', 'rejected', or 'resubmission_required'
    
    Args:
        user: Django User instance
    
    Returns:
        str: Status string
    """
    if not user or not user.is_authenticated:
        return 'not_started'
    
    try:
        from user_dashboard.kyc_utils import get_kyc_profile
        kyc_profile = get_kyc_profile(user)
        return kyc_profile.verification_status
    except Exception:
        return 'not_started'


@register.filter
def kyc_status_badge(user):
    """
    Get a colored badge HTML for KYC status.
    
    Usage:
        {{ user|kyc_status_badge|safe }}
    
    Args:
        user: Django User instance
    
    Returns:
        str: HTML string with styled badge
    """
    if not user or not user.is_authenticated:
        return '<span class="badge bg-secondary">Not Verified</span>'
    
    try:
        from user_dashboard.kyc_utils import get_kyc_profile
        kyc_profile = get_kyc_profile(user)
        
        status_map = {
            'not_started': {
                'class': 'bg-warning',
                'icon': 'fas fa-exclamation-circle',
                'text': 'Not Verified'
            },
            'pending': {
                'class': 'bg-info',
                'icon': 'fas fa-clock',
                'text': 'Under Review'
            },
            'approved': {
                'class': 'bg-success',
                'icon': 'fas fa-check-circle',
                'text': 'Verified'
            },
            'rejected': {
                'class': 'bg-danger',
                'icon': 'fas fa-times-circle',
                'text': 'Rejected'
            },
            'resubmission_required': {
                'class': 'bg-warning',
                'icon': 'fas fa-redo',
                'text': 'Resubmit Required'
            }
        }
        
        status_info = status_map.get(
            kyc_profile.verification_status,
            status_map['not_started']
        )
        
        return (
            f'<span class="badge {status_info["class"]}">'
            f'<i class="{status_info["icon"]} me-1"></i>'
            f'{status_info["text"]}'
            f'</span>'
        )
    except Exception:
        return '<span class="badge bg-secondary">Unknown</span>'


@register.simple_tag
def can_withdraw(user):
    """
    Check if user can withdraw funds.
    
    Usage:
        {% can_withdraw user as can_do %}
        {% if can_do %}
            <a href="...">Withdraw</a>
        {% endif %}
    
    Args:
        user: Django User instance
    
    Returns:
        bool: True if can withdraw, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        from user_dashboard.kyc_utils import can_withdraw_funds
        can_do, _ = can_withdraw_funds(user)
        return can_do
    except Exception:
        return False


@register.simple_tag
def can_create_goal(user):
    """
    Check if user can create savings goals.
    
    Usage:
        {% can_create_goal user as can_do %}
        {% if can_do %}
            <a href="...">Create Goal</a>
        {% endif %}
    
    Args:
        user: Django User instance
    
    Returns:
        bool: True if can create goals, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        from user_dashboard.kyc_utils import can_create_goal as check_can_create
        can_do, _ = check_can_create(user)
        return can_do
    except Exception:
        return False


@register.simple_tag
def can_request_loan(user):
    """
    Check if user can request loans.
    
    Usage:
        {% can_request_loan user as can_do %}
        {% if can_do %}
            <a href="...">Request Loan</a>
        {% endif %}
    
    Args:
        user: Django User instance
    
    Returns:
        bool: True if can request loans, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        from user_dashboard.kyc_utils import can_request_loan as check_can_request
        can_do, _ = check_can_request(user)
        return can_do
    except Exception:
        return False


@register.simple_tag
def can_join_mgr(user):
    """
    Check if user can join merry-go-rounds.
    
    Usage:
        {% can_join_mgr user as can_do %}
        {% if can_do %}
            <a href="...">Join Round</a>
        {% endif %}
    
    Args:
        user: Django User instance
    
    Returns:
        bool: True if can join MGR, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        from user_dashboard.kyc_utils import can_join_mgr as check_can_join
        can_do, _ = check_can_join(user)
        return can_do
    except Exception:
        return False


@register.inclusion_tag('user_dashboard/kyc_status_widget.html', takes_context=True)
def kyc_status_widget(context):
    """
    Render a KYC status widget.
    
    Usage in template:
        {% load kyc_tags %}
        {% kyc_status_widget %}
    
    This will render a small widget showing KYC status with appropriate actions.
    
    Args:
        context: Template context
    
    Returns:
        dict: Context for the widget template
    """
    user = context.get('request').user if 'request' in context else None
    
    if not user or not user.is_authenticated:
        return {'show_widget': False}
    
    try:
        from user_dashboard.kyc_utils import get_kyc_status, format_kyc_status_message
        
        status_info = get_kyc_status(user)
        status_message = format_kyc_status_message(status_info['status'])
        
        return {
            'show_widget': True,
            'user': user,
            'status_info': status_info,
            'status_message': status_message,
        }
    except Exception:
        return {'show_widget': False}


# Optional: Custom template tag for checking multiple permissions at once
@register.simple_tag
def kyc_permissions(user):
    """
    Get all KYC-related permissions for a user.
    
    Usage:
        {% kyc_permissions user as perms %}
        {% if perms.can_withdraw %}
            Withdraw button
        {% endif %}
    
    Args:
        user: Django User instance
    
    Returns:
        dict: Dictionary of permission booleans
    """
    if not user or not user.is_authenticated:
        return {
            'is_verified': False,
            'can_withdraw': False,
            'can_deposit': True,  # Always allow deposits
            'can_create_goal': False,
            'can_request_loan': False,
            'can_grant_loan': False,
            'can_join_mgr': False,
        }
    
    try:
        from user_dashboard.kyc_utils import (
            is_kyc_verified,
            can_withdraw_funds,
            can_deposit_funds,
            can_create_goal as check_goal,
            can_request_loan as check_request,
            can_grant_loan as check_grant,
            can_join_mgr as check_mgr,
        )
        
        return {
            'is_verified': is_kyc_verified(user),
            'can_withdraw': can_withdraw_funds(user)[0],
            'can_deposit': can_deposit_funds(user)[0],
            'can_create_goal': check_goal(user)[0],
            'can_request_loan': check_request(user)[0],
            'can_grant_loan': check_grant(user)[0],
            'can_join_mgr': check_mgr(user)[0],
        }
    except Exception:
        return {
            'is_verified': False,
            'can_withdraw': False,
            'can_deposit': True,
            'can_create_goal': False,
            'can_request_loan': False,
            'can_grant_loan': False,
            'can_join_mgr': False,
        }