# MCP Server Integration Guide

This guide provides specific recommendations for building an MCP (Model Context Protocol) server to interact with the Eliza Platform API.

## Overview

The Eliza Platform provides a comprehensive REST API for AI-powered business intelligence and talent analysis. This guide will help you integrate it with an MCP server to enable LLM-powered interactions.

## MCP Server Architecture

```
┌─────────────────────────────────────────────────┐
│           LLM (Claude, GPT, etc.)               │
└────────────────┬────────────────────────────────┘
                 │ MCP Protocol
┌────────────────▼────────────────────────────────┐
│              MCP Server                         │
│  ┌──────────────────────────────────────────┐  │
│  │    Authentication Handler                │  │
│  │  - Token management                      │  │
│  │  - Token refresh                         │  │
│  │  - Session handling                      │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │    Resource Handlers                     │  │
│  │  - Business Intelligence                 │  │
│  │  - Talent Analysis                       │  │
│  │  - Document Management                   │  │
│  │  - Search & Discovery                    │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │    Tool Implementations                  │  │
│  │  - ask_business_question()               │  │
│  │  - analyze_talent_pool()                 │  │
│  │  - search_documents()                    │  │
│  │  - find_candidates()                     │  │
│  └──────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────┘
                 │ HTTPS REST API
┌────────────────▼────────────────────────────────┐
│           Eliza Platform API                    │
│         http://localhost:5001                   │
└─────────────────────────────────────────────────┘
```

## Recommended MCP Tools

### 1. Business Intelligence Tools

#### `ask_business_question`
Ask natural language questions about business data.

**Input Schema:**
```typescript
{
  question: string;        // Required: Natural language question
  company?: string;        // Optional: Company to query (defaults to system default)
  wait_for_result?: boolean; // Optional: Wait for completion or return immediately
}
```

