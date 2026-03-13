"""
GEPA Optimizer API Routes

Endpoints for creating, managing, and monitoring GEPA optimization runs.
Includes SSE streaming for real-time progress updates.
"""
import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.schemas.gepa_optimizer import (
    CreateOptimizerJobRequest,
    CreateOptimizerJobResponse,
    OptimizerJobSummary,
    OptimizerJobDetail,
    OptimizerJobListResponse,
    OptimizerJobStatus,
    CandidateVariantSummary,
    CandidateVariantDetail,
    VariantListResponse,
    VariantScores,
    ComponentDiff,
    ParetoFrontierPoint,
    ParetoSnapshotSummary,
    PauseJobRequest,
    CancelJobRequest,
    TryVariantRequest,
    TryVariantResponse,
    PromoteVariantRequest,
    PromoteVariantResponse,
    PromptCreatedInfo,
    VariantEvalResultsResponse,
    EvalResultSummary,
    VariantTracesResponse,
    TraceSummary,
    VariantComparisonRequest,
    VariantComparison,
    PromotionHistoryResponse,
    PromotionHistoryItem,
    RollbackRequest,
    GEPATelemetryEvent,
    VariantStatus as VariantStatusSchema,
    MutationType as MutationTypeSchema,
    # Human feedback schemas
    SubmitFeedbackRequest,
    HumanFeedbackSummary,
    HumanFeedbackDetail,
    VariantFeedbackResponse,
    JobFeedbackResponse,
    FeedbackStatsResponse,
    FeedbackType,
    FeedbackRating,
    SeedFeedbackItem,
)
from src.core.logging import get_logger
from src.middleware.authorization import require_any_permission
from src.models import get_db
from src.models.gepa_optimizer import (
    OptimizerJobStatus as DBOptimizerJobStatus,
    VariantStatus as DBVariantStatus,
)
from src.services.gepa_optimizer_service import GEPAOptimizerService

logger = get_logger(__name__, component="api.gepa_optimizer")

router = APIRouter(prefix="/optimizers/gepa", tags=["GEPA Optimizer"])


# ============= Helper Functions =============

def _build_job_summary(job) -> OptimizerJobSummary:
    """Build OptimizerJobSummary from database model."""
    duration = None
    if job.started_at and job.completed_at:
        duration = (job.completed_at - job.started_at).total_seconds()
    
    return OptimizerJobSummary(
        id=job.id,
        job_id=job.job_id,
        name=job.name,
        description=job.description,
        status=OptimizerJobStatus(job.status.value),
        target_components=job.target_components,
        objectives=job.objectives,
        optimization_strategy=job.optimization_strategy or "genetic",
        population_size=job.population_size,
        max_iterations=job.max_iterations,
        current_iteration=job.current_iteration,
        total_evals_used=job.total_evals_used,
        eval_budget=job.eval_budget,
        best_quality_score=job.best_quality_score,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=duration,
        created_at=job.created_at,
    )


def _build_job_detail(job, service: GEPAOptimizerService) -> OptimizerJobDetail:
    """Build OptimizerJobDetail from database model."""
    summary = _build_job_summary(job)
    
    # Get current frontier
    variants, _ = service.get_variants(job.id, pareto_rank=0, limit=20)
    current_frontier = [
        ParetoFrontierPoint(
            variant_id=v.variant_id,
            scores={
                "quality": v.quality_score or 0,
                "groundedness": v.groundedness_score or 0,
                "citation_accuracy": v.citation_accuracy or 0,
                "latency": v.avg_latency_ms or 0,
                "cost": v.avg_cost or 0,
            }
        )
        for v in variants
    ]
    
    # Get best variant
    best_variant = None
    if job.best_variant_id:
        best = next((v for v in variants if v.id == job.best_variant_id), None)
        if best:
            best_variant = _build_variant_summary(best)
    
    # Get frontier history
    snapshots = service.get_pareto_snapshots(job.id, limit=20)
    frontier_history = [
        ParetoSnapshotSummary(
            iteration=s.iteration,
            frontier_count=s.frontier_count,
            frontier_variant_ids=s.frontier_variant_ids,
            hypervolume=s.hypervolume,
            diversity_score=s.diversity_score,
            frontier_stats=s.frontier_stats,
            created_at=s.created_at,
        )
        for s in snapshots
    ]
    
    return OptimizerJobDetail(
        **summary.model_dump(),
        baseline_components=job.baseline_components,
        objective_weights=job.objective_weights,
        mutation_rate=job.mutation_rate,
        crossover_rate=job.crossover_rate,
        elite_count=job.elite_count,
        agent_config_id=job.agent_config_id,
        eval_suite_id=job.eval_suite_id,
        error_message=job.error_message,
        celery_task_id=job.celery_task_id,
        current_frontier=current_frontier,
        best_variant=best_variant,
        frontier_history=frontier_history,
    )


