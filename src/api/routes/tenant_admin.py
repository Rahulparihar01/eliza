"""
AI Enablement Platform - Tenant Admin API Routes

API endpoints for tenant-level administration:
- Role management (CRUD, permissions)
- User management
- User invites
- Available permissions
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.auth import User
from src.middleware.authorization import get_current_user, auth_middleware
from src.services.tenant_admin_service import TenantAdminService
from src.api.schemas.tenant_admin import (
    # Permissions
    PermissionCategory,
    AvailablePermissionsResponse,
    FeaturePermissionResponse,
    # Roles
    TenantRoleCreate,
    TenantRoleUpdate,
    TenantRoleResponse,
    TenantRoleWithPermissions,
    RolePermissionsUpdateRequest,
    # Users
    TenantUserResponse,
    TenantUserListResponse,
    TenantUserUpdate,
    UserRolesUpdateRequest,
    UserRoleAssignment,
    # Invites
    UserInviteCreate,
    UserInviteResponse,
    UserInviteListResponse,
    InviteValidationResponse,
    InviteAcceptRequest,
)

router = APIRouter(prefix="/admin", tags=["Tenant Admin"])


def get_tenant_admin_service(db: Session = Depends(get_db)) -> TenantAdminService:
    """Dependency to get TenantAdminService."""
    return TenantAdminService(db)


def require_admin_permission(
    current_user = Depends(get_current_user),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Require user to have admin permission for user/role management."""
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    permissions = service.get_user_permissions(user_id)
    
    # Check for any admin-level permissions (new comprehensive permission names)
    admin_permissions = [
        'roles:create', 'roles:update', 'roles:delete', 'roles:assign',
        'users:invite', 'users:update', 'users:deactivate', 'users:delete',
        'invites:create', 'invites:revoke', 'invites:resend',
        'platform:admin'  # Platform admins always have access
    ]
    
    has_admin_permission = any(perm in permissions for perm in admin_permissions)
    
    if not has_admin_permission:
        # Also check if user is a superuser
        is_superuser = current_user.is_superuser if hasattr(current_user, 'is_superuser') else False
        if not is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for admin operations"
            )
    return current_user


# =============================================================================
# PERMISSIONS
# =============================================================================

