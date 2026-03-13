# PRD Prompting Template

## Instructions for the User

Answer the questions below as thoroughly as you can, but **don't worry if some answers are incomplete, uncertain, or missing entirely.** Partial answers are expected and acceptable — the more context you provide, the more accurate the output will be, but thin answers are a valid starting point.

For any gaps, the model will make reasonable inferences based on what you have provided and will clearly flag those inferences as assumptions within the generated PRD so you can review and correct them. If a question doesn't apply to your feature yet, you can leave it blank or write "TBD."

---

## Instructions for the Model

Use the user's responses below to generate a complete PRD using the standard template structure provided below the questions and user answers. Where the user has provided sufficient detail, reflect it accurately. Where the user's input is thin, partial, or absent, do the following:

- **Extrapolate reasonably** from the context provided elsewhere in the response. Use domain knowledge and common patterns to fill gaps where they are clearly implied.
- **Flag all inferences and assumptions** inline within the PRD using a callout such as `> ⚠️ Assumption: [what was assumed and why]` so the product owner can review and correct them.
- **Raise unresolved gaps as Open Questions** when something is genuinely unknowable from the input — particularly if it represents a blocking decision for design or engineering.
- Do not silently invent specifics that materially affect scope or architecture without flagging them.
- **Question 7 (User Stories):** If the user has not provided stories, generate them from the target users and feature description provided in questions 1 and 6.
- **Question 8 (User Flows):** If flows have not been defined, propose them based on the user's inputs and flag each as a draft for review.
- **Question 11 (Acceptance Criteria):** If the user has described a desired end state in plain language rather than testable criteria, translate that into specific, verifiable conditions.

---

## Questions

1. **Feature overview** — Describe what this feature does and why it matters. What capability does it add or improve for users of the existing system?

2. **Current-state challenges** — What specific problems exist today that this feature directly addresses? For each challenge, note its impact on users or the business. Focus on first-order, direct pain points only.

3. **The opportunity** — What value does solving these problems create? Quantify if possible (e.g., time saved, error reduction, revenue impact).

4. **Goals and priorities** — List the goals for this feature and assign each a priority: P0 (must-have for launch), P1 (high value but not blocking), or P2 (nice-to-have for a future iteration). If you're unsure of priorities, list the goals and the model will take a reasonable pass at prioritization and flag it as an assumption.

5. **Out of scope** — What will this feature explicitly *not* do or interact with? What problems is it not solving? For each item, briefly note why it's excluded.

6. **Target users** — Who are the primary users of this feature? Describe their role, what they need, and how they'll use it. Note any secondary stakeholders who benefit indirectly.

7. **User stories** — For each user type, provide one or more stories in this format: *"As a [user type], I want to [action] so that [benefit]."* Group related stories under an epic name if applicable.

8. **Feature and user flow details** — Describe how the feature works step by step. Include any UI/UX considerations or constraints. If multiple features are involved, address each separately.

9. **Technical requirements** — What are the known technical constraints? Is this a standalone feature or integrated into an existing platform? Note data, performance, security, or integration requirements.

10. **Dependencies** — List anything this feature relies on that isn't yet in place — internal systems, teams, or external APIs and services. Note the status of each (ready, in progress, blocked).

11. **Acceptance criteria** — What specific, testable conditions must be true for this feature to be considered complete? These should be verifiable by QA or engineering.

12. **Success metrics** — How will you know this feature is working? List measurable targets and how each will be tracked.

13. **Open questions** — What is still unresolved that needs an answer before or during development?

14. **Supporting materials** — Are wireframes, mockups, or research references available? If not, should they be produced as part of this work?


# Product Requirements Document Template

## [Feature Name]


| **Document Version** | 1.0                          |
| -------------------- | ---------------------------- |
| **Status**           | Draft / In Review / Approved |
| **Last Updated**     | [Date]                       |
| **Product Owner**    | [Name]                       |
| **Engineering Lead** | [Name]                       |


