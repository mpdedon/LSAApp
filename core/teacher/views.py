# views.py

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import models
from django.db.models import Q, Count, F, Sum, Subquery, OuterRef, IntegerField
from django.http import HttpResponseForbidden
from datetime import date
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from core.teacher.forms import TeacherRegistrationForm, MessageForm
from core.models import Teacher, Student, Guardian, Class, Subject, Attendance, Assessment, Exam
from core.models import Assignment, Question, AssignmentSubmission, AssessmentSubmission, ExamSubmission, AcademicAlert
from core.models import Session, Term, Message, SubjectResult, Result
from core.subject_result.form import SubjectResultForm
from core.forms import NonAcademicSkillsForm
from core.assignment.forms import AssignmentForm, QuestionForm
from core.assessment.forms import AssessmentForm, OnlineQuestionForm
from core.exams.forms import ExamForm, OnlineQuestion
import logging

logger = logging.getLogger(__name__)

# Teacher Views

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser
    
def teacher_required(function):
    def wrap(request, *args, **kwargs):
        if request.user.role == 'teacher': # Adjust role check as per your CustomUser
            return function(request, *args, **kwargs)
        else:
            messages.error(request, "You are not authorized to view this page.")
            return redirect('login') # Or appropriate redirect
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap
    
def TeacherRegisterView(request):
    if request.method == 'POST':
        form = TeacherRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('teacher_dashboard')
    else:
        form = TeacherRegistrationForm()
    return render(request, 'teacher/register.html', {'form': form})

def TeacherProfileView(request):
    if request.method == 'POST':
        form = TeacherRegistrationForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('teacher_dashboard')
    else:
        form = TeacherRegistrationForm(instance=request.user)
    return render(request, 'teacher/profile.html', {'form': form})
    
@login_required
@user_passes_test(lambda u: u.role == 'teacher')
def teacher_dashboard(request):
    teacher = Teacher.objects.get(user=request.user)
    current_class = teacher.current_class
    students = Student.objects.filter(current_class=current_class)
    subjects = current_class.subjects.all() if current_class else []
    
    context = {
        'teacher': teacher,
        'class': current_class,
        'students': students,
        'subjects': subjects,
    }
    return render(request, 'teacher/teacher_dashboard.html', context)

class TeacherListView(View, AdminRequiredMixin):
    template_name = 'teacher/teacher_list.html'

    def get(self, request, *args, **kwargs):
        status = request.GET.get('status', 'active')
        query = request.GET.get('q', '')

        teachers = Teacher.objects.filter(status=status).order_by('employee_id')

        if query:
            teachers = teachers.filter(
                Q(user__username__icontains=query)  |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__email__icontains=query) 
                                        )

        # Pagination
        paginator = Paginator(teachers, 20)  # Show 15 teachers per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'active_tab': status,
        })

class TeacherBulkActionView(View, AdminRequiredMixin):
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        selected_teachers = request.POST.getlist('selected_teachers')

        if not selected_teachers:
            messages.error(request, "No teachers selected for bulk action.")
            return redirect('teacher_list')

        teachers = Teacher.objects.filter(user__id__in=selected_teachers)

        if action == 'mark_active':
            teachers.update(status='active')
            messages.success(request, "Selected teachers marked as active.")
        elif action == 'mark_inactive':
            teachers.update(status='dormant')
            messages.success(request, "Selected teachers marked as dormant.")
        elif action == 'mark_left':
            teachers.update(status='left')
            messages.success(request, "Selected teachers marked left.")
        else:
            messages.error(request, "Invalid bulk action.")

        return redirect('teacher_list')
    
class TeacherCreateView(View):
    template_name = 'teacher/teacher_form.html'

    def get(self, request, *args, **kwargs):
        form = TeacherRegistrationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = TeacherRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('teacher_list')
        return render(request, self.template_name, {'form': form})

class TeacherUpdateView(View):
    template_name = 'teacher/teacher_form.html'

    def get(self, request, pk, *args, **kwargs):
        teacher = get_object_or_404(Teacher, pk=pk)
        form = TeacherRegistrationForm(instance=teacher.user, teacher_instance=teacher)
        return render(request, self.template_name, {'form': form, 'is_update': True, 'teacher': teacher})

    def post(self, request, pk, *args, **kwargs):
        teacher = get_object_or_404(Teacher, pk=pk)
        form = TeacherRegistrationForm(request.POST, request.FILES, instance=teacher.user, teacher_instance=teacher)
        if form.is_valid():
            user = form.save(commit=False)
            user.save()

            teacher.gender = form.cleaned_data['gender']
            teacher.date_of_birth = form.cleaned_data['date_of_birth']
            teacher.contact = form.cleaned_data['contact']
            teacher.profile_image = form.cleaned_data['profile_image']
            teacher.address = form.cleaned_data['address']

            teacher.save()

            return redirect('teacher_detail', pk=teacher.pk)
        
        print(f"Form Errors: {form.errors}")
        return render(request, self.template_name, {'form': form, 'is_update': True, 'teacher': teacher})
 
class TeacherDetailView(View):
    template_name = 'teacher/teacher_detail.html'

    def get(self, request, pk, *args, **kwargs):
        teacher = get_object_or_404(Teacher, pk=pk)
        return render(request, self.template_name, {'teacher': teacher})

class TeacherDeleteView(View):
    template_name = 'teacher/teacher_confirm_delete.html'

    def get(self, request, pk, *args, **kwargs):
        teacher = get_object_or_404(Teacher, pk=pk)
        return render(request, self.template_name, {'teacher': teacher})

    def post(self, request, pk, *args, **kwargs):
        teacher = get_object_or_404(Teacher, pk=pk)
        teacher.delete()
        return redirect('teacher_list')


def export_teachers(request):
    # Implement export logic here
    pass

def teacher_reports(request):
    # Implement report generation logic here
    pass


