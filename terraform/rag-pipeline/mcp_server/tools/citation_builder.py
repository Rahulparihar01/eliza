"""MCP tool: build structured citations from retrieved chunks."""

from __future__ import annotations

from typing import Any


def build_citations(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform retrieved chunks into numbered citation objects.

    Each citation includes: number, document_name, section, page, text snippet.
    """
    citations: list[dict[str, Any]] = []
    for i, chunk in enumerate(chunks, start=1):
        meta = chunk.get("metadata", {})
        citations.append({
            "number": i,
            "document_id": chunk.get("document_id", ""),
            "document_name": chunk.get("document_name", meta.get("filename", "")),
            "section_title": chunk.get("section_title", meta.get("section_title", "")),
            "page_number": chunk.get("page_number", meta.get("page_number")),
            "chunk_index": chunk.get("chunk_index", 0),
            "text_snippet": chunk.get("text", "")[:500],
            "score": chunk.get("score", 0.0),
        })
    return citations


def format_citations_block(citations: list[dict[str, Any]]) -> str:
    """Render citations as a markdown sources block for appending to answers."""
    if not citations:
        return ""
    lines = ["\n---\n**Sources:**"]
    for c in citations:
        parts = [f"[{c['number']}]"]
        if c.get("document_name"):
            parts.append(c["document_name"])
        if c.get("section_title"):
            parts.append(f"§ {c['section_title']}")
        if c.get("page_number"):
            parts.append(f"p. {c['page_number']}")
        lines.append(" — ".join(parts))
    return "\n".join(lines)
