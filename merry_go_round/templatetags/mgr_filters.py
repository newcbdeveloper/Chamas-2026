
from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def get_accurate_interest(round_obj, member_contributions=None):
    """
    Template filter to get accurate projected interest after tax
    Usage: {{ round|get_accurate_interest }}
    """
    if not member_contributions:
        total_cycles = round_obj.calculate_total_cycles()
        member_contributions = round_obj.contribution_amount * total_cycles
    
    return round_obj.get_accurate_projected_interest_after_tax(member_contributions)


@register.filter
def format_percentage(value):
    """Format decimal as percentage"""
    try:
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return "0.0%"


@register.filter
def days_to_weeks(days):
    """Convert days to weeks"""
    try:
        return int(days) // 7
    except (ValueError, TypeError):
        return 0