"""
AI Enablement Platform - Configuration Routes

API endpoints for managing customer configuration and settings.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from src.core.config import get_settings, get_customer_config
from src.core.exceptions import ConfigurationError, ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()


class BrandingConfig(BaseModel):
    """Branding configuration model."""
    company_name: str
    logo_url: Optional[str] = None
    primary_color: str = "#2F6BFF"
    secondary_color: str = "#8B5CF6"
    custom_css: Optional[str] = None


class DataSourceConfig(BaseModel):
    """Data source configuration model."""
    name: str
    type: str
    enabled: bool = True
    connection_config: Dict[str, Any] = {}
    chunking_strategy: str = "semantic"
    qa_rag_enabled: bool = False


class BusinessRulesConfig(BaseModel):
    """Business rules configuration model."""
    departments: List[str] = []
    roles: List[str] = []
    custom_analysis_rules: Dict[str, Any] = {}
    roi_calculation_method: str = "realistic"


class CustomerConfigResponse(BaseModel):
    """Customer configuration response model."""
    customer_id: str
    customer_name: str
    branding: BrandingConfig
    data_sources: List[DataSourceConfig]
    business_rules: BusinessRulesConfig
    created_at: str
    updated_at: str


class SystemInfoResponse(BaseModel):
    """System information response model."""
    version: str
    environment: str
    customer_id: str
    customer_name: str
    uptime_seconds: float
    configuration_loaded: bool
    data_sources_count: int
    enabled_data_sources_count: int


class RAGSettingsResponse(BaseModel):
    """RAG pipeline settings (embedding and inference). Read from env; changing requires RAG_* env vars."""
    embedding_provider: str = Field(description="Current embedding provider: openai, local, or bedrock")
    embedding_model: str = Field(description="Current embedding model (e.g. text-embedding-3-small, amazon.titan-embed-text-v1)")
    available_embedding_providers: List[str] = Field(
        default_factory=lambda: ["openai", "local", "bedrock"],
        description="Supported embedding providers",
    )
    default_llm_model: Optional[str] = Field(default=None, description="Default LLM model for RAG chat when no workspace override is set")


def get_customer_config_dependency():
    """Dependency to get customer configuration."""
    settings = get_settings()
    return get_customer_config(settings.customer_id)


@router.get("/rag-settings", response_model=RAGSettingsResponse)
async def get_rag_settings():
    """
    Get current RAG pipeline settings (embedding provider/model and default LLM).

    Values are read from environment (RAG_EMBEDDING_PROVIDER, RAGFLOW_DEFAULT_EMBEDDING_MODEL,
    DEFAULT_LLM_MODEL). To change embedding provider (e.g. to Bedrock), set
    RAG_EMBEDDING_PROVIDER=bedrock and RAG_BEDROCK_EMBEDDING_REGION as needed.
    """
    settings = get_settings()
    provider = (settings.rag_embedding_provider or "openai").strip().lower()
    if provider not in ("openai", "local", "bedrock"):
        provider = "openai"
    embedding_model = (
        settings.ragflow_default_embedding_model
        or (("amazon.titan-embed-text-v1" if provider == "bedrock" else "text-embedding-3-small"))
    )
    return RAGSettingsResponse(
        embedding_provider=provider,
        embedding_model=embedding_model,
        available_embedding_providers=["openai", "local", "bedrock"],
        default_llm_model=settings.default_llm_model or None,
    )


@router.get("/", response_model=CustomerConfigResponse)
async def get_configuration(
    customer_config = Depends(get_customer_config_dependency)
):
    """
    Get complete customer configuration.
    
    Returns all configuration settings for the current customer.
    """
    try:
        config_data = customer_config.load_config()
        
        return CustomerConfigResponse(
            customer_id=config_data["customer_id"],
            customer_name=config_data["customer_name"],
            branding=BrandingConfig(**config_data["branding"]),
            data_sources=[DataSourceConfig(**ds) for ds in config_data["data_sources"]],
            business_rules=BusinessRulesConfig(**config_data["business_rules"]),
            created_at=config_data["created_at"],
            updated_at=config_data["updated_at"]
        )
    
    except Exception as e:
        logger.error(f"Failed to get customer configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve configuration: {str(e)}"
        )


@router.get("/branding", response_model=BrandingConfig)
async def get_branding_config(
    customer_config = Depends(get_customer_config_dependency)
):
    """
    Get branding configuration.
    
    Returns customer-specific branding settings.
    """
    try:
        branding = customer_config.branding
        return BrandingConfig(**branding)
    
    except Exception as e:
        logger.error(f"Failed to get branding configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve branding configuration: {str(e)}"
        )


@router.get("/data-sources", response_model=List[DataSourceConfig])
async def get_data_sources_config(
    enabled_only: bool = False,
    customer_config = Depends(get_customer_config_dependency)
):
    """
    Get data sources configuration.
    
    Args:
        enabled_only: If True, return only enabled data sources
    
    Returns customer-specific data source configurations.
    """
    try:
        if enabled_only:
            data_sources = customer_config.get_enabled_data_sources()
        else:
            data_sources = customer_config.data_sources
        
        return [DataSourceConfig(**ds) for ds in data_sources]
    
    except Exception as e:
        logger.error(f"Failed to get data sources configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve data sources configuration: {str(e)}"
        )


@router.get("/data-sources/{source_name}", response_model=DataSourceConfig)
async def get_data_source_config(
    source_name: str,
    customer_config = Depends(get_customer_config_dependency)
):
    """
    Get configuration for a specific data source.
    
    Args:
        source_name: Name of the data source
    """
    try:
        data_sources = customer_config.data_sources
        
        for ds in data_sources:
            if ds["name"].lower() == source_name.lower():
                return DataSourceConfig(**ds)
        
        raise HTTPException(
            status_code=404,
            detail=f"Data source '{source_name}' not found"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get data source configuration for {source_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve data source configuration: {str(e)}"
        )


@router.get("/business-rules", response_model=BusinessRulesConfig)
async def get_business_rules_config(
    customer_config = Depends(get_customer_config_dependency)
):
    """
    Get business rules configuration.
    
    Returns customer-specific business rules and constraints.
    """
    try:
        business_rules = customer_config.business_rules
        return BusinessRulesConfig(**business_rules)
    
    except Exception as e:
        logger.error(f"Failed to get business rules configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve business rules configuration: {str(e)}"
        )


@router.get("/system-info", response_model=SystemInfoResponse)
async def get_system_info(
    customer_config = Depends(get_customer_config_dependency)
):
    """
    Get system information and configuration status.
    
    Returns general system information and configuration health.
    """
    try:
        settings = get_settings()
        config_data = customer_config.load_config()
        
        # Calculate uptime (placeholder - would need actual start time tracking)
        uptime_seconds = 0.0  # TODO: Implement actual uptime tracking
        
        return SystemInfoResponse(
            version="1.0.0",
            environment=settings.environment,
            customer_id=settings.customer_id,
            customer_name=config_data["customer_name"],
            uptime_seconds=uptime_seconds,
            configuration_loaded=True,
            data_sources_count=len(customer_config.data_sources),
            enabled_data_sources_count=len(customer_config.get_enabled_data_sources())
        )
    
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve system information: {str(e)}"
        )


@router.get("/validate", response_model=Dict[str, Any])
async def validate_configuration(
    customer_config = Depends(get_customer_config_dependency)
):
    """
    Validate customer configuration.
    
    Performs comprehensive validation of the customer configuration
    and returns any issues found.
    """
    try:
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks_performed": []
        }
        
        # Load and validate configuration
        config_data = customer_config.load_config()
        validation_results["checks_performed"].append("configuration_loading")
        
        # Validate required fields
        required_fields = ["customer_id", "customer_name", "branding", "data_sources"]
        for field in required_fields:
            if field not in config_data:
                validation_results["errors"].append(f"Missing required field: {field}")
                validation_results["valid"] = False
        
        validation_results["checks_performed"].append("required_fields")
        
        # Validate data sources
        data_sources = customer_config.data_sources
        if not data_sources:
            validation_results["warnings"].append("No data sources configured")
        else:
            enabled_sources = customer_config.get_enabled_data_sources()
            if not enabled_sources:
                validation_results["warnings"].append("No data sources are enabled")
        
        validation_results["checks_performed"].append("data_sources")
        
        # Validate business rules
        business_rules = customer_config.business_rules
        if not business_rules.get("departments"):
            validation_results["warnings"].append("No departments configured in business rules")
        
        if not business_rules.get("roles"):
            validation_results["warnings"].append("No roles configured in business rules")
        
        validation_results["checks_performed"].append("business_rules")
        
        # Validate model configuration
        try:
            default_provider = customer_config.get_default_provider()
            fallback_providers = customer_config.get_fallback_providers()
            
            if not default_provider:
                validation_results["errors"].append("No default AI provider configured")
                validation_results["valid"] = False
            
            if not fallback_providers:
                validation_results["warnings"].append("No fallback AI providers configured")
        
        except Exception as e:
            validation_results["errors"].append(f"Model configuration error: {str(e)}")
            validation_results["valid"] = False
        
        validation_results["checks_performed"].append("model_configuration")
        
        return validation_results
    
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration validation failed: {str(e)}"
        )
