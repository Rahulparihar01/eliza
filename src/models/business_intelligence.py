"""
Business Intelligence Models

SQLAlchemy models for the Business Intelligence Q&A system.
Supports task enrichment, data retrieval, analysis, and telemetry tracking.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, JSON,
    ForeignKey, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from src.models.database import Base


class QuestionStatus(str, enum.Enum):
    """Status of a business intelligence question."""
    PENDING = "pending"
    ENRICHING = "enriching"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStatus(str, enum.Enum):
    """Status of an agent execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TelemetryEventType(str, enum.Enum):
    """Types of telemetry events."""
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    PROGRESS_UPDATE = "progress_update"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class BIQuestion(Base):
    """
    Business Intelligence Question model.
    
    Represents a user's question about their business that will be
    processed through task enrichment and data analysis flows.
    """
    __tablename__ = "bi_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # User's organization
    company_hr_dataset = Column(String(100), nullable=True, index=True)  # Target company for HR data analysis
    session_id = Column(String(100), nullable=True, index=True)
    original_question = Column(Text, nullable=False)
    status = Column(SQLEnum(
        QuestionStatus,
        name="question_status",
        native_enum=False,
        values_callable=lambda obj: [member.value for member in obj],
        create_constraint=True,
    ), nullable=False, default=QuestionStatus.PENDING, index=True)
    enriched_prompt_id = Column(Integer, ForeignKey("bi_enriched_prompts.id"), nullable=True)
    analysis_session_id = Column(Integer, ForeignKey("bi_analysis_sessions.id"), nullable=True)
    result_id = Column(Integer, ForeignKey("bi_analysis_results.id"), nullable=True)
    error_message = Column(Text, nullable=True)
    question_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="bi_questions")
    enriched_prompt = relationship("BIEnrichedPrompt", foreign_keys="BIEnrichedPrompt.question_id", back_populates="question", uselist=False)
    analysis_session = relationship("BIAnalysisSession", foreign_keys="BIAnalysisSession.question_id", back_populates="question", uselist=False)
    result = relationship("BIAnalysisResult", foreign_keys="BIAnalysisResult.question_id", back_populates="question", uselist=False)
    
    def __repr__(self):
        return f"<BIQuestion(id={self.id}, question_id={self.question_id}, status={self.status})>"


class BIEnrichedPrompt(Base):
    """
    Enriched Prompt model.
    
    Stores the output from the Task Enrichment Flow, which transforms
    the user's original question into an optimized prompt for the
    data analysis agents.
    """
    __tablename__ = "bi_enriched_prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(String(100), unique=True, nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("bi_questions.id"), nullable=False, index=True)
    original_input = Column(Text, nullable=False)
    enriched_prompt = Column(Text, nullable=False)
    intent_type = Column(String(100), nullable=True, index=True)
    complexity = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)
    processing_instructions = Column(JSON, nullable=True)
    expected_output_format = Column(JSON, nullable=True)
    validation_criteria = Column(JSON, nullable=True)
    quality_score = Column(Float, nullable=True)
    user_context = Column(JSON, nullable=True)
    rag_context = Column(JSON, nullable=True)
    enrichment_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    question = relationship("BIQuestion", foreign_keys=[question_id], back_populates="enriched_prompt")
    analysis_sessions = relationship("BIAnalysisSession", back_populates="enriched_prompt")
    agent_responses = relationship("BIAgentResponse", back_populates="enriched_prompt")
    
    def __repr__(self):
        return f"<BIEnrichedPrompt(id={self.id}, prompt_id={self.prompt_id}, intent={self.intent_type})>"


