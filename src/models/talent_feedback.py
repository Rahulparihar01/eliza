"""
Talent Feedback Model

Database model for storing user feedback about the Talent Intelligence system.
Used to collect feature requests, bug reports, and improvement suggestions.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from .database import Base


class FeedbackType(str, Enum):
    """Types of feedback"""
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    GENERAL_FEEDBACK = "general_feedback"
    MODEL_IMPROVEMENT = "model_improvement"


class FeedbackCategory(str, Enum):
    """Categories for feedback"""
    RESUME_PARSING = "resume_parsing"
    SCORING = "scoring"
    SEARCH = "search"
    UI_UX = "ui_ux"
    PERFORMANCE = "performance"
    ACCURACY = "accuracy"
    OTHER = "other"


class FeedbackPriority(str, Enum):
    """Priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FeedbackStatus(str, Enum):
    """Feedback status"""
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"


class TalentFeedback(Base):
    """User feedback for Talent Intelligence system"""
    
    __tablename__ = 'talent_feedback'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Feedback details
    feedback_type = Column(String(50), nullable=False)
    category = Column(String(100), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Context
    analysis_id = Column(String(100), nullable=True)  # Link to specific analysis
    rating = Column(Integer, nullable=True)  # 1-5 rating
    priority = Column(String(20), default=FeedbackPriority.MEDIUM.value)
    
    # Status tracking
    status = Column(String(20), default=FeedbackStatus.SUBMITTED.value)
    admin_notes = Column(Text, nullable=True)
    
    # Additional metadata (using feedback_metadata to avoid SQLAlchemy reserved name)
    feedback_metadata = Column('metadata', JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Review tracking
    reviewed_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="talent_feedback")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_feedback")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'user_id': self.user_id,
            'feedback_type': self.feedback_type,
            'category': self.category,
            'title': self.title,
            'description': self.description,
            'analysis_id': self.analysis_id,
            'rating': self.rating,
            'priority': self.priority,
            'status': self.status,
            'admin_notes': self.admin_notes,
            'metadata': self.feedback_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
        }

