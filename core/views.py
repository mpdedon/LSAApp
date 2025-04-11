import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse, reverse_lazy
from django.db import IntegrityError, transaction
from django.db.models import Sum, Max, Q
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, TemplateView, FormView
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest, JsonResponse
from django.core.mail import send_mail
from django.shortcuts import HttpResponse
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from core.models import Session, Term, Student, Teacher, Guardian, Notification
from core.models import Class, Subject, FeeAssignment, Enrollment, Payment, Assessment, Exam
from core.models import SubjectAssignment, TeacherAssignment, ClassSubjectAssignment
from core.models import SubjectResult, Result, StudentFeeRecord, FinancialRecord, AcademicAlert
from core.forms import ClassSubjectAssignmentForm, NonAcademicSkillsForm, NotificationForm
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
import logging

logger = logging.getLogger(__name__)

# Create your views here.

def home(request):
    return render(request, 'home.html')

from django.views.generic import TemplateView

def programs(request):
    return render(request, 'programs.html')

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
            print('Form is Valid')
            form.save()
            return redirect('subject_list')
        else:
            print(form.errors)
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
                    print("Form saved successfully")  # Debug print to confirm form is saved
                    return redirect('teacher_assignment_list')  # Redirect on successful save
                except IntegrityError as e:
                    error_message = f"A unique constraint error occurred: {str(e)}"
        else:
            print("Form is invalid")
            print(form.errors)  # Print the form errors to debug

    else:
        form = TeacherAssignmentForm()

    context = {
        'form': form,
        'error_message': error_message,
    }

    return render(request, 'setup/assign_teacher.html', context)

class TeacherAssignmentListView(AdminRequiredMixin, ListView):
    template_name = 'teacher_assignment/teacher_assignment_list.html'

    def get(self, request):
        teacher_assignments = TeacherAssignment.objects.all()
        return render(request, self.template_name, {'teacher_assignments': teacher_assignments})

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
            print("Applying filters...")
            subject_assignments = subject_assignments.filter(
                Q(teacher__user__first_name__icontains=search_query) |
                Q(teacher__user__last_name__icontains=search_query) |
                Q(subject__name__icontains=search_query) |
                Q(class_assigned__name__icontains=search_query)
            )
            print(f"Filtered Results: {subject_assignments}")  # Debugging line

        paginator = Paginator(subject_assignments, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'search_query': search_query,
        })
    
class AssignClassSubjectView(CreateView, AdminRequiredMixin): 
    template_name = 'setup/assign_class_subjects.html'

    def get(self, request, pk):
        """Display the form with pre-selected subjects for the class."""
        class_instance = get_object_or_404(Class, pk=pk)
        current_session = Session.objects.filter(is_active=True).first()
        current_term = Term.objects.filter(is_active=True).first()
        assigned_subject_ids = ClassSubjectAssignment.objects.filter(
            class_assigned=class_instance,
            session=current_session,
            term=current_term
        ).values_list('subject_id', flat=True)
        form = ClassSubjectAssignmentForm(initial={
            'subjects': list(assigned_subject_ids),
            'session': current_session,
            'term': current_term,
        })
        return render(request, self.template_name, {'form': form, 'class_instance': class_instance, 'session': current_session, 'term': current_term})

    def post(self, request, pk):
        """Handle the form submission to assign subjects."""
        class_instance = get_object_or_404(Class, pk=pk)
        form = ClassSubjectAssignmentForm(request.POST)

        if form.is_valid():
            selected_subjects = form.cleaned_data['subjects']
            session = form.cleaned_data['session']
            term = form.cleaned_data['term']

            # Remove unselected subjects for this session and term
            ClassSubjectAssignment.objects.filter(
                class_assigned=class_instance, session=session, term=term
            ).exclude(subject__in=selected_subjects).delete()

            # Add new subjects
            for subject in selected_subjects:
                assignment, created = ClassSubjectAssignment.objects.get_or_create(
                    class_assigned=class_instance,
                    subject=subject,
                    session=session,
                    term=term
                )
                assignment.save()
                # print(subject, 'assigned to', class_instance)

            return redirect(reverse('class_subjects'))

        logger.error(f"Form is invalid: {form.errors}")
        return render(request, self.template_name, {'form': form, 'class_instance': class_instance})


