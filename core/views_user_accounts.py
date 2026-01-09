from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from core.models import CustomUser, Student, Teacher, Guardian
from django.core.paginator import Paginator


def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)


@login_required
@user_passes_test(is_admin)
def user_account_list(request):
    """List all user accounts with filtering and search"""
    query = request.GET.get('q', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    per_page = int(request.GET.get('per_page', 20))
    
    users = CustomUser.objects.all().order_by('-date_joined')
    
    # Apply filters
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )
    
    if role_filter:
        users = users.filter(role=role_filter)
    
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Count stats
    total_users = CustomUser.objects.count()
    active_users = CustomUser.objects.filter(is_active=True).count()
    inactive_users = CustomUser.objects.filter(is_active=False).count()
    student_count = CustomUser.objects.filter(role='student').count()
    teacher_count = CustomUser.objects.filter(role='teacher').count()
    guardian_count = CustomUser.objects.filter(role='guardian').count()
    admin_count = CustomUser.objects.filter(role='admin').count()
    
    paginator = Paginator(users, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'per_page': per_page,
        'counts': {
            'total': total_users,
            'active': active_users,
            'inactive': inactive_users,
            'students': student_count,
            'teachers': teacher_count,
            'guardians': guardian_count,
            'admins': admin_count,
        }
    }
    
    return render(request, 'accounts/user_account_list.html', context)


@login_required
@user_passes_test(is_admin)
def toggle_user_status(request, user_id):
    """Activate or deactivate a user account"""
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Prevent admin from deactivating themselves
        if user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect('user_account_list')
        
        user.is_active = not user.is_active
        user.save()
        
        status = "activated" if user.is_active else "deactivated"
        messages.success(request, f"User account '{user.username}' has been {status}.")
    
    return redirect('user_account_list')


@login_required
@user_passes_test(is_admin)
def reset_user_password(request, user_id):
    """Reset a user's password"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Password for '{user.username}' has been reset successfully.")
            return redirect('user_account_list')
    else:
        form = SetPasswordForm(user)
    
    context = {
        'form': form,
        'target_user': user
    }
    
    return render(request, 'accounts/reset_password.html', context)


@login_required
@user_passes_test(is_admin)
def change_user_role(request, user_id):
    """Change a user's role"""
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        new_role = request.POST.get('role')
        
        # Prevent admin from changing their own role
        if user == request.user:
            messages.error(request, "You cannot change your own role.")
            return redirect('user_account_list')
        
        if new_role in ['student', 'teacher', 'guardian', 'admin']:
            old_role = user.role
            user.role = new_role
            user.save()
            
            messages.success(request, f"User '{user.username}' role changed from {old_role} to {new_role}.")
        else:
            messages.error(request, "Invalid role selected.")
    
    return redirect('user_account_list')


@login_required
@user_passes_test(is_admin)
def bulk_user_action(request):
    """Perform bulk actions on user accounts"""
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_users = request.POST.getlist('selected_users')
        
        if not action or not selected_users:
            messages.error(request, "Please select both an action and at least one user.")
            return redirect('user_account_list')
        
        users = CustomUser.objects.filter(id__in=selected_users)
        
        # Exclude the current admin from bulk actions
        users = users.exclude(id=request.user.id)
        
        if action == 'activate':
            count = users.update(is_active=True)
            messages.success(request, f"{count} user(s) activated successfully.")
        elif action == 'deactivate':
            count = users.update(is_active=False)
            messages.success(request, f"{count} user(s) deactivated successfully.")
        elif action == 'delete':
            count = users.count()
            users.delete()
            messages.success(request, f"{count} user(s) deleted successfully.")
        else:
            messages.error(request, "Invalid action selected.")
    
    return redirect('user_account_list')


@login_required
@user_passes_test(is_admin)
def user_account_detail(request, user_id):
    """View detailed information about a user account"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    # Get profile based on role
    profile = None
    if user.role == 'student' and hasattr(user, 'student'):
        profile = user.student
    elif user.role == 'teacher' and hasattr(user, 'teacher'):
        profile = user.teacher
    elif user.role == 'guardian' and hasattr(user, 'guardian'):
        profile = user.guardian
    
    context = {
        'target_user': user,
        'profile': profile,
    }
    
    return render(request, 'accounts/user_account_detail.html', context)
