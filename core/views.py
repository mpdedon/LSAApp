from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.db import IntegrityError, transaction
from django.db.models import Sum, Count, Max, F, Q
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, TemplateView, FormView
from django.core.paginator import Paginator
from django.http import Http404
from django.core.mail import send_mail
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
from core.models import Session, Term, Student, Teacher, Guardian, Notification
from core.models import Class, Subject, FeeAssignment, Enrollment, Payment
from core.models import SubjectAssignment, TeacherAssignment, ClassSubjectAssignment
from core.models import SubjectResult, Result, StudentFeeRecord, FinancialRecord
from core.forms import ClassSubjectAssignmentForm, NonAcademicSkillsForm, NotificationForm
from core.session.forms import SessionForm
from core.term.forms import TermForm
from core.subject.forms import SubjectForm
from core.fee_assignment.forms import FeeAssignmentForm, StudentFeeRecordForm
from core.payment.forms import PaymentForm
from core.enrollment.forms import EnrollmentForm
from core.subject_assignment.forms import SubjectAssignmentForm
from core.teacher_assignment.forms import TeacherAssignmentForm


# Create your views here.

def home(request):
    return render(request, 'home.html')

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

class CreateNotificationView(CreateView):
    template_name = 'create_notification.html'

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
    if notification.audience in ['all', 'guardian']:
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

# Class and Teacher Assignment Views
class AssignTeacherView(AdminRequiredMixin, CreateView):
    model = TeacherAssignment
    template_name = 'setup/assign_teacher.html'
    fields = ['teacher', 'class_assigned']

class AssignSubjectView(AdminRequiredMixin, CreateView):
    model = SubjectAssignment
    template_name = 'setup/assign_subject.html'
    fields = ['subject', 'teacher', 'class_assigned']


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
        # Log all incoming GET parameters
        print(f"GET parameters: {request.GET}")  # Debugging line
        print('Name')
        search_query = request.GET.get('q', '').strip()
        print(f"Search Query: {search_query}")  # Debugging line

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
    
class AssignClassSubjectView(AdminRequiredMixin, CreateView):
    def get(self, request, pk):
        class_instance = get_object_or_404(Class, pk=pk)
        form = ClassSubjectAssignmentForm()  # Initialize your form here
        if form.is_valid():
            subjects = form.cleaned_data['subjects']
            session = form.cleaned_data['session']
            term = form.cleaned_data['term']

            for subject in subjects:
                ClassSubjectAssignment.objects.get_or_create(
                    class_assigned=class_instance,
                    subject=subject,
                    session=session,
                    term=term
                )
            class_instance.save(subjects=subjects)
            return redirect('class_list', pk=class_instance.pk)
        
        return render(request, 'setup/assign_class_subjects.html', {
            'form': form,
            'class_instance': class_instance,
        })

    def post(self, request, pk):
        class_instance = get_object_or_404(Class, pk=pk)
        form = ClassSubjectAssignmentForm(request.POST)

        if form.is_valid():
            subjects = form.cleaned_data['subjects']
            session = form.cleaned_data['session']
            term = form.cleaned_data['term']

            for subject in subjects:
                ClassSubjectAssignment.objects.get_or_create(
                    class_assigned=class_instance,
                    subject=subject,
                    session=session,
                    term=term
                )
            return redirect('class_detail', pk=class_instance.pk)
        
        return render(request, 'setup/assign_class_subjects.html', {
            'form': form,
            'class_instance': class_instance,
        })

class DeleteClassSubjectAssignmentView(AdminRequiredMixin, DeleteView):
    def post(self, request, pk):
        assignment = get_object_or_404(ClassSubjectAssignment, pk=pk)
        class_pk = assignment.class_assigned.pk  # Preserve the class ID for redirection
        assignment.delete()
        return redirect('class_detail', pk=class_pk) 
    
@login_required
def approve_broadsheets(request):
    if not request.user.is_staff:
        return redirect('teacher_dashboard')

    terms = Term.objects.all()
    class_instances = Class.objects.all()
    context = {
        'terms': terms,
        'class_instances': class_instances,
    }
    return render(request, 'approve_broadsheets.html', context)

