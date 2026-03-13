"""
AI Enablement Platform - Platform Admin API Routes

API endpoints for platform-level administration (Eliza team only):
- Tenant management
- Feature allocation
- Platform admin management
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import structlog

from src.models.database import get_db

logger = structlog.get_logger(__name__)
from src.models.auth import User
from src.middleware.authorization import get_current_user
from src.services.tenant_admin_service import TenantAdminService, PlatformAdminService
from src.services.tenant_sso_settings_service import PlatformSSOPolicyService
from src.services.audit_service import audit_service, AuditAction
from src.api.schemas.sso_settings import (
    PlatformSSOPolicyResponse,
    PlatformSSOPolicyUpdateRequest,
)
from src.api.schemas.tenant_admin import (
    # Features
    PlatformFeatureResponse,
    PlatformFeatureWithPermissions,
    FeaturePermissionResponse,
    FeatureAllocationResponse,
    TenantFeaturesUpdateRequest,
    TenantFeaturesResponse,
    # Tenants
    TenantCreate,
    TenantResponse,
    TenantWithAdmin,
    TenantListResponse,
    TenantUpdate,
    TenantDeactivateRequest,
    TenantReactivateRequest,
    # Platform Admins
    PlatformAdminCreate,
    PlatformAdminResponse,
    PlatformAdminListResponse,
)

router = APIRouter(prefix="/platform-admin", tags=["Platform Admin"])


def get_services(db: Session = Depends(get_db)):
    """Dependency to get services."""
    return {
        "platform": PlatformAdminService(db),
        "tenant": TenantAdminService(db)
    }


def require_platform_admin(
    current_user = Depends(get_current_user),
    services: dict = Depends(get_services)
):
    """Require user to be a platform admin."""
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    if not services["platform"].is_platform_admin(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required"
        )
    return current_user


def require_super_admin(
    current_user = Depends(get_current_user),
    services: dict = Depends(get_services)
):
    """Require user to be a super admin."""
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    admin = services["platform"].get_platform_admin(user_id)
    if not admin or not admin.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user


def require_job_access(
    current_user = Depends(get_current_user),
    services: dict = Depends(get_services)
):
    """Require platform admin OR adoption:manage_jobs permission."""
    if current_user.is_superuser:
        return current_user
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    if services["platform"].is_platform_admin(user_id):
        return current_user
    if current_user.has_permission('adoption:manage_jobs'):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Platform admin access or adoption:manage_jobs permission required"
    )


# =============================================================================
# PLATFORM FEATURES
# =============================================================================

@router.get("/features", response_model=List[PlatformFeatureWithPermissions])
async def list_features(
    include_inactive: bool = Query(False, description="Include inactive features"),
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """List all platform features with their permissions."""
    features = services["tenant"].get_all_features(include_inactive)
    
    result = []
    for feature in features:
        feature_with_perms = services["tenant"].get_feature_with_permissions(feature.id)
        result.append(PlatformFeatureWithPermissions(
            id=feature.id,
            feature_key=feature.feature_key,
            display_name=feature.display_name,
            description=feature.description,
            category=feature.category,
            icon=feature.icon,
            sort_order=feature.sort_order,
            is_active=feature.is_active,
            permission_count=len(feature_with_perms.permissions) if feature_with_perms else 0,
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
            ]
        ))
    
    return result


# =============================================================================
# PLATFORM AUTHENTICATION GOVERNANCE
# =============================================================================

@router.get("/auth/sso-policy", response_model=PlatformSSOPolicyResponse)
async def get_platform_sso_policy(
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Get platform-wide SSO governance policy."""
    _ = current_user  # explicit for dependency-driven auth
    service = PlatformSSOPolicyService(db)
    return service.get_policy()


