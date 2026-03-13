# Frontend Architecture Audit & Recommendations

**Date**: 2025-10-01  
**Status**: Action Required  
**Priority**: High

## Executive Summary

Current frontend implementation **does not comply** with the [Type Generation Specification](./TYPE_GENERATION_SPECIFICATION.md) and has several React Query anti-patterns. This document outlines gaps and provides a migration plan.

---

## 🔴 Current State Analysis

### Type Management (❌ Not Compliant)

**Current Approach:**
- ✅ Manual type definitions in `frontend/src/types/api.ts` (349 lines)
- ✅ Duplicate type definitions in individual components
- ✅ Manual data transformations to map backend → frontend types
- ❌ No Orval configuration
- ❌ No generated types
- ❌ No type safety guarantees

**Example of Manual Types:**
```typescript
// frontend/src/pages/company-data/CompanyDataOverview.tsx
interface RecentUpload {
  id: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
  uploaded_at: string;
  file_size: number;
  chunks_created?: number;
  processing_time?: number;
}

// Manual transformation required:
const documents = response.data?.documents || response.data || [];
return documents.map((doc: any) => ({
  id: String(doc.id),
  filename: doc.original_filename || doc.filename,
  status: doc.status,
  uploaded_at: doc.created_at || doc.uploaded_at,
  file_size: doc.file_size,
  chunks_created: doc.total_chunks,
})) as RecentUpload[];
```

**Issues:**
1. **Type drift**: Frontend types can diverge from backend without detection
2. **Manual maintenance**: Every API change requires manual frontend updates
3. **Error prone**: Field name mismatches (e.g., `created_at` vs `uploaded_at`)
4. **Duplication**: Same types defined multiple times
5. **No compile-time safety**: `(doc: any)` defeats TypeScript

---

### API Client Architecture (❌ Not Compliant)

**Current Approach:**
```typescript
// Manual API calls in every component
const { data: recentUploads } = useQuery({
  queryKey: ['company-data', 'recent-uploads'],
  queryFn: async () => {
    const response = await apiService.request('GET', '/v1/documents/recent?limit=5');
    const documents = response.data?.documents || response.data || [];
    return documents.map((doc: any) => ({...})) as RecentUpload[];
  },
});
```

**Per Specification, Should Be:**
```typescript
// Auto-generated hook
import { useGetRecentDocuments } from '@/generated/api';

const { data: recentUploads } = useGetRecentDocuments({
  query: { limit: 5 }
});
// No manual transformation needed - types match backend!
```

**Issues:**
1. **Manual hooks**: Every component manually creates `useQuery` calls
2. **String-based URLs**: No compile-time checking of endpoints
3. **Manual transformations**: Data mapping should not exist
4. **No hook reusability**: Same queries duplicated across components

---

### React Query Best Practices (⚠️ Partially Compliant)

#### ❌ Query Key Management

**Current:**
```typescript
// Inconsistent and error-prone
queryKey: ['company-data', 'recent-uploads']
queryKey: ['company-data', 'stats', timeRange]
queryKey: ['documents', 'library', { search, status, ...}]
```

**Best Practice:**
```typescript
// Query key factory
export const queryKeys = {
  companyData: {
    all: ['company-data'] as const,
    stats: (range: string) => [...queryKeys.companyData.all, 'stats', range] as const,
    recentUploads: () => [...queryKeys.companyData.all, 'recent-uploads'] as const,
  },
  documents: {
    all: ['documents'] as const,
    lists: () => [...queryKeys.documents.all, 'list'] as const,
    list: (filters: DocumentFilters) => [...queryKeys.documents.lists(), filters] as const,
    details: () => [...queryKeys.documents.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.documents.details(), id] as const,
  },
};

// Usage
queryKey: queryKeys.companyData.recentUploads()
```

#### ⚠️ Inconsistent staleTime

```typescript
// Different values everywhere
staleTime: 30000,  // CompanyDataOverview stats
staleTime: 15000,  // CompanyDataOverview uploads
staleTime: 30000,  // DocumentLibrary
// Some queries have no staleTime at all
```