def _build_variant_summary(variant) -> CandidateVariantSummary:
    """Build CandidateVariantSummary from database model."""
    return CandidateVariantSummary(
        id=variant.id,
        variant_id=variant.variant_id,
        generation=variant.generation,
        mutation_type=MutationTypeSchema(variant.mutation_type.value) if variant.mutation_type else None,
        parent_variant_ids=variant.parent_variant_ids,
        status=VariantStatusSchema(variant.status.value),
        scores=VariantScores(
            quality_score=variant.quality_score,
            groundedness_score=variant.groundedness_score,
            citation_accuracy=variant.citation_accuracy,
            avg_latency_ms=variant.avg_latency_ms,
            avg_cost=variant.avg_cost,
        ),
        pareto_rank=variant.pareto_rank,
        crowding_distance=variant.crowding_distance,
        is_baseline=variant.is_baseline,
        is_promoted=variant.is_promoted,
        promoted_to=variant.promoted_to,
        created_at=variant.created_at,
    )


def _build_variant_detail(variant, baseline_components: dict) -> CandidateVariantDetail:
    """Build CandidateVariantDetail from database model."""
    summary = _build_variant_summary(variant)
    
    # Build component diffs
    component_diffs = []
    if variant.component_diffs:
        for comp_type, diff in variant.component_diffs.items():
            component_diffs.append(ComponentDiff(
                component_type=comp_type,
                baseline_value=baseline_components.get(comp_type, ""),
                variant_value=variant.component_values.get(comp_type, ""),
                added_lines=diff.get("added"),
                removed_lines=diff.get("removed"),
                similarity_score=diff.get("similarity_score"),
            ))
    
    # Count eval results
    pass_count = fail_count = error_count = 0
    if variant.evaluation_results:
        for r in variant.evaluation_results:
            if r.verdict == "pass":
                pass_count += 1
            elif r.verdict == "fail":
                fail_count += 1
            else:
                error_count += 1
    
    return CandidateVariantDetail(
        **summary.model_dump(),
        component_values=variant.component_values,
        component_diffs=component_diffs if component_diffs else None,
        eval_results_count=len(variant.evaluation_results) if variant.evaluation_results else 0,
        pass_count=pass_count,
        fail_count=fail_count,
        error_count=error_count,
    )


# ============= Job Management Endpoints =============

