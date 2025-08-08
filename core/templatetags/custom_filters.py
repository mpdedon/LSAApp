# core/templatetags/custom_filters.py

from django import template
import collections.abc # Import for checking if an attribute is callable

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Allows accessing a dictionary key using a variable in a Django template.
    Returns None if the key doesn't exist.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter(name='get_attribute')
def get_attribute(obj, attr_name):
    """
    Allows accessing an object's attribute using a variable in a Django template.
    If the attribute is a method, it will be called.
    Returns None if the attribute doesn't exist.
    """
    if hasattr(obj, str(attr_name)):
        attribute = getattr(obj, str(attr_name))
        # Check if the attribute is a method (callable) and not a simple value
        if isinstance(attribute, collections.abc.Callable):
            # It's a method, so call it and return the result
            return attribute()
        else:
            # It's a regular attribute, return its value
            return attribute
    return None

# Keep your original dict_key for compatibility
@register.filter(name='dict_key')
def dict_key(dictionary, key):
    """Alias for 'get_item' to match your old template's filter name."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None