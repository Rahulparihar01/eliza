# AI Enablement Platform API Design Specification

## Executive Summary

This document defines the comprehensive REST API design for the AI Enablement Platform, serving as the single entry point for all backend systems and processes. The API is designed to be used by both the frontend application and any CLI/SDK implementations, providing a unified interface for data ingestion, AI analysis, user task enrichment, and system management.

**Key Design Principles:**
- **Single Entry Point**: All backend functionality accessible through unified API
- **RESTful Design**: Standard HTTP methods and status codes
- **OpenAPI Compatible**: Full OpenAPI 3.0 specification for documentation and code generation
- **Secure by Default**: Comprehensive authentication and authorization
- **Developer Friendly**: Clear, consistent patterns and excellent error handling
- **Scalable Architecture**: Designed for high throughput and horizontal scaling

---

## 1. API Architecture Overview

### 1.1 Base URL Structure

```
Production:  https://api.ai-enablement.com/v1
Staging:     https://staging-api.ai-enablement.com/v1
Development: http://localhost:5001/v1
```

### 1.2 API Versioning Strategy

```
/v1/     - Current stable API version
/v2/     - Next major version (when available)
/beta/   - Beta features and experimental endpoints
/alpha/  - Alpha features for early testing
```

### 1.3 Core API Groups

```
Authentication & Users:
├── /auth                    # Authentication endpoints
├── /users                   # User management
└── /organizations          # Organization management

Data Management:
├── /data-sources           # Data source management
├── /documents              # Document upload and management
├── /ingestion              # Data ingestion pipeline
└── /knowledge              # Knowledge base queries

AI Processing:
├── /enrichment             # User task enrichment
├── /analysis               # AI analysis workflows
├── /agents                 # CrewAI agent management
└── /completions            # OpenAI-compatible completions

System Management:
├── /models                 # Model configuration
├── /api-keys               # API key management
├── /logs                   # Logging and monitoring
├── /health                 # Health checks
└── /metrics                # System metrics
```

---

## 2. Authentication & Authorization

### 2.1 Authentication Methods

```python
# From authentication patterns - EXAMPLE
from typing import Dict, Any, Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

security = HTTPBearer()

class AuthenticationSchemes:
    """Supported authentication schemes"""
    
    # API Key Authentication
    API_KEY = "api_key"          # Format: "Bearer aiplatform_..."
    
    # JWT Token Authentication  
    JWT_TOKEN = "jwt"            # Format: "Bearer eyJ..."
    
    # OAuth 2.0 (Future)
    OAUTH2 = "oauth2"           # Standard OAuth 2.0 flows

# API Key Format
API_KEY_PREFIX = "aiplatform_"
API_KEY_LENGTH = 64

# JWT Configuration
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
JWT_REFRESH_EXPIRATION_DAYS = 30
```

### 2.2 Authentication Endpoints

```yaml
# Authentication API Endpoints
POST /v1/auth/login:
  summary: "Authenticate user with email/password"
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            email:
              type: string
              format: email
            password:
              type: string
              minLength: 8
            remember_me:
              type: boolean
              default: false
  responses:
    200:
      description: "Authentication successful"
      content:
        application/json:
          schema:
            type: object
            properties:
              access_token:
                type: string
                description: "JWT access token"
              refresh_token:
                type: string
                description: "JWT refresh token"
              token_type:
                type: string
                enum: ["bearer"]
              expires_in:
                type: integer
                description: "Token expiration in seconds"
              user:
                $ref: "#/components/schemas/User"

POST /v1/auth/refresh:
  summary: "Refresh access token using refresh token"
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            refresh_token:
              type: string
  responses:
    200:
      description: "Token refreshed successfully"
      content:
        application/json:
          schema:
            type: object
            properties:
              access_token:
                type: string
              expires_in:
                type: integer

POST /v1/auth/logout:
  summary: "Logout and invalidate tokens"
  security:
    - bearerAuth: []
  responses:
    200:
      description: "Logout successful"

POST /v1/auth/api-keys:
  summary: "Generate new API key"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            name:
              type: string
              description: "Human-readable name for the API key"
            permissions:
              type: array
              items:
                type: string
              description: "List of permissions for this API key"
            expires_at:
              type: string
              format: date-time
              description: "Optional expiration date"
  responses:
    201:
      description: "API key created successfully"
      content:
        application/json:
          schema:
            type: object
            properties:
              api_key:
                type: string
                description: "The generated API key (only shown once)"
              key_id:
                type: string
                description: "Unique identifier for the key"
              name:
                type: string
              permissions:
                type: array
                items:
                  type: string
              created_at:
                type: string
                format: date-time
              expires_at:
                type: string
                format: date-time

GET /v1/auth/api-keys:
  summary: "List user's API keys"
  security:
    - bearerAuth: []
  responses:
    200:
      description: "API keys retrieved successfully"
      content:
        application/json:
          schema:
            type: object
            properties:
              api_keys:
                type: array
                items:
                  type: object
                  properties:
                    key_id:
                      type: string
                    name:
                      type: string
                    permissions:
                      type: array
                      items:
                        type: string
                    created_at:
                      type: string
                      format: date-time
                    last_used:
                      type: string
                      format: date-time
                    expires_at:
                      type: string
                      format: date-time
                    status:
                      type: string
                      enum: ["active", "inactive", "expired"]

DELETE /v1/auth/api-keys/{key_id}:
  summary: "Revoke API key"
  security:
    - bearerAuth: []
  parameters:
    - name: key_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "API key revoked successfully"
```

### 2.3 Authorization Model

