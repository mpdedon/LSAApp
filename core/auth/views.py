# core/auth/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.sessions.models import Session
from django.contrib.messages.views import SuccessMessageMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse_lazy
from django.db.models import Count, Q
from collections import defaultdict
from decimal import Decimal
from core.models import Student, Teacher, Guardian, Assignment, Result, Attendance, Subject, Class, Payment
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
        return context

# Custom Guardian Registration
class GuardianRegisterView(FormView):
    template_name = 'auth/guardian_register.html'

    def get(self, request, *args, **kwargs):
        form = GuardianRegistrationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = GuardianRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('login')
        else:
            print(form.errors)
            
        return render(request, self.template_name, {'form': form})

    def form_invalid(self, form):
        messages.error(self.request, "There was an error with the registration. Please try again.")
        return super().form_invalid(form)

# Custom Teacher Registration
class TeacherRegisterView(FormView):
    template_name = 'auth/teacher_register.html'

    def get(self, request, *args, **kwargs):
        form = TeacherRegistrationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = TeacherRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('login')
        return render(request, self.template_name, {'form': form})
    
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
            return reverse_lazy('school-setup')
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
        username = form.cleaned_data.get('username', 'Unknown')
        logger.warning(f"Invalid login attempt: {username}")

        # Add a generic error message  
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
def admin_required(login_url=None):
    return user_passes_test(lambda u: u.is_superuser, login_url=login_url or '/login/')

@login_required
@admin_required() # Apply decorator
def admin_dashboard(request):
    # Fetch counts (use .count() for efficiency)
    student_count = Student.objects.filter(status='active').count() # Count only active?
    teacher_count = Teacher.objects.filter(status='active').count() # Count only active?
    guardian_count = Guardian.objects.count()
    class_count = Class.objects.count()
    session_count = Session.objects.count()
    term_count = Term.objects.count()
    subject_count = Subject.objects.count()
    payment_count = Payment.objects.count() # Total number of payment records

    # Fetch recent enrollments (Example using Student's class assignment change)
    recent_enrollments = Student.objects.select_related(
        'user', 'current_class', 'current_class__term__session' # Adjust relations
        ).order_by('-user__date_joined')[:5] # Example: recent student creations

    # Fetch data for charts (Example: Students per class)
    # Needs optimization for large datasets
    class_counts_query = Class.objects.annotate(
        num_students=Count('enrolled_students', filter=Q(enrolled_students__status='active'))
    ).order_by('name')

    student_counts_by_class_labels = [c.name for c in class_counts_query]
    student_counts_by_class_data = [c.num_students for c in class_counts_query]


    context = {
        'student_count': student_count,
        'teacher_count': teacher_count,
        'guardian_count': guardian_count,
        'class_count': class_count,
        'session_count': session_count,
        'term_count': term_count,
        'subject_count': subject_count,
        'payment_count': payment_count,
        'recent_enrollments': recent_enrollments, # Pass recent enrollments
        'student_counts_by_class_labels': student_counts_by_class_labels, # Data for JS chart
        'student_counts_by_class_data': student_counts_by_class_data,   # Data for JS chart
        # Add other analytics data needed
    }
    # Use the new base template for rendering
    return render(request, 'setup/dashboard.html', context) # Adjust template path

