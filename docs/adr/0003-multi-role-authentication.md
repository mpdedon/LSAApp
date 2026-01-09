# ADR-0003: Multi-Role Authentication Model

## Status
**Accepted**

**Date:** 2024-12-22  
**Author:** Development Team

---

## Context

### Problem Statement
School management system requires different user types with distinct permissions and data access:
- **Students:** Access grades, courses, assignments
- **Teachers:** Manage classes, grade students, create content
- **Guardians:** View their children's progress
- **Admin:** Full system access

Need to decide how to model these roles in Django's authentication system.

### Current State
Starting fresh with Django 5.0.1's built-in User model. Need to extend for school-specific requirements.

### Assumptions
- Users can have only ONE primary role
- Guardian can monitor multiple students
- Student/Teacher data needs custom fields (admission number, subjects, etc.)
- Admin uses Django's built-in superuser

---

## Decision

### What We've Decided
**We will use Django's custom User model with a role field and separate profile models (Student, Teacher, Guardian) linked via OneToOne relationships.**

### Rationale

**Custom User Model approach:**
```python
# core/models.py
class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('guardian', 'Guardian'),
        ('admin', 'Admin'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    admission_number = models.CharField(max_length=20, unique=True)
    # ... student-specific fields
    
class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True)
    # ... teacher-specific fields
```

**Benefits:**
- Single authentication system for all users
- Role stored directly on User model for quick checks
- Profile models keep role-specific data separate
- Django permissions and groups still work
- Can use `@login_required` and custom decorators

### Implementation Approach
1. Create custom User model extending AbstractUser
2. Add `user_type` field with choices
3. Create Student, Teacher, Guardian models with OneToOne to User
4. Create decorators: `@student_required`, `@teacher_required`
5. Use signals to create profile when User created

---

## Consequences

### Positive Consequences
- ✅ **Single Sign-On:** One account per person across all features
- ✅ **Role Enforcement:** Easy to check `user.user_type` in views
- ✅ **Django Compatibility:** Works with built-in auth, permissions
- ✅ **Data Separation:** Student data separate from Teacher data
- ✅ **Type Safety:** Can query `Student.objects.all()` without filtering

### Negative Consequences
- ❌ **Migration Complexity:** Custom User must be set at project start
- ❌ **Join Queries:** Need to join User + Student tables
- ⚠️ **Role Changes:** Difficult to change student → teacher (requires data migration)

### Trade-offs
- **Simplicity vs. flexibility:** Single role per user vs. multi-role support
- **Performance:** Extra join vs. denormalized data
- **Type safety:** Separate models vs. single User table with JSON fields

---

## Alternatives Considered

### Alternative 1: Django Groups for Roles
**Description:** Use built-in Groups (Students, Teachers, Guardians)

**Pros:**
- Built-in Django feature
- Supports multiple roles per user
- Permission integration

**Cons:**
- Group membership queries slower than field check
- No type-specific fields (where to store admission_number?)
- Groups meant for permissions, not role modeling

**Why rejected:** Groups don't solve the problem of storing role-specific data like admission numbers or employee IDs.

### Alternative 2: Separate User Tables
**Description:** Different tables for StudentUser, TeacherUser, GuardianUser

**Pros:**
- Complete data separation
- No OneToOne joins needed

**Cons:**
- Can't query all users at once
- Three authentication systems to maintain
- Guardian needs access to student portal (how?)
- Violates DRY principle

**Why rejected:** Creates massive complexity for authentication, permissions, and cross-role features.

### Alternative 3: Single User Table with JSON Fields
**Description:** Store all role data in JSONField on User

**Pros:**
- No joins needed
- Flexible schema

**Cons:**
- Can't query by student-specific fields efficiently
- No referential integrity
- Violates database normalization
- Type checking difficult

**Why rejected:** JSON fields sacrifice database integrity and query performance for minimal benefit.

---

## References

### Documentation
- [Django Custom User Model](https://docs.djangoproject.com/en/5.0/topics/auth/customizing/#substituting-a-custom-user-model)
- [OneToOne Relationships](https://docs.djangoproject.com/en/5.0/ref/models/fields/#onetoonefield)

### Discussion
- Team meeting: 2024-12-20
- Django best practices research

### Code
- User model: `core/models.py` lines 15-35
- Decorators: `core/decorators.py`
- Signals: `core/signals.py`

---

## Notes

### Review History
- **2024-12-20:** Initial proposal
- **2024-12-21:** Discussed alternatives
- **2024-12-22:** ADR accepted, User model created

### Future Considerations
- **Multi-role support:** If user needs both student AND teacher role, will require architecture change
- **Guest accounts:** May add 'guest' role for trial access
- **Role hierarchy:** Could add admin levels (super_admin, school_admin, etc.)

### Implementation Details
Created custom decorators:
```python
def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.user_type != 'student':
            return HttpResponseForbidden()
        return view_func(request, *args, **kwargs)
    return wrapper
```

---

**Last Updated:** 2024-12-22