@router.put("/auth/sso-policy", response_model=PlatformSSOPolicyResponse)
async def update_platform_sso_policy(
    request: PlatformSSOPolicyUpdateRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Update platform-wide SSO governance policy."""
    current_user_id = current_user.user_id if hasattr(current_user, "user_id") else current_user.id
    service = PlatformSSOPolicyService(db)
    updated = service.update_policy(request)

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user_id,
        resource_type="platform_sso_policy",
        resource_id="global",
        additional_context={
            "global_sso_enabled": updated.global_sso_enabled,
            "allowed_provider_types": [p.value for p in updated.allowed_provider_types],
            "allow_tenant_enforced_mode": updated.allow_tenant_enforced_mode,
            "require_domain_verification_for_enforced_mode": updated.require_domain_verification_for_enforced_mode,
            "break_glass_enabled": updated.break_glass_enabled,
            "break_glass_allowed_user_emails": updated.break_glass_allowed_user_emails,
            "jit_provisioning_default": updated.jit_provisioning_default,
            "default_password_policy_profile": updated.default_password_policy_profile,
        },
    )

    return updated


# =============================================================================
# TENANT MANAGEMENT
# =============================================================================

@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    include_inactive: bool = Query(False, description="Include inactive tenants"),
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services),
    db: Session = Depends(get_db)
):
    """List all tenants."""
    from src.models.auth import User as UserModel
    
    tenants = services["platform"].get_all_tenants(include_inactive)
    
    tenant_responses = []
    for t in tenants:
        # Get admin info for each tenant
        admin_info = services["tenant"].get_tenant_admin_info(t.customer_id)
        
        # Get deactivated by user name if applicable
        deactivated_by_name = None
        if t.deactivated_by:
            deactivated_by_user = db.query(UserModel).filter(UserModel.id == t.deactivated_by).first()
            if deactivated_by_user:
                deactivated_by_name = deactivated_by_user.full_name or deactivated_by_user.username
        
        tenant_responses.append(
            TenantResponse(
                id=t.id,
                customer_id=t.customer_id,
                name=t.name,
                display_name=t.display_name,
                contact_email=t.contact_email,
                is_active=t.is_active,
                subscription_tier=t.subscription_tier,
                current_users=t.current_users,
                max_users=t.max_users,
                created_at=t.created_at,
                updated_at=t.updated_at,
                admin_name=admin_info.get("admin_name"),
                admin_email=admin_info.get("admin_email"),
                admin_status=admin_info.get("admin_status"),
                deactivated_at=t.deactivated_at,
                deactivation_reason=t.deactivation_reason,
                deactivated_by_name=deactivated_by_name
            )
        )
    
    return TenantListResponse(
        tenants=tenant_responses,
        total=len(tenant_responses)
    )


@router.post("/tenants", response_model=TenantWithAdmin, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """
    Create a new tenant with admin invite.
    
    This creates:
    - The customer record
    - Feature allocations
    - Default Admin and Viewer roles
    - An invite for the tenant admin
    """
    # Check if customer_id already exists
    existing = services["platform"].get_tenant(tenant_data.customer_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with customer_id '{tenant_data.customer_id}' already exists"
        )
    
    # Validate feature IDs
    if tenant_data.feature_ids:
        all_features = services["tenant"].get_all_features()
        all_feature_ids = {f.id for f in all_features}
        invalid_ids = set(tenant_data.feature_ids) - all_feature_ids
        if invalid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid feature IDs: {invalid_ids}"
            )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    customer, admin_invite = services["platform"].create_tenant(
        tenant_data=tenant_data,
        created_by=current_user_id
    )
    
    # Get allocated feature keys
    allocations = services["tenant"].get_tenant_allocations(customer.customer_id)
    allocated_features = [a.feature.feature_key for a in allocations if a.is_enabled]
    
    # Generate invite URL
    from src.core.config import get_settings
    settings = get_settings()
    base_url = settings.frontend_url or "https://app.eliza.ai"
    invite_url = f"{base_url}/accept-invite?token={admin_invite.invite_token}"
    
    return TenantWithAdmin(
        id=customer.id,
        customer_id=customer.customer_id,
        name=customer.name,
        display_name=customer.display_name,
        contact_email=customer.contact_email,
        is_active=customer.is_active,
        subscription_tier=customer.subscription_tier,
        current_users=customer.current_users,
        max_users=customer.max_users,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        admin_invite_url=invite_url,
        allocated_features=allocated_features
    )


@router.get("/tenants/{customer_id}", response_model=TenantWithAdmin)
async def get_tenant(
    customer_id: str,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """Get a tenant by customer_id."""
    customer = services["platform"].get_tenant(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Get allocated features
    allocations = services["tenant"].get_tenant_allocations(customer_id)
    allocated_features = [a.feature.feature_key for a in allocations if a.is_enabled]
    
    return TenantWithAdmin(
        id=customer.id,
        customer_id=customer.customer_id,
        name=customer.name,
        display_name=customer.display_name,
        contact_email=customer.contact_email,
        is_active=customer.is_active,
        subscription_tier=customer.subscription_tier,
        current_users=customer.current_users,
        max_users=customer.max_users,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        admin_invite_url=None,
        allocated_features=allocated_features
    )


@router.put("/tenants/{customer_id}", response_model=TenantResponse)
async def update_tenant(
    customer_id: str,
    update_data: TenantUpdate,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """Update a tenant."""
    customer = services["platform"].update_tenant(
        customer_id,
        **update_data.model_dump(exclude_unset=True)
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return TenantResponse(
        id=customer.id,
        customer_id=customer.customer_id,
        name=customer.name,
        display_name=customer.display_name,
        contact_email=customer.contact_email,
        is_active=customer.is_active,
        subscription_tier=customer.subscription_tier,
        current_users=customer.current_users,
        max_users=customer.max_users,
        created_at=customer.created_at,
        updated_at=customer.updated_at
    )


@router.delete("/tenants/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_legacy(
    customer_id: str,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """
    Legacy endpoint - deactivate a tenant (soft delete).
    Use POST /tenants/{customer_id}/deactivate for proper deactivation with reason.
    """
    success = services["platform"].deactivate_tenant(customer_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )


@router.post("/tenants/{customer_id}/deactivate", response_model=TenantResponse)
async def deactivate_tenant(
    customer_id: str,
    request: TenantDeactivateRequest,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services),
    db: Session = Depends(get_db)
):
    """
    Deactivate a tenant with confirmation and reason.
    
    Requires:
    - confirmation: Must type 'DEACTIVATE' exactly
    - reason: Explanation for deactivation (min 10 characters)
    
    This action:
    - Prevents all users in the tenant from accessing data
    - Logs the deactivation with full audit trail
    - Can be reversed with the reactivate endpoint
    """
    import logging
    from datetime import datetime, timezone
    from src.models.customer import Customer
    from src.models.auth import User as UserModel
    
    logger = logging.getLogger(__name__)
    
    # Validate confirmation
    if request.confirmation != "DEACTIVATE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation must be 'DEACTIVATE' (exact match required)"
        )
    
    # Get the tenant
    customer = services["platform"].get_tenant(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check if already deactivated
    if not customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant is already deactivated"
        )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    
    # Update the tenant
    customer.is_active = False
    customer.deactivated_at = datetime.now(timezone.utc)
    customer.deactivated_by = current_user_id
    customer.deactivation_reason = request.reason
    db.commit()
    db.refresh(customer)
    
    # Get deactivated by user info
    deactivated_by_user = db.query(UserModel).filter(UserModel.id == current_user_id).first()
    deactivated_by_name = deactivated_by_user.full_name or deactivated_by_user.username if deactivated_by_user else None
    
    # Log the deactivation with extensive audit info
    logger.warning(
        f"TENANT DEACTIVATION: customer_id={customer_id}, "
        f"tenant_name={customer.name}, "
        f"deactivated_by_user_id={current_user_id}, "
        f"deactivated_by_name={deactivated_by_name}, "
        f"reason={request.reason}"
    )
    
    # Get admin info
    admin_info = services["tenant"].get_tenant_admin_info(customer_id)
    
    return TenantResponse(
        id=customer.id,
        customer_id=customer.customer_id,
        name=customer.name,
        display_name=customer.display_name,
        contact_email=customer.contact_email,
        is_active=customer.is_active,
        subscription_tier=customer.subscription_tier,
        current_users=customer.current_users,
        max_users=customer.max_users,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        admin_name=admin_info.get("admin_name"),
        admin_email=admin_info.get("admin_email"),
        admin_status=admin_info.get("admin_status"),
        deactivated_at=customer.deactivated_at,
        deactivation_reason=customer.deactivation_reason,
        deactivated_by_name=deactivated_by_name
    )


@router.post("/tenants/{customer_id}/reactivate", response_model=TenantResponse)
async def reactivate_tenant(
    customer_id: str,
    request: TenantReactivateRequest,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services),
    db: Session = Depends(get_db)
):
    """
    Reactivate a previously deactivated tenant.
    
    Requires:
    - confirmation: Must type 'REACTIVATE' exactly
    """
    import logging
    from src.models.customer import Customer
    from src.models.auth import User as UserModel
    
    logger = logging.getLogger(__name__)
    
    # Validate confirmation
    if request.confirmation != "REACTIVATE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation must be 'REACTIVATE' (exact match required)"
        )
    
    # Get the tenant
    customer = services["platform"].get_tenant(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check if already active
    if customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant is already active"
        )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    reactivated_by_user = db.query(UserModel).filter(UserModel.id == current_user_id).first()
    reactivated_by_name = reactivated_by_user.full_name or reactivated_by_user.username if reactivated_by_user else None
    
    # Log the reactivation
    logger.warning(
        f"TENANT REACTIVATION: customer_id={customer_id}, "
        f"tenant_name={customer.name}, "
        f"reactivated_by_user_id={current_user_id}, "
        f"reactivated_by_name={reactivated_by_name}, "
        f"previous_deactivation_reason={customer.deactivation_reason}"
    )
    
    # Update the tenant
    customer.is_active = True
    customer.deactivated_at = None
    customer.deactivated_by = None
    customer.deactivation_reason = None
    db.commit()
    db.refresh(customer)
    
    # Get admin info
    admin_info = services["tenant"].get_tenant_admin_info(customer_id)
    
    return TenantResponse(
        id=customer.id,
        customer_id=customer.customer_id,
        name=customer.name,
        display_name=customer.display_name,
        contact_email=customer.contact_email,
        is_active=customer.is_active,
        subscription_tier=customer.subscription_tier,
        current_users=customer.current_users,
        max_users=customer.max_users,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        admin_name=admin_info.get("admin_name"),
        admin_email=admin_info.get("admin_email"),
        admin_status=admin_info.get("admin_status"),
        deactivated_at=None,
        deactivation_reason=None,
        deactivated_by_name=None
    )


# =============================================================================
# TENANT FEATURE ALLOCATION
# =============================================================================

@router.get("/tenants/{customer_id}/features", response_model=List[FeatureAllocationResponse])
async def get_tenant_features(
    customer_id: str,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """Get all feature allocations for a tenant."""
    customer = services["platform"].get_tenant(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    allocations = services["tenant"].get_tenant_allocations(customer_id)
    
    return [
        FeatureAllocationResponse(
            id=a.id,
            customer_id=a.customer_id,
            feature_id=a.feature_id,
            feature_key=a.feature.feature_key,
            feature_display_name=a.feature.display_name,
            is_enabled=a.is_enabled,
            allocated_at=a.allocated_at,
            expires_at=a.expires_at,
            usage_limit=a.usage_limit,
            notes=a.notes
        )
        for a in allocations
    ]


@router.put("/tenants/{customer_id}/features", response_model=List[FeatureAllocationResponse])
async def update_tenant_features(
    customer_id: str,
    request: TenantFeaturesUpdateRequest,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """Update all feature allocations for a tenant (replaces existing)."""
    customer = services["platform"].get_tenant(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Validate feature IDs
    all_features = services["tenant"].get_all_features()
    all_feature_ids = {f.id for f in all_features}
    invalid_ids = set(request.feature_ids) - all_feature_ids
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid feature IDs: {invalid_ids}"
        )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    allocations = services["tenant"].update_tenant_features(
        customer_id=customer_id,
        feature_ids=request.feature_ids,
        allocated_by=current_user_id
    )
    
    return [
        FeatureAllocationResponse(
            id=a.id,
            customer_id=a.customer_id,
            feature_id=a.feature_id,
            feature_key=a.feature.feature_key,
            feature_display_name=a.feature.display_name,
            is_enabled=a.is_enabled,
            allocated_at=a.allocated_at,
            expires_at=a.expires_at,
            usage_limit=a.usage_limit,
            notes=a.notes
        )
        for a in allocations
        if a.is_enabled
    ]


@router.post("/tenants/{customer_id}/features/{feature_id}/enable", status_code=status.HTTP_201_CREATED)
async def enable_feature(
    customer_id: str,
    feature_id: int,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """Enable a feature for a tenant."""
    customer = services["platform"].get_tenant(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    services["tenant"].allocate_feature(
        customer_id=customer_id,
        feature_id=feature_id,
        allocated_by=current_user_id
    )
    
    return {"message": "Feature enabled"}


@router.post("/tenants/{customer_id}/features/{feature_id}/disable", status_code=status.HTTP_200_OK)
async def disable_feature(
    customer_id: str,
    feature_id: int,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """Disable a feature for a tenant."""
    customer = services["platform"].get_tenant(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    services["tenant"].deallocate_feature(customer_id, feature_id)
    
    return {"message": "Feature disabled"}


# =============================================================================
# TENANT ADMIN MANAGEMENT
# =============================================================================

class UpdateTenantAdminRequest(BaseModel):
    """Request to update tenant admin."""
    admin_email: EmailStr
    admin_name: Optional[str] = None


class TenantAdminResponse(BaseModel):
    """Response for tenant admin operations."""
    message: str
    invite_url: Optional[str] = None


@router.post("/tenants/{customer_id}/admin", response_model=TenantAdminResponse)
async def update_tenant_admin(
    customer_id: str,
    request: UpdateTenantAdminRequest,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """
    Update or create a new tenant admin.
    
    This will:
    1. Revoke any existing pending admin invites
    2. Create a new admin invite for the specified email
    """
    customer = services["platform"].get_tenant(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    
    invite = services["platform"].update_tenant_admin(
        customer_id=customer_id,
        admin_email=request.admin_email,
        admin_name=request.admin_name,
        created_by=current_user_id
    )
    
    from src.core.config import get_settings
    settings = get_settings()
    invite_url = f"{settings.frontend_url}/accept-invite?token={invite.invite_token}"
    
    return TenantAdminResponse(
        message="Admin invite created successfully",
        invite_url=invite_url
    )


@router.post("/tenants/{customer_id}/resend-invite", response_model=TenantAdminResponse)
async def resend_admin_invite(
    customer_id: str,
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """
    Resend the admin invite for a tenant.
    
    Creates a new invite token and returns the new invite URL.
    """
    customer = services["platform"].get_tenant(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    
    invite = services["platform"].resend_admin_invite(
        customer_id=customer_id,
        created_by=current_user_id
    )
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending admin invite found for this tenant"
        )
    
    from src.core.config import get_settings
    settings = get_settings()
    invite_url = f"{settings.frontend_url}/accept-invite?token={invite.invite_token}"
    
    return TenantAdminResponse(
        message="Admin invite resent successfully",
        invite_url=invite_url
    )


# =============================================================================
# ALL USERS (for selection)
# =============================================================================

class UserBasicResponse(BaseModel):
    """Basic user info for selection."""
    id: int
    email: str
    username: str
    full_name: Optional[str]
    customer_id: Optional[str]
    is_active: bool


class AllUsersListResponse(BaseModel):
    """List of all users."""
    users: List[UserBasicResponse]
    total: int


@router.get("/users", response_model=AllUsersListResponse)
async def list_all_users(
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services),
    db: Session = Depends(get_db)
):
    """List all users in the system (for platform admin selection)."""
    from src.models.auth import User as UserModel
    
    users = db.query(UserModel).filter(UserModel.is_active == True).all()
    
    return AllUsersListResponse(
        users=[
            UserBasicResponse(
                id=u.id,
                email=u.email,
                username=u.username,
                full_name=u.full_name,
                customer_id=u.customer_id,
                is_active=u.is_active
            )
            for u in users
        ],
        total=len(users)
    )


# =============================================================================
# PLATFORM ADMINS
# =============================================================================

@router.get("/admins", response_model=PlatformAdminListResponse)
async def list_platform_admins(
    current_user: User = Depends(require_platform_admin),
    services: dict = Depends(get_services)
):
    """List all platform admins."""
    admins = services["platform"].get_all_platform_admins()
    
    return PlatformAdminListResponse(
        admins=[
            PlatformAdminResponse(
                id=a.id,
                user_id=a.user_id,
                user_email=a.user.email if a.user else None,
                user_name=a.user.full_name if a.user else None,
                admin_level=a.admin_level,
                can_create_tenants=a.can_create_tenants,
                can_allocate_features=a.can_allocate_features,
                can_manage_platform_admins=a.can_manage_platform_admins,
                can_impersonate=a.can_impersonate,
                is_active=a.is_active,
                created_at=a.created_at
            )
            for a in admins
        ],
        total=len(admins)
    )


@router.post("/admins", response_model=PlatformAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_platform_admin(
    admin_data: PlatformAdminCreate,
    current_user: User = Depends(require_super_admin),
    services: dict = Depends(get_services)
):
    """Create a new platform admin (super admin only)."""
    # Check if user already is a platform admin
    existing = services["platform"].get_platform_admin(admin_data.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a platform admin"
        )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    admin = services["platform"].create_platform_admin(
        user_id=admin_data.user_id,
        admin_level=admin_data.admin_level,
        created_by=current_user_id,
        can_create_tenants=admin_data.can_create_tenants,
        can_allocate_features=admin_data.can_allocate_features,
        can_manage_platform_admins=admin_data.can_manage_platform_admins,
        can_impersonate=admin_data.can_impersonate
    )
    
    return PlatformAdminResponse(
        id=admin.id,
        user_id=admin.user_id,
        user_email=admin.user.email if admin.user else None,
        user_name=admin.user.full_name if admin.user else None,
        admin_level=admin.admin_level,
        can_create_tenants=admin.can_create_tenants,
        can_allocate_features=admin.can_allocate_features,
        can_manage_platform_admins=admin.can_manage_platform_admins,
        can_impersonate=admin.can_impersonate,
        is_active=admin.is_active,
        created_at=admin.created_at
    )


@router.delete("/admins/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_platform_admin(
    user_id: int,
    current_user: User = Depends(require_super_admin),
    services: dict = Depends(get_services)
):
    """Remove a platform admin (super admin only)."""
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    if user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself as platform admin"
        )
    
    success = services["platform"].remove_platform_admin(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform admin not found"
        )


# =============================================================================
# SHARED AI PROVIDERS
# =============================================================================

from src.models.provider_config import (
    PlatformProviderResponse,
    PlatformProviderListResponse,
    PlatformProviderCreate,
    ProviderSharingUpdate,
    SharedTenantInfo,
    ProviderType,
    ProviderConnectionTestRequest,
    ProviderConnectionTestResponse,
)
from src.models.customer import CustomerAIProvider, SharedAIProvider, Customer
from src.services.provider_service import ProviderService
import os


def get_platform_customer_id() -> str:
    """
    Get the platform customer_id for platform-level assets.
    
    Platform AI Providers are owned by 'platform' customer_id,
    making them distinct from tenant-specific providers.
    """
    return 'platform'


@router.get("/ai-providers", response_model=PlatformProviderListResponse)
async def list_platform_providers(
    filter_global: Optional[bool] = Query(None, description="Filter by global status"),
    filter_tenant_id: Optional[str] = Query(None, description="Filter by tenant access"),
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    List all AI provider configurations from the platform admin's tenant.
    
    These providers can be shared with other tenants either globally or selectively.
    Platform admins see providers from their own tenant (the tenant they belong to).
    """
    # Use the current user's customer_id (platform admin's tenant)
    platform_customer_id = get_platform_customer_id()
    
    # Query providers from platform admin's tenant
    query = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.customer_id == platform_customer_id
    )
    
    # Apply filters
    if filter_global is True:
        query = query.filter(CustomerAIProvider.is_global_shared == True)
    elif filter_global is False:
        query = query.filter(CustomerAIProvider.is_global_shared == False)
    
    providers = query.all()
    
    # Build response with sharing info
    responses = []
    global_count = 0
    shared_count = 0
    by_type = {}
    
    for provider in providers:
        config_data = provider.config_data or {}
        
        # Get sharing info
        shared_with = db.query(SharedAIProvider).filter(
            SharedAIProvider.source_provider_id == provider.id
        ).all()
        
        # Apply tenant filter if specified
        if filter_tenant_id:
            has_access = any(s.target_customer_id == filter_tenant_id for s in shared_with)
            if not has_access and not provider.is_global_shared:
                continue
        
        # Get tenant details for shared_with
        shared_tenant_info = []
        for share in shared_with:
            customer = db.query(Customer).filter(
                Customer.customer_id == share.target_customer_id
            ).first()
            if customer:
                shared_tenant_info.append(SharedTenantInfo(
                    customer_id=share.target_customer_id,
                    customer_name=customer.display_name or customer.name,
                    is_enabled=share.is_enabled,
                    shared_at=share.shared_at
                ))
        
        # Count stats
        if provider.is_global_shared:
            global_count += 1
        if shared_with:
            shared_count += 1
        
        provider_type_str = provider.provider_name
        by_type[provider_type_str] = by_type.get(provider_type_str, 0) + 1
        
        responses.append(PlatformProviderResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_type=provider.provider_name,
            name=provider.name,
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            config_summary=config_data,
            available_models=config_data.get("available_models", []),
            default_model=config_data.get("default_model"),
            is_global_shared=provider.is_global_shared,
            shared_with_tenants=shared_tenant_info,
            shared_with_count=len(shared_tenant_info),
            is_adoption_source=provider.is_adoption_source,
            chatgpt_workspace_id=provider.chatgpt_workspace_id,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            error_count=provider.error_count,
            last_error=provider.last_error
        ))
    
    return PlatformProviderListResponse(
        providers=responses,
        total_count=len(responses),
        global_count=global_count,
        shared_count=shared_count,
        by_type=by_type
    )


