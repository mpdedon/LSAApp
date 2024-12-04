from django import forms
from core.models import SubjectResult


class SubjectResultForm(forms.ModelForm):
    class Meta:
        model = SubjectResult
        fields = [
            'continuous_assessment_1',
            'continuous_assessment_2',
            'continuous_assessment_3',
            'assignment',
            'oral_test',
            'exam_score',
            'is_finalized'
        ]
    