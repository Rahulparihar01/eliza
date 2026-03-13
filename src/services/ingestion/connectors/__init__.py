"""
Connector Registry and Factory

Central registry for all available connectors.
Factory methods for instantiating connectors by type.
"""
from typing import Dict, Any, List, Optional
from src.core.logging import get_logger, LogCategory

from .base import BaseConnector
from .people_data_labs import PeopleDataLabsConnector, PDLQuotaExceededError, PDLAuthenticationError
from .filesystem_connector import FileSystemConnector
from .hubspot import HubSpotConnector
from .fathom import FathomConnector
# Use the full-featured Greenhouse connector (greenhouse.py) with resume fetching,
# historical candidates, department hierarchy, and ATS integration
from .greenhouse import GreenhouseConnector

logger = get_logger(__name__, LogCategory.BUSINESS)


# Connector Registry
# Maps connector type strings to connector classes
CONNECTOR_REGISTRY: Dict[str, type] = {
    "people_data_labs": PeopleDataLabsConnector,
    "filesystem": FileSystemConnector,
    "greenhouse": GreenhouseConnector,
    "hubspot": HubSpotConnector,
    "fathom": FathomConnector,
    # Future connectors:
    # "lever": LeverConnector,
    # "workday": WorkdayConnector,
    # "bamboohr": BambooHRConnector,
    # "salesforce": SalesforceConnector,
    # "postgresql": PostgreSQLConnector,
    # "mysql": MySQLConnector,
    # "mongodb": MongoDBConnector,
    # "s3": S3Connector,
    # "hubspot": HubSpotConnector,
    # "zendesk": ZendeskConnector,
}


def get_connector_class(connector_type: str) -> type:
    """
    Get connector class by type identifier.
    
    Args:
        connector_type: Type identifier (e.g., "people_data_labs")
        
    Returns:
        Connector class (subclass of BaseConnector)
        
    Raises:
        ValueError: If connector type not found
        
    Example:
        connector_class = get_connector_class("people_data_labs")
        connector = connector_class(credentials, config, customer_id)
    """
    if connector_type not in CONNECTOR_REGISTRY:
        available = ", ".join(CONNECTOR_REGISTRY.keys())
        raise ValueError(
            f"Unknown connector type: '{connector_type}'. "
            f"Available connectors: {available}"
        )
    
    return CONNECTOR_REGISTRY[connector_type]


def create_connector(
    connector_type: str,
    credentials: Dict[str, str],
    config: Dict[str, Any],
    customer_id: str
) -> BaseConnector:
    """
    Factory method to instantiate a connector.
    
    Args:
        connector_type: Type identifier (e.g., "people_data_labs")
        credentials: Decrypted credentials for the connector
        config: Connector configuration (including query)
        customer_id: Customer ID for multi-tenant isolation
        
    Returns:
        Initialized connector instance
        
    Raises:
        ValueError: If connector type not found or validation fails
        
    Example:
        connector = create_connector(
            connector_type="people_data_labs",
            credentials={"api_key": "pdl_xxx"},
            config={"search_query": {...}, "max_records": 10000},
            customer_id="customer_123"
        )
        
        # Test connection
        result = connector.check()
        if result["status"] == "healthy":
            # Start syncing
            for batch in connector.read_stream("full", {}):
                process_batch(batch)
    """
    connector_class = get_connector_class(connector_type)
    
    try:
        connector = connector_class(
            credentials=credentials,
            config=config,
            customer_id=customer_id
        )
        
        logger.info(
            "connector_created",
            connector_type=connector_type,
            customer_id=customer_id
        )
        
        return connector
        
    except Exception as e:
        logger.error(
            "connector_creation_failed",
            connector_type=connector_type,
            customer_id=customer_id,
            error=str(e),
            exc_info=True
        )
        raise


