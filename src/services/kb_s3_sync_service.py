"""
Knowledge-base S3 sync service.

Syncs PDFs from a configured S3 prefix into a workspace knowledge base by
reusing the native parse/chunk/embed/index pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.models.ragflow_domain import RAGFlowDomain, RAGFlowDocument, RAGFlowDocumentStatus
from src.models.workspace import KnowledgeBase, KnowledgeBaseSourceType, KnowledgeBaseStatus
from src.services.native_rag_service import NativeRAGService

logger = logging.getLogger(__name__)


@dataclass
class S3SourceSpec:
    """Normalized S3 source configuration for KB sync."""

    bucket: str
    prefix: str
    sync_enabled: bool
    max_files_per_sync: int
    stale_inflight_seconds: int
    file_extensions: List[str]


def _parse_bool(value: Any, default: bool = True) -> bool:
    """Parse permissive boolean values from JSON-like source config."""
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
    """Parse and clamp integer settings from source config."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _parse_s3_path(value: str) -> Tuple[Optional[str], str]:
    """
    Parse either:
    - s3://bucket/path/to/prefix
    - path/to/prefix
    """
    normalized = value.strip()
    if not normalized:
        return None, ""
    if normalized.lower().startswith("s3://"):
        path_without_scheme = normalized[5:]
        bucket, _, prefix = path_without_scheme.partition("/")
        return (bucket.strip() or None), prefix.strip().strip("/")
    return None, normalized.strip().strip("/")


