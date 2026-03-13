"""
PDF Cache Service - Local MinIO cache for cited document PDFs.

After RAG synthesis identifies cited documents, this service pre-fetches
those PDFs into a local MinIO bucket so they're ready when users click
"Show PDF". On subsequent requests the cached copy is served directly.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.core.config import get_settings

logger = logging.getLogger(__name__)

CACHE_BUCKET = "pdf-cache"


class PDFCacheService:
    """Manages a local MinIO PDF cache bucket."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        import boto3
        from botocore.client import Config as BotoConfig

        endpoint = self.settings.pdf_cache_endpoint or self.settings.minio_endpoint
        access_key = self.settings.pdf_cache_access_key or self.settings.minio_access_key
        secret_key = self.settings.pdf_cache_secret_key or self.settings.minio_secret_key

        if not endpoint or not access_key or not secret_key:
            return None

        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
            region_name="us-east-1",
            config=BotoConfig(s3={"addressing_style": "path"}),
        )
        self._ensure_bucket()
        return self._client

    def _ensure_bucket(self):
        try:
            self._client.head_bucket(Bucket=CACHE_BUCKET)
        except Exception:
            try:
                self._client.create_bucket(Bucket=CACHE_BUCKET)
            except Exception as exc:
                logger.warning("pdf_cache_bucket_create_failed: %s", exc)

    @staticmethod
    def _cache_key(document_id: int) -> str:
        return f"doc_{document_id}.pdf"

    async def get_cached_pdf(self, document_id: int) -> Optional[bytes]:
        """Return cached PDF bytes or None if not cached."""
        client = self._get_client()
        if not client:
            return None
        loop = asyncio.get_running_loop()
        try:
            def _get():
                resp = client.get_object(
                    Bucket=CACHE_BUCKET,
                    Key=self._cache_key(document_id),
                )
                body = resp.get("Body")
                data = body.read() if body else b""
                if body:
                    body.close()
                return data
            return await loop.run_in_executor(None, _get)
        except Exception:
            return None

    async def cache_pdf(self, document_id: int, pdf_bytes: bytes) -> bool:
        """Store PDF bytes in the local cache."""
        client = self._get_client()
        if not client or not pdf_bytes:
            return False
        loop = asyncio.get_running_loop()
        try:
            def _put():
                client.put_object(
                    Bucket=CACHE_BUCKET,
                    Key=self._cache_key(document_id),
                    Body=pdf_bytes,
                    ContentType="application/pdf",
                )
            await loop.run_in_executor(None, _put)
            logger.info("pdf_cached doc_id=%s size=%d", document_id, len(pdf_bytes))
            return True
        except Exception as exc:
            logger.warning("pdf_cache_put_failed doc_id=%s: %s", document_id, exc)
            return False

    async def is_cached(self, document_id: int) -> bool:
        """Check if a PDF is in the cache without fetching it."""
        client = self._get_client()
        if not client:
            return False
        loop = asyncio.get_running_loop()
        try:
            def _head():
                client.head_object(Bucket=CACHE_BUCKET, Key=self._cache_key(document_id))
            await loop.run_in_executor(None, _head)
            return True
        except Exception:
            return False

    async def prefetch_cited_pdfs(self, document_ids: List[int]) -> None:
        """Pre-fetch PDFs for cited documents into the local cache.

        Fetches from tenant object storage (the document's origin) and
        writes to the local MinIO cache. Skips documents already cached.
        """
        if not document_ids:
            return

        unique_ids = list(set(document_ids))
        tasks = [self._prefetch_one(doc_id) for doc_id in unique_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _prefetch_one(self, document_id: int) -> None:
        if await self.is_cached(document_id):
            return

        try:
            from src.models.ragflow_domain import RAGFlowDocument
            from src.services.object_storage_service import ObjectStorageService

            doc = self.db.query(RAGFlowDocument).filter(
                RAGFlowDocument.id == document_id,
            ).first()
            if not doc:
                return

            metadata = doc.document_metadata if isinstance(doc.document_metadata, dict) else {}
            storage = metadata.get("storage") or {}
            bucket = storage.get("bucket")
            object_key = storage.get("object_key")
            if not bucket or not object_key:
                return

            obj_service = ObjectStorageService(self.db)
            result = await obj_service.get_object_bytes(
                customer_id=doc.customer_id,
                bucket=bucket,
                object_key=object_key,
            )
            pdf_bytes = result.get("content")
            if pdf_bytes:
                await self.cache_pdf(document_id, pdf_bytes)
        except Exception as exc:
            logger.warning("pdf_prefetch_failed doc_id=%s: %s", document_id, exc)