```python
# From authorization patterns - EXAMPLE
from enum import Enum
from typing import List, Set

class Permission(Enum):
    """System permissions"""
    
    # Data Management
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    DATA_DELETE = "data:delete"
    
    # Document Management
    DOCUMENTS_UPLOAD = "documents:upload"
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_DELETE = "documents:delete"
    
    # AI Processing
    ANALYSIS_RUN = "analysis:run"
    ANALYSIS_READ = "analysis:read"
    ENRICHMENT_USE = "enrichment:use"
    
    # System Administration
    USERS_MANAGE = "users:manage"
    SYSTEM_CONFIGURE = "system:configure"
    LOGS_READ = "logs:read"
    METRICS_READ = "metrics:read"
    
    # API Keys
    API_KEYS_MANAGE = "api_keys:manage"

class Role(Enum):
    """User roles with associated permissions"""
    
    VIEWER = "viewer"
    ANALYST = "analyst" 
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

ROLE_PERMISSIONS = {
    Role.VIEWER: {
        Permission.DATA_READ,
        Permission.DOCUMENTS_READ,
        Permission.ANALYSIS_READ,
    },
    Role.ANALYST: {
        Permission.DATA_READ,
        Permission.DATA_WRITE,
        Permission.DOCUMENTS_UPLOAD,
        Permission.DOCUMENTS_READ,
        Permission.ANALYSIS_RUN,
        Permission.ANALYSIS_READ,
        Permission.ENRICHMENT_USE,
        Permission.API_KEYS_MANAGE,
    },
    Role.ADMIN: {
        # All analyst permissions plus:
        Permission.DATA_DELETE,
        Permission.DOCUMENTS_DELETE,
        Permission.USERS_MANAGE,
        Permission.LOGS_READ,
        Permission.METRICS_READ,
    },
    Role.SUPER_ADMIN: {
        # All permissions
        *[p for p in Permission]
    }
}

def check_permission(user_role: Role, required_permission: Permission) -> bool:
    """Check if user role has required permission"""
    user_permissions = ROLE_PERMISSIONS.get(user_role, set())
    return required_permission in user_permissions
```

---

## 3. Data Management APIs

### 3.1 Data Sources Management

```yaml
# Data Sources API Endpoints
GET /v1/data-sources:
  summary: "List all configured data sources"
  security:
    - bearerAuth: []
  parameters:
    - name: type
      in: query
      schema:
        type: string
        enum: ["hr", "crm", "financial", "linkedin", "documents", "research"]
    - name: status
      in: query
      schema:
        type: string
        enum: ["active", "inactive", "error"]
    - name: limit
      in: query
      schema:
        type: integer
        default: 50
        maximum: 100
    - name: offset
      in: query
      schema:
        type: integer
        default: 0
  responses:
    200:
      description: "Data sources retrieved successfully"
      content:
        application/json:
          schema:
            type: object
            properties:
              data_sources:
                type: array
                items:
                  $ref: "#/components/schemas/DataSource"
              total:
                type: integer
              limit:
                type: integer
              offset:
                type: integer

POST /v1/data-sources:
  summary: "Create new data source configuration"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            name:
              type: string
              description: "Human-readable name for the data source"
            type:
              type: string
              enum: ["hr", "crm", "financial", "linkedin", "documents", "research"]
            description:
              type: string
            configuration:
              type: object
              description: "Type-specific configuration parameters"
              properties:
                connection_string:
                  type: string
                  description: "Database connection string or API endpoint"
                credentials:
                  type: object
                  description: "Authentication credentials"
                sync_schedule:
                  type: string
                  description: "Cron expression for automatic sync"
                filters:
                  type: object
                  description: "Data filtering rules"
            chunking_config:
              $ref: "#/components/schemas/ChunkingConfig"
            qa_rag_enabled:
              type: boolean
              default: false
              description: "Enable Q&A generation for this source"
  responses:
    201:
      description: "Data source created successfully"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/DataSource"

GET /v1/data-sources/{source_id}:
  summary: "Get data source details"
  security:
    - bearerAuth: []
  parameters:
    - name: source_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "Data source details retrieved"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/DataSource"

PUT /v1/data-sources/{source_id}:
  summary: "Update data source configuration"
  security:
    - bearerAuth: []
  parameters:
    - name: source_id
      in: path
      required: true
      schema:
        type: string
  requestBody:
    required: true
    content:
      application/json:
        schema:
          $ref: "#/components/schemas/DataSourceUpdate"
  responses:
    200:
      description: "Data source updated successfully"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/DataSource"

DELETE /v1/data-sources/{source_id}:
  summary: "Delete data source"
  security:
    - bearerAuth: []
  parameters:
    - name: source_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "Data source deleted successfully"

POST /v1/data-sources/{source_id}/sync:
  summary: "Trigger manual sync for data source"
  security:
    - bearerAuth: []
  parameters:
    - name: source_id
      in: path
      required: true
      schema:
        type: string
  requestBody:
    required: false
    content:
      application/json:
        schema:
          type: object
          properties:
            full_sync:
              type: boolean
              default: false
              description: "Perform full sync instead of incremental"
            filters:
              type: object
              description: "Override default filters for this sync"
  responses:
    202:
      description: "Sync started successfully"
      content:
        application/json:
          schema:
            type: object
            properties:
              sync_id:
                type: string
                description: "Unique identifier for this sync operation"
              status:
                type: string
                enum: ["started"]
              estimated_duration:
                type: string
                description: "Estimated completion time"

GET /v1/data-sources/{source_id}/sync/{sync_id}:
  summary: "Get sync operation status"
  security:
    - bearerAuth: []
  parameters:
    - name: source_id
      in: path
      required: true
      schema:
        type: string
    - name: sync_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "Sync status retrieved"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/SyncOperation"
```

### 3.2 Document Management

