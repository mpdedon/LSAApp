# core.student.views

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q
from core.models import Student, Assignment, AssignmentSubmission
from .forms import StudentRegistrationForm
from core.assignment.forms import AssignmentSubmissionForm

# Student Views

def StudentRegisterView(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('student_dashboard')
    else:
        form = StudentRegistrationForm()
    return render(request, 'student/register.html', {'form': form})

def StudentProfileView(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('student_dashboard')
    else:
        form = StudentRegistrationForm(instance=request.user)
    return render(request, 'student/profile.html', {'form': form})

@login_required
def student_dashboard(request):
    if not request.user.role == 'student':
        return redirect('login')
    # Add any data for students
    return render(request, 'student_dashboard.html')
    
class StudentListView(View):
    template_name = 'student/student_list.html'

    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        status = request.GET.get('status', 'active')  # Default to 'active'

        # Filter students by status
        students = Student.objects.filter(status=status).order_by('current_class')

        # Apply search filter
        if query:
            students = students.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(LSA_number__icontains=query) |
                Q(current_class__name__icontains=query) |
                Q(student_guardian__user__first_name__icontains=query) |
                Q(student_guardian__user__last_name__icontains=query)
            )

        # Paginate students
        paginator = Paginator(students, 15)  # Show 15 students per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'active_tab': status
        })

class BulkUpdateStudentsView(View):
    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        selected_students = request.POST.getlist("selected_students")

        if not selected_students:
            messages.error(request, "No students selected for the bulk action.")
            return redirect("student_list")

        students = Student.objects.filter(user__id__in=selected_students)

        if action == "promote":
            for student in students:
                if student.current_class and student.current_class.next_class:
                    student.current_class = student.current_class.next_class
                    student.save()
            messages.success(request, "Selected students have been promoted.")
        
        elif action == "demote":
            for student in students:
                if student.current_class and student.current_class.previous_class:
                    student.current_class = student.current_class.previous_class
                    student.save()
            messages.success(request, "Selected students have been demoted.")

        elif action == "mark_dormant":
            students.update(status="dormant")
            messages.success(request, "Selected students have been marked as dormant.")
        
        elif action == "mark_active":
            students.update(status="active")
            messages.success(request, "Selected students have been marked as active.")
        
        elif action == "mark_left":
            students.update(status="left")
            messages.success(request, "Selected students have been marked as left.")
        
        else:
            messages.error(request, "Invalid action selected.")

        return redirect("student_list")


class StudentCreateView(View):
    template_name = 'student/student_form.html'

    def get(self, request, *args, **kwargs):
        form = StudentRegistrationForm()
        response = render(request, self.template_name, {'form': form})
        return response

    def post(self, request, *args, **kwargs):
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            print("Successfully saved form")
            return redirect('student_list')
        else:
            print("Form is NOT valid. Errors: ", form.errors)
        return render(request, self.template_name, {'form': form})

class StudentUpdateView(View):
    template_name = 'student/student_form.html'

    def get(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        form = StudentRegistrationForm(instance=student.user, student_instance=student)
        return render(request, self.template_name, {'form': form, 'is_update': True, 'student': student})

    def post(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        form = StudentRegistrationForm(request.POST, request.FILES, instance=student.user)

        # Ensure the student fields are updated correctly
        if form.is_valid():
            user = form.save(commit=False)
            user.save()

            student.date_of_birth = form.cleaned_data['date_of_birth']
            student.gender = form.cleaned_data['gender']
            student.profile_image = form.cleaned_data['profile_image']
            student.student_guardian = form.cleaned_data['student_guardian']
            student.relationship = form.cleaned_data['relationship']
            student.current_class = form.cleaned_data['current_class']
            student.save()

            return redirect('student_detail', pk=student.pk)

        return render(request, self.template_name, {'form': form, 'is_update': True, 'student': student})

class StudentDetailView(View):
    template_name = 'student/student_detail.html'

    def get(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        return render(request, self.template_name, {'student': student})

class StudentDeleteView(View):
    template_name = 'student/student_confirm_delete.html'

    def get(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        return render(request, self.template_name, {'student': student})

    def post(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, pk=pk)
        student.delete()
        return redirect('student_list')

# Example for export_students and student_reports
def export_students(request):
    # Implement export logic here
    pass

def student_reports(request):
    # Implement report generation logic here
    pass

@login_required
def submit_assignment(request, assignment_id):
    # Get the assignment or return a 404 if not found
    assignment = get_object_or_404(Assignment, id=assignment_id)

    # Determine the logged-in user's type
    if hasattr(request.user, 'guardian'):
        guardian = request.user.guardian

        # Filter students by the guardian and the assignment's class
        students = Student.objects.filter(
            student_guardian=guardian,
            current_class=assignment.class_assigned
        )

        if not students.exists():
            messages.error(request, "No students associated with this guardian are enrolled in the assignment's class.")
            return redirect('guardian_dashboard')

        # Check if a specific student is selected
        student_id = request.GET.get('student_id')
        if student_id:
            student = get_object_or_404(students, id=student_id)
        elif students.count() == 1:
            student = students.first()
        else:
            # Render a selection page if multiple students match
            return render(request, 'assignment/select_student.html', {
                'students': students,
                'assignment': assignment,
            })

    else:
        # Handle student users submitting their own assignment
        student = get_object_or_404(
            Student,
            user=request.user,
            current_class=assignment.class_assigned
        )

    # Handle form submission
    if request.method == 'POST':
        answers = {}
        
        # Collect the answers for each question
        for question in assignment.questions.all():
            answer_key = f'answers[{question.id}]'
            answer_value = request.POST.get(answer_key)

            # If the answer exists for this question, store it
            if answer_value:
                # For MCQ/SCQ, answers will be stored as the selected option
                answers[question.id] = answer_value
            else:
                # For essay questions, we might want to store the plain text response
                if question.question_type == 'ES':
                    essay_answer = request.POST.get(f'answers_essay[{question.id}]')
                    if essay_answer:
                        answers[question.id] = essay_answer

        # If answers are valid, save the submission
        if answers:
            submission = AssignmentSubmission.objects.create(
                student=student,
                assignment=assignment,
                answers=json.dumps(answers),  # Save answers as JSON
                is_completed=True,
            )
            messages.success(request, "Your assignment has been successfully submitted!")
            return redirect('guardian_dashboard' if hasattr(request.user, 'guardian') else 'student_dashboard')

        messages.error(request, "Please answer all questions before submitting.")
        return redirect('submit_assignment', assignment_id=assignment_id)
            
    else:
        form = AssignmentSubmissionForm()

    # Render the form for assignment submission
    return render(request, 'assignment/submit_assignment.html', {
        'assignment': assignment,
        'form': form,
        'student': student,
    })