def list_available_connectors() -> List[Dict[str, Any]]:
    """
    List all available connector types.
    
    Returns:
        List of connector metadata:
        [
            {
                "type": "people_data_labs",
                "name": "People Data Labs",
                "description": "Person data enrichment API",
                "category": "people_data"
            },
            ...
        ]
        
    Used by frontend to show available connector options.
    """
    connectors = []
    
    for connector_type, connector_class in CONNECTOR_REGISTRY.items():
        # Extract metadata from connector class
        metadata = {
            "type": connector_type,
            "name": _get_connector_display_name(connector_type),
            "description": _get_connector_description(connector_class),
            "category": _get_connector_category(connector_type),
            "requires_credentials": True,
            "supported_sync_modes": _get_supported_sync_modes(connector_class)
        }
        connectors.append(metadata)
    
    return connectors


def _get_connector_display_name(connector_type: str) -> str:
    """Convert connector type to display name."""
    # Simple title case conversion
    return " ".join(word.capitalize() for word in connector_type.split("_"))


def _get_connector_description(connector_class: type) -> str:
    """Extract description from connector class docstring."""
    if connector_class.__doc__:
        # Get first line of docstring
        lines = connector_class.__doc__.strip().split("\n")
        return lines[0] if lines else "No description available"
    return "No description available"


def _get_connector_category(connector_type: str) -> str:
    """
    Categorize connector for UI organization.
    
    Categories:
    - people_data: Person/contact data sources
    - hr_ats: HR/ATS platforms (Greenhouse, Lever, etc.)
    - crm: CRM systems (Salesforce, HubSpot)
    - database: Database connectors (PostgreSQL, MySQL)
    - cloud_storage: S3, GCS, Azure Blob
    - filesystem: Local filesystem
    - saas: SaaS applications
    """
    category_map = {
        "people_data_labs": "people_data",
        "greenhouse": "hr_ats",
        "lever": "hr_ats",
        "workday": "hr_ats",
        "bamboohr": "hr_ats",
        "filesystem": "filesystem",
        "salesforce": "crm",
        "hubspot": "crm",
        "fathom": "meeting_intelligence",
        "postgresql": "database",
        "mysql": "database",
        "mongodb": "database",
        "s3": "cloud_storage",
        "zendesk": "saas",
    }
    return category_map.get(connector_type, "other")


def _get_supported_sync_modes(connector_class: type) -> List[str]:
    """Get supported sync modes from connector class."""
    try:
        # Try to instantiate with dummy data to get sync modes
        # (Not ideal, but works for SimpleStreamConnector)
        if hasattr(connector_class, 'supported_sync_modes'):
            # It's a property, need instance
            return ["full", "incremental"]  # Default assumption
        return ["full", "incremental"]
    except:
        return ["full"]


def validate_connector_config(
    connector_type: str,
    config: Dict[str, Any]
) -> tuple[bool, str]:
    """
    Validate connector configuration without instantiating.
    
    Useful for pre-validation before saving configuration.
    
    Args:
        connector_type: Type identifier
        config: Configuration to validate
        
    Returns:
        (is_valid, error_message)
        
    Example:
        is_valid, error = validate_connector_config(
            "people_data_labs",
            {"search_query": {...}}
        )
        if not is_valid:
            return error_response(error)
    """
    try:
        connector_class = get_connector_class(connector_type)
        
        # Create temporary instance with dummy credentials
        temp_connector = connector_class(
            credentials={"api_key": "dummy"},
            config=config,
            customer_id="validation"
        )
        
        # Call validation method
        return temp_connector.validate_config()
        
    except Exception as e:
        return False, f"Configuration validation failed: {str(e)}"


# Export public API
__all__ = [
    "BaseConnector",
    "PeopleDataLabsConnector",
    "FileSystemConnector",
    "GreenhouseConnector",
    "HubSpotConnector",
    "FathomConnector",
    "CONNECTOR_REGISTRY",
    "get_connector_class",
    "create_connector",
    "list_available_connectors",
    "validate_connector_config",
]
