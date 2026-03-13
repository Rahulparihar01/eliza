"""
RAG Evaluation API Routes

Endpoints for running and monitoring RAG evaluations with Langfuse tracing.
"""
import asyncio
import json
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from sqlalchemy.orm import Session

from src.api.schemas.rag_eval import (
    StartEvalRunRequest,
    StartEvalRunRequestV2,
    StartEvalRunResponse,
    EvalRunResponse,
    EvalRunSummary,
    EvalRunListResponse,
    EvalResultItem,
    EvalMetrics,
    CancelEvalRunRequest,
    QuestionsPreviewResponse,
    QuestionWithReference,
    FailureAnalysis,
    FailureAnalysisResponse,
    EvalRunStatus as EvalRunStatusSchema,
    EvalVerdict as EvalVerdictSchema,
    CitationValidationRequest,
    CitationValidationResponse,
    CitationValidationResult,
    # Eval Set schemas
    EvalSetSummary,
    EvalSetDetail,
    EvalSetListResponse,
    CreateEvalSetRequest,
    UpdateEvalSetRequest,
    EvalSetQuestionsResponse,
    EvalSetType as EvalSetTypeSchema,
    EvalSetCategory as EvalSetCategorySchema,
    EvalSource as EvalSourceSchema,
)
from src.core.config import get_settings
from src.core.logging import get_logger
from src.middleware.authorization import require_permission, require_any_permission
from src.models import get_db
from src.models.rag_eval import EvalRunStatus, EvalVerdict, EvalSource
from src.models.eval_set import EvalSet, EvalSetType, EvalSetCategory
from src.services.rag_eval_service import RAGEvalService
from src.services.eval_set_service import EvalSetService, EvalSetValidationError
from src.services.citation_validation_service import CitationValidationService
from src.services.fasb_service import get_fasb_service

logger = get_logger(__name__, component="api.rag_eval")

router = APIRouter(prefix="/rag-eval", tags=["RAG Evaluation"])


# ============= Helper Functions =============

import math

def _safe_float(value) -> float | None:
    """Convert NaN to None for JSON serialization."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _sanitize_metrics_dict(obj):
    """Recursively sanitize NaN values in metrics dict for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize_metrics_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_metrics_dict(v) for v in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def _build_eval_summary(eval_run) -> EvalRunSummary:
    """Build EvalRunSummary from database model."""
    metrics = None
    if eval_run.total_questions:
        metrics = EvalMetrics(
            total_questions=eval_run.total_questions,
            pass_count=eval_run.pass_count or 0,
            fail_count=eval_run.fail_count or 0,
            error_count=eval_run.error_count or 0,
            pass_rate=_safe_float(eval_run.pass_rate) or 0.0,
            factual_correctness_mean=_safe_float(eval_run.factual_correctness_mean),
            faithfulness_mean=_safe_float(eval_run.faithfulness_mean),
            context_precision_mean=_safe_float(eval_run.context_precision_mean),
            context_recall_mean=_safe_float(eval_run.context_recall_mean),
            citation_compliance_mean=_safe_float(eval_run.citation_compliance_mean),
            citation_page_accuracy_mean=_safe_float(eval_run.citation_page_accuracy_mean),
        )
    
    duration = None
    if eval_run.started_at and eval_run.completed_at:
        duration = (eval_run.completed_at - eval_run.started_at).total_seconds()
    
    return EvalRunSummary(
        id=eval_run.id,
        run_id=eval_run.run_id,
        domain=eval_run.domain,
        eval_type=getattr(eval_run, "eval_type", None),
        status=EvalRunStatusSchema(eval_run.status.value),
        sample_size=eval_run.sample_size,
        difficulty_counts=eval_run.difficulty_counts,
        eval_source=eval_run.eval_source.value if eval_run.eval_source else None,
        eval_set_id=eval_run.eval_set_id,
        eval_set_name=eval_run.eval_set_name,
        started_at=eval_run.started_at,
        completed_at=eval_run.completed_at,
        duration_seconds=duration,
        metrics=metrics,
        metrics_by_difficulty=_sanitize_metrics_dict(eval_run.metrics_by_difficulty),
        chat_model=eval_run.chat_model,
        embed_model=eval_run.embed_model,
        judge_model=eval_run.judge_model,
        prompt_template_snapshot=eval_run.prompt_template_snapshot,
        created_at=eval_run.created_at,
    )


def _build_result_item(result) -> EvalResultItem:
    """Build EvalResultItem from database model."""
    return EvalResultItem(
        id=result.id,
        eval_id=result.eval_id,
        question_index=result.question_index,
        question=result.question,
        expected_answer=result.expected_answer,
        difficulty=result.difficulty,
        model_response=result.model_response,
        verdict=EvalVerdictSchema(result.verdict.value) if result.verdict else None,
        verdict_reason=result.verdict_reason,
        citations=result.citations,
        citation_compliance=result.citation_compliance,
        citation_page_validations=result.citation_page_validations,
        citation_page_score=_safe_float(result.citation_page_score),
        contexts_count=result.contexts_count,
        factual_correctness=_safe_float(result.factual_correctness),
        faithfulness=_safe_float(result.faithfulness),
        context_precision=_safe_float(result.context_precision),
        context_recall=_safe_float(result.context_recall),
        processing_time_ms=result.processing_time_ms,
        created_at=result.created_at,
    )


