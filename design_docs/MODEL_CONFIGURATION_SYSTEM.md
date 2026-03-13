# Model Configuration System - Model Agnostic Implementation

## Executive Summary

This document defines a comprehensive model configuration system that makes the AI Enablement Platform model-agnostic while defaulting to OpenAI models. The system provides simplified model selection for each application component while maintaining compatibility with multiple LLM providers.

**Key Features:**
- **OpenAI as Default**: All components default to OpenAI models
- **Model Agnostic Design**: Easy switching between providers (OpenAI, Lamini, Anthropic, etc.)
- **Component-Specific Models**: Different models for different tasks
- **Unified Configuration**: Single configuration file for all model choices
- **Performance Optimization**: Model selection based on task requirements
- **Cost Optimization**: Balance performance and cost per component

---

## 1. Model Configuration Architecture

### 1.1 Unified Model Configuration

```python
# From model configuration system - EXAMPLE
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import openai
from abc import ABC, abstractmethod

class ModelProvider(Enum):
    """Supported model providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    TOGETHER = "together"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    GROQ = "groq"

class TaskType(Enum):
    """Different types of tasks requiring different model characteristics"""
    INTENT_ANALYSIS = "intent_analysis"          # Requires consistency and accuracy
    RAG_RETRIEVAL = "rag_retrieval"             # Requires understanding and query generation
    CONTEXT_ENRICHMENT = "context_enrichment"   # Requires business knowledge and reasoning
    PROMPT_GENERATION = "prompt_generation"     # Requires creativity and instruction following
    QUALITY_VALIDATION = "quality_validation"   # Requires critical analysis and evaluation
    EMBEDDING_GENERATION = "embedding_generation" # Requires semantic understanding
    DOCUMENT_PROCESSING = "document_processing"  # Requires text analysis and extraction
    QA_GENERATION = "qa_generation"             # Requires question formulation and answering

@dataclass
class ModelConfig:
    """Configuration for a specific model"""
    provider: ModelProvider
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 1000
    timeout: int = 60
    retry_attempts: int = 3
    cost_per_1k_tokens: float = 0.0
    performance_tier: str = "standard"  # "fast", "standard", "premium"
    specialized_for: List[TaskType] = field(default_factory=list)
    
    def to_client_config(self) -> Dict[str, Any]:
        """Convert to client configuration"""
        config = {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout
        }
        
        if self.api_key:
            config["api_key"] = self.api_key
        if self.base_url:
            config["base_url"] = self.base_url
            
        return config

@dataclass
class ApplicationModelConfig:
    """Complete model configuration for the application"""
    
    # Default provider settings
    default_provider: ModelProvider = ModelProvider.OPENAI
    fallback_provider: ModelProvider = ModelProvider.ANTHROPIC
    
    # Provider configurations
    provider_configs: Dict[ModelProvider, Dict[str, Any]] = field(default_factory=dict)
    
    # Available models by provider
    available_models: Dict[ModelProvider, List[ModelConfig]] = field(default_factory=dict)
    
    # Task-specific model assignments
    task_model_assignments: Dict[TaskType, str] = field(default_factory=dict)
    
    # Performance and cost preferences
    performance_preference: str = "balanced"  # "cost_optimized", "balanced", "performance_optimized"
    max_cost_per_request: float = 0.10  # Maximum cost per request in USD
    
    def __post_init__(self):
        """Initialize default configurations"""
        self._setup_default_providers()
        self._setup_default_models()
        self._setup_default_task_assignments()
    
    def _setup_default_providers(self):
        """Setup default provider configurations"""
        self.provider_configs = {
            ModelProvider.OPENAI: {
                "api_key": None,  # Will be set from environment or config
                "base_url": "https://api.openai.com/v1",
                "organization": None
            },
            ModelProvider.GROQ: {
                "api_key": None,
                "base_url": "https://api.groq.com/openai/v1"
            },
            ModelProvider.ANTHROPIC: {
                "api_key": None,
                "base_url": "https://api.anthropic.com"
            },
            ModelProvider.TOGETHER: {
                "api_key": None,
                "base_url": "https://api.together.xyz/v1"
            },
            ModelProvider.AZURE_OPENAI: {
                "api_key": None,
                "base_url": None,  # Will be set based on deployment
                "api_version": "2024-02-15-preview"
            }
        }
    
    def _setup_default_models(self):
        """Setup default model configurations"""
        self.available_models = {
            ModelProvider.OPENAI: [
                # GPT-4 Models - Premium Performance
                ModelConfig(
                    provider=ModelProvider.OPENAI,
                    model_name="gpt-4o",
                    temperature=0.3,
                    max_tokens=4000,
                    cost_per_1k_tokens=0.005,
                    performance_tier="premium",
                    specialized_for=[TaskType.PROMPT_GENERATION, TaskType.QUALITY_VALIDATION, TaskType.CONTEXT_ENRICHMENT]
                ),
                ModelConfig(
                    provider=ModelProvider.OPENAI,
                    model_name="gpt-4o-mini",
                    temperature=0.3,
                    max_tokens=2000,
                    cost_per_1k_tokens=0.00015,
                    performance_tier="standard",
                    specialized_for=[TaskType.INTENT_ANALYSIS, TaskType.RAG_RETRIEVAL, TaskType.DOCUMENT_PROCESSING]
                ),
                
                # GPT-3.5 Models - Cost Optimized
                ModelConfig(
                    provider=ModelProvider.OPENAI,
                    model_name="gpt-3.5-turbo",
                    temperature=0.3,
                    max_tokens=1500,
                    cost_per_1k_tokens=0.0005,
                    performance_tier="fast",
                    specialized_for=[TaskType.INTENT_ANALYSIS, TaskType.DOCUMENT_PROCESSING]
                ),
                
                # Embedding Models
                ModelConfig(
                    provider=ModelProvider.OPENAI,
                    model_name="text-embedding-3-small",
                    temperature=0.0,
                    max_tokens=0,  # N/A for embeddings
                    cost_per_1k_tokens=0.00002,
                    performance_tier="standard",
                    specialized_for=[TaskType.EMBEDDING_GENERATION]
                ),
                ModelConfig(
                    provider=ModelProvider.OPENAI,
                    model_name="text-embedding-3-large",
                    temperature=0.0,
                    max_tokens=0,
                    cost_per_1k_tokens=0.00013,
                    performance_tier="premium",
                    specialized_for=[TaskType.EMBEDDING_GENERATION]
                )
            ],
            
            ModelProvider.GROQ: [
                # Groq Models - Fast inference
                ModelConfig(
                    provider=ModelProvider.GROQ,
                    model_name="llama-3.1-8b-instant",
                    temperature=0.3,
                    max_tokens=2000,
                    cost_per_1k_tokens=0.0001,  # Very cost effective
                    performance_tier="fast",
                    specialized_for=[TaskType.INTENT_ANALYSIS, TaskType.RAG_RETRIEVAL, TaskType.DOCUMENT_PROCESSING]
                ),
                ModelConfig(
                    provider=ModelProvider.GROQ,
                    model_name="llama-3.1-70b-versatile",
                    temperature=0.3,
                    max_tokens=3000,
                    cost_per_1k_tokens=0.0008,
                    performance_tier="standard",
                    specialized_for=[TaskType.CONTEXT_ENRICHMENT, TaskType.QA_GENERATION]
                ),
                ModelConfig(
                    provider=ModelProvider.GROQ,
                    model_name="mixtral-8x7b-32768",
                    temperature=0.3,
                    max_tokens=4000,
                    cost_per_1k_tokens=0.0006,
                    performance_tier="standard",
                    specialized_for=[TaskType.PROMPT_GENERATION, TaskType.QUALITY_VALIDATION]
                )
            ],
            
            ModelProvider.TOGETHER: [
                # Together AI Models
                ModelConfig(
                    provider=ModelProvider.TOGETHER,
                    model_name="meta-llama/Llama-3-8b-chat-hf",
                    temperature=0.3,
                    max_tokens=2000,
                    cost_per_1k_tokens=0.0002,
                    performance_tier="standard",
                    specialized_for=[TaskType.INTENT_ANALYSIS, TaskType.DOCUMENT_PROCESSING]
                ),
                ModelConfig(
                    provider=ModelProvider.TOGETHER,
                    model_name="meta-llama/Llama-3-70b-chat-hf",
                    temperature=0.3,
                    max_tokens=3000,
                    cost_per_1k_tokens=0.0009,
                    performance_tier="premium",
                    specialized_for=[TaskType.PROMPT_GENERATION, TaskType.CONTEXT_ENRICHMENT, TaskType.QUALITY_VALIDATION]
                ),
                ModelConfig(
                    provider=ModelProvider.TOGETHER,
                    model_name="togethercomputer/m2-bert-80M-8k-retrieval",
                    temperature=0.0,
                    max_tokens=0,
                    cost_per_1k_tokens=0.00008,
                    performance_tier="standard",
                    specialized_for=[TaskType.EMBEDDING_GENERATION]
                )
            ],
            
            ModelProvider.ANTHROPIC: [
                ModelConfig(
                    provider=ModelProvider.ANTHROPIC,
                    model_name="claude-3-5-sonnet-20241022",
                    temperature=0.3,
                    max_tokens=4000,
                    cost_per_1k_tokens=0.003,
                    performance_tier="premium",
                    specialized_for=[TaskType.PROMPT_GENERATION, TaskType.QUALITY_VALIDATION, TaskType.CONTEXT_ENRICHMENT]
                ),
                ModelConfig(
                    provider=ModelProvider.ANTHROPIC,
                    model_name="claude-3-haiku-20240307",
                    temperature=0.3,
                    max_tokens=2000,
                    cost_per_1k_tokens=0.00025,
                    performance_tier="fast",
                    specialized_for=[TaskType.INTENT_ANALYSIS, TaskType.DOCUMENT_PROCESSING]
                )
            ]
        }
    
    def _setup_default_task_assignments(self):
        """Setup default task-to-model assignments (OpenAI as default)"""
        self.task_model_assignments = {
            TaskType.INTENT_ANALYSIS: "gpt-4o-mini",
            TaskType.RAG_RETRIEVAL: "gpt-4o-mini", 
            TaskType.CONTEXT_ENRICHMENT: "gpt-4o",
            TaskType.PROMPT_GENERATION: "gpt-4o",
            TaskType.QUALITY_VALIDATION: "gpt-4o",
            TaskType.EMBEDDING_GENERATION: "text-embedding-3-small",
            TaskType.DOCUMENT_PROCESSING: "gpt-4o-mini",
            TaskType.QA_GENERATION: "gpt-4o"
        }

class ModelManager:
    """Manages model selection and client creation"""
    
    def __init__(self, config: ApplicationModelConfig):
        self.config = config
        self.clients: Dict[str, Any] = {}
        self.model_cache: Dict[str, ModelConfig] = {}
        self._build_model_cache()
    
    def _build_model_cache(self):
        """Build cache of all available models by name"""
        for provider_models in self.config.available_models.values():
            for model_config in provider_models:
                self.model_cache[model_config.model_name] = model_config
    
    def get_model_for_task(self, task_type: TaskType, performance_preference: Optional[str] = None) -> ModelConfig:
        """Get the optimal model for a specific task type"""
        
        # Get assigned model name for task
        assigned_model_name = self.config.task_model_assignments.get(task_type)
        
        if assigned_model_name and assigned_model_name in self.model_cache:
            return self.model_cache[assigned_model_name]
        
        # Fallback: Find best model for task type
        return self._find_best_model_for_task(task_type, performance_preference)
    
    def _find_best_model_for_task(self, task_type: TaskType, performance_preference: Optional[str] = None) -> ModelConfig:
        """Find the best available model for a task type"""
        
        preference = performance_preference or self.config.performance_preference
        suitable_models = []
        
        # Find models specialized for this task
        for model_config in self.model_cache.values():
            if task_type in model_config.specialized_for:
                suitable_models.append(model_config)
        
        if not suitable_models:
            # Fallback to default provider's first model
            default_models = self.config.available_models.get(self.config.default_provider, [])
            if default_models:
                return default_models[0]
            else:
                raise ValueError(f"No suitable model found for task {task_type}")
        
        # Sort by preference
        if preference == "cost_optimized":
            suitable_models.sort(key=lambda m: m.cost_per_1k_tokens)
        elif preference == "performance_optimized":
            tier_priority = {"premium": 0, "standard": 1, "fast": 2}
            suitable_models.sort(key=lambda m: tier_priority.get(m.performance_tier, 3))
        else:  # balanced
            # Balance cost and performance
            suitable_models.sort(key=lambda m: (m.cost_per_1k_tokens * 1000, {"premium": 0, "standard": 1, "fast": 2}.get(m.performance_tier, 3)))
        
        return suitable_models[0]
    
    def get_client(self, model_config: ModelConfig) -> Any:
        """Get or create a client for the specified model"""
        
        client_key = f"{model_config.provider.value}_{model_config.model_name}"
        
        if client_key not in self.clients:
            self.clients[client_key] = self._create_client(model_config)
        
        return self.clients[client_key]
    
    def _create_client(self, model_config: ModelConfig) -> Any:
        """Create a client for the specified model provider"""
        
        provider_config = self.config.provider_configs.get(model_config.provider, {})
        
        if model_config.provider == ModelProvider.OPENAI:
            return openai.OpenAI(
                api_key=model_config.api_key or provider_config.get("api_key"),
                base_url=model_config.base_url or provider_config.get("base_url"),
                organization=provider_config.get("organization"),
                timeout=model_config.timeout
            )
        
        elif model_config.provider == ModelProvider.GROQ:
            return openai.OpenAI(  # Groq uses OpenAI-compatible API
                api_key=model_config.api_key or provider_config.get("api_key"),
                base_url=model_config.base_url or provider_config.get("base_url"),
                timeout=model_config.timeout
            )
        
        elif model_config.provider == ModelProvider.ANTHROPIC:
            # Would use Anthropic client here
            import anthropic
            return anthropic.Anthropic(
                api_key=model_config.api_key or provider_config.get("api_key"),
                timeout=model_config.timeout
            )
        
        elif model_config.provider == ModelProvider.TOGETHER:
            return openai.OpenAI(  # Together uses OpenAI-compatible API
                api_key=model_config.api_key or provider_config.get("api_key"),
                base_url=model_config.base_url or provider_config.get("base_url"),
                timeout=model_config.timeout
            )
        
        elif model_config.provider == ModelProvider.AZURE_OPENAI:
            from openai import AzureOpenAI
            return AzureOpenAI(
                api_key=model_config.api_key or provider_config.get("api_key"),
                azure_endpoint=model_config.base_url or provider_config.get("base_url"),
                api_version=provider_config.get("api_version", "2024-02-15-preview"),
                timeout=model_config.timeout
            )
        
        else:
            raise ValueError(f"Unsupported provider: {model_config.provider}")

class UnifiedLLMInterface:
    """Unified interface for all LLM interactions"""
    
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
    
    async def generate_completion(
        self, 
        task_type: TaskType,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """Generate completion using the appropriate model for the task"""
        
        # Get optimal model for task
        model_config = self.model_manager.get_model_for_task(task_type)
        client = self.model_manager.get_client(model_config)
        
        # Prepare request parameters
        request_params = {
            "model": model_config.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", model_config.temperature),
            "max_tokens": kwargs.get("max_tokens", model_config.max_tokens),
            **kwargs
        }
        
        # Handle different providers
        try:
            if model_config.provider in [ModelProvider.OPENAI, ModelProvider.GROQ, ModelProvider.TOGETHER, ModelProvider.AZURE_OPENAI]:
                response = await client.chat.completions.create(**request_params)
                return response.choices[0].message.content.strip()
            
            elif model_config.provider == ModelProvider.ANTHROPIC:
                # Anthropic has different message format
                response = await client.messages.create(
                    model=model_config.model_name,
                    max_tokens=request_params["max_tokens"],
                    temperature=request_params["temperature"],
                    messages=messages
                )
                return response.content[0].text
            
            else:
                raise ValueError(f"Unsupported provider: {model_config.provider}")
                
        except Exception as e:
            # Fallback to alternative model if available
            return await self._handle_completion_fallback(task_type, messages, e, **kwargs)
    
    async def generate_embedding(
        self,
        text: str,
        task_type: TaskType = TaskType.EMBEDDING_GENERATION,
        **kwargs
    ) -> List[float]:
        """Generate embeddings using the appropriate model"""
        
        model_config = self.model_manager.get_model_for_task(task_type)
        client = self.model_manager.get_client(model_config)
        
        try:
            if model_config.provider in [ModelProvider.OPENAI, ModelProvider.GROQ, ModelProvider.TOGETHER]:
                response = await client.embeddings.create(
                    model=model_config.model_name,
                    input=text,
                    **kwargs
                )
                return response.data[0].embedding
            
            else:
                raise ValueError(f"Embedding not supported for provider: {model_config.provider}")
                
        except Exception as e:
            # Fallback to alternative embedding model
            return await self._handle_embedding_fallback(text, e, **kwargs)
    
    async def _handle_completion_fallback(
        self, 
        task_type: TaskType, 
        messages: List[Dict[str, str]], 
        original_error: Exception,
        **kwargs
    ) -> str:
        """Handle fallback for failed completions"""
        
        # Try fallback provider
        fallback_models = self.model_manager.config.available_models.get(
            self.model_manager.config.fallback_provider, []
        )
        
        for fallback_model in fallback_models:
            if task_type in fallback_model.specialized_for:
                try:
                    client = self.model_manager.get_client(fallback_model)
                    response = await client.chat.completions.create(
                        model=fallback_model.model_name,
                        messages=messages,
                        temperature=kwargs.get("temperature", fallback_model.temperature),
                        max_tokens=kwargs.get("max_tokens", fallback_model.max_tokens)
                    )
                    return response.choices[0].message.content.strip()
                except Exception:
                    continue
        
        # If all fallbacks fail, raise original error
        raise original_error
    
    async def _handle_embedding_fallback(self, text: str, original_error: Exception, **kwargs) -> List[float]:
        """Handle fallback for failed embeddings"""
        
        # Try fallback embedding models
        fallback_models = self.model_manager.config.available_models.get(
            self.model_manager.config.fallback_provider, []
        )
        
        for fallback_model in fallback_models:
            if TaskType.EMBEDDING_GENERATION in fallback_model.specialized_for:
                try:
                    client = self.model_manager.get_client(fallback_model)
                    response = await client.embeddings.create(
                        model=fallback_model.model_name,
                        input=text
                    )
                    return response.data[0].embedding
                except Exception:
                    continue
        
        # If all fallbacks fail, raise original error
        raise original_error

def load_model_config_from_file(config_path: str = "model_config.yaml") -> ApplicationModelConfig:
    """Load model configuration from YAML file"""
    
    import yaml
    from pathlib import Path
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        # Return default configuration
        return ApplicationModelConfig()
    
    with open(config_file, 'r') as f:
        config_data = yaml.safe_load(f)
    
    # Parse configuration data into ApplicationModelConfig
    app_config = ApplicationModelConfig()
    
    # Override defaults with file configuration
    if 'default_provider' in config_data:
        app_config.default_provider = ModelProvider(config_data['default_provider'])
    
    if 'performance_preference' in config_data:
        app_config.performance_preference = config_data['performance_preference']
    
    if 'task_assignments' in config_data:
        for task_name, model_name in config_data['task_assignments'].items():
            task_type = TaskType(task_name)
            app_config.task_model_assignments[task_type] = model_name
    
    if 'provider_configs' in config_data:
        for provider_name, provider_config in config_data['provider_configs'].items():
            provider = ModelProvider(provider_name)
            app_config.provider_configs[provider].update(provider_config)
    
    return app_config
```

