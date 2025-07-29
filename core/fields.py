# core/fields.py

from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError

class AwareDateTimeField(forms.DateTimeField):
    """
    A custom form field that ensures the submitted datetime
    is made timezone-aware before being used.
    """
    def to_python(self, value):
        value = super().to_python(value)
        if value is not None and timezone.is_naive(value):
            # Get the current default timezone from settings (e.g., 'Africa/Lagos')
            current_tz = timezone.get_current_timezone()
            try:
                # Make the naive datetime aware of the current timezone
                return timezone.make_aware(value, current_tz)
            except Exception as e:
                # This might happen with ambiguous times during DST changes
                raise ValidationError(f"Could not make datetime timezone-aware: {e}")
        return value