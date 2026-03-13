# Documents API

**Base Path:** `/api/v1/documents`

**Required Permission:** `documents:read` (for reading), `documents:write` (for uploading)

## Overview

The Documents API provides:
- **Upload**: Multi-file upload with various formats (PDF, DOCX, TXT, MD, CSV, JSON)
- **Processing**: Automatic chunking, embedding generation, and vector indexing
- **Search**: Semantic search using vector similarity
- **Management**: List, view, download, and delete documents
- **Real-Time Progress**: SSE for upload and processing status

## Key Concepts

- **Document**: A file uploaded to the system
- **Chunk**: A document split into smaller pieces for processing
- **Upload Batch**: Group of files uploaded together
- **Chunking Strategy**: Algorithm for splitting documents (semantic, fixed-size, sliding-window)
- **Vector Index**: Embedding-based search index for semantic search
- **Company HR Dataset**: Associates documents with a specific company

## Document Lifecycle

```
1. Upload → 2. Parse → 3. Chunk → 4. Embed → 5. Index → 6. Searchable
```

**Status Flow:**
- `uploaded` → File received
- `processing` → Being chunked and embedded
- `completed` → Ready for search
- `failed` → Error occurred
- `deleted` → Soft deleted (marked for cleanup)

---

## Endpoints

### POST /api/v1/documents/upload

Upload one or more documents for processing.

**Requires Permission:** `documents:write`

**Request:** `multipart/form-data`

**Form Fields:**
- `files` (files, required) - Documents to upload (max 10 per batch)
- `source_id` (string, optional) - Associate with data source
- `company_hr_dataset` (string, optional) - Company to associate with (defaults to system default)
- `chunking_strategy` (enum, default: `semantic`) - Chunking method
  - `semantic` - AI-powered semantic boundaries
  - `fixed_size` - Fixed character count
  - `sliding_window` - Overlapping windows
- `chunk_size` (integer, default: 1024) - Target chunk size in characters
- `chunk_overlap` (integer, default: 128) - Overlap between chunks
- `similarity_threshold` (float, default: 0.85) - Threshold for semantic chunking (0-1)
- `enable_qa_rag` (boolean, default: false) - Enable Q&A pair generation
- `metadata` (string, optional) - JSON string with additional metadata

**Supported File Types:**
- **Documents**: PDF, DOC, DOCX, TXT, MD
- **Spreadsheets**: XLS, XLSX, CSV
- **Data**: JSON

**Example Request:**
```bash
curl -X POST http://localhost:5001/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@employee_handbook.pdf" \
  -F "files=@skills_matrix.xlsx" \
  -F "company_hr_dataset=caylent" \
  -F "chunking_strategy=semantic" \
  -F "chunk_size=1024" \
  -F "enable_qa_rag=true" \
  -F 'metadata={"department": "HR", "year": 2024}'
```

**Response:** `202 Accepted`
```json
{
  "upload_id": "upload_batch_abc123",
  "files": [
    {
      "filename": "employee_handbook.pdf",
      "status": "uploaded",
      "document_id": 101,
      "file_size": 524288,
      "mime_type": "pdf",
      "error": null
    },
    {
      "filename": "skills_matrix.xlsx",
      "status": "uploaded",
      "document_id": 102,
      "file_size": 102400,
      "mime_type": "xlsx",
      "error": null
    }
  ],
  "total_files": 2,
  "estimated_processing_time": "60 seconds",
  "message": "Upload started successfully. 2/2 files accepted for processing."
}
```

**Errors:**
- `400` - No files provided or too many files (>10)
- `422` - Duplicate filename in same batch
- `413` - File too large (check server configuration)
- `415` - Unsupported file type

**Processing Time:**
- **PDF** (10 pages): ~30 seconds
- **PDF** (100 pages): ~5 minutes
- **DOCX** (50 pages): ~45 seconds
- **CSV** (10K rows): ~1 minute

**Chunking Strategies Explained:**

1. **Semantic Chunking** (Recommended)
   - Uses AI to identify natural document boundaries
   - Preserves context and meaning
   - Best for: Reports, articles, manuals
   - Slower but higher quality

2. **Fixed Size**
   - Splits at exact character count
   - Fast and predictable
   - Best for: Large text files, logs
   - May split sentences mid-word

3. **Sliding Window**
   - Creates overlapping chunks
   - Ensures context preservation
   - Best for: Dense technical documents
   - More chunks = more storage

---

### GET /api/v1/documents/upload/{upload_id}/status

Get status of an upload batch.

**Requires Permission:** `documents:read`

