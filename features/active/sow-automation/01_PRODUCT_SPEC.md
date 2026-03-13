# Product Requirements Document
## SOW Automation: Transcript-Assisted Statement of Work Generator

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Draft |
| **Last Updated** | January 16, 2026 |
| **Product Owner** | TBD |
| **Engineering Lead** | TBD |

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Goals and Non-Goals](#goals-and-non-goals)
4. [Target Users](#target-users)
5. [Key Features](#key-features)
6. [User Stories and Flows](#user-stories-and-flows)
7. [Technical Alignment](#technical-alignment)
8. [Dependencies and Edge Cases](#dependencies-and-edge-cases)
9. [Acceptance Criteria](#acceptance-criteria)
10. [Open Questions](#open-questions)

---

## Executive Summary

SOW Automation is an in-app assistant that helps Sales and Solutions/Pre-Sales teams rapidly generate an **early-stage Statement of Work (SOW)** from customer call transcripts plus lightweight user input. The feature uses a **DOCX template with tagged variables** and deterministically inserts finalized answers into the correct locations, producing a versioned SOW draft that can be exported.

The system prioritizes **speed + accuracy + control**:
- It **auto-fills only when confident** (from transcripts),
- It asks **follow-up questions** to resolve gaps,
- It keeps the user in control with **always-visible template questions + current answers** and per-field clarification.

---

## Problem Statement

Today, drafting an SOW early in the sales cycle often requires Delivery team involvement to interpret discovery calls and translate them into a document. This creates a bottleneck and slows down momentum with prospective customers.

Sales and Solutions teams need a way to:
- Convert multiple early calls into a credible, outcome-oriented SOW draft quickly,
- Reduce reliance on Delivery for first-pass SOW creation,
- Still allow Delivery to optionally review high-risk or complex drafts.

---

## Goals and Non-Goals

### Goals
- Generate a **high-quality early-stage SOW** focused on goals/outcomes, scope boundaries, assumptions, and a high-level timeline.
- Support **DOCX template upload** (plus Google Docs import/conversion into DOCX).
- Provide a **conversational questionnaire UX** backed by a hidden structured schema.
- **Auto-fill from pasted/uploaded transcripts** when confident; otherwise ask follow-ups to reach confidence.
- Enable users to **review, edit, and refine** any answer, including via **natural-language clarifications** on a specific field.
- Save **versioned SOW drafts** in the application and allow **DOCX export**.
- Support **optional Delivery review** as a workflow step.

### Non-Goals (V1)
- Acting as a full document management system (long-term archival, complex sharing, permissions inheritance, e-signature).
- Perfect granular delivery task breakdowns; V1 is explicitly **outcome-oriented** and intentionally higher-level.
- Supporting every call-recording/transcript vendor and every CRM in V1 (V1 targets Fathom, Granola, HubSpot).

---

## Target Users

### Primary Users

#### Sales / Solutions / Pre-Sales Teams
- **Role**: Account Executives, Solutions Architects, Pre-Sales Engineers
- **Primary Needs**: 
  - Quickly generate SOW drafts from discovery call transcripts
  - Maintain momentum with prospects
  - Reduce dependency on Delivery team
- **Usage Frequency**: Per-opportunity (multiple times per month)

#### SOW Automation Product Owner (Template Admin)
- **Role**: Technical Delivery lead responsible for template management
- **Primary Needs**:
  - Define and maintain DOCX templates with tagged variables
  - Configure field definitions and required/optional fields
  - Publish approved templates to the organization
- **Usage Frequency**: Periodic (template updates)

### Secondary Users

#### Delivery Reviewers
- **Role**: Delivery leads, Solution Architects reviewing SOWs
- **Primary Needs**:
  - Review flagged or complex SOW drafts
  - Recommend field-level edits
  - Mark versions as "reviewed"
- **Usage Frequency**: As requested by Sales/Solutions

---

## Key Features

### 1) Template Management (DOCX + Google Docs import)
- Upload a **DOCX template** containing tagged variables (e.g., `{{PROJECT_GOALS}}`).
- Import a **Google Doc** template by converting it into DOCX for tag-based insertion.
- The template owner can:
  - Define each variable/tag,
  - Provide an internal "field definition" and user-facing guidance,
  - Maintain an approved set of templates for the organization.

**Design principle:** The LLM does *not* decide where content goes. Placement is deterministic: **tag → field → insertion location**.

### 2) Conversational Questionnaire + "Answer Sheet" Side Panel
- The main interaction is a conversational UI that asks straightforward questions.
- A persistent "Answer Sheet" panel shows:
  - All template fields/questions,
  - Current answer values,
  - Answer status (e.g., *confirmed*, *needs review*, *missing*),
  - Source indicator (e.g., *from transcript* vs *user provided*).
- The panel updates live as the system extracts information or the user clarifies.

### 3) Inputs: Transcripts + Customer Context (manual + connectors)
- **Manual transcripts (V1):** user can add one or more transcripts by pasting or uploading transcript text.
- Each transcript requires a **human-friendly name** (e.g., "Discovery Call #2 — Security & Timeline") to provide context.
- **Connected transcripts (V1):** user can import selected call transcripts via connectors for **Fathom** and **Granola**.
- **CRM context (V1):** user can connect/select a **HubSpot** record (e.g., Company/Deal) to prefill known customer metadata used in the SOW.
- All inputs are associated to an SOW Draft and used for extraction, traceability, and optional review.

### 4) Confidence-Gated Autofill + Follow-Up Questions
- The system attempts to populate fields from transcripts.
- It **only auto-fills when confident**.
- For uncertain or missing fields, the system asks follow-up questions to reach a confident value.
- Users can always override or edit.

### 5) Field-Level Clarifications (Natural Language Refinement)
- On any pre-filled (or user-filled) field, the user can add a natural-language clarification.
- The system refines **only that field's** answer (plus any explicitly dependent fields, if defined), and updates the Answer Sheet.

### 6) Generate + Version + Export
- Users generate a DOCX draft using the template and finalized answers.
- Each generation creates a **new version** of the SOW Draft (e.g., v1, v2, …).
- Users can export any version as DOCX.

### 7) Optional Delivery Review
- A draft can be optionally sent for Delivery review.
- Delivery reviewers can:
  - Comment/flag fields for revision,
  - Recommend edits (field-level),
  - Approve a version as "reviewed".

---

## User Stories and Flows

### Flow A: Create early-stage SOW (Sales/Solutions)
1. User starts a new SOW Draft.
2. User selects a template (or requests one) and adds customer/opportunity basics.
3. User pastes/uploads transcripts (one or more), naming each.
4. System auto-fills high-confidence fields and displays them in the Answer Sheet.
5. System asks follow-ups to complete missing/uncertain fields.
6. User reviews Answer Sheet, adds clarifications on any field.
7. User generates SOW → system produces DOCX draft and saves version.
8. User exports DOCX to share externally.

### Flow B: Optional Delivery review
1. Sales/Solutions marks a draft "Request review."
2. Delivery reviewer opens the draft, reviews Answer Sheet + generated DOCX preview.
3. Reviewer flags specific fields or adds comments.
4. Sales/Solutions updates responses and regenerates a new version.
5. Reviewer optionally marks a version "Reviewed."

### Flow C: Template setup (SOW Automation Product Owner)
1. Product Owner uploads DOCX (or imports Google Doc → converted to DOCX).
2. Product Owner defines tags/variables and corresponding field definitions.
3. Product Owner configures which fields are required for "Generate" vs optional.
4. Template is published to permitted teams.

---

## Technical Alignment

- Implemented as a new product feature using Eliza's standard patterns:
  - REST API endpoints for CRUD + actions,
  - Background processing for transcript extraction, confidence evaluation, Q&A refinement, and doc assembly,
  - Optional real-time updates to keep the Answer Sheet synchronized during extraction and follow-ups,
  - RBAC permissions to separate generation, template administration, and review roles.
- Multi-tenant behavior: all SOW drafts, templates, and transcripts are scoped to the correct tenant/customer context.

---

## Dependencies and Edge Cases

### Dependencies
- DOCX templating capability for tagged variable replacement.
- Google Docs import/conversion path that results in a DOCX compatible with tagging.
- A structured field schema for each template, including required/optional fields and dependencies.
- Storage of SOW Drafts + Versions + attached transcript text.
- Connector framework support for authenticated access to **Fathom**, **Granola**, and **HubSpot** APIs.
- Secure storage of connector credentials/tokens and auditable access controls per workspace/account.
- Mapping rules from HubSpot objects (e.g., Company/Deal/Contact fields) into the SOW Draft's structured fields.

### Edge Cases
- Conflicting information across transcripts (e.g., timeline differs between calls).
  - Expected behavior: mark field as needing review and ask a targeted follow-up.
- Templates missing tags or containing unknown tags.
  - Expected behavior: validation error during template publishing; generation blocked until resolved.
- Users clarifying a field in a way that contradicts transcript-derived content.
  - Expected behavior: accept user clarification, mark source as user-provided, optionally retain traceability to transcript excerpts.
- Very long transcripts.
  - Expected behavior: system processes incrementally and updates the Answer Sheet as extraction completes.
- Connector auth expiry/revocation; partial imports; rate limits; and mismatched transcript formats across vendors.
- Conflicts between manual transcript edits and imported transcripts (source-of-truth rules).
- HubSpot record changes after an SOW Draft is created (sync vs snapshot behavior).

---

## Acceptance Criteria

### Template Management
- A Product Owner can upload a DOCX template, define tags/fields, and publish it.
- A Product Owner can import a Google Doc template and it becomes a DOCX template usable by the system.
- The system validates that all required tags are defined and mapped before publishing.

### Integrations (Fathom, Granola, HubSpot)
- An admin can connect Fathom, Granola, and HubSpot for a workspace/account (subject to RBAC).
- A user can import one or more transcripts from Fathom/Granola into an SOW Draft, providing or inheriting call names.
- A user can link a HubSpot record (e.g., Company/Deal) and auto-populate available customer metadata fields.
- The system handles token expiry and error states gracefully, offering retry and falling back to manual paste/upload.

### SOW Draft Creation + Transcript Handling
- A Sales/Solutions user can create an SOW Draft and attach multiple transcripts, each with a required name.
- The system extracts candidate answers from transcripts and **only commits auto-filled answers when confident**.
- For low-confidence fields, the system asks follow-up questions and updates answers only after confidence is achieved.

### UX: Continuous Visibility + Field Clarification
- The user can see the full list of SOW fields/questions and current answers throughout the experience.
- The user can edit any field directly or add a natural-language clarification to refine it.
- Clarifications update the target field without rewriting unrelated fields.

### Generation + Versioning + Export
- The user can generate a DOCX SOW draft with deterministic insertion into template tags.
- Each generation creates a new version stored in-app.
- The user can export any version as DOCX.

### Optional Review
- A Sales/Solutions user can request Delivery review.
- A Delivery reviewer can view the draft, flag fields, and mark a version as reviewed.

---

## Open Questions

### Outstanding Product Decisions
None.

### Open Engineering Questions
- **OPEN ENGINEERING QUESTION:** Define the tag/variable format and validation rules for DOCX templates (including how tags are represented in the document to minimize formatting issues).
- **OPEN ENGINEERING QUESTION:** Define the confidence thresholding approach (e.g., numeric thresholds, rule-based + model-based signals) and how "certainty" is computed consistently.
- **OPEN ENGINEERING QUESTION:** Define the data model for field dependencies (e.g., clarifying "timeline" may require revalidating "phases").
- **OPEN ENGINEERING QUESTION:** Define transcript size limits and the strategy for chunking/processing while preserving correct extraction and traceability.
- Fathom / Granola: preferred auth methods, transcript export formats, pagination/rate limits, and how to map call metadata.
- HubSpot: which objects are in-scope (Company/Deal/Contact), required fields, and expected sync semantics (snapshot vs live refresh).
- Connector credential storage + audit requirements, including tenant isolation and token rotation.

### Future Enhancements
- Additional transcript/call sources beyond Fathom/Granola (e.g., Zoom, Teams, Gong) and richer meeting metadata.
- Deeper HubSpot bidirectional sync (attach exported SOW back to the deal; stage-based automation).
- Template governance features (approval, rollout, A/B templates, sandbox vs production).
- PDF export option and richer proposal packaging (optional).

---

*This document is a living artifact and will be updated as product decisions are made and engineering questions are resolved.*