@login_required
@user_passes_test(lambda u: u.role == 'student')
def student_dashboard(request):

    # --- Fetch Core Objects Safely ---
    try:
        student = Student.objects.select_related(
            'user', 'current_class' 
        ).get(user=request.user)
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect('login') 

    current_class = student.current_class
    active_term = Term.objects.filter(is_active=True).select_related('session').first()
    active_session = active_term.session if active_term else None

    if not current_class or not active_term:
        # Handle case where student isn't assigned a class or no active term
        messages.warning(request, "Class or active term information is currently unavailable.")
        # Render template with minimal data or redirect
        context = {'student': student, 'term': active_term}
        return render(request, 'student/student_dashboard.html', context)

    # --- Initialize Data Dictionaries (using student.id) ---
    student_id = student.user.id 
    attendance_data = {}
    assignments_data = {} 
    # assessments/exams can be passed as querysets filtered later
    financial_data = {}
    result_data = {}
    archived_results_data = defaultdict(list) # Keep using defaultdict


    # --- Fetch Data Efficiently ---
    now = timezone.now()

    # Subjects for the current class/term
    subjects = Subject.objects.filter(
        class_assignments__class_assigned=current_class,
        class_assignments__term=active_term # Filter by active term
        # class_assignments__session=active_session # Redundant if filtering by active_term
    ).distinct()

    # Assignments for current class & term (show upcoming/recent?)
    # Decide which assignments to show (e.g., only pending, or recent)
    assignments = Assignment.objects.filter(
        class_assigned=current_class,
        term=active_term, # Filter by term
        due_date__gte=now # Optionally filter only upcoming
    ).select_related('subject', 'teacher__user').order_by('due_date')

    # Fetch student's submissions for these assignments
    assignment_submissions = AssignmentSubmission.objects.filter(
        student=student,
        assignment__in=assignments
    ).values('assignment_id', 'is_completed') # Get IDs and completion status
    submissions_dict = {sub['assignment_id']: sub['is_completed'] for sub in assignment_submissions}

    # Calculate assignment summary
    total_assign = assignments.count()
    completed_assign = sum(1 for assign_id, completed in submissions_dict.items() if completed)
    pending_assign = total_assign - completed_assign
    completion_perc = round((completed_assign / total_assign * 100), 1) if total_assign > 0 else 0
    assignments_data[student_id] = {
        'total': total_assign,
        'completed': completed_assign,
        'pending': pending_assign,
        'completion_percentage': completion_perc,
        'details': assignments # Pass the queryset for iteration
    }

    # Assessments & Exams for current class & term
    assessments = Assessment.objects.filter(
        class_assigned=current_class,
        term=active_term
        # due_date__gte=now # Optional: Filter upcoming only
        ).select_related('subject').order_by('due_date')

    exams = Exam.objects.filter(
        class_assigned=current_class,
        term=active_term
        # due_date__gte=now # Optional: Filter upcoming only
        ).select_related('subject').order_by('due_date')

    # Attendance Summary (for the active term is more relevant here)
    attendance_summary = Attendance.objects.filter(
        student=student,
        term=active_term
    ).aggregate(
        total_days=Count('id'),
        present_days=Count('id', filter=Q(is_present=True))
    )
    total_days = attendance_summary.get('total_days', 0) or 0
    present_days = attendance_summary.get('present_days', 0) or 0
    absent_days = total_days - present_days
    att_percentage = round((present_days / total_days * 100), 1) if total_days > 0 else 0
    attendance_data[student_id] = {
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'attendance_percentage': att_percentage
    }

    # Financial Record for current term
    financial_record = FinancialRecord.objects.filter(
        student=student, term=active_term
    ).first() # Use first() instead of get() to handle non-existence gracefully

    if financial_record:
        financial_data[student_id] = {
            'total_fee': financial_record.total_fee,
            'total_discount': financial_record.total_discount,
            'total_paid': financial_record.total_paid,
            'outstanding_balance': financial_record.outstanding_balance,
            'can_access_results': financial_record.can_access_results,
            'is_fully_paid': financial_record.is_fully_paid,
            'payment_percentage': round((financial_record.total_paid / financial_record.total_fee * 100), 1) if financial_record.total_fee > 0 else (100 if financial_record.is_fully_paid else 0),
            'has_waiver': financial_record.has_waiver,
        }
    else:
        # Handle case where student might not have a financial record yet
        # Check if a fee record exists to determine waiver/zero fee status
        fee_record = StudentFeeRecord.objects.filter(student=student, term=active_term).first()
        has_waiver = fee_record and fee_record.waiver
        total_fee = fee_record.net_fee if fee_record else Decimal('0.00')
        financial_data[student_id] = {
            'total_fee': total_fee,
            'total_discount': fee_record.discount if fee_record else Decimal('0.00'),
            'total_paid': Decimal('0.00'),
            'outstanding_balance': total_fee,
            'can_access_results': has_waiver or (total_fee <= Decimal('0.01')), # Access if waived or fee is zero
            'is_fully_paid': (total_fee <= Decimal('0.01')),
            'payment_percentage': 100 if (total_fee <= Decimal('0.01')) else 0,
            'has_waiver': has_waiver,
        }

    # Results (Current Term)
    current_result = Result.objects.filter(
        student=student, term=active_term, is_approved=True
    ).first()
    if current_result:
         result_data[student_id] = {
             'id': current_result.id,
             'term_id': current_result.term_id,
             'student_id': student_id,
         }
    else:
         result_data[student_id] = None

    # Results (Archived) - Fetch only necessary fields
    archived_terms = Term.objects.filter(is_active=False, session=active_session).order_by('-start_date') # Filter by current session? Or all past?
    archived_results_qs = Result.objects.filter(
        student=student, term__in=archived_terms, is_approved=True, is_archived=True
        ).select_related('term').values('id', 'term_id', 'term__name') # Fetch only needed fields

    for res in archived_results_qs:
        archived_results_data[student_id].append({
            'term_name': res['term__name'],
            'term_id': res['term_id'],
            'student_id': student_id, # Already known
            'result_id': res['id']
        })

    notifications = Notification.objects.filter(
        Q(audience='guardian') | Q(audience='all'),
        is_active=True
    ).exclude(
        expiry_date__lt=timezone.now().date()
    ).order_by('-created_at')

    # Fetch academic alerts for the students
    academic_alerts = AcademicAlert.objects.filter(
        student=student,
        due_date__gte=timezone.now()
    ).select_related('teacher', 'student').order_by('-due_date')

    context = {
        'student': student,
        'current_class': current_class, # Renamed from 'class' to avoid conflict
        'term': active_term,
        'session': active_session,
        'subjects': subjects,
        'assignments_data': assignments_data, 
        'assessments': assessments, # Pass queryset
        'exams': exams, # Pass queryset
        'attendance_data': attendance_data,
        'financial_data': financial_data,
        'result_data': result_data,
        'archived_results_data': dict(archived_results_data),
        'notifications': notifications,
        'academic_alerts': academic_alerts,
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
    exams = Exam.objects.filter(created_by=teacher.user).order_by('-created_at')
    
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
        'exams': exams,
        'message_counts': message_counts_dict,
    }

    return render(request, 'teacher/teacher_dashboard.html', context)