@router.get("/permissions", response_model=AvailablePermissionsResponse)
async def get_available_permissions(
    current_user: User = Depends(get_current_user),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """
    Get all permissions available to the current tenant.
    
    Permissions are grouped by feature category. Features not allocated
    to the tenant are marked as disabled.
    """
    # Get all features
    all_features = service.get_all_features()
    
    # Get allocated feature IDs for this tenant
    allocated_ids = service.get_allocated_feature_ids(current_user.customer_id)
    
    categories = []
    for feature in all_features:
        feature_with_perms = service.get_feature_with_permissions(feature.id)
        is_enabled = feature.id in allocated_ids
        
        categories.append(PermissionCategory(
            id=feature.feature_key,
            display_name=feature.display_name,
            icon=feature.icon,
            is_enabled=is_enabled,
            disabled_reason="Feature not allocated to your tenant" if not is_enabled else None,
            permissions=[
                FeaturePermissionResponse(
                    id=p.id,
                    feature_id=p.feature_id,
                    permission_key=p.permission_key,
                    display_name=p.display_name,
                    description=p.description,
                    sort_order=p.sort_order
                )
                for p in (feature_with_perms.permissions if feature_with_perms else [])
            ] if is_enabled else []
        ))
    
    return AvailablePermissionsResponse(categories=categories)


@router.get("/permissions/by-feature", response_model=AvailablePermissionsResponse)
async def get_permissions_by_feature(
    current_user: User = Depends(get_current_user),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Get permissions grouped by feature (only allocated features)."""
    return await get_available_permissions(current_user, service)


@router.get("/permissions/all")
async def get_all_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    scope: str = Query(
        default="tenant",
        pattern="^(tenant|global)$",
        description="Permission catalog scope. tenant = allocated features only, global = all permissions (platform admins only).",
    ),
):
    """
    Get permissions available to this tenant based on allocated features.
    
    This returns permissions in the new format (name, resource, action)
    for the Northflank-style permission selector.
    
    IMPORTANT: Only returns permissions for features allocated to the tenant.
    Platform admins see all permissions.
    """
    from src.models.auth import Permission
    from src.models.tenant_admin import TenantFeatureAllocation, PlatformFeature
    
    # Feature key to permission prefix mapping (same as in tenant_admin_service.py)
    FEATURE_PERMISSION_MAP = {
        # Admin features (core tenant admin functionality - always available)
        'users_roles': ['users:', 'roles:'],
        'invites': ['invites:'],
        'settings': ['admin:settings:', 'admin:email:'],
        'connectors': ['connections:'],
        'audit': ['audit:'],
        
        # AI Assistant features
        'documents': ['assistant:documents:', 'assistant:domains:'],
        'assistant_chat': ['assistant:chat:', 'assistant:access'],
        'business_intelligence': ['assistant:questions:'],
        
        # AI Recruiter features
        'talent_intelligence': ['recruiter:access', 'recruiter:config:', 'recruiter:dna:', 'recruiter:results:', 'recruiter:history:'],
        'recruiter_blueprints': ['recruiter:blueprints:'],
        'recruiter_email_templates': ['recruiter:email_templates:', 'recruiter:section_library:'],
        'recruiter_reference_checks': ['recruiter:reference_checks:'],
        
        # Labs features
        'labs_resume_parsing': ['labs:resume_parsing:'],
        'ai_providers': ['labs:agents:'],
        
        # Analytics features
        'adoption_dashboard': ['adoption:view_dashboard', 'adoption:read:', 'adoption:manage_sharing', 'adoption:manage_sync', 'adoption:manage_jobs'],
    }
    
    all_permissions = db.query(Permission).order_by(Permission.name).all()
    
    # Optional global scope for platform admin surfaces.
    # Tenant admin flows should call with scope=tenant (default).
    if scope == "global" and current_user.has_permission('platform:admin'):
        return {
            "permissions": [
                {
                    "id": p.id,
                    "name": p.name,
                    "resource": p.resource,
                    "action": p.action,
                    "description": p.description,
                }
                for p in all_permissions
            ]
        }
    
    # Get allocated features for this tenant
    allocations = db.query(TenantFeatureAllocation).join(
        PlatformFeature
    ).filter(
        TenantFeatureAllocation.customer_id == current_user.customer_id,
        TenantFeatureAllocation.is_enabled == True
    ).all()
    
    allocated_feature_keys = {a.feature.feature_key for a in allocations}
    
    # Build allowed permission prefixes based on allocated features
    allowed_prefixes = []
    for feature_key in allocated_feature_keys:
        if feature_key in FEATURE_PERMISSION_MAP:
            allowed_prefixes.extend(FEATURE_PERMISSION_MAP[feature_key])
    
    def permission_is_allowed(perm_name: str) -> bool:
        """Check if a permission is allowed based on allocated features."""
        # platform:admin is never shown to tenant admins
        if perm_name == 'platform:admin':
            return False
        
        # Check if permission matches any allowed prefix
        for prefix in allowed_prefixes:
            if perm_name.startswith(prefix) or perm_name == prefix:
                return True
        return False
    
    # Filter permissions
    filtered_permissions = [p for p in all_permissions if permission_is_allowed(p.name)]
    
    return {
        "permissions": [
            {
                "id": p.id,
                "name": p.name,
                "resource": p.resource,
                "action": p.action,
                "description": p.description,
            }
            for p in filtered_permissions
        ]
    }


# =============================================================================
# ROLES
# =============================================================================

@router.get("/roles", response_model=List[TenantRoleResponse])
async def list_roles(
    include_inactive: bool = Query(False, description="Include inactive roles"),
    scoped_to_allocated_features: bool = Query(
        True,
        description="Only include roles relevant to allocated features for the tenant.",
    ),
    current_user: User = Depends(get_current_user),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """List all roles in the current tenant."""
    roles = service.get_tenant_roles(
        current_user.customer_id,
        include_inactive=include_inactive,
        filter_by_allocated_features=scoped_to_allocated_features,
    )
    return [
        TenantRoleResponse(
            id=role.id,
            customer_id=role.customer_id,
            role_name=role.role_name,
            display_name=role.display_name,
            description=role.description,
            is_system_role=role.is_system_role,
            is_active=role.is_active,
            permission_count=role.permission_count,
            user_count=role.user_count,
            created_at=role.created_at,
            updated_at=role.updated_at
        )
        for role in roles
    ]


@router.post("/roles", response_model=TenantRoleWithPermissions, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: TenantRoleCreate,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service),
    db: Session = Depends(get_db)
):
    """Create a new role with optional permissions."""
    from src.models.auth import Permission
    
    # Validate permission IDs exist in the Permission table
    # The frontend sends Permission IDs (from auth.permissions table), not FeaturePermission IDs
    if role_data.permission_ids:
        existing_perms = db.query(Permission.id).filter(
            Permission.id.in_(role_data.permission_ids)
        ).all()
        existing_ids = {p.id for p in existing_perms}
        invalid_ids = set(role_data.permission_ids) - existing_ids
        if invalid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission IDs: {invalid_ids}"
            )
    
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    role = service.create_role(
        customer_id=current_user.customer_id,
        role_data=role_data,
        created_by=user_id
    )
    
    return _role_with_permissions_response(role)


@router.get("/roles/{role_id}", response_model=TenantRoleWithPermissions)
async def get_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Get a role with its permissions."""
    role = service.get_role_by_id(role_id)
    if not role or role.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    return _role_with_permissions_response(role)


@router.put("/roles/{role_id}", response_model=TenantRoleWithPermissions)
async def update_role(
    role_id: int,
    role_data: TenantRoleUpdate,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Update a role."""
    role = service.get_role_by_id(role_id)
    if not role or role.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Protect platform_admin role - can only be managed via Platform Admin section
    if role.name == 'platform_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin role cannot be modified. Manage via Platform Admin > Manage Admins."
        )
    
    try:
        updated_role = service.update_role(role_id, role_data)
        return _role_with_permissions_response(updated_role)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Delete a role (soft delete)."""
    role = service.get_role_by_id(role_id)
    if not role or role.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Protect platform_admin role - can only be managed via Platform Admin section
    if role.name == 'platform_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin role cannot be deleted."
        )
    
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system roles"
        )
    
    service.delete_role(role_id)


@router.put("/roles/{role_id}/permissions", response_model=TenantRoleWithPermissions)
async def update_role_permissions(
    role_id: int,
    request: RolePermissionsUpdateRequest,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service),
    db: Session = Depends(get_db)
):
    """Update all permissions for a role (replaces existing)."""
    role = service.get_role_by_id(role_id)
    if not role or role.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Protect platform_admin role - can only be managed via Platform Admin section
    if role.name == 'platform_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin role permissions cannot be modified."
        )
    
    # Validate permission IDs against BOTH permission tables (legacy feature_permissions and new permissions)
    if request.permission_ids:
        from src.models.auth import Permission
        
        # Get IDs from new permissions table
        new_perms = db.query(Permission.id).all()
        new_perm_ids = {p.id for p in new_perms}
        
        # Get IDs from legacy feature_permissions table
        legacy_perms = service.get_available_permissions_for_tenant(current_user.customer_id)
        legacy_ids = {p.id for p in legacy_perms}
        
        # Accept IDs from either table
        available_ids = new_perm_ids | legacy_ids
        invalid_ids = set(request.permission_ids) - available_ids
        if invalid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission IDs: {invalid_ids}"
            )
    
    updated_role = service.set_role_permissions(role_id, request.permission_ids)
    return _role_with_permissions_response(updated_role)


