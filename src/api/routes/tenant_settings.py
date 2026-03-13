"""
Tenant Settings API Routes

API endpoints for managing tenant-specific settings including theme/branding.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.models import get_db
from src.models.tenant_theme import TenantTheme
from src.models.tenant_admin import PlatformFeature, TenantFeatureAllocation
from src.api.schemas.tenant_settings import (
    ThemeResponse,
    ThemeUpdateRequest,
    TenantObjectStorageSettingsResponse,
    TenantObjectStorageSettingsUpdateRequest,
    DEFAULT_THEME,
)
from src.api.schemas.sso_settings import (
    SSOLoginMode,
    TenantSSODomainCreateRequest,
    TenantSSODomainResponse,
    TenantSSOPolicyResponse,
    TenantSSOPolicyUpdateRequest,
    TenantSSOProviderResponse,
    TenantSSOProviderUpsertRequest,
    TenantSSOSettingsResponse,
    TenantSSOSettingsUpdateRequest,
)
from src.services.tenant_storage_settings_service import TenantStorageSettingsService
from src.services.tenant_sso_settings_service import (
    PlatformSSOPolicyService,
    TenantSSOSettingsService,
)
from src.services.tenant_sso_provider_service import TenantSSOProviderService
from src.services.audit_service import audit_service, AuditAction
from src.middleware.authorization import auth_middleware
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.API)

router = APIRouter(prefix="/v1/tenant-settings", tags=["Tenant Settings"])
SSO_FEATURE_KEY = "sso_authentication"


def _is_sso_feature_allocated(db: Session, customer_id: str) -> bool:
    """Check whether SSO feature is allocated and enabled for the tenant."""
    allocation = (
        db.query(TenantFeatureAllocation)
        .join(PlatformFeature, PlatformFeature.id == TenantFeatureAllocation.feature_id)
        .filter(
            TenantFeatureAllocation.customer_id == customer_id,
            TenantFeatureAllocation.is_enabled == True,  # noqa: E712
            PlatformFeature.feature_key == SSO_FEATURE_KEY,
            PlatformFeature.is_active == True,  # noqa: E712
        )
        .first()
    )
    return allocation is not None


def _assert_tenant_can_use_sso(db: Session, customer_id: str):
    """Ensure platform policy and tenant feature allocation allow SSO operations."""
    policy = PlatformSSOPolicyService(db).get_policy()
    if not policy.global_sso_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SSO is disabled by platform policy",
        )

    if not _is_sso_feature_allocated(db, customer_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SSO feature is not allocated to this tenant",
        )
    return policy


# ============================================================================
# THEME ENDPOINTS
# ============================================================================

@router.get(
    "/theme",
    response_model=ThemeResponse,
    summary="Get tenant theme",
    description="Get the theme/branding settings for the current user's tenant."
)
async def get_tenant_theme(
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Get theme for current user's tenant.
    
    Returns the tenant's custom theme if configured, otherwise returns
    the default Eliza Forge theme.
    """
    theme = db.query(TenantTheme).filter(
        TenantTheme.customer_id == current_user.customer_id
    ).first()
    
    if not theme:
        # Return defaults if no theme configured
        logger.debug(
            "theme_not_found_returning_defaults",
            customer_id=current_user.customer_id
        )
        return ThemeResponse(
            primary=DEFAULT_THEME['primary'],
            primaryLight=DEFAULT_THEME['primaryLight'],
            accent=DEFAULT_THEME['accent'],
            text=DEFAULT_THEME['text'],
            preset='eliza-forge'
        )
    
    logger.debug(
        "theme_retrieved",
        customer_id=current_user.customer_id,
        preset=theme.preset_name
    )
    
    return ThemeResponse(
        primary=theme.primary_color,
        primaryLight=theme.primary_light_color,
        accent=theme.accent_color,
        text=theme.text_color,
        preset=theme.preset_name
    )


