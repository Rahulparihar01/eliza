"""
AI Enablement Platform - Configuration Management

Handles application configuration, environment variables, and customer-specific settings.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Dict, Any, Union
from functools import lru_cache
import os
import yaml
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    app_name: str = Field(default="AI Enablement Platform", alias="APP_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Logging configuration
    logstash_enabled: bool = Field(default=False, alias="LOGSTASH_ENABLED")
    logstash_host: str = Field(default="logstash", alias="LOGSTASH_HOST")
    logstash_port: int = Field(default=5000, alias="LOGSTASH_PORT")
    log_to_file: bool = Field(default=True, alias="LOG_TO_FILE")
    log_json_format: bool = Field(default=True, alias="LOG_JSON_FORMAT")
    
    # Customer configuration
    customer_id: str = Field(default="default", alias="CUSTOMER_ID")
    customer_name: str = Field(default="Default Customer", alias="CUSTOMER_NAME")
    
    # Default admin user configuration (for initial setup - must be set via env vars)
    admin_email: Optional[str] = Field(default=None, alias="ADMIN_EMAIL", description="Admin email for initial setup (required if INIT_TENANT=true)")
    admin_password: Optional[str] = Field(default=None, alias="ADMIN_PASSWORD", description="Admin password for initial setup (required if INIT_TENANT=true)")
    init_tenant: bool = Field(default=False, alias="INIT_TENANT", description="Initialize tenant and admin user on startup")
    
    # Database settings
    database_url: str = Field(default="postgresql://postgres:password@postgres:5432/ai_platform", alias="DATABASE_URL")
    insurance_demo_db_url: str = Field(default="postgresql://user:password@postgres:5432/insurance_demo_db", alias="INSURANCE_DEMO_DB_URL")
    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    neo4j_uri: str = Field(default="bolt://neo4j:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")
    
    # Celery configuration
    celery_broker_url: str = Field(default="redis://redis:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://redis:6379/1", alias="CELERY_RESULT_BACKEND")
    
    # AI Provider API Keys
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    together_api_key: Optional[str] = Field(default=None, alias="TOGETHER_API_KEY")
    default_llm_model: str = Field(default="gpt-4o-mini", alias="DEFAULT_LLM_MODEL")  # OpenAI GPT-4o-mini
    crewai_llm_model: str = Field(default="gpt-5.2", alias="CREWAI_LLM_MODEL", description="LLM model for CrewAI agents (talent intelligence, etc.)")
    resume_extraction_mode: str = Field(default="openai", alias="RESUME_EXTRACTION_MODE", description="Resume data extraction mode: 'openai' (GPT-4o-mini structured output) or 'local' (regex heuristics)")
    resume_extraction_model: str = Field(default="gpt-4o-mini", alias="RESUME_EXTRACTION_MODEL", description="OpenAI model for resume structured extraction")
    openai_api_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_API_BASE_URL")
    
    # Security settings
    jwt_secret_key: str = Field(default="change-this-secret-key", alias="JWT_SECRET_KEY")
    session_timeout_minutes: int = Field(default=60, alias="SESSION_TIMEOUT_MINUTES")
    encryption_key: Optional[str] = Field(default=None, alias="ENCRYPTION_KEY", description="Fernet encryption key for sensitive data (generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")")

    # CORS and security
    allowed_origins: Union[List[str], str] = Field(default=["*"], alias="ALLOWED_ORIGINS")
    allowed_hosts: Union[List[str], str] = Field(default=["*"], alias="ALLOWED_HOSTS")
    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")
    public_base_url: Optional[str] = Field(
        default=None,
        alias="PUBLIC_BASE_URL",
        description="Public HTTPS base URL for externally reachable API endpoints like MCP OAuth",
    )
    
    # File paths
    customer_config_path: str = Field(default="/app/config/customer", alias="CUSTOMER_CONFIG_PATH")
    data_path: str = Field(default="/app/data", alias="CUSTOMER_DATA_PATH")
    logs_path: str = Field(default="/app/logs", alias="CUSTOMER_LOG_PATH")
    cache_path: str = Field(default="/app/cache", alias="CUSTOMER_CACHE_PATH")

    # Document processing configuration
    upload_directory: str = Field(default="./data/uploads", alias="UPLOAD_DIRECTORY")
    data_directory: str = Field(default="./data", alias="DATA_DIRECTORY")
    max_file_size_mb: int = Field(default=100, alias="MAX_FILE_SIZE_MB")
    supported_file_types: List[str] = Field(default=[
        "pdf",
        "doc",
        "docx",
        "txt",
        "md",
        "xls",
        "xlsx",
        "csv",
        "json"
    ], alias="SUPPORTED_FILE_TYPES")

    # Vector storage configuration
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")
    faiss_index_type: str = Field(default="IndexFlatIP", alias="FAISS_INDEX_TYPE")
    vector_index_directory: str = Field(default="./data/vectors", alias="VECTOR_INDEX_DIRECTORY")

    # Chunking configuration defaults
    default_chunk_size: int = Field(default=1024, alias="DEFAULT_CHUNK_SIZE")
    default_chunk_overlap: int = Field(default=128, alias="DEFAULT_CHUNK_OVERLAP")
    default_similarity_threshold: float = Field(default=0.85, alias="DEFAULT_SIMILARITY_THRESHOLD")

    # Authentication Configuration
    jwt_secret_key: str = Field(default="your-secret-key-change-in-production", alias="JWT_SECRET_KEY", description="JWT secret key for token signing")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM", description="JWT signing algorithm")
    jwt_expiration_hours: int = Field(default=8, alias="JWT_EXPIRATION_HOURS", description="JWT token expiration in hours")
    
    # Data Ingestion Configuration
    enable_ai_schema_mapping: bool = Field(default=False, alias="ENABLE_AI_SCHEMA_MAPPING", description="Enable AI-powered schema discovery and mapping")
    max_connector_records_default: int = Field(default=10000, alias="MAX_CONNECTOR_RECORDS_DEFAULT")
    connector_cost_per_record: float = Field(default=0.02, alias="CONNECTOR_COST_PER_RECORD")
    connector_cost_warning_threshold: float = Field(default=100.0, alias="CONNECTOR_COST_WARNING_THRESHOLD")
    connector_execution_timeout: int = Field(default=7200, alias="CONNECTOR_EXECUTION_TIMEOUT")
    pdl_default_rate_limit: int = Field(default=60, alias="PDL_DEFAULT_RATE_LIMIT")
    pdl_api_key: Optional[str] = Field(default=None, alias="PDL_API_KEY", description="People Data Labs API key for employee search")
    
    # ML Talent Intelligence Configuration
    ml_talent_pdl_query_limit: int = Field(default=50, alias="ML_TALENT_PDL_QUERY_LIMIT", description="Number of candidates to retrieve from PDL market search")
    resume_parsing_model: str = Field(default="gpt-4o", alias="RESUME_PARSING_MODEL", description="LLM model for resume parsing (text+LLM approach). Options: gpt-4o, gpt-5.2, gpt-4o-mini")
    
    # FASB RAG Configuration
    fasb_opensearch_host: str = Field(
        default="chzxazbhxqqye1nb189ah.us-east-1.aoss.amazonaws.com",
        alias="FASB_OPENSEARCH_HOST",
        description="OpenSearch Serverless host for FASB RAG"
    )
    fasb_opensearch_region: str = Field(
        default="us-east-1",
        alias="FASB_OPENSEARCH_REGION",
        description="AWS region for FASB OpenSearch Serverless"
    )
    fasb_opensearch_index: str = Field(
        default="fasb-chunks",
        alias="FASB_OPENSEARCH_INDEX",
        description="OpenSearch index name for FASB chunks"
    )
    fasb_memo_enabled: bool = Field(
        default=False,
        alias="FASB_MEMO_ENABLED",
        description="Enable secondary memo retrieval source for FASB RAG"
    )
    fasb_memo_opensearch_host: Optional[str] = Field(
        default=None,
        alias="FASB_MEMO_OPENSEARCH_HOST",
        description="Optional OpenSearch host for FASB memo source (defaults to FASB_OPENSEARCH_HOST)"
    )
    fasb_memo_opensearch_region: Optional[str] = Field(
        default=None,
        alias="FASB_MEMO_OPENSEARCH_REGION",
        description="Optional AWS region for FASB memo source (defaults to FASB_OPENSEARCH_REGION)"
    )
    fasb_memo_opensearch_index: Optional[str] = Field(
        default=None,
        alias="FASB_MEMO_OPENSEARCH_INDEX",
        description="Optional OpenSearch index name for memo chunks"
    )
    fasb_embed_model: str = Field(
        default="text-embedding-3-large",
        alias="FASB_EMBED_MODEL",
        description="OpenAI embedding model for FASB queries"
    )
    fasb_chat_model: str = Field(
        default="gpt-4o",
        alias="FASB_CHAT_MODEL",
        description="OpenAI chat model for FASB answers"
    )
    fasb_knn_k: int = Field(
        default=50,
        alias="FASB_KNN_K",
        description="Number of candidates for kNN retrieval"
    )
    fasb_retrieve_size: int = Field(
        default=12,
        alias="FASB_RETRIEVE_SIZE",
        description="Number of unique chunks to return after collapse"
    )
    fasb_rerank_keep: int = Field(
        default=8,
        alias="FASB_RERANK_KEEP",
        description="Number of chunks to keep after reranking"
    )
    fasb_docs_path: str = Field(
        default="data/eval/fasb_docs",
        alias="FASB_DOCS_PATH",
        description="Local path to FASB PDF documents for citation validation"
    )
    
    # Citation Validation Configuration
    citation_eval_similarity_threshold: float = Field(
        default=0.6,
        alias="CITATION_EVAL_SIMILARITY_THRESHOLD",
        description="Minimum similarity score for citation page validation"
    )
    citation_eval_vlm_model: str = Field(
        default="gpt-5.2",
        alias="CITATION_EVAL_VLM_MODEL",
        description="VLM model used when PDF text extraction fails (gpt-5.2 recommended)"
    )
    citation_eval_vlm_max_tokens: int = Field(
        default=400,
        alias="CITATION_EVAL_VLM_MAX_TOKENS",
        description="Max tokens for citation VLM validation responses"
    )
    
    # Langfuse observability
    langfuse_enabled: bool = Field(
        default=False,
        alias="LANGFUSE_ENABLED",
        description="Enable Langfuse tracing for RAG, eval, and optimization flows",
    )
    langfuse_public_key: Optional[str] = Field(
        default=None,
        alias="LANGFUSE_PUBLIC_KEY",
    )
    langfuse_secret_key: Optional[str] = Field(
        default=None,
        alias="LANGFUSE_SECRET_KEY",
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        alias="LANGFUSE_HOST",
    )
    langfuse_base_url: Optional[str] = Field(
        default=None,
        alias="LANGFUSE_BASE_URL",
        description="Legacy/quickstart alias for Langfuse host URL (used when LANGFUSE_HOST is not set)",
    )
    langfuse_public_url: Optional[str] = Field(
        default=None,
        alias="LANGFUSE_PUBLIC_URL",
        description="Browser-accessible Langfuse URL for dashboard links/embedding",
    )
    langfuse_project_id: Optional[str] = Field(
        default=None,
        alias="LANGFUSE_PROJECT_ID",
        description="Langfuse project identifier for deep links",
    )
    langfuse_embed_url: Optional[str] = Field(
        default=None,
        alias="LANGFUSE_EMBED_URL",
        description="Langfuse embed URL used by frontend telemetry pages; defaults to LANGFUSE_PUBLIC_URL",
    )
    
    # RAG Evaluation Configuration
    rag_eval_judge_model: str = Field(
        default="gpt-4o-mini",
        alias="RAG_EVAL_JUDGE_MODEL",
        description="Model used for judging RAG evaluation responses"
    )
    rag_eval_default_sample_size: int = Field(
        default=20,
        alias="RAG_EVAL_DEFAULT_SAMPLE_SIZE",
        description="Default number of questions to sample for evaluation"
    )
    rag_eval_default_concurrency: int = Field(
        default=3,
        alias="RAG_EVAL_DEFAULT_CONCURRENCY",
        description="Default concurrency for evaluation runs"
    )
    rag_eval_questions_path: str = Field(
        default="data/eval/eval_questions.jsonl",
        alias="RAG_EVAL_QUESTIONS_PATH",
        description="Path to evaluation questions JSONL file"
    )
    
    # Data Analyst Conversation Limits (Centralized)
    data_analyst_max_messages_per_conversation: int = Field(
        default=100, 
        alias="DATA_ANALYST_MAX_MESSAGES_PER_CONVERSATION",
        description="Maximum number of messages allowed per conversation"
    )
    data_analyst_max_active_conversations_per_user: int = Field(
        default=100, 
        alias="DATA_ANALYST_MAX_ACTIVE_CONVERSATIONS_PER_USER",
        description="Maximum number of active conversations per user"
    )
    data_analyst_context_window_size: int = Field(
        default=10, 
        alias="DATA_ANALYST_CONTEXT_WINDOW_SIZE",
        description="Number of previous messages to include in context (sliding window)"
    )
    data_analyst_context_data_rows: int = Field(
        default=5, 
        alias="DATA_ANALYST_CONTEXT_DATA_ROWS",
        description="Number of data rows to include in conversation context (first N rows only)"
    )
    
    # Search Store Sync Configuration
    elasticsearch_sync_enabled: bool = Field(default=True, alias="ELASTICSEARCH_SYNC_ENABLED", description="Enable automatic sync to Elasticsearch for person search")
    neo4j_sync_enabled: bool = Field(default=True, alias="NEO4J_SYNC_ENABLED", description="Enable automatic sync to Neo4j for relationship analysis")
    elasticsearch_hosts: List[str] | str = Field(default=["http://elasticsearch:9200"], alias="ELASTICSEARCH_HOSTS", description="Elasticsearch cluster hosts (comma-separated string or JSON array)")
    elasticsearch_index_prefix: str = Field(default="pdl_persons", alias="ELASTICSEARCH_INDEX_PREFIX", description="Prefix for Elasticsearch indexes")
    mcp_redis_db: int = Field(
        default=2,
        alias="MCP_REDIS_DB",
        description="Redis DB index used by MCP sessions, OAuth state, and caches",
    )
    mcp_redis_required: bool = Field(
        default=False,
        alias="MCP_REDIS_REQUIRED",
        description="Require Redis for MCP startup instead of falling back to in-memory state",
    )
    
    # Native RAG Configuration
    # Uses VLM for parsing, OpenAI embeddings, AWS OpenSearch for vectors
    rag_vlm_base_url: str = Field(default="http://localhost:8000/v1", alias="RAG_VLM_BASE_URL", description="VLM API base URL for document parsing (OpenAI-compatible)")
    rag_vlm_model: str = Field(default="default", alias="RAG_VLM_MODEL", description="VLM model name for document parsing")
    rag_parser_page_concurrency: int = Field(default=8, alias="RAG_PARSER_PAGE_CONCURRENCY", description="Max concurrent page OCR requests per document (VLM/GPT-4o)")
    rag_parser_page_batch_size: int = Field(default=16, alias="RAG_PARSER_PAGE_BATCH_SIZE", description="Number of pages submitted per parser batch")
    rag_parser_request_timeout_seconds: int = Field(default=120, alias="RAG_PARSER_REQUEST_TIMEOUT_SECONDS", description="Timeout (seconds) for each OCR page request")
    rag_parser_retry_attempts: int = Field(default=2, alias="RAG_PARSER_RETRY_ATTEMPTS", description="Retry attempts per page for transient OCR API failures")
    rag_parser_retry_backoff_seconds: float = Field(default=1.5, alias="RAG_PARSER_RETRY_BACKOFF_SECONDS", description="Base backoff seconds between OCR retries")
    rag_parser_openai_max_tokens: int = Field(default=4096, alias="RAG_PARSER_OPENAI_MAX_TOKENS", description="Max GPT-4o completion tokens per page")
    rag_kb_s3_sync_enabled: bool = Field(
        default=True,
        alias="RAG_KB_S3_SYNC_ENABLED",
        description="Enable periodic sync of S3-backed knowledge bases",
    )
    rag_kb_s3_sync_interval_seconds: int = Field(
        default=60,
        alias="RAG_KB_S3_SYNC_INTERVAL_SECONDS",
        description="Scheduler interval (seconds) for dispatching S3 KB sync tasks",
    )
    rag_kb_s3_sync_max_files_per_run: int = Field(
        default=25,
        alias="RAG_KB_S3_SYNC_MAX_FILES_PER_RUN",
        description="Max new/updated files ingested per KB sync execution",
    )
    rag_opensearch_host: str = Field(default="", alias="RAG_OPENSEARCH_HOST", description="AWS OpenSearch Serverless collection endpoint (e.g. xxx.region.aoss.amazonaws.com); can be Terraform output")
    rag_opensearch_region: str = Field(default="us-east-1", alias="RAG_OPENSEARCH_REGION", description="AWS region for OpenSearch (must match collection region)")
    rag_opensearch_index_prefix: str = Field(default="rag_domains", alias="RAG_OPENSEARCH_INDEX_PREFIX", description="Index prefix for RAG domains; set to match Terraform (e.g. eliza_rag_dev). Normalized to [a-z0-9_-] for AOSS")
    rag_use_local_elasticsearch: bool = Field(default=False, alias="RAG_USE_LOCAL_ELASTICSEARCH", description="Use local Elasticsearch instead of AWS OpenSearch")
    rag_embedding_provider: str = Field(default="bedrock", alias="RAG_EMBEDDING_PROVIDER", description="Embedding provider: openai, local, or bedrock")
    rag_bedrock_embedding_region: str = Field(default="us-east-1", alias="RAG_BEDROCK_EMBEDDING_REGION", description="AWS region for Bedrock Titan embeddings (when RAG_EMBEDDING_PROVIDER=bedrock)")

    # Metadata enrichment
    rag_metadata_enrichment_tier: str = Field(default="standard", alias="RAG_METADATA_ENRICHMENT_TIER", description="Metadata enrichment level: basic (no LLM), standard (doc summary), full (per-chunk LLM)")
    rag_metadata_enrichment_model: str = Field(default="gpt-4o-mini", alias="RAG_METADATA_ENRICHMENT_MODEL", description="LLM model for metadata enrichment")

    # RAG Ingestion Service (optional remote processing)
    rag_ingestion_service_url: Optional[str] = Field(default=None, alias="RAG_INGESTION_SERVICE_URL", description="When set, delegates parse/chunk/embed/index to a remote ingestion service (e.g. http://rag-ingestion:8100)")

    # Legacy config names (kept for compatibility)
    ragflow_base_url: str = Field(default="", alias="RAGFLOW_BASE_URL", description="[DEPRECATED] Use RAG_VLM_BASE_URL")
    ragflow_api_key: Optional[str] = Field(default=None, alias="RAGFLOW_API_KEY", description="[DEPRECATED] No longer used")
    ragflow_default_embedding_model: str = Field(default="amazon.titan-embed-text-v2:0", alias="RAGFLOW_DEFAULT_EMBEDDING_MODEL", description="Embedding model for RAG")
    ragflow_default_parser: str = Field(default="vlm", alias="RAGFLOW_DEFAULT_PARSER", description="Document parser (naive, docling, vlm)")
    ragflow_default_chunk_size: int = Field(default=512, alias="RAGFLOW_DEFAULT_CHUNK_SIZE", description="Default chunk token count for RAG")
    ragflow_prompt_domain: str = Field(default="knowledge_base", alias="RAGFLOW_PROMPT_DOMAIN", description="Prompt management domain for RAG prompts")
    ragflow_query_rewrite_enabled: bool = Field(default=True, alias="RAGFLOW_QUERY_REWRITE_ENABLED", description="Enable query rewrite for retrieval")
    ragflow_rerank_enabled: bool = Field(default=False, alias="RAGFLOW_RERANK_ENABLED", description="Enable LLM reranking for retrieval")
    ragflow_rerank_keep: int = Field(default=8, alias="RAGFLOW_RERANK_KEEP", description="Number of chunks to keep after rerank")
    ragflow_max_retrieve_k: int = Field(default=10, alias="RAGFLOW_MAX_RETRIEVE_K", description="Maximum chunks to retrieve")
    ragflow_fallback_similarity_threshold: float = Field(default=0.05, alias="RAGFLOW_FALLBACK_SIMILARITY_THRESHOLD", description="Minimum similarity threshold")
    ragflow_max_context_chars: int = Field(default=16000, alias="RAGFLOW_MAX_CONTEXT_CHARS", description="Max characters to include in answer context")
    
    # HubSpot Retrieval Configuration
    hubspot_filter_group_limit: int = Field(default=5, alias="HUBSPOT_FILTER_GROUP_LIMIT", description="Max filter groups per HubSpot search")
    hubspot_filter_total_limit: int = Field(default=25, alias="HUBSPOT_FILTER_TOTAL_LIMIT", description="Max total filters per HubSpot search")
    hubspot_filters_per_group: int = Field(default=10, alias="HUBSPOT_FILTERS_PER_GROUP", description="Max filters per filter group")
    hubspot_client_id: str = Field(default="", alias="HUBSPOT_CLIENT_ID", description="HubSpot OAuth client ID")
    hubspot_client_secret: str = Field(default="", alias="HUBSPOT_CLIENT_SECRET", description="HubSpot OAuth client secret")
    hubspot_redirect_uri: str = Field(default="", alias="HUBSPOT_REDIRECT_URI", description="HubSpot OAuth redirect URI")
    oauth_state_secret: str = Field(default="", alias="OAUTH_STATE_SECRET", description="Secret for HMAC-signing OAuth state tokens")
    master_encryption_key: str = Field(default="", alias="MASTER_ENCRYPTION_KEY", description="Master key for tenant-scoped token encryption (Fernet/HKDF)")

    # PDF cache (local MinIO) - reuses tenant MinIO when specific keys are empty
    minio_endpoint: str = Field(default="", alias="MINIO_ENDPOINT", description="MinIO endpoint URL for local object storage")
    minio_access_key: str = Field(default="", alias="MINIO_ACCESS_KEY", description="MinIO access key")
    minio_secret_key: str = Field(default="", alias="MINIO_SECRET_KEY", description="MinIO secret key")
    pdf_cache_endpoint: str = Field(default="", alias="PDF_CACHE_ENDPOINT", description="Override MinIO endpoint for PDF cache bucket")
    pdf_cache_access_key: str = Field(default="", alias="PDF_CACHE_ACCESS_KEY", description="Override access key for PDF cache")
    pdf_cache_secret_key: str = Field(default="", alias="PDF_CACHE_SECRET_KEY", description="Override secret key for PDF cache")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment."""
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Environment must be one of: {valid_envs}")
        return v.lower()

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, v):
        """Validate externally reachable public base URL."""
        if v is None:
            return None
        cleaned = v.strip().rstrip("/")
        if not cleaned:
            return None
        if not cleaned.startswith(("https://", "http://")):
            raise ValueError("PUBLIC_BASE_URL must start with http:// or https://")
        return cleaned

    @field_validator("allowed_origins", mode="after")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse allowed origins from string to list."""
        if isinstance(v, str):
            if not v.strip():  # Handle empty string
                return []
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v or []

    @field_validator("allowed_hosts", mode="after")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse allowed hosts from string to list."""
        if isinstance(v, str):
            if not v.strip():  # Handle empty string
                return []
            return [host.strip() for host in v.split(",") if host.strip()]
        return v or []

    @field_validator("elasticsearch_hosts", mode="after")
    @classmethod
    def parse_elasticsearch_hosts(cls, v):
        """Parse elasticsearch hosts from string to list."""
        if isinstance(v, str):
            if not v.strip():  # Handle empty string
                return ["http://elasticsearch:9200"]  # Default
            return [host.strip() for host in v.split(",") if host.strip()]
        return v or ["http://elasticsearch:9200"]

    @property
    def OPENAI_API_KEY(self) -> Optional[str]:
        """Maintain backwards compatibility for uppercase attribute access."""
        return self.openai_api_key

    @property
    def OPENAI_API_BASE_URL(self) -> str:
        return self.openai_api_base_url

    @property
    def DEFAULT_LLM_MODEL(self) -> str:
        return self.default_llm_model

    @property
    def allowed_origins_list(self) -> List[str]:
        """Get allowed origins as a list."""
        return self.parse_allowed_origins(self.allowed_origins)

    @property
    def allowed_hosts_list(self) -> List[str]:
        """Get allowed hosts as a list."""
        return self.parse_allowed_hosts(self.allowed_hosts)

    @property
    def redis_host_url(self) -> str:
        """Build Redis URL from host/port if needed."""
        if self.redis_url:
            return self.redis_url
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'  # Allow extra env vars that don't match any field
    )


