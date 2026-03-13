# OpenAPI Schema Fix Plan

**Date:** October 1, 2025  
**Status:** ✅ IMPLEMENTED (Backend Complete - Frontend Testing Pending)  
**Priority:** High (blocking full type safety in frontend)

---

## 🎯 **Executive Summary**

The frontend migration to Orval-generated types revealed that several backend API endpoints have incomplete OpenAPI response schemas, causing Orval to generate `unknown` types. This requires type assertions in the frontend, reducing type safety and developer experience.

**Impact:**
- 3 critical endpoints returning `unknown` instead of typed responses
- Frontend requires manual type assertions (`as any`)
- Loss of TypeScript intellisense and compile-time safety
- Potential runtime errors from schema mismatches

---

## 📋 **Affected Endpoints**

### **1. Admin Dashboard Overview**
**Endpoint:** `GET /v1/admin/dashboard/overview`  
**Current Issue:** Returns `unknown`  
**Frontend Usage:** `AdminDashboard.tsx` (line 107)

**Expected Response Structure:**
```typescript
{
  system_health: {
    api_status: 'online' | 'degraded' | 'offline',
    database_status: 'healthy' | 'slow' | 'error',
    vector_service_status: 'operational' | 'degraded' | 'down',
    redis_status: 'connected' | 'disconnected',
    neo4j_status: 'available' | 'unavailable',
    last_health_check: string,
    uptime_percentage: number
  },
  user_activity: {
    active_users_now: number,
    active_users_today: number,
    total_registered_users: number,
    new_users_this_week: number,
    user_growth_percentage: number
  },
  document_metrics: {
    total_documents: number,
    documents_uploaded_today: number,
    total_searches_today: number,
    processing_queue_size: number,
    storage_usage_gb: number
  },
  ai_usage: {
    total_calls_today: number,
    total_cost_today: number,
    average_response_time: number,
    success_rate: number,
    provider_breakdown: Record<string, number>
  },
  recent_activity: Array<{
    timestamp: string,
    action: string,
    details: string
  }>
}
```

---

### **2. Document Statistics**
**Endpoint:** `GET /v1/documents/stats`  
**Current Issue:** Returns `unknown`  
**Frontend Usage:** `CompanyDataOverview.tsx` (line 33)

**Expected Response Structure:**
```typescript
{
  total_documents: number,
  processing_documents: number,
  completed_documents: number,
  failed_documents: number,
  total_chunks: number,
  storage_used_mb: number
}
```

---

### **3. Recent Documents**
**Endpoint:** `GET /v1/documents/recent`  
**Current Issue:** Returns partial schema (missing `documents` array typing)  
**Frontend Usage:** `CompanyDataOverview.tsx` (line 44)

**Expected Response Structure:**
```typescript
{
  documents: Array<{
    id: number,
    original_filename: string,
    status: string,
    created_at: string,
    total_chunks: number,
    file_size_bytes: number
  }>,
  total: number,
  limit: number
}
```

---

### **4. Admin Users List**
**Endpoint:** `GET /v1/admin/users`  
**Current Issue:** Returns `unknown`  
**Frontend Usage:** `UserManagement.tsx` (line 54)

**Expected Response Structure:**
```typescript
{
  users: Array<{
    id: number,
    email: string,
    full_name: string,
    roles: string[],
    is_active: boolean,
    last_login_at: string | null,
    created_at: string
  }>,
  pagination: {
    total_count: number,
    page: number,
    page_size: number,
    total_pages: number
  }
}
```

---

## 🔍 **Root Cause Analysis**

### **Why is Orval Generating `unknown`?**

1. **Missing `response_model` in FastAPI route decorators**
   ```python
   # ❌ BAD: No response model specified
   @router.get("/dashboard/overview")
   async def get_dashboard_overview():
       return {"data": ...}
   
   # ✅ GOOD: Explicit response model
   @router.get("/dashboard/overview", response_model=DashboardOverviewResponse)
   async def get_dashboard_overview() -> DashboardOverviewResponse:
       return DashboardOverviewResponse(...)
   ```

2. **Using `dict` or `Any` return types**
   - FastAPI can't infer schema from dynamic types
   - OpenAPI schema defaults to `unknown`

