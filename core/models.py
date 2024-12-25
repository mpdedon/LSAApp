from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MaxValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.db.models.signals import pre_save
from django.db.models import Sum, Avg
from django.utils import timezone
from datetime import date, timedelta, datetime
from decimal import Decimal
import json


# Create your models here.

class Session(models.Model):
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    @property
    def name(self):
        start_year = self.start_date.year
        end_year = self.end_date.year
        return f"{start_year}-{end_year} Session"

    def __str__(self):
        return self.name


class Term(models.Model):

    TERM_OPTIONS = [
        ('First Term', 'First'),
        ('Second Term', 'Second'),
        ('Third Term', 'Third'),
    ]

    session = models.ForeignKey(Session, related_name='terms', on_delete=models.CASCADE)
    name = models.CharField(max_length=20, choices=TERM_OPTIONS)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Generate SchoolDay entries for the term
        current_date = self.start_date
        while current_date <= self.end_date:
            SchoolDay.objects.get_or_create(term=self, date=current_date)
            current_date += timedelta(days=1)
    
    def get_term_weeks(term):
        term_days = []
        current_date = term.start_date
        while current_date <= term.end_date:
            term_days.append(current_date)
            current_date += timedelta(days=1)
        
        # Group by weeks
        weeks = [term_days[i:i+7] for i in range(0, len(term_days), 7)]
        return weeks

    def __str__(self):
        return f"{self.name} ({self.session.name})"

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
    profile_image = models.ImageField(upload_to='media/profile_images/', default='profile_images/default.jpg')
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
    profile_image = models.ImageField(upload_to='media/profile_images/', default='profile_images/default.jpg')
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
    profile_image = models.ImageField(upload_to='media/profile_images/', default='profile_images/default.jpg')
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    contact = models.CharField(max_length=15, null=True)
    address = models.TextField()
    current_class = models.ForeignKey('Class', on_delete=models.SET_NULL, null=True, blank=True, related_name='enrolled_class', default=None)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')


    def __str__(self):
        return self.user.get_full_name()
    
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
    description = models.TextField()
    teacher = models.ForeignKey('Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='classes')
    subjects = models.ManyToManyField('Subject', related_name='class_set', blank=True)  # Assuming you have a Subject model
    students = models.ManyToManyField('Student', related_name='classes', blank=True)
    order = models.PositiveIntegerField(null=True)  # Order defines the class progression

    def next_class(self):
        try:
            return Class.objects.get(order=self.order + 1)
        except Class.DoesNotExist:
            return None
        
    def previous_class(self):
        try:
            return Class.objects.get(order=self.order - 1)
        except Class.DoesNotExist:
            return None

    def save(self, *args, **kwargs):
        if self.order is None:
            max_order = Class.objects.aggregate(max_order=models.Max('order'))['max_order']
            self.order = 1 if max_order is None else max_order + 1
        super().save(*args, **kwargs)

    def subject_count(self):
        return self.subjects.count()
    
    def student_count(self):
        return self.students.count()
    
    def __str__(self):
        return self.name


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

    def __str__(self):
        return f"{self.subject.name} - {self.class_assigned.name} ({self.session.name} - {self.term.name})"
    

class Assignment(models.Model):
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE, default=1)
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=500, null=True, blank=True)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    class_assigned = models.ForeignKey('Class', related_name='assignments', on_delete=models.CASCADE)
    due_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=datetime.now())
    updated_at = models.DateTimeField(default=datetime.now())
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
    submitted_at = models.DateTimeField(auto_now_add=True)
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

    def __str__(self):
        return self.question_text
    
    def options_list(self):
        """Returns options as a Python list."""
        if self.options:
            try:
                return json.loads(self.options)
            except json.JSONDecodeError:
                return []
        return []
    

