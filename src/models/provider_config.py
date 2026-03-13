"""
AI Enablement Platform - Provider Configuration Models

Unified Pydantic models for configuring AI providers (OpenAI, Anthropic, Groq, Bedrock, etc.)
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ProviderType(str, Enum):
    """Supported AI provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    BEDROCK = "bedrock"
    TOGETHER = "together"
    AZURE_OPENAI = "azure_openai"


class ProviderAuthMethod(str, Enum):
    """Authentication methods for providers."""
    API_KEY = "api_key"
    IAM_ROLE = "iam_role"
    AZURE_AD = "azure_ad"


# ============================================================================
# OpenAI Configuration
# ============================================================================

class OpenAIConfiguration(BaseModel):
    """OpenAI provider configuration."""
    api_key: str = Field(..., description="OpenAI API key")
    organization_id: Optional[str] = Field(None, description="OpenAI organization ID")
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL"
    )
    available_models: List[str] = Field(
        default_factory=lambda: ["gpt-5", "gpt-5.2", "gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini"],
        description="Available models for this configuration"
    )
    default_model: Optional[str] = Field(None, description="Default model to use")
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout: int = Field(default=60, ge=5, le=300)


class OpenAIConfigurationCreate(BaseModel):
    """Request to create OpenAI configuration."""
    api_key: str
    organization_id: Optional[str] = None
    base_url: Optional[str] = None
    available_models: Optional[List[str]] = None
    default_model: Optional[str] = None
    max_retries: Optional[int] = Field(default=3, ge=0, le=10)
    timeout: Optional[int] = Field(default=60, ge=5, le=300)


# ============================================================================
# Anthropic Configuration
# ============================================================================

class AnthropicConfiguration(BaseModel):
    """Anthropic (Claude) provider configuration."""
    api_key: str = Field(..., description="Anthropic API key")
    base_url: str = Field(
        default="https://api.anthropic.com",
        description="Anthropic API base URL"
    )
    available_models: List[str] = Field(
        default_factory=lambda: [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-instant-1.2"
        ],
        description="Available Claude models"
    )
    default_model: Optional[str] = Field(None, description="Default model to use")
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout: int = Field(default=60, ge=5, le=300)


class AnthropicConfigurationCreate(BaseModel):
    """Request to create Anthropic configuration."""
    api_key: str
    base_url: Optional[str] = None
    available_models: Optional[List[str]] = None
    default_model: Optional[str] = None
    max_retries: Optional[int] = Field(default=3, ge=0, le=10)
    timeout: Optional[int] = Field(default=60, ge=5, le=300)


# ============================================================================
# Groq Configuration
# ============================================================================

class GroqConfiguration(BaseModel):
    """Groq provider configuration."""
    api_key: str = Field(..., description="Groq API key")
    base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Groq API base URL"
    )
    available_models: List[str] = Field(
        default_factory=lambda: [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma-7b-it"
        ],
        description="Available Groq models"
    )
    default_model: Optional[str] = Field(None, description="Default model to use")
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout: int = Field(default=60, ge=5, le=300)


class GroqConfigurationCreate(BaseModel):
    """Request to create Groq configuration."""
    api_key: str
    base_url: Optional[str] = None
    available_models: Optional[List[str]] = None
    default_model: Optional[str] = None
    max_retries: Optional[int] = Field(default=3, ge=0, le=10)
    timeout: Optional[int] = Field(default=60, ge=5, le=300)


# ============================================================================
# Unified Provider Configuration
# ============================================================================

class ProviderConfigurationCreate(BaseModel):
    """Unified request to create any provider configuration."""
    provider_type: ProviderType = Field(..., description="Type of provider to configure")
    
    # Common fields
    name: Optional[str] = Field(None, description="Friendly name for this configuration")
    is_enabled: bool = Field(default=True, description="Enable/disable this configuration")
    
    # Provider-specific config (JSON)
    config: Dict[str, Any] = Field(
        ...,
        description="Provider-specific configuration (API keys, endpoints, models, etc.)"
    )
    
    # Adoption tracking (OpenAI only)
    is_adoption_source: bool = Field(default=False, description="Use this provider for adoption tracking (OpenAI only)")
    chatgpt_workspace_id: Optional[str] = Field(None, description="ChatGPT Enterprise Workspace ID for compliance API")
    
    @validator('config')
    def validate_config(cls, v, values):
        """Validate config based on provider type."""
        provider_type = values.get('provider_type')
        
        if provider_type == ProviderType.OPENAI:
            if 'api_key' not in v:
                raise ValueError("OpenAI config requires 'api_key'")
        elif provider_type == ProviderType.ANTHROPIC:
            if 'api_key' not in v:
                raise ValueError("Anthropic config requires 'api_key'")
        elif provider_type == ProviderType.GROQ:
            if 'api_key' not in v:
                raise ValueError("Groq config requires 'api_key'")
        elif provider_type == ProviderType.BEDROCK:
            if 'aws_region' not in v:
                raise ValueError("Bedrock config requires 'aws_region'")
            auth_method = v.get('auth_method', 'api_keys')
            if auth_method == 'api_keys' and 'aws_access_key_id' not in v:
                raise ValueError("Bedrock API keys auth requires 'aws_access_key_id'")
        
        return v


