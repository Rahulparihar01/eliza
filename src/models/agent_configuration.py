"""Agent Configuration models for runtime agent configuration."""

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Optional, List, Dict, Any

from src.models.database import BaseModel


class AgentConfiguration(BaseModel):
    """Agent configuration for CrewAI agents with runtime resolution."""

    __tablename__ = "agent_configurations"
    __table_args__ = ({'extend_existing': True},)

    id = Column(Integer, primary_key=True, index=True)
    
    # Composite unique key (one config per agent per customer)
    customer_id = Column(String(255), nullable=False, index=True)
    flow_identifier = Column(String(255), nullable=False)  # "data_analysis_flow"
    agent_identifier = Column(String(255), nullable=False)  # "data_retrieval_agent"
    
    # Agent prompts (nullable = use code defaults)
    role = Column(Text, nullable=True)
    goal = Column(Text, nullable=True)
    backstory = Column(Text, nullable=True)
    
    # Model configuration
    model_id = Column(String(255), nullable=True)  # "gpt-4", "claude-3-opus-20240229"
    provider_config_id = Column(Integer, ForeignKey("customer_ai_providers.id"), nullable=True)
    temperature = Column(Float, default=0.7, nullable=True)
    max_tokens = Column(Integer, default=2000, nullable=True)
    
    # Tool configuration
    enabled_tools = Column(JSON, nullable=True)  # ["hr_database", "document_search"]
    tool_configs = Column(JSON, nullable=True)   # Tool-specific settings
    
    # Status
    is_enabled = Column(Boolean, default=True, nullable=False)
    
    # Audit trail
    version = Column(Integer, default=1, nullable=False)
    updated_by = Column(String(50), nullable=True)  # "ui", "code", "migration", "api"
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    provider = relationship("CustomerAIProvider", foreign_keys=[provider_config_id])
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])
    
    def __repr__(self):
        return (
            f"<AgentConfiguration(id={self.id}, customer_id='{self.customer_id}', "
            f"flow='{self.flow_identifier}', agent='{self.agent_identifier}', "
            f"model='{self.model_id}', version={self.version})>"
        )

