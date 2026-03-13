"""Hybrid retriever agent — orchestrates vector + keyword search with RRF."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def hybrid_retrieve(
    query: str,
    domain_id: str,
    top_k: int = 10,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7,
    knowledge_base_ids: list[int] | None = None,
    *,
    embedding_service,
    vector_store,
) -> list[dict[str, Any]]:
    """Run both semantic and keyword search, fuse with RRF, return ranked results."""

    RRF_K = 60

    query_embedding = await embedding_service.embed_query(query)
    semantic_results = await vector_store.search(
        domain_id=domain_id,
        query_embedding=query_embedding,
        top_k=top_k * 2,
        min_score=0.1,
        knowledge_base_ids=knowledge_base_ids,
    )
    keyword_results = await vector_store.keyword_search(
        domain_id=domain_id,
        query=query,
        top_k=top_k * 2,
        knowledge_base_ids=knowledge_base_ids,
    )

    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}

    for rank, r in enumerate(semantic_results):
        key = f"{r.document_id}_{r.chunk_index}"
        scores[key] = scores.get(key, 0) + semantic_weight * (1.0 / (RRF_K + rank + 1))
        docs[key] = {
            "document_id": r.document_id,
            "chunk_index": r.chunk_index,
            "text": r.text,
            "metadata": r.metadata,
        }

    for rank, r in enumerate(keyword_results):
        key = f"{r.document_id}_{r.chunk_index}"
        scores[key] = scores.get(key, 0) + keyword_weight * (1.0 / (RRF_K + rank + 1))
        if key not in docs:
            docs[key] = {
                "document_id": r.document_id,
                "chunk_index": r.chunk_index,
                "text": r.text,
                "metadata": r.metadata,
            }

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    results = []
    for key, score in ranked:
        doc = docs[key]
        doc["score"] = score
        results.append(doc)

    logger.info(f"Hybrid retrieval: {len(semantic_results)} semantic + {len(keyword_results)} keyword → {len(results)} fused")
    return results
