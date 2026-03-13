# Eliza Platform Talent Intelligence MCP Server

Model Context Protocol (MCP) server for accessing Eliza Platform's AI-powered talent intelligence features.

## Features

- 🔍 **Talent Analysis**: Start and manage AI-powered talent analyses
- 📊 **Results Tracking**: Monitor analysis progress and retrieve results
- 🎯 **Refinement**: Adjust search criteria to find better candidates
- 💬 **Feedback**: Submit feedback to improve future analyses
- 🔑 **API Key Management**: Create and manage API keys directly from MCP

## Authentication

### Recommended: API Key Authentication

API keys provide secure, permanent access without exposing user credentials.

#### Step 1: Generate an API Key

Use the MCP tool to generate an API key:

```
Tool: create_api_key
Parameters:
  name: "MCP Server Production"
  description: "API key for talent intelligence MCP server"
  expires_in_days: "90"
```

**⚠️ IMPORTANT:** Save the API key immediately - it's only shown once!

#### Step 2: Store the API Key Securely

Create a secrets directory and save the key:

```bash
mkdir -p secrets
echo "uak_your_api_key_here" > secrets/eliza_api_key.txt
chmod 600 secrets/eliza_api_key.txt
```

Add to `.gitignore`:
```
secrets/
```

#### Step 3: Configure Docker

Use the provided `docker-compose.example.yml`:

```bash
cp docker-compose.example.yml docker-compose.yml
# Edit docker-compose.yml to set ELIZA_API_BASE if needed
```

The Docker secret will be automatically loaded from `secrets/eliza_api_key.txt`.

### Legacy: Email/Password Authentication (Deprecated)

For backward compatibility, email/password authentication is still supported:

```bash
# Create secrets
echo "user@example.com" > secrets/eliza_email.txt
echo "password123" > secrets/eliza_password.txt
```

Update `docker-compose.yml`:
```yaml
secrets:
  - eliza_email
  - eliza_password

secrets:
  eliza_email:
    file: ./secrets/eliza_email.txt
  eliza_password:
    file: ./secrets/eliza_password.txt
```

**⚠️ Recommendation:** Migrate to API keys for better security and no session expiration.

## Running the Server

### With Docker Compose (Recommended)

```bash
docker-compose up -d
```

### With Docker

```bash
docker build -t eliza-talent-mcp .
docker run -it \
  -e ELIZA_API_BASE="http://backend:5001" \
  --secret eliza_api_key \
  eliza-talent-mcp
```

### Locally (Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ELIZA_API_BASE="http://localhost:5001"
export ELIZA_API_KEY="uak_your_api_key_here"

# Run the server
python eliza_talent_server.py
```

## Available Tools

### Authentication & API Key Management

- **check_authentication_status**: Verify authentication and view user info
- **create_api_key**: Generate a new API key for programmatic access
- **list_api_keys**: List all API keys for the current user
- **revoke_api_key**: Revoke an API key (cannot be undone)

### Talent Intelligence

- **start_talent_analysis_from_connector**: Start a new talent analysis
- **get_analysis_status**: Check progress of an analysis
- **get_analysis_results**: Retrieve complete results
- **list_talent_analyses**: List all analyses with pagination
- **refine_talent_analysis**: Adjust search criteria
- **submit_analysis_feedback**: Provide feedback on results
- **get_analysis_diagnostic**: View job competencies and weights
- **get_pdl_query**: View the People Data Labs search query

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ELIZA_API_BASE` | Yes | `http://localhost:5001` | Base URL of Eliza Platform API |
| `ELIZA_API_KEY` | Recommended | - | API key for authentication |
| `ELIZA_EMAIL` | Legacy | - | User email (deprecated) |
| `ELIZA_PASSWORD` | Legacy | - | User password (deprecated) |

### Docker Secrets

| Secret | Path | Description |
|--------|------|-------------|
| `eliza_api_key` | `/run/secrets/eliza_api_key` | API key (recommended) |
| `eliza_email` | `/run/secrets/eliza_email` | User email (legacy) |
| `eliza_password` | `/run/secrets/eliza_password` | User password (legacy) |

## Security Best Practices

1. **Use API Keys**: Prefer API keys over email/password
2. **Set Expiration**: Use `expires_in_days` when creating keys
3. **Rotate Keys**: Regularly rotate API keys (every 90 days recommended)
4. **Revoke Unused Keys**: Remove keys that are no longer needed
5. **Use Docker Secrets**: Never commit secrets to version control
6. **Limit Permissions**: Use role-based access control (RBAC)

## Troubleshooting

### Authentication Failed

```
❌ Authentication not configured.
```

**Solution:** Set `ELIZA_API_KEY` or create an API key using the `create_api_key` tool.

### API Key Expired

```
❌ Invalid or expired API key
```

**Solution:** Create a new API key and update your secrets file.

### Connection Refused

```
❌ Request error: Connection refused
```

**Solution:** Check that `ELIZA_API_BASE` points to the correct backend URL and the backend is running.

## Example Usage

### 1. Check Authentication

```
Tool: check_authentication_status
```

### 2. Create API Key

```
Tool: create_api_key
Parameters:
  name: "Production MCP Server"
  description: "Long-term API key for MCP server"
  expires_in_days: "90"
```

### 3. Start Talent Analysis

```
Tool: start_talent_analysis_from_connector
Parameters:
  job_description: "Senior ML Engineer with 5+ years experience..."
  ideal_candidate_description: "Strong Python, TensorFlow, and AWS skills..."
  role: "Machine Learning Engineer"
  data_source_connector_id: "conn_fs_resumes"
  baseline_employee_ids: "1,2,3"
```

### 4. Check Analysis Status

```
Tool: get_analysis_status
Parameters:
  analysis_id: "analysis_abc123"
```

### 5. Get Results

```
Tool: get_analysis_results
Parameters:
  analysis_id: "analysis_abc123"
```

## Development

### Running Tests

```bash
# TODO: Add tests
pytest tests/
```

### Logging

Logs are written to stderr and include:
- Authentication status
- API requests and responses
- Error details

View logs:
```bash
docker-compose logs -f eliza-talent-mcp
```

## License

Part of the Eliza Platform project.

## Support

For issues or questions, please contact the Eliza Platform team.

