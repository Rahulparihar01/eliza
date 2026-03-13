"""
Data Analyst Agent Database Models
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, Enum as SQLEnum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel as PydanticBaseModel
import enum

from src.models.database import BaseModel, Base

class DataSourceType(str, Enum):
    """Supported data source types."""
    INSURANCE = "insurance"
    FASB = "fasb"  # FASB Accounting Standards Codification RAG
    KNOWLEDGE_BASE = "knowledge_base"  # RAGFlow-powered custom knowledge domains
    # Future: FINANCE = "finance", RETAIL = "retail", etc.

class ConversationType(str, Enum):
    """Conversation type."""
    USER = "user"
    GROUP = "group"

class ConversationStatus(str, Enum):
    """Conversation status."""
    ACTIVE = "active"
    DELETED = "deleted"

class MessageType(str, Enum):
    """Message type."""
    DATA = "data"  # Requires SQL generation
    CONVERSATIONAL = "conversational"  # General question, no SQL

class DataAnalystQuestionStatus(str, Enum):
    """Question processing status."""
    PENDING = "pending"
    CLARIFICATION_NEEDED = "clarification_needed"  # Waiting for user clarification
    INTENT_CONFIRMED = "intent_confirmed"  # User confirmed intent, ready to process
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DataAnalystTelemetryEventType(str, enum.Enum):
    """Types of telemetry events for data analyst flow."""
    FLOW_STARTED = "flow_started"
    FLOW_COMPLETED = "flow_completed"
    FLOW_FAILED = "flow_failed"
    INTENT_DETECTION_STARTED = "intent_detection_started"
    INTENT_DETECTION_COMPLETED = "intent_detection_completed"
    CLARIFICATION_STARTED = "clarification_started"
    CLARIFICATION_COMPLETED = "clarification_completed"
    CONFIRMATION_STARTED = "confirmation_started"
    CONFIRMATION_COMPLETED = "confirmation_completed"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    SQL_GENERATION_STARTED = "sql_generation_started"
    SQL_GENERATION_COMPLETED = "sql_generation_completed"
    SQL_EXECUTION_STARTED = "sql_execution_started"
    SQL_EXECUTION_COMPLETED = "sql_execution_completed"
    INSIGHTS_GENERATION_STARTED = "insights_generation_started"
    INSIGHTS_GENERATION_COMPLETED = "insights_generation_completed"
    PROGRESS_UPDATE = "progress_update"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class ParticipantRole(str, Enum):
    """Participant role in group conversations."""
    OWNER = "owner"
    PARTICIPANT = "participant"

# Pydantic schema for participant validation
class ConversationParticipant(PydanticBaseModel):
    """Participant schema for JSON storage."""
    user_id: int
    role: ParticipantRole = ParticipantRole.PARTICIPANT
    joined_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class DataAnalystConversation(BaseModel):
    """
    Data Analyst conversation record.
    
    Groups multiple messages/questions together for context-aware conversations.
    Supports both user-specific and group conversations.
    """
    __tablename__ = "data_analyst_conversations"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # Creator/owner
    customer_id = Column(String(100), nullable=False, index=True)
    data_source_type = Column(SQLEnum(DataSourceType), nullable=False)
    
    # Conversation type and sharing
    conversation_type = Column(String(50), nullable=False, default=ConversationType.USER.value)
    is_shared = Column(Boolean, nullable=False, default=False)
    
    # Participants (JSON array: [{user_id: int, role: str, joined_at: timestamp}])
    # Stored as JSONB in database, accessed as list of dicts in Python
    participants = Column(JSON, nullable=False, default=[])  # Stored as JSON array
    
    # Metadata
    title = Column(String(255), nullable=True)  # Auto-generated, user can rename
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=ConversationStatus.ACTIVE.value)
    
    # Context for LLM/Vanna (stores last 10 messages summary)
    conversation_context = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_activity_at = Column(DateTime, nullable=True)
    
    # Relationships
    messages = relationship("DataAnalystMessage", back_populates="conversation", lazy="select", order_by="DataAnalystMessage.message_order")

class DataAnalystMessage(BaseModel):
    """
    Data Analyst message record (renamed from Question).
    
    Tracks user messages/questions, which can be either:
    - DATA messages: Require SQL generation and data retrieval
    - CONVERSATIONAL messages: General questions, SOPs, documentation (no SQL)
    
    Messages belong to conversations for context-aware processing.
    """
    __tablename__ = "data_analyst_messages"  # Table renamed from data_analyst_questions
    
    id = Column(Integer, primary_key=True)
    question_id = Column(String(100), unique=True, nullable=False, index=True)  # Keep for backward compat
    user_id = Column(Integer, nullable=False, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    
    # Question details
    data_source_type = Column(SQLEnum(DataSourceType), nullable=False)
    original_question = Column(Text, nullable=False)  # The user's question/message
    
    # NEW: Message tracking
    message_id = Column(String(100), unique=True, nullable=True, index=True)  # New primary identifier
    conversation_id = Column(String(100), ForeignKey("data_analyst_conversations.conversation_id"), nullable=True, index=True)
    message_order = Column(Integer, nullable=True)  # Order within conversation
    message_type = Column(String(50), nullable=False, default=MessageType.DATA.value)
    parent_message_id = Column(String(100), nullable=True, index=True)  # Reference to previous message
    
    # Processing (for DATA messages only)
    # Note: Using String instead of SQLEnum because migration created it as String
    # The enum values are lowercase: "pending", "processing", "completed", "failed"
    status = Column(String(50), nullable=False, default=DataAnalystQuestionStatus.PENDING.value)
    generated_sql = Column(Text, nullable=True)  # Only for DATA messages
    sql_error = Column(Text, nullable=True)
    
    # Results (for DATA messages only)
    result_data = Column(JSON, nullable=True)  # Raw query results: {columns: [], rows: [], row_count: int}
    result_metadata = Column(JSON, nullable=True)  # Charts, insights, summaries: {sql: str, chart_suggestions: [], insights: str, summary: str}
    
    # Conversational response (for CONVERSATIONAL messages)
    conversational_response = Column(Text, nullable=True)  # LLM response for non-data questions
    
    # Intent detection and clarification
    detected_intent = Column(String(50), nullable=True)  # 'data_query', 'conversational', etc.
    intent_confidence = Column(String(50), nullable=True)  # 'high', 'medium', 'low'
    clarification_prompt = Column(Text, nullable=True)  # Question asked to user for clarification
    clarification_response = Column(Text, nullable=True)  # User's response to clarification
    clarified_question = Column(Text, nullable=True)  # Final clarified question after user response
    intent_confirmed = Column(Boolean, nullable=False, default=False)  # User confirmed intent
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    conversation = relationship("DataAnalystConversation", back_populates="messages", lazy="select")
    # Note: No relationship to telemetry - telemetry is independent observability data
    # Query telemetry separately using message_id filter when needed
    # Self-referential relationship: parent_message_id references message_id (not id)
    # Note: Since parent_message_id is a String and references message_id (also String), 
    # we need to use a primaryjoin expression. For now, we'll make this relationship optional
    # and handle parent message lookups manually in the service layer if needed.
    # parent_message = relationship("DataAnalystMessage", ...)  # Commented out due to String FK complexity

    def __repr__(self):
        return f"<DataAnalystMessage(id={self.id}, question_id={self.question_id}, status={self.status})>"


class DataAnalystTelemetry(Base):
    """
    Data Analyst Telemetry model.
    
    Captures real-time telemetry events from CrewAI flow execution.
    Used for streaming progress updates to the frontend via SSE.
    
    Note: Uses Base instead of BaseModel to avoid created_at/updated_at columns
    since we only need timestamp for events.
    """
    __tablename__ = "data_analyst_telemetry"
    
    id = Column(Integer, primary_key=True, index=True)
    telemetry_id = Column(String(100), unique=True, nullable=False, index=True)
    # Note: No FK constraint - telemetry is observability data, should be independent
    # We keep message_id as indexed string for filtering/searching
    message_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # DataAnalystTelemetryEventType as string
    agent_name = Column(String(255), nullable=True)
    tool_name = Column(String(255), nullable=True)
    stage_name = Column(String(255), nullable=True)  # "Intent Detection", "Clarification", "Confirmation", "Processing"
    message = Column(Text, nullable=True)
    user_message = Column(Text, nullable=True)  # User-friendly message
    progress_percentage = Column(Integer, nullable=True)  # 0-100
    data = Column(JSON, nullable=True)  # Arbitrary event data
    error_details = Column(JSON, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    # No relationships - telemetry is independent observability data
    # Access via direct queries using message_id filter
    
    def __repr__(self):
        return f"<DataAnalystTelemetry(id={self.id}, event_type={self.event_type}, stage={self.stage_name})>"

# Backward compatibility alias
DataAnalystQuestion = DataAnalystMessage
