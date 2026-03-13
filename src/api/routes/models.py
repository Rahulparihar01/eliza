"""
AI Enablement Platform - Model Management Routes

API endpoints for managing AI models and providers.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.auth_context import CurrentUserContext
from src.core.config import get_customer_config, get_settings
from src.core.exceptions import ModelProviderError
from src.middleware.authorization import get_current_user
from src.models.customer import CustomerAIProvider
from src.models.database import get_db
from src.models.model_info import ModelInfo as ModelInfoModel
from src.models.model_info import ModelTestRequest, ModelTestResponse
from src.models.model_info import ProviderStatus as ProviderStatusModel
from src.services.bedrock_model_utils import normalize_bedrock_models
from src.services.model_service import ModelService

logger = logging.getLogger(__name__)
router = APIRouter()


# Use the models from the models module
ModelInfo = ModelInfoModel
ProviderStatus = ProviderStatusModel


class ModelListResponse(BaseModel):
    """Response for listing available models."""

    providers: list[ProviderStatusModel]
    default_provider: str
    fallback_providers: list[str]
    total_models: int


class ModelTestRequest(BaseModel):
    """Request for testing a model."""

    provider: str
    model: str
    test_prompt: str = "Hello, this is a test message. Please respond with 'Test successful'."


class ModelTestResponse(BaseModel):
    """Response for model testing."""

    success: bool
    provider: str
    model: str
    response_text: str | None = None
    response_time_ms: float | None = None
    error_message: str | None = None
    tokens_used: int | None = None


class RAGChatModelOption(BaseModel):
    """Single model option for RAG chat (inference) selection. id is the value to store (LiteLLM model string)."""

    id: str = Field(
        description="Model ID to use in API (e.g. gpt-4o-mini or bedrock/anthropic.claude-3-sonnet-20240229-v1:0)"
    )
    name: str = Field(description="Display name")
    provider: str = Field(description="Provider key for grouping (e.g. openai, bedrock)")


class RAGChatModelsResponse(BaseModel):
    """List of models available for RAG chat inference (includes Bedrock when configured)."""

    models: list[RAGChatModelOption]


def get_model_service() -> ModelService:
    """Dependency to get model service instance (uses settings.customer_id)."""
    settings = get_settings()
    customer_config = get_customer_config(settings.customer_id)
    return ModelService(settings, customer_config)


def get_model_service_for_user(
    current_user: CurrentUserContext = Depends(get_current_user),
) -> ModelService:
    """Dependency that returns model service scoped to the current user's customer (for tenant-aware model lists)."""
    settings = get_settings()
    customer_config = get_customer_config(current_user.customer_id)
    return ModelService(settings, customer_config)


@router.get("/", response_model=ModelListResponse)
async def list_models(model_service: ModelService = Depends(get_model_service_for_user)):
    """
    List all available AI models and providers.

    Returns information about configured providers, their status,
    and available models.
    """
    try:
        providers_info = await model_service.get_providers_status()
        customer_config = model_service.customer_config

        return ModelListResponse(
            providers=providers_info,
            default_provider=customer_config.get_default_provider(),
            fallback_providers=customer_config.get_fallback_providers(),
            total_models=sum(len(p.models) for p in providers_info),
        )

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve model information: {e!s}")


@router.get("/for-rag", response_model=RAGChatModelsResponse)
async def list_models_for_rag(
    model_service: ModelService = Depends(get_model_service_for_user),
    db: Session = Depends(get_db),
):
    """
    List models suitable for RAG chat inference.

    Aggregates from all configured providers (OpenAI, Anthropic, Groq, Bedrock).
    Bedrock models are included from both ModelService and from stored Bedrock
    configs (config_data.available_models) so that any Bedrock config with
    discovered/added models appears in the dropdown.
    Bedrock model ids are prefixed with 'bedrock/' for LiteLLM routing.
    """
    try:
        providers_info = await model_service.get_providers_status()
        options: list[RAGChatModelOption] = []
        option_ids: set = set()

        # From ModelService (OpenAI, Anthropic, Groq, and Bedrock if provider returned models)
        for prov in providers_info:
            if not prov.models:
                continue
            is_bedrock = prov.name.lower().startswith("bedrock")
            for m in prov.models:
                model_id = m.id or m.name
                if not model_id:
                    continue
                if is_bedrock and not model_id.startswith("bedrock/"):
                    model_id = f"bedrock/{model_id}"
                if model_id in option_ids:
                    continue
                option_ids.add(model_id)
                provider_key = "bedrock" if is_bedrock else prov.name.split("_")[0].lower()
                options.append(
                    RAGChatModelOption(
                        id=model_id,
                        name=m.name or model_id,
                        provider=provider_key,
                    )
                )

        # Merge Bedrock models from database (in case config has available_models but
        # ModelService Bedrock provider returned none, e.g. empty list at init)
        customer_id = model_service.customer_config.customer_id
        bedrock_configs = (
            db.query(CustomerAIProvider)
            .filter(
                CustomerAIProvider.customer_id == customer_id,
                CustomerAIProvider.provider_name == "bedrock",
                CustomerAIProvider.is_enabled == True,
            )
            .all()
        )
        if bedrock_configs:
            logger.debug(
                "for-rag: merging Bedrock configs for customer_id=%s, configs=%s",
                customer_id,
                [c.id for c in bedrock_configs],
            )
        for config in bedrock_configs:
            config_data = config.config_data or {}
            raw_models = config_data.get("available_models", [])
            normalized_models = normalize_bedrock_models(
                raw_models,
                logger=logger,
                context=f"for-rag config_id={config.id} customer_id={customer_id}",
            )
            logger.debug(
                "for-rag: config_id=%s raw_models=%s normalized_models=%s",
                config.id,
                len(raw_models) if isinstance(raw_models, list) else 0,
                len(normalized_models),
            )
            for m in normalized_models:
                if not m.get("is_enabled", True):
                    continue
                model_id_raw = m.get("model_id") or m.get("model_name")
                if not model_id_raw:
                    continue
                model_id = (
                    f"bedrock/{model_id_raw}"
                    if not model_id_raw.startswith("bedrock/")
                    else model_id_raw
                )
                if model_id in option_ids:
                    continue
                option_ids.add(model_id)
                options.append(
                    RAGChatModelOption(
                        id=model_id,
                        name=m.get("model_name") or model_id_raw,
                        provider="bedrock",
                    )
                )

        return RAGChatModelsResponse(models=options)
    except Exception as e:
        logger.error(f"Failed to list models for RAG: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve models for RAG: {e!s}",
        )