class ProviderConfigurationUpdate(BaseModel):
    """Request to update provider configuration."""
    name: Optional[str] = None
    is_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class ProviderConfigurationResponse(BaseModel):
    """Response model for provider configuration."""
    id: int
    customer_id: str
    provider_type: str
    name: Optional[str]
    is_enabled: bool
    is_healthy: bool
    last_health_check: Optional[datetime]
    
    # Sanitized config (no API keys)
    config_summary: Dict[str, Any] = Field(
        ...,
        description="Configuration summary without sensitive data"
    )
    
    # Available models
    available_models: List[str] = Field(default_factory=list)
    default_model: Optional[str] = None
    
    # Metadata
    created_at: datetime
    updated_at: Optional[datetime]
    error_count: int = 0
    last_error: Optional[str] = None
    
    class Config:
        from_attributes = True


class ProviderConnectionTestRequest(BaseModel):
    """Request to test provider connection."""
    test_prompt: str = Field(
        default="Hello, this is a connection test.",
        description="Prompt to use for testing"
    )


class FetchModelsRequest(BaseModel):
    """Request to fetch available models from a provider."""
    provider_type: str = Field(description="Provider type (openai, anthropic, groq, bedrock)")
    api_key: Optional[str] = Field(None, description="API key for OpenAI, Anthropic, Groq")
    organization_id: Optional[str] = Field(None, description="OpenAI organization ID")
    aws_region: Optional[str] = Field(None, description="AWS region for Bedrock")
    aws_access_key_id: Optional[str] = Field(None, description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(None, description="AWS secret access key")
    aws_session_token: Optional[str] = Field(None, description="AWS session token")


class ModelOption(BaseModel):
    """A model available from a provider."""
    name: str = Field(description="Model identifier")
    description: Optional[str] = Field(None, description="Model description")
    context_length: Optional[int] = Field(None, description="Maximum context length")
    supports_functions: Optional[bool] = Field(None, description="Supports function calling")
    supports_vision: Optional[bool] = Field(None, description="Supports vision/images")


class FetchModelsResponse(BaseModel):
    """Response with available models from a provider."""
    success: bool
    provider_type: str
    models: List[ModelOption] = Field(default_factory=list)
    error_message: Optional[str] = None


class ProviderConnectionTestResponse(BaseModel):
    """Response from provider connection test."""
    success: bool
    provider_type: str
    message: str
    response_time_ms: Optional[float] = None
    test_output: Optional[str] = None
    error_details: Optional[str] = None
    tested_at: datetime
    
    # Model used for testing
    model_tested: Optional[str] = None


class ProviderListResponse(BaseModel):
    """Response listing all provider configurations."""
    providers: List[ProviderConfigurationResponse]
    total_count: int
    by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of configurations by provider type"
    )


class AvailableProvidersResponse(BaseModel):
    """Response listing available provider types."""
    
    class ProviderTypeInfo(BaseModel):
        type: str
        name: str
        description: str
        requires_api_key: bool
        supports_models: List[str]
        auth_methods: List[str]
    
    available_providers: List[ProviderTypeInfo]


# ============================================================================
# Model Management
# ============================================================================

class AddModelRequest(BaseModel):
    """Request to add a model to provider configuration."""
    model_id: str = Field(..., description="Model identifier")
    model_name: Optional[str] = Field(None, description="Human-readable model name")
    set_as_default: bool = Field(default=False, description="Set as default model")


class RemoveModelRequest(BaseModel):
    """Request to remove a model from provider configuration."""
    model_id: str = Field(..., description="Model identifier to remove")


# ============================================================================
# Provider Metadata
# ============================================================================

