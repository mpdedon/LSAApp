from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return 0  # Or another default value
    return dictionary.get(key, 0)