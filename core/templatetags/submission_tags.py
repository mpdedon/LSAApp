from django import template
from django.apps import apps
from django.db import models

register = template.Library()

@register.simple_tag
def get_submission(submission_model_name_str, item_instance, student_instance):
    # Construct model class from string
    # Assumes submission_model_name_str is like "AssessmentSubmission"
    # And that the model has fields 'assessment' (or 'exam', 'assignment') and 'student'
    
    # Determine the correct field name on the submission model that links to item_instance
    item_field_name = ""
    if item_instance._meta.model_name == "assessment":
        item_field_name = "Assessment"
    elif item_instance._meta.model_name == "exam":
        item_field_name = "Exam"
    elif item_instance._meta.model_name == "assignment":
        item_field_name = "Assignment"
    else:
        return None # Unknown item type

    try:
        SubmissionModel = apps.get_model(app_label=item_instance._meta.app_label, model_name=submission_model_name_str)
        submission = SubmissionModel.objects.filter(
            **{item_field_name: item_instance}, # e.g., assessment=item_instance
            student=student_instance
        ).first()
        return submission
    except LookupError: # Model not found
        return None
    except Exception as e: # Other errors
        print(f"Error in get_submission tag: {e}")
        return None

# You might also need a filter for model_name_lower if not available
@register.filter
def model_name_lower(value):
    if isinstance(value, models.Model):
        return value._meta.model_name.lower()
    # Check if the value is a model class
    elif isinstance(value, type) and issubclass(value, models.Model):
         return value._meta.model_name.lower()
    # If it's already a string, just return it lowercased
    elif isinstance(value, str):
        return value.lower()
    # For any other type, return an empty string to avoid errors
    return ""