@router.get("/providers", response_model=list[ProviderStatus])
async def list_providers(model_service: ModelService = Depends(get_model_service_for_user)):
    """
    List all AI providers and their status.

    Returns detailed information about each configured provider.
    """
    try:
        providers_info = await model_service.get_providers_status()
        return providers_info

    except Exception as e:
        logger.error(f"Failed to list providers: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve provider information: {e!s}"
        )


@router.get("/providers/{provider_name}", response_model=ProviderStatus)
async def get_provider_status(
    provider_name: str, model_service: ModelService = Depends(get_model_service_for_user)
):
    """
    Get detailed status for a specific provider.

    Args:
        provider_name: Name of the provider (openai, anthropic, groq, together)
    """
    try:
        provider_status = await model_service.get_provider_status(provider_name)

        if not provider_status:
            raise HTTPException(
                status_code=404, detail=f"Provider '{provider_name}' not found or not configured"
            )

        return provider_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provider status for {provider_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve provider status: {e!s}")


@router.post("/test", response_model=ModelTestResponse)
async def test_model(
    request: ModelTestRequest, model_service: ModelService = Depends(get_model_service)
):
    """
    Test a specific model with a sample prompt.

    This endpoint allows testing connectivity and functionality
    of a specific model from a provider.
    """
    try:
        result = await model_service.test_model(
            provider=request.provider, model=request.model, test_prompt=request.test_prompt
        )

        return result

    except ModelProviderError as e:
        logger.warning(f"Model test failed for {request.provider}/{request.model}: {e.detail}")
        return ModelTestResponse(
            success=False, provider=request.provider, model=request.model, error_message=e.detail
        )

    except Exception as e:
        logger.error(f"Unexpected error testing model {request.provider}/{request.model}: {e}")
        return ModelTestResponse(
            success=False,
            provider=request.provider,
            model=request.model,
            error_message=f"Unexpected error: {e!s}",
        )


@router.get("/config", response_model=dict[str, Any])
async def get_model_configuration(model_service: ModelService = Depends(get_model_service)):
    """
    Get current model configuration for the customer.

    Returns the customer's model preferences and task-specific model assignments.
    """
    try:
        customer_config = model_service.customer_config
        model_config = customer_config.model_config

        return {
            "default_provider": customer_config.get_default_provider(),
            "fallback_providers": customer_config.get_fallback_providers(),
            "models": model_config.get("models", {}),
            "task_assignments": {
                "intent_analysis": customer_config.get_model_for_task("intent_analysis"),
                "context_enrichment": customer_config.get_model_for_task("context_enrichment"),
                "prompt_generation": customer_config.get_model_for_task("prompt_generation"),
                "embeddings": customer_config.get_model_for_task("embeddings"),
                "department_analysis": customer_config.get_model_for_task("department_analysis"),
                "skills_analysis": customer_config.get_model_for_task("skills_analysis"),
                "roi_calculation": customer_config.get_model_for_task("roi_calculation"),
                "personality_matching": customer_config.get_model_for_task("personality_matching"),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get model configuration: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve model configuration: {e!s}"
        )


@router.get("/health", response_model=dict[str, Any])
async def models_health_check(model_service: ModelService = Depends(get_model_service)):
    """
    Health check specifically for model services.

    Tests connectivity to all configured providers and returns status.
    """
    try:
        health_status = await model_service.health_check()
        return health_status

    except Exception as e:
        logger.error(f"Model health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Model services health check failed: {e!s}")
