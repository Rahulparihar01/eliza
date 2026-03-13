"""
RAG Ingestion Client - Call the standalone ingestion service from the main platform.

Drop-in replacement: instead of calling NativeRAGService._process_document() locally,
the platform calls this client which forwards to the remote ingestion service.

Usage in the platform:
    from services.rag_ingestion.client import RAGIngestionClient

    client = RAGIngestionClient(base_url="http://rag-ingestion:8100")

    # Async ingestion (returns immediately, poll for status)
    job = await client.ingest_async(
        file_content=pdf_bytes,
        workspace_id=400,
        document_id=250,
        filename="report.pdf",
        knowledge_base_id=32,
        knowledge_base_name="Misc Docs",
    )
    # job.job_id = "abc-123"
    # job.status = "queued"

    # Poll for completion
    status = await client.get_status(job.job_id)
    # status.status = "completed"
    # status.chunks_indexed = 9
    # status.enrichment = {"title": "...", "summary": "...", ...}

    # Or synchronous (blocks until done, good for small docs)
    result = await client.ingest_sync(
        file_content=pdf_bytes,
        workspace_id=400,
        document_id=250,
        filename="report.pdf",
    )
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    job_id: str
    status: str
    document_id: int


@dataclass
class JobStatus:
    job_id: str
    status: str
    document_id: Optional[int] = None
    chunks_indexed: Optional[int] = None
    enrichment: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class RAGIngestionClient:
    """HTTP client for the RAG Ingestion microservice."""

    def __init__(self, base_url: str = "http://rag-ingestion:8100", timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def ingest_async(
        self,
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
    ) -> IngestResult:
        """Submit document for async ingestion. Returns immediately with job_id."""
        data = {
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

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/ingest", data=data, files=files)
            resp.raise_for_status()
            d = resp.json()
            return IngestResult(job_id=d["job_id"], status=d["status"], document_id=d["document_id"])

    async def ingest_sync(
        self,
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
    ) -> JobStatus:
        """Submit document and wait for completion. Use for small documents."""
        data = {
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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/ingest/sync", data=data, files=files)
            resp.raise_for_status()
            d = resp.json()
            return JobStatus(**d)

    async def get_status(self, job_id: str) -> JobStatus:
        """Poll job status."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/ingest/status/{job_id}")
            resp.raise_for_status()
            d = resp.json()
            return JobStatus(**d)

    async def health(self) -> Dict[str, Any]:
        """Check service health."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{self.base_url}/health")
            resp.raise_for_status()
            return resp.json()
