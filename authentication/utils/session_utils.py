"""
Session utility functions for ChamaSpace.
Handles session invalidation, security checks, and session management.
"""

from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth import logout


def invalidate_all_user_sessions(user, exclude_current=None):
    """
    Invalidate all sessions for a user.
    
    Args:
        user: User object
        exclude_current: Session key to exclude (current session)
    
    Usage:
        # Logout user from all devices
        invalidate_all_user_sessions(request.user)
        
        # Logout from all other devices (keep current)
        invalidate_all_user_sessions(request.user, request.session.session_key)
    """
    # Get all active sessions
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    
    user_sessions = []
    user_id_str = str(user.id)  # Convert once
    
    for session in sessions:
        try:
            data = session.get_decoded()
            session_user_id = data.get('_auth_user_id')
            
            # Check if this session belongs to the user
            if session_user_id == user_id_str:
                # Skip current session if specified
                if exclude_current and session.session_key == exclude_current:
                    continue
                user_sessions.append(session.session_key)
        except Exception:
            # Skip corrupted sessions
            continue
    
    # Delete all user sessions
    Session.objects.filter(session_key__in=user_sessions).delete()
    
    return len(user_sessions)

def invalidate_session_on_security_event(user, event_type='security_change'):
    """
    Mark all user sessions for invalidation on next request.
    
    Args:
        user: User object
        event_type: Type of security event (for logging)
    
    This sets a flag in all sessions that will be checked by middleware.
    """
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    
    count = 0
    for session in sessions:
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(user.id):
            # Set invalidation flag
            data['invalidate_session'] = True
            data['invalidation_reason'] = event_type
            session.session_data = session.encode(data)
            session.save()
            count += 1
    
    return count


def get_user_active_sessions(user):
    """
    Get all active sessions for a user with metadata.
    
    Returns list of session info dictionaries.
    Useful for "Active Sessions" UI feature.
    """
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    
    active_sessions = []
    for session in sessions:
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(user.id):
            session_info = {
                'session_key': session.session_key,
                'user_agent': data.get('user_agent', 'Unknown'),
                'ip_address': data.get('ip_address', 'Unknown'),
                'login_time': data.get('login_timestamp'),
                'last_activity': data.get('last_activity'),
                'expire_date': session.expire_date,
            }
            active_sessions.append(session_info)
    
    return active_sessions


def is_session_expired(request):
    """
    Check if current session has exceeded absolute timeout.
    
    Returns:
        True if session is expired, False otherwise
    """
    from django.conf import settings
    import time
    
    login_time = request.session.get('login_timestamp')
    if not login_time:
        return False
    
    # Get absolute session age (default 24 hours)
    max_age = getattr(settings, 'SESSION_COOKIE_AGE', 86400)
    
    current_time = time.time()
    session_age = current_time - login_time
    
    return session_age > max_age


def refresh_session_on_login(request, user):
    """
    Add session metadata when user logs in.
    Sets initial metadata and timestamps.
    
    Call this in your login view AFTER successful authentication.
    Note: Django's login() function already creates the session,
    so we just add our tracking metadata here.
    """
    import time
    
    # Get current timestamp
    current_time = time.time()
    
    # Set timestamps for tracking
    request.session['login_timestamp'] = current_time
    request.session['last_activity'] = current_time
    
    # Set device metadata
    request.session['user_agent'] = request.META.get('HTTP_USER_AGENT', 'Unknown')
    
    # Get IP address (considering proxy)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'Unknown')
    request.session['ip_address'] = ip
    
    # Mark metadata as stored
    request.session['session_metadata_stored'] = True
    
    # Save the session with new metadata
    request.session.save()


def create_logout_message(reason='idle_timeout'):
    """
    Create appropriate logout message based on reason.
    
    Args:
        reason: 'idle_timeout', 'absolute_expiry', 'security_change', 'manual'
    
    Returns:
        Message string
    """
    messages = {
        'idle_timeout': 'You were logged out due to inactivity to keep your account secure.',
        'absolute_expiry': 'Your session has expired. Please login again.',
        'security_change': 'Your session was ended for security reasons. Please login again.',
        'password_change': 'Your password was changed. Please login with your new password.',
        'phone_change': 'Your phone number was updated. Please login again.',
        'manual': 'You have been logged out successfully.',
        'logout_all': 'You have been logged out from all devices.',
    }
    
    return messages.get(reason, 'You have been logged out.')