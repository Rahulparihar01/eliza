"""
AI Enablement Platform - Unified Provider Configuration Routes

API endpoints for managing AI provider configurations across all types.
Supports OpenAI, Anthropic, Groq, AWS Bedrock, and more.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import os

from src.models.provider_config import (
    ProviderType,
    ProviderConfigurationCreate,
    ProviderConfigurationUpdate,
    ProviderConfigurationResponse,
    ProviderConnectionTestRequest,
    ProviderConnectionTestResponse,
    ProviderListResponse,
    AvailableProvidersResponse,
    FetchModelsRequest,
    FetchModelsResponse,
    ModelOption,
    PROVIDER_METADATA,
    TenantProviderResponse,
    TenantProviderListResponse,
)
from src.services.provider_service import ProviderService
from src.models.database import get_db
from src.models.customer import CustomerAIProvider, SharedAIProvider
from src.middleware.authorization import get_current_user
from src.core.exceptions import ConfigurationError
from src.core.auth_context import CurrentUserContext

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/providers", tags=["AI Providers"])


def get_provider_service(db: Session = Depends(get_db)) -> ProviderService:
    """Dependency to get provider service instance."""
    return ProviderService(db)


@router.get(
    "/available",
    response_model=AvailableProvidersResponse,
    summary="List Available Provider Types",
    description="Get information about all available provider types that can be configured."
)
async def list_available_providers(
    current_user=Depends(get_current_user)
):
    """
    List all available provider types.
    
    Returns metadata about each provider type including:
    - Required configuration fields
    - Available models
    - Authentication methods
    
    **Permissions**: Requires authenticated user
    """
    available = []
    
    for provider_type, metadata in PROVIDER_METADATA.items():
        available.append(
            AvailableProvidersResponse.ProviderTypeInfo(
                type=provider_type.value,
                name=metadata["name"],
                description=metadata["description"],
                requires_api_key=metadata["requires_api_key"],
                supports_models=metadata["default_models"],
                auth_methods=metadata["auth_methods"]
            )
        )
    
    return AvailableProvidersResponse(available_providers=available)


@router.post(
    "/fetch-models",
    response_model=FetchModelsResponse,
    summary="Fetch Available Models",
    description="Fetch available models from a provider using credentials (without saving configuration)."
)
async def fetch_provider_models(
    request: FetchModelsRequest,
    current_user=Depends(get_current_user),
    service: ProviderService = Depends(get_provider_service)
):
    """
    Fetch available models from a provider using temporary credentials.
    
    This endpoint allows you to validate credentials and see available models
    before creating a provider configuration.
    
    **Workflow**:
    1. User enters API credentials
    2. Call this endpoint to fetch available models
    3. User selects which models to enable
    4. Create provider configuration with selected models
    
    **Permissions**: Requires authenticated user
    """
    try:
        provider_type = ProviderType(request.provider_type)
        
        # Build credentials dict based on provider type
        credentials = {}
        if provider_type in [ProviderType.OPENAI, ProviderType.ANTHROPIC, ProviderType.GROQ]:
            if not request.api_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API key is required"
                )
            credentials['api_key'] = request.api_key
            if request.organization_id:
                credentials['organization_id'] = request.organization_id
        
        elif provider_type == ProviderType.BEDROCK:
            if not request.aws_access_key_id or not request.aws_secret_access_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AWS Access Key ID and Secret Access Key are required to fetch Bedrock models"
                )
            credentials['aws_region'] = request.aws_region or 'us-west-2'
            credentials['aws_access_key_id'] = request.aws_access_key_id
            credentials['aws_secret_access_key'] = request.aws_secret_access_key
            if request.aws_session_token:
                credentials['aws_session_token'] = request.aws_session_token

        # Fetch models from provider
        models = await service.fetch_available_models(provider_type, credentials)
        
        # Convert to ModelOption format
        model_options = [
            ModelOption(
                name=model.name,
                description=model.description,
                context_length=model.context_length,
                supports_functions=model.supports_functions,
                supports_vision=model.supports_vision
            )
            for model in models
        ]
        
        return FetchModelsResponse(
            success=True,
            provider_type=provider_type.value,
            models=model_options
        )
        
    except ValueError as e:
        logger.error(f"Invalid provider type: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider type: {request.provider_type}"
        )
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}")
        return FetchModelsResponse(
            success=False,
            provider_type=request.provider_type,
            models=[],
            error_message=str(e)
        )


@router.post(
    "/configurations",
    response_model=ProviderConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Provider Configuration",
    description="Create a new AI provider configuration (OpenAI, Anthropic, Groq, Bedrock, etc.)."
)
async def create_provider_configuration(
    config: ProviderConfigurationCreate,
    current_user=Depends(get_current_user),
    service: ProviderService = Depends(get_provider_service)
):
    """
    Create a new provider configuration.
    
    **Supported Providers**:
    - **openai**: OpenAI GPT models
    - **anthropic**: Anthropic Claude models  
    - **groq**: Groq fast inference
    - **bedrock**: AWS Bedrock foundation models
    
    **Example - OpenAI**:
    ```json
    {
      "provider_type": "openai",
      "name": "My OpenAI Config",
      "config": {
        "api_key": "sk-...",
        "available_models": ["gpt-4", "gpt-3.5-turbo"],
        "default_model": "gpt-4"
      }
    }
    ```
    
    **Example - Anthropic**:
    ```json
    {
      "provider_type": "anthropic",
      "name": "My Claude Config",
      "config": {
        "api_key": "sk-ant-...",
        "available_models": ["claude-3-opus-20240229"],
        "default_model": "claude-3-opus-20240229"
      }
    }
    ```
    
    **Permissions**: Requires authenticated user
    """
    try:
        customer_id = current_user.customer_id
        
        provider = service.create_provider_config(
            customer_id=customer_id,
            config_request=config
        )
        
        # Build response
        config_data = provider.config_data or {}
        return ProviderConfigurationResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_type=provider.provider_name,
            name=config.name,
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            config_summary=config_data,  # Sanitized (no API keys)
            available_models=config_data.get("available_models", []),
            default_model=config_data.get("default_model"),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            error_count=provider.error_count,
            last_error=provider.last_error
        )
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating provider config: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create provider configuration: {str(e)}"
        )


@router.get(
    "/configurations",
    response_model=ProviderListResponse,
    summary="List Provider Configurations",
    description="List all provider configurations for the current user."
)
async def list_provider_configurations(
    provider_type: Optional[ProviderType] = Query(
        None,
        description="Filter by provider type (openai, anthropic, groq, bedrock)"
    ),
    current_user=Depends(get_current_user),
    service: ProviderService = Depends(get_provider_service)
):
    """
    List all provider configurations.
    
    **Query Parameters**:
    - **provider_type**: Filter by provider type (optional)
    
    **Permissions**: Requires authenticated user
    """
    try:
        customer_id = current_user.customer_id
        providers = service.list_provider_configs(customer_id, provider_type)
        
        # Build responses
        responses = []
        by_type = {}
        
        for provider in providers:
            config_data = provider.config_data or {}
            
            # Count by type
            provider_type_str = provider.provider_name
            by_type[provider_type_str] = by_type.get(provider_type_str, 0) + 1
            
            responses.append(ProviderConfigurationResponse(
                id=provider.id,
                customer_id=provider.customer_id,
                provider_type=provider.provider_name,
                name=provider.name,
                is_enabled=provider.is_enabled,
                is_healthy=provider.is_healthy,
                last_health_check=provider.last_health_check,
                config_summary=config_data,
                available_models=config_data.get("available_models", []),
                default_model=config_data.get("default_model"),
                created_at=provider.created_at,
                updated_at=provider.updated_at,
                error_count=provider.error_count,
                last_error=provider.last_error
            ))
        
        return ProviderListResponse(
            providers=responses,
            total_count=len(responses),
            by_type=by_type
        )
        
    except Exception as e:
        logger.error(f"Error listing provider configs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list provider configurations: {str(e)}"
        )


# NOTE: This route MUST be defined BEFORE /configurations/{config_id} 
# to prevent FastAPI from matching "with-shared" as an integer config_id
@router.get(
    "/configurations/with-shared",
    response_model=TenantProviderListResponse,
    summary="List Provider Configurations Including Shared",
    description="List all provider configurations including shared platform providers."
)
async def list_provider_configurations_with_shared(
    provider_type: Optional[ProviderType] = Query(
        None,
        description="Filter by provider type (openai, anthropic, groq, bedrock)"
    ),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all provider configurations including shared ones from the platform.
    
    Returns:
    - Own providers: Full edit/delete access
    - Global shared providers: Read-only, can toggle enabled
    - Selectively shared providers: Read-only, can toggle enabled
    
    **Permissions**: Requires authenticated user
    """
    try:
        customer_id = current_user.customer_id
        logger.info(f"Listing providers with shared for customer_id: {customer_id}")
        
        responses = []
        by_type = {}
        own_count = 0
        shared_count = 0
        
        # 1. Get own providers
        own_query = db.query(CustomerAIProvider).filter(
            CustomerAIProvider.customer_id == customer_id
        )
        if provider_type:
            own_query = own_query.filter(CustomerAIProvider.provider_name == provider_type.value)
        
        own_providers = own_query.all()
        
        # Track provider IDs we've added to avoid duplicates
        added_provider_ids = set()
        
        for provider in own_providers:
            config_data = provider.config_data or {}
            provider_type_str = provider.provider_name
            by_type[provider_type_str] = by_type.get(provider_type_str, 0) + 1
            own_count += 1
            added_provider_ids.add(provider.id)
            
            responses.append(TenantProviderResponse(
                id=provider.id,
                customer_id=provider.customer_id,
                provider_type=provider.provider_name,
                name=provider.name,
                is_enabled=provider.is_enabled,
                is_healthy=provider.is_healthy,
                last_health_check=provider.last_health_check,
                config_summary=config_data,
                available_models=config_data.get("available_models", []),
                default_model=config_data.get("default_model"),
                is_shared_from_platform=False,
                is_editable=True,
                is_adoption_source=provider.is_adoption_source,
                chatgpt_workspace_id=provider.chatgpt_workspace_id,
                adoption_compliance_status=provider.adoption_compliance_status,
                adoption_compliance_last_checked=provider.adoption_compliance_last_checked,
                adoption_compliance_error=provider.adoption_compliance_error,
                created_at=provider.created_at,
                updated_at=provider.updated_at,
                error_count=provider.error_count,
                last_error=provider.last_error
            ))
        
        # 2. Get global shared providers (providers marked as is_global_shared from other tenants)
        global_query = db.query(CustomerAIProvider).filter(
            CustomerAIProvider.is_global_shared == True,
            CustomerAIProvider.customer_id != customer_id  # Exclude own providers
        )
        if provider_type:
            global_query = global_query.filter(CustomerAIProvider.provider_name == provider_type.value)
        
        global_providers = global_query.all()
        
        for provider in global_providers:
            if provider.id in added_provider_ids:
                continue
            
            config_data = provider.config_data or {}
            provider_type_str = provider.provider_name
            by_type[provider_type_str] = by_type.get(provider_type_str, 0) + 1
            shared_count += 1
            added_provider_ids.add(provider.id)
            
            responses.append(TenantProviderResponse(
                id=provider.id,
                customer_id=provider.customer_id,
                provider_type=provider.provider_name,
                name=f"{provider.name} (Platform)",
                is_enabled=provider.is_enabled,
                is_healthy=provider.is_healthy,
                last_health_check=provider.last_health_check,
                config_summary=config_data,
                available_models=config_data.get("available_models", []),
                default_model=config_data.get("default_model"),
                is_shared_from_platform=True,
                is_editable=False,
                is_adoption_source=False,  # Shared providers can't be adoption sources
                chatgpt_workspace_id=None,
                adoption_compliance_status=None,
                adoption_compliance_last_checked=None,
                adoption_compliance_error=None,
                created_at=provider.created_at,
                updated_at=provider.updated_at,
                error_count=provider.error_count,
                last_error=provider.last_error
            ))
        
        # 3. Get selectively shared providers (shared with this tenant specifically)
        shared_records = db.query(SharedAIProvider).filter(
            SharedAIProvider.target_customer_id == customer_id
        ).all()
        
        for share in shared_records:
            if share.source_provider_id in added_provider_ids:
                # Skip if already added (own provider or global)
                continue
            
            provider = db.query(CustomerAIProvider).filter(
                CustomerAIProvider.id == share.source_provider_id
            ).first()
            
            if not provider:
                continue
            
            if provider.is_global_shared:
                # Skip - should have been included as global provider
                continue
            
            if provider_type and provider.provider_name != provider_type.value:
                continue
            
            config_data = provider.config_data or {}
            provider_type_str = provider.provider_name
            by_type[provider_type_str] = by_type.get(provider_type_str, 0) + 1
            shared_count += 1
            added_provider_ids.add(provider.id)
            
            responses.append(TenantProviderResponse(
                id=provider.id,
                customer_id=provider.customer_id,
                provider_type=provider.provider_name,
                name=f"{provider.name} (Shared)",
                is_enabled=share.is_enabled,  # Use tenant's enabled status
                is_healthy=provider.is_healthy,
                last_health_check=provider.last_health_check,
                config_summary=config_data,
                available_models=config_data.get("available_models", []),
                default_model=config_data.get("default_model"),
                is_shared_from_platform=True,
                is_editable=False,
                is_adoption_source=False,  # Shared providers can't be adoption sources
                chatgpt_workspace_id=None,
                adoption_compliance_status=None,
                adoption_compliance_last_checked=None,
                adoption_compliance_error=None,
                created_at=provider.created_at,
                updated_at=provider.updated_at,
                error_count=provider.error_count,
                last_error=provider.last_error
            ))
        
        logger.info(f"Found {len(responses)} providers (own: {own_count}, shared: {shared_count})")
        
        result = TenantProviderListResponse(
            providers=responses,
            total_count=len(responses),
            own_count=own_count,
            shared_count=shared_count,
            by_type=by_type
        )
        logger.info(f"Successfully created response with {result.total_count} providers")
        return result
        
    except Exception as e:
        logger.error(f"Error listing provider configs with shared: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list provider configurations: {str(e)}"
        )


