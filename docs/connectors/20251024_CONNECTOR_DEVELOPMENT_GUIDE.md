# Connector Development Guide

## Overview

This guide provides step-by-step instructions for adding new data source connectors to the Eliza Platform. Our connector framework is designed to make integration straightforward and consistent.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Implementation](#step-by-step-implementation)
4. [Testing Your Connector](#testing-your-connector)
5. [Deployment Checklist](#deployment-checklist)
6. [Examples](#examples)

---

## Architecture Overview

### Connector Framework Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend Layer                          │
│  - CreateConnectionModal: UI for connector setup            │
│  - ConnectionDetailPane: Display connector details          │
│  - DataSourceSelector: Select connector in workflows        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                              │
│  - /api/connectors/types: List available connector types   │
│  - /api/connectors/configurations: CRUD operations         │
│  - /api/connectors/test-connection: Test connectivity      │
│  - /api/connectors/{type}/...: Type-specific endpoints     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   Connector Service Layer                   │
│  - ConnectorService: Configuration management               │
│  - BaseConnector: Abstract base class (Airbyte-style)      │
│  - {Type}Connector: Concrete implementation                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    External API                             │
│  - Third-party service (Greenhouse, Lever, etc.)           │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Airbyte-Compatible**: Our connectors follow the Airbyte specification for easy migration
2. **Stream-Based**: Data flows through generators/iterators for memory efficiency
3. **Type-Safe**: Pydantic models for validation and API schemas
4. **Testable**: Clear separation of concerns, easy to unit test
5. **Observable**: Built-in telemetry and error tracking

---

## Prerequisites

### What You'll Need

1. **API Documentation**: Complete documentation for the target service's API
2. **Test Credentials**: API keys or OAuth tokens for testing
3. **Understanding of Data Model**: What entities you'll be syncing (candidates, jobs, etc.)
4. **Python Knowledge**: Familiarity with async/await, type hints, and Pydantic

### Required Files to Modify

- Backend (Python):
  - `src/models/connector.py` - Add connector type enum
  - `src/services/ingestion/connectors/{name}.py` - Connector implementation
  - `src/api/routes/connectors.py` - API endpoints
  - `alembic/versions/` - Database migration (if needed)

- Frontend (TypeScript):
  - `frontend/src/components/data-connections/CreateConnectionModal.tsx` - Setup UI
  - `frontend/src/components/ml-talent/DataSourceSelector.tsx` - Display in workflows

---

## Step-by-Step Implementation

### Step 1: Add Connector Type Enum

**File**: `src/models/connector.py`

```python
class ConnectorType(str, Enum):
    PEOPLE_DATA_LABS = "people_data_labs"
    FILESYSTEM = "filesystem"
    GREENHOUSE = "greenhouse"
    YOUR_CONNECTOR = "your_connector"  # ← Add this line
    # ... existing types
```

### Step 2: Create Connector Implementation

**File**: `src/services/ingestion/connectors/your_connector.py`

```python
"""
Your Connector Integration

This connector integrates with [Service Name] to sync [data types].
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Iterator
import aiohttp

from src.services.ingestion.connectors.base import BaseConnector
from src.models.connector import ConnectorConfiguration

logger = logging.getLogger(__name__)


class YourConnector(BaseConnector):
    """
    Connector for [Service Name] integration.
    
    Configuration:
        credentials:
            - api_key: API key for authentication
            - (optional) api_secret: API secret if needed
        
        sync_config:
            - option1: Description of option1
            - option2: Description of option2
    """
    
    def __init__(
        self,
        config: ConnectorConfiguration = None,
        credentials: Dict = None,
        sync_config: Dict = None,
        customer_id: str = None
    ):
        """
        Initialize the connector.
        
        Supports two initialization modes:
        1. With ConnectorConfiguration object (from database)
        2. With individual parameters (for testing)
        """
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
        
        # Parse sync config options
        self.option1 = self._sync_config.get("option1", "default_value")
        self.option2 = self._sync_config.get("option2", 100)
    
    def _get_api_key(self) -> str:
        """Extract API key from credentials with fallback logic."""
        # For API testing, check for temporary credentials first
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
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated HTTP request to API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json: Request body (for POST/PUT)
        
        Returns:
            Response JSON as dictionary
        
        Raises:
            aiohttp.ClientError: On network errors
            ValueError: On API errors
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Basic {self.api_key}",  # Adjust auth method as needed
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json
            ) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise ValueError(
                        f"API error {response.status}: {error_text}"
                    )
                
                return await response.json()
    
    # ============================================================
    # REQUIRED ABSTRACT METHODS FROM BaseConnector
    # ============================================================
    
    async def check(self) -> bool:
        """
        Test connectivity to the service.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Make a simple API call to verify credentials
            await self._make_request("GET", "health")  # Adjust endpoint
            logger.info("[YourConnector] Connection test successful")
            return True
        except Exception as e:
            logger.error(f"[YourConnector] Connection test failed: {e}")
            return False
    
    def discover(self) -> Dict[str, Any]:
        """
        Discover available data streams and their schemas.
        
        Returns Airbyte-style catalog with stream definitions.
        """
        return {
            "streams": [
                {
                    "name": "primary_stream",  # e.g., "candidates", "jobs", etc.
                    "json_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "created_at": {"type": "string", "format": "date-time"},
                            # Add all fields your stream returns
                        }
                    },
                    "supported_sync_modes": ["full_refresh", "incremental"]
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
        Read records from a specific stream.
        
        This method must be synchronous (not async) and yield records one at a time.
        
        Args:
            stream_name: Name of the stream to read
            sync_mode: "full_refresh" or "incremental"
            cursor_field: Field to use for incremental sync
            stream_state: Previous state for incremental sync
        
        Yields:
            Individual records as dictionaries
        """
        if stream_name != "primary_stream":
            raise ValueError(f"Unknown stream: {stream_name}")
        
        # Run async sync method in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(self.sync())
            for record in results.get("records", []):
                yield record
        finally:
            loop.close()
    
    def validate_config(self) -> Dict[str, Any]:
        """
        Validate connector configuration.
        
        Returns:
            Dictionary with validation results
        """
        errors = []
        
        if not self.api_key:
            errors.append("API key is required")
        
        if self.option2 < 1 or self.option2 > 1000:
            errors.append("option2 must be between 1 and 1000")
        
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
    
    # ============================================================
    # CUSTOM SYNC METHOD (Your main logic)
    # ============================================================
    
    async def sync(self) -> Dict[str, Any]:
        """
        Main sync method to fetch data from the service.
        
        Returns:
            Dictionary with sync results, typically:
            {
                "records": [...],
                "metadata": {...},
                "stats": {...}
            }
        """
        logger.info(f"[YourConnector] Starting sync for customer {self._customer_id}")
        
        try:
            # Fetch data from API
            response = await self._make_request(
                "GET",
                "your-endpoint",
                params={"option1": self.option1, "limit": self.option2}
            )
            
            records = []
            for item in response.get("items", []):
                # Transform API response to your internal format
                record = {
                    "id": item["id"],
                    "name": item["name"],
                    "email": item["email"],
                    "created_at": item["created_at"],
                    # Map all relevant fields
                }
                records.append(record)
            
            logger.info(f"[YourConnector] Synced {len(records)} records")
            
            return {
                "records": records,
                "metadata": {
                    "connector_type": "your_connector",
                    "sync_timestamp": asyncio.get_event_loop().time()
                },
                "stats": {
                    "total_fetched": len(records)
                }
            }
        
        except Exception as e:
            logger.error(f"[YourConnector] Sync failed: {e}", exc_info=True)
            raise
```

**Key Points**:
- Inherit from `BaseConnector`
- Implement all abstract methods: `check`, `discover`, `read_stream`, `validate_config`
- Support both initialization modes (with `ConnectorConfiguration` or individual params)
- Use `_get_api_key()` pattern for credential extraction with test override support

### Step 3: Add API Endpoint to Connector Types

**File**: `src/api/routes/connectors.py`

Find the `get_available_connector_types` function and add your connector:

```python
@router.get("/types", response_model=AvailableConnectorTypesResponse)
async def get_available_connector_types(
    current_user: User = Depends(require_permission(["system:admin"]))
):
    """Get all available connector types with their metadata."""
    from src.api.schemas.connector_schemas import ConnectorTypeInfo
    from src.models.connector import ConnectorType, SyncMode
    
    connector_types_info = [
        # ... existing connectors ...
        
        ConnectorTypeInfo(
            type=ConnectorType.YOUR_CONNECTOR,
            name="Your Service Name",
            description="Sync data from Your Service",
            category="hr_data",  # or "people_data", "crm", etc.
            requires_credentials=True,
            supported_sync_modes=[SyncMode.FULL_REFRESH, SyncMode.INCREMENTAL],
            available=True  # Set to False if not ready for production
        ),
    ]
    
    return AvailableConnectorTypesResponse(connector_types=connector_types_info)
```

### Step 4: Add Connector-Specific API Routes (Optional)

If your connector needs special endpoints (like Greenhouse's `/greenhouse/jobs`):

**File**: `src/api/routes/connectors.py`

```python
@router.get(
    "/your-connector/special-endpoint",
    response_model=YourResponseModel,
    dependencies=[Depends(require_permission("connectors:read"))]
)
async def your_connector_special_endpoint(
    api_key: str = Query(..., description="API key for testing"),
    current_user = Depends(get_current_user)
):
    """
    Special endpoint specific to your connector.
    """
    from src.services.ingestion.connectors.your_connector import YourConnector
    
    try:
        connector = YourConnector(
            credentials={"api_key": api_key},
            sync_config={},
            customer_id=current_user.customer_id
        )
        
        # Do something special
        result = await connector.some_special_method()
        
        return YourResponseModel(**result)
    
    except Exception as e:
        logger.error(f"Special endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Step 5: Update Frontend - Create Connection Modal

**File**: `frontend/src/components/data-connections/CreateConnectionModal.tsx`

Add connector-specific form fields:

```typescript
// Inside the form, after existing connector sections:

{/* Your Connector specific fields */}
{formData.connector_type === ConnectorType.YOUR_CONNECTOR && (
  <>
    {/* API Key */}
    <div>
      <label className="block text-sm font-medium text-text mb-2">
        API Key <span className="text-error">*</span>
      </label>
      <input
        type="password"
        value={formData.api_key}
        onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
        placeholder="Enter your API key"
        className="w-full px-4 py-2.5 border border-border rounded-lg bg-bg text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
        required
      />
      <p className="mt-1 text-xs text-muted">
        Get your API key from [Service Name]: Settings → API Keys
      </p>
    </div>

    {/* Option 1 */}
    <div>
      <label className="block text-sm font-medium text-text mb-2">
        Option 1 Description
      </label>
      <input
        type="text"
        value={formData.sync_config?.option1 || ''}
        onChange={(e) =>
          setFormData({
            ...formData,
            sync_config: { ...formData.sync_config, option1: e.target.value },
          })
        }
        placeholder="Enter value"
        className="w-full px-4 py-2.5 border border-border rounded-lg bg-bg text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
      />
      <p className="mt-1 text-xs text-muted">
        Helpful description of what this option does
      </p>
    </div>

    {/* Option 2 - Number */}
    <div>
      <label className="block text-sm font-medium text-text mb-2">
        Option 2 Description
      </label>
      <input
        type="number"
        min="1"
        max="1000"
        value={formData.sync_config?.option2 || 100}
        onChange={(e) =>
          setFormData({
            ...formData,
            sync_config: { ...formData.sync_config, option2: parseInt(e.target.value) || 100 },
          })
        }
        placeholder="100"
        className="w-full px-4 py-2.5 border border-border rounded-lg bg-bg text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
      />
      <p className="mt-1 text-xs text-muted">
        Valid range: 1-1000
      </p>
    </div>
  </>
)}
```

### Step 6: Update Form Submission Logic

**File**: `frontend/src/components/data-connections/CreateConnectionModal.tsx`

In the `handleSubmit` function:

```typescript
const handleSubmit = (e: React.FormEvent) => {
  e.preventDefault();

  // ... existing validation ...

  } else if (formData.connector_type === ConnectorType.YOUR_CONNECTOR) {
    // Your connector
    if (!formData.connector_name || !formData.api_key) {
      addToast({
        kind: 'error',
        message: 'Please fill in all required fields.',
      });
      return;
    }

    createConnector({
      data: {
        connector_name: formData.connector_name,
        connector_type: formData.connector_type,
        credentials: { api_key: formData.api_key },
        sync_config: {
          option1: formData.sync_config?.option1 || 'default',
          option2: formData.sync_config?.option2 || 100,
        },
        sync_mode: formData.sync_mode,
        description: formData.description,
        sync_schedule: formData.sync_schedule,
      },
    });
  } else {
    // Existing fallback logic...
  }
};
```

### Step 7: Update Form Validation

**File**: `frontend/src/components/data-connections/CreateConnectionModal.tsx`

Update the submit button's disabled condition:

```typescript
<button
  type="submit"
  disabled={
    isCreating ||
    !formData.connector_name ||
    (formData.connector_type === ConnectorType.PEOPLE_DATA_LABS && !formData.api_key) ||
    (formData.connector_type === ConnectorType.GREENHOUSE && !formData.api_key) ||
    (formData.connector_type === ConnectorType.YOUR_CONNECTOR && !formData.api_key) || // ← Add this
    (formData.connector_type === ConnectorType.FILESYSTEM && !formData.sync_config?.directory_path)
  }
  className="btn-primary"
>
```

### Step 8: Update Data Source Selector (For Talent Intelligence)

**File**: `frontend/src/components/ml-talent/DataSourceSelector.tsx`

Add icon and preview for your connector:

```typescript
// Add icon import at top:
import { YourIcon } from '@heroicons/react/24/outline';

// In the connector card rendering:
) : connector.connector_type === 'your_connector' ? (
  <YourIcon className="w-5 h-5 text-brand" />
) : (
  <DocumentIcon className="w-5 h-5 text-brand" />
)}

// Add preview section:
{connector.connector_type === 'your_connector' && connector.sync_config && (
  <div className="mt-2 p-2 bg-surface-2 rounded text-xs text-muted-2">
    <div className="flex items-center gap-2">
      <YourIcon className="w-4 h-4" />
      <span>
        Your Service
        {(connector.sync_config as any).option2 &&
          ` • Up to ${(connector.sync_config as any).option2} records`}
      </span>
    </div>
  </div>
)}
```

---

## Testing Your Connector

### 1. Unit Tests

Create `tests/test_your_connector_integration.py`:

```python
"""
Integration tests for Your Connector
"""

import asyncio
import pytest
import logging
from src.services.ingestion.connectors.your_connector import YourConnector

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_connector_check():
    """Test connection validation."""
    connector = YourConnector(
        credentials={"api_key": "test_key"},
        sync_config={"option1": "test", "option2": 50},
        customer_id="test"
    )
    
    # Note: Will fail without valid credentials
    is_connected = await connector.check()
    assert isinstance(is_connected, bool)


@pytest.mark.asyncio
async def test_connector_discover():
    """Test stream discovery."""
    connector = YourConnector(
        credentials={"api_key": "test_key"},
        sync_config={},
        customer_id="test"
    )
    
    catalog = connector.discover()
    
    assert "streams" in catalog
    assert len(catalog["streams"]) > 0
    assert catalog["streams"][0]["name"] == "primary_stream"


@pytest.mark.asyncio
async def test_connector_validate_config():
    """Test configuration validation."""
    # Valid config
    connector = YourConnector(
        credentials={"api_key": "test_key"},
        sync_config={"option2": 50},
        customer_id="test"
    )
    result = connector.validate_config()
    assert result["status"] == "valid"
    
    # Invalid config
    connector_invalid = YourConnector(
        credentials={},  # Missing API key
        sync_config={"option2": 5000},  # Out of range
        customer_id="test"
    )
    result = connector_invalid.validate_config()
    assert result["status"] == "invalid"
    assert len(result["errors"]) > 0


@pytest.mark.skipif(
    not os.getenv("YOUR_SERVICE_API_KEY"),
    reason="YOUR_SERVICE_API_KEY not set"
)
@pytest.mark.asyncio
async def test_connector_sync_real_api():
    """Test actual API sync with real credentials."""
    api_key = os.getenv("YOUR_SERVICE_API_KEY")
    
    connector = YourConnector(
        credentials={"api_key": api_key},
        sync_config={"option2": 10},
        customer_id="test"
    )
    
    # Test connection
    is_connected = await connector.check()
    assert is_connected, "Connection test failed"
    
    # Test sync
    result = await connector.sync()
    
    assert "records" in result
    assert isinstance(result["records"], list)
    logger.info(f"Fetched {len(result['records'])} records")
```

### 2. Manual API Testing

Create a simple test script `test_your_connector_manual.sh`:

```bash
#!/bin/bash

# Test Your Connector endpoints

BASE_URL="http://localhost:5001"
YOUR_API_KEY="your_test_api_key_here"

echo "1. Testing connection..."
curl -X POST "$BASE_URL/api/connectors/test-connection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "connector_type": "your_connector",
    "credentials": {"api_key": "'"$YOUR_API_KEY"'"},
    "sync_config": {"option2": 10}
  }'

echo -e "\n\n2. Creating connector configuration..."
curl -X POST "$BASE_URL/api/connectors/configurations" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "connector_name": "Test Your Connector",
    "connector_type": "your_connector",
    "credentials": {"api_key": "'"$YOUR_API_KEY"'"},
    "sync_config": {"option1": "test", "option2": 50},
    "sync_mode": "full_refresh"
  }'