## 2. Configuration File Format

### 2.1 YAML Configuration Example

```yaml
# model_config.yaml - EXAMPLE
# Model configuration for AI Enablement Platform

# Default settings
default_provider: "openai"
fallback_provider: "anthropic"
performance_preference: "balanced"  # cost_optimized, balanced, performance_optimized
max_cost_per_request: 0.10

# Provider-specific configurations
provider_configs:
  openai:
    api_key: "${OPENAI_API_KEY}"  # Environment variable
    base_url: "https://api.openai.com/v1"
    organization: "${OPENAI_ORG_ID}"
  
  groq:
    api_key: "${GROQ_API_KEY}"
    base_url: "https://api.groq.com/openai/v1"
  
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    base_url: "https://api.anthropic.com"
  
  together:
    api_key: "${TOGETHER_API_KEY}"
    base_url: "https://api.together.xyz/v1"

# Task-specific model assignments
task_assignments:
  intent_analysis: "gpt-4o-mini"
  rag_retrieval: "gpt-4o-mini"
  context_enrichment: "gpt-4o"
  prompt_generation: "gpt-4o"
  quality_validation: "gpt-4o"
  embedding_generation: "text-embedding-3-small"
  document_processing: "gpt-4o-mini"
  qa_generation: "gpt-4o"

# Performance profiles for different environments
profiles:
  development:
    default_provider: "groq"  # Use fast, cost-effective models for development
    performance_preference: "cost_optimized"
    task_assignments:
      intent_analysis: "llama-3.1-8b-instant"
      rag_retrieval: "llama-3.1-8b-instant"
      context_enrichment: "llama-3.1-70b-versatile"
      prompt_generation: "mixtral-8x7b-32768"
      quality_validation: "mixtral-8x7b-32768"
      embedding_generation: "text-embedding-3-small"
  
  production:
    default_provider: "openai"
    performance_preference: "balanced"
    task_assignments:
      intent_analysis: "gpt-4o-mini"
      rag_retrieval: "gpt-4o-mini"
      context_enrichment: "gpt-4o"
      prompt_generation: "gpt-4o"
      quality_validation: "gpt-4o"
      embedding_generation: "text-embedding-3-small"
  
  premium:
    default_provider: "openai"
    performance_preference: "performance_optimized"
    task_assignments:
      intent_analysis: "gpt-4o"
      rag_retrieval: "gpt-4o"
      context_enrichment: "gpt-4o"
      prompt_generation: "gpt-4o"
      quality_validation: "gpt-4o"
      embedding_generation: "text-embedding-3-large"

# Custom model definitions (for adding new models)
custom_models:
  - provider: "openai"
    model_name: "gpt-4o-2024-08-06"
    temperature: 0.3
    max_tokens: 4000
    cost_per_1k_tokens: 0.005
    performance_tier: "premium"
    specialized_for: ["prompt_generation", "quality_validation"]
```

