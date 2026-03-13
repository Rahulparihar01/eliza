"""
Metadata Enrichment Service - Enrich document and chunk metadata for production RAG.

Enrichment layers:
1. Document-level: PDF metadata extraction, language detection, LLM-generated summary/title
2. Chunk-level: page numbers, section hierarchy, LLM-generated summaries + hypothetical questions
3. Knowledge base context: KB name/description attached to each chunk for multi-KB retrieval
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from .chunking import TextChunk

logger = logging.getLogger(__name__)

# Cheaper/faster model for metadata enrichment tasks
_DEFAULT_ENRICHMENT_MODEL = "gpt-4o-mini"

_DOCUMENT_SUMMARY_PROMPT = """Analyze the following document excerpt and produce a JSON object with these fields:
- "title": A concise descriptive title for this document (max 12 words).
- "summary": A 2-3 sentence summary of the document's main content and purpose.
- "language": The primary language of the document (e.g., "en", "es", "fr").
- "document_type": The type of document (e.g., "report", "policy", "manual", "research_paper", "legal", "financial", "technical", "presentation", "correspondence", "other").
- "key_topics": A list of 3-7 key topics/themes covered (short phrases).

Return ONLY valid JSON, no markdown fencing.

Document excerpt (first ~3000 chars):
{text_excerpt}"""

_CHUNK_ENRICHMENT_PROMPT = """For each of the following numbered text chunks from a document titled "{doc_title}", produce a JSON array where each element has:
- "index": the chunk number
- "summary": A 1-sentence summary of the chunk's content (max 30 words).
- "key_entities": Up to 5 important named entities (people, organizations, dates, specific terms) found in the chunk.
- "hypothetical_questions": 2-3 questions that this chunk would answer, phrased as a user might ask them.
- "chunk_type": One of "text", "table", "list", "header", "definition", "example", "reference".

Return ONLY a valid JSON array, no markdown fencing.

