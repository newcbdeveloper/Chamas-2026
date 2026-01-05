
"""
Utilities for KYC verification and enforcement.
These functions should be used throughout the app to check user verification status.
"""

from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from .models import KYCProfile


def get_kyc_profile(user):
    """
    Safely get or create KYC profile for a user.
    
    Args:
        user: Django User instance
    
    Returns:
        KYCProfile instance
    """
    kyc_profile, created = KYCProfile.objects.get_or_create(
        user=user,
        defaults={
            'declared_national_id': getattr(user, 'username', 'unknown')
        }
    )
    
    # Sync declared ID from Profile if it exists and KYC is new
    if created:
        try:
            from authentication.models import Profile
            profile = Profile.objects.filter(owner=user).first()
            if profile and profile.NIC_No:
                kyc_profile.declared_national_id = profile.NIC_No
                kyc_profile.save()
        except Exception:
            pass
    
    return kyc_profile


def is_kyc_verified(user):
    """
    Check if user has completed and been approved for KYC.
    
    Args:
        user: Django User instance
    
    Returns:
        bool: True if verified, False otherwise
    """
    try:
        kyc_profile = get_kyc_profile(user)
        return kyc_profile.is_verified
    except Exception:
        return False


def get_kyc_status(user):
    """
    Get detailed KYC status for a user.
    
    Args:
        user: Django User instance
    
    Returns:
        dict with status information
    """
    try:
        kyc_profile = get_kyc_profile(user)
        return {
            'status': kyc_profile.verification_status,
            'is_verified': kyc_profile.is_verified,
            'can_submit': kyc_profile.can_submit,
            'needs_correction': kyc_profile.needs_correction,
            'submitted_at': kyc_profile.submitted_at,
            'approved_at': kyc_profile.approved_at,
            'rejection_reason': kyc_profile.rejection_reason,
        }
    except Exception as e:
        return {
            'status': 'error',
            'is_verified': False,
            'can_submit': False,
            'error': str(e)
        }