**Response:** `200 OK`
```json
{
  "upload_id": "upload_batch_abc123",
  "customer_id": "eliza",
  "status": "processing",
  "total_files": 2,
  "completed_files": 1,
  "failed_files": 0,
  "total_chunks_created": 145,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:45Z"
}
```

**Status Values:**
- `pending` - Upload initiated
- `processing` - Files being processed
- `completed` - All files processed successfully
- `failed` - One or more files failed

---

### GET /api/v1/documents/upload/{upload_id}/stream

Stream real-time upload progress via Server-Sent Events (SSE).

**Requires Permission:** `documents:read`

**Query Parameters:**
- `token` (string, required) - JWT access token

**Example:**
```javascript
const token = localStorage.getItem('auth_token');
const eventSource = new EventSource(
  `http://localhost:5001/api/v1/documents/upload/${uploadId}/stream?token=${token}`
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.event_type) {
    case 'status_update':
      console.log(`Progress: ${data.progress_percentage}%`);
      console.log(`Completed: ${data.completed_files}/${data.total_files}`);
      console.log(`Chunks created: ${data.total_chunks_created}`);
      break;
    case 'completed':
      console.log('Upload complete!', data.message);
      eventSource.close();
      break;
    case 'failed':
      console.error('Upload failed:', data.message);
      eventSource.close();
      break;
    case 'heartbeat':
      // Keep-alive ping
      break;
  }
};

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  eventSource.close();
};
```

**Event Format:**
```json
{
  "event_id": "status-xyz789",
  "event_type": "status_update",
  "upload_id": "upload_batch_abc123",
  "status": "processing",
  "total_files": 2,
  "completed_files": 1,
  "failed_files": 0,
  "progress_percentage": 50.0,
  "total_chunks_created": 145,
  "timestamp": "2024-01-15T10:00:45Z"
}
```

---

### GET /api/v1/documents

List documents with filtering and pagination.

**Requires Permission:** `documents:read`

**Query Parameters:**
- `source_id` (string, optional) - Filter by data source
- `status` (enum, optional) - Filter by status (`uploaded`, `processing`, `completed`, `failed`)
- `company_hr_dataset` (string, optional) - Filter by company
- `created_after` (datetime, optional) - Filter documents created after (ISO 8601)
- `created_before` (datetime, optional) - Filter documents created before (ISO 8601)
- `limit` (integer, default: 50, max: 100) - Number of results
- `offset` (integer, default: 0) - Pagination offset
- `sort` (string, default: `-created_at`) - Sort field (prefix `-` for descending)
  - Options: `created_at`, `filename`, `file_size`, `original_filename`

**Example:**
```bash
# Get recent completed documents
GET /api/v1/documents?status=completed&limit=20&sort=-created_at

# Get documents from last 7 days for specific company
GET /api/v1/documents?company_hr_dataset=caylent&created_after=2024-01-08T00:00:00Z

# Get failed documents
GET /api/v1/documents?status=failed&limit=10
```

**Response:** `200 OK`
```json
{
  "documents": [
    {
      "id": 101,
      "customer_id": "eliza",
      "original_filename": "employee_handbook.pdf",
      "file_size": 524288,
      "mime_type": "pdf",
      "status": "completed",
      "company_hr_dataset": "caylent",
      "source_id": "hr_docs",
      "total_chunks": 45,
      "chunking_strategy": "semantic",
      "processing_started_at": "2024-01-15T10:00:05Z",
      "processing_completed_at": "2024-01-15T10:00:35Z",
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:35Z",
      "metadata": {"department": "HR", "year": 2024}
    },
    ...
  ],
  "total": 150,
  "offset": 0,
  "limit": 50
}
```

---

### GET /api/v1/documents/{document_id}

Get detailed information about a specific document.

**Requires Permission:** `documents:read`

**Response:** `200 OK`
```json
{
  "id": 101,
  "customer_id": "eliza",
  "original_filename": "employee_handbook.pdf",
  "file_path": "/storage/eliza/documents/101_employee_handbook.pdf",
  "file_size": 524288,
  "mime_type": "pdf",
  "status": "completed",
  "company_hr_dataset": "caylent",
  "source_id": "hr_docs",
  "total_chunks": 45,
  "chunking_strategy": "semantic",
  "chunking_config": {
    "chunk_size": 1024,
    "chunk_overlap": 128,
    "similarity_threshold": 0.85
  },
  "processing_error": null,
  "processing_started_at": "2024-01-15T10:00:05Z",
  "processing_completed_at": "2024-01-15T10:00:35Z",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:35Z",
  "metadata": {
    "department": "HR",
    "year": 2024,
    "page_count": 50
  }
}
```

**Errors:**
- `404` - Document not found
- `403` - Access denied (document belongs to different customer)

---

### GET /api/v1/documents/{document_id}/download

Download the original document file.

**Requires Permission:** `documents:read`

**Response:** `200 OK`
- **Content-Type**: Original file MIME type (e.g., `application/pdf`)
- **Content-Disposition**: `attachment; filename="employee_handbook.pdf"`
- **Body**: Binary file data

**Example:**
```bash
curl -X GET http://localhost:5001/api/v1/documents/101/download \
  -H "Authorization: Bearer $TOKEN" \
  -o employee_handbook.pdf
