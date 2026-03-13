"""
RAG Ingestion Microservice

Standalone FastAPI service for document parsing, metadata enrichment,
chunking, embedding, and vector indexing.

Designed to run on a separate host/container from the main Eliza platform.
The main platform calls this service via HTTP to ingest documents, and
handles chat/retrieval itself (retrieval is just a kNN query, no heavy compute).

Environment variables:
  OPENAI_API_KEY          - Required for embeddings + enrichment LLM calls
  RAG_OPENSEARCH_HOST     - AWS OpenSearch Serverless host (or empty for local ES)
  RAG_OPENSEARCH_REGION   - AWS region (default: us-east-1)
  RAG_OPENSEARCH_INDEX_PREFIX - Index prefix (default: rag_domains)
  RAG_USE_LOCAL_ELASTICSEARCH - "true" to use local ES instead of AWS
  ELASTICSEARCH_HOSTS     - Local ES hosts (default: http://localhost:9200)
  RAG_VLM_BASE_URL        - VLM API base URL for document parsing
  RAG_VLM_MODEL           - VLM model name
  RAG_VLM_API_KEY         - VLM API key (if needed)
  RAG_METADATA_ENRICHMENT_TIER  - basic | standard | full (default: standard)
  RAG_METADATA_ENRICHMENT_MODEL - LLM model for enrichment (default: gpt-4o-mini)
  EMBEDDING_MODEL         - OpenAI embedding model (default: text-embedding-3-small)
  DEFAULT_CHUNK_SIZE      - Tokens per chunk (default: 512)
  DEFAULT_PARSER          - Parser type: naive | vlm | gpt-4o | docling (default: vlm)
  PORT                    - Server port (default: 8100)
"""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel, Field

# ---- RAG module imports (portable package) ----
from eliza_rag.document_parser import DocumentParser, ParserType
from eliza_rag.chunking import ChunkingService, ChunkingStrategy
from eliza_rag.embeddings import EmbeddingService, EmbeddingProvider
from eliza_rag.vector_store import VectorStore, VectorDocument
from eliza_rag.metadata_enrichment import MetadataEnrichmentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag-ingestion")

# ---- Configuration from environment ----

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).strip().lower() in ("true", "1", "yes")

def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


# ---- Shared service instances (initialized once at startup) ----

_parser: Optional[DocumentParser] = None
_chunking: Optional[ChunkingService] = None
_embedding: Optional[EmbeddingService] = None
_vector_store: Optional[VectorStore] = None
_enrichment: Optional[MetadataEnrichmentService] = None

# In-memory job store (swap for Redis in production)
_jobs: Dict[str, Dict[str, Any]] = {}