def require_kyc_verification(
    redirect_url='user_dashboard:kyc:dashboard',
    message='Please complete KYC verification to access this feature.'
):
    """
    Decorator to require KYC verification for a view.
    
    USE THIS DECORATOR FOR:
    - Wallet withdrawals (wallet app)
    - Setting up Wekeza goals (goals app)
    - Requesting loans (Kopeshana app)
    - Granting loans (Kopeshana app)
    - Joining merry-go-round (merry_go_round app)
    
    DO NOT USE FOR:
    - Wallet deposits (allow unverified users to deposit)
    - Viewing dashboards
    - Profile settings
    
    Usage:
        @require_kyc_verification()
        def withdraw_funds(request):
            # Only verified users can access this
            pass
        
        # With custom message
        @require_kyc_verification(
            message='You must verify your account to join a merry-go-round'
        )
        def join_mgr(request):
            pass
    
    Args:
        redirect_url: Where to redirect unverified users
        message: Custom message to show unverified users
    
    Returns:
        Decorated function
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('Login')
            
            if not is_kyc_verified(request.user):
                messages.warning(request, message)
                return redirect(redirect_url)
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def can_withdraw_funds(user):
    """
    Check if user can withdraw funds from wallet (requires KYC).
    
    USE IN: wallet app - withdrawal views
    
    Args:
        user: Django User instance
    
    Returns:
        tuple: (bool, str) - (can_withdraw, reason_if_not)
    """
    if not is_kyc_verified(user):
        return False, "KYC verification required to withdraw funds. This helps us protect your money and comply with financial regulations."
    
    return True, ""


def can_deposit_funds(user):
    """
    Check if user can deposit funds (NO KYC required - allow deposits).
    
    USE IN: wallet app - deposit views
    NOTE: Deposits are ALLOWED without KYC to encourage user engagement.
    
    Args:
        user: Django User instance
    
    Returns:
        tuple: (bool, str) - (can_deposit, reason_if_not)
    """
    # IMPORTANT: We allow deposits WITHOUT KYC verification
    # This encourages users to add funds before completing verification
    return True, ""


def can_create_goal(user):
    """
    Check if user can create Wekeza savings goals (requires KYC).
    
    USE IN: goals app - create goal views
    
    Args:
        user: Django User instance
    
    Returns:
        tuple: (bool, str) - (can_create, reason_if_not)
    """
    if not is_kyc_verified(user):
        return False, "KYC verification required to create savings goals. Verify your account to start saving towards your dreams!"
    
    return True, ""


def can_request_loan(user):
    """
    Check if user can request a loan (requires KYC).
    
    USE IN: Kopeshana app - loan request views
    
    Args:
        user: Django User instance
    
    Returns:
        tuple: (bool, str) - (can_request, reason_if_not)
    """
    if not is_kyc_verified(user):
        return False, "KYC verification required to request loans. This protects both lenders and borrowers in our community."
    
    return True, ""


def can_grant_loan(user):
    """
    Check if user can grant/lend money (requires KYC).
    
    USE IN: Kopeshana app - grant loan views
    
    Args:
        user: Django User instance
    
    Returns:
        tuple: (bool, str) - (can_grant, reason_if_not)
    """
    if not is_kyc_verified(user):
        return False, "KYC verification required to lend money. This ensures all lenders are verified members of our community."
    
    return True, ""


def can_join_mgr(user):
    """
    Check if user can join a merry-go-round (requires KYC).
    
    USE IN: merry_go_round app - join round views
    
    Args:
        user: Django User instance
    
    Returns:
        tuple: (bool, str) - (can_join, reason_if_not)
    """
    if not is_kyc_verified(user):
        return False, "KYC verification required to join a merry-go-round. This protects all members and ensures accountability."
    
    return True, ""


def can_be_chama_admin(user):
    """
    Check if user can be a chama admin (requires KYC).
    
    USE IN: chamas app - admin assignment views
    
    Args:
        user: Django User instance
    
    Returns:
        tuple: (bool, str) - (can_be_admin, reason_if_not)
    """
    if not is_kyc_verified(user):
        return False, "KYC verification required to manage chama activities. This ensures accountability for financial management."
    
    return True, ""


def get_verification_requirements():
    """
    Get list of what's required for KYC verification.
    
    Returns:
        dict with requirements
    """
    return {
        'required_documents': [
            {
                'name': 'National ID or Passport',
                'description': 'Clear photo of front and back (front only for passport)',
                'required': True
            },
            {
                'name': 'Live Selfie',
                'description': 'Recent selfie taken with your camera',
                'required': True
            }
        ],
        'requirements': [
            'Documents must be valid and not expired',
            'Photos must be clear and readable',
            'Selfie must match ID photo',
            'ID number must be visible and legible',
            'All information must be accurate'
        ],
        'processing_time': '1-2 business days',
        'restrictions_until_verified': [
            'Cannot withdraw funds from wallet',
            'Cannot create savings goals',
            'Cannot request or grant loans',
            'Cannot join merry-go-round groups',
            'Cannot be a chama administrator'
        ]
    }


def log_kyc_action(kyc_profile, action, user=None, notes='', ip_address=None):
    """
    Create an audit log entry for a KYC action.
    
    Args:
        kyc_profile: KYCProfile instance
        action: Action type (see KYCAuditLog.ACTION_CHOICES)
        user: User performing the action
        notes: Additional notes
        ip_address: IP address of request
    """
    from .models import KYCAuditLog
    
    KYCAuditLog.objects.create(
        kyc_profile=kyc_profile,
        action=action,
        performed_by=user,
        notes=notes,
        ip_address=ip_address
    )


def get_client_ip(request):
    """
    Get client IP address from request.
    
    Args:
        request: Django request object
    
    Returns:
        str: IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def validate_id_number(id_number, id_type='national_id'):
    """
    Basic validation for ID numbers.
    
    Args:
        id_number: ID number to validate
        id_type: Type of ID ('national_id' or 'passport')
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not id_number:
        return False, "ID number is required"
    
    id_number = str(id_number).strip()
    
    if id_type == 'national_id':
        # Kenyan National ID is typically 7-8 digits
        if not id_number.isdigit():
            return False, "National ID should contain only numbers"
        
        if len(id_number) < 7 or len(id_number) > 8:
            return False, "National ID should be 7-8 digits"
    
    elif id_type == 'passport':
        # Passport numbers are alphanumeric
        if len(id_number) < 6:
            return False, "Passport number too short"
        
        if not id_number.isalnum():
            return False, "Passport number should be alphanumeric"
    
    return True, ""


def check_duplicate_verified_id(id_number, exclude_user_id=None):
    """
    Check if an ID number is already verified for another user.
    
    Args:
        id_number: ID number to check
        exclude_user_id: User ID to exclude from check (current user)
    
    Returns:
        tuple: (is_duplicate, existing_user_id)
    """
    query = KYCProfile.objects.filter(
        verified_national_id=id_number,
        verification_status=KYCProfile.STATUS_APPROVED
    )
    
    if exclude_user_id:
        query = query.exclude(user_id=exclude_user_id)
    
    existing = query.first()
    if existing:
        return True, existing.user_id
    
    return False, None


def format_kyc_status_message(status):
    """
    Get user-friendly message for KYC status.
    
    Args:
        status: KYC status string
    
    Returns:
        dict with title and message
    """
    messages = {
        'not_started': {
            'title': 'Verification Not Started',
            'message': 'Complete your KYC verification to unlock all features including withdrawals, loans, and merry-go-rounds.',
            'action': 'Start Verification',
            'color': 'warning'
        },
        'pending': {
            'title': 'Verification Pending',
            'message': 'Your documents are being reviewed. This usually takes 1-2 business days.',
            'action': None,
            'color': 'info'
        },
        'approved': {
            'title': 'Verified',
            'message': 'Your account is fully verified. You can access all features.',
            'action': None,
            'color': 'success'
        },
        'rejected': {
            'title': 'Verification Rejected',
            'message': 'Please review the feedback and resubmit your documents.',
            'action': 'Resubmit Documents',
            'color': 'danger'
        },
        'resubmission_required': {
            'title': 'Resubmission Required',
            'message': 'Please review the feedback and resubmit your documents.',
            'action': 'Resubmit Documents',
            'color': 'warning'
        }
    }
    
    return messages.get(status, {
        'title': 'Unknown Status',
        'message': 'Please contact support.',
        'action': None,
        'color': 'secondary'
    })