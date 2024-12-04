from django.shortcuts import render, redirect, get_object_or_404
from core.models import Student, Class, Session, Term, Enrollment
from .forms import EnrollmentForm  

def StudentClassEnrollmentView(request):
    if request.method == 'POST':
        form = EnrollmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('student_list')
    else:
        form = EnrollmentForm()
    
    return render(request, 'enrol_student.html', {'form': form})

def StudentEnrollmentsView(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    enrollments = student.enrollments.all()
    return render(request, 'view_enrollments.html', {'student': student, 'enrollments': enrollments})