def _init_services():
    global _parser, _chunking, _embedding, _vector_store, _enrichment

    parser_type_str = _env("DEFAULT_PARSER", "vlm")
    parser_type_map = {
        "naive": ParserType.NAIVE,
        "vlm": ParserType.VLM,
        "gpt-4o": ParserType.GPT4O,
        "docling": ParserType.DOCLING,
        "custom-vlm": ParserType.CUSTOM_VLM,
    }
    parser_type = parser_type_map.get(parser_type_str, ParserType.VLM)
    chunk_size = _env_int("DEFAULT_CHUNK_SIZE", 512)

    _parser = DocumentParser(
        parser_type=parser_type,
        chunk_size=chunk_size,
        chunk_overlap=50,
        vlm_base_url=_env("RAG_VLM_BASE_URL", "http://localhost:8000/v1"),
        vlm_model=_env("RAG_VLM_MODEL", "default"),
        vlm_api_key=_env("RAG_VLM_API_KEY") or None,
        openai_api_key=_env("OPENAI_API_KEY") or None,
    )

    _chunking = ChunkingService(
        chunk_size=chunk_size,
        chunk_overlap=50,
        strategy=ChunkingStrategy.SEMANTIC,
    )

    embedding_model = _env("EMBEDDING_MODEL", "text-embedding-3-small")
    _embedding = EmbeddingService(
        provider=EmbeddingProvider.OPENAI,
        model=embedding_model,
        batch_size=100,
    )

    es_hosts_raw = _env("ELASTICSEARCH_HOSTS", "http://localhost:9200")
    es_hosts = [h.strip() for h in es_hosts_raw.split(",")]
    use_local = _env_bool("RAG_USE_LOCAL_ELASTICSEARCH") or not _env("RAG_OPENSEARCH_HOST")

    _vector_store = VectorStore(
        hosts=es_hosts,
        index_prefix=_env("RAG_OPENSEARCH_INDEX_PREFIX", "rag_domains"),
        dimensions=_embedding.dimensions,
        similarity="cosine",
        opensearch_host=_env("RAG_OPENSEARCH_HOST") or None,
        opensearch_region=_env("RAG_OPENSEARCH_REGION", "us-east-1"),
        use_local=use_local,
    )

    _enrichment = MetadataEnrichmentService(
        enrichment_tier=_env("RAG_METADATA_ENRICHMENT_TIER", "standard"),
        enrichment_model=_env("RAG_METADATA_ENRICHMENT_MODEL", "gpt-4o-mini"),
    )

    logger.info(
        "Services initialized: parser=%s embedding=%s vector_store=%s enrichment=%s",
        parser_type.value,
        embedding_model,
        "local-ES" if use_local else f"AWS-OpenSearch({_env('RAG_OPENSEARCH_HOST')})",
        _enrichment.enrichment_tier,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_services()
    yield


app = FastAPI(
    title="RAG Ingestion Service",
    description="Standalone document parsing, enrichment, chunking, embedding, and indexing service.",
    version="1.0.0",
    lifespan=lifespan,
)


# ==================== Request / Response Models ====================

class IngestRequest(BaseModel):
    """Ingest a document from raw bytes or a pre-signed S3 URL."""
    workspace_id: int = Field(..., description="Target workspace / domain ID")
    knowledge_base_id: Optional[int] = Field(None, description="Target knowledge base ID")
    document_id: int = Field(..., description="Postgres document ID (caller manages DB records)")
    filename: str = Field(..., description="Original filename")
    mime_type: str = Field("application/pdf")
    customer_id: str = Field("default")
    # Optional context for enrichment
    knowledge_base_name: Optional[str] = None
    knowledge_base_description: Optional[str] = None
    workspace_name: Optional[str] = None
    # Overrides
    parser_type: Optional[str] = None
    chunk_size: Optional[int] = None
    enrichment_tier: Optional[str] = None


class IngestResponse(BaseModel):
    job_id: str
    status: str  # "queued" | "processing" | "completed" | "failed"
    document_id: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    document_id: Optional[int] = None
    chunks_indexed: Optional[int] = None
    enrichment: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    parser: str
    embedding_model: str
    vector_store: str
    enrichment_tier: str


# ==================== Endpoints ====================

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        parser=_parser.parser_type.value if _parser else "not_initialized",
        embedding_model=_embedding.model if _embedding else "not_initialized",
        vector_store="local-ES" if (_vector_store and _vector_store.use_local) else f"AWS-OpenSearch",
        enrichment_tier=_enrichment.enrichment_tier if _enrichment else "not_initialized",
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    workspace_id: int = Form(...),
    document_id: int = Form(...),
    filename: str = Form(...),
    mime_type: str = Form("application/pdf"),
    customer_id: str = Form("default"),
    knowledge_base_id: Optional[int] = Form(None),
    knowledge_base_name: Optional[str] = Form(None),
    knowledge_base_description: Optional[str] = Form(None),
    workspace_name: Optional[str] = Form(None),
    parser_type: Optional[str] = Form(None),
    chunk_size: Optional[int] = Form(None),
    enrichment_tier: Optional[str] = Form(None),
):
    """
    Upload a document for ingestion.

    The caller (Eliza platform) manages the database record. This service
    only handles: parse → enrich → chunk → embed → index to OpenSearch.

    Returns immediately with a job_id. Poll /ingest/status/{job_id} for progress.
    """
    file_content = await file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="Empty file")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "document_id": document_id,
        "started_at": datetime.utcnow().isoformat(),
    }

    background_tasks.add_task(
        _run_ingestion,
        job_id=job_id,
        file_content=file_content,
        workspace_id=workspace_id,
        document_id=document_id,
        filename=filename,
        mime_type=mime_type,
        customer_id=customer_id,
        knowledge_base_id=knowledge_base_id,
        knowledge_base_name=knowledge_base_name,
        knowledge_base_description=knowledge_base_description,
        workspace_name=workspace_name,
        parser_type_override=parser_type,
        chunk_size_override=chunk_size,
        enrichment_tier_override=enrichment_tier,
    )

    return IngestResponse(job_id=job_id, status="queued", document_id=document_id)


