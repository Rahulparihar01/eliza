"""
Content Writer API Routes

API endpoints for the Research-First Content Writer product.
"""
import logging
from typing import Optional, List, Union
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.middleware.authorization import AuthorizationMiddleware
from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory

from src.api.schemas.content_writer import (
    # Enums
    ContentFormat, SourceType, RunStatus, SkillType, IssueType,
    # Run schemas
    RunCreateRequest, RunResponse, RunListResponse, RunSubmitResponse,
    POVSelectRequest, HookSelectRequest, OutlineSelectRequest,
    # Research Pack schemas
    ResearchPackResponse, ResearchPackActionRequest, ResearchPackActionResponse,
    ResearchPackExcerptResponse,
    # Draft schemas
    DraftArtifactResponse, DraftRefineRequest,
    POVPointersResponse, SectionRefineResponse,
    GenerateDraftRequest, GenerateDraftResponse,
    DraftVersionListResponse,
    # Skill schemas
    SkillCreateRequest, SkillUpdateRequest, SkillResponse, SkillListResponse,
    # POV schemas
    POVPointerResponse, HookOptionResponse, OutlineOptionResponse,
)
from src.services.content_writer import ContentWriterService
from src.models.content_writer import (
    ContentWriterRun, ResearchPack, DraftArtifact, ContentWriterSkill,
    RunStatus as RunStatusModel,
)

logger = get_logger(__name__, LogCategory.API)
settings = get_settings()

router = APIRouter(prefix="/v1/content-writer", tags=["Content Writer"])
auth_middleware = AuthorizationMiddleware()


# ==================== Run Endpoints ====================

