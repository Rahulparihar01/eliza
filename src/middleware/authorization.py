"""
AI Enablement Platform - Authorization Middleware

Comprehensive authorization middleware for API endpoint protection with RBAC,
resource scoping, and context-aware permission checking.
"""

import logging
from typing import Optional, Dict, Any, List, Callable, Union
from functools import wraps
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from enum import Enum

from src.models.auth import User
from src.services.auth_service import auth_service, AuthenticationError, AuthorizationError
from src.services.audit_service import audit_service, AuditAction, AuditSeverity
from src.core.auth_context import (
    CurrentUserContext,
    CurrentUserSessionInfo,
    CurrentUserSettings,
)

logger = logging.getLogger(__name__)
security = HTTPBearer()


class ResourceScope(Enum):
    """Resource access scopes for permission checking."""
    OWN = "own"
    TEAM = "team"
    DEPARTMENT = "department"
    ALL = "all"


class AuthorizationContext(BaseModel):
    """Context information for authorization decisions."""
    user: CurrentUserContext
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_owner_id: Optional[int] = None
    resource_department: Optional[str] = None
    resource_team: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_token: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True


class AuthorizationMiddleware:
    """Comprehensive authorization middleware for API endpoints."""
    
    def __init__(self):
        self.protected_endpoints = {}
        self.resource_resolvers = {}
    
    async def get_current_user(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> CurrentUserContext:
        """Enhanced user authentication with session validation or API key, returning DTO."""
        try:
            token = credentials.credentials

            # Try API key authentication first (if token starts with "uak_")
            if token.startswith("uak_"):
                from src.services.api_key_service import api_key_service

                user = await api_key_service.authenticate_with_api_key(
                    api_key=token,
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent")
                )

                if not user:
                    await audit_service.log_event(
                        AuditAction.PERMISSION_DENIED,
                        ip_address=request.client.host,
                        user_agent=request.headers.get("user-agent"),
                        severity=AuditSeverity.HIGH,
                        additional_context={
                            "reason": "invalid_api_key",
                            "endpoint": str(request.url)
                        }
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired API key",
                        headers={"WWW-Authenticate": "Bearer"}
                    )

                # Build context from API key authentication
                context = self._build_current_user_context(user, current_session_token=None)
                
                # Check if tenant is active
                await self._check_tenant_active(context, request)
                
                # Store tenant context in request.state for middleware/audit access
                request.state.customer_id = context.customer_id
                request.state.user_id = context.user_id
                request.state.is_platform_admin = context.has_permission('platform:admin')
                request.state.user_context = context
                
                return context

            # Otherwise, try JWT authentication
            payload = await auth_service.verify_token(token)
            user_id = int(payload.get("sub"))

            # Fetch ORM user with relationships while session is open
            user = await auth_service.get_user_by_id(user_id)
            if not user:
                await audit_service.log_event(
                    AuditAction.PERMISSION_DENIED,
                    user_id=user_id,
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent"),
                    severity=AuditSeverity.MEDIUM,
                    additional_context={
                        "reason": "user_not_found",
                        "endpoint": str(request.url)
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )

            context = self._build_current_user_context(user, payload.get("session_token"))
            
            # Check if tenant is active (unless user is platform admin accessing platform routes)
            await self._check_tenant_active(context, request)
            
            # Store tenant context in request.state for middleware/audit access
            request.state.customer_id = context.customer_id
            request.state.user_id = context.user_id
            request.state.is_platform_admin = context.has_permission('platform:admin')
            request.state.user_context = context
            
            return context

        except AuthenticationError as e:
            await audit_service.log_event(
                AuditAction.PERMISSION_DENIED,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                severity=AuditSeverity.MEDIUM,
                additional_context={
                    "reason": "authentication_failed",
                    "error": str(e),
                    "endpoint": str(request.url)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    def require_permission(
        self,
        permission: str,
        resource_type: Optional[str] = None,
        scope: Optional[ResourceScope] = None,
        allow_superuser: bool = True
    ):
        """
        Enhanced permission dependency with resource scoping.
        
        Args:
            permission: Required permission (e.g., 'documents:read')
            resource_type: Type of resource being accessed
            scope: Required access scope
            allow_superuser: Whether superusers bypass permission checks
        """
        async def permission_checker(
            request: Request,
            current_user: CurrentUserContext = Depends(self.get_current_user)
        ):
            # Superuser bypass
            if allow_superuser and current_user.is_superuser:
                return current_user
            
            # Build authorization context
            context = AuthorizationContext(
                user=current_user,
                resource_type=resource_type,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                additional_context={
                    "endpoint": str(request.url),
                    "method": request.method
                }
            )
            
            # Check permission with context
            has_permission = await self._check_permission_with_context(
                current_user, permission, context, scope
            )
            
            if not has_permission:
                await audit_service.log_event(
                    AuditAction.PERMISSION_DENIED,
                    user_id=current_user.user_id,
                    resource_type=resource_type,
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent"),
                    severity=AuditSeverity.HIGH,
                    additional_context={
                        "required_permission": permission,
                        "required_scope": scope.value if scope else None,
                        "endpoint": str(request.url),
                        "method": request.method
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission required: {permission}"
                )
            
            return current_user
        
        return permission_checker
    
    def require_any_permission(
        self,
        permissions: List[str],
        resource_type: Optional[str] = None,
        scope: Optional[ResourceScope] = None,
        allow_superuser: bool = True
    ):
        """Require any of multiple permissions."""
        async def permission_checker(
            request: Request,
            current_user: CurrentUserContext = Depends(self.get_current_user)
        ):
            # Superuser bypass
            if allow_superuser and current_user.is_superuser:
                return current_user
            
            # Build authorization context
            context = AuthorizationContext(
                user=current_user,
                resource_type=resource_type,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                additional_context={
                    "endpoint": str(request.url),
                    "method": request.method
                }
            )
            
            # Check if user has any of the required permissions
            has_any_permission = False
            for permission in permissions:
                if await self._check_permission_with_context(
                    current_user, permission, context, scope
                ):
                    has_any_permission = True
                    break
            
            if not has_any_permission:
                await audit_service.log_event(
                    AuditAction.PERMISSION_DENIED,
                    user_id=current_user.user_id,
                    resource_type=resource_type,
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent"),
                    severity=AuditSeverity.HIGH,
                    additional_context={
                        "required_permissions": permissions,
                        "required_scope": scope.value if scope else None,
                        "endpoint": str(request.url),
                        "method": request.method
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"One of these permissions required: {', '.join(permissions)}"
                )
            
            return current_user
        
        return permission_checker
    
    def require_resource_access(
        self,
        permission: str,
        resource_type: str,
        resource_id_param: str = "id",
        scope: Optional[ResourceScope] = None
    ):
        """
        Require permission with resource-specific access control.
        
        Args:
            permission: Required permission
            resource_type: Type of resource
            resource_id_param: Path parameter name for resource ID
            scope: Required access scope
        """
        async def resource_permission_checker(
            request: Request,
            current_user: CurrentUserContext = Depends(self.get_current_user)
        ):
            # Get resource ID from path parameters
            resource_id = request.path_params.get(resource_id_param)
            if not resource_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Resource ID parameter '{resource_id_param}' not found"
                )
            
            # Resolve resource information
            resource_info = await self._resolve_resource_info(
                resource_type, resource_id
            )
            
            # Build authorization context with resource information
            context = AuthorizationContext(
                user=current_user,
                resource_type=resource_type,
                resource_id=str(resource_id),
                resource_owner_id=resource_info.get("owner_id"),
                resource_department=resource_info.get("department"),
                resource_team=resource_info.get("team"),
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                additional_context={
                    "endpoint": str(request.url),
                    "method": request.method,
                    "resource_info": resource_info
                }
            )
            
            # Check permission with resource context
            has_permission = await self._check_permission_with_context(
                current_user, permission, context, scope
            )
            
            if not has_permission:
                await audit_service.log_event(
                    AuditAction.PERMISSION_DENIED,
                    user_id=current_user.user_id,
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent"),
                    severity=AuditSeverity.HIGH,
                    additional_context={
                        "required_permission": permission,
                        "required_scope": scope.value if scope else None,
                        "endpoint": str(request.url),
                        "method": request.method
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied to {resource_type} {resource_id}"
                )
            
            return current_user
        
        return resource_permission_checker
    
    def check_company_access(
        self,
        user: CurrentUserContext,
        company_id: str,
        allow_superuser: bool = True
    ) -> bool:
        """
        Check if user has permission to access a specific company's HR data.
        
        Args:
            user: Current user context
            company_id: Target company ID to check access for
            allow_superuser: Whether superusers bypass permission checks
            
        Returns:
            bool: True if user has access to the company's data
            
        Permission format:
            - hr:read:company:* - Access to ALL companies (wildcard)
            - hr:read:company:{company_id} - Access to specific company
        """
        # Superuser bypass
        if allow_superuser and user.is_superuser:
            return True
        
        # Check for wildcard permission (access to all companies)
        wildcard_permission = "hr:read:company:*"
        if user.has_permission(wildcard_permission):
            return True
        
        # Check for specific company permission
        company_permission = f"hr:read:company:{company_id}"
        if user.has_permission(company_permission):
            return True
        
        # No access
        return False
    
    def check_adoption_access(
        self,
        user: CurrentUserContext,
        company_id: str,
        action: str = "read",
        allow_superuser: bool = True
    ) -> bool:
        """
        Check if user has permission to access a specific company's adoption data.
        
        Args:
            user: Current user context
            company_id: Target company ID to check access for
            action: Action type ('read' or 'admin')
            allow_superuser: Whether superusers bypass permission checks
            
        Returns:
            bool: True if user has access to the company's adoption data
            
        Permission format:
            - adoption:{action}:company:* - Access to ALL companies (wildcard)
            - adoption:{action}:company:{company_id} - Access to specific company
            
        Also checks AdoptionDataShare records for tenant self-service sharing.
        """
        # Superuser bypass
        if allow_superuser and user.is_superuser:
            return True
        
        # User's own tenant is always accessible
        if company_id == user.customer_id:
            return True
        
        # Check for wildcard permission (access to all companies)
        wildcard_permission = f"adoption:{action}:company:*"
        if user.has_permission(wildcard_permission):
            return True
        
        # Check for specific company permission
        company_permission = f"adoption:{action}:company:{company_id}"
        if user.has_permission(company_permission):
            return True
        
        # Check AdoptionDataShare records (tenant self-service sharing)
        from src.models import database
        from src.models.adoption import AdoptionDataShare
        from sqlalchemy import or_
        from sqlalchemy.sql import func
        
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        try:
            query = db.query(AdoptionDataShare).filter(
                AdoptionDataShare.source_customer_id == company_id,
                AdoptionDataShare.target_customer_id == user.customer_id,
                AdoptionDataShare.is_enabled == True,
                or_(
                    AdoptionDataShare.expires_at.is_(None),
                    AdoptionDataShare.expires_at > func.now()
                )
            )
            
            # If action is admin, also check share_level
            if action == "admin":
                query = query.filter(AdoptionDataShare.share_level == "admin")
            
            share = query.first()
            if share:
                return True
        finally:
            db.close()
        
        # No access
        return False
    
    def get_accessible_adoption_companies(
        self,
        user: CurrentUserContext,
        action: str = "read",
        db=None
    ) -> List[str]:
        """
        Get all company IDs the user can access for adoption metrics.
        
        Args:
            user: Current user context
            action: Action type ('read' or 'admin')
            db: Optional database session (creates one if not provided)
            
        Returns:
            List of customer_id strings the user can access
            
        Checks:
        1. User's own tenant (always included)
        2. Explicit permission grants (from platform admin)
        3. AdoptionDataShare records (from tenant self-service)
        """
        accessible = set()
        
        # Always include own tenant
        accessible.add(user.customer_id)
        
        # Import database module (use module import for globals per Rule 4b)
        from src.models import database
        from src.models.customer import Customer
        from src.models.adoption import AdoptionDataShare
        from sqlalchemy import or_
        from sqlalchemy.sql import func
        
        def get_db_session():
            """Get or create database session."""
            if database.SessionLocal is None:
                database.init_database()
            return database.SessionLocal()
        
        # Superuser gets access to all
        if user.is_superuser:
            close_db = False
            if db is None:
                db = get_db_session()
                close_db = True
            try:
                all_companies = db.query(Customer.customer_id).filter(
                    Customer.is_active == True
                ).all()
                return [c[0] for c in all_companies]
            finally:
                if close_db:
                    db.close()
        
        # PATH 1: Check permission grants (platform admin created)
        for perm in user.permissions:
            if perm.startswith(f"adoption:{action}:company:"):
                company_id = perm.split(":")[-1]
                if company_id == "*":
                    # Wildcard - return all companies
                    close_db = False
                    if db is None:
                        db = get_db_session()
                        close_db = True
                    try:
                        all_companies = db.query(Customer.customer_id).filter(
                            Customer.is_active == True
                        ).all()
                        return [c[0] for c in all_companies]
                    finally:
                        if close_db:
                            db.close()
                accessible.add(company_id)
        
        # PATH 2: Check adoption shares (tenant self-service)
        close_db = False
        if db is None:
            db = get_db_session()
            close_db = True
        
        try:
            query = db.query(AdoptionDataShare).filter(
                AdoptionDataShare.target_customer_id == user.customer_id,
                AdoptionDataShare.is_enabled == True,
                or_(
                    AdoptionDataShare.expires_at.is_(None),
                    AdoptionDataShare.expires_at > func.now()
                )
            )
            
            if action == "admin":
                query = query.filter(AdoptionDataShare.share_level == "admin")
            
            for share in query.all():
                accessible.add(share.source_customer_id)
        finally:
            if close_db:
                db.close()
        
        return list(accessible)
    
    def require_company_access(self, company_id_param: str = "company_hr_dataset"):
        """
        Dependency that requires company-specific HR data access.
        
        Args:
            company_id_param: Query/path parameter name for company ID
            
        Raises:
            HTTPException: If user doesn't have access to the company
        """
        async def company_access_checker(
            request: Request,
            current_user: CurrentUserContext = Depends(self.get_current_user)
        ):
            # Get company_id from query params or path params
            company_id = request.query_params.get(company_id_param) or request.path_params.get(company_id_param)
            
            if not company_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Company ID parameter '{company_id_param}' is required"
                )
            
            # Check if user has access to this company's data
            has_access = self.check_company_access(current_user, company_id)
            
            if not has_access:
                await audit_service.log_event(
                    AuditAction.PERMISSION_DENIED,
                    user_id=current_user.user_id,
                    resource_type="company_hr_data",
                    resource_id=company_id,
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent"),
                    severity=AuditSeverity.HIGH,
                    additional_context={
                        "required_permission": f"hr:read:company:{company_id}",
                        "endpoint": str(request.url),
                        "method": request.method,
                        "user_customer_id": current_user.customer_id,
                        "target_company_id": company_id
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied to company '{company_id}' HR data"
                )
            
            return current_user
        
        return company_access_checker
    
    def require_adoption_access(
        self,
        company_id_param: str = "customer_id",
        action: str = "read"
    ):
        """
        Dependency that requires company-specific adoption data access.
        
        Args:
            company_id_param: Query/path parameter name for company ID
            action: Action type ('read' or 'admin')
            
        Raises:
            HTTPException: If user doesn't have access to the company's adoption data
        """
        async def adoption_access_checker(
            request: Request,
            current_user: CurrentUserContext = Depends(self.get_current_user)
        ):
            # Get company_id from query params or path params
            company_id = request.query_params.get(company_id_param) or request.path_params.get(company_id_param)
            
            if not company_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Company ID parameter '{company_id_param}' is required"
                )
            
            # Check if user has access to this company's adoption data
            has_access = self.check_adoption_access(current_user, company_id, action)
            
            if not has_access:
                await audit_service.log_event(
                    AuditAction.PERMISSION_DENIED,
                    user_id=current_user.user_id,
                    resource_type="company_adoption_data",
                    resource_id=company_id,
                    ip_address=request.client.host,
                    user_agent=request.headers.get("user-agent"),
                    severity=AuditSeverity.HIGH,
                    additional_context={
                        "required_permission": f"adoption:{action}:company:{company_id}",
                        "endpoint": str(request.url),
                        "method": request.method,
                        "user_customer_id": current_user.customer_id,
                        "target_company_id": company_id
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied to company '{company_id}' adoption data"
                )
            
            return current_user
        
        return adoption_access_checker
    
    async def _check_permission_with_context(
        self,
        user: CurrentUserContext,
        permission: str,
        context: AuthorizationContext,
        scope: Optional[ResourceScope] = None
    ) -> bool:
        """Check permission with full context and resource scoping."""
        # Basic permission check
        if not user.has_permission(permission):
            return False
        
        # If no scope specified, basic permission is sufficient
        if not scope:
            return True
        
        # Resource scoping checks
        if scope == ResourceScope.OWN:
            return (
                context.resource_owner_id is not None and
                user.user_id == context.resource_owner_id
            )
        elif scope == ResourceScope.TEAM:
            return (
                user.team is not None and
                context.resource_team is not None and
                user.team == context.resource_team
            )
        elif scope == ResourceScope.DEPARTMENT:
            return (
                user.department is not None and
                context.resource_department is not None and
                user.department == context.resource_department
            )
        elif scope == ResourceScope.ALL:
            return True
        
        return False
    
    async def _resolve_resource_info(
        self,
        resource_type: str,
        resource_id: str
    ) -> Dict[str, Any]:
        """Resolve resource information for authorization."""
        resolver = self.resource_resolvers.get(resource_type)
        if resolver:
            return await resolver(resource_id)

        # Default resource resolution based on type
        if resource_type == "user":
            return await self._resolve_user_resource(resource_id)
        elif resource_type == "document":
            return await self._resolve_document_resource(resource_id)
        elif resource_type == "audit_log":
            return await self._resolve_audit_log_resource(resource_id)

        return {}

    async def _resolve_user_resource(self, user_id: str) -> Dict[str, Any]:
        """Resolve user resource information."""
        try:
            user = await auth_service.get_user_by_id(int(user_id))
            if user:
                return {
                    "owner_id": user.id,
                    "department": user.department,
                    "team": user.team,
                    "is_active": user.is_active
                }
        except (ValueError, TypeError):
            pass
        return {}

    async def _resolve_document_resource(self, document_id: str) -> Dict[str, Any]:
        """Resolve document resource information."""
        # This would integrate with document service
        # For now, return basic structure
        return {
            "owner_id": None,  # Would be resolved from document service
            "department": None,
            "team": None,
            "customer_id": None  # Would be resolved from document service
        }

    async def _resolve_audit_log_resource(self, log_id: str) -> Dict[str, Any]:
        """Resolve audit log resource information."""
        # Audit logs are typically accessible only by admins
        return {
            "owner_id": None,
            "department": None,
            "team": None,
            "restricted": True
        }
    
    def register_resource_resolver(
        self,
        resource_type: str,
        resolver: Callable[[str], Dict[str, Any]]
    ):
        """Register a resource resolver for a specific resource type."""
        self.resource_resolvers[resource_type] = resolver

    @staticmethod
    def _check_tenant_active_sync(customer_id: str):
        """
        Synchronous tenant status check — runs in threadpool to avoid blocking the event loop.
        
        Returns tenant object if found, None otherwise.
        """
        from src.models.database import SessionLocal
        from src.models.customer import Customer
        
        db = SessionLocal()
        try:
            tenant = db.query(Customer).filter(
                Customer.customer_id == customer_id
            ).first()
            if tenant:
                # Extract data while session is open to avoid lazy-load issues
                return {
                    "is_active": tenant.is_active,
                    "name": tenant.name,
                    "display_name": tenant.display_name,
                    "deactivation_reason": getattr(tenant, 'deactivation_reason', None),
                    "deactivated_at": tenant.deactivated_at if hasattr(tenant, 'deactivated_at') else None,
                }
            return None
        finally:
            db.close()

    async def _check_tenant_active(
        self,
        user_context: CurrentUserContext,
        request: Request
    ) -> None:
        """
        Check if the user's tenant is active.
        
        Platform admins can still access platform admin routes even if their 
        primary tenant is deactivated.
        
        Raises:
            HTTPException: If tenant is deactivated
        """
        # Skip check for platform admin routes
        if "/platform-admin/" in str(request.url.path):
            is_platform_admin = user_context.has_permission('platform:admin')
            if is_platform_admin:
                return
        
        # Skip check if no customer_id (shouldn't happen, but defensive)
        if not user_context.customer_id:
            return
        
        # Offload sync DB query to threadpool to avoid blocking the event loop
        tenant_data = await run_in_threadpool(
            self._check_tenant_active_sync, user_context.customer_id
        )
        
        if tenant_data and not tenant_data["is_active"]:
            # Tenant is deactivated
            await audit_service.log_event(
                AuditAction.PERMISSION_DENIED,
                user_id=user_context.user_id,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                severity=AuditSeverity.HIGH,
                additional_context={
                    "reason": "tenant_deactivated",
                    "customer_id": user_context.customer_id,
                    "tenant_name": tenant_data["name"],
                    "deactivation_reason": tenant_data["deactivation_reason"],
                    "deactivated_at": str(tenant_data["deactivated_at"]) if tenant_data["deactivated_at"] else None,
                    "endpoint": str(request.url)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "tenant_deactivated",
                    "message": "Your organization has been deactivated. Please contact your Eliza representative or platform administrator for assistance.",
                    "tenant_name": tenant_data["display_name"] or tenant_data["name"],
                    "deactivated_at": tenant_data["deactivated_at"].isoformat() if tenant_data["deactivated_at"] else None
                }
            )

    def _build_current_user_context(self, user: User, current_session_token: str | None) -> CurrentUserContext:
        """Convert ORM user to DTO while session is active."""
        # Use cached values if available (for expunged/API key users)
        if hasattr(user, '_cached_role_names'):
            roles = user._cached_role_names
        else:
            roles = [role.name for role in user.roles]
        
        if hasattr(user, '_cached_permissions'):
            permissions = user._cached_permissions
        else:
            permissions = user.get_permissions()
        
        if hasattr(user, '_cached_primary_role_name'):
            primary_role = user._cached_primary_role_name
        else:
            primary_role = user.primary_role.name if user.primary_role else None

        sessions_info: List[CurrentUserSessionInfo] = []
        for session in user.sessions or []:
            sessions_info.append(CurrentUserSessionInfo(
                session_token=session.session_token,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                device_fingerprint=getattr(session, "device_fingerprint", None),
                created_at=session.created_at,
                last_activity_at=session.last_activity_at,
                expires_at=session.expires_at,
                is_current=(session.session_token == current_session_token),
            ))

        settings = CurrentUserSettings(
            preferred_language=getattr(user, "preferred_language", None),
            timezone=getattr(user, "timezone", None),
        )

        return CurrentUserContext(
            user_id=user.id,
            email=user.email,
            username=getattr(user, "username", None),
            full_name=getattr(user, "full_name", None),
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            customer_id=user.customer_id,
            department=getattr(user, "department", None),
            team=getattr(user, "team", None),
            roles=roles,
            permissions=permissions,
            primary_role=primary_role,
            last_login_at=getattr(user, "last_login_at", None),
            created_at=user.created_at,
            settings=settings,
            active_sessions=sessions_info,
        )


# Global authorization middleware instance
auth_middleware = AuthorizationMiddleware()
authorization_middleware = auth_middleware  # Backward compatibility alias

# Convenience functions for backward compatibility
get_current_user = auth_middleware.get_current_user
require_permission = auth_middleware.require_permission
require_any_permission = auth_middleware.require_any_permission
require_resource_access = auth_middleware.require_resource_access
check_company_access = auth_middleware.check_company_access
require_company_access = auth_middleware.require_company_access

# Adoption dashboard access functions
check_adoption_access = auth_middleware.check_adoption_access
require_adoption_access = auth_middleware.require_adoption_access
get_accessible_adoption_companies = auth_middleware.get_accessible_adoption_companies


async def get_current_customer_id(
    current_user: CurrentUserContext = Depends(get_current_user)
) -> str:
    """Expose the authenticated user's customer context."""
    if not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer context missing in token"
        )
    return current_user.customer_id
