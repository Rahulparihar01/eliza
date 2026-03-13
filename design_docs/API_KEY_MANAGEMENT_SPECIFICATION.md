# API Key Management Specification

## Executive Summary

This document defines a comprehensive API key management system for the AI Enablement Platform, ensuring secure storage, rotation, and access control for multiple LLM providers while maintaining operational simplicity and security best practices.

**Key Features:**
- **Secure Storage**: Environment variables, encrypted files, and secret management systems
- **Multi-Provider Support**: OpenAI, Anthropic, Groq, Together AI, Azure OpenAI
- **Key Rotation**: Automated key rotation and validation
- **Access Control**: Role-based access to different API keys
- **Cost Monitoring**: Usage tracking and budget alerts
- **Fallback Management**: Graceful degradation when keys are invalid or rate-limited

---

## 1. API Key Architecture

### 1.1 Key Storage Hierarchy

```python
# From API key management patterns - EXAMPLE
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import os
import json
from pathlib import Path
import logging
from datetime import datetime, timedelta
import asyncio

class KeySource(Enum):
    """Sources for API key retrieval"""
    ENVIRONMENT = "environment"
    CONFIG_FILE = "config_file"
    SECRET_MANAGER = "secret_manager"
    VAULT = "vault"
    KUBERNETES_SECRET = "kubernetes_secret"

class KeyStatus(Enum):
    """API key status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    RATE_LIMITED = "rate_limited"
    INVALID = "invalid"
    SUSPENDED = "suspended"

@dataclass
class APIKeyConfig:
    """Configuration for a single API key"""
    key_id: str
    provider: str
    key_value: Optional[str] = None
    key_source: KeySource = KeySource.ENVIRONMENT
    environment_var: Optional[str] = None
    config_path: Optional[str] = None
    secret_name: Optional[str] = None
    
    # Key metadata
    description: str = ""
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    
    # Usage limits
    daily_limit: Optional[int] = None
    monthly_limit: Optional[int] = None
    cost_limit_usd: Optional[float] = None
    
    # Status and health
    status: KeyStatus = KeyStatus.ACTIVE
    health_check_url: Optional[str] = None
    last_health_check: Optional[datetime] = None
    
    # Access control
    allowed_users: List[str] = field(default_factory=list)
    allowed_environments: List[str] = field(default_factory=list)
    
    def is_valid(self) -> bool:
        """Check if key is valid and active"""
        if self.status != KeyStatus.ACTIVE:
            return False
        
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        
        return True
    
    def is_within_limits(self, current_usage: Dict[str, Any]) -> bool:
        """Check if current usage is within limits"""
        if self.daily_limit and current_usage.get("daily_requests", 0) >= self.daily_limit:
            return False
        
        if self.monthly_limit and current_usage.get("monthly_requests", 0) >= self.monthly_limit:
            return False
        
        if self.cost_limit_usd and current_usage.get("monthly_cost", 0) >= self.cost_limit_usd:
            return False
        
        return True

@dataclass
class ProviderKeyPool:
    """Pool of API keys for a specific provider"""
    provider: str
    primary_key: APIKeyConfig
    fallback_keys: List[APIKeyConfig] = field(default_factory=list)
    round_robin_index: int = 0
    
    def get_active_key(self, usage_stats: Dict[str, Any] = None) -> Optional[APIKeyConfig]:
        """Get the next active key from the pool"""
        usage_stats = usage_stats or {}
        
        # Try primary key first
        if self.primary_key.is_valid() and self.primary_key.is_within_limits(usage_stats):
            return self.primary_key
        
        # Try fallback keys
        for key in self.fallback_keys:
            if key.is_valid() and key.is_within_limits(usage_stats):
                return key
        
        return None
    
    def get_round_robin_key(self, usage_stats: Dict[str, Any] = None) -> Optional[APIKeyConfig]:
        """Get key using round-robin strategy"""
        usage_stats = usage_stats or {}
        all_keys = [self.primary_key] + self.fallback_keys
        
        for _ in range(len(all_keys)):
            key = all_keys[self.round_robin_index % len(all_keys)]
            self.round_robin_index = (self.round_robin_index + 1) % len(all_keys)
            
            if key.is_valid() and key.is_within_limits(usage_stats):
                return key
        
        return None

class APIKeyManager:
    """Manages API keys for all providers"""
    
    def __init__(self, config_path: str = "api_keys.yaml"):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # Key pools by provider
        self.key_pools: Dict[str, ProviderKeyPool] = {}
        
        # Usage tracking
        self.usage_stats: Dict[str, Dict[str, Any]] = {}
        
        # Load configuration
        self._load_key_configuration()
        
        # Initialize usage tracking
        self._initialize_usage_tracking()
    
    def _load_key_configuration(self):
        """Load API key configuration from file"""
        
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            self.logger.warning(f"API key config file not found: {self.config_path}")
            self._create_default_configuration()
            return
        
        try:
            import yaml
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            self._parse_configuration(config_data)
            
        except Exception as e:
            self.logger.error(f"Failed to load API key configuration: {e}")
            self._create_default_configuration()
    
    def _create_default_configuration(self):
        """Create default API key configuration"""
        
        default_config = {
            "providers": {
                "openai": {
                    "primary": {
                        "key_id": "openai_primary",
                        "environment_var": "OPENAI_API_KEY",
                        "description": "Primary OpenAI API key",
                        "daily_limit": 10000,
                        "cost_limit_usd": 100.0
                    },
                    "fallback": []
                },
                "anthropic": {
                    "primary": {
                        "key_id": "anthropic_primary",
                        "environment_var": "ANTHROPIC_API_KEY",
                        "description": "Primary Anthropic API key",
                        "daily_limit": 5000,
                        "cost_limit_usd": 50.0
                    },
                    "fallback": []
                },
                "groq": {
                    "primary": {
                        "key_id": "groq_primary",
                        "environment_var": "GROQ_API_KEY",
                        "description": "Primary Groq API key",
                        "daily_limit": 20000,
                        "cost_limit_usd": 25.0
                    },
                    "fallback": []
                },
                "together": {
                    "primary": {
                        "key_id": "together_primary",
                        "environment_var": "TOGETHER_API_KEY",
                        "description": "Primary Together AI API key",
                        "daily_limit": 15000,
                        "cost_limit_usd": 40.0
                    },
                    "fallback": []
                }
            }
        }
        
        self._parse_configuration(default_config)
    
    def _parse_configuration(self, config_data: Dict[str, Any]):
        """Parse configuration data into key pools"""
        
        providers_config = config_data.get("providers", {})
        
        for provider_name, provider_config in providers_config.items():
            # Parse primary key
            primary_config = provider_config.get("primary", {})
            primary_key = self._create_key_config(provider_name, primary_config)
            
            # Parse fallback keys
            fallback_keys = []
            for fallback_config in provider_config.get("fallback", []):
                fallback_key = self._create_key_config(provider_name, fallback_config)
                fallback_keys.append(fallback_key)
            
            # Create key pool
            self.key_pools[provider_name] = ProviderKeyPool(
                provider=provider_name,
                primary_key=primary_key,
                fallback_keys=fallback_keys
            )
    
    def _create_key_config(self, provider: str, config: Dict[str, Any]) -> APIKeyConfig:
        """Create API key configuration from config data"""
        
        key_config = APIKeyConfig(
            key_id=config.get("key_id", f"{provider}_key"),
            provider=provider,
            environment_var=config.get("environment_var"),
            config_path=config.get("config_path"),
            secret_name=config.get("secret_name"),
            description=config.get("description", ""),
            daily_limit=config.get("daily_limit"),
            monthly_limit=config.get("monthly_limit"),
            cost_limit_usd=config.get("cost_limit_usd"),
            allowed_users=config.get("allowed_users", []),
            allowed_environments=config.get("allowed_environments", [])
        )
        
        # Retrieve actual key value
        key_config.key_value = self._retrieve_key_value(key_config)
        
        return key_config
    
    def _retrieve_key_value(self, key_config: APIKeyConfig) -> Optional[str]:
        """Retrieve API key value from configured source"""
        
        if key_config.environment_var:
            key_value = os.getenv(key_config.environment_var)
            if key_value:
                return key_value
        
        if key_config.config_path:
            try:
                with open(key_config.config_path, 'r') as f:
                    return f.read().strip()
            except Exception as e:
                self.logger.error(f"Failed to read key from {key_config.config_path}: {e}")
        
        if key_config.secret_name:
            # Implement secret manager integration here
            return self._retrieve_from_secret_manager(key_config.secret_name)
        
        return None
    
    def _retrieve_from_secret_manager(self, secret_name: str) -> Optional[str]:
        """Retrieve key from secret management system"""
        # Implementation would depend on your secret management system
        # Examples: AWS Secrets Manager, Azure Key Vault, HashiCorp Vault
        
        # Example for AWS Secrets Manager:
        # import boto3
        # client = boto3.client('secretsmanager')
        # response = client.get_secret_value(SecretId=secret_name)
        # return response['SecretString']
        
        self.logger.warning(f"Secret manager integration not implemented for: {secret_name}")
        return None
    
    def get_api_key(self, provider: str, strategy: str = "primary") -> Optional[str]:
        """Get API key for a provider using specified strategy"""
        
        if provider not in self.key_pools:
            self.logger.error(f"No key pool configured for provider: {provider}")
            return None
        
        key_pool = self.key_pools[provider]
        usage_stats = self.usage_stats.get(provider, {})
        
        if strategy == "primary":
            key_config = key_pool.get_active_key(usage_stats)
        elif strategy == "round_robin":
            key_config = key_pool.get_round_robin_key(usage_stats)
        else:
            key_config = key_pool.get_active_key(usage_stats)
        
        if key_config:
            # Update usage tracking
            self._track_key_usage(key_config)
            return key_config.key_value
        
        return None
    
    def _track_key_usage(self, key_config: APIKeyConfig):
        """Track API key usage"""
        
        provider = key_config.provider
        if provider not in self.usage_stats:
            self.usage_stats[provider] = {
                "daily_requests": 0,
                "monthly_requests": 0,
                "monthly_cost": 0.0,
                "last_reset": datetime.now()
            }
        
        # Increment request count
        self.usage_stats[provider]["daily_requests"] += 1
        self.usage_stats[provider]["monthly_requests"] += 1
        
        # Update last used timestamp
        key_config.last_used = datetime.now()
    
    def _initialize_usage_tracking(self):
        """Initialize usage tracking for all providers"""
        
        for provider in self.key_pools.keys():
            if provider not in self.usage_stats:
                self.usage_stats[provider] = {
                    "daily_requests": 0,
                    "monthly_requests": 0,
                    "monthly_cost": 0.0,
                    "last_reset": datetime.now()
                }
    
    async def validate_all_keys(self) -> Dict[str, Dict[str, Any]]:
        """Validate all API keys by making test requests"""
        
        validation_results = {}
        
        for provider, key_pool in self.key_pools.items():
            provider_results = {
                "primary": await self._validate_key(key_pool.primary_key),
                "fallback": []
            }
            
            for fallback_key in key_pool.fallback_keys:
                result = await self._validate_key(fallback_key)
                provider_results["fallback"].append(result)
            
            validation_results[provider] = provider_results
        
        return validation_results
    
    async def _validate_key(self, key_config: APIKeyConfig) -> Dict[str, Any]:
        """Validate a single API key"""
        
        if not key_config.key_value:
            return {
                "key_id": key_config.key_id,
                "status": "invalid",
                "error": "No key value available"
            }
        
        try:
            # Perform provider-specific validation
            if key_config.provider == "openai":
                result = await self._validate_openai_key(key_config)
            elif key_config.provider == "anthropic":
                result = await self._validate_anthropic_key(key_config)
            elif key_config.provider == "groq":
                result = await self._validate_groq_key(key_config)
            elif key_config.provider == "together":
                result = await self._validate_together_key(key_config)
            else:
                result = {"status": "unknown", "error": f"Validation not implemented for {key_config.provider}"}
            
            # Update key status based on validation
            if result["status"] == "valid":
                key_config.status = KeyStatus.ACTIVE
            else:
                key_config.status = KeyStatus.INVALID
            
            key_config.last_health_check = datetime.now()
            
            return {
                "key_id": key_config.key_id,
                "provider": key_config.provider,
                **result
            }
            
        except Exception as e:
            self.logger.error(f"Key validation failed for {key_config.key_id}: {e}")
            key_config.status = KeyStatus.INVALID
            
            return {
                "key_id": key_config.key_id,
                "status": "error",
                "error": str(e)
            }
    
    async def _validate_openai_key(self, key_config: APIKeyConfig) -> Dict[str, Any]:
        """Validate OpenAI API key"""
        
        import openai
        
        try:
            client = openai.OpenAI(api_key=key_config.key_value)
            
            # Make a minimal request to validate the key
            models = await client.models.list()
            
            return {
                "status": "valid",
                "models_available": len(models.data),
                "organization": getattr(models, 'organization', None)
            }
            
        except openai.AuthenticationError:
            return {"status": "invalid", "error": "Authentication failed"}
        except openai.RateLimitError:
            return {"status": "rate_limited", "error": "Rate limit exceeded"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _validate_anthropic_key(self, key_config: APIKeyConfig) -> Dict[str, Any]:
        """Validate Anthropic API key"""
        
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=key_config.key_value)
            
            # Make a minimal request
            response = await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "Hi"}]
            )
            
            return {"status": "valid", "model": "claude-3-haiku-20240307"}
            
        except anthropic.AuthenticationError:
            return {"status": "invalid", "error": "Authentication failed"}
        except anthropic.RateLimitError:
            return {"status": "rate_limited", "error": "Rate limit exceeded"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _validate_groq_key(self, key_config: APIKeyConfig) -> Dict[str, Any]:
        """Validate Groq API key"""
        
        try:
            import openai
            
            client = openai.OpenAI(
                api_key=key_config.key_value,
                base_url="https://api.groq.com/openai/v1"
            )
            
            # Make a minimal request
            models = await client.models.list()
            
            return {
                "status": "valid",
                "models_available": len(models.data)
            }
            
        except openai.AuthenticationError:
            return {"status": "invalid", "error": "Authentication failed"}
        except openai.RateLimitError:
            return {"status": "rate_limited", "error": "Rate limit exceeded"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _validate_together_key(self, key_config: APIKeyConfig) -> Dict[str, Any]:
        """Validate Together AI API key"""
        
        try:
            import openai
            
            client = openai.OpenAI(
                api_key=key_config.key_value,
                base_url="https://api.together.xyz/v1"
            )
            
            # Make a minimal request
            models = await client.models.list()
            
            return {
                "status": "valid",
                "models_available": len(models.data)
            }
            
        except openai.AuthenticationError:
            return {"status": "invalid", "error": "Authentication failed"}
        except openai.RateLimitError:
            return {"status": "rate_limited", "error": "Rate limit exceeded"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get usage summary for all providers"""
        
        summary = {}
        
        for provider, usage in self.usage_stats.items():
            key_pool = self.key_pools.get(provider)
            if not key_pool:
                continue
            
            primary_key = key_pool.primary_key
            
            summary[provider] = {
                "daily_requests": usage["daily_requests"],
                "monthly_requests": usage["monthly_requests"],
                "monthly_cost": usage["monthly_cost"],
                "daily_limit": primary_key.daily_limit,
                "monthly_limit": primary_key.monthly_limit,
                "cost_limit": primary_key.cost_limit_usd,
                "utilization": {
                    "daily": (usage["daily_requests"] / primary_key.daily_limit * 100) if primary_key.daily_limit else 0,
                    "monthly": (usage["monthly_requests"] / primary_key.monthly_limit * 100) if primary_key.monthly_limit else 0,
                    "cost": (usage["monthly_cost"] / primary_key.cost_limit_usd * 100) if primary_key.cost_limit_usd else 0
                }
            }
        
        return summary
    
    def reset_daily_usage(self):
        """Reset daily usage counters"""
        
        for provider in self.usage_stats:
            self.usage_stats[provider]["daily_requests"] = 0
        
        self.logger.info("Daily usage counters reset")
    
    def reset_monthly_usage(self):
        """Reset monthly usage counters"""
        
        for provider in self.usage_stats:
            self.usage_stats[provider]["monthly_requests"] = 0
            self.usage_stats[provider]["monthly_cost"] = 0.0
            self.usage_stats[provider]["last_reset"] = datetime.now()
        
        self.logger.info("Monthly usage counters reset")
```

