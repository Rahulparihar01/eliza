"""
SSO settings schemas.

Shared request/response models for tenant-scoped SSO config and
platform-scoped SSO policy.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class SSOProtocol(str, Enum):
    """Supported SSO protocols."""

    OIDC = "oidc"
    SAML = "saml"


class SSOProviderType(str, Enum):
    """Supported provider families."""

    AZURE = "azure"
    OKTA = "okta"
    GOOGLE = "google"
    GENERIC = "generic"


class SSOLoginMode(str, Enum):
    """Tenant login policy mode."""

    PASSWORD_ONLY = "password_only"
    SSO_OPTIONAL = "sso_optional"
    SSO_ENFORCED = "sso_enforced"


class SSODomainStatus(str, Enum):
    """Domain verification status values."""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


DEFAULT_ALLOWED_PROVIDER_TYPES = [
    SSOProviderType.AZURE,
    SSOProviderType.OKTA,
    SSOProviderType.GOOGLE,
    SSOProviderType.GENERIC,
]


class TenantSSOSettingsResponse(BaseModel):
    """Tenant SSO settings response (secrets never returned)."""

    is_enabled: bool
    login_mode: SSOLoginMode
    provider_type: Optional[SSOProviderType] = None
    protocol: Optional[SSOProtocol] = None
    provider_display_name: Optional[str] = None

    domain_allowlist: List[str] = Field(default_factory=list)
    domain_verification_required: bool = True

    jit_provisioning_enabled: bool = False
    jit_default_role: str = "viewer"

    # OIDC config (public/non-secret)
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_scopes: List[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    has_oidc_client_secret: bool = False

    # SAML config (public/non-secret)
    saml_entity_id: Optional[str] = None
    saml_sso_url: Optional[str] = None
    saml_metadata_url: Optional[str] = None
    has_saml_x509_cert: bool = False

    last_test_status: Optional[str] = None
    last_test_error: Optional[str] = None
    last_tested_at: Optional[str] = None


class TenantSSOSettingsUpdateRequest(BaseModel):
    """Full tenant SSO config update (single-provider MVP)."""

    is_enabled: bool = False
    login_mode: SSOLoginMode = SSOLoginMode.PASSWORD_ONLY
    provider_type: Optional[SSOProviderType] = None
    protocol: Optional[SSOProtocol] = None
    provider_display_name: Optional[str] = Field(None, max_length=255)

    domain_allowlist: List[str] = Field(default_factory=list)
    domain_verification_required: bool = True

    jit_provisioning_enabled: bool = False
    jit_default_role: str = Field(default="viewer", min_length=1, max_length=100)

    # OIDC
    oidc_issuer_url: Optional[str] = Field(None, max_length=512)
    oidc_client_id: Optional[str] = Field(None, max_length=512)
    oidc_client_secret: Optional[str] = Field(None, max_length=4096)
    oidc_scopes: List[str] = Field(default_factory=lambda: ["openid", "profile", "email"])

    # SAML
    saml_entity_id: Optional[str] = Field(None, max_length=1024)
    saml_sso_url: Optional[str] = Field(None, max_length=1024)
    saml_metadata_url: Optional[str] = Field(None, max_length=1024)
    saml_x509_cert: Optional[str] = None

    @field_validator("domain_allowlist")
    @classmethod
    def normalize_domains(cls, v: List[str]) -> List[str]:
        normalized = []
        for domain in v or []:
            d = (domain or "").strip().lower()
            if d:
                normalized.append(d)
        # Preserve order while removing duplicates
        deduped = list(dict.fromkeys(normalized))
        return deduped

    @field_validator("oidc_scopes")
    @classmethod
    def normalize_scopes(cls, v: List[str]) -> List[str]:
        scopes = []
        for scope in v or []:
            s = (scope or "").strip()
            if s:
                scopes.append(s)
        return scopes or ["openid", "profile", "email"]

    @field_validator("oidc_issuer_url", "saml_sso_url", "saml_metadata_url")
    @classmethod
    def validate_https_urls(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip()
        if value and not value.startswith("https://"):
            raise ValueError("URL must start with https://")
        return value or None

    @model_validator(mode="after")
    def validate_protocol_specific_config(self):
        sso_mode = self.login_mode != SSOLoginMode.PASSWORD_ONLY
        if self.is_enabled or sso_mode:
            if self.provider_type is None or self.protocol is None:
                raise ValueError("provider_type and protocol are required when SSO is enabled")

        if self.login_mode == SSOLoginMode.SSO_ENFORCED and not self.domain_allowlist:
            raise ValueError("domain_allowlist is required when login_mode is sso_enforced")

        if self.protocol == SSOProtocol.OIDC and (self.is_enabled or sso_mode):
            if not self.oidc_issuer_url:
                raise ValueError("oidc_issuer_url is required for OIDC configuration")
            if not self.oidc_client_id:
                raise ValueError("oidc_client_id is required for OIDC configuration")

        if self.protocol == SSOProtocol.SAML and (self.is_enabled or sso_mode):
            if not self.saml_entity_id:
                raise ValueError("saml_entity_id is required for SAML configuration")
            if not self.saml_sso_url:
                raise ValueError("saml_sso_url is required for SAML configuration")
            if not self.saml_metadata_url and not self.saml_x509_cert:
                raise ValueError("Either saml_metadata_url or saml_x509_cert is required for SAML configuration")

        return self


class TenantSSOProviderResponse(BaseModel):
    """Tenant SSO provider response (secrets are not returned)."""

    id: int
    customer_id: str
    provider_type: SSOProviderType
    protocol: SSOProtocol
    display_name: Optional[str] = None
    is_enabled: bool = False

    jit_provisioning_enabled: bool = False
    jit_default_role: str = "viewer"

    # OIDC config (public/non-secret)
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_scopes: List[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    has_oidc_client_secret: bool = False

    # SAML config (public/non-secret)
    saml_entity_id: Optional[str] = None
    saml_sso_url: Optional[str] = None
    saml_metadata_url: Optional[str] = None
    has_saml_x509_cert: bool = False

    last_test_status: Optional[str] = None
    last_test_error: Optional[str] = None
    last_tested_at: Optional[str] = None


class TenantSSOProviderUpsertRequest(BaseModel):
    """Create/update request for a tenant SSO provider."""

    provider_type: SSOProviderType
    protocol: SSOProtocol
    display_name: Optional[str] = Field(None, max_length=255)
    is_enabled: bool = False

    jit_provisioning_enabled: bool = False
    jit_default_role: str = Field(default="viewer", min_length=1, max_length=100)

    # OIDC
    oidc_issuer_url: Optional[str] = Field(None, max_length=512)
    oidc_client_id: Optional[str] = Field(None, max_length=512)
    oidc_client_secret: Optional[str] = Field(None, max_length=4096)
    oidc_scopes: List[str] = Field(default_factory=lambda: ["openid", "profile", "email"])

    # SAML
    saml_entity_id: Optional[str] = Field(None, max_length=1024)
    saml_sso_url: Optional[str] = Field(None, max_length=1024)
    saml_metadata_url: Optional[str] = Field(None, max_length=1024)
    saml_x509_cert: Optional[str] = None

    @field_validator("oidc_scopes")
    @classmethod
    def normalize_scopes_for_provider(cls, v: List[str]) -> List[str]:
        scopes = []
        for scope in v or []:
            s = (scope or "").strip()
            if s:
                scopes.append(s)
        return scopes or ["openid", "profile", "email"]

    @field_validator("oidc_issuer_url", "saml_sso_url", "saml_metadata_url")
    @classmethod
    def validate_provider_https_urls(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        value = v.strip()
        if value and not value.startswith("https://"):
            raise ValueError("URL must start with https://")
        return value or None

    @model_validator(mode="after")
    def validate_provider_protocol_specific_config(self):
        if self.protocol == SSOProtocol.OIDC:
            if not self.oidc_issuer_url:
                raise ValueError("oidc_issuer_url is required for OIDC configuration")
            if not self.oidc_client_id:
                raise ValueError("oidc_client_id is required for OIDC configuration")

        if self.protocol == SSOProtocol.SAML:
            if not self.saml_entity_id:
                raise ValueError("saml_entity_id is required for SAML configuration")
            if not self.saml_sso_url:
                raise ValueError("saml_sso_url is required for SAML configuration")
            if not self.saml_metadata_url and not self.saml_x509_cert:
                raise ValueError(
                    "Either saml_metadata_url or saml_x509_cert is required for SAML configuration"
                )

        return self


class TenantSSODomainResponse(BaseModel):
    """Tenant domain response with verification metadata."""

    id: int
    customer_id: str
    domain: str
    verification_token: str
    status: SSODomainStatus
    verified_at: Optional[str] = None
    last_checked_at: Optional[str] = None
    last_check_error: Optional[str] = None


class TenantSSODomainCreateRequest(BaseModel):
    """Create request for a tenant SSO domain."""

    domain: str = Field(..., min_length=1, max_length=255)

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        domain = (value or "").strip().lower()
        if not domain:
            raise ValueError("domain is required")
        if "://" in domain:
            raise ValueError("domain must not include protocol")
        if "/" in domain:
            raise ValueError("domain must not include path segments")
        return domain


class TenantSSOPolicyResponse(BaseModel):
    """Tenant login policy (separate from provider configuration)."""

    login_mode: SSOLoginMode
    domain_verification_required: bool = True


class TenantSSOPolicyUpdateRequest(BaseModel):
    """Update tenant login policy only."""

    login_mode: SSOLoginMode = SSOLoginMode.PASSWORD_ONLY
    domain_verification_required: bool = True


class PlatformSSOPolicyResponse(BaseModel):
    """Platform-level SSO governance policy."""

    global_sso_enabled: bool
    allowed_provider_types: List[SSOProviderType]
    allow_tenant_enforced_mode: bool
    require_domain_verification_for_enforced_mode: bool

    break_glass_enabled: bool
    break_glass_allowed_user_emails: List[str]

    jit_provisioning_default: bool
    default_password_policy_profile: str


class PlatformSSOPolicyUpdateRequest(BaseModel):
    """Partial update for platform-level SSO governance policy."""

    global_sso_enabled: Optional[bool] = None
    allowed_provider_types: Optional[List[SSOProviderType]] = None
    allow_tenant_enforced_mode: Optional[bool] = None
    require_domain_verification_for_enforced_mode: Optional[bool] = None

    break_glass_enabled: Optional[bool] = None
    break_glass_allowed_user_emails: Optional[List[str]] = None

    jit_provisioning_default: Optional[bool] = None
    default_password_policy_profile: Optional[str] = Field(None, min_length=1, max_length=100)

    @field_validator("break_glass_allowed_user_emails")
    @classmethod
    def normalize_emails(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        normalized = []
        for email in v:
            value = (email or "").strip().lower()
            if value:
                normalized.append(value)
        return list(dict.fromkeys(normalized))
