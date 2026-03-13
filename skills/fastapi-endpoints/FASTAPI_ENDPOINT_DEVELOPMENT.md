# FastAPI Endpoint Development Guide

> **Purpose:** This skill ensures API endpoints are built correctly the first time, with proper authentication, validation, error handling, and response models.

---

## Quick Reference

```python
# ✅ CORRECT FastAPI Endpoint Pattern
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from src.models import get_db
from src.middleware.authorization import AuthorizationMiddleware
from src.api.schemas.your_feature import (
    YourCreateRequest, YourResponse, YourListResponse
)
from src.services.your_service import YourService
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.API)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/v1/your-feature", tags=["Your Feature"])

@router.post(
    "/",
    response_model=YourResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new resource",
    description="Detailed description of what this endpoint does."
)
async def create_resource(
    request: YourCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("your-feature:write"))
):
    """Create a new resource."""
    logger.info(
        "create_resource_request",
        user_id=current_user.user_id,
        customer_id=current_user.customer_id
    )
    
    try:
        service = YourService(db)
        resource = service.create(
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
            **request.dict()
        )
        return YourResponse.from_orm(resource)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("create_resource_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create resource"
        )
```

---

## Critical Rules

### Rule 1: Never Hardcode Placeholder Values in Responses

**Context:** Returning hardcoded values instead of database fields creates silent data loss. The frontend has no idea the data exists in the database, changes don't appear to "save," and debugging wastes hours.

```python
# ❌ WRONG: Hardcoding placeholder values
@router.get("/{id}")
async def get_resource(id: int, db: Session = Depends(get_db)):
    resource = db.query(Resource).get(id)
    return ResourceResponse(
        id=resource.id,
        name=None,  # "Not stored yet, would need schema update" ← WRONG!
        status=resource.status
    )

# ✅ CORRECT: Return actual database values
@router.get("/{id}")
async def get_resource(id: int, db: Session = Depends(get_db)):
    resource = db.query(Resource).get(id)
    return ResourceResponse(
        id=resource.id,
        name=resource.name,  # Return actual value
        status=resource.status
    )
```

**RED FLAGS to watch for:**
- `name=None` or `name=""` when database field exists
- Comments like "Not stored yet" or "TODO: add this field"
- Response model fields that don't map to database fields
- Using `.get("field")` with default values that hide missing data

### Rule 2: Use Proper HTTP Status Codes

**Context:** Incorrect status codes break client-side error handling and violate REST conventions.

```python
# Status code reference:
# 200 OK - Successful GET, PUT, PATCH
# 201 Created - Successful POST that creates a resource
# 202 Accepted - Request accepted for async processing
# 204 No Content - Successful DELETE
# 400 Bad Request - Invalid input/validation error
# 401 Unauthorized - Missing/invalid authentication
# 403 Forbidden - Authenticated but no permission
# 404 Not Found - Resource doesn't exist
# 409 Conflict - Duplicate/conflict error
# 422 Unprocessable Entity - Validation failed (FastAPI default)
# 500 Internal Server Error - Unexpected server error
# 503 Service Unavailable - Dependency unavailable

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create():
    ...

@router.post("/async", status_code=status.HTTP_202_ACCEPTED)
async def create_async():
    ...

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(id: int):
    ...
```

### Rule 3: Consistent Authorization Pattern

**Context:** Missing or inconsistent auth checks lead to data leaks across tenants and unauthorized access.

```python
from src.middleware.authorization import AuthorizationMiddleware

auth_middleware = AuthorizationMiddleware()

# ❌ WRONG: No authorization
@router.get("/")
async def list_items():
    ...

# ✅ CORRECT: Permission-based (most common)
@router.get("/")
async def list_items(
    current_user = Depends(auth_middleware.require_permission("items:read"))
):
    ...

# ✅ CORRECT: Role-based (for admin endpoints)
@router.delete("/{id}")
async def delete_item(
    id: int,
    current_user = Depends(auth_middleware.require_permission("items:delete"))
):
    # Additional role check for sensitive operations
    if not auth_middleware.has_role(current_user, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    ...

# ✅ CORRECT: Company access check (for multi-tenant data)
@router.get("/{company}/data")
async def get_company_data(
    company: str,
    current_user = Depends(auth_middleware.require_permission("data:read"))
):
    if not auth_middleware.check_company_access(current_user, company):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to access data from '{company}'"
        )
    ...
```

### Rule 4: Proper Pydantic Response Models

**Context:** Missing response models cause undocumented APIs, inconsistent responses, and broken Orval client generation.

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ✅ CORRECT: Response model with all database fields
class ResourceResponse(BaseModel):
    id: int
    resource_id: str
    name: str
    description: Optional[str] = None
    status: str
    customer_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # Pydantic v2
        # OR for Pydantic v1:
        # orm_mode = True

# ✅ CORRECT: Request model with validation
class ResourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Resource name")
    description: Optional[str] = Field(None, max_length=2000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Resource",
                "description": "A useful resource"
            }
        }

