from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from ..models import Student, Teacher, CustomUser, Message


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
    highest_education = forms.ChoiceField(
        choices=[('', '-- Select Qualification --')] + Teacher.EDUCATION_CHOICES,
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
        self.teacher_instance = kwargs.pop('teacher_instance', None)  # Store teacher_instance
        super().__init__(*args, **kwargs)

        if self.is_update:
            # Remove password fields for the update view
            self.fields.pop('password1', None)
            self.fields.pop('password2', None)

        # Populate initial data if a teacher instance is provided
        if self.teacher_instance:
            self.fields['date_of_birth'].initial = self.teacher_instance.date_of_birth
            self.fields['gender'].initial = self.teacher_instance.gender
            self.fields['profile_image'].initial = self.teacher_instance.profile_image
            self.fields['contact'].initial = self.teacher_instance.contact
            self.fields['address'].initial = self.teacher_instance.address
            self.fields['nin'].initial = self.teacher_instance.nin
            self.fields['highest_education'].initial = self.teacher_instance.highest_education


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

    def clean_nin(self):
        nin = self.cleaned_data.get('nin')
        if not nin or not nin.strip():
            return None
        
        nin = nin.strip()
        if len(nin) != 11 or not nin.isdigit():
            raise ValidationError("The National Identification Number must be exactly 11 digits.")
            
        qs = Teacher.objects.filter(nin=nin)
        if hasattr(self, 'teacher_instance') and self.teacher_instance:
            qs = qs.exclude(pk=self.teacher_instance.pk)
        if qs.exists():
            raise ValidationError("This National Identification Number is already registered.")
        return nin

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
            user.role = 'teacher'  # Assign the 'teacher' role only for new users

        if commit:
            user.save()

        # Handle Teacher instance
        if hasattr(self, 'teacher_instance') and self.teacher_instance:
            teacher = self.teacher_instance  # Use the existing Teacher instance
            teacher.date_of_birth = self.cleaned_data['date_of_birth']
            teacher.contact = self.cleaned_data['contact']
            teacher.address = self.cleaned_data['address']
            teacher.gender = self.cleaned_data['gender']
            teacher.nin = self.cleaned_data.get('nin')
            teacher.highest_education = self.cleaned_data.get('highest_education')
            if self.cleaned_data.get('profile_image'):
                teacher.profile_image = self.cleaned_data['profile_image']
            if commit:
                teacher.save()
        else:
            from django.utils import timezone
            teacher = Teacher(
                user=user,
                date_of_birth=self.cleaned_data['date_of_birth'],
                contact=self.cleaned_data['contact'],
                address=self.cleaned_data['address'],
                gender=self.cleaned_data['gender'],
                profile_image=self.cleaned_data.get('profile_image'),
                nin=self.cleaned_data.get('nin'),
                highest_education=self.cleaned_data.get('highest_education'),
                ndpr_consent=self.cleaned_data.get('ndpr_consent', False),
                ndpr_consent_date=timezone.now() if self.cleaned_data.get('ndpr_consent') else None
            )
            if commit:
                teacher.save()

        return teacher

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