**Best Practice:**
```typescript
// frontend/src/lib/react-query.ts
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes default
      cacheTime: 10 * 60 * 1000, // 10 minutes
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// Override per-query only when needed
useQuery({
  queryKey: queryKeys.companyData.stats(timeRange),
  queryFn: getStats,
  staleTime: 30 * 1000, // 30 seconds for real-time stats
});
```

#### ❌ Manual Data Transformations in queryFn

**Current:**
```typescript
queryFn: async () => {
  const response = await apiService.request('GET', '/v1/documents/recent?limit=5');
  const documents = response.data?.documents || response.data || [];
  
  // This transformation should NOT be in the query function
  return documents.map((doc: any) => ({
    id: String(doc.id),
    filename: doc.original_filename || doc.filename,
    // ...more transformations
  })) as RecentUpload[];
}
```

**Why This Is Wrong:**
1. Makes caching inefficient (transformation runs every time)
2. Can't use `select` option for derived data
3. Couples data fetching with business logic

**Best Practice:**
```typescript
// With Orval-generated types, NO transformation needed
import { useGetRecentDocumentsV1DocumentsRecentGet } from '@/generated/api';

const { data } = useGetRecentDocumentsV1DocumentsRecentGet({ limit: 5 });
// data is already correctly typed!
```

#### ❌ Missing Error Boundaries

No global error handling for queries. Every component should not handle errors individually.

**Best Practice:**
```typescript
// App.tsx
<QueryErrorResetBoundary>
  {({ reset }) => (
    <ErrorBoundary onReset={reset} fallback={<ErrorFallback />}>
      <Suspense fallback={<LoadingFallback />}>
        <Routes />
      </Suspense>
    </ErrorBoundary>
  )}
</QueryErrorResetBoundary>
```

#### ⚠️ No Query Suspense

**Current**: Manual loading states everywhere
```typescript
{isLoading ? <Skeleton /> : <Content />}
```

**Best Practice**: Use Suspense
```typescript
// Mark queries as suspense-enabled
const { data } = useQuery({
  queryKey: ['data'],
  queryFn: fetchData,
  suspense: true, // No more isLoading checks!
});
```

---

## 📊 Compliance Matrix

| Requirement | Status | Current | Target |
|------------|--------|---------|--------|
| Auto-generated types | ❌ | Manual definitions | Orval-generated |
| Type safety | ⚠️ | Partial (manual) | Full (generated) |
| API client hooks | ❌ | Manual `useQuery` | Generated hooks |
| Query key factory | ❌ | Ad-hoc strings | Centralized factory |
| Default query options | ❌ | Per-query config | Global defaults |
| Error boundaries | ❌ | None | Global boundary |
| Suspense | ❌ | Manual loading | React Suspense |
| Data transformations | ❌ | In `queryFn` | Separate layer or none |

**Overall Compliance: 10% ❌**

---

## 🎯 Aggressive Migration Plan (Execute Now)

> **Approach**: Component-by-component | **Risk**: Low (parallel migration) | **Status**: EXECUTING

---

## PHASE 0: Foundation Setup

### Step 0.1: Install Dependencies

```bash
cd frontend
npm install -D orval
npm install @tanstack/react-query-devtools
```

**Validation:**
```bash
npm list orval
# Should show: orval@X.X.X
```

---

### Step 0.2: Create Orval Configuration

**Create `frontend/orval.config.ts`:**

```typescript
import { defineConfig } from 'orval';

export default defineConfig({
  'ai-platform': {
    input: {
      target: 'http://localhost:5001/openapi.json',
    },
    output: {
      mode: 'tags-split',
      target: './src/generated/api.ts',
      schemas: './src/generated/models',
      client: 'react-query',
      mock: false, // Disable for now
      prettier: true,
      override: {
        mutator: {
          path: './src/services/api-client.ts',
          name: 'customInstance',
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
});
```

**Validation:**
```bash
cat frontend/orval.config.ts
# Should match above
```

---

### Step 0.3: Create Custom API Client

**Create `frontend/src/services/api-client.ts`:**

