# views.py

import io 
import json
import pathlib
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.template.loader import render_to_string
from django.http import HttpResponse, Http404
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q
from playwright.sync_api import sync_playwright
from .forms import GuardianRegistrationForm
from core.models import Guardian, Term, Session, FinancialRecord, Student, Result, Subject, SubjectResult, Attendance
from core.models import Assignment, Assessment, Exam, AssessmentSubmission, ExamSubmission, AcademicAlert
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

@login_required
def submit_assignment(request, assignment_id):
    # Get the assignment or return a 404 if not found
    assignment = get_object_or_404(Assignment, id=assignment_id)

    # Determine the logged-in user's type
    if hasattr(request.user, 'guardian'):
        guardian = request.user.guardian

        # Filter students by the guardian and the assignment's class
        students = Student.objects.filter(
            student_guardian=guardian,
            current_class=assignment.class_assigned
        )

        if not students.exists():
            messages.error(request, "No students associated with this guardian are enrolled in the assignment's class.")
            return redirect('guardian_dashboard')

        # Check if a specific student is selected
        student_id = request.GET.get('student_id')
        if student_id:
            student = get_object_or_404(students, id=student_id)
        elif students.count() == 1:
            student = students.first()
        else:
            # Render a selection page if multiple students match
            return render(request, 'assignment/select_student.html', {
                'students': students,
                'item': assignment, 
                'item_type_verbose': 'Assignment', 
                'submit_url_name': 'submit_assignment'
            })

    else:
        # Handle student users submitting their own assignment
        student = get_object_or_404(
            Student,
            user=request.user,
            current_class=assignment.class_assigned
        )

    # Handle form submission
    if request.method == 'POST':
        answers = {}
        
        # Collect the answers for each question
        for question in assignment.questions.all():
            answer_key = f'answers[{question.id}]'
            answer_value = request.POST.get(answer_key)

            # If the answer exists for this question, store it
            if answer_value:
                # For MCQ/SCQ, answers will be stored as the selected option
                answers[question.id] = answer_value
            else:
                # For essay questions, we might want to store the plain text response
                if question.question_type == 'ES':
                    essay_answer = request.POST.get(f'answers_essay[{question.id}]')
                    if essay_answer:
                        answers[question.id] = essay_answer

        # If answers are valid, save the submission
        if answers:
            submission = AssignmentSubmission.objects.create(
                student=student,
                assignment=assignment,
                answers=json.dumps(answers),  # Save answers as JSON
                is_completed=True,
            )
            messages.success(request, "Your assignment has been successfully submitted!")
            return redirect('guardian_dashboard' if hasattr(request.user, 'guardian') else 'student_dashboard')

        messages.error(request, "Please answer all questions before submitting.")
        return redirect('submit_assignment', assignment_id=assignment_id)
            
    else:
        form = AssignmentSubmissionForm()

    # Render the form for assignment submission
    return render(request, 'assignment/submit_assignment.html', {
        'assignment': assignment,
        'form': form,
        'student': student,
    })


