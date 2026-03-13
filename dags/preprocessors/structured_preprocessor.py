"""Schema-aware preprocessor for Excel and CSV files.

Produces one chunk per sheet (Excel) or per logical table (CSV).
Preserves column headers in every chunk so retrieval always has context.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_ROWS_PER_CHUNK = 50


def preprocess_structured(filename: str, content: bytes) -> list[dict[str, Any]]:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in ("xlsx", "xls"):
        return _process_excel(filename, content)
    elif ext in ("csv", "tsv"):
        return _process_csv(filename, content, delimiter="\t" if ext == "tsv" else ",")
    else:
        logger.warning(f"Unsupported structured format: {ext}")
        return []


def _process_excel(filename: str, content: bytes) -> list[dict[str, Any]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    chunks: list[dict[str, Any]] = []
    chunk_idx = 0

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        headers = [str(c) if c is not None else "" for c in rows[0]]
        data_rows = rows[1:]

        for batch_start in range(0, max(len(data_rows), 1), MAX_ROWS_PER_CHUNK):
            batch = data_rows[batch_start : batch_start + MAX_ROWS_PER_CHUNK]
            lines = [" | ".join(headers)]
            lines.append(" | ".join(["---"] * len(headers)))
            for row in batch:
                cells = [str(c) if c is not None else "" for c in row]
                while len(cells) < len(headers):
                    cells.append("")
                lines.append(" | ".join(cells[: len(headers)]))

            text = "\n".join(lines)
            col_types = _infer_column_types(headers, batch)

            chunks.append({
                "index": chunk_idx,
                "text": text,
                "filename": filename,
                "document_id": filename,
                "metadata": {
                    "sheet_name": sheet_name,
                    "headers": headers,
                    "column_types": col_types,
                    "row_range": f"{batch_start + 2}-{batch_start + 1 + len(batch)}",
                    "total_rows": len(data_rows),
                    "source_type": "structured",
                },
            })
            chunk_idx += 1

    wb.close()
    logger.info(f"Excel '{filename}': {len(chunks)} chunks from {len(wb.sheetnames)} sheets")
    return chunks


def _process_csv(filename: str, content: bytes, delimiter: str = ",") -> list[dict[str, Any]]:
    text_content = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)
    all_rows = list(reader)
    if not all_rows:
        return []

    headers = all_rows[0]
    data_rows = all_rows[1:]
    chunks: list[dict[str, Any]] = []
    chunk_idx = 0

    for batch_start in range(0, max(len(data_rows), 1), MAX_ROWS_PER_CHUNK):
        batch = data_rows[batch_start : batch_start + MAX_ROWS_PER_CHUNK]
        lines = [" | ".join(headers)]
        lines.append(" | ".join(["---"] * len(headers)))
        for row in batch:
            while len(row) < len(headers):
                row.append("")
            lines.append(" | ".join(row[: len(headers)]))

        text = "\n".join(lines)
        chunks.append({
            "index": chunk_idx,
            "text": text,
            "filename": filename,
            "document_id": filename,
            "metadata": {
                "headers": headers,
                "row_range": f"{batch_start + 2}-{batch_start + 1 + len(batch)}",
                "total_rows": len(data_rows),
                "source_type": "structured",
            },
        })
        chunk_idx += 1

    logger.info(f"CSV '{filename}': {len(chunks)} chunks from {len(data_rows)} data rows")
    return chunks


def _infer_column_types(headers: list[str], rows: list[tuple]) -> dict[str, str]:
    """Best-effort type inference for each column."""
    types: dict[str, str] = {}
    for col_idx, header in enumerate(headers):
        values = [r[col_idx] for r in rows if col_idx < len(r) and r[col_idx] is not None]
        if not values:
            types[header] = "empty"
            continue
        sample = values[:20]
        if all(isinstance(v, (int, float)) for v in sample):
            types[header] = "numeric"
        elif all(isinstance(v, str) and len(v) > 50 for v in sample):
            types[header] = "text"
        else:
            types[header] = "string"
    return types