---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Goals and Non-Goals](#goals-and-non-goals)
4. [Target Users](#target-users)
5. [User Stories](#user-stories)
6. [Feature Details](#feature-details)
7. [Technical Requirements](#technical-requirements)
8. [Dependencies](#dependencies)
9. [Acceptance Criteria](#acceptance-criteria)
10. [Success Metrics](#success-metrics)
11. [Open Questions](#open-questions)
12. [Appendix](#appendix)

---

## Executive Summary

[2-3 sentences describing what this feature does and why it matters to the business]

---

## Problem Statement

### Current State Challenges

[What problems exist today? Be specific about pain points and their impact]


| Challenge     | Impact            |
| ------------- | ----------------- |
| [Challenge 1] | [Business impact] |
| [Challenge 2] | [Business impact] |


### The Opportunity

[What value does solving this create? Quantify if possible]

---

## Goals and Non-Goals

### Goals (P0/P1/P2)


| Priority | Goal                                        |
| -------- | ------------------------------------------- |
| **P0**   | [Must have for MVP - critical for launch]   |
| **P0**   | [Must have for MVP]                         |
| **P1**   | [Should have - high value but not blocking] |
| **P2**   | [Nice to have - future enhancement]         |


### Non-Goals (Out of Scope)


| Item        | Rationale                           |
| ----------- | ----------------------------------- |
| [Feature X] | [Why it's excluded from this scope] |
| [Feature Y] | [Why it's excluded from this scope] |


---

## Target Users

### Primary Users

#### User Type 1: [Role Name]

- **Who they are:** [Description]
- **What they need:** [Key needs]
- **How they'll use this:** [Usage pattern]

#### User Type 2: [Role Name]

- **Who they are:** [Description]
- **What they need:** [Key needs]
- **How they'll use this:** [Usage pattern]

### Secondary Users

[Other stakeholders who benefit indirectly]

---

## User Stories

### Epic: [Epic Name]

**US-001:** As a [user type], I want to [action] so that [benefit].

**US-002:** As a [user type], I want to [action] so that [benefit].

**US-003:** As a [user type], I want to [action] so that [benefit].

### Epic: [Epic Name]

**US-004:** As a [user type], I want to [action] so that [benefit].

---

## Feature Details

### Feature 1: [Feature Name]

[Detailed description of the feature]

**User Flow:**

1. User does X
2. System responds with Y
3. User sees Z

**UI/UX Considerations:**

- [Design requirement 1]
- [Design requirement 2]

### Feature 2: [Feature Name]

[Detailed description]

---

## Technical Requirements (High-Level)

[Any known technical constraints or requirements - detailed specs go in Technical Spec]

- **Data Requirements:** [What data is needed]
- **Integration Requirements:** [Systems to integrate with]
- **Performance Requirements:** [Response times, throughput]
- **Security Requirements:** [Auth, data protection]

---

## Dependencies

### Internal Dependencies


| Dependency         | Status                      | Owner         |
| ------------------ | --------------------------- | ------------- |
| [Feature/System X] | [Ready/In Progress/Blocked] | [Team/Person] |


### External Dependencies


| Dependency      | Status              | Notes                |
| --------------- | ------------------- | -------------------- |
| [API/Service X] | [Available/Pending] | [Any relevant notes] |


---

## Acceptance Criteria

### Feature 1: [Feature Name]

- [Specific, testable criterion 1]
- [Specific, testable criterion 2]
- [Specific, testable criterion 3]

### Feature 2: [Feature Name]

- [Specific, testable criterion 1]
- [Specific, testable criterion 2]

---

## Success Metrics


| Metric        | Target         | How to Measure       |
| ------------- | -------------- | -------------------- |
| [Metric name] | [Target value] | [Measurement method] |
| [Metric name] | [Target value] | [Measurement method] |


---

## Open Questions

- [Question 1 that needs resolution before/during development]
- [Question 2]
- [Question 3]

---

## Appendix

### Mockups / Wireframes

[Links or embedded images of UI designs]

### Research / References

[Links to relevant research, competitor analysis, etc.]

### Glossary


| Term     | Definition   |
| -------- | ------------ |
| [Term 1] | [Definition] |


