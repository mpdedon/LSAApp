# your_app/templatetags/assessment_filters.py
from django import template

register = template.Library()

@register.filter(name='percentage_of')
def percentage_of(value, total):
    """Calculates what percentage 'value' is of 'total'."""
    try:
        value = int(value)
        total = int(total)
        if total == 0:
            return 0
        return round((value / total) * 100)
    except (ValueError, TypeError):
        return 0