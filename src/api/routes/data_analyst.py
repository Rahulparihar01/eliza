"""
Data Analyst Agent API Routes
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import asyncio
import json
import uuid
from datetime import datetime, timezone

from src.models import get_db
from src.models.data_analyst import DataSourceType, DataAnalystQuestionStatus
from src.services.data_analyst_service import DataAnalystService
from src.middleware.authorization import AuthorizationMiddleware
from src.api.schemas.data_analyst import (
    QuestionSubmitRequest,
    QuestionSubmitResponse,
    QuestionResponse,
    QuestionListResponse,
    QuestionStatusResponse,
    AnalysisResultResponse,
    ClarificationRequest,
    ConfirmationRequest
)
from src.core.logging import get_logger
from src.services.auth_service import AuthService

logger = get_logger(__name__, component="data.analyst.api")
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/v1/data-analyst", tags=["Data Analyst"])


@router.post(
    "/questions",
    response_model=QuestionSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a data analyst question"
)
async def submit_question(
    request: QuestionSubmitRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:ask"))
):
    """
    Submit a new data analyst question.
    
    Uses CrewAI flow for intent detection, clarification, and processing.
    """
    service = DataAnalystService(db)
    
    # Create message (which will use smart intent detection)
    message = service.create_message(
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        data_source_type=request.data_source_type,
        question=request.question,
        conversation_id=request.conversation_id  # Optional conversation ID
    )
    
    # Emit immediate telemetry event: question submitted
    try:
        from src.models.data_analyst import DataAnalystTelemetryEventType
        service.add_telemetry_event(
            message_id=message.message_id,
            event_type=DataAnalystTelemetryEventType.INFO,  # Pass enum, not .value
            stage_name="Question Submission",
            user_message=f"Question submitted: {request.question[:100]}...",
            progress_percentage=0,
            data={"question_preview": request.question[:200]}
        )
        logger.info(f"Emitted question submitted event for message {message.message_id}")
    except Exception as e:
        logger.warning(f"Failed to emit question submitted event: {e}", exc_info=True)
    
    # Trigger async processing (CrewAI flow via Celery task)
    from src.tasks.data_analyst_tasks import process_data_analyst_message
    process_data_analyst_message.delay(message.message_id)
    
    # Emit telemetry event: processing queued
    try:
        service.add_telemetry_event(
            message_id=message.message_id,
            event_type=DataAnalystTelemetryEventType.PROCESSING_STARTED,  # Pass enum, not .value
            stage_name="Processing",
            user_message="Processing started - queued for analysis",
            progress_percentage=5
        )
        logger.info(f"Emitted processing started event for message {message.message_id}")
    except Exception as e:
        logger.warning(f"Failed to emit processing started event: {e}", exc_info=True)
    
    # Check if clarification or confirmation is needed
    clarification_needed = message.status == DataAnalystQuestionStatus.CLARIFICATION_NEEDED
    
    # Get conversation_id if message was created in a conversation
    conversation_id = message.conversation_id if hasattr(message, 'conversation_id') else None
    
    # Handle status - it might be an enum or a string
    status_value = message.status.value if hasattr(message.status, 'value') else str(message.status)
    
    return QuestionSubmitResponse(
        question_id=message.question_id,  # Backward compatibility
        status=status_value,
        message="Question submitted successfully" + (" - clarification needed" if clarification_needed else ""),
        conversation_id=conversation_id
    )


@router.get(
    "/questions/{question_id}",
    response_model=QuestionResponse,
    summary="Get question details"
)
async def get_question(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """Get question details."""
    service = DataAnalystService(db)
    question = service.get_question(question_id)
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Authorization check
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return QuestionResponse(
        question_id=question.question_id,
        user_id=question.user_id,
        customer_id=question.customer_id,
        data_source_type=question.data_source_type.value,
        original_question=question.original_question,
        status=question.status.value,
        generated_sql=question.generated_sql,
        sql_error=question.sql_error,
        result_data=question.result_data,
        result_metadata=question.result_metadata,
        created_at=question.created_at,
        updated_at=question.updated_at,
        completed_at=question.completed_at
    )


@router.get(
    "/questions/{question_id}/status",
    response_model=QuestionStatusResponse,
    summary="Get question status"
)
async def get_question_status(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """Get question processing status."""
    service = DataAnalystService(db)
    question = service.get_question(question_id)
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    progress_map = {
        DataAnalystQuestionStatus.PENDING: 0.0,
        DataAnalystQuestionStatus.PROCESSING: 50.0,
        DataAnalystQuestionStatus.COMPLETED: 100.0,
        DataAnalystQuestionStatus.FAILED: 0.0,
        DataAnalystQuestionStatus.CLARIFICATION_NEEDED: 25.0,
        DataAnalystQuestionStatus.INTENT_CONFIRMED: 75.0
    }
    
    # Handle status as string (from database) or enum
    status_str = question.status.value if hasattr(question.status, 'value') else str(question.status)
    try:
        status_enum = DataAnalystQuestionStatus(status_str)
    except ValueError:
        # If status string doesn't match enum, default to PENDING
        status_enum = DataAnalystQuestionStatus.PENDING
    
    return QuestionStatusResponse(
        question_id=question.question_id,
        status=status_str,
        progress_percentage=progress_map.get(status_enum, 0.0),
        error_message=question.sql_error
    )


@router.get(
    "/questions/{question_id}/stream",
    summary="Stream question status updates",
    description="Stream real-time status updates for a data analyst question using Server-Sent Events (SSE)."
)
async def stream_question_status(
    request: Request,
    question_id: str,
    token: str = Query(..., description="JWT access token (EventSource doesn't support headers)"),
    db: Session = Depends(get_db)
):
    """
    Stream real-time status updates for a data analyst question using Server-Sent Events.
    
    Events emitted:
    - connected: Initial connection established
    - status_update: Status changed (pending, processing, clarification_needed, completed, failed)
    - heartbeat: Keep-alive signal (every 15 seconds if idle)
    - completed: Processing completed successfully
    - failed: Processing failed
    
    Note: Token is passed as query param because EventSource doesn't support custom headers.
    """
    from src.models.data_analyst import DataAnalystMessage
    
    # Verify token and get user (EventSource can't send Authorization header)
    auth_service = AuthService()
    try:
        payload = await auth_service.verify_token(token)
        user_id = int(payload.get("sub"))
        user = await auth_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found"
            )
        
        # Permissions will be checked when accessing the question (via ownership check)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("SSE auth failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication failed"
        )
    
    async def event_generator():
        """Generate SSE events from status polling and telemetry."""
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'event_type': 'connected', 'question_id': question_id})}\n\n"
            
            poll_interval = 1  # Check every 1 second
            idle_cycles = 0
            heartbeat_interval = 15  # Send heartbeat every 15 seconds if idle
            max_iterations = 300  # 5 minutes max (300 * 1 second)
            iteration = 0
            last_status = None
            last_telemetry_id = 0
            
            # Get message to find message_id
            message = db.query(DataAnalystMessage).filter(
                (DataAnalystMessage.question_id == question_id) |
                (DataAnalystMessage.message_id == question_id)
            ).first()
            
            if not message:
                error_event = {
                    "event_id": f"error-{uuid.uuid4().hex}",
                    "event_type": "error",
                    "message": "Question not found",
                    "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                return
            
            message_id = message.message_id or message.question_id
            
            while iteration < max_iterations:
                if await request.is_disconnected():
                    logger.debug("SSE client disconnected", question_id=question_id)
                    break
                
                # Get telemetry events
                from src.services.data_analyst_service import DataAnalystService
                service = DataAnalystService(db)
                telemetry_events = service.get_telemetry_events(
                    message_id=message_id,
                    limit=100,
                    after_id=last_telemetry_id
                )
                
                # Stream new telemetry events
                for event in telemetry_events:
                    event_data = {
                        "event_id": f"telemetry-{event.telemetry_id}",
                        "telemetry_id": event.telemetry_id,
                        "event_type": event.event_type,
                        "agent_name": event.agent_name,
                        "tool_name": event.tool_name,
                        "stage_name": event.stage_name,
                        "message": event.message,
                        "user_message": event.user_message,
                        "progress_percentage": event.progress_percentage,
                        "data": event.data,
                        "error_details": event.error_details,
                        "duration_ms": event.duration_ms,
                        "timestamp": event.timestamp.isoformat() if event.timestamp else datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    last_telemetry_id = event.id
                    idle_cycles = 0
                
                # Get current question status
                question = db.query(DataAnalystMessage).filter(
                    (DataAnalystMessage.question_id == question_id) |
                    (DataAnalystMessage.message_id == question_id)
                ).first()
                
                if not question:
                    # Already handled above
                    break
                
                # Check authorization
                if question.user_id != user_id and not user.is_superuser:
                    error_event = {
                        "event_id": f"error-{uuid.uuid4().hex}",
                        "event_type": "error",
                        "message": "Not authorized",
                        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    break
                
                # Get status as string
                status_str = question.status.value if hasattr(question.status, 'value') else str(question.status)
                
                # Send status update if it changed
                if status_str != last_status:
                    progress_map = {
                        "pending": 0.0,
                        "processing": 50.0,
                        "clarification_needed": 25.0,
                        "intent_confirmed": 75.0,
                        "completed": 100.0,
                        "failed": 0.0
                    }
                    
                    status_event = {
                        "event_id": f"status-{uuid.uuid4().hex}",
                        "event_type": "status_update",
                        "question_id": question.question_id,
                        "message_id": question.message_id,
                        "status": status_str,
                        "progress_percentage": progress_map.get(status_str.lower(), 0.0),
                        "error_message": question.sql_error,
                        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(status_event)}\n\n"
                    last_status = status_str
                    idle_cycles = 0
                
                # Check if processing is complete
                if status_str in ["completed", "failed"]:
                    final_event = {
                        "event_id": f"terminal-{uuid.uuid4().hex}",
                        "event_type": "completed" if status_str == "completed" else "failed",
                        "status": status_str,
                        "message": "Processing completed" if status_str == "completed" else (question.sql_error or "Processing failed"),
                        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(final_event)}\n\n"
                    break
                
                # Send heartbeat if idle
                idle_cycles += 1
                if idle_cycles >= heartbeat_interval:
                    heartbeat_event = {
                        "event_id": f"heartbeat-{uuid.uuid4().hex}",
                        "event_type": "heartbeat",
                        "status": status_str,
                        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(heartbeat_event)}\n\n"
                    idle_cycles = 0
                
                iteration += 1
                await asyncio.sleep(poll_interval)
                
        except Exception as e:
            logger.error("SSE stream error", error=str(e), question_id=question_id, exc_info=True)
            error_event = {
                "event_id": f"error-{uuid.uuid4().hex}",
                "event_type": "error",
                "message": f"Stream error: {str(e)}",
                "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
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
    summary="Get analysis result"
)
async def get_analysis_result(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """Get analysis result."""
    service = DataAnalystService(db)
    question = service.get_question(question_id)
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if question.status != DataAnalystQuestionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Question not yet completed")
    
    return AnalysisResultResponse(
        question_id=question.question_id,
        result_data=question.result_data or {},
        result_metadata=question.result_metadata or {}
    )


@router.get(
    "/questions",
    response_model=QuestionListResponse,
    summary="List questions"
)
async def list_questions(
    data_source_type: Optional[DataSourceType] = Query(None),
    conversation_id: Optional[str] = Query(None, description="Filter by conversation ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """List questions with pagination, optionally filtered by conversation."""
    service = DataAnalystService(db)
    
    offset = (page - 1) * page_size
    questions, total = service.list_questions(
        user_id=current_user.user_id if not current_user.is_superuser else None,
        customer_id=current_user.customer_id,
        data_source_type=data_source_type,
        conversation_id=conversation_id,
        limit=page_size,
        offset=offset
    )
    
    return QuestionListResponse(
        questions=[_serialize_question(q) for q in questions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.post(
    "/questions/{question_id}/clarify",
    response_model=QuestionResponse,
    summary="Provide clarification response"
)
async def clarify_question(
    question_id: str,
    request: ClarificationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:ask"))
):
    """
    Provide clarification response for a question that needs clarification.
    
    This creates a NEW question that combines:
    - The original question context
    - The clarification prompt that was asked
    - The user's clarification response
    
    The original question is marked as 'clarified' and the new question is processed.
    """
    service = DataAnalystService(db)
    
    # Get original message (using question_id for backward compatibility)
    from src.models.data_analyst import DataAnalystMessage
    original_message = db.query(DataAnalystMessage).filter(
        (DataAnalystMessage.question_id == question_id) | 
        (DataAnalystMessage.message_id == question_id)
    ).first()
    
    if not original_message:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if original_message.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if original_message.status != DataAnalystQuestionStatus.CLARIFICATION_NEEDED.value:
        raise HTTPException(status_code=400, detail="Question does not need clarification")
    
    # Build the clarified question by combining original + clarification context
    clarified_question = f"""Original Question: {original_message.original_question}

