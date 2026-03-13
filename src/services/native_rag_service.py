"""
Native RAG Service - Replaces external RAGFlow dependency.

Provides the same interface as RAGFlowService but uses native Python
libraries for document parsing, embedding, and retrieval:
- docling: Document parsing
- OpenAI/sentence-transformers: Embeddings
- Elasticsearch: Vector storage
- LiteLLM: LLM chat
"""

import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, BinaryIO, AsyncIterator

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.core.config import get_settings
from src.models.ragflow_domain import (
    RAGFlowDomain, RAGFlowDocument, RAGFlowConversation, RAGFlowMessage,
    RAGFlowDomainStatus, RAGFlowDocumentStatus, RAGFlowParserType
)
from src.models.workspace import KnowledgeBase, KnowledgeBaseStatus
from src.models.prompt_template import PromptTemplate, PromptType, PromptStatus

from eliza_rag.document_parser import DocumentParser, ParserType
from eliza_rag.chunking import ChunkingService, ChunkingStrategy
from eliza_rag.embeddings import EmbeddingService, EmbeddingProvider
from eliza_rag.vector_store import VectorStore, VectorDocument
from eliza_rag.retrieval import RetrievalService, RetrievedChunk
from eliza_rag.chat import RAGChatService, ChatMessage
from eliza_rag.metadata_enrichment import MetadataEnrichmentService
from .rag_ingestion_client import RAGIngestionClient, IngestionResult
from .workspace_rag_backend import get_workspace_agent
from .object_storage_service import ObjectStorageService
from src.services.fasb_service import get_fasb_service
from src.services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)


