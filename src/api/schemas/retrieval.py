"""
Pydantic schemas for the Retrieval API (HubSpot CRM search v0).
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class RetrievalSearchRequest(BaseModel):
    """Request body for POST /api/retrieval/search."""
    query: str = Field(..., min_length=1, max_length=2000, description="Natural-language search query")
    workspace_id: int = Field(..., description="Agent Mesh workspace ID to execute against")
    conversation_id: Optional[str] = Field(None, description="Conversation to append this search to")


class RetrievalSearchResponse(BaseModel):
    """Returned immediately (202) after enqueuing a retrieval run."""
    run_id: str
    status: str
    workspace_id: int
    conversation_id: Optional[str] = None


class RetrievalRunResponse(BaseModel):
    """Returned by GET /api/retrieval/runs/{run_id}."""
    run_id: str
    status: str
    query: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    sources: Optional[List[str]] = None
    follow_ups: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    auth_required: Optional[Dict[str, Any]] = None


class ConversationMessageResponse(BaseModel):
    """A single message in a conversation."""
    id: int
    role: str
    content: str
    sources: Optional[List[str]] = None
    follow_ups: Optional[List[str]] = None
    run_id: Optional[str] = None
    created_at: Optional[datetime] = None


class ConversationResponse(BaseModel):
    """Summary of a conversation (for list view)."""
    id: str
    workspace_id: Optional[int] = None
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    preview: Optional[str] = None


class ConversationDetailResponse(BaseModel):
    """A conversation with all its messages."""
    id: str
    workspace_id: Optional[int] = None
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    messages: List[ConversationMessageResponse] = []


class RenameConversationRequest(BaseModel):
    """Request body to rename a conversation."""
    title: str = Field(..., min_length=1, max_length=255)