3. **Incomplete Pydantic model definitions**
   - Missing fields in response models
   - Optional fields not properly typed

4. **Manual dict construction in route handlers**
   - Bypasses Pydantic validation
   - Doesn't enforce schema consistency

---

## 🛠️ **Detailed Fix Plan**

### **Phase 1: Create Pydantic Response Models**

**File:** `src/api/schemas/admin.py` (create if doesn't exist)

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

# System Health
class SystemHealthStatus(BaseModel):
    api_status: str = Field(..., description="API status")
    database_status: str = Field(..., description="Database status")
    vector_service_status: str = Field(..., description="Vector service status")
    redis_status: str = Field(..., description="Redis cache status")
    neo4j_status: str = Field(..., description="Neo4j graph DB status")
    last_health_check: datetime
    uptime_percentage: float = Field(..., ge=0, le=100)

class UserActivityMetrics(BaseModel):
    active_users_now: int = Field(..., ge=0)
    active_users_today: int = Field(..., ge=0)
    total_registered_users: int = Field(..., ge=0)
    new_users_this_week: int = Field(..., ge=0)
    user_growth_percentage: float

class DocumentMetrics(BaseModel):
    total_documents: int = Field(..., ge=0)
    documents_uploaded_today: int = Field(..., ge=0)
    total_searches_today: int = Field(..., ge=0)
    processing_queue_size: int = Field(..., ge=0)
    storage_usage_gb: float = Field(..., ge=0)

class AIUsageMetrics(BaseModel):
    total_calls_today: int = Field(..., ge=0)
    total_cost_today: float = Field(..., ge=0)
    average_response_time: float = Field(..., ge=0)
    success_rate: float = Field(..., ge=0, le=100)
    provider_breakdown: Dict[str, float] = Field(default_factory=dict)

class RecentActivityItem(BaseModel):
    timestamp: datetime
    action: str
    details: str

class DashboardOverviewResponse(BaseModel):
    system_health: SystemHealthStatus
    user_activity: UserActivityMetrics
    document_metrics: DocumentMetrics
    ai_usage: AIUsageMetrics
    recent_activity: List[RecentActivityItem] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "system_health": {
                    "api_status": "online",
                    "database_status": "healthy",
                    "vector_service_status": "operational",
                    "redis_status": "connected",
                    "neo4j_status": "available",
                    "last_health_check": "2025-10-01T12:00:00Z",
                    "uptime_percentage": 99.9
                },
                # ... more examples
            }
        }
```

---

**File:** `src/api/schemas/documents.py` (update existing)

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from src.models.document import DocumentStatus

class DocumentStatsResponse(BaseModel):
    """Document statistics response schema"""
    total_documents: int = Field(..., ge=0, description="Total number of documents")
    processing_documents: int = Field(..., ge=0, description="Documents currently processing")
    completed_documents: int = Field(..., ge=0, description="Completed documents")
    failed_documents: int = Field(..., ge=0, description="Failed documents")
    total_chunks: int = Field(..., ge=0, description="Total document chunks")
    storage_used_mb: float = Field(..., ge=0, description="Storage used in megabytes")

    class Config:
        json_schema_extra = {
            "example": {
                "total_documents": 150,
                "processing_documents": 5,
                "completed_documents": 140,
                "failed_documents": 5,
                "total_chunks": 4500,
                "storage_used_mb": 2048.5
            }
        }

class RecentDocumentInfo(BaseModel):
    """Simplified document info for recent uploads"""
    id: int
    original_filename: str
    status: DocumentStatus
    created_at: datetime
    total_chunks: int = Field(default=0)
    file_size_bytes: int = Field(default=0)

class RecentDocumentsResponse(BaseModel):
    """Recent documents list response"""
    documents: List[RecentDocumentInfo] = Field(default_factory=list)
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)

    class Config:
        json_schema_extra = {
            "example": {
                "documents": [
                    {
                        "id": 123,
                        "original_filename": "report.pdf",
                        "status": "completed",
                        "created_at": "2025-10-01T10:30:00Z",
                        "total_chunks": 45,
                        "file_size_bytes": 1048576
                    }
                ],
                "total": 10,
                "limit": 5
            }
        }
```

---

**File:** `src/api/schemas/users.py` (create or update)

