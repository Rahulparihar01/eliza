"""
Email Templates API Routes

CRUD operations for email templates and AI-powered email generation.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.email_templates import (
    EmailTemplate,
    EmailTemplateSection,
    EmailSectionLibrary,
    GeneratedEmail,
    CustomerSettings,
    TemplateSectionType,
    TemplateCategory
)
from src.services.email_generation_service import EmailGenerationService, PDLCacheService
from src.middleware.authorization import get_current_user
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/email-templates", tags=["Email Templates"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TemplateSectionCreate(BaseModel):
    """Request model for creating a template section."""
    order: int = Field(default=0, description="Section order (0-indexed)")
    section_type: str = Field(default="static", description="'static' or 'ai_generated'")
    content: Optional[str] = Field(None, description="Static content with variables")
    ai_prompt: Optional[str] = Field(None, description="AI generation prompt")
    ai_context_fields: Optional[List[str]] = Field(None, description="Fields to include in AI context")
    ai_tone: Optional[str] = Field(default="professional", description="AI tone: professional, casual, enthusiastic")
    ai_max_length: Optional[int] = Field(default=200, description="Max characters for AI content")
    section_name: Optional[str] = Field(None, description="Section name for reference")


class TemplateSectionResponse(BaseModel):
    """Response model for a template section."""
    id: int
    order: int = Field(validation_alias="section_order", serialization_alias="order")
    section_type: str
    content: Optional[str]
    ai_prompt: Optional[str]
    ai_context_fields: Optional[List[str]]
    ai_tone: Optional[str]
    ai_max_length: Optional[int]
    section_name: Optional[str]
    
    class Config:
        from_attributes = True
        populate_by_name = True


class EmailTemplateCreate(BaseModel):
    """Request model for creating an email template."""
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: str = Field(default="custom", description="Template category")
    subject: str = Field(..., description="Email subject line")
    subject_is_ai_generated: bool = Field(default=False, description="Whether subject uses AI")
    subject_ai_prompt: Optional[str] = Field(None, description="AI prompt for subject")
    sections: List[TemplateSectionCreate] = Field(default_factory=list, description="Template sections")
    is_default: bool = Field(default=False, description="Set as default for category")


class EmailTemplateUpdate(BaseModel):
    """Request model for updating an email template."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    subject: Optional[str] = None
    subject_is_ai_generated: Optional[bool] = None
    subject_ai_prompt: Optional[str] = None
    sections: Optional[List[TemplateSectionCreate]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class EmailTemplateResponse(BaseModel):
    """Response model for an email template."""
    id: int
    name: str
    description: Optional[str]
    category: str
    subject: str
    subject_is_ai_generated: bool
    subject_ai_prompt: Optional[str]
    use_count: int
    last_used_at: Optional[datetime]
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    sections: List[TemplateSectionResponse]
    variables: List[str]  # Extracted variables from template
    
    class Config:
        from_attributes = True


class EmailTemplateListResponse(BaseModel):
    """Response model for template list."""
    templates: List[EmailTemplateResponse]
    total: int


class GenerateEmailRequest(BaseModel):
    """Request to generate an email for a candidate."""
    template_id: int = Field(..., description="Template ID to use")
    candidate_data: Dict[str, Any] = Field(..., description="Candidate information")
    talent_analysis_id: Optional[str] = Field(None, description="Associated analysis ID")
    force_regenerate: bool = Field(default=False, description="Force regeneration even if cached")


class PreviewTemplateRequest(BaseModel):
    """Request to preview an email template without saving it first."""
    subject: str = Field(..., description="Email subject line")
    subject_is_ai_generated: bool = Field(default=False, description="Whether subject uses AI")
    subject_ai_prompt: Optional[str] = Field(None, description="AI prompt for subject")
    sections: List[TemplateSectionCreate] = Field(default_factory=list, description="Template sections")
    candidate_data: Dict[str, Any] = Field(..., description="Candidate information for preview")


class PreviewTemplateResponse(BaseModel):
    """Response for template preview."""
    subject: str
    body: str
    generated_at: datetime


class GeneratedEmailResponse(BaseModel):
    """Response model for generated email."""
    id: int
    template_id: Optional[int]
    candidate_id: str
    subject: str
    body: str
    is_edited: bool
    status: str
    created_at: datetime
    greenhouse_maildrop: Optional[str]  # Include maildrop for frontend
    
    class Config:
        from_attributes = True


class UpdateGeneratedEmailRequest(BaseModel):
    """Request to update a generated email."""
    subject: Optional[str] = None
    body: Optional[str] = None


class CustomerSettingsResponse(BaseModel):
    """Response model for customer settings."""
    greenhouse_maildrop_address: Optional[str]
    pdl_cache_ttl_days: int
    sender_name: Optional[str]
    sender_title: Optional[str]
    ai_email_generation_enabled: bool
    
    class Config:
        from_attributes = True


class CustomerSettingsUpdate(BaseModel):
    """Request to update customer settings."""
    greenhouse_maildrop_address: Optional[str] = None
    pdl_cache_ttl_days: Optional[int] = None
    sender_name: Optional[str] = None
    sender_title: Optional[str] = None
    email_signature: Optional[str] = None
    ai_email_generation_enabled: Optional[bool] = None


# ============================================================================
# SECTION LIBRARY REQUEST/RESPONSE MODELS
# ============================================================================

class SectionLibraryCreate(BaseModel):
    """Request model for creating a library section."""
    name: str = Field(..., min_length=1, max_length=255, description="Section name")
    description: Optional[str] = Field(None, description="When to use this section")
    category: Optional[str] = Field(None, description="Section category (opening, skills_match, call_to_action, closing)")
    tags: Optional[List[str]] = Field(None, description="Tags for searching")
    section_type: str = Field(default="static", description="'static' or 'ai_generated'")
    content: Optional[str] = Field(None, description="Static content with variables")
    ai_prompt: Optional[str] = Field(None, description="AI generation prompt")
    ai_context_fields: Optional[List[str]] = Field(None, description="Fields to include in AI context")
    ai_tone: Optional[str] = Field(default="professional", description="AI tone")
    ai_max_length: Optional[int] = Field(default=200, description="Max characters for AI content")
    is_shared: bool = Field(default=True, description="Share with team members")


class SectionLibraryUpdate(BaseModel):
    """Request model for updating a library section."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    section_type: Optional[str] = None
    content: Optional[str] = None
    ai_prompt: Optional[str] = None
    ai_context_fields: Optional[List[str]] = None
    ai_tone: Optional[str] = None
    ai_max_length: Optional[int] = None
    is_shared: Optional[bool] = None
    is_active: Optional[bool] = None


class SectionLibraryResponse(BaseModel):
    """Response model for a library section."""
    id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    tags: Optional[List[str]]
    section_type: str
    content: Optional[str]
    ai_prompt: Optional[str]
    ai_context_fields: Optional[List[str]]
    ai_tone: Optional[str]
    ai_max_length: Optional[int]
    use_count: int
    last_used_at: Optional[datetime]
    is_active: bool
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    created_by_user_id: Optional[int]
    
    class Config:
        from_attributes = True


class SectionLibraryListResponse(BaseModel):
    """Response model for section library list."""
    sections: List[SectionLibraryResponse]
    total: int


# ============================================================================
# TEMPLATE CRUD ENDPOINTS
# ============================================================================

@router.get(
    "",
    response_model=EmailTemplateListResponse,
    summary="List email templates"
)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: bool = Query(True, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List all email templates for the customer."""
    query = db.query(EmailTemplate).filter(
        EmailTemplate.customer_id == current_user.customer_id,
        EmailTemplate.is_active == is_active
    )
    
    if category:
        query = query.filter(EmailTemplate.category == category)
    
    templates = query.order_by(EmailTemplate.name).all()
    
    # Build response with extracted variables
    template_responses = []
    for template in templates:
        response = EmailTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            category=template.category,
            subject=template.subject,
            subject_is_ai_generated=template.subject_is_ai_generated,
            subject_ai_prompt=template.subject_ai_prompt,
            use_count=template.use_count,
            last_used_at=template.last_used_at,
            is_active=template.is_active,
            is_default=template.is_default,
            created_at=template.created_at,
            updated_at=template.updated_at,
            sections=[TemplateSectionResponse.model_validate(s) for s in template.sections],
            variables=template.get_all_variables()
        )
        template_responses.append(response)
    
    return EmailTemplateListResponse(
        templates=template_responses,
        total=len(template_responses)
    )


