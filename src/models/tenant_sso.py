"""
Tenant SSO models.

Legacy `TenantSSOConfig` remains during migration.
New tables:
- `TenantSSOProvider`: provider-level configuration (multi-provider per tenant)
- `TenantSSODomain`: tenant domain ownership and verification status
"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.models.database import BaseModel


class TenantSSOConfig(BaseModel):
    """Legacy tenant-scoped SSO configuration (transition compatibility)."""

    __tablename__ = "tenant_sso_configs"
    __table_args__ = ({"extend_existing": True},)

    customer_id = Column(
        String(100),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Policy and provider metadata
    is_enabled = Column(Boolean, nullable=False, default=False)
    login_mode = Column(String(32), nullable=False, default="password_only")
    provider_type = Column(String(64), nullable=True, index=True)
    protocol = Column(String(16), nullable=True, index=True)  # oidc | saml
    provider_display_name = Column(String(255), nullable=True)

    # Tenant domain controls
    domain_allowlist = Column(JSON, nullable=True)  # ["acme.com", ...]
    domain_verification_required = Column(Boolean, nullable=False, default=True)

    # JIT provisioning policy
    jit_provisioning_enabled = Column(Boolean, nullable=False, default=False)
    jit_default_role = Column(String(100), nullable=False, default="viewer")

    # Public config (non-secret) and encrypted secret payload
    config_data = Column(JSON, nullable=True)
    secret_data_encrypted = Column(JSON, nullable=True)

    # Config test tracking
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    last_test_status = Column(String(32), nullable=True)  # success | failed
    last_test_error = Column(Text, nullable=True)

    # Audit attribution
    updated_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer = relationship("Customer")
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])

    def __repr__(self):
        return (
            f"<TenantSSOConfig(customer_id='{self.customer_id}', "
            f"protocol='{self.protocol}', provider='{self.provider_type}', mode='{self.login_mode}')>"
        )


class TenantSSOProvider(BaseModel):
    """Provider-level SSO configuration (supports multiple providers per tenant)."""

    __tablename__ = "tenant_sso_providers"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "provider_type",
            "protocol",
            name="uq_tenant_sso_providers_customer_provider_protocol",
        ),
        {"extend_existing": True},
    )

    customer_id = Column(
        String(100),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_type = Column(String(64), nullable=False, index=True)
    protocol = Column(String(16), nullable=False, index=True)  # oidc | saml
    display_name = Column(String(255), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=False, index=True)

    config_data = Column(JSON, nullable=True)
    secret_data_encrypted = Column(JSON, nullable=True)

    jit_provisioning_enabled = Column(Boolean, nullable=False, default=False)
    jit_default_role = Column(String(100), nullable=False, default="viewer")

    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    last_test_status = Column(String(32), nullable=True)  # success | failed
    last_test_error = Column(Text, nullable=True)

    updated_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer = relationship("Customer")
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])

    def __repr__(self):
        return (
            f"<TenantSSOProvider(customer_id='{self.customer_id}', "
            f"provider_type='{self.provider_type}', protocol='{self.protocol}', "
            f"is_enabled={self.is_enabled})>"
        )


class TenantSSODomain(BaseModel):
    """Tenant-managed domain with DNS TXT verification state."""

    __tablename__ = "tenant_sso_domains"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "domain",
            name="uq_tenant_sso_domains_customer_domain",
        ),
        {"extend_existing": True},
    )

    customer_id = Column(
        String(100),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    domain = Column(String(255), nullable=False, index=True)
    verification_token = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="pending")  # pending | verified | failed
    verified_at = Column(DateTime(timezone=True), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_check_error = Column(Text, nullable=True)

    customer = relationship("Customer")

    def __repr__(self):
        return (
            f"<TenantSSODomain(customer_id='{self.customer_id}', domain='{self.domain}', "
            f"status='{self.status}')>"
        )