@login_required
def submit_assessment(request, assessment_id):

    assessment = get_object_or_404(Assessment, id=assessment_id)
    user = request.user
    student = None 

    if hasattr(user, 'guardian'): 
        guardian = user.guardian

        students_qs = Student.objects.filter(
            student_guardian=guardian,
            current_class=assessment.class_assigned
        )

        if not students_qs.exists():
            messages.error(request, "No students associated with this guardian are enrolled in this assessment's class.")
            return redirect('guardian_dashboard')

        student_id_from_get = request.GET.get('student_id')

        if student_id_from_get:
            try:
                student = students_qs.get(user__id=student_id_from_get) 
            except Student.DoesNotExist:
                messages.error(request, "Selected student not found or not eligible for this guardian/class.")
                return redirect('guardian_dashboard') 
        elif students_qs.count() == 1:
            student = students_qs.first()
        else:
            return render(request, 'assessment/select_student.html', {
                'students': students_qs,
                'item': assessment,
                'item_type_verbose': 'Assessment',
                'submit_url_name': 'submit_assessment'
            })

    elif hasattr(user, 'student'): 
        try:
            student = user.student
            if student.current_class != assessment.class_assigned:
                 messages.error(request, "You are not enrolled in the class for this assessment.")
                 return redirect('student_dashboard')
        except Student.DoesNotExist: 
            messages.error(request, "Your student profile was not found.")
            return redirect('student_dashboard')
    else:
        messages.error(request, "You are not authorized to submit this assessment (not a guardian or student).")
        return redirect('home')

    if not student: 
        messages.error(request, "Could not determine the student for this submission. Please try again or contact support.")
        return redirect('guardian_dashboard' if hasattr(user, 'guardian_profile') else 'student_dashboard' if hasattr(user, 'student_profile') else 'home')

    if assessment.is_due: 
        return render(request, 'assessment/assessment_due.html', {"assessment": assessment, "student": student})
    
    if AssessmentSubmission.objects.filter(assessment=assessment, student=student).exists():
        return render(request, 'assessment/already_submitted.html', {"assessment": assessment, "student": student})

    # Handle POST (Submission Logic)
    if request.method == "POST":

        answers = {}
        score = 0
        requires_manual_review = False

        for question in assessment.questions.all().order_by('id'):
            submitted_answer_values = []
            if question.question_type == 'MCQ':
                submitted_answer_values = request.POST.getlist(f'answer_{question.id}')
                if question.is_option_correct(submitted_answer_values):
                    score += 1
            else: 
                single_answer = request.POST.get(f'answer_{question.id}')
                if single_answer is not None:
                    submitted_answer_values.append(single_answer)
            
            answers[str(question.id)] = submitted_answer_values[0] if len(submitted_answer_values) == 1 and question.question_type != 'MCQ' else submitted_answer_values

            if question.question_type == 'SCQ':
                if submitted_answer_values and question.is_option_correct(submitted_answer_values[0]):
                    score += 1 
            elif question.question_type == 'ES':
                requires_manual_review = True
        
        submission = AssessmentSubmission.objects.create(
            assessment=assessment, student=student, answers=answers,
            score=score if not requires_manual_review else None,
            is_graded=not requires_manual_review, requires_manual_review=requires_manual_review
        )
        messages.success(request, f"Assessment '{assessment.title}' submitted successfully for {student.user.get_full_name()}.")
        return redirect('student_dashboard' if hasattr(user, 'student_dashboard') else 'guardian_dashboard')

    # Render Submission Form (GET Request)
    return render(request, 'assessment/submit_assessment.html', {
        'assessment': assessment,
        'questions': assessment.questions.all().order_by('id'),
        'student': student,
    })


@login_required
def submit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    user = request.user

    # Determine the logged-in user's type
    if hasattr(request.user, 'guardian'):
        guardian = request.user.guardian

        # Filter students by the guardian and the assignment's class
        students = Student.objects.filter(
            student_guardian=guardian,
            current_class=exam.class_assigned
        )

        if not students.exists():
            messages.error(request, "No students associated with this guardian are enrolled in the assignment's class.")
            return redirect('guardian_dashboard')

        # Check if a specific student is selected
        student_id = request.GET.get('student_id')
        if student_id:
            student = get_object_or_404(students, user_id=student_id)
        elif students.count() == 1:
            student = students.first()
        else:
            # Render a selection page if multiple students match
            return render(request, 'exam/select_student.html', {
                'students': students,
                'item': exam, 
                'item_type_verbose': 'Exam', 
                'submit_url_name': 'submit_exam'
            })

    else:
        # Handle student users submitting their own assignment
        student = get_object_or_404(
            Student,
            user=request.user,
            current_class=exam.class_assigned
        )

    # Prevent multiple submissions and overdue submissions
    if exam.is_due:
        return render(request, 'exam/exam_due.html', {"exam": exam})
    
    if ExamSubmission.objects.filter(exam=exam, student=student).exists():
        return render(request, 'exam/already_submitted.html')

    # Handle POST submission
    if request.method == "POST":
        answers = {}
        score = 0
        requires_manual_review = False

        for question in exam.questions.all():
            answer = request.POST.get(f'answer_{question.id}')
            answers[str(question.id)] = answer

            # Auto-grade SCQ/MCQ
            if question.question_type in ['SCQ', 'MCQ']:
                if question.correct_answer == answer:
                    score += 1
            elif question.question_type == 'ES':
                requires_manual_review = True

        # Save the submission
        submission = ExamSubmission.objects.create(
            exam=exam,
            student=student,
            answers=answers,
            score=score if not requires_manual_review else None,
            is_graded=not requires_manual_review,
            requires_manual_review=requires_manual_review
        )

        return redirect('student_dashboard' if hasattr(user, 'student') else 'guardian_dashboard')

    # Render the exam form
    return render(request, 'exam/submit_exam.html', {
        'exam': exam,
        'questions': exam.questions.all()
    })


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
        student_for_view = user.student_profile
        if student_for_view.current_class != parent_item_class_assigned:
            messages.error(request, f"You are not enrolled in the class for this {item_type_verbose.lower()}.")
            return None, False, {}
    else:
        messages.error(request, "You are not authorized to view this result.")
        return None, False, {}
    
    return student_for_view, render_select_student, select_student_context


