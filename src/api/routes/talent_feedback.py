"""
Talent Feedback API Routes

API endpoints for submitting and managing user feedback about the Talent Intelligence system.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from src.models.database import get_db
from src.models.talent_feedback import (
    TalentFeedback,
    FeedbackType,
    FeedbackCategory,
    FeedbackPriority,
    FeedbackStatus
)
from src.middleware.authorization import get_current_user
from src.core.auth_context import CurrentUserContext
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.API)
router = APIRouter(prefix="/api/v1/talent/feedback", tags=["Talent Feedback"])


# Request/Response Models
class SubmitFeedbackRequest(BaseModel):
    """Request to submit feedback"""
    feedback_type: str = Field(description="Type of feedback: feature_request, bug_report, general_feedback, model_improvement")
    category: Optional[str] = Field(None, description="Category: resume_parsing, scoring, search, ui_ux, performance, accuracy, other")
    title: str = Field(description="Brief title/summary of feedback", max_length=255)
    description: str = Field(description="Detailed description of the feedback")
    analysis_id: Optional[str] = Field(None, description="Related analysis ID if applicable")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating from 1-5 if providing satisfaction feedback")
    metadata: Optional[dict] = Field(None, description="Additional context (browser, version, etc)")


class FeedbackResponse(BaseModel):
    """Response with feedback details"""
    id: int
    customer_id: str
    user_id: int
    feedback_type: str
    category: Optional[str]
    title: str
    description: str
    analysis_id: Optional[str]
    rating: Optional[int]
    priority: str
    status: str
    admin_notes: Optional[str]
    metadata: Optional[dict]
    created_at: datetime
    updated_at: Optional[datetime]
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]


class FeedbackListResponse(BaseModel):
    """Response with list of feedback"""
    feedback: List[FeedbackResponse]
    total: int
    page: int
    page_size: int
    pages: int


class UpdateFeedbackStatusRequest(BaseModel):
    """Request to update feedback status (admin only)"""
    status: str = Field(description="New status: submitted, reviewed, in_progress, completed, declined")
    priority: Optional[str] = Field(None, description="New priority: low, medium, high, critical")
    admin_notes: Optional[str] = Field(None, description="Admin notes/response")


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/submit",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback",
    description="Submit feedback about the Talent Intelligence system"
)
async def submit_feedback(
    request: SubmitFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Submit user feedback about the Talent Intelligence system.
    
    Types of feedback:
    - feature_request: Request for new features
    - bug_report: Report bugs or issues
    - general_feedback: General comments or suggestions
    - model_improvement: Suggestions for improving AI models/prompts
    
    Categories:
    - resume_parsing: Issues with resume extraction
    - scoring: Candidate scoring accuracy
    - search: Market search functionality
    - ui_ux: User interface/experience
    - performance: Speed/performance issues
    - accuracy: Result accuracy concerns
    - other: Other feedback
    """
    logger.info(
        "feedback_submission_received",
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        feedback_type=request.feedback_type,
        category=request.category
    )
    
    try:
        # Create feedback record
        feedback = TalentFeedback(
            customer_id=current_user.customer_id,
            user_id=current_user.user_id,
            feedback_type=request.feedback_type,
            category=request.category,
            title=request.title,
            description=request.description,
            analysis_id=request.analysis_id,
            rating=request.rating,
            priority=FeedbackPriority.MEDIUM.value,  # Default priority
            status=FeedbackStatus.SUBMITTED.value,
            metadata=request.metadata
        )
        
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        logger.info(
            "feedback_submitted_successfully",
            feedback_id=feedback.id,
            user_id=current_user.user_id,
            feedback_type=request.feedback_type
        )
        
        return FeedbackResponse(**feedback.to_dict())
        
    except Exception as e:
        db.rollback()
        logger.error(
            "feedback_submission_failed",
            error=str(e),
            user_id=current_user.user_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )


@router.get(
    "/my-feedback",
    response_model=FeedbackListResponse,
    summary="Get my feedback",
    description="Get feedback submitted by the current user"
)
async def get_my_feedback(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    feedback_type: Optional[str] = Query(None, description="Filter by type"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Get all feedback submitted by the current user"""
    
    try:
        # Build query
        query = db.query(TalentFeedback).filter(
            TalentFeedback.customer_id == current_user.customer_id,
            TalentFeedback.user_id == current_user.user_id
        )
        
        # Apply filters
        if feedback_type:
            query = query.filter(TalentFeedback.feedback_type == feedback_type)
        if status_filter:
            query = query.filter(TalentFeedback.status == status_filter)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        feedback_items = query.order_by(TalentFeedback.created_at.desc()).offset(offset).limit(page_size).all()
        
        # Calculate pages
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return FeedbackListResponse(
            feedback=[FeedbackResponse(**f.to_dict()) for f in feedback_items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages
        )
        
    except Exception as e:
        logger.error(
            "failed_to_fetch_my_feedback",
            error=str(e),
            user_id=current_user.user_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch feedback: {str(e)}"
        )


@router.get(
    "/all",
    response_model=FeedbackListResponse,
    summary="Get all feedback (Admin)",
    description="Get all feedback from all users (admin only)"
)
async def get_all_feedback(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    feedback_type: Optional[str] = Query(None, description="Filter by type"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Get all feedback (admin only)"""
    
    # Check if user has admin permissions
    if not current_user.is_superuser and "system:admin" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        # Build query
        query = db.query(TalentFeedback).filter(
            TalentFeedback.customer_id == current_user.customer_id
        )
        
        # Apply filters
        if feedback_type:
            query = query.filter(TalentFeedback.feedback_type == feedback_type)
        if status_filter:
            query = query.filter(TalentFeedback.status == status_filter)
        if priority:
            query = query.filter(TalentFeedback.priority == priority)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        feedback_items = query.order_by(TalentFeedback.created_at.desc()).offset(offset).limit(page_size).all()
        
        # Calculate pages
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return FeedbackListResponse(
            feedback=[FeedbackResponse(**f.to_dict()) for f in feedback_items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "failed_to_fetch_all_feedback",
            error=str(e),
            user_id=current_user.user_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch feedback: {str(e)}"
        )


@router.put(
    "/{feedback_id}/status",
    response_model=FeedbackResponse,
    summary="Update feedback status (Admin)",
    description="Update feedback status and priority (admin only)"
)
async def update_feedback_status(
    feedback_id: int,
    request: UpdateFeedbackStatusRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Update feedback status (admin only)"""
    
    # Check if user has admin permissions
    if not current_user.is_superuser and "system:admin" not in current_user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        # Get feedback
        feedback = db.query(TalentFeedback).filter(
            TalentFeedback.id == feedback_id,
            TalentFeedback.customer_id == current_user.customer_id
        ).first()
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
        
        # Update fields
        feedback.status = request.status
        if request.priority:
            feedback.priority = request.priority
        if request.admin_notes:
            feedback.admin_notes = request.admin_notes
        
        feedback.reviewed_by = current_user.user_id
        feedback.reviewed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(feedback)
        
        logger.info(
            "feedback_status_updated",
            feedback_id=feedback_id,
            new_status=request.status,
            reviewed_by=current_user.user_id
        )
        
        return FeedbackResponse(**feedback.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            "failed_to_update_feedback_status",
            error=str(e),
            feedback_id=feedback_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update feedback: {str(e)}"
        )

