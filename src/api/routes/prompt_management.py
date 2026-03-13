"""
Prompt Management API Routes.

Provides endpoints for managing prompt templates across domains.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.models import get_db
from src.middleware.authorization import require_any_permission
from src.services.prompt_management_service import PromptManagementService
from src.models.prompt_template import PromptType as PromptTypeModel, PromptStatus as PromptStatusModel
from src.api.schemas.prompt_management import (
    # Request schemas
    CreatePromptRequest,
    UpdatePromptRequest,
    CreateDomainRequest,
    UpdateDomainRequest,
    PromoteFromGEPARequest,
    # Response schemas
    PromptType,
    PromptStatus,
    PromptSummary,
    PromptDetail,
    PromptVersionList,
    DomainConfigResponse,
    DomainWithPromptsResponse,
    ChangeLogEntry,
    PromptChangeLogResponse,
    DomainListResponse,
    PromptListResponse,
    RAGPromptsResponse,
    DomainStatsResponse,
    CreateDomainFeedbackRequest,
    DomainFeedbackItem,
    DomainFeedbackListResponse,
    GepaSeedFeedbackResponse,
)

router = APIRouter(prefix="/prompts", tags=["Prompt Management"])


# ==================== Domain Endpoints ====================

@router.get("/domains", response_model=DomainListResponse)
async def list_domains(
    include_inactive: bool = Query(False, description="Include inactive domains"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """List all domains with prompt configurations."""
    service = PromptManagementService(db)
    domains = service.list_domain_configs(
        customer_id=current_user.customer_id,
        active_only=not include_inactive,
    )
    
    return DomainListResponse(
        domains=[DomainConfigResponse.model_validate(d) for d in domains],
        total=len(domains),
    )


@router.post("/domains", response_model=DomainConfigResponse, status_code=201)
async def create_domain(
    request: CreateDomainRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Create or get a domain configuration."""
    service = PromptManagementService(db)
    
    # Check if domain already exists
    existing = service.get_or_create_domain_config(
        customer_id=current_user.customer_id,
        domain=request.domain,
        display_name=request.display_name,
    )
    
    # Update with provided settings
    config = service.update_domain_config(
        customer_id=current_user.customer_id,
        domain=request.domain,
        display_name=request.display_name,
        description=request.description,
        use_query_rewrite=request.use_query_rewrite,
        use_custom_system_prompt=request.use_custom_system_prompt,
        default_model=request.default_model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        retrieval_top_k=request.retrieval_top_k,
        similarity_threshold=request.similarity_threshold,
    )
    
    return DomainConfigResponse.model_validate(config)