def view_assessment_result(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id)
    student, render_select_page, select_context = _get_student_for_result_view(
        request, assessment, 'Assessment', 'view_assessment_result', 'submit_assessment'
    )

    if render_select_page:
        return render(request, 'results/select_student.html', select_context) 
    if not student:
        return redirect('guardian_dashboard' if hasattr(request.user, 'guardian_profile') else 'student_dashboard')

    try:
        submission = AssessmentSubmission.objects.get(assessment=assessment, student=student)
    except AssessmentSubmission.DoesNotExist:
        messages.warning(request, f"No submission found for '{assessment.title}' for {student.user.get_full_name()}.")
        return redirect('view_assessment', assessment_id=assessment.id)

    questions_data_for_template = []
    for question in assessment.questions.all().order_by('id'):
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
            'question_instance': question, # Pass the full question object
            'question_text': question.question_text,
            'question_type': question.question_type,
            'options_detailed': options_with_status, # Use this for detailed option display
            'student_answer_display': student_answer_raw, # The raw answer for "Your Answer" section
            'correct_answer_model': question.correct_answer, # The model's correct_answer string for essays/SCQ display
            'is_correct_display': is_overall_correct_display, # Overall correctness for card border
        })

    context = {
        'item': assessment,
        'submission': submission,
        'questions_with_answers': questions_data_for_template, # Pass the processed list
        'item_type_verbose': 'Assessment',
        'student_viewing': student,
    }
    return render(request, 'results/view_result_detail.html', context)


