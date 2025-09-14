# core/tests/test_guardian.py

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict # FIX: Added import

# Import all necessary models
from ..models import (
    CustomUser, Guardian, Student, Teacher, Class, Subject, Session, Term, TeacherAssignment, SubjectAssignment,
    Assignment, AssignmentSubmission, Assessment, AssessmentSubmission, Exam, ExamSubmission,
    Message, Notification, AcademicAlert, Result, SessionalResult, 
    FeeAssignment, StudentFeeRecord, FinancialRecord 
)

class GuardianDashboardComprehensiveTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        # === USERS & PROFILES ===
        cls.guardian_user = CustomUser.objects.create_user(username='guardian_kaz', password='password123', role='guardian', first_name='Guardian', last_name='One')
        cls.student_user1 = CustomUser.objects.create_user(username='student_rajab', password='password123', role='student', first_name='Student', last_name='Alpha')
        cls.student_user2 = CustomUser.objects.create_user(username='student_nussy', password='password123', role='student', first_name='Student', last_name='Beta')
        cls.other_guardian_user = CustomUser.objects.create_user(username='other_guardian', password='password123', role='guardian')
        cls.teacher_user = CustomUser.objects.create_user(username='testteacher', password='password123', role='teacher', first_name='Tahir', last_name='Musa')
        cls.admin_user = CustomUser.objects.create_superuser(username='admin', password='password123', role='admin')

        cls.guardian = Guardian.objects.get(user=cls.guardian_user)
        cls.other_guardian = Guardian.objects.get(user=cls.other_guardian_user)
        cls.teacher = Teacher.objects.get(user=cls.teacher_user)

        # === ACADEMIC STRUCTURE ===
        cls.session = Session.objects.create(is_active=True, start_date=date(2025, 9, 1), end_date=date(2026, 6, 30))
        cls.past_session = Session.objects.create(is_active=False, start_date=date(2024, 9, 1), end_date=date(2025, 6, 30))
        cls.active_term = Term.objects.create(name="First Term", session=cls.session, is_active=True, start_date=date(2025, 9, 1), end_date=date(2025, 12, 20))
        cls.archived_term = Term.objects.create(name="Third Term", session=cls.past_session, is_active=False, start_date=date(2025, 4, 15), end_date=date(2025, 6, 30))
        cls.class_obj = Class.objects.create(name="JSS 1", order=1, school_level='secondary')
        cls.subject = Subject.objects.create(name="Mathematics")
        cls.english_subject = Subject.objects.create(name="English")

        TeacherAssignment.objects.create(teacher=cls.teacher, class_assigned=cls.class_obj, term=cls.active_term, session=cls.session)
        SubjectAssignment.objects.create(teacher=cls.teacher, subject=cls.subject, class_assigned=cls.class_obj, term=cls.active_term, session=cls.session)

        # --- STUDENTS (WARDS) ---
        cls.student1 = Student.objects.get(user=cls.student_user1)
        cls.student1.student_guardian = cls.guardian
        cls.student1.current_class = cls.class_obj
        cls.student1.save()

        cls.student2 = Student.objects.get(user=cls.student_user2)
        cls.student2.student_guardian = cls.guardian
        cls.student2.current_class = cls.class_obj
        cls.student2.save()
        
        cls.other_student_user = CustomUser.objects.create_user(username='otherstudent', password='password123', role='student')
        cls.other_student = Student.objects.get(user=cls.other_student_user)
        cls.other_student.student_guardian = cls.other_guardian
        cls.other_student.current_class = cls.class_obj
        cls.other_student.save()

        # --- TASKS & SUBMISSIONS ---
        cls.assignment1 = Assignment.objects.create(teacher=cls.teacher, title="Algebra HW", subject=cls.subject, class_assigned=cls.class_obj, term=cls.active_term, due_date=timezone.now() + timedelta(days=5))
        cls.assessment1 = Assessment.objects.create(created_by=cls.teacher_user, title="Poetry Test", subject=cls.english_subject, class_assigned=cls.class_obj, term=cls.active_term, is_approved=True, due_date=timezone.now() + timedelta(days=10))
        cls.exam1 = Exam.objects.create(created_by=cls.admin_user, title="End of Term Exam", subject=cls.subject, class_assigned=cls.class_obj, term=cls.active_term, is_approved=True, due_date=timezone.now() + timedelta(days=15))
        AssignmentSubmission.objects.create(student=cls.student1, assignment=cls.assignment1, is_completed=True, answers={})

        # --- FINANCIAL & RESULT DATA (WITH FIX) ---
        # FIX 1: Create the FeeAssignment first.
        cls.fee_assignment = FeeAssignment.objects.create(term=cls.active_term, class_instance=cls.class_obj, amount=50000)
        
        cls.fee_record = StudentFeeRecord.objects.create(
            student=cls.student1,
            term=cls.active_term,
            fee_assignment=cls.fee_assignment, 
            amount=50000,
            net_fee=50000
        )
        
        cls.financial_record = FinancialRecord.objects.get(student=cls.student1, term=cls.active_term)
        cls.financial_record.total_paid = 45000
        cls.financial_record.save()
        
        cls.term_result = Result.objects.get(student=cls.student1, term=cls.active_term)
        cls.term_result.is_published = True
        cls.term_result.save()

        cls.sessional_result = SessionalResult.objects.get_or_create(student=cls.student1, session=cls.session)[0]
        cls.sessional_result.is_published = True
        cls.sessional_result.sessional_gpa = Decimal('4.50')
        cls.sessional_result.save()

        cls.archived_result = Result.objects.get(student=cls.student1, term=cls.archived_term)
        cls.archived_result.is_published = True
        cls.archived_result.is_archived = True
        cls.archived_result.save()
        
        cls.archived_sessional_result = SessionalResult.objects.get_or_create(student=cls.student1, session=cls.past_session)[0]
        cls.archived_sessional_result.is_published = True
        cls.archived_sessional_result.save()

        # --- ALERTS & MESSAGES ---
        cls.alert = AcademicAlert.objects.create(student=cls.student2, alert_type='assessment_available', title="Poetry Test is Live", due_date=timezone.now() + timedelta(days=10), related_object_id=cls.assessment1.id)
        cls.notification = Notification.objects.create(audience='guardian', message="Parent-Teacher meeting next Friday.")
        cls.message_thread = Message.objects.create(sender=cls.teacher_user, recipient=cls.guardian_user, title="Meeting about Rajab", content="Can we chat?")

        cls.client = Client()
        cls.dashboard_url = reverse('guardian_dashboard')

    def setUp(self):
        self.client.login(username='guardian_kaz', password='password123')

    def test_unauthenticated_access_redirects(self):
        self.client.logout()
        response = self.client.get(self.dashboard_url)
        expected_url = f"auth/login?next={self.dashboard_url}"  
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)

    def test_teacher_access_is_forbidden(self):
        self.client.login(username='testteacher', password='password123')
        response = self.client.get(self.dashboard_url)
        expected_url = f"auth/login?next={self.dashboard_url}"     
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)

    def test_dashboard_loads_for_correct_guardian(self):
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'guardian/guardian_dashboard.html')
        
    def test_context_contains_correct_wards(self):
        response = self.client.get(self.dashboard_url)
        self.assertIn('students', response.context)
        self.assertEqual(len(response.context['students']), 2)
        student_pks_in_context = [s.pk for s in response.context['students']]
        self.assertIn(self.student1.pk, student_pks_in_context)
        self.assertIn(self.student2.pk, student_pks_in_context)
        self.assertNotIn(self.other_student.pk, student_pks_in_context)

    def test_context_assignments_data_is_correctly_structured(self):
        response = self.client.get(self.dashboard_url)
        assignments_data = response.context['assignments_data']
        self.assertIsInstance(assignments_data, defaultdict)
        
        student1_data = assignments_data[self.student1.pk]
        self.assertEqual(student1_data['total'], 1)
        self.assertEqual(student1_data['completed'], 1)
        self.assertTrue(student1_data['details'][0]['submitted'])
        self.assertEqual(student1_data['details'][0]['obj'], self.assignment1)

        student2_data = assignments_data[self.student2.pk]
        self.assertEqual(student2_data['total'], 1)
        self.assertEqual(student2_data['completed'], 0)
        self.assertFalse(student2_data['details'][0]['submitted'])
        
    def test_context_assessments_and_exams_data_is_correct(self):
        response = self.client.get(self.dashboard_url)
        assessments_data = response.context['assessments_data']
        exams_data = response.context['exams_data']
        
        student1_assessments = assessments_data[self.student1.pk]['details']
        student1_exams = exams_data[self.student1.pk]['details']
        
        self.assertEqual(len(student1_assessments), 1)
        self.assertEqual(student1_assessments[0]['obj'], self.assessment1)
        self.assertFalse(student1_assessments[0]['submitted'])
        
        self.assertEqual(len(student1_exams), 1)
        self.assertEqual(student1_exams[0]['obj'], self.exam1)
        self.assertFalse(student1_exams[0]['submitted'])

    def test_context_financial_data_is_correct(self):
        response = self.client.get(self.dashboard_url)
        financial_data = response.context['financial_data']
        self.assertIn(self.student1.pk, financial_data)
        self.assertEqual(financial_data[self.student1.pk], self.financial_record)
        self.assertNotIn(self.student2.pk, financial_data)

    def test_context_result_data_is_correct(self):
        response = self.client.get(self.dashboard_url)
        result_data = response.context['result_data']
        sessional_results_data = response.context['sessional_results_data']
        archived_results_data = response.context['archived_results_data']
        archived_sessional_results_data = response.context['archived_sessional_results_data']

        self.assertIn(self.student1.pk, result_data)
        self.assertEqual(result_data[self.student1.pk], self.term_result)
        self.assertIn(self.student1.pk, sessional_results_data)
        self.assertEqual(sessional_results_data[self.student1.pk], self.sessional_result)
        self.assertIn(self.student1.pk, archived_results_data)
        self.assertIn(self.archived_result, archived_results_data[self.student1.pk])
        self.assertIn(self.student1.pk, archived_sessional_results_data)
        self.assertIn(self.archived_sessional_result, archived_sessional_results_data[self.student1.pk])
        self.assertNotIn(self.student2.pk, result_data)

    def test_context_communication_data_is_correct(self):
        response = self.client.get(self.dashboard_url)
        self.assertIn('notifications', response.context)
        self.assertIn(self.notification, response.context['notifications'])
        self.assertIn('message_threads', response.context)
        self.assertEqual(response.context['message_threads'].count(), 1)
        self.assertIn(self.message_thread, response.context['message_threads'])
        self.assertEqual(response.context['unread_message_count'], 1)