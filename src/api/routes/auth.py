"""
AI Enablement Platform - Authentication API Routes

FastAPI routes for user authentication, session management, and RBAC operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlencode
import logging

from src.core.config import get_settings
from src.services.auth_service import auth_service, AuthenticationError
from src.services.audit_service import audit_service, AuditAction
from src.services.security_service import security_service
from src.services.tenant_sso_runtime_service import (
    SSOAuthenticationError,
    SSOConfigurationError,
    SSOProvisioningError,
    SSOResolutionError,
    TenantSSORuntimeService,
)
from src.models.auth import User
from src.middleware.authorization import (
    get_current_user,
    require_permission,
)
from src.core.auth_context import CurrentUserContext
from src.models.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)
settings = get_settings()


def get_customer_display_name(db: Session, customer_id: str) -> Optional[str]:
    """
    Get the display name for a customer/tenant.
    Returns the display_name or name of the customer.
    """
    if not customer_id:
        return None
    
    from src.models.customer import Customer
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if customer:
        return customer.display_name or customer.name
    return customer_id  # Fall back to customer_id if no customer found


def get_allocated_features(db: Session, customer_id: str) -> List[str]:
    """
    Get list of allocated feature keys for a customer/tenant.
    Returns feature keys that are enabled for this tenant.
    """
    from src.models.tenant_admin import TenantFeatureAllocation, PlatformFeature
    
    if not customer_id:
        return []
    
    # Platform admin sees all features
    # Get all enabled features for this tenant
    allocations = db.query(TenantFeatureAllocation).join(
        PlatformFeature
    ).filter(
        TenantFeatureAllocation.customer_id == customer_id,
        TenantFeatureAllocation.is_enabled == True
    ).all()
    
    return [a.feature.feature_key for a in allocations]


def _build_frontend_sso_success_redirect(access_token: str, refresh_token: str) -> str:
    """Build frontend redirect URL carrying issued tokens in URL fragment."""
    callback_base = f"{settings.frontend_url.rstrip('/')}/auth/sso/callback"
    fragment = urlencode(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    )
    return f"{callback_base}#{fragment}"


def _build_frontend_sso_error_redirect(message: str) -> str:
    """Build frontend login redirect URL with an SSO error message."""
    login_url = f"{settings.frontend_url.rstrip('/')}/login"
    return f"{login_url}?{urlencode({'message': message})}"


router = APIRouter()
security = HTTPBearer()


# Pydantic models for request/response
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: 'UserProfile'


class SSODiscoveryProvider(BaseModel):
    """Minimal provider info for the unauthenticated login page."""

    id: int
    provider_type: Optional[str] = None
    protocol: Optional[str] = None
    display_name: Optional[str] = None


class SSODiscoveryResponse(BaseModel):
    """Available SSO providers across the deployment (no auth required)."""

    providers: List[SSODiscoveryProvider] = Field(default_factory=list)


class SSOLoginOptionsResponse(BaseModel):
    """Public login policy + available auth methods for an email/tenant context."""

    email: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None

    login_mode: str
    sso_login_available: bool
    password_login_allowed: bool
    requires_sso: bool
    break_glass_allowed: bool

    provider_type: Optional[str] = None
    protocol: Optional[str] = None
    provider_display_name: Optional[str] = None
    provider_id: Optional[int] = None
    providers: List[Dict[str, Any]] = Field(default_factory=list)


class UserProfile(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    first_name: Optional[str] = None  # Extracted from full_name or username
    is_active: bool
    is_superuser: bool
    roles: List[str]
    permissions: List[str]
    primary_role: Optional[str]
    last_login_at: Optional[datetime]
    created_at: datetime
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None  # Display name of the tenant/organization
    allocated_features: List[str] = []  # Feature keys allocated to user's tenant
    tenant_memberships: List['TenantMembership'] = []  # All tenants user belongs to
    has_multiple_tenants: bool = False  # Quick flag for UI

    class Config:
        from_attributes = True

    @staticmethod
    def _extract_first_name(full_name: Optional[str], username: str) -> str:
        """Extract first name from full_name, falling back to username."""
        if full_name and full_name.strip():
            # Get first word from full name
            return full_name.strip().split()[0]
        # Fall back to username
        return username

    @classmethod
    def from_user(cls, user: User, allocated_features: List[str] = None, customer_name: str = None, tenant_memberships: List['TenantMembership'] = None) -> 'UserProfile':
        """Create UserProfile from User model."""
        memberships = tenant_memberships or []
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            first_name=cls._extract_first_name(user.full_name, user.username),
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            roles=[role.name for role in user.roles],
            permissions=user.get_permissions(),
            primary_role=user.primary_role.name if user.primary_role else None,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            customer_id=user.customer_id,
            customer_name=customer_name,
            allocated_features=allocated_features or [],
            tenant_memberships=memberships,
            has_multiple_tenants=len(memberships) > 1
        )

    @classmethod
    def from_user_context(cls, user: CurrentUserContext, allocated_features: List[str] = None, customer_name: str = None, tenant_memberships: List['TenantMembership'] = None) -> 'UserProfile':
        """Create UserProfile from CurrentUserContext DTO."""
        username = user.username or user.email
        memberships = tenant_memberships or []
        return cls(
            id=user.user_id,
            email=user.email,
            username=username,
            full_name=user.full_name,
            first_name=cls._extract_first_name(user.full_name, username),
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            roles=user.roles,
            permissions=user.permissions,
            primary_role=user.primary_role,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            customer_id=user.customer_id,
            customer_name=customer_name,
            allocated_features=allocated_features or [],
            tenant_memberships=memberships,
            has_multiple_tenants=len(memberships) > 1
        )


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    roles: List[str] = []


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class PermissionCheckRequest(BaseModel):
    permissions: List[str]
    require_all: bool = False


class PermissionCheckResponse(BaseModel):
    has_permission: bool
    missing_permissions: List[str] = []


class SessionInfo(BaseModel):
    session_token: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    device_fingerprint: Optional[str]
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    is_current: bool = False


class UserSessionsResponse(BaseModel):
    sessions: List[SessionInfo]
    total_count: int


# Multi-tenant support models
class TenantMembership(BaseModel):
    """Represents a user's membership in a tenant."""
    customer_id: str
    customer_name: str
    is_default: bool
    first_login_completed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TenantMembershipsResponse(BaseModel):
    """Response containing all tenant memberships for a user."""
    memberships: List[TenantMembership]
    current_tenant_id: str
    total_count: int