@router.post("/ai-providers", response_model=PlatformProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_platform_provider(
    request: PlatformProviderCreate,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new AI provider configuration for the platform.
    
    Can optionally be shared globally or with specific tenants.
    """
    platform_customer_id = get_platform_customer_id()
    
    # Use provider service to create the provider
    provider_service = ProviderService(db)
    
    from src.models.provider_config import ProviderConfigurationCreate
    config_request = ProviderConfigurationCreate(
        provider_type=request.provider_type,
        name=request.name,
        is_enabled=request.is_enabled,
        config=request.config
    )
    
    try:
        provider = provider_service.create_provider_config(
            customer_id=platform_customer_id,
            config_request=config_request
        )
        
        # Update global sharing flag
        provider.is_global_shared = request.is_global_shared
        db.commit()
        
        # Create sharing records for specific tenants
        shared_tenant_info = []
        if request.share_with_tenant_ids:
            current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
            for tenant_id in request.share_with_tenant_ids:
                # Skip if tenant doesn't exist
                customer = db.query(Customer).filter(
                    Customer.customer_id == tenant_id
                ).first()
                if not customer:
                    continue
                
                share = SharedAIProvider(
                    source_provider_id=provider.id,
                    target_customer_id=tenant_id,
                    shared_by=current_user_id,
                    is_enabled=True
                )
                db.add(share)
                shared_tenant_info.append(SharedTenantInfo(
                    customer_id=tenant_id,
                    customer_name=customer.display_name or customer.name,
                    is_enabled=True,
                    shared_at=share.shared_at
                ))
            
            db.commit()
        
        config_data = provider.config_data or {}
        return PlatformProviderResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_type=provider.provider_name,
            name=provider.name,
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            config_summary=config_data,
            available_models=config_data.get("available_models", []),
            default_model=config_data.get("default_model"),
            is_global_shared=provider.is_global_shared,
            shared_with_tenants=shared_tenant_info,
            shared_with_count=len(shared_tenant_info),
            is_adoption_source=provider.is_adoption_source,
            chatgpt_workspace_id=provider.chatgpt_workspace_id,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            error_count=provider.error_count,
            last_error=provider.last_error
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/ai-providers/{provider_id}/sharing", response_model=PlatformProviderResponse)
async def update_provider_sharing(
    provider_id: int,
    request: ProviderSharingUpdate,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Update sharing settings for a platform AI provider.
    
    Can:
    - Toggle global sharing
    - Add tenants to share with
    - Remove tenants from sharing
    """
    platform_customer_id = get_platform_customer_id()
    
    # Get the provider
    provider = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.id == provider_id,
        CustomerAIProvider.customer_id == platform_customer_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found or not owned by your tenant"
        )
    
    current_user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    
    # Check if enabling sharing on an adoption key - auto-disable adoption
    will_be_shared = (
        (request.is_global_shared is True) or 
        (request.share_with_tenant_ids and len(request.share_with_tenant_ids) > 0)
    )
    if will_be_shared and provider.is_adoption_source:
        # Auto-disable adoption when sharing is enabled
        provider.is_adoption_source = False
        provider.chatgpt_workspace_id = None
    
    # Update global sharing
    if request.is_global_shared is not None:
        provider.is_global_shared = request.is_global_shared
    
    # Add new sharing relationships
    if request.share_with_tenant_ids:
        for tenant_id in request.share_with_tenant_ids:
            # Check if already shared
            existing = db.query(SharedAIProvider).filter(
                SharedAIProvider.source_provider_id == provider_id,
                SharedAIProvider.target_customer_id == tenant_id
            ).first()
            
            if not existing:
                # Verify tenant exists
                customer = db.query(Customer).filter(
                    Customer.customer_id == tenant_id
                ).first()
                if customer:
                    share = SharedAIProvider(
                        source_provider_id=provider_id,
                        target_customer_id=tenant_id,
                        shared_by=current_user_id,
                        is_enabled=True
                    )
                    db.add(share)
    
    # Remove sharing relationships
    if request.unshare_from_tenant_ids:
        db.query(SharedAIProvider).filter(
            SharedAIProvider.source_provider_id == provider_id,
            SharedAIProvider.target_customer_id.in_(request.unshare_from_tenant_ids)
        ).delete(synchronize_session=False)
    
    db.commit()
    db.refresh(provider)
    
    # Build response with updated sharing info
    shared_with = db.query(SharedAIProvider).filter(
        SharedAIProvider.source_provider_id == provider.id
    ).all()
    
    shared_tenant_info = []
    for share in shared_with:
        customer = db.query(Customer).filter(
            Customer.customer_id == share.target_customer_id
        ).first()
        if customer:
            shared_tenant_info.append(SharedTenantInfo(
                customer_id=share.target_customer_id,
                customer_name=customer.display_name or customer.name,
                is_enabled=share.is_enabled,
                shared_at=share.shared_at
            ))
    
    config_data = provider.config_data or {}
    return PlatformProviderResponse(
        id=provider.id,
        customer_id=provider.customer_id,
        provider_type=provider.provider_name,
        name=provider.name,
        is_enabled=provider.is_enabled,
        is_healthy=provider.is_healthy,
        last_health_check=provider.last_health_check,
        config_summary=config_data,
        available_models=config_data.get("available_models", []),
        default_model=config_data.get("default_model"),
        is_global_shared=provider.is_global_shared,
        shared_with_tenants=shared_tenant_info,
        shared_with_count=len(shared_tenant_info),
        is_adoption_source=provider.is_adoption_source,
        chatgpt_workspace_id=provider.chatgpt_workspace_id,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        error_count=provider.error_count,
        last_error=provider.last_error
    )


@router.delete("/ai-providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform_provider(
    provider_id: int,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """Delete a platform AI provider configuration."""
    platform_customer_id = get_platform_customer_id()
    
    provider = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.id == provider_id,
        CustomerAIProvider.customer_id == platform_customer_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found or not owned by your tenant"
        )
    
    # Delete associated sharing records (cascade should handle this, but be explicit)
    db.query(SharedAIProvider).filter(
        SharedAIProvider.source_provider_id == provider_id
    ).delete(synchronize_session=False)
    
    db.delete(provider)
    db.commit()


@router.post(
    "/ai-providers/{provider_id}/test",
    response_model=ProviderConnectionTestResponse,
    summary="Test Platform Provider Connection",
    description="Test provider connection and credentials for a platform AI provider."
)
async def test_platform_provider_connection(
    provider_id: int,
    request: ProviderConnectionTestRequest = ProviderConnectionTestRequest(),
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Test platform provider connection.
    
    Makes a test API call to verify:
    - Credentials are valid
    - Provider is accessible
    - Models are available
    
    Updates the provider's health status based on test result.
    
    **Permissions**: Requires platform admin
    """
    platform_customer_id = get_platform_customer_id()
    
    provider = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.id == provider_id,
        CustomerAIProvider.customer_id == platform_customer_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found or not owned by platform"
        )
    
    try:
        service = ProviderService(db)
        test_result = await service.test_provider_connection(
            provider_id,
            platform_customer_id,
            request.test_prompt
        )
        
        return test_result
        
    except Exception as e:
        logger.error(f"Error testing platform provider connection for provider {provider_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test provider connection: {str(e)}"
        )


@router.get("/ai-providers/{provider_id}", response_model=PlatformProviderResponse)
async def get_platform_provider(
    provider_id: int,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """Get a specific platform AI provider with sharing details."""
    platform_customer_id = get_platform_customer_id()
    
    provider = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.id == provider_id,
        CustomerAIProvider.customer_id == platform_customer_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found or not owned by your tenant"
        )
    
    # Get sharing info
    shared_with = db.query(SharedAIProvider).filter(
        SharedAIProvider.source_provider_id == provider.id
    ).all()
    
    shared_tenant_info = []
    for share in shared_with:
        customer = db.query(Customer).filter(
            Customer.customer_id == share.target_customer_id
        ).first()
        if customer:
            shared_tenant_info.append(SharedTenantInfo(
                customer_id=share.target_customer_id,
                customer_name=customer.display_name or customer.name,
                is_enabled=share.is_enabled,
                shared_at=share.shared_at
            ))
    
    config_data = provider.config_data or {}
    return PlatformProviderResponse(
        id=provider.id,
        customer_id=provider.customer_id,
        provider_type=provider.provider_name,
        name=provider.name,
        is_enabled=provider.is_enabled,
        is_healthy=provider.is_healthy,
        last_health_check=provider.last_health_check,
        config_summary=config_data,
        available_models=config_data.get("available_models", []),
        default_model=config_data.get("default_model"),
        is_global_shared=provider.is_global_shared,
        shared_with_tenants=shared_tenant_info,
        shared_with_count=len(shared_tenant_info),
        is_adoption_source=provider.is_adoption_source,
        chatgpt_workspace_id=provider.chatgpt_workspace_id,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        error_count=provider.error_count,
        last_error=provider.last_error
    )


# =============================================================================
# ADOPTION SOURCE MANAGEMENT
# =============================================================================

class AdoptionSourceUpdate(BaseModel):
    """Request to update adoption source settings for a provider."""
    is_adoption_source: bool
    chatgpt_workspace_id: Optional[str] = None


@router.put("/ai-providers/{provider_id}/adoption", response_model=PlatformProviderResponse)
async def update_provider_adoption_settings(
    provider_id: int,
    request: AdoptionSourceUpdate,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Update adoption tracking settings for a provider (Platform Admin Override).
    
    NOTE: Adoption is primarily configured at the tenant level via Admin Settings.
    This endpoint is for platform admin support/override purposes only.
    
    Rules:
    - Adoption keys cannot be shared (globally or with specific tenants)
    - Only one provider per customer per provider_type can be marked as adoption source
    - Enabling adoption on one provider will disable it on others of the same type
    """
    # Platform admins can update any provider's adoption settings (support override)
    provider = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.id == provider_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    # Check if trying to enable adoption on a shared key
    if request.is_adoption_source:
        # Check if globally shared
        if provider.is_global_shared:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot enable adoption on a globally shared key. Adoption tracking requires a dedicated, non-shared API key."
            )
        
        # Check if shared with specific tenants
        share_count = db.query(SharedAIProvider).filter(
            SharedAIProvider.source_provider_id == provider_id
        ).count()
        
        if share_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot enable adoption on a shared key. Adoption tracking requires a dedicated, non-shared API key. Either unshare this key or create a new key for adoption metrics."
            )
        
        # Disable adoption on other providers of the same type for this customer
        db.query(CustomerAIProvider).filter(
            CustomerAIProvider.customer_id == provider.customer_id,
            CustomerAIProvider.provider_name == provider.provider_name,
            CustomerAIProvider.id != provider_id,
            CustomerAIProvider.is_adoption_source == True
        ).update({"is_adoption_source": False}, synchronize_session=False)
    
    # Update the provider
    provider.is_adoption_source = request.is_adoption_source
    if request.chatgpt_workspace_id is not None:
        provider.chatgpt_workspace_id = request.chatgpt_workspace_id
    
    db.commit()
    db.refresh(provider)
    
    # Build response with sharing info
    shared_with = db.query(SharedAIProvider).filter(
        SharedAIProvider.source_provider_id == provider.id
    ).all()
    
    shared_tenant_info = []
    for share in shared_with:
        customer = db.query(Customer).filter(
            Customer.customer_id == share.target_customer_id
        ).first()
        if customer:
            shared_tenant_info.append(SharedTenantInfo(
                customer_id=share.target_customer_id,
                customer_name=customer.display_name or customer.name,
                is_enabled=share.is_enabled,
                shared_at=share.shared_at
            ))
    
    config_data = provider.config_data or {}
    return PlatformProviderResponse(
        id=provider.id,
        customer_id=provider.customer_id,
        provider_type=provider.provider_name,
        name=provider.name,
        is_enabled=provider.is_enabled,
        is_healthy=provider.is_healthy,
        last_health_check=provider.last_health_check,
        config_summary=config_data,
        available_models=config_data.get("available_models", []),
        default_model=config_data.get("default_model"),
        is_global_shared=provider.is_global_shared,
        shared_with_tenants=shared_tenant_info,
        shared_with_count=len(shared_tenant_info),
        is_adoption_source=provider.is_adoption_source,
        chatgpt_workspace_id=provider.chatgpt_workspace_id,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        error_count=provider.error_count,
        last_error=provider.last_error
    )


