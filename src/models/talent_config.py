"""
Talent Configuration Models

SQLAlchemy models for Career Blueprints and Company DNA profiles.
These are persistent configurations used across talent analyses.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from src.models.database import Base


class CareerBlueprint(Base):
    """
    Career Blueprint - Reusable career pattern template.
    
    Created from look-alike LinkedIn profiles to define what an ideal
    candidate's career trajectory should look like.
    """
    __tablename__ = "career_blueprints"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    
    # Blueprint identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    role_category = Column(String(100), nullable=True)  # e.g., "engineering", "sales"
    
    # Source profiles
    source_linkedin_urls = Column(JSONB, nullable=False, server_default='[]')
    source_profile_count = Column(Integer, nullable=False, server_default='0')
    source_pdl_person_ids = Column(JSONB, nullable=True)  # References to pdl_persons.id for full profile data
    
    # Extracted patterns (JSONB for flexibility)
    company_progression = Column(JSONB, nullable=True)
    role_progression = Column(JSONB, nullable=True)
    skill_profile = Column(JSONB, nullable=True)
    experience_profile = Column(JSONB, nullable=True)
    education_profile = Column(JSONB, nullable=True)
    
    # Query and scoring configuration
    pdl_query_hints = Column(JSONB, nullable=True)
    scoring_weights = Column(JSONB, nullable=True)
    
    # Status and metadata
    is_active = Column(Boolean, nullable=False, server_default='true')
    usage_count = Column(Integer, nullable=False, server_default='0')
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_by_user_id = Column(Integer, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "name": self.name,
            "description": self.description,
            "role_category": self.role_category,
            "source_linkedin_urls": self.source_linkedin_urls or [],
            "source_profile_count": self.source_profile_count,
            "source_pdl_person_ids": self.source_pdl_person_ids or [],
            "company_progression": self.company_progression,
            "role_progression": self.role_progression,
            "skill_profile": self.skill_profile,
            "experience_profile": self.experience_profile,
            "education_profile": self.education_profile,
            "pdl_query_hints": self.pdl_query_hints,
            "scoring_weights": self.scoring_weights,
            "is_active": self.is_active,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CompanyDNAProfile(Base):
    """
    Company DNA Profile - Organizational hiring patterns.
    
    Scoped by company + role category, built from analyzing current employees.
    Used to find candidates who fit the organizational culture.
    """
    __tablename__ = "company_dna_profiles"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    
    # Company identification
    company_name = Column(String(255), nullable=False)
    company_website = Column(String(500), nullable=True)
    role_category = Column(String(100), nullable=False)  # e.g., "engineering", "sales", "all"
    
    # Analysis parameters
    time_window_months = Column(Integer, nullable=False, server_default='24')
    employee_count_analyzed = Column(Integer, nullable=False, server_default='0')
    
    # DNA data (JSONB for flexibility)
    workforce_dna = Column(JSONB, nullable=True)
    culture_indicators = Column(JSONB, nullable=True)
    success_patterns = Column(JSONB, nullable=True)
    hiring_preferences = Column(JSONB, nullable=True)
    pdl_query_modifiers = Column(JSONB, nullable=True)
    
    # Status and metadata
    is_active = Column(Boolean, nullable=False, server_default='true')
    is_default = Column(Boolean, nullable=False, server_default='false')
    last_analyzed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_by_user_id = Column(Integer, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('customer_id', 'company_name', 'role_category', name='uq_company_dna_company_role'),
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "company_name": self.company_name,
            "company_website": self.company_website,
            "role_category": self.role_category,
            "time_window_months": self.time_window_months,
            "employee_count_analyzed": self.employee_count_analyzed,
            "workforce_dna": self.workforce_dna,
            "culture_indicators": self.culture_indicators,
            "success_patterns": self.success_patterns,
            "hiring_preferences": self.hiring_preferences,
            "pdl_query_modifiers": self.pdl_query_modifiers,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "last_analyzed_at": self.last_analyzed_at.isoformat() if self.last_analyzed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

