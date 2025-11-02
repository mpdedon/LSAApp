# lsalms/management/commands/sync_enrollments.py

from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Student, Term
from lsalms.models import Course, CourseEnrollment

class Command(BaseCommand):
    help = 'Synchronizes internal course enrollments for all active students based on their current class and the active term.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting enrollment synchronization..."))

        # 1. Get the single active term.
        active_term = Term.objects.filter(is_active=True).first()
        if not active_term:
            self.stderr.write(self.style.ERROR("Synchronization failed: No active term found. Please set an active term in the admin."))
            return

        self.stdout.write(f"Found active term: {active_term}")

        # 2. Get all active students who have a current class assigned.
        active_students = Student.objects.filter(
            status='active',
            current_class__isnull=False
        ).select_related('current_class', 'user')

        if not active_students.exists():
            self.stdout.write("No active students found. Nothing to do.")
            return

        self.stdout.write(f"Found {active_students.count()} active students to process.")
        
        # 3. Initialize counters for the summary report.
        total_enrollments_created = 0
        students_processed = 0

        # Use a transaction to ensure the entire operation is atomic.
        with transaction.atomic():
            for student in active_students:
                students_processed += 1
                
                # Find all INTERNAL, PUBLISHED courses for the student's current class in the active term.
                courses_for_class = Course.objects.filter(
                    course_type=Course.CourseType.INTERNAL,
                    linked_class=student.current_class,
                    term=active_term,
                    status=Course.Status.PUBLISHED
                )

                if not courses_for_class.exists():
                    self.stdout.write(f" -> No active internal courses found for class '{student.current_class}'. Skipping student {student}.")
                    continue

                enrollments_for_this_student = 0
                for course in courses_for_class:
                    # Use get_or_create to safely create the enrollment only if it doesn't exist.
                    # This makes the command safe to run multiple times.
                    enrollment, created = CourseEnrollment.objects.get_or_create(
                        student=student,
                        course=course
                    )
                    
                    if created:
                        total_enrollments_created += 1
                        enrollments_for_this_student += 1

                if enrollments_for_this_student > 0:
                    self.stdout.write(self.style.SUCCESS(f" -> Created {enrollments_for_this_student} new enrollment(s) for {student} in {student.current_class}."))
                else:
                    self.stdout.write(f" -> {student} is already correctly enrolled.")

        # 4. Print a final summary report.
        self.stdout.write("\n" + "="*30)
        self.stdout.write(self.style.SUCCESS("Enrollment Synchronization Complete!"))
        self.stdout.write(f"Total Students Processed: {students_processed}")
        self.stdout.write(f"Total New Enrollments Created: {total_enrollments_created}")
        self.stdout.write("="*30 + "\n")