"""
Reference Check Models

SQLAlchemy models for the Reference Check Voice Agent feature:
- ReferenceCheckRequest: Request to collect references from a candidate
- CandidateReference: Individual reference submitted by candidate
- ReferenceCallTemplate: Templates defining questions for calls
- ReferenceTemplateQuestion: Individual questions in a template
- ReferenceVoicePersona: Voice agent personality configurations
- ReferenceConsentTemplate: Recording consent scripts by jurisdiction
- ReferenceScheduledCall: Scheduled reference check calls
- ReferenceCall: Actual call records
- ReferenceCallTranscript: Call transcripts with timestamps
- ReferenceQuestionResponse: Extracted Q&A from calls
- ReferenceCallSummary: AI-generated call summaries
- ReferenceCheckAuditLog: Audit trail for all actions
- CustomerCallerId: Verified caller IDs per customer
- CustomerCallSettings: Customer-level call settings
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Text, DateTime, ForeignKey,
    Boolean, UniqueConstraint, Index, Enum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.database import Base


# ============================================================================
# Enums
# ============================================================================

class ReferenceRequestStatus(str, PyEnum):
    """Status of a reference check request."""
    PENDING = "pending"
    REFERENCES_REQUESTED = "references_requested"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReferenceStatus(str, PyEnum):
    """Status of an individual reference."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DECLINED = "declined"
    VOICEMAIL = "voicemail"
    CALLBACK_PENDING = "callback_pending"


class RelationshipType(str, PyEnum):
    """Type of relationship between reference and candidate."""
    DIRECT_MANAGER = "direct_manager"
    COLLEAGUE = "colleague"
    DIRECT_REPORT = "direct_report"
    CLIENT = "client"
    OTHER = "other"


class QuestionType(str, PyEnum):
    """Type of question - verbatim or concept."""
    VERBATIM = "verbatim"
    CONCEPT = "concept"


class QuestionPriority(str, PyEnum):
    """Priority of a question."""
    REQUIRED = "required"
    OPTIONAL = "optional"


class CallStatus(str, PyEnum):
    """Status of a call."""
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    VOICEMAIL = "voicemail"


class CallType(str, PyEnum):
    """Type of call."""
    OUTBOUND = "outbound"
    INBOUND_CALLBACK = "inbound_callback"
    TEST = "test"
    SANDBOX = "sandbox"


