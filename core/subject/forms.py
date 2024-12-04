# forms.py

from django import forms
from ..models import Subject

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'description', 'subject_weight']


