from django import template

register = template.Library()

@register.filter
def attr(field, attr_name):
    """Get the value of an attribute of the field."""
    return getattr(field, attr_name, None)