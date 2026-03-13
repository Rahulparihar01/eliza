# Technical Clarification Questions
## SOW Automation Feature

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Awaiting Answers |
| **Last Updated** | January 16, 2026 |
| **PRD Reference** | [01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md) |

---

> **Purpose:** These questions help the development agent understand requirements deeply enough to produce a complete Technical Specification. Questions are organized by the Technical Spec sections they inform.

---

## Table of Contents

1. [Architecture Questions](#1-architecture-questions)
2. [Data Model Questions](#2-data-model-questions)
3. [API Design Questions](#3-api-design-questions)
4. [Integration Points Questions](#4-integration-points-questions)
5. [Security & Permissions Questions](#5-security--permissions-questions)
6. [LLM & AI Processing Questions](#6-llm--ai-processing-questions)
7. [Error Handling Questions](#7-error-handling-questions)
8. [Performance & Scalability Questions](#8-performance--scalability-questions)
9. [Frontend UX Questions](#9-frontend-ux-questions)
10. [Migration & Deployment Questions](#10-migration--deployment-questions)

---

## 1. Architecture Questions

### 1.1 Processing Pipeline

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 1.1.1 | Should transcript extraction be **synchronous** (user waits) or **asynchronous** (background task with SSE updates)? | Determines if we use Celery tasks with real-time streaming or simpler request/response flow. Long transcripts may require async. |
| 1.1.2 | When a user adds multiple transcripts, should they be processed **sequentially** or **in parallel**? | Affects task orchestration, resource usage, and how results are merged. Parallel may be faster but more complex. |
| 1.1.3 | Should we use **CrewAI flows** for the extraction + confidence evaluation + Q&A pipeline, or simpler direct LLM calls? | CrewAI flows provide better orchestration for multi-step AI workflows but add complexity. Direct calls are simpler for straightforward extraction. |
| 1.1.4 | Is document generation (DOCX assembly) synchronous or should it also be a background task? | Large documents or complex templates may benefit from async processing. |

### 1.2 Template Processing

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 1.2.1 | What DOCX library should we use for tag replacement: **python-docx**, **docxtpl**, or another? | `docxtpl` supports Jinja2-style templating; `python-docx` is lower-level but more flexible. Need to handle complex formatting preservation. |
| 1.2.2 | How should we handle **tag format validation**? The PRD mentions `{{TAG_NAME}}` — should this be strictly enforced, and what about variations like `{{ TAG_NAME }}` (spaces) or `{{tag_name}}` (lowercase)? | Prevents template parsing failures. Need clear rules for template authors. |
| 1.2.3 | Should template parsing happen at **upload time** (validate and extract tags immediately) or at **generation time** (lazy parsing)? | Upload-time validation provides immediate feedback but may miss runtime edge cases. |
| 1.2.4 | How should we handle tags that appear **multiple times** in a template (e.g., company name in header and body)? | Need to decide: same value everywhere, or allow section-specific variants? |

### 1.3 Google Docs Integration

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 1.3.1 | For Google Docs import, should we use the **Google Docs API** to export as DOCX, or a third-party conversion service? | Direct API gives more control but requires OAuth setup; third-party may be simpler but less reliable. |
| 1.3.2 | Should Google Docs import be a **one-time conversion** or maintain a **link** for re-sync? | One-time is simpler (PRD implies this), but link allows template updates. |
| 1.3.3 | What happens to Google Docs-specific features (comments, suggestions, drawings) during conversion? | Need to define behavior: strip, convert, or error. |

---

## 2. Data Model Questions

### 2.1 Core Entities

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 2.1.1 | What is the relationship between **SOW Draft** and **customer/opportunity**? Should drafts be linked to a specific deal/customer entity? | Affects foreign keys, search/filter capabilities, and data lifecycle. |
| 2.1.2 | Should **transcripts** be stored as separate records linked to drafts, or embedded within the draft record? | Separate records allow reuse across drafts and better storage management; embedded is simpler. |
| 2.1.3 | For **field answers**, should we store the full history of changes, or just current + version snapshots? | Full history enables detailed audit trails; snapshots are simpler. |
| 2.1.4 | How should **field dependencies** be modeled? The PRD mentions "clarifying timeline may require revalidating phases." | Needs schema design: JSON adjacency list, separate mapping table, or graph structure? |

### 2.2 Versioning Model

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 2.2.1 | What triggers a new **version** — every save, only on "Generate", or explicit user action? | Affects storage requirements and user mental model of versioning. |
| 2.2.2 | Should versions store **full snapshots** of all data, or **deltas** from previous versions? | Full snapshots are simpler to retrieve but use more storage; deltas are space-efficient but complex to reconstruct. |
| 2.2.3 | Are versions **immutable** once created? Can a user "amend" a version or must they create a new one? | Affects audit requirements and data integrity constraints. |
| 2.2.4 | Should we store the **generated DOCX file** per version, or regenerate on demand? | Storing guarantees exact reproduction; regenerating saves storage but may produce slightly different output. |

### 2.3 Template Schema

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 2.3.1 | How should **field definitions** be stored? Options: JSON blob per template, normalized field table, or hybrid. | Affects query flexibility, validation logic, and schema evolution. |
| 2.3.2 | What **field types** should be supported: text only, or also: date, number, multi-select, rich text? | PRD is text-focused, but structured types enable validation and better extraction. |
| 2.3.3 | How should **field ordering** be managed for the questionnaire flow? | User-defined order, tag order in document, or intelligent ordering? |
| 2.3.4 | Should templates support **conditional fields** (show field X only if field Y = value)? | Adds complexity but may be needed for complex SOWs with optional sections. |

---

## 3. API Design Questions

### 3.1 Endpoint Structure

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 3.1.1 | Should SOW drafts be nested under a customer/opportunity resource, or be a **top-level resource**? e.g., `/api/v1/sow-drafts` vs `/api/v1/customers/{id}/sow-drafts` | Affects URL structure, permissions model, and API discoverability. |
| 3.1.2 | Should transcript upload be a **separate endpoint** or part of draft creation/update? | Separate enables upload-then-process UX; combined is simpler for single-transcript scenarios. |
| 3.1.3 | How should the **"process transcripts"** action be triggered: automatic on upload, explicit action endpoint, or configurable? | User control vs. magic behavior trade-off. |
| 3.1.4 | Should **field clarifications** be sent via the main draft update endpoint or a dedicated clarification endpoint? | Dedicated endpoint could trigger targeted re-processing; combined is simpler. |

### 3.2 Real-Time Updates

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 3.2.1 | Should we use **SSE** (Server-Sent Events), **WebSockets**, or **polling** for real-time Answer Sheet updates during extraction? | SSE is our standard pattern; WebSockets allow bidirectional; polling is simplest. |
| 3.2.2 | What events should be streamed: per-field extraction, overall progress, confidence changes, follow-up questions? | Affects frontend complexity and user experience granularity. |
| 3.2.3 | Should real-time updates be **optional** (user can refresh manually) or **required** for proper UX? | Determines if we need SSE infrastructure or can start simpler. |

### 3.3 Response Models

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 3.3.1 | Should the draft response include **full transcript content** or just **references/metadata**? | Full content bloats responses; references require additional calls for content. |
| 3.3.2 | How should **confidence scores** be represented: numeric (0-1), categorical (high/medium/low), or both? | Affects frontend display options and extraction logic interface. |
| 3.3.3 | Should generated DOCX be returned as **base64 in response** or via a **separate download endpoint**? | Download endpoint is standard for files; inline works for small docs. |

---

## 4. Integration Points Questions

### 4.1 Fathom Integration

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 4.1.1 | What **authentication method** does Fathom use: OAuth 2.0, API key, or both? | Determines connector implementation and credential storage approach. |
| 4.1.2 | What **transcript format** does Fathom export: plain text, timestamped segments, speaker-attributed, or structured JSON? | Affects parsing logic and how we preserve speaker context. |
| 4.1.3 | Does Fathom provide **call metadata** (date, participants, duration) alongside transcripts? | Useful for automatic naming and context. |
| 4.1.4 | What are Fathom's **rate limits** and pagination approach for listing/fetching calls? | Affects bulk import UX and error handling. |

### 4.2 Granola Integration

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 4.2.1 | What **authentication method** does Granola use? | Same considerations as Fathom. |
| 4.2.2 | What **transcript format** does Granola export? Is it different from Fathom? | May need format-specific parsers or normalization. |
| 4.2.3 | Does Granola support **selective export** (specific calls) or only bulk? | Affects import flow design. |

### 4.3 HubSpot Integration

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 4.3.1 | Which HubSpot objects are **in-scope for V1**: Company, Deal, Contact, or all three? | Affects API integration scope and field mapping complexity. |
| 4.3.2 | What **specific fields** from HubSpot should map to SOW template fields? | Need explicit mapping rules: e.g., `deal.name` → `{{CLIENT_NAME}}`. |
| 4.3.3 | Should HubSpot data be **snapshotted** at draft creation or **refreshed** on demand? | Snapshot is simpler; refresh handles updates but adds complexity. |
| 4.3.4 | How should we handle HubSpot **custom properties** that vary by customer? | May need configurable field mapping per tenant. |

### 4.4 Existing Eliza Systems

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 4.4.1 | Should SOW drafts integrate with **existing Eliza chat** for conversational Q&A, or use a **dedicated SOW chat**? | Reuse provides consistency; dedicated allows optimized UX. |
| 4.4.2 | Should generated SOWs be **indexed for search** in Eliza's document search? | Enables finding past SOWs but may not fit typical document search use case. |
| 4.4.3 | Is there an existing **customer/opportunity data model** in Eliza that SOW drafts should reference? | Affects foreign key design and data consistency. |

---

## 5. Security & Permissions Questions

### 5.1 RBAC Model

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 5.1.1 | What **permission resources** should we create: `sow:read`, `sow:write`, `sow-templates:admin`, `sow:review`? | Defines the permission model and integration with existing RBAC. |
| 5.1.2 | Can a user **see drafts created by others** on their team, or only their own? | Affects visibility rules and query filters. |
| 5.1.3 | Should **template access** be global (all templates visible to all users) or permission-gated per template? | Some templates may be team-specific or experimental. |
| 5.1.4 | Who can **request a review**: any draft creator, or requires specific permission? | May want to limit review requests to reduce noise for reviewers. |

### 5.2 Data Security

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 5.2.1 | Transcripts may contain **sensitive customer information**. Are there specific data retention or encryption requirements? | May require encryption at rest, PII handling policies. |
| 5.2.2 | Should **connector credentials** (Fathom, Granola, HubSpot tokens) be stored per-user or per-tenant? | Affects credential management and who can use integrations. |
| 5.2.3 | Should there be an **audit log** of who accessed/modified each SOW draft? | Compliance requirement for some organizations. |
| 5.2.4 | Can exported DOCX files be **watermarked** or tagged with metadata for traceability? | Helps track document provenance if shared externally. |

### 5.3 Multi-Tenancy

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 5.3.1 | Is SOW Automation a **tenant-level feature** (enabled/disabled per customer)? | May need feature flags or license checks. |
| 5.3.2 | Can templates be **shared across tenants** (global templates) or are they always tenant-specific? | Global templates could be platform defaults; tenant-specific for customization. |

---

## 6. LLM & AI Processing Questions

### 6.1 Confidence Scoring

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 6.1.1 | How should **confidence** be computed: purely from LLM output (self-reported), rule-based heuristics, or a combination? | LLM self-reporting may be unreliable; rules add engineering effort but more control. |
| 6.1.2 | What **confidence threshold** determines auto-fill vs. ask follow-up? (e.g., >0.8 = auto-fill, 0.5-0.8 = suggest, <0.5 = ask) | Directly affects UX balance between automation and human oversight. |
| 6.1.3 | Should confidence be **per-field** or **per-extraction-source**? | Per-field is more granular; per-source helps when transcripts conflict. |
| 6.1.4 | How do we handle **conflicting information** across transcripts: lowest confidence wins, most recent wins, or always ask? | Critical for multi-transcript scenarios. |

### 6.2 Extraction Approach

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 6.2.1 | Should extraction use **structured output** (JSON mode) or **free-form with parsing**? | Structured output is more reliable but may limit flexibility. |
| 6.2.2 | Should we extract all fields in **one LLM call** or **per-field calls**? | One call is faster/cheaper but may hit token limits; per-field is more controlled but expensive. |
| 6.2.3 | How should we handle **very long transcripts** that exceed context window: chunking with overlap, summarization first, or iterative extraction? | Directly affects accuracy and cost. The PRD asks for this to be defined. |
| 6.2.4 | Should extracted text be **verbatim quotes** from transcripts or **synthesized summaries**? | Verbatim preserves traceability; synthesized may be more readable. |

### 6.3 Follow-Up Question Generation

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 6.3.1 | Should follow-up questions be **pre-defined per field** or **dynamically generated** by the LLM? | Pre-defined is predictable; dynamic may be more contextually relevant. |
| 6.3.2 | How should follow-up questions handle **context** from partial extraction (what we already know)? | Better context = better questions, but increases complexity. |
| 6.3.3 | Should the system ask **all missing fields at once** or **one at a time** (conversational flow)? | All at once is faster; one at a time feels more conversational. |

### 6.4 Field Clarification

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 6.4.1 | When a user provides a natural-language clarification, should the LLM **rewrite the field value** or **append** the clarification? | Rewrite produces cleaner output; append preserves original + modification. |
| 6.4.2 | How do we prevent clarifications from **inadvertently changing other fields**? | Need guardrails or explicit scoping in prompts. |
| 6.4.3 | Should clarification trigger **re-validation of dependent fields**? | The PRD mentions this possibility; need clear dependency model. |

---

## 7. Error Handling Questions

### 7.1 Extraction Errors

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 7.1.1 | What should happen if **transcript extraction fails** (LLM error, timeout)? | Options: retry, partial results, full failure with user notification. |
| 7.1.2 | Should **partial extraction** be accepted (some fields extracted, others failed) or should it be all-or-nothing? | Partial is more forgiving; all-or-nothing is simpler to reason about. |
| 7.1.3 | How should we handle **malformed transcripts** (e.g., encoding issues, binary content)? | Need validation and clear error messages. |

### 7.2 Integration Errors

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 7.2.1 | What happens if **Fathom/Granola/HubSpot API** is down or rate-limited during import? | Need graceful degradation, retry logic, and user feedback. |
| 7.2.2 | How should we handle **expired OAuth tokens**: automatic refresh, prompt re-auth, or fail? | Automatic refresh is best UX; prompt may be needed for user consent. |
| 7.2.3 | What if **HubSpot record linked to a draft is deleted** in HubSpot? | Snapshot vs. sync affects behavior; need clear user message. |

### 7.3 Generation Errors

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 7.3.1 | What if a **required field is empty** at generation time: block generation or generate with placeholder? | Block is safer; placeholder may be acceptable for drafts. |
| 7.3.2 | What if the **template has been modified** since the draft was created? | Options: use original template, use updated template, or warn user. |
| 7.3.3 | How should we handle **DOCX generation failures** (library error, malformed template)? | Need informative error messages; may need template validation tooling. |

---

## 8. Performance & Scalability Questions

### 8.1 Processing Time

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 8.1.1 | What is the **target extraction time** for a single transcript (e.g., <30 seconds, <2 minutes)? | Sets performance requirements and architecture decisions. |
| 8.1.2 | What is the **maximum transcript length** we should support? | Affects chunking strategy and processing cost. The PRD asks for this to be defined. |
| 8.1.3 | Should there be **concurrent processing limits** per user or per tenant? | Prevents resource exhaustion and ensures fair usage. |

### 8.2 Storage

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 8.2.1 | How long should **transcripts** be retained: indefinitely, until draft is deleted, or time-limited? | Affects storage costs and compliance. |
| 8.2.2 | How long should **old versions** be retained? | Similar considerations plus potential regulatory requirements. |
| 8.2.3 | Should **generated DOCX files** be stored in blob storage (S3) or in the database? | Blob storage is standard for files; affects retrieval patterns. |

### 8.3 Caching

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 8.3.1 | Should **template parsing results** be cached? | Avoids re-parsing same template; invalidation on template update. |
| 8.3.2 | Should **HubSpot data** be cached, and for how long? | Reduces API calls; stale data risk. |

---

## 9. Frontend UX Questions

### 9.1 Answer Sheet Panel

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 9.1.1 | Should the Answer Sheet be a **persistent sidebar**, **modal**, or **tabbed view**? | Affects layout and user interaction patterns. |
| 9.1.2 | Should fields be **grouped** (e.g., by category: "Customer Info", "Scope", "Timeline") or **flat list**? | Grouping aids comprehension for many fields; flat is simpler. |
| 9.1.3 | How should **field status** be visualized: icons, colors, badges, or text labels? | Affects scannability and accessibility. |
| 9.1.4 | Should users be able to **collapse/expand** sections or field details? | Helps manage complexity for large templates. |

### 9.2 Conversational Interface

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 9.2.1 | Is the conversational interface a **full chat** (like existing Eliza chat) or a **simplified Q&A flow**? | Full chat is more flexible; Q&A is more guided. |
| 9.2.2 | Should **follow-up questions** appear in the chat or as **inline prompts** on specific fields? | Chat feels conversational; inline is more direct. |
| 9.2.3 | Can users **skip** follow-up questions and leave fields empty? | Allows faster drafting; may produce incomplete SOWs. |

### 9.3 Template Management UI

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 9.3.1 | Should template field definition have a **visual editor** or be **YAML/JSON configuration**? | Visual is more accessible; config is more powerful for advanced users. |
| 9.3.2 | Should there be a **template preview** showing how tags will be replaced? | Helps template authors validate their work. |
| 9.3.3 | Should templates support **test data** for preview? | Enables more realistic previews. |

---

## 10. Migration & Deployment Questions

### 10.1 Feature Rollout

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 10.1.1 | Is SOW Automation a **separate product** or a **feature within an existing product area**? | Affects navigation, permissions, and pricing considerations. |
| 10.1.2 | Should there be a **feature flag** to enable/disable per tenant during rollout? | Allows phased rollout and quick disable if issues arise. |
| 10.1.3 | What is the **MVP scope** if we need to phase the implementation? | Helps prioritize if full scope is too large. |

### 10.2 Data Migration

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 10.2.1 | Are there **existing SOW documents** that need to be imported or migrated? | May need import tooling. |
| 10.2.2 | Should we provide **sample templates** out of the box? | Accelerates adoption; requires template authoring. |

### 10.3 Dependencies

| # | Question | Context/Why This Matters |
|---|----------|--------------------------|
| 10.3.1 | What **new Python dependencies** are needed (DOCX processing, Google Docs API)? | Affects requirements.txt and Docker image. |
| 10.3.2 | Are there any **frontend library additions** needed (rich text editor, specific UI components)? | Affects package.json and bundle size. |

---

## Summary: Priority Questions

The following questions are **highest priority** to answer before beginning the Technical Specification:

### Must Answer (Blocking)

| # | Question | Why Critical |
|---|----------|--------------|
| 1.1.1 | Sync vs async transcript processing | Fundamentally shapes architecture |
| 2.1.1 | Draft-to-customer relationship | Defines core data model |
| 2.2.1 | What triggers a new version | Core UX decision |
| 4.1.1-4.2.2 | Fathom/Granola auth and format | Required for connector design |
| 4.3.1-4.3.2 | HubSpot objects and field mapping | Required for integration design |
| 6.1.2 | Confidence threshold for auto-fill | Core to the feature's value prop |
| 6.2.3 | Long transcript handling strategy | Required per PRD |
| 8.1.2 | Maximum transcript length | Directly affects 6.2.3 |

### Should Answer (Important)

| # | Question | Why Important |
|---|----------|---------------|
| 1.2.1 | DOCX library choice | Affects implementation details |
| 3.2.1 | Real-time update mechanism | Affects UX and infrastructure |
| 5.1.1 | Permission model | Security foundation |
| 6.3.1 | Pre-defined vs dynamic follow-ups | UX and complexity trade-off |
| 9.1.1 | Answer Sheet layout | Major UX decision |

### Can Defer (Nice to Know)

| # | Question | Why Deferrable |
|---|----------|----------------|
| 1.3.x | Google Docs specifics | Can start with DOCX-only |
| 9.3.x | Template management UI details | Can use minimal UI initially |
| 10.2.x | Migration questions | Only needed if existing data |

---

## How to Use This Document

1. **Product Owner / Stakeholder**: Review questions and provide answers in the "Resolution" column (to be added).
2. **Engineering Lead**: Use answered questions to complete the Technical Specification.
3. **Questions without answers**: Mark as "TBD" in tech spec and note as risks.

---

*This document was generated to facilitate the PRD → Technical Spec transition per the Eliza Platform feature development workflow.*