```

### 3. Frontend Testing

1. Start the frontend dev server: `npm run start`
2. Navigate to **Data Connections** page
3. Click **New Connection** dropdown
4. Verify "Your Service Name" appears in the list
5. Select it and verify the form shows your custom fields
6. Fill in test credentials and click **Create Connection**
7. Verify the connection appears in the list with correct details

### 4. End-to-End Testing

Test in the Talent Intelligence workflow:

1. Go to **Talent Intelligence** page
2. Click **Data Source** tab
3. Your connector should appear in the list
4. Select it and proceed through the workflow
5. Verify data syncs correctly

---

## Deployment Checklist

Before deploying your connector to production:

- [ ] All abstract methods implemented
- [ ] Error handling for API failures
- [ ] Credential validation works
- [ ] Rate limiting handled (if applicable)
- [ ] Pagination implemented (if applicable)
- [ ] Unit tests written and passing
- [ ] Manual testing completed
- [ ] Frontend UI looks correct
- [ ] Documentation updated (this file!)
- [ ] API credentials secured (never commit)
- [ ] Connector type marked as `available=True` in API
- [ ] Backend container rebuilt and restarted
- [ ] Frontend changes compiled and deployed

### Rebuild Commands

```bash
# Backend
docker-compose -f docker/docker-compose.yml build app
docker-compose -f docker/docker-compose.yml up -d app

