from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from core.models import Guardian, CustomUser


class GuardianRegistrationForm(UserCreationForm):
    gender = forms.ChoiceField(
        choices=Guardian.GENDER_CHOICES,
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
        guardian_instance = kwargs.pop('guardian_instance', None)  # Extract student_instance if provided
        super().__init__(*args, **kwargs)

        if self.is_update:
            # Remove password fields for the update view
            self.fields.pop('password1', None)
            self.fields.pop('password2', None)

        # Populate initial data if a student instance is provided
        if guardian_instance:
            self.fields['gender'].initial = guardian_instance.gender
            self.fields['profile_image'].initial = guardian_instance.profile_image
            self.fields['contact'].initial = guardian_instance.contact
            self.fields['address'].initial = guardian_instance.address

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
            user.role = 'guardian'  # Assign the 'student' role only for new users

        if commit:
            user.save()

        guardian = Guardian.objects.create(
        user=user,
        gender=self.cleaned_data.get('gender'),
        profile_image=self.cleaned_data.get('profile_image'),
        contact=self.cleaned_data.get('contact'),
        address=self.cleaned_data.get('address')
    )

        if commit:
            guardian.save()

        return guardian