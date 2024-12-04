from django import forms
from core.models import FeeAssignment, StudentFeeRecord

class FeeAssignmentForm(forms.ModelForm):
    class Meta:
        model = FeeAssignment
        fields = ['class_instance', 'term', 'amount']
        widgets = {
            'class_instance': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class StudentFeeRecordForm(forms.ModelForm):
    class Meta:
        model = StudentFeeRecord
        fields = ['discount', 'waiver']
        widgets = {
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter discount'}),
            'waiver': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }