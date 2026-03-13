"""
RAG Evaluation Models

Database models for tracking RAG evaluation runs, results, and metrics.
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.database import BaseModel


class EvalRunStatus(str, PyEnum):
    """Status of an evaluation run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvalSource(str, PyEnum):
    """Source of evaluation questions for a run."""
    RANDOM_SAMPLING = "random_sampling"  # Traditional random/stratified sampling
    EVAL_SET = "eval_set"                # From a specific eval set (static or uploaded)


class EvalVerdict(str, PyEnum):
    """Verdict for individual evaluation questions."""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class RAGEvalRun(BaseModel):
    """
    Represents a single RAG evaluation run.
    
    Tracks configuration, metrics, and links to individual results.
    """
    __tablename__ = "rag_eval_runs"
    
    # Run identification
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # Run configuration
    domain = Column(String(50), nullable=False, default="fasb")  # fasb, insurance, etc.
    eval_type = Column(String(50), nullable=False, default="rag_full")  # rag_full, citation_validation
    sample_size = Column(Integer, nullable=False)
    difficulty_counts = Column(JSON, nullable=True)  # {"easy": 5, "medium": 5, "hard": 5}
    seed = Column(Integer, nullable=True, default=42)
    concurrency = Column(Integer, nullable=True, default=3)
    validate_citations = Column(Boolean, nullable=True, default=False)  # Enable citation page validation
    
    # Eval source tracking (for reproducibility)
    eval_source = Column(
        Enum(
            EvalSource,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
        default=EvalSource.RANDOM_SAMPLING,
    )
    eval_set_id = Column(Integer, ForeignKey("eval_sets.id", ondelete="SET NULL"), nullable=True, index=True)
    eval_set_name = Column(String(255), nullable=True)  # Snapshot of name at run time
    
    # Model configuration (snapshot at run time)
    chat_model = Column(String(100), nullable=True)
    embed_model = Column(String(100), nullable=True)
    judge_model = Column(String(100), nullable=True)
    knn_k = Column(Integer, nullable=True)
    retrieve_size = Column(Integer, nullable=True)
    rerank_keep = Column(Integer, nullable=True)
    prompt_template_snapshot = Column(JSON, nullable=True)  # WorkspacePromptTemplate snapshot
    
    # Status and timing
    # IMPORTANT: Persist enum *values* (lowercase), not names (uppercase),
    # because Postgres enum type is ('pending', 'running', ...) in production DBs.
    status = Column(
        Enum(
            EvalRunStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=EvalRunStatus.PENDING,
    )
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Aggregate metrics (computed after run completes)
    total_questions = Column(Integer, nullable=True)
    pass_count = Column(Integer, nullable=True)
    fail_count = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    pass_rate = Column(Float, nullable=True)
    
    # RAGAS metrics (mean values)
    factual_correctness_mean = Column(Float, nullable=True)
    faithfulness_mean = Column(Float, nullable=True)
    context_precision_mean = Column(Float, nullable=True)
    context_recall_mean = Column(Float, nullable=True)
    citation_compliance_mean = Column(Float, nullable=True)
    citation_page_accuracy_mean = Column(Float, nullable=True)
    
    # Metrics by difficulty (JSON)
    metrics_by_difficulty = Column(JSON, nullable=True)
    
    # Results artifacts
    results_file_path = Column(String(500), nullable=True)
    failures_file_path = Column(String(500), nullable=True)
    summary_file_path = Column(String(500), nullable=True)
    
    # Relationships
    results = relationship("RAGEvalResult", back_populates="eval_run", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<RAGEvalRun(run_id={self.run_id}, status={self.status}, pass_rate={self.pass_rate})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "customer_id": self.customer_id,
            "user_id": self.user_id,
            "domain": self.domain,
            "eval_type": self.eval_type,
            "sample_size": self.sample_size,
            "difficulty_counts": self.difficulty_counts,
            "seed": self.seed,
            "status": self.status.value if self.status else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_questions": self.total_questions,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "error_count": self.error_count,
            "pass_rate": self.pass_rate,
            "factual_correctness_mean": self.factual_correctness_mean,
            "faithfulness_mean": self.faithfulness_mean,
            "context_precision_mean": self.context_precision_mean,
            "context_recall_mean": self.context_recall_mean,
            "citation_compliance_mean": self.citation_compliance_mean,
            "citation_page_accuracy_mean": self.citation_page_accuracy_mean,
            "metrics_by_difficulty": self.metrics_by_difficulty,
            "chat_model": self.chat_model,
            "embed_model": self.embed_model,
            "judge_model": self.judge_model,
            "prompt_template_snapshot": self.prompt_template_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "eval_source": self.eval_source.value if self.eval_source else None,
            "eval_set_id": self.eval_set_id,
            "eval_set_name": self.eval_set_name,
        }


class RAGEvalResult(BaseModel):
    """
    Represents an individual evaluation result for a single question.
    """
    __tablename__ = "rag_eval_results"
    
    # Link to parent run
    eval_run_id = Column(Integer, ForeignKey("rag_eval_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Question identification
    eval_id = Column(String(100), nullable=False)  # Original eval_id from JSONL
    question_index = Column(Integer, nullable=False)  # Order in the run
    
    # Question content
    question = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=False)
    difficulty = Column(String(50), nullable=True)
    
    # Model response
    model_response = Column(Text, nullable=True)
    
    # Verdict
    # IMPORTANT: Persist enum *values* (lowercase), not names (uppercase),
    # because Postgres enum type is ('pass', 'fail', 'error') in production DBs.
    verdict = Column(
        Enum(
            EvalVerdict,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )
    verdict_reason = Column(Text, nullable=True)
    
    # Citations
    citations = Column(JSON, nullable=True)  # List of citation strings
    citation_compliance = Column(Integer, nullable=True)  # 0 or 1
    citation_page_validations = Column(JSON, nullable=True)  # Per-citation page validation results
    citation_page_score = Column(Float, nullable=True)  # Aggregate citation page score
    
    # Retrieved contexts
    contexts_count = Column(Integer, nullable=True)
    
    # RAGAS metrics
    factual_correctness = Column(Float, nullable=True)
    faithfulness = Column(Float, nullable=True)
    context_precision = Column(Float, nullable=True)
    context_recall = Column(Float, nullable=True)
    
    # Timing
    processing_time_ms = Column(Integer, nullable=True)
    
    # Relationship
    eval_run = relationship("RAGEvalRun", back_populates="results")
    
    def __repr__(self):
        return f"<RAGEvalResult(eval_id={self.eval_id}, verdict={self.verdict})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "eval_run_id": self.eval_run_id,
            "eval_id": self.eval_id,
            "question_index": self.question_index,
            "question": self.question,
            "expected_answer": self.expected_answer,
            "difficulty": self.difficulty,
            "model_response": self.model_response,
            "verdict": self.verdict.value if self.verdict else None,
            "verdict_reason": self.verdict_reason,
            "citations": self.citations,
            "citation_compliance": self.citation_compliance,
            "citation_page_validations": self.citation_page_validations,
            "citation_page_score": self.citation_page_score,
            "contexts_count": self.contexts_count,
            "factual_correctness": self.factual_correctness,
            "faithfulness": self.faithfulness,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RAGEvalTelemetryEvent(BaseModel):
    """
    Telemetry events for evaluation runs (for SSE streaming).
    """
    __tablename__ = "rag_eval_telemetry_events"
    
    eval_run_id = Column(Integer, ForeignKey("rag_eval_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    event_type = Column(String(50), nullable=False)  # info, progress, error, complete
    stage_name = Column(String(100), nullable=True)
    message = Column(Text, nullable=True)
    progress_percentage = Column(Float, nullable=True)
    
    # Additional data
    data = Column(JSON, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "eval_run_id": self.eval_run_id,
            "event_type": self.event_type,
            "stage_name": self.stage_name,
            "message": self.message,
            "progress_percentage": self.progress_percentage,
            "data": self.data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