```yaml
# Document Management API Endpoints
POST /v1/documents/upload:
  summary: "Upload documents for processing"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      multipart/form-data:
        schema:
          type: object
          properties:
            files:
              type: array
              items:
                type: string
                format: binary
              description: "Documents to upload (PDF, DOCX, TXT, etc.)"
            source_id:
              type: string
              description: "Associate with specific data source"
            metadata:
              type: string
              description: "JSON string with additional metadata"
            chunking_strategy:
              type: string
              enum: ["semantic", "fixed", "hierarchical", "adaptive", "hybrid"]
              default: "semantic"
            enable_qa_rag:
              type: boolean
              default: false
  responses:
    202:
      description: "Upload started successfully"
      content:
        application/json:
          schema:
            type: object
            properties:
              upload_id:
                type: string
                description: "Unique identifier for this upload batch"
              files:
                type: array
                items:
                  type: object
                  properties:
                    filename:
                      type: string
                    document_id:
                      type: string
                    status:
                      type: string
                      enum: ["uploaded", "processing", "completed", "failed"]
              total_files:
                type: integer
              estimated_processing_time:
                type: string

GET /v1/documents:
  summary: "List uploaded documents"
  security:
    - bearerAuth: []
  parameters:
    - name: source_id
      in: query
      schema:
        type: string
    - name: status
      in: query
      schema:
        type: string
        enum: ["processing", "completed", "failed"]
    - name: search
      in: query
      schema:
        type: string
        description: "Search in document names and content"
    - name: limit
      in: query
      schema:
        type: integer
        default: 50
    - name: offset
      in: query
      schema:
        type: integer
        default: 0
  responses:
    200:
      description: "Documents retrieved successfully"
      content:
        application/json:
          schema:
            type: object
            properties:
              documents:
                type: array
                items:
                  $ref: "#/components/schemas/Document"
              total:
                type: integer
              limit:
                type: integer
              offset:
                type: integer

GET /v1/documents/{document_id}:
  summary: "Get document details"
  security:
    - bearerAuth: []
  parameters:
    - name: document_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "Document details retrieved"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/DocumentDetails"

GET /v1/documents/{document_id}/chunks:
  summary: "Get document chunks"
  security:
    - bearerAuth: []
  parameters:
    - name: document_id
      in: path
      required: true
      schema:
        type: string
    - name: limit
      in: query
      schema:
        type: integer
        default: 50
    - name: offset
      in: query
      schema:
        type: integer
        default: 0
  responses:
    200:
      description: "Document chunks retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              chunks:
                type: array
                items:
                  $ref: "#/components/schemas/DocumentChunk"
              total:
                type: integer

GET /v1/documents/{document_id}/qa-pairs:
  summary: "Get Q&A pairs generated from document"
  security:
    - bearerAuth: []
  parameters:
    - name: document_id
      in: path
      required: true
      schema:
        type: string
    - name: quality_threshold
      in: query
      schema:
        type: number
        minimum: 0
        maximum: 1
        description: "Minimum quality score for returned pairs"
  responses:
    200:
      description: "Q&A pairs retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              qa_pairs:
                type: array
                items:
                  $ref: "#/components/schemas/QAPair"
              total:
                type: integer

DELETE /v1/documents/{document_id}:
  summary: "Delete document and associated data"
  security:
    - bearerAuth: []
  parameters:
    - name: document_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "Document deleted successfully"
```

### 3.3 Data Ingestion Pipeline

```yaml
# Data Ingestion API Endpoints
POST /v1/ingestion/start:
  summary: "Start data ingestion pipeline"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            sources:
              type: array
              items:
                type: string
              description: "List of data source IDs to process"
            pipeline_config:
              type: object
              properties:
                chunking_strategy:
                  type: string
                  enum: ["semantic", "fixed", "hierarchical", "adaptive", "hybrid"]
                enable_qa_rag:
                  type: boolean
                  default: false
                quality_threshold:
                  type: number
                  minimum: 0
                  maximum: 1
                  default: 0.7
                batch_size:
                  type: integer
                  default: 100
            priority:
              type: string
              enum: ["low", "normal", "high"]
              default: "normal"
  responses:
    202:
      description: "Ingestion pipeline started"
      content:
        application/json:
          schema:
            type: object
            properties:
              pipeline_id:
                type: string
              status:
                type: string
                enum: ["started"]
              estimated_duration:
                type: string

GET /v1/ingestion/{pipeline_id}:
  summary: "Get ingestion pipeline status"
  security:
    - bearerAuth: []
  parameters:
    - name: pipeline_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "Pipeline status retrieved"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/IngestionPipeline"

GET /v1/ingestion/{pipeline_id}/logs:
  summary: "Get ingestion pipeline logs"
  security:
    - bearerAuth: []
  parameters:
    - name: pipeline_id
      in: path
      required: true
      schema:
        type: string
    - name: level
      in: query
      schema:
        type: string
        enum: ["info", "warning", "error"]
    - name: limit
      in: query
      schema:
        type: integer
        default: 100
  responses:
    200:
      description: "Pipeline logs retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              logs:
                type: array
                items:
                  $ref: "#/components/schemas/LogEntry"

POST /v1/ingestion/{pipeline_id}/cancel:
  summary: "Cancel running ingestion pipeline"
  security:
    - bearerAuth: []
  parameters:
    - name: pipeline_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "Pipeline cancellation requested"
```

---

## 4. AI Processing APIs

### 4.1 User Task Enrichment

```yaml
# Task Enrichment API Endpoints
POST /v1/enrichment/analyze:
  summary: "Analyze and enrich user task"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            user_input:
              type: string
              description: "Raw user input to analyze and enrich"
            context:
              type: object
              description: "Additional context for enrichment"
              properties:
                domain:
                  type: string
                  description: "Business domain (e.g., 'sales', 'hr', 'finance')"
                user_role:
                  type: string
                  description: "User's role in organization"
                previous_tasks:
                  type: array
                  items:
                    type: string
                  description: "Previous related tasks for context"
            enrichment_options:
              type: object
              properties:
                include_examples:
                  type: boolean
                  default: true
                include_best_practices:
                  type: boolean
                  default: true
                complexity_level:
                  type: string
                  enum: ["basic", "intermediate", "advanced"]
                  default: "intermediate"
  responses:
    200:
      description: "Task analysis completed"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/TaskEnrichmentResult"

POST /v1/enrichment/batch:
  summary: "Batch process multiple tasks"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            tasks:
              type: array
              items:
                type: object
                properties:
                  task_id:
                    type: string
                  user_input:
                    type: string
                  context:
                    type: object
            enrichment_options:
              type: object
  responses:
    202:
      description: "Batch processing started"
      content:
        application/json:
          schema:
            type: object
            properties:
              batch_id:
                type: string
              status:
                type: string
                enum: ["processing"]
              total_tasks:
                type: integer

GET /v1/enrichment/batch/{batch_id}:
  summary: "Get batch processing status"
  security:
    - bearerAuth: []
  parameters:
    - name: batch_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "Batch status retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              batch_id:
                type: string
              status:
                type: string
                enum: ["processing", "completed", "failed"]
              completed_tasks:
                type: integer
              total_tasks:
                type: integer
              results:
                type: array
                items:
                  type: object
                  properties:
                    task_id:
                      type: string
                    status:
                      type: string
                    result:
                      $ref: "#/components/schemas/TaskEnrichmentResult"
```

