"""
Admin Routes - System Administration Endpoints

Includes:
- Resume parsing test tool
- Other admin utilities
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
import structlog

from src.models.database import get_db
from src.middleware.authorization import get_current_user, require_permission
from src.models.auth import User
from src.services.resume_processing.docling_parser import DoclingParser
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# Response Models
class ResumeParsingTestResponse(BaseModel):
    """Response from resume parsing test"""
    success: bool
    filename: str
    file_size: int
    
    # Raw markdown output
    raw_markdown: Optional[str] = None
    
    # Extracted structured data
    contact_info: Dict[str, Optional[str]]
    skills: list[str]
    experience: list[Dict[str, Any]]
    education: list[Dict[str, Any]]
    certifications: list[str]
    summary: Optional[str] = None
    
    # Full parsed resume
    parsed_resume: Dict[str, Any]
    
    # PDL-normalized format
    pdl_format: Dict[str, Any]
    
    # Quality assessment
    quality_assessment: Dict[str, Any]
    
    # Docling output structure
    docling_output: Optional[Dict[str, Any]] = None


@router.post(
    "/test-resume-parsing",
    response_model=ResumeParsingTestResponse,
    summary="Test resume parsing with Docling",
    description="Upload a resume PDF/DOCX and see detailed parsing output for testing and iteration"
)
async def test_resume_parsing(
    file: UploadFile = File(..., description="Resume file (PDF, DOCX, or TXT)"),
    current_user: User = Depends(require_permission("labs:resume_parsing:analyze")),
    db: Session = Depends(get_db)
):
    """
    Test resume parsing endpoint for admin users.
    
    Upload a resume and get back:
    - Raw markdown output from Docling
    - Extracted structured data (contact, skills, experience, education)
    - PDL-normalized format
    - Quality assessment
    - Full Docling output structure
    
    Useful for iterating on parsing quality.
    """
    try:
        logger.info(
            "admin_resume_parsing_test",
            filename=file.filename,
            content_type=file.content_type,
            user_id=current_user.id
        )
        
        # Validate file type
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
            "text/plain",
        ]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, DOCX, DOC, PPTX, PPT, TXT"
            )
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size: 10MB"
            )
        
        # Parse resume
        parser = DoclingParser()
        parsed_resume = parser.parse_resume(file_content, file.filename)
        
        # Extract quality assessment
        quality_issues = []
        if not parsed_resume.full_name:
            quality_issues.append("Name not extracted")
        if not parsed_resume.email:
            quality_issues.append("Email not extracted")
        if len(parsed_resume.skills) == 0:
            quality_issues.append("No skills extracted")
        if len(parsed_resume.experience) == 0:
            quality_issues.append("No work experience extracted")
        if len(parsed_resume.education) == 0:
            quality_issues.append("No education extracted")
        
        quality_assessment = {
            "has_contact_info": bool(parsed_resume.email or parsed_resume.phone),
            "skills_count": len(parsed_resume.skills),
            "experience_count": len(parsed_resume.experience),
            "education_count": len(parsed_resume.education),
            "certifications_count": len(parsed_resume.certifications),
            "issues": quality_issues,
            "quality_score": _calculate_quality_score(parsed_resume)
        }
        
        # Get PDL-normalized format
        pdl_format = parser.normalize_to_pdl_format(parsed_resume)
        
        # Build response
        return ResumeParsingTestResponse(
            success=True,
            filename=file.filename,
            file_size=file_size,
            raw_markdown=parsed_resume.raw_text,
            contact_info={
                "full_name": parsed_resume.full_name,
                "first_name": parsed_resume.first_name,
                "last_name": parsed_resume.last_name,
                "email": parsed_resume.email,
                "phone": parsed_resume.phone,
                "linkedin_url": parsed_resume.linkedin_url,
                "github_url": parsed_resume.github_url,
                "location": parsed_resume.location,
            },
            skills=parsed_resume.skills,
            experience=[exp.dict() for exp in parsed_resume.experience],
            education=[edu.dict() for edu in parsed_resume.education],
            certifications=parsed_resume.certifications,
            summary=parsed_resume.summary,
            parsed_resume=parsed_resume.dict(exclude={"docling_output"}),
            pdl_format=pdl_format,
            quality_assessment=quality_assessment,
            docling_output=parsed_resume.docling_output
        )
        
    except Exception as e:
        logger.error(
            "admin_resume_parsing_test_failed",
            error=str(e),
            filename=file.filename,
            user_id=current_user.id,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}"
        )


def _calculate_quality_score(parsed_resume) -> float:
    """
    Calculate overall quality score (0-100) based on extracted fields.
    """
    score = 0.0
    
    # Contact info (30 points)
    if parsed_resume.full_name:
        score += 10
    if parsed_resume.email:
        score += 10
    if parsed_resume.phone:
        score += 5
    if parsed_resume.linkedin_url or parsed_resume.github_url:
        score += 5
    
    # Skills (20 points)
    if len(parsed_resume.skills) > 0:
        score += min(20, len(parsed_resume.skills) * 2)
    
    # Experience (30 points)
    if len(parsed_resume.experience) > 0:
        score += min(30, len(parsed_resume.experience) * 10)
    
    # Education (15 points)
    if len(parsed_resume.education) > 0:
        score += min(15, len(parsed_resume.education) * 7.5)
    
    # Summary (5 points)
    if parsed_resume.summary:
        score += 5
    
    return round(score, 1)