@router.post(
    "/runs",
    response_model=RunSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new content writer run",
    description="Start a new content generation run. Returns immediately with run_id for tracking."
)
async def create_run(
    request: RunCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """
    Create a new content writer run.
    
    The run will be processed through:
    1. Research Phase - Gather evidence from selected sources
    2. POV Generation - Generate 3-5 distinct POV options
    3. Draft Generation - Create content based on selected POV
    """
    logger.info(
        "content_writer_run_created",
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        topic=request.topic[:50],
        format=request.format.value,
    )
    
    try:
        service = ContentWriterService(db)
        run = service.create_run(
            request=request,
            customer_id=current_user.customer_id,
            user_id=current_user.user_id,
        )
        
        # Queue Celery task for processing
        from src.tasks.content_writer_tasks import process_content_writer_run
        from celery.exceptions import CeleryError
        
        try:
            task_result = process_content_writer_run.delay(
                run_id=run.run_id,
                user_id=current_user.user_id,
                customer_id=current_user.customer_id,
            )
            
            # Update run with task_id
            service.update_run_status(
                run_id=run.run_id,
                status=RunStatusModel.RESEARCHING,
                task_id=task_result.id,
            )
            
            return RunSubmitResponse(
                run_id=run.run_id,
                status=RunStatus.RESEARCHING,
                message="Run created, research starting",
                task_id=task_result.id,
            )
        except CeleryError as e:
            logger.error(f"Failed to queue content writer task: {e}")
            service.update_run_status(
                run_id=run.run_id,
                status=RunStatusModel.FAILED,
                error_message="Failed to queue processing task",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Processing workers unavailable"
            )
        
    except Exception as e:
        logger.error(f"Failed to create content writer run: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/runs",
    response_model=RunListResponse,
    summary="List content writer runs",
    description="Get paginated list of runs for the current user."
)
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[RunStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """List runs for the current user."""
    service = ContentWriterService(db)
    
    status_model = RunStatusModel(status_filter.value) if status_filter else None
    
    runs, total = service.list_runs(
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
        status=status_model,
    )
    
    return RunListResponse(
        items=[_run_to_response(run) for run in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/runs/{run_id}",
    response_model=RunResponse,
    summary="Get run details",
    description="Get full details of a run including research pack and latest draft."
)
async def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """Get run details."""
    service = ContentWriterService(db)
    
    run = service.get_run(
        run_id=run_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
    )
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    return _run_to_response(run, include_details=True)


@router.post(
    "/runs/{run_id}/select-pov",
    response_model=RunResponse,
    summary="Select POV for run",
    description="Select a POV from generated options or provide a custom POV."
)
async def select_pov(
    run_id: str,
    request: POVSelectRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Select POV for the run."""
    service = ContentWriterService(db)
    
    run = service.get_run(run_id, current_user.customer_id, current_user.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run = service.select_pov(
        run_id=run_id,
        pov_index=request.pov_index,
        custom_pov=request.custom_pov,
    )
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return _run_to_response(run)


@router.post(
    "/runs/{run_id}/select-hook",
    response_model=RunResponse,
    summary="Select hook for run",
    description="Select a hook from generated options."
)
async def select_hook(
    run_id: str,
    request: HookSelectRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Select hook for the run."""
    service = ContentWriterService(db)
    
    run = service.get_run(run_id, current_user.customer_id, current_user.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run = service.select_hook(run_id=run_id, hook_index=request.hook_index)
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return _run_to_response(run)


@router.post(
    "/runs/{run_id}/select-outline",
    response_model=RunResponse,
    summary="Select outline for run",
    description="Select an outline from generated options."
)
async def select_outline(
    run_id: str,
    request: OutlineSelectRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Select outline for the run."""
    service = ContentWriterService(db)
    
    run = service.get_run(run_id, current_user.customer_id, current_user.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run = service.select_outline(run_id=run_id, outline_index=request.outline_index)
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return _run_to_response(run)


@router.post(
    "/runs/{run_id}/generate-draft",
    response_model=GenerateDraftResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate draft (Fast Path)",
    description="Generate full draft using selected POV, hook, and outline."
)
async def generate_draft(
    run_id: str,
    request: GenerateDraftRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Generate draft using Fast Path."""
    service = ContentWriterService(db)
    
    run = service.get_run(run_id, current_user.customer_id, current_user.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if not run.selected_pov:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="POV must be selected before generating draft"
        )
    
    # Queue draft generation task
    from src.tasks.content_writer_tasks import generate_draft_task
    from celery.exceptions import CeleryError
    
    try:
        task_result = generate_draft_task.delay(
            run_id=run_id,
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
            apply_default_skills=request.apply_default_skills,
            specific_skill_ids=request.specific_skill_ids,
        )
        
        service.update_run_status(run_id, RunStatusModel.DRAFTING, task_id=task_result.id)
        
        return GenerateDraftResponse(
            run_id=run_id,
            status=RunStatus.DRAFTING,
            message="Draft generation started",
            draft=None,
        )
    except CeleryError as e:
        logger.error(f"Failed to queue draft generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Processing workers unavailable"
        )


# ==================== Research Pack Endpoints ====================

@router.get(
    "/runs/{run_id}/research-pack",
    response_model=ResearchPackResponse,
    summary="Get research pack",
    description="Get the research pack for a run."
)
async def get_research_pack(
    run_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """Get research pack for a run."""
    service = ContentWriterService(db)
    
    run = service.get_run(run_id, current_user.customer_id, current_user.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    research_pack = service.get_research_pack(run_id)
    if not research_pack:
        raise HTTPException(status_code=404, detail="Research pack not found")
    
    return _research_pack_to_response(run_id, research_pack)


@router.post(
    "/runs/{run_id}/research-pack/actions",
    response_model=ResearchPackActionResponse,
    summary="Research pack actions",
    description="Perform actions on research pack excerpts (use, ignore, find opposing view)."
)
async def research_pack_action(
    run_id: str,
    request: ResearchPackActionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Perform action on research pack excerpt."""
    service = ContentWriterService(db)
    
    run = service.get_run(run_id, current_user.customer_id, current_user.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    research_pack = service.get_research_pack(run_id)
    if not research_pack:
        raise HTTPException(status_code=404, detail="Research pack not found")
    
    # Handle action
    if request.action == "use":
        # Add to selected excerpts
        selected = research_pack.selected_excerpt_ids or []
        if request.excerpt_id not in selected:
            selected.append(request.excerpt_id)
        service.update_research_pack_selections(run_id, selected)
        
        return ResearchPackActionResponse(
            success=True,
            action="use",
            excerpt_id=request.excerpt_id,
            message="Excerpt added to selected evidence",
        )
    
    elif request.action == "ignore":
        # Remove from selected excerpts
        selected = research_pack.selected_excerpt_ids or []
        if request.excerpt_id in selected:
            selected.remove(request.excerpt_id)
        service.update_research_pack_selections(run_id, selected)
        
        return ResearchPackActionResponse(
            success=True,
            action="ignore",
            excerpt_id=request.excerpt_id,
            message="Excerpt removed from selected evidence",
        )
    
    elif request.action in ("find_opposing_view", "find_stronger_support"):
        # TODO: Queue task to find additional evidence
        # For MVP, return placeholder response
        return ResearchPackActionResponse(
            success=True,
            action=request.action,
            excerpt_id=request.excerpt_id,
            message=f"Action '{request.action}' will be processed (coming soon)",
            new_excerpts=None,
        )
    
    raise HTTPException(status_code=422, detail=f"Unknown action: {request.action}")


# ==================== Draft Refinement Endpoints ====================

@router.post(
    "/runs/{run_id}/refine",
    response_model=Union[POVPointersResponse, SectionRefineResponse],
    summary="Refine draft section",
    description="Two-step refinement: generate POV pointers or apply selected POV."
)
async def refine_draft_section(
    run_id: str,
    request: DraftRefineRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """
    Refine a draft section with structured feedback.
    
    Two-step workflow:
    1. refinement_type='generate_pov_pointers': Generate POV approach suggestions
    2. refinement_type='section_critique': Rewrite section with selected POV
    """
    service = ContentWriterService(db)
    
    run = service.get_run(run_id, current_user.customer_id, current_user.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    latest_draft = service.get_latest_draft(run_id)
    if not latest_draft:
        raise HTTPException(status_code=404, detail="No draft found for this run")
    
    if not request.section:
        raise HTTPException(status_code=422, detail="section is required for refinement")
    
    # Extract section context (2-3 paragraphs + document summary)
    try:
        section_context = service.extract_section_context(
            draft=latest_draft,
            section=request.section,
            context_paragraphs=2,
            include_summary=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Load research pack
    research_pack = service.get_research_pack(run_id)
    
    # STEP 1: Generate POV Pointers
    if request.refinement_type == "generate_pov_pointers":
        from src.tasks.content_writer_tasks import generate_pov_pointers_task
        
        task_result = generate_pov_pointers_task.delay(
            run_id=run_id,
            section_text=request.section.highlighted_text,
            document_summary=section_context["document_summary"],
            context_before=section_context["before"],
            context_after=section_context["after"],
            issue_types=[it.value for it in request.issue_types] if request.issue_types else [],
            issue_explanation=request.issue_explanation,
            num_pointers=request.num_pov_pointers,
            research_pack=research_pack.excerpts if research_pack else None,
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
        )
        
        # Wait for result (2-5 minutes timeout)
        pov_result = task_result.get(timeout=300)
        
        return POVPointersResponse(
            section_text=request.section.highlighted_text,
            document_summary=section_context["document_summary"],
            issue_types=request.issue_types or [],
            pov_pointers=[
                POVPointerResponse(**p) for p in pov_result["pov_pointers"]
            ],
        )
    
    # STEP 2: Apply Selected POV & Rewrite
    elif request.refinement_type == "section_critique":
        if not request.pov_selection:
            raise HTTPException(status_code=422, detail="pov_selection required for section_critique")
        
        # Get user skills
        user_skills = service.get_user_skills(
            current_user.customer_id,
            current_user.user_id,
            skill_types=["voice", "pillars"],
        )
        
        from src.tasks.content_writer_tasks import refine_draft_section_task
        
        task_result = refine_draft_section_task.delay(
            run_id=run_id,
            section_text=request.section.highlighted_text,
            document_summary=section_context["document_summary"],
            context_before=section_context["before"],
            context_after=section_context["after"],
            issue_types=[it.value for it in request.issue_types] if request.issue_types else [],
            issue_explanation=request.issue_explanation,
            pov_selection=request.pov_selection.dict(),
            research_pack=research_pack.excerpts if research_pack else None,
            user_skills=[s.content for s in user_skills],
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
        )
        
        # Wait for result (2-5 minutes timeout)
        refined_result = task_result.get(timeout=300)
        
        # Save as new draft version
        new_draft = service.create_draft_version(
            run_id=run_id,
            content=service.replace_section(
                latest_draft.content,
                request.section,
                refined_result["refined_text"]
            ),
            parent_version_id=latest_draft.id,
            refinement_type="section_critique",
            refinement_instruction=f"Issues: {request.issue_types}; POV: {request.pov_selection.custom_pov or f'pointer_{request.pov_selection.selected_index}'}",
        )
        
        return SectionRefineResponse(
            original_text=request.section.highlighted_text,
            refined_text=refined_result["refined_text"],
            changes_summary=refined_result.get("changes_summary", "Section refined"),
            issues_addressed=request.issue_types or [],
            pov_applied=refined_result.get("pov_applied", "Selected POV applied"),
            research_pack_refs=refined_result.get("research_pack_refs"),
            new_version=_draft_to_response(run_id, new_draft) if new_draft else None,
        )
    
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported refinement_type: {request.refinement_type}"
        )


# ==================== Draft Version Endpoints ====================

@router.get(
    "/runs/{run_id}/drafts",
    response_model=DraftVersionListResponse,
    summary="List draft versions",
    description="Get all draft versions for a run."
)
async def list_draft_versions(
    run_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """List all draft versions."""
    service = ContentWriterService(db)
    
    run = service.get_run(run_id, current_user.customer_id, current_user.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    drafts = service.list_draft_versions(run_id)
    
    return DraftVersionListResponse(
        run_id=run_id,
        versions=[_draft_to_response(run_id, d) for d in drafts],
        total=len(drafts),
    )


@router.get(
    "/runs/{run_id}/drafts/{version}",
    response_model=DraftArtifactResponse,
    summary="Get draft version",
    description="Get a specific draft version."
)
async def get_draft_version(
    run_id: str,
    version: int,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """Get specific draft version."""
    service = ContentWriterService(db)
    
    run = service.get_run(run_id, current_user.customer_id, current_user.user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    draft = service.get_draft_version(run_id, version)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft version {version} not found")
    
    return _draft_to_response(run_id, draft)


# ==================== Skills Endpoints ====================

@router.get(
    "/skills",
    response_model=SkillListResponse,
    summary="List skills",
    description="Get all skills for the current user."
)
async def list_skills(
    skill_type: Optional[SkillType] = None,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """List user's skills."""
    service = ContentWriterService(db)
    
    skill_types = [skill_type] if skill_type else None
    
    skills = service.list_skills(
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        skill_types=skill_types,
    )
    
    return SkillListResponse(
        items=[_skill_to_response(s) for s in skills],
        total=len(skills),
    )


@router.post(
    "/skills",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create skill",
    description="Create a new skill."
)
async def create_skill(
    request: SkillCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Create a new skill."""
    service = ContentWriterService(db)
    
    from src.models.content_writer import SkillType as SkillTypeModel
    
    skill = service.create_skill(
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        skill_type=SkillTypeModel(request.skill_type.value),
        name=request.name,
        description=request.description,
        content=request.content,
        is_default=request.is_default,
    )
    
    return _skill_to_response(skill)


@router.get(
    "/skills/{skill_id}",
    response_model=SkillResponse,
    summary="Get skill",
    description="Get a skill by ID."
)
async def get_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """Get a skill."""
    service = ContentWriterService(db)
    
    skill = service.get_skill(
        skill_id=skill_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
    )
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    return _skill_to_response(skill)


@router.put(
    "/skills/{skill_id}",
    response_model=SkillResponse,
    summary="Update skill",
    description="Update a skill."
)
async def update_skill(
    skill_id: str,
    request: SkillUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Update a skill."""
    service = ContentWriterService(db)
    
    skill = service.update_skill(
        skill_id=skill_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        name=request.name,
        description=request.description,
        content=request.content,
        is_default=request.is_default,
    )
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    return _skill_to_response(skill)


@router.delete(
    "/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete skill",
    description="Delete a skill."
)
async def delete_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Delete a skill."""
    service = ContentWriterService(db)
    
    success = service.delete_skill(
        skill_id=skill_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    return None


# ==================== Helper Functions ====================

def _run_to_response(run: ContentWriterRun, include_details: bool = False) -> RunResponse:
    """Convert run model to response."""
    response = RunResponse(
        id=run.id,
        run_id=run.run_id,
        customer_id=run.customer_id,
        user_id=run.user_id,
        topic=run.topic,
        format=ContentFormat(run.format.value if hasattr(run.format, 'value') else run.format),
        status=RunStatus(run.status.value if hasattr(run.status, 'value') else run.status),
        selected_sources=[SourceType(s) for s in run.selected_sources],
        pasted_text=run.pasted_text,
        constraints=run.constraints,
        pov_options=[POVPointerResponse(**p) for p in run.pov_options] if run.pov_options else None,
        selected_pov=run.selected_pov,
        hook_options=[HookOptionResponse(**h) for h in run.hook_options] if run.hook_options else None,
        selected_hook=run.selected_hook,
        outline_options=[OutlineOptionResponse(**o) for o in run.outline_options] if run.outline_options else None,
        selected_outline=run.selected_outline,
        applied_skill_ids=run.applied_skill_ids,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        task_id=run.task_id,
    )
    
    if include_details:
        if run.research_pack:
            response.research_pack = _research_pack_to_response(run.run_id, run.research_pack)
        
        if run.draft_artifacts:
            latest_draft = run.draft_artifacts[0] if run.draft_artifacts else None
            if latest_draft:
                response.latest_draft = _draft_to_response(run.run_id, latest_draft)
    
    return response


def _research_pack_to_response(run_id: str, rp: ResearchPack) -> ResearchPackResponse:
    """Convert research pack model to response."""
    selected_ids = rp.selected_excerpt_ids or []
    
    excerpts = []
    for e in rp.excerpts or []:
        excerpts.append(ResearchPackExcerptResponse(
            id=e.get('id', 0),
            text=e.get('text', ''),
            source_url=e.get('source_url'),
            source_type=SourceType(e.get('source_type', 'web')),
            metadata=e.get('metadata'),
            selected=e.get('id', 0) in selected_ids,
        ))
    
    return ResearchPackResponse(
        run_id=run_id,
        key_takeaways=rp.key_takeaways or [],
        excerpts=excerpts,
        contested_items=rp.contested_items,
        best_counterargument=rp.best_counterargument,
        selected_excerpt_ids=selected_ids,
    )


def _draft_to_response(run_id: str, draft: DraftArtifact) -> DraftArtifactResponse:
    """Convert draft model to response."""
    return DraftArtifactResponse(
        id=draft.id,
        run_id=run_id,
        version=draft.version,
        format=ContentFormat(draft.format.value if hasattr(draft.format, 'value') else draft.format),
        content=draft.content,
        word_count=draft.word_count,
        character_count=draft.character_count,
        generated_at=draft.generated_at,
        refinement_type=draft.refinement_type,
        refinement_instruction=draft.refinement_instruction,
    )


def _skill_to_response(skill: ContentWriterSkill) -> SkillResponse:
    """Convert skill model to response."""
    return SkillResponse(
        id=skill.id,
        skill_id=skill.skill_id,
        skill_type=SkillType(skill.skill_type.value if hasattr(skill.skill_type, 'value') else skill.skill_type),
        name=skill.name,
        description=skill.description,
        content=skill.content,
        is_default=skill.is_default,
        usage_count=skill.usage_count,
        last_used_at=skill.last_used_at,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )
