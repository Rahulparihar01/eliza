"""Standalone MCP server for RAG retrieval — no platform dependencies.

Connects directly to AWS OpenSearch + Bedrock. Exposes tools and agents
via FastMCP (SSE / Streamable HTTP) for ChatGPT Enterprise or any MCP client.

Run:
    python -m mcp_server.server          # stdio transport (default)
    MCP_TRANSPORT=sse python -m mcp_server.server   # SSE transport on port 8888
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from mcp_server.config import MCPConfig, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("eliza-rag-mcp")

# ---------------------------------------------------------------------------
# Lazy service singletons (initialised on first tool call)
# ---------------------------------------------------------------------------
_embedding_service = None
_vector_store = None
_retrieval_service = None
_config: MCPConfig | None = None


def _get_config() -> MCPConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def _get_embedding_service():
    global _embedding_service
    if _embedding_service is None:
        from eliza_rag.embeddings import EmbeddingProvider, EmbeddingService

        cfg = _get_config()
        _embedding_service = EmbeddingService(
            provider=EmbeddingProvider.BEDROCK,
            model=cfg.bedrock_model,
            aws_region=cfg.bedrock_region,
        )
    return _embedding_service


def _get_vector_store():
    global _vector_store
    if _vector_store is None:
        from eliza_rag.vector_store import VectorStore

        cfg = _get_config()
        _vector_store = VectorStore(
            opensearch_host=cfg.opensearch_host,
            opensearch_region=cfg.opensearch_region,
            index_prefix=cfg.opensearch_index_prefix,
            dimensions=_get_embedding_service().dimensions,
        )
    return _vector_store


def _get_retrieval_service():
    global _retrieval_service
    if _retrieval_service is None:
        from eliza_rag.retrieval import RetrievalService

        _retrieval_service = RetrievalService(
            embedding_service=_get_embedding_service(),
            vector_store=_get_vector_store(),
        )
    return _retrieval_service


# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("eliza-rag")


@mcp.tool()
async def vector_search(
    query: str,
    domain_id: str = "default",
    top_k: int = 10,
    min_score: float = 0.3,
) -> str:
    """Semantic vector search over indexed documents.

    Returns the top_k most similar chunks to the query.
    """
    from mcp_server.tools.vector_search import vector_search as _vs

    results = await _vs(
        query=query,
        domain_id=domain_id,
        top_k=top_k,
        min_score=min_score,
        embedding_service=_get_embedding_service(),
        vector_store=_get_vector_store(),
    )
    return json.dumps(results, indent=2)


@mcp.tool()
async def keyword_search(
    query: str,
    domain_id: str = "default",
    top_k: int = 10,
) -> str:
    """BM25 keyword search over indexed documents."""
    from mcp_server.tools.keyword_search import keyword_search as _ks

    results = await _ks(
        query=query,
        domain_id=domain_id,
        top_k=top_k,
        vector_store=_get_vector_store(),
    )
    return json.dumps(results, indent=2)


@mcp.tool()
async def hybrid_search(
    query: str,
    domain_id: str = "default",
    top_k: int = 10,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7,
) -> str:
    """Hybrid search combining semantic + keyword with RRF scoring."""
    from mcp_server.tools.hybrid_search import hybrid_search as _hs

    results = await _hs(
        query=query,
        domain_id=domain_id,
        top_k=top_k,
        keyword_weight=keyword_weight,
        semantic_weight=semantic_weight,
        retrieval_service=_get_retrieval_service(),
    )
    return json.dumps(results, indent=2)


@mcp.tool()
async def metadata_filter_search(
    query: str,
    filters: str,
    domain_id: str = "default",
    top_k: int = 10,
) -> str:
    """Semantic search with metadata filters (pass filters as JSON string)."""
    from mcp_server.tools.metadata_filter import metadata_filter_search as _mf

    filter_dict = json.loads(filters) if isinstance(filters, str) else filters
    results = await _mf(
        query=query,
        domain_id=domain_id,
        filters=filter_dict,
        top_k=top_k,
        embedding_service=_get_embedding_service(),
        vector_store=_get_vector_store(),
    )
    return json.dumps(results, indent=2)


@mcp.tool()
async def fetch_document(bucket: str, key: str) -> str:
    """Fetch a document from S3 by bucket and key."""
    from mcp_server.tools.doc_fetcher import fetch_document as _fd

    result = await _fd(bucket=bucket, key=key)
    return json.dumps(result, indent=2)


@mcp.tool()
async def ask(
    query: str,
    domain_id: str = "default",
    top_k: int = 10,
) -> str:
    """Full RAG pipeline: hybrid search → rerank → generate cited answer.

    This is the primary tool for answering questions over the knowledge base.
    """
    from mcp_server.agents.hybrid_retriever import hybrid_retrieve
    from mcp_server.agents.reranker import rerank
    from mcp_server.agents.response_formatter import generate_cited_response

    cfg = _get_config()

    chunks = await hybrid_retrieve(
        query=query,
        domain_id=domain_id,
        top_k=top_k,
        keyword_weight=cfg.keyword_weight,
        semantic_weight=cfg.semantic_weight,
        embedding_service=_get_embedding_service(),
        vector_store=_get_vector_store(),
    )

    reranked = await rerank(query=query, chunks=chunks, keep=cfg.rerank_keep)

    response = await generate_cited_response(query=query, chunks=reranked)
    return response["full_response"]


@mcp.tool()
async def plan_and_execute(
    query: str,
    domain_id: str = "default",
) -> str:
    """Decompose a complex query into sub-queries, execute each, then synthesize.

    Use for multi-faceted questions that benefit from targeted retrieval.
    """
    from mcp_server.agents.query_planner import plan_query
    from mcp_server.agents.reranker import rerank
    from mcp_server.agents.response_formatter import generate_cited_response

    plan = await plan_query(query=query)

    all_chunks: list[dict] = []
    for step in plan:
        tool_name = step.get("tool", "hybrid_search")
        params = step.get("params", {})
        params.setdefault("domain_id", domain_id)

        if tool_name == "hybrid_search":
            from mcp_server.agents.hybrid_retriever import hybrid_retrieve
            chunks = await hybrid_retrieve(
                **params,
                embedding_service=_get_embedding_service(),
                vector_store=_get_vector_store(),
            )
            all_chunks.extend(chunks)
        elif tool_name in ("vector_search", "metadata_filter_search"):
            from mcp_server.tools.vector_search import vector_search as _vs
            results = await _vs(
                **params,
                embedding_service=_get_embedding_service(),
                vector_store=_get_vector_store(),
            )
            all_chunks.extend(results)
        elif tool_name == "keyword_search":
            from mcp_server.tools.keyword_search import keyword_search as _ks
            results = await _ks(**params, vector_store=_get_vector_store())
            all_chunks.extend(results)

    seen = set()
    deduped = []
    for c in all_chunks:
        key = f"{c.get('document_id')}_{c.get('chunk_index')}"
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    reranked = await rerank(query=query, chunks=deduped, keep=8)
    response = await generate_cited_response(query=query, chunks=reranked)
    return response["full_response"]


# ---------------------------------------------------------------------------
# Health endpoint + API key auth middleware (SSE transport only)
# ---------------------------------------------------------------------------

def _create_sse_app():
    """Build a Starlette ASGI app with health check, optional API key auth,
    and the MCP SSE transport mounted underneath."""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    cfg = _get_config()
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )

    async def health(request: Request):
        return JSONResponse({"status": "healthy", "service": "eliza-rag-mcp"})

    class APIKeyAuthMiddleware:
        """Reject non-health requests that lack a valid API key."""

        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                path = scope.get("path", "")
                if path != "/health" and cfg.api_key:
                    headers = dict(scope.get("headers", []))
                    auth = headers.get(b"authorization", b"").decode()
                    api_key_hdr = headers.get(b"x-api-key", b"").decode()
                    valid = (
                        auth == f"Bearer {cfg.api_key}"
                        or api_key_hdr == cfg.api_key
                    )
                    if not valid:
                        resp = JSONResponse(
                            {"error": "unauthorized"}, status_code=401
                        )
                        await resp(scope, receive, send)
                        return
            await self.app(scope, receive, send)

    middlewares = [Middleware(APIKeyAuthMiddleware)]

    app = Starlette(
        routes=[
            Route("/health", health),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        middleware=middlewares,
    )
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        import uvicorn

        cfg = _get_config()
        app = _create_sse_app()
        logger.info("Starting MCP SSE server on %s:%s", cfg.host, cfg.port)
        uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")
    else:
        mcp.run()
