from django.db import models

# lsalms/models.py

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F, Q
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

# --- Import core application models ---
try:
    from core.models import Student, Class, Term, Subject, Assignment, Assessment, Exam
except ImportError:
    # Fallback for initial migrations or design phase
    Student = settings.AUTH_USER_MODEL 
    Class = Term = Assignment = Assessment = Exam = type('MockModel', (object,), {})

# === Custom Managers for Cleaner Queries ===

class PublishedCourseManager(models.Manager):
    """
    CTO Note: Encapsulates business logic for what constitutes a "live" course.
    This keeps view logic clean and consistent across the application.
    Usage: Course.published.all()
    """
    def get_queryset(self):
        return super().get_queryset().filter(status=Course.Status.PUBLISHED)


# === 1. Core Curriculum Structure ===

class Course(models.Model):
    """
    The central model for a course. It defines scope, status, target audience,
    and access rules. It acts as the anchor for all related content and tracking.
    """
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'        # Teacher is building, not visible to students.
        PUBLISHED = 'PUBLISHED', 'Published'  # Live and accessible to enrolled students.
        ARCHIVED = 'ARCHIVED', 'Archived'    # Historical record, not active, read-only.

    class CourseType(models.TextChoices):
        INTERNAL = 'INTERNAL', 'Internal Class Course' # Tied to a physical school class.
        EXTERNAL = 'EXTERNAL', 'Online Academy Course' # Subscription-based.

    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=275, unique=True, editable=False,
                            help_text="URL-friendly identifier. Auto-generated from title.")
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='lsalms_courses')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)

    # --- UX & Pedagogical Fields (For better course descriptions) ---
    learning_objectives = models.TextField(
        blank=True,
        help_text="What new skills or knowledge will students gain? (List key points)"
    )
    prerequisites = models.TextField(
        blank=True,
        help_text="What knowledge should students have before starting this course?"
    )

    # --- Access Control & Structural Links ---
    course_type = models.CharField(max_length=10, choices=CourseType.choices, default=CourseType.INTERNAL)
    linked_class = models.ForeignKey(
        Class, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="For INTERNAL courses: links to the primary school class."
    )
    term = models.ForeignKey(
        Term, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="For INTERNAL courses: links to the academic term."
    )
    is_subscription_based = models.BooleanField(
        default=False,
        help_text="For EXTERNAL courses: requires a paid subscription."
    )
    # --- Timestamps & Managers ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = models.Manager()
    published = PublishedCourseManager() 

    class Meta:
        ordering = ['title', 'subject__name']
        constraints = [
            models.UniqueConstraint(
                fields=['linked_class', 'term', 'subject'], # A subject can only have one course per class per term
                condition=Q(course_type='INTERNAL'),
                name='unique_subject_course_per_class_term'
            )
        ]

    def __str__(self):
        return self.get_course_title()

    def get_course_title(self):
        if self.course_type == self.CourseType.INTERNAL and self.subject:
            class_name = f" for {self.linked_class.name}" if self.linked_class else ""
            return f"{self.subject.name}{class_name}"
        return self.title

    def clean(self):
        """ Enforce our new business logic at the model level. """
        # Rule 1: Internal courses MUST have a subject, class, and term.
        if self.course_type == self.CourseType.INTERNAL:
            if not self.subject or not self.linked_class or not self.term:
                raise ValidationError("Internal courses require a Subject, a Linked Class, and a Term.")
            # Rule 2: We can auto-set the title for internal courses to keep data clean.
            if not self.title:
                self.title = f"{self.subject.name} for {self.linked_class.name}"

        # Rule 3: External courses MUST have a title, but NOT a subject.
        if self.course_type == self.CourseType.EXTERNAL:
            if not self.title:
                raise ValidationError("External (Online Academy) courses require a Title.")
            if self.subject:
                raise ValidationError("External courses cannot be linked to an internal Subject.")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        base_slug = slugify(self.title) or "course"
        slug = base_slug
        counter = 1
        while type(self).objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        return slug

    def get_next_uncompleted_lesson(self, student):
            # 1. Get a list of all lesson IDs in this course, in the correct order.
        all_lesson_ids_qs = Lesson.objects.filter(
            module__course=self
        ).order_by('module__order', 'order').values_list('id', flat=True)

        # Convert the queryset to a list and explicitly remove any None values.
        all_lesson_ids = [lesson_id for lesson_id in all_lesson_ids_qs if lesson_id is not None]

        if not all_lesson_ids:
            return None # Course has no valid lessons

        # 2. Get a set of lesson IDs this student has completed.
        completed_lesson_ids = set(
            LessonProgress.objects.filter(
                enrollment__student=student,
                enrollment__course=self,
                lesson_id__in=all_lesson_ids
            ).values_list('lesson_id', flat=True)
        )

        # 3. Find the first lesson ID that is not in the completed set.
        for lesson_id in all_lesson_ids:
            if lesson_id not in completed_lesson_ids:
                return Lesson.objects.get(pk=lesson_id)
        
        # 5. If the loop finishes, all lessons are complete.
        return None