class BIAnalysisSession(Base):
    """
    Analysis Session model.
    
    Tracks the execution of the Data Retrieval & Analysis Flow,
    including which agents were executed and which tools were used.
    """
    __tablename__ = "bi_analysis_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("bi_questions.id"), nullable=False, index=True)
    enriched_prompt_id = Column(Integer, ForeignKey("bi_enriched_prompts.id"), nullable=False)
    status = Column(SQLEnum(
        AgentStatus,
        name="agent_status",
        native_enum=False,
        values_callable=lambda obj: [member.value for member in obj],
        create_constraint=True,
    ), nullable=False, default=AgentStatus.PENDING, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    agents_executed = Column(JSON, nullable=True)
    tools_used = Column(JSON, nullable=True)
    data_sources_queried = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    session_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    question = relationship("BIQuestion", foreign_keys=[question_id], back_populates="analysis_session")
    enriched_prompt = relationship("BIEnrichedPrompt", foreign_keys=[enriched_prompt_id], back_populates="analysis_sessions")
    telemetry_events = relationship("BIAgentTelemetry", back_populates="session", cascade="all, delete-orphan")
    tool_executions = relationship("BIToolExecution", back_populates="session", cascade="all, delete-orphan")
    agent_responses = relationship("BIAgentResponse", back_populates="session", cascade="all, delete-orphan")
    results = relationship("BIAnalysisResult", back_populates="session")
    
    def __repr__(self):
        return f"<BIAnalysisSession(id={self.id}, session_id={self.session_id}, status={self.status})>"


class BIAgentTelemetry(Base):
    """
    Agent Telemetry model.
    
    Captures real-time telemetry events from CrewAI agents during execution.
    Used for streaming progress updates to the frontend.
    """
    __tablename__ = "bi_agent_telemetry"
    
    id = Column(Integer, primary_key=True, index=True)
    telemetry_id = Column(String(100), unique=True, nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("bi_analysis_sessions.id"), nullable=False, index=True)
    event_type = Column(SQLEnum(
        TelemetryEventType,
        name="telemetry_event_type",
        native_enum=False,
        values_callable=lambda obj: [member.value for member in obj],
        create_constraint=True,
    ), nullable=False, index=True)
    agent_name = Column(String(255), nullable=True)
    tool_name = Column(String(255), nullable=True)
    stage_name = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)
    user_message = Column(Text, nullable=True)
    progress_percentage = Column(Float, nullable=True)
    data = Column(JSON, nullable=True)
    error_details = Column(JSON, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    session = relationship("BIAnalysisSession", back_populates="telemetry_events")
    
    def __repr__(self):
        return f"<BIAgentTelemetry(id={self.id}, event_type={self.event_type}, agent={self.agent_name})>"


class BIToolExecution(Base):
    """
    Tool Execution model.
    
    Captures detailed information about each tool call made by agents,
    including inputs, outputs, and execution metrics.
    """
    __tablename__ = "bi_tool_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(String(100), unique=True, nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("bi_analysis_sessions.id"), nullable=False, index=True)
    agent_name = Column(String(255), nullable=True)
    tool_name = Column(String(255), nullable=False, index=True)
    tool_input = Column(JSON, nullable=True)  # Input parameters passed to tool
    tool_output = Column(JSON, nullable=True)  # Results returned by tool
    status = Column(String(50), nullable=False)  # success, failed, timeout
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    results_count = Column(Integer, nullable=True)  # Number of results returned
    execution_metadata = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    session = relationship("BIAnalysisSession", back_populates="tool_executions")
    
    def __repr__(self):
        return f"<BIToolExecution(id={self.id}, tool={self.tool_name}, status={self.status})>"


class BIAgentResponse(Base):
    """
    Agent Response model.
    
    Captures agent reasoning, responses, and outputs at each stage of processing.
    Links together the agent's thought process with the tools it called.
    """
    __tablename__ = "bi_agent_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(String(100), unique=True, nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("bi_analysis_sessions.id"), nullable=False, index=True)
    enriched_prompt_id = Column(Integer, ForeignKey("bi_enriched_prompts.id"), nullable=True)
    agent_name = Column(String(255), nullable=False, index=True)
    stage_name = Column(String(255), nullable=True, index=True)  # enrichment, retrieval, analysis
    input_prompt = Column(Text, nullable=True)  # Prompt given to agent
    response_text = Column(Text, nullable=False)  # Agent's response
    reasoning = Column(Text, nullable=True)  # Agent's reasoning process
    tool_calls = Column(JSON, nullable=True)  # List of tools called during this response
    confidence_score = Column(Float, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    response_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    session = relationship("BIAnalysisSession", back_populates="agent_responses")
    enriched_prompt = relationship("BIEnrichedPrompt", back_populates="agent_responses")
    
    def __repr__(self):
        return f"<BIAgentResponse(id={self.id}, agent={self.agent_name}, stage={self.stage_name})>"


class BIAnalysisResult(Base):
    """
    Analysis Result model.
    
    Stores the final output from the Data Analysis Agent,
    including the analysis text, key findings, and recommendations.
    """
    __tablename__ = "bi_analysis_results"
    
    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(String(100), unique=True, nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("bi_questions.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("bi_analysis_sessions.id"), nullable=False, index=True)
    analysis_text = Column(Text, nullable=False)
    executive_summary = Column(Text, nullable=True)
    key_findings = Column(JSON, nullable=True)
    data_sources_used = Column(JSON, nullable=True)
    hr_data_queried = Column(JSON, nullable=True)
    documents_referenced = Column(JSON, nullable=True)
    confidence_score = Column(Float, nullable=True)
    recommendations = Column(JSON, nullable=True)
    visualizations = Column(JSON, nullable=True)
    result_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    question = relationship("BIQuestion", foreign_keys=[question_id], back_populates="result")
    session = relationship("BIAnalysisSession", foreign_keys=[session_id], back_populates="results")
    
    def __repr__(self):
        return f"<BIAnalysisResult(id={self.id}, result_id={self.result_id})>"


# Add relationship to User model (will be imported in models/__init__.py)
def add_bi_relationships():
    """Add BI relationships to existing models."""
    from src.models.auth import User
    User.bi_questions = relationship("BIQuestion", back_populates="user")

