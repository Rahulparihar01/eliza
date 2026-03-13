"""
GEPA Optimizer API Schemas

Pydantic models for GEPA optimization API requests and responses.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class OptimizerJobStatus(str, Enum):
    """Status of a GEPA optimizer job."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VariantStatus(str, Enum):
    """Status of a candidate variant."""
    PENDING = "pending"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"
    FAILED = "failed"
    PROMOTED = "promoted"


class ComponentType(str, Enum):
    """Types of mutable text components."""
    QUERY_REWRITE_PROMPT = "query_rewrite_prompt"
    RETRIEVAL_INSTRUCTIONS = "retrieval_instructions"
    TOOL_INSTRUCTIONS = "tool_instructions"
    ANSWER_SYNTHESIS_PROMPT = "answer_synthesis_prompt"
    SYSTEM_PROMPT = "system_prompt"
    FEW_SHOT_EXAMPLES = "few_shot_examples"
    TEXTUAL_SPEC = "textual_spec"
    CUSTOM = "custom"


class MutationType(str, Enum):
    """Types of mutations applied to components."""
    REPHRASE = "rephrase"
    EXPAND = "expand"
    COMPRESS = "compress"
    RESTRUCTURE = "restructure"
    ADD_CONSTRAINT = "add_constraint"
    REMOVE_CONSTRAINT = "remove_constraint"
    CROSSOVER = "crossover"
    REFLECTION_GUIDED = "reflection_guided"
    ERROR_TARGETED = "error_targeted"


class OptimizationObjective(str, Enum):
    """Available optimization objectives."""
    QUALITY = "quality"
    GROUNDEDNESS = "groundedness"
    CITATION_ACCURACY = "citation_accuracy"
    LATENCY = "latency"
    COST = "cost"
    FACTUAL_CORRECTNESS = "factual_correctness"
    FAITHFULNESS = "faithfulness"


class OptimizationStrategy(str, Enum):
    """Optimization backend strategy."""
    GENETIC = "genetic"
    DSPY_BOOTSTRAP = "dspy_bootstrap"
    DSPY_MIPRO = "dspy_mipro"


# ============= Request Schemas =============

class ComponentConfig(BaseModel):
    """Configuration for a single component to optimize."""
    component_type: ComponentType
    # Optional because we can prefill from Prompt Management when domain is provided.
    initial_value: Optional[str] = Field(
        None,
        description="Initial/baseline value for this component. If omitted and domain+use_prompt_management are set, it will be loaded automatically.",
    )
    custom_name: Optional[str] = Field(None, description="Custom name for CUSTOM component type")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Constraints for mutations")


class ObjectiveConfig(BaseModel):
    """Configuration for an optimization objective."""
    name: OptimizationObjective
    weight: float = Field(1.0, ge=0, le=1, description="Weight for this objective (0-1)")
    direction: str = Field("maximize", pattern="^(maximize|minimize)$")
    target: Optional[float] = Field(None, description="Target value to achieve")


class SeedFeedbackItem(BaseModel):
    """
    Feedback collected outside the run (e.g., from prod) to guide a NEW GEPA run.
    This is attached to the baseline variant at job start and used for mutation guidance.
    """
    rating_numeric: int = Field(
        -1,
        ge=-2,
        le=2,
        description="Numeric rating (-2..+2). Negative means 'needs improvement'.",
    )
    comment: str = Field(..., min_length=1, max_length=5000, description="Feedback text from users/humans")
    tags: Optional[List[str]] = Field(None, max_length=20, description="Optional tags (e.g., 'too_verbose')")
    improvement_suggestions: Optional[str] = Field(None, max_length=2000)
    target_components: Optional[List[ComponentType]] = Field(
        None,
        description="Optional: which GEPA component(s) this feedback should apply to",
    )