def class_subjects(request): 
    classes = Class.objects.all()
    current_session = Session.objects.filter(is_active=True).first()
    current_term = Term.objects.filter(is_active=True).first()

    class_subjects_data = []

    for class_instance in classes:
        subjects = Subject.objects.filter(
            class_assignments__class_assigned=class_instance,
            class_assignments__session=current_session,
            class_assignments__term=current_term
        ).distinct()

        class_subjects_data.append({
            'class': class_instance,
            'subjects': subjects
        })

    return render(request, 'setup/class_subjects.html', {'class_subjects_data': class_subjects_data})


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
    terms = Term.objects.order_by('-start_date')  # Latest terms first
    paginator = Paginator(terms, 6)  # Paginate (5 terms per page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'setup/all_broadsheets.html', {'page_obj': page_obj})

@login_required
def view_broadsheet(request, term_id):
    session = Session.objects.get(is_active=True)
    term = get_object_or_404(Term, id=term_id)

    # Check which classes these students belong to
    classes = Class.objects.filter(enrolled_students__result__term=term).distinct()

    broadsheets = []
    for class_obj in classes:
        students = class_obj.enrolled_students.all()
        subjects = Subject.objects.filter(
            class_assignments__class_assigned=class_obj,
            class_assignments__session=session,
            class_assignments__term=term
        ).distinct()

        results_data = []

        for student in students:
            result = Result.objects.filter(student=student, term=term).first()
            if result:
                subject_results = result.subjectresult_set.all()
                gpa = result.calculate_gpa()
                total_score = sum(sr.total_score() for sr in subject_results)

                subject_results_dict = {sr.subject.id: sr for sr in subject_results}

                results_data.append({
                    'student': student,
                    'subject_results': subject_results_dict,
                    'gpa': gpa,
                    'total_score': total_score,
                    'is_approved': result.is_approved,
                })
        # Sort students by total score and GPA
        results_data.sort(key=lambda x: (-x['total_score'], -x['gpa']))

        broadsheets.append({
            'class': class_obj,
            'students': students,
            'subjects': subjects,
            'results_data': results_data,
            'is_approved': all(r['is_approved'] for r in results_data),  # Check if all results in the class are approved
        })

    context = {
        'term': term,
        'broadsheets': broadsheets,
    }
    return render(request, 'setup/view_broadsheet.html', context)


@login_required
def approve_broadsheet(request, term_id, class_id):
    term = get_object_or_404(Term, id=term_id)
    class_obj = get_object_or_404(Class, id=class_id)
    results = Result.objects.filter(student__in=class_obj.enrolled_students.all(), term=term)

    if request.method == "POST":
        updated_status = results.update(is_approved=True)
        print(f"Updated {updated_status} Results")
        return JsonResponse({'message': f"Broadsheet for {class_obj.name} approved!"})

    return JsonResponse({'error': "Invalid request"}, status=400)


@login_required
def archive_broadsheet(request, term_id):
    term = get_object_or_404(Term, id=term_id)
    results = Result.objects.filter(term=term)

    if request.method == "POST":
        results.update(is_archived=True)
        return JsonResponse({'message': f"Broadsheet for {term.name} archived!"})

    return JsonResponse({'error': "Invalid request"}, status=400)


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
            print("Sync aborted: No active term provided.") # Use logging in production
            return

        term_assignments = FeeAssignment.objects.filter(term=active_term).select_related('class_instance')
        if not term_assignments.exists():
            print(f"Sync Info: No fee assignments found for active term {active_term}.")
            return # Nothing to assign

        assignments_by_class_id = {fa.class_instance_id: fa for fa in term_assignments}

        # Use Student PK ('id') for clarity and robustness
        students_in_assigned_classes = Student.objects.filter(
            current_class_id__in=assignments_by_class_id.keys(),
            status='active' # Optional: Only sync for active students?
        ).values_list('user_id', 'current_class_id') # Get Student PK

        student_map = {s_id: c_id for s_id, c_id in students_in_assigned_classes}
        if not student_map:
            print(f"Sync Info: No active students found in classes with assignments for term {active_term}.")
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
                # Use print for dev, logging for prod
                print(f"Sync: Created {len(created_records)} new StudentFeeRecords.")
                # messages.info(self.request, f"Created {len(created_records)} new fee records.") # Avoid messages in sync logic
            except IntegrityError as e:
                 # Handle potential unique constraint violations if sync runs concurrently (unlikely here)
                 print(f"Sync Error during bulk_create: {e}")
                 # Optionally re-fetch or handle differently
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
        # (Keep the existing get_queryset method from previous version - it fetches and groups)
        active_term = self.get_active_term()
        if not active_term:
            return {}

        self.sync_fee_records(active_term)

        queryset = StudentFeeRecord.objects.filter(term=active_term) \
            .select_related('student__user', 'term', 'student__current_class') \
            .order_by('student__current_class__name', 'student__user__last_name')

        class_records_grouped = {}
        for record in queryset:
            if record.student.current_class:
                class_obj = record.student.current_class
                class_id = class_obj.id
                class_name = class_obj.name
                if class_id not in class_records_grouped:
                    class_records_grouped[class_id] = {'name': class_name, 'records': []}
                class_records_grouped[class_id]['records'].append(record)

        return class_records_grouped


    def get_context_data(self, **kwargs):
        # (Keep the existing get_context_data method from previous version)
        context = super().get_context_data(**kwargs)
        active_term = self.get_active_term()
        context['term'] = active_term
        context['session'] = active_term.session if active_term else None
        context.pop('object_list', None) # Remove default ListView context if present
        return context

    @transaction.atomic # Process all updates for a class atomically
    def post(self, request, *args, **kwargs):
        """Handle saving changes for a specific class submitted via its form."""
        submitted_class_id_str = request.POST.get('submitted_class_id')
        active_term = self.get_active_term() # Needed for context if redirecting on error

        if not active_term:
             messages.error(request, "Cannot process submission: Active term not found.")
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
            term=active_term # Ensure correct term
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
        redirect_url = reverse('student_fee_record_list') + f'#collapse-{submitted_class_id}'
        return redirect(redirect_url)

