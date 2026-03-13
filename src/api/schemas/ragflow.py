"""
RAGFlow API Schemas - Request and Response models for RAG domains.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


# ==================== Enums ====================

class RAGFlowParserType(str, Enum):
    """Document parsing strategies."""
    NAIVE = "naive"
    DEEPDOC = "deepdoc"
    GPT4O = "gpt-4o"
    GPT5 = "gpt-5.2"
    DOCLING = "docling"
    CUSTOM_VLM = "custom-vlm"


class RAGFlowDomainStatus(str, Enum):
    """Domain status (per spec)."""
    PENDING = "pending"       # Domain created, awaiting first upload
    INDEXING = "indexing"     # Documents being processed
    READY = "ready"           # Ready for chat
    FAILED = "failed"         # Ingestion failed


class RAGFlowDocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== Domain Schemas ====================

class CreateDomainRequest(BaseModel):
    """Request to create a new RAG domain."""
    name: str = Field(..., min_length=1, max_length=100, description="Unique domain identifier (lowercase, no spaces)")
    display_name: str = Field(..., min_length=1, max_length=255, description="Human-readable display name")
    description: Optional[str] = Field(None, max_length=2000, description="Domain description")
    icon: str = Field(
        default="folder",
        max_length=50,
        description="Icon key from icon set (e.g., folder, document, chart)"
    )
    color: str = Field(
        default="violet",
        max_length=50,
        description="Color token or hex (e.g., violet, emerald, #7c3aed)"
    )
    parser_type: RAGFlowParserType = Field(
        default=RAGFlowParserType.NAIVE,
        description="Document parser type. 'naive' is fast but basic, 'gpt-5.2' handles complex layouts (recommended), 'gpt-4o' is legacy fallback"
    )
    custom_vlm_model: Optional[str] = Field(
        None,
        description="Custom VLM model ID (e.g. deepseek-ocr2@OpenAI-API-Compatible) when parser_type=custom-vlm"
    )
    embedding_model: Optional[str] = Field(
        None,
        description="Embedding model (default: text-embedding-3-large@OpenAI)"
    )
    chunk_token_count: Optional[int] = Field(
        None,
        ge=128,
        le=2048,
        description="Tokens per chunk (default: 512)"
    )
    task_page_size: Optional[int] = Field(
        None,
        ge=1,
        le=50,
        description="Pages per parsing task (lower = more parallelism). Defaults: 4 for GPT-4o, 8 for DeepDoc, 12 for Naive"
    )
    similarity_threshold: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Minimum similarity score for retrieval (0-100, default: 20)"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve (default: 5)"
    )

    @model_validator(mode="after")
    def _validate_custom_vlm_model(self):
        if self.parser_type == RAGFlowParserType.CUSTOM_VLM:
            if not self.custom_vlm_model or not self.custom_vlm_model.strip():
                raise ValueError("custom_vlm_model is required when parser_type is custom-vlm")
        return self


class UpdateDomainRequest(BaseModel):
    """Request to update domain settings."""
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=50)
    parser_type: Optional[RAGFlowParserType] = None
    similarity_threshold: Optional[int] = Field(None, ge=0, le=100)
    top_k: Optional[int] = Field(None, ge=1, le=20)
    is_active: Optional[bool] = None


class DomainResponse(BaseModel):
    """Domain details response."""
    id: int
    customer_id: str
    name: str
    display_name: str
    description: Optional[str]
    icon: str
    color: str
    status: RAGFlowDomainStatus
    parser_type: RAGFlowParserType
    embedding_model: str
    chunk_token_count: int
    similarity_threshold: int
    top_k: int
    document_count: int
    chunk_count: int
    total_tokens: int
    is_active: bool
    last_error: Optional[str] = None
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DomainListResponse(BaseModel):
    """List of domains."""
    domains: List[DomainResponse]
    total: int
    offset: int
    limit: int


class DomainStatsResponse(BaseModel):
    """Domain statistics."""
    domain_id: int
    document_count: int
    chunk_count: int
    total_tokens: int
    completed_documents: int
    pending_documents: int
    failed_documents: int


# ==================== Document Schemas ====================

class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    id: int
    domain_id: int
    knowledge_base_id: Optional[int] = None
    original_filename: str
    file_size: int
    mime_type: str
    status: RAGFlowDocumentStatus
    ragflow_document_id: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    """Document details response."""
    id: int
    domain_id: int
    knowledge_base_id: Optional[int] = None
    customer_id: str
    original_filename: str
    file_size: int
    mime_type: str
    status: RAGFlowDocumentStatus
    progress: int
    ragflow_document_id: Optional[str]
    chunk_count: int
    token_count: int
    processing_error: Optional[str]
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    document_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """List of documents."""
    documents: List[DocumentResponse]
    total: int
    offset: int
    limit: int


# ==================== Retrieval Schemas ====================

class RetrievalRequest(BaseModel):
    """Request for document retrieval."""
    query: str = Field(..., min_length=1, max_length=2000, description="Search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results")
    similarity_threshold: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity (0-1), overrides domain default"
    )
    rerank: bool = Field(default=True, description="Whether to rerank results")
    fasb_source_filter: Optional[str] = Field(
        default=None,
        description="Optional FASB source filter: all | primary | memo"
    )
    knowledge_base_ids: Optional[List[int]] = Field(
        default=None,
        description="Optional knowledge base scope. Defaults to all accessible KBs in the workspace.",
    )


class RetrievedChunk(BaseModel):
    """A retrieved document chunk with enriched metadata."""
    content: str
    document_name: str
    document_id: Optional[str]
    similarity: float
    metadata: Optional[Dict[str, Any]] = None
    # Enriched fields from metadata enrichment pipeline
    page_number: Optional[int] = None
    page_range: Optional[List[int]] = None
    section_title: Optional[str] = None
    section_hierarchy: Optional[List[str]] = None
    chunk_type: Optional[str] = None
    chunk_summary: Optional[str] = None
    key_entities: Optional[List[str]] = None
    document_title: Optional[str] = None
    knowledge_base_name: Optional[str] = None
    chunk_index: Optional[int] = None


class RetrievalResponse(BaseModel):
    """Retrieval results."""
    query: str
    chunks: List[RetrievedChunk]
    total_chunks: int


# ==================== Chat/Conversation Schemas ====================

class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    title: Optional[str] = Field(None, max_length=255, description="Optional conversation title")


class ConversationResponse(BaseModel):
    """Conversation details."""
    id: int
    uuid: str
    domain_id: int
    user_id: int
    title: Optional[str]
    message_count: int
    last_message_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    """List of conversations."""
    conversations: List[ConversationResponse]
    total: int


class MessageResponse(BaseModel):
    """Chat message."""
    id: int
    conversation_id: int
    role: str  # "user" or "assistant"
    content: str
    retrieved_chunks: Optional[List[Dict[str, Any]]]
    chunk_count: Optional[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SendMessageRequest(BaseModel):
    """Request to send a chat message."""
    content: str = Field(..., min_length=1, max_length=4000, description="Message content")
    fasb_source_filter: Optional[str] = Field(
        default=None,
        description="Optional FASB source filter: all | primary | memo"
    )
    knowledge_base_ids: Optional[List[int]] = Field(
        default=None,
        description="Optional knowledge base scope for this message. Defaults to all accessible KBs.",
    )
    request_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional client-generated ID used for live Agent Mesh SSE progress streaming.",
    )


class ChatResponse(BaseModel):
    """Response to a chat message."""
    user_message: MessageResponse
    assistant_message: MessageResponse


class ConversationWithMessagesResponse(BaseModel):
    """Conversation with all messages."""
    conversation: ConversationResponse
    messages: List[MessageResponse]


# ==================== Health Check ====================

class RAGFlowHealthResponse(BaseModel):
    """RAGFlow service health status."""
    status: str  # "healthy" or "unhealthy"
    ragflow_reachable: bool
    api_configured: bool
    error: Optional[str] = None
