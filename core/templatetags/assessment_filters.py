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
    
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Allows dictionary lookup in templates using a variable key."""
    return dictionary.get(key)

@register.filter
def filter_pending_grade(submission_values):
    """
    Filters a list/queryset of submission objects (or dicts) and returns
    only those that require manual review and are not yet graded.
    """
    if not submission_values:
        return []
        
    pending = []
    for sub in submission_values:
        # Check if it's an object or a dictionary
        if hasattr(sub, 'requires_manual_review'): # Object
            if sub.requires_manual_review and not sub.is_graded:
                pending.append(sub)
        elif isinstance(sub, dict): # Dictionary
            if sub.get('requires_manual_review') and not sub.get('is_graded'):
                pending.append(sub)
    return pending