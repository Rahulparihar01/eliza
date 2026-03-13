"""
AI Enablement Platform - OpenAI Provider

OpenAI API provider implementation.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import openai
from openai import AsyncOpenAI

from src.services.providers.base_provider import BaseProvider
from src.models.model_info import ModelInfo
from src.core.exceptions import ModelProviderError

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI API provider implementation."""
    
    def __init__(self, api_key: str, customer_config):
        super().__init__(api_key, customer_config)
        self.client = AsyncOpenAI(api_key=api_key)
        self.name = "openai"
    
    async def test_connection(self) -> bool:
        """Test connection to OpenAI API."""
        try:
            # Simple test request
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            return False
    
    async def get_available_models(self) -> List[ModelInfo]:
        """Get list of available OpenAI models."""
        try:
            # Define commonly used OpenAI models with their specifications
            models = [
                # GPT-5 family
                ModelInfo(
                    name="gpt-5",
                    provider="openai",
                    description="Most capable GPT-5 model",
                    context_length=128000,
                    input_cost_per_token=0.000005,
                    output_cost_per_token=0.000015,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="gpt-5.2",
                    provider="openai",
                    description="GPT-5.2 with enhanced reasoning",
                    context_length=128000,
                    input_cost_per_token=0.000005,
                    output_cost_per_token=0.000015,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="gpt-5-mini",
                    provider="openai",
                    description="Fast, efficient GPT-5 model",
                    context_length=128000,
                    input_cost_per_token=0.0000003,
                    output_cost_per_token=0.0000012,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="gpt-5-nano",
                    provider="openai",
                    description="Smallest, cheapest GPT-5 model for lightweight tasks",
                    context_length=128000,
                    input_cost_per_token=0.0000001,
                    output_cost_per_token=0.0000004,
                    supports_functions=True,
                    supports_vision=False
                ),
                # GPT-4.1 family
                ModelInfo(
                    name="gpt-4.1",
                    provider="openai",
                    description="GPT-4.1 with improved coding and instruction following",
                    context_length=1047576,
                    input_cost_per_token=0.000002,
                    output_cost_per_token=0.000008,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="gpt-4.1-mini",
                    provider="openai",
                    description="Balanced GPT-4.1 model for most tasks",
                    context_length=1047576,
                    input_cost_per_token=0.0000004,
                    output_cost_per_token=0.0000016,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="gpt-4.1-nano",
                    provider="openai",
                    description="Fastest, cheapest GPT-4.1 model for simple tasks",
                    context_length=1047576,
                    input_cost_per_token=0.0000001,
                    output_cost_per_token=0.0000004,
                    supports_functions=True,
                    supports_vision=True
                ),
                # GPT-4o family
                ModelInfo(
                    name="gpt-4o",
                    provider="openai",
                    description="GPT-4o with vision capabilities",
                    context_length=128000,
                    input_cost_per_token=0.0000025,
                    output_cost_per_token=0.00001,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="gpt-4o-mini",
                    provider="openai",
                    description="Faster, cheaper GPT-4o model",
                    context_length=128000,
                    input_cost_per_token=0.00000015,
                    output_cost_per_token=0.0000006,
                    supports_functions=True,
                    supports_vision=True
                ),
                # Embeddings
                ModelInfo(
                    name="text-embedding-3-large",
                    provider="openai",
                    description="Most capable embedding model",
                    context_length=8191,
                    input_cost_per_token=0.00000013,
                    supports_functions=False,
                    supports_vision=False
                ),
                ModelInfo(
                    name="text-embedding-3-small",
                    provider="openai",
                    description="Efficient embedding model",
                    context_length=8191,
                    input_cost_per_token=0.00000002,
                    supports_functions=False,
                    supports_vision=False
                ),
            ]
            
            return models
        
        except Exception as e:
            logger.error(f"Failed to get OpenAI models: {e}")
            return []
    
    async def generate_text(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text using OpenAI API."""
        try:
            # Prepare messages
            messages = [{"role": "user", "content": prompt}]
            
            # Handle system message if provided
            if "system_message" in kwargs:
                messages.insert(0, {"role": "system", "content": kwargs["system_message"]})
            
            # Make API request
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **{k: v for k, v in kwargs.items() if k not in ["system_message"]}
            )
            
            # Extract response data
            choice = response.choices[0]
            text = choice.message.content
            finish_reason = choice.finish_reason
            
            # Calculate tokens used
            tokens_used = response.usage.total_tokens if response.usage else None
            
            return self._format_response(
                text=text,
                model=model,
                tokens_used=tokens_used,
                finish_reason=finish_reason,
                prompt_tokens=response.usage.prompt_tokens if response.usage else None,
                completion_tokens=response.usage.completion_tokens if response.usage else None
            )
        
        except openai.RateLimitError as e:
            raise ModelProviderError(f"OpenAI rate limit exceeded: {e}", "openai")
        except openai.AuthenticationError as e:
            raise ModelProviderError(f"OpenAI authentication failed: {e}", "openai")
        except openai.APIError as e:
            raise ModelProviderError(f"OpenAI API error: {e}", "openai")
        except Exception as e:
            self._handle_error(e, "text generation")
    
    async def generate_embeddings(
        self,
        model: str,
        texts: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate embeddings using OpenAI API."""
        try:
            response = await self.client.embeddings.create(
                model=model,
                input=texts,
                **kwargs
            )
            
            # Extract embeddings
            embeddings = [item.embedding for item in response.data]
            
            # Calculate tokens used
            tokens_used = response.usage.total_tokens if response.usage else None
            
            return {
                "embeddings": embeddings,
                "model": model,
                "provider": self.name,
                "tokens_used": tokens_used,
                "dimensions": len(embeddings[0]) if embeddings else 0,
                "count": len(embeddings)
            }
        
        except openai.RateLimitError as e:
            raise ModelProviderError(f"OpenAI rate limit exceeded: {e}", "openai")
        except openai.AuthenticationError as e:
            raise ModelProviderError(f"OpenAI authentication failed: {e}", "openai")
        except openai.APIError as e:
            raise ModelProviderError(f"OpenAI API error: {e}", "openai")
        except Exception as e:
            self._handle_error(e, "embedding generation")
    
    async def generate_with_functions(
        self,
        model: str,
        prompt: str,
        functions: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text with function calling support."""
        try:
            messages = [{"role": "user", "content": prompt}]
            
            if "system_message" in kwargs:
                messages.insert(0, {"role": "system", "content": kwargs["system_message"]})
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                functions=functions,
                max_tokens=max_tokens,
                temperature=temperature,
                **{k: v for k, v in kwargs.items() if k not in ["system_message"]}
            )
            
            choice = response.choices[0]
            message = choice.message
            
            result = self._format_response(
                text=message.content or "",
                model=model,
                tokens_used=response.usage.total_tokens if response.usage else None,
                finish_reason=choice.finish_reason
            )
            
            # Add function call information if present
            if message.function_call:
                result["function_call"] = {
                    "name": message.function_call.name,
                    "arguments": message.function_call.arguments
                }
            
            return result
        
        except Exception as e:
            self._handle_error(e, "function calling")
    
    def get_model_context_length(self, model: str) -> int:
        """Get context length for a specific model."""
        context_lengths = {
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-4-turbo": 128000,
            "gpt-4": 8192,
            "gpt-3.5-turbo": 16385,
            "text-embedding-3-large": 8191,
            "text-embedding-3-small": 8191,
            "text-embedding-ada-002": 8191
        }
        return context_lengths.get(model, 4096)  # Default fallback
