# views.py

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.timezone import now
from django.urls import reverse, reverse_lazy
from django.db.models import Q, Count, Prefetch, F
from datetime import date
from .forms import TeacherRegistrationForm, MessageForm
from core.forms import NonAcademicSkillsForm
from core.models import Teacher, Student, Guardian, Class, Subject, Attendance, Assessment
from core.models import Assignment, Question, AssignmentSubmission, AcademicAlert
from core.models import Session, Term, Message, Holiday, SubjectResult, Result, SubjectAssignment
from core.subject_result.form import SubjectResultForm
from core.assignment.forms import AssignmentForm, QuestionForm, AssignmentSubmissionForm


# Teacher Views

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

class TeacherListView(View):
    template_name = 'teacher/teacher_list.html'

    def get(self, request, *args, **kwargs):
        status = request.GET.get('status', 'active')
        query = request.GET.get('q', '')

        teachers = Teacher.objects.filter(status=status).order_by('current_class')

        if query:
            teachers = teachers.filter(
                Q(user__username__icontains=query)  |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__email__icontains=query) |
                Q(current_class__name__icontains=query) 
            )

        # Pagination
        paginator = Paginator(teachers, 15)  # Show 15 teachers per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'active_tab': status,
        })

class TeacherBulkActionView(View):
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
def mark_attendance(request, class_id):
    class_instance = Class.objects.get(id=class_id)
    students = class_instance.enrolled_students.all()

    # Fetch the active session and term
    current_session = Session.objects.get(is_active=True)
    current_term = Term.objects.filter(session=current_session, is_active=True).order_by('-start_date').first()

    # Get the current week based on today's date and the term's start date
    weeks = current_term.get_term_weeks()
    # Calculate the current week (how many weeks have passed since the term started)
    today = date.today()
    start_date = current_term.start_date
    current_week = (today - start_date).days // 7  # Calculate which week we're currently in

    # Handle the case where the `week` parameter is passed via the URL
    selected_week = int(request.GET.get('week', current_week))

    # Ensure the selected week is within a valid range
    selected_week = max(0, min(selected_week, len(weeks) - 1))

    # Determine the selected week's date range
    if weeks and isinstance(weeks[selected_week], list):  # Ensure that weeks[selected_week] is a list
        week_days = weeks[selected_week]  # Using the selected week's days directly for display
    else:
        week_days = []

    # Exclude weekends (Saturday and Sunday)
    week_days = [day for day in week_days if day.weekday() < 5]

    # Get attendance records for the week
    if week_days:  # Ensure week_days is not empty
        attendance_records = Attendance.objects.filter(
            class_assigned=class_instance,
            date__in=week_days,
            term=current_term
        ).select_related('student')
    else:
        attendance_records = Attendance.objects.none()

    # Prepare attendance dictionary: {student_id: {date: attendance_record}}
    attendance_dict = {}
    for record in attendance_records:
        student_id = record.student.user.id
        record_date = record.date  # Changed 'date' to 'record_date' to avoid confusion
        if student_id not in attendance_dict:
            attendance_dict[student_id] = {}
        attendance_dict[student_id][record_date] = record.is_present

    if request.method == 'POST':
        # Check if attendance has already been submitted for this week
        #if Attendance.objects.filter(class_assigned=class_instance, term=current_term, date__in=week_days).exists():
        #    messages.error(request, "Attendance for this week has already been submitted and cannot be edited.")
        #    return redirect('attendance_log', class_id=class_instance.id)

        for student in students:
            for day in week_days:
                day_str = day.strftime("%Y-%m-%d")
                attendance_status = request.POST.get(f'attendance_{student.user.id}_{day_str}')

                if attendance_status:
                    is_present = True if attendance_status == 'present' else False

                    # Create or update attendance record for each day in the week
                    attendance_record, created = Attendance.objects.update_or_create(
                        student=student,
                        date=day,
                        class_assigned=class_instance,
                        term=current_term,
                        defaults={'is_present': is_present}
                    )

                    if created:
                        print(f"Created attendance record for {student}: {attendance_record}")
                    else:
                        print(f"Updated attendance record for {student}: {attendance_record}")

        messages.success(request, "Attendance marked successfully.")
        return redirect('attendance_log', class_id=class_instance.id)  # Redirect to the attendance log

    # Get today's date
    today = date.today()

    # Determine the maximum week number based on today's date
    max_week = next((i for i, week in enumerate(weeks) if week[-1] > today), len(weeks) - 1)

    context = {
        'class_instance': class_instance,
        'students': students,
        'weeks': weeks,
        'selected_week': selected_week,
        'week_days': week_days,
        'attendance_dict': attendance_dict,
        'current_week': current_week,
        'total_weeks': len(weeks),  # Total number of weeks for navigation
        'max_week': max_week,  # New variable to control navigation
    }
    return render(request, 'teacher/mark_attendance.html', context)

