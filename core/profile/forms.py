# core/profile/forms.py
"""
Forms for user profile management
"""
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from core.models import CustomUser, Student, Teacher, Guardian
from core.system_settings import SystemSettings


class ProfileImageForm(forms.ModelForm):
    """Common form for profile image upload"""
    class Meta:
        fields = ['profile_image']
        widgets = {
            'profile_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }


class UserProfileForm(forms.ModelForm):
    """Form for updating basic user information"""
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email Address'
            }),
        }


class StudentProfileForm(forms.ModelForm):
    """Form for student-specific profile fields"""
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)
    
    class Meta:
        model = Student
        fields = ['profile_image', 'date_of_birth', 'gender']
        widgets = {
            'profile_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'gender': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
    
    def save(self, commit=True):
        student = super().save(commit=False)
        if student.user:
            student.user.first_name = self.cleaned_data['first_name']
            student.user.last_name = self.cleaned_data['last_name']
            student.user.email = self.cleaned_data['email']
            if commit:
                student.user.save()
        if commit:
            student.save()
        return student


class TeacherProfileForm(forms.ModelForm):
    """Form for teacher-specific profile fields"""
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    
    class Meta:
        model = Teacher
        fields = ['profile_image', 'date_of_birth', 'gender', 'contact', 'address']
        widgets = {
            'profile_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'gender': forms.Select(attrs={
                'class': 'form-control'
            }),
            'contact': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone Number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Full Address'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
    
    def save(self, commit=True):
        teacher = super().save(commit=False)
        if teacher.user:
            teacher.user.first_name = self.cleaned_data['first_name']
            teacher.user.last_name = self.cleaned_data['last_name']
            teacher.user.email = self.cleaned_data['email']
            if commit:
                teacher.user.save()
        if commit:
            teacher.save()
        return teacher


class GuardianProfileForm(forms.ModelForm):
    """Form for guardian-specific profile fields"""
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    
    class Meta:
        model = Guardian
        fields = ['profile_image', 'gender', 'contact', 'address']
        widgets = {
            'profile_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'gender': forms.Select(attrs={
                'class': 'form-control'
            }),
            'contact': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone Number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Full Address'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
    
    def save(self, commit=True):
        guardian = super().save(commit=False)
        if guardian.user:
            guardian.user.first_name = self.cleaned_data['first_name']
            guardian.user.last_name = self.cleaned_data['last_name']
            guardian.user.email = self.cleaned_data['email']
            if commit:
                guardian.user.save()
        if commit:
            guardian.save()
        return guardian


class SystemSettingsForm(forms.ModelForm):
    """Form for system settings configuration"""
    
    class Meta:
        model = SystemSettings
        exclude = ['last_modified', 'last_modified_by', 'email_host_password', 'payment_secret_key', 'sms_api_key']
        widgets = {
            'school_name': forms.TextInput(attrs={'class': 'form-control'}),
            'school_motto': forms.TextInput(attrs={'class': 'form-control'}),
            'school_logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'school_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'school_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'school_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'school_website': forms.URLInput(attrs={'class': 'form-control'}),
            
            'email_host': forms.TextInput(attrs={'class': 'form-control'}),
            'email_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'email_use_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_use_ssl': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_host_user': forms.EmailInput(attrs={'class': 'form-control'}),
            'default_from_email': forms.EmailInput(attrs={'class': 'form-control'}),
            
            'passing_grade': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'attendance_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'late_arrival_grace_period': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            
            'default_currency': forms.TextInput(attrs={'class': 'form-control'}),
            'currency_symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'late_payment_penalty_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            
            'assignment_max_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'assessment_max_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'exam_max_score': forms.NumberInput(attrs={'class': 'form-control'}),
            
            'default_term_duration_weeks': forms.NumberInput(attrs={'class': 'form-control'}),
            'number_of_terms_per_session': forms.NumberInput(attrs={'class': 'form-control'}),
            'academic_year_start_month': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            
            'session_timeout_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_login_attempts': forms.NumberInput(attrs={'class': 'form-control'}),
            
            # SMS Configuration
            'sms_provider': forms.Select(attrs={'class': 'form-control'}),
            'sms_sender_id': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Payment Gateway
            'payment_provider': forms.Select(attrs={'class': 'form-control'}),
            'payment_public_key': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Admission Configuration
            'admission_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_students_per_class': forms.NumberInput(attrs={'class': 'form-control'}),
            
            # Report Card Configuration
            'report_card_header': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'report_card_footer': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'principal_signature': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            
            # Backup & Maintenance
            'backup_frequency_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'maintenance_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            
            # Boolean fields
            'enable_fee_module': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'late_payment_penalty_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_assignments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_assessments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_exams': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_position': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_promote_students': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'result_approval_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_lms': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_blog': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_messaging': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_email_verification': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_sms': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_online_payment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'payment_test_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_online_admission': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_admission_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_student_photo_on_report': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_backup_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'maintenance_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    grading_system_json = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 8,
            'placeholder': 'Enter grading system as JSON'
        }),
        required=False,
        help_text='JSON format: {"A": {"min_score": 70, "max_score": 100, "remark": "Excellent"}, ...}'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.grading_system:
            import json
            self.fields['grading_system_json'].initial = json.dumps(
                self.instance.grading_system, indent=2
            )
    
    def clean_grading_system_json(self):
        """Validate and parse JSON grading system"""
        import json
        data = self.cleaned_data.get('grading_system_json')
        if data:
            try:
                parsed = json.loads(data)
                # Validate structure
                for grade, config in parsed.items():
                    if not all(k in config for k in ['min_score', 'max_score', 'remark']):
                        raise forms.ValidationError(
                            f"Grade {grade} must have min_score, max_score, and remark"
                        )
                return parsed
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON format")
        return {}
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        grading_system = self.cleaned_data.get('grading_system_json')
        if grading_system:
            instance.grading_system = grading_system
        if commit:
            instance.save()
        return instance