@router.get(
    "/configurations/{config_id}",
    response_model=ProviderConfigurationResponse,
    summary="Get Provider Configuration",
    description="Get a specific provider configuration by ID."
)
async def get_provider_configuration(
    config_id: int,
    current_user=Depends(get_current_user),
    service: ProviderService = Depends(get_provider_service)
):
    """
    Get a specific provider configuration.
    
    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        provider = service.get_provider_config(config_id, customer_id)
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider configuration {config_id} not found"
            )
        
        # Build response
        config_data = provider.config_data or {}
        return ProviderConfigurationResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_type=provider.provider_name,
            name=provider.name,
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            config_summary=config_data,
            available_models=config_data.get("available_models", []),
            default_model=config_data.get("default_model"),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            error_count=provider.error_count,
            last_error=provider.last_error
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider config {config_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get provider configuration: {str(e)}"
        )


@router.put(
    "/configurations/{config_id}",
    response_model=ProviderConfigurationResponse,
    summary="Update Provider Configuration",
    description="Update an existing provider configuration."
)
async def update_provider_configuration(
    config_id: int,
    update_data: ProviderConfigurationUpdate,
    current_user=Depends(get_current_user),
    service: ProviderService = Depends(get_provider_service)
):
    """
    Update a provider configuration.
    
    Can update:
    - is_enabled status
    - API keys/credentials
    - Available models
    - Default model
    
    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        provider = service.update_provider_config(config_id, customer_id, update_data)
        
        # Build response
        config_data = provider.config_data or {}
        return ProviderConfigurationResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_type=provider.provider_name,
            name=provider.name,
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            config_summary=config_data,
            available_models=config_data.get("available_models", []),
            default_model=config_data.get("default_model"),
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            error_count=provider.error_count,
            last_error=provider.last_error
        )
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating provider config {config_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update provider configuration: {str(e)}"
        )


