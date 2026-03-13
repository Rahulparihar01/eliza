"""
Document Parser - Extract text from various document formats.

Supported file types: PDF, DOCX, DOC, PPTX, PPT, TXT, MD, HTML.

Parsing strategies:
- naive: Fast PyPDF2/python-docx/python-pptx text extraction
- docling: Full docling pipeline with layout analysis
- vlm: Vision Language Model for OCR (OpenAI-compatible API)
- gpt-5.2: OpenAI GPT-5.2 vision model (recommended, best OCR quality)
- gpt-4o: OpenAI GPT-4o vision model (legacy fallback)

For PDFs, VLM/GPT parsing renders pages as images and sends to a vision
model for OCR. For office formats (DOCX, PPTX), text is extracted
natively (python-docx / python-pptx) and then sent as text to the LLM
for structured section identification — no image conversion or
LibreOffice needed.
"""

import logging
import asyncio
import tempfile
import os
import base64
import io
from pathlib import Path
from typing import Optional, List, Dict, Any, BinaryIO, Callable, Awaitable, Tuple, Union, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# MIME types the LLM-based pipeline (GPT-4o/GPT-5/VLM) supports.
# PDFs go through the vision (image) path; office formats use text extraction + LLM structuring.
SUPPORTED_LLM_MIME_TYPES: Set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    "application/vnd.ms-powerpoint",  # .ppt
}

_OFFICE_MIME_TYPES: Set[str] = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
}


class ParserType(str, Enum):
    """Document parsing strategies."""
    NAIVE = "naive"           # Fast, plain text extraction
    DOCLING = "docling"       # Full docling pipeline with layout analysis
    DOCLING_OCR = "docling-ocr"  # Docling with OCR enabled
    VLM = "vlm"               # Vision Language Model for OCR
    CUSTOM_VLM = "custom-vlm" # Custom hosted VLM (OpenAI-compatible)
    GPT4O = "gpt-4o"          # OpenAI GPT-4o vision model (legacy)
    GPT5 = "gpt-5.2"          # OpenAI GPT-5.2 vision model (recommended)