class SwitchTenantRequest(BaseModel):
    """Request to switch active tenant."""
    customer_id: str


class SwitchTenantResponse(BaseModel):
    """Response after switching tenant."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: 'UserProfile'
    message: str
    show_welcome_popup: bool = False  # True if first login to this tenant


class SetDefaultTenantRequest(BaseModel):
    """Request to set default tenant."""
    customer_id: str


class SetDefaultTenantResponse(BaseModel):
    """Response after setting default tenant."""
    success: bool
    message: str
    default_tenant_id: str


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and create session.
    
    Returns JWT access token and refresh token for authenticated user.
    Includes tenant memberships for multi-tenant users.
    """
    try:
        # Get client IP and user agent
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")

        # Generate device fingerprint from available headers
        device_fingerprint = _generate_device_fingerprint(request)

        runtime_service = TenantSSORuntimeService(db)
        try:
            runtime_service.assert_password_login_allowed(login_data.email)
        except SSOAuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

        user, access_token, refresh_token = await auth_service.authenticate_user(
            email=login_data.email,
            password=login_data.password,
            ip_address=client_ip,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint
        )
        
        # Ensure user has a tenant membership (backward compatibility)
        ensure_tenant_membership(db, user.id, user.customer_id)
        
        # Get tenant memberships
        tenant_memberships = get_user_tenant_memberships(db, user.id)
        
        # Get allocated features for this user's tenant
        allocated_features = get_allocated_features(db, user.customer_id)
        
        # Platform admins see all features
        if 'platform:admin' in user.get_permissions():
            from src.models.tenant_admin import PlatformFeature
            all_features = db.query(PlatformFeature).filter(PlatformFeature.is_active == True).all()
            allocated_features = [f.feature_key for f in all_features]
        
        # Get customer display name
        customer_name = get_customer_display_name(db, user.customer_id)
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=8 * 3600,  # 8 hours in seconds
            user=UserProfile.from_user(
                user, 
                allocated_features=allocated_features, 
                customer_name=customer_name,
                tenant_memberships=tenant_memberships
            )
        )
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/sso/discovery", response_model=SSODiscoveryResponse)
async def discover_sso_providers(db: Session = Depends(get_db)):
    """Return all runtime-enabled SSO providers for the login page.

    This is an unauthenticated endpoint that returns only minimal, non-secret
    provider metadata so the login page can render branded SSO buttons before
    the user enters an email address.
    """
    runtime_service = TenantSSORuntimeService(db)
    raw = runtime_service.discover_providers()
    return SSODiscoveryResponse(
        providers=[SSODiscoveryProvider(**p) for p in raw],
    )


@router.get("/sso/options", response_model=SSOLoginOptionsResponse)
async def get_sso_login_options(
    email: EmailStr = Query(..., description="User email used to resolve tenant login policy"),
    customer_id: Optional[str] = Query(
        default=None, description="Optional tenant context override"
    ),
    db: Session = Depends(get_db),
):
    """Return available login methods for the resolved tenant context."""
    runtime_service = TenantSSORuntimeService(db)
    try:
        resolution = runtime_service.resolve_login(email=email, customer_id=customer_id)
    except SSOResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SSOLoginOptionsResponse(
        email=resolution.email,
        customer_id=resolution.customer_id,
        customer_name=resolution.customer_name,
        login_mode=resolution.login_mode,
        sso_login_available=resolution.sso_login_available,
        password_login_allowed=resolution.password_login_allowed,
        requires_sso=resolution.requires_sso,
        break_glass_allowed=resolution.break_glass_allowed,
        provider_type=resolution.provider_type,
        protocol=resolution.protocol,
        provider_display_name=resolution.provider_display_name,
        provider_id=resolution.provider_id,
        providers=resolution.providers or [],
    )


