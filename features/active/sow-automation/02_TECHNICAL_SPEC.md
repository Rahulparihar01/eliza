# Technical Specification
## SOW Automation: Transcript-Assisted Statement of Work Generator

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Draft |
| **Last Updated** | January 16, 2026 |
| **PRD Reference** | [01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md) |
| **Author** | Development Agent |

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Model](#data-model)
4. [API Design](#api-design)
5. [Integration Points](#integration-points)
6. [Security Considerations](#security-considerations)
7. [Error Handling](#error-handling)
8. [Performance Considerations](#performance-considerations)
9. [Testing Strategy](#testing-strategy)
10. [Migration Strategy](#migration-strategy)
11. [Agent Review Notes](#agent-review-notes)

---

## Overview

SOW Automation enables Sales and Solutions teams to rapidly generate early-stage Statements of Work from customer call transcripts. The system uses a **deterministic template-based approach** where LLMs extract information but placement is controlled by tagged variables in DOCX templates.

### Technical Approach Summary

The feature implements a **multi-stage AI extraction pipeline** using CrewAI flows for orchestration:

1. **Transcript Ingestion** — Accept transcripts via paste, upload, or connector import
2. **Field Extraction** — Use LLM to extract candidate values with confidence scores
3. **Confidence Gating** — Auto-fill high-confidence fields; generate follow-up questions for low-confidence
4. **Interactive Refinement** — Accept user clarifications and re-process targeted fields
5. **Document Generation** — Deterministic tag replacement in DOCX template
6. **Version Management** — Store each generation as an immutable version

### Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| **Async processing with Celery + SSE** | Long transcripts may take 30-60s to process; matches existing BI/Talent patterns |
| **CrewAI Flow for extraction pipeline** | Multi-step AI workflow with state management; proven pattern in DataAnalystFlow |
| **`docxtpl` for DOCX generation** | Jinja2-style templating is cleaner than low-level python-docx; handles complex formatting |
| **Numeric confidence (0.0-1.0) with categorical mapping** | Provides precision for tuning while offering user-friendly display |
| **Separate transcript storage** | Enables reuse, better storage management, and clear audit trail |
| **Full version snapshots** | Simpler retrieval, guarantees reproducibility; storage cost acceptable |
| **OAuth 2.0 for Fathom/Granola** | Standard pattern; enables user-level authorization |
| **HubSpot snapshot at draft creation** | Simpler than live sync; avoids data consistency issues |

---

## Architecture

### System Context

SOW Automation integrates with the existing Eliza Platform as a new product feature:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ELIZA PLATFORM                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────────────┐ │
│  │   SOW Frontend   │   │  Existing Chat   │   │   Other Products             │ │
│  │  (React + TS)    │   │    Interface     │   │   (BI, Talent, etc.)         │ │
│  └────────┬─────────┘   └──────────────────┘   └──────────────────────────────┘ │
│           │                                                                      │
│           │ HTTP/SSE                                                             │
│           ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                         FastAPI Backend                                      ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ ││
│  │  │ SOW Routes  │  │ Connector   │  │ Auth/RBAC   │  │ SSE Streaming       │ ││
│  │  │ /api/v1/sow │  │ Routes      │  │ Middleware  │  │ Endpoints           │ ││
│  │  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └─────────────────────┘ ││
│  └─────────┼────────────────┼───────────────────────────────────────────────────┘│
│            │                │                                                    │
│            ▼                ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                         Celery Workers                                       ││
│  │  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────────┐││
│  │  │ SOW Extraction    │  │ Connector Sync    │  │ Document Generation       │││
│  │  │ Task              │  │ Tasks             │  │ Task                      │││
│  │  └─────────┬─────────┘  └───────────────────┘  └───────────────────────────┘││
│  └────────────┼─────────────────────────────────────────────────────────────────┘│
│               │                                                                  │
│               ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                    CrewAI SOW Extraction Flow                                ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ ││
│  │  │  Transcript  │  │  Field       │  │  Confidence  │  │  Follow-up       │ ││
│  │  │  Parser      │→ │  Extractor   │→ │  Evaluator   │→ │  Generator       │ ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐           │
│  │                      External Integrations                        │           │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                  │           │
│  │  │  Fathom    │  │  Granola   │  │  HubSpot   │                  │           │
│  │  │ Connector  │  │ Connector  │  │ Connector  │                  │           │
│  │  └────────────┘  └────────────┘  └────────────┘                  │           │
│  └──────────────────────────────────────────────────────────────────┘           │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐           │
│  │                        Data Layer                                 │           │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                  │           │
│  │  │ PostgreSQL │  │   Redis    │  │  S3/Blob   │                  │           │
│  │  │  (Models)  │  │  (Cache)   │  │  (Files)   │                  │           │
│  │  └────────────┘  └────────────┘  └────────────┘                  │           │
│  └──────────────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SOW Automation Components                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  API Layer (src/api/)                                                        │
│  ├── routes/sow.py              # CRUD + actions for drafts, templates      │
│  ├── routes/sow_connectors.py   # Fathom/Granola/HubSpot import endpoints   │
│  └── schemas/sow.py             # Pydantic request/response models          │
│                                                                              │
│  Service Layer (src/services/)                                               │
│  ├── sow_service.py             # Draft lifecycle, versioning               │
│  ├── sow_template_service.py    # Template parsing, validation              │
│  └── sow_extraction_service.py  # LLM extraction orchestration              │
│                                                                              │
│  Flow Layer (src/flows/)                                                     │
│  └── sow_extraction_flow.py     # CrewAI flow for transcript extraction     │
│                                                                              │
│  Task Layer (src/tasks/)                                                     │
│  ├── sow_extraction_tasks.py    # Celery tasks for async processing         │
│  └── sow_generation_tasks.py    # Celery tasks for DOCX generation          │
│                                                                              │
│  Connector Layer (src/services/ingestion/connectors/)                        │
│  ├── fathom_connector.py        # Fathom transcript import                  │
│  ├── granola_connector.py       # Granola transcript import                 │
│  └── hubspot_connector.py       # HubSpot CRM data import                   │
│                                                                              │
│  Model Layer (src/models/)                                                   │
│  └── sow.py                     # SQLAlchemy models                         │
│                                                                              │
│  Frontend (frontend/src/)                                                    │
│  ├── pages/sow/                 # SOW pages                                 │
│  ├── components/sow/            # SOW-specific components                   │
│  │   ├── AnswerSheet.tsx        # Persistent field panel                    │
│  │   ├── TranscriptUploader.tsx # Upload/paste/import UI                    │
│  │   ├── SOWChat.tsx            # Conversational Q&A interface              │
│  │   └── TemplateManager.tsx    # Template admin UI                         │
│  └── hooks/useSOWStream.ts      # SSE hook for real-time updates            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

#### Flow 1: Transcript Extraction

```
1. User uploads/pastes transcript(s)
   └─→ POST /api/v1/sow/drafts/{id}/transcripts
   
2. API validates and stores transcript
   └─→ Creates SOWTranscript record
   
3. API queues extraction task
   └─→ Celery task: process_sow_transcripts.delay(draft_id)
   
4. Frontend connects to SSE stream
   └─→ GET /api/v1/sow/drafts/{id}/stream?token=...
   
5. Celery worker runs SOWExtractionFlow
   └─→ For each field in template:
       ├─→ Extract candidate value from transcripts
       ├─→ Calculate confidence score
       ├─→ Store SOWFieldAnswer record
       └─→ Emit SSE event with field update
       
6. Flow identifies low-confidence fields
   └─→ Generates follow-up questions
   └─→ Stores as pending SOWFollowUp records
   └─→ Emits SSE event with follow-up questions
   
7. SSE stream sends completion event
   └─→ Frontend updates Answer Sheet UI
```

#### Flow 2: Document Generation

```
1. User clicks "Generate SOW"
   └─→ POST /api/v1/sow/drafts/{id}/generate
   
2. API validates all required fields populated
   └─→ If missing: Return 422 with field list
   
3. API queues generation task (or runs sync for small templates)
   └─→ Celery task: generate_sow_document.delay(draft_id)
   
4. Worker loads template and field answers
   └─→ Uses docxtpl to render template
   └─→ Stores generated DOCX in blob storage
   └─→ Creates SOWVersion record
   
5. API returns version info with download URL
   └─→ GET /api/v1/sow/versions/{id}/download
```

---

## Data Model

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────────┐
│   SOWTemplate   │       │     SOWDraft        │
├─────────────────┤       ├─────────────────────┤
│ id              │       │ id                  │
│ customer_id     │◄──────┤ customer_id         │
│ name            │       │ template_id (FK)    │
│ description     │       │ name                │
│ file_path       │       │ status              │
│ schema (JSON)   │       │ opportunity_name    │
│ is_published    │       │ hubspot_deal_id     │
│ created_by      │       │ created_by          │
│ created_at      │       │ reviewer_id         │
│ updated_at      │       │ review_status       │
└────────┬────────┘       │ created_at          │
         │                │ updated_at          │
         │                └──────────┬──────────┘
         │                           │
         │                           │ 1:N
         │                           ▼
         │                ┌─────────────────────┐
         │                │   SOWTranscript     │
         │                ├─────────────────────┤
         │                │ id                  │
         │                │ draft_id (FK)       │
         │                │ name                │
         │                │ source_type         │
         │                │ source_id           │
         │                │ content             │
         │                │ metadata (JSON)     │
         │                │ created_at          │
         │                └─────────────────────┘
         │
         │ 1:N (via schema)
         ▼
┌─────────────────────┐   ┌─────────────────────┐
│  SOWTemplateField   │   │   SOWFieldAnswer    │
├─────────────────────┤   ├─────────────────────┤
│ id                  │   │ id                  │
│ template_id (FK)    │   │ draft_id (FK)       │
│ tag_name            │◄──┤ field_tag           │
│ display_name        │   │ value               │
│ description         │   │ confidence          │
│ field_type          │   │ source_type         │
│ is_required         │   │ source_excerpt      │
│ default_value       │   │ status              │
│ validation_rules    │   │ clarification       │
│ depends_on (JSON)   │   │ created_at          │
│ display_order       │   │ updated_at          │
└─────────────────────┘   └─────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
                          ┌─────────────────────┐
                          │   SOWVersion        │
                          ├─────────────────────┤
                          │ id                  │
                          │ draft_id (FK)       │
                          │ version_number      │
                          │ file_path           │
                          │ field_snapshot(JSON)│
                          │ generated_by        │
                          │ generated_at        │
                          │ is_reviewed         │
                          │ reviewer_notes      │
                          └─────────────────────┘
```

### New Tables

#### `sow_templates`

```sql
CREATE TABLE sow_templates (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL,
    
    -- Template identification
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Template file
    file_path VARCHAR(500) NOT NULL,  -- S3 path to DOCX
    file_hash VARCHAR(64),            -- SHA-256 for change detection
    
    -- Parsed schema (extracted tags and definitions)
    schema JSONB NOT NULL DEFAULT '{}',
    
    -- Status
    is_published BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    
    -- Audit
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sow_templates_customer ON sow_templates(customer_id);
CREATE INDEX idx_sow_templates_published ON sow_templates(customer_id, is_published) WHERE is_published = TRUE;
```

#### `sow_template_fields`

```sql
CREATE TABLE sow_template_fields (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES sow_templates(id) ON DELETE CASCADE,
    
    -- Field identification
    tag_name VARCHAR(100) NOT NULL,        -- e.g., "PROJECT_GOALS"
    display_name VARCHAR(255) NOT NULL,    -- e.g., "Project Goals"
    description TEXT,                      -- Internal guidance
    user_guidance TEXT,                    -- Shown to users
    
    -- Field configuration
    field_type VARCHAR(50) DEFAULT 'text', -- text, date, number, rich_text
    is_required BOOLEAN DEFAULT FALSE,
    default_value TEXT,
    
    -- Validation
    validation_rules JSONB DEFAULT '{}',   -- e.g., {"max_length": 1000}
    
    -- Dependencies
    depends_on JSONB DEFAULT '[]',         -- Array of field tags this depends on
    
    -- Display
    display_order INTEGER DEFAULT 0,
    field_group VARCHAR(100),              -- For UI grouping
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(template_id, tag_name)
);

CREATE INDEX idx_sow_template_fields_template ON sow_template_fields(template_id);
```

#### `sow_drafts`

```sql
CREATE TYPE sow_draft_status AS ENUM (
    'draft',           -- Initial state
    'extracting',      -- Transcripts being processed
    'ready',           -- Ready for generation
    'generating',      -- DOCX being generated
    'review_requested', -- Sent for Delivery review
    'reviewed',        -- Delivery has reviewed
    'archived'         -- No longer active
);

CREATE TYPE sow_review_status AS ENUM (
    'none',
    'requested',
    'in_review',
    'changes_requested',
    'approved'
);

CREATE TABLE sow_drafts (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL,
    
    -- Draft identification
    name VARCHAR(255) NOT NULL,
    opportunity_name VARCHAR(255),        -- Customer/deal name
    
    -- Template reference
    template_id INTEGER REFERENCES sow_templates(id),
    
    -- External linkage (optional)
    hubspot_company_id VARCHAR(100),
    hubspot_deal_id VARCHAR(100),
    hubspot_snapshot JSONB,               -- Snapshotted HubSpot data
    
    -- Status
    status sow_draft_status DEFAULT 'draft',
    
    -- Review workflow
    review_status sow_review_status DEFAULT 'none',
    reviewer_id INTEGER REFERENCES users(id),
    review_notes TEXT,
    
    -- Audit
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sow_drafts_customer ON sow_drafts(customer_id);
CREATE INDEX idx_sow_drafts_created_by ON sow_drafts(created_by);
CREATE INDEX idx_sow_drafts_status ON sow_drafts(customer_id, status);
```

#### `sow_transcripts`

```sql
CREATE TYPE sow_transcript_source AS ENUM (
    'manual_paste',
    'manual_upload',
    'fathom',
    'granola'
);

CREATE TABLE sow_transcripts (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER NOT NULL REFERENCES sow_drafts(id) ON DELETE CASCADE,
    
    -- Transcript identification
    name VARCHAR(255) NOT NULL,           -- User-provided name
    
    -- Source tracking
    source_type sow_transcript_source NOT NULL,
    source_id VARCHAR(255),               -- External ID (Fathom call ID, etc.)
    
    -- Content
    content TEXT NOT NULL,
    word_count INTEGER,
    
    -- Metadata from source
    metadata JSONB DEFAULT '{}',          -- Date, participants, duration, etc.
    
    -- Processing
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sow_transcripts_draft ON sow_transcripts(draft_id);
```

#### `sow_field_answers`

```sql
CREATE TYPE sow_field_status AS ENUM (
    'empty',           -- No value yet
    'auto_filled',     -- LLM extracted with high confidence
    'suggested',       -- LLM extracted with medium confidence (needs review)
    'needs_input',     -- Low confidence, follow-up asked
    'user_provided',   -- User manually entered
    'clarified',       -- User refined LLM suggestion
    'confirmed'        -- User explicitly confirmed
);

CREATE TYPE sow_answer_source AS ENUM (
    'transcript',
    'hubspot',
    'user_input',
    'clarification'
);

CREATE TABLE sow_field_answers (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER NOT NULL REFERENCES sow_drafts(id) ON DELETE CASCADE,
    
    -- Field reference
    field_tag VARCHAR(100) NOT NULL,
    
    -- Value
    value TEXT,
    
    -- Confidence (0.0 to 1.0)
    confidence DECIMAL(3, 2),
    
    -- Source tracking
    source_type sow_answer_source,
    source_transcript_id INTEGER REFERENCES sow_transcripts(id),
    source_excerpt TEXT,                  -- Relevant transcript excerpt
    
    -- Status
    status sow_field_status DEFAULT 'empty',
    
    -- User refinement
    clarification TEXT,                   -- User's clarification input
    clarification_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(draft_id, field_tag)
);

CREATE INDEX idx_sow_field_answers_draft ON sow_field_answers(draft_id);
CREATE INDEX idx_sow_field_answers_status ON sow_field_answers(draft_id, status);
```

#### `sow_versions`

```sql
CREATE TABLE sow_versions (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER NOT NULL REFERENCES sow_drafts(id) ON DELETE CASCADE,
    
    -- Version identification
    version_number INTEGER NOT NULL,
    
    -- Generated document
    file_path VARCHAR(500) NOT NULL,      -- S3 path to generated DOCX
    file_size INTEGER,                    -- Bytes
    
    -- Snapshot of field values at generation time
    field_snapshot JSONB NOT NULL,
    
    -- Review status
    is_reviewed BOOLEAN DEFAULT FALSE,
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewer_notes TEXT,
    
    -- Audit
    generated_by INTEGER NOT NULL REFERENCES users(id),
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(draft_id, version_number)
);

CREATE INDEX idx_sow_versions_draft ON sow_versions(draft_id);
```

#### `sow_extraction_events` (for SSE and audit)

```sql
CREATE TYPE sow_extraction_event_type AS ENUM (
    'extraction_started',
    'field_extracted',
    'field_confidence_low',
    'followup_generated',
    'extraction_completed',
    'extraction_failed'
);

CREATE TABLE sow_extraction_events (
    id SERIAL PRIMARY KEY,
    draft_id INTEGER NOT NULL REFERENCES sow_drafts(id) ON DELETE CASCADE,
    
    event_type sow_extraction_event_type NOT NULL,
    field_tag VARCHAR(100),
    data JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sow_extraction_events_draft ON sow_extraction_events(draft_id);
CREATE INDEX idx_sow_extraction_events_created ON sow_extraction_events(draft_id, created_at);
```

---

## API Design

### New Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| **Templates** | | | |
| POST | `/api/v1/sow/templates` | Upload new template | `sow-templates:admin` |
| GET | `/api/v1/sow/templates` | List templates | `sow:read` |
| GET | `/api/v1/sow/templates/{id}` | Get template details | `sow:read` |
| PUT | `/api/v1/sow/templates/{id}` | Update template | `sow-templates:admin` |
| DELETE | `/api/v1/sow/templates/{id}` | Archive template | `sow-templates:admin` |
| POST | `/api/v1/sow/templates/{id}/publish` | Publish template | `sow-templates:admin` |
| POST | `/api/v1/sow/templates/import-gdoc` | Import from Google Docs | `sow-templates:admin` |
| **Drafts** | | | |
| POST | `/api/v1/sow/drafts` | Create new draft | `sow:write` |
| GET | `/api/v1/sow/drafts` | List drafts | `sow:read` |
| GET | `/api/v1/sow/drafts/{id}` | Get draft details | `sow:read` |
| PUT | `/api/v1/sow/drafts/{id}` | Update draft | `sow:write` |
| DELETE | `/api/v1/sow/drafts/{id}` | Delete draft | `sow:write` |
| **Transcripts** | | | |
| POST | `/api/v1/sow/drafts/{id}/transcripts` | Add transcript | `sow:write` |
| GET | `/api/v1/sow/drafts/{id}/transcripts` | List transcripts | `sow:read` |
| DELETE | `/api/v1/sow/drafts/{id}/transcripts/{tid}` | Remove transcript | `sow:write` |
| POST | `/api/v1/sow/drafts/{id}/transcripts/import` | Import from connector | `sow:write` |
| **Processing** | | | |
| POST | `/api/v1/sow/drafts/{id}/extract` | Start extraction | `sow:write` |
| GET | `/api/v1/sow/drafts/{id}/stream` | SSE stream | `sow:read` |
| **Fields** | | | |
| GET | `/api/v1/sow/drafts/{id}/fields` | Get all field answers | `sow:read` |
| PUT | `/api/v1/sow/drafts/{id}/fields/{tag}` | Update field value | `sow:write` |
| POST | `/api/v1/sow/drafts/{id}/fields/{tag}/clarify` | Submit clarification | `sow:write` |
| **Generation** | | | |
| POST | `/api/v1/sow/drafts/{id}/generate` | Generate DOCX | `sow:write` |
| GET | `/api/v1/sow/drafts/{id}/versions` | List versions | `sow:read` |
| GET | `/api/v1/sow/versions/{id}/download` | Download DOCX | `sow:read` |
| **Review** | | | |
| POST | `/api/v1/sow/drafts/{id}/request-review` | Request Delivery review | `sow:write` |
| POST | `/api/v1/sow/drafts/{id}/submit-review` | Submit review | `sow:review` |
| **Connectors** | | | |
| GET | `/api/v1/sow/connectors/fathom/calls` | List Fathom calls | `sow:write` |
| GET | `/api/v1/sow/connectors/granola/calls` | List Granola calls | `sow:write` |
| GET | `/api/v1/sow/connectors/hubspot/deals` | List HubSpot deals | `sow:write` |
| POST | `/api/v1/sow/drafts/{id}/link-hubspot` | Link HubSpot record | `sow:write` |

### Request/Response Models

```python
# src/api/schemas/sow.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# Enums
class SOWDraftStatus(str, Enum):
    DRAFT = "draft"
    EXTRACTING = "extracting"
    READY = "ready"
    GENERATING = "generating"
    REVIEW_REQUESTED = "review_requested"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


class SOWFieldStatus(str, Enum):
    EMPTY = "empty"
    AUTO_FILLED = "auto_filled"
    SUGGESTED = "suggested"
    NEEDS_INPUT = "needs_input"
    USER_PROVIDED = "user_provided"
    CLARIFIED = "clarified"
    CONFIRMED = "confirmed"


class SOWAnswerSource(str, Enum):
    TRANSCRIPT = "transcript"
    HUBSPOT = "hubspot"
    USER_INPUT = "user_input"
    CLARIFICATION = "clarification"


class TranscriptSource(str, Enum):
    MANUAL_PASTE = "manual_paste"
    MANUAL_UPLOAD = "manual_upload"
    FATHOM = "fathom"
    GRANOLA = "granola"


# Template Schemas
class TemplateFieldDefinition(BaseModel):
    """Definition of a template field."""
    tag_name: str
    display_name: str
    description: Optional[str] = None
    user_guidance: Optional[str] = None
    field_type: str = "text"
    is_required: bool = False
    default_value: Optional[str] = None
    validation_rules: Dict[str, Any] = {}
    depends_on: List[str] = []
    field_group: Optional[str] = None
    display_order: int = 0


class TemplateCreateRequest(BaseModel):
    """Request to create/upload a template."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None


class TemplateResponse(BaseModel):
    """Template details response."""
    id: int
    name: str
    description: Optional[str]
    is_published: bool
    fields: List[TemplateFieldDefinition]
    created_by: int
    created_at: datetime
    updated_at: datetime


class TemplateListResponse(BaseModel):
    """List of templates."""
    items: List[TemplateResponse]
    total: int


# Draft Schemas
class DraftCreateRequest(BaseModel):
    """Request to create a new SOW draft."""
    name: str = Field(..., max_length=255)
    template_id: int
    opportunity_name: Optional[str] = None
    hubspot_deal_id: Optional[str] = None


class DraftUpdateRequest(BaseModel):
    """Request to update draft metadata."""
    name: Optional[str] = None
    opportunity_name: Optional[str] = None


class DraftResponse(BaseModel):
    """SOW draft details."""
    id: int
    name: str
    opportunity_name: Optional[str]
    template_id: int
    template_name: str
    status: SOWDraftStatus
    review_status: str
    hubspot_deal_id: Optional[str]
    transcript_count: int
    fields_completed: int
    fields_total: int
    latest_version: Optional[int]
    created_by: int
    created_at: datetime
    updated_at: datetime


class DraftListResponse(BaseModel):
    """List of drafts."""
    items: List[DraftResponse]
    total: int
    page: int
    page_size: int


# Transcript Schemas
class TranscriptAddRequest(BaseModel):
    """Request to add a transcript."""
    name: str = Field(..., max_length=255)
    content: str = Field(..., min_length=100)  # Minimum 100 chars
    source_type: TranscriptSource = TranscriptSource.MANUAL_PASTE


class TranscriptImportRequest(BaseModel):
    """Request to import transcripts from connector."""
    source_type: TranscriptSource
    source_ids: List[str]  # External IDs to import


class TranscriptResponse(BaseModel):
    """Transcript details."""
    id: int
    name: str
    source_type: TranscriptSource
    word_count: int
    is_processed: bool
    created_at: datetime


# Field Schemas
class FieldAnswerResponse(BaseModel):
    """Field answer details."""
    field_tag: str
    display_name: str
    description: Optional[str]
    user_guidance: Optional[str]
    field_type: str
    is_required: bool
    field_group: Optional[str]
    display_order: int
    
    # Current value
    value: Optional[str]
    confidence: Optional[float]
    confidence_category: Optional[str]  # "high", "medium", "low"
    status: SOWFieldStatus
    source_type: Optional[SOWAnswerSource]
    source_excerpt: Optional[str]
    clarification: Optional[str]


class FieldUpdateRequest(BaseModel):
    """Request to update a field value directly."""
    value: str


class FieldClarifyRequest(BaseModel):
    """Request to clarify/refine a field value."""
    clarification: str = Field(..., max_length=2000)


class FieldsResponse(BaseModel):
    """All fields for a draft."""
    fields: List[FieldAnswerResponse]
    completed_count: int
    required_completed: int
    required_total: int


# Generation Schemas
class GenerateRequest(BaseModel):
    """Request to generate DOCX."""
    pass  # No parameters needed; generates from current field values


class VersionResponse(BaseModel):
    """Generated version details."""
    id: int
    version_number: int
    file_size: int
    is_reviewed: bool
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    reviewer_notes: Optional[str]
    generated_by: int
    generated_at: datetime
    download_url: str


class VersionListResponse(BaseModel):
    """List of versions."""
    items: List[VersionResponse]


# Review Schemas
class ReviewRequestRequest(BaseModel):
    """Request to submit for review."""
    notes: Optional[str] = None


class ReviewSubmitRequest(BaseModel):
    """Submit review decision."""
    status: str  # "approved" or "changes_requested"
    notes: Optional[str] = None
    field_feedback: Optional[Dict[str, str]] = None  # {field_tag: feedback}


# SSE Event Schemas
class ExtractionEvent(BaseModel):
    """SSE event during extraction."""
    event_id: str
    event_type: str
    field_tag: Optional[str] = None
    field_value: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    message: Optional[str] = None
    progress_percentage: Optional[int] = None
    timestamp: datetime


# Connector Schemas
class FathomCallResponse(BaseModel):
    """Fathom call available for import."""
    call_id: str
    title: str
    date: datetime
    duration_minutes: int
    participants: List[str]


class HubSpotDealResponse(BaseModel):
    """HubSpot deal available for linking."""
    deal_id: str
    deal_name: str
    company_name: Optional[str]
    stage: str
    amount: Optional[float]
    close_date: Optional[datetime]
```

### API Examples

```bash
# Create a new draft
curl -X POST /api/v1/sow/drafts \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Acme Corp Cloud Migration SOW",
    "template_id": 1,
    "opportunity_name": "Acme Corp"
  }'

# Response
{
  "id": 42,
  "name": "Acme Corp Cloud Migration SOW",
  "opportunity_name": "Acme Corp",
  "template_id": 1,
  "template_name": "Standard Cloud Migration SOW",
  "status": "draft",
  "review_status": "none",
  "transcript_count": 0,
  "fields_completed": 0,
  "fields_total": 15,
  "latest_version": null,
  "created_at": "2026-01-16T12:00:00Z"
}

# Add transcript
curl -X POST /api/v1/sow/drafts/42/transcripts \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Discovery Call #1 - Technical Requirements",
    "content": "John: Thanks for joining the call today...",
    "source_type": "manual_paste"
  }'

# Start extraction
curl -X POST /api/v1/sow/drafts/42/extract \
  -H "Authorization: Bearer $TOKEN"

# Response (immediate)
{
  "status": "extracting",
  "stream_url": "/api/v1/sow/drafts/42/stream?token=eyJ..."
}

# SSE stream events
event: field_extracted
data: {"event_id": "evt_123", "event_type": "field_extracted", "field_tag": "CLIENT_NAME", "field_value": "Acme Corporation", "confidence": 0.95, "status": "auto_filled", "progress_percentage": 10}

event: field_extracted
data: {"event_id": "evt_124", "event_type": "field_extracted", "field_tag": "PROJECT_GOALS", "field_value": "Migrate legacy on-premise infrastructure to AWS...", "confidence": 0.72, "status": "suggested", "progress_percentage": 20}

event: followup_generated
data: {"event_id": "evt_125", "event_type": "followup_generated", "field_tag": "TIMELINE", "message": "The transcripts mention both '4-6 weeks' and '6-8 weeks'. What is the agreed timeline?", "progress_percentage": 30}

event: extraction_completed
data: {"event_id": "evt_200", "event_type": "extraction_completed", "progress_percentage": 100}

# Submit clarification
curl -X POST /api/v1/sow/drafts/42/fields/TIMELINE/clarify \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "clarification": "The timeline should be 6-8 weeks as discussed in the second call"
  }'

# Generate DOCX
curl -X POST /api/v1/sow/drafts/42/generate \
  -H "Authorization: Bearer $TOKEN"

# Response
{
  "id": 1,
  "version_number": 1,
  "file_size": 45678,
  "generated_at": "2026-01-16T12:30:00Z",
  "download_url": "/api/v1/sow/versions/1/download"
}
```

---

## Integration Points

### Existing Services

| Service | Usage | Location |
|---------|-------|----------|
| `AuthService` | Token verification for SSE | `src/services/auth_service.py` |
| `StorageService` | Blob storage for DOCX files | `src/services/storage_service.py` |
| Connector Framework | Base class for Fathom/Granola/HubSpot | `src/services/ingestion/connectors/base.py` |

### External APIs

| API | Purpose | Auth Method |
|-----|---------|-------------|
| **Fathom** | Import call transcripts | OAuth 2.0 |
| **Granola** | Import call transcripts | OAuth 2.0 |
| **HubSpot** | Import deal/company data | OAuth 2.0 |
| **Google Drive** | Import Google Docs templates | OAuth 2.0 |
| **OpenAI/LLM** | Transcript extraction | API Key |

### Celery Tasks

| Task | Purpose | Queue |
|------|---------|-------|
| `process_sow_transcripts` | Run extraction flow | `default` |
| `generate_sow_document` | Generate DOCX from template | `default` |
| `process_sow_clarification` | Re-process field after clarification | `default` |

### New Connectors

#### Fathom Connector

```python
# src/services/ingestion/connectors/fathom_connector.py

class FathomConnector(SimpleStreamConnector):
    """Connector for Fathom.video call transcripts."""
    
    stream_name = "transcripts"
    supported_sync_modes = ["full"]
    
    def __init__(self, credentials: Dict, config: Dict, customer_id: str):
        super().__init__(credentials, config, customer_id)
        self.access_token = credentials.get("access_token")
        self.base_url = "https://api.fathom.video/v1"
    
    def check(self) -> Dict[str, Any]:
        """Test Fathom API connectivity."""
        response = self._make_request("GET", "/user")
        return {
            "status": "healthy" if response.ok else "unhealthy",
            "message": "Connected to Fathom" if response.ok else response.text
        }
    
    def list_calls(self, since: Optional[datetime] = None) -> List[Dict]:
        """List available calls with transcripts."""
        params = {}
        if since:
            params["created_after"] = since.isoformat()
        return self._make_request("GET", "/calls", params=params).json()
    
    def get_transcript(self, call_id: str) -> str:
        """Get full transcript for a call."""
        response = self._make_request("GET", f"/calls/{call_id}/transcript")
        data = response.json()
        # Format as readable transcript with speakers
        return self._format_transcript(data)
```

#### Granola Connector

```python
# src/services/ingestion/connectors/granola_connector.py

class GranolaConnector(SimpleStreamConnector):
    """Connector for Granola meeting notes and transcripts."""
    
    stream_name = "meetings"
    supported_sync_modes = ["full"]
    
    # Similar structure to Fathom
```

#### HubSpot SOW Connector

```python
# src/services/ingestion/connectors/hubspot_sow_connector.py

class HubSpotSOWConnector(SimpleStreamConnector):
    """Connector for HubSpot CRM data for SOW population."""
    
    stream_name = "deals"
    supported_sync_modes = ["full"]
    
    def __init__(self, credentials: Dict, config: Dict, customer_id: str):
        super().__init__(credentials, config, customer_id)
        self.access_token = credentials.get("access_token")
        self.base_url = "https://api.hubapi.com"
    
    def check(self) -> Dict[str, Any]:
        """Test HubSpot API connectivity."""
        response = self._make_request("GET", "/crm/v3/objects/deals", params={"limit": 1})
        return {
            "status": "healthy" if response.ok else "unhealthy"
        }
    
    def get_deal_with_company(self, deal_id: str) -> Dict[str, Any]:
        """Get deal with associated company data."""
        deal = self._get_deal(deal_id)
        company = self._get_associated_company(deal_id)
        contacts = self._get_associated_contacts(deal_id)
        
        return {
            "deal": deal,
            "company": company,
            "contacts": contacts
        }
    
    def map_to_sow_fields(self, data: Dict) -> Dict[str, str]:
        """Map HubSpot data to SOW field tags."""
        # Configurable mapping
        return {
            "CLIENT_NAME": data.get("company", {}).get("name"),
            "CLIENT_CONTACT": data.get("contacts", [{}])[0].get("email"),
            "DEAL_VALUE": data.get("deal", {}).get("amount"),
            # ... more mappings
        }
```

---

## Security Considerations

### Authentication & Authorization

**New Permissions:**

| Permission | Description |
|------------|-------------|
| `sow:read` | View SOW drafts, templates, versions |
| `sow:write` | Create/edit drafts, add transcripts, generate |
| `sow-templates:admin` | Upload/edit/publish templates |
| `sow:review` | Submit Delivery reviews |

**Permission Assignment:**

```python
# Typical role assignments
ROLE_PERMISSIONS = {
    "sales": ["sow:read", "sow:write"],
    "solutions": ["sow:read", "sow:write"],
    "delivery": ["sow:read", "sow:write", "sow:review"],
    "sow_admin": ["sow:read", "sow:write", "sow-templates:admin", "sow:review"],
}
```

### Row Level Security

All queries MUST filter by `customer_id`:

```python
@router.get("/drafts")
async def list_drafts(
    current_user = Depends(require_permission(["sow:read"])),
    db: Session = Depends(get_db)
):
    drafts = db.query(SOWDraft).filter(
        SOWDraft.customer_id == current_user.customer_id  # RLS
    ).all()
    return drafts
```

### Data Security

| Data Type | Protection |
|-----------|------------|
| **Transcripts** | Encrypted at rest (database encryption); contains sensitive customer discussions |
| **Generated DOCX** | Stored in S3 with server-side encryption; signed URLs for download |
| **Connector Tokens** | Encrypted with tenant-specific keys; stored in `customer_ai_providers` |
| **Field Answers** | Standard database encryption; may contain sensitive deal information |

### Audit Trail

- All SOW operations logged to `sow_extraction_events` table
- User actions (create, edit, generate, review) logged with user_id and timestamp
- Version history provides complete change tracking

---

## Error Handling

| Error Case | HTTP Code | Response | Handling |
|------------|-----------|----------|----------|
| Draft not found | 404 | `{"detail": "SOW draft not found"}` | Return early |
| Template not found | 404 | `{"detail": "Template not found"}` | Return early |
| Invalid template (missing tags) | 422 | `{"detail": "Template validation failed", "errors": [...]}` | Block publish |
| Required field empty on generate | 422 | `{"detail": "Required fields missing", "fields": ["TIMELINE"]}` | Block generate |
| Extraction failed | 500 | `{"detail": "Extraction failed", "error": "..."}` | Log, notify, allow retry |
| Connector auth expired | 401 | `{"detail": "Connector authentication expired"}` | Prompt re-auth |
| Transcript too long | 413 | `{"detail": "Transcript exceeds maximum length"}` | Reject with limit info |
| Rate limited (external API) | 429 | `{"detail": "External API rate limited", "retry_after": 60}` | Retry with backoff |

### Extraction Error Recovery

```python
# In SOW extraction task
try:
    flow = SOWExtractionFlow(draft_id=draft_id)
    result = flow.run()
except ExtractionError as e:
    # Update draft status
    draft.status = "draft"  # Revert to allow retry
    
    # Log event
    db.add(SOWExtractionEvent(
        draft_id=draft_id,
        event_type="extraction_failed",
        data={"error": str(e)}
    ))
    
    # Emit SSE error
    emit_sse_event(draft_id, {
        "event_type": "extraction_failed",
        "message": "Extraction failed. Please try again.",
        "error": str(e)
    })
```

---

## Performance Considerations

### Processing Time Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Single transcript extraction | < 30 seconds | For transcripts up to 10,000 words |
| Multi-transcript extraction (3) | < 90 seconds | Parallel processing |
| DOCX generation | < 5 seconds | Synchronous acceptable |
| SSE event delivery | < 500ms | From database to client |

### Transcript Size Limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| **Single transcript** | 50,000 words (~200KB) | ~2 hours of call |
| **Total per draft** | 150,000 words | Prevent excessive processing |
| **Minimum** | 100 characters | Avoid empty submissions |

### Long Transcript Handling

For transcripts exceeding LLM context window:

```python
def chunk_transcript_for_extraction(transcript: str, max_tokens: int = 100000) -> List[str]:
    """
    Split transcript into overlapping chunks for extraction.
    
    Strategy:
    1. Split by natural breaks (speaker changes, paragraphs)
    2. Ensure 500-token overlap between chunks
    3. Process each chunk and merge results
    """
    chunks = []
    # Implementation uses tiktoken for accurate tokenization
    # Preserves speaker context across chunk boundaries
    return chunks
```

### Caching Strategy

| Data | Cache | TTL | Invalidation |
|------|-------|-----|--------------|
| Template parsed schema | Redis | 1 hour | On template update |
| HubSpot deal data (per draft) | PostgreSQL (snapshot) | Permanent | Manual refresh only |
| Fathom call list | Redis | 5 minutes | On user request |
| LLM extraction results | Database | Permanent | On re-extraction |

### Query Optimization

```sql
-- Key indexes for common queries
CREATE INDEX idx_sow_drafts_list ON sow_drafts(customer_id, status, created_at DESC);
CREATE INDEX idx_sow_field_answers_draft ON sow_field_answers(draft_id);
CREATE INDEX idx_sow_extraction_events_poll ON sow_extraction_events(draft_id, created_at);
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_sow_service.py

def test_create_draft():
    """Test creating a new SOW draft."""
    # Arrange
    template = create_test_template()
    user = create_test_user()
    
    # Act
    draft = sow_service.create_draft(
        name="Test Draft",
        template_id=template.id,
        user_id=user.id,
        customer_id=user.customer_id
    )
    
    # Assert
    assert draft.status == SOWDraftStatus.DRAFT
    assert draft.template_id == template.id


def test_extraction_confidence_thresholds():
    """Test confidence categorization."""
    assert categorize_confidence(0.95) == "high"
    assert categorize_confidence(0.75) == "medium"
    assert categorize_confidence(0.45) == "low"


def test_docx_tag_replacement():
    """Test DOCX template tag replacement."""
    template_path = "tests/fixtures/test_template.docx"
    values = {"CLIENT_NAME": "Acme Corp", "PROJECT_GOALS": "Migration"}
    
    output = generate_docx(template_path, values)
    
    # Verify tags replaced
    doc = Document(output)
    full_text = "\n".join([p.text for p in doc.paragraphs])
    assert "{{CLIENT_NAME}}" not in full_text
    assert "Acme Corp" in full_text
```

### Integration Tests

```python
# tests/test_sow_api.py

@pytest.mark.asyncio
async def test_full_sow_flow():
    """Test complete SOW creation to generation flow."""
    # 1. Create draft
    response = await client.post("/api/v1/sow/drafts", json={...})
    draft_id = response.json()["id"]
    
    # 2. Add transcript
    await client.post(f"/api/v1/sow/drafts/{draft_id}/transcripts", json={...})
    
    # 3. Start extraction
    await client.post(f"/api/v1/sow/drafts/{draft_id}/extract")
    
    # 4. Wait for completion (poll or SSE)
    await wait_for_status(draft_id, "ready")
    
    # 5. Generate
    response = await client.post(f"/api/v1/sow/drafts/{draft_id}/generate")
    version = response.json()
    
    # 6. Download and verify
    docx = await client.get(version["download_url"])
    assert docx.status_code == 200


def test_multi_tenant_isolation():
    """Verify tenant A cannot see tenant B's drafts."""
    draft_a = create_draft(customer_id="tenant_a")
    draft_b = create_draft(customer_id="tenant_b")
    
    # User from tenant A
    user_a = create_user(customer_id="tenant_a")
    drafts = list_drafts(user=user_a)
    
    assert draft_a.id in [d.id for d in drafts]
    assert draft_b.id not in [d.id for d in drafts]
```

### E2E Tests

- [ ] User can create draft and add transcript via UI
- [ ] SSE stream shows real-time extraction progress
- [ ] User can clarify low-confidence fields
- [ ] Generated DOCX downloads correctly
- [ ] Review workflow functions correctly
- [ ] Fathom import works with valid credentials
- [ ] HubSpot linking populates fields

---

## Migration Strategy

### Database Migration

```python
# alembic/versions/xxxx_add_sow_automation_tables.py

def upgrade():
    # Create enums
    op.execute("CREATE TYPE sow_draft_status AS ENUM ('draft', 'extracting', 'ready', 'generating', 'review_requested', 'reviewed', 'archived')")
    op.execute("CREATE TYPE sow_review_status AS ENUM ('none', 'requested', 'in_review', 'changes_requested', 'approved')")
    op.execute("CREATE TYPE sow_transcript_source AS ENUM ('manual_paste', 'manual_upload', 'fathom', 'granola')")
    op.execute("CREATE TYPE sow_field_status AS ENUM ('empty', 'auto_filled', 'suggested', 'needs_input', 'user_provided', 'clarified', 'confirmed')")
    op.execute("CREATE TYPE sow_answer_source AS ENUM ('transcript', 'hubspot', 'user_input', 'clarification')")
    op.execute("CREATE TYPE sow_extraction_event_type AS ENUM ('extraction_started', 'field_extracted', 'field_confidence_low', 'followup_generated', 'extraction_completed', 'extraction_failed')")
    
    # Create tables (in dependency order)
    op.create_table('sow_templates', ...)
    op.create_table('sow_template_fields', ...)
    op.create_table('sow_drafts', ...)
    op.create_table('sow_transcripts', ...)
    op.create_table('sow_field_answers', ...)
    op.create_table('sow_versions', ...)
    op.create_table('sow_extraction_events', ...)
    
    # Create indexes
    op.create_index(...)


def downgrade():
    # Drop tables in reverse order
    op.drop_table('sow_extraction_events')
    op.drop_table('sow_versions')
    op.drop_table('sow_field_answers')
    op.drop_table('sow_transcripts')
    op.drop_table('sow_drafts')
    op.drop_table('sow_template_fields')
    op.drop_table('sow_templates')
    
    # Drop enums
    op.execute("DROP TYPE sow_extraction_event_type")
    op.execute("DROP TYPE sow_answer_source")
    op.execute("DROP TYPE sow_field_status")
    op.execute("DROP TYPE sow_transcript_source")
    op.execute("DROP TYPE sow_review_status")
    op.execute("DROP TYPE sow_draft_status")
```

### Deployment Order

1. **Pre-deployment**
   - Run database migration
   - Add new permissions to RBAC
   
2. **Backend deployment**
   - Deploy API routes
   - Deploy Celery tasks
   - Deploy CrewAI flow
   
3. **Frontend deployment**
   - Deploy SOW pages and components
   - Regenerate Orval API clients

4. **Post-deployment**
   - Verify health checks
   - Upload sample templates
   - Enable feature flag (if used)

### Rollback Plan

1. Disable feature flag (if used)
2. Revert frontend deployment
3. Revert backend deployment
4. Run `alembic downgrade -1` (if needed)

---

## Agent Review Notes

### Questions Resolved During Review

| Question | Resolution |
|----------|------------|
| Sync vs async processing? | **Async** — Celery task with SSE stream for long-running extraction |
| CrewAI vs direct LLM calls? | **CrewAI Flow** — Better orchestration for multi-step extraction pipeline |
| DOCX library? | **docxtpl** — Jinja2 templating is cleaner for tag replacement |
| Confidence representation? | **Numeric (0-1)** with categorical mapping (high/medium/low) |
| Template tag format? | **`{{TAG_NAME}}`** — Jinja2 style, uppercase with underscores |
| Transcript storage? | **Separate records** — Enables reuse and better audit |
| Version storage? | **Full snapshots** — Simpler, guarantees reproducibility |
| HubSpot sync model? | **Snapshot at draft creation** — Simpler than live sync |

### Confidence Threshold Configuration

```python
# src/core/config.py

class SOWSettings(BaseSettings):
    """SOW Automation configuration."""
    
    # Confidence thresholds
    confidence_auto_fill: float = 0.80    # >= 0.80 = auto-fill
    confidence_suggest: float = 0.60      # 0.60-0.79 = suggest (needs review)
    confidence_ask: float = 0.60          # < 0.60 = ask follow-up
    
    # Processing limits
    max_transcript_words: int = 50000
    max_transcripts_per_draft: int = 10
    extraction_timeout_seconds: int = 300
    
    # LLM settings
    extraction_model: str = "gpt-4o"
    extraction_temperature: float = 0.2
```

### Edge Cases Identified

| Edge Case | Handling |
|-----------|----------|
| **Conflicting transcript info** | Mark field as "suggested" with lower confidence; include both excerpts; let user resolve |
| **Template updated after draft created** | Use template version at draft creation; warn if template changed |
| **Very short transcript** | Warn user; proceed with extraction but expect low confidence |
| **All fields low confidence** | Present all as follow-up questions; don't auto-fill anything |
| **User clears auto-filled field** | Mark as "empty" with "user_input" source; don't re-extract |
| **Review requested while extracting** | Block until extraction complete |
| **Duplicate transcript upload** | Warn user; allow if they confirm |

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **LLM extraction quality varies** | Medium | High | Confidence gating; user review; iterative prompt tuning |
| **Long transcript processing timeout** | Medium | Medium | Chunking strategy; progress streaming; generous timeouts |
| **Fathom/Granola API changes** | Low | Medium | Connector abstraction; version pinning; monitoring |
| **DOCX formatting corrupted** | Low | High | Template validation; preview before publish; test suite |
| **User adoption friction** | Medium | High | Excel-like familiarity; clear guidance; minimal required fields |

---

## Open Technical Questions

- [ ] **Google Docs OAuth scope requirements** — Need to verify minimum scopes for read-only access
- [ ] **Fathom API pagination limits** — Need to test with accounts that have 100+ calls
- [ ] **DOCX table handling** — How should tables with merged cells be handled during tag replacement?
- [ ] **Rich text in fields** — Should we support basic formatting (bold, bullets) in field values?

---

*This Technical Specification provides the architectural blueprint for implementing SOW Automation. Implementation should follow the patterns established in the Implementation Plan.*
