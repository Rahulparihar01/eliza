"""
Resume Service

Orchestrates resume storage, parsing, and database persistence.

Workflow:
1. Download resume from URL or receive file bytes
2. Store resume file locally (or S3 in future)
3. Parse resume using DoclingParser
4. Save parsed data to applicants.resume_parsed
5. Update applicant record with parsed_at timestamp
"""
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import hashlib
import requests
from sqlalchemy.orm import Session

import structlog

from src.services.resume_processing.docling_parser import DoclingParser, ParsedResume
from src.models.connector import Applicant

logger = structlog.get_logger(__name__)


class ResumeService:
    """
    Service for storing and parsing resumes.
    
    Handles:
    - File storage (local filesystem)
    - Resume parsing (Docling)
    - Database updates
    """
    
    def __init__(
        self,
        storage_dir: str = "/app/data/resumes",
        db_session: Optional[Session] = None
    ):
        """
        Initialize Resume Service.
        
        Args:
            storage_dir: Directory to store resume files
            db_session: Database session (optional, can be passed per method)
        """
        self.logger = logger.bind(service="resume_service")
        self.storage_dir = Path(storage_dir)
        self.db_session = db_session
        
        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("Resume storage initialized", storage_dir=str(self.storage_dir))
        
        # Initialize parser
        self.parser = DoclingParser()
    
    def download_and_parse_resume(
        self,
        applicant_id: int,
        resume_url: str,
        filename: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Tuple[Optional[ParsedResume], Optional[str]]:
        """
        Download resume from URL, store, parse, and update database.
        
        Args:
            applicant_id: Applicant database ID
            resume_url: URL to download resume from
            filename: Original filename (optional)
            db: Database session (optional, uses self.db_session if not provided)
            
        Returns:
            Tuple of (ParsedResume, stored_file_path) or (None, None) on error
        """
        try:
            self.logger.info(
                "Downloading resume",
                applicant_id=applicant_id,
                resume_url=resume_url
            )
            
            # Download resume
            response = requests.get(resume_url, timeout=30)
            response.raise_for_status()
            resume_bytes = response.content
            
            # Determine filename
            if not filename:
                # Try to get from Content-Disposition header
                content_disposition = response.headers.get('Content-Disposition', '')
                if 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[1].strip('"')
                else:
                    # Generate filename from URL
                    filename = resume_url.split('/')[-1].split('?')[0]
                    if not filename or '.' not in filename:
                        filename = f"resume_{applicant_id}.pdf"
            
            # Store and parse
            return self.store_and_parse_resume(
                applicant_id=applicant_id,
                resume_bytes=resume_bytes,
                filename=filename,
                db=db
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to download resume",
                applicant_id=applicant_id,
                resume_url=resume_url,
                error=str(e)
            )
            return None, None
    
    def store_and_parse_resume(
        self,
        applicant_id: int,
        resume_bytes: bytes,
        filename: str,
        db: Optional[Session] = None
    ) -> Tuple[Optional[ParsedResume], Optional[str]]:
        """
        Store resume file and parse it.
        
        Args:
            applicant_id: Applicant database ID
            resume_bytes: Resume file content
            filename: Original filename
            db: Database session (optional)
            
        Returns:
            Tuple of (ParsedResume, stored_file_path) or (None, None) on error
        """
        try:
            self.logger.info(
                "Storing and parsing resume",
                applicant_id=applicant_id,
                filename=filename
            )
            
            # Store file
            file_path = self._store_resume_file(
                applicant_id=applicant_id,
                resume_bytes=resume_bytes,
                filename=filename
            )
            
            # Parse resume
            parsed_resume = self.parser.parse_resume(
                file_bytes=resume_bytes,
                filename=filename
            )
            
            # Update database
            db_session = db or self.db_session
            if db_session:
                self._update_applicant_resume_data(
                    db=db_session,
                    applicant_id=applicant_id,
                    file_path=file_path,
                    filename=filename,
                    parsed_resume=parsed_resume
                )
            
            self.logger.info(
                "Resume stored and parsed successfully",
                applicant_id=applicant_id,
                file_path=file_path,
                skills_count=len(parsed_resume.skills)
            )
            
            return parsed_resume, file_path
            
        except Exception as e:
            self.logger.error(
                "Failed to store and parse resume",
                applicant_id=applicant_id,
                filename=filename,
                error=str(e)
            )
            return None, None
    
    def _store_resume_file(
        self,
        applicant_id: int,
        resume_bytes: bytes,
        filename: str
    ) -> str:
        """
        Store resume file to local filesystem.
        
        Organization: /app/data/resumes/{applicant_id}/{hash}_{filename}
        
        Args:
            applicant_id: Applicant database ID
            resume_bytes: File content
            filename: Original filename
            
        Returns:
            Stored file path
        """
        # Create applicant-specific directory
        applicant_dir = self.storage_dir / str(applicant_id)
        applicant_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename with hash to avoid duplicates
        file_hash = hashlib.md5(resume_bytes).hexdigest()[:8]
        safe_filename = f"{file_hash}_{filename}"
        
        file_path = applicant_dir / safe_filename
        
        # Write file
        with open(file_path, 'wb') as f:
            f.write(resume_bytes)
        
        self.logger.info(
            "Resume file stored",
            applicant_id=applicant_id,
            file_path=str(file_path),
            file_size=len(resume_bytes)
        )
        
        return str(file_path)
    
    def _update_applicant_resume_data(
        self,
        db: Session,
        applicant_id: int,
        file_path: str,
        filename: str,
        parsed_resume: ParsedResume
    ):
        """
        Update applicant record with resume data.
        
        Args:
            db: Database session
            applicant_id: Applicant database ID
            file_path: Stored file path
            filename: Original filename
            parsed_resume: Parsed resume data
        """
        try:
            # Get applicant
            applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
            
            if not applicant:
                self.logger.error("Applicant not found", applicant_id=applicant_id)
                return
            
            # Update applicant
            applicant.resume_path = file_path
            applicant.resume_filename = filename
            applicant.resume_parsed = parsed_resume.dict()
            applicant.parsed_at = datetime.now()
            
            # Update contact info if not already set
            if not applicant.email and parsed_resume.email:
                applicant.email = parsed_resume.email
            
            if not applicant.phone and parsed_resume.phone:
                applicant.phone = parsed_resume.phone
            
            # Name handling: ATS/HR platform names are AUTHORITATIVE and must never
            # be overwritten by resume parsing. The profile_data JSON field stores 
            # the original data from Greenhouse/ATS. If the ATS provided a name,
            # treat it as the source of truth even if first_name appears empty
            # (could be a timing issue where the ATS name hasn't been set yet).
            ats_has_name = False
            if applicant.profile_data and isinstance(applicant.profile_data, dict):
                ats_first = applicant.profile_data.get("first_name")
                ats_last = applicant.profile_data.get("last_name")
                if ats_first or ats_last:
                    ats_has_name = True
                    # If ATS provided a name but the record is somehow empty, 
                    # restore from ATS data (not from resume parse)
                    if not applicant.first_name and ats_first:
                        applicant.first_name = ats_first
                        self.logger.info(
                            "Restored first_name from ATS profile_data",
                            applicant_id=applicant_id,
                            name=ats_first
                        )
                    if not applicant.last_name and ats_last:
                        applicant.last_name = ats_last
                        self.logger.info(
                            "Restored last_name from ATS profile_data",
                            applicant_id=applicant_id,
                            name=ats_last
                        )
            
            # Only use resume-parsed names if the ATS did not provide any name
            if not ats_has_name:
                if not applicant.first_name and parsed_resume.first_name:
                    applicant.first_name = parsed_resume.first_name
                    self.logger.info(
                        "Set first_name from resume parse (no ATS name available)",
                        applicant_id=applicant_id,
                        name=parsed_resume.first_name
                    )
                
                if not applicant.last_name and parsed_resume.last_name:
                    applicant.last_name = parsed_resume.last_name
                    self.logger.info(
                        "Set last_name from resume parse (no ATS name available)",
                        applicant_id=applicant_id,
                        name=parsed_resume.last_name
                    )
            
            db.commit()
            
            self.logger.info(
                "Applicant record updated with resume data",
                applicant_id=applicant_id
            )
            
        except Exception as e:
            db.rollback()
            self.logger.error(
                "Failed to update applicant record",
                applicant_id=applicant_id,
                error=str(e)
            )
            raise
    
    def parse_resume_file(
        self,
        file_path: str
    ) -> Optional[ParsedResume]:
        """
        Parse an already-stored resume file.
        
        Useful for re-parsing existing resumes.
        
        Args:
            file_path: Path to resume file
            
        Returns:
            ParsedResume or None on error
        """
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                self.logger.error("Resume file not found", file_path=file_path)
                return None
            
            # Read file
            with open(file_path_obj, 'rb') as f:
                resume_bytes = f.read()
            
            # Parse
            parsed_resume = self.parser.parse_resume(
                file_bytes=resume_bytes,
                filename=file_path_obj.name
            )
            
            return parsed_resume
            
        except Exception as e:
            self.logger.error(
                "Failed to parse resume file",
                file_path=file_path,
                error=str(e)
            )
            return None
    
    def batch_parse_applicant_resumes(
        self,
        job_posting_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Parse all resumes for applicants of a job posting.
        
        Useful for bulk processing after syncing from HR platform.
        
        Args:
            job_posting_id: Job posting database ID
            db: Database session
            
        Returns:
            Summary statistics
        """
        try:
            self.logger.info(
                "Batch parsing resumes",
                job_posting_id=job_posting_id
            )
            
            # Get all applicants with resume URLs but not yet parsed
            applicants = db.query(Applicant).filter(
                Applicant.job_posting_id == job_posting_id,
                Applicant.resume_url.isnot(None),
                Applicant.parsed_at.is_(None)
            ).all()
            
            stats = {
                "total_applicants": len(applicants),
                "parsed_successfully": 0,
                "parse_failures": 0,
                "skipped": 0
            }
            
            for applicant in applicants:
                if not applicant.resume_url:
                    stats["skipped"] += 1
                    continue
                
                parsed_resume, file_path = self.download_and_parse_resume(
                    applicant_id=applicant.id,
                    resume_url=applicant.resume_url,
                    filename=applicant.resume_filename,
                    db=db
                )
                
                if parsed_resume:
                    stats["parsed_successfully"] += 1
                else:
                    stats["parse_failures"] += 1
            
            self.logger.info(
                "Batch parsing complete",
                job_posting_id=job_posting_id,
                stats=stats
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(
                "Batch parsing failed",
                job_posting_id=job_posting_id,
                error=str(e)
            )
            return {
                "error": str(e)
            }

