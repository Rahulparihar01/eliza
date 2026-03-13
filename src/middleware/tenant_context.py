"""
Tenant Context Middleware for Multi-Tenant Isolation

This middleware sets the PostgreSQL session variable `app.customer_id` 
for Row Level Security (RLS) policies to use. It ensures that all database
queries are automatically scoped to the current user's tenant.

Critical for SOC2 compliance - provides defense-in-depth tenant isolation.
"""

import logging
import time
import uuid
import asyncio
from typing import Optional, Callable
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import re
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.database import SessionLocal, init_database

logger = logging.getLogger(__name__)

# Flag to control audit logging (can be disabled for performance testing)
ENABLE_API_AUDIT_LOGGING = True

# Context variable to store current tenant ID (thread-safe)
_current_tenant_id: ContextVar[Optional[str]] = ContextVar('current_tenant_id', default=None)
_current_user_id: ContextVar[Optional[int]] = ContextVar('current_user_id', default=None)
_current_request_id: ContextVar[Optional[str]] = ContextVar('current_request_id', default=None)


def get_current_tenant_id() -> Optional[str]:
    """Get the current tenant ID from context."""
    return _current_tenant_id.get()


def get_current_user_id() -> Optional[int]:
    """Get the current user ID from context."""
    return _current_user_id.get()


def get_current_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return _current_request_id.get()


def set_tenant_context(tenant_id: Optional[str], user_id: Optional[int] = None, request_id: Optional[str] = None):
    """
    Set the tenant context for the current request/task.
    
    This should be called:
    1. By middleware for HTTP requests
    2. By Celery tasks before database operations
    3. By background jobs that need tenant scoping
    """
    _current_tenant_id.set(tenant_id)
    if user_id is not None:
        _current_user_id.set(user_id)
    if request_id is not None:
        _current_request_id.set(request_id)


def clear_tenant_context():
    """Clear the tenant context after request/task completion."""
    _current_tenant_id.set(None)
    _current_user_id.set(None)
    _current_request_id.set(None)


def set_db_tenant_context(
    db: Session, 
    tenant_id: str,
    is_platform_admin: bool = False,
    cross_tenant_access: bool = False
) -> None:
    """
    Set the PostgreSQL session variables for RLS.
    
    This MUST be called before any tenant-scoped queries to ensure
    Row Level Security policies are properly applied.
    
    Args:
        db: SQLAlchemy database session
        tenant_id: The customer_id to scope queries to (REQUIRED - never NULL)
        is_platform_admin: Whether the current user is a platform admin
        cross_tenant_access: Whether cross-tenant read access is explicitly requested
    
    Security Notes:
        - tenant_id is ALWAYS required - no NULL bypass
        - cross_tenant_access only allows READS, not writes
        - Both is_platform_admin AND cross_tenant_access must be true for cross-tenant
    """
    if not tenant_id:
        raise ValueError("tenant_id is required - cannot be NULL or empty")

    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', tenant_id):
        raise ValueError(f"tenant_id contains invalid characters: {tenant_id!r}")

    admin_flag = str(is_platform_admin).lower()
    cross_flag = str(cross_tenant_access).lower()

    db.execute(text("SET LOCAL app.customer_id = :tid"), {"tid": tenant_id})
    db.execute(text("SET LOCAL app.is_platform_admin = :flag"), {"flag": admin_flag})
    db.execute(text("SET LOCAL app.cross_tenant_access = :flag"), {"flag": cross_flag})

    logger.debug(
        f"Set database tenant context: tenant={tenant_id}, "
        f"platform_admin={is_platform_admin}, cross_tenant={cross_tenant_access}"
    )


