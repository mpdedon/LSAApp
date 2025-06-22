# your_app/templatetags/custom_string_filters.py

from django import template

register = template.Library()

@register.filter(name='split')
def split_string(value, arg):
    """
    Splits a string by the given argument.
    Usage: {{ some_string|split:"," }}
    """
    if isinstance(value, str):
        return [item.strip() for item in value.split(arg)] # Added strip() for each item
    return value # Return original value if not a string or if split fails

@register.filter(name='strip_filter') # You also used this
def strip_value(value):
    """
    Strips whitespace from a string.
    Usage: {{ some_string|strip_filter }}
    """
    if isinstance(value, str):
        return value.strip()
    return value