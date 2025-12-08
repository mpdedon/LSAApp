from django.db import models, transaction
from django.core.validators import MaxValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db.models import Sum, Avg, Q, F
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.html import strip_tags
from datetime import date, timedelta
from decimal import Decimal
from django_ckeditor_5.fields import CKEditor5Field
import json


# Create your models here.

class Session(models.Model):
    start_date = models.DateField(unique=True)
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.is_active and not self._state.adding: 
            # Get current active session if it exists and is not self
            current_active = Session.objects.filter(is_active=True).exclude(pk=self.pk).first()
            if current_active:
                current_active.is_active = False
                current_active.save(update_fields=['is_active']) # Avoid recursion
        elif self._state.adding and self.is_active: 
             Session.objects.filter(is_active=True).update(is_active=False) # Deactivate all others
        super().save(*args, **kwargs)

    def get_next_session(self):
        """Finds the next session based on start date."""
        return Session.objects.filter(start_date__gt=self.start_date).order_by('start_date').first()

    def __str__(self):
        return self.name or f"Session {self.pk}"
    
    @property
    def name(self): 
        if self.start_date and self.end_date:
            return f"{self.start_date.year}-{self.end_date.year} Session"
        return f"Session ID {self.pk}"

    class Meta:
        ordering = ['start_date']

    def save(self, *args, **kwargs):
        if self.is_active:
            Session.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)


# Custom manager for profile models to safely handle create() calls that may
# be invoked when a profile already exists (helpful during tests or idempotent setups).
class ProfileManager(models.Manager):
    def create(self, **kwargs):
        """
        If a 'user' kwarg is provided and a profile with that user already exists,
        update and return it instead of raising IntegrityError.
        Otherwise, fall back to normal create behavior.
        """
        user = kwargs.get('user')
        if user is not None:
            existing = self.filter(user=user).first()
            if existing:
                # Update provided fields on existing instance
                for k, v in kwargs.items():
                    setattr(existing, k, v)
                existing.save()
                return existing
        return super().create(**kwargs)

    @classmethod
    def get_current_session(cls):
        return cls.objects.filter(is_active=True).order_by('-start_date').first()

    def get_next_session(self):
        """Gets the session immediately following this one."""
        return Session.objects.filter(start_date__gt=self.end_date).order_by('start_date').first()


class Term(models.Model):

    TERM_OPTIONS = [
        ('First Term', 'First'),
        ('Second Term', 'Second'),
        ('Third Term', 'Third'),
    ]

    TERM_ORDER = {
        'First Term': 1,
        'Second Term': 2,
        'Third Term': 3
    }

    session = models.ForeignKey(Session, related_name='terms', on_delete=models.CASCADE)
    name = models.CharField(max_length=20, choices=TERM_OPTIONS)
    start_date = models.DateField()
    end_date = models.DateField()
    order = models.IntegerField(editable=False, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    original_is_active = None

    class Meta:
        unique_together = ('session', 'name') 
        ordering = ['session__start_date', 'order']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store the initial state when the model instance is loaded
        self._original_is_active = self.is_active

    @transaction.atomic 
    def save(self, *args, **kwargs):
        # Set order automatically based on name
        self.order = self.TERM_ORDER.get(self.name)

        # Activation logic
        was_active_before_save = self._original_is_active
        is_being_activated = self.is_active and not was_active_before_save

        if is_being_activated:
            with transaction.atomic():
                # Deactivate other terms in the SAME session
                Term.objects.filter(
                    session=self.session, is_active=True
                ).exclude(pk=self.pk).update(is_active=False)
                # Ensure the parent session is active
                if not self.session.is_active:
                    self.session.is_active = True
                    self.session.save() # This might trigger Session's save logic
        super().save(*args, **kwargs)
        self._original_is_active = self.is_active
    
    def activate(self):
        """Explicit method to activate this term and deactivate others in the session."""
        if not self.is_active:
            self.is_active = True
            self.save() # The save method now contains the deactivation logic

    def deactivate(self): # Also check this one if you use it
        """Explicit method to deactivate this term."""
        if self.is_active:
            self.is_active = False
            self.save()
            
    def get_term_weeks(term):
        term_days = []
        current_date = term.start_date
        while current_date <= term.end_date:
            term_days.append(current_date)
            current_date += timedelta(days=1)
        
        # Group by weeks
        weeks = [term_days[i:i+7] for i in range(0, len(term_days), 7)]
        return weeks

    @cached_property # Calculate once per instance, cache the result
    def actual_school_days_count(self):
        """
        Calculates the number of actual school days (Mon-Fri, excluding holidays)
        within this term's date range.
        """
        start_date = self.start_date
        end_date = self.end_date

        if not start_date or not end_date or start_date > end_date:
            return 0 # Invalid range

        # Fetch holidays for this term ONCE
        term_holidays = set(Holiday.objects.filter(term=self).values_list('date', flat=True))

        count = 0
        current_date = start_date
        while current_date <= end_date:
            # Check weekday and not a holiday
            if current_date.weekday() < 5 and current_date not in term_holidays:
                count += 1
            current_date += timedelta(days=1)
        return count

    # --- Optional: Method to get the list of school day dates ---
    @cached_property
    def get_actual_school_day_dates(self):
        """
        Returns a list of actual school day dates (Mon-Fri, excluding holidays)
        within this term's date range.
        """
        start_date = self.start_date
        end_date = self.end_date
        dates = []
        if not start_date or not end_date or start_date > end_date:
            return dates

        term_holidays = set(Holiday.objects.filter(term=self).values_list('date', flat=True))
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5 and current_date not in term_holidays:
                dates.append(current_date)
            current_date += timedelta(days=1)
        return dates
    
    @classmethod
    def get_current_term(cls):
        """Gets the currently active term. Assumes only one term is active at a time."""
        return cls.objects.filter(is_active=True).select_related('session').first()

    def get_next_term_in_session(self):
        """Gets the next term within the SAME session based on order."""
        if self.order is None: return None
        return Term.objects.filter(
            session=self.session,
            order__gt=self.order
        ).order_by('order').select_related('session').first()

    def get_first_term_of_next_session(self):
        """Gets the first term (order=1) of the next chronological session."""
        next_session = self.session.get_next_session()
        if next_session:
            return Term.objects.filter(
                session=next_session,
                order=1 # Assuming first term is order 1
            ).select_related('session').first()
        return None

    @classmethod
    def get_next_term(cls, current_term_instance=None):
        """
        Determines the next logical term.
        If current_term is provided, it finds the next one.
        If not, it implies finding the next for the *globally* current term.
        """
        if not current_term_instance:
            current_term_instance = cls.get_current_term()

        if not current_term_instance:
            return None # No current term, so no "next" term

        # Try to find next term in the same session
        next_in_session = current_term_instance.get_next_term_in_session()
        if next_in_session:
            return next_in_session

        # If no next term in current session, try first term of next session
        return current_term_instance.get_first_term_of_next_session()

    def __str__(self):
        return f"{self.name} ({self.session.name if self.session else 'No Session'})"

# class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username field must be set")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(username, password, **extra_fields)

class CustomUser(AbstractUser):

    USER_ROLES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('guardian', 'Guardian'),
        ('accountant', 'Accountant'),
        ('admin', 'Admin'),
    )

    role = models.CharField(max_length=20, choices=USER_ROLES)

    def __str__(self):
        return self.username


