"""
Pydantic models for Talent Intelligence System.

These models define structured outputs for all services and agents,
ensuring type safety and validation throughout the pipeline.
Role-agnostic: supports any role type, not just ML Engineers.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class AnalysisStatus(str, Enum):
    """Status of talent analysis"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CandidateSource(str, Enum):
    """Source of candidate"""
    APPLICANT = "applicant"
    MARKET = "market"
    PREVIOUS_CANDIDATE = "previous_candidate"  # Candidates from closed/historical job listings


class FeedbackType(str, Enum):
    """Type of feedback"""
    CANDIDATE_RATING = "candidate_rating"
    ATTRIBUTE_WEIGHT = "attribute_weight"
    PATTERN_VALIDATION = "pattern_validation"
    OVERALL_COMMENT = "overall_comment"


class PatternType(str, Enum):
    """Type of pattern"""
    CAREER_PATH = "career_path"
    SKILL_COMBO = "skill_combo"
    COMPANY_CLUSTER = "company_cluster"
    EXPERIENCE_LEVEL = "experience_level"


# ============================================================================
# DIAGNOSTIC MODELS
# ============================================================================

class AttributePriority(BaseModel):
    """Single attribute weight from diagnostic analysis"""
    attribute: str
    weight: float = Field(ge=0.0, le=1.0, description="Weight from 0.0 to 1.0")
    reason: str = Field(description="Why this weight was chosen")


class CompetencyPriority(BaseModel):
    """Role-specific competency priorities (applicable to any role type)"""
    research_focus: float = Field(ge=0.0, le=1.0, description="Research/innovation focus")
    production_focus: float = Field(ge=0.0, le=1.0, description="Production/delivery focus")
    mlops_focus: float = Field(ge=0.0, le=1.0, description="Operations/infrastructure focus")
    leadership_potential: float = Field(ge=0.0, le=1.0, description="Leadership/management potential")


# Backward compatibility alias
MLCompetencyPriority = CompetencyPriority


class DiagnosticReport(BaseModel):
    """
    Output from Diagnostic Intent Analyzer Agent.
    Structured analysis of hiring manager's requirements.
    """
    role_type: str = Field(description="Role being hired for (e.g., 'Software Engineer', 'Data Scientist', 'Product Manager')")
    seniority_level: str = Field(description="Mid, Senior, Staff, Principal, etc.")
    
    # Role-specific priorities
    ml_competencies: CompetencyPriority
    
    # Required and preferred skills
    required_skills: List[str] = Field(description="Must-have technical skills")
    preferred_skills: List[str] = Field(description="Nice-to-have skills")
    
    # Attribute weights for scoring
    attribute_weights: List[AttributePriority] = Field(
        description="Adjusted weights for each scoring dimension"
    )
    
    # Key hypotheses about ideal candidate
    key_hypotheses: List[str] = Field(
        description="Hypotheses about what makes great candidate"
    )
    
    # Baseline query parameters for Neo4j
    baseline_query_params: Dict[str, Any] = Field(
        description="Parameters to query for baseline employees"
    )
    
    # Confidence in understanding the role
    confidence: float = Field(
        ge=0.0, le=1.0, 
        description="Confidence in diagnostic analysis"
    )


# ============================================================================
# BASELINE MODELS
# ============================================================================

class CareerPathPattern(BaseModel):
    """A career progression pattern"""
    path_description: str
    frequency: int
    example_employees: List[int]


class BaselineProfile(BaseModel):
    """
    Output from Baseline Builder.
    Aggregated from Career Blueprint patterns (enriched LinkedIn profiles)
    and the user's ideal candidate preferences (must-haves, nice-to-haves,
    dealbreakers, personality traits, hiring manager notes).
    """
    role_type: str = Field(description="Target role type for this baseline")
    
    # Prototype employees
    prototype_employee_ids: List[int] = Field(
        description="IDs of employees used as baseline"
    )
    
    # Attribute weights (can be adjusted by diagnostic)
    attribute_weights: Dict[str, float] = Field(
        description="Final weights for scoring dimensions"
    )
    
    # Career path patterns
    common_career_paths: List[CareerPathPattern] = Field(
        description="Common career progressions"
    )
    
    # Skill distributions
    skill_distributions: Dict[str, float] = Field(
        description="Frequency of skills in baseline group"
    )
    
    # Company clusters
    company_clusters: List[str] = Field(
        description="Common companies in career paths"
    )
    
    # Average metrics
    average_years_experience: float
    
    # Success patterns
    success_patterns: List[str] = Field(
        description="Patterns correlated with success"
    )
    
    # Data quality
    data_quality_score: float = Field(
        ge=0.0, le=1.0,
        description="Quality of baseline data"
    )


# ============================================================================
# RESUME PARSING MODELS
# ============================================================================

