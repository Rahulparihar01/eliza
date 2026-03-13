"""LLM-based reranker agent — scores and filters retrieved chunks by relevance."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


async def rerank(
    query: str,
    chunks: list[dict[str, Any]],
    keep: int = 5,
    *,
    llm_client=None,
) -> list[dict[str, Any]]:
    """Use an LLM to score each chunk's relevance to the query, keep top *keep*.

    If no *llm_client* is provided, falls back to Bedrock Claude.
    """
    if not chunks:
        return []

    if len(chunks) <= keep:
        return chunks

    context_block = "\n\n".join(
        f"[Chunk {i}] (doc: {c.get('document_id', '?')}, idx: {c.get('chunk_index', '?')})\n{c['text'][:600]}"
        for i, c in enumerate(chunks)
    )

    prompt = (
        f"You are a relevance scoring assistant. Given a query and {len(chunks)} text chunks, "
        f"score each chunk 0-10 for relevance to the query.\n\n"
        f"Query: {query}\n\n"
        f"Chunks:\n{context_block}\n\n"
        f"Return ONLY a JSON array of objects with keys 'index' (int) and 'score' (int 0-10). "
        f"No other text."
    )

    try:
        if llm_client:
            scores_raw = await llm_client(prompt)
        else:
            scores_raw = _invoke_bedrock_llm(prompt)

        scores = json.loads(scores_raw)
        scored = []
        for entry in scores:
            idx = entry.get("index", 0)
            if 0 <= idx < len(chunks):
                chunk = dict(chunks[idx])
                chunk["rerank_score"] = entry.get("score", 0)
                scored.append(chunk)

        scored.sort(key=lambda c: c.get("rerank_score", 0), reverse=True)
        return scored[:keep]

    except Exception:
        logger.exception("Reranking failed, returning top chunks by original score")
        return sorted(chunks, key=lambda c: c.get("score", 0), reverse=True)[:keep]


def _invoke_bedrock_llm(prompt: str) -> str:
    import boto3

    region = os.environ.get("MCP_LLM_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    model_id = os.environ.get("MCP_LLM_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0")
    client = boto3.client("bedrock-runtime", region_name=region)

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    })
    resp = client.invoke_model(modelId=model_id, body=body, contentType="application/json", accept="application/json")
    result = json.loads(resp["body"].read())
    return result["content"][0]["text"]
