"""
RAG Evaluation API Schemas

Pydantic models for RAG evaluation API requests and responses.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class EvalRunStatus(str, Enum):
    """Status of an evaluation run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvalVerdict(str, Enum):
    """Verdict for individual evaluation questions."""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


# ============= Request Schemas =============

class DifficultyCountsRequest(BaseModel):
    """Difficulty-based sampling configuration."""
    easy: Optional[int] = Field(None, ge=0, description="Number of easy questions")
    medium: Optional[int] = Field(None, ge=0, description="Number of medium questions")
    hard: Optional[int] = Field(None, ge=0, description="Number of hard questions")


class StartEvalRunRequest(BaseModel):
    """Request to start a new evaluation run."""
    domain: str = Field(default="fasb", description="Domain to evaluate (fasb, insurance)")
    sample_size: Optional[int] = Field(
        None, 
        ge=1, 
        le=500,
        description="Number of questions to evaluate (random sampling)"
    )
    difficulty_counts: Optional[DifficultyCountsRequest] = Field(
        None,
        description="Stratified sampling by difficulty"
    )
    seed: int = Field(default=42, ge=0, description="Random seed for reproducibility")
    concurrency: int = Field(default=3, ge=1, le=10, description="Parallel evaluation workers")
    validate_citations: bool = Field(
        default=False,
        description="Enable citation page validation (slower, requires PDF files)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "domain": "fasb",
                "difficulty_counts": {"easy": 5, "medium": 5, "hard": 5},
                "seed": 42,
                "concurrency": 3,
                "validate_citations": False
            }
        }


class CancelEvalRunRequest(BaseModel):
    """Request to cancel a running evaluation."""
    reason: Optional[str] = Field(None, description="Reason for cancellation")


# ============= Response Schemas =============

class EvalMetrics(BaseModel):
    """Aggregate evaluation metrics."""
    total_questions: int
    pass_count: int
    fail_count: int
    error_count: int
    pass_rate: float
    
    # RAGAS metrics
    factual_correctness_mean: Optional[float] = None
    faithfulness_mean: Optional[float] = None
    context_precision_mean: Optional[float] = None
    context_recall_mean: Optional[float] = None
    citation_compliance_mean: Optional[float] = None
    citation_page_accuracy_mean: Optional[float] = None


class EvalRunSummary(BaseModel):
    """Summary of an evaluation run."""
    id: int
    run_id: str
    domain: str
    eval_type: Optional[str] = None
    status: EvalRunStatus
    sample_size: int
    difficulty_counts: Optional[Dict[str, int]] = None
    
    # Eval source tracking (for reproducibility)
    eval_source: Optional[str] = None  # "eval_set" or "random_sampling"
    eval_set_id: Optional[int] = None
    eval_set_name: Optional[str] = None
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Metrics
    metrics: Optional[EvalMetrics] = None
    metrics_by_difficulty: Optional[Dict[str, Dict[str, Optional[float]]]] = None
    
    # Model configuration
    chat_model: Optional[str] = None
    embed_model: Optional[str] = None
    judge_model: Optional[str] = None
    prompt_template_snapshot: Optional[Dict[str, Any]] = None
    
    created_at: datetime
    
    class Config:
        from_attributes = True


class EvalResultItem(BaseModel):
    """Individual evaluation result."""
    id: int
    eval_id: str
    question_index: int
    question: str
    expected_answer: str
    difficulty: Optional[str] = None
    
    model_response: Optional[str] = None
    verdict: Optional[EvalVerdict] = None
    verdict_reason: Optional[str] = None
    
    citations: Optional[List[str]] = None
    citation_compliance: Optional[int] = None
    citation_page_validations: Optional[List[Dict[str, Any]]] = None
    citation_page_score: Optional[float] = None
    contexts_count: Optional[int] = None
    
    # RAGAS metrics
    factual_correctness: Optional[float] = None
    faithfulness: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    
    processing_time_ms: Optional[int] = None
    
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EvalRunResponse(BaseModel):
    """Full evaluation run response with results."""
    summary: EvalRunSummary
    results: Optional[List[EvalResultItem]] = None
    
    # Pagination for results
    total_results: int = 0
    page: int = 1
    page_size: int = 50


class StartEvalRunResponse(BaseModel):
    """Response when starting an evaluation run."""
    run_id: str
    status: EvalRunStatus
    message: str
    sse_url: str = Field(..., description="URL to stream evaluation progress via SSE")


class EvalRunListResponse(BaseModel):
    """List of evaluation runs."""
    runs: List[EvalRunSummary]
    total: int
    page: int
    page_size: int


class EvalTelemetryEvent(BaseModel):
    """Telemetry event for SSE streaming."""
    event_type: str
    stage_name: Optional[str] = None
    message: Optional[str] = None
    progress_percentage: Optional[float] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime


# ============= Question Analysis =============

class QuestionWithReference(BaseModel):
    """Evaluation question with reference answer (for preview)."""
    eval_id: str
    question: str
    reference_answer: str
    difficulty: str
    gold_chunk_ids: Optional[List[str]] = None


class QuestionsPreviewResponse(BaseModel):
    """Preview of evaluation questions."""
    total_available: int
    by_difficulty: Dict[str, int]
    sample_questions: List[QuestionWithReference]


# ============= Failure Analysis =============

