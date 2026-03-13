# Data Ingestion Flow Diagrams

## Overview

The Eliza Platform has **two primary ingestion pipelines**:

1. **General Document Ingestion** - For HR documents, policies, etc. (FAISS-based)
2. **FASB RAG Ingestion** - For FASB Accounting Standards (OpenSearch Serverless-based)

---

## 1. FASB RAG Pipeline (OpenSearch Serverless)

This is the specialized pipeline for FASB Accounting Standards Codification.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FASB DOCUMENT INGESTION PIPELINE                          │
│                     (Pre-processed - External to This Codebase)                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   FASB PDF       │      │   PDF Parser     │      │   Text Chunks    │
│   Documents      │ ───▶ │   & Chunker      │ ───▶ │   with Metadata  │
│   (360.pdf, etc) │      │   (External)     │      │                  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
                                                              │
                                                              ▼
                          ┌──────────────────────────────────────────────┐
                          │           OpenAI Embedding API               │
                          │      Model: text-embedding-3-large           │
                          │         Dimension: 3072 vectors              │
                          └──────────────────────────────────────────────┘
                                                              │
                                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AWS OPENSEARCH SERVERLESS                                │
│                           Index: fasb-chunks-v4                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Document Schema:                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  {                                                                       │    │
│  │    "chunk_id": "unique_hash",                                           │    │
│  │    "doc_id": "360",                    ← PDF document ID                │    │
│  │    "chunk_type": "paragraph",                                           │    │
│  │    "source_path": "ASC/606/...",                                        │    │
│  │    "page_start": 70,                   ← For citation validation        │    │
│  │    "page_end": 70,                                                      │    │
│  │    "paragraph_id": "606-10-25-1",                                       │    │
│  │    "section_path": ["Revenue", "Recognition", "..."],                   │    │
│  │    "text": "Full chunk text content...",                                │    │
│  │    "embedding": [0.123, 0.456, ...],   ← 3072-dim vector               │    │
│  │    "is_superseded": false                                               │    │
│  │  }                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ (Already indexed - ready for queries)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          FASB RAG QUERY FLOW                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

  User Question: "What is ASC 606 revenue recognition?"
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  1. EMBED QUERY                                                           │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  OpenAI Embedding API (text-embedding-3-large)                 │   │
│     │  Query → 3072-dimensional vector                               │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  2. KNN SEARCH (OpenSearch Serverless)                                    │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  - k=50 candidates from vector search                          │   │
│     │  - Collapse by chunk_id (deduplication)                        │   │
│     │  - Filter: is_superseded=false, chunk_type≠test                │   │
│     │  - Return top 12 unique chunks                                 │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  3. RERANK (GPT-4o)                                                       │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  - Send 12 chunks + question to GPT                            │   │
│     │  - GPT selects best 8 chunks                                   │   │
│     │  - Prioritizes: direct answers, authoritative language         │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  4. GENERATE ANSWER (GPT-4o)                                              │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  System Prompt: FASB ASC expert, cite sources [1], [2]...      │   │
│     │  User Prompt: Question + numbered context blocks               │   │
│     │  Output: Authoritative answer with inline citations            │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  5. RESPONSE                                                              │
│     {                                                                     │
│       "answer": "According to ASC 606 [1], revenue recognition...",     │
│       "sources": [                                                        │
│         {"citation": "doc:360 pages:70-70 chunk:abc123 section:..."}    │
│       ]                                                                   │
│     }                                                                     │
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                     CITATION VALIDATION (Optional)                               │
└─────────────────────────────────────────────────────────────────────────────────┘

  When validate_citations=true in RAG eval:
  
  Citation: "doc:360 pages:70 chunk:abc123"
                      │
                      ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  1. Parse citation → doc_id=360, page=70                            │
  │  2. Load PDF from: data/eval/fasb_docs/360.pdf                      │
  │  3. Render page 70 as image (pypdfium2)                             │
  │  4. Send image + chunk text to GPT-4o Vision                        │
  │  5. GPT verifies: "Does this page contain this text?"               │
  │  6. Return: pass/fail verdict with confidence score                 │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 2. General Document Ingestion Pipeline (FAISS-based)

