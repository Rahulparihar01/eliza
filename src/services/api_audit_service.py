"""
API Audit Service - Background task-based audit logging for API requests.

This service provides audit logging that runs AFTER the request completes,
using FastAPI's BackgroundTasks. This approach:
1. Doesn't block the response
2. Has access to full request context (user, tenant, outcome)
3. Uses the standard database session pattern
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from src.models.audit import DataAccessAuditLog
from src.models.database import SessionLocal, init_database

logger = logging.getLogger(__name__)


def log_api_request_sync(
    action: str,
    resource_type: str,
    api_endpoint: str,
    api_method: str,
    customer_id: Optional[str] = None,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    outcome: str = 'success',
    status_code: Optional[int] = None,
    denial_reason: Optional[str] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    is_platform_admin: bool = False,
    cross_tenant_access: bool = False,
    view_as_tenant: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Synchronous audit logging function for use with BackgroundTasks.
    
    This is the primary function for logging API requests. It creates its own
    database session and handles cleanup properly.
    
    Args:
        action: The action performed (SELECT, INSERT, UPDATE, DELETE)
        resource_type: The type of resource accessed
        api_endpoint: API endpoint path
        api_method: HTTP method
        customer_id: Tenant ID
        user_id: User ID
        session_id: Request/session ID for tracing
        ip_address: Client IP
        user_agent: Client user agent
        outcome: Result (success, denied, error)
        status_code: HTTP status code
        denial_reason: Why access was denied
        error_message: Error details if failed
        duration_ms: Request duration
        is_platform_admin: Whether user is platform admin
        cross_tenant_access: Whether cross-tenant access was enabled
        view_as_tenant: Tenant ID if viewing as different tenant
        additional_context: Any additional context
    """
    try:
        # Ensure database is initialized
        if SessionLocal is None:
            init_database()
        
        db: Session = SessionLocal()
        try:
            # Build additional context
            ctx = additional_context or {}
            ctx['is_platform_admin'] = is_platform_admin
            ctx['cross_tenant_access'] = cross_tenant_access
            if view_as_tenant:
                ctx['view_as_tenant'] = view_as_tenant
            if status_code:
                ctx['status_code'] = status_code
            
            # Determine severity
            severity = 'low'
            if outcome == 'denied':
                severity = 'medium'
            elif outcome == 'error':
                severity = 'medium'
            elif action == 'DELETE':
                severity = 'medium'
            
            audit_log = DataAccessAuditLog(
                user_id=user_id,
                customer_id=customer_id or 'anonymous',
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,  # Limit length
                action=action,
                resource_type=resource_type,
                api_endpoint=api_endpoint,
                api_method=api_method,
                outcome=outcome,
                denial_reason=denial_reason,
                error_message=error_message[:1000] if error_message else None,
                severity=severity,
                duration_ms=duration_ms,
                additional_context=ctx,
            )
            
            db.add(audit_log)
            db.commit()
            
            logger.debug(
                f"API audit logged: {api_method} {api_endpoint} -> {outcome} "
                f"(user={user_id}, tenant={customer_id})"
            )
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to log API audit: {e}", exc_info=True)
        finally:
            db.close()
            
    except Exception as e:
        # Never let audit logging break the application
        logger.error(f"Failed to initialize audit logging: {e}", exc_info=True)


def create_audit_background_task(
    request,
    response_status_code: int,
    duration_ms: int,
) -> callable:
    """
    Create a background task function for audit logging.
    
    This is designed to be used with FastAPI's BackgroundTasks:
    
        @app.get("/items")
        async def get_items(
            background_tasks: BackgroundTasks,
            request: Request,
            current_user: CurrentUserContext = Depends(get_current_user)
        ):
            start_time = time.time()
            # ... do work ...
            duration_ms = int((time.time() - start_time) * 1000)
            background_tasks.add_task(
                create_audit_background_task(request, response.status_code, duration_ms)
            )
            return result
    
    Args:
        request: FastAPI Request object (must have state set by auth)
        response_status_code: HTTP status code of the response
        duration_ms: Request duration in milliseconds
    
    Returns:
        A callable that can be added to BackgroundTasks
    """
    # Extract all values NOW (before the request context is gone)
    customer_id = getattr(request.state, 'customer_id', None)
    user_id = getattr(request.state, 'user_id', None)
    is_platform_admin = getattr(request.state, 'is_platform_admin', False)
    
    api_endpoint = request.url.path
    api_method = request.method
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get('user-agent', '')
    request_id = request.headers.get('x-request-id', '')
    
    # Check for view-as-tenant header
    view_as_tenant = request.headers.get('x-view-as-tenant')
    cross_tenant_access = request.headers.get('x-cross-tenant-access', '').lower() == 'true'
    
    # Determine action from HTTP method
    method_to_action = {
        'GET': 'SELECT',
        'POST': 'INSERT',
        'PUT': 'UPDATE',
        'PATCH': 'UPDATE',
        'DELETE': 'DELETE',
    }
    action = method_to_action.get(api_method, api_method)
    
    # Extract resource type from path
    path_parts = api_endpoint.strip('/').split('/')
    resource_type = 'api_request'
    # Try to find meaningful resource type (e.g., "roles" from "/api/v1/admin/roles")
    for i, part in enumerate(path_parts):
        if part in ['api', 'v1', 'admin', 'platform-admin', 'tenant-admin']:
            continue
        if part and not part.isdigit():
            resource_type = part
            break
    
    # Determine outcome from status code
    if response_status_code < 400:
        outcome = 'success'
    elif response_status_code in [401, 403]:
        outcome = 'denied'
    else:
        outcome = 'error'
    
    def task():
        log_api_request_sync(
            action=action,
            resource_type=resource_type,
            api_endpoint=api_endpoint,
            api_method=api_method,
            customer_id=customer_id,
            user_id=user_id,
            session_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            outcome=outcome,
            status_code=response_status_code,
            duration_ms=duration_ms,
            is_platform_admin=is_platform_admin,
            cross_tenant_access=cross_tenant_access,
            view_as_tenant=view_as_tenant,
        )
    
    return task

