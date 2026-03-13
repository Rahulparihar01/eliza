"""
Content Research API Routes

API endpoints for research-first content generation using OpenAI web search.
NO external data connectors - only OpenAI web search.

WORKFLOW:
1. POST /runs - Start research (web search for sources)
2. GET /runs/{run_id}/sources - View all sources found
3. POST /runs/{run_id}/select-sources - Multi-select which sources to use
4. POST /runs/{run_id}/generate-povs - Generate POV options (optional)
5. POST /runs/{run_id}/select-pov - Select POV (optional)
6. POST /runs/{run_id}/generate-hooks - Generate hook options (optional)
7. POST /runs/{run_id}/select-hook - Select hook (optional)
8. POST /runs/{run_id}/generate - Generate content from selected sources
"""
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from src.models.database import get_db
from src.middleware.authorization import AuthorizationMiddleware
from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory

from src.api.schemas.content_research import (
    ResearchRunStatus,
    WebSourceResponse, ResearchPackResponse,
    SourceSelectRequest, SelectedSourcesResponse,
    GeneratedContentResponse, CitationResponse,
    ResearchRunCreateRequest, ResearchRunResponse,
    ResearchRunListResponse, ResearchRunSubmitResponse,
    POVOptionResponse, POVSelectRequest,
    HookOptionResponse, HookSelectRequest,
    GenerateContentRequest, GenerateContentResponse,
)
from src.flows.content_research_flow import ContentResearchFlow, create_content_research_flow

logger = get_logger(__name__, LogCategory.API)
settings = get_settings()

router = APIRouter(prefix="/v1/content-research", tags=["Content Research"])
auth_middleware = AuthorizationMiddleware()

# In-memory storage for flow instances (in production, use Redis or DB)
# This is a simple approach - in production you'd persist flow state to DB
_flow_instances: dict = {}


# ==================== Run Endpoints ====================