### 4.2 AI Analysis Workflows

```yaml
# AI Analysis API Endpoints
POST /v1/analysis/department-readiness:
  summary: "Analyze department AI readiness"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            departments:
              type: array
              items:
                type: string
              description: "List of departments to analyze (empty for all)"
            analysis_depth:
              type: string
              enum: ["basic", "comprehensive", "detailed"]
              default: "comprehensive"
            include_roi_estimation:
              type: boolean
              default: true
            data_sources:
              type: array
              items:
                type: string
              description: "Data sources to include in analysis"
  responses:
    202:
      description: "Analysis started"
      content:
        application/json:
          schema:
            type: object
            properties:
              analysis_id:
                type: string
              status:
                type: string
                enum: ["started"]
              estimated_completion:
                type: string
                format: date-time

POST /v1/analysis/employee-matching:
  summary: "Match employees with AI tools based on personality"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            employee_ids:
              type: array
              items:
                type: string
              description: "Specific employees to analyze (empty for all)"
            personality_frameworks:
              type: array
              items:
                type: string
                enum: ["big_five", "disc", "mbti"]
              default: ["big_five"]
            available_tools:
              type: array
              items:
                type: string
              description: "AI tools to consider for matching"
            include_training_recommendations:
              type: boolean
              default: true
  responses:
    202:
      description: "Matching analysis started"
      content:
        application/json:
          schema:
            type: object
            properties:
              analysis_id:
                type: string
              status:
                type: string
                enum: ["started"]

POST /v1/analysis/roi-calculation:
  summary: "Calculate ROI for AI initiatives"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            initiatives:
              type: array
              items:
                type: object
                properties:
                  department:
                    type: string
                  proposed_tools:
                    type: array
                    items:
                      type: string
                  investment_amount:
                    type: number
                  timeline_months:
                    type: integer
            calculation_method:
              type: string
              enum: ["conservative", "realistic", "optimistic"]
              default: "realistic"
            include_risk_analysis:
              type: boolean
              default: true
  responses:
    202:
      description: "ROI calculation started"
      content:
        application/json:
          schema:
            type: object
            properties:
              analysis_id:
                type: string
              status:
                type: string
                enum: ["started"]

GET /v1/analysis/{analysis_id}:
  summary: "Get analysis results"
  security:
    - bearerAuth: []
  parameters:
    - name: analysis_id
      in: path
      required: true
      schema:
        type: string
  responses:
    200:
      description: "Analysis results retrieved"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/AnalysisResult"

GET /v1/analysis:
  summary: "List user's analyses"
  security:
    - bearerAuth: []
  parameters:
    - name: type
      in: query
      schema:
        type: string
        enum: ["department-readiness", "employee-matching", "roi-calculation"]
    - name: status
      in: query
      schema:
        type: string
        enum: ["running", "completed", "failed"]
    - name: limit
      in: query
      schema:
        type: integer
        default: 20
  responses:
    200:
      description: "Analyses retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              analyses:
                type: array
                items:
                  $ref: "#/components/schemas/AnalysisSummary"
```

### 4.3 OpenAI-Compatible Completions

```yaml
# OpenAI-Compatible API Endpoints
POST /v1/chat/completions:
  summary: "OpenAI-compatible chat completions"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            model:
              type: string
              description: "Model to use for completion"
              default: "ai-enablement-analyst"
            messages:
              type: array
              items:
                type: object
                properties:
                  role:
                    type: string
                    enum: ["system", "user", "assistant"]
                  content:
                    type: string
            temperature:
              type: number
              minimum: 0
              maximum: 2
              default: 0.7
            max_tokens:
              type: integer
              minimum: 1
              maximum: 4096
              default: 1024
            stream:
              type: boolean
              default: false
            tools:
              type: array
              items:
                type: object
              description: "Available tools for the model to use"
  responses:
    200:
      description: "Completion generated successfully"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ChatCompletion"

POST /v1/embeddings:
  summary: "Generate embeddings for text"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            input:
              oneOf:
                - type: string
                - type: array
                  items:
                    type: string
            model:
              type: string
              default: "text-embedding-3-small"
            encoding_format:
              type: string
              enum: ["float", "base64"]
              default: "float"
  responses:
    200:
      description: "Embeddings generated successfully"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/EmbeddingResponse"

GET /v1/models:
  summary: "List available models"
  security:
    - bearerAuth: []
  responses:
    200:
      description: "Models retrieved successfully"
      content:
        application/json:
          schema:
            type: object
            properties:
              object:
                type: string
                enum: ["list"]
              data:
                type: array
                items:
                  $ref: "#/components/schemas/Model"
```

---

## 5. Knowledge & Search APIs

### 5.1 Knowledge Base Queries

```yaml
# Knowledge Base API Endpoints
POST /v1/knowledge/search:
  summary: "Search knowledge base using vector similarity"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            query:
              type: string
              description: "Search query"
            sources:
              type: array
              items:
                type: string
              description: "Limit search to specific data sources"
            limit:
              type: integer
              default: 10
              maximum: 100
            similarity_threshold:
              type: number
              minimum: 0
              maximum: 1
              default: 0.7
            include_metadata:
              type: boolean
              default: true
  responses:
    200:
      description: "Search results retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              results:
                type: array
                items:
                  $ref: "#/components/schemas/SearchResult"
              total:
                type: integer
              query_time_ms:
                type: number

POST /v1/knowledge/qa-search:
  summary: "Search Q&A pairs"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            question:
              type: string
              description: "Question to search for"
            sources:
              type: array
              items:
                type: string
            quality_threshold:
              type: number
              minimum: 0
              maximum: 1
              default: 0.7
            limit:
              type: integer
              default: 5
  responses:
    200:
      description: "Q&A search results retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              qa_pairs:
                type: array
                items:
                  $ref: "#/components/schemas/QAPair"
              total:
                type: integer

GET /v1/knowledge/stats:
  summary: "Get knowledge base statistics"
  security:
    - bearerAuth: []
  responses:
    200:
      description: "Knowledge base stats retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              total_documents:
                type: integer
              total_chunks:
                type: integer
              total_qa_pairs:
                type: integer
              sources:
                type: array
                items:
                  type: object
                  properties:
                    source_id:
                      type: string
                    source_name:
                      type: string
                    document_count:
                      type: integer
                    chunk_count:
                      type: integer
                    qa_pair_count:
                      type: integer
              last_updated:
                type: string
                format: date-time
```

