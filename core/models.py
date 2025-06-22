from django.db import models, transaction
from django.core.validators import MaxValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db.models import Sum, Avg, Q, F
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
    profile_image = models.ImageField(upload_to='profile_images/', default='profile_images/default.jpg')
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
    profile_image = models.ImageField(upload_to='profile_images/', default='profile_images/default.jpg')
    contact = models.CharField(max_length=15, null=True)
    address = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def student_count(self):
        return self.students.count()  

    def __str__(self):
        return self.user.username


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
    profile_image = models.ImageField(upload_to='profile_images/', default='profile_images/default.jpg')
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
    term = models.ForeignKey('Term', on_delete=models.CASCADE, default=1)
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE, default=1)
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=500, null=True, blank=True)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    class_assigned = models.ForeignKey('Class', related_name='assignments', on_delete=models.CASCADE)
    due_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)  # To mark assignments as active/inactive

    def has_expired(self):
        """Checks if the assignment is past its due date."""
        return timezone.now() > self.due_date
    
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
    # For MCQ/SCQ questions, store choices as JSON
    options = models.JSONField(null=True, blank=True)
    correct_answer = models.CharField(max_length=255, null=True, blank=True)  # For MCQ/SCQ correct answer

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
    answers = models.JSONField()  # Store answers as JSON for simplicity
    grade = models.FloatField(null=True, blank=True)  # Auto-graded for SCQ/MCQ
    feedback = models.TextField(null=True, blank=True)  # Teacher feedback for essay/manual grading
    is_completed = models.BooleanField(default=False)

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
    points = models.PositiveIntegerField(default=1)

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
    term = models.ForeignKey('Term', on_delete=models.CASCADE, default=1)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)
    short_description = models.CharField(max_length=500, null=True, blank=True)
    score = models.IntegerField(default=0, null=True, blank=True)
    total_marks = models.PositiveIntegerField(null=True, blank=True, help_text="Total marks possible for this assessment.")
    class_assigned = models.ForeignKey('Class', on_delete=models.CASCADE, default=None)
    is_online = models.BooleanField(default=True)
    due_date = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)
    questions = models.ManyToManyField('OnlineQuestion', related_name='assessments', blank=True)
    is_approved = models.BooleanField(default=False)  # New field
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_assessments")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_assessments")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.title} - {self.subject.name}"

    @property
    def is_due(self):
        """Check if the online assessment is due for submission."""
        if self.is_online and self.due_date:
            return timezone.now() > self.due_date
        return False

    @property
    def get_total_marks(self):
        return self.questions.aggregate(total_marks=Sum('points'))['total_marks'] or 0

class AssessmentSubmission(models.Model):
    assessment = models.ForeignKey('Assessment', on_delete=models.CASCADE, related_name='submissions_for_assessment')
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    answers = models.JSONField()  # Stores the student's answers
    score = models.IntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_graded = models.BooleanField(default=False)
    requires_manual_review = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.assessment.title}"

class Exam(models.Model):
    term = models.ForeignKey('Term', on_delete=models.CASCADE, default=1)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)
    short_description = models.CharField(max_length=500, null=True, blank=True)
    score = models.IntegerField(default=0, null=True, blank=True)
    total_marks = models.PositiveIntegerField(null=True, blank=True, help_text="Total marks possible for this assessment.")
    class_assigned = models.ForeignKey('Class', on_delete=models.CASCADE, default=None)
    is_online = models.BooleanField(default=True)
    due_date = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)
    questions = models.ManyToManyField('OnlineQuestion', related_name='exams', blank=True)
    is_approved = models.BooleanField(default=False)  # New field
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_exams")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_exams")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.title} - {self.subject.name}"

    @property
    def is_due(self):
        """Check if the online exam is due for submission."""
        if self.is_online and self.due_date:
            return timezone.now() > self.due_date
        return False

    @property
    def get_total_marks(self):
        return self.questions.aggregate(total_marks=Sum('points'))['total_marks'] or 0

class ExamSubmission(models.Model):
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='submissions_for_exam')
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    answers = models.JSONField()  # Stores the student's answers
    score = models.IntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_graded = models.BooleanField(default=False)
    requires_manual_review = models.BooleanField(default=False)

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
    
    def total_continuous_assessment(self, subject):
        return sum(getattr(self, f'{subject}_ca{i}', 0) for i in range(1, 4))

    def total_assignments(self, subject):
        return sum(getattr(self, f'{subject}_assignment{i}', 0) for i in range(1, 4))
    
    def total_exam_score(self, subject):
        return sum(getattr(self, f'{subject}_exam_score{i}', 0) for i in range(1, 4))

    def overall_score(self, subject):
        return (
            self.total_continuous_assessment(subject)
            + self.total_assignments(subject)
            + getattr(self, f'{subject}_exam_score', 0)
        )

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.term}"
    
    def calculate_gpa(self):
        subject_results = self.subjectresult_set.filter(
                Q(continuous_assessment_1__isnull=False) |
                Q(continuous_assessment_2__isnull=False) |
                Q(continuous_assessment_3__isnull=False) |
                Q(assignment__isnull=False) |
                Q(oral_test__isnull=False) |
                Q(exam_score__isnull=False)
            )
        total_weighted_grade_points = 0
        total_weights = 0

        for subject_result in subject_results:
            subject_weight = subject_result.subject.subject_weight
            grade_point = subject_result.calculate_grade_point()
            total_weighted_grade_points += grade_point * subject_weight
            total_weights += subject_weight

        if total_weights > 0:
            return round(total_weighted_grade_points / total_weights, 2)
        return 0.0
    
    
