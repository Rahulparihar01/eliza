"""MCP tool: semantic vector search over indexed documents."""

from __future__ import annotations

from typing import Any


async def vector_search(
    query: str,
    domain_id: str,
    top_k: int = 10,
    min_score: float = 0.3,
    knowledge_base_ids: list[int] | None = None,
    filter_metadata: dict[str, Any] | None = None,
    *,
    embedding_service,
    vector_store,
) -> list[dict[str, Any]]:
    """Run semantic search: embed the query then kNN against OpenSearch."""
    query_embedding = await embedding_service.embed_query(query)
    results = await vector_store.search(
        domain_id=domain_id,
        query_embedding=query_embedding,
        top_k=top_k,
        min_score=min_score,
        filter_metadata=filter_metadata,
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