---

## 6. System Management APIs

### 6.1 Health & Monitoring

```yaml
# Health & Monitoring API Endpoints
GET /v1/health:
  summary: "System health check"
  responses:
    200:
      description: "System is healthy"
      content:
        application/json:
          schema:
            type: object
            properties:
              status:
                type: string
                enum: ["healthy", "degraded", "unhealthy"]
              timestamp:
                type: string
                format: date-time
              version:
                type: string
              services:
                type: object
                properties:
                  database:
                    $ref: "#/components/schemas/ServiceHealth"
                  redis:
                    $ref: "#/components/schemas/ServiceHealth"
                  vector_db:
                    $ref: "#/components/schemas/ServiceHealth"
                  ai_providers:
                    type: object
                    additionalProperties:
                      $ref: "#/components/schemas/ServiceHealth"

GET /v1/health/detailed:
  summary: "Detailed system health check"
  security:
    - bearerAuth: []
  responses:
    200:
      description: "Detailed health information"
      content:
        application/json:
          schema:
            type: object
            properties:
              system:
                $ref: "#/components/schemas/SystemHealth"
              services:
                type: object
              performance:
                type: object
                properties:
                  avg_response_time_ms:
                    type: number
                  requests_per_minute:
                    type: number
                  error_rate_percent:
                    type: number

GET /v1/metrics:
  summary: "System metrics"
  security:
    - bearerAuth: []
  parameters:
    - name: timeframe
      in: query
      schema:
        type: string
        enum: ["1h", "24h", "7d", "30d"]
        default: "24h"
    - name: metrics
      in: query
      schema:
        type: array
        items:
          type: string
          enum: ["requests", "errors", "latency", "usage", "costs"]
  responses:
    200:
      description: "Metrics retrieved"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/MetricsResponse"

GET /v1/logs:
  summary: "System logs"
  security:
    - bearerAuth: []
  parameters:
    - name: level
      in: query
      schema:
        type: string
        enum: ["info", "warning", "error"]
    - name: component
      in: query
      schema:
        type: string
    - name: start_time
      in: query
      schema:
        type: string
        format: date-time
    - name: end_time
      in: query
      schema:
        type: string
        format: date-time
    - name: limit
      in: query
      schema:
        type: integer
        default: 100
  responses:
    200:
      description: "Logs retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              logs:
                type: array
                items:
                  $ref: "#/components/schemas/LogEntry"
```

### 6.2 Model Configuration

```yaml
# Model Configuration API Endpoints
GET /v1/models/config:
  summary: "Get current model configuration"
  security:
    - bearerAuth: []
  responses:
    200:
      description: "Model configuration retrieved"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ModelConfiguration"

PUT /v1/models/config:
  summary: "Update model configuration"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          $ref: "#/components/schemas/ModelConfigurationUpdate"
  responses:
    200:
      description: "Model configuration updated"
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ModelConfiguration"

GET /v1/models/providers:
  summary: "List available AI providers"
  security:
    - bearerAuth: []
  responses:
    200:
      description: "Providers retrieved"
      content:
        application/json:
          schema:
            type: object
            properties:
              providers:
                type: array
                items:
                  $ref: "#/components/schemas/AIProvider"

POST /v1/models/test:
  summary: "Test model configuration"
  security:
    - bearerAuth: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          properties:
            provider:
              type: string
            model:
              type: string
            test_prompt:
              type: string
              default: "Hello, this is a test."
  responses:
    200:
      description: "Model test completed"
      content:
        application/json:
          schema:
            type: object
            properties:
              success:
                type: boolean
              response:
                type: string
              latency_ms:
                type: number
              error:
                type: string
```

---

## 7. Data Schemas

### 7.1 Core Data Models

