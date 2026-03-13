"""
AI Enablement Platform - Adoption Dashboard Models

Models for tracking ChatGPT Enterprise and LLM adoption metrics across tenants.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, 
    Text, BigInteger, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Dict, Any, Optional, List
from datetime import date, datetime

from src.models.database import BaseModel


class AdoptionDataShare(BaseModel):
    """
    Allows a tenant to share their adoption metrics with another tenant.
    
    This enables the "tenant self-service share" pattern where a portfolio company
    (e.g., Acme) can opt-in to share their adoption data with a holding company
    (e.g., Blackstone).
    
    Access can also be granted via permissions (adoption:read:company:X) by platform admins,
    which doesn't require a record in this table.
    """
    
    __tablename__ = "adoption_data_shares"
    __table_args__ = (
        UniqueConstraint('source_customer_id', 'target_customer_id', name='uq_adoption_share'),
        {'extend_existing': True},
    )
    
    # WHO is sharing (the data owner)
    source_customer_id = Column(
        String(100), 
        ForeignKey("customers.customer_id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # WHO can view the data
    target_customer_id = Column(
        String(100), 
        ForeignKey("customers.customer_id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Configuration
    is_enabled = Column(Boolean, default=True, nullable=False)
    share_level = Column(String(20), default="read", nullable=False)  # "read" or "admin"
    
    # Audit
    shared_by_user_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )
    shared_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    source_customer = relationship(
        "Customer", 
        foreign_keys=[source_customer_id],
        backref="adoption_shares_outbound"
    )
    target_customer = relationship(
        "Customer", 
        foreign_keys=[target_customer_id],
        backref="adoption_shares_inbound"
    )
    shared_by_user = relationship("User")
    
    def is_active(self) -> bool:
        """Check if this share is currently active."""
        if not self.is_enabled:
            return False
        if self.expires_at and self.expires_at < datetime.now(self.expires_at.tzinfo):
            return False
        return True
    
    def grants_admin(self) -> bool:
        """Check if this share grants admin access (not just read)."""
        return self.share_level == "admin" and self.is_active()
    
    def __repr__(self):
        return (
            f"<AdoptionDataShare(source='{self.source_customer_id}', "
            f"target='{self.target_customer_id}', level='{self.share_level}', "
            f"enabled={self.is_enabled})>"
        )


class AdoptionSyncConfig(BaseModel):
    """
    Per-tenant adoption sync configuration.

    Stores first-time sync setup choices and scheduler config values used by
    tenant-scoped adoption sync execution.
    """

    __tablename__ = "adoption_sync_configs"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_adoption_sync_configs_customer"),
        {"extend_existing": True},
    )

    customer_id = Column(
        String(100),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Initial backfill anchor chosen in Adoption Settings.
    initial_sync_start_date = Column(Date, nullable=False, index=True)

    # Scheduler settings owned by Adoption Settings page.
    schedule_enabled = Column(Boolean, default=False, nullable=False)
    schedule_cron = Column(String(100), nullable=True)

    customer = relationship("Customer", backref="adoption_sync_config")

    def __repr__(self):
        return (
            f"<AdoptionSyncConfig(customer='{self.customer_id}', "
            f"start_date={self.initial_sync_start_date}, enabled={self.schedule_enabled})>"
        )


class AdoptionDailyMetrics(BaseModel):
    """
    Aggregated daily adoption metrics per company.
    
    NO message content is stored - only counts and aggregates.
    
    This table stores metrics from various sources:
    - openai_compliance: ChatGPT Enterprise metrics via OpenAI Compliance API
    - eliza_platform: Internal Eliza Platform usage metrics
    - google_gemini_compliance: Google Gemini metrics (future)
    - anthropic_compliance: Anthropic Claude metrics (future)
    """
    
    __tablename__ = "adoption_daily_metrics"
    __table_args__ = (
        UniqueConstraint('customer_id', 'source_type', 'metric_date', name='uq_adoption_metrics'),
        {'extend_existing': True},
    )
    
    # Identifiers
    customer_id = Column(
        String(100), 
        ForeignKey("customers.customer_id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    source_type = Column(String(50), nullable=False, index=True)  # openai_compliance, eliza_platform
    metric_date = Column(Date, nullable=False, index=True)
    
    # Core metrics
    active_users = Column(Integer, default=0, nullable=False)
    total_messages = Column(Integer, default=0, nullable=False)
    total_conversations = Column(Integer, default=0, nullable=False)
    total_images = Column(Integer, default=0, nullable=False)
    
    # GPT adoption metrics
    gpt_conversations = Column(Integer, default=0, nullable=False)  # Conversations using custom GPTs
    base_conversations = Column(Integer, default=0, nullable=False)  # Conversations using base ChatGPT
    unique_gpts = Column(Integer, default=0, nullable=False)  # Count of unique GPTs used
    
    # Token usage (not available from Compliance API, kept for future use)
    input_tokens = Column(BigInteger, default=0, nullable=False)
    output_tokens = Column(BigInteger, default=0, nullable=False)
    
    # Breakdowns (JSONB for flexibility)
    model_breakdown = Column(JSON, nullable=True)   # {"gpt-4": 1000, "gpt-4o": 500}
    top_gpts = Column(JSON, nullable=True)          # [{"name": "...", "uses": 100}]
    user_distribution = Column(JSON, nullable=True) # {"power": 10, "regular": 50, "light": 100}
    
    # Sync metadata
    sync_metadata = Column(JSON, nullable=True)     # {"last_sync_id": "...", "records_processed": 100}
    sync_run_id = Column(String(36), nullable=True, index=True)  # UUID string for run provenance
    
    # Relationships
    customer = relationship("Customer", backref="adoption_metrics")
    
    @property
    def total_tokens(self) -> int:
        """Calculate total tokens (input + output)."""
        return (self.input_tokens or 0) + (self.output_tokens or 0)
    
    def get_model_usage(self, model_name: str) -> int:
        """Get usage count for a specific model."""
        if not self.model_breakdown:
            return 0
        return self.model_breakdown.get(model_name, 0)
    
    def get_top_gpt_names(self, limit: int = 5) -> List[str]:
        """Get names of top GPTs by usage."""
        if not self.top_gpts:
            return []
        sorted_gpts = sorted(self.top_gpts, key=lambda x: x.get('uses', 0), reverse=True)
        return [gpt.get('name', 'Unknown') for gpt in sorted_gpts[:limit]]
    
    def __repr__(self):
        return (
            f"<AdoptionDailyMetrics(customer='{self.customer_id}', "
            f"source='{self.source_type}', date={self.metric_date}, "
            f"users={self.active_users}, messages={self.total_messages})>"
        )


# =============================================================================
# Source Type Constants
# =============================================================================

class AdoptionSourceType:
    """Constants for adoption data source types."""
    
    OPENAI_COMPLIANCE = "openai_compliance"
    ELIZA_PLATFORM = "eliza_platform"
    GOOGLE_GEMINI_COMPLIANCE = "google_gemini_compliance"
    ANTHROPIC_COMPLIANCE = "anthropic_compliance"
    MICROSOFT_COPILOT = "microsoft_copilot"
    
    @classmethod
    def all_types(cls) -> List[str]:
        """Return all valid source types."""
        return [
            cls.OPENAI_COMPLIANCE,
            cls.ELIZA_PLATFORM,
            cls.GOOGLE_GEMINI_COMPLIANCE,
            cls.ANTHROPIC_COMPLIANCE,
            cls.MICROSOFT_COPILOT,
        ]
    
    @classmethod
    def is_valid(cls, source_type: str) -> bool:
        """Check if a source type is valid."""
        return source_type in cls.all_types()


# =============================================================================
# Share Level Constants
# =============================================================================

class AdoptionShareLevel:
    """Constants for adoption share levels."""
    
    READ = "read"   # Can view metrics only
    ADMIN = "admin" # Can view metrics AND configure data sources
    
    @classmethod
    def all_levels(cls) -> List[str]:
        """Return all valid share levels."""
        return [cls.READ, cls.ADMIN]
    
    @classmethod
    def is_valid(cls, level: str) -> bool:
        """Check if a share level is valid."""
        return level in cls.all_levels()


# =============================================================================
# Granular Data Tables (for rich analytics and user-GPT tracking)
# =============================================================================

class AdoptionGPT(BaseModel):
    """
    GPT metadata synced from ChatGPT Enterprise.
    
    Stores information about custom GPTs in the organization for display
    and linking to user interactions.
    """
    
    __tablename__ = "adoption_gpts"
    __table_args__ = (
        UniqueConstraint('customer_id', 'external_gpt_id', name='uq_adoption_gpt'),
        {'extend_existing': True},
    )
    
    # Tenant ownership
    customer_id = Column(
        String(100), 
        ForeignKey("customers.customer_id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # GPT identifiers (from OpenAI)
    external_gpt_id = Column(String(100), nullable=False, index=True)  # g-xxx from OpenAI
    short_url = Column(String(255), nullable=True)  # chatgpt.com/g/xxx
    
    # GPT metadata
    name = Column(String(500), nullable=True)  # Display name (can be null for unnamed GPTs)
    description = Column(Text, nullable=True)
    
    # Creator info
    creator_user_id = Column(String(100), nullable=True, index=True)  # OpenAI user ID
    creator_email = Column(String(255), nullable=True, index=True)
    creator_name = Column(String(255), nullable=True)
    
    # Visibility and status
    visibility = Column(String(50), nullable=True)  # "workspace", "invite-only", "workspace-with-link"
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps from OpenAI
    external_created_at = Column(DateTime(timezone=True), nullable=True)
    external_updated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Sync tracking
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    customer = relationship("Customer", backref="adoption_gpts")
    
    def __repr__(self):
        return (
            f"<AdoptionGPT(id={self.id}, customer='{self.customer_id}', "
            f"gpt_id='{self.external_gpt_id}', name='{self.name}')>"
        )


class AdoptionConversation(BaseModel):
    """
    Individual conversation records from ChatGPT Enterprise.
    
    NO message content is stored - only metadata for analytics.
    This enables user-GPT interaction tracking.
    """
    
    __tablename__ = "adoption_conversations"
    __table_args__ = (
        UniqueConstraint('customer_id', 'external_conversation_id', name='uq_adoption_conversation'),
        {'extend_existing': True},
    )
    
    # Tenant ownership
    customer_id = Column(
        String(100), 
        ForeignKey("customers.customer_id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Conversation identifiers (from OpenAI)
    external_conversation_id = Column(String(100), nullable=False, index=True)
    
    # User info
    user_external_id = Column(String(100), nullable=True, index=True)  # OpenAI user ID
    user_email = Column(String(255), nullable=True, index=True)
    
    # GPT used (nullable - not all conversations use a GPT)
    gpt_id = Column(
        Integer,
        ForeignKey("adoption_gpts.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    external_gpt_id = Column(String(100), nullable=True, index=True)  # For linking before GPT is synced
    
    # Conversation metrics (no content!)
    message_count = Column(Integer, default=0, nullable=False)  # Total messages
    user_message_count = Column(Integer, default=0, nullable=False)  # User messages only
    
    # Timestamps
    conversation_created_at = Column(DateTime(timezone=True), nullable=True, index=True)
    conversation_updated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Sync tracking
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now())
    sync_run_id = Column(String(36), nullable=True, index=True)  # UUID string for run provenance
    
    # Relationships
    customer = relationship("Customer", backref="adoption_conversations")
    gpt = relationship("AdoptionGPT", backref="conversations")
    
    def __repr__(self):
        return (
            f"<AdoptionConversation(id={self.id}, customer='{self.customer_id}', "
            f"user='{self.user_email}', gpt_id={self.gpt_id}, messages={self.message_count})>"
        )


class AdoptionUserGPTInteraction(BaseModel):
    """
    Aggregated user-GPT interaction summary.
    
    Tracks which users have interacted with which GPTs, enabling:
    - User outreach for feedback
    - Power user identification per GPT
    - Adoption tracking per user per GPT
    """
    
    __tablename__ = "adoption_user_gpt_interactions"
    __table_args__ = (
        UniqueConstraint('customer_id', 'user_external_id', 'gpt_id', name='uq_user_gpt_interaction'),
        {'extend_existing': True},
    )
    
    # Tenant ownership
    customer_id = Column(
        String(100), 
        ForeignKey("customers.customer_id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # User info
    user_external_id = Column(String(100), nullable=False, index=True)  # OpenAI user ID
    user_email = Column(String(255), nullable=True, index=True)
    
    # GPT reference
    gpt_id = Column(
        Integer,
        ForeignKey("adoption_gpts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Interaction metrics
    total_conversations = Column(Integer, default=0, nullable=False)
    total_messages = Column(Integer, default=0, nullable=False)  # User messages only
    
    # Timestamps
    first_interaction_at = Column(DateTime(timezone=True), nullable=True)
    last_interaction_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    customer = relationship("Customer", backref="adoption_user_gpt_interactions")
    gpt = relationship("AdoptionGPT", backref="user_interactions")
    
    def __repr__(self):
        return (
            f"<AdoptionUserGPTInteraction(user='{self.user_email}', "
            f"gpt_id={self.gpt_id}, convos={self.total_conversations})>"
        )