class Student(models.Model):

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('dormant', 'Dormant'),
        ('left', 'Left School'),
    ]
 
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True, related_name='student')    
    LSA_number = models.CharField(max_length=20, unique=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', default='images/default.jpg', null=True, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    student_guardian = models.ForeignKey('Guardian', on_delete=models.SET_NULL, null=True, related_name='students')
    relationship = models.CharField(max_length=50)
    current_class = models.ForeignKey('Class', on_delete=models.SET_NULL, null=True, blank=True, related_name='enrolled_students', default=None, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    promotion_history = models.TextField(blank=True)  # To store history of movements as JSON

    def __str__(self):
        return self.user.get_full_name()
    
    def save(self, *args, **kwargs):
        if not self.LSA_number:
            self.set_LSA_number()
        super().save(*args, **kwargs)

    def set_LSA_number(self):
        # Use `-pk` for descending order to get the last entry
        last_student = Student.objects.order_by('-pk').first()
        if last_student and last_student.LSA_number:
            last_id = int(last_student.LSA_number.split('/')[-1])
            new_id = f'LSA/S/{last_id + 1:03d}'
        else:
            new_id = 'LSA/S/001'  # Start from 001 if no previous records exist
        self.LSA_number = new_id

    # Use custom manager to make create() idempotent in test/setup scenarios
    objects = ProfileManager()

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def promote(self):
        """Promote the student to the next class."""
        next_class = self.get_next_class()
        if next_class:
            self.update_history('Promoted', self.current_class, next_class)
            self.current_class = next_class
            self.save()

    def repeat(self):
        """Mark the student as repeating the same class."""
        self.update_history('Repeated', self.current_class, self.current_class)
        self.save()

    def demote(self):
        """Demote the student to the previous class."""
        previous_class = self.get_previous_class()
        if previous_class:
            self.update_history('Demoted', self.current_class, previous_class)
            self.current_class = previous_class
            self.save()

    def mark_dormant(self):
        """Mark the student as dormant."""
        self.update_history('Dormant', self.current_class, None)
        self.status = 'dormant'
        self.save()

    def mark_active(self):
        """Mark the student as Active"""
        self.update_history('Active', self.current_class, None)
        self.status = 'active'
        self.save()
        
    def mark_left(self):
        """Mark the student as left the school."""
        self.update_history('Left School', self.current_class, None)
        self.status = 'left'
        self.current_class = None
        self.save()

    def update_history(self, action, from_class, to_class):
        """Log promotions or other actions."""
        history = json.loads(self.promotion_history or '[]')
        history.append({
            'action': action,
            'from_class': str(from_class),
            'to_class': str(to_class),
            'date': timezone.now().isoformat(),
        })
        self.promotion_history = json.dumps(history)
        self.save()

    def get_next_class(self):
        """Get the next class (implement logic as per your class structure)."""
        return Class.objects.filter(order__gt=self.current_class.order).order_by('order').first()

    def get_previous_class(self):
        """Get the previous class (implement logic as per your class structure)."""
        return Class.objects.filter(order__lt=self.current_class.order).order_by('-order').first()


class Guardian(models.Model):

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('dormant', 'Dormant'),
        ('left', 'Left School'),
    ]

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True, related_name='guardian')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    profile_image = models.ImageField(upload_to='profile_images/', default='images/default.jpg', null=True, blank=True)
    contact = models.CharField(max_length=15, null=True)
    address = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def student_count(self):
        return self.students.count()  

    def __str__(self):
        return self.user.username

    # Use custom manager to tolerate repeated create() calls (idempotent)
    objects = ProfileManager()


class Teacher(models.Model):

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('dormant', 'Dormant'),
        ('left', 'Left School'),
    ]

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True, related_name='teacher')
    employee_id = models.CharField(max_length=20, unique=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', default='images/default.jpg', null=True, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    contact = models.CharField(max_length=15, null=True)
    address = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def current_classes(self):
        """Retrieve all classes where the teacher is a form teacher."""
        form_teacher_assignments = TeacherAssignment.objects.filter(teacher=self, is_form_teacher=True)
        return Class.objects.filter(teacherassignment__in=form_teacher_assignments) if form_teacher_assignments.exists() else Class.objects.none()


    def assigned_classes(self):
        """Retrieve all classes the teacher is assigned to, including form classes and subject-teaching classes."""
        form_classes = Class.objects.filter(teacherassignment__teacher=self).distinct()
        subject_classes = Class.objects.filter(subjectassignment__teacher=self).distinct()
        # Combine the two QuerySets, removing duplicates
        all_classes = form_classes | subject_classes
        return all_classes

    def subjects_taught(self):
        """Retrieve all subjects taught by the teacher across all classes."""
        return Subject.objects.filter(subjectassignment__teacher=self).distinct()

    def form_class_subjects(self):
        """Retrieve subjects assigned to the class where the teacher is the form teacher."""

        current_session = Session.objects.filter(is_active=True).first()
        current_term = Term.objects.filter(is_active=True).first()
        form_classes = self.current_classes()

        if form_classes:
            for class_instance in form_classes:
                subjects = Subject.objects.filter(
                        class_assignments__class_assigned=class_instance,
                        class_assignments__session=current_session,
                        class_assignments__term=current_term
                    ).distinct()
            return subjects
        return Subject.objects.none()
    
    def assigned_subjects(self):
        """Retrieve all subjects in form classes and other classes for assignments etc."""
        subject_teaching = self.subjects_taught()
        class_teaching = self.form_class_subjects()
        all_subjects = subject_teaching | class_teaching
        return all_subjects
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.employee_id}"
    
    def save(self, *args, **kwargs):
        if not self.employee_id:
            self.set_employee_id()
        super().save(*args, **kwargs)

    def set_employee_id(self):
        # Use `pk` instead of `id`
        last_teacher = Teacher.objects.all().order_by('pk').last()
        if last_teacher:
            last_id = int(last_teacher.employee_id.split('/')[-1])
            new_id = f'LSA/T/{last_id + 1:03d}'
        else:
            new_id = 'LSA/T/001'
        self.employee_id = new_id

    # Use custom manager to tolerate repeated create() calls (idempotent)
    objects = ProfileManager()

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
    )


