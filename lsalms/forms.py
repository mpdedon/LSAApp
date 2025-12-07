# lsalms/forms.py

from django import forms
from .models import Course, Module, Lesson, ContentBlock
from core.models import Subject
from django_ckeditor_5.widgets import CKEditor5Widget


# lsalms/forms.py

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'title', 'status', 
            'course_type', 'linked_class', 'term', 'subject', 'is_subscription_based',
            'learning_objectives', 'prerequisites', 'image'
        ]
        widgets = {
            'learning_objectives': forms.Textarea(attrs={'rows': 4}),
            'prerequisites': forms.Textarea(attrs={'rows': 4}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        help_texts = {
            'status': "Set to 'Published' to make the course visible to students. 'Draft' keeps it hidden for editing.",
            'course_type': 'Select "Internal" for regular school classes or "External" for the Online Academy.',
            'subject': "Select the official school subject this course is for.",
            'title': "Enter a catchy title for your Online Academy course.",
            'is_subscription_based': 'Check this if students must pay to access this external course.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make status optional in the form so create flows that omit it (e.g., tests
        # or quick teacher posts) will default to Course.Status.DRAFT at the model level
        # without causing a validation error.
        if 'status' in self.fields:
            try:
                from .models import Course as _Course
                self.fields['status'].required = False
                self.fields['status'].initial = _Course.Status.DRAFT
            except Exception:
                # If import fails during migrations, ignore and leave as-is.
                pass
        # Add CSS classes to fields to allow JavaScript to easily target them for show/hide logic
        self.fields['linked_class'].widget.attrs['class'] = 'form-select internal-field'
        self.fields['term'].widget.attrs['class'] = 'form-select internal-field'
        self.fields['subject'].widget.attrs['class'] = 'form-select internal-field'
        self.fields['is_subscription_based'].widget.attrs['class'] = 'form-check-input external-field'

        if self.is_bound:
            try:
                class_id = int(self.data.get('linked_class'))
                self.fields['subject'].queryset = Subject.objects.filter(
                    class_assignments__class_assigned_id=class_id
                ).distinct()
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.pk and self.instance.linked_class:
            self.fields['subject'].queryset = Subject.objects.filter(
                class_assignments__class_assigned=self.instance.linked_class
            ).distinct()
        else:
            self.fields['subject'].queryset = Subject.objects.none()

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
        widgets = {
            "rich_text": CKEditor5Widget(config_name="default"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Map content types to the fields they should display
        self.fields['content_type'].widget.attrs.update({
            '@change': 'selectedType = $event.target.value',
            'class': 'form-select' 
        })

        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs.update({'class': 'form-control'}) 

        if 'rich_text' in self.fields:
            self.fields['rich_text'].widget.attrs.update({'class': 'ckeditor-textarea'})