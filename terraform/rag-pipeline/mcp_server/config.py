"""Standalone MCP server configuration — no platform dependencies."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class MCPConfig:
    # OpenSearch
    opensearch_host: str = field(default_factory=lambda: os.environ.get("RAG_OPENSEARCH_HOST", ""))
    opensearch_region: str = field(default_factory=lambda: os.environ.get("RAG_OPENSEARCH_REGION", "us-east-1"))
    opensearch_index_prefix: str = field(default_factory=lambda: os.environ.get("RAG_OPENSEARCH_INDEX_PREFIX", "rag_domains"))

    # Bedrock embeddings
    bedrock_model: str = field(default_factory=lambda: os.environ.get("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"))
    bedrock_region: str = field(default_factory=lambda: os.environ.get("BEDROCK_EMBEDDING_REGION", "us-east-1"))

    # LLM for reranking / response generation
    llm_model: str = field(default_factory=lambda: os.environ.get("MCP_LLM_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0"))
    llm_region: str = field(default_factory=lambda: os.environ.get("MCP_LLM_REGION", "us-east-1"))

    # S3
    raw_bucket: str = field(default_factory=lambda: os.environ.get("S3_RAW_BUCKET", "eliza-raw-documents"))
    processed_bucket: str = field(default_factory=lambda: os.environ.get("S3_PROCESSED_BUCKET", "eliza-processed-documents"))

    # Domain / index
    domain_id: str = field(default_factory=lambda: os.environ.get("RAG_DOMAIN_ID", "default"))

    # Retrieval defaults
    default_top_k: int = 10
    default_min_score: float = 0.3
    keyword_weight: float = 0.3
    semantic_weight: float = 0.7
    rerank_keep: int = 5

    # Auth — if set, all non-health requests require this key
    api_key: str = field(default_factory=lambda: os.environ.get("MCP_API_KEY", ""))

    # Server
    host: str = field(default_factory=lambda: os.environ.get("MCP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.environ.get("MCP_SSE_PORT", "8888")))


def load_config() -> MCPConfig:
    return MCPConfig()