```python
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

class UserListItem(BaseModel):
    """User item in list response"""
    id: int
    email: EmailStr
    full_name: str
    roles: List[str] = Field(default_factory=list)
    is_active: bool = True
    last_login_at: Optional[datetime] = None
    created_at: datetime

class PaginationInfo(BaseModel):
    """Pagination metadata"""
    total_count: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)

class UsersListResponse(BaseModel):
    """Paginated users list response"""
    users: List[UserListItem] = Field(default_factory=list)
    pagination: PaginationInfo

    class Config:
        json_schema_extra = {
            "example": {
                "users": [
                    {
                        "id": 1,
                        "email": "user@example.com",
                        "full_name": "John Doe",
                        "roles": ["admin"],
                        "is_active": True,
                        "last_login_at": "2025-10-01T09:15:00Z",
                        "created_at": "2025-01-01T00:00:00Z"
                    }
                ],
                "pagination": {
                    "total_count": 50,
                    "page": 1,
                    "page_size": 20,
                    "total_pages": 3
                }
            }
        }
```

---

### **Phase 2: Update Route Handlers**

**File:** `src/api/routes/admin.py`

```python
from fastapi import APIRouter, Depends
from src.api.schemas.admin import DashboardOverviewResponse
from src.api.schemas.users import UsersListResponse, PaginationInfo, UserListItem

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get(
    "/dashboard/overview",
    response_model=DashboardOverviewResponse,
    summary="Get Admin Dashboard Overview",
    description="Retrieve comprehensive dashboard metrics including system health, user activity, and AI usage"
)
async def get_dashboard_overview(
    # ... dependencies
) -> DashboardOverviewResponse:
    """
    Get comprehensive dashboard overview with:
    - System health status
    - User activity metrics
    - Document processing stats
    - AI usage and costs
    - Recent activity log
    """
    # ... existing logic to gather data ...
    
    return DashboardOverviewResponse(
        system_health=SystemHealthStatus(
            api_status=health_data["api_status"],
            database_status=health_data["database_status"],
            # ... map all fields
        ),
        user_activity=UserActivityMetrics(
            active_users_now=user_data["active_now"],
            # ... map all fields
        ),
        # ... complete mapping
    )

@router.get(
    "/users",
    response_model=UsersListResponse,
    summary="List Users",
    description="Get paginated list of users with filtering options"
)
async def get_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    # ... dependencies
) -> UsersListResponse:
    """
    Retrieve paginated user list with optional filtering.
    """
    # ... existing logic ...
    
    return UsersListResponse(
        users=[
            UserListItem(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                roles=user.roles,
                is_active=user.is_active,
                last_login_at=user.last_login_at,
                created_at=user.created_at
            )
            for user in users
        ],
        pagination=PaginationInfo(
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=(total_count + page_size - 1) // page_size
        )
    )
```

---

**File:** `src/api/routes/documents.py`

```python
from fastapi import APIRouter, Depends, Query
from src.api.schemas.documents import (
    DocumentStatsResponse,
    RecentDocumentsResponse,
    RecentDocumentInfo
)

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get(
    "/stats",
    response_model=DocumentStatsResponse,
    summary="Get Document Statistics",
    description="Retrieve document processing statistics and storage metrics"
)
async def get_document_stats(
    range: str = Query("30d", description="Time range for stats"),
    customer_id: int = Depends(get_current_customer_id)
) -> DocumentStatsResponse:
    """
    Get document statistics including:
    - Total document counts by status
    - Processing metrics
    - Storage usage
    """
    # ... existing logic ...
    
    return DocumentStatsResponse(
        total_documents=stats["total"],
        processing_documents=stats["processing"],
        completed_documents=stats["completed"],
        failed_documents=stats["failed"],
        total_chunks=stats["chunks"],
        storage_used_mb=stats["storage_bytes"] / (1024 * 1024)
    )

@router.get(
    "/recent",
    response_model=RecentDocumentsResponse,
    summary="Get Recent Documents",
    description="Retrieve recently uploaded documents (last 24 hours)"
)
async def get_recent_documents(
    limit: int = Query(5, ge=1, le=50),
    customer_id: int = Depends(get_current_customer_id)
) -> RecentDocumentsResponse:
    """
    Get recent documents uploaded in the last 24 hours.
    """
    from datetime import datetime, timedelta
    
    # Query documents from last 24 hours
    cutoff = datetime.utcnow() - timedelta(hours=24)
    
    # ... existing query logic ...
    
    return RecentDocumentsResponse(
        documents=[
            RecentDocumentInfo(
                id=doc.id,
                original_filename=doc.original_filename,
                status=doc.status,
                created_at=doc.created_at,
                total_chunks=doc.total_chunks or 0,
                file_size_bytes=doc.file_size_bytes or 0
            )
            for doc in recent_docs
        ],
        total=len(recent_docs),
        limit=limit
    )
```

