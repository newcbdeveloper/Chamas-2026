# custom_filters.py

from django import template
from datetime import datetime

register = template.Library()

@register.filter(name='format_date')
def format_date(value):
    if value is not None and isinstance(value, datetime):
        return value.strftime('%d/%m/%Y')
    return ''
