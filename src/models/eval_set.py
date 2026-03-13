"""
Eval Set Models - Static and Uploaded Evaluation Sets.

Provides first-class support for repeatable, non-random evaluations
by allowing users to define and upload curated eval sets.
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean,
    ForeignKey, JSON, Enum, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.database import BaseModel


class EvalSetType(str, PyEnum):
    """Type of evaluation set."""
    STATIC = "static"       # Built-in curated sets (globally visible)
    UPLOADED = "uploaded"   # User-uploaded sets (tenant-scoped)


class EvalSetCategory(str, PyEnum):
    """Category/focus area of the eval set."""
    GENERAL = "general"                 # Mixed questions
    RETRIEVAL = "retrieval"             # Retrieval quality focus
    SYNTHESIS = "synthesis"             # Answer synthesis focus
    GROUNDING = "grounding"             # Citation/grounding focus
    MULTI_HOP = "multi_hop"             # Multi-hop reasoning
    EDGE_CASES = "edge_cases"           # Edge cases and conflicts
    REGRESSION = "regression"           # Regression testing
    CUSTOM = "custom"                   # User-defined category


class EvalSet(BaseModel):
    """
    Represents an evaluation set - a collection of eval questions.
    
    Static sets are globally visible (customer_id = NULL).
    Uploaded sets are tenant-scoped (customer_id = tenant).
    """
    __tablename__ = "eval_sets"
    
    # Identification
    customer_id = Column(String(100), nullable=True, index=True)  # NULL for static/built-in
    
    # Metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    domain = Column(String(50), nullable=False, default="fasb")  # fasb, insurance, etc.
    
    # Type and category
    set_type = Column(
        Enum(EvalSetType, name='eval_set_type', values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        default=EvalSetType.UPLOADED
    )
    category = Column(
        Enum(EvalSetCategory, name='eval_set_category', values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        default=EvalSetCategory.GENERAL
    )
    
    # Questions storage (JSONL as JSON array)
    # Each item: {eval_id, question, reference_answer, difficulty, gold_chunk_ids?, ...}
    questions = Column(JSON, nullable=False, default=list)
    
    # Stats
    example_count = Column(Integer, nullable=False, default=0)
    difficulty_distribution = Column(JSON, nullable=True)  # {"easy": 5, "medium": 10, "hard": 5}
    
    # Tags for filtering
    tags = Column(JSON, nullable=True)  # ["citation-heavy", "multi-doc", etc.]
    
    # Built-in flag (for static sets that ship with the platform)
    is_built_in = Column(Boolean, nullable=False, default=False)
    
    # Audit
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    
    __table_args__ = (
        Index('ix_eval_sets_customer_domain', 'customer_id', 'domain'),
        Index('ix_eval_sets_type', 'set_type'),
    )
    
    def __repr__(self):
        return f"<EvalSet(name={self.name}, type={self.set_type}, count={self.example_count})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "set_type": self.set_type.value if self.set_type else None,
            "category": self.category.value if self.category else None,
            "example_count": self.example_count,
            "difficulty_distribution": self.difficulty_distribution,
            "tags": self.tags,
            "is_built_in": self.is_built_in,
            "created_by_user_id": self.created_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EvalSetUsage(BaseModel):
    """
    Tracks which eval runs used which eval sets.
    Provides audit trail and usage analytics.
    """
    __tablename__ = "eval_set_usages"
    
    eval_set_id = Column(Integer, ForeignKey("eval_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    eval_run_id = Column(Integer, ForeignKey("rag_eval_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Snapshot of set at time of use (in case set is later modified/deleted)
    example_count_at_run = Column(Integer, nullable=False)
    
    # Relationships
    eval_set = relationship("EvalSet")
    eval_run = relationship("RAGEvalRun")
    
    __table_args__ = (
        Index('ix_eval_set_usages_set_run', 'eval_set_id', 'eval_run_id'),
    )
