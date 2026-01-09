# Core App - School Management System

The `core` app is the foundation of LearnSwift Academia, handling all school management functionality including students, teachers, classes, attendance, assessments, and finances.

## 📋 Overview

**Purpose:** Comprehensive school administration and academic management

**Key Features:**
- Student, Teacher, Guardian management
- Class and subject organization
- Attendance tracking
- Assessment and examination system
- Grade calculation and reporting
- Financial records and fee management
- Blog and content management

---

## 🗂️ Models

### User Authentication

#### User
**File:** `core/models.py`

Custom user model extending Django's `AbstractUser`.

```python
class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('guardian', 'Guardian'),
        ('admin', 'Admin'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True)
```

**Fields:**
- `user_type`: Role designation
- `profile_image`: User avatar
- Inherits: username, email, password, is_staff, is_active

**Relationships:**
- OneToOne → Student, Teacher, or Guardian (based on user_type)

---

### Student Management

#### Student
**File:** `core/models.py`

```python
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    admission_number = models.CharField(max_length=20, unique=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10)
    address = models.TextField()
    guardian = models.ForeignKey(Guardian, on_delete=models.SET_NULL, null=True)
    current_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True)
    enrollment_date = models.DateField()
    is_active = models.BooleanField(default=True)
```

**Key Methods:**
- `get_full_name()`: Returns first + last name
- `calculate_gpa()`: Computes GPA for term
- `get_attendance_percentage()`: Attendance rate calculation

---

#### ClassEnrollment
Links students to classes for specific academic sessions.

```python
class ClassEnrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    class_assigned = models.ForeignKey(Class, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    enrollment_date = models.DateField()
```

---

### Teacher Management

#### Teacher
**File:** `core/models.py`

```python
class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True)
    date_of_joining = models.DateField()
    qualification = models.CharField(max_length=200)
    subjects = models.ManyToManyField(Subject)
    phone_number = models.CharField(max_length=15)
```

**Key Methods:**
- `get_assigned_classes()`: Returns classes taught
- `get_subjects()`: Returns subjects expertise

---

### Class & Subject Organization

#### Class
Represents a grade level or class group.

```python
class Class(models.Model):
    name = models.CharField(max_length=100)  # e.g., "Grade 5A"
    class_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    capacity = models.IntegerField(default=30)
```

#### Subject
Academic subjects taught in the school.

```python
class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField()
```

#### SubjectAssignment
Assigns subjects to classes.

```python
class SubjectAssignment(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_assigned = models.ForeignKey(Class, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
```

---

### Academic Sessions & Terms

#### Session
Academic year (e.g., 2025/2026).

```python
class Session(models.Model):
    name = models.CharField(max_length=100)  # "2025/2026"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
```

#### Term
Academic term within a session (e.g., First Term).

```python
class Term(models.Model):
    TERM_CHOICES = (
        ('first', 'First Term'),
        ('second', 'Second Term'),
        ('third', 'Third Term'),
    )
    name = models.CharField(max_length=20, choices=TERM_CHOICES)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
```

---

### Attendance System

#### Attendance
Daily attendance records.

```python
class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=[
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ])
    remarks = models.TextField(blank=True)
```

---

### Assessment & Grading

#### Assessment
Individual assessments (quizzes, tests, exams).

```python
class Assessment(models.Model):
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_assigned = models.ForeignKey(Class, on_delete=models.CASCADE)
    date = models.DateField()
    total_marks = models.IntegerField()
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
```

#### AssessmentResult
Student scores on assessments.

```python
class AssessmentResult(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=2)
    remarks = models.TextField(blank=True)
```

#### SubjectResult
Final subject results for a term.

```python
class SubjectResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    ca_score = models.DecimalField(max_digits=5, decimal_places=2)  # Continuous Assessment
    exam_score = models.DecimalField(max_digits=5, decimal_places=2)
    total_score = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=2)
```

---

### Financial Management

#### FinancialRecord
Income and expense tracking.

```python
class FinancialRecord(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('income', 'Income'),
        ('expense', 'Expense'),
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    date = models.DateField()
    category = models.CharField(max_length=100)
```

#### Payment
Student fee payments.

```python
class Payment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=50)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    receipt_number = models.CharField(max_length=50, unique=True)
```

---

### Blog System

#### BlogPost
Blog posts and announcements.

```python
class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    featured_image = models.ImageField(upload_to='blog/', blank=True)
    published_date = models.DateTimeField()
    is_published = models.BooleanField(default=False)
    categories = models.ManyToManyField('BlogCategory')
    tags = models.ManyToManyField('BlogTag')
```

---

## 🔧 Key Views

### Student Management

**File:** `core/student/views.py`

- `student_list(request)` - List all students
- `student_create(request)` - Create new student
- `student_detail(request, pk)` - View student details
- `student_update(request, pk)` - Edit student
- `student_delete(request, pk)` - Delete student

