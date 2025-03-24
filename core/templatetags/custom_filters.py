from django import template

register = template.Library()

@register.filter
def dict_key(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, None)
    return None