@router.post(
    "/runs",
    response_model=ResearchRunSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start content research",
    description="""
    Start a new content research run using OpenAI web search.
    
    This will:
    1. Generate multiple search queries for HIGH RECALL
    2. Execute web searches using OpenAI's web search tool
    3. Score and rank sources by relevance
    4. Return sources for user multi-selection
    """
)
async def create_research_run(
    request: ResearchRunCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Create a new content research run."""
    logger.info(
        "content_research_run_created",
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        topic=request.topic[:50],
        target_word_count=request.target_word_count,
    )
    
    try:
        # Create flow instance
        flow = create_content_research_flow(
            topic=request.topic,
            target_word_count=request.target_word_count,
            customer_id=current_user.customer_id,
            user_id=current_user.user_id,
            constraints=request.constraints,
        )
        
        # Store flow instance
        _flow_instances[flow.run_id] = {
            "flow": flow,
            "status": ResearchRunStatus.RESEARCHING,
            "customer_id": current_user.customer_id,
            "user_id": current_user.user_id,
            "created_at": datetime.utcnow(),
            "request": request,
        }
        
        # Run research in background
        def run_research():
            try:
                research_pack = flow.conduct_research(num_queries=request.num_search_queries)
                _flow_instances[flow.run_id]["status"] = ResearchRunStatus.SOURCE_SELECTION
                _flow_instances[flow.run_id]["research_pack"] = research_pack
            except Exception as e:
                logger.error(f"Research failed: {e}")
                _flow_instances[flow.run_id]["status"] = ResearchRunStatus.FAILED
                _flow_instances[flow.run_id]["error"] = str(e)
        
        background_tasks.add_task(run_research)
        
        return ResearchRunSubmitResponse(
            run_id=flow.run_id,
            status=ResearchRunStatus.RESEARCHING,
            message="Research started. Web search in progress.",
        )
        
    except Exception as e:
        logger.error(f"Failed to create research run: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/runs/{run_id}",
    response_model=ResearchRunResponse,
    summary="Get research run status",
    description="Get full details of a research run including sources and content."
)
async def get_research_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """Get research run details."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    # Verify ownership
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    flow = run_data["flow"]
    request = run_data["request"]
    
    # Build response
    response_data = {
        "id": 0,  # In-memory, no DB ID
        "run_id": run_id,
        "customer_id": run_data["customer_id"],
        "user_id": run_data["user_id"],
        "topic": request.topic,
        "target_word_count": request.target_word_count,
        "status": run_data["status"],
        "created_at": run_data["created_at"],
        "updated_at": datetime.utcnow(),
    }
    
    # Add research data if available
    if "research_pack" in run_data:
        rp = run_data["research_pack"]
        response_data["queries_executed"] = rp.queries_executed
        response_data["total_sources_found"] = rp.total_sources_found
        response_data["sources"] = [
            WebSourceResponse(
                id=s.id,
                url=s.url,
                title=s.title,
                snippet=s.snippet[:500],
                relevance_score=s.relevance_score,
                query_origin=s.query_origin,
                source_type=s.source_type,
            )
            for s in rp.sources
        ]
    
    # Add selected sources if available
    if flow.selected_sources:
        response_data["selected_source_ids"] = flow.selected_sources.source_ids
        response_data["selected_sources"] = [
            WebSourceResponse(
                id=s.id,
                url=s.url,
                title=s.title,
                snippet=s.snippet[:500],
                relevance_score=s.relevance_score,
                query_origin=s.query_origin,
                source_type=s.source_type,
            )
            for s in flow.selected_sources.sources
        ]
    
    # Add content if generated
    if "content" in run_data:
        response_data["content"] = run_data["content"]
    
    # Add error if any
    if "error" in run_data:
        response_data["error_message"] = run_data["error"]
    
    return ResearchRunResponse(**response_data)


# ==================== Source Endpoints ====================

@router.get(
    "/runs/{run_id}/sources",
    response_model=ResearchPackResponse,
    summary="Get discovered sources",
    description="""
    Get all sources discovered during research.
    
    Sources are ranked by relevance. User should multi-select
    which sources to use for content generation.
    """
)
async def get_sources(
    run_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """Get all sources for selection."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if "research_pack" not in run_data:
        if run_data["status"] == ResearchRunStatus.RESEARCHING:
            raise HTTPException(
                status_code=status.HTTP_425_TOO_EARLY,
                detail="Research still in progress. Check back shortly."
            )
        raise HTTPException(status_code=404, detail="Research pack not found")
    
    rp = run_data["research_pack"]
    
    return ResearchPackResponse(
        run_id=run_id,
        topic=rp.topic,
        queries_executed=rp.queries_executed,
        total_sources_found=rp.total_sources_found,
        sources=[
            WebSourceResponse(
                id=s.id,
                url=s.url,
                title=s.title,
                snippet=s.snippet,
                relevance_score=s.relevance_score,
                query_origin=s.query_origin,
                source_type=s.source_type,
                retrieved_at=s.retrieved_at,
            )
            for s in rp.sources
        ],
        status=run_data["status"],
    )


@router.post(
    "/runs/{run_id}/select-sources",
    response_model=SelectedSourcesResponse,
    summary="Select sources for content",
    description="""
    Multi-select which sources to use for content generation.
    
    Content will be generated ONLY from selected sources.
    Every claim will be cited. No information will be fabricated.
    """
)
async def select_sources(
    run_id: str,
    request: SourceSelectRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Select sources for content generation."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if run_data["status"] not in [ResearchRunStatus.SOURCE_SELECTION, ResearchRunStatus.POV_SELECTION]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot select sources in status: {run_data['status']}"
        )
    
    flow = run_data["flow"]
    
    try:
        selected = flow.select_sources(
            source_ids=request.source_ids,
            usage_notes=request.usage_notes,
        )
        
        run_data["status"] = ResearchRunStatus.POV_SELECTION
        
        return SelectedSourcesResponse(
            run_id=run_id,
            selected_count=len(selected.sources),
            sources=[
                WebSourceResponse(
                    id=s.id,
                    url=s.url,
                    title=s.title,
                    snippet=s.snippet[:500],
                    relevance_score=s.relevance_score,
                    query_origin=s.query_origin,
                    source_type=s.source_type,
                )
                for s in selected.sources
            ],
            status=ResearchRunStatus.POV_SELECTION,
            message=f"Selected {len(selected.sources)} sources. Ready for POV selection or content generation.",
        )
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ==================== POV Endpoints ====================

@router.post(
    "/runs/{run_id}/generate-povs",
    response_model=List[POVOptionResponse],
    summary="Generate POV options",
    description="Generate POV options based on selected sources (optional step)."
)
async def generate_povs(
    run_id: str,
    num_povs: int = Query(5, ge=3, le=10),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Generate POV options from selected sources."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    flow = run_data["flow"]
    
    if not flow.selected_sources:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Must select sources before generating POVs"
        )
    
    # Generate POVs based on selected sources
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    
    source_summary = "\n\n".join([
        f"Source: {s.title}\n{s.snippet[:300]}"
        for s in flow.selected_sources.sources[:10]
    ])
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""Generate {num_povs} distinct POV approaches for writing about this topic.
                Each POV should be grounded in the source material - don't make up angles that aren't supported.
                
                Return JSON array:
                [
                    {{
                        "index": 0,
                        "label": "Short label",
                        "description": "2-3 sentence description",
                        "key_concepts": ["concept1", "concept2", "concept3"],
                        "source_refs": ["source_id1", "source_id2"]
                    }}
                ]"""
            },
            {
                "role": "user",
                "content": f"Topic: {flow.topic}\n\nSelected Sources:\n{source_summary}"
            }
        ],
        temperature=0.7,
    )
    
    import json
    import re
    try:
        content_text = response.choices[0].message.content
        # Strip markdown code blocks if present
        content_text = re.sub(r'^```(?:json)?\s*', '', content_text.strip())
        content_text = re.sub(r'\s*```$', '', content_text)
        povs = json.loads(content_text)
        run_data["pov_options"] = povs
        return [POVOptionResponse(**pov) for pov in povs]
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse POV JSON: {e}, content: {response.choices[0].message.content[:200]}")
        raise HTTPException(status_code=500, detail="Failed to generate POV options")


