"""
Pydantic schemas for User Management API endpoints.
Defines request/response models for user operations and listings.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime


# ============================================================================
# User List Schemas
# ============================================================================

class UserListItem(BaseModel):
    """User item in list response"""
    id: int = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., description="User full name")
    roles: List[str] = Field(default_factory=list, description="User roles")
    is_active: bool = Field(True, description="User active status")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "email": "user@example.com",
                "full_name": "John Doe",
                "roles": ["admin"],
                "is_active": True,
                "last_login_at": "2025-10-01T09:15:00Z",
                "created_at": "2025-01-01T00:00:00Z"
            }
        }


# ============================================================================
# Pagination Schema
# ============================================================================

class PaginationInfo(BaseModel):
    """Pagination metadata"""
    total_count: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")

    class Config:
        json_schema_extra = {
            "example": {
                "total_count": 50,
                "page": 1,
                "page_size": 20,
                "total_pages": 3
            }
        }


# ============================================================================
# Users List Response Schema
# ============================================================================

class UsersListResponse(BaseModel):
    """Paginated users list response"""
    users: List[UserListItem] = Field(default_factory=list, description="List of users")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")

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

