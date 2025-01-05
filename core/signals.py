# signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Student, Term, SchoolDay, Student, Result, FeeAssignment, StudentFeeRecord

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from core.models import CustomUser
from core.tasks import send_email_task


@receiver(post_save, sender=CustomUser)
def send_welcome_email(sender, instance, created, **kwargs):
    if created:
        send_email_task.delay(
            subject="Welcome to Our Platform",
            to_email=instance.email,
            template='emails/welcome_email.html',
            context={'user': instance}
        )


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