class ParsedExperience(BaseModel):
    """Single work experience entry"""
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_months: Optional[int] = None
    description: Optional[str] = None
    achievements: List[str] = Field(default_factory=list)


class ParsedEducation(BaseModel):
    """Single education entry"""
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    school: Optional[str] = None
    graduation_year: Optional[int] = None


class ParsedResume(BaseModel):
    """
    Structured resume data extracted from PDF/DOCX via text extraction + LLM.
    """
    # Contact info
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    
    # Source system metadata (e.g., from Greenhouse)
    greenhouse_id: Optional[int] = Field(
        default=None,
        description="Greenhouse candidate ID if sourced from Greenhouse"
    )
    current_title: Optional[str] = Field(
        default=None,
        description="Current job title"
    )
    current_company: Optional[str] = Field(
        default=None,
        description="Current company"
    )
    is_historical: bool = Field(
        default=False,
        description="True if candidate is from a closed/historical job listing"
    )
    source_job_id: Optional[int] = Field(
        default=None,
        description="Original job ID the candidate applied to (for historical candidates)"
    )
    
    # Skills
    skills: List[str] = Field(default_factory=list)
    
    # Experience
    experience: List[ParsedExperience] = Field(default_factory=list)
    
    # Education
    education: List[ParsedEducation] = Field(default_factory=list)
    
    # Summary/objective
    summary: Optional[str] = None
    
    # Certifications
    certifications: List[str] = Field(default_factory=list)
    
    # Quality metadata
    parse_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in parse quality"
    )
    quality_flags: List[str] = Field(
        default_factory=list,
        description="Warnings or issues in parsing"
    )
    
    # Raw outputs for debugging
    raw_text: Optional[str] = None
    docling_output: Optional[Dict[str, Any]] = None


# ============================================================================
# SCORING MODELS
# ============================================================================

class ScoreDimension(BaseModel):
    """Single scoring dimension breakdown"""
    dimension: str = Field(description="Dimension name (e.g., 'ml_skills')")
    score: float = Field(ge=0.0, le=100.0, description="Score out of 100")
    explanation: str = Field(description="Why this score was given")
    evidence: List[str] = Field(
        default_factory=list,
        description="Specific evidence supporting this score"
    )


class CandidateScore(BaseModel):
    """
    Output from Scoring Engine.
    Complete scoring breakdown for a candidate.
    """
    candidate_id: str
    source: CandidateSource
    
    # Overall score
    overall_score: float = Field(
        ge=0.0, le=100.0,
        description="Weighted overall score"
    )
    
    # Dimension breakdown
    dimensions: List[ScoreDimension] = Field(
        description="Score breakdown by dimension"
    )
    
    # Pattern matching
    patterns_matched: List[str] = Field(
        default_factory=list,
        description="Patterns this candidate matches"
    )
    
    # Baseline similarity
    baseline_similarity: float = Field(
        ge=0.0, le=1.0,
        description="Similarity to baseline employees"
    )
    
    # Confidence
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in this scoring"
    )
    
    # Profile data (for display in outreach)
    full_name: Optional[str] = Field(
        default=None,
        description="Candidate full name"
    )
    email: Optional[str] = Field(
        default=None,
        description="Candidate email address"
    )
    phone: Optional[str] = Field(
        default=None,
        description="Candidate phone number"
    )
    linkedin_url: Optional[str] = Field(
        default=None,
        description="LinkedIn profile URL"
    )
    location: Optional[str] = Field(
        default=None,
        description="Candidate location"
    )
    current_title: Optional[str] = Field(
        default=None,
        description="Current job title"
    )
    current_company: Optional[str] = Field(
        default=None,
        description="Current company"
    )
    greenhouse_id: Optional[int] = Field(
        default=None,
        description="Greenhouse candidate ID for applicants"
    )


# ============================================================================
# PATTERN MODELS
# ============================================================================

class PatternInsight(BaseModel):
    """Extracted pattern from top candidates"""
    pattern_type: PatternType
    description: str = Field(description="Human-readable pattern description")
    frequency: int = Field(description="How many top candidates have this")
    baseline_comparison: str = Field(
        description="How this compares to baseline employees"
    )
    examples: List[str] = Field(
        default_factory=list,
        description="Example candidate IDs showing this pattern"
    )


# ============================================================================
# SYNTHESIS MODELS
# ============================================================================

class SynthesisReport(BaseModel):
    """
    Output from Synthesis Agent.
    Human-readable insights and recommendations.
    """
    executive_summary: str = Field(
        description="2-3 paragraph summary for hiring manager"
    )
    
    key_insights: List[str] = Field(
        description="Top 5-7 key insights about candidate pool"
    )
    
    pattern_highlights: List[PatternInsight] = Field(
        description="Important patterns identified"
    )
    
    recommendations: List[str] = Field(
        description="Actionable recommendations for hiring process"
    )
    
    concerns: List[str] = Field(
        default_factory=list,
        description="Potential concerns or caveats"
    )
    
    confidence_assessment: str = Field(
        description="Overall confidence in analysis quality"
    )


