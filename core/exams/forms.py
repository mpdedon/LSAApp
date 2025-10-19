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

    due_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M']
    )
    duration = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 60'}),
        min_value=1
    )

    class Meta:
        model = Exam
        fields = ['term', 'subject', 'title', 'short_description', 'class_assigned', 
                  'due_date', 'duration', 'questions', 'result_field_mapping', 'shuffle_questions']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter the title of the exam'}),
            'short_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Provide a brief description'}),
            'class_assigned': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'duration': forms.NumberInput(attrs={'placeholder': 'Duration in minutes'}),
            'shuffle_questions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),

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
        fields = ['question_type', 'question_text', 'options', 'correct_answer', 'points']

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get('question_type')
        points = cleaned_data.get('points')

        if question_type in ['SCQ', 'MCQ']:
            if not points:  # Catches None, 0, or empty
                cleaned_data['points'] = 1

        elif question_type == 'ES':
            if not points or points <= 0:
                self.add_error('points', 'A point value greater than zero is required for Essay questions.')
        
        return cleaned_data
    
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




