# lsalms/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView, TemplateView, CreateView, UpdateView, ListView
from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt 
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.template.loader import render_to_string
from django.db import models, transaction
from django.db.models import Max, Prefetch, Sum, Subquery, OuterRef, Count, Avg, Q
from django.core.paginator import Paginator
from .models import Course, Lesson, Module, ContentBlock, CourseEnrollment, LessonProgress, StudentActivityLog
from .models import GradedActivity, SpacedRepetitionItem, AIInteractionLog
from .forms import CourseForm, ModuleForm, LessonForm, ContentBlockForm
from core.models import Subject, Student, Teacher
from .services import update_course_grade_for_student
import google.generativeai as genai
from datetime import timedelta
from django.utils import timezone


# === Permission Mixins (CBV) & Decorators (FBV) for Harmony ===

def teacher_required(view_func):
    """ Decorator for FBVs that checks if the user is a teacher. """
    return user_passes_test(lambda u: hasattr(u, 'teacher'))(view_func)


# === Teacher "Creator Hub" Views ===

class OwnerRequiredMixin(UserPassesTestMixin):
    """ A generic mixin to check ownership for Modules, Lessons, and ContentBlocks. """
    def test_func(self):
        obj = self.get_object()
        if isinstance(obj, (Module, Lesson)):
            teacher = obj.module.course.teacher if isinstance(obj, Lesson) else obj.course.teacher
        elif isinstance(obj, ContentBlock):
            teacher = obj.lesson.module.course.teacher
        else:
            return False
        return teacher == self.request.user
    

class CourseCreateView(LoginRequiredMixin, CreateView):
    model = Course
    form_class = CourseForm
    template_name = 'teacher/course_form.html'

    def get_success_url(self):
        # Redirect to the new course's management page
        return reverse('lsalms:course_manage', kwargs={'slug': self.object.slug})

    def form_valid(self, form):
        form.instance.teacher = self.request.user
        messages.success(self.request, "Course created successfully. You can now build its curriculum.")
        return super().form_valid(form)


class CourseUpdateView(LoginRequiredMixin, UpdateView): 
    model = Course
    form_class = CourseForm
    template_name = 'teacher/course_form.html' 
    
    def get_context_data(self, **kwargs):
        
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        
        all_activities = course.graded_activities.all().select_related('content_type')
        assignments = [act for act in all_activities if act.content_type.model == 'assignment']
        assessments = [act for act in all_activities if act.content_type.model == 'assessment']
        exams = [act for act in all_activities if act.content_type.model == 'exam']
        context['grading_scheme'] = {
            'assignments': {'activities': assignments, 'subtotal': sum(a.weight for a in assignments)},
            'assessments': {'activities': assessments, 'subtotal': sum(a.weight for a in assessments)},
            'exams': {'activities': exams, 'subtotal': sum(a.weight for a in exams)},
        }
        context['total_weight'] = sum(act.weight for act in all_activities)
        return context
    
    def form_valid(self, form):

        self.object = form.save(commit=False)
        self.object.save()
        messages.success(self.request, "Course details updated successfully.")
        return redirect(self.get_success_url())
    
    def get_success_url(self):
        return reverse('lsalms:course_edit', kwargs={'slug': self.object.slug})
    

