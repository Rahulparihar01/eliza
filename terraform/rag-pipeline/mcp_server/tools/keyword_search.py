"""MCP tool: BM25 keyword search over indexed documents."""

from __future__ import annotations

from typing import Any


async def keyword_search(
    query: str,
    domain_id: str,
    top_k: int = 10,
    knowledge_base_ids: list[int] | None = None,
    filter_metadata: dict[str, Any] | None = None,
    *,
    vector_store,
) -> list[dict[str, Any]]:
    """Run BM25 keyword search against OpenSearch."""
    results = await vector_store.keyword_search(
        domain_id=domain_id,
        query=query,
        top_k=top_k,
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