class ScheduledCallStatus(str, PyEnum):
    """Status of a scheduled call."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VOICEMAIL = "voicemail"
    CALLBACK_PENDING = "callback_pending"
    CANCELLED = "cancelled"


# ============================================================================
# Models
# ============================================================================

class ReferenceCheckRequest(Base):
    """
    Request to collect references for a candidate.
    
    Initiated by hiring manager, sends form to candidate to submit references.
    """
    __tablename__ = 'reference_check_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(100), ForeignKey('customers.customer_id'), nullable=False)
    
    # Candidate info
    candidate_id = Column(Integer, ForeignKey('candidates.id'), nullable=True)
    candidate_name = Column(String(255), nullable=False)
    candidate_email = Column(String(255), nullable=False)
    candidate_phone = Column(String(50), nullable=True)
    
    # Job context
    job_id = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)
    
    # Greenhouse integration
    greenhouse_candidate_id = Column(BigInteger, nullable=True)
    greenhouse_application_id = Column(BigInteger, nullable=True)
    
    # Status
    status = Column(
        Enum(ReferenceRequestStatus),
        default=ReferenceRequestStatus.PENDING,
        nullable=False
    )
    max_references = Column(Integer, default=10, nullable=False)
    
    # Verification
    verification_token = Column(String(255), unique=True, nullable=True)
    verification_expires_at = Column(DateTime(timezone=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Created by
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    references = relationship("CandidateReference", back_populates="request", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    
    __table_args__ = (
        Index('ix_rcr_customer_id', 'customer_id'),
        Index('ix_rcr_candidate_id', 'candidate_id'),
        Index('ix_rcr_status', 'status'),
        Index('ix_rcr_verification_token', 'verification_token'),
    )
    
    def __repr__(self):
        return f"<ReferenceCheckRequest(id={self.id}, candidate='{self.candidate_name}', status='{self.status}')>"


class CandidateReference(Base):
    """
    Individual reference submitted by a candidate.
    """
    __tablename__ = 'candidate_references'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey('reference_check_requests.id', ondelete='CASCADE'), nullable=False)
    
    # Reference details
    full_name = Column(String(255), nullable=False)
    relationship_type = Column(Enum(RelationshipType), nullable=True)
    company = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=False)
    email = Column(String(255), nullable=True)
    preferred_contact_time = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Status
    status = Column(
        Enum(ReferenceStatus),
        default=ReferenceStatus.PENDING,
        nullable=False
    )
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    request = relationship("ReferenceCheckRequest", back_populates="references")
    scheduled_calls = relationship("ReferenceScheduledCall", back_populates="reference", cascade="all, delete-orphan")
    calls = relationship("ReferenceCall", back_populates="reference", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_cr_request_id', 'request_id'),
        Index('ix_cr_phone_number', 'phone_number'),
        Index('ix_cr_status', 'status'),
    )
    
    def __repr__(self):
        return f"<CandidateReference(id={self.id}, name='{self.full_name}', status='{self.status}')>"


class ReferenceCallTemplate(Base):
    """
    Template defining questions for reference check calls.
    """
    __tablename__ = 'reference_call_templates'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(100), ForeignKey('customers.customer_id'), nullable=False)
    
    # Template details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Created by
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    questions = relationship(
        "ReferenceTemplateQuestion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ReferenceTemplateQuestion.order_index"
    )
    
    __table_args__ = (
        Index('ix_rct_customer_id', 'customer_id'),
        Index('ix_rct_is_default', 'is_default'),
        Index('ix_rct_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<ReferenceCallTemplate(id={self.id}, name='{self.name}')>"


class ReferenceTemplateQuestion(Base):
    """
    Individual question in a call template.
    """
    __tablename__ = 'reference_template_questions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey('reference_call_templates.id', ondelete='CASCADE'), nullable=False)
    
    # Question details
    question_text = Column(Text, nullable=False)
    question_type = Column(
        Enum(QuestionType),
        default=QuestionType.CONCEPT,
        nullable=False
    )
    priority = Column(
        Enum(QuestionPriority),
        default=QuestionPriority.REQUIRED,
        nullable=False
    )
    order_index = Column(Integer, nullable=False)
    
    # Follow-up settings
    follow_up_enabled = Column(Boolean, default=True, nullable=False)
    max_follow_ups = Column(Integer, default=2, nullable=False)
    
    # Expected answer type
    expected_answer_type = Column(String(50), nullable=True)  # 'rating', 'yes_no', 'open_ended', 'examples'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    template = relationship("ReferenceCallTemplate", back_populates="questions")
    
    __table_args__ = (
        Index('ix_rtq_template_id', 'template_id'),
    )
    
    def __repr__(self):
        return f"<ReferenceTemplateQuestion(id={self.id}, order={self.order_index})>"


class ReferenceVoicePersona(Base):
    """
    Voice agent personality configuration.
    """
    __tablename__ = 'reference_voice_personas'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(100), ForeignKey('customers.customer_id'), nullable=False)
    
    # Persona details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Voice settings
    voice_model = Column(String(100), default='alloy', nullable=False)  # OpenAI voice options
    speaking_rate = Column(Float, default=1.0, nullable=False)  # 0.5 to 2.0
    tone = Column(String(50), default='professional', nullable=False)  # professional, friendly, formal, casual
    personality_traits = Column(JSONB, nullable=True)  # {"warmth": 0.7, "directness": 0.8, ...}
    
    # Scripts
    introduction_script = Column(Text, nullable=True)
    closing_script = Column(Text, nullable=True)
    
    # Settings
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_rvp_customer_id', 'customer_id'),
        Index('ix_rvp_is_default', 'is_default'),
    )
    
    def __repr__(self):
        return f"<ReferenceVoicePersona(id={self.id}, name='{self.name}')>"


class ReferenceConsentTemplate(Base):
    """
    Recording consent scripts by jurisdiction.
    """
    __tablename__ = 'reference_consent_templates'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Jurisdiction
    jurisdiction = Column(String(100), nullable=False, unique=True)  # 'us_one_party', 'california', etc.
    
    # Consent details
    consent_script = Column(Text, nullable=False)
    requires_explicit_consent = Column(Boolean, default=True, nullable=False)
    legal_notes = Column(Text, nullable=True)
    
    # Settings
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_rconst_jurisdiction', 'jurisdiction'),
        Index('ix_rconst_is_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<ReferenceConsentTemplate(id={self.id}, jurisdiction='{self.jurisdiction}')>"


class ReferenceScheduledCall(Base):
    """
    Scheduled reference check call.
    """
    __tablename__ = 'reference_scheduled_calls'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_id = Column(Integer, ForeignKey('candidate_references.id', ondelete='CASCADE'), nullable=False)
    
    # Configuration
    template_id = Column(Integer, ForeignKey('reference_call_templates.id'), nullable=True)
    persona_id = Column(Integer, ForeignKey('reference_voice_personas.id'), nullable=True)
    consent_template_id = Column(Integer, ForeignKey('reference_consent_templates.id'), nullable=True)
    
    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    reminder_intervals = Column(JSONB, default=[86400, 7200, 900], nullable=False)  # seconds before call
    
    # Reminder tracking
    reminder_24h_sent = Column(Boolean, default=False, nullable=False)
    reminder_2h_sent = Column(Boolean, default=False, nullable=False)
    reminder_15m_sent = Column(Boolean, default=False, nullable=False)
    
    # Caller ID
    caller_id = Column(String(50), nullable=True)  # Verified Twilio number
    
    # Status
    status = Column(
        Enum(ScheduledCallStatus),
        default=ScheduledCallStatus.SCHEDULED,
        nullable=False
    )
    
    # Created by
    created_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    reference = relationship("CandidateReference", back_populates="scheduled_calls")
    template = relationship("ReferenceCallTemplate")
    persona = relationship("ReferenceVoicePersona")
    consent_template = relationship("ReferenceConsentTemplate")
    calls = relationship("ReferenceCall", back_populates="scheduled_call", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_rsc_reference_id', 'reference_id'),
        Index('ix_rsc_scheduled_at', 'scheduled_at'),
        Index('ix_rsc_status', 'status'),
    )
    
    def __repr__(self):
        return f"<ReferenceScheduledCall(id={self.id}, scheduled_at='{self.scheduled_at}', status='{self.status}')>"


class ReferenceCall(Base):
    """
    Actual call record.
    """
    __tablename__ = 'reference_calls'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    scheduled_call_id = Column(Integer, ForeignKey('reference_scheduled_calls.id'), nullable=True)
    reference_id = Column(Integer, ForeignKey('candidate_references.id'), nullable=True)
    
    # Twilio info
    twilio_call_sid = Column(String(100), unique=True, nullable=True)
    
    # Call details
    call_type = Column(
        Enum(CallType),
        default=CallType.OUTBOUND,
        nullable=False
    )
    call_status = Column(Enum(CallStatus), nullable=True)
    
    # Consent
    consent_obtained = Column(Boolean, default=False, nullable=False)
    consent_timestamp = Column(DateTime(timezone=True), nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Recording
    recording_url = Column(Text, nullable=True)
    recording_duration_seconds = Column(Integer, nullable=True)
    recording_sid = Column(String(100), nullable=True)
    
    # Completion
    is_complete = Column(Boolean, default=False, nullable=False)
    incomplete_reason = Column(String(100), nullable=True)  # 'declined_consent', 'disconnected', 'voicemail', 'timeout', 'error'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    scheduled_call = relationship("ReferenceScheduledCall", back_populates="calls")
    reference = relationship("CandidateReference", back_populates="calls")
    transcript = relationship("ReferenceCallTranscript", back_populates="call", uselist=False, cascade="all, delete-orphan")
    question_responses = relationship("ReferenceQuestionResponse", back_populates="call", cascade="all, delete-orphan")
    summary = relationship("ReferenceCallSummary", back_populates="call", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_rc_scheduled_call_id', 'scheduled_call_id'),
        Index('ix_rc_reference_id', 'reference_id'),
        Index('ix_rc_twilio_call_sid', 'twilio_call_sid'),
        Index('ix_rc_call_type', 'call_type'),
        Index('ix_rc_call_status', 'call_status'),
    )
    
    def __repr__(self):
        return f"<ReferenceCall(id={self.id}, type='{self.call_type}', status='{self.call_status}')>"


class ReferenceCallTranscript(Base):
    """
    Call transcript with timestamps for audio sync.
    """
    __tablename__ = 'reference_call_transcripts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(Integer, ForeignKey('reference_calls.id', ondelete='CASCADE'), nullable=False)
    
    # Transcript content
    full_transcript = Column(Text, nullable=False)
    transcript_segments = Column(JSONB, nullable=False)  # [{speaker, text, start_time, end_time}, ...]
    word_timestamps = Column(JSONB, nullable=True)  # For precise audio mapping
    
    # Metadata
    language = Column(String(10), default='en', nullable=False)
    confidence_score = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    call = relationship("ReferenceCall", back_populates="transcript")
    
    __table_args__ = (
        Index('ix_rctrans_call_id', 'call_id'),
    )
    
    def __repr__(self):
        return f"<ReferenceCallTranscript(id={self.id}, call_id={self.call_id})>"


class ReferenceQuestionResponse(Base):
    """
    Extracted question-answer pair from a call.
    """
    __tablename__ = 'reference_question_responses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(Integer, ForeignKey('reference_calls.id', ondelete='CASCADE'), nullable=False)
    template_question_id = Column(Integer, ForeignKey('reference_template_questions.id'), nullable=True)
    
    # Q&A content
    question_asked = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    
    # Analysis
    response_sentiment = Column(String(50), nullable=True)  # 'positive', 'neutral', 'negative', 'mixed'
    response_confidence = Column(Float, nullable=True)
    
    # Timestamps in recording
    transcript_start_time = Column(Float, nullable=True)  # seconds into recording
    transcript_end_time = Column(Float, nullable=True)
    
    # Follow-ups
    follow_up_questions = Column(JSONB, nullable=True)  # [{question, response, timestamp}, ...]
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    call = relationship("ReferenceCall", back_populates="question_responses")
    template_question = relationship("ReferenceTemplateQuestion")
    
    __table_args__ = (
        Index('ix_rqr_call_id', 'call_id'),
        Index('ix_rqr_template_question_id', 'template_question_id'),
    )
    
    def __repr__(self):
        return f"<ReferenceQuestionResponse(id={self.id}, call_id={self.call_id})>"


class ReferenceCallSummary(Base):
    """
    AI-generated summary of a reference check call.
    """
    __tablename__ = 'reference_call_summaries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(Integer, ForeignKey('reference_calls.id', ondelete='CASCADE'), nullable=False)
    
    # Summary content
    executive_summary = Column(Text, nullable=False)
    key_strengths = Column(JSONB, nullable=True)  # ["strength1", "strength2", ...]
    areas_of_concern = Column(JSONB, nullable=True)
    notable_quotes = Column(JSONB, nullable=True)  # [{quote, context, timestamp}, ...]
    
    # Assessment
    overall_sentiment = Column(String(50), nullable=True)
    recommendation_score = Column(Integer, nullable=True)  # 1-10
    recommendation_notes = Column(Text, nullable=True)
    
    # Timestamps
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    call = relationship("ReferenceCall", back_populates="summary")
    
    __table_args__ = (
        Index('ix_rcs_call_id', 'call_id'),
    )
    
    def __repr__(self):
        return f"<ReferenceCallSummary(id={self.id}, call_id={self.call_id}, score={self.recommendation_score})>"


class ReferenceCheckAuditLog(Base):
    """
    Audit trail for reference check actions.
    """
    __tablename__ = 'reference_check_audit_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Entity being audited
    entity_type = Column(String(50), nullable=False)  # 'request', 'reference', 'call', 'template', etc.
    entity_id = Column(Integer, nullable=False)
    
    # Action details
    action = Column(String(50), nullable=False)  # 'created', 'updated', 'deleted', 'viewed', 'exported'
    
    # User info
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    user_role = Column(String(50), nullable=True)
    ip_address = Column(String(50), nullable=True)
    
    # Changes
    changes = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_rcal_entity_type', 'entity_type'),
        Index('ix_rcal_entity_id', 'entity_id'),
        Index('ix_rcal_user_id', 'user_id'),
        Index('ix_rcal_action', 'action'),
        Index('ix_rcal_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ReferenceCheckAuditLog(id={self.id}, entity='{self.entity_type}:{self.entity_id}', action='{self.action}')>"


class CustomerCallerId(Base):
    """
    Verified caller IDs for a customer.
    """
    __tablename__ = 'customer_caller_ids'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(100), ForeignKey('customers.customer_id'), nullable=False)
    
    # Phone number
    twilio_phone_number = Column(String(50), nullable=False)
    display_name = Column(String(100), nullable=True)
    
    # Verification
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_sid = Column(String(100), nullable=True)
    
    # Settings
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_cci_customer_id', 'customer_id'),
        Index('ix_cci_is_default', 'is_default'),
        UniqueConstraint('customer_id', 'twilio_phone_number', name='uq_customer_caller_id'),
    )
    
    def __repr__(self):
        return f"<CustomerCallerId(id={self.id}, number='{self.twilio_phone_number}')>"


class CustomerCallSettings(Base):
    """
    Customer-level call settings.
    """
    __tablename__ = 'customer_call_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(100), ForeignKey('customers.customer_id'), unique=True, nullable=False)
    
    # Duration limits
    max_call_duration_seconds = Column(Integer, default=1800, nullable=False)  # 30 min default
    hard_limit_seconds = Column(Integer, default=3600, nullable=False)  # 60 min hard limit
    
    # Reference limits
    max_references_per_candidate = Column(Integer, default=10, nullable=False)
    
    # Reminder settings
    default_reminder_intervals = Column(JSONB, default=[86400, 7200, 900], nullable=False)
    
    # Defaults
    default_persona_id = Column(Integer, ForeignKey('reference_voice_personas.id'), nullable=True)
    default_template_id = Column(Integer, ForeignKey('reference_call_templates.id'), nullable=True)
    default_consent_template = Column(String(100), default='strict_compliance', nullable=False)
    
    # Incomplete call handling
    incomplete_call_action = Column(String(50), default='save_partial', nullable=False)  # 'save_partial', 'discard', 'reschedule'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_ccs_customer_id', 'customer_id'),
    )
    
    def __repr__(self):
        return f"<CustomerCallSettings(id={self.id}, customer_id='{self.customer_id}')>"