**Implementation:**
```typescript
async function ask_business_question(params: {
  question: string;
  company?: string;
  wait_for_result?: boolean;
}) {
  // 1. Submit question
  const response = await fetch(`${API_BASE}/api/v1/bi/questions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      question: params.question,
      company_hr_dataset: params.company || undefined
    })
  });
  
  const { question_id } = await response.json();
  
  if (!params.wait_for_result) {
    return {
      question_id,
      status: 'submitted',
      message: 'Question submitted. Use get_question_status to check progress.'
    };
  }
  
  // 2. Poll for completion
  while (true) {
    const statusResponse = await fetch(
      `${API_BASE}/api/v1/bi/questions/${question_id}/status`,
      { headers: { 'Authorization': `Bearer ${accessToken}` }}
    );
    const status = await statusResponse.json();
    
    if (status.status === 'completed') {
      // 3. Get final result
      const resultResponse = await fetch(
        `${API_BASE}/api/v1/bi/questions/${question_id}/result`,
        { headers: { 'Authorization': `Bearer ${accessToken}` }}
      );
      return await resultResponse.json();
    } else if (status.status === 'failed') {
      throw new Error(status.error_message || 'Analysis failed');
    }
    
    await new Promise(resolve => setTimeout(resolve, 2000)); // Poll every 2s
  }
}
```

**Returns:**
```typescript
{
  answer: string;           // Natural language answer
  confidence: number;       // 0-1 confidence score
  data_sources: string[];   // Sources used
  visualizations?: any[];   // Charts/graphs data
  recommendations?: string[]; // Action items
}
```

---

#### `get_question_status`
Check status of a submitted question.

**Input Schema:**
```typescript
{
  question_id: string;
}
```

**Returns:**
```typescript
{
  question_id: string;
  status: 'pending' | 'enriching' | 'analyzing' | 'completed' | 'failed';
  progress_percentage: number;
  current_stage: string;
  error_message?: string;
}
```

---

#### `list_questions`
List recent business intelligence questions.

**Input Schema:**
```typescript
{
  page?: number;
  page_size?: number;
  status?: string;
}
```

**Returns:**
```typescript
{
  questions: Array<{
    question_id: string;
    original_question: string;
    status: string;
    created_at: string;
    completed_at?: string;
  }>;
  total: number;
  page: number;
  pages: number;
}
```

---

### 2. Talent Intelligence Tools

#### `analyze_talent_pool`
Analyze a pool of candidates for a role.

**Input Schema:**
```typescript
{
  job_description: string;      // Required
  ideal_candidate: string;       // Required
  connector_id: string;          // Required: Where to get resumes
  role?: string;                 // Optional: Role name
  wait_for_result?: boolean;     // Optional
}
```

**Implementation:**
```typescript
async function analyze_talent_pool(params: {
  job_description: string;
  ideal_candidate: string;
  connector_id: string;
  role?: string;
  wait_for_result?: boolean;
}) {
  // Submit analysis
  const response = await fetch(
    `${API_BASE}/api/v1/ml-talent/analyze-from-connector`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        job_description: params.job_description,
        ideal_candidate_description: params.ideal_candidate,
        data_source_connector_id: params.connector_id,
        role: params.role || 'Machine Learning Engineer'
      })
    }
  );
  
  const { analysis_id } = await response.json();
  
  if (!params.wait_for_result) {
    return { analysis_id, status: 'submitted' };
  }
  
  // Poll for completion
  while (true) {
    const statusResponse = await fetch(
      `${API_BASE}/api/v1/ml-talent/analysis/${analysis_id}/status`,
      { headers: { 'Authorization': `Bearer ${accessToken}` }}
    );
    const status = await statusResponse.json();
    
    if (status.status === 'completed') {
      const resultResponse = await fetch(
        `${API_BASE}/api/v1/ml-talent/analysis/${analysis_id}`,
        { headers: { 'Authorization': `Bearer ${accessToken}` }}
      );
      return await resultResponse.json();
    } else if (status.status === 'failed') {
      throw new Error(status.message || 'Analysis failed');
    }
    
    await new Promise(resolve => setTimeout(resolve, 5000)); // Poll every 5s
  }
}
```

**Returns:**
```typescript
{
  analysis_id: string;
  status: string;
  top_overall: Array<{
    candidate_id: string;
    full_name: string;
    overall_score: number;
    dimensions: Array<{
      name: string;
      score: number;
      rationale: string;
    }>;
  }>;
  synthesis: {
    executive_summary: string;
    recommendations: string[];
  };
}
```

---

#### `list_talent_analyses`
List recent talent analyses.

**Input Schema:**
```typescript
{
  page?: number;
  page_size?: number;
  status?: string;
}
```

---

### 3. Document Tools

#### `search_documents`
Semantic search across uploaded documents.

**Input Schema:**
```typescript
{
  query: string;              // Required: Search query
  limit?: number;             // Optional: Max results (default 10)
  similarity_threshold?: number; // Optional: 0-1 (default 0.7)
  source_ids?: string[];      // Optional: Filter by sources
}
```

**Implementation:**
```typescript
async function search_documents(params: {
  query: string;
  limit?: number;
  similarity_threshold?: number;
  source_ids?: string[];
}) {
  const response = await fetch(
    `${API_BASE}/api/v1/documents/search`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        query: params.query,
        limit: params.limit || 10,
        similarity_threshold: params.similarity_threshold || 0.7,
        source_ids: params.source_ids
      })
    }
  );
  
  return await response.json();
}
```

**Returns:**
```typescript
{
  results: Array<{
    document_filename: string;
    text: string;             // Chunk text
    similarity_score: number;
    section_title?: string;
    page_number?: number;
  }>;
  total: number;
}
```

---

#### `upload_documents`
Upload documents for processing.

**Input Schema:**
```typescript
{
  file_paths: string[];     // Paths to files
  company?: string;         // Company to associate with
  chunking_strategy?: 'semantic' | 'fixed_size' | 'sliding_window';
}
```

---

#### `list_documents`
List uploaded documents with filtering.

**Input Schema:**
```typescript
{
  status?: 'uploaded' | 'processing' | 'completed' | 'failed';
  company?: string;
  limit?: number;
  offset?: number;
}
```

---

### 4. Search & Discovery Tools

#### `find_candidates`
Search for candidates with specific criteria.

**Input Schema:**
```typescript
{
  query: string;              // Search query
  skills?: string[];          // Required skills
  location?: string;          // Location filter
  experience_years_min?: number;
  limit?: number;
}
```

**Implementation:**
```typescript
async function find_candidates(params: {
  query: string;
  skills?: string[];
  location?: string;
  experience_years_min?: number;
  limit?: number;
}) {
  const response = await fetch(`${API_BASE}/search/persons`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      query: params.query,
      filters: {
        skills: params.skills,
        location_country: params.location,
        experience_years_min: params.experience_years_min
      },
      size: params.limit || 20
    })
  });
  
  return await response.json();
}
```

---

#### `find_skill_cooccurrence`
Find skills that commonly occur together.

**Input Schema:**
```typescript
{
  skill: string;
  top_n?: number;
}
```

---

#### `analyze_career_transitions`
Find people who moved between companies.

**Input Schema:**
```typescript
{
  from_company: string;
  to_company: string;
  limit?: number;
}
```

---

### 5. Connector Tools

#### `list_connectors`
List available data connectors.

**Returns:**
```typescript
{
  connectors: Array<{
    connector_id: string;
    connector_name: string;
    connector_type: string;
    is_enabled: boolean;
  }>;
}
```

---

#### `trigger_connector_sync`
Manually trigger a connector sync.

**Input Schema:**
```typescript
{
  connector_id: string;
}
```

---

## Authentication Implementation

### Token Management

```typescript
class AuthManager {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private tokenExpiry: number = 0;
  
