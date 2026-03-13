"""
RAGFlow Service - HTTP client wrapper for RAGFlow API.

Provides multi-tenant RAG capabilities through RAGFlow:
- Dataset (knowledge base) management
- Document upload and parsing
- Semantic retrieval
- Chat with documents
"""

import logging
import httpx
import asyncio
import json
import random
import re
from typing import Optional, List, Dict, Any, BinaryIO, AsyncIterator
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.core.config import get_settings
from src.models.ragflow_domain import (
    RAGFlowDomain, RAGFlowDocument, RAGFlowConversation, RAGFlowMessage,
    RAGFlowDomainStatus, RAGFlowDocumentStatus, RAGFlowParserType
)

logger = logging.getLogger(__name__)


class RAGFlowError(Exception):
    """RAGFlow API error."""
    def __init__(self, message: str, code: Optional[int] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details


class RAGFlowService:
    """
    Service for interacting with RAGFlow API.
    
    Handles all RAGFlow operations including dataset management,
    document upload/parsing, and retrieval.
    """
    
    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.settings = get_settings()
        self.base_url = self.settings.ragflow_base_url.rstrip('/')
        self.api_key = api_key or self.settings.ragflow_api_key
        
        if not self.api_key:
            logger.warning("RAGFlow API key not configured - some operations may fail")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for RAGFlow API."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _should_retry_status(self, status_code: int) -> bool:
        """Return True for transient HTTP status codes."""
        return status_code in {429, 500, 502, 503, 504}

    def _should_retry_error_message(self, message: str) -> bool:
        """Heuristic for retryable RAGFlow errors (OpenSearch/Elasticsearch boot)."""
        if not message:
            return False
        lowered = message.lower()
        retry_terms = (
            "connectionerror",
            "connection refused",
            "connection reset",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "no living connections",
            "cluster block",
            "elasticsearch",
            "opensearch",
            "aoss",
        )
        return any(term in lowered for term in retry_terms)

    def _backoff_delay(self, attempt: int, base_delay: float, retry_after: Optional[str] = None) -> float:
        """Exponential backoff with jitter and optional Retry-After."""
        delay = base_delay * (2 ** attempt)
        delay += random.uniform(0, base_delay * 0.25)
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
        return delay

    def _parse_json_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Parse JSON response or raise a RAGFlowError with context."""
        try:
            return response.json()
        except ValueError:
            snippet = (response.text or "")[:500]
            raise RAGFlowError(
                message="Invalid JSON response from RAGFlow",
                code=response.status_code,
                details={"body": snippet}
            )
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> Dict[str, Any]:
        """
        Make HTTP request to RAGFlow API with automatic retry for transient failures.
        
        Retries on connection errors (e.g., when Elasticsearch is starting up)
        with exponential backoff.
        """
        url = f"{self.base_url}/api/v1{endpoint}"
        last_error: Optional[RAGFlowError] = None
        
        for attempt in range(max_retries):
            headers = self._get_headers()
            
            # For file uploads, don't set Content-Type (let httpx handle multipart)
            if files:
                headers.pop("Content-Type", None)
            
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=json_data,
                        files=files,
                        params=params
                    )
            except httpx.RequestError as e:
                # Network-level connection errors - retry these
                last_error = RAGFlowError(f"Request failed: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = self._backoff_delay(attempt, retry_delay)
                    logger.warning(
                        f"RAGFlow request error (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.error(f"RAGFlow request error after {max_retries} attempts: {e}")
                raise last_error
            
            # Handle HTTP status codes before JSON parsing
            if response.status_code >= 400:
                body = response.text or ""
                if self._should_retry_status(response.status_code) and attempt < max_retries - 1:
                    wait_time = self._backoff_delay(attempt, retry_delay, response.headers.get("Retry-After"))
                    logger.warning(
                        f"RAGFlow HTTP {response.status_code} (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time:.1f}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                raise RAGFlowError(
                    message=f"HTTP {response.status_code}: {body[:500]}",
                    code=response.status_code,
                    details={"body": body[:2000]}
                )
            
            data = self._parse_json_response(response)
            
            # RAGFlow returns {"code": 0, "data": {...}} for success
            error_msg = data.get("message", "")
            if data.get("code", 0) != 0:
                last_error = RAGFlowError(
                    message=error_msg or "Unknown RAGFlow error",
                    code=data.get("code"),
                    details=data
                )
                if self._should_retry_error_message(error_msg) and attempt < max_retries - 1:
                    wait_time = self._backoff_delay(attempt, retry_delay)
                    logger.warning(
                        f"RAGFlow connection error (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time:.1f}s: {error_msg[:120]}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise last_error
            
            return data.get("data", data)
        
        # Should not reach here, but just in case
        raise last_error or RAGFlowError("Request failed after retries")

    def _get_managed_prompt(
        self,
        customer_id: Optional[str],
        prompt_type: str,
        prompt_domain: Optional[str] = None
    ) -> Optional[str]:
        """Load a managed prompt for RAGFlow, if available."""
        if not customer_id:
            return None
        domain = prompt_domain or self.settings.ragflow_prompt_domain
        try:
            from src.utils.prompt_loader import get_prompt
            return get_prompt(customer_id, domain, prompt_type)
        except Exception as e:
            logger.debug(f"Could not load managed prompt {prompt_type}: {e}")
            return None

    def _render_prompt_template(self, template: str, **vars: str) -> str:
        """
        Render a prompt template safely.
        Supports {question} and {context} style placeholders.
        Unknown placeholders are left as-is.
        """
        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        try:
            return template.format_map(_SafeDict(**{k: v for k, v in vars.items() if v is not None}))
        except Exception:
            rendered = template
            for k, v in vars.items():
                if v is None:
                    continue
                rendered = rendered.replace("{" + k + "}", str(v))
            return rendered

    async def _rewrite_query(
        self,
        question: str,
        customer_id: Optional[str],
        prompt_domain: Optional[str] = None
    ) -> str:
        """Rewrite the user's question for retrieval using a managed prompt."""
        if not self.settings.ragflow_query_rewrite_enabled:
            return question
        prompt = self._get_managed_prompt(customer_id, "query_rewrite", prompt_domain)
        if not prompt:
            return question

        rendered = self._render_prompt_template(prompt, question=question, query=question)
        try:
            from litellm import acompletion
            model = self.settings.default_llm_model
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": rendered}],
                temperature=0,
                max_tokens=256,
            )
            rewritten = (response.choices[0].message.content or "").strip()

            if not rewritten or len(rewritten) < 3:
                return question
            if len(rewritten) > 5000:
                return question

            rewritten = rewritten.strip().strip("`").strip('"').strip("'")

            # Heuristic parsing: handle bullet lists or numbered outputs
            lines = [l.strip() for l in rewritten.splitlines() if l.strip()]

            def normalize_line(line: str) -> str:
                line = re.sub(r"^\s*[-•]\s*", "", line)
                line = re.sub(r"^\s*\d+\s*[\).\-\:]\s*", "", line)
                return line.strip()

            skip_prefixes = (
                "here are",
                "goal",
                "output",
                "instructions",
                "rewrite",
                "you are",
                "return",
                "format",
                "original question",
                "rewritten query",
                "queries",
            )

            candidates: list[str] = []
            for raw in lines:
                l = normalize_line(raw)
                low = l.lower()
                if not l:
                    continue
                if low.startswith(skip_prefixes):
                    continue
                if "provide" in low and "query" in low:
                    continue
                if len(l) < 6:
                    continue
                candidates.append(l)

            if not candidates:
                return question

            candidates = sorted(candidates, key=lambda s: len(s), reverse=True)
            merged = " ; ".join(candidates[:3]).strip()
            merged = merged[:512]
            return merged or question
        except Exception as e:
            logger.warning(f"Query rewrite failed, using original question: {e}")
            return question

    def _normalize_similarity(self, value: Any) -> float:
        """Normalize similarity to 0-1 float."""
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        if score > 1.0 and score <= 100.0:
            score = score / 100.0
        if score < 0.0:
            return 0.0
        return score

    def _clean_content(self, text: str) -> str:
        """Clean chunk content for consistent prompting."""
        if not text:
            return ""
        text = text.replace("\x00", "")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _chunk_signature(self, chunk: Dict[str, Any]) -> str:
        """Build a stable signature for deduping chunks."""
        doc_id = chunk.get("document_id") or chunk.get("document_name") or ""
        content = (chunk.get("content") or "")[:200]
        return f"{doc_id}::{content}"

    def _post_process_chunks(
        self,
        chunks: List[Dict[str, Any]],
        similarity_threshold: Optional[float]
    ) -> List[Dict[str, Any]]:
        """Normalize, filter, and dedupe retrieved chunks."""
        cleaned: List[Dict[str, Any]] = []
        for chunk in chunks or []:
            content = self._clean_content(chunk.get("content", ""))
            if not content:
                continue
            similarity = self._normalize_similarity(chunk.get("similarity", 0.0))
            if similarity_threshold is not None and similarity < similarity_threshold:
                continue

            doc_name = chunk.get("document_name") or chunk.get("doc_name") or "Unknown"
            metadata = chunk.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}

            cleaned.append({
                **chunk,
                "content": content,
                "similarity": similarity,
                "document_name": doc_name,
                "metadata": metadata,
            })

        # Dedupe by document + content prefix (keep highest similarity)
        cleaned.sort(key=lambda c: c.get("similarity", 0.0), reverse=True)
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for chunk in cleaned:
            sig = self._chunk_signature(chunk)
            if sig in seen:
                continue
            seen.add(sig)
            deduped.append(chunk)
        return deduped

    def _format_chunk_source(self, chunk: Dict[str, Any], index: int) -> str:
        """Build a human-readable source label for a chunk."""
        doc_name = chunk.get("document_name") or "Unknown"
        meta = chunk.get("metadata") or {}

        page_start = meta.get("page_start") or meta.get("page") or meta.get("page_number")
        page_end = meta.get("page_end")
        page_str = None
        if page_start and page_end and page_end != page_start:
            page_str = f"pp. {page_start}-{page_end}"
        elif page_start:
            page_str = f"p. {page_start}"

        section = meta.get("section") or meta.get("section_path") or meta.get("heading")
        if isinstance(section, list):
            section = " > ".join([str(s) for s in section if s])

        parts = [doc_name]
        if page_str:
            parts.append(page_str)
        if section:
            parts.append(str(section))
        return " | ".join(parts) if parts else f"Source {index}"

    def _build_context(self, chunks: List[Dict[str, Any]], max_chars: int) -> str:
        """Build a context block with numbered sources and size limits."""
        if not chunks:
            return ""

        max_chars = max(2000, max_chars)
        per_chunk_limit = max(800, int(max_chars / max(1, min(len(chunks), 6))))
        context_parts = []
        total = 0

        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            content = content[:per_chunk_limit].strip()
            if not content:
                continue
            source_label = self._format_chunk_source(chunk, i)
            part = f"[{i}] {source_label}\n{content}"
            if total + len(part) > max_chars and context_parts:
                break
            context_parts.append(part)
            total += len(part)

        return "\n\n".join(context_parts)

    async def _rerank_chunks(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        keep: int,
        customer_id: Optional[str],
        prompt_domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """LLM rerank retrieved chunks, with robust fallback."""
        if not self.settings.ragflow_rerank_enabled:
            return chunks[:keep]

        if len(chunks) <= keep:
            return chunks

        # Cap keep based on settings
        keep = min(keep, self.settings.ragflow_rerank_keep)

        items = "\n\n".join([
            f"[{i+1}] {chunk.get('document_name', 'Unknown')}\n{chunk.get('content', '')[:1200]}"
            for i, chunk in enumerate(chunks)
        ])

        prompt = f"""
You are reranking retrieved snippets for a RAG system.

User question:
{query}

Snippets:
{items}

Task:
Select the {keep} snippets that are most useful to answer the question.
Return ONLY valid JSON in this exact format:
{{"keep":[1,2,3]}}

Rules:
- Indices must be unique and between 1 and {len(chunks)}.
- Prefer snippets that directly answer the question.
- Prefer authoritative definitions, requirements, or factual statements.
"""

        try:
            from litellm import acompletion
            model = self.settings.default_llm_model
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200,
            )

            text = (response.choices[0].message.content or "").strip()
            keep_indices: List[int] = []

            try:
                data = json.loads(text)
                keep_indices = data.get("keep", [])
            except json.JSONDecodeError:
                # Fallback: parse integers from the response
                keep_indices = [int(x) for x in re.findall(r"\b\d+\b", text)]

            keep_indices = [
                int(i) for i in keep_indices
                if isinstance(i, (int, str)) and 1 <= int(i) <= len(chunks)
            ]

            # Unique preserve order
            seen = set()
            ordered = []
            for idx in keep_indices:
                if idx in seen:
                    continue
                seen.add(idx)
                ordered.append(idx)

            ordered = ordered[:keep]
            if not ordered:
                return chunks[:keep]

            reranked = [chunks[i - 1] for i in ordered]
            logger.info(f"RAGFlow rerank: kept {len(reranked)}/{len(chunks)}")
            return reranked
        except Exception as e:
            logger.warning(f"RAGFlow rerank failed, using top-k fallback: {e}")
            return chunks[:keep]
    
    # ==================== Health Check ====================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check RAGFlow service health."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/v1/health")
                return {"status": "healthy", "response": response.json()}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    # ==================== Dataset (Domain) Management ====================
    
    async def create_dataset(
        self,
        name: str,
        description: Optional[str] = None,
        language: str = "English",
        embedding_model: Optional[str] = None,
        parser_type: RAGFlowParserType = RAGFlowParserType.NAIVE,
        chunk_token_count: Optional[int] = None,
        task_page_size: Optional[int] = None,
        custom_vlm_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new RAGFlow dataset (knowledge base).
        
        Args:
            name: Dataset name (must be unique)
            description: Optional description
            language: Document language
            embedding_model: Embedding model (default from config)
            parser_type: Document parser type
            chunk_token_count: Tokens per chunk (default from config)
            task_page_size: Pages per parsing task (lower = more parallelism, default 4 for GPT-4o)
            custom_vlm_model: Custom VLM model ID for layout recognition
        
        Returns:
            Dataset info including ID
        """
        embedding_model = embedding_model or self.settings.ragflow_default_embedding_model
        chunk_token_count = chunk_token_count or self.settings.ragflow_default_chunk_size
        
        # Map parser type to RAGFlow layout_recognize format
        parser_config = {}
        if parser_type == RAGFlowParserType.GPT4O:
            parser_config["layout_recognize"] = "gpt-4o@OpenAI"
            # Use smaller page batches for GPT-4o to maximize parallelism
            parser_config["task_page_size"] = task_page_size or 4
        elif parser_type == RAGFlowParserType.DEEPDOC:
            parser_config["layout_recognize"] = "deepdoc"
            parser_config["task_page_size"] = task_page_size or 8
        elif parser_type == RAGFlowParserType.CUSTOM_VLM:
            if not custom_vlm_model:
                raise RAGFlowError("custom_vlm_model is required for custom-vlm parser type")
            parser_config["layout_recognize"] = custom_vlm_model
            parser_config["task_page_size"] = task_page_size or 4
        else:
            # NAIVE uses default (no layout recognition) - can use larger batches
            if task_page_size:
                parser_config["task_page_size"] = task_page_size
        
        payload = {
            "name": name,
            "description": description or "",
            "language": language,
            "embedding_model": embedding_model,
            "parser_config": {
                **parser_config,
                "chunk_token_num": chunk_token_count
            }
        }
        
        logger.info(f"Creating RAGFlow dataset: {name}")
        return await self._request("POST", "/datasets", json_data=payload)
    
    async def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get dataset details by ID (searches in list since RAGFlow doesn't support single GET)."""
        try:
            result = await self._request("GET", "/datasets", params={"page": 1, "page_size": 1000})
            datasets = result if isinstance(result, list) else result.get("data", result)
            
            # Handle if result is a list directly
            if isinstance(datasets, list):
                for ds in datasets:
                    if ds.get("id") == dataset_id:
                        return ds
            
            return None
        except RAGFlowError as e:
            logger.warning(f"Failed to get dataset {dataset_id}: {e}")
            return None
    
    async def list_datasets(self, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """List all datasets."""
        params = {"page": page, "page_size": page_size}
        return await self._request("GET", "/datasets", params=params)
    
    async def delete_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """Delete a dataset."""
        return await self._request("DELETE", f"/datasets/{dataset_id}")
    
    async def update_dataset(
        self,
        dataset_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parser_config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Update dataset configuration."""
        payload = {}
        if name:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if parser_config:
            payload["parser_config"] = parser_config
        
        return await self._request("PUT", f"/datasets/{dataset_id}", json_data=payload)
    
    # ==================== Document Management ====================
    
    async def upload_document(
        self,
        dataset_id: str,
        file_content: bytes,
        filename: str,
        run_immediately: bool = True
    ) -> Dict[str, Any]:
        """
        Upload a document to a dataset.
        
        Args:
            dataset_id: Target dataset ID
            file_content: File bytes
            filename: Original filename
            run_immediately: Start parsing immediately
        
        Returns:
            Document info including ID
        """
        files = {"file": (filename, file_content)}
        params = {"run": str(run_immediately).lower()} if run_immediately else {}
        
        logger.info(f"Uploading document '{filename}' to dataset {dataset_id}")
        return await self._request(
            "POST", 
            f"/datasets/{dataset_id}/documents",
            files=files,
            params=params,
            timeout=120.0  # Longer timeout for uploads
        )
    
    async def list_documents(
        self,
        dataset_id: str,
        page: int = 1,
        page_size: int = 100,
        keywords: Optional[str] = None
    ) -> Dict[str, Any]:
        """List documents in a dataset."""
        params = {"page": page, "page_size": page_size}
        if keywords:
            params["keywords"] = keywords
        
        return await self._request("GET", f"/datasets/{dataset_id}/documents", params=params)
    
    async def get_document(self, dataset_id: str, document_id: str) -> Dict[str, Any]:
        """Get document details including parsing status."""
        docs = await self.list_documents(dataset_id, page_size=1000)
        for doc in docs.get("docs", []):
            if doc.get("id") == document_id:
                return doc
        raise RAGFlowError(f"Document {document_id} not found")
    
    async def delete_document(self, dataset_id: str, document_id: str) -> Dict[str, Any]:
        """Delete a document from a dataset."""
        return await self._request(
            "DELETE", 
            f"/datasets/{dataset_id}/documents",
            json_data={"ids": [document_id]}
        )
    
    async def parse_documents(
        self,
        dataset_id: str,
        document_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Trigger parsing for documents.
        
        Use this if documents were uploaded without run_immediately=True.
        """
        return await self._request(
            "POST",
            f"/datasets/{dataset_id}/chunks",
            json_data={"document_ids": document_ids}
        )
    
    async def stop_parsing(self, dataset_id: str, document_ids: List[str]) -> Dict[str, Any]:
        """Stop parsing for documents."""
        return await self._request(
            "DELETE",
            f"/datasets/{dataset_id}/chunks",
            json_data={"document_ids": document_ids}
        )
    
    # ==================== Retrieval ====================
    
    async def retrieve(
        self,
        dataset_ids: List[str],
        query: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = 0.2,
        rerank: bool = True,
        customer_id: Optional[str] = None,
        prompt_domain: Optional[str] = None,
        allow_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            dataset_ids: List of dataset IDs to search
            query: Search query
            top_k: Number of chunks to return
            similarity_threshold: Minimum similarity score (0-1)
            rerank: Whether to rerank results
            customer_id: Optional tenant for prompt management
            prompt_domain: Optional prompt domain override
            allow_fallback: Retry with a lower similarity threshold if empty
        
        Returns:
            Retrieved chunks with content and metadata
        """
        if not dataset_ids:
            return {"chunks": []}

        effective_top_k = max(1, top_k)
        effective_top_k = min(effective_top_k, self.settings.ragflow_max_retrieve_k)

        if similarity_threshold is not None:
            effective_threshold = max(0.0, min(1.0, similarity_threshold))
        else:
            effective_threshold = None

        retrieval_query = await self._rewrite_query(query, customer_id, prompt_domain)

        candidate_k = effective_top_k
        if rerank:
            candidate_k = max(candidate_k, self.settings.ragflow_rerank_keep)
            candidate_k = max(candidate_k, min(effective_top_k * 2, self.settings.ragflow_max_retrieve_k))
            candidate_k = min(candidate_k, self.settings.ragflow_max_retrieve_k)

        payload = {
            "dataset_ids": dataset_ids,
            "query": retrieval_query,
            "top_k": candidate_k,
            "similarity_threshold": effective_threshold,
            "rerank": False
        }

        logger.info(
            f"RAGFlow retrieval: query='{query[:80]}', rewritten='{retrieval_query[:80]}', "
            f"datasets={dataset_ids}, top_k={candidate_k}, threshold={effective_threshold}"
        )

        # Use more retries for retrieval since OpenSearch can be slow to warm up
        result = await self._request(
            "POST",
            "/retrieval",
            json_data=payload,
            timeout=90.0,
            max_retries=5,
            retry_delay=3.0
        )

        chunks = self._post_process_chunks(result.get("chunks", []), effective_threshold)

        if not chunks and allow_fallback and effective_threshold is not None:
            fallback_threshold = self.settings.ragflow_fallback_similarity_threshold
            if fallback_threshold < effective_threshold:
                logger.info(
                    f"RAGFlow retrieval empty, retrying with fallback threshold {fallback_threshold}"
                )
                payload["similarity_threshold"] = fallback_threshold
                fallback_result = await self._request(
                    "POST",
                    "/retrieval",
                    json_data=payload,
                    timeout=90.0,
                    max_retries=5,
                    retry_delay=3.0
                )
                chunks = self._post_process_chunks(
                    fallback_result.get("chunks", []),
                    fallback_threshold
                )

        if rerank and chunks:
            chunks = await self._rerank_chunks(
                query=query,
                chunks=chunks,
                keep=effective_top_k,
                customer_id=customer_id,
                prompt_domain=prompt_domain
            )
        else:
            chunks = chunks[:effective_top_k]

        return {
            "query": query,
            "retrieval_query": retrieval_query,
            "chunks": chunks,
            "total_chunks": len(chunks)
        }
    
    # ==================== Chat ====================
    
    async def chat(
        self,
        dataset_ids: List[str],
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.2,
        stream: bool = False,
        customer_id: Optional[str] = None,
        prompt_domain: Optional[str] = None,
        rerank: bool = True
    ) -> Dict[str, Any]:
        """
        Chat with documents using RAG.
        
        Uses RAGFlow's /retrieval endpoint to get relevant chunks,
        then generates an answer using the configured LLM.
        
        Args:
            dataset_ids: Dataset IDs to use for retrieval
            question: User question
            conversation_history: Previous messages [{role, content}, ...]
            top_k: Number of chunks to retrieve
            similarity_threshold: Minimum similarity
            stream: Whether to stream response (not supported yet)
            customer_id: Optional tenant for prompt management
            prompt_domain: Optional prompt domain override
            rerank: Whether to rerank results
        
        Returns:
            Dict with 'answer' and 'chunks' keys
        """
        # Step 1: Retrieve relevant chunks (with rewrite + rerank)
        retrieval_result = await self.retrieve(
            dataset_ids=dataset_ids,
            query=question,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            rerank=rerank,
            customer_id=customer_id,
            prompt_domain=prompt_domain
        )
        chunks = retrieval_result.get("chunks", [])

        logger.info(f"RAGFlow retrieval result: {len(chunks)} chunks found")

        if not chunks:
            return {
                "answer": "I couldn't find any relevant information in the documents to answer your question.",
                "chunks": []
            }

        # Step 2: Build context from retrieved chunks
        context = self._build_context(chunks, self.settings.ragflow_max_context_chars)
        logger.info(f"Built context with {len(chunks)} chunks, total length: {len(context)} chars")

        # Step 3: Generate answer using LiteLLM
        from litellm import acompletion

        system_prompt = self._get_managed_prompt(customer_id, "system", prompt_domain)
        if not system_prompt:
            system_prompt = """You are a retrieval-augmented assistant.
- Answer using ONLY the provided context
- If the answer isn't in the context, say you don't know
- Cite sources like [1], [2] when stating facts
- Be concise and accurate"""

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        base_user_prompt = f"""Question:
{question}

Context (cite [1], [2], etc.):
{context}
"""

        synthesis_prompt = self._get_managed_prompt(customer_id, "synthesis", prompt_domain)
        if synthesis_prompt:
            synthesis_instructions = self._render_prompt_template(
                synthesis_prompt,
                question=question,
                context=context,
                query=question
            ).strip()
            user_prompt = f"""{synthesis_instructions}

{base_user_prompt}

Provide a clear, well-cited answer:"""
        else:
            user_prompt = f"""{base_user_prompt}

Provide a clear, well-cited answer:"""

        messages.append({"role": "user", "content": user_prompt})

        try:
            model = self.settings.default_llm_model or "gpt-4o-mini"
            response = await acompletion(
                model=model,
                messages=messages,
                max_tokens=1200,
                temperature=0
            )
            answer = response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM completion error: {e}")
            # Fallback: return chunks summary with citations
            fallback_lines = ["I couldn't generate a full answer. Relevant excerpts:"]
            for i, chunk in enumerate(chunks[:3], 1):
                source = self._format_chunk_source(chunk, i)
                preview = chunk.get("content", "")[:300]
                fallback_lines.append(f"[{i}] {source}\n{preview}")
            answer = "\n\n".join(fallback_lines)

        return {
            "answer": answer,
            "chunks": chunks
        }
    
    async def chat_stream(
        self,
        dataset_ids: List[str],
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.2
    ) -> AsyncIterator[str]:
        """
        Stream chat response.
        
        Yields chunks of the response as they're generated.
        """
        url = f"{self.base_url}/api/v1/chat"
        payload = {
            "dataset_ids": dataset_ids,
            "question": question,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "stream": True
        }
        
        if conversation_history:
            payload["history"] = conversation_history
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                url,
                headers=self._get_headers(),
                json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        yield line[5:].strip()
    
    # ==================== Domain CRUD (Database + RAGFlow) ====================
    
    async def create_domain(
        self,
        customer_id: str,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        icon: str = "folder",
        color: str = "violet",
        parser_type: RAGFlowParserType = RAGFlowParserType.NAIVE,
        embedding_model: Optional[str] = None,
        chunk_token_count: Optional[int] = None,
        task_page_size: Optional[int] = None,
        user_id: Optional[int] = None,
        custom_vlm_model: Optional[str] = None
    ) -> RAGFlowDomain:
        """
        Create a new RAG domain (both in DB and RAGFlow).
        
        Creates a local domain record and a corresponding RAGFlow dataset.
        Domain starts in PENDING status until documents are uploaded.
        
        Args:
            task_page_size: Pages per parsing task (lower = more parallelism).
                           Defaults: 4 for GPT-4o, 8 for DeepDoc, 12 for Naive.
        """
        # Create unique dataset name for RAGFlow
        ragflow_name = f"{customer_id}_{name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Create dataset in RAGFlow
        try:
            dataset = await self.create_dataset(
                name=ragflow_name,
                description=description,
                parser_type=parser_type,
                embedding_model=embedding_model,
                chunk_token_count=chunk_token_count,
                task_page_size=task_page_size,
                custom_vlm_model=custom_vlm_model
            )
            ragflow_dataset_id = dataset.get("id")
            logger.info(f"Created RAGFlow dataset: {ragflow_dataset_id}")
        except RAGFlowError as e:
            logger.error(f"Failed to create RAGFlow dataset: {e}")
            raise
        
        # Create local domain record - starts as PENDING per spec
        domain = RAGFlowDomain(
            customer_id=customer_id,
            name=name,
            display_name=display_name,
            description=description,
            icon=icon,
            color=color,
            ragflow_dataset_id=ragflow_dataset_id,
            ragflow_dataset_name=ragflow_name,
            parser_type=parser_type,
            parser_config={"layout_recognize": custom_vlm_model} if custom_vlm_model else None,
            embedding_model=embedding_model or self.settings.ragflow_default_embedding_model,
            chunk_token_count=chunk_token_count or self.settings.ragflow_default_chunk_size,
            status=RAGFlowDomainStatus.PENDING,
            created_by_user_id=user_id
        )
        
        self.db.add(domain)
        self.db.commit()
        self.db.refresh(domain)
        
        logger.info(f"Created domain {customer_id}/{name} with RAGFlow dataset {ragflow_dataset_id}")
        return domain
    
    async def get_domain(self, domain_id: int, customer_id: str) -> Optional[RAGFlowDomain]:
        """Get a domain by ID."""
        return self.db.query(RAGFlowDomain).filter(
            RAGFlowDomain.id == domain_id,
            RAGFlowDomain.customer_id == customer_id
        ).first()
    
    async def get_domain_by_name(self, name: str, customer_id: str) -> Optional[RAGFlowDomain]:
        """Get a domain by name."""
        return self.db.query(RAGFlowDomain).filter(
            RAGFlowDomain.name == name,
            RAGFlowDomain.customer_id == customer_id
        ).first()
    
    async def list_domains(
        self,
        customer_id: str,
        status: Optional[RAGFlowDomainStatus] = None,
        limit: int = 100,
        offset: int = 0,
        sync_stats: bool = True
    ) -> List[RAGFlowDomain]:
        """List domains for a customer, optionally syncing stats from RAGFlow."""
        query = self.db.query(RAGFlowDomain).filter(
            RAGFlowDomain.customer_id == customer_id
        )
        
        if status:
            query = query.filter(RAGFlowDomain.status == status)
        
        domains = query.order_by(RAGFlowDomain.created_at.desc()).offset(offset).limit(limit).all()
        
        # Sync stats from RAGFlow for ALL domains with a dataset ID
        if sync_stats:
            for domain in domains:
                if domain.ragflow_dataset_id:
                    try:
                        # Get dataset info from RAGFlow
                        dataset = await self.get_dataset(domain.ragflow_dataset_id)
                        if dataset:
                            new_chunk_count = dataset.get("chunk_count", 0)
                            new_doc_count = dataset.get("document_count", 0)
                            new_token_count = dataset.get("token_num", 0)
                            
                            # Always update from RAGFlow (source of truth)
                            domain.chunk_count = new_chunk_count
                            domain.document_count = new_doc_count
                            domain.total_tokens = new_token_count
                            domain.last_sync_at = datetime.utcnow()
                            
                            # Update domain status based on document states (per spec)
                            await self._update_domain_status(domain)
                            
                            logger.info(f"Synced domain {domain.id}: docs={new_doc_count}, chunks={new_chunk_count}, status={domain.status.value}")
                    except RAGFlowError as e:
                        logger.warning(f"Could not sync stats for domain {domain.id}: {e}")
            
            # Commit all updates
            try:
                self.db.commit()
            except Exception as e:
                logger.error(f"Failed to commit domain stats: {e}")
                self.db.rollback()
        
        return domains
    
    async def _update_domain_status(self, domain: RAGFlowDomain) -> None:
        """
        Update domain status based on document states (per spec).
        
        Status transitions:
        - pending: No documents yet
        - indexing: Documents being processed
        - ready: All documents processed successfully, chunks available
        - failed: All documents failed or RAGFlow collection failed
        """
        # Get document statuses
        docs = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == domain.id
        ).all()
        
        if not docs:
            # No documents uploaded yet
            domain.status = RAGFlowDomainStatus.PENDING
            domain.last_error = None
            return
        
        completed = sum(1 for d in docs if d.status == RAGFlowDocumentStatus.COMPLETED)
        pending_or_parsing = sum(1 for d in docs if d.status in [RAGFlowDocumentStatus.PENDING, RAGFlowDocumentStatus.PARSING])
        failed = sum(1 for d in docs if d.status == RAGFlowDocumentStatus.FAILED)
        
        if pending_or_parsing > 0:
            # Still processing documents
            domain.status = RAGFlowDomainStatus.INDEXING
            domain.last_error = None
        elif completed > 0 and domain.chunk_count > 0:
            # At least some documents completed and chunks exist
            domain.status = RAGFlowDomainStatus.READY
            domain.last_error = None
        elif failed == len(docs):
            # All documents failed
            domain.status = RAGFlowDomainStatus.FAILED
            # Get error from first failed doc
            failed_doc = next((d for d in docs if d.status == RAGFlowDocumentStatus.FAILED), None)
            domain.last_error = failed_doc.processing_error if failed_doc else "All documents failed to process"
        elif completed > 0:
            # Some completed but no chunks yet (may still be indexing in RAGFlow)
            domain.status = RAGFlowDomainStatus.INDEXING
        else:
            # Edge case: some combination we haven't covered
            domain.status = RAGFlowDomainStatus.PENDING
    
    async def delete_domain(self, domain_id: int, customer_id: str) -> bool:
        """Delete a domain (both from DB and RAGFlow)."""
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            return False
        
        # Delete from RAGFlow
        if domain.ragflow_dataset_id:
            try:
                await self.delete_dataset(domain.ragflow_dataset_id)
                logger.info(f"Deleted RAGFlow dataset: {domain.ragflow_dataset_id}")
            except RAGFlowError as e:
                logger.warning(f"Failed to delete RAGFlow dataset: {e}")
        
        # Delete from DB
        self.db.delete(domain)
        self.db.commit()
        
        return True
    
    # ==================== Document CRUD (Database + RAGFlow) ====================
    
    async def upload_domain_document(
        self,
        domain_id: int,
        customer_id: str,
        file_content: bytes,
        filename: str,
        file_size: int,
        mime_type: str,
        user_id: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> RAGFlowDocument:
        """
        Upload a document to a domain.
        
        Uploads to RAGFlow and creates local tracking record.
        """
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            raise RAGFlowError(f"Domain {domain_id} not found")
        
        if not domain.ragflow_dataset_id:
            raise RAGFlowError(f"Domain {domain_id} has no RAGFlow dataset")
        
        # Upload to RAGFlow
        try:
            result = await self.upload_document(
                dataset_id=domain.ragflow_dataset_id,
                file_content=file_content,
                filename=filename,
                run_immediately=True
            )
            # RAGFlow returns a list of uploaded documents
            if isinstance(result, list) and len(result) > 0:
                ragflow_doc_id = result[0].get("id")
            elif isinstance(result, dict):
                ragflow_doc_id = result.get("id")
            else:
                ragflow_doc_id = None
            logger.info(f"Uploaded document to RAGFlow: {ragflow_doc_id}")
        except RAGFlowError as e:
            logger.error(f"Failed to upload to RAGFlow: {e}")
            raise
        
        # Create local record
        document = RAGFlowDocument(
            domain_id=domain_id,
            customer_id=customer_id,
            original_filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            ragflow_document_id=ragflow_doc_id,
            status=RAGFlowDocumentStatus.PARSING,
            uploaded_by_user_id=user_id,
            document_metadata=metadata,
            processing_started_at=datetime.utcnow()
        )
        
        self.db.add(document)
        
        # Update domain stats and status
        domain.document_count += 1
        # Transition to INDEXING status when documents are uploaded (per spec)
        domain.status = RAGFlowDomainStatus.INDEXING
        domain.last_error = None
        
        self.db.commit()
        self.db.refresh(document)
        
        return document
    
    async def get_document_status(
        self,
        document_id: int,
        customer_id: str
    ) -> Optional[RAGFlowDocument]:
        """Get document with refreshed status from RAGFlow."""
        document = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.id == document_id,
            RAGFlowDocument.customer_id == customer_id
        ).first()
        
        if not document or not document.ragflow_document_id:
            return document
        
        # Get status from RAGFlow
        domain = await self.get_domain(document.domain_id, customer_id)
        if domain and domain.ragflow_dataset_id:
            try:
                ragflow_doc = await self.get_document(
                    domain.ragflow_dataset_id,
                    document.ragflow_document_id
                )
                
                # Update local status
                progress = ragflow_doc.get("progress", 0)
                document.progress = int(progress * 100) if progress <= 1 else progress
                
                # RAGFlow run status - can be numeric string OR status name
                # Numeric: '0'=UNSTART, '1'=RUNNING, '2'=CANCEL, '3'=DONE, '4'=FAIL
                # Name: 'UNSTART', 'RUNNING', 'CANCEL', 'DONE', 'FAIL'
                run_status = str(ragflow_doc.get("run", "")).upper()
                if run_status in ("3", "DONE"):
                    document.status = RAGFlowDocumentStatus.COMPLETED
                    document.processing_completed_at = datetime.utcnow()
                    document.chunk_count = ragflow_doc.get("chunk_count", ragflow_doc.get("chunk_num", 0))
                    document.token_count = ragflow_doc.get("token_count", ragflow_doc.get("token_num", 0))
                elif run_status in ("4", "FAIL"):
                    document.status = RAGFlowDocumentStatus.FAILED
                    document.processing_error = ragflow_doc.get("progress_msg")
                elif run_status in ("1", "RUNNING"):
                    document.status = RAGFlowDocumentStatus.PARSING
                elif run_status in ("0", "UNSTART"):
                    document.status = RAGFlowDocumentStatus.PENDING
                elif run_status in ("2", "CANCEL"):
                    document.status = RAGFlowDocumentStatus.PENDING
                    document.processing_error = "Parsing was cancelled"
                
                self.db.commit()
                self.db.refresh(document)
                
            except RAGFlowError as e:
                logger.warning(f"Could not get RAGFlow document status: {e}")
        
        return document
    
    async def list_domain_documents(
        self,
        domain_id: int,
        customer_id: str,
        status: Optional[RAGFlowDocumentStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RAGFlowDocument]:
        """List documents in a domain, syncing with RAGFlow first."""
        # First sync documents from RAGFlow
        await self._sync_domain_documents(domain_id, customer_id)
        
        query = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == domain_id,
            RAGFlowDocument.customer_id == customer_id
        )
        
        if status:
            query = query.filter(RAGFlowDocument.status == status)
        
        return query.order_by(RAGFlowDocument.created_at.desc()).offset(offset).limit(limit).all()

    async def _sync_domain_documents(self, domain_id: int, customer_id: str):
        """Sync documents from RAGFlow to local database."""
        domain = await self.get_domain(domain_id, customer_id)
        if not domain or not domain.ragflow_dataset_id:
            return
        
        try:
            # Fetch documents from RAGFlow
            ragflow_docs = await self.list_documents(domain.ragflow_dataset_id, page_size=1000)
            ragflow_docs_list = ragflow_docs.get("docs", [])
            
            # Get existing local document IDs
            existing_ragflow_ids = {
                doc.ragflow_document_id 
                for doc in self.db.query(RAGFlowDocument).filter(
                    RAGFlowDocument.domain_id == domain_id,
                    RAGFlowDocument.customer_id == customer_id
                ).all()
                if doc.ragflow_document_id
            }
            
            # Sync each RAGFlow document
            for ragflow_doc in ragflow_docs_list:
                ragflow_id = ragflow_doc.get("id")
                if not ragflow_id:
                    continue
                
                if ragflow_id in existing_ragflow_ids:
                    # Update existing document status
                    local_doc = self.db.query(RAGFlowDocument).filter(
                        RAGFlowDocument.ragflow_document_id == ragflow_id,
                        RAGFlowDocument.customer_id == customer_id
                    ).first()
                    if local_doc:
                        self._update_doc_from_ragflow(local_doc, ragflow_doc)
                else:
                    # Create new local document record
                    new_doc = RAGFlowDocument(
                        domain_id=domain_id,
                        customer_id=customer_id,
                        original_filename=ragflow_doc.get("name", "unknown"),
                        file_size=ragflow_doc.get("size", 0),
                        mime_type=ragflow_doc.get("type", "application/octet-stream"),
                        ragflow_document_id=ragflow_id,
                        status=RAGFlowDocumentStatus.PENDING,
                    )
                    self._update_doc_from_ragflow(new_doc, ragflow_doc)
                    self.db.add(new_doc)
            
            self.db.commit()
            
            # Update domain counts
            total_docs = self.db.query(RAGFlowDocument).filter(
                RAGFlowDocument.domain_id == domain_id,
                RAGFlowDocument.customer_id == customer_id
            ).count()
            total_chunks = sum(
                doc.chunk_count or 0 
                for doc in self.db.query(RAGFlowDocument).filter(
                    RAGFlowDocument.domain_id == domain_id
                ).all()
            )
            domain.document_count = total_docs
            domain.chunk_count = total_chunks
            self.db.commit()
            
        except RAGFlowError as e:
            logger.warning(f"Failed to sync documents from RAGFlow: {e}")

    def _update_doc_from_ragflow(self, doc: RAGFlowDocument, ragflow_doc: Dict):
        """Update local document record from RAGFlow data."""
        progress = ragflow_doc.get("progress", 0)
        # RAGFlow returns progress as 0-1 float, convert to percentage
        doc.progress = int(progress * 100) if isinstance(progress, float) and progress <= 1 else int(progress)
        # RAGFlow uses 'chunk_count' for number of chunks
        doc.chunk_count = ragflow_doc.get("chunk_count", ragflow_doc.get("chunk_num", 0))
        doc.token_count = ragflow_doc.get("token_count", ragflow_doc.get("token_num", 0))
        
        # RAGFlow run status - can be numeric string OR status name
        # Numeric: '0'=UNSTART, '1'=RUNNING, '2'=CANCEL, '3'=DONE, '4'=FAIL
        # Name: 'UNSTART', 'RUNNING', 'CANCEL', 'DONE', 'FAIL'
        run_status = str(ragflow_doc.get("run", "0")).upper()
        
        logger.debug(f"Doc {ragflow_doc.get('name')}: run={run_status}, progress={progress}, chunks={doc.chunk_count}")
        
        if run_status in ("3", "DONE"):
            doc.status = RAGFlowDocumentStatus.COMPLETED
            doc.processing_completed_at = datetime.utcnow()
        elif run_status in ("4", "FAIL"):
            doc.status = RAGFlowDocumentStatus.FAILED
            doc.processing_error = ragflow_doc.get("progress_msg")
        elif run_status in ("1", "RUNNING"):
            doc.status = RAGFlowDocumentStatus.PARSING
        else:  # '0', 'UNSTART', '2', 'CANCEL'
            doc.status = RAGFlowDocumentStatus.PENDING
    
    async def delete_domain_document(
        self,
        document_id: int,
        customer_id: str
    ) -> bool:
        """Delete a document from domain and RAGFlow."""
        document = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.id == document_id,
            RAGFlowDocument.customer_id == customer_id
        ).first()
        
        if not document:
            return False
        
        # Delete from RAGFlow
        if document.ragflow_document_id:
            domain = await self.get_domain(document.domain_id, customer_id)
            if domain and domain.ragflow_dataset_id:
                try:
                    await self.delete_document(
                        domain.ragflow_dataset_id,
                        document.ragflow_document_id
                    )
                except RAGFlowError as e:
                    logger.warning(f"Failed to delete from RAGFlow: {e}")
        
        # Update domain stats
        domain = await self.get_domain(document.domain_id, customer_id)
        if domain:
            domain.document_count = max(0, domain.document_count - 1)
        
        # Delete local record
        self.db.delete(document)
        self.db.commit()
        
        return True
    
    async def start_parsing(
        self,
        domain_id: int,
        customer_id: str,
        document_ids: Optional[List[int]] = None
    ) -> RAGFlowDomain:
        """
        Start parsing for pending documents in a domain.
        
        If document_ids is provided, only parse those documents.
        Otherwise, parse all pending/unstarted documents.
        """
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            raise RAGFlowError(f"Domain {domain_id} not found")
        
        if not domain.ragflow_dataset_id:
            raise RAGFlowError(f"Domain {domain_id} has no RAGFlow dataset")
        
        # Get pending documents
        query = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == domain_id,
            RAGFlowDocument.customer_id == customer_id,
            RAGFlowDocument.status == RAGFlowDocumentStatus.PENDING
        )
        
        if document_ids:
            query = query.filter(RAGFlowDocument.id.in_(document_ids))
        
        pending_docs = query.all()
        
        if not pending_docs:
            logger.info(f"No pending documents to parse in domain {domain_id}")
            return domain
        
        # Get RAGFlow document IDs
        ragflow_doc_ids = [doc.ragflow_document_id for doc in pending_docs if doc.ragflow_document_id]
        
        if ragflow_doc_ids:
            try:
                await self.parse_documents(domain.ragflow_dataset_id, ragflow_doc_ids)
                logger.info(f"Started parsing {len(ragflow_doc_ids)} documents in domain {domain_id}")
                
                # Update local statuses
                for doc in pending_docs:
                    doc.status = RAGFlowDocumentStatus.PARSING
                    doc.processing_started_at = datetime.utcnow()
                
                domain.status = RAGFlowDomainStatus.INDEXING
                self.db.commit()
                self.db.refresh(domain)
                
            except RAGFlowError as e:
                logger.error(f"Failed to start parsing: {e}")
                raise
        
        return domain

    async def retry_failed_documents(
        self,
        domain_id: int,
        customer_id: str
    ) -> RAGFlowDomain:
        """
        Retry ingestion for failed documents in a domain.
        
        Re-queues failed documents for parsing in RAGFlow.
        """
        domain = await self.get_domain(domain_id, customer_id)
        if not domain:
            raise RAGFlowError(f"Domain {domain_id} not found")
        
        if not domain.ragflow_dataset_id:
            raise RAGFlowError(f"Domain {domain_id} has no RAGFlow dataset")
        
        # Get failed documents
        failed_docs = self.db.query(RAGFlowDocument).filter(
            RAGFlowDocument.domain_id == domain_id,
            RAGFlowDocument.customer_id == customer_id,
            RAGFlowDocument.status == RAGFlowDocumentStatus.FAILED
        ).all()
        
        if not failed_docs:
            logger.info(f"No failed documents to retry in domain {domain_id}")
            return domain
        
        # Collect RAGFlow document IDs to retry
        ragflow_doc_ids = [
            doc.ragflow_document_id 
            for doc in failed_docs 
            if doc.ragflow_document_id
        ]
        
        if ragflow_doc_ids:
            try:
                # Trigger re-parsing in RAGFlow
                await self.parse_documents(domain.ragflow_dataset_id, ragflow_doc_ids)
                logger.info(f"Triggered retry for {len(ragflow_doc_ids)} documents in domain {domain_id}")
                
                # Update local document statuses
                for doc in failed_docs:
                    doc.status = RAGFlowDocumentStatus.PARSING
                    doc.processing_error = None
                    doc.progress = 0
                    doc.processing_started_at = datetime.utcnow()
                
                # Update domain status to INDEXING
                domain.status = RAGFlowDomainStatus.INDEXING
                domain.last_error = None
                
                self.db.commit()
                self.db.refresh(domain)
                
            except RAGFlowError as e:
                logger.error(f"Failed to retry documents in RAGFlow: {e}")
                domain.last_error = str(e)
                self.db.commit()
                raise
        
        return domain
    
    # ==================== Conversation Management ====================
    
    async def create_conversation(
        self,
        domain_id: int,
        customer_id: str,
        user_id: int,
        title: Optional[str] = None
    ) -> RAGFlowConversation:
        """Create a new conversation."""
        conversation = RAGFlowConversation(
            domain_id=domain_id,
            customer_id=customer_id,
            user_id=user_id,
            title=title
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        return conversation
    
    async def get_conversation(
        self,
        conversation_id: int,
        customer_id: str
    ) -> Optional[RAGFlowConversation]:
        """Get a conversation by ID."""
        return self.db.query(RAGFlowConversation).filter(
            RAGFlowConversation.id == conversation_id,
            RAGFlowConversation.customer_id == customer_id
        ).first()
    
    async def list_conversations(
        self,
        domain_id: int,
        customer_id: str,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[RAGFlowConversation]:
        """List conversations for a domain."""
        query = self.db.query(RAGFlowConversation).filter(
            RAGFlowConversation.domain_id == domain_id,
            RAGFlowConversation.customer_id == customer_id,
            RAGFlowConversation.is_active == True
        )
        
        if user_id:
            query = query.filter(RAGFlowConversation.user_id == user_id)
        
        return query.order_by(RAGFlowConversation.last_message_at.desc().nullslast()).offset(offset).limit(limit).all()
    
    async def send_message(
        self,
        conversation_id: int,
        customer_id: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Send a message in a conversation and get RAG response.
        
        Returns both the user message and assistant response.
        """
        conversation = await self.get_conversation(conversation_id, customer_id)
        if not conversation:
            raise RAGFlowError(f"Conversation {conversation_id} not found")
        
        domain = await self.get_domain(conversation.domain_id, customer_id)
        if not domain or not domain.ragflow_dataset_id:
            raise RAGFlowError("Domain not configured for RAG")
        
        # Save user message
        user_message = RAGFlowMessage(
            conversation_id=conversation_id,
            role="user",
            content=content
        )
        self.db.add(user_message)
        
        # Get conversation history for context
        history = []
        for msg in conversation.messages[-10:]:  # Last 10 messages
            history.append({"role": msg.role, "content": msg.content})
        
        # Call RAGFlow chat
        try:
            response = await self.chat(
                dataset_ids=[domain.ragflow_dataset_id],
                question=content,
                conversation_history=history,
                top_k=domain.top_k,
                similarity_threshold=domain.similarity_threshold / 100.0,
                customer_id=customer_id,
                prompt_domain=self.settings.ragflow_prompt_domain
            )
            
            answer = response.get("answer", "I couldn't find relevant information to answer your question.")
            chunks = response.get("chunks", [])
            
        except RAGFlowError as e:
            logger.error(f"RAGFlow chat error: {e}")
            answer = f"Sorry, I encountered an error: {str(e)}"
            chunks = []
        
        # Save assistant message
        assistant_message = RAGFlowMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            retrieved_chunks=[{
                "content": c.get("content", "")[:500],
                "document_name": c.get("document_name"),
                "similarity": c.get("similarity")
            } for c in chunks[:5]],
            chunk_count=len(chunks)
        )
        self.db.add(assistant_message)
        
        # Update conversation stats
        conversation.message_count += 2
        conversation.last_message_at = datetime.utcnow()
        
        # Auto-generate title if not set
        if not conversation.title and conversation.message_count == 2:
            conversation.title = content[:100] + ("..." if len(content) > 100 else "")
        
        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)
        
        return {
            "user_message": {
                "id": user_message.id,
                "role": "user",
                "content": content,
                "created_at": user_message.created_at.isoformat()
            },
            "assistant_message": {
                "id": assistant_message.id,
                "role": "assistant",
                "content": answer,
                "chunks": chunks[:5],
                "created_at": assistant_message.created_at.isoformat()
            }
        }
    
    async def delete_conversation(
        self,
        conversation_id: int,
        customer_id: str
    ) -> bool:
        """Soft-delete a conversation."""
        conversation = await self.get_conversation(conversation_id, customer_id)
        if not conversation:
            return False
        
        conversation.is_active = False
        self.db.commit()
        
        return True
