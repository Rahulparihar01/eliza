"""
FileSystem Connector for reading resumes from local directories.

This connector treats a directory of resume files as a data source,
creating dummy applicants for each resume file found. Perfect for
testing the full pipeline without external dependencies.
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Iterator, Tuple
from datetime import datetime

from src.services.ingestion.connectors.base_hr_connector import (
    BaseHRConnector,
    JobPostingData,
    ApplicantData
)

logger = logging.getLogger(__name__)


class FileSystemConnector(BaseHRConnector):
    """
    Connector for reading resumes from a local filesystem directory.
    
    Configuration:
    {
        "directory_path": "/path/to/resumes",
        "file_extensions": [".pdf", ".docx", ".txt"],  # Optional
        "recursive": false  # Optional, scan subdirectories
    }
    
    Creates a dummy "Test Job Posting" and generates applicants for each resume file.
    """
    
    def __init__(self, credentials: Dict[str, Any], config: Dict[str, Any], customer_id: str):
        """
        Initialize FileSystem connector.
        
        Args:
            credentials: Not used for filesystem, but kept for interface consistency
            config: Must contain 'directory_path'
            customer_id: Customer identifier
        """
        # FileSystem doesn't need API key, so we set a dummy one to satisfy BaseHRConnector
        if not credentials:
            credentials = {}
        if "api_key" not in credentials:
            credentials["api_key"] = "filesystem_no_auth_required"
        
        super().__init__(credentials, config, customer_id)
        
        # Get directory path from config
        self.directory_path = config.get("directory_path")
        if not self.directory_path:
            raise ValueError("directory_path is required in config")
        
        # Convert to absolute path
        self.directory_path = Path(self.directory_path).resolve()
        
        # Get file extensions to scan (default to common resume formats)
        self.file_extensions = config.get("file_extensions", [".pdf", ".docx", ".txt", ".doc"])
        
        # Whether to scan subdirectories
        self.recursive = config.get("recursive", False)
        
        logger.info(
            f"FileSystemConnector initialized",
            extra={
                "directory": str(self.directory_path),
                "extensions": self.file_extensions,
                "recursive": self.recursive
            }
        )
    
    def check(self) -> Dict[str, Any]:
        """
        Check if directory exists and is readable.
        
        Required by BaseConnector interface.
        
        Returns:
            Dict with status and metadata
        """
        try:
            if not self.directory_path.exists():
                return {
                    "status": "unhealthy",
                    "message": f"Directory does not exist: {self.directory_path}",
                    "metadata": {}
                }
            
            if not self.directory_path.is_dir():
                return {
                    "status": "unhealthy",
                    "message": f"Path is not a directory: {self.directory_path}",
                    "metadata": {}
                }
            
            if not os.access(self.directory_path, os.R_OK):
                return {
                    "status": "unhealthy",
                    "message": f"Directory is not readable: {self.directory_path}",
                    "metadata": {}
                }
            
            # Count resume files
            resume_files = self._list_resume_files()
            file_count = len(resume_files)
            
            return {
                "status": "healthy",
                "message": f"Found {file_count} resume files in {self.directory_path}",
                "metadata": {
                    "directory": str(self.directory_path),
                    "file_count": file_count,
                    "extensions": self.file_extensions,
                    "sample_files": [f.name for f in resume_files[:5]]
                }
            }
        except Exception as e:
            logger.exception("FileSystem connection check failed")
            return {
                "status": "unhealthy",
                "message": f"Connection check failed: {str(e)}",
                "metadata": {}
            }
    
    def discover(self) -> Dict[str, Any]:
        """
        Discover available streams and schemas.
        
        Required by BaseConnector interface.
        
        Returns:
            Dict describing available streams
        """
        return {
            "streams": [
                {
                    "name": "job_postings",
                    "supported_sync_modes": ["full"],
                    "json_schema": {
                        "type": "object",
                        "properties": {
                            "external_job_id": {"type": "string"},
                            "title": {"type": "string"},
                            "department": {"type": "string"},
                            "office": {"type": "string"},
                            "description": {"type": "string"},
                            "status": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "applicants",
                    "supported_sync_modes": ["full"],
                    "json_schema": {
                        "type": "object",
                        "properties": {
                            "external_applicant_id": {"type": "string"},
                            "job_id": {"type": "string"},
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "email": {"type": "string"},
                            "resume_filename": {"type": "string"},
                            "applied_at": {"type": "string", "format": "date-time"},
                            "status": {"type": "string"}
                        }
                    }
                }
            ]
        }
    
    def read_job_postings(
        self,
        status: Optional[str] = None,
        created_after: Optional[datetime] = None
    ) -> Iterator[JobPostingData]:
        """
        Generate a single dummy job posting for the test data.
        
        Args:
            status: Not used
            created_after: Not used
            
        Yields:
            JobPostingData for a test job
        """
        # Create a single dummy job posting for all resumes
        yield JobPostingData(
            external_job_id="filesystem_test_job_001",
            title="Test Job - Resume Analysis",
            department="Testing",
            office="Local",
            description="Dummy job posting for filesystem-based resume testing. "
                       "All resumes from the filesystem will be associated with this job.",
            status="open",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            custom_fields={
                "source": "filesystem",
                "directory": str(self.directory_path)
            }
        )
    
    def read_applicants(
        self,
        job_id: str,
        status: Optional[str] = None,
        updated_after: Optional[datetime] = None
    ) -> Iterator[ApplicantData]:
        """
        Generate applicants from resume files in the directory.
        
        Args:
            job_id: Job ID (should be "filesystem_test_job_001")
            status: Not used
            updated_after: Not used
            
        Yields:
            ApplicantData for each resume file
        """
        resume_files = self._list_resume_files()
        
        logger.info(
            f"Reading applicants from filesystem",
            extra={
                "job_id": job_id,
                "file_count": len(resume_files)
            }
        )
        
        for idx, file_path in enumerate(resume_files, start=1):
            try:
                # Get file metadata
                stat = file_path.stat()
                created_at = datetime.fromtimestamp(stat.st_ctime)
                
                # Generate applicant ID from filename
                external_applicant_id = f"fs_{file_path.stem}_{idx}"
                
                # Extract name from filename if possible (e.g., "resume_john_doe.pdf")
                filename_parts = file_path.stem.replace("_", " ").split()
                first_name = filename_parts[1] if len(filename_parts) > 1 else "Test"
                last_name = filename_parts[2] if len(filename_parts) > 2 else f"Applicant{idx:03d}"
                
                yield ApplicantData(
                    external_applicant_id=external_applicant_id,
                    job_id=job_id,
                    first_name=first_name,
                    last_name=last_name,
                    email=f"{external_applicant_id}@filesystem.local",
                    phone=None,
                    resume_url=None,  # We'll use local path instead
                    resume_filename=file_path.name,
                    applied_at=created_at,
                    updated_at=created_at,
                    status="new",
                    current_stage="Application Review",
                    profile_data={
                        "source": "filesystem",
                        "file_path": str(file_path),
                        "file_size": stat.st_size,
                        "file_extension": file_path.suffix
                    }
                )
            except Exception as e:
                logger.error(
                    f"Error reading file metadata: {file_path}",
                    extra={"error": str(e)}
                )
                continue
    
    def download_resume(self, applicant_id: str, applicant_data: ApplicantData) -> Optional[bytes]:
        """
        Read resume file from filesystem.
        
        Args:
            applicant_id: Applicant identifier
            applicant_data: Applicant data containing file_path in profile_data
            
        Returns:
            Resume file bytes
        """
        try:
            # Get file path from profile_data
            file_path_str = applicant_data.profile_data.get("file_path")
            if not file_path_str:
                logger.error(f"No file_path in profile_data for applicant {applicant_id}")
                return None
            
            file_path = Path(file_path_str)
            
            if not file_path.exists():
                logger.error(f"Resume file not found: {file_path}")
                return None
            
            # Read file content
            with open(file_path, 'rb') as f:
                content = f.read()
            
            logger.info(
                f"Read resume file",
                extra={
                    "applicant_id": applicant_id,
                    "file_path": str(file_path),
                    "size": len(content)
                }
            )
            
            return content
        except Exception as e:
            logger.exception(f"Error reading resume file for applicant {applicant_id}")
            return None
    
    def _list_resume_files(self) -> List[Path]:
        """
        List all resume files in the directory.
        
        Returns:
            List of Path objects for resume files
        """
        resume_files = []
        
        if self.recursive:
            # Scan recursively
            for ext in self.file_extensions:
                resume_files.extend(self.directory_path.rglob(f"*{ext}"))
        else:
            # Scan only top-level directory
            for ext in self.file_extensions:
                resume_files.extend(self.directory_path.glob(f"*{ext}"))
        
        # Sort by filename for consistent ordering
        resume_files.sort()
        
        return resume_files
    
    # Abstract methods from BaseHRConnector
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        No auth headers needed for filesystem.
        
        Returns:
            Empty dict
        """
        return {}
    
    def get_jobs(
        self,
        status: Optional[str] = None,
        created_after: Optional[datetime] = None,
        updated_after: Optional[datetime] = None
    ) -> List[JobPostingData]:
        """
        Get job postings (returns single dummy job for filesystem).
        
        Args:
            status: Not used
            created_after: Not used
            updated_after: Not used
            
        Returns:
            List containing one dummy job posting
        """
        return list(self.read_job_postings(status, created_after))
    
    def get_job(self, external_job_id: str) -> JobPostingData:
        """
        Get a single job by ID.
        
        Args:
            external_job_id: Job ID
            
        Returns:
            JobPostingData
        """
        # FileSystem only has one job
        jobs = self.get_jobs()
        if jobs and jobs[0].external_job_id == external_job_id:
            return jobs[0]
        raise ValueError(f"Job not found: {external_job_id}")
    
    def get_applicants(
        self,
        external_job_id: str,
        status: Optional[str] = None,
        created_after: Optional[datetime] = None,
        updated_after: Optional[datetime] = None
    ) -> List[ApplicantData]:
        """
        Get applicants for a job.
        
        Args:
            external_job_id: Job ID
            status: Not used
            created_after: Not used
            updated_after: Not used
            
        Returns:
            List of ApplicantData
        """
        return list(self.read_applicants(external_job_id, status, updated_after))
    
    def get_applicant(self, external_applicant_id: str) -> ApplicantData:
        """
        Get a single applicant by ID.
        
        Args:
            external_applicant_id: Applicant ID
            
        Returns:
            ApplicantData
        """
        # Fetch all applicants and find matching one
        all_applicants = self.get_applicants("filesystem_test_job_001")
        for applicant in all_applicants:
            if applicant.external_applicant_id == external_applicant_id:
                return applicant
        raise ValueError(f"Applicant not found: {external_applicant_id}")
    
    def get_resume(self, external_applicant_id: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download resume for an applicant.
        
        Args:
            external_applicant_id: Applicant ID
            
        Returns:
            Tuple of (resume_bytes, filename)
        """
        try:
            applicant = self.get_applicant(external_applicant_id)
            resume_bytes = self.download_resume(external_applicant_id, applicant)
            if resume_bytes:
                return resume_bytes, applicant.resume_filename
            return None, None
        except Exception as e:
            logger.error(f"Failed to get resume for {external_applicant_id}: {e}")
            return None, None
    
    def read_stream(
        self,
        sync_mode: str,
        sync_params: Dict[str, Any]
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Stream records from filesystem connector.
        
        Required by BaseConnector interface.
        
        Args:
            sync_mode: "full" or "incremental"
            sync_params: Sync parameters (e.g., checkpoint, max_records)
            
        Yields:
            Batches of records
        """
        # Get the job first
        jobs = self.get_jobs()
        if not jobs:
            logger.warning("No jobs found in filesystem connector")
            return
        
        job = jobs[0]
        
        # Yield job posting as first batch
        yield [job.dict()]
        
        # Yield applicants in batches of 10
        applicants = self.get_applicants(job.external_job_id)
        batch_size = 10
        batch = []
        
        for applicant in applicants:
            batch.append(applicant.dict())
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        # Yield remaining applicants
        if batch:
            yield batch
    
    # Abstract method from BaseConnector
    
    def validate_config(self) -> Tuple[bool, str]:
        """
        Validate filesystem connector configuration.
        
        Returns:
            (is_valid, error_message)
        """
        # Check directory_path is provided
        if not self.config.get("directory_path"):
            return False, "directory_path is required in configuration"
        
        # Check directory exists
        directory = Path(self.config["directory_path"])
        if not directory.exists():
            return False, f"Directory does not exist: {directory}"
        
        if not directory.is_dir():
            return False, f"Path is not a directory: {directory}"
        
        if not os.access(directory, os.R_OK):
            return False, f"Directory is not readable: {directory}"
        
        return True, ""