# ✅ CORRECT: List response with pagination
class ResourceListResponse(BaseModel):
    items: List[ResourceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
```

---

## Patterns

### Request/Response Schemas

Create schemas in `src/api/schemas/your_feature.py`:

```python
"""
[Feature Name] API Schemas

Pydantic models for request/response validation.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ResourceStatus(str, Enum):
    """Status enum for resources."""
    PENDING = "pending"
    ACTIVE = "active"
    ARCHIVED = "archived"


# ============================================================
# Request Models
# ============================================================
class ResourceCreateRequest(BaseModel):
    """Request model for creating a resource."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the resource"
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Detailed description"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Configuration options"
    )
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Ensure name doesn't contain special characters."""
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Resource",
                "description": "A helpful resource for the team",
                "config": {"option1": True}
            }
        }


class ResourceUpdateRequest(BaseModel):
    """Request model for updating a resource."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[ResourceStatus] = None


# ============================================================
# Response Models
# ============================================================
class ResourceResponse(BaseModel):
    """Response model for a single resource."""
    id: int
    resource_id: str
    name: str
    description: Optional[str] = None
    status: ResourceStatus
    customer_id: str
    user_id: int
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # Enable ORM mode


class ResourceListResponse(BaseModel):
    """Response model for paginated resource list."""
    items: List[ResourceResponse]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


# ============================================================
# Async Operation Responses
# ============================================================
class ResourceSubmitResponse(BaseModel):
    """Response for async operation submission."""
    resource_id: str
    status: str
    message: str
    task_id: Optional[str] = None


class ResourceStatusResponse(BaseModel):
    """Response for status check."""
    resource_id: str
    status: str
    progress_percentage: Optional[float] = None
    current_stage: Optional[str] = None
    error_message: Optional[str] = None
```

### SQLAlchemy Model Alignment

Ensure your response model matches the database schema. Every database field should map to a response field.

```python
# src/models/your_model.py
class Resource(BaseModel):  # Inherits id, created_at, updated_at
    __tablename__ = "resources"
    
    resource_id = Column(String(100), unique=True, nullable=False)
    customer_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    config = Column(JSON, nullable=True)

# Response model MUST include all these fields:
class ResourceResponse(BaseModel):
    id: int                           # ← From BaseModel
    resource_id: str                  # ← From Resource
    customer_id: str                  # ← From Resource
    user_id: int                      # ← From Resource
    name: str                         # ← From Resource
    description: Optional[str]        # ← From Resource (nullable)
    status: str                       # ← From Resource
    config: Optional[Dict[str, Any]]  # ← From Resource (nullable)
    created_at: datetime              # ← From BaseModel
    updated_at: Optional[datetime]    # ← From BaseModel (may be null)
```

### Error Handling Patterns

```python
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

# Standard HTTP exceptions
def resource_not_found(resource_id: str):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Resource '{resource_id}' not found"
    )

def forbidden(message: str = "Access denied"):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message
    )

def bad_request(message: str):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message
    )

# For validation errors with multiple issues
def validation_error(errors: List[Dict]):
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=errors
    )

# Proper exception ordering in endpoints
@router.post("/")
async def create_resource(request: CreateRequest):
    try:
        # ... logic ...
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## Complete Template

```python
"""
[Feature Name] API Routes

API endpoints for [describe what this module does].
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from src.models import get_db
from src.middleware.authorization import AuthorizationMiddleware
from src.api.schemas.your_feature import (
    ResourceCreateRequest,
    ResourceUpdateRequest,
    ResourceResponse,
    ResourceListResponse
)
from src.services.your_service import YourService
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.API)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/v1/resources", tags=["Resources"])


# ============================================================
# CREATE
# ============================================================
@router.post(
    "/",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new resource",
    description="Create a new resource. Requires 'resources:write' permission."
)
async def create_resource(
    request: ResourceCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("resources:write"))
):
    """
    Create a new resource.
    
    - **name**: Required. Name of the resource.
    - **description**: Optional. Detailed description.
    """
    logger.info(
        "create_resource",
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        resource_name=request.name
    )
    
    try:
        service = YourService(db)
        
        # Check for duplicates if needed
        existing = service.get_by_name(
            name=request.name,
            customer_id=current_user.customer_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Resource with name '{request.name}' already exists"
            )
        
        # Create resource
        resource = service.create(
            user_id=current_user.user_id,
            customer_id=current_user.customer_id,
            name=request.name,
            description=request.description
        )
        
        return ResourceResponse.from_orm(resource)
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("create_resource_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create resource"
        )


# ============================================================
# READ (Single)
# ============================================================
@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Get resource details",
    description="Get detailed information about a specific resource."
)
async def get_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("resources:read"))
):
    """Get a resource by ID."""
    service = YourService(db)
    
    resource = service.get(resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )
    
    # Authorization: Check ownership or admin role
    if (resource.customer_id != current_user.customer_id 
            and not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this resource"
        )
    
    return ResourceResponse.from_orm(resource)


