# Feature Development Guide

**Version:** 1.0  
**Date:** October 1, 2025  
**Status:** Active Reference Document

---

## 🎯 **Overview**

This guide outlines the **complete architecture and best practices** for building new features in the AI Enablement Platform. Following these patterns ensures:

- ✅ Full type safety across frontend and backend
- ✅ Scalable async processing with Celery
- ✅ Consistent code patterns
- ✅ Auto-generated TypeScript types
- ✅ Production-ready implementations

---

## 📋 **Table of Contents**

1. [Backend Development](#backend-development)
   - [API Endpoints & Routes](#api-endpoints--routes)
   - [Pydantic Response Schemas](#pydantic-response-schemas)
   - [Service Layer](#service-layer)
   - [Database Queries](#database-queries)
   - [Structured Logging](#structured-logging)
2. [Async Processing with Celery](#async-processing-with-celery)
3. [Frontend Development](#frontend-development)
4. [Type Generation & Integration](#type-generation--integration)
5. [Testing Strategy](#testing-strategy)
6. [Deployment Checklist](#deployment-checklist)

---

## 🔧 **Backend Development**

> **Reminder:** Authentication dependencies now return a `CurrentUserContext` DTO. If you need to reference the current user elsewhere, use the DTO fields documented in `CurrentUserContext` instead of raw ORM models.

#### **Current User DTO (`CurrentUserContext`)**

- **Why it exists:** The FastAPI dependencies close their database sessions before returning, so ORM objects become detached. The DTO provides a session-safe snapshot of the authenticated user and prevents `DetachedInstanceError`.
- **Where it lives:** `src/core/auth_context.py` exports `CurrentUserContext`, `CurrentUserSettings`, and `CurrentUserSessionInfo` dataclasses.
- **What you get:**
  - Identity: `user_id`, `email`, `username`, `full_name`
  - Org context: `customer_id`, `department`, `team`
  - Authorization: `roles`, `permissions`, `primary_role`, plus helper methods (`has_permission`, `has_any_permission`, `has_all_permissions`, `has_role`)
  - Account metadata: `is_active`, `is_superuser`, `last_login_at`, `created_at`
  - Preferences: `settings.preferred_language`, `settings.timezone`
  - Sessions: `active_sessions` array with token, device fingerprint, timestamps, and `is_current`
- **How to use it:**
  - Annotate dependencies with `CurrentUserContext`: `current_user: CurrentUserContext = Depends(get_current_user)`
  - Reference DTO fields directly (`current_user.user_id`, `current_user.customer_id`). **Never** call ORM-only properties like `current_user.roles[0].permissions`; use the provided lists or helper methods instead.
  - When you need to persist changes to the user, fetch a fresh ORM instance inside a new service-layer session using `current_user.user_id`.
- **Middleware helpers:** `authorization_middleware.require_permission(...)` and related utilities now return the DTO. Any custom dependencies should follow the same pattern.
- **Logging & context:** Request middleware binds `user_id` using the DTO. If you manually log user context, prefer `current_user.user_id` and `current_user.customer_id`.

### **API Endpoints & Routes**

**File Location:** `src/api/routes/<feature>.py`

#### **✅ Best Practices**

1. **Always specify `response_model`** - This generates proper OpenAPI schemas
2. **Use type hints** - Return type annotation for clarity
3. **Include detailed docstrings** - Appears in OpenAPI docs
4. **Use Query/Path parameters** - With descriptions and validation
5. **Handle errors gracefully** - Consistent HTTPException patterns

#### **Template Pattern**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from src.api.schemas.<feature> import (
    FeatureResponse,
    FeatureListResponse,
    FeatureCreateRequest
)
from src.services.<feature>_service import feature_service
from src.middleware.authorization import require_permission, get_current_user

router = APIRouter(prefix="/v1/<feature>", tags=["<feature>"])

@router.get("/", response_model=FeatureListResponse)
async def list_features(
    search: Optional[str] = Query(None, description="Search term"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user = Depends(require_permission("feature:read"))
) -> FeatureListResponse:
    """
    Get paginated list of features with optional filtering.
    
    Returns a list of features with:
    - Search filtering by name/description
    - Pagination support
    - Metadata about results
    
    Requires: feature:read permission
    """
    try:
        features = await feature_service.list_features(
            search=search,
            limit=limit,
            offset=offset,
            user_id=current_user.id
        )
        
        return FeatureListResponse(
            features=features,
            total=len(features),
            limit=limit,
            offset=offset
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list features: {str(e)}"
        )

@router.post("/", response_model=FeatureResponse, status_code=status.HTTP_201_CREATED)
async def create_feature(
    data: FeatureCreateRequest,
    current_user = Depends(require_permission("feature:create"))
) -> FeatureResponse:
    """
    Create a new feature.
    
    Accepts feature data and returns the created feature with generated ID.
    
    Requires: feature:create permission
    """
    try:
        feature = await feature_service.create_feature(
            data=data,
            created_by=current_user.id
        )
        
        return FeatureResponse.from_orm(feature)
    except ValueError as e:
        # Validation errors (duplicate name, invalid data, etc.)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create feature: {str(e)}"
        )
```

#### **🚨 Common Mistakes to Avoid**

- ❌ Returning raw dicts without `response_model`
- ❌ Missing type hints on function signatures
- ❌ Using `as any` or manual type casting
- ❌ Not handling specific exception types
- ❌ Missing docstrings

---

### **Pydantic Response Schemas**

**File Location:** `src/api/schemas/<feature>.py`

#### **✅ Best Practices**

1. **Create dedicated schema files** - One per feature/domain
2. **Use descriptive class names** - End with `Response`, `Request`, `Info`
3. **Include field descriptions** - For OpenAPI documentation
4. **Add validation constraints** - `ge`, `le`, `min_length`, etc.
5. **Provide examples** - In `Config.json_schema_extra`
6. **Use nested schemas** - For complex objects

#### **Template Pattern**

```python
"""
Pydantic schemas for Feature API endpoints.
Defines request/response models for feature operations.
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class FeatureStatus(str, Enum):
    """Feature status options"""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


# ============================================================================
# Base/Shared Schemas
# ============================================================================

class PaginationInfo(BaseModel):
    """Pagination metadata"""
    total: int = Field(..., ge=0, description="Total number of items")
    limit: int = Field(..., ge=1, description="Items per page")
    offset: int = Field(..., ge=0, description="Starting offset")
    has_more: bool = Field(..., description="More items available")


# ============================================================================
# Request Schemas
# ============================================================================

class FeatureCreateRequest(BaseModel):
    """Feature creation request"""
    name: str = Field(..., min_length=1, max_length=255, description="Feature name")
    description: Optional[str] = Field(None, max_length=1000, description="Feature description")
    status: FeatureStatus = Field(FeatureStatus.DRAFT, description="Initial status")
    tags: List[str] = Field(default_factory=list, description="Feature tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "name": "New Feature",
                "description": "A detailed description of the feature",
                "status": "draft",
                "tags": ["category1", "priority-high"],
                "metadata": {"version": "1.0"}
            }
        }


# ============================================================================
# Response Schemas
# ============================================================================

class FeatureInfo(BaseModel):
    """Basic feature information"""
    id: int = Field(..., description="Feature ID")
    name: str = Field(..., description="Feature name")
    description: Optional[str] = Field(None, description="Feature description")
    status: FeatureStatus = Field(..., description="Feature status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by: int = Field(..., description="Creator user ID")

    class Config:
        from_attributes = True  # Pydantic v2 (was orm_mode in v1)
        json_schema_extra = {
            "example": {
                "id": 123,
                "name": "Example Feature",
                "description": "Feature description",
                "status": "active",
                "created_at": "2025-10-01T10:30:00Z",
                "updated_at": "2025-10-01T12:00:00Z",
                "created_by": 1
            }
        }


class FeatureResponse(BaseModel):
    """Detailed feature response with all data"""
    id: int
    name: str
    description: Optional[str]
    status: FeatureStatus
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: int
    # Add any related data
    related_items_count: int = Field(default=0, description="Count of related items")

    class Config:
        from_attributes = True


class FeatureListResponse(BaseModel):
    """Paginated feature list response"""
    features: List[FeatureInfo] = Field(default_factory=list, description="List of features")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "features": [
                    {
                        "id": 123,
                        "name": "Feature 1",
                        "status": "active",
                        "created_at": "2025-10-01T10:30:00Z"
                    }
                ],
                "pagination": {
                    "total": 50,
                    "limit": 20,
                    "offset": 0,
                    "has_more": True
                }
            }
        }
```

#### **🔑 Key Points**

- **Use `Field(...)`** for required fields with descriptions
- **Use `Field(default=X)`** for optional fields with defaults
- **Add validators** for complex validation logic
- **Nest schemas** for complex structures (don't use raw dicts)
- **Export in `__init__.py`** for clean imports

---

### **Service Layer**

**File Location:** `src/services/<feature>_service.py`

#### **✅ Best Practices**

1. **Extend `BaseService`** - For database session management
2. **Use async methods** - For database queries and I/O
3. **Separate concerns** - Keep business logic out of routes
4. **Return ORM models** - Let routes handle response serialization
5. **Handle errors at service level** - Raise specific exceptions

#### **Template Pattern**

```python
"""
Feature Service - Business logic for feature management
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.base_service import BaseService
from src.models.feature import Feature, FeatureStatus
from src.core.logging import get_logger

logger = get_logger(__name__)


class FeatureService(BaseService):
    """Service for feature management operations"""

    async def list_features(
        self,
        search: Optional[str] = None,
        status: Optional[FeatureStatus] = None,
        limit: int = 20,
        offset: int = 0,
        user_id: Optional[int] = None
    ) -> List[Feature]:
        """
        Get paginated list of features with optional filtering.
        
        Args:
            search: Search term for name/description
            status: Filter by status
            limit: Maximum results to return
            offset: Starting offset for pagination
            user_id: Filter by creator (optional)
            
        Returns:
            List of Feature models
        """
        from src.models.database import get_async_session_factory
        AsyncSessionLocal = get_async_session_factory()
        
        async with AsyncSessionLocal() as session:
            # Build query
            query = select(Feature).order_by(desc(Feature.created_at))
            
            # Apply filters
            conditions = []
            
            if search:
                search_term = f"%{search}%"
                conditions.append(
                    or_(
                        Feature.name.ilike(search_term),
                        Feature.description.ilike(search_term)
                    )
                )
            
            if status:
                conditions.append(Feature.status == status)
            
            if user_id:
                conditions.append(Feature.created_by == user_id)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            # Execute query
            result = await session.execute(query)
            features = result.scalars().all()
            
            return list(features)

    async def get_feature_by_id(self, feature_id: int) -> Optional[Feature]:
        """
        Get feature by ID.
        
        Args:
            feature_id: Feature ID
            
        Returns:
            Feature model or None if not found
        """
        from src.models.database import get_async_session_factory
        AsyncSessionLocal = get_async_session_factory()
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Feature).where(Feature.id == feature_id)
            )
            return result.scalar_one_or_none()

    async def create_feature(
        self,
        name: str,
        description: Optional[str],
        status: FeatureStatus,
        created_by: int,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Feature:
        """
        Create a new feature.
        
        Args:
            name: Feature name
            description: Feature description
            status: Initial status
            created_by: Creator user ID
            tags: Optional tags list
            metadata: Optional metadata dict
            
        Returns:
            Created Feature model
            
        Raises:
            ValueError: If validation fails (e.g., duplicate name)
        """
        from src.models.database import get_async_session_factory
        AsyncSessionLocal = get_async_session_factory()
        
        async with AsyncSessionLocal() as session:
            # Check for duplicate name
            existing = await session.execute(
                select(Feature).where(Feature.name == name)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Feature with name '{name}' already exists")
            
            # Create feature
            feature = Feature(
                name=name,
                description=description,
                status=status,
                created_by=created_by,
                tags=tags or [],
                metadata=metadata or {},
                created_at=datetime.utcnow()
            )
            
            session.add(feature)
            await session.commit()
            await session.refresh(feature)
            
            logger.info(
                f"Feature created successfully",
                extra={
                    "feature_id": feature.id,
                    "name": name,
                    "created_by": created_by
                }
            )
            
            return feature

    async def update_feature(
        self,
        feature_id: int,
        **updates
    ) -> Feature:
        """
        Update an existing feature.
        
        Args:
            feature_id: Feature ID to update
            **updates: Fields to update
            
        Returns:
            Updated Feature model
            
        Raises:
            ValueError: If feature not found
        """
        from src.models.database import get_async_session_factory
        AsyncSessionLocal = get_async_session_factory()
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Feature).where(Feature.id == feature_id)
            )
            feature = result.scalar_one_or_none()
            
            if not feature:
                raise ValueError(f"Feature with ID {feature_id} not found")
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(feature, key):
                    setattr(feature, key, value)
            
            feature.updated_at = datetime.utcnow()
            
            await session.commit()
            await session.refresh(feature)
            
            return feature

    async def delete_feature(self, feature_id: int) -> bool:
        """
        Soft delete a feature (set status to ARCHIVED).
        
        Args:
            feature_id: Feature ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If feature not found
        """
        from src.models.database import get_async_session_factory
        AsyncSessionLocal = get_async_session_factory()
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Feature).where(Feature.id == feature_id)
            )
            feature = result.scalar_one_or_none()
            
            if not feature:
                raise ValueError(f"Feature with ID {feature_id} not found")
            
            feature.status = FeatureStatus.ARCHIVED
            feature.updated_at = datetime.utcnow()
            
            await session.commit()
            
            logger.info(
                f"Feature archived",
                extra={"feature_id": feature_id}
            )
            
            return True


# Singleton instance
feature_service = FeatureService()
```

#### **🔑 Key Points**

- **Use `get_async_session_factory()`** for async database access
- **Always commit and refresh** after creates/updates
- **Raise ValueError** for validation errors (caught by routes as 422)
- **Use structured logging** with `extra` context
- **Return ORM models** not Pydantic models

---

### **Database Queries**

#### **✅ Best Practices**

1. **Use SQLAlchemy select()** - Modern query syntax
2. **Filter efficiently** - Use indexes, avoid N+1 queries
3. **Paginate results** - Always use `limit()` and `offset()`
4. **Use aggregations** - `func.count()`, `func.sum()` for stats
5. **Handle timezones** - Use `datetime.utcnow()` consistently

#### **Query Patterns**

```python
# Simple select
result = await session.execute(
    select(Model).where(Model.id == id)
)
item = result.scalar_one_or_none()

# With filters and pagination
query = select(Model).where(
    and_(
        Model.status == 'active',
        Model.created_at >= cutoff_date
    )
).order_by(desc(Model.created_at)).limit(20).offset(0)

result = await session.execute(query)
items = result.scalars().all()

# Aggregations
result = await session.execute(
    select(func.count(Model.id)).where(Model.status == 'active')
)
count = result.scalar() or 0

# Join queries
result = await session.execute(
    select(Model, RelatedModel)
    .join(RelatedModel, Model.related_id == RelatedModel.id)
    .where(Model.status == 'active')
)
pairs = result.all()

# Group by with aggregations
result = await session.execute(
    select(
        Model.category,
        func.count(Model.id).label('count')
    )
    .group_by(Model.category)
    .order_by(desc('count'))
)
stats = result.all()
```

---

### **Structured Logging**

The platform uses a comprehensive structured logging system with context propagation, ELK stack integration, and operation tracking.

#### **✅ Best Practices**

1. **Always use `get_logger`** - Never use `logging.getLogger()` directly
2. **Include context** - Use `bind_context()` for request/task tracking
3. **Track operations** - Use `start_operation()` and `end_operation()` for timing
4. **Add categories** - Categorize logs for filtering (`LogCategory`)
5. **Include metadata** - Add structured data for searchability
6. **User messages** - Provide user-friendly messages for UI display

#### **Getting a Logger**

```python
from src.core.logging import get_logger, LogCategory

# Basic logger
logger = get_logger(__name__)

# Logger with component name
logger = get_logger(__name__, component="documents.processor")

# Logger with default context
logger = get_logger(__name__, component="feature", default_key="value")
```

#### **Basic Logging**

```python
# Simple info log
logger.info("Processing started")

# With category
logger.info(
    "Processing document",
    category=LogCategory.DATA_PROCESSING
)

# With metadata
logger.info(
    "User action performed",
    category=LogCategory.USER_ACTION,
    metadata={
        'action': 'document_upload',
        'document_count': 5
    }
)

# Error with exception
try:
    # ... code ...
except Exception as e:
    logger.error(
        "Failed to process document",
        exception=e,
        category=LogCategory.DATA_PROCESSING,
        metadata={'document_id': doc_id}
    )
```

#### **Context Propagation**

Context variables (request_id, user_id, task_id, etc.) are automatically included in all logs:

```python
from src.core.logging import bind_context, reset_context

# In API routes (automatic via middleware)
# Request ID, user ID automatically bound

# In Celery tasks
def process_task(task_id: str, document_id: int):
    # Bind task context
    context_tokens = bind_context(
        task_id=task_id,
        document_id=str(document_id),
        customer_id="customer-123"
    )
    
    try:
        # All logs in this scope include context
        logger.info("Processing document")  # Includes task_id, document_id, customer_id
        
        # ... do work ...
        
    finally:
        # Always reset context
        reset_context(context_tokens)
```

#### **Operation Tracking**

Track long-running operations with automatic timing:

```python
# Start operation
op_id = logger.start_operation(
    "document_processing",
    category=LogCategory.DATA_PROCESSING,
    user_message="Processing document...",
    metadata={'document_id': doc_id, 'pages': 10}
)

try:
    # ... do work ...
    
    # End operation (success)
    logger.end_operation(
        op_id,
        success=True,
        items_processed=10,
        user_message="Document processed successfully"
    )
except Exception as e:
    # End operation (failure)
    logger.end_operation(
        op_id,
        success=False,
        error=str(e),
        user_message=f"Processing failed: {str(e)}"
    )
    raise
```

#### **Log Categories**

Use categories for filtering and routing logs:

```python
from src.core.logging import LogCategory

# Available categories:
LogCategory.SYSTEM           # System events (startup, shutdown)
LogCategory.SECURITY         # Authentication, authorization
LogCategory.PERFORMANCE      # Slow queries, timing
LogCategory.BUSINESS         # Business metrics, KPIs
LogCategory.USER_ACTION      # User interactions
LogCategory.DATA_PROCESSING  # Document processing, ETL
LogCategory.API              # HTTP requests/responses
LogCategory.INTEGRATION      # External API calls
LogCategory.QA_RAG           # Q&A and RAG operations
LogCategory.CHUNKING         # Document chunking
LogCategory.INGESTION        # Data ingestion
LogCategory.ANALYSIS         # Analytics and reporting
```

#### **Complete Example**

```python
"""
Document processing service with structured logging
"""

from typing import Optional
from src.core.logging import get_logger, bind_context, reset_context, LogCategory
from src.models.document import Document

logger = get_logger(__name__, component="documents.service")


async def process_document(document_id: int, user_id: Optional[str] = None) -> Document:
    """Process a document with full logging"""
    
    # Bind context
    context_tokens = bind_context(
        document_id=str(document_id),
        user_id=user_id
    )
    
    try:
        # Start operation tracking
        op_id = logger.start_operation(
            "process_document",
            category=LogCategory.DATA_PROCESSING,
            user_message=f"Processing document {document_id}...",
            metadata={'document_id': document_id}
        )
        
        # Log steps with context
        logger.info(
            "Loading document",
            category=LogCategory.DATA_PROCESSING,
            operation="load_document",
            metadata={'document_id': document_id}
        )
        
        document = await load_document(document_id)
        
        logger.info(
            "Extracting text",
            category=LogCategory.DATA_PROCESSING,
            operation="extract_text",
            metadata={
                'document_id': document_id,
                'pages': document.page_count
            }
        )
        
        text = await extract_text(document)
        
        logger.info(
            "Generating embeddings",
            category=LogCategory.DATA_PROCESSING,
            operation="generate_embeddings",
            metadata={
                'document_id': document_id,
                'text_length': len(text)
            }
        )
        
        embeddings = await generate_embeddings(text)
        
        # Log business metrics
        logger.log_business_metric(
            "documents_processed",
            value=1,
            unit="documents"
        )
        
        # End operation successfully
        logger.end_operation(
            op_id,
            success=True,
            items_processed=1,
            user_message=f"Document {document_id} processed successfully"
        )
        
        return document
        
    except Exception as e:
        # Log error
        logger.error(
            f"Document processing failed",
            exception=e,
            category=LogCategory.DATA_PROCESSING,
            operation="process_document",
            metadata={'document_id': document_id},
            user_message=f"Failed to process document: {str(e)}"
        )
        
        # End operation with failure
        if 'op_id' in locals():
            logger.end_operation(
                op_id,
                success=False,
                error=str(e)
            )
        
        raise
        
    finally:
        # Always reset context
        reset_context(context_tokens)
```

#### **ELK Stack Integration**

Logs are automatically sent to Logstash when enabled in configuration:

```python
# Environment variables
LOGSTASH_ENABLED=true
LOGSTASH_HOST=logstash
LOGSTASH_PORT=5000
LOG_JSON_FORMAT=true
```

Logs are structured JSON with fields:
- `timestamp` - ISO 8601 timestamp
- `level` - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `category` - Log category
- `message` - Human-readable message
- `component` - Component name
- `operation` - Operation name
- `context` - Request/task context (request_id, user_id, etc.)
- `metadata` - Additional structured data
- `duration_ms` - Operation duration
- `error_type` - Exception type
- `stack_trace` - Full stack trace (errors only)

#### **Searching Logs**

In Kibana/Elasticsearch:

```json
// Find all logs for a specific request
{
  "query": {
    "term": { "context.request_id": "abc123" }
  }
}

// Find slow operations
{
  "query": {
    "range": { "duration_ms": { "gte": 1000 } }
  }
}

// Find errors for a specific document
{
  "query": {
    "bool": {
      "must": [
        { "term": { "level": "ERROR" } },
        { "term": { "context.document_id": "42" } }
      ]
    }
  }
}

// Find all operations in a category
{
  "query": {
    "term": { "category": "data_processing" }
  }
}
```

#### **Request Tracing**

Every HTTP request gets a unique `request_id` that propagates through:
1. **API layer** - Logged by `RequestLoggingMiddleware`
2. **Service layer** - Included automatically in all logs
3. **Celery tasks** - If triggered by API, request_id propagates
4. **Database queries** - Context available for slow query logging

To trace a complete request:
1. Get `request_id` from response header `X-Request-ID`
2. Search logs: `context.request_id: "abc123"`
3. See complete timeline with all operations

#### **Performance Monitoring**

The platform includes automatic performance monitoring:

```python
# Slow request detection (> 1000ms)
# Automatically logged by PerformanceLoggingMiddleware

# Operation timing
op_id = logger.start_operation("expensive_operation")
# ... work ...
logger.end_operation(op_id, success=True)  # Logs duration_ms

# Custom performance metrics
logger.info(
    "Query executed",
    category=LogCategory.PERFORMANCE,
    duration_ms=query_time,
    metadata={
        'query_type': 'complex_join',
        'rows_returned': 1000
    }
)
```

#### **🔑 Key Points**

- ✅ **Always use `get_logger`** not `logging.getLogger()`
- ✅ **Bind context** in Celery tasks and long-running operations
- ✅ **Use categories** for better log organization
- ✅ **Track operations** for automatic timing
- ✅ **Include metadata** for searchability
- ✅ **Reset context** in `finally` blocks
- ❌ **Don't log sensitive data** (passwords, tokens, PII)
- ❌ **Don't use print()** for logging
- ❌ **Don't log in tight loops** (aggregate instead)

---

## ⚙️ **Async Processing with Celery**

### **When to Use Celery**

Use Celery tasks for operations that:
- Take > 5 seconds to complete
- Involve file processing (documents, images, videos)
- Make external API calls (AI models, third-party services)
- Require retry logic with backoff
- Should not block HTTP responses

### **Task Implementation Pattern**

**File Location:** `src/tasks/<feature>_tasks.py`

```python
"""
Celery tasks for feature processing
"""

from celery import Task
from celery.utils.log import get_task_logger
from typing import Optional
import time

from src.celery_app import celery_app
from src.services.<feature>_service import feature_service

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    name='tasks.process_feature',
    max_retries=3,
    default_retry_delay=60,  # 1 minute
    autoretry_for=(Exception,),
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=600,  # Max 10 minutes
    retry_jitter=True  # Add randomness to prevent thundering herd
)
def process_feature_task(self: Task, feature_id: int, options: Optional[dict] = None) -> dict:
    """
    Process feature asynchronously with automatic retries.
    
    Args:
        feature_id: Feature ID to process
        options: Optional processing options
        
    Returns:
        dict with processing results
        
    Raises:
        Exception: On unrecoverable errors (triggers retry)
    """
    start_time = time.time()
    
    logger.info(
        f"[TASK-START] Processing feature",
        extra={
            "task_id": self.request.id,
            "feature_id": feature_id,
            "retry_count": self.request.retries
        }
    )
    
    try:
        # Idempotency check
        from src.models.database import SessionLocal
        with SessionLocal() as db:
            from src.models.feature import Feature
            feature = db.query(Feature).filter(Feature.id == feature_id).first()
            
            if not feature:
                logger.error(f"Feature {feature_id} not found")
                return {"status": "error", "message": "Feature not found"}
            
            if feature.processing_status == "completed":
                logger.info(f"Feature {feature_id} already processed, skipping")
                return {"status": "skipped", "message": "Already completed"}
            
            # Mark as processing
            feature.processing_status = "processing"
            feature.processing_started_at = time.time()
            db.commit()
        
        # === MAIN PROCESSING LOGIC ===
        
        # Step 1: Load data
        logger.info(f"[FEATURE-{feature_id}] Loading data...")
        data = _load_feature_data(feature_id)
        
        # Step 2: Process data
        logger.info(f"[FEATURE-{feature_id}] Processing data...")
        results = _process_data(data, options)
        
        # Step 3: Save results
        logger.info(f"[FEATURE-{feature_id}] Saving results...")
        _save_results(feature_id, results)
        
        # === UPDATE STATUS ===
        
        with SessionLocal() as db:
            feature = db.query(Feature).filter(Feature.id == feature_id).first()
            feature.processing_status = "completed"
            feature.processing_completed_at = time.time()
            feature.processing_duration = time.time() - start_time
            db.commit()
        
        duration = time.time() - start_time
        logger.info(
            f"[TASK-COMPLETE] Feature processed successfully",
            extra={
                "task_id": self.request.id,
                "feature_id": feature_id,
                "duration_seconds": round(duration, 2)
            }
        )
        
        return {
            "status": "success",
            "feature_id": feature_id,
            "duration": duration,
            "results": results
        }
        
    except Exception as e:
        # Update failure status
        try:
            with SessionLocal() as db:
                feature = db.query(Feature).filter(Feature.id == feature_id).first()
                if feature:
                    feature.processing_status = "failed"
                    feature.processing_error = str(e)
                    db.commit()
        except:
            pass  # Don't fail the retry because of status update
        
        logger.error(
            f"[TASK-FAILED] Feature processing failed",
            extra={
                "task_id": self.request.id,
                "feature_id": feature_id,
                "error": str(e),
                "retry_count": self.request.retries
            },
            exc_info=True
        )
        
        # Re-raise to trigger Celery retry
        raise


def _load_feature_data(feature_id: int) -> dict:
    """Helper: Load feature data"""
    # Implementation
    pass


def _process_data(data: dict, options: Optional[dict]) -> dict:
    """Helper: Process the data"""
    # Implementation
    pass


def _save_results(feature_id: int, results: dict) -> None:
    """Helper: Save processing results"""
    # Implementation
    pass
```

### **Triggering Tasks from API**

```python
# In your API route
from src.tasks.feature_tasks import process_feature_task

@router.post("/{feature_id}/process")
async def trigger_processing(
    feature_id: int,
    options: Optional[ProcessingOptions] = None,
    current_user = Depends(require_permission("feature:process"))
):
    """
    Trigger async processing for a feature.
    
    Returns immediately with task ID for status tracking.
    """
    # Enqueue task
    task = process_feature_task.delay(
        feature_id=feature_id,
        options=options.dict() if options else None
    )
    
    return {
        "message": "Processing started",
        "task_id": task.id,
        "feature_id": feature_id,
        "status_url": f"/v1/tasks/{task.id}/status"
    }
```

### **🔑 Celery Best Practices**

- ✅ **Make tasks idempotent** - Check if already processed
- ✅ **Use synchronous code** - No async/await in Celery tasks
- ✅ **Update status regularly** - Set processing, completed, failed
- ✅ **Log with context** - Include task_id, retry_count, duration
- ✅ **Handle errors gracefully** - Update DB even on failure
- ✅ **Use retry logic** - With exponential backoff and jitter
- ✅ **Monitor with Flower** - Track task execution in real-time

---

## 🎨 **Frontend Development**

### **Using Generated Hooks**

**No more manual API calls!** Orval generates React Query hooks automatically.

#### **✅ Best Practices**

1. **Import from generated files** - Never write manual `fetch` or `axios`
2. **Use `queryKeys` factory** - Centralized key management
3. **No type assertions** - Trust the generated types
4. **Handle loading/error states** - Consistent UX patterns
5. **Invalidate queries** - After mutations for fresh data

#### **Template Pattern**

```typescript
// src/pages/<feature>/FeatureList.tsx

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useListFeaturesV1FeaturesGet,
  useCreateFeatureV1FeaturesPost,
  useDeleteFeatureV1FeaturesFeatureIdDelete
} from '../../generated/features/features';
import { FeatureInfo, FeatureCreateRequest } from '../../generated/models';
import { queryKeys } from '../../lib/query-keys';
import { useToasts } from '../../stores/useToasts';

export default function FeatureList() {
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 20;
  
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();

  // ===== FETCH DATA =====
  // Uses generated hook - fully typed!
  const { data, isLoading, error } = useListFeaturesV1FeaturesGet(
    {
      search: searchQuery || undefined,
      limit: pageSize,
      offset: page * pageSize
    },
    {
      query: {
        queryKey: queryKeys.features.list({ search: searchQuery, page }),
        staleTime: 30000, // 30 seconds
      }
    }
  );

  // ===== CREATE MUTATION =====
  const { mutate: createFeature, isPending: isCreating } = useCreateFeatureV1FeaturesPost({
    mutation: {
      onSuccess: (newFeature) => {
        // Invalidate to refetch
        queryClient.invalidateQueries({ queryKey: queryKeys.features.all });
        
        addToast({
          message: `Feature "${newFeature.name}" created successfully`,
          kind: 'success'
        });
      },
      onError: (error: any) => {
        addToast({
          message: error.response?.data?.detail || 'Failed to create feature',
          kind: 'error'
        });
      }
    }
  });

  // ===== DELETE MUTATION =====
  const { mutate: deleteFeature } = useDeleteFeatureV1FeaturesFeatureIdDelete({
    mutation: {
      onMutate: async (variables) => {
        // Optimistic update
        await queryClient.cancelQueries({ queryKey: queryKeys.features.all });
        
        const previousData = queryClient.getQueryData(
          queryKeys.features.list({ search: searchQuery, page })
        );
        
        // Update cache optimistically
        queryClient.setQueryData(
          queryKeys.features.list({ search: searchQuery, page }),
          (old: any) => ({
            ...old,
            features: old.features.filter((f: FeatureInfo) => f.id !== variables.featureId)
          })
        );
        
        return { previousData };
      },
      onError: (error, variables, context) => {
        // Rollback on error
        if (context?.previousData) {
          queryClient.setQueryData(
            queryKeys.features.list({ search: searchQuery, page }),
            context.previousData
          );
        }
        
        addToast({
          message: 'Failed to delete feature',
          kind: 'error'
        });
      },
      onSuccess: () => {
        addToast({
          message: 'Feature deleted successfully',
          kind: 'success'
        });
      },
      onSettled: () => {
        // Refetch to ensure consistency
        queryClient.invalidateQueries({ queryKey: queryKeys.features.all });
      }
    }
  });

  // ===== EVENT HANDLERS =====
  const handleCreate = (data: FeatureCreateRequest) => {
    createFeature({ data });
  };

  const handleDelete = (featureId: number) => {
    if (confirm('Are you sure you want to delete this feature?')) {
      deleteFeature({ featureId });
    }
  };

  // ===== RENDER =====
  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage error={error} />;
  }

  const features = data?.features || [];
  const totalCount = data?.pagination?.total || 0;

  return (
    <div className="space-y-6">
      {/* Search */}
      <input
        type="text"
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        placeholder="Search features..."
        className="input"
      />

      {/* Feature List */}
      <div className="grid gap-4">
        {features.map((feature) => (
          <FeatureCard
            key={feature.id}
            feature={feature}
            onDelete={() => handleDelete(feature.id)}
          />
        ))}
      </div>

      {/* Pagination */}
      <Pagination
        currentPage={page}
        totalItems={totalCount}
        pageSize={pageSize}
        onPageChange={setPage}
      />
    </div>
  );
}
```

### **🔑 Frontend Best Practices**

- ✅ **Never use `as any`** - Generated types are correct
- ✅ **Always invalidate after mutations** - Keep data fresh
- ✅ **Use optimistic updates** - For better UX
- ✅ **Handle all states** - Loading, error, empty, success
- ✅ **Use queryKeys factory** - Centralized key management
- ❌ **Don't call APIs directly** - Always use generated hooks
- ❌ **Don't transform data** - Let backend return correct shape

---

## 🔄 **Type Generation & Integration**

### **Complete Workflow**

```bash
# 1. Backend: Create/Update Pydantic schemas
# src/api/schemas/feature.py

# 2. Backend: Add response_model to routes
# src/api/routes/feature.py

# 3. Backend: Rebuild Docker container
docker-compose -f docker/docker-compose.yml build app
docker-compose -f docker/docker-compose.yml up -d app

# 4. Verify OpenAPI schema
curl http://localhost:5001/openapi.json | jq '.paths."/v1/features"'

# 5. Frontend: Regenerate types
cd frontend
npm run generate:api

# 6. Frontend: Update components
# Use generated hooks, remove type assertions

# 7. Frontend: Test TypeScript compilation
npm run build

# 8. Commit changes
git add -A
git commit -m "feat(feature): implement feature with full type safety"
```

### **Query Keys Factory Pattern**

**File:** `frontend/src/lib/query-keys.ts`

```typescript
// Add new feature keys
const featuresBase = ['features'] as const;

export const queryKeys = {
  // ... existing keys ...
  
  features: {
    all: featuresBase,
    lists: () => [...featuresBase, 'list'] as const,
    list: (filters: {
      search?: string;
      status?: string;
      page?: number;
    }) => [...featuresBase, 'list', filters] as const,
    details: () => [...featuresBase, 'detail'] as const,
    detail: (id: number) => [...featuresBase, 'detail', id] as const,
  },
} as const;
```

---

## 🧪 **Testing Strategy**

### **Backend Tests**

```python
# tests/api/test_feature_routes.py

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_create_feature():
    """Test feature creation endpoint"""
    response = client.post(
        "/v1/features",
        json={
            "name": "Test Feature",
            "description": "Test description",
            "status": "draft"
        },
        headers={"Authorization": f"Bearer {get_test_token()}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Feature"
    assert "id" in data
    assert "created_at" in data

def test_list_features():
    """Test feature listing with pagination"""
    response = client.get(
        "/v1/features?limit=10&offset=0",
        headers={"Authorization": f"Bearer {get_test_token()}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    assert "pagination" in data
    assert data["pagination"]["limit"] == 10

def test_create_feature_duplicate_name():
    """Test duplicate name validation"""
    # Create first feature
    client.post("/v1/features", json={"name": "Unique"})
    
    # Try to create duplicate
    response = client.post("/v1/features", json={"name": "Unique"})
    
    assert response.status_code == 422
    assert "already exists" in response.json()["detail"]
```

### **Frontend Tests**

```typescript
// src/pages/__tests__/FeatureList.test.tsx

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import FeatureList from '../FeatureList';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

describe('FeatureList', () => {
  it('renders feature list', async () => {
    const queryClient = createTestQueryClient();
    
    render(
      <QueryClientProvider client={queryClient}>
        <FeatureList />
      </QueryClientProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByText('Features')).toBeInTheDocument();
    });
  });
  
  it('creates new feature', async () => {
    const user = userEvent.setup();
    const queryClient = createTestQueryClient();
    
    render(
      <QueryClientProvider client={queryClient}>
        <FeatureList />
      </QueryClientProvider>
    );
    
    const createButton = screen.getByText('Create Feature');
    await user.click(createButton);
    
    // Fill form and submit
    const nameInput = screen.getByLabelText('Name');
    await user.type(nameInput, 'New Feature');
    
    const submitButton = screen.getByText('Submit');
    await user.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText('New Feature')).toBeInTheDocument();
    });
  });
});
```

---

## ✅ **Deployment Checklist**

### **Before Pushing Code**

- [ ] Backend: All routes have `response_model` specified
- [ ] Backend: Pydantic schemas created with examples
- [ ] Backend: Service layer methods use async/await
- [ ] Backend: Database queries use proper indexes
- [ ] Backend: Celery tasks are idempotent
- [ ] Backend: Error handling returns appropriate HTTP codes
- [ ] Backend: Structured logging with `get_logger()` and context
- [ ] Backend: Operations tracked with `start_operation()`/`end_operation()`
- [ ] Backend: Log categories assigned appropriately
- [ ] Backend: No sensitive data in logs (passwords, tokens, PII)

- [ ] Frontend: Types regenerated with `npm run generate:api`
- [ ] Frontend: No type assertions (`as any`, `as unknown`)
- [ ] Frontend: Query keys added to factory
- [ ] Frontend: Loading and error states handled
- [ ] Frontend: Mutations invalidate relevant queries
- [ ] Frontend: TypeScript compilation passes (`npm run build`)

- [ ] Tests: Backend unit tests written and passing
- [ ] Tests: Frontend component tests written
- [ ] Tests: Integration tests cover main flows

### **Deployment Steps**

```bash
# 1. Run linter
cd backend && pylint src/
cd frontend && npm run lint

# 2. Run tests
cd backend && pytest
cd frontend && npm test

# 3. Build containers
docker-compose -f docker/docker-compose.yml build

# 4. Deploy
docker-compose -f docker/docker-compose.yml up -d

# 5. Verify health
curl http://localhost:5001/health
curl http://localhost:3000

# 6. Monitor logs
docker-compose -f docker/docker-compose.yml logs -f app
docker-compose -f docker/docker-compose.yml logs -f celery-worker

# 7. Check Flower dashboard
open http://localhost:5555
```

---

## 📚 **Reference Architecture**

### **Project Structure**

```
eliza-platform/
├── src/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── <feature>.py      # API endpoints
│   │   │   └── ...
│   │   └── schemas/
│   │       ├── <feature>.py      # Pydantic models
│   │       └── ...
│   ├── services/
│   │   ├── <feature>_service.py  # Business logic
│   │   └── ...
│   ├── tasks/
│   │   ├── <feature>_tasks.py    # Celery tasks
│   │   └── ...
│   ├── models/
│   │   ├── <feature>.py          # SQLAlchemy models
│   │   └── ...
│   └── celery_app.py             # Celery configuration
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   └── <feature>/
│   │   │       └── *.tsx         # Feature pages
│   │   ├── components/
│   │   │   └── <feature>/
│   │   │       └── *.tsx         # Reusable components
│   │   ├── generated/            # AUTO-GENERATED by Orval
│   │   │   ├── <tag>/
│   │   │   │   └── <tag>.ts     # Generated hooks
│   │   │   └── models/
│   │   │       └── *.ts          # Generated types
│   │   └── lib/
│   │       ├── query-keys.ts     # Query key factory
│   │       └── react-query.ts    # React Query config
│   └── orval.config.ts           # Orval configuration
└── design_docs/
    └── <FEATURE>_SPECIFICATION.md
```

---

## 🎓 **Learning Resources**

- **FastAPI:** https://fastapi.tiangolo.com/
- **Pydantic:** https://docs.pydantic.dev/
- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **Celery:** https://docs.celeryq.dev/
- **React Query:** https://tanstack.com/query/latest
- **Orval:** https://orval.dev/

---

## 💡 **Tips & Tricks**

### **Common Patterns**

**1. Conditional Fields in Response:**
```python
class FeatureResponse(BaseModel):
    id: int
    name: str
    # Include detailed info only if requested
    details: Optional[DetailedInfo] = None
```

**2. Enum Validation:**
```python
from enum import Enum

class FeatureType(str, Enum):
    TYPE_A = "type_a"
    TYPE_B = "type_b"

class FeatureRequest(BaseModel):
    type: FeatureType  # Only accepts enum values
```

**3. Nested Object Validation:**
```python
class Address(BaseModel):
    street: str
    city: str
    zip_code: str

class Feature(BaseModel):
    name: str
    address: Address  # Validated recursively
```

**4. Custom Validators:**
```python
from pydantic import validator

class FeatureRequest(BaseModel):
    email: str
    
    @validator('email')
    def validate_email_domain(cls, v):
        if not v.endswith('@company.com'):
            raise ValueError('Must be company email')
        return v
```

### **Debugging Tips**

**1. Check OpenAPI Schema:**
```bash
# View generated schema for specific endpoint
curl http://localhost:5001/openapi.json | \
  jq '.paths."/v1/features".post'
```

**2. Test Celery Task Directly:**
```python
# In Django/Flask shell or Python REPL
from src.tasks.feature_tasks import process_feature_task
result = process_feature_task.apply(args=[feature_id])
print(result.get())  # Wait for result
```

**3. Monitor Celery:**
```bash
# Check task status
docker-compose logs -f celery-worker

# Open Flower dashboard
open http://localhost:5555
```

**4. Frontend Type Errors:**
```bash
# Check generated types
cat frontend/src/generated/models/<model>.ts

# Regenerate if outdated
cd frontend && npm run generate:api
```

---

## 🎯 **Quick Start Checklist**

When starting a new feature:

1. [ ] Create feature specification document
2. [ ] Design database models (if needed)
3. [ ] Create Pydantic schemas (`src/api/schemas/<feature>.py`)
4. [ ] Implement service layer (`src/services/<feature>_service.py`)
5. [ ] Create API routes (`src/api/routes/<feature>.py`)
6. [ ] Add Celery tasks (if async processing needed)
7. [ ] Rebuild backend Docker container
8. [ ] Verify OpenAPI schema generation
9. [ ] Regenerate frontend types (`npm run generate:api`)
10. [ ] Add query keys to `query-keys.ts`
11. [ ] Implement frontend components
12. [ ] Write tests (backend & frontend)
13. [ ] Test end-to-end flow
14. [ ] Deploy and monitor

---

## 📞 **Getting Help**

- **Review existing code** - Check `documents.py`, `admin.py` for patterns
- **Check design docs** - `design_docs/` for architectural decisions
- **OpenAPI schema** - `http://localhost:5001/docs` for API docs
- **Flower dashboard** - `http://localhost:5555` for Celery monitoring

---

**Version History:**
- 1.0 (Oct 1, 2025) - Initial guide based on OpenAPI schema implementation
- 1.1 (Oct 1, 2025) - Added comprehensive structured logging section with ELK integration

