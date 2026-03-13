"""
API schemas package for the AI Enablement Platform.
Exports Pydantic models for request/response validation.
"""

from .admin import (
    SystemHealthStatus,
    UserActivityMetrics,
    DocumentMetrics,
    AIUsageMetrics,
    RecentActivityItem,
    DashboardOverviewResponse
)
from .documents import (
    DocumentStatsResponse,
    RecentDocumentInfo,
    RecentDocumentsResponse
)
from .users import (
    UserListItem,
    PaginationInfo,
    UsersListResponse
)
from .tenant_admin import (
    # Platform Features
    PlatformFeatureResponse,
    PlatformFeatureWithPermissions,
    FeaturePermissionResponse,
    PermissionCategory,
    AvailablePermissionsResponse,
    # Feature Allocations
    FeatureAllocationRequest,
    FeatureAllocationResponse,
    TenantFeaturesUpdateRequest,
    TenantFeaturesResponse,
    # Tenant Roles
    TenantRoleCreate,
    TenantRoleUpdate,
    TenantRoleResponse,
    TenantRoleWithPermissions,
    RolePermissionsUpdateRequest,
    # User Roles
    UserRoleAssignment,
    UserRolesUpdateRequest,
    # User Invites
    UserInviteCreate,
    UserInviteResponse,
    UserInviteListResponse,
    InviteValidationResponse,
    InviteAcceptRequest,
    # Tenant Users
    TenantUserCreate,
    TenantUserUpdate,
    TenantUserResponse,
    TenantUserListResponse,
    # Platform Admin
    PlatformAdminCreate,
    PlatformAdminResponse,
    PlatformAdminListResponse,
    # Tenant Management
    TenantCreate,
    TenantResponse,
    TenantWithAdmin,
    TenantListResponse,
    TenantUpdate,
)
from .hr import (
    # Enums
    EmploymentStatus,
    EmploymentType,
    WorkLocation,
    ChangeType,
    ProficiencyLevel,
    TrainingStatus,
    ReviewStatus,
    TimeOffStatus,
    # Department schemas
    DepartmentCreateRequest,
    DepartmentUpdateRequest,
    DepartmentInfo,
    DepartmentResponse,
    DepartmentListResponse,
    # Position schemas
    PositionCreateRequest,
    PositionUpdateRequest,
    PositionInfo,
    PositionResponse,
    # Employee schemas
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    EmployeeInfo,
    EmployeeResponse,
    EmployeeDetailResponse,
    EmployeeListResponse,
    # Skill schemas
    SkillCreateRequest,
    SkillResponse,
    SkillListResponse,
    EmployeeSkillCreateRequest,
    EmployeeSkillResponse,
    # Performance review schemas
    PerformanceReviewCreateRequest,
    PerformanceReviewResponse,
    # Training schemas
    TrainingProgramCreateRequest,
    TrainingProgramResponse,
    TrainingProgramListResponse,
    EmployeeTrainingRecordCreateRequest,
    EmployeeTrainingRecordResponse,
)

__all__ = [
    # Admin schemas
    "SystemHealthStatus",
    "UserActivityMetrics",
    "DocumentMetrics",
    "AIUsageMetrics",
    "RecentActivityItem",
    "DashboardOverviewResponse",
    # Document schemas
    "DocumentStatsResponse",
    "RecentDocumentInfo",
    "RecentDocumentsResponse",
    # User schemas
    "UserListItem",
    "PaginationInfo",
    "UsersListResponse",
    # HR Enums
    "EmploymentStatus",
    "EmploymentType",
    "WorkLocation",
    "ChangeType",
    "ProficiencyLevel",
    "TrainingStatus",
    "ReviewStatus",
    "TimeOffStatus",
    # HR Department schemas
    "DepartmentCreateRequest",
    "DepartmentUpdateRequest",
    "DepartmentInfo",
    "DepartmentResponse",
    "DepartmentListResponse",
    # HR Position schemas
    "PositionCreateRequest",
    "PositionUpdateRequest",
    "PositionInfo",
    "PositionResponse",
    # HR Employee schemas
    "EmployeeCreateRequest",
    "EmployeeUpdateRequest",
    "EmployeeInfo",
    "EmployeeResponse",
    "EmployeeDetailResponse",
    "EmployeeListResponse",
    # HR Skill schemas
    "SkillCreateRequest",
    "SkillResponse",
    "SkillListResponse",
    "EmployeeSkillCreateRequest",
    "EmployeeSkillResponse",
    # HR Performance review schemas
    "PerformanceReviewCreateRequest",
    "PerformanceReviewResponse",
    # HR Training schemas
    "TrainingProgramCreateRequest",
    "TrainingProgramResponse",
    "TrainingProgramListResponse",
    "EmployeeTrainingRecordCreateRequest",
    "EmployeeTrainingRecordResponse",
    # Tenant Admin - Platform Features
    "PlatformFeatureResponse",
    "PlatformFeatureWithPermissions",
    "FeaturePermissionResponse",
    "PermissionCategory",
    "AvailablePermissionsResponse",
    # Tenant Admin - Feature Allocations
    "FeatureAllocationRequest",
    "FeatureAllocationResponse",
    "TenantFeaturesUpdateRequest",
    "TenantFeaturesResponse",
    # Tenant Admin - Roles
    "TenantRoleCreate",
    "TenantRoleUpdate",
    "TenantRoleResponse",
    "TenantRoleWithPermissions",
    "RolePermissionsUpdateRequest",
    # Tenant Admin - User Roles
    "UserRoleAssignment",
    "UserRolesUpdateRequest",
    # Tenant Admin - Invites
    "UserInviteCreate",
    "UserInviteResponse",
    "UserInviteListResponse",
    "InviteValidationResponse",
    "InviteAcceptRequest",
    # Tenant Admin - Users
    "TenantUserCreate",
    "TenantUserUpdate",
    "TenantUserResponse",
    "TenantUserListResponse",
    # Tenant Admin - Platform Admin
    "PlatformAdminCreate",
    "PlatformAdminResponse",
    "PlatformAdminListResponse",
    # Tenant Admin - Tenants
    "TenantCreate",
    "TenantResponse",
    "TenantWithAdmin",
    "TenantListResponse",
    "TenantUpdate",
]

