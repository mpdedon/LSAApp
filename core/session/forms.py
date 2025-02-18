from django import forms
from core.models import Session

class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['start_date', 'end_date', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes and placeholders for date fields
        self.fields['start_date'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'YYYY-MM-DD'
        })
        self.fields['end_date'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'YYYY-MM-DD'
        })
        self.fields['is_active'].widget.attrs.update({
            'class': 'form-check-input'
        })
