# ADR-0006: Free Course Auto-Enrollment

## Status
**Accepted**

**Date:** 2026-01-08  
**Author:** Development Team

---

## Context

### Problem Statement
The online academy (external course catalog) has two types of courses:
1. **Free courses:** Should be accessible to all authenticated users
2. **Paid courses:** Require payment before access

Previous implementation required manual enrollment for all courses, creating friction for free content.

Requirements:
- Reduce barriers to free course access
- Maintain payment requirement for paid courses
- Track who accesses what content
- Prepare for future payment gateway integration

### Current State
- All courses require explicit enrollment action
- Users click "Enroll" button regardless of course price
- No distinction between free and paid in enrollment flow
- `Course.is_subscription_based` field exists but unused

### Assumptions
- Users are authenticated (login required)
- Free courses have `is_subscription_based = False`
- Payment gateway integration coming later
- Enrollment tracking needed for analytics

---

## Decision

### What We've Decided
**We will automatically enroll authenticated users in free courses when they click "Enroll Now", while showing payment placeholder for paid courses.**

### Rationale

**Benefits of auto-enrollment for free courses:**
- **Reduced Friction:** One click to access instead of multi-step enrollment
- **Better UX:** Users don't question why they need to "enroll" in free content
- **Higher Engagement:** Lower barrier increases course completion
- **Clear Messaging:** Distinction between free and paid is obvious

**Implementation:**
```python
# lsalms/views.py - subscribe_to_course_view
is_paid_course = course.is_subscription_based

if is_paid_course:
    # Show payment gateway placeholder
    messages.info(request, "Payment integration coming soon.")
else:
    # Auto-enroll in free course
    Enrollment.objects.get_or_create(
        student=student,
        course=course,
        defaults={'enrollment_date': timezone.now()}
    )
    messages.success(request, f"You've been enrolled in {course.title}!")

return redirect('lsalms:course_detail', course_id=course.id)
```

### Implementation Approach
1. Check `course.is_subscription_based` field
2. Free courses: Create enrollment immediately
3. Paid courses: Show payment placeholder message
4. Redirect to course detail page (not dashboard)
5. Display appropriate success message based on type

---

## Consequences

### Positive Consequences
- ✅ **Improved UX:** One-click access to free content
- ✅ **Clear Distinction:** Free vs. paid is obvious to users
- ✅ **Enrollment Tracking:** Still track who accesses free courses
- ✅ **Gateway Ready:** Placeholder for future payment integration
- ✅ **Higher Conversion:** More users will try free courses
- ✅ **Better Analytics:** Track enrollment patterns

### Negative Consequences
- ❌ **No Confirmation Step:** User enrolled without explicit confirmation
- ⚠️ **Payment Placeholder:** Paid courses not functional until gateway integrated

### Trade-offs
- **Convenience vs. confirmation:** Instant access vs. explicit consent
- **Simplicity vs. flexibility:** Auto-enroll vs. customizable enrollment flow
- **Free vs. freemium:** All-or-nothing vs. trial period options

---

## Alternatives Considered

### Alternative 1: Two Separate Buttons
**Description:** "Access Now" for free, "Purchase" for paid

**Pros:**
- Very clear distinction
- Different user expectations
- No enrollment needed for free

**Cons:**
- UI inconsistency
- Still want to track free course access
- More complex template logic

**Why rejected:** Still need enrollment tracking even for free courses. Auto-enrollment solves same problem more elegantly.

### Alternative 2: Trial Period for Paid Courses
**Description:** Auto-enroll in paid courses with 7-day trial

**Pros:**
- Increases paid course engagement
- Users try before buying
- Funnel to conversion

**Cons:**
- Complex trial logic needed
- Need to revoke access after trial
- Email reminders required
- Not requested by stakeholders

**Why rejected:** Adds complexity without clear benefit. Can revisit if needed.

### Alternative 3: Preview Mode for Free Courses
**Description:** Show first lesson without enrollment

**Pros:**
- No enrollment needed
- True "preview" experience
- Lighter data model

**Cons:**
- Don't track who previews
- Can't save progress without enrollment
- Confusing when preview ends

**Why rejected:** Lose analytics value. Enrollment is lightweight operation.

### Alternative 4: Mandatory Account Creation
**Description:** Require full profile before any enrollment

**Pros:**
- Complete user data
- Better analytics

**Cons:**
- High friction
- Users abandon signup
- Not necessary for free content

**Why rejected:** Already require authentication. Don't need more barriers.

---

## References

### Documentation
- [Enrollment Model](../database/schema-overview.md#enrollment)
- [Course Model](../components/lsalms-app.md#models)

### Discussion
- User feedback: "Why do I need to enroll in free course?"
- Analytics: 30% enrollment abandonment on free courses

### Code
- View implementation: `lsalms/views.py` lines 859-903
- Template: `lsalms/templates/academy/course_detail.html`
- Enrollment model: `lsalms/models.py` line 156

---

## Notes

### Review History
- **2026-01-07:** Issue identified - free course friction
- **2026-01-08:** Solution proposed and implemented
- **2026-01-08:** ADR accepted

### Future Considerations
- **Payment Gateway:** Paystack integration for paid courses
- **Trial Periods:** May add 7-day trial for paid courses
- **Gift Codes:** Allow enrollment via promo codes
- **Bulk Enrollment:** School admin can enroll entire class
- **Prerequisite Courses:** Enforce course sequencing

### Success Metrics
Monitor post-implementation:
- Free course enrollment rate (should increase)
- User confusion reports (should decrease)
- Time from click to course access (should decrease)
- Overall course completion rate

### Payment Gateway Integration Plan
When Paystack is integrated:
1. Replace placeholder with actual payment form
2. Verify payment before creating enrollment
3. Handle payment failures gracefully
4. Send confirmation email
5. Generate receipt

---

**Last Updated:** 2026-01-08
