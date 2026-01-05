import re
import os
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Max
from .models import SupportTicket
from django.db import transaction


def sanitize_message(message):
    """
    Sanitize user message to block sensitive information
    
    Args:
        message: String message from user
        
    Returns:
        Sanitized message or raises ValidationError
    """
    # Keywords to block (case-insensitive)
    blocked_keywords = [
    # Auth & access
    'pin',    'otp',    'password',
    'passwd',    'passcode',    'verification code',
    'auth code',    'authentication code',    '2fa',
    'backup code',    'recovery code',

    # Mobile money (Kenya-specific)
    'mpesa pin',    'm-pesa pin',
    'mpesa password',    'safaricom pin',
    'paybill pin',    'till pin',

    # Cards & banking
    'cvv',    'card number',
    'debit card',    'credit card',
    'expiry date',    'expiration date',
    'bank account',    'account number',
    'iban',    'swift',    'bic',

    # Crypto / system secrets
    'secret',    'secret key',
    'private key',    'api key',
    'access key',    'token',    'bearer',
    'jwt',    'session id',
    
]
    
    message_lower = message.lower()
    
    for keyword in blocked_keywords:
        if keyword in message_lower:
            raise ValidationError(
                f"⚠️ Please do not share sensitive information like {keyword.upper()}. "
                f"Our support team will NEVER ask for your PIN, password, or OTP."
            )
    
    # Check for patterns that look like PINs (4-6 digits)
    pin_pattern = re.compile(
            r'(pin|otp|code)[^\d]{0,10}(\d{4,6})',
            re.IGNORECASE
        )

    if pin_pattern.search(message):
        raise ValidationError(
            "⚠️ It looks like you may have entered a PIN or OTP. "
            "Please remove this for your security. We never need your PIN."
        )
    
    return message


def validate_file_upload(file):
    """
    Validate uploaded file
    
    Args:
        file: Uploaded file object
        
    Returns:
        True if valid, raises ValidationError otherwise
    """
    # Check file size (5MB limit)
    max_size = 5 * 1024 * 1024  # 5MB
    if file.size > max_size:
        raise ValidationError(
            f"File size too large. Maximum allowed size is 5MB. "
            f"Your file is {round(file.size / (1024 * 1024), 2)}MB."
        )
    
    # Check file extension
    allowed_extensions = [
        '.jpg', 
        '.jpeg', 
        '.png', 
        '.pdf', 
        '.txt',
        '.doc',
        '.docx',
    ]
    
    filename = file.name.lower()
    ext = os.path.splitext(filename)[1]
    
    if ext not in allowed_extensions:
        raise ValidationError(
            f"File type '{ext}' is not allowed. "
            f"Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Check for suspicious filenames
    suspicious_patterns = [
        '.exe',        '.bat',
        '.cmd',        '.sh',
        '.php',        '.js',
        '.html',        '.docm',   
        '.xlsm',          '.zip',    
        '.rar',        '.7z',

    ]
    
    for pattern in suspicious_patterns:
        if pattern in filename:
            raise ValidationError(
                "This file type is not allowed for security reasons."
            )
    
    return True


def generate_ticket_reference():
    """
    Generate unique ticket reference number
    Format: SUPP-YYYY-NNNNNN
    
    Returns:
        String reference number
    """
    
    
    year = timezone.now().year
    prefix = f"SUPP-{year}-"

    with transaction.atomic():
        last_ticket = (
            SupportTicket.objects
            .select_for_update()
            .filter(reference_number__startswith=prefix)
            .order_by('-reference_number')
            .first()
        )

        if last_ticket:
            last_num = int(last_ticket.reference_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1

        return f"{prefix}{str(new_num).zfill(6)}"

def get_user_ip(request):
    """
    Extract user IP address from request
    Handles proxies and load balancers
    
    Args:
        request: Django request object
        
    Returns:
        IP address string
    """
    # Check for X-Forwarded-For header (proxies)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    return ip


def get_priority_from_category(category):
    """
    Auto-detect priority based on ticket category
    
    Args:
        category: Ticket category string
        
    Returns:
        Priority string
    """
    high_priority_categories = [
        'suspicious',
        'withdrawals',
        'wallet',
    ]
    
    medium_priority_categories = [
        'deposits',
        'kyc',
        'mgr',
    ]
    
    if category in high_priority_categories:
        return 'high'
    elif category in medium_priority_categories:
        return 'medium'
    else:
        return 'low'


def format_time_ago(datetime_obj):
    """
    Format datetime as 'X time ago'
    
    Args:
        datetime_obj: datetime object
        
    Returns:
        Formatted string
    """
    if not datetime_obj:
        return "Never"
    
    now = timezone.now()
    diff = now - datetime_obj
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"


def detect_urgent_keywords(message):
    """
    Detect if message contains urgent keywords
    Auto-escalate priority if found
    
    Args:
        message: Message text
        
    Returns:
        Boolean indicating if urgent
    """
    urgent_keywords = [
    # Fraud / security
    'fraud',    'scam',    'hack',    'hacked',
    'account compromised',    'unauthorized',    'unknown login',
    'suspicious login',    'someone accessed',    'account takeover',

    # Money loss
    'stolen',    'money missing',    'funds missing',
    'lost money',    'money disappeared',    'wrong transaction',
    'sent by mistake',    'sent to wrong number',    'wrong recipient',

    # Mpesa / payments (Kenya)
    'mpesa issue',    'mpesa problem',    'mpesa not received',
    'debited but not credited',    'charged twice',
    'double charge',    'payment deducted',    'payment failed but deducted',

    # Urgency language
    'urgent',    'emergency',    'help immediately',
    'asap',    'now',    'immediately',    'please help',
]

    message_lower = message.lower()
    
    for keyword in urgent_keywords:
        if keyword in message_lower:
            return True
    
    return False


def clean_phone_number(phone):
    """
    Clean and format phone number
    
    Args:
        phone: Phone number string
        
    Returns:
        Cleaned phone number
    """
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', phone)
    
    # Handle Kenyan numbers
    if cleaned.startswith('254'):
        return '+' + cleaned
    elif cleaned.startswith('0'):
        return '+254' + cleaned[1:]
    else:
        return '+254' + cleaned


def truncate_text(text, max_length=100):
    """
    Truncate text to max length with ellipsis
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + '...'