class CreateOptimizerJobRequest(BaseModel):
    """Request to create a new GEPA optimizer job."""
    name: str = Field(..., min_length=1, max_length=255, description="Name for this optimization run")
    description: Optional[str] = Field(None, description="Description of optimization goals")

    # Domain integration (Prompt Management)
    domain: Optional[str] = Field(
        None,
        description="Domain identifier (e.g., 'fasb', 'insurance'). If set with use_prompt_management=true, missing component initial values will be loaded from Prompt Management active prompts.",
    )
    use_prompt_management: bool = Field(
        True,
        description="If true and domain is provided, prefill missing component initial values from Prompt Management.",
    )

    # Seed feedback (e.g., from prod) for the CURRENT prompts
    seed_feedback: Optional[List[SeedFeedbackItem]] = Field(
        None,
        description="Optional feedback (e.g., from prod) to guide this new run. Will be attached to the baseline variant and used in mutations.",
    )

    import_prompt_feedback: bool = Field(
        False,
        description="If true and seed_feedback is not provided, import feedback from Prompt Management for this domain/environment and attach it to the baseline variant.",
    )
    prompt_feedback_environment: str = Field(
        "prod",
        pattern="^(prod|staging|dev)$",
        description="Environment to import feedback from (default: prod).",
    )
    prompt_feedback_limit: int = Field(
        20,
        ge=1,
        le=200,
        description="Max feedback items to import from Prompt Management.",
    )
    
    # Target configuration
    agent_config_id: Optional[int] = Field(None, description="Agent configuration ID to optimize")
    eval_suite_id: Optional[int] = Field(None, description="Evaluation suite ID to use")
    
    # Components to optimize
    components: List[ComponentConfig] = Field(
        default_factory=list,
        description="Components to optimize. If domain+use_prompt_management are set, components may omit initial_value and will be auto-filled.",
    )
    
    # Objectives
    objectives: List[ObjectiveConfig] = Field(
        default=[
            ObjectiveConfig(name=OptimizationObjective.QUALITY, weight=0.4),
            ObjectiveConfig(name=OptimizationObjective.GROUNDEDNESS, weight=0.3),
            ObjectiveConfig(name=OptimizationObjective.LATENCY, weight=0.15, direction="minimize"),
            ObjectiveConfig(name=OptimizationObjective.COST, weight=0.15, direction="minimize"),
        ],
        description="Optimization objectives with weights"
    )
    
    # Algorithm parameters
    population_size: int = Field(10, ge=4, le=50, description="Population size for each generation")
    max_iterations: int = Field(20, ge=1, le=100, description="Maximum number of generations")
    eval_budget: int = Field(500, ge=10, le=5000, description="Maximum total evaluations allowed")
    mutation_rate: float = Field(0.3, ge=0.0, le=1.0, description="Probability of mutation")
    crossover_rate: float = Field(0.5, ge=0.0, le=1.0, description="Probability of crossover")
    elite_count: int = Field(2, ge=1, le=10, description="Number of elite individuals to preserve")
    optimization_strategy: OptimizationStrategy = Field(
        OptimizationStrategy.DSPY_MIPRO,
        description="Optimization strategy backend",
    )
    
    # Evaluation config
    eval_sample_size: Optional[int] = Field(None, ge=1, le=100, description="Questions per eval (None = use full suite)")
    eval_concurrency: int = Field(3, ge=1, le=10, description="Parallel evaluation workers")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Optimize FASB RAG Prompts",
                "description": "Improve quality and groundedness while reducing latency",
                "components": [
                    {
                        "component_type": "query_rewrite_prompt",
                        "initial_value": "Rewrite the following user question..."
                    },
                    {
                        "component_type": "answer_synthesis_prompt", 
                        "initial_value": "Based on the retrieved context..."
                    }
                ],
                "objectives": [
                    {"name": "quality", "weight": 0.4},
                    {"name": "groundedness", "weight": 0.3},
                    {"name": "latency", "weight": 0.15, "direction": "minimize"},
                    {"name": "cost", "weight": 0.15, "direction": "minimize"}
                ],
                "population_size": 10,
                "max_iterations": 20,
                "eval_budget": 500
            }
        }

    @field_validator('objectives')
    @classmethod
    def validate_weights_sum(cls, objectives):
        total_weight = sum(obj.weight for obj in objectives)
        if abs(total_weight - 1.0) > 0.01:
            # Auto-normalize weights
            for obj in objectives:
                obj.weight = obj.weight / total_weight
        return objectives

    @model_validator(mode="after")
    def validate_components_or_domain(self):
        # If no component values are provided, we must have a domain to prefill from.
        has_any_initial = any((c.initial_value or "").strip() for c in (self.components or []))
        if not has_any_initial and not (self.domain and self.use_prompt_management):
            raise ValueError(
                "Provide at least one component initial_value, or set domain with use_prompt_management=true to prefill from Prompt Management."
            )
        return self