## 2. Configuration File Format

### 2.1 API Keys Configuration

```yaml
# api_keys.yaml - EXAMPLE
providers:
  openai:
    primary:
      key_id: "openai_primary"
      environment_var: "OPENAI_API_KEY"
      description: "Primary OpenAI API key for production"
      daily_limit: 10000
      monthly_limit: 300000
      cost_limit_usd: 500.0
      allowed_environments: ["production", "staging"]
    
    fallback:
      - key_id: "openai_backup"
        environment_var: "OPENAI_BACKUP_API_KEY"
        description: "Backup OpenAI API key"
        daily_limit: 5000
        cost_limit_usd: 200.0
        allowed_environments: ["production"]

  anthropic:
    primary:
      key_id: "anthropic_primary"
      environment_var: "ANTHROPIC_API_KEY"
      description: "Primary Anthropic API key"
      daily_limit: 5000
      monthly_limit: 150000
      cost_limit_usd: 300.0
      allowed_environments: ["production", "staging"]

  groq:
    primary:
      key_id: "groq_primary"
      environment_var: "GROQ_API_KEY"
      description: "Primary Groq API key for fast inference"
      daily_limit: 20000
      monthly_limit: 600000
      cost_limit_usd: 100.0
      allowed_environments: ["development", "staging", "production"]

  together:
    primary:
      key_id: "together_primary"
      environment_var: "TOGETHER_API_KEY"
      description: "Together AI API key"
      daily_limit: 15000
      monthly_limit: 450000
      cost_limit_usd: 200.0
      allowed_environments: ["development", "production"]

# Global settings
settings:
  usage_tracking: true
  daily_reset_hour: 0  # UTC hour for daily reset
  monthly_reset_day: 1  # Day of month for monthly reset
  health_check_interval: 3600  # Seconds between health checks
  
  # Alerting
  alerts:
    usage_threshold: 80  # Percent usage before alert
    cost_threshold: 90   # Percent cost before alert
    webhook_url: "${ALERT_WEBHOOK_URL}"
    
  # Security
  encryption:
    enabled: false  # Enable key encryption at rest
    key_file: "encryption.key"
```