def get_tenant_scoped_session(
    tenant_id: str,
    is_platform_admin: bool = False,
    cross_tenant_access: bool = False
) -> Session:
    """
    Get a database session with tenant context already set.
    
    Usage:
        with get_tenant_scoped_session('customer_123') as db:
            # All queries automatically scoped to customer_123
            users = db.query(User).all()
    
    Args:
        tenant_id: The tenant to scope queries to (REQUIRED)
        is_platform_admin: Whether user is platform admin
        cross_tenant_access: Whether to allow cross-tenant reads
    """
    if not tenant_id:
        raise ValueError("tenant_id is required for all database sessions")
    
    if SessionLocal is None:
        init_database()
    
    db = SessionLocal()
    try:
        set_db_tenant_context(db, tenant_id, is_platform_admin, cross_tenant_access)
        return db
    except Exception:
        db.close()
        raise


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that handles tenant context and audit logging.
    
    This middleware:
    1. Generates request ID for tracing
    2. Sets context variables for application-level access
    3. Logs requests to audit trail (using background sync function)
    
    Note: Tenant info is extracted from request.state AFTER the route handler
    sets it via the auth dependency. This avoids duplicating JWT decoding logic.
    
    Security:
    - Platform admins can "view as" another tenant with X-View-As-Tenant header
    - Cross-tenant access requires explicit X-Cross-Tenant-Access header
    """
    
    # Header for platform admins to view as a different tenant
    VIEW_AS_TENANT_HEADER = 'x-view-as-tenant'
    # Header to enable cross-tenant read access (platform admins only)
    CROSS_TENANT_HEADER = 'x-cross-tenant-access'
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.excluded_paths = {
            '/health',
            '/health/ready',
            '/health/live',
            '/metrics',
            '/docs',
            '/openapi.json',
            '/redoc',
            '/api/v1/auth/login',
            '/api/v1/auth/register',
            '/api/v1/auth/refresh',
            '/api/v1/auth/forgot-password',
            '/api/v1/auth/reset-password',
            '/v1/auth/login',
            '/v1/auth/register',
            '/v1/auth/refresh',
            '/v1/auth/forgot-password',
            '/v1/auth/reset-password',
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with tenant context and audit logging."""
        
        # Generate request ID for tracing
        request_id = request.headers.get('x-request-id') or str(uuid.uuid4())
        
        # Initialize request state for tenant context (will be set by auth dependency)
        request.state.customer_id = None
        request.state.user_id = None
        request.state.is_platform_admin = False
        request.state.request_id = request_id
        
        # Skip detailed processing for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Check for platform admin headers (will be validated by auth dependency)
        view_as_tenant = request.headers.get(self.VIEW_AS_TENANT_HEADER)
        cross_tenant_access = request.headers.get(self.CROSS_TENANT_HEADER, '').lower() == 'true'
        
        # Store header values in request state for auth dependency to use
        request.state.view_as_tenant_header = view_as_tenant
        request.state.cross_tenant_access_header = cross_tenant_access
        
        start_time = time.time()
        
        try:
            # Process the request - auth dependency will set request.state.customer_id etc.
            response = await call_next(request)
            
            # Get tenant context that was set by auth dependency
            tenant_id = getattr(request.state, 'customer_id', None)
            user_id = getattr(request.state, 'user_id', None)
            is_platform_admin = getattr(request.state, 'is_platform_admin', False)
            
            # Handle "View As Tenant" for platform admins
            effective_tenant_id = tenant_id
            if is_platform_admin and view_as_tenant:
                effective_tenant_id = view_as_tenant
                logger.info(
                    f"Platform admin {user_id} viewing as tenant: {view_as_tenant}",
                    extra={
                        'original_tenant': tenant_id,
                        'view_as_tenant': view_as_tenant,
                        'user_id': user_id,
                    }
                )
            
            # Set context variables for downstream use
            set_tenant_context(effective_tenant_id, user_id, request_id)
            set_platform_admin_context(is_platform_admin, cross_tenant_access)
            
            # Add context to response headers (for debugging)
            if effective_tenant_id:
                response.headers['X-Tenant-ID'] = effective_tenant_id
            response.headers['X-Request-ID'] = request_id
            if view_as_tenant and is_platform_admin:
                response.headers['X-Viewing-As-Tenant'] = view_as_tenant
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log request completion
            logger.info(
                f"Request completed",
                extra={
                    'request_id': request_id,
                    'tenant_id': effective_tenant_id,
                    'user_id': user_id,
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': response.status_code,
                    'duration_ms': duration_ms,
                    'is_platform_admin': is_platform_admin,
                    'view_as_tenant': view_as_tenant,
                    'cross_tenant_access': cross_tenant_access,
                }
            )
            
            # Log to audit database — fire-and-forget in background thread.
            # Uses run_in_executor (without await) so audit logging never delays the response.
            # We extract request data first since the request object may not be available later.
            if ENABLE_API_AUDIT_LOGGING and effective_tenant_id:
                # Extract request data while request is still available
                _req_method = request.method
                _req_path = request.url.path
                _req_client_host = request.client.host if request.client else None
                _req_user_agent = request.headers.get('user-agent', '')
                _resp_status = response.status_code
                
                def _audit_log():
                    self._log_api_request_sync(
                        request=request,
                        status_code=_resp_status,
                        tenant_id=effective_tenant_id,
                        user_id=user_id,
                        request_id=request_id,
                        duration_ms=duration_ms,
                        is_platform_admin=is_platform_admin,
                        view_as_tenant=view_as_tenant,
                        cross_tenant_access=cross_tenant_access,
                    )
                
                asyncio.get_event_loop().run_in_executor(None, _audit_log)
            
            return response
            
        except Exception as e:
            # Log failed request
            duration_ms = int((time.time() - start_time) * 1000)
            tenant_id = getattr(request.state, 'customer_id', None)
            user_id = getattr(request.state, 'user_id', None)
            
            logger.error(
                f"Request failed: {str(e)}",
                extra={
                    'request_id': request_id,
                    'tenant_id': tenant_id,
                    'user_id': user_id,
                    'method': request.method,
                    'path': request.url.path,
                    'duration_ms': duration_ms,
                    'error': str(e),
                }
            )
            
            # Log failure to audit database — fire-and-forget in background thread
            if ENABLE_API_AUDIT_LOGGING and tenant_id:
                _error_msg = str(e)
                
                def _audit_log_error():
                    self._log_api_request_sync(
                        request=request,
                        status_code=500,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        request_id=request_id,
                        duration_ms=duration_ms,
                        is_platform_admin=False,
                        view_as_tenant=None,
                        cross_tenant_access=False,
                        error_message=_error_msg,
                    )
                
                asyncio.get_event_loop().run_in_executor(None, _audit_log_error)
            
            raise
            
        finally:
            # Always clear context after request
            clear_tenant_context()
            set_platform_admin_context(False, False)
    
    def _log_api_request_sync(
        self,
        request: Request,
        status_code: int,
        tenant_id: str,
        user_id: Optional[int],
        request_id: str,
        duration_ms: int,
        is_platform_admin: bool,
        view_as_tenant: Optional[str],
        cross_tenant_access: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Log API request to the data access audit log using synchronous function.
        
        This uses the api_audit_service which handles its own database session.
        """
        try:
            from src.services.api_audit_service import log_api_request_sync
            
            # Determine outcome based on status code
            if status_code < 400:
                outcome = 'success'
            elif status_code in [401, 403]:
                outcome = 'denied'
            else:
                outcome = 'error'
            
            # Determine action based on HTTP method
            method_to_action = {
                'GET': 'SELECT',
                'POST': 'INSERT',
                'PUT': 'UPDATE',
                'PATCH': 'UPDATE',
                'DELETE': 'DELETE',
            }
            action = method_to_action.get(request.method, request.method)
            
            # Extract resource type from path
            path_parts = request.url.path.strip('/').split('/')
            resource_type = 'api_request'
            for part in path_parts:
                if part in ['api', 'v1', 'admin', 'platform-admin', 'tenant-admin']:
                    continue
                if part and not part.isdigit():
                    resource_type = part
                    break
            
            # Get client info
            client_host = request.client.host if request.client else None
            user_agent = request.headers.get('user-agent', '')
            
            log_api_request_sync(
                action=action,
                resource_type=resource_type,
                api_endpoint=request.url.path,
                api_method=request.method,
                customer_id=tenant_id,
                user_id=user_id,
                session_id=request_id,
                ip_address=client_host,
                user_agent=user_agent,
                outcome=outcome,
                status_code=status_code,
                denial_reason=f"HTTP {status_code}" if outcome == 'denied' else None,
                error_message=error_message or (f"HTTP {status_code}" if outcome == 'error' else None),
                duration_ms=duration_ms,
                is_platform_admin=is_platform_admin,
                cross_tenant_access=cross_tenant_access,
                view_as_tenant=view_as_tenant,
            )
            
        except Exception as e:
            # Never let audit logging failures break the application
            logger.error(f"Failed to log API request to audit: {e}", exc_info=True)


class TenantScopedSession:
    """
    Context manager for tenant-scoped database sessions.
    
    Usage:
        async with TenantScopedSession(tenant_id='customer_123') as db:
            users = db.query(User).filter(...).all()
    
    Or in sync context:
        with TenantScopedSession(tenant_id='customer_123') as db:
            users = db.query(User).filter(...).all()
    
    For platform admins doing cross-tenant operations:
        with TenantScopedSession(
            tenant_id='eliza',  # Platform admin's home tenant
            is_platform_admin=True,
            cross_tenant_access=True
        ) as db:
            # Can read from all tenants
            all_users = db.query(User).all()
    """
    
    def __init__(
        self, 
        tenant_id: Optional[str] = None, 
        user_id: Optional[int] = None,
        is_platform_admin: bool = False,
        cross_tenant_access: bool = False
    ):
        """
        Initialize tenant-scoped session.
        
        Args:
            tenant_id: Customer ID to scope queries to. If None, uses current context.
            user_id: User ID for audit logging. If None, uses current context.
            is_platform_admin: Whether the user is a platform admin.
            cross_tenant_access: Whether to allow cross-tenant read access.
        """
        self.tenant_id = tenant_id or get_current_tenant_id()
        self.user_id = user_id or get_current_user_id()
        self.is_platform_admin = is_platform_admin
        self.cross_tenant_access = cross_tenant_access
        self.db: Optional[Session] = None
        
        if not self.tenant_id:
            raise ValueError(
                "tenant_id is required. Either pass it explicitly or ensure "
                "the request has tenant context set via middleware."
            )
    
    def __enter__(self) -> Session:
        """Sync context manager entry."""
        if SessionLocal is None:
            init_database()
        
        self.db = SessionLocal()
        
        # Set all tenant context variables
        set_db_tenant_context(
            self.db, 
            self.tenant_id,
            self.is_platform_admin,
            self.cross_tenant_access
        )
        
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        if self.db:
            if exc_type is not None:
                self.db.rollback()
            self.db.close()
    
    async def __aenter__(self) -> Session:
        """Async context manager entry."""
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        return self.__exit__(exc_type, exc_val, exc_tb)


def with_tenant_context(tenant_id: str):
    """
    Decorator to wrap a function with tenant context.
    
    Usage:
        @with_tenant_context('customer_123')
        def my_task():
            # All database queries scoped to customer_123
            pass
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            set_tenant_context(tenant_id)
            try:
                return func(*args, **kwargs)
            finally:
                clear_tenant_context()
        return wrapper
    return decorator


# Context variable for platform admin flags
_is_platform_admin: ContextVar[bool] = ContextVar('is_platform_admin', default=False)
_cross_tenant_access: ContextVar[bool] = ContextVar('cross_tenant_access', default=False)


def get_is_platform_admin() -> bool:
    """Get whether current user is a platform admin."""
    return _is_platform_admin.get()


def get_cross_tenant_access() -> bool:
    """Get whether cross-tenant access is enabled for current request."""
    return _cross_tenant_access.get()


def set_platform_admin_context(is_admin: bool, cross_tenant: bool = False):
    """Set platform admin context for current request."""
    _is_platform_admin.set(is_admin)
    _cross_tenant_access.set(cross_tenant)


# Dependency injection for FastAPI routes
def get_tenant_db(tenant_id: Optional[str] = None):
    """
    FastAPI dependency that provides a tenant-scoped database session.
    
    Usage in routes:
        @router.get("/items")
        async def get_items(
            db: Session = Depends(get_tenant_db),
            current_user: User = Depends(get_current_user)
        ):
            # db is already scoped to current_user's tenant
            return db.query(Item).all()
    """
    if SessionLocal is None:
        init_database()
    
    db = SessionLocal()
    try:
        # Use provided tenant_id or get from context
        effective_tenant_id = tenant_id or get_current_tenant_id()
        
        if not effective_tenant_id:
            raise ValueError(
                "No tenant context available. Ensure user is authenticated "
                "and tenant context middleware is configured."
            )
        
        # Get platform admin flags from context
        is_admin = get_is_platform_admin()
        cross_tenant = get_cross_tenant_access()
        
        # Set all context variables in database
        set_db_tenant_context(db, effective_tenant_id, is_admin, cross_tenant)
        logger.debug(
            f"Database session: tenant={effective_tenant_id}, "
            f"platform_admin={is_admin}, cross_tenant={cross_tenant}"
        )
        
        yield db
    finally:
        db.close()

