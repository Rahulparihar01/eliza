"""
Document management API routes for the AI Enablement Platform.
Handles document upload, processing, and retrieval.
"""

import logging
import json
import traceback
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.document import (
    DocumentUploadRequest, DocumentInfo, UploadBatchInfo, DocumentSearchRequest,
    DocumentSearchResult, DocumentStatus, ChunkingStrategy
)
from src.models.auth import User
from src.models.database import get_db
from src.api.schemas.documents import DocumentStatsResponse, RecentDocumentsResponse, RecentDocumentInfo
from src.services.document_processor import DocumentProcessor
from src.services.vector_service import VectorService
from src.services.native_rag_service import NativeRAGService, NativeRAGError
from src.core.config import get_settings
from src.middleware.authorization import get_current_user, get_current_customer_id, authorization_middleware, require_permission
from src.core.auth_context import CurrentUserContext

# Mapping for serving files with correct MIME types
SIMPLIFIED_TO_MIME_TYPE = {
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'ppt': 'application/vnd.ms-powerpoint',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'txt': 'text/plain',
    'md': 'text/markdown',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'csv': 'text/csv',
    'json': 'application/json'
}

# Enhanced logging following LOGGING_SPECIFICATION.md
from enum import Enum
from dataclasses import dataclass, field, asdict
from contextvars import ContextVar
import uuid

# Context variables for request tracking
request_id_context: ContextVar[str] = ContextVar('request_id', default='')
user_id_context: ContextVar[str] = ContextVar('user_id', default='')

class LogLevel(Enum):
    """Standard log levels with numeric values"""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

class LogCategory(Enum):
    """Log categories for filtering and routing"""
    SYSTEM = "system"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    USER_ACTION = "user_action"
    DATA_PROCESSING = "data_processing"
    API = "api"
    INTEGRATION = "integration"
    INGESTION = "ingestion"

@dataclass
class LogEntry:
    """Structured log entry format"""
    timestamp: str
    level: str
    category: str
    message: str
    component: str
    operation: str = ""
    operation_id: Optional[str] = None

    # Context information
    context: Dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    duration_ms: Optional[float] = None

    # Error information
    error_type: Optional[str] = None
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None

    # Business metrics
    items_processed: Optional[int] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # User-friendly information
    user_message: Optional[str] = None

    def to_json(self) -> str:
        """Convert to JSON string for structured logging"""
        return json.dumps(asdict(self), default=str, separators=(',', ':'))

