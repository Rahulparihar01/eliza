"""
Pydantic schemas for Document API endpoints.
Defines request/response models for document operations, stats, and listings.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from src.models.document import DocumentStatus


# ============================================================================
# Document Statistics Schema
# ============================================================================

class DocumentStatsResponse(BaseModel):
    """Document statistics response schema"""
    total_documents: int = Field(..., ge=0, description="Total number of documents")
    processing_documents: int = Field(..., ge=0, description="Documents currently processing")
    completed_documents: int = Field(..., ge=0, description="Completed documents")
    failed_documents: int = Field(..., ge=0, description="Failed documents")
    total_chunks: int = Field(..., ge=0, description="Total document chunks")
    storage_used_mb: float = Field(..., ge=0, description="Storage used in megabytes")

    class Config:
        json_schema_extra = {
            "example": {
                "total_documents": 150,
                "processing_documents": 5,
                "completed_documents": 140,
                "failed_documents": 5,
                "total_chunks": 4500,
                "storage_used_mb": 2048.5
            }
        }


# ============================================================================
# Recent Documents Schema
# ============================================================================

class RecentDocumentInfo(BaseModel):
    """Simplified document info for recent uploads"""
    id: int = Field(..., description="Document ID")
    original_filename: str = Field(..., description="Original filename")
    status: DocumentStatus = Field(..., description="Processing status")
    created_at: datetime = Field(..., description="Upload timestamp")
    total_chunks: int = Field(default=0, ge=0, description="Total chunks created")
    file_size_bytes: int = Field(default=0, ge=0, description="File size in bytes")
    company_hr_dataset: Optional[str] = Field(None, description="Company associated with this document")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "original_filename": "report.pdf",
                "status": "completed",
                "created_at": "2025-10-01T10:30:00Z",
                "total_chunks": 45,
                "file_size_bytes": 1048576,
                "company_hr_dataset": "eliza"
            }
        }


class RecentDocumentsResponse(BaseModel):
    """Recent documents list response"""
    documents: List[RecentDocumentInfo] = Field(default_factory=list, description="List of recent documents")
    total: int = Field(..., ge=0, description="Total number of documents returned")
    limit: int = Field(..., ge=1, description="Limit applied to query")

    class Config:
        json_schema_extra = {
            "example": {
                "documents": [
                    {
                        "id": 123,
                        "original_filename": "report.pdf",
                        "status": "completed",
                        "created_at": "2025-10-01T10:30:00Z",
                        "total_chunks": 45,
                        "file_size_bytes": 1048576
                    }
                ],
                "total": 10,
                "limit": 5
            }
        }