@router.post(
    "/runs/{run_id}/select-pov",
    summary="Select POV",
    description="Select a POV for content generation (optional)."
)
async def select_pov(
    run_id: str,
    request: POVSelectRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Select POV for content generation."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if request.pov_index is not None:
        if "pov_options" not in run_data:
            raise HTTPException(status_code=422, detail="Must generate POV options first")
        
        if request.pov_index >= len(run_data["pov_options"]):
            raise HTTPException(status_code=422, detail="Invalid POV index")
        
        run_data["selected_pov"] = run_data["pov_options"][request.pov_index]
    else:
        run_data["selected_pov"] = {
            "label": "Custom POV",
            "description": request.custom_pov,
            "key_concepts": [],
        }
    
    run_data["status"] = ResearchRunStatus.HOOK_SELECTION
    
    return {"message": "POV selected", "selected_pov": run_data["selected_pov"]}


# ==================== Hook Endpoints ====================

@router.post(
    "/runs/{run_id}/generate-hooks",
    response_model=List[HookOptionResponse],
    summary="Generate hook options",
    description="Generate hook options based on selected sources and POV (optional)."
)
async def generate_hooks(
    run_id: str,
    num_hooks: int = Query(5, ge=3, le=10),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Generate hook options."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    flow = run_data["flow"]
    
    if not flow.selected_sources:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Must select sources first"
        )
    
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    
    pov_context = ""
    if "selected_pov" in run_data:
        pov = run_data["selected_pov"]
        pov_context = f"\nPOV: {pov.get('label', '')} - {pov.get('description', '')}"
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""Generate {num_hooks} compelling hooks for an article (target: ~{flow.target_word_count} words).
                
                Use the 2-line structure:
                - Line 1: Social proof + personal story (must work standalone on mobile)
                - Line 2: Expectation setting (what reader will get)
                
                Return JSON array:
                [
                    {{
                        "index": 0,
                        "title": null,
                        "lede": "Full hook text",
                        "line1": "Just the first line",
                        "pattern": "Hook pattern used",
                        "why_it_works": "Brief explanation"
                    }}
                ]"""
            },
            {
                "role": "user",
                "content": f"Topic: {flow.topic}{pov_context}\n\nTarget length: ~{flow.target_word_count} words"
            }
        ],
        temperature=0.8,
    )
    
    import json
    import re
    try:
        content_text = response.choices[0].message.content
        # Strip markdown code blocks if present
        content_text = re.sub(r'^```(?:json)?\s*', '', content_text.strip())
        content_text = re.sub(r'\s*```$', '', content_text)
        hooks = json.loads(content_text)
        run_data["hook_options"] = hooks
        return [HookOptionResponse(**hook) for hook in hooks]
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse hooks JSON: {e}, content: {response.choices[0].message.content[:200]}")
        raise HTTPException(status_code=500, detail="Failed to generate hooks")


@router.post(
    "/runs/{run_id}/select-hook",
    summary="Select hook",
    description="Select a hook for content generation (optional)."
)
async def select_hook(
    run_id: str,
    request: HookSelectRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Select hook for content generation."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if "hook_options" not in run_data:
        raise HTTPException(status_code=422, detail="Must generate hook options first")
    
    if request.hook_index >= len(run_data["hook_options"]):
        raise HTTPException(status_code=422, detail="Invalid hook index")
    
    run_data["selected_hook"] = run_data["hook_options"][request.hook_index]
    
    return {"message": "Hook selected", "selected_hook": run_data["selected_hook"]}


# ==================== Content Generation ====================

@router.post(
    "/runs/{run_id}/generate",
    response_model=GenerateContentResponse,
    summary="Generate content from selected sources",
    description="""
    Generate content STRICTLY from selected sources.
    
    GUARANTEES:
    - Content uses ONLY information from selected sources
    - Every factual claim is cited with [Source X] markers
    - No information is fabricated or inferred
    - If something can't be sourced, it won't be included
    """
)
async def generate_content(
    run_id: str,
    request: GenerateContentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Generate content from selected sources."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    flow = run_data["flow"]
    
    if not flow.selected_sources:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Must select sources before generating content"
        )
    
    try:
        # Get optional POV and hook
        selected_pov = run_data.get("selected_pov") if request.use_selected_pov else None
        selected_hook = run_data.get("selected_hook") if request.use_selected_hook else None
        
        # Generate content
        run_data["status"] = ResearchRunStatus.GENERATING
        
        content = flow.generate_content(
            selected_pov=selected_pov,
            selected_hook=selected_hook,
        )
        
        # Format response
        content_response = GeneratedContentResponse(
            run_id=run_id,
            content=content.content,
            formatted_content=flow.format_citations_for_display(content),
            target_word_count=flow.target_word_count,
            word_count=content.word_count,
            sources_cited=content.sources_used,
            citations=[
                CitationResponse(
                    marker=c["marker"],
                    source_id=c["source_id"],
                    url=c["url"],
                    title=c["title"],
                )
                for c in content.citations
            ],
            uncited_claims=content.uncited_claims,
            generated_at=datetime.utcnow(),
        )
        
        run_data["content"] = content_response
        run_data["status"] = ResearchRunStatus.COMPLETED
        run_data["completed_at"] = datetime.utcnow()
        
        warnings = None
        if content.uncited_claims:
            warnings = {
                "uncited_claims": content.uncited_claims,
                "message": "Some claims could not be traced to sources. Review and verify."
            }
        
        return GenerateContentResponse(
            run_id=run_id,
            status=ResearchRunStatus.COMPLETED,
            content=content_response,
            message="Content generated successfully from selected sources.",
            warnings=warnings,
        )
        
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        run_data["status"] = ResearchRunStatus.FAILED
        run_data["error"] = str(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Section Regeneration ====================

class RegenerateSectionRequest(BaseModel):
    """Request to regenerate a section of content."""
    original_text: str = Field(..., description="The text to be regenerated", min_length=10)
    feedback: str = Field(..., description="What should be improved", min_length=3)
    full_content: str = Field(..., description="The full content for context")

class RegenerateSectionResponse(BaseModel):
    """Response with regenerated text."""
    regenerated_text: str
    original_text: str
    full_content: Optional[str] = None  # Complete content with replacement applied (when match found)


@router.post(
    "/runs/{run_id}/regenerate-section",
    response_model=RegenerateSectionResponse,
    summary="Regenerate a section of content",
    description="""
    Regenerate a specific section of the content based on user feedback.
    
    The LLM will:
    - Keep the context and flow consistent with surrounding content
    - Apply the user's feedback to improve the section
    - Maintain citations where applicable
    """
)
async def regenerate_section(
    run_id: str,
    request: RegenerateSectionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Regenerate a section of content based on feedback."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    flow = run_data["flow"]
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        
        # Build context from selected sources
        source_context = ""
        if flow.selected_sources:
            source_context = "\n".join([
                f"[Source {i+1}]: {s.title} - {s.snippet[:200]}"
                for i, s in enumerate(flow.selected_sources.sources[:5])
            ])
        
        # Find surrounding context
        full_content = request.full_content
        original_pos = full_content.find(request.original_text)
        
        # Get ~200 chars before and after for context
        context_before = full_content[max(0, original_pos-200):original_pos] if original_pos > 0 else ""
        context_after = full_content[original_pos+len(request.original_text):original_pos+len(request.original_text)+200] if original_pos >= 0 else ""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are rewriting a specific section of an article based on user feedback.

CRITICAL RULES:
1. ONLY rewrite the specific text provided - do not add surrounding content
2. Keep the same general meaning and information
3. Apply the user's feedback to improve the text
4. Maintain any citation markers like [Source X] if present
5. Keep the tone and style consistent with the surrounding content
6. Return ONLY the rewritten text, nothing else

Available sources for reference:
{source_context if source_context else "No specific sources available"}"""
                },
                {
                    "role": "user",
                    "content": f"""CONTEXT BEFORE:
...{context_before}

TEXT TO REWRITE:
{request.original_text}

CONTEXT AFTER:
{context_after}...

USER FEEDBACK: {request.feedback}

Please rewrite the TEXT TO REWRITE section based on the feedback. Return ONLY the rewritten text."""
                }
            ],
            temperature=0.7,
            max_tokens=1000,
        )
        
        regenerated = response.choices[0].message.content.strip()
        
        # Clean up any quotes or extra formatting the model might add
        if regenerated.startswith('"') and regenerated.endswith('"'):
            regenerated = regenerated[1:-1]
        if regenerated.startswith("'") and regenerated.endswith("'"):
            regenerated = regenerated[1:-1]
        
        logger.info(f"Regenerated section: {len(request.original_text)} chars -> {len(regenerated)} chars")
        
        return RegenerateSectionResponse(
            regenerated_text=regenerated,
            original_text=request.original_text,
        )
        
    except Exception as e:
        logger.error(f"Section regeneration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== Utility Endpoints ====================

@router.get(
    "/runs",
    response_model=ResearchRunListResponse,
    summary="List research runs",
    description="Get paginated list of research runs for the current user."
)
async def list_research_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[ResearchRunStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:read"))
):
    """List research runs."""
    # Filter runs for this customer
    runs = [
        run_data for run_id, run_data in _flow_instances.items()
        if run_data["customer_id"] == current_user.customer_id
        and (status_filter is None or run_data["status"] == status_filter)
    ]
    
    # Sort by created_at descending
    runs.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Paginate
    total = len(runs)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_runs = runs[start:end]
    
    # Convert to response
    items = []
    for run_data in paginated_runs:
        flow = run_data["flow"]
        request = run_data["request"]
        
        items.append(ResearchRunResponse(
            id=0,
            run_id=flow.run_id,
            customer_id=run_data["customer_id"],
            user_id=run_data["user_id"],
            topic=request.topic,
            target_word_count=request.target_word_count,
            status=run_data["status"],
            created_at=run_data["created_at"],
            updated_at=datetime.utcnow(),
        ))
    
    return ResearchRunListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete research run",
    description="Delete a research run and its data."
)
async def delete_research_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("content_writer:write"))
):
    """Delete a research run."""
    if run_id not in _flow_instances:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_data = _flow_instances[run_id]
    
    if run_data["customer_id"] != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Run not found")
    
    del _flow_instances[run_id]
    return None
