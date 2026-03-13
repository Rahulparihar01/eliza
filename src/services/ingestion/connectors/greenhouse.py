"""
Greenhouse ATS Connector

Fetches candidate resumes from Greenhouse using the Harvest API.
Supports filtering by job, application status, candidate tags, and date ranges.

API Documentation: https://developers.greenhouse.io/harvest.html
"""

import logging
import aiohttp
import re
from typing import List, Dict, Any, Optional, Iterator, Tuple
from datetime import datetime
from urllib.parse import urljoin

from src.services.ingestion.connectors.base import BaseConnector, ConnectorStatus
from src.models.connector import ConnectorConfiguration

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
    
    # Rate limiting (per Greenhouse docs: 50 requests per 10 seconds)
    RATE_LIMIT_CALLS = 50
    RATE_LIMIT_WINDOW = 10  # seconds
    
    def __init__(self, credentials: Dict = None, config: Dict = None, customer_id: str = None):
        """
        Initialize Greenhouse connector.
        
        Args:
            credentials: Decrypted credentials containing api_key
            config: Sync configuration (sync_config from database)
            customer_id: Customer ID for multi-tenant isolation
        """
        # Call parent constructor
        super().__init__(
            credentials=credentials or {},
            config=config or {},
            customer_id=customer_id or ""
        )
        
        # For backwards compatibility, support both 'config' and 'sync_config'
        self._sync_config = config or {}
            
        self.api_key = self._get_api_key()
        self.job_ids = self._parse_job_ids()
        self.application_status = (self._sync_config or {}).get("application_status")
        self.candidate_tags = self._parse_candidate_tags()
        self.created_after = self._parse_created_after()
        self.include_prospects = (self._sync_config or {}).get("include_prospects", False)
        self.max_candidates = (self._sync_config or {}).get("max_candidates", 100)
        
    def _get_api_key(self) -> str:
        """Extract API key from credentials."""
        api_key = self.credentials.get("api_key")
        if not api_key:
            raise ValueError("Greenhouse API key is required")
        return api_key
    
    def _parse_job_ids(self) -> Optional[List[int]]:
        """Parse job IDs from config."""
        job_ids = (self._sync_config or {}).get("job_ids")
        if not job_ids:
            return None
        
        if isinstance(job_ids, list):
            return [int(jid) for jid in job_ids]
        
        # Handle comma-separated string
        return [int(jid.strip()) for jid in str(job_ids).split(",") if jid.strip()]
    
    def _parse_candidate_tags(self) -> Optional[List[str]]:
        """Parse candidate tags from config."""
        tags = (self._sync_config or {}).get("candidate_tags")
        if not tags:
            return None
        
        if isinstance(tags, list):
            return tags
        
        # Handle comma-separated string
        return [tag.strip() for tag in str(tags).split(",") if tag.strip()]
    
    def _parse_created_after(self) -> Optional[datetime]:
        """Parse created_after date from config."""
        created_after = (self._sync_config or {}).get("created_after")
        if not created_after:
            return None
        
        if isinstance(created_after, datetime):
            return created_after
        
        # Parse ISO date string
        return datetime.fromisoformat(str(created_after).replace('Z', '+00:00'))
    
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
        match = re.search(r'page=(\d+)>;\s*rel="next"', link_header)
        if match:
            return int(match.group(1))
        return None
    
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
                # Fetch page of candidates (use max_candidates as per_page for efficiency)
                per_page = min(100, self.max_candidates - candidates_processed)
                response = await self.fetch_candidates(page=page, per_page=per_page)
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
        
        # Download each resume (use most recent if multiple)
        if resume_attachments:
            # Sort by created_at, most recent first
            resume_attachments.sort(
                key=lambda x: x.get("created_at", ""),
                reverse=True
            )
            
            # Take only the most recent resume
            attachment = resume_attachments[0]
            
            try:
                url = attachment.get("url")
                filename = attachment.get("filename", "resume.pdf")
                
                if not url:
                    return resumes
                
                # Download resume
                file_bytes = await self.download_resume(url)
                
                resumes.append({
                    "filename": filename,
                    "file_bytes": file_bytes,
                    "candidate_id": candidate.get("id"),
                    "candidate_name": f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip(),
                    "candidate_email": self._get_primary_email(candidate),
                    "linkedin_url": self._get_linkedin_url(candidate),
                    "phone": self._get_primary_phone(candidate),
                    "location": self._get_location(candidate),
                    "current_title": self._get_current_title(candidate),
                    "current_company": self._get_current_company(candidate),
                    "created_at": attachment.get("created_at"),
                    "metadata": {
                        "source": "greenhouse",
                        "greenhouse_candidate_id": candidate.get("id"),
                        "greenhouse_application_ids": [
                            app.get("id") for app in candidate.get("applications", [])
                        ],
                        "candidate_tags": candidate.get("tags", []),
                        "attachment_type": attachment.get("type"),
                        "fetched_at": datetime.utcnow().isoformat()
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
    
    def _get_linkedin_url(self, candidate: Dict[str, Any]) -> Optional[str]:
        """Extract LinkedIn URL from candidate social media addresses."""
        social_media = candidate.get("social_media_addresses", [])
        for sm in social_media:
            if sm.get("type", "").lower() == "linkedin":
                return sm.get("value")
        return None
    
    def _get_primary_phone(self, candidate: Dict[str, Any]) -> Optional[str]:
        """Extract primary phone number from candidate."""
        phone_numbers = candidate.get("phone_numbers", [])
        if phone_numbers:
            return phone_numbers[0].get("value")
        return None
    
    def _get_location(self, candidate: Dict[str, Any]) -> Optional[str]:
        """Extract location from candidate addresses."""
        addresses = candidate.get("addresses", [])
        if addresses:
            addr = addresses[0]
            parts = []
            if addr.get("city"):
                parts.append(addr["city"])
            if addr.get("state"):
                parts.append(addr["state"])
            if addr.get("country"):
                parts.append(addr["country"])
            return ", ".join(parts) if parts else None
        return None
    
    def _get_current_title(self, candidate: Dict[str, Any]) -> Optional[str]:
        """Extract current job title from candidate employments."""
        employments = candidate.get("employments", [])
        if employments:
            return employments[0].get("title")
        return None
    
    def _get_current_company(self, candidate: Dict[str, Any]) -> Optional[str]:
        """Extract current company from candidate employments."""
        employments = candidate.get("employments", [])
        if employments:
            return employments[0].get("company_name")
        return None
    
    async def get_jobs(
        self, 
        department_ids: Optional[List[int]] = None,
        status_filter: str = "open"
    ) -> List[Dict[str, Any]]:
        """
        Fetch list of jobs from Greenhouse.
        Used for UI dropdowns when configuring the connector.
        
        Args:
            department_ids: Optional list of department IDs to filter by
            status_filter: Job status to filter by: 'open', 'closed', or 'all'
        
        Returns:
            List of job dicts with id, name, status, departments, offices
        """
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            
            params = {"per_page": 500}
            
            async with session.get(
                urljoin(self.BASE_URL, "jobs"),
                auth=auth,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                jobs = await response.json()
                
                result = []
                for job in jobs:
                    job_status = job.get("status", "")
                    
                    # Filter by status
                    if status_filter == "open" and job_status != "open":
                        continue
                    elif status_filter == "closed" and job_status != "closed":
                        continue
                    # 'all' includes all statuses
                    
                    job_dept_ids = [dept["id"] for dept in job.get("departments", [])]
                    
                    # Filter by department if specified
                    if department_ids:
                        if not any(dept_id in job_dept_ids for dept_id in department_ids):
                            continue
                    
                    result.append({
                        "id": job["id"],
                        "name": job["name"],
                        "status": job["status"],
                        "departments": [dept["name"] for dept in job.get("departments", [])],
                        "department_ids": job_dept_ids,
                        "offices": [office["name"] for office in job.get("offices", [])],
                        "closed_at": job.get("closed_at"),  # For historical filtering
                        "opened_at": job.get("opened_at")
                    })
                
                return result
    
    async def get_historical_jobs(
        self,
        department_ids: Optional[List[int]] = None,
        closed_after: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch closed/historical jobs from Greenhouse.
        
        Args:
            department_ids: Optional list of department IDs to filter by
            closed_after: Only include jobs closed after this date (for lookback filtering)
        
        Returns:
            List of closed job dicts
        """
        all_closed_jobs = await self.get_jobs(department_ids=department_ids, status_filter="closed")
        
        # Filter by closed_after date if specified
        if closed_after:
            filtered_jobs = []
            for job in all_closed_jobs:
                closed_at_str = job.get("closed_at")
                if closed_at_str:
                    try:
                        # Parse the closed_at timestamp
                        closed_at = datetime.fromisoformat(closed_at_str.replace('Z', '+00:00'))
                        if closed_at >= closed_after:
                            filtered_jobs.append(job)
                    except (ValueError, TypeError):
                        # If we can't parse the date, include the job
                        filtered_jobs.append(job)
                else:
                    # If no closed_at, include the job
                    filtered_jobs.append(job)
            return filtered_jobs
        
        return all_closed_jobs
    
    async def get_job_details(
        self,
        job_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information for a single job including the full description.
        
        Args:
            job_id: The Greenhouse job ID
            
        Returns:
            Job details dict including description, or None if not found
        """
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            
            try:
                async with session.get(
                    urljoin(self.BASE_URL, f"jobs/{job_id}"),
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 404:
                        logger.warning(f"Job {job_id} not found in Greenhouse")
                        return None
                        
                    response.raise_for_status()
                    job = await response.json()
                    
                    # Extract the job description from various possible fields
                    # Greenhouse stores description as HTML in 'notes' or 'content'
                    description = ""
                    
                    # Try job post content first (most likely to have full description)
                    job_posts = job.get("job_posts", [])
                    if job_posts:
                        for post in job_posts:
                            if post.get("live"):  # Use the live job post
                                description = post.get("content", "")
                                break
                        if not description and job_posts:
                            # Fall back to first post
                            description = job_posts[0].get("content", "")
                    
                    # Also try the keyed_custom_fields or notes
                    if not description:
                        description = job.get("notes", "")
                    
                    # Strip HTML tags for clean text
                    import re
                    if description:
                        # Remove HTML tags
                        description = re.sub(r'<[^>]+>', ' ', description)
                        # Clean up whitespace
                        description = ' '.join(description.split())
                    
                    return {
                        "id": job["id"],
                        "name": job["name"],
                        "status": job.get("status"),
                        "description": description,
                        "departments": [dept["name"] for dept in job.get("departments", [])],
                        "offices": [office["name"] for office in job.get("offices", [])],
                        "requisition_id": job.get("requisition_id"),
                        "opened_at": job.get("opened_at"),
                        "closed_at": job.get("closed_at")
                    }
                    
            except aiohttp.ClientError as e:
                logger.error(f"Failed to fetch job {job_id} from Greenhouse: {e}")
                return None
    
    async def fetch_candidates_from_jobs(
        self,
        job_ids: List[int],
        applied_after: Optional[datetime] = None,
        max_candidates: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch candidates who applied to specific jobs.
        Uses the applications endpoint filtered by job_id.
        
        According to Greenhouse API docs:
        GET /v1/applications?job_id=123 returns applications for that job
        
        Args:
            job_ids: List of job IDs to fetch candidates from
            applied_after: Only include candidates who applied after this date
            max_candidates: Maximum number of candidates to fetch
            
        Returns:
            List of candidate dicts with resume data
        """
        all_candidates = []
        seen_candidate_ids = set()
        
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            
            for job_id in job_ids:
                if len(all_candidates) >= max_candidates:
                    break
                
                page = 1
                while len(all_candidates) < max_candidates:
                    params = {
                        "page": page,
                        "per_page": 100,
                        "job_id": job_id
                    }
                    
                    if applied_after:
                        params["created_after"] = applied_after.isoformat()
                    
                    try:
                        async with session.get(
                            urljoin(self.BASE_URL, "applications"),
                            auth=auth,
                            params=params,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status != 200:
                                logger.warning(f"Failed to fetch applications for job {job_id}: {response.status}")
                                break
                            
                            applications = await response.json()
                            
                            if not applications:
                                break
                            
                            for app in applications:
                                candidate = app.get("candidate", {})
                                candidate_id = candidate.get("id")
                                
                                if not candidate_id or candidate_id in seen_candidate_ids:
                                    continue
                                
                                if len(all_candidates) >= max_candidates:
                                    break
                                
                                seen_candidate_ids.add(candidate_id)
                                
                                # Get full candidate details with attachments
                                candidate_data = await self._fetch_full_candidate(session, auth, candidate_id)
                                if candidate_data:
                                    # Add application context
                                    candidate_data["source_job_id"] = job_id
                                    candidate_data["source_application_id"] = app.get("id")
                                    candidate_data["applied_at"] = app.get("applied_at")
                                    candidate_data["application_status"] = app.get("status")
                                    all_candidates.append(candidate_data)
                            
                            # Check for next page
                            link_header = response.headers.get('Link', '')
                            if 'rel="next"' not in link_header:
                                break
                            
                            page += 1
                            
                    except Exception as e:
                        logger.error(f"Error fetching applications for job {job_id}: {e}")
                        break
        
        logger.info(f"Fetched {len(all_candidates)} candidates from {len(job_ids)} historical jobs")
        return all_candidates
    
    async def _fetch_full_candidate(
        self,
        session: aiohttp.ClientSession,
        auth: aiohttp.BasicAuth,
        candidate_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch full candidate details including attachments.
        
        Args:
            session: aiohttp session
            auth: Basic auth credentials
            candidate_id: Greenhouse candidate ID
            
        Returns:
            Full candidate dict or None if failed
        """
        try:
            async with session.get(
                urljoin(self.BASE_URL, f"candidates/{candidate_id}"),
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Failed to fetch candidate {candidate_id}: {response.status}")
                    return None
        except Exception as e:
            logger.warning(f"Error fetching candidate {candidate_id}: {e}")
            return None
    
    async def fetch_historical_candidates_with_resumes(
        self,
        department_ids: List[int],
        lookback_days: int = 365,
        max_candidates: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch candidates from closed/historical jobs in specified departments.
        
        This is the main method for fetching "previous candidates" - people who
        applied to jobs that are now closed.
        
        Args:
            department_ids: List of department IDs to search
            lookback_days: How far back to look for closed jobs (default 365 days)
            max_candidates: Maximum number of candidates to fetch
            
        Returns:
            List of resume dicts with candidate data (same format as sync())
        """
        from datetime import timedelta
        
        # Calculate the lookback date
        lookback_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Get historical jobs in these departments
        historical_jobs = await self.get_historical_jobs(
            department_ids=department_ids,
            closed_after=lookback_date
        )
        
        if not historical_jobs:
            logger.info(f"No historical jobs found in departments {department_ids} within {lookback_days} days")
            return []
        
        logger.info(f"Found {len(historical_jobs)} historical jobs in departments {department_ids}")
        
        # Get job IDs
        job_ids = [job["id"] for job in historical_jobs]
        
        # Fetch candidates from these jobs
        candidates = await self.fetch_candidates_from_jobs(
            job_ids=job_ids,
            applied_after=lookback_date,
            max_candidates=max_candidates
        )
        
        # Extract resumes from candidates
        results = []
        for candidate in candidates:
            resumes = await self._extract_candidate_resumes(candidate)
            for resume in resumes:
                # Mark as previous candidate
                resume["is_historical"] = True
                resume["source_job_id"] = candidate.get("source_job_id")
                resume["applied_at"] = candidate.get("applied_at")
                results.append(resume)
        
        logger.info(f"Extracted {len(results)} resumes from {len(candidates)} historical candidates")
        return results

    async def get_departments(self) -> List[Dict[str, Any]]:
        """
        Fetch list of departments from Greenhouse with hierarchy.
        
        Returns:
            List of department dicts with id, name, parent_id, child_ids
        """
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            
            async with session.get(
                urljoin(self.BASE_URL, "departments"),
                auth=auth,
                params={"per_page": 500},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                departments = await response.json()
                
                return [
                    {
                        "id": dept["id"],
                        "name": dept["name"],
                        "parent_id": dept.get("parent_id"),
                        "child_ids": dept.get("child_ids", []),
                        "external_id": dept.get("external_id")
                    }
                    for dept in departments
                ]
    
    def get_subordinate_department_ids(
        self, 
        departments: List[Dict[str, Any]], 
        parent_id: int
    ) -> List[int]:
        """
        Get all subordinate department IDs (recursive).
        
        Args:
            departments: List of all departments
            parent_id: Parent department ID to get subordinates for
            
        Returns:
            List of department IDs including parent and all subordinates
        """
        result = [parent_id]
        
        # Find direct children
        for dept in departments:
            if dept.get("parent_id") == parent_id:
                # Recursively get subordinates
                result.extend(self.get_subordinate_department_ids(departments, dept["id"]))
        
        return result
    
    # Abstract method implementations (required by BaseConnector)
    
    async def check_async(self) -> Dict[str, Any]:
        """
        Async version of connection check for use in async contexts.
        
        Returns:
            Dict with status and message
        """
        try:
            # Try to fetch jobs to test connection
            jobs = await self.get_jobs()
            
            return {
                "status": ConnectorStatus.HEALTHY.value,
                "message": f"Successfully connected to Greenhouse. Found {len(jobs)} jobs.",
                "job_count": len(jobs)
            }
        except Exception as e:
            logger.error(f"Greenhouse connection test failed: {e}")
            return {
                "status": ConnectorStatus.UNHEALTHY.value,
                "message": f"Connection failed: {str(e)}"
            }
    
    def check(self) -> Dict[str, Any]:
        """
        Test Greenhouse API connection (sync version).
        
        This method is required by BaseConnector and called by ConnectorService.
        For async contexts, use check_async() instead.
        
        Returns:
            Dict with status and message
        """
        import asyncio
        
        # Run async check in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, run in a thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.check_async())
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(self.check_async())
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.check_async())
    
    def discover(self) -> Dict[str, Any]:
        """
        Discover available streams from Greenhouse.
        
        Returns schema information for the candidate resumes stream.
        """
        return {
            "streams": [{
                "name": "candidates",
                "json_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "file_bytes": {"type": "string", "format": "binary"},
                        "candidate_id": {"type": "integer"},
                        "candidate_name": {"type": "string"},
                        "candidate_email": {"type": "string"},
                        "created_at": {"type": "string", "format": "date-time"},
                        "metadata": {"type": "object"}
                    }
                },
                "supported_sync_modes": ["full_refresh"]
            }]
        }
    
    def read_stream(
        self,
        stream_name: str,
        sync_mode: str,
        cursor_field: Optional[str] = None,
        stream_state: Optional[Dict[str, Any]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Read records from Greenhouse candidates stream.
        
        Yields resume records one at a time.
        """
        # Run async sync and yield results
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(self.sync())
            for resume in results.get("resumes", []):
                yield resume
        finally:
            loop.close()
    
    def validate_config(self) -> Tuple[bool, str]:
        """
        Validate connector configuration.
        
        Checks that API key is valid and filters are correct.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        errors = []
        
        # Validate API key exists
        if not self.api_key:
            errors.append("API key is required")
        
        # Validate max_candidates range
        if self.max_candidates < 1 or self.max_candidates > 1000:
            errors.append("max_candidates must be between 1 and 1000")
        
        # Validate application_status
        if self.application_status and self.application_status not in ["active", "rejected", "hired"]:
            errors.append("application_status must be 'active', 'rejected', or 'hired'")
        
        if errors:
            return False, "; ".join(errors)
        
        return True, "Configuration is valid"
    
    # =========================================================================
    # CANDIDATE CREATION (Add to ATS)
    # =========================================================================
    
    async def add_candidate(
        self,
        first_name: str,
        last_name: str,
        email: str,
        job_id: int,
        on_behalf_of_user_id: int,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        location: Optional[str] = None,
        resume_url: Optional[str] = None,
        resume_content: Optional[bytes] = None,
        resume_filename: Optional[str] = None,
        source_name: str = "Eliza",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a new candidate to Greenhouse and apply them to a job.
        
        Per Greenhouse API docs (https://developers.greenhouse.io/harvest.html#post-add-candidate):
        - POST /v1/candidates
        - Requires On-Behalf-Of header for crediting the user
        - Source is set via the applications.source object
        
        Args:
            first_name: Candidate's first name
            last_name: Candidate's last name
            email: Candidate's email address
            job_id: Job ID to apply the candidate to
            on_behalf_of_user_id: Greenhouse user ID who gets credit for adding
            phone: Optional phone number
            linkedin_url: Optional LinkedIn profile URL
            location: Optional location string
            resume_url: Optional URL to resume (if hosted externally)
            resume_content: Optional resume file bytes (for direct upload)
            resume_filename: Filename for resume upload
            source_name: Source name (default: "Eliza")
            notes: Optional notes to add to the candidate
            
        Returns:
            Dict with created candidate data including greenhouse_id
            
        Raises:
            Exception if API call fails
        """
        # Build the candidate payload
        payload: Dict[str, Any] = {
            "first_name": first_name,
            "last_name": last_name,
            "email_addresses": [
                {
                    "value": email,
                    "type": "personal"
                }
            ],
            "applications": [
                {
                    "job_id": job_id,
                    "source_id": None,  # Will use source object instead
                    "referrer": {
                        "type": "outside",
                        "value": source_name
                    }
                }
            ]
        }
        
        # Add optional phone
        if phone:
            payload["phone_numbers"] = [
                {
                    "value": phone,
                    "type": "mobile"
                }
            ]
        
        # Add LinkedIn URL
        if linkedin_url:
            payload["social_media_addresses"] = [
                {
                    "value": linkedin_url
                }
            ]
        
        # Add location
        if location:
            payload["addresses"] = [
                {
                    "value": location,
                    "type": "home"
                }
            ]
        
        # Add notes
        if notes:
            payload["notes"] = notes
        
        logger.info(
            f"Adding candidate to Greenhouse: {first_name} {last_name} ({email}) for job {job_id}"
        )
        
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            headers = {
                "Content-Type": "application/json",
                "On-Behalf-Of": str(on_behalf_of_user_id)
            }
            
            async with session.post(
                urljoin(self.BASE_URL, "candidates"),
                auth=auth,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_text = await response.text()
                
                if response.status == 201:
                    candidate_data = await response.json()
                    candidate_id = candidate_data.get("id")
                    
                    logger.info(
                        f"Successfully added candidate to Greenhouse: ID {candidate_id}"
                    )
                    
                    # If we have resume content, upload it as an attachment
                    if resume_content and resume_filename:
                        try:
                            await self._add_attachment_to_candidate(
                                candidate_id=candidate_id,
                                file_content=resume_content,
                                filename=resume_filename,
                                on_behalf_of_user_id=on_behalf_of_user_id
                            )
                        except Exception as e:
                            logger.warning(f"Failed to upload resume attachment: {e}")
                    
                    return {
                        "success": True,
                        "greenhouse_id": candidate_id,
                        "candidate_data": candidate_data,
                        "message": f"Candidate added successfully with ID {candidate_id}"
                    }
                else:
                    error_msg = f"Greenhouse API error {response.status}: {response_text}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "status_code": response.status
                    }
    
    async def _add_attachment_to_candidate(
        self,
        candidate_id: int,
        file_content: bytes,
        filename: str,
        on_behalf_of_user_id: int,
        attachment_type: str = "resume"
    ) -> Dict[str, Any]:
        """
        Add an attachment (resume) to an existing candidate.
        
        Per Greenhouse API: POST /v1/candidates/{id}/attachments
        
        Args:
            candidate_id: Greenhouse candidate ID
            file_content: File bytes
            filename: Original filename
            on_behalf_of_user_id: User ID for crediting
            attachment_type: Type of attachment (default: "resume")
            
        Returns:
            API response dict
        """
        import base64
        
        # Greenhouse expects base64-encoded content
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        # Determine content type from filename
        content_type = "application/pdf"
        if filename.lower().endswith(".doc"):
            content_type = "application/msword"
        elif filename.lower().endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        payload = {
            "filename": filename,
            "type": attachment_type,
            "content": encoded_content,
            "content_type": content_type
        }
        
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            headers = {
                "Content-Type": "application/json",
                "On-Behalf-Of": str(on_behalf_of_user_id)
            }
            
            async with session.post(
                urljoin(self.BASE_URL, f"candidates/{candidate_id}/attachments"),
                auth=auth,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)  # Longer timeout for file upload
            ) as response:
                if response.status == 201:
                    return await response.json()
                else:
                    response_text = await response.text()
                    raise Exception(f"Failed to add attachment: {response.status} - {response_text}")
    
    async def get_users(self) -> List[Dict[str, Any]]:
        """
        Fetch list of users from Greenhouse.
        
        Used to find the Greenhouse user ID for the On-Behalf-Of header.
        
        Returns:
            List of user dicts with id, name, email
        """
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.api_key, '')
            
            async with session.get(
                urljoin(self.BASE_URL, "users"),
                auth=auth,
                params={"per_page": 500},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                users = await response.json()
                
                return [
                    {
                        "id": user["id"],
                        "name": user.get("name", ""),
                        "first_name": user.get("first_name", ""),
                        "last_name": user.get("last_name", ""),
                        "email": user.get("primary_email_address", ""),
                        "employee_id": user.get("employee_id")
                    }
                    for user in users
                ]
    
    async def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find a Greenhouse user by email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            User dict if found, None otherwise
        """
        users = await self.get_users()
        email_lower = email.lower()
        
        for user in users:
            if user.get("email", "").lower() == email_lower:
                return user
        
        return None