Chunks:
{chunks_text}"""


@dataclass
class DocumentMetadata:
    """Enriched document-level metadata."""
    title: Optional[str] = None
    summary: Optional[str] = None
    language: str = "en"
    document_type: str = "other"
    key_topics: List[str] = field(default_factory=list)
    total_pages: int = 0
    file_type: str = ""
    file_size_bytes: int = 0
    author: Optional[str] = None
    creation_date: Optional[str] = None
    producer: Optional[str] = None
    pdf_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkMetadata:
    """Enriched chunk-level metadata."""
    chunk_index: int = 0
    page_number: Optional[int] = None
    page_range: Optional[List[int]] = None
    section_title: Optional[str] = None
    section_hierarchy: List[str] = field(default_factory=list)
    heading_context: Optional[str] = None
    chunk_type: str = "text"
    chunk_summary: Optional[str] = None
    key_entities: List[str] = field(default_factory=list)
    hypothetical_questions: List[str] = field(default_factory=list)
    has_table: bool = False
    has_code: bool = False
    has_list: bool = False
    token_count: int = 0
    char_count: int = 0
    # KB context
    knowledge_base_id: Optional[int] = None
    knowledge_base_name: Optional[str] = None
    knowledge_base_description: Optional[str] = None
    workspace_id: Optional[int] = None
    workspace_name: Optional[str] = None
    # Document context
    document_id: Optional[int] = None
    document_title: Optional[str] = None
    document_type: str = "other"
    filename: str = ""

    def to_flat_dict(self) -> Dict[str, Any]:
        """Flatten to a dict suitable for OpenSearch metadata field."""
        d = {
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "section_hierarchy": self.section_hierarchy or [],
            "heading_context": self.heading_context,
            "chunk_type": self.chunk_type,
            "chunk_summary": self.chunk_summary,
            "key_entities": self.key_entities or [],
            "hypothetical_questions": self.hypothetical_questions or [],
            "has_table": self.has_table,
            "has_code": self.has_code,
            "has_list": self.has_list,
            "token_count": self.token_count,
            "char_count": self.char_count,
            "knowledge_base_id": self.knowledge_base_id,
            "knowledge_base_name": self.knowledge_base_name,
            "knowledge_base_description": self.knowledge_base_description,
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "document_type": self.document_type,
            "filename": self.filename,
        }
        if self.page_range:
            d["page_range"] = self.page_range
        return d


class MetadataEnrichmentService:
    """
    Enrich documents and chunks with metadata for production-quality RAG.

    Three enrichment tiers:
    - BASIC: structural metadata only (page numbers, headings, file metadata) — no LLM calls
    - STANDARD: BASIC + LLM document summary/title (1 LLM call per document)
    - FULL: STANDARD + per-chunk LLM enrichment (summaries, entities, hypothetical Qs)
    """

    class Tier:
        BASIC = "basic"
        STANDARD = "standard"
        FULL = "full"

    def __init__(
        self,
        enrichment_tier: str = "standard",
        enrichment_model: str = _DEFAULT_ENRICHMENT_MODEL,
        max_chunks_per_llm_batch: int = 10,
        contextual_headers: bool = True,
    ):
        self.enrichment_tier = enrichment_tier
        self.enrichment_model = enrichment_model
        self.max_chunks_per_llm_batch = max_chunks_per_llm_batch
        self.contextual_headers = contextual_headers

    # ------------------------------------------------------------------
    # Document-level enrichment
    # ------------------------------------------------------------------

    def extract_pdf_metadata(self, file_content: bytes) -> Dict[str, Any]:
        """Extract metadata from PDF file (author, creation date, producer, etc.)."""
        meta: Dict[str, Any] = {}
        try:
            import fitz
            doc = fitz.open(stream=file_content, filetype="pdf")
            pdf_meta = doc.metadata or {}
            meta["author"] = pdf_meta.get("author") or None
            meta["title"] = pdf_meta.get("title") or None
            meta["subject"] = pdf_meta.get("subject") or None
            meta["creator"] = pdf_meta.get("creator") or None
            meta["producer"] = pdf_meta.get("producer") or None
            raw_date = pdf_meta.get("creationDate") or ""
            meta["creation_date"] = self._parse_pdf_date(raw_date)
            mod_date = pdf_meta.get("modDate") or ""
            meta["modification_date"] = self._parse_pdf_date(mod_date)
            meta["total_pages"] = len(doc)
            meta["keywords"] = pdf_meta.get("keywords") or None
            doc.close()
        except Exception as exc:
            logger.warning("pdf_metadata_extraction_failed: %s", exc)
        return meta

    @staticmethod
    def _parse_pdf_date(raw: str) -> Optional[str]:
        """Parse PDF date format D:YYYYMMDDHHmmSS into ISO-ish string."""
        if not raw:
            return None
        cleaned = raw.replace("D:", "").replace("'", "")
        try:
            dt = datetime.strptime(cleaned[:14], "%Y%m%d%H%M%S")
            return dt.isoformat()
        except (ValueError, IndexError):
            return cleaned[:10] if len(cleaned) >= 8 else None

    @staticmethod
    def detect_file_type(filename: str, mime_type: str) -> str:
        """Determine canonical file type label."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        type_map = {
            "pdf": "pdf",
            "docx": "docx",
            "doc": "doc",
            "txt": "text",
            "md": "markdown",
            "html": "html",
            "htm": "html",
            "csv": "csv",
            "xlsx": "excel",
            "pptx": "powerpoint",
        }
        return type_map.get(ext, mime_type.split("/")[-1] if mime_type else "unknown")

    async def enrich_document_metadata(
        self,
        *,
        file_content: bytes,
        filename: str,
        mime_type: str,
        parsed_text: str,
        page_count: int,
    ) -> DocumentMetadata:
        """
        Build enriched document-level metadata.

        For BASIC tier: only structural/file metadata (no LLM).
        For STANDARD+: adds LLM-generated title, summary, topics.
        """
        meta = DocumentMetadata(
            total_pages=page_count,
            file_type=self.detect_file_type(filename, mime_type),
            file_size_bytes=len(file_content),
        )

        if mime_type == "application/pdf":
            pdf_meta = self.extract_pdf_metadata(file_content)
            meta.pdf_metadata = pdf_meta
            meta.author = pdf_meta.get("author")
            meta.creation_date = pdf_meta.get("creation_date")
            meta.producer = pdf_meta.get("producer")
            if pdf_meta.get("title"):
                meta.title = pdf_meta["title"]
            if pdf_meta.get("total_pages"):
                meta.total_pages = pdf_meta["total_pages"]

        if self.enrichment_tier in (self.Tier.STANDARD, self.Tier.FULL):
            llm_meta = await self._llm_document_summary(parsed_text)
            if llm_meta:
                if not meta.title or meta.title.strip() == "":
                    meta.title = llm_meta.get("title")
                meta.summary = llm_meta.get("summary")
                meta.language = llm_meta.get("language", "en")
                meta.document_type = llm_meta.get("document_type", "other")
                meta.key_topics = llm_meta.get("key_topics", [])

        if not meta.title:
            meta.title = filename.rsplit(".", 1)[0] if "." in filename else filename

        return meta

    async def _llm_document_summary(self, text: str) -> Optional[Dict[str, Any]]:
        """Call LLM to generate document title, summary, topics."""
        excerpt = text[:3000]
        if len(text) > 3000:
            excerpt += f"\n\n[... truncated, total {len(text)} characters ...]"

        prompt = _DOCUMENT_SUMMARY_PROMPT.format(text_excerpt=excerpt)

        try:
            from litellm import acompletion

            response = await acompletion(
                model=self.enrichment_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
                timeout=30,
            )
            raw = response.choices[0].message.content.strip()
            raw = self._strip_json_fences(raw)
            return json.loads(raw)
        except Exception as exc:
            logger.warning("llm_document_summary_failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Chunk-level enrichment
    # ------------------------------------------------------------------

    def enrich_chunks_structural(
        self,
        chunks: List[TextChunk],
        *,
        parsed_text: str,
        filename: str,
        doc_id: int,
        doc_metadata: DocumentMetadata,
        knowledge_base_id: Optional[int] = None,
        knowledge_base_name: Optional[str] = None,
        knowledge_base_description: Optional[str] = None,
        workspace_id: Optional[int] = None,
        workspace_name: Optional[str] = None,
    ) -> List[ChunkMetadata]:
        """
        Build structural metadata for every chunk (no LLM calls).

        Extracts page numbers, section hierarchy, heading context,
        detects tables/code/lists, and attaches KB/workspace context.
        """
        headings = self._extract_headings(parsed_text)
        page_marker_re = re.compile(r"---\s*Page\s+(\d+)\s*---")

        # Pre-compute a page map from the full parsed text so we can
        # assign page numbers to chunks that fall between markers.
        page_map = self._build_page_offset_map(parsed_text, page_marker_re)

        enriched: List[ChunkMetadata] = []
        last_known_page: Optional[int] = None

        for chunk in chunks:
            text = chunk.text
            cm = ChunkMetadata(
                chunk_index=chunk.index,
                token_count=chunk.token_count,
                char_count=len(text),
                filename=filename,
                document_id=doc_id,
                document_title=doc_metadata.title,
                document_type=doc_metadata.document_type,
                knowledge_base_id=knowledge_base_id,
                knowledge_base_name=knowledge_base_name,
                knowledge_base_description=knowledge_base_description,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
            )

            # Page number(s) from --- Page N --- markers in chunk text
            page_matches = page_marker_re.findall(text)
            if page_matches:
                pages = sorted(set(int(p) for p in page_matches))
                cm.page_number = pages[0]
                if len(pages) > 1:
                    cm.page_range = [pages[0], pages[-1]]
                last_known_page = pages[-1]
            elif hasattr(chunk, "page_number") and chunk.page_number:
                cm.page_number = chunk.page_number
                last_known_page = chunk.page_number
            else:
                # Resolve from character offset in full text
                resolved = self._resolve_page_from_offset(page_map, chunk.start_char)
                if resolved is not None:
                    cm.page_number = resolved
                    last_known_page = resolved
                elif last_known_page is not None:
                    cm.page_number = last_known_page

            # Section/heading context
            heading_info = self._find_heading_for_position(headings, chunk.start_char)
            if heading_info:
                cm.section_title = heading_info["text"]
                cm.section_hierarchy = heading_info.get("hierarchy", [])
                cm.heading_context = heading_info["text"]
            elif hasattr(chunk, "section_title") and chunk.section_title:
                cm.section_title = chunk.section_title

            # Structural detection
            cm.has_table = self._detect_table(text)
            cm.has_code = self._detect_code(text)
            cm.has_list = self._detect_list(text)
            cm.chunk_type = self._infer_chunk_type(text, cm)

            enriched.append(cm)

        return enriched

    async def enrich_chunks_with_llm(
        self,
        chunks: List[TextChunk],
        chunk_metadata: List[ChunkMetadata],
        doc_title: str,
    ) -> List[ChunkMetadata]:
        """
        Enrich chunks with LLM-generated summaries, entities, and hypothetical questions.

        Only runs when enrichment_tier == FULL.
        Processes chunks in batches to minimize LLM calls.
        """
        if self.enrichment_tier != self.Tier.FULL:
            return chunk_metadata

        batch_size = self.max_chunks_per_llm_batch
        for batch_start in range(0, len(chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(chunks))
            batch_chunks = chunks[batch_start:batch_end]
            batch_meta = chunk_metadata[batch_start:batch_end]

            llm_results = await self._llm_chunk_enrichment(batch_chunks, doc_title)
            if not llm_results:
                continue

            result_map = {r.get("index", -1): r for r in llm_results}
            for i, cm in enumerate(batch_meta):
                global_idx = batch_start + i
                result = result_map.get(global_idx) or result_map.get(i)
                if not result:
                    continue
                cm.chunk_summary = result.get("summary")
                cm.key_entities = result.get("key_entities", [])[:8]
                cm.hypothetical_questions = result.get("hypothetical_questions", [])[:3]
                if result.get("chunk_type"):
                    cm.chunk_type = result["chunk_type"]

        return chunk_metadata

    async def _llm_chunk_enrichment(
        self,
        chunks: List[TextChunk],
        doc_title: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Batch-enrich chunks via a single LLM call."""
        chunks_text_parts = []
        for i, chunk in enumerate(chunks):
            preview = chunk.text[:600]
            if len(chunk.text) > 600:
                preview += "..."
            chunks_text_parts.append(f"--- Chunk {i} ---\n{preview}")

        prompt = _CHUNK_ENRICHMENT_PROMPT.format(
            doc_title=doc_title or "Unknown Document",
            chunks_text="\n\n".join(chunks_text_parts),
        )

        try:
            from litellm import acompletion

            response = await acompletion(
                model=self.enrichment_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000,
                timeout=60,
            )
            raw = response.choices[0].message.content.strip()
            raw = self._strip_json_fences(raw)
            return json.loads(raw)
        except Exception as exc:
            logger.warning("llm_chunk_enrichment_failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Contextual chunk headers (Anthropic-style contextual retrieval)
    # ------------------------------------------------------------------

    @staticmethod
    def build_contextual_header(cm: "ChunkMetadata") -> str:
        """
        Build a contextual header to prepend to chunk text before embedding.

        This is the core of contextual retrieval: the embedding model sees
        "This chunk is from [Document Title] in the [Section] section of the
        [KB Name] knowledge base, discussing [topics]." before the actual text.
        This dramatically improves embedding quality for ambiguous chunks.
        """
        parts = []
        if cm.document_title:
            parts.append(f"From document: {cm.document_title}")
        if cm.knowledge_base_name:
            parts.append(f"Knowledge base: {cm.knowledge_base_name}")
        if cm.section_title:
            parts.append(f"Section: {cm.section_title}")
        if cm.heading_context and cm.heading_context != cm.section_title:
            parts.append(f"Topic: {cm.heading_context}")
        if cm.page_number:
            parts.append(f"Page {cm.page_number}")
        if cm.chunk_type and cm.chunk_type != "text":
            parts.append(f"Content type: {cm.chunk_type}")
        if not parts:
            return ""
        return " | ".join(parts) + "\n\n"

    def build_embedding_text(self, chunk_text: str, cm: "ChunkMetadata") -> str:
        """
        Produce the text that gets embedded — original chunk with contextual header.

        When contextual_headers is True, prepends document/section context so the
        embedding vector captures the broader meaning, not just the raw text.
        """
        if not self.contextual_headers:
            return chunk_text
        header = self.build_contextual_header(cm)
        if not header:
            return chunk_text
        return header + chunk_text

    # ------------------------------------------------------------------
    # Page number resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _build_page_offset_map(
        text: str, page_marker_re: re.Pattern
    ) -> List[Tuple[int, int]]:
        """Build a sorted list of (char_offset, page_number) from page markers."""
        entries: List[Tuple[int, int]] = []
        for m in page_marker_re.finditer(text):
            entries.append((m.start(), int(m.group(1))))
        return entries

    @staticmethod
    def _resolve_page_from_offset(
        page_map: List[Tuple[int, int]], char_offset: int
    ) -> Optional[int]:
        """Find the page number for a character offset using binary search."""
        if not page_map:
            return None
        lo, hi = 0, len(page_map) - 1
        result = None
        while lo <= hi:
            mid = (lo + hi) // 2
            if page_map[mid][0] <= char_offset:
                result = page_map[mid][1]
                lo = mid + 1
            else:
                hi = mid - 1
        return result

    # ------------------------------------------------------------------
    # Heading / section extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_headings(text: str) -> List[Dict[str, Any]]:
        """Extract headings and their positions from text for section hierarchy."""
        headings: List[Dict[str, Any]] = []
        hierarchy: List[str] = []

        heading_patterns = [
            (re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE), "markdown"),
            (re.compile(r"^([A-Z][A-Z\s]{2,60}[A-Z])$", re.MULTILINE), "allcaps"),
            (re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$", re.MULTILINE), "numbered"),
        ]

        for pattern, ptype in heading_patterns:
            for match in pattern.finditer(text):
                if ptype == "markdown":
                    level = len(match.group(1))
                    title = match.group(2).strip()
                elif ptype == "allcaps":
                    level = 1
                    title = match.group(1).strip()
                elif ptype == "numbered":
                    level = match.group(1).count(".") + 1
                    title = match.group(2).strip()
                else:
                    continue

                headings.append({
                    "text": title,
                    "level": level,
                    "position": match.start(),
                    "type": ptype,
                })

        headings.sort(key=lambda h: h["position"])

        # Build hierarchy chains
        stack: List[Tuple[int, str]] = []
        for heading in headings:
            level = heading["level"]
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading["text"]))
            heading["hierarchy"] = [s[1] for s in stack]

        return headings

    @staticmethod
    def _find_heading_for_position(
        headings: List[Dict[str, Any]], char_position: int
    ) -> Optional[Dict[str, Any]]:
        """Find the nearest heading that precedes a character position."""
        result = None
        for heading in headings:
            if heading["position"] <= char_position:
                result = heading
            else:
                break
        return result

    # ------------------------------------------------------------------
    # Structural detectors
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_table(text: str) -> bool:
        pipe_rows = len(re.findall(r"^\s*\|.*\|", text, re.MULTILINE))
        if pipe_rows >= 2:
            return True
        tab_rows = len(re.findall(r"\t.*\t", text))
        return tab_rows >= 3

    @staticmethod
    def _detect_code(text: str) -> bool:
        if "```" in text:
            return True
        indented = len(re.findall(r"^    \S", text, re.MULTILINE))
        return indented >= 3

    @staticmethod
    def _detect_list(text: str) -> bool:
        bullet_items = len(re.findall(r"^[\s]*[-•*]\s", text, re.MULTILINE))
        numbered_items = len(re.findall(r"^[\s]*\d+[.)]\s", text, re.MULTILINE))
        return (bullet_items + numbered_items) >= 3

    @staticmethod
    def _infer_chunk_type(text: str, cm: "ChunkMetadata") -> str:
        if cm.has_table:
            return "table"
        if cm.has_code:
            return "code"
        if cm.has_list:
            return "list"
        stripped = text.strip()
        if len(stripped) < 100 and not stripped.endswith("."):
            return "header"
        return "text"

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_json_fences(raw: str) -> str:
        """Remove markdown JSON code fences if present."""
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        return raw.strip()
