from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from core.models import CustomUser, Teacher, Class, Subject, Session, Term, Assessment, Exam, ClassSubjectAssignment
from core.models import TeacherAssignment, SubjectAssignment


class QuestionPersistenceTests(TestCase):
    def setUp(self):
        # Create users and basic academic structure
        self.teacher_user = CustomUser.objects.create_user(username='t1', password='password', role='teacher')
        # Ensure related teacher profile exists
        self.teacher = self.teacher_user.teacher

        self.session = Session.objects.create(start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=90), is_active=True)
        self.term = Term.objects.create(session=self.session, name='T1', start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=30), is_active=True)
        self.school_class = Class.objects.create(name='Test Class', school_level='Primary')
        self.subject = Subject.objects.create(name='Test Subject', description='Desc')
        ClassSubjectAssignment.objects.create(class_assigned=self.school_class, subject=self.subject, session=self.session, term=self.term)
        # Assign teacher to the class and subject so they can create assessments/exams
        TeacherAssignment.objects.create(class_assigned=self.school_class, teacher=self.teacher, session=self.session, term=self.term, is_form_teacher=True)
        SubjectAssignment.objects.create(class_assigned=self.school_class, subject=self.subject, session=self.session, term=self.term, teacher=self.teacher)

    def test_create_assessment_preserves_posted_questions_on_validation_error(self):
        self.client.login(username='t1', password='password')

        url = reverse('create_assessment')

        due_date = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')

        data = {
            'title': 'Test Assessment',
            'short_description': 'desc',
            'class_assigned': str(self.school_class.pk),
            'subject': str(self.subject.pk),
            'term': str(self.term.pk),
            'due_date': due_date,
            'duration': '30',
            # Add one new MCQ with NO options to force a validation error
            'question_type_1': 'MCQ',
            'question_text_1': 'What is 2+2?',
            'question_options_1': '',  # empty options -> validation error
            'question_correct_answer_1': '',
            'question_points_1': '1',
        }

        response = self.client.post(url, data)

        # View should re-render the form (status 200) and not create an Assessment
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Assessment.objects.count(), 0)

        # The posted question text should appear in the rendered page (hydration JSON or inline)
        self.assertIn(b'What is 2+2?', response.content)

    def test_create_exam_preserves_posted_questions_on_validation_error(self):
        self.client.login(username='t1', password='password')

        url = reverse('create_exam')

        due_date = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')

        data = {
            'title': 'Test Exam',
            'short_description': 'desc',
            'class_assigned': str(self.school_class.pk),
            'subject': str(self.subject.pk),
            'term': str(self.term.pk),
            'due_date': due_date,
            'duration': '45',
            # Add one new SCQ with NO options to force a validation error
            'question_type_1': 'SCQ',
            'question_text_1': 'Choose the right answer',
            'question_options_1': '',
            'question_correct_answer_1': '',
            'question_points_1': '2',
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Exam.objects.count(), 0)
        self.assertIn(b'Choose the right answer', response.content)