@app.post("/ingest/sync", response_model=JobStatusResponse)
async def ingest_document_sync(
    file: UploadFile = File(...),
    workspace_id: int = Form(...),
    document_id: int = Form(...),
    filename: str = Form(...),
    mime_type: str = Form("application/pdf"),
    customer_id: str = Form("default"),
    knowledge_base_id: Optional[int] = Form(None),
    knowledge_base_name: Optional[str] = Form(None),
    knowledge_base_description: Optional[str] = Form(None),
    workspace_name: Optional[str] = Form(None),
    parser_type: Optional[str] = Form(None),
    chunk_size: Optional[int] = Form(None),
    enrichment_tier: Optional[str] = Form(None),
):
    """
    Synchronous ingestion — blocks until complete. Use for small documents
    or when you need the result immediately.
    """
    file_content = await file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="Empty file")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "document_id": document_id, "started_at": datetime.utcnow().isoformat()}

    await _run_ingestion(
        job_id=job_id,
        file_content=file_content,
        workspace_id=workspace_id,
        document_id=document_id,
        filename=filename,
        mime_type=mime_type,
        customer_id=customer_id,
        knowledge_base_id=knowledge_base_id,
        knowledge_base_name=knowledge_base_name,
        knowledge_base_description=knowledge_base_description,
        workspace_name=workspace_name,
        parser_type_override=parser_type,
        chunk_size_override=chunk_size,
        enrichment_tier_override=enrichment_tier,
    )

    return JobStatusResponse(job_id=job_id, **_jobs[job_id])


