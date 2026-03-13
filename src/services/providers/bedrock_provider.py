"""
AI Enablement Platform - AWS Bedrock Provider

AWS Bedrock provider using OpenAI-compatible API.
Supports both API key authentication and IAM role authentication.

Terraform alignment: Use auth_method=iam_role and (optional) base_url for a VPC
endpoint so generation uses Terraform-provisioned IAM and private connectivity.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI, AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai._streaming import Stream
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from src.services.providers.base_provider import BaseProvider
from src.models.model_info import ModelInfo
from src.models.bedrock_config import BedrockModelInfo, BedrockAuthMethod
from src.core.config import CustomerConfig

logger = logging.getLogger(__name__)


def _bedrock_message_content(content: Any) -> List[Dict[str, Any]]:
    """Convert content to Bedrock OpenAI-compatible format (JSONArray of content blocks)."""
    if isinstance(content, list):
        return content
    # Bedrock expects blocks with "text" only; "type" is not permitted
    return [{"text": str(content)}]


class BedrockProvider(BaseProvider):
    """
    AWS Bedrock provider using OpenAI-compatible API.
    
    Supports two authentication methods:
    1. API Keys (aws_access_key_id + aws_secret_access_key)
    2. IAM Role (uses default AWS credential chain)
    """
    
    def __init__(
        self,
        aws_region: str = "us-west-2",
        auth_method: str = BedrockAuthMethod.API_KEYS,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        bedrock_api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        available_models: Optional[List[BedrockModelInfo]] = None,
        connection_timeout: int = 30,
        max_retries: int = 3,
        customer_config: Optional[CustomerConfig] = None,
        **kwargs
    ):
        """
        Initialize Bedrock provider.

        Args:
            aws_region: AWS region for Bedrock service
            auth_method: Authentication method ('api_keys' or 'iam_role')
            aws_access_key_id: AWS Access Key ID (for boto3 / SigV4; not used by OpenAI client)
            aws_secret_access_key: AWS Secret Access Key (for boto3 / SigV4)
            aws_session_token: AWS Session Token (optional, for temporary credentials)
            bedrock_api_key: Amazon Bedrock API key (bearer token) for OpenAI-compatible API.
                Required when using the OpenAI SDK against Bedrock. Set e.g. from AWS_BEARER_TOKEN_BEDROCK.
            base_url: Bedrock API base URL (auto-generated if not provided)
            available_models: List of available models
            connection_timeout: Connection timeout in seconds
            max_retries: Maximum retry attempts
            customer_config: Customer configuration
        """
        # Store configuration
        self.aws_region = aws_region
        self.auth_method = auth_method
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_session_token = aws_session_token
        self.bedrock_api_key = bedrock_api_key
        self.connection_timeout = connection_timeout
        self.max_retries = max_retries
        self.available_models = available_models or []

        # Generate base URL if not provided
        if not base_url:
            base_url = f"https://bedrock-runtime.{aws_region}.amazonaws.com/openai/v1"
        self.base_url = base_url

        # OpenAI-compatible API requires an Amazon Bedrock API key (bearer token), not AWS_ACCESS_KEY_ID.
        # See: https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions.html
        api_key_for_openai = bedrock_api_key if bedrock_api_key else "bedrock"

        self.client = OpenAI(
            api_key=api_key_for_openai,
            base_url=self.base_url,
            timeout=connection_timeout,
            max_retries=max_retries
        )

        self.async_client = AsyncOpenAI(
            api_key=api_key_for_openai,
            base_url=self.base_url,
            timeout=connection_timeout,
            max_retries=max_retries
        )

        super().__init__(api_key=api_key_for_openai, customer_config=customer_config)
        self.name = "bedrock"
        
        logger.info(
            f"Initialized Bedrock provider: region={aws_region}, "
            f"auth_method={auth_method}, models_count={len(self.available_models)}"
        )
    
    def _get_boto3_client(self):
        """
        Get boto3 Bedrock client with appropriate authentication.
        
        Returns:
            boto3 client for Bedrock service
        """
        if self.auth_method == BedrockAuthMethod.IAM_ROLE:
            # Use default credential chain (IAM role, env vars, etc.)
            client = boto3.client(
                'bedrock-runtime',
                region_name=self.aws_region
            )
            logger.debug(f"Created Bedrock boto3 client using IAM role for region {self.aws_region}")
        else:
            # Use explicit credentials
            session_kwargs = {
                'aws_access_key_id': self.aws_access_key_id,
                'aws_secret_access_key': self.aws_secret_access_key,
                'region_name': self.aws_region
            }
            if self.aws_session_token:
                session_kwargs['aws_session_token'] = self.aws_session_token
            
            client = boto3.client('bedrock-runtime', **session_kwargs)
            logger.debug(f"Created Bedrock boto3 client using API keys for region {self.aws_region}")
        
        return client
    
    async def test_connection(self) -> bool:
        """
        Test connection to Bedrock.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Get first available model or use a default
            test_model = None
            if self.available_models:
                for model in self.available_models:
                    if model.is_enabled:
                        test_model = model.model_id
                        break
            
            if not test_model:
                # Use a common Bedrock model for testing
                test_model = "anthropic.claude-instant-v1"
                logger.warning(
                    f"No enabled models configured for testing, using default: {test_model}"
                )
            
            # Bedrock uses X-Amzn-Bedrock-Model header; include model in body for OpenAI client validation
            body = {
                "model": test_model,
                "messages": [{"role": "user", "content": _bedrock_message_content("test")}],
                "max_tokens": 5,
            }
            response = await asyncio.to_thread(
                self.client.post,
                "/chat/completions",
                body=body,
                cast_to=ChatCompletion,
                options={"headers": {"X-Amzn-Bedrock-Model": test_model}},
            )
            
            logger.info(f"Bedrock connection test successful with model: {test_model}")
            return True
            
        except Exception as e:
            msg = str(e)
            err_type = type(e).__name__
            cause = getattr(e, "__cause__", None)
            if cause:
                logger.error(
                    "Bedrock connection test failed: %s (%s). Cause: %s (%s)",
                    msg,
                    err_type,
                    cause,
                    type(cause).__name__,
                    exc_info=True,
                )
            else:
                logger.error(
                    "Bedrock connection test failed: %s (%s)",
                    msg,
                    err_type,
                    exc_info=True,
                )
            return False
    
    async def get_available_models(self) -> List[ModelInfo]:
        """
        Get list of available models from configuration.
        
        Note: This returns models from the configuration, not live discovery.
        Use the boto3 discovery service for live model discovery.
        
        Returns:
            List of ModelInfo objects
        """
        model_infos = []
        
        for bedrock_model in self.available_models:
            if bedrock_model.is_enabled:
                model_info = ModelInfo(
                    id=bedrock_model.model_id,
                    name=bedrock_model.model_name,
                    provider="bedrock",
                    supports_completion=True,
                    supports_embeddings=False,  # Bedrock embeddings use different API
                    max_tokens=bedrock_model.max_tokens or 4096,
                    description=f"AWS Bedrock model from {bedrock_model.provider}"
                )
                model_infos.append(model_info)
        
        logger.debug(f"Returning {len(model_infos)} available Bedrock models")
        return model_infos
    
    async def generate_text(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text using Bedrock model via OpenAI-compatible API.
        
        Args:
            model: Bedrock model ID
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters
        
        Returns:
            Formatted response dictionary
        """
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=model,
                messages=[{"role": "user", "content": _bedrock_message_content(prompt)}],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            # Extract response
            text = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            tokens_used = getattr(response.usage, 'total_tokens', None) if hasattr(response, 'usage') else None
            
            logger.info(
                f"Bedrock text generation successful: model={model}, "
                f"tokens={tokens_used}, finish_reason={finish_reason}"
            )
            
            return self._format_response(
                text=text,
                model=model,
                tokens_used=tokens_used,
                finish_reason=finish_reason,
                region=self.aws_region
            )
            
        except Exception as e:
            logger.error(f"Bedrock text generation failed: {str(e)}")
            self._handle_error(e, "generate_text")
    
    async def generate_embeddings(
        self,
        model: str,
        texts: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate embeddings using Bedrock.
        
        Note: Bedrock embeddings may not be available via OpenAI-compatible API.
        This method is a placeholder for future implementation.
        
        Args:
            model: Embedding model ID
            texts: List of texts to embed
            **kwargs: Additional parameters
        
        Returns:
            Formatted response with embeddings
        
        Raises:
            NotImplementedError: Bedrock embeddings not yet implemented
        """
        raise NotImplementedError(
            "Bedrock embeddings via OpenAI-compatible API not yet implemented. "
            "Use native boto3 Bedrock API for embeddings."
        )
    
    async def stream_generate_text(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ):
        """
        Stream text generation from Bedrock model.
        
        Args:
            model: Bedrock model ID
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters
        
        Yields:
            Chunks of generated text
        """
        try:
            stream = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=model,
                messages=[{"role": "user", "content": _bedrock_message_content(prompt)}],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                **kwargs
            )
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Bedrock streaming failed: {str(e)}")
            self._handle_error(e, "stream_generate_text")
    
    def get_credentials_info(self) -> Dict[str, Any]:
        """
        Get information about configured credentials (for debugging).
        
        Returns:
            Dictionary with credential info (no sensitive data)
        """
        return {
            "auth_method": self.auth_method,
            "aws_region": self.aws_region,
            "base_url": self.base_url,
            "has_access_key": bool(self.aws_access_key_id),
            "has_secret_key": bool(self.aws_secret_access_key),
            "has_session_token": bool(self.aws_session_token),
            "models_count": len(self.available_models)
        }

