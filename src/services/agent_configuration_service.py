"""Agent Configuration Service with runtime resolution and caching."""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field

from src.services.base_service import BaseService
from src.services.provider_service import ProviderService
from src.models.customer import CustomerAIProvider
from src.models.agent_configuration import AgentConfiguration
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Agent configuration (Layer 2 only)."""
    agent_identifier: str
    flow_identifier: str
    role: str
    goal: str
    backstory: str
    model_id: Optional[str] = None  # None in code defaults, resolved from provider at runtime
    provider_config_id: Optional[int] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    enabled_tools: List[str] = []
    tool_configs: Dict[str, Any] = {}
    is_enabled: bool = True
    version: int = 1
    source: str = "default"  # "default", "override", "merged"


class CompleteAgentConfig(BaseModel):
    """Fully resolved agent configuration (Layer 1 + Layer 2)."""
    # Layer 2: Agent behavior
    agent_identifier: str
    flow_identifier: str
    role: str
    goal: str
    backstory: str
    model_id: str
    temperature: float
    max_tokens: int
    enabled_tools: List[str]
    tool_configs: Dict[str, Any]
    
    # Layer 1: Provider/LLM config
    provider_type: str          # "openai", "anthropic", etc.
    provider_name: str          # "OpenAI Production Account"
    provider_config_id: int
    api_key: Optional[str] = None   # Decrypted (internal use only!)
    base_url: Optional[str] = None
    
    # Metadata
    source: str
    version: int


class AgentConfigurationService(BaseService):
    """Manages agent configurations with runtime resolution."""
    
    # In-memory cache (60 second TTL)
    _cache: Dict[str, Tuple[CompleteAgentConfig, float]] = {}
    _cache_ttl: int = 60
    
    def __init__(self, db: Session):
        self.db = db
        self.provider_service = ProviderService(db)
        self.defaults = self._load_code_defaults()
    
    def get_complete_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str
    ) -> CompleteAgentConfig:
        """
        Get COMPLETE agent config (Layer 1 + Layer 2 merged).
        
        This is the single source of truth for runtime execution.
        Returns fully resolved config with provider credentials.
        
        Resolution order:
        1. Check cache
        2. Query database for customer override
        3. Merge with code defaults
        4. Resolve provider configuration
        5. Cache and return
        """
        cache_key = f"{customer_id}:{flow_identifier}:{agent_identifier}"
        
        # Check cache
        if cache_key in self._cache:
            config, cached_at = self._cache[cache_key]
            if time.time() - cached_at < self._cache_ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return config
        
        logger.info(f"Resolving agent config for {cache_key}")
        
        # Load agent config (Layer 2)
        agent_config = self._get_agent_config(customer_id, flow_identifier, agent_identifier)
        
        # If model_id is None (from code defaults), get it from provider's default_model
        if agent_config.model_id is None:
            # Get first enabled provider and use its default_model
            first_provider = self.db.query(CustomerAIProvider).filter(
                CustomerAIProvider.customer_id == customer_id,
                CustomerAIProvider.is_enabled == True
            ).order_by(CustomerAIProvider.priority).first()
            
            if not first_provider:
                raise ConfigurationError(
                    f"No enabled provider found. Please configure a provider in Admin Settings > AI Model Providers."
                )
            
            # Get default_model from provider config
            default_model = None
            if first_provider.config_data:
                default_model = first_provider.config_data.get("default_model")
            
            if not default_model:
                # Fall back to first available model
                available_models = first_provider.config_data.get("available_models", []) if first_provider.config_data else []
                if available_models:
                    default_model = available_models[0]
                else:
                    raise ConfigurationError(
                        f"Provider '{first_provider.name or first_provider.provider_name}' has no available models configured."
                    )
            
            agent_config.model_id = default_model
            logger.info(
                f"Using provider default model '{default_model}' from '{first_provider.name or first_provider.provider_name}' "
                f"for agent {agent_identifier}"
            )
        
        # Resolve provider config (Layer 1)
        if agent_config.provider_config_id:
            provider_config = self.provider_service.get_provider_config(
                config_id=agent_config.provider_config_id,
                customer_id=customer_id
            )
        else:
            # Auto-select provider for this model
            provider_config = self._resolve_provider_for_model(
                customer_id=customer_id,
                model_id=agent_config.model_id
            )
            agent_config.provider_config_id = provider_config.id
        
        if not provider_config:
            raise ConfigurationError(
                f"No provider configuration found for agent {agent_identifier}. "
                f"Please configure a provider in Admin Settings > AI Model Providers."
            )
        
        # Get provider name (use name field if available, fallback to provider_name)
        provider_display_name = provider_config.name or f"{provider_config.provider_name.capitalize()} Config {provider_config.id}"
        
        # Decrypt credentials
        api_key = None
        if provider_config.api_key_encrypted:
            from src.utils.encryption import decrypt_value, EncryptionError
            import json
            try:
                # Try to decrypt as JSON first (for providers with multiple credentials)
                decrypted = json.loads(decrypt_value(provider_config.api_key_encrypted))
                api_key = decrypted.get('api_key') or decrypted.get('aws_access_key_id')
            except (json.JSONDecodeError, KeyError):
                # Fall back to direct string decryption (simple API key)
                try:
                    api_key = decrypt_value(provider_config.api_key_encrypted)
                except EncryptionError as e:
                    # If decryption fails, raise clear configuration error
                    raise ConfigurationError(
                        f"Provider configuration {provider_config.id} ({provider_display_name}) "
                        f"has an invalid or corrupted API key. Please reconfigure this provider "
                        f"in Admin Settings > AI Model Providers."
                    ) from e
        
        # Get base_url from config_data
        base_url = None
        if provider_config.config_data:
            base_url = provider_config.config_data.get("base_url")
        
        # Build complete config
        complete_config = CompleteAgentConfig(
            # Layer 2: Agent behavior
            agent_identifier=agent_config.agent_identifier,
            flow_identifier=agent_config.flow_identifier,
            role=agent_config.role,
            goal=agent_config.goal,
            backstory=agent_config.backstory,
            model_id=agent_config.model_id,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            enabled_tools=agent_config.enabled_tools,
            tool_configs=agent_config.tool_configs,
            
            # Layer 1: Provider/LLM
            provider_type=provider_config.provider_name,
            provider_name=provider_display_name,
            provider_config_id=provider_config.id,
            api_key=api_key,
            base_url=base_url,
            
            # Metadata
            source=agent_config.source,
            version=agent_config.version
        )
        
        # Cache
        self._cache[cache_key] = (complete_config, time.time())
        logger.info(
            f"Resolved config for {agent_identifier}: model={complete_config.model_id}, "
            f"provider={complete_config.provider_name}, source={complete_config.source}"
        )
        
        return complete_config
    
    def set_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str,
        config: Dict[str, Any],
        updated_by: str = "api",
        user_id: Optional[int] = None
    ) -> AgentConfiguration:
        """
        Update agent configuration.
        
        Provider resolution (in order of priority):
        1. config["provider_config_id"] - Explicit ID
        2. config["provider_name"] - Name lookup
        3. Auto-select based on model_id and priority
        
        Automatically invalidates cache.
        """
        # Ensure model_id is provided
        if "model_id" not in config:
            raise ValueError("model_id is required")
        
        model_id = config["model_id"]
        
        # Resolve provider (three options)
        if "provider_config_id" in config:
            # Option A: Explicit ID provided
            provider_config_id = config["provider_config_id"]
            logger.info(f"Using explicit provider_config_id: {provider_config_id}")
            
        elif "provider_name" in config:
            # Option B: Name provided, resolve to ID
            provider = self.db.query(CustomerAIProvider).filter(
                CustomerAIProvider.customer_id == customer_id,
                CustomerAIProvider.name == config["provider_name"]
            ).first()
            
            if not provider:
                raise ConfigurationError(
                    f"Provider '{config['provider_name']}' not found for customer {customer_id}"
                )
            
            provider_config_id = provider.id
            logger.info(f"Resolved provider name '{config['provider_name']}' to id: {provider_config_id}")
            
        else:
            # Option C: Auto-select based on model and priority
            provider = self._resolve_provider_for_model(customer_id, model_id)
            provider_config_id = provider.id
            logger.info(f"Auto-selected provider {provider_config_id} for model {model_id}")
        
        # Validate provider supports this model
        provider = self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.id == provider_config_id
        ).first()
        
        if not provider:
            raise ConfigurationError(f"Provider config {provider_config_id} not found")
        
        available_models = (
            provider.config_data.get("available_models", []) or 
            provider.config_data.get("models", [])
        ) if provider.config_data else []
        if model_id not in available_models:
            raise ConfigurationError(
                f"Model {model_id} not available in provider '{provider.name or provider.provider_name}'. "
                f"Available models: {', '.join(available_models)}"
            )
        
        # Find or create agent config
        db_config = self.db.query(AgentConfiguration).filter(
            AgentConfiguration.customer_id == customer_id,
            AgentConfiguration.flow_identifier == flow_identifier,
            AgentConfiguration.agent_identifier == agent_identifier
        ).first()
        
        if db_config:
            # Update existing
            db_config.model_id = model_id
            db_config.provider_config_id = provider_config_id
            db_config.role = config.get("role", db_config.role)
            db_config.goal = config.get("goal", db_config.goal)
            db_config.backstory = config.get("backstory", db_config.backstory)
            db_config.temperature = config.get("temperature", db_config.temperature)
            db_config.max_tokens = config.get("max_tokens", db_config.max_tokens)
            db_config.enabled_tools = config.get("enabled_tools", db_config.enabled_tools)
            db_config.tool_configs = config.get("tool_configs", db_config.tool_configs)
            db_config.version += 1
            db_config.updated_by = updated_by
            db_config.updated_by_user_id = user_id
            db_config.updated_at = func.now()
        else:
            # Create new
            db_config = AgentConfiguration(
                customer_id=customer_id,
                flow_identifier=flow_identifier,
                agent_identifier=agent_identifier,
                model_id=model_id,
                provider_config_id=provider_config_id,
                role=config.get("role"),
                goal=config.get("goal"),
                backstory=config.get("backstory"),
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 2000),
                enabled_tools=config.get("enabled_tools", []),
                tool_configs=config.get("tool_configs", {}),
                version=1,
                updated_by=updated_by,
                updated_by_user_id=user_id
            )
            self.db.add(db_config)
        
        self.db.commit()
        self.db.refresh(db_config)
        
        # Invalidate cache
        cache_key = f"{customer_id}:{flow_identifier}:{agent_identifier}"
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.info(f"Invalidated cache for {cache_key}")
        
        logger.info(
            f"Updated agent config: {flow_identifier}.{agent_identifier} "
            f"for customer {customer_id} (model: {model_id}, provider: {provider.name or provider.provider_name}, "
            f"source: {updated_by}, version: {db_config.version})"
        )
        
        return db_config
    
    def _get_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str
    ) -> AgentConfig:
        """Get agent config (Layer 2), merging DB override with code defaults."""
        
        # Query database
        db_config = self.db.query(AgentConfiguration).filter(
            AgentConfiguration.customer_id == customer_id,
            AgentConfiguration.flow_identifier == flow_identifier,
            AgentConfiguration.agent_identifier == agent_identifier
        ).first()
        
        # Get code defaults
        default_key = f"{flow_identifier}.{agent_identifier}"
        default_config = self.defaults.get(default_key, self._get_system_default(agent_identifier))
        
        # Merge
        if db_config and db_config.is_enabled:
            merged = self._merge_configs(default_config, db_config)
            merged.source = "override"
            merged.version = db_config.version
            return merged
        else:
            default_config.source = "default"
            return default_config
    
    def _resolve_provider_for_model(
        self,
        customer_id: str,
        model_id: str
    ) -> CustomerAIProvider:
        """Auto-select provider for a model based on priority."""
        candidates = self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.customer_id == customer_id,
            CustomerAIProvider.is_enabled == True
        ).all()
        
        # Filter by model support
        matching = [
            p for p in candidates
            if p.config_data and model_id in (
                p.config_data.get("available_models", []) or 
                p.config_data.get("models", [])
            )
        ]
        
        if not matching:
            raise ConfigurationError(
                f"No enabled provider found that supports model '{model_id}'. "
                f"Please configure a provider in Admin Settings > AI Model Providers."
            )
        
        # Select highest priority (lowest number)
        provider = min(matching, key=lambda p: p.priority)
        logger.info(
            f"Auto-selected provider '{provider.name or provider.provider_name}' "
            f"(id={provider.id}, priority={provider.priority}) for model '{model_id}'"
        )
        return provider
    
    def _load_code_defaults(self) -> Dict[str, AgentConfig]:
        """Load hardcoded defaults for all agents (personality and behavior)."""
        return {
            "data_analysis_flow.data_retrieval_agent": AgentConfig(
                agent_identifier="data_retrieval_agent",
                flow_identifier="data_analysis_flow",
                role="Data Retrieval Specialist",
                goal="Retrieve relevant data from HR database and document embeddings",
                backstory=(
                    "You are an expert at finding and retrieving relevant data from multiple sources. "
                    "You know how to query databases effectively and search through documents to find "
                    "the most relevant information for analysis."
                ),
                model_id=None,  # Will be resolved from provider's default_model at runtime
                enabled_tools=["hr_database", "document_search"],
                temperature=0.3,
                max_tokens=2000
            ),
            "data_analysis_flow.bi_analyst_agent": AgentConfig(
                agent_identifier="bi_analyst_agent",
                flow_identifier="data_analysis_flow",
                role="Business Intelligence Analyst",
                goal="Analyze data and generate actionable insights",
                backstory=(
                    "You are a seasoned business intelligence analyst with expertise in HR analytics. "
                    "You can identify patterns, trends, and insights from data that help organizations "
                    "make better decisions."
                ),
                model_id=None,  # Will be resolved from provider's default_model at runtime
                enabled_tools=[],
                temperature=0.3,
                max_tokens=4000
            ),
            "task_enrichment_flow.task_analyzer_agent": AgentConfig(
                agent_identifier="task_analyzer_agent",
                flow_identifier="task_enrichment_flow",
                role="Intent Analyzer",
                goal="Analyze user questions to understand their intent, complexity, and requirements",
                backstory=(
                    "You are an expert at understanding user intent and extracting key information "
                    "from business questions. You can identify what type of analysis is needed, "
                    "what data sources are required, and how complex the task is."
                ),
                model_id=None,  # Will be resolved from provider's default_model at runtime
                enabled_tools=[],
                temperature=0.3,
                max_tokens=2000
            ),
            "task_enrichment_flow.enrichment_agent": AgentConfig(
                agent_identifier="enrichment_agent",
                flow_identifier="task_enrichment_flow",
                role="Prompt Engineer",
                goal="Transform user questions into optimized prompts for analysis agents",
                backstory=(
                    "You are an expert prompt engineer who knows how to create clear, detailed prompts "
                    "that help AI agents produce high-quality analysis. You understand how to structure "
                    "prompts for maximum clarity and effectiveness."
                ),
                model_id=None,  # Will be resolved from provider's default_model at runtime
                enabled_tools=[],
                temperature=0.5,
                max_tokens=3000
            ),
        }
    
    def _merge_configs(
        self,
        default: AgentConfig,
        override: AgentConfiguration
    ) -> AgentConfig:
        """Merge database override with code defaults."""
        merged = default.model_copy()
        
        if override.role:
            merged.role = override.role
        if override.goal:
            merged.goal = override.goal
        if override.backstory:
            merged.backstory = override.backstory
        if override.model_id:
            merged.model_id = override.model_id
        if override.provider_config_id:
            merged.provider_config_id = override.provider_config_id
        if override.temperature is not None:
            merged.temperature = override.temperature
        if override.max_tokens:
            merged.max_tokens = override.max_tokens
        if override.enabled_tools:
            merged.enabled_tools = override.enabled_tools
        if override.tool_configs:
            merged.tool_configs = override.tool_configs
        
        return merged
    
    def _get_system_default(self, agent_identifier: str) -> AgentConfig:
        """Get system-wide default for unknown agents."""
        return AgentConfig(
            agent_identifier=agent_identifier,
            flow_identifier="unknown",
            role="AI Assistant",
            goal="Help users with their questions",
            backstory="You are a helpful AI assistant.",
            model_id="gpt-3.5-turbo",
            enabled_tools=[],
            temperature=0.7,
            max_tokens=2000
        )