# Frontend (if running in Docker)
docker-compose -f docker/docker-compose.yml build frontend
docker-compose -f docker/docker-compose.yml up -d frontend

# Frontend (if running locally)
npm run build  # Production build
# OR
npm run start  # Development server auto-recompiles
```

---

## Examples

### Example 1: Greenhouse Connector (Real Implementation)

See actual working code:
- Backend: `src/services/ingestion/connectors/greenhouse.py`
- API: `src/api/routes/connectors.py` (search for "greenhouse")
- Frontend: `frontend/src/components/data-connections/CreateConnectionModal.tsx` (search for "GREENHOUSE")

### Example 2: People Data Labs Connector

See actual working code:
- Backend: `src/services/ingestion/connectors/people_data_labs.py`
- API: Uses standard connector endpoints
- Frontend: `CreateConnectionModal.tsx` (search for "PEOPLE_DATA_LABS")

### Example 3: Filesystem Connector (Simplest)

See actual working code:
- Backend: `src/services/ingestion/connectors/filesystem.py`
- No special API endpoints needed
- Frontend: `CreateConnectionModal.tsx` (search for "FILESYSTEM")

---

## Common Patterns

### Authentication Methods

**Basic Auth** (Greenhouse):
```python
headers = {
    "Authorization": f"Basic {base64.b64encode(f'{api_key}:'.encode()).decode()}"
}
```

**Bearer Token** (PDL):
```python
headers = {
    "X-Api-Key": api_key
}
```

**OAuth 2.0** (Future connectors):
```python
# Store refresh_token in credentials
# Implement token refresh logic in _make_request
```

### Pagination

```python
async def _fetch_all_pages(self, endpoint: str) -> List[Dict]:
    """Fetch all pages from a paginated endpoint."""
    all_records = []
    page = 1
    
    while True:
        response = await self._make_request(
            "GET",
            endpoint,
            params={"page": page, "per_page": 100}
        )
        
        records = response.get("items", [])
        if not records:
            break
        
        all_records.extend(records)
        page += 1
        
        # Respect rate limits
        await asyncio.sleep(0.5)
    
    return all_records