  constructor(
    private apiBase: string,
    private email: string,
    private password: string
  ) {}
  
  async initialize() {
    await this.login();
  }
  
  async login() {
    const response = await fetch(`${this.apiBase}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: this.email,
        password: this.password
      })
    });
    
    if (!response.ok) {
      throw new Error('Login failed');
    }
    
    const data = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    this.tokenExpiry = Date.now() + (data.expires_in * 1000);
  }
  
  async refreshAccessToken() {
    if (!this.refreshToken) {
      await this.login();
      return;
    }
    
    const response = await fetch(`${this.apiBase}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        refresh_token: this.refreshToken
      })
    });
    
    if (!response.ok) {
      await this.login();
      return;
    }
    
    const data = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    this.tokenExpiry = Date.now() + (data.expires_in * 1000);
  }
  
  async getAccessToken(): Promise<string> {
    // Refresh if token expires in next 5 minutes
    if (Date.now() >= this.tokenExpiry - (5 * 60 * 1000)) {
      await this.refreshAccessToken();
    }
    
    if (!this.accessToken) {
      await this.login();
    }
    
    return this.accessToken!;
  }
  
  async makeRequest(
    method: string,
    path: string,
    body?: any
  ): Promise<Response> {
    const token = await this.getAccessToken();
    
    const response = await fetch(`${this.apiBase}${path}`, {
      method,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: body ? JSON.stringify(body) : undefined
    });
    
    // Handle 401 by refreshing token and retrying once
    if (response.status === 401) {
      await this.refreshAccessToken();
      const token = await this.getAccessToken();
      
      return fetch(`${this.apiBase}${path}`, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: body ? JSON.stringify(body) : undefined
      });
    }
    
    return response;
  }
}
```

---

## Error Handling

### Standard Error Response

```typescript
interface APIError {
  detail: string;
  status_code: number;
}

