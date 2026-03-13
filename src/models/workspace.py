"""
Workspace Models - Multi-tenant workspace and knowledge base management.

Provides models for:
- WorkspaceTemplate: Available workspace types (RAG Retrieval, Data Analytics)
- KnowledgeBase: Knowledge bases within workspaces
- KnowledgeBasePermission: User/role access to knowledge bases
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, JSON, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.database import BaseModel, Base


class WorkspaceTemplateType(str, PyEnum):
    """Available workspace template types."""
    RAG_RETRIEVAL = "rag_retrieval"
    DATA_ANALYTICS = "data_analytics"
    AGENT_MESH_RETRIEVAL = "agent_mesh_retrieval"


class KnowledgeBaseStatus(str, PyEnum):
    """Status of a knowledge base."""
    PENDING = "pending"       # Created, no documents yet
    INDEXING = "indexing"     # Documents being processed
    READY = "ready"           # Ready for retrieval
    FAILED = "failed"         # Processing failed


class KnowledgeBasePermissionType(str, PyEnum):
    """Permission types for knowledge base access."""
    READ = "read"             # Can query/search the KB
    WRITE = "write"           # Can upload/manage documents
    ADMIN = "admin"           # Full control including permissions


class KnowledgeBaseSourceType(str, PyEnum):
    """Upstream source types for knowledge base ingestion."""

    ELASTICSEARCH = "elasticsearch"
    S3 = "s3"
    LOCAL_DIRECTORY = "local_directory"


class KnowledgeBaseStorageBackend(str, PyEnum):
    """Raw object storage backend options."""

    TENANT_DEFAULT = "tenant_default"
    S3 = "s3"
    MINIO = "minio"


class WorkspaceTemplate(BaseModel):
    """
    Workspace template defining available workspace types.
    
    Templates define the structure and configuration options
    for different workspace types (RAG Retrieval, Data Analytics, etc.)
    """
    __tablename__ = "workspace_templates"
    
    # Template identification
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # UI
    icon = Column(String(50), nullable=False, default="folder")
    
    # Availability
    is_available = Column(Boolean, nullable=False, default=True)
    
    # Configuration schema (JSON Schema)
    config_schema = Column(JSON, nullable=True)
    default_config = Column(JSON, nullable=True)
    
    # Relationships
    workspaces = relationship("RAGFlowDomain", back_populates="template")
    
    def __repr__(self):
        return f"<WorkspaceTemplate {self.name}>"


class KnowledgeBase(BaseModel):
    """
    Knowledge base within a workspace.
    
    Each workspace can have multiple knowledge bases, each containing
    documents for RAG retrieval. Supports KB-level permissions.
    """
    __tablename__ = "knowledge_bases"
    
    # Workspace relationship
    workspace_id = Column(
        Integer, 
        ForeignKey("ragflow_domains.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Multi-tenant isolation (denormalized for RLS)
    customer_id = Column(
        String(100), 
        ForeignKey("customers.customer_id"), 
        nullable=False, 
        index=True
    )
    
    # Knowledge base identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # RAGFlow integration
    ragflow_dataset_id = Column(String(100), nullable=True, unique=True, index=True)
    
    # Parser configuration
    parser_type = Column(String(50), nullable=False, default="naive")
    parser_config = Column(JSON, nullable=True)
    
    # Embedding configuration
    embedding_model = Column(String(100), nullable=False, default="text-embedding-3-large@OpenAI")
    chunk_token_count = Column(Integer, nullable=False, default=512)
    
    # Retrieval configuration
    similarity_threshold = Column(Integer, nullable=False, default=20)
    top_k = Column(Integer, nullable=False, default=5)

    # Source/storage configuration
    source_type = Column(String(50), nullable=False, default=KnowledgeBaseSourceType.ELASTICSEARCH.value)
    source_config = Column(JSON, nullable=True)
    storage_backend = Column(
        String(50),
        nullable=False,
        default=KnowledgeBaseStorageBackend.TENANT_DEFAULT.value,
    )
    storage_config = Column(JSON, nullable=True)
    
    # Statistics (synced from RAGFlow)
    document_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    
    # Status
    status = Column(String(50), nullable=False, default=KnowledgeBaseStatus.PENDING.value)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Flags
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Audit
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    workspace = relationship("RAGFlowDomain", back_populates="knowledge_bases")
    documents = relationship("RAGFlowDocument", back_populates="knowledge_base")
    permissions = relationship(
        "KnowledgeBasePermission", 
        back_populates="knowledge_base",
        cascade="all, delete-orphan"
    )
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    
    __table_args__ = (
        UniqueConstraint('workspace_id', 'name', name='uq_knowledge_base_workspace_name'),
        Index('ix_knowledge_bases_status', 'status'),
    )
    
    def __repr__(self):
        return f"<KnowledgeBase {self.workspace_id}/{self.name}>"


class KnowledgeBasePermission(Base):
    """
    Permission grant for knowledge base access.
    
    Supports both user-level and role-level permissions.
    Each permission can be read, write, or admin.
    """
    __tablename__ = "knowledge_base_permissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Knowledge base relationship
    knowledge_base_id = Column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Permission target (user OR role, not both)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Permission type
    permission_type = Column(String(50), nullable=False)
    
    # Audit
    granted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="permissions")
    user = relationship("User", foreign_keys=[user_id])
    role = relationship("Role", foreign_keys=[role_id])
    granted_by = relationship("User", foreign_keys=[granted_by_user_id])
    
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND role_id IS NULL) OR (user_id IS NULL AND role_id IS NOT NULL)",
            name='kb_perm_user_or_role'
        ),
        UniqueConstraint('knowledge_base_id', 'user_id', name='uq_kb_perm_user'),
        UniqueConstraint('knowledge_base_id', 'role_id', name='uq_kb_perm_role'),
    )
    
    def __repr__(self):
        target = f"user:{self.user_id}" if self.user_id else f"role:{self.role_id}"
        return f"<KnowledgeBasePermission {self.knowledge_base_id} -> {target} ({self.permission_type})>"
