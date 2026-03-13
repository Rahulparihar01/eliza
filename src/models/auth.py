"""
AI Enablement Platform - Authentication & RBAC Models

Database models for user authentication, roles, and permissions following
the Single-Tenant RBAC Specification and matching actual database schema.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Table, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta, timezone
import bcrypt
import secrets
from typing import List, Optional

from .database import Base


# Association table for many-to-many relationship between users and roles
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True),
    Column('assigned_at', DateTime, default=func.now()),
    Column('assigned_by', Integer, ForeignKey('users.id')),
    Column('active', Boolean, default=True),
    extend_existing=True
)

# Association table for many-to-many relationship between roles and permissions
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id'), primary_key=True),
    Column('granted_at', DateTime, default=func.now()),
    Column('granted_by', Integer, ForeignKey('users.id')),
    extend_existing=True
)


class User(Base):
    """User model matching actual database schema."""

    __tablename__ = 'users'
    __table_args__ = ({'extend_existing': True},)
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Core authentication fields (matching actual DB schema)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)  # Note: hashed_password not password_hash
    is_active = Column(Boolean, nullable=False, default=True)
    is_superuser = Column(Boolean, nullable=False, default=False)
    
    # Customer relationship (multi-tenancy)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)

    # Organizational structure (for resource scoping)
    department = Column(String(100), nullable=True, index=True)
    team = Column(String(100), nullable=True, index=True)

    # Localization settings
    preferred_language = Column(String(10), nullable=False, default='en')
    timezone = Column(String(50), nullable=False, default='UTC')
    
    # Security and login tracking
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_failed_login = Column(DateTime(timezone=True), nullable=True)
    force_password_change = Column(Boolean, default=False)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    
    # API access management
    api_key_hash = Column(String(255), nullable=True, index=True)
    api_key_created_at = Column(DateTime(timezone=True), nullable=True)
    
    # Enhanced security fields (from recent migrations)
    password_changed_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)  # IPv6 compatible
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    # Note: foreign_keys specified to disambiguate from Customer.deactivated_by FK
    customer = relationship(
        "Customer", 
        back_populates="users",
        foreign_keys=[customer_id]
    )
    roles = relationship("Role", secondary=user_roles, back_populates="users",
                        primaryjoin="User.id == user_roles.c.user_id",
                        secondaryjoin="Role.id == user_roles.c.role_id")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("UserAuditLog", back_populates="user")
    password_history = relationship("PasswordHistory", back_populates="user", cascade="all, delete-orphan")
    mfa_settings = relationship("UserMFA", back_populates="user", cascade="all, delete-orphan")
    tenant_memberships = relationship("UserTenantMembership", back_populates="user", cascade="all, delete-orphan")
    # TODO: UserAPIKey model needs to be created - temporarily commented out
    # api_keys = relationship("UserAPIKey", foreign_keys="UserAPIKey.user_id", back_populates="user", cascade="all, delete-orphan")
    
    def set_password(self, password: str) -> None:
        """Hash and set user password."""
        salt = bcrypt.gensalt()
        self.hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        self.password_changed_at = func.now()
    
    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return bcrypt.checkpw(password.encode('utf-8'), self.hashed_password.encode('utf-8'))
    
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until
    
    def lock_account(self, duration_minutes: int = 30) -> None:
        """Lock account for specified duration."""
        self.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
    
    def unlock_account(self) -> None:
        """Unlock account and reset failed attempts."""
        self.locked_until = None
        self.failed_login_attempts = 0
    
    def has_permission(self, permission: str, resource=None, context=None) -> bool:
        """Check if user has specific permission with optional resource scoping."""
        for role in self.roles:
            if role.has_permission(permission, resource, context, self):
                return True
        return False
    
    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions."""
        return any(self.has_permission(perm) for perm in permissions)
    
    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if user has all specified permissions."""
        return all(self.has_permission(perm) for perm in permissions)
    
    def get_permissions(self) -> List[str]:
        """Get all permissions for user across all roles."""
        permissions = set()
        for role in self.roles:
            permissions.update(role.get_permissions())
        return list(permissions)
    
    @property
    def display_name(self) -> str:
        """Get user's display name (full_name or username)."""
        return self.full_name or self.username
    
    @property
    def primary_role(self) -> Optional['Role']:
        """Get user's primary (highest) role."""
        if not self.roles:
            return None
        
        # Role hierarchy: viewer < analyst < manager < admin < super_admin
        role_hierarchy = {
            'viewer': 1,
            'analyst': 2,
            'manager': 3,
            'admin': 4,
            'super_admin': 5
        }
        
        return max(self.roles, key=lambda r: role_hierarchy.get(r.name, 0))


