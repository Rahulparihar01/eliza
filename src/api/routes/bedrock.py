"""
AI Enablement Platform - AWS Bedrock Configuration Routes

API endpoints for managing AWS Bedrock provider configurations.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.exceptions import ConfigurationError
from src.middleware.authorization import get_current_user
from src.models.bedrock_config import (
    AddBedrockModelRequest,
    BedrockConfigurationCreate,
    BedrockConfigurationResponse,
    BedrockConfigurationUpdate,
    BedrockConnectionTestResponse,
    BedrockModelDiscoveryResponse,
    BedrockModelInfo,
)
from src.models.database import get_db
from src.services.bedrock_model_utils import normalize_bedrock_models
from src.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/bedrock", tags=["AWS Bedrock"])


def get_bedrock_service(db: Session = Depends(get_db)) -> BedrockService:
    """Dependency to get Bedrock service instance."""
    return BedrockService(db)


def _build_bedrock_model_info_list(
    config_data: dict,
    *,
    context: str,
) -> list[BedrockModelInfo]:
    """Normalize stored model payloads into BedrockModelInfo list."""
    normalized_models = normalize_bedrock_models(
        config_data.get("available_models", []),
        logger=logger,
        context=context,
    )
    return [BedrockModelInfo(**m) for m in normalized_models]


@router.post(
    "/configurations",
    response_model=BedrockConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Bedrock Configuration",
    description="Create a new AWS Bedrock provider configuration for the current user.",
)
async def create_bedrock_configuration(
    config: BedrockConfigurationCreate,
    current_user=Depends(get_current_user),
    service: BedrockService = Depends(get_bedrock_service),
):
    """
    Create a new AWS Bedrock configuration.

    Supports two authentication methods:
    - **api_keys**: Requires AWS Access Key ID and Secret Access Key
    - **iam_role**: Uses IAM role from EC2/ECS instance (no keys required)

    **Permissions**: Requires authenticated user
    """
    try:
        customer_id = current_user.customer_id

        provider = service.create_bedrock_config(customer_id=customer_id, config=config)

        # Build response
        config_data = provider.config_data or {}
        return BedrockConfigurationResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            auth_method=config_data.get("auth_method", "api_keys"),
            aws_region=config_data.get("aws_region", "us-west-2"),
            base_url=config_data.get("base_url", ""),
            available_models=_build_bedrock_model_info_list(
                config_data,
                context=f"bedrock_route_create config_id={provider.id}",
            ),
            default_model=config_data.get("default_model"),
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            connection_timeout=config_data.get("connection_timeout", 30),
            max_retries=config_data.get("max_retries", 3),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    except ConfigurationError as e:
        logger.error(f"Configuration error creating Bedrock config: {e!s}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating Bedrock config: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Bedrock configuration: {e!s}",
        )


@router.get(
    "/configurations",
    response_model=list[BedrockConfigurationResponse],
    summary="List Bedrock Configurations",
    description="List all AWS Bedrock configurations for the current user.",
)
async def list_bedrock_configurations(
    current_user=Depends(get_current_user), service: BedrockService = Depends(get_bedrock_service)
):
    """
    List all Bedrock configurations for the current user.

    **Permissions**: Requires authenticated user
    """
    try:
        customer_id = current_user.customer_id
        providers = service.list_bedrock_configs(customer_id)

        # Build responses
        responses = []
        for provider in providers:
            config_data = provider.config_data or {}
            responses.append(
                BedrockConfigurationResponse(
                    id=provider.id,
                    customer_id=provider.customer_id,
                    auth_method=config_data.get("auth_method", "api_keys"),
                    aws_region=config_data.get("aws_region", "us-west-2"),
                    base_url=config_data.get("base_url", ""),
                    available_models=_build_bedrock_model_info_list(
                        config_data,
                        context=f"bedrock_route_list config_id={provider.id}",
                    ),
                    default_model=config_data.get("default_model"),
                    is_enabled=provider.is_enabled,
                    is_healthy=provider.is_healthy,
                    last_health_check=provider.last_health_check,
                    connection_timeout=config_data.get("connection_timeout", 30),
                    max_retries=config_data.get("max_retries", 3),
                    created_at=provider.created_at,
                    updated_at=provider.updated_at,
                )
            )

        return responses

    except Exception as e:
        logger.error(f"Error listing Bedrock configs: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list Bedrock configurations: {e!s}",
        )


@router.get(
    "/configurations/{config_id}",
    response_model=BedrockConfigurationResponse,
    summary="Get Bedrock Configuration",
    description="Get a specific AWS Bedrock configuration by ID.",
)
async def get_bedrock_configuration(
    config_id: int,
    current_user=Depends(get_current_user),
    service: BedrockService = Depends(get_bedrock_service),
):
    """
    Get a specific Bedrock configuration.

    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        provider = service.get_bedrock_config(config_id, customer_id)

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bedrock configuration {config_id} not found",
            )

        # Build response
        config_data = provider.config_data or {}
        return BedrockConfigurationResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            auth_method=config_data.get("auth_method", "api_keys"),
            aws_region=config_data.get("aws_region", "us-west-2"),
            base_url=config_data.get("base_url", ""),
            available_models=_build_bedrock_model_info_list(
                config_data,
                context=f"bedrock_route_get config_id={provider.id}",
            ),
            default_model=config_data.get("default_model"),
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            connection_timeout=config_data.get("connection_timeout", 30),
            max_retries=config_data.get("max_retries", 3),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Bedrock config {config_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Bedrock configuration: {e!s}",
        )