@router.post(
    "",
    response_model=EmailTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create email template"
)
async def create_template(
    request: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new email template with sections."""
    # If setting as default, unset other defaults in category
    if request.is_default:
        db.query(EmailTemplate).filter(
            EmailTemplate.customer_id == current_user.customer_id,
            EmailTemplate.category == request.category,
            EmailTemplate.is_default == True
        ).update({"is_default": False})
    
    # Create template
    template = EmailTemplate(
        customer_id=current_user.customer_id,
        name=request.name,
        description=request.description,
        category=request.category,
        subject=request.subject,
        subject_is_ai_generated=request.subject_is_ai_generated,
        subject_ai_prompt=request.subject_ai_prompt,
        is_default=request.is_default
    )
    db.add(template)
    db.flush()  # Get template ID
    
    # Create sections
    for section_data in request.sections:
        section = EmailTemplateSection(
            template_id=template.id,
            section_order=section_data.order,
            section_type=section_data.section_type,
            content=section_data.content,
            ai_prompt=section_data.ai_prompt,
            ai_context_fields=section_data.ai_context_fields,
            ai_tone=section_data.ai_tone,
            ai_max_length=section_data.ai_max_length,
            section_name=section_data.section_name
        )
        db.add(section)
    
    db.commit()
    db.refresh(template)
    
    logger.info(
        "email_template_created",
        template_id=template.id,
        name=template.name,
        section_count=len(request.sections)
    )
    
    return EmailTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        subject=template.subject,
        subject_is_ai_generated=template.subject_is_ai_generated,
        subject_ai_prompt=template.subject_ai_prompt,
        use_count=template.use_count,
        last_used_at=template.last_used_at,
        is_active=template.is_active,
        is_default=template.is_default,
        created_at=template.created_at,
        updated_at=template.updated_at,
        sections=[TemplateSectionResponse.model_validate(s) for s in template.sections],
        variables=template.get_all_variables()
    )


# ============================================================================
# SECTION LIBRARY ENDPOINTS
# Note: These must come BEFORE /{template_id} to avoid route matching issues
# ============================================================================

SECTION_CATEGORIES = [
    {"value": "opening", "label": "Opening / Greeting", "description": "How to start the email"},
    {"value": "introduction", "label": "Introduction", "description": "Introduce yourself or the opportunity"},
    {"value": "skills_match", "label": "Skills Match", "description": "Highlight relevant skills/experience"},
    {"value": "value_proposition", "label": "Value Proposition", "description": "Why they should be interested"},
    {"value": "company_pitch", "label": "Company Pitch", "description": "About the company/team"},
    {"value": "call_to_action", "label": "Call to Action", "description": "What you want them to do next"},
    {"value": "closing", "label": "Closing", "description": "Sign off the email"},
    {"value": "custom", "label": "Custom", "description": "Other sections"},
]


@router.get(
    "/library",
    summary="List section library"
)
async def list_library_sections(
    category: Optional[str] = Query(None, description="Filter by category"),
    section_type: Optional[str] = Query(None, description="Filter by type (static/ai_generated)"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    is_active: bool = Query(True, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List all sections in the library for the customer."""
    try:
        query = db.query(EmailSectionLibrary).filter(
            EmailSectionLibrary.customer_id == current_user.customer_id,
            EmailSectionLibrary.is_active == is_active
        )
        
        # Only show shared sections or sections created by the user
        query = query.filter(
            (EmailSectionLibrary.is_shared == True) | 
            (EmailSectionLibrary.created_by_user_id == current_user.user_id)
        )
        
        if category:
            query = query.filter(EmailSectionLibrary.category == category)
        
        if section_type:
            query = query.filter(EmailSectionLibrary.section_type == section_type)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (EmailSectionLibrary.name.ilike(search_term)) |
                (EmailSectionLibrary.description.ilike(search_term))
            )
        
        sections = query.order_by(EmailSectionLibrary.use_count.desc(), EmailSectionLibrary.name).all()
        
        # Manually serialize to dict to avoid Pydantic serialization issues
        section_dicts = []
        for s in sections:
            section_dicts.append({
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "tags": s.tags if s.tags else None,
                "section_type": s.section_type,
                "content": s.content,
                "ai_prompt": s.ai_prompt,
                "ai_context_fields": s.ai_context_fields if s.ai_context_fields else None,
                "ai_tone": s.ai_tone,
                "ai_max_length": s.ai_max_length,
                "use_count": s.use_count,
                "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
                "is_active": s.is_active,
                "is_shared": s.is_shared,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "created_by_user_id": s.created_by_user_id,
            })
        
        return {"sections": section_dicts, "total": len(section_dicts)}
    except Exception as e:
        logger.error(f"Error in list_library_sections: {e}", exc_info=True)
        raise