```typescript
import Axios, { AxiosRequestConfig, AxiosResponse } from 'axios';

const API_URL = process.env.NODE_ENV === 'production' 
  ? '' 
  : (process.env.REACT_APP_API_URL || 'http://localhost:5001');

export const AXIOS_INSTANCE = Axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Flag to prevent infinite refresh loops
let isRefreshing = false;

// Request interceptor - add auth token
AXIOS_INSTANCE.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle 401 errors
AXIOS_INSTANCE.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !isRefreshing) {
      isRefreshing = true;
      try {
        // Try to refresh token
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await AXIOS_INSTANCE.post('/v1/auth/refresh', {
            refresh_token: refreshToken,
          });
          
          const { access_token, refresh_token: newRefreshToken } = response.data;
          localStorage.setItem('auth_token', access_token);
          localStorage.setItem('refresh_token', newRefreshToken);
          
          // Retry original request
          error.config.headers.Authorization = `Bearer ${access_token}`;
          return AXIOS_INSTANCE.request(error.config);
        }
      } catch (refreshError) {
        // Refresh failed - logout
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

// Custom instance for Orval
export const customInstance = <T>(
  config: AxiosRequestConfig,
  options?: AxiosRequestConfig,
): Promise<T> => {
  const promise = AXIOS_INSTANCE.request<T>({
    ...config,
    ...options,
  }).then(({ data }) => data);

  return promise;
};

export default customInstance;
```

**Validation:**
```bash
# Should compile without errors
cd frontend && npx tsc --noEmit
```

---

### Step 0.4: Create Query Key Factory

**Create `frontend/src/lib/query-keys.ts`:**

```typescript
export const queryKeys = {
  // Health & System
  health: {
    all: ['health'] as const,
    basic: () => [...queryKeys.health.all, 'basic'] as const,
    detailed: () => [...queryKeys.health.all, 'detailed'] as const,
  },

  // Authentication
  auth: {
    all: ['auth'] as const,
    currentUser: () => [...queryKeys.auth.all, 'current-user'] as const,
    sessions: () => [...queryKeys.auth.all, 'sessions'] as const,
  },

  // Documents
  documents: {
    all: ['documents'] as const,
    lists: () => [...queryKeys.documents.all, 'list'] as const,
    list: (filters: {
      search?: string;
      status?: string;
      source?: string;
      sort?: string;
      order?: string;
      page?: number;
    }) => [...queryKeys.documents.lists(), filters] as const,
    details: () => [...queryKeys.documents.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.documents.details(), id] as const,
    stats: (range: string) => [...queryKeys.documents.all, 'stats', range] as const,
    recent: (limit?: number) => [...queryKeys.documents.all, 'recent', limit ?? 5] as const,
  },

  // Company Data
  companyData: {
    all: ['company-data'] as const,
    stats: (range: string) => [...queryKeys.companyData.all, 'stats', range] as const,
    recentUploads: () => [...queryKeys.companyData.all, 'recent-uploads'] as const,
  },

  // Models
  models: {
    all: ['models'] as const,
    list: () => [...queryKeys.models.all, 'list'] as const,
    providers: () => [...queryKeys.models.all, 'providers'] as const,
    provider: (name: string) => [...queryKeys.models.providers(), name] as const,
    config: () => [...queryKeys.models.all, 'config'] as const,
  },

  // Configuration
  config: {
    all: ['config'] as const,
    full: () => [...queryKeys.config.all, 'full'] as const,
    branding: () => [...queryKeys.config.all, 'branding'] as const,
    dataSources: (enabledOnly?: boolean) => 
      [...queryKeys.config.all, 'data-sources', { enabledOnly }] as const,
    businessRules: () => [...queryKeys.config.all, 'business-rules'] as const,
  },

  // Admin
  admin: {
    all: ['admin'] as const,
    users: {
      all: [...queryKeys.admin.all, 'users'] as const,
      lists: () => [...queryKeys.admin.users.all, 'list'] as const,
      list: (filters: any) => [...queryKeys.admin.users.lists(), filters] as const,
      detail: (id: string) => [...queryKeys.admin.users.all, 'detail', id] as const,
    },
    audit: {
      all: [...queryKeys.admin.all, 'audit'] as const,
      logs: (filters: any) => [...queryKeys.admin.audit.all, 'logs', filters] as const,
      summary: () => [...queryKeys.admin.audit.all, 'summary'] as const,
    },
  },
} as const;
```