```yaml
# Core Data Schemas
components:
  schemas:
    User:
      type: object
      properties:
        user_id:
          type: string
        email:
          type: string
          format: email
        name:
          type: string
        role:
          type: string
          enum: ["viewer", "analyst", "admin", "super_admin"]
        organization_id:
          type: string
        created_at:
          type: string
          format: date-time
        last_login:
          type: string
          format: date-time
        is_active:
          type: boolean

    DataSource:
      type: object
      properties:
        source_id:
          type: string
        name:
          type: string
        type:
          type: string
          enum: ["hr", "crm", "financial", "linkedin", "documents", "research"]
        description:
          type: string
        status:
          type: string
          enum: ["active", "inactive", "error"]
        configuration:
          type: object
        chunking_config:
          $ref: "#/components/schemas/ChunkingConfig"
        qa_rag_enabled:
          type: boolean
        created_at:
          type: string
          format: date-time
        last_sync:
          type: string
          format: date-time
        document_count:
          type: integer
        chunk_count:
          type: integer

    ChunkingConfig:
      type: object
      properties:
        strategy:
          type: string
          enum: ["semantic", "fixed", "hierarchical", "adaptive", "hybrid"]
        chunk_size:
          type: integer
          description: "Target chunk size in characters"
        chunk_overlap:
          type: integer
          description: "Overlap between chunks in characters"
        semantic_threshold:
          type: number
          description: "Threshold for semantic chunking"
        hierarchical_levels:
          type: array
          items:
            type: string
          description: "Document structure levels to respect"

    Document:
      type: object
      properties:
        document_id:
          type: string
        filename:
          type: string
        source_id:
          type: string
        content_type:
          type: string
        file_size:
          type: integer
        status:
          type: string
          enum: ["processing", "completed", "failed"]
        processing_progress:
          type: number
          minimum: 0
          maximum: 100
        chunk_count:
          type: integer
        qa_pair_count:
          type: integer
        uploaded_at:
          type: string
          format: date-time
        processed_at:
          type: string
          format: date-time
        metadata:
          type: object

    DocumentChunk:
      type: object
      properties:
        chunk_id:
          type: string
        document_id:
          type: string
        content:
          type: string
        chunk_index:
          type: integer
        start_position:
          type: integer
        end_position:
          type: integer
        metadata:
          type: object
        embedding:
          type: array
          items:
            type: number
          description: "Vector embedding of the chunk"

    QAPair:
      type: object
      properties:
        qa_id:
          type: string
        document_id:
          type: string
        chunk_id:
          type: string
        question:
          type: string
        answer:
          type: string
        quality_score:
          type: number
          minimum: 0
          maximum: 1
        confidence_score:
          type: number
          minimum: 0
          maximum: 1
        created_at:
          type: string
          format: date-time
        validated:
          type: boolean
        feedback:
          type: object

    TaskEnrichmentResult:
      type: object
      properties:
        enrichment_id:
          type: string
        original_input:
          type: string
        intent_analysis:
          type: object
          properties:
            primary_intent:
              type: string
            confidence:
              type: number
            categories:
              type: array
              items:
                type: string
            complexity:
              type: string
              enum: ["low", "medium", "high"]
        enriched_prompt:
          type: string
        context_added:
          type: object
          properties:
            domain_knowledge:
              type: array
              items:
                type: string
            best_practices:
              type: array
              items:
                type: string
            examples:
              type: array
              items:
                type: object
        quality_score:
          type: number
          minimum: 0
          maximum: 1
        processing_time_ms:
          type: number

    AnalysisResult:
      type: object
      properties:
        analysis_id:
          type: string
        type:
          type: string
          enum: ["department-readiness", "employee-matching", "roi-calculation"]
        status:
          type: string
          enum: ["running", "completed", "failed"]
        progress:
          type: number
          minimum: 0
          maximum: 100
        results:
          type: object
          description: "Analysis-specific results"
        started_at:
          type: string
          format: date-time
        completed_at:
          type: string
          format: date-time
        metadata:
          type: object

    ChatCompletion:
      type: object
      properties:
        id:
          type: string
        object:
          type: string
          enum: ["chat.completion"]
        created:
          type: integer
        model:
          type: string
        choices:
          type: array
          items:
            type: object
            properties:
              index:
                type: integer
              message:
                type: object
                properties:
                  role:
                    type: string
                  content:
                    type: string
              finish_reason:
                type: string
        usage:
          type: object
          properties:
            prompt_tokens:
              type: integer
            completion_tokens:
              type: integer
            total_tokens:
              type: integer

    ServiceHealth:
      type: object
      properties:
        status:
          type: string
          enum: ["healthy", "degraded", "unhealthy"]
        response_time_ms:
          type: number
        last_check:
          type: string
          format: date-time
        error:
          type: string
        details:
          type: object

    LogEntry:
      type: object
      properties:
        timestamp:
          type: string
          format: date-time
        level:
          type: string
          enum: ["info", "warning", "error"]
        message:
          type: string
        component:
          type: string
        operation:
          type: string
        user_id:
          type: string
        request_id:
          type: string
        duration_ms:
          type: number
        metadata:
          type: object

  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

---

## 8. Error Handling

### 8.1 Standard Error Response Format

```yaml
# Error Response Schema
ErrorResponse:
  type: object
  properties:
    error:
      type: object
      properties:
        code:
          type: string
          description: "Machine-readable error code"
        message:
          type: string
          description: "Human-readable error message"
        details:
          type: object
          description: "Additional error details"
        request_id:
          type: string
          description: "Unique request identifier for debugging"
        timestamp:
          type: string
          format: date-time
        documentation_url:
          type: string
          description: "Link to relevant documentation"
      required:
        - code
        - message
```

### 8.2 HTTP Status Codes

```python
# From error handling patterns - EXAMPLE
from enum import Enum

class APIErrorCode(Enum):
    """Standardized API error codes"""
    
    # Authentication & Authorization (4xx)
    INVALID_CREDENTIALS = "auth.invalid_credentials"
    TOKEN_EXPIRED = "auth.token_expired"
    INSUFFICIENT_PERMISSIONS = "auth.insufficient_permissions"
    API_KEY_INVALID = "auth.api_key_invalid"
    RATE_LIMIT_EXCEEDED = "auth.rate_limit_exceeded"
    
    # Request Validation (4xx)
    INVALID_REQUEST = "request.invalid"
    MISSING_REQUIRED_FIELD = "request.missing_field"
    INVALID_FIELD_VALUE = "request.invalid_value"
    REQUEST_TOO_LARGE = "request.too_large"
    UNSUPPORTED_MEDIA_TYPE = "request.unsupported_media"
    
    # Resource Management (4xx)
    RESOURCE_NOT_FOUND = "resource.not_found"
    RESOURCE_ALREADY_EXISTS = "resource.already_exists"
    RESOURCE_LOCKED = "resource.locked"
    RESOURCE_QUOTA_EXCEEDED = "resource.quota_exceeded"
    
    # Processing Errors (4xx/5xx)
    PROCESSING_FAILED = "processing.failed"
    TIMEOUT = "processing.timeout"
    INVALID_FILE_FORMAT = "processing.invalid_format"
    FILE_TOO_LARGE = "processing.file_too_large"
    
    # System Errors (5xx)
    INTERNAL_ERROR = "system.internal_error"
    SERVICE_UNAVAILABLE = "system.service_unavailable"
    DATABASE_ERROR = "system.database_error"
    EXTERNAL_SERVICE_ERROR = "system.external_service_error"
    CONFIGURATION_ERROR = "system.configuration_error"

