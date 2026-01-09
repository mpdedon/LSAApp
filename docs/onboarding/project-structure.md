# Project Structure Guide

Understanding the codebase organization and file layout.

## 📁 Root Directory

```
LSAApp/
├── core/              # Main school management app
├── lsalms/            # Learning Management System app
├── lsaapp/            # Django project configuration
├── docs/              # Documentation
├── media/             # User-uploaded files (gitignored)
├── staticfiles/       # Collected static files for production
├── scripts/           # Utility scripts
├── lsa_env/           # Virtual environment (gitignored)
├── manage.py          # Django CLI
├── requirements.txt   # Python dependencies
├── compose.yaml       # Docker Compose configuration
├── Dockerfile         # Docker image definition
├── dump.sql           # Database backup
└── robot.txt          # Robots.txt for SEO
```

---

## 🎓 Core App Structure

**Path:** `core/`

The main school management application containing all student, teacher, class, and academic functionality.

```
core/
├── __init__.py
├── admin.py           # Django admin configuration
├── apps.py            # App configuration
├── decorators.py      # Custom decorators (@student_required, etc.)
├── fields.py          # Custom model fields
├── forms.py           # Base forms
├── models.py          # Core models (User, Student, Teacher, etc.)
├── signals.py         # Django signals
├── system_settings.py # Site-wide settings
├── tasks.py           # Celery tasks (future)
├── urls.py            # URL routing
├── utils.py           # Utility functions
├── views.py           # General views
├── views_user_accounts.py  # User management views
│
├── assessment/        # Assessment & grading
│   ├── forms.py
│   └── views.py
│
├── assignment/        # Student assignments
│   ├── forms.py
│   └── views.py
│
├── attendance/        # Attendance tracking
│   ├── forms.py
│   └── views.py
│
├── auth/              # Authentication
│   ├── forms.py
│   └── views.py
│
├── blog/              # Blog/content management
│   ├── forms.py
│   ├── sitemaps.py
│   └── views.py
│
├── classes/           # Class management
│   ├── forms.py
│   └── views.py
│
├── enrollment/        # Class enrollment
│   ├── forms.py
│   └── views.py
│
├── exams/             # Examination system
│   ├── forms.py
│   └── views.py
│
├── expense/           # Expense tracking
│   ├── forms.py
│   └── views.py
│
├── fee_assignment/    # Fee management
│   ├── forms.py
│   └── views.py
│
├── financial_record/  # Financial records
│   ├── forms.py
│   └── views.py
│
├── guardian/          # Guardian/parent management
│   ├── forms.py
│   └── views.py
│
├── management/        # Django management commands
│   └── commands/
│
├── migrations/        # Database migrations
│   ├── __init__.py
│   ├── 0001_initial.py
│   └── ...
│
├── payment/           # Payment processing
│   ├── forms.py
│   └── views.py
│
├── profile/           # User profiles
│   ├── forms.py
│   └── views.py
│
├── results/           # Exam results
│   ├── forms.py
│   └── views.py
│
├── session/           # Academic sessions/years
│   ├── forms.py
│   └── views.py
│
├── static/            # Core app static files
│   ├── css/
│   ├── js/
│   └── images/
│
├── student/           # Student management
│   ├── forms.py
│   └── views.py
│
├── subject/           # Subject management
│   ├── forms.py
│   └── views.py
│
├── subject_assignment/  # Assign subjects to classes
│   ├── forms.py
│   └── views.py
│
├── subject_result/    # Subject-level results
│   ├── forms.py
│   └── views.py
│
├── teacher/           # Teacher management
│   ├── forms.py
│   └── views.py
│
├── teacher_assignment/  # Assign teachers to subjects
│   ├── forms.py
│   └── views.py
│
├── templates/         # Django templates
│   ├── base.html      # Base template
│   ├── homepage.html
│   ├── dashboard/
│   ├── student/
│   ├── teacher/
│   ├── blog/
│   └── ...
│
├── templatetags/      # Custom template tags
│   └── custom_tags.py
│
├── term/              # Academic terms
│   ├── forms.py
│   └── views.py
│
└── tests/             # Unit tests
    └── ...
```

---

## 📚 LMS App Structure

**Path:** `lsalms/`

Learning Management System for online courses.

```
lsalms/
├── __init__.py
├── admin.py           # Admin configuration for LMS
├── apps.py            # App configuration
├── forms.py           # Course, module, lesson forms
├── models.py          # Course, Module, Lesson, Enrollment models
├── services.py        # Business logic services
├── signals.py         # LMS-specific signals
├── tests.py           # LMS tests
├── urls.py            # LMS URL routing
├── views.py           # Course, enrollment views
│
├── management/        # Management commands
│   └── commands/
│
├── migrations/        # Database migrations
│   ├── __init__.py
│   └── ...
│
├── templates/         # LMS templates
│   └── academy/       # Online academy (external catalog)
│       ├── hub.html   # Course listing
│       └── course_detail.html
│   └── lms/           # Internal LMS views
│       ├── course_list.html
│       ├── module_detail.html
│       └── lesson_view.html
│
└── templatetags/      # LMS template tags
    └── lms_tags.py
```

---

## ⚙️ Project Configuration

**Path:** `lsaapp/`

Django project settings and configuration.

```
lsaapp/
├── __init__.py
├── asgi.py            # ASGI config for async/WebSocket
├── celery_app.py      # Celery configuration
├── settings.py        # Django settings
├── urls.py            # Root URL configuration
└── wsgi.py            # WSGI config for deployment
```

### Key Settings Sections

**settings.py:**
- `INSTALLED_APPS` - Django apps
- `MIDDLEWARE` - Request/response processing
- `DATABASES` - Database configuration
- `AUTH_USER_MODEL = 'core.User'` - Custom user model
- `STATIC_ROOT`, `MEDIA_ROOT` - File paths
- `TEMPLATES` - Template configuration