class Assessment(models.Model):
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)
    short_description = models.CharField(max_length=500, null=True, blank=True)
    date = models.DateField(default=timezone.now)
    score = models.IntegerField(default=0, null=True, blank=True)
    class_assigned = models.ForeignKey('Class', on_delete=models.CASCADE, default=None)
    is_online = models.BooleanField(default=False)
    due_date = models.DateTimeField(null=True, blank=True)  # Only for online
    duration = models.IntegerField(null=True, blank=True)  # Only for online, in minutes
    questions = models.ManyToManyField('OnlineQuestion', related_name='assessment', blank=True)  # Link to questions

    def __str__(self):
        return f"{self.title} - {self.subject.name}"

    @property
    def is_due(self):
        """Check if the online assessment is due for submission."""
        if self.is_online and self.due_date:
            return timezone.now() > self.due_date
        return False


class Exam(models.Model):
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)
    short_description = models.CharField(max_length=500, null=True, blank=True)
    date = models.DateField(default=timezone.now)
    score = models.IntegerField(default=0, null=True, blank=True)
    class_assigned = models.ForeignKey('Class', on_delete=models.CASCADE, default=None)
    is_online = models.BooleanField(default=False)
    due_date = models.DateTimeField(null=True, blank=True)  # Only for online
    duration = models.IntegerField(null=True, blank=True)  # Only for online, in minutes
    questions = models.ManyToManyField('OnlineQuestion', related_name='exams', blank=True)  # Link to questions

    def __str__(self):
        return f"{self.title} - {self.subject.name} - {self.class_assigned.name}"

    @property
    def is_due(self):
        """Check if the online exam is due for submission."""
        if self.is_online and self.due_date:
            return timezone.now() > self.due_date
        return False
    

class AcademicAlert(models.Model):
    ALERT_TYPE_CHOICES = [
        ('assignment', 'Assignment'),
        ('assessment', 'Assessment'),
        ('exam', 'Exam'),
    ]
    
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='alerts_sent')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='academic_alerts')
    due_date = models.DateTimeField(null=True, blank=True)
    is_done = models.BooleanField(default=False)
    date_submitted = models.DateTimeField(null=True, blank=True)
    total_grade = models.FloatField(null=True, blank=True)
    related_object_id = models.IntegerField()  # ID of the related assignment, assessment, or exam
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
        return f"{self.alert_type.capitalize()} Alert: {self.title} for {self.student.get_full_name()}"


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
        subject_results = self.subjectresult_set.all()
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
    continuous_assessment_1 = models.DecimalField(max_digits=2, validators=[MaxValueValidator(10.0)], decimal_places=1, null=True, blank=True)
    continuous_assessment_2 = models.DecimalField(max_digits=2, validators=[MaxValueValidator(10.0)], decimal_places=1, null=True, blank=True)
    continuous_assessment_3 = models.DecimalField(max_digits=2, validators=[MaxValueValidator(10.0)], decimal_places=1, null=True, blank=True)
    assignment = models.DecimalField(max_digits=2, validators=[MaxValueValidator(10.0)], decimal_places=1, null=True, blank=True)
    oral_test = models.DecimalField(max_digits=3, validators=[MaxValueValidator(20.0)], decimal_places=1, null=True, blank=True)
    exam_score = models.DecimalField(max_digits=4, validators=[MaxValueValidator(40.0)], decimal_places=1, null=True, blank=True)
    is_finalized = models.BooleanField(default=True)  # New field to track if the scores are finalized

    def __str__(self):
        return f"{self.result.student} - {self.subject.name} ({'Finalized' if self.is_finalized else 'Draft'})"

    def total_score(self):
        ca1 = self.continuous_assessment_1 or 0
        ca2 = self.continuous_assessment_2 or 0
        ca3 = self.continuous_assessment_3 or 0
        assignment = self.assignment or 0
        oral_test = self.oral_test or 0
        exam_score = self.exam_score or 0

        total = ca1 + ca2 + ca3 + assignment + oral_test + exam_score
        return total

    @classmethod
    def get_class_average(cls, subject):
        # Calculate the average of total scores for all results associated with this subject
        total_scores = cls.objects.filter(subject=subject).aggregate(avg_total=Avg(models.F('continuous_assessment_1') + models.F('continuous_assessment_2') + models.F('continuous_assessment_3') + models.F('assignment') + models.F('oral_test') + models.F('exam_score')))
        return total_scores['avg_total'] or 0
    
    def calculate_grade(self):
        score = self.total_score()
        if score >= 75:
            return 'A'
        elif score >= 65:
            return 'B'
        elif score >= 55:
            return 'C'
        elif score >= 45:
            return 'D'
        elif score >= 40:
            return 'E'
        else:
            return 'F'

    def calculate_grade_point(self):
        grade = self.calculate_grade()
        grade_points = {
            'A': 5, 'B': 4, 'C': 3, 'D': 2, 'E': 1, 'F': 0,
        }
        return grade_points.get(grade, 0)
    

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
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    date = models.DateField(unique=True)