# =============================================================================
# ADOPTION ACCESS MANAGEMENT
# =============================================================================

from datetime import datetime as dt

class AdoptionGrantCreate(BaseModel):
    """Request to create an adoption access grant."""
    source_customer_id: str  # Whose data is being shared
    target_customer_id: str  # Who gets to view it
    share_level: str = "read"  # "read" or "admin"
    notes: Optional[str] = None


class AdoptionGrantResponse(BaseModel):
    """Response for an adoption grant."""
    id: int
    source_customer_id: str
    source_customer_name: Optional[str]
    target_customer_id: str
    target_customer_name: Optional[str]
    share_level: str
    is_enabled: bool
    created_by_user_id: Optional[int]
    created_by_name: Optional[str]
    created_at: dt
    expires_at: Optional[dt]


class AdoptionGrantListResponse(BaseModel):
    """Response for listing adoption grants."""
    grants: List[AdoptionGrantResponse]
    total: int


@router.get("/adoption/grants", response_model=AdoptionGrantListResponse)
async def list_adoption_grants(
    source_customer_id: Optional[str] = Query(None, description="Filter by source customer"),
    target_customer_id: Optional[str] = Query(None, description="Filter by target customer"),
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """List all adoption access grants (platform admin only)."""
    from src.models.adoption import AdoptionDataShare
    from src.models.customer import Customer
    from src.models.auth import User as UserModel
    
    query = db.query(AdoptionDataShare)
    
    if source_customer_id:
        query = query.filter(AdoptionDataShare.source_customer_id == source_customer_id)
    if target_customer_id:
        query = query.filter(AdoptionDataShare.target_customer_id == target_customer_id)
    
    grants = query.order_by(AdoptionDataShare.created_at.desc()).all()
    
    # Get customer names
    customer_ids = set()
    user_ids = set()
    for g in grants:
        customer_ids.add(g.source_customer_id)
        customer_ids.add(g.target_customer_id)
        if g.shared_by_user_id:
            user_ids.add(g.shared_by_user_id)
    
    customers = {
        c.customer_id: c.display_name or c.name
        for c in db.query(Customer).filter(Customer.customer_id.in_(customer_ids)).all()
    } if customer_ids else {}
    
    users = {
        u.id: u.full_name or u.username
        for u in db.query(UserModel).filter(UserModel.id.in_(user_ids)).all()
    } if user_ids else {}
    
    grant_responses = [
        AdoptionGrantResponse(
            id=g.id,
            source_customer_id=g.source_customer_id,
            source_customer_name=customers.get(g.source_customer_id),
            target_customer_id=g.target_customer_id,
            target_customer_name=customers.get(g.target_customer_id),
            share_level=g.share_level,
            is_enabled=g.is_enabled,
            created_by_user_id=g.shared_by_user_id,
            created_by_name=users.get(g.shared_by_user_id) if g.shared_by_user_id else None,
            created_at=g.created_at,
            expires_at=g.expires_at
        )
        for g in grants
    ]
    
    return AdoptionGrantListResponse(
        grants=grant_responses,
        total=len(grant_responses)
    )


@router.post("/adoption/grants", response_model=AdoptionGrantResponse, status_code=status.HTTP_201_CREATED)
async def create_adoption_grant(
    request: AdoptionGrantCreate,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Create an adoption access grant (platform admin only).
    
    This allows a target tenant to view adoption data from a source tenant.
    For example, allowing Blackstone (target) to view Acme's (source) adoption metrics.
    """
    from src.models.adoption import AdoptionDataShare, AdoptionShareLevel
    from src.models.customer import Customer
    
    # Validate source and target exist
    source = db.query(Customer).filter(Customer.customer_id == request.source_customer_id).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source customer '{request.source_customer_id}' not found"
        )
    
    target = db.query(Customer).filter(Customer.customer_id == request.target_customer_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target customer '{request.target_customer_id}' not found"
        )
    
    # Validate share level
    if not AdoptionShareLevel.is_valid(request.share_level):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid share level. Must be one of: {AdoptionShareLevel.all_levels()}"
        )
    
    # Check if grant already exists
    existing = db.query(AdoptionDataShare).filter(
        AdoptionDataShare.source_customer_id == request.source_customer_id,
        AdoptionDataShare.target_customer_id == request.target_customer_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Grant already exists between these tenants"
        )
    
    # Create grant
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    grant = AdoptionDataShare(
        source_customer_id=request.source_customer_id,
        target_customer_id=request.target_customer_id,
        share_level=request.share_level,
        is_enabled=True,
        shared_by_user_id=user_id
    )
    
    db.add(grant)
    db.commit()
    db.refresh(grant)
    
    # Get user name
    from src.models.auth import User as UserModel
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    
    return AdoptionGrantResponse(
        id=grant.id,
        source_customer_id=grant.source_customer_id,
        source_customer_name=source.display_name or source.name,
        target_customer_id=grant.target_customer_id,
        target_customer_name=target.display_name or target.name,
        share_level=grant.share_level,
        is_enabled=grant.is_enabled,
        created_by_user_id=grant.shared_by_user_id,
        created_by_name=user.full_name or user.username if user else None,
        created_at=grant.created_at,
        expires_at=grant.expires_at
    )


@router.patch("/adoption/grants/{grant_id}")
async def update_adoption_grant(
    grant_id: int,
    is_enabled: Optional[bool] = None,
    share_level: Optional[str] = None,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """Update an adoption access grant."""
    from src.models.adoption import AdoptionDataShare, AdoptionShareLevel
    
    grant = db.query(AdoptionDataShare).filter(AdoptionDataShare.id == grant_id).first()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grant not found"
        )
    
    if is_enabled is not None:
        grant.is_enabled = is_enabled
    
    if share_level is not None:
        if not AdoptionShareLevel.is_valid(share_level):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid share level. Must be one of: {AdoptionShareLevel.all_levels()}"
            )
        grant.share_level = share_level
    
    db.commit()
    
    return {"message": "Grant updated", "id": grant_id}


@router.delete("/adoption/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_adoption_grant(
    grant_id: int,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """Delete an adoption access grant."""
    from src.models.adoption import AdoptionDataShare
    
    grant = db.query(AdoptionDataShare).filter(AdoptionDataShare.id == grant_id).first()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grant not found"
        )
    
    db.delete(grant)
    db.commit()
    
    return None


# ============================================================================
# JOB SCHEDULER ENDPOINTS
# ============================================================================

class ScheduledJobResponse(BaseModel):
    """Response model for scheduled job."""
    id: int
    job_name: str
    display_name: str
    description: Optional[str] = None
    task_name: str
    schedule_type: str
    schedule_value: str
    schedule_display: Optional[str] = None  # Human-readable schedule
    is_enabled: bool
    last_run_at: Optional[str] = None
    last_run_status: str
    last_run_duration_seconds: Optional[int] = None
    last_error: Optional[str] = None
    last_task_id: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class ScheduledJobListResponse(BaseModel):
    """Response model for list of scheduled jobs."""
    jobs: List[ScheduledJobResponse]
    total: int


class ScheduledJobUpdateRequest(BaseModel):
    """Request to update a scheduled job."""
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    schedule_type: Optional[str] = None
    schedule_value: Optional[str] = None


class JobExecutionResponse(BaseModel):
    """Response model for job execution."""
    id: int
    job_name: str
    task_id: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    triggered_by: str
    result_summary: Optional[str] = None

    class Config:
        from_attributes = True


class JobExecutionListResponse(BaseModel):
    """Response model for list of job executions."""
    executions: List[JobExecutionResponse]
    total: int


class JobTriggerResponse(BaseModel):
    """Response for manual job trigger."""
    success: bool
    message: str
    task_id: Optional[str] = None


def _build_job_dict(job, db: Session, customer_id: Optional[str] = None) -> dict:
    """Build a response dict for a ScheduledJobConfig.

    For the adoption dispatcher job, replaces the raw 60-second polling
    interval with the requesting tenant's actual cron schedule so the Job
    Scheduler UI shows a meaningful label.
    """
    job_dict = job.to_dict()

    if job.job_name == "adoption-daily-sync" and customer_id:
        from src.models.adoption import AdoptionSyncConfig

        config = db.query(AdoptionSyncConfig).filter(
            AdoptionSyncConfig.customer_id == customer_id,
            AdoptionSyncConfig.schedule_enabled.is_(True),
        ).first()

        if config and config.schedule_cron:
            job_dict["schedule_type"] = "cron"
            job_dict["schedule_value"] = config.schedule_cron
            job_dict["schedule_display"] = format_schedule_display("cron", config.schedule_cron)
        else:
            job_dict["schedule_display"] = "Per-tenant schedule (Adoption Settings)"
    else:
        job_dict["schedule_display"] = format_schedule_display(job.schedule_type, job.schedule_value)

    return job_dict


def format_schedule_display(schedule_type: str, schedule_value: str) -> str:
    """Convert schedule to human-readable format."""
    if schedule_type == "interval":
        try:
            seconds = int(schedule_value)
            if seconds >= 86400:
                days = seconds // 86400
                return f"Every {days} day{'s' if days > 1 else ''}"
            elif seconds >= 3600:
                hours = seconds // 3600
                return f"Every {hours} hour{'s' if hours > 1 else ''}"
            elif seconds >= 60:
                minutes = seconds // 60
                return f"Every {minutes} minute{'s' if minutes > 1 else ''}"
            else:
                return f"Every {seconds} seconds"
        except ValueError:
            return schedule_value
    elif schedule_type == "cron":
        # Parse cron expression and display in Eastern time
        try:
            parts = schedule_value.split()
            if len(parts) == 5:
                minute, hour, day_of_month, month, day_of_week = parts
                # Convert UTC hour to Eastern (subtract 5)
                utc_hour = int(hour)
                eastern_hour = (utc_hour - 5) % 24
                # Format as 12-hour time
                period = "AM" if eastern_hour < 12 else "PM"
                display_hour = eastern_hour % 12 or 12
                time_str = f"{display_hour}:{minute.zfill(2)} {period} ET"
                
                # Handle various day formats
                if day_of_week == "*" and day_of_month == "*":
                    return f"Daily at {time_str}"
                elif day_of_week == "1-5":
                    return f"Weekdays at {time_str}"
                elif day_of_week == "0,6" or day_of_week == "6,0":
                    return f"Weekends at {time_str}"
                elif day_of_week == "0":
                    return f"Sun at {time_str}"
                elif day_of_week == "6":
                    return f"Sat at {time_str}"
                elif "," in day_of_week:
                    # Multiple specific days
                    day_names = {
                        "0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed",
                        "4": "Thu", "5": "Fri", "6": "Sat"
                    }
                    days = [day_names.get(d.strip(), d) for d in day_of_week.split(",")]
                    return f"{', '.join(days)} at {time_str}"
                else:
                    return f"Cron: {schedule_value}"
            return f"Cron: {schedule_value}"
        except (ValueError, IndexError):
            return f"Cron: {schedule_value}"
    return schedule_value


@router.get("/jobs", response_model=ScheduledJobListResponse)
async def list_scheduled_jobs(
    current_user: User = Depends(require_job_access),
    db: Session = Depends(get_db)
):
    """
    List all scheduled jobs with their current status.
    
    Returns job configurations including last execution status and next run time.
    """
    from src.models.scheduled_job import ScheduledJobConfig
    
    jobs = db.query(ScheduledJobConfig).order_by(ScheduledJobConfig.display_name).all()

    customer_id = getattr(current_user, "customer_id", None)
    job_responses = []
    for job in jobs:
        job_dict = _build_job_dict(job, db, customer_id)
        job_responses.append(ScheduledJobResponse(**job_dict))

    return ScheduledJobListResponse(jobs=job_responses, total=len(job_responses))


@router.get("/jobs/stream")
async def stream_job_status(
    request: Request,
    token: str = Query(..., description="JWT access token (EventSource doesn't support headers)"),
    db: Session = Depends(get_db)
):
    """
    Stream real-time job status updates using Server-Sent Events (SSE).
    
    Events emitted:
    - connected: Initial connection established with all current jobs
    - job_update: A job's status changed
    - execution_update: A new execution started or completed
    - heartbeat: Keep-alive signal (every 15 seconds)
    
    Note: Token is passed as query param because EventSource doesn't support custom headers.
    """
    from src.models.scheduled_job import ScheduledJobConfig, ScheduledJobExecution
    from src.services.auth_service import AuthService
    from fastapi.responses import StreamingResponse
    from datetime import datetime, timezone
    import asyncio
    import json
    import uuid
    
    # Verify token and ensure platform admin
    auth_service = AuthService()
    try:
        payload = await auth_service.verify_token(token)
        user_id = int(payload.get("sub"))
        user = await auth_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found"
            )
        
        # Verify platform admin or adoption:manage_jobs access
        platform_service = PlatformAdminService(db)
        user_permissions = user.get_permissions() if hasattr(user, 'get_permissions') else []
        is_admin = platform_service.is_platform_admin(user_id)
        has_manage_jobs = 'adoption:manage_jobs' in user_permissions
        if not is_admin and not has_manage_jobs:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform admin access or adoption:manage_jobs permission required"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("SSE auth failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication failed"
        )

    sse_customer_id = getattr(user, "customer_id", None)

    async def event_generator():
        """Generate SSE events from job status polling."""
        poll_interval = 2  # Check every 2 seconds
        heartbeat_interval = 15  # Send heartbeat every ~15 seconds if idle
        max_iterations = 1800  # Max 1 hour of streaming
        
        # Track last known state to detect changes
        last_job_states = {}
        last_execution_ids = set()
        idle_cycles = 0
        
        try:
            # Initial connection event with all current job states
            jobs = db.query(ScheduledJobConfig).all()
            initial_jobs = []
            for job in jobs:
                job_dict = _build_job_dict(job, db, sse_customer_id)
                initial_jobs.append(job_dict)
                # Track initial state
                last_job_states[job.job_name] = {
                    "status": job.last_run_status,
                    "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
                    "last_task_id": job.last_task_id
                }
            
            # Get initial execution IDs
            recent_executions = db.query(ScheduledJobExecution).order_by(
                ScheduledJobExecution.started_at.desc()
            ).limit(100).all()
            last_execution_ids = {ex.id for ex in recent_executions}
            
            connected_event = {
                "event_id": f"connected-{uuid.uuid4().hex[:8]}",
                "event_type": "connected",
                "jobs": initial_jobs,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            yield f"data: {json.dumps(connected_event)}\n\n"
            
            # Polling loop
            iteration = 0
            while iteration < max_iterations:
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                
                # Refresh session to get fresh data
                db.expire_all()
                
                # Check for job status changes
                jobs = db.query(ScheduledJobConfig).all()
                for job in jobs:
                    job_dict = _build_job_dict(job, db, sse_customer_id)
                    
                    current_state = {
                        "status": job.last_run_status,
                        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
                        "last_task_id": job.last_task_id
                    }
                    
                    prev_state = last_job_states.get(job.job_name, {})
                    
                    # Detect changes in status or last run
                    if (current_state["status"] != prev_state.get("status") or
                        current_state["last_run_at"] != prev_state.get("last_run_at") or
                        current_state["last_task_id"] != prev_state.get("last_task_id")):
                        
                        update_event = {
                            "event_id": f"job-{uuid.uuid4().hex[:8]}",
                            "event_type": "job_update",
                            "job": job_dict,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        yield f"data: {json.dumps(update_event)}\n\n"
                        last_job_states[job.job_name] = current_state
                        idle_cycles = 0
                
                # Check for new executions
                recent_executions = db.query(ScheduledJobExecution).order_by(
                    ScheduledJobExecution.started_at.desc()
                ).limit(100).all()
                
                current_execution_ids = {ex.id for ex in recent_executions}
                new_execution_ids = current_execution_ids - last_execution_ids
                
                if new_execution_ids:
                    for ex in recent_executions:
                        if ex.id in new_execution_ids:
                            execution_event = {
                                "event_id": f"exec-{uuid.uuid4().hex[:8]}",
                                "event_type": "execution_update",
                                "execution": {
                                    "id": ex.id,
                                    "job_name": ex.job_name,
                                    "task_id": ex.task_id,
                                    "started_at": ex.started_at.isoformat() if ex.started_at else None,
                                    "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
                                    "duration_seconds": ex.duration_seconds,
                                    "status": ex.status,
                                    "error_message": ex.error_message,
                                    "triggered_by": ex.triggered_by,
                                    "result_summary": ex.result_summary
                                },
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                            yield f"data: {json.dumps(execution_event)}\n\n"
                    last_execution_ids = current_execution_ids
                    idle_cycles = 0
                
                # Send heartbeat if idle for a while
                idle_cycles += 1
                if idle_cycles >= (heartbeat_interval // poll_interval):
                    heartbeat_event = {
                        "event_id": f"heartbeat-{uuid.uuid4().hex[:8]}",
                        "event_type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(heartbeat_event)}\n\n"
                    idle_cycles = 0
                
                iteration += 1
                await asyncio.sleep(poll_interval)
                
        except Exception as e:
            logger.error("SSE stream error", error=str(e), exc_info=True)
            error_event = {
                "event_id": f"error-{uuid.uuid4().hex[:8]}",
                "event_type": "error",
                "message": f"Stream error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/jobs/{job_name}", response_model=ScheduledJobResponse)
async def get_scheduled_job(
    job_name: str,
    current_user: User = Depends(require_job_access),
    db: Session = Depends(get_db)
):
    """Get details for a specific scheduled job."""
    from src.models.scheduled_job import ScheduledJobConfig
    
    job = db.query(ScheduledJobConfig).filter(ScheduledJobConfig.job_name == job_name).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_name}' not found"
        )

    customer_id = getattr(current_user, "customer_id", None)
    job_dict = _build_job_dict(job, db, customer_id)
    return ScheduledJobResponse(**job_dict)


@router.put("/jobs/{job_name}", response_model=ScheduledJobResponse)
async def update_scheduled_job(
    job_name: str,
    request: ScheduledJobUpdateRequest,
    current_user: User = Depends(require_job_access),
    db: Session = Depends(get_db)
):
    """
    Update a scheduled job's configuration.
    
    Can update:
    - display_name: Human-readable name
    - description: Job description
    - is_enabled: Enable/disable the job
    - schedule_type: 'interval' or 'cron'
    - schedule_value: Seconds for interval, cron expression for cron
    """
    from src.models.scheduled_job import ScheduledJobConfig
    
    job = db.query(ScheduledJobConfig).filter(ScheduledJobConfig.job_name == job_name).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_name}' not found"
        )
    
    # Update fields if provided
    if request.display_name is not None:
        job.display_name = request.display_name
    
    if request.description is not None:
        job.description = request.description
    
    if request.is_enabled is not None:
        job.is_enabled = request.is_enabled
    
    if request.schedule_type is not None:
        if request.schedule_type not in ("interval", "cron"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="schedule_type must be 'interval' or 'cron'"
            )
        job.schedule_type = request.schedule_type
    
    if request.schedule_value is not None:
        # Validate interval is a positive integer
        schedule_type = request.schedule_type if request.schedule_type else job.schedule_type
        if schedule_type == "interval":
            try:
                val = int(request.schedule_value)
                if val <= 0:
                    raise ValueError()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="For interval schedule, value must be a positive integer (seconds)"
                )
        job.schedule_value = request.schedule_value
    
    # Track who updated
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
    job.updated_by_user_id = user_id
    
    db.commit()
    db.refresh(job)

    customer_id = getattr(current_user, "customer_id", None)
    job_dict = _build_job_dict(job, db, customer_id)
    return ScheduledJobResponse(**job_dict)


@router.post("/jobs/{job_name}/trigger", response_model=JobTriggerResponse)
async def trigger_job(
    job_name: str,
    current_user: User = Depends(require_job_access),
    db: Session = Depends(get_db)
):
    """
    Manually trigger a job to run immediately.
    
    The job runs asynchronously. Use GET /jobs/{job_name}/executions to check status.
    """
    from src.models.scheduled_job import ScheduledJobConfig, ScheduledJobExecution
    from src.celery_app import celery_app
    from datetime import datetime, timezone
    
    job = db.query(ScheduledJobConfig).filter(ScheduledJobConfig.job_name == job_name).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_name}' not found"
        )
    
    # Check if job is already running
    if job.last_run_status == "running":
        # Detect stale "running" status - if job has been running for more than
        # 30 minutes, it's likely stuck (chord callback never fired). Allow
        # re-triggering by marking the stale execution as failed.
        stale_threshold_minutes = 30
        is_stale = False
        if job.last_run_at:
            elapsed = datetime.now(timezone.utc) - job.last_run_at.replace(tzinfo=timezone.utc) if job.last_run_at.tzinfo is None else datetime.now(timezone.utc) - job.last_run_at
            is_stale = elapsed.total_seconds() > stale_threshold_minutes * 60
        
        if not is_stale:
            return JobTriggerResponse(
                success=False,
                message=f"Job '{job_name}' is already running (task_id: {job.last_task_id}). Will auto-reset after {stale_threshold_minutes} min if stuck.",
                task_id=job.last_task_id
            )
        
        # Mark the stale execution as failed so the job can be re-triggered
        logger.warning(
            f"Job '{job_name}' has been running for >{stale_threshold_minutes}min "
            f"(started {job.last_run_at}). Marking as stale/failed and allowing re-trigger."
        )
        stale_execution = db.query(ScheduledJobExecution).filter(
            ScheduledJobExecution.task_id == job.last_task_id
        ).first()
        if stale_execution:
            stale_execution.status = "failed"
            stale_execution.completed_at = datetime.now(timezone.utc)
            stale_execution.error_message = f"Timed out after {stale_threshold_minutes} minutes (stale detection)"
        job.last_run_status = "failed"
        job.last_error = f"Timed out after {stale_threshold_minutes} minutes (stale detection)"
        db.commit()
    
    try:
        # Send task to Celery
        result = celery_app.send_task(job.task_name)
        task_id = result.id
        
        # Update job status
        job.last_run_status = "running"
        job.last_run_at = datetime.now(timezone.utc)
        job.last_task_id = task_id
        job.last_error = None
        
        # Create execution record
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else current_user.id
        execution = ScheduledJobExecution(
            job_name=job_name,
            task_id=task_id,
            status="running",
            triggered_by="manual",
            triggered_by_user_id=user_id
        )
        db.add(execution)
        db.commit()
        
        return JobTriggerResponse(
            success=True,
            message=f"Job '{job_name}' triggered successfully",
            task_id=task_id
        )
        
    except Exception as e:
        return JobTriggerResponse(
            success=False,
            message=f"Failed to trigger job: {str(e)}",
            task_id=None
        )


@router.get("/jobs/{job_name}/executions", response_model=JobExecutionListResponse)
async def get_job_executions(
    job_name: str,
    limit: int = Query(20, ge=1, le=100, description="Number of executions to return"),
    current_user: User = Depends(require_job_access),
    db: Session = Depends(get_db)
):
    """
    Get recent execution history for a job.
    
    Returns the most recent executions ordered by start time (newest first).
    """
    from src.models.scheduled_job import ScheduledJobConfig, ScheduledJobExecution
    
    # Verify job exists
    job = db.query(ScheduledJobConfig).filter(ScheduledJobConfig.job_name == job_name).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_name}' not found"
        )
    
    executions = db.query(ScheduledJobExecution).filter(
        ScheduledJobExecution.job_name == job_name
    ).order_by(ScheduledJobExecution.started_at.desc()).limit(limit).all()
    
    execution_responses = []
    for ex in executions:
        execution_responses.append(JobExecutionResponse(
            id=ex.id,
            job_name=ex.job_name,
            task_id=ex.task_id,
            started_at=ex.started_at.isoformat() if ex.started_at else None,
            completed_at=ex.completed_at.isoformat() if ex.completed_at else None,
            duration_seconds=ex.duration_seconds,
            status=ex.status,
            error_message=ex.error_message,
            triggered_by=ex.triggered_by,
            result_summary=ex.result_summary
        ))
    
    return JobExecutionListResponse(executions=execution_responses, total=len(execution_responses))
