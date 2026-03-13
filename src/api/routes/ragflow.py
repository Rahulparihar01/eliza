"""
Native RAG API Routes - Multi-tenant RAG chat service.

Provides endpoints for:
- Domain (knowledge base) management
- Document upload and processing
- RAG retrieval
- Chat with documents

Uses native Python libraries (docling, OpenAI embeddings, Elasticsearch)
instead of external RAGFlow service.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Form, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.ragflow_domain import (
    RAGFlowDomain, RAGFlowDocument, RAGFlowConversation,
    RAGFlowDomainStatus, RAGFlowDocumentStatus, RAGFlowParserType
)
from src.models.workspace import WorkspaceTemplate, KnowledgeBasePermissionType
from src.api.schemas.ragflow import (
    CreateDomainRequest, UpdateDomainRequest, DomainResponse, DomainListResponse, DomainStatsResponse,
    DocumentUploadResponse, DocumentResponse, DocumentListResponse,
    RetrievalRequest, RetrievalResponse, RetrievedChunk,
    CreateConversationRequest, ConversationResponse, ConversationListResponse,
    MessageResponse, SendMessageRequest, ChatResponse, ConversationWithMessagesResponse,
    RAGFlowHealthResponse
)
# Use native RAG service instead of external RAGFlow
from src.services.native_rag_service import NativeRAGService as RAGFlowService, NativeRAGError as RAGFlowError
from src.middleware.authorization import require_permission
from src.core.auth_context import CurrentUserContext
from src.core.config import get_settings
from src.services.auth_service import AuthService
from src.services.langfuse_service import get_langfuse_service
from src.models.workspace import KnowledgeBase
from src.services.knowledge_base_access_service import KnowledgeBaseAccessService
from src.services.retrieval.agent_mesh_progress_stream import get_agent_mesh_progress_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ragflow", tags=["RAG Chat Service (Native)"])


def get_ragflow_service(db: Session = Depends(get_db)) -> RAGFlowService:
    """Get RAGFlow service instance."""
    return RAGFlowService(db)


def _is_fasb_workspace(domain: RAGFlowDomain) -> bool:
    """
    Detect FASB-backed workspace routing.

    Supports legacy `name == "fasb"` and config-driven routing via
    `workspace_config.backend_type == "opensearch_fasb"`.
    """
    workspace_config = domain.workspace_config if isinstance(domain.workspace_config, dict) else {}
    backend_type = str(workspace_config.get("backend_type") or "").strip().lower()
    domain_name = str(domain.name or "").strip().lower()
    opensearch_index = str(workspace_config.get("opensearch_index") or "").strip().lower()

    return (
        domain_name == "fasb"
        or backend_type == "opensearch_fasb"
        or opensearch_index.startswith("fasb")
    )


def _is_agent_mesh_workspace(domain: RAGFlowDomain, db: Session) -> bool:
    """Detect Agent Mesh workspace routing."""
    workspace_config = domain.workspace_config if isinstance(domain.workspace_config, dict) else {}
    backend_type = str(workspace_config.get("backend_type") or "").strip().lower()
    domain_name = str(domain.name or "").strip().lower()

    template_name = ""
    if domain.template_id:
        template_name = (
            db.query(WorkspaceTemplate.name)
            .filter(WorkspaceTemplate.id == domain.template_id)
            .scalar()
            or ""
        )
        template_name = str(template_name).strip().lower()

    return (
        template_name == "agent_mesh_retrieval"
        or backend_type in {"agent_mesh", "agent_mesh_retrieval"}
        or domain_name in {"agent_mesh", "agentmesh"}
    )


def _normalize_stream_request_id(raw_request_id: Optional[str]) -> Optional[str]:
    """Normalize optional request_id for Agent Mesh live stream correlation."""
    if raw_request_id is None:
        return None
    request_id = str(raw_request_id).strip()
    if not request_id:
        return None
    return request_id[:128]


def _normalize_fasb_source_filter(value: Optional[str]) -> Optional[str]:
    """Normalize optional FASB source filter value."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"all", "primary", "memo"}:
        return normalized
    return None


def _get_fasb_source_filter(
    domain: RAGFlowDomain,
    request_filter: Optional[str] = None,
) -> Optional[str]:
    """
    Resolve effective FASB source filter.

    Precedence:
    1) Explicit request filter
    2) Workspace config (`fasb_source_filter` / `source_filter`)
    3) None (service default: all configured sources)
    """
    explicit = _normalize_fasb_source_filter(request_filter)
    if explicit:
        return explicit

    workspace_config = domain.workspace_config if isinstance(domain.workspace_config, dict) else {}
    config_filter = workspace_config.get("fasb_source_filter") or workspace_config.get("source_filter")
    return _normalize_fasb_source_filter(config_filter)


