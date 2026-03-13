"""
Reference Check API Routes

Endpoints for managing reference check requests, templates, personas, and calls.
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models import get_db
from src.middleware.authorization import AuthorizationMiddleware
from src.core.auth_context import CurrentUserContext
from src.core.logging import get_logger, LogCategory
from src.services.reference_check import (
    ReferenceCheckService,
    TwilioService,
    VoiceAgentService,
    SynthesisService
)
from src.models.reference_check import (
    ReferenceRequestStatus,
    ReferenceStatus,
    RelationshipType,
    QuestionType,
    QuestionPriority,
    ScheduledCallStatus
)

logger = get_logger(__name__, LogCategory.API)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/reference-checks", tags=["Reference Checks"])


# ============================================================================
# Pydantic Models
# ============================================================================

# Request Models
class ReferenceCheckRequestCreate(BaseModel):
    """Create a reference check request."""
    candidate_name: str = Field(..., min_length=1, max_length=255)
    candidate_email: str = Field(..., min_length=1, max_length=255)
    candidate_phone: Optional[str] = Field(None, max_length=50)
    job_id: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    greenhouse_candidate_id: Optional[int] = None
    greenhouse_application_id: Optional[int] = None
    candidate_id: Optional[int] = None
    max_references: int = Field(default=10, ge=1, le=20)


class ReferenceCreate(BaseModel):
    """Add a reference."""
    full_name: str = Field(..., min_length=1, max_length=255)
    phone_number: str = Field(..., min_length=1, max_length=50)
    relationship: Optional[RelationshipType] = None
    company: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    preferred_contact_time: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class TemplateQuestionCreate(BaseModel):
    """Question for a template."""
    question_text: str = Field(..., min_length=1)
    question_type: QuestionType = QuestionType.CONCEPT
    priority: QuestionPriority = QuestionPriority.REQUIRED
    order_index: int = 0
    follow_up_enabled: bool = True
    max_follow_ups: int = Field(default=2, ge=0, le=5)
    expected_answer_type: Optional[str] = None


class CallTemplateCreate(BaseModel):
    """Create a call template."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    questions: List[TemplateQuestionCreate]
    is_default: bool = False


class CallTemplateUpdate(BaseModel):
    """Update a call template."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    questions: Optional[List[TemplateQuestionCreate]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class VoicePersonaCreate(BaseModel):
    """Create a voice persona."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    voice_model: str = Field(default="alloy", max_length=100)
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    tone: str = Field(default="professional", max_length=50)
    personality_traits: Optional[dict] = None
    introduction_script: Optional[str] = None
    closing_script: Optional[str] = None
    is_default: bool = False


class ScheduleCallRequest(BaseModel):
    """Schedule a call."""
    reference_id: int
    scheduled_at: datetime
    template_id: Optional[int] = None
    persona_id: Optional[int] = None
    consent_template_id: Optional[int] = None
    reminder_intervals: Optional[List[int]] = None
    caller_id: Optional[str] = None


class CustomerSettingsUpdate(BaseModel):
    """Update customer settings."""
    max_call_duration_seconds: Optional[int] = Field(None, ge=300, le=3600)
    max_references_per_candidate: Optional[int] = Field(None, ge=1, le=20)
    default_reminder_intervals: Optional[List[int]] = None
    default_persona_id: Optional[int] = None
    default_template_id: Optional[int] = None
    default_consent_template: Optional[str] = None
    incomplete_call_action: Optional[str] = None


class CallerIdCreate(BaseModel):
    """Add a caller ID."""
    phone_number: str = Field(..., min_length=10, max_length=50)
    display_name: Optional[str] = Field(None, max_length=100)


class VerifyRequest(BaseModel):
    """Verify candidate identity."""
    verification_token: str
    otp: str


class ReferencesSubmit(BaseModel):
    """Submit references (candidate-facing)."""
    references: List[ReferenceCreate] = Field(..., min_items=1, max_items=10)