class PauseJobRequest(BaseModel):
    """Request to pause/resume an optimizer job."""
    reason: Optional[str] = Field(None, description="Reason for pausing")


class CancelJobRequest(BaseModel):
    """Request to cancel an optimizer job."""
    reason: Optional[str] = Field(None, description="Reason for cancellation")


class TryVariantRequest(BaseModel):
    """Request to temporarily try a variant in a chat session."""
    session_id: Optional[str] = Field(None, description="Existing chat session to use")
    query: Optional[str] = Field(None, description="Test query to run")


class PromoteVariantRequest(BaseModel):
    """Request to promote a variant to an environment via Prompt Management."""
    environment: str = Field(..., pattern="^(dev|staging|prod)$", description="Target environment")
    domain: Optional[str] = Field(None, description="Target domain for prompts (e.g., 'fasb', 'insurance')")
    auto_activate: bool = Field(False, description="Immediately activate the new prompt versions")
    notes: Optional[str] = Field(None, description="Promotion notes/reason")
    create_backup: bool = Field(True, description="Create backup of current prompt values")
    agent_config_id: Optional[int] = Field(None, description="[Deprecated] Use domain instead")


# ============= Response Schemas =============

class ComponentDiff(BaseModel):
    """Diff between baseline and variant for a component."""
    component_type: str
    baseline_value: str
    variant_value: str
    added_lines: Optional[List[str]] = None
    removed_lines: Optional[List[str]] = None
    similarity_score: Optional[float] = None


class VariantScores(BaseModel):
    """Scores for a candidate variant."""
    quality_score: Optional[float] = None
    groundedness_score: Optional[float] = None
    citation_accuracy: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    avg_cost: Optional[float] = None
    factual_correctness: Optional[float] = None
    faithfulness: Optional[float] = None


class CandidateVariantSummary(BaseModel):
    """Summary of a candidate variant."""
    id: int
    variant_id: str
    generation: int
    mutation_type: Optional[MutationType] = None
    parent_variant_ids: Optional[List[str]] = None
    status: VariantStatus
    scores: VariantScores
    pareto_rank: Optional[int] = None
    crowding_distance: Optional[float] = None
    is_baseline: bool = False
    is_promoted: bool = False
    promoted_to: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class CandidateVariantDetail(CandidateVariantSummary):
    """Detailed variant information including component values."""
    component_values: Dict[str, str]
    component_diffs: Optional[List[ComponentDiff]] = None
    eval_results_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    error_count: int = 0


class ParetoFrontierPoint(BaseModel):
    """A point on the Pareto frontier."""
    variant_id: str
    scores: Dict[str, float]  # {"quality": 0.9, "latency": 500, ...}
    
    class Config:
        from_attributes = True


class ParetoSnapshotSummary(BaseModel):
    """Summary of a Pareto frontier snapshot."""
    iteration: int
    frontier_count: int
    frontier_variant_ids: List[str]
    hypervolume: Optional[float] = None
    diversity_score: Optional[float] = None
    frontier_stats: Dict[str, Dict[str, float]]  # {"quality": {"min": 0.7, "max": 0.95, "mean": 0.85}, ...}
    created_at: datetime
    
    class Config:
        from_attributes = True


class OptimizerJobSummary(BaseModel):
    """Summary of an optimizer job."""
    id: int
    job_id: str
    name: str
    description: Optional[str] = None
    status: OptimizerJobStatus
    target_components: List[str]
    objectives: List[str]
    optimization_strategy: str
    population_size: int
    max_iterations: int
    current_iteration: int
    total_evals_used: int
    eval_budget: int
    best_quality_score: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class OptimizerJobDetail(OptimizerJobSummary):
    """Detailed optimizer job information."""
    baseline_components: Dict[str, str]
    objective_weights: Optional[Dict[str, float]] = None
    mutation_rate: float
    crossover_rate: float
    elite_count: int
    agent_config_id: Optional[int] = None
    eval_suite_id: Optional[int] = None
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    
    # Current frontier
    current_frontier: Optional[List[ParetoFrontierPoint]] = None
    
    # Best variant
    best_variant: Optional[CandidateVariantSummary] = None
    
    # Progress history
    frontier_history: Optional[List[ParetoSnapshotSummary]] = None