HTTP_STATUS_MAPPING = {
    # 400 Bad Request
    APIErrorCode.INVALID_REQUEST: 400,
    APIErrorCode.MISSING_REQUIRED_FIELD: 400,
    APIErrorCode.INVALID_FIELD_VALUE: 400,
    APIErrorCode.INVALID_FILE_FORMAT: 400,
    
    # 401 Unauthorized
    APIErrorCode.INVALID_CREDENTIALS: 401,
    APIErrorCode.TOKEN_EXPIRED: 401,
    APIErrorCode.API_KEY_INVALID: 401,
    
    # 403 Forbidden
    APIErrorCode.INSUFFICIENT_PERMISSIONS: 403,
    
    # 404 Not Found
    APIErrorCode.RESOURCE_NOT_FOUND: 404,
    
    # 409 Conflict
    APIErrorCode.RESOURCE_ALREADY_EXISTS: 409,
    APIErrorCode.RESOURCE_LOCKED: 409,
    
    # 413 Payload Too Large
    APIErrorCode.REQUEST_TOO_LARGE: 413,
    APIErrorCode.FILE_TOO_LARGE: 413,
    
    # 415 Unsupported Media Type
    APIErrorCode.UNSUPPORTED_MEDIA_TYPE: 415,
    
    # 422 Unprocessable Entity
    APIErrorCode.PROCESSING_FAILED: 422,
    
    # 429 Too Many Requests
    APIErrorCode.RATE_LIMIT_EXCEEDED: 429,
    APIErrorCode.RESOURCE_QUOTA_EXCEEDED: 429,
    
    # 500 Internal Server Error
    APIErrorCode.INTERNAL_ERROR: 500,
    APIErrorCode.DATABASE_ERROR: 500,
    APIErrorCode.CONFIGURATION_ERROR: 500,
    
    # 502 Bad Gateway
    APIErrorCode.EXTERNAL_SERVICE_ERROR: 502,
    
    # 503 Service Unavailable
    APIErrorCode.SERVICE_UNAVAILABLE: 503,
    
    # 504 Gateway Timeout
    APIErrorCode.TIMEOUT: 504,
}
```

### 8.3 Error Response Examples

```json
// Authentication Error
{
  "error": {
    "code": "auth.token_expired",
    "message": "Authentication token has expired",
    "details": {
      "expired_at": "2024-01-15T10:30:00Z",
      "current_time": "2024-01-15T11:00:00Z"
    },
    "request_id": "req_abc123",
    "timestamp": "2024-01-15T11:00:00Z",
    "documentation_url": "https://docs.ai-enablement.com/auth#token-expiration"
  }
}

// Validation Error
{
  "error": {
    "code": "request.invalid",
    "message": "Request validation failed",
    "details": {
      "validation_errors": [
        {
          "field": "email",
          "message": "Invalid email format"
        },
        {
          "field": "chunking_strategy",
          "message": "Must be one of: semantic, fixed, hierarchical, adaptive, hybrid"
        }
      ]
    },
    "request_id": "req_def456",
    "timestamp": "2024-01-15T11:00:00Z"
  }
}

// Processing Error
{
  "error": {
    "code": "processing.failed",
    "message": "Document processing failed",
    "details": {
      "document_id": "doc_789",
      "stage": "chunking",
      "reason": "Unsupported document format",
      "supported_formats": ["pdf", "docx", "txt", "md"]
    },
    "request_id": "req_ghi789",
    "timestamp": "2024-01-15T11:00:00Z"
  }
}
```

---

## 9. Rate Limiting & Quotas

### 9.1 Rate Limiting Strategy

```python
# From rate limiting patterns - EXAMPLE
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class RateLimit:
    """Rate limit configuration"""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_allowance: int = 10  # Additional requests allowed in burst

# Rate limits by user role
RATE_LIMITS = {
    "viewer": RateLimit(
        requests_per_minute=30,
        requests_per_hour=500,
        requests_per_day=2000
    ),
    "analyst": RateLimit(
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=5000
    ),
    "admin": RateLimit(
        requests_per_minute=120,
        requests_per_hour=2000,
        requests_per_day=10000
    ),
    "super_admin": RateLimit(
        requests_per_minute=300,
        requests_per_hour=5000,
        requests_per_day=25000
    )
}

# Special rate limits for expensive operations
OPERATION_RATE_LIMITS = {
    "document_upload": {
        "requests_per_hour": 50,
        "max_file_size_mb": 100,
        "max_files_per_request": 10
    },
    "analysis_start": {
        "requests_per_hour": 20,
        "concurrent_analyses": 3
    },
    "batch_processing": {
        "requests_per_day": 10,
        "max_batch_size": 1000
    }
}
```

### 9.2 Rate Limiting Headers

```http
# Rate Limiting Response Headers
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642248000
X-RateLimit-Retry-After: 60
```

---

## 10. WebSocket APIs for Real-Time Updates

### 10.1 WebSocket Endpoints

```yaml
# WebSocket API Endpoints
/ws/logs:
  summary: "Real-time log streaming"
  description: "Stream logs for current user's operations"
  authentication: "Bearer token in query parameter or header"
  
/ws/analysis/{analysis_id}:
  summary: "Real-time analysis progress"
  description: "Stream progress updates for specific analysis"
  
/ws/ingestion/{pipeline_id}:
  summary: "Real-time ingestion progress"
  description: "Stream progress updates for data ingestion pipeline"
```

### 10.2 WebSocket Message Format

```json
// Log Message
{
  "type": "log_entry",
  "timestamp": "2024-01-15T11:00:00Z",
  "data": {
    "level": "info",
    "message": "Document processing completed",
    "category": "Processing",
    "progress": 100,
    "details": {
      "document_id": "doc_123",
      "chunks_created": 45
    }
  }
}

// Progress Update
{
  "type": "progress_update",
  "timestamp": "2024-01-15T11:00:00Z",
  "data": {
    "operation_id": "analysis_456",
    "progress": 65,
    "stage": "roi_calculation",
    "message": "Calculating ROI for Marketing department",
    "estimated_completion": "2024-01-15T11:05:00Z"
  }
}

// Error Message
{
  "type": "error",
  "timestamp": "2024-01-15T11:00:00Z",
  "data": {
    "code": "processing.failed",
    "message": "Analysis failed due to insufficient data",
    "operation_id": "analysis_456",
    "can_retry": true
  }
}
```

---

## 11. SDK Integration Patterns

### 11.1 Python SDK Example

```python
# From SDK integration patterns - EXAMPLE
from ai_enablement_sdk import AIEnablementClient
import asyncio

# Initialize client
client = AIEnablementClient(
    api_key="aiplatform_your_api_key_here",
    base_url="https://api.ai-enablement.com/v1"
)