**Decorators:**
```python
@login_required
@user_passes_test(lambda u: u.user_type in ['admin', 'teacher'])
def student_list(request):
    students = Student.objects.filter(is_active=True)
    return render(request, 'student/student_list.html', {'students': students})
```

---

### Attendance Views

**File:** `core/attendance/views.py`

- `mark_attendance(request)` - Daily attendance marking
- `attendance_report(request)` - Generate reports
- `student_attendance_detail(request, student_id)` - Individual student

---

### Assessment Views

**File:** `core/assessment/views.py`

- `create_assessment(request)` - Create new assessment
- `record_results(request, assessment_id)` - Input student scores
- `grade_calculation(request)` - Auto-calculate grades

---

## 📝 Forms

### StudentForm
**File:** `core/student/forms.py`

```python
class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['user', 'admission_number', 'date_of_birth', 'gender',
                  'address', 'guardian', 'current_class', 'enrollment_date']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }
```

---

## 🎯 Custom Decorators

**File:** `core/decorators.py`

```python
def student_required(view_func):
    """Restrict view to students only"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.user_type != 'student':
            return HttpResponseForbidden()
        return view_func(request, *args, **kwargs)
    return wrapper

def teacher_required(view_func):
    """Restrict view to teachers only"""
    # Similar implementation

def admin_required(view_func):
    """Restrict view to admins only"""
    # Similar implementation
```

**Usage:**
```python
@login_required
@student_required
def student_dashboard(request):
    # Only students can access
    pass
```

---

## 🔗 URL Routing

**File:** `core/urls.py`

```python
urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('students/', include('core.student.urls')),
    path('teachers/', include('core.teacher.urls')),
    path('classes/', include('core.classes.urls')),
    path('attendance/', include('core.attendance.urls')),
    path('assessments/', include('core.assessment.urls')),
    path('blog/', include('core.blog.urls')),
]
```

---

## 🎨 Templates

### Template Hierarchy

```
core/templates/
├── base.html                 # Base template with navbar, footer
├── homepage.html             # Landing page
├── dashboard/
│   ├── student_dashboard.html
│   ├── teacher_dashboard.html
│   └── admin_dashboard.html
├── student/
│   ├── student_list.html
│   ├── student_detail.html
│   └── student_form.html
├── teacher/
│   └── ...
└── blog/
    ├── post_list.html
    ├── post_detail.html
    ├── _post_card.html       # Partial template
    └── _sidebar.html         # Partial template
```

---

## 🛠️ Utilities

**File:** `core/utils.py`

```python
def generate_admission_number():
    """Generate unique admission number"""
    year = timezone.now().year
    last_student = Student.objects.filter(
        admission_number__startswith=str(year)
    ).order_by('-admission_number').first()
    
    if last_student:
        last_num = int(last_student.admission_number[-4:])
        new_num = last_num + 1
    else:
        new_num = 1
    
    return f"{year}{new_num:04d}"

def calculate_grade(score):
    """Convert numeric score to letter grade"""
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'
```

---

## 📊 Admin Configuration

**File:** `core/admin.py`

```python
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['admission_number', 'user', 'current_class', 'is_active']
    list_filter = ['current_class', 'is_active', 'enrollment_date']
    search_fields = ['admission_number', 'user__first_name', 'user__last_name']
    date_hierarchy = 'enrollment_date'
```

---

## 🔐 Permissions

### View-Level Permissions

```python
# Only admins can delete students
@login_required
@admin_required
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.delete()
    return redirect('student_list')
```

### Model-Level Permissions

Django default permissions:
- `core.add_student`
- `core.change_student`
- `core.delete_student`
- `core.view_student`

---

## 🧪 Testing

**File:** `core/tests/test_models.py`

```python
class StudentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='student1',
            user_type='student'
        )
        self.student = Student.objects.create(
            user=self.user,
            admission_number='20260001',
            date_of_birth='2010-01-01'
        )
    
    def test_admission_number_unique(self):
        self.assertTrue(Student.objects.filter(
            admission_number='20260001'
        ).exists())
```

---

## 📱 Related Apps/Components

- **LSALMS:** Uses Student and Teacher models for course enrollment
- **Authentication:** Provides User model foundation
- **Blog:** Content management for announcements

---

## 🚀 Common Operations

### Create Student Programmatically
```python
from core.models import User, Student

user = User.objects.create_user(
    username='newstudent',
    email='student@example.com',
    first_name='John',
    last_name='Doe',
    user_type='student'
)

student = Student.objects.create(
    user=user,
    admission_number='20260005',
    date_of_birth='2010-05-15',
    gender='male'
)
```

### Query Student Grades
```python
results = SubjectResult.objects.filter(
    student=student,
    term=current_term
)
total_score = sum(r.total_score for r in results)
```

---

**Last Updated:** January 9, 2026