class CustomerConfig:
    """Customer-specific configuration loader."""
    
    def __init__(self, customer_id: str, config_path: str):
        self.customer_id = customer_id
        self.config_path = Path(config_path)
        self._config_data: Optional[Dict[str, Any]] = None
    
    def load_config(self) -> Dict[str, Any]:
        """Load customer configuration from YAML file."""
        if self._config_data is not None:
            return self._config_data
        
        config_file = self.config_path / "config.yml"
        
        if not config_file.exists():
            # Try default config
            default_config_file = Path("/app/config/default/config.yml")
            if default_config_file.exists():
                config_file = default_config_file
            else:
                raise FileNotFoundError(f"Customer config not found: {config_file}")
        
        try:
            with open(config_file, 'r') as f:
                self._config_data = yaml.safe_load(f)
            return self._config_data
        except Exception as e:
            raise ValueError(f"Failed to load customer config: {e}")
    
    @property
    def branding(self) -> Dict[str, Any]:
        """Get branding configuration."""
        config = self.load_config()
        return config.get("branding", {})
    
    @property
    def data_sources(self) -> List[Dict[str, Any]]:
        """Get data sources configuration."""
        config = self.load_config()
        return config.get("data_sources", [])
    
    @property
    def model_config(self) -> Dict[str, Any]:
        """Get model configuration."""
        config = self.load_config()
        return config.get("model_config", {})
    
    @property
    def security_config(self) -> Dict[str, Any]:
        """Get security configuration."""
        config = self.load_config()
        return config.get("security_config", {})
    
    @property
    def business_rules(self) -> Dict[str, Any]:
        """Get business rules configuration."""
        config = self.load_config()
        return config.get("business_rules", {})
    
    def get_enabled_data_sources(self) -> List[Dict[str, Any]]:
        """Get only enabled data sources."""
        return [ds for ds in self.data_sources if ds.get("enabled", False)]
    
    def get_model_for_task(self, task: str) -> str:
        """Get the configured model for a specific task."""
        models = self.model_config.get("models", {})
        return models.get(task, models.get("default", "gpt-4o-mini"))
    
    def get_default_provider(self) -> str:
        """Get the default AI provider."""
        return self.model_config.get("default_provider", "openai")
    
    def get_fallback_providers(self) -> List[str]:
        """Get fallback AI providers."""
        return self.model_config.get("fallback_providers", ["anthropic", "groq"])


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


@lru_cache()
def get_customer_config(customer_id: str = None) -> CustomerConfig:
    """Get cached customer configuration."""
    settings = get_settings()
    customer_id = customer_id or settings.customer_id
    return CustomerConfig(customer_id, settings.customer_config_path)


def get_database_url() -> str:
    """Get database URL with proper formatting."""
    settings = get_settings()
    return settings.database_url


def get_redis_url() -> str:
    """Get Redis URL with proper formatting."""
    settings = get_settings()
    return settings.redis_host_url


def get_neo4j_config() -> Dict[str, str]:
    """Get Neo4j configuration."""
    settings = get_settings()
    return {
        "uri": settings.neo4j_uri,
        "user": settings.neo4j_user,
        "password": settings.neo4j_password
    }