class CourseManageView(LoginRequiredMixin, DetailView):
    """
    Handles both the initial page load (GET) and all AJAX actions (POST)
    for the course builder.
    """
    def dispatch(self, request, *args, **kwargs):
        """ Get the course object once for all methods. """
        self.course = get_object_or_404(
            Course.objects.prefetch_related('modules__lessons__content_blocks'),
            slug=self.kwargs.get('slug')
        )
        # --- Authorization Check ---
        if not (request.user.is_superuser or self.course.teacher == request.user):
            messages.error(request, "You are not authorized to manage this course.")
            return redirect('lsalms:academy_hub')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        """ Handles the initial page load. """
        course = get_object_or_404(
            Course.objects.prefetch_related('modules__lessons__content_blocks'),
            slug=self.kwargs.get('slug')
        )
      
        graded_activities = course.graded_activities.all().select_related('content_type')
        total_weight = graded_activities.aggregate(total=Sum('weight'))['total'] or 0

        enrollments = CourseEnrollment.objects.filter(
            course=course
        ).select_related('student__user', 'grade_report')

        total_lessons_in_course = Lesson.objects.filter(module__course=course).count()

        # 3. Only proceed if there are actual enrollments.
        if enrollments.exists():
            # Trigger grade calculations for all enrolled students.
            for enrollment in enrollments:
                update_course_grade_for_student(course=course, student=enrollment.student)

            # Re-fetch the enrollments to get the updated grade_report data.
            enrollments_with_grades = CourseEnrollment.objects.filter(
                course=course
            ).select_related('student__user', 'grade_report')

            # Efficiently count completed lessons for these specific enrollments.
            completed_lessons_subquery = LessonProgress.objects.filter(
                enrollment=OuterRef('pk')
            ).values('enrollment').annotate(c=Count('id')).values('c')
            
            enrollments_with_progress = enrollments_with_grades.annotate(
                completed_lessons_count=Subquery(completed_lessons_subquery, output_field=models.IntegerField())
            )

            # Attach the final percentage.
            for enrollment in enrollments_with_progress:
                completed_count = enrollment.completed_lessons_count or 0
                if total_lessons_in_course > 0:
                    enrollment.progress_percentage = int((completed_count / total_lessons_in_course) * 100)
                else:
                    enrollment.progress_percentage = 0
        
        context = {
            'course': course,
            'graded_activities': graded_activities,
            'total_weight': total_weight,
            'student_progress_data': enrollments_with_progress,
            'AI_IS_CONFIGURED': bool(settings.GEMINI_API_KEY),
        }
        return render(request, 'teacher/course_manage.html', context)

    def post(self, request, *args, **kwargs):
        """
        Acts as a router for all AJAX POST requests. The 'action' parameter
        determines which private method to call.
        """
        action = request.POST.get('action')
        handler = getattr(self, f'_handle_{action}', self._handle_invalid_action)
        return handler(request)

    # --- ACTION HANDLERS ---
    def _handle_invalid_action(self, request):
        return JsonResponse({'status': 'error', 'message': 'Invalid action specified.'}, status=400)

    def _render_form(self, request, form, url, modal_title):
        """ Helper to render a form inside a modal structure. """
        context = {'form': form, 'form_action_url': url, 'modal_title': modal_title}
        return render(request, 'lsalms/partials/generic_form_modal.html', context)

    def _handle_get_form(self, request):
        """ Generic handler for fetching create/edit form HTML. """
        form_type = request.GET.get('form_type')
        pk = request.GET.get('pk')
        
        if form_type == 'module':
            instance = get_object_or_404(Module, pk=pk, course=self.course) if pk else None
            form = ModuleForm(instance=instance)
            url = reverse('lsalms:course_manage', kwargs={'slug': self.course.slug})
            modal_title = 'Edit Module' if instance else 'Create New Module'
            
        elif form_type == 'lesson':
            instance = get_object_or_404(Lesson, pk=pk, module__course=self.course) if pk else None
            form = LessonForm(instance=instance)
            url = reverse('lsalms:course_manage', kwargs={'slug': self.course.slug})
            modal_title = 'Edit Lesson' if instance else 'Create New Lesson'
            
        elif form_type == 'content_block':
            instance = get_object_or_404(ContentBlock, pk=pk, lesson__module__course=self.course) if pk else None
            form = ContentBlockForm(instance=instance)
            url = reverse('lsalms:course_manage', kwargs={'slug': self.course.slug})
            modal_title = 'Edit Content' if instance else 'Add New Content'
        
        else:
            return HttpResponseBadRequest("Invalid form type.")
            
        return self._render_form(request, form, url, modal_title)
        
    def _handle_save_form(self, request):
        """ Generic handler for saving create/edit forms. """
        form_type = request.POST.get('form_type')
        pk = request.POST.get('pk')

        if form_type == 'module':
            instance = get_object_or_404(Module, pk=pk, course=self.course) if pk else None
            form = ModuleForm(request.POST, instance=instance)
            if form.is_valid():
                obj = form.save(commit=False)
                if not instance: obj.course = self.course
                obj.save()
                html = render_to_string('lsalms/partials/_module_item.html', {'module': obj})
                return JsonResponse({'status': 'success', 'html': html, 'is_new': not instance})
            
        if form_type == 'lesson':
            instance = get_object_or_404(Lesson, pk=pk, course=self.course) if pk else None
            form = LessonForm(request.POST, instance=instance)
            if form.is_valid():
                obj = form.save(commit=False)
                if not instance: obj.module = self.module
                obj.save()
                html = render_to_string('lsalms/partials/_lesson_item.html', {'module': obj})
                return JsonResponse({'status': 'successmod', 'html': html, 'is_new': not instance})
            
        if form_type == 'content_block':
            instance = get_object_or_404(ContentBlock, pk=pk, course=self.course) if pk else None
            form = ContentBlockForm(request.POST, instance=instance)
            if form.is_valid():
                obj = form.save(commit=False)
                if not instance: obj.lesson = self.lesson
                obj.save()
                html = render_to_string('lsalms/partials/_content_block_item.html', {'module': obj})
                return JsonResponse({'status': 'success', 'html': html, 'is_new': not instance})
              
        return JsonResponse({'status': 'error', 'errors': form.errors})

    def _handle_delete_item(self, request):
        """ Generic handler for deleting items. """
        item_type = request.POST.get('item_type')
        pk = request.POST.get('pk')

        if item_type == 'module':
            Module.objects.filter(pk=pk, course=self.course).delete()
        elif item_type == 'lesson':
            Lesson.objects.filter(pk=pk, module__course=self.course).delete()
        elif item_type == 'content_block':
            ContentBlock.objects.filter(pk=pk, lesson__module__course=self.course).delete()
        else:
            return HttpResponseBadRequest("Invalid item type.")

        return JsonResponse({'status': 'success'})
    