```

### Rate Limiting

```python
from asyncio import Semaphore

class YourConnector(BaseConnector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rate_limiter = Semaphore(5)  # Max 5 concurrent requests
    
    async def _make_request(self, *args, **kwargs):
        async with self._rate_limiter:
            return await super()._make_request(*args, **kwargs)
```

### Error Recovery

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class YourConnector(BaseConnector):
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _make_request(self, *args, **kwargs):
        # Will automatically retry on failure with exponential backoff
        return await super()._make_request(*args, **kwargs)
```

---

## Troubleshooting

### Common Issues

**Issue**: Connector doesn't appear in dropdown
- **Check**: `available=True` in `get_available_connector_types`
- **Check**: Frontend enum includes your connector type
- **Check**: Backend container rebuilt after changes

**Issue**: Form validation fails
- **Check**: Validation logic in `handleSubmit`
- **Check**: Required fields marked correctly
- **Check**: `disabled` condition on submit button

**Issue**: API returns 404 for connector
- **Check**: Connector type added to enum
- **Check**: Backend restarted after changes
- **Check**: Import statement correct

**Issue**: Credentials not working
- **Check**: `_get_api_key()` logic
- **Check**: Auth header format matches API docs
- **Check**: Credentials encrypted correctly in database

**Issue**: Data not syncing
- **Check**: `sync()` method returns correct format
- **Check**: `read_stream()` yields records properly
- **Check**: Error logs in `docker-compose logs app`

---

## Additional Resources

- [Airbyte Connector Specification](https://docs.airbyte.com/understanding-airbyte/airbyte-protocol)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app/)

---

## Getting Help

If you run into issues:

1. Check existing connector implementations for reference
2. Review this guide's examples section
3. Check application logs: `docker-compose logs app --tail=100`
4. Verify API responses with `curl` or Postman
5. Ask the team in #engineering-help

---

**Happy Connector Building! 🚀**

