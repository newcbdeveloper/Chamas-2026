"""
ChamaSpace Session Security Middleware
Handles idle timeout, session tracking, and security enforcement.
"""

import time
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to enforce idle timeout and track session metadata.
    
    Features:
    - Idle timeout (15 minutes default)
    - Track last activity timestamp
    - Store device/user-agent info
    - Automatic logout on timeout
    """
    
    # URLs that don't require session checks (login, signup, etc.)
    EXEMPT_URLS = [
        '/user/Login',
        '/user/signup',
        '/user/login-otp',
        '/user/login_token',
        '/user/forget_password',
        '/user/update_password',
        '/user/reset_password',
        '/user/verify_otp',
        '/static/',
        '/media/',
        '/admin/login/',
    ]
    
    def process_request(self, request):
        """
        Check session idle timeout and update activity timestamp.
        """
        # Skip checks for exempt URLs
        if any(request.path.startswith(url) for url in self.EXEMPT_URLS):
            return None
        
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return None
        
        # Get current timestamp
        current_time = time.time()
        
        # Get idle timeout from settings (default 15 minutes)
        idle_timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT', 900)
        
        # Get last activity time from session
        last_activity = request.session.get('last_activity')
        
        if last_activity:
            # Calculate idle time
            idle_time = current_time - last_activity
            
            # If idle time exceeds timeout, logout user
            if idle_time > idle_timeout:
                # Store redirect message before logout
                messages.warning(
                    request,
                    'You were logged out due to inactivity to keep your account secure.'
                )
                
                # Perform logout
                logout(request)
                
                # Redirect to login page
                return redirect('Login')
        
        # Update last activity timestamp
        request.session['last_activity'] = current_time
        
        # Store session metadata (first time only)
        if not request.session.get('session_metadata_stored'):
            self._store_session_metadata(request)
        
        return None
    
    def _store_session_metadata(self, request):
        """
        Store device and session metadata for security tracking.
        """
        # Store user agent
        request.session['user_agent'] = request.META.get('HTTP_USER_AGENT', 'Unknown')
        
        # Store IP address (considering proxy)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
        request.session['ip_address'] = ip_address
        
        # Store login timestamp
        request.session['login_timestamp'] = time.time()
        
        # Mark metadata as stored
        request.session['session_metadata_stored'] = True
        
        # Store session key for future invalidation tracking
        request.session['session_key'] = request.session.session_key


class SessionInvalidationMiddleware(MiddlewareMixin):
    """
    Middleware to check if session should be invalidated due to security events.
    
    Checks for:
    - Password changes
    - Phone number updates
    - Manual session invalidation flags
    """
    
    def process_request(self, request):
        """
        Check if session should be invalidated.
        """
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return None
        
        # Check if session invalidation flag is set
        should_invalidate = request.session.get('invalidate_session', False)
        
        if should_invalidate:
            request.session.pop('invalidate_session', None)
            
            messages.info(
                request,
                'Your session was ended for security reasons. Please login again.'
            )
            
            logout(request)
            return redirect('Login')
        
        # Get user's profile
        try:
            profile = request.user.profile
            
            # Check if password was changed after this session started
            login_timestamp = request.session.get('login_timestamp')
            
            if login_timestamp and hasattr(profile, 'password_changed_at') and profile.password_changed_at:
                # If password was changed after this session started, invalidate
                if profile.password_changed_at.timestamp() > login_timestamp:
                    messages.info(
                        request,
                        'Your password was changed. Please login with your new password.'
                    )
                    logout(request)
                    return redirect('Login')
            
        except Exception:
            pass
        
        return None