```

**Errors:**
- `404` - Document or file not found
- `410` - Document has been deleted
- `403` - Access denied

---

### DELETE /api/v1/documents/{document_id}

Delete a document and its associated chunks.

**Requires Permission:** `documents:delete`

**Response:** `200 OK`
```json
{
  "message": "Document deleted successfully"
}
```

**Notes:**
- This is a soft delete (document marked as `deleted`)
- Chunks are removed from vector index
- Physical file deletion happens during cleanup jobs
- Cannot be undone

**Errors:**
- `404` - Document not found or already deleted
- `403` - Access denied

---

### POST /api/v1/documents/{document_id}/retry

Retry processing a failed document.

**Requires Permission:** `documents:write`

**Response:** `200 OK`
```json
{
  "message": "Document reprocessing started",
  "document_id": 101,
  "task_id": "celery_task_abc123"
}
```

**Use Cases:**
- Transient failures (network errors, service timeouts)
- After fixing configuration issues
- Testing different chunking strategies

**Errors:**
- `404` - Document not found
- `400` - Document is not in failed status

---

### POST /api/v1/documents/search

Semantic search across documents using vector similarity.

**Requires Permission:** `documents:read`

**Request:**
```json
{
  "query": "employee benefits and vacation policies",
  "limit": 10,
  "similarity_threshold": 0.7,
  "source_ids": ["hr_docs"],
  "document_ids": [101, 102, 103],
  "include_qa_pairs": false
}
```

**Parameters:**
- `query` (string, required) - Search query
- `limit` (integer, default: 10, max: 100) - Number of results
- `similarity_threshold` (float, default: 0.7) - Minimum similarity score (0-1)
- `source_ids` (array, optional) - Filter by source IDs
- `document_ids` (array, optional) - Filter by specific documents
- `include_qa_pairs` (boolean, default: false) - Include generated Q&A pairs

**Response:** `200 OK`
```json
{
  "results": [
    {
      "document_id": 101,
      "document_filename": "employee_handbook.pdf",
      "chunk_id": 1523,
      "chunk_index": 12,
      "text": "Employee Benefits\n\nOur comprehensive benefits package includes:\n\n1. Health Insurance: Full medical, dental, and vision coverage\n2. Vacation: 20 days paid time off annually\n3. 401(k): Company matches up to 6%\n4. Professional Development: $2,000 annual budget",
      "similarity_score": 0.89,
      "section_title": "Benefits Overview",
      "page_number": 15,
      "metadata": {
        "department": "HR",
        "year": 2024
      },
      "qa_questions": null,
      "qa_answers": null
    },
    {
      "document_id": 101,
      "document_filename": "employee_handbook.pdf",
      "chunk_id": 1524,
      "chunk_index": 13,
      "text": "Vacation Policy\n\nNew employees receive 15 days of paid vacation per year. After 3 years, this increases to 20 days. Vacation must be approved by your manager at least 2 weeks in advance.",
      "similarity_score": 0.82,
      "section_title": "Time Off Policies",
      "page_number": 16,
      "metadata": {
        "department": "HR",
        "year": 2024
      }
    },
    ...
  ],
  "total": 8,
  "query": "employee benefits and vacation policies"
}
```

**Search Algorithm:**
1. Query is converted to embedding vector (1536 dimensions)
2. Vector similarity search using FAISS index
3. Results filtered by customer_id and optional filters
4. Results ranked by similarity score (cosine similarity)
5. Top N results returned

**Similarity Score Interpretation:**
- **0.9-1.0**: Highly relevant, nearly exact match
- **0.8-0.9**: Very relevant, strong semantic match
- **0.7-0.8**: Relevant, good semantic match
- **0.6-0.7**: Somewhat relevant, weak match
- **<0.6**: Not very relevant

**Performance:**
- Typical search: 50-200ms
- Large corpus (1M+ chunks): 200-500ms
- Filters reduce search time

---

### GET /api/v1/documents/stats

Get document statistics for the current user's organization.

**Requires Permission:** `documents:read`

**Query Parameters:**
- `range` (enum, default: `7d`) - Time range
  - `24h` - Last 24 hours
  - `7d` - Last 7 days
  - `30d` - Last 30 days

**Response:** `200 OK`
```json
{
  "total_documents": 150,
  "processing_documents": 5,
  "completed_documents": 140,
  "failed_documents": 5,
  "total_chunks": 8432,
  "storage_used_mb": 1245.67,
  "range": "7d"
}
```

**Use Cases:**
- Dashboard metrics
- Capacity planning
- Quality monitoring

---

### GET /api/v1/documents/recent

**DEPRECATED** - Use `GET /api/v1/documents` with date filtering instead.

Get recently uploaded documents (last 24 hours).

**Query Parameters:**
- `limit` (integer, default: 5, max: 50)

**Response:** `200 OK`
```json
{
  "documents": [...],
  "total": 12,
  "limit": 5
}
```

**Recommended Alternative:**
```bash
GET /api/v1/documents?created_after=<24h_ago>&limit=5&sort=-created_at
```

---

### GET /api/v1/documents/stats/index

Get vector index statistics.

**Requires Permission:** `documents:read`

**Response:** `200 OK`
```json
{
  "total_vectors": 8432,
  "index_size_mb": 102.5,
  "vector_dimension": 1536,
  "index_type": "FAISS_HNSW",
  "last_updated": "2024-01-15T10:00:00Z",
  "search_performance_ms": {
    "avg": 85,
    "p50": 75,
    "p95": 150,
    "p99": 200
  }
}
```

---

### POST /api/v1/documents/admin/rebuild-index

Rebuild the vector index from existing chunks (admin only).

**Requires Permission:** `system:admin`

**Response:** `200 OK`
```json
{
  "message": "Index rebuild completed successfully",
  "stats": {
    "total_chunks": 8432,
    "vectors_indexed": 8432,
    "duration_seconds": 45.2,
    "success": true
  }
}
```

**Use Cases:**
- After index corruption
- Changing index configuration
- Performance optimization
- Testing

**Warning:** This operation can take several minutes for large document collections.

---

### GET /api/v1/documents/health

Health check for document processing service.

**No authentication required**

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "document_processor": {
    "status": "healthy"
  },
  "vector_service": {
    "status": "healthy",
    "stats": {
      "total_vectors": 8432,
      "index_size_mb": 102.5
    }
  },
  "vector_index_stats": {...}
}
```

