"""Document processing DAG — classify, preprocess, embed, and index.

Can be triggered by the sharepoint_sync DAG (via dataset) or run standalone
against files already in the S3 raw bucket.

Flow:
  list_new_files -> classify -> route -> [unstructured | structured | presentation | pdf] -> embed_and_index
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

from airflow.decorators import dag, task

from common.document_classifier import EXTENSION_MAP, DocCategory, classify
from common.s3_utils import (
    download_bytes,
    download_head_bytes,
    get_processed_bucket,
    get_raw_bucket,
    list_objects,
    upload_bytes,
)

logger = logging.getLogger(__name__)

DAG_ID = "document_pipeline"
DOMAIN_ID = os.environ.get("RAG_DOMAIN_ID", "default")

default_args = {
    "owner": "eliza",
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}


@dag(
    dag_id=DAG_ID,
    default_args=default_args,
    schedule=None,  # triggered externally or manually
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["rag", "ingestion", "preprocessing"],
    params={"s3_keys": [], "bucket": ""},
    doc_md=__doc__,
)
def document_pipeline():

    @task()
    def resolve_files(**context) -> list[dict]:
        """Resolve which S3 keys to process — from params or scan raw bucket."""
        params = context["params"]
        keys: list[str] = params.get("s3_keys", [])
        bucket = params.get("bucket") or get_raw_bucket()

        if not keys:
            objects = list_objects(bucket, prefix="sharepoint/")
            keys = [o["Key"] for o in objects]
            logger.info(f"Scanned raw bucket: {len(keys)} objects")

        return [{"bucket": bucket, "key": k} for k in keys]

    @task()
    def classify_file(file_ref: dict) -> dict:
        """Classify a single file and attach routing category."""
        bucket, key = file_ref["bucket"], file_ref["key"]
        filename = key.rsplit("/", 1)[-1]
        ext = os.path.splitext(filename)[1].lower()
        if ext in EXTENSION_MAP:
            # For known extensions, classification is deterministic without
            # downloading object bytes.
            result = classify(filename)
        else:
            head = download_head_bytes(bucket, key, size=1024)
            result = classify(filename, head_bytes=head)

        return {
            **file_ref,
            "filename": filename,
            "category": result.category.value,
            "mime_type": result.mime_type,
            "extension": result.extension,
        }

    @task()
    def route_by_category(classified_files: list[dict]) -> dict[str, list[dict]]:
        """Partition files into per-category lists for downstream processors."""
        routed: dict[str, list[dict]] = {
            DocCategory.UNSTRUCTURED.value: [],
            DocCategory.STRUCTURED.value: [],
            DocCategory.PRESENTATION.value: [],
            DocCategory.PDF.value: [],
            DocCategory.UNKNOWN.value: [],
        }
        for f in classified_files:
            cat = f.get("category", DocCategory.UNKNOWN.value)
            routed.setdefault(cat, []).append(f)
        for cat, items in routed.items():
            logger.info(f"Category {cat}: {len(items)} files")
        return routed

    @task()
    def process_unstructured(routed: dict[str, list[dict]]) -> list[dict]:
        from preprocessors.unstructured_preprocessor import preprocess_unstructured

        files = routed.get(DocCategory.UNSTRUCTURED.value, [])
        all_chunks: list[dict] = []
        for f in files:
            content = download_bytes(f["bucket"], f["key"])
            chunks = preprocess_unstructured(f["filename"], content)
            for chunk in chunks:
                key = f"processed/{f['key']}/chunk_{chunk['index']}.json"
                upload_bytes(get_processed_bucket(), key, json.dumps(chunk).encode())
            all_chunks.extend(chunks)
        return all_chunks

    @task()
    def process_structured(routed: dict[str, list[dict]]) -> list[dict]:
        from preprocessors.structured_preprocessor import preprocess_structured

        files = routed.get(DocCategory.STRUCTURED.value, [])
        all_chunks: list[dict] = []
        for f in files:
            content = download_bytes(f["bucket"], f["key"])
            chunks = preprocess_structured(f["filename"], content)
            for chunk in chunks:
                key = f"processed/{f['key']}/chunk_{chunk['index']}.json"
                upload_bytes(get_processed_bucket(), key, json.dumps(chunk).encode())
            all_chunks.extend(chunks)
        return all_chunks

    @task()
    def process_presentations(routed: dict[str, list[dict]]) -> list[dict]:
        from preprocessors.ppt_preprocessor import preprocess_ppt

        files = routed.get(DocCategory.PRESENTATION.value, [])
        all_chunks: list[dict] = []
        for f in files:
            content = download_bytes(f["bucket"], f["key"])
            chunks = preprocess_ppt(f["filename"], content)
            for chunk in chunks:
                key = f"processed/{f['key']}/chunk_{chunk['index']}.json"
                upload_bytes(get_processed_bucket(), key, json.dumps(chunk).encode())
            all_chunks.extend(chunks)
        return all_chunks

    @task()
    def process_pdfs(routed: dict[str, list[dict]]) -> list[dict]:
        from preprocessors.ocr_preprocessor import preprocess_pdf

        files = routed.get(DocCategory.PDF.value, [])
        all_chunks: list[dict] = []
        for f in files:
            content = download_bytes(f["bucket"], f["key"])
            chunks = preprocess_pdf(f["filename"], content)
            for chunk in chunks:
                key = f"processed/{f['key']}/chunk_{chunk['index']}.json"
                upload_bytes(get_processed_bucket(), key, json.dumps(chunk).encode())
            all_chunks.extend(chunks)
        return all_chunks

    @task()
    def embed_and_index(
        unstructured_chunks: list[dict],
        structured_chunks: list[dict],
        presentation_chunks: list[dict],
        pdf_chunks: list[dict],
    ) -> dict:
        """Embed all processed chunks via Bedrock Titan and index into OpenSearch."""
        from common.embedding_load_balancer import EmbeddingLoadBalancer, RateLimiterConfig

        all_chunks = unstructured_chunks + structured_chunks + presentation_chunks + pdf_chunks
        if not all_chunks:
            logger.info("No chunks to embed")
            return {"embedded": 0}

        texts = [c["text"] for c in all_chunks]

        embedding_model = os.environ.get("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
        embedding_region = os.environ.get("BEDROCK_EMBEDDING_REGION", "us-east-1")

        from eliza_rag.embeddings import EmbeddingProvider, EmbeddingService

        svc = EmbeddingService(
            provider=EmbeddingProvider.BEDROCK,
            model=embedding_model,
            aws_region=embedding_region,
        )

        async def _embed_batch(batch: list[str]) -> list[list[float]]:
            # Use the service's sync Bedrock path in thread workers to avoid
            # nested event loop behavior under Airflow subprocess execution.
            loop = asyncio.get_running_loop()
            tasks = [
                loop.run_in_executor(None, svc._invoke_bedrock_embedding, text)
                for text in batch
            ]
            return await asyncio.gather(*tasks)

        balancer = EmbeddingLoadBalancer(RateLimiterConfig(
            requests_per_minute=int(os.environ.get("BEDROCK_RPM", "100")),
            tokens_per_minute=int(os.environ.get("BEDROCK_TPM", "300000")),
            max_concurrent=int(os.environ.get("BEDROCK_MAX_CONCURRENT", "10")),
        ))

        embeddings = asyncio.run(balancer.embed_batched(texts, _embed_batch, batch_size=25))

        opensearch_host = os.environ.get("RAG_OPENSEARCH_HOST", "")
        opensearch_region = os.environ.get("RAG_OPENSEARCH_REGION", "us-east-1")
        index_prefix = os.environ.get("RAG_OPENSEARCH_INDEX_PREFIX", "rag_domains")

        if opensearch_host:
            from eliza_rag.vector_store import VectorDocument, VectorStore

            vs = VectorStore(
                opensearch_host=opensearch_host,
                opensearch_region=opensearch_region,
                index_prefix=index_prefix,
                dimensions=svc.dimensions,
            )
            docs = []
            for i, (chunk, emb) in enumerate(zip(all_chunks, embeddings)):
                docs.append(VectorDocument(
                    id=f"{chunk.get('document_id', 'doc')}_{chunk['index']}",
                    domain_id=DOMAIN_ID,
                    document_id=chunk.get("document_id", chunk.get("filename", "unknown")),
                    chunk_index=chunk["index"],
                    text=chunk["text"],
                    embedding=emb,
                    metadata=chunk.get("metadata", {}),
                ))
            indexed = asyncio.run(vs.index_documents(DOMAIN_ID, docs))
            logger.info(f"Indexed {indexed} documents into OpenSearch")
        else:
            logger.warning("RAG_OPENSEARCH_HOST not set — skipping indexing")

        return {"embedded": len(embeddings), "indexed": bool(opensearch_host)}

    files = resolve_files()
    classified = classify_file.expand(file_ref=files)
    routed = route_by_category(classified)

    u = process_unstructured(routed)
    s = process_structured(routed)
    p = process_presentations(routed)
    d = process_pdfs(routed)

    embed_and_index(u, s, p, d)


document_pipeline()
