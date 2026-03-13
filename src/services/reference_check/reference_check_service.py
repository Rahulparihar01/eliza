"""
Reference Check Service

Main service for managing reference check requests, references, and calls.
"""

import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.models.reference_check import (
    ReferenceCheckRequest,
    CandidateReference,
    ReferenceCallTemplate,
    ReferenceTemplateQuestion,
    ReferenceVoicePersona,
    ReferenceScheduledCall,
    ReferenceCall,
    ReferenceCheckAuditLog,
    CustomerCallSettings,
    ReferenceRequestStatus,
    ReferenceStatus,
    RelationshipType,
    ScheduledCallStatus,
    QuestionType,
    QuestionPriority
)
from src.models.candidate import Candidate

logger = get_logger(__name__, LogCategory.INTEGRATION)


class ReferenceCheckService:
    """
    Service for managing reference check operations.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
    
    # =========================================================================
    # Reference Check Requests
    # =========================================================================
    
    async def create_request(
        self,
        customer_id: str,
        candidate_name: str,
        candidate_email: str,
        candidate_phone: Optional[str] = None,
        job_id: Optional[str] = None,
        job_title: Optional[str] = None,
        greenhouse_candidate_id: Optional[int] = None,
        greenhouse_application_id: Optional[int] = None,
        candidate_id: Optional[int] = None,
        max_references: int = 10,
        created_by_user_id: Optional[int] = None
    ) -> ReferenceCheckRequest:
        """
        Create a new reference check request.
        
        Args:
            customer_id: Customer ID
            candidate_name: Name of the candidate
            candidate_email: Email of the candidate
            candidate_phone: Phone number of the candidate
            job_id: Job ID (optional)
            job_title: Job title (optional)
            greenhouse_candidate_id: Greenhouse candidate ID (optional)
            greenhouse_application_id: Greenhouse application ID (optional)
            candidate_id: Internal candidate ID (optional)
            max_references: Maximum number of references allowed
            created_by_user_id: User ID who created the request
        
        Returns:
            Created request
        """
        # Get customer settings for max references
        settings = self._get_customer_settings(customer_id)
        if settings and max_references > settings.max_references_per_candidate:
            max_references = settings.max_references_per_candidate
        
        # Generate verification token
        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.now(timezone.utc) + timedelta(days=7)
        
        request = ReferenceCheckRequest(
            customer_id=customer_id,
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            candidate_phone=candidate_phone,
            job_id=job_id,
            job_title=job_title,
            greenhouse_candidate_id=greenhouse_candidate_id,
            greenhouse_application_id=greenhouse_application_id,
            status=ReferenceRequestStatus.PENDING,
            max_references=max_references,
            verification_token=verification_token,
            verification_expires_at=verification_expires,
            created_by_user_id=created_by_user_id
        )
        
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        
        # Log audit
        self._log_audit(
            entity_type="request",
            entity_id=request.id,
            action="created",
            user_id=created_by_user_id,
            changes={"candidate_name": candidate_name, "candidate_email": candidate_email}
        )
        
        logger.info(
            "Reference check request created",
            extra={
                "request_id": request.id,
                "candidate_name": candidate_name
            }
        )
        
        return request
    
    async def get_request(
        self,
        request_id: int,
        customer_id: str
    ) -> Optional[ReferenceCheckRequest]:
        """Get a reference check request by ID."""
        return self.db.query(ReferenceCheckRequest).filter(
            ReferenceCheckRequest.id == request_id,
            ReferenceCheckRequest.customer_id == customer_id
        ).first()
    
    async def list_requests(
        self,
        customer_id: str,
        status: Optional[ReferenceRequestStatus] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[ReferenceCheckRequest]:
        """List reference check requests for a customer."""
        query = self.db.query(ReferenceCheckRequest).filter(
            ReferenceCheckRequest.customer_id == customer_id
        )
        
        if status:
            query = query.filter(ReferenceCheckRequest.status == status)
        
        return query.order_by(desc(ReferenceCheckRequest.created_at)).offset(skip).limit(limit).all()
    
    async def update_request_status(
        self,
        request_id: int,
        customer_id: str,
        status: ReferenceRequestStatus,
        user_id: Optional[int] = None
    ) -> ReferenceCheckRequest:
        """Update the status of a reference check request."""
        request = await self.get_request(request_id, customer_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        old_status = request.status
        request.status = status
        self.db.commit()
        
        self._log_audit(
            entity_type="request",
            entity_id=request_id,
            action="status_updated",
            user_id=user_id,
            changes={"old_status": old_status.value, "new_status": status.value}
        )
        
        return request
    
    async def verify_candidate(
        self,
        verification_token: str,
        otp: str
    ) -> Optional[ReferenceCheckRequest]:
        """
        Verify candidate identity for reference submission.
        
        Args:
            verification_token: Token from the reference request link
            otp: One-time password sent to candidate's phone
        
        Returns:
            Verified request or None
        """
        request = self.db.query(ReferenceCheckRequest).filter(
            ReferenceCheckRequest.verification_token == verification_token,
            ReferenceCheckRequest.verification_expires_at > datetime.now(timezone.utc)
        ).first()
        
        if not request:
            return None
        
        # TODO: Implement OTP verification via Twilio
        # For now, accept any OTP for testing
        
        request.verified_at = datetime.now(timezone.utc)
        request.status = ReferenceRequestStatus.REFERENCES_REQUESTED
        self.db.commit()
        
        return request
    
    # =========================================================================
    # References
    # =========================================================================
    
    async def add_reference(
        self,
        request_id: int,
        full_name: str,
        phone_number: str,
        relationship: Optional[RelationshipType] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        email: Optional[str] = None,
        preferred_contact_time: Optional[str] = None,
        notes: Optional[str] = None
    ) -> CandidateReference:
        """
        Add a reference to a request.
        
        Args:
            request_id: ID of the reference check request
            full_name: Name of the reference
            phone_number: Phone number of the reference
            relationship: Relationship type
            company: Company of the reference
            title: Title of the reference
            email: Email of the reference
            preferred_contact_time: Preferred time to contact
            notes: Additional notes
        
        Returns:
            Created reference
        """
        # Check request exists and has capacity
        request = self.db.query(ReferenceCheckRequest).filter(
            ReferenceCheckRequest.id == request_id
        ).first()
        
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        current_count = len(request.references)
        if current_count >= request.max_references:
            raise ValueError(f"Maximum references ({request.max_references}) reached")
        
        reference = CandidateReference(
            request_id=request_id,
            full_name=full_name,
            phone_number=phone_number,
            relationship_type=relationship,
            company=company,
            title=title,
            email=email,
            preferred_contact_time=preferred_contact_time,
            notes=notes,
            status=ReferenceStatus.PENDING
        )
        
        self.db.add(reference)
        self.db.commit()
        self.db.refresh(reference)
        
        logger.info(
            "Reference added",
            extra={
                "request_id": request_id,
                "reference_id": reference.id,
                "reference_name": full_name
            }
        )
        
        return reference
    
    async def get_reference(
        self,
        reference_id: int
    ) -> Optional[CandidateReference]:
        """Get a reference by ID."""
        return self.db.query(CandidateReference).filter(
            CandidateReference.id == reference_id
        ).first()
    
    async def list_references(
        self,
        request_id: int
    ) -> List[CandidateReference]:
        """List all references for a request."""
        return self.db.query(CandidateReference).filter(
            CandidateReference.request_id == request_id
        ).all()
    
    async def update_reference_status(
        self,
        reference_id: int,
        status: ReferenceStatus
    ) -> CandidateReference:
        """Update reference status."""
        reference = await self.get_reference(reference_id)
        if not reference:
            raise ValueError(f"Reference {reference_id} not found")
        
        reference.status = status
        self.db.commit()
        
        return reference
    
    # =========================================================================
    # Call Templates
    # =========================================================================
    
    async def create_template(
        self,
        customer_id: str,
        name: str,
        questions: List[Dict[str, Any]],
        description: Optional[str] = None,
        is_default: bool = False,
        created_by_user_id: Optional[int] = None
    ) -> ReferenceCallTemplate:
        """
        Create a call template with questions.
        
        Args:
            customer_id: Customer ID
            name: Template name
            questions: List of question definitions
            description: Template description
            is_default: Whether this is the default template
            created_by_user_id: User who created the template
        
        Returns:
            Created template
        """
        # If setting as default, clear other defaults
        if is_default:
            self.db.query(ReferenceCallTemplate).filter(
                ReferenceCallTemplate.customer_id == customer_id,
                ReferenceCallTemplate.is_default == True
            ).update({"is_default": False})
        
        template = ReferenceCallTemplate(
            customer_id=customer_id,
            name=name,
            description=description,
            is_default=is_default,
            is_active=True,
            created_by_user_id=created_by_user_id
        )
        
        self.db.add(template)
        self.db.flush()  # Get template ID
        
        # Add questions
        for i, q in enumerate(questions):
            question = ReferenceTemplateQuestion(
                template_id=template.id,
                question_text=q.get("question_text", ""),
                question_type=QuestionType(q.get("question_type", "concept")),
                priority=QuestionPriority(q.get("priority", "required")),
                order_index=q.get("order_index", i),
                follow_up_enabled=q.get("follow_up_enabled", True),
                max_follow_ups=q.get("max_follow_ups", 2),
                expected_answer_type=q.get("expected_answer_type")
            )
            self.db.add(question)
        
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(
            "Call template created",
            extra={
                "template_id": template.id,
                "name": name,
                "question_count": len(questions)
            }
        )
        
        return template
    
    async def get_template(
        self,
        template_id: int,
        customer_id: str
    ) -> Optional[ReferenceCallTemplate]:
        """Get a template by ID."""
        return self.db.query(ReferenceCallTemplate).filter(
            ReferenceCallTemplate.id == template_id,
            ReferenceCallTemplate.customer_id == customer_id
        ).first()
    
    async def list_templates(
        self,
        customer_id: str,
        active_only: bool = True
    ) -> List[ReferenceCallTemplate]:
        """List templates for a customer."""
        query = self.db.query(ReferenceCallTemplate).filter(
            ReferenceCallTemplate.customer_id == customer_id
        )
        
        if active_only:
            query = query.filter(ReferenceCallTemplate.is_active == True)
        
        return query.order_by(desc(ReferenceCallTemplate.is_default), ReferenceCallTemplate.name).all()
    
    async def update_template(
        self,
        template_id: int,
        customer_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        questions: Optional[List[Dict[str, Any]]] = None,
        is_default: Optional[bool] = None,
        is_active: Optional[bool] = None
    ) -> ReferenceCallTemplate:
        """Update a template."""
        template = await self.get_template(template_id, customer_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if is_active is not None:
            template.is_active = is_active
        
        if is_default is not None:
            if is_default:
                # Clear other defaults
                self.db.query(ReferenceCallTemplate).filter(
                    ReferenceCallTemplate.customer_id == customer_id,
                    ReferenceCallTemplate.is_default == True,
                    ReferenceCallTemplate.id != template_id
                ).update({"is_default": False})
            template.is_default = is_default
        
        if questions is not None:
            # Delete existing questions
            self.db.query(ReferenceTemplateQuestion).filter(
                ReferenceTemplateQuestion.template_id == template_id
            ).delete()
            
            # Add new questions
            for i, q in enumerate(questions):
                question = ReferenceTemplateQuestion(
                    template_id=template_id,
                    question_text=q.get("question_text", ""),
                    question_type=QuestionType(q.get("question_type", "concept")),
                    priority=QuestionPriority(q.get("priority", "required")),
                    order_index=q.get("order_index", i),
                    follow_up_enabled=q.get("follow_up_enabled", True),
                    max_follow_ups=q.get("max_follow_ups", 2),
                    expected_answer_type=q.get("expected_answer_type")
                )
                self.db.add(question)
        
        self.db.commit()
        self.db.refresh(template)
        
        return template
    
    async def delete_template(
        self,
        template_id: int,
        customer_id: str
    ) -> bool:
        """Delete a template (soft delete by marking inactive)."""
        template = await self.get_template(template_id, customer_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        template.is_active = False
        self.db.commit()
        
        return True
    
    # =========================================================================
    # Voice Personas
    # =========================================================================
    
    async def create_persona(
        self,
        customer_id: str,
        name: str,
        voice_model: str = "alloy",
        speaking_rate: float = 1.0,
        tone: str = "professional",
        personality_traits: Optional[Dict[str, float]] = None,
        introduction_script: Optional[str] = None,
        closing_script: Optional[str] = None,
        description: Optional[str] = None,
        is_default: bool = False
    ) -> ReferenceVoicePersona:
        """Create a voice persona."""
        # If setting as default, clear other defaults
        if is_default:
            self.db.query(ReferenceVoicePersona).filter(
                ReferenceVoicePersona.customer_id == customer_id,
                ReferenceVoicePersona.is_default == True
            ).update({"is_default": False})
        
        persona = ReferenceVoicePersona(
            customer_id=customer_id,
            name=name,
            description=description,
            voice_model=voice_model,
            speaking_rate=speaking_rate,
            tone=tone,
            personality_traits=personality_traits,
            introduction_script=introduction_script,
            closing_script=closing_script,
            is_default=is_default
        )
        
        self.db.add(persona)
        self.db.commit()
        self.db.refresh(persona)
        
        return persona
    
    async def get_persona(
        self,
        persona_id: int,
        customer_id: str
    ) -> Optional[ReferenceVoicePersona]:
        """Get a persona by ID."""
        return self.db.query(ReferenceVoicePersona).filter(
            ReferenceVoicePersona.id == persona_id,
            ReferenceVoicePersona.customer_id == customer_id
        ).first()
    
    async def list_personas(
        self,
        customer_id: str
    ) -> List[ReferenceVoicePersona]:
        """List personas for a customer."""
        return self.db.query(ReferenceVoicePersona).filter(
            ReferenceVoicePersona.customer_id == customer_id
        ).order_by(desc(ReferenceVoicePersona.is_default), ReferenceVoicePersona.name).all()
    
    # =========================================================================
    # Scheduled Calls
    # =========================================================================
    
    async def schedule_call(
        self,
        reference_id: int,
        scheduled_at: datetime,
        template_id: Optional[int] = None,
        persona_id: Optional[int] = None,
        consent_template_id: Optional[int] = None,
        reminder_intervals: Optional[List[int]] = None,
        caller_id: Optional[str] = None,
        created_by_user_id: Optional[int] = None
    ) -> ReferenceScheduledCall:
        """
        Schedule a reference check call.
        
        Args:
            reference_id: ID of the reference
            scheduled_at: When to make the call
            template_id: Call template to use
            persona_id: Voice persona to use
            consent_template_id: Consent template to use
            reminder_intervals: SMS reminder intervals in seconds
            caller_id: Caller ID to use
            created_by_user_id: User scheduling the call
        
        Returns:
            Scheduled call record
        """
        reference = await self.get_reference(reference_id)
        if not reference:
            raise ValueError(f"Reference {reference_id} not found")
        
        # Default reminder intervals
        if reminder_intervals is None:
            settings = self._get_customer_settings(reference.request.customer_id)
            reminder_intervals = settings.default_reminder_intervals if settings else [86400, 7200, 900]
        
        scheduled_call = ReferenceScheduledCall(
            reference_id=reference_id,
            template_id=template_id,
            persona_id=persona_id,
            consent_template_id=consent_template_id,
            scheduled_at=scheduled_at,
            reminder_intervals=reminder_intervals,
            caller_id=caller_id,
            status=ScheduledCallStatus.SCHEDULED,
            created_by_user_id=created_by_user_id
        )
        
        self.db.add(scheduled_call)
        
        # Update reference status
        reference.status = ReferenceStatus.SCHEDULED
        
        self.db.commit()
        self.db.refresh(scheduled_call)
        
        logger.info(
            "Call scheduled",
            extra={
                "scheduled_call_id": scheduled_call.id,
                "reference_id": reference_id,
                "scheduled_at": scheduled_at.isoformat()
            }
        )
        
        return scheduled_call
    
    async def get_scheduled_call(
        self,
        scheduled_call_id: int
    ) -> Optional[ReferenceScheduledCall]:
        """Get a scheduled call by ID."""
        return self.db.query(ReferenceScheduledCall).filter(
            ReferenceScheduledCall.id == scheduled_call_id
        ).first()
    
    async def list_scheduled_calls(
        self,
        customer_id: str,
        status: Optional[ScheduledCallStatus] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[ReferenceScheduledCall]:
        """List scheduled calls for a customer."""
        query = self.db.query(ReferenceScheduledCall).join(
            CandidateReference
        ).join(
            ReferenceCheckRequest
        ).filter(
            ReferenceCheckRequest.customer_id == customer_id
        )
        
        if status:
            query = query.filter(ReferenceScheduledCall.status == status)
        if from_date:
            query = query.filter(ReferenceScheduledCall.scheduled_at >= from_date)
        if to_date:
            query = query.filter(ReferenceScheduledCall.scheduled_at <= to_date)
        
        return query.order_by(ReferenceScheduledCall.scheduled_at).all()
    
    async def cancel_scheduled_call(
        self,
        scheduled_call_id: int,
        user_id: Optional[int] = None
    ) -> ReferenceScheduledCall:
        """Cancel a scheduled call."""
        scheduled_call = await self.get_scheduled_call(scheduled_call_id)
        if not scheduled_call:
            raise ValueError(f"Scheduled call {scheduled_call_id} not found")
        
        scheduled_call.status = ScheduledCallStatus.CANCELLED
        scheduled_call.reference.status = ReferenceStatus.PENDING
        
        self.db.commit()
        
        self._log_audit(
            entity_type="scheduled_call",
            entity_id=scheduled_call_id,
            action="cancelled",
            user_id=user_id
        )
        
        return scheduled_call
    
    # =========================================================================
    # Calls
    # =========================================================================
    
    async def get_call(
        self,
        call_id: int
    ) -> Optional[ReferenceCall]:
        """Get a call by ID."""
        return self.db.query(ReferenceCall).filter(
            ReferenceCall.id == call_id
        ).first()
    
    async def list_calls(
        self,
        customer_id: str,
        reference_id: Optional[int] = None,
        request_id: Optional[int] = None
    ) -> List[ReferenceCall]:
        """List calls for a customer."""
        query = self.db.query(ReferenceCall).join(
            CandidateReference
        ).join(
            ReferenceCheckRequest
        ).filter(
            ReferenceCheckRequest.customer_id == customer_id
        )
        
        if reference_id:
            query = query.filter(ReferenceCall.reference_id == reference_id)
        if request_id:
            query = query.filter(ReferenceCheckRequest.id == request_id)
        
        return query.order_by(desc(ReferenceCall.created_at)).all()
    
    # =========================================================================
    # Customer Settings
    # =========================================================================
    
    def _get_customer_settings(
        self,
        customer_id: str
    ) -> Optional[CustomerCallSettings]:
        """Get customer call settings."""
        return self.db.query(CustomerCallSettings).filter(
            CustomerCallSettings.customer_id == customer_id
        ).first()
    
    async def get_or_create_customer_settings(
        self,
        customer_id: str
    ) -> CustomerCallSettings:
        """Get or create customer call settings."""
        settings = self._get_customer_settings(customer_id)
        
        if not settings:
            settings = CustomerCallSettings(
                customer_id=customer_id,
                max_call_duration_seconds=self.settings.reference_check_max_call_duration,
                hard_limit_seconds=self.settings.reference_check_hard_limit,
                max_references_per_candidate=self.settings.reference_check_max_references
            )
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        
        return settings
    
    async def update_customer_settings(
        self,
        customer_id: str,
        **kwargs
    ) -> CustomerCallSettings:
        """Update customer call settings."""
        settings = await self.get_or_create_customer_settings(customer_id)
        
        for key, value in kwargs.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        
        self.db.commit()
        self.db.refresh(settings)
        
        return settings
    
    # =========================================================================
    # Audit Logging
    # =========================================================================
    
    def _log_audit(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        user_id: Optional[int] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None
    ):
        """Log an audit entry."""
        audit = ReferenceCheckAuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            user_role=user_role,
            ip_address=ip_address,
            changes=changes
        )
        self.db.add(audit)
        # Don't commit here - let the calling function handle the commit

