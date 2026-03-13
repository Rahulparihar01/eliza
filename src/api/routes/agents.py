"""API routes for agent configuration management."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from src.models.database import get_db
from src.middleware.authorization import get_current_user, require_permission
from src.services.agent_configuration_service import AgentConfigurationService
from src.models.agent_configuration import AgentConfiguration
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/agents", tags=["Agent Configuration"])


# --- Schemas ---

class AgentConfigUpdateRequest(BaseModel):
    """Request to update agent configuration."""
    role: Optional[str] = Field(None, description="Agent's role description")
    goal: Optional[str] = Field(None, description="Agent's goal")
    backstory: Optional[str] = Field(None, description="Agent's backstory")
    model_id: Optional[str] = Field(None, description="Model to use (e.g., 'gpt-4')")
    provider_config_id: Optional[int] = Field(None, description="Provider configuration ID")
    provider_name: Optional[str] = Field(None, description="Provider configuration name (alternative to ID)")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature (0.0-2.0)")
    max_tokens: Optional[int] = Field(None, ge=1, le=32000, description="Maximum tokens")
    enabled_tools: Optional[List[str]] = Field(None, description="List of enabled tool names")
    tool_configs: Optional[dict] = Field(None, description="Tool-specific configurations")


class AgentConfigResponse(BaseModel):
    """Response with agent configuration details."""
    customer_id: str
    flow_identifier: str
    agent_identifier: str
    role: str
    goal: str
    backstory: str
    model_id: str
    provider_config_id: int
    provider_name: str  # Friendly name for display
    temperature: float
    max_tokens: int
    enabled_tools: List[str]
    is_enabled: bool
    version: int
    source: str  # "default", "override", "merged"


class FlowInfo(BaseModel):
    """Information about a flow."""
    flow_identifier: str
    flow_name: str
    agent_count: int


class AgentInfo(BaseModel):
    """Information about an agent."""
    agent_identifier: str
    agent_name: str
    current_model: str
    current_provider: str


# --- Endpoints ---

@router.get("/flows", response_model=List[FlowInfo], summary="List all flows")
async def list_flows(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List all available CrewAI flows.
    
    Returns basic information about each flow including the number of agents.
    """
    # Hardcoded for now, could be dynamic in the future via introspection
    return [
        {
            "flow_identifier": "data_analysis_flow",
            "flow_name": "Data Analysis Flow",
            "agent_count": 2
        },
        {
            "flow_identifier": "task_enrichment_flow",
            "flow_name": "Task Enrichment Flow",
            "agent_count": 2
        }
    ]


