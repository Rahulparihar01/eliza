"""
Workspace API Schemas - Request and Response models for workspaces and knowledge bases.

Provides schemas for:
- WorkspaceTemplate: Available workspace types
- Workspace: Workspace CRUD operations (extends RAGFlow domains)
- KnowledgeBase: Knowledge base management within workspaces
- KnowledgeBasePermission: Permission management
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


# ==================== Enums ====================

class WorkspaceTemplateType(str, Enum):
    """Available workspace template types."""
    RAG_RETRIEVAL = "rag_retrieval"
    DATA_ANALYTICS = "data_analytics"
    AGENT_MESH_RETRIEVAL = "agent_mesh_retrieval"


class KnowledgeBaseStatus(str, Enum):
    """Status of a knowledge base."""
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class KnowledgeBasePermissionType(str, Enum):
    """Permission types for knowledge base access."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class ParserType(str, Enum):
    """Document parsing strategies."""
    NAIVE = "naive"
    DEEPDOC = "deepdoc"
    GPT4O = "gpt-4o"
    DOCLING = "docling"
    CUSTOM_VLM = "custom-vlm"


class KnowledgeBaseSourceType(str, Enum):
    """Supported upstream source types for a knowledge base."""

    ELASTICSEARCH = "elasticsearch"
    S3 = "s3"
    LOCAL_DIRECTORY = "local_directory"


class KnowledgeBaseStorageBackend(str, Enum):
    """Storage backend used for raw document blobs."""

    TENANT_DEFAULT = "tenant_default"
    S3 = "s3"
    MINIO = "minio"


# ==================== Workspace Template Schemas ====================

class WorkspaceTemplateResponse(BaseModel):
    """Workspace template details."""
    id: int
    name: str
    display_name: str
    description: Optional[str]
    icon: str
    is_available: bool
    config_schema: Optional[Dict[str, Any]] = None
    default_config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class WorkspaceTemplateListResponse(BaseModel):
    """List of workspace templates."""
    templates: List[WorkspaceTemplateResponse]
    total: int


# ==================== Knowledge Base Schemas ====================

class KnowledgeBaseCreateRequest(BaseModel):
    """Request to create a knowledge base within a workspace."""
    name: str = Field(..., min_length=1, max_length=255, description="Knowledge base name")
    description: Optional[str] = Field(None, max_length=2000, description="Description")
    parser_type: ParserType = Field(
        default=ParserType.NAIVE,
        description="Document parser type"
    )
    parser_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional parser configuration"
    )
    embedding_model: Optional[str] = Field(
        None,
        description="Embedding model (default: text-embedding-3-large@OpenAI)"
    )
    chunk_token_count: Optional[int] = Field(
        512,
        ge=128,
        le=2048,
        description="Tokens per chunk"
    )
    similarity_threshold: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Minimum similarity score (0-100)"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve"
    )
    source_type: KnowledgeBaseSourceType = Field(
        default=KnowledgeBaseSourceType.ELASTICSEARCH,
        description="Document source type for this knowledge base",
    )
    source_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Source-specific configuration (path/prefix/index details)",
    )
    storage_backend: KnowledgeBaseStorageBackend = Field(
        default=KnowledgeBaseStorageBackend.TENANT_DEFAULT,
        description="Raw document storage backend selection",
    )
    storage_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional backend-specific overrides for this knowledge base",
    )

    @model_validator(mode="after")
    def validate_s3_source_path(self):
        """Require an S3 path/prefix when source_type is S3."""
        if self.source_type != KnowledgeBaseSourceType.S3:
            return self
        source_config = self.source_config or {}
        raw_path = (
            source_config.get("s3_path")
            or source_config.get("prefix")
            or source_config.get("path")
            or ""
        )
        if not str(raw_path).strip():
            raise ValueError(
                "source_config.prefix (or source_config.s3_path) is required when source_type='s3'"
            )
        return self


