"""
Document models for the AI Enablement Platform.
Handles document storage, processing status, and metadata.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from .database import BaseModel as DBBaseModel


class DocumentStatus(str, Enum):
    """Document processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class ChunkingStrategy(str, Enum):
    """Available chunking strategies"""
    SEMANTIC = "semantic"
    FIXED = "fixed"
    HIERARCHICAL = "hierarchical"
    ADAPTIVE = "adaptive"
    HYBRID = "hybrid"


class Document(DBBaseModel):
    """Document storage model"""
    __tablename__ = "documents"
    __table_args__ = ({'extend_existing': True},)
    
    # Basic document info
    filename = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # Database uses bigint, but Integer works for most files
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash
    
    # Processing info
    status = Column(String(20), nullable=False, default=DocumentStatus.UPLOADED, index=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)
    
    # Chunking configuration
    chunking_strategy = Column(String(20), nullable=False, default=ChunkingStrategy.SEMANTIC)
    chunking_config = Column(JSON, nullable=True)
    
    # Processing results
    total_chunks = Column(Integer, nullable=False, default=0)
    duplicate_chunks_count = Column(Integer, nullable=False, default=0)  # Chunks skipped due to duplicates
    total_characters = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    
    # Quality metrics
    quality_score = Column(Float, nullable=True)
    extraction_confidence = Column(Float, nullable=True)
    
    # Relationships
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)  # Uploader's organization
    company_hr_dataset = Column(String(100), nullable=True, index=True)  # Target company for data association
    source_id = Column(String(100), nullable=True, index=True)  # Associated data source
    upload_batch_id = Column(String(100), nullable=True, index=True)  # Batch upload ID
    
    # Metadata
    document_metadata = Column(JSON, nullable=True)
    extracted_metadata = Column(JSON, nullable=True)  # Metadata extracted from document
    
    # Enable QA RAG processing
    qa_rag_enabled = Column(Boolean, nullable=False, default=False)
    qa_pairs_generated = Column(Integer, nullable=False, default=0)
    
    # Relationships with lazy loading disabled to prevent session issues
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="select")


class DocumentChunk(DBBaseModel):
    """Document chunk model"""
    __tablename__ = "document_chunks"
    __table_args__ = ({'extend_existing': True},)
    
    # Basic chunk info
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)  # Order within document
    chunk_id = Column(String(100), nullable=False, unique=True, index=True)  # Database uses varchar(50), but 100 is safe
    company_hr_dataset = Column(String(100), nullable=True, index=True)  # Inherited from parent document
    
    # Content
    text = Column(Text, nullable=False)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    character_count = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=False)
    
    # Vector embedding (column is 'embedding_vector' in database)
    embedding_vector = Column(JSON, nullable=True)  # Stored as array
    embedding_model = Column(String(100), nullable=True)
    embedding_created_at = Column(DateTime(timezone=True), nullable=True)
    
    # Quality metrics
    quality_score = Column(Float, nullable=True)
    semantic_density = Column(Float, nullable=True)
    
    # Duplicate detection
    is_duplicate = Column(Boolean, nullable=False, default=False)
    duplicate_of_chunk_id = Column(String(100), nullable=True)
    
    # Hierarchical info
    section_title = Column(String(500), nullable=True)
    section_level = Column(Integer, nullable=True)
    parent_chunk_id = Column(String(100), nullable=True, index=True)
    
    # QA RAG data
    qa_questions = Column(JSON, nullable=True)  # Generated questions
    qa_answers = Column(JSON, nullable=True)    # Generated answers
    qa_quality_score = Column(Float, nullable=True)
    
    # Metadata
    chunk_metadata = Column(JSON, nullable=True)
    
    # Relationships with lazy loading disabled to prevent session issues
    document = relationship("Document", back_populates="chunks", lazy="select")


class UploadBatch(DBBaseModel):
    """Upload batch tracking"""
    __tablename__ = "upload_batches"
    __table_args__ = ({'extend_existing': True},)
    
    batch_id = Column(String(100), nullable=False, unique=True, index=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    
    # Batch info
    total_files = Column(Integer, nullable=False, default=0)
    completed_files = Column(Integer, nullable=False, default=0)
    failed_files = Column(Integer, nullable=False, default=0)
    
    # Status
    status = Column(String(20), nullable=False, default="processing")
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Configuration
    chunking_strategy = Column(String(20), nullable=False, default=ChunkingStrategy.SEMANTIC)
    chunking_config = Column(JSON, nullable=True)
    qa_rag_enabled = Column(Boolean, nullable=False, default=False)
    
    # Results
    total_chunks_created = Column(Integer, nullable=False, default=0)
    total_qa_pairs_generated = Column(Integer, nullable=False, default=0)
    
    # Metadata
    batch_metadata = Column(JSON, nullable=True)


# Pydantic models for API

class DocumentUploadRequest(BaseModel):
    """Request model for document upload"""
    source_id: Optional[str] = None
    company_hr_dataset: Optional[str] = None  # Company for document association
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC
    chunking_config: Optional[Dict[str, Any]] = None
    enable_qa_rag: bool = False
    metadata: Optional[Dict[str, Any]] = None
    document_metadata: Optional[Dict[str, Any]] = None


class DocumentInfo(BaseModel):
    """Document information response"""
    id: int
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    status: DocumentStatus
    total_chunks: int
    duplicate_chunks_count: int = 0  # Chunks skipped due to duplicates
    total_characters: int
    quality_score: Optional[float]
    chunking_strategy: ChunkingStrategy
    qa_rag_enabled: bool
    qa_pairs_generated: int
    customer_id: str
    company_hr_dataset: Optional[str] = None  # Company association for document
    created_at: datetime
    processing_completed_at: Optional[datetime]
    document_metadata: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkInfo(BaseModel):
    """Document chunk information"""
    id: int
    chunk_id: str
    chunk_index: int
    text: str
    character_count: int
    token_count: int
    quality_score: Optional[float]
    section_title: Optional[str]
    section_level: Optional[int]
    qa_questions: Optional[List[str]]
    qa_answers: Optional[List[str]]
    chunk_metadata: Optional[Dict[str, Any]]
    
    model_config = ConfigDict(from_attributes=True)


class UploadBatchInfo(BaseModel):
    """Upload batch information"""
    batch_id: str
    total_files: int
    completed_files: int
    failed_files: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    chunking_strategy: ChunkingStrategy
    qa_rag_enabled: bool
    total_chunks_created: int
    total_qa_pairs_generated: int
    progress_percentage: float = Field(default=0.0)
    
    model_config = ConfigDict(from_attributes=True)
    
    def __init__(self, **data):
        super().__init__(**data)
        # Calculate progress percentage
        if self.total_files > 0:
            self.progress_percentage = (self.completed_files + self.failed_files) / self.total_files * 100
        else:
            self.progress_percentage = 0.0


class DocumentSearchRequest(BaseModel):
    """Document search request"""
    query: str
    limit: int = Field(default=10, ge=1, le=100)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    source_ids: Optional[List[str]] = None
    document_ids: Optional[List[int]] = None
    include_qa_pairs: bool = False


class DocumentSearchResult(BaseModel):
    """Document search result"""
    chunk_id: str
    document_id: int
    document_filename: str
    text: str
    similarity_score: float
    section_title: Optional[str]
    qa_questions: Optional[List[str]]
    qa_answers: Optional[List[str]]
    metadata: Optional[Dict[str, Any]]
