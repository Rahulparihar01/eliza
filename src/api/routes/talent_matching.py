"""
Talent Matching API Endpoints

Role-agnostic candidate matching using CrewAI flows.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from src.middleware.authorization import get_current_user
from src.core.auth_context import CurrentUserContext
from src.models import get_db
from src.models.talent_matching import (
    TalentMatchingRequest,
    TalentMatchingResponse,
    MatchedCandidateResult,
    CandidateScoreBreakdown,
    IdealCandidateProfileSchema,
    MatchingSession,
    CandidateAnalysis
)
from src.flows.ml_engineer_matching_flow import CandidateMatchingFlow, MLEngineerMatchingFlow
from src.tasks.talent_tasks import run_ml_matching_task  # Background task
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)

router = APIRouter(prefix="/talent-matching", tags=["Talent Matching"])


@router.post("/ml-engineer/match", response_model=dict)
async def start_ml_engineer_matching(
    request: TalentMatchingRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start candidate matching analysis.
    
    This endpoint kicks off a comprehensive talent matching flow that:
    1. Synthesizes ideal candidate profile from JD + hiring manager notes + employee patterns
    2. Searches and ranks internal applicants
    3. Generates PDL query and finds external candidates
    4. Produces detailed talent intelligence report
    
    Processing is async (runs as Celery task). Returns immediately with session_id.
    Poll /ml-engineer/match/{session_id} for results.
    
    **Example Request:**
    ```json
    {
      "job_description": "We're hiring a Senior Engineer to build...",
      "hiring_manager_notes": "Need someone who can work independently and has shipped production systems",
      "reference_employee_ids": [123, 456, 789],
      "analyze_internal_applicants": true,
      "search_external_pdl": true,
      "max_results": 20
    }
    ```
    
    **Cost Estimate:**
    - Internal search: ~$0.30 in LLM costs
    - External PDL search: ~$0.50-2.00 depending on results
    - Total: ~$1-3 per search
    """
    try:
        logger.info(
            "ml_matching_request_received",
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
            has_hiring_notes=bool(request.hiring_manager_notes),
            analyze_internal=request.analyze_internal_applicants,
            search_external=request.search_external_pdl
        )
        
        # Create matching session record
        matching_session = MatchingSession(
            session_id=f"ml_match_{current_user.customer_id}_{int(datetime.now().timestamp())}",
            customer_id=current_user.customer_id,
            job_description=request.job_description,
            hiring_manager_notes=request.hiring_manager_notes,
            reference_employee_ids=request.reference_employee_ids,
            status='pending'
        )
        db.add(matching_session)
        db.commit()
        db.refresh(matching_session)
        
        # Queue background task
        background_tasks.add_task(
            run_ml_matching_task,
            session_id=matching_session.session_id,
            customer_id=current_user.customer_id,
            job_description=request.job_description,
            hiring_manager_notes=request.hiring_manager_notes,
            reference_employee_ids=request.reference_employee_ids,
            analyze_internal=request.analyze_internal_applicants,
            search_external=request.search_external_pdl,
            max_results=request.max_results,
            use_fast_ranking=request.use_fast_ranking,
            budget_usd=request.budget_usd
        )
        
        logger.info(
            "ml_matching_task_queued",
            session_id=matching_session.session_id
        )
        
        return {
            "session_id": matching_session.session_id,
            "status": "processing",
            "message": "ML engineer matching analysis started. Check back in ~2-5 minutes.",
            "estimated_duration_seconds": 180,
            "poll_url": f"/api/talent-matching/ml-engineer/match/{matching_session.session_id}"
        }
        
    except Exception as e:
        logger.error("ml_matching_request_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start matching analysis: {str(e)}"
        )


