# myapp/templatetags/form_extras.py

from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    """
    Add a class to a form field.
    Usage: {{ form.field|add_class:"css-class" }}
    """
    return field.as_widget(attrs={'class': css_class})
