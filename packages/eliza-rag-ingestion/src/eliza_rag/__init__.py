"""Portable RAG ingestion/retrieval package."""

from .chat import RAGChatService, ChatMessage, ChatResponse
from .chunking import ChunkingService, ChunkingStrategy, TextChunk
from .document_parser import DocumentParser, ParserType, ParsedDocument, ParsedChunk
from .embeddings import EmbeddingProvider, EmbeddingService
from .metadata_enrichment import MetadataEnrichmentService, DocumentMetadata, ChunkMetadata
from .retrieval import RetrievalService, RetrievedChunk
from .vector_store import VectorStore, VectorDocument, VectorSearchResult

__all__ = [
    "ChunkMetadata",
    "ChunkingService",
    "ChunkingStrategy",
    "ChatMessage",
    "ChatResponse",
    "DocumentMetadata",
    "DocumentParser",
    "EmbeddingProvider",
    "EmbeddingService",
    "MetadataEnrichmentService",
    "ParsedChunk",
    "ParsedDocument",
    "ParserType",
    "RAGChatService",
    "RetrievedChunk",
    "RetrievalService",
    "TextChunk",
    "VectorDocument",
    "VectorSearchResult",
    "VectorStore",
]
