"""Response formatter agent — generates answers with inline citations."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from mcp_server.tools.citation_builder import build_citations, format_citations_block

logger = logging.getLogger(__name__)


async def generate_cited_response(
    query: str,
    chunks: list[dict[str, Any]],
    *,
    llm_client=None,
) -> dict[str, Any]:
    """Generate an answer referencing chunks with inline [1], [2] citations.

    Returns ``{"answer": str, "citations": list, "sources_block": str}``.
    """
    if not chunks:
        return {"answer": "No relevant documents found.", "citations": [], "sources_block": ""}

    citations = build_citations(chunks)

    context_block = "\n\n".join(
        f"[{c['number']}] {c['text_snippet']}" for c in citations
    )

    prompt = (
        "You are a helpful research assistant. Answer the user's question using ONLY "
        "the provided sources. Cite sources inline using [1], [2], etc.\n\n"
        f"Sources:\n{context_block}\n\n"
        f"Question: {query}\n\n"
        "Answer (with inline citations):"
    )

    try:
        if llm_client:
            raw_answer = await llm_client(prompt)
        else:
            raw_answer = _invoke_bedrock_llm(prompt)
    except Exception:
        logger.exception("LLM generation failed")
        raw_answer = "Unable to generate a response at this time."

    used_numbers = set(int(m) for m in re.findall(r"\[(\d+)\]", raw_answer))
    used_citations = [c for c in citations if c["number"] in used_numbers]

    if used_citations:
        renumber = {}
        for new_num, c in enumerate(used_citations, start=1):
            renumber[c["number"]] = new_num
            c["number"] = new_num
        for old, new in renumber.items():
            raw_answer = raw_answer.replace(f"[{old}]", f"[__{new}__]")
        for new in renumber.values():
            raw_answer = raw_answer.replace(f"[__{new}__]", f"[{new}]")

    sources_block = format_citations_block(used_citations)

    return {
        "answer": raw_answer,
        "citations": used_citations,
        "sources_block": sources_block,
        "full_response": raw_answer + sources_block,
    }


def _invoke_bedrock_llm(prompt: str) -> str:
    import boto3

    region = os.environ.get("MCP_LLM_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    model_id = os.environ.get("MCP_LLM_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0")
    client = boto3.client("bedrock-runtime", region_name=region)

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    })
    resp = client.invoke_model(modelId=model_id, body=body, contentType="application/json", accept="application/json")
    result = json.loads(resp["body"].read())
    return result["content"][0]["text"]
