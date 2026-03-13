# Connector Development Guide

> **Purpose:** This skill ensures data source connectors are built correctly, following the Airbyte-compatible BaseConnector pattern with proper credential handling, error recovery, and multi-tenant isolation.

---

## Quick Reference

```python
# ✅ CORRECT Connector Pattern
from src.services.ingestion.connectors.base import BaseConnector
from src.models.connector import ConnectorConfiguration

class YourConnector(BaseConnector):
    """Connector for [Service Name] integration."""
    
    def __init__(
        self,
        config: ConnectorConfiguration = None,
        credentials: Dict = None,
        sync_config: Dict = None,
        customer_id: str = None
    ):
        # Support both initialization modes
        if config is not None:
            self.config = config
            self._credentials = None
            self._sync_config = config.sync_config
            self._customer_id = config.customer_id
        else:
            super().__init__(credentials or {}, sync_config or {}, customer_id or "")
            self.config = None
            self._credentials = credentials
            self._sync_config = sync_config
            self._customer_id = customer_id
        
        self.api_key = self._get_api_key()
        self.base_url = "https://api.yourservice.com/v1"
    
    # Required abstract methods
    async def check(self) -> bool: ...
    def discover(self) -> Dict[str, Any]: ...
    def read_stream(self, stream_name, sync_mode, ...) -> Iterator[Dict]: ...
    def validate_config(self) -> Dict[str, Any]: ...
```

---

## Overview

Connectors integrate external data sources into the Eliza Platform using an Airbyte-compatible `BaseConnector` pattern. Each connector handles authentication, stream discovery, paginated data fetching, and record transformation for a specific third-party service.

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend Layer                          │
│  CreateConnectionModal → ConnectionDetailPane               │
└─────────────────────────────────────────────────────────────┘
                              ↓ API Calls
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                              │
│  /api/connectors/types → /configurations → /test-connection │
└─────────────────────────────────────────────────────────────┘
                              ↓ Service Layer
┌─────────────────────────────────────────────────────────────┐
│                   Connector Service                         │
│  ConnectorService → YourConnector (BaseConnector)          │
└─────────────────────────────────────────────────────────────┘
                              ↓ External API
┌─────────────────────────────────────────────────────────────┐
│                    External Service                         │
│  Third-party API (Greenhouse, Lever, PDL, etc.)            │
└─────────────────────────────────────────────────────────────┘
```

---

## Critical Rules

### Rule 1: Support Both Initialization Modes

**Context:** Connectors must work with both database configurations (production) AND direct parameters (for testing). Only supporting one mode makes the connector untestable or unusable in production.

```python
# ❌ WRONG: Only supporting direct parameters
def __init__(self, credentials: Dict, sync_config: Dict, customer_id: str):
    super().__init__(credentials, sync_config, customer_id)
    self.api_key = credentials.get("api_key")

# ✅ CORRECT: Supporting both initialization modes
def __init__(
    self,
    config: ConnectorConfiguration = None,  # From database
    credentials: Dict = None,               # Direct for testing
    sync_config: Dict = None,               # Direct for testing
    customer_id: str = None                 # Direct for testing
):
    if config is not None:
        # Database configuration mode
        self.config = config
        self._credentials = None
        self._sync_config = config.sync_config
        self._customer_id = config.customer_id
    else:
        # Direct parameter mode (testing)
        super().__init__(credentials or {}, sync_config or {}, customer_id or "")
        self.config = None
        self._credentials = credentials
        self._sync_config = sync_config
        self._customer_id = customer_id
```

### Rule 2: Implement Proper Credential Extraction

**Context:** Credentials come from different sources depending on context: temporary credentials during API test-connection calls, stored config credentials in production, or direct dict credentials during unit testing. Missing any path causes auth failures.

```python
# ❌ WRONG: Only checking one credential source
def _get_api_key(self) -> str:
    return self.config.credentials.get("api_key")  # Fails during testing!

