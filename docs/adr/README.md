# Architectural Decision Records (ADRs)

## Overview

This directory contains records of all significant architectural decisions made during the development of LearnSwift Academia.

## What is an ADR?

An **Architectural Decision Record** (ADR) is a document that captures an important architectural decision made along with its context and consequences.

## ADR Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| [0001](0001-use-django-framework.md) | Use Django Framework | Accepted | 2024-12-15 |
| [0002](0002-integrated-lms.md) | Integrated LMS vs Separate System | Accepted | 2024-12-20 |
| [0003](0003-multi-role-authentication.md) | Multi-Role Authentication Model | Accepted | 2024-12-22 |
| [0004](0004-template-based-frontend.md) | Template-Based Frontend | Accepted | 2024-12-28 |
| [0005](0005-cyberpunk-design-system.md) | Cyberpunk Design System | Accepted | 2026-01-05 |
| [0006](0006-free-course-auto-enrollment.md) | Free Course Auto-Enrollment | Accepted | 2026-01-08 |

---

## How to Use ADRs

### When to Create an ADR

Create an ADR when you make a decision that:
- Affects the overall architecture
- Impacts multiple components
- Has long-term consequences
- Changes a previous decision
- Requires significant effort to reverse

### When NOT to Create an ADR

Don't create an ADR for:
- Trivial implementation details
- Temporary workarounds
- Decisions that can be easily reversed
- Standard framework usage

---

## ADR Process

1. **Identify the decision** that needs to be made
2. **Copy the [template](TEMPLATE.md)**
3. **Fill in all sections** with context and rationale
4. **Number it sequentially** (next available number)
5. **Name the file** `XXXX-short-description.md`
6. **Submit for review** (PR or team discussion)
7. **Update this index** when accepted

---

## ADR Statuses

- **Proposed:** Decision is under discussion
- **Accepted:** Decision has been approved and implemented
- **Deprecated:** Decision is no longer relevant
- **Superseded:** Replaced by a newer ADR (link to new ADR)

---

## ADR Format

Each ADR follows this structure:

```markdown
# ADR-XXXX: Title

## Status
Proposed | Accepted | Deprecated | Superseded by [ADR-YYYY](YYYY-title.md)

## Context
What is the issue we're facing?

## Decision
What are we going to do about it?

## Consequences
What becomes easier or harder as a result?

## Alternatives Considered
What other options did we evaluate?
```

See [TEMPLATE.md](TEMPLATE.md) for the full template.

---

## Quick Reference

### Recent Decisions
- **Design System:** Adopted cyberpunk theme with glassmorphism (ADR-0005)
- **LMS Access:** Free courses auto-enroll authenticated users (ADR-0006)

### Key Architectural Choices
- **Framework:** Django for rapid development and batteries-included approach (ADR-0001)
- **LMS Integration:** Integrated within monolith for simplicity (ADR-0002)
- **Authentication:** Custom user model with role-based access (ADR-0003)

---

## Contributing

When proposing an ADR:
1. Start with "Proposed" status
2. Present to team for discussion
3. Incorporate feedback
4. Change to "Accepted" when approved
5. Implement the decision
6. Update this index

---

**Last Updated:** January 8, 2026