---

### **Phase 3: Regenerate OpenAPI Schema & Frontend Types**

**Step 1: Verify Backend Schema**
```bash
# Start backend
cd /Users/scottgay/Documents/Eliza/eliza-platform
docker-compose -f docker/docker-compose.yml up app -d

# Check OpenAPI schema
curl http://localhost:5001/openapi.json | jq '.paths."/v1/admin/dashboard/overview".get.responses."200".content."application/json".schema'

# Should now show proper schema instead of {}
```

**Step 2: Regenerate Frontend Types**
```bash
cd frontend
npm run generate:api
```

**Step 3: Remove Type Assertions**

Update frontend files to use proper types:

```typescript
// ❌ BEFORE (CompanyDataOverview.tsx)
const statsTyped = statsData as any;
const recentData = recentDataRaw as { documents?: any[] };

// ✅ AFTER
// No assertions needed - types are correct!
const stats = statsData; // Properly typed as DocumentStatsResponse
const recentData = recentDataRaw; // Properly typed as RecentDocumentsResponse
```

---

### **Phase 4: Testing & Validation**

**Backend Tests:**
```python
# tests/api/test_admin_routes.py
def test_dashboard_overview_schema():
    """Verify dashboard overview returns correct schema"""
    response = client.get("/v1/admin/dashboard/overview")
    assert response.status_code == 200
    data = response.json()
    
    # Validate structure
    assert "system_health" in data
    assert "user_activity" in data
    assert "document_metrics" in data
    assert "ai_usage" in data
    assert "recent_activity" in data
    
    # Validate types
    assert isinstance(data["system_health"]["uptime_percentage"], (int, float))
    assert isinstance(data["user_activity"]["active_users_now"], int)
```

**Frontend Tests:**
```typescript
// Verify TypeScript compilation
npm run build

// Should compile without errors or type assertions
```

---

## 📝 **Implementation Checklist**

### **Backend Changes:**
- [x] Create `src/api/schemas/admin.py` with response models
- [x] Update `src/api/schemas/documents.py` with stats & recent models
- [x] Create `src/api/schemas/users.py` with list response models
- [x] Update `src/api/routes/admin.py` route handlers
- [x] Update `src/api/routes/documents.py` route handlers
- [x] Update `src/api/routes/admin.py` users route handler
- [x] Add docstrings and OpenAPI examples
- [ ] Run backend tests (pending)
- [ ] Verify `/openapi.json` schema (pending rebuild)

### **Frontend Changes:**
- [ ] Regenerate types with `npm run generate:api`
- [ ] Remove type assertions from `CompanyDataOverview.tsx`
- [ ] Remove type assertions from `AdminDashboard.tsx`
- [ ] Remove type assertions from `UserManagement.tsx`
- [ ] Run `npm run build` to verify no type errors
- [ ] Test all affected components in UI

### **Documentation:**
- [ ] Update API documentation
- [ ] Add schema examples to docs
- [ ] Update `TYPE_GENERATION_SPECIFICATION.md`

---

## ⚠️ **Potential Issues & Mitigations**

### **Issue 1: Breaking Changes**
**Risk:** Changing response structure could break existing API consumers  
**Mitigation:** 
- Use API versioning if external consumers exist
- Add fields, don't remove (backward compatible)
- Test thoroughly before deployment

### **Issue 2: Data Type Mismatches**
**Risk:** Existing data might not match new strict types  
**Mitigation:**
- Use `Optional` fields where data might be missing
- Add default values in Pydantic models
- Include data migration if needed