class FailureAnalysis(BaseModel):
    """Analysis of a failed evaluation."""
    eval_id: str
    question: str
    expected_answer: str
    model_response: str
    verdict_reason: str
    
    # Metrics that contributed to failure
    factual_correctness: Optional[float] = None
    faithfulness: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    


class FailureAnalysisResponse(BaseModel):
    """Response with failure analysis."""
    run_id: str
    total_failures: int
    failures: List[FailureAnalysis]
    
    # Common failure patterns
    common_issues: Optional[List[str]] = None


# ============= Citation Validation (On-Demand) =============

class CitationValidationRequest(BaseModel):
    """Request to validate a single citation."""
    question_id: Optional[str] = Field(None, description="Question/message ID for on-demand validation")
    citation_index: Optional[int] = Field(None, ge=1, description="1-based citation index from Sources")
    citation: Optional[str] = Field(None, description="Raw citation string (fallback mode)")
    chunk_text: Optional[str] = Field(None, description="Chunk text to validate against (fallback mode)")
    question: Optional[str] = Field(None, description="Question text (fallback mode)")
    answer: Optional[str] = Field(None, description="Answer text (fallback mode)")


class CitationValidationResult(BaseModel):
    """Citation validation result."""
    citation: str
    doc_id: Optional[str] = None
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None
    verdict: str
    score: Optional[float] = None
    method: str
    evidence: Optional[str] = None
    reason: Optional[str] = None


class CitationValidationResponse(BaseModel):
    """Response for citation validation."""
    result: CitationValidationResult


# ============= Eval Set Schemas =============

class EvalSetType(str, Enum):
    """Type of evaluation set."""
    STATIC = "static"
    UPLOADED = "uploaded"


class EvalSetCategory(str, Enum):
    """Category/focus area of the eval set."""
    GENERAL = "general"
    RETRIEVAL = "retrieval"
    SYNTHESIS = "synthesis"
    GROUNDING = "grounding"
    MULTI_HOP = "multi_hop"
    EDGE_CASES = "edge_cases"
    REGRESSION = "regression"
    CUSTOM = "custom"


class EvalSource(str, Enum):
    """Source of evaluation questions for a run."""
    RANDOM_SAMPLING = "random_sampling"
    EVAL_SET = "eval_set"


class EvalSetSummary(BaseModel):
    """Summary of an eval set."""
    id: int
    customer_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    domain: str
    set_type: EvalSetType
    category: EvalSetCategory
    example_count: int
    difficulty_distribution: Optional[Dict[str, int]] = None
    tags: Optional[List[str]] = None
    is_built_in: bool
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EvalSetDetail(EvalSetSummary):
    """Full eval set with questions (for preview)."""
    questions: Optional[List[Dict[str, Any]]] = None


class EvalSetListResponse(BaseModel):
    """List of eval sets."""
    eval_sets: List[EvalSetSummary]
    total: int


class CreateEvalSetRequest(BaseModel):
    """Request to create an eval set from JSONL content."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    domain: str = Field(default="fasb", max_length=50)
    category: EvalSetCategory = Field(default=EvalSetCategory.GENERAL)
    tags: Optional[List[str]] = Field(None, max_length=20)
    # Note: questions are uploaded as file, not in request body


class UpdateEvalSetRequest(BaseModel):
    """Request to update an eval set metadata."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[EvalSetCategory] = None
    tags: Optional[List[str]] = Field(None, max_length=20)


class EvalSetQuestionsResponse(BaseModel):
    """Questions from an eval set with pagination."""
    eval_set_id: int
    name: str
    questions: List[Dict[str, Any]]
    total: int
    offset: int
    limit: int


# ============= Updated Start Eval Request with Eval Source =============

class StartEvalRunRequestV2(BaseModel):
    """
    Request to start a new evaluation run (v2 with eval source support).
    
    Either use an eval_set_id OR random sampling (sample_size/difficulty_counts).
    """
    domain: str = Field(default="fasb", description="Domain to evaluate (fasb, insurance)")
    
    # Eval source choice
    eval_source: EvalSource = Field(
        default=EvalSource.RANDOM_SAMPLING,
        description="Source of questions: eval_set or random_sampling"
    )
    eval_set_id: Optional[int] = Field(
        None,
        description="ID of eval set to use (required if eval_source=eval_set)"
    )
    
    # Random sampling options (used if eval_source=random_sampling)
    sample_size: Optional[int] = Field(
        None, 
        ge=1, 
        le=500,
        description="Number of questions to evaluate (random sampling)"
    )
    difficulty_counts: Optional[DifficultyCountsRequest] = Field(
        None,
        description="Stratified sampling by difficulty"
    )
    seed: int = Field(default=42, ge=0, description="Random seed for reproducibility")
    
    # Common options
    concurrency: int = Field(default=3, ge=1, le=10, description="Parallel evaluation workers")
    validate_citations: bool = Field(
        default=False,
        description="Enable citation page validation (slower, requires PDF files)"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "domain": "fasb",
                    "eval_source": "eval_set",
                    "eval_set_id": 1,
                    "concurrency": 3,
                },
                {
                    "domain": "fasb",
                    "eval_source": "random_sampling",
                    "difficulty_counts": {"easy": 5, "medium": 5, "hard": 5},
                    "seed": 42,
                    "concurrency": 3,
                }
            ]
        }
