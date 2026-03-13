"""NLP cleaning preprocessor for unstructured text documents.

Handles .txt, .md, .html, .docx — cleans boilerplate, detects sections,
and produces quality-scored chunks ready for embedding.
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

BOILERPLATE_PATTERNS = [
    re.compile(r"^page\s+\d+\s*(of\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^confidential\s*$", re.IGNORECASE),
    re.compile(r"^\s*©.*$"),
    re.compile(r"^(header|footer)\s*:?\s*$", re.IGNORECASE),
    re.compile(r"^\s*-{3,}\s*$"),
    re.compile(r"^\s*_{3,}\s*$"),
]

HEADING_PATTERNS = [
    re.compile(r"^#{1,6}\s+(.+)$"),                         # Markdown
    re.compile(r"^([A-Z][A-Z0-9 ]{2,60})$"),                # ALL CAPS heading
    re.compile(r"^(\d+\.[\d.]*)\s+(.+)$"),                  # Numbered heading
    re.compile(r"^(Section|Chapter|Part)\s+[\dIVXLC]+", re.IGNORECASE),
]


def preprocess_unstructured(filename: str, content: bytes) -> list[dict[str, Any]]:
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext in ("html", "htm"):
        text = _extract_html(content)
    elif ext == "docx":
        text = _extract_docx(content)
    else:
        text = content.decode("utf-8", errors="replace")

    text = _clean_text(text)
    sections = _detect_sections(text)
    chunks = _build_chunks(filename, sections)
    logger.info(f"Unstructured '{filename}': {len(chunks)} chunks from {len(sections)} sections")
    return chunks


def _extract_html(content: bytes) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def _extract_docx(content: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(content))
    parts: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            style = para.style.name if para.style else ""
            if "Heading" in style:
                parts.append(f"\n## {text}\n")
            else:
                parts.append(text)
    return "\n".join(parts)


def _clean_text(text: str) -> str:
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if any(p.match(stripped) for p in BOILERPLATE_PATTERNS):
            continue
        if not stripped:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned).strip()


def _detect_sections(text: str) -> list[dict[str, Any]]:
    """Split text into sections based on heading patterns."""
    lines = text.split("\n")
    sections: list[dict[str, Any]] = []
    current_title = "Introduction"
    current_lines: list[str] = []

    for line in lines:
        is_heading = False
        for pattern in HEADING_PATTERNS:
            if pattern.match(line.strip()):
                is_heading = True
                break

        if is_heading and current_lines:
            sections.append({
                "title": current_title,
                "text": "\n".join(current_lines).strip(),
            })
            current_title = line.strip().lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({
            "title": current_title,
            "text": "\n".join(current_lines).strip(),
        })

    return [s for s in sections if len(s["text"]) > 20]


def _quality_score(text: str) -> float:
    """Heuristic quality score 0..1 for embedding priority."""
    score = 0.5
    words = text.split()
    word_count = len(words)

    if word_count < 10:
        score -= 0.3
    elif word_count > 50:
        score += 0.1

    unique_ratio = len(set(w.lower() for w in words)) / max(word_count, 1)
    score += unique_ratio * 0.2

    if any(c in text for c in ("?", "!", ".", ":")):
        score += 0.1

    return max(0.0, min(1.0, score))


CHUNK_TARGET_SIZE = 1500  # characters


def _build_chunks(filename: str, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    idx = 0

    for section in sections:
        text = section["text"]
        title = section["title"]

        if len(text) <= CHUNK_TARGET_SIZE:
            chunks.append({
                "index": idx,
                "text": text,
                "filename": filename,
                "document_id": filename,
                "metadata": {
                    "section_title": title,
                    "quality_score": _quality_score(text),
                    "char_count": len(text),
                    "source_type": "unstructured",
                },
            })
            idx += 1
        else:
            paragraphs = text.split("\n\n")
            buffer = ""
            for para in paragraphs:
                if len(buffer) + len(para) > CHUNK_TARGET_SIZE and buffer:
                    chunks.append({
                        "index": idx,
                        "text": buffer.strip(),
                        "filename": filename,
                        "document_id": filename,
                        "metadata": {
                            "section_title": title,
                            "quality_score": _quality_score(buffer),
                            "char_count": len(buffer),
                            "source_type": "unstructured",
                        },
                    })
                    idx += 1
                    buffer = ""
                buffer += para + "\n\n"
            if buffer.strip():
                chunks.append({
                    "index": idx,
                    "text": buffer.strip(),
                    "filename": filename,
                    "document_id": filename,
                    "metadata": {
                        "section_title": title,
                        "quality_score": _quality_score(buffer),
                        "char_count": len(buffer),
                        "source_type": "unstructured",
                    },
                })
                idx += 1

    return chunks