@router.post("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_201_CREATED)
async def add_permission_to_role(
    role_id: int,
    permission_id: int,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Add a single permission to a role."""
    role = service.get_role_by_id(role_id)
    if not role or role.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    success = service.add_permission_to_role(role_id, permission_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission already assigned to role"
        )
    
    return {"message": "Permission added"}


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Remove a permission from a role."""
    role = service.get_role_by_id(role_id)
    if not role or role.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    service.remove_permission_from_role(role_id, permission_id)


# =============================================================================
# USERS
# =============================================================================

@router.get("/users", response_model=TenantUserListResponse)
async def list_users(
    current_user: User = Depends(get_current_user),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """List all users in the current tenant."""
    users = service.get_tenant_users(current_user.customer_id)
    
    user_responses = []
    for user in users:
        # Only get roles for the current tenant
        roles = service.get_user_roles(user.id, customer_id=current_user.customer_id)
        user_responses.append(TenantUserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            customer_id=user.customer_id,
            is_active=user.is_active,
            department=user.department,
            team=user.team,
            last_login=user.last_login_at,  # Use last_login_at which is updated by security service
            created_at=user.created_at,
            roles=[
                UserRoleAssignment(
                    role_id=r.id,
                    role_name=r.role_name,
                    display_name=r.display_name,
                    assigned_at=r.created_at  # Use role created_at as fallback
                )
                for r in roles
            ]
        ))
    
    return TenantUserListResponse(users=user_responses, total=len(user_responses))


@router.get("/users/{user_id}", response_model=TenantUserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Get a user with their roles."""
    user = service.get_user_with_roles(user_id)
    if not user or user.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only get roles for the current tenant
    roles = service.get_user_roles(user_id, customer_id=current_user.customer_id)
    return TenantUserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        customer_id=user.customer_id,
        is_active=user.is_active,
        department=user.department,
        team=user.team,
        last_login=user.last_login_at,  # Use last_login_at which is updated by security service
        created_at=user.created_at,
        roles=[
            UserRoleAssignment(
                role_id=r.id,
                role_name=r.role_name,
                display_name=r.display_name,
                assigned_at=r.created_at
            )
            for r in roles
        ]
    )


@router.post("/users/{user_id}/roles", response_model=List[UserRoleAssignment])
async def update_user_roles(
    user_id: int,
    request: UserRolesUpdateRequest,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Update roles for a user (replaces existing roles)."""
    user = service.get_user_with_roles(user_id)
    if not user or user.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate role IDs belong to this tenant
    tenant_roles = service.get_tenant_roles(
        current_user.customer_id,
        filter_by_allocated_features=True,
    )
    tenant_role_ids = {r.id for r in tenant_roles}
    invalid_ids = set(request.role_ids) - tenant_role_ids
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role IDs: {invalid_ids}"
        )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    roles = service.set_user_roles(user_id, request.role_ids, current_user_id)
    return [
        UserRoleAssignment(
            role_id=r.id,
            role_name=r.role_name,
            display_name=r.display_name,
            assigned_at=r.created_at
        )
        for r in roles
    ]


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Remove a role from a user."""
    user = service.get_user_with_roles(user_id)
    if not user or user.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    service.remove_role_from_user(user_id, role_id)


# =============================================================================
# USER INVITES
# =============================================================================

@router.post("/invites", response_model=UserInviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    invite_data: UserInviteCreate,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Create a new user invite."""
    # Validate role IDs if provided
    if invite_data.role_ids:
        tenant_roles = service.get_tenant_roles(
            current_user.customer_id,
            filter_by_allocated_features=True,
        )
        tenant_role_ids = {r.id for r in tenant_roles}
        invalid_ids = set(invite_data.role_ids) - tenant_role_ids
        if invalid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role IDs: {invalid_ids}"
            )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    invite = service.create_invite(
        customer_id=current_user.customer_id,
        invite_data=invite_data,
        created_by=current_user_id
    )
    
    # Generate invite URL
    from src.core.config import get_settings
    settings = get_settings()
    base_url = settings.frontend_url or "https://app.eliza.ai"
    invite_url = f"{base_url}/accept-invite?token={invite.invite_token}"
    
    return UserInviteResponse(
        id=invite.id,
        customer_id=invite.customer_id,
        email=invite.email,
        full_name=invite.full_name,
        invite_token=invite.invite_token,
        invite_url=invite_url,
        role_ids=invite.role_ids,
        status=invite.status,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at
    )


@router.get("/invites", response_model=UserInviteListResponse)
async def list_invites(
    current_user: User = Depends(get_current_user),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """List all pending invites for the current tenant."""
    invites = service.get_pending_invites(current_user.customer_id)
    
    from src.core.config import get_settings
    settings = get_settings()
    base_url = settings.frontend_url or "https://app.eliza.ai"
    
    return UserInviteListResponse(
        invites=[
            UserInviteResponse(
                id=i.id,
                customer_id=i.customer_id,
                email=i.email,
                full_name=i.full_name,
                invite_token=i.invite_token,
                invite_url=f"{base_url}/accept-invite?token={i.invite_token}",
                role_ids=i.role_ids,
                status=i.status,
                created_at=i.created_at,
                expires_at=i.expires_at,
                accepted_at=i.accepted_at
            )
            for i in invites
        ],
        total=len(invites)
    )


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: int,
    current_user = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Revoke a pending invite."""
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    success = service.revoke_invite(invite_id, current_user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or already used"
        )


@router.post("/invites/{invite_id}/resend", response_model=UserInviteResponse)
async def resend_invite(
    invite_id: int,
    current_user: User = Depends(require_admin_permission),
    service: TenantAdminService = Depends(get_tenant_admin_service)
):
    """Resend an invite (generates new token and extends expiration)."""
    invite = service.resend_invite(invite_id)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found or not pending"
        )
    
    from src.core.config import get_settings
    settings = get_settings()
    base_url = settings.frontend_url or "https://app.eliza.ai"
    
    return UserInviteResponse(
        id=invite.id,
        customer_id=invite.customer_id,
        email=invite.email,
        full_name=invite.full_name,
        invite_token=invite.invite_token,
        invite_url=f"{base_url}/accept-invite?token={invite.invite_token}",
        role_ids=invite.role_ids,
        status=invite.status,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _role_with_permissions_response(role) -> TenantRoleWithPermissions:
    """Convert a Role to TenantRoleWithPermissions response."""
    permissions = []
    
    # Role.permissions is the relationship to Permission model via role_permissions table
    for perm in role.permissions:
        # Handle both old (FeaturePermission) and new (Permission) formats
        if hasattr(perm, 'permission_key'):
            # Old format from feature_permissions table
            permissions.append(FeaturePermissionResponse(
                id=perm.id,
                feature_id=getattr(perm, 'feature_id', 0),
                permission_key=perm.permission_key,
                display_name=perm.display_name,
                description=perm.description,
                sort_order=getattr(perm, 'sort_order', 0)
            ))
        elif hasattr(perm, 'name'):
            # New format from permissions table
            # Extract a display name from the permission name
            name_parts = perm.name.split(':')
            display_name = ' '.join(name_parts).title().replace('_', ' ')
            permissions.append(FeaturePermissionResponse(
                id=perm.id,
                feature_id=0,  # Not used in new system
                permission_key=perm.name,  # Use full name as key
                display_name=display_name,
                description=perm.description,
                sort_order=0
            ))
    
    # Role model uses 'name' but response expects 'role_name'
    role_name = getattr(role, 'role_name', None) or getattr(role, 'name', '')
    user_count = getattr(role, 'user_count', 0) or len(getattr(role, 'users', []))
    
    return TenantRoleWithPermissions(
        id=role.id,
        customer_id=role.customer_id,
        role_name=role_name,
        display_name=role.display_name,
        description=role.description,
        is_system_role=role.is_system_role,
        is_active=role.is_active,
        permission_count=len(permissions),
        user_count=user_count,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=permissions,
        permission_ids=[p.id for p in permissions]
    )


# =============================================================================
# ADOPTION ACCESS MANAGEMENT (Phase 9)
# =============================================================================

from pydantic import BaseModel as PydanticBaseModel
from datetime import datetime as dt

class AdoptionGrantInfo(PydanticBaseModel):
    """Information about an adoption data sharing grant."""
    id: int
    customer_id: str
    customer_name: Optional[str]
    is_enabled: bool
    share_level: str
    granted_at: dt
    expires_at: Optional[dt]

class TenantAdoptionAccessResponse(PydanticBaseModel):
    """Response with tenant's inbound and outbound adoption grants."""
    inbound_grants: List[AdoptionGrantInfo]  # Tenants whose data WE can view
    outbound_grants: List[AdoptionGrantInfo]  # Tenants who can view OUR data

class AdoptionGrantToggleRequest(PydanticBaseModel):
    """Request to toggle an adoption grant."""
    is_enabled: bool


class TenantAdoptionSettingsResponse(PydanticBaseModel):
    """Tenant adoption sync settings and status."""
    customer_id: str
    initial_sync_start_date: str
    schedule_enabled: bool
    schedule_cron: Optional[str]
    last_synced_at: Optional[str]
    sync_health: str
    adoption_provider_configured: bool
    compliance_api_key_configured: bool
    compliance_status: Optional[str]


class TenantAdoptionSettingsUpdateRequest(PydanticBaseModel):
    """Update tenant adoption sync settings."""
    initial_sync_start_date: Optional[str] = None
    schedule_enabled: Optional[bool] = None
    schedule_cron: Optional[str] = None


def _get_last_sync_timestamp(db: Session, customer_id: str) -> Optional[str]:
    """Return the most recent sync-run timestamp for a tenant.

    Uses the ``last_synced_at`` column written during each sync run on
    conversation and GPT records, which reflects when the sync actually
    executed (not the date of the data that was synced).
    """
    from sqlalchemy import func as sql_func
    from src.models.adoption import AdoptionConversation, AdoptionGPT

    candidates = []
    for model in (AdoptionConversation, AdoptionGPT):
        ts = db.query(sql_func.max(model.last_synced_at)).filter(
            model.customer_id == customer_id
        ).scalar()
        if ts is not None:
            candidates.append(ts)

    if not candidates:
        return None

    latest = max(candidates)
    return latest.isoformat()


def _upsert_adoption_job_config(
    db: Session,
    schedule_enabled: bool,
    schedule_cron: Optional[str],
) -> None:
    """Keep platform job metadata aligned with RedBeat-driven adoption sync."""
    from src.models.scheduled_job import ScheduledJobConfig

    job = db.query(ScheduledJobConfig).filter(
        ScheduledJobConfig.job_name == "adoption-daily-sync"
    ).first()
    if not job:
        return

    job.task_name = "adoption.daily_sync"
    job.schedule_type = "cron" if schedule_cron else "interval"
    job.schedule_value = schedule_cron or "60"
    job.is_enabled = schedule_enabled
    job.description = (
        "Syncs ChatGPT Enterprise adoption metrics from OpenAI Compliance API. "
        "Runs on tenant-specific schedules managed in Adoption Settings."
    )


def _sync_adoption_redbeat_schedule(
    customer_id: str,
    schedule_enabled: bool,
    schedule_cron: Optional[str],
) -> None:
    """Create/update/remove tenant adoption schedule entry in RedBeat."""
    from celery.schedules import crontab
    from redbeat import RedBeatSchedulerEntry
    from src.celery_app import celery_app

    entry_name = f"adoption-daily-sync:{customer_id}"
    key_prefix = getattr(celery_app.conf, "redbeat_key_prefix", "redbeat:")
    redis_key = f"{key_prefix}{entry_name}"

    if not schedule_enabled or not schedule_cron:
        # Disable path: remove any existing tenant schedule.
        try:
            existing_entry = RedBeatSchedulerEntry.from_key(redis_key, app=celery_app)
            existing_entry.delete()
        except KeyError:
            pass
        return

    parts = schedule_cron.split()
    if len(parts) != 5:
        raise ValueError("schedule_cron must be a valid 5-field cron expression")

    minute, hour, day_of_month, month_of_year, day_of_week = parts
    schedule = crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )

    new_entry = RedBeatSchedulerEntry(
        name=entry_name,
        task="adoption.daily_sync",
        schedule=schedule,
        kwargs={
            "customer_id": customer_id,
            "track_job": True,
        },
        app=celery_app,
    )

    # Replace only after the new schedule has been parsed/constructed successfully.
    try:
        existing_entry = RedBeatSchedulerEntry.from_key(redis_key, app=celery_app)
        existing_entry.delete()
    except KeyError:
        pass

    new_entry.save()


@router.get("/adoption-settings", response_model=TenantAdoptionSettingsResponse)
async def get_tenant_adoption_settings(
    current_user=Depends(auth_middleware.require_any_permission(
        ["adoption:manage_sync", "adoption:manage_sharing", "platform:admin"]
    )),
    db: Session = Depends(get_db),
):
    """
    Get tenant adoption sync settings.

    This endpoint is the config source of truth for initial start date and
    schedule options shown in Adoption Settings UI.
    """
    from src.models.customer import CustomerAIProvider
    from src.services.adoption.sync_service import AdoptionSyncService

    customer_id = current_user.customer_id
    sync_service = AdoptionSyncService(db)
    config = sync_service.get_or_create_sync_config(customer_id)

    provider = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.customer_id == customer_id,
        CustomerAIProvider.is_adoption_source == True,
        CustomerAIProvider.is_enabled == True,
    ).first()

    last_synced_at = _get_last_sync_timestamp(db, customer_id)

    sync_health = "unknown"
    if provider:
        integrity = sync_service.check_consistency(customer_id, provider.provider_name)
        sync_health = "healthy" if integrity["is_consistent"] else "degraded"

    adoption_provider_configured = provider is not None
    compliance_api_key_configured = bool(
        provider
        and provider.provider_name == "openai"
        and provider.api_key_encrypted
        and provider.chatgpt_workspace_id
    )
    compliance_status = provider.adoption_compliance_status if provider else None

    return TenantAdoptionSettingsResponse(
        customer_id=customer_id,
        initial_sync_start_date=config.initial_sync_start_date.isoformat(),
        schedule_enabled=config.schedule_enabled,
        schedule_cron=config.schedule_cron,
        last_synced_at=last_synced_at,
        sync_health=sync_health,
        adoption_provider_configured=adoption_provider_configured,
        compliance_api_key_configured=compliance_api_key_configured,
        compliance_status=compliance_status,
    )


