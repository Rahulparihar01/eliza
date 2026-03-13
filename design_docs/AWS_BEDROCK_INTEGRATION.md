# AWS Bedrock Integration Guide

## Overview

The AI Enablement Platform now supports **AWS Bedrock** as an AI model provider, giving you access to foundation models from Anthropic (Claude), Meta (Llama), Amazon (Titan), and more through a unified API.

### Key Features

- ✅ **Multiple Authentication Methods**: API Keys or IAM Roles
- ✅ **Multi-Region Support**: Configure providers for different AWS regions
- ✅ **OpenAI-Compatible API**: Use Bedrock models through familiar OpenAI client
- ✅ **Model Discovery**: Automatically discover available models via boto3 API
- ✅ **Per-Configuration Model Management**: Add/remove models from your configurations
- ✅ **Health Monitoring**: Track provider health and connection status
- ✅ **Secure Credential Storage**: Encrypted storage of AWS credentials

---

## Architecture

### Components

1. **BedrockProvider** (`src/services/providers/bedrock_provider.py`)
   - OpenAI-compatible client wrapper for Bedrock
   - Handles authentication (API keys or IAM roles)
   - Manages model interactions

2. **BedrockDiscoveryService** (`src/services/bedrock_discovery_service.py`)
   - boto3-based model discovery
   - Lists available foundation models in a region
   - Tests credentials and connectivity

3. **BedrockService** (`src/services/bedrock_service.py`)
   - CRUD operations for Bedrock configurations
   - Manages model lists per configuration
   - Handles credential encryption/decryption

4. **API Routes** (`src/api/routes/bedrock.py`)
   - RESTful endpoints for configuration management
   - Model discovery and addition endpoints
   - Connection testing endpoints

---

## Setup Guide

### Prerequisites

1. **AWS Account** with Bedrock access
2. **AWS Credentials** (one of):
   - Access Key ID + Secret Access Key
   - IAM Role (for EC2/ECS deployments)
3. **Bedrock Model Access**: Request access to models in AWS Console

### Step 1: Install Dependencies

```bash
# Dependencies are already in requirements.txt
pip install boto3>=1.34.0 botocore>=1.34.0
```

### Step 2: Request Bedrock Model Access

1. Go to AWS Console → Bedrock
2. Navigate to "Model access"
3. Request access to desired models (e.g., Claude, Llama)
4. Wait for approval (usually instant for most models)

### Step 3: Get AWS Credentials

**Option A: API Keys (Development)**
```bash
# Create IAM user with Bedrock permissions
aws iam create-user --user-name bedrock-api-user

# Attach Bedrock policy
aws iam attach-user-policy \
  --user-name bedrock-api-user \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

# Create access key
aws iam create-access-key --user-name bedrock-api-user
```

**Option B: IAM Role (Production)**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## API Usage

### 1. Create Bedrock Configuration

**Using API Keys:**
```bash
curl -X POST "http://localhost:5001/v1/bedrock/configurations" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "auth_method": "api_keys",
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "aws_region": "us-west-2",
    "connection_timeout": 30,
    "max_retries": 3
  }'
```

**Using IAM Role:**
```bash
curl -X POST "http://localhost:5001/v1/bedrock/configurations" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "auth_method": "iam_role",
    "aws_region": "us-west-2",
    "connection_timeout": 30,
    "max_retries": 3
  }'
```

**Response:**
```json
{
  "id": 1,
  "customer_id": "your_customer_id",
  "auth_method": "api_keys",
  "aws_region": "us-west-2",
  "base_url": "https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1",
  "available_models": [],
  "default_model": null,
  "is_enabled": true,
  "is_healthy": false,
  "last_health_check": null,
  "connection_timeout": 30,
  "max_retries": 3,
  "created_at": "2025-01-08T12:00:00Z",
  "updated_at": null
}
```

### 2. Test Connection

```bash
curl -X POST "http://localhost:5001/v1/bedrock/configurations/1/test" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "message": "Credentials valid and Bedrock accessible",
  "region": "us-west-2",
  "auth_method": "api_keys",
  "response_time_ms": 245.3,
  "error_details": null,
  "tested_at": "2025-01-08T12:05:00Z"
}
```