For HR documents, policies, and other customer-uploaded content.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    GENERAL DOCUMENT INGESTION PIPELINE                           │
└─────────────────────────────────────────────────────────────────────────────────┘

  POST /v1/documents/upload
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  1. UPLOAD PHASE                                                          │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  - Save file: data/<customer_id>/<batch_id>/<filename>         │   │
│     │  - Create Document record (status: UPLOADED)                   │   │
│     │  - Queue Celery task: process_document_task                    │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
          │
          ▼ (Async via Celery)
┌──────────────────────────────────────────────────────────────────────────┐
│  2. TEXT EXTRACTION                                                       │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  PDF  → PyPDF2.PdfReader (or Docling for complex layouts)      │   │
│     │  DOCX → python-docx                                            │   │
│     │  TXT  → Direct read                                            │   │
│     │  + Metadata extraction (pages, word count, dates)              │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  3. CHUNKING                                                              │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  Strategy: SEMANTIC (default) | FIXED | HIERARCHICAL           │   │
│     │                                                                 │   │
│     │  SEMANTIC chunking:                                             │   │
│     │  - Use sentence-transformers for similarity                    │   │
│     │  - Group semantically related sentences                        │   │
│     │  - Target ~1024 chars per chunk                                │   │
│     │  - Maintain coherent context boundaries                        │   │
│     │                                                                 │   │
│     │  Each chunk gets:                                               │   │
│     │  - chunk_id (unique hash)                                      │   │
│     │  - chunk_index (position in document)                          │   │
│     │  - section_title (if detected)                                 │   │
│     │  - quality_score (0.0-1.0)                                     │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  4. SAVE TO POSTGRESQL                                                    │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  Table: document_chunks                                         │   │
│     │  ┌─────────────────────────────────────────────────────────┐   │   │
│     │  │  document_id      │  Reference to parent document       │   │   │
│     │  │  chunk_id         │  Unique hash (dedup key)            │   │   │
│     │  │  chunk_index      │  Position in document               │   │   │
│     │  │  text             │  Full chunk content                 │   │   │
│     │  │  start_char       │  Character offset start             │   │   │
│     │  │  end_char         │  Character offset end               │   │   │
│     │  │  token_count      │  Token count                        │   │   │
│     │  │  section_title    │  Detected section header            │   │   │
│     │  │  quality_score    │  Chunk quality (0-1)                │   │   │
│     │  │  embedding_model  │  Model used for embeddings          │   │   │
│     │  └─────────────────────────────────────────────────────────┘   │   │
│     │  ✓ Duplicate detection by chunk_id                             │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  5. GENERATE EMBEDDINGS & INDEX IN FAISS                                  │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  Model: sentence-transformers/all-MiniLM-L6-v2                 │   │
│     │  Dimension: 384 vectors                                         │   │
│     │                                                                 │   │
│     │  Process:                                                       │   │
│     │  1. Batch encode all chunk texts                               │   │
│     │  2. Add vectors to FAISS index                                 │   │
│     │  3. Update chunk_id → index_position mapping                   │   │
│     │  4. Save index to: data/vectors/faiss_index.bin                │   │
│     │  5. Save mapping: data/vectors/chunk_mapping.json              │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  6. FINALIZE                                                              │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  - Update document status: COMPLETED                           │   │
│     │  - Set total_chunks count                                      │   │
│     │  - Calculate overall quality_score                             │   │
│     │  - Log telemetry/metrics                                       │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SEARCH FLOW                                         │
└─────────────────────────────────────────────────────────────────────────────────┘

  User Query: "What are the company benefits?"
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  1. Generate query embedding (same model: all-MiniLM-L6-v2)              │
│  2. Search FAISS index (fast approximate nearest neighbor)               │
│  3. Get top-k chunk_ids by similarity score                              │
│  4. Fetch full chunk details from PostgreSQL                             │
│  5. Filter by customer_id and similarity_threshold                       │
│  6. Return results with text, metadata, and scores                       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. PDL (People Data Labs) Ingestion Pipeline