class Holiday(models.Model):
    name = models.CharField(max_length=100)
    date = models.DateField()
    term = models.ForeignKey(Term, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} ({self.date})"
    

class Notification(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    audience = models.CharField(max_length=20, choices=[('all', 'All'), ('guardian', 'Guardians'), ('student', 'Students')])
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
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    term = models.ForeignKey('Term', on_delete=models.CASCADE)
    fee_assignment = models.ForeignKey('FeeAssignment', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    waiver = models.BooleanField(default=False)
    net_fee = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.term} - {self.net_fee}"

    def calculate_net_fee(self):
        """Calculate the net fee after applying discount or waiver."""
        # Ensure that the amount and discount are correctly considered
        amount = self.amount or Decimal('0.00')
        discount = self.discount or Decimal('0.00')
        
        if self.waiver:
            return Decimal('0.00')

        # Calculate the net fee, ensuring it's never negative
        return max(amount - discount, Decimal('0.00'))
    
    def save(self, *args, **kwargs):
        """Ensure the net fee is calculated before saving."""
        self.net_fee = self.calculate_net_fee()
        super().save(*args, **kwargs)

class Payment(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    term = models.ForeignKey('Term', on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    financial_record = models.ForeignKey('FinancialRecord', related_name='payments', on_delete=models.CASCADE, default=None)

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.term} - {self.amount_paid} on {self.payment_date}"


# In models.py
class FinancialRecord(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    term = models.ForeignKey('Term', on_delete=models.CASCADE)
    total_fee = models.DecimalField(max_digits=10, decimal_places=2)
    total_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    archived = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('student', 'term')  # Ensure one record per student per term

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.term}"

    def save(self, *args, **kwargs):
        """Automatically update outstanding balance and archive if term ends."""
        # Calculate net fee from FeeAssignment
        student_fee_record = StudentFeeRecord.objects.filter(student=self.student, term=self.term).first()
        if student_fee_record:
            self.total_fee = student_fee_record.net_fee
            self.total_discount = student_fee_record.discount

        # Calculate total paid based on linked payments
        self.total_paid = self.payments.aggregate(total=Sum('amount_paid'))['total'] or 0
        self.outstanding_balance = max(self.total_fee - self.total_paid, 0)

        # Archive if the term has ended
        if self.term.end_date <= timezone.now().date():
            self.archived = True

        # Save changes without `update_fields` argument
        super(FinancialRecord, self).save(*args, **kwargs)

    @property
    def is_fully_paid(self):
        """Check if the student has fully paid the fee for this term."""
        return self.outstanding_balance == 0

    @property
    def can_access_results(self):
        """Determine if the student can access results based on financial status."""
        # Restrict access if there is an outstanding balance
        return self.is_fully_paid or self.outstanding_balance < self.total_fee * Decimal('0.2')  # Allow access if at least 80% is paid


class Expense(models.Model):
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} - {self.amount} on {self.expense_date}"




