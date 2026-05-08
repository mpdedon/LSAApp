# forms.py

from django import forms
from core.models import Assessment, OnlineQuestion, Term
from django.utils.timezone import now
import json


class AssessmentForm(forms.ModelForm):

    due_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M']
    )
    duration = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 60'}),
        min_value=1
    )

    class Meta:
        model = Assessment
        fields = [
            'title', 'short_description', 'class_assigned',
            'subject', 'term', 'due_date', 'duration',
            'result_field_mapping', 'shuffle_questions'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter the title of the assessment'}),
            'short_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Provide a brief description'}),
            'class_assigned': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 45 for 45 minutes'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'result_field_mapping': forms.Select(attrs={'class': 'form-control'}),
            'shuffle_questions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['term'].queryset = Term.objects.all()

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
        options = self.cleaned_data.get('options') # This should be a list if coming from view/JSONField
        question_type = self.cleaned_data.get('question_type')

        if question_type in ['SCQ', 'MCQ']:
            if not options or not isinstance(options, list) or len(options) < 1: # Allow at least one option
                raise forms.ValidationError("At least one option is required for SCQ/MCQ questions.")
        return options

    def clean_correct_answer(self):
        correct_answer_input = self.cleaned_data.get('correct_answer')
        question_type = self.cleaned_data.get('question_type')
        options = self.cleaned_data.get('options')

        # Normalise to lowercase so validation is case-insensitive (matches grading logic)
        if correct_answer_input:
            correct_answer_input = correct_answer_input.strip().lower()
        options_lower = [o.lower() for o in options] if options else []

        if question_type == 'SCQ':
            if not correct_answer_input:
                raise forms.ValidationError("A correct answer is required for Single Choice Questions.")
            if options_lower and correct_answer_input not in options_lower:
                raise forms.ValidationError("For Single Choice, the correct answer must be one of the provided options.")

        elif question_type == 'MCQ':
            if not correct_answer_input:
                raise forms.ValidationError("At least one correct answer is required for Multiple Choice Questions.")

            sep = ',' if ',' in correct_answer_input else ' '
            individual_correct_answers = [ans.strip() for ans in correct_answer_input.split(sep) if ans.strip()]

            if not individual_correct_answers:
                raise forms.ValidationError("Please provide valid correct answer(s) for MCQ.")

            if options_lower:
                for ans_part in individual_correct_answers:
                    if ans_part not in options_lower:
                        raise forms.ValidationError(
                            f"The answer '{ans_part}' is not among the provided options. "
                            f"Options: {', '.join(options)}."
                        )
            else:
                raise forms.ValidationError("Options are missing for this MCQ, cannot validate correct answer.")

            return correct_answer_input

        elif question_type == 'ES':
            # For Essay, correct_answer is optional (can be a model answer or rubric)
            # No specific validation here other than what ModelCharField imposes (e.g. max_length)
            pass 
            
        return correct_answer_input # Return original input for ES or if no specific validation was triggered


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        initial_options = self.initial.get('options')
        # This logic is for when the form is initialized with existing instance data
        # for an edit form, ensuring stringified JSON for options is parsed to a list.
        if self.instance and self.instance.pk and isinstance(self.instance.options, str):
            try:
                parsed_options = json.loads(self.instance.options)
                if isinstance(parsed_options, list):
                     pass # Rely on JSONField's behavior
            except (json.JSONDecodeError, TypeError):
                # self.initial['options'] = [] # Default to empty list if parsing fails
                pass
        elif isinstance(initial_options, str): # If 'options' passed in initial dict is a string
             try:
                self.initial['options'] = json.loads(initial_options)
             except json.JSONDecodeError:
                self.initial['options'] = []
    
  

