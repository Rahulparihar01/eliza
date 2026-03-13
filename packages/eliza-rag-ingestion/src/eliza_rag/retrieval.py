"""
Retrieval Service - Semantic search over document chunks.

Combines embedding generation and vector search for RAG retrieval.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .embeddings import EmbeddingService
from .vector_store import VectorStore, VectorSearchResult

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with enriched context."""
    document_id: str
    document_name: str
    chunk_index: int
    text: str
    score: float
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = None
    # Enriched fields (populated from metadata for convenience)
    chunk_summary: Optional[str] = None
    chunk_type: Optional[str] = None
    key_entities: Optional[List[str]] = None
    knowledge_base_name: Optional[str] = None
    document_title: Optional[str] = None
    section_hierarchy: Optional[List[str]] = None
    page_range: Optional[List[int]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        d = {
            "document_id": self.document_id,
            "document_name": self.document_name,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "score": self.score,
            "section_title": self.section_title,
            "page_number": self.page_number,
            "metadata": self.metadata or {},
        }
        if self.chunk_summary:
            d["chunk_summary"] = self.chunk_summary
        if self.chunk_type:
            d["chunk_type"] = self.chunk_type
        if self.key_entities:
            d["key_entities"] = self.key_entities
        if self.knowledge_base_name:
            d["knowledge_base_name"] = self.knowledge_base_name
        if self.document_title:
            d["document_title"] = self.document_title
        if self.section_hierarchy:
            d["section_hierarchy"] = self.section_hierarchy
        if self.page_range:
            d["page_range"] = self.page_range
        return d


class RetrievalService:
    """
    Semantic retrieval service for RAG applications.
    
    Provides:
    - Query embedding
    - Vector similarity search
    - Result ranking and filtering
    - Context assembly for LLM
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        document_lookup: Optional[callable] = None
    ):
        """
        Initialize retrieval service.
        
        Args:
            embedding_service: Service for generating embeddings
            vector_store: Vector storage backend
            document_lookup: Optional function to get document metadata by ID
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.document_lookup = document_lookup

    # ASC-style references like:
    # - 272-10
    # - 272-10-05
    # - 272-10-05-6
    _ASC_REFERENCE_PATTERN = re.compile(r"\b\d{3}-\d{1,2}(?:-\d{2}(?:-\d+)?)?\b")

    @staticmethod
    def _result_key(document_id: str, chunk_index: int) -> str:
        return f"{document_id}_{chunk_index}"

    @classmethod
    def _extract_reference_tokens(cls, query: str) -> List[str]:
        """Extract ASC-like numeric references from the query."""
        if not query:
            return []

        # Keep unique terms preserving first-seen order.
        seen = set()
        refs: List[str] = []
        for match in cls._ASC_REFERENCE_PATTERN.finditer(query):
            token = match.group(0)
            if token not in seen:
                seen.add(token)
                refs.append(token)

        # Prefer more specific references first (paragraph > section > subtopic).
        refs.sort(key=lambda token: (token.count("-"), len(token)), reverse=True)
        return refs[:5]

    @staticmethod
    def _reference_boost(token: str) -> float:
        """Boost weight for exact numeric references by specificity."""
        specificity = token.count("-")
        if specificity >= 3:  # e.g., 272-10-05-6
            return 2.5
        if specificity == 2:  # e.g., 272-10-05
            return 1.5
        return 0.8  # e.g., 272-10

    async def _to_retrieved_chunk(self, result: VectorSearchResult) -> RetrievedChunk:
        """Convert a VectorSearchResult to RetrievedChunk with enriched metadata."""
        metadata = result.metadata or {}
        doc_name = metadata.get("filename", "Unknown")

        if self.document_lookup:
            try:
                doc_info = await self.document_lookup(result.document_id)
                if doc_info:
                    doc_name = doc_info.get("filename", doc_name)
            except Exception:
                pass

        return RetrievedChunk(
            document_id=result.document_id,
            document_name=doc_name,
            chunk_index=result.chunk_index,
            text=result.text,
            score=result.score,
            section_title=metadata.get("section_title"),
            page_number=metadata.get("page_number"),
            metadata=metadata,
            chunk_summary=metadata.get("chunk_summary"),
            chunk_type=metadata.get("chunk_type"),
            key_entities=metadata.get("key_entities"),
            knowledge_base_name=metadata.get("knowledge_base_name"),
            document_title=metadata.get("document_title"),
            section_hierarchy=metadata.get("section_hierarchy"),
            page_range=metadata.get("page_range"),
        )

    async def _to_retrieved_chunks(self, results: List[VectorSearchResult]) -> List[RetrievedChunk]:
        chunks: List[RetrievedChunk] = []
        for result in results:
            chunks.append(await self._to_retrieved_chunk(result))
        return chunks
    
    async def retrieve(
        self,
        domain_id: str,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        rerank: bool = False,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieve relevant document chunks for a query.
        
        Args:
            domain_id: Domain to search in
            query: Search query
            top_k: Number of results
            min_score: Minimum similarity score (0-1)
            rerank: Whether to rerank results (future: cross-encoder)
            
        Returns:
            List of retrieved chunks sorted by relevance
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_query(query)
        
        # Search vector store
        results = await self.vector_store.search(
            domain_id=domain_id,
            query_embedding=query_embedding,
            top_k=top_k * 2 if rerank else top_k,  # Get more for reranking
            min_score=min_score,
            knowledge_base_ids=knowledge_base_ids,
        )

        # Convert to RetrievedChunk with document metadata
        chunks = await self._to_retrieved_chunks(results)
        
        # TODO: Add reranking with cross-encoder if rerank=True
        
        # Return top_k results
        return chunks[:top_k]
    
    async def retrieve_with_context(
        self,
        domain_id: str,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
        context_size: int = 3,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> tuple[List[RetrievedChunk], str]:
        """
        Retrieve chunks and assemble enriched context for LLM.

        Context includes document title, section hierarchy, page numbers,
        and knowledge base name when available — all derived from the
        metadata enrichment pipeline.
        """
        chunks = await self.retrieve(
            domain_id=domain_id,
            query=query,
            top_k=top_k,
            min_score=min_score,
            knowledge_base_ids=knowledge_base_ids,
        )
        
        context_parts = []
        for i, chunk in enumerate(chunks[:context_size]):
            header_parts = []
            doc_label = chunk.document_title or chunk.document_name
            header_parts.append(f"Document: {doc_label}")
            if chunk.knowledge_base_name:
                header_parts.append(f"Knowledge Base: {chunk.knowledge_base_name}")
            if chunk.section_hierarchy:
                header_parts.append(f"Section: {' > '.join(chunk.section_hierarchy)}")
            elif chunk.section_title:
                header_parts.append(f"Section: {chunk.section_title}")
            if chunk.page_number:
                page_str = str(chunk.page_number)
                if chunk.page_range and len(chunk.page_range) == 2 and chunk.page_range[0] != chunk.page_range[1]:
                    page_str = f"{chunk.page_range[0]}-{chunk.page_range[1]}"
                header_parts.append(f"Page: {page_str}")

            source = f"[{i+1}] " + " | ".join(header_parts)
            context_parts.append(f"{source}\n{chunk.text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        return chunks, context
    
    async def hybrid_retrieve(
        self,
        domain_id: str,
        query: str,
        top_k: int = 5,
        keyword_weight: float = 0.5,
        semantic_weight: float = 0.5,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> List[RetrievedChunk]:
        """
        Hybrid retrieval combining keyword and semantic search.
        
        Uses reciprocal rank fusion to combine results.
        
        Args:
            domain_id: Domain to search
            query: Search query
            top_k: Number of results
            keyword_weight: Weight for keyword search
            semantic_weight: Weight for semantic search
            
        Returns:
            Fused and ranked results
        """
        candidate_top_k = max(top_k * 2, 10)
        reference_tokens = self._extract_reference_tokens(query)

        # Get semantic results
        semantic_results = await self.retrieve(
            domain_id=domain_id,
            query=query,
            top_k=candidate_top_k,
            knowledge_base_ids=knowledge_base_ids,
        )
        logger.info(f"Hybrid search - semantic results: {len(semantic_results)} chunks")
        for i, r in enumerate(semantic_results[:3]):
            logger.info(f"  Semantic result {i}: chunk_idx={r.chunk_index}, score={r.score:.3f}, text[:50]={r.text[:50]}")
        
        # Get keyword results
        keyword_results = await self.vector_store.keyword_search(
            domain_id=domain_id,
            query=query,
            top_k=candidate_top_k,
            knowledge_base_ids=knowledge_base_ids,
        )
        logger.info(f"Hybrid search - keyword results: {len(keyword_results)} chunks")
        for i, r in enumerate(keyword_results[:3]):
            logger.info(f"  Keyword result {i}: chunk_idx={r.chunk_index}, score={r.score:.2f}, text[:50]={r.text[:50]}")

        # Run targeted keyword retrieval for exact ASC-like references (if present).
        # This is critical for queries like "272-10-05-6" where generic semantic + BM25
        # may miss the exact paragraph in top-k.
        reference_results: List[VectorSearchResult] = []
        for token in reference_tokens:
            ref_hits = await self.vector_store.keyword_search(
                domain_id=domain_id,
                query=token,
                top_k=candidate_top_k,
                knowledge_base_ids=knowledge_base_ids,
            )
            reference_results.extend(ref_hits)

        keyword_chunks = await self._to_retrieved_chunks(keyword_results)
        reference_chunks = await self._to_retrieved_chunks(reference_results)
        
        # Reciprocal Rank Fusion (RRF) to combine results
        k = 60  # RRF constant
        scores = {}  # key -> {"chunk": chunk, "score": float}
        
        # Score semantic results
        for rank, chunk in enumerate(semantic_results):
            key = self._result_key(chunk.document_id, chunk.chunk_index)
            if key not in scores:
                scores[key] = {"chunk": chunk, "score": 0.0}
            scores[key]["score"] += semantic_weight * (1 / (k + rank + 1))
        
        # Score keyword results
        for rank, chunk in enumerate(keyword_chunks):
            key = self._result_key(chunk.document_id, chunk.chunk_index)
            if key not in scores:
                scores[key] = {"chunk": chunk, "score": 0.0}
            scores[key]["score"] += keyword_weight * (1 / (k + rank + 1))

        # Add strong boosts for chunks that contain exact reference tokens.
        # This makes direct section/paragraph lookups reliably surface in top-k.
        if reference_tokens:
            for chunk in reference_chunks:
                key = self._result_key(chunk.document_id, chunk.chunk_index)
                if key not in scores:
                    scores[key] = {"chunk": chunk, "score": 0.0}

                text = chunk.text or ""
                matched_tokens = [token for token in reference_tokens if token in text]
                if not matched_tokens:
                    continue

                boost = max(self._reference_boost(token) for token in matched_tokens)
                scores[key]["score"] += boost
        
        # Sort by combined score
        sorted_results = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        
        final_chunks = [item["chunk"] for item in sorted_results[:top_k]]
        logger.info(f"Hybrid search - final {len(final_chunks)} chunks after RRF:")
        for i, chunk in enumerate(final_chunks[:3]):
            logger.info(f"  Final {i}: chunk_idx={chunk.chunk_index}, text[:60]={chunk.text[:60]}")
        
        return final_chunks
    
    def format_context_for_llm(
        self,
        chunks: List[RetrievedChunk],
        max_tokens: int = 4000
    ) -> str:
        """
        Format retrieved chunks into an enriched context string for LLM.

        Includes document title, KB name, section, and page info.
        """
        if not chunks:
            return "No relevant documents found."
        
        context_parts = []
        estimated_tokens = 0
        chars_per_token = 4
        
        for idx, chunk in enumerate(chunks, start=1):
            doc_label = chunk.document_title or chunk.document_name
            header = f"[{idx}] {doc_label}"
            if chunk.knowledge_base_name:
                header += f" (KB: {chunk.knowledge_base_name})"
            if chunk.section_title:
                header += f" — {chunk.section_title}"
            if chunk.page_number:
                header += f" [p.{chunk.page_number}]"

            chunk_text = f"{header}\n{chunk.text}"
            chunk_tokens = len(chunk_text) // chars_per_token
            
            if estimated_tokens + chunk_tokens > max_tokens:
                remaining_chars = (max_tokens - estimated_tokens) * chars_per_token
                if remaining_chars > 100:
                    chunk_text = chunk_text[:remaining_chars] + "..."
                    context_parts.append(chunk_text)
                break
            
            context_parts.append(chunk_text)
            estimated_tokens += chunk_tokens
        
        return "\n\n---\n\n".join(context_parts)
