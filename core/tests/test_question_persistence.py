from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, date

from core.models import (
    CustomUser, Teacher, Class, Subject, Session, Term,
    Assessment, Exam, OnlineQuestion, AssessmentSubmission, ExamSubmission,
    ClassSubjectAssignment, TeacherAssignment, SubjectAssignment,
    Student, Guardian,
)
from core.assessment.forms import AssessmentForm, OnlineQuestionForm as AssessmentQuestionForm
from core.exams.forms import ExamForm


# ---------------------------------------------------------------------------
# Shared helper: build a minimal valid POST payload for creating an assessment
# ---------------------------------------------------------------------------
def _assessment_payload(school_class, subject, term, **overrides):
    due_date = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
    data = {
        'title': 'Test Assessment',
        'short_description': 'desc',
        'class_assigned': str(school_class.pk),
        'subject': str(subject.pk),
        'term': str(term.pk),
        'due_date': due_date,
        'duration': '30',
    }
    data.update(overrides)
    return data


def _exam_payload(school_class, subject, term, **overrides):
    due_date = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
    data = {
        'title': 'Test Exam',
        'short_description': 'desc',
        'class_assigned': str(school_class.pk),
        'subject': str(subject.pk),
        'term': str(term.pk),
        'due_date': due_date,
        'duration': '45',
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Base setup shared across all test classes
# ---------------------------------------------------------------------------
class BaseAssessmentTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher_user = CustomUser.objects.create_user(
            username='teacher1', password='password', role='teacher',
            first_name='Test', last_name='Teacher',
        )
        cls.teacher = cls.teacher_user.teacher

        cls.admin_user = CustomUser.objects.create_superuser(
            username='admin1', password='password', role='admin',
        )

        cls.session = Session.objects.create(
            start_date=date.today(),
            end_date=date.today() + timedelta(days=180),
            is_active=True,
        )
        cls.term = Term.objects.create(
            session=cls.session, name='First Term',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            is_active=True,
        )
        cls.school_class = Class.objects.create(name='JSS 1A', school_level='Junior')
        cls.subject = Subject.objects.create(name='Mathematics', description='Maths')

        ClassSubjectAssignment.objects.create(
            class_assigned=cls.school_class, subject=cls.subject,
            session=cls.session, term=cls.term,
        )
        TeacherAssignment.objects.create(
            class_assigned=cls.school_class, teacher=cls.teacher,
            session=cls.session, term=cls.term, is_form_teacher=True,
        )
        SubjectAssignment.objects.create(
            class_assigned=cls.school_class, subject=cls.subject,
            session=cls.session, term=cls.term, teacher=cls.teacher,
        )

        # Student for submission tests
        cls.student_user = CustomUser.objects.create_user(
            username='student1', password='password', role='student',
            first_name='Alice', last_name='Smith',
        )
        guardian_user = CustomUser.objects.create_user(
            username='guardian1', password='password', role='guardian',
        )
        cls.guardian = Guardian.objects.create(user=guardian_user, address='1 Main St')
        cls.student = Student.objects.create(
            user=cls.student_user,
            date_of_birth=date(2010, 1, 1),
            gender='F',
            student_guardian=cls.guardian,
            relationship='Parent',
            current_class=cls.school_class,
            status='active',
        )


# ===========================================================================
# 1. DRAFT-SAVE BEHAVIOUR (replaces nuclear rollback)
# ===========================================================================
class NuclearRollbackFixTests(BaseAssessmentTestCase):
    """
    With the fix, question errors must NOT delete the assessment header.
    Instead the assessment is saved as an unapproved draft and the teacher
    is redirected to the update page.
    """

    def test_create_assessment_saves_draft_on_question_error(self):
        self.client.force_login(self.teacher_user)
        url = reverse('create_assessment')
        data = _assessment_payload(
            self.school_class, self.subject, self.term,
            # Invalid question: SCQ with no options
            question_type_1='SCQ',
            question_text_1='Bad question no options',
            question_options_1='',
            question_correct_answer_1='',
        )
        response = self.client.post(url, data)

        # Assessment header MUST be saved as a draft
        self.assertEqual(Assessment.objects.count(), 1)
        assessment = Assessment.objects.first()
        self.assertFalse(assessment.is_approved, "Draft should not be auto-approved")
        self.assertEqual(assessment.title, 'Test Assessment')

        # Teacher is redirected to the update page to fix the broken questions
        self.assertRedirects(
            response,
            reverse('update_assessment', kwargs={'assessment_id': assessment.pk}),
        )

    def test_create_exam_saves_draft_on_question_error(self):
        self.client.force_login(self.teacher_user)
        url = reverse('create_exam')
        data = _exam_payload(
            self.school_class, self.subject, self.term,
            question_type_1='SCQ',
            question_text_1='Bad exam question',
            question_options_1='',
            question_correct_answer_1='',
        )
        response = self.client.post(url, data)

        self.assertEqual(Exam.objects.count(), 1)
        exam = Exam.objects.first()
        self.assertFalse(exam.is_approved)

        self.assertRedirects(
            response,
            reverse('update_exam', kwargs={'exam_id': exam.pk}),
        )

    def test_create_assessment_with_valid_question_succeeds(self):
        self.client.force_login(self.teacher_user)
        url = reverse('create_assessment')
        data = _assessment_payload(
            self.school_class, self.subject, self.term,
            question_type_1='SCQ',
            question_text_1='What is 2+2?',
            question_options_1='3, 4, 5, 6',
            question_correct_answer_1='4',
            question_points_1='1',
        )
        response = self.client.post(url, data)

        self.assertEqual(Assessment.objects.count(), 1)
        self.assertEqual(OnlineQuestion.objects.count(), 1)
        # Teacher is redirected to dashboard (not update page)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('update_assessment', response['Location'])


# ===========================================================================
# 2. GAP-SAFE QUESTION PROCESSING
# ===========================================================================
class QuestionGapTests(BaseAssessmentTestCase):
    """
    After JS deletes card #2 of 3, POST contains keys _1 and _3 (gap at 2).
    All submitted questions must be processed.
    """

    def test_questions_with_numbering_gap_all_saved(self):
        self.client.force_login(self.teacher_user)
        url = reverse('create_assessment')
        data = _assessment_payload(
            self.school_class, self.subject, self.term,
            # Question 1
            question_type_1='SCQ',
            question_text_1='First question',
            question_options_1='Yes, No',
            question_correct_answer_1='Yes',
            question_points_1='1',
            # No question_2 key (simulates JS deletion)
            # Question 3
            question_type_3='SCQ',
            question_text_3='Third question',
            question_options_3='A, B',
            question_correct_answer_3='A',
            question_points_3='1',
        )
        response = self.client.post(url, data)

        self.assertEqual(Assessment.objects.count(), 1)
        self.assertEqual(OnlineQuestion.objects.count(), 2, "Both question 1 and question 3 should be saved despite the gap")


# ===========================================================================
# 3. FORM VALIDATION FIXES (dead Meta methods now active)
# ===========================================================================
class FormValidationFixTests(TestCase):
    """
    AssessmentForm.clean_due_date and ExamForm.clean_due_date should now
    reject past dates (they were previously buried inside Meta and never ran).
    """

    @classmethod
    def setUpTestData(cls):
        cls.session = Session.objects.create(
            start_date=date.today(),
            end_date=date.today() + timedelta(days=180),
            is_active=True,
        )
        cls.term = Term.objects.create(
            session=cls.session, name='First Term',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            is_active=True,
        )
        cls.school_class = Class.objects.create(name='JSS 1', school_level='Junior')
        cls.subject = Subject.objects.create(name='English', description='')

    def _base_data(self):
        return {
            'title': 'Draft',
            'class_assigned': self.school_class.pk,
            'subject': self.subject.pk,
            'term': self.term.pk,
            'duration': 30,
        }

    def test_assessment_form_rejects_past_due_date(self):
        data = self._base_data()
        data['due_date'] = (timezone.now() - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        form = AssessmentForm(data=data)
        form.fields['class_assigned'].queryset = Class.objects.filter(pk=self.school_class.pk)
        form.fields['subject'].queryset = Subject.objects.filter(pk=self.subject.pk)
        self.assertFalse(form.is_valid())
        self.assertIn('due_date', form.errors)

    def test_assessment_form_accepts_future_due_date(self):
        data = self._base_data()
        data['due_date'] = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        form = AssessmentForm(data=data)
        form.fields['class_assigned'].queryset = Class.objects.filter(pk=self.school_class.pk)
        form.fields['subject'].queryset = Subject.objects.filter(pk=self.subject.pk)
        # Form errors (other than due_date) are fine; we only assert due_date is clean
        self.assertNotIn('due_date', form.errors)

    def test_exam_form_rejects_past_due_date(self):
        data = self._base_data()
        data['due_date'] = (timezone.now() - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        form = ExamForm(data=data)
        form.fields['class_assigned'].queryset = Class.objects.filter(pk=self.school_class.pk)
        form.fields['subject'].queryset = Subject.objects.filter(pk=self.subject.pk)
        self.assertFalse(form.is_valid())
        self.assertIn('due_date', form.errors)

    def test_exam_form_no_unused_questions_field(self):
        """ExamForm must not expose a 'questions' M2M widget."""
        form = ExamForm()
        self.assertNotIn('questions', form.fields)


# ===========================================================================
# 4. ZERO-QUESTION GUARD ON APPROVAL
# ===========================================================================
class ApprovalGuardTests(BaseAssessmentTestCase):

    def _make_assessment(self):
        return Assessment.objects.create(
            title='Empty Assessment',
            term=self.term,
            subject=self.subject,
            class_assigned=self.school_class,
            created_by=self.admin_user,
            is_approved=False,
            duration=30,
            due_date=timezone.now() + timedelta(days=2),
        )

    def _make_exam(self):
        return Exam.objects.create(
            title='Empty Exam',
            term=self.term,
            subject=self.subject,
            class_assigned=self.school_class,
            created_by=self.admin_user,
            is_approved=False,
            duration=60,
            due_date=timezone.now() + timedelta(days=2),
        )

    def test_approve_assessment_with_no_questions_is_blocked(self):
        self.client.force_login(self.admin_user)
        assessment = self._make_assessment()
        url = reverse('approve_assessment', kwargs={'assessment_id': assessment.pk})
        response = self.client.post(url)

        # Should NOT approve
        assessment.refresh_from_db()
        self.assertFalse(assessment.is_approved)
        # Should redirect back (not to school-setup)
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(assessment.pk), response['Location'])

    def test_approve_assessment_with_questions_succeeds(self):
        self.client.force_login(self.admin_user)
        assessment = self._make_assessment()
        q = OnlineQuestion.objects.create(
            question_type='SCQ',
            question_text='Sample?',
            options=['A', 'B'],
            correct_answer='A',
            points=1,
        )
        assessment.questions.add(q)
        url = reverse('approve_assessment', kwargs={'assessment_id': assessment.pk})
        response = self.client.post(url)

        assessment.refresh_from_db()
        self.assertTrue(assessment.is_approved)

    def test_approve_exam_with_no_questions_is_blocked(self):
        self.client.force_login(self.admin_user)
        exam = self._make_exam()
        url = reverse('approve_exam', kwargs={'exam_id': exam.pk})
        response = self.client.post(url)

        exam.refresh_from_db()
        self.assertFalse(exam.is_approved)
        self.assertEqual(response.status_code, 302)

    def test_approve_exam_with_questions_succeeds(self):
        self.client.force_login(self.admin_user)
        exam = self._make_exam()
        q = OnlineQuestion.objects.create(
            question_type='SCQ',
            question_text='Exam question?',
            options=['X', 'Y'],
            correct_answer='X',
            points=2,
        )
        exam.questions.add(q)
        url = reverse('approve_exam', kwargs={'exam_id': exam.pk})
        response = self.client.post(url)

        exam.refresh_from_db()
        self.assertTrue(exam.is_approved)


# ===========================================================================
# 5. GRADING VIEWS REQUIRE LOGIN (security fix)
# ===========================================================================
class GradingViewAuthTests(BaseAssessmentTestCase):

    def _make_assessment_submission(self):
        assessment = Assessment.objects.create(
            title='Auth Test Assessment',
            term=self.term,
            subject=self.subject,
            class_assigned=self.school_class,
            created_by=self.admin_user,
            is_approved=True,
            duration=30,
            due_date=timezone.now() + timedelta(days=1),
        )
        return AssessmentSubmission.objects.create(
            assessment=assessment,
            student=self.student,
            is_completed=True,
            requires_manual_review=True,
            answers={},
        )

    def _make_exam_submission(self):
        exam = Exam.objects.create(
            title='Auth Test Exam',
            term=self.term,
            subject=self.subject,
            class_assigned=self.school_class,
            created_by=self.admin_user,
            is_approved=True,
            duration=60,
            due_date=timezone.now() + timedelta(days=1),
        )
        return ExamSubmission.objects.create(
            exam=exam,
            student=self.student,
            is_completed=True,
            requires_manual_review=True,
            answers={},
        )

    def test_grade_assessment_unauthenticated_redirects_to_login(self):
        sub = self._make_assessment_submission()
        url = reverse('grade_essay_assessment', kwargs={'submission_id': sub.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'].lower())

    def test_grade_exam_unauthenticated_redirects_to_login(self):
        sub = self._make_exam_submission()
        url = reverse('grade_essay_exam', kwargs={'submission_id': sub.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'].lower())


# ===========================================================================
# 6. ORPHAN QUESTION DELETION (safe cross-model check)
# ===========================================================================
class OrphanQuestionDeletionTests(BaseAssessmentTestCase):

    def test_question_shared_with_exam_is_not_deleted_when_removed_from_assessment(self):
        """A question linked to both an assessment and an exam must survive assessment removal."""
        self.client.force_login(self.admin_user)

        q = OnlineQuestion.objects.create(
            question_type='SCQ',
            question_text='Shared question',
            options=['A', 'B'],
            correct_answer='A',
            points=1,
        )

        assessment = Assessment.objects.create(
            title='Assess with shared Q',
            term=self.term, subject=self.subject,
            class_assigned=self.school_class,
            created_by=self.admin_user,
            is_approved=False, duration=30,
            due_date=timezone.now() + timedelta(days=1),
        )
        assessment.questions.add(q)

        exam = Exam.objects.create(
            title='Exam with shared Q',
            term=self.term, subject=self.subject,
            class_assigned=self.school_class,
            created_by=self.admin_user,
            is_approved=False, duration=60,
            due_date=timezone.now() + timedelta(days=1),
        )
        exam.questions.add(q)

        # Update assessment and mark the shared question for deletion
        update_url = reverse('update_assessment', kwargs={'assessment_id': assessment.pk})
        response = self.client.post(update_url, {
            'title': 'Assess with shared Q',
            'short_description': '',
            'class_assigned': str(self.school_class.pk),
            'subject': str(self.subject.pk),
            'term': str(self.term.pk),
            'due_date': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'duration': '30',
            'deleted_question_ids': str(q.pk),
        })

        # Question must still exist because the exam references it
        self.assertTrue(
            OnlineQuestion.objects.filter(pk=q.pk).exists(),
            "Shared question should not be hard-deleted while still linked to an exam",
        )
        # But it must be removed from the assessment
        assessment.refresh_from_db()
        self.assertNotIn(q, assessment.questions.all())
        # And still present in the exam
        self.assertIn(q, exam.questions.all())

    def test_question_with_no_references_is_deleted(self):
        """A question removed from assessment and not used by any exam must be hard-deleted."""
        self.client.force_login(self.admin_user)

        q = OnlineQuestion.objects.create(
            question_type='SCQ',
            question_text='Orphan question',
            options=['A', 'B'],
            correct_answer='A',
            points=1,
        )

        assessment = Assessment.objects.create(
            title='Assess with orphan Q',
            term=self.term, subject=self.subject,
            class_assigned=self.school_class,
            created_by=self.admin_user,
            is_approved=False, duration=30,
            due_date=timezone.now() + timedelta(days=1),
        )
        assessment.questions.add(q)

        update_url = reverse('update_assessment', kwargs={'assessment_id': assessment.pk})
        self.client.post(update_url, {
            'title': 'Assess with orphan Q',
            'short_description': '',
            'class_assigned': str(self.school_class.pk),
            'subject': str(self.subject.pk),
            'term': str(self.term.pk),
            'due_date': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'duration': '30',
            'deleted_question_ids': str(q.pk),
        })

        self.assertFalse(
            OnlineQuestion.objects.filter(pk=q.pk).exists(),
            "Orphan question (no exam or assessment links) must be hard-deleted",
        )
