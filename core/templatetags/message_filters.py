# core/templatetags/message_filter.py
from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
   
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None 

@register.filter(name='get_iterable_item')
def get_iterable_item(dictionary, key):
   
    if isinstance(dictionary, dict):
        # Return the item if it's a list/queryset, otherwise return empty list
        value = dictionary.get(key)
        # Check if the value is iterable but not a string (as looping over strings is usually not intended here)
        if hasattr(value, '__iter__') and not isinstance(value, str):
            return value
    return [] 