class Class(models.Model):

    LEVEL_CHOICES = [
        ('Primary', 'Primary'),
        ('Secondary', 'Secondary'),
    ]

    name = models.CharField(max_length=20, unique=True)
    school_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, unique=False, default=None)
    description = models.TextField(blank=True, null=True)
    subjects = models.ManyToManyField('Subject', related_name='class_set', blank=True)  
    students = models.ManyToManyField('Student', related_name='classes', blank=True)
    order = models.PositiveIntegerField(null=True, blank=True, unique=True)

    def form_teacher(self):
        """Retrieve the teacher who is the form teacher for this class."""
        try:
            # Use select_related to fetch related teacher and user efficiently in one go
            form_teacher_assignment = TeacherAssignment.objects.select_related('teacher__user').filter(
                class_assigned=self,
                is_form_teacher=True
            ).first()
            return form_teacher_assignment.teacher if form_teacher_assignment else None
        except NameError: # Handle case where TeacherAssignment is not defined/imported
             print("Warning: TeacherAssignment model not found or imported.")
             return None
        except AttributeError: # Handle case where teacher or user is missing
             print("Warning: Teacher or User missing for form teacher assignment.")
             return None
    
    def next_class(self):
        if self.order is None:
            return None
        try:
            return Class.objects.filter(order__gt=self.order).order_by('order').first()
        except Class.DoesNotExist:
            return None

    def previous_class(self):
        if self.order is None or self.order == 0: 
            return None
        try:
            # Find the highest order less than the current one
            return Class.objects.filter(order__lt=self.order).order_by('-order').first()
        except Class.DoesNotExist:
            return None

    def save(self, *args, **kwargs):
        # Ensure `school_level` is never left as None (migrations created the DB column NOT NULL).
        # Some tests/create calls omit school_level; default to a sensible value here so
        # the DB insert doesn't fail due to a NOT NULL constraint.
        if not self.school_level:
            self.school_level = 'Primary'

        # Handle the auto-increment of the `order` field
        if self.order is None:
            # Use aggregate safely, handling the None case
            result = Class.objects.aggregate(max_order=models.Max('order'))
            max_order = result.get('max_order') 
            self.order = 1 if max_order is None else max_order + 1

        super().save(*args, **kwargs) 
        
        try:
            class_subject_assignments = ClassSubjectAssignment.objects.filter(class_assigned=self)
            assigned_subjects_ids = [assignment.subject.id for assignment in class_subject_assignments]
            # Use set() for efficiency if you are adding/removing individually
            self.subjects.set(assigned_subjects_ids)

        except NameError:
             print("Warning: ClassSubjectAssignment model not found or imported. Subject syncing skipped.")

    def subject_count(self):
        return self.subjects.count()
    
    def student_count(self):
        return self.students.count()
    
    def __str__(self):
        return f"{self.name} ({self.school_level})"


class Subject(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    subject_weight = models.IntegerField(default=2)
    classes = models.ManyToManyField(Class, related_name='subjects_set', default=None)
    students = models.ManyToManyField('Student', related_name='subjects', default=None)
   
    def __str__(self):
        return self.name


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    class_enrolled = models.ForeignKey(Class, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student.name} - {self.class_enrolled.name} ({self.term.name}, {self.session.name})"
    

class Attendance(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    date = models.DateField()
    term = models.ForeignKey(Term, on_delete=models.CASCADE, default=None)
    class_assigned = models.ForeignKey(Class, on_delete=models.CASCADE, default=None)
    is_present = models.BooleanField(default=False)
    
    
    class Meta:
        unique_together = ('student', 'date', 'class_assigned', 'term')

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.date}"
    

class TeacherAssignment(models.Model):
    class_assigned = models.ForeignKey(Class, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, default=None)
    term = models.ForeignKey('Term', on_delete=models.CASCADE, default=None)
    is_form_teacher = models.BooleanField(default=False)

    class Meta:
        unique_together = ('class_assigned', 'teacher', 'session', 'term', 'is_form_teacher')

    ordering = ['session__start_date', 'term__order', 'class_assigned__name', 'teacher__user__last_name']
    def __str__(self):
        form_indicator = " (Form Teacher)" if self.is_form_teacher else ""
        return f"{self.teacher} - {self.class_assigned}{form_indicator} ({self.session.name} - {self.term.name})"


class SubjectAssignment(models.Model):
    class_assigned = models.ForeignKey(Class, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, null=True, blank=True)
    term = models.ForeignKey(Term, on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('class_assigned', 'subject', 'teacher', 'term', 'session')

    def __str__(self):
        return f"{self.subject} - {self.class_assigned} ({self.teacher} - {self.session.name} - {self.term.name})"


class ClassSubjectAssignment(models.Model):
    class_assigned = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="subject_assignments")
    subject = models.ForeignKey(Subject, related_name='class_assignments', on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('class_assigned', 'subject', 'session', 'term')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Ensure the subject is added to the Class.subjects field
        if not self.class_assigned.subjects.filter(pk=self.subject.pk).exists():
            self.class_assigned.subjects.add(self.subject)

    def delete(self, *args, **kwargs):
        # Remove the subject from Class.subjects if no other assignments exist
        super().delete(*args, **kwargs)
        if not ClassSubjectAssignment.objects.filter(
            class_assigned=self.class_assigned,
            subject=self.subject
        ).exists():
            self.class_assigned.subjects.remove(self.subject)

    def __str__(self):
        return f"{self.subject.name} - {self.class_assigned.name} ({self.session.name} - {self.term.name})"
    

class Assignment(models.Model):

    RESULT_FIELD_CHOICES = [
        ('', 'Do Not Link to Term Result'),
        ('assignment', 'Assignment (Max 10)'),
    ]
    result_field_mapping = models.CharField(
        max_length=50,
        choices=RESULT_FIELD_CHOICES,
        null=True,
        blank=True,
        help_text="If set, scores from this assessment will populate the selected field in the student's term result."
    )
    term = models.ForeignKey('Term', on_delete=models.CASCADE, default=1)
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE, default=1)
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=500, null=True, blank=True)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    class_assigned = models.ForeignKey('Class', related_name='assignments', on_delete=models.CASCADE)
    duration = models.IntegerField(null=True, blank=True)
    due_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)  # To mark assignments as active/inactive
    shuffle_questions = models.BooleanField(default=False)


    def has_expired(self):
        """Checks if the assignment is past its due date."""
        return timezone.now() > self.due_date
    
    def get_total_marks(self):
        return self.questions.count()
    
    def __str__(self):
        return f"{self.title} = {self.subject} = {self.class_assigned} = {self.due_date}"


