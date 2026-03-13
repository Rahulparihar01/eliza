"""
Analysis Configuration Model

SQLAlchemy model for persistent storage of talent analysis configurations.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.database import Base


class AnalysisConfig(Base):
    """
    Persistent storage for analysis configurations.
    
    Allows users to save, edit, and reuse analysis configurations
    without having to recreate them from scratch.
    """
    __tablename__ = 'analysis_configs'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(100), ForeignKey('customers.customer_id', ondelete='CASCADE'), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Configuration details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Related entities (foreign keys)
    blueprint_id = Column(Integer, ForeignKey('career_blueprints.id', ondelete='SET NULL'), nullable=True)
    company_dna_id = Column(Integer, ForeignKey('company_dna_profiles.id', ondelete='SET NULL'), nullable=True)
    ats_connection_id = Column(Integer, ForeignKey('connector_configurations.id', ondelete='SET NULL'), nullable=True)
    selected_job_id = Column(String(100), nullable=True)  # Job ID from ATS
    
    # Configuration content
    job_description = Column(Text, nullable=True)
    ideal_candidate_details = Column(Text, nullable=True)  # JSON string with structured details
    department_ids = Column(JSONB, nullable=True)  # Array of department IDs for candidate source
    candidate_source_mode = Column(String(20), nullable=True, default='ats')  # 'ats' or 'upload'
    uploaded_resume_files = Column(JSONB, nullable=True)  # Array of uploaded resume filenames
    market_search_limit = Column(Integer, nullable=True, default=50)  # Number of candidates to fetch from market search
    max_candidate_fetch = Column(Integer, nullable=True, default=100)  # Max candidates to fetch from ATS
    
    # Historical candidate settings (previous candidates from closed jobs)
    include_historical_candidates = Column(Boolean, nullable=False, default=False)  # Whether to include candidates from closed jobs
    historical_lookback_days = Column(Integer, nullable=True, default=365)  # How far back to look for historical candidates
    
    # Run tracking
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_analysis_id = Column(String(100), ForeignKey('talent_analyses.analysis_id', ondelete='SET NULL'), nullable=True)
    run_count = Column(Integer, nullable=False, default=0)
    
    # Metadata
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships (optional, for eager loading)
    # blueprint = relationship("CareerBlueprint", foreign_keys=[blueprint_id])
    # company_dna = relationship("CompanyDNAProfile", foreign_keys=[company_dna_id])
    # ats_connection = relationship("ConnectorConfiguration", foreign_keys=[ats_connection_id])
    # last_analysis = relationship("TalentAnalysis", foreign_keys=[last_analysis_id])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "created_by_user_id": self.created_by_user_id,
            "name": self.name,
            "description": self.description,
            "blueprint_id": self.blueprint_id,
            "company_dna_id": self.company_dna_id,
            "ats_connection_id": self.ats_connection_id,
            "selected_job_id": self.selected_job_id,
            "job_description": self.job_description,
            "ideal_candidate_details": self.ideal_candidate_details,
            "department_ids": self.department_ids,
            "candidate_source_mode": self.candidate_source_mode,
            "uploaded_resume_files": self.uploaded_resume_files,
            "market_search_limit": self.market_search_limit,
            "max_candidate_fetch": self.max_candidate_fetch,
            "include_historical_candidates": self.include_historical_candidates,
            "historical_lookback_days": self.historical_lookback_days,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_analysis_id": self.last_analysis_id,
            "run_count": self.run_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self) -> str:
        return f"<AnalysisConfig(id={self.id}, name='{self.name}', customer_id='{self.customer_id}')>"