@router.put(
    "/configurations/{config_id}",
    response_model=BedrockConfigurationResponse,
    summary="Update Bedrock Configuration",
    description="Update an existing AWS Bedrock configuration.",
)
async def update_bedrock_configuration(
    config_id: int,
    update_data: BedrockConfigurationUpdate,
    current_user=Depends(get_current_user),
    service: BedrockService = Depends(get_bedrock_service),
):
    """
    Update a Bedrock configuration.

    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        provider = service.update_bedrock_config(config_id, customer_id, update_data)

        # Build response
        config_data = provider.config_data or {}
        return BedrockConfigurationResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            auth_method=config_data.get("auth_method", "api_keys"),
            aws_region=config_data.get("aws_region", "us-west-2"),
            base_url=config_data.get("base_url", ""),
            available_models=_build_bedrock_model_info_list(
                config_data,
                context=f"bedrock_route_update config_id={provider.id}",
            ),
            default_model=config_data.get("default_model"),
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            connection_timeout=config_data.get("connection_timeout", 30),
            max_retries=config_data.get("max_retries", 3),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    except ConfigurationError as e:
        logger.error(f"Configuration error updating Bedrock config: {e!s}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating Bedrock config {config_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update Bedrock configuration: {e!s}",
        )


@router.delete(
    "/configurations/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Bedrock Configuration",
    description="Delete an AWS Bedrock configuration.",
)
async def delete_bedrock_configuration(
    config_id: int,
    current_user=Depends(get_current_user),
    service: BedrockService = Depends(get_bedrock_service),
):
    """
    Delete a Bedrock configuration.

    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        deleted = service.delete_bedrock_config(config_id, customer_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bedrock configuration {config_id} not found",
            )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Bedrock config {config_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete Bedrock configuration: {e!s}",
        )


