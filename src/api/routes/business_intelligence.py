"""
Business Intelligence API Routes

API endpoints for the Business Intelligence Q&A system.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import asyncio
import json
import time
import uuid
import redis
from celery.exceptions import CeleryError
from datetime import datetime, timezone

from src.models import get_db
from src.models.auth import User
from src.models.business_intelligence import QuestionStatus
from src.middleware.authorization import AuthorizationMiddleware
from src.api.schemas.business_intelligence import (
    QuestionSubmitRequest, QuestionSubmitResponse,
    QuestionResponse, QuestionListResponse,
    QuestionStatusResponse, TelemetryEventResponse,
    PromptListResponse, EnrichedPromptResponse,
    AnalysisResultResponse, HealthCheckResponse
)
from src.services.business_intelligence_service import BusinessIntelligenceService
from src.services.auth_service import auth_service
from src.services.settings_service import SettingsService
from src.tasks.business_intelligence_tasks import process_bi_question
from src.core.logging import get_logger, LogCategory
from src.core.auth_context import CurrentUserContext
from src.core.config import get_settings
from src.celery_app import celery_app

settings = get_settings()
DEFAULT_CELERY_QUEUE = celery_app.conf.task_default_queue or "celery"

logger = get_logger(__name__, LogCategory.API)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/v1/bi", tags=["Business Intelligence"])


@router.post(
    "/questions",
    response_model=QuestionSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a business intelligence question",
    description="Submit a question about your business data. The question will be processed asynchronously through task enrichment and data analysis flows."
)
async def submit_question(
    request: QuestionSubmitRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:ask"))
):
    """
    Submit a new business intelligence question.
    
    The question will be processed through:
    1. Task Enrichment Flow - Analyzes intent and enriches the prompt
    2. Data Analysis Flow - Retrieves data and generates analysis
    
    Returns immediately with a question_id that can be used to track progress.
    """
    # Determine target company for HR data analysis
    settings_service = SettingsService(db)
    company_hr_dataset = request.company_hr_dataset
    
    if not company_hr_dataset:
        # Use system default if not specified
        company_hr_dataset = settings_service.get_default_company_hr_dataset()
        logger.info(
            "using_default_company",
            user_id=current_user.user_id,
            default_company=company_hr_dataset
        )
    
    # Authorization: Check if user has access to the target company
    if not auth_middleware.check_company_access(current_user, company_hr_dataset):
        logger.warning(
            "company_access_denied",
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
            target_company=company_hr_dataset
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to access data from company '{company_hr_dataset}'"
        )
    
    logger.info(
        "bi_question_submit",
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        company_hr_dataset=company_hr_dataset,
        question_length=len(request.question)
    )
    
    try:
        bi_service = BusinessIntelligenceService(db)
        
        # Create question record
        question = bi_service.create_question(
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
            company_hr_dataset=company_hr_dataset,
            question=request.question,
            session_id=request.session_id,
            metadata=request.metadata
        )
        
        # Trigger async processing
        try:
            async_result = process_bi_question.delay(
                question_id=question.question_id,
                user_id=current_user.user_id,
                customer_id=current_user.customer_id,
                company_hr_dataset=company_hr_dataset
            )
        except CeleryError as celery_error:
            error_message = (
                "Unable to enqueue question for processing. "
                "Background workers appear unavailable."
            )
            logger.error(
                "bi_question_enqueue_failed",
                question_id=question.question_id,
                user_id=current_user.user_id,
                error=str(celery_error),
                exc_info=True
            )
            bi_service.update_question_status(
                question.question_id,
                QuestionStatus.FAILED,
                error_message=error_message
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_message
            ) from celery_error
        except Exception as enqueue_error:
            error_message = (
                "Unexpected error while scheduling question for processing."
            )
            logger.error(
                "bi_question_enqueue_exception",
                question_id=question.question_id,
                user_id=current_user.user_id,
                error=str(enqueue_error),
                exc_info=True
            )
            bi_service.update_question_status(
                question.question_id,
                QuestionStatus.FAILED,
                error_message=error_message
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_message
            ) from enqueue_error
        
        return QuestionSubmitResponse(
            question_id=question.question_id,
            status=question.status,
            message="Question submitted successfully and is being processed",
            task_id=async_result.id if 'async_result' in locals() else None
        )
        
    except Exception as e:
        logger.error(
            "bi_question_submit_error",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit question: {str(e)}"
        )


@router.get(
    "/questions/{question_id}",
    response_model=QuestionResponse,
    summary="Get question details",
    description="Get detailed information about a specific question including enriched prompt, analysis session, and results."
)
async def get_question(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """Get detailed information about a question."""
    bi_service = BusinessIntelligenceService(db)
    
    question = bi_service.get_question(question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Check authorization
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this question"
        )
    
    return _serialize_question(question)


@router.get(
    "/questions/{question_id}/status",
    response_model=QuestionStatusResponse,
    summary="Get question status",
    description="Get quick status information about a question's processing progress."
)
async def get_question_status(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """Get quick status of a question."""
    bi_service = BusinessIntelligenceService(db)
    
    question = bi_service.get_question(question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Check authorization
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this question"
        )
    
    # Calculate progress percentage
    progress_map = {
        QuestionStatus.PENDING: 0.0,
        QuestionStatus.ENRICHING: 25.0,
        QuestionStatus.ANALYZING: 50.0,
        QuestionStatus.COMPLETED: 100.0,
        QuestionStatus.FAILED: 0.0
    }
    
    # Get current stage
    stage_map = {
        QuestionStatus.PENDING: "Queued",
        QuestionStatus.ENRICHING: "Task Enrichment",
        QuestionStatus.ANALYZING: "Data Analysis",
        QuestionStatus.COMPLETED: "Completed",
        QuestionStatus.FAILED: "Failed"
    }
    
    question_enum = question.status if isinstance(question.status, QuestionStatus) else QuestionStatus(question.status)

    return QuestionStatusResponse(
        question_id=question.question_id,
        status=question_enum.value,
        progress_percentage=progress_map.get(question_enum, 0.0),
        current_stage=stage_map.get(question_enum, "Unknown"),
        error_message=question.error_message
    )


@router.get(
    "/questions/{question_id}/telemetry",
    summary="Stream telemetry events",
    description="Stream real-time telemetry events from agent execution using Server-Sent Events (SSE)."
)
async def stream_telemetry(
    request: Request,
    question_id: str,
    token: str = Query(..., description="JWT access token (EventSource doesn't support headers)"),
    db: Session = Depends(get_db)
):
    """
    Stream telemetry events for a question using Server-Sent Events.
    
    This endpoint streams real-time updates about agent execution,
    tool usage, and progress updates.
    
    Note: Token is passed as query param because EventSource doesn't support custom headers.
    """
    # Verify token and get user (EventSource can't send Authorization header)
    try:
        payload = await auth_service.verify_token(token)
        user_id = int(payload.get("sub"))
        user = await auth_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found"
            )
        
        # Build user context (simplified for SSE)
        current_user = CurrentUserContext(
            user_id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            customer_id=user.customer_id,
            department=getattr(user, "department", None),
            team=getattr(user, "team", None),
            roles=[role.name for role in getattr(user, "roles", [])],
            permissions=user.get_permissions() if hasattr(user, "get_permissions") else [],
            primary_role=user.primary_role.name if user.primary_role else None,
            last_login_at=getattr(user, "last_login_at", None),
            created_at=user.created_at,
        )
    except Exception as e:
        logger.error("SSE auth failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired token"
        )
    
    bi_service = BusinessIntelligenceService(db)
    
    question = bi_service.get_question(question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Check authorization
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this question"
        )
    
    async def event_generator():
        """Generate SSE events from telemetry."""
        last_event_id = 0
        idle_cycles = 0
        poll_interval = 1.0
        heartbeat_interval = 15

        while True:
            if await request.is_disconnected():
                logger.debug("SSE client disconnected", question_id=question_id)
                break

            if question.analysis_session_id:
                events = bi_service.get_telemetry_events(
                    session_id=question.analysis_session_id,
                    limit=100,
                    after_id=last_event_id
                )

                for event in events:
                    event_data = {
                        "event_id": f"telemetry-{event.telemetry_id}",
                        "telemetry_id": event.telemetry_id,
                        "event_type": event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
                        "agent_name": event.agent_name,
                        "tool_name": event.tool_name,
                        "stage_name": event.stage_name,
                        "message": event.message,
                        "user_message": event.user_message,
                        "progress_percentage": event.progress_percentage,
                        "timestamp": event.timestamp.isoformat() if event.timestamp else datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                    }

                    yield f"data: {json.dumps(event_data)}\n\n"
                    last_event_id = event.id
                    idle_cycles = 0

            # Re-fetch question status periodically
            latest_question = bi_service.get_question(question_id)
            if latest_question:
                question_status = latest_question.status
                question_error = latest_question.error_message
            else:
                question_status = QuestionStatus.FAILED
                question_error = "Question not found"

            if question_status in [QuestionStatus.COMPLETED, QuestionStatus.FAILED]:
                final_event = {
                    "event_id": f"terminal-{uuid.uuid4().hex}",
                    "event_type": "completed" if question_status == QuestionStatus.COMPLETED else "failed",
                    "status": question_status.value,
                    "message": "Processing completed" if question_status == QuestionStatus.COMPLETED else question_error,
                    "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                }
                yield f"data: {json.dumps(final_event)}\n\n"
                break

            idle_cycles += 1
            if idle_cycles >= heartbeat_interval:
                status_value = question_status.value if hasattr(question_status, "value") else question_status
                heartbeat_payload = {
                    "event_id": f"heartbeat-{uuid.uuid4().hex}",
                    "event_type": "heartbeat",
                    "status": status_value,
                    "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                }
                yield f"data: {json.dumps(heartbeat_payload)}\n\n"
                idle_cycles = 0

            await asyncio.sleep(poll_interval)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get(
    "/questions/{question_id}/result",
    response_model=AnalysisResultResponse,
    summary="Get analysis result",
    description="Get the final analysis result for a completed question."
)
async def get_analysis_result(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """Get the analysis result for a question."""
    bi_service = BusinessIntelligenceService(db)
    
    question = bi_service.get_question(question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Check authorization
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this question"
        )
    
    if not question.result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis result not yet available"
        )
    
    return question.result


@router.get(
    "/questions",
    response_model=QuestionListResponse,
    summary="List questions",
    description="List business intelligence questions with optional filters and pagination."
)
async def list_questions(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    status_filter: Optional[QuestionStatus] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """List questions with pagination."""
    bi_service = BusinessIntelligenceService(db)
    
    offset = (page - 1) * page_size
    
    questions, total = bi_service.list_questions(
        user_id=current_user.user_id if not current_user.is_superuser else None,
        customer_id=current_user.customer_id,
        session_id=session_id,
        status=status_filter,
        limit=page_size,
        offset=offset
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    # Convert questions to dict to avoid SQLAlchemy metadata conflict
    # Must manually serialize to avoid SQLAlchemy's reserved 'metadata' attribute
    questions_data = [_serialize_question(q) for q in questions]
    
    return {
        "questions": questions_data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


def _serialize_question(question):
    status_value = question.status.value if hasattr(question.status, "value") else question.status
    return {
        "id": question.id,
        "question_id": question.question_id,
        "user_id": question.user_id,
        "customer_id": question.customer_id,
        "session_id": question.session_id,
        "original_question": question.original_question,
        "status": status_value,
        "enriched_prompt": question.enriched_prompt,
        "analysis_session": question.analysis_session,
        "result": question.result,
        "error_message": question.error_message,
        "question_metadata": question.question_metadata or {},
        "created_at": question.created_at,
        "updated_at": question.updated_at,
        "completed_at": question.completed_at,
    }


@router.get(
    "/prompts",
    response_model=PromptListResponse,
    summary="List enriched prompts",
    description="List enriched prompts from the task enrichment flow. Useful for debugging and improving prompt quality."
)
async def list_prompts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:delete"))
):
    """List enriched prompts with pagination."""
    bi_service = BusinessIntelligenceService(db)
    
    offset = (page - 1) * page_size
    prompts, total = bi_service.list_enriched_prompts(
        limit=page_size,
        offset=offset
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return PromptListResponse(
        prompts=prompts,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get(
    "/questions/{question_id}/timeline",
    summary="Get execution timeline",
    description="Get a complete timeline of agent execution including tool calls, responses, and telemetry for a question."
)
async def get_execution_timeline(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """
    Get a complete execution timeline for a question.
    
    Returns a comprehensive timeline including:
    - Tool executions with inputs and outputs
    - Agent responses at each stage
    - Telemetry events
    - Enriched prompts
    
    Useful for debugging and showing users what the system is doing.
    """
    bi_service = BusinessIntelligenceService(db)
    
    # Get the question
    question = bi_service.get_question(question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Authorization check - match logic from get_question endpoint
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this question"
        )
    
    # Build timeline
    timeline = {
        "question_id": question_id,
        "status": question.status.value if hasattr(question.status, "value") else question.status,
        "created_at": question.created_at,
        "completed_at": question.completed_at,
        "enriched_prompt": None,
        "tool_executions": [],
        "agent_responses": [],
        "telemetry_events": []
    }
    
    # Get enriched prompt
    if question.enriched_prompt:
        timeline["enriched_prompt"] = {
            "prompt_id": question.enriched_prompt.prompt_id,
            "original_input": question.enriched_prompt.original_input,
            "enriched_prompt": question.enriched_prompt.enriched_prompt,
            "intent_type": question.enriched_prompt.intent_type,
            "complexity": question.enriched_prompt.complexity,
            "confidence_score": question.enriched_prompt.confidence_score,
            "quality_score": question.enriched_prompt.quality_score,
            "created_at": question.enriched_prompt.created_at
        }
    
    # Get tool executions if session exists
    if question.analysis_session:
        session = question.analysis_session
        
        # Get tool executions
        tool_executions = bi_service.get_tool_executions(session.id)
        for execution in tool_executions:
            timeline["tool_executions"].append({
                "execution_id": execution.execution_id,
                "tool_name": execution.tool_name,
                "agent_name": execution.agent_name,
                "tool_input": execution.tool_input,
                "tool_output": execution.tool_output,
                "status": execution.status,
                "error_message": execution.error_message,
                "duration_ms": execution.duration_ms,
                "results_count": execution.results_count,
                "started_at": execution.started_at,
                "completed_at": execution.completed_at
            })
        
        # Get agent responses
        agent_responses = bi_service.get_agent_responses(session.id)
        for response in agent_responses:
            timeline["agent_responses"].append({
                "response_id": response.response_id,
                "agent_name": response.agent_name,
                "stage_name": response.stage_name,
                "input_prompt": response.input_prompt,
                "response_text": response.response_text,
                "reasoning": response.reasoning,
                "tool_calls": response.tool_calls,
                "confidence_score": response.confidence_score,
                "duration_ms": response.duration_ms,
                "created_at": response.created_at
            })
        
        # Get telemetry events
        telemetry_events = bi_service.get_telemetry_events(session.id, limit=200)
        for event in telemetry_events:
            timeline["telemetry_events"].append({
                "telemetry_id": event.telemetry_id,
                "event_type": event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
                "agent_name": event.agent_name,
                "tool_name": event.tool_name,
                "stage_name": event.stage_name,
                "message": event.message,
                "user_message": event.user_message,
                "progress_percentage": event.progress_percentage,
                "data": event.data,
                "error_details": event.error_details,
                "duration_ms": event.duration_ms,
                "timestamp": event.timestamp
            })
    
    return timeline


@router.get(
    "/sessions/{session_id}/tool-executions",
    summary="Get tool executions for a session",
    description="Get all tool executions for an analysis session, including inputs, outputs, and timing."
)
async def get_tool_executions(
    session_id: str,
    tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """Get tool executions for an analysis session."""
    from src.models.business_intelligence import BIAnalysisSession
    
    # Get session
    session = db.query(BIAnalysisSession).filter(
        BIAnalysisSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Authorization check via question
    if session.question.customer_id != current_user.customer_id and not auth_middleware.has_role(current_user, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this session"
        )
    
    bi_service = BusinessIntelligenceService(db)
    executions = bi_service.get_tool_executions(session.id, tool_name=tool_name)
    
    return {
        "session_id": session_id,
        "tool_executions": [
            {
                "execution_id": e.execution_id,
                "tool_name": e.tool_name,
                "agent_name": e.agent_name,
                "tool_input": e.tool_input,
                "tool_output": e.tool_output,
                "status": e.status,
                "error_message": e.error_message,
                "duration_ms": e.duration_ms,
                "results_count": e.results_count,
                "started_at": e.started_at,
                "completed_at": e.completed_at
            }
            for e in executions
        ],
        "total": len(executions)
    }


@router.get(
    "/sessions/{session_id}/agent-responses",
    summary="Get agent responses for a session",
    description="Get all agent responses for an analysis session, including reasoning and tool usage."
)
async def get_agent_responses(
    session_id: str,
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    stage_name: Optional[str] = Query(None, description="Filter by stage name"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """Get agent responses for an analysis session."""
    from src.models.business_intelligence import BIAnalysisSession
    
    # Get session
    session = db.query(BIAnalysisSession).filter(
        BIAnalysisSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Authorization check via question
    if session.question.customer_id != current_user.customer_id and not auth_middleware.has_role(current_user, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this session"
        )
    
    bi_service = BusinessIntelligenceService(db)
    responses = bi_service.get_agent_responses(
        session.id,
        agent_name=agent_name,
        stage_name=stage_name
    )
    
    return {
        "session_id": session_id,
        "agent_responses": [
            {
                "response_id": r.response_id,
                "agent_name": r.agent_name,
                "stage_name": r.stage_name,
                "input_prompt": r.input_prompt,
                "response_text": r.response_text,
                "reasoning": r.reasoning,
                "tool_calls": r.tool_calls,
                "confidence_score": r.confidence_score,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at
            }
            for r in responses
        ],
        "total": len(responses)
    }


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check the health of the Business Intelligence system components."
)
async def health_check(
    db: Session = Depends(get_db)
):
    """Check system health."""
    components: Dict[str, str] = {}
    component_details: Dict[str, Any] = {}
    
    # Check database
    try:
        db.execute("SELECT 1")
        components["database"] = "healthy"
    except Exception:
        components["database"] = "unhealthy"
    
    # Check Redis / Celery broker
    loop = asyncio.get_running_loop()

    async def check_redis() -> Dict[str, Any]:
        def _check():
            client = redis.Redis.from_url(settings.redis_host_url)
            started = time.perf_counter()
            client.ping()
            latency_ms = (time.perf_counter() - started) * 1000
            queue_depth = client.llen(DEFAULT_CELERY_QUEUE)
            return {
                "latency_ms": round(latency_ms, 2),
                "queue_depth": queue_depth
            }

        return await loop.run_in_executor(None, _check)

    async def check_celery_workers() -> Dict[str, Any]:
        def _check():
            inspector = celery_app.control.inspect(timeout=1)
            if inspector is None:
                raise RuntimeError("Celery inspector unavailable")
            ping_result = inspector.ping()
            if not ping_result:
                raise RuntimeError("No active Celery workers responded to ping")
            return {
                "workers": list(ping_result.keys())
            }

        return await loop.run_in_executor(None, _check)

    try:
        redis_info = await check_redis()
        components["redis"] = "healthy"
        component_details["redis"] = redis_info
    except Exception as redis_error:
        components["redis"] = "unhealthy"
        component_details["redis"] = {"error": str(redis_error)}

    try:
        celery_info = await check_celery_workers()
        components["celery_workers"] = "healthy"
        component_details["celery_workers"] = celery_info
    except Exception as celery_error:
        components["celery_workers"] = "unhealthy"
        component_details["celery_workers"] = {"error": str(celery_error)}

    # Check vector service (basic check)
    try:
        from src.services.vector_service import VectorService
        VectorService(db)
        components["vector_service"] = "healthy"
    except Exception as vector_error:
        components["vector_service"] = "unhealthy"
        component_details["vector_service"] = {"error": str(vector_error)}
    
    # Check CrewAI (basic import check)
    try:
        import crewai
        components["crewai"] = "healthy"
    except Exception:
        components["crewai"] = "unhealthy"
    
    overall_status = "healthy" if all(v == "healthy" for v in components.values()) else "degraded"
    
    return HealthCheckResponse(
        status=overall_status,
        components=components,
        details=component_details or None,
        timestamp=datetime.utcnow()
    )