---

### Step 0.5: Create Query Client Configuration

**Create `frontend/src/lib/react-query.ts`:**

```typescript
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
      retry: 1,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
    mutations: {
      retry: 0,
    },
  },
});
```

**Update `frontend/src/index.tsx`:**

```typescript
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { queryClient } from './lib/react-query';

// ... existing imports

root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </React.StrictMode>
);
```

---

### Step 0.6: Add Error Boundary

**Create `frontend/src/components/common/ErrorBoundary.tsx`:**

```typescript
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { XCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

interface Props {
  children: ReactNode;
  onReset?: () => void;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: undefined });
    this.props.onReset?.();
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-background p-6">
          <div className="max-w-md w-full bg-surface border border-border rounded-lg p-8 text-center">
            <XCircleIcon className="w-16 h-16 text-ai-danger mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-text mb-2">Something went wrong</h2>
            <p className="text-muted mb-6">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <button
              onClick={this.handleReset}
              className="inline-flex items-center px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-hover transition-colors"
            >
              <ArrowPathIcon className="w-4 h-4 mr-2" />
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
```

**Update `frontend/src/App.tsx`:**

```typescript
import { ErrorBoundary } from './components/common/ErrorBoundary';

function App() {
  return (
    <ErrorBoundary>
      {/* existing app content */}
    </ErrorBoundary>
  );
}
```

---

### Step 0.7: Update package.json Scripts

**Add to `frontend/package.json`:**

```json
{
  "scripts": {
    "generate:api": "orval",
    "generate:api:watch": "orval --watch",
    "predev": "npm run generate:api",
    "prebuild": "npm run generate:api"
  }
}
```

---

### Step 0.8: Generate Types for First Time

```bash
# Ensure backend is running
docker-compose -f docker/docker-compose.yml ps

# Generate types
cd frontend
npm run generate:api
```

**Expected Output:**
```
✔ 🎉 - Your OpenAPI spec has been generated at ./src/generated/api.ts
```

**Validation:**
```bash
ls -la frontend/src/generated/
# Should see: api.ts, models/
```

---

### Step 0.9: Update .gitignore

**DO NOT ignore generated code** (keep in git for easier debugging):

**Ensure `frontend/.gitignore` does NOT contain:**
```
# Keep generated types in git
# src/generated/
```

**Commit foundation:**
```bash
git add frontend/
git commit -m "feat(frontend): setup Orval type generation and React Query architecture

- Add Orval config with custom API client
- Create query key factory
- Add React Query default options
- Add Error Boundary component
- Generate initial types from OpenAPI schema
- Add React Query DevTools"
```

---

## PHASE 1: Migrate Core Infrastructure

### Component 1.1: Update API Service Exports

**Modify `frontend/src/services/api.ts`:**

Keep the `ApiService` class for now (backwards compatibility), but add a comment:

```typescript
// TODO: This class will be deprecated after migration to generated hooks
// Current usage: Legacy components still using apiService.request()
```

**Create `frontend/src/services/index.ts`:**

```typescript
// Export both old and new for parallel migration
export { apiService } from './api';
export { AXIOS_INSTANCE, customInstance } from './api-client';
```

---

### Component 1.2: Health Check (Pilot Migration)