@router.put(
    "/theme",
    response_model=ThemeResponse,
    summary="Update tenant theme",
    description="Update the theme/branding settings for the current user's tenant. Requires theme:write permission."
)
async def update_tenant_theme(
    request: ThemeUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("theme:write"))
):
    """
    Update theme for current user's tenant.
    
    Creates a new theme record if one doesn't exist, or updates the existing one.
    """
    theme = db.query(TenantTheme).filter(
        TenantTheme.customer_id == current_user.customer_id
    ).first()
    
    if not theme:
        # Create new theme record
        theme = TenantTheme(
            customer_id=current_user.customer_id,
            primary_color=request.primary,
            primary_light_color=request.primaryLight,
            accent_color=request.accent,
            text_color=request.text,
            preset_name=request.preset
        )
        db.add(theme)
        logger.info(
            "theme_created",
            customer_id=current_user.customer_id,
            user_id=current_user.user_id,
            preset=request.preset
        )
    else:
        # Update existing
        theme.primary_color = request.primary
        theme.primary_light_color = request.primaryLight
        theme.accent_color = request.accent
        theme.text_color = request.text
        theme.preset_name = request.preset
        logger.info(
            "theme_updated",
            customer_id=current_user.customer_id,
            user_id=current_user.user_id,
            preset=request.preset
        )
    
    db.commit()
    db.refresh(theme)
    
    return ThemeResponse(
        primary=theme.primary_color,
        primaryLight=theme.primary_light_color,
        accent=theme.accent_color,
        text=theme.text_color,
        preset=theme.preset_name
    )


# ============================================================================
# SSO ENDPOINTS
# ============================================================================


@router.get(
    "/sso/policy",
    response_model=TenantSSOPolicyResponse,
    summary="Get tenant SSO login policy",
    description="Get tenant-scoped login policy only (separate from providers).",
)
async def get_tenant_sso_policy(
    db: Session = Depends(get_db),
    current_user=Depends(
        auth_middleware.require_any_permission(
            ["admin:settings:read", "admin:settings:update", "platform:admin"]
        )
    ),
):
    """Get SSO login policy for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    return service.get_policy(current_user.customer_id)


@router.put(
    "/sso/policy",
    response_model=TenantSSOPolicyResponse,
    summary="Update tenant SSO login policy",
    description="Update tenant-scoped login policy only (separate from providers).",
)
async def update_tenant_sso_policy(
    request: TenantSSOPolicyUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Update SSO login policy for the current tenant."""
    policy = _assert_tenant_can_use_sso(db, current_user.customer_id)
    effective_domain_verification_required = (
        True
        if policy.require_domain_verification_for_enforced_mode
        else request.domain_verification_required
    )

    if (
        request.login_mode == SSOLoginMode.SSO_ENFORCED
        and not policy.allow_tenant_enforced_mode
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant enforced SSO mode is disabled by platform policy",
        )
    if (
        request.login_mode == SSOLoginMode.SSO_ENFORCED
        and effective_domain_verification_required
    ):
        domain_service = TenantSSOProviderService(db)
        domains = domain_service.list_domains(current_user.customer_id)
        has_verified_domain = any(domain.status.value == "verified" for domain in domains)
        if not has_verified_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one verified domain is required when enforcing SSO with domain verification",
            )

    service = TenantSSOProviderService(db)
    updated = service.update_policy(
        customer_id=current_user.customer_id,
        request=TenantSSOPolicyUpdateRequest(
            login_mode=request.login_mode,
            domain_verification_required=effective_domain_verification_required,
        ),
        updated_by_user_id=current_user.user_id,
    )

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_policy",
        resource_id=current_user.customer_id,
        additional_context={
            "customer_id": current_user.customer_id,
            "login_mode": updated.login_mode,
            "domain_verification_required": updated.domain_verification_required,
        },
    )
    return updated

@router.get(
    "/sso",
    response_model=TenantSSOSettingsResponse,
    summary="Get tenant SSO settings",
    description="Get tenant-scoped SSO provider and login policy settings.",
)
async def get_tenant_sso_settings(
    db: Session = Depends(get_db),
    current_user=Depends(
        auth_middleware.require_any_permission(
            ["admin:settings:read", "admin:settings:update", "platform:admin"]
        )
    ),
):
    """Get SSO settings for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOSettingsService(db)
    return service.get_settings(current_user.customer_id)


@router.put(
    "/sso",
    response_model=TenantSSOSettingsResponse,
    summary="Update tenant SSO settings",
    description="Create or update tenant-scoped SSO provider and login policy settings.",
)
async def update_tenant_sso_settings(
    request: TenantSSOSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Update SSO settings for the current tenant."""
    policy = _assert_tenant_can_use_sso(db, current_user.customer_id)

    if (
        request.login_mode == SSOLoginMode.SSO_ENFORCED
        and not policy.allow_tenant_enforced_mode
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant enforced SSO mode is disabled by platform policy",
        )

    # TODO(testing): Domain verification checks temporarily bypassed for SSO enforcement testing.
    # Restore these blocks when done testing.
    # if (
    #     request.login_mode == SSOLoginMode.SSO_ENFORCED
    #     and policy.require_domain_verification_for_enforced_mode
    #     and not request.domain_verification_required
    # ):
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Domain verification is required by platform policy for enforced mode",
    #     )
    #
    # if (
    #     request.login_mode == SSOLoginMode.SSO_ENFORCED
    #     and request.domain_verification_required
    #     and not request.domain_allowlist
    # ):
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="At least one domain must be in the allowlist when enforcing SSO with domain verification",
    #     )

    if (
        request.provider_type is not None
        and request.provider_type not in policy.allowed_provider_types
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider type '{request.provider_type.value}' is not allowed by platform policy",
        )

    service = TenantSSOSettingsService(db)
    try:
        updated = service.update_settings(
            customer_id=current_user.customer_id,
            request=request,
            updated_by_user_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    logger.info(
        "tenant_sso_settings_updated",
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        login_mode=updated.login_mode,
        provider_type=updated.provider_type,
        protocol=updated.protocol,
        is_enabled=updated.is_enabled,
    )

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_config",
        resource_id=current_user.customer_id,
        additional_context={
            "customer_id": current_user.customer_id,
            "login_mode": updated.login_mode,
            "provider_type": updated.provider_type.value if updated.provider_type else None,
            "protocol": updated.protocol.value if updated.protocol else None,
            "is_enabled": updated.is_enabled,
            "domain_verification_required": updated.domain_verification_required,
            "jit_provisioning_enabled": updated.jit_provisioning_enabled,
            "jit_default_role": updated.jit_default_role,
        },
    )
    return updated


