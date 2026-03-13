"""
RAG knowledge-base source sync tasks.

Schedules and executes S3-prefix sync for knowledge bases so newly uploaded
PDFs are parsed/chunked/indexed automatically.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict

from src.celery_app import celery_app
from src.core.config import get_settings
from src.core.logging import get_logger
from src.models import database
from src.models.workspace import KnowledgeBase, KnowledgeBaseSourceType
from src.services.kb_s3_sync_service import KnowledgeBaseS3SyncService

try:
    import redis
except Exception:  # pragma: no cover - defensive fallback if redis package unavailable
    redis = None

logger = get_logger(__name__)


def _get_db_session():
    """Initialize and return a scoped DB session for Celery tasks."""
    if database.SessionLocal is None:
        database.init_database()
    if database.SessionLocal is None:
        raise RuntimeError("SessionLocal is unavailable")
    return database.SessionLocal()


def _acquire_kb_sync_lock(
    *,
    workspace_id: int,
    knowledge_base_id: int,
    ttl_seconds: int = 4 * 60 * 60,
):
    """
    Acquire a best-effort distributed lock per KB sync.

    Prevents overlapping sync runs for the same workspace+KB pair.
    """
    if redis is None:
        return None, None, None

    redis_url = (
        os.getenv("CELERY_BROKER_URL")
        or os.getenv("REDIS_URL")
        or "redis://redis:6379/0"
    )
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    key = f"ragflow:kb_sync_lock:{workspace_id}:{knowledge_base_id}"
    token = str(uuid.uuid4())
    acquired = bool(client.set(key, token, nx=True, ex=max(300, int(ttl_seconds))))
    if not acquired:
        return key, None, client
    return key, token, client


def _release_kb_sync_lock(*, client, key: str | None, token: str | None) -> None:
    """Release lock only if token still matches to avoid stealing another run's lock."""
    if client is None or not key or not token:
        return
    try:
        current = client.get(key)
        if current == token:
            client.delete(key)
    except Exception:
        logger.warning("kb_s3_sync_lock_release_failed", key=key, exc_info=True)


@celery_app.task(
    bind=True,
    name="ragflow.process_s3_document",
    queue="rag_ingestion",
    autoretry_for=(),
    max_retries=2,
    default_retry_delay=30,
)
def process_s3_document(
    self,
    doc_id: int,
    customer_id: str,
) -> Dict[str, Any]:
    """Download a single S3 document and run parse/chunk/index."""
    db = _get_db_session()
    try:
        from src.services.native_rag_service import NativeRAGService

        service = NativeRAGService(db)
        asyncio.run(service.process_document_from_s3(doc_id, customer_id))
        logger.info(
            "process_s3_document_complete",
            doc_id=doc_id,
            customer_id=customer_id,
        )
        return {"doc_id": doc_id, "status": "ok"}
    except Exception as exc:
        logger.error(
            "process_s3_document_failed",
            doc_id=doc_id,
            customer_id=customer_id,
            error=str(exc),
            exc_info=True,
        )
        return {"doc_id": doc_id, "status": "error", "error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="ragflow.sync_s3_knowledge_base",
    queue="rag_ingestion",
    autoretry_for=(),
    max_retries=0,
)
def sync_s3_knowledge_base(
    self,
    workspace_id: int,
    knowledge_base_id: int,
    customer_id: str,
    trigger: str = "manual",
) -> Dict[str, Any]:
    """Sync a single S3-backed KB into the native RAG pipeline."""
    lock_key = None
    lock_token = None
    lock_client = None
    db = _get_db_session()
    try:
        lock_key, lock_token, lock_client = _acquire_kb_sync_lock(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
        )
        if lock_key and lock_token is None:
            logger.info(
                "kb_s3_sync_skipped_already_running",
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                trigger=trigger,
            )
            return {
                "workspace_id": workspace_id,
                "knowledge_base_id": knowledge_base_id,
                "customer_id": customer_id,
                "trigger": trigger,
                "skipped": "already_running",
                "ingested": 0,
                "failed": 0,
            }

        service = KnowledgeBaseS3SyncService(db)
        result = asyncio.run(
            service.sync_knowledge_base(
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                customer_id=customer_id,
                trigger=trigger,
            )
        )

        queued_doc_ids = result.get("ingested_document_ids") or []
        for doc_id in queued_doc_ids:
            process_s3_document.delay(doc_id=doc_id, customer_id=customer_id)

        logger.info(
            "kb_s3_sync_complete",
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            trigger=trigger,
            ingested=result.get("ingested", 0),
            queued_processing=len(queued_doc_ids),
            failed=result.get("failed", 0),
            skipped_existing=result.get("skipped_existing", 0),
        )
        return result
    except Exception as exc:
        logger.error(
            "kb_s3_sync_failed",
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            trigger=trigger,
            error=str(exc),
            exc_info=True,
        )
        return {
            "workspace_id": workspace_id,
            "knowledge_base_id": knowledge_base_id,
            "customer_id": customer_id,
            "trigger": trigger,
            "error": str(exc),
            "ingested": 0,
            "failed": 1,
        }
    finally:
        db.close()
        _release_kb_sync_lock(client=lock_client, key=lock_key, token=lock_token)


@celery_app.task(
    bind=True,
    name="ragflow.schedule_s3_kb_syncs",
    queue="rag_ingestion",
    autoretry_for=(),
    max_retries=0,
)
def schedule_s3_kb_syncs(self) -> Dict[str, Any]:
    """Schedule per-KB S3 sync tasks for all active S3-backed KBs."""
    settings = get_settings()
    if not settings.rag_kb_s3_sync_enabled:
        return {
            "scheduled": 0,
            "skipped": "sync_disabled",
        }

    db = _get_db_session()
    try:
        knowledge_bases = (
            db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.is_active == True,
                KnowledgeBase.source_type == KnowledgeBaseSourceType.S3.value,
            )
            .all()
        )

        scheduled = 0
        skipped_disabled = 0
        skipped_indexing = 0
        skipped_invalid_source = 0

        for kb in knowledge_bases:
            source_config = kb.source_config if isinstance(kb.source_config, dict) else {}
            sync_enabled = source_config.get("sync_enabled", True)
            if isinstance(sync_enabled, str):
                sync_enabled = sync_enabled.strip().lower() not in {"0", "false", "no", "off"}
            if sync_enabled is False:
                skipped_disabled += 1
                continue

            raw_source_path = (
                source_config.get("s3_path")
                or source_config.get("prefix")
                or source_config.get("path")
                or ""
            )
            if not str(raw_source_path).strip():
                skipped_invalid_source += 1
                logger.warning(
                    "kb_s3_sync_skipped_missing_source_path",
                    workspace_id=kb.workspace_id,
                    knowledge_base_id=kb.id,
                    customer_id=kb.customer_id,
                )
                continue

            if str(kb.status or "").strip().lower() == "indexing":
                skipped_indexing += 1
                continue

            sync_s3_knowledge_base.delay(
                workspace_id=kb.workspace_id,
                knowledge_base_id=kb.id,
                customer_id=kb.customer_id,
                trigger="scheduled",
            )
            scheduled += 1

        payload = {
            "total_s3_kbs": len(knowledge_bases),
            "scheduled": scheduled,
            "skipped_disabled": skipped_disabled,
            "skipped_invalid_source": skipped_invalid_source,
            "skipped_indexing": skipped_indexing,
        }
        logger.info("kb_s3_sync_schedule_dispatch", **payload)
        return payload
    finally:
        db.close()
