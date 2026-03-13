"""
Celery tasks for AI-powered talent analysis.

Orchestrates the CrewAI flow for finding ideal candidates.
"""

from celery import Task
from typing import Optional, Dict, Any, List
import structlog
import asyncio
from datetime import datetime

from src.celery_app import celery_app
from src.models import database
from src.models.connector import TalentAnalysis, TalentAnalysisEvent, TalentAnalysisStatus
from src.services.langfuse_service import get_langfuse_service

logger = structlog.get_logger(__name__)

# Import ML matching task so it's registered with Celery
from src.tasks.ml_matching_task import run_ml_matching_task  # noqa: F401


class TalentAnalysisTask(Task):
    """Base task with database session management"""
    
    def __call__(self, *args, **kwargs):
        # Ensure database is initialized
        if database.SessionLocal is None:
            database.init_database()
        return super().__call__(*args, **kwargs)


@celery_app.task(
    base=TalentAnalysisTask,
    bind=True,
    name="talent.run_analysis",
    max_retries=3,
    default_retry_delay=60
)
def run_talent_analysis_task(
    self,
    customer_id: str,
    analysis_id: str,
    job_description: Optional[str] = None,
    ideal_candidate_description: Optional[str] = None,
    manual_persona: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None
):
    """
    Run talent analysis using CrewAI agents.
    
    Flow:
    1. Agent 1 (Job Analyst): Parse JD + ideal candidate description → Ideal persona
    2. Agent 2 (Talent Scout): Search people data → Ranked candidates
    3. Agent 3 (Insights Synthesizer): Generate report → Market insights
    
    Args:
        customer_id: Customer identifier
        analysis_id: Unique analysis ID
        job_description: Job description text (optional)
        ideal_candidate_description: Natural language ideal candidate description (optional)
        manual_persona: Manually defined persona (alternative to JD)
        user_id: Requesting user ID
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    langfuse_service = get_langfuse_service()
    
    try:
        logger.info(
            "talent_analysis_starting",
            analysis_id=analysis_id,
            customer_id=customer_id,
            task_id=self.request.id,
            has_job_description=bool(job_description),
            has_ideal_candidate_description=bool(ideal_candidate_description),
            has_manual_persona=bool(manual_persona)
        )
        
        # Create analysis record
        analysis = TalentAnalysis(
            analysis_id=analysis_id,
            customer_id=customer_id,
            user_id=user_id,
            job_description=job_description,
            ideal_candidate_description=ideal_candidate_description,
            manual_persona=manual_persona,
            status=TalentAnalysisStatus.PROCESSING.value,
            started_at=datetime.utcnow(),
            task_id=self.request.id
        )
        db.add(analysis)
        db.commit()
        
        # Log start event
        _log_event(
            db,
            analysis_id,
            event_type="analysis_started",
            message="AI agents are analyzing your requirements...",
            progress_percentage=0
        )
        
        # Import and run CrewAI flow
        from src.flows.talent_intelligence_flow import TalentIntelligenceFlow
        
        flow = TalentIntelligenceFlow(
            customer_id=customer_id,
            analysis_id=analysis_id
        )
        
        # Run the flow with BOTH inputs (job description AND ideal candidate description)
        with langfuse_service.span_scope(
            name="agentmesh.talent.run_talent_analysis_task.flow_run",
            input_data={
                "analysis_id": analysis_id,
                "customer_id": customer_id,
                "has_job_description": bool(job_description),
                "has_ideal_candidate_description": bool(ideal_candidate_description),
                "has_manual_persona": bool(manual_persona),
            },
            metadata={
                "component": "agentmesh",
                "task": "talent.run_analysis",
                "analysis_id": analysis_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        ):
            results = flow.run(
                job_description=job_description,
                ideal_candidate_description=ideal_candidate_description,
                manual_persona=manual_persona
            )
        
        # Update analysis with results
        analysis.status = TalentAnalysisStatus.COMPLETED.value
        analysis.ideal_persona = results.get('ideal_persona')
        analysis.candidates = results.get('candidates', [])
        analysis.insights_report = results.get('insights_report')
        analysis.completed_at = datetime.utcnow()
        
        # Calculate metadata
        if analysis.candidates:
            analysis.candidate_count = len(analysis.candidates)
            fit_scores = [c.get('fit_score', 0) for c in analysis.candidates]
            if fit_scores:
                analysis.top_candidate_fit_score = max(fit_scores)
                analysis.average_fit_score = sum(fit_scores) / len(fit_scores)
        
        db.commit()
        
        # Log completion event
        _log_event(
            db,
            analysis_id,
            event_type="analysis_completed",
            message=f"Analysis complete! Found {analysis.candidate_count} matching candidates.",
            progress_percentage=100,
            data={
                'candidate_count': analysis.candidate_count,
                'top_fit_score': analysis.top_candidate_fit_score
            }
        )
        
        logger.info(
            "talent_analysis_completed",
            analysis_id=analysis_id,
            customer_id=customer_id,
            candidate_count=analysis.candidate_count,
            top_fit_score=analysis.top_candidate_fit_score
        )
        langfuse_service.trace_event(
            name="agentmesh.talent.run_talent_analysis_task.completed",
            input_data={"analysis_id": analysis_id},
            output_data={
                "candidate_count": analysis.candidate_count,
                "top_fit_score": analysis.top_candidate_fit_score,
            },
            metadata={
                "component": "agentmesh",
                "task": "talent.run_analysis",
                "analysis_id": analysis_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        )
        
        return {
            'analysis_id': analysis_id,
            'status': 'completed',
            'candidate_count': analysis.candidate_count
        }
        
    except Exception as e:
        logger.error(
            "talent_analysis_failed",
            analysis_id=analysis_id,
            customer_id=customer_id,
            error=str(e),
            exc_info=True
        )
        
        # Update analysis status
        analysis = db.query(TalentAnalysis).filter(
            TalentAnalysis.analysis_id == analysis_id
        ).first()
        
        if analysis:
            analysis.status = TalentAnalysisStatus.FAILED.value
            analysis.error_message = str(e)
            analysis.completed_at = datetime.utcnow()
            db.commit()
            
            # Log failure event
            _log_event(
                db,
                analysis_id,
                event_type="analysis_failed",
                message=f"Analysis failed: {str(e)}",
                progress_percentage=0
            )
        
        # Re-raise for Celery retry
        raise
        
    finally:
        db.close()


def _log_event(
    db,
    analysis_id: str,
    event_type: str,
    message: str,
    progress_percentage: int = None,
    agent_name: str = None,
    data: Dict[str, Any] = None
):
    """Helper to log analysis event"""
    event = TalentAnalysisEvent(
        analysis_id=analysis_id,
        event_type=event_type,
        agent_name=agent_name,
        message=message,
        progress_percentage=progress_percentage,
        data=data
    )
    db.add(event)
    db.commit()
    
    logger.info(
        "talent_event_logged",
        analysis_id=analysis_id,
        event_type=event_type,
        progress=progress_percentage
    )


# ============================================================================
# NEW ORCHESTRATOR-BASED ANALYSIS TASK
# ============================================================================

@celery_app.task(
    base=TalentAnalysisTask,
    bind=True,
    name="talent.run_orchestrator_analysis",
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=1800,  # 30 minutes
    time_limit=1860  # 31 minutes hard limit
)
def run_orchestrator_analysis_task(
    self,
    analysis_id: str,
    customer_id: str,
    user_id: int,
    job_description: str,
    ideal_candidate_description: str,
    role: Optional[str] = None,
    ats_connection_id: Optional[int] = None,
    department_ids: Optional[List[int]] = None,
    blueprint_id: Optional[int] = None,
    company_dna_id: Optional[int] = None,
    market_search_limit: int = 50,
    max_candidate_fetch: int = 100,
    include_historical_candidates: bool = False,
    historical_lookback_days: int = 365,
    uploaded_resume_files: Optional[List[str]] = None
):
    """
    Run talent analysis using the new TalentIntelligenceOrchestrator.
    
    This task:
    1. Fetches candidates from Greenhouse (if configured)
    2. Loads uploaded resume files (if configured)
    3. Optionally fetches historical candidates from closed jobs
    4. Runs the multi-stage analysis pipeline
    5. Scores candidates using blueprints and company DNA
    6. Searches PDL for market candidates
    
    Args:
        analysis_id: Unique analysis ID
        customer_id: Customer identifier
        user_id: Requesting user ID
        job_description: Job description text
        ideal_candidate_description: Ideal candidate description
        role: Optional role hint (extracted from JD by the diagnostic agent if not provided)
        ats_connection_id: Optional ATS connection ID for fetching candidates
        department_ids: Optional department IDs to filter candidates
        blueprint_id: Optional career blueprint ID for scoring
        company_dna_id: Optional company DNA ID for scoring
        market_search_limit: Max candidates to fetch from PDL
        max_candidate_fetch: Max candidates to fetch from Greenhouse (default 100)
        include_historical_candidates: Whether to include candidates from closed jobs
        historical_lookback_days: How far back to look for historical candidates (default 365)
        uploaded_resume_files: Optional list of uploaded resume filenames to process
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    langfuse_service = get_langfuse_service()
    
    try:
        logger.info(
            "orchestrator_analysis_starting",
            analysis_id=analysis_id,
            customer_id=customer_id,
            task_id=self.request.id,
            ats_connection_id=ats_connection_id,
            department_ids=department_ids,
            blueprint_id=blueprint_id,
            company_dna_id=company_dna_id
        )
        
        # Import services
        from src.services.ml_talent_service import MLTalentService
        from src.services.talent.orchestrator import TalentIntelligenceOrchestrator, TalentAnalysisRequest
        from src.models.talent_analysis import AnalysisStatus
        
        ml_service = MLTalentService(db)
        
        # Log start event
        ml_service.create_analysis_event(
            analysis_id=analysis_id,
            event_type="analysis_started",
            message="Analysis started - preparing to run AI agents",
            metadata={"role": role, "task_id": self.request.id}
        )
        
        # Update status to processing
        ml_service.update_analysis_status(
            analysis_id=analysis_id,
            status=AnalysisStatus.PROCESSING
        )
        
        # Fetch candidates from Greenhouse if configured
        applicant_resume_files = []
        historical_candidate_files = []
        
        if ats_connection_id and department_ids:
            # Fetch current applicants from open jobs
            applicant_resume_files = _fetch_greenhouse_candidates(
                db=db,
                ats_connection_id=ats_connection_id,
                department_ids=department_ids,
                customer_id=customer_id,
                analysis_id=analysis_id,
                ml_service=ml_service,
                max_candidate_fetch=max_candidate_fetch
            )
            
            # Fetch historical candidates from closed jobs if enabled
            if include_historical_candidates:
                historical_candidate_files = _fetch_historical_candidates(
                    db=db,
                    ats_connection_id=ats_connection_id,
                    department_ids=department_ids,
                    customer_id=customer_id,
                    analysis_id=analysis_id,
                    ml_service=ml_service,
                    lookback_days=historical_lookback_days,
                    max_candidates=max_candidate_fetch
                )
        
        # Load uploaded resume files if configured
        if uploaded_resume_files:
            from src.core.config import get_settings
            from pathlib import Path
            
            settings = get_settings()
            upload_dir = Path(settings.upload_directory) / customer_id / "resumes"
            
            logger.info(
                "loading_uploaded_resumes",
                analysis_id=analysis_id,
                customer_id=customer_id,
                resume_count=len(uploaded_resume_files),
                upload_dir=str(upload_dir)
            )
            
            ml_service.create_analysis_event(
                analysis_id=analysis_id,
                event_type="loading_uploaded_resumes",
                message=f"Loading {len(uploaded_resume_files)} uploaded resumes",
                metadata={"resume_count": len(uploaded_resume_files)}
            )
            
            for filename in uploaded_resume_files:
                # Try exact filename first, then search for UUID-prefixed version
                file_path = upload_dir / filename
                if not file_path.exists():
                    # Search for UUID-prefixed version
                    for candidate_file in upload_dir.iterdir():
                        if candidate_file.name.endswith(filename) or filename in candidate_file.name:
                            file_path = candidate_file
                            break
                
                if file_path.exists():
                    try:
                        with open(file_path, 'rb') as f:
                            resume_content = f.read()
                        
                        # Add to applicant resume files in the format the orchestrator expects
                        applicant_resume_files.append({
                            "filename": filename,
                            "file_path": str(file_path),
                            "content": resume_content,
                            "source": "upload"
                        })
                        logger.info(
                            "resume_file_loaded",
                            analysis_id=analysis_id,
                            filename=filename,
                            file_size=len(resume_content)
                        )
                    except Exception as e:
                        logger.error(
                            "resume_file_load_error",
                            analysis_id=analysis_id,
                            filename=filename,
                            error=str(e)
                        )
                else:
                    logger.warning(
                        "resume_file_not_found",
                        analysis_id=analysis_id,
                        filename=filename,
                        searched_dir=str(upload_dir)
                    )
            
            ml_service.create_analysis_event(
                analysis_id=analysis_id,
                event_type="uploaded_resumes_loaded",
                message=f"Loaded {len(applicant_resume_files)} resume files",
                metadata={"loaded_count": len(applicant_resume_files)}
            )
        
        # Create event callback
        def emit_event(analysis_id: str, event_type: str, message: str, metadata: dict = None):
            ml_service.create_analysis_event(analysis_id, event_type, message, metadata)
        
        # Initialize orchestrator
        orchestrator = TalentIntelligenceOrchestrator(
            customer_id=customer_id,
            user_id=user_id,
            event_callback=emit_event,
            blueprint_id=blueprint_id,
            company_dna_id=company_dna_id,
        )
        
        ml_service.create_analysis_event(
            analysis_id=analysis_id,
            event_type="orchestrator_initialized",
            message="AI orchestrator initialized - starting analysis workflow"
        )
        
        # Build analysis request
        request = TalentAnalysisRequest(
            analysis_id=analysis_id,
            job_description=job_description,
            ideal_candidate_description=ideal_candidate_description,
            applicant_resume_files=applicant_resume_files,
            historical_candidate_files=historical_candidate_files,  # Previous candidates from closed jobs
            role=role,
            customer_id=customer_id,
            user_id=user_id,
            baseline_employee_ids=[],
            baseline_linkedin_urls=[],
            selected_blueprint_id=blueprint_id,
            company_dna_id=company_dna_id,
            market_search_limit=market_search_limit
        )
        
        # Run analysis (Celery workers can use asyncio.run safely)
        with langfuse_service.span_scope(
            name="agentmesh.talent.run_orchestrator_analysis_task.orchestrator_run",
            input_data={
                "analysis_id": analysis_id,
                "customer_id": customer_id,
                "role": role,
                "uploaded_resume_files": len(uploaded_resume_files or []),
                "department_ids": department_ids or [],
                "ats_connection_id": ats_connection_id,
                "include_historical_candidates": include_historical_candidates,
            },
            metadata={
                "component": "agentmesh",
                "task": "talent.run_orchestrator_analysis",
                "analysis_id": analysis_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        ):
            result = asyncio.run(orchestrator.run_analysis(request))
        
        # Store result
        store_success = ml_service.store_analysis_result(
            analysis_id=analysis_id,
            result=result,
            customer_id=customer_id
        )
        
        if not store_success:
            logger.warning(
                "orchestrator_analysis_store_failed",
                analysis_id=analysis_id,
                message="store_analysis_result returned False"
            )
            ml_service.update_analysis_status(
                analysis_id=analysis_id,
                status=AnalysisStatus.COMPLETED
            )
        
        # Log completion
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
            "orchestrator_analysis_completed",
            analysis_id=analysis_id,
            customer_id=customer_id,
            applicant_count=len(result.applicant_results),
            market_count=len(result.market_results)
        )
        langfuse_service.trace_event(
            name="agentmesh.talent.run_orchestrator_analysis_task.completed",
            input_data={"analysis_id": analysis_id},
            output_data={
                "applicant_count": len(result.applicant_results),
                "market_count": len(result.market_results),
                "top_overall_count": len(result.top_overall),
            },
            metadata={
                "component": "agentmesh",
                "task": "talent.run_orchestrator_analysis",
                "analysis_id": analysis_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        )
        
        return {
            'analysis_id': analysis_id,
            'status': 'completed',
            'applicant_count': len(result.applicant_results),
            'market_count': len(result.market_results)
        }
        
    except Exception as e:
        logger.error(
            "orchestrator_analysis_failed",
            analysis_id=analysis_id,
            customer_id=customer_id,
            error=str(e),
            exc_info=True
        )
        
        # Update status to failed
        try:
            from src.services.ml_talent_service import MLTalentService
            from src.models.talent_analysis import AnalysisStatus
            ml_service = MLTalentService(db)
            
            ml_service.create_analysis_event(
                analysis_id=analysis_id,
                event_type="analysis_failed",
                message=f"Analysis failed: {str(e)}",
                metadata={"error": str(e)}
            )
            
            ml_service.update_analysis_status(
                analysis_id=analysis_id,
                status=AnalysisStatus.FAILED,
                error_message=str(e)
            )
        except Exception as update_error:
            logger.error(
                "orchestrator_analysis_status_update_failed",
                analysis_id=analysis_id,
                error=str(update_error)
            )
        
        raise
        
    finally:
        db.close()


def _fetch_greenhouse_candidates(
    db,
    ats_connection_id: int,
    department_ids: List[int],
    customer_id: str,
    analysis_id: str,
    ml_service,
    max_candidate_fetch: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetch candidates from Greenhouse for the given departments.
    
    Args:
        db: Database session
        ats_connection_id: ID of the ATS connector configuration
        department_ids: List of department IDs to fetch candidates from
        customer_id: Customer identifier
        analysis_id: Analysis ID for logging
        ml_service: MLTalentService instance for logging events
        max_candidate_fetch: Maximum number of candidates to fetch (default 100)
    
    Returns list of resume data dicts with:
    - file_bytes: Resume file content
    - filename: Resume filename
    - greenhouse_id: Candidate ID in Greenhouse
    - candidate_name: Full name
    - email: Email address
    """
    from src.services.ingestion.connector_service import ConnectorService
    from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
    
    connector_service = ConnectorService(db)
    connector_config = connector_service.get_configuration_by_id(ats_connection_id)
    
    if not connector_config or connector_config.connector_type != "greenhouse":
        logger.warning(
            "greenhouse_connector_not_found",
            ats_connection_id=ats_connection_id
        )
        return []
    
    credentials = connector_service.get_credentials(connector_config)
    
    async def fetch_async():
        # Create connector to get jobs in departments
        connector = GreenhouseConnector(
            credentials=credentials,
            config={},
            customer_id=customer_id
        )
        
        # Get all jobs in the selected departments
        department_jobs = await connector.get_jobs(department_ids=department_ids)
        department_job_ids = [job["id"] for job in department_jobs]
        
        logger.info(
            "greenhouse_department_jobs_found",
            analysis_id=analysis_id,
            department_ids=department_ids,
            job_count=len(department_job_ids)
        )
        
        if not department_job_ids:
            return []
        
        # Create connector with job IDs filter
        connector_with_jobs = GreenhouseConnector(
            credentials=credentials,
            config={'job_ids': department_job_ids},
            customer_id=customer_id
        )
        
        candidates_data = []
        page = 1
        max_pages = 10
        seen_candidate_ids = set()
        
        while page <= max_pages:
            response = await connector_with_jobs.fetch_candidates(page=page, per_page=100)
            candidates = response.get("candidates", [])
            
            if not candidates:
                break
            
            for candidate in candidates:
                candidate_id = candidate.get("id")
                
                if candidate_id in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(candidate_id)
                
                # Check for valid applications
                applications = candidate.get("applications", [])
                has_valid_application = False
                
                for app in applications:
                    if app.get("prospect", False):
                        continue
                    
                    app_jobs = app.get("jobs", [])
                    for job in app_jobs:
                        if job.get("id") in department_job_ids:
                            has_valid_application = True
                            break
                    
                    if has_valid_application:
                        break
                
                if not has_valid_application:
                    continue
                
                # Get resume
                attachments = candidate.get("attachments", [])
                for attachment in attachments:
                    if attachment.get("type") == "resume":
                        try:
                            resume_url = attachment.get("url")
                            if resume_url:
                                resume_bytes = await connector.download_resume(resume_url)
                                candidates_data.append({
                                    'file_bytes': resume_bytes,
                                    'filename': attachment.get("filename", "resume.pdf"),
                                    'greenhouse_id': candidate_id,
                                    'candidate_name': f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip(),
                                    'email': candidate.get("email_addresses", [{}])[0].get("value") if candidate.get("email_addresses") else None
                                })
                                break
                        except Exception as e:
                            logger.warning(f"Failed to download resume for candidate {candidate_id}: {e}")
                
                if len(candidates_data) >= max_candidate_fetch:
                    break
            
            if len(candidates_data) >= max_candidate_fetch or not response.get("has_next"):
                break
            
            page += 1
        
        return candidates_data
    
    # Run async fetch in Celery worker
    candidates = asyncio.run(fetch_async())
    
    logger.info(
        "greenhouse_candidates_fetched",
        analysis_id=analysis_id,
        candidate_count=len(candidates),
        department_ids=department_ids
    )
    
    # Log event
    ml_service.create_analysis_event(
        analysis_id=analysis_id,
        event_type="greenhouse_candidates_fetched",
        message=f"Fetched {len(candidates)} candidates from Greenhouse",
        metadata={
            "candidate_count": len(candidates),
            "department_ids": department_ids
        }
    )
    
    return candidates


def _fetch_historical_candidates(
    db,
    ats_connection_id: int,
    department_ids: List[int],
    customer_id: str,
    analysis_id: str,
    ml_service,
    lookback_days: int = 365,
    max_candidates: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetch historical candidates from closed jobs in the given departments.
    
    These are candidates who applied to jobs that are now closed but may still
    be relevant for current openings.
    
    Args:
        db: Database session
        ats_connection_id: ID of the ATS connector configuration
        department_ids: List of department IDs to fetch candidates from
        customer_id: Customer identifier
        analysis_id: Analysis ID for logging
        ml_service: MLTalentService instance for logging events
        lookback_days: How far back to look for closed jobs (default 365 days)
        max_candidates: Maximum number of candidates to fetch (default 100)
    
    Returns list of resume data dicts with:
    - file_bytes: Resume file content
    - filename: Resume filename
    - greenhouse_id: Candidate ID in Greenhouse
    - candidate_name: Full name
    - email: Email address
    - is_historical: True (marks as previous candidate)
    - source_job_id: Original job ID they applied to
    """
    from src.services.ingestion.connector_service import ConnectorService
    from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
    
    connector_service = ConnectorService(db)
    connector_config = connector_service.get_configuration_by_id(ats_connection_id)
    
    if not connector_config or connector_config.connector_type != "greenhouse":
        logger.warning(
            "greenhouse_connector_not_found_for_historical",
            ats_connection_id=ats_connection_id
        )
        return []
    
    credentials = connector_service.get_credentials(connector_config)
    
    async def fetch_async():
        connector = GreenhouseConnector(
            credentials=credentials,
            config={},
            customer_id=customer_id
        )
        
        # Fetch historical candidates with resumes
        historical_resumes = await connector.fetch_historical_candidates_with_resumes(
            department_ids=department_ids,
            lookback_days=lookback_days,
            max_candidates=max_candidates
        )
        
        # Convert to the format expected by the orchestrator
        candidates_data = []
        for resume in historical_resumes:
            candidates_data.append({
                'file_bytes': resume.get('file_bytes'),
                'filename': resume.get('filename', 'resume.pdf'),
                'greenhouse_id': resume.get('candidate_id'),
                'candidate_name': resume.get('candidate_name'),
                'email': resume.get('candidate_email'),
                'is_historical': True,
                'source_job_id': resume.get('source_job_id'),
                'applied_at': resume.get('applied_at')
            })
        
        return candidates_data
    
    # Run async fetch in Celery worker
    candidates = asyncio.run(fetch_async())
    
    logger.info(
        "historical_candidates_fetched",
        analysis_id=analysis_id,
        candidate_count=len(candidates),
        department_ids=department_ids,
        lookback_days=lookback_days
    )
    
    # Log event
    ml_service.create_analysis_event(
        analysis_id=analysis_id,
        event_type="historical_candidates_fetched",
        message=f"Fetched {len(candidates)} previous candidates from closed jobs (last {lookback_days} days)",
        metadata={
            "candidate_count": len(candidates),
            "department_ids": department_ids,
            "lookback_days": lookback_days
        }
    )
    
    return candidates
