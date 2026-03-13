# Greenhouse Connector Implementation Plan

**Date:** October 23, 2025  
**Status:** Ready to Implement  
**API Connectivity:** ✅ Verified

---

## Executive Summary

Implement a Greenhouse ATS connector to enable sourcing candidate resumes directly from Greenhouse for Talent Intelligence Analysis. This connector will integrate into the existing connector framework and appear alongside the File System connector in the UI.

### API Verification Results

✅ **API Connection:** Working  
✅ **Candidates Endpoint:** Accessible (11M+ candidates)  
✅ **Jobs Endpoint:** Accessible  
✅ **Applications Endpoint:** Accessible  
✅ **Resume Attachments:** Accessible (PDF, DOCX URLs)  

**API Documentation:** https://developers.greenhouse.io/harvest.html#introduction

---

## Architecture Overview

### Integration Points

```
┌─────────────────────────────────────────────────────────┐
│                    Eliza Platform                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │   Connector Framework (Existing)               │    │
│  │                                                 │    │
│  │  • PeopleDataLabsConnector                     │    │
│  │  • LocalFileSystemConnector                    │    │
│  │  • GreenhouseConnector (NEW) ◄─────────────┐   │    │
│  └────────────────────────────────────────────────┘   │
│                          │                            │
│                          │                            │
│  ┌────────────────────────────────────────────────┐   │
│  │   Connector Service                            │   │
│  │   • create_configuration()                     │   │
│  │   • list_configurations()                      │   │
│  │   • test_connection()                          │   │
│  │   • fetch_resumes()                            │   │
│  └────────────────────────────────────────────────┘   │
│                          │                            │
│                          ▼                            │
│  ┌────────────────────────────────────────────────┐   │
│  │   Talent Intelligence Orchestrator             │   │
│  │   • run_analysis()                             │   │
│  │   • _parse_resumes()                           │   │
│  │   • _score_applicants()                        │   │
│  └────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
                           │
                           │ HTTP + Basic Auth
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Greenhouse Harvest API                      │
│                                                          │
│  • GET /v1/candidates                                    │
│  • GET /v1/jobs                                          │
│  • GET /v1/applications                                  │
│  • Download Resume Attachments                          │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 1: Backend Implementation

### 1.1 Database Schema Changes

**New Migration:** `add_greenhouse_connector_support.py`

```python
"""Add Greenhouse connector support

Revision ID: h8i9j0k1l2m3
"""

def upgrade():
    # Add 'greenhouse' to provider_name enum
    op.execute("""
        ALTER TYPE provider_type ADD VALUE IF NOT EXISTS 'greenhouse';
    """)
    
    # No schema changes needed - existing connector tables support it
    pass

def downgrade():
    # Cannot remove enum values in PostgreSQL
    pass
```

### 1.2 Greenhouse Connector Implementation

**File:** `src/services/ingestion/connectors/greenhouse.py`

```python
"""
Greenhouse ATS Connector

Fetches candidate resumes from Greenhouse using the Harvest API.
Supports filtering by job, application status, candidate tags, and date ranges.
"""

import logging
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin

from src.services.ingestion.connectors.base import BaseConnector
from src.models.ingestion import ConnectorConfiguration

logger = logging.getLogger(__name__)


