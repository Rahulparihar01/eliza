"""
AI Enablement Platform - Customer Models

Customer and tenant management models.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Dict, Any, Optional, List

from src.models.database import BaseModel


class Customer(BaseModel):
    """Customer model for multi-tenant support."""

    __tablename__ = "customers"
    __table_args__ = ({'extend_existing': True},)
    
    # Customer identification
    customer_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    
    # Contact information
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    
    # Status and configuration
    is_active = Column(Boolean, default=True, nullable=False)
    subscription_tier = Column(String(50), default="basic", nullable=False)
    
    # Deactivation tracking
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    deactivation_reason = Column(Text, nullable=True)
    
    # Configuration storage
    config_data = Column(JSON, nullable=True)
    branding_config = Column(JSON, nullable=True)
    
    # Limits and quotas
    max_users = Column(Integer, default=10, nullable=False)
    max_documents = Column(Integer, default=1000, nullable=False)
    max_api_calls_per_month = Column(Integer, default=10000, nullable=False)
    
    # Usage tracking
    current_users = Column(Integer, default=0, nullable=False)
    current_documents = Column(Integer, default=0, nullable=False)
    api_calls_this_month = Column(Integer, default=0, nullable=False)
    last_usage_reset = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Billing
    billing_email = Column(String(255), nullable=True)
    billing_address = Column(Text, nullable=True)
    
    # Relationships
    # Note: foreign_keys specified to disambiguate from deactivated_by FK
    users = relationship(
        "User", 
        back_populates="customer",
        foreign_keys="[User.customer_id]"
    )
    ai_providers = relationship("CustomerAIProvider", back_populates="customer")
    user_memberships = relationship("UserTenantMembership", back_populates="customer")
    deactivated_by_user = relationship(
        "User",
        foreign_keys=[deactivated_by],
        uselist=False
    )
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        if not self.config_data:
            return default
        return self.config_data.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value by key."""
        if not self.config_data:
            self.config_data = {}
        self.config_data[key] = value
    
    def get_branding(self, key: str, default: Any = None) -> Any:
        """Get branding configuration value by key."""
        if not self.branding_config:
            return default
        return self.branding_config.get(key, default)
    
    def set_branding(self, key: str, value: Any) -> None:
        """Set branding configuration value by key."""
        if not self.branding_config:
            self.branding_config = {}
        self.branding_config[key] = value
    
    def is_within_limits(self) -> Dict[str, bool]:
        """Check if customer is within usage limits."""
        return {
            "users": self.current_users < self.max_users,
            "documents": self.current_documents < self.max_documents,
            "api_calls": self.api_calls_this_month < self.max_api_calls_per_month
        }
    
    def increment_usage(self, metric: str, amount: int = 1) -> bool:
        """Increment usage counter and check limits."""
        if metric == "users":
            if self.current_users + amount > self.max_users:
                return False
            self.current_users += amount
        elif metric == "documents":
            if self.current_documents + amount > self.max_documents:
                return False
            self.current_documents += amount
        elif metric == "api_calls":
            if self.api_calls_this_month + amount > self.max_api_calls_per_month:
                return False
            self.api_calls_this_month += amount
        
        return True
    
    def reset_monthly_usage(self) -> None:
        """Reset monthly usage counters."""
        self.api_calls_this_month = 0
        self.last_usage_reset = func.now()
    
    def __repr__(self):
        return f"<Customer(id={self.id}, customer_id='{self.customer_id}', name='{self.name}')>"


class CustomerAIProvider(BaseModel):
    """Customer-specific AI provider configurations."""

    __tablename__ = "customer_ai_providers"
    __table_args__ = ({'extend_existing': True},)
    
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    provider_name = Column(String(50), nullable=False)  # openai, anthropic, groq, etc.
    name = Column(String(255), nullable=True)  # User-friendly name: "OpenAI Production Account"
    
    # Configuration
    is_enabled = Column(Boolean, default=True, nullable=False)
    api_key_encrypted = Column(Text, nullable=True)  # Encrypted API key
    config_data = Column(JSON, nullable=True)  # Provider-specific config
    
    # Platform sharing
    is_global_shared = Column(Boolean, default=False, nullable=False)  # If True, auto-available to all tenants
    
    # Adoption tracking
    is_adoption_source = Column(Boolean, default=False, nullable=False)  # If True, used for adoption metrics sync
    chatgpt_workspace_id = Column(String(100), nullable=True)  # ChatGPT Enterprise workspace UUID for Compliance API
    adoption_compliance_status = Column(String(20), nullable=True)  # 'success', 'failed', 'untested'
    adoption_compliance_last_checked = Column(DateTime(timezone=True), nullable=True)
    adoption_compliance_error = Column(Text, nullable=True)  # Error message if failed
    
    # Usage and limits
    priority = Column(Integer, default=1, nullable=False)  # Lower number = higher priority
    max_requests_per_minute = Column(Integer, default=60, nullable=False)
    max_tokens_per_request = Column(Integer, default=4000, nullable=False)
    
    # Status tracking
    is_healthy = Column(Boolean, default=True, nullable=False)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="ai_providers")
    shared_with = relationship("SharedAIProvider", back_populates="source_provider", cascade="all, delete-orphan")
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get provider configuration value by key."""
        if not self.config_data:
            return default
        return self.config_data.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """Set provider configuration value by key."""
        if not self.config_data:
            self.config_data = {}
        self.config_data[key] = value
    
    def record_error(self, error_message: str) -> None:
        """Record an error for this provider."""
        self.error_count += 1
        self.last_error = error_message
        self.is_healthy = False
    
    def mark_healthy(self) -> None:
        """Mark provider as healthy."""
        self.is_healthy = True
        self.last_health_check = func.now()
        self.error_count = 0
        self.last_error = None
    
    def __repr__(self):
        return f"<CustomerAIProvider(id={self.id}, customer_id='{self.customer_id}', provider='{self.provider_name}')>"


class SharedAIProvider(BaseModel):
    """
    Junction table for selectively sharing AI providers with specific tenants.
    
    Platform admins can share their AI provider configs with specific tenants.
    Tenant admins can enable/disable shared providers for their tenant.
    """
    
    __tablename__ = "shared_ai_providers"
    __table_args__ = (
        {'extend_existing': True},
    )
    
    # Source provider (from platform admin's tenant)
    source_provider_id = Column(Integer, ForeignKey("customer_ai_providers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Target tenant receiving the shared provider
    target_customer_id = Column(String(100), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Who shared it and when
    shared_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    shared_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Tenant admin can disable shared provider for their tenant
    is_enabled = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    source_provider = relationship("CustomerAIProvider", back_populates="shared_with")
    target_customer = relationship("Customer")
    shared_by_user = relationship("User")
    
    def __repr__(self):
        return f"<SharedAIProvider(source={self.source_provider_id}, target='{self.target_customer_id}', enabled={self.is_enabled})>"
