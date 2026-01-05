from django import template

register = template.Library()

@register.filter
def get_initials(name):
    """Extract initials from a full name"""
    if not name:
        return "??"
    
    name_parts = name.strip().split()
    
    if len(name_parts) >= 2:
        # If we have first and last name, take first letter of each
        return f"{name_parts[0][0].upper()}{name_parts[-1][0].upper()}"
    elif len(name_parts) == 1:
        # If we only have one name, take first two letters
        single_name = name_parts[0]
        if len(single_name) >= 2:
            return f"{single_name[0].upper()}{single_name[1].upper()}"
        else:
            return f"{single_name[0].upper()}?"
    else:
        return "??"