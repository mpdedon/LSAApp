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
from django.urls import reverse, reverse_lazy, NoReverseMatch
from django.db.models import Count, Sum, Q, F, Window, OuterRef, Subquery, IntegerField, Value, Prefetch
from django.db.models.functions import Rank, Coalesce
from collections import defaultdict
from decimal import Decimal
from core.models import CustomUser, Student, Teacher, Guardian, Assignment, Result, Attendance, Subject, Class, Payment, ClassSubjectAssignment
from core.models import Session, Term, Message, Assessment, Exam, Notification, AssignmentSubmission, AcademicAlert, TeacherAssignment
from core.models import FinancialRecord, StudentFeeRecord, AssessmentSubmission, ExamSubmission
from django.db.models import Sum
from django.views.generic.edit import FormView
from django.contrib import messages
from core.guardian.forms import GuardianRegistrationForm
from core.teacher.forms import TeacherRegistrationForm
from core.student.forms import MessageForm
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
    payment_count = Payment.objects.count() 

    # Fetch recent enrollments (Example using Student's class assignment change)
    recent_enrollments = Student.objects.select_related(
        'user', 'current_class', 'current_class__term__session' # Adjust relations
        ).order_by('-user__date_joined')[:5] # Example: recent student creations

    # Fetch data for charts (Example: Students per class)
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
        'student_counts_by_class_labels': student_counts_by_class_labels, 
        'student_counts_by_class_data': student_counts_by_class_data,   
    }

    return render(request, 'setup/dashboard.html', context) 


