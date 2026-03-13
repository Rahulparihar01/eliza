# Implementation Plan
## SOW Automation: Transcript-Assisted Statement of Work Generator

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Ready |
| **Last Updated** | January 16, 2026 |
| **Tech Spec Reference** | [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md) |
| **Estimated Total Time** | 8-10 days |

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Implementation Phases](#implementation-phases)
3. [Database Migrations](#database-migrations)
4. [Deployment Checklist](#deployment-checklist)
5. [Rollback Plan](#rollback-plan)
6. [Progress Tracking](#progress-tracking)

---

## Prerequisites

Before starting implementation:

- [ ] Technical Spec approved
- [ ] Database schema reviewed
- [ ] API contracts finalized
- [ ] Sample DOCX template(s) available for testing
- [ ] Fathom API documentation and test credentials available
- [ ] Granola API documentation and test credentials available
- [ ] HubSpot sandbox account for testing
- [ ] New RBAC permissions defined in permissions table

---

## Implementation Phases

### Phase 1: Database & Models (Est: 4-6 hours)

#### Task 1.1: Create Database Migration

**Files:**
- `alembic/versions/xxxx_add_sow_automation_tables.py`

**Changes:**
1. Create migration with `alembic revision -m "add_sow_automation_tables"`
2. Add enum types:
   - `sow_draft_status`
   - `sow_review_status`
   - `sow_transcript_source`
   - `sow_field_status`
   - `sow_answer_source`
   - `sow_extraction_event_type`
3. Add tables in dependency order:
   - `sow_templates`
   - `sow_template_fields`
   - `sow_drafts`
   - `sow_transcripts`
   - `sow_field_answers`
   - `sow_versions`
   - `sow_extraction_events`
4. Add all indexes
5. Implement downgrade (drop in reverse order)

**Checkpoint:** Migration runs successfully with `alembic upgrade head`

---

#### Task 1.2: Create SQLAlchemy Models

**Files:**
- `src/models/sow.py` (new)
- `src/models/__init__.py` (update exports)

**Changes:**
```python
# src/models/sow.py

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Numeric, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from src.models.database import BaseModel


class SOWDraftStatus(str, enum.Enum):
    DRAFT = "draft"
    EXTRACTING = "extracting"
    READY = "ready"
    GENERATING = "generating"
    REVIEW_REQUESTED = "review_requested"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


class SOWReviewStatus(str, enum.Enum):
    NONE = "none"
    REQUESTED = "requested"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"


class SOWTranscriptSource(str, enum.Enum):
    MANUAL_PASTE = "manual_paste"
    MANUAL_UPLOAD = "manual_upload"
    FATHOM = "fathom"
    GRANOLA = "granola"


class SOWFieldStatus(str, enum.Enum):
    EMPTY = "empty"
    AUTO_FILLED = "auto_filled"
    SUGGESTED = "suggested"
    NEEDS_INPUT = "needs_input"
    USER_PROVIDED = "user_provided"
    CLARIFIED = "clarified"
    CONFIRMED = "confirmed"


class SOWAnswerSource(str, enum.Enum):
    TRANSCRIPT = "transcript"
    HUBSPOT = "hubspot"
    USER_INPUT = "user_input"
    CLARIFICATION = "clarification"


class SOWExtractionEventType(str, enum.Enum):
    EXTRACTION_STARTED = "extraction_started"
    FIELD_EXTRACTED = "field_extracted"
    FIELD_CONFIDENCE_LOW = "field_confidence_low"
    FOLLOWUP_GENERATED = "followup_generated"
    EXTRACTION_COMPLETED = "extraction_completed"
    EXTRACTION_FAILED = "extraction_failed"


class SOWTemplate(BaseModel):
    __tablename__ = "sow_templates"
    
    customer_id = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64))
    schema = Column(JSONB, nullable=False, default={})
    is_published = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    fields = relationship("SOWTemplateField", back_populates="template", cascade="all, delete-orphan")
    drafts = relationship("SOWDraft", back_populates="template")


class SOWTemplateField(BaseModel):
    __tablename__ = "sow_template_fields"
    
    template_id = Column(Integer, ForeignKey("sow_templates.id", ondelete="CASCADE"), nullable=False)
    tag_name = Column(String(100), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    user_guidance = Column(Text)
    field_type = Column(String(50), default="text")
    is_required = Column(Boolean, default=False)
    default_value = Column(Text)
    validation_rules = Column(JSONB, default={})
    depends_on = Column(JSONB, default=[])
    display_order = Column(Integer, default=0)
    field_group = Column(String(100))
    
    # Relationships
    template = relationship("SOWTemplate", back_populates="fields")


class SOWDraft(BaseModel):
    __tablename__ = "sow_drafts"
    
    customer_id = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    opportunity_name = Column(String(255))
    template_id = Column(Integer, ForeignKey("sow_templates.id"))
    hubspot_company_id = Column(String(100))
    hubspot_deal_id = Column(String(100))
    hubspot_snapshot = Column(JSONB)
    status = Column(String(50), default="draft")
    review_status = Column(String(50), default="none")
    reviewer_id = Column(Integer, ForeignKey("users.id"))
    review_notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relationships
    template = relationship("SOWTemplate", back_populates="drafts")
    transcripts = relationship("SOWTranscript", back_populates="draft", cascade="all, delete-orphan")
    field_answers = relationship("SOWFieldAnswer", back_populates="draft", cascade="all, delete-orphan")
    versions = relationship("SOWVersion", back_populates="draft", cascade="all, delete-orphan")
    events = relationship("SOWExtractionEvent", back_populates="draft", cascade="all, delete-orphan")


class SOWTranscript(BaseModel):
    __tablename__ = "sow_transcripts"
    
    draft_id = Column(Integer, ForeignKey("sow_drafts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)
    source_id = Column(String(255))
    content = Column(Text, nullable=False)
    word_count = Column(Integer)
    metadata = Column(JSONB, default={})
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True))
    
    # Relationships
    draft = relationship("SOWDraft", back_populates="transcripts")


class SOWFieldAnswer(BaseModel):
    __tablename__ = "sow_field_answers"
    
    draft_id = Column(Integer, ForeignKey("sow_drafts.id", ondelete="CASCADE"), nullable=False)
    field_tag = Column(String(100), nullable=False)
    value = Column(Text)
    confidence = Column(Numeric(3, 2))
    source_type = Column(String(50))
    source_transcript_id = Column(Integer, ForeignKey("sow_transcripts.id"))
    source_excerpt = Column(Text)
    status = Column(String(50), default="empty")
    clarification = Column(Text)
    clarification_at = Column(DateTime(timezone=True))
    
    # Relationships
    draft = relationship("SOWDraft", back_populates="field_answers")


class SOWVersion(BaseModel):
    __tablename__ = "sow_versions"
    
    draft_id = Column(Integer, ForeignKey("sow_drafts.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    field_snapshot = Column(JSONB, nullable=False)
    is_reviewed = Column(Boolean, default=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    reviewer_notes = Column(Text)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    draft = relationship("SOWDraft", back_populates="versions")


class SOWExtractionEvent(BaseModel):
    __tablename__ = "sow_extraction_events"
    
    draft_id = Column(Integer, ForeignKey("sow_drafts.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)
    field_tag = Column(String(100))
    data = Column(JSONB, default={})
    
    # Relationships
    draft = relationship("SOWDraft", back_populates="events")
```

**Tests:**
- [ ] Models can be imported without errors
- [ ] `db.query(SOWDraft).first()` works after migration

**Checkpoint:** All models queryable, relationships work

---

#### Task 1.3: Add RBAC Permissions

**Files:**
- Database seed or migration for permissions

**Changes:**
1. Add new permissions:
   - `sow:read` - View SOW drafts, templates, versions
   - `sow:write` - Create/edit drafts, add transcripts, generate
   - `sow-templates:admin` - Upload/edit/publish templates
   - `sow:review` - Submit Delivery reviews

2. Assign to default roles (via seed data or migration)

**Checkpoint:** Permissions exist in database

---

### Phase 2: Service Layer (Est: 6-8 hours)

#### Task 2.1: Create SOW Template Service

**Files:**
- `src/services/sow_template_service.py` (new)

**Changes:**
```python
# src/services/sow_template_service.py

class SOWTemplateService:
    """Service for managing SOW templates."""
    
    def __init__(self, db: Session, customer_id: str):
        self.db = db
        self.customer_id = customer_id
    
    def upload_template(
        self,
        name: str,
        file_content: bytes,
        created_by: int,
        description: Optional[str] = None
    ) -> SOWTemplate:
        """
        Upload and parse a DOCX template.
        
        1. Save file to blob storage
        2. Parse tags from DOCX
        3. Create template and field records
        """
        pass
    
    def parse_docx_tags(self, file_path: str) -> List[str]:
        """Extract {{TAG}} patterns from DOCX."""
        pass
    
    def validate_template(self, template_id: int) -> Dict[str, Any]:
        """Validate template is ready for publishing."""
        pass
    
    def publish_template(self, template_id: int) -> SOWTemplate:
        """Mark template as published."""
        pass
    
    def import_from_google_doc(
        self,
        doc_id: str,
        name: str,
        created_by: int,
        oauth_token: str
    ) -> SOWTemplate:
        """Import Google Doc as DOCX template."""
        pass
```

**Tests:**
- [ ] Template upload extracts tags correctly
- [ ] Invalid templates rejected
- [ ] Publishing requires all fields defined

**Checkpoint:** Templates can be uploaded and parsed

---

#### Task 2.2: Create SOW Draft Service

**Files:**
- `src/services/sow_service.py` (new)

**Changes:**
```python
# src/services/sow_service.py

class SOWService:
    """Service for SOW draft lifecycle management."""
    
    def __init__(self, db: Session, customer_id: str):
        self.db = db
        self.customer_id = customer_id
    
    def create_draft(
        self,
        name: str,
        template_id: int,
        created_by: int,
        opportunity_name: Optional[str] = None,
        hubspot_deal_id: Optional[str] = None
    ) -> SOWDraft:
        """Create new SOW draft with empty field answers."""
        pass
    
    def add_transcript(
        self,
        draft_id: int,
        name: str,
        content: str,
        source_type: str,
        source_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> SOWTranscript:
        """Add transcript to draft."""
        pass
    
    def update_field_answer(
        self,
        draft_id: int,
        field_tag: str,
        value: str,
        source_type: str = "user_input"
    ) -> SOWFieldAnswer:
        """Update field value directly."""
        pass
    
    def clarify_field(
        self,
        draft_id: int,
        field_tag: str,
        clarification: str
    ) -> SOWFieldAnswer:
        """Process user clarification for a field."""
        pass
    
    def get_draft_with_fields(self, draft_id: int) -> Dict[str, Any]:
        """Get draft with all field answers and template info."""
        pass
    
    def request_review(self, draft_id: int, notes: Optional[str] = None) -> SOWDraft:
        """Mark draft as ready for Delivery review."""
        pass
    
    def submit_review(
        self,
        draft_id: int,
        reviewer_id: int,
        status: str,
        notes: Optional[str] = None,
        field_feedback: Optional[Dict[str, str]] = None
    ) -> SOWDraft:
        """Submit Delivery review."""
        pass
```

**Tests:**
- [ ] Draft creation initializes empty field answers
- [ ] Field updates work correctly
- [ ] Review workflow state transitions valid

**Checkpoint:** Draft CRUD operations work

---

#### Task 2.3: Create DOCX Generation Service

**Files:**
- `src/services/sow_generation_service.py` (new)

**Changes:**
```python
# src/services/sow_generation_service.py

from docxtpl import DocxTemplate
import io

class SOWGenerationService:
    """Service for generating DOCX from templates."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate(
        self,
        draft_id: int,
        generated_by: int
    ) -> SOWVersion:
        """
        Generate DOCX from draft's field answers.
        
        1. Load template DOCX
        2. Get all field answers
        3. Replace tags using docxtpl
        4. Save to blob storage
        5. Create version record
        """
        pass
    
    def validate_ready_to_generate(self, draft_id: int) -> Dict[str, Any]:
        """Check if all required fields are filled."""
        pass
    
    def _render_template(
        self,
        template_path: str,
        values: Dict[str, str]
    ) -> bytes:
        """Render DOCX with tag replacements."""
        doc = DocxTemplate(template_path)
        doc.render(values)
        
        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()
```

**Tests:**
- [ ] Tag replacement works correctly
- [ ] Missing required fields blocks generation
- [ ] Version number increments correctly

**Checkpoint:** DOCX generation produces valid documents

---

### Phase 3: Extraction Flow (Est: 8-10 hours)

#### Task 3.1: Create SOW Extraction Flow

**Files:**
- `src/flows/sow_extraction_flow.py` (new)

**Changes:**
```python
# src/flows/sow_extraction_flow.py

from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class SOWExtractionState(BaseModel):
    """State for SOW extraction flow."""
    draft_id: int
    customer_id: str
    template_fields: List[Dict[str, Any]] = []
    transcripts: List[Dict[str, Any]] = []
    extracted_values: Dict[str, Any] = {}
    low_confidence_fields: List[str] = []
    followup_questions: Dict[str, str] = {}
    error: Optional[str] = None


class SOWExtractionFlow(Flow[SOWExtractionState]):
    """
    CrewAI Flow for extracting SOW field values from transcripts.
    
    Flow steps:
    1. load_context - Load template fields and transcripts
    2. extract_fields - Use LLM to extract values with confidence
    3. evaluate_confidence - Categorize fields by confidence level
    4. generate_followups - Create follow-up questions for low-confidence
    5. save_results - Persist to database and emit events
    """
    
    def __init__(self, draft_id: int, customer_id: str):
        self.draft_id = draft_id
        self.customer_id = customer_id
        super().__init__()
    
    def _create_initial_state(self) -> SOWExtractionState:
        return SOWExtractionState(
            draft_id=self.draft_id,
            customer_id=self.customer_id
        )
    
    @start()
    def load_context(self):
        """Load template fields and transcripts from database."""
        pass
    
    @listen(load_context)
    def extract_fields(self):
        """
        Extract field values from transcripts using LLM.
        
        Uses structured output for reliable extraction.
        Handles long transcripts with chunking strategy.
        """
        pass
    
    @listen(extract_fields)
    def evaluate_confidence(self):
        """
        Categorize extracted values by confidence level.
        
        >= 0.80: auto_filled (high confidence)
        0.60-0.79: suggested (needs review)
        < 0.60: needs_input (ask follow-up)
        """
        pass
    
    @listen(evaluate_confidence)
    def generate_followups(self):
        """Generate follow-up questions for low-confidence fields."""
        pass
    
    @listen(generate_followups)
    def save_results(self):
        """
        Save extracted values and emit SSE events.
        
        1. Update SOWFieldAnswer records
        2. Create SOWExtractionEvent records
        3. Update draft status to 'ready'
        """
        pass
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit extraction event for SSE stream."""
        pass
```

**Tests:**
- [ ] Flow executes without errors
- [ ] Field values extracted from sample transcripts
- [ ] Confidence scores in expected ranges
- [ ] Events emitted correctly

**Checkpoint:** Extraction flow processes test transcript

---

#### Task 3.2: Create Extraction Celery Tasks

**Files:**
- `src/tasks/sow_tasks.py` (new)

**Changes:**
```python
# src/tasks/sow_tasks.py

from src.celery_app import celery_app
from src.models import database
from src.flows.sow_extraction_flow import SOWExtractionFlow
from src.services.sow_generation_service import SOWGenerationService

@celery_app.task(
    bind=True,
    name="process_sow_transcripts",
    max_retries=2,
    soft_time_limit=300
)
def process_sow_transcripts(self, draft_id: int, customer_id: str):
    """
    Process transcripts and extract field values.
    
    Runs SOWExtractionFlow asynchronously.
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        # Update draft status to 'extracting'
        draft = db.query(SOWDraft).filter(SOWDraft.id == draft_id).first()
        draft.status = "extracting"
        db.commit()
        
        # Run extraction flow
        flow = SOWExtractionFlow(draft_id=draft_id, customer_id=customer_id)
        result = flow.kickoff()
        
        # Update draft status to 'ready'
        draft.status = "ready"
        db.commit()
        
        return {"success": True, "draft_id": draft_id}
        
    except Exception as e:
        # Update draft status back to 'draft'
        draft = db.query(SOWDraft).filter(SOWDraft.id == draft_id).first()
        if draft:
            draft.status = "draft"
            db.commit()
        
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="process_sow_clarification",
    max_retries=1,
    soft_time_limit=60
)
def process_sow_clarification(
    self,
    draft_id: int,
    field_tag: str,
    clarification: str,
    customer_id: str
):
    """
    Re-process a field after user clarification.
    
    Uses LLM to refine the field value based on clarification.
    """
    pass


@celery_app.task(
    bind=True,
    name="generate_sow_document",
    max_retries=1,
    soft_time_limit=60
)
def generate_sow_document(self, draft_id: int, generated_by: int):
    """
    Generate DOCX document from draft.
    
    Runs synchronously (fast operation).
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        service = SOWGenerationService(db)
        version = service.generate(draft_id, generated_by)
        return {
            "success": True,
            "version_id": version.id,
            "version_number": version.version_number
        }
    finally:
        db.close()
```

**Tests:**
- [ ] Task executes without errors
- [ ] Status transitions work correctly
- [ ] Errors are handled gracefully

**Checkpoint:** Tasks run via Celery

---

### Phase 4: API Layer (Est: 6-8 hours)

#### Task 4.1: Create Pydantic Schemas

**Files:**
- `src/api/schemas/sow.py` (new)

**Changes:**
- Implement all request/response schemas from Tech Spec
- Add validation rules
- Add OpenAPI descriptions

**Checkpoint:** Schemas serialize/deserialize correctly

---

#### Task 4.2: Create SOW API Routes

**Files:**
- `src/api/routes/sow.py` (new)
- `src/main.py` (update to register router)

**Changes:**
```python
# src/api/routes/sow.py

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.schemas.sow import *
from src.middleware.authorization import require_permission
from src.core.database import get_db
from src.services.sow_service import SOWService
from src.services.sow_template_service import SOWTemplateService
from src.services.sow_generation_service import SOWGenerationService
from src.tasks.sow_tasks import process_sow_transcripts, generate_sow_document

router = APIRouter(prefix="/sow", tags=["SOW Automation"])


# Template endpoints
@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def upload_template(
    name: str,
    file: UploadFile = File(...),
    description: Optional[str] = None,
    current_user = Depends(require_permission(["sow-templates:admin"])),
    db: Session = Depends(get_db)
):
    """Upload a new DOCX template."""
    service = SOWTemplateService(db, current_user.customer_id)
    template = service.upload_template(
        name=name,
        file_content=await file.read(),
        created_by=current_user.user_id,
        description=description
    )
    return template


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    current_user = Depends(require_permission(["sow:read"])),
    db: Session = Depends(get_db)
):
    """List available templates."""
    templates = db.query(SOWTemplate).filter(
        SOWTemplate.customer_id == current_user.customer_id,
        SOWTemplate.is_published == True,
        SOWTemplate.is_archived == False
    ).all()
    return TemplateListResponse(items=templates, total=len(templates))


# Draft endpoints
@router.post("/drafts", response_model=DraftResponse, status_code=201)
async def create_draft(
    request: DraftCreateRequest,
    current_user = Depends(require_permission(["sow:write"])),
    db: Session = Depends(get_db)
):
    """Create a new SOW draft."""
    service = SOWService(db, current_user.customer_id)
    draft = service.create_draft(
        name=request.name,
        template_id=request.template_id,
        created_by=current_user.user_id,
        opportunity_name=request.opportunity_name,
        hubspot_deal_id=request.hubspot_deal_id
    )
    return draft


@router.get("/drafts", response_model=DraftListResponse)
async def list_drafts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    current_user = Depends(require_permission(["sow:read"])),
    db: Session = Depends(get_db)
):
    """List SOW drafts."""
    query = db.query(SOWDraft).filter(
        SOWDraft.customer_id == current_user.customer_id
    )
    if status:
        query = query.filter(SOWDraft.status == status)
    
    total = query.count()
    drafts = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return DraftListResponse(
        items=drafts,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/drafts/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: int,
    current_user = Depends(require_permission(["sow:read"])),
    db: Session = Depends(get_db)
):
    """Get draft details."""
    draft = db.query(SOWDraft).filter(
        SOWDraft.id == draft_id,
        SOWDraft.customer_id == current_user.customer_id
    ).first()
    
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    return draft


# Transcript endpoints
@router.post("/drafts/{draft_id}/transcripts", response_model=TranscriptResponse, status_code=201)
async def add_transcript(
    draft_id: int,
    request: TranscriptAddRequest,
    current_user = Depends(require_permission(["sow:write"])),
    db: Session = Depends(get_db)
):
    """Add a transcript to a draft."""
    service = SOWService(db, current_user.customer_id)
    transcript = service.add_transcript(
        draft_id=draft_id,
        name=request.name,
        content=request.content,
        source_type=request.source_type.value
    )
    return transcript


# Processing endpoints
@router.post("/drafts/{draft_id}/extract", status_code=202)
async def start_extraction(
    draft_id: int,
    current_user = Depends(require_permission(["sow:write"])),
    db: Session = Depends(get_db)
):
    """Start transcript extraction."""
    draft = db.query(SOWDraft).filter(
        SOWDraft.id == draft_id,
        SOWDraft.customer_id == current_user.customer_id
    ).first()
    
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft.status not in ["draft", "ready"]:
        raise HTTPException(status_code=400, detail=f"Cannot extract in status {draft.status}")
    
    # Queue extraction task
    process_sow_transcripts.delay(draft_id, current_user.customer_id)
    
    # Generate stream token
    from src.services.auth_service import AuthService
    auth_service = AuthService()
    token = await auth_service.create_access_token({"sub": str(current_user.user_id)})
    
    return {
        "status": "extracting",
        "stream_url": f"/api/v1/sow/drafts/{draft_id}/stream?token={token}"
    }


@router.get("/drafts/{draft_id}/stream")
async def stream_extraction(
    draft_id: int,
    token: str = Query(..., description="JWT access token"),
    db: Session = Depends(get_db)
):
    """SSE stream for extraction progress."""
    # Token verification and event generator (similar to existing SSE patterns)
    pass


# Field endpoints
@router.get("/drafts/{draft_id}/fields", response_model=FieldsResponse)
async def get_fields(
    draft_id: int,
    current_user = Depends(require_permission(["sow:read"])),
    db: Session = Depends(get_db)
):
    """Get all field answers for a draft."""
    service = SOWService(db, current_user.customer_id)
    return service.get_draft_with_fields(draft_id)


@router.put("/drafts/{draft_id}/fields/{field_tag}")
async def update_field(
    draft_id: int,
    field_tag: str,
    request: FieldUpdateRequest,
    current_user = Depends(require_permission(["sow:write"])),
    db: Session = Depends(get_db)
):
    """Update a field value directly."""
    service = SOWService(db, current_user.customer_id)
    answer = service.update_field_answer(
        draft_id=draft_id,
        field_tag=field_tag,
        value=request.value
    )
    return answer


@router.post("/drafts/{draft_id}/fields/{field_tag}/clarify")
async def clarify_field(
    draft_id: int,
    field_tag: str,
    request: FieldClarifyRequest,
    current_user = Depends(require_permission(["sow:write"])),
    db: Session = Depends(get_db)
):
    """Submit clarification for a field."""
    service = SOWService(db, current_user.customer_id)
    answer = service.clarify_field(
        draft_id=draft_id,
        field_tag=field_tag,
        clarification=request.clarification
    )
    return answer


# Generation endpoints
@router.post("/drafts/{draft_id}/generate", response_model=VersionResponse, status_code=201)
async def generate_sow(
    draft_id: int,
    current_user = Depends(require_permission(["sow:write"])),
    db: Session = Depends(get_db)
):
    """Generate DOCX from current field values."""
    service = SOWGenerationService(db)
    
    # Validate ready to generate
    validation = service.validate_ready_to_generate(draft_id)
    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Required fields missing",
                "fields": validation["missing_fields"]
            }
        )
    
    version = service.generate(draft_id, current_user.user_id)
    return version


@router.get("/drafts/{draft_id}/versions", response_model=VersionListResponse)
async def list_versions(
    draft_id: int,
    current_user = Depends(require_permission(["sow:read"])),
    db: Session = Depends(get_db)
):
    """List all versions of a draft."""
    versions = db.query(SOWVersion).filter(
        SOWVersion.draft_id == draft_id
    ).order_by(SOWVersion.version_number.desc()).all()
    return VersionListResponse(items=versions)


@router.get("/versions/{version_id}/download")
async def download_version(
    version_id: int,
    current_user = Depends(require_permission(["sow:read"])),
    db: Session = Depends(get_db)
):
    """Download generated DOCX."""
    version = db.query(SOWVersion).filter(SOWVersion.id == version_id).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # Get file from storage and return
    pass


# Review endpoints
@router.post("/drafts/{draft_id}/request-review")
async def request_review(
    draft_id: int,
    request: ReviewRequestRequest,
    current_user = Depends(require_permission(["sow:write"])),
    db: Session = Depends(get_db)
):
    """Request Delivery review."""
    service = SOWService(db, current_user.customer_id)
    draft = service.request_review(draft_id, request.notes)
    return draft


@router.post("/drafts/{draft_id}/submit-review")
async def submit_review(
    draft_id: int,
    request: ReviewSubmitRequest,
    current_user = Depends(require_permission(["sow:review"])),
    db: Session = Depends(get_db)
):
    """Submit Delivery review."""
    service = SOWService(db, current_user.customer_id)
    draft = service.submit_review(
        draft_id=draft_id,
        reviewer_id=current_user.user_id,
        status=request.status,
        notes=request.notes,
        field_feedback=request.field_feedback
    )
    return draft
```

**Tests:**
- [ ] All endpoints return correct status codes
- [ ] Multi-tenant filtering works
- [ ] Permission checks enforced

**Checkpoint:** API docs show all endpoints at `/docs`

---

#### Task 4.3: Create Connector Import Endpoints

**Files:**
- `src/api/routes/sow_connectors.py` (new)

**Changes:**
- Implement Fathom call listing and import
- Implement Granola call listing and import
- Implement HubSpot deal listing and linking

**Checkpoint:** Connector endpoints work with test credentials

---

### Phase 5: Connectors (Est: 6-8 hours)

#### Task 5.1: Create Fathom Connector

**Files:**
- `src/services/ingestion/connectors/fathom_connector.py` (new)
- `src/services/ingestion/connectors/__init__.py` (register)

**Changes:**
- Implement `FathomConnector` class
- OAuth 2.0 authentication flow
- List calls with metadata
- Get transcript for specific call
- Format transcript with speaker attribution

**Tests:**
- [ ] Auth flow works with test credentials
- [ ] Call listing returns expected data
- [ ] Transcript retrieval works

**Checkpoint:** Fathom import works end-to-end

---

#### Task 5.2: Create Granola Connector

**Files:**
- `src/services/ingestion/connectors/granola_connector.py` (new)

**Changes:**
- Similar structure to Fathom connector
- Platform-specific API calls

**Checkpoint:** Granola import works end-to-end

---

#### Task 5.3: Create HubSpot SOW Connector

**Files:**
- `src/services/ingestion/connectors/hubspot_sow_connector.py` (new)

**Changes:**
- List deals with filters
- Get deal with associated company/contacts
- Map HubSpot fields to SOW template fields

**Checkpoint:** HubSpot linking works end-to-end

---

### Phase 6: Frontend (Est: 12-16 hours)

#### Task 6.1: Generate API Client

**Files:**
- `frontend/orval.config.ts` (update if needed)
- `frontend/src/api/` (generated)

**Changes:**
1. Run `npm run generate:api`
2. Verify new SOW hooks generated:
   - `useCreateSowDraft`
   - `useListSowDrafts`
   - `useSowDraftStream`
   - etc.

**Checkpoint:** All SOW API hooks available

---

#### Task 6.2: Create SOW Pages

**Files:**
- `frontend/src/pages/sow/DraftListPage.tsx`
- `frontend/src/pages/sow/DraftDetailPage.tsx`
- `frontend/src/pages/sow/TemplateListPage.tsx`
- `frontend/src/pages/sow/TemplateUploadPage.tsx`

**Changes:**
- Implement page layouts
- Wire up navigation
- Add route configuration

**Checkpoint:** Pages accessible via navigation

---

#### Task 6.3: Create Answer Sheet Component

**Files:**
- `frontend/src/components/sow/AnswerSheet.tsx`

**Changes:**
```typescript
// frontend/src/components/sow/AnswerSheet.tsx

interface AnswerSheetProps {
  draftId: number;
  fields: FieldAnswerResponse[];
  onFieldUpdate: (fieldTag: string, value: string) => void;
  onFieldClarify: (fieldTag: string, clarification: string) => void;
}

export function AnswerSheet({
  draftId,
  fields,
  onFieldUpdate,
  onFieldClarify
}: AnswerSheetProps) {
  // Group fields by field_group
  const groupedFields = useMemo(() => {
    return fields.reduce((acc, field) => {
      const group = field.field_group || "Other";
      if (!acc[group]) acc[group] = [];
      acc[group].push(field);
      return acc;
    }, {} as Record<string, FieldAnswerResponse[]>);
  }, [fields]);
  
  return (
    <div className="h-full overflow-y-auto bg-surface-secondary p-4">
      {Object.entries(groupedFields).map(([group, groupFields]) => (
        <FieldGroup
          key={group}
          title={group}
          fields={groupFields}
          onUpdate={onFieldUpdate}
          onClarify={onFieldClarify}
        />
      ))}
    </div>
  );
}
```

**Tests:**
- [ ] Fields display correctly
- [ ] Status indicators visible
- [ ] Edit and clarify work

**Checkpoint:** Answer Sheet renders with test data

---

#### Task 6.4: Create SSE Stream Hook

**Files:**
- `frontend/src/hooks/useSOWStream.ts`

**Changes:**
```typescript
// frontend/src/hooks/useSOWStream.ts

interface SOWStreamEvent {
  event_id: string;
  event_type: string;
  field_tag?: string;
  field_value?: string;
  confidence?: number;
  status?: string;
  message?: string;
  progress_percentage?: number;
  timestamp: string;
}

export function useSOWStream(
  draftId: number | null,
  token: string | null,
  onEvent: (event: SOWStreamEvent) => void
) {
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  
  useEffect(() => {
    if (!draftId || !token) return;
    
    const url = `${API_URL}/api/v1/sow/drafts/${draftId}/stream?token=${token}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;
    
    eventSource.onopen = () => setIsConnected(true);
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data) as SOWStreamEvent;
      onEvent(data);
    };
    
    eventSource.onerror = () => {
      setIsConnected(false);
      eventSource.close();
    };
    
    return () => {
      eventSource.close();
      setIsConnected(false);
    };
  }, [draftId, token, onEvent]);
  
  return { isConnected };
}
```

**Checkpoint:** SSE events received in frontend

---

#### Task 6.5: Create Transcript Uploader Component

**Files:**
- `frontend/src/components/sow/TranscriptUploader.tsx`

**Changes:**
- Paste textarea
- File upload dropzone
- Connector import buttons (Fathom/Granola)
- Name input field

**Checkpoint:** Transcripts can be added via UI

---

#### Task 6.6: Create SOW Chat Component

**Files:**
- `frontend/src/components/sow/SOWChat.tsx`

**Changes:**
- Conversational interface for follow-up questions
- Message history display
- Input field for responses
- Integration with clarification API

**Checkpoint:** Chat interaction works

---

### Phase 7: Integration & Testing (Est: 4-6 hours)

#### Task 7.1: Integration Tests

**Files:**
- `tests/test_sow_integration.py`

**Changes:**
- Test full draft creation to generation flow
- Test multi-tenant isolation
- Test extraction with sample transcripts
- Test connector imports

**Checkpoint:** All integration tests pass

---

#### Task 7.2: E2E Testing

**Manual testing checklist:**
- [ ] Create draft from template
- [ ] Add transcript via paste
- [ ] Start extraction and see SSE updates
- [ ] Answer Sheet updates in real-time
- [ ] Clarify a low-confidence field
- [ ] Generate DOCX and download
- [ ] Request and submit review
- [ ] Import from Fathom (if credentials available)
- [ ] Link HubSpot deal (if credentials available)

**Checkpoint:** Feature works end-to-end in browser

---

## Database Migrations

### Migration 1: Add SOW Automation Tables

**File:** `alembic/versions/xxxx_add_sow_automation_tables.py`

```python
"""Add SOW Automation tables

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-01-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = 'xxxx'
down_revision = 'yyyy'
branch_labels = None
depends_on = None


def upgrade():
    # Create enums
    op.execute("""
        CREATE TYPE sow_draft_status AS ENUM (
            'draft', 'extracting', 'ready', 'generating',
            'review_requested', 'reviewed', 'archived'
        )
    """)
    op.execute("""
        CREATE TYPE sow_review_status AS ENUM (
            'none', 'requested', 'in_review', 'changes_requested', 'approved'
        )
    """)
    op.execute("""
        CREATE TYPE sow_transcript_source AS ENUM (
            'manual_paste', 'manual_upload', 'fathom', 'granola'
        )
    """)
    op.execute("""
        CREATE TYPE sow_field_status AS ENUM (
            'empty', 'auto_filled', 'suggested', 'needs_input',
            'user_provided', 'clarified', 'confirmed'
        )
    """)
    op.execute("""
        CREATE TYPE sow_answer_source AS ENUM (
            'transcript', 'hubspot', 'user_input', 'clarification'
        )
    """)
    op.execute("""
        CREATE TYPE sow_extraction_event_type AS ENUM (
            'extraction_started', 'field_extracted', 'field_confidence_low',
            'followup_generated', 'extraction_completed', 'extraction_failed'
        )
    """)
    
    # Create sow_templates table
    op.create_table(
        'sow_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('customer_id', sa.String(100), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_hash', sa.String(64)),
        sa.Column('schema', JSONB, nullable=False, server_default='{}'),
        sa.Column('is_published', sa.Boolean(), server_default='false'),
        sa.Column('is_archived', sa.Boolean(), server_default='false'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Create sow_template_fields table
    op.create_table(
        'sow_template_fields',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('sow_templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tag_name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('user_guidance', sa.Text()),
        sa.Column('field_type', sa.String(50), server_default='text'),
        sa.Column('is_required', sa.Boolean(), server_default='false'),
        sa.Column('default_value', sa.Text()),
        sa.Column('validation_rules', JSONB, server_default='{}'),
        sa.Column('depends_on', JSONB, server_default='[]'),
        sa.Column('display_order', sa.Integer(), server_default='0'),
        sa.Column('field_group', sa.String(100)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('template_id', 'tag_name', name='uq_template_field_tag'),
    )
    op.create_index('idx_sow_template_fields_template', 'sow_template_fields', ['template_id'])
    
    # Create sow_drafts table
    op.create_table(
        'sow_drafts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('customer_id', sa.String(100), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('opportunity_name', sa.String(255)),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('sow_templates.id')),
        sa.Column('hubspot_company_id', sa.String(100)),
        sa.Column('hubspot_deal_id', sa.String(100)),
        sa.Column('hubspot_snapshot', JSONB),
        sa.Column('status', sa.String(50), server_default='draft'),
        sa.Column('review_status', sa.String(50), server_default='none'),
        sa.Column('reviewer_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('review_notes', sa.Text()),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_sow_drafts_status', 'sow_drafts', ['customer_id', 'status'])
    op.create_index('idx_sow_drafts_created_by', 'sow_drafts', ['created_by'])
    
    # Create sow_transcripts table
    op.create_table(
        'sow_transcripts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('draft_id', sa.Integer(), sa.ForeignKey('sow_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_id', sa.String(255)),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('word_count', sa.Integer()),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('is_processed', sa.Boolean(), server_default='false'),
        sa.Column('processed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_sow_transcripts_draft', 'sow_transcripts', ['draft_id'])
    
    # Create sow_field_answers table
    op.create_table(
        'sow_field_answers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('draft_id', sa.Integer(), sa.ForeignKey('sow_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('field_tag', sa.String(100), nullable=False),
        sa.Column('value', sa.Text()),
        sa.Column('confidence', sa.Numeric(3, 2)),
        sa.Column('source_type', sa.String(50)),
        sa.Column('source_transcript_id', sa.Integer(), sa.ForeignKey('sow_transcripts.id')),
        sa.Column('source_excerpt', sa.Text()),
        sa.Column('status', sa.String(50), server_default='empty'),
        sa.Column('clarification', sa.Text()),
        sa.Column('clarification_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('draft_id', 'field_tag', name='uq_draft_field_answer'),
    )
    op.create_index('idx_sow_field_answers_draft', 'sow_field_answers', ['draft_id'])
    op.create_index('idx_sow_field_answers_status', 'sow_field_answers', ['draft_id', 'status'])
    
    # Create sow_versions table
    op.create_table(
        'sow_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('draft_id', sa.Integer(), sa.ForeignKey('sow_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer()),
        sa.Column('field_snapshot', JSONB, nullable=False),
        sa.Column('is_reviewed', sa.Boolean(), server_default='false'),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('reviewer_notes', sa.Text()),
        sa.Column('generated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('draft_id', 'version_number', name='uq_draft_version'),
    )
    op.create_index('idx_sow_versions_draft', 'sow_versions', ['draft_id'])
    
    # Create sow_extraction_events table
    op.create_table(
        'sow_extraction_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('draft_id', sa.Integer(), sa.ForeignKey('sow_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('field_tag', sa.String(100)),
        sa.Column('data', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_sow_extraction_events_draft', 'sow_extraction_events', ['draft_id'])
    op.create_index('idx_sow_extraction_events_created', 'sow_extraction_events', ['draft_id', 'created_at'])


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
    op.execute('DROP TYPE sow_extraction_event_type')
    op.execute('DROP TYPE sow_answer_source')
    op.execute('DROP TYPE sow_field_status')
    op.execute('DROP TYPE sow_transcript_source')
    op.execute('DROP TYPE sow_review_status')
    op.execute('DROP TYPE sow_draft_status')
```

**Run Order:** Before deploying backend code

---

## Deployment Checklist

### Pre-Deployment

- [ ] All tests passing locally
- [ ] Migration tested on local database
- [ ] Code reviewed and approved
- [ ] Sample DOCX template prepared
- [ ] Documentation updated
- [ ] `docxtpl` added to requirements.txt

### Deployment Steps

1. [ ] Backup database (if production)
2. [ ] Run database migrations: `alembic upgrade head`
3. [ ] Add RBAC permissions to database
4. [ ] Deploy backend: `docker-compose build app celery-worker && docker-compose up -d`
5. [ ] Deploy frontend: `docker-compose build frontend && docker-compose up -d frontend`
6. [ ] Verify health checks pass
7. [ ] Upload sample template via API
8. [ ] Smoke test: create draft, add transcript, extract, generate

### Post-Deployment Verification

- [ ] API endpoints responding correctly: `GET /api/v1/sow/templates`
- [ ] UI loads without errors: Navigate to SOW section
- [ ] Template upload works
- [ ] Draft creation works
- [ ] Transcript extraction processes without errors
- [ ] DOCX generation produces valid file
- [ ] Monitor error rates for 15 minutes
- [ ] Check Celery worker logs for task execution

---

## Rollback Plan

If issues are detected post-deployment:

### Immediate Rollback (< 5 minutes)

1. Revert frontend to previous image
2. Revert backend to previous image
3. Notify team

### Database Rollback (if needed)

1. Run `alembic downgrade -1`
2. Verify application still works
3. Investigate root cause

### Rollback Commands

```bash
# Revert to previous images
docker-compose down
git checkout HEAD~1 -- src/ frontend/
docker-compose build app celery-worker frontend
docker-compose up -d

# Database rollback
docker-compose exec app alembic downgrade -1
```

---

## Progress Tracking

### Overall Progress

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Database & Models | ⬜ Not Started | 0% |
| Phase 2: Service Layer | ⬜ Not Started | 0% |
| Phase 3: Extraction Flow | ⬜ Not Started | 0% |
| Phase 4: API Layer | ⬜ Not Started | 0% |
| Phase 5: Connectors | ⬜ Not Started | 0% |
| Phase 6: Frontend | ⬜ Not Started | 0% |
| Phase 7: Integration & Testing | ⬜ Not Started | 0% |

### Detailed Task Tracking

| Phase | Task | Status | Est Hours | Notes |
|-------|------|--------|-----------|-------|
| 1 | 1.1 Create Migration | ⬜ | 2 | |
| 1 | 1.2 Create Models | ⬜ | 2 | |
| 1 | 1.3 Add RBAC Permissions | ⬜ | 1 | |
| 2 | 2.1 Template Service | ⬜ | 3 | |
| 2 | 2.2 Draft Service | ⬜ | 3 | |
| 2 | 2.3 Generation Service | ⬜ | 2 | |
| 3 | 3.1 Extraction Flow | ⬜ | 6 | Core AI logic |
| 3 | 3.2 Celery Tasks | ⬜ | 2 | |
| 4 | 4.1 Pydantic Schemas | ⬜ | 2 | |
| 4 | 4.2 SOW Routes | ⬜ | 4 | |
| 4 | 4.3 Connector Routes | ⬜ | 2 | |
| 5 | 5.1 Fathom Connector | ⬜ | 3 | |
| 5 | 5.2 Granola Connector | ⬜ | 2 | |
| 5 | 5.3 HubSpot Connector | ⬜ | 3 | |
| 6 | 6.1 API Client | ⬜ | 0.5 | |
| 6 | 6.2 SOW Pages | ⬜ | 4 | |
| 6 | 6.3 Answer Sheet | ⬜ | 4 | |
| 6 | 6.4 SSE Hook | ⬜ | 2 | |
| 6 | 6.5 Transcript Uploader | ⬜ | 2 | |
| 6 | 6.6 SOW Chat | ⬜ | 3 | |
| 7 | 7.1 Integration Tests | ⬜ | 3 | |
| 7 | 7.2 E2E Testing | ⬜ | 3 | |

**Status Legend:** ⬜ Not Started | 🟡 In Progress | ✅ Complete | ❌ Blocked

---

## Dependencies & Risks

### New Python Dependencies

```
# Add to requirements.txt
docxtpl>=0.16.0          # DOCX template rendering
python-docx>=0.8.11      # DOCX manipulation (dependency of docxtpl)
```

### New Frontend Dependencies

None required (uses existing libraries)

### External Dependencies

| Dependency | Risk | Mitigation |
|------------|------|------------|
| Fathom API | API may change | Version pin, monitoring |
| Granola API | API may change | Version pin, monitoring |
| HubSpot API | API may change | Use official SDK |
| OpenAI API | Rate limits | Implement retries, caching |

---

## Notes

- **MVP Scope Reduction (if needed):** Start with manual transcripts only; add connector imports in Phase 2
- **Template Complexity:** Start with simple tags only; complex tables/conditionals can be Phase 2
- **Performance Tuning:** Monitor extraction times; implement chunking if needed for long transcripts

---

*This Implementation Plan provides the detailed roadmap for building SOW Automation. Follow phases in order; update progress tracking as work completes.*
