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
        from core.models import Session, Term
        from django.db.models import Q
        
        # Get active session and term for filtering
        active_session = Session.objects.filter(is_active=True).first()
        active_term = Term.objects.filter(session=active_session, is_active=True).first() if active_session else None
        
        # Build annotation with conditional filtering
        if active_session and active_term:
            queryset = Class.objects.annotate(
                student_count=Count('enrolled_students', distinct=True),
                # Count subjects for current session and term only
                subject_count=Count(
                    'subject_assignments',
                    filter=Q(subject_assignments__session=active_session, subject_assignments__term=active_term),
                    distinct=True
                ),
            ).order_by('order', 'name')
        else:
            queryset = Class.objects.annotate(
                student_count=Count('enrolled_students', distinct=True),
                subject_count=Count('subject_assignments', distinct=True),
            ).order_by('order', 'name')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from core.models import Session, Term
        active_session = Session.objects.filter(is_active=True).first()
        active_term = Term.objects.filter(session=active_session, is_active=True).first() if active_session else None
        
        # Process the prefetched data to easily access the form teacher in the template
        # Handle both paginated and non-paginated lists
        classes_list = context.get('classes', []) or context.get('object_list', [])
        for class_instance in classes_list:
            # Use the form_teacher method with active session/term
            if active_session and active_term:
                class_instance.form_teacher_obj = class_instance.form_teacher(session=active_session, term=active_term)
            else:
                class_instance.form_teacher_obj = None
                
            # Add session/term info for context
            class_instance.student_count_agg = class_instance.student_count
            class_instance.subject_count_agg = class_instance.subject_count
        
        context['active_session'] = active_session
        context['active_term'] = active_term

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
        
        from core.models import Session, Term
        active_session = Session.objects.filter(is_active=True).first()
        active_term = Term.objects.filter(session=active_session, is_active=True).first() if active_session else None
        
        context['class_instance'] = class_instance
        context['enrollment_form'] = EnrollmentForm(class_instance=class_instance)
        context['active_session'] = active_session
        context['active_term'] = active_term
        
        # Get form teacher for active session/term
        if active_session and active_term:
            context['form_teacher'] = class_instance.form_teacher(session=active_session, term=active_term)
            # Filter subject assignments by current session/term
            subject_assignments = class_instance.subject_assignments.filter(
                session=active_session,
                term=active_term
            ).select_related('subject', 'session', 'term').order_by('subject__name')
        else:
            context['form_teacher'] = None
            # Show all assignments if no active session/term
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