@dataclass
class ParsedChunk:
    """A chunk of parsed document content."""
    text: str
    chunk_index: int
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Result of document parsing."""
    filename: str
    content: str
    chunks: List[ParsedChunk]
    page_count: int
    metadata: Dict[str, Any]
    parser_type: ParserType
    success: bool = True
    error: Optional[str] = None
    # LLM-identified logical sections (populated when structured_parse=True)
    structured_sections: Optional[List[Dict[str, Any]]] = None


class DocumentParser:
    """
    Parse documents into text using VLM, docling, or fallback methods.
    
    VLM parsing:
    - Sends document pages as images to a Vision Language Model
    - Best quality for scanned documents and complex layouts
    - Requires VLM API endpoint (OpenAI-compatible)
    
    Docling parsing:
    - Local document processing with layout detection
    - Good for structured documents
    """
    
    def __init__(
        self,
        parser_type: ParserType = ParserType.VLM,
        ocr_enabled: bool = False,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        vlm_base_url: str = "http://localhost:8000/v1",
        vlm_model: str = "default",
        vlm_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        page_parse_concurrency: int = 8,
        page_batch_size: int = 16,
        request_timeout_seconds: float = 120.0,
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 1.5,
        openai_max_tokens: int = 4096,
        page_hard_timeout_seconds: Optional[float] = None,
        pdf_render_dpi: int = 110,
        pdf_image_format: str = "jpeg",
        pdf_jpeg_quality: int = 70,
    ):
        self.parser_type = parser_type
        self.ocr_enabled = ocr_enabled or parser_type == ParserType.DOCLING_OCR
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.vlm_base_url = vlm_base_url.rstrip('/')
        self.vlm_model = vlm_model
        self.vlm_api_key = vlm_api_key
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.page_parse_concurrency = max(1, int(page_parse_concurrency or 1))
        self.page_batch_size = max(1, int(page_batch_size or 1))
        self.request_timeout_seconds = max(10.0, float(request_timeout_seconds or 120.0))
        self.retry_attempts = max(0, int(retry_attempts or 0))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds or 0.0))
        self.openai_max_tokens = max(256, int(openai_max_tokens or 4096))
        self.pdf_render_dpi = max(72, min(int(pdf_render_dpi or 110), 300))
        normalized_format = str(pdf_image_format or "jpeg").strip().lower()
        if normalized_format in {"jpg", "jpeg"}:
            self.pdf_image_format = "jpeg"
            self.pdf_image_mime_type = "image/jpeg"
        else:
            self.pdf_image_format = "png"
            self.pdf_image_mime_type = "image/png"
        self.pdf_jpeg_quality = max(30, min(int(pdf_jpeg_quality or 70), 95))
        retry_window = max(1, self.retry_attempts + 1)
        computed_timeout = min(
            180.0,
            (self.request_timeout_seconds * retry_window)
            + (self.retry_backoff_seconds * max(1, self.retry_attempts)),
        )
        self.page_hard_timeout_seconds = max(
            30.0,
            float(page_hard_timeout_seconds or computed_timeout),
        )
        self._docling_converter = None
    
    def _get_docling_converter(self):
        """Lazy-load docling converter."""
        if self._docling_converter is None:
            try:
                from docling.document_converter import DocumentConverter
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.datamodel.base_models import InputFormat
                
                # Configure pipeline options
                pipeline_options = PdfPipelineOptions()
                pipeline_options.do_ocr = self.ocr_enabled
                pipeline_options.do_table_structure = True
                
                self._docling_converter = DocumentConverter()
                logger.info(f"Docling converter initialized (OCR: {self.ocr_enabled})")
            except ImportError as e:
                logger.error(f"Docling not available: {e}")
                raise RuntimeError("Docling library not installed. Install with: pip install docling")
        return self._docling_converter
    
    async def parse_file(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        progress_callback: Optional[Callable[[int, int], Any]] = None,
    ) -> ParsedDocument:
        """
        Parse a document file into text content.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            mime_type: MIME type of the file
            
        Returns:
            ParsedDocument with extracted text and metadata
        """
        try:
            if self.parser_type == ParserType.NAIVE:
                return await self._parse_naive(file_content, filename, mime_type)
            elif self.parser_type == ParserType.GPT5:
                return await self._parse_with_openai(file_content, filename, mime_type, model="gpt-5.2")
            elif self.parser_type == ParserType.GPT4O:
                return await self._parse_with_openai(
                    file_content,
                    filename,
                    mime_type,
                    progress_callback=progress_callback,
                )
            elif self.parser_type in [ParserType.VLM, ParserType.CUSTOM_VLM]:
                return await self._parse_with_vlm(
                    file_content,
                    filename,
                    mime_type,
                    progress_callback=progress_callback,
                )
            else:
                return await self._parse_with_docling(file_content, filename, mime_type)
        except Exception as e:
            logger.error(f"Failed to parse {filename}: {e}")
            return ParsedDocument(
                filename=filename,
                content="",
                chunks=[],
                page_count=0,
                metadata={"mime_type": mime_type},
                parser_type=self.parser_type,
                success=False,
                error=str(e)
            )
    
    async def _parse_naive(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str
    ) -> ParsedDocument:
        """Fast, simple text extraction without layout analysis."""
        content = ""
        page_count = 1
        
        if mime_type == "application/pdf":
            content, page_count = self._extract_pdf_text(file_content)
        elif mime_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            content = self._extract_docx_text(file_content)
        elif mime_type in [
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        ]:
            content, page_count = self._extract_pptx_text(file_content)
        elif mime_type == "text/plain":
            content = file_content.decode("utf-8", errors="ignore")
        elif mime_type in ["text/markdown", "text/x-markdown"]:
            content = file_content.decode("utf-8", errors="ignore")
        elif mime_type == "text/html":
            content = self._extract_html_text(file_content)
        else:
            content = file_content.decode("utf-8", errors="ignore")
        
        # Create simple chunks
        chunks = self._create_chunks(content, filename)
        
        return ParsedDocument(
            filename=filename,
            content=content,
            chunks=chunks,
            page_count=page_count,
            metadata={"mime_type": mime_type, "char_count": len(content)},
            parser_type=ParserType.NAIVE
        )

    @staticmethod
    def _iter_page_batches(page_images: List[Tuple[int, str]], batch_size: int):
        """Yield fixed-size page batches for controlled request fan-out."""
        for start in range(0, len(page_images), batch_size):
            yield page_images[start:start + batch_size]

    async def _extract_page_with_retry(
        self,
        extract_fn: Callable[..., Awaitable[str]],
        *,
        image_base64: str,
        page_num: int,
        filename: str,
        client: Optional["httpx.AsyncClient"] = None,
    ) -> str:
        """Extract a page with bounded retry/backoff for transient provider errors."""
        attempts = self.retry_attempts + 1
        for attempt in range(1, attempts + 1):
            try:
                return await extract_fn(
                    image_base64,
                    page_num,
                    filename,
                    client=client,
                )
            except Exception as exc:
                if attempt >= attempts:
                    raise
                backoff = self.retry_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Page parse retry %s/%s for %s page=%s error=%s backoff=%.1fs",
                    attempt,
                    attempts - 1,
                    filename,
                    page_num,
                    str(exc),
                    backoff,
                )
                if backoff > 0:
                    await asyncio.sleep(backoff)

        return ""

    async def _extract_pages_parallel(
        self,
        *,
        page_images: List[Tuple[int, str]],
        filename: str,
        provider_name: str,
        extract_fn: Callable[..., Awaitable[str]],
        client: Optional["httpx.AsyncClient"] = None,
        progress_callback: Optional[Callable[[int, int], Any]] = None,
        return_page_map: bool = False,
    ) -> Union[List[str], Dict[int, str]]:
        """Extract pages concurrently in batches to maximize throughput safely."""
        if not page_images:
            return []

        total_pages = len(page_images)
        concurrency = max(1, min(self.page_parse_concurrency, total_pages))
        batch_size = max(concurrency, self.page_batch_size)
        extracted_by_page: Dict[int, str] = {}
        completed = 0
        succeeded = 0
        failed = 0
        total_batches = (total_pages + batch_size - 1) // batch_size

        logger.info(
            "Starting %s parsing for %s pages=%s concurrency=%s batch_size=%s",
            provider_name,
            filename,
            total_pages,
            concurrency,
            batch_size,
        )

        for batch_idx, page_batch in enumerate(
            self._iter_page_batches(page_images, batch_size),
            start=1,
        ):
            semaphore = asyncio.Semaphore(concurrency)

            async def _parse_one(page_num: int, image_base64: str):
                async with semaphore:
                    try:
                        page_text = await asyncio.wait_for(
                            self._extract_page_with_retry(
                                extract_fn,
                                image_base64=image_base64,
                                page_num=page_num,
                                filename=filename,
                                client=client,
                            ),
                            timeout=self.page_hard_timeout_seconds,
                        )
                        return page_num, page_text, None
                    except asyncio.TimeoutError:
                        timeout_msg = (
                            f"page parse timed out after {self.page_hard_timeout_seconds:.1f}s"
                        )
                        logger.warning(
                            "%s timeout on page %s of %s (%s)",
                            provider_name,
                            page_num,
                            filename,
                            timeout_msg,
                        )
                        return page_num, "", timeout_msg
                    except Exception as exc:
                        return page_num, "", str(exc)

            tasks = [
                asyncio.create_task(_parse_one(page_num, image_base64))
                for page_num, image_base64 in page_batch
            ]
            results = await asyncio.gather(*tasks)

            for page_num, page_text, error in results:
                completed += 1
                if error:
                    failed += 1
                    logger.error("%s failed on page %s of %s: %s", provider_name, page_num, filename, error)
                    continue

                if page_text:
                    succeeded += 1
                    extracted_by_page[page_num] = page_text

            logger.info(
                "%s progress for %s: %s/%s pages done (success=%s failed=%s batch=%s/%s)",
                provider_name,
                filename,
                completed,
                total_pages,
                succeeded,
                failed,
                batch_idx,
                total_batches,
            )
            if progress_callback is not None:
                try:
                    callback_result = progress_callback(completed, total_pages)
                    if asyncio.iscoroutine(callback_result):
                        await callback_result
                except Exception as callback_exc:
                    logger.debug(
                        "Progress callback failed for %s page progress on %s: %s",
                        provider_name,
                        filename,
                        str(callback_exc),
                    )

        if return_page_map:
            return extracted_by_page

        ordered_text: List[str] = []
        for page_num, _ in page_images:
            page_text = extracted_by_page.get(page_num)
            if not page_text:
                continue
            ordered_text.append(f"--- Page {page_num} ---\n{page_text}")

        return ordered_text
    
    async def _parse_with_vlm(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        progress_callback: Optional[Callable[[int, int], Any]] = None,
    ) -> ParsedDocument:
        """
        Parse document using Vision Language Model for OCR.
        
        Converts PDF pages to images and sends to VLM for text extraction.
        Works with any OpenAI-compatible vision API.
        """
        import httpx

        if mime_type not in SUPPORTED_LLM_MIME_TYPES:
            logger.info(f"VLM parsing unsupported for {mime_type}, falling back to naive for {filename}")
            return await self._parse_naive(file_content, filename, mime_type)

        if mime_type in _OFFICE_MIME_TYPES:
            return await self._parse_office_with_llm(
                file_content, filename, mime_type,
                structured=False, progress_callback=progress_callback,
            )

        page_images = self._pdf_to_images(file_content)
        if not page_images:
            logger.warning(f"Could not convert PDF to images, falling back to naive: {filename}")
            return await self._parse_naive(file_content, filename, mime_type)
        
        logger.info(f"Parsing {filename} with VLM ({len(page_images)} pages)")

        # Process pages concurrently in controllable batches.
        async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as client:
            all_text = await self._extract_pages_parallel(
                page_images=page_images,
                filename=filename,
                provider_name="VLM",
                extract_fn=self._vlm_extract_text,
                client=client,
                progress_callback=progress_callback,
            )
        
        content = "\n\n".join(all_text)
        
        if not content:
            logger.warning(f"VLM returned no text for {filename}, falling back to naive")
            return await self._parse_naive(file_content, filename, mime_type)
        
        # Create chunks
        chunks = self._create_chunks(content, filename)
        
        return ParsedDocument(
            filename=filename,
            content=content,
            chunks=chunks,
            page_count=len(page_images),
            metadata={
                "mime_type": mime_type,
                "char_count": len(content),
                "parser": "vlm",
                "vlm_model": self.vlm_model
            },
            parser_type=ParserType.VLM
        )
    
    async def _parse_with_openai(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        progress_callback: Optional[Callable[[int, int], Any]] = None,
        model: str = "gpt-4o",
    ) -> ParsedDocument:
        """
        Parse document using OpenAI vision model.
        
        Uses OpenAI's official API endpoint for high-quality OCR.
        Default model is GPT-5.2 (best vision/OCR quality, ELO #1).
        Supports GPT-4o as fallback for cost-sensitive use cases.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            mime_type: MIME type
            model: OpenAI model to use ("gpt-5.2" or "gpt-4o")
        """
        import httpx
        
        if not self.openai_api_key:
            logger.warning("No OpenAI API key configured, falling back to naive parsing")
            return await self._parse_naive(file_content, filename, mime_type)

        if mime_type not in SUPPORTED_LLM_MIME_TYPES:
            logger.info(f"{model} parsing unsupported for {mime_type}, falling back to naive for {filename}")
            return await self._parse_naive(file_content, filename, mime_type)

        if mime_type in _OFFICE_MIME_TYPES:
            return await self._parse_office_with_llm(
                file_content, filename, mime_type, model=model,
                structured=False, progress_callback=progress_callback,
            )

        page_images = self._pdf_to_images(file_content)
        if not page_images:
            logger.warning(f"Could not convert PDF to images, falling back to naive: {filename}")
            return await self._parse_naive(file_content, filename, mime_type)

        logger.info(f"Parsing {filename} with OpenAI {model} ({len(page_images)} pages)")

        self._openai_model = model

        # Process pages concurrently in controllable batches.
        limits = httpx.Limits(
            max_connections=max(100, self.page_parse_concurrency * 8),
            max_keepalive_connections=max(20, self.page_parse_concurrency * 2),
        )
        async with httpx.AsyncClient(
            timeout=self.request_timeout_seconds,
            limits=limits,
        ) as client:
            all_text = await self._extract_pages_parallel(
                page_images=page_images,
                filename=filename,
                provider_name="OpenAI GPT-4o",
                extract_fn=self._openai_extract_text,
                client=client,
                progress_callback=progress_callback,
            )

        content = "\n\n".join(all_text)
        
        if not content:
            logger.warning(f"OpenAI {model} returned no text for {filename}, falling back to naive")
            return await self._parse_naive(file_content, filename, mime_type)
        
        chunks = self._create_chunks(content, filename)
        
        # Map model to parser type
        parser_type = ParserType.GPT5 if model.startswith("gpt-5") else ParserType.GPT4O
        
        return ParsedDocument(
            filename=filename,
            content=content,
            chunks=chunks,
            page_count=len(page_images),
            metadata={
                "mime_type": mime_type,
                "char_count": len(content),
                "parser": model,
                "model": model,
                "total_pages": len(page_images),
                "ocr_pages": len(page_images),
            },
            parser_type=parser_type
        )
    
    async def _openai_extract_text(
        self,
        image_base64: str,
        page_num: int,
        filename: str,
        client: Optional["httpx.AsyncClient"] = None,
    ) -> str:
        """Send image to OpenAI vision model for text extraction."""
        import httpx
        
        model = getattr(self, "_openai_model", "gpt-4o")
        
        url = "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all text from this document image. Preserve the structure including headers, paragraphs, lists, and tables. Return only the extracted text, no commentary."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{self.pdf_image_mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_completion_tokens": self.openai_max_tokens,
            "temperature": 0
        }

        if client is not None:
            response = await client.post(url, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as standalone_client:
                response = await standalone_client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error(f"OpenAI API error: {response.status_code} - {response.text[:500]}")
            raise Exception(f"OpenAI API returned {response.status_code}")

        data = response.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return text.strip()

    _STRUCTURED_PARSE_PROMPT = (
        "Extract all content from this document page image. "
        "Return a JSON array of logical sections found on this page. "
        "Each section object must have:\n"
        '- "heading": the section/subsection heading if visible (null if none)\n'
        '- "text": the full text content of that section\n'
        '- "type": one of "paragraph", "table", "list", "header", "definition", "example", "footnote"\n'
        "\n"
        "Rules:\n"
        "- Keep each section as a self-contained logical unit (don't split mid-paragraph)\n"
        "- Tables should be kept as one section with pipe-delimited rows\n"
        "- Numbered/bulleted lists should be kept together\n"
        "- If a section continues from the previous page, start it with the text that appears on this page\n"
        "- Preserve ALL text exactly as it appears\n"
        "- Return ONLY the JSON array, no markdown fences, no commentary"
    )

    async def _openai_extract_structured(
        self,
        image_base64: str,
        page_num: int,
        filename: str,
        client: Optional["httpx.AsyncClient"] = None,
    ) -> str:
        """Extract structured JSON sections from a page image via OpenAI vision."""
        import httpx

        model = getattr(self, "_openai_model", "gpt-4o")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._STRUCTURED_PARSE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{self.pdf_image_mime_type};base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            "max_completion_tokens": self.openai_max_tokens,
            "temperature": 0,
        }

        if client is not None:
            response = await client.post(url, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as sc:
                response = await sc.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error("OpenAI structured parse error: %s - %s", response.status_code, response.text[:500])
            raise Exception(f"OpenAI API returned {response.status_code}")

        raw = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return raw.strip()

    async def _parse_with_openai_structured(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        progress_callback: Optional[Callable[[int, int], Any]] = None,
        model: str = "gpt-4o",
    ) -> ParsedDocument:
        """
        Parse document using OpenAI vision with structured JSON output per page.

        Each page returns a JSON array of logical sections with headings and types.
        This produces both raw text (for backward compat) and structured_sections
        that the LLM chunking strategy can use directly.
        """
        import httpx
        import json as _json

        if not self.openai_api_key:
            return await self._parse_naive(file_content, filename, mime_type)
        if mime_type not in SUPPORTED_LLM_MIME_TYPES:
            return await self._parse_naive(file_content, filename, mime_type)

        if mime_type in _OFFICE_MIME_TYPES:
            return await self._parse_office_with_llm(
                file_content, filename, mime_type, model=model,
                structured=True, progress_callback=progress_callback,
            )

        page_images = self._pdf_to_images(file_content)
        if not page_images:
            return await self._parse_naive(file_content, filename, mime_type)

        logger.info("Structured parsing %s with %s (%d pages)", filename, model, len(page_images))
        self._openai_model = model

        limits = httpx.Limits(
            max_connections=max(100, self.page_parse_concurrency * 8),
            max_keepalive_connections=max(20, self.page_parse_concurrency * 2),
        )
        async with httpx.AsyncClient(timeout=self.request_timeout_seconds, limits=limits) as client:
            page_results = await self._extract_pages_parallel(
                page_images=page_images,
                filename=filename,
                provider_name=f"OpenAI-Structured({model})",
                extract_fn=self._openai_extract_structured,
                client=client,
                progress_callback=progress_callback,
                return_page_map=True,
            )

        all_sections: List[Dict[str, Any]] = []
        text_parts: List[str] = []

        for page_num, _ in page_images:
            raw_page = page_results.get(page_num, "") if isinstance(page_results, dict) else ""
            if not raw_page:
                continue

            # Parse the JSON output
            cleaned = raw_page.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            try:
                sections = _json.loads(cleaned)
                if not isinstance(sections, list):
                    sections = [sections]
            except _json.JSONDecodeError:
                # Fallback: treat as raw text
                sections = [{"heading": None, "text": raw_page, "type": "paragraph"}]

            page_text_parts = []
            for section in sections:
                if not isinstance(section, dict):
                    continue
                section["page_number"] = page_num
                all_sections.append(section)
                text = section.get("text", "")
                heading = section.get("heading")
                if heading:
                    page_text_parts.append(f"{heading}\n{text}")
                else:
                    page_text_parts.append(text)

            text_parts.append(f"--- Page {page_num} ---\n" + "\n\n".join(page_text_parts))

        content = "\n\n".join(text_parts)

        if not content:
            logger.warning("Structured parse returned no content for %s, falling back", filename)
            return await self._parse_naive(file_content, filename, mime_type)

        chunks = self._create_chunks(content, filename)
        parser_type = ParserType.GPT5 if model.startswith("gpt-5") else ParserType.GPT4O

        return ParsedDocument(
            filename=filename,
            content=content,
            chunks=chunks,
            page_count=len(page_images),
            metadata={
                "mime_type": mime_type,
                "char_count": len(content),
                "parser": model,
                "model": model,
                "structured_parse": True,
                "total_sections": len(all_sections),
            },
            parser_type=parser_type,
            structured_sections=all_sections,
        )

    def _pdf_to_images(
        self,
        pdf_content: bytes,
        page_numbers: Optional[Set[int]] = None,
    ) -> List[tuple]:
        """Convert PDF pages to base64 images for VLM."""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            images = []
            
            for page_num in range(len(doc)):
                current_page = page_num + 1
                if page_numbers is not None and current_page not in page_numbers:
                    continue
                page = doc[page_num]
                mat = fitz.Matrix(self.pdf_render_dpi / 72, self.pdf_render_dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                if self.pdf_image_format == "jpeg":
                    img_bytes = pix.tobytes("jpeg", jpg_quality=self.pdf_jpeg_quality)
                else:
                    img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                images.append((current_page, img_base64))
            
            doc.close()
            return images
            
        except ImportError:
            logger.warning("PyMuPDF not installed, trying pdf2image")
            try:
                from pdf2image import convert_from_bytes
                
                pages = convert_from_bytes(pdf_content, dpi=self.pdf_render_dpi)
                images = []
                
                for i, page in enumerate(pages):
                    current_page = i + 1
                    if page_numbers is not None and current_page not in page_numbers:
                        continue
                    img_buffer = io.BytesIO()
                    if self.pdf_image_format == "jpeg":
                        page.save(
                            img_buffer,
                            format="JPEG",
                            quality=self.pdf_jpeg_quality,
                            optimize=True,
                        )
                    else:
                        page.save(img_buffer, format="PNG")
                    img_base64 = base64.b64encode(img_buffer.getvalue()).decode("utf-8")
                    images.append((current_page, img_base64))
                
                return images
            except Exception as e:
                logger.error(f"Failed to convert PDF to images: {e}")
                return []
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {e}")
            return []

    def _extract_office_text(self, file_content: bytes, filename: str, mime_type: str) -> Tuple[str, int]:
        """Extract text from office documents using pure-Python libraries.

        Returns (text_with_page_markers, page_count).
        """
        if mime_type in (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        ):
            return self._extract_pptx_text(file_content)

        if mime_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ):
            text = self._extract_docx_text(file_content)
            page_count = max(1, text.count("\f") + 1) if text else 0
            return text, page_count

        return "", 0

    async def _parse_office_with_llm(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str,
        *,
        model: str = "gpt-4o",
        structured: bool = False,
        progress_callback: Optional[Callable[[int, int], Any]] = None,
    ) -> ParsedDocument:
        """Parse an office document by extracting text natively, then using an LLM
        for structured section identification.

        This avoids the vision/image pipeline entirely — the text is already digital.
        """
        import httpx
        import json as _json

        raw_text, page_count = self._extract_office_text(file_content, filename, mime_type)
        if not raw_text or not raw_text.strip():
            logger.warning("No text extracted from %s, returning empty", filename)
            return ParsedDocument(
                filename=filename, content="", chunks=[], page_count=0,
                metadata={"mime_type": mime_type}, parser_type=ParserType.NAIVE,
                success=False, error="No text could be extracted from the document",
            )

        if not self.openai_api_key or not structured:
            # No LLM structuring requested or possible — return naive-quality result
            # with page markers already in place from extraction.
            chunks = self._create_chunks(raw_text, filename)
            parser_type = ParserType.GPT5 if model.startswith("gpt-5") else ParserType.GPT4O
            return ParsedDocument(
                filename=filename, content=raw_text, chunks=chunks,
                page_count=page_count,
                metadata={
                    "mime_type": mime_type, "char_count": len(raw_text),
                    "parser": model, "model": model,
                    "office_native_extraction": True,
                },
                parser_type=parser_type,
            )

        # --- LLM-based structured parsing via text (not vision) ---
        logger.info(
            "Structured-text parsing %s with %s (%d chars extracted)",
            filename, model, len(raw_text),
        )
        self._openai_model = model

        # Split into manageable text windows (~6000 chars each) to avoid
        # exceeding context limits and to get per-section granularity.
        window_size = 6000
        text_windows: List[Tuple[int, str]] = []
        for i in range(0, len(raw_text), window_size):
            window_idx = i // window_size + 1
            text_windows.append((window_idx, raw_text[i:i + window_size]))

        if progress_callback:
            try:
                cb = progress_callback(0, len(text_windows))
                if asyncio.iscoroutine(cb):
                    await cb
            except Exception:
                pass

        all_sections: List[Dict[str, Any]] = []
        text_parts: List[str] = []

        limits = httpx.Limits(
            max_connections=max(100, self.page_parse_concurrency * 8),
            max_keepalive_connections=max(20, self.page_parse_concurrency * 2),
        )
        async with httpx.AsyncClient(timeout=self.request_timeout_seconds, limits=limits) as client:
            for win_idx, window_text in text_windows:
                try:
                    structured_json = await self._openai_structure_text(
                        window_text, win_idx, filename, client=client,
                    )
                except Exception as exc:
                    logger.warning("LLM structuring failed for window %s of %s: %s", win_idx, filename, exc)
                    structured_json = ""

                cleaned = structured_json.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                try:
                    sections = _json.loads(cleaned)
                    if not isinstance(sections, list):
                        sections = [sections]
                except _json.JSONDecodeError:
                    sections = [{"heading": None, "text": window_text, "type": "paragraph"}]

                page_text_parts = []
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    section["page_number"] = win_idx
                    all_sections.append(section)
                    text = section.get("text", "")
                    heading = section.get("heading")
                    if heading:
                        page_text_parts.append(f"{heading}\n{text}")
                    else:
                        page_text_parts.append(text)

                text_parts.append(f"--- Page {win_idx} ---\n" + "\n\n".join(page_text_parts))

                if progress_callback:
                    try:
                        cb = progress_callback(win_idx, len(text_windows))
                        if asyncio.iscoroutine(cb):
                            await cb
                    except Exception:
                        pass

        content = "\n\n".join(text_parts) if text_parts else raw_text
        chunks = self._create_chunks(content, filename)
        parser_type = ParserType.GPT5 if model.startswith("gpt-5") else ParserType.GPT4O

        return ParsedDocument(
            filename=filename, content=content, chunks=chunks,
            page_count=page_count,
            metadata={
                "mime_type": mime_type, "char_count": len(content),
                "parser": model, "model": model,
                "structured_parse": True, "total_sections": len(all_sections),
                "office_native_extraction": True,
            },
            parser_type=parser_type,
            structured_sections=all_sections,
        )

    async def _openai_structure_text(
        self,
        text: str,
        window_index: int,
        filename: str,
        client: Optional["httpx.AsyncClient"] = None,
    ) -> str:
        """Send extracted text to OpenAI for structured section identification (no vision)."""
        import httpx

        model = getattr(self, "_openai_model", "gpt-4o")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}",
        }

        prompt = (
            "Analyze the following document text and return a JSON array of logical sections. "
            "Each section object must have:\n"
            '- "heading": the section/subsection heading if identifiable (null if none)\n'
            '- "text": the full text content of that section\n'
            '- "type": one of "paragraph", "table", "list", "header", "definition", "example", "footnote"\n'
            "\nRules:\n"
            "- Keep each section as a self-contained logical unit\n"
            "- Tables should be kept as one section\n"
            "- Numbered/bulleted lists should be kept together\n"
            "- Preserve ALL text exactly as it appears\n"
            "- Return ONLY the JSON array, no markdown fences, no commentary\n"
            "\n--- DOCUMENT TEXT ---\n"
            f"{text}"
        )

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_completion_tokens": self.openai_max_tokens,
            "temperature": 0,
        }

        if client is not None:
            response = await client.post(url, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as sc:
                response = await sc.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error("OpenAI text structuring error: %s - %s", response.status_code, response.text[:500])
            raise Exception(f"OpenAI API returned {response.status_code}")

        return (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

    async def _vlm_extract_text(
        self,
        image_base64: str,
        page_num: int,
        filename: str,
        client: Optional["httpx.AsyncClient"] = None,
    ) -> str:
        """Send image to VLM API for text extraction."""
        import httpx
        
        url = f"{self.vlm_base_url}/chat/completions"
        
        headers = {"Content-Type": "application/json"}
        if self.vlm_api_key:
            headers["Authorization"] = f"Bearer {self.vlm_api_key}"
        
        payload = {
            "model": self.vlm_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all text from this document image. Preserve the structure including headers, paragraphs, lists, and tables. Return only the extracted text, no commentary."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{self.pdf_image_mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_completion_tokens": 4096,
            "temperature": 0
        }

        if client is not None:
            response = await client.post(url, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.request_timeout_seconds) as standalone_client:
                response = await standalone_client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error(f"VLM API error: {response.status_code} - {response.text[:500]}")
            raise Exception(f"VLM API returned {response.status_code}")

        data = response.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return text.strip()
    
    async def _parse_with_docling(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str
    ) -> ParsedDocument:
        """Parse using docling for rich document understanding."""
        import asyncio
        
        # Docling is synchronous, run in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._parse_with_docling_sync,
            file_content,
            filename,
            mime_type
        )
    
    def _parse_with_docling_sync(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str
    ) -> ParsedDocument:
        """Synchronous docling parsing."""
        converter = self._get_docling_converter()
        
        # Write to temp file (docling needs file path)
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # Convert document
            result = converter.convert(tmp_path)
            
            # Extract text content
            content = result.document.export_to_markdown()
            
            # Get page count
            page_count = len(result.document.pages) if hasattr(result.document, 'pages') else 1
            
            # Extract metadata
            metadata = {
                "mime_type": mime_type,
                "char_count": len(content),
                "has_tables": bool(result.document.tables) if hasattr(result.document, 'tables') else False,
                "has_images": bool(result.document.pictures) if hasattr(result.document, 'pictures') else False,
            }
            
            # Create chunks with section awareness
            chunks = self._create_chunks_from_docling(result.document, filename)
            
            return ParsedDocument(
                filename=filename,
                content=content,
                chunks=chunks,
                page_count=page_count,
                metadata=metadata,
                parser_type=self.parser_type
            )
        finally:
            # Cleanup temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _extract_pdf_text(self, content: bytes) -> tuple[str, int]:
        """Extract text from PDF using PyPDF2."""
        try:
            from PyPDF2 import PdfReader
            import io
            
            reader = PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text() or ""
                text_parts.append(text)
            
            return "\n\n".join(text_parts), len(reader.pages)
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}")
            return "", 0
    
    def _extract_docx_text(self, content: bytes) -> str:
        """Extract text from DOCX."""
        try:
            from docx import Document
            import io
            
            doc = Document(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as e:
            logger.warning(f"DOCX extraction failed: {e}")
            return ""
    
    def _extract_html_text(self, content: bytes) -> str:
        """Extract text from HTML."""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(content, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            return soup.get_text(separator="\n", strip=True)
        except Exception as e:
            logger.warning(f"HTML extraction failed: {e}")
            return content.decode("utf-8", errors="ignore")

    def _extract_pptx_text(self, content: bytes) -> tuple[str, int]:
        """Extract text from PPTX (PowerPoint)."""
        try:
            from pptx import Presentation

            prs = Presentation(io.BytesIO(content))
            slide_texts = []
            for i, slide in enumerate(prs.slides, start=1):
                parts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for paragraph in shape.text_frame.paragraphs:
                            text = paragraph.text.strip()
                            if text:
                                parts.append(text)
                    if shape.has_table:
                        table = shape.table
                        for row in table.rows:
                            row_text = " | ".join(
                                cell.text.strip() for cell in row.cells
                            )
                            if row_text.strip(" |"):
                                parts.append(row_text)
                if parts:
                    slide_texts.append(f"--- Slide {i} ---\n" + "\n".join(parts))
            return "\n\n".join(slide_texts), len(prs.slides)
        except ImportError:
            logger.warning("python-pptx not installed, cannot extract PPTX text")
            return "", 0
        except Exception as e:
            logger.warning(f"PPTX extraction failed: {e}")
            return "", 0

    def _create_chunks(self, content: str, filename: str) -> List[ParsedChunk]:
        """Create text chunks with page number tracking.
        
        Parses ``--- Page N ---`` markers (injected by VLM extraction) to
        assign the correct ``page_number`` to each chunk.
        """
        import re as _re

        if not content:
            return []

        # Split content into (page_number, text) segments using page/slide markers
        page_marker_re = _re.compile(r"---\s*(?:Page|Slide)\s+(\d+)\s*---")
        segments: list[tuple[Optional[int], str]] = []
        last_pos = 0
        current_page: Optional[int] = None

        for m in page_marker_re.finditer(content):
            # Text before this marker belongs to current_page
            text_before = content[last_pos:m.start()].strip()
            if text_before:
                segments.append((current_page, text_before))
            current_page = int(m.group(1))
            last_pos = m.end()

        # Remaining text after last marker
        tail = content[last_pos:].strip()
        if tail:
            segments.append((current_page, tail))

        # Build word list with page numbers tracked per-word
        word_pages: list[tuple[str, Optional[int]]] = []
        for page_num, seg_text in segments:
            for word in seg_text.split():
                word_pages.append((word, page_num))

        if not word_pages:
            return []

        words_per_chunk = self.chunk_size // 5
        overlap_words = self.chunk_overlap // 5

        chunks: list[ParsedChunk] = []
        i = 0
        chunk_idx = 0
        while i < len(word_pages):
            window = word_pages[i:i + words_per_chunk]
            chunk_text = " ".join(w for w, _ in window)

            # Determine page number: most common page in the window
            page_counts: dict[Optional[int], int] = {}
            for _, pg in window:
                page_counts[pg] = page_counts.get(pg, 0) + 1
            dominant_page = max(page_counts, key=lambda k: page_counts[k])

            chunks.append(ParsedChunk(
                text=chunk_text,
                chunk_index=chunk_idx,
                page_number=dominant_page,
                metadata={"source": filename},
            ))

            i += words_per_chunk - overlap_words
            chunk_idx += 1

        return chunks
    
    def _create_chunks_from_docling(self, document, filename: str) -> List[ParsedChunk]:
        """Create chunks from docling document with section awareness."""
        chunks = []
        chunk_idx = 0
        
        # Try to get text items from docling document
        try:
            # Export to markdown and chunk that
            content = document.export_to_markdown()
            
            # Split by sections (markdown headers)
            import re
            sections = re.split(r'\n(?=#{1,6}\s)', content)
            
            for section in sections:
                if not section.strip():
                    continue
                
                # Extract section title if present
                title_match = re.match(r'^(#{1,6})\s+(.+?)(?:\n|$)', section)
                section_title = title_match.group(2) if title_match else None
                
                # Create chunks from section
                section_chunks = self._create_chunks(section, filename)
                for chunk in section_chunks:
                    chunk.chunk_index = chunk_idx
                    chunk.section_title = section_title
                    chunks.append(chunk)
                    chunk_idx += 1
                    
        except Exception as e:
            logger.warning(f"Failed to extract docling sections: {e}")
            # Fallback to simple chunking
            content = str(document)
            chunks = self._create_chunks(content, filename)
        
        return chunks