@login_required
@user_passes_test(lambda u: u.role == 'student', login_url='/login/')
def student_dashboard(request):
    try:
        student = Student.objects.select_related(
            'user', 'current_class'
        ).get(user=request.user)
    except Student.DoesNotExist:
        messages.error(request, "Your student profile could not be found.")
        return redirect('login')

    active_term = Term.objects.filter(is_active=True).select_related('session').first()
    if not student.current_class or not active_term:
        messages.warning(request, "Your class or the current academic term is not set. Please contact administration.")
        return render(request, 'student/student_dashboard.html', {'student': student})

    now = timezone.now()
    context = {'student': student, 'term': active_term, 'session': active_term.session, 'now': now,
               'school_level': student.current_class.school_level.lower()}
    

    # --- 1. GAMIFICATION & LEADERBOARD DATA ---
    assignment_subs_count = AssignmentSubmission.objects.filter(student=student).count()
    assessment_subs_count = AssessmentSubmission.objects.filter(student=student).count()
    exam_subs_count = ExamSubmission.objects.filter(student=student).count()

    # The total count is the sum of these individual counts.
    all_submissions_count = assignment_subs_count + assessment_subs_count + exam_subs_count
    
    # This was the debug print that showed "0 0 0 3" - let's make it more informative

    badge_tiers = [
        {'name': 'First Quest!', 'icon': 'bi-rocket-takeoff-fill', 'threshold': 1},
        {'name': 'Consistent Learner', 'icon': 'bi-star-fill', 'threshold': 5},
        {'name': 'Assignment Ace', 'icon': 'bi-award-fill', 'threshold': 10},
        {'name': 'Task Master', 'icon': 'bi-trophy-fill', 'threshold': 20},
    ]
    earned_badges = [badge for badge in badge_tiers if all_submissions_count >= badge['threshold']]
    next_badge = next((badge for badge in badge_tiers if all_submissions_count < badge['threshold']), None)

    context['gamification'] = {
        'submission_count': all_submissions_count,
        'earned_badges': earned_badges,
        'next_badge': next_badge,
        'progress_to_next_badge': (all_submissions_count / next_badge['threshold'] * 100) if next_badge and next_badge['threshold'] > 0 else 100,
    }

    # Leaderboard Data (for the active term)
    assignment_count_sub = AssignmentSubmission.objects.filter(student=OuterRef('pk'), assignment__term=active_term).values('student').annotate(c=Count('pk')).values('c')
    assessment_count_sub = AssessmentSubmission.objects.filter(student=OuterRef('pk'), assessment__term=active_term).values('student').annotate(c=Count('pk')).values('c')
    exam_count_sub = ExamSubmission.objects.filter(student=OuterRef('pk'), exam__term=active_term).values('student').annotate(c=Count('pk')).values('c')

    class_leaderboard_qs = Student.objects.filter(
        current_class=student.current_class, status='active'
    ).select_related('user').annotate(
        num_assignments=Coalesce(Subquery(assignment_count_sub, output_field=IntegerField()), Value(0)),
        num_assessments=Coalesce(Subquery(assessment_count_sub, output_field=IntegerField()), Value(0)),
        num_exams=Coalesce(Subquery(exam_count_sub, output_field=IntegerField()), Value(0)),
    ).annotate(
        term_submission_count=F('num_assignments') + F('num_assessments') + F('num_exams')
    ).annotate(
        rank=Window(expression=Rank(), order_by=F('term_submission_count').desc())
    ).order_by('rank', 'user__first_name')

    context['class_leaderboard'] = class_leaderboard_qs[:5]
    current_student_rank_info = next((s for s in class_leaderboard_qs if s.user.id == student.user.id), None)
    context['current_student_rank'] = current_student_rank_info.rank if current_student_rank_info else 'N/A'


    # --- 2. PREPARE "QUESTS" (UNIFIED TASK LIST) ---
    upcoming_quests = []
    # Fetch all submissions for this student at once
    submitted_assignment_ids = set(AssignmentSubmission.objects.filter(student=student).values_list('assignment_id', flat=True))
    submitted_assessment_ids = set(AssessmentSubmission.objects.filter(student=student).values_list('assessment_id', flat=True))
    submitted_exam_ids = set(ExamSubmission.objects.filter(student=student).values_list('exam_id', flat=True))

    # Get active tasks
    assignments = Assignment.objects.filter(class_assigned=student.current_class, term=active_term, active=True).select_related('subject')
    assessments = Assessment.objects.filter(class_assigned=student.current_class, term=active_term, is_approved=True).select_related('subject')
    exams = Exam.objects.filter(class_assigned=student.current_class, term=active_term, is_approved=True).select_related('subject')

    # Helper function to safely reverse URLs
    def safe_reverse(url_name, kwargs):
        try:
            return reverse(url_name, kwargs=kwargs)
        except NoReverseMatch:
            return "#" # Return a dead link as a fallback

    for task in assignments:
        if task.id not in submitted_assignment_ids:
            upcoming_quests.append({
                'type': 'assignment', 'obj': task, 'due_date': task.due_date,
                'submit_url': safe_reverse('submit_assignment', kwargs={'assignment_id': task.id})
            })

    for task in assessments:
        if task.id not in submitted_assessment_ids:
            upcoming_quests.append({
                'type': 'assessment', 'obj': task, 'due_date': task.due_date,
                'submit_url': safe_reverse('submit_assessment', kwargs={'assessment_id': task.id})
            })

    for task in exams:
        if task.id not in submitted_exam_ids:
            upcoming_quests.append({
                'type': 'exam', 'obj': task, 'due_date': task.due_date,
                'submit_url': safe_reverse('submit_exam', kwargs={'exam_id': task.id})
            })

    context['upcoming_quests'] = sorted(upcoming_quests, key=lambda q: q['due_date'])


    # --- 3. FETCH OTHER DASHBOARD DATA ---
    context['subjects'] = Subject.objects.filter(class_assignments__class_assigned=student.current_class, class_assignments__term=active_term).distinct()

    attendance_summary = Attendance.objects.filter(student=student, term=active_term).aggregate(
        total_days=Count('id'), present_days=Count('id', filter=Q(is_present=True))
    )
    total_days = attendance_summary.get('total_days', 0)
    present_days = attendance_summary.get('present_days', 0)
    context['attendance_data'] = {
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': total_days - present_days,
        'attendance_percentage': round((present_days / total_days * 100)) if total_days > 0 else 0
    }

    context['financial_data'] = FinancialRecord.objects.filter(student=student, term=active_term).first()
    context['result_data'] = Result.objects.filter(student=student, term=active_term, is_approved=True).first()
    context['archived_results_data'] = Result.objects.filter(student=student, term__is_active=False, is_approved=True, is_archived=True).select_related('term').order_by('-term__start_date')
    context['notifications'] = Notification.objects.filter(Q(audience='student') | Q(audience='all'), is_active=True).exclude(expiry_date__lt=now.date()).order_by('-created_at')

    context['class_teachers'] = Teacher.objects.filter(
        teacherassignment__class_assigned=student.current_class,
        teacherassignment__term=active_term
    ).select_related('user').distinct()

    received_messages = Message.objects.filter(
        recipient=request.user,
        parent_message__isnull=True 
    ).select_related('sender').order_by('-updated_at')
    
    unread_message_count = received_messages.filter(is_read=False).count()

    context['received_messages'] = received_messages
    
    # Received Messages
    context['unread_message_count'] = unread_message_count

    return render(request, 'student/student_dashboard.html', context)