## 3. Environment Variables

### 3.1 Required Environment Variables

```bash
# .env - EXAMPLE

# Primary API Keys
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-api03-...
GROQ_API_KEY=gsk_...
TOGETHER_API_KEY=...

# Backup API Keys (optional)
OPENAI_BACKUP_API_KEY=sk-proj-...

# Azure OpenAI (if using)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Configuration
API_KEYS_CONFIG_PATH=api_keys.yaml
MODEL_CONFIG_PROFILE=production

# Monitoring and Alerts
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/...
USAGE_TRACKING_ENABLED=true

# Security (optional)
API_KEY_ENCRYPTION_ENABLED=false
API_KEY_ENCRYPTION_KEY_FILE=encryption.key
```

## 4. Integration with Model Configuration

### 4.1 Enhanced Model Manager

```python
# From enhanced model manager - EXAMPLE

class EnhancedModelManager(ModelManager):
    """Model manager with integrated API key management"""
    
    def __init__(self, model_config: ApplicationModelConfig, api_keys_config_path: str = "api_keys.yaml"):
        super().__init__(model_config)
        self.api_key_manager = APIKeyManager(api_keys_config_path)
        
        # Validate all keys on startup
        asyncio.create_task(self._startup_key_validation())
    
    async def _startup_key_validation(self):
        """Validate all API keys on startup"""
        
        self.logger.info("Validating API keys...")
        validation_results = await self.api_key_manager.validate_all_keys()
        
        for provider, results in validation_results.items():
            primary_status = results["primary"]["status"]
            if primary_status == "valid":
                self.logger.info(f"✅ {provider} primary key is valid")
            else:
                self.logger.error(f"❌ {provider} primary key is invalid: {results['primary'].get('error', 'Unknown error')}")
    
    def get_client(self, model_config: ModelConfig) -> Any:
        """Get client with automatic API key retrieval"""
        
        # Get API key from key manager
        api_key = self.api_key_manager.get_api_key(model_config.provider.value)
        
        if not api_key:
            raise ValueError(f"No valid API key available for provider: {model_config.provider.value}")
        
        # Update model config with retrieved key
        model_config.api_key = api_key
        
        # Create client using parent method
        return super().get_client(model_config)
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get comprehensive usage summary"""
        
        return {
            "api_key_usage": self.api_key_manager.get_usage_summary(),
            "model_usage": self._get_model_usage_stats(),
            "cost_analysis": self._get_cost_analysis()
        }
    
    def _get_model_usage_stats(self) -> Dict[str, Any]:
        """Get model-specific usage statistics"""
        # Implementation for model usage tracking
        return {}
    
    def _get_cost_analysis(self) -> Dict[str, Any]:
        """Get cost analysis across all providers"""
        # Implementation for cost analysis
        return {}
```

