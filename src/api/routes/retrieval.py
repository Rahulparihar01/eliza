"""
Retrieval API routes – multi-source data search.

POST /api/retrieval/search                – enqueue a retrieval run
GET  /api/retrieval/runs/{run_id}         – poll run status / results
GET  /api/retrieval/conversations          – list user conversations
GET  /api/retrieval/conversations/{id}     – get conversation + messages
PATCH /api/retrieval/conversations/{id}    – rename conversation
DELETE /api/retrieval/conversations/{id}   – delete conversation
"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from src.models import get_db
from src.models.retrieval import (
    RetrievalRun,
    RetrievalConversation,
    RetrievalMessage,
)
from src.models.ragflow_domain import RAGFlowDomain
from src.models.workspace import WorkspaceTemplate
from src.middleware.authorization import AuthorizationMiddleware
from src.core.auth_context import CurrentUserContext
from src.api.schemas.retrieval import (
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalRunResponse,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationMessageResponse,
    RenameConversationRequest,
)
from src.tasks.retrieval_tasks import run_retrieval


logger = logging.getLogger(__name__)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/api/retrieval", tags=["Retrieval"])


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #


@router.post(
    "/search",
    response_model=RetrievalSearchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a data search query",
)
async def search(
    req: RetrievalSearchRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_any_permission(["documents:read", "assistant:access"])
    ),
):
    """Enqueue a retrieval run and return the run_id for polling."""
    run_id = str(uuid.uuid4())
    conversation_id = req.conversation_id

    workspace = (
        db.query(RAGFlowDomain)
        .join(WorkspaceTemplate, RAGFlowDomain.template_id == WorkspaceTemplate.id)
        .filter(
            RAGFlowDomain.id == req.workspace_id,
            RAGFlowDomain.customer_id == current_user.customer_id,
            RAGFlowDomain.is_active == True,
            WorkspaceTemplate.name == "agent_mesh_retrieval",
        )
        .first()
    )
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent Mesh workspace not found",
        )

    # Auto-create a conversation if none provided
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        conv = RetrievalConversation(
            id=conversation_id,
            customer_id=current_user.customer_id,
            user_id=current_user.user_id,
            workspace_id=req.workspace_id,
            title=None,  # Will be auto-generated after first response
        )
        db.add(conv)
    else:
        conv = (
            db.query(RetrievalConversation)
            .filter(
                RetrievalConversation.id == conversation_id,
                RetrievalConversation.customer_id == current_user.customer_id,
                RetrievalConversation.user_id == current_user.user_id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conv.workspace_id is None:
            conv.workspace_id = req.workspace_id
        elif conv.workspace_id != req.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conversation belongs to a different workspace",
            )

    # Save the user message
    user_msg = RetrievalMessage(
        conversation_id=conversation_id,
        role="user",
        content=req.query.strip(),
    )
    db.add(user_msg)

    # Persist the run stub
    run = RetrievalRun(
        run_id=run_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        conversation_id=conversation_id,
        query_text=req.query,
        status="queued",
    )
    db.add(run)
    db.commit()

    # Dispatch to Celery
    run_retrieval.delay(
        run_id=run_id,
        query=req.query,
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        conversation_id=conversation_id,
        workspace_id=req.workspace_id,
    )

    return RetrievalSearchResponse(
        run_id=run_id,
        status="queued",
        workspace_id=req.workspace_id,
        conversation_id=conversation_id,
    )


# --------------------------------------------------------------------------- #
# Poll results
# --------------------------------------------------------------------------- #


@router.get(
    "/runs/{run_id}",
    response_model=RetrievalRunResponse,
    summary="Get retrieval run status and results",
)
async def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_any_permission(["documents:read", "assistant:access"])
    ),
):
    """Poll a retrieval run by its ID."""
    run = (
        db.query(RetrievalRun)
        .filter(
            RetrievalRun.run_id == run_id,
            RetrievalRun.customer_id == current_user.customer_id,
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Retrieval run not found")

    # If the run failed because of missing auth, surface that to the frontend
    auth_required = None
    if run.status == "failed" and run.results_json and run.results_json.get("error", "").startswith("No connected"):
        auth_required = {"source_type": "hubspot", "message": run.results_json["error"]}

    # Extract follow-ups from results if present
    follow_ups = None
    if run.status == "completed" and run.results_json:
        follow_ups = run.results_json.get("follow_ups")

    return RetrievalRunResponse(
        run_id=run.run_id,
        status=run.status,
        query=run.query_text,
        results=run.results_json if run.status == "completed" else None,
        sources=run.sources_used,
        follow_ups=follow_ups,
        created_at=run.created_at,
        completed_at=run.completed_at,
        auth_required=auth_required,
    )


# --------------------------------------------------------------------------- #
# Conversations
# --------------------------------------------------------------------------- #


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
    summary="List user conversations",
)
async def list_conversations(
    workspace_id: int | None = Query(None, description="Filter by workspace"),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_any_permission(["documents:read", "assistant:access"])
    ),
):
    """Return conversations for the current user, newest first."""
    query = (
        db.query(RetrievalConversation)
        .filter(
            RetrievalConversation.customer_id == current_user.customer_id,
            RetrievalConversation.user_id == current_user.user_id,
        )
    )
    if workspace_id is not None:
        query = query.filter(RetrievalConversation.workspace_id == workspace_id)

    convs = query.order_by(RetrievalConversation.updated_at.desc()).limit(50).all()

    results = []
    for conv in convs:
        # Count messages and get preview
        msg_count = (
            db.query(sa_func.count(RetrievalMessage.id))
            .filter(RetrievalMessage.conversation_id == conv.id)
            .scalar()
        )
        last_msg = (
            db.query(RetrievalMessage)
            .filter(RetrievalMessage.conversation_id == conv.id)
            .order_by(RetrievalMessage.created_at.desc())
            .first()
        )
        preview = None
        if last_msg:
            preview = last_msg.content[:120] + ("..." if len(last_msg.content) > 120 else "")

        results.append(ConversationResponse(
            id=conv.id,
            workspace_id=conv.workspace_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count or 0,
            preview=preview,
        ))

    return results


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation with messages",
)
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_any_permission(["documents:read", "assistant:access"])
    ),
):
    """Return a conversation and all its messages."""
    conv = (
        db.query(RetrievalConversation)
        .filter(
            RetrievalConversation.id == conversation_id,
            RetrievalConversation.customer_id == current_user.customer_id,
            RetrievalConversation.user_id == current_user.user_id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(RetrievalMessage)
        .filter(RetrievalMessage.conversation_id == conversation_id)
        .order_by(RetrievalMessage.created_at.asc())
        .all()
    )

    return ConversationDetailResponse(
        id=conv.id,
        workspace_id=conv.workspace_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            ConversationMessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                sources=m.sources,
                follow_ups=m.follow_ups,
                run_id=m.run_id,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Rename a conversation",
)
async def rename_conversation(
    conversation_id: str,
    req: RenameConversationRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_any_permission(["documents:read", "assistant:access"])
    ),
):
    """Update the title of a conversation."""
    conv = (
        db.query(RetrievalConversation)
        .filter(
            RetrievalConversation.id == conversation_id,
            RetrievalConversation.customer_id == current_user.customer_id,
            RetrievalConversation.user_id == current_user.user_id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.title = req.title
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    msg_count = (
        db.query(sa_func.count(RetrievalMessage.id))
        .filter(RetrievalMessage.conversation_id == conv.id)
        .scalar()
    )

    return ConversationResponse(
        id=conv.id,
        workspace_id=conv.workspace_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=msg_count or 0,
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_any_permission(["documents:read", "assistant:access"])
    ),
):
    """Delete a conversation and all its messages."""
    conv = (
        db.query(RetrievalConversation)
        .filter(
            RetrievalConversation.id == conversation_id,
            RetrievalConversation.customer_id == current_user.customer_id,
            RetrievalConversation.user_id == current_user.user_id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Delete messages first (cascade should handle this, but be explicit)
    db.query(RetrievalMessage).filter(
        RetrievalMessage.conversation_id == conversation_id
    ).delete()
    db.delete(conv)
    db.commit()
