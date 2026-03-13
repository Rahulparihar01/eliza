"""
AI Enablement Platform - Multi-Tenant Admin Service

Service layer for multi-tenant administration operations.
Handles tenant management, role management, user invites, and feature allocation.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
import secrets
import logging

from src.models.tenant_admin import (
    PlatformFeature,
    FeaturePermission,
    TenantFeatureAllocation,
    UserInvite,
    PlatformAdmin
)
from src.models.customer import Customer
from src.models.auth import User, Role, Permission, user_roles, role_permissions
from src.api.schemas.tenant_admin import (
    TenantCreate,
    TenantRoleCreate,
    TenantRoleUpdate,
    UserInviteCreate,
    TenantUserCreate,
)

logger = logging.getLogger(__name__)


class TenantAdminService:
    """
    Service for tenant administration operations.
    
    Handles:
    - Feature management and allocation
    - Tenant role management
    - User management within a tenant
    - User invite flow
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # PLATFORM FEATURES
    # =========================================================================
    
    def get_all_features(self, include_inactive: bool = False) -> List[PlatformFeature]:
        """Get all platform features."""
        query = self.db.query(PlatformFeature)
        if not include_inactive:
            query = query.filter(PlatformFeature.is_active == True)
        return query.order_by(PlatformFeature.sort_order).all()
    
    def get_feature_by_key(self, feature_key: str) -> Optional[PlatformFeature]:
        """Get a feature by its key."""
        return self.db.query(PlatformFeature).filter(
            PlatformFeature.feature_key == feature_key
        ).first()
    
    def get_feature_with_permissions(self, feature_id: int) -> Optional[PlatformFeature]:
        """Get a feature with its permissions loaded."""
        return self.db.query(PlatformFeature).options(
            joinedload(PlatformFeature.permissions)
        ).filter(PlatformFeature.id == feature_id).first()
    
    def get_all_permissions(self) -> List[FeaturePermission]:
        """Get all feature permissions."""
        return self.db.query(FeaturePermission).join(PlatformFeature).filter(
            PlatformFeature.is_active == True
        ).order_by(PlatformFeature.sort_order, FeaturePermission.sort_order).all()
    
    # =========================================================================
    # TENANT FEATURE ALLOCATION
    # =========================================================================
    
    def get_tenant_allocations(self, customer_id: str) -> List[TenantFeatureAllocation]:
        """Get all feature allocations for a tenant."""
        return self.db.query(TenantFeatureAllocation).options(
            joinedload(TenantFeatureAllocation.feature)
        ).filter(
            TenantFeatureAllocation.customer_id == customer_id
        ).all()
    
    def get_allocated_feature_ids(self, customer_id: str) -> Set[int]:
        """Get the set of enabled feature IDs for a tenant."""
        allocations = self.db.query(TenantFeatureAllocation).filter(
            and_(
                TenantFeatureAllocation.customer_id == customer_id,
                TenantFeatureAllocation.is_enabled == True
            )
        ).all()
        return {a.feature_id for a in allocations}
    
    def allocate_feature(
        self,
        customer_id: str,
        feature_id: int,
        allocated_by: int,
        expires_at: Optional[datetime] = None,
        usage_limit: Optional[int] = None,
        notes: Optional[str] = None
    ) -> TenantFeatureAllocation:
        """Allocate a feature to a tenant."""
        # Check if allocation already exists
        existing = self.db.query(TenantFeatureAllocation).filter(
            and_(
                TenantFeatureAllocation.customer_id == customer_id,
                TenantFeatureAllocation.feature_id == feature_id
            )
        ).first()
        
        if existing:
            # Update existing allocation
            existing.is_enabled = True
            existing.allocated_by = allocated_by
            existing.allocated_at = datetime.utcnow()
            existing.expires_at = expires_at
            existing.usage_limit = usage_limit
            existing.notes = notes
            self.db.commit()
            return existing
        
        # Create new allocation
        allocation = TenantFeatureAllocation(
            customer_id=customer_id,
            feature_id=feature_id,
            is_enabled=True,
            allocated_by=allocated_by,
            expires_at=expires_at,
            usage_limit=usage_limit,
            notes=notes
        )
        self.db.add(allocation)
        self.db.commit()
        self.db.refresh(allocation)
        return allocation
    
    def deallocate_feature(self, customer_id: str, feature_id: int) -> bool:
        """Disable a feature for a tenant."""
        allocation = self.db.query(TenantFeatureAllocation).filter(
            and_(
                TenantFeatureAllocation.customer_id == customer_id,
                TenantFeatureAllocation.feature_id == feature_id
            )
        ).first()
        
        if allocation:
            allocation.is_enabled = False
            self.db.commit()
            return True
        return False
    
    def update_tenant_features(
        self,
        customer_id: str,
        feature_ids: List[int],
        allocated_by: int
    ) -> List[TenantFeatureAllocation]:
        """Update all feature allocations for a tenant (bulk update)."""
        # Get current allocations
        current_allocations = {
            a.feature_id: a 
            for a in self.get_tenant_allocations(customer_id)
        }
        
        new_feature_ids = set(feature_ids)
        
        # Enable new features
        for feature_id in new_feature_ids:
            if feature_id in current_allocations:
                current_allocations[feature_id].is_enabled = True
            else:
                allocation = TenantFeatureAllocation(
                    customer_id=customer_id,
                    feature_id=feature_id,
                    is_enabled=True,
                    allocated_by=allocated_by
                )
                self.db.add(allocation)
        
        # Disable removed features
        for feature_id, allocation in current_allocations.items():
            if feature_id not in new_feature_ids:
                allocation.is_enabled = False
        
        self.db.commit()
        return self.get_tenant_allocations(customer_id)
    
    def get_available_permissions_for_tenant(self, customer_id: str) -> List[FeaturePermission]:
        """Get permissions available to a tenant based on allocated features."""
        allocated_feature_ids = self.get_allocated_feature_ids(customer_id)
        if not allocated_feature_ids:
            return []
        
        return self.db.query(FeaturePermission).filter(
            FeaturePermission.feature_id.in_(allocated_feature_ids)
        ).order_by(FeaturePermission.feature_id, FeaturePermission.sort_order).all()
    
    # =========================================================================
    # TENANT ROLES (Using unified roles table)
    # =========================================================================
    
    def _get_allowed_permission_prefixes_for_tenant(self, customer_id: str) -> List[str]:
        """
        Build permission prefixes allowed by this tenant's feature allocations.

        Kept aligned with route-level permission scoping rules.
        """
        feature_permission_map = {
            # Admin features
            "users_roles": ["users:", "roles:"],
            "invites": ["invites:"],
            "settings": ["admin:settings:", "admin:email:"],
            "connectors": ["connections:"],
            "audit": ["audit:"],
            # Assistant features
            "documents": ["assistant:documents:", "assistant:domains:"],
            "assistant_chat": ["assistant:chat:", "assistant:access"],
            "business_intelligence": ["assistant:questions:"],
            # Recruiter features
            "talent_intelligence": [
                "recruiter:access",
                "recruiter:config:",
                "recruiter:dna:",
                "recruiter:results:",
                "recruiter:history:",
            ],
            "recruiter_blueprints": ["recruiter:blueprints:"],
            "recruiter_email_templates": ["recruiter:email_templates:", "recruiter:section_library:"],
            "recruiter_reference_checks": ["recruiter:reference_checks:"],
            # Labs features
            "labs_resume_parsing": ["labs:resume_parsing:"],
            "ai_providers": ["labs:agents:"],
            # Analytics features
            "adoption_dashboard": ["adoption:view_dashboard", "adoption:read:", "adoption:manage_sharing", "adoption:manage_sync", "adoption:manage_jobs"],
        }

        allocations = self.db.query(TenantFeatureAllocation).join(
            PlatformFeature
        ).filter(
            TenantFeatureAllocation.customer_id == customer_id,
            TenantFeatureAllocation.is_enabled == True
        ).all()

        allocated_feature_keys = {a.feature.feature_key for a in allocations}
        allowed_prefixes: List[str] = []
        for feature_key in allocated_feature_keys:
            allowed_prefixes.extend(feature_permission_map.get(feature_key, []))
        return allowed_prefixes

    def _role_matches_allocated_features(self, role: Role, allowed_prefixes: List[str]) -> bool:
        """
        Return True if role should be visible in tenant-scoped role surfaces.

        Always keep core baseline roles visible so invite/user-management UX remains usable.
        """
        always_visible_roles = {"admin", "editor", "viewer", "platform_admin"}
        role_name = (role.name or "").lower()
        if role_name in always_visible_roles:
            return True

        if not allowed_prefixes:
            return False

        role_permissions = role.permissions or []
        for perm in role_permissions:
            perm_name = getattr(perm, "name", None)
            if not perm_name:
                continue
            if perm_name == "platform:admin":
                continue
            if any(perm_name.startswith(prefix) or perm_name == prefix for prefix in allowed_prefixes):
                return True
        return False

    def get_tenant_roles(
        self,
        customer_id: str,
        include_inactive: bool = False,
        filter_by_allocated_features: bool = False,
    ) -> List[Role]:
        """Get tenant roles, optionally filtered by allocated feature scope."""
        query = self.db.query(Role).options(joinedload(Role.permissions)).filter(
            Role.customer_id == customer_id
        )
        if not include_inactive:
            query = query.filter(Role.is_active == True)

        roles = query.order_by(Role.is_system_role.desc(), Role.name).all()
        if not filter_by_allocated_features:
            return roles

        allowed_prefixes = self._get_allowed_permission_prefixes_for_tenant(customer_id)
        return [role for role in roles if self._role_matches_allocated_features(role, allowed_prefixes)]
    
    def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """Get a role by ID."""
        return self.db.query(Role).options(
            joinedload(Role.permissions)
        ).filter(Role.id == role_id).first()
    
    def create_role(
        self,
        customer_id: str,
        role_data: TenantRoleCreate,
        created_by: int
    ) -> Role:
        """Create a new role for a tenant."""
        role = Role(
            customer_id=customer_id,
            name=role_data.role_name,
            display_name=role_data.display_name or role_data.role_name,
            description=role_data.description,
            is_system_role=False,
            created_by=created_by
        )
        self.db.add(role)
        self.db.flush()  # Get the role ID
        
        # Add permissions
        if role_data.permission_ids:
            self._set_role_permissions(role.id, role_data.permission_ids)
        
        self.db.commit()
        self.db.refresh(role)
        return role
    
    def update_role(self, role_id: int, role_data: TenantRoleUpdate) -> Optional[Role]:
        """Update a role."""
        role = self.get_role_by_id(role_id)
        if not role:
            return None
        
        # Don't allow modifying system roles
        if role.is_system_role and (role_data.role_name or role_data.is_active is False):
            raise ValueError("Cannot modify system role name or deactivate")
        
        if role_data.role_name is not None:
            role.name = role_data.role_name
        if role_data.display_name is not None:
            role.display_name = role_data.display_name
        if role_data.description is not None:
            role.description = role_data.description
        if role_data.is_active is not None:
            role.is_active = role_data.is_active
        
        self.db.commit()
        self.db.refresh(role)
        return role
    
    def delete_role(self, role_id: int) -> bool:
        """Delete a role (soft delete by deactivating)."""
        role = self.get_role_by_id(role_id)
        if not role or role.is_system_role:
            return False
        
        role.is_active = False
        self.db.commit()
        return True
    
    def set_role_permissions(self, role_id: int, permission_ids: List[int]) -> Role:
        """Set all permissions for a role (replaces existing)."""
        role = self.get_role_by_id(role_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")
        
        self._set_role_permissions(role_id, permission_ids)
        self.db.commit()
        self.db.refresh(role)
        return role
    
    def _set_role_permissions(self, role_id: int, permission_ids: List[int]) -> None:
        """Internal: Set permissions for a role using the unified role_permissions table."""
        from datetime import datetime
        # Remove existing permissions
        self.db.execute(
            role_permissions.delete().where(role_permissions.c.role_id == role_id)
        )
        
        # Add new permissions
        for permission_id in permission_ids:
            self.db.execute(
                role_permissions.insert().values(
                    role_id=role_id,
                    permission_id=permission_id,
                    granted_at=datetime.utcnow()
                )
            )
    
    def add_permission_to_role(self, role_id: int, permission_id: int) -> bool:
        """Add a single permission to a role."""
        from datetime import datetime
        existing = self.db.execute(
            role_permissions.select().where(
                and_(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id
                )
            )
        ).first()
        
        if existing:
            return False  # Already exists
        
        self.db.execute(
            role_permissions.insert().values(
                role_id=role_id,
                permission_id=permission_id,
                granted_at=datetime.utcnow()
            )
        )
        self.db.commit()
        return True
    
    def remove_permission_from_role(self, role_id: int, permission_id: int) -> bool:
        """Remove a permission from a role."""
        result = self.db.execute(
            role_permissions.delete().where(
                and_(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id
                )
            )
        )
        self.db.commit()
        return result.rowcount > 0
    
    def create_default_roles_for_tenant(self, customer_id: str, allocated_feature_ids: Set[int]) -> Tuple[Role, Role, Role]:
        """
        Create default roles for a new tenant: tenant_admin, tenant_editor, tenant_viewer.
        
        IMPORTANT: Only assigns permissions for features that are allocated to this tenant.
        
        Returns: (tenant_admin, tenant_editor, tenant_viewer)
        """
        from datetime import datetime
        
        # Feature key to permission prefix mapping
        # This maps each feature to the permission prefixes it grants access to
        FEATURE_PERMISSION_MAP = {
            # Admin features (core tenant admin functionality)
            'users_roles': ['users:', 'roles:'],
            'invites': ['invites:'],
            'settings': ['admin:settings:', 'admin:email:'],
            'connectors': ['connections:'],
            'audit': ['audit:'],
            
            # AI Assistant features
            'documents': ['assistant:documents:', 'assistant:domains:'],
            'assistant_chat': ['assistant:chat:', 'assistant:access'],
            'business_intelligence': ['assistant:questions:'],
            
            # AI Recruiter features
            'talent_intelligence': ['recruiter:access', 'recruiter:config:', 'recruiter:dna:', 'recruiter:results:', 'recruiter:history:'],
            'recruiter_blueprints': ['recruiter:blueprints:'],
            'recruiter_email_templates': ['recruiter:email_templates:', 'recruiter:section_library:'],
            'recruiter_reference_checks': ['recruiter:reference_checks:'],
            
            # Labs features
            'labs_resume_parsing': ['labs:resume_parsing:'],
            'ai_providers': ['labs:agents:'],
            
            # Analytics features
            'adoption_dashboard': ['adoption:view_dashboard', 'adoption:read:', 'adoption:manage_sharing'],
            
            # Intelligence features (future)
            'hr_intelligence': [],  # TBD
            'operations_intelligence': [],  # TBD
        }
        
        # Get the allocated feature keys from feature IDs
        allocated_features = self.db.query(PlatformFeature).filter(
            PlatformFeature.id.in_(allocated_feature_ids)
        ).all() if allocated_feature_ids else []
        
        allocated_feature_keys = {f.feature_key for f in allocated_features}
        logger.info(f"Creating roles for tenant {customer_id} with allocated features: {allocated_feature_keys}")
        
        # Build the list of allowed permission prefixes based on allocated features
        allowed_prefixes = []
        for feature_key in allocated_feature_keys:
            if feature_key in FEATURE_PERMISSION_MAP:
                allowed_prefixes.extend(FEATURE_PERMISSION_MAP[feature_key])
        
        logger.info(f"Allowed permission prefixes: {allowed_prefixes}")
        
        # Get all permissions and filter based on allocated features
        all_permissions = self.db.query(Permission).all()
        
        def permission_is_allowed(perm_name: str) -> bool:
            """Check if a permission is allowed based on allocated features."""
            # platform:admin is never assigned to tenant roles
            if perm_name == 'platform:admin':
                return False
            
            # Check if permission matches any allowed prefix
            for prefix in allowed_prefixes:
                if perm_name.startswith(prefix) or perm_name == prefix:
                    return True
            return False
        
        # Filter permissions to only those allowed by allocated features
        allowed_permissions = [p for p in all_permissions if permission_is_allowed(p.name)]
        logger.info(f"Filtered {len(allowed_permissions)} permissions from {len(all_permissions)} total")
        
        # Define admin-only permission prefixes (these should NOT be given to viewers/editors)
        ADMIN_ONLY_PREFIXES = [
            'admin:',        # Admin settings
            'connections:',  # Data connections management
            'users:',        # User management
            'roles:',        # Role management
            'invites:',      # Invite management
            'audit:',        # Audit logs
        ]
        
        def is_admin_permission(perm_name: str) -> bool:
            """Check if a permission is admin-only."""
            return any(perm_name.startswith(prefix) for prefix in ADMIN_ONLY_PREFIXES)
        
        # Categorize allowed permissions
        all_read_permissions = [p for p in allowed_permissions if ':read' in p.name or ':list' in p.name or ':view' in p.name or ':access' in p.name]
        all_write_permissions = [p for p in allowed_permissions if ':create' in p.name or ':update' in p.name or ':edit' in p.name or ':upload' in p.name or ':ask' in p.name or ':analyze' in p.name]
        
        # Filter out admin permissions for non-admin roles
        content_read_permissions = [p for p in all_read_permissions if not is_admin_permission(p.name)]
        content_write_permissions = [p for p in all_write_permissions if not is_admin_permission(p.name)]
        
        # Tenant Admin - full access to allocated features
        tenant_admin_perms = allowed_permissions
        
        # Tenant Editor - read + write for CONTENT only (no admin permissions)
        tenant_editor_perms = list(set(content_read_permissions + content_write_permissions))
        
        # Tenant Viewer - read-only for CONTENT only (no admin permissions)
        tenant_viewer_perms = content_read_permissions
        
        # Create admin role
        admin_role = Role(
            customer_id=customer_id,
            name="admin",
            display_name="Admin",
            description="Full administrative access within this organization",
            is_system_role=True
        )
        self.db.add(admin_role)
        self.db.flush()
        
        for perm in tenant_admin_perms:
            self.db.execute(role_permissions.insert().values(
                role_id=admin_role.id,
                permission_id=perm.id
            ))
        
        # Create editor role
        editor_role = Role(
            customer_id=customer_id,
            name="editor",
            display_name="Editor",
            description="Can create and modify content",
            is_system_role=True
        )
        self.db.add(editor_role)
        self.db.flush()
        
        for perm in tenant_editor_perms:
            self.db.execute(role_permissions.insert().values(
                role_id=editor_role.id,
                permission_id=perm.id
            ))
        
        # Create viewer role
        viewer_role = Role(
            customer_id=customer_id,
            name="viewer",
            display_name="Viewer",
            description="Read-only access to view content",
            is_system_role=True
        )
        self.db.add(viewer_role)
        self.db.flush()
        
        for perm in tenant_viewer_perms:
            self.db.execute(role_permissions.insert().values(
                role_id=viewer_role.id,
                permission_id=perm.id
            ))
        
        self.db.commit()
        return admin_role, editor_role, viewer_role
    
    def get_tenant_admin_info(self, customer_id: str) -> dict:
        """
        Get the admin info for a tenant.
        
        Returns dict with admin_name, admin_email, admin_status.
        Checks for active admin users first, then pending invites.
        """
        # First check for active users with Admin role (case-insensitive)
        admin_role = self.db.query(Role).filter(
            and_(
                Role.customer_id == customer_id,
                func.lower(Role.name) == "admin",
                Role.is_active == True
            )
        ).first()
        
        if admin_role:
            # Find users with this admin role using the unified user_roles table
            admin_user_assignment = self.db.execute(
                user_roles.select().where(user_roles.c.role_id == admin_role.id)
            ).first()
            
            if admin_user_assignment:
                admin_user = self.db.query(User).filter(
                    User.id == admin_user_assignment.user_id
                ).first()
                if admin_user:
                    return {
                        "admin_name": admin_user.full_name,
                        "admin_email": admin_user.email,
                        "admin_status": "active"
                    }
        
        # Check for pending admin invites
        admin_invite = self.db.query(UserInvite).filter(
            and_(
                UserInvite.customer_id == customer_id,
                UserInvite.status == "pending"
            )
        ).order_by(UserInvite.created_at.desc()).first()
        
        if admin_invite:
            return {
                "admin_name": admin_invite.full_name,
                "admin_email": admin_invite.email,
                "admin_status": "pending_invite"
            }
        
        return {
            "admin_name": None,
            "admin_email": None,
            "admin_status": "no_admin"
        }
    
    # =========================================================================
    # USER ROLE MANAGEMENT (Using unified user_roles table)
    # =========================================================================
    
    def get_user_roles(self, user_id: int, customer_id: str = None) -> List[Role]:
        """Get all roles assigned to a user, optionally filtered by tenant.
        
        Args:
            user_id: The user's ID
            customer_id: If provided, only return roles belonging to this tenant
        """
        # Query using the unified user_roles association table
        role_ids = self.db.execute(
            user_roles.select().where(user_roles.c.user_id == user_id)
        ).fetchall()
        
        if not role_ids:
            return []
        
        query = self.db.query(Role).filter(
            Role.id.in_([r.role_id for r in role_ids])
        )
        
        # Filter by tenant if customer_id is provided
        if customer_id:
            query = query.filter(Role.customer_id == customer_id)
        
        return query.all()
    
    def get_user_permissions(self, user_id: int) -> Set[str]:
        """Get all permissions for a user (union of all role permissions)."""
        roles = self.get_user_roles(user_id)
        permissions = set()
        for role in roles:
            permissions.update(role.get_permissions())
        return permissions
    
    def assign_role_to_user(self, user_id: int, role_id: int, assigned_by: int) -> bool:
        """Assign a role to a user."""
        from datetime import datetime
        existing = self.db.execute(
            user_roles.select().where(
                and_(
                    user_roles.c.user_id == user_id,
                    user_roles.c.role_id == role_id
                )
            )
        ).first()
        
        if existing:
            return False  # Already assigned
        
        self.db.execute(
            user_roles.insert().values(
                user_id=user_id,
                role_id=role_id,
                assigned_by=assigned_by,
                assigned_at=datetime.utcnow(),
                active=True
            )
        )
        self.db.commit()
        return True
    
    def remove_role_from_user(self, user_id: int, role_id: int) -> bool:
        """Remove a role from a user."""
        result = self.db.execute(
            user_roles.delete().where(
                and_(
                    user_roles.c.user_id == user_id,
                    user_roles.c.role_id == role_id
                )
            )
        )
        self.db.commit()
        return result.rowcount > 0
    
    def set_user_roles(self, user_id: int, role_ids: List[int], assigned_by: int) -> List[Role]:
        """Set all roles for a user (replaces existing)."""
        from datetime import datetime
        # Remove existing roles
        self.db.execute(
            user_roles.delete().where(user_roles.c.user_id == user_id)
        )
        
        # Add new roles
        for role_id in role_ids:
            self.db.execute(
                user_roles.insert().values(
                    user_id=user_id,
                    role_id=role_id,
                    assigned_by=assigned_by,
                    assigned_at=datetime.utcnow(),
                    active=True
                )
            )
        
        self.db.commit()
        return self.get_user_roles(user_id)
    
    # =========================================================================
    # USER INVITES
    # =========================================================================
    
    def create_invite(
        self,
        customer_id: str,
        invite_data: UserInviteCreate,
        created_by: int
    ) -> UserInvite:
        """Create a user invite."""
        invite = UserInvite.create_invite(
            customer_id=customer_id,
            email=invite_data.email,
            full_name=invite_data.full_name,
            role_ids=invite_data.role_ids,
            created_by=created_by,
            expires_in_days=invite_data.expires_in_days
        )
        self.db.add(invite)
        self.db.commit()
        self.db.refresh(invite)
        return invite
    
    def get_invite_by_token(self, token: str) -> Optional[UserInvite]:
        """Get an invite by its token."""
        return self.db.query(UserInvite).filter(
            UserInvite.invite_token == token
        ).first()
    
    def get_pending_invites(self, customer_id: str) -> List[UserInvite]:
        """Get all pending invites for a tenant."""
        return self.db.query(UserInvite).filter(
            and_(
                UserInvite.customer_id == customer_id,
                UserInvite.status == "pending"
            )
        ).order_by(UserInvite.created_at.desc()).all()
    
    def accept_invite(self, invite: UserInvite, user: User) -> None:
        """Accept an invite and link to user."""
        invite.accept(user.id)
        
        # Assign pre-defined roles
        if invite.role_ids:
            for role_id in invite.role_ids:
                self.assign_role_to_user(user.id, role_id, invite.created_by)
        
        self.db.commit()
    
    def revoke_invite(self, invite_id: int, revoked_by: int) -> bool:
        """Revoke a pending invite."""
        invite = self.db.query(UserInvite).filter(
            UserInvite.id == invite_id
        ).first()
        
        if not invite or invite.status != "pending":
            return False
        
        invite.revoke(revoked_by)
        self.db.commit()
        return True
    
    def resend_invite(self, invite_id: int) -> Optional[UserInvite]:
        """Resend an invite by generating a new token and extending expiration."""
        invite = self.db.query(UserInvite).filter(
            UserInvite.id == invite_id
        ).first()
        
        if not invite or invite.status != "pending":
            return None
        
        invite.invite_token = UserInvite.generate_token()
        invite.expires_at = datetime.utcnow() + timedelta(days=7)
        self.db.commit()
        self.db.refresh(invite)
        return invite
    
    # =========================================================================
    # TENANT USERS
    # =========================================================================
    
    def get_tenant_users(self, customer_id: str) -> List[User]:
        """Get all users for a tenant."""
        return self.db.query(User).filter(
            User.customer_id == customer_id
        ).order_by(User.created_at.desc()).all()
    
    def get_user_with_roles(self, user_id: int) -> Optional[User]:
        """Get a user with their roles loaded."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            # Load tenant roles
            user._tenant_roles = self.get_user_roles(user_id)
        return user


class PlatformAdminService:
    """
    Service for platform-level administration (Eliza team only).
    
    Handles:
    - Tenant creation and management
    - Platform admin management
    - Global feature management
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.tenant_service = TenantAdminService(db)
    
    # =========================================================================
    # PLATFORM ADMIN MANAGEMENT
    # =========================================================================
    
    def is_platform_admin(self, user_id: int) -> bool:
        """Check if a user is a platform admin."""
        admin = self.db.query(PlatformAdmin).filter(
            and_(
                PlatformAdmin.user_id == user_id,
                PlatformAdmin.is_active == True
            )
        ).first()
        return admin is not None
    
    def get_platform_admin(self, user_id: int) -> Optional[PlatformAdmin]:
        """Get platform admin by user ID."""
        return self.db.query(PlatformAdmin).filter(
            PlatformAdmin.user_id == user_id
        ).first()
    
    def get_all_platform_admins(self) -> List[PlatformAdmin]:
        """Get all platform admins."""
        return self.db.query(PlatformAdmin).options(
            joinedload(PlatformAdmin.user)
        ).filter(PlatformAdmin.is_active == True).all()
    
    def create_platform_admin(
        self,
        user_id: int,
        admin_level: str = "admin",
        created_by: Optional[int] = None,
        can_create_tenants: bool = True,
        can_allocate_features: bool = True,
        can_manage_platform_admins: bool = False,
        can_impersonate: bool = False
    ) -> PlatformAdmin:
        """Create a new platform admin."""
        admin = PlatformAdmin(
            user_id=user_id,
            admin_level=admin_level,
            created_by=created_by,
            can_create_tenants=can_create_tenants,
            can_allocate_features=can_allocate_features,
            can_manage_platform_admins=can_manage_platform_admins,
            can_impersonate=can_impersonate
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)
        return admin
    
    def remove_platform_admin(self, user_id: int) -> bool:
        """Remove a platform admin (soft delete)."""
        admin = self.get_platform_admin(user_id)
        if not admin:
            return False
        
        admin.is_active = False
        self.db.commit()
        return True
    
    # =========================================================================
    # TENANT MANAGEMENT
    # =========================================================================
    
    def get_all_tenants(self, include_inactive: bool = False) -> List[Customer]:
        """Get all tenants."""
        query = self.db.query(Customer)
        if not include_inactive:
            query = query.filter(Customer.is_active == True)
        return query.order_by(Customer.created_at.desc()).all()
    
    def get_tenant(self, customer_id: str) -> Optional[Customer]:
        """Get a tenant by customer_id."""
        return self.db.query(Customer).filter(
            Customer.customer_id == customer_id
        ).first()
    
    def create_tenant(
        self,
        tenant_data: TenantCreate,
        created_by: int
    ) -> Tuple[Customer, UserInvite]:
        """
        Create a new tenant with admin user invite.
        
        Returns: (Customer, UserInvite for admin)
        """
        # Create customer
        customer = Customer(
            customer_id=tenant_data.customer_id,
            name=tenant_data.name,
            display_name=tenant_data.display_name,
            contact_email=tenant_data.contact_email,
            subscription_tier=tenant_data.subscription_tier,
            is_active=True
        )
        self.db.add(customer)
        self.db.flush()
        
        # Allocate features
        allocated_feature_ids = set()
        if tenant_data.feature_ids:
            for feature_id in tenant_data.feature_ids:
                allocation = TenantFeatureAllocation(
                    customer_id=tenant_data.customer_id,
                    feature_id=feature_id,
                    is_enabled=True,
                    allocated_by=created_by
                )
                self.db.add(allocation)
                allocated_feature_ids.add(feature_id)
        
        self.db.flush()
        
        # Create default roles (tenant_admin, tenant_editor, tenant_viewer)
        admin_role, editor_role, viewer_role = self.tenant_service.create_default_roles_for_tenant(
            tenant_data.customer_id,
            allocated_feature_ids
        )
        
        # Create admin invite
        admin_invite = UserInvite.create_invite(
            customer_id=tenant_data.customer_id,
            email=tenant_data.admin_email,
            full_name=tenant_data.admin_name,
            role_ids=[admin_role.id],
            created_by=created_by,
            expires_in_days=14  # Admin gets 2 weeks
        )
        self.db.add(admin_invite)
        
        self.db.commit()
        self.db.refresh(customer)
        self.db.refresh(admin_invite)
        
        return customer, admin_invite
    
    def update_tenant(self, customer_id: str, **kwargs) -> Optional[Customer]:
        """Update tenant details."""
        customer = self.get_tenant(customer_id)
        if not customer:
            return None
        
        for key, value in kwargs.items():
            if hasattr(customer, key) and value is not None:
                setattr(customer, key, value)
        
        self.db.commit()
        self.db.refresh(customer)
        return customer
    
    def deactivate_tenant(self, customer_id: str) -> bool:
        """Deactivate a tenant."""
        customer = self.get_tenant(customer_id)
        if not customer:
            return False
        
        customer.is_active = False
        self.db.commit()
        return True
    
    def update_tenant_admin(
        self,
        customer_id: str,
        admin_email: str,
        admin_name: Optional[str],
        created_by: int
    ) -> UserInvite:
        """
        Update the tenant admin by creating a new invite.
        
        1. Revokes any existing pending invites for this tenant
        2. Creates a new admin invite
        """
        # Get the admin role for this tenant
        admin_role = self.db.query(Role).filter(
            and_(
                Role.customer_id == customer_id,
                Role.name == "Admin",
                Role.is_active == True
            )
        ).first()
        
        if not admin_role:
            # Create admin role if it doesn't exist
            admin_role = Role(
                customer_id=customer_id,
                name="Admin",
                display_name="Administrator",
                description="Full access to all features",
                is_system_role=True
            )
            self.db.add(admin_role)
            self.db.flush()
        
        # Revoke any existing pending invites for this tenant (admin role)
        existing_invites = self.db.query(UserInvite).filter(
            and_(
                UserInvite.customer_id == customer_id,
                UserInvite.status == "pending"
            )
        ).all()
        
        for invite in existing_invites:
            invite.status = "revoked"
            invite.revoked_by = created_by
            invite.revoked_at = datetime.utcnow()
        
        # Create new admin invite
        new_invite = UserInvite.create_invite(
            customer_id=customer_id,
            email=admin_email,
            full_name=admin_name,
            role_ids=[admin_role.id],
            created_by=created_by,
            expires_in_days=14
        )
        self.db.add(new_invite)
        
        self.db.commit()
        self.db.refresh(new_invite)
        
        return new_invite
    
    def resend_admin_invite(
        self,
        customer_id: str,
        created_by: int
    ) -> Optional[UserInvite]:
        """
        Resend the admin invite by creating a new token.
        
        Finds the most recent pending invite and creates a new one with the same details.
        """
        # Find the most recent pending invite
        existing_invite = self.db.query(UserInvite).filter(
            and_(
                UserInvite.customer_id == customer_id,
                UserInvite.status == "pending"
            )
        ).order_by(UserInvite.created_at.desc()).first()
        
        if not existing_invite:
            return None
        
        # Revoke the old invite
        existing_invite.status = "revoked"
        existing_invite.revoked_by = created_by
        existing_invite.revoked_at = datetime.utcnow()
        
        # Create a new invite with the same details
        new_invite = UserInvite.create_invite(
            customer_id=customer_id,
            email=existing_invite.email,
            full_name=existing_invite.full_name,
            role_ids=existing_invite.role_ids or [],
            created_by=created_by,
            expires_in_days=14
        )
        self.db.add(new_invite)
        
        self.db.commit()
        self.db.refresh(new_invite)
        
        return new_invite