For candidate and person data from external APIs.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        PDL PERSON DATA INGESTION                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

  Connector Configuration (API Key, Query Parameters)
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  1. PDL API CALL                                                          │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  - Rate limited: 60 requests/minute                            │   │
│     │  - Cost estimation before execution                            │   │
│     │  - Pagination via scroll_token                                 │   │
│     │  - Query validation                                            │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  2. RAW DATA STAGING                                                      │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  Table: ingested_data                                          │   │
│     │  - Raw JSON from API                                           │   │
│     │  - Sync metadata                                               │   │
│     │  - Error tracking                                              │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  3. TRANSFORM (PDLTransformer)                                            │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  Raw JSON → PDLPerson model                                     │   │
│     │  - Field mapping & validation                                  │   │
│     │  - UPSERT logic (deduplication by pdl_id)                      │   │
│     │  - Sync count tracking                                         │   │
│     └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  4. MULTI-STORE SYNC                                                      │
│     ┌─────────────────────────────────────────┐                          │
│     │  PostgreSQL (pdl_persons)               │ ← Primary storage        │
│     │  - Full person data                     │                          │
│     │  - ACID transactions                    │                          │
│     └─────────────────────────────────────────┘                          │
│                       │                                                   │
│                       ├────────────────────────────────────┐             │
│                       ▼                                    ▼             │
│     ┌─────────────────────────────────────────┐  ┌─────────────────────┐│
│     │  Elasticsearch                          │  │  Neo4j              ││
│     │  - Full-text search                     │  │  - Graph relations  ││
│     │  - Fuzzy matching                       │  │  - Company nodes    ││
│     │  - Faceted filtering                    │  │  - Skill edges      ││
│     │  - Autocomplete                         │  │  - Career paths     ││
│     └─────────────────────────────────────────┘  └─────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Key Configuration Parameters

### FASB RAG Config
| Parameter | Default | Description |
|-----------|---------|-------------|
| `FASB_OPENSEARCH_HOST` | (required) | AWS OpenSearch Serverless endpoint |
| `FASB_OPENSEARCH_INDEX` | `fasb-chunks-v4` | Index name |
| `FASB_EMBED_MODEL` | `text-embedding-3-large` | OpenAI embedding model |
| `FASB_KNN_K` | `50` | kNN candidates |
| `FASB_RETRIEVE_SIZE` | `12` | Chunks after collapse |
| `FASB_RERANK_KEEP` | `8` | Chunks after reranking |
| `FASB_DOCS_PATH` | `data/eval/fasb_docs` | PDF files for citation validation |

### General Document Config
| Parameter | Default | Description |
|-----------|---------|-------------|
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model |
| `EMBEDDING_DIMENSION` | `384` | Vector dimension |
| `DEFAULT_CHUNK_SIZE` | `1024` | Target chunk size |
| `DEFAULT_CHUNK_OVERLAP` | `128` | Overlap between chunks |

---

## 5. Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW COMPARISON                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────┬─────────────────────────┬─────────────────────────────┐
│     FASB RAG            │   General Documents     │   PDL Connector             │
├─────────────────────────┼─────────────────────────┼─────────────────────────────┤
│ Source: External PDFs   │ Source: User Uploads    │ Source: PDL API             │
│                         │                         │                             │
│ Indexing: External      │ Indexing: Celery Task   │ Indexing: Celery Task       │
│ (pre-indexed)           │                         │                             │
│                         │                         │                             │
│ Vector Store:           │ Vector Store:           │ Vector Store:               │
│ AWS OpenSearch          │ FAISS (local)           │ N/A (structured data)       │
│ Serverless              │                         │                             │
│                         │                         │                             │
│ Embeddings:             │ Embeddings:             │ Search:                     │
│ text-embedding-3-large  │ all-MiniLM-L6-v2        │ Elasticsearch               │
│ (OpenAI, 3072-dim)      │ (local, 384-dim)        │                             │
│                         │                         │                             │
│ Storage:                │ Storage:                │ Storage:                    │
│ OpenSearch only         │ PostgreSQL + FAISS      │ PostgreSQL + ES + Neo4j     │
│                         │                         │                             │
│ Use Case:               │ Use Case:               │ Use Case:                   │
│ FASB Q&A                │ Company docs search     │ Candidate matching          │
└─────────────────────────┴─────────────────────────┴─────────────────────────────┘
```
