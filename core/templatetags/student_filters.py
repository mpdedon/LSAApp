# core/templatetags/student_filters.py

from django import template
from django.urls import reverse, NoReverseMatch
from datetime import datetime
import pytz

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

def create_task_dict(item, task_type):
    """Helper function to create a consistent dictionary for any task object."""
    submit_url = '#' # Default fallback URL
    try:
        if task_type == 'assignment':
            submit_url = reverse('submit_assignment', kwargs={'assignment_id': item.id})
        elif task_type == 'assessment':
            submit_url = reverse('submit_assessment', kwargs={'assessment_id': item.id})
        elif task_type == 'exam':
            submit_url = reverse('submit_exam', kwargs={'exam_id': item.id})
    except NoReverseMatch:
        print(f"Warning: URL for {task_type} with ID {item.id} not found.")

    return {
        'id': item.id,
        'title': item.title,
        'subject': item.subject,
        'due_date': item.due_date,
        'has_submitted': item.has_submitted, # Pass this from view if calculated
        'type': task_type,
        'submit_url': submit_url,
    }

@register.filter
def add_list(list1, list2):
    """Merges two lists of task objects into a single list of dictionaries."""
    # Ensure list1 is a list, not a queryset, if it's the first call
    if not isinstance(list1, list):
        list1 = []

    if not list2:
        return list1

    task_type = 'unknown'
    # Infer type based on the model name of the first item in the list
    model_name = list2.model.__name__.lower()
    if 'assignment' in model_name:
        task_type = 'assignment'
    elif 'assessment' in model_name:
        task_type = 'assessment'
    elif 'exam' in model_name:
        task_type = 'exam'

    for item in list2:
        # Pre-calculate has_submitted status in the view for efficiency
        # Here we just check if it was passed, a bit less efficient
        # has_submitted = # This needs to be passed from the view
        # For now, let's assume the view handles this check.
        # This filter's main job is to structure the data.
        list1.append(create_task_dict(item, task_type))

    return list1

@register.filter
def sort_by_due_date(items):
    """Sorts a combined list of task DICTIONARIES by their due_date."""
    def get_due_date(item_dict):
        due = item_dict.get('due_date')
        if isinstance(due, datetime):
            return due
        # Return a date far in the future for items with no date
        return datetime.max.replace(tzinfo=pytz.UTC)

    if isinstance(items, list):
        return sorted(items, key=get_due_date)
    return items