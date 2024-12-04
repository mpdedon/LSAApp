# core/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Subject, Session, Term, Result, Notification

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role', 'password1', 'password2')


class ClassSubjectAssignmentForm(forms.Form):
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    session = forms.ModelChoiceField(queryset=Session.objects.all())
    term = forms.ModelChoiceField(queryset=Term.objects.all())


class NonAcademicSkillsForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = [
            'punctuality', 'diligence', 'cooperation', 'respectfulness',
            'sportsmanship', 'agility', 'creativity', 'hand_eye_coordination',
            'teacher_remarks', 'principal_remarks'
        ]
        widgets = {
            'punctuality': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'diligence': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'cooperation': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'respectfulness': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'sportsmanship': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'agility': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'creativity': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'hand_eye_coordination': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'teacher_remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'principal_remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['title', 'message', 'audience', 'expiry_date', 'is_active']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }
