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
from django.db import transaction
from django.db.models import Q, Count, F, Sum, Subquery, OuterRef, IntegerField
from django.http import HttpResponseForbidden, Http404
from datetime import date
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from core.teacher.forms import TeacherRegistrationForm, MessageForm, ReplyForm
from core.models import CustomUser, Teacher, Student, Guardian, Class, Subject, Attendance, Assessment, Exam
from core.models import Assignment, Question, AssignmentSubmission, AssessmentSubmission, ExamSubmission, AcademicAlert
from core.models import Session, Term, Message, SubjectResult, Result
from core.subject_result.form import SubjectResultForm
from core.forms import NonAcademicSkillsForm
from core.assignment.forms import AssignmentForm, QuestionForm
from core.assessment.forms import AssessmentForm, OnlineQuestionForm
from core.exams.forms import ExamForm, OnlineQuestion
import logging

logger = logging.getLogger(__name__)

    # Helper: robust permission check for creator/editor (handles created_by being either a User or Teacher)
def _user_can_edit_created_object(user, obj):
    """Return True when user should be allowed to edit/delete an object they created.
    Handles common shapes: obj.created_by may be a User, a Teacher, or a related object.
    Also allows form-teachers for class-scoped objects.
    """
    if not user or not obj:
        return False
    # superusers always allowed
    if getattr(user, 'is_superuser', False):
        return True

    # direct equality check (created_by was stored as request.user)
    created_by = getattr(obj, 'created_by', None)
    try:
        if created_by == user:
            return True
    except Exception:
        pass

    # created_by might be a Teacher instance (or similar) with .user
    if created_by is not None and hasattr(created_by, 'user'):
        try:
            if created_by.user == user:
                return True
        except Exception:
            pass

    # created_by might be a User stored on a related teacher-like object
    # check if the requesting user has a teacher profile and matches created_by
    if hasattr(user, 'teacher') and created_by is not None:
        try:
            if created_by == user.teacher:
                return True
        except Exception:
            pass

    # If object has a class_assigned, allow the class form teacher to edit
    class_obj = getattr(obj, 'class_assigned', None)
    if class_obj is not None and hasattr(user, 'teacher'):
        try:
            form_teacher = class_obj.form_teacher() if hasattr(class_obj, 'form_teacher') else None
            if form_teacher and form_teacher == user.teacher:
                return True
        except Exception:
            pass

    return False
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
        'students': students, 
        'current_term': current_term,
        'student_attendance_summary': student_attendance_summary,
        'weeks_for_nav': weeks_date_objects,
        'selected_week_index': selected_week_index,
        'max_week_index': max_week_index,
        'week_days_for_log_display': school_week_days_for_log, 
    }
    return render(request, 'teacher/attendance_log.html', context)


@login_required
def input_scores(request, class_id, subject_id, term_id):
    class_obj = get_object_or_404(Class, id=class_id)
    subject = get_object_or_404(Subject, id=subject_id)
    term = get_object_or_404(Term, id=term_id)
    # Ensure we only get students currently enrolled in THIS class
    students = Student.objects.filter(current_class=class_obj, status='active').order_by('user__last_name', 'user__first_name').distinct()

    # Prepare instances and forms
    subject_results = {}
    forms_dict = {}
    for student in students:
        # Ensure a Result object exists for the student and term
        result_obj, _ = Result.objects.get_or_create(student=student, term=term)
        # Get or create the specific SubjectResult
        subject_result, _ = SubjectResult.objects.get_or_create(result=result_obj, subject=subject)
        subject_results[student.user.id] = subject_result 

    if request.method == 'POST':
        all_forms_valid = True
        forms_to_save = []

        for student in students:
            subject_result = subject_results.get(student.user.id)
            if not subject_result:
                 continue

            form = SubjectResultForm(request.POST, instance=subject_result, prefix=str(student.user.id))
            forms_dict[student] = form # Store the bound form for rendering

            if form.is_valid():
                forms_to_save.append(form) 
            else:
                all_forms_valid = False

        if all_forms_valid:
            for form in forms_to_save:
                form.save()
            messages.success(request, f"{subject.name} scores for {class_obj.name} submitted successfully.")
            return redirect('broadsheet', class_id=class_id, term_id=term_id)
        else:
            messages.error(request, "Please correct the errors below.")

    else: # GET request
        for student in students:
            subject_result = subject_results.get(student.user.id)
            forms_dict[student] = SubjectResultForm(instance=subject_result, prefix=str(student.user.id))

    context = {
        'forms': forms_dict, 
        'class': class_obj,
        'subject': subject,
        'term': term,
        'students': students, 
    }
    return render(request, 'teacher/input_scores.html', context)

# --- Broadsheet View  ---
@login_required
def broadsheet(request, class_id, term_id):
    class_obj = get_object_or_404(Class, id=class_id)
    term = get_object_or_404(Term, id=term_id)
    session = term.session

    students = Student.objects.filter(current_class=class_obj, status='active').select_related('user').order_by('user__last_name', 'user__first_name')

    subjects = Subject.objects.filter(
        class_assignments__class_assigned=class_obj,
        class_assignments__term=term
    ).distinct().order_by('name')

    results_data = []

    for student in students:
        result = Result.objects.filter(student=student, term=term).first()
        
        # --- Defensive Initialization for ALL variables ---
        student_subject_results = {}
        total_score_sum = Decimal('0.0')
        average_score = Decimal('0.0')
        student_gpa = Decimal('0.0')
        overall_grade = 'F'
        total_weighted_points = Decimal('0.0')
        total_weights = Decimal('0.0')
        graded_subject_count = 0

        if result:
            # Filter for graded subjects relevant to this broadsheet
            graded_subject_results = result.subject_results.filter(
                subject__in=subjects
            ).select_related('subject').exclude(
                continuous_assessment_1__isnull=True,
                continuous_assessment_2__isnull=True,
                continuous_assessment_3__isnull=True,
                assignment__isnull=True,
                oral_test__isnull=True,
                exam_score__isnull=True,
            )

            graded_subject_count = graded_subject_results.count()

            if graded_subject_count > 0:
                for sr in graded_subject_results:
                    student_subject_results[sr.subject.id] = sr
                    total_score_sum += sr.total_score()
                    
                    # --- WEIGHTED GPA CALCULATION ---
                    weight = Decimal(getattr(sr.subject, 'subject_weight', 1))
                    total_weighted_points += sr.calculate_grade_point() * weight
                    total_weights += weight

                # Calculate averages only if there were graded subjects
                average_score = total_score_sum / graded_subject_count
                student_gpa = total_weighted_points / total_weights if total_weights > 0 else Decimal('0.0')

                # Calculate the overall grade based on the correct average score
                if average_score >= 80: overall_grade = 'A'
                elif average_score >= 65: overall_grade = 'B'
                elif average_score >= 50: overall_grade = 'C'
                elif average_score >= 45: overall_grade = 'D'
                elif average_score >= 40: overall_grade = 'E'
                else: overall_grade = 'F'
        
        results_data.append({
            'student': student,
            'subject_results': student_subject_results, 
            'gpa': student_gpa.quantize(Decimal('0.01')), 
            'total_score': total_score_sum.quantize(Decimal('0.1')),
            'average_score': average_score.quantize(Decimal('0.1')),
            'grade': overall_grade,
        })

    # Sort students based on total score, then GPA
    results_data.sort(key=lambda x: (-x['total_score'], -x['gpa']))

    # Assign rank AFTER sorting is complete
    for i, data in enumerate(results_data):
        data['rank'] = i + 1

    context = {
        'class': class_obj,
        'term': term,
        'results_data': results_data,
        'subjects': subjects, 
        'session': session,
    }
    return render(request, 'teacher/broadsheet.html', context)


@login_required
def sessional_broadsheet(request, class_id, session_id):
    # Fetch core objects
    class_obj = get_object_or_404(Class, id=class_id)
    session = get_object_or_404(Session, id=session_id)
    
    # --- Authorization Check ---
    try:
        teacher = request.user.teacher
        # Check if teacher is assigned to this class
        if class_obj not in teacher.assigned_classes():
            return HttpResponseForbidden("You are not authorized to view this broadsheet.")
    except Teacher.DoesNotExist:
        return HttpResponseForbidden("You must have a teacher profile to view this page.")

    # Get all terms for this session, ordered
    terms_in_session = Term.objects.filter(session=session).order_by('start_date')
    if terms_in_session.count() == 0:
        messages.warning(request, f"No terms found for the {session.name} session.")
        # Redirect or render with a message
        return redirect('teacher_dashboard')

    # Get all subjects taught in this class for any term in this session
    subjects_in_class = Subject.objects.filter(
        class_assignments__class_assigned=class_obj,
        class_assignments__term__in=terms_in_session
    ).distinct().order_by('name')

    students_in_class = Student.objects.filter(current_class=class_obj, status='active').select_related('user').order_by('user__last_name', 'user__first_name')

    # --- Data Processing: Build a nested structure for the template ---
    broadsheet_data = []
    for student in students_in_class:
        student_data = {
            'student_obj': student,
            'sessional_gpa': 0.0,
            'subject_rows': [],
        }

        # Fetch all of this student's results for the session at once
        student_term_results = Result.objects.filter(
            student=student, 
            term__in=terms_in_session
        ).prefetch_related('subject_results__subject') # Efficiently prefetch related data

        # Create a map for easy lookup: {term_id: {subject_id: score}}
        scores_by_term_subject = defaultdict(dict)
        for result in student_term_results:
            for sr in result.subject_results.all():
                scores_by_term_subject[result.term_id][sr.subject_id] = sr.total_score()

        # Calculate Sessional GPA and build subject rows
        term_gpas_found = []
        for result in student_term_results:
            if result.term_gpa is not None:
                term_gpas_found.append(result.term_gpa)
        
        if term_gpas_found:
            student_data['sessional_gpa'] = sum(term_gpas_found) / len(term_gpas_found)

        # Structure data by subject for template rows
        for subject in subjects_in_class:
            term_scores = []
            valid_scores_for_avg = []
            for term in terms_in_session:
                score = scores_by_term_subject.get(term.id, {}).get(subject.id)
                term_scores.append(score)
                if score is not None:
                    valid_scores_for_avg.append(score)
            
            sessional_average = sum(valid_scores_for_avg) / len(valid_scores_for_avg) if valid_scores_for_avg else None
            
            student_data['subject_rows'].append({
                'subject_name': subject.name,
                'term_scores': term_scores,
                'sessional_average': sessional_average
            })
        
        broadsheet_data.append(student_data)

    context = {
        'teacher': teacher,
        'class_obj': class_obj,
        'session': session,
        'terms_in_session': terms_in_session,
        'subjects': subjects_in_class,
        'broadsheet_data': broadsheet_data, 
    }
    return render(request, 'teacher/sessional_broadsheet.html', context)


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
    
    submission.grade = (total_score / len(questions)) * 100  
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
def assignment_submissions_list(request, assignment_id):

    assignment = get_object_or_404(
        Assignment.objects.select_related('class_assigned', 'teacher__user'), 
        id=assignment_id
    )

    is_creator = assignment.teacher.user == request.user
    is_form_teacher = False
    if hasattr(request.user, 'teacher'):
        form_teacher_of_class = assignment.class_assigned.form_teacher()
        if form_teacher_of_class and form_teacher_of_class == request.user.teacher:
            is_form_teacher = True

    if not (request.user.is_superuser or is_creator or is_form_teacher):
        messages.error(request, "You are not authorized to view submissions for this assignment.")
        return redirect('teacher_dashboard')

    submissions = AssignmentSubmission.objects.filter(assignment=assignment) \
                                          .select_related('student__user') \
                                          .order_by('student__user__last_name')

    context = {
        'assignment': assignment,
        'submissions': submissions,
    }
    return render(request, 'assignment/assignment_submissions_list.html', context)

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
    """Process newly added questions from the POST payload.
    Returns a tuple: (posted_questions_data, errors)
    - posted_questions_data: list of dicts {index, question_type, question_text, options, correct_answer, points}
    - errors: list of error strings
    """
    errors = []
    posted_questions = []
    question_number = 1
    questions_successfully_added = 0

    while True:
        q_type_key = f'{question_name_prefix}type_{question_number}'
        q_text_key = f'{question_name_prefix}text_{question_number}'
        q_options_key = f'{question_name_prefix}options_{question_number}'
        q_correct_key = f'{question_name_prefix}correct_answer_{question_number}'
        q_points_key = f'{question_name_prefix}points_{question_number}'

        if q_type_key not in request.POST and q_text_key not in request.POST:
            break

        question_type = request.POST.get(q_type_key)
        question_text = request.POST.get(q_text_key, '').strip()
        options_str = request.POST.get(q_options_key, '')
        correct_answer_str = request.POST.get(q_correct_key, '').strip()
        points_str = request.POST.get(q_points_key)

        # Collect posted representation for hydration even if invalid
        options_list = [opt.strip() for opt in options_str.split(',') if opt.strip()]
        posted_questions.append({
            'index': question_number,
            'question_type': question_type,
            'question_text': question_text,
            'options': options_list,
            'correct_answer': correct_answer_str if correct_answer_str else None,
            'points': points_str if points_str else None,
        })

        if not question_text and not question_type:
            question_number += 1
            continue
        if not question_text:
            if question_type:
                errors.append(f"Error in New Question {question_number}: Text is empty.")
            question_number += 1
            continue

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
                # Only add to assessment/exam if provided assessment has been saved
                try:
                    assessment.questions.add(new_question)
                except Exception:
                    # If assessment isn't persisted (transactional rollback scenario), just keep posted data
                    pass
                questions_successfully_added += 1
            except Exception as e:
                errors.append(f"Error saving new question {question_number}: {str(e)}")
        else:
            for field, field_errors in question_form.errors.items():
                errors.append(f"New Question {question_number} ({field.replace('_',' ').title()}): {', '.join(field_errors)}")

        question_number += 1

    if questions_successfully_added == 0 and f'{question_name_prefix}type_1' in request.POST:
        if not errors:
            errors.append("Attempted to add new questions, but none were valid or saved.")

    return posted_questions, errors

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
            posted_questions = []
            question_processing_errors = []
            try:
                with transaction.atomic():
                    assessment = form.save(commit=False)
                    assessment.created_by = user
                    if user.is_superuser: # Superusers can auto-approve
                        assessment.is_approved = True
                    assessment.save()

                    posted_questions, question_processing_errors = _process_newly_added_questions(request, assessment, question_name_prefix='question_')
                    if question_processing_errors:
                        # Force a rollback
                        raise ValueError('Question processing errors')

                # If we get here, transaction committed and no question errors
                messages.success(request, f"Assessment '{assessment.title}' created successfully.")
                return redirect('school-setup' if user.is_superuser else 'teacher_dashboard')
            except Exception:
                # Render the form with posted question data and errors (no half-saved objects due to atomic rollback)
                form_with_initial_data = AssessmentForm(request.POST) # Re-bind to show original data
                form_with_initial_data.fields['class_assigned'].queryset = assigned_classes_qs
                form_with_initial_data.fields['subject'].queryset = assigned_subjects_qs
                messages.error(request, "Assessment not created. Please correct the question errors.")
                return render(request, 'assessment/create_assessment.html', {
                    'form': form_with_initial_data,
                    'question_errors': question_processing_errors,
                    'posted_questions_json': json.dumps(posted_questions),
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
    
    # Authorization: allow superuser, creators, or class form teacher
    if not _user_can_edit_created_object(user, assessment):
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

            posted_new_questions, new_question_errors = _process_newly_added_questions(request, assessment, question_name_prefix='new_question_')
            all_errors.extend(new_question_errors)

            # --- Redirect or Re-render Logic (remains the same) ---
            if not all_errors:
                messages.success(request, "Assessment updated successfully.")
                return redirect('view_assessment', assessment_id=assessment.id)
            else:
                messages.error(request, "Errors occurred while processing questions. Please review.")
        
        # If form is invalid or question processing had errors, re-render the page
        current_questions = assessment.questions.all().order_by('id')
        context = {
            'form': form,
            'assessment': assessment,
            'questions': current_questions,
            'processing_errors': all_errors if 'all_errors' in locals() else [],
            'can_edit': _user_can_edit_created_object(user, assessment),
        }
        # If there were posted new questions, include them for client-side hydration
        if 'posted_new_questions' in locals() and posted_new_questions:
            context['posted_questions_json'] = json.dumps(posted_new_questions)

        return render(request, 'assessment/update_assessment.html', context)

    else: # GET request
        form = AssessmentForm(instance=assessment)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs
        questions = assessment.questions.all().order_by('id')
        return render(request, 'assessment/update_assessment.html', {
            'form': form,
            'assessment': assessment,
            'questions': questions,
            'can_edit': _user_can_edit_created_object(user, assessment),
        })
    

@login_required
def teacher_assessment_list(request):
    try:
        teacher = get_object_or_404(Teacher, user=request.user)
    except Teacher.DoesNotExist:
        messages.error(request, "You do not have a teacher profile.")
        return redirect('home')

    # Get the list of classes where this teacher is the FORM TEACHER
    form_teacher_classes = teacher.current_classes().all()
    
    # --- Subqueries for annotation (these are efficient and well-written) ---
    total_submissions_subquery = AssessmentSubmission.objects.filter(
        assessment=OuterRef('pk')
    ).values('assessment').annotate(count=Count('pk')).values('count')

    graded_submissions_subquery = AssessmentSubmission.objects.filter(
        assessment=OuterRef('pk'),
        is_graded=True
    ).values('assessment').annotate(count=Count('pk')).values('count')

    # This query now fetches assessments that meet EITHER condition:
    # 1. The assessment was created by the logged-in teacher.
    # 2. The assessment is assigned to a class where the teacher is the form teacher.
    
    assessments_for_teacher = Assessment.objects.filter(
        Q(created_by=request.user) | Q(class_assigned__in=form_teacher_classes)
    ).distinct().select_related( # Use distinct() to avoid duplicates if a teacher creates an assessment for their own form class
        'class_assigned', 'subject'
    ).annotate(
        total_possible_score=Sum('questions__points'),
        submission_count=Subquery(total_submissions_subquery, output_field=IntegerField()),
        submission_count_graded=Subquery(graded_submissions_subquery, output_field=IntegerField())
    ).order_by('-created_at')

    pending_submissions_to_grade = AssessmentSubmission.objects.filter(
        assessment__in=assessments_for_teacher, # Filter based on the assessments we just found
        requires_manual_review=True,
        is_graded=False
    ).select_related(
        'assessment', 'student__user', 'assessment__class_assigned'
    ).order_by('submitted_at')

    context = {
        'assessments': assessments_for_teacher,
        'pending_submissions_to_grade': pending_submissions_to_grade,
        'page_title': "Manage Assessments", 
    }
    return render(request, 'assessment/teacher_assessment_list.html', context)

@login_required
def assessment_submissions_list(request, assessment_id):
    assessment = get_object_or_404(Assessment.objects.select_related('class_assigned__form_teacher__user'), id=assessment_id)

    is_creator = assessment.created_by == request.user
    is_form_teacher = hasattr(request.user, 'teacher') and assessment.class_assigned.form_teacher == request.user.teacher

    if not (request.user.is_superuser or is_creator or is_form_teacher):
        messages.error(request, "You are not authorized to view submissions for this assessment.")
        return redirect('teacher_dashboard')

    submissions = AssessmentSubmission.objects.filter(assessment=assessment) \
                                          .select_related('student__user') \
                                          .order_by('-submitted_at')
    
    context = { 'assessment': assessment, 'submissions': submissions}
    return render(request, 'assessment/assessment_submissions_list.html', context)


@login_required
def view_assessment(request, assessment_id):

    assessment = get_object_or_404(Assessment.objects.select_related('class_assigned', 'created_by'), id=assessment_id)
    # Authorization: allow superuser, creators, or class form teacher
    if not _user_can_edit_created_object(request.user, assessment):
        messages.error(request, "You are not authorized to view this assessment's details.")
        return redirect('teacher_dashboard')

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
        'can_edit': _user_can_edit_created_object(request.user, assessment),
    }
    return render(request, 'assessment/assessment_detail.html', context)



@login_required
def delete_assessment(request, assessment_id):
    assessment = get_object_or_404(Assessment, id=assessment_id)
    teacher = get_object_or_404(Teacher, user=request.user)

    # Ensure the logged-in user is the creator, form-teacher, or an admin
    if not _user_can_edit_created_object(request.user, assessment):
        return HttpResponseForbidden("You do not have permission to delete this assessment.")

    if request.method == 'POST':
        assessment.delete()
        return redirect('teacher_dashboard')

    return render(request, 'assessment/delete_assessment.html', {
        'assessment': assessment,
        'can_edit': _user_can_edit_created_object(request.user, assessment),
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
            posted_questions = []
            question_processing_errors = []
            try:
                with transaction.atomic():
                    exam = form.save(commit=False)
                    exam.created_by = user
                    if user.is_superuser: # Superusers can auto-approve
                        exam.is_approved = True
                    exam.save()

                    posted_questions, question_processing_errors = _process_newly_added_questions(request, exam, question_name_prefix='question_')
                    if question_processing_errors:
                        raise ValueError('Question processing errors')

                messages.success(request, f"Exam '{exam.title}' created successfully.")
                return redirect('school-setup' if user.is_superuser else 'teacher_dashboard')
            except Exception:
                form_with_initial_data = ExamForm(request.POST) # Re-bind to show original data
                form_with_initial_data.fields['class_assigned'].queryset = assigned_classes_qs
                form_with_initial_data.fields['subject'].queryset = assigned_subjects_qs
                messages.error(request, "Exam not created. Please correct the question errors.")
                return render(request, 'exam/create_exam.html', {
                    'form': form_with_initial_data,
                    'question_errors': question_processing_errors,
                    'posted_questions_json': json.dumps(posted_questions),
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

    # Authorization: allow superuser, creators, or class form teacher
    if not _user_can_edit_created_object(user, exam):
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
            posted_new_questions, new_question_errors = _process_newly_added_questions(request, exam, question_name_prefix='new_question_')
            all_errors.extend(new_question_errors)

            if not all_errors:
                messages.success(request, "Exam updated successfully.")
                return redirect('view_exam', exam_id=exam.id)
            else:
                messages.error(request, "Errors occurred. Please review.")
        # If form is invalid or errors occurred, re-render with context
        current_questions = exam.questions.all().order_by('id')
        context = {
            'form': form, # This form instance will have its own errors
            'exam': exam,
            'questions': current_questions,
            'processing_errors': all_errors if 'all_errors' in locals() and all_errors else [],
            'can_edit': _user_can_edit_created_object(user, exam),
        }
        if 'posted_new_questions' in locals() and posted_new_questions:
            context['posted_questions_json'] = json.dumps(posted_new_questions)
        return render(request, 'exam/update_exam.html', context)

    else: # GET request
        form = ExamForm(instance=exam)
        form.fields['class_assigned'].queryset = assigned_classes_qs
        form.fields['subject'].queryset = assigned_subjects_qs
        questions = exam.questions.all().order_by('id')
        return render(request, 'exam/update_exam.html', {
            'form': form,
            'exam': exam,
            'questions': questions,
            'can_edit': _user_can_edit_created_object(user, exam),
        })

@login_required
def teacher_exam_list(request):
    try:
        teacher = get_object_or_404(Teacher, user=request.user)
    except Teacher.DoesNotExist:
        messages.error(request, "You do not have a teacher profile.")
        return redirect('home')

    # Get the list of classes where this teacher is the FORM TEACHER
    form_teacher_classes = teacher.current_classes().all()
    
    # --- Subqueries for annotation (these are efficient and well-written) ---
    total_submissions_subquery = ExamSubmission.objects.filter(
        exam=OuterRef('pk')
    ).values('exam').annotate(count=Count('pk')).values('count')

    graded_submissions_subquery = ExamSubmission.objects.filter(
        exam=OuterRef('pk'),
        is_graded=True
    ).values('exam').annotate(count=Count('pk')).values('count')

    # This query now fetches exams that meet EITHER condition:
    # 1. The exam was created by the logged-in teacher.
    # 2. The exam is assigned to a class where the teacher is the form teacher.
    
    exams_for_teacher = Exam.objects.filter(
        Q(created_by=request.user) | Q(class_assigned__in=form_teacher_classes)
    ).distinct().select_related( # Use distinct() to avoid duplicates if a teacher creates an exam for their own form class
        'class_assigned', 'subject'
    ).annotate(
        total_possible_score=Sum('questions__points'),
        submission_count=Subquery(total_submissions_subquery, output_field=IntegerField()),
        submission_count_graded=Subquery(graded_submissions_subquery, output_field=IntegerField())
    ).order_by('-created_at')

    pending_submissions_to_grade = ExamSubmission.objects.filter(
        exam__in=exams_for_teacher, # Filter based on the exams we just found
        requires_manual_review=True,
        is_graded=False
    ).select_related(
        'exam', 'student__user', 'exam__class_assigned'
    ).order_by('submitted_at')

    context = {
        'exams': exams_for_teacher,
        'pending_submissions_to_grade': pending_submissions_to_grade,
        'page_title': "Manage Exams", 
    }
    return render(request, 'exam/teacher_exam_list.html', context)


@login_required
def exam_submissions_list(request, exam_id):
    exam = get_object_or_404(Exam.objects.select_related('class_assigned__form_teacher__user'), id=exam_id)

    is_creator = exam.created_by == request.user
    is_form_teacher = hasattr(request.user, 'teacher') and exam.class_assigned.form_teacher == request.user.teacher

    if not (request.user.is_superuser or is_creator or is_form_teacher):
        messages.error(request, "You are not authorized to view submissions for this exam.")
        return redirect('teacher_dashboard')

    submissions = ExamSubmission.objects.filter(exam=exam) \
                                          .select_related('student__user') \
                                          .order_by('-submitted_at')
    
    context = { 'exam': exam, 'submissions': submissions}
    return render(request, 'exam/exam_submissions_list.html', context)


@login_required
def view_exam(request, exam_id):

    exam = get_object_or_404(Exam.objects.select_related('class_assigned', 'created_by'), id=exam_id)
    # Authorization: allow superuser, creators, or class form teacher
    if not _user_can_edit_created_object(request.user, exam):
        messages.error(request, "You are not authorized to view this exam's details.")
        return redirect('teacher_dashboard')

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
        'can_edit': _user_can_edit_created_object(request.user, exam),
    }
    return render(request, 'exam/exam_detail.html', context)


@login_required
def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    teacher = get_object_or_404(Teacher, user=request.user)

    # Ensure the logged-in user is the creator, form-teacher, or an admin
    if not _user_can_edit_created_object(request.user, exam):
        return HttpResponseForbidden("You do not have permission to delete this exam.")

    if request.method == 'POST':
        exam.delete()
        return redirect('teacher_dashboard')

    return render(request, 'exam/delete_exam.html', {
        'exam': exam,
        'can_edit': _user_can_edit_created_object(request.user, exam),
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