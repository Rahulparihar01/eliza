"""MCP tool: hybrid search (vector + keyword with RRF fusion)."""

from __future__ import annotations

from typing import Any


async def hybrid_search(
    query: str,
    domain_id: str,
    top_k: int = 10,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7,
    knowledge_base_ids: list[int] | None = None,
    *,
    retrieval_service,
) -> list[dict[str, Any]]:
    """Run hybrid retrieval with Reciprocal Rank Fusion scoring."""
    chunks = await retrieval_service.hybrid_retrieve(
        domain_id=domain_id,
        query=query,
        top_k=top_k,
        keyword_weight=keyword_weight,
        semantic_weight=semantic_weight,
        knowledge_base_ids=knowledge_base_ids,
    )
    return [
        {
            "document_id": c.document_id,
            "document_name": c.document_name,
            "chunk_index": c.chunk_index,
            "text": c.text,
            "score": c.score,
            "section_title": c.section_title,
            "page_number": c.page_number,
            "metadata": c.metadata,
        }
        for c in chunks
    ]
