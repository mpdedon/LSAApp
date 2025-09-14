# lsalms/forms.py

from django import forms
from .models import Course, Module, Lesson, ContentBlock
from core.models import Subject

class CourseForm(forms.ModelForm):
    """
    A comprehensive form for creating and editing courses.
    Designed to be used with JavaScript to show/hide conditional fields.
    """
    class Meta:
        model = Course
        fields = [
            'title', 'course_type', 'linked_class', 'term', 'subject', 'is_subscription_based',
            'learning_objectives', 'prerequisites'
        ]
        widgets = {
            'learning_objectives': forms.Textarea(attrs={'rows': 4}),
            'prerequisites': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'course_type': 'Select "Internal" for regular school classes or "External" for the Online Academy.',
            'subject': "Select the official school subject this course is for.",
            'title': "Enter a catchy title for your Online Academy course.",
            'is_subscription_based': 'Check this if students must pay to access this external course.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes to fields to allow JavaScript to easily target them for show/hide logic
        self.fields['linked_class'].widget.attrs['class'] = 'form-select internal-field'
        self.fields['term'].widget.attrs['class'] = 'form-select internal-field'
        self.fields['subject'].widget.attrs['class'] = 'form-select internal-field'
        self.fields['is_subscription_based'].widget.attrs['class'] = 'form-check-input external-field'

        # Case 1: The form is bound with data (i.e., it's a POST request)
        if self.is_bound:
            # If a class was submitted in the data, filter the subject queryset
            try:
                class_id = int(self.data.get('linked_class'))
                self.fields['subject'].queryset = Subject.objects.filter(
                    class_assignments__class_assigned_id=class_id
                ).distinct()
            except (ValueError, TypeError):
                # If class_id is not a valid number, do nothing (validation will catch it)
                pass
        
        # Case 2: The form is for an existing instance (i.e., it's an EDIT page)
        elif self.instance and self.instance.pk and self.instance.linked_class:
            self.fields['subject'].queryset = Subject.objects.filter(
                class_assignments__class_assigned=self.instance.linked_class
            ).distinct()

        # Case 3: The form is new and unbound (i.e., a fresh CREATE page)
        # The JS will handle populating this, so it can start empty.
        else:
            self.fields['subject'].queryset = Subject.objects.none()


    # The model's clean method now handles most validation, but we can keep this for safety.
    def clean(self):
        return super().clean()

class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ['title', 'description', 'order']

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'estimated_duration']

class ContentBlockForm(forms.ModelForm):
    class Meta:
        model = ContentBlock
        fields = [
            'title', 'content_type', 'rich_text', 'media_url', 'media_file',
            'linked_practice_quiz', 'linked_assignment', 'linked_assessment', 'linked_exam', 'order'
        ]
        # ... (help_texts)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Map content types to the fields they should display
        field_map = {
            'TEXT': ['rich_text'],
            'VIDEO': ['media_url'],
            'IMAGE': ['media_file'],
            'AUDIO': ['media_file', 'media_url'],
            'FILE': ['media_file'],
            'PRACTICE_QUIZ': ['linked_practice_quiz'],
            'ASSIGNMENT': ['linked_assignment'],
            'ASSESSMENT': ['linked_assessment'],
            'EXAM': ['linked_exam'],
        }

        # Add data attributes and classes to each field for JS targeting
        for field_name in self.fields:
            self.fields[field_name].widget.attrs['class'] = 'form-control content-block-field'
            
            # Find which content types this field belongs to
            relevant_types = []
            for content_type, fields in field_map.items():
                if field_name in fields:
                    relevant_types.append(content_type)
            
            if relevant_types:
                self.fields[field_name].widget.attrs['data-content-type'] = " ".join(relevant_types)