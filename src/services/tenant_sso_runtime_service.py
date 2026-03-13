"""
Runtime SSO services for login policy resolution and SSO authentication flows.

This module handles:
- tenant/policy lookup from login email
- password-vs-SSO policy enforcement
- OIDC authorize/callback processing
- SAML start/ACS processing
- user linking and JIT provisioning
"""

from __future__ import annotations

import base64
import logging
import re
import secrets
import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from xml.sax.saxutils import escape as xml_escape, quoteattr as xml_quoteattr

import httpx
import jwt
from lxml import etree
from signxml import InvalidSignature, XMLVerifier
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.api.schemas.sso_settings import SSOLoginMode
from src.core.config import get_settings
from src.models.auth import Role, User, UserTenantMembership
from src.models.customer import Customer
from src.models.tenant_admin import PlatformFeature, TenantFeatureAllocation
from src.models.tenant_sso import TenantSSOConfig, TenantSSODomain, TenantSSOProvider
from src.models.user_sso_identity import UserSSOIdentity
from src.services.tenant_sso_provider_service import TenantSSOProviderService
from src.services.tenant_sso_settings_service import PlatformSSOPolicyService
from src.utils.encryption import EncryptionError, decrypt_value

logger = logging.getLogger(__name__)


class SSOResolutionError(ValueError):
    """Raised when tenant/policy cannot be deterministically resolved."""


class SSOConfigurationError(ValueError):
    """Raised when SSO configuration is missing or invalid."""


class SSOAuthenticationError(ValueError):
    """Raised when SSO auth handshake fails."""


class SSOProvisioningError(ValueError):
    """Raised when user linking/JIT provisioning fails."""


@dataclass
class LoginResolution:
    """Resolved login policy context for a given email (+ optional tenant hint)."""

    email: str
    customer_id: Optional[str]
    customer_name: Optional[str]
    login_mode: str
    sso_login_available: bool
    password_login_allowed: bool
    requires_sso: bool
    break_glass_allowed: bool
    provider_type: Optional[str]
    protocol: Optional[str]
    provider_display_name: Optional[str]
    jit_provisioning_enabled: bool
    jit_default_role: str
    provider_id: Optional[int] = None
    providers: list[dict[str, Any]] | None = None
    config: Optional[TenantSSOProvider] = None
    user: Optional[User] = None