class CreateOptimizerJobResponse(BaseModel):
    """Response when creating an optimizer job."""
    job_id: str
    status: OptimizerJobStatus
    message: str
    sse_url: str = Field(..., description="URL to stream optimization progress via SSE")


class OptimizerJobListResponse(BaseModel):
    """List of optimizer jobs."""
    jobs: List[OptimizerJobSummary]
    total: int
    page: int
    page_size: int


class VariantListResponse(BaseModel):
    """List of candidate variants for a job."""
    variants: List[CandidateVariantSummary]
    total: int
    page: int
    page_size: int
    
    # Aggregate stats
    frontier_count: int = 0
    evaluated_count: int = 0
    pending_count: int = 0


class TryVariantResponse(BaseModel):
    """Response from trying a variant."""
    session_id: str
    variant_id: str
    query: Optional[str] = None
    response: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    comparison: Optional[Dict[str, Any]] = None  # Comparison with baseline


class PromptCreatedInfo(BaseModel):
    """Info about a prompt created during promotion."""
    component: str
    prompt_id: int
    version: int
    prompt_type: str


class PromoteVariantResponse(BaseModel):
    """Response from promoting a variant via Prompt Management."""
    success: bool
    variant_id: str
    environment: str
    domain: Optional[str] = None
    promotion_id: int  # ID in promotion history
    prompts_created: Optional[List[PromptCreatedInfo]] = None
    auto_activated: bool = False
    message: str
    backup_created: bool = False
    agent_config_id: Optional[int] = None  # Deprecated


# ============= SSE Event Schemas =============

class GEPATelemetryEvent(BaseModel):
    """Telemetry event for SSE streaming."""
    event_type: str  # "info", "progress", "mutation", "evaluation", "frontier", "error", "complete"
    stage_name: Optional[str] = None
    message: Optional[str] = None
    progress_percentage: Optional[float] = None
    iteration: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime


# ============= Evaluation Result Schemas =============

class EvalResultSummary(BaseModel):
    """Summary of an evaluation result."""
    id: int
    eval_case_id: str
    question: str
    verdict: Optional[str] = None
    factual_correctness: Optional[float] = None
    faithfulness: Optional[float] = None
    citation_compliance: Optional[float] = None
    latency_ms: Optional[float] = None
    
    class Config:
        from_attributes = True