@router.get(
    "/library/categories",
    response_model=List[Dict[str, str]],
    summary="Get section categories"
)
async def get_library_categories():
    """Get available section categories."""
    return SECTION_CATEGORIES


@router.post(
    "/library",
    response_model=SectionLibraryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create library section"
)
async def create_library_section(
    request: SectionLibraryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new section in the library."""
    section = EmailSectionLibrary(
        customer_id=current_user.customer_id,
        created_by_user_id=current_user.user_id,
        name=request.name,
        description=request.description,
        category=request.category,
        tags=request.tags,
        section_type=request.section_type,
        content=request.content,
        ai_prompt=request.ai_prompt,
        ai_context_fields=request.ai_context_fields,
        ai_tone=request.ai_tone,
        ai_max_length=request.ai_max_length,
        is_shared=request.is_shared,
    )
    
    db.add(section)
    db.commit()
    db.refresh(section)
    
    logger.info(
        "library_section_created",
        section_id=section.id,
        name=section.name,
        section_type=section.section_type
    )
    
    return SectionLibraryResponse.model_validate(section)


@router.get(
    "/library/{section_id}",
    response_model=SectionLibraryResponse,
    summary="Get library section"
)
async def get_library_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific section from the library."""
    section = db.query(EmailSectionLibrary).filter(
        EmailSectionLibrary.id == section_id,
        EmailSectionLibrary.customer_id == current_user.customer_id
    ).first()
    
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id} not found"
        )
    
    return SectionLibraryResponse.model_validate(section)


