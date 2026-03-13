"""
Greenhouse Connector

Connects to Greenhouse Harvest API to fetch jobs and applicants.

API Docs: https://developers.greenhouse.io/harvest.html#introduction

Authentication: Basic Auth with API token as username (password is empty)
Base URL: https://harvest.greenhouse.io/v1/

Key Endpoints:
- GET /v1/jobs - List jobs
- GET /v1/jobs/{id} - Get job
- GET /v1/applications - List applications
- GET /v1/applications/{id} - Get application
- GET /v1/candidates/{id} - Get candidate
"""
import base64
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import requests
from urllib.parse import urlencode

from src.services.ingestion.connectors.base_hr_connector import (
    BaseHRConnector,
    JobPostingData,
    ApplicantData
)


class GreenhouseConnector(BaseHRConnector):
    """
    Greenhouse Harvest API connector.
    
    Fetches job postings and applicants from Greenhouse ATS.
    """
    
    def __init__(
        self,
        credentials: Dict[str, Any],
        config: Dict[str, Any],
        customer_id: str
    ):
        """
        Initialize Greenhouse connector.
        
        Args:
            credentials: Must contain {"api_key": "greenhouse_api_token"}
            config: Connector configuration
            customer_id: Customer identifier
        """
        super().__init__(credentials, config, customer_id)
        
        self.base_url = "https://harvest.greenhouse.io/v1"
        self.name = "Greenhouse"
        
        # Pagination defaults
        self.per_page = 100  # Greenhouse default
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get Basic Auth headers for Greenhouse API.
        
        Greenhouse uses Basic Auth with API token as username and empty password.
        Note the trailing colon after the token.
        """
        # Encode "api_token:" with base64
        credential = base64.b64encode(f"{self.api_key}:".encode()).decode()
        
        return {
            "Authorization": f"Basic {credential}",
            "Content-Type": "application/json"
        }
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Greenhouse API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/jobs")
            params: Query parameters
            data: Request body
            
        Returns:
            JSON response as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            elif e.response.status_code == 429:
                # Rate limited
                self.logger.warning("Rate limited by Greenhouse API")
                raise Exception("Rate limit exceeded")
            else:
                self.logger.error(f"Greenhouse API error: {e.response.text}")
                raise
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            raise
    
    def _paginate(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Handle pagination for list endpoints.
        
        Greenhouse uses page-based pagination:
        - ?page=1&per_page=100
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            All results across all pages
        """
        all_results = []
        page = 1
        
        if params is None:
            params = {}
        
        params["per_page"] = self.per_page
        
        while True:
            params["page"] = page
            
            self.logger.debug(f"Fetching page {page} from {endpoint}")
            results = self._make_request("GET", endpoint, params=params)
            
            if not results or len(results) == 0:
                break
            
            all_results.extend(results)
            
            # If we got fewer results than per_page, we're on the last page
            if len(results) < self.per_page:
                break
            
            page += 1
        
        return all_results
    
    def get_jobs(
        self,
        status: Optional[str] = None,
        created_after: Optional[datetime] = None,
        updated_after: Optional[datetime] = None
    ) -> List[JobPostingData]:
        """
        Fetch job postings from Greenhouse.
        
        GET /v1/jobs
        
        Args:
            status: Filter by status (open, closed, draft)
            created_after: Only jobs created after this date
            updated_after: Only jobs updated after this date
            
        Returns:
            List of JobPostingData objects
        """
        params = {}
        
        # Greenhouse filters
        if status:
            params["status"] = status
        if created_after:
            params["created_after"] = created_after.isoformat()
        if updated_after:
            params["updated_after"] = updated_after.isoformat()
        
        jobs_data = self._paginate("/jobs", params=params)
        
        # Convert to JobPostingData
        job_postings = []
        for job in jobs_data:
            job_postings.append(self._parse_job(job))
        
        return job_postings
    
    def get_job(self, external_job_id: str) -> JobPostingData:
        """
        Get a single job posting by ID.
        
        GET /v1/jobs/{id}
        
        Args:
            external_job_id: Greenhouse job ID
            
        Returns:
            JobPostingData object
        """
        job_data = self._make_request("GET", f"/jobs/{external_job_id}")
        
        if not job_data:
            raise Exception(f"Job {external_job_id} not found")
        
        return self._parse_job(job_data)
    
    def _parse_job(self, job_data: Dict[str, Any]) -> JobPostingData:
        """
        Parse Greenhouse job data into JobPostingData.
        
        Greenhouse job object:
        {
          "id": 12345,
          "name": "Software Engineer",
          "status": "open",
          "created_at": "2023-01-01T00:00:00Z",
          "updated_at": "2023-01-02T00:00:00Z",
          "departments": [{"id": 123, "name": "Engineering"}],
          "offices": [{"id": 456, "name": "San Francisco"}],
          "requisition_id": "REQ-123",
          ...
        }
        """
        return JobPostingData(
            external_job_id=str(job_data.get("id")),
            title=job_data.get("name", ""),
            department=job_data.get("departments", [{}])[0].get("name") if job_data.get("departments") else None,
            office=job_data.get("offices", [{}])[0].get("name") if job_data.get("offices") else None,
            description=job_data.get("notes", ""),  # Job description in notes field
            status=job_data.get("status", "open"),
            requirements=job_data.get("custom_fields"),  # Custom fields may contain requirements
            remote_url=f"https://app.greenhouse.io/plans/{job_data.get('id')}",
            created_at=datetime.fromisoformat(job_data.get("created_at").replace("Z", "+00:00")) if job_data.get("created_at") else None,
            updated_at=datetime.fromisoformat(job_data.get("updated_at").replace("Z", "+00:00")) if job_data.get("updated_at") else None,
        )
    
    def get_applicants(
        self,
        external_job_id: str,
        status: Optional[str] = None,
        created_after: Optional[datetime] = None,
        updated_after: Optional[datetime] = None
    ) -> List[ApplicantData]:
        """
        Fetch applicants for a specific job.
        
        GET /v1/applications?job_id={id}
        
        Args:
            external_job_id: Greenhouse job ID
            status: Filter by status
            created_after: Only applicants created after this date
            updated_after: Only applicants updated after this date
            
        Returns:
            List of ApplicantData objects
        """
        params = {"job_id": external_job_id}
        
        if status:
            params["status"] = status
        if created_after:
            params["created_after"] = created_after.isoformat()
        if updated_after:
            params["updated_after"] = updated_after.isoformat()
        
        applications_data = self._paginate("/applications", params=params)
        
        # Convert to ApplicantData
        applicants = []
        for app in applications_data:
            applicants.append(self._parse_application(app, external_job_id))
        
        return applicants
    
    def get_applicant(
        self,
        external_applicant_id: str
    ) -> ApplicantData:
        """
        Get a single applicant by application ID.
        
        GET /v1/applications/{id}
        
        Args:
            external_applicant_id: Greenhouse application ID
            
        Returns:
            ApplicantData object
        """
        app_data = self._make_request("GET", f"/applications/{external_applicant_id}")
        
        if not app_data:
            raise Exception(f"Application {external_applicant_id} not found")
        
        # Get job ID from application
        job_id = None
        if app_data.get("jobs"):
            job_id = str(app_data["jobs"][0]["id"])
        
        return self._parse_application(app_data, job_id)
    
    def _parse_application(self, app_data: Dict[str, Any], job_id: Optional[str] = None) -> ApplicantData:
        """
        Parse Greenhouse application data into ApplicantData.
        
        Greenhouse application object:
        {
          "id": 67890,
          "candidate_id": 12345,
          "prospect": false,
          "applied_at": "2023-01-01T00:00:00Z",
          "last_activity_at": "2023-01-02T00:00:00Z",
          "status": "active",
          "current_stage": {"name": "Phone Screen"},
          "candidate": {
            "id": 12345,
            "first_name": "John",
            "last_name": "Doe",
            "email_addresses": [{"value": "john@example.com"}],
            "phone_numbers": [{"value": "+1234567890"}],
            "attachments": [...]
          },
          ...
        }
        """
        candidate = app_data.get("candidate", {})
        
        # Extract email
        email = None
        if candidate.get("email_addresses"):
            email = candidate["email_addresses"][0].get("value")
        
        # Extract phone
        phone = None
        if candidate.get("phone_numbers"):
            phone = candidate["phone_numbers"][0].get("value")
        
        # Get resume URL from attachments
        resume_url = None
        if candidate.get("attachments"):
            for attachment in candidate["attachments"]:
                if attachment.get("type") == "resume":
                    resume_url = attachment.get("url")
                    break
        
        return ApplicantData(
            external_applicant_id=str(app_data.get("id")),
            external_job_id=job_id or str(app_data.get("jobs", [{}])[0].get("id", "")),
            first_name=candidate.get("first_name"),
            last_name=candidate.get("last_name"),
            email=email,
            phone=phone,
            resume_url=resume_url,
            status=app_data.get("status", "active"),
            current_stage=app_data.get("current_stage", {}).get("name") if app_data.get("current_stage") else None,
            applied_at=datetime.fromisoformat(app_data.get("applied_at").replace("Z", "+00:00")) if app_data.get("applied_at") else None,
            profile_data=candidate  # Store full candidate data
        )
    
    def get_resume(
        self,
        external_applicant_id: str
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download resume/CV for an applicant.
        
        Steps:
        1. Get application to find candidate_id
        2. Get candidate to find resume attachment
        3. Download resume from URL
        
        Args:
            external_applicant_id: Greenhouse application ID
            
        Returns:
            Tuple of (resume_bytes, filename)
        """
        try:
            # Get application
            app_data = self._make_request("GET", f"/applications/{external_applicant_id}")
            
            if not app_data:
                return None, None
            
            # Get candidate
            candidate_id = app_data.get("candidate_id")
            if not candidate_id:
                return None, None
            
            candidate_data = self._make_request("GET", f"/candidates/{candidate_id}")
            
            if not candidate_data:
                return None, None
            
            # Find resume attachment
            resume_url = None
            resume_filename = None
            
            for attachment in candidate_data.get("attachments", []):
                if attachment.get("type") == "resume":
                    resume_url = attachment.get("url")
                    resume_filename = attachment.get("filename")
                    break
            
            if not resume_url:
                self.logger.warning(f"No resume found for applicant {external_applicant_id}")
                return None, None
            
            # Download resume
            response = requests.get(resume_url)
            response.raise_for_status()
            
            return response.content, resume_filename
            
        except Exception as e:
            self.logger.error(f"Failed to download resume: {e}")
            return None, None
    
    def validate_config(self) -> Tuple[bool, str]:
        """
        Validate Greenhouse connector configuration.
        
        Checks:
        - API key is present
        - Configuration is valid
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        errors = []
        
        # Check API key
        if not self.api_key:
            errors.append("API key is required")
        
        # Check base URL is set
        if not self.base_url:
            errors.append("Base URL not configured")
        
        if errors:
            return False, "; ".join(errors)
        
        return True, "Configuration is valid"

