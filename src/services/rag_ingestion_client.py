"""
RAG Ingestion Service Client.

HTTP client used by NativeRAGService to delegate the heavy
parse/chunk/enrich/embed/index pipeline to a remote service
when RAG_INGESTION_SERVICE_URL is configured.

When the URL is not set, the platform processes documents in-process (default).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result returned by the remote ingestion service."""
    job_id: str = ""
    status: str = "unknown"
    document_id: Optional[int] = None
    chunks_indexed: int = 0
    total_tokens: int = 0
    enrichment: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class RAGIngestionClient:
    """
    Async HTTP client for the RAG Ingestion microservice.

    Used by NativeRAGService._process_document() when
    settings.rag_ingestion_service_url is set.
    """

    def __init__(self, base_url: str, timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def ingest(
        self,
        *,
        file_content: bytes,
        workspace_id: int,
        document_id: int,
        filename: str,
        mime_type: str = "application/pdf",
        customer_id: str = "default",
        knowledge_base_id: Optional[int] = None,
        knowledge_base_name: Optional[str] = None,
        knowledge_base_description: Optional[str] = None,
        workspace_name: Optional[str] = None,
        parser_type: Optional[str] = None,
        chunk_size: Optional[int] = None,
        enrichment_tier: Optional[str] = None,
    ) -> IngestionResult:
        """
        Send document to remote ingestion service (synchronous mode — blocks until done).

        The remote service handles: parse → enrich → chunk → embed → index to OpenSearch.
        Returns enrichment metadata and chunk count for the caller to update Postgres.
        """
        data: Dict[str, str] = {
            "workspace_id": str(workspace_id),
            "document_id": str(document_id),
            "filename": filename,
            "mime_type": mime_type,
            "customer_id": customer_id,
        }
        if knowledge_base_id is not None:
            data["knowledge_base_id"] = str(knowledge_base_id)
        if knowledge_base_name:
            data["knowledge_base_name"] = knowledge_base_name
        if knowledge_base_description:
            data["knowledge_base_description"] = knowledge_base_description
        if workspace_name:
            data["workspace_name"] = workspace_name
        if parser_type:
            data["parser_type"] = parser_type
        if chunk_size is not None:
            data["chunk_size"] = str(chunk_size)
        if enrichment_tier:
            data["enrichment_tier"] = enrichment_tier

        files = {"file": (filename, file_content, mime_type)}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/ingest/sync",
                    data=data,
                    files=files,
                )
                resp.raise_for_status()
                d = resp.json()

                enrichment = d.get("enrichment") or {}
                chunks_indexed = d.get("chunks_indexed") or 0

                # Estimate total tokens from enrichment if available
                total_tokens = 0
                if chunks_indexed > 0:
                    total_tokens = chunks_indexed * 500  # rough estimate

                return IngestionResult(
                    job_id=d.get("job_id", ""),
                    status=d.get("status", "unknown"),
                    document_id=d.get("document_id"),
                    chunks_indexed=chunks_indexed,
                    total_tokens=total_tokens,
                    enrichment=enrichment,
                    error=d.get("error"),
                )

        except httpx.HTTPStatusError as exc:
            error_body = exc.response.text[:500] if exc.response else str(exc)
            logger.error(
                "rag_ingestion_service_http_error url=%s status=%s body=%s",
                self.base_url, exc.response.status_code if exc.response else "?", error_body,
            )
            return IngestionResult(status="failed", error=f"HTTP {exc.response.status_code}: {error_body}")

        except Exception as exc:
            logger.error("rag_ingestion_service_error url=%s error=%s", self.base_url, exc, exc_info=True)
            return IngestionResult(status="failed", error=str(exc))

    async def health(self) -> Dict[str, Any]:
        """Check remote service health."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            return {"status": "unreachable", "error": str(exc)}