---

## 📖 Documentation Structure

**Path:** `docs/`

```
docs/
├── README.md          # Documentation hub
│
├── architecture/      # System architecture
│   ├── overview.md
│   ├── characteristics.md
│   └── system-context.md
│
├── adr/               # Architectural Decision Records
│   ├── README.md
│   ├── TEMPLATE.md
│   ├── 0001-use-django-framework.md
│   └── ...
│
├── components/        # Component documentation
│   ├── core-app.md
│   ├── lsalms-app.md
│   ├── authentication.md
│   └── blog.md
│
├── onboarding/        # Developer onboarding
│   ├── README.md      # Quick start guide
│   ├── setup-local.md
│   ├── project-structure.md (this file)
│   ├── coding-standards.md
│   └── common-tasks.md
│
├── api/               # API documentation
│   ├── internal-apis.md
│   └── external-integrations.md
│
├── database/          # Database documentation
│   ├── schema-overview.md
│   └── migrations-guide.md
│
└── deployment/        # Deployment guides
    ├── production-setup.md
    ├── docker-guide.md
    └── media-files.md
```

---

## 🗄️ Media Files

**Path:** `media/`

User-uploaded files organized by app/type.

```
media/
├── blog/              # Blog images
│   └── featured/
├── courses/           # Course thumbnails
├── lsalms/            # LMS content
│   ├── lessons/
│   └── assignments/
└── profile_images/    # User avatars
```

**Not in Git:** Media files are gitignored and backed up separately.

---

## 📜 Utility Scripts

**Path:** `scripts/`

Standalone Python scripts for maintenance tasks.

```
scripts/
├── create_enrollments.py     # Bulk enrollment script
├── create_sample_activities.py  # Generate test data
└── export_sqlite.py           # Export SQLite to SQL
```

**Usage:**
```bash
python scripts/create_enrollments.py
```

---

## 🎨 Static Files

**Development:** Served from app `static/` directories  
**Production:** Collected to `staticfiles/` via `collectstatic`

```
core/static/
├── css/
│   ├── base.css
│   ├── dashboard.css
│   └── cyberpunk-theme.css
├── js/
│   ├── main.js
│   └── particles-config.js
└── images/
    └── logo.png
```

**Collected static files:**
```
staticfiles/
├── admin/             # Django admin static files
├── css/               # All collected CSS
├── js/                # All collected JavaScript
├── images/            # All collected images
└── staticfiles.json   # Manifest
```

---

## 🔧 Configuration Files

### requirements.txt
Python package dependencies. Install with:
```bash
pip install -r requirements.txt
```

### compose.yaml
Docker Compose configuration for containerized deployment.

### Dockerfile
Docker image definition.

### .gitignore
Specifies intentionally untracked files:
- `lsa_env/` (virtual environment)
- `*.pyc` (Python bytecode)
- `db.sqlite3` (development database)
- `media/` (user uploads)
- `.env` (secrets)

---

## 📝 File Naming Conventions

### Python Files
- **Models:** `models.py` (singular model classes)
- **Views:** `views.py` or feature-specific (e.g., `views_user_accounts.py`)
- **Forms:** `forms.py`
- **URLs:** `urls.py`
- **Tests:** `tests.py` or `test_*.py`

### Templates
- **Location:** `app/templates/app_name/`
- **Naming:** Lowercase with underscores (`student_list.html`)
- **Partials:** Prefix with `_` (`_sidebar.html`)

### Static Files
- **CSS:** Lowercase with hyphens (`student-dashboard.css`)
- **JS:** Lowercase with hyphens (`form-validation.js`)
- **Images:** Descriptive names (`logo-transparent.png`)

---

## 🔍 Finding Things

### Where is...?

**Student CRUD:** `core/student/`
**Course enrollment:** `lsalms/views.py` - `subscribe_to_course_view`
**Homepage:** `core/templates/homepage.html`
**User model:** `core/models.py` - class `User`
**Settings:** `lsaapp/settings.py`
**URL routing:** `lsaapp/urls.py` (root), then app-specific `urls.py`
**Admin config:** `core/admin.py` or `lsalms/admin.py`

### Search Strategies

**By filename:**
```bash
find . -name "models.py"
```

**By content:**
```bash
grep -r "class Student" --include="*.py"
```

**Django way:**
```bash
python manage.py show_urls  # If django-extensions installed
```

---

## 🚀 Application Flow

### URL → View → Template

1. **URL Matching:** `lsaapp/urls.py` → `core/urls.py`
2. **View Processing:** `core/student/views.py` → function
3. **Template Rendering:** `core/templates/student/student_list.html`

**Example:**
```
URL: /students/
↓
lsaapp/urls.py: path('', include('core.urls'))
↓
core/urls.py: path('students/', include('core.student.urls'))
↓
core/student/views.py: student_list(request)
↓
core/templates/student/student_list.html
```

---

## 📦 App Modularity

Each Django app is **self-contained**:
- Own models, views, forms
- Own templates (in app/templates/app_name/)
- Own static files (in app/static/)
- Own migrations
- Own tests

**Apps can import from each other:**
```python
# lsalms/models.py
from core.models import Student  # ✅ OK

# core/models.py
from lsalms.models import Course  # ⚠️ Avoid circular imports
```

---

## Next Steps

- [Coding Standards](coding-standards.md) - How to write code
- [Common Tasks](common-tasks.md) - Frequently performed operations
- [Core App Details](../components/core-app.md) - Deep dive into core
- [LMS App Details](../components/lsalms-app.md) - Deep dive into LMS

---

**Last Updated:** January 9, 2026