@router.put("/adoption-settings", response_model=TenantAdoptionSettingsResponse)
async def update_tenant_adoption_settings(
    request: TenantAdoptionSettingsUpdateRequest,
    current_user=Depends(auth_middleware.require_any_permission(
        ["adoption:manage_sync", "platform:admin"]
    )),
    db: Session = Depends(get_db),
):
    """Update tenant adoption sync settings."""
    from datetime import date, timedelta
    from src.models.customer import CustomerAIProvider
    from src.services.adoption.sync_service import AdoptionSyncService

    customer_id = current_user.customer_id
    sync_service = AdoptionSyncService(db)
    config = sync_service.get_or_create_sync_config(customer_id)

    if request.initial_sync_start_date is not None:
        try:
            parsed_start = date.fromisoformat(request.initial_sync_start_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="initial_sync_start_date must be YYYY-MM-DD",
            )

        if parsed_start > (date.today() - timedelta(days=1)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="initial_sync_start_date cannot be in the future",
            )
        config.initial_sync_start_date = parsed_start

    if request.schedule_cron is not None:
        normalized_cron = request.schedule_cron.strip() if request.schedule_cron else None
        config.schedule_cron = normalized_cron

    if request.schedule_enabled is not None:
        config.schedule_enabled = request.schedule_enabled

    effective_schedule_enabled = config.schedule_enabled
    effective_schedule_cron = config.schedule_cron
    if effective_schedule_enabled and not effective_schedule_cron:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="schedule_cron is required when schedule_enabled is true",
        )

    try:
        _sync_adoption_redbeat_schedule(
            customer_id=customer_id,
            schedule_enabled=effective_schedule_enabled,
            schedule_cron=effective_schedule_cron,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update adoption schedule: {str(e)}",
        ) from e

    _upsert_adoption_job_config(
        db=db,
        schedule_enabled=effective_schedule_enabled,
        schedule_cron=effective_schedule_cron,
    )

    db.commit()
    db.refresh(config)

    provider = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.customer_id == customer_id,
        CustomerAIProvider.is_adoption_source == True,
        CustomerAIProvider.is_enabled == True,
    ).first()

    last_synced_at = _get_last_sync_timestamp(db, customer_id)

    sync_health = "unknown"
    if provider:
        integrity = sync_service.check_consistency(customer_id, provider.provider_name)
        sync_health = "healthy" if integrity["is_consistent"] else "degraded"

    adoption_provider_configured = provider is not None
    compliance_api_key_configured = bool(
        provider
        and provider.provider_name == "openai"
        and provider.api_key_encrypted
        and provider.chatgpt_workspace_id
    )
    compliance_status = provider.adoption_compliance_status if provider else None

    return TenantAdoptionSettingsResponse(
        customer_id=customer_id,
        initial_sync_start_date=config.initial_sync_start_date.isoformat(),
        schedule_enabled=config.schedule_enabled,
        schedule_cron=config.schedule_cron,
        last_synced_at=last_synced_at,
        sync_health=sync_health,
        adoption_provider_configured=adoption_provider_configured,
        compliance_api_key_configured=compliance_api_key_configured,
        compliance_status=compliance_status,
    )


