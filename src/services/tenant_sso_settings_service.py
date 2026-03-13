"""
Tenant and platform SSO settings services.

Phase 1 scope:
- Persist tenant-scoped SSO configuration
- Persist platform-scoped SSO governance policy
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
import httpx
from sqlalchemy.orm import Session

from src.api.schemas.sso_settings import (
    DEFAULT_ALLOWED_PROVIDER_TYPES,
    PlatformSSOPolicyResponse,
    PlatformSSOPolicyUpdateRequest,
    SSOLoginMode,
    SSOProviderType,
    TenantSSOSettingsResponse,
    TenantSSOSettingsUpdateRequest,
)
from src.models.system_settings import SettingType
from src.models.tenant_sso import TenantSSOConfig
from src.services.settings_service import SettingsService
from src.utils.encryption import EncryptionError, encrypt_value


class TenantSSOSettingsService:
    """Service for tenant-scoped SSO configuration CRUD."""

    OIDC_CLIENT_SECRET_ENCRYPTED = "oidc_client_secret_encrypted"
    SAML_X509_CERT_ENCRYPTED = "saml_x509_cert_encrypted"

    def __init__(self, db: Session):
        self.db = db

    def _get_config(self, customer_id: str) -> TenantSSOConfig | None:
        return (
            self.db.query(TenantSSOConfig)
            .filter(TenantSSOConfig.customer_id == customer_id)
            .first()
        )

    def get_settings(self, customer_id: str) -> TenantSSOSettingsResponse:
        """Get tenant SSO settings, returning defaults when unset."""
        config = self._get_config(customer_id)
        if not config:
            return TenantSSOSettingsResponse(
                is_enabled=False,
                login_mode=SSOLoginMode.PASSWORD_ONLY,
                domain_allowlist=[],
                domain_verification_required=True,
                jit_provisioning_enabled=False,
                jit_default_role="viewer",
                oidc_scopes=["openid", "profile", "email"],
            )

        config_data: Dict[str, Any] = config.config_data or {}
        secret_data: Dict[str, Any] = config.secret_data_encrypted or {}

        return TenantSSOSettingsResponse(
            is_enabled=config.is_enabled,
            login_mode=config.login_mode,
            provider_type=config.provider_type,
            protocol=config.protocol,
            provider_display_name=config.provider_display_name,
            domain_allowlist=config.domain_allowlist or [],
            domain_verification_required=config.domain_verification_required,
            jit_provisioning_enabled=config.jit_provisioning_enabled,
            jit_default_role=config.jit_default_role,
            oidc_issuer_url=config_data.get("oidc_issuer_url"),
            oidc_client_id=config_data.get("oidc_client_id"),
            oidc_scopes=config_data.get("oidc_scopes") or ["openid", "profile", "email"],
            has_oidc_client_secret=bool(secret_data.get(self.OIDC_CLIENT_SECRET_ENCRYPTED)),
            saml_entity_id=config_data.get("saml_entity_id"),
            saml_sso_url=config_data.get("saml_sso_url"),
            saml_metadata_url=config_data.get("saml_metadata_url"),
            has_saml_x509_cert=bool(secret_data.get(self.SAML_X509_CERT_ENCRYPTED)),
            last_test_status=config.last_test_status,
            last_test_error=config.last_test_error,
            last_tested_at=config.last_tested_at.isoformat() if config.last_tested_at else None,
        )

    def update_settings(
        self,
        customer_id: str,
        request: TenantSSOSettingsUpdateRequest,
        updated_by_user_id: int | None,
    ) -> TenantSSOSettingsResponse:
        """Create or update tenant SSO settings."""
        config = self._get_config(customer_id)
        if not config:
            config = TenantSSOConfig(customer_id=customer_id)
            self.db.add(config)

        config_data: Dict[str, Any] = {
            "oidc_issuer_url": request.oidc_issuer_url,
            "oidc_client_id": request.oidc_client_id,
            "oidc_scopes": request.oidc_scopes,
            "saml_entity_id": request.saml_entity_id,
            "saml_sso_url": request.saml_sso_url,
            "saml_metadata_url": request.saml_metadata_url,
        }

        existing_secret_data = dict(config.secret_data_encrypted or {})
        secret_data_encrypted = dict(existing_secret_data)

        if request.oidc_client_secret:
            try:
                secret_data_encrypted[self.OIDC_CLIENT_SECRET_ENCRYPTED] = encrypt_value(
                    request.oidc_client_secret
                )
            except EncryptionError as exc:
                raise ValueError(f"Failed to encrypt OIDC client secret: {exc}") from exc

        if request.saml_x509_cert:
            try:
                secret_data_encrypted[self.SAML_X509_CERT_ENCRYPTED] = encrypt_value(
                    request.saml_x509_cert
                )
            except EncryptionError as exc:
                raise ValueError(f"Failed to encrypt SAML certificate: {exc}") from exc

        config.is_enabled = request.is_enabled
        config.login_mode = request.login_mode.value
        config.provider_type = request.provider_type.value if request.provider_type else None
        config.protocol = request.protocol.value if request.protocol else None
        config.provider_display_name = request.provider_display_name

        config.domain_allowlist = request.domain_allowlist
        config.domain_verification_required = request.domain_verification_required
        config.jit_provisioning_enabled = request.jit_provisioning_enabled
        config.jit_default_role = request.jit_default_role
        config.config_data = config_data
        config.secret_data_encrypted = secret_data_encrypted
        config.updated_by_user_id = updated_by_user_id

        # Config changed, test status should be refreshed by explicit test flow later.
        config.last_test_status = None
        config.last_test_error = None
        config.last_tested_at = None

        self.db.commit()
        self.db.refresh(config)
        return self.get_settings(customer_id)

    def test_settings(self, customer_id: str) -> TenantSSOSettingsResponse:
        """
        Test current tenant SSO configuration.

        Updates last_test_* fields and returns the latest settings snapshot.
        """
        config = self._get_config(customer_id)
        if not config:
            raise ValueError("No SSO configuration found for this tenant")

        config_data: Dict[str, Any] = config.config_data or {}
        try:
            if not config.is_enabled:
                raise ValueError("SSO is disabled for this tenant")
            if not config.protocol:
                raise ValueError("SSO protocol is not configured")

            if config.protocol == "oidc":
                issuer_url = str(config_data.get("oidc_issuer_url") or "").strip()
                if not issuer_url:
                    raise ValueError("OIDC issuer URL is missing")
                discovery_url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"
                response = httpx.get(discovery_url, timeout=12.0)
                response.raise_for_status()
                metadata = response.json()
                if not metadata.get("authorization_endpoint"):
                    raise ValueError("OIDC metadata missing authorization_endpoint")
                if not metadata.get("token_endpoint"):
                    raise ValueError("OIDC metadata missing token_endpoint")

            elif config.protocol == "saml":
                sso_url = str(config_data.get("saml_sso_url") or "").strip()
                metadata_url = str(config_data.get("saml_metadata_url") or "").strip()
                if not sso_url:
                    raise ValueError("SAML SSO URL is missing")
                if metadata_url:
                    response = httpx.get(metadata_url, timeout=12.0)
                    response.raise_for_status()
            else:
                raise ValueError("Unsupported SSO protocol")

            config.last_test_status = "success"
            config.last_test_error = None
        except Exception as exc:
            config.last_test_status = "failed"
            config.last_test_error = str(exc)

        config.last_tested_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(config)
        return self.get_settings(customer_id)


class PlatformSSOPolicyService:
    """Service for platform-wide SSO governance policy."""

    KEY_GLOBAL_SSO_ENABLED = "sso.global_enabled"
    KEY_ALLOWED_PROVIDER_TYPES = "sso.allowed_provider_types"
    KEY_ALLOW_TENANT_ENFORCED_MODE = "sso.allow_tenant_enforced_mode"
    KEY_REQUIRE_DOMAIN_VERIFICATION = "sso.require_domain_verification_for_enforced_mode"
    KEY_BREAK_GLASS_ENABLED = "sso.break_glass_enabled"
    KEY_BREAK_GLASS_ALLOWED_USER_EMAILS = "sso.break_glass_allowed_user_emails"
    KEY_JIT_PROVISIONING_DEFAULT = "sso.jit_provisioning_default"
    KEY_DEFAULT_PASSWORD_POLICY_PROFILE = "sso.default_password_policy_profile"

    def __init__(self, db: Session):
        self.db = db
        self.settings = SettingsService(db)

    def get_policy(self) -> PlatformSSOPolicyResponse:
        """Return current platform SSO policy with defaults."""
        default_provider_values = [provider.value for provider in DEFAULT_ALLOWED_PROVIDER_TYPES]
        raw_allowed = self.settings.get_setting_value(
            self.KEY_ALLOWED_PROVIDER_TYPES, default_provider_values
        ) or default_provider_values
        allowed_provider_types: List[SSOProviderType] = []
        for provider in raw_allowed:
            try:
                allowed_provider_types.append(SSOProviderType(provider))
            except ValueError:
                continue
        if not allowed_provider_types:
            allowed_provider_types = DEFAULT_ALLOWED_PROVIDER_TYPES

        raw_break_glass_emails = self.settings.get_setting_value(
            self.KEY_BREAK_GLASS_ALLOWED_USER_EMAILS, []
        ) or []
        break_glass_emails = [str(email).strip().lower() for email in raw_break_glass_emails if str(email).strip()]

        return PlatformSSOPolicyResponse(
            global_sso_enabled=bool(
                self.settings.get_setting_value(self.KEY_GLOBAL_SSO_ENABLED, True)
            ),
            allowed_provider_types=allowed_provider_types,
            allow_tenant_enforced_mode=bool(
                self.settings.get_setting_value(self.KEY_ALLOW_TENANT_ENFORCED_MODE, True)
            ),
            require_domain_verification_for_enforced_mode=bool(
                self.settings.get_setting_value(self.KEY_REQUIRE_DOMAIN_VERIFICATION, True)
            ),
            break_glass_enabled=bool(
                self.settings.get_setting_value(self.KEY_BREAK_GLASS_ENABLED, True)
            ),
            break_glass_allowed_user_emails=break_glass_emails,
            jit_provisioning_default=bool(
                self.settings.get_setting_value(self.KEY_JIT_PROVISIONING_DEFAULT, False)
            ),
            default_password_policy_profile=str(
                self.settings.get_setting_value(
                    self.KEY_DEFAULT_PASSWORD_POLICY_PROFILE, "strong_8_char"
                )
            ),
        )

    def update_policy(self, request: PlatformSSOPolicyUpdateRequest) -> PlatformSSOPolicyResponse:
        """Apply partial updates and return resulting policy."""
        if request.global_sso_enabled is not None:
            self.settings.set_setting(
                key=self.KEY_GLOBAL_SSO_ENABLED,
                value=request.global_sso_enabled,
                setting_type=SettingType.BOOLEAN.value,
                description="Global kill switch for tenant SSO features",
                is_public=False,
            )

        if request.allowed_provider_types is not None:
            self.settings.set_setting(
                key=self.KEY_ALLOWED_PROVIDER_TYPES,
                value=[provider.value for provider in request.allowed_provider_types],
                setting_type=SettingType.JSON.value,
                description="Allowed SSO provider families for tenant configuration",
                is_public=False,
            )

        if request.allow_tenant_enforced_mode is not None:
            self.settings.set_setting(
                key=self.KEY_ALLOW_TENANT_ENFORCED_MODE,
                value=request.allow_tenant_enforced_mode,
                setting_type=SettingType.BOOLEAN.value,
                description="Whether tenants can set SSO_ENFORCED login mode",
                is_public=False,
            )

        if request.require_domain_verification_for_enforced_mode is not None:
            self.settings.set_setting(
                key=self.KEY_REQUIRE_DOMAIN_VERIFICATION,
                value=request.require_domain_verification_for_enforced_mode,
                setting_type=SettingType.BOOLEAN.value,
                description="Require domain allowlist/verification for SSO_ENFORCED mode",
                is_public=False,
            )

        if request.break_glass_enabled is not None:
            self.settings.set_setting(
                key=self.KEY_BREAK_GLASS_ENABLED,
                value=request.break_glass_enabled,
                setting_type=SettingType.BOOLEAN.value,
                description="Enable break-glass local login behavior for enforced SSO tenants",
                is_public=False,
            )

        if request.break_glass_allowed_user_emails is not None:
            self.settings.set_setting(
                key=self.KEY_BREAK_GLASS_ALLOWED_USER_EMAILS,
                value=request.break_glass_allowed_user_emails,
                setting_type=SettingType.JSON.value,
                description="Allowed break-glass account emails for local login in enforced mode",
                is_public=False,
            )

        if request.jit_provisioning_default is not None:
            self.settings.set_setting(
                key=self.KEY_JIT_PROVISIONING_DEFAULT,
                value=request.jit_provisioning_default,
                setting_type=SettingType.BOOLEAN.value,
                description="Default tenant setting for JIT user provisioning",
                is_public=False,
            )

        if request.default_password_policy_profile is not None:
            self.settings.set_setting(
                key=self.KEY_DEFAULT_PASSWORD_POLICY_PROFILE,
                value=request.default_password_policy_profile,
                setting_type=SettingType.STRING.value,
                description="Default password policy profile for local credentials",
                is_public=False,
            )

        return self.get_policy()