class EnhancedLogger:
    """Enhanced logger with structured logging and context management"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self.operation_timers: Dict[str, float] = {}

    def _create_log_entry(
        self,
        level: str,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        operation: str = "",
        **kwargs
    ) -> LogEntry:
        """Create structured log entry with context"""

        # Get context from context variables
        context = {
            "request_id": request_id_context.get(),
            "user_id": user_id_context.get(),
            "component": self.name,
            "operation": operation
        }

        # Add any additional context from kwargs
        context.update(kwargs.get('context', {}))

        # Filter out parameters that aren't LogEntry fields
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['context', 'exception', 'category', 'user_message']}

        return LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            category=category.value,
            message=message,
            component=self.name,
            operation=operation,
            context=context,
            **filtered_kwargs
        )

    def info(self, message: str, **kwargs):
        """Log info level message"""
        entry = self._create_log_entry("INFO", message, **kwargs)
        self.logger.info(entry.to_json())

    def warning(self, message: str, **kwargs):
        """Log warning level message"""
        entry = self._create_log_entry("WARNING", message, **kwargs)
        self.logger.warning(entry.to_json())

    def error(self, message: str, **kwargs):
        """Log error level message"""
        entry = self._create_log_entry("ERROR", message, **kwargs)

        # Add stack trace if exception is available
        if 'exception' in kwargs:
            entry.stack_trace = traceback.format_exc()
            entry.error_type = type(kwargs['exception']).__name__

        self.logger.error(entry.to_json())

    def start_operation(self, operation_name: str, **kwargs) -> str:
        """Start timing an operation"""
        operation_id = f"{operation_name}_{uuid.uuid4().hex[:8]}"
        self.operation_timers[operation_id] = datetime.now(timezone.utc).timestamp()

        # Filter out category and user_message from kwargs to avoid conflicts
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['category', 'user_message']}

        self.info(
            f"Starting operation: {operation_name}",
            category=LogCategory.PERFORMANCE,
            operation=operation_name,
            operation_id=operation_id,
            user_message=f"Starting {operation_name}...",
            **filtered_kwargs
        )

        return operation_id

    def end_operation(
        self,
        operation_id: str,
        operation_name: str,
        success: bool = True,
        items_processed: int = None,
        **kwargs
    ):
        """End timing an operation"""
        if operation_id not in self.operation_timers:
            self.warning(f"Operation timer not found: {operation_id}")
            return

        start_time = self.operation_timers.pop(operation_id)
        duration_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000

        status_msg = "completed" if success else "failed"

        # Filter out category and user_message from kwargs to avoid conflicts
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['category', 'user_message']}

        log_method = self.info if success else self.error
        log_method(
            f"Operation {status_msg}: {operation_name}",
            category=LogCategory.PERFORMANCE,
            operation=operation_name,
            operation_id=operation_id,
            duration_ms=duration_ms,
            items_processed=items_processed,
            user_message=f"{operation_name} {status_msg}" + (f" ({items_processed} items)" if items_processed else ""),
            **filtered_kwargs
        )

# Initialize enhanced logger
logger = EnhancedLogger("documents_api")

router = APIRouter(prefix="/v1/documents", tags=["documents"])

# Response models
class DocumentUploadResponse(BaseModel):
    """Response model for document upload"""
    upload_id: str
    files: List[Dict[str, Any]]
    total_files: int
    estimated_processing_time: str
    message: str

class DocumentListResponse(BaseModel):
    """Response model for document listing"""
    documents: List[DocumentInfo]
    total: int
    offset: int
    limit: int

# Services will be initialized lazily to avoid SessionLocal being None
document_processor = None
vector_service = None

def get_document_processor():
    """Get document processor instance with lazy initialization"""
    global document_processor
    if document_processor is None:
        document_processor = DocumentProcessor()
    return document_processor

def get_vector_service():
    """Get vector service instance with lazy initialization"""
    global vector_service
    if vector_service is None:
        vector_service = VectorService()
    return vector_service


class DocumentUploadResponse(BaseModel):
    """Response model for document upload"""
    upload_id: str
    files: List[dict]
    total_files: int
    estimated_processing_time: str
    message: str


class DocumentListResponse(BaseModel):
    """Response model for document listing"""
    documents: List[DocumentInfo]
    total: int
    offset: int
    limit: int


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    request: Request,
    files: List[UploadFile] = File(..., description="Documents to upload (PDF, DOCX, TXT, etc.)"),
    workspace_id: Optional[int] = Form(None, description="Optional workspace ID for native RAG ingestion"),
    knowledge_base_id: Optional[int] = Form(None, description="Optional knowledge base ID for native RAG ingestion"),
    source_id: Optional[str] = Form(None, description="Associate with specific data source"),
    company_hr_dataset: Optional[str] = Form(None, description="Company to associate documents with (defaults to system setting)"),
    chunking_strategy: ChunkingStrategy = Form(ChunkingStrategy.SEMANTIC, description="Chunking strategy to use"),
    chunk_size: int = Form(1024, description="Target chunk size in characters"),
    chunk_overlap: int = Form(128, description="Overlap between chunks in characters"),
    similarity_threshold: float = Form(0.85, description="Similarity threshold for semantic chunking"),
    enable_qa_rag: bool = Form(False, description="Enable QA RAG processing"),
    metadata: Optional[str] = Form(None, description="JSON string with additional metadata"),
    current_user: CurrentUserContext = Depends(require_permission('assistant:documents:upload')),
    customer_id: str = Depends(get_current_customer_id),
    db: Session = Depends(get_db)
):
    """
    Upload documents for processing.

    Supports multiple file formats: PDF, DOCX, TXT, MD, CSV, JSON, etc.
    Files are processed asynchronously with configurable chunking strategies.
    Documents are associated with a company (defaults to system default if not specified).
    """

    # Set request context for logging
    request_id = str(uuid.uuid4())
    request_id_context.set(request_id)
    user_id_context.set(str(current_user.user_id))

    # Start operation logging
    operation_id = logger.start_operation(
        "document_upload",
        category=LogCategory.INGESTION,
        metadata={
            "file_count": len(files) if files else 0,
            "chunking_strategy": chunking_strategy.value if chunking_strategy else "semantic",
            "enable_qa_rag": enable_qa_rag
        },
        user_message=f"Uploading {len(files) if files else 0} documents"
    )

    try:
        # Validate files
        if not files:
            logger.error(
                "Upload validation failed: No files provided",
                category=LogCategory.API,
                operation="document_upload",
                error_code="NO_FILES_PROVIDED",
                user_message="No files were selected for upload"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files provided"
            )

        if len(files) > 10:  # Limit batch size
            logger.error(
                f"Upload validation failed: Too many files ({len(files)})",
                category=LogCategory.API,
                operation="document_upload",
                error_code="TOO_MANY_FILES",
                metadata={"file_count": len(files), "max_allowed": 10},
                user_message="Too many files selected. Maximum 10 files per upload."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 10 files per upload batch"
            )

        # Log file validation
        logger.info(
            f"Validating {len(files)} files for upload",
            category=LogCategory.INGESTION,
            operation="file_validation",
            metadata={"file_names": [f.filename for f in files]},
            user_message="Validating uploaded files..."
        )

        # Parse metadata if provided
        parsed_metadata = {}
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
                logger.info(
                    "Parsed upload metadata",
                    category=LogCategory.INGESTION,
                    operation="metadata_parsing",
                    metadata={"metadata_keys": list(parsed_metadata.keys())}
                )
            except json.JSONDecodeError as e:
                logger.error(
                    "Invalid JSON in metadata field",
                    category=LogCategory.API,
                    operation="metadata_parsing",
                    error_code="INVALID_JSON",
                    exception=e,
                    user_message="Invalid metadata format provided"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON in metadata field"
                )

        # Get company for document association
        # Use the user's tenant (customer_id) - with multi-tenancy, documents 
        # are always associated with the tenant that uploaded them
        if not company_hr_dataset:
            # Default to the user's customer_id (their tenant)
            company_hr_dataset = customer_id
            logger.info(
                f"Using user's tenant for document upload: {company_hr_dataset}",
                category=LogCategory.INGESTION,
                operation="company_selection",
                metadata={"company_hr_dataset": company_hr_dataset, "tenant_default": True}
            )
        else:
            logger.info(
                f"Using specified company for document upload: {company_hr_dataset}",
                category=LogCategory.INGESTION,
                operation="company_selection",
                metadata={"company_hr_dataset": company_hr_dataset, "tenant_default": False}
            )

        # Optional convergence path: route generic uploads into workspace/KB-native ingestion.
        if workspace_id is not None:
            logger.info(
                "Routing generic upload through workspace-native ingestion",
                category=LogCategory.INGESTION,
                operation="workspace_ingestion_route",
                metadata={
                    "workspace_id": workspace_id,
                    "knowledge_base_id": knowledge_base_id,
                    "file_count": len(files),
                },
            )

            rag_service = NativeRAGService(db)
            file_results = []
            successful_uploads = 0
            total_size = 0

            for file in files:
                try:
                    file_content = await file.read()
                    file_size = len(file_content)
                    total_size += file_size
                    uploaded_doc = await rag_service.upload_domain_document(
                        domain_id=workspace_id,
                        customer_id=current_user.customer_id,
                        file_content=file_content,
                        filename=file.filename or "document",
                        file_size=file_size,
                        mime_type=file.content_type or "application/octet-stream",
                        user_id=current_user.user_id,
                        knowledge_base_id=knowledge_base_id,
                    )
                    successful_uploads += 1
                    file_results.append(
                        {
                            "filename": file.filename,
                            "status": "uploaded",
                            "document_id": uploaded_doc.id,
                            "file_size": file_size,
                            "mime_type": file.content_type,
                            "knowledge_base_id": uploaded_doc.knowledge_base_id,
                        }
                    )
                except NativeRAGError as rag_error:
                    file_results.append(
                        {
                            "filename": file.filename,
                            "status": "failed",
                            "error": str(rag_error),
                        }
                    )
                except Exception as file_error:
                    file_results.append(
                        {
                            "filename": file.filename,
                            "status": "failed",
                            "error": str(file_error),
                        }
                    )

            upload_id = f"workspace-{workspace_id}-{uuid.uuid4().hex[:8]}"
            estimated_time = f"{successful_uploads * 30} seconds"
            response = DocumentUploadResponse(
                upload_id=upload_id,
                files=file_results,
                total_files=len(files),
                estimated_processing_time=estimated_time,
                message=(
                    f"Workspace ingestion started. "
                    f"{successful_uploads}/{len(files)} files accepted for processing."
                ),
            )
            logger.end_operation(
                operation_id,
                "document_upload",
                success=successful_uploads > 0,
                items_processed=successful_uploads,
                category=LogCategory.INGESTION,
                metadata={
                    "workspace_id": workspace_id,
                    "knowledge_base_id": knowledge_base_id,
                    "successful_uploads": successful_uploads,
                    "total_files": len(files),
                    "total_size_bytes": total_size,
                    "ingestion_mode": "workspace_native",
                },
                user_message=(
                    f"Workspace upload completed: {successful_uploads}/{len(files)} files processed"
                ),
            )
            return response

        # Create upload request
        upload_request = DocumentUploadRequest(
            source_id=source_id,
            company_hr_dataset=company_hr_dataset,
            chunking_strategy=chunking_strategy,
            chunking_config={
                'chunk_size': chunk_size,
                'chunk_overlap': chunk_overlap,
                'similarity_threshold': similarity_threshold
            },
            enable_qa_rag=enable_qa_rag,
            metadata=parsed_metadata
        )

        # Create upload batch
        logger.info(
            "Creating upload batch",
            category=LogCategory.INGESTION,
            operation="batch_creation",
            user_message="Preparing files for processing..."
        )

        batch_id = await get_document_processor().create_upload_batch(customer_id, upload_request)

        # Process files
        file_results = []
        successful_uploads = 0
        total_size = 0

        for i, file in enumerate(files):
            file_operation_id = logger.start_operation(
                "file_processing",
                category=LogCategory.DATA_PROCESSING,
                metadata={
                    "filename": file.filename,
                    "file_index": i + 1,
                    "total_files": len(files)
                },
                user_message=f"Processing {file.filename} ({i + 1}/{len(files)})"
            )

            try:
                # Read file content
                file_content = await file.read()
                file_size = len(file_content)
                total_size += file_size

                logger.info(
                    f"Read file content: {file.filename}",
                    category=LogCategory.DATA_PROCESSING,
                    operation="file_reading",
                    metadata={
                        "filename": file.filename,
                        "file_size": file_size,
                        "mime_type": file.content_type
                    }
                )

                # Process file
                result = await get_document_processor().process_uploaded_file(
                    file_content, file.filename, customer_id, batch_id, upload_request
                )

                file_result = {
                    "filename": file.filename,
                    "status": "uploaded" if result['success'] else "failed",
                    "document_id": result.get('document_id'),
                    "file_size": result.get('file_size'),
                    "mime_type": result.get('mime_type'),
                    "error": result.get('error')
                }

                file_results.append(file_result)

                if result['success']:
                    successful_uploads += 1
                    logger.end_operation(
                        file_operation_id,
                        "file_processing",
                        success=True,
                        category=LogCategory.DATA_PROCESSING,
                        metadata={"document_id": result.get('document_id')},
                        user_message=f"Successfully processed {file.filename}"
                    )
                else:
                    logger.end_operation(
                        file_operation_id,
                        "file_processing",
                        success=False,
                        category=LogCategory.DATA_PROCESSING,
                        metadata={"error": result.get('error')},
                        user_message=f"Failed to process {file.filename}: {result.get('error', 'Unknown error')}"
                    )

            except ValueError as val_error:
                # Validation errors (like duplicate filenames) should return HTTP 422
                logger.end_operation(
                    file_operation_id,
                    "file_processing",
                    success=False,
                    category=LogCategory.DATA_PROCESSING,
                    exception=val_error,
                    user_message=f"Validation error for {file.filename}"
                )
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(val_error)
                )
            except Exception as file_error:
                logger.end_operation(
                    file_operation_id,
                    "file_processing",
                    success=False,
                    category=LogCategory.DATA_PROCESSING,
                    exception=file_error,
                    user_message=f"Error processing {file.filename}"
                )

                file_results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": str(file_error)
                })

        # Estimate processing time (rough estimate: 30 seconds per file)
        estimated_time = f"{successful_uploads * 30} seconds"

        response = DocumentUploadResponse(
            upload_id=batch_id,
            files=file_results,
            total_files=len(files),
            estimated_processing_time=estimated_time,
            message=f"Upload started successfully. {successful_uploads}/{len(files)} files accepted for processing."
        )

        # End operation logging
        logger.end_operation(
            operation_id,
            "document_upload",
            success=True,
            items_processed=successful_uploads,
            category=LogCategory.INGESTION,
            metadata={
                "batch_id": batch_id,
                "successful_uploads": successful_uploads,
                "total_files": len(files),
                "total_size_bytes": total_size
            },
            user_message=f"Upload completed: {successful_uploads}/{len(files)} files processed successfully"
        )

        return response

    except HTTPException as http_error:
        logger.end_operation(
            operation_id,
            "document_upload",
            success=False,
            category=LogCategory.API,
            metadata={"http_status": http_error.status_code, "detail": http_error.detail},
            user_message=f"Upload failed: {http_error.detail}"
        )
        raise
    except Exception as e:
        logger.end_operation(
            operation_id,
            "document_upload",
            success=False,
            category=LogCategory.INGESTION,
            exception=e,
            user_message="Upload failed due to an unexpected error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/upload/{upload_id}/status", response_model=UploadBatchInfo)
async def get_upload_status(
    upload_id: str,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Get the status of a document upload batch."""
    
    batch_info = await get_document_processor().get_upload_batch_status(upload_id)
    
    if not batch_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload batch not found"
        )
    
    # Verify customer access
    if batch_info.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return batch_info