**Before** (`frontend/src/pages/HealthCheck.tsx` - create if doesn't exist):

```typescript
const { data, isLoading } = useQuery({
  queryKey: ['health'],
  queryFn: async () => {
    const response = await apiService.request('GET', '/health/');
    return response.data;
  },
});
```

**After:**

```typescript
import { useHealthCheckHealthGet } from '@/generated/api';
import { queryKeys } from '@/lib/query-keys';

const { data, isLoading } = useHealthCheckHealthGet({
  query: {
    queryKey: queryKeys.health.basic(),
  },
});
```

**Test:**
- Navigate to health check page
- Verify data loads correctly
- Check React Query DevTools shows correct query key
- Check Network tab shows correct API call

**Commit:**
```bash
git add .
git commit -m "feat(frontend): migrate health check to generated types (pilot)"
```

---

## PHASE 2: Migrate Documents Module

### Component 2.1: Document Library

**File:** `frontend/src/pages/company-data/DocumentLibrary.tsx`

**Current Issues:**
- Manual `Document` interface
- Manual `DocumentsResponse` interface
- Manual API call with `apiService.request()`

**Migration Steps:**

1. **Remove manual interfaces** (lines 28-58)
2. **Import generated types:**
   ```typescript
   import {
     useListDocumentsV1DocumentsGet,
     useDeleteDocumentV1DocumentsDocumentIdDelete,
     useRetryDocumentProcessingV1DocumentsDocumentIdRetryPost,
     DocumentInfo,
     DocumentListResponse,
   } from '@/generated/api';
   import { queryKeys } from '@/lib/query-keys';
   ```

3. **Replace documents query:**
   ```typescript
   // BEFORE
   const { data: documentsResponse, isLoading, error } = useQuery({
     queryKey: ['documents', 'library', { ... }],
     queryFn: async () => {
       const params = new URLSearchParams({...});
       const response = await apiService.request('GET', `/v1/documents?${params}`);
       return response.data as DocumentsResponse;
     },
   });

   // AFTER
   const { data: documentsResponse, isLoading } = useListDocumentsV1DocumentsGet(
     {
       page: page,
       page_size: pageSize,
       sort_by: sortBy,
       sort_order: sortOrder,
       ...(searchQuery && { search: searchQuery }),
       ...(statusFilter !== 'all' && { status: statusFilter }),
       ...(sourceFilter !== 'all' && { data_source_type: sourceFilter }),
     },
     {
       query: {
         queryKey: queryKeys.documents.list({
           search: searchQuery,
           status: statusFilter,
           source: sourceFilter,
           sort: sortBy,
           order: sortOrder,
           page,
         }),
       },
     }
   );
   ```

4. **Replace delete mutation:**
   ```typescript
   // BEFORE
   const deleteDocumentMutation = useMutation({
     mutationFn: async (documentId: number) => {
       await apiService.request('DELETE', `/v1/documents/${documentId}`);
     },
     ...
   });

   // AFTER
   const { mutate: deleteDocument } = useDeleteDocumentV1DocumentsDocumentIdDelete({
     mutation: {
       onSuccess: () => {
         queryClient.invalidateQueries({ queryKey: queryKeys.documents.lists() });
         addToast({ message: 'Document deleted successfully', kind: 'success' });
       },
       onError: (error) => {
         addToast({ message: `Failed to delete document: ${error.message}`, kind: 'error' });
       },
     },
   });
   ```

5. **Replace retry mutation:**
   ```typescript
   const { mutate: retryDocument } = useRetryDocumentProcessingV1DocumentsDocumentIdRetryPost({
     mutation: {
       onSuccess: () => {
         queryClient.invalidateQueries({ queryKey: queryKeys.documents.lists() });
         addToast({ message: 'Document reprocessing started', kind: 'success' });
       },
     },
   });
   ```

6. **Update type references:**
   - Change `Document` → `DocumentInfo`
   - Change `DocumentsResponse` → `DocumentListResponse`

**Testing Checklist:**
- [ ] Documents list loads
- [ ] Search works
- [ ] Filtering works (status, source)
- [ ] Sorting works
- [ ] Pagination works
- [ ] Delete document works
- [ ] Retry failed document works
- [ ] No TypeScript errors
- [ ] React Query DevTools shows correct keys

**Commit:**
```bash
git add frontend/src/pages/company-data/DocumentLibrary.tsx
git commit -m "feat(frontend): migrate DocumentLibrary to generated types"
```

---

### Component 2.2: Document Upload Modal

**File:** `frontend/src/components/company-data/DocumentUploadModal.tsx`

**Migration Steps:**

1. **Import generated mutation:**
   ```typescript
   import { useUploadDocumentsV1DocumentsUploadPost } from '@/generated/api';
   ```

2. **Replace upload mutation:**
   ```typescript
   // AFTER
   const { mutateAsync: uploadDocument } = useUploadDocumentsV1DocumentsUploadPost({
     mutation: {
       onSuccess: (data) => {
         queryClient.invalidateQueries({ queryKey: queryKeys.documents.all });
         queryClient.invalidateQueries({ queryKey: queryKeys.companyData.all });
       },
     },
   });
   ```

3. **Update upload function:**
   ```typescript
   const startUpload = async (uploadFile: UploadFile) => {
     const formData = new FormData();
     const fileToUpload = uploadFile.displayFilename !== uploadFile.file.name
       ? new File([uploadFile.file], uploadFile.displayFilename, { type: uploadFile.file.type })
       : uploadFile.file;
     
     formData.append('files', fileToUpload);
     formData.append('source_id', processingOptions.dataSource);
     formData.append('chunking_strategy', processingOptions.chunkingStrategy);
     // ... other fields

     try {
       await uploadDocument({ data: formData });
       // Update file status
     } catch (error) {
       // Handle error
     }
   };
   ```

**Testing Checklist:**
- [ ] Modal opens
- [ ] File selection works
- [ ] Drag & drop works
- [ ] Inline rename works
- [ ] Upload starts
- [ ] Progress shows
- [ ] Success message appears
- [ ] Modal closes on success
- [ ] Documents appear in library

**Commit:**
```bash
git add frontend/src/components/company-data/DocumentUploadModal.tsx
git commit -m "feat(frontend): migrate DocumentUploadModal to generated types"
```

---

### Component 2.3: Company Data Overview

**File:** `frontend/src/pages/company-data/CompanyDataOverview.tsx`

**Current Issues:**
- Manual `DataIngestionStats` interface
- Manual `RecentUpload` interface
- **Manual data transformation** (biggest issue!)

**Migration Steps:**

1. **Remove manual interfaces and transformations**

2. **Import generated hooks:**
   ```typescript
   import {
     useGetDocumentStatsV1DocumentsStatsGet,
     useGetRecentDocumentsV1DocumentsRecentGet,
   } from '@/generated/api';
   ```

3. **Replace stats query:**
   ```typescript
   const { data: stats, isLoading: statsLoading } = useGetDocumentStatsV1DocumentsStatsGet(
     { range: timeRange },
     {
       query: {
         queryKey: queryKeys.companyData.stats(timeRange),
       },
     }
   );
   ```

4. **Replace recent uploads query (NO MORE TRANSFORMATIONS!):**
   ```typescript
   const { data: recentData, isLoading: uploadsLoading } = useGetRecentDocumentsV1DocumentsRecentGet(
     { limit: 5 },
     {
       query: {
         queryKey: queryKeys.companyData.recentUploads(),
       },
     }
   );

   // Access documents directly
   const recentUploads = recentData?.documents || [];
   ```

5. **Update UI to use correct field names:**
   ```typescript
   // Change uploadedfilename to original_filename
   <p className="text-sm font-medium text-text truncate">
     {upload.original_filename}
   </p>

   // Change uploaded_at to created_at
   <span>{formatDate(upload.created_at)}</span>
   ```

**Testing Checklist:**
- [ ] Stats cards load (Total, Processing, Completed, Chunks)
- [ ] Recent uploads list shows
- [ ] File names display correctly
- [ ] Upload dates display correctly
- [ ] Status badges show correctly
- [ ] No manual transformations in code

**Commit:**
```bash
git add frontend/src/pages/company-data/CompanyDataOverview.tsx
git commit -m "feat(frontend): migrate CompanyDataOverview to generated types

- Remove manual RecentUpload interface
- Remove manual data transformations
- Use correct backend field names directly"
```

---

## PHASE 3: Migrate Auth Module

### Component 3.1: Login Page

**File:** `frontend/src/pages/auth/LoginPage.tsx`

**Migration Steps:**

1. **Import generated mutations:**
   ```typescript
   import { useLoginV1AuthLoginPost } from '@/generated/api';
   ```

2. **Replace login mutation:**
   ```typescript
   const { mutate: login, isPending } = useLoginV1AuthLoginPost({
     mutation: {
       onSuccess: (data) => {
         localStorage.setItem('auth_token', data.access_token);
         localStorage.setItem('refresh_token', data.refresh_token);
         // ... handle success
       },
       onError: (error) => {
         // ... handle error
       },
     },
   });
   ```

3. **Update form submit:**
   ```typescript
   const onSubmit = (values: { email: string; password: string }) => {
     login({
       data: {
         email: values.email,
         password: values.password,
         remember_me: false,
       },
     });
   };
   ```

**Testing Checklist:**
- [ ] Login form displays
- [ ] Email validation works
- [ ] Password validation works
- [ ] Login submits
- [ ] Success redirects to dashboard
- [ ] Error shows toast message

**Commit:**
```bash
git add frontend/src/pages/auth/LoginPage.tsx
git commit -m "feat(frontend): migrate LoginPage to generated types"
```

---

### Component 3.2: Auth Context

**File:** `frontend/src/contexts/AuthContext.tsx`

**Migration Steps:**

1. **Import generated hooks:**
   ```typescript
   import {
     useGetCurrentUserProfileV1AuthMeGet,
     useLogoutV1AuthLogoutPost,
     UserProfile,
   } from '@/generated/api';
   ```

2. **Replace current user query:**
   ```typescript
   const { data: user, refetch } = useGetCurrentUserProfileV1AuthMeGet(
     undefined,
     {
       query: {
         queryKey: queryKeys.auth.currentUser(),
         enabled: !!token,
       },
     }
   );
   ```

3. **Replace logout mutation:**
   ```typescript
   const { mutate: logoutMutation } = useLogoutV1AuthLogoutPost();
   ```

**Testing Checklist:**
- [ ] User loads on app start
- [ ] Protected routes work
- [ ] Logout works
- [ ] Token refresh works

**Commit:**
```bash
git add frontend/src/contexts/AuthContext.tsx
git commit -m "feat(frontend): migrate AuthContext to generated types"
```

---

## PHASE 4: Migrate Models & Config

### Component 4.1: Model Configuration Page

**File:** `frontend/src/pages/models/*`

**Quick Migration:**
```typescript
import {
  useListModelsV1ModelsGet,
  useListProvidersV1ModelsProvidersGet,
  useTestModelV1ModelsTestPost,
} from '@/generated/api';
```

**Testing Checklist:**
- [ ] Models list loads
- [ ] Providers show status
- [ ] Test model works

---

## PHASE 5: Cleanup

### Step 5.1: Delete Manual Types

```bash
# Backup first
cp frontend/src/types/api.ts frontend/src/types/api.ts.backup

# Then delete
rm frontend/src/types/api.ts
```

### Step 5.2: Update Imports

Search and replace across codebase:
```bash
# Find any remaining imports
cd frontend
grep -r "from '../types/api'" src/
grep -r "from '../../types/api'" src/

# They should all be replaced with generated imports
```

### Step 5.3: Final Test

```bash
# Full type check
cd frontend && npx tsc --noEmit

# Build
npm run build

# Run tests
npm test
```

---

## Component Migration Checklist

For each component, follow this checklist:

### Pre-Migration
- [ ] Identify all manual interfaces
- [ ] Identify all `apiService.request()` calls
- [ ] Identify all data transformations
- [ ] Note any custom error handling
- [ ] Create a git branch: `git checkout -b migrate/component-name`

### During Migration
- [ ] Import generated types
- [ ] Replace manual interfaces
- [ ] Replace API calls with generated hooks
- [ ] Remove data transformations
- [ ] Use query key factory
- [ ] Update TypeScript types
- [ ] Remove unused imports

### Post-Migration
- [ ] No TypeScript errors
- [ ] Component renders
- [ ] All features work
- [ ] React Query DevTools shows correct keys
- [ ] No console errors
- [ ] Manual testing passed
- [ ] Commit changes: `git commit -m "feat: migrate ComponentName"`

---

## Rollback Procedure

If anything breaks:

1. **Immediate Rollback:**
   ```bash
   git checkout main
   git branch -D migrate/component-name
   ```

2. **Keep Generated Types:**
   The generated types are safe and don't affect existing code

3. **Revert One Component:**
   ```bash
   git checkout main -- frontend/src/path/to/component.tsx
   ```

---

## Success Criteria

✅ **Phase Complete When:**
- All components use generated types
- No manual interfaces remain
- No `apiService.request()` calls remain
- No manual data transformations
- All tests pass
- TypeScript compiles without errors
- App works identically to before migration

---

## Migration Progress

| Phase | Status | Components |
|-------|--------|------------|
| Phase 0: Foundation | ⏳ IN PROGRESS | Setup, config, infrastructure |
| Phase 1: Core | ⏳ PENDING | Health, API client |
| Phase 2: Documents | ⏳ PENDING | Library, Upload, Overview (3 components) |
| Phase 3: Auth | ⏳ PENDING | Login, Context (2 components) |
| Phase 4: Models/Config | ⏳ PENDING | Models page |
| Phase 5: Cleanup | ⏳ PENDING | Delete old types, final tests |

---

## Next Immediate Actions

1. ✅ Review this plan
2. ⏳ Start Phase 0 (Foundation Setup)
3. ⏳ Test with Phase 1 (Health Check pilot)
4. ⏳ Proceed to Phase 2 (Documents)
5. ⏳ Continue systematically through all phases

**Ready to start Phase 0?**

---

## 💰 Cost-Benefit Analysis

### Time Investment
- **Setup & Migration**: ~4 weeks (1 developer)
- **Training**: 2-4 hours for team

### Long-term Savings (per year)
- **Reduced bugs**: ~50 hours (no more field name mismatches)
- **Faster API changes**: ~80 hours (no manual type updates)
- **Onboarding**: ~20 hours (auto-generated docs)
- **Maintenance**: ~40 hours (single source of truth)

**Total Annual Savings: ~190 hours (~$30-50K value)**

### Risk Mitigation
- ✅ Parallel migration (low risk)
- ✅ Module-by-module approach
- ✅ Existing types as fallback during transition
- ✅ Comprehensive testing at each phase

---

## 🚀 Quick Wins (Can Do Today)

### 1. Query Key Factory (2 hours)
Create `frontend/src/lib/query-keys.ts` and start using it for new queries.

### 2. Query Client Defaults (30 minutes)
Set default `staleTime` and `cacheTime` to reduce boilerplate.

### 3. Remove One Transformation (1 hour)
Fix the backend `/v1/documents/recent` response to match frontend expectations,
eliminating the need for transformation.

### 4. Add Error Boundary (1 hour)
Wrap app in `QueryErrorResetBoundary` + `ErrorBoundary`.

---

## 📋 Next Steps

**Immediate Actions:**
1. ✅ Review this audit with team
2. ⏳ Approve migration plan
3. ⏳ Setup Orval (Phase 1, Day 1)
4. ⏳ Pilot with one component (Phase 1, Day 2-3)

**Decision Required:**
- **Timeline**: 4-week migration or faster (parallel work)?
- **Pilot component**: `CompanyDataOverview.tsx` (recommended) or other?
- **Keep generated in git**: Yes (recommended) or No?

---

## 📚 References

- [Type Generation Specification](./TYPE_GENERATION_SPECIFICATION.md)
- [Orval Documentation](https://orval.dev/)
- [React Query Best Practices](https://tkdodo.eu/blog/practical-react-query)
- [FastAPI OpenAPI](http://localhost:5001/openapi.json)

---

## Appendix: Backend Response Inconsistencies

**Issue**: Backend returns nested structures inconsistently

Example 1: `/v1/documents/recent`
```json
{
  "documents": [...],
  "total": 5,
  "limit": 5
}
```

Example 2: `/v1/documents/stats`
```json
{
  "total_documents": 5,
  "processing_documents": 2,
  ...
}
```

**Recommendation**: Standardize backend responses to match OpenAPI schema exactly.
This will eliminate the need for frontend transformations.

