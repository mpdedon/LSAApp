# LSALMS App - Learning Management System

The `lsalms` app provides comprehensive online learning management capabilities integrated with the school management system.

## 📋 Overview

**Purpose:** Course delivery, student enrollment, progress tracking, and online academy

**Key Features:**
- Course and curriculum management
- Module and lesson organization
- Student enrollment and progress tracking
- Online academy (external course catalog)
- Quiz and assessment integration
- Content delivery (text, video, files)

---

## 🗂️ Models

### Course Management

#### Course
**File:** `lsalms/models.py`

Main course model for all online courses.

```python
class Course(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    image = models.ImageField(upload_to='courses/', blank=True)
    instructor = models.ForeignKey('core.Teacher', on_delete=models.CASCADE)
    is_published = models.BooleanField(default=False)
    is_subscription_based = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Key Fields:**
- `is_subscription_based`: If `False`, course is free (auto-enrollment)
- `is_published`: Controls visibility in online academy
- `instructor`: Teacher who created/teaches the course
- `price`: Course price (for future payment gateway integration)

**Key Methods:**
```python
def get_duration(self):
    """Calculate total course duration from all lessons"""
    total_minutes = sum(
        lesson.duration for module in self.modules.all() 
        for lesson in module.lessons.all()
    )
    return total_minutes

def get_enrollment_count(self):
    """Get total enrolled students"""
    return self.enrollments.filter(is_active=True).count()

def is_enrolled(self, student):
    """Check if student is enrolled"""
    return self.enrollments.filter(student=student, is_active=True).exists()
```

---

#### Module
Course content organized into modules/units.

```python
class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
```

**Ordering:** Modules displayed by `order` field, then creation date

---

#### Lesson
Individual learning units within modules.

```python
class Lesson(models.Model):
    LESSON_TYPE_CHOICES = (
        ('text', 'Text Content'),
        ('video', 'Video'),
        ('file', 'File Download'),
        ('quiz', 'Quiz'),
    )
    
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES)
    content = models.TextField(blank=True)  # For text lessons
    video_url = models.URLField(blank=True)  # For video lessons
    file = models.FileField(upload_to='lsalms/lessons/', blank=True)
    duration = models.IntegerField(default=0)  # Minutes
    order = models.IntegerField(default=0)
    is_preview = models.BooleanField(default=False)  # Free preview
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
```

**Lesson Types:**
- **Text:** Rich text content (using CKEditor)
- **Video:** Embedded video (YouTube, Vimeo URL)
- **File:** Downloadable resource (PDF, documents)
- **Quiz:** Assessment (future integration)

---

### Enrollment & Progress

#### Enrollment
Student enrollment in courses.

```python
class Enrollment(models.Model):
    student = models.ForeignKey('core.Student', on_delete=models.CASCADE, related_name='course_enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['student', 'course']
```

**Unique Constraint:** One enrollment per student per course

**Key Methods:**
```python
def get_progress_percentage(self):
    """Calculate completion percentage"""
    total_lessons = sum(
        module.lessons.count() 
        for module in self.course.modules.all()
    )
    if total_lessons == 0:
        return 0
    
    completed_lessons = self.lesson_progress.filter(completed=True).count()
    return round((completed_lessons / total_lessons) * 100, 2)

def mark_complete(self):
    """Mark enrollment as completed"""
    self.completed = True
    self.completion_date = timezone.now()
    self.save()
```

---

#### LessonProgress
Track individual lesson completion.

```python
class LessonProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['enrollment', 'lesson']
```

---

## 🔧 Key Views

### Online Academy (External Catalog)

**File:** `lsalms/views.py`

#### course_hub_view
Display all published courses in the online academy.

```python
@login_required
def course_hub_view(request):
    """Online academy - course catalog"""
    courses = Course.objects.filter(is_published=True).select_related('instructor')
    
    # Filter by search query
    query = request.GET.get('q')
    if query:
        courses = courses.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query)
        )
    
    # Pagination
    paginator = Paginator(courses, 9)  # 9 courses per page
    page = request.GET.get('page')
    courses_page = paginator.get_page(page)
    
    context = {
        'courses': courses_page,
        'total_courses': courses.count(),
    }
    return render(request, 'academy/hub.html', context)
```

**Template:** `lsalms/templates/academy/hub.html` (Modernized with cyberpunk theme)

---

#### course_detail_view
Show course details and enrollment button.

```python
@login_required
def course_detail_view(request, course_id):
    """Course detail page with enrollment"""
    course = get_object_or_404(Course, id=course_id, is_published=True)
    student = get_object_or_404(Student, user=request.user)
    
    # Check if already enrolled
    is_enrolled = Enrollment.objects.filter(
        student=student, 
        course=course, 
        is_active=True
    ).exists()
    
    # Get modules and lessons
    modules = course.modules.prefetch_related('lessons').all()
    
    context = {
        'course': course,
        'is_enrolled': is_enrolled,
        'modules': modules,
        'total_lessons': sum(m.lessons.count() for m in modules),
    }
    return render(request, 'academy/course_detail.html', context)