@router.get("/sso/oidc/start")
async def start_oidc_sso_login(
    request: Request,
    email: Optional[EmailStr] = Query(
        default=None,
        description="Optional user email used to resolve tenant policy",
    ),
    customer_id: Optional[str] = Query(
        default=None, description="Optional tenant context override"
    ),
    provider_id: Optional[int] = Query(
        default=None, description="Optional SSO provider ID when multiple are configured"
    ),
    db: Session = Depends(get_db),
):
    """Start OIDC SSO login flow by redirecting to the IdP authorize URL."""
    runtime_service = TenantSSORuntimeService(db)
    try:
        if email:
            resolution = runtime_service.get_sso_config_for_login(
                email=email,
                customer_id=customer_id,
                expected_protocol="oidc",
                provider_id=provider_id,
            )
        else:
            resolution = runtime_service.get_sso_config_for_start(
                expected_protocol="oidc",
                customer_id=customer_id,
                provider_id=provider_id,
            )
        callback_url = str(request.url_for("oidc_sso_callback"))
        authorize_url = await runtime_service.build_oidc_authorize_url(
            resolution=resolution,
            callback_url=callback_url,
        )
        return RedirectResponse(url=authorize_url, status_code=status.HTTP_302_FOUND)
    except (SSOResolutionError, SSOConfigurationError, SSOAuthenticationError) as exc:
        return RedirectResponse(
            url=_build_frontend_sso_error_redirect(str(exc)),
            status_code=status.HTTP_302_FOUND,
        )