class ModuleCreateView(LoginRequiredMixin, CreateView):
    model = Module
    form_class = ModuleForm
    template_name = 'teacher/partials/generic_form_modal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action_url'] = reverse('lsalms:module_create', kwargs={'course_id': self.kwargs['course_id']})
        return context

    def form_valid(self, form):
        course = get_object_or_404(Course, pk=self.kwargs['course_id'], teacher=self.request.user)
        form.instance.course = course
        last_module_order = Module.objects.filter(course=course).aggregate(max_order=Max('order'))['max_order']
        form.instance.order = 1 if last_module_order is None else last_module_order + 1
        messages.success(self.request, "Module created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('lsalms:course_manage', kwargs={'slug': self.object.course.slug})


class LessonCreateView(LoginRequiredMixin, CreateView):
    model = Lesson
    form_class = LessonForm
    # CORRECTED PATH
    template_name = 'teacher/partials/generic_form_modal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action_url'] = reverse('lsalms:lesson_create', kwargs={'module_id': self.kwargs['module_id']})
        return context

    def form_valid(self, form):
        module = get_object_or_404(Module, pk=self.kwargs['module_id'], course__teacher=self.request.user)
        form.instance.module = module
        last_lesson_order = Lesson.objects.filter(module=module).aggregate(max_order=Max('order'))['max_order']
        form.instance.order = 1 if last_lesson_order is None else last_lesson_order + 1
        messages.success(self.request, "Lesson created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('lsalms:course_manage', kwargs={'slug': self.object.module.course.slug})


class ContentBlockCreateView(LoginRequiredMixin, CreateView):
    model = ContentBlock
    form_class = ContentBlockForm
    # CORRECTED PATH
    template_name = 'teacher/partials/generic_form_modal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action_url'] = reverse('lsalms:content_block_create', kwargs={'lesson_id': self.kwargs['lesson_id']})
        return context

    def form_valid(self, form):
        lesson = get_object_or_404(Lesson, pk=self.kwargs['lesson_id'], module__course__teacher=self.request.user)
        form.instance.lesson = lesson
        last_content_order = ContentBlock.objects.filter(lesson=lesson).aggregate(max_order=Max('order'))['max_order']
        form.instance.order = 1 if last_content_order is None else last_content_order + 1
        messages.success(self.request, "Content Block created successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('lsalms:course_manage', kwargs={'slug': self.object.lesson.module.course.slug})


class ModuleUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Module
    form_class = ModuleForm
    # CORRECTED PATH
    template_name = 'teacher/partials/generic_form_modal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action_url'] = reverse('lsalms:module_edit', kwargs={'pk': self.object.pk})
        return context

    def get_success_url(self):
        return reverse('lsalms:course_manage', kwargs={'slug': self.object.course.slug})


class LessonUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Lesson
    form_class = LessonForm
    # CORRECTED PATH
    template_name = 'teacher/partials/generic_form_modal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action_url'] = reverse('lsalms:lesson_edit', kwargs={'pk': self.object.pk})
        return context

    def get_success_url(self):
        return reverse('lsalms:course_manage', kwargs={'slug': self.object.module.course.slug})


class ContentBlockUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = ContentBlock
    form_class = ContentBlockForm
    template_name = 'teacher/partials/generic_form_modal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action_url'] = reverse('lsalms:content_block_edit', kwargs={'pk': self.object.pk})
        return context
    
    def get_success_url(self):
        return reverse('lsalms:course_manage', kwargs={'slug': self.object.lesson.module.course.slug})


# === "Creator Hub" FBVs for DELETING ===

@login_required
def course_builder_view(request, course_slug):
    # Fetch the course and prefetch all related items in an efficient way
    course = get_object_or_404(Course.objects.prefetch_related('modules__lessons__content_blocks'), slug=course_slug)

    # Authorization Check: Ensure the user is the teacher of the course or a superuser
    if not (request.user.is_superuser or course.teacher == request.user):
        messages.error(request, "You are not authorized to edit this course.")
        return redirect('lsalms:academy_hub')

    context = {
        'course': course,
    }
    return render(request, 'lsalms/builder/course_builder.html', context)


