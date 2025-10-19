# lsalms/templatetags/lsalms_extras.py
from django import template
from django.utils.safestring import mark_safe
import re
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



@register.filter(name='youtube_embed_url')
def youtube_embed_url(value):
    """
    Converts a YouTube 'watch' URL to an 'embed' URL.
    Example: https://www.youtube.com/watch?v=dQw4w9WgXcQ -> https://www.youtube.com/embed/dQw4w9WgXcQ
    """
    if "youtube.com/watch?v=" in value:
        # Use regex to find the video ID for robustness
        match = re.search(r"v=([^&]+)", value)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/embed/{video_id}"
    # If it's already an embed link or not a youtube link, return it as is.
    return value


@register.filter
def in_set(value, arg):
    """Checks if a value is present in a set."""
    return value in arg