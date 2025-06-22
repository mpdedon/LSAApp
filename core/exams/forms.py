# forms.py

from django import forms
from core.models import Exam, OnlineQuestion, Term
from django.utils.timezone import now
import json


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

    def clean_options(self):
        options = self.cleaned_data.get('options')
        question_type = self.cleaned_data.get('question_type')
        if question_type in ['SCQ', 'MCQ']:
            if not options: 
                raise forms.ValidationError("Options are required for SCQ/MCQ questions.")
        return options

    def clean_correct_answer(self):
        correct_answer = self.cleaned_data.get('correct_answer')
        question_type = self.cleaned_data.get('question_type')
        options = self.cleaned_data.get('options') 

        if question_type in ['SCQ', 'MCQ']:
            if not correct_answer:
                raise forms.ValidationError("A correct answer is required for SCQ/MCQ questions.")
            if options and correct_answer not in options:
                raise forms.ValidationError("The correct answer must be one of the provided options.")
        elif question_type == 'ES':
            pass 
        return correct_answer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If options are coming as a JSON string and you want the form to handle it as a list
        if self.instance and isinstance(self.instance.options, str):
            try:
                self.initial['options'] = json.loads(self.instance.options)
            except json.JSONDecodeError:
                self.initial['options'] = []
        elif 'options' in self.initial and isinstance(self.initial['options'], str):
             try:
                self.initial['options'] = json.loads(self.initial['options'])
             except json.JSONDecodeError:
                self.initial['options'] = []




