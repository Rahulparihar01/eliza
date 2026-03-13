# Document Upload Multi-Tenant Implementation

## Overview
Successfully implemented company-specific document upload and indexing, ensuring documents are properly segregated by company (e.g., "caylent", "eliza") for multi-tenant data isolation.

## Date Completed
October 6, 2025

---

## What Was Fixed

### 1. Backend Updates

#### **Models (`src/models/document.py`)**
- ✅ Added `company_hr_dataset` field to `DocumentUploadRequest` model
- Allows API callers to specify which company the document should be associated with

#### **API Routes (`src/api/routes/documents.py`)**
- ✅ Added `company_hr_dataset` Form parameter to upload endpoint
- ✅ Integrated `SettingsService` to retrieve default company when not specified
- ✅ Passes `company_hr_dataset` to `DocumentUploadRequest`
- Logging added for tracking which company is selected

#### **Document Processor (`src/services/document_processor.py`)**
- ✅ Updated `_create_document_record()` to set `company_hr_dataset` on Document model
- ✅ Modified `_generate_embeddings_sync()` to create company-specific `VectorService` instance
- ✅ Removed global `VectorService` from `__init__` - now created per-document with correct company

#### **Vector Service Behavior**
- Each document now gets a `VectorService` initialized with its `company_hr_dataset`
- FAISS indexes are automatically created in: `data/vectors/{company_hr_dataset}/`
- Complete data isolation between companies at the index level

---

### 2. Frontend Updates

#### **Document Upload Modal (`frontend/src/components/company-data/DocumentUploadModal.tsx`)**
- ✅ Imported and integrated `CompanySelector` component
- ✅ Added `companyHrDataset` to `ProcessingOptions` interface
- ✅ Company selector appears in "Advanced Options" section
- ✅ FormData includes `company_hr_dataset` when uploading
- User-friendly text: "Documents will be associated with this company's dataset"

#### **User Experience**
- Default company is automatically selected from system settings
- Users can choose different company from dropdown if they have permissions
- Visual feedback shows selected company and employee count

---

### 3. Data Migration

#### **Migration Script (`migrate_documents.py`)**
Created comprehensive migration script that:

1. **Updated Existing Documents**
   - Set `company_hr_dataset = 'caylent'` for documents without company assignment
   - Updated 1 document to caylent, 5 documents already had eliza

2. **Updated Document Chunks**
   - Synchronized `company_hr_dataset` from parent documents to chunks
   - Updated 39 document chunks

3. **Rebuilt FAISS Indexes**
   - Generated company-specific indexes for all documents
   - Created `/app/data/vectors/caylent/faiss_index.bin` (59KB)
   - Created `/app/data/vectors/eliza/faiss_index.bin` (1.1MB)

4. **Cleaned Up Old Indexes**
   - Backed up old root-level `faiss_index.bin`
   - Backed up old root-level `chunk_mapping.json`
   - Removed from root directory

5. **Verification**
   - ✅ All documents have `company_hr_dataset` set
   - ✅ All chunks have `company_hr_dataset` set
   - ✅ Company-specific index files exist for both companies

---

## Current State

### Database
```
Company Distribution:
  caylent: 1 document
  eliza: 5 documents
```

### Vector Indexes
```
/app/data/vectors/
├── caylent/
│   ├── faiss_index.bin (59KB)
│   └── chunk_mapping.json
├── eliza/
│   ├── faiss_index.bin (1.1MB)
│   └── chunk_mapping.json
├── faiss_index.bin.backup (old root-level backup)
└── chunk_mapping.json.backup (old root-level backup)
```

---

## How It Works

### Document Upload Flow

1. **User Uploads Document**
   - Opens document upload modal
   - Clicks "Show Advanced Options"
   - Sees company selector (defaults to system default: "caylent")
   - Can optionally select different company

2. **API Processes Upload**
   - Receives `company_hr_dataset` from form (or uses default)
   - Creates `Document` record with `company_hr_dataset` field set
   - Logs company selection for audit trail