class Role(Base):
    """Role model for RBAC system with tenant scoping."""

    __tablename__ = 'roles'
    __table_args__ = ({'extend_existing': True},)
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Tenant scoping - NULL means platform-level role (e.g., platform_admin)
    customer_id = Column(String(100), ForeignKey('customers.customer_id', ondelete='CASCADE'), nullable=True, index=True)
    
    # System role flag - cannot be deleted by tenant admins
    is_system_role = Column(Boolean, default=False)
    
    # Hierarchy and inheritance
    parent_role_id = Column(Integer, ForeignKey('roles.id'), nullable=True)
    hierarchy_level = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Relationships
    customer = relationship("Customer", backref="roles")
    users = relationship("User", secondary=user_roles, back_populates="roles",
                        primaryjoin="Role.id == user_roles.c.role_id",
                        secondaryjoin="User.id == user_roles.c.user_id")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    parent_role = relationship("Role", remote_side=[id])
    child_roles = relationship("Role")
    
    @property
    def role_name(self) -> str:
        """Alias for name property for API compatibility."""
        return self.name
    
    @property
    def permission_count(self) -> int:
        """Get count of permissions assigned to this role."""
        return len(self.permissions) if self.permissions else 0
    
    @property
    def user_count(self) -> int:
        """Get count of users assigned to this role."""
        return len(self.users) if self.users else 0
    
    def has_permission(self, permission: str, resource=None, context=None, user=None) -> bool:
        """Check if role has specific permission with resource scoping (including inherited)."""
        # Check direct permissions
        for perm in self.permissions:
            if perm.name == permission or perm.name.endswith(':*'):
                # Handle wildcard permissions (e.g., 'documents:*')
                if perm.name.endswith(':*'):
                    resource_prefix = perm.name[:-2]  # Remove ':*'
                    if permission.startswith(f"{resource_prefix}:"):
                        # Check scope access if resource and user provided
                        if resource and user:
                            return perm.check_scope_access(
                                user,
                                getattr(resource, 'owner', None),
                                getattr(resource, 'department', None),
                                getattr(resource, 'team', None)
                            )
                        return True
                else:
                    # Exact permission match - check scope
                    if resource and user:
                        return perm.check_scope_access(
                            user,
                            getattr(resource, 'owner', None),
                            getattr(resource, 'department', None),
                            getattr(resource, 'team', None)
                        )
                    return True

        # Check inherited permissions from parent role
        if self.parent_role:
            return self.parent_role.has_permission(permission, resource, context, user)

        return False
    
    def get_permissions(self) -> List[str]:
        """Get all permissions for role (including inherited)."""
        permissions = set()
        
        # Add direct permissions
        for perm in self.permissions:
            permissions.add(perm.name)
        
        # Add inherited permissions
        if self.parent_role:
            permissions.update(self.parent_role.get_permissions())
        
        return list(permissions)


class Permission(Base):
    """Permission model for granular access control with resource scoping."""

    __tablename__ = 'permissions'
    __table_args__ = ({'extend_existing': True},)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    resource = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Resource scoping: 'own', 'team', 'department', 'all'
    scope = Column(String(20), nullable=False, default='all', index=True)

    # Contextual permissions and conditions
    conditions = Column(JSON, nullable=True)  # Store conditions as JSON

    # Metadata
    created_at = Column(DateTime, default=func.now())
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")

    def check_scope_access(self, user, resource_owner=None, resource_department=None, resource_team=None) -> bool:
        """Check if user has access based on permission scope."""
        if self.scope == 'all':
            return True
        elif self.scope == 'own':
            return resource_owner and user.id == resource_owner.id
        elif self.scope == 'team':
            return user.team and user.team == resource_team
        elif self.scope == 'department':
            return user.department and user.department == resource_department
        return False


