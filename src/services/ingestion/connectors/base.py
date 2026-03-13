"""
Base Connector Interface

Abstract base class that all data connectors must implement.
Follows Airbyte CDK patterns but simplified for embedded use.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator, List, Tuple, Optional
from enum import Enum

from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class SyncMode(str, Enum):
    """Sync mode for connector operations."""
    FULL_REFRESH = "full"
    INCREMENTAL = "incremental"


class ConnectorStatus(str, Enum):
    """Health status for connector checks."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class BaseConnector(ABC):
    """
    Abstract base class for all data connectors.
    
    Connectors implement the extract phase of ELT:
    1. check() - Test connection and credentials
    2. discover() - Get available streams and schemas
    3. read_stream() - Extract records with pagination
    4. validate_config() - Validate configuration before saving
    
    Each connector instance represents one configured connection.
    Multiple instances of same connector type can exist with different queries.
    
    Example:
        class PeopleDataLabsConnector(BaseConnector):
            def check(self):
                # Test PDL API key
                ...
            
            def discover(self):
                # Return person_search stream schema
                ...
            
            def read_stream(self, sync_mode, sync_params):
                # Yield batches of person records
                ...
    """
    
    def __init__(
        self,
        credentials: Dict[str, str],
        config: Dict[str, Any],
        customer_id: str
    ):
        """
        Initialize connector.
        
        Args:
            credentials: Decrypted credentials (e.g., {"api_key": "..."})
            config: Connector configuration including query (e.g., {"search_query": {...}, "max_records": 10000})
            customer_id: Customer ID for multi-tenant isolation
        """
        self.credentials = credentials
        self.config = config
        self.customer_id = customer_id
        
        logger.info(
            "connector_initialized",
            connector_type=self.__class__.__name__,
            customer_id=customer_id,
            config_keys=list(config.keys())
        )
    
    @abstractmethod
    def check(self) -> Dict[str, Any]:
        """
        Test connection and credentials.
        
        Called:
        - During connector configuration (to validate setup)
        - Periodically for health monitoring
        - Before starting a sync (optional check)
        
        Returns:
            {
                "status": "healthy" | "unhealthy" | "degraded",
                "message": str (human-readable status),
                "metadata": dict (additional info like rate limits, API version, etc.)
            }
            
        Example:
            {
                "status": "healthy",
                "message": "Connected to PDL API successfully",
                "metadata": {
                    "rate_limit": 60,
                    "plan_tier": "professional",
                    "api_version": "v5"
                }
            }
        """
        pass
    
    @abstractmethod
    def discover(self) -> Dict[str, Any]:
        """
        Discover available streams (tables, endpoints, resources).
        
        Returns information about what data this connector can provide.
        Used for schema discovery and optional AI mapping.
        
        Returns:
            {
                "streams": [
                    {
                        "name": str (stream identifier),
                        "supported_sync_modes": ["full", "incremental"],
                        "json_schema": dict (JSON schema of records),
                        "description": str (optional)
                    }
                ]
            }
            
        Example:
            {
                "streams": [
                    {
                        "name": "person_search",
                        "supported_sync_modes": ["full", "incremental"],
                        "json_schema": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "full_name": {"type": "string"},
                                "job_title": {"type": "string"},
                                ...
                            }
                        }
                    }
                ]
            }
        """
        pass
    
    @abstractmethod
    def read_stream(
        self,
        sync_mode: str,
        sync_params: Dict[str, Any]
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Stream records from the connector.
        
        Yields batches of records. Handles pagination internally.
        Must respect rate limits (use RateLimiter).
        
        Args:
            sync_mode: "full" or "incremental"
            sync_params: Parameters for this sync:
                - checkpoint: dict (for incremental sync - where we left off)
                - max_records: int (optional limit)
                - ... connector-specific params
        
        Yields:
            List[Dict[str, Any]]: Batches of records
            
        Example:
            def read_stream(self, sync_mode, sync_params):
                offset = sync_params.get("checkpoint", {}).get("offset", 0)
                max_records = sync_params.get("max_records", 10000)
                
                records_fetched = 0
                while records_fetched < max_records:
                    batch = self._fetch_page(offset)
                    if not batch:
                        break
                    
                    yield batch
                    records_fetched += len(batch)
                    offset += len(batch)
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> Tuple[bool, str]:
        """
        Validate connector configuration.
        
        Called before saving a connector to catch errors early.
        Checks query syntax, required fields, etc.
        
        Returns:
            (is_valid, error_message)
            
        Example:
            def validate_config(self):
                query = self.config.get("search_query")
                if not query:
                    return False, "search_query is required"
                
                if "job_title_role" not in query and "job_company_name" not in query:
                    return False, "Must specify at least one search criterion"
                
                return True, ""
        """
        pass
    
    # Optional methods (have default implementations)
    
    def estimate_record_count(self, query_params: Dict[str, Any]) -> Optional[int]:
        """
        Estimate number of records for a query.
        
        Used during connector configuration to show cost estimates.
        Not all connectors support this (return None if not supported).
        
        Args:
            query_params: Query to estimate
            
        Returns:
            Estimated record count, or None if not supported
            
        Example:
            def estimate_record_count(self, query_params):
                # Make API call with size=0 to get total count
                response = self.api.search(query=query_params, size=0)
                return response.get("total", 0)
        """
        logger.warning(
            "estimate_not_supported",
            connector_type=self.__class__.__name__
        )
        return None
    
    def get_checkpoint(self, sync_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract checkpoint from previous sync state.
        
        For incremental syncs - determines where to resume.
        
        Args:
            sync_state: State from previous sync
            
        Returns:
            Checkpoint dict for read_stream()
            
        Default implementation:
            Returns sync_state.get("checkpoint", {})
        """
        return sync_state.get("checkpoint", {})
    
    def create_checkpoint(
        self,
        records_synced: int,
        last_record: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create checkpoint for next incremental sync.
        
        Args:
            records_synced: Total records synced so far
            last_record: Last record processed (for cursor-based pagination)
            
        Returns:
            Checkpoint dict to save in ConnectorSyncRun
            
        Default implementation:
            Returns {"offset": records_synced}
        """
        return {"offset": records_synced}
    
    def get_stream_names(self) -> List[str]:
        """
        Get list of available stream names.
        
        Convenience method that calls discover() and extracts names.
        
        Returns:
            List of stream names
        """
        try:
            discovery = self.discover()
            return [stream["name"] for stream in discovery.get("streams", [])]
        except Exception as e:
            logger.error(f"Failed to get stream names: {e}", exc_info=True)
            return []
    
    def __repr__(self):
        """String representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"customer_id='{self.customer_id}', "
            f"config_keys={list(self.config.keys())})"
        )


class SimpleStreamConnector(BaseConnector):
    """
    Simplified base class for connectors with a single stream.
    
    Most connectors only have one stream (e.g., PDL person_search).
    This class provides default discover() implementation.
    
    Subclasses only need to implement:
    - check()
    - read_stream()
    - validate_config()
    - get_stream_schema() (instead of discover())
    """
    
    @property
    @abstractmethod
    def stream_name(self) -> str:
        """Name of the single stream this connector provides."""
        pass
    
    @property
    @abstractmethod
    def supported_sync_modes(self) -> List[str]:
        """Sync modes supported by this connector."""
        pass
    
    @abstractmethod
    def get_stream_schema(self) -> Dict[str, Any]:
        """
        Return JSON schema for this stream's records.
        
        Returns:
            JSON schema dict
        """
        pass
    
    def discover(self) -> Dict[str, Any]:
        """
        Default implementation for single-stream connectors.
        
        Returns discovery info for the one stream.
        """
        return {
            "streams": [
                {
                    "name": self.stream_name,
                    "supported_sync_modes": self.supported_sync_modes,
                    "json_schema": self.get_stream_schema()
                }
            ]
        }