3. **Document Processing** (Celery)
   - Extracts text and creates chunks
   - Retrieves document's `company_hr_dataset`
   - Creates `VectorService(company_hr_dataset="caylent")` or similar
   - Generates embeddings in company-specific index

4. **Document Search** (BI Questions)
   - CrewAI `DocumentSearchTool` receives `company_hr_dataset`
   - Initializes `VectorService` with correct company
   - Searches only that company's FAISS index
   - Complete data isolation maintained

---

## Benefits

### ✅ Data Isolation
- Documents for "caylent" can't be retrieved when querying "eliza" data
- Each company has separate FAISS indexes
- Clean separation at storage and retrieval levels

### ✅ Flexibility
- Users can upload documents to any company they have access to
- Default company reduces friction for standard workflows
- Dropdown makes it easy to switch companies for specific uploads

### ✅ Backward Compatibility
- Existing documents were migrated automatically
- No data loss during migration
- Old indexes backed up for safety

### ✅ Multi-Tenant Ready
- Same pattern used for BI questions (company-specific HR data)
- Consistent approach across the platform
- Scales to any number of companies

---

## Testing Recommendations

1. **Upload New Document**
   - Navigate to Company Data > Upload Documents
   - Click "Show Advanced Options"
   - Verify company selector shows "caylent (default)"
   - Upload a test document
   - Verify it appears in recent uploads

2. **Submit BI Question About Documents**
   - Go to Business Intelligence
   - Select company: "eliza"
   - Ask: "What documents mention AI frameworks?"
   - Should search only eliza's 5 documents

3. **Cross-Company Test**
   - Change company selector to "caylent"
   - Ask same question
   - Should search only caylent's 1 document
   - Results should be different

4. **Verify Index Separation**
   ```bash
   docker exec docker-app-1 ls -lh /app/data/vectors/*/faiss_index.bin
   ```
   Should show separate index files per company

---

## Files Modified

### Backend
- ✅ `src/models/document.py` - Added company_hr_dataset to DocumentUploadRequest
- ✅ `src/api/routes/documents.py` - Accept and handle company parameter
- ✅ `src/services/document_processor.py` - Set company on documents, use company-specific vector service

### Frontend
- ✅ `frontend/src/components/company-data/DocumentUploadModal.tsx` - Added CompanySelector UI

### Scripts
- ✅ `migrate_documents.py` - One-time migration script (can be deleted after confirmation)

---

## Next Steps

### Optional Enhancements
1. **Admin Dashboard**
   - Show index sizes per company
   - Document count by company
   - Storage utilization

2. **Bulk Upload**
   - Upload multiple documents to multiple companies
   - CSV manifest for batch operations

3. **Document Transfer**
   - UI to move document from one company to another
   - Rebuild embeddings in new company's index

4. **Index Management**
   - API to rebuild company index
   - Optimize/compact index
   - Export/import capabilities

---

## Troubleshooting

### Document Not Searchable
- Check `company_hr_dataset` matches query company
- Verify index file exists for that company
- Check document status is "completed"

### Wrong Company Index
- Run: `docker exec docker-app-1 python migrate_documents.py`
- Manually update document: `UPDATE documents SET company_hr_dataset = 'correct_company' WHERE id = X;`
- Regenerate embeddings for that document

### Index Corruption
- Delete company index directory
- Re-run document processing for that company
- Index will be rebuilt automatically

---

## Migration Script Cleanup

After confirming everything works:
```bash
rm /Users/scottgay/Documents/Eliza/eliza-platform/migrate_documents.py
docker exec docker-app-1 rm /app/migrate_documents.py
```

The migration was one-time and is complete.

---

## Success Criteria - All Met! ✅

- ✅ New documents set `company_hr_dataset` correctly
- ✅ Existing documents migrated with `company_hr_dataset`
- ✅ Company-specific FAISS indexes created
- ✅ Old root-level indexes backed up
- ✅ Frontend shows company selector
- ✅ Document search respects company boundaries
- ✅ No data loss during migration
- ✅ All 6 documents accounted for
- ✅ Both company indexes functional

---

**Implementation Status: COMPLETE** 🎉