@login_required
@teacher_required # Use your teacher role check
def mark_attendance(request, class_id):
    try:
        class_instance = get_object_or_404(Class, id=class_id)

        students = class_instance.enrolled_students.filter(status='active').order_by('user__last_name', 'user__first_name')
    except Class.DoesNotExist:
        messages.error(request, "Class not found.")
        return redirect('teacher_dashboard') # Or a more appropriate error page

    # Fetch the active term
    current_term = Term.get_current_term() # Use the robust method from Term model
    if not current_term:
        messages.error(request, "No active term found. Attendance cannot be marked.")
        context = {'class_instance': class_instance, 'students': students, 'no_active_term': True}
        return render(request, 'teacher/mark_attendance.html', context)

    weeks_date_objects = current_term.get_term_weeks() # List of lists of date objects
    if not weeks_date_objects:
        messages.warning(request, f"No weeks defined for the current term: {current_term}.")
        context = {'class_instance': class_instance, 'students': students, 'current_term': current_term, 'no_weeks': True}
        return render(request, 'teacher/mark_attendance.html', context)

    # Determine default selected week (current calendar week or last viewed)
    today = timezone.now().date()
    default_week_index = 0
    for i, week in enumerate(weeks_date_objects):
        if week and today >= week[0] and today <= week[-1]: # Check if today falls within this week
            default_week_index = i
            break
        elif week and today < week[0] and i == 0: # If today is before the first week, show first week
            default_week_index = 0
            break
        elif week and today > week[-1] and i == len(weeks_date_objects) -1: # If today is after last week, show last week
             default_week_index = i
             break


    # "Remember Last Week" - Store in session
    session_key_last_week = f'attendance_last_week_class_{class_id}'
    if 'week' in request.GET:
        selected_week_index = int(request.GET.get('week'))
        request.session[session_key_last_week] = selected_week_index
    else:
        selected_week_index = request.session.get(session_key_last_week, default_week_index)

    # Ensure selected_week_index is valid
    selected_week_index = max(0, min(selected_week_index, len(weeks_date_objects) - 1))
    request.session[session_key_last_week] = selected_week_index # Update session with validated index

    week_days_for_display = weeks_date_objects[selected_week_index] if selected_week_index < len(weeks_date_objects) else []
    # Filter out weekends (Saturday=5, Sunday=6)
    school_week_days = [day for day in week_days_for_display if day.weekday() < 5]

    # Prepare attendance dictionary: {student_id: {'YYYY-MM-DD': 'present'/'absent'}}
    attendance_dict = defaultdict(dict) # Use defaultdict
    if school_week_days:
        attendance_records = Attendance.objects.filter(
            class_assigned=class_instance,
            date__in=school_week_days, # Use actual date objects for query
            term=current_term,
            student__in=students
        ).select_related('student')

        for record in attendance_records:
            date_str = record.date.strftime('%Y-%m-%d')
            status = "present" if record.is_present else "absent"
            # For other statuses if you add them:
            # if record.is_late: status = "late"
            # elif record.is_excused: status = "excused"
            attendance_dict[record.student_id][date_str] = status # Use student.id as key

    if request.method == 'POST':
        submitted_week_idx = int(request.POST.get('submitted_week_index', -1))
        if submitted_week_idx != selected_week_index:
            messages.error(request, "Week mismatch during submission. Please try again.")
            return redirect(request.path_info + f"?week={selected_week_index}")

        records_to_update_or_create = []
        for student in students:
            for day_obj in school_week_days: 
                day_str = day_obj.strftime("%Y-%m-%d")
                # Use student.id for consistency in name attribute
                attendance_status = request.POST.get(f'attendance_{student.user.id}_{day_str}')

                if attendance_status: # If 'present' or 'absent' was selected
                    is_present_val = (attendance_status == 'present')
                    is_absent_val = (attendance_status == 'absent')
                    # Add other status checks if needed
                    # is_late_val = (attendance_status == 'late')
                    # is_excused_val = (attendance_status == 'excused')

                    # Prepare for update_or_create
                    defaults = {'is_present': is_present_val}
                    # Add other fields to defaults:
                    # defaults['is_late'] = is_late_val
                    # defaults['is_excused'] = is_excused_val
                    # defaults['remarks'] = request.POST.get(f'remarks_{student.id}_{day_str}', '')

                    Attendance.objects.update_or_create(
                        student=student,
                        date=day_obj, 
                        class_assigned=class_instance,
                        term=current_term,
                        defaults=defaults
                    )

        messages.success(request, f"Attendance for Week {selected_week_index + 1} saved successfully.")
        # Redirect to the same week to show saved changes
        return redirect('attendance_log', class_id=class_instance.id)


    # Determine max_week correctly based on actual weeks defined
    # max_week is the last valid index for weeks_date_objects
    max_week_index = len(weeks_date_objects) - 1 if weeks_date_objects else 0

    context = {
        'class_instance': class_instance,
        'students': students,
        'current_term': current_term,
        'weeks_for_nav': weeks_date_objects, # Pass the full list for length calculation
        'selected_week_index': selected_week_index, # Pass the 0-based index
        'week_days_for_display': school_week_days, # Actual school days to iterate
        'attendance_dict': attendance_dict,
        'max_week_index': max_week_index,
    }
    return render(request, 'teacher/mark_attendance.html', context)

