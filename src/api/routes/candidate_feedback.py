"""
Candidate Score Feedback API Routes

Endpoints for submitting and retrieving user feedback on candidate scores.
This feedback is used to tune the scoring algorithm.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from src.models import get_db, CandidateScoreFeedback, CandidateAnalysisScore, Candidate
from src.middleware.authorization import AuthorizationMiddleware
from src.core.auth_context import CurrentUserContext


logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/candidate-feedback", tags=["candidate-feedback"])
auth_middleware = AuthorizationMiddleware()


# ============================================================================
# Pydantic Schemas
# ============================================================================

class DimensionFeedbackItem(BaseModel):
    """Feedback for a single scoring dimension."""
    dimension: str = Field(..., description="Name of the scoring dimension")
    accuracy: str = Field(..., description="How accurate was this score", pattern="^(too_high|accurate|too_low)$")
    

class FeedbackCreate(BaseModel):
    """Request schema for creating feedback."""
    candidate_analysis_score_id: int = Field(..., description="ID of the candidate analysis score")
    user_rating: int = Field(..., ge=1, le=5, description="Overall rating 1-5 stars")
    would_interview: Optional[str] = Field(None, pattern="^(definitely|probably|maybe|no)$", description="Would you interview this candidate?")
    dimension_feedback: Optional[Dict[str, str]] = Field(None, description="Feedback per dimension: {dimension: 'too_high'|'accurate'|'too_low'}")
    feedback_notes: Optional[str] = Field(None, max_length=2000, description="Optional notes")
    action_taken: Optional[str] = Field(None, pattern="^(contacted|interviewed|hired|rejected|no_action)$", description="Action taken on candidate")


class FeedbackUpdate(BaseModel):
    """Request schema for updating feedback."""
    user_rating: Optional[int] = Field(None, ge=1, le=5, description="Overall rating 1-5 stars")
    would_interview: Optional[str] = Field(None, pattern="^(definitely|probably|maybe|no)$")
    dimension_feedback: Optional[Dict[str, str]] = Field(None)
    feedback_notes: Optional[str] = Field(None, max_length=2000)
    action_taken: Optional[str] = Field(None, pattern="^(contacted|interviewed|hired|rejected|no_action)$")


class FeedbackResponse(BaseModel):
    """Response schema for feedback."""
    id: int
    candidate_analysis_score_id: int
    user_id: Optional[int]
    customer_id: str
    user_rating: int
    would_interview: Optional[str]
    dimension_feedback: Optional[Dict[str, str]]
    feedback_notes: Optional[str]
    action_taken: Optional[str]
    created_at: str
    updated_at: str
    
    # Include candidate info for context
    candidate_name: Optional[str] = None
    candidate_score: Optional[float] = None
    analysis_id: Optional[str] = None

    class Config:
        from_attributes = True


class FeedbackStatsResponse(BaseModel):
    """Response schema for feedback statistics."""
    total_feedback: int
    average_rating: float
    rating_distribution: Dict[int, int]  # {1: count, 2: count, ...}
    would_interview_distribution: Dict[str, int]
    action_distribution: Dict[str, int]
    dimension_accuracy: Dict[str, Dict[str, int]]  # {dimension: {too_high: x, accurate: y, too_low: z}}


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback on a candidate score",
    description="Submit feedback on how accurate a candidate's score was. Used to tune scoring algorithm."
)
async def create_feedback(
    feedback: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Create feedback for a candidate score."""
    # Verify the score exists and belongs to user's customer
    score = db.query(CandidateAnalysisScore).filter(
        CandidateAnalysisScore.id == feedback.candidate_analysis_score_id
    ).first()
    
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate score not found"
        )
    
    # Get candidate to verify customer_id
    candidate = db.query(Candidate).filter(Candidate.id == score.candidate_id).first()
    if not candidate or candidate.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to provide feedback on this candidate"
        )
    
    # Check if user already provided feedback
    existing = db.query(CandidateScoreFeedback).filter(
        CandidateScoreFeedback.candidate_analysis_score_id == feedback.candidate_analysis_score_id,
        CandidateScoreFeedback.user_id == current_user.user_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already provided feedback for this candidate. Use PUT to update."
        )
    
    # Create feedback
    db_feedback = CandidateScoreFeedback(
        candidate_analysis_score_id=feedback.candidate_analysis_score_id,
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        user_rating=feedback.user_rating,
        would_interview=feedback.would_interview,
        dimension_feedback=feedback.dimension_feedback,
        feedback_notes=feedback.feedback_notes,
        action_taken=feedback.action_taken
    )
    
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    
    logger.info(
        "candidate_feedback_created",
        feedback_id=db_feedback.id,
        score_id=feedback.candidate_analysis_score_id,
        user_id=current_user.user_id,
        rating=feedback.user_rating
    )
    
    return FeedbackResponse(
        id=db_feedback.id,
        candidate_analysis_score_id=db_feedback.candidate_analysis_score_id,
        user_id=db_feedback.user_id,
        customer_id=db_feedback.customer_id,
        user_rating=db_feedback.user_rating,
        would_interview=db_feedback.would_interview,
        dimension_feedback=db_feedback.dimension_feedback,
        feedback_notes=db_feedback.feedback_notes,
        action_taken=db_feedback.action_taken,
        created_at=db_feedback.created_at.isoformat(),
        updated_at=db_feedback.updated_at.isoformat(),
        candidate_name=candidate.full_name,
        candidate_score=score.overall_score,
        analysis_id=score.analysis_id
    )