# Response Models
class ReferenceCheckRequestResponse(BaseModel):
    """Reference check request response."""
    id: int
    customer_id: str
    candidate_name: str
    candidate_email: str
    candidate_phone: Optional[str]
    job_id: Optional[str]
    job_title: Optional[str]
    status: str
    max_references: int
    reference_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ReferenceResponse(BaseModel):
    """Reference response."""
    id: int
    request_id: int
    full_name: str
    phone_number: str
    relationship: Optional[str]
    company: Optional[str]
    title: Optional[str]
    email: Optional[str]
    status: str
    created_at: str

    class Config:
        from_attributes = True


class TemplateQuestionResponse(BaseModel):
    """Template question response."""
    id: int
    question_text: str
    question_type: str
    priority: str
    order_index: int
    follow_up_enabled: bool
    max_follow_ups: int
    expected_answer_type: Optional[str]

    class Config:
        from_attributes = True


class CallTemplateResponse(BaseModel):
    """Call template response."""
    id: int
    name: str
    description: Optional[str]
    is_default: bool
    is_active: bool
    question_count: int
    questions: List[TemplateQuestionResponse]
    created_at: str

    class Config:
        from_attributes = True


class VoicePersonaResponse(BaseModel):
    """Voice persona response."""
    id: int
    name: str
    description: Optional[str]
    voice_model: str
    speaking_rate: float
    tone: str
    personality_traits: Optional[dict]
    is_default: bool
    created_at: str

    class Config:
        from_attributes = True


class ScheduledCallResponse(BaseModel):
    """Scheduled call response."""
    id: int
    reference_id: int
    reference_name: str
    template_id: Optional[int]
    template_name: Optional[str]
    persona_id: Optional[int]
    persona_name: Optional[str]
    scheduled_at: str
    status: str
    reminder_24h_sent: bool
    reminder_2h_sent: bool
    reminder_15m_sent: bool
    created_at: str

    class Config:
        from_attributes = True


class CallResponse(BaseModel):
    """Call response."""
    id: int
    scheduled_call_id: Optional[int]
    reference_id: Optional[int]
    reference_name: Optional[str]
    call_type: str
    call_status: Optional[str]
    consent_obtained: bool
    started_at: Optional[str]
    ended_at: Optional[str]
    duration_seconds: Optional[int]
    is_complete: bool
    has_recording: bool
    has_transcript: bool
    has_summary: bool
    created_at: str

    class Config:
        from_attributes = True


class CallDetailResponse(BaseModel):
    """Detailed call response with transcript and summary."""
    id: int
    reference_name: str
    candidate_name: str
    call_type: str
    call_status: Optional[str]
    consent_obtained: bool
    duration_seconds: Optional[int]
    recording_url: Optional[str]
    transcript: Optional[dict]
    question_responses: List[dict]
    summary: Optional[dict]
    created_at: str

    class Config:
        from_attributes = True


class CustomerSettingsResponse(BaseModel):
    """Customer settings response."""
    max_call_duration_seconds: int
    hard_limit_seconds: int
    max_references_per_candidate: int
    default_reminder_intervals: List[int]
    default_persona_id: Optional[int]
    default_template_id: Optional[int]
    default_consent_template: str
    incomplete_call_action: str

    class Config:
        from_attributes = True


class CallerIdResponse(BaseModel):
    """Caller ID response."""
    id: int
    phone_number: str
    display_name: Optional[str]
    is_verified: bool
    is_default: bool
    created_at: str

    class Config:
        from_attributes = True


class ConsentTemplateResponse(BaseModel):
    """Consent template response."""
    id: int
    jurisdiction: str
    consent_script: str
    requires_explicit_consent: bool
    legal_notes: Optional[str]

    class Config:
        from_attributes = True


# ============================================================================
# Reference Check Request Endpoints
# ============================================================================

