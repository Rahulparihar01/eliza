"""Document classifier — route files to type-specific preprocessors."""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocCategory(str, Enum):
    UNSTRUCTURED = "unstructured"
    STRUCTURED = "structured"
    PRESENTATION = "presentation"
    PDF = "pdf"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    category: DocCategory
    mime_type: str
    extension: str
    metadata: dict[str, Any] = field(default_factory=dict)


EXTENSION_MAP: dict[str, DocCategory] = {
    ".txt": DocCategory.UNSTRUCTURED,
    ".md": DocCategory.UNSTRUCTURED,
    ".html": DocCategory.UNSTRUCTURED,
    ".htm": DocCategory.UNSTRUCTURED,
    ".docx": DocCategory.UNSTRUCTURED,
    ".doc": DocCategory.UNSTRUCTURED,
    ".rtf": DocCategory.UNSTRUCTURED,
    ".xlsx": DocCategory.STRUCTURED,
    ".xls": DocCategory.STRUCTURED,
    ".csv": DocCategory.STRUCTURED,
    ".tsv": DocCategory.STRUCTURED,
    ".pptx": DocCategory.PRESENTATION,
    ".ppt": DocCategory.PRESENTATION,
    ".pdf": DocCategory.PDF,
}

MIME_MAP: dict[str, DocCategory] = {
    "text/plain": DocCategory.UNSTRUCTURED,
    "text/html": DocCategory.UNSTRUCTURED,
    "text/markdown": DocCategory.UNSTRUCTURED,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocCategory.UNSTRUCTURED,
    "application/msword": DocCategory.UNSTRUCTURED,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": DocCategory.STRUCTURED,
    "application/vnd.ms-excel": DocCategory.STRUCTURED,
    "text/csv": DocCategory.STRUCTURED,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": DocCategory.PRESENTATION,
    "application/vnd.ms-powerpoint": DocCategory.PRESENTATION,
    "application/pdf": DocCategory.PDF,
}


def classify(filename: str, content_type: str | None = None, head_bytes: bytes | None = None) -> ClassificationResult:
    """Classify a document into a processing category.

    Priority: extension > MIME > content sampling.
    """
    ext = os.path.splitext(filename)[1].lower()
    mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    category = EXTENSION_MAP.get(ext)
    if category is None:
        category = MIME_MAP.get(mime)

    if category is None and head_bytes:
        if head_bytes[:4] == b"%PDF":
            category = DocCategory.PDF
        elif head_bytes[:2] == b"PK":
            # ZIP-based (could be docx, xlsx, pptx)
            if ext in (".xlsx", ".xls"):
                category = DocCategory.STRUCTURED
            elif ext in (".pptx", ".ppt"):
                category = DocCategory.PRESENTATION
            else:
                category = DocCategory.UNSTRUCTURED
        else:
            try:
                head_bytes.decode("utf-8")
                category = DocCategory.UNSTRUCTURED
            except UnicodeDecodeError:
                category = DocCategory.UNKNOWN

    if category is None:
        category = DocCategory.UNKNOWN

    return ClassificationResult(
        category=category,
        mime_type=mime,
        extension=ext,
        metadata={"filename": filename},
    )