class Question(models.Model):
    QUESTION_TYPES = (
        ('SCQ', 'Single Choice Question'),
        ('MCQ', 'Multiple Choice Question'),
        ('ES', 'Essay Question'),
    )
    
    assignment = models.ForeignKey(Assignment, related_name='questions', on_delete=models.CASCADE)
    question_type = models.CharField(max_length=3, choices=QUESTION_TYPES)
    question_text = models.TextField()
    options = models.JSONField(null=True, blank=True)
    correct_answer = models.CharField(max_length=255, null=True, blank=True)  

    @property
    def options_list(self):
        """Returns options as a Python list."""
        if self.options:
            try:
                return json.loads(self.options)
            except json.JSONDecodeError:
                return []
        return []
     
    def __str__(self):
        return self.question_text


class AssignmentSubmission(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, related_name='submissions', on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(default=timezone.now)
    answers = models.JSONField(null=True, blank=True) 
    grade = models.FloatField(null=True, blank=True)  
    feedback = models.TextField(null=True, blank=True)  
    is_completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    force_submitted_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def calculate_grade(self):
        """
        Automatically grade SCQ and MCQ and calculate total score.
        """
        questions = self.assignment.question_set.all()
        auto_grade = 0
        essay_questions = []

        for question in questions:
            if question.question_type in ['SCQ', 'MCQ']:
                # Check if the student's answer matches the correct answer
                student_answer = self.answers.get(str(question.id))
                if student_answer == question.correct_answer:
                    auto_grade += 1  # Assume 1 point per correct answer
            elif question.question_type == 'Essay':
                # Append essay questions for manual grading
                essay_questions.append(question)

        # Update grade for auto-graded questions only
        self.grade = auto_grade  # Total grade will include manual grading later
        self.save()
        return essay_questions
    
    def __str__(self):
        return f"Submission by {self.student.user.get_full_name} for {self.assignment.title}"
    

class OnlineQuestion(models.Model):
    QUESTION_TYPES = (
        ('SCQ', 'Single Choice Question'),
        ('MCQ', 'Multiple Choice Question'),
        ('ES', 'Essay Question'),
    )
    
    question_type = models.CharField(max_length=3, choices=QUESTION_TYPES)
    question_text = models.TextField()
    options = models.JSONField(null=True, blank=True)  # For SCQ/MCQ, store choices as JSON
    correct_answer = models.CharField(max_length=255, null=True, blank=True)  # For SCQ/MCQ correct answer
    points = models.PositiveIntegerField(default=1, blank=True, null=True)

    def __str__(self):
        return self.question_text
    
    def options_list(self):
        if self.options and isinstance(self.options, list):
            return self.options
        elif self.options and isinstance(self.options, str):
            try:
                return json.loads(self.options)
            except json.JSONDecodeError:
                return []
        return []

    def is_option_correct(self, submitted_answer):
        if not self.correct_answer or submitted_answer is None:
            return False

        if self.question_type == 'SCQ':
            return str(submitted_answer).strip().lower() == str(self.correct_answer).strip().lower()
        elif self.question_type == 'MCQ':
            # For MCQ, self.correct_answer stores comma or space-separated correct options
            # submitted_answer here for MCQ would be a LIST of strings from request.POST.getlist()
            if not isinstance(submitted_answer, list): 
                return False 
            
            correct_options_set = set()
            if self.correct_answer:
                if ',' in self.correct_answer:
                    correct_options_set = set(opt.strip().lower() for opt in self.correct_answer.split(','))
                else: # Assume space separated
                    correct_options_set = set(opt.strip().lower() for opt in self.correct_answer.split(' ') if opt.strip())
            
            submitted_options_set = set(str(opt).strip().lower() for opt in submitted_answer)
            
            return submitted_options_set == correct_options_set and bool(correct_options_set) # Match and ensure not empty set comparison
        
        # For ES, this method isn't directly applicable for boolean correctness
        return False
    
class Assessment(models.Model):

    RESULT_FIELD_CHOICES = [
        ('', 'Do Not Link to Term Result'),
        ('continuous_assessment_1', 'Continuous Assessment 1 (Max 10)'),
        ('continuous_assessment_2', 'Continuous Assessment 2 (Max 10)'),
        ('continuous_assessment_3', 'Continuous Assessment 3 (Max 10)'),
    ]
    result_field_mapping = models.CharField(
        max_length=50,
        choices=RESULT_FIELD_CHOICES,
        null=True,
        blank=True,
        help_text="If set, scores from this assessment will populate the selected field in the student's term result."
    )
    term = models.ForeignKey('Term', on_delete=models.CASCADE, default=1)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)
    short_description = models.CharField(max_length=500, null=True, blank=True)
    score = models.IntegerField(default=0, null=True, blank=True)
    total_marks = models.PositiveIntegerField(null=True, blank=True, help_text="Total marks possible for this assessment.")
    class_assigned = models.ForeignKey('Class', on_delete=models.CASCADE, default=None)
    due_date = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)
    questions = models.ManyToManyField('OnlineQuestion', related_name='assessments', blank=True)
    is_approved = models.BooleanField(default=False)  # New field
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_assessments")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_assessments")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    shuffle_questions = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} - {self.subject.name}"

    @property
    def is_due(self):
        if self.due_date:
            return timezone.now() > self.due_date
        return False

    @property
    def get_total_marks(self):
        return self.questions.aggregate(total_marks=Sum('points'))['total_marks'] or 0


