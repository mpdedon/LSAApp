# core/system_settings.py
"""
System-wide settings model and utilities for LSA Application
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, EmailValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
import json


class SystemSettings(models.Model):
    """
    Singleton model for system-wide configuration.
    Only one instance should exist in the database.
    """
    
    # School Information
    school_name = models.CharField(max_length=200, default="LearnSwift Academia")
    school_motto = models.CharField(max_length=200, blank=True, default="Excellence in Education")
    school_logo = models.ImageField(upload_to='system/', blank=True, null=True)
    school_address = models.TextField(blank=True)
    school_phone = models.CharField(max_length=20, blank=True)
    school_email = models.EmailField(blank=True, validators=[EmailValidator()])
    school_website = models.URLField(blank=True)
    
    # Email Configuration
    email_host = models.CharField(max_length=100, blank=True, default='smtp.gmail.com')
    email_port = models.IntegerField(default=587, validators=[MinValueValidator(1), MaxValueValidator(65535)])
    email_use_tls = models.BooleanField(default=True)
    email_use_ssl = models.BooleanField(default=False)
    email_host_user = models.EmailField(blank=True)
    email_host_password = models.CharField(max_length=200, blank=True, help_text="Stored encrypted")
    default_from_email = models.EmailField(blank=True)
    
    # Grading System
    grading_system = models.JSONField(
        default=dict,
        blank=True,
        help_text="Grading scale configuration: {grade: {min_score, max_score, remark}}"
    )
    passing_grade = models.IntegerField(
        default=40,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum score to pass"
    )
    
    # Attendance Configuration
    attendance_threshold = models.IntegerField(
        default=75,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum attendance percentage required (%)"
    )
    late_arrival_grace_period = models.IntegerField(
        default=15,
        validators=[MinValueValidator(0)],
        help_text="Grace period for late arrival in minutes"
    )
    
    # Fee Configuration
    enable_fee_module = models.BooleanField(default=True)
    default_currency = models.CharField(max_length=10, default="NGN")
    currency_symbol = models.CharField(max_length=5, default="₦")
    late_payment_penalty_enabled = models.BooleanField(default=False)
    late_payment_penalty_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Assessment Configuration
    enable_assignments = models.BooleanField(default=True)
    enable_assessments = models.BooleanField(default=True)
    enable_exams = models.BooleanField(default=True)
    assignment_max_score = models.IntegerField(default=10)
    assessment_max_score = models.IntegerField(default=20)
    exam_max_score = models.IntegerField(default=70)
    
    # Result Configuration
    show_position = models.BooleanField(default=True, help_text="Show class position on results")
    auto_promote_students = models.BooleanField(default=False, help_text="Automatically promote students at end of session")
    result_approval_required = models.BooleanField(default=True, help_text="Require admin approval before publishing results")
    
    # Term Configuration
    default_term_duration_weeks = models.IntegerField(
        default=12,
        validators=[MinValueValidator(1), MaxValueValidator(52)],
        help_text="Default duration for a term in weeks"
    )
    number_of_terms_per_session = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="Number of terms in an academic session"
    )
    
    # Academic Year Configuration
    academic_year_start_month = models.IntegerField(
        default=9,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Month when academic year begins (1-12)"
    )
    
    # Platform Features
    enable_lms = models.BooleanField(default=True, help_text="Enable Learning Management System")
    enable_blog = models.BooleanField(default=True, help_text="Enable blog/news feature")
    enable_messaging = models.BooleanField(default=True, help_text="Enable internal messaging")
    enable_notifications = models.BooleanField(default=True)
    
    # SMS Configuration
    enable_sms = models.BooleanField(default=False, help_text="Enable SMS notifications")
    sms_provider = models.CharField(
        max_length=50,
        blank=True,
        choices=[('twilio', 'Twilio'), ('africastalking', 'Africa\'s Talking'), ('custom', 'Custom')],
        default='twilio'
    )
    sms_api_key = models.CharField(max_length=200, blank=True, help_text="SMS provider API key")
    sms_sender_id = models.CharField(max_length=20, blank=True, help_text="SMS sender name/number")
    
    # Payment Gateway Configuration
    enable_online_payment = models.BooleanField(default=False, help_text="Enable online fee payment")
    payment_provider = models.CharField(
        max_length=50,
        blank=True,
        choices=[('paystack', 'Paystack'), ('flutterwave', 'Flutterwave'), ('stripe', 'Stripe')],
        default='paystack'
    )
    payment_public_key = models.CharField(max_length=200, blank=True)
    payment_secret_key = models.CharField(max_length=200, blank=True, help_text="Stored encrypted")
    payment_test_mode = models.BooleanField(default=True, help_text="Use test mode for payments")
    
    # Student Admission Configuration
    enable_online_admission = models.BooleanField(default=False, help_text="Enable online student admission")
    admission_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    require_admission_approval = models.BooleanField(default=True, help_text="Require admin approval for admissions")
    max_students_per_class = models.IntegerField(
        default=40,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Maximum number of students allowed per class"
    )
    
    # Report Card Configuration
    report_card_header = models.TextField(blank=True, help_text="Custom header text for report cards")
    report_card_footer = models.TextField(blank=True, help_text="Custom footer text for report cards")
    principal_signature = models.ImageField(upload_to='system/signatures/', blank=True, null=True)
    show_student_photo_on_report = models.BooleanField(default=True)
    
    # Backup & Maintenance
    auto_backup_enabled = models.BooleanField(default=False)
    backup_frequency_days = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="Number of days between automatic backups"
    )
    maintenance_mode = models.BooleanField(default=False, help_text="Put system in maintenance mode")
    maintenance_message = models.TextField(
        blank=True,
        default="System is under maintenance. Please check back later."
    )
    
    # Security & Privacy
    require_email_verification = models.BooleanField(default=False)
    session_timeout_minutes = models.IntegerField(
        default=60,
        validators=[MinValueValidator(5), MaxValueValidator(1440)],
        help_text="Auto-logout after inactivity (minutes)"
    )
    max_login_attempts = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    
    # Metadata
    last_modified = models.DateTimeField(auto_now=True)
    last_modified_by = models.ForeignKey(
        'CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settings_modifications'
    )
    
    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)"""
        if not self.pk and SystemSettings.objects.exists():
            # If trying to create a new instance when one exists, update existing instead
            existing = SystemSettings.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate settings"""
        if self.email_use_tls and self.email_use_ssl:
            raise ValidationError("Cannot use both TLS and SSL for email")
        
        # Validate grading system JSON structure
        if self.grading_system:
            try:
                for grade, config in self.grading_system.items():
                    if not all(k in config for k in ['min_score', 'max_score', 'remark']):
                        raise ValidationError(f"Invalid grading configuration for grade {grade}")
            except (TypeError, AttributeError):
                raise ValidationError("Invalid grading system format")
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        if created:
            # Set default grading system
            settings.grading_system = cls.get_default_grading_system()
            settings.save()
        return settings
    
    @staticmethod
    def get_default_grading_system():
        """Return the default grading scale"""
        return {
            "A": {"min_score": 70, "max_score": 100, "remark": "Excellent"},
            "B": {"min_score": 60, "max_score": 69, "remark": "Very Good"},
            "C": {"min_score": 50, "max_score": 59, "remark": "Good"},
            "D": {"min_score": 40, "max_score": 49, "remark": "Fair"},
            "E": {"min_score": 30, "max_score": 39, "remark": "Poor"},
            "F": {"min_score": 0, "max_score": 29, "remark": "Fail"}
        }
    
    def get_grade(self, score):
        """Get grade for a given score"""
        if not self.grading_system:
            return None
        
        for grade, config in self.grading_system.items():
            if config['min_score'] <= score <= config['max_score']:
                return {
                    'grade': grade,
                    'remark': config.get('remark', '')
                }
        return None
    
    def __str__(self):
        return f"{self.school_name} - System Settings"