# Example: Upload and process documents
async def process_documents():
    # Upload documents
    upload_result = await client.documents.upload(
        files=["hr_data.pdf", "financial_report.xlsx"],
        chunking_strategy="semantic",
        enable_qa_rag=True
    )
    
    print(f"Upload started: {upload_result.upload_id}")
    
    # Wait for processing to complete
    while True:
        status = await client.documents.get_upload_status(upload_result.upload_id)
        if status.status == "completed":
            break
        elif status.status == "failed":
            print(f"Upload failed: {status.error}")
            return
        
        print(f"Processing: {status.progress}%")
        await asyncio.sleep(5)
    
    print("Documents processed successfully!")

# Example: Run department analysis
async def analyze_departments():
    # Start analysis
    analysis = await client.analysis.department_readiness(
        departments=["sales", "marketing", "engineering"],
        analysis_depth="comprehensive",
        include_roi_estimation=True
    )
    
    print(f"Analysis started: {analysis.analysis_id}")
    
    # Wait for completion with progress updates
    async for update in client.analysis.stream_progress(analysis.analysis_id):
        print(f"Progress: {update.progress}% - {update.message}")
    
    # Get final results
    results = await client.analysis.get_results(analysis.analysis_id)
    
    for dept_result in results.department_rankings:
        print(f"{dept_result.department}: {dept_result.readiness_score}/100")

# Run examples
asyncio.run(process_documents())
asyncio.run(analyze_departments())
```

### 11.2 CLI Integration Example

```bash
# CLI Examples using the API
# Install CLI tool
pip install ai-enablement-cli

# Configure authentication
ai-enablement auth login --email user@company.com

# Upload documents
ai-enablement documents upload \
  --files "*.pdf" \
  --chunking-strategy semantic \
  --enable-qa-rag \
  --watch

# Run department analysis
ai-enablement analysis department-readiness \
  --departments sales,marketing,engineering \
  --depth comprehensive \
  --include-roi \
  --output results.json

# Search knowledge base
ai-enablement knowledge search \
  --query "What are our Q3 sales targets?" \
  --sources hr,financial \
  --limit 5

# Stream logs in real-time
ai-enablement logs stream --level info --follow
```

---

## 12. OpenAPI Specification

### 12.1 Complete OpenAPI Document Structure

```yaml
openapi: 3.0.3
info:
  title: AI Enablement Platform API
  description: |
    Comprehensive API for the AI Enablement Platform, providing data ingestion,
    AI analysis, user task enrichment, and system management capabilities.
  version: 1.0.0
  contact:
    name: AI Enablement Platform Team
    email: api-support@ai-enablement.com
    url: https://docs.ai-enablement.com
  license:
    name: MIT
    url: https://opensource.org/licenses/MIT

servers:
  - url: https://api.ai-enablement.com/v1
    description: Production server
  - url: https://staging-api.ai-enablement.com/v1
    description: Staging server
  - url: http://localhost:5001/v1
    description: Development server

security:
  - bearerAuth: []

paths:
  # Authentication endpoints
  /auth/login:
    $ref: "#/paths/auth_login"
  
  # Data management endpoints
  /data-sources:
    $ref: "#/paths/data_sources"
  
  # Document management endpoints
  /documents/upload:
    $ref: "#/paths/documents_upload"
  
  # AI processing endpoints
  /enrichment/analyze:
    $ref: "#/paths/enrichment_analyze"
  
  # Analysis endpoints
  /analysis/department-readiness:
    $ref: "#/paths/analysis_department_readiness"
  
  # OpenAI-compatible endpoints
  /chat/completions:
    $ref: "#/paths/chat_completions"
  
  # Knowledge base endpoints
  /knowledge/search:
    $ref: "#/paths/knowledge_search"
  
  # System endpoints
  /health:
    $ref: "#/paths/health"

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: |
        JWT token or API key authentication.
        For JWT: `Bearer eyJ...`
        For API key: `Bearer aiplatform_...`
  
  schemas:
    # Include all schemas defined above
    User:
      $ref: "#/components/schemas/User"
    DataSource:
      $ref: "#/components/schemas/DataSource"
    # ... (all other schemas)
  
  responses:
    UnauthorizedError:
      description: Authentication required
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
    
    ForbiddenError:
      description: Insufficient permissions
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
    
    NotFoundError:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
    
    ValidationError:
      description: Request validation failed
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
    
    RateLimitError:
      description: Rate limit exceeded
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/ErrorResponse"
      headers:
        X-RateLimit-Limit:
          schema:
            type: integer
        X-RateLimit-Remaining:
          schema:
            type: integer
        X-RateLimit-Reset:
          schema:
            type: integer
```

---

## 13. Implementation Priority Order

### 13.1 Core Foundation (Highest Priority)
- Authentication & authorization system
- User management endpoints
- Basic health checks and monitoring
- Error handling framework
- Rate limiting implementation

### 13.2 Data Management Layer
- Data source management endpoints
- Document upload and processing APIs
- Data ingestion pipeline APIs
- Basic knowledge base queries
- WebSocket support for real-time updates

### 13.3 AI Processing Layer
- User task enrichment endpoints
- AI analysis workflow APIs
- OpenAI-compatible completion endpoints
- CrewAI agent management APIs
- Streaming response support

### 13.4 Advanced Features
- Advanced search and knowledge APIs
- System management and configuration
- Comprehensive monitoring and metrics
- Performance optimization

---

## 14. Conclusion

This API design specification provides a comprehensive, production-ready REST API for the AI Enablement Platform. The design emphasizes:

1. **Developer Experience**: Clear, consistent patterns with excellent documentation
2. **Security**: Comprehensive authentication and authorization
3. **Scalability**: Designed for high throughput and horizontal scaling
4. **Flexibility**: Support for multiple client types (web, mobile, CLI, SDK)
5. **Observability**: Built-in logging, monitoring, and error tracking
6. **Standards Compliance**: OpenAPI 3.0 compatible with industry best practices

The API serves as the single entry point for all backend functionality, enabling seamless integration with frontend applications, CLI tools, and third-party systems while maintaining security, performance, and reliability standards required for enterprise deployment.

**Next Steps:**
1. Review and validate API design with stakeholders
2. Begin implementation starting with Core Foundation components
3. Set up API documentation and developer portal
4. Implement comprehensive testing strategy
5. Plan deployment and monitoring infrastructure
