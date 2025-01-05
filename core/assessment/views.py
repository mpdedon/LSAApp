# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import AssessmentForm
from ..models import Assessment


class AssessmentCreateView(View):
    template_name = 'assessment/assessment_form.html'

    def get(self, request, *args, **kwargs):
        form = AssessmentForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = AssessmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('assessment_list')
        return render(request, self.template_name, {'form': form})

class AssessmentUpdateView(View):
    template_name = 'assessment/assessment_form.html'

    def get(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        form = AssessmentForm(instance=assessment)
        return render(request, self.template_name, {'form': form, 'is_update': True})

    def post(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        form = AssessmentForm(request.POST, instance=assessment)
        if form.is_valid():
            form.save()
            return redirect('assessment_list')
        return render(request, self.template_name, {'form': form, 'is_update': True})

class AssessmentDeleteView(View):
    template_name = 'assessment/assessment_confirm_delete.html'

    def get(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        return render(request, self.template_name, {'assessment': assessment})

    def post(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        assessment.delete()
        return redirect('assessment_list')

class AssessmentListView(View):
    template_name = 'assessment/assessment_list.html'

    def get(self, request, *args, **kwargs):
        assessments = Assessment.objects.all()
        return render(request, self.template_name, {'assessments': assessments})

    def post(self, request, *args, **kwargs):
        form = AssessmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('assessment_list')
        assessments = Assessment.objects.all()
        return render(request, self.template_name, {'assessments': assessments, 'form': form})

class AssessmentDetailView(View):
    template_name = 'assessment/assessment_detail.html'

    def get(self, request, pk, *args, **kwargs):
        assessment = get_object_or_404(Assessment, pk=pk)
        return render(request, self.template_name, {'assessment': assessment})

