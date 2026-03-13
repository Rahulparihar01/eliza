"""
Talent Intelligence API Routes

FastAPI routes for AI-powered talent analysis using CrewAI agents.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import structlog
import uuid
import json
from datetime import datetime

from src.middleware.authorization import get_current_user
from src.core.auth_context import CurrentUserContext
from src.models import get_db
from src.tasks.talent_tasks import run_talent_analysis_task

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/talent", tags=["Talent Intelligence"])


# Request/Response Models
class TalentAnalysisRequest(BaseModel):
    """Request to start talent analysis"""
    job_description: Optional[str] = Field(None, description="Job description text")
    ideal_candidate_description: Optional[str] = Field(None, description="Natural language description of ideal candidate")
    manual_persona: Optional[dict] = Field(None, description="Manually defined persona")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_description": "We're hiring a Senior Backend Engineer...",
                "ideal_candidate_description": "Someone with 5+ years Python, strong AWS experience, has worked at high-growth startups, great communication skills"
            }
        }


class TalentAnalysisResponse(BaseModel):
    """Response with analysis ID and status"""
    analysis_id: str
    status: str = "processing"
    message: str = "Analysis started. Check progress at /api/talent/analysis/{analysis_id}/stream"


class TalentAnalysisResult(BaseModel):
    """Complete analysis results"""
    analysis_id: str
    customer_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    job_description: Optional[str] = None
    ideal_candidate_description: Optional[str] = None
    ideal_persona: Optional[dict] = None
    candidates: Optional[list] = None
    insights_report: Optional[dict] = None
    error: Optional[str] = None


# Routes
@router.post("/analyze", response_model=TalentAnalysisResponse)
async def start_talent_analysis(
    request: TalentAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start AI-powered talent analysis.
    
    Accepts:
    - Job description (text or uploaded)
    - Natural language ideal candidate description
    - Manual persona definition
    
    The job description and ideal candidate description are BOTH used as input
    to give the AI agents maximum context for finding the best candidates.
    """
    # Validate input
    if not request.job_description and not request.manual_persona:
        raise HTTPException(
            status_code=400,
            detail="Either job_description or manual_persona must be provided"
        )
    
    # Generate analysis ID
    analysis_id = str(uuid.uuid4())
    
    logger.info(
        "talent_analysis_requested",
        analysis_id=analysis_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        has_job_description=bool(request.job_description),
        has_ideal_candidate_description=bool(request.ideal_candidate_description),
        has_manual_persona=bool(request.manual_persona)
    )
    
    # Queue Celery task
    try:
        task = run_talent_analysis_task.delay(
            customer_id=current_user.customer_id,
            analysis_id=analysis_id,
            job_description=request.job_description,
            ideal_candidate_description=request.ideal_candidate_description,
            manual_persona=request.manual_persona,
            user_id=current_user.user_id
        )

        logger.info(
            "talent_analysis_queued",
            analysis_id=analysis_id,
            task_id=task.id
        )

        return TalentAnalysisResponse(
            analysis_id=analysis_id,
            status="processing",
            message=f"Analysis started. Monitor progress at /api/talent/analysis/{analysis_id}/stream"
        )
        
    except Exception as e:
        logger.error(
            "failed_to_queue_analysis",
            analysis_id=analysis_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start analysis: {str(e)}"
        )


