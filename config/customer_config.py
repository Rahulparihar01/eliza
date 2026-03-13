from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import yaml
import os

@dataclass
class BrandingConfig:
    """Customer branding configuration"""
    company_name: str
    logo_url: Optional[str] = None
    primary_color: str = "#2F6BFF"
    secondary_color: str = "#8B5CF6"
    custom_css: Optional[str] = None

@dataclass
class DataSourceConfig:
    """Data source configuration"""
    name: str
    type: str  # hr, crm, financial, linkedin, documents, research
    enabled: bool = True
    connection_config: Dict[str, Any] = field(default_factory=dict)
    chunking_strategy: str = "semantic"
    qa_rag_enabled: bool = False

@dataclass
class ModelConfig:
    """AI model configuration"""
    default_provider: str = "openai"
    models: Dict[str, str] = field(default_factory=lambda: {
        "intent_analysis": "gpt-4o-mini",
        "context_enrichment": "gpt-4o",
        "prompt_generation": "gpt-4o",
        "embeddings": "text-embedding-3-small"
    })
    fallback_providers: List[str] = field(default_factory=lambda: ["anthropic", "groq"])

@dataclass
class SecurityConfig:
    """Security configuration"""
    jwt_secret_key: str
    session_timeout_minutes: int = 60
    max_login_attempts: int = 5
    require_2fa: bool = False
    allowed_domains: List[str] = field(default_factory=list)

@dataclass
class BusinessRulesConfig:
    """Business-specific rules and constraints"""
    departments: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    custom_analysis_rules: Dict[str, Any] = field(default_factory=dict)
    roi_calculation_method: str = "realistic"  # conservative, realistic, optimistic

@dataclass
class CustomerConfig:
    """Complete customer configuration"""
    customer_id: str
    customer_name: str
    branding: BrandingConfig
    data_sources: List[DataSourceConfig]
    model_config: ModelConfig
    security_config: SecurityConfig
    business_rules: BusinessRulesConfig
    created_at: str
    updated_at: str
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'CustomerConfig':
        """Load customer configuration from YAML file"""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        return cls(
            customer_id=config_data['customer_id'],
            customer_name=config_data['customer_name'],
            branding=BrandingConfig(**config_data['branding']),
            data_sources=[DataSourceConfig(**ds) for ds in config_data['data_sources']],
            model_config=ModelConfig(**config_data['model_config']),
            security_config=SecurityConfig(**config_data['security_config']),
            business_rules=BusinessRulesConfig(**config_data['business_rules']),
            created_at=config_data['created_at'],
            updated_at=config_data['updated_at']
        )
    
    def save_to_file(self, config_path: str):
        """Save customer configuration to YAML file"""
        config_data = {
            'customer_id': self.customer_id,
            'customer_name': self.customer_name,
            'branding': self.branding.__dict__,
            'data_sources': [ds.__dict__ for ds in self.data_sources],
            'model_config': self.model_config.__dict__,
            'security_config': self.security_config.__dict__,
            'business_rules': self.business_rules.__dict__,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
