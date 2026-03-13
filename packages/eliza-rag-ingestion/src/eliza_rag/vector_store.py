"""
Vector Store - AWS OpenSearch Serverless or local Elasticsearch for RAG.

Supports:
- AWS OpenSearch Serverless (AOSS) with SigV4 authentication
- Local Elasticsearch for development

Terraform / IAM alignment (when using Terraform-managed OpenSearch):
- Index naming: Uses index_prefix + normalized domain_id. Set RAG_OPENSEARCH_INDEX_PREFIX
  to match Terraform (e.g. output from Terraform). Index names are normalized to
  OpenSearch Serverless rules: lowercase, [a-z0-9_-], cannot start with _ or -.
- Endpoint: Set RAG_OPENSEARCH_HOST to the AOSS collection endpoint (Terraform output).
- Region: RAG_OPENSEARCH_REGION must match the collection region.
- IAM: App uses default boto3 credential chain (env, instance role, etc.). Terraform
  must attach a data access policy to the app's IAM principal granting access to the
  OpenSearch Serverless collection (and index pattern if using fine-grained access).
"""

import asyncio
import logging
import re
import requests
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# OpenSearch Serverless index name rules: lowercase, [a-z0-9_-], cannot start with _ or -
_OPENSEARCH_INDEX_MAX_LENGTH = 255
_OPENSEARCH_INDEX_INVALID_CHAR = re.compile(r"[^a-z0-9_-]")
_OPENSEARCH_INDEX_LEADING_STRIP = re.compile(r"^[-_]+")


@dataclass
class VectorDocument:
    """Document with vector embedding for storage."""
    id: str
    domain_id: str
    knowledge_base_id: Optional[str]
    document_id: str
    chunk_index: int
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    hypothetical_questions: Optional[List[str]] = None


@dataclass
class VectorSearchResult:
    """Search result from vector store."""
    id: str
    document_id: str
    chunk_index: int
    text: str
    score: float
    metadata: Dict[str, Any]


