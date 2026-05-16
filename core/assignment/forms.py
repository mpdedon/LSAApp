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
        # 'teacher' and 'active' are set programmatically in the view
        fields = [
            'term', 'title', 'description', 'subject',
            'class_assigned', 'due_date', 'duration',
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

    @staticmethod
    def _normalise_options(options):
        if not options:
            return []
        return [str(option).strip() for option in options if str(option).strip()]

    @staticmethod
    def _normalise_answers(correct_answer):
        if not correct_answer:
            return []
        return [answer.strip() for answer in str(correct_answer).split(',') if answer.strip()]

    @staticmethod
    def _match_answer_labels(options, answers):
        option_lookup = {option.lower(): option for option in options}
        return [option_lookup.get(answer.lower(), answer) for answer in answers]

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get("question_type")
        question_text = cleaned_data.get("question_text")

        if not question_text:
            raise forms.ValidationError("Question text is required.")

        if question_type in ['SCQ', 'MCQ']:
            options = self._normalise_options(cleaned_data.get("options"))
            correct_answer = cleaned_data.get("correct_answer")
            if not options:
                raise forms.ValidationError("Options must be provided for SCQ/MCQ.")
            if not correct_answer:
                raise forms.ValidationError("Correct answer is required for SCQ/MCQ.")

            options_lookup = {option.lower() for option in options}
            answers = self._normalise_answers(correct_answer)
            if question_type == 'SCQ':
                if len(answers) != 1:
                    raise forms.ValidationError("Single Choice questions must have exactly one correct answer.")
            elif not answers:
                raise forms.ValidationError("Multiple Choice questions must have at least one correct answer.")

            invalid_answers = [answer for answer in answers if answer.lower() not in options_lookup]
            if invalid_answers:
                raise forms.ValidationError("Correct answers must be selected from the provided options.")

            answers = self._match_answer_labels(options, answers)

            cleaned_data['options'] = options
            cleaned_data['correct_answer'] = ','.join(answers)
        elif question_type == 'ES':
            # No additional validation for essay
            cleaned_data['options'] = None
            cleaned_data['correct_answer'] = None

        return cleaned_data



class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['answers']
