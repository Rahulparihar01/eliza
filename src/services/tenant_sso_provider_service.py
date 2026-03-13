"""
Tenant SSO provider/domain services.

Phase 2 scope:
- Manage multiple SSO providers per tenant
- Manage tenant domains and TXT verification status
"""

from __future__ import annotations

from datetime import datetime, timezone
import secrets
from typing import Any, Dict, List

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.schemas.sso_settings import (
    SSODomainStatus,
    TenantSSODomainCreateRequest,
    TenantSSODomainResponse,
    TenantSSOPolicyResponse,
    TenantSSOPolicyUpdateRequest,
    TenantSSOProviderResponse,
    TenantSSOProviderUpsertRequest,
)
from src.models.tenant_sso import TenantSSOConfig, TenantSSODomain, TenantSSOProvider
from src.utils.encryption import EncryptionError, encrypt_value


class TenantSSOProviderService:
    """Service for tenant-scoped SSO provider and domain management."""

    OIDC_CLIENT_SECRET_ENCRYPTED = "oidc_client_secret_encrypted"
    SAML_X509_CERT_ENCRYPTED = "saml_x509_cert_encrypted"
    DOMAIN_TOKEN_PREFIX = "eliza-domain-verify=t_"

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        value = (domain or "").strip().lower()
        return value.rstrip(".")

    @staticmethod
    def _extract_txt_value(raw_value: str) -> str:
        # DNS JSON APIs often return TXT values wrapped with one or more quotes.
        value = (raw_value or "").strip()
        while len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1].strip()
        return value

    def _provider_to_response(self, provider: TenantSSOProvider) -> TenantSSOProviderResponse:
        config_data: Dict[str, Any] = provider.config_data or {}
        secret_data: Dict[str, Any] = provider.secret_data_encrypted or {}
        return TenantSSOProviderResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_type=provider.provider_type,
            protocol=provider.protocol,
            display_name=provider.display_name,
            is_enabled=provider.is_enabled,
            jit_provisioning_enabled=provider.jit_provisioning_enabled,
            jit_default_role=provider.jit_default_role,
            oidc_issuer_url=config_data.get("oidc_issuer_url"),
            oidc_client_id=config_data.get("oidc_client_id"),
            oidc_scopes=config_data.get("oidc_scopes") or ["openid", "profile", "email"],
            has_oidc_client_secret=bool(secret_data.get(self.OIDC_CLIENT_SECRET_ENCRYPTED)),
            saml_entity_id=config_data.get("saml_entity_id"),
            saml_sso_url=config_data.get("saml_sso_url"),
            saml_metadata_url=config_data.get("saml_metadata_url"),
            has_saml_x509_cert=bool(secret_data.get(self.SAML_X509_CERT_ENCRYPTED)),
            last_test_status=provider.last_test_status,
            last_test_error=provider.last_test_error,
            last_tested_at=provider.last_tested_at.isoformat() if provider.last_tested_at else None,
        )

    def _domain_to_response(self, domain: TenantSSODomain) -> TenantSSODomainResponse:
        return TenantSSODomainResponse(
            id=domain.id,
            customer_id=domain.customer_id,
            domain=domain.domain,
            verification_token=domain.verification_token,
            status=domain.status,
            verified_at=domain.verified_at.isoformat() if domain.verified_at else None,
            last_checked_at=domain.last_checked_at.isoformat() if domain.last_checked_at else None,
            last_check_error=domain.last_check_error,
        )

    def get_policy(self, customer_id: str) -> TenantSSOPolicyResponse:
        config = (
            self.db.query(TenantSSOConfig)
            .filter(TenantSSOConfig.customer_id == customer_id)
            .first()
        )
        if not config:
            return TenantSSOPolicyResponse(
                login_mode="password_only",
                domain_verification_required=True,
            )
        return TenantSSOPolicyResponse(
            login_mode=config.login_mode,
            domain_verification_required=config.domain_verification_required,
        )

    def update_policy(
        self,
        customer_id: str,
        request: TenantSSOPolicyUpdateRequest,
        updated_by_user_id: int | None,
    ) -> TenantSSOPolicyResponse:
        config = (
            self.db.query(TenantSSOConfig)
            .filter(TenantSSOConfig.customer_id == customer_id)
            .first()
        )
        if not config:
            config = TenantSSOConfig(customer_id=customer_id)
            self.db.add(config)

        config.login_mode = request.login_mode.value
        config.domain_verification_required = request.domain_verification_required
        config.updated_by_user_id = updated_by_user_id
        self.db.commit()
        self.db.refresh(config)
        return TenantSSOPolicyResponse(
            login_mode=config.login_mode,
            domain_verification_required=config.domain_verification_required,
        )

    def list_providers(self, customer_id: str) -> List[TenantSSOProviderResponse]:
        providers = (
            self.db.query(TenantSSOProvider)
            .filter(TenantSSOProvider.customer_id == customer_id)
            .order_by(TenantSSOProvider.provider_type.asc(), TenantSSOProvider.protocol.asc())
            .all()
        )
        return [self._provider_to_response(provider) for provider in providers]

    def get_provider(self, customer_id: str, provider_id: int) -> TenantSSOProviderResponse:
        provider = (
            self.db.query(TenantSSOProvider)
            .filter(
                TenantSSOProvider.id == provider_id,
                TenantSSOProvider.customer_id == customer_id,
            )
            .first()
        )
        if not provider:
            raise ValueError("SSO provider not found")
        return self._provider_to_response(provider)

    def create_provider(
        self,
        customer_id: str,
        request: TenantSSOProviderUpsertRequest,
        updated_by_user_id: int | None,
    ) -> TenantSSOProviderResponse:
        config_data: Dict[str, Any] = {
            "oidc_issuer_url": request.oidc_issuer_url,
            "oidc_client_id": request.oidc_client_id,
            "oidc_scopes": request.oidc_scopes,
            "saml_entity_id": request.saml_entity_id,
            "saml_sso_url": request.saml_sso_url,
            "saml_metadata_url": request.saml_metadata_url,
        }
        secret_data_encrypted: Dict[str, Any] = {}

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

        provider = TenantSSOProvider(
            customer_id=customer_id,
            provider_type=request.provider_type.value,
            protocol=request.protocol.value,
            display_name=request.display_name,
            is_enabled=request.is_enabled,
            config_data=config_data,
            secret_data_encrypted=secret_data_encrypted,
            jit_provisioning_enabled=request.jit_provisioning_enabled,
            jit_default_role=request.jit_default_role,
            updated_by_user_id=updated_by_user_id,
            last_test_status=None,
            last_test_error=None,
            last_tested_at=None,
        )
        self.db.add(provider)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError(
                "A provider with this provider type and protocol already exists for this tenant."
            ) from exc
        self.db.refresh(provider)
        return self._provider_to_response(provider)

    def update_provider(
        self,
        customer_id: str,
        provider_id: int,
        request: TenantSSOProviderUpsertRequest,
        updated_by_user_id: int | None,
    ) -> TenantSSOProviderResponse:
        provider = (
            self.db.query(TenantSSOProvider)
            .filter(
                TenantSSOProvider.id == provider_id,
                TenantSSOProvider.customer_id == customer_id,
            )
            .first()
        )
        if not provider:
            raise ValueError("SSO provider not found")

        existing_secret_data = dict(provider.secret_data_encrypted or {})
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

        provider.provider_type = request.provider_type.value
        provider.protocol = request.protocol.value
        provider.display_name = request.display_name
        provider.is_enabled = request.is_enabled
        provider.jit_provisioning_enabled = request.jit_provisioning_enabled
        provider.jit_default_role = request.jit_default_role
        provider.updated_by_user_id = updated_by_user_id
        provider.config_data = {
            "oidc_issuer_url": request.oidc_issuer_url,
            "oidc_client_id": request.oidc_client_id,
            "oidc_scopes": request.oidc_scopes,
            "saml_entity_id": request.saml_entity_id,
            "saml_sso_url": request.saml_sso_url,
            "saml_metadata_url": request.saml_metadata_url,
        }
        provider.secret_data_encrypted = secret_data_encrypted
        provider.last_test_status = None
        provider.last_test_error = None
        provider.last_tested_at = None

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError(
                "A provider with this provider type and protocol already exists for this tenant."
            ) from exc
        self.db.refresh(provider)
        return self._provider_to_response(provider)

    def delete_provider(self, customer_id: str, provider_id: int) -> None:
        provider = (
            self.db.query(TenantSSOProvider)
            .filter(
                TenantSSOProvider.id == provider_id,
                TenantSSOProvider.customer_id == customer_id,
            )
            .first()
        )
        if not provider:
            raise ValueError("SSO provider not found")
        self.db.delete(provider)
        self.db.commit()

    def test_provider(self, customer_id: str, provider_id: int) -> TenantSSOProviderResponse:
        provider = (
            self.db.query(TenantSSOProvider)
            .filter(
                TenantSSOProvider.id == provider_id,
                TenantSSOProvider.customer_id == customer_id,
            )
            .first()
        )
        if not provider:
            raise ValueError("SSO provider not found")

        config_data: Dict[str, Any] = provider.config_data or {}
        try:
            if provider.protocol == "oidc":
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
            elif provider.protocol == "saml":
                sso_url = str(config_data.get("saml_sso_url") or "").strip()
                metadata_url = str(config_data.get("saml_metadata_url") or "").strip()
                if not sso_url:
                    raise ValueError("SAML SSO URL is missing")
                if metadata_url:
                    response = httpx.get(metadata_url, timeout=12.0)
                    response.raise_for_status()
            else:
                raise ValueError("Unsupported SSO protocol")

            provider.last_test_status = "success"
            provider.last_test_error = None
        except Exception as exc:
            provider.last_test_status = "failed"
            provider.last_test_error = str(exc)

        provider.last_tested_at = self._now()
        self.db.commit()
        self.db.refresh(provider)
        return self._provider_to_response(provider)

    def list_domains(self, customer_id: str) -> List[TenantSSODomainResponse]:
        domains = (
            self.db.query(TenantSSODomain)
            .filter(TenantSSODomain.customer_id == customer_id)
            .order_by(TenantSSODomain.domain.asc())
            .all()
        )
        return [self._domain_to_response(domain) for domain in domains]

    def create_domain(
        self,
        customer_id: str,
        request: TenantSSODomainCreateRequest,
    ) -> TenantSSODomainResponse:
        domain = self._normalize_domain(request.domain)
        verification_token = self.DOMAIN_TOKEN_PREFIX + secrets.token_urlsafe(18)
        row = TenantSSODomain(
            customer_id=customer_id,
            domain=domain,
            verification_token=verification_token,
            status=SSODomainStatus.PENDING.value,
            verified_at=None,
            last_checked_at=None,
            last_check_error=None,
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Domain already exists for this tenant") from exc
        self.db.refresh(row)
        return self._domain_to_response(row)

    def delete_domain(self, customer_id: str, domain_id: int) -> None:
        row = (
            self.db.query(TenantSSODomain)
            .filter(
                TenantSSODomain.id == domain_id,
                TenantSSODomain.customer_id == customer_id,
            )
            .first()
        )
        if not row:
            raise ValueError("Domain not found")
        self.db.delete(row)
        self.db.commit()

    def _lookup_txt_records(self, domain: str) -> List[str]:
        # DNS-over-HTTPS via Cloudflare/Google fallback for portability.
        endpoints = [
            "https://cloudflare-dns.com/dns-query",
            "https://dns.google/resolve",
        ]
        for endpoint in endpoints:
            try:
                response = httpx.get(
                    endpoint,
                    params={"name": domain, "type": "TXT"},
                    headers={"accept": "application/dns-json"},
                    timeout=8.0,
                )
                response.raise_for_status()
                payload = response.json()
                answers = payload.get("Answer") or []
                values = []
                for answer in answers:
                    data = answer.get("data")
                    if isinstance(data, str) and data.strip():
                        values.append(self._extract_txt_value(data))
                return values
            except Exception:
                continue
        raise ValueError("Unable to resolve DNS TXT records for verification")

    def verify_domain(self, customer_id: str, domain_id: int) -> TenantSSODomainResponse:
        row = (
            self.db.query(TenantSSODomain)
            .filter(
                TenantSSODomain.id == domain_id,
                TenantSSODomain.customer_id == customer_id,
            )
            .first()
        )
        if not row:
            raise ValueError("Domain not found")

        now = self._now()
        try:
            txt_values = self._lookup_txt_records(row.domain)
            if row.verification_token in txt_values:
                row.status = SSODomainStatus.VERIFIED.value
                row.verified_at = now
                row.last_checked_at = now
                row.last_check_error = None
            else:
                row.status = SSODomainStatus.FAILED.value
                row.last_checked_at = now
                row.last_check_error = (
                    "Verification token was not found in DNS TXT records."
                )
        except Exception as exc:
            row.status = SSODomainStatus.FAILED.value
            row.last_checked_at = now
            row.last_check_error = str(exc)

        self.db.commit()
        self.db.refresh(row)
        return self._domain_to_response(row)
