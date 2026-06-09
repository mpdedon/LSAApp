from django import forms
from core.models import FeeAssignment, StudentFeeRecord, Term

class FeeAssignmentForm(forms.ModelForm):
    class Meta:
        model = FeeAssignment
        fields = ['class_instance', 'term', 'amount']
        widgets = {
            'class_instance': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        class_instance = cleaned_data.get('class_instance')
        term = cleaned_data.get('term')
        if class_instance and term:
            existing = FeeAssignment.objects.filter(class_instance=class_instance, term=term)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError(
                    'A fee assignment already exists for this class and term. Edit the existing assignment or use rollover.'
                )
        return cleaned_data

class StudentFeeRecordForm(forms.ModelForm):
    class Meta:
        model = StudentFeeRecord
        fields = ['discount', 'waiver']
        widgets = {
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter discount'}),
            'waiver': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FeeAssignmentRolloverForm(forms.Form):
    source_term = forms.ModelChoiceField(
        queryset=Term.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Copy fees from',
    )
    target_term = forms.ModelChoiceField(
        queryset=Term.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Into term',
    )
    overwrite_existing_assignments = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Replace amounts on existing target-term class fees',
    )
    carry_forward_adjustments = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Carry forward discounts and waivers for active students',
    )

    def __init__(self, *args, **kwargs):
        self.target_term = kwargs.pop('target_term', None)
        self.source_term = kwargs.pop('source_term', None)
        super().__init__(*args, **kwargs)
        term_qs = Term.objects.select_related('session').order_by('-start_date')
        self.fields['source_term'].queryset = term_qs
        self.fields['target_term'].queryset = term_qs
        if self.target_term:
            self.fields['target_term'].initial = self.target_term
        if self.source_term:
            self.fields['source_term'].initial = self.source_term

    def clean(self):
        cleaned_data = super().clean()
        source_term = cleaned_data.get('source_term')
        target_term = cleaned_data.get('target_term')
        if source_term and target_term and source_term.pk == target_term.pk:
            raise forms.ValidationError('Source term and target term must be different.')
        return cleaned_data