class TenantSSORuntimeService:
    """Runtime helpers for tenant-scoped SSO authentication."""

    OIDC_STATE_PURPOSE = "oidc_login"
    SAML_STATE_PURPOSE = "saml_login"
    STATE_TOKEN_TTL_MINUTES = 10

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.policy_service = PlatformSSOPolicyService(db)

    @staticmethod
    def _normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    @staticmethod
    def _email_domain(email: str) -> Optional[str]:
        normalized = TenantSSORuntimeService._normalize_email(email)
        if "@" not in normalized:
            return None
        return normalized.split("@", 1)[1]

    @staticmethod
    def _username_from_email(email: str) -> str:
        if "@" not in email:
            return "user"
        return email.split("@", 1)[0]

    def _is_sso_feature_allocated(self, customer_id: str) -> bool:
        allocation = (
            self.db.query(TenantFeatureAllocation)
            .join(PlatformFeature, PlatformFeature.id == TenantFeatureAllocation.feature_id)
            .filter(
                TenantFeatureAllocation.customer_id == customer_id,
                TenantFeatureAllocation.is_enabled == True,  # noqa: E712
                PlatformFeature.feature_key == "sso_authentication",
                PlatformFeature.is_active == True,  # noqa: E712
            )
            .first()
        )
        return allocation is not None

    def _get_customer_name(self, customer_id: str) -> Optional[str]:
        customer = (
            self.db.query(Customer)
            .filter(Customer.customer_id == customer_id)
            .first()
        )
        if not customer:
            return None
        return customer.display_name or customer.name

    def _get_user_by_email(self, email: str, with_roles: bool = False) -> Optional[User]:
        query = self.db.query(User).filter(func.lower(User.email) == email)
        if with_roles:
            query = query.options(
                joinedload(User.roles).joinedload(Role.permissions),
                joinedload(User.tenant_memberships),
            )
        return query.first()

    def _select_customer_for_user(
        self,
        user: User,
        requested_customer_id: Optional[str],
    ) -> str:
        memberships = (
            self.db.query(UserTenantMembership)
            .filter(UserTenantMembership.user_id == user.id)
            .all()
        )
        membership_customer_ids = {m.customer_id for m in memberships}

        if requested_customer_id:
            if requested_customer_id in membership_customer_ids:
                return requested_customer_id
            raise SSOResolutionError(
                "Requested tenant context is not accessible for this account."
            )

        default_membership = next((m for m in memberships if m.is_default), None)
        if default_membership:
            return default_membership.customer_id

        if user.customer_id:
            return user.customer_id

        if memberships:
            return memberships[0].customer_id

        raise SSOResolutionError("No tenant memberships found for this user.")

    def _match_tenant_by_email_domain(self, email: str) -> Optional[str]:
        domain = self._email_domain(email)
        if not domain:
            return None

        domain_rows = (
            self.db.query(TenantSSODomain)
            .filter(
                TenantSSODomain.status == "verified",
                TenantSSODomain.domain == domain,
            )
            .all()
        )

        matched_customer_ids = list(dict.fromkeys([row.customer_id for row in domain_rows]))
        if len(matched_customer_ids) > 1:
            raise SSOResolutionError(
                "Multiple organizations match this email domain. Specify tenant context."
            )
        if not matched_customer_ids:
            return None
        return matched_customer_ids[0]

    def _get_enabled_providers(
        self,
        customer_id: str,
        expected_protocol: Optional[str] = None,
    ) -> list[TenantSSOProvider]:
        query = self.db.query(TenantSSOProvider).filter(
            TenantSSOProvider.customer_id == customer_id,
            TenantSSOProvider.is_enabled == True,  # noqa: E712
        )
        if expected_protocol:
            query = query.filter(TenantSSOProvider.protocol == expected_protocol)
        providers = query.order_by(TenantSSOProvider.id.asc()).all()
        if not providers:
            return []

        policy = self.policy_service.get_policy()
        allowed_types = {provider.value for provider in policy.allowed_provider_types}
        return [p for p in providers if (p.provider_type or "") in allowed_types]

    def _is_break_glass_allowed(self, email: str, user: Optional[User] = None) -> bool:
        policy = self.policy_service.get_policy()
        if not policy.break_glass_enabled:
            return False

        if email in policy.break_glass_allowed_user_emails:
            return True

        if user is None:
            user = self._get_user_by_email(email, with_roles=True)

        if user:
            try:
                if "platform:admin" in user.get_permissions():
                    return True
            except Exception:
                logger.exception("Failed to evaluate platform admin break-glass permissions")

        return False

    def _effective_sso_runtime_enabled(
        self,
        customer_id: str,
        providers: list[TenantSSOProvider],
    ) -> bool:
        policy = self.policy_service.get_policy()
        if not policy.global_sso_enabled:
            return False
        if not self._is_sso_feature_allocated(customer_id):
            return False
        if not providers:
            return False
        allowed_provider_types = {
            provider_type.value for provider_type in policy.allowed_provider_types
        }
        if not any((provider.provider_type or "") in allowed_provider_types for provider in providers):
            return False
        return True

    def discover_providers(self) -> list[dict[str, Any]]:
        """Return all runtime-enabled SSO providers across the deployment.

        Used by the unauthenticated login page to render branded SSO buttons
        before the user has entered an email address.  Only minimal, non-secret
        fields are returned.
        """
        policy = self.policy_service.get_policy()
        if not policy.global_sso_enabled:
            return []

        allowed_types = {pt.value for pt in policy.allowed_provider_types}

        all_enabled = (
            self.db.query(TenantSSOProvider)
            .filter(TenantSSOProvider.is_enabled == True)  # noqa: E712
            .order_by(TenantSSOProvider.id.asc())
            .all()
        )

        tenant_configs: dict[str, TenantSSOConfig | None] = {}
        results: list[dict[str, Any]] = []
        checked_customers: dict[str, bool] = {}
        for provider in all_enabled:
            if (provider.provider_type or "") not in allowed_types:
                continue
            cid = provider.customer_id
            if cid not in checked_customers:
                checked_customers[cid] = self._is_sso_feature_allocated(cid)
            if not checked_customers[cid]:
                continue
            if cid not in tenant_configs:
                tenant_configs[cid] = (
                    self.db.query(TenantSSOConfig)
                    .filter(TenantSSOConfig.customer_id == cid)
                    .first()
                )
            cfg = tenant_configs[cid]
            login_mode = cfg.login_mode if cfg else SSOLoginMode.PASSWORD_ONLY.value
            if login_mode == SSOLoginMode.PASSWORD_ONLY.value:
                continue
            results.append(
                {
                    "id": provider.id,
                    "provider_type": provider.provider_type,
                    "protocol": provider.protocol,
                    "display_name": provider.display_name,
                }
            )
        return results

    def resolve_login(
        self,
        email: str,
        customer_id: Optional[str] = None,
    ) -> LoginResolution:
        """Resolve tenant login policy from email and optional tenant hint."""
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            raise SSOResolutionError("Email is required.")

        user = self._get_user_by_email(normalized_email, with_roles=True)
        selected_customer_id: Optional[str] = None

        if user:
            selected_customer_id = self._select_customer_for_user(user, customer_id)
        elif customer_id:
            selected_customer_id = customer_id
        else:
            selected_customer_id = self._match_tenant_by_email_domain(normalized_email)

        if not selected_customer_id:
            return LoginResolution(
                email=normalized_email,
                customer_id=None,
                customer_name=None,
                login_mode=SSOLoginMode.PASSWORD_ONLY.value,
                sso_login_available=False,
                password_login_allowed=True,
                requires_sso=False,
                break_glass_allowed=False,
                provider_type=None,
                protocol=None,
                provider_display_name=None,
                jit_provisioning_enabled=False,
                jit_default_role="viewer",
                provider_id=None,
                providers=[],
                config=None,
                user=user,
            )

        tenant_config = (
            self.db.query(TenantSSOConfig)
            .filter(TenantSSOConfig.customer_id == selected_customer_id)
            .first()
        )
        providers = self._get_enabled_providers(selected_customer_id)
        customer_name = self._get_customer_name(selected_customer_id)
        runtime_enabled = self._effective_sso_runtime_enabled(selected_customer_id, providers)
        break_glass_allowed = self._is_break_glass_allowed(normalized_email, user)
        primary_provider = providers[0] if providers else None
        provider_options = [
            {
                "id": provider.id,
                "provider_type": provider.provider_type,
                "protocol": provider.protocol,
                "provider_display_name": provider.display_name,
                "is_enabled": provider.is_enabled,
            }
            for provider in providers
        ]
        login_mode_value = (
            tenant_config.login_mode if tenant_config else SSOLoginMode.PASSWORD_ONLY.value
        )

        sso_available = runtime_enabled and login_mode_value != SSOLoginMode.PASSWORD_ONLY.value

        if sso_available and login_mode_value == SSOLoginMode.SSO_ENFORCED.value:
            password_login_allowed = break_glass_allowed
            requires_sso = not break_glass_allowed
            login_mode = SSOLoginMode.SSO_ENFORCED.value
        elif sso_available:
            password_login_allowed = True
            requires_sso = False
            login_mode = login_mode_value
        else:
            password_login_allowed = True
            requires_sso = False
            login_mode = SSOLoginMode.PASSWORD_ONLY.value

        return LoginResolution(
            email=normalized_email,
            customer_id=selected_customer_id,
            customer_name=customer_name,
            login_mode=login_mode,
            sso_login_available=sso_available,
            password_login_allowed=password_login_allowed,
            requires_sso=requires_sso,
            break_glass_allowed=break_glass_allowed,
            provider_type=primary_provider.provider_type if primary_provider else None,
            protocol=primary_provider.protocol if primary_provider else None,
            provider_display_name=(primary_provider.display_name if primary_provider else None),
            jit_provisioning_enabled=(
                bool(primary_provider.jit_provisioning_enabled)
                if primary_provider
                else False
            ),
            jit_default_role=(primary_provider.jit_default_role if primary_provider else "viewer"),
            provider_id=(primary_provider.id if primary_provider else None),
            providers=provider_options,
            config=primary_provider,
            user=user,
        )

    def assert_password_login_allowed(
        self,
        email: str,
        customer_id: Optional[str] = None,
    ) -> LoginResolution:
        """Raise if password login is disallowed by tenant policy."""
        resolution = self.resolve_login(email=email, customer_id=customer_id)
        if not resolution.password_login_allowed:
            raise SSOAuthenticationError(
                "Password login is disabled for this organization. Use SSO."
            )
        return resolution

    def get_sso_config_for_login(
        self,
        email: str,
        customer_id: Optional[str] = None,
        expected_protocol: Optional[str] = None,
        provider_id: Optional[int] = None,
    ) -> LoginResolution:
        """Resolve and validate an active SSO configuration for login."""
        resolution = self.resolve_login(email=email, customer_id=customer_id)
        if not resolution.customer_id:
            raise SSOResolutionError("Unable to determine organization for this email.")
        if not resolution.sso_login_available:
            raise SSOConfigurationError("SSO is not configured for this organization.")

        providers = self._get_enabled_providers(
            resolution.customer_id,
            expected_protocol=expected_protocol,
        )
        if not providers:
            if expected_protocol:
                raise SSOConfigurationError(
                    f"This organization is not configured for {expected_protocol.upper()} login."
                )
            raise SSOConfigurationError("SSO is not configured for this organization.")

        selected_provider: Optional[TenantSSOProvider] = None
        if provider_id is not None:
            selected_provider = next((p for p in providers if p.id == provider_id), None)
            if not selected_provider:
                raise SSOConfigurationError("Selected SSO provider is not available.")
        elif len(providers) == 1:
            selected_provider = providers[0]
        else:
            raise SSOResolutionError(
                "Multiple SSO providers are available. Select a provider to continue."
            )

        resolution.provider_id = selected_provider.id
        resolution.provider_type = selected_provider.provider_type
        resolution.protocol = selected_provider.protocol
        resolution.provider_display_name = selected_provider.display_name
        resolution.jit_provisioning_enabled = bool(selected_provider.jit_provisioning_enabled)
        resolution.jit_default_role = selected_provider.jit_default_role
        resolution.config = selected_provider
        return resolution

    def get_sso_config_for_customer(
        self,
        customer_id: str,
        expected_protocol: Optional[str] = None,
        login_email: Optional[str] = None,
        provider_id: Optional[int] = None,
    ) -> LoginResolution:
        """Resolve and validate SSO configuration directly from tenant context."""
        if not customer_id:
            raise SSOResolutionError("Organization context is required.")

        tenant_config = (
            self.db.query(TenantSSOConfig)
            .filter(TenantSSOConfig.customer_id == customer_id)
            .first()
        )
        login_mode = tenant_config.login_mode if tenant_config else SSOLoginMode.PASSWORD_ONLY.value
        if login_mode == SSOLoginMode.PASSWORD_ONLY.value:
            raise SSOConfigurationError("SSO login is disabled for this organization.")

        providers = self._get_enabled_providers(
            customer_id,
            expected_protocol=expected_protocol,
        )
        if not self._effective_sso_runtime_enabled(customer_id, providers):
            raise SSOConfigurationError("SSO is not configured for this organization.")

        selected_provider: Optional[TenantSSOProvider] = None
        if provider_id is not None:
            selected_provider = next((p for p in providers if p.id == provider_id), None)
            if not selected_provider:
                raise SSOConfigurationError("Selected SSO provider is not available.")
        elif len(providers) == 1:
            selected_provider = providers[0]
        else:
            raise SSOResolutionError(
                "Multiple SSO providers are available. Select a provider to continue."
            )

        normalized_email = self._normalize_email(login_email or "")
        customer_name = self._get_customer_name(customer_id)
        provider_options = [
            {
                "id": provider.id,
                "provider_type": provider.provider_type,
                "protocol": provider.protocol,
                "provider_display_name": provider.display_name,
                "is_enabled": provider.is_enabled,
            }
            for provider in providers
        ]

        return LoginResolution(
            email=normalized_email,
            customer_id=customer_id,
            customer_name=customer_name,
            login_mode=(
                tenant_config.login_mode
                if tenant_config
                else SSOLoginMode.PASSWORD_ONLY.value
            ),
            sso_login_available=True,
            password_login_allowed=True,
            requires_sso=False,
            break_glass_allowed=False,
            provider_type=selected_provider.provider_type,
            protocol=selected_provider.protocol,
            provider_display_name=selected_provider.display_name,
            jit_provisioning_enabled=bool(selected_provider.jit_provisioning_enabled),
            jit_default_role=selected_provider.jit_default_role,
            provider_id=selected_provider.id,
            providers=provider_options,
            config=selected_provider,
            user=None,
        )

    def get_sso_config_for_start(
        self,
        expected_protocol: Optional[str] = None,
        customer_id: Optional[str] = None,
        login_email: Optional[str] = None,
        provider_id: Optional[int] = None,
    ) -> LoginResolution:
        """
        Resolve SSO configuration for an IdP-start flow when login email may be absent.

        Resolution order:
        1. provided customer_id
        2. single runtime-enabled SSO tenant in this deployment
        """
        if customer_id:
            return self.get_sso_config_for_customer(
                customer_id=customer_id,
                expected_protocol=expected_protocol,
                login_email=login_email,
                provider_id=provider_id,
            )

        providers = (
            self.db.query(TenantSSOProvider)
            .filter(TenantSSOProvider.is_enabled == True)  # noqa: E712
            .all()
        )

        runtime_enabled_customer_ids = []
        for provider in providers:
            if expected_protocol and provider.protocol != expected_protocol:
                continue
            if self._effective_sso_runtime_enabled(provider.customer_id, [provider]):
                runtime_enabled_customer_ids.append(provider.customer_id)

        runtime_enabled_customer_ids = list(dict.fromkeys(runtime_enabled_customer_ids))

        if not runtime_enabled_customer_ids:
            raise SSOConfigurationError("No SSO configuration is currently available.")
        if len(runtime_enabled_customer_ids) > 1:
            raise SSOResolutionError(
                "Multiple organizations support SSO. Enter your work email first."
            )

        return self.get_sso_config_for_customer(
            customer_id=runtime_enabled_customer_ids[0],
            expected_protocol=expected_protocol,
            login_email=login_email,
            provider_id=provider_id,
        )

    def _encode_state_token(self, payload: Dict[str, Any]) -> str:
        now = datetime.now(timezone.utc)
        state_payload = dict(payload)
        state_payload["iat"] = int(now.timestamp())
        state_payload["exp"] = int(
            (now + timedelta(minutes=self.STATE_TOKEN_TTL_MINUTES)).timestamp()
        )
        state_payload["iss"] = "eliza-sso-runtime"
        return jwt.encode(
            state_payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )

    def decode_state_token(self, state_token: str, expected_purpose: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(
                state_token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
                options={"require": ["exp", "iat", "purpose", "customer_id"]},
            )
        except jwt.PyJWTError as exc:
            raise SSOAuthenticationError("Invalid or expired SSO state token.") from exc

        if payload.get("purpose") != expected_purpose:
            raise SSOAuthenticationError("SSO state token purpose mismatch.")

        return payload

    @staticmethod
    def _config_data(config: TenantSSOProvider) -> Dict[str, Any]:
        return dict(config.config_data or {})

    @staticmethod
    def _secret_data(config: TenantSSOProvider) -> Dict[str, Any]:
        return dict(config.secret_data_encrypted or {})

    def _decrypt_secret(self, config: TenantSSOProvider, key: str) -> Optional[str]:
        encrypted = self._secret_data(config).get(key)
        if not encrypted:
            return None
        try:
            return decrypt_value(encrypted)
        except EncryptionError as exc:
            raise SSOConfigurationError(f"Unable to decrypt required secret '{key}'.") from exc

    async def _fetch_oidc_metadata(self, issuer_url: str) -> Dict[str, Any]:
        issuer = issuer_url.rstrip("/")
        discovery_url = f"{issuer}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(discovery_url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SSOAuthenticationError("Failed to discover OIDC metadata.") from exc
        return response.json()

    async def build_oidc_authorize_url(
        self,
        resolution: LoginResolution,
        callback_url: str,
    ) -> str:
        """Build OIDC authorization redirect URL for a resolved tenant config."""
        if not resolution.config:
            raise SSOConfigurationError("Missing SSO configuration.")

        config_data = self._config_data(resolution.config)
        issuer_url = str(config_data.get("oidc_issuer_url") or "").strip()
        client_id = str(config_data.get("oidc_client_id") or "").strip()
        scopes = config_data.get("oidc_scopes") or ["openid", "profile", "email"]

        if not issuer_url or not client_id:
            raise SSOConfigurationError("OIDC issuer URL and client ID are required.")

        metadata = await self._fetch_oidc_metadata(issuer_url)
        authorization_endpoint = metadata.get("authorization_endpoint")
        if not authorization_endpoint:
            raise SSOConfigurationError("OIDC metadata missing authorization endpoint.")

        nonce = secrets.token_urlsafe(16)
        state_token = self._encode_state_token(
            {
                "purpose": self.OIDC_STATE_PURPOSE,
                "customer_id": resolution.customer_id,
                "email": resolution.email,
                "protocol": "oidc",
                "provider_id": resolution.provider_id,
                "nonce": nonce,
            }
        )

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": callback_url,
            "scope": " ".join(scopes),
            "state": state_token,
            "nonce": nonce,
        }
        if resolution.email:
            params["login_hint"] = resolution.email
        # For Google sign-in, force account chooser when email isn't prefilled.
        if (resolution.provider_type or "").lower() == "google":
            params["prompt"] = "select_account"

        separator = "&" if "?" in authorization_endpoint else "?"
        return f"{authorization_endpoint}{separator}{urlencode(params)}"

    async def exchange_oidc_code(
        self,
        resolution: LoginResolution,
        authorization_code: str,
        callback_url: str,
        state_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Exchange OIDC auth code and validate resulting ID token claims."""
        if not resolution.config:
            raise SSOConfigurationError("Missing OIDC configuration.")

        config = resolution.config
        config_data = self._config_data(config)
        issuer_url = str(config_data.get("oidc_issuer_url") or "").strip()
        client_id = str(config_data.get("oidc_client_id") or "").strip()
        client_secret = self._decrypt_secret(
            config, TenantSSOProviderService.OIDC_CLIENT_SECRET_ENCRYPTED
        )
        if not issuer_url or not client_id:
            raise SSOConfigurationError("OIDC issuer URL and client ID are required.")
        if not client_secret:
            raise SSOConfigurationError("OIDC client secret is required for code exchange.")

        metadata = await self._fetch_oidc_metadata(issuer_url)
        token_endpoint = metadata.get("token_endpoint")
        if not token_endpoint:
            raise SSOConfigurationError("OIDC metadata missing token endpoint.")

        payload = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": callback_url,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(token_endpoint, data=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SSOAuthenticationError("OIDC token exchange failed.") from exc

        token_data = response.json()
        id_token = token_data.get("id_token")
        if not id_token:
            raise SSOAuthenticationError("OIDC provider did not return an ID token.")

        claims = self._validate_oidc_id_token(
            id_token=id_token,
            metadata=metadata,
            expected_client_id=client_id,
            expected_issuer=metadata.get("issuer") or issuer_url,
            expected_nonce=state_payload.get("nonce"),
        )
        return claims

    def _validate_oidc_id_token(
        self,
        id_token: str,
        metadata: Dict[str, Any],
        expected_client_id: str,
        expected_issuer: str,
        expected_nonce: Optional[str],
    ) -> Dict[str, Any]:
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise SSOAuthenticationError("OIDC metadata missing JWKS URI.")

        unverified_header = jwt.get_unverified_header(id_token)
        algorithm = unverified_header.get("alg")
        if not algorithm:
            raise SSOAuthenticationError("OIDC token header missing algorithm.")

        try:
            signing_key = jwt.PyJWKClient(jwks_uri).get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=[algorithm],
                audience=expected_client_id,
                issuer=expected_issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise SSOAuthenticationError("OIDC ID token validation failed.") from exc

        token_nonce = claims.get("nonce")
        if expected_nonce and token_nonce != expected_nonce:
            raise SSOAuthenticationError("OIDC nonce verification failed.")

        return claims

    def build_saml_redirect_url(
        self,
        resolution: LoginResolution,
        acs_url: str,
    ) -> str:
        """Build unsigned SAML AuthnRequest redirect URL."""
        if not resolution.config:
            raise SSOConfigurationError("Missing SAML configuration.")

        config_data = self._config_data(resolution.config)
        sso_url = str(config_data.get("saml_sso_url") or "").strip()
        entity_id = str(config_data.get("saml_entity_id") or "").strip()
        if not sso_url:
            raise SSOConfigurationError("SAML SSO URL is required.")
        if not entity_id:
            raise SSOConfigurationError("SAML entity ID is required.")

        request_id = f"_{uuid.uuid4().hex}"
        issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        authn_request = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<samlp:AuthnRequest '
            'xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
            'xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
            f'ID={xml_quoteattr(request_id)} Version="2.0" IssueInstant={xml_quoteattr(issue_instant)} '
            f'Destination={xml_quoteattr(sso_url)} ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" '
            f'AssertionConsumerServiceURL={xml_quoteattr(acs_url)}>'
            f"<saml:Issuer>{xml_escape(entity_id)}</saml:Issuer>"
            '<samlp:NameIDPolicy AllowCreate="true" '
            'Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"/>'
            "</samlp:AuthnRequest>"
        )

        deflated = zlib.compress(authn_request.encode("utf-8"))[2:-4]
        saml_request = base64.b64encode(deflated).decode("utf-8")
        relay_state = self._encode_state_token(
            {
                "purpose": self.SAML_STATE_PURPOSE,
                "customer_id": resolution.customer_id,
                "email": resolution.email,
                "protocol": "saml",
                "provider_id": resolution.provider_id,
            }
        )
        return f"{sso_url}?{urlencode({'SAMLRequest': saml_request, 'RelayState': relay_state})}"

    def parse_saml_response(
        self,
        saml_response_b64: str,
        expected_audience: Optional[str] = None,
        provider_config: Optional[TenantSSOProvider] = None,
    ) -> Dict[str, Any]:
        """Parse and verify a signed SAML response, then extract identity claims."""
        if provider_config is None:
            raise SSOConfigurationError(
                "SAML provider configuration is required for signature verification."
            )

        verification_certificates = self._load_saml_verification_certificates(provider_config)
        try:
            xml_payload = base64.b64decode(saml_response_b64, validate=True)
            parser = etree.XMLParser(resolve_entities=False, no_network=True)
            root = etree.fromstring(xml_payload, parser=parser)
        except Exception as exc:
            raise SSOAuthenticationError("Invalid SAML response payload.") from exc

        ns = self._saml_namespaces()
        assertion = self._verify_and_extract_signed_assertion(root, verification_certificates)

        status_code = None
        # xml.etree doesn't support @attribute lookup in findtext; evaluate via element access.
        status_element = root.find(".//samlp:StatusCode", ns)
        if status_element is not None:
            status_code = status_element.attrib.get("Value")
        if status_code and status_code != "urn:oasis:names:tc:SAML:2.0:status:Success":
            raise SSOAuthenticationError("SAML authentication was not successful.")

        issuer = assertion.findtext(".//saml:Issuer", default="", namespaces=ns).strip() or None
        name_id = assertion.findtext(".//saml:Subject/saml:NameID", default="", namespaces=ns).strip()
        audience = assertion.findtext(
            ".//saml:Conditions/saml:AudienceRestriction/saml:Audience",
            default="",
            namespaces=ns,
        ).strip() or None

        if expected_audience and audience != expected_audience:
            raise SSOAuthenticationError("SAML audience restriction check failed.")

        conditions = assertion.find(".//saml:Conditions", ns)
        if conditions is not None:
            now = datetime.now(timezone.utc)
            not_before = conditions.attrib.get("NotBefore")
            not_on_or_after = conditions.attrib.get("NotOnOrAfter")
            if not_before:
                if self._parse_saml_timestamp(not_before) > now + timedelta(minutes=1):
                    raise SSOAuthenticationError("SAML assertion is not yet valid.")
            if not_on_or_after:
                if self._parse_saml_timestamp(not_on_or_after) <= now - timedelta(minutes=1):
                    raise SSOAuthenticationError("SAML assertion has expired.")

        attributes: Dict[str, str] = {}
        for attribute in assertion.findall(".//saml:AttributeStatement/saml:Attribute", ns):
            attr_name = attribute.attrib.get("Name", "").strip()
            if not attr_name:
                continue
            values = attribute.findall("saml:AttributeValue", ns)
            if not values:
                continue
            value_text = (values[0].text or "").strip()
            if value_text:
                attributes[attr_name] = value_text

        email = self._extract_email_from_saml(name_id=name_id, attributes=attributes)
        subject = name_id or attributes.get(
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
            "",
        ).strip()
        if not subject:
            raise SSOAuthenticationError("SAML response missing subject identifier.")

        claims = {
            "sub": subject,
            "email": email,
            "given_name": attributes.get(
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"
            )
            or attributes.get("given_name"),
            "family_name": attributes.get(
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"
            )
            or attributes.get("family_name"),
            "name": attributes.get("name")
            or attributes.get("displayName")
            or attributes.get(
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
            ),
            "issuer": issuer,
            "audience": audience,
            "attributes": attributes,
        }
        return claims

    @staticmethod
    def _saml_namespaces() -> Dict[str, str]:
        return {
            "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
            "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
            "md": "urn:oasis:names:tc:SAML:2.0:metadata",
            "ds": "http://www.w3.org/2000/09/xmldsig#",
        }

    @staticmethod
    def _normalize_pem_certificate(raw_certificate: str) -> Optional[str]:
        value = (raw_certificate or "").strip()
        if not value:
            return None

        body = (
            value.replace("-----BEGIN CERTIFICATE-----", "")
            .replace("-----END CERTIFICATE-----", "")
        )
        body = "".join(body.split())
        if not body:
            return None

        wrapped = "\n".join(body[i : i + 64] for i in range(0, len(body), 64))
        return f"-----BEGIN CERTIFICATE-----\n{wrapped}\n-----END CERTIFICATE-----"

    @classmethod
    def _extract_pem_certificates(cls, raw_certificates: str) -> list[str]:
        value = (raw_certificates or "").strip()
        if not value:
            return []

        matches = re.findall(
            r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
            value,
            flags=re.DOTALL,
        )
        if not matches:
            normalized = cls._normalize_pem_certificate(value)
            return [normalized] if normalized else []

        normalized_certs: list[str] = []
        for match in matches:
            normalized = cls._normalize_pem_certificate(match)
            if normalized:
                normalized_certs.append(normalized)
        return normalized_certs

    def _extract_saml_certificates_from_metadata(self, metadata_xml: str) -> list[str]:
        try:
            parser = etree.XMLParser(resolve_entities=False, no_network=True)
            metadata_root = etree.fromstring(metadata_xml.encode("utf-8"), parser=parser)
        except etree.XMLSyntaxError as exc:
            raise SSOConfigurationError("SAML metadata XML is invalid.") from exc

        ns = self._saml_namespaces()
        certificate_nodes = metadata_root.xpath(
            ".//md:IDPSSODescriptor/md:KeyDescriptor[not(@use) or @use='signing']//ds:X509Certificate",
            namespaces=ns,
        )
        if not certificate_nodes:
            certificate_nodes = metadata_root.xpath(".//ds:X509Certificate", namespaces=ns)

        certificates: list[str] = []
        for node in certificate_nodes:
            if node.text and node.text.strip():
                certificates.extend(self._extract_pem_certificates(node.text))
        return certificates

    def _load_saml_verification_certificates(self, config: TenantSSOProvider) -> list[str]:
        certificates: list[str] = []

        configured_certificate = self._decrypt_secret(
            config,
            TenantSSOProviderService.SAML_X509_CERT_ENCRYPTED,
        )
        if configured_certificate:
            certificates.extend(self._extract_pem_certificates(configured_certificate))

        metadata_url = str(self._config_data(config).get("saml_metadata_url") or "").strip()
        if not certificates and metadata_url:
            try:
                response = httpx.get(metadata_url, timeout=10.0)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SSOConfigurationError(
                    "Failed to fetch SAML metadata for signature verification."
                ) from exc
            certificates.extend(self._extract_saml_certificates_from_metadata(response.text))

        unique_certificates: list[str] = []
        seen: set[str] = set()
        for certificate in certificates:
            cert_value = certificate.strip()
            if not cert_value or cert_value in seen:
                continue
            seen.add(cert_value)
            unique_certificates.append(cert_value)

        if not unique_certificates:
            raise SSOConfigurationError(
                "SAML signing certificate is required for signature verification."
            )

        return unique_certificates

    def _verify_and_extract_signed_assertion(
        self,
        root: etree._Element,
        verification_certificates: list[str],
    ) -> etree._Element:
        ns = self._saml_namespaces()
        if not root.xpath(".//ds:Signature", namespaces=ns):
            raise SSOAuthenticationError("SAML response is missing an XML digital signature.")

        verification_targets = [root, *root.xpath(".//saml:Assertion", namespaces=ns)]
        last_error: Optional[Exception] = None
        for certificate in verification_certificates:
            for target in verification_targets:
                try:
                    verified = XMLVerifier().verify(target, x509_cert=certificate)
                except InvalidSignature as exc:
                    last_error = exc
                    continue
                except Exception as exc:  # pragma: no cover - defensive for parser/library failures
                    last_error = exc
                    continue

                signed_xml = verified.signed_xml
                if signed_xml is None:
                    continue
                signed_tag = etree.QName(signed_xml.tag).localname
                if signed_tag == "Assertion":
                    return signed_xml
                if signed_tag == "Response":
                    response_assertion = signed_xml.find(".//saml:Assertion", ns)
                    if response_assertion is not None:
                        return response_assertion

        raise SSOAuthenticationError("SAML signature verification failed.") from last_error

    @staticmethod
    def _parse_saml_timestamp(value: str) -> datetime:
        ts = value.strip()
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        parsed = datetime.fromisoformat(ts)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _extract_email_from_saml(name_id: str, attributes: Dict[str, str]) -> Optional[str]:
        candidate_keys = [
            "email",
            "mail",
            "emailaddress",
            "EmailAddress",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        ]
        for key in candidate_keys:
            value = attributes.get(key)
            if value and "@" in value:
                return value.strip().lower()
        if name_id and "@" in name_id:
            return name_id.strip().lower()
        return None

    @staticmethod
    def extract_identity_from_claims(claims: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Normalize identity claims from OIDC or parsed SAML payload."""
        email = (
            claims.get("email")
            or claims.get("upn")
            or claims.get("preferred_username")
            or claims.get("unique_name")
        )
        normalized_email = str(email).strip().lower() if email else None
        subject = str(claims.get("sub") or "").strip() or None
        given_name = (claims.get("given_name") or "").strip() or None
        family_name = (claims.get("family_name") or "").strip() or None
        full_name = (
            (claims.get("name") or "").strip()
            or " ".join([part for part in [given_name, family_name] if part]).strip()
            or None
        )
        return {
            "subject": subject,
            "email": normalized_email,
            "given_name": given_name,
            "family_name": family_name,
            "full_name": full_name,
        }

    @staticmethod
    def _generate_system_password(length: int = 20) -> str:
        """Generate strong non-interactive password for SSO-created users."""
        if length < 12:
            length = 12
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*()-_=+"
        # Ensure minimum complexity
        required = [
            secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ"),
            secrets.choice("abcdefghijkmnopqrstuvwxyz"),
            secrets.choice("23456789"),
            secrets.choice("!@#$%^&*()-_=+"),
        ]
        remainder = [secrets.choice(alphabet) for _ in range(length - len(required))]
        chars = required + remainder
        secrets.SystemRandom().shuffle(chars)
        return "".join(chars)

    def _next_unique_username(self, email: Optional[str], subject: Optional[str]) -> str:
        seed = self._username_from_email(email or "")
        if not seed:
            seed = f"sso_{(subject or 'user').replace('|', '_')[:24]}"
        seed = "".join(ch for ch in seed if ch.isalnum() or ch in ("_", "-", ".")) or "sso_user"
        username = seed
        suffix = 1
        while (
            self.db.query(User)
            .filter(func.lower(User.username) == func.lower(username))
            .first()
            is not None
        ):
            username = f"{seed}{suffix}"
            suffix += 1
        return username

    def _ensure_membership(self, user: User, customer_id: str) -> UserTenantMembership:
        membership = (
            self.db.query(UserTenantMembership)
            .filter(
                UserTenantMembership.user_id == user.id,
                UserTenantMembership.customer_id == customer_id,
            )
            .first()
        )
        if membership:
            return membership

        has_any_membership = (
            self.db.query(UserTenantMembership)
            .filter(UserTenantMembership.user_id == user.id)
            .count()
            > 0
        )
        membership = UserTenantMembership(
            user_id=user.id,
            customer_id=customer_id,
            is_default=not has_any_membership,
            first_login_completed=False,
        )
        self.db.add(membership)
        return membership

    def _assign_jit_role(self, user: User, customer_id: str, role_name: str) -> None:
        role = (
            self.db.query(Role)
            .filter(
                func.lower(Role.name) == func.lower(role_name),
                Role.customer_id == customer_id,
                Role.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not role and role_name.lower() != "viewer":
            role = (
                self.db.query(Role)
                .filter(
                    func.lower(Role.name) == "viewer",
                    Role.customer_id == customer_id,
                    Role.is_active == True,  # noqa: E712
                )
                .first()
            )

        if role and role not in user.roles:
            user.roles.append(role)

    def link_or_provision_user(
        self,
        resolution: LoginResolution,
        subject: str,
        email: Optional[str],
        full_name: Optional[str],
        claims: Dict[str, Any],
    ) -> User:
        """
        Resolve or create a user for an SSO login.

        Linking order:
        1. existing user_sso_identities row by subject/provider/tenant
        2. existing user by email (case-insensitive)
        3. JIT create user if enabled
        """
        if not resolution.customer_id or not resolution.config:
            raise SSOProvisioningError("Tenant context is required for SSO login.")
        if not subject:
            raise SSOProvisioningError("SSO subject is required.")

        customer_id = resolution.customer_id
        provider_type = resolution.provider_type or "generic"
        protocol = resolution.protocol or "oidc"
        normalized_email = self._normalize_email(email or "") if email else None

        identity = (
            self.db.query(UserSSOIdentity)
            .options(joinedload(UserSSOIdentity.user).joinedload(User.roles))
            .filter(
                UserSSOIdentity.customer_id == customer_id,
                UserSSOIdentity.provider_type == provider_type,
                UserSSOIdentity.protocol == protocol,
                UserSSOIdentity.external_subject == subject,
            )
            .first()
        )

        user: Optional[User] = identity.user if identity else None
        if not user and normalized_email:
            user = self._get_user_by_email(normalized_email, with_roles=True)

        if user:
            membership = (
                self.db.query(UserTenantMembership)
                .filter(
                    UserTenantMembership.user_id == user.id,
                    UserTenantMembership.customer_id == customer_id,
                )
                .first()
            )
            if not membership:
                if not resolution.jit_provisioning_enabled:
                    raise SSOProvisioningError(
                        "Account is not provisioned for this organization. Contact your admin."
                    )
                self._ensure_membership(user, customer_id)
                self._assign_jit_role(user, customer_id, resolution.jit_default_role)
        else:
            if not resolution.jit_provisioning_enabled:
                raise SSOProvisioningError(
                    "Account is not provisioned for this organization. Contact your admin."
                )
            if not normalized_email:
                raise SSOProvisioningError(
                    "JIT provisioning requires an email claim from the identity provider."
                )

            username = self._next_unique_username(normalized_email, subject)
            user = User(
                email=normalized_email,
                username=username,
                full_name=full_name,
                hashed_password="",
                customer_id=customer_id,
                is_active=True,
                is_superuser=False,
            )
            user.set_password(self._generate_system_password())
            self.db.add(user)
            self.db.flush()

            self._ensure_membership(user, customer_id)
            self._assign_jit_role(user, customer_id, resolution.jit_default_role)

        if full_name and not user.full_name:
            user.full_name = full_name

        # Update active tenant context to the current login tenant.
        user.customer_id = customer_id

        if not identity:
            identity = UserSSOIdentity(
                user_id=user.id,
                customer_id=customer_id,
                provider_type=provider_type,
                protocol=protocol,
                external_subject=subject,
                external_email=normalized_email,
                claims_snapshot=claims,
                last_login_at=datetime.now(timezone.utc),
            )
            self.db.add(identity)
        else:
            identity.external_email = normalized_email
            identity.claims_snapshot = claims
            identity.last_login_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(user)
        return user
