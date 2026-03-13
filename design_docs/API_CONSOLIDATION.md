# Document List API Consolidation

## 🎯 Architectural Improvement

**Date:** October 7, 2025  
**Type:** Refactoring / API Consolidation  
**Impact:** Breaking change (with backward compatibility period)

---

## 📋 Summary

Consolidated two separate document listing endpoints into a single flexible endpoint with comprehensive filtering capabilities.

**Before:**
- `GET /v1/documents` - Full document list (basic filtering)
- `GET /v1/documents/recent` - Recent uploads only (simplified response)

**After:**
- `GET /v1/documents` - Enhanced with flexible filtering, sorting, date ranges
- `GET /v1/documents/recent` - Deprecated (kept for backward compatibility)

---

## 🤔 Why This Change?

### Problems with Separate Endpoints

1. **Code Duplication** - Similar logic in two places
2. **Inconsistent Response Models** - `DocumentInfo` vs `RecentDocumentInfo`
3. **Limited Flexibility** - Can't filter recent docs by company or status
4. **Maintenance Overhead** - Changes need to happen in two places
5. **API Sprawl** - More endpoints = more complexity

### Benefits of Consolidation

1. ✅ **Single Source of Truth** - One endpoint, one response model
2. ✅ **More Flexible** - Combine any filters (date + company + status)
3. ✅ **DRY Principle** - Don't Repeat Yourself
4. ✅ **RESTful Design** - Standard pattern: `GET /resources?filters`
5. ✅ **Easier Testing** - Test one endpoint thoroughly
6. ✅ **Better Documentation** - One comprehensive endpoint doc
7. ✅ **Future-Proof** - Easy to add new filters

---

## 🔧 Technical Changes

### Backend Changes

#### 1. Enhanced `/v1/documents` Endpoint

**New Query Parameters:**
```python
@router.get("", response_model=DocumentListResponse)
async def list_documents(
    source_id: Optional[str] = None,                    # Existing
    status: Optional[DocumentStatus] = None,            # Existing
    company_hr_dataset: Optional[str] = None,           # NEW
    created_after: Optional[datetime] = None,           # NEW
    created_before: Optional[datetime] = None,          # NEW
    sort: str = "-created_at",                          # NEW
    limit: int = 50,                                    # Enhanced validation
    offset: int = 0,                                    # Existing
    current_user: CurrentUserContext = Depends(get_current_user)
)
```

**Filtering Logic:**
- Company filter: `if company_hr_dataset: filter by company`
- Date range: `if created_after/before: filter by timestamp`
- Sorting: Support for `field` or `-field` (descending)
- Sort fields: `created_at`, `filename`, `file_size`, `original_filename`

**Example Requests:**
```bash
# Recent uploads (replaces /recent endpoint)
GET /v1/documents?created_after=2025-10-06T00:00:00Z&limit=5&sort=-created_at

# Documents for specific company
GET /v1/documents?company_hr_dataset=eliza&limit=10

# Processing documents from last hour
GET /v1/documents?status=processing&created_after=2025-10-07T03:00:00Z

# Combine filters: eliza documents from today, sorted by size
GET /v1/documents?company_hr_dataset=eliza&created_after=2025-10-07T00:00:00Z&sort=-file_size
```

---

#### 2. Added `company_hr_dataset` to `DocumentInfo`

**Problem:** The database model has `company_hr_dataset`, but it wasn't in the main API response.

**Before:**
```python
class DocumentInfo(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    status: DocumentStatus
    total_chunks: int
    # ... more fields
    customer_id: str
    created_at: datetime
    # company_hr_dataset was MISSING!
```

**After:**
```python
class DocumentInfo(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    status: DocumentStatus
    total_chunks: int
    # ... more fields
    customer_id: str
    company_hr_dataset: Optional[str] = None  # NOW INCLUDED
    created_at: datetime
```

**Why:** Consistency - all document responses should include company association.

---

#### 3. Deprecated `/v1/documents/recent`

**Status:** Marked as `deprecated=True` in OpenAPI schema

**Documentation Updated:**
```python
@router.get("/recent", response_model=RecentDocumentsResponse, deprecated=True)
async def get_recent_documents(...):
    """
    **DEPRECATED:** Use GET /v1/documents with date filtering instead.
    
    This endpoint is maintained for backward compatibility but will be removed.
    
    **Recommended alternative:**
    GET /v1/documents?created_after=<24h_ago>&limit=5&sort=-created_at
    """
```

**Timeline:**
- Now: Deprecated, still functional
- Next major version: Will be removed
- Clients should migrate to new endpoint

---

### Frontend Changes

#### 1. Updated `CompanyDataOverview.tsx`

**Before:**
```typescript
const { data: recentData } = useGetRecentDocumentsV1DocumentsRecentGet(
  { limit: 5 },
  { query: { ... } }
);
const recentUploads = recentData?.documents || [];
```

**After:**
```typescript
// Calculate 24 hours ago
const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

// Use main list endpoint with date filter
const { data: recentData } = useListDocumentsV1DocumentsGet(
  { 
    limit: 5,
    created_after: twentyFourHoursAgo,
    sort: '-created_at'
  },
  { query: { ... } }
);
const recentUploads = recentData?.documents || [];
```

**Benefits:**
- Uses `DocumentInfo` (includes all fields)
- Can easily adjust time range
- Can add company filter if needed
- Consistent with document library

#### 2. Fixed Field Name

**Before:** `upload.file_size_bytes`  
**After:** `upload.file_size`

**Why:** `DocumentInfo` uses `file_size`, not `file_size_bytes`.

#### 3. Updated Imports