@router.post(
    "/configurations/{config_id}/test",
    response_model=BedrockConnectionTestResponse,
    summary="Test Bedrock Connection",
    description="Test AWS Bedrock connection for a configuration.",
)
async def test_bedrock_connection(
    config_id: int,
    current_user=Depends(get_current_user),
    service: BedrockService = Depends(get_bedrock_service),
):
    """
    Test Bedrock connection and credentials.

    Makes a test API call to AWS Bedrock to verify:
    - Credentials are valid
    - Region is accessible
    - Bedrock service is available

    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        test_result = service.test_bedrock_connection(config_id, customer_id)

        return BedrockConnectionTestResponse(
            success=test_result["success"],
            message=test_result["message"],
            region=test_result["region"],
            auth_method=test_result["auth_method"],
            response_time_ms=test_result.get("response_time_ms"),
            error_details=test_result.get("error_details"),
            tested_at=test_result["tested_at"],
        )

    except ConfigurationError as e:
        logger.error(f"Configuration error testing Bedrock connection: {e!s}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error testing Bedrock connection for config {config_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test Bedrock connection: {e!s}",
        )


@router.post(
    "/configurations/{config_id}/discover-models",
    response_model=BedrockModelDiscoveryResponse,
    summary="Discover Available Models",
    description="Discover available foundation models in AWS Bedrock using boto3 API.",
)
async def discover_bedrock_models(
    config_id: int,
    provider_filter: str | None = None,
    current_user=Depends(get_current_user),
    service: BedrockService = Depends(get_bedrock_service),
):
    """
    Discover available Bedrock models using AWS API.

    Uses boto3 to query AWS Bedrock and list all available foundation models
    in the configured region. Discovered models are NOT automatically added
    to the configuration - use the "add model" endpoint to add them.

    **Query Parameters**:
    - **provider_filter**: Filter by provider (e.g., 'anthropic', 'meta', 'amazon')

    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id

        # Get config to determine region
        provider = service.get_bedrock_config(config_id, customer_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bedrock configuration {config_id} not found",
            )

        # Discover models
        discovered_models = service.discover_models(
            config_id=config_id, customer_id=customer_id, provider_filter=provider_filter
        )

        config_data = provider.config_data or {}
        aws_region = config_data.get("aws_region", "us-west-2")

        return BedrockModelDiscoveryResponse(
            region=aws_region,
            discovered_models=discovered_models,
            total_count=len(discovered_models),
            discovery_timestamp=datetime.now(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error discovering Bedrock models for config {config_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover Bedrock models: {e!s}",
        )


@router.post(
    "/configurations/{config_id}/models",
    response_model=BedrockConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Model to Configuration",
    description="Add a discovered model to the Bedrock configuration's available models list.",
)
async def add_model_to_configuration(
    config_id: int,
    model_request: AddBedrockModelRequest,
    current_user=Depends(get_current_user),
    service: BedrockService = Depends(get_bedrock_service),
):
    """
    Add a model to the Bedrock configuration.

    After discovering models, use this endpoint to add them to your
    configuration's available models list. Added models can then be
    used for text generation.

    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        provider = service.add_model_to_config(config_id, customer_id, model_request)

        # Build response
        config_data = provider.config_data or {}
        return BedrockConfigurationResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            auth_method=config_data.get("auth_method", "api_keys"),
            aws_region=config_data.get("aws_region", "us-west-2"),
            base_url=config_data.get("base_url", ""),
            available_models=_build_bedrock_model_info_list(
                config_data,
                context=f"bedrock_route_add_model config_id={provider.id}",
            ),
            default_model=config_data.get("default_model"),
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            connection_timeout=config_data.get("connection_timeout", 30),
            max_retries=config_data.get("max_retries", 3),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    except ConfigurationError as e:
        logger.error(f"Configuration error adding model: {e!s}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding model to config {config_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add model: {e!s}"
        )


@router.delete(
    "/configurations/{config_id}/models/{model_id}",
    response_model=BedrockConfigurationResponse,
    summary="Remove Model from Configuration",
    description="Remove a model from the Bedrock configuration's available models list.",
)
async def remove_model_from_configuration(
    config_id: int,
    model_id: str,
    current_user=Depends(get_current_user),
    service: BedrockService = Depends(get_bedrock_service),
):
    """
    Remove a model from the Bedrock configuration.

    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        provider = service.remove_model_from_config(config_id, customer_id, model_id)

        # Build response
        config_data = provider.config_data or {}
        return BedrockConfigurationResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            auth_method=config_data.get("auth_method", "api_keys"),
            aws_region=config_data.get("aws_region", "us-west-2"),
            base_url=config_data.get("base_url", ""),
            available_models=_build_bedrock_model_info_list(
                config_data,
                context=f"bedrock_route_remove_model config_id={provider.id}",
            ),
            default_model=config_data.get("default_model"),
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            connection_timeout=config_data.get("connection_timeout", 30),
            max_retries=config_data.get("max_retries", 3),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    except ConfigurationError as e:
        logger.error(f"Configuration error removing model: {e!s}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing model from config {config_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove model: {e!s}",
        )