# ✅ CORRECT: Fallback logic across all credential sources
def _get_api_key(self) -> str:
    """Extract API key with fallback logic for testing."""
    # 1. Check for temporary credentials (API testing)
    if self.config and hasattr(self.config, '_temp_credentials') and self.config._temp_credentials:
        api_key = self.config._temp_credentials.get("api_key")
        if api_key:
            return api_key
    
    # 2. Regular credential retrieval
    if self.config:
        api_key = self.config.credentials.get("api_key")
    else:
        api_key = self._credentials.get("api_key") if self._credentials else None
    
    if not api_key:
        raise ValueError("API key is required for [Service Name]")
    
    return api_key
```

### Rule 3: Implement All Abstract Methods

**Context:** `BaseConnector` defines four abstract methods. Missing any will raise `TypeError` at instantiation. Each method serves a distinct purpose in the connector lifecycle.

```python
# ❌ WRONG: Missing abstract methods
class YourConnector(BaseConnector):
    def check(self) -> Dict[str, Any]: ...
    # Missing discover(), read_stream(), validate_config() → TypeError!

# ✅ CORRECT: All abstract methods implemented
class BaseConnector(ABC):
    @abstractmethod
    def check(self) -> Dict[str, Any]:
        """Test connection - returns status dict."""
        pass
    
    @abstractmethod
    def discover(self) -> Dict[str, Any]:
        """Return available streams and schemas."""
        pass
    
    @abstractmethod
    def read_stream(self, sync_mode: str, sync_params: Dict) -> Iterator[List[Dict]]:
        """Yield batches of records."""
        pass
    
    @abstractmethod
    def validate_config(self) -> Tuple[bool, str]:
        """Validate configuration before saving."""
        pass