class KnowledgeBaseS3SyncService:
    """Sync PDFs from S3 source path into a knowledge base."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.rag_service = NativeRAGService(db)
        self.object_storage_service = self.rag_service.object_storage_service

    def _resolve_source_spec(self, kb: KnowledgeBase) -> S3SourceSpec:
        """Resolve and validate S3 source config for a knowledge base."""
        source_config = kb.source_config if isinstance(kb.source_config, dict) else {}
        tenant_storage = self.object_storage_service.settings_service.resolve_storage_config(kb.customer_id)
        tenant_bucket = tenant_storage.bucket if tenant_storage else None

        raw_path = str(
            source_config.get("s3_path")
            or source_config.get("prefix")
            or source_config.get("path")
            or ""
        ).strip()
        bucket_from_path, prefix = _parse_s3_path(raw_path)
        bucket = str(source_config.get("bucket") or "").strip() or bucket_from_path or tenant_bucket or ""

        if not raw_path:
            raise ValueError(
                f"Knowledge base {kb.id} is missing S3 source path. "
                "Set source_config.prefix (or source_config.s3_path)."
            )
        if not bucket:
            raise ValueError(
                f"Knowledge base {kb.id} cannot resolve S3 bucket. "
                "Configure tenant storage bucket or source_config.bucket."
            )

        extensions_raw = source_config.get("file_extensions")
        extensions: List[str] = []
        if isinstance(extensions_raw, list):
            for ext in extensions_raw:
                if not isinstance(ext, str):
                    continue
                normalized_ext = ext.strip().lower()
                if not normalized_ext:
                    continue
                if not normalized_ext.startswith("."):
                    normalized_ext = f".{normalized_ext}"
                extensions.append(normalized_ext)
        if not extensions:
            extensions = [".pdf", ".docx", ".doc", ".pptx", ".ppt"]

        return S3SourceSpec(
            bucket=bucket,
            prefix=prefix,
            sync_enabled=_parse_bool(source_config.get("sync_enabled"), default=True),
            max_files_per_sync=_parse_positive_int(
                source_config.get("max_files_per_sync"),
                default=self.settings.rag_kb_s3_sync_max_files_per_run,
                minimum=1,
                maximum=1000,
            ),
            stale_inflight_seconds=_parse_positive_int(
                source_config.get("stale_inflight_seconds"),
                default=1800,
                minimum=300,
                maximum=86400,
            ),
            file_extensions=extensions,
        )

    @staticmethod
    def _mime_type_from_filename(filename: str) -> str:
        """Resolve MIME type from filename extension."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc": "application/msword",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "ppt": "application/vnd.ms-powerpoint",
            "txt": "text/plain",
            "md": "text/markdown",
            "html": "text/html",
            "htm": "text/html",
        }.get(ext, "application/pdf")

    @staticmethod
    def _get_doc_source_metadata(doc: RAGFlowDocument) -> Dict[str, Any]:
        """Extract source metadata from document metadata payload."""
        metadata = doc.document_metadata if isinstance(doc.document_metadata, dict) else {}
        source = metadata.get("source")
        return source if isinstance(source, dict) else {}

    def _load_existing_docs_by_object_key(
        self,
        *,
        workspace_id: int,
        knowledge_base_id: int,
        customer_id: str,
    ) -> Dict[str, RAGFlowDocument]:
        """Build a map of already-synced S3 objects for this KB."""
        docs = (
            self.db.query(RAGFlowDocument)
            .filter(
                RAGFlowDocument.domain_id == workspace_id,
                RAGFlowDocument.knowledge_base_id == knowledge_base_id,
                RAGFlowDocument.customer_id == customer_id,
            )
            .all()
        )

        by_object_key: Dict[str, RAGFlowDocument] = {}
        for doc in docs:
            source = self._get_doc_source_metadata(doc)
            if str(source.get("type") or "").strip().lower() != "s3_sync":
                continue
            object_key = str(source.get("object_key") or "").strip()
            if object_key:
                by_object_key[object_key] = doc
        return by_object_key

    async def sync_knowledge_base(
        self,
        *,
        workspace_id: int,
        knowledge_base_id: int,
        customer_id: str,
        trigger: str = "manual",
    ) -> Dict[str, Any]:
        """
        Sync S3 PDFs for one knowledge base.

        Returns ingestion summary and never hides partial progress.
        """
        result: Dict[str, Any] = {
            "workspace_id": workspace_id,
            "knowledge_base_id": knowledge_base_id,
            "customer_id": customer_id,
            "trigger": trigger,
            "scanned": 0,
            "ingested": 0,
            "replaced": 0,
            "failed": 0,
            "skipped_existing": 0,
            "skipped_inflight": 0,
            "recovered_stale_inflight": 0,
            "skipped_non_pdf": 0,
            "limit_reached": False,
            "errors": [],
            "ingested_document_ids": [],
        }

        kb = (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.id == knowledge_base_id,
                KnowledgeBase.workspace_id == workspace_id,
                KnowledgeBase.customer_id == customer_id,
                KnowledgeBase.is_active == True,
            )
            .first()
        )
        if not kb:
            raise ValueError(f"Knowledge base {knowledge_base_id} not found")
        if kb.source_type != KnowledgeBaseSourceType.S3.value:
            result["skipped"] = "knowledge_base_source_is_not_s3"
            return result

        workspace = (
            self.db.query(RAGFlowDomain)
            .filter(
                RAGFlowDomain.id == workspace_id,
                RAGFlowDomain.customer_id == customer_id,
            )
            .first()
        )
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        spec = self._resolve_source_spec(kb)
        if trigger == "scheduled" and not spec.sync_enabled:
            result["skipped"] = "sync_disabled"
            return result

        kb.status = KnowledgeBaseStatus.INDEXING.value
        kb.last_error = None
        self.db.commit()

        existing_by_object_key = self._load_existing_docs_by_object_key(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            customer_id=customer_id,
        )

        continuation_token: Optional[str] = None
        while True:
            listing = await self.object_storage_service.list_objects(
                customer_id=customer_id,
                bucket=spec.bucket,
                prefix=spec.prefix,
                continuation_token=continuation_token,
                max_keys=1000,
            )

            objects = listing.get("objects") or []
            for obj in objects:
                object_key = str(obj.get("key") or "").strip()
                if not object_key:
                    continue

                result["scanned"] += 1
                lower_key = object_key.lower()
                if not any(lower_key.endswith(ext) for ext in spec.file_extensions):
                    result["skipped_non_pdf"] += 1
                    continue

                existing_doc = existing_by_object_key.get(object_key)
                current_etag = str(obj.get("etag") or "").strip()
                if existing_doc:
                    existing_source = self._get_doc_source_metadata(existing_doc)
                    existing_etag = str(existing_source.get("etag") or "").strip()
                    if existing_doc.status in {
                        RAGFlowDocumentStatus.PENDING,
                        RAGFlowDocumentStatus.PARSING,
                    }:
                        started_at = (
                            existing_doc.processing_started_at
                            or existing_doc.updated_at
                            or existing_doc.created_at
                        )
                        age_seconds: Optional[float] = None
                        if started_at is not None:
                            reference_started_at = (
                                started_at.replace(tzinfo=None)
                                if getattr(started_at, "tzinfo", None) is not None
                                else started_at
                            )
                            age_seconds = max(
                                0.0,
                                (datetime.utcnow() - reference_started_at).total_seconds(),
                            )
                        if (
                            age_seconds is None
                            or age_seconds < float(spec.stale_inflight_seconds)
                        ):
                            result["skipped_inflight"] += 1
                            continue

                        logger.warning(
                            "kb_s3_sync_recover_stale_inflight workspace_id=%s kb_id=%s object_key=%s doc_id=%s age_seconds=%s",
                            workspace_id,
                            knowledge_base_id,
                            object_key,
                            existing_doc.id,
                            int(age_seconds),
                        )
                        existing_doc.status = RAGFlowDocumentStatus.FAILED
                        existing_doc.progress = -1
                        existing_doc.processing_error = (
                            f"Recovered stale inflight document after {int(age_seconds)}s"
                        )
                        existing_doc.processing_completed_at = datetime.utcnow()
                        self.db.commit()
                        result["recovered_stale_inflight"] += 1

                    if (
                        existing_doc.status == RAGFlowDocumentStatus.COMPLETED
                        and existing_etag
                        and current_etag
                        and existing_etag == current_etag
                    ):
                        result["skipped_existing"] += 1
                        continue

                    await self.rag_service.delete_document(existing_doc.id, customer_id)
                    existing_by_object_key.pop(object_key, None)
                    result["replaced"] += 1

                if result["ingested"] >= spec.max_files_per_sync:
                    result["limit_reached"] = True
                    break

                try:
                    filename = object_key.rsplit("/", 1)[-1] or "document.pdf"
                    mime_type = self._mime_type_from_filename(filename)
                    file_size = int(obj.get("size") or 0)
                    sync_metadata = {
                        "source": {
                            "type": "s3_sync",
                            "bucket": spec.bucket,
                            "object_key": object_key,
                            "etag": current_etag,
                            "size_bytes": file_size,
                            "last_modified": obj.get("last_modified"),
                            "synced_at": datetime.utcnow().isoformat(),
                            "trigger": trigger,
                        },
                        "storage": {
                            "backend": "s3",
                            "bucket": spec.bucket,
                            "object_key": object_key,
                            "managed": False,
                        },
                    }

                    registered_doc = await self.rag_service.register_external_document(
                        domain_id=workspace_id,
                        customer_id=customer_id,
                        knowledge_base_id=knowledge_base_id,
                        filename=filename,
                        file_size=file_size,
                        mime_type=mime_type,
                        document_metadata=sync_metadata,
                    )
                    existing_by_object_key[object_key] = registered_doc
                    result["ingested"] += 1
                    result["ingested_document_ids"].append(registered_doc.id)
                except Exception as exc:
                    result["failed"] += 1
                    message = f"{object_key}: {exc}"
                    if len(result["errors"]) < 25:
                        result["errors"].append(message)
                    logger.warning(
                        "kb_s3_sync_object_failed workspace_id=%s kb_id=%s object_key=%s error=%s",
                        workspace_id,
                        knowledge_base_id,
                        object_key,
                        str(exc),
                    )

            if result["limit_reached"]:
                break

            next_token = listing.get("next_token")
            if not next_token:
                break
            continuation_token = str(next_token)

        if result["errors"]:
            kb.last_error = result["errors"][0]
        else:
            kb.last_error = None
        kb.last_sync_at = datetime.utcnow()

        await self.rag_service._refresh_workspace_and_kb_stats(
            domain_id=workspace_id,
            customer_id=customer_id,
            knowledge_base_id=knowledge_base_id,
        )
        self.db.commit()
        return result