# ============================================================
# READ (List with pagination and filters)
# ============================================================
@router.get(
    "/",
    response_model=ResourceListResponse,
    summary="List resources",
    description="List resources with optional filters and pagination."
)
async def list_resources(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("resources:read"))
):
    """List resources with pagination."""
    service = YourService(db)
    
    offset = (page - 1) * page_size
    
    resources, total = service.list(
        customer_id=current_user.customer_id,
        status=status_filter,
        search=search,
        limit=page_size,
        offset=offset
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return ResourceListResponse(
        items=[ResourceResponse.from_orm(r) for r in resources],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


# ============================================================
# UPDATE
# ============================================================
@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Update a resource",
    description="Update an existing resource. Only provided fields will be updated."
)
async def update_resource(
    resource_id: str,
    request: ResourceUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("resources:write"))
):
    """Update a resource."""
    service = YourService(db)
    
    resource = service.get(resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )
    
    # Authorization
    if (resource.customer_id != current_user.customer_id 
            and not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this resource"
        )
    
    try:
        updated = service.update(
            resource_id=resource_id,
            **request.dict(exclude_unset=True)  # Only update provided fields
        )
        return ResourceResponse.from_orm(updated)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================
# DELETE
# ============================================================
@router.delete(
    "/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a resource",
    description="Delete a resource. This action cannot be undone."
)
async def delete_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("resources:delete"))
):
    """Delete a resource."""
    service = YourService(db)
    
    resource = service.get(resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )
    
    # Authorization
    if (resource.customer_id != current_user.customer_id 
            and not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this resource"
        )
    
    logger.info(
        "delete_resource",
        resource_id=resource_id,
        user_id=current_user.user_id
    )
    
    service.delete(resource_id)
    # Return 204 No Content (no response body)
```

---

## Integration

### Step 1: Register Router in main.py

After creating your router, register it in `src/main.py`:

```python
# src/main.py
from src.api.routes.your_feature import router as your_feature_router

# ... existing routers ...

app.include_router(your_feature_router)
```

### Step 2: Rebuild Container

```bash
docker-compose build app
docker-compose up -d app
```

---

## File Locations

```
src/
├── api/
│   ├── routes/
│   │   └── your_feature.py      # FastAPI route definitions
│   └── schemas/
│       └── your_feature.py      # Pydantic request/response models
├── models/
│   └── your_model.py            # SQLAlchemy ORM models
├── services/
│   └── your_service.py          # Business logic layer
├── middleware/
│   └── authorization.py         # AuthorizationMiddleware
├── core/
│   └── logging.py               # Structured logging
└── main.py                      # Router registration
```

---

## Testing

### Unit Tests

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from src.main import app

client = TestClient(app)

@pytest.fixture
def auth_header():
    """Get authentication header for tests."""
    return {"Authorization": "Bearer test-token"}

@pytest.fixture
def mock_current_user():
    """Mock authenticated user."""
    return Mock(
        user_id=1,
        customer_id="test-customer",
        is_superuser=False
    )

def test_create_resource_success(auth_header, mock_current_user):
    """Test successful resource creation."""
    with patch('src.middleware.authorization.AuthorizationMiddleware.require_permission') as mock_auth:
        mock_auth.return_value = lambda: mock_current_user
        
        response = client.post(
            "/v1/resources/",
            headers=auth_header,
            json={
                "name": "Test Resource",
                "description": "A test resource"
            }
        )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Resource"
    assert "resource_id" in data

def test_create_resource_duplicate(auth_header, mock_current_user):
    """Test duplicate resource creation returns 409."""
    # ... setup to create duplicate ...
    
    response = client.post(
        "/v1/resources/",
        headers=auth_header,
        json={"name": "Existing Resource"}
    )
    
    assert response.status_code == 409

def test_get_resource_not_found(auth_header):
    """Test 404 for non-existent resource."""
    response = client.get(
        "/v1/resources/nonexistent-id",
        headers=auth_header
    )
    
    assert response.status_code == 404
```

---

## Checklist

- [ ] Response model includes ALL database fields (no hardcoded None values)
- [ ] Correct HTTP status codes used (201 for create, 202 for async, etc.)
- [ ] Permission checks on all endpoints
- [ ] Customer isolation enforced (filter by customer_id)
- [ ] Input validation with Pydantic validators
- [ ] Error handling doesn't leak internal details
- [ ] Logging at key operations
- [ ] Router registered in main.py
- [ ] API documented (summary, description)
- [ ] Container rebuilt: `docker-compose build app`

---

## References

- `src/api/routes/` — API route implementations
- `src/api/schemas/` — Pydantic request/response models
- `src/models/` — SQLAlchemy database models
- `src/services/` — Business logic services
- `src/middleware/authorization.py` — Authentication and authorization middleware
- `src/main.py` — Application entry point and router registration
- `skills/celery-tasks/` — Async task patterns for long-running operations
- [FastAPI Documentation](https://fastapi.tiangolo.com/) — Official FastAPI docs