class AssessmentSubmission(models.Model):
    assessment = models.ForeignKey('Assessment', on_delete=models.CASCADE, related_name='submissions_for_assessment')
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    answers = models.JSONField(null=True, blank=True) 
    score = models.IntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_graded = models.BooleanField(default=False)
    requires_manual_review = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    force_submitted_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    attempt_number = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(3)], help_text="The attempt number for this submission.")

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.assessment.title}"
    
    class Meta:
        unique_together = ('student', 'assessment', 'attempt_number')
        

class Exam(models.Model):

    RESULT_FIELD_CHOICES = [
        ('', 'Do Not Link to Term Result'),
        ('exam_score', 'Exam Score (Max 40)'),
    ]
    result_field_mapping = models.CharField(
        max_length=50,
        choices=RESULT_FIELD_CHOICES,
        null=True,
        blank=True,
        help_text="Scores from this exam will populate the 'Exam Score' field in the student's term result."
    )
    term = models.ForeignKey('Term', on_delete=models.CASCADE, default=1)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)
    short_description = models.CharField(max_length=500, null=True, blank=True)
    score = models.IntegerField(default=0, null=True, blank=True)
    total_marks = models.PositiveIntegerField(null=True, blank=True, help_text="Total marks possible for this assessment.")
    class_assigned = models.ForeignKey('Class', on_delete=models.CASCADE, default=None)
    due_date = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)
    questions = models.ManyToManyField('OnlineQuestion', related_name='exams', blank=True)
    is_approved = models.BooleanField(default=False)  # New field
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_exams")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_exams")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    shuffle_questions = models.BooleanField(default=False)


    def __str__(self):
        return f"{self.title} - {self.subject.name}"

    @property
    def is_due(self):
        """Check if the online exam is due for submission."""
        if self.due_date:
            return timezone.now() > self.due_date
        return False

    @property
    def get_total_marks(self):
        return self.questions.aggregate(total_marks=Sum('points'))['total_marks'] or 0

class ExamSubmission(models.Model):
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='submissions_for_exam')
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    answers = models.JSONField(null=True, blank=True)  
    score = models.IntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_graded = models.BooleanField(default=False)
    requires_manual_review = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    force_submitted_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    attempt_number = models.PositiveIntegerField(default=1, validators=[MaxValueValidator(3)], help_text="The attempt number for this submission.")
    
    class Meta:
        unique_together = ('student', 'exam', 'attempt_number')

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.exam.title}"


class AcademicAlert(models.Model):
    ALERT_TYPE_CHOICES = [
        ('assignment_available', 'Assignment Available'),
        ('assignment_submission', 'Assignment Submitted'),
        ('assessment_available', 'Assessment Available'),
        ('assessment_submission', 'Assessment Submitted'),
        ('exam_available', 'Exam Available'),
        ('exam_submission', 'Exam Submitted'),
        ('general_announcement', 'General Announcement')
    ]
    
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    source_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="generated_academic_alerts")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='academic_alerts')
    due_date = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)
    is_done = models.BooleanField(default=False)
    date_submitted = models.DateTimeField(null=True, blank=True)
    total_grade = models.FloatField(null=True, blank=True)
    related_object_id = models.IntegerField()  
    is_read = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)

    def get_related_url(self):
        """Generate URL to the related object (assignment, assessment, or exam)."""
        if self.alert_type == 'assignment':
            return f"/assignments/{self.related_object_id}/"
        elif self.alert_type == 'assessment':
            return f"/assessments/{self.related_object_id}/"
        elif self.alert_type == 'exam':
            return f"/exams/{self.related_object_id}/"
        return "#"

    def __str__(self):
        source_name = self.source_user.get_full_name() or self.source_user.username if self.source_user else "School Admin"
        return f"{self.get_alert_type_display()} for {self.student.user.username} from {source_name}: {self.title}"

    class Meta:
        ordering = ['-date_created']


class SubjectResult(models.Model):
    """
    Stores all scores for ONE subject within ONE term's result sheet.
    This is the lowest level of academic record.
    """
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    result = models.ForeignKey('Result', on_delete=models.CASCADE, related_name='subject_results')
    
    continuous_assessment_1 = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, validators=[MaxValueValidator(10.0)])
    continuous_assessment_2 = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, validators=[MaxValueValidator(10.0)])
    continuous_assessment_3 = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, validators=[MaxValueValidator(10.0)])
    assignment = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, validators=[MaxValueValidator(10.0)])
    oral_test = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, validators=[MaxValueValidator(20.0)])
    exam_score = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, validators=[MaxValueValidator(40.0)])
    
    is_finalized = models.BooleanField(default=False)

    class Meta:
        unique_together = ('result', 'subject')
        ordering = ['subject__name']

    def __str__(self):
        student_name = self.result.student.user.get_full_name() if self.result.student else "Unknown Student"
        subject_name = self.subject.name if self.subject else "Unknown Subject"
        status = 'Finalized' if self.is_finalized else 'Draft'
        return f"{student_name} - {subject_name} ({status})"

    def total_score(self) -> Decimal:
        """Calculates the total score for this subject. Returns a Decimal."""
        total = sum(filter(None, [
            self.continuous_assessment_1, self.continuous_assessment_2, self.continuous_assessment_3,
            self.assignment, self.oral_test, self.exam_score
        ]))
        return Decimal(total).quantize(Decimal('0.1'))

    def calculate_grade(self) -> str:
        """Determines the letter grade based on the total score."""
        score = self.total_score()
        if score >= 80:
            return 'A'
        elif score >= 65:
            return 'B'
        elif score >= 50:
            return 'C'
        elif score >= 45:
            return 'D'
        elif score >= 40:
            return 'E'
        else:
            return 'F'

    def calculate_grade_point(self) -> Decimal:
        """Determines the grade point (e.g., for GPA calculation)."""
        score = self.total_score()
        # Use the same thresholds as calculate_grade to keep consistency
        if score >= 80:
            return Decimal('5.0')
        elif score >= 65:
            return Decimal('4.0')
        elif score >= 50:
            return Decimal('3.0')
        elif score >= 45:
            return Decimal('2.0')
        elif score >= 40:
            return Decimal('1.0')
        else:
            return Decimal('0.0')

    @classmethod
    def get_class_average(cls, subject, term, class_obj) -> Decimal:
        """Calculates the average total score for a subject in a specific class and term."""
        subject_results_in_class = cls.objects.filter(
            subject=subject,
            result__term=term,
            result__student__current_class=class_obj)
        
        aggregation_queryset = subject_results_in_class.annotate(
            total_per_student=(
                Coalesce(F('continuous_assessment_1'), Decimal(0)) +
                Coalesce(F('continuous_assessment_2'), Decimal(0)) +
                Coalesce(F('continuous_assessment_3'), Decimal(0)) +
                Coalesce(F('assignment'), Decimal(0)) +
                Coalesce(F('oral_test'), Decimal(0)) +
                Coalesce(F('exam_score'), Decimal(0))
            )
        )
        
        aggregation = aggregation_queryset.aggregate(class_avg=Avg('total_per_student'))
        avg = aggregation.get('class_avg')
        return avg.quantize(Decimal('0.1')) if avg is not None else Decimal('0.0')
    