@router.get(
    "/upload/{upload_id}/stream",
    summary="Stream upload progress",
    description="Stream real-time upload and processing status using Server-Sent Events (SSE)."
)
async def stream_upload_status(
    request: Request,
    upload_id: str,
    token: str = Query(..., description="JWT access token (EventSource doesn't support headers)")
):
    """
    Stream real-time upload progress for a batch.
    
    This endpoint streams real-time updates about document upload and processing progress.
    
    Note: Token is passed as query param because EventSource doesn't support custom headers.
    """
    from fastapi.responses import StreamingResponse
    from src.services.auth_service import AuthService
    import asyncio
    
    auth_service = AuthService(None)  # Will be instantiated properly inside
    
    # Verify token and get user (EventSource can't send Authorization header)
    try:
        payload = await auth_service.verify_token(token)
        user_id = int(payload.get("sub"))
        user = await auth_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found"
            )
        
        customer_id = user.customer_id
        
    except Exception as e:
        logger.error(f"SSE auth failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication failed"
        )
    
    # Get initial batch info and verify access
    batch_info = await get_document_processor().get_upload_batch_status(upload_id)
    
    if not batch_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload batch not found"
        )
    
    if batch_info.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    async def event_generator():
        """Generate SSE events from upload batch status."""
        poll_interval = 1  # Check every 1 second
        idle_cycles = 0
        heartbeat_interval = 15  # Send heartbeat every 15 seconds if idle
        
        while True:
            if await request.is_disconnected():
                logger.debug(f"SSE client disconnected for upload {upload_id}")
                break
            
            # Get current batch status
            current_batch = await get_document_processor().get_upload_batch_status(upload_id)
            
            if current_batch:
                # Calculate progress percentage
                total = current_batch.total_files
                processed = current_batch.completed_files + current_batch.failed_files
                progress = (processed / total * 100) if total > 0 else 0
                
                # Send status update
                status_event = {
                    "event_id": f"status-{uuid.uuid4().hex}",
                    "event_type": "status_update",
                    "upload_id": upload_id,
                    "status": current_batch.status,
                    "total_files": current_batch.total_files,
                    "completed_files": current_batch.completed_files,
                    "failed_files": current_batch.failed_files,
                    "progress_percentage": round(progress, 1),
                    "total_chunks_created": current_batch.total_chunks_created,
                    "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                }
                
                yield f"data: {json.dumps(status_event)}\n\n"
                idle_cycles = 0
                
                # Check if processing is complete
                if current_batch.status == "completed":
                    completion_event = {
                        "event_id": f"terminal-{uuid.uuid4().hex}",
                        "event_type": "completed",
                        "upload_id": upload_id,
                        "message": f"Processing completed: {current_batch.completed_files} files processed successfully",
                        "total_chunks": current_batch.total_chunks_created,
                        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(completion_event)}\n\n"
                    break
                
                elif current_batch.status == "failed":
                    failure_event = {
                        "event_id": f"terminal-{uuid.uuid4().hex}",
                        "event_type": "failed",
                        "upload_id": upload_id,
                        "message": f"Processing failed: {current_batch.failed_files} files failed",
                        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(failure_event)}\n\n"
                    break
            else:
                # Batch not found - might have been deleted
                error_event = {
                    "event_id": f"terminal-{uuid.uuid4().hex}",
                    "event_type": "error",
                    "message": "Upload batch not found",
                    "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                break
            
            # Send heartbeat if idle
            idle_cycles += 1
            if idle_cycles >= heartbeat_interval:
                heartbeat_event = {
                    "event_id": f"heartbeat-{uuid.uuid4().hex}",
                    "event_type": "heartbeat",
                    "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                }
                yield f"data: {json.dumps(heartbeat_event)}\n\n"
                idle_cycles = 0
            
            await asyncio.sleep(poll_interval)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    source_id: Optional[str] = None,
    status: Optional[DocumentStatus] = None,
    company_hr_dataset: Optional[str] = Query(None, description="Filter by company"),
    created_after: Optional[datetime] = Query(None, description="Filter documents created after this date (ISO 8601)"),
    created_before: Optional[datetime] = Query(None, description="Filter documents created before this date (ISO 8601)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of documents to return"),
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    sort: str = Query("-created_at", description="Sort field (prefix with - for descending)"),
    current_user: CurrentUserContext = Depends(require_permission('assistant:documents:read'))
):
    """
    List uploaded documents with flexible filtering.
    
    Supports filtering by:
    - source_id: Filter by data source
    - status: Filter by processing status (uploaded, processing, completed, failed)
    - company_hr_dataset: Filter by associated company
    - created_after: Only documents created after this timestamp
    - created_before: Only documents created before this timestamp
    - sort: Sort by field (e.g., 'created_at', '-created_at', 'filename')
    
    Use this endpoint for both full document lists and recent uploads by
    specifying appropriate date filters and limits.
    """
    
    if limit > 100:
        limit = 100
    
    documents = await get_document_processor().list_documents(
        customer_id=current_user.customer_id,
        source_id=source_id,
        status=status,
        limit=limit,
        offset=offset
    )
    
    # Apply company filter if specified
    if company_hr_dataset:
        documents = [doc for doc in documents if doc.company_hr_dataset == company_hr_dataset]
    
    # Apply date filters if specified
    if created_after or created_before:
        filtered_docs = []
        for doc in documents:
            doc_created = doc.created_at
            if doc_created:
                # Handle timezone-aware comparison
                if doc_created.tzinfo is None:
                    from datetime import timezone as tz
                    doc_created = doc_created.replace(tzinfo=tz.utc)
                
                if created_after and doc_created < created_after:
                    continue
                if created_before and doc_created > created_before:
                    continue
                filtered_docs.append(doc)
        documents = filtered_docs
    
    # Apply sorting
    reverse_sort = sort.startswith('-')
    sort_field = sort.lstrip('-')
    
    if sort_field in ['created_at', 'filename', 'file_size', 'original_filename']:
        try:
            documents = sorted(
                documents,
                key=lambda x: getattr(x, sort_field, ''),
                reverse=reverse_sort
            )
        except (AttributeError, TypeError):
            pass  # If sorting fails, return unsorted
    
    # Get total count (simplified - in production, you'd want a separate count query)
    total = len(documents)  # This is approximate
    
    return DocumentListResponse(
        documents=documents,
        total=total,
        offset=offset,
        limit=limit
    )


# Health check endpoint for document processing
@router.get("/health")
async def document_service_health():
    """Health check for document processing service."""

    try:
        # Get services using lazy initialization
        processor = get_document_processor()
        vector_svc = get_vector_service()
        
        processor_healthy = processor is not None
        vector_healthy = vector_svc is not None

        # Check vector service stats
        vector_stats = await vector_svc.get_index_stats()

        return {
            "status": "healthy" if (processor_healthy and vector_healthy) else "unhealthy",
            "document_processor": {
                "status": "healthy" if processor_healthy else "unhealthy"
            },
            "vector_service": {
                "status": "healthy" if vector_healthy else "unhealthy",
                "stats": vector_stats
            },
            "vector_index_stats": vector_stats  # Keep for backward compatibility
        }

    except Exception as e:
        logger.error(f"Document service health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/stats", response_model=DocumentStatsResponse)
async def get_document_stats(
    range: str = "7d",
    current_user: CurrentUserContext = Depends(get_current_user)
) -> DocumentStatsResponse:
    """
    Get document statistics for the specified time range.
    
    Returns comprehensive document metrics including:
    - Total document counts
    - Documents by status (processing, completed, failed)
    - Total chunks created
    - Storage usage in megabytes
    
    Time range options: 24h, 7d, 30d (default: 7d)
    """

    # Set request context for logging
    request_id = str(uuid.uuid4())
    request_id_context.set(request_id)
    user_id_context.set(str(current_user.user_id))

    operation_id = logger.start_operation(
        "get_document_stats",
        category=LogCategory.API,
        metadata={"range": range},
        user_message=f"Fetching document statistics for {range}"
    )

    try:
        # Parse time range
        if range == "24h":
            hours = 24
        elif range == "7d":
            hours = 24 * 7
        elif range == "30d":
            hours = 24 * 30
        else:
            hours = 24 * 7  # Default to 7 days

        # Get document processor
        processor = get_document_processor()

        # Get all documents for this customer to calculate stats
        all_documents = await processor.list_documents(
            customer_id=current_user.customer_id,
            limit=1000  # Get a large number to calculate stats
        )

        # Calculate statistics from actual documents
        total_documents = len(all_documents)
        processing = len([d for d in all_documents if d.status == 'processing'])
        completed = len([d for d in all_documents if d.status == 'completed'])
        failed = len([d for d in all_documents if d.status == 'failed'])

        # Calculate total chunks and storage
        total_chunks = sum(getattr(d, 'total_chunks', 0) for d in all_documents)
        storage_used_bytes = sum(getattr(d, 'file_size', 0) for d in all_documents)

        stats = {
            "total_documents": total_documents,
            "processing_documents": processing,
            "completed_documents": completed,
            "failed_documents": failed,
            "total_chunks": total_chunks,
            "storage_used_mb": storage_used_bytes / (1024 * 1024),  # Convert to MB
            "range": range
        }

        logger.end_operation(
            operation_id,
            "get_document_stats",
            success=True,
            category=LogCategory.API,
            metadata=stats,
            user_message="Document statistics retrieved successfully"
        )

        return DocumentStatsResponse(**stats)

    except Exception as e:
        logger.end_operation(
            operation_id,
            "get_document_stats",
            success=False,
            category=LogCategory.API,
            exception=e,
            user_message="Failed to retrieve document statistics"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get("/recent", response_model=RecentDocumentsResponse, deprecated=True)
async def get_recent_documents(
    limit: int = 5,
    current_user: CurrentUserContext = Depends(get_current_user)
) -> RecentDocumentsResponse:
    """
    **DEPRECATED:** Use GET /v1/documents with date filtering instead.
    
    This endpoint is maintained for backward compatibility but will be removed in a future version.
    
    **Recommended alternative:**
    ```
    GET /v1/documents?created_after=<24h_ago>&limit=5&sort=-created_at
    ```
    
    Get recently uploaded documents (last 24 hours).
    
    Returns a list of recently uploaded documents with:
    - Document ID and filename
    - Processing status
    - Upload timestamp
    - Chunk count and file size
    
    Max limit: 50 documents
    """

    # Set request context for logging
    request_id = str(uuid.uuid4())
    request_id_context.set(request_id)
    user_id_context.set(str(current_user.user_id))

    operation_id = logger.start_operation(
        "get_recent_documents",
        category=LogCategory.API,
        metadata={"limit": limit},
        user_message=f"Fetching {limit} recent documents"
    )

    try:
        if limit > 50:
            limit = 50  # Cap at 50 documents

        # Get document processor
        processor = get_document_processor()

        # Get recent documents using the same method as list_documents
        all_documents = await processor.list_documents(
            customer_id=current_user.customer_id,
            limit=1000  # Get more to filter by date
        )

        # Filter to last 24 hours
        from datetime import datetime, timedelta, timezone
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        recent_documents = []
        for doc in all_documents:
            created_at = doc.created_at
            if created_at:
                try:
                    # Handle both timezone-aware and naive datetimes
                    if created_at.tzinfo is None:
                        # Make naive datetime timezone-aware (assume UTC)
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    
                    if created_at >= cutoff_time:
                        recent_documents.append(doc)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error comparing created_at for doc {doc.id}: {e}")
                    continue
        
        # Sort by created_at descending and take the most recent
        documents = sorted(
            recent_documents,
            key=lambda x: getattr(x, 'created_at', ''),
            reverse=True
        )[:limit]

        logger.end_operation(
            operation_id,
            "get_recent_documents",
            success=True,
            items_processed=len(documents),
            category=LogCategory.API,
            user_message=f"Retrieved {len(documents)} recent documents"
        )

        return RecentDocumentsResponse(
            documents=[
                RecentDocumentInfo(
                    id=doc.id,
                    original_filename=doc.original_filename,
                    status=doc.status,
                    created_at=doc.created_at,
                    total_chunks=doc.total_chunks,
                    file_size_bytes=doc.file_size,
                    company_hr_dataset=doc.company_hr_dataset
                )
                for doc in documents
            ],
            total=len(documents),
            limit=limit
        )

    except Exception as e:
        logger.end_operation(
            operation_id,
            "get_recent_documents",
            success=False,
            category=LogCategory.API,
            exception=e,
            user_message="Failed to retrieve recent documents"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recent documents: {str(e)}"
        )


@router.get("/{document_id}", response_model=DocumentInfo)
async def get_document(
    document_id: int,
    current_user: CurrentUserContext = Depends(require_permission('assistant:documents:read'))
):
    """Get detailed information about a specific document."""

    document = await get_document_processor().get_document_info(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Verify customer access
    if document.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return document


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: CurrentUserContext = Depends(require_permission('assistant:documents:read'))
):
    """Download the original document file."""

    document = await get_document_processor().get_document_info(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Verify customer access
    if document.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Check if document is deleted
    if document.status == DocumentStatus.DELETED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Document has been deleted"
        )

    # Get the file path from the database using proper service layer session management
    from pathlib import Path
    from src.models.document import Document
    from src.services.base_service import get_service_db_session

    with get_service_db_session() as db:
        db_document = db.query(Document).filter(Document.id == document_id).first()
        if not db_document or not db_document.file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file path not found"
            )

        file_path = Path(db_document.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file not found on disk"
            )

    # Map simplified type back to proper MIME type for Content-Type header
    mime_type = SIMPLIFIED_TO_MIME_TYPE.get(document.mime_type, document.mime_type)
    
    return FileResponse(
        path=str(file_path),
        filename=document.original_filename,
        media_type=mime_type
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: CurrentUserContext = Depends(require_permission('assistant:documents:delete'))
):
    """Delete a document and its associated chunks."""
    
    success = await get_document_processor().delete_document(document_id, current_user.customer_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied"
        )
    
    # Remove from vector index
    await get_vector_service().remove_document_from_index(document_id)
    
    return {"message": "Document deleted successfully"}


@router.post("/{document_id}/retry")
async def retry_document_processing(
    document_id: int,
    current_user: CurrentUserContext = Depends(require_permission('assistant:documents:upload'))
):
    """Retry processing a failed document."""
    
    from src.models.document import Document
    from src.services.base_service import get_service_db_session
    
    with get_service_db_session() as db:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.customer_id == current_user.customer_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or access denied"
            )
        
        # Only allow retry for failed documents
        if document.status != DocumentStatus.FAILED:
            # document.status might be a string or enum, handle both cases
            status_str = document.status.value if hasattr(document.status, 'value') else str(document.status)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document is not in failed status (current status: {status_str})"
            )
        
        # Reset document status to uploaded (task will handle the rest)
        document.status = DocumentStatus.UPLOADED
        document.processing_error = None
        document.processing_started_at = None
        document.processing_completed_at = None
        db.commit()
    
    # Enqueue Celery task for reprocessing
    from src.tasks.documents import retry_failed_document_task
    task_result = retry_failed_document_task.delay(document_id)
    
    return {
        "message": "Document reprocessing started",
        "document_id": document_id,
        "task_id": task_result.id
    }


