# Register your models here.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Student, Guardian, Teacher, Class, Subject
from .models import TeacherAssignment, SubjectAssignment, Assessment, Assignment, ClassSubjectAssignment
from .models import Attendance, Expense, Payment, FeeAssignment, FinancialRecord
from .models import Session, Term, Result, Enrollment, Holiday, SchoolDay, Message
from .models import AssignmentSubmission, Notification, Exam, SubjectResult
from .models import CustomUser


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
    list_filter = ('role',)  # Add a filter for role in admin
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