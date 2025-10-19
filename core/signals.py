# signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from core.models import Student, Term, SchoolDay, Student, Teacher, Guardian, Result, FeeAssignment, StudentFeeRecord
from core.models import StudentFeeRecord, Payment, FinancialRecord, Term, Student, Holiday
from core.models import (
    Assessment, Exam, Assignment, 
    AssessmentSubmission, ExamSubmission, AssignmentSubmission,
    Student, AcademicAlert, SubjectResult
)

from django.core.mail import send_mail, EmailMultiAlternatives
from django.db import IntegrityError
from django.db import transaction
from django.template.loader import render_to_string
from core.models import CustomUser
from core.tasks import send_email_task
from decimal import Decimal
from datetime import timedelta

# @receiver(post_save, sender=CustomUser)
# def send_welcome_email(sender, instance, created, **kwargs):
#    if created:
#        send_email_task.delay(
#            subject="Welcome to Our Platform",
#            to_email=instance.email,
#            template='emails/welcome_email.html',
#            context={'user': instance}
#        )


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a Guardian, Teacher, or Student profile
    when a new CustomUser is created with a specific role.
    """
    if created: # Only run on initial creation
        if instance.role == 'guardian':
            Guardian.objects.create(user=instance)
            print(f"Guardian profile created for user: {instance.username}")
        elif instance.role == 'teacher':
            # Teacher model has a required 'date_of_birth' field, so we need a placeholder.
            # The admin will need to edit this later to a real date.
            Teacher.objects.create(user=instance, date_of_birth=timezone.now().date())
            print(f"Teacher profile created for user: {instance.username}")
        elif instance.role == 'student':
            # Student model also has required fields, provide placeholders.
            Student.objects.create(
                user=instance,
                date_of_birth=timezone.now().date(),
                gender='M', 
                relationship='N/A' 
            )
            print(f"Student profile created for user: {instance.username}")

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """
    Ensure the related profile is saved when the user object is saved.
    (This is often needed for OneToOneField relationships).
    """
    if instance.role == 'guardian' and hasattr(instance, 'guardian'): 
        instance.guardian.save()
    elif instance.role == 'teacher' and hasattr(instance, 'teacher'):
        instance.teacher.save()
    elif instance.role == 'student' and hasattr(instance, 'student'):
        instance.student.save()


# --- Signal to Manage SchoolDay Entries ---
@receiver(post_save, sender=Term)
def manage_schoolday_entries_for_term(sender, instance, created, **kwargs):
    """
    Creates/updates/deletes SchoolDay entries when a Term is saved.
    Handles date range changes.
    """
    print(f"Signal: Managing SchoolDays for Term {instance.pk}...") # Debug/Log

    # Use update_fields if available to detect date changes specifically
    update_fields = kwargs.get('update_fields')
    dates_changed = (update_fields is None or
                     'start_date' in update_fields or
                     'end_date' in update_fields)

    if created or dates_changed:
        # We need to adjust SchoolDay entries
        term = instance # The saved term instance
        start_date = term.start_date
        end_date = term.end_date

        if not start_date or not end_date or start_date > end_date:
            print(f"Signal Warning: Invalid date range for Term {term.pk}. Skipping SchoolDay update.")
            return # Avoid processing if dates are invalid

        # Define the set of dates that *should* exist for this term
        required_dates = set()
        current_date = start_date
        while current_date <= end_date:
            required_dates.add(current_date)
            current_date += timedelta(days=1)

        with transaction.atomic(): # Perform operations atomically
            # Find existing dates for THIS term
            existing_dates = set(SchoolDay.objects.filter(term=term).values_list('date', flat=True))

            # Dates to add
            dates_to_add = required_dates - existing_dates
            # Dates to delete (exist in DB for this term but are no longer required)
            dates_to_delete = existing_dates - required_dates

            # Bulk create missing SchoolDay entries
            if dates_to_add:
                school_days_to_create = [
                    SchoolDay(term=term, date=d) for d in dates_to_add
                ]
                try:
                    SchoolDay.objects.bulk_create(school_days_to_create, ignore_conflicts=False) # Don't ignore conflicts with new constraint
                    print(f"Signal: Created {len(school_days_to_create)} SchoolDays for Term {term.pk}.")
                except IntegrityError as e:
                    # This might happen in very rare race conditions, log it
                    print(f"Signal Error: Integrity error creating SchoolDays for Term {term.pk}: {e}")


            # Delete SchoolDay entries that are no longer in the term's date range
            if dates_to_delete:
                deleted_count, _ = SchoolDay.objects.filter(term=term, date__in=dates_to_delete).delete()
                print(f"Signal: Deleted {deleted_count} SchoolDays for Term {term.pk}.")

    print(f"Signal: Finished SchoolDay management for Term {instance.pk}.")


# --- Remove any *other* signals that might also be creating SchoolDay entries ---
# e.g., if generate_attendance_records in your signals.py was doing this, remove that part.

@receiver(post_save, sender=Term)
def generate_initial_result_records(sender, instance, created, **kwargs): # Rename for clarity
    """
    Creates initial Result records for students when a NEW Term is created.
    """
    if created: # Only run when a Term is first created
        print(f"Signal: Generating initial Result records for NEW Term {instance.pk}...")

        # Get students (filter if needed, e.g., only active students)
        students = Student.objects.filter(status='active') # Example filter

        results_to_create = []
        for student in students:
            # Create a Result record with default/zero values
            # Attendance percentage might be calculated later or defaulted to 0 here
            results_to_create.append(
                Result(
                    student=student,
                    term=instance,
                    attendance_percentage=Decimal('0.00'), # Default to 0 initially
                    # Set other defaults for Result fields if necessary
                    # e.g., teacher_remarks="", principal_remarks="", is_approved=False etc.
                )
            )

        if results_to_create:
            try:
                Result.objects.bulk_create(results_to_create, ignore_conflicts=True) # Ignore if result somehow exists
                print(f"Signal: Created {len(results_to_create)} initial Result records for Term {instance.pk}.")
            except Exception as e:
                 print(f"Signal Error: Failed to bulk_create initial Result records for Term {instance.pk}: {e}")

@receiver(post_save, sender=Holiday)
def remove_schoolday_on_holiday_creation(sender, instance, created, **kwargs):
    """
    When a Holiday is created or its date changes, delete the corresponding SchoolDay
    if it exists for that term and date.
    """
    if created or (kwargs.get('update_fields') and 'date' in kwargs['update_fields']):
        term = instance.term
        holiday_date = instance.date
        # Delete SchoolDay if it exists for this term and date
        deleted_count, _ = SchoolDay.objects.filter(term=term, date=holiday_date).delete()
        if deleted_count:
             print(f"Signal: Deleted SchoolDay on {holiday_date} for Term {term.pk} because Holiday '{instance.name}' was added/updated.")

@receiver(post_delete, sender=Holiday)
def add_schoolday_on_holiday_deletion(sender, instance, **kwargs):
    """
    When a Holiday is deleted, create the corresponding SchoolDay if the date
    is within the term's range and is a weekday.
    """
    term = instance.term
    holiday_date = instance.date

    # Check if the date is still within the term's range and is a weekday
    if term.start_date <= holiday_date <= term.end_date and holiday_date.weekday() < 5:
        # Use get_or_create to safely add it back only if it doesn't exist
        sd, created = SchoolDay.objects.get_or_create(term=term, date=holiday_date)
        if created:
             print(f"Signal: Re-created SchoolDay on {holiday_date} for Term {term.pk} because Holiday '{instance.name}' was deleted.")



@receiver(post_save, sender=Student)
def create_student_fee_records(sender, instance, created, **kwargs):
    if created:
        current_class = instance.current_class
        if current_class:
            # Assign fees for the student
            fee_assignments = FeeAssignment.objects.filter(class_instance=current_class)
            for assignment in fee_assignments:
                StudentFeeRecord.objects.get_or_create(
                    student=instance,
                    term=assignment.term,
                    defaults={
                        'fee_assignment': assignment,
                        'amount': assignment.amount,
                        'discount': 0,
                        'waiver': False,
                        'net_fee': assignment.calculate_net_fee(assignment.amount, 0, False),
                    },
                )


@receiver(post_save, sender=StudentFeeRecord)
def update_financial_record_on_fee_change(sender, instance, created, **kwargs):
    """
    Update FinancialRecord when StudentFeeRecord changes or is created.
    Handles both creation of FR and updates.
    """
    fin_record, fin_created = FinancialRecord.objects.get_or_create(
        student=instance.student,
        term=instance.term,
        defaults={ # Basic defaults, will be overwritten by update_record
            'total_fee': instance.net_fee,
            'total_discount': instance.discount,
            'total_paid': Decimal('0.00'),
            'outstanding_balance': instance.net_fee # Initial balance is net_fee
        }
    )

    # --- Crucial Change ---
    # If the FinancialRecord was just created, its pk might not be available yet
    # for reverse lookups within the same transaction.
    # We only need to update fields based on the StudentFeeRecord here.
    # The total_paid calculation should happen ONLY when a Payment is involved.

    should_save = False
    if fin_record.total_fee != instance.net_fee:
        fin_record.total_fee = instance.net_fee
        should_save = True
    if fin_record.total_discount != instance.discount:
        fin_record.total_discount = instance.discount
        should_save = True

    # Recalculate outstanding balance based ONLY on fee and the *current* total_paid
    # (Do not try to re-aggregate payments here)
    new_outstanding = max(fin_record.total_fee - fin_record.total_paid, Decimal('0.00'))
    if fin_record.outstanding_balance != new_outstanding:
        fin_record.outstanding_balance = new_outstanding
        should_save = True

    # Also update archived status based on term (moved from update_record)
    term_is_inactive = not instance.term.is_active
    if fin_record.archived != term_is_inactive:
        fin_record.archived = term_is_inactive
        should_save = True

    if should_save:
        # Save only if necessary, avoid calling update_record recursively or before pk exists
        fin_record.save(update_fields=['total_fee', 'total_discount', 'outstanding_balance', 'archived'])

@receiver(post_save, sender=Payment)
def update_financial_record_on_payment_save(sender, instance, created, **kwargs):
    """
    Update FinancialRecord when a Payment is saved. This is where total_paid IS recalculated.
    """
    fin_record = instance.financial_record
    if fin_record:
        # Now it's safe to call update_record because fin_record definitely exists with a PK
        fin_record.update_record()
        # Use update_fields for efficiency and to prevent potential signal loops if save() triggers others
        fin_record.save(update_fields=['total_paid', 'outstanding_balance'])


@receiver(post_delete, sender=Payment)
def update_financial_record_on_payment_delete(sender, instance, **kwargs):
    """
    Update FinancialRecord when a Payment is deleted.
    """
    fin_record = instance.financial_record
    # Check if the related FinancialRecord still exists before trying to update
    if fin_record and FinancialRecord.objects.filter(pk=fin_record.pk).exists():
         # Refresh to ensure we have the latest state if other operations happened
        fin_record.refresh_from_db()
        fin_record.update_record()
        fin_record.save(update_fields=['total_paid', 'outstanding_balance'])
    # else: pass # Related record deleted, nothing to update

# Optional: Signal to update FinancialRecord archive status when Term becomes inactive
@receiver(post_save, sender=Term)
def update_financial_record_archive_on_term_change(sender, instance, **kwargs):
    if 'update_fields' in kwargs and kwargs['update_fields'] and 'is_active' not in kwargs['update_fields']:
         return # Only run if is_active might have changed

    if not instance.is_active:
        # Find all financial records for this term and archive them
        FinancialRecord.objects.filter(term=instance, archived=False).update(archived=True)
    # You might also need logic if a term is reactivated (unlikely?)
    else:
        FinancialRecord.objects.filter(term=instance, archived=True).update(archived=False)

# Optional: Signal to create initial FinancialRecord when StudentFeeRecord is created
# This might overlap with the post_save on StudentFeeRecord, ensure logic is sound.
# Can be useful if fee records are created before any payment attempts.
# @receiver(post_save, sender=StudentFeeRecord)
# def create_financial_record_on_fee_creation(sender, instance, created, **kwargs):
#     if created:
#         FinancialRecord.objects.get_or_create(
#             student=instance.student,
#             term=instance.term,
#             defaults={
#                 'total_fee': instance.net_fee,
#                 'total_discount': instance.discount,
#                 'total_paid': Decimal('0.00'),
#                 'outstanding_balance': instance.net_fee
#             }
#         )


# --- Helper for Item Availability (Assessments, Exams, Assignments) ---
def _create_notifications_for_item_availability(item_instance, item_type_prefix, item_verbose_name):
    """
    Helper to create notifications when an item becomes available.
    item_type_prefix should be 'assessment', 'exam', or 'assignment'.
    item_verbose_name is 'Assessment', 'Exam', or 'Assignment'.
    """
    # For Assignment, check 'active' status instead of 'is_approved'
    if item_type_prefix == 'assignment':
        if not item_instance.active or (item_instance.due_date and item_instance.due_date < timezone.now()): # Don't notify for past due, inactive
            return
    elif not getattr(item_instance, 'is_approved', False): # For Assessment/Exam
        return

    # For Assignment, created_by is the Teacher instance directly
    if item_type_prefix == 'assignment':
        teacher_creator = item_instance.teacher 
        initiating_user = teacher_creator.user if teacher_creator else None # Get CustomUser from Teacher
    else: # For Assessment/Exam, created_by is a CustomUser
        initiating_user = item_instance.created_by
    
    if not initiating_user:
        print(f"Signal Warning: {item_verbose_name} ID {item_instance.id} has no clear initiating user. Skipping notifications.")
        return

    target_class = item_instance.class_assigned
    students_in_class = Student.objects.filter(current_class=target_class)
    if not students_in_class.exists():
        return
        
    alerts_created_count = 0
    alert_type_for_item = f"{item_type_prefix}_available"

    for student in students_in_class:
        if not AcademicAlert.objects.filter(
            student=student,
            alert_type=alert_type_for_item,
            related_object_id=item_instance.id 
        ).exists():
            AcademicAlert.objects.create(
                student=student,
                alert_type=alert_type_for_item,
                title=f"{item_verbose_name} Available: {item_instance.title}",
                summary=getattr(item_instance, 'description', None) or getattr(item_instance, 'short_description', None) or f"The {item_verbose_name.lower()} '{item_instance.title}' is now available.",
                source_user=initiating_user,
                due_date=getattr(item_instance, 'due_date', None),
                duration=getattr(item_instance, 'duration', None), # Assignment might not have duration
                related_object_id=item_instance.id,
            )
            alerts_created_count += 1
    
    if alerts_created_count > 0:
        print(f"Signal: {alerts_created_count} student alerts created for {item_verbose_name.lower()} '{item_instance.title}'.")

@receiver(post_save, sender=Assessment)
def assessment_availability_notifier(sender, instance, created, **kwargs):
    if instance.is_approved:
        _create_notifications_for_item_availability(instance, 'assessment', 'Assessment')

@receiver(post_save, sender=Exam)
def exam_availability_notifier(sender, instance, created, **kwargs):
    if instance.is_approved:
        _create_notifications_for_item_availability(instance, 'exam', 'Exam')

@receiver(post_save, sender=Assignment)
def assignment_availability_notifier(sender, instance, created, **kwargs):
    # Assignment doesn't have 'is_approved', it uses 'active' and due_date
    if instance.active and (not instance.due_date or instance.due_date >= timezone.now()):
        # Only notify if it's newly created and active, or if it became active
        # The duplicate check in the helper handles repeated saves of an active assignment.
         _create_notifications_for_item_availability(instance, 'assignment', 'Assignment')


# --- Helper for Item Submission (Assessments, Exams, Assignments) ---
def _create_notifications_for_submission(submission_instance, item_type_prefix, related_item_title, related_item_id, item_verbose_name):
    """
    Helper to create notifications when an item is submitted.
    item_type_prefix should be 'assessment', 'exam', or 'assignment'.
    related_item_title is the title of the parent Assessment/Exam/Assignment.
    related_item_id is the ID of the parent Assessment/Exam/Assignment.
    item_verbose_name is 'Assessment', 'Exam', or 'Assignment'.
    """
    student = submission_instance.student
    alert_type_for_submission = f"{item_type_prefix}_submission"
    
    # Alert for the student (and thus visible to guardian)
    if not AcademicAlert.objects.filter(
        student=student, 
        alert_type=alert_type_for_submission, 
        related_object_id=submission_instance.id # Link to the submission itself
    ).exists():
        AcademicAlert.objects.create(
            student=student,
            alert_type=alert_type_for_submission,
            title=f"{item_verbose_name} Submitted: {related_item_title}",
            summary=(f"Your submission for {item_verbose_name.lower()} '{related_item_title}' "
                     f"by {student.user.get_full_name()} was received on "
                     f"{submission_instance.submitted_at.strftime('%Y-%m-%d %H:%M')}."),
            source_user=student.user, # Student is the actor for submission
            related_object_id=submission_instance.id, 
        )
        print(f"Signal: Submission alert created for {item_verbose_name.lower()} (parent ID {related_item_id}) by student '{student.user.username}'.")

@receiver(post_save, sender=AssessmentSubmission)
def assessment_submission_notifier(sender, instance, created, **kwargs):
    if created:
        _create_notifications_for_submission(instance, 'assessment', instance.assessment.title, instance.assessment.id, 'Assessment')

@receiver(post_save, sender=ExamSubmission)
def exam_submission_notifier(sender, instance, created, **kwargs):
    if created:
        _create_notifications_for_submission(instance, 'exam', instance.exam.title, instance.exam.id, 'Exam')

@receiver(post_save, sender=AssignmentSubmission)
def assignment_submission_notifier(sender, instance, created, **kwargs):
    if created:
        _create_notifications_for_submission(instance, 'assignment', instance.assignment.title, instance.assignment.id, 'Assignment')

# Helper function for linking Assignemnt, Assessment and Exam to SubjectResult
def _update_subject_result(submission, related_item, item_type):
    """
    Helper function to update SubjectResult from a submission.
    `related_item` is either an Assessment or Exam instance.
    """
    if submission.is_graded and related_item.result_field_mapping:
        student = submission.student
        
        # 1. Get or create the main Result object for the student and term
        result_sheet, _ = Result.objects.get_or_create(student=student, term=related_item.term)

        # 2. Get or create the specific SubjectResult entry
        subject_result, _ = SubjectResult.objects.get_or_create(
            result=result_sheet,
            subject=related_item.subject
        )

        # 3. Define max scores based on the target field
        max_score_for_field = {
            'continuous_assessment_1': Decimal('10.0'),
            'continuous_assessment_2': Decimal('10.0'),
            'continuous_assessment_3': Decimal('10.0'),
            'assignment': Decimal('10.0'),
            'oral_test': Decimal('20.0'),
            'exam_score': Decimal('40.0'),
        }.get(related_item.result_field_mapping, Decimal('0.0'))

        if max_score_for_field == Decimal('0.0'):
            return # Mapping is invalid or not found

        # 4. Calculate the scaled score
        total_possible_marks = related_item.get_total_marks
        if total_possible_marks > 0 and submission.score is not None:
            scaled_score = (Decimal(submission.score) / Decimal(total_possible_marks)) * max_score_for_field
        else:
            scaled_score = Decimal('0.0')

        # 5. Update the SubjectResult field and save
        setattr(subject_result, related_item.result_field_mapping, scaled_score)
        subject_result.save()
        
        # Optional: Recalculate the overall term summary after updating a component
        result_sheet.calculate_term_summary()

@receiver(post_save, sender=AssignmentSubmission)
def update_subject_result_from_assignment(sender, instance, **kwargs):
    _update_subject_result(instance, instance.assignmenet, 'Assignment')


def _update_subject_result_with_best_attempt(SubmissionModel, instance, related_item, item_type_str):
    """
    Generic helper that finds the highest scoring attempt and updates the SubjectResult.
    """
    if not (instance.is_graded and related_item.result_field_mapping):
        return

    # Find the highest scoring, completed submission for this student and item
    best_submission = SubmissionModel.objects.filter(
        **{item_type_str: related_item},
        student=instance.student,
        is_completed=True,
        is_graded=True,
        score__isnull=False
    ).order_by('-score').first()

    if not best_submission:
        return

    # Now proceed with the scaling logic, but use the score from the best_submission
    # ... (The rest of the logic is the same as the _update_subject_result helper from before,
    # just ensure you use `best_submission.score` for the calculation) ...
    
    result_sheet, _ = Result.objects.get_or_create(student=instance.student, term=related_item.term)
    subject_result, _ = SubjectResult.objects.get_or_create(result=result_sheet, subject=related_item.subject)
    
    MAX_SCORES = {
        'continuous_assessment_1': Decimal('10.0'), 'continuous_assessment_2': Decimal('10.0'),
        'continuous_assessment_3': Decimal('10.0'), 'assignment': Decimal('10.0'),
        'exam_score': Decimal('40.0'),
    }
    target_max_score = MAX_SCORES.get(related_item.result_field_mapping)
    if not target_max_score: return

    total_possible_marks = related_item.get_total_marks
    scaled_score = Decimal('0.0')
    if total_possible_marks > 0:
        student_best_score = Decimal(best_submission.score)
        scaled_score = (student_best_score / Decimal(total_possible_marks)) * target_max_score

    setattr(subject_result, related_item.result_field_mapping, scaled_score)
    subject_result.save()
    result_sheet.calculate_term_summary()


@receiver(post_save, sender=AssignmentSubmission)
def update_subject_result_from_assignment(sender, instance, **kwargs):
    _update_subject_result(instance, instance.assignmenet, 'Assignment')

@receiver(post_save, sender=AssessmentSubmission)
def update_assessment_result(sender, instance, **kwargs):
    _update_subject_result_with_best_attempt(AssessmentSubmission, instance, instance.assessment, 'assessment')

@receiver(post_save, sender=ExamSubmission)
def update_exam_result(sender, instance, **kwargs):
    _update_subject_result_with_best_attempt(ExamSubmission, instance, instance.exam, 'exam')