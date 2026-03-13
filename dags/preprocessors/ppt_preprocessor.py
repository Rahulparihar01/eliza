"""Slide-aware PowerPoint preprocessor.

Produces one chunk per slide containing:
  - Slide body text (all shapes)
  - Speaker notes
  - Table content (pipe-delimited)
  - Image alt-text
"""

from __future__ import annotations

import io
import logging
from typing import Any

logger = logging.getLogger(__name__)


def preprocess_ppt(filename: str, content: bytes) -> list[dict[str, Any]]:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation(io.BytesIO(content))
    chunks: list[dict[str, Any]] = []

    for slide_idx, slide in enumerate(prs.slides, start=1):
        parts: list[str] = []
        tables: list[str] = []
        has_table = False
        has_image = False
        slide_title = ""

        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    parts.append(text)
                if shape.shape_id == slide.shapes.title and shape.has_text_frame:
                    slide_title = shape.text_frame.text.strip()

            if shape.has_table:
                has_table = True
                tbl = shape.table
                rows = []
                for row in tbl.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    rows.append(" | ".join(cells))
                tables.append("\n".join(rows))

            if shape.shape_type is not None and shape.shape_type == 13:  # Picture
                has_image = True
                alt = getattr(shape, "name", "") or ""
                if alt:
                    parts.append(f"[Image: {alt}]")

        if not slide_title and parts:
            slide_title = parts[0][:80]

        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"Speaker Notes: {notes}")

        if tables:
            parts.append("Table:\n" + "\n\n".join(tables))

        full_text = "\n".join(parts).strip()
        if not full_text:
            continue

        chunks.append({
            "index": slide_idx - 1,
            "text": full_text,
            "filename": filename,
            "document_id": filename,
            "metadata": {
                "slide_number": slide_idx,
                "slide_title": slide_title,
                "has_table": has_table,
                "has_image": has_image,
                "source_type": "presentation",
            },
        })

    logger.info(f"PPT '{filename}': {len(chunks)} slide chunks from {len(prs.slides)} slides")
    return chunks