def _resolve_knowledge_base_scope_or_raise(
    *,
    db: Session,
    current_user: CurrentUserContext,
    domain_id: int,
    requested_kb_ids: Optional[List[int]],
    required_permission: KnowledgeBasePermissionType = KnowledgeBasePermissionType.READ,
) -> List[int]:
    """Resolve effective KB IDs for workspace-scoped operations."""
    access_service = KnowledgeBaseAccessService(db)
    try:
        return access_service.resolve_effective_kb_scope(
            workspace_id=domain_id,
            user=current_user,
            requested_kb_ids=requested_kb_ids,
            required_permission=required_permission,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


# ==================== Health Check ====================

@router.get("/health", response_model=RAGFlowHealthResponse)
async def ragflow_health_check(
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Check RAGFlow service health.
    
    Verifies that RAGFlow is reachable and the API key is configured.
    """
    settings = get_settings()
    
    health = await ragflow.health_check()
    
    return RAGFlowHealthResponse(
        status=health.get("status", "unknown"),
        ragflow_reachable=health.get("status") == "healthy",
        api_configured=bool(settings.ragflow_api_key),
        error=health.get("error")
    )


@router.get("/health/fasb")
async def fasb_health_check(response: Response):
    """
    Check FASB service health including OpenSearch and OpenAI connectivity.
    
    Use this endpoint to diagnose FASB workspace issues.
    Returns detailed status of each component (OpenSearch, AWS credentials, OpenAI).
    Returns HTTP 503 if any component is unhealthy.
    """
    try:
        from src.services.fasb_service import get_fasb_service
        fasb_service = get_fasb_service()
        health = fasb_service.health_check()
        
        if health["status"] != "healthy":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return health
        
    except Exception as e:
        logger.error(f"FASB health check failed: {e}", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "error": str(e),
            "components": {}
        }


# ==================== Domain Management ====================

@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def create_domain(
    request: CreateDomainRequest,
    current_user: CurrentUserContext = Depends(require_permission("documents:upload")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Create a new RAG domain (knowledge base).
    
    Creates both a local domain record and a corresponding RAGFlow dataset
    for document storage and retrieval.
    
    **Parser Types:**
    - `naive`: Fast, plain text extraction (default)
    - `deepdoc`: CPU-based OCR and layout recognition
    - `gpt-5.2`: Vision model for complex documents (recommended, best OCR quality)
    - `gpt-4o`: Legacy vision model fallback
    - `docling`: Balanced parser option
    - `custom-vlm`: Custom hosted VLM (OpenAI-compatible)
    """
    # Check if domain name already exists
    existing = await ragflow.get_domain_by_name(request.name, current_user.customer_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Domain '{request.name}' already exists"
        )
    
    try:
        domain = await ragflow.create_domain(
            customer_id=current_user.customer_id,
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            icon=request.icon,
            color=request.color,
            parser_type=RAGFlowParserType(request.parser_type.value),
            embedding_model=request.embedding_model,
            chunk_token_count=request.chunk_token_count,
            task_page_size=request.task_page_size,
            user_id=current_user.user_id,
            custom_vlm_model=request.custom_vlm_model
        )
        
        # Update retrieval settings if provided
        if request.similarity_threshold != 20 or request.top_k != 5:
            domain.similarity_threshold = request.similarity_threshold
            domain.top_k = request.top_k
            ragflow.db.commit()
            ragflow.db.refresh(domain)
        
        return DomainResponse.model_validate(domain)
        
    except RAGFlowError as e:
        logger.error(f"Failed to create domain: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RAGFlow error: {str(e)}"
        )


@router.get("/domains", response_model=DomainListResponse)
async def list_domains(
    status_filter: Optional[RAGFlowDomainStatus] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    List all RAG domains for the current tenant.
    
    Returns domains with document counts and processing status.
    """
    # Map schema enum to model enum if filter provided
    model_status = None
    if status_filter:
        model_status = RAGFlowDomainStatus(status_filter.value) if hasattr(status_filter, 'value') else status_filter
    
    domains = await ragflow.list_domains(
        customer_id=current_user.customer_id,
        status=model_status,
        limit=limit,
        offset=offset,
        sync_stats=False  # Don't sync on every list - blocks event loop
    )
    
    return DomainListResponse(
        domains=[DomainResponse.model_validate(d) for d in domains],
        total=len(domains),  # TODO: Get actual count
        offset=offset,
        limit=limit
    )


@router.get("/domains/by-name/{domain_name}", response_model=DomainResponse)
async def get_domain_by_name(
    domain_name: str,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """Get domain details by name."""
    domain = await ragflow.get_domain_by_name(domain_name, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{domain_name}' not found"
        )
    
    return DomainResponse.model_validate(domain)


@router.get("/domains/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: int,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """Get domain details by ID."""
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    return DomainResponse.model_validate(domain)


@router.patch("/domains/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: int,
    request: UpdateDomainRequest,
    current_user: CurrentUserContext = Depends(require_permission("documents:upload")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """Update domain settings."""
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    # Update fields if provided
    if request.display_name is not None:
        domain.display_name = request.display_name
    if request.description is not None:
        domain.description = request.description
    if request.icon is not None:
        domain.icon = request.icon
    if request.color is not None:
        domain.color = request.color
    if request.parser_type is not None:
        domain.parser_type = RAGFlowParserType(request.parser_type.value)
    if request.similarity_threshold is not None:
        domain.similarity_threshold = request.similarity_threshold
    if request.top_k is not None:
        domain.top_k = request.top_k
    if request.is_active is not None:
        domain.is_active = request.is_active
    
    ragflow.db.commit()
    ragflow.db.refresh(domain)
    
    return DomainResponse.model_validate(domain)


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    domain_id: int,
    current_user: CurrentUserContext = Depends(require_permission("documents:upload")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Delete a domain and all its documents.
    
    This will also delete the corresponding RAGFlow dataset.
    """
    success = await ragflow.delete_domain(domain_id, current_user.customer_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )


@router.get("/domains/{domain_id}/stats", response_model=DomainStatsResponse)
async def get_domain_stats(
    domain_id: int,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """Get domain statistics including document counts by status."""
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    # Count documents by status
    docs = await ragflow.list_domain_documents(domain_id, current_user.customer_id, limit=1000)
    completed = sum(1 for d in docs if d.status == RAGFlowDocumentStatus.COMPLETED)
    pending = sum(1 for d in docs if d.status in [RAGFlowDocumentStatus.PENDING, RAGFlowDocumentStatus.PARSING])
    failed = sum(1 for d in docs if d.status == RAGFlowDocumentStatus.FAILED)
    
    return DomainStatsResponse(
        domain_id=domain_id,
        document_count=domain.document_count,
        chunk_count=domain.chunk_count,
        total_tokens=domain.total_tokens,
        completed_documents=completed,
        pending_documents=pending,
        failed_documents=failed
    )


@router.post("/domains/{domain_id}/sync-stats", response_model=DomainResponse)
async def sync_domain_stats(
    domain_id: int,
    current_user: CurrentUserContext = Depends(require_permission("documents:upload")),
    ragflow: RAGFlowService = Depends(get_ragflow_service),
    db: Session = Depends(get_db)
):
    """
    Sync domain/workspace statistics from external sources.
    
    For FASB workspace, syncs document and chunk counts from AWS OpenSearch.
    For RAGFlow workspaces, syncs from RAGFlow API.
    """
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    # Check if this is the FASB workspace (uses OpenSearch instead of RAGFlow)
    if _is_fasb_workspace(domain):
        try:
            from src.services.fasb_service import get_fasb_service
            fasb_service = get_fasb_service()
            source_filter = _get_fasb_source_filter(domain)
            stats = fasb_service.get_index_stats(source_filter=source_filter)
            
            if "error" not in stats:
                domain.document_count = stats.get("document_count", 0)
                domain.chunk_count = stats.get("chunk_count", 0)
                db.commit()
                db.refresh(domain)
                logger.info(
                    "Synced FASB stats: domain=%s source_filter=%s docs=%s chunks=%s",
                    domain.id,
                    source_filter or "all",
                    domain.document_count,
                    domain.chunk_count,
                )
            else:
                logger.warning(f"Could not sync FASB stats: {stats.get('error')}")
        except Exception as e:
            logger.error(f"Failed to sync FASB stats: {e}")
    elif domain.ragflow_dataset_id:
        # RAGFlow workspaces - stats are synced via list_domains(sync_stats=True)
        try:
            await ragflow.list_domains(current_user.customer_id, sync_stats=True)
            db.refresh(domain)
        except Exception as e:
            logger.error(f"Failed to sync RAGFlow stats: {e}")
    
    return DomainResponse(
        id=domain.id,
        customer_id=domain.customer_id,
        name=domain.name,
        display_name=domain.display_name,
        description=domain.description,
        icon=domain.icon,
        color=domain.color,
        status=domain.status.value,
        parser_type=domain.parser_type.value if domain.parser_type else None,
        embedding_model=domain.embedding_model,
        chunk_token_count=domain.chunk_token_count,
        similarity_threshold=domain.similarity_threshold,
        top_k=domain.top_k,
        document_count=domain.document_count,
        chunk_count=domain.chunk_count,
        total_tokens=domain.total_tokens,
        is_active=domain.is_active,
        ragflow_dataset_id=domain.ragflow_dataset_id,
        created_at=domain.created_at,
        updated_at=domain.updated_at
    )


@router.post("/domains/{domain_id}/parse", response_model=DomainResponse)
async def start_parsing(
    domain_id: int,
    current_user: CurrentUserContext = Depends(require_permission("documents:upload")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Start parsing for pending documents in a domain.
    
    Triggers RAGFlow to begin processing uploaded documents.
    """
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    try:
        domain = await ragflow.start_parsing(domain_id, current_user.customer_id)
        return DomainResponse.model_validate(domain)
        
    except RAGFlowError as e:
        logger.error(f"Failed to start parsing: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RAGFlow error: {str(e)}"
        )


@router.post("/domains/{domain_id}/retry-ingestion")
async def retry_ingestion(
    domain_id: int,
    current_user: CurrentUserContext = Depends(require_permission("documents:upload")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Retry ingestion for failed / stuck documents in a domain.
    
    Resets failed and stuck-parsing documents to pending, then dispatches
    Celery tasks to re-process them from object storage.
    """
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    try:
        result = await ragflow.retry_failed_documents(domain_id, current_user.customer_id)
        return result
        
    except RAGFlowError as e:
        logger.error(f"Failed to retry ingestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RAGFlow error: {str(e)}"
        )


# ==================== Document Management ====================

@router.post("/domains/{domain_id}/documents", response_model=DocumentUploadResponse)
async def upload_document(
    domain_id: int,
    file: UploadFile = File(..., description="Document file (PDF, DOCX, TXT, etc.)"),
    knowledge_base_id: Optional[int] = Form(
        None,
        description="Optional target knowledge base. Defaults to first accessible KB.",
    ),
    current_user: CurrentUserContext = Depends(require_permission("documents:upload")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Upload a document to a RAG domain.
    
    The document will be processed immediately using the domain's parser configuration.
    
    **Supported formats:** PDF, DOCX, TXT, MD, HTML, XLSX, PPTX
    """
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Validate file size (100MB max)
    if file_size > 100 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 100MB limit"
        )

    kb_scope = _resolve_knowledge_base_scope_or_raise(
        db=ragflow.db,
        current_user=current_user,
        domain_id=domain_id,
        requested_kb_ids=[knowledge_base_id] if knowledge_base_id is not None else None,
        required_permission=KnowledgeBasePermissionType.WRITE,
    )
    if not kb_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No writable knowledge base available in this workspace",
        )
    target_kb_id = knowledge_base_id if knowledge_base_id is not None else kb_scope[0]
    logger.info(
        "upload_target_resolved domain_id=%s kb_id=%s user_id=%s",
        domain_id,
        target_kb_id,
        current_user.user_id,
    )
    
    try:
        document = await ragflow.upload_domain_document(
            domain_id=domain_id,
            customer_id=current_user.customer_id,
            file_content=file_content,
            filename=file.filename or "document",
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            user_id=current_user.user_id,
            knowledge_base_id=target_kb_id,
        )
        
        return DocumentUploadResponse.model_validate(document)
        
    except RAGFlowError as e:
        logger.error(f"Failed to upload document: {e}")
        detail = str(e)
        status_code = status.HTTP_502_BAD_GATEWAY
        if "Tenant object storage is not configured" in detail:
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=f"RAGFlow error: {detail}"
        )


@router.get("/domains/{domain_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    domain_id: int,
    status_filter: Optional[RAGFlowDocumentStatus] = Query(None, alias="status"),
    knowledge_base_id: Optional[int] = Query(None, description="Optional knowledge base filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """List documents in a domain."""
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    # Map schema enum to model enum if filter provided
    model_status = None
    if status_filter:
        model_status = RAGFlowDocumentStatus(status_filter.value) if hasattr(status_filter, 'value') else status_filter

    kb_scope = _resolve_knowledge_base_scope_or_raise(
        db=ragflow.db,
        current_user=current_user,
        domain_id=domain_id,
        requested_kb_ids=[knowledge_base_id] if knowledge_base_id is not None else None,
        required_permission=KnowledgeBasePermissionType.READ,
    )
    if not kb_scope:
        return DocumentListResponse(documents=[], total=0, offset=offset, limit=limit)
    
    documents = await ragflow.list_domain_documents(
        domain_id=domain_id,
        customer_id=current_user.customer_id,
        knowledge_base_id=knowledge_base_id if knowledge_base_id is not None else None,
        knowledge_base_ids=None if knowledge_base_id is not None else kb_scope,
        status=model_status,
        limit=limit,
        offset=offset
    )
    
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=len(documents),
        offset=offset,
        limit=limit
    )


@router.get("/domains/{domain_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    domain_id: int,
    document_id: int,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Get document details with current processing status.
    
    Fetches latest status from RAGFlow to show parsing progress.
    """
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    document = await ragflow.get_document_status(document_id, current_user.customer_id)
    
    if not document or document.domain_id != domain_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found in domain {domain_id}"
        )

    if document.knowledge_base_id is not None:
        kb_scope = _resolve_knowledge_base_scope_or_raise(
            db=ragflow.db,
            current_user=current_user,
            domain_id=domain_id,
            requested_kb_ids=[document.knowledge_base_id],
            required_permission=KnowledgeBasePermissionType.READ,
        )
        if not kb_scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this document's knowledge base",
            )
    
    return DocumentResponse.model_validate(document)


@router.delete("/domains/{domain_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    domain_id: int,
    document_id: int,
    current_user: CurrentUserContext = Depends(require_permission("documents:upload")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """Delete a document from a domain."""
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    # Verify document belongs to domain
    doc = ragflow.db.query(RAGFlowDocument).filter(
        RAGFlowDocument.id == document_id,
        RAGFlowDocument.domain_id == domain_id,
        RAGFlowDocument.customer_id == current_user.customer_id
    ).first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )

    if doc.knowledge_base_id is not None:
        kb_scope = _resolve_knowledge_base_scope_or_raise(
            db=ragflow.db,
            current_user=current_user,
            domain_id=domain_id,
            requested_kb_ids=[doc.knowledge_base_id],
            required_permission=KnowledgeBasePermissionType.WRITE,
        )
        if not kb_scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this document's knowledge base",
            )
    
    success = await ragflow.delete_domain_document(document_id, current_user.customer_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


# ==================== Retrieval ====================

@router.post("/domains/{domain_id}/retrieve", response_model=RetrievalResponse)
async def retrieve_from_domain(
    domain_id: int,
    request: RetrievalRequest,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Retrieve relevant document chunks for a query.
    
    Uses vector similarity search to find the most relevant chunks
    from documents in the domain.
    """
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )

    if _is_fasb_workspace(domain):
        try:
            from src.services.fasb_service import get_fasb_service

            fasb_service = get_fasb_service()
            kb_scope: Optional[List[int]] = None
            if request.knowledge_base_ids:
                resolved_scope = _resolve_knowledge_base_scope_or_raise(
                    db=ragflow.db,
                    current_user=current_user,
                    domain_id=domain_id,
                    requested_kb_ids=request.knowledge_base_ids,
                    required_permission=KnowledgeBasePermissionType.READ,
                )
                kb_scope = resolved_scope or None
            source_filter = _get_fasb_source_filter(domain, request.fasb_source_filter)
            contexts = fasb_service.retrieve(
                request.query,
                original_query=request.query,
                source_filter=source_filter,
                knowledge_base_ids=kb_scope,
            )
            chunks = [
                RetrievedChunk(
                    content=ctx.text,
                    document_name=ctx.citation,
                    document_id=None,
                    similarity=ctx.score / 100.0 if ctx.score < 100 else 1.0,
                    metadata={
                        "score": ctx.score,
                        "source_filter": source_filter or "all",
                        "knowledge_base_ids": kb_scope,
                    },
                )
                for ctx in contexts[: request.top_k]
            ]
            return RetrievalResponse(query=request.query, chunks=chunks, total_chunks=len(chunks))
        except Exception as exc:
            logger.error(f"FASB retrieval failed: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"FASB error: {str(exc)}",
            ) from exc
    
    # Use domain defaults unless overridden
    similarity_threshold = request.similarity_threshold
    if similarity_threshold is None:
        similarity_threshold = domain.similarity_threshold / 100.0

    kb_scope = _resolve_knowledge_base_scope_or_raise(
        db=ragflow.db,
        current_user=current_user,
        domain_id=domain_id,
        requested_kb_ids=request.knowledge_base_ids,
        required_permission=KnowledgeBasePermissionType.READ,
    )
    if not kb_scope:
        return RetrievalResponse(query=request.query, chunks=[], total_chunks=0)
    
    try:
        results = await ragflow.retrieve(
            domain_id=domain_id,
            customer_id=current_user.customer_id,
            query=request.query,
            top_k=request.top_k,
            min_score=similarity_threshold,
            knowledge_base_ids=kb_scope,
        )
        
        chunks = []
        for c in results:
            metadata = c.get("metadata") or {}
            chunks.append(
                RetrievedChunk(
                    content=c.get("text", ""),
                    document_name=c.get("document_name") or metadata.get("filename", "Unknown"),
                    document_id=c.get("document_id"),
                    similarity=c.get("score", 0.0),
                    metadata=metadata,
                    page_number=c.get("page_number") or metadata.get("page_number"),
                    page_range=c.get("page_range") or metadata.get("page_range"),
                    section_title=c.get("section_title") or metadata.get("section_title"),
                    section_hierarchy=c.get("section_hierarchy") or metadata.get("section_hierarchy"),
                    chunk_type=c.get("chunk_type") or metadata.get("chunk_type"),
                    chunk_summary=c.get("chunk_summary") or metadata.get("chunk_summary"),
                    key_entities=c.get("key_entities") or metadata.get("key_entities"),
                    document_title=c.get("document_title") or metadata.get("document_title"),
                    knowledge_base_name=c.get("knowledge_base_name") or metadata.get("knowledge_base_name"),
                    chunk_index=c.get("chunk_index") or metadata.get("chunk_index"),
                )
            )
        
        return RetrievalResponse(
            query=request.query,
            chunks=chunks,
            total_chunks=len(chunks)
        )
        
    except RAGFlowError as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RAGFlow error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Retrieval backend unavailable: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG retrieval backend is temporarily unavailable. Please retry in a moment."
        )


# ==================== Chat / Conversations ====================

@router.post("/domains/{domain_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    domain_id: int,
    request: CreateConversationRequest,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Start a new conversation with a domain.
    
    Creates a chat session for RAG-based Q&A with the domain's documents.
    """
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    conversation = await ragflow.create_conversation(
        domain_id=domain_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        title=request.title
    )
    
    return ConversationResponse.model_validate(conversation)


@router.get("/domains/{domain_id}/conversations", response_model=ConversationListResponse)
async def list_conversations(
    domain_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """List conversations for a domain."""
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    conversations = await ragflow.list_conversations(
        domain_id=domain_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        limit=limit,
        offset=offset
    )
    
    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in conversations],
        total=len(conversations)
    )


@router.patch("/conversations/{conversation_uuid}/title")
async def update_conversation_title(
    conversation_uuid: str,
    request: dict,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    db: Session = Depends(get_db)
):
    """Update conversation title by UUID."""
    from src.models.ragflow_domain import RAGFlowConversation
    
    conversation = db.query(RAGFlowConversation).filter(
        RAGFlowConversation.uuid == conversation_uuid,
        RAGFlowConversation.customer_id == current_user.customer_id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    conversation.title = request.get("title", "").strip() or "New conversation"
    db.commit()
    
    return {"success": True, "title": conversation.title}


@router.get("/domains/{domain_id}/conversations/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation(
    domain_id: int,
    conversation_id: int,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """Get conversation with all messages."""
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    conversation = await ragflow.get_conversation(conversation_id, current_user.customer_id)
    
    if not conversation or conversation.domain_id != domain_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found"
        )
    
    return ConversationWithMessagesResponse(
        conversation=ConversationResponse.model_validate(conversation),
        messages=[MessageResponse.model_validate(m) for m in conversation.messages]
    )


@router.get("/conversations/by-uuid/{conversation_uuid}", response_model=ConversationWithMessagesResponse)
async def get_conversation_by_uuid(
    conversation_uuid: str,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """Get conversation by UUID with all messages."""
    conversation = await ragflow.get_conversation_by_uuid(conversation_uuid, current_user.customer_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation not found"
        )
    
    return ConversationWithMessagesResponse(
        conversation=ConversationResponse.model_validate(conversation),
        messages=[MessageResponse.model_validate(m) for m in conversation.messages]
    )


@router.get(
    "/domains/{domain_id}/conversations/{conversation_id}/agent-mesh/stream",
    summary="Stream Agent Mesh live progress",
    description="Stream live Agent Mesh execution events via SSE for a single message request_id.",
)
async def stream_agent_mesh_progress(
    request: Request,
    domain_id: int,
    conversation_id: int,
    request_id: str = Query(..., description="Client-generated request ID"),
    token: str = Query(..., description="JWT access token (EventSource doesn't support headers)"),
    db: Session = Depends(get_db),
    ragflow: RAGFlowService = Depends(get_ragflow_service),
):
    """
    Stream Agent Mesh execution progress in real time.

    This endpoint is designed for `/chat` Agent Mesh UX where the frontend:
    1) opens this stream with request_id
    2) sends chat message with same request_id
    3) renders tool calls/stages as events arrive
    """
    auth_service = AuthService()
    try:
        payload = await auth_service.verify_token(token)
        user_id = int(payload.get("sub"))
        user = await auth_service.get_user_by_id(user_id)
    except Exception as exc:
        logger.error("agent_mesh_sse_auth_failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired token",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found",
        )

    normalized_request_id = _normalize_stream_request_id(request_id)
    if not normalized_request_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request_id is required",
        )

    domain = await ragflow.get_domain(domain_id, user.customer_id)
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found",
        )

    if not _is_agent_mesh_workspace(domain, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live Agent Mesh stream is only available for Agent Mesh workspaces",
        )

    conversation = await ragflow.get_conversation(conversation_id, user.customer_id)
    if not conversation or conversation.domain_id != domain_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    if conversation.user_id != user.id and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this conversation",
        )

    stream_store = get_agent_mesh_progress_store()
    stream_store.initialize(normalized_request_id)

    async def event_generator():
        last_sequence = 0
        idle_cycles = 0
        poll_interval_seconds = 0.35
        heartbeat_cycles = 25  # ~8.75s at 0.35s poll interval
        max_iterations = 2400  # ~14 minutes
        iteration = 0

        connected_event = {
            "event_id": f"agent-mesh-connected-{uuid.uuid4().hex}",
            "event_type": "connected",
            "message": "Agent Mesh live stream connected",
            "metadata": {
                "request_id": normalized_request_id,
                "conversation_id": conversation_id,
                "domain_id": domain_id,
            },
            "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        }
        yield f"data: {json.dumps(connected_event)}\n\n"

        while iteration < max_iterations:
            iteration += 1
            if await request.is_disconnected():
                logger.debug(
                    "agent_mesh_sse_client_disconnected",
                    extra={
                        "request_id": normalized_request_id,
                        "conversation_id": conversation_id,
                    },
                )
                break

            events = stream_store.get_events(
                normalized_request_id,
                after_sequence=last_sequence,
            )
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
                last_sequence = max(last_sequence, int(event.get("sequence", 0)))
                idle_cycles = 0
                if event.get("event_type") in {"completed", "failed"}:
                    return

            idle_cycles += 1
            if idle_cycles >= heartbeat_cycles:
                heartbeat_event = {
                    "event_id": f"agent-mesh-heartbeat-{uuid.uuid4().hex}",
                    "event_type": "heartbeat",
                    "message": "heartbeat",
                    "metadata": {
                        "request_id": normalized_request_id,
                        "last_sequence": last_sequence,
                    },
                    "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
                }
                yield f"data: {json.dumps(heartbeat_event)}\n\n"
                idle_cycles = 0

            await asyncio.sleep(poll_interval_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/domains/{domain_id}/conversations/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(
    domain_id: int,
    conversation_id: int,
    request: SendMessageRequest,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Send a message in a conversation and get a RAG-powered response.
    
    The assistant will retrieve relevant document chunks and generate
    an answer based on the domain's documents.
    """
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    conversation = await ragflow.get_conversation(conversation_id, current_user.customer_id)
    
    if not conversation or conversation.domain_id != domain_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found"
        )
    
    # Verify user owns the conversation
    if conversation.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this conversation"
        )

    is_fasb = _is_fasb_workspace(domain)
    kb_scope: Optional[List[int]] = None
    if is_fasb:
        # Transitional behavior for FASB: keep legacy unfiltered retrieval unless
        # caller explicitly scopes to KB IDs. This avoids hiding pre-existing chunks
        # that were indexed before knowledge_base_id metadata was introduced.
        if request.knowledge_base_ids:
            resolved_scope = _resolve_knowledge_base_scope_or_raise(
                db=ragflow.db,
                current_user=current_user,
                domain_id=domain_id,
                requested_kb_ids=request.knowledge_base_ids,
                required_permission=KnowledgeBasePermissionType.READ,
            )
            kb_scope = resolved_scope or None
    else:
        kb_scope = _resolve_knowledge_base_scope_or_raise(
            db=ragflow.db,
            current_user=current_user,
            domain_id=domain_id,
            requested_kb_ids=request.knowledge_base_ids,
            required_permission=KnowledgeBasePermissionType.READ,
        )
        if not kb_scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No accessible knowledge bases in this workspace",
            )
    
    try:
        # Route template-specific chat paths.
        is_agent_mesh = _is_agent_mesh_workspace(domain, ragflow.db)
        request_started_at = time.perf_counter()
        request_id = _normalize_stream_request_id(request.request_id)
        stream_store = get_agent_mesh_progress_store() if request_id else None

        if is_agent_mesh and request_id and stream_store is not None:
            stream_store.initialize(request_id)
            stream_store.publish(
                request_id,
                event_type="submitted",
                message="Question submitted to Agent Mesh",
                metadata={
                    "domain_id": domain_id,
                    "conversation_id": conversation_id,
                    "query_preview": request.content[:200],
                },
            )
        
        if is_fasb:
            try:
                from src.services.fasb_service import get_fasb_service
                from src.models.ragflow_domain import RAGFlowMessage
                from datetime import datetime
                
                fasb_service = get_fasb_service()
                
                # Build conversation context from previous messages (last 10)
                # This enables follow-up questions to have context from prior Q&A
                conversation_context = None
                if conversation.messages:
                    context_messages = conversation.messages[-10:]  # Last 10 messages
                    if context_messages:
                        context_parts = []
                        context_parts.append(f"Previous conversation ({len(context_messages)} messages):")
                        for msg in context_messages:
                            role_label = "User" if msg.role == "user" else "Assistant"
                            # Truncate long messages to avoid token bloat
                            content_preview = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                            context_parts.append(f"{role_label}: {content_preview}")
                        conversation_context = "\n".join(context_parts)
                
                # Pass domain's top_k and similarity_threshold to control sources
                # Use domain settings if explicitly changed from defaults, otherwise use FASB service defaults
                # Domain stores threshold as 0-100, convert to 0-1
                # Default domain values: top_k=5, similarity_threshold=20
                # For FASB, we want more sources by default (8) with lower threshold (0.1)
                top_k = domain.top_k if domain.top_k != 5 else 8  # FASB default: 8 sources
                threshold = domain.similarity_threshold / 100.0 if domain.similarity_threshold != 20 else 0.1
                source_filter = _get_fasb_source_filter(domain, request.fasb_source_filter)
                
                # Use process_message which handles context enhancement internally
                fasb_result = fasb_service.process_message(
                    question=request.content,
                    conversation_context=conversation_context,
                    customer_id=current_user.customer_id,
                    top_k=top_k,
                    similarity_threshold=threshold,
                    source_filter=source_filter,
                    knowledge_base_ids=kb_scope,
                )
                
                # Extract answer and sources from process_message result format
                result_metadata = fasb_result.get("result_metadata", {})
                answer = result_metadata.get("summary", "")
                sources = result_metadata.get("sources", [])
                
                # Save user message
                user_msg = RAGFlowMessage(
                    conversation_id=conversation_id,
                    role="user",
                    content=request.content
                )
                ragflow.db.add(user_msg)
                
                # Save assistant message with sources
                assistant_chunks = [{
                    "content": s.get("text_preview", ""),
                    "document_name": s.get("citation", ""),
                    "similarity": 1.0
                } for s in sources]
                
                assistant_msg = RAGFlowMessage(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                    retrieved_chunks=assistant_chunks,
                    chunk_count=len(sources)
                )
                ragflow.db.add(assistant_msg)
                
                # Update conversation
                conversation.message_count = (conversation.message_count or 0) + 2
                conversation.last_message_at = datetime.utcnow()
                ragflow.db.commit()
                ragflow.db.refresh(user_msg)
                ragflow.db.refresh(assistant_msg)

                # FASB routing bypasses the Pydantic backend, so emit trace here explicitly.
                try:
                    langfuse_service = get_langfuse_service()
                    langfuse_service.trace_workspace_chat(
                        model=fasb_result.get("model", "gpt-4o"),
                        input_data={
                            "question": request.content,
                            "domain_id": domain.id,
                            "conversation_id": conversation.id,
                            "conversation_uuid": conversation.uuid,
                            "route": "fasb_service",
                        },
                        output_data={
                            "answer": answer,
                            "sources_count": len(sources),
                        },
                        usage_details=None,
                        workspace_id=domain.id,
                        domain=domain.name,
                        customer_id=current_user.customer_id,
                        session_id=str(conversation.id),
                        latency_ms=(time.perf_counter() - request_started_at) * 1000.0,
                        extra_metadata={
                            "backend": "fasb_service",
                            "source_filter": source_filter or "all",
                            "knowledge_base_ids": kb_scope,
                            "conversation_uuid": conversation.uuid,
                            "conversation_id": conversation.id,
                            "user_id": current_user.user_id,
                        },
                    )
                except Exception as trace_exc:
                    logger.warning(
                        "fasb_trace_emit_failed workspace_id=%s customer_id=%s conversation_id=%s error=%s",
                        domain.id,
                        current_user.customer_id,
                        conversation.id,
                        str(trace_exc),
                    )
                
                # Auto-generate title after first message exchange (fire-and-forget)
                if conversation.message_count == 2 and conversation.title == "New conversation":
                    try:
                        from src.tasks.ragflow_tasks import generate_conversation_title
                        generate_conversation_title.delay(
                            conversation.id, current_user.customer_id, request.content
                        )
                    except Exception:
                        pass  # Never let title generation affect the chat response
                
                return ChatResponse(
                    user_message=MessageResponse(
                        id=user_msg.id,
                        conversation_id=conversation_id,
                        role="user",
                        content=request.content,
                        retrieved_chunks=None,
                        chunk_count=None,
                        created_at=user_msg.created_at
                    ),
                    assistant_message=MessageResponse(
                        id=assistant_msg.id,
                        conversation_id=conversation_id,
                        role="assistant",
                        content=answer,
                        retrieved_chunks=assistant_chunks,
                        chunk_count=len(sources),
                        created_at=assistant_msg.created_at
                    )
                )
            
            except (ValueError, RuntimeError) as fasb_error:
                # Catch FASB-specific errors (AWS auth, OpenSearch connectivity, embedding failures)
                logger.error(f"FASB service error: {fasb_error}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"FASB service error: {str(fasb_error)}"
                )
            except Exception as fasb_unexpected:
                logger.error(f"Unexpected FASB error: {fasb_unexpected}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"FASB processing failed: {str(fasb_unexpected)}"
                )
        
        if is_agent_mesh:
            try:
                from src.flows.retrieval_flow import RetrievalFlow
                from src.models.ragflow_domain import RAGFlowMessage
                from datetime import datetime

                def _publish_agent_mesh_progress(event_payload: dict) -> None:
                    if not request_id or stream_store is None:
                        return
                    event_type = str(event_payload.get("event_type") or "progress").strip() or "progress"
                    message = str(event_payload.get("message") or "").strip() or "Agent Mesh progress update"
                    metadata = event_payload.get("metadata") if isinstance(event_payload.get("metadata"), dict) else {}
                    stream_store.publish(
                        request_id,
                        event_type=event_type,
                        message=message,
                        metadata=metadata,
                    )

                # Persist user message first so UI has complete chat history in one table.
                user_msg = RAGFlowMessage(
                    conversation_id=conversation_id,
                    role="user",
                    content=request.content,
                )
                ragflow.db.add(user_msg)
                ragflow.db.flush()

                retrieval_result = await asyncio.to_thread(
                    RetrievalFlow().run,
                    query=request.content,
                    user_id=current_user.user_id,
                    customer_id=current_user.customer_id,
                    run_id=f"ragflow-{conversation.uuid}-{int(time.time())}",
                    conversation_id=str(conversation.id),
                    workspace_id=domain.id,
                    event_callback=_publish_agent_mesh_progress,
                )

                answer = ""
                if isinstance(retrieval_result, dict):
                    answer = str(
                        retrieval_result.get("raw")
                        or retrieval_result.get("error")
                        or ""
                    ).strip()

                if not answer:
                    answer = "I couldn't find relevant information to answer your question."

                sources = retrieval_result.get("sources", []) if isinstance(retrieval_result, dict) else []
                if not isinstance(sources, list):
                    sources = []

                follow_ups = retrieval_result.get("follow_ups", []) if isinstance(retrieval_result, dict) else []
                failed_tools = retrieval_result.get("failed_tools", []) if isinstance(retrieval_result, dict) else []
                tool_calls = retrieval_result.get("tool_calls", []) if isinstance(retrieval_result, dict) else []

                if not isinstance(follow_ups, list):
                    follow_ups = []
                if not isinstance(failed_tools, list):
                    failed_tools = []
                if not isinstance(tool_calls, list):
                    tool_calls = []

                assistant_chunks = [
                    {
                        "kind": "source",
                        "content": f"Retrieved via {source}",
                        "document_name": str(source).upper(),
                        "similarity": 1.0,
                        "metadata": {
                            "source": str(source),
                        },
                    }
                    for source in sources
                ]

                if follow_ups or tool_calls or failed_tools:
                    assistant_chunks.append(
                        {
                            "kind": "agent_mesh_meta",
                            "content": "Agent Mesh execution metadata",
                            "document_name": "__AGENT_MESH_META__",
                            "similarity": 1.0,
                            "metadata": {
                                "follow_ups": follow_ups,
                                "tool_calls": tool_calls,
                                "failed_tools": failed_tools,
                                "sources": sources,
                            },
                        }
                    )

                assistant_msg = RAGFlowMessage(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                    retrieved_chunks=assistant_chunks,
                    chunk_count=len(sources),
                )
                ragflow.db.add(assistant_msg)

                conversation.message_count = (conversation.message_count or 0) + 2
                conversation.last_message_at = datetime.utcnow()
                ragflow.db.commit()
                ragflow.db.refresh(user_msg)
                ragflow.db.refresh(assistant_msg)

                if request_id and stream_store is not None and not stream_store.is_terminal(request_id):
                    stream_store.publish(
                        request_id,
                        event_type="completed",
                        message="Agent Mesh run complete",
                        metadata={
                            "sources": sources,
                            "tool_call_count": len(tool_calls),
                            "follow_up_count": len(follow_ups),
                        },
                    )

                try:
                    langfuse_service = get_langfuse_service()
                    langfuse_service.trace_workspace_chat(
                        model=get_settings().default_llm_model,
                        input_data={
                            "question": request.content,
                            "domain_id": domain.id,
                            "conversation_id": conversation.id,
                            "conversation_uuid": conversation.uuid,
                            "route": "agent_mesh_retrieval",
                        },
                        output_data={
                            "answer": answer,
                            "sources_count": len(sources),
                            "tool_call_count": len(tool_calls),
                            "follow_ups": follow_ups,
                            "failed_tools": failed_tools,
                        },
                        usage_details=None,
                        workspace_id=domain.id,
                        domain=domain.name,
                        customer_id=current_user.customer_id,
                        session_id=str(conversation.id),
                        latency_ms=(time.perf_counter() - request_started_at) * 1000.0,
                        extra_metadata={
                            "backend": "agent_mesh_retrieval",
                            "conversation_uuid": conversation.uuid,
                            "conversation_id": conversation.id,
                            "user_id": current_user.user_id,
                            "sources": sources,
                        },
                    )
                except Exception as trace_exc:
                    logger.warning(
                        "agent_mesh_trace_emit_failed",
                        workspace_id=domain.id,
                        customer_id=current_user.customer_id,
                        conversation_id=conversation.id,
                        error=str(trace_exc),
                    )

                if conversation.message_count == 2 and conversation.title == "New conversation":
                    try:
                        from src.tasks.ragflow_tasks import generate_conversation_title

                        generate_conversation_title.delay(
                            conversation.id, current_user.customer_id, request.content
                        )
                    except Exception:
                        pass

                return ChatResponse(
                    user_message=MessageResponse(
                        id=user_msg.id,
                        conversation_id=conversation_id,
                        role="user",
                        content=request.content,
                        retrieved_chunks=None,
                        chunk_count=None,
                        created_at=user_msg.created_at,
                    ),
                    assistant_message=MessageResponse(
                        id=assistant_msg.id,
                        conversation_id=conversation_id,
                        role="assistant",
                        content=answer,
                        retrieved_chunks=assistant_chunks,
                        chunk_count=len(sources),
                        created_at=assistant_msg.created_at,
                    ),
                )
            except Exception as agent_mesh_error:
                ragflow.db.rollback()
                logger.error(f"Agent Mesh processing failed: {agent_mesh_error}", exc_info=True)
                if request_id and stream_store is not None:
                    stream_store.publish(
                        request_id,
                        event_type="failed",
                        message="Agent Mesh processing failed",
                        metadata={"error": str(agent_mesh_error)},
                    )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Agent Mesh processing failed: {str(agent_mesh_error)}",
                )

        # Standard RAGFlow path
        result = await ragflow.send_message(
            conversation_id=conversation_id,
            customer_id=current_user.customer_id,
            content=request.content,
            knowledge_base_ids=kb_scope,
        )
        
        return ChatResponse(
            user_message=MessageResponse(
                id=result["user_message"]["id"],
                conversation_id=conversation_id,
                role="user",
                content=result["user_message"]["content"],
                retrieved_chunks=None,
                chunk_count=None,
                created_at=result["user_message"]["created_at"]
            ),
            assistant_message=MessageResponse(
                id=result["assistant_message"]["id"],
                conversation_id=conversation_id,
                role="assistant",
                content=result["assistant_message"]["content"],
                retrieved_chunks=result["assistant_message"].get("chunks"),
                chunk_count=len(result["assistant_message"].get("chunks", [])),
                created_at=result["assistant_message"]["created_at"]
            )
        )
        
    except RAGFlowError as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RAGFlow error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Chat backend unavailable: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG chat backend is temporarily unavailable. Please retry in a moment."
        )


@router.delete("/domains/{domain_id}/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    domain_id: int,
    conversation_id: int,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """Delete (soft-delete) a conversation."""
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    conversation = await ragflow.get_conversation(conversation_id, current_user.customer_id)
    
    if not conversation or conversation.domain_id != domain_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found"
        )
    
    # Verify user owns the conversation
    if conversation.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this conversation"
        )
    
    success = await ragflow.delete_conversation(conversation_id, current_user.customer_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )


# ==================== Quick Chat (No Conversation Persistence) ====================

@router.post("/domains/{domain_id}/chat", response_model=RetrievalResponse)
async def quick_chat(
    domain_id: int,
    request: RetrievalRequest,
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
    ragflow: RAGFlowService = Depends(get_ragflow_service)
):
    """
    Quick RAG query without conversation persistence.
    
    Retrieves relevant chunks and optionally generates an answer.
    Use this for one-off queries that don't need conversation history.
    """
    domain = await ragflow.get_domain(domain_id, current_user.customer_id)
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain {domain_id} not found"
        )
    
    # Route FASB domains to the FASB service (uses OpenSearch, not RAGFlow)
    is_fasb = _is_fasb_workspace(domain)
    
    if is_fasb:
        try:
            from src.services.fasb_service import get_fasb_service
            
            fasb_service = get_fasb_service()
            kb_scope: Optional[List[int]] = None
            if request.knowledge_base_ids:
                resolved_scope = _resolve_knowledge_base_scope_or_raise(
                    db=ragflow.db,
                    current_user=current_user,
                    domain_id=domain_id,
                    requested_kb_ids=request.knowledge_base_ids,
                    required_permission=KnowledgeBasePermissionType.READ,
                )
                kb_scope = resolved_scope or None
            source_filter = _get_fasb_source_filter(domain, request.fasb_source_filter)
            contexts = fasb_service.retrieve(
                request.query,
                original_query=request.query,
                source_filter=source_filter,
                knowledge_base_ids=kb_scope,
            )
            
            chunks = [
                RetrievedChunk(
                    content=ctx.text,
                    document_name=ctx.citation,
                    document_id=None,
                    similarity=ctx.score / 100.0 if ctx.score < 100 else 1.0,
                    metadata={
                        "score": ctx.score,
                        "source_filter": source_filter or "all",
                        "knowledge_base_ids": kb_scope,
                    }
                )
                for ctx in contexts[:request.top_k]
            ]
            
            return RetrievalResponse(
                query=request.query,
                chunks=chunks,
                total_chunks=len(chunks)
            )
            
        except Exception as e:
            logger.error(f"FASB quick chat failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"FASB error: {str(e)}"
            )
    
    similarity_threshold = request.similarity_threshold
    if similarity_threshold is None:
        similarity_threshold = domain.similarity_threshold / 100.0

    kb_scope = _resolve_knowledge_base_scope_or_raise(
        db=ragflow.db,
        current_user=current_user,
        domain_id=domain_id,
        requested_kb_ids=request.knowledge_base_ids,
        required_permission=KnowledgeBasePermissionType.READ,
    )
    if not kb_scope:
        return RetrievalResponse(query=request.query, chunks=[], total_chunks=0)
    
    try:
        results = await ragflow.retrieve(
            domain_id=domain_id,
            customer_id=current_user.customer_id,
            query=request.query,
            top_k=request.top_k,
            min_score=similarity_threshold,
            knowledge_base_ids=kb_scope,
        )
        
        chunks = []
        for c in results:
            metadata = c.get("metadata") or {}
            chunks.append(
                RetrievedChunk(
                    content=c.get("text", ""),
                    document_name=c.get("document_name") or metadata.get("filename", "Unknown"),
                    document_id=c.get("document_id"),
                    similarity=c.get("score", 0.0),
                    metadata=metadata,
                    page_number=c.get("page_number") or metadata.get("page_number"),
                    page_range=c.get("page_range") or metadata.get("page_range"),
                    section_title=c.get("section_title") or metadata.get("section_title"),
                    section_hierarchy=c.get("section_hierarchy") or metadata.get("section_hierarchy"),
                    chunk_type=c.get("chunk_type") or metadata.get("chunk_type"),
                    chunk_summary=c.get("chunk_summary") or metadata.get("chunk_summary"),
                    key_entities=c.get("key_entities") or metadata.get("key_entities"),
                    document_title=c.get("document_title") or metadata.get("document_title"),
                    knowledge_base_name=c.get("knowledge_base_name") or metadata.get("knowledge_base_name"),
                    chunk_index=c.get("chunk_index") or metadata.get("chunk_index"),
                )
            )
        
        return RetrievalResponse(
            query=request.query,
            chunks=chunks,
            total_chunks=len(chunks)
        )
        
    except RAGFlowError as e:
        logger.error(f"Quick chat failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RAGFlow error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Quick chat backend unavailable: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG chat backend is temporarily unavailable. Please retry in a moment."
        )


# ==================== Document PDF Serving ====================

@router.options("/documents/{document_id}/pdf")
async def pdf_options(document_id: int):
    """CORS preflight for PDF.js fetch requests."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.get("/documents/{document_id}/pdf")
async def get_document_pdf(
    document_id: int,
    page: Optional[int] = Query(None, description="Page number (1-based)"),
    token: Optional[str] = Query(None, description="Auth token (for iframe/PDF.js)"),
    db: Session = Depends(get_db),
):
    """
    Serve a workspace document PDF for citation preview.

    Works for both FASB (on-disk) and native RAG (object storage) documents.
    Accepts token as query parameter for iframe/PDF.js compatibility.
    """
    from pathlib import Path
    from src.services.auth_service import AuthService

    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }

    # Authenticate
    if not token:
        return Response(
            content='{"error": "Not authenticated"}',
            status_code=401,
            media_type="application/json",
            headers=cors_headers,
        )

    try:
        auth_service = AuthService()
        payload = await auth_service.verify_token(token)
        if not payload:
            return Response(
                content='{"error": "Invalid token"}',
                status_code=401,
                media_type="application/json",
                headers=cors_headers,
            )
    except Exception as e:
        logger.warning(f"PDF auth failed: {e}")
        return Response(
            content='{"error": "Invalid token"}',
            status_code=401,
            media_type="application/json",
            headers=cors_headers,
        )

    settings = get_settings()

    # --- Path 1: FASB on-disk PDF (only if document belongs to a FASB workspace) ---
    doc_for_fasb_check = db.query(RAGFlowDocument).filter(RAGFlowDocument.id == document_id).first()
    is_fasb_doc = False
    if doc_for_fasb_check:
        domain_for_check = db.query(RAGFlowDomain).filter(RAGFlowDomain.id == doc_for_fasb_check.domain_id).first()
        if domain_for_check:
            ws_config = domain_for_check.workspace_config if isinstance(domain_for_check.workspace_config, dict) else {}
            domain_name = str(domain_for_check.name or "").strip().lower()
            backend_type = str(ws_config.get("backend_type") or "").strip().lower()
            is_fasb_doc = domain_name == "fasb" or backend_type == "opensearch_fasb"

    if is_fasb_doc:
        fasb_path = Path(settings.fasb_docs_path) / f"{document_id}.pdf"
        if fasb_path.exists():
            with open(fasb_path, "rb") as f:
                pdf_content = f.read()
            return Response(
                content=pdf_content,
                media_type="application/pdf",
                headers={
                    **cors_headers,
                    "Content-Disposition": f"inline; filename={document_id}.pdf",
                    "X-Page-Number": str(page) if page else "1",
                },
            )

    # --- Path 2: Check local MinIO PDF cache first ---
    try:
        from src.services.pdf_cache_service import PDFCacheService
        pdf_cache = PDFCacheService(db)
        cached_bytes = await pdf_cache.get_cached_pdf(document_id)
        if cached_bytes:
            logger.info(f"PDF cache HIT for document {document_id}")
            return Response(
                content=cached_bytes,
                media_type="application/pdf",
                headers={
                    **cors_headers,
                    "Content-Disposition": f"inline; filename=doc_{document_id}.pdf",
                    "X-Page-Number": str(page) if page else "1",
                    "X-Cache": "HIT",
                },
            )
    except Exception as e:
        logger.debug(f"PDF cache lookup failed (non-fatal): {e}")

    # --- Path 3: Native RAG document from object storage ---
    doc = db.query(RAGFlowDocument).filter(
        RAGFlowDocument.id == document_id,
    ).first()

    if not doc:
        return Response(
            content=f'{{"error": "Document {document_id} not found"}}',
            status_code=404,
            media_type="application/json",
            headers=cors_headers,
        )

    metadata = doc.document_metadata if isinstance(doc.document_metadata, dict) else {}
    storage = metadata.get("storage") or {}
    source = metadata.get("source") or {}
    bucket = storage.get("bucket") or source.get("bucket")
    object_key = storage.get("object_key") or source.get("object_key")

    # Fallback: resolve from the knowledge base's S3 source config
    if (not bucket or not object_key) and doc.knowledge_base_id:
        try:
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == doc.knowledge_base_id).first()
            if kb and kb.source_config:
                kb_sc = kb.source_config if isinstance(kb.source_config, dict) else {}
                if not bucket:
                    bucket = kb_sc.get("bucket")
                if not object_key:
                    object_key = doc.original_filename
        except Exception:
            pass

    if not bucket or not object_key:
        return Response(
            content='{"error": "Document file not available in storage"}',
            status_code=404,
            media_type="application/json",
            headers=cors_headers,
        )

    try:
        from src.services.object_storage_service import ObjectStorageService

        obj_service = ObjectStorageService(db)
        result = await obj_service.get_object_bytes(
            customer_id=doc.customer_id,
            bucket=bucket,
            object_key=object_key,
        )
        pdf_content = result.get("content", b"")
        content_type = result.get("content_type") or doc.mime_type or "application/pdf"

        # Cache in local MinIO for next time (fire-and-forget)
        try:
            from src.services.pdf_cache_service import PDFCacheService
            pdf_cache = PDFCacheService(db)
            asyncio.ensure_future(pdf_cache.cache_pdf(document_id, pdf_content))
        except Exception:
            pass

        return Response(
            content=pdf_content,
            media_type=content_type,
            headers={
                **cors_headers,
                "Content-Disposition": f"inline; filename={doc.original_filename}",
                "X-Page-Number": str(page) if page else "1",
                "X-Cache": "MISS",
            },
        )
    except Exception as e:
        logger.error(f"Failed to fetch document from storage: {e}")
        return Response(
            content=f'{{"error": "Failed to retrieve document: {str(e)}"}}',
            status_code=500,
            media_type="application/json",
            headers=cors_headers,
        )