```

---

## Complete Template

```python
"""
[Service Name] Connector

Integrates with [Service Name] to sync [data types].
API Documentation: [link to docs]
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Iterator, Tuple
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from src.services.ingestion.connectors.base import BaseConnector
from src.models.connector import ConnectorConfiguration
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class YourConnector(BaseConnector):
    """
    Connector for [Service Name] integration.
    
    Configuration:
        credentials:
            - api_key: API key for authentication (required)
            - api_secret: API secret if needed (optional)
        
        sync_config:
            - option1: Description (default: "value")
            - max_records: Maximum records to fetch (default: 1000)
    
    Streams:
        - primary_stream: Main data stream (candidates, jobs, etc.)
    """
    
    # ================================================================
    # Initialization
    # ================================================================
    
    def __init__(
        self,
        config: ConnectorConfiguration = None,
        credentials: Dict = None,
        sync_config: Dict = None,
        customer_id: str = None
    ):
        """
        Initialize the connector.
        
        Supports two modes:
        1. With ConnectorConfiguration (from database)
        2. With individual parameters (for testing)
        """
        if config is not None:
            self.config = config
            self._credentials = None
            self._sync_config = config.sync_config or {}
            self._customer_id = config.customer_id
        else:
            super().__init__(credentials or {}, sync_config or {}, customer_id or "")
            self.config = None
            self._credentials = credentials or {}
            self._sync_config = sync_config or {}
            self._customer_id = customer_id or ""
        
        # Extract credentials
        self.api_key = self._get_api_key()
        
        # API configuration
        self.base_url = "https://api.yourservice.com/v1"
        self.timeout = aiohttp.ClientTimeout(total=30)
        
        # Parse sync config with defaults
        self.max_records = self._sync_config.get("max_records", 1000)
        self.option1 = self._sync_config.get("option1", "default_value")
        
        logger.info(
            "connector_initialized",
            connector_type="your_connector",
            customer_id=self._customer_id,
            max_records=self.max_records
        )
    
    def _get_api_key(self) -> str:
        """Extract API key from credentials with fallback logic."""
        # For API testing with temporary credentials
        if self.config and hasattr(self.config, '_temp_credentials') and self.config._temp_credentials:
            api_key = self.config._temp_credentials.get("api_key")
            if api_key:
                return api_key
        
        # Regular credential retrieval
        if self.config:
            api_key = self.config.credentials.get("api_key")
        else:
            api_key = self._credentials.get("api_key")
        
        if not api_key:
            raise ValueError("API key is required for [Service Name]")
        
        return api_key
    
    # ================================================================
    # HTTP Client
    # ================================================================
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json_data: Request body
        
        Returns:
            Response JSON as dictionary
        
        Raises:
            ValueError: On API errors (4xx, 5xx)
            aiohttp.ClientError: On network errors
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",  # Adjust auth format
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        logger.debug(
            "api_request",
            method=method,
            endpoint=endpoint,
            params=params
        )
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            ) as response:
                response_text = await response.text()
                
                if response.status == 401:
                    raise ValueError("Invalid API key or authentication failed")
                
                if response.status == 403:
                    raise ValueError("Access forbidden - check API permissions")
                
                if response.status == 429:
                    # Rate limited - will be retried by tenacity
                    raise ValueError("Rate limit exceeded - retrying")
                
                if response.status >= 400:
                    logger.error(
                        "api_error",
                        status=response.status,
                        response=response_text[:500]
                    )
                    raise ValueError(f"API error {response.status}: {response_text[:200]}")
                
                return await response.json()
    
    # ================================================================
    # Required Abstract Methods
    # ================================================================
    
    async def check(self) -> bool:
        """
        Test connectivity to the service.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Make a lightweight API call to verify credentials
            await self._make_request("GET", "me")  # Or appropriate health endpoint
            logger.info(
                "connection_check_success",
                connector_type="your_connector",
                customer_id=self._customer_id
            )
            return True
        except Exception as e:
            logger.error(
                "connection_check_failed",
                connector_type="your_connector",
                error=str(e)
            )
            return False
    
    def discover(self) -> Dict[str, Any]:
        """
        Discover available streams and their schemas.
        
        Returns Airbyte-compatible catalog format.
        """
        return {
            "streams": [
                {
                    "name": "primary_stream",  # e.g., "candidates", "jobs"
                    "supported_sync_modes": ["full_refresh", "incremental"],
                    "source_defined_primary_key": [["id"]],
                    "json_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "external_id": {"type": "string"},
                            "name": {"type": "string"},
                            "email": {"type": ["string", "null"]},
                            "status": {"type": "string"},
                            "created_at": {"type": "string", "format": "date-time"},
                            "updated_at": {"type": ["string", "null"], "format": "date-time"},
                            # Add all fields your stream returns
                            "metadata": {"type": ["object", "null"]}
                        },
                        "required": ["id", "name"]
                    }
                }
            ]
        }
    
    def read_stream(
        self,
        stream_name: str,
        sync_mode: str,
        cursor_field: Optional[str] = None,
        stream_state: Optional[Dict[str, Any]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Read records from a stream.
        
        This method must be synchronous (BaseConnector requirement).
        Uses asyncio.run() for async operations.
        
        Args:
            stream_name: Name of stream to read
            sync_mode: "full_refresh" or "incremental"
            cursor_field: Field for incremental sync
            stream_state: Previous state for incremental
        
        Yields:
            Individual records as dictionaries
        """
        if stream_name != "primary_stream":
            raise ValueError(f"Unknown stream: {stream_name}")
        
        logger.info(
            "read_stream_start",
            stream_name=stream_name,
            sync_mode=sync_mode,
            max_records=self.max_records
        )
        
        # Run async sync in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                self._fetch_all_records(sync_mode, stream_state)
            )
            
            for record in results:
                yield record
                
        finally:
            loop.close()
        
        logger.info(
            "read_stream_complete",
            stream_name=stream_name,
            records_count=len(results) if 'results' in locals() else 0
        )
    
    def validate_config(self) -> Dict[str, Any]:
        """
        Validate connector configuration.
        
        Returns:
            Dict with status, message, and errors list
        """
        errors = []
        
        # Validate required credentials
        if not self.api_key:
            errors.append("API key is required")
        
        # Validate sync config
        if self.max_records < 1:
            errors.append("max_records must be at least 1")
        
        if self.max_records > 100000:
            errors.append("max_records cannot exceed 100,000")
        
        # Return validation result
        if errors:
            return {
                "status": "invalid",
                "message": "; ".join(errors),
                "errors": errors
            }
        
        return {
            "status": "valid",
            "message": "Configuration is valid",
            "errors": []
        }
    
    # ================================================================
    # Data Fetching
    # ================================================================
    
    async def _fetch_all_records(
        self,
        sync_mode: str,
        stream_state: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all records with pagination.
        
        Args:
            sync_mode: "full_refresh" or "incremental"
            stream_state: Previous state for incremental sync
        
        Returns:
            List of all records
        """
        all_records = []
        page = 1
        per_page = 100  # API page size
        
        # For incremental sync, get cursor from state
        cursor_value = None
        if sync_mode == "incremental" and stream_state:
            cursor_value = stream_state.get("cursor_value")
        
        while len(all_records) < self.max_records:
            # Build request params
            params = {
                "page": page,
                "per_page": per_page
            }
            
            if cursor_value:
                params["updated_since"] = cursor_value
            
            # Fetch page
            response = await self._make_request("GET", "items", params=params)
            items = response.get("items", response.get("data", []))
            
            if not items:
                break
            
            # Transform records
            for item in items:
                record = self._transform_record(item)
                all_records.append(record)
                
                if len(all_records) >= self.max_records:
                    break
            
            # Check if more pages
            total_pages = response.get("total_pages", 1)
            if page >= total_pages:
                break
            
            page += 1
            
            # Rate limiting courtesy delay
            await asyncio.sleep(0.2)
        
        logger.info(
            "fetch_complete",
            total_records=len(all_records),
            pages_fetched=page
        )
        
        return all_records
    
    def _transform_record(self, raw_item: Dict) -> Dict[str, Any]:
        """
        Transform API response to standard record format.
        
        Args:
            raw_item: Raw API response item
        
        Returns:
            Transformed record matching schema
        """
        return {
            "id": raw_item["id"],
            "external_id": str(raw_item["id"]),
            "name": raw_item.get("name") or raw_item.get("title", ""),
            "email": raw_item.get("email"),
            "status": raw_item.get("status", "active"),
            "created_at": raw_item.get("created_at"),
            "updated_at": raw_item.get("updated_at"),
            "metadata": {
                "source": "your_connector",
                "raw_id": raw_item["id"]
            }
        }
    
    # ================================================================
    # Optional: Custom Methods
    # ================================================================
    
    async def sync(self) -> Dict[str, Any]:
        """
        Full sync method (alternative to read_stream for simple use cases).
        
        Returns:
            Dict with records, metadata, and stats
        """
        logger.info(
            "sync_start",
            connector_type="your_connector",
            customer_id=self._customer_id
        )
        
        try:
            records = await self._fetch_all_records("full_refresh", None)
            
            return {
                "records": records,
                "metadata": {
                    "connector_type": "your_connector",
                    "customer_id": self._customer_id,
                    "sync_mode": "full_refresh"
                },
                "stats": {
                    "total_fetched": len(records),
                    "max_records_config": self.max_records
                }
            }
            
        except Exception as e:
            logger.error(
                "sync_failed",
                connector_type="your_connector",
                error=str(e),
                exc_info=True
            )
            raise
```

---

## Integration

### Step 1: Add Enum Value

```python
# src/models/connector.py
class ConnectorType(str, Enum):
    PEOPLE_DATA_LABS = "people_data_labs"
    GREENHOUSE = "greenhouse"
    YOUR_CONNECTOR = "your_connector"  # ← Add this
```

### Step 2: Register in Available Types

```python
# src/api/routes/connectors.py
@router.get("/types")
async def get_available_connector_types():
    return {
        "connector_types": [
            ConnectorTypeInfo(
                type=ConnectorType.YOUR_CONNECTOR,
                name="Your Service Name",
                description="Sync data from Your Service",
                category="hr_data",
                requires_credentials=True,
                supported_sync_modes=[SyncMode.FULL_REFRESH, SyncMode.INCREMENTAL],
                available=True
            ),
            # ... other connectors
        ]
    }
```

### Step 3: Add Frontend Form Fields

```typescript
// frontend/src/components/data-connections/CreateConnectionModal.tsx
{formData.connector_type === ConnectorType.YOUR_CONNECTOR && (
  <>
    <div>
      <label className="block text-sm font-medium text-text mb-2">
        API Key <span className="text-error">*</span>
      </label>
      <input
        type="password"
        value={formData.api_key}
        onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
        placeholder="Enter your API key"
        className="input-field"
        required
      />
      <p className="mt-1 text-xs text-muted">
        Get your API key from [Service Name]: Settings → API Keys
      </p>
    </div>
    
    <div>
      <label className="block text-sm font-medium text-text mb-2">
        Max Records
      </label>
      <input
        type="number"
        min="1"
        max="100000"
        value={formData.sync_config?.max_records || 1000}
        onChange={(e) =>
          setFormData({
            ...formData,
            sync_config: { 
              ...formData.sync_config, 
              max_records: parseInt(e.target.value) || 1000 
            },
          })
        }
        className="input-field"
      />
    </div>
  </>
)}
```

---

## Testing

### Unit Tests

```python
# tests/test_your_connector.py
import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.services.ingestion.connectors.your_connector import YourConnector


@pytest.fixture
def connector():
    """Create connector with test credentials."""
    return YourConnector(
        credentials={"api_key": "test_key"},
        sync_config={"max_records": 10},
        customer_id="test_customer"
    )


class TestYourConnector:
    
    def test_init_with_credentials(self, connector):
        """Test initialization with direct credentials."""
        assert connector.api_key == "test_key"
        assert connector.max_records == 10
        assert connector._customer_id == "test_customer"
    
    def test_validate_config_valid(self, connector):
        """Test config validation with valid settings."""
        result = connector.validate_config()
        assert result["status"] == "valid"
    
    def test_validate_config_missing_key(self):
        """Test config validation without API key."""
        with pytest.raises(ValueError, match="API key is required"):
            YourConnector(
                credentials={},  # No API key
                sync_config={},
                customer_id="test"
            )
    
    def test_discover(self, connector):
        """Test stream discovery."""
        catalog = connector.discover()
        
        assert "streams" in catalog
        assert len(catalog["streams"]) > 0
        assert catalog["streams"][0]["name"] == "primary_stream"
    
    @pytest.mark.asyncio
    async def test_check_success(self, connector):
        """Test successful connection check."""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "ok"}
            
            result = await connector.check()
            
            assert result is True
            mock.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_failure(self, connector):
        """Test failed connection check."""
        with patch.object(connector, '_make_request', new_callable=AsyncMock) as mock:
            mock.side_effect = ValueError("Invalid API key")
            
            result = await connector.check()
            
            assert result is False
```

---

## Checklist

- [ ] Connector class implements all abstract methods
- [ ] Both initialization modes supported (config vs direct params)
- [ ] Credential extraction handles temp credentials for testing
- [ ] Error handling with meaningful messages
- [ ] Rate limiting respected (delays between requests)
- [ ] Retry logic for transient failures
- [ ] Logging at key operations
- [ ] Enum added to ConnectorType
- [ ] Registered in /types endpoint
- [ ] Frontend form fields added
- [ ] Unit tests written
- [ ] Container rebuilt: `docker-compose build app`

---

## References

- `docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md` — Comprehensive connector development instructions including frontend integration
- `src/services/ingestion/connectors/base.py` — BaseConnector abstract class
- `src/models/connector.py` — ConnectorType enum and ConnectorConfiguration model
- `src/api/routes/connectors.py` — Connector API endpoints
- `frontend/src/components/data-connections/CreateConnectionModal.tsx` — Frontend connection form
