"""
Base HR Connector

Abstract base class for HR/ATS platform connectors (Greenhouse, Lever, Workday, BambooHR).

Provides common interface for:
- Fetching job postings
- Retrieving applicants per job
- Downloading resumes/CVs
- Getting applicant metadata
"""
from abc import abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import requests
from pydantic import BaseModel

from src.services.ingestion.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class JobPostingData(BaseModel):
    """Standardized job posting data from HR platforms"""
    external_job_id: str
    title: str
    department: Optional[str] = None
    office: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[Dict[str, Any]] = None
    status: str = "open"
    remote_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ApplicantData(BaseModel):
    """Standardized applicant data from HR platforms"""
    external_applicant_id: str
    external_job_id: str  # Links to job posting
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    resume_url: Optional[str] = None  # URL to download resume
    status: str = "new"
    current_stage: Optional[str] = None
    applied_at: Optional[datetime] = None
    profile_data: Optional[Dict[str, Any]] = None  # Platform-specific data


class BaseHRConnector(BaseConnector):
    """
    Base class for all HR/ATS platform connectors.
    
    Extends BaseConnector with HR-specific methods for:
    - Job postings
    - Applicants
    - Resumes
    
    Each platform connector (Greenhouse, Lever, etc.) implements these methods.
    """
    
    def __init__(
        self,
        credentials: Dict[str, Any],
        config: Dict[str, Any],
        customer_id: str
    ):
        """
        Initialize HR connector.
        
        Args:
            credentials: API credentials (e.g., {"api_key": "xyz"})
            config: Connector configuration
            customer_id: Customer identifier
        """
        super().__init__(credentials, config, customer_id)
        
        # HR connector specific initialization
        self.api_key = credentials.get("api_key")
        if not self.api_key:
            raise ValueError("API key is required for HR connector")
        
        # Platform-specific base URL (set by subclasses)
        self.base_url: Optional[str] = None
        
        # Session for requests
        self.session = requests.Session()
        self.session.headers.update(self._get_auth_headers())
        
        # Logger for subclasses
        self.logger = logger
    
    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests.
        
        Returns:
            Dictionary of HTTP headers
        """
        pass
    
    @abstractmethod
    def get_jobs(
        self,
        status: Optional[str] = None,
        created_after: Optional[datetime] = None,
        updated_after: Optional[datetime] = None
    ) -> List[JobPostingData]:
        """
        Fetch job postings from HR platform.
        
        Args:
            status: Filter by job status (open, closed, draft)
            created_after: Only jobs created after this date
            updated_after: Only jobs updated after this date
            
        Returns:
            List of JobPostingData objects
        """
        pass
    
    @abstractmethod
    def get_job(self, external_job_id: str) -> JobPostingData:
        """
        Get a single job posting by ID.
        
        Args:
            external_job_id: Job ID in the HR platform
            
        Returns:
            JobPostingData object
        """
        pass
    
    @abstractmethod
    def get_applicants(
        self,
        external_job_id: str,
        status: Optional[str] = None,
        created_after: Optional[datetime] = None,
        updated_after: Optional[datetime] = None
    ) -> List[ApplicantData]:
        """
        Fetch applicants for a specific job.
        
        Args:
            external_job_id: Job ID in the HR platform
            status: Filter by applicant status
            created_after: Only applicants who applied after this date
            updated_after: Only applicants updated after this date
            
        Returns:
            List of ApplicantData objects
        """
        pass
    
    @abstractmethod
    def get_applicant(
        self,
        external_applicant_id: str
    ) -> ApplicantData:
        """
        Get a single applicant by ID.
        
        Args:
            external_applicant_id: Applicant ID in the HR platform
            
        Returns:
            ApplicantData object
        """
        pass
    
    @abstractmethod
    def get_resume(
        self,
        external_applicant_id: str
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download resume/CV for an applicant.
        
        Args:
            external_applicant_id: Applicant ID in the HR platform
            
        Returns:
            Tuple of (resume_bytes, filename)
            Returns (None, None) if resume not available
        """
        pass
    
    def check(self) -> Dict[str, Any]:
        """
        Test connection to HR platform.
        
        Attempts to make a simple API call to verify credentials.
        
        Returns:
            Dict with status and message
        """
        try:
            # Try to fetch jobs to verify connection
            jobs = self.get_jobs()
            return {
                "status": "healthy",
                "message": f"Connected successfully. Found {len(jobs)} jobs.",
                "metadata": {"job_count": len(jobs)}
            }
        except Exception as e:
            self.logger.error(f"Connection check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Connection failed: {str(e)}"
            }
    
    def validate_config(self) -> Tuple[bool, str]:
        """
        Validate HR connector configuration.
        
        Default implementation checks for API key.
        Subclasses can override for more specific validation.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.api_key:
            return False, "API key is required"
        
        return True, "Configuration is valid"
    
    def discover(self) -> Dict[str, Any]:
        """
        Discover available jobs and their schema.
        
        Returns:
            Schema information about available jobs
        """
        try:
            jobs = self.get_jobs()
            
            return {
                "jobs_count": len(jobs),
                "sample_job": jobs[0].dict() if jobs else None,
                "supported_filters": [
                    "status",
                    "created_after",
                    "updated_after",
                ],
            }
        except Exception as e:
            self.logger.error(f"Discovery failed: {e}")
            return {"error": str(e)}
    
    def read_stream(
        self,
        external_job_id: str,
        state: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Stream applicants for a specific job.
        
        Args:
            external_job_id: Job ID to fetch applicants for
            state: Incremental sync state (e.g., last sync timestamp)
            
        Returns:
            Tuple of (applicants, updated_state)
        """
        try:
            # Get last sync timestamp from state
            last_sync = None
            if state and "last_sync_timestamp" in state:
                last_sync = datetime.fromisoformat(state["last_sync_timestamp"])
            
            # Fetch applicants updated since last sync
            applicants = self.get_applicants(
                external_job_id=external_job_id,
                updated_after=last_sync
            )
            
            # Convert to dict format
            records = [applicant.dict() for applicant in applicants]
            
            # Update state with current timestamp
            new_state = {
                "last_sync_timestamp": datetime.now().isoformat(),
                "records_synced": len(records)
            }
            
            return records, new_state
            
        except Exception as e:
            self.logger.error(f"Stream read failed: {e}")
            raise

