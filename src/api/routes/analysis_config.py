"""
Analysis Configuration API Routes

Endpoints for managing saved talent analysis configurations.
Configurations are persisted to the database for reuse.
"""

from typing import List, Optional
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models import get_db
from src.middleware.authorization import AuthorizationMiddleware
from src.core.auth_context import CurrentUserContext
from src.core.logging import get_logger, LogCategory
from src.models.connector import TalentAnalysis, TalentAnalysisEvent
from src.models.analysis_config import AnalysisConfig

logger = get_logger(__name__, LogCategory.API)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/talent/analysis-configs", tags=["Analysis Configuration"])


# ============================================================================
# Pydantic Models
# ============================================================================

class AnalysisConfigCreate(BaseModel):
    """Request to create an analysis configuration."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    blueprint_id: Optional[int] = None
    company_dna_id: Optional[int] = None
    job_description: Optional[str] = None
    job_id: Optional[str] = None  # Job ID from ATS
    candidate_source_id: Optional[int] = None  # ATS connection ID
    department_ids: Optional[List[int]] = None
    candidate_source_mode: Optional[str] = Field(default="ats", description="Source mode: 'ats' or 'upload'")
    uploaded_resume_files: Optional[List[str]] = Field(default=None, description="List of uploaded resume filenames")
    ideal_candidate_details: Optional[str] = None
    market_search_limit: Optional[int] = Field(default=50, ge=1, le=100, description="Number of candidates to fetch from market search (1-100)")
    max_candidate_fetch: Optional[int] = Field(default=100, ge=1, le=500, description="Max candidates to fetch from ATS (1-500)")
    include_historical_candidates: Optional[bool] = Field(default=False, description="Include candidates from closed/historical job listings")
    historical_lookback_days: Optional[int] = Field(default=365, ge=30, le=1095, description="How far back to look for historical candidates (30-1095 days)")


class AnalysisConfigUpdate(BaseModel):
    """Request to update an analysis configuration."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    blueprint_id: Optional[int] = None
    company_dna_id: Optional[int] = None
    job_description: Optional[str] = None
    job_id: Optional[str] = None
    candidate_source_id: Optional[int] = None
    department_ids: Optional[List[int]] = None
    candidate_source_mode: Optional[str] = Field(None, description="Source mode: 'ats' or 'upload'")
    uploaded_resume_files: Optional[List[str]] = Field(None, description="List of uploaded resume filenames")
    ideal_candidate_details: Optional[str] = None
    market_search_limit: Optional[int] = Field(None, ge=1, le=100, description="Number of candidates to fetch from market search (1-100)")
    max_candidate_fetch: Optional[int] = Field(None, ge=1, le=500, description="Max candidates to fetch from ATS (1-500)")
    include_historical_candidates: Optional[bool] = Field(None, description="Include candidates from closed/historical job listings")
    historical_lookback_days: Optional[int] = Field(None, ge=30, le=1095, description="How far back to look for historical candidates (30-1095 days)")


class AnalysisConfigResponse(BaseModel):
    """Analysis configuration response."""
    id: int
    name: str
    description: Optional[str] = None
    blueprint_id: Optional[int] = None
    blueprint_name: Optional[str] = None
    company_dna_id: Optional[int] = None
    company_dna_name: Optional[str] = None
    job_description: Optional[str] = None
    selected_job_id: Optional[str] = None
    candidate_source_id: Optional[int] = None
    candidate_source_name: Optional[str] = None
    department_ids: Optional[List[int]] = None
    candidate_source_mode: Optional[str] = "ats"
    uploaded_resume_files: Optional[List[str]] = None
    ideal_candidate_details: Optional[str] = None
    market_search_limit: Optional[int] = 50
    max_candidate_fetch: Optional[int] = 100
    include_historical_candidates: Optional[bool] = False
    historical_lookback_days: Optional[int] = 365
    last_run_at: Optional[str] = None
    last_analysis_id: Optional[str] = None
    last_run_status: Optional[str] = None
    last_run_error: Optional[str] = None
    run_count: int = 0
    created_by_user_id: Optional[int] = None
    created_by_username: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class AnalysisConfigListResponse(BaseModel):
    """List of analysis configurations."""
    configs: List[AnalysisConfigResponse]
    total: int


class AnalysisRunStage(BaseModel):
    """Status of a single analysis stage."""
    stage: str
    status: str  # pending, running, completed, failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    message: Optional[str] = None


