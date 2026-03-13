"""
Talent Matching Data Models

Enhanced models for ML Engineer candidate matching system.
Stores detailed analysis, scoring, and pattern matching results.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from src.models.database import BaseModel as DBBaseModel


class CandidateAnalysis(DBBaseModel):
    """
    Detailed analysis of candidate against ideal profile.
    
    Stores scoring breakdown, pattern matches, and agent reasoning.
    Used for both internal applicants and external PDL candidates.
    """
    __tablename__ = 'candidate_analyses'
    __table_args__ = (
        Index('idx_candidate_analysis_job', 'job_posting_id'),
        Index('idx_candidate_analysis_score', 'total_score'),
        Index('idx_candidate_analysis_customer', 'customer_id'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(255), nullable=False, index=True)
    
    # Analysis metadata
    analysis_session_id = Column(String(100), nullable=False, index=True)  # Groups analyses from same search
    job_posting_id = Column(Integer, ForeignKey('job_postings.id'), nullable=True)
    
    # Candidate identification (one of these will be set)
    applicant_id = Column(Integer, ForeignKey('applicants.id'), nullable=True)  # Internal applicant
    pdl_person_id = Column(Integer, ForeignKey('pdl_persons.id'), nullable=True)  # External PDL candidate
    
    # Candidate source
    candidate_source = Column(String(50), nullable=False)  # 'internal_applicant' or 'external_pdl'
    
    # Ideal profile (what we're matching against)
    ideal_profile = Column(JSON, nullable=False)  # Synthesized from JD + hiring manager + patterns
    
    # Overall scoring
    total_score = Column(Float, nullable=False, index=True)  # 0-100
    confidence = Column(Float, nullable=True)  # Agent's confidence in the score
    
    # Detailed score breakdown (aligned with our discussion)
    score_skills_match = Column(Float, nullable=True)  # 0-100
    score_experience_fit = Column(Float, nullable=True)  # 0-100
    score_career_trajectory = Column(Float, nullable=True)  # 0-100
    score_company_background = Column(Float, nullable=True)  # 0-100
    score_cultural_fit = Column(Float, nullable=True)  # 0-100
    score_production_ml = Column(Float, nullable=True)  # 0-100 (ML-specific)
    score_independence = Column(Float, nullable=True)  # 0-100 (startup readiness)
    
    # Pattern matching (novel concept from our discussion)
    pattern_matches = Column(JSON, nullable=True)  # Which success patterns this candidate matches
    """
    Example:
    {
        "consulting_to_tech_transition": true,
        "databricks_alumni": false,
        "series_b_startup_experience": true,
        "similar_career_path_to_top_performers": 0.87
    }
    """
    
    # Agent reasoning and explanations
    why_great_fit = Column(Text, nullable=True)  # 2-3 sentence explanation
    potential_concerns = Column(Text, nullable=True)  # Gaps or red flags
    evidence = Column(JSON, nullable=True)  # Supporting evidence with citations
    """
    Example:
    [
        {
            "claim": "5 years PyTorch experience",
            "evidence": "Built recommendation engine at Spotify",
            "source": "resume_page_1_experience",
            "confidence": 0.95
        }
    ]
    """
    
    # Metadata boosting applied (from our discussion)
    metadata_boosts_applied = Column(JSON, nullable=True)
    """
    {
        "company_tier_boost": 1.3,  # Databricks alumni
        "recency_boost": 1.1,
        "department_match_boost": 1.0
    }
    """
    
    # Ranking metadata
    ranking_method = Column(String(50), nullable=True)  # 'fast_deterministic' or 'two_stage_llm'
    ranking_stage = Column(String(50), nullable=True)  # 'stage_1_fast' or 'stage_2_deep'
    
    # Timing
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    analysis_duration_ms = Column(Integer, nullable=True)  # How long analysis took
    
    # Relationships
    applicant = relationship("Applicant", foreign_keys=[applicant_id])
    pdl_person = relationship("PDLPerson", foreign_keys=[pdl_person_id])


class MatchingSession(DBBaseModel):
    """
    A single talent matching session (one JD analysis).
    
    Groups all analyses, tracks agent decisions, stores insights.
    """
    __tablename__ = 'matching_sessions'
    __table_args__ = (
        Index('idx_matching_session_customer', 'customer_id'),
        Index('idx_matching_session_created', 'created_at'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(255), nullable=False, index=True)
    
    # Input data
    job_description = Column(Text, nullable=False)
    hiring_manager_notes = Column(Text, nullable=True)  # Natural language ideal candidate description
    reference_employee_ids = Column(JSON, nullable=True)  # IDs of employees to analyze for patterns
    
    # Synthesized ideal profile (output of Profile Synthesizer Agent)
    ideal_candidate_profile = Column(JSON, nullable=False)
    profile_synthesis_reasoning = Column(Text, nullable=True)  # How profile was created
    
    # Employee pattern analysis (from Neo4j)
    success_patterns_found = Column(JSON, nullable=True)
    """
    Example:
    {
        "consulting_to_tech_transitions": {
            "frequency": 0.60,
            "examples": ["emp_123", "emp_456"],
            "success_rate": 0.85
        },
        "databricks_alumni": {
            "frequency": 0.30,
            "all_top_performers": true
        }
    }
    """
    
    # Search execution
    internal_candidates_analyzed = Column(Integer, nullable=True)  # Count of applicants
    external_candidates_found = Column(Integer, nullable=True)  # Count from PDL
    
    # PDL query used (for external search)
    pdl_query_generated = Column(JSON, nullable=True)
    pdl_query_reasoning = Column(Text, nullable=True)
    pdl_query_cost_usd = Column(Float, nullable=True)
    
    # Results
    top_internal_candidate_id = Column(Integer, ForeignKey('candidate_analyses.id'), nullable=True)
    top_external_candidate_id = Column(Integer, ForeignKey('candidate_analyses.id'), nullable=True)
    
    # Performance metrics
    total_duration_seconds = Column(Float, nullable=True)
    total_cost_usd = Column(Float, nullable=True)
    
    # Agent execution trace (for debugging and learning)
    agent_trace = Column(JSON, nullable=True)
    """
    {
        "profile_synthesis_agent": {"duration_ms": 8500, "llm_calls": 2, "cost": 0.15},
        "pattern_analyzer_agent": {"duration_ms": 2100, "neo4j_queries": 5},
        "ranking_agent": {"duration_ms": 12000, "candidates_scored": 50, "cost": 0.25}
    }
    """
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(50), nullable=False, default='pending')  # pending, running, completed, failed


# Pydantic models for API requests/responses

class IdealCandidateProfileSchema(BaseModel):
    """Synthesized ideal candidate profile"""
    must_have_skills: List[Dict[str, Any]] = Field(default_factory=list)
    """
    [
        {"skill": "PyTorch", "weight": 1.0, "aliases": ["Torch"]},
        {"skill": "Production ML", "weight": 1.0, "signals": ["deployed", "at scale"]}
    ]
    """
    
    strong_preferences: List[Dict[str, Any]] = Field(default_factory=list)
    """
    [
        {"attribute": "consulting_to_tech_transition", "pattern_backed": true, "weight": 0.8},
        {"attribute": "series_b_startup_experience", "weight": 0.7}
    ]
    """
    
    nice_to_have: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    
    seniority_level: str  # "mid", "senior", "staff", "principal"
    experience_years_min: int
    experience_years_ideal: int
    
    target_companies: List[str] = Field(default_factory=list)
    target_company_types: List[str] = Field(default_factory=list)  # "series_b", "faang", etc.


class CandidateScoreBreakdown(BaseModel):
    """Detailed scoring breakdown"""
    total_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    
    skills_match: float = Field(ge=0, le=100)
    experience_fit: float = Field(ge=0, le=100)
    career_trajectory: float = Field(ge=0, le=100)
    company_background: float = Field(ge=0, le=100)
    cultural_fit: float = Field(ge=0, le=100)
    
    # ML-specific scores
    production_ml_evidence: Optional[float] = Field(default=None, ge=0, le=100)
    independence_signals: Optional[float] = Field(default=None, ge=0, le=100)


class MatchedCandidateResult(BaseModel):
    """Single matched candidate result"""
    candidate_id: int
    source: str  # "internal_applicant" or "external_pdl"
    
    # Basic info
    name: str
    current_title: Optional[str]
    current_company: Optional[str]
    email: Optional[str]
    linkedin_url: Optional[str]
    
    # Scoring
    score_breakdown: CandidateScoreBreakdown
    pattern_matches: Dict[str, Any]
    
    # Explanations
    why_great_fit: str
    potential_concerns: Optional[str]
    evidence: List[Dict[str, Any]]
    
    # Metadata
    analyzed_at: datetime
    ranking_method: str


class TalentMatchingRequest(BaseModel):
    """Request to start talent matching"""
    job_description: str = Field(..., description="Full job description text")
    hiring_manager_notes: Optional[str] = Field(
        default=None,
        description="Natural language description of ideal candidate from hiring manager"
    )
    reference_employee_ids: Optional[List[int]] = Field(
        default=None,
        description="IDs of current employees to analyze for success patterns"
    )
    
    # Search configuration
    analyze_internal_applicants: bool = Field(default=True, description="Search internal applicants")
    search_external_pdl: bool = Field(default=True, description="Search PDL for external candidates")
    max_results: int = Field(default=20, description="Max results to return")
    
    # Performance tuning
    use_fast_ranking: bool = Field(default=False, description="Use fast deterministic ranking only (no deep LLM)")
    budget_usd: Optional[float] = Field(default=None, description="Optional budget cap for search")


class TalentMatchingResponse(BaseModel):
    """Response from talent matching"""
    session_id: str
    status: str  # "running", "completed", "failed"
    
    # Profile synthesis
    ideal_profile: IdealCandidateProfileSchema
    success_patterns_found: Dict[str, Any]
    
    # Results
    internal_matches: List[MatchedCandidateResult]
    external_matches: List[MatchedCandidateResult]
    
    # Insights
    market_insights: Dict[str, Any]
    sourcing_recommendations: List[str]
    
    # Performance
    total_duration_seconds: float
    total_cost_usd: float
    candidates_analyzed: int


class PatternAnalysisResult(BaseModel):
    """Results from employee pattern analysis"""
    patterns_found: Dict[str, Any]
    top_performer_analysis: Dict[str, Any]
    recommended_focus_areas: List[str]
    company_sources: List[Dict[str, Any]]  # Best companies to source from

