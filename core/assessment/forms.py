# forms.py

from django import forms
from ..models import Assessment

class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = '__all__'


