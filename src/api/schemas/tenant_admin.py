"""
AI Enablement Platform - Multi-Tenant Admin API Schemas

Pydantic models for the multi-tenant administration API.
"""

from datetime import datetime
from typing import Optional, List, Set
from pydantic import BaseModel, Field, EmailStr


# ============================================================================
# PLATFORM FEATURES
# ============================================================================

class PlatformFeatureBase(BaseModel):
    """Base schema for platform features."""
    feature_key: str = Field(..., description="Unique feature identifier", example="talent_intelligence")
    display_name: str = Field(..., description="Human-readable feature name", example="Talent Intelligence")
    description: Optional[str] = Field(None, description="Feature description")
    category: Optional[str] = Field(None, description="Feature category", example="intelligence")
    icon: Optional[str] = Field(None, description="Heroicon name", example="Users")


class PlatformFeatureResponse(PlatformFeatureBase):
    """Platform feature response schema."""
    id: int
    sort_order: int
    is_active: bool
    permission_count: Optional[int] = Field(None, description="Number of permissions in this feature")
    
    class Config:
        from_attributes = True


class PlatformFeatureWithPermissions(PlatformFeatureResponse):
    """Platform feature with its permissions."""
    permissions: List["FeaturePermissionResponse"] = []


# ============================================================================
# FEATURE PERMISSIONS
# ============================================================================

class FeaturePermissionBase(BaseModel):
    """Base schema for feature permissions."""
    permission_key: str = Field(..., description="Permission key", example="documents:create")
    display_name: str = Field(..., description="Human-readable name", example="Create Documents")
    description: Optional[str] = Field(None, description="Permission description")


class FeaturePermissionResponse(FeaturePermissionBase):
    """Feature permission response schema."""
    id: int
    feature_id: int
    sort_order: int
    
    class Config:
        from_attributes = True


class PermissionCategory(BaseModel):
    """Permission category for UI display."""
    id: str = Field(..., description="Category/feature key")
    display_name: str
    icon: Optional[str] = None
    is_enabled: bool = Field(True, description="Whether feature is allocated to tenant")
    disabled_reason: Optional[str] = Field(None, description="Reason if disabled")
    permissions: List[FeaturePermissionResponse] = []


class AvailablePermissionsResponse(BaseModel):
    """Available permissions grouped by category."""
    categories: List[PermissionCategory]


# ============================================================================
# TENANT FEATURE ALLOCATIONS
# ============================================================================

class FeatureAllocationRequest(BaseModel):
    """Request to allocate a feature to a tenant."""
    feature_id: int
    is_enabled: bool = True
    expires_at: Optional[datetime] = None
    usage_limit: Optional[int] = None
    notes: Optional[str] = None


class FeatureAllocationResponse(BaseModel):
    """Feature allocation response."""
    id: int
    customer_id: str
    feature_id: int
    feature_key: str
    feature_display_name: str
    is_enabled: bool
    allocated_at: datetime
    expires_at: Optional[datetime]
    usage_limit: Optional[int]
    notes: Optional[str]
    
    class Config:
        from_attributes = True


class TenantFeaturesUpdateRequest(BaseModel):
    """Request to update all feature allocations for a tenant."""
    feature_ids: List[int] = Field(..., description="List of feature IDs to enable")


class TenantFeaturesResponse(BaseModel):
    """All features with allocation status for a tenant."""
    customer_id: str
    allocations: List[FeatureAllocationResponse]
    available_features: List[PlatformFeatureResponse]


# ============================================================================
# TENANT ROLES
# ============================================================================

class TenantRoleBase(BaseModel):
    """Base schema for tenant roles."""
    role_name: str = Field(..., min_length=1, max_length=100, description="Role name")
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class TenantRoleCreate(TenantRoleBase):
    """Request to create a new tenant role."""
    permission_ids: List[int] = Field(default=[], description="Permission IDs to assign")


class TenantRoleUpdate(BaseModel):
    """Request to update a tenant role."""
    role_name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TenantRoleResponse(TenantRoleBase):
    """Tenant role response schema."""
    id: int
    customer_id: str
    is_system_role: bool
    is_active: bool
    permission_count: int = 0
    user_count: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TenantRoleWithPermissions(TenantRoleResponse):
    """Tenant role with its permission details."""
    permissions: List[FeaturePermissionResponse] = []
    permission_ids: List[int] = []


class RolePermissionsUpdateRequest(BaseModel):
    """Request to update role permissions (bulk)."""
    permission_ids: List[int] = Field(..., description="Complete list of permission IDs for role")


# ============================================================================
# TENANT USER ROLES
# ============================================================================

class UserRoleAssignment(BaseModel):
    """Role assignment for a user."""
    role_id: int
    role_name: str
    display_name: Optional[str]
    assigned_at: datetime
    
    class Config:
        from_attributes = True


class UserRolesUpdateRequest(BaseModel):
    """Request to update user roles."""
    role_ids: List[int] = Field(..., description="List of role IDs to assign")


# ============================================================================
# USER INVITES
# ============================================================================

class UserInviteCreate(BaseModel):
    """Request to create a user invite."""
    email: EmailStr = Field(..., description="Email address to invite")
    full_name: Optional[str] = Field(None, max_length=255)
    role_ids: Optional[List[int]] = Field(default=[], description="Roles to pre-assign")
    expires_in_days: int = Field(default=7, ge=1, le=30, description="Days until invite expires")