@router.get(
    "/score/{score_id}",
    response_model=Optional[FeedbackResponse],
    summary="Get feedback for a specific score",
    description="Get the current user's feedback for a specific candidate score, if any."
)
async def get_feedback_for_score(
    score_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get feedback for a specific score."""
    feedback = db.query(CandidateScoreFeedback).filter(
        CandidateScoreFeedback.candidate_analysis_score_id == score_id,
        CandidateScoreFeedback.user_id == current_user.user_id
    ).first()
    
    if not feedback:
        return None
    
    # Get candidate and score info
    score = db.query(CandidateAnalysisScore).filter(CandidateAnalysisScore.id == score_id).first()
    candidate = db.query(Candidate).filter(Candidate.id == score.candidate_id).first() if score else None
    
    return FeedbackResponse(
        id=feedback.id,
        candidate_analysis_score_id=feedback.candidate_analysis_score_id,
        user_id=feedback.user_id,
        customer_id=feedback.customer_id,
        user_rating=feedback.user_rating,
        would_interview=feedback.would_interview,
        dimension_feedback=feedback.dimension_feedback,
        feedback_notes=feedback.feedback_notes,
        action_taken=feedback.action_taken,
        created_at=feedback.created_at.isoformat(),
        updated_at=feedback.updated_at.isoformat(),
        candidate_name=candidate.full_name if candidate else None,
        candidate_score=score.overall_score if score else None,
        analysis_id=score.analysis_id if score else None
    )


@router.put(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    summary="Update existing feedback",
    description="Update your feedback for a candidate score."
)
async def update_feedback(
    feedback_id: int,
    update: FeedbackUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Update existing feedback."""
    feedback = db.query(CandidateScoreFeedback).filter(
        CandidateScoreFeedback.id == feedback_id,
        CandidateScoreFeedback.user_id == current_user.user_id
    ).first()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found or you don't have permission to update it"
        )
    
    # Update fields
    if update.user_rating is not None:
        feedback.user_rating = update.user_rating
    if update.would_interview is not None:
        feedback.would_interview = update.would_interview
    if update.dimension_feedback is not None:
        feedback.dimension_feedback = update.dimension_feedback
    if update.feedback_notes is not None:
        feedback.feedback_notes = update.feedback_notes
    if update.action_taken is not None:
        feedback.action_taken = update.action_taken
    
    db.commit()
    db.refresh(feedback)
    
    logger.info(
        "candidate_feedback_updated",
        feedback_id=feedback_id,
        user_id=current_user.user_id
    )
    
    # Get candidate and score info
    score = db.query(CandidateAnalysisScore).filter(
        CandidateAnalysisScore.id == feedback.candidate_analysis_score_id
    ).first()
    candidate = db.query(Candidate).filter(Candidate.id == score.candidate_id).first() if score else None
    
    return FeedbackResponse(
        id=feedback.id,
        candidate_analysis_score_id=feedback.candidate_analysis_score_id,
        user_id=feedback.user_id,
        customer_id=feedback.customer_id,
        user_rating=feedback.user_rating,
        would_interview=feedback.would_interview,
        dimension_feedback=feedback.dimension_feedback,
        feedback_notes=feedback.feedback_notes,
        action_taken=feedback.action_taken,
        created_at=feedback.created_at.isoformat(),
        updated_at=feedback.updated_at.isoformat(),
        candidate_name=candidate.full_name if candidate else None,
        candidate_score=score.overall_score if score else None,
        analysis_id=score.analysis_id if score else None
    )