@router.put(
    "/library/{section_id}",
    response_model=SectionLibraryResponse,
    summary="Update library section"
)
async def update_library_section(
    section_id: int,
    request: SectionLibraryUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a section in the library."""
    section = db.query(EmailSectionLibrary).filter(
        EmailSectionLibrary.id == section_id,
        EmailSectionLibrary.customer_id == current_user.customer_id
    ).first()
    
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id} not found"
        )
    
    # Only creator can update non-shared sections
    if not section.is_shared and section.created_by_user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own sections"
        )
    
    # Update fields
    if request.name is not None:
        section.name = request.name
    if request.description is not None:
        section.description = request.description
    if request.category is not None:
        section.category = request.category
    if request.tags is not None:
        section.tags = request.tags
    if request.section_type is not None:
        section.section_type = request.section_type
    if request.content is not None:
        section.content = request.content
    if request.ai_prompt is not None:
        section.ai_prompt = request.ai_prompt
    if request.ai_context_fields is not None:
        section.ai_context_fields = request.ai_context_fields
    if request.ai_tone is not None:
        section.ai_tone = request.ai_tone
    if request.ai_max_length is not None:
        section.ai_max_length = request.ai_max_length
    if request.is_shared is not None:
        section.is_shared = request.is_shared
    if request.is_active is not None:
        section.is_active = request.is_active
    
    db.commit()
    db.refresh(section)
    
    logger.info(
        "library_section_updated",
        section_id=section.id
    )
    
    return SectionLibraryResponse.model_validate(section)


@router.delete(
    "/library/{section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete library section"
)
async def delete_library_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a section from the library (soft delete)."""
    section = db.query(EmailSectionLibrary).filter(
        EmailSectionLibrary.id == section_id,
        EmailSectionLibrary.customer_id == current_user.customer_id
    ).first()
    
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id} not found"
        )
    
    # Only creator can delete their sections
    if section.created_by_user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own sections"
        )
    
    section.is_active = False
    db.commit()
    
    logger.info(
        "library_section_deleted",
        section_id=section_id
    )