Clarification Requested: {original_message.clarification_prompt}

User's Clarification: {request.clarification_response}

Based on the above context, please answer the user's question with the provided clarification."""
    
    # Mark original message as 'clarified' (not 'completed', just indicates it was handled)
    original_message.status = "clarified"
    original_message.clarified_question = request.clarification_response
    db.commit()
    
    # Create a NEW message with the combined context
    import uuid
    new_message_id = str(uuid.uuid4())
    new_question_id = str(uuid.uuid4())
    
    new_message = DataAnalystMessage(
        message_id=new_message_id,
        question_id=new_question_id,
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        data_source_type=original_message.data_source_type,
        original_question=clarified_question,
        conversation_id=original_message.conversation_id,
        status="pending",
        # Reference to original question for tracking
        parent_message_id=original_message.message_id
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    
    logger.info(
        "clarification_created_new_question",
        original_question_id=question_id,
        new_question_id=new_question_id,
        clarification_response=request.clarification_response[:100]
    )
    
    # Trigger processing for the NEW message
    from src.tasks.data_analyst_tasks import process_data_analyst_message
    process_data_analyst_message.delay(new_message.message_id)
    
    return QuestionResponse(
        question_id=new_message.question_id,
        user_id=new_message.user_id,
        customer_id=new_message.customer_id,
        data_source_type=new_message.data_source_type.value if hasattr(new_message.data_source_type, 'value') else str(new_message.data_source_type),
        original_question=new_message.original_question,
        status=new_message.status,
        generated_sql=None,
        sql_error=None,
        result_data=None,
        result_metadata=None,
        created_at=new_message.created_at,
        updated_at=new_message.updated_at,
        completed_at=None
    )


@router.post(
    "/questions/{question_id}/confirm",
    response_model=QuestionResponse,
    summary="Confirm or correct intent"
)
async def confirm_intent(
    question_id: str,
    request: ConfirmationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:ask"))
):
    """
    Confirm or correct the detected intent for a question.
    
    If user confirms, processing continues.
    If user provides corrections, the question is updated and reprocessed.
    """
    service = DataAnalystService(db)
    
    # Get message
    from src.models.data_analyst import DataAnalystMessage
    message = db.query(DataAnalystMessage).filter(
        (DataAnalystMessage.question_id == question_id) | 
        (DataAnalystMessage.message_id == question_id)
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if message.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Parse confirmation response
    response_lower = request.confirmation_response.lower().strip()
    confirmed = any(word in response_lower for word in ["yes", "y", "correct", "confirm", "proceed"])
    
    # Update message with confirmation
    if confirmed:
        message.intent_confirmed = True
        if message.status == DataAnalystQuestionStatus.INTENT_CONFIRMED.value:
            message.status = DataAnalystQuestionStatus.PENDING.value  # Ready to process
    else:
        # User provided corrections - treat as clarification
        message.clarification_response = request.confirmation_response
        message.intent_confirmed = False
    
    db.commit()
    
    # Re-trigger processing
    from src.tasks.data_analyst_tasks import process_data_analyst_message
    process_data_analyst_message.delay(message.message_id)
    
    return QuestionResponse(
        question_id=message.question_id,
        user_id=message.user_id,
        customer_id=message.customer_id,
        data_source_type=message.data_source_type.value,
        original_question=message.original_question,
        status=message.status.value if hasattr(message.status, 'value') else str(message.status),
        generated_sql=message.generated_sql,
        sql_error=message.sql_error,
        result_data=message.result_data,
        result_metadata=message.result_metadata,
        created_at=message.created_at,
        updated_at=message.updated_at,
        completed_at=message.completed_at
    )


def _serialize_question(question):
    """Serialize question to dict."""
    return {
        "question_id": question.question_id,
        "user_id": question.user_id,
        "customer_id": question.customer_id,
        "data_source_type": question.data_source_type.value,
        "original_question": question.original_question,
        "status": question.status.value if hasattr(question.status, 'value') else str(question.status),
        "sql_error": question.sql_error,
        "generated_sql": question.generated_sql,
        "result_data": question.result_data,
        "result_metadata": question.result_metadata,
        "clarification_prompt": getattr(question, 'clarification_prompt', None),
        "clarified_question": getattr(question, 'clarified_question', None),
        "created_at": question.created_at,
        "completed_at": question.completed_at
    }


# ==================================================================================
# CONVERSATION ENDPOINTS
# ==================================================================================

from src.services.conversation_service import ConversationService
from src.api.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
    ConversationUpdateTitle,
    ConversationAddParticipant
)
from src.models.data_analyst import ConversationType


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation"
)
async def create_conversation(
    request: ConversationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:ask"))
):
    """
    Create a new conversation (user or group).
    
    User conversations are private to the creator.
    Group conversations can have multiple participants.
    """
    service = ConversationService(db)
    
    conversation = service.create_conversation(
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        data_source_type=request.data_source_type,
        conversation_type=request.conversation_type,
        title=request.title,
        participant_ids=request.participant_ids
    )
    
    # Get message count and latest message
    message_count = service.get_message_count(conversation.conversation_id)
    latest_message_obj = service.get_latest_message(conversation.conversation_id)
    latest_message = latest_message_obj.original_question[:100] if latest_message_obj else None
    
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        customer_id=conversation.customer_id,
        data_source_type=conversation.data_source_type.value,
        conversation_type=conversation.conversation_type,
        is_shared=conversation.is_shared,
        participants=conversation.participants,
        title=conversation.title,
        status=conversation.status,
        message_count=message_count,
        latest_message=latest_message,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        last_activity_at=conversation.last_activity_at
    )


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List conversations"
)
async def list_conversations(
    data_source_type: Optional[DataSourceType] = Query(None),
    conversation_type: Optional[ConversationType] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """
    List conversations accessible to the current user.
    
    Returns conversations where user is owner or participant,
    ordered by last activity.
    """
    service = ConversationService(db)
    
    conversations, total = service.list_conversations(
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        data_source_type=data_source_type,
        conversation_type=conversation_type,
        page=page,
        page_size=page_size
    )
    
    # Enrich with message count and latest message
    conversation_responses = []
    for conv in conversations:
        message_count = service.get_message_count(conv.conversation_id)
        latest_message_obj = service.get_latest_message(conv.conversation_id)
        latest_message = latest_message_obj.original_question[:100] if latest_message_obj else None
        
        conversation_responses.append(ConversationResponse(
            conversation_id=conv.conversation_id,
            user_id=conv.user_id,
            customer_id=conv.customer_id,
            data_source_type=conv.data_source_type.value,
            conversation_type=conv.conversation_type,
            is_shared=conv.is_shared,
            participants=conv.participants,
            title=conv.title,
            status=conv.status,
            message_count=message_count,
            latest_message=latest_message,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            last_activity_at=conv.last_activity_at
        ))
    
    return ConversationListResponse(
        conversations=conversation_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation details"
)
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:read"))
):
    """Get conversation details."""
    service = ConversationService(db)
    
    conversation = service.get_conversation(conversation_id, current_user.user_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied"
        )
    
    # Get message count and latest message
    message_count = service.get_message_count(conversation.conversation_id)
    latest_message_obj = service.get_latest_message(conversation.conversation_id)
    latest_message = latest_message_obj.original_question[:100] if latest_message_obj else None
    
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        customer_id=conversation.customer_id,
        data_source_type=conversation.data_source_type.value,
        conversation_type=conversation.conversation_type,
        is_shared=conversation.is_shared,
        participants=conversation.participants,
        title=conversation.title,
        status=conversation.status,
        message_count=message_count,
        latest_message=latest_message,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        last_activity_at=conversation.last_activity_at
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation"
)
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:ask"))
):
    """Delete a conversation (soft delete). Only owner can delete."""
    service = ConversationService(db)
    
    success = service.delete_conversation(conversation_id, current_user.user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or you are not the owner"
        )
    
    return None


