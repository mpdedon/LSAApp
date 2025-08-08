# core/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from core.models import CustomUser, Student, Subject, Session, Term, Result, Notification, Message


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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter notification title'
        })
        self.fields['message'].widget.attrs.update({
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter the message content'
        })
        self.fields['audience'].widget.attrs.update({
            'class': 'form-select'
        })
        self.fields['expiry_date'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'YYYY-MM-DD'
        })
        self.fields['is_active'].widget.attrs.update({
            'class': 'form-check-input'
        })


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Your Full Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Your Email Address'})
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False, # Optional field
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Your Phone Number (Optional)'})
    )
    subject = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Subject of your inquiry'})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 5, 'placeholder': 'Your Message'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""


class MessageForm(forms.ModelForm):

    recipient = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(), 
        label="Recipient",
        empty_label="-- Select Recipient --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    student_context = forms.ModelChoiceField(
        queryset=Student.objects.none(), 
        label="Regarding Student (Optional)",
        required=False,
        empty_label="-- General Message --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Message
        fields = ['recipient', 'student_context', 'title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Message Subject'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Type your message here...'}),
        }

    def __init__(self, *args, **kwargs):
        recipient_queryset = kwargs.pop('recipient_queryset', None)
        student_queryset = kwargs.pop('student_queryset', None)
        
        super().__init__(*args, **kwargs)
        
        if recipient_queryset is not None:
            self.fields['recipient'].queryset = recipient_queryset
        
        if student_queryset is not None:
            self.fields['student_context'].queryset = student_queryset


class ReplyForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Message Subject'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Type your message here...'}),
        }