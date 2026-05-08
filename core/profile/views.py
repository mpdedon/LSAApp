# core/profile/views.py
"""
Views for user profile and system settings management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.http import Http404
from django.urls import NoReverseMatch, reverse

from core.models import CustomUser, Student, Teacher, Guardian
from core.system_settings import SystemSettings
from .forms import (
    StudentProfileForm, TeacherProfileForm, GuardianProfileForm,
    UserProfileForm, SystemSettingsForm
)


def _safe_reverse(route_name, fallback='/'):
    try:
        return reverse(route_name)
    except NoReverseMatch:
        return fallback


@login_required
def profile_view(request):
    """
    Unified profile view for all user types.
    Displays role-specific information and allows editing.
    """
    user = request.user
    profile_instance = None
    profile_form = None
    
    # Get the appropriate profile instance and form based on user role
    if user.role == 'student':
        try:
            profile_instance = user.student
            if request.method == 'POST':
                profile_form = StudentProfileForm(
                    request.POST,
                    request.FILES,
                    instance=profile_instance
                )
            else:
                profile_form = StudentProfileForm(instance=profile_instance)
        except Student.DoesNotExist:
            messages.error(request, "Student profile not found.")
            profile_form = None
    
    elif user.role == 'teacher':
        try:
            profile_instance = user.teacher
            if request.method == 'POST':
                profile_form = TeacherProfileForm(
                    request.POST,
                    request.FILES,
                    instance=profile_instance
                )
            else:
                profile_form = TeacherProfileForm(instance=profile_instance)
        except Teacher.DoesNotExist:
            messages.error(request, "Teacher profile not found.")
            profile_form = None
    
    elif user.role == 'guardian':
        try:
            profile_instance = user.guardian
            if request.method == 'POST':
                profile_form = GuardianProfileForm(
                    request.POST,
                    request.FILES,
                    instance=profile_instance
                )
            else:
                profile_form = GuardianProfileForm(instance=profile_instance)
        except Guardian.DoesNotExist:
            messages.error(request, "Guardian profile not found.")
            profile_form = None
    
    else:
        # Admin or other roles - just basic user info
        if request.method == 'POST':
            profile_form = UserProfileForm(request.POST, instance=user)
        else:
            profile_form = UserProfileForm(instance=user)
    
    # Handle form submission
    if request.method == 'POST' and profile_form:
        if profile_form.is_valid():
            try:
                with transaction.atomic():
                    profile_form.save()
                    messages.success(request, "Profile updated successfully!")
                    return redirect('profile')
            except Exception as e:
                messages.error(request, f"Error updating profile: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    
    page_title = "My Profile"
    page_subtitle = "Manage your personal information and account settings."
    base_template = 'base.html'
    cancel_url = _safe_reverse('home')

    if user.is_superuser or user.role == 'admin':
        page_title = "Admin Profile"
        page_subtitle = "Manage your administrator account and system-facing contact details."
        base_template = 'base_admin_sidebar.html'
        cancel_url = _safe_reverse('school-setup', cancel_url)
    elif user.role == 'teacher':
        page_title = "Teacher Profile"
        page_subtitle = "Update the details students and administrators rely on across your teaching workspace."
        cancel_url = _safe_reverse('teacher_dashboard', cancel_url)
    elif user.role == 'student':
        page_title = "Student Profile"
        page_subtitle = "Keep your academic account details accurate and up to date."
        cancel_url = _safe_reverse('student_dashboard', cancel_url)
    elif user.role == 'guardian':
        page_title = "Guardian Profile"
        page_subtitle = "Manage the contact information connected to your ward accounts."
        cancel_url = _safe_reverse('guardian_dashboard', cancel_url)

    context = {
        'user': user,
        'profile': profile_instance,
        'profile_form': profile_form,
        'base_template': base_template,
        'cancel_url': cancel_url,
        'page_title': page_title,
        'page_subtitle': page_subtitle,
    }
    
    return render(request, 'profile/profile.html', context)


@login_required
def change_password_view(request):
    """
    Handle password change for users
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'profile/change_password.html', {
        'form': form
    })


def is_admin(user):
    """Check if user is admin/superuser"""
    return user.is_authenticated and (user.is_superuser or user.role == 'admin')


@login_required
@user_passes_test(is_admin)
def system_settings_view(request):
    """
    System settings configuration view (admin only)
    """
    settings = SystemSettings.get_settings()
    
    if request.method == 'POST':
        form = SystemSettingsForm(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_settings = form.save(commit=False)
                    updated_settings.last_modified_by = request.user
                    updated_settings.save()
                    messages.success(request, "System settings updated successfully!")
                    return redirect('system_settings')
            except Exception as e:
                messages.error(request, f"Error updating settings: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SystemSettingsForm(instance=settings)
    
    return render(request, 'profile/system_settings.html', {
        'form': form,
        'settings': settings
    })


@login_required
@user_passes_test(is_admin)
def grading_system_view(request):
    """
    Manage grading system configuration
    """
    settings = SystemSettings.get_settings()
    
    if request.method == 'POST':
        import json
        try:
            grading_data = request.POST.get('grading_system_json')
            if grading_data:
                grading_system = json.loads(grading_data)
                # Validate structure
                for grade, config in grading_system.items():
                    if not all(k in config for k in ['min_score', 'max_score', 'remark']):
                        raise ValueError(f"Invalid grade configuration for {grade}")
                
                settings.grading_system = grading_system
                settings.last_modified_by = request.user
                settings.save()
                messages.success(request, "Grading system updated successfully!")
                return redirect('grading_system')
        except json.JSONDecodeError:
            messages.error(request, "Invalid JSON format")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Error updating grading system: {str(e)}")
    
    import json
    grading_json = json.dumps(settings.grading_system, indent=2) if settings.grading_system else ''
    
    return render(request, 'profile/grading_system.html', {
        'settings': settings,
        'grading_json': grading_json
    })