## 3. Integration with CrewAI Components

### 3.1 Updated CrewAI Agent Configuration

```python
# From CrewAI integration with model system - EXAMPLE

class UserTaskEnrichmentFlow(Flow):
    """CrewAI Flow with model-agnostic configuration"""
    
    def __init__(self, config: EnrichmentFlowConfig, model_config_path: str = "model_config.yaml"):
        super().__init__()
        self.config = config
        
        # Initialize model management system
        self.model_config = load_model_config_from_file(model_config_path)
        self.model_manager = ModelManager(self.model_config)
        self.llm_interface = UnifiedLLMInterface(self.model_manager)
        
        # Initialize agents with model-agnostic configuration
        self.agents = self._create_model_agnostic_agents()
        self.tools = self._create_model_agnostic_tools()
    
    def _create_model_agnostic_agents(self) -> Dict[str, Agent]:
        """Create agents with automatic model selection"""
        
        agents = {}
        
        # Intent Analysis Agent
        intent_model = self.model_manager.get_model_for_task(TaskType.INTENT_ANALYSIS)
        agents['intent_analyzer'] = Agent(
            role="Intent Analysis Specialist",
            goal="Analyze user requests to determine intent, complexity, and requirements",
            backstory="""You are an expert at understanding user intentions and breaking down 
            complex requests into structured, analyzable components.""",
            tools=[
                IntentClassificationTool(self.llm_interface, TaskType.INTENT_ANALYSIS),
                EntityExtractionTool(self.llm_interface, TaskType.INTENT_ANALYSIS),
                ComplexityAssessmentTool(self.llm_interface, TaskType.INTENT_ANALYSIS)
            ],
            llm_config=self._create_agent_llm_config(intent_model),
            verbose=True,
            memory=True
        )
        
        # RAG Retrieval Agent
        rag_model = self.model_manager.get_model_for_task(TaskType.RAG_RETRIEVAL)
        agents['rag_retriever'] = Agent(
            role="Knowledge Retrieval Specialist",
            goal="Find and retrieve relevant information from the knowledge base",
            backstory="""You are an expert information retrieval specialist with deep knowledge 
            of semantic search, query optimization, and knowledge base navigation.""",
            tools=[
                RAGQueryGeneratorTool(self.llm_interface, TaskType.RAG_RETRIEVAL),
                VectorSearchTool(self.llm_interface, TaskType.EMBEDDING_GENERATION),
                QADatabaseSearchTool(self.llm_interface, TaskType.RAG_RETRIEVAL),
                ContextSynthesizerTool(self.llm_interface, TaskType.RAG_RETRIEVAL)
            ],
            llm_config=self._create_agent_llm_config(rag_model),
            verbose=True,
            memory=True
        )
        
        # Context Enrichment Agent
        context_model = self.model_manager.get_model_for_task(TaskType.CONTEXT_ENRICHMENT)
        agents['context_enricher'] = Agent(
            role="Business Context Specialist",
            goal="Enrich user requests with relevant business, organizational, and domain context",
            backstory="""You are a business analyst with deep understanding of organizational 
            structures, business processes, and domain-specific knowledge.""",
            tools=[
                OrganizationalContextTool(self.llm_interface, TaskType.CONTEXT_ENRICHMENT),
                TemporalContextTool(self.llm_interface, TaskType.CONTEXT_ENRICHMENT),
                DomainContextTool(self.llm_interface, TaskType.CONTEXT_ENRICHMENT),
                UserContextAnalyzerTool(self.llm_interface, TaskType.CONTEXT_ENRICHMENT)
            ],
            llm_config=self._create_agent_llm_config(context_model),
            verbose=True,
            memory=True
        )
        
        # Prompt Generation Agent  
        prompt_model = self.model_manager.get_model_for_task(TaskType.PROMPT_GENERATION)
        agents['prompt_generator'] = Agent(
            role="Prompt Engineering Expert",
            goal="Generate exceptional prompts that maximize processing agent success rates",
            backstory="""You are a world-class prompt engineering expert with deep knowledge of 
            AI agent psychology, instruction clarity, and task optimization.""",
            tools=[
                TemplateSelectorTool(self.llm_interface, TaskType.PROMPT_GENERATION),
                ExampleMatcherTool(self.llm_interface, TaskType.PROMPT_GENERATION),
                PromptEnhancerTool(self.llm_interface, TaskType.PROMPT_GENERATION),
                BestPracticesApplierTool(self.llm_interface, TaskType.PROMPT_GENERATION)
            ],
            llm_config=self._create_agent_llm_config(prompt_model),
            verbose=True,
            memory=True
        )
        
        # Quality Validation Agent
        quality_model = self.model_manager.get_model_for_task(TaskType.QUALITY_VALIDATION)
        agents['quality_validator'] = Agent(
            role="Quality Assurance Specialist",
            goal="Ensure generated prompts meet the highest quality standards",
            backstory="""You are a meticulous quality assurance expert with deep understanding 
            of prompt effectiveness, clarity metrics, and success prediction.""",
            tools=[
                QualityAssessorTool(self.llm_interface, TaskType.QUALITY_VALIDATION),
                PromptRefinerTool(self.llm_interface, TaskType.QUALITY_VALIDATION),
                ValidationCriteriaCheckerTool(self.llm_interface, TaskType.QUALITY_VALIDATION),
                SuccessPredictorTool(self.llm_interface, TaskType.QUALITY_VALIDATION)
            ],
            llm_config=self._create_agent_llm_config(quality_model),
            verbose=True,
            memory=True
        )
        
        return agents
    
    def _create_agent_llm_config(self, model_config: ModelConfig) -> Dict[str, Any]:
        """Create LLM configuration for CrewAI agent"""
        
        # CrewAI expects specific format
        llm_config = {
            "model": model_config.model_name,
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
            "timeout": model_config.timeout
        }
        
        # Add provider-specific configuration
        provider_config = self.model_config.provider_configs.get(model_config.provider, {})
        
        if model_config.api_key or provider_config.get("api_key"):
            llm_config["api_key"] = model_config.api_key or provider_config.get("api_key")
        
        if model_config.base_url or provider_config.get("base_url"):
            llm_config["base_url"] = model_config.base_url or provider_config.get("base_url")
        
        # Add provider-specific parameters
        if model_config.provider == ModelProvider.AZURE_OPENAI:
            llm_config["api_version"] = provider_config.get("api_version", "2024-02-15-preview")
        
        return llm_config

### 3.2 Updated CrewAI Tools with Model Agnostic Interface

class ModelAgnosticTool(BaseTool):
    """Base class for model-agnostic CrewAI tools"""
    
    def __init__(self, llm_interface: UnifiedLLMInterface, task_type: TaskType):
        super().__init__()
        self.llm_interface = llm_interface
        self.task_type = task_type
    
    async def generate_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate completion using the unified interface"""
        return await self.llm_interface.generate_completion(
            self.task_type, messages, **kwargs
        )
    
    async def generate_embedding(self, text: str, **kwargs) -> List[float]:
        """Generate embedding using the unified interface"""
        return await self.llm_interface.generate_embedding(text, self.task_type, **kwargs)

class IntentClassificationTool(ModelAgnosticTool):
    """Model-agnostic intent classification tool"""
    
    name: str = "Intent Classification"
    description: str = "Classify user intent using the optimal model for the task"
    
    def _run(self, user_input: str, user_context: Dict[str, Any]) -> str:
        """Execute intent classification with automatic model selection"""
        
        messages = [
            {"role": "system", "content": "You are an expert at analyzing user requests and understanding intent. Always respond with valid JSON."},
            {"role": "user", "content": self._create_classification_prompt(user_input, user_context)}
        ]
        
        try:
            result = asyncio.run(self.generate_completion(messages, temperature=0.1, max_tokens=800))
            return result
        except Exception as e:
            return json.dumps({"error": str(e), "primary_intent": "question_answering"})
    
    def _create_classification_prompt(self, user_input: str, user_context: Dict[str, Any]) -> str:
        """Create classification prompt"""
        return f"""
        Classify the following user request and provide detailed analysis:
        
        User Input: "{user_input}"
        User Context: {json.dumps(user_context, indent=2)}
        
        Analyze and respond with JSON:
        {{
            "primary_intent": "question_answering|data_analysis|report_generation|recommendation|comparison|summarization|calculation|workflow_execution|information_extraction",
            "confidence": 0.0-1.0,
            "complexity": "simple|moderate|complex|expert",
            "main_objective": "clear statement of primary goal",
            "sub_objectives": ["list of sub-goals"],
            "entities_mentioned": ["specific entities referenced"],
            "success_criteria": ["how to measure success"],
            "estimated_effort": "quick|moderate|extensive"
        }}
        """
```