@router.post(
    "/sso/test",
    response_model=TenantSSOSettingsResponse,
    summary="Test tenant SSO settings",
    description="Run a connectivity/metadata test against the configured SSO provider.",
)
async def test_tenant_sso_settings(
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Test current tenant SSO provider settings and persist test result metadata."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOSettingsService(db)
    try:
        tested = service.test_settings(current_user.customer_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_test",
        resource_id=current_user.customer_id,
        additional_context={
            "customer_id": current_user.customer_id,
            "last_test_status": tested.last_test_status,
            "last_test_error": tested.last_test_error,
            "protocol": tested.protocol.value if tested.protocol else None,
            "provider_type": tested.provider_type.value if tested.provider_type else None,
        },
    )
    return tested


@router.get(
    "/sso/providers",
    response_model=list[TenantSSOProviderResponse],
    summary="List tenant SSO providers",
    description="List all tenant-scoped SSO providers.",
)
async def list_tenant_sso_providers(
    db: Session = Depends(get_db),
    current_user=Depends(
        auth_middleware.require_any_permission(
            ["admin:settings:read", "admin:settings:update", "platform:admin"]
        )
    ),
):
    """List SSO providers for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    return service.list_providers(current_user.customer_id)


@router.post(
    "/sso/providers",
    response_model=TenantSSOProviderResponse,
    summary="Create tenant SSO provider",
    description="Create a tenant-scoped SSO provider configuration.",
)
async def create_tenant_sso_provider(
    request: TenantSSOProviderUpsertRequest,
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Create an SSO provider for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    try:
        created = service.create_provider(
            customer_id=current_user.customer_id,
            request=request,
            updated_by_user_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_provider",
        resource_id=str(created.id),
        additional_context={
            "customer_id": current_user.customer_id,
            "provider_type": created.provider_type.value,
            "protocol": created.protocol.value,
            "is_enabled": created.is_enabled,
        },
    )
    return created


@router.get(
    "/sso/providers/{provider_id}",
    response_model=TenantSSOProviderResponse,
    summary="Get tenant SSO provider",
    description="Get a tenant-scoped SSO provider by ID.",
)
async def get_tenant_sso_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        auth_middleware.require_any_permission(
            ["admin:settings:read", "admin:settings:update", "platform:admin"]
        )
    ),
):
    """Get one SSO provider for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    try:
        return service.get_provider(current_user.customer_id, provider_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put(
    "/sso/providers/{provider_id}",
    response_model=TenantSSOProviderResponse,
    summary="Update tenant SSO provider",
    description="Update a tenant-scoped SSO provider by ID.",
)
async def update_tenant_sso_provider(
    provider_id: int,
    request: TenantSSOProviderUpsertRequest,
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Update one SSO provider for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    try:
        updated = service.update_provider(
            customer_id=current_user.customer_id,
            provider_id=provider_id,
            request=request,
            updated_by_user_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_provider",
        resource_id=str(updated.id),
        additional_context={
            "customer_id": current_user.customer_id,
            "provider_type": updated.provider_type.value,
            "protocol": updated.protocol.value,
            "is_enabled": updated.is_enabled,
        },
    )
    return updated


@router.delete(
    "/sso/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tenant SSO provider",
    description="Delete a tenant-scoped SSO provider by ID.",
)
async def delete_tenant_sso_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Delete one SSO provider for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    try:
        service.delete_provider(current_user.customer_id, provider_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_provider",
        resource_id=str(provider_id),
        additional_context={
            "customer_id": current_user.customer_id,
            "deleted": True,
        },
    )


@router.post(
    "/sso/providers/{provider_id}/test",
    response_model=TenantSSOProviderResponse,
    summary="Test tenant SSO provider",
    description="Run metadata/connectivity test for one tenant-scoped SSO provider.",
)
async def test_tenant_sso_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Test one SSO provider for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    try:
        tested = service.test_provider(current_user.customer_id, provider_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_provider_test",
        resource_id=str(provider_id),
        additional_context={
            "customer_id": current_user.customer_id,
            "last_test_status": tested.last_test_status,
            "last_test_error": tested.last_test_error,
        },
    )
    return tested


@router.get(
    "/sso/domains",
    response_model=list[TenantSSODomainResponse],
    summary="List tenant SSO domains",
    description="List domain verification rows for the current tenant.",
)
async def list_tenant_sso_domains(
    db: Session = Depends(get_db),
    current_user=Depends(
        auth_middleware.require_any_permission(
            ["admin:settings:read", "admin:settings:update", "platform:admin"]
        )
    ),
):
    """List SSO domains for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    return service.list_domains(current_user.customer_id)


@router.post(
    "/sso/domains",
    response_model=TenantSSODomainResponse,
    summary="Add tenant SSO domain",
    description="Add a domain for DNS TXT verification in the current tenant.",
)
async def create_tenant_sso_domain(
    request: TenantSSODomainCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Create an SSO domain row for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    try:
        created = service.create_domain(current_user.customer_id, request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_domain",
        resource_id=str(created.id),
        additional_context={
            "customer_id": current_user.customer_id,
            "domain": created.domain,
            "status": created.status.value,
        },
    )
    return created


@router.post(
    "/sso/domains/{domain_id}/verify",
    response_model=TenantSSODomainResponse,
    summary="Verify tenant SSO domain",
    description="Perform DNS TXT verification for a tenant domain.",
)
async def verify_tenant_sso_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Verify one SSO domain for the current tenant via DNS TXT lookup."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    try:
        verified = service.verify_domain(current_user.customer_id, domain_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_domain_verify",
        resource_id=str(domain_id),
        additional_context={
            "customer_id": current_user.customer_id,
            "domain": verified.domain,
            "status": verified.status.value,
            "last_check_error": verified.last_check_error,
        },
    )
    return verified


@router.delete(
    "/sso/domains/{domain_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tenant SSO domain",
    description="Delete one tenant domain verification row.",
)
async def delete_tenant_sso_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth_middleware.require_permission("admin:settings:update")),
):
    """Delete one SSO domain for the current tenant."""
    _assert_tenant_can_use_sso(db, current_user.customer_id)
    service = TenantSSOProviderService(db)
    try:
        service.delete_domain(current_user.customer_id, domain_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    await audit_service.log_event(
        AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user.user_id,
        resource_type="tenant_sso_domain",
        resource_id=str(domain_id),
        additional_context={
            "customer_id": current_user.customer_id,
            "deleted": True,
        },
    )


# ============================================================================
# OBJECT STORAGE ENDPOINTS
# ============================================================================

@router.get(
    "/storage",
    response_model=TenantObjectStorageSettingsResponse,
    summary="Get tenant object storage settings",
    description="Get tenant-scoped document storage settings (S3/MinIO).",
)
async def get_tenant_storage_settings(
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("workspaces:write")),
):
    """Get object storage settings for the current tenant."""
    service = TenantStorageSettingsService(db)
    try:
        return service.get_storage_settings(current_user.customer_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.put(
    "/storage",
    response_model=TenantObjectStorageSettingsResponse,
    summary="Update tenant object storage settings",
    description="Create or update tenant-scoped S3/MinIO settings for document storage.",
)
async def update_tenant_storage_settings(
    request: TenantObjectStorageSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("workspaces:write")),
):
    """Update object storage settings for the current tenant."""
    service = TenantStorageSettingsService(db)
    try:
        updated = service.update_storage_settings(current_user.customer_id, request)
        logger.info(
            "tenant_storage_settings_updated",
            customer_id=current_user.customer_id,
            user_id=current_user.user_id,
            backend=updated.backend.value if updated.backend else None,
            bucket=updated.bucket,
        )
        return updated
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
