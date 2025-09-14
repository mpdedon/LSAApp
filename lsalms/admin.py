from django.contrib import admin

# Register your models here.
# lsalms/admin.py

from django.contrib import admin
from .models import (
    Course, Module, Lesson, ContentBlock, LearningTrack, TrackCourseOrder,
    PracticeQuiz, PracticeQuestion, CourseEnrollment, CourseGrade,
    StudentActivityLog, SpacedRepetitionItem, AIInteractionLog
)

# Admin UX Note: We define inlines first. Inlines are the key to creating a powerful
# "builder" experience, allowing you to edit related models on the same page.

class ContentBlockInline(admin.TabularInline):
    """
    Allows adding/editing ContentBlocks directly within the Lesson change page.
    This is the lowest level of our "Course Builder".
    """
    model = ContentBlock
    extra = 1
    # For better UX on complex inlines, we can group fields.
    fieldsets = (
        (None, {
            'fields': (('title', 'content_type', 'order'),)
        }),
        ('Content Payload', {
            'classes': ('collapse',), # Collapsible for a cleaner look
            'fields': ('rich_text', 'media_url', 'media_file'),
        }),
        ('Activity Links', {
            'classes': ('collapse',),
            'fields': ('linked_practice_quiz', 'linked_assignment', 'linked_assessment', 'linked_exam'),
        }),
    )
    # Power-Up Suggestion: Use a library like 'django-admin-sortable2' to make these
    # inlines drag-and-drop reorderable.


class LessonInline(admin.TabularInline):
    """
    Allows adding/editing Lessons directly within the Module change page.
    """
    model = Lesson
    extra = 1
    fields = ('title', 'order', 'estimated_duration')
    show_change_link = True # Crucial for navigating to the Lesson's detail view to add ContentBlocks.


class ModuleInline(admin.TabularInline):
    """
    Allows adding/editing Modules directly within the Course change page.
    """
    model = Module
    extra = 1
    fields = ('title', 'order', 'description')
    show_change_link = True # Navigate to the Module's detail view to add Lessons.


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """
    This is the master "Course Builder" interface. It's the starting point for teachers.
    """
    # --- List View Configuration (for browsing courses) ---
    list_display = ('title', 'teacher', 'status', 'course_type', 'linked_class', 'term')
    list_filter = ('status', 'course_type', 'teacher')
    search_fields = ('title', 'description', 'teacher__username')

    # --- Form View Configuration (for creating/editing a course) ---
    prepopulated_fields = {'slug': ('title',)} # Auto-fills slug for better UX.
    inlines = [ModuleInline]

    # Admin UX Note: Fieldsets organize the form into logical sections, making a complex
    # model much less intimidating for the user.
    fieldsets = (
        ('Core Details', {
            'fields': ('title', 'slug', 'teacher', 'status')
        }),
        ('Pedagogy & Content Overview', {
            'description': "Provide a clear overview for prospective students and guardians.",
            'fields': ('learning_objectives', 'prerequisites')
        }),
        ('Access & Structure (IMPORTANT)', {
            'fields': ('course_type', ('linked_class', 'term'), 'is_subscription_based')
        }),
        ('Advanced: Grading', {
            'classes': ('collapse',), # Hide by default as it's an advanced setting.
            'fields': ('grading_weights',)
        }),
    )

    # --- Actions for Bulk Operations ---
    actions = ['publish_courses', 'archive_courses']

    @admin.action(description='Mark selected courses as Published')
    def publish_courses(self, request, queryset):
        queryset.update(status=Course.Status.PUBLISHED)

    @admin.action(description='Mark selected courses as Archived')
    def archive_courses(self, request, queryset):
        queryset.update(status=Course.Status.ARCHIVED)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    """
    Dedicated admin view for a Module, showing its Lessons.
    """
    list_display = ('title', 'course', 'order')
    list_filter = ('course__title',)
    search_fields = ('title',)
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """
    Dedicated admin view for a Lesson, showing its ContentBlocks.
    This is where the actual content is assembled.
    """
    list_display = ('title', 'module', 'order', 'estimated_duration')
    list_filter = ('module__course__title', 'module__title')
    search_fields = ('title',)
    inlines = [ContentBlockInline]


class TrackCourseOrderInline(admin.TabularInline):
    """
    This inline will be used within the LearningTrackAdmin.
    It allows us to manage the 'courses' relationship and its extra data ('order').
    """
    model = TrackCourseOrder
    extra = 1
    # For a better UX, use autocomplete_fields for the course selection.
    # This is much better than a dropdown if you have many courses.
    autocomplete_fields = ['course']


@admin.register(LearningTrack)
class LearningTrackAdmin(admin.ModelAdmin):
    """
    Admin for curating sequences of courses.
    We are replacing the problematic 'filter_horizontal' with our new inline.
    """
    list_display = ('title',)
    search_fields = ('title', 'description')
    
    # This is the corrected implementation:
    inlines = [TrackCourseOrderInline]


class PracticeQuestionInline(admin.TabularInline):
    model = PracticeQuestion
    extra = 3

@admin.register(PracticeQuiz)
class PracticeQuizAdmin(admin.ModelAdmin):
    """
    Admin for creating ungraded retrieval practice quizzes.
    """
    list_display = ('title', 'created_by')
    search_fields = ('title',)
    inlines = [PracticeQuestionInline]


# === Read-Only Views for Logging and Auditing ===

@admin.register(StudentActivityLog)
class StudentActivityLogAdmin(admin.ModelAdmin):
    """
    A read-only interface for administrators to review student activity for
    support or auditing purposes.
    """
    list_display = ('timestamp', 'student', 'activity_type', 'related_object')
    list_filter = ('activity_type', 'student__user__username')
    readonly_fields = [f.name for f in StudentActivityLog._meta.fields] # Makes all fields read-only

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AIInteractionLog)
class AIInteractionLogAdmin(admin.ModelAdmin):
    """
    A read-only interface for auditing AI usage and costs.
    """
    list_display = ('timestamp', 'user', 'task_type', 'prompt_tokens', 'response_tokens')
    list_filter = ('task_type', 'user')
    readonly_fields = [f.name for f in AIInteractionLog._meta.fields]

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


# --- Simple Registrations for other models ---
# These models are mostly managed through other interfaces or automatically,
# but they are registered here for admin visibility and manual correction if needed.

@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at', 'is_active')
    list_filter = ('course__title',)
    search_fields = ('student__user__username', 'course__title')
    autocomplete_fields = ['student', 'course'] # Makes selection easier with many users/courses.

admin.site.register(SpacedRepetitionItem)
admin.site.register(CourseGrade)