async function handleAPIError(response: Response) {
  if (!response.ok) {
    const error: APIError = await response.json();
    
    switch (error.status_code) {
      case 400:
        throw new Error(`Bad Request: ${error.detail}`);
      case 401:
        throw new Error('Unauthorized. Please check credentials.');
      case 403:
        throw new Error(`Permission Denied: ${error.detail}`);
      case 404:
        throw new Error(`Not Found: ${error.detail}`);
      case 422:
        throw new Error(`Validation Error: ${error.detail}`);
      case 500:
        throw new Error('Internal Server Error. Please try again later.');
      case 503:
        throw new Error('Service Unavailable. Workers may be down.');
      default:
        throw new Error(`API Error (${error.status_code}): ${error.detail}`);
    }
  }
}
```

---

## Rate Limiting & Retries

```typescript
async function makeRequestWithRetry(
  requestFn: () => Promise<Response>,
  maxRetries = 3,
  backoffMs = 1000
): Promise<Response> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await requestFn();
      
      // Success or client error (don't retry)
      if (response.ok || response.status < 500) {
        return response;
      }
      
      // Server error - retry with exponential backoff
      if (i < maxRetries - 1) {
        await new Promise(resolve => 
          setTimeout(resolve, backoffMs * Math.pow(2, i))
        );
        continue;
      }
      
      return response;
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      
      await new Promise(resolve => 
        setTimeout(resolve, backoffMs * Math.pow(2, i))
      );
    }
  }
  
  throw new Error('Max retries exceeded');
}
```

---

## Configuration

### Environment Variables

```bash
# .env
ELIZA_API_BASE=http://localhost:5001
ELIZA_API_EMAIL=your_email@example.com
ELIZA_API_PASSWORD=your_password

# Optional
ELIZA_API_TIMEOUT_MS=30000
ELIZA_API_MAX_RETRIES=3
ELIZA_API_DEFAULT_COMPANY=caylent
```

---

## Testing

### Example Test Suite

```typescript
import { describe, it, expect, beforeAll } from '@jest/globals';

describe('Eliza API Integration', () => {
  let authManager: AuthManager;
  
  beforeAll(async () => {
    authManager = new AuthManager(
      process.env.ELIZA_API_BASE!,
      process.env.ELIZA_API_EMAIL!,
      process.env.ELIZA_API_PASSWORD!
    );
    await authManager.initialize();
  });
  
  it('should ask a business question', async () => {
    const result = await ask_business_question({
      question: 'What are the top 5 skills?',
      wait_for_result: true
    });
    
    expect(result).toHaveProperty('answer');
    expect(result.confidence).toBeGreaterThan(0.5);
  });
  
  it('should search documents', async () => {
    const result = await search_documents({
      query: 'employee benefits',
      limit: 5
    });
    
    expect(result.results).toBeInstanceOf(Array);
    expect(result.results.length).toBeLessThanOrEqual(5);
  });
  
  it('should find candidates', async () => {
    const result = await find_candidates({
      query: 'python engineer',
      skills: ['python'],
      limit: 10
    });
    
    expect(result.hits).toBeInstanceOf(Array);
    expect(result.hits.length).toBeLessThanOrEqual(10);
  });
});
```

---

## Best Practices

### 1. Caching
Cache frequently accessed data to reduce API calls:
- Connector lists
- Document stats
- Aggregation results

### 2. Batch Operations
Group related operations when possible to reduce round trips.

### 3. Async Operations
Use background task patterns for long-running operations:
- Business intelligence questions
- Talent analyses
- Document uploads

### 4. Error Recovery
Implement robust error handling:
- Retry transient failures
- Fall back to cached data
- Provide meaningful error messages

### 5. Resource Cleanup
Always clean up resources:
- Close SSE connections
- Cancel in-progress operations when no longer needed

### 6. Security
- Store credentials securely (not in code)
- Use environment variables
- Implement token rotation
- Log security events

---

## Complete MCP Server Example

See the full implementation example in the repository:
- `examples/mcp-server/` - Complete MCP server implementation
- `examples/mcp-server/README.md` - Setup and usage guide
- `examples/mcp-server/tools/` - Individual tool implementations

---

## Support

For questions or issues:
- **API Documentation**: `/docs/api/`
- **GitHub Issues**: https://github.com/your-org/eliza-platform/issues
- **Email**: support@eliza-platform.com


