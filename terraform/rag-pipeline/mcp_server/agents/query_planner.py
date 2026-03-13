"""Query planner agent — decomposes complex queries into sub-queries.

Adapted from the platform's Planner → Executor → Evaluator → Synthesizer pattern
in src/flows/retrieval_flow.py for standalone MCP use.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


async def plan_query(
    query: str,
    available_knowledge_bases: list[dict[str, Any]] | None = None,
    *,
    llm_client=None,
) -> list[dict[str, Any]]:
    """Decompose a user query into planned retrieval steps.

    Returns a list of planned calls, e.g.:
    [
        {"tool": "hybrid_search", "params": {"query": "sub-query 1", "domain_id": "...", "top_k": 5}},
        {"tool": "keyword_search", "params": {"query": "sub-query 2", "domain_id": "..."}},
    ]
    """
    kb_context = ""
    if available_knowledge_bases:
        kb_lines = [f"- {kb.get('name', kb.get('id', '?'))}: {kb.get('description', 'N/A')}" for kb in available_knowledge_bases]
        kb_context = f"\n\nAvailable knowledge bases:\n" + "\n".join(kb_lines)

    prompt = (
        "You are a query planner for a RAG system. Given a user question, decompose it into "
        "one or more retrieval steps.\n\n"
        "Available tools:\n"
        "- hybrid_search(query, domain_id, top_k): Semantic + keyword search with RRF fusion\n"
        "- vector_search(query, domain_id, top_k, min_score): Pure semantic search\n"
        "- keyword_search(query, domain_id, top_k): BM25 keyword search\n"
        "- metadata_filter_search(query, domain_id, filters, top_k): Filtered semantic search\n"
        "- fetch_document(bucket, key): Get full document from S3\n"
        f"{kb_context}\n\n"
        f"User question: {query}\n\n"
        "Return ONLY a JSON array of objects with keys 'tool' (str) and 'params' (dict). "
        "For simple factual questions, a single hybrid_search is sufficient. "
        "For complex multi-faceted questions, decompose into targeted sub-queries."
    )

    try:
        if llm_client:
            raw = await llm_client(prompt)
        else:
            raw = _invoke_bedrock_llm(prompt)

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        plan = json.loads(raw)

        if not isinstance(plan, list):
            plan = [plan]

        logger.info(f"Query plan: {len(plan)} steps for '{query[:80]}'")
        return plan

    except Exception:
        logger.exception("Query planning failed, falling back to single hybrid search")
        return [{
            "tool": "hybrid_search",
            "params": {"query": query, "domain_id": "default", "top_k": 10},
        }]


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
