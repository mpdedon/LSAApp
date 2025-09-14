# core/tests/test_result_views.py

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

# Import all necessary models
from ..models import (
    CustomUser, Guardian, Student, Teacher, Class, Subject, Session, Term, Message,
    Result, SubjectResult, SessionalResult, CumulativeRecord, FinancialRecord, StudentFeeRecord
)

class ResultViewsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        # === USERS & PROFILES ===
        cls.guardian_user = CustomUser.objects.create_user(username='testguardian', password='password123', role='guardian')
        cls.student_user = CustomUser.objects.create_user(username='teststudent', password='password123', role='student')
        cls.other_guardian_user = CustomUser.objects.create_user(username='otherguardian', password='password123', role='guardian')
        cls.teacher_user = CustomUser.objects.create_user(username='testteacher', password='password123', role='teacher')

        cls.guardian = Guardian.objects.get(user=cls.guardian_user)
        cls.student = Student.objects.get(user=cls.student_user)
        cls.teacher = Teacher.objects.get(user=cls.teacher_user)
        
        # === ACADEMIC STRUCTURE ===
        cls.session1 = Session.objects.create(is_active=False, start_date=date(2024, 9, 1), end_date=date(2025, 6, 30))
        cls.session2 = Session.objects.create(is_active=True, start_date=date(2025, 9, 1), end_date=date(2026, 6, 30))
        cls.term1 = Term.objects.create(name="First Term", session=cls.session2, is_active=True, start_date=date(2025, 9, 1), end_date=date(2025, 12, 20))
        cls.prev_term = Term.objects.create(name="Third Term", session=cls.session1, is_active=False, start_date=date(2025, 4, 15), end_date=date(2025, 6, 30))
        cls.class_obj = Class.objects.create(name="JSS 1", order=1, school_level='Secondary')
        cls.math = Subject.objects.create(name="Mathematics", subject_weight=2)
        cls.english = Subject.objects.create(name="English", subject_weight=1)
        
        cls.student.student_guardian = cls.guardian
        cls.student.current_class = cls.class_obj
        cls.student.save()

        # --- CREATE DATA FOR PREVIOUS TERM (for performance change) ---
        cls.prev_result = Result.objects.get(student=cls.student, term=cls.prev_term)
        SubjectResult.objects.create(result=cls.prev_result, subject=cls.math, exam_score=70) # Avg: 70
        cls.prev_result.calculate_term_summary() # Calculate and save summary for past term
        
        cls.prev_sessional_result = SessionalResult.objects.get_or_create(student=cls.student, session=cls.session1)[0]
        cls.prev_sessional_result.calculate_sessional_summary()

        # --- CREATE DATA FOR CURRENT TERM (initially uncalculated) ---
        cls.result = Result.objects.get(student=cls.student, term=cls.term1)
        SubjectResult.objects.create(result=cls.result, subject=cls.math, exam_score=80)
        SubjectResult.objects.create(result=cls.result, subject=cls.english, exam_score=50)
        
        # FIX: SessionalResult for the current session needs to be created
        cls.sessional_result = SessionalResult.objects.get_or_create(student=cls.student, session=cls.session2)[0]
        
        # FIX: Explicitly create the CumulativeRecord that the view expects to exist
        cls.cumulative_record = CumulativeRecord.objects.create(student=cls.student)

        # FIX: Create Message objects needed by the message test
        cls.message_thread = Message.objects.create(sender=cls.teacher_user, recipient=cls.guardian_user, title="Meeting", student_context=cls.student, content="Initial message.")
        cls.message_reply = Message.objects.create(sender=cls.guardian_user, recipient=cls.teacher_user, title="Re: Meeting", parent_message=cls.message_thread, student_context=cls.student, content="I am available.")

        cls.client = Client()
        cls.termly_url = reverse('view_termly_result', kwargs={'student_id': cls.student.pk, 'term_id': cls.term1.id})
        cls.sessional_url = reverse('view_sessional_result', kwargs={'student_id': cls.student.pk, 'session_id': cls.session2.id})
    
    # === TERMLY RESULT VIEW TESTS ===

    def test_termly_result_permission_for_guardian(self):
        self.client.login(username='testguardian', password='password123')
        response = self.client.get(self.termly_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'guardian/view_termly_result.html')

    def test_termly_result_permission_for_student(self):
        self.client.login(username='teststudent', password='password123')
        response = self.client.get(self.termly_url)
        self.assertEqual(response.status_code, 200)

    def test_termly_result_permission_denied_for_other_guardian(self):
        self.client.login(username='otherguardian', password='password123')
        response = self.client.get(self.termly_url)
        self.assertEqual(response.status_code, 403)

    def test_termly_result_just_in_time_calculation(self):
        # Refresh from DB to ensure it's uncalculated before the test
        self.result.refresh_from_db()
        self.assertIsNone(self.result.term_gpa)
        self.assertIsNone(self.result.performance_change)

        self.client.login(username='testguardian', password='password123')
        response = self.client.get(self.termly_url)
        
        self.assertEqual(response.status_code, 200) # First, ensure the page loaded
        
        self.result.refresh_from_db()
        self.assertIsNotNone(self.result.term_gpa)
        self.assertIsNotNone(self.result.performance_change)

    def test_termly_result_context_data_is_correct(self):
        self.client.login(username='testguardian', password='password123')
        response = self.client.get(self.termly_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['student'], self.student)
        self.assertEqual(len(response.context['subject_results']), 2)

        # Expected GPA = ( (5.0 * 2) + (3.0 * 1) ) / (2 + 1) = 13.0 / 3 = 4.33
        expected_gpa = Decimal('4.33')
        self.assertEqual(response.context['result'].term_gpa.quantize(Decimal('0.01')), expected_gpa)

        # Prev Avg = 70. Current Total = 80+50=130, Current Avg = 65.
        # Change = ((65 - 70) / 70) * 100 = -7.14%
        expected_perf_change = Decimal('-7.14')
        self.assertEqual(response.context['result'].performance_change.quantize(Decimal('0.01')), expected_perf_change)
        
        # For the first term in a new session, cumulative should equal termly
        self.assertEqual(response.context['cumulative_gpa'].quantize(Decimal('0.01')), expected_gpa)

    # --- SESSIONAL RESULT VIEW TESTS ---
    
    def test_sessional_result_loads_and_calculates(self):
        self.sessional_result.refresh_from_db()
        self.assertIsNone(self.sessional_result.sessional_gpa)
        
        self.client.login(username='testguardian', password='password123')
        response = self.client.get(self.sessional_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'guardian/view_sessional_result.html')
        
        self.sessional_result.refresh_from_db()
        self.assertIsNotNone(self.sessional_result.sessional_gpa)
        
        # Sessional GPA should equal the only term's GPA in that session
        expected_gpa = Decimal('4.33')
        self.assertEqual(self.sessional_result.sessional_gpa.quantize(Decimal('0.01')), expected_gpa)

    def test_sessional_result_performance_change_and_cumulative(self):
        # Approve the term results so they are included in sessional calculation
        self.prev_result.is_approved = True
        self.prev_result.save()
        self.result.is_approved = True
        self.result.save()
        
        # Approve the sessional results so they are included in cumulative calculation
        self.prev_sessional_result.calculate_sessional_summary()
        self.sessional_result.calculate_sessional_summary()
        
        # Now approve the SESSIONAL results for cumulative calc
        self.prev_sessional_result.is_approved = True
        self.prev_sessional_result.save()
        self.sessional_result.is_approved = True
        self.sessional_result.save()

        self.client.login(username='testguardian', password='password123')
        response = self.client.get(self.sessional_url)
        self.assertEqual(response.status_code, 200)

        # Prev Sessional Avg = 70. Current Sessional Avg = 65.
        # Change = ((65-70)/70)*100 = -7.14%
        expected_perf_change = Decimal('-7.14')
        self.assertEqual(response.context['sessional_result'].performance_change.quantize(Decimal('0.01')), expected_perf_change)

        # Cumulative GPA is calculated from scratch in the model.
        # It will average the two approved sessional GPAs.
        prev_sessional_gpa = self.prev_sessional_result.sessional_gpa
        current_sessional_gpa = self.sessional_result.sessional_gpa
        expected_cgpa = (prev_sessional_gpa + current_sessional_gpa) / 2
        
        self.assertEqual(response.context['cumulative_gpa'].quantize(Decimal('0.01')), expected_cgpa.quantize(Decimal('0.01')))

    # --- MESSAGING VIEW TESTS ---
    
    def test_message_thread_view_loads_and_marks_as_read(self):
        self.client.login(username='testguardian', password='password123')
        
        # We need to test on the parent message, which is unread
        message_to_check = Message.objects.get(pk=self.message_thread.pk)
        message_to_check.is_read = False
        message_to_check.save()

        url = reverse('message_thread', kwargs={'thread_id': self.message_thread.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'messaging/message_thread.html')
        self.assertEqual(response.context['parent_message'], self.message_thread)
        self.assertIn(self.message_reply, response.context['thread_messages'])
        
        # Verify that accessing the thread marked the parent message as read
        self.assertTrue(Message.objects.get(pk=self.message_thread.pk).is_read)