class EvalResultDetail(EvalResultSummary):
    """Detailed evaluation result."""
    expected_answer: Optional[str] = None
    model_response: Optional[str] = None
    verdict_reason: Optional[str] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    answer_relevance: Optional[float] = None
    estimated_cost: Optional[float] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    retrieved_docs: Optional[List[Dict[str, Any]]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


class VariantEvalResultsResponse(BaseModel):
    """Evaluation results for a variant."""
    variant_id: str
    results: List[EvalResultSummary]
    total: int
    pass_count: int
    fail_count: int
    error_count: int
    aggregate_scores: VariantScores


# ============= Trace Schemas =============

class TraceStep(BaseModel):
    """A single step in an execution trace."""
    step_type: str  # "query_rewrite", "retrieval", "tool_call", "generation"
    input: Optional[str] = None
    output: Optional[str] = None
    latency_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class TraceSummary(BaseModel):
    """Summary of a trace artifact."""
    id: int
    trace_id: str
    trace_type: str
    eval_case_id: Optional[str] = None
    total_latency_ms: Optional[float] = None
    total_tokens: Optional[int] = None
    step_count: Optional[int] = None
    error_count: Optional[int] = None
    created_at: datetime


class TraceDetail(TraceSummary):
    """Detailed trace information."""
    steps: List[TraceStep]
    reflection_insights: Optional[Dict[str, Any]] = None


class VariantTracesResponse(BaseModel):
    """Traces for a variant."""
    variant_id: str
    traces: List[TraceSummary]
    total: int


# ============= Comparison Schemas =============

class VariantComparisonRequest(BaseModel):
    """Request to compare variants."""
    variant_ids: List[str] = Field(..., min_length=2, max_length=10)
    include_diffs: bool = Field(True, description="Include component diffs")
    include_eval_details: bool = Field(False, description="Include individual eval results")


class VariantComparison(BaseModel):
    """Comparison between variants."""
    variants: List[CandidateVariantDetail]
    score_comparison: Dict[str, List[float]]  # {"quality": [0.8, 0.85, 0.9], ...}
    best_for: Dict[str, str]  # {"quality": "variant_3", "latency": "variant_1"}
    pareto_optimal: List[str]  # Variant IDs on the frontier


# ============= Promotion History Schemas =============

class PromotionHistoryItem(BaseModel):
    """A single promotion history entry."""
    id: int
    variant_id: Optional[int] = None
    job_id: Optional[int] = None
    environment: str
    promoted_by_user_id: int
    agent_config_id: Optional[int] = None
    scores_at_promotion: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    is_rolled_back: bool = False
    rolled_back_at: Optional[datetime] = None
    created_at: datetime


class PromotionHistoryResponse(BaseModel):
    """Promotion history for an agent config or job."""
    history: List[PromotionHistoryItem]
    total: int


class RollbackRequest(BaseModel):
    """Request to rollback a promotion."""
    promotion_id: int
    reason: Optional[str] = Field(None, description="Reason for rollback")


# ============= Human Feedback Schemas =============

class FeedbackType(str, Enum):
    """Type of human feedback."""
    PER_QUERY = "per_query"
    OVERALL = "overall"


class FeedbackRating(str, Enum):
    """Rating scale for feedback."""
    STRONGLY_NEGATIVE = "strongly_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    STRONGLY_POSITIVE = "strongly_positive"


RATING_TO_NUMERIC = {
    FeedbackRating.STRONGLY_NEGATIVE: -2,
    FeedbackRating.NEGATIVE: -1,
    FeedbackRating.NEUTRAL: 0,
    FeedbackRating.POSITIVE: 1,
    FeedbackRating.STRONGLY_POSITIVE: 2,
}


class SubmitFeedbackRequest(BaseModel):
    """Request to submit human feedback on a variant."""
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    rating: FeedbackRating = Field(..., description="Rating (-2 to +2)")
    
    # For per-query feedback
    eval_result_id: Optional[int] = Field(None, description="Evaluation result ID for per-query feedback")
    query_text: Optional[str] = Field(None, description="The query/question being rated")
    response_text: Optional[str] = Field(None, description="The response being rated")
    
    # Feedback content
    comment: Optional[str] = Field(None, max_length=5000, description="Detailed feedback comment")
    tags: Optional[List[str]] = Field(
        None, 
        max_length=20,
        description="Tags categorizing the feedback (e.g., 'too_verbose', 'good_citations')"
    )
    improvement_suggestions: Optional[str] = Field(
        None, 
        max_length=2000,
        description="Specific suggestions for improvement"
    )
    target_components: Optional[List[ComponentType]] = Field(
        None,
        description="Which component(s) this feedback applies to"
    )


class HumanFeedbackSummary(BaseModel):
    """Summary of a human feedback entry."""
    id: int
    variant_id: int
    feedback_type: FeedbackType
    rating: FeedbackRating
    rating_numeric: int
    comment: Optional[str] = None
    tags: Optional[List[str]] = None
    target_components: Optional[List[str]] = None
    user_id: int
    incorporated: bool = False
    created_at: datetime


class HumanFeedbackDetail(HumanFeedbackSummary):
    """Detailed human feedback entry."""
    job_id: int
    eval_result_id: Optional[int] = None
    query_text: Optional[str] = None
    response_text: Optional[str] = None
    improvement_suggestions: Optional[str] = None
    incorporated_at: Optional[datetime] = None
    incorporated_in_variant_id: Optional[int] = None


class VariantFeedbackResponse(BaseModel):
    """Feedback for a variant."""
    variant_id: str
    feedback: List[HumanFeedbackSummary]
    total: int
    average_rating: Optional[float] = None
    rating_distribution: Dict[str, int]  # {"strongly_positive": 3, "positive": 5, ...}


class JobFeedbackResponse(BaseModel):
    """All feedback for a job."""
    job_id: str
    feedback: List[HumanFeedbackDetail]
    total: int
    unincorporated_count: int
    by_variant: Dict[str, int]  # variant_id -> feedback count


class FeedbackStatsResponse(BaseModel):
    """Statistics about feedback for a job."""
    job_id: str
    total_feedback: int
    incorporated_count: int
    pending_count: int
    average_rating: Optional[float] = None
    feedback_by_type: Dict[str, int]  # {"per_query": 5, "overall": 10}
    feedback_by_rating: Dict[str, int]  # {"positive": 8, "negative": 2, ...}
    most_tagged: List[str]  # Most common tags
    variants_with_feedback: int