class AnalysisRunResponse(BaseModel):
    """Response for an analysis run with detailed status."""
    analysis_id: str
    config_id: int
    status: str  # pending, processing, completed, failed
    error_message: Optional[str] = None
    current_stage: Optional[str] = None
    progress_percentage: int = 0
    stages: List[AnalysisRunStage] = []
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    candidate_count: int = 0


class AnalysisRunListResponse(BaseModel):
    """List of analysis runs for a configuration."""
    runs: List[AnalysisRunResponse]
    total: int


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("", response_model=AnalysisConfigListResponse)
async def list_analysis_configs(
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List all analysis configurations for the customer."""
    configs = db.query(AnalysisConfig).filter(
        AnalysisConfig.customer_id == current_user.customer_id,
        AnalysisConfig.is_active == True
    ).order_by(desc(AnalysisConfig.created_at)).all()
    
    # Enrich with related names
    enriched = []
    for config in configs:
        enriched.append(_enrich_config(config, db))
    
    return AnalysisConfigListResponse(
        configs=enriched,
        total=len(enriched)
    )


@router.get("/{config_id}", response_model=AnalysisConfigResponse)
async def get_analysis_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get a specific analysis configuration."""
    config = db.query(AnalysisConfig).filter(
        AnalysisConfig.id == config_id,
        AnalysisConfig.customer_id == current_user.customer_id,
        AnalysisConfig.is_active == True
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    return _enrich_config(config, db)


@router.post("", response_model=AnalysisConfigResponse)
async def create_analysis_config(
    request: AnalysisConfigCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Create a new analysis configuration."""
    config = AnalysisConfig(
        customer_id=current_user.customer_id,
        created_by_user_id=current_user.user_id,
        name=request.name,
        description=request.description,
        blueprint_id=request.blueprint_id,
        company_dna_id=request.company_dna_id,
        job_description=request.job_description,
        selected_job_id=request.job_id,
        ats_connection_id=request.candidate_source_id,
        department_ids=request.department_ids,
        candidate_source_mode=request.candidate_source_mode or 'ats',
        uploaded_resume_files=request.uploaded_resume_files,
        ideal_candidate_details=request.ideal_candidate_details,
        market_search_limit=request.market_search_limit or 50,
        max_candidate_fetch=request.max_candidate_fetch or 100,
        include_historical_candidates=request.include_historical_candidates or False,
        historical_lookback_days=request.historical_lookback_days or 365,
        run_count=0,
        is_active=True
    )
    
    db.add(config)
    db.commit()
    db.refresh(config)
    
    logger.info(
        "analysis_config_created",
        config_id=config.id,
        name=config.name,
        customer_id=current_user.customer_id
    )
    
    return _enrich_config(config, db)


@router.put("/{config_id}", response_model=AnalysisConfigResponse)
async def update_analysis_config(
    config_id: int,
    request: AnalysisConfigUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Update an analysis configuration."""
    config = db.query(AnalysisConfig).filter(
        AnalysisConfig.id == config_id,
        AnalysisConfig.customer_id == current_user.customer_id,
        AnalysisConfig.is_active == True
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    # Update fields if provided
    if request.name is not None:
        config.name = request.name
    if request.description is not None:
        config.description = request.description
    if request.blueprint_id is not None:
        config.blueprint_id = request.blueprint_id
    if request.company_dna_id is not None:
        config.company_dna_id = request.company_dna_id
    if request.job_description is not None:
        config.job_description = request.job_description
    if request.job_id is not None:
        config.selected_job_id = request.job_id
    if request.candidate_source_id is not None:
        config.ats_connection_id = request.candidate_source_id
    if request.department_ids is not None:
        config.department_ids = request.department_ids
    if request.candidate_source_mode is not None:
        config.candidate_source_mode = request.candidate_source_mode
    if request.uploaded_resume_files is not None:
        config.uploaded_resume_files = request.uploaded_resume_files
    if request.ideal_candidate_details is not None:
        config.ideal_candidate_details = request.ideal_candidate_details
    if request.market_search_limit is not None:
        config.market_search_limit = request.market_search_limit
    if request.max_candidate_fetch is not None:
        config.max_candidate_fetch = request.max_candidate_fetch
    if request.include_historical_candidates is not None:
        config.include_historical_candidates = request.include_historical_candidates
    if request.historical_lookback_days is not None:
        config.historical_lookback_days = request.historical_lookback_days
    
    db.commit()
    db.refresh(config)
    
    logger.info(
        "analysis_config_updated",
        config_id=config_id,
        customer_id=current_user.customer_id
    )
    
    return _enrich_config(config, db)


@router.delete("/{config_id}")
async def delete_analysis_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Delete an analysis configuration (soft delete)."""
    config = db.query(AnalysisConfig).filter(
        AnalysisConfig.id == config_id,
        AnalysisConfig.customer_id == current_user.customer_id,
        AnalysisConfig.is_active == True
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    # Soft delete
    config.is_active = False
    db.commit()
    
    logger.info(
        "analysis_config_deleted",
        config_id=config_id,
        customer_id=current_user.customer_id
    )
    
    return {"status": "deleted", "id": config_id}


@router.post("/{config_id}/run")
async def run_analysis_from_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Run an analysis using a saved configuration.
    
    This endpoint queues a Celery task to run the analysis in a worker process,
    following the platform's best practice for long-running operations.
    """
    config = db.query(AnalysisConfig).filter(
        AnalysisConfig.id == config_id,
        AnalysisConfig.customer_id == current_user.customer_id,
        AnalysisConfig.is_active == True
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    try:
        # Generate unique analysis ID
        analysis_id = f"ml_ta_{uuid.uuid4().hex[:12]}"
        
        # Import the ML talent service to create the analysis record
        from src.services.ml_talent_service import MLTalentService
        
        ml_service = MLTalentService(db)
        
        # Role is not set here — it will be extracted from the job description
        # by the diagnostic agent during analysis execution.
        role = None
        
        # Fetch job description from Greenhouse if not already set
        job_description = config.job_description or ""
        if not job_description and config.selected_job_id and config.ats_connection_id:
            try:
                from src.services.ingestion.connector_service import ConnectorService
                from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
                import asyncio
                
                connector_service = ConnectorService(db)
                connector_config = connector_service.get_configuration_by_id(
                    config_id=config.ats_connection_id
                )
                
                if connector_config and connector_config.connector_type == "greenhouse":
                    credentials = connector_service.get_credentials(connector_config)
                    greenhouse = GreenhouseConnector(
                        credentials=credentials,
                        config=connector_config.sync_config or {},
                        customer_id=current_user.customer_id
                    )
                    
                    # Fetch job details including description
                    job_details = asyncio.get_event_loop().run_until_complete(
                        greenhouse.get_job_details(int(config.selected_job_id))
                    )
                    
                    if job_details and job_details.get("description"):
                        job_description = job_details["description"]
                        logger.info(
                            "fetched_job_description_from_greenhouse",
                            config_id=config_id,
                            job_id=config.selected_job_id,
                            description_length=len(job_description)
                        )
                    else:
                        logger.warning(
                            "no_job_description_found_in_greenhouse",
                            config_id=config_id,
                            job_id=config.selected_job_id
                        )
            except Exception as e:
                logger.warning(
                    "failed_to_fetch_job_description",
                    config_id=config_id,
                    job_id=config.selected_job_id,
                    error=str(e)
                )
        
        # Create the analysis record in the database
        ml_service.create_analysis(
            analysis_id=analysis_id,
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
            job_description=job_description,
            ideal_candidate_description=config.ideal_candidate_details or "",
            role=role
        )
        
        # Update config run stats
        config.last_run_at = datetime.now(timezone.utc)
        config.last_analysis_id = analysis_id
        config.run_count = (config.run_count or 0) + 1
        db.commit()
        
        # Queue Celery task for analysis
        # This runs in a separate worker process, following platform best practices
        from src.tasks.talent_tasks import run_orchestrator_analysis_task
        
        task = run_orchestrator_analysis_task.delay(
            analysis_id=analysis_id,
            customer_id=current_user.customer_id,
            user_id=current_user.user_id,
            job_description=job_description,  # Use the fetched job description
            ideal_candidate_description=config.ideal_candidate_details or "",
            role=role,
            ats_connection_id=config.ats_connection_id,
            department_ids=config.department_ids,
            blueprint_id=config.blueprint_id,
            company_dna_id=config.company_dna_id,
            market_search_limit=config.market_search_limit or 50,
            max_candidate_fetch=config.max_candidate_fetch or 100,
            include_historical_candidates=config.include_historical_candidates or False,
            historical_lookback_days=config.historical_lookback_days or 365,
            uploaded_resume_files=config.uploaded_resume_files if config.candidate_source_mode == 'upload' else None
        )
        
        logger.info(
            "analysis_run_triggered",
            config_id=config_id,
            analysis_id=analysis_id,
            celery_task_id=task.id,
            run_count=config.run_count,
            customer_id=current_user.customer_id
        )
        
        return {
            "status": "started",
            "config_id": config_id,
            "analysis_id": analysis_id,
            "message": f"Analysis started. Check status at /v1/ml-talent/analysis/{analysis_id}/status"
        }
        
    except Exception as e:
        logger.error(
            "analysis_run_failed",
            config_id=config_id,
            error=str(e),
            customer_id=current_user.customer_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start analysis: {str(e)}"
        )


@router.post("/{config_id}/cancel")
async def cancel_analysis(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Cancel a running analysis.
    
    This will mark the analysis as failed with a 'Cancelled by user' message
    and attempt to revoke any pending Celery tasks.
    """
    config = db.query(AnalysisConfig).filter(
        AnalysisConfig.id == config_id,
        AnalysisConfig.customer_id == current_user.customer_id,
        AnalysisConfig.is_active == True
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    if not config.last_analysis_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No analysis to cancel"
        )
    
    # Get the analysis
    analysis = db.query(TalentAnalysis).filter(
        TalentAnalysis.analysis_id == config.last_analysis_id
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Check if analysis is still running
    if analysis.status not in ('pending', 'processing'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analysis is not running (status: {analysis.status})"
        )
    
    try:
        # Update analysis status to cancelled
        analysis.status = 'cancelled'
        analysis.error_message = 'Cancelled by user'
        analysis.completed_at = datetime.now(timezone.utc)
        
        # Add a cancellation event
        cancel_event = TalentAnalysisEvent(
            analysis_id=config.last_analysis_id,
            event_type='cancelled',
            agent_name='System',
            message='Analysis cancelled by user',
            progress_percentage=0
        )
        db.add(cancel_event)
        db.commit()
        
        # Attempt to revoke Celery task (best effort)
        try:
            from src.celery_app import celery_app
            # Note: This won't stop a task that's already executing,
            # but will prevent queued tasks from starting
            celery_app.control.purge()
        except Exception as e:
            logger.warning(
                "celery_purge_failed",
                error=str(e),
                analysis_id=config.last_analysis_id
            )
        
        logger.info(
            "analysis_cancelled",
            config_id=config_id,
            analysis_id=config.last_analysis_id,
            customer_id=current_user.customer_id
        )
        
        return {
            "status": "cancelled",
            "config_id": config_id,
            "analysis_id": config.last_analysis_id,
            "message": "Analysis has been cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "analysis_cancel_failed",
            config_id=config_id,
            error=str(e),
            customer_id=current_user.customer_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel analysis: {str(e)}"
        )


@router.get("/{config_id}/runs", response_model=AnalysisRunListResponse)
async def get_config_runs(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get all analysis runs for a configuration with detailed status."""
    config = db.query(AnalysisConfig).filter(
        AnalysisConfig.id == config_id,
        AnalysisConfig.customer_id == current_user.customer_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    runs = []
    
    # Get the last analysis if available
    if config.last_analysis_id:
        analysis = db.query(TalentAnalysis).filter(
            TalentAnalysis.analysis_id == config.last_analysis_id
        ).first()
        
        if analysis:
            # Get events for this analysis
            events = db.query(TalentAnalysisEvent).filter(
                TalentAnalysisEvent.analysis_id == config.last_analysis_id
            ).order_by(TalentAnalysisEvent.timestamp.asc()).all()
            
            # Build stages from events
            stages = _build_stages_from_events(events)
            current_stage = _get_current_stage(stages)
            progress = _calculate_progress(stages, analysis.status)
            
            runs.append(AnalysisRunResponse(
                analysis_id=analysis.analysis_id,
                config_id=config_id,
                status=analysis.status,
                error_message=analysis.error_message,
                current_stage=current_stage,
                progress_percentage=progress,
                stages=stages,
                created_at=analysis.created_at.isoformat() if analysis.created_at else "",
                started_at=analysis.started_at.isoformat() if analysis.started_at else None,
                completed_at=analysis.completed_at.isoformat() if analysis.completed_at else None,
                candidate_count=analysis.candidate_count or 0
            ))
    
    return AnalysisRunListResponse(runs=runs, total=len(runs))


@router.get("/{config_id}/latest-run", response_model=Optional[AnalysisRunResponse])
async def get_latest_run(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get the latest analysis run for a configuration."""
    config = db.query(AnalysisConfig).filter(
        AnalysisConfig.id == config_id,
        AnalysisConfig.customer_id == current_user.customer_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    if not config.last_analysis_id:
        return None
    
    analysis = db.query(TalentAnalysis).filter(
        TalentAnalysis.analysis_id == config.last_analysis_id
    ).first()
    
    if not analysis:
        return None
    
    # Get events for this analysis
    events = db.query(TalentAnalysisEvent).filter(
        TalentAnalysisEvent.analysis_id == config.last_analysis_id
    ).order_by(TalentAnalysisEvent.timestamp.asc()).all()
    
    stages = _build_stages_from_events(events)
    current_stage = _get_current_stage(stages)
    progress = _calculate_progress(stages, analysis.status)
    
    return AnalysisRunResponse(
        analysis_id=analysis.analysis_id,
        config_id=config_id,
        status=analysis.status,
        error_message=analysis.error_message,
        current_stage=current_stage,
        progress_percentage=progress,
        stages=stages,
        created_at=analysis.created_at.isoformat() if analysis.created_at else "",
        started_at=analysis.started_at.isoformat() if analysis.started_at else None,
        completed_at=analysis.completed_at.isoformat() if analysis.completed_at else None,
        candidate_count=analysis.candidate_count or 0
    )


# ============================================================================
# Helper Functions
# ============================================================================

# Stage definitions for the analysis pipeline
ANALYSIS_STAGES = [
    {"id": "1", "name": "Baseline Build", "description": "Creating ideal candidate profile"},
    {"id": "2", "name": "Diagnostic Analysis", "description": "Analyzing job requirements"},
    {"id": "3", "name": "Resume Parsing", "description": "Processing candidate resumes"},
    {"id": "4", "name": "Applicant Scoring", "description": "Scoring internal candidates"},
    {"id": "5", "name": "Market Search", "description": "Searching external candidates"},
    {"id": "6", "name": "Market Scoring", "description": "Scoring external candidates"},
    {"id": "7", "name": "Synthesis", "description": "Generating final report"},
]


def _build_stages_from_events(events: List[TalentAnalysisEvent]) -> List[AnalysisRunStage]:
    """Build stage status list from analysis events."""
    stages = []
    stage_status = {}
    
    for event in events:
        event_type = event.event_type
        
        # Parse stage events
        if event_type.startswith("stage_") and "_started" in event_type:
            stage_num = event_type.replace("stage_", "").replace("_started", "")
            if stage_num not in stage_status:
                stage_status[stage_num] = {"status": "running", "started_at": event.timestamp}
            else:
                stage_status[stage_num]["status"] = "running"
                stage_status[stage_num]["started_at"] = event.timestamp
                
        elif event_type.startswith("stage_") and "_completed" in event_type:
            stage_num = event_type.replace("stage_", "").replace("_completed", "")
            if stage_num not in stage_status:
                stage_status[stage_num] = {"status": "completed", "completed_at": event.timestamp}
            else:
                stage_status[stage_num]["status"] = "completed"
                stage_status[stage_num]["completed_at"] = event.timestamp
                
        elif event_type == "analysis_error" or event_type == "analysis_failed":
            # Mark the current running stage as failed
            for snum, sdata in stage_status.items():
                if sdata.get("status") == "running":
                    sdata["status"] = "failed"
                    sdata["message"] = event.message
                    
        elif event_type == "cancelled":
            # Mark the current running stage as cancelled
            for snum, sdata in stage_status.items():
                if sdata.get("status") == "running":
                    sdata["status"] = "cancelled"
                    sdata["message"] = event.message or "Cancelled by user"
    
    # Build the stage list
    for stage_def in ANALYSIS_STAGES:
        stage_num = stage_def["id"]
        sdata = stage_status.get(stage_num, {})
        
        status = sdata.get("status", "pending")
        started = sdata.get("started_at")
        completed = sdata.get("completed_at")
        message = sdata.get("message")
        
        stages.append(AnalysisRunStage(
            stage=f"Stage {stage_num}: {stage_def['name']}",
            status=status,
            started_at=started.isoformat() if started else None,
            completed_at=completed.isoformat() if completed else None,
            message=message or stage_def["description"]
        ))
    
    return stages


def _get_current_stage(stages: List[AnalysisRunStage]) -> Optional[str]:
    """Get the name of the currently running or last completed stage."""
    current = None
    for stage in stages:
        if stage.status == "running":
            return stage.stage
        if stage.status == "completed":
            current = stage.stage
    return current


def _calculate_progress(stages: List[AnalysisRunStage], overall_status: str) -> int:
    """Calculate progress percentage based on completed stages."""
    if overall_status == "completed":
        return 100
    if overall_status == "failed":
        # Return progress up to failure
        pass
    
    total = len(stages)
    if total == 0:
        return 0
    
    completed = sum(1 for s in stages if s.status == "completed")
    running = sum(1 for s in stages if s.status == "running")
    
    # Each completed stage = full weight, running = half weight
    progress = (completed * 100 // total) + (running * 50 // total)
    return min(progress, 99)  # Cap at 99 until fully complete


def _enrich_config(config: AnalysisConfig, db: Session) -> AnalysisConfigResponse:
    """Enrich config with related entity names and latest run status."""
    blueprint_name = None
    dna_name = None
    source_name = None
    last_run_status = None
    last_run_error = None
    created_by_username = None
    
    # Get blueprint name
    if config.blueprint_id:
        try:
            from src.models.talent_config import CareerBlueprint
            blueprint = db.query(CareerBlueprint).filter(
                CareerBlueprint.id == config.blueprint_id
            ).first()
            if blueprint:
                blueprint_name = blueprint.name
        except Exception:
            pass
    
    # Get DNA name
    if config.company_dna_id:
        try:
            from src.models.talent_config import CompanyDNAProfile
            dna = db.query(CompanyDNAProfile).filter(
                CompanyDNAProfile.id == config.company_dna_id
            ).first()
            if dna:
                dna_name = f"{dna.company_name} - {dna.role_category}"
        except Exception:
            pass
    
    # Get source name (ATS connection)
    if config.ats_connection_id:
        try:
            from src.models.connector import ConnectorConfiguration
            source = db.query(ConnectorConfiguration).filter(
                ConnectorConfiguration.id == config.ats_connection_id
            ).first()
            if source:
                source_name = source.connector_name or source.connector_type
        except Exception:
            pass
    
    # Get latest run status
    if config.last_analysis_id:
        try:
            analysis = db.query(TalentAnalysis).filter(
                TalentAnalysis.analysis_id == config.last_analysis_id
            ).first()
            if analysis:
                last_run_status = analysis.status
                last_run_error = analysis.error_message
        except Exception:
            pass
    
    # Get created by username
    if config.created_by_user_id:
        try:
            from src.models.auth import User
            user = db.query(User).filter(
                User.id == config.created_by_user_id
            ).first()
            if user:
                # Use full name if available, otherwise username or email
                created_by_username = user.full_name or user.username or user.email or f"User {user.id}"
        except Exception:
            pass
    
    return AnalysisConfigResponse(
        id=config.id,
        name=config.name,
        description=config.description,
        blueprint_id=config.blueprint_id,
        blueprint_name=blueprint_name,
        company_dna_id=config.company_dna_id,
        company_dna_name=dna_name,
        job_description=config.job_description,
        selected_job_id=config.selected_job_id,
        candidate_source_id=config.ats_connection_id,
        candidate_source_name=source_name,
        department_ids=config.department_ids,
        candidate_source_mode=config.candidate_source_mode or 'ats',
        uploaded_resume_files=config.uploaded_resume_files,
        ideal_candidate_details=config.ideal_candidate_details,
        market_search_limit=config.market_search_limit or 50,
        max_candidate_fetch=config.max_candidate_fetch or 100,
        include_historical_candidates=config.include_historical_candidates or False,
        historical_lookback_days=config.historical_lookback_days or 365,
        last_run_at=config.last_run_at.isoformat() if config.last_run_at else None,
        last_analysis_id=config.last_analysis_id,
        last_run_status=last_run_status,
        last_run_error=last_run_error,
        run_count=config.run_count or 0,
        created_by_user_id=config.created_by_user_id,
        created_by_username=created_by_username,
        created_at=config.created_at.isoformat() if config.created_at else "",
        updated_at=config.updated_at.isoformat() if config.updated_at else "",
    )
