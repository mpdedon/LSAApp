# views.py

import io 
import json
import random
import pathlib
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.template.loader import render_to_string
from django.http import HttpResponse, Http404, HttpResponseForbidden, HttpResponseNotAllowed
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg, F, DecimalField, Case, When, Value
from django.db.models.functions import Cast
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from playwright.sync_api import sync_playwright
from .forms import GuardianRegistrationForm, MessageForm, ReplyForm
from core.models import CustomUser, Guardian, Term, Teacher, Session, FinancialRecord, Student, Result, Subject, SubjectResult, Attendance
from core.models import Assignment, Assessment, Exam, AssessmentSubmission, ExamSubmission, Message, CumulativeRecord, SessionalResult, StudentFeeRecord
from core.assignment.forms import AssignmentSubmission, AssignmentSubmissionForm


try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except ImportError:
    HTML = None # Handle case where WeasyPrint might not be installed
    CSS = None
    FontConfiguration = None


# Guardian Views
class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser
    

def GuardianRegisterView(request):
    if request.method == 'POST':
        form = GuardianRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('guardian_dashboard')
    else:
        form = GuardianRegistrationForm()
    return render(request, 'guardian/register.html', {'form': form})

def GuardianProfileView(request):
    if request.method == 'POST':
        form = GuardianRegistrationForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('guardian_dashboard')
    else:
        form = GuardianRegistrationForm(instance=request.user)
    return render(request, 'guardian/profile.html', {'form': form})

@login_required
def guardian_dashboard(request):
    if not request.user.role == 'guardian':
        return redirect('login')
    # Add any data for guardians
    return render(request, 'guardian_dashboard.html')


class GuardianListView(View, AdminRequiredMixin):
    template_name = 'guardian/guardian_list.html'

    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        status = request.GET.get('status', 'active')

        guardians = Guardian.objects.filter(status=status).order_by('user__first_name', 'user__last_name')

        if query:
            guardians = guardians.filter(
                Q(user__username__icontains=query)  |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__email__icontains=query) |
                Q(contact__icontains=query) 
            )

        paginator = Paginator(guardians, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'active_tab': status,
            'query': query,
        })

class GuardianBulkActionView(View, AdminRequiredMixin):
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        selected_guardians = request.POST.getlist('selected_guardians')

        if not action or not selected_guardians:
            messages.error(request, "Please select both an action and at least one guardian.")
            return redirect('guardian_list')

        guardians = Guardian.objects.filter(user__id__in=selected_guardians)

        if action == 'mark_dormant':
            guardians.update(status='dormant')
            messages.success(request, "Selected guardians marked as dormant.")
        elif action == 'mark_active':
            guardians.update(status='active')
            messages.success(request, "Selected guardians marked as active.")
        elif action == 'mark_left':
            guardians.update(status='left')
            messages.success(request, "Selected guardians marked as left.")
        else:
            messages.error(request, "Invalid action selected.")
        
        return redirect('guardian_list')
    
class GuardianCreateView(View):
    template_name = 'guardian/guardian_form.html'

    def get(self, request, *args, **kwargs):
        form = GuardianRegistrationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = GuardianRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('guardian_list')
        else:
            print(form.errors)
            
        return render(request, self.template_name, {'form': form})

class GuardianUpdateView(View):
    template_name = 'guardian/guardian_form.html'

    def get(self, request, pk, *args, **kwargs):
        guardian = get_object_or_404(Guardian, pk=pk)
        form = GuardianRegistrationForm(instance=guardian.user, guardian_instance=guardian)
        return render(request, self.template_name, {'form': form, 'is_update': True, 'guardian': guardian})
    
    def post(self, request, pk, *args, **kwargs):
        guardian = get_object_or_404(Guardian, pk=pk)
        form = GuardianRegistrationForm(request.POST, request.FILES, instance=guardian.user, guardian_instance=guardian)

        if form.is_valid():
            user = form.save(commit=False)
            user.save()

            guardian.gender = form.cleaned_data['gender']
            guardian.profile_image = form.cleaned_data['profile_image']
            guardian.contact = form.cleaned_data['contact']
            guardian.address= form.cleaned_data['address']

            guardian.save()
            
            return redirect('guardian_detail', pk=guardian.pk)
            
        print(f"Form Errors: {form.errors}")
        return render(request, self.template_name, {'form': form, 'is_update': True, 'guardian': guardian})
  
class GuardianDetailView(View):
    template_name = 'guardian/guardian_detail.html'

    def get(self, request, pk, *args, **kwargs):
        guardian = get_object_or_404(Guardian, pk=pk)
        return render(request, self.template_name, {'guardian': guardian})
    
class GuardianDeleteView(View):
    template_name = 'guardian/guardian_confirm_delete.html'

    def get(self, request, pk, *args, **kwargs):
        guardian = get_object_or_404(Guardian, pk=pk)
        return render(request, self.template_name, {'guardian': guardian})

    def post(self, request, pk, *args, **kwargs):
        guardian = get_object_or_404(Guardian, pk=pk)
        guardian.delete()
        return redirect('guardian_list')


@login_required
@user_passes_test(lambda u: u.role == 'guardian')
def financial_record_detail(request, student_id):
    guardian = request.user.guardian
    student = get_object_or_404(guardian.students, id=student_id)
    current_term = Term.objects.get(is_current=True)
    
    # Get all financial records for the student, including past terms
    financial_records = FinancialRecord.objects.filter(student=student).order_by('-term__start_date')

    context = {
        'student': student,
        'financial_records': financial_records,
        'current_term': current_term,
    }
    return render(request, 'guardian/financial_record_detail.html', context)


