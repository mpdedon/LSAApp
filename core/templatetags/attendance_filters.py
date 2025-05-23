# your_app/templatetags/attendance_filters.py
from django import template
from datetime import date as date_obj

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter(name='get_item_date')
def get_item_date(student_date_dict, date_key_obj):
    """
    Looks up a status in a dictionary like: {student_id: {'YYYY-MM-DD': 'status'}}
    The date_key_obj is expected to be a Python date object.
    """
    if not isinstance(student_date_dict, dict):
        return None
    if isinstance(date_key_obj, date_obj):
        date_str_key = date_key_obj.strftime('%Y-%m-%d')
        return student_date_dict.get(date_str_key)
    return None # Or handle if date_key_obj is already a string

@register.filter(name='percentage_of')
def percentage_of(value, total):
    if total is None or total == 0:
        return 0
    if value is None:
        value = 0
    try:
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0