@router.get("/sso/oidc/callback", name="oidc_sso_callback")
async def oidc_sso_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle OIDC callback, issue local session tokens, and redirect to frontend."""
    runtime_service = TenantSSORuntimeService(db)
    try:
        state_payload = runtime_service.decode_state_token(
            state_token=state,
            expected_purpose=TenantSSORuntimeService.OIDC_STATE_PURPOSE,
        )
        state_email = state_payload.get("email")
        if state_email:
            resolution = runtime_service.get_sso_config_for_login(
                email=state_email,
                customer_id=state_payload.get("customer_id"),
                expected_protocol="oidc",
                provider_id=state_payload.get("provider_id"),
            )
        else:
            resolution = runtime_service.get_sso_config_for_customer(
                customer_id=state_payload.get("customer_id"),
                expected_protocol="oidc",
                provider_id=state_payload.get("provider_id"),
            )

        callback_url = str(request.url_for("oidc_sso_callback"))
        claims = await runtime_service.exchange_oidc_code(
            resolution=resolution,
            authorization_code=code,
            callback_url=callback_url,
            state_payload=state_payload,
        )
        identity = runtime_service.extract_identity_from_claims(claims)
        if not identity.get("subject"):
            raise SSOAuthenticationError("OIDC response missing subject claim.")

        user = runtime_service.link_or_provision_user(
            resolution=resolution,
            subject=identity["subject"],
            email=identity.get("email"),
            full_name=identity.get("full_name"),
            claims=claims,
        )

        access_token, refresh_token = await auth_service.create_session_for_user(
            user=user,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            device_fingerprint=_generate_device_fingerprint(request),
        )

        await audit_service.log_event(
            AuditAction.LOGIN_SUCCESS,
            user_id=user.id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            additional_context={
                "auth_method": "sso",
                "sso_protocol": resolution.protocol,
                "sso_provider_type": resolution.provider_type,
                "customer_id": resolution.customer_id,
            },
        )

        return RedirectResponse(
            url=_build_frontend_sso_success_redirect(access_token, refresh_token),
            status_code=status.HTTP_302_FOUND,
        )
    except (SSOResolutionError, SSOConfigurationError, SSOAuthenticationError, SSOProvisioningError) as exc:
        logger.exception("OIDC SSO callback failed: %s", exc)
        return RedirectResponse(
            url=_build_frontend_sso_error_redirect(str(exc)),
            status_code=status.HTTP_302_FOUND,
        )


@router.get("/sso/saml/start")
async def start_saml_sso_login(
    request: Request,
    email: EmailStr = Query(..., description="User email used to resolve tenant policy"),
    customer_id: Optional[str] = Query(
        default=None, description="Optional tenant context override"
    ),
    provider_id: Optional[int] = Query(
        default=None, description="Optional SSO provider ID when multiple are configured"
    ),
    db: Session = Depends(get_db),
):
    """Start SAML login flow by redirecting to IdP with AuthnRequest."""
    runtime_service = TenantSSORuntimeService(db)
    try:
        resolution = runtime_service.get_sso_config_for_login(
            email=email,
            customer_id=customer_id,
            expected_protocol="saml",
            provider_id=provider_id,
        )
        acs_url = str(request.url_for("saml_sso_acs"))
        saml_redirect_url = runtime_service.build_saml_redirect_url(
            resolution=resolution,
            acs_url=acs_url,
        )
        return RedirectResponse(url=saml_redirect_url, status_code=status.HTTP_302_FOUND)
    except (SSOResolutionError, SSOConfigurationError, SSOAuthenticationError) as exc:
        return RedirectResponse(
            url=_build_frontend_sso_error_redirect(str(exc)),
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/sso/saml/acs", response_class=HTMLResponse, name="saml_sso_acs")
async def saml_sso_acs(
    request: Request,
    saml_response: str = Form(..., alias="SAMLResponse"),
    relay_state: Optional[str] = Form(None, alias="RelayState"),
    db: Session = Depends(get_db),
):
    """
    SAML Assertion Consumer Service endpoint.

    Consumes IdP POSTed assertions, resolves user identity, and redirects to frontend.
    """
    runtime_service = TenantSSORuntimeService(db)
    try:
        if not relay_state:
            raise SSOAuthenticationError("SAML relay state is required.")

        state_payload = runtime_service.decode_state_token(
            state_token=relay_state,
            expected_purpose=TenantSSORuntimeService.SAML_STATE_PURPOSE,
        )
        resolution = runtime_service.get_sso_config_for_login(
            email=state_payload["email"],
            customer_id=state_payload.get("customer_id"),
            expected_protocol="saml",
            provider_id=state_payload.get("provider_id"),
        )

        expected_audience = (resolution.config.config_data or {}).get("saml_entity_id") if resolution.config else None
        claims = runtime_service.parse_saml_response(
            saml_response_b64=saml_response,
            expected_audience=expected_audience,
            provider_config=resolution.config,
        )
        identity = runtime_service.extract_identity_from_claims(claims)
        if not identity.get("subject"):
            raise SSOAuthenticationError("SAML assertion missing subject.")

        user = runtime_service.link_or_provision_user(
            resolution=resolution,
            subject=identity["subject"],
            email=identity.get("email"),
            full_name=identity.get("full_name"),
            claims=claims,
        )

        access_token, refresh_token = await auth_service.create_session_for_user(
            user=user,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            device_fingerprint=_generate_device_fingerprint(request),
        )

        await audit_service.log_event(
            AuditAction.LOGIN_SUCCESS,
            user_id=user.id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            additional_context={
                "auth_method": "sso",
                "sso_protocol": resolution.protocol,
                "sso_provider_type": resolution.provider_type,
                "customer_id": resolution.customer_id,
            },
        )

        return RedirectResponse(
            url=_build_frontend_sso_success_redirect(access_token, refresh_token),
            status_code=status.HTTP_302_FOUND,
        )
    except (SSOResolutionError, SSOConfigurationError, SSOAuthenticationError, SSOProvisioningError) as exc:
        logger.exception("SAML ACS processing failed: %s", exc)
        return RedirectResponse(
            url=_build_frontend_sso_error_redirect(str(exc)),
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(refresh_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token.
    
    Returns new access token and refresh token.
    """
    try:
        access_token, new_refresh_token = await auth_service.refresh_token(
            refresh_data.refresh_token
        )
        
        # Get user info for response
        payload = await auth_service.verify_token(access_token)
        user_id = int(payload.get("sub"))
        user = await auth_service.get_user_by_id(user_id)
        
        # Get allocated features for this user's tenant
        allocated_features = get_allocated_features(db, user.customer_id)
        
        # Platform admins see all features
        if 'platform:admin' in user.get_permissions():
            from src.models.tenant_admin import PlatformFeature
            all_features = db.query(PlatformFeature).filter(PlatformFeature.is_active == True).all()
            allocated_features = [f.feature_key for f in all_features]
        
        # Get customer display name
        customer_name = get_customer_display_name(db, user.customer_id)
        
        # Get tenant memberships
        tenant_memberships = get_user_tenant_memberships(db, user.id)
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=8 * 3600,
            user=UserProfile.from_user(
                user, 
                allocated_features=allocated_features, 
                customer_name=customer_name,
                tenant_memberships=tenant_memberships
            )
        )
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/logout")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Logout user and invalidate session.
    """
    try:
        token = credentials.credentials
        payload = await auth_service.verify_token(token)
        session_token = payload.get("session_token")
        
        await auth_service.logout(session_token)
        
        return {"message": "Successfully logged out"}
        
    except AuthenticationError:
        # Even if token is invalid, consider logout successful
        return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user profile information.
    """
    # Get allocated features for this user's tenant
    allocated_features = get_allocated_features(db, current_user.customer_id)
    
    # Platform admins see all features
    if current_user.has_permission('platform:admin'):
        from src.models.tenant_admin import PlatformFeature
        all_features = db.query(PlatformFeature).filter(PlatformFeature.is_active == True).all()
        allocated_features = [f.feature_key for f in all_features]
    
    # Get customer display name
    customer_name = get_customer_display_name(db, current_user.customer_id)
    
    # Get tenant memberships
    tenant_memberships = get_user_tenant_memberships(db, current_user.user_id)
    
    return UserProfile.from_user_context(
        current_user, 
        allocated_features=allocated_features, 
        customer_name=customer_name,
        tenant_memberships=tenant_memberships
    )


