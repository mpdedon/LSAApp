# lsalms/management/commands/sync_enrollments.py

from django.core.management.base import BaseCommand
from django.db import transaction
from lsalms.models import Course, CourseEnrollment, Student
from core.models import Class 

class Command(BaseCommand):
    help = 'Synchronizes student enrollments for all published internal courses.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.HTTP_INFO("Starting enrollment synchronization..."))
        
        created_count = 0
        
        # Get all active school classes
        active_classes = Class.objects.all()
        if not active_classes:
            self.stdout.write(self.style.WARNING("No classes found in the database. Aborting."))
            return
            
        self.stdout.write(f"Found {active_classes.count()} classes to process.")

        # Loop through each CLASS, not each course
        for school_class in active_classes:
            # Find all internal, published courses for THIS class
            courses_for_this_class = Course.objects.filter(
                linked_class=school_class,
                status=Course.Status.PUBLISHED,
                course_type=Course.CourseType.INTERNAL
            )
            
            # Find all active students in THIS class
            students_in_this_class = Student.objects.filter(
                current_class=school_class,
                status='active'
            )
            
            if not courses_for_this_class.exists() or not students_in_this_class.exists():
                self.stdout.write(f" - Skipping class '{school_class.name}' (no courses or no students).")
                continue
            
            self.stdout.write(self.style.SUCCESS(f"Processing Class: '{school_class.name}'..."))
            self.stdout.write(f"  - Found {students_in_this_class.count()} student(s) and {courses_for_this_class.count()} course(s).")

            # The core logic: Enroll every student in every course for their class
            for student in students_in_this_class:
                for course in courses_for_this_class:
                    enrollment, created = CourseEnrollment.objects.get_or_create(
                        student=student,
                        course=course,
                    )
                    if created:
                        created_count += 1
                        self.stdout.write(f"    + Enrolled '{student.user.username}' in '{course.get_course_title()}'")

        self.stdout.write(self.style.SUCCESS(f"\nSynchronization complete. Created {created_count} new enrollments."))