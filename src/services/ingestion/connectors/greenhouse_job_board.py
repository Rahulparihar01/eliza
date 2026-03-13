"""
Greenhouse Job Board API Connector

This connector is specifically for submitting external candidates to Greenhouse
job postings via the Job Board API. This is different from the Harvest API,
which is used for reading internal candidate data.

Job Board API Documentation:
https://developers.greenhouse.io/job-board.html

Key Differences from Harvest API:
- Job Board API: POST candidates to specific jobs (applicant submission)
- Harvest API: GET candidates, jobs, applications (internal data reading)
- Different authentication and rate limits
"""

import aiohttp
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class GreenhouseJobBoardConnector:
    """
    Greenhouse Job Board API connector for submitting external candidates.
    
    This connector enables:
    1. Listing available job postings
    2. Submitting candidates to specific jobs
    3. Uploading resumes with candidate submissions
    """
    
    BASE_URL = "https://boards-api.greenhouse.io/v1/"
    
    def __init__(
        self,
        api_key: str,
        board_token: Optional[str] = None,
        customer_id: str = None
    ):
        """
        Initialize Greenhouse Job Board connector.
        
        Args:
            api_key: Greenhouse Job Board API key
            board_token: Optional board token for specific job board
            customer_id: Customer ID for multi-tenancy
        """
        self.api_key = api_key
        self.board_token = board_token
        self.customer_id = customer_id
        
    async def list_jobs(
        self,
        board_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all active job postings from the job board.
        
        Args:
            board_token: Optional board token (uses instance token if not provided)
            
        Returns:
            List of job dictionaries with id, title, location, etc.
        """
        token = board_token or self.board_token
        
        if not token:
            logger.warning("No board token provided, attempting to use API key")
            # Some organizations might allow listing jobs with just API key
            token = self.api_key
        
        async with aiohttp.ClientSession() as session:
            url = urljoin(self.BASE_URL, f"boards/{token}/jobs")
            
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    jobs = data.get("jobs", [])
                    logger.info(f"Retrieved {len(jobs)} jobs from Greenhouse Job Board")
                    
                    return jobs
                    
            except aiohttp.ClientResponseError as e:
                if e.status == 404:
                    logger.error(f"Board not found with token: {token}")
                    raise ValueError(f"Invalid board token: {token}")
                elif e.status == 401:
                    logger.error("Unauthorized - invalid API credentials")
                    raise ValueError("Invalid Greenhouse Job Board API credentials")
                else:
                    logger.error(f"Failed to list jobs: {e.status} - {e.message}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error listing jobs: {e}", exc_info=True)
                raise
    
    async def submit_candidate(
        self,
        job_id: int,
        first_name: str,
        last_name: str,
        email: str,
        resume_content: Optional[bytes] = None,
        resume_filename: Optional[str] = None,
        phone: Optional[str] = None,
        location: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        website: Optional[str] = None,
        cover_letter: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Submit a candidate application to a specific Greenhouse job.
        
        Args:
            job_id: Greenhouse job ID
            first_name: Candidate's first name
            last_name: Candidate's last name
            email: Candidate's email address
            resume_content: Resume file content (bytes)
            resume_filename: Resume filename (e.g., "resume.pdf")
            phone: Candidate's phone number
            location: Candidate's location
            linkedin_url: LinkedIn profile URL
            website: Personal website URL
            cover_letter: Cover letter text
            custom_fields: Additional custom fields for the application
            
        Returns:
            Response from Greenhouse API with application ID
        """
        async with aiohttp.ClientSession() as session:
            url = urljoin(self.BASE_URL, f"boards/{self.board_token}/jobs/{job_id}")
            
            # Prepare form data
            data = aiohttp.FormData()
            data.add_field("first_name", first_name)
            data.add_field("last_name", last_name)
            data.add_field("email", email)
            
            # Add optional fields
            if phone:
                data.add_field("phone", phone)
            if location:
                data.add_field("location", location)
            if linkedin_url:
                data.add_field("question_12345", linkedin_url)  # LinkedIn question ID
            if website:
                data.add_field("website", website)
            if cover_letter:
                data.add_field("cover_letter", cover_letter)
            
            # Add resume if provided
            if resume_content and resume_filename:
                data.add_field(
                    "resume",
                    resume_content,
                    filename=resume_filename,
                    content_type="application/pdf"
                )
            
            # Add custom fields
            if custom_fields:
                for key, value in custom_fields.items():
                    data.add_field(key, str(value))
            
            # Add API key for authentication
            headers = {
                "On-Behalf-Of": self.api_key  # Job Board API uses this header
            }
            
            try:
                async with session.post(url, data=data, headers=headers) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    logger.info(
                        f"Successfully submitted candidate {first_name} {last_name} "
                        f"to job {job_id}"
                    )
                    
                    return {
                        "success": True,
                        "application_id": result.get("id"),
                        "message": f"Candidate submitted successfully to job {job_id}",
                        "greenhouse_response": result
                    }
                    
            except aiohttp.ClientResponseError as e:
                logger.error(
                    f"Failed to submit candidate: {e.status} - {e.message}",
                    exc_info=True
                )
                
                if e.status == 422:
                    error_msg = "Validation error - check required fields"
                elif e.status == 401:
                    error_msg = "Invalid API credentials"
                elif e.status == 404:
                    error_msg = f"Job {job_id} not found"
                else:
                    error_msg = f"Submission failed: {e.message}"
                
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": e.status
                }
                
            except Exception as e:
                logger.error(f"Unexpected error submitting candidate: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def get_job_details(
        self,
        job_id: int,
        board_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific job.
        
        Args:
            job_id: Greenhouse job ID
            board_token: Optional board token
            
        Returns:
            Job details including requirements, questions, etc.
        """
        token = board_token or self.board_token
        
        async with aiohttp.ClientSession() as session:
            url = urljoin(self.BASE_URL, f"boards/{token}/jobs/{job_id}")
            
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    job_data = await response.json()
                    
                    logger.info(f"Retrieved details for job {job_id}")
                    return job_data
                    
            except aiohttp.ClientResponseError as e:
                logger.error(f"Failed to get job details: {e.status} - {e.message}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error getting job details: {e}", exc_info=True)
                raise
    
    async def check_connection(self) -> bool:
        """
        Test the connection to Greenhouse Job Board API.
        
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            # Try to list jobs as a connection test
            jobs = await self.list_jobs()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

