from django import forms
from core.models import Assignment, Question, AssignmentSubmission
from core.fields import AwareDateTimeField

class AssignmentForm(forms.ModelForm):

    due_date = AwareDateTimeField(
        required=False, 
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )
    class Meta:
        model = Assignment
        fields = [
            'term', 'teacher', 'title', 'description', 'subject', 
            'class_assigned', 'due_date', 'duration', 'active',
            'result_field_mapping', 'shuffle_questions'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'class_assigned': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'shuffle_questions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['question_type', 'question_text', 'options', 'correct_answer']

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get("question_type")
        question_text = cleaned_data.get("question_text")

        if not question_text:
            raise forms.ValidationError("Question text is required.")

        if question_type in ['SCQ', 'MCQ']:
            options = cleaned_data.get("options")
            correct_answer = cleaned_data.get("correct_answer")
            if not options:
                raise forms.ValidationError("Options must be provided for SCQ/MCQ.")
            if not correct_answer:
                raise forms.ValidationError("Correct answer is required for SCQ/MCQ.")
        elif question_type == 'ES':
            # No additional validation for essay
            cleaned_data['options'] = None
            cleaned_data['correct_answer'] = None

        return cleaned_data



class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['answers']