class SubjectResult(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    result = models.ForeignKey(Result, on_delete=models.CASCADE)
    continuous_assessment_1 = models.DecimalField(max_digits=4, validators=[MaxValueValidator(10.0)], decimal_places=1, null=True, blank=True)
    continuous_assessment_2 = models.DecimalField(max_digits=4, validators=[MaxValueValidator(10.0)], decimal_places=1, null=True, blank=True)
    continuous_assessment_3 = models.DecimalField(max_digits=4, validators=[MaxValueValidator(10.0)], decimal_places=1, null=True, blank=True)
    assignment = models.DecimalField(max_digits=4, validators=[MaxValueValidator(10.0)], decimal_places=1, null=True, blank=True)
    oral_test = models.DecimalField(max_digits=4, validators=[MaxValueValidator(20.0)], decimal_places=1, null=True, blank=True)
    exam_score = models.DecimalField(max_digits=4, validators=[MaxValueValidator(40.0)], decimal_places=1, null=True, blank=True)
    is_finalized = models.BooleanField(default=False) # Default to False initially

    def __str__(self):
        student_name = self.result.student.user.get_full_name() if self.result.student else "Unknown Student"
        subject_name = self.subject.name if self.subject else "Unknown Subject"
        status = 'Finalized' if self.is_finalized else 'Draft'
        return f"{student_name} - {subject_name} ({status})"

    def total_score(self):
        # Ensure Decimal conversion for consistent arithmetic
        ca1 = self.continuous_assessment_1 or 0
        ca2 = self.continuous_assessment_2 or 0
        ca3 = self.continuous_assessment_3 or 0
        assignment = self.assignment or 0
        oral_test = self.oral_test or 0
        exam_score = self.exam_score or 0
        # Cast to Decimal if they are not already, although model fields should be
        total = Decimal(ca1) + Decimal(ca2) + Decimal(ca3) + Decimal(assignment) + Decimal(oral_test) + Decimal(exam_score)
        return total.quantize(Decimal('0.1')) # Keep one decimal place

    @classmethod
    def get_class_average(cls, subject, term, class_obj):
        # More specific filtering is needed for a meaningful class average
        results_in_term = Result.objects.filter(term=term, student__current_class=class_obj)
        subject_results = cls.objects.filter(subject=subject, result__in=results_in_term)

        # Aggregate sum of components, handling NULLs
        aggregation = subject_results.aggregate(
            avg_total=Avg(
                F('continuous_assessment_1') + F('continuous_assessment_2') +
                F('continuous_assessment_3') + F('assignment') +
                F('oral_test') + F('exam_score'),
                # Provide default=0 if a component is NULL before summing
                # Note: Direct sum with F objects handles NULLs reasonably in newer Django versions
                # but explicit Coalesce might be safer if issues arise
                output_field=models.DecimalField()
            )
        )
        avg = aggregation['avg_total']
        return avg.quantize(Decimal('0.1')) if avg is not None else Decimal('0.0')

    def calculate_grade(self):
        score = self.total_score()
        if score >= 80: return 'A'
        elif score >= 65: return 'B'
        elif score >= 55: return 'C'
        elif score >= 45: return 'D'
        elif score >= 40: return 'E'
        else: return 'F'

    def calculate_grade_point(self):
        score = self.total_score() # Use total score for points calculation
        if score >= 80: return 5.0
        elif score >= 65: return 4.0
        elif score >= 55: return 3.0
        elif score >= 45: return 2.0
        elif score >= 40: return 1.0
        else: return 0.0
    

class Message(models.Model):
    sender = models.ForeignKey(CustomUser, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(CustomUser, related_name='received_messages', on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='messages')
    title = models.CharField(max_length=255, default="")
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_unread = models.BooleanField(default=True)

    def clean(self):
        if not self.student:
            raise ValidationError("A student must be associated with the message.")
    
    def __str__(self):
        return f"Message from {self.sender} to {self.recipient}"
    

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
        amount = self.amount or Decimal('0.00')
        discount = self.discount or Decimal('0.00')
        
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