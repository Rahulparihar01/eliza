"""
AI Enablement Platform - Groq Provider

Groq API provider implementation for fast inference.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import httpx

from src.services.providers.base_provider import BaseProvider
from src.models.model_info import ModelInfo
from src.core.exceptions import ModelProviderError

logger = logging.getLogger(__name__)


class GroqProvider(BaseProvider):
    """Groq API provider implementation."""
    
    def __init__(self, api_key: str, customer_config):
        super().__init__(api_key, customer_config)
        self.base_url = "https://api.groq.com/openai/v1"
        self.name = "groq"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def test_connection(self) -> bool:
        """Test connection to Groq API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": "llama2-70b-4096",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "max_tokens": 5
                    },
                    timeout=30.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Groq connection test failed: {e}")
            return False
    
    async def get_available_models(self) -> List[ModelInfo]:
        """Get list of available Groq models."""
        try:
            models = [
                ModelInfo(
                    name="llama2-70b-4096",
                    provider="groq",
                    description="Llama 2 70B model optimized for speed",
                    context_length=4096,
                    input_cost_per_token=0.0000007,
                    output_cost_per_token=0.0000008,
                    supports_functions=False,
                    supports_vision=False
                ),
                ModelInfo(
                    name="mixtral-8x7b-32768",
                    provider="groq",
                    description="Mixtral 8x7B model with large context",
                    context_length=32768,
                    input_cost_per_token=0.00000027,
                    output_cost_per_token=0.00000027,
                    supports_functions=False,
                    supports_vision=False
                ),
                ModelInfo(
                    name="llama3-8b-8192",
                    provider="groq",
                    description="Llama 3 8B model for general tasks",
                    context_length=8192,
                    input_cost_per_token=0.00000005,
                    output_cost_per_token=0.00000008,
                    supports_functions=False,
                    supports_vision=False
                ),
                ModelInfo(
                    name="llama3-70b-8192",
                    provider="groq",
                    description="Llama 3 70B model for complex tasks",
                    context_length=8192,
                    input_cost_per_token=0.00000059,
                    output_cost_per_token=0.00000079,
                    supports_functions=False,
                    supports_vision=False
                ),
                ModelInfo(
                    name="gemma-7b-it",
                    provider="groq",
                    description="Google Gemma 7B instruction-tuned model",
                    context_length=8192,
                    input_cost_per_token=0.00000007,
                    output_cost_per_token=0.00000007,
                    supports_functions=False,
                    supports_vision=False
                )
            ]
            
            return models
        
        except Exception as e:
            logger.error(f"Failed to get Groq models: {e}")
            return []
    
    async def generate_text(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text using Groq API."""
        try:
            # Prepare messages
            messages = [{"role": "user", "content": prompt}]
            
            # Handle system message if provided
            if "system_message" in kwargs:
                messages.insert(0, {"role": "system", "content": kwargs["system_message"]})
            
            # Prepare request payload
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }
            
            # Add other supported parameters
            for key in ["top_p", "frequency_penalty", "presence_penalty", "stop"]:
                if key in kwargs:
                    payload[key] = kwargs[key]
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    error_detail = response.text
                    raise ModelProviderError(
                        f"Groq API error (status {response.status_code}): {error_detail}",
                        "groq"
                    )
                
                data = response.json()
                
                # Extract response data
                choice = data["choices"][0]
                text = choice["message"]["content"]
                finish_reason = choice["finish_reason"]
                
                # Calculate tokens used
                usage = data.get("usage", {})
                tokens_used = usage.get("total_tokens")
                
                return self._format_response(
                    text=text,
                    model=model,
                    tokens_used=tokens_used,
                    finish_reason=finish_reason,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens")
                )
        
        except httpx.TimeoutException:
            raise ModelProviderError("Groq API request timeout", "groq")
        except httpx.HTTPStatusError as e:
            raise ModelProviderError(f"Groq API HTTP error: {e}", "groq")
        except Exception as e:
            self._handle_error(e, "text generation")
    
    async def generate_embeddings(
        self,
        model: str,
        texts: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate embeddings using Groq API."""
        # Note: Groq doesn't provide embedding models directly
        # This is a placeholder for potential future embedding support
        raise ModelProviderError(
            "Groq does not provide embedding models. Use OpenAI or other providers for embeddings.",
            "groq"
        )
    
    async def get_models_list(self) -> List[Dict[str, Any]]:
        """Get list of models from Groq API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                else:
                    logger.warning(f"Failed to fetch Groq models list: {response.status_code}")
                    return []
        
        except Exception as e:
            logger.error(f"Error fetching Groq models list: {e}")
            return []
    
    def get_model_context_length(self, model: str) -> int:
        """Get context length for a specific model."""
        context_lengths = {
            "llama2-70b-4096": 4096,
            "mixtral-8x7b-32768": 32768,
            "llama3-8b-8192": 8192,
            "llama3-70b-8192": 8192,
            "gemma-7b-it": 8192,
        }
        return context_lengths.get(model, 4096)  # Default fallback
    
    def _handle_rate_limit(self, response: httpx.Response) -> None:
        """Handle rate limit responses from Groq."""
        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            error_msg = f"Groq rate limit exceeded"
            if retry_after:
                error_msg += f". Retry after {retry_after} seconds"
            raise ModelProviderError(error_msg, "groq")
    
    def _parse_error_response(self, response: httpx.Response) -> str:
        """Parse error response from Groq API."""
        try:
            error_data = response.json()
            if "error" in error_data:
                error_info = error_data["error"]
                if isinstance(error_info, dict):
                    return error_info.get("message", str(error_info))
                return str(error_info)
            return response.text
        except Exception:
            return response.text
