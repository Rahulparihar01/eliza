"""
ML Talent Intelligence Service

Service layer for ML Talent Intelligence System.
Handles database operations, status tracking, and analysis orchestration.
Pattern follows BusinessIntelligenceService for consistency.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
import json
import uuid

from src.models.talent_analysis import (
    TalentAnalysisResult, AnalysisStatus, BaselineProfile,
    DiagnosticReport, SynthesisReport, CandidateScore
)
from src.models.candidate import Candidate, CandidateAnalysisScore
from src.services.base_service import BaseService
from src.services.candidate_service import CandidateService
from src.core.logging import get_logger, LogCategory, bind_context

logger = get_logger(__name__, component="ml_talent_intelligence")


class MLTalentService(BaseService):
    """Service for managing ML Talent Intelligence analyses."""
    
    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        bind_context(service="ml_talent_intelligence")
    
    def _safe_json_load(self, value: Any) -> Any:
        """Safely load JSON data, handling both string and dict inputs."""
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value  # Already parsed
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value  # Return as-is if not valid JSON
        return value
    
    def create_analysis(
        self,
        analysis_id: str,
        user_id: int,
        customer_id: str,
        job_description: str,
        ideal_candidate_description: str,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new talent analysis record.
        
        Args:
            analysis_id: Unique analysis identifier
            user_id: User requesting the analysis
            customer_id: Customer organization ID
            job_description: Job description text
            ideal_candidate_description: Ideal candidate description
            role: Optional role hint (will be extracted from JD by the diagnostic agent)
            
        Returns:
            Created analysis record as dict
        """
        logger.debug(
            "create_ml_talent_analysis_start",
            analysis_id=analysis_id,
            user_id=user_id,
            customer_id=customer_id
        )
        
        try:
            self.db.execute(
                text("""
                    INSERT INTO talent_analyses (
                        analysis_id, customer_id, user_id, job_description,
                        ideal_candidate_description, status, version, created_at
                    ) VALUES (
                        :analysis_id, :customer_id, :user_id, :job_description,
                        :ideal_candidate_description, :status, :version, :created_at
                    )
                """),
                {
                    "analysis_id": analysis_id,
                    "customer_id": customer_id,
                    "user_id": user_id,
                    "job_description": job_description,
                    "ideal_candidate_description": ideal_candidate_description,
                    "status": AnalysisStatus.PENDING.value,
                    "version": "v2",
                    "created_at": datetime.now(timezone.utc)
                }
            )
            self.db.commit()
            
            logger.info(
                "ml_talent_analysis_created",
                analysis_id=analysis_id,
                user_id=user_id,
                customer_id=customer_id
            )
            
            return {
                "analysis_id": analysis_id,
                "status": AnalysisStatus.PENDING.value,
                "created_at": datetime.now(timezone.utc)
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                "ml_talent_analysis_creation_failed",
                analysis_id=analysis_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def get_analysis(
        self,
        analysis_id: str,
        customer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get analysis by ID.
        
        Args:
            analysis_id: Analysis identifier
            customer_id: Customer ID for security check
            
        Returns:
            Analysis record as dict or None
        """
        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        analysis_id, customer_id, user_id, job_description,
                        ideal_candidate_description, status, error_message,
                        diagnostic_report, baseline_profile, synthesis_report,
                        overall_confidence, candidate_count, candidates,
                        created_at, started_at, completed_at, version
                    FROM talent_analyses
                    WHERE analysis_id = :analysis_id AND customer_id = :customer_id
                """),
                {"analysis_id": analysis_id, "customer_id": customer_id}
            ).fetchone()
            
            if not result:
                return None
            
            return {
                "analysis_id": result[0],
                "customer_id": result[1],
                "user_id": result[2],
                "job_description": result[3],
                "ideal_candidate_description": result[4],
                "status": result[5],
                "error_message": result[6],
                "diagnostic_report": result[7],
                "baseline_profile": result[8],
                "synthesis_report": result[9],
                "overall_confidence": result[10],
                "candidate_count": result[11],
                "candidates": result[12],
                "created_at": result[13],
                "started_at": result[14],
                "completed_at": result[15],
                "version": result[16]
            }
            
        except Exception as e:
            logger.error(
                "get_ml_talent_analysis_failed",
                analysis_id=analysis_id,
                error=str(e),
                exc_info=True
            )
            return None
    
    def update_analysis_status(
        self,
        analysis_id: str,
        status: AnalysisStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update analysis status.
        
        Args:
            analysis_id: Analysis identifier
            status: New status
            error_message: Optional error message
            
        Returns:
            True if updated, False otherwise
        """
        try:
            update_fields = {
                "analysis_id": analysis_id,
                "status": status.value,
                "updated_at": datetime.now(timezone.utc)
            }
            
            if status == AnalysisStatus.PROCESSING:
                update_fields["started_at"] = datetime.now(timezone.utc)
                query = text("""
                    UPDATE talent_analyses
                    SET status = :status, started_at = :started_at
                    WHERE analysis_id = :analysis_id
                """)
            elif status in [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]:
                update_fields["completed_at"] = datetime.now(timezone.utc)
                if error_message:
                    update_fields["error_message"] = error_message
                    query = text("""
                        UPDATE talent_analyses
                        SET status = :status, completed_at = :completed_at, error_message = :error_message
                        WHERE analysis_id = :analysis_id
                    """)
                else:
                    query = text("""
                        UPDATE talent_analyses
                        SET status = :status, completed_at = :completed_at
                        WHERE analysis_id = :analysis_id
                    """)
            else:
                query = text("""
                    UPDATE talent_analyses
                    SET status = :status
                    WHERE analysis_id = :analysis_id
                """)
            
            self.db.execute(query, update_fields)
            self.db.commit()
            
            logger.info(
                "ml_talent_analysis_status_updated",
                analysis_id=analysis_id,
                status=status.value
            )
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                "update_ml_talent_analysis_status_failed",
                analysis_id=analysis_id,
                error=str(e),
                exc_info=True
            )
            return False
    
    def store_analysis_result(
        self,
        analysis_id: str,
        result: TalentAnalysisResult,
        customer_id: Optional[str] = None
    ) -> bool:
        """
        Store complete analysis result.
        
        Stores both the legacy JSON blob (for backwards compatibility) and
        the new normalized candidate tables.
        
        Args:
            analysis_id: Analysis identifier
            result: Complete TalentAnalysisResult
            customer_id: Customer ID (required for new candidate storage)
            
        Returns:
            True if stored, False otherwise
        """
        try:
            # Prepare JSON data
            diagnostic_json = json.dumps(result.diagnostic_report.dict()) if result.diagnostic_report else None
            baseline_json = json.dumps(result.baseline_profile.dict()) if result.baseline_profile else None
            # Note: TalentAnalysisResult uses 'synthesis' but database column is 'synthesis_report'
            synthesis = getattr(result, 'synthesis', None) or getattr(result, 'synthesis_report', None)
            synthesis_json = json.dumps(synthesis.dict()) if synthesis else None
            
            # Note: TalentAnalysisResult uses different field names than the JSON structure
            # Model: applicant_results, market_results, top_overall
            # JSON: applicant_candidates, market_candidates, top_overall_candidates
            applicant_list = getattr(result, 'applicant_results', None) or getattr(result, 'applicant_candidates', [])
            market_list = getattr(result, 'market_results', None) or getattr(result, 'market_candidates', [])
            top_overall_list = getattr(result, 'top_overall', None) or getattr(result, 'top_overall_candidates', [])
            
            # Legacy JSON blob for backwards compatibility
            candidates_json = json.dumps({
                "applicant_candidates": [c.dict() for c in applicant_list],
                "market_candidates": [c.dict() for c in market_list],
                "top_overall_candidates": [c.dict() for c in top_overall_list]
            })
            
            self.db.execute(
                text("""
                    UPDATE talent_analyses
                    SET 
                        status = :status,
                        completed_at = :completed_at,
                        diagnostic_report = :diagnostic_report,
                        baseline_profile = :baseline_profile,
                        synthesis_report = :synthesis_report,
                        overall_confidence = :overall_confidence,
                        candidate_count = :candidate_count,
                        candidates = :candidates
                    WHERE analysis_id = :analysis_id
                """),
                {
                    "analysis_id": analysis_id,
                    "status": result.status.value,
                    "completed_at": datetime.now(timezone.utc),
                    "diagnostic_report": diagnostic_json,
                    "baseline_profile": baseline_json,
                    "synthesis_report": synthesis_json,
                    "overall_confidence": result.overall_confidence,
                    "candidate_count": len(applicant_list) + len(market_list),
                    "candidates": candidates_json
                }
            )
            self.db.commit()
            
            logger.info(
                "ml_talent_analysis_result_stored",
                analysis_id=analysis_id,
                applicant_count=len(applicant_list),
                market_count=len(market_list),
                overall_confidence=result.overall_confidence
            )
            
            # ================================================================
            # NEW: Store candidates in normalized tables
            # ================================================================
            if customer_id:
                try:
                    self._store_candidates_normalized(
                        analysis_id=analysis_id,
                        customer_id=customer_id,
                        applicant_candidates=applicant_list,
                        market_candidates=market_list
                    )
                except Exception as e:
                    # Log but don't fail the overall operation
                    logger.warning(
                        "normalized_candidate_storage_failed",
                        analysis_id=analysis_id,
                        error=str(e),
                        exc_info=True
                    )
            else:
                logger.warning(
                    "skipping_normalized_candidate_storage",
                    analysis_id=analysis_id,
                    reason="customer_id not provided"
                )
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                "store_ml_talent_analysis_result_failed",
                analysis_id=analysis_id,
                error=str(e),
                exc_info=True
            )
            return False
    
    def _store_candidates_normalized(
        self,
        analysis_id: str,
        customer_id: str,
        applicant_candidates: List[CandidateScore],
        market_candidates: List[CandidateScore]
    ) -> None:
        """
        Store candidates in the normalized candidates and candidate_analysis_scores tables.
        
        This is the new architecture:
        - candidates: Master table with profile data
        - candidate_analysis_scores: Scores per analysis
        """
        candidate_service = CandidateService(self.db, customer_id)
        
        all_candidates = [
            (c, "applicant") for c in applicant_candidates
        ] + [
            (c, "market") for c in market_candidates
        ]
        
        # Sort all candidates by score for ranking
        all_candidates.sort(key=lambda x: x[0].overall_score, reverse=True)
        
        # Track rankings
        applicant_rank = 0
        market_rank = 0
        
        for overall_rank, (candidate_score, source) in enumerate(all_candidates, start=1):
            try:
                # Increment source-specific rank
                if source == "applicant":
                    applicant_rank += 1
                    rank_in_source = applicant_rank
                else:
                    market_rank += 1
                    rank_in_source = market_rank
                
                # Upsert candidate profile
                greenhouse_id_value = getattr(candidate_score, 'greenhouse_id', None)
                logger.debug(
                    "storing_candidate_score",
                    candidate_id=candidate_score.candidate_id,
                    greenhouse_id=greenhouse_id_value,
                    greenhouse_id_type=type(greenhouse_id_value).__name__ if greenhouse_id_value else None,
                    email=getattr(candidate_score, 'email', None),
                    source=source
                )
                candidate = candidate_service.upsert_candidate(
                    email=getattr(candidate_score, 'email', None),
                    greenhouse_id=greenhouse_id_value,
                    pdl_id=getattr(candidate_score, 'pdl_id', None),
                    full_name=getattr(candidate_score, 'full_name', None),
                    phone=getattr(candidate_score, 'phone', None),
                    linkedin_url=getattr(candidate_score, 'linkedin_url', None),
                    location=getattr(candidate_score, 'location', None),
                    current_title=getattr(candidate_score, 'current_title', None),
                    current_company=getattr(candidate_score, 'current_company', None),
                    skills=getattr(candidate_score, 'skills', None),
                    experience=getattr(candidate_score, 'experience', None),
                    education=getattr(candidate_score, 'education', None),
                    certifications=getattr(candidate_score, 'certifications', None),
                    summary=getattr(candidate_score, 'summary', None),
                    source=source,
                    source_metadata={
                        "analysis_id": analysis_id,
                        "candidate_id": candidate_score.candidate_id
                    }
                )
                
                # Build score breakdown from dimensions
                dimensions = getattr(candidate_score, 'dimensions', [])
                score_breakdown = {
                    "dimensions": [
                        {
                            "dimension": d.dimension,
                            "score": d.score,
                            "explanation": d.explanation,
                            "evidence": getattr(d, 'evidence', [])
                        }
                        for d in dimensions
                    ] if dimensions else [],
                    "baseline_similarity": getattr(candidate_score, 'baseline_similarity', None),
                    "confidence": getattr(candidate_score, 'confidence', None)
                }
                
                # Save analysis score
                candidate_service.save_analysis_score(
                    candidate_id=candidate.id,
                    analysis_id=analysis_id,
                    overall_score=candidate_score.overall_score,
                    source=source,
                    score_breakdown=score_breakdown,
                    confidence=getattr(candidate_score, 'confidence', None),
                    patterns_matched=getattr(candidate_score, 'patterns_matched', None),
                    rank_overall=overall_rank,
                    rank_in_source=rank_in_source
                )
                
                logger.debug(
                    "candidate_stored_normalized",
                    candidate_id=candidate.id,
                    analysis_id=analysis_id,
                    overall_score=candidate_score.overall_score,
                    rank_overall=overall_rank
                )
                
            except Exception as e:
                logger.warning(
                    "candidate_storage_failed",
                    candidate_id=candidate_score.candidate_id,
                    analysis_id=analysis_id,
                    error=str(e),
                    exc_info=True
                )
        
        logger.info(
            "candidates_stored_normalized",
            analysis_id=analysis_id,
            total_count=len(all_candidates),
            applicant_count=len(applicant_candidates),
            market_count=len(market_candidates)
        )
    
    def store_feedback(
        self,
        analysis_id: str,
        user_id: int,
        feedback_type: str,
        feedback_data: Dict[str, Any]
    ) -> bool:
        """
        Store user feedback for an analysis.
        
        Args:
            analysis_id: Analysis identifier
            user_id: User providing feedback
            feedback_type: Type of feedback
            feedback_data: Feedback content
            
        Returns:
            True if stored, False otherwise
        """
        try:
            # Get analysis internal ID
            result = self.db.execute(
                text("SELECT id FROM talent_analyses WHERE analysis_id = :analysis_id"),
                {"analysis_id": analysis_id}
            ).fetchone()
            
            if not result:
                logger.warning("analysis_not_found_for_feedback", analysis_id=analysis_id)
                return False
            
            analysis_internal_id = result[0]
            
            self.db.execute(
                text("""
                    INSERT INTO talent_analysis_feedback (
                        analysis_id, user_id, feedback_type, feedback_data, created_at
                    ) VALUES (
                        :analysis_id, :user_id, :feedback_type, :feedback_data, :created_at
                    )
                """),
                {
                    "analysis_id": analysis_internal_id,
                    "user_id": user_id,
                    "feedback_type": feedback_type,
                    "feedback_data": json.dumps(feedback_data),
                    "created_at": datetime.now(timezone.utc)
                }
            )
            self.db.commit()
            
            logger.info(
                "ml_talent_feedback_stored",
                analysis_id=analysis_id,
                user_id=user_id,
                feedback_type=feedback_type
            )
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                "store_ml_talent_feedback_failed",
                analysis_id=analysis_id,
                error=str(e),
                exc_info=True
            )
            return False
    
    def list_analyses(
        self,
        customer_id: str,
        user_id: Optional[int] = None,
        status: Optional[AnalysisStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        List analyses with optional filters.
        
        Returns:
            Tuple of (analyses list, total count)
        """
        try:
            # Build query based on filters
            where_clauses = ["customer_id = :customer_id"]
            params = {"customer_id": customer_id, "limit": limit, "offset": offset}
            
            if user_id:
                where_clauses.append("user_id = :user_id")
                params["user_id"] = user_id
            
            if status:
                where_clauses.append("status = :status")
                params["status"] = status.value
            
            where_clause = " AND ".join(where_clauses)
            
            # Get total count
            count_result = self.db.execute(
                text(f"SELECT COUNT(*) FROM talent_analyses WHERE {where_clause}"),
                params
            ).fetchone()
            total = count_result[0] if count_result else 0
            
            # Get analyses
            results = self.db.execute(
                text(f"""
                    SELECT 
                        analysis_id, status, candidate_count, overall_confidence,
                        created_at, started_at, completed_at
                    FROM talent_analyses
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                params
            ).fetchall()
            
            analyses = [
                {
                    "analysis_id": row[0],
                    "status": row[1],
                    "candidate_count": row[2],
                    "overall_confidence": row[3],
                    "created_at": row[4],
                    "started_at": row[5],
                    "completed_at": row[6]
                }
                for row in results
            ]
            
            return analyses, total
            
        except Exception as e:
            logger.error(
                "list_ml_talent_analyses_failed",
                customer_id=customer_id,
                error=str(e),
                exc_info=True
            )
            return [], 0
    
    def list_analyses(
        self,
        customer_id: str,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List ML talent analyses for a customer.
        
        Args:
            customer_id: Customer organization ID
            offset: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter
            
        Returns:
            Dict with 'analyses' list and 'total' count
        """
        try:
            # Build query
            query = """
                SELECT 
                    analysis_id,
                    status,
                    created_at,
                    started_at,
                    completed_at,
                    job_description,
                    ideal_candidate_description,
                    candidate_count,
                    top_candidate_fit_score,
                    average_fit_score,
                    error_message,
                    version
                FROM talent_analyses
                WHERE customer_id = :customer_id
            """
            params = {"customer_id": customer_id, "offset": offset, "limit": limit}
            
            if status:
                query += " AND status = :status"
                params["status"] = status
            
            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM talent_analyses WHERE customer_id = :customer_id"
            if status:
                count_query += " AND status = :status"
            
            total_result = self.db.execute(text(count_query), {"customer_id": customer_id, "status": status} if status else {"customer_id": customer_id})
            total = total_result.fetchone()[0]
            
            # Get analyses
            query += " ORDER BY created_at DESC OFFSET :offset LIMIT :limit"
            result = self.db.execute(text(query), params)
            
            analyses = []
            for row in result:
                # Truncate job description for list view
                job_desc_preview = row.job_description[:200] + "..." if row.job_description and len(row.job_description) > 200 else row.job_description
                
                analyses.append({
                    "analysis_id": row.analysis_id,
                    "status": row.status,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                    "job_description_preview": job_desc_preview,
                    "candidate_count": row.candidate_count or 0,
                    "top_candidate_fit_score": row.top_candidate_fit_score,
                    "average_fit_score": row.average_fit_score,
                    "error_message": row.error_message,
                    "version": row.version
                })
            
            return {
                "analyses": analyses,
                "total": total
            }
            
        except Exception as e:
            logger.error(
                "list_ml_talent_analyses_failed",
                customer_id=customer_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def get_analysis(
        self,
        analysis_id: str,
        customer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single ML talent analysis.
        
        Args:
            analysis_id: Analysis ID
            customer_id: Customer organization ID (for authorization)
            
        Returns:
            Analysis record as dict, or None if not found
        """
        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        analysis_id,
                        customer_id,
                        user_id,
                        status,
                        created_at,
                        started_at,
                        completed_at,
                        job_description,
                        ideal_candidate_description,
                        manual_persona,
                        ideal_persona,
                        candidates,
                        insights_report,
                        candidate_count,
                        top_candidate_fit_score,
                        average_fit_score,
                        error_message,
                        diagnostic_report,
                        baseline_profile,
                        synthesis_report,
                        overall_confidence,
                        version
                    FROM talent_analyses
                    WHERE analysis_id = :analysis_id AND customer_id = :customer_id
                """),
                {"analysis_id": analysis_id, "customer_id": customer_id}
            )
            
            row = result.fetchone()
            if not row:
                return None
            
            return {
                "analysis_id": row.analysis_id,
                "customer_id": row.customer_id,
                "user_id": row.user_id,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "job_description": row.job_description,
                "ideal_candidate_description": row.ideal_candidate_description,
                "manual_persona": self._safe_json_load(row.manual_persona),
                "ideal_persona": self._safe_json_load(row.ideal_persona),
                "candidates": self._safe_json_load(row.candidates),
                "insights_report": self._safe_json_load(row.insights_report),
                "candidate_count": row.candidate_count or 0,
                "top_candidate_fit_score": row.top_candidate_fit_score,
                "average_fit_score": row.average_fit_score,
                "error_message": row.error_message,
                "diagnostic_report": self._safe_json_load(row.diagnostic_report),
                "baseline_profile": self._safe_json_load(row.baseline_profile),
                "synthesis_report": self._safe_json_load(row.synthesis_report),
                "overall_confidence": row.overall_confidence,
                "version": row.version
            }
            
        except Exception as e:
            logger.error(
                "get_ml_talent_analysis_failed",
                analysis_id=analysis_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def create_analysis_event(
        self,
        analysis_id: str,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Create a talent analysis event for SSE streaming.
        
        Uses an independent database session to ensure events are persisted
        even if the main analysis transaction fails.
        
        Args:
            analysis_id: Analysis ID
            event_type: Event type (e.g., 'analysis_started', 'agent_1_started', 'analysis_failed')
            message: Human-readable message
            metadata: Optional metadata dictionary
        """
        from src.models import database
        from datetime import datetime, timezone
        
        # Use a NEW, independent session for each event to avoid transaction conflicts
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        try:
            # Insert event into database
            db.execute(
                text("""
                    INSERT INTO talent_analysis_events 
                    (analysis_id, event_type, message, data, timestamp)
                    VALUES (:analysis_id, :event_type, :message, :data, :timestamp)
                """),
                {
                    "analysis_id": analysis_id,
                    "event_type": event_type,
                    "message": message,
                    "data": json.dumps(metadata) if metadata else None,
                    "timestamp": datetime.now(timezone.utc)
                }
            )
            db.commit()
            
            logger.debug(
                "talent_analysis_event_created",
                analysis_id=analysis_id,
                event_type=event_type
            )
            
        except Exception as e:
            db.rollback()
            logger.error(
                "create_talent_analysis_event_failed",
                analysis_id=analysis_id,
                event_type=event_type,
                error=str(e),
                exc_info=True
            )
            # Don't re-raise - event creation failure shouldn't stop analysis
        finally:
            db.close()

