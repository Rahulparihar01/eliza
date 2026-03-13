"""
AI Enablement Platform - Unified Provider Configuration Service

Service for managing AI provider configurations across all provider types.
Handles CRUD operations, credential encryption, and provider initialization.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.exceptions import ConfigurationError
from src.models.bedrock_config import BedrockModelInfo
from src.models.customer import CustomerAIProvider
from src.models.model_info import ModelInfo
from src.models.provider_config import (
    PROVIDER_METADATA,
    ProviderConfigurationCreate,
    ProviderConfigurationUpdate,
    ProviderConnectionTestResponse,
    ProviderType,
)
from src.services.base_service import BaseService
from src.services.bedrock_model_utils import normalize_bedrock_models
from src.services.providers.anthropic_provider import AnthropicProvider
from src.services.providers.bedrock_provider import BedrockProvider
from src.services.providers.groq_provider import GroqProvider
from src.services.providers.openai_provider import OpenAIProvider
from src.utils.encryption import EncryptionError, decrypt_value, encrypt_value

logger = logging.getLogger(__name__)


class ProviderService(BaseService):
    """
    Unified service for managing AI provider configurations.

    Handles all provider types: OpenAI, Anthropic, Groq, Bedrock, etc.
    Provides consistent CRUD operations, credential encryption, and testing.
    """

    # Map provider types to their provider classes
    PROVIDER_CLASSES = {
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.ANTHROPIC: AnthropicProvider,
        ProviderType.GROQ: GroqProvider,
        ProviderType.BEDROCK: BedrockProvider,
    }

    def __init__(self, db: Session):
        """Initialize provider service with database session."""
        self.db = db

    def create_provider_config(
        self, customer_id: str, config_request: ProviderConfigurationCreate
    ) -> CustomerAIProvider:
        """
        Create a new provider configuration for a customer.

        Args:
            customer_id: Customer identifier
            config_request: Provider configuration request

        Returns:
            Created CustomerAIProvider instance

        Raises:
            ConfigurationError: If validation fails
        """
        try:
            provider_type = config_request.provider_type
            config_data = config_request.config

            # Validate provider type
            if provider_type not in self.PROVIDER_CLASSES:
                raise ConfigurationError(f"Unsupported provider type: {provider_type}")

            # Extract and encrypt sensitive credentials
            encrypted_credentials = self._encrypt_credentials(provider_type, config_data)

            # Remove sensitive data from config_data
            sanitized_config = self._sanitize_config(provider_type, config_data)

            # Add provider-type-specific defaults
            sanitized_config = self._apply_defaults(provider_type, sanitized_config)

            # Handle adoption tracking (disable others if enabling this one)
            is_adoption = getattr(config_request, "is_adoption_source", False)
            chatgpt_workspace = getattr(config_request, "chatgpt_workspace_id", None)

            if is_adoption and provider_type.value == "openai":
                # Disable adoption on other OpenAI providers for this customer
                self.db.query(CustomerAIProvider).filter(
                    CustomerAIProvider.customer_id == customer_id,
                    CustomerAIProvider.provider_name == "openai",
                    CustomerAIProvider.is_adoption_source == True,
                ).update({"is_adoption_source": False}, synchronize_session=False)

            # Create CustomerAIProvider record
            provider = CustomerAIProvider(
                customer_id=customer_id,
                provider_name=provider_type.value,
                name=config_request.name,  # User-friendly name
                is_enabled=config_request.is_enabled,
                api_key_encrypted=encrypted_credentials,
                config_data=sanitized_config,
                priority=self._get_default_priority(provider_type),
                max_requests_per_minute=60,
                max_tokens_per_request=100000,
                is_healthy=False,
                last_health_check=None,
                error_count=0,
                is_adoption_source=is_adoption if provider_type.value == "openai" else False,
                chatgpt_workspace_id=chatgpt_workspace if provider_type.value == "openai" else None,
            )

            self.db.add(provider)
            self.db.commit()
            self.db.refresh(provider)

            logger.info(
                f"Created {provider_type.value} configuration for customer {customer_id}: "
                f"config_id={provider.id}"
            )

            return provider

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Provider configuration already exists: {e!s}")
            raise ConfigurationError(
                f"{provider_type.value} configuration already exists for customer"
            ) from e

        except EncryptionError as e:
            self.db.rollback()
            logger.error(f"Provider credential encryption failed: {e!s}")
            raise ConfigurationError(str(e)) from e

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create provider configuration: {e!s}")
            raise

    def get_provider_config(self, config_id: int, customer_id: str) -> CustomerAIProvider | None:
        """
        Get provider configuration by ID.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)

        Returns:
            CustomerAIProvider instance or None
        """
        provider = (
            self.db.query(CustomerAIProvider)
            .filter(
                CustomerAIProvider.id == config_id, CustomerAIProvider.customer_id == customer_id
            )
            .first()
        )

        return provider

    def list_provider_configs(
        self, customer_id: str, provider_type: ProviderType | None = None
    ) -> list[CustomerAIProvider]:
        """
        List provider configurations for a customer.

        Args:
            customer_id: Customer identifier
            provider_type: Optional filter by provider type

        Returns:
            List of CustomerAIProvider instances
        """
        query = self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.customer_id == customer_id
        )

        if provider_type:
            query = query.filter(CustomerAIProvider.provider_name == provider_type.value)

        providers = query.all()

        logger.debug(f"Found {len(providers)} provider configurations for customer {customer_id}")
        return providers

    def update_provider_config(
        self, config_id: int, customer_id: str, update_data: ProviderConfigurationUpdate
    ) -> CustomerAIProvider:
        """
        Update provider configuration.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)
            update_data: Update data

        Returns:
            Updated CustomerAIProvider instance
        """
        provider = self.get_provider_config(config_id, customer_id)
        if not provider:
            raise ConfigurationError(f"Provider configuration {config_id} not found")

        try:
            provider_type = ProviderType(provider.provider_name)

            # Update is_enabled
            if update_data.is_enabled is not None:
                provider.is_enabled = update_data.is_enabled

            # Update config_data
            if update_data.config is not None:
                config_data = provider.config_data or {}

                # Re-encrypt credentials if API key changed
                if "api_key" in update_data.config or "aws_access_key_id" in update_data.config:
                    encrypted_credentials = self._encrypt_credentials(
                        provider_type, update_data.config
                    )
                    provider.api_key_encrypted = encrypted_credentials

                # Update config_data (sanitized)
                sanitized_config = self._sanitize_config(provider_type, update_data.config)
                config_data.update(sanitized_config)
                provider.config_data = config_data

            self.db.commit()
            self.db.refresh(provider)

            logger.info(f"Updated provider configuration {config_id} for customer {customer_id}")
            return provider

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update provider configuration {config_id}: {e!s}")
            raise

    def delete_provider_config(self, config_id: int, customer_id: str) -> bool:
        """
        Delete provider configuration.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        provider = self.get_provider_config(config_id, customer_id)
        if not provider:
            return False

        try:
            self.db.delete(provider)
            self.db.commit()
            logger.info(f"Deleted provider configuration {config_id} for customer {customer_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete provider configuration {config_id}: {e!s}")
            raise

    async def fetch_available_models(
        self, provider_type: ProviderType, credentials: dict[str, Any]
    ):
        """
        Fetch available models from a provider using temporary credentials.
        Does not save anything to the database.

        Args:
            provider_type: Provider type (openai, anthropic, etc.)
            credentials: Provider credentials (api_key, aws keys, etc.)

        Returns:
            List of available models
        """
        try:
            # Initialize provider instance with temporary credentials
            provider_class = self.PROVIDER_CLASSES.get(provider_type)
            if not provider_class:
                raise ConfigurationError(f"Unsupported provider type: {provider_type}")

            # Initialize provider based on type
            if (
                provider_type == ProviderType.OPENAI
                or provider_type == ProviderType.ANTHROPIC
                or provider_type == ProviderType.GROQ
            ):
                provider_instance = provider_class(
                    api_key=credentials["api_key"], customer_config=None
                )
            elif provider_type == ProviderType.BEDROCK:
                # BedrockProvider.get_available_models() only returns configured models.
                # Use BedrockDiscoveryService to list models from AWS with the given credentials.
                from src.models.bedrock_config import BedrockAuthMethod
                from src.services.bedrock_discovery_service import BedrockDiscoveryService

                aws_region = credentials.get("aws_region") or "us-west-2"
                aws_access_key_id = credentials.get("aws_access_key_id")
                aws_secret_access_key = credentials.get("aws_secret_access_key")
                if not aws_access_key_id or not aws_secret_access_key:
                    raise ConfigurationError(
                        "AWS Access Key ID and Secret Access Key are required to fetch Bedrock models"
                    )
                discovery = BedrockDiscoveryService(
                    aws_region=aws_region,
                    auth_method=BedrockAuthMethod.API_KEYS,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    aws_session_token=credentials.get("aws_session_token"),
                )
                discovered = await asyncio.to_thread(
                    discovery.discover_models,
                    provider_filter=None,
                    include_inactive=False,
                )
                # Convert BedrockModelInfo to ModelInfo for consistent API response
                models = [
                    ModelInfo(
                        id=m.model_id,
                        name=m.model_id,
                        provider=m.provider,
                        description=m.model_name or f"{m.model_id} ({m.provider})",
                        context_length=m.max_tokens,
                        max_tokens=m.max_tokens,
                        supports_functions=False,
                        supports_vision=False,
                    )
                    for m in discovered
                ]
            else:
                raise ConfigurationError(f"Unsupported provider type: {provider_type}")

            # Fetch available models (for non-Bedrock, provider_instance.get_available_models())
            if provider_type != ProviderType.BEDROCK:
                models = await provider_instance.get_available_models()

            logger.info(f"Fetched {len(models)} models from {provider_type.value}")

            return models

        except Exception as e:
            logger.error(f"Failed to fetch models from {provider_type.value}: {e!s}")
            raise

    async def test_provider_connection(
        self, config_id: int, customer_id: str, test_prompt: str = "Hello, this is a test."
    ) -> ProviderConnectionTestResponse:
        """
        Test provider connection and credentials.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)
            test_prompt: Prompt to use for testing

        Returns:
            ProviderConnectionTestResponse with test results
        """
        provider = self.get_provider_config(config_id, customer_id)
        if not provider:
            raise ConfigurationError(f"Provider configuration {config_id} not found")

        try:
            provider_type = ProviderType(provider.provider_name)
            start_time = datetime.now()

            # Initialize provider instance
            provider_instance = self._initialize_provider(provider)

            # Test connection
            test_model = self._get_test_model(provider)

            # Make a minimal test request
            response = await provider_instance.generate_text(
                model=test_model, prompt=test_prompt, max_tokens=50, temperature=0.7
            )

            end_time = datetime.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000

            # Update health status
            provider.is_healthy = True
            provider.last_health_check = datetime.now()
            provider.error_count = 0
            provider.last_error = None
            self.db.commit()

            return ProviderConnectionTestResponse(
                success=True,
                provider_type=provider_type.value,
                message=f"{provider_type.value} connection successful",
                response_time_ms=response_time_ms,
                test_output=response.get("text", "")[:200],  # First 200 chars
                model_tested=test_model,
                tested_at=datetime.now(),
            )

        except Exception as e:
            # Update health status
            provider.is_healthy = False
            provider.last_health_check = datetime.now()
            provider.error_count += 1
            provider.last_error = str(e)
            self.db.commit()

            logger.error(f"Provider connection test failed for config {config_id}: {e!s}")

            return ProviderConnectionTestResponse(
                success=False,
                provider_type=provider.provider_name,
                message=f"{provider.provider_name} connection failed",
                error_details=str(e),
                tested_at=datetime.now(),
            )

    def _initialize_provider(self, config: CustomerAIProvider) -> Any:
        """
        Initialize provider instance from configuration.

        Args:
            config: CustomerAIProvider database record

        Returns:
            Provider instance (OpenAIProvider, AnthropicProvider, etc.)
        """
        provider_type = ProviderType(config.provider_name)
        config_data = config.config_data or {}

        # Decrypt credentials
        decrypted_config = self._decrypt_credentials(provider_type, config)

        # Merge with config_data
        full_config = {**config_data, **decrypted_config}

        # Initialize provider based on type
        provider_class = self.PROVIDER_CLASSES.get(provider_type)
        if not provider_class:
            raise ConfigurationError(f"No provider class for type: {provider_type}")

        # Initialize with appropriate parameters
        if (
            provider_type == ProviderType.OPENAI
            or provider_type == ProviderType.ANTHROPIC
            or provider_type == ProviderType.GROQ
        ):
            return provider_class(api_key=full_config["api_key"], customer_config=None)
        elif provider_type == ProviderType.BEDROCK:
            raw_available_models = full_config.get("available_models", [])
            normalized_available_models = normalize_bedrock_models(
                raw_available_models,
                logger=logger,
                context=f"provider_service_init_bedrock config_id={config.id}",
            )
            available_models = [
                BedrockModelInfo(**model_dict) for model_dict in normalized_available_models
            ]

            return provider_class(
                aws_region=full_config.get("aws_region", "us-west-2"),
                auth_method=full_config.get("auth_method", "api_keys"),
                aws_access_key_id=full_config.get("aws_access_key_id"),
                aws_secret_access_key=full_config.get("aws_secret_access_key"),
                aws_session_token=full_config.get("aws_session_token"),
                base_url=full_config.get("base_url"),
                available_models=available_models,
                customer_config=None,
            )
        else:
            raise ConfigurationError(f"Unsupported provider type: {provider_type}")

    def _encrypt_credentials(self, provider_type: ProviderType, config: dict[str, Any]) -> str:
        """Encrypt sensitive credentials based on provider type."""
        credentials = {}

        if provider_type in [ProviderType.OPENAI, ProviderType.ANTHROPIC, ProviderType.GROQ]:
            if "api_key" in config:
                credentials["api_key"] = config["api_key"]
            if "organization_id" in config:
                credentials["organization_id"] = config.get("organization_id")

        elif provider_type == ProviderType.BEDROCK:
            if "aws_access_key_id" in config:
                credentials["aws_access_key_id"] = config["aws_access_key_id"]
            if "aws_secret_access_key" in config:
                credentials["aws_secret_access_key"] = config["aws_secret_access_key"]
            if "aws_session_token" in config:
                credentials["aws_session_token"] = config["aws_session_token"]

        return encrypt_value(json.dumps(credentials))

    def _decrypt_credentials(
        self, provider_type: ProviderType, config: CustomerAIProvider
    ) -> dict[str, Any]:
        """Decrypt credentials from database."""
        if not config.api_key_encrypted:
            return {}

        try:
            decrypted = json.loads(decrypt_value(config.api_key_encrypted))
            return decrypted
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for config {config.id}: {e!s}")
            return {}

    def _sanitize_config(
        self, provider_type: ProviderType, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Remove sensitive data from config before storing in config_data."""
        sanitized = config.copy()

        # Remove API keys
        sanitized.pop("api_key", None)
        sanitized.pop("aws_access_key_id", None)
        sanitized.pop("aws_secret_access_key", None)
        sanitized.pop("aws_session_token", None)

        return sanitized

    def _apply_defaults(
        self, provider_type: ProviderType, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply provider-specific defaults."""
        metadata = PROVIDER_METADATA.get(provider_type, {})

        if "available_models" not in config:
            config["available_models"] = metadata.get("default_models", [])

        if provider_type == ProviderType.OPENAI and "base_url" not in config:
            config["base_url"] = "https://api.openai.com/v1"
        elif provider_type == ProviderType.ANTHROPIC and "base_url" not in config:
            config["base_url"] = "https://api.anthropic.com"
        elif provider_type == ProviderType.GROQ and "base_url" not in config:
            config["base_url"] = "https://api.groq.com/openai/v1"
        elif provider_type == ProviderType.BEDROCK and "base_url" not in config:
            region = config.get("aws_region", "us-west-2")
            config["base_url"] = f"https://bedrock-runtime.{region}.amazonaws.com/openai/v1"

        return config

    def _get_default_priority(self, provider_type: ProviderType) -> int:
        """Get default priority for provider type."""
        priorities = {
            ProviderType.OPENAI: 1,
            ProviderType.ANTHROPIC: 2,
            ProviderType.GROQ: 5,
            ProviderType.BEDROCK: 10,
        }
        return priorities.get(provider_type, 50)

    def _get_test_model(self, config: CustomerAIProvider) -> str:
        """Get appropriate test model for provider."""
        config_data = config.config_data or {}

        # Try default model first
        default_model = config_data.get("default_model")
        if default_model:
            return default_model

        # Get first available model
        available_models = config_data.get("available_models", [])
        if available_models:
            if isinstance(available_models[0], dict):
                return available_models[0].get("model_id", available_models[0].get("id"))
            return available_models[0]

        # Fallback to provider-specific defaults
        provider_type = ProviderType(config.provider_name)
        metadata = PROVIDER_METADATA.get(provider_type, {})
        default_models = metadata.get("default_models", [])

        if default_models:
            return default_models[0]

        # Last resort fallbacks
        fallbacks = {
            ProviderType.OPENAI: "gpt-3.5-turbo",
            ProviderType.ANTHROPIC: "claude-3-haiku-20240307",
            ProviderType.GROQ: "llama-3.1-8b-instant",
            ProviderType.BEDROCK: "anthropic.claude-instant-v1",
        }
        return fallbacks.get(provider_type, "gpt-3.5-turbo")
