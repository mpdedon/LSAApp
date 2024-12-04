from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import FeeAssignmentForm
from ..models import FeeAssignment

class FeeAssignmentListView(View):
    template_name = 'fee_assignment/fee_assignment_list.html'

    def get(self, request):
        fee_assignments = FeeAssignment.objects.all()
        return render(request, self.template_name, {'fee_assignments': fee_assignments})

class FeeAssignmentDetailView(View):
    template_name = 'fee_assignment/fee_assignment_detail.html'

    def get(self, request, pk):
        fee_assignment = get_object_or_404(FeeAssignment, pk=pk)
        return render(request, self.template_name, {'fee_assignment': fee_assignment})

class FeeAssignmentCreateView(View):
    template_name = 'fee_assignment/fee_assignment_form.html'

    def get(self, request):
        form = FeeAssignmentForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = FeeAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('fee_assignment_list')
        return render(request, self.template_name, {'form': form})

class FeeAssignmentUpdateView(View):
    template_name = 'fee_assignment/fee_assignment_form.html'

    def get(self, request, pk):
        fee_assignment = get_object_or_404(FeeAssignment, pk=pk)
        form = FeeAssignmentForm(instance=fee_assignment)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        fee_assignment = get_object_or_404(FeeAssignment, pk=pk)
        form = FeeAssignmentForm(request.POST, instance=fee_assignment)
        if form.is_valid():
            form.save()
            return redirect('fee_assignment_list')
        return render(request, self.template_name, {'form': form})

class FeeAssignmentDeleteView(View):
    template_name = 'fee_assignment/fee_assignment_confirm_delete.html'

    def get(self, request, pk):
        fee_assignment = get_object_or_404(FeeAssignment, pk=pk)
        return render(request, self.template_name, {'fee_assignment': fee_assignment})

    def post(self, request, pk):
        fee_assignment = get_object_or_404(FeeAssignment, pk=pk)
        fee_assignment.delete()
        return redirect('fee_assignment_list')
