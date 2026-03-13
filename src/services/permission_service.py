"""
AI Enablement Platform - Permission Management Service

Service for managing permissions, roles, and access control policies.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.models.auth import User, Role, Permission, user_roles, role_permissions
from src.services.base_service import BaseService
from src.services.audit_service import audit_service, AuditAction, AuditSeverity

logger = logging.getLogger(__name__)


class PermissionService(BaseService):
    """Service for managing permissions and access control."""
    
    def __init__(self):
        self.permission_cache = {}
        self.role_hierarchy = {
            "super_admin": 5,
            "admin": 4,
            "manager": 3,
            "analyst": 2,
            "viewer": 1
        }
    
    async def create_permission(
        self,
        name: str,
        resource: str,
        action: str,
        description: Optional[str] = None,
        scope: str = "all",
        conditions: Optional[Dict[str, Any]] = None,
        created_by_id: Optional[int] = None
    ) -> Permission:
        """Create a new permission."""
        with self.get_db_session() as db:
            # Check if permission already exists
            existing = db.query(Permission).filter(Permission.name == name).first()
            if existing:
                raise ValueError(f"Permission '{name}' already exists")
            
            permission = Permission(
                name=name,
                resource=resource,
                action=action,
                description=description,
                scope=scope,
                conditions=conditions,
                created_by=created_by_id
            )
            
            db.add(permission)
            db.commit()
            db.refresh(permission)
            
            # Log permission creation
            await audit_service.log_event(
                AuditAction.PERMISSION_GRANTED,
                user_id=created_by_id,
                resource_type="permission",
                resource_id=str(permission.id),
                new_values={
                    "name": name,
                    "resource": resource,
                    "action": action,
                    "scope": scope
                }
            )
            
            return permission
    
    async def assign_permission_to_role(
        self,
        role_id: int,
        permission_id: int,
        granted_by_id: Optional[int] = None
    ) -> bool:
        """Assign a permission to a role."""
        with self.get_db_session() as db:
            # Check if assignment already exists
            existing = db.query(role_permissions).filter(
                and_(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id
                )
            ).first()
            
            if existing:
                return False  # Already assigned
            
            # Get role and permission for logging
            role = db.query(Role).filter(Role.id == role_id).first()
            permission = db.query(Permission).filter(Permission.id == permission_id).first()
            
            if not role or not permission:
                raise ValueError("Role or permission not found")
            
            # Create assignment
            db.execute(
                role_permissions.insert().values(
                    role_id=role_id,
                    permission_id=permission_id,
                    granted_by=granted_by_id
                )
            )
            db.commit()
            
            # Log permission assignment
            await audit_service.log_event(
                AuditAction.PERMISSION_GRANTED,
                user_id=granted_by_id,
                resource_type="role",
                resource_id=str(role_id),
                new_values={
                    "role_name": role.name,
                    "permission_name": permission.name,
                    "permission_id": permission_id
                }
            )
            
            return True
    
    async def revoke_permission_from_role(
        self,
        role_id: int,
        permission_id: int,
        revoked_by_id: Optional[int] = None
    ) -> bool:
        """Revoke a permission from a role."""
        with self.get_db_session() as db:
            # Get role and permission for logging
            role = db.query(Role).filter(Role.id == role_id).first()
            permission = db.query(Permission).filter(Permission.id == permission_id).first()
            
            if not role or not permission:
                raise ValueError("Role or permission not found")
            
            # Remove assignment
            result = db.execute(
                role_permissions.delete().where(
                    and_(
                        role_permissions.c.role_id == role_id,
                        role_permissions.c.permission_id == permission_id
                    )
                )
            )
            db.commit()
            
            if result.rowcount > 0:
                # Log permission revocation
                await audit_service.log_event(
                    AuditAction.PERMISSION_REVOKED,
                    user_id=revoked_by_id,
                    resource_type="role",
                    resource_id=str(role_id),
                    old_values={
                        "role_name": role.name,
                        "permission_name": permission.name,
                        "permission_id": permission_id
                    }
                )
                return True
            
            return False
    
    async def assign_role_to_user(
        self,
        user_id: int,
        role_id: int,
        assigned_by_id: Optional[int] = None
    ) -> bool:
        """Assign a role to a user."""
        with self.get_db_session() as db:
            # Check if assignment already exists
            existing = db.query(user_roles).filter(
                and_(
                    user_roles.c.user_id == user_id,
                    user_roles.c.role_id == role_id
                )
            ).first()
            
            if existing:
                return False  # Already assigned
            
            # Get user and role for logging
            user = db.query(User).filter(User.id == user_id).first()
            role = db.query(Role).filter(Role.id == role_id).first()
            
            if not user or not role:
                raise ValueError("User or role not found")
            
            # Create assignment
            db.execute(
                user_roles.insert().values(
                    user_id=user_id,
                    role_id=role_id,
                    assigned_by=assigned_by_id
                )
            )
            db.commit()
            
            # Log role assignment
            await audit_service.log_event(
                AuditAction.ROLE_ASSIGNED,
                user_id=assigned_by_id,
                resource_type="user",
                resource_id=str(user_id),
                new_values={
                    "target_user_email": user.email,
                    "role_name": role.name,
                    "role_id": role_id
                }
            )
            
            return True
    
    async def revoke_role_from_user(
        self,
        user_id: int,
        role_id: int,
        revoked_by_id: Optional[int] = None
    ) -> bool:
        """Revoke a role from a user."""
        with self.get_db_session() as db:
            # Get user and role for logging
            user = db.query(User).filter(User.id == user_id).first()
            role = db.query(Role).filter(Role.id == role_id).first()
            
            if not user or not role:
                raise ValueError("User or role not found")
            
            # Remove assignment
            result = db.execute(
                user_roles.delete().where(
                    and_(
                        user_roles.c.user_id == user_id,
                        user_roles.c.role_id == role_id
                    )
                )
            )
            db.commit()
            
            if result.rowcount > 0:
                # Log role revocation
                await audit_service.log_event(
                    AuditAction.ROLE_REMOVED,
                    user_id=revoked_by_id,
                    resource_type="user",
                    resource_id=str(user_id),
                    old_values={
                        "target_user_email": user.email,
                        "role_name": role.name,
                        "role_id": role_id
                    }
                )
                return True
            
            return False
    
    async def get_user_effective_permissions(self, user_id: int) -> List[str]:
        """Get all effective permissions for a user (including inherited)."""
        with self.get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return []
            
            return user.get_permissions()
    
    async def check_user_permission(
        self,
        user_id: int,
        permission: str,
        resource_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if user has specific permission with optional resource context."""
        with self.get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            # Basic permission check
            if not user.has_permission(permission):
                return False
            
            # If no resource context, basic permission is sufficient
            if not resource_context:
                return True
            
            # Resource-specific permission checking would go here
            # This would integrate with the resource scoping logic
            return True
    
    async def get_role_hierarchy_level(self, role_name: str) -> int:
        """Get the hierarchy level of a role."""
        return self.role_hierarchy.get(role_name.lower(), 0)
    
    async def can_user_manage_role(
        self,
        manager_user_id: int,
        target_role_name: str
    ) -> bool:
        """Check if a user can manage (assign/revoke) a specific role."""
        with self.get_db_session() as db:
            manager = db.query(User).filter(User.id == manager_user_id).first()
            if not manager:
                return False
            
            # Superusers can manage any role
            if manager.is_superuser:
                return True
            
            # Get manager's highest role level
            manager_level = 0
            for role in manager.roles:
                role_level = await self.get_role_hierarchy_level(role.name)
                manager_level = max(manager_level, role_level)
            
            # Get target role level
            target_level = await self.get_role_hierarchy_level(target_role_name)
            
            # Can only manage roles at lower levels
            return manager_level > target_level
    
    async def list_permissions(
        self,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        scope: Optional[str] = None
    ) -> List[Permission]:
        """List permissions with optional filtering."""
        with self.get_db_session() as db:
            query = db.query(Permission)
            
            if resource:
                query = query.filter(Permission.resource == resource)
            if action:
                query = query.filter(Permission.action == action)
            if scope:
                query = query.filter(Permission.scope == scope)
            
            return query.order_by(Permission.resource, Permission.action).all()
    
    async def list_roles(self) -> List[Role]:
        """List all roles."""
        with self.get_db_session() as db:
            return db.query(Role).order_by(Role.name).all()


# Global permission service instance
permission_service = PermissionService()
