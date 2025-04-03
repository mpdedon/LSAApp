from django import forms
from core.models import SubjectResult

class SubjectResultForm(forms.ModelForm):
    class Meta:
        model = SubjectResult
        fields = [
            'continuous_assessment_1', 'continuous_assessment_2',
            'continuous_assessment_3', 'assignment', 'oral_test',
            'exam_score', 'is_finalized'
        ]
        widgets = {
            # Add 'step' for better browser number handling and classes for JS/styling
            'continuous_assessment_1': forms.NumberInput(attrs={
                'class': 'form-control score-input ca1-input',
                'oninput': 'calculateRow(this)', 'step': '0.5', 'min': '0', 'max': '10.0'
            }),
            'continuous_assessment_2': forms.NumberInput(attrs={
                'class': 'form-control score-input ca2-input',
                'oninput': 'calculateRow(this)', 'step': '0.5', 'min': '0', 'max': '10.0'
            }),
            'continuous_assessment_3': forms.NumberInput(attrs={
                'class': 'form-control score-input ca3-input',
                'oninput': 'calculateRow(this)', 'step': '0.5', 'min': '0', 'max': '10.0'
            }),
            'assignment': forms.NumberInput(attrs={
                'class': 'form-control score-input assignment-input',
                'oninput': 'calculateRow(this)', 'step': '0.5', 'min': '0', 'max': '10.0'
            }),
            'oral_test': forms.NumberInput(attrs={
                'class': 'form-control score-input oral-input',
                'oninput': 'calculateRow(this)', 'step': '0.5', 'min': '0', 'max': '20.0'
            }),
            'exam_score': forms.NumberInput(attrs={
                'class': 'form-control score-input exam-input',
                'oninput': 'calculateRow(this)', 'step': '0.5', 'min': '0', 'max': '40.0'
            }),
            # Use CheckboxInput for the boolean field
            'is_finalized': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Add any cross-field validation if needed here
        # Example: Ensure total doesn't exceed 100 conceptually (though individual max validators help)
        ca1 = cleaned_data.get('continuous_assessment_1') or 0
        ca2 = cleaned_data.get('continuous_assessment_2') or 0
        ca3 = cleaned_data.get('continuous_assessment_3') or 0
        assignment = cleaned_data.get('assignment') or 0
        oral_test = cleaned_data.get('oral_test') or 0
        exam_score = cleaned_data.get('exam_score') or 0

        total = ca1 + ca2 + ca3 + assignment + oral_test + exam_score
        if total > 100:
             # You could raise a general validation error or attach to a field
             raise forms.ValidationError("Calculated total score exceeds 100. Please check individual scores.")

        return cleaned_data