@login_required
def approve_results(request, class_id):
    class_instance = get_object_or_404(Class, id=class_id)
    subject_results = SubjectResult.objects.filter(result__term=class_instance.term)

    if request.method == 'POST':
        subject_results.update(is_finalized=True)
        return redirect('approve_broadsheets')

    context = {
        'class_instance': class_instance,
        'subject_results': subject_results,
    }
    return render(request, 'approve_results.html', context)

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
    paginate_by = 20  # Adjust the number of records per page as needed
    
    def get_queryset(self):
        # Synchronize records
        self.sync_fee_records()
        return super().get_queryset().select_related('student', 'term', 'fee_assignment', 'student__current_class')

    def sync_fee_records(self):
        """Ensure fee records exist for all students."""
        all_students = Student.objects.filter(current_class__isnull=False)  # Only students with a class
        for student in all_students:
            fee_assignments = FeeAssignment.objects.filter(class_instance=student.current_class)
            for assignment in fee_assignments:
                StudentFeeRecord.objects.get_or_create(
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
        
        # Check if a FinancialRecord for this student and term exists
        financial_record = FinancialRecord.objects.filter(
            student_id=payment.student_id,
            term_id=payment.term_id
        ).first()
        
        if not financial_record:
            # Create FinancialRecord with calculated fields and unique ID handling
            try:
                with transaction.atomic():
                    # Ensure no duplicate ID by handling it manually
                    max_id = FinancialRecord.objects.aggregate(max_id=Max('id'))['max_id'] or 0
                    next_id = max_id + 1

                    # Calculate fields for the FinancialRecord based on StudentFeeRecord data
                    student_fee_record = StudentFeeRecord.objects.filter(
                        student=payment.student,
                        term=payment.term
                    ).first()
                    
                    total_fee = student_fee_record.net_fee if student_fee_record else 0
                    total_discount = student_fee_record.discount if student_fee_record else 0

                    financial_record = FinancialRecord(
                        id=next_id,
                        student=payment.student,
                        term=payment.term,
                        total_fee=total_fee,
                        total_discount=total_discount,
                        total_paid=0,
                        outstanding_balance=total_fee  # Initially full amount is unpaid
                    )
                    financial_record.save()
                    print("Debug: New FinancialRecord created.")

            except IntegrityError:
                # Handle a case where the unique constraint fails again by retrying the process
                messages.error(self.request, "Error creating Financial Record. Please try again.")
                return redirect(self.get_success_url())
        else:
            print("Debug: Existing FinancialRecord retrieved.")

        # Link payment to financial record and save
        payment.financial_record = financial_record
        payment.save()

        # Update financial record totals after payment save
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
        payment = form.save()
        
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
        
        # Update the financial record after the payment is deleted.
        self.update_financial_record(financial_record)

        messages.success(request, 'Payment deleted successfully.')
        return response

    def update_financial_record(self, financial_record):
        total_paid = financial_record.payments.aggregate(total=Sum('amount_paid'))['total'] or 0
        financial_record.total_paid = total_paid
        financial_record.outstanding_balance = max(financial_record.total_fee - total_paid, 0)
        financial_record.save()

    def get_success_url(self):
        return reverse_lazy('payment_list')  # Adjust the URL name as needed
    
class FinancialRecordListView(ListView):
    model = FinancialRecord
    template_name = 'financial_record/financial_record_list.html'
    context_object_name = 'financial_records'

    def get_queryset(self):
        # Fetch financial records for all students with related fields preloaded for optimization
        return FinancialRecord.objects.annotate(total_paid_amount=Sum('payments__amount_paid')).order_by('student__user__last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate summary statistics: total fee, discount, paid amount, and outstanding balance across all records
        context['total_fee'] = self.get_queryset().aggregate(total_fee=Sum('total_fee'))['total_fee'] or 0
        context['total_discount'] = self.get_queryset().aggregate(total_discount=Sum('total_discount'))['total_discount'] or 0
        context['total_paid'] = self.get_queryset().aggregate(total_paid=Sum('total_paid'))['total_paid'] or 0
        context['total_outstanding_balance'] = self.get_queryset().aggregate(
            total_outstanding_balance=Sum('outstanding_balance')
        )['total_outstanding_balance'] or 0

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