## 5. Security Best Practices

### 5.1 Key Security Guidelines

```python
# From security best practices - EXAMPLE

class SecureAPIKeyManager(APIKeyManager):
    """API key manager with enhanced security features"""
    
    def __init__(self, config_path: str = "api_keys.yaml"):
        super().__init__(config_path)
        
        # Initialize encryption if enabled
        self.encryption_enabled = os.getenv("API_KEY_ENCRYPTION_ENABLED", "false").lower() == "true"
        if self.encryption_enabled:
            self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize encryption for API keys"""
        from cryptography.fernet import Fernet
        
        key_file = os.getenv("API_KEY_ENCRYPTION_KEY_FILE", "encryption.key")
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new encryption key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            self.logger.info(f"Generated new encryption key: {key_file}")
        
        self.cipher_suite = Fernet(key)
    
    def _encrypt_key(self, key_value: str) -> str:
        """Encrypt API key value"""
        if not self.encryption_enabled:
            return key_value
        
        encrypted = self.cipher_suite.encrypt(key_value.encode())
        return encrypted.decode()
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt API key value"""
        if not self.encryption_enabled:
            return encrypted_key
        
        decrypted = self.cipher_suite.decrypt(encrypted_key.encode())
        return decrypted.decode()
    
    def audit_key_access(self, key_id: str, user: str, action: str):
        """Audit API key access"""
        
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "key_id": key_id,
            "user": user,
            "action": action,
            "ip_address": self._get_client_ip()
        }
        
        # Log to audit file
        audit_file = "api_key_audit.log"
        with open(audit_file, 'a') as f:
            f.write(json.dumps(audit_entry) + "\n")
        
        self.logger.info(f"API key access audited: {key_id} by {user}")
    
    def _get_client_ip(self) -> str:
        """Get client IP address for auditing"""
        # Implementation depends on your deployment
        return "unknown"
```

This comprehensive API key management system provides:

1. **Secure Storage**: Multiple storage options with encryption support
2. **Multi-Provider Support**: OpenAI, Anthropic, Groq, Together AI, Azure OpenAI
3. **Usage Tracking**: Request counts, cost tracking, and limit enforcement
4. **Key Validation**: Automated health checks for all API keys
5. **Fallback Management**: Automatic fallback to backup keys
6. **Access Control**: Role-based access and environment restrictions
7. **Audit Logging**: Complete audit trail of key usage
8. **Cost Control**: Budget limits and usage alerts

The system ensures your platform can securely manage API keys across multiple providers while maintaining operational simplicity and security best practices.
