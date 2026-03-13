"""
AI Enablement Platform - AWS Bedrock Configuration Models

Pydantic models for AWS Bedrock provider configuration.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime


class BedrockAuthMethod(str):
    """Authentication methods for Bedrock."""
    API_KEYS = "api_keys"
    IAM_ROLE = "iam_role"


class BedrockModelInfo(BaseModel):
    """Information about a Bedrock model."""
    model_id: str = Field(..., description="Bedrock model identifier (e.g., 'anthropic.claude-v2')")
    model_name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="Model provider (e.g., 'anthropic', 'meta', 'amazon')")
    is_enabled: bool = Field(default=True, description="Whether this model is enabled for use")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens supported by the model")
    supports_streaming: bool = Field(default=True, description="Whether the model supports streaming")
    
    class Config:
        json_schema_extra = {
            "example": {
                "model_id": "anthropic.claude-v2",
                "model_name": "Claude 2",
                "provider": "anthropic",
                "is_enabled": True,
                "max_tokens": 100000,
                "supports_streaming": True
            }
        }


class BedrockConfiguration(BaseModel):
    """AWS Bedrock provider configuration."""
    
    # Authentication
    auth_method: str = Field(
        default=BedrockAuthMethod.API_KEYS,
        description="Authentication method: 'api_keys' or 'iam_role'"
    )
    aws_access_key_id: Optional[str] = Field(
        None,
        description="AWS Access Key ID (encrypted in database, required if auth_method='api_keys')"
    )
    aws_secret_access_key: Optional[str] = Field(
        None,
        description="AWS Secret Access Key (encrypted in database, required if auth_method='api_keys')"
    )
    aws_session_token: Optional[str] = Field(
        None,
        description="AWS Session Token (optional, for temporary credentials)"
    )
    
    # Region and endpoint
    aws_region: str = Field(
        default="us-west-2",
        description="AWS region for Bedrock service"
    )
    base_url: Optional[str] = Field(
        None,
        description="Bedrock API base URL (auto-generated from region if not provided)"
    )
    
    # Model configuration
    available_models: List[BedrockModelInfo] = Field(
        default_factory=list,
        description="List of available models in this Bedrock configuration"
    )
    default_model: Optional[str] = Field(
        None,
        description="Default model ID to use if none specified"
    )
    
    # Connection settings
    connection_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Connection timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts"
    )
    
    @model_validator(mode='after')
    def generate_base_url_and_validate(self):
        """Auto-generate base URL if not provided and validate API keys."""
        # Auto-generate base URL if not provided
        if not self.base_url and self.aws_region:
            self.base_url = f"https://bedrock-runtime.{self.aws_region}.amazonaws.com/openai/v1"
        
        # Validate API keys when using api_keys auth method
        if self.auth_method == BedrockAuthMethod.API_KEYS:
            if not self.aws_access_key_id:
                raise ValueError("aws_access_key_id is required when auth_method is 'api_keys'")
            if not self.aws_secret_access_key:
                raise ValueError("aws_secret_access_key is required when auth_method is 'api_keys'")
        
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "auth_method": "api_keys",
                "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                "aws_region": "us-west-2",
                "available_models": [
                    {
                        "model_id": "anthropic.claude-v2",
                        "model_name": "Claude 2",
                        "provider": "anthropic",
                        "is_enabled": True,
                        "max_tokens": 100000
                    }
                ],
                "default_model": "anthropic.claude-v2",
                "connection_timeout": 30,
                "max_retries": 3
            }
        }


class BedrockConfigurationCreate(BaseModel):
    """Request model for creating a Bedrock configuration."""
    auth_method: str = Field(default=BedrockAuthMethod.API_KEYS)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_region: str = Field(default="us-west-2")
    base_url: Optional[str] = Field(
        None,
        description="Override Bedrock API base URL (e.g. VPC endpoint). If unset, derived from aws_region."
    )
    connection_timeout: int = Field(default=30, ge=5, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)


class BedrockConfigurationUpdate(BaseModel):
    """Request model for updating a Bedrock configuration."""
    auth_method: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_region: Optional[str] = None
    base_url: Optional[str] = Field(
        None,
        description="Override Bedrock API base URL (e.g. VPC endpoint). Set to empty string to revert to region-derived URL."
    )
    connection_timeout: Optional[int] = Field(None, ge=5, le=300)
    max_retries: Optional[int] = Field(None, ge=0, le=10)


class BedrockConfigurationResponse(BaseModel):
    """Response model for Bedrock configuration."""
    id: int
    customer_id: str
    auth_method: str
    aws_region: str
    base_url: str
    available_models: List[BedrockModelInfo]
    default_model: Optional[str]
    is_enabled: bool
    is_healthy: bool
    last_health_check: Optional[datetime]
    connection_timeout: int
    max_retries: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class BedrockModelDiscoveryResponse(BaseModel):
    """Response model for Bedrock model discovery."""
    region: str
    discovered_models: List[BedrockModelInfo]
    total_count: int
    discovery_timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "region": "us-west-2",
                "discovered_models": [
                    {
                        "model_id": "anthropic.claude-v2",
                        "model_name": "Claude 2",
                        "provider": "anthropic",
                        "is_enabled": False,
                        "max_tokens": 100000
                    }
                ],
                "total_count": 15,
                "discovery_timestamp": "2025-01-08T12:00:00Z"
            }
        }


class AddBedrockModelRequest(BaseModel):
    """Request model for adding a model to Bedrock configuration."""
    model_id: str = Field(..., description="Bedrock model ID to add")
    model_name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="Model provider")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens")
    supports_streaming: bool = Field(default=True)
    set_as_default: bool = Field(
        default=False,
        description="Set this as the default model for this configuration"
    )


class BedrockConnectionTestResponse(BaseModel):
    """Response model for Bedrock connection test."""
    success: bool
    message: str
    region: str
    auth_method: str
    response_time_ms: Optional[float] = None
    error_details: Optional[str] = None
    tested_at: datetime