@router.post("/check-permissions", response_model=PermissionCheckResponse)
async def check_permissions(
    permission_check: PermissionCheckRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Check if current user has specified permissions.
    """
    if permission_check.require_all:
        has_permission = current_user.has_all_permissions(permission_check.permissions)
        missing_permissions = [
            perm for perm in permission_check.permissions 
            if not current_user.has_permission(perm)
        ]
    else:
        has_permission = current_user.has_any_permission(permission_check.permissions)
        missing_permissions = permission_check.permissions if not has_permission else []
    
    return PermissionCheckResponse(
        has_permission=has_permission,
        missing_permissions=missing_permissions
    )


@router.post("/users", response_model=UserProfile)
async def create_user(
    user_data: CreateUserRequest,
    current_user: CurrentUserContext = Depends(require_permission("users:invite"))
):
    """
    Create new user account.
    
    Requires 'users:create' permission.
    """
    try:
        is_valid, errors = await security_service.validate_password_policy(
            user_data.password
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(errors),
            )

        new_user = await auth_service.create_user(
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            customer_id=current_user.customer_id,
            role_names=user_data.roles,
            created_by_id=current_user.user_id
        )
        
        return UserProfile.from_user(new_user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/me/password")
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change current user's password.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify current password
    if not user.verify_password(password_data.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    is_valid, errors = await security_service.validate_password_policy(
        password_data.new_password,
        user_id=user.id,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )
    
    # Set new password
    user.set_password(password_data.new_password)
    db.commit()

    await audit_service.log_event(
        AuditAction.PASSWORD_CHANGED,
        user_id=user.id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        additional_context={"auth_method": "password"},
    )
    
    return {"message": "Password changed successfully"}


@router.get("/health")
async def auth_health_check():
    """
    Health check for authentication service.
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "jwt_auth": True,
            "session_management": True,
            "rbac": True,
            "audit_logging": True,
            "concurrent_session_limits": True,
            "device_fingerprinting": True
        }
    }


def _generate_device_fingerprint(request: Request) -> str:
    """Generate device fingerprint from request headers."""
    import hashlib

    # Collect available headers for fingerprinting
    fingerprint_data = []
    fingerprint_data.append(request.client.host or "")
    fingerprint_data.append(request.headers.get("user-agent", ""))
    fingerprint_data.append(request.headers.get("accept-language", ""))
    fingerprint_data.append(request.headers.get("accept-encoding", ""))
    fingerprint_data.append(request.headers.get("accept", ""))

    # Create hash from combined data
    combined_data = "|".join(fingerprint_data)
    return hashlib.sha256(combined_data.encode()).hexdigest()[:32]


@router.get("/sessions", response_model=UserSessionsResponse)
async def get_user_sessions(current_user: CurrentUserContext = Depends(get_current_user)):
    """
    Get all active sessions for the current user.
    """
    sessions = await auth_service.get_user_active_sessions(current_user.user_id)

    # Get current session token from the request context
    # This would need to be passed through the dependency
    current_session_token = None  # TODO: Get from request context

    session_info = []
    for session in sessions:
        session_info.append(SessionInfo(
            session_token=session.session_token[:8] + "...",  # Truncate for security
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            device_fingerprint=session.device_fingerprint[:8] + "..." if session.device_fingerprint else None,
            created_at=session.created_at,
            last_activity_at=session.last_activity_at,
            expires_at=session.expires_at,
            is_current=(session.session_token == current_session_token)
        ))

    return UserSessionsResponse(
        sessions=session_info,
        total_count=len(session_info)
    )


