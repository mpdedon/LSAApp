# forms.py

from django import forms
from core.models import Class

class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'school_level', 'description', 'teacher', 'order']