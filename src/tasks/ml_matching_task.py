"""
ML Engineer Matching Celery Task

Background task for running ML engineer candidate matching.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import traceback

from src.celery_app import celery_app
from src.models import database
from src.models.talent_matching import MatchingSession, CandidateAnalysis
from src.flows.ml_engineer_matching_flow import MLEngineerMatchingFlow
from src.core.logging import get_logger, LogCategory
from src.services.langfuse_service import get_langfuse_service

logger = get_logger(__name__, LogCategory.BUSINESS)


@celery_app.task(
    name="run_ml_matching_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def run_ml_matching_task(
    self,
    session_id: str,
    customer_id: str,
    job_description: str,
    hiring_manager_notes: Optional[str] = None,
    reference_employee_ids: Optional[List[int]] = None,
    analyze_internal: bool = True,
    search_external: bool = True,
    max_results: int = 20,
    use_fast_ranking: bool = False,
    budget_usd: Optional[float] = None
):
    """
    Run ML engineer candidate matching as background task.
    
    This task:
    1. Executes the MLEngineerMatchingFlow
    2. Stores results in database (MatchingSession + CandidateAnalysis records)
    3. Updates session status throughout execution
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    langfuse_service = get_langfuse_service()
    
    try:
        logger.info(
            "ml_matching_task_started",
            session_id=session_id,
            customer_id=customer_id,
            task_id=self.request.id
        )
        
        # Update session status
        matching_session = db.query(MatchingSession).filter(
            MatchingSession.session_id == session_id
        ).first()
        
        if not matching_session:
            logger.error("matching_session_not_found", session_id=session_id)
            raise ValueError(f"Matching session {session_id} not found")
        
        matching_session.status = 'running'
        db.commit()
        
        # Initialize and run flow
        flow = MLEngineerMatchingFlow()
        
        start_time = datetime.now()
        
        with langfuse_service.span_scope(
            name="agentmesh.ml_matching.task.run_ml_matching_task.flow_kickoff",
            input_data={
                "session_id": session_id,
                "customer_id": customer_id,
                "analyze_internal": analyze_internal,
                "search_external": search_external,
                "max_results": max_results,
                "use_fast_ranking": use_fast_ranking,
                "budget_usd": budget_usd,
            },
            metadata={
                "component": "agentmesh",
                "task": "run_ml_matching_task",
                "session_id": session_id,
                "customer_id": customer_id,
            },
        ):
            result = flow.kickoff({
                'customer_id': customer_id,
                'job_description': job_description,
                'hiring_manager_notes': hiring_manager_notes,
                'reference_employee_ids': reference_employee_ids,
                'analyze_internal': analyze_internal,
                'search_external': search_external,
                'max_results': max_results,
                'use_fast_ranking': use_fast_ranking,
                'budget_usd': budget_usd
            })
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Store results in database
        _store_matching_results(
            db=db,
            session_id=session_id,
            customer_id=customer_id,
            result=result,
            duration=duration
        )
        
        # Update session
        matching_session.status = 'completed'
        matching_session.completed_at = end_time
        matching_session.total_duration_seconds = duration
        matching_session.total_cost_usd = result.get('cost_usd', 0.0)
        matching_session.agent_trace = {
            'flow_result': result,
            'task_id': self.request.id
        }
        db.commit()
        
        logger.info(
            "ml_matching_task_completed",
            session_id=session_id,
            duration_seconds=duration,
            internal_matches=len(result.get('internal_matches', [])),
            external_matches=len(result.get('external_matches', []))
        )
        langfuse_service.trace_event(
            name="agentmesh.ml_matching.task.run_ml_matching_task.completed",
            input_data={"session_id": session_id},
            output_data={
                "duration_seconds": duration,
                "internal_matches": len(result.get("internal_matches", [])),
                "external_matches": len(result.get("external_matches", [])),
                "cost_usd": result.get("cost_usd", 0.0),
            },
            metadata={
                "component": "agentmesh",
                "task": "run_ml_matching_task",
                "session_id": session_id,
                "customer_id": customer_id,
            },
        )
        
        return {
            'session_id': session_id,
            'status': 'completed',
            'duration_seconds': duration
        }
        
    except Exception as e:
        logger.error(
            "ml_matching_task_failed",
            session_id=session_id,
            error=str(e),
            traceback=traceback.format_exc()
        )
        
        # Update session status
        try:
            matching_session = db.query(MatchingSession).filter(
                MatchingSession.session_id == session_id
            ).first()
            
            if matching_session:
                matching_session.status = 'failed'
                matching_session.completed_at = datetime.now()
                matching_session.agent_trace = {
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }
                db.commit()
        except:
            pass
        
        # Retry if appropriate
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        else:
            return {
                'session_id': session_id,
                'status': 'failed',
                'error': str(e)
            }
    
    finally:
        db.close()


