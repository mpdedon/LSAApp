# lsalms/templatetags/lsalms_extras.py
from django import template
from ..models import Lesson, Course

register = template.Library()

@register.simple_tag
def get_total_lesson_count(course):
    """ A custom template tag to safely count all lessons in a course. """
    if not isinstance(course, Course):
        return 0

    # If the check passes, proceed with the safe database query.
    return Lesson.objects.filter(module__course=course).count()

@register.filter
def class_name(value):
    """
    Returns the name of an object's class.
    Used in templates for dynamic titles, e.g., "Edit Module", "Create Lesson".
    """
    # Check if the value is a form instance, if so, get the model from Meta
    if hasattr(value, 'Meta') and hasattr(value.Meta, 'model'):
        return value.Meta.model.__name__
    # Otherwise, get the class name from the object instance itself
    return value.__class__.__name__