@router.get("/adoption-access", response_model=TenantAdoptionAccessResponse)
async def get_tenant_adoption_access(
    current_user = Depends(auth_middleware.require_any_permission(
        ["adoption:manage_sharing", "platform:admin"]
    )),
    db: Session = Depends(get_db)
):
    """
    Get adoption data sharing grants for the current tenant.
    
    Returns both:
    - Inbound grants: Tenants whose data this tenant CAN view
    - Outbound grants: Tenants who CAN view this tenant's data
    
    Tenant admins can toggle these grants on/off but cannot create new ones.
    """
    from src.models.adoption import AdoptionDataShare
    from src.models.customer import Customer
    
    customer_id = current_user.customer_id
    
    # Get inbound grants (we can view their data)
    inbound_query = db.query(AdoptionDataShare).filter(
        AdoptionDataShare.target_customer_id == customer_id
    ).all()
    
    inbound_grants = []
    for grant in inbound_query:
        source = db.query(Customer).filter(
            Customer.customer_id == grant.source_customer_id
        ).first()
        inbound_grants.append(AdoptionGrantInfo(
            id=grant.id,
            customer_id=grant.source_customer_id,
            customer_name=source.display_name or source.name if source else None,
            is_enabled=grant.is_enabled,
            share_level=grant.share_level,
            granted_at=grant.shared_at,
            expires_at=grant.expires_at
        ))
    
    # Get outbound grants (they can view our data)
    outbound_query = db.query(AdoptionDataShare).filter(
        AdoptionDataShare.source_customer_id == customer_id
    ).all()
    
    outbound_grants = []
    for grant in outbound_query:
        target = db.query(Customer).filter(
            Customer.customer_id == grant.target_customer_id
        ).first()
        outbound_grants.append(AdoptionGrantInfo(
            id=grant.id,
            customer_id=grant.target_customer_id,
            customer_name=target.display_name or target.name if target else None,
            is_enabled=grant.is_enabled,
            share_level=grant.share_level,
            granted_at=grant.shared_at,
            expires_at=grant.expires_at
        ))
    
    return TenantAdoptionAccessResponse(
        inbound_grants=inbound_grants,
        outbound_grants=outbound_grants
    )


