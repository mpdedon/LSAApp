"""
Create sample activity log entries for testing the dashboard analytics
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lsaapp.settings')
django.setup()

from core.models import ActivityLog, Student, Teacher, Guardian
from django.utils import timezone
from datetime import timedelta
import random

# Activity types for each role
TEACHER_ACTIVITIES = [
    ('attendance_marked', 'Marked attendance for Class {}'),
    ('assessment_created', 'Created new assessment: {}'),
    ('exam_created', 'Created exam: {}'),
    ('course_updated', 'Updated course: {}'),
    ('score_uploaded', 'Uploaded scores for {} students'),
    ('result_approved', 'Approved results for {}'),
]

GUARDIAN_ACTIVITIES = [
    ('guardian_login', 'Logged into the system'),
    ('view_student_results', 'Viewed student progress report'),
    ('view_fees', 'Checked fee payment history'),
    ('view_attendance', 'Viewed student attendance record'),
    ('payment_made', 'Made a fee payment'),
    ('message_sent', 'Sent message to teacher'),
]

STUDENT_ACTIVITIES = [
    ('student_login', 'Logged into the system'),
    ('assignment_submitted', 'Submitted assignment: {}'),
    ('assessment_submitted', 'Submitted assessment: {}'),
    ('course_viewed', 'Viewed course: {}'),
    ('result_viewed', 'Checked results'),
    ('lesson_completed', 'Completed lesson: {}'),
]

def create_activities():
    """Create sample activity logs for the past week"""
    
    # Get users
    teachers = list(Teacher.objects.filter(status='active').select_related('user')[:5])
    guardians = list(Guardian.objects.filter(status='active').select_related('user')[:5])
    students = list(Student.objects.filter(status='active').select_related('user')[:10])
    
    print(f"Found {len(teachers)} teachers, {len(guardians)} guardians, {len(students)} students")
    
    if not (teachers or guardians or students):
        print("No users found! Please create some users first.")
        return
    
    # Create activities for the past 7 days
    now = timezone.now()
    created_count = 0
    
    # Teacher activities (15-20 per week)
    for teacher in teachers:
        for _ in range(random.randint(3, 5)):
            activity_type, description_template = random.choice(TEACHER_ACTIVITIES)
            description = description_template.format(
                random.choice(['JSS 1', 'JSS 2', 'SSS 1', 'Mathematics', 'English', '20'])
            )
            
            # Random time in past 7 days
            days_ago = random.randint(0, 6)
            hours_ago = random.randint(0, 23)
            created_at = now - timedelta(days=days_ago, hours=hours_ago)
            
            ActivityLog.objects.create(
                user=teacher.user,
                activity_type=activity_type,
                description=description,
                ip_address='127.0.0.1',
                created_at=created_at
            )
            created_count += 1
    
    # Guardian activities (10-15 per week)
    for guardian in guardians:
        for _ in range(random.randint(2, 4)):
            activity_type, description = random.choice(GUARDIAN_ACTIVITIES)
            
            # Random time in past 7 days
            days_ago = random.randint(0, 6)
            hours_ago = random.randint(0, 23)
            created_at = now - timedelta(days=days_ago, hours=hours_ago)
            
            ActivityLog.objects.create(
                user=guardian.user,
                activity_type=activity_type,
                description=description,
                ip_address='127.0.0.1',
                created_at=created_at
            )
            created_count += 1
    
    # Student activities (20-30 per week)
    for student in students:
        for _ in range(random.randint(2, 4)):
            activity_type, description_template = random.choice(STUDENT_ACTIVITIES)
            
            if '{}' in description_template:
                description = description_template.format(
                    random.choice(['Mathematics Assignment', 'English Quiz', 'Science Lab', 'History Chapter 1'])
                )
            else:
                description = description_template
            
            # Random time in past 7 days
            days_ago = random.randint(0, 6)
            hours_ago = random.randint(0, 23)
            created_at = now - timedelta(days=days_ago, hours=hours_ago)
            
            ActivityLog.objects.create(
                user=student.user,
                activity_type=activity_type,
                description=description,
                ip_address='127.0.0.1',
                created_at=created_at
            )
            created_count += 1
    
    print(f"\n✅ Created {created_count} activity log entries successfully!")
    
    # Show summary
    print("\n📊 Activity Summary:")
    print(f"   - Teacher activities: {ActivityLog.objects.filter(user__role='teacher').count()}")
    print(f"   - Guardian activities: {ActivityLog.objects.filter(user__role='guardian').count()}")
    print(f"   - Student activities: {ActivityLog.objects.filter(user__role='student').count()}")
    print(f"   - Total: {ActivityLog.objects.count()}")

if __name__ == '__main__':
    create_activities()
