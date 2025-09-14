# lsalms/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import Course, CourseEnrollment, ContentBlock, GradedActivity
from core.models import Student, Assignment, Assessment, Exam


@receiver(post_save, sender=Course)
def auto_enroll_students_on_publish(sender, instance, created, **kwargs):
    """
    Signal 1: When a Course is PUBLISHED, automatically enroll all students
    from the course's linked class. This is the primary automation.
    """
    # We only care about INTERNAL courses that are PUBLISHED
    if instance.course_type != Course.CourseType.INTERNAL or instance.status != Course.Status.PUBLISHED:
        return

    print(f"SIGNAL TRIGGERED: Course '{instance.title}' saved as PUBLISHED. Checking enrollments.")
    
    students_to_enroll = Student.objects.filter(
        current_class=instance.linked_class,
        status='active'
    )
    
    for student in students_to_enroll:
        # get_or_create is safe and efficient. It does nothing if the enrollment already exists.
        _, created = CourseEnrollment.objects.get_or_create(
            student=student,
            course=instance
        )
        if created:
            print(f"  + Auto-enrolled '{student.user.username}' via signal.")


@receiver(post_save, sender=Student)
def auto_enroll_student_on_class_change(sender, instance, created, **kwargs):
    """
    Signal 2: When a Student is saved, check if their 'current_class' has
    changed. If so, enroll them in all published courses for their NEW class.
    """
    # If this is a new student, they will be enrolled by the sync command or later actions.
    if created:
        return
    
    try:
        # Get the student's state BEFORE this save
        old_instance = Student.objects.get(pk=instance.pk)
        # If the class hasn't changed, do nothing.
        if old_instance.current_class == instance.current_class:
            return
    except Student.DoesNotExist:
        return 

    new_class = instance.current_class
    if not new_class:
        return # Do nothing if they are unassigned from a class

    print(f"SIGNAL TRIGGERED: Student '{instance.user.username}' moved to new class '{new_class}'. Checking enrollments.")

    courses_for_new_class = Course.objects.filter(
        linked_class=new_class,
        status=Course.Status.PUBLISHED,
        course_type=Course.CourseType.INTERNAL
    )

    for course in courses_for_new_class:
        _, created = CourseEnrollment.objects.get_or_create(student=instance, course=course)
        if created:
            print(f"  + Auto-enrolled '{instance.user.username}' in '{course.get_course_title()}' due to class change.")


@receiver(post_save, sender=ContentBlock)
def create_or_update_graded_activity_on_link(sender, instance, created, **kwargs):
    """
    Signal 3: When a ContentBlock is saved, check if it links to a graded activity.
    If so, create a GradedActivity entry for the course.
    """
    course = instance.lesson.module.course
    activity = None
    
    if instance.linked_assignment:
        activity = instance.linked_assignment
    elif instance.linked_assessment:
        activity = instance.linked_assessment
    elif instance.linked_exam:
        activity = instance.linked_exam
        
    if activity:
        # Get the ContentType for the specific model (Assignment, Assessment, etc.)
        activity_type = ContentType.objects.get_for_model(activity)
        
        max_score_value = getattr(activity, 'total_marks', None) or getattr(activity, 'calculate_grade', 100)
        if callable(max_score_value):
            max_score_value = max_score_value()

        # Create the GradedActivity record if it doesn't exist
        GradedActivity.objects.get_or_create(
            course=course,
            content_type=activity_type,
            object_id=activity.id,
            defaults={'max_score': max_score_value}
        )


@receiver(post_delete, sender=ContentBlock)
def delete_graded_activity_on_unlink(sender, instance, **kwargs):
    """
    When a ContentBlock is deleted, if it was linked to a graded activity,
    remove the corresponding GradedActivity entry.
    """
    activity = None
    if instance.linked_assignment_id: 
        activity_model = Assignment
        activity_id = instance.linked_assignment_id
    elif instance.linked_assessment_id:
        activity_model = Assessment
        activity_id = instance.linked_assessment_id
    elif instance.linked_exam_id:
        activity_model = Exam
        activity_id = instance.linked_exam_id
    else:
        return
  
    if activity_id:
        activity_type = ContentType.objects.get_for_model(activity_model)
        GradedActivity.objects.filter(
            course=instance.lesson.module.course,
            content_type=activity_type,
            object_id=activity_id
        ).delete()