# ============================================================================
# PROVENANCE MODELS
# ============================================================================

class ProvenanceStep(BaseModel):
    """Single step in provenance chain"""
    step: int
    action: str
    details: Dict[str, Any]


class WorkflowProvenanceStep(BaseModel):
    """Workflow-level provenance for each stage of the analysis"""
    step_name: str = Field(description="Name of the workflow step")
    step_description: str = Field(description="Human-readable description")
    inputs: Dict[str, Any] = Field(description="Inputs to this step")
    outputs: Dict[str, Any] = Field(description="Outputs from this step")
    service_used: str = Field(description="Service/component that performed the step")
    llm_provider: Optional[str] = Field(default=None, description="LLM provider if used")
    llm_model: Optional[str] = Field(default=None, description="LLM model if used")
    timestamp: datetime = Field(description="When this step started")
    duration_seconds: float = Field(description="How long the step took")


class ProvenanceChain(BaseModel):
    """Complete audit trail for a candidate"""
    candidate_id: str
    source_type: CandidateSource
    
    # Extraction details
    extraction_details: Dict[str, Any] = Field(
        description="How data was extracted (VLM parse, PDL fields)"
    )
    
    # Scoring breakdown
    scoring_breakdown: Dict[str, Any] = Field(
        description="Detailed scoring calculation"
    )
    
    # Boosts applied
    boosts_applied: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Metadata boosts or penalties"
    )
    
    # Comparison rationale
    comparison_rationale: str = Field(
        description="Why this candidate ranks where they do"
    )
    
    # Full chain
    provenance_steps: List[ProvenanceStep] = Field(
        description="Complete step-by-step provenance"
    )


# ============================================================================
# FEEDBACK MODELS
# ============================================================================

class CandidateFeedback(BaseModel):
    """Feedback on individual candidate"""
    candidate_id: str
    rating: Literal["great", "good", "meh", "bad"] = Field(
        description="Overall rating"
    )
    comment: Optional[str] = None


class AttributeFeedback(BaseModel):
    """Feedback on attribute importance"""
    attribute: str
    importance: float = Field(
        ge=0.0, le=1.0,
        description="Adjusted importance (from slider)"
    )
    comment: Optional[str] = None


class PatternFeedback(BaseModel):
    """Feedback on pattern validation"""
    pattern_id: str
    validated: bool = Field(
        description="Whether this pattern is correct"
    )
    comment: Optional[str] = None


class AnalysisFeedback(BaseModel):
    """Complete feedback from hiring manager"""
    analysis_id: str
    
    # Candidate-level feedback
    candidate_feedback: List[CandidateFeedback] = Field(default_factory=list)
    
    # Attribute-level feedback
    attribute_feedback: List[AttributeFeedback] = Field(default_factory=list)
    
    # Pattern-level feedback
    pattern_feedback: List[PatternFeedback] = Field(default_factory=list)
    
    # Overall comment
    overall_comment: Optional[str] = None


# ============================================================================
# PDL QUERY MODELS
# ============================================================================

class PDLQuery(BaseModel):
    """PDL query configuration"""
    base_query: str = Field(description="Base PDL query string")
    params: Dict[str, Any] = Field(description="Query parameters")
    version: int = Field(default=1, description="Query version (for refinement)")
    refinement_reason: Optional[str] = None


# ============================================================================
# API RESPONSE MODELS
# ============================================================================

class TalentAnalysisResponse(BaseModel):
    """Response for starting analysis"""
    analysis_id: str
    status: AnalysisStatus
    message: str


class TalentAnalysisResult(BaseModel):
    """Complete analysis result"""
    analysis_id: str
    status: AnalysisStatus
    
    # Inputs
    job_description: str
    ideal_candidate_description: str
    
    # Analysis outputs (may be None if analysis is still processing)
    diagnostic_report: Optional[DiagnosticReport] = None
    baseline_profile: Optional[BaselineProfile] = None
    synthesis: Optional[SynthesisReport] = None
    
    # Candidate results
    applicant_results: List[CandidateScore]
    previous_candidate_results: List[CandidateScore] = Field(default_factory=list, description="Candidates from closed/historical job listings")
    market_results: List[CandidateScore]
    top_overall: List[CandidateScore]
    
    # Patterns
    patterns: List[PatternInsight]
    
    # Provenance (workflow-level audit trail)
    provenance: List[WorkflowProvenanceStep]
    
    # Metadata
    overall_confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    # PDL query used
    pdl_query: Optional[PDLQuery] = None


class TalentAnalysisList(BaseModel):
    """List of analyses"""
    analyses: List[TalentAnalysisResult]
    total: int
    offset: int
    limit: int

