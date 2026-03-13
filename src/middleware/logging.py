"""
Request Logging Middleware

Manages request context propagation and HTTP request/response logging.
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.core.logging import (
    get_logger,
    bind_context,
    reset_context,
    LogCategory
)


logger = get_logger(__name__, component="middleware.logging")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to:
    1. Generate and propagate request IDs
    2. Bind request context (request_id, user_id, session_id)
    3. Log all HTTP requests/responses with timing
    4. Add request ID to response headers
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging and context management"""
        
        # Generate or extract request ID
        request_id = request.headers.get('x-request-id') or str(uuid.uuid4())
        
        # Extract user info if authenticated
        user_id = None
        session_id = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = str(getattr(request.state.user, 'id', None))
            session_id = request.headers.get('x-session-id')
        
        # Bind context for this request
        context_tokens = bind_context(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            trace_id=request.headers.get('x-trace-id')
        )
        
        # Start request timing
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            category=LogCategory.API,
            operation="http_request",
            metadata={
                'method': request.method,
                'path': request.url.path,
                'query_params': dict(request.query_params) if request.query_params else None,
                'client_host': request.client.host if request.client else None,
                'user_agent': request.headers.get('user-agent')
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            log_method = logger.info if response.status_code < 400 else logger.error
            log_method(
                f"Request completed: {request.method} {request.url.path} -> {response.status_code}",
                category=LogCategory.API,
                operation="http_request",
                duration_ms=duration_ms,
                metadata={
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': response.status_code,
                    'response_time_ms': round(duration_ms, 2)
                }
            )
            
            # Add request ID to response headers
            response.headers['X-Request-ID'] = request_id
            
            return response
            
        except Exception as e:
            # Log error
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exception=e,
                category=LogCategory.API,
                operation="http_request",
                duration_ms=duration_ms,
                metadata={
                    'method': request.method,
                    'path': request.url.path,
                    'error': str(e)
                }
            )
            
            # Re-raise to be handled by exception handlers
            raise
            
        finally:
            # Always reset context
            reset_context(context_tokens)


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log slow requests for performance monitoring.
    """
    
    def __init__(self, app: ASGIApp, slow_request_threshold_ms: float = 1000.0):
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log if slow"""
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Log slow requests
            if duration_ms > self.slow_request_threshold_ms:
                logger.warning(
                    f"Slow request detected: {request.method} {request.url.path}",
                    category=LogCategory.PERFORMANCE,
                    operation="slow_request",
                    duration_ms=duration_ms,
                    metadata={
                        'method': request.method,
                        'path': request.url.path,
                        'threshold_ms': self.slow_request_threshold_ms
                    }
                )
            
            return response
            
        except Exception:
            # Still log the duration even if request failed
            duration_ms = (time.time() - start_time) * 1000
            if duration_ms > self.slow_request_threshold_ms:
                logger.warning(
                    f"Slow failed request: {request.method} {request.url.path}",
                    category=LogCategory.PERFORMANCE,
                    operation="slow_request",
                    duration_ms=duration_ms,
                    metadata={
                        'method': request.method,
                        'path': request.url.path,
                        'threshold_ms': self.slow_request_threshold_ms,
                        'failed': True
                    }
                )
            raise

