"""Eliza Platform Workspace RAG MCP Server.

Exposes workspace knowledge bases as MCP tools for ChatGPT Enterprise
or any MCP client. Authenticates to the platform via API key.

Usage:
    ELIZA_API_BASE=http://localhost:5001 ELIZA_API_KEY=... python eliza_workspace_rag_server.py
"""

from __future__ import annotations

import json
import logging
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("eliza-workspace-rag")

mcp = FastMCP("eliza-workspace-rag")

ELIZA_API_BASE = os.environ.get("ELIZA_API_BASE", "http://localhost:5001")
ELIZA_API_KEY = os.environ.get("ELIZA_API_KEY", "")
DEFAULT_WORKSPACE_ID = os.environ.get("ELIZA_WORKSPACE_ID", "")


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if ELIZA_API_KEY:
        h["Authorization"] = f"Bearer {ELIZA_API_KEY}"
    return h


async def _api_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(f"{ELIZA_API_BASE}{path}", headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def _api_post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{ELIZA_API_BASE}{path}", headers=_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def list_workspaces() -> str:
    """List all accessible workspaces and their knowledge bases."""
    data = await _api_get("/api/v1/workspaces")
    workspaces = data if isinstance(data, list) else data.get("workspaces", data.get("items", []))
    result = []
    for ws in workspaces:
        result.append({
            "id": ws.get("id"),
            "name": ws.get("name"),
            "description": ws.get("description", ""),
            "knowledge_base_count": len(ws.get("knowledge_bases", [])),
        })
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_knowledge_bases(workspace_id: str = "") -> str:
    """List knowledge bases in a workspace."""
    ws_id = workspace_id or DEFAULT_WORKSPACE_ID
    if not ws_id:
        return json.dumps({"error": "workspace_id required (or set ELIZA_WORKSPACE_ID)"})
    data = await _api_get(f"/api/v1/workspaces/{ws_id}/knowledge-bases")
    kbs = data if isinstance(data, list) else data.get("knowledge_bases", data.get("items", []))
    result = []
    for kb in kbs:
        result.append({
            "id": kb.get("id"),
            "name": kb.get("name"),
            "description": kb.get("description", ""),
            "document_count": kb.get("document_count", 0),
        })
    return json.dumps(result, indent=2)


@mcp.tool()
async def search(
    query: str,
    workspace_id: str = "",
    knowledge_base_ids: str = "",
    top_k: int = 10,
    source_filter: str = "all",
) -> str:
    """Search across workspace knowledge bases using hybrid retrieval.

    Pass knowledge_base_ids as comma-separated IDs to restrict scope.
    """
    ws_id = workspace_id or DEFAULT_WORKSPACE_ID
    if not ws_id:
        return json.dumps({"error": "workspace_id required"})

    kb_ids = [int(x.strip()) for x in knowledge_base_ids.split(",") if x.strip()] if knowledge_base_ids else None

    body: dict = {
        "question": query,
        "top_k": top_k,
        "source_filter": source_filter,
    }
    if kb_ids:
        body["knowledge_base_ids"] = kb_ids

    data = await _api_post(f"/api/v1/workspaces/{ws_id}/ragflow/retrieve", body)
    return json.dumps(data, indent=2)


@mcp.tool()
async def ask(
    question: str,
    workspace_id: str = "",
    knowledge_base_ids: str = "",
    top_k: int = 10,
) -> str:
    """Ask a question and get a cited answer from workspace knowledge bases.

    Returns an answer with inline [1], [2] citations and a sources block.
    """
    ws_id = workspace_id or DEFAULT_WORKSPACE_ID
    if not ws_id:
        return json.dumps({"error": "workspace_id required"})

    kb_ids = [int(x.strip()) for x in knowledge_base_ids.split(",") if x.strip()] if knowledge_base_ids else None

    body: dict = {
        "question": question,
        "top_k": top_k,
    }
    if kb_ids:
        body["knowledge_base_ids"] = kb_ids

    data = await _api_post(f"/api/v1/workspaces/{ws_id}/ragflow/chat", body)

    answer = data.get("answer", data.get("result_data", ""))
    citations = data.get("citations", data.get("result_metadata", {}).get("citations", []))

    return json.dumps({
        "answer": answer,
        "citations": citations,
    }, indent=2)


@mcp.tool()
async def get_document(
    workspace_id: str,
    knowledge_base_id: int,
    document_id: int,
) -> str:
    """Fetch metadata for a specific document in a knowledge base."""
    data = await _api_get(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases/{knowledge_base_id}/documents/{document_id}"
    )
    return json.dumps(data, indent=2)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run()