@router.post(
    "/library/{section_id}/use",
    response_model=SectionLibraryResponse,
    summary="Track section usage"
)
async def track_section_usage(
    section_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Track when a library section is used in a template."""
    section = db.query(EmailSectionLibrary).filter(
        EmailSectionLibrary.id == section_id,
        EmailSectionLibrary.customer_id == current_user.customer_id
    ).first()
    
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id} not found"
        )
    
    section.use_count += 1
    section.last_used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(section)
    
    return SectionLibraryResponse.model_validate(section)


# ============================================================================
# TEMPLATE CRUD ENDPOINTS (CONTINUED)
# ============================================================================

@router.get(
    "/{template_id}",
    response_model=EmailTemplateResponse,
    summary="Get email template"
)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific email template."""
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.customer_id == current_user.customer_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )
    
    return EmailTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        subject=template.subject,
        subject_is_ai_generated=template.subject_is_ai_generated,
        subject_ai_prompt=template.subject_ai_prompt,
        use_count=template.use_count,
        last_used_at=template.last_used_at,
        is_active=template.is_active,
        is_default=template.is_default,
        created_at=template.created_at,
        updated_at=template.updated_at,
        sections=[TemplateSectionResponse.model_validate(s) for s in template.sections],
        variables=template.get_all_variables()
    )


@router.put(
    "/{template_id}",
    response_model=EmailTemplateResponse,
    summary="Update email template"
)
async def update_template(
    template_id: int,
    request: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update an email template."""
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.customer_id == current_user.customer_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )
    
    # Update fields
    if request.name is not None:
        template.name = request.name
    if request.description is not None:
        template.description = request.description
    if request.category is not None:
        template.category = request.category
    if request.subject is not None:
        template.subject = request.subject
    if request.subject_is_ai_generated is not None:
        template.subject_is_ai_generated = request.subject_is_ai_generated
    if request.subject_ai_prompt is not None:
        template.subject_ai_prompt = request.subject_ai_prompt
    if request.is_active is not None:
        template.is_active = request.is_active
    if request.is_default is not None:
        if request.is_default:
            # Unset other defaults
            db.query(EmailTemplate).filter(
                EmailTemplate.customer_id == current_user.customer_id,
                EmailTemplate.category == template.category,
                EmailTemplate.is_default == True,
                EmailTemplate.id != template_id
            ).update({"is_default": False})
        template.is_default = request.is_default
    
    # Update sections if provided
    if request.sections is not None:
        # Delete existing sections
        db.query(EmailTemplateSection).filter(
            EmailTemplateSection.template_id == template_id
        ).delete()
        
        # Create new sections
        for section_data in request.sections:
            section = EmailTemplateSection(
                template_id=template.id,
                section_order=section_data.order,
                section_type=section_data.section_type,
                content=section_data.content,
                ai_prompt=section_data.ai_prompt,
                ai_context_fields=section_data.ai_context_fields,
                ai_tone=section_data.ai_tone,
                ai_max_length=section_data.ai_max_length,
                section_name=section_data.section_name
            )
            db.add(section)
    
    db.commit()
    db.refresh(template)
    
    logger.info(
        "email_template_updated",
        template_id=template.id
    )
    
    return EmailTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        subject=template.subject,
        subject_is_ai_generated=template.subject_is_ai_generated,
        subject_ai_prompt=template.subject_ai_prompt,
        use_count=template.use_count,
        last_used_at=template.last_used_at,
        is_active=template.is_active,
        is_default=template.is_default,
        created_at=template.created_at,
        updated_at=template.updated_at,
        sections=[TemplateSectionResponse.model_validate(s) for s in template.sections],
        variables=template.get_all_variables()
    )


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete email template"
)
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete an email template (soft delete by setting is_active=False)."""
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.customer_id == current_user.customer_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )
    
    template.is_active = False
    db.commit()
    
    logger.info(
        "email_template_deleted",
        template_id=template_id
    )


# ============================================================================
# EMAIL GENERATION ENDPOINTS
# ============================================================================

