"""
Workspace API Routes - Workspace and knowledge base management.

Provides endpoints for:
- Workspace templates (available workspace types)
- Workspace CRUD (extends RAGFlow domains)
- Knowledge base management within workspaces
- Knowledge base permissions
- Chat history across workspaces
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from src.models.database import get_db
from src.models.ragflow_domain import (
    RAGFlowConversation,
    RAGFlowDomain,
    RAGFlowMessage,
    RAGFlowDomainStatus, RAGFlowParserType
)
from src.models.workspace import (
    WorkspaceTemplate, KnowledgeBase, KnowledgeBasePermission,
    KnowledgeBaseStatus, KnowledgeBasePermissionType,
    KnowledgeBaseSourceType, KnowledgeBaseStorageBackend,
)
from src.models.auth import User, Role
from src.api.schemas.workspace import (
    # Templates
    WorkspaceTemplateResponse, WorkspaceTemplateListResponse,
    # Knowledge Bases
    KnowledgeBaseCreateRequest, KnowledgeBaseUpdateRequest,
    KnowledgeBaseResponse, KnowledgeBaseListResponse, KnowledgeBaseSummaryResponse,
    # Knowledge Base Permissions
    KnowledgeBasePermissionCreateRequest, KnowledgeBasePermissionResponse,
    KnowledgeBasePermissionListResponse,
    # Workspaces
    WorkspaceCreateRequest, WorkspaceUpdateRequest,
    WorkspaceResponse, WorkspaceListResponse, WorkspaceDetailResponse,
    WorkspacePromptTemplateResponse, WorkspacePromptTemplateUpdateRequest,
    WorkspaceTelemetryResponse, WorkspaceTelemetryRequestItem, WorkspaceLangfuseTraceItem,
    # Chat History
    ConversationSummary, ChatHistoryResponse,
    # Workspace Picker
    WorkspacePickerItem, WorkspacePickerResponse,
)
from src.middleware.authorization import require_permission
from src.core.auth_context import CurrentUserContext
from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings
from src.services.workspace_rag_backend import (
    get_workspace_prompt_template,
    save_workspace_prompt_template,
    seed_workspace_prompts,
)
from src.services.langfuse_service import get_langfuse_service
from src.services.fasb_service import get_fasb_service
from src.services.native_rag_service import NativeRAGService
from src.services.knowledge_base_access_service import KnowledgeBaseAccessService
from src.services.tenant_storage_settings_service import TenantStorageSettingsService

logger = get_logger(__name__, LogCategory.API)

router = APIRouter(prefix="/v1/workspaces", tags=["Workspaces"])
template_router = APIRouter(prefix="/v1/workspace-templates", tags=["Workspace Templates"])
chat_router = APIRouter(prefix="/v1/chat", tags=["Chat"])


# ==================== Helper Functions ====================

def get_workspace_response(workspace: RAGFlowDomain, include_kbs: bool = False) -> WorkspaceResponse:
    """Convert RAGFlowDomain to WorkspaceResponse."""
    kb_count = len(workspace.knowledge_bases) if workspace.knowledge_bases else 0
    
    response_data = {
        "id": workspace.id,
        "customer_id": workspace.customer_id,
        "name": workspace.name,
        "display_name": workspace.display_name,
        "description": workspace.description,
        "icon": workspace.icon,
        "color": workspace.color,
        "template_id": workspace.template_id,
        "template_name": workspace.template.name if workspace.template else None,
        "template_display_name": workspace.template.display_name if workspace.template else None,
        "workspace_config": workspace.workspace_config,
        "status": workspace.status.value if hasattr(workspace.status, 'value') else str(workspace.status),
        "document_count": workspace.document_count,
        "chunk_count": workspace.chunk_count,
        "total_tokens": workspace.total_tokens,
        "knowledge_base_count": kb_count,
        "is_active": workspace.is_active,
        "last_error": workspace.last_error,
        "last_sync_at": workspace.last_sync_at,
        "created_at": workspace.created_at,
        "updated_at": workspace.updated_at,
    }
    
    if include_kbs and workspace.knowledge_bases:
        response_data["knowledge_bases"] = [
            KnowledgeBaseSummaryResponse(
                id=kb.id,
                name=kb.name,
                status=KnowledgeBaseStatus(kb.status),
                document_count=kb.document_count,
                chunk_count=kb.chunk_count,
                is_active=kb.is_active,
            )
            for kb in workspace.knowledge_bases
        ]
    
    return WorkspaceResponse(**response_data)


def _is_fasb_workspace(workspace: RAGFlowDomain) -> bool:
    """Detect FASB-backed workspace routing."""
    workspace_config = workspace.workspace_config if isinstance(workspace.workspace_config, dict) else {}
    backend_type = str(workspace_config.get("backend_type") or "").strip().lower()
    domain_name = str(workspace.name or "").strip().lower()
    opensearch_index = str(workspace_config.get("opensearch_index") or "").strip().lower()

    return (
        domain_name == "fasb"
        or backend_type == "opensearch_fasb"
        or opensearch_index.startswith("fasb")
    )


def _get_fasb_source_filter(workspace: RAGFlowDomain) -> Optional[str]:
    """Resolve optional FASB source filter from workspace config."""
    workspace_config = workspace.workspace_config if isinstance(workspace.workspace_config, dict) else {}
    raw = workspace_config.get("fasb_source_filter") or workspace_config.get("source_filter")
    if raw is None:
        return None
    normalized = str(raw).strip().lower()
    if normalized in {"all", "primary", "memo"}:
        return normalized
    return None


def _merge_workspace_config(
    template_config: Optional[dict],
    request_config: Optional[dict],
) -> Optional[dict]:
    """Merge template defaults with request overrides (shallow merge)."""
    if not template_config and not request_config:
        return None
    merged = dict(template_config or {})
    merged.update(request_config or {})
    return merged


def _parse_s3_source_path(value: str) -> Tuple[Optional[str], str]:
    """Parse `s3://bucket/prefix` or plain `prefix` source paths."""
    normalized = value.strip()
    if not normalized:
        return None, ""
    if normalized.lower().startswith("s3://"):
        body = normalized[5:]
        bucket, _, prefix = body.partition("/")
        return (bucket.strip() or None), prefix.strip().strip("/")
    return None, normalized.strip().strip("/")


def _parse_bool_flag(value: Any, default: bool = True) -> bool:
    """Parse permissive boolean values from JSON payloads."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _parse_positive_int(value: Any, default: int, minimum: int = 1, maximum: int = 1000) -> int:
    """Parse and clamp positive integer config values."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _normalize_s3_source_config(
    source_config: Dict[str, Any],
    tenant_storage_settings: Optional[dict],
) -> Dict[str, Any]:
    """
    Normalize and validate S3 KB source config.

    Required:
    - source_config.prefix OR source_config.s3_path
    - resolvable bucket (source_config.bucket, s3_path bucket, or tenant bucket)
    """
    tenant_bucket = str((tenant_storage_settings or {}).get("bucket") or "").strip()

    raw_path = str(
        source_config.get("s3_path")
        or source_config.get("prefix")
        or source_config.get("path")
        or ""
    ).strip()
    bucket_from_path, prefix = _parse_s3_source_path(raw_path)
    bucket = str(source_config.get("bucket") or "").strip() or bucket_from_path or tenant_bucket

    if not raw_path:
        raise ValueError(
            "S3 knowledge base source requires an S3 path. "
            "Provide source_config.prefix (or source_config.s3_path)."
        )
    if not bucket:
        raise ValueError(
            "S3 knowledge base source could not resolve bucket. "
            "Configure tenant object storage bucket or provide source_config.bucket."
        )

    file_extensions = source_config.get("file_extensions")
    normalized_extensions: List[str] = []
    if isinstance(file_extensions, list):
        for ext in file_extensions:
            if not isinstance(ext, str):
                continue
            normalized_ext = ext.strip().lower()
            if not normalized_ext:
                continue
            if not normalized_ext.startswith("."):
                normalized_ext = f".{normalized_ext}"
            normalized_extensions.append(normalized_ext)
    if not normalized_extensions:
        normalized_extensions = [".pdf", ".docx", ".doc", ".pptx", ".ppt"]

    normalized_s3_path = f"s3://{bucket}/{prefix}" if prefix else f"s3://{bucket}/"
    max_files_default = get_settings().rag_kb_s3_sync_max_files_per_run
    return {
        "bucket": bucket,
        "prefix": prefix,
        "s3_path": normalized_s3_path,
        "sync_enabled": _parse_bool_flag(source_config.get("sync_enabled"), default=True),
        "max_files_per_sync": _parse_positive_int(
            source_config.get("max_files_per_sync"),
            default=max_files_default,
            minimum=1,
            maximum=1000,
        ),
        "file_extensions": normalized_extensions,
    }


def _resolve_kb_source_and_storage(
    *,
    kb_request: KnowledgeBaseCreateRequest | KnowledgeBaseUpdateRequest,
    tenant_storage_settings: Optional[dict],
    existing_source_type: Optional[str] = None,
    existing_storage_backend: Optional[str] = None,
) -> tuple[str, Optional[dict], str, Optional[dict]]:
    """
    Resolve source/storage settings for knowledge base create/update.

    - Supports tenant-level defaults for local directory source path.
    - Expands `tenant_default` storage backend to tenant backend when available.
    """
    source_type = (
        kb_request.source_type.value
        if getattr(kb_request, "source_type", None) is not None
        else existing_source_type or KnowledgeBaseSourceType.ELASTICSEARCH.value
    )
    source_config = dict(getattr(kb_request, "source_config", None) or {})

    tenant_default_local_path = None
    tenant_backend = None
    if tenant_storage_settings:
        tenant_default_local_path = tenant_storage_settings.get("default_local_source_path")
        tenant_backend = tenant_storage_settings.get("backend")

    if source_type == KnowledgeBaseSourceType.LOCAL_DIRECTORY.value and "path" not in source_config:
        if tenant_default_local_path:
            source_config["path"] = tenant_default_local_path
    elif source_type == KnowledgeBaseSourceType.S3.value:
        source_config = _normalize_s3_source_config(
            source_config=source_config,
            tenant_storage_settings=tenant_storage_settings,
        )

    requested_storage_backend = (
        kb_request.storage_backend.value
        if getattr(kb_request, "storage_backend", None) is not None
        else existing_storage_backend or KnowledgeBaseStorageBackend.TENANT_DEFAULT.value
    )
    if requested_storage_backend == KnowledgeBaseStorageBackend.TENANT_DEFAULT.value and tenant_backend:
        resolved_storage_backend = tenant_backend
    else:
        resolved_storage_backend = requested_storage_backend

    storage_config = dict(getattr(kb_request, "storage_config", None) or {})

    return (
        source_type,
        source_config or None,
        resolved_storage_backend,
        storage_config or None,
    )


def _enqueue_s3_kb_sync(
    *,
    workspace_id: int,
    knowledge_base_id: int,
    customer_id: str,
    trigger: str,
) -> None:
    """Best-effort enqueue of S3 knowledge-base sync task."""
    try:
        from src.tasks.ragflow_source_sync_tasks import sync_s3_knowledge_base

        sync_s3_knowledge_base.delay(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            customer_id=customer_id,
            trigger=trigger,
        )
    except Exception as exc:
        logger.warning(
            "knowledge_base_s3_sync_enqueue_failed",
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            trigger=trigger,
            error=str(exc),
        )


def check_kb_access(
    db: Session,
    user: CurrentUserContext,
    knowledge_base_id: int,
    required_permission: KnowledgeBasePermissionType = KnowledgeBasePermissionType.READ
) -> bool:
    """
    Check if user has access to a knowledge base.
    
    Access is granted if:
    1. User is a platform admin
    2. User has direct permission grant
    3. User's role has permission grant
    """
    kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_base_id).first()
    if not kb or kb.customer_id != user.customer_id:
        return False

    access_service = KnowledgeBaseAccessService(db)
    accessible = access_service.resolve_accessible_kb_ids(
        workspace_id=kb.workspace_id,
        user=user,
        required_permission=required_permission,
    )
    return knowledge_base_id in accessible


def _build_workspace_request_telemetry(
    db: Session,
    *,
    workspace_id: int,
    customer_id: str,
    limit: int,
) -> List[WorkspaceTelemetryRequestItem]:
    """
    Build recent workspace request telemetry from persisted chat messages.

    Each item represents an assistant response paired with the nearest preceding
    user message in the same conversation.
    """
    assistant_rows = (
        db.query(RAGFlowMessage, RAGFlowConversation)
        .join(RAGFlowConversation, RAGFlowMessage.conversation_id == RAGFlowConversation.id)
        .filter(
            RAGFlowConversation.domain_id == workspace_id,
            RAGFlowConversation.customer_id == customer_id,
            RAGFlowConversation.is_active == True,
            RAGFlowMessage.role == "assistant",
        )
        .order_by(RAGFlowMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    request_items: List[WorkspaceTelemetryRequestItem] = []
    for assistant_msg, conversation in assistant_rows:
        user_msg = (
            db.query(RAGFlowMessage)
            .filter(
                RAGFlowMessage.conversation_id == conversation.id,
                RAGFlowMessage.role == "user",
                RAGFlowMessage.created_at <= assistant_msg.created_at,
            )
            .order_by(RAGFlowMessage.created_at.desc())
            .first()
        )

        latency_ms: Optional[float] = None
        if user_msg and user_msg.created_at and assistant_msg.created_at:
            latency_ms = max(
                0.0,
                (assistant_msg.created_at - user_msg.created_at).total_seconds() * 1000,
            )

        prompt_tokens = assistant_msg.prompt_tokens or 0
        completion_tokens = assistant_msg.completion_tokens or 0

        request_items.append(
            WorkspaceTelemetryRequestItem(
                conversation_id=conversation.id,
                conversation_uuid=conversation.uuid,
                user_message_id=user_msg.id if user_msg else None,
                assistant_message_id=assistant_msg.id,
                request_text=user_msg.content if user_msg else None,
                response_text=assistant_msg.content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                created_at=assistant_msg.created_at,
                latency_ms=latency_ms,
            )
        )

    return request_items


# ==================== Workspace Template Endpoints ====================

@template_router.get("", response_model=WorkspaceTemplateListResponse)
async def list_workspace_templates(
    include_unavailable: bool = Query(False, description="Include coming soon templates"),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access"))
):
    """
    List available workspace templates.
    
    Returns templates that can be used to create new workspaces.
    By default, only available templates are returned.
    """
    query = db.query(WorkspaceTemplate)
    
    if not include_unavailable:
        query = query.filter(WorkspaceTemplate.is_available == True)
    
    templates = query.order_by(WorkspaceTemplate.display_name).all()
    
    return WorkspaceTemplateListResponse(
        templates=[WorkspaceTemplateResponse.model_validate(t) for t in templates],
        total=len(templates)
    )


@template_router.get("/{template_id}", response_model=WorkspaceTemplateResponse)
async def get_workspace_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access"))
):
    """Get workspace template details."""
    template = db.query(WorkspaceTemplate).filter(WorkspaceTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    return WorkspaceTemplateResponse.model_validate(template)


# ==================== Workspace Endpoints ====================

@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("workspaces:write"))
):
    """
    Create a new workspace.
    
    Requires a template selection. For RAG Retrieval template,
    optionally creates an initial knowledge base.
    """
    # Verify template exists and is available
    template = db.query(WorkspaceTemplate).filter(
        WorkspaceTemplate.id == request.template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    if not template.is_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template '{template.display_name}' is not yet available"
        )
    
    # Check for duplicate name
    existing = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.customer_id == current_user.customer_id,
        RAGFlowDomain.name == request.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workspace '{request.name}' already exists"
        )
    
    try:
        initial_kb_for_sync: Optional[KnowledgeBase] = None
        tenant_storage_service = TenantStorageSettingsService(db)
        tenant_storage = tenant_storage_service.get_storage_settings(current_user.customer_id)
        tenant_storage_settings = {
            "backend": tenant_storage.backend.value if tenant_storage.backend else None,
            "bucket": tenant_storage.bucket,
            "default_local_source_path": tenant_storage.default_local_source_path,
        }

        # Create workspace (RAGFlowDomain)
        workspace = RAGFlowDomain(
            customer_id=current_user.customer_id,
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            icon=request.icon,
            color=request.color,
            template_id=request.template_id,
            workspace_config=_merge_workspace_config(template.default_config, request.workspace_config),
            status=RAGFlowDomainStatus.PENDING,
            created_by_user_id=current_user.user_id,
        )
        db.add(workspace)
        db.flush()  # Get workspace ID
        
        # Create initial knowledge base if requested (RAG Retrieval template)
        if request.initial_knowledge_base and template.name == "rag_retrieval":
            kb_request = request.initial_knowledge_base
            source_type, source_config, storage_backend, storage_config = _resolve_kb_source_and_storage(
                kb_request=kb_request,
                tenant_storage_settings=tenant_storage_settings,
            )
            knowledge_base = KnowledgeBase(
                workspace_id=workspace.id,
                customer_id=current_user.customer_id,
                name=kb_request.name,
                description=kb_request.description,
                parser_type=kb_request.parser_type.value,
                parser_config=kb_request.parser_config,
                embedding_model=kb_request.embedding_model or "text-embedding-3-large@OpenAI",
                chunk_token_count=kb_request.chunk_token_count or 512,
                similarity_threshold=kb_request.similarity_threshold,
                top_k=kb_request.top_k,
                source_type=source_type,
                source_config=source_config,
                storage_backend=storage_backend,
                storage_config=storage_config,
                status=KnowledgeBaseStatus.PENDING.value,
                created_by_user_id=current_user.user_id,
            )
            db.add(knowledge_base)
            initial_kb_for_sync = knowledge_base
        
        db.commit()
        db.refresh(workspace)
        if initial_kb_for_sync is not None:
            db.refresh(initial_kb_for_sync)

        # Create workspace vector index immediately so new workspaces are query-ready.
        try:
            rag_service = NativeRAGService(db)
            await rag_service.vector_store.create_index(str(workspace.id))
        except Exception as index_error:
            logger.warning(
                "workspace_index_create_failed",
                workspace_id=workspace.id,
                error=str(index_error),
            )

        if (
            initial_kb_for_sync is not None
            and initial_kb_for_sync.id is not None
            and initial_kb_for_sync.source_type == KnowledgeBaseSourceType.S3.value
        ):
            _enqueue_s3_kb_sync(
                workspace_id=workspace.id,
                knowledge_base_id=initial_kb_for_sync.id,
                customer_id=current_user.customer_id,
                trigger="kb_created",
            )
        
        # Load relationships for response
        workspace = db.query(RAGFlowDomain).options(
            joinedload(RAGFlowDomain.template),
            joinedload(RAGFlowDomain.knowledge_bases)
        ).filter(RAGFlowDomain.id == workspace.id).first()
        
        # Seed default RAG prompts into prompt_templates for admin UI + GEPA
        try:
            seed_workspace_prompts(
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                customer_id=current_user.customer_id,
                db=db,
            )
            db.commit()
        except Exception as seed_exc:
            logger.warning("workspace_prompt_seed_failed", error=str(seed_exc), workspace_id=workspace.id)

        logger.info(
            "workspace_created",
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            template_id=template.id,
            customer_id=current_user.customer_id,
            user_id=current_user.user_id
        )
        
        return get_workspace_response(workspace, include_kbs=True)
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        db.rollback()
        logger.error("create_workspace_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace"
        )


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    template_filter: Optional[str] = Query(None, alias="template", description="Filter by template name"),
    search: Optional[str] = Query(None, description="Search by name or display name"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access"))
):
    """
    List workspaces for the current tenant.
    
    Returns workspaces with template info and knowledge base counts.
    """
    query = db.query(RAGFlowDomain).options(
        joinedload(RAGFlowDomain.template),
        joinedload(RAGFlowDomain.knowledge_bases)
    ).filter(
        RAGFlowDomain.customer_id == current_user.customer_id,
        RAGFlowDomain.is_active == True
    )
    
    if status_filter:
        query = query.filter(RAGFlowDomain.status == status_filter)
    
    if template_filter:
        query = query.join(RAGFlowDomain.template).filter(
            WorkspaceTemplate.name == template_filter
        )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            RAGFlowDomain.name.ilike(search_term),
            RAGFlowDomain.display_name.ilike(search_term)
        ))
    
    total = query.count()
    workspaces = query.order_by(RAGFlowDomain.created_at.desc()).offset(offset).limit(limit).all()
    
    return WorkspaceListResponse(
        workspaces=[get_workspace_response(w) for w in workspaces],
        total=total,
        offset=offset,
        limit=limit
    )


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access"))
):
    """Get workspace details including knowledge bases."""
    workspace = db.query(RAGFlowDomain).options(
        joinedload(RAGFlowDomain.template),
        joinedload(RAGFlowDomain.knowledge_bases)
    ).filter(
        RAGFlowDomain.id == workspace_id,
        RAGFlowDomain.customer_id == current_user.customer_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )

    # Auto-sync FASB stats on detail load so UI reflects live OpenSearch counts.
    if _is_fasb_workspace(workspace):
        try:
            source_filter = _get_fasb_source_filter(workspace)
            stats = get_fasb_service().get_index_stats(source_filter=source_filter)
            if "error" not in stats:
                next_doc_count = int(stats.get("document_count", 0) or 0)
                next_chunk_count = int(stats.get("chunk_count", 0) or 0)
                if (
                    workspace.document_count != next_doc_count
                    or workspace.chunk_count != next_chunk_count
                ):
                    workspace.document_count = next_doc_count
                    workspace.chunk_count = next_chunk_count
                    workspace.last_sync_at = datetime.utcnow()
                    db.commit()
                    db.refresh(workspace)
        except Exception as e:
            logger.warning(
                "workspace_fasb_auto_sync_failed",
                workspace_id=workspace.id,
                error=str(e),
            )
    
    access_service = KnowledgeBaseAccessService(db)
    accessible_kb_ids = set(
        access_service.resolve_accessible_kb_ids(
            workspace_id=workspace.id,
            user=current_user,
            required_permission=KnowledgeBasePermissionType.READ,
        )
    )
    visible_kbs = [kb for kb in workspace.knowledge_bases if kb.id in accessible_kb_ids]

    workspace_response = get_workspace_response(workspace, include_kbs=False)
    workspace_response.knowledge_base_count = len(visible_kbs)
    workspace_response.knowledge_bases = [
        KnowledgeBaseSummaryResponse(
            id=kb.id,
            name=kb.name,
            status=KnowledgeBaseStatus(kb.status),
            document_count=kb.document_count,
            chunk_count=kb.chunk_count,
            is_active=kb.is_active,
        )
        for kb in visible_kbs
    ]

    return WorkspaceDetailResponse(
        workspace=workspace_response,
        knowledge_bases=[KnowledgeBaseResponse.model_validate(kb) for kb in visible_kbs],
        template=WorkspaceTemplateResponse.model_validate(workspace.template) if workspace.template else None,
    )


@router.get("/{workspace_id}/telemetry", response_model=WorkspaceTelemetryResponse)
async def get_workspace_telemetry(
    workspace_id: int,
    limit: int = Query(25, ge=1, le=100, description="Maximum number of recent requests/traces"),
    include_langfuse_traces: bool = Query(
        True,
        description="Include traces fetched from Langfuse public API",
    ),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
):
    """Get workspace telemetry for recent chat requests and Langfuse traces."""
    workspace = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.id == workspace_id,
        RAGFlowDomain.customer_id == current_user.customer_id,
        RAGFlowDomain.is_active == True,
    ).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    recent_requests = _build_workspace_request_telemetry(
        db,
        workspace_id=workspace_id,
        customer_id=current_user.customer_id,
        limit=limit,
    )

    langfuse_service = get_langfuse_service()
    traces: List[WorkspaceLangfuseTraceItem] = []
    traces_fetch_error: Optional[str] = None

    if include_langfuse_traces:
        trace_payload, traces_fetch_error = await langfuse_service.fetch_workspace_traces(
            workspace_id=workspace_id,
            customer_id=current_user.customer_id,
            limit=limit,
        )
        for raw_trace in trace_payload:
            try:
                traces.append(WorkspaceLangfuseTraceItem.model_validate(raw_trace))
            except Exception:
                continue

    return WorkspaceTelemetryResponse(
        workspace_id=workspace.id,
        workspace_name=workspace.display_name or workspace.name,
        langfuse_enabled=bool(langfuse_service.enabled),
        langfuse_host=langfuse_service.host or None,
        langfuse_public_url=langfuse_service.public_url or None,
        langfuse_embed_url=langfuse_service.embed_url or None,
        langfuse_project_id=langfuse_service.project_id,
        recent_requests=recent_requests,
        traces=traces,
        traces_fetch_error=traces_fetch_error,
    )


@router.get("/{workspace_id}/prompt-template", response_model=WorkspacePromptTemplateResponse)
async def get_workspace_prompt_template_config(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access")),
):
    """Get the resolved workspace prompt template configuration."""
    workspace = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.id == workspace_id,
        RAGFlowDomain.customer_id == current_user.customer_id,
        RAGFlowDomain.is_active == True,
    ).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    template = get_workspace_prompt_template(
        workspace_id=workspace_id,
        customer_id=current_user.customer_id,
        db=db,
    )
    return WorkspacePromptTemplateResponse(**template.model_dump())


@router.put("/{workspace_id}/prompt-template", response_model=WorkspacePromptTemplateResponse)
async def update_workspace_prompt_template_config(
    workspace_id: int,
    request: WorkspacePromptTemplateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("workspaces:write")),
):
    """Update and persist workspace prompt template configuration."""
    workspace = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.id == workspace_id,
        RAGFlowDomain.customer_id == current_user.customer_id,
        RAGFlowDomain.is_active == True,
    ).first()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    current_template = get_workspace_prompt_template(
        workspace_id=workspace_id,
        customer_id=current_user.customer_id,
        db=db,
    )
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        return WorkspacePromptTemplateResponse(**current_template.model_dump())

    updated_template = current_template.model_copy(update=updates)
    if not updated_template.system_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="system_prompt cannot be empty",
        )

    updated_template.prompt_version = (current_template.prompt_version or 0) + 1
    saved = save_workspace_prompt_template(
        workspace_id=workspace_id,
        customer_id=current_user.customer_id,
        db=db,
        template=updated_template,
    )
    return WorkspacePromptTemplateResponse(**saved.model_dump())


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: int,
    request: WorkspaceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("workspaces:write"))
):
    """Update workspace settings."""
    workspace = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.id == workspace_id,
        RAGFlowDomain.customer_id == current_user.customer_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(workspace, field, value)
    
    db.commit()
    db.refresh(workspace)
    
    # Reload with relationships
    workspace = db.query(RAGFlowDomain).options(
        joinedload(RAGFlowDomain.template),
        joinedload(RAGFlowDomain.knowledge_bases)
    ).filter(RAGFlowDomain.id == workspace_id).first()
    
    return get_workspace_response(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("workspaces:write"))
):
    """
    Delete a workspace (soft delete).
    
    Sets is_active=False. Use permanently_delete for hard delete.
    """
    workspace = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.id == workspace_id,
        RAGFlowDomain.customer_id == current_user.customer_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    workspace.is_active = False
    db.commit()
    
    logger.info(
        "workspace_deleted",
        workspace_id=workspace_id,
        user_id=current_user.user_id
    )


# ==================== Knowledge Base Endpoints ====================

@router.get("/{workspace_id}/knowledge-bases", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access"))
):
    """List knowledge bases in a workspace."""
    # Verify workspace access
    workspace = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.id == workspace_id,
        RAGFlowDomain.customer_id == current_user.customer_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    access_service = KnowledgeBaseAccessService(db)
    accessible_kb_ids = access_service.resolve_accessible_kb_ids(
        workspace_id=workspace_id,
        user=current_user,
        required_permission=KnowledgeBasePermissionType.READ,
    )
    if not accessible_kb_ids:
        return KnowledgeBaseListResponse(knowledge_bases=[], total=0)

    knowledge_bases = db.query(KnowledgeBase).filter(
        KnowledgeBase.workspace_id == workspace_id,
        KnowledgeBase.is_active == True,
        KnowledgeBase.id.in_(accessible_kb_ids),
    ).order_by(KnowledgeBase.created_at.desc()).all()
    
    return KnowledgeBaseListResponse(
        knowledge_bases=[KnowledgeBaseResponse.model_validate(kb) for kb in knowledge_bases],
        total=len(knowledge_bases)
    )


@router.post("/{workspace_id}/knowledge-bases", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    workspace_id: int,
    request: KnowledgeBaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("workspaces:write"))
):
    """Create a new knowledge base in a workspace."""
    # Verify workspace access
    workspace = db.query(RAGFlowDomain).filter(
        RAGFlowDomain.id == workspace_id,
        RAGFlowDomain.customer_id == current_user.customer_id
    ).first()
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Check for duplicate name within workspace
    existing = db.query(KnowledgeBase).filter(
        KnowledgeBase.workspace_id == workspace_id,
        KnowledgeBase.name == request.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Knowledge base '{request.name}' already exists in this workspace"
        )
    
    try:
        tenant_storage_service = TenantStorageSettingsService(db)
        tenant_storage = tenant_storage_service.get_storage_settings(current_user.customer_id)
        tenant_storage_settings = {
            "backend": tenant_storage.backend.value if tenant_storage.backend else None,
            "bucket": tenant_storage.bucket,
            "default_local_source_path": tenant_storage.default_local_source_path,
        }
        source_type, source_config, storage_backend, storage_config = _resolve_kb_source_and_storage(
            kb_request=request,
            tenant_storage_settings=tenant_storage_settings,
        )

        knowledge_base = KnowledgeBase(
            workspace_id=workspace_id,
            customer_id=current_user.customer_id,
            name=request.name,
            description=request.description,
            parser_type=request.parser_type.value,
            parser_config=request.parser_config,
            embedding_model=request.embedding_model or "text-embedding-3-large@OpenAI",
            chunk_token_count=request.chunk_token_count or 512,
            similarity_threshold=request.similarity_threshold,
            top_k=request.top_k,
            source_type=source_type,
            source_config=source_config,
            storage_backend=storage_backend,
            storage_config=storage_config,
            status=KnowledgeBaseStatus.PENDING.value,
            created_by_user_id=current_user.user_id,
        )
        db.add(knowledge_base)
        db.commit()
        db.refresh(knowledge_base)

        if knowledge_base.source_type == KnowledgeBaseSourceType.S3.value:
            _enqueue_s3_kb_sync(
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base.id,
                customer_id=current_user.customer_id,
                trigger="kb_created",
            )
        
        logger.info(
            "knowledge_base_created",
            knowledge_base_id=knowledge_base.id,
            workspace_id=workspace_id,
            user_id=current_user.user_id
        )
        
        return KnowledgeBaseResponse.model_validate(knowledge_base)
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        db.rollback()
        logger.error("create_knowledge_base_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create knowledge base"
        )


@router.get("/{workspace_id}/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    workspace_id: int,
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access"))
):
    """Get knowledge base details."""
    knowledge_base = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.workspace_id == workspace_id,
        KnowledgeBase.customer_id == current_user.customer_id
    ).first()
    
    if not knowledge_base:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    if not check_kb_access(db, current_user, kb_id, KnowledgeBasePermissionType.READ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this knowledge base",
        )
    
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.post("/{workspace_id}/knowledge-bases/{kb_id}/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_knowledge_base_source(
    workspace_id: int,
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("workspaces:write")),
):
    """Queue source sync for an S3-backed knowledge base."""
    knowledge_base = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.workspace_id == workspace_id,
        KnowledgeBase.customer_id == current_user.customer_id,
        KnowledgeBase.is_active == True,
    ).first()

    if not knowledge_base:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )
    if not check_kb_access(db, current_user, kb_id, KnowledgeBasePermissionType.WRITE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to sync this knowledge base",
        )
    if knowledge_base.source_type != KnowledgeBaseSourceType.S3.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sync is only supported for S3-backed knowledge bases",
        )

    _enqueue_s3_kb_sync(
        workspace_id=workspace_id,
        knowledge_base_id=knowledge_base.id,
        customer_id=current_user.customer_id,
        trigger="manual_api",
    )
    return {"queued": True}


@router.patch("/{workspace_id}/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    workspace_id: int,
    kb_id: int,
    request: KnowledgeBaseUpdateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("workspaces:write"))
):
    """Update knowledge base settings."""
    knowledge_base = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.workspace_id == workspace_id,
        KnowledgeBase.customer_id == current_user.customer_id
    ).first()
    
    if not knowledge_base:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    if not check_kb_access(db, current_user, kb_id, KnowledgeBasePermissionType.WRITE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to modify this knowledge base",
        )
    
    update_data = request.model_dump(exclude_unset=True)
    
    # Handle enum conversion for parser_type
    if 'parser_type' in update_data and update_data['parser_type']:
        update_data['parser_type'] = update_data['parser_type'].value

    tenant_storage_service = TenantStorageSettingsService(db)
    tenant_storage = tenant_storage_service.get_storage_settings(current_user.customer_id)
    tenant_storage_settings = {
        "backend": tenant_storage.backend.value if tenant_storage.backend else None,
        "bucket": tenant_storage.bucket,
        "default_local_source_path": tenant_storage.default_local_source_path,
    }
    try:
        source_type, source_config, storage_backend, storage_config = _resolve_kb_source_and_storage(
            kb_request=request,
            tenant_storage_settings=tenant_storage_settings,
            existing_source_type=knowledge_base.source_type,
            existing_storage_backend=knowledge_base.storage_backend,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if request.source_type is not None:
        update_data["source_type"] = source_type
        update_data["source_config"] = source_config
    elif request.source_config is not None:
        update_data["source_config"] = source_config

    if request.storage_backend is not None:
        update_data["storage_backend"] = storage_backend
    if request.storage_config is not None:
        update_data["storage_config"] = storage_config
    
    for field, value in update_data.items():
        setattr(knowledge_base, field, value)
    
    db.commit()
    db.refresh(knowledge_base)

    if (
        knowledge_base.source_type == KnowledgeBaseSourceType.S3.value
        and (request.source_type is not None or request.source_config is not None)
    ):
        _enqueue_s3_kb_sync(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base.id,
            customer_id=current_user.customer_id,
            trigger="kb_updated",
        )
    
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.delete("/{workspace_id}/knowledge-bases/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    workspace_id: int,
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("workspaces:write"))
):
    """Delete a knowledge base (soft delete)."""
    knowledge_base = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.workspace_id == workspace_id,
        KnowledgeBase.customer_id == current_user.customer_id
    ).first()
    
    if not knowledge_base:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    if not check_kb_access(db, current_user, kb_id, KnowledgeBasePermissionType.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to delete this knowledge base",
        )
    
    knowledge_base.is_active = False
    db.commit()
    
    logger.info(
        "knowledge_base_deleted",
        knowledge_base_id=kb_id,
        workspace_id=workspace_id,
        user_id=current_user.user_id
    )


# ==================== Chat History Endpoints ====================

@chat_router.get("/history", response_model=ChatHistoryResponse)
def get_chat_history(
    workspace_id: Optional[int] = Query(None, description="Filter by workspace"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access"))
):
    """
    Get user's chat history across all workspaces.
    
    Returns conversations sorted by last activity, optionally filtered by workspace.
    
    Note: Uses plain `def` (not `async def`) so FastAPI runs it in a threadpool,
    preventing sync SQLAlchemy queries from blocking the event loop.
    """
    query = db.query(RAGFlowConversation).join(
        RAGFlowDomain, RAGFlowConversation.domain_id == RAGFlowDomain.id
    ).filter(
        RAGFlowConversation.user_id == current_user.user_id,
        RAGFlowConversation.customer_id == current_user.customer_id,
        RAGFlowConversation.is_active == True,
        RAGFlowDomain.is_active == True
    )
    
    if workspace_id:
        query = query.filter(RAGFlowConversation.domain_id == workspace_id)
    
    total = query.count()
    
    offset = (page - 1) * page_size
    conversations = query.order_by(
        func.coalesce(
            RAGFlowConversation.last_message_at,
            RAGFlowConversation.created_at
        ).desc()
    ).offset(offset).limit(page_size).all()
    
    # Batch-load workspace info to avoid N+1 queries
    domain_ids = {conv.domain_id for conv in conversations}
    domains = db.query(RAGFlowDomain).filter(RAGFlowDomain.id.in_(domain_ids)).all() if domain_ids else []
    domain_map = {d.id: d for d in domains}
    
    conversation_summaries = []
    for conv in conversations:
        workspace = domain_map.get(conv.domain_id)
        if workspace:
            conversation_summaries.append(ConversationSummary(
                id=conv.id,
                uuid=conv.uuid,
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                workspace_display_name=workspace.display_name,
                workspace_color=workspace.color,
                title=conv.title,
                message_count=conv.message_count,
                last_message_at=conv.last_message_at,
                created_at=conv.created_at,
            ))
    
    return ChatHistoryResponse(
        conversations=conversation_summaries,
        total=total,
        page=page,
        page_size=page_size
    )


@chat_router.get("/workspaces", response_model=WorkspacePickerResponse)
def get_workspace_picker(
    search: Optional[str] = Query(None, description="Search workspaces"),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("assistant:access"))
):
    """
    Get workspaces available for starting a new chat.
    
    Returns workspaces the user has access to, with availability status.
    
    Note: Uses plain `def` (not `async def`) so FastAPI runs it in a threadpool,
    preventing sync SQLAlchemy queries from blocking the event loop.
    """
    query = db.query(RAGFlowDomain).options(
        joinedload(RAGFlowDomain.template)
    ).filter(
        RAGFlowDomain.customer_id == current_user.customer_id,
        RAGFlowDomain.is_active == True
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            RAGFlowDomain.name.ilike(search_term),
            RAGFlowDomain.display_name.ilike(search_term)
        ))
    
    workspaces = query.order_by(RAGFlowDomain.display_name).all()
    
    access_service = KnowledgeBaseAccessService(db)
    picker_items = []
    for w in workspaces:
        accessible_kb_ids = access_service.resolve_accessible_kb_ids(
            workspace_id=w.id,
            user=current_user,
            required_permission=KnowledgeBasePermissionType.READ,
        )
        accessible_document_count = 0
        if accessible_kb_ids:
            accessible_document_count = int(
                db.query(func.coalesce(func.sum(KnowledgeBase.document_count), 0))
                .filter(
                    KnowledgeBase.workspace_id == w.id,
                    KnowledgeBase.id.in_(accessible_kb_ids),
                    KnowledgeBase.is_active == True,
                )
                .scalar()
                or 0
            )

        # Workspace is available if it's ready or has documents
        template_name = w.template.name if w.template else None
        is_agent_mesh = template_name == "agent_mesh_retrieval"
        is_available = (
            w.status == RAGFlowDomainStatus.READY or 
            accessible_document_count > 0 or
            (w.template and w.template.name == "data_analytics") or  # Data analytics doesn't need docs
            is_agent_mesh  # Agent Mesh uses connected sources, not uploaded docs
        )
        
        picker_items.append(WorkspacePickerItem(
            id=w.id,
            name=w.name,
            display_name=w.display_name,
            description=w.description,
            icon=w.icon,
            color=w.color,
            template_name=template_name,
            template_display_name=w.template.display_name if w.template else None,
            document_count=accessible_document_count,
            is_available=is_available,
        ))
    
    return WorkspacePickerResponse(
        workspaces=picker_items,
        total=len(picker_items)
    )
