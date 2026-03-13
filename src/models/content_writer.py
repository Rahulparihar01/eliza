"""
Content Writer Models

SQLAlchemy models for the Research-First Content Writer product.
Supports research-driven content generation with POV selection, 
draft management, and personal skills/memory system.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, JSON, Boolean,
    ForeignKey, Enum as SQLEnum, Index, ARRAY
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from src.models.database import Base


class ContentFormat(str, enum.Enum):
    """Output format for content generation."""
    LINKEDIN = "linkedin"
    BLOG = "blog"
    TWITTER_ARTICLE = "twitter_article"


class SourceType(str, enum.Enum):
    """Types of research sources."""
    WEB = "web"
    REDDIT = "reddit"
    HACKER_NEWS = "hacker_news"
    TWITTER = "twitter"
    CURATED_BLOGS = "curated_blogs"
    PASTED_TEXT = "pasted_text"


class RunStatus(str, enum.Enum):
    """Status of a content writer run."""
    PENDING = "pending"
    RESEARCHING = "researching"
    POV_SELECTION = "pov_selection"
    HOOK_SELECTION = "hook_selection"
    OUTLINE_SELECTION = "outline_selection"
    DRAFTING = "drafting"
    COMPLETED = "completed"
    FAILED = "failed"


class SkillType(str, enum.Enum):
    """Types of user skills/memory."""
    VOICE = "voice"
    PILLARS = "pillars"
    HOOKS = "hooks"
    EXAMPLES = "examples"
    PROOF_BANK = "proof_bank"


class IssueType(str, enum.Enum):
    """Types of issues that can be identified in content for refinement."""
    TOO_VAGUE = "too_vague"
    CONTRADICTORY = "contradictory"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    OFF_BRAND = "off_brand"
    WEAK_HOOK = "weak_hook"
    POOR_FLOW = "poor_flow"
    TOO_TECHNICAL = "too_technical"
    TOO_GENERIC = "too_generic"
    WRONG_TONE = "wrong_tone"
    NEEDS_EVIDENCE = "needs_evidence"


class ContentWriterRun(Base):
    """
    Content Writer Run model.
    
    Represents a single content generation run from topic to final draft.
    Tracks the full workflow: research → POV selection → draft generation → refinement.
    """
    __tablename__ = "content_writer_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Input configuration
    topic = Column(Text, nullable=False)
    format = Column(SQLEnum(
        ContentFormat,
        name="content_format",
        native_enum=False,
        values_callable=lambda obj: [member.value for member in obj],
        create_constraint=True,
    ), nullable=False)
    selected_sources = Column(JSON, nullable=False)  # List of SourceType values
    pasted_text = Column(Text, nullable=True)  # If 'pasted_text' in selected_sources
    constraints = Column(JSON, nullable=True)  # {audience, tone, length, etc.}
    
    # Status tracking
    status = Column(SQLEnum(
        RunStatus,
        name="content_writer_run_status",
        native_enum=False,
        values_callable=lambda obj: [member.value for member in obj],
        create_constraint=True,
    ), nullable=False, default=RunStatus.PENDING, index=True)
    error_message = Column(Text, nullable=True)
    
    # Generated POV options (from POV Analysis Agent)
    pov_options = Column(JSON, nullable=True)  # List of POV pointers
    selected_pov = Column(JSON, nullable=True)  # Selected POV {type, thesis, key_concepts}
    
    # Generated hook options
    hook_options = Column(JSON, nullable=True)  # List of hook options
    selected_hook = Column(JSON, nullable=True)  # Selected hook {title, lede}
    
    # Generated outline options (for blog/twitter_article)
    outline_options = Column(JSON, nullable=True)  # List of outline options
    selected_outline = Column(JSON, nullable=True)  # Selected outline {sections}
    
    # Skills applied (IDs of skills used)
    applied_skill_ids = Column(ARRAY(Integer), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Celery task tracking
    task_id = Column(String(100), nullable=True, index=True)
    
    # Relationships
    user = relationship("User", back_populates="content_writer_runs")
    research_pack = relationship(
        "ResearchPack",
        back_populates="run",
        uselist=False,
        cascade="all, delete-orphan"
    )
    draft_artifacts = relationship(
        "DraftArtifact",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="DraftArtifact.version.desc()"
    )
    
    def __repr__(self):
        return f"<ContentWriterRun(id={self.id}, run_id={self.run_id}, status={self.status})>"


class ResearchPack(Base):
    """
    Research Pack model.
    
    Stores structured research data separate from the draft.
    Includes excerpts, takeaways, contested items, and user selections.
    """
    __tablename__ = "research_packs"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("content_writer_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Structured research data
    key_takeaways = Column(JSON, nullable=False, default=list)  # [{text, theme, source}]
    excerpts = Column(JSON, nullable=False, default=list)  # [{id, text, source_url, source_type, metadata}]
    contested_items = Column(JSON, nullable=True)  # [{claim, pro_evidence, con_evidence}]
    best_counterargument = Column(Text, nullable=True)
    
    # User interactions (selected evidence)
    selected_excerpt_ids = Column(ARRAY(Integer), nullable=True)  # IDs from excerpts array
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    run = relationship("ContentWriterRun", back_populates="research_pack")
    
    def __repr__(self):
        return f"<ResearchPack(id={self.id}, run_id={self.run_id}, excerpts={len(self.excerpts or [])})>"


class DraftArtifact(Base):
    """
    Draft Artifact model.
    
    Stores versioned draft content with refinement history.
    Each refinement creates a new version linked to its parent.
    """
    __tablename__ = "draft_artifacts"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("content_writer_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    
    # Draft content
    format = Column(SQLEnum(
        ContentFormat,
        name="draft_format",
        native_enum=False,
        values_callable=lambda obj: [member.value for member in obj],
        create_constraint=True,
    ), nullable=False)
    content = Column(Text, nullable=False)
    
    # Metadata
    word_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # Version tracking
    parent_version_id = Column(Integer, ForeignKey("draft_artifacts.id"), nullable=True)
    refinement_type = Column(String(50), nullable=True)  # 'full_generation', 'surgical_edit', 'section_critique'
    refinement_instruction = Column(Text, nullable=True)  # User's instruction for this version
    
    # Timestamps
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    run = relationship("ContentWriterRun", back_populates="draft_artifacts")
    parent_version = relationship("DraftArtifact", remote_side=[id], backref="child_versions")
    
    # Composite index for version lookup
    __table_args__ = (
        Index('idx_draft_artifacts_run_version', 'run_id', 'version'),
    )
    
    def __repr__(self):
        return f"<DraftArtifact(id={self.id}, run_id={self.run_id}, version={self.version})>"


class ContentWriterSkill(Base):
    """
    Content Writer Skill model.
    
    Personal skills/memory that users can create, edit, and reuse.
    Skills are applied automatically based on relevance to the request.
    """
    __tablename__ = "content_writer_skills"
    
    id = Column(Integer, primary_key=True, index=True)
    skill_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Skill type and content
    skill_type = Column(SQLEnum(
        SkillType,
        name="skill_type",
        native_enum=False,
        values_callable=lambda obj: [member.value for member in obj],
        create_constraint=True,
    ), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    content = Column(JSON, nullable=False)  # Flexible structure per skill type
    
    # Usage tracking
    is_default = Column(Boolean, default=False)  # Auto-apply if relevant
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="content_writer_skills")
    
    # Composite index for user lookup
    __table_args__ = (
        Index('idx_content_writer_skills_user', 'user_id', 'customer_id'),
        Index('idx_content_writer_skills_type', 'skill_type'),
    )
    
    def __repr__(self):
        return f"<ContentWriterSkill(id={self.id}, skill_id={self.skill_id}, type={self.skill_type})>"


def add_content_writer_relationships():
    """Add Content Writer relationships to User model."""
    from src.models.auth import User
    
    # Add relationships if not already defined
    if not hasattr(User, 'content_writer_runs'):
        User.content_writer_runs = relationship(
            "ContentWriterRun",
            back_populates="user",
            lazy="dynamic"
        )
    
    if not hasattr(User, 'content_writer_skills'):
        User.content_writer_skills = relationship(
            "ContentWriterSkill",
            back_populates="user",
            lazy="dynamic"
        )
