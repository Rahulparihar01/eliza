"""
Data Analyst API Schemas
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.models.data_analyst import DataSourceType, DataAnalystQuestionStatus, DataAnalystTelemetryEventType


class QuestionSubmitRequest(BaseModel):
    """Request to submit a new question."""
    data_source_type: DataSourceType = Field(..., description="Data source type")
    question: str = Field(..., min_length=1, description="Natural language question")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for multi-turn conversations")


class QuestionSubmitResponse(BaseModel):
    """Response after submitting a question."""
    question_id: str
    status: str
    message: str
    conversation_id: Optional[str] = Field(None, description="Conversation ID if message was added to a conversation")


class QuestionResponse(BaseModel):
    """Full question details."""
    question_id: str
    user_id: int
    customer_id: str
    data_source_type: str
    original_question: str
    status: str
    generated_sql: Optional[str] = None
    sql_error: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    result_metadata: Optional[Dict[str, Any]] = None
    clarification_prompt: Optional[str] = Field(None, description="Clarification question from the system when status is clarification_needed")
    clarified_question: Optional[str] = Field(None, description="The clarified version of the question after user provides clarification")
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class QuestionStatusResponse(BaseModel):
    """Question status response."""
    question_id: str
    status: str
    progress_percentage: float
    error_message: Optional[str] = None


class AnalysisResultResponse(BaseModel):
    """Analysis result response."""
    question_id: str
    result_data: Dict[str, Any]
    result_metadata: Dict[str, Any]


class QuestionListItem(BaseModel):
    """Question list item."""
    question_id: str
    user_id: int
    customer_id: str
    data_source_type: str
    original_question: str
    status: str
    sql_error: Optional[str] = None
    generated_sql: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    result_metadata: Optional[Dict[str, Any]] = None
    clarification_prompt: Optional[str] = Field(None, description="Clarification question from the system when status is clarification_needed")
    clarified_question: Optional[str] = Field(None, description="The clarified version of the question after user provides clarification")
    created_at: datetime
    completed_at: Optional[datetime] = None


class QuestionListResponse(BaseModel):
    """Question list response."""
    questions: List[QuestionListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ClarificationRequest(BaseModel):
    """Request to provide clarification response."""
    clarification_response: str = Field(..., min_length=1, description="User's clarification response")


class ConfirmationRequest(BaseModel):
    """Request to confirm or correct intent."""
    confirmation_response: str = Field(..., min_length=1, description="User's confirmation (yes/no) or correction")


# ============================================================================
# Telemetry Schemas (for validation)
# ============================================================================

class TelemetryEventCreate(BaseModel):
    """
    Pydantic model for creating telemetry events.
    
    This provides type validation BEFORE data reaches SQLAlchemy/database.
    Catches type errors early and provides clear error messages.
    """
    message_id: str = Field(..., min_length=1, description="Message ID (required, non-empty)")
    event_type: DataAnalystTelemetryEventType = Field(..., description="Type of telemetry event")
    agent_name: Optional[str] = Field(None, max_length=255, description="Name of the CrewAI agent")
    tool_name: Optional[str] = Field(None, max_length=255, description="Name of the tool being used")
    stage_name: Optional[str] = Field(None, max_length=255, description="Processing stage")
    message: Optional[str] = Field(None, description="Technical message for logging")
    user_message: Optional[str] = Field(None, description="User-friendly status message")
    progress_percentage: Optional[int] = Field(None, ge=0, le=100, description="Progress (0-100)")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional event data")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if applicable")
    duration_ms: Optional[int] = Field(None, ge=0, description="Duration in milliseconds")
    
    @field_validator('message_id')
    @classmethod
    def validate_message_id(cls, v):
        """Ensure message_id is not None, empty, or the string 'None'."""
        if not v or v.strip() == "" or v == "None":
            raise ValueError("message_id cannot be None, empty, or the string 'None'")
        return v
    
    @field_validator('event_type', mode='before')
    @classmethod
    def validate_event_type(cls, v):
        """Convert string to enum if needed."""
        if isinstance(v, str):
            try:
                return DataAnalystTelemetryEventType(v)
            except ValueError:
                raise ValueError(f"Invalid event_type: {v}")
        return v
    
    class Config:
        use_enum_values = False  # Keep as enum, don't convert to string


class TelemetryEventResponse(BaseModel):
    """Response after creating a telemetry event."""
    telemetry_id: str
    message_id: str
    event_type: str
    stage_name: Optional[str]
    user_message: Optional[str]
    progress_percentage: Optional[int]
    timestamp: datetime
    
    class Config:
        from_attributes = True  # For SQLAlchemy models

