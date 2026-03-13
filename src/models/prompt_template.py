"""
Prompt Template Models - Centralized prompt storage and versioning.

This module provides database models for storing, versioning, and managing
prompts across different domains (FASB, Insurance, etc.) in the platform.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, JSON, Enum, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.database import BaseModel, Base


class PromptType(str, PyEnum):
    """Types of prompts in the RAG pipeline."""
    SYSTEM = "system"           # Main system prompt
    QUERY_REWRITE = "query_rewrite"  # Query transformation
    RETRIEVAL = "retrieval"     # Retrieval instructions
    SYNTHESIS = "synthesis"     # Answer synthesis
    EVALUATION = "evaluation"   # Eval criteria
    CUSTOM = "custom"           # User-defined


class PromptStatus(str, PyEnum):
    """Status of a prompt template."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    TESTING = "testing"


class PromptTemplate(BaseModel):
    """
    A prompt template for a specific domain and type.
    
    Each domain (FASB, Insurance, etc.) can have multiple prompt types
    (system, query_rewrite, etc.), and each prompt type can have multiple
    versions with one being active.
    """
    __tablename__ = "prompt_templates"
    
    # Identification
    customer_id = Column(String(100), nullable=False, index=True)
    domain = Column(String(100), nullable=False, index=True)  # e.g., "fasb", "insurance"
    prompt_type = Column(
        Enum(PromptType, name='prompt_type', values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Content
    content = Column(Text, nullable=False)  # The actual prompt text
    variables = Column(JSON, nullable=True)  # List of variables like {{context}}, {{question}}
    
    # Versioning
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=False)
    parent_version_id = Column(Integer, ForeignKey("prompt_templates.id"), nullable=True)
    
    # Status
    status = Column(
        Enum(PromptStatus, name='prompt_status', values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        default=PromptStatus.DRAFT
    )
    
    # Audit
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_modified_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # GEPA integration
    gepa_variant_id = Column(Integer, ForeignKey("gepa_candidate_variants.id", ondelete="SET NULL"), nullable=True)
    gepa_job_id = Column(Integer, ForeignKey("gepa_optimizer_jobs.id", ondelete="SET NULL"), nullable=True)
    
    # Performance metadata
    avg_quality_score = Column(Integer, nullable=True)  # 0-100
    usage_count = Column(Integer, nullable=False, default=0)
    
    # Relationships
    parent_version = relationship("PromptTemplate", remote_side="PromptTemplate.id", backref="child_versions")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    modified_by = relationship("User", foreign_keys=[last_modified_by_user_id])
    
    __table_args__ = (
        # Only one active prompt per customer+domain+type
        Index('ix_prompt_templates_active', 'customer_id', 'domain', 'prompt_type', 'is_active',
              postgresql_where=(Column('is_active') == True)),
        # Unique version per customer+domain+type
        UniqueConstraint('customer_id', 'domain', 'prompt_type', 'version', 
                        name='uq_prompt_version'),
    )
    
    def __repr__(self):
        return f"<PromptTemplate {self.domain}/{self.prompt_type} v{self.version}>"


class PromptChangeLog(Base):
    """
    Audit log for prompt changes.
    
    Tracks who changed what and when for compliance and rollback.
    """
    __tablename__ = "prompt_change_logs"
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Reference
    prompt_template_id = Column(Integer, ForeignKey("prompt_templates.id", ondelete="CASCADE"), nullable=False)
    
    # Change details
    action = Column(String(50), nullable=False)  # "created", "updated", "activated", "archived"
    previous_content = Column(Text, nullable=True)
    new_content = Column(Text, nullable=True)
    change_summary = Column(Text, nullable=True)
    
    # Who made the change
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Source of change
    source = Column(String(50), nullable=False, default="manual")  # "manual", "gepa", "import"
    source_reference = Column(String(255), nullable=True)  # e.g., GEPA job ID
    
    # Relationships
    prompt_template = relationship("PromptTemplate", backref="change_logs")
    user = relationship("User")


class DomainPromptConfig(BaseModel):
    """
    Domain-level configuration for prompt behavior.
    
    Allows customizing which prompts are used and how they're applied
    for each domain.
    """
    __tablename__ = "domain_prompt_configs"
    
    customer_id = Column(String(100), nullable=False, index=True)
    domain = Column(String(100), nullable=False, index=True)
    
    # Configuration
    display_name = Column(String(255), nullable=False)  # Human-readable name
    description = Column(Text, nullable=True)
    
    # Feature flags
    use_query_rewrite = Column(Boolean, nullable=False, default=True)
    use_custom_system_prompt = Column(Boolean, nullable=False, default=True)
    
    # Model settings (optional overrides)
    default_model = Column(String(100), nullable=True)
    temperature = Column(Integer, nullable=True)  # Stored as 0-100, divided by 100
    max_tokens = Column(Integer, nullable=True)
    
    # RAG settings
    retrieval_top_k = Column(Integer, nullable=True, default=10)
    similarity_threshold = Column(Integer, nullable=True, default=70)  # 0-100
    
    is_active = Column(Boolean, nullable=False, default=True)
    
    __table_args__ = (
        UniqueConstraint('customer_id', 'domain', name='uq_domain_config'),
    )


class DomainPromptFeedback(BaseModel):
    """
    Human/user feedback collected in prod (or other envs) about the CURRENT prompt set for a domain.

    Key design:
    - Feedback is domain-scoped (e.g. "fasb") and environment-scoped (prod/staging/dev).
    - We snapshot which prompt versions were active at the time of feedback, so future GEPA runs
      can import feedback that actually corresponds to the current deployed prompts.
    - target_components uses GEPA component names (e.g. "answer_synthesis_prompt") so it can be
      fed directly into GEPA seed_feedback.
    """
    __tablename__ = "domain_prompt_feedback"

    customer_id = Column(String(100), nullable=False, index=True)
    domain = Column(String(100), nullable=False, index=True)
    environment = Column(String(20), nullable=False, default="prod", index=True)  # prod/staging/dev

    # Feedback content
    rating_numeric = Column(Integer, nullable=False, default=-1)  # -2..+2
    comment = Column(Text, nullable=False)
    tags = Column(JSON, nullable=True)  # ["too_verbose", ...]
    improvement_suggestions = Column(Text, nullable=True)
    target_components = Column(JSON, nullable=True)  # ["answer_synthesis_prompt", ...]

    # Snapshot of active prompt versions at time of feedback
    prompt_snapshot = Column(JSON, nullable=False)  # {"system": {"id": 14, "version": 3}, ...}

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        Index("ix_domain_prompt_feedback_customer_domain_env", "customer_id", "domain", "environment"),
    )