def _strip_sources_from_summary(summary: str) -> str:
    if not summary:
        return ""
    sources_match = re.search(r"\n\nSources:\n[\s\S]*?$", summary)
    return summary[: sources_match.start()] if sources_match else summary


# ============= Endpoints =============

@router.get("/questions/preview", response_model=QuestionsPreviewResponse)
async def preview_questions(
    sample_count: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """
    Preview available evaluation questions.
    
    Returns a summary of available questions by difficulty and sample questions.
    """
    service = RAGEvalService(db)
    preview = service.get_questions_preview(sample_count)
    
    return QuestionsPreviewResponse(
        total_available=preview["total_available"],
        by_difficulty=preview["by_difficulty"],
        sample_questions=[
            QuestionWithReference(
                eval_id=q["eval_id"],
                question=q["question"],
                reference_answer=q["expected_answer"],
                difficulty=q["difficulty"],
                gold_chunk_ids=q.get("gold_chunk_ids"),
            )
            for q in preview["sample_questions"]
        ],
    )


@router.post("/runs", response_model=StartEvalRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_eval_run(
    request: StartEvalRunRequest,
    sync: bool = Query(False, description="Run synchronously (for testing)"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Start a new RAG evaluation run.
    
    The evaluation runs asynchronously via Celery. Use the returned SSE URL
    to stream progress updates. Set sync=true to run synchronously (for testing).
    """
    service = RAGEvalService(db)
    
    # Build difficulty counts from request
    difficulty_counts = None
    if request.difficulty_counts:
        difficulty_counts = {}
        if request.difficulty_counts.easy is not None:
            difficulty_counts["easy"] = request.difficulty_counts.easy
        if request.difficulty_counts.medium is not None:
            difficulty_counts["medium"] = request.difficulty_counts.medium
        if request.difficulty_counts.hard is not None:
            difficulty_counts["hard"] = request.difficulty_counts.hard
        
        if not difficulty_counts:
            difficulty_counts = None
    
    # Determine sample size
    sample_size = request.sample_size
    if not sample_size and not difficulty_counts:
        # Use default stratified sampling
        settings = get_settings()
        difficulty_counts = {"easy": 5, "medium": 5, "hard": 5}
    
    # Create the evaluation run
    eval_run = service.create_eval_run(
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        domain=request.domain,
        sample_size=sample_size,
        difficulty_counts=difficulty_counts,
        seed=request.seed,
        concurrency=request.concurrency,
        validate_citations=request.validate_citations,
    )
    
    if sync:
        # Run synchronously for testing (blocks until complete)
        logger.info("Running evaluation synchronously", run_id=eval_run.run_id)
        try:
            eval_run = await service.run_evaluation(eval_run)
        except Exception as e:
            logger.error("Sync evaluation failed", error=str(e), run_id=eval_run.run_id)
            eval_run.status = EvalRunStatus.FAILED
            db.commit()
    else:
        # Trigger async execution.
        # Prefer Celery when a worker is alive; otherwise run in-process (dev-friendly).
        should_use_celery = False
        try:
            from src.celery_app import celery_app

            inspector = celery_app.control.inspect(timeout=1.0)
            pong = inspector.ping() or {}
            should_use_celery = len(pong) > 0
        except Exception as e:
            logger.warning("celery_ping_failed", error=str(e))

        if should_use_celery:
            from src.tasks.rag_eval_tasks import run_rag_evaluation

            run_rag_evaluation.delay(eval_run.id)
            logger.info("eval_run_dispatched_to_celery", run_id=eval_run.run_id)
        else:
            logger.warning(
                "no_celery_workers_detected_running_in_process",
                run_id=eval_run.run_id,
            )

            import asyncio
            from src.models import database

            async def run_in_background():
                # Use a fresh DB session for background execution
                if database.SessionLocal is None:
                    database.init_database()
                session = database.SessionLocal()
                try:
                    bg_service = RAGEvalService(session)
                    from src.models.rag_eval import RAGEvalRun

                    bg_eval_run = (
                        session.query(RAGEvalRun)
                        .filter(RAGEvalRun.id == eval_run.id)
                        .first()
                    )
                    if bg_eval_run:
                        await bg_service.run_evaluation(bg_eval_run)
                except Exception as bg_error:
                    logger.error(
                        "background_eval_failed",
                        run_id=eval_run.run_id,
                        error=str(bg_error),
                        exc_info=True,
                    )
                finally:
                    session.close()

            asyncio.create_task(run_in_background())
    
    logger.info(
        "eval_run_started",
        run_id=eval_run.run_id,
        user_id=current_user.user_id,
        domain=request.domain,
        sync=sync,
    )
    
    return StartEvalRunResponse(
        run_id=eval_run.run_id,
        status=EvalRunStatusSchema(eval_run.status.value),
        message="Evaluation started." + (" Running synchronously." if sync else " Use SSE URL to stream progress."),
        sse_url=f"/api/v1/rag-eval/runs/{eval_run.run_id}/stream",
    )


@router.get("/runs", response_model=EvalRunListResponse)
async def list_eval_runs(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """
    List evaluation runs for the current customer.
    """
    service = RAGEvalService(db)
    
    status_filter = None
    if status:
        try:
            status_filter = EvalRunStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}"
            )
    
    offset = (page - 1) * page_size
    runs, total = service.list_eval_runs(
        customer_id=current_user.customer_id,
        domain=domain,
        status=status_filter,
        limit=page_size,
        offset=offset,
    )
    
    return EvalRunListResponse(
        runs=[_build_eval_summary(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
async def get_eval_run(
    run_id: str,
    include_results: bool = Query(True, description="Include individual results"),
    results_page: int = Query(1, ge=1),
    results_page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """
    Get details of an evaluation run.
    """
    service = RAGEvalService(db)
    eval_run = service.get_eval_run(run_id)
    
    if not eval_run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    
    if eval_run.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    summary = _build_eval_summary(eval_run)
    
    results = None
    total_results = 0
    if include_results:
        offset = (results_page - 1) * results_page_size
        result_list, total_results = service.get_eval_results(
            eval_run_id=eval_run.id,
            limit=results_page_size,
            offset=offset,
        )
        results = [_build_result_item(r) for r in result_list]
    
    return EvalRunResponse(
        summary=summary,
        results=results,
        total_results=total_results,
        page=results_page,
        page_size=results_page_size,
    )


@router.get("/runs/{run_id}/failures", response_model=FailureAnalysisResponse)
async def get_eval_failures(
    run_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """
    Get failures from an evaluation run for analysis.
    """
    service = RAGEvalService(db)
    eval_run = service.get_eval_run(run_id)
    
    if not eval_run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    
    if eval_run.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get failed results
    results, total = service.get_eval_results(
        eval_run_id=eval_run.id,
        verdict=EvalVerdict.FAIL,
        limit=limit,
    )
    
    failures = [
        FailureAnalysis(
            eval_id=r.eval_id,
            question=r.question,
            expected_answer=r.expected_answer,
            model_response=r.model_response or "",
            verdict_reason=r.verdict_reason or "",
            factual_correctness=r.factual_correctness,
            faithfulness=r.faithfulness,
            context_precision=r.context_precision,
            context_recall=r.context_recall,
        )
        for r in results
    ]
    
    return FailureAnalysisResponse(
        run_id=run_id,
        total_failures=total,
        failures=failures,
    )


@router.post("/runs/{run_id}/cancel")
async def cancel_eval_run(
    run_id: str,
    request: CancelEvalRunRequest = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Cancel a running evaluation.
    """
    service = RAGEvalService(db)
    eval_run = service.get_eval_run(run_id)
    
    if not eval_run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    
    if eval_run.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    reason = request.reason if request else None
    eval_run = service.cancel_eval_run(run_id, reason)
    
    return {"status": "cancelled", "run_id": run_id}


@router.delete("/runs/{run_id}")
async def delete_eval_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Delete an evaluation run and all associated results/telemetry.

    Notes:
    - Results + telemetry are deleted via FK ON DELETE CASCADE.
    - Refuses to delete PENDING/RUNNING runs (cancel first).
    """
    service = RAGEvalService(db)
    eval_run = service.get_eval_run(run_id)

    if not eval_run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")

    if eval_run.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")

    status_value = eval_run.status.value if hasattr(eval_run.status, "value") else str(eval_run.status)
    if status_value in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a running evaluation. Cancel it first.",
        )

    db.delete(eval_run)
    db.commit()

    return {"status": "deleted", "run_id": run_id}


@router.post("/citations/validate", response_model=CitationValidationResponse)
async def validate_citation(
    request: CitationValidationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["assistant:questions:read", "bi:read", "platform:admin"])),
):
    """
    Validate a single citation by page number.
    
    Supports:
    - question_id + citation_index (on-demand from chat)
    - raw citation + chunk_text (fallback mode)
    """
    validator = CitationValidationService(db=db)
    
    if request.question_id and request.citation_index:
        from src.models.data_analyst import DataAnalystMessage, DataSourceType
        
        message = db.query(DataAnalystMessage).filter(
            (DataAnalystMessage.question_id == request.question_id)
            | (DataAnalystMessage.message_id == request.question_id)
        ).first()
        
        if not message:
            raise HTTPException(status_code=404, detail="Question not found")
        
        if message.user_id != current_user.user_id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        result_metadata = message.result_metadata or {}
        sources = result_metadata.get("sources") or []
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except json.JSONDecodeError:
                sources = []
        
        source = next((s for s in sources if s.get("index") == request.citation_index), None)
        if not source:
            raise HTTPException(status_code=404, detail="Citation index not found")
        
        citation = source.get("citation") or ""
        parsed = validator.parse_citation(citation)
        chunk_text = None
        if parsed.chunk_id:
            fasb_service = get_fasb_service()
            chunk = fasb_service.get_chunk_by_id(parsed.chunk_id)
            if chunk:
                chunk_text = chunk.text
        
        if not chunk_text:
            chunk_text = source.get("text_preview") or ""
        
        if not chunk_text:
            raise HTTPException(status_code=400, detail="Chunk text not available for citation validation")
        
        question_text = message.original_question
        answer_text = _strip_sources_from_summary(result_metadata.get("summary", ""))
        
        result = await validator.validate_citation(
            citation=citation,
            chunk_text=chunk_text,
            question=question_text,
            answer=answer_text,
        )
        return CitationValidationResponse(result=CitationValidationResult(**result))
    
    if not request.citation or not request.chunk_text:
        raise HTTPException(
            status_code=400,
            detail="Provide question_id + citation_index or citation + chunk_text",
        )
    
    result = await validator.validate_citation(
        citation=request.citation,
        chunk_text=request.chunk_text,
        question=request.question,
        answer=request.answer,
    )
    return CitationValidationResponse(result=CitationValidationResult(**result))


@router.get("/runs/{run_id}/stream")
async def stream_eval_progress(
    run_id: str,
    token: str = Query(..., description="Auth token for SSE"),
    db: Session = Depends(get_db),
):
    """
    Stream evaluation progress via Server-Sent Events.
    
    Connect to this endpoint to receive real-time updates as the evaluation runs.
    """
    service = RAGEvalService(db)
    eval_run = service.get_eval_run(run_id)
    
    if not eval_run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    
    # Token validation would go here in production
    # For now, we allow access to any run
    
    async def event_generator():
        """Generate SSE events."""
        last_event_id = 0
        completed_statuses = {EvalRunStatus.COMPLETED, EvalRunStatus.FAILED, EvalRunStatus.CANCELLED}
        
        while True:
            # Refresh eval_run status
            db.refresh(eval_run)
            
            # Get new telemetry events
            events = service.get_telemetry_events(eval_run.id, after_id=last_event_id)
            
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
            
            # Check if evaluation is complete
            if eval_run.status in completed_statuses:
                # Send final status event
                final_data = json.dumps({
                    "event_type": "final",
                    "status": eval_run.status.value,
                    "pass_rate": eval_run.pass_rate,
                    "total_questions": eval_run.total_questions,
                    "pass_count": eval_run.pass_count,
                    "fail_count": eval_run.fail_count,
                })
                yield f"data: {final_data}\n\n"
                break
            
            await asyncio.sleep(1)  # Poll every second
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============= PDF Serving for Citation Preview =============

@router.options("/pdf/{doc_id}")
async def pdf_options(doc_id: str):
    """Handle CORS preflight for PDF endpoint."""
    from fastapi.responses import Response
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
        }
    )


# ============= Eval Sets Endpoints =============

@router.get("/eval-sets", response_model=EvalSetListResponse)
async def list_eval_sets(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    set_type: Optional[str] = Query(None, description="Filter by type (static/uploaded)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """
    List evaluation sets accessible to the current customer.
    
    Includes both built-in static sets and customer's uploaded sets.
    """
    from src.models.eval_set import EvalSetType as EvalSetTypeModel, EvalSetCategory as EvalSetCategoryModel
    
    service = EvalSetService(db)
    
    # Convert string filters to enums
    set_type_enum = None
    if set_type:
        try:
            set_type_enum = EvalSetTypeModel(set_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid set_type: {set_type}")
    
    category_enum = None
    if category:
        try:
            category_enum = EvalSetCategoryModel(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    
    eval_sets = service.list_eval_sets(
        customer_id=current_user.customer_id,
        domain=domain,
        set_type=set_type_enum,
        category=category_enum,
    )
    
    return EvalSetListResponse(
        eval_sets=[
            EvalSetSummary(
                id=es.id,
                customer_id=es.customer_id,
                name=es.name,
                description=es.description,
                domain=es.domain,
                set_type=EvalSetTypeSchema(es.set_type.value),
                category=EvalSetCategorySchema(es.category.value),
                example_count=es.example_count,
                difficulty_distribution=es.difficulty_distribution,
                tags=es.tags,
                is_built_in=es.is_built_in,
                created_by_user_id=es.created_by_user_id,
                created_at=es.created_at,
                updated_at=es.updated_at,
            )
            for es in eval_sets
        ],
        total=len(eval_sets),
    )


@router.get("/eval-sets/{eval_set_id}", response_model=EvalSetDetail)
async def get_eval_set(
    eval_set_id: int,
    include_questions: bool = Query(False, description="Include questions in response"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get details of an evaluation set."""
    service = EvalSetService(db)
    eval_set = service.get_eval_set_for_customer(eval_set_id, current_user.customer_id)
    
    if not eval_set:
        raise HTTPException(status_code=404, detail="Eval set not found")
    
    return EvalSetDetail(
        id=eval_set.id,
        customer_id=eval_set.customer_id,
        name=eval_set.name,
        description=eval_set.description,
        domain=eval_set.domain,
        set_type=EvalSetTypeSchema(eval_set.set_type.value),
        category=EvalSetCategorySchema(eval_set.category.value),
        example_count=eval_set.example_count,
        difficulty_distribution=eval_set.difficulty_distribution,
        tags=eval_set.tags,
        is_built_in=eval_set.is_built_in,
        created_by_user_id=eval_set.created_by_user_id,
        created_at=eval_set.created_at,
        updated_at=eval_set.updated_at,
        questions=eval_set.questions if include_questions else None,
    )


@router.get("/eval-sets/{eval_set_id}/questions", response_model=EvalSetQuestionsResponse)
async def get_eval_set_questions(
    eval_set_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Get questions from an eval set with pagination (for preview)."""
    service = EvalSetService(db)
    eval_set = service.get_eval_set_for_customer(eval_set_id, current_user.customer_id)
    
    if not eval_set:
        raise HTTPException(status_code=404, detail="Eval set not found")
    
    questions = service.get_questions(
        eval_set_id=eval_set_id,
        customer_id=current_user.customer_id,
        limit=limit,
        offset=offset,
    )
    
    return EvalSetQuestionsResponse(
        eval_set_id=eval_set_id,
        name=eval_set.name,
        questions=questions,
        total=eval_set.example_count,
        offset=offset,
        limit=limit,
    )


@router.post("/eval-sets", response_model=EvalSetSummary, status_code=status.HTTP_201_CREATED)
async def create_eval_set(
    name: str = Form(..., min_length=1, max_length=255),
    description: Optional[str] = Form(None, max_length=2000),
    domain: str = Form("fasb", max_length=50),
    category: str = Form("general"),
    tags: Optional[str] = Form(None, description="Comma-separated tags"),
    file: UploadFile = File(..., description="Questions file (.jsonl, .csv, or .json)"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Upload a new eval set from JSONL, CSV, or JSON file.

    Required fields in every format:
    - question: str (required)
    - reference_answer: str (required)
    Optional fields:
    - eval_id: str (auto-generated if missing)
    - difficulty: str (default: unknown)
    - gold_chunk_ids: list[str]
    - reference_contexts: list[str]
    - tags: list[str]
    """
    from src.models.eval_set import EvalSetType as EvalSetTypeModel, EvalSetCategory as EvalSetCategoryModel
    
    service = EvalSetService(db)
    
    # Parse category
    try:
        category_enum = EvalSetCategoryModel(category)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category: {category}. Valid: {[c.value for c in EvalSetCategoryModel]}"
        )
    
    # Parse tags
    parsed_tags = None
    if tags:
        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]
    
    # Read and validate file
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    
    try:
        questions, difficulty_dist = service.validate_dataset_content(
            content_str,
            filename=file.filename,
        )
    except EvalSetValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create the eval set
    eval_set = service.create_eval_set(
        customer_id=current_user.customer_id,
        name=name,
        questions=questions,
        domain=domain,
        description=description,
        set_type=EvalSetTypeModel.UPLOADED,
        category=category_enum,
        tags=parsed_tags,
        is_built_in=False,
        user_id=current_user.user_id,
        difficulty_distribution=difficulty_dist,
    )
    
    logger.info(
        "eval_set_uploaded",
        eval_set_id=eval_set.id,
        name=name,
        count=eval_set.example_count,
        user_id=current_user.user_id,
    )
    
    return EvalSetSummary(
        id=eval_set.id,
        customer_id=eval_set.customer_id,
        name=eval_set.name,
        description=eval_set.description,
        domain=eval_set.domain,
        set_type=EvalSetTypeSchema(eval_set.set_type.value),
        category=EvalSetCategorySchema(eval_set.category.value),
        example_count=eval_set.example_count,
        difficulty_distribution=eval_set.difficulty_distribution,
        tags=eval_set.tags,
        is_built_in=eval_set.is_built_in,
        created_by_user_id=eval_set.created_by_user_id,
        created_at=eval_set.created_at,
        updated_at=eval_set.updated_at,
    )


@router.patch("/eval-sets/{eval_set_id}", response_model=EvalSetSummary)
async def update_eval_set(
    eval_set_id: int,
    request: UpdateEvalSetRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Update eval set metadata (uploaded sets only).
    
    Cannot modify built-in static sets.
    """
    from src.models.eval_set import EvalSetCategory as EvalSetCategoryModel
    
    service = EvalSetService(db)
    
    # Check if set exists and is owned by customer
    eval_set = service.get_eval_set_for_customer(eval_set_id, current_user.customer_id)
    if not eval_set:
        raise HTTPException(status_code=404, detail="Eval set not found")
    
    if eval_set.is_built_in:
        raise HTTPException(status_code=403, detail="Cannot modify built-in eval sets")
    
    # Build update kwargs
    update_kwargs = {}
    if request.name is not None:
        update_kwargs["name"] = request.name
    if request.description is not None:
        update_kwargs["description"] = request.description
    if request.category is not None:
        update_kwargs["category"] = EvalSetCategoryModel(request.category.value)
    if request.tags is not None:
        update_kwargs["tags"] = request.tags
    
    updated = service.update_eval_set(
        eval_set_id=eval_set_id,
        customer_id=current_user.customer_id,
        **update_kwargs
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Eval set not found or cannot be modified")
    
    return EvalSetSummary(
        id=updated.id,
        customer_id=updated.customer_id,
        name=updated.name,
        description=updated.description,
        domain=updated.domain,
        set_type=EvalSetTypeSchema(updated.set_type.value),
        category=EvalSetCategorySchema(updated.category.value),
        example_count=updated.example_count,
        difficulty_distribution=updated.difficulty_distribution,
        tags=updated.tags,
        is_built_in=updated.is_built_in,
        created_by_user_id=updated.created_by_user_id,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/eval-sets/{eval_set_id}")
async def delete_eval_set(
    eval_set_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Delete an eval set (uploaded sets only).
    
    Cannot delete built-in static sets.
    """
    service = EvalSetService(db)
    
    # Check if set exists first
    eval_set = service.get_eval_set_for_customer(eval_set_id, current_user.customer_id)
    if not eval_set:
        raise HTTPException(status_code=404, detail="Eval set not found")
    
    if eval_set.is_built_in:
        raise HTTPException(status_code=403, detail="Cannot delete built-in eval sets")
    
    if eval_set.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    deleted = service.delete_eval_set(eval_set_id, current_user.customer_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Eval set not found or cannot be deleted")
    
    logger.info(
        "eval_set_deleted",
        eval_set_id=eval_set_id,
        user_id=current_user.user_id,
    )
    
    return {"status": "deleted", "eval_set_id": eval_set_id}


@router.get("/eval-sets/{eval_set_id}/download")
async def download_eval_set(
    eval_set_id: int,
    format: str = Query("jsonl", pattern="^(jsonl|csv|json)$", description="Download format"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:read", "platform:admin"])),
):
    """Download an eval set as JSONL, CSV, or JSON."""
    service = EvalSetService(db)
    eval_set = service.get_eval_set_for_customer(eval_set_id, current_user.customer_id)
    
    if not eval_set:
        raise HTTPException(status_code=404, detail="Eval set not found")

    questions = eval_set.questions or []
    safe_name = re.sub(r"[^\w\-]", "_", eval_set.name)[:50]

    if format == "json":
        content = json.dumps({"questions": questions}, ensure_ascii=False, indent=2)
        filename = f"{safe_name}.json"
        media_type = "application/json"
    elif format == "csv":
        from io import StringIO
        import csv

        output = StringIO()
        fieldnames = [
            "eval_id",
            "question",
            "reference_answer",
            "difficulty",
            "gold_chunk_ids",
            "reference_contexts",
            "tags",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for q in questions:
            writer.writerow(
                {
                    "eval_id": q.get("eval_id", ""),
                    "question": q.get("question", ""),
                    "reference_answer": q.get("reference_answer", ""),
                    "difficulty": q.get("difficulty", ""),
                    "gold_chunk_ids": json.dumps(q.get("gold_chunk_ids", []), ensure_ascii=False),
                    "reference_contexts": json.dumps(q.get("reference_contexts", []), ensure_ascii=False),
                    "tags": json.dumps(q.get("tags", []), ensure_ascii=False),
                }
            )
        content = output.getvalue()
        filename = f"{safe_name}.csv"
        media_type = "text/csv"
    else:
        lines = [json.dumps(q, ensure_ascii=False) for q in questions]
        content = "\n".join(lines)
        filename = f"{safe_name}.jsonl"
        media_type = "application/x-ndjson"

    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/eval-sets/{eval_set_id}/duplicate", response_model=EvalSetSummary, status_code=status.HTTP_201_CREATED)
async def duplicate_eval_set(
    eval_set_id: int,
    name: Optional[str] = Query(None, description="Name for the duplicate (defaults to 'Copy of ...')"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Duplicate an eval set to the customer's uploaded sets.
    
    Useful for creating custom versions of built-in sets.
    """
    from src.models.eval_set import EvalSetType as EvalSetTypeModel
    
    service = EvalSetService(db)
    
    # Get source set
    source_set = service.get_eval_set_for_customer(eval_set_id, current_user.customer_id)
    if not source_set:
        raise HTTPException(status_code=404, detail="Eval set not found")
    
    # Generate name if not provided
    duplicate_name = name or f"Copy of {source_set.name}"
    
    # Create duplicate as uploaded set
    duplicate = service.create_eval_set(
        customer_id=current_user.customer_id,
        name=duplicate_name,
        questions=source_set.questions.copy() if source_set.questions else [],
        domain=source_set.domain,
        description=source_set.description,
        set_type=EvalSetTypeModel.UPLOADED,
        category=source_set.category,
        tags=source_set.tags.copy() if source_set.tags else None,
        is_built_in=False,
        user_id=current_user.user_id,
        difficulty_distribution=source_set.difficulty_distribution.copy() if source_set.difficulty_distribution else None,
    )
    
    logger.info(
        "eval_set_duplicated",
        source_id=eval_set_id,
        duplicate_id=duplicate.id,
        user_id=current_user.user_id,
    )
    
    return EvalSetSummary(
        id=duplicate.id,
        customer_id=duplicate.customer_id,
        name=duplicate.name,
        description=duplicate.description,
        domain=duplicate.domain,
        set_type=EvalSetTypeSchema(duplicate.set_type.value),
        category=EvalSetCategorySchema(duplicate.category.value),
        example_count=duplicate.example_count,
        difficulty_distribution=duplicate.difficulty_distribution,
        tags=duplicate.tags,
        is_built_in=duplicate.is_built_in,
        created_by_user_id=duplicate.created_by_user_id,
        created_at=duplicate.created_at,
        updated_at=duplicate.updated_at,
    )


@router.post("/eval-sets/seed-static")
async def seed_static_eval_sets(
    force: bool = Query(False, description="Force re-seed even if sets exist"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["platform:admin"])),
):
    """
    Seed built-in static eval sets.
    
    Admin only. Creates curated eval sets from the main eval questions file.
    """
    service = EvalSetService(db)
    created = service.seed_static_sets(force=force)
    
    return {
        "status": "seeded" if created else "already_exists",
        "count": len(created),
        "sets": [{"id": s.id, "name": s.name, "count": s.example_count} for s in created]
    }


# ============= V2 Run Endpoint with Eval Source Support =============

@router.post("/runs/v2", response_model=StartEvalRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_eval_run_v2(
    request: StartEvalRunRequestV2,
    sync: bool = Query(False, description="Run synchronously (for testing)"),
    db: Session = Depends(get_db),
    current_user=Depends(require_any_permission(["bi:write", "platform:admin"])),
):
    """
    Start a new RAG evaluation run (v2 with eval source support).
    
    Either:
    - Use an eval_set (eval_source=eval_set, eval_set_id required): Runs exactly that set
    - Use random sampling (eval_source=random_sampling): Traditional random/stratified sampling
    """
    from src.models.rag_eval import EvalSource as EvalSourceModel
    
    service = RAGEvalService(db)
    eval_set_service = EvalSetService(db)
    
    # Validate eval source configuration
    eval_set = None
    if request.eval_source == EvalSourceSchema.EVAL_SET:
        if not request.eval_set_id:
            raise HTTPException(
                status_code=400,
                detail="eval_set_id is required when eval_source=eval_set"
            )
        
        # Verify access to eval set
        eval_set = eval_set_service.get_eval_set_for_customer(
            request.eval_set_id,
            current_user.customer_id
        )
        if not eval_set:
            raise HTTPException(status_code=404, detail="Eval set not found")
    
    # Build difficulty counts from request
    difficulty_counts = None
    if request.difficulty_counts and request.eval_source == EvalSourceSchema.RANDOM_SAMPLING:
        difficulty_counts = {}
        if request.difficulty_counts.easy is not None:
            difficulty_counts["easy"] = request.difficulty_counts.easy
        if request.difficulty_counts.medium is not None:
            difficulty_counts["medium"] = request.difficulty_counts.medium
        if request.difficulty_counts.hard is not None:
            difficulty_counts["hard"] = request.difficulty_counts.hard
        
        if not difficulty_counts:
            difficulty_counts = None
    
    # Determine sample size
    sample_size = None
    if request.eval_source == EvalSourceSchema.EVAL_SET:
        sample_size = eval_set.example_count
    elif request.sample_size:
        sample_size = request.sample_size
    elif not difficulty_counts:
        # Use default stratified sampling
        difficulty_counts = {"easy": 5, "medium": 5, "hard": 5}
    
    # Create the evaluation run
    eval_run = service.create_eval_run_v2(
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        domain=request.domain,
        sample_size=sample_size or (sum(difficulty_counts.values()) if difficulty_counts else 0),
        difficulty_counts=difficulty_counts,
        seed=request.seed,
        concurrency=request.concurrency,
        validate_citations=request.validate_citations,
        eval_source=EvalSourceModel(request.eval_source.value),
        eval_set_id=request.eval_set_id if eval_set else None,
        eval_set_name=eval_set.name if eval_set else None,
    )
    
    if sync:
        # Run synchronously for testing
        logger.info("Running evaluation synchronously", run_id=eval_run.run_id)
        try:
            eval_run = await service.run_evaluation_v2(eval_run, eval_set=eval_set)
        except Exception as e:
            logger.error("Sync evaluation failed", error=str(e), run_id=eval_run.run_id)
            eval_run.status = EvalRunStatus.FAILED
            db.commit()
    else:
        # Trigger async execution
        should_use_celery = False
        try:
            from src.celery_app import celery_app
            inspector = celery_app.control.inspect(timeout=1.0)
            pong = inspector.ping() or {}
            should_use_celery = len(pong) > 0
        except Exception as e:
            logger.warning("celery_ping_failed", error=str(e))

        if should_use_celery:
            from src.tasks.rag_eval_tasks import run_rag_evaluation_v2
            run_rag_evaluation_v2.delay(eval_run.id, request.eval_set_id)
            logger.info("eval_run_dispatched_to_celery", run_id=eval_run.run_id)
        else:
            logger.warning("no_celery_workers_running_in_process", run_id=eval_run.run_id)

            async def run_in_background():
                from src.models import database
                if database.SessionLocal is None:
                    database.init_database()
                session = database.SessionLocal()
                try:
                    bg_service = RAGEvalService(session)
                    bg_eval_set_service = EvalSetService(session)
                    from src.models.rag_eval import RAGEvalRun
                    bg_eval_run = session.query(RAGEvalRun).filter(RAGEvalRun.id == eval_run.id).first()
                    bg_eval_set = None
                    if request.eval_set_id:
                        bg_eval_set = bg_eval_set_service.get_eval_set(request.eval_set_id)
                    if bg_eval_run:
                        await bg_service.run_evaluation_v2(bg_eval_run, eval_set=bg_eval_set)
                except Exception as bg_error:
                    logger.error("background_eval_failed", run_id=eval_run.run_id, error=str(bg_error), exc_info=True)
                finally:
                    session.close()

            asyncio.create_task(run_in_background())
    
    logger.info(
        "eval_run_v2_started",
        run_id=eval_run.run_id,
        user_id=current_user.user_id,
        eval_source=request.eval_source.value,
        eval_set_id=request.eval_set_id,
        sync=sync,
    )
    
    return StartEvalRunResponse(
        run_id=eval_run.run_id,
        status=EvalRunStatusSchema(eval_run.status.value),
        message=f"Evaluation started using {request.eval_source.value}." + (" Running synchronously." if sync else " Use SSE URL to stream progress."),
        sse_url=f"/api/v1/rag-eval/runs/{eval_run.run_id}/stream",
    )


# ============= PDF Serving for Citation Preview =============

@router.get("/pdf/{doc_id}")
async def get_pdf_document(
    doc_id: str,
    page: Optional[int] = Query(None, description="Page number to open (1-based)"),
    token: Optional[str] = Query(None, description="Auth token (for iframe access)"),
):
    """
    Serve a FASB PDF document for citation preview.
    
    Accepts token as query parameter for iframe compatibility (iframes can't send headers).
    The optional `page` parameter is included in the response headers for client-side navigation.
    Most PDF viewers support the #page=N fragment for direct page navigation.
    """
    from pathlib import Path
    from fastapi.responses import Response
    from src.services.auth_service import AuthService
    
    # CORS headers for PDF.js fetch support
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }
    
    # Validate token (passed as query param for iframe compatibility)
    if not token:
        return Response(
            content='{"error": "Not authenticated"}',
            status_code=401,
            media_type="application/json",
            headers=cors_headers
        )
    
    try:
        auth_service = AuthService()
        payload = await auth_service.verify_token(token)
        if not payload:
            return Response(
                content='{"error": "Invalid token"}',
                status_code=401,
                media_type="application/json",
                headers=cors_headers
            )
    except Exception as e:
        logger.warning(f"PDF auth failed: {e}")
        return Response(
            content='{"error": "Invalid token"}',
            status_code=401,
            media_type="application/json",
            headers=cors_headers
        )
    
    settings = get_settings()
    
    # Validate doc_id (should be numeric to prevent path traversal)
    if not doc_id.isdigit():
        return Response(
            content='{"error": "Invalid document ID"}',
            status_code=400,
            media_type="application/json",
            headers=cors_headers
        )
    
    pdf_path = Path(settings.fasb_docs_path) / f"{doc_id}.pdf"
    
    if not pdf_path.exists():
        return Response(
            content=f'{{"error": "PDF document {doc_id} not found"}}',
            status_code=404,
            media_type="application/json",
            headers=cors_headers
        )
    
    # Read and return PDF with CORS headers
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            **cors_headers,
            "Content-Disposition": f"inline; filename={doc_id}.pdf",
            "X-Page-Number": str(page) if page else "1",
        }
    )