class Result(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    term = models.ForeignKey('Term', on_delete=models.CASCADE)
    teacher_remarks = models.TextField(null=True, blank=True)
    principal_remarks = models.TextField(null=True, blank=True)

    # Attendance
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Affective (Character) Skills - 4 Key Areas
    punctuality = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    diligence = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    cooperation = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    respectfulness = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])

    # Psychomotor (Physical) Skills - 4 Key Areas
    sportsmanship = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    agility = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    creativity = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    hand_eye_coordination = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])

    # Continuous assessments and assignments for each subject
    subjects = models.ManyToManyField('Subject', through='SubjectResult')

    is_approved = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False, help_text="Controls visibility to students/parents")
    
    total_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    term_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    performance_change = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Percentage change in average score from the previous term.")

    class Meta:
        unique_together = ('student', 'term')
        ordering = ['-term__start_date']

    def __str__(self):
        return f"Result for {self.student.user.get_full_name()} - {self.term}"

    def get_previous_term_result(self):
        """Finds the Result object for the same student from the immediately preceding term."""
        previous_terms = Term.objects.filter(start_date__lt=self.term.start_date).order_by('-start_date')
        for prev_term in previous_terms:
            previous_result = Result.objects.filter(student=self.student, term=prev_term).first()
            if previous_result and previous_result.average_score is not None:
                return previous_result
        return None

    def calculate_term_summary(self):
        """Calculates all summary fields for this term and saves the instance."""
        subject_results = self.subject_results.all().select_related('subject')
        scored_subjects = [sr for sr in subject_results if sr.total_score() > 0]
        
        if not scored_subjects:
            self.total_score, self.average_score, self.term_gpa = Decimal('0.00'), Decimal('0.00'), Decimal('0.00')
        else:
            self.total_score = sum(sr.total_score() for sr in scored_subjects)
            self.average_score = self.total_score / len(scored_subjects)
            # GPA Calculation
            total_weighted_points, total_weights = Decimal('0.0'), Decimal('0.0')
            for sr in scored_subjects:
                weight = Decimal(getattr(sr.subject, 'subject_weight', 1))
                total_weighted_points += Decimal(sr.calculate_grade_point()) * weight
                total_weights += weight
            self.term_gpa = (total_weighted_points / total_weights) if total_weights > 0 else Decimal('0.00')

        # Calculate Performance Change
        previous_result = self.get_previous_term_result()
        if previous_result and self.average_score is not None:
            prev_avg = previous_result.average_score
            if prev_avg > 0:
                change = ((self.average_score - prev_avg) / prev_avg) * 100
                self.performance_change = change
            elif self.average_score > 0:
                self.performance_change = Decimal('100.00') 
            else:
                self.performance_change = Decimal('0.00')
        else:
            self.performance_change = None 
        
        self.save()


class SessionalResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    
    subject_summary_json = models.JSONField(default=dict, blank=True)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sessional_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    performance_change = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'session')
        ordering = ['-session__start_date']

    def __str__(self):
        return f"Sessional Result for {self.student.user.get_full_name()} - {self.session}"

    def get_previous_sessional_result(self):
        """Finds the SessionalResult object for the same student from the previous session."""
        previous_sessions = Session.objects.filter(start_date__lt=self.session.start_date).order_by('-start_date')
        for prev_session in previous_sessions:
            previous_sessional_result = SessionalResult.objects.filter(student=self.student, session=prev_session).first()
            if previous_sessional_result and previous_sessional_result.average_score is not None:
                return previous_sessional_result
        return None

    def calculate_sessional_summary(self, save=True):
        """Calculates and saves the sessional GPA, average, and performance change."""
        terms_in_session = Term.objects.filter(session=self.session)

        # Prefer approved & published term results for official sessional records
        term_results = Result.objects.filter(
            student=self.student,
            term__in=terms_in_session,
            is_approved=True,
            is_published=True
        ).prefetch_related('subject_results__subject')

        # If no approved/published results exist (for example during just-in-time calculation
        # in views/tests), fall back to using any term results in this session so we can
        # compute a reasonable sessional GPA for display purposes.
        if not term_results.exists():
            term_results = Result.objects.filter(
                student=self.student,
                term__in=terms_in_session,
            ).prefetch_related('subject_results__subject')

        if not term_results:
            self.sessional_gpa, self.average_score, self.performance_change = Decimal('0.00'), Decimal('0.00'), None
            if save:
                self.save()
            return

        # Ensure each term result has summary fields calculated (just-in-time)
        for res in term_results:
            try:
                if res.average_score is None or res.term_gpa is None:
                    # Calculate and persist term summary so we can use its averages
                    res.calculate_term_summary()
            except Exception:
                # If calculating term summary fails for any reason, skip and continue
                pass

        # --- CORRECTED GPA CALCULATION (True Weighted Average) ---
        total_weighted_points_session = Decimal('0.0')
        total_weights_session = Decimal('0.0')
        for term_res in term_results:
            for sr in term_res.subject_results.all():
                if sr.total_score() > 0:
                    weight = Decimal(getattr(sr.subject, 'subject_weight', 1))
                    # This now uses the Decimal-returning method
                    total_weighted_points_session += sr.calculate_grade_point() * weight
                    total_weights_session += weight
        self.sessional_gpa = (total_weighted_points_session / total_weights_session) if total_weights_session > 0 else Decimal('0.00')
        
        # Calculate Sessional Average (Simple average of term averages)
        term_averages = [res.average_score for res in term_results if res.average_score is not None]
        self.average_score = sum(term_averages) / len(term_averages) if term_averages else Decimal('0.00')
        
        # Calculate Performance Change
        previous_sessional_result = self.get_previous_sessional_result()
        if previous_sessional_result and self.average_score is not None:
            prev_avg = previous_sessional_result.average_score
            if prev_avg > 0: self.performance_change = ((self.average_score - prev_avg) / prev_avg) * 100
            elif self.average_score > 0: self.performance_change = Decimal('100.00')
            else: self.performance_change = Decimal('0.00')
        else:
            self.performance_change = None

        if save: self.save()