```

---

#### subscribe_to_course_view
Handle course enrollment (free auto-enrollment or payment).

```python
@login_required
@require_POST
def subscribe_to_course_view(request, course_id):
    """Enroll student in course"""
    course = get_object_or_404(Course, id=course_id)
    student = get_object_or_404(Student, user=request.user)
    
    # Check if already enrolled
    existing = Enrollment.objects.filter(student=student, course=course).first()
    if existing:
        if existing.is_active:
            messages.info(request, f"You're already enrolled in {course.title}")
        else:
            existing.is_active = True
            existing.save()
            messages.success(request, f"Re-enrolled in {course.title}")
        return redirect('lsalms:course_detail', course_id=course.id)
    
    # Check if course is paid
    is_paid_course = course.is_subscription_based
    
    if is_paid_course:
        # Future: Integrate payment gateway (Paystack)
        messages.info(request, "Payment integration coming soon. This is a paid course.")
        return redirect('lsalms:course_detail', course_id=course.id)
    else:
        # Free course - auto-enroll
        Enrollment.objects.create(
            student=student,
            course=course,
            enrollment_date=timezone.now()
        )
        messages.success(request, f"You've been enrolled in {course.title}! Start learning now.")
        return redirect('lsalms:course_detail', course_id=course.id)
```

**Decision Record:** See [ADR-0006](../adr/0006-free-course-auto-enrollment.md) for auto-enrollment rationale

---

### Internal LMS Views

#### my_courses_view
Student dashboard showing enrolled courses.

```python
@login_required
@student_required
def my_courses_view(request):
    """Student's enrolled courses"""
    student = get_object_or_404(Student, user=request.user)
    enrollments = Enrollment.objects.filter(
        student=student, 
        is_active=True
    ).select_related('course').prefetch_related('lesson_progress')
    
    # Calculate progress for each enrollment
    for enrollment in enrollments:
        enrollment.progress = enrollment.get_progress_percentage()
    
    context = {
        'enrollments': enrollments,
        'total_courses': enrollments.count(),
    }
    return render(request, 'lms/my_courses.html', context)
