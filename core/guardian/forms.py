from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from core.models import Student, Guardian, CustomUser, Message


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
    nin = forms.CharField(
        max_length=11,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '12345678901',
            'pattern': '[0-9]{11}',
            'title': '11-digit National Identification Number'
        }),
        help_text='Optional: Your 11-digit NIN'
    )
    occupation = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Teacher, Engineer, Business Owner'
        }),
        help_text='Optional: Your current occupation'
    )
    highest_education = forms.ChoiceField(
        choices=[('', '-- Select Qualification --')] + Guardian.EDUCATION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    ndpr_consent = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I consent to the collection and processing of my personal data',
        help_text='Required: You must agree to our data protection policy to register'
    )

    def __init__(self, *args, **kwargs):
        self.is_update = kwargs.pop('is_update', False)
        self.guardian_instance = kwargs.pop('guardian_instance', None)  # Store guardian_instance
        super().__init__(*args, **kwargs)

        if self.is_update:
            # Remove password fields for the update view
            self.fields.pop('password1', None)
            self.fields.pop('password2', None)

        # Populate initial data if a guardian instance is provided
        if self.guardian_instance:
            self.fields['gender'].initial = self.guardian_instance.gender
            self.fields['profile_image'].initial = self.guardian_instance.profile_image
            self.fields['contact'].initial = self.guardian_instance.contact
            self.fields['address'].initial = self.guardian_instance.address
            self.fields['nin'].initial = self.guardian_instance.nin
            self.fields['occupation'].initial = self.guardian_instance.occupation
            self.fields['highest_education'].initial = self.guardian_instance.highest_education

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
        if username:
            user_qs = CustomUser.objects.filter(username=username)
            if self.instance:  # If updating, exclude the current user
                user_qs = user_qs.exclude(pk=self.instance.pk)
            if user_qs.exists():
                raise ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email_qs = CustomUser.objects.filter(email=email)
            if self.instance:  # If updating, exclude the current user
                email_qs = email_qs.exclude(pk=self.instance.pk)
            if email_qs.exists():
                raise ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        if self.is_update:
            # For updates, just update the user instance directly
            user = self.instance
            user.username = self.cleaned_data['username']
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
        else:
            # For new users, use the parent's save method
            user = super().save(commit=False)
            user.role = 'guardian'  # Assign the 'guardian' role only for new users

        if commit:
            user.save()

        # Handle guardian instance
        if hasattr(self, 'guardian_instance') and self.guardian_instance:
            guardian = self.guardian_instance  # Use the existing guardian instance
            guardian.contact = self.cleaned_data['contact']
            guardian.address = self.cleaned_data['address']
            guardian.gender = self.cleaned_data['gender']
            guardian.nin = self.cleaned_data.get('nin')
            guardian.occupation = self.cleaned_data.get('occupation')
            guardian.highest_education = self.cleaned_data.get('highest_education')
            if self.cleaned_data.get('profile_image'):
                guardian.profile_image = self.cleaned_data['profile_image']
            if commit:
                guardian.save()
        else:
            from django.utils import timezone
            guardian = Guardian(
                user=user,
                contact=self.cleaned_data['contact'],
                address=self.cleaned_data['address'],
                gender=self.cleaned_data['gender'],
                profile_image=self.cleaned_data.get('profile_image'),
                nin=self.cleaned_data.get('nin'),
                occupation=self.cleaned_data.get('occupation'),
                highest_education=self.cleaned_data.get('highest_education'),
                ndpr_consent=self.cleaned_data.get('ndpr_consent', False),
                ndpr_consent_date=timezone.now() if self.cleaned_data.get('ndpr_consent') else None
            )
            if commit:
                guardian.save()

        return guardian


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