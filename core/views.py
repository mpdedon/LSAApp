import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.urls import reverse, reverse_lazy
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum, Q, F, Window, OuterRef, Subquery, IntegerField, Value, Prefetch, Max
from django.db.models.functions import Rank, Coalesce
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, TemplateView, FormView
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest, JsonResponse, Http404
from django.core.mail import send_mail, BadHeaderError
from django.shortcuts import HttpResponse
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from core.models import Session, Term, CustomUser, Student, Teacher, Guardian, Notification
from core.models import Class, Subject, FeeAssignment, Enrollment, Payment, Assessment, Exam
from core.models import SubjectAssignment, TeacherAssignment, ClassSubjectAssignment
from core.models import SubjectResult, Result, StudentFeeRecord, FinancialRecord, Message
from core.models import OnlineQuestion, AssignmentSubmission, AssessmentSubmission, ExamSubmission, SessionalResult, CumulativeRecord
from core.utils import get_current_term, get_next_term   
from core.forms import ClassSubjectAssignmentForm, NonAcademicSkillsForm, NotificationForm, ContactForm, MessageForm, ReplyForm
from core.session.forms import SessionForm
from core.term.forms import TermForm
from core.subject.forms import SubjectForm
from core.fee_assignment.forms import FeeAssignmentForm
from core.payment.forms import PaymentForm
from core.enrollment.forms import EnrollmentForm
from core.subject_assignment.forms import SubjectAssignmentForm
from core.teacher_assignment.forms import TeacherAssignmentForm
from core.assessment.forms import AssessmentForm, OnlineQuestionForm
from core.exams.forms import ExamForm
from core.models import Post, Category, Tag
from core.blog.forms import PostForm, CategoryForm, TagForm
import logging

logger = logging.getLogger(__name__)

# Create your views here.

def home(request):
    return render(request, 'home.html')

def about(request):
    return render(request, 'about.html')

def programs(request):
    return render(request, 'programs.html')

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            from_email = form.cleaned_data['email']
            phone = form.cleaned_data['phone_number']
            subject = form.cleaned_data['subject']
            message_content = form.cleaned_data['message']

            full_message = f"Message from: {name}\n"
            full_message += f"Email: {from_email}\n"
            if phone:
                full_message += f"Phone: {phone}\n\n"
            full_message += f"Subject: {subject}\n\n"
            full_message += f"Message:\n{message_content}"

            try:
                send_mail(
                    f"Contact Form Inquiry: {subject}", # Email subject
                    full_message, # Email body
                    from_email, # From (can be a fixed email from settings or user's email)
                    [settings.DEFAULT_FROM_EMAIL], # To (your school's inquiry email address)
                    # Use settings.EMAIL_HOST_USER or a dedicated inquiry email
                    # For testing, DEFAULT_FROM_EMAIL might be your console backend address
                    # In production, this should be your actual inquiry handling email.
                    fail_silently=False,
                )
                messages.success(request, "Your message has been sent successfully! We will get back to you soon.")
                return redirect('contact_us') # Redirect to same page (or a thank you page)
            except BadHeaderError:
                messages.error(request, "Invalid header found. Could not send email.")
            except Exception as e:
                messages.error(request, f"An error occurred while sending your message: {e}. Please try again later or contact us directly via phone.")
                # Log the error e
                print(f"Email sending error: {e}")

        else: # Form is invalid
            messages.error(request, "Please correct the errors below and try again.")
    else:
        form = ContactForm()

    context = {
        'form': form,
        'school_email': 'learnswift2020@gmail.com',
        'school_phone_1': '+234 703 485 8160',
        'school_phone_2': '+234 706 236 1134',
        'school_address_line1': '5 Bode Tobun Street, off Oniwaya Road,',
        'school_address_line2': 'Agege, Lagos, Nigeria',
    }
    return render(request, 'contact_us.html', context)

# core/views.py
def custom_404(request, exception):
    return render(request, '404.html', status=404)

def custom_500(request):
    return render(request, '500.html', status=500)

def custom_403(request, exception):
    return render(request, '403.html', status=403)

def custom_400(request, exception):
    return render(request, '400.html', status=400)

# Base Admin Privilege Mixin
class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser
    
class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = 'setup/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Analytics data
        context['student_count'] = Student.objects.count()
        context['teacher_count'] = Teacher.objects.count()
        context['guardian_count'] = Guardian.objects.count()
        context['class_count'] = Class.objects.count()
        context['session_count'] = Session.objects.count()
        context['term_count'] = Term.objects.count()
        context['subject_count'] = Subject.objects.count()
        context['payment_count'] = Payment.objects.count()
        context['recent_enrollments'] = Enrollment.objects.order_by('-id')[:5]
        return context

class CreateNotificationView(AdminRequiredMixin, CreateView):
    template_name = 'setup/notification_form.html'

    def get(self, request):
        form = NotificationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = NotificationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notification created successfully!')
            send_notification_to_users(form.instance)
            return redirect('notification_list')  # Redirect to notification list or dashboard page
        return render(request, self.template_name, {'form': form})

def send_notification_to_users(notification):
    if notification.audience in ['all', 'guardian', 'teacher']:
        guardians = Guardian.objects.filter(groups__name='Guardians')
        for guardian in guardians:
            send_mail(
                notification.title,
                notification.message,
                'from@example.com',
                [guardian.email]
            )
    if notification.audience in ['all', 'student']:
        students = Student.objects.filter(groups__name='Students')
        for student in students:
            send_mail(
                notification.title,
                notification.message,
                'from@example.com',
                [student.email]
            )
    if notification.audience in ['all', 'teacher']:
        teachers = Teacher.objects.filter(groups__name='Teachers')
        for teacher in teachers:
            send_mail(
                notification.title,
                notification.message,
                'admin@localhost',
                [teacher.email]
            )


class NotificationListView(ListView):
    template_name = 'setup/notification_list.html'

    def get(self, request):
        # Fetch all active, non-expired notifications
        notifications = Notification.objects.filter(is_active=True)
        current_date = timezone.now().date()  # Get current date
        notifications = notifications.filter(
            Q(expiry_date__gte=current_date) | Q(expiry_date__isnull=True)
        )

        # Add a "new" flag to notifications created within the last day
        for notification in notifications:
            notification.is_new = notification.created_at.date() >= current_date - timedelta(days=1)

        # Initialize the notification form
        form = NotificationForm()

        return render(request, self.template_name, {
            'notifications': notifications,
            'form': form,
        })

    def post(self, request):
        # Handle form submission to create a notification
        form = NotificationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notification created successfully!')
            return redirect('notification_list')
        return render(request, self.template_name, {
            'form': form,
            'notifications': Notification.objects.filter(is_active=True),
        })

# Session Management
class SessionListView(AdminRequiredMixin, ListView):
    template_name = 'setup/session_list.html'

    def get(self, request):
        sessions = Session.objects.all()
        return render(request, self.template_name, {'sessions': sessions})