class CumulativeRecord(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, primary_key=True, related_name='cumulative_record')
    cumulative_gpa = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    session_gpa_history_json = models.JSONField(default=dict, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cumulative Record for {self.student.user.get_full_name()}"

    def update_cumulative_gpa(self, save=True):
        sessional_results = SessionalResult.objects.filter(student=self.student, is_approved=True, sessional_gpa__isnull=False).order_by('session__start_date')
        gpa_history = {str(res.session.id): float(res.sessional_gpa) for res in sessional_results}
        sessional_gpas = [res.sessional_gpa for res in sessional_results]
        self.session_gpa_history_json = gpa_history
        if sessional_gpas:
            # Use Decimal quantize with ROUND_HALF_UP for predictable rounding to 2 decimal places
            from decimal import ROUND_HALF_UP
            avg = sum(sessional_gpas) / len(sessional_gpas)
            self.cumulative_gpa = avg.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            self.cumulative_gpa = Decimal('0.00')

        if save: self.save()


class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL,  on_delete=models.SET_NULL, null=True, related_name='sent_messages' )
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages')
    student_context = models.ForeignKey('Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='related_messages')
    parent_message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        sender_name = self.sender.username if self.sender else "[Deleted User]"
        recipient_name = self.recipient.username if self.recipient else "[Deleted User]"
        return f'From {sender_name} to {recipient_name}: "{self.title}"'
    

class SchoolDay(models.Model):
    term = models.ForeignKey('Term', on_delete=models.CASCADE, related_name='school_days')
    date = models.DateField()

    class Meta:
        # CRITICAL: Ensure uniqueness for DATE within a specific TERM
        unique_together = ('term', 'date')
        ordering = ['date'] # Order naturally

    def __str__(self):
        return f"{self.date.strftime('%Y-%m-%d')} ({self.term.name})"


class Holiday(models.Model):
    name = models.CharField(max_length=100)
    date = models.DateField()
    term = models.ForeignKey(Term, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} ({self.date})"
    

class Notification(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    audience = models.CharField(max_length=20, choices=[('all', 'All'), ('guardian', 'Guardians'), ('student', 'Students'), ('teacher', 'Teachers')], default='all')
    created_at = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True, help_text="Leave blank if the notification should not expire.")
    is_active = models.BooleanField(default=True)

    @property
    def is_expired(self):
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False

    def __str__(self):
        return self.title


class FeeAssignment(models.Model):
    class_instance = models.ForeignKey('Class', on_delete=models.CASCADE, default=None)
    term = models.ForeignKey('Term', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.class_instance.name} - {self.term} - {self.amount}"

    def calculate_net_fee(self, amount, discount, waiver):
        """Calculate the net fee for a student based on assignment."""
        amount = amount or Decimal('0.00')
        discount = discount or Decimal('0.00')

        if waiver:
            return Decimal('0.00')

        return max(amount - discount, Decimal('0.00'))
    
    def assign_fees_to_students(self):
        """Automatically assign fees to all students in the class."""
        students = self.class_instance.students.all()
        for student in students:
            StudentFeeRecord.objects.get_or_create(
                student=student,
                term=self.term,
                defaults={
                    'fee_assignment': self,
                    'amount': self.amount,
                    'discount': Decimal('0.00'),  # Default discount
                    'waiver': False,  # Default no waiver
                    'net_fee': self.calculate_net_fee(self.amount, Decimal('0.00'), False),  # Calculated net fee
                }
            )


class StudentFeeRecord(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='fee_records')
    term = models.ForeignKey('Term', on_delete=models.CASCADE, related_name='student_fee_records')
    fee_assignment = models.ForeignKey('FeeAssignment', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2) 
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0) 
    waiver = models.BooleanField(default=False)
    net_fee = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    class Meta:
        unique_together = ('student', 'term', 'fee_assignment')


    def calculate_net_fee(self):
        """Calculate the net fee after applying discount or waiver."""
        # Ensure that the amount and discount are correctly considered
        # Coerce possibly-string inputs into Decimal for robust calculation
        try:
            amount = Decimal(str(self.amount)) if self.amount is not None else Decimal('0.00')
        except Exception:
            amount = Decimal('0.00')
        try:
            discount = Decimal(str(self.discount)) if self.discount is not None else Decimal('0.00')
        except Exception:
            discount = Decimal('0.00')
        
        if self.waiver:
            return Decimal('0.00')

        # Calculate the net fee, ensuring it's never negative
        discount = min(amount, discount)
        return max(amount - discount, Decimal('0.00'))
    
    def save(self, *args, **kwargs):
        """Ensure the net fee is calculated before saving."""
        self.net_fee = self.calculate_net_fee()
        super().save(*args, **kwargs)

    def __str__(self):
        # Use student's name if available, otherwise student ID
        student_name = self.student.user.get_full_name() if hasattr(self.student, 'user') and self.student.user else f"Student {self.student.pk}"
        return f"{student_name} - {self.term} - Net: {self.net_fee}"

