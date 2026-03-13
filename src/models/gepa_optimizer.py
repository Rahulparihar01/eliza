"""
GEPA Optimizer Models

Database models for GEPA (Genetic Prompt Algorithm) optimization runs.
Tracks optimizer jobs, candidate variants, evaluation results, traces, and Pareto frontiers.
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, ForeignKey, 
    JSON, Enum, Boolean, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.database import BaseModel


class OptimizerJobStatus(str, PyEnum):
    """Status of a GEPA optimizer job."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VariantStatus(str, PyEnum):
    """Status of a candidate variant."""
    PENDING = "pending"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"
    FAILED = "failed"
    PROMOTED = "promoted"


class ComponentType(str, PyEnum):
    """Types of mutable text components."""
    QUERY_REWRITE_PROMPT = "query_rewrite_prompt"
    RETRIEVAL_INSTRUCTIONS = "retrieval_instructions"
    TOOL_INSTRUCTIONS = "tool_instructions"
    ANSWER_SYNTHESIS_PROMPT = "answer_synthesis_prompt"
    SYSTEM_PROMPT = "system_prompt"
    FEW_SHOT_EXAMPLES = "few_shot_examples"
    TEXTUAL_SPEC = "textual_spec"
    CUSTOM = "custom"


class MutationType(str, PyEnum):
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


