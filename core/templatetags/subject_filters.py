from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """Returns the value of the given key from a dictionary-like object."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None  # or raise an exception or return a fallback value