@router.delete(
    "/configurations/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Provider Configuration",
    description="Delete a provider configuration."
)
async def delete_provider_configuration(
    config_id: int,
    current_user=Depends(get_current_user),
    service: ProviderService = Depends(get_provider_service)
):
    """
    Delete a provider configuration.
    
    **Warning**: This will remove the configuration and all associated settings.
    The provider will no longer be available for use.
    
    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        deleted = service.delete_provider_config(config_id, customer_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider configuration {config_id} not found"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting provider config {config_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete provider configuration: {str(e)}"
        )


@router.post(
    "/configurations/{config_id}/test",
    response_model=ProviderConnectionTestResponse,
    summary="Test Provider Connection",
    description="Test provider connection and credentials."
)
async def test_provider_connection(
    config_id: int,
    request: ProviderConnectionTestRequest = ProviderConnectionTestRequest(),
    current_user=Depends(get_current_user),
    service: ProviderService = Depends(get_provider_service)
):
    """
    Test provider connection.
    
    Makes a test API call to verify:
    - Credentials are valid
    - Provider is accessible
    - Models are available
    
    **Permissions**: Requires authenticated user (owner of configuration)
    """
    try:
        customer_id = current_user.customer_id
        test_result = await service.test_provider_connection(
            config_id,
            customer_id,
            request.test_prompt
        )
        
        return test_result
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error testing provider connection for config {config_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test provider connection: {str(e)}"
        )


# =============================================================================
# SHARED PROVIDER ENDPOINTS (For Tenant Admins)
# =============================================================================

@router.put(
    "/shared/{provider_id}/toggle",
    response_model=TenantProviderResponse,
    summary="Toggle Shared Provider",
    description="Enable or disable a shared provider for your tenant."
)
async def toggle_shared_provider(
    provider_id: int,
    is_enabled: bool = Query(..., description="Enable or disable the shared provider"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle a shared provider on/off for the current tenant.
    
    This allows tenant admins to disable shared providers they don't want to use
    without affecting other tenants.
    
    **Permissions**: Requires authenticated user
    """
    try:
        customer_id = current_user.customer_id
        
        # Find the sharing record
        share = db.query(SharedAIProvider).filter(
            SharedAIProvider.source_provider_id == provider_id,
            SharedAIProvider.target_customer_id == customer_id
        ).first()
        
        if not share:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shared provider not found for your tenant"
            )
        
        # Update enabled status
        share.is_enabled = is_enabled
        db.commit()
        
        # Get provider details for response
        provider = db.query(CustomerAIProvider).filter(
            CustomerAIProvider.id == provider_id
        ).first()
        
        config_data = provider.config_data or {}
        return TenantProviderResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_type=provider.provider_name,
            name=f"{provider.name} (Shared)",
            is_enabled=share.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            config_summary=config_data,
            available_models=config_data.get("available_models", []),
            default_model=config_data.get("default_model"),
            is_shared_from_platform=True,
            is_editable=False,
            is_adoption_source=False,  # Shared providers can't be adoption sources
            chatgpt_workspace_id=None,
            adoption_compliance_status=None,
            adoption_compliance_last_checked=None,
            adoption_compliance_error=None,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            error_count=provider.error_count,
            last_error=provider.last_error
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling shared provider {provider_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle shared provider: {str(e)}"
        )