### 3. Discover Available Models

```bash
curl -X POST "http://localhost:5001/v1/bedrock/configurations/1/discover-models" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "region": "us-west-2",
  "discovered_models": [
    {
      "model_id": "anthropic.claude-v2",
      "model_name": "Claude 2",
      "provider": "anthropic",
      "is_enabled": false,
      "max_tokens": 100000,
      "supports_streaming": true
    },
    {
      "model_id": "anthropic.claude-instant-v1",
      "model_name": "Claude Instant",
      "provider": "anthropic",
      "is_enabled": false,
      "max_tokens": 100000,
      "supports_streaming": true
    },
    {
      "model_id": "meta.llama2-70b-chat-v1",
      "model_name": "Llama 2 Chat 70B",
      "provider": "meta",
      "is_enabled": false,
      "max_tokens": 4096,
      "supports_streaming": true
    }
  ],
  "total_count": 3,
  "discovery_timestamp": "2025-01-08T12:10:00Z"
}
```

### 4. Add Model to Configuration

```bash
curl -X POST "http://localhost:5001/v1/bedrock/configurations/1/models" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "anthropic.claude-v2",
    "model_name": "Claude 2",
    "provider": "anthropic",
    "max_tokens": 100000,
    "supports_streaming": true,
    "set_as_default": true
  }'
```

### 5. List All Configurations

```bash
curl -X GET "http://localhost:5001/v1/bedrock/configurations" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 6. Update Configuration

```bash
curl -X PUT "http://localhost:5001/v1/bedrock/configurations/1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "aws_region": "us-east-1",
    "connection_timeout": 60
  }'
```

### 7. Remove Model from Configuration

```bash
curl -X DELETE "http://localhost:5001/v1/bedrock/configurations/1/models/anthropic.claude-v2" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 8. Delete Configuration

```bash
curl -X DELETE "http://localhost:5001/v1/bedrock/configurations/1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Using Bedrock Models

Once configured, Bedrock models are automatically available through the platform's model service:

### Via Python (Internal)
```python
from src.services.model_service import ModelService
from src.core.config import get_settings, get_customer_config

settings = get_settings()
customer_config = get_customer_config(settings.customer_id)
model_service = ModelService(settings, customer_config)

# List all providers (includes Bedrock)
providers = await model_service.get_providers_status()

# Generate text using Bedrock model
response = await model_service.generate_text(
    provider="bedrock_us-west-2_1",  # Auto-generated provider key
    model="anthropic.claude-v2",
    prompt="What is the capital of France?",
    max_tokens=100
)
```

### Via CrewAI (Flows)
```python
from crewai import Agent, Task

# Bedrock models are available through the platform's model service
analyst = Agent(
    role="Data Analyst",
    goal="Analyze business data",
    backstory="Expert analyst",
    llm="bedrock_us-west-2_1:anthropic.claude-v2"  # Use Bedrock model
)
```

---

## Security Considerations

### Credential Storage

- **API Keys**: Encrypted using Fernet (AES-128) before storage
- **Encryption Key**: Configured via `ENCRYPTION_KEY` environment variable
- **IAM Roles**: No credentials stored (uses AWS credential chain)

### IAM Policy (Minimum Permissions)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel"
      ],
      "Resource": "*"
    }
  ]
}
```

### Multi-Tenancy

- Configurations are per-customer (`customer_id`)
- Each customer can only access their own Bedrock configurations
- Credentials are never exposed in API responses

---

## Troubleshooting

### Connection Test Fails

**Issue**: `NoCredentialsError: AWS credentials not configured`

**Solution**:
- Verify API keys are correct
- Check IAM role is attached to EC2/ECS instance
- Ensure AWS credentials environment variables are set

**Issue**: `ClientError: Access Denied`

**Solution**:
- Check IAM policy has `bedrock:InvokeModel` permission
- Verify model access is granted in AWS Bedrock console
- Confirm region is correct

### Model Discovery Returns Empty List

**Issue**: No models found in discovery

**Solution**:
- Request model access in AWS Bedrock console
- Wait for approval (usually instant)
- Try different region (not all models available in all regions)

### Text Generation Fails

**Issue**: `Model not found` error

