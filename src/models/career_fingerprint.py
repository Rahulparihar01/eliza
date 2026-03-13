"""
Career Trajectory Fingerprint Models

Stores career trajectory patterns extracted from LinkedIn profiles.
Used to build "fingerprints" that can guide PDL searches and candidate scoring.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from src.models.database import BaseModel as DBBaseModel


class CareerFingerprint(DBBaseModel):
    """
    A career trajectory fingerprint built from 1+ LinkedIn profiles.
    
    Fingerprints capture patterns like:
    - Company progression (startup → big tech → startup)
    - Role progression (IC → lead → manager)
    - Industry transitions
    - Skill acquisition velocity
    - Education patterns
    """
    __tablename__ = 'career_fingerprints'
    __table_args__ = (
        Index('idx_career_fingerprint_customer', 'customer_id'),
        Index('idx_career_fingerprint_active', 'is_active'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(255), nullable=False, index=True)
    
    # Fingerprint metadata
    name = Column(String(255), nullable=False)  # e.g., "Senior ML Engineer Path"
    description = Column(Text, nullable=True)  # User description of this fingerprint
    
    # Source profiles (LinkedIn URLs or PDL person IDs)
    source_profiles = Column(JSON, nullable=False, default=list)
    """
    [
        {
            "linkedin_url": "https://linkedin.com/in/example",
            "pdl_person_id": "abc123",
            "full_name": "John Doe",
            "added_at": "2024-01-15T10:00:00Z"
        }
    ]
    """
    
    # Extracted patterns
    company_progression = Column(JSON, nullable=True)
    """
    {
        "pattern": ["startup", "faang", "startup"],
        "company_sizes": ["1-50", "10000+", "51-200"],
        "company_types": ["private", "public", "private"],
        "avg_tenure_months": 24,
        "industries": ["technology", "software", "ai"]
    }
    """
    
    role_progression = Column(JSON, nullable=True)
    """
    {
        "pattern": ["engineer", "senior_engineer", "staff_engineer"],
        "avg_promotion_months": 18,
        "management_track": false,
        "technical_depth": 0.8
    }
    """
    
    skill_velocity = Column(JSON, nullable=True)
    """
    {
        "skills_per_year": 3.5,
        "core_skills": ["python", "tensorflow", "kubernetes"],
        "recent_skills": ["llms", "langchain"],
        "skill_categories": {
            "ml_frameworks": 0.9,
            "cloud": 0.7,
            "mlops": 0.6
        }
    }
    """
    
    education_patterns = Column(JSON, nullable=True)
    """
    {
        "degree_levels": ["bachelors", "masters"],
        "fields": ["computer science", "machine learning"],
        "top_schools": true,
        "phd_rate": 0.3
    }
    """
    
    # Aggregated characteristics
    avg_years_experience = Column(Float, nullable=True)
    common_skills = Column(JSON, nullable=True)  # List of most common skills
    common_companies = Column(JSON, nullable=True)  # List of common companies
    common_titles = Column(JSON, nullable=True)  # List of common job titles
    
    # PDL query hints (pre-computed for faster searches)
    pdl_query_hints = Column(JSON, nullable=True)
    """
    {
        "suggested_job_titles": ["machine learning engineer", "ml engineer"],
        "suggested_skills": ["python", "tensorflow"],
        "suggested_companies": ["google", "meta", "openai"],
        "experience_range": {"min": 5, "max": 10}
    }
    """
    
    # Scoring weights (how to weight dimensions when scoring against this fingerprint)
    scoring_weights = Column(JSON, nullable=True)
    """
    {
        "technical_skills": 0.35,
        "experience_level": 0.25,
        "company_background": 0.20,
        "career_trajectory": 0.15,
        "education": 0.05
    }
    """
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    profile_count = Column(Integer, default=0, nullable=False)
    
    # Audit
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CompanyDNAProfile(DBBaseModel):
    """
    Company DNA Profile - captures the characteristics of a company's workforce.
    
    Built from analyzing current employees to understand:
    - What backgrounds succeed at this company
    - Company culture indicators
    - Hiring patterns
    """
    __tablename__ = 'company_dna_profiles'
    __table_args__ = (
        Index('idx_company_dna_customer', 'customer_id'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(255), nullable=False, index=True)
    
    # Company info
    company_name = Column(String(255), nullable=False)
    company_website = Column(String(500), nullable=True)
    company_description = Column(Text, nullable=True)
    
    # Company characteristics
    company_stage = Column(String(50), nullable=True)  # startup, growth, enterprise
    company_size = Column(String(50), nullable=True)  # 1-50, 51-200, etc.
    industry = Column(String(255), nullable=True)
    
    # DNA Profile (extracted from employees)
    workforce_dna = Column(JSON, nullable=True)
    """
    {
        "avg_tenure_months": 24,
        "avg_experience_years": 7,
        "common_backgrounds": {
            "faang_alumni": 0.35,
            "startup_experience": 0.60,
            "consulting_background": 0.15
        },
        "education_profile": {
            "phd_rate": 0.20,
            "top_school_rate": 0.45,
            "common_degrees": ["computer science", "data science"]
        },
        "skill_profile": {
            "core_skills": ["python", "aws", "kubernetes"],
            "emerging_skills": ["llms", "langchain"],
            "skill_diversity": 0.7
        }
    }
    """
    
    # Culture indicators (inferred from workforce patterns)
    culture_indicators = Column(JSON, nullable=True)
    """
    {
        "pace": "fast",  # fast, moderate, steady
        "autonomy_level": "high",  # high, medium, low
        "remote_friendly": true,
        "career_growth": "rapid",  # rapid, steady, limited
        "technical_depth": 0.8,  # 0-1 scale
        "collaboration_style": "cross_functional"
    }
    """
    
    # Success patterns (what makes employees successful here)
    success_patterns = Column(JSON, nullable=True)
    """
    {
        "high_performers": {
            "common_traits": ["startup_experience", "self_starter"],
            "common_backgrounds": ["consulting", "faang"],
            "avg_ramp_time_months": 3
        },
        "retention_factors": {
            "growth_opportunity": 0.9,
            "technical_challenge": 0.8,
            "compensation": 0.7
        }
    }
    """
    
    # Hiring preferences (what to look for)
    hiring_preferences = Column(JSON, nullable=True)
    """
    {
        "preferred_companies": ["google", "meta", "stripe"],
        "preferred_backgrounds": ["startup_to_scale"],
        "red_flags": ["job_hopping", "only_big_company"],
        "must_haves": ["production_experience", "ownership_mentality"]
    }
    """
    
    # PDL query modifiers (how to adjust searches for this company)
    pdl_query_modifiers = Column(JSON, nullable=True)
    """
    {
        "boost_companies": ["stripe", "plaid", "databricks"],
        "boost_skills": ["kubernetes", "terraform"],
        "company_size_preference": ["51-200", "201-500"],
        "industry_preference": ["technology", "fintech"]
    }
    """
    
    # Source data
    employee_count_analyzed = Column(Integer, default=0, nullable=False)
    employee_ids_analyzed = Column(JSON, nullable=True)  # List of employee IDs used
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_analyzed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Audit
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ============================================================================
# PYDANTIC MODELS FOR API
# ============================================================================

class CareerFingerprintCreate(BaseModel):
    """Request model for creating a career fingerprint"""
    name: str = Field(..., description="Name for this fingerprint")
    description: Optional[str] = Field(None, description="Description of this fingerprint")
    linkedin_urls: List[str] = Field(..., description="LinkedIn profile URLs to analyze")


class CareerFingerprintResponse(BaseModel):
    """Response model for career fingerprint"""
    id: int
    name: str
    description: Optional[str]
    profile_count: int
    source_profiles: List[Dict[str, Any]]
    company_progression: Optional[Dict[str, Any]]
    role_progression: Optional[Dict[str, Any]]
    skill_velocity: Optional[Dict[str, Any]]
    common_skills: Optional[List[str]]
    common_companies: Optional[List[str]]
    avg_years_experience: Optional[float]
    pdl_query_hints: Optional[Dict[str, Any]]
    scoring_weights: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class CompanyDNACreate(BaseModel):
    """Request model for creating/updating company DNA"""
    company_name: str
    company_website: Optional[str] = None
    company_description: Optional[str] = None
    analyze_employees: bool = Field(True, description="Whether to analyze existing employees")


class CompanyDNAResponse(BaseModel):
    """Response model for company DNA profile"""
    id: int
    company_name: str
    company_website: Optional[str]
    company_stage: Optional[str]
    company_size: Optional[str]
    industry: Optional[str]
    workforce_dna: Optional[Dict[str, Any]]
    culture_indicators: Optional[Dict[str, Any]]
    success_patterns: Optional[Dict[str, Any]]
    hiring_preferences: Optional[Dict[str, Any]]
    pdl_query_modifiers: Optional[Dict[str, Any]]
    employee_count_analyzed: int
    is_active: bool
    last_analyzed_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


