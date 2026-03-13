"""
AI Enablement Platform - AWS Bedrock Configuration Service

Service for managing AWS Bedrock provider configurations in the database.
Handles CRUD operations, credential encryption, and model management.

Terraform alignment (generation / IAM / VPC):
- IAM: Use auth_method=iam_role so the app uses the default boto3 credential chain
  (env, instance role, ECS task role). Terraform should attach a policy allowing
  bedrock:InvokeModel, bedrock:InvokeModelWithResponseStream (and list/get if needed).
- VPC endpoint: If Terraform provisions a Bedrock VPC endpoint for private access,
  either (1) run the app in the VPC so traffic uses the endpoint automatically, or
  (2) set base_url to the VPC endpoint URL when creating/updating the config.
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.exceptions import ConfigurationError
from src.models.bedrock_config import (
    AddBedrockModelRequest,
    BedrockAuthMethod,
    BedrockConfigurationCreate,
    BedrockConfigurationUpdate,
    BedrockModelInfo,
)
from src.models.customer import CustomerAIProvider
from src.services.base_service import BaseService
from src.services.bedrock_discovery_service import BedrockDiscoveryService
from src.services.bedrock_model_utils import normalize_bedrock_models
from src.utils.encryption import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)


class BedrockService(BaseService):
    """
    Service for managing AWS Bedrock configurations.

    Provides CRUD operations for Bedrock provider configurations,
    handles credential encryption, and integrates with discovery service.
    """

    def __init__(self, db: Session):
        """Initialize Bedrock service with database session."""
        super().__init__()
        self.db = db

    def create_bedrock_config(
        self, customer_id: str, config: BedrockConfigurationCreate
    ) -> CustomerAIProvider:
        """
        Create a new Bedrock configuration for a customer.

        Args:
            customer_id: Customer identifier
            config: Bedrock configuration data

        Returns:
            Created CustomerAIProvider instance

        Raises:
            ConfigurationError: If validation fails
            IntegrityError: If configuration already exists
        """
        try:
            # Validate authentication method
            if config.auth_method == BedrockAuthMethod.API_KEYS:
                if not config.aws_access_key_id or not config.aws_secret_access_key:
                    raise ConfigurationError(
                        "AWS Access Key ID and Secret Access Key are required for 'api_keys' auth method"
                    )

            # Encrypt sensitive credentials
            config_data = {
                "auth_method": config.auth_method,
                "aws_region": config.aws_region,
                "connection_timeout": config.connection_timeout,
                "max_retries": config.max_retries,
                "available_models": [],
                "default_model": None,
            }

            # Base URL: explicit override (e.g. VPC endpoint) or derive from region
            if config.base_url and config.base_url.strip():
                config_data["base_url"] = config.base_url.strip()
            else:
                config_data["base_url"] = (
                    f"https://bedrock-runtime.{config.aws_region}.amazonaws.com/openai/v1"
                )

            # Encrypt AWS credentials if using API keys
            encrypted_credentials = None
            if config.auth_method == BedrockAuthMethod.API_KEYS:
                credentials_json = {
                    "aws_access_key_id": config.aws_access_key_id,
                    "aws_secret_access_key": config.aws_secret_access_key,
                }
                if config.aws_session_token:
                    credentials_json["aws_session_token"] = config.aws_session_token

                # Encrypt and store
                import json

                encrypted_credentials = encrypt_value(json.dumps(credentials_json))

            # Create CustomerAIProvider record
            provider = CustomerAIProvider(
                customer_id=customer_id,
                provider_name="bedrock",
                is_enabled=True,
                api_key_encrypted=encrypted_credentials,
                config_data=config_data,
                priority=10,  # Default priority for Bedrock
                max_requests_per_minute=60,
                max_tokens_per_request=100000,
                is_healthy=False,  # Will be set on first health check
                last_health_check=None,
                error_count=0,
            )

            self.db.add(provider)
            self.db.commit()
            self.db.refresh(provider)

            logger.info(
                f"Created Bedrock configuration for customer {customer_id}: "
                f"region={config.aws_region}, auth={config.auth_method}"
            )

            return provider

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Bedrock configuration already exists for customer {customer_id}")
            raise ConfigurationError(
                f"Bedrock configuration already exists for customer {customer_id}"
            ) from e

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create Bedrock configuration: {e!s}")
            raise

    def get_bedrock_config(self, config_id: int, customer_id: str) -> CustomerAIProvider | None:
        """
        Get Bedrock configuration by ID.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)

        Returns:
            CustomerAIProvider instance or None
        """
        provider = (
            self.db.query(CustomerAIProvider)
            .filter(
                CustomerAIProvider.id == config_id,
                CustomerAIProvider.customer_id == customer_id,
                CustomerAIProvider.provider_name == "bedrock",
            )
            .first()
        )

        return provider

    def list_bedrock_configs(self, customer_id: str) -> list[CustomerAIProvider]:
        """
        List all Bedrock configurations for a customer.

        Args:
            customer_id: Customer identifier

        Returns:
            List of CustomerAIProvider instances
        """
        providers = (
            self.db.query(CustomerAIProvider)
            .filter(
                CustomerAIProvider.customer_id == customer_id,
                CustomerAIProvider.provider_name == "bedrock",
            )
            .all()
        )

        logger.debug(f"Found {len(providers)} Bedrock configurations for customer {customer_id}")
        return providers

    def update_bedrock_config(
        self, config_id: int, customer_id: str, update_data: BedrockConfigurationUpdate
    ) -> CustomerAIProvider:
        """
        Update Bedrock configuration.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)
            update_data: Update data

        Returns:
            Updated CustomerAIProvider instance

        Raises:
            ConfigurationError: If configuration not found
        """
        provider = self.get_bedrock_config(config_id, customer_id)
        if not provider:
            raise ConfigurationError(f"Bedrock configuration {config_id} not found")

        try:
            config_data = provider.config_data or {}

            # Update authentication method
            if update_data.auth_method is not None:
                config_data["auth_method"] = update_data.auth_method

            # Update region
            if update_data.aws_region is not None:
                config_data["aws_region"] = update_data.aws_region
                # Regenerate base URL from region only if no explicit base_url in this update
                if update_data.base_url is None:
                    config_data["base_url"] = (
                        f"https://bedrock-runtime.{update_data.aws_region}.amazonaws.com/openai/v1"
                    )
            # Optional base_url override (e.g. VPC endpoint)
            if update_data.base_url is not None:
                config_data["base_url"] = (
                    update_data.base_url.strip()
                    if update_data.base_url.strip()
                    else f"https://bedrock-runtime.{config_data.get('aws_region', 'us-west-2')}.amazonaws.com/openai/v1"
                )

            # Update connection settings
            if update_data.connection_timeout is not None:
                config_data["connection_timeout"] = update_data.connection_timeout
            if update_data.max_retries is not None:
                config_data["max_retries"] = update_data.max_retries

            # Update credentials if provided
            if update_data.aws_access_key_id or update_data.aws_secret_access_key:
                import json

                # Decrypt existing credentials
                existing_creds = {}
                if provider.api_key_encrypted:
                    try:
                        existing_creds = json.loads(decrypt_value(provider.api_key_encrypted))
                    except Exception:
                        pass

                # Update with new values
                if update_data.aws_access_key_id:
                    existing_creds["aws_access_key_id"] = update_data.aws_access_key_id
                if update_data.aws_secret_access_key:
                    existing_creds["aws_secret_access_key"] = update_data.aws_secret_access_key
                if update_data.aws_session_token:
                    existing_creds["aws_session_token"] = update_data.aws_session_token

                # Re-encrypt
                provider.api_key_encrypted = encrypt_value(json.dumps(existing_creds))

            provider.config_data = config_data
            self.db.commit()
            self.db.refresh(provider)

            logger.info(f"Updated Bedrock configuration {config_id} for customer {customer_id}")
            return provider

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update Bedrock configuration {config_id}: {e!s}")
            raise

    def delete_bedrock_config(self, config_id: int, customer_id: str) -> bool:
        """
        Delete Bedrock configuration.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        provider = self.get_bedrock_config(config_id, customer_id)
        if not provider:
            return False

        try:
            self.db.delete(provider)
            self.db.commit()
            logger.info(f"Deleted Bedrock configuration {config_id} for customer {customer_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete Bedrock configuration {config_id}: {e!s}")
            raise

    def add_model_to_config(
        self, config_id: int, customer_id: str, model_request: AddBedrockModelRequest
    ) -> CustomerAIProvider:
        """
        Add a model to Bedrock configuration.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)
            model_request: Model addition request

        Returns:
            Updated CustomerAIProvider instance

        Raises:
            ConfigurationError: If configuration not found or model already exists
        """
        provider = self.get_bedrock_config(config_id, customer_id)
        if not provider:
            raise ConfigurationError(f"Bedrock configuration {config_id} not found")

        try:
            config_data = provider.config_data or {}
            available_models = normalize_bedrock_models(
                config_data.get("available_models", []),
                logger=logger,
                context=f"bedrock_service_add_model config_id={config_id}",
            )

            # Check if model already exists
            if any(m.get("model_id") == model_request.model_id for m in available_models):
                raise ConfigurationError(
                    f"Model {model_request.model_id} already exists in configuration"
                )

            # Add new model
            new_model = {
                "model_id": model_request.model_id,
                "model_name": model_request.model_name,
                "provider": model_request.provider,
                "is_enabled": True,
                "max_tokens": model_request.max_tokens,
                "supports_streaming": model_request.supports_streaming,
            }
            available_models.append(new_model)
            config_data["available_models"] = available_models

            # Set as default if requested
            if model_request.set_as_default:
                config_data["default_model"] = model_request.model_id

            provider.config_data = config_data
            self.db.commit()
            self.db.refresh(provider)

            logger.info(
                f"Added model {model_request.model_id} to Bedrock configuration {config_id}"
            )
            return provider

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add model to configuration {config_id}: {e!s}")
            raise

    def remove_model_from_config(
        self, config_id: int, customer_id: str, model_id: str
    ) -> CustomerAIProvider:
        """
        Remove a model from Bedrock configuration.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)
            model_id: Model ID to remove

        Returns:
            Updated CustomerAIProvider instance
        """
        provider = self.get_bedrock_config(config_id, customer_id)
        if not provider:
            raise ConfigurationError(f"Bedrock configuration {config_id} not found")

        try:
            config_data = provider.config_data or {}
            available_models = normalize_bedrock_models(
                config_data.get("available_models", []),
                logger=logger,
                context=f"bedrock_service_remove_model config_id={config_id}",
            )

            # Remove model
            available_models = [m for m in available_models if m.get("model_id") != model_id]
            config_data["available_models"] = available_models

            # Clear default if it was this model
            if config_data.get("default_model") == model_id:
                config_data["default_model"] = None

            provider.config_data = config_data
            self.db.commit()
            self.db.refresh(provider)

            logger.info(f"Removed model {model_id} from Bedrock configuration {config_id}")
            return provider

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to remove model from configuration {config_id}: {e!s}")
            raise

    def test_bedrock_connection(self, config_id: int, customer_id: str) -> dict[str, Any]:
        """
        Test Bedrock connection for a configuration.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)

        Returns:
            Dictionary with test results
        """
        provider = self.get_bedrock_config(config_id, customer_id)
        if not provider:
            raise ConfigurationError(f"Bedrock configuration {config_id} not found")

        try:
            # Get configuration
            config_data = provider.config_data or {}
            auth_method = config_data.get("auth_method", BedrockAuthMethod.API_KEYS)
            aws_region = config_data.get("aws_region", "us-west-2")

            # Decrypt credentials if using API keys
            aws_access_key_id = None
            aws_secret_access_key = None
            aws_session_token = None

            if auth_method == BedrockAuthMethod.API_KEYS and provider.api_key_encrypted:
                import json

                credentials = json.loads(decrypt_value(provider.api_key_encrypted))
                aws_access_key_id = credentials.get("aws_access_key_id")
                aws_secret_access_key = credentials.get("aws_secret_access_key")
                aws_session_token = credentials.get("aws_session_token")

            # Create discovery service and test
            discovery_service = BedrockDiscoveryService(
                aws_region=aws_region,
                auth_method=auth_method,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
            )

            test_result = discovery_service.test_credentials()

            # Update health status
            if test_result["success"]:
                provider.is_healthy = True
                provider.last_health_check = datetime.now()
                provider.error_count = 0
                provider.last_error = None
            else:
                provider.is_healthy = False
                provider.last_health_check = datetime.now()
                provider.error_count += 1
                provider.last_error = test_result.get("error_details")

            self.db.commit()

            return test_result

        except Exception as e:
            logger.error(f"Failed to test Bedrock connection for config {config_id}: {e!s}")
            raise

    def discover_models(
        self, config_id: int, customer_id: str, provider_filter: str | None = None
    ) -> list[BedrockModelInfo]:
        """
        Discover available models using boto3 API.

        Args:
            config_id: Configuration ID
            customer_id: Customer ID (for authorization)
            provider_filter: Filter models by provider

        Returns:
            List of discovered BedrockModelInfo objects
        """
        provider = self.get_bedrock_config(config_id, customer_id)
        if not provider:
            raise ConfigurationError(f"Bedrock configuration {config_id} not found")

        try:
            # Get configuration
            config_data = provider.config_data or {}
            auth_method = config_data.get("auth_method", BedrockAuthMethod.API_KEYS)
            aws_region = config_data.get("aws_region", "us-west-2")

            # Decrypt credentials if using API keys
            aws_access_key_id = None
            aws_secret_access_key = None
            aws_session_token = None

            if auth_method == BedrockAuthMethod.API_KEYS and provider.api_key_encrypted:
                import json

                credentials = json.loads(decrypt_value(provider.api_key_encrypted))
                aws_access_key_id = credentials.get("aws_access_key_id")
                aws_secret_access_key = credentials.get("aws_secret_access_key")
                aws_session_token = credentials.get("aws_session_token")

            # Create discovery service
            discovery_service = BedrockDiscoveryService(
                aws_region=aws_region,
                auth_method=auth_method,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
            )

            # Discover models
            discovered_models = discovery_service.discover_models(
                provider_filter=provider_filter, include_inactive=False
            )

            logger.info(
                f"Discovered {len(discovered_models)} models for Bedrock config {config_id}"
            )

            return discovered_models

        except Exception as e:
            logger.error(f"Failed to discover models for config {config_id}: {e!s}")
            raise
