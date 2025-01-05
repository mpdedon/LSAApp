# core/auth/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.messages.views import SuccessMessageMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse_lazy
from django.db.models import Count, Q
from collections import defaultdict
from core.models import Student, Teacher, Guardian, Assignment, Result, Attendance
from core.models import Session, Term, Message, Assessment, Exam, Notification, AssignmentSubmission, AcademicAlert
from core.models import FinancialRecord, StudentFeeRecord, AssessmentSubmission
from django.db.models import Sum
from django.views.generic.edit import FormView
from django.contrib import messages
from core.guardian.forms import GuardianRegistrationForm
from core.teacher.forms import TeacherRegistrationForm
from core.auth.forms import LoginForm
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class RegisterView(TemplateView):
    template_name = 'auth/register.html'

    # You can override get_context_data if you need to pass additional context
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any custom context if needed
        return context
# Custom Guardian Registration
class GuardianRegistrationView(FormView):
    template_name = 'auth/guardian_register.html'
    form_class = GuardianRegistrationForm
    success_url = reverse_lazy('guardian_registration')

    def form_valid(self, form):
        # Create the user and guardian instances
        user = form.save(commit=False)
        user.role = 'guardian'
        user.save()

        # Create Guardian profile
        guardian = form.save_guardian_profile(user)
        messages.success(self.request, f"Guardian {user.username} registered successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "There was an error with the registration. Please try again.")
        return super().form_invalid(form)

# Custom Teacher Registration
class TeacherRegistrationView(FormView):
    template_name = 'auth/teacher_register.html'
    form_class = TeacherRegistrationForm
    success_url = reverse_lazy('teacher_registration')

    def form_valid(self, form):
        # Create the user and teacher instances
        user = form.save(commit=False)
        user.role = 'teacher'
        user.save()

        # Create Teacher profile
        teacher = form.save_teacher_profile(user)
        messages.success(self.request, f"Teacher {user.username} registered successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "There was an error with the registration. Please try again.")
        return super().form_invalid(form)

# Login view
class CustomLoginView(LoginView):
    template_name = 'auth/login.html'
    form_class = LoginForm

    def get_success_url(self):
        user = self.request.user
        logger.info(f"Login successful: User: {user.username}, Role: {user.role}")

        # Redirection based on user roles
        if user.is_superuser:
            return reverse_lazy('school_setup')
        elif user.role == 'teacher':
            return reverse_lazy('teacher_dashboard')
        elif user.role == 'student':
            return reverse_lazy('student_dashboard')
        elif user.role == 'guardian':
            return reverse_lazy('guardian_dashboard')
        else:
            logger.warning(f"Unknown role for user {user.username}. Redirecting to login.")
            return reverse_lazy('login')

    def form_invalid(self, form):
        # Log the invalid login attempt
        username = form.cleaned_data.get('username')
        logger.warning(f"Invalid login attempt: {username}")
        return super().form_invalid(form)

    def form_valid(self, form):
        # Log successful login and handle login process
        try:
            user = form.get_user()
            logger.info(f"Login successful for user: {user.username}")
            login(self.request, user)
            return super().form_valid(form)
        except Exception as e:
            logger.error(f"Error during login for user: {form.cleaned_data.get('username')}. Error: {str(e)}")
            form.add_error(None, _("An unexpected error occurred. Please try again."))
            return super().form_invalid(form)

# Admin dashboard view
@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('login')
    # Add any data you want to display on the dashboard
    return render(request, 'setup/dashboard.html')

# Student Dashboard
@login_required
@user_passes_test(lambda u: u.role == 'student')
def student_dashboard(request):

    if request.user.role != 'student':
        return redirect('login')  
    
    student = Student.objects.select_related('current_class').get(user=request.user)
    current_class = student.current_class
    subjects = current_class.subjects.prefetch_related('assignments').all()
    assignments = Assignment.objects.filter(class_assigned=current_class).select_related('teacher')
    assessments = Assessment.objects.filter(class_assigned=current_class).select_related('teacher')
    results = Result.objects.filter(student=student).select_related('term')
    attendance = Attendance.objects.filter(student=student).order_by('-date')


    context = {
        'student': student,
        'class': current_class,
        'subjects': subjects,
        'assignments': assignments,
        'assessments': assessments,
        'results': results,
        'attendance': attendance,
    }
    return render(request, 'student/student_dashboard.html', context)

# Teacher Dashboard
@login_required
@user_passes_test(lambda u: u.role == 'teacher')
def teacher_dashboard(request):

    if request.user.role != 'teacher':
        return redirect('login')  
    
    teacher = Teacher.objects.get(user=request.user)
    assigned_classes = teacher.current_classes()
    students = Student.objects.filter(current_class__in=assigned_classes).distinct()
    class_subjects = teacher.form_class_subjects()
    subjects_taught = teacher.subjects_taught()                       
    classes_subjects_taught = teacher.assigned_classes()
    guardians = set(student.student_guardian for student in students if student.student_guardian is not None)
    assignments = Assignment.objects.filter(teacher=teacher)
    assessments = Assessment.objects.filter(created_by=teacher.user).order_by('-created_at')
    
    current_session = Session.objects.get(is_active=True)
    current_term = Term.objects.filter(session=current_session, is_active=True).order_by('-start_date').first()

    # Calculate weeks in the term
    weeks = current_term.get_term_weeks

    
    # Create a dictionary to store the message count for each guardian
    message_counts = (
        Message.objects.filter(student__in=students)
        .values('student')
        .annotate(count=Count('id'))
    )

    # Transform into a dictionary for easy lookup
    message_counts_dict = {msg['student']: msg['count'] for msg in message_counts}
    
    context = {
        'teacher': teacher,
        'assigned_classes': assigned_classes,
        'students': students,
        'class_subjects': class_subjects,
        'subjects_taught': subjects_taught,
        'classes_subjects_taught': classes_subjects_taught,
        'guardians': guardians,
        'current_term': current_term,
        'weeks': weeks,
        'assignments': assignments,
        'assessments': assessments,
        'message_counts': message_counts_dict,
    }

    return render(request, 'teacher/teacher_dashboard.html', context)

# Guardian Dashboard View

@login_required
@user_passes_test(lambda u: u.role == 'guardian')
def guardian_dashboard(request):
    guardian = Guardian.objects.get(user=request.user)
    students = guardian.students.all()
    current_session = Session.objects.get(is_active=True)
    current_term = Term.objects.filter(session=current_session, is_active=True).order_by('-start_date').first()
    teachers = Teacher.objects.filter(subjectassignment__subject__students__in=students).distinct()

    assignments_data = {}
    assessments_data = {}
    exams_data = {}
    messages_data = defaultdict(list)
    attendance_data = {}
    attendance_logs = {}
    financial_data = {}
    result_data = {}
    
    notifications = Notification.objects.filter(
        Q(audience='guardian') | Q(audience='all'),
        is_active=True
    ).exclude(
        expiry_date__lt=timezone.now().date()
    ).order_by('-created_at')

    # Fetch academic alerts for the students
    academic_alerts = AcademicAlert.objects.filter(
        student__in=students,
        due_date__gte=timezone.now()
    ).select_related('teacher', 'student').order_by('-due_date')

    for student in students:
        # Assignments data
        total_assignments = Assignment.objects.filter(
            class_assigned=student.current_class,
            active=True, due_date__gte=timezone.now()
            ).count()
        
        completed_assignments = AssignmentSubmission.objects.filter(
            student=student, assignment__class_assigned=student.current_class, is_completed=True
        ).count()

        if total_assignments > 0:
            completion_percentage = (completed_assignments / total_assignments) * 100
        else:
            completion_percentage = 0
        # Get the list of assignment details
        assignments_details = Assignment.objects.filter(class_assigned=student.current_class)

        assignments_data[student.user.id] = {
            'total': total_assignments,
            'completed': completed_assignments,
            'pending': total_assignments - completed_assignments,
            'completion_percentage': completion_percentage,
            'details': assignments_details
        }

        # Assessments and exams data
        online_assessments = Assessment.objects.filter(class_assigned=student.current_class, due_date__gte=timezone.now())
        assessments_data[student.user.id] = online_assessments

        online_exams = Exam.objects.filter(class_assigned=student.current_class, due_date__gte=timezone.now())
        exams_data[student.user.id] = online_exams
    
        # Fetch messages sent by any of these teachers regarding this student
        student_messages = Message.objects.filter(
            recipient=guardian.user,  # Ensure recipient is the guardian
            student=student  # Ensure the message is related to this student
        ).order_by('-timestamp')
        # Initialize messages data for each student
        if student.user.id not in messages_data:
            messages_data[student.user.id] = {'messages': [], 'message_counts': {}}
        
        # Populate messages
        for message in student_messages:
            date_key = message.timestamp.date()
            messages_data[student.user.id]['messages'].append({
                'id': message.id,  # Add message ID for toggle functionality
                'content': message.content,
                'title': message.title,  # Adjust to your Message model fields
                'date': date_key,
                'sender': message.sender.get_full_name(),  # Adjust for readability
            })

            # Populate message counts by sender
        message_counts = student_messages.values('sender').annotate(count=Count('id'))
        message_counts_dict = {msg['sender']: msg['count'] for msg in message_counts}
        messages_data[student.user.id]['message_counts'] = message_counts_dict
        # Attendance data
        total_days = Attendance.objects.filter(student=student).count()
        present_days = Attendance.objects.filter(student=student, is_present=True).count()
        attendance_data[student.user.id] = {
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': total_days - present_days,
            'attendance_percentage': (present_days / total_days * 100) if total_days > 0 else 0
        }

        # Detailed logs
        logs = Attendance.objects.filter(student=student).order_by('-date')  # Recent logs first
        attendance_logs[student.user.id] = [
            {
                'date': log.date,
                'status': 'Present' if log.is_present else 'Absent',
                'remarks': log.remarks if hasattr(log, 'remarks') else ''
            }
            for log in logs
        ]
        # Retrieve StudentFeeRecord and FinancialRecord for the current term
        student_fee_record = StudentFeeRecord.objects.filter(student=student, term=current_term).first()
        financial_record = FinancialRecord.objects.filter(student=student, term=current_term).first()

        if student_fee_record:
            total_fee = student_fee_record.net_fee
            discount = student_fee_record.discount
        else:
            total_fee = discount = 0

        if financial_record:
            total_paid = financial_record.payments.aggregate(total=Sum('amount_paid'))['total'] or 0
            outstanding_balance = financial_record.total_fee - financial_record.total_discount - total_paid
            is_fully_paid = outstanding_balance <= 0
            can_access_results = financial_record.can_access_results
        else:
            total_paid = 0
            outstanding_balance = total_fee - discount  # Full balance if no financial record
            is_fully_paid = False
            can_access_results = False

        if total_fee > 0:
            payment_percentage = (total_paid / total_fee) * 100
        else:
            payment_percentage = 0
        # Update financial data for the context
        financial_data[student.user.id] = {
            'total_fee': total_fee,
            'total_discount': discount,
            'total_paid': total_paid,
            'outstanding_balance': outstanding_balance,
            'can_access_results': can_access_results,
            'is_fully_paid': is_fully_paid,
            'payment_percenage': payment_percentage,
        }

        can_access_results = financial_data[student.user.id]['can_access_results']

        # Get results if the guardian can access them
        if can_access_results:
            result = Result.objects.filter(student=student, term=current_term).first()
            if result:
                result_data[student.user.id] = {
                    'id': result.id,
                    'term_id': result.term.id,
                    'student_id': result.student.user.id,
                }
            else:
                result_data[student.user.id] = None
        
    context = {
        'guardian': guardian,
        'students': students,
        'teachers': teachers,
        'assignments_data': assignments_data,
        'assessments_data': assessments_data,
        'exams_data': exams_data,
        'messages_data': messages_data,
        'attendance_data': attendance_data,
        'attendance_logs': attendance_logs,
        'financial_data': financial_data,
        'result_data': result_data,
        'notifications': notifications,
        'academic_alerts': academic_alerts,
    }
    return render(request, 'guardian/guardian_dashboard.html', context)

# Logout view
class CustomLogoutView(LogoutView):
    template_name = 'auth/logout.html'

# Password Reset Views
class PasswordResetView(SuccessMessageMixin, PasswordResetView):
    template_name = 'auth/password_reset.html'
    form_class = PasswordResetForm
    email_template_name = 'auth/password_reset_email.html'
    subject_template_name = 'auth/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    success_message = _("We've emailed you instructions for setting your password, "
                        "if an account exists with the email you entered. You should receive them shortly. "
                        "If you don't receive an email, please make sure you've entered the address "
                        "you registered with, and check your spam folder.")

class PasswordResetDoneView(PasswordResetDoneView):
    template_name = 'auth/password_reset_done.html'

class PasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'auth/password_reset_confirm.html'
    form_class = SetPasswordForm
    success_url = reverse_lazy('password_reset_complete')

class PasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'auth/password_reset_complete.html'