# Teacher Dashboard
@login_required
@user_passes_test(lambda u: u.role == 'teacher')
def teacher_dashboard(request):
 
    try:
        teacher = get_object_or_404(Teacher, user=request.user)
    except Teacher.DoesNotExist:
        messages.error(request, "Your teacher profile could not be found.")
        return redirect('home')
    
    teacher = Teacher.objects.get(user=request.user)
    
    #guardians = set(student.student_guardian for student in students if student.student_guardian is not None)
   
    now = timezone.now()
    active_term = Term.objects.filter(is_active=True).select_related('session').first()
    # Calculate weeks in the term
    weeks = active_term.get_term_weeks
    
    teacher_assigned_classes_qs = teacher.assigned_classes().order_by('name')
    form_teacher_classes_qs = teacher.current_classes().order_by('name')
    subjects_taught_qs = teacher.subjects_taught()
    
    # --- CONTEXT FOR: Overview Tab ---
    student_count = Student.objects.filter(current_class__in=teacher_assigned_classes_qs, status='active').count()
    subject_count = subjects_taught_qs.count()
    
    upcoming_tasks = []
    assignments = Assignment.objects.filter(teacher=teacher, due_date__gte=now, active=True, term=active_term).select_related('subject', 'class_assigned').order_by('due_date')[:3]
    for item in assignments: upcoming_tasks.append({'type': 'Assignment', 'obj': item})
    
    assessments = Assessment.objects.filter(created_by=request.user, due_date__gte=now, is_approved=True, term=active_term).select_related('subject', 'class_assigned').order_by('due_date')[:3]
    for item in assessments: upcoming_tasks.append({'type': 'Assessment', 'obj': item})

    exams = Exam.objects.filter(created_by=request.user, due_date__gte=now, is_approved=True, term=active_term).select_related('subject', 'class_assigned').order_by('due_date')[:3]
    for item in exams: upcoming_tasks.append({'type': 'Exam', 'obj': item})
    
    upcoming_tasks.sort(key=lambda x: x['obj'].due_date)

    pending_submissions = AssessmentSubmission.objects.filter(
        assessment__created_by=request.user,
        requires_manual_review=True, is_graded=False
    ).select_related('student__user', 'assessment').order_by('submitted_at')[:5]
    
    notifications = Notification.objects.filter(
        Q(audience='teacher') | Q(audience='all'),
        is_active=True, expiry_date__gte=now.date()
    ).order_by('-created_at')[:5]

    # --- CONTEXT FOR: My Classes Tab & Non-Academic Grade Entry ---
    students_by_class_dict = {}
    if form_teacher_classes_qs.exists():
        all_students_in_form_classes_qs = Student.objects.filter(
            current_class__in=form_teacher_classes_qs, status='active'
        ).select_related('user', 'student_guardian__user').order_by('user__last_name', 'user__first_name')
        
        if active_term:
            student_results_for_term = Result.objects.filter(student__in=all_students_in_form_classes_qs, term=active_term)
            results_map = {result.student_id: result for result in student_results_for_term}
            for student in all_students_in_form_classes_qs:
                student.result_for_term = results_map.get(student.pk, Result(student=student, term=active_term))
        
        for student in all_students_in_form_classes_qs:
            if student.current_class not in students_by_class_dict:
                students_by_class_dict[student.current_class] = []
            students_by_class_dict[student.current_class].append(student)

    # --- CONTEXT FOR: Manage Tasks Tab ---
    all_assignments = Assignment.objects.filter(teacher=teacher).order_by('-created_at')
    all_assessments = Assessment.objects.filter(created_by=request.user).order_by('-created_at')
    all_exams = Exam.objects.filter(created_by=request.user).order_by('-created_at')
    
    # --- CONTEXT FOR: Leaderboard & Broadsheet Tabs ---
    form_teacher_term_ids = TeacherAssignment.objects.filter(teacher=teacher).values_list('term_id', flat=True)
    subjects_taught_by_teacher = subjects_taught_qs
    subject_teacher_term_ids = ClassSubjectAssignment.objects.filter(subject__in=subjects_taught_by_teacher).values_list('term_id', flat=True)
    all_involved_term_ids = set(form_teacher_term_ids) | set(subject_teacher_term_ids)
    selectable_terms = Term.objects.filter(id__in=all_involved_term_ids).select_related('session').distinct().order_by('-start_date')
    all_sessions = Session.objects.filter(terms__in=selectable_terms).distinct().order_by('-start_date')
    
    selected_term_id = request.GET.get('term_id')
    display_term = None
    if selected_term_id and selected_term_id.isdigit():
        display_term = selectable_terms.filter(pk=selected_term_id).first()
    if not display_term:
        display_term = active_term if active_term in selectable_terms else selectable_terms.first()

    leaderboard_data = {}
    if display_term:
        for class_instance in teacher_assigned_classes_qs:
            # Subqueries for counting submissions
            assignment_count_sub = AssignmentSubmission.objects.filter(student=OuterRef('pk'), assignment__term=display_term).values('student').annotate(c=Count('pk')).values('c')
            assessment_count_sub = AssessmentSubmission.objects.filter(student=OuterRef('pk'), assessment__term=display_term).values('student').annotate(c=Count('pk')).values('c')
            exam_count_sub = ExamSubmission.objects.filter(student=OuterRef('pk'), exam__term=display_term).values('student').annotate(c=Count('pk')).values('c')
            class_leaderboard_qs = Student.objects.filter(current_class=class_instance, status='active').select_related('user').annotate(
                num_assignments=Coalesce(Subquery(assignment_count_sub, output_field=IntegerField()), Value(0)),
                num_assessments=Coalesce(Subquery(assessment_count_sub, output_field=IntegerField()), Value(0)),
                num_exams=Coalesce(Subquery(exam_count_sub, output_field=IntegerField()), Value(0)),
            ).annotate(term_submission_count=F('num_assignments') + F('num_assessments') + F('num_exams')) \
             .annotate(rank=Window(expression=Rank(), order_by=F('term_submission_count').desc())) \
             .order_by('rank', 'user__last_name', 'user__first_name')
            leaderboard_data[class_instance.id] = {'class_name': class_instance.name, 'top_students': class_leaderboard_qs[:5]}
    
    received_messages = Message.objects.filter(recipient=request.user).select_related('sender', 'student_context__user').order_by('-sent_at')

    notifications = Notification.objects.filter(Q(audience='teacher') | Q(audience='all'), is_active=True, expiry_date__gte=timezone.now().date()).order_by('-created_at')

    context = {        
        # Overview Tab
        'teacher': teacher,
        'student_count': student_count,
        'subject_count': subject_count,
        'upcoming_tasks': upcoming_tasks,
        'pending_submissions': pending_submissions,
        'notifications': notifications,
        'form_teacher_classes_count': form_teacher_classes_qs.count(),

        # My Classes Tab
        'students_by_class': students_by_class_dict,
        'active_term': active_term,
        
        # Grade Entry Tab
        'teacher_assigned_classes': teacher_assigned_classes_qs,
        'teacher_subjects': teacher.assigned_subjects(),
        
        # Manage Tasks Tab
        'all_assignments': all_assignments,
        'all_assessments': all_assessments,
        'all_exams': all_exams,
        
        # Broadsheets Tab
        'all_sessions': all_sessions, 
        
        # Leaderboard Tab
        'leaderboard_data': leaderboard_data,
        'display_term': display_term,
        'selectable_terms': selectable_terms,
        'received_messages': received_messages,
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
    student_ids = students.values_list('pk', flat=True)

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
    
    # --- START OF CONTEXT FOR COMMUNICATION PANE ---
    received_messages = Message.objects.filter(
        Q(parent_message__isnull=True) &
        (
            Q(recipient=request.user) | 
            Q(recipient_id__in=student_ids) | 
            Q(sender=request.user) 
        )
    ).select_related(
        'sender', 
        'recipient', 
        'student_context__user'
    ).prefetch_related(
        Prefetch('replies', queryset=Message.objects.order_by('sent_at').select_related('sender', 'recipient'))
    ).distinct().order_by('-updated_at') 

    unread_message_count = Message.objects.filter(
        (
            Q(recipient=request.user) | 
            Q(recipient_id__in=student_ids)
        ),
        is_read=False
    ).count()
 
    students_classes = students.values_list('current_class_id', flat=True)
    guardian_teachers = Teacher.objects.filter(
        Q(teacherassignment__class_assigned_id__in=students_classes) |
        Q(subjectassignment__class_assigned_id__in=students_classes)
    ).select_related('user').distinct().order_by('user__last_name', 'user__first_name')

    context = {
        'guardian': guardian,
        'students': students,
        'teachers': teachers,
        'guardian_teachers': guardian_teachers,
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
        'received_messages': received_messages,
        'unread_message_count': unread_message_count,
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


