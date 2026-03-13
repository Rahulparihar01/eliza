"""
AI Enablement Platform - Base Provider

Abstract base class for AI model providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

from src.models.model_info import ModelInfo
from src.core.config import CustomerConfig

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """Abstract base class for AI model providers."""
    
    def __init__(self, api_key: str, customer_config: CustomerConfig):
        self.api_key = api_key
        self.customer_config = customer_config
        self.name = self.__class__.__name__.replace("Provider", "").lower()
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to the provider."""
        pass
    
    @abstractmethod
    async def get_available_models(self) -> List[ModelInfo]:
        """Get list of available models from the provider."""
        pass
    
    @abstractmethod
    async def generate_text(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text using the specified model."""
        pass
    
    @abstractmethod
    async def generate_embeddings(
        self,
        model: str,
        texts: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate embeddings for the given texts."""
        pass
    
    def _format_response(
        self,
        text: str,
        model: str,
        tokens_used: Optional[int] = None,
        finish_reason: Optional[str] = None,
        **metadata
    ) -> Dict[str, Any]:
        """Format provider response in a standard format."""
        return {
            "text": text,
            "model": model,
            "provider": self.name,
            "tokens_used": tokens_used,
            "finish_reason": finish_reason,
            "metadata": metadata
        }
    
    def _handle_error(self, error: Exception, operation: str) -> None:
        """Handle and log provider errors."""
        logger.error(f"{self.name} provider error during {operation}: {error}")
        raise error
