# forms.py

from django import forms
from ..models import Subject

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'description', 'subject_weight']    
    def clean_name(self):
        """Validate subject name uniqueness, excluding current instance on update"""
        name = self.cleaned_data.get('name')
        
        # Check for existing subjects with this name
        qs = Subject.objects.filter(name=name)
        
        # Exclude current instance if updating
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise forms.ValidationError('A subject with this name already exists.')
        
        return name

