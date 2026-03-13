# Connector Documentation

This folder contains documentation for data source connectors in the Eliza Platform.

## Quick Links

- **[Connector Development Guide](./CONNECTOR_DEVELOPMENT_GUIDE.md)** - Complete guide for building new connectors
- **[Greenhouse Connector Enabled](./GREENHOUSE_CONNECTOR_ENABLED.md)** - Recent changes enabling Greenhouse

## Available Connectors

### Production Ready ✅

| Connector | Type | Purpose | Documentation |
|-----------|------|---------|---------------|
| **People Data Labs** | `people_data_labs` | Market talent data via PDL API | [PDL API Docs](https://docs.peopledatalabs.com/) |
| **Filesystem** | `filesystem` | Local file system for testing | Built-in, no external API |
| **Greenhouse** | `greenhouse` | ATS candidate and job data | [Greenhouse Harvest API](https://developers.greenhouse.io/harvest.html) |

### Coming Soon 🚧

| Connector | Type | Purpose | Status |
|-----------|------|---------|--------|
| **Lever** | `lever` | ATS candidate and job data | Planned |
| **Workday** | `workday` | Employee and org data | Planned |
| **Salesforce** | `salesforce` | CRM data | Planned |
| **HubSpot** | `hubspot` | CRM data | Planned |

## Getting Started

### Using Connectors

1. Navigate to **Data Connections** page in the UI
2. Click **New Connection** dropdown
3. Select a connector type
4. Fill in credentials and configuration
5. Test connection and save

### Building Connectors

See the **[Connector Development Guide](./CONNECTOR_DEVELOPMENT_GUIDE.md)** for:
- Architecture overview
- Step-by-step implementation
- Code examples
- Testing strategies
- Deployment checklist

## Architecture

```
Frontend (React/TypeScript)
    ↓
API Layer (FastAPI)
    ↓
Connector Service (Python)
    ↓
Base Connector (Airbyte-style)
    ↓
Concrete Connector Implementation
    ↓
External API
```

## Key Concepts

### Streams
Connectors expose **streams** (e.g., "candidates", "jobs") that represent different data entities. Each stream has:
- Schema definition
- Supported sync modes (full_refresh, incremental)
- Data transformation logic

### Sync Modes
- **Full Refresh**: Fetch all data every time
- **Incremental**: Only fetch new/updated data since last sync

### Configuration
Each connector stores:
- **Credentials**: API keys, OAuth tokens (encrypted)
- **Sync Config**: Connector-specific settings (query params, filters, etc.)
- **Sync Schedule**: When to run syncs (e.g., "0 */6 * * *" for every 6 hours)

## Common Tasks

### Add a New Connector
```bash
# 1. Follow the development guide
open docs/connectors/CONNECTOR_DEVELOPMENT_GUIDE.md

# 2. Implement backend connector
# Create: src/services/ingestion/connectors/your_connector.py

# 3. Update API routes
# Edit: src/api/routes/connectors.py

# 4. Update frontend UI
# Edit: frontend/src/components/data-connections/CreateConnectionModal.tsx

# 5. Test and deploy
pytest tests/test_your_connector.py
docker-compose build app
docker-compose up -d app
```

### Test a Connector
```bash
# Run integration tests
pytest tests/test_greenhouse_integration.py

# Manual API test
curl -X POST "http://localhost:5001/api/connectors/test-connection" \
  -H "Content-Type: application/json" \
  -d '{"connector_type": "greenhouse", "credentials": {"api_key": "..."}, "sync_config": {}}'
```

### Debug Connector Issues
```bash
# Check app logs
docker-compose logs app --tail=100 --follow

# Check database
docker exec docker-postgres-1 psql -U user -d ai_enablement -c \
  "SELECT connector_id, connector_name, connector_type, is_enabled FROM connector_configurations;"

# Test connection manually
python -c "
from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
connector = GreenhouseConnector(credentials={'api_key': 'YOUR_KEY'}, sync_config={}, customer_id='test')
import asyncio
print(asyncio.run(connector.check()))
"
```

## Best Practices

1. **Follow the Framework**: Use `BaseConnector` as your base class
2. **Handle Errors Gracefully**: Catch API errors and log them properly
3. **Respect Rate Limits**: Implement backoff and retry logic
4. **Validate Early**: Check config in `validate_config()` before syncing
5. **Stream Data**: Use generators/iterators for memory efficiency
6. **Test Thoroughly**: Unit tests + integration tests + manual testing
7. **Document Everything**: Add inline comments and update this README

## Support

- **Questions?** Check the [Connector Development Guide](./CONNECTOR_DEVELOPMENT_GUIDE.md)
- **Issues?** Check app logs: `docker-compose logs app`
- **Need Help?** Ask in #engineering-help

---

**Last Updated**: October 24, 2025