@login_required
def view_exam_result(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    student, render_select_page, select_context = _get_student_for_result_view(
        request, exam, 'Exam', 'view_exam_result', 'submit_exam'
    )
    if render_select_page:
        return render(request, 'results/select_student_for_result.html', select_context)
    if not student:
        return redirect('guardian_dashboard' if hasattr(request.user, 'guardian_profile') else 'student_dashboard')
    # ... rest of the logic similar to view_assessment_result ...
    try:
        submission = ExamSubmission.objects.get(exam=exam, student=student)
    except ExamSubmission.DoesNotExist:
        messages.warning(request, f"No submission found for exam '{exam.title}' for {student.user.get_full_name()}.")
        return redirect('view_exam', exam_id=exam.id)

    questions_with_answers = []
    for question in exam.questions.all().order_by('id'): 
        student_answer_data = submission.answers.get(str(question.id))
        questions_with_answers.append({
            'question_text': question.question_text,
            'question_type': question.question_type,
            'options': question.options_list(),
            'correct_answer': question.correct_answer,
            'student_answer': student_answer_data,
            'is_correct_display': question.is_option_correct(student_answer_data) if question.question_type != 'ES' else None,
        })
    
    context = {
        'item': exam, 'submission': submission, 'questions_with_answers': questions_with_answers,
        'item_type_verbose': 'Exam', 'student_viewing': student,
    }
    return render(request, 'results/view_result_detail.html', context)


@login_required
def view_assignment_result(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student, render_select_page, select_context = _get_student_for_result_view(
        request, assignment, 'Assignment', 'view_assignment_result', 'submit_assignment'
    )
    if render_select_page:
        return render(request, 'results/select_student_for_result.html', select_context)
    if not student:
        return redirect('guardian_dashboard' if hasattr(request.user, 'guardian_profile') else 'student_dashboard')
    # ... rest of the logic similar to view_assessment_result ...
    try:
        submission = AssignmentSubmission.objects.get(assignment=assignment, student=student)
    except AssignmentSubmission.DoesNotExist:
        messages.warning(request, f"No submission found for assignment '{assignment.title}' for {student.user.get_full_name()}.")
        return redirect('view_assignment', assignment_id=assignment.id)

    questions_with_answers = []
    for question in assignment.questions.all().order_by('id'):
        student_answer_data = submission.answers.get(str(question.id))
        questions_with_answers.append({
            'question_text': question.question_text,
            'question_type': question.question_type,
            'options': question.options_list,
            'correct_answer': question.correct_answer,
            'student_answer': student_answer_data,
            'is_correct_display': question.is_option_correct(student_answer_data) if hasattr(question, 'is_option_correct') and question.question_type != 'ES' else None,
        })
    
    context = {
        'item': assignment, 'submission': submission, 'questions_with_answers': questions_with_answers,
        'item_type_verbose': 'Assignment', 'student_viewing': student,
    }
    return render(request, 'results/view_result_detail.html', context)

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


def view_student_result(request, student_id, term_id):
    """
    Displays a student's result for a specific term and allows PDF download.
    """
    if HTML is None:
        # WeasyPrint not installed, handle gracefully (e.g., disable PDF download)
        pass

    try:
        student = get_object_or_404(Student.objects.select_related('user', 'current_class'), user_id=student_id)
        term = get_object_or_404(Term.objects.select_related('session'), id=term_id)
        session = term.session
        class_obj = student.current_class
        result = get_object_or_404(Result.objects.select_related('term__session'), student=student, term=term)

    except Http404 as e:
        return HttpResponse("Result data not found.", status=404)
    except Exception as e:
        return HttpResponse("An error occurred while retrieving result data.", status=500)

    # --- Permissions Check ---
    financial_record = FinancialRecord.objects.filter(student=student, term=term).first()
    can_view_result = (not financial_record) or (financial_record and financial_record.can_access_results) 

    # --- Prepare Data for Template ---
    profile_image_url = None
    if student.profile_image:
        try:
            profile_image_url = build_absolute_uri(request, student.profile_image.url)
        except Exception as e:
            print(f"Error building profile image URL: {e}") # Log error but continue

    # Attendance Data
    total_days = Attendance.objects.filter(student=student, term=term).count() # Filter by term too? Adjust if needed.
    present_days = Attendance.objects.filter(student=student, term=term, is_present=True).count() # Filter by term too?
    absent_days = total_days - present_days
    attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0

    attendance_data = {
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'attendance_percentage': round(attendance_percentage, 1), # Round for display
    }

    # Teacher and Principal Remarks
    teacher_remarks = result.teacher_remarks
    principal_remarks = result.principal_remarks

    # Fetch Subject Results and Class Averages
    subjects_in_class_term = Subject.objects.filter(
        class_assignments__class_assigned=class_obj,
        class_assignments__session=session,
        class_assignments__term=term
    ).distinct()

    # Fetch finalized results for these subjects only
    subject_results_query = SubjectResult.objects.filter(
        result=result,
        subject__in=subjects_in_class_term,
    ).select_related('subject') # Optimize subject name lookup

    # Prepare data for Chart.js and potentially for PDF (if chart is rendered as image later)
    chart_data = []
    subject_results_list = [] # Keep the queryset for the main template table
    for sr in subject_results_query:
        class_average = sr.get_class_average(sr.subject, term, class_obj) 
        total_score_val = sr.total_score() 

        # Append full object for template table
        subject_results_list.append(sr)

        # Append data for JSON chart (convert Decimals to float here)
        chart_data.append({
            'subject': sr.subject.name,
            'total_score': float(total_score_val) if total_score_val is not None else 0.0,
            'class_average': float(class_average) if class_average is not None else 0.0
        })

    # --- Context for Template Rendering ---
    school_logo_url = build_absolute_uri(request, 'images/logo.jpg') # Use your actual logo path
    signature_url = build_absolute_uri(request, 'images/signature.png') # Use your actual signature path

    context = {
        'student': student,
        'result': result,
        'term': term,
        'session': session, 
        'class_obj': class_obj,
        'subject_results': subject_results_list, 
        'chart_data_json': json.dumps(chart_data), 
        'attendance_data': attendance_data,
        'teacher_comment': teacher_remarks,
        'principal_comment': principal_remarks,
        'profile_image_url': profile_image_url,
        'school_logo_url': school_logo_url,
        'signature_url': signature_url,
        'is_pdf_render': False, # Flag for conditional rendering in template (optional)
    }

    # --- PDF Download Handling ---
    if "download" in request.GET and request.GET["download"] == "pdf":
        if HTML is None:
            return HttpResponse("PDF generation library (WeasyPrint) is not installed or configured correctly.", status=501) # 501 Not Implemented

        context['is_pdf_render'] = True # Set flag for PDF context

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
                stylesheets=[css], # Pass the loaded CSS object or list of paths
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

    return render(request, 'guardian/view_result.html', context)