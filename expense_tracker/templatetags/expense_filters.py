from django import template
from decimal import Decimal
from datetime import datetime, timedelta

register = template.Library()


@register.filter
def currency(value, symbol='KSh'):
    """
    Format a number as currency
    Usage: {{ amount|currency }} or {{ amount|currency:"USD" }}
    """
    try:
        value = Decimal(str(value))
        return f"{symbol} {value:,.2f}"
    except (ValueError, TypeError):
        return f"{symbol} 0.00"


@register.filter
def abs_value(value):
    """
    Return absolute value of a number
    Usage: {{ -100|abs_value }}
    """
    try:
        return abs(Decimal(str(value)))
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage(value, total):
    """
    Calculate percentage
    Usage: {{ part|percentage:total }}
    """
    try:
        value = Decimal(str(value))
        total = Decimal(str(total))
        if total == 0:
            return 0
        return round((value / total) * 100, 1)
    except (ValueError, TypeError):
        return 0


@register.filter
def sign_prefix(value, transaction_type):
    """
    Add + or - prefix based on transaction type
    Usage: {{ amount|sign_prefix:type }}
    """
    try:
        value = Decimal(str(value))
        prefix = '+' if transaction_type == 'income' else '-'
        return f"{prefix} KSh {value:,.2f}"
    except (ValueError, TypeError):
        return "KSh 0.00"


@register.filter
def budget_status(percentage):
    """
    Return budget status class based on percentage
    Usage: {{ percentage|budget_status }}
    Returns: 'success', 'warning', or 'danger'
    """
    try:
        percentage = float(percentage)
        if percentage < 50:
            return 'success'
        elif percentage < 80:
            return 'warning'
        else:
            return 'danger'
    except (ValueError, TypeError):
        return 'secondary'


@register.filter
def transaction_color(transaction_type):
    """
    Return color class based on transaction type
    Usage: {{ type|transaction_color }}
    """
    return 'text-success' if transaction_type == 'income' else 'text-danger'


