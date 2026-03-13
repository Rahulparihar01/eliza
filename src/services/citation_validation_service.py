"""
Citation Validation Service

Validates that a cited PDF page contains the cited chunk text using GPT-4o vision.
Renders PDF pages as images and sends them to the VLM for validation.

Supports both FASB on-disk PDFs and native RAG documents stored in object storage.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from PIL import Image
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__, component="citation_validation.service")


@dataclass
class ParsedCitation:
    doc_id: str
    page_start: Optional[int]
    page_end: Optional[int]
    chunk_id: Optional[str]
    section: Optional[str]


class CitationValidationService:
    """Validate citations by rendering PDF pages and using GPT-4o vision."""

    def __init__(self, db: Optional[Session] = None, async_client: Optional[AsyncOpenAI] = None):
        self.settings = get_settings()
        self._async_client = async_client
        self.db = db

    @property
    def async_client(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._async_client

    def parse_citation(self, citation: str) -> ParsedCitation:
        """Parse citation string into structured components."""
        doc_match = re.search(r"doc:(\d+)", citation)
        pages_match = re.search(r"pages:([^\s]+)", citation)
        chunk_match = re.search(r"chunk:([^\s]+)", citation)
        section_match = re.search(r"section:(.+)$", citation)

        page_start = None
        page_end = None
        if pages_match:
            page_text = pages_match.group(1)
            if "-" in page_text:
                start_str, end_str = page_text.split("-", 1)
                page_start = int(start_str) if start_str.isdigit() else None
                page_end = int(end_str) if end_str.isdigit() else None
            elif page_text.isdigit():
                page_start = int(page_text)
                page_end = int(page_text)

        return ParsedCitation(
            doc_id=doc_match.group(1) if doc_match else "",
            page_start=page_start,
            page_end=page_end,
            chunk_id=chunk_match.group(1) if chunk_match else None,
            section=section_match.group(1) if section_match else None,
        )

    def _get_pdf_path(self, doc_id: str) -> Path:
        """Get the path to a PDF document."""
        return Path(self.settings.fasb_docs_path) / f"{doc_id}.pdf"

    async def _fetch_pdf_from_storage(self, doc_id: str) -> Optional[bytes]:
        """Fetch PDF bytes from object storage for a native RAG document."""
        if not self.db:
            return None
        try:
            from src.models.ragflow_domain import RAGFlowDocument
            from src.services.object_storage_service import ObjectStorageService

            doc = self.db.query(RAGFlowDocument).filter(
                RAGFlowDocument.id == int(doc_id),
            ).first()
            if not doc:
                logger.debug("doc_not_in_db", doc_id=doc_id)
                return None

            metadata = doc.document_metadata if isinstance(doc.document_metadata, dict) else {}
            storage = metadata.get("storage") or {}
            bucket = storage.get("bucket")
            object_key = storage.get("object_key")
            if not bucket or not object_key:
                logger.debug("doc_no_storage_info", doc_id=doc_id)
                return None

            obj_service = ObjectStorageService(self.db)
            result = await obj_service.get_object_bytes(
                customer_id=doc.customer_id,
                bucket=bucket,
                object_key=object_key,
            )
            return result.get("content")
        except Exception as exc:
            logger.warning("storage_fetch_failed", doc_id=doc_id, error=str(exc))
            return None

    def _render_page_from_bytes(self, pdf_bytes: bytes, page_number: int, scale: float = 2.0) -> Optional[Image.Image]:
        """Render a page from in-memory PDF bytes."""
        try:
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(pdf_bytes)
            page_index = page_number - 1
            if page_index < 0 or page_index >= len(pdf):
                pdf.close()
                return None
            page = pdf[page_index]
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            pdf.close()
            return pil_image
        except Exception as exc:
            logger.warning("pdf_bytes_render_failed", error=str(exc))
            return None

    def _render_pdf_page(self, doc_id: str, page_number: int, scale: float = 2.0) -> Optional[Image.Image]:
        """Render a PDF page as a PIL Image using pypdfium2 (FASB on-disk only)."""
        pdf_path = self._get_pdf_path(doc_id)
        if not pdf_path.exists():
            logger.debug("pdf_not_found", doc_id=doc_id, path=str(pdf_path))
            return None

        try:
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(str(pdf_path))
            page_index = page_number - 1

            if page_index < 0 or page_index >= len(pdf):
                logger.debug(
                    "page_out_of_range",
                    doc_id=doc_id,
                    page_number=page_number,
                    total_pages=len(pdf),
                )
                pdf.close()
                return None

            page = pdf[page_index]
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            pdf.close()

            logger.debug(
                "pdf_page_rendered",
                doc_id=doc_id,
                page_number=page_number,
                image_size=pil_image.size,
            )
            return pil_image

        except Exception as exc:
            logger.warning(
                "pdf_render_failed",
                doc_id=doc_id,
                page_number=page_number,
                error=str(exc),
            )
            return None

    @staticmethod
    def _image_to_data_url(image: Image.Image) -> str:
        """Convert PIL Image to base64 data URL for OpenAI API."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    async def _vlm_validate(
        self,
        chunk_text: str,
        page_image: Image.Image,
        page_number: int,
        question: Optional[str] = None,
        answer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Use GPT-4o vision to validate if the chunk text appears on the page."""
        if not self.settings.openai_api_key:
            return {
                "verdict": "error",
                "confidence": 0,
                "evidence": None,
                "reason": "OpenAI API key not configured",
            }

        # Build the prompt
        prompt_parts = [
            "You are validating a citation for a RAG (Retrieval-Augmented Generation) system.",
            "Your task is to verify if the cited text chunk actually appears on or is supported by the PDF page shown.",
            "",
            f"**Cited Page Number:** {page_number}",
            f"**Cited Chunk Text:**",
            f"```",
            f"{chunk_text[:2000]}",  # Limit chunk text length
            f"```",
        ]

        if question:
            prompt_parts.extend(["", f"**Question being answered:** {question[:500]}"])
        if answer:
            prompt_parts.extend(["", f"**Answer given:** {answer[:500]}"])

        prompt_parts.extend([
            "",
            "**Instructions:**",
            "1. Examine the PDF page image carefully",
            "2. Determine if the cited chunk text appears on this page (exact or near-exact match)",
            "3. If the text appears, the citation is valid (pass)",
            "4. If the text does NOT appear on this page, the citation is invalid (fail)",
            "5. If you cannot determine with confidence, return unsure",
            "",
            "**Return ONLY valid JSON in this exact format:**",
            '{"verdict": "pass|fail|unsure", "confidence": 0-100, "evidence": "brief quote from page if found", "reason": "short explanation"}',
        ])

        prompt = "\n".join(prompt_parts)
        image_payload = self._image_to_data_url(page_image)

        try:
            response = await self.async_client.chat.completions.create(
                model=self.settings.citation_eval_vlm_model,  # gpt-4o
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_payload}},
                        ],
                    }
                ],
                temperature=0,
                max_completion_tokens=self.settings.citation_eval_vlm_max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            return {
                "verdict": data.get("verdict", "unsure"),
                "confidence": data.get("confidence", 0),
                "evidence": data.get("evidence"),
                "reason": data.get("reason"),
            }

        except json.JSONDecodeError as exc:
            logger.warning("vlm_json_parse_error", error=str(exc))
            return {
                "verdict": "error",
                "confidence": 0,
                "evidence": None,
                "reason": f"Failed to parse VLM response: {exc}",
            }
        except Exception as exc:
            logger.warning("vlm_api_error", error=str(exc))
            return {
                "verdict": "error",
                "confidence": 0,
                "evidence": None,
                "reason": f"VLM API error: {exc}",
            }

    @staticmethod
    def _normalize_confidence(confidence: Any) -> Optional[float]:
        """Convert confidence (0-100) to score (0.0-1.0)."""
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return None
        return round(max(0.0, min(value / 100.0, 1.0)), 4)

    async def validate_citation(
        self,
        citation: str,
        chunk_text: str,
        question: Optional[str] = None,
        answer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate a single citation using GPT-4o vision.
        
        Args:
            citation: Citation string (e.g., "doc:360 pages:70-70 chunk:abc123 section:...")
            chunk_text: The text content of the cited chunk
            question: Optional question being answered
            answer: Optional answer given
            
        Returns:
            Validation result with verdict, score, evidence, and reason
        """
        parsed = self.parse_citation(citation)

        if not parsed.doc_id:
            return {
                "citation": citation,
                "doc_id": parsed.doc_id,
                "page_number": parsed.page_start,
                "chunk_id": parsed.chunk_id,
                "verdict": "error",
                "score": None,
                "method": "vlm",
                "evidence": None,
                "reason": "Unable to parse citation: missing doc_id",
            }

        if not parsed.page_start:
            parsed.page_start = 1
            parsed.page_end = 1

        # Try object storage first (native RAG docs), fall back to FASB on-disk
        page_image = None
        pdf_bytes = await self._fetch_pdf_from_storage(parsed.doc_id)
        if pdf_bytes:
            page_image = self._render_page_from_bytes(pdf_bytes, parsed.page_start)

        if page_image is None:
            page_image = self._render_pdf_page(parsed.doc_id, parsed.page_start)

        if page_image is None:
            return {
                "citation": citation,
                "doc_id": parsed.doc_id,
                "page_number": parsed.page_start,
                "chunk_id": parsed.chunk_id,
                "verdict": "unavailable",
                "score": None,
                "method": "vlm",
                "evidence": None,
                "reason": f"PDF not found for document {parsed.doc_id}",
            }

        # Validate using GPT-4o vision
        vlm_result = await self._vlm_validate(
            chunk_text=chunk_text,
            page_image=page_image,
            page_number=parsed.page_start,
            question=question,
            answer=answer,
        )

        return {
            "citation": citation,
            "doc_id": parsed.doc_id,
            "page_number": parsed.page_start,
            "chunk_id": parsed.chunk_id,
            "verdict": vlm_result.get("verdict", "unsure"),
            "score": self._normalize_confidence(vlm_result.get("confidence")),
            "method": "vlm",
            "evidence": vlm_result.get("evidence"),
            "reason": vlm_result.get("reason"),
        }

    async def validate_contexts(
        self,
        contexts: List[Any],
        question: Optional[str],
        answer: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Validate multiple contexts/citations."""
        validations: List[Dict[str, Any]] = []
        for context in contexts:
            citation = getattr(context, "citation", None) or ""
            text = getattr(context, "text", None) or ""
            validations.append(
                await self.validate_citation(citation, text, question, answer)
            )
        return validations

    @staticmethod
    def aggregate_score(validations: List[Dict[str, Any]]) -> Optional[float]:
        """Calculate average score from validations."""
        scores = [
            v.get("score")
            for v in validations
            if isinstance(v.get("score"), (int, float))
        ]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 4)
