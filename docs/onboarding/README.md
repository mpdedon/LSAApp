# Developer Onboarding Guide

Welcome to the LearnSwift Academia development team! This guide will help you get started with the codebase.

## 🎯 Quick Start

**Time to first running app:** ~30 minutes

1. [Prerequisites](#prerequisites)
2. [Clone and Setup](#clone-and-setup)
3. [Run Development Server](#run-development-server)
4. [Explore the Application](#explore-the-application)
5. [Next Steps](#next-steps)

---

## Prerequisites

### Required Software
- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **PostgreSQL 14+** (production) or SQLite (development)
- **Git** - [Download](https://git-scm.com/)
- **Code Editor** - VS Code recommended

### Recommended Tools
- **DB Browser for SQLite** - View development database
- **Postman** - API testing (future)
- **Docker** (optional) - Container deployment

### Knowledge Requirements
- Python intermediate level
- Django basics (models, views, templates)
- HTML/CSS/Bootstrap
- Git fundamentals
- Basic SQL understanding

---

## Clone and Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd LSAApp
```

### 2. Create Virtual Environment
**Windows:**
```powershell
python -m venv lsa_env
lsa_env\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv lsa_env
source lsa_env/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

**Key packages installed:**
- Django 5.0.1
- psycopg2 (PostgreSQL adapter)
- Pillow (image handling)
- django-ckeditor-5 (rich text editor)
- celery (future background tasks)

### 4. Configure Environment Variables
Create `.env` file in project root:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Development)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# Email (Development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Media Files
MEDIA_ROOT=media
MEDIA_URL=/media/
```

**Generate SECRET_KEY:**
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Run Migrations
```bash
python manage.py migrate
```

Creates all database tables based on models.

### 6. Create Superuser
```bash
python manage.py createsuperuser
```

Follow prompts to create admin account.

### 7. Load Sample Data (Optional)
```bash
python manage.py loaddata core/fixtures/sample_data.json
```

---

## Run Development Server

### Start Server
```bash
python manage.py runserver
```

**Access application:**
- Main site: http://127.0.0.1:8000/
- Admin panel: http://127.0.0.1:8000/admin/
- Online Academy: http://127.0.0.1:8000/academy/

### Verify Installation
- [ ] Homepage loads with cyberpunk theme
- [ ] Admin login works
- [ ] Static files load (CSS, images)
- [ ] No console errors

---

## Explore the Application

### Default Accounts
After loading sample data:

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Admin | admin | admin123 | Full system |
| Teacher | teacher1 | teacher123 | Classes, grading |
| Student | student1 | student123 | Courses, grades |
| Guardian | guardian1 | guardian123 | Child's progress |

### Key URLs
- `/` - Homepage
- `/dashboard/` - Role-based dashboard
- `/academy/` - Online course catalog
- `/blog/` - Blog posts
- `/admin/` - Django admin

### Admin Panel Tour
1. Go to http://127.0.0.1:8000/admin/
2. Login with superuser credentials
3. Explore:
   - **Core** → Students, Teachers, Classes
   - **Lsalms** → Courses, Modules, Enrollments
   - **Blog** → Posts, Categories

---

## Project Structure

```
LSAApp/
├── core/              # School management (students, teachers, classes)
├── lsalms/            # Learning Management System (courses, modules)
├── lsaapp/            # Project settings and configuration
├── docs/              # Documentation (you are here!)
├── media/             # User-uploaded files
├── staticfiles/       # Collected static files (production)
├── scripts/           # Utility scripts
├── manage.py          # Django management script
└── requirements.txt   # Python dependencies
```

See [Project Structure](project-structure.md) for detailed breakdown.

---

## Development Workflow

### 1. Pick a Task
- Check GitHub issues or project board
- Discuss with team lead
- Read related ADRs in `docs/adr/`

### 2. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 3. Make Changes
- Edit code following [Coding Standards](coding-standards.md)
- Test locally
- Write/update tests

### 4. Run Tests
```bash
python manage.py test
```

### 5. Commit Changes
```bash
git add .
git commit -m "feat: add student attendance tracking"
```

**Commit message format:**
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `style:` formatting
- `refactor:` code restructuring
- `test:` adding tests

### 6. Push and Create PR
```bash
git push origin feature/your-feature-name
```

Create Pull Request on GitHub with:
- Clear description
- Related issue number
- Screenshots (if UI changes)

---

## Common Tasks

### Create New Model
See [Common Tasks Guide](common-tasks.md#create-model)

### Add New View
See [Common Tasks Guide](common-tasks.md#add-view)

### Create Template
See [Common Tasks Guide](common-tasks.md#create-template)

### Run Specific Migration
```bash
python manage.py migrate core 0005
```

### Reset Database (Development)
```bash
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

---

## Debugging Tips

### Django Debug Toolbar
Already installed. Shows:
- SQL queries per page
- Template render time
- Cache hits/misses

Access at: http://127.0.0.1:8000/ (sidebar on right)

### Common Errors

**Import Error:**
```
ModuleNotFoundError: No module named 'core'
```
**Solution:** Activate virtual environment

**Migration Error:**
```
django.db.migrations.exceptions.InconsistentMigrationHistory
```
**Solution:** Delete db.sqlite3 and re-migrate (dev only)

**Static Files Not Loading:**
```bash
python manage.py collectstatic
```

**Port Already in Use:**
```bash
python manage.py runserver 8001
```

---

## Getting Help

### Resources
- **Documentation:** `docs/` folder
- **ADRs:** `docs/adr/` - architectural decisions
- **Components:** `docs/components/` - app-specific docs
- **Django Docs:** https://docs.djangoproject.com/

### Team Communication
- Ask questions in team chat
- Tag senior developers for code review
- Consult ADRs before major decisions

---

## Next Steps

After completing this guide:

1. ✅ Read [Project Structure](project-structure.md)
2. ✅ Review [Coding Standards](coding-standards.md)
3. ✅ Explore [Core App](../components/core-app.md)
4. ✅ Study [LMS App](../components/lsalms-app.md)
5. ✅ Review [ADRs](../adr/README.md)
6. ✅ Take on first issue!

---

## Checklist

Before you start coding:

- [ ] Python 3.11+ installed
- [ ] Virtual environment activated
- [ ] Dependencies installed
- [ ] Migrations run
- [ ] Superuser created
- [ ] Development server running
- [ ] Admin panel accessible
- [ ] Read coding standards
- [ ] Understood project structure
- [ ] Know where to ask questions

**Ready to code! 🚀**

---

**Last Updated:** January 9, 2026  
**Maintainer:** Development Team
