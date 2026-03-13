"""
AI Enablement Platform - Health Check Routes

Health check endpoints for monitoring and deployment validation.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import time
import asyncio
import logging
from datetime import datetime

from src.core.config import get_settings, get_customer_config
from src.core.exceptions import AIEnablementException
from src.services.database_service import DatabaseService

logger = logging.getLogger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: float
    version: str
    customer_id: str
    environment: str
    uptime_seconds: Optional[float] = None


class DetailedHealthResponse(BaseModel):
    """Detailed health check response model."""
    status: str
    timestamp: float
    version: str
    customer_id: str
    environment: str
    uptime_seconds: Optional[float] = None
    services: Dict[str, Dict[str, Any]]
    configuration: Dict[str, Any]


# Track application start time for uptime calculation
_start_time = time.time()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns basic application status and metadata.
    """
    settings = get_settings()
    
    return HealthResponse(
        status="healthy",
        timestamp=time.time(),
        version="1.0.0",
        customer_id=settings.customer_id,
        environment=settings.environment,
        uptime_seconds=time.time() - _start_time
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check():
    """
    Readiness check endpoint.
    
    Verifies that the application is ready to serve requests.
    This includes checking critical dependencies.
    """
    settings = get_settings()
    
    try:
        # Check customer configuration
        customer_config = get_customer_config(settings.customer_id)
        customer_config.load_config()
        
        # TODO: Add more readiness checks as we implement services
        # - Database connectivity
        # - Redis connectivity
        # - Neo4j connectivity
        # - AI provider availability
        
        return HealthResponse(
            status="ready",
            timestamp=time.time(),
            version="1.0.0",
            customer_id=settings.customer_id,
            environment=settings.environment,
            uptime_seconds=time.time() - _start_time
        )
    
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """
    Detailed health check endpoint.
    
    Provides comprehensive status information about all services and configuration.
    """
    settings = get_settings()
    
    try:
        # Initialize service status tracking
        services = {}
        
        # Check customer configuration
        config_status = await _check_customer_configuration(settings.customer_id)
        services["customer_configuration"] = config_status
        
        # Check AI providers
        ai_providers_status = await _check_ai_providers(settings)
        services["ai_providers"] = ai_providers_status
        
        # Check database
        database_status = await _check_database()
        services["database"] = database_status

        # TODO: Add more service checks as we implement them
        # services["redis"] = await _check_redis()
        # services["neo4j"] = await _check_neo4j()
        # services["vector_store"] = await _check_vector_store()
        
        # Determine overall status
        overall_status = "healthy"
        for service_name, service_info in services.items():
            if service_info["status"] != "healthy":
                overall_status = "degraded" if overall_status == "healthy" else "unhealthy"
        
        # Get configuration summary
        configuration = _get_configuration_summary(settings)
        
        return DetailedHealthResponse(
            status=overall_status,
            timestamp=time.time(),
            version="1.0.0",
            customer_id=settings.customer_id,
            environment=settings.environment,
            uptime_seconds=time.time() - _start_time,
            services=services,
            configuration=configuration
        )
    
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


async def _check_customer_configuration(customer_id: str) -> Dict[str, Any]:
    """Check customer configuration status."""
    try:
        customer_config = get_customer_config(customer_id)
        config_data = customer_config.load_config()
        
        return {
            "status": "healthy",
            "message": "Customer configuration loaded successfully",
            "details": {
                "customer_name": config_data.get("customer_name", "Unknown"),
                "data_sources_count": len(customer_config.data_sources),
                "enabled_data_sources": len(customer_config.get_enabled_data_sources()),
                "default_provider": customer_config.get_default_provider(),
                "config_file_exists": True
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Customer configuration error: {str(e)}",
            "details": {"error": str(e)}
        }


async def _check_ai_providers(settings) -> Dict[str, Any]:
    """Check AI provider availability."""
    providers = {}
    
    # Check OpenAI
    if settings.openai_api_key:
        providers["openai"] = {
            "configured": True,
            "api_key_present": bool(settings.openai_api_key),
            "status": "unknown"  # TODO: Add actual API check
        }
    else:
        providers["openai"] = {
            "configured": False,
            "api_key_present": False,
            "status": "not_configured"
        }
    
    # Check Anthropic
    if settings.anthropic_api_key:
        providers["anthropic"] = {
            "configured": True,
            "api_key_present": bool(settings.anthropic_api_key),
            "status": "unknown"  # TODO: Add actual API check
        }
    else:
        providers["anthropic"] = {
            "configured": False,
            "api_key_present": False,
            "status": "not_configured"
        }
    
    # Check Groq
    if settings.groq_api_key:
        providers["groq"] = {
            "configured": True,
            "api_key_present": bool(settings.groq_api_key),
            "status": "unknown"  # TODO: Add actual API check
        }
    else:
        providers["groq"] = {
            "configured": False,
            "api_key_present": False,
            "status": "not_configured"
        }
    
    # Determine overall AI providers status
    configured_count = sum(1 for p in providers.values() if p["configured"])
    
    if configured_count == 0:
        status = "unhealthy"
        message = "No AI providers configured"
    elif configured_count >= 1:
        status = "healthy"
        message = f"{configured_count} AI provider(s) configured"
    else:
        status = "degraded"
        message = "Limited AI providers configured"
    
    return {
        "status": status,
        "message": message,
        "details": {
            "providers": providers,
            "configured_count": configured_count
        }
    }


def _get_configuration_summary(settings) -> Dict[str, Any]:
    """Get configuration summary for health check."""
    return {
        "environment": settings.environment,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "customer_id": settings.customer_id,
        "database_configured": bool(settings.database_url),
        "redis_configured": bool(settings.redis_host_url),
        "neo4j_configured": bool(settings.neo4j_uri),
        "ai_providers": {
            "openai": bool(settings.openai_api_key),
            "anthropic": bool(settings.anthropic_api_key),
            "groq": bool(settings.groq_api_key),
            "together": bool(settings.together_api_key)
        }
    }


async def _check_database() -> Dict[str, Any]:
    """Check database connectivity and status."""
    try:
        # Use the database service from app state if available
        from fastapi import Request
        from src.models import check_database_health

        # For now, use the direct database health check
        # In a real implementation, we'd get the db_service from app state
        health_status = await check_database_health()

        return {
            "status": health_status["status"],
            "message": health_status["message"],
            "details": health_status.get("details", {})
        }

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Database check failed: {str(e)}",
            "details": {}
        }