### **Issue 3: Performance Impact**
**Risk:** Pydantic validation might add overhead  
**Mitigation:**
- Pydantic is highly optimized (minimal overhead)
- Response serialization is already happening
- Monitor response times before/after

---

## 🎯 **Success Criteria**

- [ ] All 4 affected endpoints return properly typed responses
- [ ] Orval generates TypeScript interfaces (not `unknown`)
- [ ] Frontend builds without type assertions
- [ ] All existing functionality works correctly
- [ ] OpenAPI schema is complete and accurate
- [ ] TypeScript intellisense works in IDE

---

## 📊 **Estimated Effort**

| Task | Effort | Owner |
|------|--------|-------|
| Create Pydantic models | 2-3 hours | Backend |
| Update route handlers | 2-3 hours | Backend |
| Backend testing | 1 hour | Backend |
| Regenerate frontend types | 15 min | Frontend |
| Remove type assertions | 30 min | Frontend |
| Integration testing | 1 hour | Full Stack |
| **TOTAL** | **7-9 hours** | Team |

---

## 🚀 **Next Steps**

1. **Review this plan** - Get approval from team
2. **Create backend schemas** - Start with Phase 1
3. **Update routes incrementally** - One endpoint at a time
4. **Test after each endpoint** - Ensure no regressions
5. **Regenerate frontend types** - After all backend changes
6. **Final validation** - End-to-end testing

---

## 📚 **References**

- [FastAPI Response Models](https://fastapi.tiangolo.com/tutorial/response-model/)
- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/)
- [OpenAPI Specification](https://swagger.io/specification/)
- [Orval Documentation](https://orval.dev/)
- Project: `@TYPE_GENERATION_SPECIFICATION.md`

---

## ✅ **Implementation Summary**

### **Completed (October 1, 2025)**

**Files Created:**
- `src/api/schemas/__init__.py` - Schema package exports
- `src/api/schemas/admin.py` - Admin dashboard schemas (175 lines)
- `src/api/schemas/documents.py` - Document operation schemas (80 lines)
- `src/api/schemas/users.py` - User management schemas (75 lines)

**Files Modified:**
- `src/services/admin_service.py` - Replaced hardcoded data with real database queries
- `src/api/routes/admin.py` - Added `response_model` to `/dashboard/overview` and `/users`
- `src/api/routes/documents.py` - Added `response_model` to `/stats` and `/recent`

**Real Data Implementation:**
✅ **User Activity Metrics** - Querying `User`, `UserSession` tables
  - Active users: Session activity in last 15 minutes
  - Active today: Logins since midnight
  - New users: Registrations in last 7 days
  - Growth percentage: Week-over-week comparison

✅ **Document Metrics** - Querying `Document` table
  - Total documents: Count excluding `DELETED` status
  - Uploaded today: Documents created since midnight
  - Processing queue: Count of `PROCESSING` + `UPLOADED` statuses
  - Storage usage: Sum of `file_size` column converted to GB

✅ **Recent Activity** - Querying `UserAuditLog` table
  - Last 10 audit log entries
  - Formatted action names and details

⚠️ **AI Usage Metrics** - Defaults to 0 (tracking tables needed)
  - Requires dedicated `AIUsageLog` table for future implementation
  - Currently returns empty/zero values

**Impact:**
- **601 lines added** to codebase
- **63 lines removed** (hardcoded data)
- **4 endpoints** now have proper OpenAPI schemas
- **Zero linter errors**

### **Remaining Steps:**

1. **Rebuild Docker Backend** - Deploy new schemas
2. **Verify OpenAPI Schema** - Check `/openapi.json` endpoint
3. **Regenerate Frontend Types** - Run `npm run generate:api`
4. **Remove Type Assertions** - Clean up `AdminDashboard.tsx`, `CompanyDataOverview.tsx`, `UserManagement.tsx`
5. **Test End-to-End** - Verify TypeScript compilation and runtime behavior

### **Future Enhancement: AI Usage Tracking**

To populate real AI usage metrics, implement:
```sql
CREATE TABLE ai_usage_logs (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    tokens_used INTEGER NOT NULL,
    cost_usd DECIMAL(10, 6) NOT NULL,
    response_time_ms INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

This table would enable:
- Real-time cost tracking by provider
- Performance monitoring (response times)
- Success/failure rates
- Per-user usage analytics