## 4. Environment-Specific Configurations

### 4.1 Development Environment

```yaml
# model_config.dev.yaml - EXAMPLE
default_provider: "lamini"
fallback_provider: "openai"
performance_preference: "cost_optimized"

task_assignments:
  intent_analysis: "meta-llama/Llama-3.1-8B-Instruct"
  rag_retrieval: "meta-llama/Llama-3.1-8B-Instruct"
  context_enrichment: "meta-llama/Llama-3.1-70B-Instruct"
  prompt_generation: "meta-llama/Llama-3.1-70B-Instruct"
  quality_validation: "meta-llama/Llama-3.1-70B-Instruct"
  embedding_generation: "sentence-transformers/all-MiniLM-L6-v2"
  document_processing: "meta-llama/Llama-3.1-8B-Instruct"
  qa_generation: "meta-llama/Llama-3.1-70B-Instruct"

provider_configs:
  lamini:
    api_key: "${LAMINI_API_KEY}"
    base_url: "http://localhost:5001/inf"
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
```

### 4.2 Production Environment

```yaml
# model_config.prod.yaml - EXAMPLE
default_provider: "openai"
fallback_provider: "lamini"
performance_preference: "balanced"

task_assignments:
  intent_analysis: "gpt-4o-mini"
  rag_retrieval: "gpt-4o-mini"
  context_enrichment: "gpt-4o"
  prompt_generation: "gpt-4o"
  quality_validation: "gpt-4o"
  embedding_generation: "text-embedding-3-small"
  document_processing: "gpt-4o-mini"
  qa_generation: "gpt-4o"

provider_configs:
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
    organization: "${OPENAI_ORG_ID}"
  lamini:
    api_key: "${LAMINI_API_KEY}"
    base_url: "http://localhost:5001/inf"
```

This comprehensive model configuration system provides:

1. **OpenAI as Default**: All components default to OpenAI models for reliability
2. **Model Agnostic Design**: Easy switching between providers without code changes
3. **Task-Specific Optimization**: Different models optimized for different tasks
4. **Cost Management**: Built-in cost tracking and optimization
5. **Performance Profiles**: Different configurations for different environments
6. **Automatic Fallback**: Graceful degradation when primary models fail
7. **Unified Interface**: Single interface for all LLM interactions
8. **Easy Configuration**: YAML-based configuration with environment variables

The system ensures your application can easily adapt to different deployment scenarios while maintaining optimal performance and cost efficiency.