class NativeRAGError(Exception):
    """Native RAG service error."""
    def __init__(self, message: str, code: Optional[int] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details


# Alias for backward compatibility with existing code
RAGFlowError = NativeRAGError


class NativeRAGService:
    """
    Native RAG service using Python libraries instead of external RAGFlow.
    
    Provides the same interface as RAGFlowService for backward compatibility.
    """
    
    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.settings = get_settings()
        self.object_storage_service = ObjectStorageService(db)
        
        # Initialize components
        self._init_components()
    
    def _init_components(self):
        """Initialize RAG pipeline components."""
        settings = self.settings
        
        # Determine parser type from config
        parser_type_str = settings.ragflow_default_parser or "vlm"
        parser_type_map = {
            "naive": ParserType.NAIVE,
            "docling": ParserType.DOCLING,
            "vlm": ParserType.VLM,
            "custom-vlm": ParserType.CUSTOM_VLM,
            "gpt-4o": ParserType.GPT4O,
        }
        parser_type = parser_type_map.get(parser_type_str.lower(), ParserType.VLM)
        
        # Document parser - uses VLM on port 8000 by default
        self.document_parser = DocumentParser(
            parser_type=parser_type,
            chunk_size=settings.ragflow_default_chunk_size or 512,
            chunk_overlap=50,
            vlm_base_url=settings.rag_vlm_base_url or "http://localhost:8000/v1",
            vlm_model=settings.rag_vlm_model or "default",
            page_parse_concurrency=settings.rag_parser_page_concurrency,
            page_batch_size=settings.rag_parser_page_batch_size,
            request_timeout_seconds=settings.rag_parser_request_timeout_seconds,
            retry_attempts=settings.rag_parser_retry_attempts,
            retry_backoff_seconds=settings.rag_parser_retry_backoff_seconds,
            openai_max_tokens=settings.rag_parser_openai_max_tokens,
        )
        
        # Chunking service
        self.chunking_service = ChunkingService(
            chunk_size=settings.ragflow_default_chunk_size or 512,
            chunk_overlap=50,
            strategy=ChunkingStrategy.SEMANTIC
        )
        
        # Embedding service (OpenAI, local, or Bedrock Titan)
        embedding_model = settings.ragflow_default_embedding_model or "text-embedding-3-small"
        provider_str = (settings.rag_embedding_provider or "openai").lower()
        if provider_str == "bedrock":
            self.embedding_service = EmbeddingService(
                provider=EmbeddingProvider.BEDROCK,
                model=embedding_model or "amazon.titan-embed-text-v1",
                batch_size=100,
                aws_region=settings.rag_bedrock_embedding_region or "us-east-1",
            )
        elif provider_str == "local":
            self.embedding_service = EmbeddingService(
                provider=EmbeddingProvider.LOCAL,
                model=embedding_model or "all-MiniLM-L6-v2",
                batch_size=100,
            )
        else:
            self.embedding_service = EmbeddingService(
                provider=EmbeddingProvider.OPENAI,
                model=embedding_model,
                batch_size=100,
            )
        
        # Vector store - AWS OpenSearch or local Elasticsearch
        es_hosts = settings.elasticsearch_hosts
        if isinstance(es_hosts, str):
            es_hosts = [h.strip() for h in es_hosts.split(",")]
        
        use_local = settings.rag_use_local_elasticsearch or not settings.rag_opensearch_host
        
        self.vector_store = VectorStore(
            hosts=es_hosts,
            index_prefix=settings.rag_opensearch_index_prefix or "rag_domains",
            dimensions=self.embedding_service.dimensions,
            similarity="cosine",
            opensearch_host=settings.rag_opensearch_host,
            opensearch_region=settings.rag_opensearch_region,
            use_local=use_local
        )
        
        # Metadata enrichment service
        self.metadata_enrichment = MetadataEnrichmentService(
            enrichment_tier=settings.rag_metadata_enrichment_tier or "standard",
            enrichment_model=settings.rag_metadata_enrichment_model or "gpt-4o-mini",
        )

        # Remote ingestion service (optional — when set, _process_document delegates to it)
        self._ingestion_client: Optional[RAGIngestionClient] = None
        ingestion_url = (settings.rag_ingestion_service_url or "").strip()
        if ingestion_url:
            self._ingestion_client = RAGIngestionClient(base_url=ingestion_url)

        logger.info(f"RAG Vector Store: {'local Elasticsearch' if use_local else f'AWS OpenSearch ({settings.rag_opensearch_host})'}")
        logger.info(f"RAG Document Parser: {parser_type.value} (VLM: {settings.rag_vlm_base_url})")
        logger.info(f"RAG Metadata Enrichment: {self.metadata_enrichment.enrichment_tier}")
        logger.info(f"RAG Ingestion Service: {ingestion_url or 'local (in-process)'}")
        
        # Retrieval service
        self.retrieval_service = RetrievalService(
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
            document_lookup=self._get_document_info
        )
        
        # Chat service
        self.chat_service = RAGChatService(
            retrieval_service=self.retrieval_service,
            model=settings.default_llm_model or "gpt-4o-mini",
            temperature=0.1
        )

    @staticmethod
    def _is_fasb_workspace(domain: Optional[RAGFlowDomain]) -> bool:
        """Detect FASB-backed workspace routing."""
        if domain is None:
            return False

        workspace_config = domain.workspace_config if isinstance(domain.workspace_config, dict) else {}
        backend_type = str(workspace_config.get("backend_type") or "").strip().lower()
        domain_name = str(domain.name or "").strip().lower()
        opensearch_index = str(workspace_config.get("opensearch_index") or "").strip().lower()

        return (
            domain_name == "fasb"
            or backend_type == "opensearch_fasb"
            or opensearch_index.startswith("fasb")
        )
    
    async def _get_document_info(self, document_id: str) -> Optional[Dict]:
        """Get document info for retrieval context."""
        try:
            doc = self.db.query(RAGFlowDocument).filter(
                RAGFlowDocument.id == int(document_id)
            ).first()
            if doc:
                return {"filename": doc.original_filename}
        except:
            pass
        return None

    @staticmethod
    def _normalize_min_score(min_score: float) -> float:
        """Normalize similarity threshold to 0-1 range."""
        try:
            value = float(min_score)
        except (TypeError, ValueError):
            return 0.0
        if value > 1:
            value = value / 100.0
        return max(0.0, min(value, 1.0))

    async def _get_knowledge_base(
        self,
        knowledge_base_id: int,
        domain_id: int,
        customer_id: str,
        require_active: bool = True,
    ) -> Optional[KnowledgeBase]:
        """Load a knowledge base scoped to workspace + tenant."""
        query = self.db.query(KnowledgeBase).filter(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.workspace_id == domain_id,
            KnowledgeBase.customer_id == customer_id,
        )
        if require_active:
            query = query.filter(KnowledgeBase.is_active == True)
        return query.first()

    async def _resolve_upload_knowledge_base(
        self,
        *,
        domain: RAGFlowDomain,
        customer_id: str,
        knowledge_base_id: Optional[int] = None,
    ) -> KnowledgeBase:
        """Resolve target KB for document upload (explicit or default)."""
        if knowledge_base_id is not None:
            kb = await self._get_knowledge_base(
                knowledge_base_id=knowledge_base_id,
                domain_id=domain.id,
                customer_id=customer_id,
            )
            if not kb:
                raise NativeRAGError(
                    f"Knowledge base {knowledge_base_id} not found in workspace {domain.id}"
                )
            return kb

        kb = (
            self.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.workspace_id == domain.id,
                KnowledgeBase.customer_id == customer_id,
                KnowledgeBase.is_active == True,
            )
            .order_by(KnowledgeBase.created_at.asc())
            .first()
        )
        if not kb:
            raise NativeRAGError(
                f"Workspace {domain.id} has no active knowledge bases. "
                "Create a knowledge base before uploading documents."
            )
        return kb

    async def _update_knowledge_base_status(self, kb: KnowledgeBase) -> None:
        """Update KB status based on document states."""
        docs = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == kb.workspace_id,
            RAGFlowDocument.customer_id == kb.customer_id,
            RAGFlowDocument.knowledge_base_id == kb.id,
        ).all()

        if not docs:
            kb.status = KnowledgeBaseStatus.PENDING.value
            kb.last_error = None
            return

        completed = sum(1 for d in docs if d.status == RAGFlowDocumentStatus.COMPLETED)
        pending_or_parsing = sum(
            1 for d in docs if d.status in [RAGFlowDocumentStatus.PENDING, RAGFlowDocumentStatus.PARSING]
        )
        failed = sum(1 for d in docs if d.status == RAGFlowDocumentStatus.FAILED)

        if pending_or_parsing > 0:
            kb.status = KnowledgeBaseStatus.INDEXING.value
            kb.last_error = None
        elif completed > 0 and kb.chunk_count > 0:
            kb.status = KnowledgeBaseStatus.READY.value
            kb.last_error = None
        elif failed == len(docs):
            kb.status = KnowledgeBaseStatus.FAILED.value
            failed_doc = next((d for d in docs if d.status == RAGFlowDocumentStatus.FAILED), None)
            kb.last_error = failed_doc.processing_error if failed_doc else "All documents failed"
        elif completed > 0:
            kb.status = KnowledgeBaseStatus.INDEXING.value
        else:
            kb.status = KnowledgeBaseStatus.PENDING.value

    async def _refresh_workspace_and_kb_stats(
        self,
        *,
        domain_id: int,
        customer_id: str,
        knowledge_base_id: Optional[int] = None,
    ) -> None:
        """Recompute workspace + KB aggregate stats from completed documents."""
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            return

        domain_stats = (
            self.db.query(
                func.count(RAGFlowDocument.id),
                func.coalesce(func.sum(RAGFlowDocument.chunk_count), 0),
                func.coalesce(func.sum(RAGFlowDocument.token_count), 0),
            )
            .filter(
                RAGFlowDocument.domain_id == domain_id,
                RAGFlowDocument.customer_id == customer_id,
                RAGFlowDocument.status == RAGFlowDocumentStatus.COMPLETED,
            )
            .first()
        )
        domain.document_count = int(domain_stats[0] or 0)
        domain.chunk_count = int(domain_stats[1] or 0)
        domain.total_tokens = int(domain_stats[2] or 0)
        await self._update_domain_status(domain)

        if knowledge_base_id is None:
            return

        kb = await self._get_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            domain_id=domain_id,
            customer_id=customer_id,
            require_active=False,
        )
        if not kb:
            return

        kb_stats = (
            self.db.query(
                func.count(RAGFlowDocument.id),
                func.coalesce(func.sum(RAGFlowDocument.chunk_count), 0),
                func.coalesce(func.sum(RAGFlowDocument.token_count), 0),
            )
            .filter(
                RAGFlowDocument.domain_id == domain_id,
                RAGFlowDocument.customer_id == customer_id,
                RAGFlowDocument.knowledge_base_id == knowledge_base_id,
                RAGFlowDocument.status == RAGFlowDocumentStatus.COMPLETED,
            )
            .first()
        )
        kb.document_count = int(kb_stats[0] or 0)
        kb.chunk_count = int(kb_stats[1] or 0)
        kb.total_tokens = int(kb_stats[2] or 0)
        kb.last_sync_at = datetime.utcnow()
        await self._update_knowledge_base_status(kb)

    async def _persist_document_blob(
        self,
        *,
        document: RAGFlowDocument,
        file_content: bytes,
        mime_type: str,
    ) -> None:
        """Persist raw document bytes into configured tenant object storage."""
        storage_meta = await self.object_storage_service.upload_document_bytes(
            customer_id=document.customer_id,
            workspace_id=document.domain_id,
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            filename=document.original_filename,
            content=file_content,
            content_type=mime_type,
        )

        metadata = dict(document.document_metadata or {})
        metadata["storage"] = storage_meta
        document.document_metadata = metadata

    async def _delete_document_blob(self, document: RAGFlowDocument) -> None:
        """Delete raw document blob from object storage when document is removed."""
        metadata = document.document_metadata if isinstance(document.document_metadata, dict) else {}
        storage = metadata.get("storage") if isinstance(metadata.get("storage"), dict) else {}
        managed_flag = storage.get("managed")
        if isinstance(managed_flag, str):
            managed = managed_flag.strip().lower() not in {"false", "0", "no"}
        elif managed_flag is None:
            managed = True
        else:
            managed = bool(managed_flag)
        if not managed:
            return
        bucket = storage.get("bucket")
        object_key = storage.get("object_key")
        if not bucket or not object_key:
            return
        try:
            await self.object_storage_service.delete_object(
                customer_id=document.customer_id,
                bucket=bucket,
                object_key=object_key,
            )
        except Exception as exc:
            logger.warning(
                "document_blob_delete_failed doc_id=%s workspace_id=%s kb_id=%s error=%s",
                document.id,
                document.domain_id,
                document.knowledge_base_id,
                str(exc),
            )
    
    def _get_domain_prompts(self, domain_name: str, customer_id: str) -> Dict[str, Optional[str]]:
        """
        Load active prompts for a domain from the database.
        
        Returns dict with keys: 'system', 'query_rewrite', 'synthesis', 'retrieval'
        Values are the prompt content or None if not configured.
        """
        prompts = {}
        
        # Map PromptType enum to keys
        type_keys = {
            PromptType.SYSTEM: 'system',
            PromptType.QUERY_REWRITE: 'query_rewrite',
            PromptType.SYNTHESIS: 'synthesis',
            PromptType.RETRIEVAL: 'retrieval',
        }
        
        # Query all active prompts for this domain
        active_prompts = self.db.query(PromptTemplate).filter(
            PromptTemplate.domain == domain_name,
            PromptTemplate.customer_id == customer_id,
            PromptTemplate.is_active == True,
            PromptTemplate.status == PromptStatus.ACTIVE
        ).all()
        
        for prompt in active_prompts:
            key = type_keys.get(prompt.prompt_type)
            if key:
                prompts[key] = prompt.content
                logger.debug(f"Loaded {key} prompt for domain {domain_name} (v{prompt.version})")
        
        return prompts
    
    def _get_chat_service_for_domain(self, domain: RAGFlowDomain, customer_id: str):
        """
        Create a workspace chat backend with Pydantic AI when possible.
        
        Falls back to legacy RAGChatService if workspace agent setup fails.
        """
        try:
            return get_workspace_agent(
                workspace_id=domain.id,
                customer_id=customer_id,
                db=self.db,
                retrieval_service=self.retrieval_service,
            )
        except Exception as exc:
            logger.warning(
                "workspace_agent_fallback_to_legacy_chat",
                workspace_id=domain.id,
                domain=domain.name,
                error=str(exc),
            )

            prompts = self._get_domain_prompts(domain.name, customer_id)
            system_prompt = prompts.get('system')
            return RAGChatService(
                retrieval_service=self.retrieval_service,
                model=self.settings.default_llm_model or "gpt-4o-mini",
                temperature=0.1,
                system_prompt=system_prompt,
            )
    
    # ==================== Citation Helpers ====================

    @staticmethod
    def _append_sources_section(
        answer: str,
        chunks: List["RetrievedChunk"],
    ) -> str:
        """Append a structured Sources section to the answer text.

        Produces the same ``\\n\\nSources:\\n[1] doc:X pages:Y chunk:Z section:...``
        format used by the FASB service so the frontend citation parser works
        uniformly for every workspace type.

        Also ensures that inline ``[N]`` references exist in the answer body.
        If the LLM already included them they are left intact; otherwise the
        method appends numbered references for each cited chunk.
        """
        if not chunks:
            return answer

        import re as _re

        existing_refs = set(int(m) for m in _re.findall(r"\[(\d+)\]", answer))

        source_lines: List[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            doc_id = chunk.document_id or ""
            page = chunk.page_number
            page_str = f"{page}-{page}" if page else ""
            if hasattr(chunk, "page_range") and chunk.page_range and len(chunk.page_range) == 2:
                page_str = f"{chunk.page_range[0]}-{chunk.page_range[1]}"
            chunk_id = ""
            if chunk.metadata and chunk.metadata.get("chunk_id"):
                chunk_id = chunk.metadata["chunk_id"]
            elif hasattr(chunk, "chunk_index"):
                chunk_id = str(chunk.chunk_index)
            section = chunk.section_title or chunk.document_name or ""
            doc_title = getattr(chunk, "document_title", None) or chunk.document_name or ""
            kb_name = getattr(chunk, "knowledge_base_name", None) or ""
            citation = f"doc:{doc_id} pages:{page_str} chunk:{chunk_id} section:{section}"
            if doc_title and doc_title != section:
                citation += f" title:{doc_title}"
            if kb_name:
                citation += f" kb:{kb_name}"
            source_lines.append(f"[{idx}] {citation}")

        if not existing_refs:
            refs = " ".join(f"[{i}]" for i in range(1, len(chunks) + 1))
            answer = answer.rstrip() + "\n\n" + refs

        sources_section = "\n\nSources:\n" + "\n".join(source_lines)
        return answer + sources_section

    # ==================== Health Check ====================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        try:
            # Check Elasticsearch
            stats = await self.vector_store.get_stats("health_check")
            return {
                "status": "healthy",
                "elasticsearch": "connected",
                "embedding_model": self.embedding_service.model
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    # ==================== Domain CRUD ====================
    
    async def create_domain(
        self,
        customer_id: str,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        icon: str = "folder",
        color: str = "violet",
        parser_type: RAGFlowParserType = RAGFlowParserType.NAIVE,
        embedding_model: Optional[str] = None,
        chunk_token_count: Optional[int] = None,
        task_page_size: Optional[int] = None,
        user_id: Optional[int] = None,
        custom_vlm_model: Optional[str] = None
    ) -> RAGFlowDomain:
        """
        Create a new RAG domain.
        
        Creates database record and Elasticsearch index for vectors.
        """
        # Generate unique domain ID for vector index
        domain_uuid = str(uuid.uuid4())[:8]
        
        # Create local domain record
        domain = RAGFlowDomain(
            customer_id=customer_id,
            name=name,
            display_name=display_name,
            description=description,
            icon=icon,
            color=color,
            ragflow_dataset_id=f"{customer_id}_{name}_{domain_uuid}",
            ragflow_dataset_name=f"{customer_id}_{name}",
            parser_type=parser_type,
            parser_config={"custom_vlm_model": custom_vlm_model} if custom_vlm_model else None,
            embedding_model=embedding_model or "text-embedding-3-small",
            chunk_token_count=chunk_token_count or self.settings.ragflow_default_chunk_size or 512,
            status=RAGFlowDomainStatus.PENDING,
            created_by_user_id=user_id
        )
        
        self.db.add(domain)
        self.db.commit()
        self.db.refresh(domain)
        
        # Create vector index
        try:
            await self.vector_store.create_index(str(domain.id))
            logger.info(f"Created domain {customer_id}/{name} with vector index")
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            # Domain record still created, index can be created later
        
        return domain
    
    async def get_domain(self, domain_id: int, customer_id: str) -> Optional[RAGFlowDomain]:
        """Get a domain by ID."""
        return self.db.query(RAGFlowDomain).filter(
            RAGFlowDomain.id == domain_id,
            RAGFlowDomain.customer_id == customer_id
        ).first()
    
    async def get_domain_by_name(self, name: str, customer_id: str) -> Optional[RAGFlowDomain]:
        """Get a domain by name."""
        return self.db.query(RAGFlowDomain).filter(
            RAGFlowDomain.name == name,
            RAGFlowDomain.customer_id == customer_id
        ).first()
    
    async def list_domains(
        self,
        customer_id: str,
        status: Optional[RAGFlowDomainStatus] = None,
        limit: int = 100,
        offset: int = 0,
        sync_stats: bool = True
    ) -> List[RAGFlowDomain]:
        """List domains for a customer."""
        query = self.db.query(RAGFlowDomain).filter(
            RAGFlowDomain.customer_id == customer_id
        )
        
        if status:
            query = query.filter(RAGFlowDomain.status == status)
        
        domains = query.order_by(RAGFlowDomain.created_at.desc()).offset(offset).limit(limit).all()
        
        # Sync stats from vector store
        if sync_stats:
            for domain in domains:
                try:
                    stats = await self.vector_store.get_stats(str(domain.id))
                    if stats.get("exists"):
                        domain.chunk_count = stats.get("document_count", 0)
                        domain.last_sync_at = datetime.utcnow()
                        await self._update_domain_status(domain)
                except Exception as e:
                    logger.warning(f"Could not sync stats for domain {domain.id}: {e}")
            
            try:
                self.db.commit()
            except:
                self.db.rollback()
        
        return domains
    
    async def _update_domain_status(self, domain: RAGFlowDomain) -> None:
        """Update domain status based on document states."""
        docs = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == domain.id
        ).all()
        
        if not docs:
            domain.status = RAGFlowDomainStatus.PENDING
            domain.last_error = None
            return
        
        completed = sum(1 for d in docs if d.status == RAGFlowDocumentStatus.COMPLETED)
        pending_or_parsing = sum(1 for d in docs if d.status in [RAGFlowDocumentStatus.PENDING, RAGFlowDocumentStatus.PARSING])
        failed = sum(1 for d in docs if d.status == RAGFlowDocumentStatus.FAILED)
        
        if pending_or_parsing > 0:
            domain.status = RAGFlowDomainStatus.INDEXING
            domain.last_error = None
        elif completed > 0 and domain.chunk_count > 0:
            domain.status = RAGFlowDomainStatus.READY
            domain.last_error = None
        elif failed == len(docs):
            domain.status = RAGFlowDomainStatus.FAILED
            failed_doc = next((d for d in docs if d.status == RAGFlowDocumentStatus.FAILED), None)
            domain.last_error = failed_doc.processing_error if failed_doc else "All documents failed"
        elif completed > 0:
            domain.status = RAGFlowDomainStatus.INDEXING
        else:
            domain.status = RAGFlowDomainStatus.PENDING
    
    async def delete_domain(self, domain_id: int, customer_id: str) -> bool:
        """Delete a domain."""
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            return False
        
        # Delete vector index
        try:
            await self.vector_store.delete_index(str(domain.id))
        except Exception as e:
            logger.warning(f"Failed to delete vector index: {e}")
        
        # Delete database record (cascades to documents)
        self.db.delete(domain)
        self.db.commit()
        
        logger.info(f"Deleted domain {customer_id}/{domain.name}")
        return True
    
    async def update_domain(
        self,
        domain_id: int,
        customer_id: str,
        **updates
    ) -> Optional[RAGFlowDomain]:
        """Update domain properties."""
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            return None
        
        for key, value in updates.items():
            if hasattr(domain, key) and value is not None:
                setattr(domain, key, value)
        
        self.db.commit()
        self.db.refresh(domain)
        return domain
    
    # ==================== Document Management ====================
    
    async def upload_document(
        self,
        domain_id: int,
        customer_id: str,
        file_content: bytes,
        filename: str,
        mime_type: str,
        user_id: Optional[int] = None,
        knowledge_base_id: Optional[int] = None,
    ) -> RAGFlowDocument:
        """
        Upload and process a document.
        
        Parses document, generates embeddings, and indexes chunks.
        """
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            raise NativeRAGError(f"Domain {domain_id} not found")

        knowledge_base = await self._resolve_upload_knowledge_base(
            domain=domain,
            customer_id=customer_id,
            knowledge_base_id=knowledge_base_id,
        )

        if not self.object_storage_service.settings_service.resolve_storage_config(customer_id):
            raise NativeRAGError(
                "Tenant object storage is not configured. "
                "Configure S3/MinIO in Tenant Admin > Storage before uploading documents."
            )
        
        # Create document record
        doc = RAGFlowDocument(
            domain_id=domain_id,
            knowledge_base_id=knowledge_base.id,
            customer_id=customer_id,
            original_filename=filename,
            file_size=len(file_content),
            mime_type=mime_type,
            status=RAGFlowDocumentStatus.PENDING,
            uploaded_by_user_id=user_id
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        try:
            await self._persist_document_blob(
                document=doc,
                file_content=file_content,
                mime_type=mime_type,
            )
        except Exception as exc:
            self.db.delete(doc)
            self.db.commit()
            raise NativeRAGError(f"Failed to persist document blob: {exc}") from exc

        knowledge_base.status = KnowledgeBaseStatus.INDEXING.value
        self.db.commit()
        
        # Process document synchronously (more reliable than background task)
        await self._process_document(
            doc.id,
            domain,
            knowledge_base,
            file_content,
            filename,
            mime_type,
        )
        
        # Refresh to get updated status
        self.db.refresh(doc)
        return doc

    async def register_external_document(
        self,
        *,
        domain_id: int,
        customer_id: str,
        knowledge_base_id: int,
        filename: str,
        file_size: int,
        mime_type: str,
        uploaded_by_user_id: Optional[int] = None,
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> RAGFlowDocument:
        """Create a PENDING document record without downloading or processing it.

        Used by the S3 sync service to decouple discovery from processing.
        """
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            raise NativeRAGError(f"Domain {domain_id} not found")

        knowledge_base = await self._resolve_upload_knowledge_base(
            domain=domain,
            customer_id=customer_id,
            knowledge_base_id=knowledge_base_id,
        )

        doc = RAGFlowDocument(
            domain_id=domain_id,
            knowledge_base_id=knowledge_base.id,
            customer_id=customer_id,
            original_filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            status=RAGFlowDocumentStatus.PENDING,
            uploaded_by_user_id=uploaded_by_user_id,
            document_metadata=document_metadata or None,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        knowledge_base.status = KnowledgeBaseStatus.INDEXING.value
        self.db.commit()
        return doc

    async def process_document_from_s3(self, doc_id: int, customer_id: str) -> None:
        """Download a PENDING document from S3 and run the full parse/chunk/index pipeline."""
        doc = self.db.query(RAGFlowDocument).filter(RAGFlowDocument.id == doc_id).first()
        if not doc:
            raise NativeRAGError(f"Document {doc_id} not found")
        if doc.status not in (RAGFlowDocumentStatus.PENDING, RAGFlowDocumentStatus.FAILED):
            logger.info("Skipping doc %s (status=%s)", doc_id, doc.status)
            return

        metadata = doc.document_metadata if isinstance(doc.document_metadata, dict) else {}
        source = metadata.get("source") or {}
        storage = metadata.get("storage") or {}
        bucket = storage.get("bucket") or source.get("bucket")
        object_key = source.get("object_key")
        if not bucket or not object_key:
            doc.status = RAGFlowDocumentStatus.FAILED
            doc.processing_error = "Missing S3 bucket/object_key in document metadata"
            self.db.commit()
            return

        domain = self.db.query(RAGFlowDomain).filter(RAGFlowDomain.id == doc.domain_id).first()
        if not domain:
            doc.status = RAGFlowDocumentStatus.FAILED
            doc.processing_error = f"Domain {doc.domain_id} not found"
            self.db.commit()
            return

        knowledge_base = (
            self.db.query(KnowledgeBase).filter(KnowledgeBase.id == doc.knowledge_base_id).first()
            if doc.knowledge_base_id
            else None
        )

        object_payload = await self.object_storage_service.get_object_bytes(
            customer_id=customer_id,
            bucket=bucket,
            object_key=object_key,
        )
        file_content = object_payload.get("content")
        if not isinstance(file_content, (bytes, bytearray)) or not file_content:
            doc.status = RAGFlowDocumentStatus.FAILED
            doc.processing_error = f"S3 object is empty: {object_key}"
            self.db.commit()
            return

        await self._process_document(
            doc.id,
            domain,
            knowledge_base,
            bytes(file_content),
            doc.original_filename,
            doc.mime_type,
        )

        await self._refresh_workspace_and_kb_stats(
            domain_id=doc.domain_id,
            customer_id=customer_id,
            knowledge_base_id=doc.knowledge_base_id,
        )
        self.db.commit()

    async def ingest_external_document(
        self,
        *,
        domain_id: int,
        customer_id: str,
        knowledge_base_id: int,
        file_content: bytes,
        filename: str,
        mime_type: str,
        uploaded_by_user_id: Optional[int] = None,
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> RAGFlowDocument:
        """
        Ingest a document from an external source (e.g., S3 sync path).

        Unlike direct uploads, this path does not persist a managed blob copy by default.
        """
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            raise NativeRAGError(f"Domain {domain_id} not found")

        knowledge_base = await self._resolve_upload_knowledge_base(
            domain=domain,
            customer_id=customer_id,
            knowledge_base_id=knowledge_base_id,
        )

        doc = RAGFlowDocument(
            domain_id=domain_id,
            knowledge_base_id=knowledge_base.id,
            customer_id=customer_id,
            original_filename=filename,
            file_size=len(file_content),
            mime_type=mime_type,
            status=RAGFlowDocumentStatus.PENDING,
            uploaded_by_user_id=uploaded_by_user_id,
            document_metadata=document_metadata or None,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        knowledge_base.status = KnowledgeBaseStatus.INDEXING.value
        self.db.commit()

        await self._process_document(
            doc.id,
            domain,
            knowledge_base,
            file_content,
            filename,
            mime_type,
        )

        self.db.refresh(doc)
        return doc
    
    def _get_parser_for_knowledge_base(
        self,
        domain: RAGFlowDomain,
        knowledge_base: Optional[KnowledgeBase],
    ) -> DocumentParser:
        """Create parser configuration resolved from KB first, workspace fallback."""
        settings = self.settings

        # Map configured parser value to native parser enum.
        parser_type_map = {
            "naive": ParserType.NAIVE,
            "docling": ParserType.DOCLING,
            "vlm": ParserType.VLM,
            "custom-vlm": ParserType.CUSTOM_VLM,
            "gpt-4o": ParserType.GPT4O,
            "deepdoc": ParserType.DOCLING,
        }

        parser_value = None
        parser_config: Dict[str, Any] = {}
        chunk_token_count = None

        if knowledge_base is not None:
            parser_value = knowledge_base.parser_type
            parser_config = dict(knowledge_base.parser_config or {})
            chunk_token_count = knowledge_base.chunk_token_count

        if not parser_value and domain.parser_type:
            parser_value = domain.parser_type.value
            parser_config = dict(domain.parser_config or {})
            chunk_token_count = chunk_token_count or domain.chunk_token_count

        parser_value = parser_value or "naive"
        parser_type = parser_type_map.get(parser_value, ParserType.NAIVE)

        configured_vlm_model = (
            parser_config.get("custom_vlm_model")
            or parser_config.get("vlm_model")
            or settings.rag_vlm_model
            or "default"
        )

        logger.info(
            "Resolved parser for workspace=%s kb=%s parser=%s mapped=%s chunk_tokens=%s",
            domain.id,
            knowledge_base.id if knowledge_base else None,
            parser_value,
            parser_type.value,
            chunk_token_count or settings.ragflow_default_chunk_size or 512,
        )

        return DocumentParser(
            parser_type=parser_type,
            chunk_size=chunk_token_count or settings.ragflow_default_chunk_size or 512,
            chunk_overlap=50,
            vlm_base_url=settings.rag_vlm_base_url or "http://localhost:8000/v1",
            vlm_model=configured_vlm_model,
            vlm_api_key=settings.rag_vlm_api_key if hasattr(settings, 'rag_vlm_api_key') else None,
            openai_api_key=settings.openai_api_key if hasattr(settings, 'openai_api_key') else None,
            page_parse_concurrency=settings.rag_parser_page_concurrency,
            page_batch_size=settings.rag_parser_page_batch_size,
            request_timeout_seconds=settings.rag_parser_request_timeout_seconds,
            retry_attempts=settings.rag_parser_retry_attempts,
            retry_backoff_seconds=settings.rag_parser_retry_backoff_seconds,
            openai_max_tokens=settings.rag_parser_openai_max_tokens,
        )
    
    async def _process_document_remote(
        self,
        doc: RAGFlowDocument,
        domain: RAGFlowDomain,
        knowledge_base: Optional[KnowledgeBase],
        file_content: bytes,
        filename: str,
        mime_type: str,
    ):
        """Delegate document processing to the remote RAG ingestion service."""
        doc.status = RAGFlowDocumentStatus.PARSING
        doc.progress = 10
        doc.processing_started_at = datetime.utcnow()
        self.db.commit()

        try:
            kb_name = knowledge_base.name if knowledge_base else None
            kb_desc = knowledge_base.description if knowledge_base else None

            result = await self._ingestion_client.ingest(
                file_content=file_content,
                workspace_id=domain.id,
                document_id=doc.id,
                filename=filename,
                mime_type=mime_type,
                customer_id=domain.customer_id,
                knowledge_base_id=doc.knowledge_base_id,
                knowledge_base_name=kb_name,
                knowledge_base_description=kb_desc,
                workspace_name=domain.display_name or domain.name,
            )

            if result.status == "failed":
                raise Exception(result.error or "Remote ingestion failed")

            doc.status = RAGFlowDocumentStatus.COMPLETED
            doc.chunk_count = result.chunks_indexed
            doc.token_count = result.total_tokens
            doc.processing_completed_at = datetime.utcnow()
            doc.progress = 100

            # Store enrichment metadata from remote service
            existing_meta = dict(doc.document_metadata or {})
            if result.enrichment:
                existing_meta["enrichment"] = result.enrichment
                existing_meta["enrichment"]["enrichment_tier"] = result.enrichment.get(
                    "enrichment_tier", self.settings.rag_metadata_enrichment_tier or "standard"
                )
            doc.document_metadata = existing_meta

            await self._refresh_workspace_and_kb_stats(
                domain_id=domain.id,
                customer_id=domain.customer_id,
                knowledge_base_id=doc.knowledge_base_id,
            )
            self.db.commit()

            logger.info(
                "Remote ingestion complete for %s: %s chunks (job=%s)",
                filename, result.chunks_indexed, result.job_id,
            )

        except Exception as e:
            logger.error("Remote ingestion failed for %s: %s", filename, e)
            doc.status = RAGFlowDocumentStatus.FAILED
            doc.processing_error = str(e)
            doc.progress = -1
            await self._refresh_workspace_and_kb_stats(
                domain_id=domain.id,
                customer_id=domain.customer_id,
                knowledge_base_id=doc.knowledge_base_id,
            )
            self.db.commit()

    async def _process_document(
        self,
        doc_id: int,
        domain: RAGFlowDomain,
        knowledge_base: Optional[KnowledgeBase],
        file_content: bytes,
        filename: str,
        mime_type: str
    ):
        """Process document: parse, chunk, embed, index.

        When RAG_INGESTION_SERVICE_URL is configured, delegates the heavy
        pipeline to the remote ingestion service. Otherwise runs in-process.
        """
        doc = self.db.query(RAGFlowDocument).filter(RAGFlowDocument.id == doc_id).first()
        if not doc:
            return

        # --- Remote ingestion path ---
        if self._ingestion_client is not None:
            await self._process_document_remote(doc, domain, knowledge_base, file_content, filename, mime_type)
            return

        # --- Local in-process path (default) ---
        doc.status = RAGFlowDocumentStatus.PARSING
        doc.progress = max(int(doc.progress or 0), 5)
        doc.processing_started_at = datetime.utcnow()
        self.db.commit()
        
        try:
            # Create parser using KB-level settings (workspace fallback).
            domain_parser = self._get_parser_for_knowledge_base(domain, knowledge_base)
            last_parse_progress_commit = int(doc.progress or 0)

            async def _on_parse_progress(completed_pages: int, total_pages: int) -> None:
                """Persist page-level parse progress for long OCR runs."""
                nonlocal last_parse_progress_commit
                if total_pages <= 0:
                    return
                bounded_completed = max(0, min(completed_pages, total_pages))
                ratio = bounded_completed / total_pages
                target_progress = 5 + int(ratio * 30)  # Parse stage owns 5-35%.
                if target_progress <= last_parse_progress_commit:
                    return
                doc.progress = max(int(doc.progress or 0), target_progress)
                self.db.commit()
                last_parse_progress_commit = target_progress

            # Parse document using resolved parser.
            # For GPT-4o/GPT-5 parsers, use structured parsing to get LLM-identified
            # logical sections with headings, types, and page numbers baked in.
            use_structured = domain_parser.parser_type in (ParserType.GPT4O, ParserType.GPT5)
            logger.info(
                "Parsing document %s with parser: %s (structured=%s)",
                filename, domain_parser.parser_type.value, use_structured,
            )

            if use_structured and hasattr(domain_parser, '_parse_with_openai_structured'):
                parsed = await domain_parser._parse_with_openai_structured(
                    file_content, filename, mime_type,
                    progress_callback=_on_parse_progress,
                    model="gpt-4o" if domain_parser.parser_type == ParserType.GPT4O else "gpt-5.2",
                )
            else:
                parsed = await domain_parser.parse_file(
                    file_content, filename, mime_type,
                    progress_callback=_on_parse_progress,
                )
            
            if not parsed.success:
                raise Exception(parsed.error or "Parse failed")

            # Parsing completed; move progress so UI reflects active work.
            doc.progress = max(int(doc.progress or 0), 35)
            self.db.commit()

            # ---- Step 2: Document-level metadata enrichment ----
            doc_meta = await self.metadata_enrichment.enrich_document_metadata(
                file_content=file_content,
                filename=filename,
                mime_type=mime_type,
                parsed_text=parsed.content,
                page_count=parsed.page_count,
            )

            # Persist enriched document metadata to Postgres
            existing_meta = dict(doc.document_metadata or {})
            existing_meta["enrichment"] = {
                "title": doc_meta.title,
                "summary": doc_meta.summary,
                "language": doc_meta.language,
                "document_type": doc_meta.document_type,
                "key_topics": doc_meta.key_topics,
                "total_pages": doc_meta.total_pages,
                "file_type": doc_meta.file_type,
                "author": doc_meta.author,
                "creation_date": doc_meta.creation_date,
                "producer": doc_meta.producer,
                "enrichment_tier": self.metadata_enrichment.enrichment_tier,
            }
            if doc_meta.pdf_metadata:
                existing_meta["pdf_metadata"] = doc_meta.pdf_metadata

            # Ensure storage metadata is present for PDF serving.
            # If the doc came from S3 sync, source/storage are already set.
            # If processed directly, resolve from the KB source config.
            if "storage" not in existing_meta or not existing_meta["storage"]:
                source_info = existing_meta.get("source") or {}
                kb_bucket = None
                if knowledge_base and knowledge_base.source_config:
                    kb_sc = knowledge_base.source_config if isinstance(knowledge_base.source_config, dict) else {}
                    kb_bucket = kb_sc.get("bucket")
                resolved_bucket = source_info.get("bucket") or kb_bucket
                if resolved_bucket:
                    existing_meta["storage"] = {
                        "bucket": resolved_bucket,
                        "backend": "s3",
                        "managed": False,
                        "object_key": source_info.get("object_key") or filename,
                    }

            doc.document_metadata = existing_meta
            self.db.commit()

            logger.info(
                "Document metadata enriched for %s: title=%s type=%s language=%s topics=%s",
                filename, doc_meta.title, doc_meta.document_type, doc_meta.language,
                doc_meta.key_topics,
            )
            doc.progress = max(int(doc.progress or 0), 40)
            self.db.commit()

            # ---- Step 3: Chunk content ----
            chunk_token_count = (
                (knowledge_base.chunk_token_count if knowledge_base else None)
                or domain.chunk_token_count
                or self.settings.ragflow_default_chunk_size
                or 512
            )
            chunker = ChunkingService(
                chunk_size=chunk_token_count,
                chunk_overlap=50,
                strategy=ChunkingStrategy.SEMANTIC,
            )
            base_metadata = {
                "filename": filename,
                "doc_id": doc_id,
                "knowledge_base_id": doc.knowledge_base_id,
                "knowledge_base_path": (
                    f"workspace/{domain.id}/kb/{doc.knowledge_base_id}"
                    if doc.knowledge_base_id is not None
                    else None
                ),
            }

            # Use LLM-identified sections when structured parse produced them
            if parsed.structured_sections:
                chunks = chunker.chunk_from_structured_sections(
                    parsed.structured_sections,
                    metadata=base_metadata,
                )
                logger.info(
                    "LLM chunking: %d sections → %d chunks for %s",
                    len(parsed.structured_sections), len(chunks), filename,
                )
            else:
                chunks = chunker.chunk_text(parsed.content, metadata=base_metadata)
                logger.info("Semantic chunking: %d chunks for %s", len(chunks), filename)

            if not chunks:
                raise Exception("No chunks generated")
            doc.progress = max(int(doc.progress or 0), 50)
            self.db.commit()

            # ---- Step 4: Structural chunk metadata enrichment ----
            kb_name = knowledge_base.name if knowledge_base else None
            kb_desc = knowledge_base.description if knowledge_base else None

            chunk_metadata_list = self.metadata_enrichment.enrich_chunks_structural(
                chunks,
                parsed_text=parsed.content,
                filename=filename,
                doc_id=doc_id,
                doc_metadata=doc_meta,
                knowledge_base_id=doc.knowledge_base_id,
                knowledge_base_name=kb_name,
                knowledge_base_description=kb_desc,
                workspace_id=domain.id,
                workspace_name=domain.display_name or domain.name,
            )

            doc.progress = max(int(doc.progress or 0), 55)
            self.db.commit()

            # ---- Step 5: LLM chunk enrichment (FULL tier only) ----
            chunk_metadata_list = await self.metadata_enrichment.enrich_chunks_with_llm(
                chunks, chunk_metadata_list, doc_meta.title or filename,
            )

            doc.progress = max(int(doc.progress or 0), 60)
            self.db.commit()

            # --- FASB legacy index (keep for backward compat) ---
            if self._is_fasb_workspace(domain):
                try:
                    fasb_chunks_payload: List[Dict[str, Any]] = []
                    for i, chunk in enumerate(chunks):
                        chunk_metadata = chunk.metadata if isinstance(chunk.metadata, dict) else {}
                        section_path = chunk_metadata.get("section_path")
                        if not isinstance(section_path, list):
                            section_path = []
                        fasb_chunks_payload.append(
                            {
                                "chunk_index": i,
                                "chunk_id": f"{doc_id}_{i}",
                                "chunk_type": chunk_metadata.get("chunk_type") or "workspace_document",
                                "source_path": filename,
                                "text": chunk.text,
                                "token_count": chunk.token_count,
                                "section_path": section_path,
                                "topic_number": chunk_metadata.get("topic_number"),
                                "subtopic_number": chunk_metadata.get("subtopic_number"),
                                "section_number": chunk_metadata.get("section_number"),
                                "paragraph_id": chunk_metadata.get("paragraph_id"),
                                "is_superseded": False,
                            }
                        )

                    fasb_service = get_fasb_service()
                    await asyncio.to_thread(
                        fasb_service.index_workspace_chunks,
                        workspace_id=domain.id,
                        knowledge_base_id=doc.knowledge_base_id,
                        customer_id=domain.customer_id,
                        document_id=doc_id,
                        filename=filename,
                        chunks=fasb_chunks_payload,
                    )
                except Exception as exc:
                    logger.warning("fasb_legacy_index_failed doc_id=%s error=%s", doc_id, str(exc))

            # ---- Step 6: Generate embeddings (with contextual headers) ----
            # Embed contextual text (header + chunk) for better semantic matching,
            # but store original chunk text in the index for display/citation.
            embedding_texts = [
                self.metadata_enrichment.build_embedding_text(c.text, cm)
                for c, cm in zip(chunks, chunk_metadata_list)
            ]
            embeddings = await self.embedding_service.embed_texts(embedding_texts)
            doc.progress = max(int(doc.progress or 0), 80)
            self.db.commit()

            # ---- Step 7: Build enriched vector documents for indexing ----
            vector_docs = []
            for i, (chunk, embedding, cm) in enumerate(zip(chunks, embeddings, chunk_metadata_list)):
                enriched_meta = cm.to_flat_dict()

                vector_docs.append(VectorDocument(
                    id=f"{doc_id}_{i}",
                    domain_id=str(domain.id),
                    knowledge_base_id=str(doc.knowledge_base_id) if doc.knowledge_base_id is not None else None,
                    document_id=str(doc_id),
                    chunk_index=i,
                    text=chunk.text,
                    embedding=embedding,
                    metadata=enriched_meta,
                    hypothetical_questions=cm.hypothetical_questions or None,
                ))

            indexed = await self.vector_store.index_documents(str(domain.id), vector_docs)
            if indexed <= 0:
                raise Exception("No chunks were indexed in vector store")
            doc.progress = max(int(doc.progress or 0), 90)
            self.db.commit()
            
            # Update document status
            doc.status = RAGFlowDocumentStatus.COMPLETED
            doc.chunk_count = len(chunks)
            doc.token_count = sum(c.token_count for c in chunks)
            doc.processing_completed_at = datetime.utcnow()
            doc.progress = 100

            await self._refresh_workspace_and_kb_stats(
                domain_id=domain.id,
                customer_id=domain.customer_id,
                knowledge_base_id=doc.knowledge_base_id,
            )
            self.db.commit()
            logger.info(
                "Successfully processed %s: %s chunks indexed (indexed=%s, kb_id=%s)",
                filename,
                len(chunks),
                indexed,
                doc.knowledge_base_id,
            )
            
        except Exception as e:
            logger.error(f"Failed to process document {filename}: {e}")
            doc.status = RAGFlowDocumentStatus.FAILED
            doc.processing_error = str(e)
            doc.progress = -1
            await self._refresh_workspace_and_kb_stats(
                domain_id=domain.id,
                customer_id=domain.customer_id,
                knowledge_base_id=doc.knowledge_base_id,
            )
            self.db.commit()
    
    async def get_document(self, document_id: int, customer_id: str) -> Optional[RAGFlowDocument]:
        """Get a document by ID."""
        return self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.id == document_id,
            RAGFlowDocument.customer_id == customer_id
        ).first()
    
    async def list_documents(
        self,
        domain_id: int,
        customer_id: str,
        knowledge_base_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RAGFlowDocument]:
        """List documents in a domain."""
        query = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == domain_id,
            RAGFlowDocument.customer_id == customer_id
        )
        if knowledge_base_id is not None:
            query = query.filter(RAGFlowDocument.knowledge_base_id == knowledge_base_id)
        return query.order_by(RAGFlowDocument.created_at.desc()).offset(offset).limit(limit).all()
    
    async def delete_document(self, document_id: int, customer_id: str) -> bool:
        """Delete a document and its chunks."""
        doc = await self.get_document(document_id, customer_id)
        if not doc:
            return False

        knowledge_base_id = doc.knowledge_base_id
        domain = await self.get_domain(doc.domain_id, customer_id)

        if self._is_fasb_workspace(domain):
            try:
                fasb_service = get_fasb_service()
                await asyncio.to_thread(
                    fasb_service.delete_workspace_document_chunks,
                    document_id=document_id,
                    knowledge_base_id=knowledge_base_id,
                    source_filter="all",
                )
            except Exception as e:
                logger.warning(f"Failed to delete FASB index chunks: {e}")
        
        # Delete chunks from vector store
        try:
            await self.vector_store.delete_document_chunks(str(doc.domain_id), str(document_id))
        except Exception as e:
            logger.warning(f"Failed to delete chunks: {e}")

        await self._delete_document_blob(doc)

        self.db.delete(doc)
        self.db.flush()
        await self._refresh_workspace_and_kb_stats(
            domain_id=doc.domain_id,
            customer_id=customer_id,
            knowledge_base_id=knowledge_base_id,
        )
        self.db.commit()

        return True
    
    async def start_parsing(self, domain_id: int, customer_id: str) -> Dict[str, Any]:
        """Re-trigger parsing for pending documents."""
        docs = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == domain_id,
            RAGFlowDocument.customer_id == customer_id,
            RAGFlowDocument.status.in_([RAGFlowDocumentStatus.PENDING, RAGFlowDocumentStatus.FAILED])
        ).all()
        
        # Note: Would need to re-fetch file content to re-process
        # For now, return count of documents that would be processed
        return {"documents_to_process": len(docs)}
    
    # ==================== Retrieval ====================
    
    async def retrieve(
        self,
        domain_id: int,
        customer_id: str,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for a query."""
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            raise NativeRAGError(f"Domain {domain_id} not found")

        normalized_min_score = self._normalize_min_score(min_score)
        
        chunks = await self.retrieval_service.retrieve(
            domain_id=str(domain.id),
            query=query,
            top_k=top_k,
            min_score=normalized_min_score,
            knowledge_base_ids=knowledge_base_ids,
        )
        
        return [c.to_dict() for c in chunks]
    
    # ==================== Chat ====================
    
    async def _chat_fasb(
        self,
        domain: RAGFlowDomain,
        customer_id: str,
        question: str,
        conversation_id: Optional[int] = None,
        user_id: Optional[int] = None,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Handle chat for FASB domain using the FASB service.
        
        FASB uses AWS OpenSearch Serverless instead of local vector store.
        """
        # Get or create conversation
        conversation = None
        if conversation_id:
            conversation = self.db.query(RAGFlowConversation).filter(
                RAGFlowConversation.id == conversation_id,
                RAGFlowConversation.customer_id == customer_id
            ).first()
        
        if not conversation:
            import uuid
            conversation = RAGFlowConversation(
                domain_id=domain.id,
                customer_id=customer_id,
                user_id=user_id or 0,
                uuid=str(uuid.uuid4()),
                title=question[:100]
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
        
        # Build conversation context for follow-up questions
        conversation_context = None
        if conversation and conversation_id:
            messages = self.db.query(RAGFlowMessage).filter(
                RAGFlowMessage.conversation_id == conversation_id
            ).order_by(RAGFlowMessage.created_at.desc()).limit(10).all()
            if messages:
                context_parts = [f"Previous conversation ({len(messages)} messages):"]
                for msg in reversed(messages):
                    role_label = "User" if msg.role == "user" else "Assistant"
                    content_preview = msg.content[:500] + ("..." if len(msg.content) > 500 else "")
                    context_parts.append(f"{role_label}: {content_preview}")
                conversation_context = "\n".join(context_parts)

        # Get FASB answer
        fasb_service = get_fasb_service()
        fasb_result = fasb_service.answer(
            question,
            customer_id=customer_id,
            knowledge_base_ids=knowledge_base_ids,
            conversation_context=conversation_context,
        )
        
        answer = fasb_result.get("answer", "")
        sources = fasb_result.get("sources", [])
        
        # Save user message
        user_msg = RAGFlowMessage(
            conversation_id=conversation.id,
            role="user",
            content=question
        )
        self.db.add(user_msg)
        self.db.flush()
        
        # Save assistant message with sources
        chunks = [{
            "content": s.get("text_preview", ""),
            "document_name": s.get("citation", ""),
            "similarity": 1.0
        } for s in sources]
        if knowledge_base_ids is not None:
            for chunk in chunks:
                chunk["knowledge_base_ids"] = knowledge_base_ids
        
        assistant_msg = RAGFlowMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            retrieved_chunks=chunks,
            chunk_count=len(sources)
        )
        self.db.add(assistant_msg)
        self.db.flush()
        
        # Update conversation
        conversation.message_count = (conversation.message_count or 0) + 2
        conversation.last_message_at = datetime.utcnow()
        
        self.db.commit()
        
        # Auto-generate title after first message exchange (fire-and-forget)
        if conversation.message_count == 2 and conversation.title == "New conversation":
            try:
                from src.tasks.ragflow_tasks import generate_conversation_title
                generate_conversation_title.delay(conversation.id, customer_id, question)
            except Exception:
                pass  # Never let title generation affect the chat response
        
        return {
            "answer": answer,
            "conversation_id": conversation.id,
            "chunks": chunks,
            "model": fasb_result.get("model", "gpt-4o"),
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0
            },
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_msg.id,
            "user_message_created_at": user_msg.created_at.isoformat() if user_msg.created_at else datetime.utcnow().isoformat(),
            "assistant_message_created_at": assistant_msg.created_at.isoformat() if assistant_msg.created_at else datetime.utcnow().isoformat()
        }
    
    async def chat(
        self,
        domain_id: int,
        customer_id: str,
        question: str,
        conversation_id: Optional[int] = None,
        user_id: Optional[int] = None,
        top_k: int = 5,
        min_score: float = 0.0,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Chat with documents in a domain.
        
        Returns answer with sources.
        """
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            raise NativeRAGError(f"Domain {domain_id} not found")

        # Unified chat path for ALL workspaces (FASB, generic, etc.)
        # Data source is abstracted away: retrieval always goes through
        # the local vector store index for this workspace.

        # Get or create conversation
        conversation = None
        history = []
        if conversation_id:
            conversation = self.db.query(RAGFlowConversation).filter(
                RAGFlowConversation.id == conversation_id,
                RAGFlowConversation.customer_id == customer_id
            ).first()
            if conversation:
                # Load recent messages
                messages = self.db.query(RAGFlowMessage).filter(
                    RAGFlowMessage.conversation_id == conversation_id
                ).order_by(RAGFlowMessage.created_at.desc()).limit(10).all()
                history = [ChatMessage(role=m.role, content=m.content) for m in reversed(messages)]
        
        if not conversation:
            conversation = RAGFlowConversation(
                domain_id=domain_id,
                customer_id=customer_id,
                user_id=user_id or 0,
                uuid=str(uuid.uuid4()),
                title=question[:100]
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
        
        # Get domain-specific chat service with custom prompts
        chat_service = self._get_chat_service_for_domain(domain, customer_id)
        normalized_min_score = self._normalize_min_score(min_score)
        
        # Get response
        chat_kwargs = {
            "domain_id": str(domain.id),
            "question": question,
            "conversation_history": history,
            "top_k": top_k,
            "min_score": normalized_min_score,
        }
        if knowledge_base_ids is not None:
            chat_kwargs["knowledge_base_ids"] = knowledge_base_ids
        if hasattr(chat_service, "template"):
            chat_kwargs["customer_id"] = customer_id
            chat_kwargs["session_id"] = str(conversation.id)

        import time as _time
        _chat_start = _time.time()

        response = await chat_service.chat(
            **chat_kwargs
        )
        _chat_latency_ms = (_time.time() - _chat_start) * 1000

        # --- Langfuse tracing for retrieval + generation ---
        try:
            langfuse_svc = get_langfuse_service()
            langfuse_svc.trace_retrieval(
                query=question,
                chunks=[c.to_dict() for c in response.chunks],
                workspace_id=domain.id,
                domain=domain.name,
                customer_id=customer_id,
                session_id=str(conversation.id),
            )
            langfuse_svc.trace_workspace_chat(
                model=response.model,
                input_data={"question": question, "workspace_id": domain.id, "conversation_id": conversation.id},
                output_data={"answer": response.answer[:500], "chunks_used": len(response.chunks)},
                usage_details={
                    "input": response.prompt_tokens,
                    "output": response.completion_tokens,
                },
                workspace_id=domain.id,
                domain=domain.name,
                customer_id=customer_id,
                session_id=str(conversation.id),
                latency_ms=_chat_latency_ms,
            )
        except Exception:
            pass

        # Build structured Sources section (same format as FASB) so frontend
        # can parse citations uniformly across all workspace types.
        answer_with_sources = self._append_sources_section(
            response.answer, response.chunks
        )
        
        # Save messages
        user_msg = RAGFlowMessage(
            conversation_id=conversation.id,
            role="user",
            content=question
        )
        self.db.add(user_msg)
        self.db.flush()  # Get ID before commit
        
        assistant_msg = RAGFlowMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=answer_with_sources,
            retrieved_chunks=[c.to_dict() for c in response.chunks],
            chunk_count=len(response.chunks),
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens
        )
        self.db.add(assistant_msg)
        self.db.flush()  # Get ID before commit
        
        # Update conversation
        conversation.message_count = (conversation.message_count or 0) + 2
        conversation.last_message_at = datetime.utcnow()
        
        self.db.commit()
        
        # Auto-generate title after first message exchange (fire-and-forget)
        if conversation.message_count == 2 and conversation.title == "New conversation":
            try:
                from src.tasks.ragflow_tasks import generate_conversation_title
                generate_conversation_title.delay(conversation.id, customer_id, question)
            except Exception:
                pass

        # Pre-fetch cited PDFs into local MinIO cache (fire-and-forget)
        try:
            cited_doc_ids = list({
                int(c.document_id) for c in response.chunks
                if c.document_id and str(c.document_id).isdigit()
            })
            if cited_doc_ids:
                from src.services.pdf_cache_service import PDFCacheService
                pdf_cache = PDFCacheService(self.db)
                asyncio.create_task(pdf_cache.prefetch_cited_pdfs(cited_doc_ids))
        except Exception:
            pass

        return {
            "answer": answer_with_sources,
            "conversation_id": conversation.id,
            "chunks": [c.to_dict() for c in response.chunks],
            "model": response.model,
            "usage": {
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens
            },
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_msg.id,
            "user_message_created_at": user_msg.created_at.isoformat() if user_msg.created_at else datetime.utcnow().isoformat(),
            "assistant_message_created_at": assistant_msg.created_at.isoformat() if assistant_msg.created_at else datetime.utcnow().isoformat()
        }
    
    async def chat_stream(
        self,
        domain_id: int,
        customer_id: str,
        question: str,
        conversation_id: Optional[int] = None,
        user_id: Optional[int] = None,
        top_k: int = 5,
        min_score: float = 0.0,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> AsyncIterator[str]:
        """Stream chat response."""
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            raise NativeRAGError(f"Domain {domain_id} not found")
        
        import json
        
        # Get domain-specific chat service with custom prompts
        chat_service = self._get_chat_service_for_domain(domain, customer_id)
        
        stream_kwargs = {
            "domain_id": str(domain.id),
            "question": question,
            "top_k": top_k,
            "min_score": self._normalize_min_score(min_score),
        }
        if knowledge_base_ids is not None:
            stream_kwargs["knowledge_base_ids"] = knowledge_base_ids
        if hasattr(chat_service, "template"):
            stream_kwargs["customer_id"] = customer_id
            stream_kwargs["session_id"] = str(conversation_id) if conversation_id else None

        async for event in chat_service.chat_stream(**stream_kwargs):
            yield json.dumps(event)
    
    # ==================== Conversations ====================
    
    async def list_conversations(
        self,
        domain_id: int,
        customer_id: str,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[RAGFlowConversation]:
        """List conversations for a domain."""
        query = self.db.query(RAGFlowConversation).filter(
            RAGFlowConversation.domain_id == domain_id,
            RAGFlowConversation.customer_id == customer_id
        )
        
        if user_id:
            query = query.filter(RAGFlowConversation.user_id == user_id)
        
        return query.order_by(RAGFlowConversation.last_message_at.desc()).offset(offset).limit(limit).all()
    
    async def get_conversation(
        self,
        conversation_id: int,
        customer_id: str
    ) -> Optional[RAGFlowConversation]:
        """Get a conversation with messages."""
        return self.db.query(RAGFlowConversation).filter(
            RAGFlowConversation.id == conversation_id,
            RAGFlowConversation.customer_id == customer_id
        ).first()
    
    async def delete_conversation(self, conversation_id: int, customer_id: str) -> bool:
        """Delete a conversation."""
        conv = await self.get_conversation(conversation_id, customer_id)
        if not conv:
            return False
        
        self.db.delete(conv)
        self.db.commit()
        return True
    
    async def create_conversation(
        self,
        domain_id: int,
        customer_id: str,
        user_id: int,
        title: Optional[str] = None,
        source: Optional[str] = None,
    ) -> RAGFlowConversation:
        """Create a new conversation.
        
        Includes dedup check: if the same user already has a recent empty
        conversation (created within the last 10 seconds) in the same workspace,
        return that instead of creating a duplicate. This guards against
        double-creation from React StrictMode or rapid clicks.
        """
        # Dedup: check for a recent empty conversation by this user in this workspace
        recent_empty = self.db.query(RAGFlowConversation).filter(
            RAGFlowConversation.domain_id == domain_id,
            RAGFlowConversation.user_id == user_id,
            RAGFlowConversation.customer_id == customer_id,
            RAGFlowConversation.message_count == 0,
            RAGFlowConversation.is_active == True,
            RAGFlowConversation.created_at > datetime.utcnow() - timedelta(seconds=10)
        ).first()
        
        if recent_empty:
            return recent_empty
        
        conversation = RAGFlowConversation(
            domain_id=domain_id,
            customer_id=customer_id,
            user_id=user_id,
            uuid=str(uuid.uuid4()),
            title=title or "New conversation",
            source=source,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
    
    async def get_conversation_by_uuid(
        self,
        conversation_uuid: str,
        customer_id: str
    ) -> Optional[RAGFlowConversation]:
        """Get a conversation by UUID."""
        return self.db.query(RAGFlowConversation).filter(
            RAGFlowConversation.uuid == conversation_uuid,
            RAGFlowConversation.customer_id == customer_id
        ).first()
    
    async def send_message(
        self,
        conversation_id: int,
        customer_id: str,
        content: str,
        user_id: Optional[int] = None,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Send a message in a conversation and get response."""
        conversation = await self.get_conversation(conversation_id, customer_id)
        if not conversation:
            raise NativeRAGError(f"Conversation {conversation_id} not found")
        
        result = await self.chat(
            domain_id=conversation.domain_id,
            customer_id=customer_id,
            question=content,
            conversation_id=conversation_id,
            user_id=user_id or conversation.user_id,
            knowledge_base_ids=knowledge_base_ids,
        )
        
        # Format response to match expected structure using actual DB IDs
        return {
            "user_message": {
                "id": result.get("user_message_id", 0),
                "content": content,
                "role": "user",
                "created_at": result.get("user_message_created_at", datetime.utcnow().isoformat())
            },
            "assistant_message": {
                "id": result.get("assistant_message_id", 0),
                "content": result.get("answer", ""),
                "role": "assistant",
                "chunks": result.get("chunks", []),
                "created_at": result.get("assistant_message_created_at", datetime.utcnow().isoformat())
            },
            "conversation_id": conversation_id
        }
    
    async def retry_failed_documents(self, domain_id: int, customer_id: str) -> Dict[str, Any]:
        """Retry processing for failed and stuck documents by dispatching Celery tasks."""
        retryable = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == domain_id,
            RAGFlowDocument.customer_id == customer_id,
            RAGFlowDocument.status.in_([
                RAGFlowDocumentStatus.FAILED,
                RAGFlowDocumentStatus.PARSING,
                RAGFlowDocumentStatus.PENDING,
            ])
        ).all()

        if not retryable:
            return {"documents_reset": 0, "documents_queued": 0}

        for doc in retryable:
            doc.status = RAGFlowDocumentStatus.PENDING
            doc.processing_error = None
            doc.progress = 0

        kb_ids = {doc.knowledge_base_id for doc in retryable if doc.knowledge_base_id is not None}
        for kb_id in kb_ids:
            kb = await self._get_knowledge_base(
                knowledge_base_id=kb_id,
                domain_id=domain_id,
                customer_id=customer_id,
                require_active=False,
            )
            if kb:
                kb.status = KnowledgeBaseStatus.INDEXING.value

        self.db.commit()

        from src.tasks.ragflow_source_sync_tasks import process_s3_document
        queued = 0
        for doc in retryable:
            try:
                process_s3_document.delay(doc.id, customer_id)
                queued += 1
            except Exception as exc:
                logger.warning("Failed to queue doc %s for retry: %s", doc.id, exc)

        return {"documents_reset": len(retryable), "documents_queued": queued}
    
    # ==================== Aliases for backward compatibility ====================
    
    async def list_domain_documents(
        self,
        domain_id: int,
        customer_id: str,
        knowledge_base_id: Optional[int] = None,
        knowledge_base_ids: Optional[List[int]] = None,
        status: Optional[RAGFlowDocumentStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RAGFlowDocument]:
        """List documents in a domain with optional status filter."""
        query = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == domain_id,
            RAGFlowDocument.customer_id == customer_id
        )
        if knowledge_base_ids:
            query = query.filter(RAGFlowDocument.knowledge_base_id.in_(knowledge_base_ids))
        if knowledge_base_id is not None:
            query = query.filter(RAGFlowDocument.knowledge_base_id == knowledge_base_id)
        if status:
            query = query.filter(RAGFlowDocument.status == status)
        return query.order_by(RAGFlowDocument.created_at.desc()).offset(offset).limit(limit).all()
    
    async def upload_domain_document(
        self,
        domain_id: int,
        customer_id: str,
        file_content: bytes,
        filename: str,
        file_size: Optional[int] = None,
        mime_type: str = "application/octet-stream",
        user_id: Optional[int] = None,
        knowledge_base_id: Optional[int] = None,
    ) -> RAGFlowDocument:
        """Alias for upload_document (file_size is ignored, computed from content)."""
        return await self.upload_document(
            domain_id=domain_id,
            customer_id=customer_id,
            file_content=file_content,
            filename=filename,
            mime_type=mime_type,
            user_id=user_id,
            knowledge_base_id=knowledge_base_id,
        )
    
    async def get_document_status(self, document_id: int, customer_id: str) -> Optional[RAGFlowDocument]:
        """Alias for get_document."""
        return await self.get_document(document_id, customer_id)
    
    async def delete_domain_document(self, document_id: int, customer_id: str) -> bool:
        """Alias for delete_document."""
        return await self.delete_document(document_id, customer_id)


# Alias for backward compatibility
RAGFlowService = NativeRAGService