@login_required
@teacher_required
def attendance_log(request, class_id):
    try:
        class_instance = get_object_or_404(Class, id=class_id)
        students = class_instance.enrolled_students.filter(status='active').order_by('user__last_name', 'user__first_name')
    except Class.DoesNotExist:
        messages.error(request, "Class not found.")
        return redirect('teacher_dashboard')

    current_term = Term.get_current_term()
    if not current_term:
        messages.error(request, "No active term found. Cannot display attendance log.")
        context = {'class_instance': class_instance, 'students': students, 'no_active_term': True}
        return render(request, 'teacher/attendance_log.html', context)

    weeks_date_objects = current_term.get_term_weeks()
    if not weeks_date_objects:
        messages.warning(request, f"No weeks defined for the current term: {current_term}.")
        context = {'class_instance': class_instance, 'students': students, 'current_term': current_term, 'no_weeks': True}
        return render(request, 'teacher/attendance_log.html', context)

    today = timezone.now().date()
    default_week_index = 0
    for i, week in enumerate(weeks_date_objects):
        if week and today >= week[0] and today <= week[-1]:
            default_week_index = i
            break
        elif week and today < week[0] and i == 0: default_week_index = 0; break
        elif week and today > week[-1] and i == len(weeks_date_objects) -1: default_week_index = i; break

    # Use session to remember last viewed log week, similar to mark_attendance
    session_key_log_week = f'attendance_log_last_week_class_{class_id}'
    if 'week' in request.GET:
        selected_week_index = int(request.GET.get('week'))
        request.session[session_key_log_week] = selected_week_index
    else:
        selected_week_index = request.session.get(session_key_log_week, default_week_index)

    selected_week_index = max(0, min(selected_week_index, len(weeks_date_objects) - 1))
    request.session[session_key_log_week] = selected_week_index # Update session

    week_days_for_log = weeks_date_objects[selected_week_index] if selected_week_index < len(weeks_date_objects) else []
    school_week_days_for_log = [day for day in week_days_for_log if day.weekday() < 5]

    student_attendance_summary = []
    for student in students:
        # Per-week summary
        present_in_selected_week = 0
        absent_in_selected_week = 0
        if school_week_days_for_log: # Only query if there are school days in the week
            present_in_selected_week = Attendance.objects.filter(
                student=student, term=current_term, date__in=school_week_days_for_log, is_present=True
            ).count()
            absent_in_selected_week = Attendance.objects.filter(
                student=student, term=current_term, date__in=school_week_days_for_log, is_present=False
            ).count()

        # Overall term summary
        total_present_term = Attendance.objects.filter(
            student=student, term=current_term, is_present=True
        ).count()
        total_absent_term = Attendance.objects.filter(
            student=student, term=current_term, is_present=False
        ).count()

        student_attendance_summary.append({
            'student': student,
            'present_in_selected_week': present_in_selected_week,
            'absent_in_selected_week': absent_in_selected_week,
            'total_present_term': total_present_term,
            'total_absent_term': total_absent_term,
        })

    max_week_index = len(weeks_date_objects) - 1 if weeks_date_objects else 0

    context = {
        'class_instance': class_instance,
        'students': students, # Pass students for iteration if needed
        'current_term': current_term,
        'student_attendance_summary': student_attendance_summary,
        'weeks_for_nav': weeks_date_objects,
        'selected_week_index': selected_week_index,
        'max_week_index': max_week_index,
        'week_days_for_log_display': school_week_days_for_log, # For displaying the days in the log
    }
    return render(request, 'teacher/attendance_log.html', context)


@login_required
def input_scores(request, class_id, subject_id, term_id):
    class_obj = get_object_or_404(Class, id=class_id)
    subject = get_object_or_404(Subject, id=subject_id)
    term = get_object_or_404(Term, id=term_id)
    # Ensure we only get students currently enrolled in THIS class
    students = Student.objects.filter(current_class=class_obj).order_by('user__last_name', 'user__first_name').distinct()

    # Prepare instances and forms
    subject_results = {}
    forms_dict = {}
    for student in students:
        # Ensure a Result object exists for the student and term
        result_obj, _ = Result.objects.get_or_create(student=student, term=term)
        # Get or create the specific SubjectResult
        subject_result, _ = SubjectResult.objects.get_or_create(result=result_obj, subject=subject)
        subject_results[student.user.id] = subject_result # Store by user ID for easier POST lookup

    if request.method == 'POST':
        all_forms_valid = True
        forms_to_save = []

        for student in students:
            subject_result = subject_results.get(student.user.id)
            if not subject_result:
                 # Should not happen with get_or_create, but good to check
                 continue

            # Create form instance with POST data, files, instance, and prefix
            form = SubjectResultForm(request.POST, instance=subject_result, prefix=str(student.user.id))
            forms_dict[student] = form # Store the bound form for rendering

            if form.is_valid():
                forms_to_save.append(form) 
            else:
                all_forms_valid = False
                # Optional: Log errors for debugging

        if all_forms_valid:
            # Save all valid forms
            for form in forms_to_save:
                form.save()
            messages.success(request, f"{subject.name} scores for {class_obj.name} submitted successfully.")
            # Redirect to broadsheet or another appropriate page
            return redirect('broadsheet', class_id=class_id, term_id=term_id)
        else:
            # If any form is invalid, display errors
            messages.error(request, "Please correct the errors below.")
            # The view will fall through to render the template with the forms_dict containing bound, invalid forms

    else: # GET request
        for student in students:
            subject_result = subject_results.get(student.user.id)
            forms_dict[student] = SubjectResultForm(instance=subject_result, prefix=str(student.user.id))

    context = {
        'forms': forms_dict, # Pass the dictionary of forms
        'class': class_obj,
        'subject': subject,
        'term': term,
        'students': students, # Pass students if needed separately (e.g., ordering)
    }
    return render(request, 'teacher/input_scores.html', context)

