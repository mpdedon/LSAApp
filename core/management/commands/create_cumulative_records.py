"""
Management command to create CumulativeRecord for all students that don't have one.
This fixes the RelatedObjectDoesNotExist error for existing students.

Usage:
    python manage.py create_cumulative_records
"""

from django.core.management.base import BaseCommand
from core.models import Student, CumulativeRecord
from decimal import Decimal


class Command(BaseCommand):
    help = 'Create CumulativeRecord for all students that do not have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update-all',
            action='store_true',
            help='Update cumulative GPA for all students (even those with existing records)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Creating Missing Cumulative Records'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Get all active students
        all_students = Student.objects.filter(status='active')
        total_students = all_students.count()
        
        self.stdout.write(f'\nTotal active students: {total_students}')
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for student in all_students:
            try:
                # Try to get existing record
                try:
                    cumulative_record = student.cumulative_record
                    
                    if options['update_all']:
                        cumulative_record.update_cumulative_gpa(save=True)
                        updated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Updated: {student.user.get_full_name()} (ID: {student.pk})')
                        )
                    
                except Student.cumulative_record.RelatedObjectDoesNotExist:
                    # Create new cumulative record
                    cumulative_record = CumulativeRecord.objects.create(
                        student=student,
                        cumulative_gpa=Decimal('0.00')
                    )
                    cumulative_record.update_cumulative_gpa(save=True)
                    created_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'  + Created: {student.user.get_full_name()} (ID: {student.pk})')
                    )
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error for {student.user.get_full_name()}: {str(e)}')
                )
        
        # Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('Summary:'))
        self.stdout.write(f'  Total students processed: {total_students}')
        self.stdout.write(self.style.WARNING(f'  Cumulative records created: {created_count}'))
        
        if options['update_all']:
            self.stdout.write(self.style.SUCCESS(f'  Cumulative records updated: {updated_count}'))
        
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'  Errors encountered: {error_count}'))
        
        self.stdout.write('=' * 70)
        
        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Successfully created {created_count} missing cumulative records!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\n✓ All students already have cumulative records!')
            )