@router.get(
    "/stats",
    response_model=FeedbackStatsResponse,
    summary="Get feedback statistics",
    description="Get aggregated feedback statistics for the customer."
)
async def get_feedback_stats(
    analysis_id: Optional[str] = Query(None, description="Filter by analysis ID"),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get aggregated feedback statistics."""
    query = db.query(CandidateScoreFeedback).filter(
        CandidateScoreFeedback.customer_id == current_user.customer_id
    )
    
    if analysis_id:
        # Join with scores to filter by analysis
        query = query.join(CandidateAnalysisScore).filter(
            CandidateAnalysisScore.analysis_id == analysis_id
        )
    
    feedbacks = query.all()
    
    if not feedbacks:
        return FeedbackStatsResponse(
            total_feedback=0,
            average_rating=0.0,
            rating_distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            would_interview_distribution={},
            action_distribution={},
            dimension_accuracy={}
        )
    
    # Calculate statistics
    total = len(feedbacks)
    avg_rating = sum(f.user_rating for f in feedbacks) / total
    
    rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    interview_dist: Dict[str, int] = {}
    action_dist: Dict[str, int] = {}
    dimension_accuracy: Dict[str, Dict[str, int]] = {}
    
    for f in feedbacks:
        # Rating distribution
        rating_dist[f.user_rating] = rating_dist.get(f.user_rating, 0) + 1
        
        # Would interview distribution
        if f.would_interview:
            interview_dist[f.would_interview] = interview_dist.get(f.would_interview, 0) + 1
        
        # Action distribution
        if f.action_taken:
            action_dist[f.action_taken] = action_dist.get(f.action_taken, 0) + 1
        
        # Dimension feedback aggregation
        if f.dimension_feedback:
            for dim, accuracy in f.dimension_feedback.items():
                if dim not in dimension_accuracy:
                    dimension_accuracy[dim] = {"too_high": 0, "accurate": 0, "too_low": 0}
                if accuracy in dimension_accuracy[dim]:
                    dimension_accuracy[dim][accuracy] += 1
    
    return FeedbackStatsResponse(
        total_feedback=total,
        average_rating=round(avg_rating, 2),
        rating_distribution=rating_dist,
        would_interview_distribution=interview_dist,
        action_distribution=action_dist,
        dimension_accuracy=dimension_accuracy
    )


@router.get(
    "",
    response_model=List[FeedbackResponse],
    summary="List all feedback",
    description="List all feedback for the customer with optional filters."
)
async def list_feedback(
    analysis_id: Optional[str] = Query(None, description="Filter by analysis ID"),
    min_rating: Optional[int] = Query(None, ge=1, le=5, description="Minimum rating filter"),
    max_rating: Optional[int] = Query(None, ge=1, le=5, description="Maximum rating filter"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List all feedback with filters."""
    query = db.query(CandidateScoreFeedback).filter(
        CandidateScoreFeedback.customer_id == current_user.customer_id
    )
    
    if analysis_id:
        query = query.join(CandidateAnalysisScore).filter(
            CandidateAnalysisScore.analysis_id == analysis_id
        )
    
    if min_rating:
        query = query.filter(CandidateScoreFeedback.user_rating >= min_rating)
    
    if max_rating:
        query = query.filter(CandidateScoreFeedback.user_rating <= max_rating)
    
    feedbacks = query.order_by(CandidateScoreFeedback.created_at.desc()).offset(offset).limit(limit).all()
    
    results = []
    for f in feedbacks:
        score = db.query(CandidateAnalysisScore).filter(
            CandidateAnalysisScore.id == f.candidate_analysis_score_id
        ).first()
        candidate = db.query(Candidate).filter(Candidate.id == score.candidate_id).first() if score else None
        
        results.append(FeedbackResponse(
            id=f.id,
            candidate_analysis_score_id=f.candidate_analysis_score_id,
            user_id=f.user_id,
            customer_id=f.customer_id,
            user_rating=f.user_rating,
            would_interview=f.would_interview,
            dimension_feedback=f.dimension_feedback,
            feedback_notes=f.feedback_notes,
            action_taken=f.action_taken,
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat(),
            candidate_name=candidate.full_name if candidate else None,
            candidate_score=score.overall_score if score else None,
            analysis_id=score.analysis_id if score else None
        ))
    
    return results


@router.delete(
    "/{feedback_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete feedback",
    description="Delete your feedback for a candidate score."
)
async def delete_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Delete feedback."""
    feedback = db.query(CandidateScoreFeedback).filter(
        CandidateScoreFeedback.id == feedback_id,
        CandidateScoreFeedback.user_id == current_user.user_id
    ).first()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found or you don't have permission to delete it"
        )
    
    db.delete(feedback)
    db.commit()
    
    logger.info(
        "candidate_feedback_deleted",
        feedback_id=feedback_id,
        user_id=current_user.user_id
    )
    
    return None

