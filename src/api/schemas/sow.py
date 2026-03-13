"""
SOW (Statement of Work) API Schemas

Pydantic models for SOW extraction and generation API endpoints.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# --- Request Models ---

class SowExtractRequest(BaseModel):
    """Request to extract SOW fields from a transcript."""
    # Transcript is uploaded as a file, not in the body
    pass


class SowUpdateFieldRequest(BaseModel):
    """Request to update a single field value."""
    session_id: str = Field(..., description="Session ID from extraction")
    tag: str = Field(..., description="Field tag to update")
    value: str = Field(..., description="New value for the field")
    status: str = Field(..., description="Field status: confirmed, edited, rejected")


class SowGenerateRequest(BaseModel):
    """Request to generate the final SOW document."""
    session_id: str = Field(..., description="Session ID from extraction")


class SowDialogueRequest(BaseModel):
    """Request for interactive dialogue about a field."""
    session_id: str = Field(..., description="Session ID")
    tag: str = Field(..., description="Field tag to discuss")
    message: str = Field(..., description="User's message")
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Previous conversation messages"
    )


# --- Response Models ---

class SowFieldResponse(BaseModel):
    """A field definition from the template."""
    tag: str = Field(..., description="Field identifier")
    question: str = Field(..., description="Extraction question/instruction")
    source: str = Field(..., description="Source of the field definition")


class SowAnswerResponse(BaseModel):
    """An extracted answer for a field."""
    tag: str = Field(..., description="Field identifier")
    value: Optional[Any] = Field(None, description="Raw extracted value")
    value_rendered: Optional[str] = Field(None, description="Rendered display value")
    confidence: float = Field(..., description="Confidence score 0.0-1.0")
    reasoning: Optional[str] = Field(None, description="Extraction reasoning")
    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Source citations from transcript"
    )
    followup_question: Optional[str] = Field(
        None, 
        description="Suggested follow-up question if clarification needed"
    )
    needs_review: bool = Field(
        False, 
        description="True if confidence is low and user should review"
    )
    status: str = Field("pending", description="Field status: pending, confirmed, rejected, edited")


class SowExtractionResponse(BaseModel):
    """Response from SOW extraction."""
    session_id: str = Field(..., description="Unique session identifier")
    fields: List[SowFieldResponse] = Field(..., description="Template fields")
    answers: List[SowAnswerResponse] = Field(..., description="Extracted answers")
    meeting_title: Optional[str] = Field(None, description="Meeting title from transcript")
    meeting_date: Optional[str] = Field(None, description="Meeting date from transcript")


class SowUpdateFieldResponse(BaseModel):
    """Response from field update."""
    success: bool = Field(..., description="Whether the update succeeded")
    tag: str = Field(..., description="Updated field tag")
    new_value: str = Field(..., description="New field value")
    status: str = Field(..., description="New field status")


class SowGenerateResponse(BaseModel):
    """Response from document generation."""
    output_path: str = Field(..., description="Path to generated document")
    download_url: str = Field(..., description="URL to download the document")


class SowDialogueResponse(BaseModel):
    """Response from interactive dialogue."""
    response: str = Field(..., description="AI response to user message")
    suggested_answer: Optional[str] = Field(
        None, 
        description="Suggested answer if the AI has one"
    )


class SowAlternativeAnswer(BaseModel):
    """An alternative interpretation for a field."""
    answer: str = Field(..., description="Alternative answer")
    confidence: float = Field(..., description="Confidence score")
    reasoning: str = Field(..., description="Reasoning for this interpretation")


class SowAlternativesResponse(BaseModel):
    """Response with alternative interpretations."""
    alternatives: List[SowAlternativeAnswer] = Field(
        ..., 
        description="List of alternative answers"
    )


class SowSessionResponse(BaseModel):
    """Response with session state."""
    session_id: str
    meeting_title: Optional[str] = None
    meeting_date: Optional[str] = None
    field_status: Dict[str, str] = Field(default_factory=dict)
    answers: List[SowAnswerResponse] = Field(default_factory=list)


class SowTemplateListResponse(BaseModel):
    """Response with available templates."""
    templates: List[Dict[str, str]] = Field(
        ..., 
        description="List of available templates"
    )