@router.post("/search", response_model=List[DocumentSearchResult])
async def search_documents(
    search_request: DocumentSearchRequest,
    current_user: CurrentUserContext = Depends(require_permission('assistant:documents:read'))
):
    """
    Search documents using vector similarity.
    
    Performs semantic search across all document chunks using embeddings.
    """
    
    try:
        results = await get_vector_service().search_similar_chunks(
            query=search_request.query,
            limit=search_request.limit,
            similarity_threshold=search_request.similarity_threshold,
            customer_id=current_user.customer_id,
            source_ids=search_request.source_ids,
            document_ids=search_request.document_ids
        )
        
        # Filter QA pairs if not requested
        if not search_request.include_qa_pairs:
            for result in results:
                result.qa_questions = None
                result.qa_answers = None
        
        return results
        
    except Exception as e:
        logger.error(f"Document search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/stats/index")
async def get_index_stats(
    current_user: CurrentUserContext = Depends(require_permission('assistant:documents:read'))
):
    """Get statistics about the vector index."""
    
    stats = await get_vector_service().get_index_stats()
    return stats


@router.post("/admin/rebuild-index")
async def rebuild_index(
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Rebuild the vector index from existing chunks.
    
    This is an admin operation that recreates the FAISS index
    from all chunks in the database.
    """
    
    try:
        result = await get_vector_service().rebuild_index(current_user.customer_id)
        
        if result['success']:
            return {
                "message": "Index rebuild completed successfully",
                "stats": result
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Index rebuild failed')
            )
            
    except Exception as e:
        logger.error(f"Index rebuild failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index rebuild failed: {str(e)}"
        )


