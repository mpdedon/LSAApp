# core/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    # User and Profile Models
    CustomUser, Student, Guardian, Teacher,
    # Academic Structure Models
    Class, Subject, Session, Term, Enrollment, Holiday, SchoolDay,
    # Assignment/Teacher Linking Models
    TeacherAssignment, SubjectAssignment, ClassSubjectAssignment,
    # Assessment and Grading Models
    Assessment, Assignment, Exam, Question, SubjectResult,
    AssessmentSubmission, AssignmentSubmission, ExamSubmission, Result,
    # Financial Models
    Attendance, Expense, Payment, FeeAssignment, FinancialRecord,
    # Communication and Blog Models
    Message, Notification, EmailCampaign, Post, Category, Tag,
)
from django.utils.html import format_html # For custom display fields

# --- Admin Actions (Define these once at the top) ---

@admin.action(description='Promote selected students')
def promote_students(modeladmin, request, queryset):
    for student in queryset:
        student.promote()
    modeladmin.message_user(request, f"{queryset.count()} student(s) successfully promoted.")

@admin.action(description='Repeat selected students')
def repeat_students(modeladmin, request, queryset):
    for student in queryset:
        student.repeat()
    modeladmin.message_user(request, f"{queryset.count()} student(s) marked for repeating.")

@admin.action(description='Demote selected students')
def demote_students(modeladmin, request, queryset):
    for student in queryset:
        student.demote()
    modeladmin.message_user(request, f"{queryset.count()} student(s) successfully demoted.")

@admin.action(description='Mark selected as Dormant')
def mark_dormant(modeladmin, request, queryset):
    updated_count = queryset.update(status='dormant')
    modeladmin.message_user(request, f"{updated_count} record(s) marked as Dormant.")

@admin.action(description='Mark selected as Left School')
def mark_left(modeladmin, request, queryset):
    # This might require more complex logic depending on model,
    # for now, assuming status update is sufficient.
    updated_count = queryset.update(status='left')
    modeladmin.message_user(request, f"{updated_count} record(s) marked as Left School.")

@admin.action(description='Mark selected as Active')
def mark_active(modeladmin, request, queryset):
    updated_count = queryset.update(status='active')
    modeladmin.message_user(request, f"{updated_count} record(s) marked as Active.")


# --- User and Profile Management ---

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """
    Custom Admin for the CustomUser model.
    Inherits from Django's BaseUserAdmin and adds the 'role' field.
    """
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'role')
    list_filter = BaseUserAdmin.list_filter + ('role',)
    
    # Add 'role' to the fieldsets for user editing in the admin
    fieldsets = BaseUserAdmin.fieldsets + (
        ('User Role & Profile', {'fields': ('role',)}),
    )
    # Add 'role' to the user creation form in the admin
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {'fields': ('role',)}),
    )

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'LSA_number', 'current_class', 'status')
    list_filter = ('current_class__name', 'status', 'gender')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'LSA_number')
    raw_id_fields = ('user', 'student_guardian') # Use search popup for User and Guardian fields
    list_per_page = 25
    actions = [promote_students, repeat_students, demote_students, mark_dormant, mark_active, mark_left]

@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'contact', 'status', 'student_count')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user',)
    list_filter = ('status',)
    actions = [mark_dormant, mark_active, mark_left]

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'employee_id', 'contact', 'status')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'employee_id')
    raw_id_fields = ('user',)
    list_filter = ('status',)
    actions = [mark_dormant, mark_active, mark_left]


# --- Academic Structure Management ---

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'class_teacher_name', 'student_count')
    
    def student_count(self, obj):
        return obj.enrolled_students.count()
    student_count.short_description = 'No. of Students'
    
    def class_teacher_name(self, obj):
        # Assuming a method or related manager exists to get the form teacher
        # This is a placeholder, adjust based on your model logic
        assignment = obj.teacherassignment_set.filter(is_form_teacher=True).first()
        return assignment.teacher if assignment else "N/A"
    class_teacher_name.short_description = 'Form Teacher'

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject_weight')
    search_fields = ('name', 'subject_weight')

@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('name', 'session', 'start_date', 'end_date', 'is_active')
    list_filter = ('session', 'is_active')

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)


# --- Assessment, Exam, and Assignment Management ---

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'class_assigned', 'created_by', 'due_date', 'is_approved')
    list_filter = ('class_assigned', 'subject', 'is_approved', 'term')
    search_fields = ('title', 'created_by__username')
    raw_id_fields = ('created_by', 'approved_by')
    list_per_page = 20

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'class_assigned', 'teacher', 'due_date', 'active')
    list_filter = ('class_assigned', 'subject', 'active', 'term')
    search_fields = ('title', 'teacher__user__username')
    raw_id_fields = ('teacher',)
    list_per_page = 20

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'class_assigned', 'created_by', 'due_date', 'is_approved')
    list_filter = ('class_assigned', 'subject', 'is_approved', 'term')
    search_fields = ('title', 'created_by__username')
    raw_id_fields = ('created_by', 'approved_by')
    list_per_page = 20

@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'submitted_at', 'grade', 'is_completed')
    list_filter = ('is_completed', 'assignment__class_assigned')
    search_fields = ('student__user__username', 'assignment__title')
    raw_id_fields = ('student', 'assignment')


# --- Blog Management ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name',)

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name',)

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'published_date', 'views_count')
    list_filter = ('status', 'created_at', 'published_date', 'author')
    search_fields = ('title', 'content')
    raw_id_fields = ('author',)
    date_hierarchy = 'published_date'
    ordering = ('status', '-published_date')
    filter_horizontal = ('categories', 'tags')
    fieldsets = (
        (None, {'fields': ('title', 'author', 'content', 'featured_image')}),
        ('Publication', {'fields': ('status', 'published_date')}),
        ('Categorization', {'fields': ('categories', 'tags')}),
        ('SEO', {'classes': ('collapse',), 'fields': ('meta_description', 'meta_keywords')}),
    )
    readonly_fields = ('slug', 'views_count', 'created_at', 'updated_at')


# --- Other Models (Simple Registration) ---

admin.site.register(Enrollment)
admin.site.register(TeacherAssignment)
admin.site.register(SubjectAssignment)
admin.site.register(ClassSubjectAssignment)
admin.site.register(Attendance)
admin.site.register(Expense)
admin.site.register(FeeAssignment)
admin.site.register(Payment)
admin.site.register(Result)
admin.site.register(FinancialRecord)
admin.site.register(Holiday)
admin.site.register(SchoolDay)
admin.site.register(SubjectResult)
admin.site.register(Notification)
admin.site.register(Message)
admin.site.register(EmailCampaign)