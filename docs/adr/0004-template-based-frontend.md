# ADR-0004: Template-Based Frontend vs SPA Framework

## Status
**Accepted**

**Date:** 2024-12-28  
**Author:** Development Team

---

## Context

### Problem Statement
Need to decide on frontend architecture for school management system:
- Traditional server-rendered templates (Django templates)
- Single Page Application (React, Vue, Angular)
- Hybrid approach (HTMX, Alpine.js)

Requirements:
- Forms for data entry (students, grades, courses)
- Dashboard views
- Role-based navigation
- Limited JavaScript complexity
- SEO for blog content

### Current State
Django project set up with Bootstrap 5.3.2. Need to decide on rendering strategy.

### Assumptions
- Team has limited frontend JavaScript experience
- Users primarily access via desktop/laptop
- Internet connectivity may be intermittent
- Page load time acceptable (< 3 seconds)

---

## Decision

### What We've Decided
**We will use Django template-based rendering with Bootstrap 5.3.2 and minimal vanilla JavaScript, avoiding SPA frameworks.**

### Rationale

**Django Templates provide:**
- Server-side rendering with full Python access in templates
- Django template tags for logic ({% if %}, {% for %})
- Template inheritance for DRY layouts
- Built-in CSRF protection in forms
- No build step required

**Bootstrap for UI:**
- Responsive components out-of-box
- Consistent design system
- Accessibility features built-in
- No compilation needed (CDN)

**Vanilla JavaScript for:**
- Form validation enhancement
- Dynamic UI updates (show/hide elements)
- Particles.js for visual effects
- AJAX for specific features (search, filters)

### Implementation Approach
1. Base template with navigation, footer
2. App-specific templates extend base
3. Bootstrap components for forms, tables, cards
4. JavaScript in `<script>` tags or external files
5. HTMX for dynamic content where needed (limited use)

---

## Consequences

### Positive Consequences
- ✅ **Simpler Development:** No build tools, no state management, no API layer
- ✅ **Faster Initial Development:** Django forms → HTML forms directly
- ✅ **SEO Friendly:** Server-rendered content indexed by search engines
- ✅ **Lower Barrier to Entry:** Junior developers can contribute
- ✅ **Progressive Enhancement:** Works without JavaScript
- ✅ **Less Code:** No need to duplicate logic in frontend/backend

### Negative Consequences
- ❌ **Full Page Reloads:** Less snappy than SPA
- ❌ **Limited Interactivity:** Complex UI interactions harder
- ❌ **API Limitations:** No REST API for mobile app (yet)
- ⚠️ **JavaScript Spaghetti:** Risk of unorganized JS without framework

### Trade-offs
- **Simplicity vs. interactivity:** Easier development vs. rich UX
- **SEO vs. SPA benefits:** Search-friendly vs. app-like experience
- **Team skills:** Python-heavy team vs. JavaScript-heavy team

---

## Alternatives Considered

### Alternative 1: React SPA
**Description:** Build frontend as React application, Django as API backend

**Pros:**
- Rich interactive UI
- Component reusability
- Large ecosystem
- Mobile app code sharing

**Cons:**
- Requires REST API development
- Build tools complexity (Webpack, Babel)
- Steeper learning curve
- SEO requires SSR setup
- Duplicated validation logic
- State management overhead

**Why rejected:** Overkill for form-heavy CRUD application. Team doesn't have React expertise. Development would be 2-3x slower.

### Alternative 2: Vue.js SPA
**Description:** Use Vue instead of React

**Pros:**
- Easier learning curve than React
- Good documentation
- Two-way data binding

**Cons:**
- Still requires API layer
- Build tools needed
- Smaller ecosystem than React

**Why rejected:** Same fundamental issues as React. Don't need SPA complexity.

### Alternative 3: HTMX-Heavy Hybrid
**Description:** Django templates with extensive HTMX for dynamic updates

**Pros:**
- Server-side rendering
- Dynamic updates without page reload
- No build step
- Small library

**Cons:**
- Another library to learn
- Can create complex request flows
- Debugging harder than traditional forms

**Why rejected:** Good for specific use cases, but not needed throughout entire app. Can add HTMX later for specific features (search, infinite scroll).

### Alternative 4: Next.js with Django API
**Description:** Next.js for SSR React, Django for backend

**Pros:**
- SEO + SPA benefits
- React ecosystem

**Cons:**
- Two applications to deploy
- Complex architecture
- Node.js dependency
- Overkill for our needs

**Why rejected:** Massive complexity increase for marginal UX benefit.

---

## References

### Documentation
- [Django Templates](https://docs.djangoproject.com/en/5.0/topics/templates/)
- [Bootstrap 5 Docs](https://getbootstrap.com/docs/5.3/)
- [HTMX](https://htmx.org/)

### Discussion
- Team skills assessment: 2024-12-26
- Framework comparison: 2024-12-27

### Code
- Base template: `core/templates/base.html`
- Bootstrap setup: `core/templates/base.html` line 10-15

---

## Notes

### Review History
- **2024-12-26:** Initial discussion on frontend approach
- **2024-12-27:** Evaluated SPA frameworks
- **2024-12-28:** Decided on Django templates, ADR accepted

### Future Considerations
- **Mobile App:** If needed, can add Django REST Framework API
- **HTMX Addition:** Can introduce for infinite scroll, live search
- **WebSockets:** For real-time notifications (Django Channels)
- **Re-evaluation Trigger:** If > 50% of features require heavy JavaScript

### Progressive Enhancement Strategy
Core functionality works without JavaScript:
- Forms submit normally
- Navigation works
- Content accessible

JavaScript enhancements:
- Client-side validation
- Dynamic filtering
- Visual effects (particles.js)
- Smooth animations

---

**Last Updated:** 2024-12-28