@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary
    Usage: {{ my_dict|get_item:key }}
    """
    if dictionary and key:
        return dictionary.get(key)
    return None


@register.filter
def multiply(value, arg):
    """
    Multiply value by argument
    Usage: {{ value|multiply:2 }}
    """
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def budget_progress_width(spent, total):
    """
    Calculate progress bar width percentage (max 100%)
    Usage: {% budget_progress_width spent_amount total_amount %}
    """
    try:
        spent = Decimal(str(spent))
        total = Decimal(str(total))
        if total == 0:
            return 0
        percentage = (spent / total) * 100
        return min(percentage, 100)
    except (ValueError, TypeError):
        return 0


@register.filter
def format_change(value):
    """
    Format percentage change with + or - sign
    Usage: {{ change|format_change }}
    """
    try:
        value = float(value)
        sign = '+' if value > 0 else ''
        return f"{sign}{value:.1f}%"
    except (ValueError, TypeError):
        return "0.0%"


@register.filter
def trend_icon(value):
    """
    Return trend icon based on value
    Usage: {{ change|trend_icon }}
    """
    try:
        value = float(value)
        if value > 0:
            return '📈'  # Increasing
        elif value < 0:
            return '📉'  # Decreasing
        else:
            return '➡️'  # Stable
    except (ValueError, TypeError):
        return '➡️'


@register.filter
def month_name(month_number):
    """
    Convert month number to name
    Usage: {{ 1|month_name }}
    Returns: January, February, etc.
    """
    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    try:
        index = int(month_number) - 1
        if 0 <= index < 12:
            return months[index]
    except (ValueError, TypeError):
        pass
    return ''


@register.filter
def date_add_days(value, days):
    """
    Add days to a date
    Usage: {{ my_date|date_add_days:7 }}
    """
    try:
        if isinstance(value, str):
            value = datetime.strptime(value, '%Y-%m-%d').date()
        return value + timedelta(days=int(days))
    except (ValueError, TypeError):
        return value


@register.filter
def date_subtract_days(value, days):
    """
    Subtract days from a date
    Usage: {{ my_date|date_subtract_days:7 }}
    """
    try:
        if isinstance(value, str):
            value = datetime.strptime(value, '%Y-%m-%d').date()
        return value - timedelta(days=int(days))
    except (ValueError, TypeError):
        return value


@register.filter
def format_number(value):
    """
    Format number with thousands separator
    Usage: {{ 1000000|format_number }}
    Returns: 1,000,000
    """
    try:
        return f"{float(value):,.0f}"
    except (ValueError, TypeError):
        return value


@register.filter
def compact_number(value):
    """
    Format large numbers in compact form (1K, 1M, etc.)
    Usage: {{ 1500|compact_number }}
    Returns: 1.5K
    """
    try:
        num = float(value)
        if num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}K"
        else:
            return f"{num:.0f}"
    except (ValueError, TypeError):
        return value


@register.filter
def status_badge_color(status):
    """
    Return Bootstrap badge color based on status
    Usage: {{ status|status_badge_color }}
    """
    status_colors = {
        'active': 'success',
        'inactive': 'secondary',
        'pending': 'warning',
        'overdue': 'danger',
        'completed': 'info',
    }
    return status_colors.get(status.lower() if status else '', 'secondary')


@register.filter
def pluralize_count(count, singular_plural):
    """
    Pluralize based on count
    Usage: {{ count|pluralize_count:"transaction,transactions" }}
    """
    try:
        count = int(count)
        singular, plural = singular_plural.split(',')
        return singular if count == 1 else plural
    except (ValueError, TypeError):
        return singular_plural


@register.simple_tag
def calculate_percentage(part, total):
    """
    Calculate percentage with proper formatting
    Usage: {% calculate_percentage 50 200 %}
    Returns: 25.0
    """
    try:
        part = Decimal(str(part))
        total = Decimal(str(total))
        if total == 0:
            return 0
        return round((part / total) * 100, 1)
    except (ValueError, TypeError):
        return 0


@register.filter
def div(value, arg):
    """
    Divide value by argument
    Usage: {{ 100|div:2 }}
    Returns: 50
    """
    try:
        return Decimal(str(value)) / Decimal(str(arg))
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def add_decimal(value, arg):
    """
    Add two decimal values
    Usage: {{ amount1|add_decimal:amount2 }}
    """
    try:
        return Decimal(str(value)) + Decimal(str(arg))
    except (ValueError, TypeError):
        return value


@register.filter
def subtract_decimal(value, arg):
    """
    Subtract two decimal values
    Usage: {{ amount1|subtract_decimal:amount2 }}
    """
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except (ValueError, TypeError):
        return value


@register.filter
def format_time_ago(date_value):
    """
    Format date as time ago (e.g., "2 hours ago")
    Usage: {{ date|format_time_ago }}
    """
    try:
        from django.utils import timezone
        
        if isinstance(date_value, str):
            date_value = datetime.fromisoformat(date_value)
        
        now = timezone.now()
        if date_value.tzinfo is None:
            date_value = timezone.make_aware(date_value)
        
        diff = now - date_value
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif seconds < 31536000:
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(seconds / 31536000)
            return f"{years} year{'s' if years != 1 else ''} ago"
    except:
        return str(date_value)


@register.filter
def is_positive(value):
    """
    Check if value is positive
    Usage: {% if amount|is_positive %}...{% endif %}
    """
    try:
        return Decimal(str(value)) > 0
    except (ValueError, TypeError):
        return False


@register.filter
def is_negative(value):
    """
    Check if value is negative
    Usage: {% if amount|is_negative %}...{% endif %}
    """
    try:
        return Decimal(str(value)) < 0
    except (ValueError, TypeError):
        return False


@register.simple_tag
def spending_rate(expenses, income):
    """
    Calculate spending rate as percentage of income
    Usage: {% spending_rate total_expenses total_income %}
    """
    try:
        expenses = Decimal(str(expenses))
        income = Decimal(str(income))
        if income == 0:
            return 0
        rate = (expenses / income) * 100
        return round(rate, 1)
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def savings_rate(expenses, income):
    """
    Calculate savings rate as percentage of income
    Usage: {% savings_rate total_expenses total_income %}
    """
    try:
        expenses = Decimal(str(expenses))
        income = Decimal(str(income))
        if income == 0:
            return 0
        savings = income - expenses
        rate = (savings / income) * 100
        return round(rate, 1)
    except (ValueError, TypeError):
        return 0