class OptimizerJob(BaseModel):
    """
    A GEPA optimization job.
    
    Tracks the configuration, status, and progress of an optimization run.
    """
    __tablename__ = "gepa_optimizer_jobs"
    
    # Job identification
    job_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # Target configuration
    agent_config_id = Column(Integer, ForeignKey("agent_configurations.id"), nullable=True)
    eval_suite_id = Column(Integer, nullable=True)  # Reference to eval suite
    
    # Job name and description
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Domain identifier (ties this GEPA job to a Prompt Management domain)
    domain = Column(String(100), nullable=True, index=True)
    
    # Components being optimized (list of component identifiers)
    target_components = Column(JSON, nullable=False)  # ["query_rewrite_prompt", "answer_synthesis_prompt"]
    
    # Initial component values (baseline)
    baseline_components = Column(JSON, nullable=False)  # {"query_rewrite_prompt": "...", ...}
    
    # Optimization configuration
    population_size = Column(Integer, default=10, nullable=False)
    max_iterations = Column(Integer, default=20, nullable=False)
    eval_budget = Column(Integer, default=500, nullable=False)  # Max total evaluations
    mutation_rate = Column(Float, default=0.3, nullable=False)
    crossover_rate = Column(Float, default=0.5, nullable=False)
    elite_count = Column(Integer, default=2, nullable=False)  # Top performers to preserve
    
    # Multi-objective weights (for weighted-sum approach, normalized to 1.0)
    objective_weights = Column(JSON, nullable=True)  # {"quality": 0.4, "groundedness": 0.3, "latency": 0.2, "cost": 0.1}
    
    # Optimization objectives (metrics to optimize)
    objectives = Column(JSON, nullable=False)  # ["quality", "groundedness", "citation_accuracy", "latency", "cost"]
    optimization_strategy = Column(String(50), nullable=False, default="genetic")
    
    # Status and progress
    status = Column(
        Enum(
            OptimizerJobStatus,
            name='optimizer_job_status',
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            create_type=False,  # Enum created by migration
        ),
        nullable=False,
        default=OptimizerJobStatus.PENDING,
    )
    
    # Progress tracking
    current_iteration = Column(Integer, default=0, nullable=False)
    total_evals_used = Column(Integer, default=0, nullable=False)
    
    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Best results (cached for quick access)
    best_variant_id = Column(Integer, ForeignKey("gepa_candidate_variants.id", use_alter=True), nullable=True)
    best_quality_score = Column(Float, nullable=True)
    
    # Celery task tracking
    celery_task_id = Column(String(100), nullable=True)
    
    # Relationships
    variants = relationship(
        "CandidateVariant", 
        back_populates="optimizer_job",
        foreign_keys="CandidateVariant.job_id",
        cascade="all, delete-orphan"
    )
    pareto_snapshots = relationship(
        "ParetoSnapshot", 
        back_populates="optimizer_job",
        cascade="all, delete-orphan"
    )
    telemetry_events = relationship(
        "GEPATelemetryEvent",
        back_populates="optimizer_job",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index('ix_gepa_jobs_customer_status', 'customer_id', 'status'),
    )
    
    def __repr__(self):
        return f"<OptimizerJob(job_id={self.job_id}, status={self.status}, iteration={self.current_iteration})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "customer_id": self.customer_id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "target_components": self.target_components,
            "population_size": self.population_size,
            "max_iterations": self.max_iterations,
            "eval_budget": self.eval_budget,
            "objectives": self.objectives,
            "objective_weights": self.objective_weights,
            "optimization_strategy": self.optimization_strategy,
            "status": self.status.value if self.status else None,
            "current_iteration": self.current_iteration,
            "total_evals_used": self.total_evals_used,
            "best_quality_score": self.best_quality_score,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CandidateVariant(BaseModel):
    """
    A candidate variant (individual) in the GEPA population.
    
    Stores the mutated component values and evaluation results.
    """
    __tablename__ = "gepa_candidate_variants"
    
    # Link to optimizer job
    job_id = Column(Integer, ForeignKey("gepa_optimizer_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Variant identification
    variant_id = Column(String(100), nullable=False)  # Unique within job
    generation = Column(Integer, nullable=False, default=0)  # Which iteration created this
    
    # Lineage (for crossover and mutation tracking)
    parent_variant_ids = Column(JSON, nullable=True)  # [parent1_id, parent2_id] for crossover
    mutation_type = Column(
        Enum(
            MutationType,
            name='mutation_type',
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            create_type=False,  # Enum created by migration
        ),
        nullable=True,
    )
    
    # Component values (the actual prompt text for each component)
    component_values = Column(JSON, nullable=False)  # {"query_rewrite_prompt": "...", ...}
    
    # Diff from baseline (for UI display)
    component_diffs = Column(JSON, nullable=True)  # {"query_rewrite_prompt": {"added": [...], "removed": [...]}}
    
    # Status
    status = Column(
        Enum(
            VariantStatus,
            name='variant_status',
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            create_type=False,  # Enum created by migration
        ),
        nullable=False,
        default=VariantStatus.PENDING,
    )
    
    # Aggregate scores (computed from evaluation results)
    quality_score = Column(Float, nullable=True)  # Composite quality metric
    groundedness_score = Column(Float, nullable=True)  # Faithfulness/grounding
    citation_accuracy = Column(Float, nullable=True)  # Citation correctness
    avg_latency_ms = Column(Float, nullable=True)  # Average response latency
    avg_cost = Column(Float, nullable=True)  # Average cost per query
    
    # Pareto ranking
    pareto_rank = Column(Integer, nullable=True)  # 0 = on frontier, 1 = dominated by 1, etc.
    crowding_distance = Column(Float, nullable=True)  # For diversity preservation
    
    # Is this the baseline/initial variant?
    is_baseline = Column(Boolean, default=False, nullable=False)
    
    # Has this been promoted to production?
    is_promoted = Column(Boolean, default=False, nullable=False)
    promoted_at = Column(DateTime, nullable=True)
    promoted_to = Column(String(50), nullable=True)  # "dev", "staging", "prod"
    
    # Relationships
    optimizer_job = relationship(
        "OptimizerJob", 
        back_populates="variants",
        foreign_keys=[job_id]
    )
    evaluation_results = relationship(
        "GEPAEvaluationResult", 
        back_populates="variant",
        cascade="all, delete-orphan"
    )
    trace_artifacts = relationship(
        "TraceArtifact", 
        back_populates="variant",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('job_id', 'variant_id', name='uq_job_variant'),
        Index('ix_gepa_variants_job_generation', 'job_id', 'generation'),
        Index('ix_gepa_variants_pareto_rank', 'job_id', 'pareto_rank'),
    )
    
    def __repr__(self):
        return f"<CandidateVariant(variant_id={self.variant_id}, gen={self.generation}, quality={self.quality_score})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "variant_id": self.variant_id,
            "generation": self.generation,
            "parent_variant_ids": self.parent_variant_ids,
            "mutation_type": self.mutation_type.value if self.mutation_type else None,
            "component_values": self.component_values,
            "component_diffs": self.component_diffs,
            "status": self.status.value if self.status else None,
            "quality_score": self.quality_score,
            "groundedness_score": self.groundedness_score,
            "citation_accuracy": self.citation_accuracy,
            "avg_latency_ms": self.avg_latency_ms,
            "avg_cost": self.avg_cost,
            "pareto_rank": self.pareto_rank,
            "crowding_distance": self.crowding_distance,
            "is_baseline": self.is_baseline,
            "is_promoted": self.is_promoted,
            "promoted_to": self.promoted_to,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GEPAEvaluationResult(BaseModel):
    """
    Evaluation result for a single test case against a variant.
    """
    __tablename__ = "gepa_evaluation_results"
    
    # Link to variant
    variant_id = Column(Integer, ForeignKey("gepa_candidate_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Test case identification
    eval_case_id = Column(String(100), nullable=False)  # From eval suite
    question = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=True)
    
    # Model response
    model_response = Column(Text, nullable=True)
    
    # Individual metrics
    factual_correctness = Column(Float, nullable=True)
    faithfulness = Column(Float, nullable=True)
    context_precision = Column(Float, nullable=True)
    context_recall = Column(Float, nullable=True)
    citation_compliance = Column(Float, nullable=True)
    answer_relevance = Column(Float, nullable=True)
    
    # Verdict
    verdict = Column(String(20), nullable=True)  # "pass", "fail", "error"
    verdict_reason = Column(Text, nullable=True)
    
    # Performance metrics
    latency_ms = Column(Float, nullable=True)
    token_count = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    
    # Tool calls made
    tool_calls = Column(JSON, nullable=True)  # [{name, args, result}, ...]
    
    # Retrieved documents
    retrieved_docs = Column(JSON, nullable=True)  # [{doc_id, chunk_id, score}, ...]
    
    # Error tracking
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    variant = relationship("CandidateVariant", back_populates="evaluation_results")
    
    __table_args__ = (
        Index('ix_gepa_eval_results_variant', 'variant_id'),
    )
    
    def __repr__(self):
        return f"<GEPAEvaluationResult(eval_case_id={self.eval_case_id}, verdict={self.verdict})>"


class TraceArtifact(BaseModel):
    """
    Detailed execution trace for debugging and reflection-based mutation.
    
    Stores the full execution trace including intermediate steps, tool calls,
    retrieved documents, and any errors or failures.
    """
    __tablename__ = "gepa_trace_artifacts"
    
    # Link to variant
    variant_id = Column(Integer, ForeignKey("gepa_candidate_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Trace identification
    trace_id = Column(String(100), nullable=False)
    eval_case_id = Column(String(100), nullable=True)  # If linked to an eval case
    
    # Trace type
    trace_type = Column(String(50), nullable=False)  # "execution", "failure", "reflection"
    
    # Full trace data
    trace_data = Column(JSON, nullable=False)
    # Structure: {
    #   "steps": [
    #     {"type": "query_rewrite", "input": "...", "output": "...", "latency_ms": 50},
    #     {"type": "retrieval", "query": "...", "results": [...], "latency_ms": 200},
    #     {"type": "tool_call", "name": "...", "args": {...}, "result": {...}},
    #     {"type": "generation", "prompt": "...", "response": "...", "tokens": 500}
    #   ],
    #   "total_latency_ms": 800,
    #   "total_tokens": 1200,
    #   "errors": [...]
    # }
    
    # Summary metrics from trace
    total_latency_ms = Column(Float, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    step_count = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    
    # Reflection insights (generated by LLM analyzing the trace)
    reflection_insights = Column(JSON, nullable=True)
    # Structure: {
    #   "failure_patterns": ["Retrieval missed key context", ...],
    #   "improvement_suggestions": ["Add more specific retrieval instructions", ...],
    #   "component_feedback": {"query_rewrite_prompt": "Consider...", ...}
    # }
    
    # Relationships
    variant = relationship("CandidateVariant", back_populates="trace_artifacts")
    
    __table_args__ = (
        Index('ix_gepa_traces_variant_type', 'variant_id', 'trace_type'),
    )
    
    def __repr__(self):
        return f"<TraceArtifact(trace_id={self.trace_id}, type={self.trace_type})>"


class ParetoSnapshot(BaseModel):
    """
    Snapshot of the Pareto frontier at a given iteration.
    
    Used for tracking optimization progress and visualizing convergence.
    """
    __tablename__ = "gepa_pareto_snapshots"
    
    # Link to optimizer job
    job_id = Column(Integer, ForeignKey("gepa_optimizer_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Iteration number
    iteration = Column(Integer, nullable=False)
    
    # Frontier data
    frontier_variant_ids = Column(JSON, nullable=False)  # [variant_id1, variant_id2, ...]
    frontier_count = Column(Integer, nullable=False)
    
    # Frontier statistics
    frontier_stats = Column(JSON, nullable=False)
    # Structure: {
    #   "quality": {"min": 0.7, "max": 0.95, "mean": 0.85},
    #   "groundedness": {"min": 0.6, "max": 0.9, "mean": 0.78},
    #   "latency": {"min": 500, "max": 2000, "mean": 1000},
    #   "cost": {"min": 0.01, "max": 0.05, "mean": 0.025}
    # }
    
    # Hypervolume indicator (for measuring frontier quality)
    hypervolume = Column(Float, nullable=True)
    
    # Population diversity metric
    diversity_score = Column(Float, nullable=True)
    
    # Relationships
    optimizer_job = relationship("OptimizerJob", back_populates="pareto_snapshots")
    
    __table_args__ = (
        UniqueConstraint('job_id', 'iteration', name='uq_job_iteration'),
        Index('ix_gepa_pareto_job_iteration', 'job_id', 'iteration'),
    )
    
    def __repr__(self):
        return f"<ParetoSnapshot(job_id={self.job_id}, iteration={self.iteration}, frontier_count={self.frontier_count})>"


class GEPATelemetryEvent(BaseModel):
    """
    Telemetry events for GEPA optimization runs (for SSE streaming).
    """
    __tablename__ = "gepa_telemetry_events"
    
    job_id = Column(Integer, ForeignKey("gepa_optimizer_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    event_type = Column(String(50), nullable=False)  # "info", "progress", "mutation", "evaluation", "frontier", "error", "complete"
    stage_name = Column(String(100), nullable=True)
    message = Column(Text, nullable=True)
    progress_percentage = Column(Float, nullable=True)
    
    # Additional data
    data = Column(JSON, nullable=True)
    
    # Relationships
    optimizer_job = relationship("OptimizerJob", back_populates="telemetry_events")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "event_type": self.event_type,
            "stage_name": self.stage_name,
            "message": self.message,
            "progress_percentage": self.progress_percentage,
            "data": self.data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PromotedVariantHistory(BaseModel):
    """
    Audit trail for promoted variants.
    
    Tracks when variants were promoted to different environments.
    """
    __tablename__ = "gepa_promoted_variant_history"
    
    # Link to variant
    variant_id = Column(Integer, ForeignKey("gepa_candidate_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("gepa_optimizer_jobs.id", ondelete="SET NULL"), nullable=True)
    
    # Snapshot of variant at promotion time
    variant_snapshot = Column(JSON, nullable=False)  # Full component values
    
    # Promotion details
    environment = Column(String(50), nullable=False)  # "dev", "staging", "prod"
    promoted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Agent config that was updated
    agent_config_id = Column(Integer, ForeignKey("agent_configurations.id"), nullable=True)
    
    # Previous values (for rollback)
    previous_values = Column(JSON, nullable=True)

    # Additional rollback metadata (e.g., prompt IDs created during promotion)
    rollback_info = Column(JSON, nullable=True)
    
    # Scores at promotion time
    scores_at_promotion = Column(JSON, nullable=True)  # {"quality": 0.9, "groundedness": 0.85, ...}
    
    # Notes/reason for promotion
    notes = Column(Text, nullable=True)
    
    # Rollback tracking
    is_rolled_back = Column(Boolean, default=False, nullable=False)
    rolled_back_at = Column(DateTime, nullable=True)
    rolled_back_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    __table_args__ = (
        Index('ix_gepa_promoted_env_time', 'environment', 'created_at'),
    )
    
    def __repr__(self):
        return f"<PromotedVariantHistory(variant_id={self.variant_id}, env={self.environment})>"


class FeedbackType(str, PyEnum):
    """Type of human feedback."""
    PER_QUERY = "per_query"  # Feedback on a specific test case/query response
    OVERALL = "overall"  # General feedback on the variant


class FeedbackRating(str, PyEnum):
    """Rating scale for feedback."""
    STRONGLY_NEGATIVE = "strongly_negative"  # -2
    NEGATIVE = "negative"  # -1
    NEUTRAL = "neutral"  # 0
    POSITIVE = "positive"  # +1
    STRONGLY_POSITIVE = "strongly_positive"  # +2


class GEPAHumanFeedback(BaseModel):
    """
    Human feedback on candidate variants.
    
    Supports both per-query feedback (rating specific responses) and
    overall variant feedback (general impressions/guidance).
    
    This feedback is used to:
    1. Adjust fitness scores (feedback bonus)
    2. Guide reflection-based mutations
    3. Influence selection pressure
    """
    __tablename__ = "gepa_human_feedback"
    
    # Link to job and variant
    job_id = Column(Integer, ForeignKey("gepa_optimizer_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("gepa_candidate_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Feedback type
    feedback_type = Column(
        Enum(
            FeedbackType,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            create_type=False,  # Don't create enum on model load - migration handles it
        ),
        nullable=False,
    )
    
    # Rating (numeric for easy aggregation)
    rating = Column(
        Enum(
            FeedbackRating,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            create_type=False,  # Don't create enum on model load - migration handles it
        ),
        nullable=False,
    )
    rating_numeric = Column(Integer, nullable=False)  # -2 to +2
    
    # Optional: link to specific evaluation result (for per-query feedback)
    eval_result_id = Column(Integer, ForeignKey("gepa_evaluation_results.id", ondelete="SET NULL"), nullable=True)
    
    # The query/test case this feedback is about (for per-query feedback)
    query_text = Column(Text, nullable=True)
    response_text = Column(Text, nullable=True)  # The response being rated
    
    # Human feedback content
    comment = Column(Text, nullable=True)  # Free-form feedback
    
    # Structured feedback tags (for categorization)
    tags = Column(JSON, nullable=True)  # ["too_verbose", "good_citations", "wrong_tone", ...]
    
    # What specifically needs improvement?
    improvement_suggestions = Column(Text, nullable=True)
    
    # Which component(s) does this feedback apply to?
    target_components = Column(JSON, nullable=True)  # ["answer_synthesis_prompt", "query_rewrite_prompt"]
    
    # Who provided this feedback
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Has this feedback been incorporated into mutations?
    incorporated = Column(Boolean, default=False, nullable=False)
    incorporated_at = Column(DateTime, nullable=True)
    incorporated_in_variant_id = Column(Integer, ForeignKey("gepa_candidate_variants.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    optimizer_job = relationship("OptimizerJob", backref="human_feedback")
    variant = relationship("CandidateVariant", foreign_keys=[variant_id], backref="feedback")
    eval_result = relationship("GEPAEvaluationResult", backref="feedback")
    incorporated_in_variant = relationship("CandidateVariant", foreign_keys=[incorporated_in_variant_id])
    
    __table_args__ = (
        Index('ix_gepa_feedback_job_variant', 'job_id', 'variant_id'),
        Index('ix_gepa_feedback_unincorporated', 'job_id', 'incorporated'),
    )
    
    def __repr__(self):
        return f"<GEPAHumanFeedback(variant_id={self.variant_id}, rating={self.rating}, type={self.feedback_type})>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "variant_id": self.variant_id,
            "feedback_type": self.feedback_type.value if self.feedback_type else None,
            "rating": self.rating.value if self.rating else None,
            "rating_numeric": self.rating_numeric,
            "eval_result_id": self.eval_result_id,
            "query_text": self.query_text,
            "response_text": self.response_text,
            "comment": self.comment,
            "tags": self.tags,
            "improvement_suggestions": self.improvement_suggestions,
            "target_components": self.target_components,
            "user_id": self.user_id,
            "incorporated": self.incorporated,
            "incorporated_at": self.incorporated_at.isoformat() if self.incorporated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