class SessionDetailView(AdminRequiredMixin, DetailView):
    template_name = 'setup/session_detail.html'

    def get(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        return render(request, self.template_name, {'session': session})

class SessionCreateView(AdminRequiredMixin, CreateView):
    template_name = 'setup/session_form.html'

    def get(self, request):
        form = SessionForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = SessionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('session_list')
        return render(request, self.template_name, {'form': form})

class SessionUpdateView(AdminRequiredMixin, UpdateView):
    template_name = 'setup/session_form.html'

    def get(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        form = SessionForm(instance=session)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            return redirect('session_list')
        return render(request, self.template_name, {'form': form})

class SessionDeleteView(AdminRequiredMixin, DeleteView):
    template_name = 'setup/session_confirm_delete.html'

    def get(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        return render(request, self.template_name, {'session': session})

    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        session.delete()
        return redirect('session_list')

# Term Management
class TermListView(AdminRequiredMixin, ListView):
    template_name = 'setup/term_list.html'

    def get(self, request):
        terms = Term.objects.all()
        return render(request, self.template_name, {'terms': terms})

class TermDetailView(AdminRequiredMixin, DetailView):
    template_name = 'setup/term_detail.html'

    def get(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        return render(request, self.template_name, {'term': term})

class TermCreateView(AdminRequiredMixin, CreateView):
    template_name = 'setup/term_form.html'

    def get(self, request):
        form = TermForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = TermForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('term_list')
        return render(request, self.template_name, {'form': form})

class TermUpdateView(AdminRequiredMixin, UpdateView):
    template_name = 'setup/term_form.html'

    def get(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        form = TermForm(instance=term)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        form = TermForm(request.POST, instance=term)
        if form.is_valid():
            form.save()
            return redirect('term_list')
        return render(request, self.template_name, {'form': form})

def admin_required(login_url=None):
    return user_passes_test(lambda u: u.is_superuser, login_url=login_url)

@admin_required(login_url='/login/') # Protect the view
def activate_term_view(request, pk):
    """Activates the selected term and deactivates others in the same session."""
    term_to_activate = get_object_or_404(Term, pk=pk)
    if term_to_activate.is_active:
        messages.info(request, f"{term_to_activate} is already active.")
    else:
        try:
            # Use the model's activate method which now handles the logic
            term_to_activate.activate()
            messages.success(request, f"{term_to_activate} has been activated.")
        except Exception as e:
            # Catch potential errors during save/update
            messages.error(request, f"An error occurred while activating the term: {e}")

    return redirect('term_list') 

class TermDeleteView(AdminRequiredMixin, DeleteView):
    template_name = 'term/term_confirm_delete.html'

    def get(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        return render(request, self.template_name, {'term': term})

    def post(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        term.delete()
        return redirect('term_list')

# Student Record Management
class StudentListView(AdminRequiredMixin, ListView):
    model = Student
    template_name = 'student/student_list.html'

# Teacher Record Management
class TeacherListView(AdminRequiredMixin, ListView):
    model = Teacher
    template_name = 'teacher/teacher_list.html'
    
# Guardian Record Management
class GuardianListView(AdminRequiredMixin, ListView):
    model = Guardian
    template_name = 'guardian/guardian_list.html'

# Class Record Management
class ClassListView(AdminRequiredMixin, ListView):
    model = Class
    template_name = 'class/class_list'

# Subject Record Management
class SubjectListView(AdminRequiredMixin, ListView):
    model = Subject
    template_name = 'subject/subject_list'

# Promoting Students
class PromoteStudentView(AdminRequiredMixin, ListView):
    model = Student
    template_name = 'setup/promote_students.html'
    
    def post(self, request, *args, **kwargs):
        # Logic for promoting students
        return redirect('student/student_list')

# Subject Record Management
class SubjectListView(AdminRequiredMixin, ListView):
    template_name = 'subject/subject_list.html'

    def get(self, request):
        subjects = Subject.objects.all()
        return render(request, self.template_name, {'subjects': subjects})

class SubjectDetailView(AdminRequiredMixin, DetailView):
    template_name = 'subject/subject_detail.html'

    def get(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        return render(request, self.template_name, {'subject': subject})

class SubjectCreateView(AdminRequiredMixin, CreateView):
    template_name = 'subject/subject_form.html'

    def get(self, request):
        form = SubjectForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('subject_list')
        else:
            pass
        return render(request, self.template_name, {'form': form})

class SubjectUpdateView(AdminRequiredMixin, UpdateView):
    template_name = 'subject/subject_form.html'

    def get(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        form = SubjectForm(instance=subject)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            return redirect('subject_list')
        return render(request, self.template_name, {'form': form})

class SubjectDeleteView(AdminRequiredMixin, DeleteView):
    template_name = 'subject/subject_confirm_delete.html'

    def get(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        return render(request, self.template_name, {'subject': subject})

    def post(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        subject.delete()
        return redirect('subject_list')

# Student Enrollment
def StudentClassEnrollmentView(request):
    if request.method == 'POST':
        form = EnrollmentForm(request.POST)
        if form.is_valid():
            student = form.cleaned_data['student']
            class_enrolled = form.cleaned_data['class_enrolled']
            
            try:
                # Enroll the student into the class
                student.current_class = class_enrolled
                student.save()
                
                # Add student to the class
                class_enrolled.students.add(student)
                messages.success(request, f"{student} successfully enrolled in {class_enrolled.name}!")
                return redirect('student_list')
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            messages.error(request, "Invalid data submitted. Please correct the errors below.")
    else:
        form = EnrollmentForm()
    
    return render(request, 'setup/enrol_student.html', {'form': form})

def StudentEnrollmentsView(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    enrollments = student.enrollments.all()
    return render(request, 'setup/view_enrollments.html', {'student': student, 'enrollments': enrollments})


@require_POST # This is crucial for safety. Only allows form submissions.
@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff) # Protect this action
def unenroll_student(request, student_id, class_id):
    """
    Sets a student's 'current_class' to None.
    This effectively "un-enrolls" them from their current class.
    """
    student = get_object_or_404(Student, pk=student_id)
    class_obj = get_object_or_404(Class, pk=class_id)

    # Check that the student is actually in the class we think they are in
    if student.current_class == class_obj:
        # Update the history before changing the class
        student.update_history('Unenrolled', from_class=class_obj, to_class=None)
        
        # Set the current_class to None. This does not delete the student.
        student.current_class = None
        student.save()
        messages.success(request, f"Successfully unenrolled {student.user.get_full_name()} from {class_obj.name}.")
    else:
        messages.warning(request, f"{student.user.get_full_name()} was not enrolled in {class_obj.name}.")

    # Redirect back to the class detail page
    # Make sure your class detail URL is named 'class_detail'
    return redirect('class_detail', pk=class_id)

# View for assigning teachers to classes

def AssignTeacherView(request): 
    error_message = None  # Initialize error message

    if request.method == 'POST':
        form = TeacherAssignmentForm(request.POST)
        if form.is_valid():
            # Check if the combination of class_assigned, teacher, session, and term already exists
            class_assigned = form.cleaned_data['class_assigned']
            teacher = form.cleaned_data['teacher']
            session = form.cleaned_data['session']
            term = form.cleaned_data['term']
            is_form_teacher = form.cleaned_data['is_form_teacher']

            # Check for duplicate record
            if TeacherAssignment.objects.filter(class_assigned=class_assigned, teacher=teacher, session=session, term=term, is_form_teacher=is_form_teacher).exists():
                error_message = "This teacher is already assigned to this class for the selected session and term."
            else:
                try:
                    form.save()
                    return redirect('teacher_assignment_list')  # Redirect on successful save
                except IntegrityError as e:
                    error_message = f"A unique constraint error occurred: {str(e)}"
        else:
            print(form.errors)  

    else:
        form = TeacherAssignmentForm()

    context = {
        'form': form,
        'error_message': error_message,
    }

    return render(request, 'setup/assign_teacher.html', context)

class TeacherAssignmentListView(AdminRequiredMixin, ListView):
    model = TeacherAssignment
    template_name = 'teacher_assignment/teacher_assignment_list.html'
    context_object_name = 'teacher_assignments'
    paginate_by = 25

    def get_queryset(self):
        return TeacherAssignment.objects.select_related(
            'class_assigned',
            'teacher__user',
            'session',
            'term'
        ).order_by( 
            'session__start_date',  
            'term__order',          
            'term_id', 
            'class_assigned__name',
            'teacher__user__last_name',
            'teacher__user__first_name'  
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            current_term = Term.get_current_term()
            next_term = Term.get_next_term(current_term) # Pass current_term instance
        except Exception as e:
            current_term = None
            next_term = None
            messages.error(self.request, "Could not determine current/next term information.")

        context['current_term'] = current_term
        context['next_term'] = next_term
        context['show_rollover_button'] = False

        # Check if basic conditions are met for rollover
        if current_term and next_term and current_term.session and next_term.session:
            try:
                assignments_in_next_term_count = TeacherAssignment.objects.filter(
                    session=next_term.session, term=next_term
                ).count()

                if assignments_in_next_term_count == 0:
                    # CONDITION: Assignments exist in CURRENT term
                    current_term_has_assignments = TeacherAssignment.objects.filter(
                        session=current_term.session, term=current_term
                    ).exists()

                    if current_term_has_assignments:
                        context['show_rollover_button'] = True
                    else:
                        print("DEBUG: [Condition 5] FAILED (Current term has NO assignments)")
                else:
                    print(f"DEBUG: [Condition 4] FAILED (Next term is NOT empty, count={assignments_in_next_term_count})")
            except Exception as e:
                print(f"DEBUG: EXCEPTION checking assignments: {e}")
        else:
            print("DEBUG: Basic conditions FAILED (current_term, next_term, or their sessions missing/invalid)")

        print(f"DEBUG: Final context['show_rollover_button'] = {context['show_rollover_button']}")
        return context

class TeacherAssignmentRolloverView(AdminRequiredMixin, ListView):

    def post(self, request, *args, **kwargs):
        current_term = Term.get_current_term()
        next_term = Term.get_next_term(current_term)

        if not current_term or not next_term:
            messages.error(request, "Cannot determine current or next term for rollover.")
            return redirect('teacher_assignment_list') 

        if TeacherAssignment.objects.filter(session=next_term.session, term=next_term).exists():
             messages.warning(request, f"Assignments already exist for {next_term}. Rollover cancelled.")
             return redirect('teacher_assignment_list')

        assignments_to_copy = TeacherAssignment.objects.filter(
            session=current_term.session, term=current_term
        )

        if not assignments_to_copy.exists():
             messages.info(request, f"No assignments found in {current_term} to roll over.")
             return redirect('teacher_assignment_list')

        new_assignments = []
        for assignment in assignments_to_copy:
            new_assignments.append(
                TeacherAssignment(
                    class_assigned=assignment.class_assigned,
                    teacher=assignment.teacher,
                    session=next_term.session, 
                    term=next_term,
                    is_form_teacher=assignment.is_form_teacher
                )
            )

        try:
            # Requires PostgreSQL, SQLite >= 3.24, MySQL >= 8.0.19
            with transaction.atomic():
                TeacherAssignment.objects.bulk_create(new_assignments, ignore_conflicts=True)
            messages.success(request, f"Successfully rolled over {len(new_assignments)} assignments from {current_term} to {next_term}.")
        except Exception as e:
            messages.error(request, f"An error occurred during rollover: {e}")

        return redirect('teacher_assignment_list')

class TeacherAssignmentDetailView(AdminRequiredMixin, DetailView):
    template_name = 'teacher_assignment/teacher_assignment_detail.html'

    def get(self, request, pk):
        teacher_assignment = get_object_or_404(TeacherAssignment, pk=pk)
        return render(request, self.template_name, {'teacher_assignment': teacher_assignment})

class TeacherAssignmentUpdateView(AdminRequiredMixin, UpdateView):
    template_name = 'teacher_assignment/teacher_assignment_form.html'

    def get(self, request, pk):
        teacher_assignment = get_object_or_404(TeacherAssignment, pk=pk)
        form = TeacherAssignmentForm(instance=teacher_assignment)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        teacher_assignment = get_object_or_404(TeacherAssignment, pk=pk)
        form = TeacherAssignmentForm(request.POST, instance=teacher_assignment)
        if form.is_valid():
            form.save()
            return redirect('teacher_assignment_list')
        return render(request, self.template_name, {'form': form})

class TeacherAssignmentDeleteView(AdminRequiredMixin, DeleteView):
    template_name = 'teacher_assignment/teacher_assignment_confirm_delete.html'

    def get(self, request, pk):
        teacher_assignment = get_object_or_404(TeacherAssignment, pk=pk)
        return render(request, self.template_name, {'teacher_assignment': teacher_assignment})

    def post(self, request, pk):
        teacher_assignment = get_object_or_404(TeacherAssignment, pk=pk)
        teacher_assignment.delete()
        return redirect('teacher_assignment_list')

# View for assigning subjects to teachers
def AssignSubjectView(request):
    if request.method == 'POST':
        subject_assignment_form = SubjectAssignmentForm(request.POST)
        if subject_assignment_form.is_valid():
            subject_assignment_form.save()
            return redirect('subject_assignment_list')  
    else:
        subject_assignment_form = SubjectAssignmentForm()

    context = {
        'subject_assignment_form': subject_assignment_form,
    }

    return render(request, 'setup/assign_subject.html', context)

class SubjectAssignmentListView(ListView):
    template_name = 'subject_assignment/subject_assignment_list.html'

    def get(self, request, *args, **kwargs):
        search_query = request.GET.get('q', '').strip()

        subject_assignments = SubjectAssignment.objects.all()

        if search_query:
            subject_assignments = subject_assignments.filter(
                Q(teacher__user__first_name__icontains=search_query) |
                Q(teacher__user__last_name__icontains=search_query) |
                Q(subject__name__icontains=search_query) |
                Q(class_assigned__name__icontains=search_query)
            )

        paginator = Paginator(subject_assignments, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'search_query': search_query,
        })
    
class AssignClassSubjectView(AdminRequiredMixin, CreateView):
    form_class = ClassSubjectAssignmentForm 
    template_name = 'setup/assign_class_subjects.html' 

    def get(self, request, pk): # pk is likely the Class ID
        class_instance = get_object_or_404(Class, pk=pk)

        # Use the robust model method to get current term
        active_term = Term.get_current_term()
        if not active_term:
            messages.error(request, "No active term found. Cannot assign subjects.")
            # Decide how to handle this - maybe redirect or show an error form state
            active_session = Session.get_current_session() # Try to get session at least
        else:
            active_session = active_term.session

        assigned_subject_ids = []
        if active_session and active_term:
             assigned_subject_ids = ClassSubjectAssignment.objects.filter(
                 class_assigned=class_instance,
                 session=active_session, # Use determined active session
                 term=active_term      # Use determined active term
             ).values_list('subject_id', flat=True)

        form = self.form_class(initial={
            'subjects': list(assigned_subject_ids),
            'session': active_session, # Pass the determined active session
            'term': active_term,       # Pass the determined active term
        })
        # Restrict form choices if needed
        if active_session:
            form.fields['session'].queryset = Session.objects.filter(pk=active_session.pk)
            form.fields['session'].initial = active_session
        if active_term:
            form.fields['term'].queryset = Term.objects.filter(pk=active_term.pk)
            form.fields['term'].initial = active_term


        existing_assignments = class_instance.subject_assignments.filter(
             session=active_session, term=active_term # Show only relevant assignments
        ).select_related('subject').order_by('subject__name')

        context = {
            'form': form,
            'class_instance': class_instance,
            'existing_assignments': existing_assignments,
            'current_session': active_session, # Pass to template for display
            'current_term': active_term,       # Pass to template for display
            'is_update': bool(assigned_subject_ids), # True if already has assignments for current
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        class_instance = get_object_or_404(Class, pk=pk)
        form = self.form_class(request.POST)

        if form.is_valid():
            selected_subjects = form.cleaned_data['subjects']
            session = form.cleaned_data['session']
            term = form.cleaned_data['term']

            # Use transaction for atomic update
            with transaction.atomic():
                # Remove assignments for subjects *not* selected in this term/session
                ClassSubjectAssignment.objects.filter(
                    class_assigned=class_instance, session=session, term=term
                ).exclude(subject__in=selected_subjects).delete()

                # Add or update assignments for selected subjects
                assignments_to_create = []
                existing_subject_ids = set(ClassSubjectAssignment.objects.filter(
                     class_assigned=class_instance, session=session, term=term
                ).values_list('subject_id', flat=True))

                for subject in selected_subjects:
                    # Only create if it doesn't already exist for this combo
                    if subject.id not in existing_subject_ids:
                         assignments_to_create.append(
                             ClassSubjectAssignment(
                                class_assigned=class_instance,
                                subject=subject,
                                session=session,
                                term=term
                            )
                         )
                if assignments_to_create:
                    ClassSubjectAssignment.objects.bulk_create(assignments_to_create)

            messages.success(request, f"Subject assignments updated successfully for {class_instance.name}, {term.name}, {session}.")
            return redirect('class_detail', pk=class_instance.pk) # Redirect back to detail view
        else:
             # Re-fetch existing assignments if form is invalid
             existing_assignments = class_instance.subject_assignments.select_related(
                'subject', 'session', 'term'
             ).order_by('session__start_date', 'term__order', 'subject__name')
             messages.error(request, "Please correct the errors below.")
             context = {
                'form': form,
                'class_instance': class_instance,
                'existing_assignments': existing_assignments,
                 'is_update': False,
             }
             return render(request, self.template_name, context)


def class_subjects(request):
    assignments = ClassSubjectAssignment.objects.select_related(
        'class_assigned', 'subject', 'session', 'term'
    ).order_by('term__session__start_date', 'term__order', 'class_assigned__name', 'subject__name')

    # Rollover Button Logic using new model methods
    current_term = Term.get_current_term()
    next_term = Term.get_next_term(current_term) if current_term else None
    show_rollover_button = False

    if current_term and next_term and current_term.session and next_term.session:
        next_term_is_empty = not ClassSubjectAssignment.objects.filter(
            session=next_term.session, term=next_term
        ).exists()
        if next_term_is_empty:
            current_term_has_assignments = ClassSubjectAssignment.objects.filter(
                session=current_term.session, term=current_term
            ).exists()
            if current_term_has_assignments:
                show_rollover_button = True
    # ... (rest of your context and render)
    context = {
        'assignments': assignments,
        'current_term': current_term,
        'next_term': next_term,
        'show_rollover_button': show_rollover_button,
    }
    return render(request, 'setup/class_subjects.html', context)

# --- NEW Rollover View ---
class ClassSubjectRolloverView(AdminRequiredMixin, ListView):

    def post(self, request, *args, **kwargs):
        current_term = Term.get_current_term()
        next_term = Term.get_next_term(current_term)

        if not current_term or not next_term:
            messages.error(request, "Cannot determine current or next term for rollover.")
            return redirect('class_subjects') # Redirect to the accordion list

        # Ensure terms and sessions are valid before proceeding
        if not hasattr(current_term, 'session') or not current_term.session or \
           not hasattr(next_term, 'session') or not next_term.session:
            messages.error(request, "Term or session data is incomplete for rollover.")
            return redirect('class_subjects')

        # Double-check: Only proceed if the next term is empty
        if ClassSubjectAssignment.objects.filter(session=next_term.session, term=next_term).exists():
             messages.warning(request, f"Assignments already exist for {next_term}. Rollover cancelled.")
             return redirect('class_subjects')

        assignments_to_copy = ClassSubjectAssignment.objects.filter(
            session=current_term.session, term=current_term
        )

        if not assignments_to_copy.exists():
             messages.info(request, f"No subject assignments found in {current_term} to roll over.")
             return redirect('class_subjects')

        new_assignments = []
        for assignment in assignments_to_copy:
            new_assignments.append(
                ClassSubjectAssignment(
                    class_assigned=assignment.class_assigned,
                    subject=assignment.subject,
                    session=next_term.session, # Assign to the NEXT session/term
                    term=next_term,
                )
            )

        try:
            with transaction.atomic():
                created_assignments = ClassSubjectAssignment.objects.bulk_create(new_assignments, ignore_conflicts=True)
            messages.success(request, f"Successfully rolled over {len(created_assignments)} subject assignments from {current_term} to {next_term}.") # Count actual created
        except Exception as e:
            messages.error(request, f"An error occurred during rollover: {e}")

        return redirect('class_subjects')

class DeleteClassSubjectAssigmentView(DeleteView, AdminRequiredMixin):
    def post(self, request, pk):
        """Delete selected subjects for a class."""
        class_instance = get_object_or_404(Class, pk=pk)
        current_session = Session.objects.filter(is_active=True).first()
        current_term = Term.objects.filter(is_active=True).first()
        subject_ids_to_delete = request.POST.getlist('subject_ids')

        if not subject_ids_to_delete:
            return HttpResponseBadRequest("No subjects selected for deletion.")

        deleted_count, _ = ClassSubjectAssignment.objects.filter(
            class_assigned=class_instance,
            subject_id__in=subject_ids_to_delete,
            session=current_session,
            term=current_term
        ).delete()

        if deleted_count == 0:
            return HttpResponseBadRequest("No matching subjects found to delete.")

        return redirect(reverse('class_subjects'))


@login_required
def broadsheets(request):
    """Display a paginated list of available terms (latest first)"""
    terms = Term.objects.all().select_related('session').order_by('-start_date') 
    paginator = Paginator(terms, 10)  
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'setup/termly_broadsheets.html', {'page_obj': page_obj})

@login_required
def termly_broadsheet(request, term_id):
    term = get_object_or_404(Term.objects.select_related('session'), id=term_id)
    session = term.session

    # Check which classes these students belong to
    classes = Class.objects.filter(enrolled_students__result__term=term).distinct().order_by('order')

    broadsheets = [] 
    for class_obj in classes:
        # Get subjects assigned to this class for the given term and session
        subjects = Subject.objects.filter(
            class_assignments__class_assigned=class_obj,
            class_assignments__session=session,
            class_assignments__term=term
        ).distinct().order_by('name')

        # Get all students currently in this class
        students = Student.objects.filter(current_class=class_obj).order_by('user__last_name', 'user__first_name')

        results_data = []
        for student in students:
            result = Result.objects.filter(student=student, term=term).first()
            student_subject_results = {}
            total_score_sum = Decimal('0.0')
            gpa_points_sum = Decimal('0.0')
            subject_count = 0

            if result:
                # Get all SubjectResult entries for this student/term, but only for the subjects in this class
                subject_results_qs = result.subject_results.filter(subject__in=subjects)

                for sr in subject_results_qs:
                     # Check if any score has been entered to consider it 'active'
                     if (sr.continuous_assessment_1 is not None or
                         sr.continuous_assessment_2 is not None or
                         sr.continuous_assessment_3 is not None or
                         sr.assignment is not None or
                         sr.oral_test is not None or
                         sr.exam_score is not None):
                        
                        student_subject_results[sr.subject.id] = sr
                        total_score_sum += sr.total_score()
                        weight = Decimal(getattr(sr.subject, 'subject_weight', 1))
                        gpa_points_sum += Decimal(sr.calculate_grade_point()) * weight
                        subject_count += weight 

            # Calculate the GPA for this student based ONLY on the subjects found and summed above
            student_gpa = (gpa_points_sum / subject_count) if subject_count > 0 else Decimal('0.0')
            
            results_data.append({
                'student': student,
                'subject_results': student_subject_results,
                'gpa': student_gpa.quantize(Decimal('0.01')),
                'total_score': total_score_sum.quantize(Decimal('0.1')),
                'is_approved': result.is_approved if result else False,
            })
        
        # Sort students by the newly calculated total score and GPA
        results_data.sort(key=lambda x: (x['total_score'], x['gpa']), reverse=True)

        broadsheets.append({
            'class': class_obj,
            'subjects': subjects,
            'results_data': results_data,
            'is_approved': all(r['is_approved'] for r in results_data) if results_data else False, 
        })

    context = {
        'term': term,
        'session': session,
        'broadsheets': broadsheets, 
    }
    return render(request, 'setup/termly_broadsheet.html', context)


@login_required
def approve_termly_broadsheet(request, term_id, class_id):
    if request.method != "POST":
        return JsonResponse({'error': "Invalid request method."}, status=400)

    term = get_object_or_404(Term, id=term_id)
    class_obj = get_object_or_404(Class, id=class_id)
    
    updated_count = Result.objects.filter(
        student__current_class=class_obj, 
        term=term
    ).update(is_approved=True, is_published=True)

    messages.success(request, f"Termly broadsheet for {class_obj.name} ({term.name}) has been approved and published.")
    return JsonResponse({'message': 'Approval successful!', 'updated_count': updated_count})


@login_required
def archive_termly_broadsheet(request, term_id):
    term = get_object_or_404(Term, id=term_id)
    results = Result.objects.filter(term=term)

    if request.method == "POST":
        results.update(is_archived=True)
        return JsonResponse({'message': f"Broadsheet for {term.name} archived!"})

    return JsonResponse({'error': "Invalid request"}, status=400)


@user_passes_test(lambda u: u.is_superuser)
def sessional_broadsheets(request):
    sessions = Session.objects.all().order_by('-start_date')
    return render(request, 'setup/sessional_broadsheets.html', {'sessions': sessions})


@user_passes_test(lambda u: u.is_superuser)
def admin_sessional_broadsheet(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    terms_in_session = Term.objects.filter(session=session).order_by('start_date')

    if not terms_in_session.exists():
        messages.warning(request, f"No terms found for the {session.name} session.")
        return redirect('sessional_broadsheets') 

    classes_in_session = Class.objects.filter(
        enrolled_students__result__term__in=terms_in_session
    ).distinct().order_by('order') 

    sessional_broadsheets_data = []
    for class_obj in classes_in_session:
        print(f"\n  Processing Class: '{class_obj.name}'")
        subjects_in_class = Subject.objects.filter(
            class_assignments__class_assigned=class_obj,
            class_assignments__term__in=terms_in_session
        ).distinct().order_by('name')

        students_in_class = Student.objects.filter(
            result__term__in=terms_in_session, 
            result__student__current_class=class_obj 
        ).distinct().select_related('user').order_by('user__last_name', 'user__first_name')

        class_sessional_results_data = []

        sessional_results_for_class = SessionalResult.objects.filter(
            student__in=students_in_class,
            session=session
        )
        sessional_results_map = {res.student_id: res for res in sessional_results_for_class}
        
        for student in students_in_class:
            sessional_result = sessional_results_map.get(student.pk)
            
            if not sessional_result:
                sessional_result, _ = SessionalResult.objects.get_or_create(student=student, session=session)
                sessional_result.calculate_and_save_summary()
                sessional_result.refresh_from_db()
            
            student_data = {
                'student_obj': student,
                'sessional_gpa': sessional_result.sessional_gpa,
                'sessional_average': sessional_result.average_score,
                'is_approved': sessional_result.is_approved,
                'subject_rows': []
            }
          
            for subject in subjects_in_class:
                subject_summary = sessional_result.subject_summary_json.get(str(subject.id), {})
                term_scores = [subject_summary.get('term_scores', {}).get(f'term_{term.id}_score') for term in terms_in_session]
                student_data['subject_rows'].append({
                    'subject_name': subject.name, 'term_scores': term_scores,
                    'sessional_average': subject_summary.get('sessional_average')
                })
            class_sessional_results_data.append(student_data)
        
        class_sessional_results_data.sort(key=lambda x: x['sessional_gpa'] or Decimal('0.0'), reverse=True)

        is_approved_flag = all(res['is_approved'] for res in class_sessional_results_data) if class_sessional_results_data else False
        
        if is_approved_flag:
            status_text = "Approved & Published"
            status_class = "bg-success"
        else:
            status_text = "Pending Approval"
            status_class = "bg-warning text-dark"

        sessional_broadsheets_data.append({
            'class': class_obj, 'subjects': subjects_in_class,
            'sessional_results_data': class_sessional_results_data,
'           is_all_approved': is_approved_flag,
            'status_text': status_text,         
            'status_class': status_class,  
        })
    
    context = {
        'session': session,
        'terms_in_session': terms_in_session,
        'sessional_broadsheets_data': sessional_broadsheets_data,
    }
    return render(request, 'setup/admin_sessional_broadsheet.html', context)


@user_passes_test(lambda u: u.is_superuser)
def approve_sessional_broadsheet(request, session_id, class_id):
    if request.method != "POST":
        return JsonResponse({'error': "Invalid request method."}, status=400)
      
    session = get_object_or_404(Session, id=session_id)
    class_obj = get_object_or_404(Class, id=class_id)

    # Step 1: Find the students we are targeting.
    student_pks_to_update = Result.objects.filter(
        term__session=session,
        student__current_class=class_obj
    ).values_list('student__pk', flat=True).distinct()

    if not student_pks_to_update:
        message_text = f"No student results found for {class_obj.name} in {session.name} to approve."
        return JsonResponse({'message': message_text, 'updated_count': 0})
    
    # Step 2: Find the SessionalResult objects that match these criteria.
    updated_count = SessionalResult.objects.filter(
        student_id__in=student_pks_to_update, 
        session=session
    ).update(is_approved=True, is_published=True)
    
    if updated_count > 0:
        print(f"  - Triggering Cumulative GPA update for {len(student_pks_to_update)} students...")
        
        students_to_update_cgpa = Student.objects.filter(
            pk__in=student_pks_to_update
        ).select_related('cumulative_record')
        
        cgpa_updated_count = 0
        for student in students_to_update_cgpa:
            try:
                cumulative_record = student.cumulative_record
                cumulative_record.update_cumulative_gpa()
                cgpa_updated_count += 1
            except CumulativeRecord.DoesNotExist:
                new_cr = CumulativeRecord.objects.create(student=student)
                new_cr.update_cumulative_gpa()
                cgpa_updated_count += 1
                
        print(f"  - CGPA update method called for {cgpa_updated_count} students.")

        message_text = f"Sessional broadsheet for {class_obj.name} ({session.name}) has been approved and published for {updated_count} students."
        return JsonResponse({'message': message_text, 'updated_count': updated_count})
    else:
        message_text = f"No sessional results needed updating for {class_obj.name} ({session.name}). They may already be approved."
        return JsonResponse({'message': message_text, 'updated_count': 0})


@user_passes_test(lambda u: u.is_superuser)
def archive_sessional_broadsheet(request, session_id):

    session = get_object_or_404(Session, session_id)
    results = SubjectResult.objects.filter(session=session)

    if request.method == "POST":
        results.update(is_archived=True)
        return JsonResponse({'message': f"Broadsheet for {session.name} archived"})

    return JsonResponse({'error': "Invalid request."}, status=400)
    

# Fee Assignment Views

class FeeAssignmentListView(AdminRequiredMixin, ListView):
    model = FeeAssignment
    template_name = 'fee_assignment/fee_assignment_list.html'
    context_object_name = 'assignments'


class FeeAssignmentCreateView(AdminRequiredMixin, CreateView):
    model = FeeAssignment
    form_class = FeeAssignmentForm
    template_name = 'fee_assignment/create_fee_assignment.html'
    success_url = reverse_lazy('fee_assignment_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.assign_fees_to_students()  # Automatically assign to students in the class
        messages.success(self.request, 'Fee assignment created successfully and assigned to students.')
        return response

class FeeAssignmentUpdateView(AdminRequiredMixin, UpdateView):
    model = FeeAssignment
    form_class = FeeAssignmentForm
    template_name = 'fee_assignment/update_fee_assignment.html'
    success_url = reverse_lazy('fee_assignment_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.assign_fees_to_students()  # Update assignments if necessary
        messages.success(self.request, 'Fee assignment updated successfully.')
        return response

class FeeAssignmentDetailView(DetailView):
    model = FeeAssignment
    template_name = 'fee_assignment/fee_assignment_detail.html'
    context_object_name = 'assignment'

class FeeAssignmentDeleteView(AdminRequiredMixin, DeleteView):
    model = FeeAssignment
    template_name = 'fee_assignment/fee_assignment_delete.html'
    success_url = reverse_lazy('fee_assignment_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Fee assignment deleted successfully.')
        return super().delete(request, *args, **kwargs)

class StudentFeeRecordListView(AdminRequiredMixin, ListView):
    model = StudentFeeRecord
    template_name = 'fee_assignment/student_fee_record_list.html' # Use new template name
    context_object_name = 'all_records_grouped_by_class'
    # No pagination at the ListView level

    def get_active_term(self):
        # (Keep the existing get_active_term method from previous version)
        try:
            active_session = Session.objects.filter(is_active=True).first()
            if not active_session:
                 raise Session.DoesNotExist("No active session found.")
            # Adjust filter if multiple terms can be active per session (unlikely)
            active_term = Term.objects.filter(session=active_session, is_active=True).first()
            if not active_term:
                 raise Term.DoesNotExist(f"No active term found for session {active_session}.")
            return active_term
        except (Session.DoesNotExist, Term.DoesNotExist) as e:
            # Use specific request object if available, otherwise log
            logger.error(f"Configuration Error fetching active term: {e}") # Assuming logger is configured
            if hasattr(self, 'request'):
                 messages.error(self.request, f"Configuration Error: {e}")
            return None

    @transaction.atomic # Keep the transaction
    def sync_fee_records(self, active_term):
        """
        Ensure fee records exist for the active term.
        Pre-calculates net_fee for bulk_create.
        Manually ensures FinancialRecord consistency after bulk_create.
        Updates existing records via save() to trigger signals if amount changes.
        """
        if not active_term:
            return

        term_assignments = FeeAssignment.objects.filter(term=active_term).select_related('class_instance')
        if not term_assignments.exists():
            return 

        assignments_by_class_id = {fa.class_instance_id: fa for fa in term_assignments}

        # Use Student PK ('id') for clarity and robustness
        students_in_assigned_classes = Student.objects.filter(
            current_class_id__in=assignments_by_class_id.keys(),
            status='active' # Optional: Only sync for active students?
        ).values_list('user_id', 'current_class_id') # Get Student PK

        student_map = {s_id: c_id for s_id, c_id in students_in_assigned_classes}
        if not student_map:
            return # No students to process

        # Fetch existing SFRs for these specific students and term
        existing_records = StudentFeeRecord.objects.filter(
            term=active_term,
            student_id__in=student_map.keys()
        ).select_related('fee_assignment') # Select related assignment for comparison

        # Use Student PK for the map key
        existing_map = {record.student_id: record for record in existing_records}
        # Note: This assumes one fee record per student per term.

        records_to_create_instances = []
        records_to_update_pks = [] # Track PKs needing potential update via save()

        for student_id, class_id in student_map.items():
            # Find the relevant assignment for the student's class
            assignment = assignments_by_class_id.get(class_id)
            if not assignment: continue # Should not happen due to initial filter

            record = existing_map.get(student_id) # Check if record exists using Student PK

            if not record:
                # --- Prepare NEW record instance ---
                initial_amount = assignment.amount or Decimal('0.00')
                initial_discount = Decimal('0.00')
                initial_waiver = False

                # Calculate net_fee directly
                if initial_waiver:
                    calculated_net_fee = Decimal('0.00')
                else:
                    applied_discount = min(initial_amount, initial_discount)
                    calculated_net_fee = max(initial_amount - applied_discount, Decimal('0.00'))

                records_to_create_instances.append(
                    StudentFeeRecord(
                        student_id=student_id,
                        term=active_term,
                        fee_assignment=assignment,
                        amount=initial_amount,
                        discount=initial_discount,
                        waiver=initial_waiver,
                        net_fee=calculated_net_fee # Assign pre-calculated value
                    )
                )
            else:
                # --- Check EXISTING record for updates ---
                needs_save = False # Use save() to trigger signals if amount/assignment changes
                if record.fee_assignment_id != assignment.id:
                    record.fee_assignment = assignment
                    needs_save = True
                if record.amount != assignment.amount:
                    record.amount = assignment.amount
                    needs_save = True
                # Note: Discount/Waiver are user-set, don't override them here.
                # If amount changed, net_fee needs recalc *during save*.

                if needs_save:
                    # Don't use .update() here if signals are important for amount change
                    # Instead, call save() on the individual instance later
                    records_to_update_pks.append(record.pk)

        # --- Perform Database Operations ---
        created_records = []
        if records_to_create_instances:
            try:
                created_records = StudentFeeRecord.objects.bulk_create(records_to_create_instances)
                # messages.info(self.request, f"Created {len(created_records)} new fee records.") # Avoid messages in sync logic
            except IntegrityError as e:
                 # Handle potential unique constraint violations if sync runs concurrently (unlikely here)
                 pass

        # --- Update Existing Records Needing Save (Triggers Signals) ---
        if records_to_update_pks:
            records_needing_save = StudentFeeRecord.objects.filter(pk__in=records_to_update_pks)
            updated_count = 0
            for record in records_needing_save:
                 # Refetch assignment just in case (might be overkill)
                assignment = assignments_by_class_id.get(record.student.current_class_id)
                if assignment: # Check if assignment still exists for the class
                    record.fee_assignment = assignment
                    record.amount = assignment.amount
                    # The save method will calculate net_fee and trigger signals
                    record.save()
                    updated_count +=1
            print(f"Sync: Updated {updated_count} existing StudentFeeRecords via save().")

        # --- Manually Ensure FinancialRecord Consistency for BULK_CREATED records ---
        if created_records:
            print(f"Sync: Ensuring FinancialRecord consistency for {len(created_records)} bulk-created records.")
            for record in created_records:
                # Use get_or_create for FinancialRecord
                fin_record, fr_created = FinancialRecord.objects.get_or_create(
                    student_id=record.student_id,
                    term=record.term
                    # REMOVE 'defaults' dictionary completely here
                )

                # --- Explicitly set fields AFTER get_or_create ---
                # This ensures fields are updated whether the FR was created or just fetched.
                needs_fr_update = False
                if fin_record.total_fee != record.net_fee:
                    fin_record.total_fee = record.net_fee; needs_fr_update = True
                if fin_record.total_discount != record.discount:
                    fin_record.total_discount = record.discount; needs_fr_update = True
                if fin_record.has_waiver != record.waiver: # Now check against the SFR waiver
                    fin_record.has_waiver = record.waiver; needs_fr_update = True

                # If newly created, total_paid should be 0 initially
                if fr_created and fin_record.total_paid != Decimal('0.00'):
                    fin_record.total_paid = Decimal('0.00')
                    needs_fr_update = True
                # Note: We don't recalculate total_paid from payments here;

                # Always recalculate balance based on current values
                new_outstanding = max(fin_record.total_fee - fin_record.total_paid, Decimal('0.00'))
                if fin_record.outstanding_balance != new_outstanding:
                    fin_record.outstanding_balance = new_outstanding
                    needs_fr_update = True

                # Always update archived status
                term_is_inactive = not record.term.is_active
                if fin_record.archived != term_is_inactive:
                    fin_record.archived = term_is_inactive
                    needs_fr_update = True

                # Save only if necessary
                if needs_fr_update:
                    # Define all potentially updated fields
                    update_fields_list = [
                        'total_fee', 'total_discount',
                        'total_paid', 'outstanding_balance', 'archived'
                    ]
                    fin_record.save(update_fields=update_fields_list)

            print(f"Sync: FinancialRecord consistency check complete.")
    def get_queryset(self):
        """Fetch and group records by class based on filters."""
        # Get term and class from query params
        selected_term_id = self.request.GET.get('term_id')
        selected_class_id = self.request.GET.get('class_id')

        active_term = self.get_active_term() # Get active for default/sync trigger
        target_term = None

        # Determine the term to display
        if selected_term_id:
            try:
                target_term = Term.objects.select_related('session').get(pk=selected_term_id)
            except (Term.DoesNotExist, ValueError):
                messages.warning(self.request, "Invalid Term specified, showing active term.")
                target_term = active_term
        else:
            target_term = active_term # Default to active if not specified

        if not target_term:
            messages.error(self.request, "Cannot determine term to display records for.")
            return {} # Return empty dict

        # --- Run sync ONLY for the active term if needed ---
        # Syncing historical terms might be complex/undesirable on every load
        # Consider a separate sync mechanism if needed for old terms.
        if target_term == active_term:
             print(f"Running sync for ACTIVE term: {active_term}")
             self.sync_fee_records(active_term)
        else:
            print(f"Displaying records for INACTIVE term: {target_term}. Sync skipped.")


        # Base queryset filtered by the target term
        queryset = StudentFeeRecord.objects.filter(term=target_term)

        # Further filter by class if specified
        target_class = None
        if selected_class_id:
            try:
                target_class = Class.objects.get(pk=selected_class_id)
                queryset = queryset.filter(student__current_class_id=selected_class_id)
                print(f"Filtering records for Class: {target_class.name} (ID: {selected_class_id})")
            except (Class.DoesNotExist, ValueError):
                 messages.warning(self.request, "Invalid Class specified, showing all classes for the term.")
                 target_class = None # Reset if class is invalid

        # Select related and order
        queryset = queryset.select_related(
                'student__user',
                'term', # Already filtered, but good practice
                'student__current_class'
            ).order_by('student__current_class__name', 'student__user__last_name')

        class_records_grouped = {}
        for record in queryset:
            if record.student.current_class:
                class_obj = record.student.current_class
                class_id = class_obj.id
                class_name = class_obj.name
                if class_id not in class_records_grouped:
                    class_records_grouped[class_id] = {'name': class_name, 'records': []}
                class_records_grouped[class_id]['records'].append(record)

        # Store target term/class in context for template display/filtering
        self.target_term = target_term
        self.target_class = target_class # Might be None if no class filter applied

        return class_records_grouped


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass the determined target term and class to the template
        context['term'] = getattr(self, 'target_term', None)
        context['session'] = context['term'].session if context.get('term') else None
        context['target_class'] = getattr(self, 'target_class', None) # Pass target class if filtered
        # Allow selecting other terms/classes (for dropdowns in template perhaps)
        context['all_terms'] = Term.objects.select_related('session').order_by('-start_date')
        context['all_classes'] = Class.objects.order_by('name')
        context.pop('object_list', None)
        return context


    @transaction.atomic # Process all updates for a class atomically
    def post(self, request, *args, **kwargs):
        """Handle saving changes for a specific class submitted via its form."""
        submitted_class_id_str = request.POST.get('submitted_class_id')
        # Refetch target term to ensure POST operates on the intended term
        selected_term_id = request.GET.get('term_id') # Get from query param
        target_term = None
        if selected_term_id:
             try:
                 target_term = Term.objects.get(pk=selected_term_id)
             except (Term.DoesNotExist, ValueError):
                 pass # Error handled below
        else:
              target_term = self.get_active_term() # Fallback to active

        if not target_term:
             messages.error(request, "Cannot process submission: Term could not be determined.")
             return redirect(request.path_info) 

        if not submitted_class_id_str:
            messages.error(request, "Invalid submission: Missing class identifier.")
            return redirect(request.path_info)

        try:
            submitted_class_id = int(submitted_class_id_str)
            target_class = Class.objects.get(pk=submitted_class_id)
        except (ValueError, ObjectDoesNotExist):
            messages.error(request, "Invalid class specified in submission.")
            return redirect(request.path_info)

        # --- Process using parallel lists ---
        # Get all relevant data lists from the POST request for THIS specific form
        record_ids = request.POST.getlist('record_id') # IDs for all rows shown in the submitted form
        discounts = request.POST.getlist('discount')   # All discount values in order
        # Waivers list contains the 'value' (which is the record_id) of CHECKED boxes ONLY
        waiver_ids_checked = request.POST.getlist('waiver')

        # Ensure lists have expected lengths (basic sanity check)
        if len(record_ids) != len(discounts):
            messages.error(request, "Form data mismatch (discounts). Please try again.")
            # Re-render form potentially highlighting errors - more complex
            # For now, redirect back
            return redirect(request.path_info + f'#collapse-{submitted_class_id}')


        updated_count = 0
        error_count = 0
        records_to_update = [] # For potential bulk_update

        # Fetch all relevant records for this class and term in one query
        records_in_db = StudentFeeRecord.objects.filter(
            pk__in=record_ids, # Only process IDs submitted
            student__current_class_id=submitted_class_id, # Security check
            term=target_term # Ensure correct term
        ).in_bulk() # Fetch as a dictionary {id: record_obj}

        # Convert waiver_ids_checked to a set for efficient lookup
        waiver_ids_set = set(waiver_ids_checked)

        for i, record_id_str in enumerate(record_ids):
            try:
                record_id = int(record_id_str)
                record = records_in_db.get(record_id)

                if not record:
                    messages.warning(request, f"Record ID {record_id_str} not found or doesn't belong to class {target_class.name}. Skipped.")
                    error_count += 1
                    continue

                # Get submitted values for this row
                discount_str = discounts[i]
                # Check if this record's ID is in the set of checked waiver IDs
                waiver_checked = str(record_id) in waiver_ids_set # Compare as strings

                # Compare with current values and update if needed
                needs_save = False
                try:
                    new_discount = Decimal(discount_str or '0.00')
                    # Use tolerance for decimal comparison
                    if abs(record.discount - new_discount) > Decimal('0.001'):
                        record.discount = new_discount
                        needs_save = True
                except InvalidOperation:
                     messages.warning(request, f"Invalid discount format '{discount_str}' for {record.student}. Skipped discount update.")
                     error_count += 1
                     # Continue processing other fields for this record

                if record.waiver != waiver_checked:
                    record.waiver = waiver_checked
                    needs_save = True

                if needs_save:
                    # Recalculate net_fee before saving (save() method does this too, but explicit is fine)
                    record.net_fee = record.calculate_net_fee()
                    # Option 1: Save individually (triggers signals immediately) - Simpler
                    record.save()
                    # Option 2: Prepare for bulk_update (more complex, skips signals) - Faster for HUGE classes
                    # records_to_update.append(record)
                    updated_count += 1

            except ValueError:
                 messages.warning(request, f"Invalid Record ID {record_id_str} found in submission. Skipped.")
                 error_count += 1
            except Exception as e:
                 messages.error(request, f"Error updating record ID {record_id_str}: {e}")
                 error_count += 1

        # If using bulk_update (Option 2):
        # if records_to_update:
        #     try:
        #         StudentFeeRecord.objects.bulk_update(records_to_update, ['discount', 'waiver', 'net_fee'])
        #         updated_count = len(records_to_update)
        #         # !!! IMPORTANT: bulk_update DOES NOT trigger signals.
        #         # You would need to manually trigger FinancialRecord updates for affected students AFTER bulk_update.
        #         # For simplicity, sticking with individual save() is often better unless performance is dire.
        #     except Exception as e:
        #          messages.error(request, f"Bulk update failed: {e}")
        #          error_count += len(records_to_update)


        # --- Feedback Messages ---
        if updated_count > 0:
            messages.success(request, f"Successfully updated {updated_count} fee records for {target_class.name}.")
        if error_count == 0 and updated_count == 0:
             messages.info(request, f"No changes detected or saved for {target_class.name}.")
        elif error_count > 0:
             messages.warning(request, f"Finished processing for {target_class.name} with {error_count} errors/warnings.")

        # Redirect back to the list view, appending hash to open the correct accordion item
        query_params = request.GET.copy()
        redirect_url_base = reverse('student_fee_record_list')
        redirect_url_params = query_params.urlencode()
        redirect_url = f"{redirect_url_base}?{redirect_url_params}#collapse-{submitted_class_id}"
        return redirect(redirect_url)

# Payment Record Management
class PaymentListView(AdminRequiredMixin, ListView):
    model = Payment
    template_name = 'payment/payment_list.html'
    context_object_name = 'payments'
    ordering = ['-payment_date', '-pk']
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'financial_record__student__user',
            'financial_record__term__session'
        ).order_by('-payment_date', '-pk')
        session_id = self.request.GET.get('session_id')
        term_id = self.request.GET.get('term_id')
        if term_id:
            try:
                qs = qs.filter(financial_record__term_id=int(term_id))
            except (ValueError, Term.DoesNotExist):
                pass
        elif session_id:
            try:
                qs = qs.filter(financial_record__term__session_id=int(session_id))
            except ValueError:
                pass
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        session_id = request.GET.get('session_id')
        term_id = request.GET.get('term_id')

        # dropdown lists
        context['sessions'] = Session.objects.all().order_by('-start_date')
        context['terms'] = Term.objects.select_related('session').order_by('-start_date')

        # base totals (apply same filters as queryset)
        totals_qs = FinancialRecord.objects.all()
        if term_id:
            try:
                totals_qs = totals_qs.filter(term_id=int(term_id))
            except ValueError:
                pass
        elif session_id:
            try:
                totals_qs = totals_qs.filter(term__session_id=int(session_id))
            except ValueError:
                pass

        context['total_fee'] = totals_qs.aggregate(total=Sum('total_fee'))['total'] or Decimal('0.00')
        context['total_discount'] = totals_qs.aggregate(total=Sum('total_discount'))['total'] or Decimal('0.00')
        context['total_paid'] = totals_qs.aggregate(total=Sum('total_paid'))['total'] or Decimal('0.00')
        context['total_outstanding_balance'] = totals_qs.aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0.00')

        # summary by class
        summary_qs = totals_qs.values('student__current_class__name').annotate(
            expected=Sum('total_fee'),
            paid=Sum('total_paid'),
            discounts=Sum('total_discount'),
            outstanding=Sum('outstanding_balance')
        ).order_by('student__current_class__name')

        summary_list = []
        for row in summary_qs:
            summary_list.append({
                'class_name': row.get('student__current_class__name') or 'Unassigned',
                'expected': row.get('expected') or Decimal('0.00'),
                'paid': row.get('paid') or Decimal('0.00'),
                'discounts': row.get('discounts') or Decimal('0.00'),
                'outstanding': row.get('outstanding') or Decimal('0.00'),
            })
        context['summary_by_class'] = summary_list

        # pass selected ids for templates
        context['selected_session_id'] = int(session_id) if session_id else None
        context['selected_term_id'] = int(term_id) if term_id else None

        # keep active_term if needed by template
        context['active_term'] = Term.objects.filter(is_active=True).first()

        return context

class PaymentCreateView(AdminRequiredMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'payment/create_payment.html'
    success_url = reverse_lazy('payment_list') # Use reverse_lazy

    def form_valid(self, form):
        payment = form.save(commit=False)

        # Determine the student and term from the form
        student = form.cleaned_data.get('student') 
        term = form.cleaned_data.get('term')       \

        if not student or not term:
            # Handle case where student/term might not be directly on payment form
             financial_record_selected = form.cleaned_data.get('financial_record')
             if financial_record_selected:
                 student = financial_record_selected.student
                 term = financial_record_selected.term
             else:
                  form.add_error(None, "Could not determine Student and Term for payment.")
                  return self.form_invalid(form)

        # Get or create FinancialRecord
        # The signal on StudentFeeRecord should have already created it if a fee exists.
        financial_record, created = FinancialRecord.objects.get_or_create(
            student=student,
            term=term,
            # Defaults might be needed if StudentFeeRecord signal didn't run yet
            defaults={
                'total_fee': Decimal('0.00'),
                'total_discount': Decimal('0.00'),
                'total_paid': Decimal('0.00'),
                'outstanding_balance': Decimal('0.00')
            }
        )
        # If created here, it might not have the correct total_fee yet.
        payment.financial_record = financial_record

        try:
            # Save the payment instance - this will trigger the post_save signal
            # The signal handler will update the financial_record
            payment.save()
            # Ensure self.object is set so get_success_url can format properly
            self.object = payment
            messages.success(self.request, 'Payment recorded successfully.')
            return redirect(self.get_success_url())
        except ValidationError as e:
            # Catch validation errors from Payment.clean()
            form.add_error(None, e) # Add validation errors back to the form
            return self.form_invalid(form)
        except Exception as e:
            # Catch other unexpected errors during save
            messages.error(self.request, f"An unexpected error occurred: {e}")
            return self.form_invalid(form)

    # Use the default form_invalid from CreateView so the form is re-rendered

class PaymentUpdateView(AdminRequiredMixin, UpdateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'payment/update_payment.html'
    success_url = reverse_lazy('payment_list')

    def form_valid(self, form):
        try:
            # Saving the form will trigger the post_save signal on Payment
            # which updates the FinancialRecord
            payment = form.save()
            messages.success(self.request, 'Payment updated successfully.')
            return redirect(self.get_success_url())
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"An unexpected error occurred: {e}")
            return self.form_invalid(form)

class PaymentDetailView(AdminRequiredMixin, DetailView):
    model = Payment
    template_name = 'payment/payment_detail.html'
    context_object_name = 'payment'

    def get_queryset(self):
         # Optimize detail view query
        return super().get_queryset().select_related(
            'financial_record__student__user',
            'financial_record__term__session'
        )

class PaymentDeleteView(AdminRequiredMixin, DeleteView):
    model = Payment
    template_name = 'payment/delete_payment.html'
    success_url = reverse_lazy('payment_list')

    def form_valid(self, form): # Use form_valid for DeleteView POST handling
        try:
            # The post_delete signal will handle updating the FinancialRecord
            response = super().form_valid(form)
            messages.success(self.request, 'Payment deleted successfully.')
            return response
        except Exception as e:
             messages.error(self.request, f"An error occurred while deleting the payment: {e}")
             # Redirect back to list or detail view on error
             return redirect('payment_list')

# --- Financial Record List View ---
class FinancialRecordListView(AdminRequiredMixin, ListView):
    model = FinancialRecord
    template_name = 'financial_record/financial_record_list.html'
    context_object_name = 'financial_records'
    paginate_by = 50 # Add pagination

    def get_queryset(self):
        # Preload related fields for optimization
        qs = FinancialRecord.objects.select_related(
            'student__user',
            'term__session'
        ).order_by('-term__start_date', 'student__user__last_name')
        # Apply filters if provided
        session_id = self.request.GET.get('session_id')
        term_id = self.request.GET.get('term_id')
        if term_id:
            try:
                qs = qs.filter(term_id=int(term_id))
            except (ValueError, Term.DoesNotExist):
                pass
        elif session_id:
            try:
                qs = qs.filter(term__session_id=int(session_id))
            except ValueError:
                pass
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # filter inputs
        request = self.request
        session_id = request.GET.get('session_id')
        term_id = request.GET.get('term_id')

        # lists for dropdowns
        context['sessions'] = Session.objects.all().order_by('-start_date')
        context['terms'] = Term.objects.select_related('session').order_by('-start_date')

        # base queryset for totals (apply same filters used for list)
        totals_qs = FinancialRecord.objects.all()
        if term_id:
            try:
                totals_qs = totals_qs.filter(term_id=int(term_id))
            except ValueError:
                pass
        elif session_id:
            try:
                totals_qs = totals_qs.filter(term__session_id=int(session_id))
            except ValueError:
                pass

        from decimal import Decimal
        from django.db.models import Sum

        context['total_fee'] = totals_qs.aggregate(total=Sum('total_fee'))['total'] or Decimal('0.00')
        context['total_discount'] = totals_qs.aggregate(total=Sum('total_discount'))['total'] or Decimal('0.00')
        context['total_paid'] = totals_qs.aggregate(total=Sum('total_paid'))['total'] or Decimal('0.00')
        context['total_outstanding_balance'] = totals_qs.aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0.00')

        # Summary by class: annotate sums grouped by student's current_class
        summary_qs = totals_qs.values('student__current_class__name').annotate(
            expected=Sum('total_fee'),
            paid=Sum('total_paid'),
            discounts=Sum('total_discount'),
            outstanding=Sum('outstanding_balance')
        ).order_by('student__current_class__name')

        summary_list = []
        for row in summary_qs:
            summary_list.append({
                'class_name': row.get('student__current_class__name') or 'Unassigned',
                'expected': row.get('expected') or Decimal('0.00'),
                'paid': row.get('paid') or Decimal('0.00'),
                'discounts': row.get('discounts') or Decimal('0.00'),
                'outstanding': row.get('outstanding') or Decimal('0.00'),
            })
        context['summary_by_class'] = summary_list

        # pass selected ids for templates
        context['selected_session_id'] = int(session_id) if session_id else None
        context['selected_term_id'] = int(term_id) if term_id else None

        return context

def update_result(request, student_id, term_id):
    student = get_object_or_404(Student, pk=student_id)
    result = get_object_or_404(Result, student=student, term=term_id)

    if request.method == 'POST':
        form = NonAcademicSkillsForm(request.POST, instance=result)
        if form.is_valid():
            form.save()
            return redirect('view_student_result', student_id=student.id, term_id=term_id)
    else:
        form = NonAcademicSkillsForm(instance=result)

    return render(request, 'update_result.html', {
        'form': form,
        'student': student,
        'result': result,
    })

# Promote a student
def promote_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if student.current_class.next_class:
        student.current_class = student.current_class.next_class()
        student.save()
        messages.success(request, f"{student.user.get_full_name()} has been promoted to {student.current_class.name}.")
    else:
        messages.error(request, f"{student.user.get_full_name()} cannot be promoted (no next class available).")
    return redirect('student_list')

# Repeat a student
def repeat_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    messages.info(request, f"{student.user.get_full_name()} will repeat {student.current_class.name}.")
    # No change in class; just log or notify.
    return redirect('student_list')

# Demote a student
def demote_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if student.current_class.previous_class:
        student.current_class = student.current_class.previous_class()
        student.save()
        messages.success(request, f"{student.user.get_full_name()} has been demoted to {student.current_class.name}.")
    else:
        messages.error(request, f"{student.user.get_full_name()} cannot be demoted (no previous class available).")
    return redirect('student_list')

# Mark a student as dormant
def mark_dormant_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.status = 'dormant'  # Ensure this value matches the choices in your model
    student.save()
    messages.success(request, f"{student.user.get_full_name()} has been marked as dormant.")
    return redirect('student_list')

# Mark a student as left
def mark_left_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.status = 'left'  # Ensure this value matches the choices in your model
    student.save()
    messages.success(request, f"{student.user.get_full_name()} has been marked as left.")
    return redirect('student_list')

def mark_active(request, pk):
    student = get_object_or_404(Student, pk)
    student.status = 'active'
    student.save()
    messages.sucess(request, f"{student.user.get_full_name()} has been marked active.")
    return redirect('stuent_list')


def send_test_email(request):
    send_mail(
        'Test Email',
        'This is a test email.',
        'your_email@example.com',
        ['recipient@example.com'],
        fail_silently=False,
    )
    return HttpResponse("Test email sent successfully!")

### ----- ASSESSMENT SECTION ----- ###

# --- Helper: Process NEW Questions (for Create and Update) ---
def _process_newly_added_questions(request, assessment, question_name_prefix='new_question_'):
    errors = []
    question_number = 1
    questions_successfully_added = 0

    while True:
        q_type_key = f'{question_name_prefix}type_{question_number}'
        q_text_key = f'{question_name_prefix}text_{question_number}'
        q_options_key = f'{question_name_prefix}options_{question_number}'
        q_correct_key = f'{question_name_prefix}correct_answer_{question_number}'
        q_points_key = f'{question_name_prefix}points_{question_number}'

        if q_type_key not in request.POST and q_text_key not in request.POST : # Check if any primary field for this new question number exists
            break

        question_type = request.POST.get(q_type_key)
        question_text = request.POST.get(q_text_key, '').strip()
        options_str = request.POST.get(q_options_key, '')
        correct_answer_str = request.POST.get(q_correct_key, '').strip()
        points_str = request.POST.get(q_points_key)

        if not question_text and not question_type: # Skip if completely empty entry from JS
             question_number += 1
             continue
        if not question_text: # Error if type present but no text
            if question_type: errors.append(f"Error in New Question {question_number}: Text is empty.")
            question_number += 1
            continue

        options_list = [opt.strip() for opt in options_str.split(',') if opt.strip()]
        
        form_data = {
            'question_type': question_type,
            'question_text': question_text,
            'options': options_list,
            'correct_answer': correct_answer_str if correct_answer_str else None,
            'points': points_str if points_str else None
        }
        
        question_form = OnlineQuestionForm(form_data)
        if question_form.is_valid():
            try:
                new_question = question_form.save()
                assessment.questions.add(new_question)
                questions_successfully_added += 1
            except Exception as e:
                errors.append(f"Error saving new question {question_number}: {str(e)}")
        else:
            for field, field_errors in question_form.errors.items():
                errors.append(f"New Question {question_number} ({field.replace('_',' ').title()}): {', '.join(field_errors)}")
        
        question_number += 1
    
    if questions_successfully_added == 0 and f'{question_name_prefix}type_1' in request.POST:
        if not errors: errors.append("Attempted to add new questions, but none were valid or saved.")
    return errors


@user_passes_test(lambda u: u.is_superuser or hasattr(u, 'teacher'))
@login_required
def grant_retake(request, item_type, item_id, student_id):
    """
    Grants a retake for a student on a specific Assessment or Exam.
    This creates a new, blank submission record with an incremented attempt number.
    """
    student = get_object_or_404(Student, pk=student_id)
    
    # Determine which models to use based on the URL parameter
    if item_type.lower() == 'assessment':
        ItemModel = Assessment
        SubmissionModel = AssessmentSubmission
        redirect_url_name = 'assessment_submissions_list'
        id_kwarg = 'assessment_id'
    elif item_type.lower() == 'exam':
        ItemModel = Exam
        SubmissionModel = ExamSubmission
        redirect_url_name = 'exam_submissions_list'
        id_kwarg = 'exam_id'
    else:
        messages.error(request, "Invalid item type specified for retake.")
        return redirect('school-setup')

    item = get_object_or_404(ItemModel, id=item_id)
    
    # Authorization: Ensure teacher is assigned to the class (optional but recommended)
    # ...

    if request.method == 'POST':
        # Find the highest existing attempt number for this student and item
        max_attempt = SubmissionModel.objects.filter(
            **{item_type.lower(): item}, student=student
        ).aggregate(Max('attempt_number'))['attempt_number__max'] or 0
        
        new_attempt_number = max_attempt + 1

        # Create the new, blank, incomplete submission record
        SubmissionModel.objects.create(
            **{item_type.lower(): item},
            student=student,
            attempt_number=new_attempt_number,
        )

        messages.success(request, f"Retake (Attempt #{new_attempt_number}) has been granted to {student.user.get_full_name()}.")
        return redirect(redirect_url_name, **{id_kwarg: item.id})

    # For the confirmation page (GET request)
    context = {
        'item': item,
        'student': student,
        'item_type': item_type,
    }
    return render(request, 'setup/grant_retake_confirm.html', context)

# --- Create Assessment View ---
@login_required
def create_assessment(request):
    user = request.user
    teacher_profile = Teacher.objects.filter(user=user).first() # Adjusted to filter

    if teacher_profile:
        assigned_classes_qs = teacher_profile.assigned_classes()
        assigned_subjects_qs = teacher_profile.assigned_subjects()
    elif user.is_superuser:
        assigned_classes_qs = Class.objects.all()
        assigned_subjects_qs = Subject.objects.all()
    else:
        messages.error(request, "You are not authorized to create assessments.")
        return redirect('home') # Or an appropriate unauthorized page

    if request.method == 'POST':
        form = AssessmentForm(request.POST)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs

        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.created_by = user
            if user.is_superuser: # Superusers can auto-approve
                assessment.is_approved = True
            assessment.save() # Save assessment to get an ID before adding M2M questions

            # Use the specific function for new questions from 'create' form (prefix 'question_')
            question_processing_errors = _process_newly_added_questions(request, assessment, question_name_prefix='question_')
            
            if not question_processing_errors:
                messages.success(request, f"Assessment '{assessment.title}' created successfully.")
                return redirect('admin_dashboard' if user.is_superuser else 'teacher_dashboard')
            else:
                assessment.delete() # Rollback assessment creation if questions had critical errors
                form_with_initial_data = AssessmentForm(request.POST) # Re-bind to show original data
                form_with_initial_data.fields['class_assigned'].queryset = assigned_classes_qs
                form_with_initial_data.fields['subject'].queryset = assigned_subjects_qs
                messages.error(request, "Assessment not created. Please correct the question errors.")
                return render(request, 'assessment/create_assessment.html', {
                    'form': form_with_initial_data,
                    'question_errors': question_processing_errors,
                })
        else: # AssessmentForm is invalid
            form.fields['class_assigned'].queryset = assigned_classes_qs # Re-set for template
            form.fields['subject'].queryset = assigned_subjects_qs
            return render(request, 'assessment/create_assessment.html', {'form': form})
    else: # GET request
        form = AssessmentForm()
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs
        return render(request, 'assessment/create_assessment.html', {'form': form})

# --- Update Assessment View ---
@login_required
def update_assessment(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id)
    user = request.user
    
    # Authorization check (can be simplified and made more robust)
    is_creator = assessment.created_by == user
    is_form_teacher = False
    if hasattr(user, 'teacher'):
        form_teacher_of_class = assessment.class_assigned.form_teacher()
        if form_teacher_of_class and form_teacher_of_class == user.teacher:
            is_form_teacher = True

    if not (user.is_superuser or is_creator or is_form_teacher):
        messages.error(request, "You are not authorized to update this assessment.")
        return redirect('home')

    # Get available classes/subjects for the form dropdowns
    if hasattr(user, 'teacher') and not user.is_superuser:
        assigned_classes_qs = user.teacher.assigned_classes()
        assigned_subjects_qs = user.teacher.assigned_subjects()
    else: 
        assigned_classes_qs = Class.objects.all()
        assigned_subjects_qs = Subject.objects.all()

    if request.method == 'POST':
        form = AssessmentForm(request.POST, instance=assessment)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs

        if form.is_valid():
            updated_assessment = form.save(commit=False)
            updated_assessment.updated_at = timezone.now()
            updated_assessment.save()

            all_errors = []

            # --- FIX 3: THE SMARTER EXISTING QUESTION PROCESSING LOOP ---
            for q_instance in assessment.questions.all():
                q_id = q_instance.id
                
                # We only process an existing question if its text is submitted in the POST.
                # This check prevents validation errors when only saving assessment details.
                submitted_text = request.POST.get(f'question_{q_id}_text')
                if submitted_text is not None:
                    data_for_existing = {
                        'question_type': request.POST.get(f'question_{q_id}_type'),
                        'question_text': submitted_text.strip(),
                        'options': [opt.strip() for opt in request.POST.get(f'question_{q_id}_options', '').split(',') if opt.strip()],
                        'correct_answer': request.POST.get(f'question_{q_id}_correct_answer', '').strip() or None,
                        'points': request.POST.get(f'question_{q_id}_points') # Pass points
                    }
                    q_form = OnlineQuestionForm(data_for_existing, instance=q_instance)
                    if q_form.is_valid():
                        q_form.save()
                    else:
                        for field, field_errors in q_form.errors.items():
                            all_errors.append(f"Existing Question ID {q_id} ({field.replace('_',' ').title()}): {', '.join(field_errors)}")
            
            # --- Logic for Deleted and New Questions (remains the same) ---
            deleted_ids_str = request.POST.get('deleted_question_ids', '')
            if deleted_ids_str:
                deleted_ids = [int(id_str) for id_str in deleted_ids_str.split(',') if id_str.isdigit()]
                assessment.questions.remove(*deleted_ids) 
                OnlineQuestion.objects.filter(id__in=deleted_ids, assessments=None).delete()

            new_question_errors = _process_newly_added_questions(request, assessment, question_name_prefix='new_question_')
            all_errors.extend(new_question_errors)

            # --- Redirect or Re-render Logic (remains the same) ---
            if not all_errors:
                messages.success(request, "Assessment updated successfully.")
                return redirect('view_assessment', assessment_id=assessment.id)
            else:
                messages.error(request, "Errors occurred while processing questions. Please review.")
        
        # If form is invalid or question processing had errors, re-render the page
        current_questions = assessment.questions.all().order_by('id')
        return render(request, 'assessment/update_assessment.html', {
            'form': form, 
            'assessment': assessment,
            'questions': current_questions,
            'processing_errors': all_errors if 'all_errors' in locals() else [] 
        })

    else: # GET request
        form = AssessmentForm(instance=assessment)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs
        questions = assessment.questions.all().order_by('id')
        return render(request, 'assessment/update_assessment.html', {
            'form': form,
            'assessment': assessment,
            'questions': questions
        })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def approve_assessment(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id)
    if request.method == 'POST':
        if not assessment.is_approved:
            assessment.is_approved = True
            assessment.approved_by = request.user
            assessment.save()
            messages.success(request, f"Assessment '{assessment.title}' approved and students notified.")
        else:
            messages.info(request, f"Assessment '{assessment.title}' was already approved.")
        return redirect('school-setup') 
    return render(request, 'assessment/approve_assessment_confirm.html', {'assessment': assessment})


@login_required
@user_passes_test(lambda u: u.is_superuser) 
def admin_assessment_list(request):

    assessments_qs = Assessment.objects.annotate(
        submission_count=Count('submissions_for_assessment') 
    ).order_by('-created_at')
    
    pending_assessment_count = Assessment.objects.filter(is_approved=False).count()
    
    return render(request, 'assessment/admin_assessment_list.html', {
        'assessments': assessments_qs,
        'pending_assessment_count': pending_assessment_count
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def pending_assessments(request):
    pending_assessments = Assessment.objects.filter(is_approved=False)
    return render(request, 'setup/pending_assessments.html', {'pending_assessments': pending_assessments})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def view_assessment(request, assessment_id):
    # Retrieve the assessment and its questions
    assessment = get_object_or_404(Assessment, id=assessment_id)
    questions = assessment.questions.all()

    context = {
        'assessment': assessment,
        'questions': questions,
    }
    return render(request, 'assessment/assessment_detail.html', context)

# views.py
@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_delete_assessment(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id)
    
    if request.method == 'POST':
        assessment_title = assessment.title
        
        try:
            assessment.delete()
            messages.success(request, f"Assessment '{assessment_title}' has been successfully deleted.")
            return redirect('admin_assessment_list')
        except Exception as e:

            import traceback
            traceback.print_exc() # This should print the full traceback to console
            
            messages.error(request, f"An error occurred: {str(e)}. Please check server logs.")

            raise e 
            
    messages.warning(request, "Invalid request to delete. Deletion must be confirmed.")
    return redirect('admin_assessment_list')


# views.py
@login_required
def assessment_submissions_list(request, assessment_id):
    assessment = get_object_or_404(Assessment.objects.select_related('class_assigned'), id=assessment_id)

    # Authorization: Superuser or creator of the assessment
    if not (request.user.is_superuser or assessment.created_by == request.user):
        messages.error(request, "You are not authorized to view submissions for this assessment.")
        return redirect('admin_assessment_list') # Or appropriate redirect

    all_enrolled_students = Student.objects.filter(
        current_class=assessment.class_assigned
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    submissions = AssessmentSubmission.objects.filter(assessment=assessment)
    submissions_map = {sub.student.pk: sub for sub in submissions}
    
    pending_manual_grade_count = submissions.filter(requires_manual_review=True, is_graded=False).count()

    context = {
        'assessment': assessment,
        'all_enrolled_students': all_enrolled_students,
        'submissions': submissions,
        'submissions_map': submissions_map,
        'pending_manual_grade_count': pending_manual_grade_count,
    }
    return render(request, 'assessment/assessment_submissions_list.html', context)


def grade_essay_assessment_view(request, submission_id):
    submission = get_object_or_404(AssessmentSubmission, id=submission_id)
    assessment = submission.assessment
    user = request.user # Get the current user

    # Authorization
    if not (user.is_superuser or assessment.created_by == user):
        messages.error(request, "You are not authorized to grade this submission.")
        return redirect('home') # Or a more appropriate unauthorized page

    # Prepare questions and answers for display
    all_questions_data = []
    max_possible_auto_score = 0
    max_possible_manual_score = 0 # Assuming 1 point per essay for now, adjust as needed

    for q_obj in assessment.questions.all().order_by('id'):
        raw_ans = submission.answers.get(str(q_obj.id)) if isinstance(submission.answers, dict) else None
        student_answer_display = ", ".join(raw_ans) if isinstance(raw_ans, list) else raw_ans
        
        is_correct_auto = None
        if q_obj.question_type in ['SCQ', 'MCQ']:
            max_possible_auto_score += 1 # Assuming 1 point per question
            # Simplified check for display; actual grading happened on submission
            if q_obj.question_type == 'SCQ' and student_answer_display == q_obj.correct_answer:
                is_correct_auto = True
            elif q_obj.question_type == 'MCQ':
                correct_mcq_set = set(op.strip().lower() for op in (q_obj.correct_answer or "").split(',') if op.strip())
                submitted_mcq_set = set(op.strip().lower() for op in (student_answer_display or "").split(',') if op.strip())
                if correct_mcq_set == submitted_mcq_set and correct_mcq_set:
                    is_correct_auto = True
                elif correct_mcq_set:
                    is_correct_auto = False
        elif q_obj.question_type == 'ES':
            max_possible_manual_score += 1 

        all_questions_data.append({
            'question': q_obj,
            'student_answer': student_answer_display,
            'is_essay': q_obj.question_type == 'ES',
            'is_correct_auto': is_correct_auto
        })

    # The score stored on submission for mixed assessments is the auto-graded part
    auto_graded_score = 0
    if not submission.requires_manual_review and submission.is_graded: # Was fully auto-graded
        auto_graded_score = submission.score or 0
    elif submission.requires_manual_review and submission.score is not None: # Auto-graded part was stored
        auto_graded_score = submission.score or 0


    if request.method == 'POST':
        manual_score_str = request.POST.get('manual_score') # Score for manually graded parts
        feedback_str = request.POST.get('feedback', '').strip()

        try:
            manual_score_input = float(manual_score_str) if manual_score_str else 0
            
            # Calculate final score
            final_score = (auto_graded_score if auto_graded_score is not None else 0) + manual_score_input
            
            submission.score = final_score 
            submission.feedback = feedback_str
            submission.is_graded = True
            submission.requires_manual_review = False 
            submission.save()
            
            messages.success(request, f"Submission for {submission.student.user.get_full_name()} graded. Final Score: {final_score}")
            
            if user.is_superuser:
                return redirect('assessment_submissions_list', assessment_id=assessment.id)
            elif hasattr(user, 'teacher_profile'): 
                return redirect('teacher_dashboard') 
            else: 
                return redirect('home')

        except (ValueError, TypeError):
            messages.error(request, "Invalid score entered. Please enter a valid number for the manual score.")

    context = {
        'submission': submission,
        'assessment': assessment,
        'all_questions_data': all_questions_data,
        'auto_graded_score': auto_graded_score, 
        'max_possible_manual_score': max_possible_manual_score, 
    }
    return render(request, 'assessment/grade_essay_submission.html', context)


### ----- EXAM SECTON ------ ###

# --- Create Exam View ---

@login_required
def create_exam(request):
    user = request.user
    teacher_profile = Teacher.objects.filter(user=user).first() 

    if teacher_profile:
        assigned_classes_qs = teacher_profile.assigned_classes()
        assigned_subjects_qs = teacher_profile.assigned_subjects()
    elif user.is_superuser:
        assigned_classes_qs = Class.objects.all()
        assigned_subjects_qs = Subject.objects.all()
    else:
        messages.error(request, "You are not authorized to create exams.")
        return redirect('home') 

    if request.method == 'POST':
        form = ExamForm(request.POST)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs

        if form.is_valid():
            exam = form.save(commit=False)
            exam.created_by = user
            if user.is_superuser: 
                exam.is_approved = True
            exam.save() 

            # Use the specific function for new questions from 'create' form (prefix 'question_')
            question_processing_errors = _process_newly_added_questions(request, exam, question_name_prefix='question_')
            
            if not question_processing_errors:
                messages.success(request, f"Exam '{exam.title}' created successfully.")
                return redirect('admin_dashboard' if user.is_superuser else 'teacher_dashboard')
            else:
                exam.delete() 
                form_with_initial_data = ExamForm(request.POST) 
                form_with_initial_data.fields['class_assigned'].queryset = assigned_classes_qs
                form_with_initial_data.fields['subject'].queryset = assigned_subjects_qs
                messages.error(request, "Exam not created. Please correct the question errors.")
                return render(request, 'exam/create_exam.html', {
                    'form': form_with_initial_data,
                    'question_errors': question_processing_errors,
                })
        else: 
            form.fields['class_assigned'].queryset = assigned_classes_qs # Re-set for template
            form.fields['subject'].queryset = assigned_subjects_qs
            return render(request, 'exam/create_exam.html', {'form': form})
    else: # GET request
        form = ExamForm()
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs
        return render(request, 'exam/create_exam.html', {'form': form})

# --- Update Exam View ---
@login_required
def update_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    user = request.user
    teacher_profile = Teacher.objects.filter(user=user).first()

    # Authorization
    if not (user.is_superuser or exam.created_by == user):
        messages.error(request, "You are not authorized to update this exam.")
        return redirect('home')

    if teacher_profile and not user.is_superuser :
        assigned_classes_qs = teacher_profile.assigned_classes()
        assigned_subjects_qs = teacher_profile.assigned_subjects()
    else: # Superuser or non-teacher (though auth check above should handle non-teacher)
        assigned_classes_qs = Class.objects.all()
        assigned_subjects_qs = Subject.objects.all()

    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs

        if form.is_valid():
            updated_exam = form.save(commit=False)
            if user.is_superuser and not exam.is_approved: 
                 updated_exam.is_approved = True
                 updated_exam.approved_by = user
            updated_exam.updated_at = timezone.now()
            updated_exam.save()

            all_errors = []

            # 1. Update Existing Questions
            submitted_existing_ids = set()
            for q_instance in exam.questions.all():
                q_id = q_instance.id
                # Check if data for this existing question was submitted for update
                # (Assumes edit form fields are named question_ID_text, etc.)
                if f'question_{q_id}_text' in request.POST or f'question_{q_id}_type' in request.POST:
                    submitted_existing_ids.add(q_id)
                    data_for_existing = {
                        'question_type': request.POST.get(f'question_{q_id}_type'),
                        'question_text': request.POST.get(f'question_{q_id}_text', '').strip(),
                        'options': [opt.strip() for opt in request.POST.get(f'question_{q_id}_options', '').split(',') if opt.strip()],
                        'correct_answer': request.POST.get(f'question_{q_id}_correct_answer', '').strip() or None
                    }
                    q_form = OnlineQuestionForm(data_for_existing, instance=q_instance)
                    if q_form.is_valid():
                        q_form.save()
                    else:
                        for field, field_errors in q_form.errors.items():
                            all_errors.append(f"Existing Question ID {q_id} ({field.replace('_',' ').title()}): {', '.join(field_errors)}")
            
            # 2. Remove Questions (if a mechanism exists to mark them for deletion)
            deleted_ids_str = request.POST.get('deleted_question_ids', '') # e.g., "12,15,20"
            if deleted_ids_str:
                deleted_ids = [int(id_str) for id_str in deleted_ids_str.split(',') if id_str.isdigit()]
                exam.questions.remove(*deleted_ids) 
                OnlineQuestion.objects.filter(id__in=deleted_ids, exams=None).delete() # Optional: delete orphaned questions

            # 3. Add Newly Added Questions (uses 'new_question_' prefix)
            new_question_errors = _process_newly_added_questions(request, exam, question_name_prefix='new_question_')
            all_errors.extend(new_question_errors)

            if not all_errors:
                messages.success(request, "Exam updated successfully.")
                return redirect('view_exam', exam_id=exam.id)
            else:
                messages.error(request, "Errors occurred. Please review.")
        # If form is invalid or errors occurred, re-render with context
        current_questions = exam.questions.all().order_by('id')
        return render(request, 'exam/update_exam.html', {
            'form': form, # This form instance will have its own errors
            'exam': exam,
            'questions': current_questions,
            'processing_errors': all_errors if 'all_errors' in locals() and all_errors else [] 
        })

    else: # GET request
        form = ExamForm(instance=exam)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs
        questions = exam.questions.all().order_by('id')
        return render(request, 'exam/update_exam.html', {
            'form': form,
            'exam': exam,
            'questions': questions
        })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def approve_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.method == 'POST':
        if not exam.is_approved:
            exam.is_approved = True
            exam.approved_by = request.user
            exam.save()
            messages.success(request, f"Exam '{exam.title}' approved and students notified.")
        else:
            messages.info(request, f"Exam '{exam.title}' was already approved.")
        return redirect('school-setup') 
    return render(request, 'exam/approve_exam_confirm.html', {'exam': exam})


@login_required
@user_passes_test(lambda u: u.is_superuser) 
def admin_exam_list(request):

    exams_qs = Exam.objects.annotate(
        submission_count=Count('submissions_for_exam') 
    ).order_by('-created_at')
    
    pending_exam_count = Exam.objects.filter(is_approved=False).count()
    
    return render(request, 'exam/admin_exam_list.html', {
        'exams': exams_qs,
        'pending_exam_count': pending_exam_count,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def pending_exams(request):
    pending_exams = Exam.objects.filter(is_approved=False)
    return render(request, 'setup/pending_exams.html', {'pending_exams': pending_exams})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def view_exam(request, exam_id):
    # Retrieve the exam and its questions
    exam = get_object_or_404(Exam, id=exam_id)
    questions = exam.questions.all()

    context = {
        'exam': exam,
        'questions': questions,
    }
    return render(request, 'exam/exam_detail.html', context)

# views.py
@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    
    if request.method == 'POST':
        exam_title = exam.title
        
        try:
            exam.delete()
            messages.success(request, f"Exam '{exam_title}' has been successfully deleted.")
            return redirect('admin_exam_list')
        
        except Exception as e:
            import traceback
            traceback.print_exc() 
            
            messages.error(request, f"An error occurred: {str(e)}. Please check server logs.")
 
            raise e 
            
    messages.warning(request, "Invalid request to delete. Deletion must be confirmed.")
    return redirect('admin_exam_list')


# views.py
@login_required
def exam_submissions_list(request, exam_id):
    exam = get_object_or_404(Exam.objects.select_related('class_assigned'), id=exam_id)

    # Authorization: Superuser or creator of the exam
    if not (request.user.is_superuser or exam.created_by == request.user):
        messages.error(request, "You are not authorized to view submissions for this exam.")
        return redirect('admin_exam_list') # Or appropriate redirect

    all_enrolled_students = Student.objects.filter(
        current_class=exam.class_assigned
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    submissions = ExamSubmission.objects.filter(exam=exam)
    submissions_map = {sub.student.pk: sub for sub in submissions}
    
    pending_manual_grade_count = submissions.filter(requires_manual_review=True, is_graded=False).count()

    context = {
        'exam': exam,
        'all_enrolled_students': all_enrolled_students,
        'submissions': submissions,
        'submissions_map': submissions_map,
        'pending_manual_grade_count': pending_manual_grade_count,
    }
    return render(request, 'exam/exam_submissions_list.html', context)


def grade_essay_exam_view(request, submission_id):
    submission = get_object_or_404(ExamSubmission, id=submission_id)
    exam = submission.exam
    user = request.user 

    # Authorization
    if not (user.is_superuser or exam.created_by == user):
        messages.error(request, "You are not authorized to grade this submission.")
        return redirect('home') # Or a more appropriate unauthorized page

    # Prepare questions and answers for display
    all_questions_data = []
    max_possible_auto_score = 0
    max_possible_manual_score = 0 # Assuming 1 point per essay for now, adjust as needed

    for q_obj in exam.questions.all().order_by('id'):
        raw_ans = submission.answers.get(str(q_obj.id)) if isinstance(submission.answers, dict) else None
        student_answer_display = ", ".join(raw_ans) if isinstance(raw_ans, list) else raw_ans
        
        is_correct_auto = None
        if q_obj.question_type in ['SCQ', 'MCQ']:
            max_possible_auto_score += 1 # Assuming 1 point per question
            # Simplified check for display; actual grading happened on submission
            if q_obj.question_type == 'SCQ' and student_answer_display == q_obj.correct_answer:
                is_correct_auto = True
            elif q_obj.question_type == 'MCQ':
                correct_mcq_set = set(op.strip().lower() for op in (q_obj.correct_answer or "").split(',') if op.strip())
                submitted_mcq_set = set(op.strip().lower() for op in (student_answer_display or "").split(',') if op.strip())
                if correct_mcq_set == submitted_mcq_set and correct_mcq_set:
                    is_correct_auto = True
                elif correct_mcq_set:
                    is_correct_auto = False
        elif q_obj.question_type == 'ES':
            max_possible_manual_score += 1 # Example: 1 point per essay, or define points per question

        all_questions_data.append({
            'question': q_obj,
            'student_answer': student_answer_display,
            'is_essay': q_obj.question_type == 'ES',
            'is_correct_auto': is_correct_auto
        })

    # The score stored on submission for mixed exams is the auto-graded part
    auto_graded_score = 0
    if not submission.requires_manual_review and submission.is_graded: # Was fully auto-graded
        auto_graded_score = submission.score or 0
    elif submission.requires_manual_review and submission.score is not None: # Auto-graded part was stored
        auto_graded_score = submission.score or 0


    if request.method == 'POST':
        manual_score_str = request.POST.get('manual_score') # Score for manually graded parts
        feedback_str = request.POST.get('feedback', '').strip()

        try:
            manual_score_input = float(manual_score_str) if manual_score_str else 0
            
            # Calculate final score
            final_score = (auto_graded_score if auto_graded_score is not None else 0) + manual_score_input
            
            submission.score = final_score 
            submission.feedback = feedback_str
            submission.is_graded = True
            submission.requires_manual_review = False 
            submission.save()
            
            messages.success(request, f"Submission for {submission.student.user.get_full_name()} graded. Final Score: {final_score}")
            
            # Dynamic redirect
            if user.is_superuser:
                return redirect('exam_submissions_list', exam_id=exam.id)
            elif hasattr(user, 'teacher_profile'): 
                return redirect('teacher_dashboard') 
            else: 
                return redirect('home')

        except (ValueError, TypeError):
            messages.error(request, "Invalid score entered. Please enter a valid number for the manual score.")

    context = {
        'submission': submission,
        'exam': exam,
        'all_questions_data': all_questions_data,
        'auto_graded_score': auto_graded_score, 
        'max_possible_manual_score': max_possible_manual_score, 
    }
    return render(request, 'exam/grade_essay_submission.html', context)


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


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_leaderboard_view(request):
    # --- Filter Logic ---
    selected_term_id = request.GET.get('term_id')
    selected_session_id = request.GET.get('session_id')

    # Get all sessions and terms for the dropdown filters
    all_sessions = Session.objects.all().order_by('-start_date')
    all_terms = Term.objects.all().select_related('session').order_by('-start_date')

    # Determine the term to display data for
    display_term = None
    if selected_term_id:
        try:
            display_term = Term.objects.get(pk=selected_term_id)
        except (Term.DoesNotExist, ValueError):
            pass # Will default to active term
    
    if not display_term:
        display_term = Term.objects.filter(is_active=True).first()

    # Filter terms based on selected session if any
    if selected_session_id:
        all_terms = all_terms.filter(session_id=selected_session_id)


    # --- LEADERBOARD DATA GENERATION ---
    leaderboard_data = {}
    all_classes = Class.objects.all().order_by('order')

    if display_term:
        for class_instance in all_classes:
            assignment_count_sub = AssignmentSubmission.objects.filter(student=OuterRef('pk'), assignment__term=display_term).values('student').annotate(c=Count('pk')).values('c')
            assessment_count_sub = AssessmentSubmission.objects.filter(student=OuterRef('pk'), assessment__term=display_term).values('student').annotate(c=Count('pk')).values('c')
            exam_count_sub = ExamSubmission.objects.filter(student=OuterRef('pk'), exam__term=display_term).values('student').annotate(c=Count('pk')).values('c')

            class_leaderboard_qs = Student.objects.filter(
                current_class=class_instance, status='active'
            ).select_related('user').annotate(
                num_assignments=Coalesce(Subquery(assignment_count_sub, output_field=IntegerField()), Value(0)),
                num_assessments=Coalesce(Subquery(assessment_count_sub, output_field=IntegerField()), Value(0)),
                num_exams=Coalesce(Subquery(exam_count_sub, output_field=IntegerField()), Value(0)),
            ).annotate(
                term_submission_count=F('num_assignments') + F('num_assessments') + F('num_exams')
            ).annotate(
                rank=Window(expression=Rank(), order_by=F('term_submission_count').desc())
            ).order_by('rank', 'user__first_name')

            leaderboard_data[class_instance.id] = {
                'class_name': class_instance.name,
                'top_students': class_leaderboard_qs[:5]
            }
            
            leaderboard_data[class_instance.id] = {
                'class_name': class_instance.name,
                'school_level': class_instance.school_level,
                'top_students': class_leaderboard_qs[:5]
            }

    context = {
        'leaderboard_data': leaderboard_data,
        'display_term': display_term,
        'all_sessions': all_sessions,
        'all_terms': all_terms,
        'selected_session_id': int(selected_session_id) if selected_session_id else None,
        'selected_term_id': display_term.id if display_term else None,
    }
    return render(request, 'setup/leaderboard_list.html', context)

# === Post Management Views ===
class ManagePostListView(AdminRequiredMixin, ListView):
    model = Post
    template_name = 'blog/post_manage_list.html' 
    context_object_name = 'posts'
    paginate_by = 15
    ordering = ['-updated_at'] 

    def get_queryset(self):
        # Show all posts (drafts and published) for management
        return Post.objects.all().select_related('author').order_by(*self.ordering)

class PostCreateView(AdminRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/post_form.html' 
    success_url = reverse_lazy('post_manage_list') 

    def form_valid(self, form):
        form.instance.author = self.request.user 
        messages.success(self.request, "Blog post created successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Create New Blog Post"
        return context

class PostUpdateView(AdminRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/post_form.html'
    success_url = reverse_lazy('post_manage_list')

    def form_valid(self, form):
        messages.success(self.request, "Blog post updated successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Edit Post: {self.object.title}"
        return context

class PostDeleteView(AdminRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/post_confirm_delete.html' 
    success_url = reverse_lazy('post_list')

    def form_valid(self, form): # Or post method for DeleteView
        messages.success(self.request, f"Blog post '{self.object.title}' deleted successfully.")
        return super().form_valid(form)


# ===  Category Management Views (Similar Structure) ===
class ManageCategoryListView(AdminRequiredMixin, ListView):
    model = Category
    template_name = 'blog/category_manage_list.html'
    context_object_name = 'categories'
    paginate_by = 20

class CategoryCreateView(AdminRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'blog/category_form.html'
    success_url = reverse_lazy('category_manage_list')
    def form_valid(self, form):
        messages.success(self.request, "Category created successfully!")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Create New Category"
        return context

class CategoryUpdateView(AdminRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'blog/category_form.html'
    success_url = reverse_lazy('category_manage_list')
    def form_valid(self, form):
        messages.success(self.request, "Category updated successfully!")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Edit Category: {self.object.name}"
        return context


# === Tag Management Views (Similar Structure) ===
class ManageTagListView(AdminRequiredMixin, ListView):
    model = Tag
    template_name = 'blog/tag_manage_list.html'
    context_object_name = 'tags'
    paginate_by = 50

class TagCreateView(AdminRequiredMixin, CreateView):
    model = Tag
    form_class = TagForm
    template_name = 'blog/tag_form.html'
    success_url = reverse_lazy('tag_manage_list')
    def form_valid(self, form):
        messages.success(self.request, "Tag created successfully!")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Create New Tag"
        return context

class TagUpdateView(AdminRequiredMixin, UpdateView):
    model = Tag
    form_class = TagForm
    template_name = 'blog/tag_form.html'
    success_url = reverse_lazy('tag_manage_list')
    def form_valid(self, form):
        messages.success(self.request, "Tag updated successfully!")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Edit Tag: {self.object.name}"
        return context

