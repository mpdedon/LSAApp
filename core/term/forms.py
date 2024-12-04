# forms.py

from django import forms
from ..models import Term

class TermForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ['session', 'name', 'start_date', 'end_date', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'class': 'form-control datepicker', 'autocomplete': 'off'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control datepicker', 'autocomplete': 'off'}),
        }