@router.post("", response_model=CreateOptimizerJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_optimizer_job(
    request: CreateOptimizerJobRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Create and start a new GEPA optimization job.
    
    The optimization runs asynchronously via Celery. Use the returned SSE URL
    to stream progress updates.
    """
    service = GEPAOptimizerService(db)

    # Resolve/prefill components from Prompt Management if requested
    domain = request.domain
    use_prompt_management = request.use_prompt_management and bool(domain)

    managed_prompts: dict[str, str] = {}
    if use_prompt_management and domain:
        try:
            from src.services.prompt_management_service import PromptManagementService
            pm_service = PromptManagementService(db)
            managed_prompts = pm_service.get_rag_prompts(current_user.customer_id, domain)
        except Exception as e:
            logger.error("gepa_prefill_prompts_failed", domain=domain, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to load prompts from Prompt Management")

    # Map GEPA component types -> Prompt Management prompt keys
    gepa_component_to_pm_key: dict[str, str] = {
        "system_prompt": "system",
        "query_rewrite_prompt": "query_rewrite",
        "answer_synthesis_prompt": "synthesis",
        "retrieval_instructions": "retrieval",
    }

    # Convert components to expected format (with optional prefill)
    components: list[dict[str, str]] = []

    if not request.components and use_prompt_management and domain:
        # Default to the common RAG prompt set if the user didn't specify components
        default_component_order = [
            "system_prompt",
            "query_rewrite_prompt",
            "answer_synthesis_prompt",
        ]
        for component_type in default_component_order:
            pm_key = gepa_component_to_pm_key.get(component_type)
            if not pm_key:
                continue
            value = (managed_prompts.get(pm_key) or "").strip()
            if value:
                components.append({"component_type": component_type, "initial_value": value})
    else:
        for c in request.components:
            component_type = c.component_type.value
            initial_value = (c.initial_value or "").strip()

            if not initial_value and use_prompt_management and domain:
                pm_key = gepa_component_to_pm_key.get(component_type)
                if pm_key:
                    initial_value = (managed_prompts.get(pm_key) or "").strip()

            if not initial_value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing initial_value for component '{component_type}'. Provide it explicitly or set domain+use_prompt_management to prefill.",
                )

            components.append({"component_type": component_type, "initial_value": initial_value})

    if not components:
        raise HTTPException(
            status_code=400,
            detail="No components resolved for optimization. Provide components or set domain+use_prompt_management to prefill from Prompt Management.",
        )
    
    # Convert objectives to expected format
    objectives = [
        {
            "name": o.name.value,
            "weight": o.weight,
            "direction": o.direction,
        }
        for o in request.objectives
    ]
    
    # Create the job
    job = service.create_optimizer_job(
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        name=request.name,
        description=request.description,
        domain=domain,
        components=components,
        objectives=objectives,
        agent_config_id=request.agent_config_id,
        eval_suite_id=request.eval_suite_id,
        population_size=request.population_size,
        max_iterations=request.max_iterations,
        eval_budget=request.eval_budget,
        mutation_rate=request.mutation_rate,
        crossover_rate=request.crossover_rate,
        elite_count=request.elite_count,
        optimization_strategy=request.optimization_strategy.value,
    )

    # Attach seed feedback (e.g., from prod) to baseline variant so it guides this run
    seed_feedback_payload = None
    if request.seed_feedback:
        seed_feedback_payload = [f.model_dump() for f in request.seed_feedback]
    elif request.import_prompt_feedback and domain:
        try:
            from src.services.prompt_management_service import PromptManagementService
            pm = PromptManagementService(db)
            seed_feedback_payload = pm.export_seed_feedback_for_gepa(
                customer_id=current_user.customer_id,
                domain=domain,
                environment=request.prompt_feedback_environment,
                limit=request.prompt_feedback_limit,
            )
        except Exception as e:
            logger.error("gepa_prompt_feedback_import_failed", job_id=job.job_id, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to import feedback from Prompt Management")

    if seed_feedback_payload:
        try:
            created = service.seed_feedback_on_baseline(
                job_id=job.id,
                user_id=current_user.user_id,
                seed_feedback=seed_feedback_payload,
            )
            logger.info("gepa_seed_feedback_ingested", job_id=job.job_id, count=created)
        except Exception as e:
            logger.error("gepa_seed_feedback_failed", job_id=job.job_id, error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to attach seed feedback to job baseline")
    
    # Trigger async execution via Celery
    should_use_celery = False
    try:
        from src.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=1.0)
        pong = inspector.ping() or {}
        should_use_celery = len(pong) > 0
    except Exception as e:
        logger.warning("celery_ping_failed", error=str(e))
    
    if should_use_celery:
        from src.tasks.gepa_optimizer_tasks import run_gepa_optimization
        run_gepa_optimization.delay(job.id)
        logger.info("gepa_job_dispatched_to_celery", job_id=job.job_id)
    else:
        # Run in background task (dev mode fallback)
        logger.warning("no_celery_workers_running_in_process", job_id=job.job_id)
        
        import asyncio
        from src.models import database
        
        async def run_in_background():
            if database.SessionLocal is None:
                database.init_database()
            session = database.SessionLocal()
            try:
                bg_service = GEPAOptimizerService(session)
                from src.models.gepa_optimizer import OptimizerJob
                bg_job = session.query(OptimizerJob).filter(OptimizerJob.id == job.id).first()
                if bg_job:
                    await bg_service.run_optimization(bg_job)
            except Exception as e:
                logger.error("background_gepa_failed", job_id=job.job_id, error=str(e), exc_info=True)
            finally:
                session.close()
        
        asyncio.create_task(run_in_background())
    
    logger.info(
        "gepa_job_created",
        job_id=job.job_id,
        user_id=current_user.user_id,
        components=request.components,
    )
    
    return CreateOptimizerJobResponse(
        job_id=job.job_id,
        status=OptimizerJobStatus(job.status.value),
        message="Optimization job started. Use SSE URL to stream progress.",
        sse_url=f"/api/v1/optimizers/gepa/{job.job_id}/stream",
    )


@router.get("", response_model=OptimizerJobListResponse)
async def list_optimizer_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    domain: Optional[str] = Query(None, description="Filter by workspace/domain name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """List GEPA optimization jobs for the current customer."""
    service = GEPAOptimizerService(db)
    
    status_filter = None
    if status:
        try:
            status_filter = DBOptimizerJobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    offset = (page - 1) * page_size
    jobs, total = service.list_jobs(
        customer_id=current_user.customer_id,
        status=status_filter,
        domain=domain,
        limit=page_size,
        offset=offset,
    )
    
    return OptimizerJobListResponse(
        jobs=[_build_job_summary(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=OptimizerJobDetail)
async def get_optimizer_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get details of a GEPA optimization job."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return _build_job_detail(job, service)


@router.post("/{job_id}/pause")
async def pause_optimizer_job(
    job_id: str,
    request: PauseJobRequest = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Pause a running optimization job."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    reason = request.reason if request else None
    
    try:
        job = service.pause_job(job_id, reason)
        return {"status": "paused", "job_id": job_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/resume")
async def resume_optimizer_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Resume a paused optimization job."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Resume via Celery task
        from src.tasks.gepa_optimizer_tasks import resume_gepa_optimization
        resume_gepa_optimization.delay(job.id)
        
        return {"status": "resuming", "job_id": job_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/cancel")
async def cancel_optimizer_job(
    job_id: str,
    request: CancelJobRequest = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Cancel an optimization job."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    reason = request.reason if request else None
    
    try:
        job = service.cancel_job(job_id, reason)
        return {"status": "cancelled", "job_id": job_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{job_id}")
async def delete_optimizer_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Delete an optimization job and all associated data."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    status_value = job.status.value if hasattr(job.status, "value") else str(job.status)
    if status_value in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a running job. Cancel it first.",
        )
    
    db.delete(job)
    db.commit()
    
    return {"status": "deleted", "job_id": job_id}


# ============= SSE Streaming =============

@router.get("/{job_id}/stream")
async def stream_optimization_progress(
    job_id: str,
    token: str = Query(..., description="Auth token for SSE"),
    db: Session = Depends(get_db),
):
    """
    Stream optimization progress via Server-Sent Events.
    
    Connect to this endpoint to receive real-time updates as the optimization runs.
    """
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    # Token validation would go here in production
    
    async def event_generator():
        """Generate SSE events."""
        last_event_id = 0
        completed_statuses = {
            DBOptimizerJobStatus.COMPLETED,
            DBOptimizerJobStatus.FAILED,
            DBOptimizerJobStatus.CANCELLED,
        }
        
        while True:
            # Refresh job status
            db.refresh(job)
            
            # Get new telemetry events
            events = service.get_telemetry_events(job.id, after_id=last_event_id)
            
            for event in events:
                event_data = json.dumps({
                    "event_type": event.event_type,
                    "stage_name": event.stage_name,
                    "message": event.message,
                    "progress_percentage": event.progress_percentage,
                    "data": event.data,
                    "timestamp": event.created_at.isoformat() if event.created_at else None,
                })
                yield f"data: {event_data}\n\n"
                last_event_id = event.id
            
            # Check if optimization is complete
            if job.status in completed_statuses:
                final_data = json.dumps({
                    "event_type": "final",
                    "status": job.status.value,
                    "best_quality_score": job.best_quality_score,
                    "total_iterations": job.current_iteration,
                    "total_evals_used": job.total_evals_used,
                })
                yield f"data: {final_data}\n\n"
                break
            
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============= Variant Endpoints =============

@router.get("/{job_id}/variants", response_model=VariantListResponse)
async def list_variants(
    job_id: str,
    generation: Optional[int] = Query(None, description="Filter by generation"),
    pareto_rank: Optional[int] = Query(None, description="Filter by Pareto rank (0 = frontier)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """List candidate variants for an optimization job."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    status_filter = None
    if status:
        try:
            status_filter = DBVariantStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    offset = (page - 1) * page_size
    variants, total = service.get_variants(
        job_id=job.id,
        generation=generation,
        pareto_rank=pareto_rank,
        status=status_filter,
        limit=page_size,
        offset=offset,
    )
    
    # Count aggregates
    frontier_count = sum(1 for v in variants if v.pareto_rank == 0)
    evaluated_count = sum(1 for v in variants if v.status == DBVariantStatus.EVALUATED)
    pending_count = sum(1 for v in variants if v.status == DBVariantStatus.PENDING)
    
    return VariantListResponse(
        variants=[_build_variant_summary(v) for v in variants],
        total=total,
        page=page,
        page_size=page_size,
        frontier_count=frontier_count,
        evaluated_count=evaluated_count,
        pending_count=pending_count,
    )


@router.get("/{job_id}/variants/{variant_id}", response_model=CandidateVariantDetail)
async def get_variant(
    job_id: str,
    variant_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get details of a specific variant."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    variant = service.get_variant(job.id, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    return _build_variant_detail(variant, job.baseline_components)


@router.get("/{job_id}/variants/{variant_id}/results", response_model=VariantEvalResultsResponse)
async def get_variant_eval_results(
    job_id: str,
    variant_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get evaluation results for a variant."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    variant = service.get_variant(job.id, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    offset = (page - 1) * page_size
    results, total = service.get_variant_eval_results(variant.id, limit=page_size, offset=offset)
    
    pass_count = sum(1 for r in results if r.verdict == "pass")
    fail_count = sum(1 for r in results if r.verdict == "fail")
    error_count = sum(1 for r in results if r.verdict not in ("pass", "fail"))
    
    return VariantEvalResultsResponse(
        variant_id=variant_id,
        results=[
            EvalResultSummary(
                id=r.id,
                eval_case_id=r.eval_case_id,
                question=r.question,
                verdict=r.verdict,
                factual_correctness=r.factual_correctness,
                faithfulness=r.faithfulness,
                citation_compliance=r.citation_compliance,
                latency_ms=r.latency_ms,
            )
            for r in results
        ],
        total=total,
        pass_count=pass_count,
        fail_count=fail_count,
        error_count=error_count,
        aggregate_scores=VariantScores(
            quality_score=variant.quality_score,
            groundedness_score=variant.groundedness_score,
            citation_accuracy=variant.citation_accuracy,
            avg_latency_ms=variant.avg_latency_ms,
            avg_cost=variant.avg_cost,
        ),
    )


@router.get("/{job_id}/variants/{variant_id}/traces", response_model=VariantTracesResponse)
async def get_variant_traces(
    job_id: str,
    variant_id: str,
    trace_type: Optional[str] = Query(None, description="Filter by trace type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get execution traces for a variant."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    variant = service.get_variant(job.id, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    offset = (page - 1) * page_size
    traces, total = service.get_variant_traces(variant.id, trace_type=trace_type, limit=page_size, offset=offset)
    
    return VariantTracesResponse(
        variant_id=variant_id,
        traces=[
            TraceSummary(
                id=t.id,
                trace_id=t.trace_id,
                trace_type=t.trace_type,
                eval_case_id=t.eval_case_id,
                total_latency_ms=t.total_latency_ms,
                total_tokens=t.total_tokens,
                step_count=t.step_count,
                error_count=t.error_count,
                created_at=t.created_at,
            )
            for t in traces
        ],
        total=total,
    )


# ============= Try and Promote Endpoints =============

@router.post("/{job_id}/variants/{variant_id}/try", response_model=TryVariantResponse)
async def try_variant(
    job_id: str,
    variant_id: str,
    request: TryVariantRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Temporarily try a variant in a chat session.
    
    This allows testing a variant before promoting it.
    """
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    variant = service.get_variant(job.id, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    # TODO: Implement actual chat session integration
    # For now, return placeholder response
    
    return TryVariantResponse(
        session_id=request.session_id or f"try_{variant_id}",
        variant_id=variant_id,
        query=request.query,
        response="[Trial response with variant prompts - TODO: integrate with chat]",
        metrics={"placeholder": True},
        comparison={
            "baseline_quality": 0.8,
            "variant_quality": variant.quality_score or 0.85,
        },
    )


@router.post("/{job_id}/variants/{variant_id}/promote", response_model=PromoteVariantResponse)
async def promote_variant(
    job_id: str,
    variant_id: str,
    request: PromoteVariantRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Promote a variant to an environment via Prompt Management.
    
    This creates new prompt versions in the Prompt Management system,
    optionally auto-activating them for immediate use by the RAG pipeline.
    """
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        promotion = service.promote_variant(
            job_id=job.id,
            variant_id=variant_id,
            environment=request.environment,
            user_id=current_user.user_id,
            domain=request.domain,
            auto_activate=request.auto_activate,
            notes=request.notes,
            create_backup=request.create_backup,
        )
        
        # Extract prompts created info from rollback_info
        prompts_created = None
        domain = request.domain
        if promotion.rollback_info:
            prompts_created = [
                {
                    "component": p["component"],
                    "prompt_id": p["prompt_id"],
                    "version": p["version"],
                    "prompt_type": p["prompt_type"],
                }
                for p in promotion.rollback_info.get("prompts_created", [])
            ]
            domain = promotion.rollback_info.get("domain", domain)
        
        return PromoteVariantResponse(
            success=True,
            variant_id=variant_id,
            environment=request.environment,
            domain=domain,
            promotion_id=promotion.id,
            prompts_created=prompts_created,
            auto_activated=request.auto_activate,
            message=f"Variant promoted to {request.environment}. {len(prompts_created) if prompts_created else 0} prompt(s) created.",
            backup_created=request.create_backup,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============= Pareto Frontier Endpoints =============

@router.get("/{job_id}/frontier", response_model=list[ParetoFrontierPoint])
async def get_current_frontier(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get the current Pareto frontier for an optimization job."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    variants, _ = service.get_variants(job.id, pareto_rank=0, limit=50)
    
    return [
        ParetoFrontierPoint(
            variant_id=v.variant_id,
            scores={
                "quality": v.quality_score or 0,
                "groundedness": v.groundedness_score or 0,
                "citation_accuracy": v.citation_accuracy or 0,
                "latency": v.avg_latency_ms or 0,
                "cost": v.avg_cost or 0,
            }
        )
        for v in variants
    ]


@router.get("/{job_id}/frontier/history", response_model=list[ParetoSnapshotSummary])
async def get_frontier_history(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get the history of Pareto frontiers across iterations."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    snapshots = service.get_pareto_snapshots(job.id, limit=100)
    
    return [
        ParetoSnapshotSummary(
            iteration=s.iteration,
            frontier_count=s.frontier_count,
            frontier_variant_ids=s.frontier_variant_ids,
            hypervolume=s.hypervolume,
            diversity_score=s.diversity_score,
            frontier_stats=s.frontier_stats,
            created_at=s.created_at,
        )
        for s in snapshots
    ]


# ============= Comparison Endpoint =============

@router.post("/{job_id}/compare", response_model=VariantComparison)
async def compare_variants(
    job_id: str,
    request: VariantComparisonRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Compare multiple variants side-by-side."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get requested variants
    variants = []
    for vid in request.variant_ids:
        v = service.get_variant(job.id, vid)
        if v:
            variants.append(_build_variant_detail(v, job.baseline_components))
    
    if len(variants) < 2:
        raise HTTPException(status_code=400, detail="At least 2 valid variants required for comparison")
    
    # Build score comparison
    score_metrics = ["quality_score", "groundedness_score", "citation_accuracy", "avg_latency_ms", "avg_cost"]
    score_comparison = {}
    for metric in score_metrics:
        score_comparison[metric] = [
            getattr(v.scores, metric) or 0 for v in variants
        ]
    
    # Find best for each metric
    best_for = {}
    for metric in score_metrics:
        scores = score_comparison[metric]
        # Latency and cost: lower is better
        if metric in ["avg_latency_ms", "avg_cost"]:
            best_idx = scores.index(min(scores))
        else:
            best_idx = scores.index(max(scores))
        best_for[metric] = variants[best_idx].variant_id
    
    # Find Pareto optimal
    pareto_optimal = [v.variant_id for v in variants if v.pareto_rank == 0]
    
    return VariantComparison(
        variants=variants,
        score_comparison=score_comparison,
        best_for=best_for,
        pareto_optimal=pareto_optimal,
    )


# ============= Human Feedback Endpoints =============

@router.post("/{job_id}/variants/{variant_id}/feedback", status_code=201)
async def submit_feedback(
    job_id: str,
    variant_id: str,
    request: SubmitFeedbackRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Submit human feedback on a variant.
    
    Supports two types of feedback:
    - per_query: Feedback on a specific test case response
    - overall: General feedback on the variant's performance/style
    
    This feedback will be used to:
    1. Adjust fitness scores (feedback bonus)
    2. Guide reflection-based mutations
    3. Influence selection pressure in future generations
    """
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    variant = service.get_variant(job.id, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    feedback = service.submit_feedback(
        job_id=job.id,
        variant_id=variant.id,
        user_id=current_user.user_id,
        feedback_type=request.feedback_type.value,
        rating=request.rating.value,
        eval_result_id=request.eval_result_id,
        query_text=request.query_text,
        response_text=request.response_text,
        comment=request.comment,
        tags=request.tags,
        improvement_suggestions=request.improvement_suggestions,
        target_components=[c.value for c in request.target_components] if request.target_components else None,
    )
    
    return {
        "id": feedback.id,
        "message": "Feedback submitted successfully",
        "incorporated": feedback.incorporated,
    }


@router.get("/{job_id}/variants/{variant_id}/feedback", response_model=VariantFeedbackResponse)
async def get_variant_feedback(
    job_id: str,
    variant_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get all feedback for a specific variant."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    variant = service.get_variant(job.id, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    feedback_list = service.get_variant_feedback(variant.id)
    
    # Calculate stats
    total = len(feedback_list)
    avg_rating = None
    rating_dist = {
        "strongly_positive": 0,
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "strongly_negative": 0,
    }
    
    if total > 0:
        avg_rating = sum(f.rating_numeric for f in feedback_list) / total
        for f in feedback_list:
            rating_dist[f.rating.value] += 1
    
    return VariantFeedbackResponse(
        variant_id=variant_id,
        feedback=[
            HumanFeedbackSummary(
                id=f.id,
                variant_id=f.variant_id,
                feedback_type=FeedbackType(f.feedback_type.value),
                rating=FeedbackRating(f.rating.value),
                rating_numeric=f.rating_numeric,
                comment=f.comment,
                tags=f.tags,
                target_components=f.target_components,
                user_id=f.user_id,
                incorporated=f.incorporated,
                created_at=f.created_at,
            )
            for f in feedback_list
        ],
        total=total,
        average_rating=avg_rating,
        rating_distribution=rating_dist,
    )


@router.get("/{job_id}/feedback", response_model=JobFeedbackResponse)
async def get_job_feedback(
    job_id: str,
    incorporated: Optional[bool] = Query(None, description="Filter by incorporation status"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get all feedback for a job, optionally filtered."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    feedback_list = service.get_job_feedback(job.id, incorporated=incorporated)
    
    # Count by variant
    by_variant = {}
    unincorporated = 0
    for f in feedback_list:
        vid = str(f.variant_id)
        by_variant[vid] = by_variant.get(vid, 0) + 1
        if not f.incorporated:
            unincorporated += 1
    
    return JobFeedbackResponse(
        job_id=job_id,
        feedback=[
            HumanFeedbackDetail(
                id=f.id,
                job_id=f.job_id,
                variant_id=f.variant_id,
                feedback_type=FeedbackType(f.feedback_type.value),
                rating=FeedbackRating(f.rating.value),
                rating_numeric=f.rating_numeric,
                eval_result_id=f.eval_result_id,
                query_text=f.query_text,
                response_text=f.response_text,
                comment=f.comment,
                tags=f.tags,
                improvement_suggestions=f.improvement_suggestions,
                target_components=f.target_components,
                user_id=f.user_id,
                incorporated=f.incorporated,
                incorporated_at=f.incorporated_at,
                incorporated_in_variant_id=f.incorporated_in_variant_id,
                created_at=f.created_at,
            )
            for f in feedback_list
        ],
        total=len(feedback_list),
        unincorporated_count=unincorporated,
        by_variant=by_variant,
    )


@router.get("/{job_id}/feedback/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get aggregated statistics about feedback for a job."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    stats = service.get_feedback_stats(job.id)
    
    return FeedbackStatsResponse(
        job_id=job_id,
        **stats
    )


@router.delete("/{job_id}/feedback/{feedback_id}", status_code=204)
async def delete_feedback(
    job_id: str,
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """Delete a feedback entry (only by the user who created it or admin)."""
    service = GEPAOptimizerService(db)
    job = service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    
    if job.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    feedback = service.get_feedback_by_id(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Only creator or admin can delete
    is_admin = "platform:admin" in current_user.permissions
    if feedback.user_id != current_user.user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Only feedback creator or admin can delete")
    
    if feedback.incorporated:
        raise HTTPException(status_code=400, detail="Cannot delete feedback that has been incorporated")
    
    service.delete_feedback(feedback_id)
    return None