@router.get(
    "/flows/{flow_id}/agents", 
    response_model=List[AgentInfo],
    summary="List agents in a flow"
)
async def list_agents_in_flow(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List all agents in a specific flow.
    
    Returns current configuration for each agent including the model and provider being used.
    """
    config_service = AgentConfigurationService(db)
    
    # Get agent identifiers for this flow
    agent_ids = {
        "data_analysis_flow": ["data_retrieval_agent", "bi_analyst_agent"],
        "task_enrichment_flow": ["task_analyzer_agent", "enrichment_agent"]
    }.get(flow_id, [])
    
    if not agent_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow '{flow_id}' not found"
        )
    
    agents = []
    for agent_id in agent_ids:
        try:
            config = config_service.get_complete_agent_config(
                customer_id=current_user.customer_id,
                flow_identifier=flow_id,
                agent_identifier=agent_id
            )
            agents.append({
                "agent_identifier": agent_id,
                "agent_name": config.role,
                "current_model": config.model_id,
                "current_provider": config.provider_name
            })
        except ConfigurationError as e:
            logger.error(f"Failed to load config for {flow_id}.{agent_id}: {e}")
            # Return with default values
            agents.append({
                "agent_identifier": agent_id,
                "agent_name": agent_id.replace("_", " ").title(),
                "current_model": "Not configured",
                "current_provider": "Not configured"
            })
    
    return agents


@router.get(
    "/configurations",
    response_model=List[AgentConfigResponse],
    summary="List all agent configuration overrides"
)
async def list_all_configurations(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List all agent configuration overrides for the current customer.
    
    Only returns agents that have database overrides (not code defaults).
    """
    from src.models.agent_configuration import AgentConfiguration
    
    # Query all configs for this customer
    configs = db.query(AgentConfiguration).filter(
        AgentConfiguration.customer_id == current_user.customer_id,
        AgentConfiguration.is_enabled == True
    ).all()
    
    if not configs:
        # Return empty list instead of 404
        return []
    
    # Build response for each config
    result = []
    config_service = AgentConfigurationService(db)
    
    for db_config in configs:
        try:
            # Get complete merged config
            complete_config = config_service.get_complete_agent_config(
                customer_id=current_user.customer_id,
                flow_identifier=db_config.flow_identifier,
                agent_identifier=db_config.agent_identifier
            )
            
            result.append({
                "customer_id": current_user.customer_id,
                "flow_identifier": db_config.flow_identifier,
                "agent_identifier": db_config.agent_identifier,
                "role": complete_config.role,
                "goal": complete_config.goal,
                "backstory": complete_config.backstory,
                "model_id": complete_config.model_id,
                "provider_config_id": complete_config.provider_config_id,
                "provider_name": complete_config.provider_name,
                "temperature": complete_config.temperature,
                "max_tokens": complete_config.max_tokens,
                "enabled_tools": complete_config.enabled_tools,
                "is_enabled": db_config.is_enabled,
                "version": complete_config.version,
                "source": complete_config.source
            })
        except Exception as e:
            # Log error but continue with other configs
            logger.error(f"Error loading config for {db_config.flow_identifier}.{db_config.agent_identifier}: {str(e)}")
            continue
    
    return result


@router.get(
    "/configurations/{flow_id}/{agent_id}",
    response_model=AgentConfigResponse,
    summary="Get agent configuration"
)
async def get_agent_configuration(
    flow_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get current agent configuration (merged: database overrides + code defaults).
    
    This returns the complete configuration that will be used at runtime.
    """
    config_service = AgentConfigurationService(db)
    
    try:
        config = config_service.get_complete_agent_config(
            customer_id=current_user.customer_id,
            flow_identifier=flow_id,
            agent_identifier=agent_id
        )
    except ConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    return {
        "customer_id": current_user.customer_id,
        "flow_identifier": flow_id,
        "agent_identifier": agent_id,
        "role": config.role,
        "goal": config.goal,
        "backstory": config.backstory,
        "model_id": config.model_id,
        "provider_config_id": config.provider_config_id,
        "provider_name": config.provider_name,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "enabled_tools": config.enabled_tools,
        "is_enabled": True,
        "version": config.version,
        "source": config.source
    }


@router.put(
    "/configurations/{flow_id}/{agent_id}",
    response_model=AgentConfigResponse,
    summary="Update agent configuration"
)
async def update_agent_configuration(
    flow_id: str,
    agent_id: str,
    request: AgentConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("labs:agents:configure"))
):
    """
    Update agent configuration.
    
    Changes take effect immediately on next execution. Cache is automatically invalidated.
    
    Provider resolution:
    - If provider_config_id is specified, uses that provider
    - If provider_name is specified, looks up provider by name
    - Otherwise, auto-selects provider based on model and priority
    """
    config_service = AgentConfigurationService(db)
    
    try:
        db_config = config_service.set_agent_config(
            customer_id=current_user.customer_id,
            flow_identifier=flow_id,
            agent_identifier=agent_id,
            config=request.dict(exclude_unset=True),
            updated_by="ui",
            user_id=current_user.user_id
        )
        
        # Return merged config (what will actually be used)
        merged_config = config_service.get_complete_agent_config(
            customer_id=current_user.customer_id,
            flow_identifier=flow_id,
            agent_identifier=agent_id
        )
        
        return {
            "customer_id": current_user.customer_id,
            "flow_identifier": flow_id,
            "agent_identifier": agent_id,
            "role": merged_config.role,
            "goal": merged_config.goal,
            "backstory": merged_config.backstory,
            "model_id": merged_config.model_id,
            "provider_config_id": merged_config.provider_config_id,
            "provider_name": merged_config.provider_name,
            "temperature": merged_config.temperature,
            "max_tokens": merged_config.max_tokens,
            "enabled_tools": merged_config.enabled_tools,
            "is_enabled": True,
            "version": merged_config.version,
            "source": merged_config.source
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating agent config {flow_id}.{agent_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent configuration"
        )


@router.delete(
    "/configurations/{flow_id}/{agent_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset agent configuration"
)
async def reset_agent_configuration(
    flow_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("labs:agents:configure"))
):
    """
    Reset agent configuration to code defaults.
    
    Deletes any custom configuration, causing the agent to use default settings.
    """
    config_service = AgentConfigurationService(db)
    
    # Delete override (falls back to code defaults)
    db_config = db.query(AgentConfiguration).filter(
        AgentConfiguration.customer_id == current_user.customer_id,
        AgentConfiguration.flow_identifier == flow_id,
        AgentConfiguration.agent_identifier == agent_id
    ).first()
    
    if db_config:
        db.delete(db_config)
        db.commit()
        
        # Invalidate cache
        cache_key = f"{current_user.customer_id}:{flow_id}:{agent_id}"
        if cache_key in config_service._cache:
            del config_service._cache[cache_key]
        
        logger.info(f"Reset agent config {flow_id}.{agent_id} for customer {current_user.customer_id}")
    
    return None

