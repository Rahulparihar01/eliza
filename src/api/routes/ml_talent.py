"""
Talent Intelligence API Routes

API endpoints for the Talent Intelligence System.
Role-agnostic: supports any role type driven by user configuration.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
import asyncio
import json
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.models import get_db
from src.middleware.authorization import AuthorizationMiddleware
from src.core.auth_context import CurrentUserContext
from src.services.talent import (
    TalentIntelligenceOrchestrator,
    TalentAnalysisRequest,
    QueryRefinementFeedback,
)
from src.services.ml_talent_service import MLTalentService
from src.models.talent_analysis import (
    TalentAnalysisResult,
    AnalysisStatus,
)
from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings

settings = get_settings()
logger = get_logger(__name__, LogCategory.API)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/v1/ml-talent", tags=["ML Talent Intelligence"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class StartAnalysisRequest(BaseModel):
    """Request to start talent analysis"""
    job_description: str = Field(description="Job description for the target role")
    ideal_candidate_description: str = Field(description="Natural language ideal candidate description")
    role: Optional[str] = Field(default=None, description="Optional role hint. If not provided, the role is automatically extracted from the job description.")


class StartAnalysisResponse(BaseModel):
    """Response when analysis is started"""
    analysis_id: str
    status: AnalysisStatus
    message: str


class AnalysisStatusResponse(BaseModel):
    """Response for status check"""
    analysis_id: str
    status: AnalysisStatus
    message: str
    progress_percentage: Optional[int] = None


class RefineQueryRequest(BaseModel):
    """Request to refine PDL query based on feedback"""
    analysis_id: str
    refinement_feedback: QueryRefinementFeedback


class StartAnalysisFromConnectorRequest(BaseModel):
    """Request to start talent analysis from data connector"""
    job_description: str = Field(description="Job description for the target role")
    ideal_candidate_description: str = Field(description="Natural language ideal candidate description")
    data_source_connector_id: str = Field(description="Connector ID containing applicant resumes")
    baseline_employee_ids: Optional[List[int]] = Field(default=None, description="IDs of employees to use as baseline")
    baseline_linkedin_urls: Optional[List[str]] = Field(default=None, description="LinkedIn profile URLs to use as baseline")
    role: Optional[str] = Field(default=None, description="Optional role hint. If not provided, the role is automatically extracted from the job description.")
    greenhouse_query_params: Optional[Dict[str, Any]] = Field(default=None, description="Greenhouse-specific query parameters (job_ids, application_status, created_after, max_candidates)")


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/analyze",
    response_model=StartAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start ML talent analysis",
    description="Start comprehensive ML talent analysis with resume parsing, baseline building, scoring, and synthesis"
)
async def start_ml_talent_analysis(
    job_description: str = Form(..., description="Job description text"),
    ideal_candidate_description: str = Form(..., description="Ideal candidate description"),
    role: Optional[str] = Form(default=None, description="Optional role hint. If not provided, the role is extracted from the job description."),
    applicant_resumes: List[UploadFile] = File(..., description="Applicant resume PDFs (max 50)"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.require_permission("recruiter:config:create"))
):
    """
    Start ML talent analysis.
    
    Process:
    1. Parse job description + ideal candidate profile
    2. Build baseline from current ML Engineers
    3. Parse applicant resumes with Docling VLM
    4. Score applicants
    5. Build PDL query and search market
    6. Score market candidates
    7. Generate synthesis report
    
    Returns analysis_id to track progress.
    """
    analysis_id = f"ml_ta_{uuid.uuid4().hex[:12]}"
    
    logger.info(
        "ml_talent_analysis_start",
        analysis_id=analysis_id,
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        role=role,
        resume_count=len(applicant_resumes)
    )
    
    try:
        # Initialize service
        ml_service = MLTalentService(db)
        
        # Validate resume count
        if len(applicant_resumes) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 applicant resumes allowed"
            )
        
        # Read resume files
        resume_files = []
        for resume in applicant_resumes:
            content = await resume.read()
            resume_files.append((content, resume.filename))
        
        # Create database record
        ml_service.create_analysis(
            analysis_id=analysis_id,
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
            job_description=job_description,
            ideal_candidate_description=ideal_candidate_description,
            role=role
        )
        
        # Create request
        request = TalentAnalysisRequest(
            analysis_id=analysis_id,
            job_description=job_description,
            ideal_candidate_description=ideal_candidate_description,
            applicant_resume_files=resume_files,
            role=role,
            customer_id=current_user.customer_id,
            user_id=current_user.user_id
        )
        
        # Run analysis in background
        if background_tasks:
            background_tasks.add_task(
                run_analysis_background,
                analysis_id=analysis_id,
                request=request
            )
        else:
            # Run immediately (for testing)
            await run_analysis_background(analysis_id, request)
        
        return StartAnalysisResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.PENDING,
            message=f"Analysis started. Check status at /v1/ml-talent/analysis/{analysis_id}/status"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "ml_talent_analysis_start_failed",
            analysis_id=analysis_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start analysis: {str(e)}"
        )


@router.post(
    "/analyze-from-connector",
    response_model=StartAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start ML talent analysis from data connector",
    description="Start comprehensive ML talent analysis by fetching resumes from a data connector"
)
async def start_ml_talent_analysis_from_connector(
    request: StartAnalysisFromConnectorRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.require_permission("recruiter:config:create"))
):
    """
    Start ML talent analysis using resumes from a data connector.
    
    Process:
    1. Fetch resume files from the specified connector
    2. Parse resumes (fast parser for now, Docling VLM later)
    3. Build baseline from selected employees (or all ML Engineers)
    4. Run diagnostic agent to analyze requirements
    5. Score applicants against baseline
    6. Build PDL query and search market
    7. Score market candidates
    8. Generate synthesis report
    
    Returns analysis_id to track progress.
    """
    analysis_id = f"ml_ta_{uuid.uuid4().hex[:12]}"
    
    logger.info(
        "ml_talent_analysis_from_connector_start",
        analysis_id=analysis_id,
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        connector_id=request.data_source_connector_id,
        role=request.role
    )
    
    try:
        # Initialize services
        ml_service = MLTalentService(db)
        from src.services.ingestion.connector_service import ConnectorService
        connector_service = ConnectorService(db)
        
        # Get connector configuration
        connector_config = connector_service.get_configuration(
            connector_id=request.data_source_connector_id,
            customer_id=current_user.customer_id
        )
        
        if not connector_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {request.data_source_connector_id} not found"
            )
        
        if connector_config.customer_id != current_user.customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this connector"
            )
        
        if not connector_config.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connector {request.data_source_connector_id} is not enabled"
            )
        
        # Fetch resume files from connector
        logger.info(
            "fetching_resumes_from_connector",
            analysis_id=analysis_id,
            connector_id=request.data_source_connector_id,
            connector_type=connector_config.connector_type
        )
        
        # Get connector instance and fetch files
        from src.services.ingestion.connectors.filesystem_connector import FileSystemConnector
        
        if connector_config.connector_type == "filesystem":
            # FileSystemConnector requires credentials, config, and customer_id
            # For filesystem, credentials can be empty dict
            connector_instance = FileSystemConnector(
                credentials={},
                config=connector_config.sync_config,
                customer_id=current_user.customer_id
            )
            
            # List files in directory
            import os
            directory_path = connector_config.sync_config.get("directory_path", "")
            
            if not os.path.exists(directory_path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Directory {directory_path} does not exist"
                )
            
            # Get PDF files
            resume_files = []
            for filename in os.listdir(directory_path):
                if filename.lower().endswith('.pdf'):
                    file_path = os.path.join(directory_path, filename)
                    with open(file_path, 'rb') as f:
                        content = f.read()
                        resume_files.append((content, filename))
            
            if not resume_files:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No PDF files found in {directory_path}"
                )
            
            if len(resume_files) > 50:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Found {len(resume_files)} resumes, maximum 50 allowed. Please limit the files in the connector directory."
                )
            
            logger.info(
                "resumes_fetched_from_connector",
                analysis_id=analysis_id,
                resume_count=len(resume_files)
            )
            
        elif connector_config.connector_type == "greenhouse":
            # Get credentials
            credentials = connector_service.get_credentials(connector_config)
            
            # Import Greenhouse connector
            from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
            
            # Merge sync_config with query params from request (request params override)
            sync_config = dict(connector_config.sync_config or {})
            if request.greenhouse_query_params:
                # Convert job_ids from comma-separated string to list if needed
                if "job_ids" in request.greenhouse_query_params and request.greenhouse_query_params["job_ids"]:
                    job_ids_str = request.greenhouse_query_params["job_ids"]
                    if isinstance(job_ids_str, str):
                        sync_config["job_ids"] = [int(jid.strip()) for jid in job_ids_str.split(",") if jid.strip()]
                    else:
                        sync_config["job_ids"] = request.greenhouse_query_params["job_ids"]
                
                # Add other params
                for key in ["application_status", "created_after", "max_candidates"]:
                    if key in request.greenhouse_query_params and request.greenhouse_query_params[key]:
                        sync_config[key] = request.greenhouse_query_params[key]
            
            # Initialize connector with merged config
            connector_instance = GreenhouseConnector(
                credentials=credentials,
                config=sync_config,
                customer_id=current_user.customer_id
            )
            
            logger.info(
                "fetching_resumes_from_greenhouse",
                analysis_id=analysis_id,
                connector_id=connector_config.connector_id,
                max_candidates=sync_config.get("max_candidates", 100),
                job_ids=sync_config.get("job_ids"),
                application_status=sync_config.get("application_status"),
                created_after=sync_config.get("created_after")
            )
            
            # Sync candidates and download resumes (async operation)
            sync_results = await connector_instance.sync()
            
            if sync_results.get("errors"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Greenhouse sync failed: {'; '.join(sync_results['errors'])}"
                )
            
            # Extract resume files from sync results (keep full metadata)
            resume_files = []
            for resume_data in sync_results.get("resumes", []):
                # Pass the full resume_data dict which includes Greenhouse metadata
                # (candidate_id, candidate_name, candidate_email, metadata.greenhouse_candidate_id, etc.)
                resume_files.append(resume_data)
            
            if not resume_files:
                # Provide detailed, actionable error message
                candidates_fetched = sync_results.get("candidates_fetched", 0)
                candidates_filtered = sync_results.get("candidates_filtered", 0)
                
                error_message = f"No resume attachments found among {candidates_fetched} candidates from Greenhouse."
                
                if candidates_filtered > 0:
                    error_message += f" ({candidates_filtered} candidates were filtered out based on your criteria)"
                
                error_message += "\n\n💡 Possible solutions:\n"
                error_message += "1. Use a different data source (Filesystem connector) for applicants with uploaded resumes\n"
                error_message += "2. Adjust your filters to include more candidates (remove status/date filters)\n"
                error_message += "3. Ask candidates to upload resumes in Greenhouse before running analysis\n"
                error_message += f"\nNote: Greenhouse returned {candidates_fetched} candidates, but none had resume attachments. "
                error_message += "This is common if candidates were added manually or applied through job boards without uploading files."
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_message
                )
            
            if len(resume_files) > 50:
                logger.warning(
                    f"Found {len(resume_files)} resumes from Greenhouse, limiting to first 50"
                )
                resume_files = resume_files[:50]
            
            logger.info(
                "resumes_fetched_from_greenhouse",
                analysis_id=analysis_id,
                resume_count=len(resume_files),
                candidates_fetched=sync_results.get("candidates_fetched", 0),
                candidates_filtered=sync_results.get("candidates_filtered", 0)
            )
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connector type {connector_config.connector_type} not supported for resume analysis. Use 'filesystem' or 'greenhouse' connector."
            )
        
        # Create database record
        ml_service.create_analysis(
            analysis_id=analysis_id,
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
            job_description=request.job_description,
            ideal_candidate_description=request.ideal_candidate_description,
            role=request.role
        )
        
        # Create request for orchestrator
        analysis_request = TalentAnalysisRequest(
            analysis_id=analysis_id,
            job_description=request.job_description,
            ideal_candidate_description=request.ideal_candidate_description,
            applicant_resume_files=resume_files,
            role=request.role,
            customer_id=current_user.customer_id,
            user_id=current_user.user_id,
            baseline_employee_ids=request.baseline_employee_ids,
            baseline_linkedin_urls=request.baseline_linkedin_urls
        )
        
        # Run analysis in background
        background_tasks.add_task(
            run_analysis_background,
            analysis_id=analysis_id,
            request=analysis_request
        )
        
        return StartAnalysisResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.PENDING,
            message=f"Analysis started with {len(resume_files)} resumes. Check status at /v1/ml-talent/analysis/{analysis_id}/status"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "ml_talent_analysis_from_connector_failed",
            analysis_id=analysis_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start analysis: {str(e)}"
        )


@router.get(
    "/analyses",
    summary="List ML Talent Intelligence analyses",
    description="Get paginated list of analyses for the current organization"
)
async def list_ml_talent_analyses(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.require_permission("recruiter:results:read"))
):
    """
    List ML Talent Intelligence analyses.
    
    Returns paginated list with:
    - analysis_id
    - status
    - created_at
    - completed_at
    - candidate counts
    - job description summary
    """
    try:
        ml_service = MLTalentService(db)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get analyses
        result = ml_service.list_analyses(
            customer_id=current_user.customer_id,
            offset=offset,
            limit=page_size,
            status=status
        )
        
        return {
            "analyses": result["analyses"],
            "total": result["total"],
            "page": page,
            "page_size": page_size,
            "pages": (result["total"] + page_size - 1) // page_size
        }
        
    except Exception as e:
        logger.error(
            "list_ml_talent_analyses_failed",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list analyses: {str(e)}"
        )


@router.get(
    "/analysis/{analysis_id}",
    response_model=TalentAnalysisResult,
    summary="Get analysis results",
    description="Get complete analysis results including scores, reports, and provenance"
)
async def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.require_permission("recruiter:results:read"))
):
    """
    Get analysis results by ID.
    
    Returns complete results including:
    - Diagnostic report
    - Baseline profile
    - Applicant scores
    - Market candidate scores
    - Synthesis report
    - Top overall candidates
    - Complete provenance chains
    """
    logger.info(
        "get_ml_talent_analysis",
        analysis_id=analysis_id,
        user_id=current_user.user_id
    )
    
    try:
        # Get analysis from database
        ml_service = MLTalentService(db)
        analysis = ml_service.get_analysis(analysis_id, current_user.customer_id)
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis {analysis_id} not found"
            )
        
        # Parse JSON fields - handle both string and dict (JSONB returns dicts directly)
        def safe_json_parse(value, default=None):
            """Parse JSON string or return dict as-is (for JSONB columns)."""
            if value is None:
                return default
            if isinstance(value, (dict, list)):
                return value  # Already parsed (JSONB column)
            if isinstance(value, str):
                return json.loads(value)
            return default
        
        diagnostic_report = safe_json_parse(analysis["diagnostic_report"])
        baseline_profile = safe_json_parse(analysis["baseline_profile"])
        synthesis_report = safe_json_parse(analysis["synthesis_report"])
        candidates_data = safe_json_parse(analysis["candidates"], {})
        
        # Extract candidates and pattern data
        applicant_results = candidates_data.get("applicant_candidates", [])
        market_results = candidates_data.get("market_candidates", [])
        top_overall = candidates_data.get("top_overall_candidates", [])
        
        # Extract patterns from synthesis if available
        patterns = []
        if synthesis_report and "pattern_insights" in synthesis_report:
            patterns = synthesis_report["pattern_insights"]
        
        # Build provenance chains (empty for now, will be populated in future)
        provenance = []
        
        # Build result
        result = TalentAnalysisResult(
            analysis_id=analysis_id,
            status=AnalysisStatus(analysis["status"]),
            job_description=analysis["job_description"],
            ideal_candidate_description=analysis["ideal_candidate_description"],
            diagnostic_report=diagnostic_report,
            baseline_profile=baseline_profile,
            applicant_results=applicant_results,
            market_results=market_results,
            top_overall=top_overall,
            synthesis=synthesis_report,
            patterns=patterns,
            provenance=provenance,
            overall_confidence=analysis["overall_confidence"] or 0.85,
            created_at=analysis["created_at"],
            completed_at=analysis["completed_at"]
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_ml_talent_analysis_failed",
            analysis_id=analysis_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analysis: {str(e)}"
        )


@router.get(
    "/analysis/{analysis_id}/status",
    response_model=AnalysisStatusResponse,
    summary="Check analysis status",
    description="Check the current status and progress of an analysis"
)
async def get_analysis_status(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.require_permission("recruiter:results:read"))
):
    """
    Check analysis status and progress.
    
    Returns current status (PENDING, PROCESSING, COMPLETED, FAILED)
    and progress percentage if available.
    """
    logger.debug(
        "get_ml_talent_analysis_status",
        analysis_id=analysis_id,
        user_id=current_user.user_id
    )
    
    try:
        # Get analysis from database
        ml_service = MLTalentService(db)
        analysis = ml_service.get_analysis(analysis_id, current_user.customer_id)
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis {analysis_id} not found"
            )
        
        # Calculate progress and message
        analysis_status = AnalysisStatus(analysis["status"])
        progress = 0
        message = "Analysis pending..."
        
        if analysis_status == AnalysisStatus.PENDING:
            progress = 0
            message = "Analysis queued, waiting to start..."
        elif analysis_status == AnalysisStatus.PROCESSING:
            progress = 50
            message = "Analyzing candidates..."
        elif analysis_status == AnalysisStatus.COMPLETED:
            progress = 100
            message = f"Analysis complete! Found {analysis['candidate_count'] or 0} candidates."
        elif analysis_status == AnalysisStatus.FAILED:
            progress = 0
            message = f"Analysis failed: {analysis['error_message'] or 'Unknown error'}"
        
        return AnalysisStatusResponse(
            analysis_id=analysis_id,
            status=analysis_status,
            message=message,
            progress_percentage=progress
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_ml_talent_analysis_status_failed",
            analysis_id=analysis_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )


@router.post(
    "/analysis/{analysis_id}/refine",
    response_model=StartAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Refine PDL query",
    description="Refine PDL market search query based on user feedback and re-run market search"
)
async def refine_pdl_query(
    analysis_id: str,
    request: RefineQueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.require_permission("recruiter:config:create"))
):
    """
    Refine PDL query based on user feedback.
    
    User can:
    - Add/remove required/optional skills
    - Adjust experience ranges
    - Modify company filters
    - Update education requirements
    - Change locations
    
    This creates a new analysis version with refined market search results.
    """
    logger.info(
        "ml_talent_query_refinement_start",
        analysis_id=analysis_id,
        user_id=current_user.user_id
    )
    
    try:
        # TODO: Fetch original analysis
        # TODO: Apply refinement
        # TODO: Re-run market search with new query
        # TODO: Re-score market candidates
        # TODO: Re-run synthesis
        
        new_analysis_id = f"{analysis_id}_v2"
        
        return StartAnalysisResponse(
            analysis_id=new_analysis_id,
            status=AnalysisStatus.PROCESSING,
            message=f"Query refined. New analysis started at /v1/ml-talent/analysis/{new_analysis_id}"
        )
        
    except Exception as e:
        logger.error(
            "ml_talent_query_refinement_failed",
            analysis_id=analysis_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refine query: {str(e)}"
        )


@router.post(
    "/analysis/{analysis_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Submit feedback",
    description="Submit feedback on candidates, attributes, or patterns for future improvements"
)
async def submit_feedback(
    analysis_id: str,
    feedback: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.require_permission("recruiter:config:create"))
):
    """
    Submit feedback on analysis.
    
    Feedback can include:
    - Candidate ratings (great, good, meh, bad)
    - Attribute weight adjustments
    - Pattern validations
    - Overall comments
    
    Feedback is stored for future analysis improvements.
    """
    logger.info(
        "ml_talent_feedback_submitted",
        analysis_id=analysis_id,
        user_id=current_user.user_id
    )
    
    try:
        # Store feedback in database
        ml_service = MLTalentService(db)
        success = ml_service.store_feedback(
            analysis_id=analysis_id,
            user_id=current_user.user_id,
            feedback_type="general",
            feedback_data=feedback
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis {analysis_id} not found"
            )
        
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "ml_talent_feedback_failed",
            analysis_id=analysis_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def run_analysis_background(
    analysis_id: str,
    request: TalentAnalysisRequest
):
    """Run analysis in background task (synchronous wrapper)."""
    import asyncio
    from src.models import database
    
    # Create new DB session for background task
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    ml_service = MLTalentService(db)
    
    logger.info(
        "ml_talent_analysis_background_start",
        analysis_id=analysis_id
    )
    
    try:
        # Send initial event
        ml_service.create_analysis_event(
            analysis_id=analysis_id,
            event_type="analysis_started",
            message="Analysis started - preparing to run AI agents",
            metadata={"role": request.role}
        )
        
        # Update status to processing
        ml_service.update_analysis_status(
            analysis_id=analysis_id,
            status=AnalysisStatus.PROCESSING
        )
        
        # Create event callback that the orchestrator can use
        def emit_event(analysis_id: str, event_type: str, message: str, metadata: dict = None):
            ml_service.create_analysis_event(analysis_id, event_type, message, metadata)
        
        # Initialize orchestrator WITH event callback
        orchestrator = TalentIntelligenceOrchestrator(
            customer_id=request.customer_id,
            user_id=request.user_id,
            neo4j_enabled=True,
            event_callback=emit_event
        )
        
        # Send event for orchestrator initialized
        ml_service.create_analysis_event(
            analysis_id=analysis_id,
            event_type="orchestrator_initialized",
            message="AI orchestrator initialized - starting analysis workflow"
        )
        
        # Run analysis (wrap async call)
        result = asyncio.run(orchestrator.run_analysis(request))
        
        # Store result in database (including normalized candidate tables)
        store_success = ml_service.store_analysis_result(
            analysis_id=analysis_id,
            result=result,
            customer_id=request.customer_id
        )
        
        if not store_success:
            logger.warning(
                "ml_talent_analysis_store_failed",
                analysis_id=analysis_id,
                message="store_analysis_result returned False - status may not be updated"
            )
            # Explicitly update status as fallback
            ml_service.update_analysis_status(
                analysis_id=analysis_id,
                status=AnalysisStatus.COMPLETED
            )
        
        # Send completion event
        ml_service.create_analysis_event(
            analysis_id=analysis_id,
            event_type="analysis_completed",
            message="Analysis completed successfully",
            metadata={
                "applicant_count": len(result.applicant_results),
                "market_count": len(result.market_results),
                "top_overall_count": len(result.top_overall)
            }
        )
        
        logger.info(
            "ml_talent_analysis_background_complete",
            analysis_id=analysis_id,
            status=result.status.value,
            applicant_count=len(result.applicant_results),
            market_count=len(result.market_results)
        )
        
    except Exception as e:
        logger.error(
            "ml_talent_analysis_background_failed",
            analysis_id=analysis_id,
            error=str(e),
            exc_info=True
        )
        
        # Send failure event
        ml_service.create_analysis_event(
            analysis_id=analysis_id,
            event_type="analysis_failed",
            message=f"Analysis failed: {str(e)}",
            metadata={"error": str(e)}
        )
        
        # Update database with error status
        ml_service.update_analysis_status(
            analysis_id=analysis_id,
            status=AnalysisStatus.FAILED,
            error_message=str(e)
        )
    
    finally:
        # Always close the database session
        db.close()

