"""
AI Enablement Platform - Anthropic Provider

Anthropic Claude API provider implementation.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import anthropic
from anthropic import AsyncAnthropic

from src.services.providers.base_provider import BaseProvider
from src.models.model_info import ModelInfo
from src.core.exceptions import ModelProviderError

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API provider implementation."""
    
    def __init__(self, api_key: str, customer_config):
        super().__init__(api_key, customer_config)
        self.client = AsyncAnthropic(api_key=api_key)
        self.name = "anthropic"
    
    async def test_connection(self) -> bool:
        """Test connection to Anthropic API."""
        try:
            # Simple test request
            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=5,
                messages=[{"role": "user", "content": "Hello"}]
            )
            return True
        except Exception as e:
            logger.error(f"Anthropic connection test failed: {e}")
            return False
    
    async def get_available_models(self) -> List[ModelInfo]:
        """Get list of available Anthropic models."""
        try:
            models = [
                ModelInfo(
                    name="claude-3-5-sonnet-20241022",
                    provider="anthropic",
                    description="Most intelligent Claude model with enhanced capabilities",
                    context_length=200000,
                    input_cost_per_token=0.000003,
                    output_cost_per_token=0.000015,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="claude-3-5-sonnet-20240620",
                    provider="anthropic",
                    description="Previous version of Claude 3.5 Sonnet",
                    context_length=200000,
                    input_cost_per_token=0.000003,
                    output_cost_per_token=0.000015,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="claude-3-opus-20240229",
                    provider="anthropic",
                    description="Most powerful Claude model for complex tasks",
                    context_length=200000,
                    input_cost_per_token=0.000015,
                    output_cost_per_token=0.000075,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="claude-3-sonnet-20240229",
                    provider="anthropic",
                    description="Balanced Claude model for most tasks",
                    context_length=200000,
                    input_cost_per_token=0.000003,
                    output_cost_per_token=0.000015,
                    supports_functions=True,
                    supports_vision=True
                ),
                ModelInfo(
                    name="claude-3-haiku-20240307",
                    provider="anthropic",
                    description="Fastest Claude model for simple tasks",
                    context_length=200000,
                    input_cost_per_token=0.00000025,
                    output_cost_per_token=0.00000125,
                    supports_functions=True,
                    supports_vision=True
                )
            ]
            
            return models
        
        except Exception as e:
            logger.error(f"Failed to get Anthropic models: {e}")
            return []
    
    async def generate_text(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text using Anthropic API."""
        try:
            # Prepare messages
            messages = [{"role": "user", "content": prompt}]
            
            # Handle system message
            system_message = kwargs.pop("system_message", None)
            
            # Make API request
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                system=system_message,
                **kwargs
            )
            
            # Extract response data
            text = ""
            for content in response.content:
                if content.type == "text":
                    text += content.text
            
            # Calculate tokens used
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            
            return self._format_response(
                text=text,
                model=model,
                tokens_used=tokens_used,
                finish_reason=response.stop_reason,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )
        
        except anthropic.RateLimitError as e:
            raise ModelProviderError(f"Anthropic rate limit exceeded: {e}", "anthropic")
        except anthropic.AuthenticationError as e:
            raise ModelProviderError(f"Anthropic authentication failed: {e}", "anthropic")
        except anthropic.APIError as e:
            raise ModelProviderError(f"Anthropic API error: {e}", "anthropic")
        except Exception as e:
            self._handle_error(e, "text generation")
    
    async def generate_embeddings(
        self,
        model: str,
        texts: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate embeddings using Anthropic API."""
        # Note: Anthropic doesn't provide embedding models directly
        # This is a placeholder for potential future embedding support
        # or integration with other embedding providers
        raise ModelProviderError(
            "Anthropic does not provide embedding models. Use OpenAI or other providers for embeddings.",
            "anthropic"
        )
    
    async def generate_with_tools(
        self,
        model: str,
        prompt: str,
        tools: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text with tool calling support (Anthropic's function calling)."""
        try:
            messages = [{"role": "user", "content": prompt}]
            
            system_message = kwargs.pop("system_message", None)
            
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                tools=tools,
                system=system_message,
                **kwargs
            )
            
            # Extract response data
            text = ""
            tool_calls = []
            
            for content in response.content:
                if content.type == "text":
                    text += content.text
                elif content.type == "tool_use":
                    tool_calls.append({
                        "id": content.id,
                        "name": content.name,
                        "input": content.input
                    })
            
            result = self._format_response(
                text=text,
                model=model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                finish_reason=response.stop_reason,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )
            
            # Add tool calls if present
            if tool_calls:
                result["tool_calls"] = tool_calls
            
            return result
        
        except Exception as e:
            self._handle_error(e, "tool calling")
    
    def get_model_context_length(self, model: str) -> int:
        """Get context length for a specific model."""
        # All current Claude 3 models have 200k context length
        context_lengths = {
            "claude-3-5-sonnet-20241022": 200000,
            "claude-3-5-sonnet-20240620": 200000,
            "claude-3-opus-20240229": 200000,
            "claude-3-sonnet-20240229": 200000,
            "claude-3-haiku-20240307": 200000,
        }
        return context_lengths.get(model, 200000)  # Default to 200k for Claude models
    
    def _convert_openai_functions_to_tools(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI function format to Anthropic tools format."""
        tools = []
        for func in functions:
            tool = {
                "name": func["name"],
                "description": func["description"],
                "input_schema": func["parameters"]
            }
            tools.append(tool)
        return tools
