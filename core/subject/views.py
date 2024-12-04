from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import SubjectForm
from ..models import Subject

class SubjectListView(View):
    template_name = 'subject/subject_list.html'

    def get(self, request):
        subjects = Subject.objects.all()
        return render(request, self.template_name, {'subjects': subjects})

class SubjectDetailView(View):
    template_name = 'subject/subject_detail.html'

    def get(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        return render(request, self.template_name, {'subject': subject})

class SubjectCreateView(View):
    template_name = 'subject/subject_form.html'

    def get(self, request):
        form = SubjectForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('subject_list')
        return render(request, self.template_name, {'form': form})

class SubjectUpdateView(View):
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

class SubjectDeleteView(View):
    template_name = 'subject/subject_confirm_delete.html'

    def get(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        return render(request, self.template_name, {'subject': subject})

    def post(self, request, pk):
        subject = get_object_or_404(Subject, pk=pk)
        subject.delete()
        return redirect('subject_list')