PROVIDER_METADATA = {
    ProviderType.OPENAI: {
        "name": "OpenAI",
        "description": "OpenAI GPT models (GPT-5, GPT-4.1, GPT-4o, etc.)",
        "requires_api_key": True,
        "default_models": ["gpt-5", "gpt-5.2", "gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini"],
        "auth_methods": ["api_key"],
        "config_template": {
            "api_key": "sk-...",
            "organization_id": "org-...",
            "base_url": "https://api.openai.com/v1",
            "available_models": ["gpt-5", "gpt-4.1", "gpt-4o", "gpt-4o-mini"],
            "default_model": "gpt-5"
        }
    },
    ProviderType.ANTHROPIC: {
        "name": "Anthropic",
        "description": "Anthropic Claude models",
        "requires_api_key": True,
        "default_models": [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-2.1"
        ],
        "auth_methods": ["api_key"],
        "config_template": {
            "api_key": "sk-ant-...",
            "base_url": "https://api.anthropic.com",
            "available_models": ["claude-3-opus-20240229", "claude-2.1"],
            "default_model": "claude-3-opus-20240229"
        }
    },
    ProviderType.GROQ: {
        "name": "Groq",
        "description": "Groq fast inference for Llama, Mixtral, and Gemma",
        "requires_api_key": True,
        "default_models": [
            "llama-3.1-70b-versatile",
            "mixtral-8x7b-32768"
        ],
        "auth_methods": ["api_key"],
        "config_template": {
            "api_key": "gsk_...",
            "base_url": "https://api.groq.com/openai/v1",
            "available_models": ["llama-3.1-70b-versatile"],
            "default_model": "llama-3.1-70b-versatile"
        }
    },
    ProviderType.BEDROCK: {
        "name": "AWS Bedrock",
        "description": "AWS Bedrock foundation models (Claude, Llama, Titan)",
        "requires_api_key": False,
        "default_models": ["anthropic.claude-v2", "meta.llama2-70b-chat-v1"],
        "auth_methods": ["api_keys", "iam_role"],
        "config_template": {
            "auth_method": "api_keys",
            "aws_region": "us-west-2",
            "aws_access_key_id": "AKIA...",
            "aws_secret_access_key": "...",
            "available_models": [],
            "default_model": None
        }
    }
}


# ============================================================================
# Shared Provider Models (Platform Admin)
# ============================================================================

class SharedTenantInfo(BaseModel):
    """Information about a tenant a provider is shared with."""
    customer_id: str
    customer_name: str
    is_enabled: bool
    shared_at: datetime


class PlatformProviderResponse(BaseModel):
    """Extended provider response with sharing information for platform admin."""
    id: int
    customer_id: str
    provider_type: str
    name: Optional[str]
    is_enabled: bool
    is_healthy: bool
    last_health_check: Optional[datetime]
    
    # Sanitized config (no API keys)
    config_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration summary without sensitive data"
    )
    
    # Available models
    available_models: List[str] = Field(default_factory=list)
    default_model: Optional[str] = None
    
    # Sharing information
    is_global_shared: bool = False
    shared_with_tenants: List[SharedTenantInfo] = Field(default_factory=list)
    shared_with_count: int = 0
    
    # Adoption tracking
    is_adoption_source: bool = False
    chatgpt_workspace_id: Optional[str] = None
    
    # Metadata
    created_at: datetime
    updated_at: Optional[datetime]
    error_count: int = 0
    last_error: Optional[str] = None
    
    class Config:
        from_attributes = True


class PlatformProviderListResponse(BaseModel):
    """Response listing platform provider configurations with sharing info."""
    providers: List[PlatformProviderResponse]
    total_count: int
    global_count: int = 0
    shared_count: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)


class ProviderSharingUpdate(BaseModel):
    """Request to update provider sharing settings."""
    is_global_shared: Optional[bool] = Field(None, description="Make available to all tenants")
    share_with_tenant_ids: Optional[List[str]] = Field(None, description="Tenant IDs to share with")
    unshare_from_tenant_ids: Optional[List[str]] = Field(None, description="Tenant IDs to remove sharing")


class PlatformProviderCreate(BaseModel):
    """Request to create a platform provider with sharing options."""
    provider_type: ProviderType
    name: Optional[str] = None
    is_enabled: bool = True
    config: Dict[str, Any]
    
    # Sharing options
    is_global_shared: bool = Field(default=False, description="Make available to all tenants")
    share_with_tenant_ids: Optional[List[str]] = Field(None, description="Specific tenant IDs to share with")


class TenantProviderResponse(BaseModel):
    """Provider response for tenant admin (includes shared providers)."""
    id: int
    customer_id: str
    provider_type: str
    name: Optional[str]
    is_enabled: bool
    is_healthy: bool
    last_health_check: Optional[datetime]
    
    # Sanitized config
    config_summary: Dict[str, Any] = Field(default_factory=dict)
    available_models: List[str] = Field(default_factory=list)
    default_model: Optional[str] = None
    
    # Sharing info (for tenant admin view)
    is_shared_from_platform: bool = False
    is_editable: bool = True  # False if shared from platform
    
    # Adoption tracking (only for own providers, not shared)
    is_adoption_source: bool = False
    chatgpt_workspace_id: Optional[str] = None
    adoption_compliance_status: Optional[str] = None  # 'success', 'failed', 'untested'
    adoption_compliance_last_checked: Optional[datetime] = None
    adoption_compliance_error: Optional[str] = None
    
    # Metadata
    created_at: datetime
    updated_at: Optional[datetime]
    error_count: int = 0
    last_error: Optional[str] = None
    
    class Config:
        from_attributes = True


class TenantProviderListResponse(BaseModel):
    """Response listing tenant providers (including shared ones)."""
    providers: List[TenantProviderResponse]
    total_count: int
    own_count: int = 0
    shared_count: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)

