"""
AI Enablement Platform - Multi-Tenant Admin Models

Database models for multi-tenant administration:
- Platform Features and Feature Permissions
- Tenant Feature Allocations
- Tenant Roles and Role Permissions
- User Role Assignments
- User Invites
- Platform Administrators
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from typing import List, Optional, Set
import secrets

from .database import BaseModel, Base


class PlatformFeature(BaseModel):
    """
    Master list of all platform features.
    
    Platform admins allocate features to tenants. Each feature has
    associated permissions that can be granted to roles.
    """
    
    __tablename__ = "platform_features"
    __table_args__ = ({'extend_existing': True},)
    
    feature_key = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True, index=True)  # data, intelligence, admin, config
    icon = Column(String(50), nullable=True)  # Heroicon name
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    permissions = relationship(
        "FeaturePermission", 
        back_populates="feature", 
        cascade="all, delete-orphan",
        order_by="FeaturePermission.sort_order"
    )
    allocations = relationship(
        "TenantFeatureAllocation", 
        back_populates="feature"
    )
    
    def __repr__(self):
        return f"<PlatformFeature(id={self.id}, feature_key='{self.feature_key}')>"


class FeaturePermission(BaseModel):
    """
    Permissions available within each feature.
    
    Each permission can be granted to tenant roles. The permission_key
    follows the format: feature:action (e.g., 'documents:create').
    """
    
    __tablename__ = "feature_permissions"
    __table_args__ = ({'extend_existing': True},)
    
    feature_id = Column(Integer, ForeignKey("platform_features.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_key = Column(String(100), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    
    # Relationships
    feature = relationship("PlatformFeature", back_populates="permissions")
    
    def __repr__(self):
        return f"<FeaturePermission(id={self.id}, permission_key='{self.permission_key}')>"


class TenantFeatureAllocation(BaseModel):
    """
    Features allocated to each tenant by platform admin.
    
    Controls which features a tenant can access and which permissions
    are available to assign to their roles.
    """
    
    __tablename__ = "tenant_feature_allocations"
    __table_args__ = ({'extend_existing': True},)
    
    customer_id = Column(String(100), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False, index=True)
    feature_id = Column(Integer, ForeignKey("platform_features.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    allocated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    allocated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    usage_limit = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    customer = relationship("Customer", backref="feature_allocations")
    feature = relationship("PlatformFeature", back_populates="allocations")
    allocator = relationship("User", foreign_keys=[allocated_by])
    
    @property
    def is_expired(self) -> bool:
        """Check if allocation has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f"<TenantFeatureAllocation(customer_id='{self.customer_id}', feature_id={self.feature_id})>"


class UserInvite(BaseModel):
    """
    Invites for new users created by tenant admins.
    
    Tenant admin creates an invite with pre-assigned roles.
    User receives link, sets password, and account is activated.
    """
    
    __tablename__ = "user_invites"
    __table_args__ = ({'extend_existing': True},)
    
    customer_id = Column(String(100), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    invite_token = Column(String(255), unique=True, nullable=False, index=True)
    role_ids = Column(ARRAY(Integer), nullable=True)  # Pre-assigned role IDs
    
    # Invite lifecycle
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending, accepted, expired, revoked
    
    # Acceptance tracking
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Revocation tracking
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    customer = relationship("Customer", backref="user_invites")
    creator = relationship("User", foreign_keys=[created_by])
    accepted_user = relationship("User", foreign_keys=[accepted_by_user_id])
    revoker = relationship("User", foreign_keys=[revoked_by])
    
    @classmethod
    def generate_token(cls) -> str:
        """Generate a secure invite token."""
        return secrets.token_urlsafe(32)
    
    @classmethod
    def create_invite(
        cls,
        customer_id: str,
        email: str,
        created_by: int,
        full_name: Optional[str] = None,
        role_ids: Optional[List[int]] = None,
        expires_in_days: int = 7
    ) -> "UserInvite":
        """Create a new user invite."""
        return cls(
            customer_id=customer_id,
            email=email,
            full_name=full_name,
            invite_token=cls.generate_token(),
            role_ids=role_ids,
            created_by=created_by,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
            status="pending"
        )
    
    @property
    def is_expired(self) -> bool:
        """Check if invite has expired."""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if invite is still valid (pending and not expired)."""
        return self.status == "pending" and not self.is_expired
    
    def accept(self, user_id: int) -> None:
        """Mark invite as accepted."""
        self.status = "accepted"
        self.accepted_at = datetime.utcnow()
        self.accepted_by_user_id = user_id
    
    def revoke(self, revoked_by: int) -> None:
        """Revoke the invite."""
        self.status = "revoked"
        self.revoked_at = datetime.utcnow()
        self.revoked_by = revoked_by
    
    def __repr__(self):
        return f"<UserInvite(id={self.id}, email='{self.email}', status='{self.status}')>"


class PlatformAdmin(BaseModel):
    """
    Platform-level administrators (Eliza team).
    
    Platform admins can create tenants, allocate features,
    and manage other platform admins.
    """
    
    __tablename__ = "platform_admins"
    __table_args__ = ({'extend_existing': True},)
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    admin_level = Column(String(50), nullable=False, default="admin", index=True)  # admin, super_admin
    
    # Permissions
    can_create_tenants = Column(Boolean, nullable=False, default=True)
    can_allocate_features = Column(Boolean, nullable=False, default=True)
    can_manage_platform_admins = Column(Boolean, nullable=False, default=False)
    can_impersonate = Column(Boolean, nullable=False, default=False)
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="platform_admin")
    creator = relationship("User", foreign_keys=[created_by])
    
    @property
    def is_super_admin(self) -> bool:
        """Check if this is a super admin."""
        return self.admin_level == "super_admin"
    
    def __repr__(self):
        return f"<PlatformAdmin(id={self.id}, user_id={self.user_id}, admin_level='{self.admin_level}')>"

