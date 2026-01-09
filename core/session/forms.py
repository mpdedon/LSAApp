from django import forms
from core.models import Session

class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['start_date', 'end_date', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Select start date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Select end date'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].widget.attrs.update({
            'class': 'form-check-input'
        })