class VectorStore:
    """
    Vector storage for RAG using AWS OpenSearch Serverless or local Elasticsearch.
    
    For AWS OpenSearch Serverless:
    - Uses SigV4 authentication via boto3
    - Requires AWS credentials in environment
    
    For local Elasticsearch:
    - Standard Elasticsearch client
    """
    
    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        index_prefix: str = "rag_domains",
        dimensions: int = 1536,
        similarity: str = "cosine",
        opensearch_host: Optional[str] = None,
        opensearch_region: str = "us-east-1",
        use_local: bool = False
    ):
        """
        Initialize vector store.
        
        Args:
            hosts: Local Elasticsearch hosts (for local mode)
            index_prefix: Prefix for index names
            dimensions: Vector dimensions
            similarity: Similarity metric (cosine, dot_product, l2_norm)
            opensearch_host: AWS OpenSearch Serverless host
            opensearch_region: AWS region
            use_local: Use local Elasticsearch instead of AWS
        """
        self.hosts = hosts or ["http://localhost:9200"]
        self.index_prefix = self._normalize_index_prefix(index_prefix)
        self.dimensions = dimensions
        self.similarity = similarity
        self.opensearch_host = opensearch_host
        self.opensearch_region = opensearch_region
        self.use_local = use_local or not opensearch_host

        self._client = None
        self._aws_auth = None

    _ASC_REFERENCE_PATTERN = re.compile(r"\b\d{3}-\d{1,2}(?:-\d{2}(?:-\d+)?)?\b")

    @classmethod
    def _extract_reference_tokens(cls, query: str) -> List[str]:
        """Extract ASC-style numeric references from query text."""
        if not query:
            return []
        seen = set()
        refs: List[str] = []
        for match in cls._ASC_REFERENCE_PATTERN.finditer(query):
            token = match.group(0)
            if token not in seen:
                seen.add(token)
                refs.append(token)
        refs.sort(key=lambda token: (token.count("-"), len(token)), reverse=True)
        return refs[:5]
    
    @property
    def aws_auth(self):
        """Lazily initialize AWS SigV4 auth for OpenSearch Serverless."""
        if self._aws_auth is None and not self.use_local:
            try:
                import boto3
                from requests_aws4auth import AWS4Auth
                
                session = boto3.Session(region_name=self.opensearch_region)
                creds = session.get_credentials().get_frozen_credentials()
                self._aws_auth = AWS4Auth(
                    creds.access_key,
                    creds.secret_key,
                    self.opensearch_region,
                    "aoss",  # OpenSearch Serverless service
                    session_token=creds.token
                )
                logger.info(f"AWS SigV4 auth initialized for OpenSearch: {self.opensearch_host}")
            except Exception as e:
                logger.error(f"Failed to initialize AWS auth: {e}")
                raise
        return self._aws_auth
    
    def _get_client(self):
        """Lazy-load Elasticsearch client (for local mode only)."""
        if self._client is None and self.use_local:
            from elasticsearch import Elasticsearch
            self._client = Elasticsearch(
                hosts=self.hosts,
                verify_certs=False,
                ssl_show_warn=False,
                request_timeout=10,  # 10s timeout to prevent indefinite hangs
            )
            logger.info(f"Connected to local Elasticsearch: {self.hosts}")
        return self._client
    
    def _opensearch_url(self, path: str) -> str:
        """Build OpenSearch Serverless URL."""
        return f"https://{self.opensearch_host}/{path}"

    @staticmethod
    def _normalize_index_prefix(prefix: str) -> str:
        """Normalize index prefix for OpenSearch Serverless: lowercase, [a-z0-9_-], no leading _ or -."""
        if not prefix:
            return "rag_domains"
        s = prefix.lower().strip()
        s = _OPENSEARCH_INDEX_INVALID_CHAR.sub("_", s)
        s = _OPENSEARCH_INDEX_LEADING_STRIP.sub("", s) or "rag"
        return s[: _OPENSEARCH_INDEX_MAX_LENGTH]

    @staticmethod
    def _normalize_index_suffix(domain_id: str) -> str:
        """Normalize domain_id for use in index name: lowercase, [a-z0-9_-], no leading _ or -."""
        if not domain_id:
            return "default"
        s = str(domain_id).lower().strip()
        s = _OPENSEARCH_INDEX_INVALID_CHAR.sub("_", s)
        s = _OPENSEARCH_INDEX_LEADING_STRIP.sub("", s) or "default"
        return s[: _OPENSEARCH_INDEX_MAX_LENGTH]

    def _get_index_name(self, domain_id: str) -> str:
        """Get index name for a domain. Safe for OpenSearch Serverless (lowercase, [a-z0-9_-])."""
        suffix = self._normalize_index_suffix(domain_id)
        full = f"{self.index_prefix}_{suffix}"
        if len(full) > _OPENSEARCH_INDEX_MAX_LENGTH:
            full = full[: _OPENSEARCH_INDEX_MAX_LENGTH]
        return full

    @staticmethod
    def _build_filter_clauses(
        *,
        knowledge_base_ids: Optional[List[int]] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Build OpenSearch/Elasticsearch filter clauses."""
        clauses: List[Dict[str, Any]] = []

        if knowledge_base_ids:
            kb_ids = [str(kb_id) for kb_id in knowledge_base_ids]
            clauses.append({"terms": {"knowledge_base_id": kb_ids}})

        if filter_metadata:
            for key, value in filter_metadata.items():
                field = f"metadata.{key}"
                if isinstance(value, (list, tuple, set)):
                    clauses.append({"terms": {field: list(value)}})
                else:
                    clauses.append({"term": {field: value}})

        return clauses
    
    async def create_index(self, domain_id: str) -> bool:
        """
        Create vector index for a domain.
        
        WARNING: Uses synchronous ES/OpenSearch calls. If called from an async
        context under load, consider wrapping with run_in_executor (see get_stats).
        
        Args:
            domain_id: Domain identifier
            
        Returns:
            True if created successfully
        """
        index_name = self._get_index_name(domain_id)
        
        # OpenSearch Serverless mapping (knn_vector type)
        mappings = {
            "properties": {
                "domain_id": {"type": "keyword"},
                "knowledge_base_id": {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
                "text": {"type": "text"},
                "hypothetical_questions": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": self.dimensions,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "faiss"
                    }
                },
                "metadata": {
                    "type": "object",
                    "enabled": True,
                    "properties": {
                        "filename": {"type": "keyword"},
                        "chunk_type": {"type": "keyword"},
                        "document_type": {"type": "keyword"},
                        "document_title": {"type": "text"},
                        "chunk_summary": {"type": "text"},
                        "key_entities": {"type": "keyword"},
                        "knowledge_base_name": {"type": "keyword"},
                        "workspace_name": {"type": "keyword"},
                        "page_number": {"type": "integer"},
                        "section_title": {"type": "text"},
                        "heading_context": {"type": "text"},
                        "section_hierarchy": {"type": "keyword"},
                        "has_table": {"type": "boolean"},
                        "has_code": {"type": "boolean"},
                        "has_list": {"type": "boolean"},
                        "language": {"type": "keyword"},
                    },
                },
                "created_at": {"type": "date"}
            }
        }
        
        if self.use_local:
            # Local Elasticsearch - no kNN plugin, use dense_vector
            client = self._get_client()
            try:
                if client.indices.exists(index=index_name):
                    return True
                
                local_mappings = {
                    "properties": {
                        "domain_id": {"type": "keyword"},
                        "knowledge_base_id": {"type": "keyword"},
                        "document_id": {"type": "keyword"},
                        "chunk_index": {"type": "integer"},
                        "text": {"type": "text"},
                        "hypothetical_questions": {"type": "text"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": self.dimensions,
                            "index": True,
                            "similarity": self.similarity
                        },
                        "metadata": {
                            "type": "object",
                            "enabled": True,
                            "properties": {
                                "filename": {"type": "keyword"},
                                "chunk_type": {"type": "keyword"},
                                "document_type": {"type": "keyword"},
                                "document_title": {"type": "text"},
                                "chunk_summary": {"type": "text"},
                                "key_entities": {"type": "keyword"},
                                "knowledge_base_name": {"type": "keyword"},
                                "workspace_name": {"type": "keyword"},
                                "page_number": {"type": "integer"},
                                "section_title": {"type": "text"},
                                "heading_context": {"type": "text"},
                                "section_hierarchy": {"type": "keyword"},
                                "has_table": {"type": "boolean"},
                                "has_code": {"type": "boolean"},
                                "has_list": {"type": "boolean"},
                                "language": {"type": "keyword"},
                            },
                        },
                        "created_at": {"type": "date"}
                    }
                }
                client.indices.create(index=index_name, mappings=local_mappings)
                logger.info(f"Created local index: {index_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to create local index: {e}")
                raise
        else:
            # AWS OpenSearch Serverless - uses knn_vector type
            opensearch_settings = {"index.knn": True}
            
            try:
                # Check if exists
                url = self._opensearch_url(index_name)
                resp = requests.head(url, auth=self.aws_auth)
                if resp.status_code == 200:
                    return True
                
                # Create index with kNN enabled
                body = {"mappings": mappings, "settings": opensearch_settings}
                resp = requests.put(url, json=body, auth=self.aws_auth)
                if resp.status_code in [200, 201]:
                    logger.info(f"Created OpenSearch index: {index_name}")
                    return True
                else:
                    logger.error(f"Failed to create index: {resp.status_code} - {resp.text}")
                    raise Exception(f"Index creation failed: {resp.text}")
            except Exception as e:
                logger.error(f"Failed to create OpenSearch index: {e}")
                raise
    
    async def delete_index(self, domain_id: str) -> bool:
        """Delete vector index for a domain.
        
        WARNING: Uses synchronous ES/OpenSearch calls. If called from an async
        context under load, consider wrapping with run_in_executor (see get_stats).
        """
        index_name = self._get_index_name(domain_id)
        
        if self.use_local:
            client = self._get_client()
            try:
                if client.indices.exists(index=index_name):
                    client.indices.delete(index=index_name)
                    logger.info(f"Deleted local index: {index_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete local index: {e}")
                raise
        else:
            try:
                url = self._opensearch_url(index_name)
                resp = requests.delete(url, auth=self.aws_auth)
                if resp.status_code in [200, 404]:
                    logger.info(f"Deleted OpenSearch index: {index_name}")
                    return True
                else:
                    raise Exception(f"Delete failed: {resp.text}")
            except Exception as e:
                logger.error(f"Failed to delete OpenSearch index: {e}")
                raise
    
    async def index_documents(
        self,
        domain_id: str,
        documents: List[VectorDocument]
    ) -> int:
        """
        Index multiple documents with embeddings.
        
        WARNING: Uses synchronous ES/OpenSearch calls. If called from an async
        context under load, consider wrapping with run_in_executor (see get_stats).
        
        Args:
            domain_id: Domain identifier
            documents: Documents to index
            
        Returns:
            Number of documents indexed
        """
        if not documents:
            return 0
        
        index_name = self._get_index_name(domain_id)
        
        # Ensure index exists
        await self.create_index(domain_id)
        
        from datetime import datetime
        
        if self.use_local:
            # Local Elasticsearch bulk
            client = self._get_client()
            operations = []
            for doc in documents:
                operations.append({"index": {"_index": index_name, "_id": doc.id}})
                doc_body: Dict[str, Any] = {
                    "domain_id": doc.domain_id,
                    "knowledge_base_id": doc.knowledge_base_id,
                    "document_id": doc.document_id,
                    "chunk_index": doc.chunk_index,
                    "text": doc.text,
                    "embedding": doc.embedding,
                    "metadata": doc.metadata,
                    "created_at": datetime.utcnow().isoformat(),
                }
                if doc.hypothetical_questions:
                    doc_body["hypothetical_questions"] = " ".join(doc.hypothetical_questions)
                operations.append(doc_body)
            
            try:
                response = client.bulk(operations=operations, refresh=True)
                success_count = sum(1 for item in response["items"] if item.get("index", {}).get("result") in ["created", "updated"])
                logger.info(f"Indexed {success_count} documents to local {index_name}")
                return success_count
            except Exception as e:
                logger.error(f"Local bulk index failed: {e}")
                raise
        else:
            # AWS OpenSearch Serverless bulk
            bulk_body = ""
            for doc in documents:
                action = {"index": {"_index": index_name}}
                document: Dict[str, Any] = {
                    "domain_id": doc.domain_id,
                    "knowledge_base_id": doc.knowledge_base_id,
                    "document_id": doc.document_id,
                    "chunk_index": doc.chunk_index,
                    "text": doc.text,
                    "embedding": doc.embedding,
                    "metadata": doc.metadata,
                    "created_at": datetime.utcnow().isoformat(),
                }
                if doc.hypothetical_questions:
                    document["hypothetical_questions"] = " ".join(doc.hypothetical_questions)
                import json
                bulk_body += json.dumps(action) + "\n" + json.dumps(document) + "\n"
            
            try:
                url = self._opensearch_url("_bulk")
                headers = {"Content-Type": "application/x-ndjson"}
                resp = requests.post(url, data=bulk_body, auth=self.aws_auth, headers=headers)
                
                if resp.status_code != 200:
                    raise Exception(f"Bulk failed: {resp.text}")
                
                result = resp.json()
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
                        error_type = error_info.get("type", "unknown_error")
                        reason = error_info.get("reason", "unknown_reason")
                    else:
                        error_type = "unknown_error"
                        reason = str(error_info)
                    failures.append(f"status={status} type={error_type} reason={reason}")

                if failures:
                    logger.error(
                        "OpenSearch bulk index had %s failures (success=%s/%s). First errors: %s",
                        len(failures),
                        success_count,
                        len(items),
                        failures[:3],
                    )

                if success_count == 0:
                    raise Exception(
                        "OpenSearch bulk indexing failed with zero successful items. "
                        + ("; ".join(failures[:3]) if failures else "No successful results returned.")
                    )

                logger.info(
                    "Indexed %s/%s documents to OpenSearch %s",
                    success_count,
                    len(items),
                    index_name,
                )
                return success_count
            except Exception as e:
                logger.error(f"OpenSearch bulk index failed: {e}")
                raise
    
    async def delete_document_chunks(
        self,
        domain_id: str,
        document_id: str
    ) -> int:
        """
        Delete all chunks for a document.
        
        WARNING: Uses synchronous ES/OpenSearch calls. If called from an async
        context under load, consider wrapping with run_in_executor (see get_stats).
        
        Args:
            domain_id: Domain identifier
            document_id: Document to delete chunks for
            
        Returns:
            Number of chunks deleted
        """
        index_name = self._get_index_name(domain_id)
        query = {"query": {"term": {"document_id": document_id}}}
        
        if self.use_local:
            client = self._get_client()
            try:
                response = client.delete_by_query(index=index_name, body=query, refresh=True)
                deleted = response.get("deleted", 0)
                logger.info(f"Deleted {deleted} chunks for document {document_id}")
                return deleted
            except Exception as e:
                logger.error(f"Failed to delete document chunks: {e}")
                raise
        else:
            try:
                url = self._opensearch_url(f"{index_name}/_delete_by_query")
                resp = requests.post(url, json=query, auth=self.aws_auth)
                if resp.status_code == 200:
                    deleted = resp.json().get("deleted", 0)
                    logger.info(f"Deleted {deleted} chunks from OpenSearch")
                    return deleted
                return 0
            except Exception as e:
                logger.error(f"OpenSearch delete failed: {e}")
                raise
    
    async def search(
        self,
        domain_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        min_score: float = 0.0,
        filter_metadata: Optional[Dict[str, Any]] = None,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> List[VectorSearchResult]:
        """
        Search for similar documents using kNN.
        
        WARNING: Uses synchronous ES/OpenSearch calls. If called from an async
        context under load, consider wrapping with run_in_executor (see get_stats).
        
        Args:
            domain_id: Domain to search in
            query_embedding: Query vector
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1 for cosine)
            filter_metadata: Optional metadata filters
            
        Returns:
            List of search results sorted by similarity
        """
        index_name = self._get_index_name(domain_id)
        
        if self.use_local:
            # Local Elasticsearch kNN
            client = self._get_client()
            
            if not client.indices.exists(index=index_name):
                logger.warning(f"Index {index_name} does not exist")
                return []
            
            knn_query: Dict[str, Any] = {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": top_k,
                "num_candidates": top_k * 10
            }

            filter_clauses = self._build_filter_clauses(
                knowledge_base_ids=knowledge_base_ids,
                filter_metadata=filter_metadata,
            )
            if filter_clauses:
                knn_query["filter"] = {"bool": {"must": filter_clauses}}
            
            try:
                response = client.search(
                    index=index_name,
                    knn=knn_query,
                    size=top_k,
                    source=["document_id", "chunk_index", "text", "metadata", "hypothetical_questions"]
                )
                return self._parse_search_results(response, min_score)
            except Exception as e:
                logger.error(f"Local search failed: {e}")
                raise
        else:
            # AWS OpenSearch Serverless kNN
            body = {
                "size": top_k,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": top_k
                        }
                    }
                },
                "_source": ["document_id", "chunk_index", "text", "metadata", "hypothetical_questions"]
            }
            
            # Add filters if provided
            filter_clauses = self._build_filter_clauses(
                knowledge_base_ids=knowledge_base_ids,
                filter_metadata=filter_metadata,
            )
            if filter_clauses:
                body["query"] = {
                    "bool": {
                        "must": [body["query"]],
                        "filter": filter_clauses
                    }
                }
            
            try:
                url = self._opensearch_url(f"{index_name}/_search")
                resp = requests.post(url, json=body, auth=self.aws_auth)
                
                if resp.status_code != 200:
                    logger.error(f"OpenSearch search failed: {resp.text}")
                    return []
                
                return self._parse_search_results(resp.json(), min_score)
            except Exception as e:
                logger.error(f"OpenSearch search failed: {e}")
                raise
    
    async def keyword_search(
        self,
        domain_id: str,
        query: str,
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> List[VectorSearchResult]:
        """
        Keyword-based text search (BM25).
        
        Useful for exact matches like section numbers, names, etc.
        
        WARNING: Uses synchronous ES/OpenSearch calls. If called from an async
        context under load, consider wrapping with run_in_executor (see get_stats).
        """
        index_name = self._get_index_name(domain_id)
        reference_tokens = self._extract_reference_tokens(query)

        should_clauses: List[Dict[str, Any]] = [
            # High precision: exact phrase in text.
            {"match_phrase": {"text": {"query": query, "boost": 4.0}}},
            # Medium precision: all terms should appear.
            {"match": {"text": {"query": query, "operator": "and", "boost": 2.0}}},
            # Broad recall fallback.
            {"match": {"text": {"query": query, "operator": "or", "boost": 1.0}}},
            # HyDE: match hypothetical questions generated during enrichment.
            {"match": {"hypothetical_questions": {"query": query, "boost": 3.0}}},
            # Match chunk summaries and entities.
            {"match": {"metadata.chunk_summary": {"query": query, "boost": 1.5}}},
            {"match": {"metadata.key_entities": {"query": query, "boost": 2.0}}},
        ]

        # Explicitly boost exact ASC references (e.g. 272-10-05-6).
        for token in reference_tokens:
            should_clauses.append(
                {"match_phrase": {"text": {"query": token, "boost": 8.0}}}
            )
        
        filter_clauses = self._build_filter_clauses(
            knowledge_base_ids=knowledge_base_ids,
            filter_metadata=filter_metadata,
        )

        if self.use_local:
            client = self._get_client()
            
            if not client.indices.exists(index=index_name):
                return []
            
            body = {
                "query": {
                    "bool": {
                        "should": should_clauses,
                        "minimum_should_match": 1,
                        "filter": filter_clauses,
                    }
                },
                "size": top_k,
                "_source": ["document_id", "chunk_index", "text", "metadata", "hypothetical_questions"]
            }
            
            try:
                response = client.search(index=index_name, body=body)
                return self._parse_search_results(response, min_score=0)
            except Exception as e:
                logger.error(f"Keyword search failed: {e}")
                return []
        else:
            # AWS OpenSearch
            body = {
                "query": {
                    "bool": {
                        "should": should_clauses,
                        "minimum_should_match": 1,
                        "filter": filter_clauses,
                    }
                },
                "size": top_k,
                "_source": ["document_id", "chunk_index", "text", "metadata", "hypothetical_questions"]
            }
            
            try:
                url = self._opensearch_url(f"{index_name}/_search")
                resp = requests.post(url, json=body, auth=self.aws_auth)
                
                if resp.status_code != 200:
                    logger.error(f"Keyword search failed: {resp.text}")
                    return []
                
                return self._parse_search_results(resp.json(), min_score=0)
            except Exception as e:
                logger.error(f"Keyword search failed: {e}")
                return []
    
    def _parse_search_results(self, response: dict, min_score: float) -> List[VectorSearchResult]:
        """Parse search response into VectorSearchResult objects."""
        results = []
        hits = response.get("hits", {}).get("hits", [])
        
        for hit in hits:
            score = hit.get("_score", 0)
            if score < min_score:
                continue
            
            source = hit.get("_source", {})
            results.append(VectorSearchResult(
                id=hit["_id"],
                document_id=source.get("document_id", ""),
                chunk_index=source.get("chunk_index", 0),
                text=source.get("text", ""),
                score=score,
                metadata=source.get("metadata", {})
            ))
        
        return results
    
    def _get_local_stats_sync(self, index_name: str) -> Dict[str, Any]:
        """Synchronous helper for local Elasticsearch stats (runs in thread executor)."""
        client = self._get_client()
        if not client.indices.exists(index=index_name):
            return {"exists": False, "document_count": 0}
        
        stats = client.indices.stats(index=index_name)
        index_stats = stats["indices"][index_name]
        
        return {
            "exists": True,
            "document_count": index_stats["primaries"]["docs"]["count"],
            "size_bytes": index_stats["primaries"]["store"]["size_in_bytes"],
            "index_name": index_name
        }
    
    def _get_opensearch_stats_sync(self, index_name: str) -> Dict[str, Any]:
        """Synchronous helper for OpenSearch stats (runs in thread executor)."""
        url = self._opensearch_url(f"{index_name}/_stats")
        resp = requests.get(url, auth=self.aws_auth, timeout=10)
        
        if resp.status_code == 404:
            return {"exists": False, "document_count": 0}
        
        if resp.status_code == 200:
            data = resp.json()
            return {
                "exists": True,
                "document_count": data.get("_all", {}).get("primaries", {}).get("docs", {}).get("count", 0),
                "index_name": index_name
            }
        return {"exists": False, "error": resp.text}
    
    async def get_stats(self, domain_id: str) -> Dict[str, Any]:
        """Get statistics for a domain's vector index.
        
        Runs synchronous ES/OpenSearch calls in a thread executor
        to avoid blocking the async event loop.
        """
        index_name = self._get_index_name(domain_id)
        loop = asyncio.get_event_loop()
        
        if self.use_local:
            try:
                return await loop.run_in_executor(
                    None, self._get_local_stats_sync, index_name
                )
            except Exception as e:
                logger.error(f"Failed to get local stats: {e}")
                return {"exists": False, "error": str(e)}
        else:
            try:
                return await loop.run_in_executor(
                    None, self._get_opensearch_stats_sync, index_name
                )
            except Exception as e:
                logger.error(f"Failed to get OpenSearch stats: {e}")
                return {"exists": False, "error": str(e)}
