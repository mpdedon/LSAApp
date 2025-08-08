from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from core.models import Student, CustomUser, Guardian, Class, Message

class StudentRegistrationForm(UserCreationForm):
    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'placeholder': 'YYYY-MM-DD'
        })
    )
    gender = forms.ChoiceField(
        choices=Student.GENDER_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    profile_image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )
    student_guardian = forms.ModelChoiceField(
        queryset=Guardian.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    relationship = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Parent, Uncle'
        })
    )
    current_class = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.is_update = kwargs.pop('is_update', False)
        student_instance = kwargs.pop('student_instance', None)  # Extract student_instance if provided
        super().__init__(*args, **kwargs)

        if self.is_update:
            # Remove password fields for the update view
            self.fields.pop('password1', None)
            self.fields.pop('password2', None)

        # Populate initial data if a student instance is provided
        if student_instance:
            self.fields['date_of_birth'].initial = student_instance.date_of_birth
            self.fields['gender'].initial = student_instance.gender
            self.fields['profile_image'].initial = student_instance.profile_image
            self.fields['student_guardian'].initial = student_instance.student_guardian
            self.fields['relationship'].initial = student_instance.relationship
            self.fields['current_class'].initial = student_instance.current_class


    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email address'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your last name'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter your password'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm your password'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match.")

        return cleaned_data

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and CustomUser.objects.filter(username=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and CustomUser.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if not self.is_update:
            user.role = 'student'  # Assign the 'student' role only for new users

        if commit:
            user.save()

        if hasattr(self, 'student_instance'):
            student = self.student_instance
            student.date_of_birth = self.cleaned_data['date_of_birth']
            student.gender = self.cleaned_data['gender']
            student.student_guardian = self.cleaned_data['student_guardian']
            student.profile_image = self.cleaned_data['profile_image']
            student.relationship = self.cleaned_data['relationship']
            student.current_class = self.cleaned_data['current-class']

        else:

            student = Student.objects.create(
            user=user,
            date_of_birth=self.cleaned_data.get('date_of_birth'),  
            gender=self.cleaned_data.get('gender'),
            student_guardian=self.cleaned_data.get('student_guardian'),
            profile_image=self.cleaned_data.get('profile_image'),
            relationship=self.cleaned_data.get('relationship'),
            current_class=self.cleaned_data.get('current_class')
        )

        if commit:
            student.save()

        return student


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
