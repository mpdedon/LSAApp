# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import AssignmentForm, AssessmentForm, AttendanceForm
from ..models import Assignment

# Assignment Views
class AssignmentCreateView(View):
    template_name = 'assignment/assignment_form.html'

    def get(self, request, *args, **kwargs):
        form = AssignmentForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = AssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('assignment_list')
        return render(request, self.template_name, {'form': form})

class AssignmentUpdateView(View):
    template_name = 'assignment/assignment_form.html'

    def get(self, request, pk, *args, **kwargs):
        assignment = get_object_or_404(Assignment, pk=pk)
        form = AssignmentForm(instance=assignment)
        return render(request, self.template_name, {'form': form, 'is_update': True})

    def post(self, request, pk, *args, **kwargs):
        assignment = get_object_or_404(Assignment, pk=pk)
        form = AssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            return redirect('assignment_list')
        return render(request, self.template_name, {'form': form, 'is_update': True})

class AssignmentDeleteView(View):
    template_name = 'assignment/assignment_confirm_delete.html'

    def get(self, request, pk, *args, **kwargs):
        assignment = get_object_or_404(Assignment, pk=pk)
        return render(request, self.template_name, {'assignment': assignment})

    def post(self, request, pk, *args, **kwargs):
        assignment = get_object_or_404(Assignment, pk=pk)
        assignment.delete()
        return redirect('assignment_list')

class AssignmentListView(View):
    template_name = 'assignment/assignment_list.html'

    def get(self, request, *args, **kwargs):
        assignments = Assignment.objects.all()
        return render(request, self.template_name, {'assignments': assignments})

    def post(self, request, *args, **kwargs):
        form = AssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('assignment_list')
        assignments = Assignment.objects.all()
        return render(request, self.template_name, {'assignments': assignments, 'form': form})

class AssignmentDetailView(View):
    template_name = 'assignment/assignment_detail.html'

    def get(self, request, pk, *args, **kwargs):
        assignment = get_object_or_404(Assignment, pk=pk)
        return render(request, self.template_name, {'assignment': assignment})