---

## Best Practices

### File Naming

✅ **Good:**
- `employee_handbook_2024.pdf`
- `skills_matrix_q1_2024.xlsx`
- `benefits_overview.docx`

❌ **Bad:**
- `Document (1).pdf` - Not descriptive
- `FINAL_FINAL_v2_REAL.docx` - Confusing versions
- `file.pdf` - Too generic

### Metadata Usage

Use metadata for:
- **Department**: `{"department": "HR"}`
- **Year/Quarter**: `{"year": 2024, "quarter": "Q1"}`
- **Document Type**: `{"type": "policy", "category": "benefits"}`
- **Version**: `{"version": "2.1", "revision_date": "2024-01-15"}`
- **Owner**: `{"owner": "jane.smith@company.com"}`
- **Sensitivity**: `{"confidential": true, "classification": "internal"}`

### Chunking Strategy Selection

| Document Type | Recommended Strategy | Chunk Size |
|---------------|---------------------|------------|
| Employee Handbook | Semantic | 1024 |
| Technical Manual | Semantic | 1536 |
| Meeting Notes | Fixed Size | 512 |
| Research Paper | Sliding Window | 1024 |
| Contract/Legal | Semantic | 2048 |
| Log Files | Fixed Size | 256 |
| Code Documentation | Sliding Window | 768 |

### Search Optimization

1. **Use specific queries**: "vacation policy" > "policy"
2. **Adjust threshold**: Lower for broader results (0.6), higher for precision (0.8)
3. **Filter by source**: Narrow search space for faster results
4. **Use document IDs**: When you know the document set
5. **Iterate threshold**: Start high (0.8), lower if no results

### Upload Best Practices

1. **Batch similar files**: Group files by type or department
2. **Use meaningful names**: Helps with debugging and organization
3. **Include metadata**: Makes filtering and searching easier
4. **Monitor progress**: Use SSE for real-time feedback
5. **Handle failures**: Retry failed documents after investigation
6. **Validate before upload**: Check file size and format