@router.patch(
    "/conversations/{conversation_id}/title",
    response_model=ConversationResponse,
    summary="Update conversation title"
)
async def update_conversation_title(
    conversation_id: str,
    request: ConversationUpdateTitle,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:ask"))
):
    """Update conversation title. Only owner can update title."""
    service = ConversationService(db)
    
    conversation = service.update_conversation_title(
        conversation_id, current_user.user_id, request.title
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or you are not the owner"
        )
    
    # Get message count and latest message
    message_count = service.get_message_count(conversation.conversation_id)
    latest_message_obj = service.get_latest_message(conversation.conversation_id)
    latest_message = latest_message_obj.original_question[:100] if latest_message_obj else None
    
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        customer_id=conversation.customer_id,
        data_source_type=conversation.data_source_type.value,
        conversation_type=conversation.conversation_type,
        is_shared=conversation.is_shared,
        participants=conversation.participants,
        title=conversation.title,
        status=conversation.status,
        message_count=message_count,
        latest_message=latest_message,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        last_activity_at=conversation.last_activity_at
    )


@router.post(
    "/conversations/{conversation_id}/participants",
    response_model=ConversationResponse,
    summary="Add participant to group conversation"
)
async def add_conversation_participant(
    conversation_id: str,
    request: ConversationAddParticipant,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("assistant:questions:ask"))
):
    """Add a participant to a group conversation. Only owner can add participants."""
    service = ConversationService(db)
    
    conversation = service.add_participant(
        conversation_id, current_user.user_id, request.user_id
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found, you are not the owner, or not a group conversation"
        )
    
    # Get message count and latest message
    message_count = service.get_message_count(conversation.conversation_id)
    latest_message_obj = service.get_latest_message(conversation.conversation_id)
    latest_message = latest_message_obj.original_question[:100] if latest_message_obj else None
    
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        user_id=conversation.user_id,
        customer_id=conversation.customer_id,
        data_source_type=conversation.data_source_type.value,
        conversation_type=conversation.conversation_type,
        is_shared=conversation.is_shared,
        participants=conversation.participants,
        title=conversation.title,
        status=conversation.status,
        message_count=message_count,
        latest_message=latest_message,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        last_activity_at=conversation.last_activity_at
    )