@router.post(
    "/generate",
    response_model=GeneratedEmailResponse,
    summary="Generate email for candidate"
)
async def generate_email(
    request: GenerateEmailRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Generate a personalized email for a candidate using a template."""
    service = EmailGenerationService(db, current_user.customer_id)
    
    try:
        generated = await service.generate_email_for_candidate(
            template_id=request.template_id,
            candidate_data=request.candidate_data,
            talent_analysis_id=request.talent_analysis_id,
            force_regenerate=request.force_regenerate
        )
        
        return GeneratedEmailResponse(
            id=generated.id,
            template_id=generated.template_id,
            candidate_id=generated.candidate_id,
            subject=generated.subject,
            body=generated.body,
            is_edited=generated.is_edited,
            status=generated.status,
            created_at=generated.created_at,
            greenhouse_maildrop=service.get_greenhouse_maildrop()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("email_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate email"
        )


@router.post(
    "/preview",
    response_model=PreviewTemplateResponse,
    summary="Preview email template without saving"
)
async def preview_template(
    request: PreviewTemplateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Generate a preview of an email template without saving it first.
    
    This allows users to test AI generation and variable substitution
    while creating/editing a template, before committing changes.
    """
    service = EmailGenerationService(db, current_user.customer_id)
    
    try:
        # Generate subject
        if request.subject_is_ai_generated and request.subject_ai_prompt:
            subject = await service._generate_ai_content(
                prompt=request.subject_ai_prompt,
                candidate_data=request.candidate_data,
                max_length=100,
                tone="professional"
            )
            # Add "Re: " prefix handling for AI subjects
            subject = f"Re: {subject}" if not subject.startswith("Re:") else subject
        else:
            subject = service._substitute_variables(request.subject, request.candidate_data)
        
        # Generate body from sections
        body_parts = []
        for section in sorted(request.sections, key=lambda s: s.order):
            if section.section_type == 'ai_generated' and section.ai_prompt:
                content = await service._generate_ai_content(
                    prompt=section.ai_prompt,
                    candidate_data=request.candidate_data,
                    context_fields=section.ai_context_fields,
                    max_length=section.ai_max_length or 200,
                    tone=section.ai_tone or "professional"
                )
                body_parts.append(content)
            elif section.section_type == 'static' and section.content:
                content = service._substitute_variables(section.content, request.candidate_data)
                body_parts.append(content)
        
        body = "\n\n".join(body_parts)
        
        logger.info(
            "template_preview_generated",
            customer_id=current_user.customer_id,
            section_count=len(request.sections),
            has_ai_subject=request.subject_is_ai_generated
        )
        
        return PreviewTemplateResponse(
            subject=subject,
            body=body,
            generated_at=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        logger.error("template_preview_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate preview: {str(e)}"
        )


class GenerateDefaultEmailRequest(BaseModel):
    """Request to generate an email using the default template."""
    candidate_data: Dict[str, Any] = Field(..., description="Candidate information")
    category: Optional[str] = Field(None, description="Template category (e.g., 'market_outreach', 'applicant_followup')")
    talent_analysis_id: Optional[str] = Field(None, description="Associated analysis ID")


class DefaultTemplateResponse(BaseModel):
    """Response with default template info."""
    id: int
    name: str
    category: str
    has_ai_sections: bool


@router.get(
    "/default",
    response_model=Optional[DefaultTemplateResponse],
    summary="Get default template info"
)
async def get_default_template(
    category: Optional[str] = Query(None, description="Template category"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get information about the default template for a category."""
    service = EmailGenerationService(db, current_user.customer_id)
    template = service.get_default_template(category)
    
    if not template:
        return None
    
    has_ai = any(s.section_type == 'ai_generated' for s in template.sections) or template.subject_is_ai_generated
    
    return DefaultTemplateResponse(
        id=template.id,
        name=template.name,
        category=template.category,
        has_ai_sections=has_ai
    )


@router.post(
    "/generate-default",
    response_model=GeneratedEmailResponse,
    summary="Generate email using default template"
)
async def generate_email_with_default(
    request: GenerateDefaultEmailRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Generate a personalized email for a candidate using the default template.
    
    This is useful for auto-generating initial emails for candidates
    without requiring the user to select a template.
    """
    service = EmailGenerationService(db, current_user.customer_id)
    
    try:
        generated = await service.generate_email_with_default_template(
            candidate_data=request.candidate_data,
            category=request.category,
            talent_analysis_id=request.talent_analysis_id
        )
        
        if not generated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No default template found for category: {request.category or 'any'}"
            )
        
        return GeneratedEmailResponse(
            id=generated.id,
            template_id=generated.template_id,
            candidate_id=generated.candidate_id,
            subject=generated.subject,
            body=generated.body,
            is_edited=generated.is_edited,
            status=generated.status,
            created_at=generated.created_at,
            greenhouse_maildrop=service.get_greenhouse_maildrop()
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("default_email_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate email with default template"
        )


@router.get(
    "/generated/{candidate_id}",
    response_model=List[GeneratedEmailResponse],
    summary="Get generated emails for candidate"
)
async def get_generated_emails(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all generated emails for a specific candidate."""
    emails = db.query(GeneratedEmail).filter(
        GeneratedEmail.customer_id == current_user.customer_id,
        GeneratedEmail.candidate_id == candidate_id
    ).order_by(GeneratedEmail.created_at.desc()).all()
    
    service = EmailGenerationService(db, current_user.customer_id)
    maildrop = service.get_greenhouse_maildrop()
    
    return [
        GeneratedEmailResponse(
            id=e.id,
            template_id=e.template_id,
            candidate_id=e.candidate_id,
            subject=e.subject,
            body=e.body,
            is_edited=e.is_edited,
            status=e.status,
            created_at=e.created_at,
            greenhouse_maildrop=maildrop
        )
        for e in emails
    ]


@router.put(
    "/generated/{generated_email_id}",
    response_model=GeneratedEmailResponse,
    summary="Update generated email"
)
async def update_generated_email(
    generated_email_id: int,
    request: UpdateGeneratedEmailRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a generated email with manual edits."""
    service = EmailGenerationService(db, current_user.customer_id)
    
    try:
        updated = service.update_generated_email(
            generated_email_id=generated_email_id,
            subject=request.subject,
            body=request.body
        )
        
        return GeneratedEmailResponse(
            id=updated.id,
            template_id=updated.template_id,
            candidate_id=updated.candidate_id,
            subject=updated.subject,
            body=updated.body,
            is_edited=updated.is_edited,
            status=updated.status,
            created_at=updated.created_at,
            greenhouse_maildrop=service.get_greenhouse_maildrop()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ============================================================================
# CUSTOMER SETTINGS ENDPOINTS
# ============================================================================

@router.get(
    "/settings",
    response_model=CustomerSettingsResponse,
    summary="Get customer email settings"
)
async def get_settings(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get customer-specific email and outreach settings."""
    settings = db.query(CustomerSettings).filter(
        CustomerSettings.customer_id == current_user.customer_id
    ).first()
    
    if not settings:
        # Return defaults
        return CustomerSettingsResponse(
            greenhouse_maildrop_address="maildrop@lily.greenhouse.io",
            pdl_cache_ttl_days=30,
            sender_name=None,
            sender_title=None,
            ai_email_generation_enabled=True
        )
    
    return CustomerSettingsResponse(
        greenhouse_maildrop_address=settings.greenhouse_maildrop_address,
        pdl_cache_ttl_days=settings.pdl_cache_ttl_days,
        sender_name=settings.sender_name,
        sender_title=settings.sender_title,
        ai_email_generation_enabled=settings.ai_email_generation_enabled
    )


@router.put(
    "/settings",
    response_model=CustomerSettingsResponse,
    summary="Update customer email settings"
)
async def update_settings(
    request: CustomerSettingsUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update customer-specific email and outreach settings."""
    settings = db.query(CustomerSettings).filter(
        CustomerSettings.customer_id == current_user.customer_id
    ).first()
    
    if not settings:
        # Create new settings
        settings = CustomerSettings(customer_id=current_user.customer_id)
        db.add(settings)
    
    # Update fields
    if request.greenhouse_maildrop_address is not None:
        settings.greenhouse_maildrop_address = request.greenhouse_maildrop_address
    if request.pdl_cache_ttl_days is not None:
        settings.pdl_cache_ttl_days = request.pdl_cache_ttl_days
    if request.sender_name is not None:
        settings.sender_name = request.sender_name
    if request.sender_title is not None:
        settings.sender_title = request.sender_title
    if request.email_signature is not None:
        settings.email_signature = request.email_signature
    if request.ai_email_generation_enabled is not None:
        settings.ai_email_generation_enabled = request.ai_email_generation_enabled
    
    db.commit()
    db.refresh(settings)
    
    logger.info(
        "customer_settings_updated",
        customer_id=current_user.customer_id
    )
    
    return CustomerSettingsResponse(
        greenhouse_maildrop_address=settings.greenhouse_maildrop_address,
        pdl_cache_ttl_days=settings.pdl_cache_ttl_days,
        sender_name=settings.sender_name,
        sender_title=settings.sender_title,
        ai_email_generation_enabled=settings.ai_email_generation_enabled
    )
