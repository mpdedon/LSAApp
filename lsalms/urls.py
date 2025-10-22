# lsalms/urls.py

from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'lsalms'

urlpatterns = [
    # === Admin "Mission Control" URL ===
    path('admin-dashboard/', views.LMSAdminDashboardView.as_view(), name='admin_lms_dashboard'),

    # === Teacher "Creator Hub" URLs ===
    path('teacher/course/create/', views.CourseCreateView.as_view(), name='course_create'),
    path('teacher/course/<slug:slug>/edit/', views.CourseUpdateView.as_view(), name='course_edit'),
    path('teacher/course/<slug:slug>/manage/', views.CourseManageView.as_view(), name='course_manage'),
    path('teacher/course/<int:pk>/publish/', views.course_publish, name='course_publish'),
    path('teacher/course/<int:course_id>/update-weights/', views.update_weights_view, name='update_weights'),
    path('builder/<slug:course_slug>/', views.course_builder_view, name='course_builder'),

    
    # URLs for adding components to the course builder (perfect for modals/HTMX)
    path('teacher/course/<int:course_id>/add-module/', views.ModuleCreateView.as_view(), name='module_create'),
    path('teacher/module/<int:module_id>/add-lesson/', views.LessonCreateView.as_view(), name='lesson_create'),
    path('teacher/module/update-order/', views.update_module_order, name='update_module_order'),
    path('teacher/lesson/<int:lesson_id>/add-content/', views.ContentBlockCreateView.as_view(), name='content_block_create'),
    path('api/reorder/modules/<int:course_id>/', views.update_module_order, name='api_update_module_order'),
    path('api/reorder/lessons/<int:module_id>/', views.update_lesson_order, name='api_update_lesson_order'),
    path('api/reorder/content-blocks/<int:lesson_id>/', views.update_content_block_order, name='api_update_content_block_order'),


    # UPDATE (Edit)
    path('teacher/module/<int:pk>/edit/', views.ModuleUpdateView.as_view(), name='module_edit'),
    path('teacher/lesson/<int:pk>/edit/', views.LessonUpdateView.as_view(), name='lesson_edit'),
    path('teacher/content/<int:pk>/edit/', views.ContentBlockUpdateView.as_view(), name='content_block_edit'),

    # DELETE
    path('admin/course/<int:pk>/delete/', views.course_delete, name='course_delete'),
    path('teacher/module/<int:pk>/delete/', views.module_delete, name='module_delete'),
    path('teacher/lesson/<int:pk>/delete/', views.lesson_delete, name='lesson_delete'),
    path('teacher/content/<int:pk>/delete/', views.content_block_delete, name='content_block_delete'),

    # === Student & Guardian Facing URLs ===
    path('course/<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail'),
    path('lesson/<int:pk>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('lesson/<int:pk>/complete/', views.mark_lesson_complete, name='mark_lesson_complete'),

    # === API URL for AI Integration ===
    path('api/ai-assist/', views.ai_content_generator_view, name='api_ai_assist'),
    path('api/get-subjects-for-class/', views.get_subjects_for_class_api, name='api_get_subjects_for_class'),

    # == Academy Hub URLs===
    path('academy/', views.OnlineAcademyHubView.as_view(), name='academy_hub'),
    path('academy/course/<slug:slug>/', views.AcademyCourseDetailView.as_view(), name='academy_course_detail'),
    path('academy/course/<int:course_id>/subscribe/', views.subscribe_to_course_view, name='subscribe_to_course'),
    path('academy/course/<slug:slug>/confirm/', views.CourseSubscriptionConfirmView.as_view(), name='course_subscription_confirm'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



