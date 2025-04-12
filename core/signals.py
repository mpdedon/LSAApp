# signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.models import Student, Term, SchoolDay, Student, Result, FeeAssignment, StudentFeeRecord
from core.models import StudentFeeRecord, Payment, FinancialRecord, Term, Student, Holiday

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
