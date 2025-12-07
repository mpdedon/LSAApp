from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from core.models import (
    CustomUser, Student, Teacher, Class, Subject, Session, Term,
    Assessment, OnlineQuestion, AssessmentSubmission, ClassSubjectAssignment, TeacherAssignment, SubjectAssignment
)


class ResultFieldMappingTests(TestCase):
    def setUp(self):
        # Create teacher and student users (profiles auto-created in tests)
        self.teacher_user = CustomUser.objects.create_user(username='tm', password='pass', role='teacher')
        self.student_user = CustomUser.objects.create_user(username='st', password='pass', role='student')

        self.teacher = self.teacher_user.teacher
        self.student = self.student_user.student

        # Academic structure
        self.session = Session.objects.create(start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=90), is_active=True)
        self.term = Term.objects.create(session=self.session, name='TermOne', start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=30), is_active=True)
        self.school_class = Class.objects.create(name='RMClass', school_level='Primary')
        self.subject = Subject.objects.create(name='Science', description='Sci')

        # Link subject/class and teacher
        ClassSubjectAssignment.objects.create(class_assigned=self.school_class, subject=self.subject, session=self.session, term=self.term)
        TeacherAssignment.objects.create(class_assigned=self.school_class, teacher=self.teacher, session=self.session, term=self.term, is_form_teacher=True)
        SubjectAssignment.objects.create(class_assigned=self.school_class, subject=self.subject, session=self.session, term=self.term, teacher=self.teacher)

        # Assign student to class
        self.student.current_class = self.school_class
        self.student.save()

    def test_assessment_mapping_updates_subject_result_scaled(self):
        # Create an assessment that maps to continuous_assessment_1 (max 10)
        assessment = Assessment.objects.create(
            title='Map Test',
            term=self.term,
            subject=self.subject,
            class_assigned=self.school_class,
            created_by=self.teacher_user,
            result_field_mapping='continuous_assessment_1'
        )

        # Add two questions with points totaling 5
        q1 = OnlineQuestion.objects.create(question_type='SCQ', question_text='Q1', points=2)
        q2 = OnlineQuestion.objects.create(question_type='SCQ', question_text='Q2', points=3)
        assessment.questions.add(q1, q2)

        # Create a graded submission with score 4 out of total 5
        submission = AssessmentSubmission.objects.create(
            assessment=assessment,
            student=self.student,
            score=4,
            is_graded=True,
            is_completed=True
        )

        # Signal should have run on save; fetch SubjectResult
        from core.models import SubjectResult, Result

        result_sheet = Result.objects.filter(student=self.student, term=self.term).first()
        self.assertIsNotNone(result_sheet, "Result sheet should be created by mapping signal")

        subject_result = SubjectResult.objects.filter(result=result_sheet, subject=self.subject).first()
        self.assertIsNotNone(subject_result, "SubjectResult should be created/updated")

        # Expected scaled value = (4 / 5) * 10 = 8.0
        expected = Decimal('8')
        actual = getattr(subject_result, 'continuous_assessment_1')
        # Allow small decimal differences but expect exact here
        self.assertIsNotNone(actual)
        self.assertEqual(Decimal(actual).quantize(Decimal('0.1')), expected.quantize(Decimal('0.1')))
