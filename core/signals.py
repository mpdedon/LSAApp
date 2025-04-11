# signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from core.models import Student, Term, SchoolDay, Student, Result, FeeAssignment, StudentFeeRecord
from core.models import StudentFeeRecord, Payment, FinancialRecord, Term, Student

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from core.models import CustomUser
from core.tasks import send_email_task
from decimal import Decimal


# @receiver(post_save, sender=CustomUser)
# def send_welcome_email(sender, instance, created, **kwargs):
#    if created:
#        send_email_task.delay(
#            subject="Welcome to Our Platform",
#            to_email=instance.email,
#            template='emails/welcome_email.html',
#            context={'user': instance}
#        )


@receiver(post_save, sender=Term)
def generate_attendance_records(sender, instance, created, **kwargs):
    if created:
        # Replace this with your actual logic to get the list of school days for the term
        school_days = calculate_school_days(instance)

        for school_day in school_days:
            SchoolDay.objects.create(term=instance, date=school_day)

        students = Student.objects.all()
        for student in students:
            total_school_days = school_days.count()
            present_days = school_days.filter(attendance__student=student, attendance__is_present=True).count()
            attendance_percentage = (present_days / total_school_days) * 100 if total_school_days > 0 else 0

            Result.objects.create(
                student=student,
                term=instance,
                attendance_percentage=attendance_percentage,
            )

def calculate_school_days(term):
    # Replace this with your actual logic to calculate the school days for the term
    # This is a simplified example using a list of dates
    from datetime import timedelta, date

    start_date = term.start_date
    end_date = term.end_date

    delta = end_date - start_date
    return [start_date + timedelta(days=i) for i in range(delta.days + 1)]


@receiver(post_save, sender=Term)
def generate_attendance_records(sender, instance, created, **kwargs):
    if created:
        students = Student.objects.all()
        for student in students:
            school_days = SchoolDay.objects.filter(date__range=(instance.start_date, instance.end_date))
            total_school_days = school_days.count()
            present_days = school_days.filter(attendance__student=student, attendance__is_present=True).count()
            attendance_percentage = (present_days / total_school_days) * 100 if total_school_days > 0 else 0

            Result.objects.create(
                student=student,
                term=instance,
                attendance_percentage=attendance_percentage,
            )


@receiver(post_save, sender=Term)
def create_fee_assignments(sender, instance, created, **kwargs):
    if created:
        students = Student.objects.all()
        for student in students:
            FeeAssignment.objects.create(term=instance, student=student, amount=calculate_class_fee(student.class_name))

def calculate_class_fee(class_name):
    # Add your logic to calculate the fee for each class
    # For example, you might have a predefined fee for each class
    # Adjust this function based on your actual requirements
    class_fee_mapping = {
        'ClassA': 1000,
        'ClassB': 1200,
        'ClassC': 1500,
        # Add more classes as needed
    }
    return class_fee_mapping.get(class_name, 0)


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
