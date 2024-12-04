from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import TeacherAssignmentForm
from ..models import TeacherAssignment

class TeacherAssignmentListView(View):
    template_name = 'teacher_assignment/teacher_assignment_list.html'

    def get(self, request):
        teacher_assignments = TeacherAssignment.objects.all()
        return render(request, self.template_name, {'teacher_assignments': teacher_assignments})

class TeacherAssignmentDetailView(View):
    template_name = 'teacher_assignment/teacher_assignment_detail.html'

    def get(self, request, pk):
        teacher_assignment = get_object_or_404(TeacherAssignment, pk=pk)
        return render(request, self.template_name, {'teacher_assignment': teacher_assignment})

class TeacherAssignmentCreateView(View):
    template_name = 'teacher_assignment/teacher_assignment_form.html'

    def get(self, request):
        form = TeacherAssignmentForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = TeacherAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('teacher_assignment_list')
        return render(request, self.template_name, {'form': form})

class TeacherAssignmentUpdateView(View):
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

class TeacherAssignmentDeleteView(View):
    template_name = 'teacher_assignment/teacher_assignment_confirm_delete.html'

    def get(self, request, pk):
        teacher_assignment = get_object_or_404(TeacherAssignment, pk=pk)
        return render(request, self.template_name, {'teacher_assignment': teacher_assignment})

    def post(self, request, pk):
        teacher_assignment = get_object_or_404(TeacherAssignment, pk=pk)
        teacher_assignment.delete()
        return redirect('teacher_assignment_list')
