"""
FASB RAG Service

Provides RAG (Retrieval Augmented Generation) for FASB Accounting Standards Codification.
Uses OpenSearch Serverless for vector search and OpenAI for embeddings/chat.
"""
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Literal, Tuple
import re
import boto3
import requests
from requests_aws4auth import AWS4Auth
from openai import OpenAI

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__, component="fasb.service")

FASBSourceFilter = Literal["all", "primary", "memo"]


@dataclass(frozen=True)
class FASBSearchSource:
    """OpenSearch target for a FASB retrieval source."""
    name: str
    host: str
    region: str
    index: str


class FASBContext:
    """A retrieved context chunk from FASB index."""
    def __init__(self, citation: str, text: str, score: float = 0.0):
        self.citation = citation
        self.text = text
        self.score = score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation": self.citation,
            "text": self.text,
            "score": self.score
        }


class FASBService:
    """
    Service for FASB Accounting Standards Codification RAG.
    
    Uses:
    - OpenSearch Serverless for vector storage and kNN search
    - OpenAI text-embedding-3-large for query embedding
    - OpenAI GPT for reranking and answer generation
    """
    
    def __init__(self, customer_id: str = "default"):
        self.settings = get_settings()
        self.customer_id = customer_id
        
        # Primary OpenSearch Serverless configuration
        self.host = self.settings.fasb_opensearch_host
        self.region = self.settings.fasb_opensearch_region
        self.index = self.settings.fasb_opensearch_index
        self.primary_source = FASBSearchSource(
            name="primary",
            host=self.host,
            region=self.region,
            index=self.index,
        )

        # Optional secondary memo source
        memo_index = (self.settings.fasb_memo_opensearch_index or "").strip()
        memo_host = (self.settings.fasb_memo_opensearch_host or self.host).strip()
        memo_region = (self.settings.fasb_memo_opensearch_region or self.region).strip()
        memo_enabled = bool(self.settings.fasb_memo_enabled and memo_index)
        self.memo_source: Optional[FASBSearchSource] = None
        if memo_enabled:
            self.memo_source = FASBSearchSource(
                name="memo",
                host=memo_host,
                region=memo_region,
                index=memo_index,
            )
        
        # Model configuration
        self.embed_model = self.settings.fasb_embed_model
        self.chat_model = self.settings.fasb_chat_model
        
        # Retrieval settings
        self.knn_k = self.settings.fasb_knn_k
        self.retrieve_size = self.settings.fasb_retrieve_size
        self.rerank_keep = self.settings.fasb_rerank_keep
        
        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=self.settings.openai_api_key)
        
        # Initialize AWS auth cache for OpenSearch Serverless (by region)
        self._aws_auth_by_region: Dict[str, AWS4Auth] = {}
        
        # Cache for managed prompts
        self._prompt_cache = {}
        
        logger.info(
            "fasb_service_initialized",
            host=self.host,
            region=self.region,
            index=self.index,
            memo_enabled=bool(self.memo_source),
            memo_index=self.memo_source.index if self.memo_source else None,
            memo_host=self.memo_source.host if self.memo_source else None,
            memo_region=self.memo_source.region if self.memo_source else None,
            embed_model=self.embed_model,
            chat_model=self.chat_model,
            customer_id=customer_id
        )
    
    def _get_managed_prompt(self, prompt_type: str, customer_id: Optional[str] = None) -> Optional[str]:
        """
        Get a prompt from the Prompt Management system.
        
        Returns None if not available, allowing fallback to hardcoded defaults.
        """
        effective_customer_id = customer_id or self.customer_id
        cache_key = f"{effective_customer_id}:{prompt_type}"
        
        # Check cache first
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]
        
        try:
            from src.utils.prompt_loader import get_prompt
            content = get_prompt(effective_customer_id, "fasb", prompt_type)
            if content:
                self._prompt_cache[cache_key] = content
            return content
        except Exception as e:
            logger.debug(f"Could not load managed prompt {prompt_type}: {e}")
            return None
    
    @property
    def aws_auth(self) -> AWS4Auth:
        """Backward-compatible auth accessor for primary source."""
        return self._get_aws_auth(self.region)

    def _get_aws_auth(self, region: str) -> AWS4Auth:
        """Lazily initialize AWS SigV4 auth for OpenSearch Serverless by region."""
        cached = self._aws_auth_by_region.get(region)
        if cached is not None:
            return cached

        # Try to get credentials from environment or boto3 session
        import os
        access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        session_token = os.environ.get('AWS_SESSION_TOKEN')
        
        if access_key and secret_key:
            logger.info("Using AWS credentials from environment variables")
            auth = AWS4Auth(
                access_key,
                secret_key,
                region,
                "aoss",
                session_token=session_token
            )
        else:
            # Fall back to boto3 session (IAM role, etc.)
            session = boto3.Session(region_name=region)
            creds = session.get_credentials()
            if creds is None:
                raise ValueError("No AWS credentials found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")
            frozen_creds = creds.get_frozen_credentials()
            auth = AWS4Auth(
                frozen_creds.access_key,
                frozen_creds.secret_key,
                region,
                "aoss",
                session_token=frozen_creds.token
            )

        self._aws_auth_by_region[region] = auth
        return auth

    def _selected_sources(self, source_filter: Optional[str] = None) -> List[FASBSearchSource]:
        """
        Resolve configured retrieval sources.

        Args:
            source_filter: all | primary | memo (None defaults to all)
        """
        normalized = (source_filter or "all").strip().lower()
        if normalized not in {"all", "primary", "memo"}:
            raise ValueError("Invalid source_filter. Expected one of: all, primary, memo")

        if normalized == "primary":
            return [self.primary_source]

        if normalized == "memo":
            if not self.memo_source:
                raise ValueError("Memo source requested but not configured. Set FASB_MEMO_* settings.")
            return [self.memo_source]

        sources = [self.primary_source]
        if self.memo_source:
            sources.append(self.memo_source)
        return sources

    def _context_chunk_key(self, citation: str) -> str:
        """Build stable dedupe key from citation text."""
        source_match = re.search(r"source:([^\s]+)", citation)
        chunk_match = re.search(r"chunk:([^\s]+)", citation)
        source = source_match.group(1) if source_match else "primary"
        chunk = chunk_match.group(1) if chunk_match else citation
        return f"{source}:{chunk}"

    @staticmethod
    def _normalize_knowledge_base_ids(knowledge_base_ids: Optional[List[int]]) -> List[int]:
        """Normalize KB ids into a unique, ordered integer list."""
        if not knowledge_base_ids:
            return []

        normalized: List[int] = []
        seen: set[int] = set()
        for raw_id in knowledge_base_ids:
            try:
                kb_id = int(raw_id)
            except (TypeError, ValueError):
                continue

            if kb_id <= 0 or kb_id in seen:
                continue
            seen.add(kb_id)
            normalized.append(kb_id)

        return normalized

    @staticmethod
    def _knowledge_base_filter_clause(knowledge_base_ids: List[int]) -> Optional[Dict[str, Any]]:
        """
        Build a resilient OpenSearch filter for KB-scoped retrieval.

        Supports both top-level `knowledge_base_id` and nested `metadata.knowledge_base_id`
        representations, with numeric or string values.
        """
        if not knowledge_base_ids:
            return None

        kb_ids_as_str = [str(kb_id) for kb_id in knowledge_base_ids]
        return {
            "bool": {
                "should": [
                    {"terms": {"knowledge_base_id": knowledge_base_ids}},
                    {"terms": {"knowledge_base_id": kb_ids_as_str}},
                    {"terms": {"metadata.knowledge_base_id": knowledge_base_ids}},
                    {"terms": {"metadata.knowledge_base_id": kb_ids_as_str}},
                ],
                "minimum_should_match": 1,
            }
        }
    
    def _embed_query(self, query: str) -> List[float]:
        """Embed query using OpenAI embedding model."""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embed_model,
                input=[query],
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to embed query: {e}", exc_info=True)
            raise ValueError(f"Embedding failed: {str(e)}")

    def _embed_texts(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """Embed multiple texts using the configured FASB embedding model."""
        if not texts:
            return []

        vectors: List[List[float]] = []
        try:
            for start in range(0, len(texts), batch_size):
                batch = texts[start:start + batch_size]
                response = self.openai_client.embeddings.create(
                    model=self.embed_model,
                    input=batch,
                    encoding_format="float",
                )
                vectors.extend([item.embedding for item in response.data])
            return vectors
        except Exception as e:
            logger.error("fasb_embed_texts_failed", error=str(e), batch_size=batch_size)
            raise ValueError(f"Embedding failed: {str(e)}")
    
    def _parse_section_reference(self, query: str) -> Optional[Dict[str, str]]:
        """
        Parse ASC section references from query.
        
        Formats supported:
        - "272-10-05-6" -> topic=272, subtopic=10, section=05, paragraph=272-10-05-6
        - "section 272" or "ASC 272" -> topic=272
        - "topic 606" -> topic=606
        
        Returns:
            Dict with parsed components or None if no reference found
        """
        # Full paragraph reference: 272-10-05-6
        full_match = re.search(r'\b(\d{3})-(\d{1,2})-(\d{2})-(\d+)\b', query)
        if full_match:
            topic, subtopic, section, para = full_match.groups()
            return {
                'topic_number': topic,
                'subtopic_number': subtopic.zfill(2),
                'section_number': section,
                'paragraph_id': f"{topic}-{subtopic.zfill(2)}-{section}-{para}"
            }
        
        # Section reference: 272-10-05
        section_match = re.search(r'\b(\d{3})-(\d{1,2})-(\d{2})\b', query)
        if section_match:
            topic, subtopic, section = section_match.groups()
            return {
                'topic_number': topic,
                'subtopic_number': subtopic.zfill(2),
                'section_number': section
            }
        
        # Subtopic reference: 272-10
        subtopic_match = re.search(r'\b(\d{3})-(\d{1,2})\b', query)
        if subtopic_match:
            topic, subtopic = subtopic_match.groups()
            return {
                'topic_number': topic,
                'subtopic_number': subtopic.zfill(2)
            }
        
        # Topic reference: "ASC 272", "section 272", "topic 606"
        topic_match = re.search(r'(?:asc|section|topic|fasb)\s*(\d{3})\b', query, re.IGNORECASE)
        if topic_match:
            return {'topic_number': topic_match.group(1)}
        
        return None

    def _fetch_exact_paragraph(
        self,
        paragraph_id: str,
        source: Optional[FASBSearchSource] = None,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> Optional[FASBContext]:
        """
        Fetch a specific paragraph by exact paragraph_id.
        
        Returns:
            FASBContext with score 999.0 (highest priority) or None if not found.
        """
        source_cfg = source or self.primary_source
        normalized_kb_ids = self._normalize_knowledge_base_ids(knowledge_base_ids)
        filter_clauses: List[Dict[str, Any]] = [
            {"term": {"is_superseded": False}},
            {"term": {"paragraph_id": paragraph_id}},
        ]
        kb_filter = self._knowledge_base_filter_clause(normalized_kb_ids)
        if kb_filter is not None:
            filter_clauses.append(kb_filter)

        body = {
            "size": 1,
            "_source": [
                "chunk_id", "doc_id", "chunk_type", "source_path",
                "page_start", "page_end", "paragraph_id", "section_path",
                "text", "is_superseded", "topic_number"
            ],
            "query": {
                "bool": {
                    "filter": filter_clauses
                }
            }
        }
        
        url = f"https://{source_cfg.host}/{source_cfg.index}/_search"
        try:
            response = requests.get(
                url,
                auth=self._get_aws_auth(source_cfg.region),
                headers={"Content-Type": "application/json"},
                data=json.dumps(body),
                timeout=30
            )
            response.raise_for_status()
            hits = response.json().get("hits", {}).get("hits", [])
            
            if hits:
                source = hits[0].get("_source", {})
                citation = self._build_citation(source, source_name=source_cfg.name)
                text = (source.get("text") or "").strip()
                logger.info(
                    "fasb_exact_paragraph_found",
                    paragraph_id=paragraph_id,
                    source=source_cfg.name,
                    text_preview=text[:100] if text else None
                )
                return FASBContext(citation=citation, text=text, score=999.0)
            
            logger.info(
                "fasb_exact_paragraph_not_found",
                paragraph_id=paragraph_id,
                source=source_cfg.name
            )
            return None
            
        except requests.RequestException as e:
            logger.warning(
                "fasb_exact_paragraph_lookup_failed",
                paragraph_id=paragraph_id,
                source=source_cfg.name,
                error=str(e)
            )
            return None

    def retrieve(
        self,
        query: str,
        original_query: Optional[str] = None,
        source_filter: Optional[str] = None,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> List[FASBContext]:
        """
        Retrieve relevant FASB chunks using hybrid search.
        
        Two-phase retrieval strategy:
        1. If a specific paragraph is referenced, fetch it directly first
        2. Then do kNN search filtered by topic for related content
        3. Combine results with exact match first
        
        Args:
            query: Query for semantic search (may be rewritten)
            original_query: Original user question (used for section parsing)
            source_filter: Optional retrieval source filter (all | primary | memo)
            knowledge_base_ids: Optional knowledge base scope filter
            
        Returns:
            List of FASBContext objects with citation and text
        """
        contexts = []
        selected_sources = self._selected_sources(source_filter)
        normalized_kb_ids = self._normalize_knowledge_base_ids(knowledge_base_ids)
        
        # Parse section references from ORIGINAL query (not rewritten)
        parse_query = original_query or query
        section_ref = self._parse_section_reference(parse_query)
        
        if section_ref:
            logger.info(
                "fasb_section_reference_detected",
                section_ref=section_ref,
                original_query=parse_query,
                source_filter=source_filter or "all",
                sources=[s.name for s in selected_sources],
                knowledge_base_ids=normalized_kb_ids or None,
            )
        
        # Phase 1: Direct lookup for exact paragraph (if specified)
        if section_ref and 'paragraph_id' in section_ref:
            # Try each selected source in order; use first exact match.
            for source_cfg in selected_sources:
                exact_ctx = self._fetch_exact_paragraph(
                    section_ref['paragraph_id'],
                    source=source_cfg,
                    knowledge_base_ids=normalized_kb_ids,
                )
                if exact_ctx:
                    contexts.append(exact_ctx)
                    break
        
        # Phase 2: Hybrid search (kNN + keyword)
        qvec = self._embed_query(query)
        
        # Build filter clauses
        filter_clauses = [
            {"term": {"is_superseded": False}},
            {"bool": {"must_not": [{"term": {"chunk_type": "test"}}]}}
        ]

        kb_filter = self._knowledge_base_filter_clause(normalized_kb_ids)
        if kb_filter is not None:
            filter_clauses.append(kb_filter)
        
        # Add topic filter if section reference detected
        if section_ref and 'topic_number' in section_ref:
            filter_clauses.append({"term": {"topic_number": section_ref['topic_number']}})
        
        # Build should clauses for boosting - combine keyword matching with kNN
        should_clauses = [
            # Keyword match on the original query text (boosts relevant keyword matches)
            {"match": {"text": {"query": parse_query, "boost": 2.0}}},
        ]
        
        # Boost matches within the same section
        if section_ref:
            if 'section_number' in section_ref:
                should_clauses.append({
                    "term": {"section_number": {"value": section_ref['section_number'], "boost": 20}}
                })
            if 'subtopic_number' in section_ref:
                should_clauses.append({
                    "term": {"subtopic_number": {"value": section_ref['subtopic_number'], "boost": 10}}
                })
        
        # Build OpenSearch hybrid query: kNN + keyword matching
        # Using script_score to combine kNN similarity with keyword relevance
        body = {
            "size": self.retrieve_size * 2,  # Get more candidates for hybrid merge
            "collapse": {"field": "chunk_id"},
            "_source": [
                "chunk_id", "doc_id", "chunk_type", "source_path",
                "page_start", "page_end", "paragraph_id", "section_path",
                "text", "is_superseded", "topic_number", "subtopic_number", "section_number"
            ],
            "query": {
                "bool": {
                    "filter": filter_clauses,
                    "must": [
                        {"knn": {"embedding": {"vector": qvec, "k": self.knn_k}}}
                    ],
                    "should": should_clauses
                }
            }
        }
        
        # Also run a pure keyword search to catch what kNN might miss
        # Use both phrase matching (high precision) and regular matching (recall)
        keyword_body = {
            "size": self.retrieve_size,
            "collapse": {"field": "chunk_id"},
            "_source": [
                "chunk_id", "doc_id", "chunk_type", "source_path",
                "page_start", "page_end", "paragraph_id", "section_path",
                "text", "is_superseded", "topic_number", "subtopic_number", "section_number"
            ],
            "query": {
                "bool": {
                    "filter": filter_clauses,
                    "should": [
                        # Phrase match gets highest boost - exact phrases like "variable interest entity"
                        {"match_phrase": {"text": {"query": parse_query, "boost": 3.0, "slop": 2}}},
                        # Regular match for broader coverage
                        {"match": {"text": {"query": parse_query, "boost": 1.0}}}
                    ],
                    "minimum_should_match": 1
                }
            }
        }
        
        # Also run a phrase-focused search for multi-word terms
        # Extract potential phrases (2-4 word sequences) from the query
        words = parse_query.split()
        phrase_queries = []
        if len(words) >= 2:
            # Try to find meaningful phrases in the query
            for i in range(len(words) - 1):
                phrase = " ".join(words[i:i+3]) if i + 3 <= len(words) else " ".join(words[i:])
                if len(phrase.split()) >= 2:
                    phrase_queries.append({"match_phrase": {"text": {"query": phrase, "boost": 5.0, "slop": 1}}})
        
        phrase_body = None
        if phrase_queries:
            phrase_body = {
                "size": self.retrieve_size // 2,
                "collapse": {"field": "chunk_id"},
                "_source": [
                    "chunk_id", "doc_id", "chunk_type", "source_path",
                    "page_start", "page_end", "paragraph_id", "section_path",
                    "text", "is_superseded", "topic_number", "subtopic_number", "section_number"
                ],
                "query": {
                    "bool": {
                        "filter": filter_clauses,
                        "should": phrase_queries,
                        "minimum_should_match": 1
                    }
                }
            }
        
        # Execute searches across all selected sources
        search_errors: List[str] = []
        knn_hits_by_source: List[Tuple[str, Dict[str, Any]]] = []
        keyword_hits_by_source: List[Tuple[str, Dict[str, Any]]] = []
        phrase_hits_by_source: List[Tuple[str, Dict[str, Any]]] = []

        for source_cfg in selected_sources:
            url = f"https://{source_cfg.host}/{source_cfg.index}/_search"
            auth = self._get_aws_auth(source_cfg.region)

            source_knn_hits: List[Dict[str, Any]] = []
            source_keyword_hits: List[Dict[str, Any]] = []
            source_phrase_hits: List[Dict[str, Any]] = []
            source_errors: List[str] = []

            # kNN hybrid search
            try:
                response = requests.get(
                    url,
                    auth=auth,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(body),
                    timeout=60
                )
                response.raise_for_status()
                source_knn_hits = response.json().get("hits", {}).get("hits", [])
            except requests.RequestException as e:
                error_detail = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    error_detail = f"HTTP {e.response.status_code}: {e.response.text[:500]}"
                source_errors.append(f"{source_cfg.name} kNN search failed: {error_detail}")
            except ValueError as e:
                source_errors.append(f"{source_cfg.name} AWS authentication failed: {str(e)}")

            # keyword search
            try:
                keyword_response = requests.get(
                    url,
                    auth=auth,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(keyword_body),
                    timeout=60
                )
                keyword_response.raise_for_status()
                source_keyword_hits = keyword_response.json().get("hits", {}).get("hits", [])
            except requests.RequestException as e:
                error_detail = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    error_detail = f"HTTP {e.response.status_code}: {e.response.text[:500]}"
                source_errors.append(f"{source_cfg.name} keyword search failed: {error_detail}")
            except ValueError as e:
                source_errors.append(f"{source_cfg.name} keyword AWS auth failed: {str(e)}")

            # phrase search
            if phrase_body:
                try:
                    phrase_response = requests.get(
                        url,
                        auth=auth,
                        headers={"Content-Type": "application/json"},
                        data=json.dumps(phrase_body),
                        timeout=60
                    )
                    phrase_response.raise_for_status()
                    source_phrase_hits = phrase_response.json().get("hits", {}).get("hits", [])
                except requests.RequestException as e:
                    source_errors.append(f"{source_cfg.name} phrase search failed: {str(e)}")
                except ValueError as e:
                    source_errors.append(f"{source_cfg.name} phrase AWS auth failed: {str(e)}")

            knn_hits_by_source.extend((source_cfg.name, hit) for hit in source_knn_hits)
            keyword_hits_by_source.extend((source_cfg.name, hit) for hit in source_keyword_hits)
            phrase_hits_by_source.extend((source_cfg.name, hit) for hit in source_phrase_hits)

            if source_errors and not source_knn_hits and not source_keyword_hits and not source_phrase_hits:
                search_errors.extend(source_errors)
                logger.warning(
                    "fasb_source_search_failed",
                    source=source_cfg.name,
                    host=source_cfg.host,
                    index=source_cfg.index,
                    region=source_cfg.region,
                    errors=source_errors,
                )

        # If ALL searches failed, raise an error instead of silently returning empty
        if (
            search_errors
            and not knn_hits_by_source
            and not keyword_hits_by_source
            and not phrase_hits_by_source
            and not contexts
        ):
            combined_error = "; ".join(search_errors[:2])  # Limit error length
            raise ValueError(
                f"FASB OpenSearch retrieval failed - all search methods returned errors. "
                f"Details: {combined_error}."
            )
        
        # Merge results: phrase matches first (highest precision), then kNN, then keyword
        seen_chunk_ids = {self._context_chunk_key(ctx.citation) for ctx in contexts}
        
        # Process phrase matches first (highest boost - exact phrase matches)
        phrase_added = 0
        for source_name, hit in phrase_hits_by_source:
            source = hit.get("_source", {})
            chunk_id = source.get("chunk_id", "")
            chunk_key = f"{source_name}:{chunk_id}"
            
            if chunk_key in seen_chunk_ids:
                continue
            
            score = hit.get("_score", 0.0) * 3.0  # 3x boost for phrase match
            citation = self._build_citation(source, source_name=source_name)
            text = (source.get("text") or "").strip()
            contexts.append(FASBContext(citation=citation, text=text, score=score))
            seen_chunk_ids.add(chunk_key)
            phrase_added += 1
        
        # Process kNN results
        knn_added = 0
        for source_name, hit in knn_hits_by_source:
            source = hit.get("_source", {})
            chunk_id = source.get("chunk_id", "")
            chunk_key = f"{source_name}:{chunk_id}"
            
            if chunk_key in seen_chunk_ids:
                continue
            
            score = hit.get("_score", 0.0)
            citation = self._build_citation(source, source_name=source_name)
            text = (source.get("text") or "").strip()
            contexts.append(FASBContext(citation=citation, text=text, score=score))
            seen_chunk_ids.add(chunk_key)
            knn_added += 1
        
        # Process keyword results (boost score slightly since they matched keywords)
        keyword_added = 0
        for source_name, hit in keyword_hits_by_source:
            source = hit.get("_source", {})
            chunk_id = source.get("chunk_id", "")
            chunk_key = f"{source_name}:{chunk_id}"
            
            if chunk_key in seen_chunk_ids:
                continue
            
            score = hit.get("_score", 0.0) * 1.5  # 50% boost for keyword match
            citation = self._build_citation(source, source_name=source_name)
            text = (source.get("text") or "").strip()
            contexts.append(FASBContext(citation=citation, text=text, score=score))
            seen_chunk_ids.add(chunk_key)
            keyword_added += 1
        
        logger.info(
            "fasb_retrieve_completed",
            query_length=len(query),
            original_query_length=len(parse_query),
            results_count=len(contexts),
            source_filter=source_filter or "all",
            source_count=len(selected_sources),
            selected_sources=[s.name for s in selected_sources],
            knowledge_base_ids=normalized_kb_ids or None,
            knn_results=len(knn_hits_by_source),
            phrase_results=len(phrase_hits_by_source),
            phrase_added=phrase_added,
            knn_added=knn_added,
            keyword_results=len(keyword_hits_by_source),
            keyword_added=keyword_added,
            has_exact_match=section_ref and 'paragraph_id' in section_ref,
            topic_filter=section_ref.get('topic_number') if section_ref else None
        )
        
        return contexts

    def index_workspace_chunks(
        self,
        *,
        workspace_id: int,
        knowledge_base_id: Optional[int],
        customer_id: str,
        document_id: int,
        filename: str,
        chunks: List[Dict[str, Any]],
    ) -> int:
        """
        Index workspace-uploaded chunks into the configured FASB OpenSearch index.

        This enables FASB workspaces to ingest additional KB-scoped documents while
        still using the FASB retrieval/generation path.
        """
        if not chunks:
            return 0

        texts = [str(chunk.get("text") or "").strip() for chunk in chunks if str(chunk.get("text") or "").strip()]
        if not texts:
            return 0

        # Preserve alignment between chunk payloads and generated vectors.
        normalized_chunks = [chunk for chunk in chunks if str(chunk.get("text") or "").strip()]
        vectors = self._embed_texts(texts)
        if len(vectors) != len(normalized_chunks):
            raise ValueError("Embedding/vector count mismatch while indexing FASB workspace chunks")

        bulk_body = ""
        for idx, (chunk, vector) in enumerate(zip(normalized_chunks, vectors)):
            chunk_index = int(chunk.get("chunk_index", idx))
            chunk_id = str(chunk.get("chunk_id") or f"{document_id}_{chunk_index}")
            section_path = chunk.get("section_path") or []
            if not isinstance(section_path, list):
                section_path = [str(section_path)]

            token_count = int(chunk.get("token_count", 0) or 0)
            document = {
                "chunk_id": chunk_id,
                "doc_id": str(document_id),
                "chunk_type": str(chunk.get("chunk_type") or "workspace_document"),
                "source_path": str(chunk.get("source_path") or filename),
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "paragraph_id": chunk.get("paragraph_id"),
                "section_path": section_path,
                "section_path_str": " > ".join([str(part) for part in section_path]),
                "topic_number": chunk.get("topic_number"),
                "subtopic_number": chunk.get("subtopic_number"),
                "section_number": chunk.get("section_number"),
                "is_superseded": bool(chunk.get("is_superseded", False)),
                "text": str(chunk.get("text") or ""),
                "embedding": vector,
                "workspace_id": int(workspace_id),
                "knowledge_base_id": int(knowledge_base_id) if knowledge_base_id is not None else None,
                "customer_id": customer_id,
                "metadata": {
                    "filename": filename,
                    "chunk_index": chunk_index,
                    "token_count": token_count,
                    "knowledge_base_id": knowledge_base_id,
                    "knowledge_base_path": (
                        f"workspace/{workspace_id}/kb/{knowledge_base_id}"
                        if knowledge_base_id is not None
                        else None
                    ),
                },
            }
            action = {"index": {"_index": self.index}}
            bulk_body += json.dumps(action) + "\n" + json.dumps(document) + "\n"

        url = f"https://{self.host}/{self.index}/_bulk"
        response = requests.post(
            url,
            auth=self._get_aws_auth(self.region),
            headers={"Content-Type": "application/x-ndjson"},
            data=bulk_body,
            timeout=120,
        )
        response.raise_for_status()

        result = response.json()
        items = result.get("items", [])
        success_count = 0
        failures: List[str] = []
        for item in items:
            index_result = item.get("index", {})
            status = int(index_result.get("status", 0) or 0)
            if 200 <= status < 300:
                success_count += 1
                continue

            error_info = index_result.get("error", {})
            if isinstance(error_info, dict):
                failures.append(
                    f"status={status} type={error_info.get('type', 'unknown')} "
                    f"reason={error_info.get('reason', 'unknown')}"
                )
            else:
                failures.append(f"status={status} error={error_info}")

        if failures:
            logger.error(
                "fasb_workspace_bulk_index_partial_failure",
                workspace_id=workspace_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                success_count=success_count,
                total_items=len(items),
                failures=failures[:3],
            )

        if success_count <= 0:
            raise ValueError(
                "FASB bulk indexing failed with zero successful items. "
                + ("; ".join(failures[:3]) if failures else "No successful results returned.")
            )

        logger.info(
            "fasb_workspace_chunks_indexed",
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            indexed=success_count,
            index=self.index,
        )
        return success_count

    def delete_workspace_document_chunks(
        self,
        *,
        document_id: int,
        knowledge_base_id: Optional[int] = None,
        source_filter: Optional[str] = "primary",
    ) -> int:
        """Delete previously indexed workspace chunks from FASB OpenSearch source(s)."""
        selected_sources = self._selected_sources(source_filter)
        deleted_total = 0
        normalized_kb_ids = self._normalize_knowledge_base_ids(
            [knowledge_base_id] if knowledge_base_id is not None else None
        )

        filter_clauses: List[Dict[str, Any]] = [{"term": {"doc_id": str(document_id)}}]
        kb_filter = self._knowledge_base_filter_clause(normalized_kb_ids)
        if kb_filter is not None:
            filter_clauses.append(kb_filter)

        body = {"query": {"bool": {"filter": filter_clauses}}}
        for source_cfg in selected_sources:
            try:
                url = f"https://{source_cfg.host}/{source_cfg.index}/_delete_by_query?conflicts=proceed"
                response = requests.post(
                    url,
                    auth=self._get_aws_auth(source_cfg.region),
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(body),
                    timeout=60,
                )
                response.raise_for_status()
                payload = response.json()
                deleted_total += int(payload.get("deleted", 0) or 0)
            except Exception as exc:
                logger.warning(
                    "fasb_workspace_chunk_delete_failed",
                    source=source_cfg.name,
                    document_id=document_id,
                    knowledge_base_id=knowledge_base_id,
                    error=str(exc),
                )

        logger.info(
            "fasb_workspace_chunk_delete_completed",
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            deleted=deleted_total,
            source_filter=source_filter or "all",
        )
        return deleted_total

    def get_chunk_by_id(
        self,
        chunk_id: str,
        source_filter: Optional[str] = None,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> Optional[FASBContext]:
        """
        Fetch a single chunk by chunk_id from OpenSearch.
        
        Returns:
            FASBContext or None if not found.
        """
        if not chunk_id:
            return None
        
        body = {
            "size": 1,
            "_source": [
                "chunk_id", "doc_id", "chunk_type", "source_path",
                "page_start", "page_end", "paragraph_id", "section_path",
                "text", "is_superseded"
            ],
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"is_superseded": False}},
                        {"bool": {"must_not": [{"term": {"chunk_type": "test"}}]}}
                    ],
                    "must": [
                        {"term": {"chunk_id": chunk_id}}
                    ]
                }
            }
        }

        normalized_kb_ids = self._normalize_knowledge_base_ids(knowledge_base_ids)
        kb_filter = self._knowledge_base_filter_clause(normalized_kb_ids)
        if kb_filter is not None:
            body["query"]["bool"]["filter"].append(kb_filter)
        
        for source_cfg in self._selected_sources(source_filter):
            url = f"https://{source_cfg.host}/{source_cfg.index}/_search"
            try:
                response = requests.get(
                    url,
                    auth=self._get_aws_auth(source_cfg.region),
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(body),
                    timeout=30
                )
                response.raise_for_status()
            except requests.RequestException as e:
                logger.error(
                    "fasb_chunk_lookup_failed",
                    source=source_cfg.name,
                    chunk_id=chunk_id,
                    error=str(e),
                )
                continue
            
            hits = response.json().get("hits", {}).get("hits", [])
            if not hits:
                continue
            
            hit = hits[0]
            source = hit.get("_source", {})
            citation = self._build_citation(source, source_name=source_cfg.name)
            text = (source.get("text") or "").strip()
            score = hit.get("_score", 0.0)
            return FASBContext(citation=citation, text=text, score=score)

        return None

    @staticmethod
    def _build_citation(source: Dict[str, Any], source_name: Optional[str] = None) -> str:
        sec_path = " > ".join(source.get("section_path") or [])
        source_prefix = f"source:{source_name} " if source_name else ""
        return (
            f'{source_prefix}doc:{source.get("doc_id")} '
            f'pages:{source.get("page_start")}-{source.get("page_end")} '
            f'chunk:{source.get("chunk_id")} '
            f'section:{sec_path}'
        )
    
    def rerank(self, query: str, contexts: List[FASBContext]) -> List[FASBContext]:
        """
        Rerank retrieved contexts using GPT to select most relevant.
        
        Args:
            query: User's question
            contexts: Retrieved contexts to rerank
            
        Returns:
            Filtered list of most relevant contexts
        """
        if len(contexts) <= self.rerank_keep:
            return contexts
        
        # Build rerank prompt
        items = "\n\n".join([
            f"[{i+1}] {c.citation}\n{c.text[:1200]}" 
            for i, c in enumerate(contexts)
        ])
        
        prompt = f"""
You are reranking retrieved snippets for a RAG system.

User question:
{query}

Snippets:
{items}

Task:
Select the {self.rerank_keep} snippets that are most useful to answer the question.
Return ONLY valid JSON in this exact format:
{{"keep":[1,2,3,4,5,6,7,8]}}

Rules:
- Indices must be unique and between 1 and {len(contexts)}.
- Prefer snippets that directly answer the question.
- Prefer authoritative definitions / requirements language.
- Only list sources that directly support the answer text.
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            text = (response.choices[0].message.content or "").strip()
            
            # Parse JSON safely
            data = json.loads(text)
            keep = data.get("keep", [])
            keep = [int(x) for x in keep if 1 <= int(x) <= len(contexts)]
            
            # Unique while preserving order
            seen = set()
            keep_unique = []
            for k in keep:
                if k not in seen:
                    seen.add(k)
                    keep_unique.append(k)
            keep_unique = keep_unique[:self.rerank_keep]
            
            if len(keep_unique) < 1:
                return contexts[:self.rerank_keep]
            
            reranked = [contexts[i-1] for i in keep_unique]
            
            logger.info(
                "fasb_rerank_completed",
                original_count=len(contexts),
                reranked_count=len(reranked)
            )
            
            return reranked
            
        except Exception as e:
            logger.warning(f"Reranking failed, using top-k fallback: {e}")
            return contexts[:self.rerank_keep]
    
    def answer(
        self, 
        query: str, 
        customer_id: Optional[str] = None,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        source_filter: Optional[str] = None,
        knowledge_base_ids: Optional[List[int]] = None,
        conversation_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate answer to FASB question using RAG.
        
        Args:
            query: User's question about FASB/ASC
            customer_id: Customer ID for loading managed prompts (optional)
            top_k: Override for number of sources to return (default: rerank_keep from config)
            similarity_threshold: Minimum similarity score 0-1 (default: 0.0, no filtering)
            source_filter: Optional retrieval source filter (all | primary | memo)
            knowledge_base_ids: Optional knowledge base scope filter
            conversation_context: Optional previous conversation context.  Used only
                for LLM synthesis and query rewriting (coreference resolution), never
                for embedding or retrieval.
            
        Returns:
            Dict with answer, sources, and metadata
        """
        original_question = query
        
        # Use provided top_k or fall back to config
        effective_top_k = top_k if top_k is not None else self.rerank_keep
        effective_threshold = similarity_threshold if similarity_threshold is not None else 0.0

        # A0) Optional query rewrite (if prompt exists in Prompt Management).
        # Conversation context is forwarded so the rewriter can resolve
        # coreferences (e.g. "that section" → "section 272-10-05-6") but the
        # resulting query is a clean, standalone search string.
        rewritten_query = self._rewrite_query(
            original_question,
            customer_id=customer_id,
            conversation_context=conversation_context,
        )

        # A) Retrieve (use rewritten query for semantic search, original for section parsing)
        contexts = self.retrieve(
            rewritten_query,
            original_query=original_question,
            source_filter=source_filter,
            knowledge_base_ids=knowledge_base_ids,
        )
        
        if not contexts:
            return {
                "answer": "I couldn't find any relevant information in the FASB Accounting Standards Codification for your question. Please try rephrasing or asking about a specific ASC topic.",
                "sources": [],
                "query": query,
                "source_filter": source_filter or "all",
                "knowledge_base_ids": self._normalize_knowledge_base_ids(knowledge_base_ids),
                "contexts_retrieved": 0,
                "contexts_used": 0,
                "model": self.chat_model
            }
        
        # B) Filter by similarity threshold (normalize scores to 0-1 range for comparison)
        if effective_threshold > 0:
            before_filter_count = len(contexts)
            # OpenSearch kNN scores vary; normalize by max score for threshold comparison
            max_score = max((c.score for c in contexts), default=1.0)
            if max_score > 0:
                contexts = [c for c in contexts if (c.score / max_score) >= effective_threshold]
            
            logger.info(
                "fasb_threshold_filter",
                original_count=before_filter_count,
                threshold=effective_threshold,
                filtered_count=len(contexts)
            )
        
        if not contexts:
            return {
                "answer": "I found some results but none met the relevance threshold. Try rephrasing your question or lowering the similarity threshold.",
                "sources": [],
                "query": query,
                "source_filter": source_filter or "all",
                "knowledge_base_ids": self._normalize_knowledge_base_ids(knowledge_base_ids),
                "contexts_retrieved": 0,
                "contexts_used": 0,
                "model": self.chat_model
            }
        
        # C) Rerank to best chunks (use rewritten query for better relevance)
        # Override rerank_keep with effective_top_k for this request
        original_rerank_keep = self.rerank_keep
        self.rerank_keep = effective_top_k
        contexts = self.rerank(rewritten_query, contexts)
        self.rerank_keep = original_rerank_keep
        
        # C) Build numbered context block for stable citations
        context_block = "\n\n".join([
            f"[{i+1}] {c.citation}\n{c.text}" 
            for i, c in enumerate(contexts)
        ])
        
        # Load system prompt from Prompt Management (if available)
        system_prompt = self._get_managed_prompt("system", customer_id)
        if not system_prompt:
            system_prompt = """You are an assistant that answers questions about FASB Accounting Standards Codification (ASC).
Use ONLY the provided context. If the answer isn't in the context, say "I don't know."
When you state facts, cite sources like [1], [2] referring to the numbered context items.

FORMATTING RULES:
- Use **bold** for key terms and requirements (e.g., **no preference**, **consistently**)
- Use bullet points (- ) when listing multiple requirements or items
- Keep answers clear, structured, and authoritative
- Cite sources inline where relevant [1], [2], etc."""
        
        # Always include the question + retrieved context in the user prompt.
        # The managed "synthesis" prompt is treated as additional instructions (it may or may not contain placeholders).
        # Conversation context is included so the LLM can understand follow-ups,
        # but it is NOT part of embedding/retrieval (that uses only the clean query).
        conversation_section = ""
        if conversation_context:
            conversation_section = f"\nConversation History:\n{conversation_context}\n"

        base_user_prompt = f"""Question:
{original_question}
{conversation_section}
Authoritative Context (cite using [1], [2], etc.):
{context_block}
"""

        synthesis_prompt = self._get_managed_prompt("synthesis", customer_id)
        if synthesis_prompt:
            synthesis_instructions = self._render_prompt_template(
                synthesis_prompt,
                question=original_question,
                context=context_block,
                query=original_question,
                rewritten_query=rewritten_query,
            ).strip()
            user_prompt = f"""{synthesis_instructions}

{base_user_prompt}

Provide a clear, well-cited answer:"""
        else:
            user_prompt = f"""{base_user_prompt}

Provide a clear, well-cited answer:"""
        
        # D) Generate answer
        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0
            )
            
            answer_text = response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}", exc_info=True)
            raise ValueError(f"Answer generation failed: {str(e)}")
        
        # E) Extract which citations are actually used in the answer
        # Find all [N] references in the answer text
        used_indices = set()
        for match in re.finditer(r'\[(\d+)\]', answer_text):
            idx = int(match.group(1))
            if 1 <= idx <= len(contexts):
                used_indices.add(idx)
        
        # Sort to maintain order
        used_indices = sorted(used_indices)
        
        # If no citations found, include top 3 as fallback
        if not used_indices:
            used_indices = list(range(1, min(4, len(contexts) + 1)))
        
        # F) Build mapping from old index to new index and filter contexts
        old_to_new = {old_idx: new_idx for new_idx, old_idx in enumerate(used_indices, start=1)}
        used_contexts = [contexts[idx - 1] for idx in used_indices]
        
        # G) Renumber citations in answer text
        def replace_citation(match):
            old_idx = int(match.group(1))
            if old_idx in old_to_new:
                return f"[{old_to_new[old_idx]}]"
            return match.group(0)  # Keep unchanged if not in our map
        
        renumbered_answer = re.sub(r'\[(\d+)\]', replace_citation, answer_text)
        
        # H) Build sources list with new indices
        sources = [
            {"index": i+1, "citation": c.citation, "text_preview": c.text[:200] + "..."}
            for i, c in enumerate(used_contexts)
        ]
        
        # I) Append sources section to the answer
        sources_section = "\n\nSources:\n" + "\n".join([
            f"[{i+1}] {c.citation}" for i, c in enumerate(used_contexts)
        ])
        answer_with_sources = renumbered_answer + sources_section
        
        result = {
            "answer": answer_with_sources,
            "sources": sources,
            "query": original_question,
            "rewritten_query": rewritten_query,
            "source_filter": source_filter or "all",
            "knowledge_base_ids": self._normalize_knowledge_base_ids(knowledge_base_ids),
            "contexts_retrieved": len(contexts),
            "contexts_used": len(used_contexts),
            "model": self.chat_model
        }
        
        logger.info(
            "fasb_answer_generated",
            query_length=len(original_question),
            answer_length=len(renumbered_answer),
            sources_count=len(sources),
            original_contexts=len(contexts),
            source_filter=source_filter or "all",
            knowledge_base_ids=self._normalize_knowledge_base_ids(knowledge_base_ids),
            used_citations=used_indices
        )
        
        return result

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

    def _rewrite_query(
        self,
        question: str,
        customer_id: Optional[str] = None,
        conversation_context: Optional[str] = None,
    ) -> str:
        """
        Rewrite the user's question for retrieval using the managed query_rewrite prompt.
        If no prompt exists but conversation context is provided, attempts a lightweight
        coreference resolution so follow-up questions like "tell me more about that"
        produce a standalone search query.
        If neither a managed prompt nor conversation context exist, returns the
        original question unchanged.
        """
        prompt = self._get_managed_prompt("query_rewrite", customer_id)

        if not prompt and not conversation_context:
            return question

        if prompt:
            rendered = self._render_prompt_template(
                prompt,
                question=question,
                query=question,
                conversation_context=conversation_context or "",
            )
        else:
            # Lightweight built-in coreference resolution when no managed prompt
            # is configured but we have conversation history.
            rendered = (
                "You are a search-query rewriter. Given the conversation history "
                "and the latest user question, produce a single standalone search "
                "query that captures the user's intent without relying on prior "
                "context.  Output ONLY the rewritten query, nothing else.\n\n"
                f"Conversation history:\n{conversation_context}\n\n"
                f"Latest question: {question}\n\n"
                "Standalone search query:"
            )

        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
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

            # Heuristic parsing: many query-rewrite prompts output multiple queries/bullets.
            # Extract the "best" query line(s) and join a few for better recall.
            lines = [l.strip() for l in rewritten.splitlines() if l.strip()]

            def normalize_line(line: str) -> str:
                # Remove bullets / numbering prefixes
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
                # Skip lines that are obviously meta
                if "provide" in low and "query" in low:
                    continue
                if len(l) < 6:
                    continue
                candidates.append(l)

            if not candidates:
                return question

            # Prefer longer, more specific candidates
            candidates = sorted(candidates, key=lambda s: len(s), reverse=True)
            merged = " ; ".join(candidates[:3]).strip()
            # Bound length to keep embedding reasonable
            merged = merged[:512]
            return merged or question
        except Exception as e:
            logger.warning(f"Query rewrite failed, using original question: {e}")
            return question
    
    def get_index_stats(self, source_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about configured FASB OpenSearch source(s).
        
        Returns:
            Dict with document_count, chunk_count, and health info
        """
        selected_sources = self._selected_sources(source_filter)
        total_chunk_count = 0
        total_document_count = 0
        source_stats: List[Dict[str, Any]] = []
        source_errors: List[str] = []

        for source_cfg in selected_sources:
            try:
                count_url = f"https://{source_cfg.host}/{source_cfg.index}/_count"
                response = requests.get(
                    count_url,
                    auth=self._get_aws_auth(source_cfg.region),
                    headers={"Content-Type": "application/json"},
                    data=json.dumps({"query": {"bool": {"filter": [{"term": {"is_superseded": False}}]}}}),
                    timeout=30
                )
                response.raise_for_status()
                count_data = response.json()
                chunk_count = int(count_data.get("count", 0) or 0)

                # Get unique document count per source
                doc_count_url = f"https://{source_cfg.host}/{source_cfg.index}/_search"
                doc_body = {
                    "size": 0,
                    "query": {"bool": {"filter": [{"term": {"is_superseded": False}}]}},
                    "aggs": {"unique_docs": {"cardinality": {"field": "doc_id"}}}
                }
                doc_response = requests.get(
                    doc_count_url,
                    auth=self._get_aws_auth(source_cfg.region),
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(doc_body),
                    timeout=30
                )
                doc_response.raise_for_status()
                doc_data = doc_response.json()
                document_count = int(doc_data.get("aggregations", {}).get("unique_docs", {}).get("value", 0) or 0)

                total_chunk_count += chunk_count
                total_document_count += document_count
                source_stats.append(
                    {
                        "name": source_cfg.name,
                        "status": "healthy",
                        "host": source_cfg.host,
                        "index": source_cfg.index,
                        "region": source_cfg.region,
                        "document_count": document_count,
                        "chunk_count": chunk_count,
                    }
                )
            except Exception as e:
                source_errors.append(f"{source_cfg.name}: {str(e)}")
                source_stats.append(
                    {
                        "name": source_cfg.name,
                        "status": "unhealthy",
                        "host": source_cfg.host,
                        "index": source_cfg.index,
                        "region": source_cfg.region,
                        "document_count": 0,
                        "chunk_count": 0,
                        "error": str(e),
                    }
                )

        healthy_sources = [s for s in source_stats if s.get("status") == "healthy"]
        if not healthy_sources:
            error = "; ".join(source_errors) if source_errors else "No healthy FASB sources configured"
            logger.error("fasb_index_stats_failed", error=error)
            return {
                "error": error,
                "document_count": 0,
                "chunk_count": 0,
                "host": self.host,
                "index": ",".join([s.index for s in selected_sources]),
                "region": ",".join(sorted({s.region for s in selected_sources})),
                "status": "unhealthy",
                "source_filter": source_filter or "all",
                "sources": source_stats,
            }

        result: Dict[str, Any] = {
            "document_count": total_document_count,
            "chunk_count": total_chunk_count,
            "host": self.host,
            "index": ",".join([s.index for s in selected_sources]),
            "region": ",".join(sorted({s.region for s in selected_sources})),
            "status": "healthy" if not source_errors else "degraded",
            "source_filter": source_filter or "all",
            "sources": source_stats,
        }
        if source_errors:
            result["errors"] = source_errors
        return result
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check FASB service health including OpenSearch and OpenAI connectivity.
        
        Returns:
            Dict with health status for each component
        """
        result = {
            "status": "healthy",
            "components": {}
        }
        
        # Check OpenSearch connectivity
        try:
            stats = self.get_index_stats()
            result["components"]["opensearch"] = {
                "status": stats.get("status", "unknown"),
                "host": stats.get("host", self.host),
                "index": stats.get("index", self.index),
                "chunk_count": stats.get("chunk_count", 0),
                "document_count": stats.get("document_count", 0),
                "sources": stats.get("sources", []),
            }
            if stats.get("status") != "healthy":
                result["status"] = "degraded"
                result["components"]["opensearch"]["error"] = stats.get("error") or stats.get("errors")
        except Exception as e:
            result["status"] = "unhealthy"
            result["components"]["opensearch"] = {
                "status": "unhealthy",
                "error": str(e),
                "host": self.host,
                "index": self.index,
            }
        
        # Check AWS credentials
        try:
            import os
            has_env_creds = bool(os.environ.get('AWS_ACCESS_KEY_ID') and os.environ.get('AWS_SECRET_ACCESS_KEY'))
            configured_regions = sorted({s.region for s in self._selected_sources("all")})
            result["components"]["aws_credentials"] = {
                "status": "configured" if has_env_creds else "using_boto3_session",
                "regions": configured_regions,
            }
        except Exception as e:
            result["components"]["aws_credentials"] = {
                "status": "error",
                "error": str(e),
            }
        
        # Check OpenAI connectivity (embedding)
        try:
            # Quick test with a short string
            self._embed_query("test")
            result["components"]["openai_embeddings"] = {
                "status": "healthy",
                "model": self.embed_model,
            }
        except Exception as e:
            result["status"] = "unhealthy"
            result["components"]["openai_embeddings"] = {
                "status": "unhealthy",
                "error": str(e),
                "model": self.embed_model,
            }
        
        return result
    
    def process_message(
        self, 
        question: str, 
        conversation_context: Optional[str] = None,
        customer_id: Optional[str] = None,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        source_filter: Optional[str] = None,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Process a FASB message and return formatted results.
        
        This method is called for FASB domain queries (via DataAnalystService or ragflow endpoints).
        
        Args:
            question: User's question
            conversation_context: Optional previous conversation context for follow-up questions
            customer_id: Customer ID for loading managed prompts
            top_k: Override for number of sources to return
            similarity_threshold: Minimum similarity score 0-1
            source_filter: Optional retrieval source filter (all | primary | memo)
            knowledge_base_ids: Optional knowledge base scope filter
            
        Returns:
            Dict with result_data and result_metadata in the same format as Insurance domain
        """
        # Pass conversation context separately so retrieval uses only the
        # clean question for embedding.  Context is forwarded to the LLM
        # synthesis step and (optionally) to query rewriting for coreference
        # resolution, but never embedded directly.
        rag_result = self.answer(
            question,
            customer_id=customer_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            source_filter=source_filter,
            knowledge_base_ids=knowledge_base_ids,
            conversation_context=conversation_context,
        )
        
        # Format as result_data (similar to SQL query results format)
        result_data = {
            "columns": ["answer", "sources"],
            "rows": [[rag_result["answer"], json.dumps(rag_result["sources"])]],
            "row_count": 1,
            "type": "rag_response"
        }
        
        # Format as result_metadata (similar to insights format)
        result_metadata = {
            "summary": rag_result["answer"],
            "sources": rag_result["sources"],
            "key_findings": [
                f"Found {rag_result['contexts_used']} relevant ASC passages",
                f"Answer generated using {rag_result['model']}"
            ],
            "statistics": {
                "contexts_retrieved": rag_result["contexts_retrieved"],
                "contexts_used": rag_result["contexts_used"],
                "model": rag_result["model"],
                "source_filter": rag_result.get("source_filter", source_filter or "all"),
                "knowledge_base_ids": rag_result.get("knowledge_base_ids", self._normalize_knowledge_base_ids(knowledge_base_ids)),
            },
            "chart_suggestions": [],  # RAG responses don't have charts
            "anomalies": [],
            "recommendations": [
                "For more details, reference the cited ASC passages directly",
                "Ask follow-up questions about specific guidance"
            ],
            "domain": "fasb",
            "query_type": "rag"
        }
        
        return {
            "result_data": result_data,
            "result_metadata": result_metadata
        }


# Singleton instance
_fasb_service_instance: Optional[FASBService] = None


def get_fasb_service() -> FASBService:
    """Get singleton FASB service instance."""
    global _fasb_service_instance
    if _fasb_service_instance is None:
        _fasb_service_instance = FASBService()
    return _fasb_service_instance