class Module(models.Model):
    """ A 'chapter' or section of a Course. """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, help_text="A brief overview of this module's goals.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = [['course', 'title']]

    def __str__(self):
        return f"{self.course.title} | {self.title}"


class Lesson(models.Model):
    """ An individual learning unit (e.g., a lecture, reading, or activity). """
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    estimated_duration = models.PositiveIntegerField(default=5, help_text="Estimated time in minutes to complete.")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class ContentBlock(models.Model):
    """
    The atomic unit of content, designed for flexibility and pedagogical variety
    (e.g., dual-coding by pairing text and media).
    """
    class ContentType(models.TextChoices):
        TEXT = 'TEXT', 'Rich Text'
        IMAGE = 'IMAGE', 'Image'
        VIDEO = 'VIDEO', 'Video Embed'
        AUDIO = 'AUDIO', 'Audio Clip'
        FILE = 'FILE', 'File Download'
        PRACTICE_QUIZ = 'PRACTICE_QUIZ', 'Practice Quiz (Ungraded)'
        ASSIGNMENT = 'ASSIGNMENT', 'Link to Graded Assignment'
        ASSESSMENT = 'ASSESSMENT', 'Link to Graded Assessment'
        EXAM = 'EXAM', 'Link to Graded Exam'

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='content_blocks')
    title = models.CharField(max_length=255, help_text="e.g., 'Video: Introduction to Photosynthesis'")
    content_type = models.CharField(max_length=15, choices=ContentType.choices)
    order = models.PositiveIntegerField(default=0)

    # --- Content Payloads ---
    rich_text = models.TextField(blank=True, help_text="For TEXT content type.")
    media_url = models.URLField(blank=True, help_text="URL for Video or external Audio/Image.")
    media_file = models.FileField(upload_to='lsalms/media/%Y/%m/', blank=True, null=True)
    
    # --- External Activity Links ---
    # Links to models in your core app. This decouples lsalms from lsaapp_core.
    linked_assignment = models.ForeignKey(Assignment, on_delete=models.SET_NULL, null=True, blank=True)
    linked_assessment = models.ForeignKey(Assessment, on_delete=models.SET_NULL, null=True, blank=True)
    linked_exam = models.ForeignKey(Exam, on_delete=models.SET_NULL, null=True, blank=True)
    linked_practice_quiz = models.ForeignKey('PracticeQuiz', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


# === 2. Learning Strategies & Tracks ===

class LearningTrack(models.Model):
    """ A curated sequence of courses leading to a specific goal or certification. """
    title = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    courses = models.ManyToManyField(Course, through='TrackCourseOrder', related_name='learning_tracks')

    def __str__(self):
        return self.title


class TrackCourseOrder(models.Model):
    """ Through model to define the precise order of courses in a LearningTrack. """
    track = models.ForeignKey(LearningTrack, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = [['track', 'course']]


class PracticeQuiz(models.Model):
    """ A non-graded quiz for retrieval practice, supporting spaced repetition. """
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.title


class PracticeQuestion(models.Model):
    """ A single question within a PracticeQuiz. """
    quiz = models.ForeignKey(PracticeQuiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    options_json = models.JSONField(help_text="List of choices, e.g., ['A', 'B', 'C']")
    correct_option = models.CharField(max_length=255)
    explanation = models.TextField(blank=True, help_text="Feedback shown after the student answers.")


# === 3. Enrollment, Progress, and Reporting ===

class CourseEnrollment(models.Model):
    """ Links a student to a course, granting access and tracking progress centrally. """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='lsalms_enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    subscription_end_date = models.DateField(null=True, blank=True, help_text="For subscription-based courses.")

    class Meta:
        unique_together = [['student', 'course']]

    def calculate_progress_percentage(self):
        """
        Calculates the student's completion percentage for this course.
        Returns an integer between 0 and 100.
        """
        # Count all lessons in the course's modules
        total_lessons_in_course = Lesson.objects.filter(module__course=self.course).count()
        
        if total_lessons_in_course == 0:
            return 0 # Avoid division by zero if course has no lessons

        # Count how many of those lessons have a completion record for THIS enrollment
        completed_lessons_count = LessonProgress.objects.filter(
            enrollment=self,
            lesson__module__course=self.course
        ).count()
        
        percentage = (completed_lessons_count / total_lessons_in_course) * 100
        return int(percentage)

    def is_active(self):

        if self.course.course_type == Course.CourseType.INTERNAL:
            return True
        
        if self.subscription_end_date is None:
            return False 
            
        return self.subscription_end_date >= timezone.now().date()

class LessonProgress(models.Model):
    """ A simple record indicating a student has completed a lesson. """
    enrollment = models.ForeignKey(CourseEnrollment, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['enrollment', 'lesson']]


class CourseGrade(models.Model):
    """ Caches the final calculated grade for a student in a course for fast reporting. """
    enrollment = models.OneToOneField(CourseEnrollment, on_delete=models.CASCADE, related_name='grade_report')
    final_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade_details_json = models.JSONField(null=True, blank=True, help_text="Snapshot of grade components.")
    last_calculated = models.DateTimeField(auto_now=True)


# === 4. Spaced Repetition & Granular Logging ===

class SpacedRepetitionItem(models.Model):
    """ Manages the review schedule for individual learning items for each student. """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='review_schedule')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE) # Or link to PracticeQuiz/ContentBlock
    next_review_date = models.DateField(db_index=True)
    current_interval = models.PositiveIntegerField(default=1, help_text="Review interval in days.")

    class Meta:
        unique_together = [['student', 'lesson']]


class StudentActivityLog(models.Model):
    """
    The central event stream. Logs every significant student interaction to power AI recommendations
    and detailed progress reports without losing a single detail.
    """
    class ActivityType(models.TextChoices):
        COURSE_ENROLLED = 'COURSE_ENROLLED', 'Course Enrolled'
        LESSON_VIEWED = 'LESSON_VIEWED', 'Lesson Viewed'
        PRACTICE_QUIZ_ATTEMPTED = 'PRACTICE_QUIZ_ATTEMPTED', 'Practice Quiz Attempted'
        VIDEO_PLAYED_TO_END = 'VIDEO_PLAYED_TO_END', 'Video Completed'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='lsalms_activity_logs')
    activity_type = models.CharField(max_length=30, choices=ActivityType.choices, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Generic link to any model in the system (Lesson, Quiz, Course)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    related_object = GenericForeignKey('content_type', 'object_id')
    
    details_json = models.JSONField(null=True, blank=True, help_text="e.g., {'score': 80, 'time_spent_sec': 120}")

    class Meta:
        ordering = ['-timestamp']


class AIInteractionLog(models.Model):
    """ Audits all calls to external AI services for cost control and quality assurance. """
    class AITask(models.TextChoices):
        CONTENT_DRAFTING = 'CONTENT_DRAFTING', 'Lesson Content Generation'
        QUIZ_GENERATION = 'QUIZ_GENERATION', 'Quiz Question Generation'
        STUDENT_GUIDANCE = 'STUDENT_GUIDANCE', 'Personalized Student Feedback'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    task_type = models.CharField(max_length=20, choices=AITask.choices)
    prompt_tokens = models.PositiveIntegerField(default=0)
    response_tokens = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']


class GradedActivity(models.Model):
    """
    Links a specific graded item (Assignment, Assessment, Exam) to a Course
    and assigns it a weight for the final grade calculation.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='graded_activities')
    
    # Generic ForeignKey to link to Assignment, Assessment, or Exam models
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    activity_object = GenericForeignKey('content_type', 'object_id')
    
    weight = models.PositiveIntegerField(
        default=10,
        help_text="The percentage weight of this activity in the final course grade (e.g., 20 for 20%)."
    )
    max_score = models.PositiveIntegerField(
        default=100,
        help_text="The maximum possible score for this activity (e.g., 50 marks)."
    )

    class Meta:
        unique_together = [['course', 'content_type', 'object_id']]

    def __str__(self):
        return f"{self.activity_object.title if self.activity_object else 'N/A'} ({self.weight}%) in {self.course.title}"