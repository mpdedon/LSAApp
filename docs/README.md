# LearnSwift Academia - Documentation Hub

> Comprehensive documentation for the LearnSwift Academia School Management System

## 📚 Documentation Index

### Getting Started
- [Developer Onboarding](onboarding/README.md) - **Start here if you're new to the project**
- [Local Setup Guide](onboarding/setup-local.md) - Environment setup and installation
- [Project Structure](onboarding/project-structure.md) - Codebase organization and navigation

### Architecture
- [System Overview](architecture/overview.md) - High-level architecture and design
- [Architectural Style](architecture/architectural-style.md) - Monolithic Django, layered architecture
- [Architectural Characteristics](architecture/characteristics.md) - Performance, security, scalability goals
- [System Context](architecture/system-context.md) - External systems and integrations

### Components
- [Core App](components/core-app.md) - School management functionality
- [LMS App](components/lsalms-app.md) - Learning Management System
- [Authentication System](components/authentication.md) - User management and access control
- [Blog System](components/blog.md) - Content management

### Architectural Decision Records (ADRs)
- [ADR Index](adr/README.md) - All architectural decisions
- [ADR Template](adr/TEMPLATE.md) - How to write new ADRs

### API & Integration
- [Internal APIs](api/internal-apis.md) - View functions, services, utilities
- [External Integrations](api/external-integrations.md) - Third-party services

### Database
- [Schema Overview](database/schema-overview.md) - Database design and relationships
- [Migrations Guide](database/migrations-guide.md) - Managing database changes

### Deployment
- [Production Setup](deployment/production-setup.md) - Server configuration
- [Docker Guide](deployment/docker-guide.md) - Container deployment
- [Media Files](deployment/media-files.md) - Static and media file serving

---

## 🎯 Quick Links

### For New Developers
1. Read [Developer Onboarding](onboarding/README.md)
2. Follow [Local Setup Guide](onboarding/setup-local.md)
3. Review [Project Structure](onboarding/project-structure.md)
4. Check [Coding Standards](onboarding/coding-standards.md)

### For Feature Development
1. Review [Component Analysis](components/) for affected areas
2. Check [ADRs](adr/README.md) for context on past decisions
3. Follow [Common Tasks](onboarding/common-tasks.md) guide

### For Deployment
1. Review [Production Setup](deployment/production-setup.md)
2. Follow [Docker Guide](deployment/docker-guide.md) if using containers
3. Configure [Media Files](deployment/media-files.md) serving

---

## 🏗️ System Overview

LearnSwift Academia is an integrated school management system with Learning Management capabilities built on Django 5.0.1.

**Key Features:**
- Student, Teacher, Guardian management
- Class and subject organization
- Attendance tracking
- Assessment and grading
- Financial records and fee management
- Integrated LMS (Learning Management System)
- Blog and content management
- Modern responsive UI with cyberpunk theme

**Technology Stack:**
- **Backend:** Django 5.0.1, Python 3.11+
- **Database:** PostgreSQL (production), SQLite (development)
- **Frontend:** Bootstrap 5.3.2, Particles.js, vanilla JavaScript
- **Task Queue:** Celery (future)
- **Deployment:** Docker, Nginx

---

## 📝 Documentation Standards

### Writing Documentation
- Use Markdown (.md) format
- Include code examples where helpful
- Add diagrams using Mermaid syntax
- Keep language clear and concise
- Update docs when code changes

### ADR Format
When making architectural decisions:
1. Copy [ADR Template](adr/TEMPLATE.md)
2. Number sequentially (0001, 0002, etc.)
3. Fill in all sections
4. Commit with code changes

### Diagrams
Use Mermaid for:
- Architecture diagrams
- Flow charts
- Entity relationships
- Sequence diagrams

---

## 🔄 Keeping Docs Updated

**When to update documentation:**
- ✅ Adding new features
- ✅ Making architectural changes
- ✅ Changing deployment processes
- ✅ Updating dependencies
- ✅ Fixing complex bugs

**Documentation is code.** Treat it with the same care and version control.

---

## 🤝 Contributing to Docs

1. **Found outdated info?** Submit a PR with updates
2. **Missing documentation?** Create new pages following structure
3. **Unclear explanations?** Add examples or clarify language
4. **New architectural decision?** Write an ADR

---

## 📞 Support

- **Technical Questions:** Check component docs or ADRs
- **Setup Issues:** Review onboarding guides
- **Architecture Discussions:** Propose ADR

---

**Last Updated:** January 8, 2026
**Version:** 1.0.0
