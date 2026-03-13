"""
Prompt Loader Utility - Helper for loading managed prompts into RAG flows.

This utility provides a simple interface for loading prompts from the
Prompt Management system into flows and services.

Usage:
    from src.utils.prompt_loader import get_managed_prompts, get_prompt
    
    # In a flow or service:
    prompts = get_managed_prompts(customer_id, domain)
    system_prompt = prompts.get('system', DEFAULT_SYSTEM_PROMPT)
    
    # Or get a single prompt:
    query_rewrite = get_prompt(customer_id, domain, 'query_rewrite')
"""

from typing import Optional, Dict
from functools import lru_cache
import time

from src.models import database
from src.core.logging import get_logger

logger = get_logger(__name__)

# Cache TTL in seconds (10 seconds - short for fast prompt updates)
PROMPT_CACHE_TTL = 10

# Default prompts to use when no managed prompt exists (fallbacks)
# These match the defaults in prompt_management_service.py
DEFAULT_PROMPTS = {
    "system": """You are an expert data analyst assistant. You help users understand 
and analyze data from their business systems. You provide clear, actionable insights 
based on the data available.""",
    
    "query_rewrite": """Analyze the user's question and rewrite it to be more specific 
and suitable for data retrieval. Focus on extracting the key data elements needed.""",
    
    "synthesis": """Based on the data retrieved, provide a clear and comprehensive 
answer to the user's question. Include relevant numbers, percentages, and comparisons 
where appropriate.""",
    
    "retrieval": """Search for relevant documents that can help answer the user's 
question. Focus on finding authoritative sources with specific data points.""",
}

# Domain-specific defaults
DOMAIN_DEFAULT_PROMPTS = {
    "fasb": {
        "system": """You are an assistant that answers questions about FASB Accounting Standards Codification (ASC).
Use ONLY the provided context. If the answer isn't in the context, say "I don't know."
When you state facts, cite sources like [1], [2] referring to the numbered context items.

FORMATTING RULES:
- Use **bold** for key terms and requirements (e.g., **no preference**, **consistently**)
- Use bullet points (- ) when listing multiple requirements or items
- Keep answers clear, structured, and authoritative
- Cite sources inline where relevant [1], [2], etc.""",
    },
    "insurance": {
        "system": """You are an expert insurance data analyst assistant.
You help users understand insurance data, policies, claims, and industry metrics.
Use the provided context and data to give accurate, helpful answers.
Always cite your sources when making factual claims.""",
    },
    "knowledge_base": {
        "system": """You are a retrieval-augmented assistant for a customer knowledge base.
Use ONLY the provided context. If the answer is not in the context, say you don't know.
When you state facts, cite sources like [1], [2] referring to the numbered context items.

FORMATTING RULES:
- Be concise, clear, and accurate
- Use bullet points (- ) for lists
- Avoid speculation or unstated assumptions
- Cite sources inline where relevant [1], [2], etc.""",
    },
}


class PromptCache:
    """Simple time-based cache for prompts."""
    
    def __init__(self, ttl: int = PROMPT_CACHE_TTL):
        self.ttl = ttl
        self._cache: Dict[str, tuple] = {}  # key -> (value, timestamp)
    
    def get(self, key: str) -> Optional[Dict[str, str]]:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Dict[str, str]) -> None:
        """Set cached value with current timestamp."""
        self._cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()


# Global cache instance
_prompt_cache = PromptCache()


def get_managed_prompts(
    customer_id: str,
    domain: str,
    use_cache: bool = True,
    fallback_to_defaults: bool = True,
) -> Dict[str, str]:
    """
    Get all active prompts for a domain.
    
    Args:
        customer_id: Customer ID
        domain: Domain identifier (e.g., 'fasb', 'insurance')
        use_cache: Whether to use cached prompts (default: True)
        fallback_to_defaults: Whether to use defaults if no managed prompt exists
    
    Returns:
        Dictionary of prompt_type -> content
    """
    cache_key = f"{customer_id}:{domain}"
    
    # Check cache
    if use_cache:
        cached = _prompt_cache.get(cache_key)
        if cached is not None:
            return cached
    
    # Load from database
    prompts = {}
    
    try:
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        try:
            from src.services.prompt_management_service import PromptManagementService
            service = PromptManagementService(db)
            prompts = service.get_rag_prompts(customer_id, domain)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to load managed prompts: {e}")
    
    # Merge with defaults if enabled
    if fallback_to_defaults:
        # Start with generic defaults
        result = {**DEFAULT_PROMPTS}
        # Override with domain-specific defaults
        if domain in DOMAIN_DEFAULT_PROMPTS:
            result.update(DOMAIN_DEFAULT_PROMPTS[domain])
        # Finally, override with managed prompts from DB
        result.update(prompts)
    else:
        result = prompts
    
    # Cache the result
    if use_cache:
        _prompt_cache.set(cache_key, result)
    
    return result


def get_prompt(
    customer_id: str,
    domain: str,
    prompt_type: str,
    default: Optional[str] = None,
) -> Optional[str]:
    """
    Get a single prompt by type.
    
    Args:
        customer_id: Customer ID
        domain: Domain identifier
        prompt_type: Type of prompt (e.g., 'system', 'query_rewrite')
        default: Default value if prompt not found
    
    Returns:
        Prompt content or default
    """
    prompts = get_managed_prompts(customer_id, domain)
    return prompts.get(prompt_type, default or DEFAULT_PROMPTS.get(prompt_type))


def clear_prompt_cache() -> None:
    """Clear the prompt cache. Call this after updating prompts."""
    _prompt_cache.clear()
    logger.info("Prompt cache cleared")


def refresh_prompts(customer_id: str, domain: str) -> Dict[str, str]:
    """Force refresh prompts from database (bypasses cache)."""
    return get_managed_prompts(customer_id, domain, use_cache=False)


# Decorator for flows to inject prompts
def with_managed_prompts(customer_id: str, domain: str):
    """
    Decorator to inject managed prompts into a flow or function.
    
    Usage:
        @with_managed_prompts(customer_id='eliza', domain='fasb')
        def my_flow(prompts: Dict[str, str], ...):
            system_prompt = prompts['system']
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            prompts = get_managed_prompts(customer_id, domain)
            return func(prompts, *args, **kwargs)
        return wrapper
    return decorator
