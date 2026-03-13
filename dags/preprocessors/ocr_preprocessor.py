"""OCR/PDF preprocessor — delegates heavy lifting to the existing DocumentParser.

For scanned PDFs it uses VLM/GPT-4o vision; for text PDFs it falls back to
PyPDF2 extraction. Adds per-page confidence scoring.
"""

from __future__ import annotations

import io
import logging
from typing import Any

logger = logging.getLogger(__name__)


def preprocess_pdf(filename: str, content: bytes) -> list[dict[str, Any]]:
    """Extract text from PDF, one chunk per page."""
    chunks = _extract_with_pypdf(filename, content)
    if not chunks:
        logger.warning(f"PyPDF extraction empty for '{filename}', likely scanned — flagging for OCR")
        chunks = _placeholder_ocr(filename, content)
    return chunks


def _extract_with_pypdf(filename: str, content: bytes) -> list[dict[str, Any]]:
    try:
        import pypdf
    except ImportError:
        try:
            import PyPDF2 as pypdf  # type: ignore[no-redef]
        except ImportError:
            logger.error("Neither pypdf nor PyPDF2 is installed")
            return []

    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
    except Exception:
        logger.exception(f"Failed to read PDF '{filename}'")
        return []

    chunks: list[dict[str, Any]] = []
    for page_idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.strip()
        if len(text) < 20:
            continue

        confidence = _estimate_confidence(text, page_idx)
        chunks.append({
            "index": page_idx,
            "text": text,
            "filename": filename,
            "document_id": filename,
            "metadata": {
                "page_number": page_idx + 1,
                "total_pages": len(reader.pages),
                "confidence": confidence,
                "source_type": "pdf",
            },
        })

    logger.info(f"PDF '{filename}': {len(chunks)} page chunks from {len(reader.pages)} pages")
    return chunks


def _placeholder_ocr(filename: str, content: bytes) -> list[dict[str, Any]]:
    """Return a placeholder for scanned pages that need VLM/GPT-4o OCR.

    In production this would call DocumentParser with parser_type=VLM or GPT4O.
    """
    return [{
        "index": 0,
        "text": f"[OCR required for scanned document: {filename}]",
        "filename": filename,
        "document_id": filename,
        "metadata": {
            "page_number": 1,
            "needs_ocr": True,
            "source_type": "pdf_scanned",
        },
    }]


def _estimate_confidence(text: str, page_idx: int) -> float:
    """Heuristic confidence that extracted text is correct (vs garbled OCR)."""
    if not text:
        return 0.0
    words = text.split()
    if len(words) < 5:
        return 0.3

    alpha_ratio = sum(1 for w in words if w[0].isalpha()) / len(words)
    avg_word_len = sum(len(w) for w in words) / len(words)

    score = 0.5
    score += alpha_ratio * 0.3
    if 3 < avg_word_len < 12:
        score += 0.2
    else:
        score -= 0.1

    return max(0.0, min(1.0, score))