@router.post("/requests", response_model=ReferenceCheckRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    data: ReferenceCheckRequestCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Create a new reference check request."""
    service = ReferenceCheckService(db)
    
    request = await service.create_request(
        customer_id=current_user.customer_id,
        candidate_name=data.candidate_name,
        candidate_email=data.candidate_email,
        candidate_phone=data.candidate_phone,
        job_id=data.job_id,
        job_title=data.job_title,
        greenhouse_candidate_id=data.greenhouse_candidate_id,
        greenhouse_application_id=data.greenhouse_application_id,
        candidate_id=data.candidate_id,
        max_references=data.max_references,
        created_by_user_id=current_user.user_id
    )
    
    return ReferenceCheckRequestResponse(
        id=request.id,
        customer_id=request.customer_id,
        candidate_name=request.candidate_name,
        candidate_email=request.candidate_email,
        candidate_phone=request.candidate_phone,
        job_id=request.job_id,
        job_title=request.job_title,
        status=request.status.value,
        max_references=request.max_references,
        reference_count=len(request.references),
        created_at=request.created_at.isoformat(),
        updated_at=request.updated_at.isoformat()
    )


@router.get("/requests", response_model=List[ReferenceCheckRequestResponse])
async def list_requests(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List reference check requests."""
    service = ReferenceCheckService(db)
    
    status_enum = ReferenceRequestStatus(status) if status else None
    
    requests = await service.list_requests(
        customer_id=current_user.customer_id,
        status=status_enum,
        skip=skip,
        limit=limit
    )
    
    return [
        ReferenceCheckRequestResponse(
            id=r.id,
            customer_id=r.customer_id,
            candidate_name=r.candidate_name,
            candidate_email=r.candidate_email,
            candidate_phone=r.candidate_phone,
            job_id=r.job_id,
            job_title=r.job_title,
            status=r.status.value,
            max_references=r.max_references,
            reference_count=len(r.references),
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat()
        )
        for r in requests
    ]


@router.get("/requests/{request_id}", response_model=ReferenceCheckRequestResponse)
async def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get a reference check request."""
    service = ReferenceCheckService(db)
    
    request = await service.get_request(request_id, current_user.customer_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    return ReferenceCheckRequestResponse(
        id=request.id,
        customer_id=request.customer_id,
        candidate_name=request.candidate_name,
        candidate_email=request.candidate_email,
        candidate_phone=request.candidate_phone,
        job_id=request.job_id,
        job_title=request.job_title,
        status=request.status.value,
        max_references=request.max_references,
        reference_count=len(request.references),
        created_at=request.created_at.isoformat(),
        updated_at=request.updated_at.isoformat()
    )


@router.post("/requests/{request_id}/send-form")
async def send_reference_form(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Send reference collection form to candidate."""
    service = ReferenceCheckService(db)
    twilio_service = TwilioService(db)
    
    request = await service.get_request(request_id, current_user.customer_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # TODO: Send SMS with link to reference form
    # For now, just update status
    await service.update_request_status(
        request_id=request_id,
        customer_id=current_user.customer_id,
        status=ReferenceRequestStatus.REFERENCES_REQUESTED,
        user_id=current_user.user_id
    )
    
    return {
        "message": "Reference form sent",
        "verification_link": f"/reference-form/{request.verification_token}"
    }


# ============================================================================
# Reference Endpoints
# ============================================================================

@router.get("/requests/{request_id}/references", response_model=List[ReferenceResponse])
async def list_references(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List references for a request."""
    service = ReferenceCheckService(db)
    
    # Verify request belongs to customer
    request = await service.get_request(request_id, current_user.customer_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    references = await service.list_references(request_id)
    
    return [
        ReferenceResponse(
            id=r.id,
            request_id=r.request_id,
            full_name=r.full_name,
            phone_number=r.phone_number,
            relationship=r.relationship_type.value if r.relationship_type else None,
            company=r.company,
            title=r.title,
            email=r.email,
            status=r.status.value,
            created_at=r.created_at.isoformat()
        )
        for r in references
    ]


@router.post("/verify")
async def verify_candidate(
    data: VerifyRequest,
    db: Session = Depends(get_db)
):
    """Verify candidate identity for reference submission (public endpoint)."""
    service = ReferenceCheckService(db)
    
    request = await service.verify_candidate(data.verification_token, data.otp)
    if not request:
        raise HTTPException(status_code=400, detail="Invalid or expired verification")
    
    return {
        "verified": True,
        "request_id": request.id,
        "candidate_name": request.candidate_name,
        "max_references": request.max_references
    }


@router.post("/references")
async def submit_references(
    data: ReferencesSubmit,
    verification_token: str,
    db: Session = Depends(get_db)
):
    """Submit references (candidate-facing, public endpoint)."""
    from src.models.reference_check import ReferenceCheckRequest
    
    # Find request by token
    request = db.query(ReferenceCheckRequest).filter(
        ReferenceCheckRequest.verification_token == verification_token,
        ReferenceCheckRequest.verified_at.isnot(None)
    ).first()
    
    if not request:
        raise HTTPException(status_code=400, detail="Invalid verification")
    
    service = ReferenceCheckService(db)
    
    # Check capacity
    current_count = len(request.references)
    if current_count + len(data.references) > request.max_references:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {request.max_references} references allowed"
        )
    
    # Add references
    added = []
    for ref in data.references:
        reference = await service.add_reference(
            request_id=request.id,
            full_name=ref.full_name,
            phone_number=ref.phone_number,
            relationship=ref.relationship,
            company=ref.company,
            title=ref.title,
            email=ref.email,
            preferred_contact_time=ref.preferred_contact_time,
            notes=ref.notes
        )
        added.append(reference.id)
    
    return {
        "submitted": len(added),
        "reference_ids": added
    }


# ============================================================================
# Template Endpoints
# ============================================================================

@router.post("/templates", response_model=CallTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: CallTemplateCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Create a call template."""
    service = ReferenceCheckService(db)
    
    questions = [q.model_dump() for q in data.questions]
    
    template = await service.create_template(
        customer_id=current_user.customer_id,
        name=data.name,
        description=data.description,
        questions=questions,
        is_default=data.is_default,
        created_by_user_id=current_user.user_id
    )
    
    return CallTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        is_default=template.is_default,
        is_active=template.is_active,
        question_count=len(template.questions),
        questions=[
            TemplateQuestionResponse(
                id=q.id,
                question_text=q.question_text,
                question_type=q.question_type.value,
                priority=q.priority.value,
                order_index=q.order_index,
                follow_up_enabled=q.follow_up_enabled,
                max_follow_ups=q.max_follow_ups,
                expected_answer_type=q.expected_answer_type
            )
            for q in template.questions
        ],
        created_at=template.created_at.isoformat()
    )


@router.get("/templates", response_model=List[CallTemplateResponse])
async def list_templates(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List call templates."""
    service = ReferenceCheckService(db)
    
    templates = await service.list_templates(
        customer_id=current_user.customer_id,
        active_only=active_only
    )
    
    return [
        CallTemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            is_default=t.is_default,
            is_active=t.is_active,
            question_count=len(t.questions),
            questions=[
                TemplateQuestionResponse(
                    id=q.id,
                    question_text=q.question_text,
                    question_type=q.question_type.value,
                    priority=q.priority.value,
                    order_index=q.order_index,
                    follow_up_enabled=q.follow_up_enabled,
                    max_follow_ups=q.max_follow_ups,
                    expected_answer_type=q.expected_answer_type
                )
                for q in t.questions
            ],
            created_at=t.created_at.isoformat()
        )
        for t in templates
    ]


@router.get("/templates/{template_id}", response_model=CallTemplateResponse)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get a call template."""
    service = ReferenceCheckService(db)
    
    template = await service.get_template(template_id, current_user.customer_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return CallTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        is_default=template.is_default,
        is_active=template.is_active,
        question_count=len(template.questions),
        questions=[
            TemplateQuestionResponse(
                id=q.id,
                question_text=q.question_text,
                question_type=q.question_type.value,
                priority=q.priority.value,
                order_index=q.order_index,
                follow_up_enabled=q.follow_up_enabled,
                max_follow_ups=q.max_follow_ups,
                expected_answer_type=q.expected_answer_type
            )
            for q in template.questions
        ],
        created_at=template.created_at.isoformat()
    )


@router.put("/templates/{template_id}", response_model=CallTemplateResponse)
async def update_template(
    template_id: int,
    data: CallTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Update a call template."""
    service = ReferenceCheckService(db)
    
    questions = [q.model_dump() for q in data.questions] if data.questions else None
    
    template = await service.update_template(
        template_id=template_id,
        customer_id=current_user.customer_id,
        name=data.name,
        description=data.description,
        questions=questions,
        is_default=data.is_default,
        is_active=data.is_active
    )
    
    return CallTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        is_default=template.is_default,
        is_active=template.is_active,
        question_count=len(template.questions),
        questions=[
            TemplateQuestionResponse(
                id=q.id,
                question_text=q.question_text,
                question_type=q.question_type.value,
                priority=q.priority.value,
                order_index=q.order_index,
                follow_up_enabled=q.follow_up_enabled,
                max_follow_ups=q.max_follow_ups,
                expected_answer_type=q.expected_answer_type
            )
            for q in template.questions
        ],
        created_at=template.created_at.isoformat()
    )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Delete a call template (soft delete)."""
    service = ReferenceCheckService(db)
    
    await service.delete_template(template_id, current_user.customer_id)
    
    return {"deleted": True}


# ============================================================================
# Persona Endpoints
# ============================================================================

@router.post("/personas", response_model=VoicePersonaResponse, status_code=status.HTTP_201_CREATED)
async def create_persona(
    data: VoicePersonaCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Create a voice persona."""
    service = ReferenceCheckService(db)
    
    persona = await service.create_persona(
        customer_id=current_user.customer_id,
        name=data.name,
        description=data.description,
        voice_model=data.voice_model,
        speaking_rate=data.speaking_rate,
        tone=data.tone,
        personality_traits=data.personality_traits,
        introduction_script=data.introduction_script,
        closing_script=data.closing_script,
        is_default=data.is_default
    )
    
    return VoicePersonaResponse(
        id=persona.id,
        name=persona.name,
        description=persona.description,
        voice_model=persona.voice_model,
        speaking_rate=persona.speaking_rate,
        tone=persona.tone,
        personality_traits=persona.personality_traits,
        is_default=persona.is_default,
        created_at=persona.created_at.isoformat()
    )


@router.get("/personas", response_model=List[VoicePersonaResponse])
async def list_personas(
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List voice personas."""
    service = ReferenceCheckService(db)
    
    personas = await service.list_personas(current_user.customer_id)
    
    return [
        VoicePersonaResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            voice_model=p.voice_model,
            speaking_rate=p.speaking_rate,
            tone=p.tone,
            personality_traits=p.personality_traits,
            is_default=p.is_default,
            created_at=p.created_at.isoformat()
        )
        for p in personas
    ]


# ============================================================================
# Call Scheduling Endpoints
# ============================================================================

@router.post("/calls/schedule", response_model=ScheduledCallResponse, status_code=status.HTTP_201_CREATED)
async def schedule_call(
    data: ScheduleCallRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Schedule a reference check call."""
    service = ReferenceCheckService(db)
    
    scheduled_call = await service.schedule_call(
        reference_id=data.reference_id,
        scheduled_at=data.scheduled_at,
        template_id=data.template_id,
        persona_id=data.persona_id,
        consent_template_id=data.consent_template_id,
        reminder_intervals=data.reminder_intervals,
        caller_id=data.caller_id,
        created_by_user_id=current_user.user_id
    )
    
    return ScheduledCallResponse(
        id=scheduled_call.id,
        reference_id=scheduled_call.reference_id,
        reference_name=scheduled_call.reference.full_name,
        template_id=scheduled_call.template_id,
        template_name=scheduled_call.template.name if scheduled_call.template else None,
        persona_id=scheduled_call.persona_id,
        persona_name=scheduled_call.persona.name if scheduled_call.persona else None,
        scheduled_at=scheduled_call.scheduled_at.isoformat(),
        status=scheduled_call.status.value,
        reminder_24h_sent=scheduled_call.reminder_24h_sent,
        reminder_2h_sent=scheduled_call.reminder_2h_sent,
        reminder_15m_sent=scheduled_call.reminder_15m_sent,
        created_at=scheduled_call.created_at.isoformat()
    )


@router.get("/calls/scheduled", response_model=List[ScheduledCallResponse])
async def list_scheduled_calls(
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List scheduled calls."""
    service = ReferenceCheckService(db)
    
    status_enum = ScheduledCallStatus(status) if status else None
    
    calls = await service.list_scheduled_calls(
        customer_id=current_user.customer_id,
        status=status_enum,
        from_date=from_date,
        to_date=to_date
    )
    
    return [
        ScheduledCallResponse(
            id=c.id,
            reference_id=c.reference_id,
            reference_name=c.reference.full_name,
            template_id=c.template_id,
            template_name=c.template.name if c.template else None,
            persona_id=c.persona_id,
            persona_name=c.persona.name if c.persona else None,
            scheduled_at=c.scheduled_at.isoformat(),
            status=c.status.value,
            reminder_24h_sent=c.reminder_24h_sent,
            reminder_2h_sent=c.reminder_2h_sent,
            reminder_15m_sent=c.reminder_15m_sent,
            created_at=c.created_at.isoformat()
        )
        for c in calls
    ]


@router.delete("/calls/scheduled/{scheduled_call_id}")
async def cancel_scheduled_call(
    scheduled_call_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Cancel a scheduled call."""
    service = ReferenceCheckService(db)
    
    await service.cancel_scheduled_call(scheduled_call_id, current_user.user_id)
    
    return {"cancelled": True}


# ============================================================================
# Call Endpoints
# ============================================================================

@router.get("/calls", response_model=List[CallResponse])
async def list_calls(
    reference_id: Optional[int] = None,
    request_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List calls."""
    service = ReferenceCheckService(db)
    
    calls = await service.list_calls(
        customer_id=current_user.customer_id,
        reference_id=reference_id,
        request_id=request_id
    )
    
    return [
        CallResponse(
            id=c.id,
            scheduled_call_id=c.scheduled_call_id,
            reference_id=c.reference_id,
            reference_name=c.reference.full_name if c.reference else None,
            call_type=c.call_type.value,
            call_status=c.call_status.value if c.call_status else None,
            consent_obtained=c.consent_obtained,
            started_at=c.started_at.isoformat() if c.started_at else None,
            ended_at=c.ended_at.isoformat() if c.ended_at else None,
            duration_seconds=c.duration_seconds,
            is_complete=c.is_complete,
            has_recording=c.recording_url is not None,
            has_transcript=c.transcript is not None,
            has_summary=c.summary is not None,
            created_at=c.created_at.isoformat()
        )
        for c in calls
    ]


@router.get("/calls/{call_id}", response_model=CallDetailResponse)
async def get_call_detail(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get detailed call information including transcript and summary."""
    service = ReferenceCheckService(db)
    
    call = await service.get_call(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Verify access
    if call.reference and call.reference.request.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    transcript_data = None
    if call.transcript:
        transcript_data = {
            "full_transcript": call.transcript.full_transcript,
            "segments": call.transcript.transcript_segments,
            "word_timestamps": call.transcript.word_timestamps
        }
    
    summary_data = None
    if call.summary:
        summary_data = {
            "executive_summary": call.summary.executive_summary,
            "key_strengths": call.summary.key_strengths,
            "areas_of_concern": call.summary.areas_of_concern,
            "notable_quotes": call.summary.notable_quotes,
            "overall_sentiment": call.summary.overall_sentiment,
            "recommendation_score": call.summary.recommendation_score,
            "recommendation_notes": call.summary.recommendation_notes
        }
    
    question_responses = [
        {
            "question_asked": qr.question_asked,
            "response_text": qr.response_text,
            "sentiment": qr.response_sentiment,
            "start_time": qr.transcript_start_time,
            "end_time": qr.transcript_end_time,
            "follow_ups": qr.follow_up_questions
        }
        for qr in call.question_responses
    ]
    
    return CallDetailResponse(
        id=call.id,
        reference_name=call.reference.full_name if call.reference else "Unknown",
        candidate_name=call.reference.request.candidate_name if call.reference else "Unknown",
        call_type=call.call_type.value,
        call_status=call.call_status.value if call.call_status else None,
        consent_obtained=call.consent_obtained,
        duration_seconds=call.duration_seconds,
        recording_url=call.recording_url,
        transcript=transcript_data,
        question_responses=question_responses,
        summary=summary_data,
        created_at=call.created_at.isoformat()
    )


@router.get("/calls/{call_id}/recording")
async def get_call_recording(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get signed URL for call recording."""
    service = ReferenceCheckService(db)
    
    call = await service.get_call(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    if not call.recording_url:
        raise HTTPException(status_code=404, detail="No recording available")
    
    # Verify access
    if call.reference and call.reference.request.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # TODO: Generate signed URL with expiration
    return {"recording_url": call.recording_url}


# ============================================================================
# Settings Endpoints
# ============================================================================

@router.get("/settings", response_model=CustomerSettingsResponse)
async def get_settings(
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get customer call settings."""
    service = ReferenceCheckService(db)
    
    settings = await service.get_or_create_customer_settings(current_user.customer_id)
    
    return CustomerSettingsResponse(
        max_call_duration_seconds=settings.max_call_duration_seconds,
        hard_limit_seconds=settings.hard_limit_seconds,
        max_references_per_candidate=settings.max_references_per_candidate,
        default_reminder_intervals=settings.default_reminder_intervals,
        default_persona_id=settings.default_persona_id,
        default_template_id=settings.default_template_id,
        default_consent_template=settings.default_consent_template,
        incomplete_call_action=settings.incomplete_call_action
    )


@router.put("/settings", response_model=CustomerSettingsResponse)
async def update_settings(
    data: CustomerSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Update customer call settings."""
    service = ReferenceCheckService(db)
    
    settings = await service.update_customer_settings(
        customer_id=current_user.customer_id,
        **data.model_dump(exclude_unset=True)
    )
    
    return CustomerSettingsResponse(
        max_call_duration_seconds=settings.max_call_duration_seconds,
        hard_limit_seconds=settings.hard_limit_seconds,
        max_references_per_candidate=settings.max_references_per_candidate,
        default_reminder_intervals=settings.default_reminder_intervals,
        default_persona_id=settings.default_persona_id,
        default_template_id=settings.default_template_id,
        default_consent_template=settings.default_consent_template,
        incomplete_call_action=settings.incomplete_call_action
    )


# ============================================================================
# Caller ID Endpoints
# ============================================================================

@router.post("/caller-ids", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_caller_id(
    data: CallerIdCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Add a caller ID (initiates verification)."""
    twilio_service = TwilioService(db)
    
    result = await twilio_service.add_caller_id(
        customer_id=current_user.customer_id,
        phone_number=data.phone_number,
        display_name=data.display_name
    )
    
    return result


@router.get("/caller-ids", response_model=List[CallerIdResponse])
async def list_caller_ids(
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List verified caller IDs."""
    twilio_service = TwilioService(db)
    
    caller_ids = await twilio_service.list_verified_caller_ids(current_user.customer_id)
    
    return [
        CallerIdResponse(
            id=cid["id"],
            phone_number=cid["phone_number"],
            display_name=cid.get("display_name"),
            is_verified=True,
            is_default=cid["is_default"],
            created_at=cid["created_at"]
        )
        for cid in caller_ids
    ]


@router.post("/caller-ids/{caller_id_id}/verify")
async def verify_caller_id(
    caller_id_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Check if caller ID is verified."""
    twilio_service = TwilioService(db)
    
    verified = await twilio_service.verify_caller_id(
        customer_id=current_user.customer_id,
        caller_id_id=caller_id_id
    )
    
    return {"verified": verified}


@router.post("/caller-ids/{caller_id_id}/set-default")
async def set_default_caller_id(
    caller_id_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Set a caller ID as default."""
    twilio_service = TwilioService(db)
    
    await twilio_service.set_default_caller_id(
        customer_id=current_user.customer_id,
        caller_id_id=caller_id_id
    )
    
    return {"success": True}


@router.delete("/caller-ids/{caller_id_id}")
async def delete_caller_id(
    caller_id_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Delete a caller ID."""
    twilio_service = TwilioService(db)
    
    await twilio_service.delete_caller_id(
        customer_id=current_user.customer_id,
        caller_id_id=caller_id_id
    )
    
    return {"deleted": True}


# ============================================================================
# Consent Template Endpoints
# ============================================================================

@router.get("/consent-templates", response_model=List[ConsentTemplateResponse])
async def list_consent_templates(
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List available consent templates."""
    from src.models.reference_check import ReferenceConsentTemplate
    
    templates = db.query(ReferenceConsentTemplate).filter(
        ReferenceConsentTemplate.is_active == True
    ).all()
    
    return [
        ConsentTemplateResponse(
            id=t.id,
            jurisdiction=t.jurisdiction,
            consent_script=t.consent_script,
            requires_explicit_consent=t.requires_explicit_consent,
            legal_notes=t.legal_notes
        )
        for t in templates
    ]


# ============================================================================
# Playground Endpoints
# ============================================================================

class PlaygroundSessionCreate(BaseModel):
    """Create a playground session."""
    template_id: int
    persona_id: int


class PlaygroundSessionResponse(BaseModel):
    """Playground session response."""
    session_id: str
    websocket_url: str


@router.post("/playground/session", response_model=PlaygroundSessionResponse)
async def create_playground_session(
    data: PlaygroundSessionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """
    Create a playground session for testing the voice agent.
    
    Returns a session ID and WebSocket URL for connecting.
    """
    service = ReferenceCheckService(db)
    voice_agent_service = VoiceAgentService(db)
    
    # Verify template and persona exist and belong to customer
    template = await service.get_template(data.template_id, current_user.customer_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    personas = await service.list_personas(current_user.customer_id)
    persona = next((p for p in personas if p.id == data.persona_id), None)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    # Create test session
    session_data = await voice_agent_service.create_session(
        template_id=data.template_id,
        persona_id=data.persona_id,
        customer_id=current_user.customer_id,
        is_test=True
    )
    
    # Build WebSocket URL
    host = request.headers.get("host", "localhost:5001")
    protocol = "wss" if request.url.scheme == "https" else "ws"
    websocket_url = f"{protocol}://{host}/api/v1/reference-checks/webhooks/playground/{session_data['session_id']}"
    
    return PlaygroundSessionResponse(
        session_id=session_data["session_id"],
        websocket_url=websocket_url
    )