class GreenhouseConnector(BaseConnector):
    """
    Greenhouse ATS connector for fetching candidate resumes.
    
    Authentication: Basic Auth (API Key as username, empty password)
    Base URL: https://harvest.greenhouse.io/v1/
    
    Configuration:
        api_key: Greenhouse Harvest API key (required)
        job_ids: List of job IDs to filter by (optional)
        application_status: Filter by status (active, rejected, hired) (optional)
        candidate_tags: Filter by candidate tags (optional)
        created_after: Only fetch candidates created after this date (optional)
        include_prospects: Include prospect candidates (optional, default: false)
        max_candidates: Maximum candidates to fetch (optional, default: 100)
    """
    
    PROVIDER_NAME = "greenhouse"
    BASE_URL = "https://harvest.greenhouse.io/v1/"
    
    # Rate limiting (per Greenhouse docs)
    RATE_LIMIT_CALLS = 50  # requests per window
    RATE_LIMIT_WINDOW = 10  # seconds
    
    def __init__(self, config: ConnectorConfiguration):
        super().__init__(config)
        self.api_key = self._get_api_key()
        self.job_ids = self._parse_job_ids()
        self.application_status = self.config.sync_config.get("application_status")
        self.candidate_tags = self._parse_candidate_tags()
        self.created_after = self._parse_created_after()
        self.include_prospects = self.config.sync_config.get("include_prospects", False)
        self.max_candidates = self.config.sync_config.get("max_candidates", 100)
        
    def _get_api_key(self) -> str:
        """Extract API key from encrypted credentials."""
        api_key = self.config.credentials.get("api_key")
        if not api_key:
            raise ValueError("Greenhouse API key is required")
        return api_key
    
    def _parse_job_ids(self) -> Optional[List[int]]:
        """Parse job IDs from config."""
        job_ids_str = self.config.sync_config.get("job_ids")
        if not job_ids_str:
            return None
        
        if isinstance(job_ids_str, list):
            return [int(jid) for jid in job_ids_str]
        
        # Handle comma-separated string
        return [int(jid.strip()) for jid in str(job_ids_str).split(",") if jid.strip()]
    
    def _parse_candidate_tags(self) -> Optional[List[str]]:
        """Parse candidate tags from config."""
        tags_str = self.config.sync_config.get("candidate_tags")
        if not tags_str:
            return None
        
        if isinstance(tags_str, list):
            return tags_str
        
        # Handle comma-separated string
        return [tag.strip() for tag in str(tags_str).split(",") if tag.strip()]
    
    def _parse_created_after(self) -> Optional[datetime]:
        """Parse created_after date from config."""
        created_after_str = self.config.sync_config.get("created_after")
        if not created_after_str:
            return None
        
        if isinstance(created_after_str, datetime):
            return created_after_str
        
        # Parse ISO date string
        return datetime.fromisoformat(str(created_after_str).replace('Z', '+00:00'))
    
    async def check(self) -> bool:
        """
        Test connection to Greenhouse API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth(self.api_key, '')
                async with session.get(
                    urljoin(self.BASE_URL, "candidates"),
                    auth=auth,
                    params={"per_page": 1},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info("Greenhouse API connection successful")
                        return True
                    elif response.status == 401:
                        logger.error("Greenhouse API authentication failed (invalid API key)")
                        return False
                    else:
                        logger.error(f"Greenhouse API returned status {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Greenhouse connection test failed: {e}", exc_info=True)
            return False
    
    async def fetch_candidates(
        self,
        page: int = 1,
        per_page: int = 100
    ) -> Dict[str, Any]:
        """
        Fetch candidates from Greenhouse.
        
        Args:
            page: Page number (1-indexed)
            per_page: Results per page (max 500)
            
        Returns:
            Dict with 'candidates' list and pagination info
        """
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            
            params = {
                "page": page,
                "per_page": min(per_page, 500)  # Greenhouse max
            }
            
            # Add filters
            if self.job_ids:
                params["job_id"] = ",".join(str(jid) for jid in self.job_ids)
            
            if self.created_after:
                params["created_after"] = self.created_after.isoformat()
            
            async with session.get(
                urljoin(self.BASE_URL, "candidates"),
                auth=auth,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                candidates = await response.json()
                
                # Extract pagination info from headers
                link_header = response.headers.get('Link', '')
                next_page = self._parse_next_page(link_header)
                
                return {
                    "candidates": candidates,
                    "page": page,
                    "has_next": next_page is not None,
                    "next_page": next_page
                }
    
    def _parse_next_page(self, link_header: str) -> Optional[int]:
        """Parse next page number from Link header."""
        if not link_header or 'rel="next"' not in link_header:
            return None
        
        # Parse: <https://harvest.greenhouse.io/v1/candidates?page=2>; rel="next"
        import re
        match = re.search(r'page=(\d+)>;\s*rel="next"', link_header)
        if match:
            return int(match.group(1))
        return None
    
    async def fetch_application(self, application_id: int) -> Dict[str, Any]:
        """Fetch detailed application data."""
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            
            async with session.get(
                urljoin(self.BASE_URL, f"applications/{application_id}"),
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                return await response.json()
    
    async def download_resume(self, url: str) -> bytes:
        """
        Download resume file from Greenhouse S3 URL.
        
        Args:
            url: Pre-signed S3 URL from attachments
            
        Returns:
            Resume file bytes
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                response.raise_for_status()
                return await response.read()
    
    async def sync(self) -> Dict[str, Any]:
        """
        Sync candidates and their resumes from Greenhouse.
        
        Returns:
            Dict with sync results and statistics
        """
        results = {
            "candidates_fetched": 0,
            "resumes_downloaded": 0,
            "candidates_filtered": 0,
            "errors": [],
            "resumes": []
        }
        
        try:
            page = 1
            candidates_processed = 0
            
            while candidates_processed < self.max_candidates:
                # Fetch page of candidates
                response = await self.fetch_candidates(page=page, per_page=100)
                candidates = response["candidates"]
                
                if not candidates:
                    break
                
                results["candidates_fetched"] += len(candidates)
                
                # Process each candidate
                for candidate in candidates:
                    if candidates_processed >= self.max_candidates:
                        break
                    
                    # Apply filters
                    if not self._should_include_candidate(candidate):
                        results["candidates_filtered"] += 1
                        continue
                    
                    # Extract resumes
                    resumes = await self._extract_candidate_resumes(candidate)
                    results["resumes"].extend(resumes)
                    results["resumes_downloaded"] += len(resumes)
                    
                    candidates_processed += 1
                
                # Check if there's a next page
                if not response["has_next"] or candidates_processed >= self.max_candidates:
                    break
                
                page = response["next_page"]
            
            logger.info(
                f"Greenhouse sync complete: {results['candidates_fetched']} candidates, "
                f"{results['resumes_downloaded']} resumes"
            )
            
        except Exception as e:
            error_msg = f"Greenhouse sync failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results["errors"].append(error_msg)
        
        return results
    
    def _should_include_candidate(self, candidate: Dict[str, Any]) -> bool:
        """Apply filters to determine if candidate should be included."""
        
        # Filter by application status
        if self.application_status:
            applications = candidate.get("applications", [])
            if not any(
                app.get("status") == self.application_status
                for app in applications
            ):
                return False
        
        # Filter by prospect status
        if not self.include_prospects:
            applications = candidate.get("applications", [])
            if all(app.get("prospect", False) for app in applications):
                return False
        
        # Filter by tags
        if self.candidate_tags:
            candidate_tags = set(candidate.get("tags", []))
            required_tags = set(self.candidate_tags)
            if not required_tags.intersection(candidate_tags):
                return False
        
        return True
    
    async def _extract_candidate_resumes(
        self,
        candidate: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract and download resume files for a candidate.
        
        Returns:
            List of resume dicts with filename and file_bytes
        """
        resumes = []
        
        # Get attachments from candidate record
        attachments = candidate.get("attachments", [])
        
        # Also check applications for attachments
        for application in candidate.get("applications", []):
            attachments.extend(application.get("attachments", []))
        
        # Filter for resume attachments
        resume_attachments = [
            att for att in attachments
            if att.get("type") == "resume" or
               att.get("filename", "").lower().endswith((".pdf", ".doc", ".docx"))
        ]
        
        # Download each resume
        for attachment in resume_attachments:
            try:
                url = attachment.get("url")
                filename = attachment.get("filename", "resume.pdf")
                
                if not url:
                    continue
                
                # Download resume
                file_bytes = await self.download_resume(url)
                
                resumes.append({
                    "filename": filename,
                    "file_bytes": file_bytes,
                    "candidate_id": candidate.get("id"),
                    "candidate_name": f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip(),
                    "candidate_email": self._get_primary_email(candidate),
                    "created_at": attachment.get("created_at"),
                    "metadata": {
                        "greenhouse_candidate_id": candidate.get("id"),
                        "greenhouse_application_ids": [
                            app.get("id") for app in candidate.get("applications", [])
                        ],
                        "candidate_tags": candidate.get("tags", []),
                        "attachment_type": attachment.get("type")
                    }
                })
                
                logger.info(f"Downloaded resume for candidate {candidate.get('id')}: {filename}")
                
            except Exception as e:
                logger.warning(
                    f"Failed to download resume for candidate {candidate.get('id')}: {e}"
                )
        
        return resumes
    
    def _get_primary_email(self, candidate: Dict[str, Any]) -> Optional[str]:
        """Extract primary email address from candidate."""
        email_addresses = candidate.get("email_addresses", [])
        if email_addresses:
            return email_addresses[0].get("value")
        return None
    
    async def get_jobs(self) -> List[Dict[str, Any]]:
        """
        Fetch list of jobs from Greenhouse.
        Used for UI dropdowns when configuring the connector.
        
        Returns:
            List of job dicts with id, name, status
        """
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            
            async with session.get(
                urljoin(self.BASE_URL, "jobs"),
                auth=auth,
                params={"per_page": 500},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                jobs = await response.json()
                
                return [
                    {
                        "id": job["id"],
                        "name": job["name"],
                        "status": job["status"],
                        "departments": [dept["name"] for dept in job.get("departments", [])],
                        "offices": [office["name"] for office in job.get("offices", [])]
                    }
                    for job in jobs
                    if job.get("status") == "open"  # Only show open jobs
                ]
```

---

## Phase 2: API Integration

### 2.1 New API Routes

**File:** `src/api/routes/connectors.py` (Extend existing)

```python
@router.get(
    "/greenhouse/jobs",
    response_model=List[GreenhouseJobResponse],
    dependencies=[Depends(require_permission("connectors:read"))]
)
async def list_greenhouse_jobs(
    api_key: str = Query(..., description="Greenhouse API key"),
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    List available jobs from Greenhouse.
    
    Used by UI to populate job selection dropdown when configuring connector.
    """
    try:
        # Create temporary connector instance for API call
        temp_config = ConnectorConfiguration(
            customer_id=current_user.customer_id,
            provider_name="greenhouse",
            credentials={"api_key": api_key},
            sync_config={},
            is_enabled=True
        )
        
        connector = GreenhouseConnector(temp_config)
        jobs = await connector.get_jobs()
        
        return [GreenhouseJobResponse(**job) for job in jobs]
        
    except Exception as e:
        logger.error(f"Failed to fetch Greenhouse jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Greenhouse jobs: {str(e)}"
        )


@router.post(
    "/greenhouse/test-connection",
    response_model=TestConnectionResponse,
    dependencies=[Depends(require_permission("connectors:manage"))]
)
async def test_greenhouse_connection(
    request: TestGreenhouseConnectionRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Test Greenhouse API connection before saving configuration.
    """
    try:
        temp_config = ConnectorConfiguration(
            customer_id=current_user.customer_id,
            provider_name="greenhouse",
            credentials={"api_key": request.api_key},
            sync_config={},
            is_enabled=True
        )
        
        connector = GreenhouseConnector(temp_config)
        is_connected = await connector.check()
        
        return TestConnectionResponse(
            success=is_connected,
            message="Connected to Greenhouse successfully" if is_connected else "Connection failed"
        )
        
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Connection test failed: {str(e)}"
        )
```

### 2.2 Pydantic Models

**File:** `src/models/ingestion.py` (Add to existing)

```python
class GreenhouseJobResponse(BaseModel):
    """Job information from Greenhouse for UI dropdowns."""
    id: int
    name: str
    status: str
    departments: List[str]
    offices: List[str]


class TestGreenhouseConnectionRequest(BaseModel):
    """Request to test Greenhouse connection."""
    api_key: str = Field(..., description="Greenhouse Harvest API key")


class GreenhouseConnectorConfig(BaseModel):
    """Configuration for Greenhouse connector."""
    api_key: str = Field(..., description="Greenhouse Harvest API key")
    job_ids: Optional[List[int]] = Field(None, description="Filter by specific job IDs")
    application_status: Optional[str] = Field(
        None,
        description="Filter by application status (active, rejected, hired)"
    )
    candidate_tags: Optional[List[str]] = Field(
        None,
        description="Filter by candidate tags"
    )
    created_after: Optional[datetime] = Field(
        None,
        description="Only fetch candidates created after this date"
    )
    include_prospects: bool = Field(
        False,
        description="Include prospect candidates (not yet applied)"
    )
    max_candidates: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of candidates to fetch"
    )
```

---

## Phase 3: Frontend Implementation

### 3.1 Greenhouse Configuration Component

**File:** `frontend/src/components/connectors/GreenhouseConnectorConfig.tsx` (NEW)

```typescript
import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { 
  BuildingOfficeIcon, 
  UserGroupIcon, 
  FunnelIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline';

interface GreenhouseJob {
  id: number;
  name: string;
  status: string;
  departments: string[];
  offices: string[];
}

interface GreenhouseConfigFormData {
  name: string;
  api_key: string;
  job_ids: number[];
  application_status: string;
  candidate_tags: string;
  created_after: string;
  include_prospects: boolean;
  max_candidates: number;
}

export function GreenhouseConnectorConfig({ onSave, onCancel, existingConfig }) {
  const [jobs, setJobs] = useState<GreenhouseJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'success' | 'error'>('idle');
  
  const { register, handleSubmit, watch, formState: { errors } } = useForm<GreenhouseConfigFormData>({
    defaultValues: existingConfig || {
      name: 'Greenhouse Connector',
      application_status: 'active',
      include_prospects: false,
      max_candidates: 100
    }
  });
  
  const apiKey = watch('api_key');
  
  // Test connection when API key changes
  const testConnection = async () => {
    if (!apiKey) return;
    
    setTestingConnection(true);
    try {
      const response = await fetch('/api/v1/connectors/greenhouse/test-connection', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ api_key: apiKey })
      });
      
      const result = await response.json();
      setConnectionStatus(result.success ? 'success' : 'error');
      
      // If successful, fetch jobs
      if (result.success) {
        await fetchJobs();
      }
    } catch (error) {
      setConnectionStatus('error');
    } finally {
      setTestingConnection(false);
    }
  };
  
  // Fetch available jobs from Greenhouse
  const fetchJobs = async () => {
    if (!apiKey) return;
    
    setLoadingJobs(true);
    try {
      const response = await fetch(
        `/api/v1/connectors/greenhouse/jobs?api_key=${encodeURIComponent(apiKey)}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('authToken')}`
          }
        }
      );
      
      const jobsData = await response.json();
      setJobs(jobsData);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setLoadingJobs(false);
    }
  };
  
  const onSubmit = async (data: GreenhouseConfigFormData) => {
    const config = {
      provider_name: 'greenhouse',
      name: data.name,
      credentials: {
        api_key: data.api_key
      },
      sync_config: {
        job_ids: data.job_ids,
        application_status: data.application_status,
        candidate_tags: data.candidate_tags ? data.candidate_tags.split(',').map(t => t.trim()) : [],
        created_after: data.created_after || null,
        include_prospects: data.include_prospects,
        max_candidates: data.max_candidates
      },
      is_enabled: true
    };
    
    await onSave(config);
  };
  
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 pb-4 border-b border-divider">
        <BuildingOfficeIcon className="w-8 h-8 text-brand" />
        <div>
          <h2 className="text-xl font-semibold text-text">Configure Greenhouse Connector</h2>
          <p className="text-sm text-muted">
            Connect to your Greenhouse ATS to source candidate resumes
          </p>
        </div>
      </div>
      
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Basic Configuration */}
        <div className="bg-surface-darker border border-divider rounded-lg p-6 space-y-4">
          <h3 className="text-lg font-semibold text-text flex items-center gap-2">
            <UserGroupIcon className="w-5 h-5 text-brand" />
            Basic Configuration
          </h3>
          
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              Configuration Name *
            </label>
            <input
              {...register('name', { required: 'Name is required' })}
              type="text"
              className="w-full px-4 py-2 bg-surface border border-divider rounded-lg text-text"
              placeholder="e.g., Engineering Candidates"
            />
            {errors.name && (
              <p className="mt-1 text-sm text-red-500">{errors.name.message}</p>
            )}
          </div>
          
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              Greenhouse API Key *
            </label>
            <div className="flex gap-2">
              <input
                {...register('api_key', { required: 'API key is required' })}
                type="password"
                className="flex-1 px-4 py-2 bg-surface border border-divider rounded-lg text-text font-mono text-sm"
                placeholder="Enter your Harvest API key"
                onBlur={testConnection}
              />
              <button
                type="button"
                onClick={testConnection}
                disabled={testingConnection || !apiKey}
                className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand/80 disabled:opacity-50"
              >
                {testingConnection ? 'Testing...' : 'Test'}
              </button>
            </div>
            {errors.api_key && (
              <p className="mt-1 text-sm text-red-500">{errors.api_key.message}</p>
            )}
            {connectionStatus === 'success' && (
              <p className="mt-1 text-sm text-green-500 flex items-center gap-1">
                <CheckCircleIcon className="w-4 h-4" />
                Connection successful
              </p>
            )}
            {connectionStatus === 'error' && (
              <p className="mt-1 text-sm text-red-500 flex items-center gap-1">
                <XCircleIcon className="w-4 h-4" />
                Connection failed - check your API key
              </p>
            )}
            <p className="mt-1 text-xs text-muted">
              Get your API key from: Greenhouse → Configure → Dev Center → API Credential Management
            </p>
          </div>
        </div>
        
        {/* Filtering Options */}
        <div className="bg-surface-darker border border-divider rounded-lg p-6 space-y-4">
          <h3 className="text-lg font-semibold text-text flex items-center gap-2">
            <FunnelIcon className="w-5 h-5 text-brand" />
            Filtering Options
          </h3>
          
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              Filter by Jobs
            </label>
            {loadingJobs ? (
              <p className="text-sm text-muted">Loading jobs...</p>
            ) : jobs.length > 0 ? (
              <select
                {...register('job_ids')}
                multiple
                className="w-full px-4 py-2 bg-surface border border-divider rounded-lg text-text"
                size={5}
              >
                {jobs.map(job => (
                  <option key={job.id} value={job.id}>
                    {job.name} ({job.departments.join(', ')})
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-sm text-muted">
                Test connection to load available jobs
              </p>
            )}
            <p className="mt-1 text-xs text-muted">
              Hold Cmd/Ctrl to select multiple jobs. Leave empty to include all jobs.
            </p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              Application Status
            </label>
            <select
              {...register('application_status')}
              className="w-full px-4 py-2 bg-surface border border-divider rounded-lg text-text"
            >
              <option value="">All statuses</option>
              <option value="active">Active (currently being considered)</option>
              <option value="rejected">Rejected</option>
              <option value="hired">Hired</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              Candidate Tags
            </label>
            <input
              {...register('candidate_tags')}
              type="text"
              className="w-full px-4 py-2 bg-surface border border-divider rounded-lg text-text"
              placeholder="e.g., Engineering, Senior, High-Priority"
            />
            <p className="mt-1 text-xs text-muted">
              Comma-separated list. Leave empty to include all candidates.
            </p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              Created After
            </label>
            <input
              {...register('created_after')}
              type="date"
              className="w-full px-4 py-2 bg-surface border border-divider rounded-lg text-text"
            />
            <p className="mt-1 text-xs text-muted">
              Only fetch candidates added after this date
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            <input
              {...register('include_prospects')}
              type="checkbox"
              id="include_prospects"
              className="w-4 h-4 text-brand"
            />
            <label htmlFor="include_prospects" className="text-sm text-text">
              Include prospect candidates (not yet applied to specific job)
            </label>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              Maximum Candidates to Fetch
            </label>
            <input
              {...register('max_candidates', { 
                required: true,
                min: 1,
                max: 1000
              })}
              type="number"
              className="w-full px-4 py-2 bg-surface border border-divider rounded-lg text-text"
              min="1"
              max="1000"
            />
            <p className="mt-1 text-xs text-muted">
              Limit: 1-1000 candidates per sync
            </p>
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="px-6 py-2 border border-divider rounded-lg text-text hover:bg-surface-darker"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={connectionStatus !== 'success'}
            className="px-6 py-2 bg-brand text-white rounded-lg hover:bg-brand/80 disabled:opacity-50"
          >
            Save Configuration
          </button>
        </div>
      </form>
    </div>
  );
}
```

### 3.2 Update Connector Selection UI

**File:** `frontend/src/pages/talent-intelligence/TalentIntelligencePage.tsx` (Update)

Add Greenhouse option to the connector selection:

```typescript
const connectorOptions = [
  {
    id: 'filesystem',
    name: 'Local File System',
    description: 'Upload resumes from your local files',
    icon: FolderIcon,
    available: true
  },
  {
    id: 'greenhouse',
    name: 'Greenhouse',
    description: 'Import candidates from your Greenhouse ATS',
    icon: BuildingOfficeIcon,
    available: true,
    comingSoon: false
  }
];
```

---

## Phase 4: Integration with Talent Intelligence

### 4.1 Update Orchestrator

**File:** `src/services/talent/orchestrator.py` (Update)

Ensure the orchestrator can handle Greenhouse-sourced resumes:

```python
# No changes needed! Greenhouse connector returns same format as filesystem:
# List[Dict] with 'filename', 'file_bytes', 'metadata'
# Orchestrator already handles this via connector framework
```

### 4.2 Enhanced Metadata Tracking

Store Greenhouse-specific metadata with parsed resumes:

```python
# In ParsedResume model, metadata will include:
{
    "source": "greenhouse",
    "greenhouse_candidate_id": 11211889004,
    "greenhouse_application_ids": [12181467004],
    "candidate_tags": ["LinkedIn InMail Import"],
    "application_status": "active",
    "fetched_at": "2025-10-23T20:45:57Z"
}
```

---

## Implementation Timeline

### Week 1: Backend Foundation
- **Day 1-2:** Database migration + GreenhouseConnector implementation
- **Day 3:** API routes + Pydantic models
- **Day 4:** Integration testing with real API
- **Day 5:** Error handling + rate limiting

### Week 2: Frontend + Integration
- **Day 1-2:** GreenhouseConnectorConfig component
- **Day 3:** Update connector selection UI
- **Day 4:** End-to-end testing
- **Day 5:** Documentation + deployment

**Total:** 10 days

---

## Testing Strategy

### 1. Unit Tests

```python
# tests/test_greenhouse_connector.py

async def test_greenhouse_connection():
    """Test API connection."""
    config = ConnectorConfiguration(
        customer_id="test",
        provider_name="greenhouse",
        credentials={"api_key": "test_key"},
        sync_config={},
        is_enabled=True
    )
    
    connector = GreenhouseConnector(config)
    # Mock aiohttp session
    # Assert connection test succeeds


async def test_greenhouse_fetch_candidates():
    """Test fetching candidates with filters."""
    config = ConnectorConfiguration(
        customer_id="test",
        provider_name="greenhouse",
        credentials={"api_key": "test_key"},
        sync_config={
            "job_ids": [4087771004],
            "application_status": "active",
            "max_candidates": 10
        },
        is_enabled=True
    )
    
    connector = GreenhouseConnector(config)
    # Mock API responses
    # Assert correct filtering
    # Assert resumes are extracted


async def test_greenhouse_resume_download():
    """Test downloading resume from S3 URL."""
    # Mock S3 pre-signed URL
    # Assert file is downloaded
    # Assert file bytes are returned
```

### 2. Integration Tests

```python
async def test_greenhouse_end_to_end():
    """Test full flow from Greenhouse to parsed resume."""
    # 1. Create Greenhouse configuration
    # 2. Test connection
    # 3. Fetch candidates
    # 4. Download resumes
    # 5. Pass to orchestrator
    # 6. Verify resumes are parsed
    # 7. Verify metadata is preserved
```

### 3. Manual Testing Checklist

- [ ] Test connection with valid API key
- [ ] Test connection with invalid API key
- [ ] Fetch candidates from real Greenhouse instance
- [ ] Filter by job ID
- [ ] Filter by application status
- [ ] Filter by candidate tags
- [ ] Filter by date range
- [ ] Download resumes (PDF, DOCX)
- [ ] Run full talent analysis with Greenhouse resumes
- [ ] Verify UI displays Greenhouse metadata
- [ ] Test rate limiting (50 requests / 10 seconds)
- [ ] Test pagination for large result sets

---

## Security Considerations

### 1. API Key Storage
- ✅ API keys stored encrypted in database
- ✅ Never logged or exposed in responses
- ✅ Transmitted via Basic Auth over HTTPS only

### 2. Resume Data
- ✅ Resumes temporarily stored in memory during processing
- ✅ Not persisted to disk unless explicitly requested
- ✅ Metadata tracked for audit trail

### 3. Rate Limiting
- ✅ Respect Greenhouse rate limits (50 req/10s)
- ✅ Implement exponential backoff on errors
- ✅ Track API usage per connector

### 4. Access Control
- ✅ Require `connectors:manage` permission to create/edit
- ✅ Require `connectors:read` permission to view
- ✅ Customer isolation (can only access own connectors)

---

## Error Handling

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Invalid API key | Verify API key in Greenhouse settings |
| 403 Forbidden | Insufficient permissions | Check API key has Harvest API access |
| 404 Not Found | Invalid job/candidate ID | Refresh job list, verify IDs exist |
| 429 Too Many Requests | Rate limit exceeded | Implement backoff, reduce batch size |
| 500 Server Error | Greenhouse issue | Retry with exponential backoff |
| Network timeout | Slow connection | Increase timeout, reduce page size |

### Error Logging

```python
# All errors logged with context
logger.error(
    "greenhouse_sync_failed",
    customer_id=config.customer_id,
    connector_id=config.id,
    error=str(e),
    candidates_fetched=count,
    time_elapsed=elapsed
)
```

---

## Monitoring & Metrics

### Key Metrics to Track

1. **Connector Health**
   - Connection success rate
   - Average sync duration
   - Candidates fetched per sync
   - Resumes downloaded per sync

2. **API Usage**
   - Requests per minute
   - Rate limit hits
   - Error rate by type
   - Average response time

3. **Data Quality**
   - Resumes with valid format
   - Parse success rate
   - Missing metadata fields

### Dashboard Queries

```sql
-- Greenhouse connector usage
SELECT 
    c.name,
    COUNT(s.id) as sync_count,
    AVG(s.records_fetched) as avg_candidates,
    AVG(s.duration_seconds) as avg_duration,
    SUM(CASE WHEN s.status = 'failed' THEN 1 ELSE 0 END) as failed_syncs
FROM connector_configurations c
LEFT JOIN connector_syncs s ON c.id = s.connector_configuration_id
WHERE c.provider_name = 'greenhouse'
GROUP BY c.id, c.name
ORDER BY sync_count DESC;
```

---

## Documentation Requirements

### 1. API Documentation
- Update `docs/api/05-connectors.md` with Greenhouse endpoints
- Add Greenhouse configuration schema
- Document filtering options

### 2. User Guide
- Create `docs/user-guides/greenhouse-connector-setup.md`
- Step-by-step setup instructions
- Screenshots of UI
- Common troubleshooting

### 3. Code Documentation
- Docstrings for all public methods
- Type hints throughout
- Inline comments for complex logic

---

## Success Criteria

### MVP (Minimum Viable Product)

- [x] API connectivity verified
- [ ] GreenhouseConnector implementation complete
- [ ] Basic filtering (job ID, status)
- [ ] Resume download working
- [ ] UI configuration page functional
- [ ] End-to-end talent analysis works
- [ ] Basic error handling
- [ ] Unit tests passing

### V1 (Full Feature Set)

- [ ] All filters implemented (tags, dates, prospects)
- [ ] Rate limiting robust
- [ ] Comprehensive error handling
- [ ] Full test coverage (>80%)
- [ ] Documentation complete
- [ ] Monitoring dashboards
- [ ] Performance optimized

### Future Enhancements

- [ ] Incremental sync (delta updates)
- [ ] Webhook integration (real-time updates)
- [ ] Candidate scoring integration
- [ ] Bulk operations (reject/hire via API)
- [ ] Custom field mapping
- [ ] Multi-tenant optimization

---

## Next Immediate Steps

1. ✅ **Verify API connectivity** - DONE
2. 🔲 **Create database migration** - Ready to implement
3. 🔲 **Implement GreenhouseConnector class** - Ready to code
4. 🔲 **Add API routes** - Ready to implement
5. 🔲 **Build frontend component** - Design complete
6. 🔲 **Integration testing** - Plan ready
7. 🔲 **Deploy to dev environment** - After testing

---

## Questions for Clarification

1. **Default Filters:** Should we default to fetching only "active" applications, or all?
   - **Recommendation:** Default to "active" to avoid rejected/hired candidates

2. **Resume Preferences:** If a candidate has multiple resumes, which one to use?
   - **Recommendation:** Use most recent (by `created_at`)

3. **Pagination:** Max candidates per sync?
   - **Recommendation:** 100 default, 1000 max (configurable)

4. **Rate Limiting:** Should we queue syncs or fail fast?
   - **Recommendation:** Implement exponential backoff, fail after 3 retries

5. **Incremental Sync:** Should we support "sync only new candidates"?
   - **Recommendation:** V2 feature - track last_synced_at per connector

---

## Conclusion

This plan provides a comprehensive roadmap for implementing the Greenhouse connector. The architecture leverages the existing connector framework, requires minimal schema changes, and follows established patterns from the PDL and filesystem connectors.

**Estimated Effort:** 10 days (1 engineer)  
**Risk Level:** Low (well-defined API, proven framework)  
**User Impact:** High (direct access to ATS candidates)

Ready to begin implementation! 🚀