# --- Broadsheet View (Minor Refinements) ---
@login_required
def broadsheet(request, class_id, term_id):
    class_obj = get_object_or_404(Class, id=class_id)
    # Ensure active session logic is robust if needed elsewhere too
    try:
        session = Session.objects.get(is_active=True)
    except Session.DoesNotExist:
        messages.error(request, "No active session found.")
        return redirect('teacher_dashboard') # Or appropriate error page
    except Session.MultipleObjectsReturned:
        messages.error(request, "Multiple active sessions found. Please resolve.")
        return redirect('teacher_dashboard')

    term = get_object_or_404(Term, id=term_id)
    # Get students enrolled in the class for this specific term/session if possible
    students = Student.objects.filter(current_class=class_obj).order_by('user__last_name', 'user__first_name') # Or filter based on historical enrollment if needed

    # Get subjects assigned to this class in this term/session
    subjects = Subject.objects.filter(
        class_assignments__class_assigned=class_obj,
        class_assignments__session=session,
        class_assignments__term=term
    ).distinct().order_by('name')

    results_data = []

    for student in students:
        # Get the main Result object for this student/term
        result = Result.objects.filter(student=student, term=term).first()
        student_subject_results = {}
        total_score_sum = Decimal('0.0')
        gpa_points_sum = Decimal('0.0')
        subject_count = 0

        if result:
            # Get all SubjectResult entries for this Result (student/term)
            # Filter only for subjects relevant to *this* broadsheet view
            subject_results_qs = result.subjectresult_set.filter(subject__in=subjects)

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
                     gpa_points_sum += Decimal(sr.calculate_grade_point()) # Ensure Decimal for precision
                     subject_count += 1

        # Calculate overall GPA for the student based *only* on subjects shown on this broadsheet
        # Note: Result.calculate_gpa() might calculate based on *all* subjects in the Result,
        # which might differ from the broadsheet's context if not all subjects are shown.
        # Here we calculate GPA based on the subjects included in `student_subject_results`.
        student_gpa = (gpa_points_sum / subject_count) if subject_count > 0 else Decimal('0.0')
        grade = sr.calculate_grade()

        results_data.append({
            'student': student,
            'subject_results': student_subject_results, # Dict: {subject_id: SubjectResult instance}
            'gpa': student_gpa.quantize(Decimal('0.01')), # Format GPA
            'total_score': total_score_sum.quantize(Decimal('0.1')), # Sum of total_scores across subjects
            'grade': grade,
        })

    # Sort students: Primary by Total Score (desc), Secondary by GPA (desc)
    results_data.sort(key=lambda x: (-x['total_score'], -x['gpa']))

    context = {
        # 'students': students, # Already part of results_data
        'class': class_obj,
        'term': term,
        'results_data': results_data, # This contains student info and their results
        'subjects': subjects, # List of subjects for table headers
        'session': session,
    }
    return render(request, 'teacher/broadsheet.html', context)


@login_required
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

@login_required
def message_guardian(request, guardian_id):
    if not request.user.is_authenticated or request.user.role != 'teacher':
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('teacher_dashboard')

    teacher = get_object_or_404(Teacher, user=request.user)

    try:
        guardian = Guardian.objects.get(user_id=guardian_id)
    except Guardian.DoesNotExist:
        messages.error(request, 'Guardian not found.')
        return redirect('teacher_dashboard')

    # Fetch the associated student for the guardian
    student = Student.objects.filter(student_guardian=guardian).first()  # Adjust this to match your schema

    if not student:
        messages.error(request, 'No student associated with this guardian.')
        return redirect('teacher_dashboard')

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            try:
                # Create the message with the correct Student instance
                Message.objects.create(
                    sender=request.user,
                    recipient=guardian.user,  # Guardian's user object
                    student=student,  # Pass the Student instance
                    title=form.cleaned_data['title'],
                    content=form.cleaned_data['content'],
                )
                messages.success(request, 'Message sent to the guardian!')
                return redirect('teacher_dashboard')
            except Exception as e:
                print(f"Error while creating message: {e}")
                messages.error(request, 'Failed to send the message. Please try again.')
    else:
        form = MessageForm()

    return render(
        request, 
        'teacher/message_guardian.html',
        {
            'form': form,
            'guardian_id': guardian_id,
            'guardian_name': guardian.user.get_full_name()
        }
    )

@login_required
def performance_chart_view(request, student_id):
    subject_results = SubjectResult.objects.filter(result__student_id=student_id)
    for result in subject_results:
        result.class_average = SubjectResult.get_class_average(result.subject)

    context = {
        'subject_results': subject_results,
    }
    return render(request, 'performance_chart.html', context)

@login_required
def create_assignment(request):
    # Ensure the logged-in user is a teacher
    teacher = get_object_or_404(Teacher, user=request.user)

    # Retrieve classes and subjects assigned to the teacher
    assigned_classes = teacher.assigned_classes()
    subjects = teacher.assigned_subjects()

    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        
        # Limit choices to teacher's assigned classes and subjects
        form.fields['class_assigned'].queryset = assigned_classes
        form.fields['subject'].queryset = subjects

        if form.is_valid():
            # Save the assignment
            assignment = form.save(commit=False)
            assignment.teacher = teacher
            assignment.created_at = timezone.now()
            assignment.updated_at = timezone.now()
            assignment.save()

            # Process each question from POST data
            question_number = 1
            errors = []
            while f'question_type_{question_number}' in request.POST:
                question_type = request.POST.get(f'question_type_{question_number}')
                question_text = request.POST.get(f'question_text_{question_number}')
                options = request.POST.get(f'options_{question_number}', '')
                correct_answer = request.POST.get(f'correct_answer_{question_number}')

                options_list = [opt.strip() for opt in options.split(',') if opt.strip()]
                question_data = {
                    'question_type': question_type,
                    'question_text': question_text,
                    'options': json.dumps(options_list) if options_list else '',
                    'correct_answer': correct_answer
                }

                question_form = QuestionForm(question_data)
                if question_form.is_valid():
                    if question_type in ['SCQ', 'MCQ']:
                        # Ensure options are provided for SCQ/MCQ
                        if not options_list:
                            errors.append(f"Error in Question {question_number}: Options must be provided for SCQ/MCQ.")
                        else:
                            # Create SCQ/MCQ question
                            Question.objects.create(
                                assignment=assignment,
                                question_type=question_type,
                                question_text=question_text,
                                options=json.dumps(options_list),
                                correct_answer=correct_answer
                            )
                    elif question_type == 'ES':
                        # Create Essay question (options and correct_answer are ignored)
                        Question.objects.create(
                            assignment=assignment,
                            question_type=question_type,
                            question_text=question_text
                        )
                else:
                    errors.append(f"Error in Question {question_number}: {question_form.errors}")

                question_number += 1

            # Handle errors or redirect on success
            if not errors:

                return redirect('teacher_dashboard')
            
            else:
                return render(request, 'assignment/create_assignment.html', {
                    'form': form,
                    'errors': errors,
                })
        else:
            print("Form Errors:", form.errors)

    else:
        form = AssignmentForm()
        # Limit the dropdown options for classes and subjects
        form.fields['class_assigned'].queryset = assigned_classes
        form.fields['subject'].queryset = subjects

    return render(request, 'assignment/create_assignment.html', {
        'form': form,
    })

