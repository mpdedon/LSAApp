from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Q
from django.core.paginator import Paginator
from .forms import SubjectAssignmentForm
from ..models import SubjectAssignment



class SubjectAssignmentListView(View):
    template_name = 'subject_assignment/subject_assignment_list.html'

    def get(self, request, *args, **kwargs):
        # Log all incoming GET parameters
        print(f"GET parameters: {request.GET}")  # Debugging line
        print('Name')
        search_query = request.GET.get('q', '').strip()
        print(f"Search Query: {search_query}")  # Debugging line

        subject_assignments = SubjectAssignment.objects.all()

        if search_query:
            subject_assignments = subject_assignments.filter(
                Q(teacher__user__first_name__icontains=search_query) |
                Q(teacher__user__last_name__icontains=search_query) |
                Q(subject__name__icontains=search_query) |
                Q(class_assigned__name__icontains=search_query)
            )
            print(f"Filtered Results: {subject_assignments}")  # Debugging line

        paginator = Paginator(subject_assignments, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'search_query': search_query,
        })
    
class SubjectAssignmentListView(View):
    template_name = 'subject_assignment/subject_assignment_list.html'

    def get(self, request):
        # Fetch all subject assignments and order by id (most recent)
        subject_assignments = SubjectAssignment.objects.all().order_by('-id')  # Adjusted to order by ID

        # Set up pagination
        paginator = Paginator(subject_assignments, 15)  # 20 assignments per page
        page_number = request.GET.get('page')  # Get the page number from the request
        page_obj = paginator.get_page(page_number)  # Get the page object
        
        return render(request, self.template_name, {'page_obj': page_obj})

class SubjectAssignmentDetailView(View):
    template_name = 'subject_assignment/subject_assignment_detail.html'

    def get(self, request, pk):
        subject_assignment = get_object_or_404(SubjectAssignment, pk=pk)
        return render(request, self.template_name, {'subject_assignment': subject_assignment})

class SubjectAssignmentCreateView(View):
    template_name = 'subject_assignment/subject_assignment_form.html'

    def get(self, request):
        form = SubjectAssignmentForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = SubjectAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('subject_assignment_list')
        return render(request, self.template_name, {'form': form})

class SubjectAssignmentUpdateView(View):
    template_name = 'subject_assignment/subject_assignment_form.html'

    def get(self, request, pk):
        subject_assignment = get_object_or_404(SubjectAssignment, pk=pk)
        form = SubjectAssignmentForm(instance=subject_assignment)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        subject_assignment = get_object_or_404(SubjectAssignment, pk=pk)
        form = SubjectAssignmentForm(request.POST, instance=subject_assignment)
        if form.is_valid():
            form.save()
            return redirect('subject_assignment_list')
        return render(request, self.template_name, {'form': form})

class SubjectAssignmentDeleteView(View):
    template_name = 'subject_assignment/subject_assignment_confirm_delete.html'

    def get(self, request, pk):
        subject_assignment = get_object_or_404(SubjectAssignment, pk=pk)
        return render(request, self.template_name, {'subject_assignment': subject_assignment})

    def post(self, request, pk):
        subject_assignment = get_object_or_404(SubjectAssignment, pk=pk)
        subject_assignment.delete()
        return redirect('subject_assignment_list')