@login_required
def attendance_log(request, class_id):
    class_instance = Class.objects.get(id=class_id)
    students = class_instance.enrolled_students.all()

    # Get active session and term
    current_session = Session.objects.get(is_active=True)
    current_term = Term.objects.filter(session=current_session, is_active=True).order_by('-start_date').first()

    # Get the current week based on today's date and the term's start date
    weeks = current_term.get_term_weeks()

    today = date.today()
    start_date = current_term.start_date
    current_week = (today - start_date).days // 7  # Calculate which week we're currently in

    # Get the selected week from the URL or use the current week by default
    selected_week = int(request.GET.get('week', current_week))

    # Ensure the selected week is within valid range
    selected_week = max(0, min(selected_week, len(weeks) - 1))

    # Get the week days for the selected week
    week_days = weeks[selected_week] if weeks and isinstance(weeks[selected_week], list) else []

    # Exclude weekends (Saturday and Sunday)
    week_days = [day for day in week_days if day.weekday() < 5]

    # Get attendance records for the selected week
    attendance_records = Attendance.objects.filter(
        class_assigned=class_instance,
        date__in=week_days,
        term=current_term
    ).select_related('student')
    
    # Summarize attendance for each student
    student_attendance_summary = []

    for student in students:
        
        total_present_week = Attendance.objects.filter(
            class_assigned=class_instance,
            term=current_term,
            student=student,
            is_present=True,
            date__in=week_days  # Filter for current week
        ).count()
        
        total_absent_week = Attendance.objects.filter(
            class_assigned=class_instance,
            term=current_term,
            student=student,
            is_present=False,
            date__in=week_days  # Filter for current week
        ).count()

        # Total attendance to date
        total_present = Attendance.objects.filter(
            class_assigned=class_instance,
            term=current_term,
            student=student,
            is_present=True
        ).count()
        
        total_absent = Attendance.objects.filter(
            class_assigned=class_instance,
            term=current_term,
            student=student,
            is_present=False
        ).count()

        today = date.today()

        # Determine the maximum week number based on today's date
        max_week = next((i for i, week in enumerate(weeks) if week[-1] > today), len(weeks) - 1)

        student_attendance_summary.append({
            'student': student,
            'total_present_week': total_present_week,
            'total_absent_week': total_absent_week,
            'total_present': total_present,
            'total_absent': total_absent,
        })

    context = {
        'class_instance': class_instance,
        'student_attendance_summary': student_attendance_summary,
        'current_week': current_week,
        'weeks': weeks,
        'max_week': max_week,
    }
    return render(request, 'teacher/attendance_log.html', context)

@login_required
def input_scores(request, class_id, subject_id, term_id):
    class_obj = get_object_or_404(Class, id=class_id)
    subject = get_object_or_404(Subject, id=subject_id)
    term = get_object_or_404(Term, id=term_id)
    students = class_obj.students.all()

    # Collect all subject results for the term
    subject_results = {}
    for student in students:
        result, _ = Result.objects.get_or_create(student=student, term=term)
        subject_result, _ = SubjectResult.objects.get_or_create(result=result, subject=subject)
        subject_results[student] = subject_result  # Store results by student

    if request.method == 'POST':
        final_submit = request.POST.get('final_submit', '') == 'true'
        all_forms_valid = True

        for student, subject_result in subject_results.items():
            form = SubjectResultForm(request.POST, instance=subject_result, prefix=str(student.user.id))

            if form.is_valid():
                subject_result = form.save(commit=False)
                subject_result.is_finalized = final_submit
                subject_result.save()  # Save the updated scores
                print(f"Saved for {student.user.get_full_name}: Finalized: {subject_result.is_finalized}, CA1: {subject_result.continuous_assessment_1}")
            else:
                all_forms_valid = False
                print(f"Form errors for {student.user.get_full_name}: {form.errors}")

        if all_forms_valid:
            return redirect('broadsheet', class_id=class_id, term_id=term_id)

    forms = {student: SubjectResultForm(instance=subject_result, prefix=str(student.user.id)) for student, subject_result in subject_results.items()}

    context = {
        'forms': forms,
        'class': class_obj,
        'subject': subject,
        'term': term,
        'students': students,
    }
    return render(request, 'teacher/input_scores.html', context)

@login_required
def broadsheet(request, class_id, term_id):
    class_obj = get_object_or_404(Class, id=class_id)
    term = get_object_or_404(Term, id=term_id)
    students = class_obj.students.all()

    subjects = class_obj.subjects.all()
    print(subjects)
    
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
            })

    # Sort students by total score and then by GPA
    results_data.sort(key=lambda x: (-x['total_score'], -x['gpa']))

    context = {
        'students': subjects,
        'class': class_obj,
        'term': term,
        'results_data': results_data,
        'subjects': subjects,
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
    assigned_classes = Class.objects.filter(teacher=teacher)
    subjects = Subject.objects.filter(subjectassignment__class_assigned__in=assigned_classes).distinct()

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
                # Notify students in the assigned class
                students = Student.objects.filter(current_class=assignment.class_assigned)
                for student in students:
                    AcademicAlert.objects.create(
                        alert_type='assignment',
                        title=assignment.title,
                        summary=assignment.description or 'New assignment available!',
                        teacher=teacher,
                        student=student,
                        due_date=assignment.due_date,
                        related_object_id=assignment.id
                    )
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