class UserSession(Base):
    """User session tracking for security and concurrent session management."""

    __tablename__ = 'user_sessions'
    __table_args__ = ({'extend_existing': True},)
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=True, index=True)
    
    # Session metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    
    # Session lifecycle
    created_at = Column(DateTime, default=func.now())
    last_activity_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    @classmethod
    def generate_tokens(cls) -> tuple[str, str]:
        """Generate secure session and refresh tokens."""
        session_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        return session_token, refresh_token
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        expires_at = self.expires_at

        # Handle timezone-naive expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return now > expires_at
    
    def extend_session(self, hours: int = 8) -> None:
        """Extend session expiration."""
        self.expires_at = datetime.utcnow() + timedelta(hours=hours)
        self.last_activity_at = func.now()


class UserAuditLog(Base):
    """Comprehensive audit logging for security and compliance."""

    __tablename__ = 'user_audit_log'
    __table_args__ = ({'extend_existing': True},)
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)
    resource_id = Column(String(100), nullable=True, index=True)
    
    # Change tracking
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Request context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(255), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class PasswordHistory(Base):
    """Track password history to prevent reuse."""

    __tablename__ = 'password_history'
    __table_args__ = ({'extend_existing': True},)
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="password_history")

    @classmethod
    def add_password_to_history(cls, session, user_id: int, password_hash: str, max_history: int = 5):
        """Add password to history and maintain max history limit."""
        # Add new password to history
        new_entry = cls(user_id=user_id, password_hash=password_hash)
        session.add(new_entry)

        # Remove old entries beyond max_history
        old_entries = session.query(cls).filter(
            cls.user_id == user_id
        ).order_by(cls.created_at.desc()).offset(max_history).all()

        for entry in old_entries:
            session.delete(entry)

    @classmethod
    def is_password_reused(cls, session, user_id: int, password_hash: str, check_count: int = 5) -> bool:
        """Check if password was used in recent history."""
        recent_passwords = session.query(cls).filter(
            cls.user_id == user_id
        ).order_by(cls.created_at.desc()).limit(check_count).all()

        return any(entry.password_hash == password_hash for entry in recent_passwords)


class TemporaryRoleAssignment(Base):
    """Temporary role assignments with expiration."""

    __tablename__ = 'temporary_role_assignments'
    __table_args__ = ({'extend_existing': True},)
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    granted_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Assignment details
    reason = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    auto_revoke = Column(Boolean, default=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    role = relationship("Role")
    granter = relationship("User", foreign_keys=[granted_by])
    revoker = relationship("User", foreign_keys=[revoked_by])

    def is_expired(self) -> bool:
        """Check if temporary assignment is expired."""
        return datetime.utcnow() > self.expires_at


class UserMFA(Base):
    """Model for user multi-factor authentication settings."""
    __tablename__ = "user_mfa"
    __table_args__ = ({'extend_existing': True},)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mfa_type = Column(String(50), nullable=False)  # 'totp', 'email'
    secret_key = Column(String(255), nullable=True)  # For TOTP
    is_enabled = Column(Boolean, default=False)
    backup_codes = Column(JSON, nullable=True)  # List of backup codes
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    user = relationship("User", back_populates="mfa_settings")


class UserTenantMembership(Base):
    """
    Track user memberships across multiple tenants.
    
    A user can belong to multiple tenants with different roles in each.
    This model tracks:
    - Which tenants a user belongs to
    - Which tenant is their default (for login)
    - Whether they've completed first login to each tenant (for welcome popup)
    """
    __tablename__ = "user_tenant_memberships"
    __table_args__ = ({'extend_existing': True},)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Default tenant flag - only one membership per user should have this true
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Track first login to show welcome popup for multi-tenant users
    first_login_completed = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    # Relationships
    user = relationship("User", back_populates="tenant_memberships")
    customer = relationship("Customer", back_populates="user_memberships")