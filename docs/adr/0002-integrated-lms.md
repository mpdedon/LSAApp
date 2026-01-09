# ADR-0002: Integrated LMS vs Separate System

## Status
**Accepted**

**Date:** 2024-12-20  
**Author:** Development Team

---

## Context

### Problem Statement
We need to decide whether the Learning Management System (LMS) should be integrated within the school management monolith or built as a separate system.

Requirements:
- Students should access courses from the same platform they use for grades/attendance
- Teachers should manage courses without separate login
- Data should be shared (student info, enrollment status)
- System should be maintainable by small team

### Current State
Django project exists with core school management features. Adding LMS capabilities.

### Assumptions
- Team size: 2-3 developers
- Users: 500-1000 students initially
- Budget: Limited infrastructure costs
- Timeline: LMS needed within 3 months

---

## Decision

### What We've Decided
**We will build the LMS as an integrated Django app (lsalms) within the existing monolith rather than as a separate system.**

### Rationale

**Integration benefits:**
- **Single Sign-On:** Students/teachers use one account across all features
- **Data Sharing:** Direct access to Student, Teacher, Class models via ORM
- **Simpler Deployment:** One application, one database, one server
- **Faster Development:** No need for API integration, authentication sync
- **Consistent UI:** Same Bootstrap theme and navigation

**Specific implementation:**
- Create `lsalms` Django app alongside `core`
- Reuse `Student` and `Teacher` models via foreign keys
- Share authentication system
- Unified navigation bar
- Single database with related tables

### Implementation Approach
1. Create `lsalms` app with Course, Module, Lesson models
2. Foreign key relationships to core.Student and core.Teacher
3. Enrollment model linking students to courses
4. Progress tracking within same database
5. Templates inherit from same base template as core

---

## Consequences

### Positive Consequences
- ✅ **Unified User Experience:** Students see grades and courses in one place
- ✅ **Data Consistency:** Single source of truth for student records
- ✅ **Simplified Deployment:** One server, one database to manage
- ✅ **Faster Development:** No API contracts, direct model access
- ✅ **Lower Infrastructure Costs:** One hosting environment
- ✅ **Easier Maintenance:** Small team can manage one codebase

### Negative Consequences
- ❌ **Tight Coupling:** LMS changes can affect school management
- ❌ **Scaling Limitations:** Can't scale LMS independently
- ❌ **Technology Lock-in:** LMS must use Django/Python
- ⚠️ **Deployment Risk:** Updates to LMS affect entire system

### Trade-offs
- **Simplicity vs. flexibility:** Easier to build/maintain vs. harder to extract later
- **Monolith vs. microservices:** Single codebase vs. distributed complexity
- **Shared database vs. service boundaries:** Direct queries vs. API overhead

---

## Alternatives Considered

### Alternative 1: Separate LMS System
**Description:** Build LMS as standalone application with API integration

**Pros:**
- Independent scaling
- Technology flexibility (could use different framework)
- Service isolation
- Easier to replace/upgrade

**Cons:**
- Authentication sync complexity
- API development overhead
- Two deployments to manage
- Duplicated student data
- Higher infrastructure costs

**Why rejected:** Team too small to manage two systems. Data synchronization would be error-prone. Infrastructure budget doesn't support multiple servers.

### Alternative 2: Use Open-Source LMS (Moodle/Canvas)
**Description:** Integrate existing LMS platform

**Pros:**
- Battle-tested features
- Active development
- Plugin ecosystem

**Cons:**
- Complex integration with our student database
- SSO setup overhead
- UI inconsistency
- Heavy/bloated for our needs
- Difficult customization

**Why rejected:** Generic LMS doesn't understand our specific school structure (terms, classes, Islamic calendar). Integration effort comparable to building custom solution.

### Alternative 3: Hybrid - LMS as Django App with API Layer
**Description:** Build LMS as Django app but expose APIs for future separation

**Pros:**
- Start simple, enable future separation
- API documentation for potential mobile app

**Cons:**
- Extra API development work upfront
- Complexity without immediate benefit

**Why rejected:** YAGNI (You Aren't Gonna Need It). We can add APIs later if needed. Don't over-engineer for uncertain future.

---

## References

### Documentation
- [Microservices vs Monolith Trade-offs](https://martinfowler.com/articles/dont-start-monolith.html)
- Django Multi-App Architecture: [Django Docs](https://docs.djangoproject.com/en/5.0/ref/applications/)

### Discussion
- Team meeting notes: 2024-12-18
- Cost-benefit analysis spreadsheet: [Internal]

### Code
- lsalms app created: Commit def456
- Course model implementation: Commit ghi789

---

## Notes

### Review History
- **2024-12-18:** Initial proposal for separate system
- **2024-12-19:** Team discussion, decided on integrated approach
- **2024-12-20:** ADR accepted, lsalms app created

### Future Considerations
- **Trigger for re-evaluation:** If LMS usage exceeds 50% of total traffic
- **Extraction path:** Could separate LMS into microservice later if needed
- **API addition:** May add REST API for mobile app without full separation
- **Performance monitoring:** Track if LMS queries slow down school management features

### Exit Strategy
If we need to separate later:
1. Add API layer to lsalms app
2. Duplicate Student data with sync mechanism
3. Deploy LMS separately with API calls to core
4. Migrate in phases (courses first, then enrollments)

---

**Last Updated:** 2024-12-20