def _store_matching_results(
    db,
    session_id: str,
    customer_id: str,
    result: Dict[str, Any],
    duration: float
):
    """Store matching results in database"""
    try:
        # Update session with synthesized profile and patterns
        matching_session = db.query(MatchingSession).filter(
            MatchingSession.session_id == session_id
        ).first()
        
        if matching_session:
            matching_session.ideal_candidate_profile = result.get('ideal_profile')
            matching_session.success_patterns_found = result.get('success_patterns')
            matching_session.pdl_query_generated = result.get('pdl_query')
            matching_session.internal_candidates_analyzed = len(result.get('internal_matches', []))
            matching_session.external_candidates_found = len(result.get('external_matches', []))
            db.commit()
        
        # Store internal candidate analyses
        for candidate in result.get('internal_matches', []):
            analysis = CandidateAnalysis(
                customer_id=customer_id,
                analysis_session_id=session_id,
                job_posting_id=None,  # Could link to job posting if available
                applicant_id=candidate.get('applicant_id'),
                candidate_source='internal_applicant',
                ideal_profile=result.get('ideal_profile'),
                total_score=candidate.get('score', 0),
                confidence=candidate.get('confidence', 0.5),
                score_skills_match=candidate.get('score_breakdown', {}).get('skills_match'),
                score_experience_fit=candidate.get('score_breakdown', {}).get('experience_fit'),
                score_career_trajectory=candidate.get('score_breakdown', {}).get('career_trajectory'),
                score_company_background=candidate.get('score_breakdown', {}).get('company_background'),
                score_cultural_fit=candidate.get('score_breakdown', {}).get('cultural_fit'),
                pattern_matches=candidate.get('pattern_matches'),
                why_great_fit=candidate.get('why_great_fit'),
                potential_concerns=candidate.get('potential_concerns'),
                evidence=candidate.get('evidence'),
                ranking_method=candidate.get('ranking_method', 'two_stage'),
                ranking_stage='stage_2_deep'
            )
            db.add(analysis)
        
        # Store external candidate analyses
        for candidate in result.get('external_matches', []):
            analysis = CandidateAnalysis(
                customer_id=customer_id,
                analysis_session_id=session_id,
                pdl_person_id=candidate.get('pdl_person_id'),
                candidate_source='external_pdl',
                ideal_profile=result.get('ideal_profile'),
                total_score=candidate.get('score', 0),
                confidence=candidate.get('confidence', 0.5),
                score_skills_match=candidate.get('score_breakdown', {}).get('skills_match'),
                score_experience_fit=candidate.get('score_breakdown', {}).get('experience_fit'),
                score_career_trajectory=candidate.get('score_breakdown', {}).get('career_trajectory'),
                score_company_background=candidate.get('score_breakdown', {}).get('company_background'),
                score_cultural_fit=candidate.get('score_breakdown', {}).get('cultural_fit'),
                pattern_matches=candidate.get('pattern_matches'),
                why_great_fit=candidate.get('why_great_fit'),
                potential_concerns=candidate.get('potential_concerns'),
                evidence=candidate.get('evidence'),
                ranking_method=candidate.get('ranking_method', 'two_stage'),
                ranking_stage='stage_2_deep'
            )
            db.add(analysis)
        
        db.commit()
        
        logger.info(
            "matching_results_stored",
            session_id=session_id,
            internal_count=len(result.get('internal_matches', [])),
            external_count=len(result.get('external_matches', []))
        )
        
    except Exception as e:
        logger.error("store_results_error", error=str(e))
        db.rollback()
        # Don't raise - results are in memory even if storage fails