@require_POST
def update_module_order(request, course_id):
    """
    Receives a list of module IDs in their new order and updates them.
    """
    module_ids = request.POST.getlist('module_order[]')
    try:
        with transaction.atomic(): # Ensures all updates succeed or none do
            for index, module_id in enumerate(module_ids):
                Module.objects.filter(id=module_id, course_id=course_id).update(order=index)
        return JsonResponse({'status': 'success', 'message': 'Module order updated.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_POST
def update_lesson_order(request, module_id):
    """
    Receives a list of lesson IDs in their new order and updates them.
    """
    lesson_ids = request.POST.getlist('lesson_order[]')
    try:
        with transaction.atomic():
            for index, lesson_id in enumerate(lesson_ids):
                Lesson.objects.filter(id=lesson_id, module_id=module_id).update(order=index)
        return JsonResponse({'status': 'success', 'message': 'Lesson order updated.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_POST
def update_content_block_order(request, lesson_id):
    """
    Receives a list of content block IDs in their new order and updates them.
    """
    block_ids = request.POST.getlist('block_order[]')
    try:
        with transaction.atomic():
            for index, block_id in enumerate(block_ids):
                ContentBlock.objects.filter(id=block_id, lesson_id=lesson_id).update(order=index)
        return JsonResponse({'status': 'success', 'message': 'Content order updated.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST 
@user_passes_test(lambda u: u.is_superuser) 
def course_delete(request, pk):
    try:
        course_to_delete = get_object_or_404(Course, pk=pk)
        course_title = course_to_delete.get_course_title() # Get title before deleting
        course_to_delete.delete()
        messages.success(request, f"The course '{course_title}' has been successfully deleted.")
    except Exception as e:
        messages.error(request, f"An error occurred while trying to delete the course: {e}")
    
    # Redirect back to the main LMS admin dashboard
    return redirect('lsalms:admin_dashboard')


@login_required
@require_POST
def module_delete(request, pk):
    module = get_object_or_404(Module, pk=pk, course__teacher=request.user)
    course_slug = module.course.slug
    module.delete()
    messages.success(request, f"Module '{module.title}' has been deleted.")
    return redirect('lsalms:course_manage', slug=course_slug)


@login_required
@require_POST
def lesson_delete(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk, module__course__teacher=request.user)
    course_slug = lesson.module.course.slug
    lesson.delete()
    messages.success(request, f"Lesson '{lesson.title}' has been deleted.")
    return redirect('lsalms:course_manage', slug=course_slug)


@login_required
@require_POST
def content_block_delete(request, pk):
    content = get_object_or_404(ContentBlock, pk=pk, lesson__module__course__teacher=request.user)
    course_slug = content.lesson.module.course.slug
    content.delete()
    messages.success(request, f"Content Block '{content.title}' has been deleted.")
    return redirect('lsalms:course_manage', slug=course_slug)

# === Student & Guardian Views ===

class CourseDetailView(LoginRequiredMixin, DetailView): # Add Enrollment Mixins
    model = Course
    template_name = 'course_detail.html'
    context_object_name = 'course'
    
    def get_queryset(self):
        return Course.objects.prefetch_related(
            Prefetch('modules', queryset=Module.objects.order_by('order').prefetch_related(
                Prefetch('lessons', queryset=Lesson.objects.order_by('order').prefetch_related(
                    Prefetch('content_blocks', queryset=ContentBlock.objects.order_by('order'))
                ))
            ))
        ).filter(slug=self.kwargs['slug']) 
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student
        course = self.get_object()

        try:
            enrollment = CourseEnrollment.objects.get(student=student, course=course)
            progress_percent = enrollment.calculate_progress_percentage()
        except CourseEnrollment.DoesNotExist:
            enrollment = None
            progress_percent = 0
        
        context['enrollment'] = enrollment
        context['progress_percent'] = progress_percent

        next_lesson = course.get_next_uncompleted_lesson(student)
        context['next_lesson'] = next_lesson
        context['next_lesson_id'] = {next_lesson.id} if next_lesson else set() 
        context['completed_lesson_ids'] = set(LessonProgress.objects.filter(
            enrollment__student=student, lesson__module__course=course
        ).values_list('lesson_id', flat=True))
            
        return context
    

class LessonDetailView(LoginRequiredMixin, DetailView):
    model = Lesson
    template_name = 'lesson_detail.html'
    context_object_name = 'lesson'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student
        lesson = self.get_object()
        course = lesson.module.course
        context['course'] = course

        # Efficiently fetch the entire course structure for the sidebar
        context['course_modules'] = Module.objects.filter(course=course).prefetch_related('lessons')

        # Get a set of completed lesson IDs for easy lookup in the template
        context['completed_lesson_ids'] = set(LessonProgress.objects.filter(
            enrollment__student=student,
            lesson__module__course=course
        ).values_list('lesson_id', flat=True))

        # Check completion status for the current lesson
        context['is_completed'] = lesson.id in context['completed_lesson_ids']

        # Calculate course progress
        try:
            enrollment = CourseEnrollment.objects.get(student=student, course=course)
            context['progress_percent'] = enrollment.calculate_progress_percentage()
        except CourseEnrollment.DoesNotExist:
            context['progress_percent'] = 0

        return context


@login_required
@require_POST
def update_weights_view(request, course_id):
    course = get_object_or_404(Course, pk=course_id, teacher=request.user)
    for key, value in request.POST.items():
        if key.startswith('weight-'):
            try:
                activity_id = int(key.split('-')[1])
                weight = int(value)
                GradedActivity.objects.filter(pk=activity_id, course=course).update(weight=weight)
            except (ValueError, IndexError):
                # Ignore invalid form data
                continue
    messages.success(request, "Grading weights have been updated successfully.")
    return redirect('lsalms:course_manage', slug=course.slug)

@login_required
def get_subjects_for_class_api(request):

    class_id = request.GET.get('class_id')
    if not class_id:
        return JsonResponse({'error': 'Class ID is required.'}, status=400)

    try:
        subjects = Subject.objects.filter(
            class_assignments__class_assigned_id=class_id
        ).distinct().order_by('name')
        
        # We format the data in a simple list of objects for the JavaScript
        data = [{'id': subject.id, 'name': subject.name} for subject in subjects]
        
        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
@require_POST
def mark_lesson_complete(request, pk):
    try:
        lesson = get_object_or_404(Lesson, pk=pk)
        student = request.user.student
        enrollment = get_object_or_404(CourseEnrollment, student=student, course=lesson.module.course)

        progress, created = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)

        # We only want to run the "first-time completion" logic if the progress record was just created.
        if created:
            # When creating a new item, we MUST provide a next_review_date.
            SpacedRepetitionItem.objects.update_or_create(
                student=student,
                lesson=lesson,
                defaults={
                    'current_interval': 1, # Start with a 1-day interval
                    'next_review_date': timezone.now().date() + timedelta(days=1)
                }
            )
            # Prepare the response to render the "Completed!" state
            context = {'is_completed': True, 'lesson': lesson}
            response = render(request, 'partials/completion_section_v2.html', context)

            # Trigger the modal and confetti
            triggers = {"showCompletionModal": True}
            response['HX-Trigger'] = json.dumps(triggers)
            return response
        else:
            # If they are clicking it again (already complete), just show the completed state quietly.
            context = {'is_completed': True, 'lesson': lesson}
            return render(request, 'partials/completion_section_v2.html', context)

    except Exception as e:
        # Return a user-friendly error message that HTMX can display
        return HttpResponse(f"<div class='alert alert-danger'>An unexpected error occurred: {e}</div>")
    

# === Admin Dashboard View ===
class LMSAdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'admin/dashboard.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # --- 1. Top-Level Stats ---
        course_stats = Course.objects.aggregate(
            total_courses=Count('id'),
            published_courses=Count('id', filter=Q(status=Course.Status.PUBLISHED)),
            draft_courses=Count('id', filter=Q(status=Course.Status.DRAFT))
        )
        context.update(course_stats)
        
        # Fetch all enrollments and then filter in Python to get the active count.
        all_enrollments = CourseEnrollment.objects.all()
        active_enrollment_count = sum(1 for enrollment in all_enrollments if enrollment.is_active)
        context['total_enrollments'] = active_enrollment_count
        
        context['online_academy_students'] = Student.objects.filter(
            lsalms_enrollments__course__course_type=Course.CourseType.EXTERNAL
        ).distinct().count()

        # --- 2. Full Course Management List (with Search & Pagination) ---
        course_list = Course.objects.all().select_related('teacher').order_by('-updated_at')
        
        query = self.request.GET.get('q')
        if query:
            course_list = course_list.filter(
                Q(title__icontains=query) | 
                Q(subject__name__icontains=query) | 
                Q(teacher__user__first_name__icontains=query) | 
                Q(teacher__user__last_name__icontains=query)
            )
        
        paginator = Paginator(course_list, 10)
        page_number = self.request.GET.get('page')
        context['all_courses'] = paginator.get_page(page_number)

        # --- 3. Student Performance Leaderboard (with Final Grades) ---
        top_students_qs = Student.objects.annotate(
            average_lms_grade=Avg('lsalms_enrollments__grade_report__final_score')
        ).filter(average_lms_grade__isnull=False).order_by('-average_lms_grade')
        
        context['top_students'] = top_students_qs[:5]

        context['at_risk_students'] = Student.objects.filter(
            lsalms_enrollments__isnull=False, 
            lsalms_enrollments__lesson_progress__isnull=True
        ).distinct()[:5]

        # --- 4. Recent Activity Feed ---
        context['recent_activities'] = StudentActivityLog.objects.all().select_related(
            'student__user', 'content_type'
        ).order_by('-timestamp')[:10]

        return context


@login_required
@require_POST 
def course_publish(request, pk):

    course = get_object_or_404(Course, pk=pk, teacher=request.user)
    
    if not course.modules.exists() or not Lesson.objects.filter(module__course=course).exists():
        messages.error(request, "Cannot publish a course with no modules or lessons.")
        return redirect('lsalms:course_manage', slug=course.slug)

    course.status = Course.Status.PUBLISHED
    course.save()
    
    messages.success(request, f"Congratulations! Your course '{course.title}' is now published and visible to enrolled students.")
    return redirect('lsalms:course_manage', slug=course.slug)


@login_required
@require_POST
def update_module_order(request):
    module_ids = request.POST.getlist('module_order[]')
    for index, module_id in enumerate(module_ids):
        Module.objects.filter(id=module_id, course__teacher=request.user).update(order=index)
    return HttpResponse(status=200) # Just return a success status

# === AI Integration View ===

@login_required
@require_POST 
def ai_content_generator_view(request):
    """
    Handles AI content generation requests from the frontend.
    It's designed to be a secure, auditable gateway to the Gemini API.
    """
    # Security Check 1: Is the AI service configured on the server?
    if not settings.GEMINI_API_KEY:
        return JsonResponse({'error': 'AI service is not configured.'}, status=503) # 503 Service Unavailable

    # Security Check 2: Is the user a teacher? (Adapt if other roles can use it)
    if not hasattr(request.user, 'teacher'):
        return JsonResponse({'error': 'You do not have permission to use this feature.'}, status=403) # 403 Forbidden

    try:
        # 1. Extract and validate data from the frontend request
        prompt_text = request.POST.get('prompt', '')
        context_text = request.POST.get('context', '') # e.g., "The title of this content block is: 'Evaporation Explained'"

        if not prompt_text:
            return JsonResponse({'error': 'A prompt is required.'}, status=400) # 400 Bad Request

        # 2. Prompt Engineering: Combine the raw inputs into a better, more robust prompt for the AI
        full_prompt = (
            "You are an expert, helpful teacher's assistant creating educational content. "
            "Your tone should be clear, informative, and engaging for students. "
            "Based on the following context, please perform the requested task.\n\n"
            f"CONTEXT: {context_text}\n\n"
            f"TASK: {prompt_text}"
        )

        # 3. Configure and call the Gemini API
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(full_prompt)

        # 4. Log the interaction for auditing and cost tracking
        # This is a critical step for any production application.
        AIInteractionLog.objects.create(
            user=request.user,
            task_type=AIInteractionLog.AITask.CONTENT_DRAFTING,
            # In a more advanced setup, you can get token counts from the API response
            # to track costs precisely.
        )

        # 5. Send the successful result back to the frontend
        return JsonResponse({'generated_text': response.text})

    except Exception as e:
        # Catch any potential errors (API downtime, invalid key, etc.)
        # In production, you would log this error to a service like Sentry or Logtail.
        print(f"ERROR [AI View]: {e}")
        return JsonResponse({'error': 'An unexpected error occurred with the AI service. Please try again later.'}, status=500)
    

class OnlineAcademyHubView(ListView):
    """
    Displays all available, published Online Academy courses for browsing.
    This is the main storefront.
    """
    model = Course
    template_name = 'academy/hub.html'
    context_object_name = 'courses'
    paginate_by = 9 

    def get_queryset(self):
        # The queryset is simple: find all published, external courses.
        return Course.objects.filter(
            status=Course.Status.PUBLISHED
        ).order_by('-created_at') 


class AcademyCourseDetailView(DetailView):
    """
    The "Sales Page" for a single online course. It shows the full curriculum
    and a clear call-to-action to subscribe.
    """
    model = Course
    template_name = 'academy/course_detail.html'
    context_object_name = 'course'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Check if the current user is already enrolled to show a different message
        if self.request.user.is_authenticated and hasattr(self.request.user, 'student'):
            context['is_enrolled'] = CourseEnrollment.objects.filter(
                student=self.request.user.student,
                course=self.get_object()
            ).exists()
        else:
            context['is_enrolled'] = False
        return context
    

class CourseSubscriptionConfirmView(LoginRequiredMixin, DetailView):
    """
    This view displays the subscription confirmation page, acting as a
    'checkout' placeholder before the final enrollment action.
    """
    model = Course
    template_name = 'academy/subscription_confirm.html'
    context_object_name = 'course'
    slug_url_kwarg = 'slug'
    slug_field = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add the student to the context for a personalized message
        context['student'] = self.request.user.student
        return context
    

@login_required
@require_POST # Security: This action can ONLY be triggered by a form submission.
def subscribe_to_course_view(request, course_id):
    """
    This view handles the final enrollment action after confirmation.
    In a real app, this would be where payment gateway logic is integrated.
    For the MVP, it simulates a successful payment and creates the enrollment.
    """
    course = get_object_or_404(Course, pk=course_id, course_type=Course.CourseType.EXTERNAL)
    
    # Ensure the logged-in user has a student profile
    if not hasattr(request.user, 'student'):
        messages.error(request, "A valid student profile is required to enroll in courses.")
        return redirect('lsalms:academy_hub') # Redirect back to the catalog

    student = request.user.student
    
    # --- PAYMENT GATEWAY INTEGRATION WOULD GO HERE ---
    # 1. Initiate payment with Paystack/Stripe for course.subscription_fee.
    # 2. On successful payment callback from the gateway, execute the logic below.
    # ---
    
    # --- MVP SIMULATION: Assume payment was successful ---
    
    # Calculate subscription end date (e.g., 365 days of access)
    subscription_duration = timedelta(days=365)
    end_date = timezone.now().date() + subscription_duration
    
    # Create or update the enrollment record. update_or_create is safe from creating duplicates.
    enrollment, created = CourseEnrollment.objects.update_or_create(
        student=student,
        course=course,
        defaults={'subscription_end_date': end_date}
    )
    
    if created:
        messages.success(request, f"Congratulations! You have successfully enrolled in '{course.title}'.")
    else:
        messages.info(request, f"Your subscription for '{course.title}' has been renewed or updated.")
        
    return redirect('student_dashboard')