**Before:** `useGetRecentDocumentsV1DocumentsRecentGet`  
**After:** `useListDocumentsV1DocumentsGet`

---

## 📊 Comparison

### Response Models

| Field | DocumentInfo | RecentDocumentInfo |
|-------|-------------|-------------------|
| id | ✅ | ✅ |
| filename | ✅ | ❌ |
| original_filename | ✅ | ✅ |
| file_size | ✅ | ✅ (as file_size_bytes) |
| mime_type | ✅ | ❌ |
| status | ✅ | ✅ |
| total_chunks | ✅ | ✅ |
| duplicate_chunks_count | ✅ | ❌ |
| total_characters | ✅ | ❌ |
| quality_score | ✅ | ❌ |
| chunking_strategy | ✅ | ❌ |
| qa_rag_enabled | ✅ | ❌ |
| qa_pairs_generated | ✅ | ❌ |
| customer_id | ✅ | ❌ |
| **company_hr_dataset** | ✅ **NEW** | ✅ |
| created_at | ✅ | ✅ |
| processing_completed_at | ✅ | ❌ |
| document_metadata | ✅ | ❌ |

**Winner:** `DocumentInfo` - More comprehensive, single model for all use cases.

---

## 🧪 Testing

### Test Case 1: Recent Uploads (Last 24 Hours)

**Old Way:**
```bash
GET /v1/documents/recent?limit=5
```

**New Way:**
```bash
GET /v1/documents?created_after=2025-10-06T04:30:00Z&limit=5&sort=-created_at
```

**Expected:** Same documents, but with `DocumentInfo` format.

---

### Test Case 2: Company-Specific Recent Uploads

**Old Way:** Not possible with `/recent` endpoint

**New Way:**
```bash
GET /v1/documents?company_hr_dataset=eliza&created_after=2025-10-06T04:30:00Z&limit=5&sort=-created_at
```

**Expected:** Only eliza documents from last 24 hours.

---

### Test Case 3: Processing Documents from Last Hour

**Old Way:** Not possible with `/recent` endpoint

**New Way:**
```bash
GET /v1/documents?status=processing&created_after=2025-10-07T03:30:00Z
```

**Expected:** Only documents currently processing, created in last hour.

---

## 🚀 Migration Guide

### For API Clients

**If you're using `/v1/documents/recent`:**

1. **Calculate timestamp for date filter:**
   ```javascript
   const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
   ```

2. **Update API call:**
   ```javascript
   // Before
   GET /v1/documents/recent?limit=5
   
   // After
   GET /v1/documents?created_after=${twentyFourHoursAgo}&limit=5&sort=-created_at
   ```

3. **Update response parsing:**
   ```javascript
   // Before: RecentDocumentInfo
   const fileSize = document.file_size_bytes;
   
   // After: DocumentInfo
   const fileSize = document.file_size;
   ```

---

### For Frontend Components

**React Query Hook:**
```typescript
// Before
import { useGetRecentDocumentsV1DocumentsRecentGet } from '../../generated/documents/documents';

const { data } = useGetRecentDocumentsV1DocumentsRecentGet({ limit: 5 });

// After
import { useListDocumentsV1DocumentsGet } from '../../generated/documents/documents';

const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
const { data } = useListDocumentsV1DocumentsGet({ 
  limit: 5,
  created_after: twentyFourHoursAgo,
  sort: '-created_at'
});
```

---

## 📈 Future Enhancements

With this flexible foundation, we can easily add:

1. **More sort fields:** `total_chunks`, `quality_score`, `status`
2. **Search:** `search=keyword` to filter by filename
3. **Data source filter:** Already supported via `source_id`
4. **Multiple status filter:** `status=processing,completed`
5. **Pagination metadata:** Total count, has_more, etc.
6. **Field selection:** `fields=id,filename,status` to reduce payload

---

## ✅ Checklist

### Backend
- [x] Add query parameters to `/v1/documents`
- [x] Implement company filtering
- [x] Implement date range filtering
- [x] Implement sorting
- [x] Add `company_hr_dataset` to `DocumentInfo`
- [x] Deprecate `/v1/documents/recent`
- [x] Update API documentation

### Frontend
- [x] Update `CompanyDataOverview` to use new endpoint
- [x] Fix field name (`file_size_bytes` → `file_size`)
- [x] Update imports
- [x] Regenerate API types
- [x] Test recent uploads display
- [x] Test company tags still work

### Documentation
- [x] Create API consolidation guide
- [x] Document migration path
- [x] Add examples for common use cases
- [x] Update deprecation timeline

### Deployment
- [x] Rebuild backend
- [x] Rebuild frontend
- [x] Test in production
- [x] Monitor for issues

---

## 🎯 Success Metrics

**API Design:**
- ✅ Reduced endpoints from 2 → 1 (for document listing)
- ✅ Increased filtering flexibility (5 new query params)
- ✅ Consistent response model across all scenarios

**Code Quality:**
- ✅ Eliminated code duplication
- ✅ Single source of truth for document listing
- ✅ More maintainable codebase

**User Experience:**
- ✅ No breaking changes (backward compatible)
- ✅ More powerful filtering for future features
- ✅ Company tags still display correctly

---

## 📚 Related Documentation

- `COMPANY_TAG_FEATURE.md` - Company tag implementation
- API Reference: `GET /v1/documents` - OpenAPI schema
- Frontend API hooks: `frontend/src/generated/documents/documents.ts`

---

**Status: COMPLETE AND DEPLOYED** ✅

This consolidation improves API design, reduces complexity, and provides a solid foundation for future filtering enhancements.