@router.get("/domains/{domain}", response_model=DomainWithPromptsResponse)
async def get_domain(
    domain: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get domain configuration with active prompts and stats."""
    service = PromptManagementService(db)
    
    config = service.get_or_create_domain_config(
        customer_id=current_user.customer_id,
        domain=domain,
    )
    
    active_prompts = service.get_active_prompts(current_user.customer_id, domain)
    stats = service.get_domain_stats(current_user.customer_id, domain)
    
    return DomainWithPromptsResponse(
        **DomainConfigResponse.model_validate(config).model_dump(),
        prompts={k: PromptSummary.model_validate(v) for k, v in active_prompts.items()},
        stats=stats,
    )


@router.patch("/domains/{domain}", response_model=DomainConfigResponse)
async def update_domain(
    domain: str,
    request: UpdateDomainRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Update domain configuration."""
    service = PromptManagementService(db)
    
    config = service.update_domain_config(
        customer_id=current_user.customer_id,
        domain=domain,
        **request.model_dump(exclude_unset=True),
    )
    
    if not config:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    return DomainConfigResponse.model_validate(config)


@router.get("/domains/{domain}/stats", response_model=DomainStatsResponse)
async def get_domain_stats(
    domain: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get statistics for a domain."""
    service = PromptManagementService(db)
    stats = service.get_domain_stats(current_user.customer_id, domain)
    return DomainStatsResponse(**stats)


# ==================== Prompt Template Endpoints ====================

@router.get("/templates", response_model=PromptListResponse)
async def list_prompts(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    prompt_type: Optional[PromptType] = Query(None, description="Filter by prompt type"),
    status: Optional[PromptStatus] = Query(None, description="Filter by status"),
    include_archived: bool = Query(False, description="Include archived prompts"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """List prompt templates with optional filters."""
    service = PromptManagementService(db)
    
    prompt_type_model = PromptTypeModel(prompt_type.value) if prompt_type else None
    status_model = PromptStatusModel(status.value) if status else None
    
    prompts = service.list_prompts(
        customer_id=current_user.customer_id,
        domain=domain,
        prompt_type=prompt_type_model,
        status=status_model,
        include_archived=include_archived,
    )
    
    return PromptListResponse(
        prompts=[PromptSummary.model_validate(p) for p in prompts],
        total=len(prompts),
    )


@router.post("/templates", response_model=PromptDetail, status_code=201)
async def create_prompt(
    request: CreatePromptRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Create a new prompt template."""
    service = PromptManagementService(db)
    
    prompt = service.create_prompt(
        customer_id=current_user.customer_id,
        domain=request.domain,
        prompt_type=PromptTypeModel(request.prompt_type.value),
        name=request.name,
        content=request.content,
        user_id=current_user.user_id,
        description=request.description,
        variables=request.variables,
        is_active=request.is_active,
    )
    
    return PromptDetail.model_validate(prompt)


@router.get("/templates/{prompt_id}", response_model=PromptDetail)
async def get_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get a specific prompt template by ID."""
    service = PromptManagementService(db)
    prompt = service.get_prompt_by_id(prompt_id)
    
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    if prompt.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return PromptDetail.model_validate(prompt)


@router.patch("/templates/{prompt_id}", response_model=PromptDetail)
async def update_prompt(
    prompt_id: int,
    request: UpdatePromptRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Update a prompt template. Content changes create a new version."""
    service = PromptManagementService(db)
    
    # Verify access
    existing = service.get_prompt_by_id(prompt_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if existing.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Convert status if provided
    update_data = request.model_dump(exclude_unset=True)
    if 'status' in update_data and update_data['status']:
        update_data['status'] = PromptStatusModel(update_data['status'].value)
    
    prompt = service.update_prompt(
        prompt_id=prompt_id,
        user_id=current_user.user_id,
        **update_data,
    )
    
    return PromptDetail.model_validate(prompt)


@router.post("/templates/{prompt_id}/activate", response_model=PromptDetail)
async def activate_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Activate a prompt version (deactivates others of same type)."""
    service = PromptManagementService(db)
    
    # Verify access
    existing = service.get_prompt_by_id(prompt_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if existing.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    prompt = service.activate_prompt(
        prompt_id=prompt_id,
        user_id=current_user.user_id,
    )
    
    return PromptDetail.model_validate(prompt)


@router.post("/templates/{prompt_id}/archive", response_model=PromptDetail)
async def archive_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Archive a prompt version."""
    service = PromptManagementService(db)
    
    # Verify access
    existing = service.get_prompt_by_id(prompt_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if existing.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        prompt = service.archive_prompt(
            prompt_id=prompt_id,
            user_id=current_user.user_id,
        )
        return PromptDetail.model_validate(prompt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/templates/{prompt_id}", status_code=204)
async def delete_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Delete a draft prompt."""
    service = PromptManagementService(db)
    
    # Verify access
    existing = service.get_prompt_by_id(prompt_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if existing.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        service.delete_prompt(prompt_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Version Management ====================

@router.get("/domains/{domain}/types/{prompt_type}/versions", response_model=PromptVersionList)
async def list_prompt_versions(
    domain: str,
    prompt_type: PromptType,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """List all versions of a specific prompt type."""
    service = PromptManagementService(db)
    
    versions = service.list_prompt_versions(
        customer_id=current_user.customer_id,
        domain=domain,
        prompt_type=PromptTypeModel(prompt_type.value),
    )
    
    active_version = next((v.version for v in versions if v.is_active), None)
    
    return PromptVersionList(
        domain=domain,
        prompt_type=prompt_type,
        versions=[PromptSummary.model_validate(v) for v in versions],
        active_version=active_version,
    )


@router.get("/domains/{domain}/types/{prompt_type}/active", response_model=PromptDetail)
async def get_active_prompt(
    domain: str,
    prompt_type: PromptType,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get the active version of a specific prompt type."""
    service = PromptManagementService(db)
    
    prompt = service.get_prompt(
        customer_id=current_user.customer_id,
        domain=domain,
        prompt_type=PromptTypeModel(prompt_type.value),
    )
    
    if not prompt:
        raise HTTPException(status_code=404, detail="No active prompt found for this type")
    
    return PromptDetail.model_validate(prompt)


# ==================== RAG Integration ====================

@router.get("/domains/{domain}/rag-prompts", response_model=RAGPromptsResponse)
async def get_rag_prompts(
    domain: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """
    Get all active prompts for a domain in RAG-ready format.
    
    This endpoint is optimized for use by the RAG pipeline.
    """
    service = PromptManagementService(db)
    prompts = service.get_rag_prompts(current_user.customer_id, domain)
    
    return RAGPromptsResponse(
        domain=domain,
        prompts=prompts,
    )


# ==================== Domain Feedback (prod → GEPA) ====================

@router.post("/domains/{domain}/feedback", response_model=DomainFeedbackItem, status_code=201)
async def create_domain_feedback(
    domain: str,
    request: CreateDomainFeedbackRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    service = PromptManagementService(db)
    fb = service.create_domain_feedback(
        customer_id=current_user.customer_id,
        domain=domain,
        environment=request.environment,
        rating_numeric=request.rating_numeric,
        comment=request.comment,
        tags=request.tags,
        improvement_suggestions=request.improvement_suggestions,
        target_components=request.target_components,
        created_by_user_id=current_user.user_id,
    )
    return DomainFeedbackItem.model_validate(fb)


@router.get("/domains/{domain}/feedback", response_model=DomainFeedbackListResponse)
async def list_domain_feedback(
    domain: str,
    environment: Optional[str] = Query(None, pattern="^(prod|staging|dev)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    service = PromptManagementService(db)
    offset = (page - 1) * page_size
    items, total = service.list_domain_feedback(
        customer_id=current_user.customer_id,
        domain=domain,
        environment=environment,
        limit=page_size,
        offset=offset,
    )
    return DomainFeedbackListResponse(
        items=[DomainFeedbackItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/domains/{domain}/gepa-seed-feedback", response_model=GepaSeedFeedbackResponse)
async def export_gepa_seed_feedback(
    domain: str,
    environment: str = Query("prod", pattern="^(prod|staging|dev)$"),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """
    Export domain feedback in the shape GEPA expects (seed_feedback).
    Intended for starting a new GEPA run based on prod feedback for current prompts.
    """
    service = PromptManagementService(db)
    seed_feedback = service.export_seed_feedback_for_gepa(
        customer_id=current_user.customer_id,
        domain=domain,
        environment=environment,
        limit=limit,
    )
    return GepaSeedFeedbackResponse(domain=domain, environment=environment, seed_feedback=seed_feedback)


# ==================== GEPA Integration ====================

@router.post("/from-gepa", response_model=PromptDetail, status_code=201)
async def promote_from_gepa(
    request: PromoteFromGEPARequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Create a new prompt version from a GEPA optimization result.
    
    Called when promoting a variant from GEPA optimizer.
    """
    service = PromptManagementService(db)
    
    prompt = service.promote_from_gepa(
        customer_id=current_user.customer_id,
        domain=request.domain,
        prompt_type=PromptTypeModel(request.prompt_type.value),
        content=request.content,
        gepa_job_id=request.gepa_job_id,
        gepa_variant_id=request.gepa_variant_id,
        user_id=current_user.user_id,
        quality_score=request.quality_score,
        auto_activate=request.auto_activate,
    )
    
    return PromptDetail.model_validate(prompt)


# ==================== Change Logs ====================

@router.get("/templates/{prompt_id}/changelog", response_model=PromptChangeLogResponse)
async def get_prompt_changelog(
    prompt_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get change log for a specific prompt."""
    service = PromptManagementService(db)
    
    # Verify access
    existing = service.get_prompt_by_id(prompt_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if existing.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    logs = service.get_change_logs(prompt_id=prompt_id)
    
    return PromptChangeLogResponse(
        prompt_id=prompt_id,
        logs=[ChangeLogEntry.model_validate(log) for log in logs],
    )


@router.get("/changelog", response_model=List[ChangeLogEntry])
async def get_all_changelogs(
    limit: int = Query(100, le=500, description="Max entries to return"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get all change logs for the customer."""
    service = PromptManagementService(db)
    logs = service.get_change_logs(customer_id=current_user.customer_id, limit=limit)
    
    return [ChangeLogEntry.model_validate(log) for log in logs]