def generate_pdf_from_html(html_content, output_path):
    """Generate a PDF from an HTML string using Playwright"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        
        # Generate PDF
        page.pdf(path=output_path, format="A4", print_background=True)
        
        browser.close()


@login_required
def assignment_list(request):
    """
    Display all assignments available to the student or guardian.
    """
    user = request.user
    if hasattr(user, 'student'):
        # If the user is a student, fetch assignments for their class
        assignments = Assignment.objects.filter(class_assigned=user.student.current_class)
    elif hasattr(user, 'guardian'):
        # If the user is a guardian, fetch assignments for their wards
        students = user.guardian.student_set.all()
        assignments = Assignment.objects.filter(class_assigned__in=[s.current_class for s in students])
    else:
        assignments = []

    return render(request, 'assignment/assignment_list.html', {'assignments': assignments})


# Helper to get client IP
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

# Helper to manage student/guardian logic to keep views DRY
def get_student_for_item(request, item, item_type_verbose, submit_url_name, template_path):
    """
    Handles student/guardian logic. Returns a student object or a redirect response.
    `item` can be an Assignment, Assessment, or Exam.
    """
    if hasattr(request.user, 'guardian'):
        guardian = request.user.guardian
        students = Student.objects.filter(student_guardian=guardian, current_class=item.class_assigned)
        if not students.exists():
            messages.error(request, "No students associated with this guardian are in this class.")
            return redirect('guardian_dashboard')
        
        student_id = request.GET.get('student_id')
        if student_id:
            return get_object_or_404(students, id=student_id)
        elif students.count() == 1:
            return students.first()
        else:
            return render(request, template_path, {
                'students': students, 'item': item, 
                'item_type_verbose': item_type_verbose, 'submit_url_name': submit_url_name
            })
    else:
        return get_object_or_404(Student, user=request.user, current_class=item.class_assigned)


@login_required
def start_assignment(request, assignment_id):
    """STEP 1: Entry point. Creates submission, starts timer, gets IP, and redirects."""
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    response = get_student_for_item(request, assignment)
    if not isinstance(response, Student):
        return response 
    student = response

    if AssignmentSubmission.objects.filter(assignment=assignment, student=student, is_completed=True).exists():
        return render(request, 'assignment/already_submitted.html', {"assignment": assignment, "student": student})

    submission, created = AssignmentSubmission.objects.get_or_create(
        assignment=assignment, student=student,
        defaults={'ip_address': get_client_ip(request)}
    )

    if not submission.started_at and assignment.duration:
        submission.started_at = timezone.now()
        submission.save()

    return redirect('take_assignment', submission_id=submission.id)


@login_required
def take_assignment(request, submission_id):
    """STEP 2: The main page where the student takes the assignment."""
    submission = get_object_or_404(AssignmentSubmission.objects.select_related('assignment', 'student__user'), id=submission_id)
    assignment = submission.assignment

    if submission.is_completed:
        messages.info(request, "This assignment has already been submitted.")
        return redirect('student_dashboard')

    end_time = None
    if assignment.duration and submission.started_at:
        end_time = submission.started_at + timedelta(minutes=assignment.duration)
        if timezone.now() > end_time:
            return render(request, 'assignment/assessment_due.html', {"assignment": assignment, "student": submission.student})

    questions_list = list(assignment.questions.all())
    if assignment.shuffle_questions:
        random.shuffle(questions_list)

    context = {
        'submission': submission, 'assignment': assignment, 'questions': questions_list,
        'student': submission.student, 'end_time_iso': end_time.isoformat() if end_time else None,
    }
    return render(request, 'assignment/take_assignment_form.html', context)


def _process_and_save_assignment_submission(request, submission_id):
    """Internal helper to process POST data for both regular and beacon submissions."""
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    if submission.is_completed:
        return submission, False

    assignment = submission.assignment
    answers = {}
    auto_grade = 0
    
    for question in assignment.questions.all():
        answer_key = f'answer_{question.id}'
        answer_value = request.POST.get(answer_key)
        answers[str(question.id)] = answer_value

        if question.question_type in ['SCQ', 'MCQ']:
            if str(answer_value).strip().lower() == str(question.correct_answer).strip().lower():
                auto_grade += 1
    
    submission.answers = answers
    submission.grade = Decimal(auto_grade) # Awaiting manual grading for essays
    submission.is_completed = True
    submission.submitted_at = timezone.now()
    submission.save()
    return submission, True


@login_required
def submit_assignment(request, submission_id):
    """STEP 3: Handles the final, intentional submission from the student."""
    if request.method != "POST":
        return HttpResponseNotAllowed(['POST'])
    
    submission, was_processed = _process_and_save_assignment_submission(request, submission_id)
    if was_processed:
        messages.success(request, f"Assignment '{submission.assignment.title}' submitted successfully.")
    else:
        messages.warning(request, "Assignment was already submitted.")
    
    return redirect('guardian_dashboard' if hasattr(request.user, 'guardian') else 'student_dashboard')


@csrf_exempt
def autosubmit_beacon_assignment(request, submission_id):
    """STEP 4: Handles background submissions from browser closure."""
    if request.method != 'POST':
        return HttpResponse(status=204)
        
    submission, was_processed = _process_and_save_assignment_submission(request, submission_id)
    if was_processed:
        submission.force_submitted_at = timezone.now()
        submission.save()
    return HttpResponse(status=204)


@login_required
def start_assessment(request, assessment_id):

    assessment = get_object_or_404(Assessment, id=assessment_id, is_approved=True)

    if assessment.is_due:
        messages.error(request, f"The deadline for '{assessment.title}' has passed.")
        return render(request, 'assessment/assessment_due.html', {"assessment": assessment})

    # Get the student object
    response = get_student_for_item(request, assessment, 'Assessment', 'start_assessment', 'assessment/select_student.html')
    if not isinstance(response, Student): 
        return response
    student = response
 
    # Get all previous attempts for this student and assessment
    previous_attempts = AssessmentSubmission.objects.filter(
        assessment=assessment,
        student=student
    ).order_by('-attempt_number')
    
    latest_attempt = previous_attempts.first()
    attempt_count = previous_attempts.count()

    # Find the next attempt number
    next_attempt_number = (latest_attempt.attempt_number + 1) if latest_attempt else 1

    # CHECK 1: Have they already used all their attempts?
    if latest_attempt and latest_attempt.is_completed and attempt_count >= 3:
        messages.error(request, "You have used all available attempts for this assessment.")
        return render(request, 'assessment/already_submitted.html', {
            "assessment": assessment, "student": student, "latest_attempt": latest_attempt
        })

    # CHECK 2: Look for a pre-existing record for the next attempt.
    submission = AssessmentSubmission.objects.filter(
        assessment=assessment,
        student=student,
        attempt_number=next_attempt_number
    ).first()
    
    if not submission:
        # Before creating, one final check: if the last attempt was NOT completed, they can't start a new one.
        if latest_attempt and not latest_attempt.is_completed:
             messages.warning(request, "You have an incomplete attempt. Please finish it or contact your teacher.")
             # Redirect them back to their incomplete attempt
             return redirect('take_assessment', submission_id=latest_attempt.id)

        # All checks passed. Create the new attempt record.
        submission = AssessmentSubmission.objects.create(
            assessment=assessment,
            student=student,
            attempt_number=next_attempt_number,
            ip_address=get_client_ip(request)
        )

    # --- Timer and Redirect Logic (remains the same) ---
    if not submission.started_at and assessment.duration:
        submission.started_at = timezone.now()
        submission.save()

    return redirect('take_assessment', submission_id=submission.id)


@login_required
def take_assessment(request, submission_id):
    """STEP 2: The main page where the student takes the timed assessment."""
    submission = get_object_or_404(AssessmentSubmission.objects.select_related('assessment', 'student__user'), id=submission_id)
    assessment = submission.assessment

    if submission.is_completed:
        messages.info(request, "This assessment has already been submitted.")
        return redirect('student_dashboard')

    end_time = None
    if assessment.duration and submission.started_at:
        end_time = submission.started_at + timedelta(minutes=assessment.duration)
        if timezone.now() > end_time:
            return render(request, 'assessment/assessment_due.html', {"assessment": assessment, "student": submission.student})

    questions_list = list(assessment.questions.all())
    if assessment.shuffle_questions:
        random.shuffle(questions_list)
    
    processed_questions = []
    for q in questions_list:
        options = q.options_list()
        if assessment.shuffle_questions and q.question_type in ['SCQ', 'MCQ']:
            random.shuffle(options)
        processed_questions.append({'question': q, 'shuffled_options': options})

    context = {
        'submission': submission, 'assessment': assessment, 'questions_data': processed_questions,
        'student': submission.student, 'end_time_iso': end_time.isoformat() if end_time else None,
    }
    return render(request, 'assessment/take_assessment_form.html', context)


def _process_and_save_assessment_submission(request, submission_id, force_submitted=False):
    """Internal helper to process POST data for both regular and beacon submissions."""
    submission = get_object_or_404(AssessmentSubmission, id=submission_id)
    if submission.is_completed:
        return submission, False

    assessment = submission.assessment
    answers = {}
    score = Decimal('0.0')
    requires_manual_review = False

    for question in assessment.questions.all():
        answer_key = f'answer_{question.id}'
        submitted_answer = None
        if question.question_type == 'MCQ':
            submitted_answer = request.POST.getlist(answer_key)
        else:
            submitted_answer = request.POST.get(answer_key)
        
        answers[str(question.id)] = submitted_answer

        if question.question_type == 'ES':
            requires_manual_review = True
        elif question.is_option_correct(submitted_answer):
            score += Decimal(question.points) # Use points from OnlineQuestion
            
    submission.answers = answers
    submission.score = score
    submission.requires_manual_review = requires_manual_review
    submission.is_graded = not requires_manual_review
    submission.is_completed = True
    submission.submitted_at = timezone.now()

    if force_submitted:
        submission.force_submitted_at = timezone.now()

    submission.save() # The signal will fire after this save
    return submission, True


@login_required
def submit_assessment(request, submission_id):
    """STEP 3: Handles the final, intentional submission."""
    if request.method != "POST":
        return HttpResponseNotAllowed(['POST'])
    
    submission, was_processed = _process_and_save_assessment_submission(request, submission_id)
    if was_processed:
        messages.success(request, f"Assessment '{submission.assessment.title}' submitted successfully.")
    else:
        messages.warning(request, "Assessment was already submitted.")
    
    return redirect('guardian_dashboard' if hasattr(request.user, 'guardian') else 'student_dashboard')


@csrf_exempt
def autosubmit_beacon_assessment(request, submission_id):
    """STEP 4: Handles background submissions from browser closure."""
    if request.method != 'POST':
        return HttpResponse(status=204)
        
    submission, was_processed = _process_and_save_assessment_submission(request, submission_id)
    if was_processed:
        submission.force_submitted_at = timezone.now()
        submission.save()
    return HttpResponse(status=204)


@login_required
def start_exam(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id, is_approved=True)

    if exam.is_due:
        messages.error(request, f"The deadline for '{exam.title}' has passed.")
        return render(request, 'exam/exam_due.html', {"exam": exam})

    response = get_student_for_item(request, exam, 'Exam', 'start_exam', 'exam/select_student.html')
    if not isinstance(response, Student): 
        return response
    student = response

    # --- 3-ATTEMPT RETAKE LOGIC ---
    previous_attempts = ExamSubmission.objects.filter(exam=exam, student=student).order_by('-attempt_number')
    latest_attempt = previous_attempts.first()
    attempt_count = previous_attempts.count()
    next_attempt_number = (latest_attempt.attempt_number + 1) if latest_attempt else 1

    if latest_attempt and latest_attempt.is_completed and attempt_count >= 3:
        messages.error(request, "You have used all available attempts for this exam.")
        return render(request, 'exam/already_submitted.html', {"exam": exam, "student": student, "latest_attempt": latest_attempt})

    submission = ExamSubmission.objects.filter(exam=exam, student=student, attempt_number=next_attempt_number).first()
    
    if not submission:
        if latest_attempt and not latest_attempt.is_completed:
             messages.warning(request, "You have an incomplete attempt. Please finish it or contact your teacher.")
             return redirect('take_exam', submission_id=latest_attempt.id)

        submission = ExamSubmission.objects.create(
            exam=exam, student=student, attempt_number=next_attempt_number, ip_address=get_client_ip(request)
        )

    # --- Timer and Redirect ---
    if not submission.started_at and exam.duration:
        submission.started_at = timezone.now()
        submission.save()

    return redirect('take_exam', submission_id=submission.id)


@login_required
def take_exam(request, submission_id):
    """STEP 2: The main page where the student takes the timed exam."""
    submission = get_object_or_404(ExamSubmission.objects.select_related('exam', 'student__user'), id=submission_id)
    exam = submission.exam

    if submission.is_completed:
        messages.info(request, "This exam has already been submitted.")
        return redirect('student_dashboard')

    end_time = None
    if exam.duration and submission.started_at:
        end_time = submission.started_at + timedelta(minutes=exam.duration)
        if timezone.now() > end_time:
            return render(request, 'exam/exam_due.html', {"exam": exam, "student": submission.student})

    questions_list = list(exam.questions.all())
    if exam.shuffle_questions:
        random.shuffle(questions_list)
    
    processed_questions = []
    for q in questions_list:
        options = q.options_list()
        if exam.shuffle_questions and q.question_type in ['SCQ', 'MCQ']:
            random.shuffle(options)
        processed_questions.append({'question': q, 'shuffled_options': options})

    context = {
        'submission': submission, 'exam': exam, 'questions_data': processed_questions,
        'student': submission.student, 'end_time_iso': end_time.isoformat() if end_time else None,
    }
    return render(request, 'exam/take_exam_form.html', context)


def _process_and_save_exam_submission(request, submission_id, force_submitted=False):
    """Internal helper to process POST data for both regular and beacon submissions."""
    submission = get_object_or_404(ExamSubmission, id=submission_id)
    if submission.is_completed:
        return submission, False

    exam = submission.exam
    answers = {}
    score = Decimal('0.0')
    requires_manual_review = False

    for question in exam.questions.all():
        answer_key = f'answer_{question.id}'
        submitted_answer = None
        if question.question_type == 'MCQ':
            submitted_answer = request.POST.getlist(answer_key)
        else:
            submitted_answer = request.POST.get(answer_key)
        
        answers[str(question.id)] = submitted_answer

        if question.question_type == 'ES':
            requires_manual_review = True
        elif question.is_option_correct(submitted_answer):
            score += Decimal(question.points) # Use points from OnlineQuestion
            
    submission.answers = answers
    submission.score = score
    submission.requires_manual_review = requires_manual_review
    submission.is_graded = not requires_manual_review
    submission.is_completed = True
    submission.submitted_at = timezone.now()

    if force_submitted:
        submission.force_submitted_at = timezone.now()
    
    submission.save() # The signal will fire after this save
    return submission, True


@login_required
def submit_exam(request, submission_id):
    """STEP 3: Handles the final, intentional submission."""
    if request.method != "POST":
        return HttpResponseNotAllowed(['POST'])
    
    submission, was_processed = _process_and_save_exam_submission(request, submission_id)
    if was_processed:
        messages.success(request, f"Exam '{submission.exam.title}' submitted successfully.")
    else:
        messages.warning(request, "Exam was already submitted.")
    
    return redirect('guardian_dashboard' if hasattr(request.user, 'guardian') else 'student_dashboard')


@csrf_exempt
def autosubmit_beacon_exam(request, submission_id):
    """STEP 4: Handles background submissions from browser closure."""
    if request.method != 'POST':
        return HttpResponse(status=204)
        
    submission, was_processed = _process_and_save_exam_submission(request, submission_id)
    if was_processed:
        submission.force_submitted_at = timezone.now()
        submission.save()
    return HttpResponse(status=204)


def _get_student_for_result_view(request, parent_item, item_type_verbose, result_url_name, submit_url_name_for_select_page):

    user = request.user
    student_for_view = None
    render_select_student = False
    select_student_context = {}

    parent_item_class_assigned = parent_item.class_assigned

    if hasattr(user, 'guardian'): 
        guardian = user.guardian
        
        # Get all students of this guardian in the item's class
        students_qs = Student.objects.filter(
            student_guardian=guardian,
            current_class=parent_item_class_assigned
        )

        if not students_qs.exists():
            messages.error(request, f"No students associated with your guardian profile are enrolled in the class for this {item_type_verbose.lower()}.")
            return None, False, {} 

        student_id_from_get = request.GET.get('student_id')

        if student_id_from_get and student_id_from_get.isdigit():
            try:
                student_for_view = students_qs.get(user_id=int(student_id_from_get))
            except Student.DoesNotExist:
                messages.error(request, "Selected student not found or not eligible for this item.")
                return None, True, {'students': students_qs, 'item': parent_item, 'item_type_verbose': item_type_verbose, 'target_url_name': result_url_name}
        elif students_qs.count() == 1:
            student_for_view = students_qs.first()
        else: 
            render_select_student = True
            select_student_context = {
                'students': students_qs,
                'item': parent_item,
                'item_type_verbose': item_type_verbose,
                'target_url_name': result_url_name, 
                'page_title_action': f"View Result for {item_type_verbose}" 
            }
                
    elif hasattr(user, 'student'): 
        student_for_view = user.student
        if student_for_view.current_class != parent_item_class_assigned:
            messages.error(request, f"You are not enrolled in the class for this {item_type_verbose.lower()}.")
            return None, False, {}
    else:
        messages.error(request, "You are not authorized to view this result.")
        return None, False, {}
    
    return student_for_view, render_select_student, select_student_context


def view_exam_result(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    student, render_select_page, select_context = _get_student_for_result_view(
        request, exam, 'Exam', 'view_exam_result', 'submit_exam'
    )

    if render_select_page:
        return render(request, 'results/select_student.html', select_context) 
    if not student:
        return redirect('guardian_dashboard' if hasattr(request.user, 'guardian') else 'student_dashboard')

    try:
        submission = ExamSubmission.objects.get(exam=exam, student=student)
    except ExamSubmission.DoesNotExist:
        messages.warning(request, f"No submission found for '{exam.title}' for {student.user.get_full_name()}.")
        return redirect('view_exam', exam_id=exam.id)

    questions_data_for_template = []
    for question in exam.questions.all().order_by('id'):
        student_answer_raw = submission.answers.get(str(question.id)) # Raw stored answer
        
        # Determine if student's answer was correct (for SCQ/MCQ)
        is_overall_correct_display = None
        if question.question_type != 'ES':
            is_overall_correct_display = question.is_option_correct(student_answer_raw)

        # Prepare options with status for display
        options_with_status = []
        if question.question_type in ['SCQ', 'MCQ']:
            all_available_options = question.options_list() # List of all options for this question
            
            # Get the list of correct answers for this question
            correct_answers_for_question_set = set()
            if question.correct_answer:
                if ',' in question.correct_answer: # Assuming MCQ correct answers are comma-separated
                    correct_answers_for_question_set = set(opt.strip().lower() for opt in question.correct_answer.split(','))
                else: # SCQ or MCQ with single correct answer string
                    correct_answers_for_question_set.add(str(question.correct_answer).strip().lower())

            # Get the student's choices for this question (ensure it's a list for MCQs)
            student_choices_for_question_list = []
            if question.question_type == 'MCQ' and isinstance(student_answer_raw, list):
                student_choices_for_question_list = [str(sa).strip().lower() for sa in student_answer_raw]
            elif student_answer_raw is not None: # SCQ or Essay (treat as single choice for this list)
                student_choices_for_question_list = [str(student_answer_raw).strip().lower()]
            
            for opt_text in all_available_options:
                opt_text_lower = str(opt_text).strip().lower()
                options_with_status.append({
                    'text': opt_text,
                    'is_correct': opt_text_lower in correct_answers_for_question_set,
                    'is_student_choice': opt_text_lower in student_choices_for_question_list,
                })
        
        questions_data_for_template.append({
            'question_instance': question, 
            'question_text': question.question_text,
            'question_type': question.question_type,
            'options_detailed': options_with_status, 
            'student_answer_display': student_answer_raw, 
            'correct_answer_model': question.correct_answer, 
            'is_correct_display': is_overall_correct_display, 
        })

    context = {
        'item': exam,
        'submission': submission,
        'questions_with_answers': questions_data_for_template,
        'item_type_verbose': 'Exam',
        'student_viewing': student,
    }
    return render(request, 'results/view_result_detail.html', context)


@login_required
def view_assignment_result(request, submission_id):
    submission = get_object_or_404(AssignmentSubmission.objects.select_related(
        'assignment__subject', 'student__user'
    ), id=submission_id)

    # Authorization check
    is_student = request.user == submission.student.user
    is_guardian = hasattr(request.user, 'guardian') and submission.student in request.user.guardian.students.all()

    if not (is_student or is_guardian):
        messages.error(request, "You are not authorized to view these results.")
        return redirect('home')

    assignment = submission.assignment
    questions = assignment.questions.all()
    
    student_answers = submission.answers
    if isinstance(student_answers, str):
        try:
            student_answers = json.loads(student_answers)
        except json.JSONDecodeError:
            student_answers = {} # Default to empty dict if the string is invalid

    # Now, `student_answers` is guaranteed to be a dictionary
    
    # Prepare data for the template
    results_data = []
    for question in questions:
        student_answer = student_answers.get(str(question.id), "Not Answered")
        is_correct = (str(student_answer).strip().lower() == str(question.correct_answer).strip().lower())
        
        results_data.append({
            'question_text': question.question_text,
            'student_answer': student_answer,
            'correct_answer': question.correct_answer,
            'is_correct': is_correct,
        })

    context = {
        'submission': submission,
        'assignment': assignment,
        'results_data': results_data, # Pass the processed data
    }
    return render(request, 'assignment/view_assignment_result.html', context)


@login_required
def view_assessment_result(request, submission_id):
    """
    This view correctly uses the unique submission_id to get a single object.
    """
    # --- THE FIX: Use get_object_or_404 with the unique submission_id ---
    submission = get_object_or_404(AssessmentSubmission.objects.select_related(
        'assessment__subject', 'student__user'
    ), id=submission_id)

    # Authorization check
    is_student = request.user == submission.student.user
    is_guardian = hasattr(request.user, 'guardian') and submission.student in request.user.guardian.students.all()

    if not (is_student or is_guardian):
        messages.error(request, "You are not authorized to view these results.")
        return redirect('home')

    assessment = submission.assessment
    questions = assessment.questions.all()
    
    # Defensively handle the 'answers' field
    student_answers = submission.answers
    if isinstance(student_answers, str):
        try: student_answers = json.loads(student_answers)
        except json.JSONDecodeError: student_answers = {}

    # Prepare data for the template (your logic here is good)
    results_data = []
    for question in questions:
        student_answer = student_answers.get(str(question.id), "Not Answered")
        is_correct = question.is_option_correct(student_answer)
        results_data.append({ ... })

    context = {
        'submission': submission,
        'assessment': assessment,
        'results_data': results_data,
    }
    return render(request, 'assessment/view_assessment_result.html', context)


@login_required
def view_exam_result(request, submission_id):
    # --- THE FIX: Look up the ExamSubmission by its ID ---
    submission = get_object_or_404(ExamSubmission.objects.select_related(
        'exam__subject', 'student__user'
    ), id=submission_id)

    # Authorization check
    is_student = request.user == submission.student.user
    is_guardian = hasattr(request.user, 'guardian') and submission.student in request.user.guardian.students.all()

    if not (is_student or is_guardian):
        messages.error(request, "You are not authorized to view these results.")
        return redirect('home')

    exam = submission.exam
    questions = exam.questions.all()
    
    # Defensively handle the 'answers' field
    student_answers = submission.answers
    if isinstance(student_answers, str):
        try: student_answers = json.loads(student_answers)
        except json.JSONDecodeError: student_answers = {}

    # Prepare data for the template
    results_data = []
    for question in questions:
        student_answer = student_answers.get(str(question.id), "Not Answered")
        # Use the robust is_option_correct method from the OnlineQuestion model
        is_correct = question.is_option_correct(student_answer)
        
        results_data.append({
            'question_text': question.question_text,
            'student_answer': student_answer,
            'correct_answer': question.correct_answer,
            'is_correct': is_correct,
            'options': question.options_list(), # Pass options for display
            'question_type': question.question_type,
        })

    context = {
        'submission': submission,
        'exam': exam,
        'results_data': results_data,
    }
    return render(request, 'exam/view_exam_result.html', context)


def export_guardians(request):
    # Implement export logic here
    pass

def guardian_reports(request):
    # Implement report generation logic here
    pass


# Helper function to build absolute URLs for static/media files
def build_absolute_uri(request, path):
    """Builds an absolute URI for static or media files."""
    if path.startswith('http'): # Already absolute
        return path
    # This assumes default /static/ and /media/ URLs
    if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
        return request.build_absolute_uri(path)
    # Fallback for potentially relative paths (less ideal)
    return request.build_absolute_uri(settings.STATIC_URL + path.lstrip('/'))


@login_required
def view_termly_result(request, student_id, term_id):
    """
    Displays a student's result for a specific term and allows PDF download.
    """
    try:
        # Use student_id (which is user_id/pk for Student model)
        student = get_object_or_404(Student.objects.select_related('user', 'current_class', 'cumulative_record'), pk=student_id)
        term = get_object_or_404(Term.objects.select_related('session'), id=term_id)
        session = term.session
        class_obj = student.current_class

        # Get or create the result object. get_or_create is safer.
        result, _ = Result.objects.get_or_create(student=student, term=term)

    except Http404:
        messages.error(request, "The requested result data could not be found.")
        return redirect('home') # Or a more appropriate dashboard
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {e}")
        return redirect('home')

    # --- Permissions & Financial Checks ---
    user = request.user
    is_guardian_of_student = hasattr(user, 'guardian') and student in user.guardian.students.all()
    is_self = (student.user == user)
    
    if not (user.is_superuser or is_self or is_guardian_of_student):
        return HttpResponseForbidden("You are not authorized to view this result.")

    financial_record = FinancialRecord.objects.filter(student=student, term=term).first()
    can_view_result = (not financial_record) or (financial_record and financial_record.can_access_results) 
    if not (user.is_superuser or hasattr(user, 'teacher')) and not can_view_result:
        return render(request, 'student/result_access_denied.html', {'student': student, 'term': term})
        
    # --- Just-in-Time Calculation (Fail-safe) ---
    # If summary fields are empty, calculate and save them now.
    if result.term_gpa is None or result.total_score is None or result.performance_change is None:
        print(f"INFO: Calculating summary on-the-fly for result ID {result.id}...")
        result.calculate_term_summary()
        result.refresh_from_db() # Reload the instance to get the newly saved values

    # --- Fetch and Prepare ALL Data for Template ---
    
    # Absolute URLs for PDF rendering
    profile_image_url = build_absolute_uri(request, student.profile_image.url) if student.profile_image else None
    school_logo_url = build_absolute_uri(request, 'images/logo.jpg')
    signature_url = build_absolute_uri(request, 'images/signature.png')

    # Attendance Data (using the stored value on the result if available, otherwise calculate)
    if result.attendance_percentage is not None:
        attendance_data = {'attendance_percentage': result.attendance_percentage}
    else:
        total_days = Attendance.objects.filter(student=student, term=term).count() 
        present_days = Attendance.objects.filter(student=student, term=term, is_present=True).count()
        attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
        attendance_data = {
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': total_days - present_days,
            'attendance_percentage': round(attendance_percentage, 1), 
        }
    
    # Subject Results for the table
    subject_results_list = result.subject_results.select_related('subject').order_by('subject__name')

    # Cumulative GPA (ensure the record is up-to-date)
    cumulative_record = student.cumulative_record
    cumulative_record.update_cumulative_gpa() 
    cumulative_gpa = cumulative_record.cumulative_gpa
    
    # Handle first-term-ever case for cumulative GPA display
    if Result.objects.filter(student=student).count() == 1:
        cumulative_gpa = result.term_gpa

    # Chart Data
    chart_data = []
    for sr in subject_results_list:
        class_average = SubjectResult.get_class_average(sr.subject, term, class_obj) 
        total_score_val = sr.total_score() 
        chart_data.append({
            'subject': sr.subject.name,
            'total_score': float(total_score_val) if total_score_val is not None else 0.0,
            'class_average': float(class_average) if class_average is not None else 0.0
        })

    # --- Final Context Dictionary ---
    context = {
        'student': student,
        'result': result, # Contains term_gpa, performance_change, remarks, skills
        'term': term,
        'session': session, 
        'class_obj': class_obj,
        'subject_results': subject_results_list, 
        'cumulative_gpa': cumulative_gpa,
        'chart_data_json': json.dumps(chart_data), 
        'attendance_data': attendance_data,
        'teacher_comment': result.teacher_remarks,
        'principal_comment': result.principal_remarks,
        'profile_image_url': profile_image_url,
        'school_logo_url': school_logo_url,
        'signature_url': signature_url,
        'is_pdf_render': False, 
    }

    # --- PDF Download Handling ---
    if "download" in request.GET and request.GET["download"] == "pdf":
        if HTML is None:
            return HttpResponse("PDF generation library (WeasyPrint) is not installed or configured correctly.", status=500) 

        context['is_pdf_render'] = True 

        # Render HTML to string using the SAME template
        html_string = render_to_string('guardian/view_result.html', context)

        try:
            # Assume STATICFILES_DIRS contains at least one path
            base_static_dir = pathlib.Path(settings.STATICFILES_DIRS[0])
            css_path = base_static_dir / 'css' / 'result_styles.css' # Use / operator with Path objects

            # Check if the file actually exists before trying to load it
            if not css_path.is_file():
                 raise FileNotFoundError(f"Result CSS file not found at calculated path: {css_path}")

            font_config = FontConfiguration()
            css = CSS(filename=css_path, font_config=font_config)

        except IndexError:
            return HttpResponse("Error generating PDF: Static file configuration missing.", status=500)
        except FileNotFoundError as e:
             return HttpResponse("Error generating PDF: Required styles missing.", status=500)
        except Exception as e:
             return HttpResponse("Error generating PDF: Could not load styles.", status=500)


        try:
            # Create HTML object
            html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
            # Generate PDF in memory
            pdf_file = io.BytesIO()
            html.write_pdf(
                target=pdf_file,
                stylesheets=[css], 
                font_config=font_config # Needed if using CSS object method
            )
            pdf_file.seek(0) # Rewind the buffer

        except Exception as e:
            # Catch WeasyPrint errors
            return HttpResponse(f"An error occurred during PDF generation: {e}", status=500)

        # Create HTTP response with PDF
        response = HttpResponse(pdf_file, content_type='application/pdf')
        # Sanitize filename
        student_name_safe = "".join(c if c.isalnum() else "_" for c in student.user.get_full_name())
        term_name_safe = "".join(c if c.isalnum() else "_" for c in term.name)
        response['Content-Disposition'] = f'attachment; filename="{student_name_safe}_result_{term_name_safe}.pdf"'

        return response

    return render(request, 'guardian/view_termly_result.html', context)


@login_required
def view_sessional_result(request, student_id, session_id):
    """
    Displays a student's sessional result, performance change, and cumulative GPA.
    This view is designed to be robust, efficient, and clear.
    """
    # 1. ===== Fetch Core Objects and Perform Checks =====
    try:
        student = get_object_or_404(Student.objects.select_related('user', 'current_class', 'cumulative_record'), pk=student_id)
        session = get_object_or_404(Session, id=session_id)
    except Http404:
        messages.error(request, "The requested student or session could not be found.")
        return redirect('home')

    # Permissions Check
    user = request.user
    if not (user.is_superuser or student.user == user or (hasattr(user, 'guardian') and student in user.guardian.students.all())):
        return HttpResponseForbidden("You are not authorized to view this result.")

    # Financial Access Check
    terms_in_session = Term.objects.filter(session=session).order_by('start_date')
    can_view_result = True
    if not (request.user.is_superuser or hasattr(request.user, 'teacher')):
        # Get total fees and payments for the entire session
        sessional_financials = FinancialRecord.objects.filter(
            student=student, term__in=terms_in_session
        )
        
        is_blocked = False
        for record in sessional_financials:
            if not record.can_access_results:
                is_blocked = True
                break 
        
        if is_blocked:
            can_view_result = False
    

    # 2. ===== Calculate/Fetch Sessional & Cumulative Data =====
    sessional_result, created = SessionalResult.objects.get_or_create(student=student, session=session)
    if created or sessional_result.sessional_gpa is None:
        sessional_result.calculate_sessional_summary(save=True)
        sessional_result.refresh_from_db()

    student.cumulative_record.update_cumulative_gpa(save=True)
    cumulative_gpa = student.cumulative_record.cumulative_gpa

    # 3. ===== Prepare Data for the Template =====

    # Get subjects the student actually took in this session
    subjects_in_session = Subject.objects.filter(
        subjectresult__result__student=student,
        subjectresult__result__term__in=terms_in_session
    ).distinct().order_by('name')

    # Sessional Attendance
    sessional_attendance = Attendance.objects.filter(student=student, term__in=terms_in_session).aggregate(
        total_days=Count('id'), present_days=Count('id', filter=Q(is_present=True))
    )
    sessional_total_days = sessional_attendance.get('total_days', 0)
    sessional_present_days = sessional_attendance.get('present_days', 0)
    
    # Broadsheet/Table and Chart Data
    subject_rows = []
    chart_data = []
    class_obj = student.current_class

    all_class_sessional_results = SessionalResult.objects.filter(
        session=session,
        student__current_class=class_obj,
    )
    
    # Step 2: Loop through subjects and calculate averages in Python.
    for subject in subjects_in_session:
        subject_id_str = str(subject.id)
        
        # Get the current student's data
        subject_summary = sessional_result.subject_summary_json.get(subject_id_str, {})
        student_sessional_avg = subject_summary.get('sessional_average')
        
        subject_rows.append({
            'subject_name': subject.name,
            'term_scores': [subject_summary.get('term_scores', {}).get(f'term_{term.id}_score') for term in terms_in_session],
            'sessional_average': student_sessional_avg
        })
        
        # Calculate Class Average for this subject in Python
        class_scores_for_subject = []
        for class_member_result in all_class_sessional_results:
            # Safely extract the sessional average for this subject from each student's JSON
            member_subject_summary = class_member_result.subject_summary_json.get(subject_id_str, {})
            member_avg_score = member_subject_summary.get('sessional_average')

            # CRITICAL: Safely convert to a number, ignoring bad data like "none" or None
            if member_avg_score is not None:
                try:
                    class_scores_for_subject.append(Decimal(member_avg_score))
                except (InvalidOperation, TypeError):
                    # This will skip any value that is not a valid number (e.g., "none")
                    continue
        
        # Calculate the final class average
        class_sessional_avg = (sum(class_scores_for_subject) / len(class_scores_for_subject)) if class_scores_for_subject else None

        chart_data.append({
            'subject': subject.name,
            'student_average': float(student_sessional_avg) if student_sessional_avg is not None else 0.0,
            'class_average': float(class_sessional_avg) if class_sessional_avg is not None else 0.0
        })

    # 4. ===== Final Context =====
    context = {
        'student': student,
        'session': session,
        'terms_in_session': terms_in_session,
        'sessional_result': sessional_result,
        'cumulative_gpa': cumulative_gpa,
        'subject_rows': subject_rows,
        'sessional_attendance_data': {
            'total_days': sessional_total_days,
            'present_days': sessional_present_days,
            'absent_days': sessional_total_days - sessional_present_days,
            'percentage': round((sessional_present_days / sessional_total_days * 100), 1) if sessional_total_days > 0 else 0
        },
        'chart_data_json': json.dumps(chart_data),
        'is_published': sessional_result.is_published,
        'is_pdf_render': False, # Flag for PDF rendering
        'school_logo_url': build_absolute_uri(request, 'images/logo.jpg'), # Example
        'signature_url': build_absolute_uri(request, 'images/signature.png'), # Example
    }

    # --- PDF Download Handling ---
    if "download" in request.GET and request.GET["download"] == "pdf":
        if HTML is None:
            return HttpResponse("PDF generation library is not available.", status=501)
        
        context['is_pdf_render'] = True
        html_string = render_to_string('student/view_sessional_result.html', context)
        try:
            css_path = settings.STATICFILES_DIRS[0] / 'css' / 'result_styles.css'
            html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
            pdf_file = html.write_pdf(stylesheets=[CSS(filename=css_path)])
            
            response = HttpResponse(pdf_file, content_type='application/pdf')
            student_name_safe = "".join(c for c in student.user.get_full_name() if c.isalnum() or c in " _-").rstrip()
            session_name_safe = "".join(c for c in session.name if c.isalnum() or c in " _-").rstrip()
            response['Content-Disposition'] = f'attachment; filename="{student_name_safe}_sessional_result_{session_name_safe}.pdf"'
            return response
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return HttpResponse(f"An error occurred during PDF generation: {e}", status=500)

    return render(request, 'guardian/view_sessional_result.html', context)


@login_required
def message_inbox(request):
    """
    A central, generic inbox for the logged-in user. Shows received message threads.
    """
    user = request.user

    conversations = Message.objects.filter(
        (Q(recipient=user) | Q(sender=user)),
        parent_message__isnull=True
    ).select_related('sender', 'recipient', 'student_context__user').prefetch_related('replies').distinct().order_by('-updated_at')

    Message.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    unread_count = conversations.filter(recipient=user, is_read=False).count()
    
    context = {
        'conversations': conversations,
        'unread_count': unread_count, 
        'page_title': "My Inbox"
    }

    return render(request, 'messaging/inbox.html', context)


@login_required
def compose_message(request):
    """
    A generic view for composing a message.
    """
    sender = request.user
    
    # --- Determine the queryset of possible recipients based on the sender's role ---
    recipient_qs = CustomUser.objects.none() 
    student_context_qs = Student.objects.none() 

    if sender.role == 'student':
        # Students can message their teachers and admins
        student = getattr(sender, 'student', None) 
        if student:
            teacher_ids = Teacher.objects.filter(
                Q(teacherassignment__class_assigned=student.current_class) |
                Q(subjectassignment__class_assigned=student.current_class)
            ).values_list('user_id', flat=True)
            recipient_qs = CustomUser.objects.filter(Q(id__in=teacher_ids) | Q(role='admin')).exclude(pk=sender.pk).distinct()
            student_context_qs = Student.objects.filter(pk=student.pk)

    elif sender.role == 'teacher':
        # Teachers can message guardians of their students, colleagues, and admins
        teacher = getattr(sender, 'teacher', None)
        if teacher:
            assigned_classes = teacher.assigned_classes()
            students_taught = Student.objects.filter(current_class__in=assigned_classes, status='active')
            guardian_ids = students_taught.filter(student_guardian__isnull=False).values_list('student_guardian__user_id', flat=True)
            
            colleague_ids = Teacher.objects.exclude(pk=teacher.pk).values_list('user_id', flat=True)
            
            recipient_qs = CustomUser.objects.filter(
                Q(guardian__pk__in=guardian_ids) |
                Q(id__in=colleague_ids) |
                Q(role='admin')
            ).distinct()
            student_context_qs = students_taught

    elif sender.role == 'guardian':
        # Guardians can message teachers of their wards and admins
        guardian = getattr(sender, 'guardian', None)
        if guardian:
            wards = guardian.students.all()
            teacher_ids = Teacher.objects.filter(
                Q(teacherassignment__class_assigned__in=wards.values_list('current_class', flat=True)) |
                Q(subjectassignment__class_assigned__in=wards.values_list('current_class', flat=True))
            ).values_list('user_id', flat=True)
            recipient_qs = CustomUser.objects.filter(Q(id__in=teacher_ids) | Q(role='admin')).distinct()
            student_context_qs = wards

    elif sender.role == 'admin':
        # Admins can message anyone
        recipient_qs = CustomUser.objects.all().exclude(pk=sender.pk)
        student_context_qs = Student.objects.filter(status='active')
    
    # --- Initialize variables for context ---
    recipient_preselected = None
    student_context = None
    initial_form_data = {}

    # --- Check for pre-selected data from GET parameters ---
    recipient_id = request.GET.get('recipient_id')
    student_context_id = request.GET.get('student_context_id')

    if recipient_id:
        try:
            # Fetch the pre-selected recipient object to display their name
            recipient_preselected = recipient_qs.get(pk=recipient_id)
            initial_form_data['recipient'] = recipient_preselected
        except CustomUser.DoesNotExist:
            messages.error(request, "The specified recipient is invalid or you are not allowed to message them.")
            return redirect('message_inbox')
    
    if student_context_id:
        try:
            student_context = student_context_qs.get(pk=student_context_id)
            initial_form_data['student_context'] = student_context
        except Student.DoesNotExist:
            pass

    # --- Handle Form Submission ---
    if request.method == 'POST':
        form = MessageForm(request.POST, recipient_queryset=recipient_qs, student_queryset=student_context_qs)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = sender
            message.save()
            messages.success(request, "Message sent successfully!")
            return redirect('message_inbox')
    else: # GET request
        form = MessageForm(initial=initial_form_data, recipient_queryset=recipient_qs, student_queryset=student_context_qs)
    
    context = {
        'form': form,
        'recipient_preselected': recipient_preselected, 
        'student_context': student_context, 
        'page_title': "Compose Message"
    }
    return render(request, 'messaging/compose_message.html', context)


@login_required
def message_thread(request, thread_id):
    # Fetch the parent message of the thread
    parent_message = get_object_or_404(Message, pk=thread_id, parent_message__isnull=True)

    # Authorization check: user must be the sender or recipient
    if request.user not in [parent_message.sender, parent_message.recipient]:
        raise Http404

    # Mark all messages in this thread as read by the current user
    Message.objects.filter(
        Q(pk=thread_id) | Q(parent_message_id=thread_id),
        recipient=request.user, is_read=False
    ).update(is_read=True)
    
    thread_messages = parent_message.replies.all().order_by('sent_at')

    # Setup form for a new reply
    reply_recipient = parent_message.sender if request.user == parent_message.recipient else parent_message.recipient
    
    if request.method == 'POST':
        reply_form = ReplyForm(request.POST)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.sender = request.user
            reply.recipient = reply_recipient
            reply.parent_message = parent_message
            if parent_message.student_context: # Carry over the student context
                reply.student_context = parent_message.student_context
            reply.save()
            messages.success(request, "Reply sent.")
            return redirect('message_thread', thread_id=thread_id)
    else:
        reply_form = MessageForm(initial={'title': f"Re: {parent_message.title}"})

    context = {
        'parent_message': parent_message,
        'thread_messages': thread_messages,
        'reply_form': reply_form,
        'reply_recipient': reply_recipient,
    }
    return render(request, 'messaging/message_thread.html', context)