class KnowledgeBaseUpdateRequest(BaseModel):
    """Request to update a knowledge base."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    parser_type: Optional[ParserType] = None
    parser_config: Optional[Dict[str, Any]] = None
    similarity_threshold: Optional[int] = Field(None, ge=0, le=100)
    top_k: Optional[int] = Field(None, ge=1, le=20)
    is_active: Optional[bool] = None
    source_type: Optional[KnowledgeBaseSourceType] = None
    source_config: Optional[Dict[str, Any]] = None
    storage_backend: Optional[KnowledgeBaseStorageBackend] = None
    storage_config: Optional[Dict[str, Any]] = None


class KnowledgeBaseResponse(BaseModel):
    """Knowledge base details."""
    id: int
    workspace_id: int
    customer_id: str
    name: str
    description: Optional[str]
    ragflow_dataset_id: Optional[str]
    parser_type: str
    parser_config: Optional[Dict[str, Any]]
    embedding_model: str
    chunk_token_count: int
    similarity_threshold: int
    top_k: int
    source_type: str
    source_config: Optional[Dict[str, Any]]
    storage_backend: str
    storage_config: Optional[Dict[str, Any]]
    document_count: int
    chunk_count: int
    total_tokens: int
    status: KnowledgeBaseStatus
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseListResponse(BaseModel):
    """List of knowledge bases."""
    knowledge_bases: List[KnowledgeBaseResponse]
    total: int


class KnowledgeBaseSummaryResponse(BaseModel):
    """Brief knowledge base summary for workspace detail."""
    id: int
    name: str
    status: KnowledgeBaseStatus
    document_count: int
    chunk_count: int
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)


# ==================== Knowledge Base Permission Schemas ====================

class KnowledgeBasePermissionCreateRequest(BaseModel):
    """Request to grant knowledge base permission."""
    user_id: Optional[int] = Field(None, description="User to grant permission (mutually exclusive with role_id)")
    role_id: Optional[int] = Field(None, description="Role to grant permission (mutually exclusive with user_id)")
    permission_type: KnowledgeBasePermissionType = Field(
        ...,
        description="Permission type: read, write, or admin"
    )


class KnowledgeBasePermissionResponse(BaseModel):
    """Knowledge base permission details."""
    id: int
    knowledge_base_id: int
    user_id: Optional[int]
    role_id: Optional[int]
    permission_type: KnowledgeBasePermissionType
    granted_by_user_id: Optional[int]
    created_at: datetime
    
    # Include user/role names for display
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    role_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class KnowledgeBasePermissionListResponse(BaseModel):
    """List of permissions for a knowledge base."""
    permissions: List[KnowledgeBasePermissionResponse]
    total: int


# ==================== Workspace Schemas (Extends RAGFlow Domain) ====================

class WorkspaceCreateRequest(BaseModel):
    """Request to create a new workspace."""
    template_id: int = Field(..., description="Workspace template ID")
    name: str = Field(..., min_length=1, max_length=100, description="Unique workspace identifier (lowercase, no spaces)")
    display_name: str = Field(..., min_length=1, max_length=255, description="Human-readable display name")
    description: Optional[str] = Field(None, max_length=2000, description="Workspace description")
    icon: str = Field(
        default="folder",
        max_length=50,
        description="Icon key"
    )
    color: str = Field(
        default="violet",
        max_length=50,
        description="Color token"
    )
    workspace_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Template-specific configuration"
    )
    
    # Initial knowledge base (for RAG Retrieval template)
    initial_knowledge_base: Optional[KnowledgeBaseCreateRequest] = Field(
        None,
        description="Optional: Create an initial knowledge base with the workspace"
    )


class WorkspaceUpdateRequest(BaseModel):
    """Request to update workspace settings."""
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=50)
    workspace_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class WorkspaceResponse(BaseModel):
    """Workspace details (extends RAGFlow Domain)."""
    id: int
    customer_id: str
    name: str
    display_name: str
    description: Optional[str]
    icon: str
    color: str
    
    # Template info
    template_id: Optional[int]
    template_name: Optional[str] = None
    template_display_name: Optional[str] = None
    
    workspace_config: Optional[Dict[str, Any]]
    
    # Status
    status: str
    
    # Aggregated stats from knowledge bases
    document_count: int
    chunk_count: int
    total_tokens: int
    knowledge_base_count: int = 0
    
    is_active: bool
    last_error: Optional[str] = None
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Knowledge bases summary (optional, for detail view)
    knowledge_bases: Optional[List[KnowledgeBaseSummaryResponse]] = None
    
    model_config = ConfigDict(from_attributes=True)


class WorkspaceListResponse(BaseModel):
    """List of workspaces."""
    workspaces: List[WorkspaceResponse]
    total: int
    offset: int
    limit: int


class WorkspaceDetailResponse(BaseModel):
    """Detailed workspace view including knowledge bases."""
    workspace: WorkspaceResponse
    knowledge_bases: List[KnowledgeBaseResponse]
    template: Optional[WorkspaceTemplateResponse]


# ==================== Workspace Prompt Template Schemas ====================

class WorkspacePromptTemplateResponse(BaseModel):
    """Workspace prompt template configuration."""
    workspace_id: int
    workspace_name: str
    domain: str
    system_prompt: str
    query_rewrite_prompt: Optional[str] = None
    synthesis_prompt: Optional[str] = None
    retrieval_prompt: Optional[str] = None
    model: str
    temperature: float
    max_tokens: int
    top_k: int
    similarity_threshold: float
    use_query_rewrite: bool
    use_hybrid_search: bool
    citation_mode: bool
    max_context_chunks: int
    gepa_variant_id: Optional[int] = None
    gepa_job_id: Optional[int] = None
    prompt_version: int


class WorkspacePromptTemplateUpdateRequest(BaseModel):
    """Patchable workspace prompt template configuration."""
    system_prompt: Optional[str] = None
    query_rewrite_prompt: Optional[str] = None
    synthesis_prompt: Optional[str] = None
    retrieval_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32000)
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    use_query_rewrite: Optional[bool] = None
    use_hybrid_search: Optional[bool] = None
    citation_mode: Optional[bool] = None
    max_context_chunks: Optional[int] = Field(default=None, ge=1, le=20)


# ==================== Workspace Telemetry Schemas ====================

class WorkspaceTelemetryRequestItem(BaseModel):
    """Workspace chat request/response pair with local usage stats."""
    conversation_id: int
    conversation_uuid: str
    user_message_id: Optional[int] = None
    assistant_message_id: int
    request_text: Optional[str] = None
    response_text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    created_at: datetime
    latency_ms: Optional[float] = None


class WorkspaceLangfuseTraceItem(BaseModel):
    """Langfuse trace metadata mapped for workspace telemetry UI."""
    trace_id: str
    name: Optional[str] = None
    timestamp: Optional[datetime] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    url: Optional[str] = None


class WorkspaceTelemetryResponse(BaseModel):
    """Workspace telemetry payload including local requests and Langfuse traces."""
    workspace_id: int
    workspace_name: str
    langfuse_enabled: bool = False
    langfuse_host: Optional[str] = None
    langfuse_public_url: Optional[str] = None
    langfuse_embed_url: Optional[str] = None
    langfuse_project_id: Optional[str] = None
    recent_requests: List[WorkspaceTelemetryRequestItem] = Field(default_factory=list)
    traces: List[WorkspaceLangfuseTraceItem] = Field(default_factory=list)
    traces_fetch_error: Optional[str] = None


# ==================== Chat History Schemas ====================

class ConversationSummary(BaseModel):
    """Conversation summary for chat history list."""
    id: int
    uuid: str
    workspace_id: int
    workspace_name: str
    workspace_display_name: str
    workspace_color: str
    title: Optional[str]
    message_count: int
    last_message_at: Optional[datetime]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    """User's chat history across all workspaces."""
    conversations: List[ConversationSummary]
    total: int
    page: int
    page_size: int


# ==================== Workspace Picker Schema ====================

class WorkspacePickerItem(BaseModel):
    """Workspace item for the chat workspace picker."""
    id: int
    name: str
    display_name: str
    description: Optional[str]
    icon: str
    color: str
    template_name: Optional[str]
    template_display_name: Optional[str]
    document_count: int
    is_available: bool  # True if user has access and workspace is ready
    
    model_config = ConfigDict(from_attributes=True)


class WorkspacePickerResponse(BaseModel):
    """List of workspaces for the chat picker."""
    workspaces: List[WorkspacePickerItem]
    total: int
