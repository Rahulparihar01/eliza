"""
AI Enablement Platform - Permission Management API Routes

FastAPI routes for managing permissions, roles, and access control.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from src.services.permission_service import permission_service
from src.models.auth import User, Role, Permission
from src.middleware.authorization import get_current_user, require_permission, ResourceScope

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for request/response
class PermissionCreate(BaseModel):
    name: str
    resource: str
    action: str
    description: Optional[str] = None
    scope: str = "all"
    conditions: Optional[Dict[str, Any]] = None


class PermissionResponse(BaseModel):
    id: int
    name: str
    resource: str
    action: str
    description: Optional[str]
    scope: str
    conditions: Optional[Dict[str, Any]]
    created_at: str

    class Config:
        from_attributes = True


class RolePermissionAssignment(BaseModel):
    role_id: int
    permission_id: int


class UserRoleAssignment(BaseModel):
    user_id: int
    role_id: int


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_system_role: bool
    permissions: List[PermissionResponse]
    created_at: str

    class Config:
        from_attributes = True


class UserPermissionsResponse(BaseModel):
    user_id: int
    user_email: str
    roles: List[str]
    permissions: List[str]
    effective_permissions: List[str]


@router.post("/permissions", response_model=PermissionResponse)
async def create_permission(
    permission_data: PermissionCreate,
    current_user: User = Depends(require_permission("roles:create", resource_type="permission"))
):
    """
    Create a new permission.
    Requires 'roles:create' permission.
    """
    try:
        permission = await permission_service.create_permission(
            name=permission_data.name,
            resource=permission_data.resource,
            action=permission_data.action,
            description=permission_data.description,
            scope=permission_data.scope,
            conditions=permission_data.conditions,
            created_by_id=current_user.id
        )
        
        return PermissionResponse(
            id=permission.id,
            name=permission.name,
            resource=permission.resource,
            action=permission.action,
            description=permission.description,
            scope=permission.scope,
            conditions=permission.conditions,
            created_at=permission.created_at.isoformat()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating permission: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create permission"
        )


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    resource: Optional[str] = Query(None, description="Filter by resource type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    scope: Optional[str] = Query(None, description="Filter by scope"),
    current_user: User = Depends(require_permission("roles:read", resource_type="permission"))
):
    """
    List permissions with optional filtering.
    Requires 'roles:read' permission.
    """
    try:
        permissions = await permission_service.list_permissions(
            resource=resource,
            action=action,
            scope=scope
        )
        
        return [
            PermissionResponse(
                id=perm.id,
                name=perm.name,
                resource=perm.resource,
                action=perm.action,
                description=perm.description,
                scope=perm.scope,
                conditions=perm.conditions,
                created_at=perm.created_at.isoformat()
            )
            for perm in permissions
        ]
        
    except Exception as e:
        logger.error(f"Error listing permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list permissions"
        )


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    current_user: User = Depends(require_permission("roles:read", resource_type="role"))
):
    """
    List all roles with their permissions.
    Requires 'roles:read' permission.
    """
    try:
        roles = await permission_service.list_roles()
        
        return [
            RoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                is_system_role=role.is_system_role,
                permissions=[
                    PermissionResponse(
                        id=perm.id,
                        name=perm.name,
                        resource=perm.resource,
                        action=perm.action,
                        description=perm.description,
                        scope=perm.scope,
                        conditions=perm.conditions,
                        created_at=perm.created_at.isoformat()
                    )
                    for perm in role.permissions
                ],
                created_at=role.created_at.isoformat()
            )
            for role in roles
        ]
        
    except Exception as e:
        logger.error(f"Error listing roles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list roles"
        )


@router.post("/roles/{role_id}/permissions")
async def assign_permission_to_role(
    role_id: int,
    assignment: RolePermissionAssignment,
    current_user: User = Depends(require_permission("roles:update", resource_type="role"))
):
    """
    Assign a permission to a role.
    Requires 'roles:update' permission.
    """
    try:
        success = await permission_service.assign_permission_to_role(
            role_id=assignment.role_id,
            permission_id=assignment.permission_id,
            granted_by_id=current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Permission already assigned to role"
            )
        
        return {"message": "Permission assigned to role successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error assigning permission to role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign permission to role"
        )


@router.delete("/roles/{role_id}/permissions/{permission_id}")
async def revoke_permission_from_role(
    role_id: int,
    permission_id: int,
    current_user: User = Depends(require_permission("roles:update", resource_type="role"))
):
    """
    Revoke a permission from a role.
    Requires 'roles:update' permission.
    """
    try:
        success = await permission_service.revoke_permission_from_role(
            role_id=role_id,
            permission_id=permission_id,
            revoked_by_id=current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Permission not assigned to role"
            )
        
        return {"message": "Permission revoked from role successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error revoking permission from role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke permission from role"
        )


@router.post("/users/{user_id}/roles")
async def assign_role_to_user(
    user_id: int,
    assignment: UserRoleAssignment,
    current_user: User = Depends(require_permission("users:update", resource_type="user"))
):
    """
    Assign a role to a user.
    Requires 'users:update' permission.
    """
    try:
        success = await permission_service.assign_role_to_user(
            user_id=assignment.user_id,
            role_id=assignment.role_id,
            assigned_by_id=current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role already assigned to user"
            )
        
        return {"message": "Role assigned to user successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error assigning role to user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role to user"
        )


@router.delete("/users/{user_id}/roles/{role_id}")
async def revoke_role_from_user(
    user_id: int,
    role_id: int,
    current_user: User = Depends(require_permission("users:update", resource_type="user"))
):
    """
    Revoke a role from a user.
    Requires 'users:update' permission.
    """
    try:
        success = await permission_service.revoke_role_from_user(
            user_id=user_id,
            role_id=role_id,
            revoked_by_id=current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not assigned to user"
            )
        
        return {"message": "Role revoked from user successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error revoking role from user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke role from user"
        )


@router.get("/users/{user_id}/permissions", response_model=UserPermissionsResponse)
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(require_permission("users:read", resource_type="user"))
):
    """
    Get all permissions for a user.
    Requires 'users:read' permission.
    """
    try:
        from src.services.auth_service import auth_service
        
        user = await auth_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        effective_permissions = await permission_service.get_user_effective_permissions(user_id)
        
        return UserPermissionsResponse(
            user_id=user.id,
            user_email=user.email,
            roles=[role.name for role in user.roles],
            permissions=[perm.name for role in user.roles for perm in role.permissions],
            effective_permissions=effective_permissions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user permissions"
        )
