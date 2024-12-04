from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from ..models import Teacher, CustomUser


class TeacherRegistrationForm(UserCreationForm):
    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'placeholder': 'YYYY-MM-DD'
        })
    )
    gender = forms.ChoiceField(
        choices=Teacher.GENDER_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'
        })
    )
    contact = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your contact number'
        })
    )
    address = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your address',
            'rows': 3  # Control the size of the textarea
        })
    )
    profile_image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )

    def __init__(self, *args, **kwargs):
        self.is_update = kwargs.pop('is_update', False)
        teacher_instance = kwargs.pop('teacher_instance', None)  # Extract student_instance if provided
        super().__init__(*args, **kwargs)

        if self.is_update:
            # Remove password fields for the update view
            self.fields.pop('password1', None)
            self.fields.pop('password2', None)

        # Populate initial data if a student instance is provided
        if teacher_instance:
            self.fields['date_of_birth'].initial = teacher_instance.date_of_birth
            self.fields['gender'].initial = teacher_instance.gender
            self.fields['profile_image'].initial = teacher_instance.profile_image
            self.fields['contact'].initial = teacher_instance.contact
            self.fields['address'].initial = teacher_instance.address


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
        # First, save the CustomUser data
        user = super().save(commit=False)
        user.role = 'teacher'  # Assign the 'teacher' role
        if commit:
            user.save()

        # Now, save the Teacher-specific data
        teacher = Teacher.objects.create(
            user=user,
            date_of_birth=self.cleaned_data['date_of_birth'],
            contact=self.cleaned_data['contact'],
            address=self.cleaned_data['address'],
            gender=self.cleaned_data['gender'],
            profile_image=self.cleaned_data.get('profile_image')
        )
        if commit:
            teacher.save()

        return teacher


class MessageForm(forms.Form):
    title = forms.CharField(max_length=100, label="Title")
    content = forms.CharField(widget=forms.Textarea, label="Message to Guardians")