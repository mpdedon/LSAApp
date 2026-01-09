# ADR-0005: Cyberpunk Design System

## Status
**Accepted**

**Date:** 2026-01-05  
**Author:** Development Team

---

## Context

### Problem Statement
The application had a basic Bootstrap design that looked generic and uninspiring. Need to modernize UI to:
- Stand out from typical school management systems
- Appeal to tech-savvy students and teachers
- Create modern, engaging user experience
- Maintain professionalism and readability

Requirements:
- Modern, visually appealing design
- Consistent color scheme and typography
- Responsive across devices
- Accessibility maintained
- Not overwhelming for older users

### Current State
- Bootstrap 5.3.2 with default theme
- Minimal custom CSS
- Standard blue/white color scheme
- Generic appearance

### Assumptions
- Users have modern browsers (Chrome, Firefox, Edge, Safari)
- Target audience appreciates modern design
- Performance impact of visual effects acceptable
- Design can evolve iteratively

---

## Decision

### What We've Decided
**We will implement a cyberpunk-inspired design system with glassmorphism, neon gradients, and particle effects while maintaining usability and accessibility.**

### Rationale

**Design Philosophy:**
- **Cyberpunk aesthetic:** Neon colors, dark backgrounds, futuristic feel
- **Glassmorphism:** Translucent cards with backdrop blur
- **Particle animations:** Dynamic backgrounds for engagement
- **Gradient accents:** Color transitions on buttons and badges
- **Modern typography:** Space Grotesk for headings, Inter for body

**Color Palette:**
```css
--cyan: #06b6d4;      /* Primary accent */
--purple: #8b5cf6;     /* Secondary accent */
--pink: #ec4899;       /* Tertiary accent */
--emerald: #10b981;    /* Success states */
--deep-navy: #0f172a;  /* Dark backgrounds */
```

**Key Visual Elements:**
1. **Particles.js:** Animated background with floating particles
2. **Glassmorphic Cards:** `backdrop-filter: blur(10px)` with transparency
3. **Gradient Buttons:** Linear gradients on hover states
4. **Neon Text Effects:** Text shadows on headings
5. **Smooth Transitions:** `cubic-bezier(0.4, 0, 0.2, 1)` easing

### Implementation Approach
1. Add Particles.js via CDN for background animations
2. Create CSS custom properties for color system
3. Design glassmorphic card components
4. Implement gradient utilities for buttons/badges
5. Add Google Fonts (Space Grotesk, Inter)
6. Apply consistently across all templates

---

## Consequences

### Positive Consequences
- ✅ **Visual Differentiation:** Stands out from generic school systems
- ✅ **Modern Appeal:** Attracts tech-savvy users
- ✅ **Brand Identity:** Memorable visual style
- ✅ **User Engagement:** Visually interesting interface
- ✅ **Responsive Design:** Works across devices
- ✅ **Maintainable:** CSS custom properties for easy theme updates

### Negative Consequences
- ❌ **Performance Impact:** Particles.js adds ~50KB and CPU usage
- ❌ **Browser Support:** Backdrop-filter not supported in older browsers
- ❌ **Accessibility Concerns:** Low contrast in some areas needs monitoring
- ⚠️ **Learning Curve:** New users may need orientation to interface

### Trade-offs
- **Visual appeal vs. performance:** Accept minor performance hit for modern look
- **Uniqueness vs. familiarity:** Custom design vs. standard Bootstrap
- **Complexity vs. simplicity:** More CSS to maintain vs. generic appearance

---

## Alternatives Considered

### Alternative 1: Material Design
**Description:** Implement Google's Material Design system

**Pros:**
- Well-documented
- Familiar to users
- Strong accessibility guidelines
- Component library available

**Cons:**
- Very common (Gmail, Google Drive look)
- Less distinctive
- Heavier framework

**Why rejected:** Too generic, doesn't differentiate us from competitors.

### Alternative 2: Minimalist/Flat Design
**Description:** Clean, simple design with minimal effects

**Pros:**
- Excellent performance
- Universal appeal
- Easy to maintain
- Timeless

**Cons:**
- Generic appearance
- Less engaging
- Doesn't stand out

**Why rejected:** Wanted more visual interest and modern feel.

### Alternative 3: Neumorphism
**Description:** Soft UI design with subtle shadows

**Pros:**
- Modern look
- Soft, approachable
- Trending design style

**Cons:**
- Accessibility issues (low contrast)
- Can look dated quickly
- Heavy on shadows (performance)

**Why rejected:** Accessibility concerns and trend may fade quickly.

### Alternative 4: Keep Bootstrap Default
**Description:** Stick with out-of-box Bootstrap

**Pros:**
- No development time
- Familiar to everyone
- Battle-tested

**Cons:**
- Generic appearance
- Looks like every other Bootstrap site
- No brand identity

**Why rejected:** Doesn't meet goal of standing out and modernization.

---

## References

### Documentation
- [Glassmorphism Design Guide](https://uxdesign.cc/glassmorphism-in-user-interfaces-1f39bb1308c9)
- [Particles.js Documentation](https://github.com/VincentGarreau/particles.js/)
- [CSS backdrop-filter](https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter)

### Discussion
- Design mockups presented: 2026-01-03
- Team review: 2026-01-04
- User feedback: 2026-01-05

### Code
- Base template: `core/templates/base.html`
- Homepage implementation: `core/templates/homepage.html`
- Academy hub: `lsalms/templates/academy/hub.html`
- Blog: `core/templates/blog/post_list.html`

---

## Notes

### Review History
- **2026-01-03:** Initial cyberpunk design proposed
- **2026-01-04:** Prototype built and reviewed
- **2026-01-05:** ADR accepted, implementation begun

### Future Considerations
- **Performance Monitoring:** Track page load times with particles.js
- **Accessibility Audit:** Regular contrast checks and screen reader testing
- **User Feedback:** Survey users on design preference
- **Fallback Styles:** Provide simpler theme for older browsers
- **Dark Mode Toggle:** Consider light theme option for user preference

### Implementation Guidelines

**For new pages:**
1. Include particles.js background
2. Use glassmorphic cards with `.glass-card` class
3. Apply gradient badges with `.badge-gradient-*`
4. Use Space Grotesk (800) for headings
5. Maintain color scheme consistency

**Accessibility checklist:**
- [ ] Color contrast minimum 4.5:1
- [ ] Focus indicators visible
- [ ] Text readable with particles background
- [ ] Works with reduced motion preference
- [ ] Screen reader tested

---

**Last Updated:** 2026-01-05