# Payment Record Management
class PaymentListView(AdminRequiredMixin, ListView):
    model = Payment
    template_name = 'payment/payment_list.html'
    context_object_name = 'payments'
    ordering = ['-payment_date', '-pk'] # Order by date then pk
    paginate_by = 50 # Add pagination

    def get_queryset(self):
        # Prefetch related financial record and student details for efficiency
        return super().get_queryset().select_related(
            'financial_record__student__user',
            'financial_record__term__session'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_term = Term.objects.filter(is_active=True).first() # Get current term for summary
        # Recalculate totals based on ALL records for overall summary
        all_records = FinancialRecord.objects.all()
        context['total_fee'] = all_records.aggregate(total=Sum('total_fee'))['total'] or Decimal('0.00')
        context['total_discount'] = all_records.aggregate(total=Sum('total_discount'))['total'] or Decimal('0.00')
        # Total paid sum from financial records is more reliable than summing all payments directly
        context['total_paid'] = all_records.aggregate(total=Sum('total_paid'))['total'] or Decimal('0.00')
        context['total_outstanding_balance'] = all_records.aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0.00')
        context['active_term'] = active_term # Pass active term if needed for display/filtering
        
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

# --- Financial Record List View (Refactored) ---
class FinancialRecordListView(AdminRequiredMixin, ListView):
    model = FinancialRecord
    template_name = 'financial_record/financial_record_list.html'
    context_object_name = 'financial_records'
    paginate_by = 50 # Add pagination

    def get_queryset(self):
        # Preload related fields for optimization
        return FinancialRecord.objects.select_related(
            'student__user',
            'term__session'
        ).order_by('-term__start_date', 'student__user__last_name') # Order by term then name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Use the paginated queryset for calculations if needed, or all records for global totals
        all_records = FinancialRecord.objects.all() # For global totals

        # Calculate summary statistics using the reliable values from FinancialRecord
        context['total_fee'] = all_records.aggregate(total=Sum('total_fee'))['total'] or Decimal('0.00')
        context['total_discount'] = all_records.aggregate(total=Sum('total_discount'))['total'] or Decimal('0.00')
        context['total_paid'] = all_records.aggregate(total=Sum('total_paid'))['total'] or Decimal('0.00')
        context['total_outstanding_balance'] = all_records.aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0.00')

        # Add active term/session if needed for filtering/display
        active_term = Term.objects.filter(is_active=True).first()
        context['active_term'] = active_term
        context['active_session'] = active_term.session if active_term else None

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


@login_required
def create_assessment(request):
    # Ensure the logged-in user is authorized
    user = request.user
    teacher = None
    if not user.is_superuser:
        teacher = get_object_or_404(Teacher, user=user)
        assigned_classes = teacher.assigned_classes().all()
        subjects = teacher.assigned_subjects().all()
    else:
        assigned_classes = Class.objects.all()
        subjects = Subject.objects.all()

    # Handle GET request: render form
    if request.method == 'GET':
        form = AssessmentForm()
        form.fields['class_assigned'].queryset = assigned_classes
        form.fields['subject'].queryset = subjects
        return render(request, 'assessment/create_assessment.html', {'form': form})

    # Handle POST request: process form data
    if request.method == 'POST':
        form = AssessmentForm(request.POST)

        # Limit class and subject choices for teachers
        form.fields['class_assigned'].queryset = assigned_classes
        form.fields['subject'].queryset = subjects

        if form.is_valid():
            # Save the assessment instance
            assessment = form.save(commit=False)
            assessment.created_by = user
            assessment.is_approved = user.is_superuser  # Auto-approve if admin
            assessment.due_date = form.cleaned_data['due_date']
            assessment.duration = form.cleaned_data['duration']
            assessment.save()
            form.save_m2m()  # Save many-to-many questions

            # Process and validate questions dynamically
            errors = process_questions(request, assessment)

            if not errors:
                # Notify students if the assessment is approved
                if assessment.is_approved:
                    notify_students(assessment)
                return redirect('teacher_dashboard' if teacher else 'admin_dashboard')
            else:
                print("Errors in questions:", errors)  # Debugging line
                return render(request, 'assessment/create_assessment.html', {
                    'form': form,
                    'errors': errors,
                })
        else:
            print("Form errors:", form.errors)  # Debugging line
            return render(request, 'assessment/create_assessment.html', {
                'form': form,
                'errors': form.errors,  # Add form errors to be displayed in the template
            })

                  
def process_questions(request, assessment):
    errors = []
    question_number = 1

    while f'question_type_{question_number}' in request.POST:
        question_type = request.POST.get(f'question_type_{question_number}')
        question_text = request.POST.get(f'question_text_{question_number}')
        options = request.POST.get(f'options_{question_number}', '')
        correct_answer = request.POST.get(f'correct_answer_{question_number}')

        print(f"Processing Question {question_number}: {question_type}, {question_text}, {options}, {correct_answer}")  # Debugging line

        options_list = [opt.strip() for opt in options.split(',') if opt.strip()]
        question_data = {
            'question_type': question_type,
            'question_text': question_text,
            'options': json.dumps(options_list) if options_list else '',
            'correct_answer': correct_answer
        }

        question_form = OnlineQuestionForm(question_data)
        if question_form.is_valid():
            if question_type in ['SCQ', 'MCQ']:
                if not options_list:
                    errors.append(f"Error in Question {question_number}: Options are required for SCQ/MCQ.")
                else:
                    question_form.save()
                    assessment.questions.add(question_form.instance)
            elif question_type == 'ES':
                question_form.save()
                assessment.questions.add(question_form.instance)
        else:
            print(f"Question {question_number} Errors: {question_form.errors}")  # Debugging line
            errors.append(f"Error in Question {question_number}: {question_form.errors}")
        question_number += 1

    return errors

def notify_students(assessment):
    students = Student.objects.filter(current_class=assessment.class_assigned)
    for student in students:
        AcademicAlert.objects.create(
            alert_type='assessment',
            title=assessment.title,
            summary=assessment.short_description or 'New assessment available!',
            teacher=assessment.created_by,
            student=student,
            due_date=assessment.due_date,
            duration=assessment.duration,
            related_object_id=assessment.id
        )

@login_required
@user_passes_test(lambda u: u.is_superuser)
def approve_assessment(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id, is_approved=False)
    if request.method == 'POST':
        assessment.is_approved = True
        assessment.approved_by = request.user
        assessment.save()
        notify_students(assessment)
        messages.success(request, f"Assessment '{assessment.title}' approved and published!")
        return redirect('admin_dashboard')

    return render(request, 'setup/approve_assessment.html', {'assessment': assessment})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_assessment_list(request):
    assessments = Assessment.objects.all()
    return render(request, 'assessment/admin_assessment_list.html', {'assessments': assessments})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def pending_approvals(request):
    pending_assessments = Assessment.objects.filter(is_approved=False)
    return render(request, 'setup/pending_assessments.html', {'pending_assessments': pending_assessments})

@login_required
def view_assessment(request, assessment_id):
    # Retrieve the assessment and its questions
    assessment = get_object_or_404(Assessment, id=assessment_id)
    questions = assessment.questions.all()

    context = {
        'assessment': assessment,
        'questions': questions,
    }
    return render(request, 'assessment/assessment_detail.html', context)


@login_required
def create_exam(request):
    # Ensure the logged-in user is authorized
    user = request.user
    teacher = None
    if not user.is_superuser:
        teacher = get_object_or_404(Teacher, user=user)
        assigned_classes = teacher.assigned_classes().all()
        subjects = teacher.assigned_subjects().all()
    else:
        assigned_classes = Class.objects.all()
        subjects = Subject.objects.all()

    # Handle GET request: render form
    if request.method == 'GET':
        form = ExamForm()
        form.fields['class_assigned'].queryset = assigned_classes
        form.fields['subject'].queryset = subjects
        return render(request, 'exam/create_exam.html', {'form': form})

    # Handle POST request: process form data
    if request.method == 'POST':
        form = ExamForm(request.POST)

        # Limit class and subject choices for teachers
        form.fields['class_assigned'].queryset = assigned_classes
        form.fields['subject'].queryset = subjects

        if form.is_valid():
            # Save the Exam instance
            exam = form.save(commit=False)
            exam.created_by = user
            exam.is_approved = user.is_superuser  # Auto-approve if admin
            exam.due_date = form.cleaned_data['due_date']
            exam.duration = form.cleaned_data['duration']
            exam.save()
            form.save_m2m()  # Save many-to-many questions

            # Process and validate questions dynamically
            errors = process_questions(request, exam)

            if not errors:
                # Notify students if the exam is approved
                if exam.is_approved:
                    notify_students(exam)
                return redirect('teacher_dashboard' if teacher else 'admin_dashboard')
            else:
                print("Errors in questions:", errors)  # Debugging line
                return render(request, 'exam/create_exam.html', {
                    'form': form,
                    'errors': errors,
                })
        else:
            print("Form errors:", form.errors)  # Debugging line
            return render(request, 'exam/create_exam.html', {
                'form': form,
                'errors': form.errors,  # Add form errors to be displayed in the template
            })

                  
def process_questions(request, exam):
    errors = []
    question_number = 1

    while f'question_type_{question_number}' in request.POST:
        question_type = request.POST.get(f'question_type_{question_number}')
        question_text = request.POST.get(f'question_text_{question_number}')
        options = request.POST.get(f'options_{question_number}', '')
        correct_answer = request.POST.get(f'correct_answer_{question_number}')

        print(f"Processing Question {question_number}: {question_type}, {question_text}, {options}, {correct_answer}")  # Debugging line

        options_list = [opt.strip() for opt in options.split(',') if opt.strip()]
        question_data = {
            'question_type': question_type,
            'question_text': question_text,
            'options': json.dumps(options_list) if options_list else '',
            'correct_answer': correct_answer
        }

        question_form = OnlineQuestionForm(question_data)
        if question_form.is_valid():
            if question_type in ['SCQ', 'MCQ']:
                if not options_list:
                    errors.append(f"Error in Question {question_number}: Options are required for SCQ/MCQ.")
                else:
                    question_form.save()
                    exam.questions.add(question_form.instance)
            elif question_type == 'ES':
                question_form.save()
                exam.questions.add(question_form.instance)
        else:
            print(f"Question {question_number} Errors: {question_form.errors}")  # Debugging line
            errors.append(f"Error in Question {question_number}: {question_form.errors}")
        question_number += 1

    return errors

def notify_students(exam):
    students = Student.objects.filter(current_class=exam.class_assigned)
    for student in students:
        AcademicAlert.objects.create(
            alert_type='exam',
            title=exam.title,
            summary=exam.short_description or 'New exam available!',
            teacher=exam.created_by,
            student=student,
            due_date=exam.due_date,
            duration=exam.duration,
            related_object_id=exam.id
        )

@login_required
@user_passes_test(lambda u: u.is_superuser)
def approve_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, is_approved=False)
    if request.method == 'POST':
        exam.is_approved = True
        exam.approved_by = request.user
        exam.save()
        notify_students(exam)
        messages.success(request, f"Exam '{exam.title}' approved and published!")
        return redirect('admin_dashboard')

    return render(request, 'setup/approve_exam.html', {'exam': exam})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_exam_list(request):
    exams = Exam.objects.all()
    return render(request, 'exam/admin_exam_list.html', {'exams': exams})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def pending_approvals(request):
    pending_exams = Exam.objects.filter(is_approved=False)
    return render(request, 'setup/pending_exams.html', {'pending_exams': pending_exams})

@login_required
def view_exam(request, exam_id):
    # Retrieve the exam and its questions
    exam = get_object_or_404(Exam, id=exam_id)
    questions = exam.questions.all()

    context = {
        'exam': exam,
        'questions': questions,
    }
    return render(request, 'exam/exam_detail.html', context)