## Common Workflows

### Bulk Document Upload with Progress Tracking

```javascript
async function uploadDocuments(files, options = {}) {
  // 1. Create FormData
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  formData.append('company_hr_dataset', options.company || 'default');
  formData.append('chunking_strategy', options.strategy || 'semantic');
  formData.append('enable_qa_rag', options.enableQA || 'false');
  
  if (options.metadata) {
    formData.append('metadata', JSON.stringify(options.metadata));
  }
  
  // 2. Submit upload
  const response = await fetch('/api/v1/documents/upload', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData
  });
  
  const { upload_id, files: uploadedFiles } = await response.json();
  
  // 3. Track progress via SSE
  return new Promise((resolve, reject) => {
    const eventSource = new EventSource(
      `/api/v1/documents/upload/${upload_id}/stream?token=${token}`
    );
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      // Update UI
      updateProgressUI(data);
      
      if (data.event_type === 'completed') {
        eventSource.close();
        resolve({ upload_id, completed: true });
      } else if (data.event_type === 'failed') {
        eventSource.close();
        reject(new Error(data.message));
      }
    };
    
    eventSource.onerror = (error) => {
      eventSource.close();
      reject(error);
    };
  });
}
```

### Search with Result Highlighting

```javascript
async function searchAndHighlight(query) {
  const response = await fetch('/api/v1/documents/search', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      query,
      limit: 10,
      similarity_threshold: 0.7
    })
  });
  
  const { results } = await response.json();
  
  // Highlight matching terms in results
  const highlightedResults = results.map(result => ({
    ...result,
    highlighted_text: highlightTerms(result.text, query)
  }));
  
  return highlightedResults;
}

function highlightTerms(text, query) {
  const terms = query.toLowerCase().split(' ');
  let highlighted = text;
  
  terms.forEach(term => {
    const regex = new RegExp(`(${term})`, 'gi');
    highlighted = highlighted.replace(regex, '<mark>$1</mark>');
  });
  
  return highlighted;
}
```

## Troubleshooting

### Upload Fails with 422 Error

**Cause:** Duplicate filename in batch

**Solution:** Rename files to have unique names within the batch

### Document Stuck in "Processing" Status

**Cause:** Celery worker crashed or stalled

**Solutions:**
1. Check Celery worker logs: `docker-compose logs celery-worker`
2. Retry processing: `POST /api/v1/documents/{document_id}/retry`
3. Check worker health: `GET /api/v1/documents/health`

### Search Returns No Results

**Causes:**
1. Threshold too high
2. No matching documents
3. Query too specific

**Solutions:**
1. Lower similarity threshold to 0.6
2. Try broader query terms
3. Check document count: `GET /api/v1/documents/stats`
4. Verify documents are completed: `GET /api/v1/documents?status=completed`

### Slow Search Performance

**Causes:**
1. Large document corpus
2. No filters applied
3. Index not optimized

**Solutions:**
1. Use filters (source_id, document_ids)
2. Consider rebuilding index: `POST /api/v1/documents/admin/rebuild-index`
3. Scale vector service infrastructure
4. Reduce result limit

### Document Processing Fails

**Common Errors:**

**"Unsupported file format"**
- Check file extension
- Verify file is not corrupted
- Convert to supported format

**"File too large"**
- Check file size (default max: 50MB)
- Compress or split file
- Contact admin to increase limit

**"Extraction failed"**
- File may be corrupted
- PDF may be image-only (OCR needed)
- Password-protected documents not supported

## Limits and Quotas

| Resource | Limit | Configurable |
|----------|-------|--------------|
| Max files per upload | 10 | No |
| Max file size | 50 MB | Yes (server config) |
| Max chunk size | 4096 chars | Yes |
| Max search results | 100 | No |
| Storage per customer | Unlimited | Yes (by quota) |
| Daily uploads | Unlimited | Yes (rate limiting) |
| Concurrent uploads | 5 | Yes (server config) |

## Storage and Retention

- **Original Files**: Stored in persistent volume
- **Chunks**: Stored in PostgreSQL
- **Vectors**: Stored in FAISS index + PostgreSQL backup
- **Retention**: Indefinite (until manually deleted)
- **Backups**: Automated daily backups
- **Cleanup**: Soft-deleted files cleaned up after 30 days

## Security

- All files scoped to customer_id (multi-tenant isolation)
- Access control via JWT + permissions
- Files encrypted at rest (server configuration)
- No public file access
- Audit logging for all operations