@router.get("/ml-engineer/match/{session_id}", response_model=dict)
async def get_ml_engineer_matching_results(
    session_id: str,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get results of ML Engineer matching analysis.
    
    Poll this endpoint after starting a match to check status and get results.
    
    **Response Statuses:**
    - `pending`: Analysis not started yet
    - `running`: Currently processing
    - `completed`: Analysis complete, results included
    - `failed`: Analysis failed, error details included
    """
    try:
        # Get matching session
        matching_session = db.query(MatchingSession).filter(
            MatchingSession.session_id == session_id,
            MatchingSession.customer_id == current_user.customer_id
        ).first()
        
        if not matching_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Matching session {session_id} not found"
            )
        
        # If still processing
        if matching_session.status in ['pending', 'running']:
            return {
                "session_id": session_id,
                "status": matching_session.status,
                "message": "Analysis in progress...",
                "progress": {
                    "profile_synthesis": matching_session.ideal_candidate_profile is not None,
                    "pattern_analysis": matching_session.success_patterns_found is not None,
                    "internal_search": matching_session.internal_candidates_analyzed is not None,
                    "external_search": matching_session.external_candidates_found is not None
                }
            }
        
        # If failed
        if matching_session.status == 'failed':
            return {
                "session_id": session_id,
                "status": "failed",
                "error": matching_session.agent_trace.get('error') if matching_session.agent_trace else "Unknown error"
            }
        
        # Get candidate analyses
        internal_analyses = db.query(CandidateAnalysis).filter(
            CandidateAnalysis.analysis_session_id == session_id,
            CandidateAnalysis.candidate_source == 'internal_applicant'
        ).order_by(CandidateAnalysis.total_score.desc()).limit(20).all()
        
        external_analyses = db.query(CandidateAnalysis).filter(
            CandidateAnalysis.analysis_session_id == session_id,
            CandidateAnalysis.candidate_source == 'external_pdl'
        ).order_by(CandidateAnalysis.total_score.desc()).limit(20).all()
        
        # Format response
        from datetime import datetime
        
        def format_candidate(analysis: CandidateAnalysis) -> dict:
            """Format candidate analysis for API response"""
            return {
                "candidate_id": analysis.applicant_id or analysis.pdl_person_id,
                "source": analysis.candidate_source,
                "score_breakdown": {
                    "total_score": analysis.total_score,
                    "confidence": analysis.confidence,
                    "skills_match": analysis.score_skills_match,
                    "experience_fit": analysis.score_experience_fit,
                    "career_trajectory": analysis.score_career_trajectory,
                    "company_background": analysis.score_company_background,
                    "cultural_fit": analysis.score_cultural_fit,
                    "production_ml_evidence": analysis.score_production_ml,
                    "independence_signals": analysis.score_independence
                },
                "pattern_matches": analysis.pattern_matches,
                "why_great_fit": analysis.why_great_fit,
                "potential_concerns": analysis.potential_concerns,
                "evidence": analysis.evidence,
                "analyzed_at": analysis.analyzed_at.isoformat(),
                "ranking_method": analysis.ranking_method
            }
        
        response = {
            "session_id": session_id,
            "status": "completed",
            "ideal_profile": matching_session.ideal_candidate_profile,
            "success_patterns_found": matching_session.success_patterns_found,
            "internal_matches": [format_candidate(a) for a in internal_analyses],
            "external_matches": [format_candidate(a) for a in external_analyses],
            "market_insights": {
                "internal_candidates_analyzed": matching_session.internal_candidates_analyzed,
                "external_candidates_found": matching_session.external_candidates_found,
                "pdl_query_used": matching_session.pdl_query_generated,
                "pdl_cost_usd": matching_session.pdl_query_cost_usd
            },
            "performance": {
                "total_duration_seconds": matching_session.total_duration_seconds,
                "total_cost_usd": matching_session.total_cost_usd,
                "agent_trace": matching_session.agent_trace
            },
            "completed_at": matching_session.completed_at.isoformat() if matching_session.completed_at else None
        }
        
        logger.info(
            "ml_matching_results_retrieved",
            session_id=session_id,
            internal_matches=len(internal_analyses),
            external_matches=len(external_analyses)
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ml_matching_results_error", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve matching results: {str(e)}"
        )


@router.get("/sessions", response_model=List[dict])
async def list_matching_sessions(
    limit: int = 20,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List recent talent matching sessions for the current customer.
    """
    try:
        sessions = db.query(MatchingSession).filter(
            MatchingSession.customer_id == current_user.customer_id
        ).order_by(
            MatchingSession.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "session_id": s.session_id,
                "status": s.status,
                "job_description_preview": s.job_description[:200] + "..." if len(s.job_description) > 200 else s.job_description,
                "internal_candidates_analyzed": s.internal_candidates_analyzed,
                "external_candidates_found": s.external_candidates_found,
                "created_at": s.created_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "duration_seconds": s.total_duration_seconds,
                "cost_usd": s.total_cost_usd
            }
            for s in sessions
        ]
        
    except Exception as e:
        logger.error("list_sessions_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )


@router.post("/test/sync", response_model=dict)
async def test_ml_matching_sync(
    request: TalentMatchingRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    TEST ENDPOINT: Run ML matching synchronously (blocks until complete).
    
    ⚠️ WARNING: This can take 2-5 minutes. Only use for testing/debugging.
    Production should use the async endpoint /ml-engineer/match.
    """
    try:
        logger.info(
            "ml_matching_sync_test_started",
            user_id=current_user.user_id
        )
        
        # Create flow
        flow = MLEngineerMatchingFlow()
        
        # Run flow
        result = flow.kickoff({
            'customer_id': current_user.customer_id,
            'job_description': request.job_description,
            'hiring_manager_notes': request.hiring_manager_notes,
            'reference_employee_ids': request.reference_employee_ids,
            'analyze_internal': request.analyze_internal_applicants,
            'search_external': request.search_external_pdl,
            'max_results': request.max_results,
            'use_fast_ranking': request.use_fast_ranking,
            'budget_usd': request.budget_usd
        })
        
        logger.info(
            "ml_matching_sync_test_completed",
            session_id=result['session_id'],
            duration_seconds=result['duration_seconds']
        )
        
        return result
        
    except Exception as e:
        logger.error("ml_matching_sync_test_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Matching failed: {str(e)}"
        )