@app.get("/ingest/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll ingestion job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(job_id=job_id, **job)


# ==================== Core Ingestion Logic ====================

async def _run_ingestion(
    *,
    job_id: str,
    file_content: bytes,
    workspace_id: int,
    document_id: int,
    filename: str,
    mime_type: str,
    customer_id: str,
    knowledge_base_id: Optional[int],
    knowledge_base_name: Optional[str],
    knowledge_base_description: Optional[str],
    workspace_name: Optional[str],
    parser_type_override: Optional[str],
    chunk_size_override: Optional[int],
    enrichment_tier_override: Optional[str],
):
    """Full ingestion pipeline: parse → enrich → chunk → embed → index."""
    _jobs[job_id]["status"] = "processing"

    try:
        # Resolve parser
        parser = _parser
        if parser_type_override:
            pmap = {"naive": ParserType.NAIVE, "vlm": ParserType.VLM, "gpt-4o": ParserType.GPT4O, "docling": ParserType.DOCLING}
            pt = pmap.get(parser_type_override, _parser.parser_type)
            parser = DocumentParser(parser_type=pt, chunk_size=chunk_size_override or _parser.chunk_size,
                                    chunk_overlap=_parser.chunk_overlap, vlm_base_url=_parser.vlm_base_url,
                                    vlm_model=_parser.vlm_model, openai_api_key=_parser.openai_api_key)

        # Resolve enrichment
        enrichment = _enrichment
        if enrichment_tier_override and enrichment_tier_override != _enrichment.enrichment_tier:
            enrichment = MetadataEnrichmentService(enrichment_tier=enrichment_tier_override,
                                                    enrichment_model=_enrichment.enrichment_model)

        # Step 1: Parse
        logger.info("Parsing %s (%s bytes)", filename, len(file_content))
        parsed = await parser.parse_file(file_content, filename, mime_type)
        if not parsed.success:
            raise Exception(parsed.error or "Parse failed")

        # Step 2: Document-level metadata enrichment
        doc_meta = await enrichment.enrich_document_metadata(
            file_content=file_content, filename=filename, mime_type=mime_type,
            parsed_text=parsed.content, page_count=parsed.page_count,
        )
        logger.info("Enriched doc metadata: title=%s type=%s topics=%s", doc_meta.title, doc_meta.document_type, doc_meta.key_topics)

        # Step 3: Chunk
        cs = chunk_size_override or _chunking.chunk_size
        chunker = ChunkingService(chunk_size=cs, chunk_overlap=50, strategy=ChunkingStrategy.SEMANTIC)
        chunks = chunker.chunk_text(parsed.content, metadata={"filename": filename, "doc_id": document_id, "knowledge_base_id": knowledge_base_id})
        if not chunks:
            raise Exception("No chunks generated")
        logger.info("Generated %d chunks", len(chunks))

        # Step 4: Structural enrichment
        chunk_metadata_list = enrichment.enrich_chunks_structural(
            chunks, parsed_text=parsed.content, filename=filename, doc_id=document_id, doc_metadata=doc_meta,
            knowledge_base_id=knowledge_base_id, knowledge_base_name=knowledge_base_name,
            knowledge_base_description=knowledge_base_description,
            workspace_id=workspace_id, workspace_name=workspace_name,
        )

        # Step 5: LLM chunk enrichment (FULL tier only)
        chunk_metadata_list = await enrichment.enrich_chunks_with_llm(chunks, chunk_metadata_list, doc_meta.title or filename)

        # Step 6: Embed
        texts = [c.text for c in chunks]
        embeddings = await _embedding.embed_texts(texts)
        logger.info("Generated %d embeddings", len(embeddings))

        # Step 7: Build vector documents
        vector_docs = []
        for i, (chunk, embedding, cm) in enumerate(zip(chunks, embeddings, chunk_metadata_list)):
            vector_docs.append(VectorDocument(
                id=f"{document_id}_{i}",
                domain_id=str(workspace_id),
                knowledge_base_id=str(knowledge_base_id) if knowledge_base_id else None,
                document_id=str(document_id),
                chunk_index=i,
                text=chunk.text,
                embedding=embedding,
                metadata=cm.to_flat_dict(),
                hypothetical_questions=cm.hypothetical_questions or None,
            ))

        # Step 8: Index
        indexed = await _vector_store.index_documents(str(workspace_id), vector_docs)
        logger.info("Indexed %d chunks for doc %d in workspace %d", indexed, document_id, workspace_id)

        _jobs[job_id].update({
            "status": "completed",
            "chunks_indexed": indexed,
            "enrichment": {
                "title": doc_meta.title,
                "summary": doc_meta.summary,
                "language": doc_meta.language,
                "document_type": doc_meta.document_type,
                "key_topics": doc_meta.key_topics,
                "total_pages": doc_meta.total_pages,
                "author": doc_meta.author,
            },
            "completed_at": datetime.utcnow().isoformat(),
        })

    except Exception as exc:
        logger.error("Ingestion failed for doc %d: %s", document_id, exc, exc_info=True)
        _jobs[job_id].update({
            "status": "failed",
            "error": str(exc),
            "completed_at": datetime.utcnow().isoformat(),
        })


# ==================== Entry point ====================

if __name__ == "__main__":
    import uvicorn
    port = _env_int("PORT", 8100)
    uvicorn.run(app, host="0.0.0.0", port=port)