@router.put("/adoption-access/{grant_id}")
async def toggle_adoption_grant(
    grant_id: int,
    request: AdoptionGrantToggleRequest,
    current_user = Depends(auth_middleware.require_any_permission(
        ["adoption:manage_sharing", "platform:admin"]
    )),
    db: Session = Depends(get_db)
):
    """
    Toggle an adoption grant on/off.
    
    Tenant admins can only toggle grants that affect their tenant:
    - Inbound grants: Enable/disable receiving another tenant's data
    - Outbound grants: Enable/disable sharing our data with another tenant
    """
    from src.models.adoption import AdoptionDataShare
    
    customer_id = current_user.customer_id
    
    # Find the grant
    grant = db.query(AdoptionDataShare).filter(
        AdoptionDataShare.id == grant_id
    ).first()
    
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adoption grant not found"
        )
    
    # Verify the grant affects this tenant
    if grant.source_customer_id != customer_id and grant.target_customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify grants that affect your tenant"
        )
    
    # Update the grant
    grant.is_enabled = request.is_enabled
    db.commit()
    
    return {
        "success": True,
        "grant_id": grant_id,
        "is_enabled": grant.is_enabled,
        "message": f"Adoption grant {'enabled' if grant.is_enabled else 'disabled'}"
    }
