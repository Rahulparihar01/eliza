"""MCP tool: metadata-filtered vector search."""

from __future__ import annotations

from typing import Any


async def metadata_filter_search(
    query: str,
    domain_id: str,
    filters: dict[str, Any],
    top_k: int = 10,
    min_score: float = 0.3,
    knowledge_base_ids: list[int] | None = None,
    *,
    embedding_service,
    vector_store,
) -> list[dict[str, Any]]:
    """Semantic search with metadata filters applied at the vector store level.

    ``filters`` maps metadata field names to match values, e.g.
    ``{"source_type": "presentation", "slide_number": 3}``.
    """
    query_embedding = await embedding_service.embed_query(query)
    results = await vector_store.search(
        domain_id=domain_id,
        query_embedding=query_embedding,
        top_k=top_k,
        min_score=min_score,
        filter_metadata=filters,
        knowledge_base_ids=knowledge_base_ids,
    )
    return [
        {
            "id": r.id,
            "document_id": r.document_id,
            "chunk_index": r.chunk_index,
            "text": r.text,
            "score": r.score,
            "metadata": r.metadata,
        }
        for r in results
    ]