@router.delete("/sessions/{session_token}")
async def terminate_session(
    session_token: str,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Terminate a specific session.
    """
    success = await auth_service.terminate_session(session_token, current_user.user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already terminated"
        )

    return {"message": "Session terminated successfully"}


@router.delete("/sessions")
async def terminate_all_sessions(
    current_user: CurrentUserContext = Depends(get_current_user),
    except_current: bool = True
):
    """
    Terminate all sessions for the current user.
    """
    current_session_token = None  # TODO: Get from request context
    except_session = current_session_token if except_current else None

    count = await auth_service.terminate_all_user_sessions(
        current_user.user_id,
        except_session=except_session
    )

    return {
        "message": f"Terminated {count} sessions",
        "terminated_count": count
    }


# =============================================================================
# INVITE ACCEPTANCE (PUBLIC - No Auth Required)
# =============================================================================

class InviteInfoResponse(BaseModel):
    """Response model for invite validation."""
    email: str
    full_name: Optional[str]
    customer_name: str
    customer_id: str
    is_valid: bool
    expires_at: datetime
    user_exists: bool = False  # True if user already has an account
    
    class Config:
        from_attributes = True


class AcceptInviteRequest(BaseModel):
    """Request model for accepting an invite."""
    token: str
    password: str
    confirm_password: str


class AcceptInviteExistingUserRequest(BaseModel):
    """Request model for existing users to accept an invite."""
    token: str


class AcceptInviteResponse(BaseModel):
    """Response model for successful invite acceptance."""
    message: str
    email: str
    customer_id: str


@router.get("/invite/{token}", response_model=InviteInfoResponse)
async def get_invite_info(token: str):
    """
    Get invite information by token (public endpoint).
    
    Used to validate invite and show user info before they set their password.
    """
    from src.models.database import SessionLocal, init_database
    from src.models.tenant_admin import UserInvite
    from src.models.customer import Customer
    from datetime import datetime, timezone
    
    if SessionLocal is None:
        init_database()
    db = SessionLocal()
    try:
        # Find the invite
        invite = db.query(UserInvite).filter(
            UserInvite.invite_token == token
        ).first()
        
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired invite link"
            )
        
        # Check if already accepted
        if invite.status == "accepted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite has already been used"
            )
        
        # Check if expired
        now = datetime.now(timezone.utc)
        expires_at = invite.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        is_valid = invite.status == "pending" and expires_at > now
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite has expired. Please request a new invite."
            )
        
        # Get customer info
        customer = db.query(Customer).filter(
            Customer.customer_id == invite.customer_id
        ).first()
        
        # Check if user already exists (case-insensitive)
        from src.models.auth import User
        existing_user = db.query(User).filter(func.lower(User.email) == func.lower(invite.email)).first()
        
        return InviteInfoResponse(
            email=invite.email,
            full_name=invite.full_name,
            customer_name=customer.display_name or customer.name if customer else invite.customer_id,
            customer_id=invite.customer_id,
            is_valid=is_valid,
            expires_at=invite.expires_at,
            user_exists=existing_user is not None
        )
    finally:
        db.close()


@router.post("/invite/accept", response_model=AcceptInviteResponse)
async def accept_invite(request: AcceptInviteRequest):
    """
    Accept an invite and create user account (public endpoint).
    
    Creates the user, assigns pre-configured roles, and marks invite as accepted.
    """
    from src.models.database import SessionLocal, init_database
    from src.models.tenant_admin import UserInvite
    from src.models.auth import User, Role
    from src.models.customer import Customer
    from datetime import datetime, timezone
    
    # Validate passwords match
    if request.password != request.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    
    # Validate password strength via centralized security policy
    is_valid, errors = await security_service.validate_password_policy(request.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )
    
    if SessionLocal is None:
        init_database()
    db = SessionLocal()
    try:
        # Find and validate the invite
        invite = db.query(UserInvite).filter(
            UserInvite.invite_token == request.token
        ).first()
        
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired invite link"
            )
        
        if invite.status == "accepted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite has already been used"
            )
        
        # Check expiration
        now = datetime.now(timezone.utc)
        expires_at = invite.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if invite.status != "pending" or expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite has expired. Please request a new invite."
            )
        
        # Check if user already exists (case-insensitive)
        existing_user = db.query(User).filter(func.lower(User.email) == func.lower(invite.email)).first()
        if existing_user:
            # User exists - add them to this tenant instead of creating new account
            from src.models.auth import UserTenantMembership
            
            # Check if they're already a member of this tenant
            existing_membership = db.query(UserTenantMembership).filter(
                UserTenantMembership.user_id == existing_user.id,
                UserTenantMembership.customer_id == invite.customer_id
            ).first()
            
            if existing_membership:
                # Already a member - just mark invite as accepted
                invite.status = "accepted"
                invite.accepted_at = datetime.now(timezone.utc)
                invite.accepted_by_user_id = existing_user.id
                db.commit()
                
                return AcceptInviteResponse(
                    message="You're already a member of this organization. Please log in.",
                    email=invite.email,
                    customer_id=invite.customer_id
                )
            
            # Create new membership for existing user
            new_membership = UserTenantMembership(
                user_id=existing_user.id,
                customer_id=invite.customer_id,
                is_default=False,  # Don't change their default
                first_login_completed=False  # Will show welcome popup
            )
            db.add(new_membership)
            
            # Assign roles to user for this tenant
            if invite.role_ids:
                for role_id in invite.role_ids:
                    role = db.query(Role).filter(
                        Role.id == role_id,
                        Role.customer_id == invite.customer_id
                    ).first()
                    if role and role not in existing_user.roles:
                        existing_user.roles.append(role)
            else:
                # Assign default viewer role
                viewer_role = db.query(Role).filter(
                    Role.name == "viewer",
                    Role.customer_id == invite.customer_id
                ).first()
                if viewer_role and viewer_role not in existing_user.roles:
                    existing_user.roles.append(viewer_role)
            
            # Mark invite as accepted
            invite.status = "accepted"
            invite.accepted_at = datetime.now(timezone.utc)
            invite.accepted_by_user_id = existing_user.id
            
            # Update customer user count
            customer = db.query(Customer).filter(
                Customer.customer_id == invite.customer_id
            ).first()
            if customer:
                customer.current_users = (customer.current_users or 0) + 1
            
            db.commit()
            
            customer_name = customer.display_name or customer.name if customer else invite.customer_id
            logger.info(f"Existing user {invite.email} added to tenant {invite.customer_id}")
            
            return AcceptInviteResponse(
                message=f"You've been added to {customer_name}! Log in and use the tenant switcher to access it.",
                email=invite.email,
                customer_id=invite.customer_id
            )
        
        # Generate username from email
        username = invite.email.split('@')[0]
        # Ensure uniqueness (case-insensitive)
        base_username = username
        counter = 1
        while db.query(User).filter(func.lower(User.username) == func.lower(username)).first():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create the user
        new_user = User(
            email=invite.email,
            username=username,
            full_name=invite.full_name,
            hashed_password="",
            customer_id=invite.customer_id,
            is_active=True,
            is_superuser=False
        )
        new_user.set_password(request.password)
        db.add(new_user)
        db.flush()  # Get the user ID
        
        # Assign pre-configured roles
        if invite.role_ids:
            for role_id in invite.role_ids:
                role = db.query(Role).filter(
                    Role.id == role_id,
                    Role.customer_id == invite.customer_id
                ).first()
                if role:
                    new_user.roles.append(role)
        else:
            # Assign default viewer role if no roles specified
            viewer_role = db.query(Role).filter(
                Role.name == "viewer",
                Role.customer_id == invite.customer_id
            ).first()
            if viewer_role:
                new_user.roles.append(viewer_role)
        
        # Mark invite as accepted
        invite.status = "accepted"
        invite.accepted_at = datetime.now(timezone.utc)
        invite.accepted_by_user_id = new_user.id
        
        # Update customer user count
        customer = db.query(Customer).filter(
            Customer.customer_id == invite.customer_id
        ).first()
        if customer:
            customer.current_users = (customer.current_users or 0) + 1
        
        db.commit()
        
        logger.info(f"User {invite.email} accepted invite and joined {invite.customer_id}")
        
        # Create tenant membership for the new user
        from src.models.auth import UserTenantMembership
        membership = UserTenantMembership(
            user_id=new_user.id,
            customer_id=invite.customer_id,
            is_default=True,  # First tenant is default
            first_login_completed=False  # Will show welcome info on first login
        )
        db.add(membership)
        
        db.commit()
        
        logger.info(f"User {invite.email} accepted invite and joined {invite.customer_id}")
        
        return AcceptInviteResponse(
            message="Account created successfully! You can now log in.",
            email=invite.email,
            customer_id=invite.customer_id
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error accepting invite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating your account"
        )
    finally:
        db.close()


@router.post("/invite/accept-existing", response_model=AcceptInviteResponse)
async def accept_invite_existing_user(request: AcceptInviteExistingUserRequest):
    """
    Accept an invite for an existing user (public endpoint).
    
    This endpoint is for users who already have an account and are being
    invited to a new tenant. No password required - they just need to
    click accept and then log in.
    """
    from src.models.database import SessionLocal, init_database
    from src.models.tenant_admin import UserInvite
    from src.models.auth import User, Role, UserTenantMembership
    from src.models.customer import Customer
    from datetime import datetime, timezone
    
    if SessionLocal is None:
        init_database()
    db = SessionLocal()
    try:
        # Find and validate the invite
        invite = db.query(UserInvite).filter(
            UserInvite.invite_token == request.token
        ).first()
        
        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired invite link"
            )
        
        if invite.status == "accepted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite has already been used"
            )
        
        # Check expiration
        now = datetime.now(timezone.utc)
        expires_at = invite.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if invite.status != "pending" or expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite has expired. Please request a new invite."
            )
        
        # Find the existing user (case-insensitive)
        existing_user = db.query(User).filter(func.lower(User.email) == func.lower(invite.email)).first()
        
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No existing account found. Please use the password form to create an account."
            )
        
        # Check if they're already a member of this tenant
        existing_membership = db.query(UserTenantMembership).filter(
            UserTenantMembership.user_id == existing_user.id,
            UserTenantMembership.customer_id == invite.customer_id
        ).first()
        
        if existing_membership:
            # Already a member - just mark invite as accepted
            invite.status = "accepted"
            invite.accepted_at = datetime.now(timezone.utc)
            invite.accepted_by_user_id = existing_user.id
            db.commit()
            
            return AcceptInviteResponse(
                message="You're already a member of this organization. Please log in.",
                email=invite.email,
                customer_id=invite.customer_id
            )
        
        # Create new membership for existing user
        new_membership = UserTenantMembership(
            user_id=existing_user.id,
            customer_id=invite.customer_id,
            is_default=False,  # Don't change their default
            first_login_completed=False  # Will show welcome popup
        )
        db.add(new_membership)
        
        # Assign roles to user for this tenant
        if invite.role_ids:
            for role_id in invite.role_ids:
                role = db.query(Role).filter(
                    Role.id == role_id,
                    Role.customer_id == invite.customer_id
                ).first()
                if role and role not in existing_user.roles:
                    existing_user.roles.append(role)
        else:
            # Assign default viewer role
            viewer_role = db.query(Role).filter(
                Role.name == "viewer",
                Role.customer_id == invite.customer_id
            ).first()
            if viewer_role and viewer_role not in existing_user.roles:
                existing_user.roles.append(viewer_role)
        
        # Mark invite as accepted
        invite.status = "accepted"
        invite.accepted_at = datetime.now(timezone.utc)
        invite.accepted_by_user_id = existing_user.id
        
        # Update customer user count
        customer = db.query(Customer).filter(
            Customer.customer_id == invite.customer_id
        ).first()
        if customer:
            customer.current_users = (customer.current_users or 0) + 1
        
        db.commit()
        
        customer_name = customer.display_name or customer.name if customer else invite.customer_id
        logger.info(f"Existing user {invite.email} added to tenant {invite.customer_id}")
        
        return AcceptInviteResponse(
            message=f"You've been added to {customer_name}! Log in and use the tenant switcher to access it.",
            email=invite.email,
            customer_id=invite.customer_id
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error accepting invite for existing user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the invite"
        )
    finally:
        db.close()


# ============================================================================
# Multi-Tenant Support Endpoints
# ============================================================================

def get_user_tenant_memberships(db: Session, user_id: int) -> List[TenantMembership]:
    """Get all tenant memberships for a user."""
    from src.models.auth import UserTenantMembership
    from src.models.customer import Customer
    
    memberships = db.query(UserTenantMembership).filter(
        UserTenantMembership.user_id == user_id
    ).all()
    
    result = []
    for m in memberships:
        customer = db.query(Customer).filter(Customer.customer_id == m.customer_id).first()
        customer_name = customer.display_name or customer.name if customer else m.customer_id
        
        result.append(TenantMembership(
            customer_id=m.customer_id,
            customer_name=customer_name,
            is_default=m.is_default,
            first_login_completed=m.first_login_completed,
            created_at=m.created_at
        ))
    
    return result


def ensure_tenant_membership(db: Session, user_id: int, customer_id: str) -> None:
    """Ensure a user has a membership record for their tenant (migration helper)."""
    from src.models.auth import UserTenantMembership
    
    existing = db.query(UserTenantMembership).filter(
        UserTenantMembership.user_id == user_id,
        UserTenantMembership.customer_id == customer_id
    ).first()
    
    if not existing:
        # Create membership for existing user (backward compatibility)
        membership = UserTenantMembership(
            user_id=user_id,
            customer_id=customer_id,
            is_default=True,
            first_login_completed=True  # Don't show popup for existing users
        )
        db.add(membership)
        db.commit()


@router.get("/tenants", response_model=TenantMembershipsResponse)
async def get_my_tenants(
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all tenants the current user belongs to.
    
    Returns list of tenant memberships with current active tenant.
    """
    # Ensure user has a membership (backward compatibility)
    ensure_tenant_membership(db, current_user.user_id, current_user.customer_id)
    
    memberships = get_user_tenant_memberships(db, current_user.user_id)
    
    return TenantMembershipsResponse(
        memberships=memberships,
        current_tenant_id=current_user.customer_id,
        total_count=len(memberships)
    )


@router.post("/switch-tenant", response_model=SwitchTenantResponse)
async def switch_tenant(
    request: Request,
    switch_request: SwitchTenantRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Switch to a different tenant.
    
    Issues new tokens with the target tenant as the active tenant.
    User must be a member of the target tenant.
    """
    from src.models.auth import UserTenantMembership, User, Role
    from src.models.customer import Customer
    
    target_tenant_id = switch_request.customer_id
    
    # Verify user has membership in target tenant
    membership = db.query(UserTenantMembership).filter(
        UserTenantMembership.user_id == current_user.user_id,
        UserTenantMembership.customer_id == target_tenant_id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this tenant"
        )
    
    # Get the user
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user's active tenant
    user.customer_id = target_tenant_id
    
    # Check if this is first login to this tenant
    show_welcome_popup = not membership.first_login_completed
    if show_welcome_popup:
        membership.first_login_completed = True
    
    db.commit()
    
    # Generate new tokens with the new tenant
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "")
    device_fingerprint = _generate_device_fingerprint(request)
    
    # Re-authenticate to get new tokens with updated customer_id
    db.refresh(user)
    
    # Generate new tokens using the auth service
    access_token, refresh_token = await auth_service.create_session_for_user(
        user=user,
        ip_address=client_ip,
        user_agent=user_agent,
        device_fingerprint=device_fingerprint
    )
    
    # Get allocated features for target tenant
    allocated_features = get_allocated_features(db, target_tenant_id)
    
    # Platform admins see all features
    if 'platform:admin' in user.get_permissions():
        from src.models.tenant_admin import PlatformFeature
        all_features = db.query(PlatformFeature).filter(PlatformFeature.is_active == True).all()
        allocated_features = [f.feature_key for f in all_features]
    
    # Get customer display name
    customer_name = get_customer_display_name(db, target_tenant_id)
    
    # Get tenant memberships for the user
    tenant_memberships = get_user_tenant_memberships(db, user.id)
    
    return SwitchTenantResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=8 * 3600,
        user=UserProfile.from_user(
            user, 
            allocated_features=allocated_features, 
            customer_name=customer_name,
            tenant_memberships=tenant_memberships
        ),
        message=f"Switched to {customer_name}",
        show_welcome_popup=show_welcome_popup
    )


@router.put("/default-tenant", response_model=SetDefaultTenantResponse)
async def set_default_tenant(
    request: SetDefaultTenantRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set the default tenant for the current user.
    
    The default tenant is used when logging in.
    """
    from src.models.auth import UserTenantMembership
    
    target_tenant_id = request.customer_id
    
    # Verify user has membership in target tenant
    target_membership = db.query(UserTenantMembership).filter(
        UserTenantMembership.user_id == current_user.user_id,
        UserTenantMembership.customer_id == target_tenant_id
    ).first()
    
    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this tenant"
        )
    
    # Clear default flag on all other memberships
    db.query(UserTenantMembership).filter(
        UserTenantMembership.user_id == current_user.user_id,
        UserTenantMembership.customer_id != target_tenant_id
    ).update({"is_default": False})
    
    # Set default flag on target membership
    target_membership.is_default = True
    
    db.commit()
    
    customer_name = get_customer_display_name(db, target_tenant_id)
    
    return SetDefaultTenantResponse(
        success=True,
        message=f"{customer_name} is now your default tenant",
        default_tenant_id=target_tenant_id
    )
