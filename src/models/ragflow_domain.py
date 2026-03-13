"""
RAGFlow Domain Models - Multi-tenant RAG knowledge base management.

Maps Eliza customer domains to RAGFlow datasets for document-based chat.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, JSON, Enum, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.models.database import BaseModel, Base


class RAGFlowParserType(str, PyEnum):
    """Document parsing strategies in RAGFlow."""
    NAIVE = "naive"           # Fast, plain text extraction
    DEEPDOC = "deepdoc"       # CPU-based OCR and layout recognition
    GPT4O = "gpt-4o"          # Vision model (legacy fallback)
    GPT5 = "gpt-5.2"          # Vision model for complex documents (recommended)
    DOCLING = "docling"       # Balanced parser option
    CUSTOM_VLM = "custom-vlm"  # Custom hosted VLM (OpenAI-compatible)


class RAGFlowDomainStatus(str, PyEnum):
    """Status of a RAGFlow domain (per spec)."""
    PENDING = "pending"       # Domain created, no documents yet or awaiting first upload
    INDEXING = "indexing"     # Documents being processed/parsed
    READY = "ready"           # All documents processed, ready for chat
    FAILED = "failed"         # Ingestion/processing failed


class RAGFlowDomain(BaseModel):
    """
    RAGFlow domain representing a workspace (formerly knowledge base).
    
    A workspace can contain multiple knowledge bases and supports
    different template types (RAG Retrieval, Data Analytics, etc.)
    
    Maps to a RAGFlow dataset and stores configuration for document
    parsing, embedding, and retrieval.
    """
    __tablename__ = "ragflow_domains"
    
    # Identification
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # UI customization (per spec)
    icon = Column(String(50), nullable=False, default="folder")  # Icon key from icon set
    color = Column(String(50), nullable=False, default="violet")  # Color token/hex
    
    # Workspace Template
    template_id = Column(Integer, ForeignKey("workspace_templates.id"), nullable=True, index=True)
    workspace_config = Column(JSON, nullable=True)  # Template-specific configuration
    prompt_config_json = Column(JSON, nullable=True)  # WorkspacePromptTemplate snapshot
    
    # RAGFlow dataset mapping (legacy - moving to KnowledgeBase)
    ragflow_dataset_id = Column(String(100), nullable=True, unique=True, index=True)
    ragflow_dataset_name = Column(String(255), nullable=True)  # name used in RAGFlow
    
    # Status
    status = Column(
        Enum(RAGFlowDomainStatus, name='ragflow_domain_status', values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        default=RAGFlowDomainStatus.PENDING
    )
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_error = Column(Text, nullable=True)
    last_error = Column(Text, nullable=True)  # Per spec: surface last_error on Domain
    
    # Parser configuration (legacy - moving to KnowledgeBase)
    parser_type = Column(
        Enum(RAGFlowParserType, name='ragflow_parser_type', values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        default=RAGFlowParserType.NAIVE
    )
    parser_config = Column(JSON, nullable=True)  # Additional parser settings
    
    # Embedding configuration (legacy - moving to KnowledgeBase)
    embedding_model = Column(String(100), nullable=False, default="text-embedding-3-large@OpenAI")
    chunk_token_count = Column(Integer, nullable=False, default=512)
    
    # Retrieval configuration (legacy - moving to KnowledgeBase)
    similarity_threshold = Column(Integer, nullable=False, default=20)  # 0-100, RAGFlow uses 0.2
    top_k = Column(Integer, nullable=False, default=5)
    
    # Statistics (aggregated from knowledge bases)
    document_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    
    # Feature flags
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Audit
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    template = relationship("WorkspaceTemplate", back_populates="workspaces")
    knowledge_bases = relationship("KnowledgeBase", back_populates="workspace", cascade="all, delete-orphan")
    documents = relationship("RAGFlowDocument", back_populates="domain", cascade="all, delete-orphan")
    conversations = relationship("RAGFlowConversation", back_populates="workspace", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    
    __table_args__ = (
        UniqueConstraint('customer_id', 'name', name='uq_ragflow_domain_name'),
        Index('ix_ragflow_domains_customer_status', 'customer_id', 'status'),
    )
    
    def __repr__(self):
        return f"<RAGFlowDomain {self.customer_id}/{self.name}>"


class RAGFlowDocumentStatus(str, PyEnum):
    """Status of a document in RAGFlow."""
    PENDING = "pending"         # Uploaded, not yet parsed
    PARSING = "parsing"         # Being processed
    COMPLETED = "completed"     # Ready for retrieval
    FAILED = "failed"


class RAGFlowDocument(BaseModel):
    """
    Document tracked in a RAGFlow domain/knowledge base.
    
    Maps local document uploads to RAGFlow document IDs and tracks
    processing status. Documents now belong to knowledge bases within workspaces.
    """
    __tablename__ = "ragflow_documents"
    
    # Domain relationship (workspace - legacy, keep for backwards compat)
    domain_id = Column(Integer, ForeignKey("ragflow_domains.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Knowledge base relationship (new - documents belong to KBs)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Multi-tenant isolation
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    
    # File information
    original_filename = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    
    # RAGFlow mapping
    ragflow_document_id = Column(String(100), nullable=True, unique=True, index=True)
    ragflow_run_id = Column(String(100), nullable=True)  # Parsing job ID
    
    # Status
    status = Column(
        Enum(RAGFlowDocumentStatus, name='ragflow_document_status', values_callable=lambda x: [e.value for e in x], create_type=False),
        nullable=False,
        default=RAGFlowDocumentStatus.PENDING
    )
    progress = Column(Integer, nullable=False, default=0)  # 0-100 parsing progress
    processing_error = Column(Text, nullable=True)
    
    # Processing results
    chunk_count = Column(Integer, nullable=False, default=0)
    token_count = Column(Integer, nullable=False, default=0)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    document_metadata = Column(JSON, nullable=True)
    
    # Audit
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    domain = relationship("RAGFlowDomain", back_populates="documents")
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])
    
    __table_args__ = (
        Index('ix_ragflow_documents_domain_status', 'domain_id', 'status'),
        Index('ix_ragflow_documents_knowledge_base_id', 'knowledge_base_id'),
    )
    
    def __repr__(self):
        return f"<RAGFlowDocument {self.original_filename} ({self.status.value})>"


class RAGFlowConversation(BaseModel):
    """
    Chat conversation with a RAGFlow workspace.
    
    Tracks conversation history for RAG-based Q&A.
    All conversations belong to a workspace.
    """
    __tablename__ = "ragflow_conversations"
    
    # Workspace relationship (domain_id = workspace_id)
    domain_id = Column(Integer, ForeignKey("ragflow_domains.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # UUID for URL-friendly identification
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    
    # Conversation info
    title = Column(String(255), nullable=True)  # Auto-generated or user-defined
    source = Column(String(50), nullable=True)  # "web", "mcp", "api" — tracks origin channel
    
    # Statistics
    message_count = Column(Integer, nullable=False, default=0)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    workspace = relationship("RAGFlowDomain", back_populates="conversations")
    messages = relationship("RAGFlowMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="RAGFlowMessage.created_at")
    user = relationship("User")
    
    __table_args__ = (
        Index('ix_ragflow_conversations_user_domain', 'user_id', 'domain_id'),
    )


class RAGFlowMessage(Base):
    """
    Individual message in a RAGFlow conversation.
    """
    __tablename__ = "ragflow_messages"
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Conversation relationship
    conversation_id = Column(Integer, ForeignKey("ragflow_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Message content
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    
    # RAG retrieval context (for assistant messages)
    retrieved_chunks = Column(JSON, nullable=True)  # List of chunk references
    chunk_count = Column(Integer, nullable=True)
    
    # Token usage
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    
    # Relationships
    conversation = relationship("RAGFlowConversation", back_populates="messages")
