# forms.py

from django import forms
from core.models import Exam, OnlineQuestion, Term
from django.utils.timezone import now

class ExamForm(forms.ModelForm):
    questions = forms.ModelMultipleChoiceField(
        queryset=OnlineQuestion.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Exam
        fields = ['term', 'subject', 'title', 'short_description', 'class_assigned', 'due_date', 'duration', 'questions']
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'duration': forms.NumberInput(attrs={'placeholder': 'Duration in minutes'}),
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Limit term choices to active terms
            self.fields['term'].queryset = Term.objects.filter(is_active=True)

        def clean_due_date(self):
            due_date = self.cleaned_data['due_date']
            if due_date <= now():
                raise forms.ValidationError("Due date must be in the future.")
            return due_date
            
class OnlineQuestionForm(forms.ModelForm):
    class Meta:
        model = OnlineQuestion
        fields = ['question_type', 'question_text', 'options', 'correct_answer']


