# lsalms/tests.py

from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

# Import your models from both apps
from core.models import Student, Teacher, Guardian, Class, Subject, Term, Session, CustomUser, ClassSubjectAssignment
from .models import Course, CourseEnrollment, Module, Lesson, ContentBlock, GradedActivity, LessonProgress

# === Test Suite for the LSALMS Application ===

class LMSCoreWorkflowTests(TestCase):
    """
    This test suite covers the entire core workflow from a teacher creating a course
    to a student accessing it, ensuring all automation works as expected.
    """

    def setUp(self):
        """
        This method runs BEFORE every single test function.
        It sets up a clean, predictable set of data for each test to use.
        """
        # 1. Create Users
        self.teacher_user = CustomUser.objects.create_user(username='testteacher', password='password', role='teacher')
        self.student_user = CustomUser.objects.create_user(username='teststudent', password='password', role='student')
        self.admin_user = CustomUser.objects.create_superuser(username='testadmin', password='password')

        # 2. Create Academic Structure
        self.session = Session.objects.create(start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=90), is_active=True)
        self.term = Term.objects.create(session=self.session, name='First Term', start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=30), is_active=True)
        self.school_class = Class.objects.create(name='Primary 5', school_level='Primary')
        self.subject = Subject.objects.create(name='Mathematics', description='Maths')
        
        # Link subject to the class
        ClassSubjectAssignment.objects.create(class_assigned=self.school_class, subject=self.subject, session=self.session, term=self.term)

        # 3. Create Profiles
        self.teacher = self.teacher_user.teacher
        self.student = self.student_user.student
        self.student.current_class = self.school_class
        self.student.save()

    def test_teacher_can_create_internal_course(self):
        """
        Tests if a logged-in teacher can successfully create a new internal course.
        """
        self.client.login(username='testteacher', password='password')
        
        create_course_url = reverse('lsalms:course_create')
        
        course_data = {
            'course_type': 'INTERNAL',
            'linked_class': self.school_class.pk,
            'term': self.term.pk,
            'subject': self.subject.pk,
            'learning_objectives': 'Test objectives'
        }
        
        # Simulate a POST request to the create view
        response = self.client.post(create_course_url, course_data)
        
        # Check 1: Was the course actually created?
        self.assertEqual(Course.objects.count(), 1)
        new_course = Course.objects.first()
        self.assertEqual(new_course.subject, self.subject)
        self.assertEqual(new_course.teacher, self.teacher_user)
        
        # Check 2: Were we redirected to the Course Builder page?
        self.assertRedirects(response, reverse('lsalms:course_manage', kwargs={'slug': new_course.slug}))
        
        print("✅ PASSED: test_teacher_can_create_internal_course")

    def test_course_publish_signal_triggers_auto_enrollment(self):
        """
        Tests the most critical piece of automation: Does publishing a course
        automatically create CourseEnrollment records via the Django signal?
        """
        # 1. A teacher creates a course (it starts as a DRAFT)
        course = Course.objects.create(
            teacher=self.teacher_user,
            course_type='INTERNAL',
            status='DRAFT',
            linked_class=self.school_class,
            term=self.term,
            subject=self.subject
        )
        
        # Check 1: Before publishing, the student should NOT be enrolled.
        self.assertEqual(CourseEnrollment.objects.filter(student=self.student, course=course).count(), 0)
        
        # 2. The teacher now publishes the course.
        course.status = Course.Status.PUBLISHED
        course.save() # This is what triggers the post_save signal
        
        # Check 2: After publishing, the student SHOULD now be enrolled.
        self.assertTrue(CourseEnrollment.objects.filter(student=self.student, course=course).exists())
        self.assertEqual(CourseEnrollment.objects.count(), 1)
        
        print("✅ PASSED: test_course_publish_signal_triggers_auto_enrollment")

    def test_student_can_see_enrolled_course_on_dashboard(self):
        """
        Tests if a student can see their course on the dashboard after being auto-enrolled.
        """
        # 1. Setup: Create and publish a course, which auto-enrolls the student.
        course = Course.objects.create(
            teacher=self.teacher_user,
            course_type='INTERNAL',
            status='PUBLISHED', # Create it as published to trigger the signal
            linked_class=self.school_class,
            term=self.term,
            subject=self.subject
        )
        
        # 2. Log in as the student and go to their dashboard
        self.client.login(username='teststudent', password='password')
        dashboard_url = reverse('student_dashboard')
        response = self.client.get(dashboard_url)
        
        # Check 1: The page should load successfully.
        self.assertEqual(response.status_code, 200)
        
        # Check 2: The context variable for internal enrollments should contain our course.
        self.assertIn('lms_internal_enrollments', response.context)
        enrollments_in_context = response.context['lms_internal_enrollments']
        self.assertEqual(len(enrollments_in_context), 1)
        self.assertEqual(enrollments_in_context[0].course, course)
        
        # Check 3: The course title should be rendered in the final HTML.
        self.assertContains(response, course.get_course_title())
        
        print("✅ PASSED: test_student_can_see_enrolled_course_on_dashboard")

    def test_student_cannot_see_draft_course(self):
        """
        Tests that a student cannot see a course that is still a draft, even if they are
        somehow enrolled in it.
        """
        # 1. Setup: Create a DRAFT course and MANUALLY enroll the student.
        course = Course.objects.create(
            teacher=self.teacher_user,
            course_type='INTERNAL',
            status='DRAFT',
            linked_class=self.school_class,
            term=self.term,
            subject=self.subject
        )
        CourseEnrollment.objects.create(student=self.student, course=course)
        
        # 2. Log in as the student and go to their dashboard
        self.client.login(username='teststudent', password='password')
        dashboard_url = reverse('student_dashboard')
        response = self.client.get(dashboard_url)
        
        # Check: The course title should NOT be in the HTML.
        self.assertNotContains(response, course.get_course_title())
        # The context list should be empty because our view filters out non-published courses.
        self.assertEqual(len(response.context['lms_internal_enrollments']), 0)
        
        print("✅ PASSED: test_student_cannot_see_draft_course")

    def test_progress_calculation_and_completion(self):
        """
        Tests the lesson completion and progress calculation logic.
        """
        # 1. Setup: Create a course with 2 lessons
        course = Course.objects.create(teacher=self.teacher_user, status='PUBLISHED', course_type='INTERNAL', linked_class=self.school_class, term=self.term, subject=self.subject)
        enrollment = CourseEnrollment.objects.create(student=self.student, course=course)
        module = Module.objects.create(course=course, title="Test Module")
        lesson1 = Lesson.objects.create(module=module, title="Lesson 1", order=1)
        lesson2 = Lesson.objects.create(module=module, title="Lesson 2", order=2)
        
        enrollment = CourseEnrollment.objects.get(student=self.student, course=course)
        # Sanity check that the enrollment exists.
        self.assertIsNotNone(enrollment)
        # 2. Log in as student, go to the course detail page
        self.client.login(username='teststudent', password='password')
        course_detail_url = reverse('lsalms:course_detail', kwargs={'slug': course.slug})
        response = self.client.get(course_detail_url)
        
        # Check 1: Initial progress should be 0%
        self.assertEqual(response.context['progress_percent'], 0)
        self.assertEqual(response.context['next_lesson'], lesson1)
        
        # 3. Simulate completing the first lesson
        complete_lesson1_url = reverse('lsalms:mark_lesson_complete', kwargs={'lesson_id': lesson1.id})
        self.client.post(complete_lesson1_url)
        
        # Check 2: Progress should now be 50%
        self.assertEqual(LessonProgress.objects.count(), 1)
        response_after_completion = self.client.get(course_detail_url)
        self.assertEqual(response_after_completion.context['progress_percent'], 50)
        self.assertEqual(response_after_completion.context['next_lesson'], lesson2)
        
        print("✅ PASSED: test_progress_calculation_and_completion")