@router.get("/analysis/{analysis_id}", response_model=TalentAnalysisResult)
async def get_talent_analysis(
    analysis_id: str,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get talent analysis results.
    
    Returns the complete analysis including:
    - Ideal persona
    - Ranked candidates with fit scores
    - Market insights and recommendations
    """
    from src.models.connector import TalentAnalysis
    
    # Fetch analysis
    analysis = db.query(TalentAnalysis).filter(
        TalentAnalysis.analysis_id == analysis_id,
        TalentAnalysis.customer_id == current_user.customer_id
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis {analysis_id} not found"
        )
    
    return TalentAnalysisResult(
        analysis_id=analysis.analysis_id,
        customer_id=analysis.customer_id,
        status=analysis.status,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        job_description=analysis.job_description,
        ideal_candidate_description=analysis.ideal_candidate_description,
        ideal_persona=analysis.ideal_persona,
        candidates=analysis.candidates,
        insights_report=analysis.insights_report,
        error=analysis.error_message
    )


@router.get("/analysis/{analysis_id}/stream")
async def stream_talent_analysis(
    analysis_id: str,
    token: str = Query(..., description="JWT access token (EventSource doesn't support headers)"),
    db: Session = Depends(get_db)
):
    """
    Stream real-time progress updates for talent analysis using Server-Sent Events (SSE).
    
    Events emitted:
    - analysis_started
    - stage_1_started through stage_7_completed
    - analysis_completed
    - analysis_failed
    
    Note: Token is passed as query param because EventSource doesn't support custom headers.
    """
    from src.models.connector import TalentAnalysis, TalentAnalysisEvent
    from src.services.auth_service import AuthService
    from fastapi import status
    import asyncio
    
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
        
        # Build user context (simplified for SSE)
        current_user = CurrentUserContext(
            user_id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            customer_id=user.customer_id,
            department=user.department,
            team=user.team,
            roles=[],  # Simplified for SSE
            permissions=[]  # Simplified for SSE
        )
        
    except Exception as e:
        logger.error("sse_auth_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication failed"
        )
    
    async def event_generator():
        """Generate SSE events from database polling"""
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'event_type': 'connected', 'analysis_id': analysis_id})}\n\n"
            
            last_event_id = None
            max_iterations = 300  # 5 minutes max (300 * 1 second)
            iteration = 0
            
            while iteration < max_iterations:
                # Query for new events
                query = db.query(TalentAnalysisEvent).filter(
                    TalentAnalysisEvent.analysis_id == analysis_id
                )
                
                if last_event_id:
                    query = query.filter(TalentAnalysisEvent.id > last_event_id)
                
                events = query.order_by(TalentAnalysisEvent.id.asc()).all()
                
                # Send new events
                for event in events:
                    event_data = {
                        'event_id': event.id,
                        'event_type': event.event_type,
                        'analysis_id': event.analysis_id,
                        'agent_name': event.agent_name,
                        'message': event.message,
                        'progress_percentage': event.progress_percentage,
                        'data': event.data,
                        'timestamp': event.timestamp.isoformat()
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    last_event_id = event.id
                
                # Check if analysis is complete
                analysis = db.query(TalentAnalysis).filter(
                    TalentAnalysis.analysis_id == analysis_id
                ).first()
                
                if analysis and analysis.status in ['completed', 'failed']:
                    # Send final event
                    final_event = {
                        'event_type': analysis.status,
                        'analysis_id': analysis_id,
                        'message': 'Analysis complete' if analysis.status == 'completed' else f'Analysis failed: {analysis.error_message}'
                    }
                    yield f"data: {json.dumps(final_event)}\n\n"
                    break
                
                # Wait before next poll
                await asyncio.sleep(1)
                iteration += 1
            
            # Timeout
            if iteration >= max_iterations:
                yield f"data: {json.dumps({'event_type': 'timeout', 'message': 'Stream timeout after 5 minutes'})}\n\n"
                
        except Exception as e:
            logger.error("sse_stream_error", error=str(e), exc_info=True)
            yield f"data: {json.dumps({'event_type': 'error', 'message': str(e)})}\n\n"
        finally:
            db.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/analyses")
async def list_talent_analyses(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all talent analyses for the current user's organization.
    """
    from src.models.connector import TalentAnalysis
    
    query = db.query(TalentAnalysis).filter(
        TalentAnalysis.customer_id == current_user.customer_id
    )
    
    if status:
        query = query.filter(TalentAnalysis.status == status)
    
    total = query.count()
    analyses = query.order_by(TalentAnalysis.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "analyses": [
            {
                "analysis_id": a.analysis_id,
                "status": a.status,
                "created_at": a.created_at,
                "completed_at": a.completed_at,
                "candidate_count": len(a.candidates) if a.candidates else 0
            }
            for a in analyses
        ]
    }

