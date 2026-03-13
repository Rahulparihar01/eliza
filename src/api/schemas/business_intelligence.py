"""
Business Intelligence API Schemas

Pydantic schemas for the Business Intelligence Q&A system API.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from src.models.business_intelligence import QuestionStatus, AgentStatus, TelemetryEventType


# Request Schemas

class QuestionSubmitRequest(BaseModel):
    """Request to submit a new business intelligence question."""
    question: str = Field(..., description="The user's question about their business", min_length=10, max_length=5000)
    company_hr_dataset: Optional[str] = Field(None, description="Target company for HR data analysis (defaults to system setting if omitted)")
    session_id: Optional[str] = Field(None, description="Optional session ID to group related questions")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What are the top skills in our Engineering department?",
                "company_hr_dataset": "caylent",
                "session_id": "session_123",
                "metadata": {"source": "web_ui"}
            }
        }
    )


# Response Schemas

class TaskAnalysisResponse(BaseModel):
    """Task analysis information."""
    intent_type: str = Field(..., description="Type of intent identified")
    complexity: str = Field(..., description="Complexity level of the task")
    confidence_score: float = Field(..., description="Confidence in the analysis")
    entities: List[str] = Field(default_factory=list, description="Extracted entities")
    keywords: List[str] = Field(default_factory=list, description="Key terms")
    data_sources_needed: List[str] = Field(default_factory=list, description="Required data sources")


class EnrichedPromptResponse(BaseModel):
    """Enriched prompt information."""
    id: int
    prompt_id: str
    original_input: str
    enriched_prompt: str
    intent_type: Optional[str]
    complexity: Optional[str]
    confidence_score: Optional[float]
    quality_score: Optional[float]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AnalysisSessionResponse(BaseModel):
    """Analysis session information."""
    id: int
    session_id: str
    status: AgentStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    agents_executed: Optional[Dict[str, Any]]
    tools_used: Optional[Dict[str, Any]]
    data_sources_queried: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AnalysisResultResponse(BaseModel):
    """Analysis result information."""
    id: int
    result_id: str
    analysis_text: str
    executive_summary: Optional[str]
    key_findings: Optional[List[str]]
    data_sources_used: Optional[List[str]]
    hr_data_queried: Optional[Dict[str, Any]]
    documents_referenced: Optional[List[Dict[str, Any]]]
    confidence_score: Optional[float]
    recommendations: Optional[List[str]]
    visualizations: Optional[Dict[str, Any]]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class QuestionResponse(BaseModel):
    """Business intelligence question response."""
    id: int
    question_id: str
    user_id: int
    customer_id: str
    session_id: Optional[str]
    original_question: str
    status: QuestionStatus
    enriched_prompt: Optional[EnrichedPromptResponse]
    analysis_session: Optional[AnalysisSessionResponse]
    result: Optional[AnalysisResultResponse]
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="question_metadata")
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class QuestionSubmitResponse(BaseModel):
    """Response after submitting a question."""
    question_id: str = Field(..., description="Unique identifier for the question")
    status: QuestionStatus = Field(..., description="Current status of the question")
    message: str = Field(..., description="Status message")
    task_id: Optional[str] = Field(None, description="Identifier of the Celery task handling the question")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question_id": "q_abc123",
                "status": "pending",
                "message": "Question submitted successfully and is being processed"
            }
        }
    )


class TelemetryEventResponse(BaseModel):
    """Telemetry event from agent execution."""
    id: int
    telemetry_id: str
    event_type: TelemetryEventType
    agent_name: Optional[str]
    tool_name: Optional[str]
    stage_name: Optional[str]
    message: Optional[str]
    user_message: Optional[str]
    progress_percentage: Optional[float]
    data: Optional[Dict[str, Any]]
    error_details: Optional[Dict[str, Any]]
    duration_ms: Optional[int]
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)


class QuestionListResponse(BaseModel):
    """List of questions with pagination."""
    questions: List[QuestionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PromptListResponse(BaseModel):
    """List of enriched prompts."""
    prompts: List[EnrichedPromptResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class QuestionStatusResponse(BaseModel):
    """Quick status check response."""
    question_id: str
    status: QuestionStatus
    progress_percentage: Optional[float]
    current_stage: Optional[str]
    error_message: Optional[str]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question_id": "q_abc123",
                "status": "analyzing",
                "progress_percentage": 65.0,
                "current_stage": "Data Analysis",
                "error_message": None
            }
        }
    )


class HealthCheckResponse(BaseModel):
    """Health check for BI system."""
    status: str = Field(..., description="Overall system status")
    components: Dict[str, str] = Field(..., description="Status of individual components")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional component diagnostics")
    timestamp: datetime = Field(..., description="Timestamp of health check")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "components": {
                    "database": "healthy",
                    "vector_service": "healthy",
                    "crewai": "healthy"
                },
                "timestamp": "2025-10-01T10:00:00Z"
            }
        }
    )