```

---

#### lesson_view
Display lesson content and track progress.

```python
@login_required
@student_required
def lesson_view(request, lesson_id):
    """View lesson and mark progress"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    student = get_object_or_404(Student, user=request.user)
    
    # Verify enrollment
    enrollment = get_object_or_404(
        Enrollment, 
        student=student, 
        course=lesson.module.course,
        is_active=True
    )
    
    # Get or create progress record
    progress, created = LessonProgress.objects.get_or_create(
        enrollment=enrollment,
        lesson=lesson
    )
    
    # Mark as completed if requested
    if request.method == 'POST':
        progress.completed = True
        progress.completed_at = timezone.now()
        progress.save()
        
        # Check if course completed
        if enrollment.get_progress_percentage() == 100:
            enrollment.mark_complete()
            messages.success(request, f"Congratulations! You completed {enrollment.course.title}!")
        
        messages.success(request, "Lesson marked as complete!")
        return redirect('lsalms:lesson_view', lesson_id=lesson.id)
    
    context = {
        'lesson': lesson,
        'progress': progress,
        'course': lesson.module.course,
        'module': lesson.module,
    }
    return render(request, 'lms/lesson_view.html', context)
```

---

## 📝 Forms

### CourseForm
**File:** `lsalms/forms.py`

```python
class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'image', 'instructor', 
                  'is_published', 'is_subscription_based', 'price']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def clean_price(self):
        """Validate price for subscription courses"""
        price = self.cleaned_data.get('price')
        is_subscription = self.cleaned_data.get('is_subscription_based')
        
        if is_subscription and price <= 0:
            raise ValidationError("Subscription-based courses must have a price > 0")
        
        return price
```

---

## 🎯 Services Layer

**File:** `lsalms/services.py`

Business logic separated from views.

```python
class CourseService:
    """Service layer for course operations"""
    
    @staticmethod
    def enroll_student(student, course):
        """Enroll student in course with validation"""
        if course.is_subscription_based:
            raise ValueError("Cannot auto-enroll in paid course")
        
        enrollment, created = Enrollment.objects.get_or_create(
            student=student,
            course=course,
            defaults={'enrollment_date': timezone.now()}
        )
        
        if not created and not enrollment.is_active:
            enrollment.is_active = True
            enrollment.save()
        
        return enrollment
    
    @staticmethod
    def calculate_course_progress(enrollment):
        """Calculate detailed progress breakdown"""
        modules = enrollment.course.modules.all()
        progress_data = []
        
        for module in modules:
            total = module.lessons.count()
            completed = enrollment.lesson_progress.filter(
                lesson__module=module,
                completed=True
            ).count()
            
            progress_data.append({
                'module': module,
                'total': total,
                'completed': completed,
                'percentage': round((completed / total * 100), 2) if total > 0 else 0
            })
        
        return progress_data
```

---

## 🔗 URL Routing

**File:** `lsalms/urls.py`

```python
app_name = 'lsalms'

urlpatterns = [
    # Online Academy (External)
    path('academy/', views.course_hub_view, name='academy_hub'),
    path('academy/course/<int:course_id>/', views.course_detail_view, name='course_detail'),
    path('academy/course/<int:course_id>/enroll/', views.subscribe_to_course_view, name='subscribe'),
    
    # Internal LMS
    path('my-courses/', views.my_courses_view, name='my_courses'),
    path('lesson/<int:lesson_id>/', views.lesson_view, name='lesson_view'),
    path('course/<int:course_id>/progress/', views.course_progress_view, name='course_progress'),
]
```

---

## 🎨 Templates

### Template Structure

```
lsalms/templates/
├── academy/               # External catalog
│   ├── hub.html          # Course listing (modernized)
│   └── course_detail.html # Course details (modernized)
│
└── lms/                  # Internal LMS
    ├── my_courses.html   # Student dashboard
    ├── course_view.html  # Course content view
    ├── lesson_view.html  # Lesson player
    └── progress.html     # Progress tracking
```

### Modern Template Features

**academy/hub.html:**
- Particles.js animated background
- Glassmorphic course cards
- Free/Premium badges with gradients
- Image fallbacks with onerror handlers
- Responsive grid layout
- Modern pagination

**academy/course_detail.html:**
- Sticky enrollment card
- Accordion curriculum display
- Breadcrumb navigation
- Gradient CTA buttons
- Mobile-responsive sidebar

---

## 📊 Admin Configuration

**File:** `lsalms/admin.py`

```python
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'is_published', 'is_subscription_based', 'price', 'created_at']
    list_filter = ['is_published', 'is_subscription_based', 'created_at']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'image', 'instructor')
        }),
        ('Pricing', {
            'fields': ('is_subscription_based', 'price')
        }),
        ('Publishing', {
            'fields': ('is_published',)
        }),
    )

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'enrollment_date', 'completed', 'is_active']
    list_filter = ['completed', 'is_active', 'enrollment_date']
    search_fields = ['student__user__first_name', 'course__title']
    date_hierarchy = 'enrollment_date'
```

---

## 🔐 Permissions & Access Control

```python
# Only students can view LMS
@student_required
def my_courses_view(request):
    pass

# Teachers can manage their own courses
@teacher_required
def teacher_course_list(request):
    teacher = get_object_or_404(Teacher, user=request.user)
    courses = Course.objects.filter(instructor=teacher)
    return render(request, 'lms/teacher_courses.html', {'courses': courses})

# Admins can manage all courses
@admin_required
def admin_course_list(request):
    courses = Course.objects.all()
    return render(request, 'lms/admin_courses.html', {'courses': courses})
```

---

## 🧪 Testing

**File:** `lsalms/tests.py`

```python
class EnrollmentTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student1', user_type='student')
        self.student = Student.objects.create(user=self.user, admission_number='2026001')
        self.teacher = Teacher.objects.create(user=User.objects.create_user(username='teacher1'))
        self.course = Course.objects.create(
            title='Python Basics',
            instructor=self.teacher,
            is_published=True,
            is_subscription_based=False
        )
    
    def test_free_course_enrollment(self):
        """Test auto-enrollment in free course"""
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course
        )
        self.assertTrue(enrollment.is_active)
        self.assertFalse(enrollment.completed)
    
    def test_progress_calculation(self):
        """Test progress percentage calculation"""
        module = Module.objects.create(course=self.course, title='Module 1')
        lesson1 = Lesson.objects.create(module=module, title='Lesson 1')
        lesson2 = Lesson.objects.create(module=module, title='Lesson 2')
        
        enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        
        # No progress
        self.assertEqual(enrollment.get_progress_percentage(), 0)
        
        # Complete one lesson
        LessonProgress.objects.create(enrollment=enrollment, lesson=lesson1, completed=True)
        self.assertEqual(enrollment.get_progress_percentage(), 50.0)
        
        # Complete all lessons
        LessonProgress.objects.create(enrollment=enrollment, lesson=lesson2, completed=True)
        self.assertEqual(enrollment.get_progress_percentage(), 100.0)
```

---

## 📱 Related Components

- **Core App:** Uses Student and Teacher models
- **Authentication:** Integrates with user roles
- **Blog:** Similar content management patterns

---

## 🚀 Future Enhancements

- [ ] Payment gateway integration (Paystack)
- [ ] Quiz and assessment system
- [ ] Discussion forums per course
- [ ] Certificates on completion
- [ ] Course reviews and ratings
- [ ] Instructor dashboard with analytics
- [ ] Mobile app API endpoints
- [ ] Live video classes integration

---

**Last Updated:** January 9, 2026  
**Version:** 2.0 (with modernized UI and auto-enrollment)