# =============================================================================
# ADOPTION SETTINGS (Tenant-Level)
# =============================================================================

from pydantic import BaseModel as PydanticBaseModel

class AdoptionSettingsUpdate(PydanticBaseModel):
    """Request to update adoption settings for a provider."""
    is_adoption_source: bool
    chatgpt_workspace_id: Optional[str] = None


@router.put(
    "/configurations/{config_id}/adoption",
    response_model=TenantProviderResponse,
    summary="Update Adoption Settings",
    description="Update adoption tracking settings for a provider configuration."
)
async def update_provider_adoption_settings(
    config_id: int,
    request: AdoptionSettingsUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update adoption tracking settings for a tenant's provider configuration.
    
    Rules:
    - Only own providers (not shared) can be marked as adoption sources
    - Only one provider per provider_type can be marked as adoption source
    - Enabling adoption on one provider auto-disables it on others of same type
    
    **Permissions**: Requires authenticated user with tenant admin access
    """
    try:
        customer_id = current_user.customer_id
        
        # Get the provider and verify ownership
        provider = db.query(CustomerAIProvider).filter(
            CustomerAIProvider.id == config_id,
            CustomerAIProvider.customer_id == customer_id
        ).first()
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider configuration not found or not owned by your tenant"
            )
        
        # Check if trying to enable adoption
        if request.is_adoption_source:
            # Disable adoption on other providers of the same type for this tenant
            db.query(CustomerAIProvider).filter(
                CustomerAIProvider.customer_id == customer_id,
                CustomerAIProvider.provider_name == provider.provider_name,
                CustomerAIProvider.id != config_id,
                CustomerAIProvider.is_adoption_source == True
            ).update({"is_adoption_source": False}, synchronize_session=False)
        
        # Update the provider
        provider.is_adoption_source = request.is_adoption_source
        if request.chatgpt_workspace_id is not None:
            provider.chatgpt_workspace_id = request.chatgpt_workspace_id
        
        db.commit()
        db.refresh(provider)
        
        config_data = provider.config_data or {}
        return TenantProviderResponse(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_type=provider.provider_name,
            name=provider.name,
            is_enabled=provider.is_enabled,
            is_healthy=provider.is_healthy,
            last_health_check=provider.last_health_check,
            config_summary=config_data,
            available_models=config_data.get("available_models", []),
            default_model=config_data.get("default_model"),
            is_shared_from_platform=False,
            is_editable=True,
            is_adoption_source=provider.is_adoption_source,
            chatgpt_workspace_id=provider.chatgpt_workspace_id,
            adoption_compliance_status=provider.adoption_compliance_status,
            adoption_compliance_last_checked=provider.adoption_compliance_last_checked,
            adoption_compliance_error=provider.adoption_compliance_error,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            error_count=provider.error_count,
            last_error=provider.last_error
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating adoption settings for provider {config_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update adoption settings: {str(e)}"
        )


# =============================================================================
# COMPLIANCE API TEST
# =============================================================================

class ComplianceTestRequest(PydanticBaseModel):
    """Request to test Compliance API access."""
    api_key: str
    workspace_id: str


class ComplianceTestResponse(PydanticBaseModel):
    """Response from Compliance API test."""
    success: bool
    message: str
    error_code: Optional[str] = None
    instructions: Optional[str] = None


@router.post(
    "/test-compliance-api",
    response_model=ComplianceTestResponse,
    summary="Test Compliance API Access",
    description="Test if an API key has access to the ChatGPT Enterprise Compliance API."
)
async def test_compliance_api(
    request: ComplianceTestRequest,
    current_user=Depends(get_current_user)
):
    """
    Test if an API key has access to the ChatGPT Enterprise Compliance API.
    
    This checks:
    - API key is valid
    - Workspace ID is valid
    - API key has compliance_export scope
    
    Returns success/failure with helpful instructions if the key lacks access.
    """
    import httpx
    
    try:
        headers = {
            'Authorization': f'Bearer {request.api_key}',
            'Content-Type': 'application/json'
        }
        
        url = f'https://api.chatgpt.com/v1/compliance/workspaces/{request.workspace_id}/users'
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params={"limit": 1})
            
            if response.status_code == 200:
                return ComplianceTestResponse(
                    success=True,
                    message="✅ Compliance API access confirmed! Your API key has the required scope."
                )
            elif response.status_code == 403:
                error_detail = response.json().get("detail", "")
                
                if "not authorized for enterprise logs" in error_detail.lower():
                    return ComplianceTestResponse(
                        success=False,
                        message="API key not authorized for Compliance API",
                        error_code="NO_COMPLIANCE_SCOPE",
                        instructions="""Your API key needs the 'compliance_export' scope to access adoption metrics.

**To enable this:**

1. **Email OpenAI Support** at support@openai.com with:
   - Last 4 digits of your API key
   - Key Name (from OpenAI Platform)
   - Created By Name
   - Request: "Please enable the compliance_export scope for enterprise logs access"

2. **Wait for confirmation** (usually 1-3 business days)

3. **Return here and test again** once OpenAI confirms the scope is enabled

Note: The API key must belong to a ChatGPT Enterprise organization with the Compliance API enabled."""
                    )
                else:
                    return ComplianceTestResponse(
                        success=False,
                        message=f"Access denied: {error_detail}",
                        error_code="FORBIDDEN",
                        instructions="Check that your workspace ID is correct and your API key belongs to the same organization."
                    )
            elif response.status_code == 401:
                return ComplianceTestResponse(
                    success=False,
                    message="Invalid API key",
                    error_code="INVALID_KEY",
                    instructions="The API key is invalid or expired. Please check the key and try again."
                )
            elif response.status_code == 404:
                return ComplianceTestResponse(
                    success=False,
                    message="Workspace not found",
                    error_code="INVALID_WORKSPACE",
                    instructions="The workspace ID is invalid. Find your correct workspace ID in the ChatGPT Enterprise admin console under Settings."
                )
            else:
                return ComplianceTestResponse(
                    success=False,
                    message=f"Unexpected response: {response.status_code}",
                    error_code="UNKNOWN_ERROR",
                    instructions=f"Response: {response.text[:200]}"
                )
                
    except httpx.TimeoutException:
        return ComplianceTestResponse(
            success=False,
            message="Request timed out",
            error_code="TIMEOUT",
            instructions="The Compliance API did not respond in time. Please try again."
        )
    except Exception as e:
        logger.error(f"Error testing compliance API: {str(e)}")
        return ComplianceTestResponse(
            success=False,
            message=f"Connection error: {str(e)}",
            error_code="CONNECTION_ERROR",
            instructions="Could not connect to the Compliance API. Check your network connection."
        )


@router.post(
    "/configurations/{config_id}/test-compliance",
    response_model=ComplianceTestResponse,
    summary="Test Compliance API for Saved Provider",
    description="Test if a saved provider configuration has access to the ChatGPT Enterprise Compliance API."
)
async def test_compliance_for_provider(
    config_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Test if a saved provider configuration has access to the ChatGPT Enterprise Compliance API.
    
    Uses the stored API key and workspace ID from the provider configuration.
    Saves the test result to the database for persistence.
    """
    import httpx
    import json
    from datetime import datetime
    from src.utils.encryption import decrypt_value
    
    # Get the provider configuration
    provider = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.id == config_id,
        CustomerAIProvider.customer_id == current_user.customer_id
    ).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider configuration not found"
        )
    
    if provider.provider_name != 'openai':
        return ComplianceTestResponse(
            success=False,
            message="Compliance API is only available for OpenAI providers",
            error_code="WRONG_PROVIDER",
            instructions="Adoption tracking is currently only available for OpenAI providers."
        )
    
    if not provider.is_adoption_source:
        return ComplianceTestResponse(
            success=False,
            message="Adoption tracking is not enabled for this provider",
            error_code="NOT_ADOPTION_SOURCE",
            instructions="Enable adoption tracking first, then test the compliance API access."
        )
    
    if not provider.chatgpt_workspace_id:
        # Save untested status
        provider.adoption_compliance_status = 'untested'
        provider.adoption_compliance_last_checked = datetime.utcnow()
        provider.adoption_compliance_error = 'Workspace ID not configured'
        db.commit()
        return ComplianceTestResponse(
            success=False,
            message="Workspace ID not configured",
            error_code="MISSING_WORKSPACE_ID",
            instructions="Please enter your ChatGPT Workspace ID first, then test compliance access."
        )
    
    # Decrypt the API key
    try:
        creds = json.loads(decrypt_value(provider.api_key_encrypted))
        api_key = creds.get('api_key', '')
        if not api_key:
            provider.adoption_compliance_status = 'failed'
            provider.adoption_compliance_last_checked = datetime.utcnow()
            provider.adoption_compliance_error = 'API key not found in configuration'
            db.commit()
            return ComplianceTestResponse(
                success=False,
                message="API key not found in configuration",
                error_code="MISSING_API_KEY",
                instructions="The provider configuration is missing an API key."
            )
    except Exception as e:
        logger.error(f"Error decrypting API key: {str(e)}")
        provider.adoption_compliance_status = 'failed'
        provider.adoption_compliance_last_checked = datetime.utcnow()
        provider.adoption_compliance_error = 'Could not decrypt API key'
        db.commit()
        return ComplianceTestResponse(
            success=False,
            message="Could not decrypt API key",
            error_code="DECRYPTION_ERROR",
            instructions="There was an error reading the stored API key. Please reconfigure the provider."
        )
    
    # Test the Compliance API
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        url = f'https://api.chatgpt.com/v1/compliance/workspaces/{provider.chatgpt_workspace_id}/users'
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params={"limit": 1})
            
            if response.status_code == 200:
                # Success! Save the status
                provider.adoption_compliance_status = 'success'
                provider.adoption_compliance_last_checked = datetime.utcnow()
                provider.adoption_compliance_error = None
                db.commit()
                return ComplianceTestResponse(
                    success=True,
                    message="✅ Compliance API access confirmed! Your API key has the required scope."
                )
            elif response.status_code == 403:
                error_detail = response.json().get("detail", "")
                
                if "not authorized for enterprise logs" in error_detail.lower():
                    error_msg = "API key not authorized for Compliance API"
                    instructions = """Your API key needs the 'compliance_export' scope to access adoption metrics.

**To enable this:**

1. **Email OpenAI Support** at support@openai.com with:
   - Last 4 digits of your API key
   - Key Name (from OpenAI Platform)
   - Created By Name
   - Request: "Please enable the compliance_export scope for enterprise logs access"

2. **Wait for confirmation** (usually 1-3 business days)

3. **Return here and test again** once OpenAI confirms the scope is enabled

Note: The API key must belong to a ChatGPT Enterprise organization with the Compliance API enabled."""
                    provider.adoption_compliance_status = 'failed'
                    provider.adoption_compliance_last_checked = datetime.utcnow()
                    provider.adoption_compliance_error = error_msg
                    db.commit()
                    return ComplianceTestResponse(
                        success=False,
                        message=error_msg,
                        error_code="NO_COMPLIANCE_SCOPE",
                        instructions=instructions
                    )
                else:
                    error_msg = f"Access denied: {error_detail}"
                    provider.adoption_compliance_status = 'failed'
                    provider.adoption_compliance_last_checked = datetime.utcnow()
                    provider.adoption_compliance_error = error_msg
                    db.commit()
                    return ComplianceTestResponse(
                        success=False,
                        message=error_msg,
                        error_code="FORBIDDEN",
                        instructions="Check that your workspace ID is correct and your API key belongs to the same organization."
                    )
            elif response.status_code == 401:
                error_msg = "Invalid API key"
                provider.adoption_compliance_status = 'failed'
                provider.adoption_compliance_last_checked = datetime.utcnow()
                provider.adoption_compliance_error = error_msg
                db.commit()
                return ComplianceTestResponse(
                    success=False,
                    message=error_msg,
                    error_code="INVALID_KEY",
                    instructions="The stored API key is invalid or expired. Please update the provider configuration with a valid key."
                )
            elif response.status_code == 404:
                error_msg = "Workspace not found"
                provider.adoption_compliance_status = 'failed'
                provider.adoption_compliance_last_checked = datetime.utcnow()
                provider.adoption_compliance_error = error_msg
                db.commit()
                return ComplianceTestResponse(
                    success=False,
                    message=error_msg,
                    error_code="INVALID_WORKSPACE",
                    instructions="The workspace ID is invalid. Update the workspace ID in the settings above."
                )
            else:
                error_msg = f"Unexpected response: {response.status_code}"
                provider.adoption_compliance_status = 'failed'
                provider.adoption_compliance_last_checked = datetime.utcnow()
                provider.adoption_compliance_error = error_msg
                db.commit()
                return ComplianceTestResponse(
                    success=False,
                    message=error_msg,
                    error_code="UNKNOWN_ERROR",
                    instructions=f"Response: {response.text[:200]}"
                )
                
    except httpx.TimeoutException:
        error_msg = "Request timed out"
        provider.adoption_compliance_status = 'failed'
        provider.adoption_compliance_last_checked = datetime.utcnow()
        provider.adoption_compliance_error = error_msg
        db.commit()
        return ComplianceTestResponse(
            success=False,
            message=error_msg,
            error_code="TIMEOUT",
            instructions="The Compliance API did not respond in time. Please try again."
        )
    except Exception as e:
        logger.error(f"Error testing compliance API for provider {config_id}: {str(e)}")
        error_msg = f"Connection error: {str(e)}"
        provider.adoption_compliance_status = 'failed'
        provider.adoption_compliance_last_checked = datetime.utcnow()
        provider.adoption_compliance_error = error_msg
        db.commit()
        return ComplianceTestResponse(
            success=False,
            message=error_msg,
            error_code="CONNECTION_ERROR",
            instructions="Could not connect to the Compliance API. Check your network connection."
        )

