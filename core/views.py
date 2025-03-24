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
from decimal import Decimal
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

                results_data.append({
                    'student': student,
                    'subject_results': subject_results,
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
    template_name = 'fee_assignment/student_fee_record_list.html'
    context_object_name = 'student_fee_records'
    paginate_by = 200

    def get_queryset(self):
        self.sync_fee_records()
        # IMPORTANT: Provide an order_by to avoid UnorderedObjectListWarning
        return super().get_queryset() \
            .select_related('student', 'term', 'fee_assignment', 'student__current_class') \
            .order_by('student__current_class__name', 'student__user__last_name')

    def post(self, request, *args, **kwargs):
        # 1) Check if 'save_all' button was clicked
        if 'save_all' in request.POST:
            self.handle_save_all(request)
            return redirect('fee_assignment_list')  
        
        else:
            # 2) Otherwise, handle single-row updates
            action = request.POST.get('action')
            record_id = request.POST.get('record_id')
            if action == 'update_discount':
                discount_str = request.POST.get('discount', '0')
                self.update_discount(record_id, discount_str)
            elif action == 'update_waiver':
                self.update_waiver(record_id, 'waiver' in request.POST)
            # After single update, redirect or re-display the page
            return redirect(request.path)

    def handle_save_all(self, request):
        """
        Handle bulk saving of discount/waiver changes for all rows in the form.
        """
        # We'll parse all record_id and discount fields from the POST
        record_ids = request.POST.getlist('record_id')
        actions = request.POST.getlist('action')
        discounts = request.POST.getlist('discount')
        waived_ids = request.POST.getlist('waiver')

        # Each row has the same 'name' attributes, so they appear as parallel lists
        discount_index = 0  # We'll only increment this when we see a discount action

        for i, rid in enumerate(record_ids):
            record = StudentFeeRecord.objects.get(pk=rid)
            if actions[i] == 'update_discount':
                # Use the next discount value
                discount_str = discounts[discount_index] if discount_index < len(discounts) else '0'
                discount_index += 1
                record.discount = Decimal(discount_str)
            elif actions[i] == 'update_waiver':
                # Check if this record_id was submitted in 'waiver'
                waived_ids = request.POST.getlist('waiver')
                record.waiver = (rid in waived_ids)
                record.save()

            record.net_fee = record.calculate_net_fee()
            record.save()

    def update_discount(self, record_id, discount_str):
        """Handle a single discount update for a specific record."""
        try:
            record = StudentFeeRecord.objects.get(pk=record_id)
        except StudentFeeRecord.DoesNotExist:
            return
        record.discount = Decimal(discount_str or '0.00')
        record.net_fee = record.calculate_net_fee()
        record.save()

    def update_waiver(self, record_id, waiver_checked):
        """Handle a single waiver update for a specific record."""
        try:
            record = StudentFeeRecord.objects.get(pk=record_id)
        except StudentFeeRecord.DoesNotExist:
            return
        record.waiver = waiver_checked
        record.net_fee = record.calculate_net_fee()
        record.save()

    def sync_fee_records(self):
        """Ensure fee records exist for all students and update if necessary."""
        all_students = Student.objects.filter(current_class__isnull=False)

        for student in all_students:
            fee_assignments = FeeAssignment.objects.filter(class_instance=student.current_class)
            
            for assignment in fee_assignments:
                record, created = StudentFeeRecord.objects.get_or_create(
                    student=student,
                    term=assignment.term,
                    defaults={
                        'fee_assignment': assignment,
                        'amount': assignment.amount,
                        'discount': Decimal('0.00'),
                        'waiver': False,
                        'net_fee': assignment.calculate_net_fee(assignment.amount, Decimal('0.00'), False),
                    }
                )

                # If the record already existed, update fields if necessary
                if not created:
                    updated = False
                    if record.fee_assignment != assignment:
                        record.fee_assignment = assignment
                        updated = True
                    if record.amount != assignment.amount:
                        record.amount = assignment.amount
                        updated = True
                    if record.net_fee != record.calculate_net_fee():
                        record.net_fee = record.calculate_net_fee()
                        updated = True
                    
                    if updated:
                        record.save()

                
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student_fee_records = context['student_fee_records']

        # Group records by class and sort classes by name
        class_records = {}
        for record in student_fee_records:
            class_name = record.student.current_class.name
            if class_name not in class_records:
                class_records[class_name] = []
            class_records[class_name].append(record)

        # Sort the classes in ascending order
        sorted_class_records = dict(sorted(class_records.items(), key=lambda item: item[0]))

        # Paginate each class group
        paginated_class_records = {}
        for class_name, records in sorted_class_records.items():
            paginator = Paginator(records, self.paginate_by)
            page_number = self.request.GET.get(f'page_{class_name}', 1)
            paginated_class_records[class_name] = paginator.get_page(page_number)

        # Include session and term in the context
        context['paginated_class_records'] = paginated_class_records
        context['term'] = Term.objects.first()  # Replace with logic to retrieve the current term
        context['session'] = context['term'].session if context['term'] else None  # Assumes Term has a 'session' field
        return context

# Payment Record Management
class PaymentListView(AdminRequiredMixin, ListView):
    model = Payment
    template_name = 'payment/payment_list.html'
    context_object_name = 'payments'
    ordering = ['-payment_date']  # Order by payment date descending

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Calculate total payments
        context['total_payment'] = Payment.objects.aggregate(total=Sum('amount_paid'))['total'] or 0

        # Calculate total outstanding balance by summing balances from all financial records
        context['total_outstanding_balance'] = (
            FinancialRecord.objects.aggregate(total=Sum('outstanding_balance'))['total'] or 0
        )

        # Prepare payment list with outstanding balance for each payment
        for payment in context['payments']:
            payment.outstanding_balance = (
                payment.financial_record.outstanding_balance 
                if payment.financial_record else None
            )

        return context

class PaymentCreateView(CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'payment/create_payment.html'

    def form_valid(self, form):
        payment = form.save(commit=False)
        student = payment.student
        term = payment.term

        # Get or create FinancialRecord using get_or_create to avoid race conditions
        financial_record, created = FinancialRecord.objects.get_or_create(
            student=student,
            term=term,
            defaults={
                'total_fee': 0,
                'total_discount': 0,
                'total_paid': 0,
                'outstanding_balance': 0
            }
        )

        # Update FinancialRecord from StudentFeeRecord
        student_fee_record = StudentFeeRecord.objects.filter(student=student, term=term).first()

        if student_fee_record:
            financial_record.total_fee = student_fee_record.net_fee
            financial_record.total_discount = student_fee_record.discount
            financial_record.save()

        payment.financial_record = financial_record
        
        try:
            payment.save()  
        except ValidationError as e:
            # Add the error message to the form so it displays nicely
            form.add_error(None, e.messages)
            return self.form_invalid(form)

        self.update_financial_record(financial_record)
        messages.success(self.request, 'Payment recorded successfully.')
        return redirect(self.get_success_url())

    def update_financial_record(self, financial_record):
        """
        Updates the financial record with the current payment information.
        """
        total_paid = financial_record.payments.aggregate(total=Sum('amount_paid'))['total'] or 0
        financial_record.total_paid = total_paid
        financial_record.outstanding_balance = max(financial_record.total_fee - total_paid, 0)
        financial_record.save()

    def get_success_url(self):
        return reverse_lazy('payment_list')  # Adjust this URL to match your view names
    
class PaymentUpdateView(UpdateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'payment/update_payment.html'

    def form_valid(self, form):
        payment = form.save(commit=False)

        try:
            payment.save()
        except ValidationError as e:
            form.add_error(None, e.message if hasattr(e, 'message') else e.messages)
            return self.form_invalid(form)
        
        # Recalculate the financial record after updating the payment.
        self.update_financial_record(payment.financial_record)

        messages.success(self.request, 'Payment updated successfully.')
        return redirect(self.get_success_url())

    def update_financial_record(self, financial_record):
        total_paid = financial_record.payments.aggregate(total=Sum('amount_paid'))['total'] or 0
        financial_record.total_paid = total_paid
        financial_record.outstanding_balance = max(financial_record.total_fee - total_paid, 0)
        financial_record.save()

    def get_success_url(self):
        return reverse('payment_list')  # Adjust the URL name as needed
    
class PaymentDetailView(DetailView):
    model = Payment
    template_name = 'payment/payment_detail.html'
    context_object_name = 'payment'

class PaymentDeleteView(DeleteView):
    model = Payment
    template_name = 'payment/delete_payment.html'

    def delete(self, request, *args, **kwargs):
        payment = self.get_object()
        financial_record = payment.financial_record
        
        # Delete the payment
        response = super().delete(request, *args, **kwargs)
        
        financial_record.refresh_from_db()
        financial_record.total_paid = financial_record.payments.aggregate(total=Sum('amount_paid'))['total'] or 0
        financial_record.outstanding_balance = max(financial_record.total_fee - financial_record.total_paid, 0)
        financial_record.save()

        messages.success(request, 'Payment deleted successfully.')
        return response

    def get_success_url(self):
        return reverse_lazy('payment_list')  # Adjust the URL name as needed
    
class FinancialRecordListView(ListView):
    model = FinancialRecord
    template_name = 'financial_record/financial_record_list.html'
    context_object_name = 'financial_records'

    def get_queryset(self):
        # Fetch financial records for all students with related fields preloaded for optimization
        return FinancialRecord.objects.order_by('student__user__last_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        
        # Calculate summary statistics: total fee, discount, paid amount, and outstanding balance across all records
        context['total_fee'] = qs.aggregate(total_fee=Sum('total_fee'))['total_fee'] or 0
        context['total_discount'] = qs.aggregate(total_discount=Sum('total_discount'))['total_discount'] or 0
        context['total_paid'] = Payment.objects.aggregate(total=Sum('amount_paid'))['total'] or 0
        print(context['total_paid'])
        context['total_outstanding_balance'] = qs.aggregate(total_outsanding_balance=Sum('outstanding_balance'))['total_outsanding_balance'] or 0

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