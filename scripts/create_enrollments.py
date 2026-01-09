"""
Create enrollments for students
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lsaapp.settings')
django.setup()

from core.models import Enrollment, Class, Student, Term, Session
import random

def create_enrollments():
    """Create enrollments for all students"""
    
    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        print("No active term found!")
        return
    
    session = active_term.session
    students = Student.objects.all()
    classes = list(Class.objects.all())
    
    print(f"Active Term: {active_term}")
    print(f"Session: {session}")
    print(f"Students: {students.count()}")
    print(f"Classes: {classes}")
    
    if not classes:
        print("No classes found!")
        return
    
    created = 0
    for student in students:
        # Check if already enrolled
        existing = Enrollment.objects.filter(
            student=student,
            term=active_term,
            is_active=True
        ).first()
        
        if existing:
            print(f"✓ {student.user.get_full_name()} already enrolled in {existing.class_enrolled.name}")
        else:
            # Randomly assign a class
            cls = random.choice(classes)
            enrollment = Enrollment.objects.create(
                student=student,
                class_enrolled=cls,
                session=session,
                term=active_term,
                is_active=True
            )
            print(f"✅ Enrolled {student.user.get_full_name()} in {cls.name}")
            created += 1
    
    print(f"\n✅ Created {created} new enrollments!")
    
    # Show summary
    print("\n📊 Enrollment Summary by Class:")
    for cls in classes:
        count = Enrollment.objects.filter(
            class_enrolled=cls,
            term=active_term,
            is_active=True
        ).count()
        print(f"   {cls.name}: {count} students")
    
    print(f"\n   Total: {Enrollment.objects.filter(term=active_term, is_active=True).count()}")

if __name__ == '__main__':
    create_enrollments()
