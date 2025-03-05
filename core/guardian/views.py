# views.py

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q
import reportlab
from .forms import GuardianRegistrationForm
from core.models import Guardian, Term, FinancialRecord, Student, Result, SubjectResult, Attendance
from core.models import Assignment, Assessment, Exam, AssessmentSubmission, ExamSubmission, AcademicAlert
from core.assignment.forms import AssignmentSubmission, AssignmentSubmissionForm


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
        print(action)
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
        form = GuardianRegistrationForm(request.POST, request.FILES, instance=guardian.user)

        if form.is_valid():
            user = form.save(commit=False)
            user.save()

            guardian.gender = form.cleaned_data['gender']
            guardian.profile_image = form.cleaned_data['profile_image']
            guardian.contact = form.cleaned_data['contact']
            guardian.address= form.cleaned_data['address']
            guardian.save()
            
            return redirect('guardian_dashboard', pk=guardian.pk)
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

def view_student_result(request, student_id, term_id):
    student = get_object_or_404(Student, user_id=student_id)
    term = get_object_or_404(Term, id=term_id)
    result = get_object_or_404(Result, student=student, term=term)

    # Correctly define the attendance data variables
    total_days = Attendance.objects.filter(student=student).count()
    present_days = Attendance.objects.filter(student=student, is_present=True).count()

    # Create the attendance data dictionary
    attendance_data = {
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': total_days - present_days,
        'attendance_percentage': (present_days / total_days * 100) if total_days > 0 else 0
    }

    # Extract teacher and principal comments from the result
    teacher_remarks = result.teacher_remarks
    principal_remarks = result.principal_remarks

    # Check permission to view results
    financial_record = FinancialRecord.objects.filter(student=student, term=term).first()
    if not financial_record or not financial_record.can_access_results:
        return HttpResponse("You do not have permission to view this result.", status=403)

    # Get subject results for the student's term
    subject_results = SubjectResult.objects.filter(result=result).select_related('subject')

    context = {
        'student': student,
        'result': result,
        'term': term,
        'subject_results': subject_results,
        'attendance_data': attendance_data,
        'teacher_comment': teacher_remarks,
        'principal_comment': principal_remarks,
    }
    
    # Handle PDF download request
    if request.GET.get('download') == 'true':
        html_string = render_to_string('guardian/view_result.html', context)
        pdf = reportlab.HTML(string=html_string).write_pdf()

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{student.user.first_name}_result_{term.name}.pdf"'
        return response

    return render(request, 'guardian/view_result.html', context)

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
                'assignment': assignment,
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

    # Determine the logged-in user's type
    if hasattr(request.user, 'guardian'):
        guardian = request.user.guardian

        # Filter students by the guardian and the assignment's class
        students = Student.objects.filter(
            student_guardian=guardian,
            current_class=assessment.class_assigned
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
            return render(request, 'assessment/select_student.html', {
                'students': students,
                'assessment': assessment,
            })

    else:
        # Handle student users submitting their own assignment
        student = get_object_or_404(
            Student,
            user=request.user,
            current_class=assessment.class_assigned
        )

    # Prevent multiple submissions and overdue submissions
    if assessment.is_due:
        return render(request, 'assessment/assessment_due.html', {"assessment": assessment})
    
    if AssessmentSubmission.objects.filter(assessment=assessment, student=student).exists():
        return render(request, 'assessment/already_submitted.html')

    # Handle POST submission
    if request.method == "POST":
        answers = {}
        score = 0
        requires_manual_review = False

        for question in assessment.questions.all():
            answer = request.POST.get(f'answer_{question.id}')
            answers[str(question.id)] = answer

            # Auto-grade SCQ/MCQ
            if question.question_type in ['SCQ', 'MCQ']:
                if question.correct_answer == answer:
                    score += 1
            elif question.question_type == 'ES':
                requires_manual_review = True

        # Save the submission
        submission = AssessmentSubmission.objects.create(
            assessment=assessment,
            student=student,
            answers=answers,
            score=score if not requires_manual_review else None,
            is_graded=not requires_manual_review,
            requires_manual_review=requires_manual_review
        )

        # Notify guardian
        notify_guardian(submission)
        return redirect('student_dashboard' if hasattr(user, 'student') else 'guardian_dashboard')

    # Render the assessment form
    return render(request, 'assessment/submit_assessment.html', {
        'assessment': assessment,
        'questions': assessment.questions.all()
    })

def notify_guardian(student, assessment):
    if student.student_guardian:
        guardian = student.student_guardian
        AcademicAlert.objects.create(
            alert_type='assessment_submission',
            title=f"{student.user.get_full_name()} submitted {assessment.title}",
            summary=f"{student.user.get_full_name()} has submitted the assessment titled '{assessment.title}'.",
            teacher=assessment.created_by.teacher,
            student=student,
            due_date=assessment.due_date,
            duration=assessment.duration,
            related_object_id=assessment.id
        )
    else:
        print(f"No guardian associated with student {student.user.get_full_name()}")


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
            student = get_object_or_404(students, id=student_id)
        elif students.count() == 1:
            student = students.first()
        else:
            # Render a selection page if multiple students match
            return render(request, 'exam/select_student.html', {
                'students': students,
                'exam': exam,
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

        # Notify guardian
        notify_guardian(submission)
        return redirect('student_dashboard' if hasattr(user, 'student') else 'guardian_dashboard')

    # Render the exam form
    return render(request, 'exam/submit_exam.html', {
        'exam': exam,
        'questions': exam.questions.all()
    })

def notify_guardian(student, exam):
    if student.student_guardian:
        guardian = student.student_guardian
        AcademicAlert.objects.create(
            alert_type='exam_submission',
            title=f"{student.user.get_full_name()} submitted {exam.title}",
            summary=f"{student.user.get_full_name()} has submitted the exam titled '{exam.title}'.",
            teacher=exam.created_by.teacher,
            student=student,
            due_date=exam.due_date,
            duration=exam.duration,
            related_object_id=exam.id
        )
    else:
        print(f"No guardian associated with student {student.user.get_full_name()}")


def export_guardians(request):
    # Implement export logic here
    pass

def guardian_reports(request):
    # Implement report generation logic here
    pass