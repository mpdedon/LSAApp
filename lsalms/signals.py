# lsalms/signals.py

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from .models import Course, CourseEnrollment, ContentBlock, GradedActivity
from core.models import Student, Assignment, Assessment, Exam, Term


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


@receiver(pre_save, sender=Student) # <-- Changed to pre_save
def auto_enroll_student_on_promotion(sender, instance, **kwargs):
    """
    Signal: Before a Student is saved, check if their 'current_class' is changing.
    If so, enroll them in all published, internal courses for their NEW class in the active term.
    This also handles newly created students.
    """
    # If the student is new (doesn't have a pk yet), we'll handle them on post_save.
    if not instance.pk:
        # For new students, we let post_save handle it.
        # This function will only handle updates to existing students.
        return

    try:
        # Get the student's state as it currently exists in the database
        old_instance = Student.objects.get(pk=instance.pk)
    except Student.DoesNotExist:
        return # Should not happen on an update

    # --- THE KEY LOGIC ---
    # Compare the old class from the database with the new class about to be saved.
    old_class = old_instance.current_class
    new_class = instance.current_class

    # If the class has not changed, or if they are being removed from a class, do nothing.
    if old_class == new_class or not new_class:
        return

    # A promotion has been detected!
    print(f"PRE_SAVE SIGNAL: Detected class change for {instance} from '{old_class}' to '{new_class}'.")
    
    # We must defer the enrollment logic to post_save, because the student's new
    # class is not yet committed to the database. We can attach the old class
    # to the instance to pass it along.
    instance._old_class_for_signal = old_class


@receiver(post_save, sender=Student)
def perform_auto_enrollment(sender, instance, created, **kwargs):
    """
    This runs AFTER the student is saved. It performs the actual enrollment
    based on the change detected by the pre_save signal or if the student is new.
    """
    student = instance
    new_class = student.current_class
    
    # Determine if we should run:
    # 1. Is it a newly created student with a class?
    # 2. Or is it an updated student where a class change was detected in pre_save?
    old_class_from_presave = getattr(student, '_old_class_for_signal', None)
    
    if not (created or old_class_from_presave):
        return # Not a new student and not a class change, so do nothing.

    if not new_class:
        return # Not assigned to a class, nothing to enroll in.

    print(f"POST_SAVE SIGNAL: Enrolling '{student}' into courses for new class '{new_class}'.")

    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        print(f"  - FAILED: No active term found.")
        return

    courses_to_enroll_in = Course.objects.filter(
        course_type=Course.CourseType.INTERNAL,
        linked_class=new_class,
        term=active_term,
        status=Course.Status.PUBLISHED
    )

    if not courses_to_enroll_in.exists():
        print(f"  - INFO: No published internal courses found for class '{new_class}' in term '{active_term}'.")
        return

    created_count = 0
    with transaction.atomic():
        for course in courses_to_enroll_in:
            _, created_enrollment = CourseEnrollment.objects.get_or_create(
                student=student,
                course=course
            )
            if created_enrollment:
                created_count += 1

    if created_count > 0:
        print(f"  - SUCCESS: Created {created_count} new enrollments for {student}.")


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

