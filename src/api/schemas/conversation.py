"""
Conversation API Schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from src.models.data_analyst import DataSourceType, ConversationType


class ConversationCreate(BaseModel):
    """Request to create a new conversation"""
    data_source_type: DataSourceType
    conversation_type: ConversationType = ConversationType.USER
    title: Optional[str] = None
    participant_ids: Optional[List[int]] = Field(None, description="User IDs to add to group conversation")


class ParticipantInfo(BaseModel):
    """Participant information"""
    user_id: int
    role: str
    joined_at: datetime


class ConversationResponse(BaseModel):
    """Conversation response"""
    conversation_id: str
    user_id: int
    customer_id: str
    data_source_type: str
    conversation_type: str
    is_shared: bool
    participants: List[dict]
    title: Optional[str]
    status: str
    message_count: int = 0
    latest_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_activity_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """List of conversations"""
    conversations: List[ConversationResponse]
    total: int
    page: int
    page_size: int


class ConversationUpdateTitle(BaseModel):
    """Update conversation title"""
    title: str


class ConversationAddParticipant(BaseModel):
    """Add participant to conversation"""
    user_id: int