**Solution**:
- Ensure model is added to configuration
- Verify model ID is correct
- Check model is enabled (`is_enabled: true`)

### Rate Limiting

**Issue**: `ThrottlingException: Rate exceeded`

**Solution**:
- AWS Bedrock has rate limits per model
- Implement exponential backoff
- Request quota increase in AWS Service Quotas

---

## Best Practices

### 1. Use IAM Roles in Production

- Avoid storing API keys
- Use EC2/ECS instance roles
- Enable automatic credential rotation

### 2. Region Selection

- Choose region closest to your users
- Consider model availability per region
- Note: Not all models available in all regions

### 3. Model Selection

- **Claude** (Anthropic): Best for reasoning, analysis, long context
- **Llama 2** (Meta): Good for general chat, cost-effective
- **Titan** (Amazon): Optimized for AWS, good baseline

### 4. Cost Optimization

- Monitor usage via AWS Cost Explorer
- Use model-specific pricing (Claude > Llama > Titan)
- Set appropriate `max_tokens` limits

### 5. Error Handling

- Implement retry logic for transient errors
- Monitor health status regularly
- Set up alerts for configuration failures

---

## Advanced Configuration

### Multiple Regions

You can configure multiple Bedrock providers for different regions:

```python
# Configuration for us-west-2
config_west = {
    "aws_region": "us-west-2",
    "auth_method": "api_keys",
    ...
}

# Configuration for us-east-1
config_east = {
    "aws_region": "us-east-1",
    "auth_method": "api_keys",
    ...
}
```

This creates separate providers: `bedrock_us-west-2_1` and `bedrock_us-east-1_2`

### Model-Specific Settings

```python
# Add model with custom settings
{
    "model_id": "anthropic.claude-v2",
    "model_name": "Claude 2 (Custom)",
    "provider": "anthropic",
    "max_tokens": 50000,  # Reduced from 100K
    "supports_streaming": true,
    "set_as_default": true
}
```

---

## Migration Guide

### From OpenAI to Bedrock

**Before:**
```python
response = await openai_client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**After:**
```python
# Same OpenAI-compatible interface!
response = await bedrock_client.chat.completions.create(
    model="anthropic.claude-v2",
    messages=[{"role": "user", "content": "Hello"}]
)
```

---

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/bedrock/configurations` | Create configuration |
| GET | `/v1/bedrock/configurations` | List configurations |
| GET | `/v1/bedrock/configurations/{id}` | Get configuration |
| PUT | `/v1/bedrock/configurations/{id}` | Update configuration |
| DELETE | `/v1/bedrock/configurations/{id}` | Delete configuration |
| POST | `/v1/bedrock/configurations/{id}/test` | Test connection |
| POST | `/v1/bedrock/configurations/{id}/discover-models` | Discover models |
| POST | `/v1/bedrock/configurations/{id}/models` | Add model |
| DELETE | `/v1/bedrock/configurations/{id}/models/{model_id}` | Remove model |

### Authentication

All endpoints require Bearer token authentication:

```
Authorization: Bearer YOUR_JWT_TOKEN
```

---

## Support

### Logging

Bedrock operations are logged at various levels:

```python
# Enable debug logging
import logging
logging.getLogger("src.services.providers.bedrock_provider").setLevel(logging.DEBUG)
logging.getLogger("src.services.bedrock_service").setLevel(logging.DEBUG)
```

### Monitoring

- Check provider health via `/v1/models/health`
- Monitor AWS CloudWatch for Bedrock metrics
- Track error counts in `CustomerAIProvider.error_count`

---

## Future Enhancements

- [ ] Streaming support via Server-Sent Events (SSE)
- [ ] Bedrock embeddings integration
- [ ] Custom model fine-tuning support
- [ ] Cost tracking and reporting
- [ ] Model performance benchmarking
- [ ] Automatic failover between regions
- [ ] Rate limiting within application
- [ ] Model version management

---

## Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)

---

## Changelog

### v1.0.0 (2025-01-08)
- Initial AWS Bedrock integration
- Support for API key and IAM role authentication
- Model discovery via boto3 API
- OpenAI-compatible API interface
- CRUD operations for configurations
- Encrypted credential storage
- Multi-region support

