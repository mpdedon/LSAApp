# core.student.views

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q
from core.models import Student, Assignment, AssignmentSubmission, Teacher, CustomUser, Message
from core.models import Assessment, AssessmentSubmission, Exam, ExamSubmission, AcademicAlert 
from .forms import StudentRegistrationForm, MessageForm, ReplyForm
from core.assignment.forms import AssignmentSubmissionForm

# Student Views

def StudentRegisterView(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('student_dashboard')
    else:
        form = StudentRegistrationForm()
    return render(request, 'student/register.html', {'form': form})

def StudentProfileView(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('student_dashboard')
    else:
        form = StudentRegistrationForm(instance=request.user)
    return render(request, 'student/profile.html', {'form': form})

@login_required
def student_dashboard(request):
    if not request.user.role == 'student':
        return redirect('login')
    # Add any data for students
    return render(request, 'student_dashboard.html')
    
class StudentListView(View):
    template_name = 'student/student_list.html'

    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        status = request.GET.get('status', 'active')  # Default to 'active'

        # Filter students by status
        students = Student.objects.filter(status=status).order_by('current_class')

        # Apply search filter
        if query:
            students = students.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(LSA_number__icontains=query) |
                Q(current_class__name__icontains=query) |
                Q(student_guardian__user__first_name__icontains=query) |
                Q(student_guardian__user__last_name__icontains=query)
            )

        # Paginate students
        paginator = Paginator(students, 20)  # Show 15 students per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'active_tab': status
        })

class BulkUpdateStudentsView(View):
    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        selected_students = request.POST.getlist("selected_students")

        if not selected_students:
            messages.error(request, "No students selected for the bulk action.")
            return redirect("student_list")

        students = Student.objects.filter(user__id__in=selected_students)

        if action == "promote":
            for student in students:
                if student.current_class and student.current_class.next_class:
                    student.current_class = student.current_class.next_class
                    student.save()
            messages.success(request, "Selected students have been promoted.")
        
        elif action == "demote":
            for student in students:
                if student.current_class and student.current_class.previous_class:
                    student.current_class = student.current_class.previous_class
                    student.save()
            messages.success(request, "Selected students have been demoted.")

        elif action == "mark_dormant":
            students.update(status="dormant")
            messages.success(request, "Selected students have been marked as dormant.")
        
        elif action == "mark_active":
            students.update(status="active")
            messages.success(request, "Selected students have been marked as active.")
        
        elif action == "mark_left":
            students.update(status="left")
            messages.success(request, "Selected students have been marked as left.")
        
        else:
            messages.error(request, "Invalid action selected.")

        return redirect("student_list")


class StudentCreateView(View):
    template_name = 'student/student_form.html'

    def get(self, request, *args, **kwargs):
        form = StudentRegistrationForm()
        response = render(request, self.template_name, {'form': form})
        return response

    def post(self, request, *args, **kwargs):
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('student_list')
        else:
            print("Form is NOT valid. Errors: ", form.errors)
        return render(request, self.template_name, {'form': form})

class StudentUpdateView(View):
    template_name = 'student/student_form.html'

    def get(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        form = StudentRegistrationForm(instance=student.user, student_instance=student)
        return render(request, self.template_name, {'form': form, 'is_update': True, 'student': student})

    def post(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        form = StudentRegistrationForm(request.POST, request.FILES, instance=student.user, student_instance=student)

        # Ensure the student fields are updated correctly
        if form.is_valid():
            user = form.save(commit=False)
            user.save()

            student.date_of_birth = form.cleaned_data['date_of_birth']
            student.gender = form.cleaned_data['gender']
            student.profile_image = form.cleaned_data['profile_image']
            student.student_guardian = form.cleaned_data['student_guardian']
            student.relationship = form.cleaned_data['relationship']
            student.current_class = form.cleaned_data['current_class']
            student.save()

            return redirect('student_detail', pk=student.pk)

        return render(request, self.template_name, {'form': form, 'is_update': True, 'student': student})

class StudentDetailView(View):
    template_name = 'student/student_detail.html'

    def get(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        return render(request, self.template_name, {'student': student})

class StudentDeleteView(View):
    template_name = 'student/student_confirm_delete.html'

    def get(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        return render(request, self.template_name, {'student': student})

    def post(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        student.delete()
        return redirect('student_list')

# Example for export_students and student_reports
def export_students(request):
    # Implement export logic here
    pass

def student_reports(request):
    # Implement report generation logic here
    pass

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

    # Render the assessment form
    return render(request, 'assessment/submit_assessment.html', {
        'assessment': assessment,
        'questions': assessment.questions.all()
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

    # Render the exam form
    return render(request, 'exam/submit_exam.html', {
        'exam': exam,
        'questions': exam.questions.all()
    })


@login_required
def message_inbox(request):
    """
    A central, generic inbox for the logged-in user.
    Shows received message threads.
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
    The list of possible recipients is determined by the sender's role.
    Recipient and other context can be pre-selected via GET parameters.
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


