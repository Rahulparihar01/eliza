"""
AI Enablement Platform - Model Service

Service for managing AI model providers and interactions.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any

from src.core.config import CustomerConfig, Settings
from src.core.exceptions import ModelProviderError
from src.models.bedrock_config import BedrockModelInfo
from src.models.customer import CustomerAIProvider
from src.models.model_info import ModelTestResponse, ProviderStatus
from src.models.provider_config import ProviderType
from src.services.bedrock_model_utils import normalize_bedrock_models
from src.services.providers.anthropic_provider import AnthropicProvider
from src.services.providers.bedrock_provider import BedrockProvider
from src.services.providers.groq_provider import GroqProvider
from src.services.providers.openai_provider import OpenAIProvider
from src.utils.encryption import decrypt_value

logger = logging.getLogger(__name__)


class ModelService:
    """Service for managing AI model providers."""

    def __init__(self, settings: Settings, customer_config: CustomerConfig):
        self.settings = settings
        self.customer_config = customer_config
        self.providers = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """
        Initialize available AI providers.

        Strategy:
        1. Load from database first (per-customer configurations)
        2. Fall back to environment variables (backward compatibility)
        """
        # Load all providers from database (multi-tenant, per-customer)
        self._initialize_database_providers()

        # Fallback to environment variables if no database configs
        self._initialize_env_fallback()

        logger.info(
            f"Initialized {len(self.providers)} AI providers: {list(self.providers.keys())}"
        )

    def _initialize_database_providers(self):
        """
        Initialize all providers from database configurations (multi-tenant).

        This method loads customer-specific provider configurations from the database.
        Each customer can have their own API keys and settings for each provider type.
        """
        customer_id = self.customer_config.customer_id
        try:
            from src.models import database

            # Check if database is initialized
            if database.SessionLocal is None:
                logger.info(
                    "ModelService: database SessionLocal not initialized, skipping database providers for customer_id=%s",
                    customer_id,
                )
                database.init_database()

            db = database.SessionLocal()
            try:
                # Use customer from config (tenant-scoped); allows API to pass current user's customer_id
                # Query ALL provider configurations for this customer
                all_configs = (
                    db.query(CustomerAIProvider)
                    .filter(
                        CustomerAIProvider.customer_id == customer_id,
                        CustomerAIProvider.is_enabled == True,
                    )
                    .all()
                )

                # Diagnostic: always log customer and count so we can see why Bedrock (or any DB config) is missing
                provider_types = [c.provider_name for c in all_configs]
                logger.info(
                    "ModelService: found %s enabled provider configs for customer_id=%s (provider_types=%s)",
                    len(all_configs),
                    customer_id,
                    provider_types,
                )

                # Initialize each provider configuration
                for config in all_configs:
                    try:
                        provider_type = ProviderType(config.provider_name)

                        if provider_type == ProviderType.OPENAI:
                            self._init_openai_from_db(config)
                        elif provider_type == ProviderType.ANTHROPIC:
                            self._init_anthropic_from_db(config)
                        elif provider_type == ProviderType.GROQ:
                            self._init_groq_from_db(config)
                        elif provider_type == ProviderType.BEDROCK:
                            self._init_bedrock_from_db(config)
                        else:
                            logger.warning(f"Unsupported provider type: {provider_type}")
                            continue

                    except Exception as e:
                        logger.error(
                            f"Failed to initialize {config.provider_name} config {config.id}: {e!s}"
                        )
                        continue

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to load providers from database: {e!s}")
            # Don't fail initialization if database loading fails

    def _init_openai_from_db(self, config: CustomerAIProvider):
        """Initialize OpenAI provider from database configuration."""
        config_data = config.config_data or {}

        # Decrypt API key
        if not config.api_key_encrypted:
            logger.warning(f"OpenAI config {config.id} has no API key")
            return

        credentials = json.loads(decrypt_value(config.api_key_encrypted))
        api_key = credentials.get("api_key")

        if not api_key:
            logger.error(f"OpenAI config {config.id} missing API key in encrypted data")
            return

        # Create provider key (unique per config)
        provider_key = f"openai_{config.id}"

        # Initialize OpenAI provider
        self.providers[provider_key] = OpenAIProvider(
            api_key=api_key, customer_config=self.customer_config
        )

        logger.info(f"Initialized OpenAI provider: {provider_key} from database")

    def _init_anthropic_from_db(self, config: CustomerAIProvider):
        """Initialize Anthropic provider from database configuration."""
        config_data = config.config_data or {}

        # Decrypt API key
        if not config.api_key_encrypted:
            logger.warning(f"Anthropic config {config.id} has no API key")
            return

        credentials = json.loads(decrypt_value(config.api_key_encrypted))
        api_key = credentials.get("api_key")

        if not api_key:
            logger.error(f"Anthropic config {config.id} missing API key in encrypted data")
            return

        # Create provider key (unique per config)
        provider_key = f"anthropic_{config.id}"

        # Initialize Anthropic provider
        self.providers[provider_key] = AnthropicProvider(
            api_key=api_key, customer_config=self.customer_config
        )

        logger.info(f"Initialized Anthropic provider: {provider_key} from database")

    def _init_groq_from_db(self, config: CustomerAIProvider):
        """Initialize Groq provider from database configuration."""
        config_data = config.config_data or {}

        # Decrypt API key
        if not config.api_key_encrypted:
            logger.warning(f"Groq config {config.id} has no API key")
            return

        credentials = json.loads(decrypt_value(config.api_key_encrypted))
        api_key = credentials.get("api_key")

        if not api_key:
            logger.error(f"Groq config {config.id} missing API key in encrypted data")
            return

        # Create provider key (unique per config)
        provider_key = f"groq_{config.id}"

        # Initialize Groq provider
        self.providers[provider_key] = GroqProvider(
            api_key=api_key, customer_config=self.customer_config
        )

        logger.info(f"Initialized Groq provider: {provider_key} from database")

    def _init_bedrock_from_db(self, config: CustomerAIProvider):
        """Initialize Bedrock provider from database configuration."""
        config_data = config.config_data or {}
        auth_method = config_data.get("auth_method", "api_keys")
        aws_region = config_data.get("aws_region", "us-west-2")
        base_url = config_data.get("base_url")
        connection_timeout = config_data.get("connection_timeout", 30)
        max_retries = config_data.get("max_retries", 3)

        # Decrypt credentials if using API keys
        aws_access_key_id = None
        aws_secret_access_key = None
        aws_session_token = None

        if auth_method == "api_keys" and config.api_key_encrypted:
            credentials = json.loads(decrypt_value(config.api_key_encrypted))
            aws_access_key_id = credentials.get("aws_access_key_id")
            aws_secret_access_key = credentials.get("aws_secret_access_key")
            aws_session_token = credentials.get("aws_session_token")

        raw_available_models = config_data.get("available_models", [])
        normalized_models = normalize_bedrock_models(
            raw_available_models,
            logger=logger,
            context=(
                f"model_service_init_bedrock customer_id={self.customer_config.customer_id} "
                f"config_id={config.id}"
            ),
        )
        available_models = [BedrockModelInfo(**model_dict) for model_dict in normalized_models]
        logger.info(
            "ModelService: normalized Bedrock available_models for config_id=%s raw_count=%s normalized_count=%s",
            config.id,
            len(raw_available_models) if isinstance(raw_available_models, list) else 0,
            len(available_models),
        )

        # Create Bedrock provider instance
        provider_key = f"bedrock_{aws_region}_{config.id}"
        self.providers[provider_key] = BedrockProvider(
            aws_region=aws_region,
            auth_method=auth_method,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            base_url=base_url,
            available_models=available_models,
            connection_timeout=connection_timeout,
            max_retries=max_retries,
            customer_config=self.customer_config,
        )

        logger.info(
            f"Initialized Bedrock provider: {provider_key} "
            f"(region={aws_region}, models={len(available_models)}) from database"
        )

    def _initialize_env_fallback(self):
        """
        Initialize providers from environment variables (backward compatibility).

        Only initializes providers that weren't already loaded from database.
        """
        # Track which provider types we already have
        existing_types = set()
        for provider_key in self.providers.keys():
            if provider_key.startswith("openai"):
                existing_types.add("openai")
            elif provider_key.startswith("anthropic"):
                existing_types.add("anthropic")
            elif provider_key.startswith("groq"):
                existing_types.add("groq")
            elif provider_key.startswith("bedrock"):
                existing_types.add("bedrock")

        # Initialize OpenAI from env if not in database
        if "openai" not in existing_types and self.settings.openai_api_key:
            self.providers["openai_env"] = OpenAIProvider(
                api_key=self.settings.openai_api_key, customer_config=self.customer_config
            )
            logger.info("Initialized OpenAI provider from environment variable")

        # Initialize Anthropic from env if not in database
        if "anthropic" not in existing_types and self.settings.anthropic_api_key:
            self.providers["anthropic_env"] = AnthropicProvider(
                api_key=self.settings.anthropic_api_key, customer_config=self.customer_config
            )
            logger.info("Initialized Anthropic provider from environment variable")

        # Initialize Groq from env if not in database
        if "groq" not in existing_types and self.settings.groq_api_key:
            self.providers["groq_env"] = GroqProvider(
                api_key=self.settings.groq_api_key, customer_config=self.customer_config
            )
            logger.info("Initialized Groq provider from environment variable")

    async def get_providers_status(self) -> list[ProviderStatus]:
        """Get status of all configured providers."""
        providers_status = []

        for provider_name, provider in self.providers.items():
            try:
                status = await self._get_single_provider_status(provider_name, provider)
                providers_status.append(status)
            except Exception as e:
                logger.error(f"Failed to get status for provider {provider_name}: {e}")
                providers_status.append(
                    ProviderStatus(
                        name=provider_name,
                        configured=True,
                        available=False,
                        models=[],
                        last_checked=datetime.utcnow(),
                        error_message=str(e),
                    )
                )

        # Add unconfigured providers
        all_providers = ["openai", "anthropic", "groq", "together"]
        for provider_name in all_providers:
            if provider_name not in self.providers:
                providers_status.append(
                    ProviderStatus(
                        name=provider_name,
                        configured=False,
                        available=False,
                        models=[],
                        error_message="Provider not configured (missing API key)",
                    )
                )

        return providers_status

    async def get_provider_status(self, provider_name: str) -> ProviderStatus | None:
        """Get status of a specific provider."""
        if provider_name not in self.providers:
            return None

        provider = self.providers[provider_name]
        return await self._get_single_provider_status(provider_name, provider)

    async def _get_single_provider_status(self, provider_name: str, provider) -> ProviderStatus:
        """Get status for a single provider."""
        try:
            # Test provider availability
            is_available = await provider.test_connection()

            # Get available models
            models = await provider.get_available_models()

            return ProviderStatus(
                name=provider_name,
                configured=True,
                available=is_available,
                models=models,
                last_checked=datetime.utcnow(),
                error_message=None if is_available else "Connection test failed",
            )

        except Exception as e:
            logger.error(f"Error checking provider {provider_name}: {e}")
            return ProviderStatus(
                name=provider_name,
                configured=True,
                available=False,
                models=[],
                last_checked=datetime.utcnow(),
                error_message=str(e),
            )

    async def test_model(self, provider: str, model: str, test_prompt: str) -> ModelTestResponse:
        """Test a specific model with a prompt."""
        if provider not in self.providers:
            return ModelTestResponse(
                success=False,
                provider=provider,
                model=model,
                error_message=f"Provider '{provider}' not configured",
            )

        provider_instance = self.providers[provider]

        try:
            start_time = time.time()

            # Make test request
            response = await provider_instance.generate_text(
                model=model, prompt=test_prompt, max_tokens=100
            )

            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000

            return ModelTestResponse(
                success=True,
                provider=provider,
                model=model,
                response_text=response.get("text", ""),
                response_time_ms=response_time_ms,
                tokens_used=response.get("tokens_used"),
            )

        except Exception as e:
            logger.error(f"Model test failed for {provider}/{model}: {e}")
            return ModelTestResponse(
                success=False, provider=provider, model=model, error_message=str(e)
            )

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on all model services."""
        health_status = {
            "status": "healthy",
            "providers": {},
            "summary": {
                "total_providers": len(self.providers),
                "healthy_providers": 0,
                "unhealthy_providers": 0,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        for provider_name, provider in self.providers.items():
            try:
                is_healthy = await provider.test_connection()
                health_status["providers"][provider_name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "available": is_healthy,
                }

                if is_healthy:
                    health_status["summary"]["healthy_providers"] += 1
                else:
                    health_status["summary"]["unhealthy_providers"] += 1

            except Exception as e:
                health_status["providers"][provider_name] = {
                    "status": "unhealthy",
                    "available": False,
                    "error": str(e),
                }
                health_status["summary"]["unhealthy_providers"] += 1

        # Determine overall status
        if health_status["summary"]["healthy_providers"] == 0:
            health_status["status"] = "unhealthy"
        elif health_status["summary"]["unhealthy_providers"] > 0:
            health_status["status"] = "degraded"

        return health_status

    def get_provider_for_task(self, task: str) -> str:
        """Get the best provider for a specific task."""
        # Get model for task from customer config
        model = self.customer_config.get_model_for_task(task)

        # Determine provider based on model
        if model.startswith("gpt-"):
            return "openai"
        elif model.startswith("claude-"):
            return "anthropic"
        elif model in ["llama2-70b-4096", "mixtral-8x7b-32768"]:
            return "groq"
        else:
            # Default to configured default provider
            return self.customer_config.get_default_provider()

    async def generate_text(
        self,
        prompt: str,
        task: str = "general",
        model: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Generate text using the appropriate model for the task."""

        # Determine model and provider
        if not model:
            model = self.customer_config.get_model_for_task(task)

        provider_name = self.get_provider_for_task(task)

        if provider_name not in self.providers:
            # Try fallback providers
            fallback_providers = self.customer_config.get_fallback_providers()
            for fallback in fallback_providers:
                if fallback in self.providers:
                    provider_name = fallback
                    break
            else:
                raise ModelProviderError(
                    f"No available providers for task '{task}'", provider=provider_name
                )

        provider = self.providers[provider_name]

        try:
            return await provider.generate_text(
                model=model, prompt=prompt, max_tokens=max_tokens, temperature=temperature
            )

        except Exception as e:
            logger.error(f"Text generation failed with {provider_name}: {e}")

            # Try fallback providers
            fallback_providers = self.customer_config.get_fallback_providers()
            for fallback in fallback_providers:
                if fallback in self.providers and fallback != provider_name:
                    try:
                        logger.info(f"Trying fallback provider: {fallback}")
                        fallback_provider = self.providers[fallback]
                        return await fallback_provider.generate_text(
                            model=model,
                            prompt=prompt,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                    except Exception as fallback_error:
                        logger.error(f"Fallback provider {fallback} also failed: {fallback_error}")
                        continue

            # All providers failed
            raise ModelProviderError(
                f"All providers failed for task '{task}': {e!s}", provider=provider_name
            )
