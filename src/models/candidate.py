"""
Candidate Models

SQLAlchemy models for the candidate database:
- Candidate: Master candidate table with profile data
- CandidateAnalysisScore: Scores per candidate per analysis
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Text, DateTime, ForeignKey,
    UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.database import Base


class Candidate(Base):
    """
    Master candidate table.
    
    Stores candidate profile data independent of any specific analysis.
    Same candidate can be scored in multiple analyses.
    """
    __tablename__ = 'candidates'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(100), ForeignKey('customers.customer_id'), nullable=False)
    
    # Identity (for deduplication)
    email = Column(String(255), nullable=True)
    greenhouse_id = Column(BigInteger, nullable=True)  # Greenhouse IDs can exceed INT max
    pdl_id = Column(String(100), nullable=True)
    
    # Profile Data
    full_name = Column(String(255), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)
    
    # Current Employment
    current_title = Column(String(255), nullable=True)
    current_company = Column(String(255), nullable=True)
    
    # Parsed Resume Data (flexible JSONB)
    skills = Column(JSONB, nullable=True)
    experience = Column(JSONB, nullable=True)
    education = Column(JSONB, nullable=True)
    certifications = Column(JSONB, nullable=True)
    summary = Column(Text, nullable=True)
    
    # Source Tracking
    source = Column(String(50), nullable=True)  # 'greenhouse', 'pdl', 'upload', 'manual'
    source_metadata = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    load_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    analysis_scores = relationship("CandidateAnalysisScore", back_populates="candidate", cascade="all, delete-orphan")
    
    # Table arguments for unique constraints
    __table_args__ = (
        UniqueConstraint('customer_id', 'email', name='uq_candidate_customer_email'),
        Index('ix_candidates_customer_id', 'customer_id'),
        Index('ix_candidates_email', 'email'),
        Index('ix_candidates_greenhouse_id', 'greenhouse_id'),
        Index('ix_candidates_pdl_id', 'pdl_id'),
        Index('ix_candidates_full_name', 'full_name'),
    )
    
    def __repr__(self):
        return f"<Candidate(id={self.id}, name='{self.full_name}', email='{self.email}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "email": self.email,
            "greenhouse_id": self.greenhouse_id,
            "pdl_id": self.pdl_id,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "linkedin_url": self.linkedin_url,
            "github_url": self.github_url,
            "location": self.location,
            "current_title": self.current_title,
            "current_company": self.current_company,
            "skills": self.skills,
            "experience": self.experience,
            "education": self.education,
            "certifications": self.certifications,
            "summary": self.summary,
            "source": self.source,
            "load_date": self.load_date.isoformat() if self.load_date else None,
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
        }


class CandidateScoreFeedback(Base):
    """
    User feedback on candidate scores.
    
    Allows users to rate how accurate the scoring was for a candidate,
    which can be used to tune the scoring algorithm.
    """
    __tablename__ = 'candidate_score_feedback'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Relationships
    candidate_analysis_score_id = Column(Integer, ForeignKey('candidate_analysis_scores.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    customer_id = Column(String(100), ForeignKey('customers.customer_id', ondelete='CASCADE'), nullable=False)
    
    # User's assessment of the candidate
    user_rating = Column(Integer, nullable=False)  # 1-5 stars
    would_interview = Column(String(20), nullable=True)  # 'definitely', 'probably', 'maybe', 'no'
    
    # Dimension-specific feedback (which scores were off)
    dimension_feedback = Column(JSONB, nullable=True)  # {"skill_alignment": "too_high", "experience_fit": "accurate", ...}
    
    # Free-form feedback
    feedback_notes = Column(Text, nullable=True)
    
    # What action did they take?
    action_taken = Column(String(50), nullable=True)  # 'contacted', 'interviewed', 'hired', 'rejected', 'no_action'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    candidate_analysis_score = relationship("CandidateAnalysisScore", backref="feedback")
    
    # Table arguments
    __table_args__ = (
        UniqueConstraint('candidate_analysis_score_id', 'user_id', name='uq_feedback_score_user'),
        Index('ix_csf_score_id', 'candidate_analysis_score_id'),
        Index('ix_csf_customer_id', 'customer_id'),
        Index('ix_csf_user_rating', 'user_rating'),
        Index('ix_csf_would_interview', 'would_interview'),
    )
    
    def __repr__(self):
        return f"<CandidateScoreFeedback(id={self.id}, score_id={self.candidate_analysis_score_id}, rating={self.user_rating})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "candidate_analysis_score_id": self.candidate_analysis_score_id,
            "user_id": self.user_id,
            "customer_id": self.customer_id,
            "user_rating": self.user_rating,
            "would_interview": self.would_interview,
            "dimension_feedback": self.dimension_feedback,
            "feedback_notes": self.feedback_notes,
            "action_taken": self.action_taken,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CandidateAnalysisScore(Base):
    """
    Candidate scores for a specific analysis.
    
    Links a candidate to an analysis with their scores and outreach status.
    Same candidate can have different scores in different analyses.
    """
    __tablename__ = 'candidate_analysis_scores'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Relationships
    candidate_id = Column(Integer, ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False)
    analysis_id = Column(String(100), ForeignKey('talent_analyses.analysis_id', ondelete='CASCADE'), nullable=False)
    
    # Scoring (fixed fields)
    overall_score = Column(Float, nullable=False)
    rank_overall = Column(Integer, nullable=True)
    rank_in_source = Column(Integer, nullable=True)
    source = Column(String(50), nullable=False)  # 'applicant', 'market', or 'previous_candidate'
    confidence = Column(Float, nullable=True)
    
    # Scoring details (flexible JSONB)
    score_breakdown = Column(JSONB, nullable=False)
    patterns_matched = Column(JSONB, nullable=True)
    match_metadata = Column(JSONB, nullable=True)
    
    # Generated Email
    email_template_id = Column(Integer, ForeignKey('email_templates.id', ondelete='SET NULL'), nullable=True)
    generated_email_subject = Column(String(500), nullable=True)
    generated_email_body = Column(Text, nullable=True)
    email_generated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Outreach Status
    outreach_status = Column(String(50), server_default='pending', nullable=False)
    outreach_sent_at = Column(DateTime(timezone=True), nullable=True)
    outreach_notes = Column(Text, nullable=True)
    
    # Timestamps
    scored_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="analysis_scores")
    analysis = relationship("TalentAnalysis", backref="candidate_scores")
    email_template = relationship("EmailTemplate", backref="generated_emails")
    
    # Table arguments
    __table_args__ = (
        UniqueConstraint('candidate_id', 'analysis_id', name='uq_candidate_analysis'),
        Index('ix_cas_analysis_id', 'analysis_id'),
        Index('ix_cas_candidate_id', 'candidate_id'),
        Index('ix_cas_analysis_score', 'analysis_id', 'overall_score'),
        Index('ix_cas_analysis_rank', 'analysis_id', 'rank_overall'),
        Index('ix_cas_outreach_status', 'outreach_status'),
        Index('ix_cas_source', 'source'),
    )
    
    def __repr__(self):
        return f"<CandidateAnalysisScore(candidate_id={self.candidate_id}, analysis_id='{self.analysis_id}', score={self.overall_score})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "analysis_id": self.analysis_id,
            "overall_score": self.overall_score,
            "rank_overall": self.rank_overall,
            "rank_in_source": self.rank_in_source,
            "source": self.source,
            "confidence": self.confidence,
            "score_breakdown": self.score_breakdown,
            "patterns_matched": self.patterns_matched,
            "outreach_status": self.outreach_status,
            "outreach_sent_at": self.outreach_sent_at.isoformat() if self.outreach_sent_at else None,
            "email_template_id": self.email_template_id,
            "generated_email_subject": self.generated_email_subject,
            "email_generated_at": self.email_generated_at.isoformat() if self.email_generated_at else None,
            "scored_at": self.scored_at.isoformat() if self.scored_at else None,
        }