class UserInviteResponse(BaseModel):
    """User invite response schema."""
    id: int
    customer_id: str
    email: str
    full_name: Optional[str]
    invite_token: str
    invite_url: Optional[str] = Field(None, description="Full invite URL")
    role_ids: Optional[List[int]]
    status: str
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserInviteListResponse(BaseModel):
    """List of user invites."""
    invites: List[UserInviteResponse]
    total: int


class InviteValidationResponse(BaseModel):
    """Response when validating an invite token."""
    valid: bool
    email: Optional[str] = None
    full_name: Optional[str] = None
    customer_name: Optional[str] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None


class InviteAcceptRequest(BaseModel):
    """Request to accept an invite and set password."""
    password: str = Field(..., min_length=8, description="User's new password")
    confirm_password: str = Field(..., description="Password confirmation")


# ============================================================================
# TENANT USERS
# ============================================================================

class TenantUserBase(BaseModel):
    """Base schema for tenant users."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)


class TenantUserCreate(TenantUserBase):
    """Request to create a tenant user directly (with password)."""
    password: str = Field(..., min_length=8)
    role_ids: List[int] = Field(default=[], description="Roles to assign")


class TenantUserUpdate(BaseModel):
    """Request to update a tenant user."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    department: Optional[str] = Field(None, max_length=100)
    team: Optional[str] = Field(None, max_length=100)


class TenantUserResponse(BaseModel):
    """Tenant user response schema."""
    id: int
    email: str
    username: str
    full_name: Optional[str]
    customer_id: str
    is_active: bool
    department: Optional[str]
    team: Optional[str]
    last_login: Optional[datetime]
    created_at: datetime
    roles: List[UserRoleAssignment] = []
    
    class Config:
        from_attributes = True


class TenantUserListResponse(BaseModel):
    """List of tenant users."""
    users: List[TenantUserResponse]
    total: int


# ============================================================================
# PLATFORM ADMIN
# ============================================================================

class PlatformAdminBase(BaseModel):
    """Base schema for platform admin."""
    admin_level: str = Field(default="admin", description="admin or super_admin")
    can_create_tenants: bool = True
    can_allocate_features: bool = True
    can_manage_platform_admins: bool = False
    can_impersonate: bool = False


class PlatformAdminCreate(PlatformAdminBase):
    """Request to create a platform admin."""
    user_id: int = Field(..., description="User ID to promote to platform admin")


class PlatformAdminResponse(PlatformAdminBase):
    """Platform admin response schema."""
    id: int
    user_id: int
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class PlatformAdminListResponse(BaseModel):
    """List of platform admins."""
    admins: List[PlatformAdminResponse]
    total: int


# ============================================================================
# TENANT MANAGEMENT (Platform Admin)
# ============================================================================

class TenantCreate(BaseModel):
    """Request to create a new tenant."""
    customer_id: str = Field(..., min_length=3, max_length=100, pattern="^[a-z0-9-]+$",
                            description="Unique tenant identifier (slug)")
    name: str = Field(..., min_length=1, max_length=255, description="Company name")
    display_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[EmailStr] = None
    
    # Admin user
    admin_email: EmailStr = Field(..., description="Tenant admin email")
    admin_name: Optional[str] = Field(None, max_length=255)
    
    # Feature allocation
    feature_ids: List[int] = Field(default=[], description="Features to allocate")
    
    # Subscription
    subscription_tier: str = Field(default="basic", description="Subscription tier")


class TenantResponse(BaseModel):
    """Tenant response schema."""
    id: int
    customer_id: str
    name: str
    display_name: Optional[str]
    contact_email: Optional[str]
    is_active: bool
    subscription_tier: str
    current_users: int
    max_users: int
    created_at: datetime
    updated_at: datetime
    # Admin info
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    admin_status: Optional[str] = None  # 'active', 'pending_invite', 'no_admin'
    # Deactivation info
    deactivated_at: Optional[datetime] = None
    deactivation_reason: Optional[str] = None
    deactivated_by_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class TenantDeactivateRequest(BaseModel):
    """Request to deactivate a tenant."""
    confirmation: str = Field(..., description="Must be 'DEACTIVATE' to confirm")
    reason: str = Field(..., min_length=10, max_length=1000, description="Reason for deactivation")


class TenantReactivateRequest(BaseModel):
    """Request to reactivate a tenant."""
    confirmation: str = Field(..., description="Must be 'REACTIVATE' to confirm")


class TenantWithAdmin(TenantResponse):
    """Tenant with admin invite info."""
    admin_invite_url: Optional[str] = None
    allocated_features: List[str] = []


class TenantListResponse(BaseModel):
    """List of tenants."""
    tenants: List[TenantResponse]
    total: int


class TenantUpdate(BaseModel):
    """Request to update a tenant."""
    name: Optional[str] = Field(None, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    subscription_tier: Optional[str] = None
    max_users: Optional[int] = Field(None, ge=1)
    max_documents: Optional[int] = Field(None, ge=1)


# Resolve forward references
PlatformFeatureWithPermissions.model_rebuild()

