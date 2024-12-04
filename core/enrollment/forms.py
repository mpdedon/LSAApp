from django import forms
from core.models import Enrollment, Student

class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['student', 'class_enrolled', 'session', 'term', 'is_active']

    def __init__(self, *args, **kwargs):
        class_instance = kwargs.pop('class_instance', None)
        super().__init__(*args, **kwargs)

        if class_instance:
            # Exclude students already enrolled in the class for this session and term
            enrolled_students = class_instance.enrollment_set.values_list('student__user_id', flat=True)
            self.fields['student'].queryset = Student.objects.exclude(user_id__in=enrolled_students)