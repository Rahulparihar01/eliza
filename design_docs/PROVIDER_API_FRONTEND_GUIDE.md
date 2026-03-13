# Provider Configuration API - Frontend Developer Guide

## 🎯 Overview

This guide provides everything frontend developers need to integrate the **unified provider configuration system** into the UI. Users can configure their own API keys for OpenAI, Anthropic, Groq, and AWS Bedrock.

---

## 📋 Table of Contents

1. [API Endpoints Overview](#api-endpoints-overview)
2. [TypeScript Types](#typescript-types)
3. [Provider Types Reference](#provider-types-reference)
4. [API Endpoint Details](#api-endpoint-details)
5. [Common Workflows](#common-workflows)
6. [UI/UX Guidelines](#uiux-guidelines)
7. [Error Handling](#error-handling)
8. [Code Examples](#code-examples)

---

## API Endpoints Overview

**Base URL**: `/v1/providers`

| Method | Endpoint | Purpose | Auth Required |
|--------|----------|---------|---------------|
| GET | `/available` | List available provider types | ✅ Yes |
| POST | `/configurations` | Create provider config | ✅ Yes |
| GET | `/configurations` | List user's configs | ✅ Yes |
| GET | `/configurations/{id}` | Get specific config | ✅ Yes |
| PUT | `/configurations/{id}` | Update config | ✅ Yes |
| DELETE | `/configurations/{id}` | Delete config | ✅ Yes |
| POST | `/configurations/{id}/test` | Test connection | ✅ Yes |

---

## TypeScript Types

### Core Types

```typescript
// Provider type enum
type ProviderType = 'openai' | 'anthropic' | 'groq' | 'bedrock';

// Provider metadata (for available providers)
interface ProviderTypeInfo {
  type: ProviderType;
  name: string;
  description: string;
  requires_api_key: boolean;
  supports_models: string[];
  auth_methods: string[];
}

// Provider configuration response
interface ProviderConfiguration {
  id: number;
  customer_id: string;
  provider_type: ProviderType;
  name: string | null;
  is_enabled: boolean;
  is_healthy: boolean;
  last_health_check: string | null;  // ISO 8601 datetime
  
  // Sanitized config (NO API keys)
  config_summary: {
    base_url?: string;
    available_models: string[];
    default_model: string | null;
    max_retries?: number;
    timeout?: number;
    // Bedrock-specific
    auth_method?: 'api_keys' | 'iam_role';
    aws_region?: string;
  };
  
  available_models: string[];
  default_model: string | null;
  
  created_at: string;  // ISO 8601 datetime
  updated_at: string | null;  // ISO 8601 datetime
  error_count: number;
  last_error: string | null;
}

// Create configuration request
interface CreateProviderConfigRequest {
  provider_type: ProviderType;
  name?: string;
  is_enabled?: boolean;  // Default: true
  config: ProviderSpecificConfig;
}

// Update configuration request
interface UpdateProviderConfigRequest {
  name?: string;
  is_enabled?: boolean;
  config?: Partial<ProviderSpecificConfig>;
}

// Connection test request
interface ConnectionTestRequest {
  test_prompt?: string;  // Default: "Hello, this is a connection test."
}

// Connection test response
interface ConnectionTestResponse {
  success: boolean;
  provider_type: ProviderType;
  message: string;
  response_time_ms: number | null;
  test_output: string | null;
  error_details: string | null;
  tested_at: string;  // ISO 8601 datetime
  model_tested: string | null;
}

// List response
interface ProviderListResponse {
  providers: ProviderConfiguration[];
  total_count: number;
  by_type: {
    [key in ProviderType]?: number;
  };
}
```

### Provider-Specific Config Types

```typescript
// OpenAI configuration
interface OpenAIConfig {
  api_key: string;  // REQUIRED
  organization_id?: string;
  base_url?: string;  // Default: "https://api.openai.com/v1"
  available_models?: string[];  // Default: ["gpt-4", "gpt-3.5-turbo"]
  default_model?: string;
  max_retries?: number;  // Default: 3
  timeout?: number;  // Default: 60
}

// Anthropic configuration
interface AnthropicConfig {
  api_key: string;  // REQUIRED
  base_url?: string;  // Default: "https://api.anthropic.com"
  available_models?: string[];  // Default: ["claude-3-opus-20240229", ...]
  default_model?: string;
  max_retries?: number;  // Default: 3
  timeout?: number;  // Default: 60
}

// Groq configuration
interface GroqConfig {
  api_key: string;  // REQUIRED
  base_url?: string;  // Default: "https://api.groq.com/openai/v1"
  available_models?: string[];  // Default: ["llama-3.1-70b-versatile", ...]
  default_model?: string;
  max_retries?: number;  // Default: 3
  timeout?: number;  // Default: 60
}

// Bedrock configuration (API Keys)
interface BedrockConfigAPIKeys {
  auth_method: 'api_keys';  // REQUIRED
  aws_region: string;  // REQUIRED, e.g., "us-west-2"
  aws_access_key_id: string;  // REQUIRED
  aws_secret_access_key: string;  // REQUIRED
  aws_session_token?: string;  // Optional
  available_models?: any[];  // Managed separately via discovery
  default_model?: string | null;
}

// Bedrock configuration (IAM Role)
interface BedrockConfigIAMRole {
  auth_method: 'iam_role';  // REQUIRED
  aws_region: string;  // REQUIRED
  available_models?: any[];
  default_model?: string | null;
}

type BedrockConfig = BedrockConfigAPIKeys | BedrockConfigIAMRole;

// Union type for all provider configs
type ProviderSpecificConfig = 
  | OpenAIConfig 
  | AnthropicConfig 
  | GroqConfig 
  | BedrockConfig;
```

---

## Provider Types Reference

### OpenAI

**Provider Type**: `"openai"`

**Required Fields**:
- `api_key`: OpenAI API key (starts with `sk-`)

**Optional Fields**:
- `organization_id`: OpenAI organization ID (starts with `org-`)
- `base_url`: Custom API base URL (default: `https://api.openai.com/v1`)
- `available_models`: Array of model IDs user wants to use
- `default_model`: Default model for this configuration
- `max_retries`: Number of retry attempts (1-10, default: 3)
- `timeout`: Request timeout in seconds (5-300, default: 60)

**Default Models**: `["gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo"]`

**Where to Get API Key**: https://platform.openai.com/api-keys

---

### Anthropic

**Provider Type**: `"anthropic"`

**Required Fields**:
- `api_key`: Anthropic API key (starts with `sk-ant-`)

**Optional Fields**:
- `base_url`: Custom API base URL (default: `https://api.anthropic.com`)
- `available_models`: Array of model IDs
- `default_model`: Default model
- `max_retries`: Number of retry attempts (1-10, default: 3)
- `timeout`: Request timeout in seconds (5-300, default: 60)

**Default Models**: 
```typescript
[
  "claude-3-opus-20240229",
  "claude-3-sonnet-20240229",
  "claude-3-haiku-20240307",
  "claude-2.1",
  "claude-instant-1.2"
]
```

**Where to Get API Key**: https://console.anthropic.com/settings/keys

---

### Groq

**Provider Type**: `"groq"`

**Required Fields**:
- `api_key`: Groq API key (starts with `gsk_`)

**Optional Fields**:
- `base_url`: Custom API base URL (default: `https://api.groq.com/openai/v1`)
- `available_models`: Array of model IDs
- `default_model`: Default model
- `max_retries`: Number of retry attempts (1-10, default: 3)
- `timeout`: Request timeout in seconds (5-300, default: 60)

**Default Models**:
```typescript
[
  "llama-3.1-70b-versatile",
  "llama-3.1-8b-instant",
  "mixtral-8x7b-32768",
  "gemma-7b-it"
]
```

**Where to Get API Key**: https://console.groq.com/keys

---

### AWS Bedrock

**Provider Type**: `"bedrock"`

**Required Fields (API Keys auth)**:
- `auth_method`: `"api_keys"`
- `aws_region`: AWS region (e.g., `"us-west-2"`)
- `aws_access_key_id`: AWS Access Key ID (starts with `AKIA`)
- `aws_secret_access_key`: AWS Secret Access Key

**Required Fields (IAM Role auth)**:
- `auth_method`: `"iam_role"`
- `aws_region`: AWS region

**Optional Fields**:
- `aws_session_token`: Session token for temporary credentials
- `available_models`: Managed via separate discovery API
- `default_model`: Default model ID

**Supported Regions**:
```typescript
[
  'us-east-1',      // US East (N. Virginia)
  'us-west-2',      // US West (Oregon)
  'ap-southeast-1', // Asia Pacific (Singapore)
  'ap-northeast-1', // Asia Pacific (Tokyo)
  'eu-central-1',   // Europe (Frankfurt)
  'eu-west-1',      // Europe (Ireland)
  'eu-west-2',      // Europe (London)
  'eu-west-3',      // Europe (Paris)
  'ap-south-1',     // Asia Pacific (Mumbai)
  'ca-central-1',   // Canada (Central)
]
```

**Where to Get Credentials**: AWS IAM Console → Users → Security Credentials

---

## API Endpoint Details

### 1. Get Available Provider Types

```http
GET /v1/providers/available
```

**Purpose**: Get metadata about all available provider types to populate UI

**Authentication**: Required (Bearer token)

**Request**: None

**Response**:
```json
{
  "available_providers": [
    {
      "type": "openai",
      "name": "OpenAI",
      "description": "OpenAI GPT models (GPT-4, GPT-3.5-turbo, etc.)",
      "requires_api_key": true,
      "supports_models": ["gpt-4", "gpt-3.5-turbo"],
      "auth_methods": ["api_key"]
    },
    {
      "type": "anthropic",
      "name": "Anthropic",
      "description": "Anthropic Claude models",
      "requires_api_key": true,
      "supports_models": ["claude-3-opus-20240229", "claude-3-sonnet-20240229"],
      "auth_methods": ["api_key"]
    },
    {
      "type": "groq",
      "name": "Groq",
      "description": "Groq fast inference for Llama, Mixtral, and Gemma",
      "requires_api_key": true,
      "supports_models": ["llama-3.1-70b-versatile", "mixtral-8x7b-32768"],
      "auth_methods": ["api_key"]
    },
    {
      "type": "bedrock",
      "name": "AWS Bedrock",
      "description": "AWS Bedrock foundation models (Claude, Llama, Titan)",
      "requires_api_key": false,
      "supports_models": ["anthropic.claude-v2", "meta.llama2-70b-chat-v1"],
      "auth_methods": ["api_keys", "iam_role"]
    }
  ]
}
```

**UI Usage**: Use this to populate provider selection dropdown

---

### 2. Create Provider Configuration

```http
POST /v1/providers/configurations
Content-Type: application/json
```

**Purpose**: Create a new provider configuration

**Authentication**: Required (Bearer token)

**Request Body** (OpenAI Example):
```json
{
  "provider_type": "openai",
  "name": "My OpenAI Configuration",
  "is_enabled": true,
  "config": {
    "api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz",
    "organization_id": "org-123456",
    "available_models": ["gpt-4", "gpt-3.5-turbo"],
    "default_model": "gpt-4",
    "max_retries": 3,
    "timeout": 60
  }
}
```

**Request Body** (Anthropic Example):
```json
{
  "provider_type": "anthropic",
  "name": "My Claude Configuration",
  "is_enabled": true,
  "config": {
    "api_key": "sk-ant-api03-xyz123",
    "available_models": ["claude-3-opus-20240229"],
    "default_model": "claude-3-opus-20240229"
  }
}
```

**Request Body** (Bedrock Example):
```json
{
  "provider_type": "bedrock",
  "name": "My AWS Bedrock",
  "is_enabled": true,
  "config": {
    "auth_method": "api_keys",
    "aws_region": "us-west-2",
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  }
}
```

**Response** (Success - 201 Created):
```json
{
  "id": 123,
  "customer_id": "customer_abc123",
  "provider_type": "openai",
  "name": "My OpenAI Configuration",
  "is_enabled": true,
  "is_healthy": false,
  "last_health_check": null,
  "config_summary": {
    "base_url": "https://api.openai.com/v1",
    "available_models": ["gpt-4", "gpt-3.5-turbo"],
    "default_model": "gpt-4",
    "max_retries": 3,
    "timeout": 60
  },
  "available_models": ["gpt-4", "gpt-3.5-turbo"],
  "default_model": "gpt-4",
  "created_at": "2025-01-08T15:30:00Z",
  "updated_at": null,
  "error_count": 0,
  "last_error": null
}
```

**Response** (Error - 400 Bad Request):
```json
{
  "detail": "OpenAI config requires 'api_key'"
}
```

**Field Validation**:
- `provider_type`: Must be one of: `"openai"`, `"anthropic"`, `"groq"`, `"bedrock"`
- `name`: Optional, max 255 characters
- `is_enabled`: Optional, default `true`
- `config.api_key`: Required for OpenAI/Anthropic/Groq, must not be empty
- `config.aws_region`: Required for Bedrock
- `config.max_retries`: Optional, 0-10
- `config.timeout`: Optional, 5-300 seconds

---

### 3. List Provider Configurations

```http
GET /v1/providers/configurations?provider_type=openai
```

**Purpose**: List all user's provider configurations

**Authentication**: Required (Bearer token)

**Query Parameters**:
- `provider_type` (optional): Filter by provider type

**Request**: None

**Response**:
```json
{
  "providers": [
    {
      "id": 123,
      "customer_id": "customer_abc123",
      "provider_type": "openai",
      "name": "My OpenAI Configuration",
      "is_enabled": true,
      "is_healthy": true,
      "last_health_check": "2025-01-08T15:35:00Z",
      "config_summary": {
        "available_models": ["gpt-4", "gpt-3.5-turbo"],
        "default_model": "gpt-4"
      },
      "available_models": ["gpt-4", "gpt-3.5-turbo"],
      "default_model": "gpt-4",
      "created_at": "2025-01-08T15:30:00Z",
      "updated_at": "2025-01-08T15:35:00Z",
      "error_count": 0,
      "last_error": null
    },
    {
      "id": 124,
      "customer_id": "customer_abc123",
      "provider_type": "anthropic",
      "name": "My Claude Configuration",
      "is_enabled": true,
      "is_healthy": true,
      "last_health_check": "2025-01-08T15:36:00Z",
      "config_summary": {
        "available_models": ["claude-3-opus-20240229"],
        "default_model": "claude-3-opus-20240229"
      },
      "available_models": ["claude-3-opus-20240229"],
      "default_model": "claude-3-opus-20240229",
      "created_at": "2025-01-08T15:32:00Z",
      "updated_at": "2025-01-08T15:36:00Z",
      "error_count": 0,
      "last_error": null
    }
  ],
  "total_count": 2,
  "by_type": {
    "openai": 1,
    "anthropic": 1
  }
}
```

**UI Usage**: Display all configured providers in a list/table

---

### 4. Get Provider Configuration

```http
GET /v1/providers/configurations/{id}
```

**Purpose**: Get details of a specific configuration

**Authentication**: Required (Bearer token)

**Path Parameters**:
- `id`: Configuration ID (integer)

**Response**: Same as create response

**Response** (Error - 404 Not Found):
```json
{
  "detail": "Provider configuration 999 not found"
}
```

---

### 5. Update Provider Configuration

```http
PUT /v1/providers/configurations/{id}
Content-Type: application/json
```

**Purpose**: Update an existing configuration

**Authentication**: Required (Bearer token)

**Path Parameters**:
- `id`: Configuration ID (integer)

**Request Body** (Partial Update):
```json
{
  "is_enabled": false
}
```

**Request Body** (Update API Key):
```json
{
  "config": {
    "api_key": "sk-new-api-key-here"
  }
}
```

**Request Body** (Update Models):
```json
{
  "config": {
    "available_models": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo-preview"],
    "default_model": "gpt-4-turbo-preview"
  }
}
```

**Response**: Updated configuration object

**Notes**:
- Only provided fields are updated
- Updating `config.api_key` triggers re-encryption
- Health status is NOT automatically updated (use test endpoint)

---

### 6. Delete Provider Configuration

```http
DELETE /v1/providers/configurations/{id}
```

**Purpose**: Delete a provider configuration

**Authentication**: Required (Bearer token)

**Path Parameters**:
- `id`: Configuration ID (integer)

**Response** (Success - 204 No Content): Empty body

**Response** (Error - 404 Not Found):
```json
{
  "detail": "Provider configuration 999 not found"
}
```

**Warning**: This is permanent! Consider adding a confirmation dialog in UI.

---

### 7. Test Provider Connection

```http
POST /v1/providers/configurations/{id}/test
Content-Type: application/json
```

**Purpose**: Test if the provider configuration works

**Authentication**: Required (Bearer token)

**Path Parameters**:
- `id`: Configuration ID (integer)

**Request Body** (Optional):
```json
{
  "test_prompt": "Hello, please respond to confirm you're working."
}
```

**Response** (Success):
```json
{
  "success": true,
  "provider_type": "openai",
  "message": "openai connection successful",
  "response_time_ms": 234.5,
  "test_output": "Hello! I'm working correctly. This is a test response from GPT-4.",
  "model_tested": "gpt-3.5-turbo",
  "tested_at": "2025-01-08T15:40:00Z"
}
```

**Response** (Failure):
```json
{
  "success": false,
  "provider_type": "openai",
  "message": "openai connection failed",
  "response_time_ms": null,
  "test_output": null,
  "error_details": "Incorrect API key provided. You can find your API key at https://platform.openai.com/account/api-keys.",
  "model_tested": null,
  "tested_at": "2025-01-08T15:40:00Z"
}
```

**UI Usage**: 
- Show "Test Connection" button on config forms
- Display loading state during test
- Show success/error message with details

---

## Common Workflows

### Workflow 1: Create New Provider Configuration

```typescript
async function createProviderConfig(
  providerType: ProviderType,
  apiKey: string,
  models: string[],
  defaultModel: string
) {
  const response = await fetch('/v1/providers/configurations', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${authToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      provider_type: providerType,
      name: `My ${providerType} Configuration`,
      is_enabled: true,
      config: {
        api_key: apiKey,
        available_models: models,
        default_model: defaultModel
      }
    })
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }
  
  return await response.json();
}

// Usage
const config = await createProviderConfig(
  'openai',
  'sk-...',
  ['gpt-4', 'gpt-3.5-turbo'],
  'gpt-4'
);
```

### Workflow 2: Test Configuration Before Saving

```typescript
async function testAndCreateConfig(providerData) {
  // 1. Create configuration
  const config = await createProviderConfig(providerData);
  
  // 2. Immediately test it
  const testResult = await fetch(
    `/v1/providers/configurations/${config.id}/test`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        test_prompt: "Test connection"
      })
    }
  );
  
  const result = await testResult.json();
  
  if (!result.success) {
    // Test failed - optionally delete config or show warning
    alert(`Warning: ${result.error_details}`);
  }
  
  return { config, testResult: result };
}
```

### Workflow 3: Update API Key

```typescript
async function updateAPIKey(configId: number, newApiKey: string) {
  const response = await fetch(
    `/v1/providers/configurations/${configId}`,
    {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        config: {
          api_key: newApiKey
        }
      })
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to update API key');
  }
  
  // Test new key
  const testResponse = await fetch(
    `/v1/providers/configurations/${configId}/test`,
    { method: 'POST', headers: { 'Authorization': `Bearer ${authToken}` } }
  );
  
  const testResult = await testResponse.json();
  
  return testResult.success;
}
```

### Workflow 4: Enable/Disable Provider

```typescript
async function toggleProvider(configId: number, enabled: boolean) {
  const response = await fetch(
    `/v1/providers/configurations/${configId}`,
    {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        is_enabled: enabled
      })
    }
  );
  
  return await response.json();
}
```

---

## UI/UX Guidelines

### Provider Configuration Form

**Recommended Form Fields**:

```tsx
// OpenAI Form
<Form>
  <Input 
    label="Configuration Name" 
    placeholder="My OpenAI Configuration"
    optional
  />
  
  <Input 
    label="API Key" 
    type="password"
    placeholder="sk-..."
    required
    helpText="Get your API key from https://platform.openai.com/api-keys"
  />
  
  <Input 
    label="Organization ID"
    placeholder="org-..."
    optional
    helpText="Optional. Find this in your OpenAI account settings."
  />
  
  <MultiSelect
    label="Available Models"
    options={['gpt-4', 'gpt-4-turbo-preview', 'gpt-3.5-turbo']}
    defaultValue={['gpt-4', 'gpt-3.5-turbo']}
  />
  
  <Select
    label="Default Model"
    options={selectedModels}
    required
  />
  
  <Toggle
    label="Enable this configuration"
    defaultValue={true}
  />
  
  <Button onClick={testConnection}>Test Connection</Button>
  <Button type="submit">Save Configuration</Button>
</Form>
```

### Configuration List View

**Recommended Display**:

```tsx
<ConfigurationCard>
  <Badge color={config.is_healthy ? 'green' : 'red'}>
    {config.is_healthy ? 'Healthy' : 'Error'}
  </Badge>
  
  <Title>{config.provider_type.toUpperCase()}</Title>
  <Subtitle>{config.name || 'Unnamed Configuration'}</Subtitle>
  
  <MetadataRow>
    <Label>Default Model:</Label>
    <Value>{config.default_model || 'Not set'}</Value>
  </MetadataRow>
  
  <MetadataRow>
    <Label>Available Models:</Label>
    <Value>{config.available_models.length} models</Value>
  </MetadataRow>
  
  <MetadataRow>
    <Label>Created:</Label>
    <Value>{formatDate(config.created_at)}</Value>
  </MetadataRow>
  
  {config.last_error && (
    <ErrorBanner>{config.last_error}</ErrorBanner>
  )}
  
  <Actions>
    <Button onClick={() => testConfig(config.id)}>Test</Button>
    <Button onClick={() => editConfig(config.id)}>Edit</Button>
    <Button variant="danger" onClick={() => deleteConfig(config.id)}>
      Delete
    </Button>
  </Actions>
</ConfigurationCard>
```

### Health Status Indicators

```typescript
function getHealthStatusColor(config: ProviderConfiguration) {
  if (!config.is_healthy && config.error_count > 0) {
    return 'red';    // Error state
  }
  if (config.is_healthy && config.last_health_check) {
    return 'green';  // Healthy
  }
  return 'gray';     // Not tested yet
}

function getHealthStatusText(config: ProviderConfiguration) {
  if (!config.is_healthy && config.error_count > 0) {
    return `Error (${config.error_count} failures)`;
  }
  if (config.is_healthy && config.last_health_check) {
    return `Healthy (tested ${formatTimeAgo(config.last_health_check)})`;
  }
  return 'Not tested';
}
```

---

## Error Handling

### Common Error Responses

**400 Bad Request** - Validation Error
```json
{
  "detail": "OpenAI config requires 'api_key'"
}
```

**401 Unauthorized** - Authentication Failed
```json
{
  "detail": "Could not validate credentials"
}
```

**404 Not Found** - Configuration Doesn't Exist
```json
{
  "detail": "Provider configuration 123 not found"
}
```

**500 Internal Server Error** - Server Error
```json
{
  "detail": "Failed to create provider configuration: Database connection error"
}
```

### Error Handling Pattern

```typescript
async function handleProviderAPI<T>(
  apiCall: () => Promise<Response>
): Promise<T> {
  try {
    const response = await apiCall();
    
    if (!response.ok) {
      const error = await response.json();
      
      switch (response.status) {
        case 400:
          throw new Error(`Validation Error: ${error.detail}`);
        case 401:
          throw new Error('Authentication failed. Please log in again.');
        case 404:
          throw new Error('Configuration not found. It may have been deleted.');
        case 500:
          throw new Error('Server error. Please try again later.');
        default:
          throw new Error(`Unexpected error: ${error.detail}`);
      }
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('Network error. Please check your connection.');
    }
    throw error;
  }
}

// Usage
try {
  const config = await handleProviderAPI(() =>
    fetch('/v1/providers/configurations', { ... })
  );
} catch (error) {
  showErrorToast(error.message);
}
```

---

## Code Examples

### Complete React Component

```tsx
import React, { useState, useEffect } from 'react';

interface ProviderConfigFormProps {
  onSave: (config: ProviderConfiguration) => void;
}

export function OpenAIConfigForm({ onSave }: ProviderConfigFormProps) {
  const [apiKey, setApiKey] = useState('');
  const [orgId, setOrgId] = useState('');
  const [models, setModels] = useState(['gpt-4', 'gpt-3.5-turbo']);
  const [defaultModel, setDefaultModel] = useState('gpt-4');
  const [isEnabled, setIsEnabled] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResponse | null>(null);

  const handleTest = async () => {
    // Create temporary config
    const tempConfig = await createConfig();
    
    // Test it
    const result = await fetch(
      `/v1/providers/configurations/${tempConfig.id}/test`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    setTestResult(await result.json());
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      const response = await fetch('/v1/providers/configurations', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          provider_type: 'openai',
          name: 'My OpenAI Configuration',
          is_enabled: isEnabled,
          config: {
            api_key: apiKey,
            organization_id: orgId || undefined,
            available_models: models,
            default_model: defaultModel
          }
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail);
      }
      
      const config = await response.json();
      onSave(config);
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label>API Key *</label>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="sk-..."
          required
        />
        <small>Get your API key from https://platform.openai.com/api-keys</small>
      </div>

      <div>
        <label>Organization ID</label>
        <input
          type="text"
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
          placeholder="org-..."
        />
      </div>

      <div>
        <label>Default Model *</label>
        <select
          value={defaultModel}
          onChange={(e) => setDefaultModel(e.target.value)}
          required
        >
          {models.map(model => (
            <option key={model} value={model}>{model}</option>
          ))}
        </select>
      </div>

      <div>
        <label>
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(e) => setIsEnabled(e.target.checked)}
          />
          Enable this configuration
        </label>
      </div>

      {testResult && (
        <div className={testResult.success ? 'success' : 'error'}>
          <strong>{testResult.message}</strong>
          {testResult.error_details && <p>{testResult.error_details}</p>}
          {testResult.test_output && <p>{testResult.test_output}</p>}
        </div>
      )}

      <button type="button" onClick={handleTest} disabled={!apiKey}>
        Test Connection
      </button>
      
      <button type="submit" disabled={isLoading || !apiKey}>
        {isLoading ? 'Saving...' : 'Save Configuration'}
      </button>
    </form>
  );
}
```

---

## Security Notes for Frontend

### Do NOT Store API Keys in Frontend

❌ **NEVER** store API keys in:
- Local storage
- Session storage
- Browser cookies (unless httpOnly)
- Application state (longer than needed)

✅ **ALWAYS**:
- Send API keys directly to backend
- Clear form fields after submission
- Use `type="password"` for API key inputs
- Warn users about API key security

### API Key Input Best Practices

```tsx
<Input
  type="password"
  autoComplete="off"
  data-lpignore="true"  // Disable LastPass
  data-form-type="other"  // Disable browser password managers
  placeholder="sk-..."
  required
/>

<Warning>
  ⚠️ Never share your API key with anyone. We encrypt it securely.
</Warning>
```

---

## Testing Your Implementation

### Manual Test Checklist

- [ ] Can create OpenAI configuration
- [ ] Can create Anthropic configuration
- [ ] Can create Groq configuration
- [ ] Can create Bedrock configuration (API keys)
- [ ] Can create Bedrock configuration (IAM role)
- [ ] Can list all configurations
- [ ] Can filter configurations by provider type
- [ ] Can update configuration
- [ ] Can enable/disable configuration
- [ ] Can test connection (success case)
- [ ] Can test connection (failure case)
- [ ] Can delete configuration
- [ ] Error messages display correctly
- [ ] Health status badges display correctly
- [ ] API key input is masked
- [ ] Form validation works
- [ ] Loading states display

---

## Questions?

For backend implementation details, see:
- `design_docs/UNIFIED_PROVIDER_SYSTEM.md`
- `PROVIDER_REFACTOR_SUMMARY.md`

For API testing:
- OpenAPI docs: `http://localhost:5001/docs`
- Swagger UI: `http://localhost:5001/docs`

