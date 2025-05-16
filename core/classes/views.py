# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import ListView
from django.views.generic import DetailView, FormView
from django.db.models import Count, Prefetch, OuterRef, Subquery, Q
from .forms import ClassForm
from core.enrollment.forms import EnrollmentForm
from core.models import Class, Enrollment, TeacherAssignment

class ClassListView(ListView): # Inherit from ListView
    model = Class
    template_name = 'class/class_list.html'
    context_object_name = 'classes' 
    paginate_by = 15

    def get_queryset(self):
        queryset = Class.objects.annotate(
            # --- Use the correct related_name from Student.current_class ---
            student_count=Count('enrolled_students', distinct=True),
            subject_count=Count('subjects', distinct=True),
        ).prefetch_related(
             Prefetch(
                'teacherassignment_set',
                queryset=TeacherAssignment.objects.select_related('teacher__user').filter(is_form_teacher=True),
                to_attr='form_teacher_assignments'
            )
        ).order_by('order', 'name')


        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Process the prefetched data to easily access the form teacher in the template
        for class_instance in context['classes']:
            form_assignment = class_instance.form_teacher_assignments[0] if class_instance.form_teacher_assignments else None
            class_instance.form_teacher_obj = form_assignment.teacher if form_assignment else None

        return context
    
class ClassCreateView(View):
    template_name = 'class/class_form.html'

    def get(self, request, *args, **kwargs):
        form = ClassForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = ClassForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                return redirect('class_list')
            except Exception as e:
                print(f"Error during save: {e}")  # Debug database errors
        else:
            print(f"Form errors: {form.errors}")  # Debug validation errors
        return render(request, self.template_name, {'form': form})

class ClassUpdateView(View):
    template_name = 'class/class_form.html'

    def get(self, request, pk, *args, **kwargs):
        class_instance = get_object_or_404(Class, pk=pk)
        form = ClassForm(instance=class_instance)
        return render(request, self.template_name, {'form': form, 'is_update': True, 'class_instance': class_instance})

    def post(self, request, pk, *args, **kwargs):
        class_instance = get_object_or_404(Class, pk=pk)
        form = ClassForm(request.POST, instance=class_instance)
        if form.is_valid():
            form.save()
            return redirect('class_list')
        return render(request, self.template_name, {'form': form, 'is_update': True, 'class_instance': class_instance})


class ClassDetailView(DetailView):
    model = Class
    template_name = 'class/class_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        class_instance = self.get_object()
        context['class_instance'] = class_instance
        context['enrollment_form'] = EnrollmentForm(class_instance=class_instance)
        subject_assignments = class_instance.subject_assignments.select_related(
            'subject', 'session', 'term'
        ).all()      
        context['optimized_subject_assignments'] = subject_assignments
        return context


class EnrollStudentView(FormView):
    form_class = EnrollmentForm
    template_name = 'setup/enrol_student.html'

    def form_valid(self, form):
        student = form.cleaned_data['student']
        class_instance = form.cleaned_data['class_enrolled']
        session = form.cleaned_data['session']
        term = form.cleaned_data['term']

        # Create a new enrollment record
        Enrollment.objects.create(
            student=student,
            class_enrolled=class_instance,
            session=session,
            term=term
        )
        
        # Redirect to the class list or any other relevant view after successful enrollment
        return redirect(self.get_success_url())

    def get_success_url(self):
        # Get the class ID from the URL parameters
        class_id = self.kwargs['pk']  # Assuming you are passing class ID as a URL parameter
        # Return to a page that makes sense for your flow, e.g., class detail or list
        return reverse('class_detail', kwargs={'pk': class_id})
    

class ClassDeleteView(View):
    template_name = 'class/class_confirm_delete.html'

    def get(self, request, pk, *args, **kwargs):
        class_instance = get_object_or_404(Class, pk=pk)
        return render(request, self.template_name, {'class_instance': class_instance})

    def post(self, request, pk, *args, **kwargs):
        class_instance = get_object_or_404(Class, pk=pk)
        class_instance.delete()
        return redirect('class_list')