@login_required
def add_question(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.assignment = assignment
            question.save()
            return redirect('assignment/assignment_detail', assignment_id=assignment_id)  # Back to assignment detail
    else:
        form = QuestionForm()
    
    return render(request, 'teacher/add_question.html', {'form': form, 'assignment': assignment})

@login_required
def assignment_detail(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    # No need to manually set `options_list` since it's handled by the @property
    return render(request, 'assignment/assignment_detail.html', {'assignment': assignment})

@login_required
def grade_assignment(request, submission_id):
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    assignment = submission.assignment
    questions = assignment.questions.all()
    
    total_score = 0
    for question in questions:
        answer = submission.answers.get(str(question.id))
        if question.question_type in ['SCQ', 'MCQ']:
            if answer == question.correct_answer:
                total_score += 1
        else:
            # Essay question - requires manual grading by teacher
            pass
    
    submission.grade = (total_score / len(questions)) * 100  # Example grading logic
    submission.save()

    return redirect('teacher_dashboard')

@login_required
def grade_essay_questions(request, assignment_id):
    assignment = get_object_or_404(
        Assignment.objects.annotate(num_submissions=Count('submissions')),
        id=assignment_id,
        teacher=request.user.teacher,
        num_submissions__gt=0  # Only fetch assignments with submissions
    )
    submissions = assignment.submissions.prefetch_related('student').all()

    if request.method == 'POST':
        for submission in submissions:
            essay_scores = {}
            total_manual_score = 0

            for question in assignment.question_set.filter(question_type='Essay'):
                score_key = f"score_{submission.student.id}_{question.id}"
                score = request.POST.get(score_key)

                if score:
                    try:
                        score = float(score)
                        essay_scores[str(question.id)] = score
                        total_manual_score += score
                    except ValueError:
                        messages.error(request, f"Invalid score for {submission.student.user.get_full_name()} on {question.question_text}.")
                        break

            # Update total grade and feedback for the submission
            submission.grade = (submission.grade or 0) + total_manual_score
            submission.feedback = request.POST.get(f"feedback_{submission.student.id}", "")
            submission.save()

        messages.success(request, "Essay questions graded successfully.")
        return redirect('teacher_dashboard')

    return render(request, 'assignment/grade_essay.html', {
        'assignment': assignment,
        'submissions': submissions,
    })

@login_required
def view_submitted_assignments(request):
    teacher = request.user.teacher
    
    # Group submissions by subject for assignments created by this teacher
    submissions_by_subject = (
        AssignmentSubmission.objects.filter(assignment__teacher=teacher)
        .select_related('assignment', 'student__user')
        .annotate(subject=F('assignment__subject'))
        .order_by('subject', 'assignment__title', 'student__user__last_name')
    )
    
    return render(request, 'teacher/view_submitted_assignments.html', {
        'submissions_by_subject': submissions_by_subject,
    })

@login_required
def assignment_list(request):
    assignments = Assignment.objects.filter(teacher=request.user.teacher)
    return render(request, 'assignment/assignment_list.html', {'assignments': assignments})

@login_required
def update_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            return redirect('teacher_dashboard')
    else:
        form = AssignmentForm(instance=assignment)
    return render(request, 'assignment/update_assignment.html', {'form': form, 'assignment': assignment})

@login_required
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    if request.method == 'POST':
        assignment.delete()
        return redirect('teacher_dashboard')
    
    return render(request, 'assignment/delete_assignment.html', {'assignment': assignment})

@login_required
def update_result(request, student_id, term_id):
    student = get_object_or_404(Student, pk=student_id)
    result = get_object_or_404(Result, student=student, term=term_id)

    if request.method == 'POST':
        form = NonAcademicSkillsForm(request.POST, instance=result)
        if form.is_valid():
            form.save()
            return redirect('view_na_result', student_id=student.user.id, term_id=term_id)
    else:
        form = NonAcademicSkillsForm(instance=result)

    return render(request, 'teacher/update_result.html', {
        'form': form,
        'student': student,
        'result': result,
    })

    
@login_required
def view_na_result(request, student_id, term_id):
    # Ensure the logged-in user is a teacher and has access to the student's result
    student = get_object_or_404(Student, pk=student_id)
    result = get_object_or_404(Result, student=student, term=term_id)
    
    return render(request, 'teacher/view_na_result.html', {
        'student': student,
        'result': result,
    })

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

        if q_type_key not in request.POST and q_text_key not in request.POST : 
            break

        question_type = request.POST.get(q_type_key)
        question_text = request.POST.get(q_text_key, '').strip()
        options_str = request.POST.get(q_options_key, '')
        correct_answer_str = request.POST.get(q_correct_key, '').strip()

        if not question_text and not question_type:
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
            'correct_answer': correct_answer_str if correct_answer_str else None
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

# --- Create Assessment View ---
@login_required
def create_assessment(request):
    user = request.user
    teacher_profile = Teacher.objects.filter(user=user).first() 

    if teacher_profile:
        assigned_classes_qs = teacher_profile.assigned_classes()
        assigned_subjects_qs = teacher_profile.assigned_subjects()
    elif user.is_superuser:
        assigned_classes_qs = Class.objects.all()
        assigned_subjects_qs = Subject.objects.all()
    else:
        messages.error(request, "You are not authorized to create assessments.")
        return redirect('home') 

    if request.method == 'POST':
        form = AssessmentForm(request.POST)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs

        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.created_by = user
            if user.is_superuser: # Superusers can auto-approve
                assessment.is_approved = True
            assessment.save() 

            question_processing_errors = _process_newly_added_questions(request, assessment, question_name_prefix='question_')
            
            if not question_processing_errors:
                messages.success(request, f"Assessment '{assessment.title}' created successfully.")
                return redirect('school-setup' if user.is_superuser else 'teacher_dashboard')
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
    teacher_profile = Teacher.objects.filter(user=user).first()

    # Authorization
    if not (user.is_superuser or assessment.created_by == user):
        messages.error(request, "You are not authorized to update this assessment.")
        return redirect('home')

    if teacher_profile and not user.is_superuser :
        assigned_classes_qs = teacher_profile.assigned_classes()
        assigned_subjects_qs = teacher_profile.assigned_subjects()
    else: # Superuser or non-teacher (though auth check above should handle non-teacher)
        assigned_classes_qs = Class.objects.all()
        assigned_subjects_qs = Subject.objects.all()

    if request.method == 'POST':
        form = AssessmentForm(request.POST, instance=assessment)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs

        if form.is_valid():
            updated_assessment = form.save(commit=False)
            if user.is_superuser and not assessment.is_approved: 
                 updated_assessment.is_approved = True
                 updated_assessment.approved_by = user
            updated_assessment.updated_at = timezone.now()
            updated_assessment.save()
            # form.save_m2m() # Only if AssessmentForm itself has M2M fields

            all_errors = []

            # 1. Update Existing Questions
            submitted_existing_ids = set()
            for q_instance in assessment.questions.all():
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
                assessment.questions.remove(*deleted_ids) 
                OnlineQuestion.objects.filter(id__in=deleted_ids, assessments=None).delete() # Optional: delete orphaned questions

            # 3. Add Newly Added Questions (uses 'new_question_' prefix)
            new_question_errors = _process_newly_added_questions(request, assessment, question_name_prefix='new_question_')
            all_errors.extend(new_question_errors)

            if not all_errors:
                messages.success(request, "Assessment updated successfully.")
                return redirect('view_assessment', assessment_id=assessment.id)
            else:
                messages.error(request, "Errors occurred. Please review.")
        # If form is invalid or errors occurred, re-render with context
        current_questions = assessment.questions.all().order_by('id')
        return render(request, 'assessment/update_assessment.html', {
            'form': form, # This form instance will have its own errors
            'assessment': assessment,
            'questions': current_questions,
            'processing_errors': all_errors if 'all_errors' in locals() and all_errors else [] 
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
def teacher_assessment_list(request):
    try:
        teacher = get_object_or_404(Teacher, user=request.user)
    except Teacher.DoesNotExist:
        messages.error(request, "You do not have a teacher profile.")
        return redirect('home') 


    total_submissions_subquery = AssessmentSubmission.objects.filter(
        assessment=OuterRef('pk')
    ).values('assessment').annotate(count=Count('pk')).values('count')

    graded_submissions_subquery = AssessmentSubmission.objects.filter(
        assessment=OuterRef('pk'),
        is_graded=True
    ).values('assessment').annotate(count=Count('pk')).values('count')

    class_student_count_subquery = Student.objects.filter(
        current_class=OuterRef("class_assigned"),
        status='active' # Optional: only count active students
    ).values('current_class').annotate(count=Count('pk')).values('count')


    # --- Main Query ---
    assessments_by_teacher = Assessment.objects.filter(
        created_by=teacher.user
    ).select_related(
        'class_assigned', 'subject'
    ).annotate(
        # Sum the 'points' field from the related OnlineQuestion model
        total_possible_score=Sum('questions__points'),

        submission_count=Subquery(total_submissions_subquery, output_field=IntegerField()),
        submission_count_graded=Subquery(graded_submissions_subquery, output_field=IntegerField()),
        total_students_in_class=Subquery(class_student_count_subquery, output_field=IntegerField())

    ).order_by('-created_at')

    # --- Query for Pending Submissions (this query is separate and fine as is) ---
    pending_essay_submissions = AssessmentSubmission.objects.filter(
        assessment__created_by=teacher.user,
        requires_manual_review=True,
        is_graded=False
    ).select_related(
        'assessment', 'student__user', 'assessment__class_assigned'
    ).order_by('submitted_at')

    context = {
        'assessments': assessments_by_teacher,
        'pending_essay_submissions': pending_essay_submissions,
        'page_title': "My Assessments & Submissions",
    }
    return render(request, 'assessment/teacher_assessment_list.html', context)


@login_required
def view_assessment(request, assessment_id): 

    assessment = get_object_or_404(Assessment, id=assessment_id) 
    questions = assessment.questions.all()
    
    if not (request.user.is_superuser or assessment.created_by == request.user):
        messages.error(request, "You are not authorized to view this assessment's details.")
        return redirect('home') 

    #for q_idx, q in enumerate(questions):
    #    print(f"  Q{q_idx+1}: {q.question_text[:50]}... (Type: {q.question_type}, Options: {q.options})")

    # Prepare questions with processed options for the template
    processed_questions_for_teacher_view = []
    for question in assessment.questions.all().order_by('id'):
        options_with_correct_status = []
        if question.question_type in ['SCQ', 'MCQ']:
            all_options = question.options_list()
            if all_options:
                for opt_text in all_options:
                    options_with_correct_status.append({
                        'text': opt_text,
                        'is_marked_correct': question.is_option_correct(opt_text) 
                    })
        
        processed_questions_for_teacher_view.append({
            'instance': question, 
            'options_with_status': options_with_correct_status 
        })

    context = {
        'assessment': assessment, 
        'questions_processed': processed_questions_for_teacher_view,
    }
    return render(request, 'assessment/assessment_detail.html', context)


@login_required
def delete_assessment(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id)
    teacher = get_object_or_404(Teacher, user=request.user)

    # Ensure the logged-in user is the creator or an admin
    if assessment.created_by != teacher.user and not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to delete this assessment.")

    if request.method == 'POST':
        assessment.delete()
        return redirect('teacher_dashboard')

    return render(request, 'assessment/delete_assessment.html', {
        'assessment': assessment,
    })


@login_required
def grade_essay_assessment(request, submission_id):
    submission = get_object_or_404(
        AssessmentSubmission.objects.select_related('assessment', 'student__user'),
        id=submission_id
    )
    assessment = submission.assessment

    # --- RECALCULATE all necessary scores for the context ---
    auto_graded_score = Decimal('0.00')
    max_possible_auto_score = Decimal('0.00')
    max_possible_manual_score = Decimal('0.00')

    # Get all questions for the assessment at once to avoid multiple DB hits
    all_assessment_questions = assessment.questions.all()
    student_answers = submission.answers if isinstance(submission.answers, dict) else {}

    # Iterate through questions to calculate scores
    for question in all_assessment_questions:
        question_id_str = str(question.id)
        student_answer = student_answers.get(question_id_str)

        if question.question_type in ['SCQ', 'MCQ']:
            max_possible_auto_score += Decimal(question.points)
            # --- Auto-grading logic (should match what happens on submission) ---
            is_correct = False
            if student_answer is not None:
                if question.question_type == 'SCQ':
                    is_correct = (str(student_answer).strip().lower() == str(question.correct_answer).strip().lower())
                elif question.question_type == 'MCQ':
                    # Assuming correct_answer is "A,B" and student_answer is a list ["A", "B"]
                    # Adjust this logic to match how you store MCQ answers
                    correct_set = set(op.strip().lower() for op in (question.correct_answer or "").split(',') if op.strip())
                    submitted_set = set(op.strip().lower() for op in student_answer if isinstance(student_answer, list))
                    is_correct = (correct_set == submitted_set and bool(correct_set))

            if is_correct:
                auto_graded_score += Decimal(question.points)

        elif question.question_type == 'ES':
            max_possible_manual_score += Decimal(question.points)

    # --- Prepare all questions data for display (your previous logic was fine) ---
    all_questions_data = []
    for question_obj in all_assessment_questions.order_by('id'):
        student_answer_for_q = None
        raw_ans = student_answers.get(str(question_obj.id))
        if isinstance(raw_ans, list):
            student_answer_for_q = ", ".join(raw_ans)
        else:
            student_answer_for_q = raw_ans

        # Re-run a simplified version of auto-grading logic for display
        is_correct_auto = None
        if question_obj.question_type != 'ES' and student_answer_for_q is not None:
             is_correct_auto = (str(student_answer_for_q).strip().lower() == str(question_obj.correct_answer).strip().lower()) # This might need refinement for MCQ display

        all_questions_data.append({
            'question': question_obj,
            'student_answer': student_answer_for_q,
            'is_essay': question_obj.question_type == 'ES',
            'is_correct_auto': is_correct_auto
        })

    # --- Handle Form Submission ---
    if request.method == 'POST':
        manual_score_str = request.POST.get('manual_score')
        feedback = request.POST.get('feedback', '').strip()

        try:
            manual_score = Decimal(manual_score_str or '0.00')
            if manual_score < 0 or manual_score > max_possible_manual_score:
                messages.error(request, f"Manual score must be between 0 and {max_possible_manual_score}.")
                # (Re-render form logic...)
            else:
                final_score = auto_graded_score + manual_score
                submission.score = final_score
                submission.feedback = feedback
                submission.is_graded = True
                submission.requires_manual_review = False
                submission.save()
                messages.success(request, f"Grade finalized for {submission.student.user.get_full_name()}. Final score: {final_score}")

                if request.user.is_superuser:
                    return redirect('assessment_submissions_list', assessment_id=assessment.id)
                else:
                    return redirect('teacher_assessment_list')

        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid score entered. Please enter a valid number.")

    context = {
        'submission': submission,
        'assessment': assessment,
        'all_questions_data': all_questions_data,
        'auto_graded_score': auto_graded_score,
        'max_possible_auto_score': max_possible_auto_score,
        'max_possible_manual_score': max_possible_manual_score,
    }

    return render(request, 'assessment/grade_essay_assessment.html', context)

### ------ EXAM SECTION ------ ###

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
            if user.is_superuser: # Superusers can auto-approve
                exam.is_approved = True
            exam.save() 

            question_processing_errors = _process_newly_added_questions(request, exam, question_name_prefix='question_')
            
            if not question_processing_errors:
                messages.success(request, f"Exam '{exam.title}' created successfully.")
                return redirect('school-setup' if user.is_superuser else 'teacher_dashboard')
            else:
                exam.delete() # Rollback exam creation if questions had critical errors
                form_with_initial_data = ExamForm(request.POST) # Re-bind to show original data
                form_with_initial_data.fields['class_assigned'].queryset = assigned_classes_qs
                form_with_initial_data.fields['subject'].queryset = assigned_subjects_qs
                messages.error(request, "Exam not created. Please correct the question errors.")
                return render(request, 'exam/create_exam.html', {
                    'form': form_with_initial_data,
                    'question_errors': question_processing_errors,
                })
        else: # ExamForm is invalid
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
            # form.save_m2m() # Only if ExamForm itself has M2M fields

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
def teacher_exam_list(request):
    try:
        teacher = get_object_or_404(Teacher, user=request.user)
    except Teacher.DoesNotExist:
        messages.error(request, "You do not have a teacher profile.")
        return redirect('home') 


    total_submissions_subquery = ExamSubmission.objects.filter(
        exam=OuterRef('pk')
    ).values('exam').annotate(count=Count('pk')).values('count')

    graded_submissions_subquery = ExamSubmission.objects.filter(
        exam=OuterRef('pk'),
        is_graded=True
    ).values('exam').annotate(count=Count('pk')).values('count')

    class_student_count_subquery = Student.objects.filter(
        current_class=OuterRef("class_assigned"),
        status='active' # Optional: only count active students
    ).values('current_class').annotate(count=Count('pk')).values('count')


    # --- Main Query ---
    exams_by_teacher = Exam.objects.filter(
        created_by=teacher.user
    ).select_related(
        'class_assigned', 'subject'
    ).annotate(
        # Sum the 'points' field from the related OnlineQuestion model
        total_possible_score=Sum('questions__points'),

        submission_count=Subquery(total_submissions_subquery, output_field=IntegerField()),
        submission_count_graded=Subquery(graded_submissions_subquery, output_field=IntegerField()),
        total_students_in_class=Subquery(class_student_count_subquery, output_field=IntegerField())

    ).order_by('-created_at')

    # --- Query for Pending Submissions (this query is separate and fine as is) ---
    pending_essay_submissions = ExamSubmission.objects.filter(
        exam__created_by=teacher.user,
        requires_manual_review=True,
        is_graded=False
    ).select_related(
        'exam', 'student__user', 'exam__class_assigned'
    ).order_by('submitted_at')

    context = {
        'exams': exams_by_teacher,
        'pending_essay_submissions': pending_essay_submissions,
        'page_title': "My Exams & Submissions",
    }
    return render(request, 'exam/teacher_exam_list.html', context)


@login_required
def view_exam(request, exam_id): 

    exam = get_object_or_404(Exam, id=exam_id) 
    questions = exam.questions.all()
    
    if not (request.user.is_superuser or exam.created_by == request.user):
        messages.error(request, "You are not authorized to view this exam's details.")
        return redirect('home') 

    #for q_idx, q in enumerate(questions):
    #    print(f"  Q{q_idx+1}: {q.question_text[:50]}... (Type: {q.question_type}, Options: {q.options})")

    # Prepare questions with processed options for the template
    processed_questions_for_teacher_view = []
    for question in exam.questions.all().order_by('id'):
        options_with_correct_status = []
        if question.question_type in ['SCQ', 'MCQ']:
            all_options = question.options_list()
            if all_options:
                for opt_text in all_options:
                    options_with_correct_status.append({
                        'text': opt_text,
                        'is_marked_correct': question.is_option_correct(opt_text) 
                    })
        
        processed_questions_for_teacher_view.append({
            'instance': question, 
            'options_with_status': options_with_correct_status 
        })

    context = {
        'exam': exam, 
        'questions_processed': processed_questions_for_teacher_view,
    }
    return render(request, 'exam/exam_detail.html', context)


@login_required
def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    teacher = get_object_or_404(Teacher, user=request.user)

    # Ensure the logged-in user is the creator or an admin
    if exam.created_by != teacher.user and not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to delete this exam.")

    if request.method == 'POST':
        exam.delete()
        return redirect('teacher_dashboard')

    return render(request, 'exam/delete_exam.html', {
        'exam': exam,
    })


@login_required
def grade_essay_exam(request, submission_id):
    submission = get_object_or_404(
        ExamSubmission.objects.select_related('exam', 'student__user'),
        id=submission_id
    )
    exam = submission.exam

    # --- RECALCULATE all necessary scores for the context ---
    auto_graded_score = Decimal('0.00')
    max_possible_auto_score = Decimal('0.00')
    max_possible_manual_score = Decimal('0.00')

    # Get all questions for the exam at once to avoid multiple DB hits
    all_exam_questions = exam.questions.all()
    student_answers = submission.answers if isinstance(submission.answers, dict) else {}

    # Iterate through questions to calculate scores
    for question in all_exam_questions:
        question_id_str = str(question.id)
        student_answer = student_answers.get(question_id_str)

        if question.question_type in ['SCQ', 'MCQ']:
            max_possible_auto_score += Decimal(question.points)
            # --- Auto-grading logic (should match what happens on submission) ---
            is_correct = False
            if student_answer is not None:
                if question.question_type == 'SCQ':
                    is_correct = (str(student_answer).strip().lower() == str(question.correct_answer).strip().lower())
                elif question.question_type == 'MCQ':
                    # Assuming correct_answer is "A,B" and student_answer is a list ["A", "B"]
                    # Adjust this logic to match how you store MCQ answers
                    correct_set = set(op.strip().lower() for op in (question.correct_answer or "").split(',') if op.strip())
                    submitted_set = set(op.strip().lower() for op in student_answer if isinstance(student_answer, list))
                    is_correct = (correct_set == submitted_set and bool(correct_set))

            if is_correct:
                auto_graded_score += Decimal(question.points)

        elif question.question_type == 'ES':
            max_possible_manual_score += Decimal(question.points)

    # --- Prepare all questions data for display (your previous logic was fine) ---
    all_questions_data = []
    for question_obj in all_exam_questions.order_by('id'):
        student_answer_for_q = None
        raw_ans = student_answers.get(str(question_obj.id))
        if isinstance(raw_ans, list):
            student_answer_for_q = ", ".join(raw_ans)
        else:
            student_answer_for_q = raw_ans

        # Re-run a simplified version of auto-grading logic for display
        is_correct_auto = None
        if question_obj.question_type != 'ES' and student_answer_for_q is not None:
             is_correct_auto = (str(student_answer_for_q).strip().lower() == str(question_obj.correct_answer).strip().lower()) # This might need refinement for MCQ display

        all_questions_data.append({
            'question': question_obj,
            'student_answer': student_answer_for_q,
            'is_essay': question_obj.question_type == 'ES',
            'is_correct_auto': is_correct_auto
        })

    # --- Handle Form Submission ---
    if request.method == 'POST':
        manual_score_str = request.POST.get('manual_score')
        feedback = request.POST.get('feedback', '').strip()

        try:
            manual_score = Decimal(manual_score_str or '0.00')
            if manual_score < 0 or manual_score > max_possible_manual_score:
                messages.error(request, f"Manual score must be between 0 and {max_possible_manual_score}.")
                # (Re-render form logic...)
            else:
                final_score = auto_graded_score + manual_score
                submission.score = final_score
                submission.feedback = feedback
                submission.is_graded = True
                submission.requires_manual_review = False
                submission.save()
                messages.success(request, f"Grade finalized for {submission.student.user.get_full_name()}. Final score: {final_score}")

                if request.user.is_superuser:
                    return redirect('exam_submissions_list', exam_id=exam.id)
                else:
                    return redirect('teacher_exam_list')

        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid score entered. Please enter a valid number.")

    context = {
        'submission': submission,
        'exam': exam,
        'all_questions_data': all_questions_data,
        'auto_graded_score': auto_graded_score,
        'max_possible_auto_score': max_possible_auto_score,
        'max_possible_manual_score': max_possible_manual_score,
    }

    return render(request, 'exam/grade_essay_exam.html', context)