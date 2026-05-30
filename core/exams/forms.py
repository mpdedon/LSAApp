# forms.py

from django import forms
from core.models import Class, Exam, OnlineQuestion, Term
from django.utils.timezone import now
import json


class ExamForm(forms.ModelForm):
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
                  'due_date', 'duration', 'result_field_mapping', 'shuffle_questions']
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
        self.allow_multiple_classes = kwargs.pop('allow_multiple_classes', False)
        self.target_classes_required = kwargs.pop('target_classes_required', True)
        self.hide_class_assigned_when_multi = kwargs.pop('hide_class_assigned_when_multi', True)
        super().__init__(*args, **kwargs)
        self.fields['term'].queryset = Term.objects.all()
        if self.allow_multiple_classes:
            self.fields['target_classes'] = forms.ModelMultipleChoiceField(
                queryset=Class.objects.none(),
                widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
                required=self.target_classes_required,
                label='Assign to classes' if self.hide_class_assigned_when_multi else 'Also add these classes',
                help_text=(
                    'Creates one exam copy per selected class so existing approval, submission, and scoring flows stay single-class.'
                    if self.hide_class_assigned_when_multi else
                    'Optional. Creates additional exam copies for the selected classes using the current edited content.'
                ),
            )
            if self.hide_class_assigned_when_multi:
                self.fields['class_assigned'].required = False
                self.fields['class_assigned'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        if self.allow_multiple_classes:
            target_classes = cleaned_data.get('target_classes')
            if target_classes and self.hide_class_assigned_when_multi:
                cleaned_data['class_assigned'] = target_classes[0]
            elif self.target_classes_required:
                self.add_error('target_classes', 'Select at least one class.')
        return cleaned_data

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date <= now():
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

        answers = [answer.strip().lower() for answer in str(correct_answer).split(',') if answer.strip()] if correct_answer else []
        option_lookup = {
            str(option).strip().lower(): str(option).strip()
            for option in (options or [])
            if str(option).strip()
        }
        options_lower = list(option_lookup.keys())

        if question_type == 'SCQ':
            if len(answers) != 1:
                raise forms.ValidationError("A single correct answer is required for SCQ questions.")
            if options_lower and answers[0] not in options_lower:
                raise forms.ValidationError("The correct answer must be one of the provided options.")
            return option_lookup.get(answers[0], answers[0])

        if question_type == 'MCQ':
            if not answers:
                raise forms.ValidationError("At least one correct answer is required for MCQ questions.")
            if options_lower:
                invalid_answers = [answer for answer in answers if answer not in options_lower]
                if invalid_answers:
                    raise forms.ValidationError("All correct answers must be selected from the provided options.")
            return ','.join(option_lookup.get(answer, answer) for answer in answers)
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




