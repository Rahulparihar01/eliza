"""
AI Enablement Platform - Custom Exceptions

Custom exception classes for the AI Enablement Platform.
"""

from typing import Optional, Dict, Any


class AIEnablementException(Exception):
    """Base exception for AI Enablement Platform."""
    
    def __init__(
        self,
        detail: str,
        status_code: int = 500,
        error_code: str = "ai_enablement_error",
        context: Optional[Dict[str, Any]] = None
    ):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        self.context = context or {}
        super().__init__(detail)


class ConfigurationError(AIEnablementException):
    """Configuration-related errors."""
    
    def __init__(self, detail: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            detail=detail,
            status_code=500,
            error_code="configuration_error",
            context=context
        )


class ModelProviderError(AIEnablementException):
    """AI model provider-related errors."""
    
    def __init__(self, detail: str, provider: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context["provider"] = provider
        super().__init__(
            detail=detail,
            status_code=502,
            error_code="model_provider_error",
            context=context
        )


class DataIngestionError(AIEnablementException):
    """Data ingestion-related errors."""
    
    def __init__(self, detail: str, source: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context["source"] = source
        super().__init__(
            detail=detail,
            status_code=422,
            error_code="data_ingestion_error",
            context=context
        )


class ValidationError(AIEnablementException):
    """Data validation errors."""
    
    def __init__(self, detail: str, field: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context["field"] = field
        super().__init__(
            detail=detail,
            status_code=400,
            error_code="validation_error",
            context=context
        )


class AuthenticationError(AIEnablementException):
    """Authentication-related errors."""
    
    def __init__(self, detail: str = "Authentication failed", context: Optional[Dict[str, Any]] = None):
        super().__init__(
            detail=detail,
            status_code=401,
            error_code="authentication_error",
            context=context
        )


class AuthorizationError(AIEnablementException):
    """Authorization-related errors."""
    
    def __init__(self, detail: str = "Access denied", context: Optional[Dict[str, Any]] = None):
        super().__init__(
            detail=detail,
            status_code=403,
            error_code="authorization_error",
            context=context
        )


class ResourceNotFoundError(AIEnablementException):
    """Resource not found errors."""
    
    def __init__(self, detail: str, resource_type: str, resource_id: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context.update({
            "resource_type": resource_type,
            "resource_id": resource_id
        })
        super().__init__(
            detail=detail,
            status_code=404,
            error_code="resource_not_found",
            context=context
        )


class RateLimitError(AIEnablementException):
    """Rate limiting errors."""
    
    def __init__(self, detail: str = "Rate limit exceeded", context: Optional[Dict[str, Any]] = None):
        super().__init__(
            detail=detail,
            status_code=429,
            error_code="rate_limit_error",
            context=context
        )


class ExternalServiceError(AIEnablementException):
    """External service errors."""
    
    def __init__(self, detail: str, service: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context["service"] = service
        super().__init__(
            detail=detail,
            status_code=503,
            error_code="external_service_error",
            context=context
        )


class DatabaseError(AIEnablementException):
    """Database-related errors."""
    
    def __init__(self, detail: str, operation: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context["operation"] = operation
        super().__init__(
            detail=detail,
            status_code=500,
            error_code="database_error",
            context=context
        )


class VectorStoreError(AIEnablementException):
    """Vector store-related errors."""
    
    def __init__(self, detail: str, operation: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context["operation"] = operation
        super().__init__(
            detail=detail,
            status_code=500,
            error_code="vector_store_error",
            context=context
        )


class AgentError(AIEnablementException):
    """CrewAI agent-related errors."""
    
    def __init__(self, detail: str, agent_name: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context["agent_name"] = agent_name
        super().__init__(
            detail=detail,
            status_code=500,
            error_code="agent_error",
            context=context
        )


class TaskEnrichmentError(AIEnablementException):
    """Task enrichment-related errors."""
    
    def __init__(self, detail: str, task_type: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context["task_type"] = task_type
        super().__init__(
            detail=detail,
            status_code=422,
            error_code="task_enrichment_error",
            context=context
        )
