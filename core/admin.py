# Register your models here.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Student, Guardian, Teacher, Class, Subject
from .models import TeacherAssignment, SubjectAssignment, Assessment, Assignment, ClassSubjectAssignment
from .models import Attendance, Expense, Payment, FeeAssignment, FinancialRecord
from .models import Session, Term, Result, Enrollment, Holiday, SchoolDay, Message
from .models import AssignmentSubmission, Notification, Exam, SubjectResult
from .models import CustomUser, EmailCampaign
from .models import Post, Category, Tag


admin.site.register(Student)
admin.site.register(Guardian)
admin.site.register(Teacher)
admin.site.register(Class)
admin.site.register(Enrollment)
admin.site.register(Subject)
admin.site.register(TeacherAssignment)
admin.site.register(SubjectAssignment)
admin.site.register(ClassSubjectAssignment)
admin.site.register(Assessment)
admin.site.register(Assignment)
admin.site.register(CustomUser, UserAdmin)
admin.site.register(Attendance)
admin.site.register(Expense)
admin.site.register(FeeAssignment)
admin.site.register(Payment)
admin.site.register(Result)
admin.site.register(Session)
admin.site.register(Term)
admin.site.register(FinancialRecord)
admin.site.register(Holiday)
admin.site.register(SchoolDay)
admin.site.register(Exam)
admin.site.register(SubjectResult)
admin.site.register(AssignmentSubmission)
admin.site.register(Notification)
admin.site.register(Message)

class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role')  # Include role for visibility
    list_filter = ('role',)  
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password', 'role')}),
    )

    def save_model(self, request, obj, form, change):
        if not change and obj.role == CustomUser.TEACHER:  # Only assign on create
            obj.role = CustomUser.TEACHER
        super().save_model(request, obj, form, change)

@admin.action(description='Promote selected students')
def promote_students(modeladmin, request, queryset):
    for student in queryset:
        student.promote()

@admin.action(description='Repeat selected students')
def repeat_students(modeladmin, request, queryset):
    for student in queryset:
        student.repeat()

@admin.action(description='Demote selected students')
def demote_students(modeladmin, request, queryset):
    for student in queryset:
        student.demote()

@admin.action(description='Mark selected students as Dormant')
def mark_students_dormant(modeladmin, request, queryset):
    queryset.update(status='dormant')

@admin.action(description='Mark selected students as Left School')
def mark_students_left(modeladmin, request, queryset):
    queryset.update(status='left', current_class=None)


try:
    admin.site.unregister(Student)
except admin.sites.NotRegistered:
    pass

# Define admin class
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_class', 'status')
    list_filter = ('current_class', 'status')
    search_fields = ('user__first_name', 'user__last_name', 'current_class__name')
    actions = [promote_students, repeat_students, demote_students, mark_students_dormant, mark_students_left]

# Register model with admin
admin.site.register(Student, StudentAdmin)

@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ('subject', 'created_at')  # Use valid fields
    search_fields = ('subject',)  # Add searchable fields

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name',)
    # prepopulated_fields = {'slug': ('name',)} # Slug is auto-generated now

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name',)
    # prepopulated_fields = {'slug': ('name',)}

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'published_date', 'views_count')
    list_filter = ('status', 'created_at', 'published_date', 'author', 'categories', 'tags')
    search_fields = ('title', 'content')
    # prepopulated_fields = {'slug': ('title',)} # Slug is auto-generated on save
    raw_id_fields = ('author',) # Useful if many users
    date_hierarchy = 'published_date'
    ordering = ('status', '-published_date')
    filter_horizontal = ('categories', 'tags') # Better UI for ManyToMany

    fieldsets = (
        (None, {
            'fields': ('title', 'author', 'content', 'featured_image')
        }),
        ('Publication', {
            'fields': ('status', 'published_date')
        }),
        ('Categorization', {
            'fields': ('categories', 'tags')
        }),
        ('SEO', {
            'classes': ('collapse',), # Collapsible section
            'fields': ('meta_description', 'meta_keywords') 
        }),
    )
    readonly_fields = ('slug', 'views_count', 'created_at', 'updated_at') 

    def get_queryset(self, request):
        # Show all posts in admin, not just published
        return super().get_queryset(request)