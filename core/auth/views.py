# core/auth/views.py
from django.shortcuts import render, redirect, get_object_or_404
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
from core.models import Student, Teacher, Guardian, Assignment, Result, Attendance, Subject, Class, Payment, ClassSubjectAssignment
from core.models import Session, Term, Message, Assessment, Exam, Notification, AssignmentSubmission, AcademicAlert
from core.models import FinancialRecord, StudentFeeRecord, AssessmentSubmission, ExamSubmission
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
        'recent_enrollments': recent_enrollments, 
        'student_counts_by_class_labels': student_counts_by_class_labels, # Data for JS chart
        'student_counts_by_class_data': student_counts_by_class_data,   # Data for JS chart
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
    financial_data = {}
    result_data = {}
    archived_results_data = defaultdict(list) # Keep using defaultdict

    # --- Fetch Data Efficiently ---
    now = timezone.now()

    # Subjects for the current class/term
    subjects = Subject.objects.filter(
        class_assignments__class_assigned=current_class,
        class_assignments__term=active_term # Filter by active term
    ).distinct()

    # Assignments for current class & term (show upcoming/recent?)
    # Decide which assignments to show (e.g., only pending, or recent)
    assignments = Assignment.objects.filter(
        class_assigned=current_class,
        term=active_term, 
        due_date__gte=now #
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
        term=active_term,
        due_date__gte=now 
        ).select_related('subject').order_by('due_date')

    exams = Exam.objects.filter(
        class_assigned=current_class,
        term=active_term,
        due_date__gte=now 
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
    ).first() 

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
    all_potential_alerts = AcademicAlert.objects.filter(
            student=student,
            due_date__gte = timezone.now()
        ).select_related(
            'student__user', 'source_user'
        ).order_by('-date_created')[:10]

    # Get IDs of submissions made by these students to avoid showing 'Take It' for completed tasks
    completed_assessment_ids = set(AssessmentSubmission.objects.filter(student=student).values_list('assessment_id', flat=True))
    completed_exam_ids = set(ExamSubmission.objects.filter(student=student).values_list('exam_id', flat=True))
    completed_assignment_ids = set(AssignmentSubmission.objects.filter(student=student).values_list('assignment_id', flat=True))

    action_required_alerts = []
    recent_update_alerts = []

    for alert in all_potential_alerts:
        # Determine the action status
        is_actionable = False
        is_overdue = alert.due_date and alert.due_date < timezone.now().date()

        if alert.alert_type == 'assessment_available' and alert.related_object_id not in completed_assessment_ids and not is_overdue:
            is_actionable = True
        elif alert.alert_type == 'exam_available' and alert.related_object_id not in completed_exam_ids and not is_overdue:
            is_actionable = True
        elif alert.alert_type == 'assignment_available' and alert.related_object_id not in completed_assignment_ids and not is_overdue:
            is_actionable = True
        
        # --- Prepare data for template ---
        # Clean up display text for 'alert_type'
        cleaned_display_type = alert.alert_type.replace('_', ' ').title()

        alert_data = {
            'instance': alert,
            'cleaned_display_type': cleaned_display_type,
            'is_overdue': is_overdue,
            'is_actionable': is_actionable,
        }

        if is_actionable:
            action_required_alerts.append(alert_data)
        else:
            recent_update_alerts.append(alert_data)


    context = {
        'student': student,
        'current_class': current_class, 
        'term': active_term,
        'session': active_session,
        'subjects': subjects,
        'assignments_data': assignments_data, 
        'assessments': assessments, 
        'exams': exams, 
        'attendance_data': attendance_data,
        'financial_data': financial_data,
        'result_data': result_data,
        'archived_results_data': dict(archived_results_data),
        'notifications': notifications,
        'action_required_alerts': action_required_alerts,
        'recent_update_alerts': recent_update_alerts[:6],
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
  
    try:
        guardian = get_object_or_404(Guardian, user=request.user)
    except Guardian.DoesNotExist:
        messages.error(request, "Guardian profile not found.")
        return redirect('login') 

    students = guardian.students.all().select_related('user', 'current_class')

    try:
        current_session = Session.objects.get(is_active=True)
        current_term = Term.objects.get(session=current_session, is_active=True)
    except (Session.DoesNotExist, Term.DoesNotExist, Session.MultipleObjectsReturned, Term.MultipleObjectsReturned) as e:
        messages.warning(request, f"Could not determine the active academic period: {e}. Some data may be unavailable.")
        current_session = None
        current_term = None

    archived_terms = Term.objects.filter(is_active=False).order_by('-start_date')

    teachers = Teacher.objects.none()
    student_class_ids = students.exclude(current_class__isnull=True).values_list('current_class_id', flat=True).distinct()
    if student_class_ids and current_term:
        # This uses the ClassSubjectAssignment model.
        subjects_assigned_to_classes = ClassSubjectAssignment.objects.filter(
            class_assigned_id__in=student_class_ids,
            term=current_term
        ).values_list('subject_id', flat=True)

        teachers = Teacher.objects.filter(
            subjectassignment__class_assigned_id__in=student_class_ids,
            subjectassignment__subject_id__in=subjects_assigned_to_classes,
            subjectassignment__term=current_term
        ).distinct().select_related('user')

    assignments_data = defaultdict(lambda: {'details': [], 'total': 0, 'completed': 0, 'pending': 0, 'completion_percentage': 0})
    assessments_data = defaultdict(list) 
    exams_data = defaultdict(list)
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

    all_potential_alerts = AcademicAlert.objects.filter(
            student__in=students,
            due_date__gte = timezone.now()
        ).select_related(
            'student__user', 'source_user'
        ).order_by('-date_created')

    # Get IDs of submissions made by these students to avoid showing 'Take It' for completed tasks
    completed_assessment_ids = set(AssessmentSubmission.objects.filter(student__in=students).values_list('assessment_id', flat=True))
    completed_exam_ids = set(ExamSubmission.objects.filter(student__in=students).values_list('exam_id', flat=True))
    completed_assignment_ids = set(AssignmentSubmission.objects.filter(student__in=students).values_list('assignment_id', flat=True))

    action_required_alerts = []
    recent_update_alerts = []

    for alert in all_potential_alerts:
        # Determine the action status
        is_actionable = False
        if alert.due_date:
            # Compare the .date() part of the due_date with today's date
            is_overdue = alert.due_date.date() < timezone.now().date()
        else:
            is_overdue = False
        if alert.alert_type == 'assessment_available' and alert.related_object_id not in completed_assessment_ids and not is_overdue:
            is_actionable = True
        elif alert.alert_type == 'exam_available' and alert.related_object_id not in completed_exam_ids and not is_overdue:
            is_actionable = True
        elif alert.alert_type == 'assignment_available' and alert.related_object_id not in completed_assignment_ids and not is_overdue:
            is_actionable = True
        
        # --- Prepare data for template ---
        # Clean up display text for 'alert_type'
        cleaned_display_type = alert.alert_type.replace('_', ' ').title()

        alert_data = {
            'instance': alert,
            'cleaned_display_type': cleaned_display_type,
            'is_overdue': is_overdue,
            'is_actionable': is_actionable,
        }

        if is_actionable:
            action_required_alerts.append(alert_data)
        else:
            recent_update_alerts.append(alert_data)

    student_ids = [s.user.id for s in students]

    # All relevant financial records
    financial_records_qs = FinancialRecord.objects.filter(student_id__in=student_ids, term=current_term).select_related('student')
    financial_records_dict = {fr.student_id: fr for fr in financial_records_qs}

    # All relevant results
    results_qs = Result.objects.filter(student_id__in=student_ids, term=current_term, is_approved=True)
    results_dict = {res.student_id: res for res in results_qs}

    # All relevant archived results
    archived_results_qs = Result.objects.filter(student_id__in=student_ids, term__in=archived_terms, is_approved=True, is_archived=True).select_related('term')
    archived_results_dict = defaultdict(list)
    for res in archived_results_qs:
        archived_results_dict[res.student_id].append(res)
    
    for student in students:

        student_id = student.user.id

        # Assignments data
        all_class_assignments = Assignment.objects.filter(
            class_assigned=student.current_class,
            active=True
        ).order_by('due_date')

        completed_assignment_ids = set(
            AssignmentSubmission.objects.filter(student=student, assignment__in=all_class_assignments, is_completed=True)
            .values_list('assignment_id', flat=True)
        )

        assignment_details_for_student = []
        total_relevant_assignments = 0
        completed_count = 0

        for assign in all_class_assignments:
            is_past_due = assign.due_date < timezone.now() if assign.due_date else False
            has_submitted = assign.id in completed_assignment_ids
            submission_instance = AssignmentSubmission.objects.filter(student=student, assignment=assign).first() # Get submission for result link

            # Only count assignments that are not past due OR have been submitted towards "total/pending"
            if not is_past_due or has_submitted:
                total_relevant_assignments +=1
                if has_submitted:
                    completed_count +=1
            
            assignment_details_for_student.append({
                'id': assign.id,
                'title': assign.title,
                'due_date': assign.due_date,
                'is_past_due': is_past_due,
                'has_submitted': has_submitted,
                'submission_id': submission_instance.id if submission_instance else None,
                })

        assignments_data[student.user.id]['details'] = assignment_details_for_student
        assignments_data[student.user.id]['total'] = total_relevant_assignments
        assignments_data[student.user.id]['completed'] = completed_count
        assignments_data[student.user.id]['pending'] = total_relevant_assignments - completed_count
        assignments_data[student.user.id]['completion_percentage'] = (completed_count / total_relevant_assignments * 100) if total_relevant_assignments > 0 else 0

        # Assessments and exams data
        all_class_assessments = Assessment.objects.filter(
            class_assigned=student.current_class,
            is_approved=True 
        ).order_by('due_date')

        submitted_assessment_ids = set(
            AssessmentSubmission.objects.filter(student=student, assessment__in=all_class_assessments)
            .values_list('assessment_id', flat=True)
        )
        
        assessment_list_for_student = []
        for assess in all_class_assessments:
            is_past_due = assess.due_date < timezone.now() if assess.due_date else False
            has_submitted = assess.id in submitted_assessment_ids
            submission_instance = AssessmentSubmission.objects.filter(student=student, assessment=assess).first()

            assessment_list_for_student.append({
                'id': assess.id,
                'title': assess.title,
                'due_date': assess.due_date,
                'is_past_due': is_past_due,
                'has_submitted': has_submitted,
                'submission_id': submission_instance.id if submission_instance else None,
                'is_graded': submission_instance.is_graded if submission_instance else False,
            })
        assessments_data[student.user.id] = assessment_list_for_student
        
        # === Exams Data ===
        all_class_exams = Exam.objects.filter(
            class_assigned=student.current_class,
            is_approved=True
        ).order_by('due_date')

        submitted_exam_ids = set(
            ExamSubmission.objects.filter(student=student, exam__in=all_class_exams)
            .values_list('exam_id', flat=True)
        )

        exam_list_for_student = []
        for ex in all_class_exams:
            is_past_due = ex.due_date < timezone.now() if ex.due_date else False
            has_submitted = ex.id in submitted_exam_ids
            submission_instance = ExamSubmission.objects.filter(student=student, exam=ex).first()

            exam_list_for_student.append({
                'id': ex.id,
                'title': ex.title,
                'due_date': ex.due_date,
                'is_past_due': is_past_due,
                'has_submitted': has_submitted,
                'submission_id': submission_instance.id if submission_instance else None,
                'is_graded': submission_instance.is_graded if submission_instance else False,
            })
        exams_data[student.user.id] = exam_list_for_student
    
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
        financial_record = financial_records_dict.get(student_id)
        if financial_record:
            financial_data[student_id] = {
                'total_fee': financial_record.total_fee,
                'total_discount': financial_record.total_discount,
                'total_paid': financial_record.total_paid,
                'outstanding_balance': financial_record.outstanding_balance,
                'can_access_results': financial_record.can_access_results,
                'is_fully_paid': financial_record.is_fully_paid,
                'has_waiver': financial_record.has_waiver,
                'payment_percentage': (financial_record.total_paid / financial_record.total_fee * 100) if financial_record.total_fee > 0 else (100 if financial_record.is_fully_paid else 0),
            }
        else: 
            financial_data[student_id] = {'can_access_results': False, 'outstanding_balance': 'N/A'} 

        # --- RESULT DATA ---
        result = results_dict.get(student_id)
        if result and financial_data[student_id]['can_access_results']: 
            result_data[student_id] = result
        else:
            result_data[student_id] = None
        
        # --- ARCHIVED RESULT DATA ---
        archived_results = archived_results_dict.get(student_id)
        if archived_results:
            archived_results_data[student_id] = archived_results

    context = {
        'guardian': guardian,
        'students': students,
        'teachers': teachers,
        'assignments_data': dict(assignments_data), 
        'assessments_data': dict(assessments_data),
        'exams_data': dict(exams_data),
        'messages_data': messages_data,
        'attendance_data': attendance_data,
        'attendance_logs': attendance_logs,
        'financial_data': financial_data,
        'result_data': result_data,
        'archived_results_data': archived_results_data,
        'notifications': notifications,
        'action_required_alerts': action_required_alerts,
        'recent_update_alerts': recent_update_alerts[:6],
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