# Guardian Dashboard View

@login_required
@user_passes_test(lambda u: u.role == 'guardian')
def guardian_dashboard(request):
  
    if request.user.role != 'guardian':
        return redirect('login') 
    
    guardian = Guardian.objects.get(user=request.user)
    students = guardian.students.all()
    current_session = Session.objects.get(is_active=True)
    current_term = Term.objects.filter(session=current_session, is_active=True).order_by('-start_date').first()
    print(f"DEBUG: Current Term identified as: {current_term} - {current_term.id}")
    teachers = Teacher.objects.filter(subjectassignment__subject__students__in=students).distinct()
    archived_terms = Term.objects.filter(is_active=False).order_by('-start_date')
    print(f"DEBUG: Archived Terms found: {[str(t) for t in archived_terms]}")

    assignments_data = {}
    assessments_data = {}
    exams_data = {}
    messages_data = defaultdict(list)
    attendance_data = {}
    attendance_logs = {}
    financial_data = {}
    result_data = {}
    archived_results_data = defaultdict(list)
    
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

        has_waiver = student_fee_record and student_fee_record.waiver

        if has_waiver:
            can_access_results = True
        
        elif financial_record:
            can_access_results = financial_record.can_access_results
        
        else:
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
            'has_waiver': has_waiver,
        }

        # Get results if the guardian can access them
        #if can_access_results:
        result = Result.objects.filter(student=student, term=current_term, is_approved=True).first()
        if result:
            result_data[student.user.id] = {
                'id': result.id,
                'term_id': result.term.id,
                'student_id': result.student.user.id,
            }
        else:
            result_data[student.user.id] = None
        # Fetch archived results (past terms)
        for term in archived_terms:
            archived_result = Result.objects.filter(
                student=student, 
                term=term, 
                is_approved=True,  
                is_archived=True   
            ).first()
            
            if archived_result:
                archived_results_data[student.user.id].append({
                    'term_name': term.name,
                    'term_id': term.id,
                    'student_id': student.user.id,
                    'result_id': archived_result.id
                })

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
        'archived_results_data': archived_results_data,
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


