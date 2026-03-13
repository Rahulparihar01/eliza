"""
AI Enablement Platform - Model Information Data Models

Defines data models for AI model information and capabilities.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


class ModelCapability(str, Enum):
    """Model capabilities enum."""
    TEXT_GENERATION = "text_generation"
    EMBEDDINGS = "embeddings"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    CODE_GENERATION = "code_generation"


class ModelInfo(BaseModel):
    """Model information data model."""

    name: str
    provider: str
    description: Optional[str] = None
    context_length: Optional[int] = None
    input_cost_per_token: Optional[float] = None
    output_cost_per_token: Optional[float] = None
    supports_functions: bool = False
    supports_vision: bool = False

    # Additional fields for compatibility
    id: Optional[str] = None
    capabilities: List[ModelCapability] = []
    max_tokens: Optional[int] = None
    metadata: Dict[str, Any] = {}


class ProviderStatus(BaseModel):
    """Provider status data model."""

    name: str
    configured: bool
    available: bool
    models: List[ModelInfo]
    error_message: Optional[str] = None
    last_checked: Optional[Any] = None


class ModelTestRequest(BaseModel):
    """Model test request data model."""
    
    model_id: str
    prompt: str
    max_tokens: Optional[int] = 100
    temperature: Optional[float] = 0.7


class ModelTestResponse(BaseModel):
    """Model test response data model."""
    
    model_id: str
    response: str
    tokens_used: int
    response_time_ms: int
    success: bool
    error: Optional[str] = None
