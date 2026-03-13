"""
User SSO identity linking model.

Maps an external IdP identity to an internal user scoped by tenant/provider.
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship

from src.models.database import BaseModel


class UserSSOIdentity(BaseModel):
    """Link table between external SSO identities and internal users."""

    __tablename__ = "user_sso_identities"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "provider_type",
            "protocol",
            "external_subject",
            name="uq_user_sso_identity_subject",
        ),
        UniqueConstraint(
            "user_id",
            "customer_id",
            "provider_type",
            "protocol",
            name="uq_user_sso_identity_user_provider",
        ),
        {"extend_existing": True},
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = Column(
        String(100),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider_type = Column(String(64), nullable=False, index=True)
    protocol = Column(String(16), nullable=False, index=True)  # oidc | saml
    external_subject = Column(String(512), nullable=False)
    external_email = Column(String(255), nullable=True, index=True)

    claims_snapshot = Column(JSON, nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    customer = relationship("Customer")

    def __repr__(self):
        return (
            f"<UserSSOIdentity(customer_id='{self.customer_id}', "
            f"provider='{self.provider_type}', protocol='{self.protocol}', "
            f"user_id={self.user_id})>"
        )
