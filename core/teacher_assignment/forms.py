# forms.py

from django import forms
from core.models import TeacherAssignment

class TeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = TeacherAssignment
        fields = ['class_assigned', 'teacher', 'session', 'term', 'is_form_teacher']
        widgets = {
            'class_assigned': forms.Select(attrs={'class': 'form-control'}),
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'is_form_teacher': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