class FinancialRecord(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='financial_records')
    term = models.ForeignKey('Term', on_delete=models.CASCADE, related_name='financial_records')
    total_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False) 
    total_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False) 
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)
    archived = models.BooleanField(default=False, editable=False) 

    class Meta:
        unique_together = ('student', 'term')
        ordering = ['term__start_date', 'student__user__last_name'] 
        constraints = [
            models.CheckConstraint(check=Q(total_fee__gte=0), name='financial_record_positive_total_fee'),
            models.CheckConstraint(check=Q(total_discount__gte=0), name='financial_record_positive_total_discount'),
            models.CheckConstraint(check=Q(total_paid__gte=0), name='financial_record_positive_total_paid'),
        ]

    def update_record(self):
        """Calculates and updates fields based on related data. Called by signals."""
        # 1. Get fee details
        fee_record = StudentFeeRecord.objects.filter(student=self.student, term=self.term).first()
        current_net_fee = fee_record.net_fee if fee_record else Decimal('0.00')
        current_discount = fee_record.discount if fee_record else Decimal('0.00')

        # 2. Calculate total paid
        # Ensure pk exists before accessing reverse relation
        current_total_paid = Decimal('0.00')
        if self.pk: # Check if instance has been saved
            current_total_paid = self.payments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        # else: If pk is None, total_paid must be 0 as no payments can exist yet

        # 3. Calculate outstanding balance
        current_outstanding = max(current_net_fee - current_total_paid, Decimal('0.00'))

        # 4. Check archived status
        term_is_inactive = not self.term.is_active

        # Update fields directly - save() will be called by the signal handler
        self.total_fee = current_net_fee
        self.total_discount = current_discount
        self.total_paid = current_total_paid
        self.outstanding_balance = current_outstanding
        self.archived = term_is_inactive

    def save(self, *args, **kwargs):
        """
        Save the FinancialRecord. Calculation logic moved to update_record
        and primarily triggered by signals.
        """
        # Rely on signals to call update_record and then save with update_fields
        super().save(*args, **kwargs)

    @property
    def is_fully_paid(self):
        """Check if the student has fully paid the fee for this term."""
        # Use a small tolerance for floating point issues if calculations were complex
        return self.outstanding_balance <= Decimal('0.01')

    @property
    def has_waiver(self):
        """Check if the corresponding fee record has a waiver."""
        fee_record = StudentFeeRecord.objects.filter(student=self.student, term=self.term).first()
        return fee_record and fee_record.waiver

    @property
    def can_access_results(self):
        """Determine if the student can access results based on financial status or waiver."""
        if self.has_waiver:
            return True
        # Allow access if fully paid or at least 80% paid (adjust percentage as needed)
        eighty_percent_paid = self.total_paid >= (self.total_fee * Decimal('0.8'))
        # Ensure total_fee is not zero before calculating percentage
        if self.total_fee <= Decimal('0.00'):
             return True # If fee is zero or less, allow access
        return self.is_fully_paid or eighty_percent_paid

    def __str__(self):
        student_name = self.student.user.get_full_name() if hasattr(self.student, 'user') and self.student.user else f"Student {self.student.pk}"
        return f"{student_name} - {self.term}" 


class Payment(models.Model):
    financial_record = models.ForeignKey('FinancialRecord', related_name='payments', on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)

    def clean(self):
        """ Add validation logic here, checked before save()."""
        super().clean()
        if not self.financial_record:
            raise ValidationError("Payment must be associated with a Financial Record.")

        # Get net fee and waiver status from the related StudentFeeRecord via FinancialRecord
        fee_record = StudentFeeRecord.objects.filter(
            student=self.financial_record.student,
            term=self.financial_record.term
        ).first()

        if not fee_record:
            # This case should ideally be prevented by ensuring FinancialRecord/StudentFeeRecord exist first
            raise ValidationError(f"No fee record found for {self.financial_record.student} in {self.financial_record.term}.")

        if fee_record.waiver and self.amount_paid > 0:
             raise ValidationError("Payment not allowed for waived fees.")

        # Check for overpayment *considering other payments for the same record*
        # We need the state *before* this payment is saved if it's an update
        current_total_paid = self.financial_record.payments.exclude(pk=self.pk).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        prospective_total_paid = current_total_paid + self.amount_paid

        if prospective_total_paid > fee_record.net_fee + Decimal('0.01'): # Add tolerance
             raise ValidationError(f"Total payments (₦{prospective_total_paid:.2f}) would exceed net fee (₦{fee_record.net_fee:.2f}).")

    def save(self, *args, **kwargs):
        # Run validation before saving
        self.full_clean()
        super().save(*args, **kwargs)
        # Signal will handle FinancialRecord update

    @property
    def student(self):
        return self.financial_record.student

    @property
    def term(self):
        return self.financial_record.term

    def __str__(self):
        student_name = self.student.user.get_full_name() if hasattr(self.student, 'user') and self.student.user else f"Student {self.student.pk}"
        return f"{student_name} - {self.term} - {self.amount_paid} on {self.payment_date}"
    
class Expense(models.Model):
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} - {self.amount} on {self.expense_date}"

class EmailCampaign(models.Model):
    subject = models.CharField(max_length=255)
    message = models.TextField()
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="email_campaigns")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subject

# Blog Models
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, editable=False)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('category_post_list', kwargs={'category_slug': self.slug})

    def __str__(self):
        return self.name

class Tag(models.Model): 
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('tag_post_list', kwargs={'tag_slug': self.slug})

    def __str__(self):
        return self.name

class PostManager(models.Manager):
    def published(self):
        return self.filter(status='published', published_date__lte=timezone.now())

class Post(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )

    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=280, unique_for_date='published_date', editable=False)
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='blog_posts')
    content = CKEditor5Field(config_name='default')
    featured_image = models.ImageField(upload_to='blog/featured_images/%Y/%m/%d/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')

    published_date = models.DateTimeField(default=timezone.now) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    categories = models.ManyToManyField(Category, related_name='posts', blank=True)
    tags = models.ManyToManyField(Tag, related_name='posts', blank=True) # Or use TaggableManager() if using django-taggit

    meta_description = models.TextField(max_length=170, blank=True, null=True, help_text="Optimal length 150-160 characters")
    meta_keywords = models.CharField(max_length=255, blank=True, null=True, help_text="Comma-separated keywords (less important for modern SEO)")

    views_count = models.PositiveIntegerField(default=0, editable=False)

    objects = models.Manager() # Default manager\
    published_objects = PostManager() # Custom manager for published posts

    class Meta:
        ordering = ('-published_date',) 
        indexes = [
            models.Index(fields=['-published_date', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            # Ensure slug is unique for the publication date (or globally if unique=True on slug)
            self.slug = base_slug
            counter = 1
            while Post.objects.filter(slug=self.slug, published_date__date=self.published_date.date()).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1

        if not self.meta_description: # Auto-generate meta description if empty
            self.meta_description = strip_tags(self.content)[:160]

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('post_detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.title

    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count']) # Save only this field to avoid triggering other save logic/signals