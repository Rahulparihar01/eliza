"""
Document Parsing API Routes

Provides endpoints for parsing various document types (PDF, DOCX, etc.)
using Docling for high-quality text extraction.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List
import tempfile
import os
import uuid
from pathlib import Path

from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings
from src.middleware.authorization import AuthorizationMiddleware
from src.core.auth_context import CurrentUserContext

logger = get_logger(__name__, LogCategory.API)

router = APIRouter(prefix="/document-parsing", tags=["document-parsing"])
auth_middleware = AuthorizationMiddleware()


class ParsedDocumentResponse(BaseModel):
    """Response schema for parsed document."""
    text: str
    filename: str
    file_type: str
    word_count: int


@router.post("/parse", response_model=ParsedDocumentResponse)
async def parse_document(
    file: UploadFile = File(..., description="Document file to parse (PDF, DOCX, TXT)"),
    force_docling: bool = False
):
    """
    Parse a document and extract text content.
    
    Supports:
    - PDF files (using Docling)
    - Text files (direct read)
    - Future: DOCX, DOC, etc.
    
    Set force_docling=True to use Docling instead of simple extraction (for testing/model download).
    
    Returns the extracted text content.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    # Check file type
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    try:
        # Read file content
        content = await file.read()
        
        if file_ext == '.pdf':
            text = await parse_pdf_with_docling(content, file.filename, force_docling=force_docling)
        elif file_ext in ['.txt', '.text']:
            text = content.decode('utf-8')
        elif file_ext in ['.doc', '.docx']:
            from eliza_rag.document_parser import DocumentParser, ParserType
            parser = DocumentParser(parser_type=ParserType.NAIVE)
            mime = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if file_ext == ".docx" else "application/msword"
            )
            parsed = await parser.parse_file(content, file.filename, mime)
            text = parsed.content if parsed.success else ""
        elif file_ext in ['.pptx', '.ppt']:
            from eliza_rag.document_parser import DocumentParser, ParserType
            parser = DocumentParser(parser_type=ParserType.NAIVE)
            mime = (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                if file_ext == ".pptx" else "application/vnd.ms-powerpoint"
            )
            parsed = await parser.parse_file(content, file.filename, mime)
            text = parsed.content if parsed.success else ""
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}. Supported types: PDF, TXT"
            )
        
        # Calculate word count
        word_count = len(text.strip().split())
        
        logger.info(
            "document_parsed",
            filename=file.filename,
            file_type=file_ext,
            word_count=word_count
        )
        
        return ParsedDocumentResponse(
            text=text,
            filename=file.filename,
            file_type=file_ext,
            word_count=word_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse document: {str(e)}"
        )


async def parse_pdf_with_docling(content: bytes, filename: str, force_docling: bool = False) -> str:
    """
    Parse PDF using Docling.
    
    Saves content to a temporary file, uses Docling to parse,
    then cleans up the temp file.
    
    Note: First run will download ML models (~500MB), which can take several minutes.
    Subsequent runs will be much faster (10-30 seconds per PDF).
    """
    import PyPDF2
    from io import BytesIO
    
    # Try simple PyPDF2 extraction first (fast, good for text-based PDFs)
    # Skip if force_docling is True
    if not force_docling:
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(content))
            text_parts = []
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())
            
            simple_text = "\n\n".join(text_parts)
            
            # If we got decent text (more than 100 chars), use it
            if len(simple_text.strip()) > 100:
                logger.info(f"Used simple extraction for {filename} ({len(simple_text)} chars)")
                return simple_text
        except Exception as e:
            logger.warning(f"Simple PDF extraction failed, falling back to Docling: {e}")
    
    # Fall back to Docling for complex PDFs (scanned, images, tables, etc.)
    from docling.document_converter import DocumentConverter
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(content)
    
    try:
        logger.info(f"Using Docling for {filename} (may take 30-60 seconds)")
        
        # Initialize Docling converter
        converter = DocumentConverter()
        
        # Convert PDF to text
        result = converter.convert(tmp_path)
        
        # Extract text from the result
        text = result.document.export_to_markdown()
        
        logger.info(f"Docling extraction complete for {filename} ({len(text)} chars)")
        return text
        
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


class ResumeUploadResponse(BaseModel):
    """Response schema for uploaded resume."""
    filename: str
    stored_filename: str
    file_path: str
    file_size: int


@router.post("/upload-resume", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(..., description="Resume file to upload (PDF, DOC, DOCX)"),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """
    Upload a resume file for analysis.
    
    Stores the file in the uploads directory and returns the stored path.
    The file can later be used in talent analysis.
    
    Supports: PDF, DOC, DOCX
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    # Check file type
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ['.pdf', '.doc', '.docx']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Supported types: PDF, DOC, DOCX"
        )
    
    try:
        settings = get_settings()
        
        # Create upload directory structure
        upload_dir = Path(settings.upload_directory) / current_user.customer_id / "resumes"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename to avoid collisions
        unique_id = uuid.uuid4().hex[:8]
        stored_filename = f"{unique_id}_{file.filename}"
        file_path = upload_dir / stored_filename
        
        # Read and save file
        content = await file.read()
        file_size = len(content)
        
        # Check file size
        max_size = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB"
            )
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        logger.info(
            "resume_uploaded",
            filename=file.filename,
            stored_filename=stored_filename,
            file_size=file_size,
            customer_id=current_user.customer_id
        )
        
        return ResumeUploadResponse(
            filename=file.filename,
            stored_filename=stored_filename,
            file_path=str(file_path),
            file_size=file_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload resume: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload resume: {str(e)}"
        )


class ResumeListResponse(BaseModel):
    """Response schema for listing uploaded resumes."""
    resumes: List[ResumeUploadResponse]
    total: int


@router.get("/resumes", response_model=ResumeListResponse)
async def list_uploaded_resumes(
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """
    List all uploaded resumes for the current customer.
    """
    try:
        settings = get_settings()
        upload_dir = Path(settings.upload_directory) / current_user.customer_id / "resumes"
        
        if not upload_dir.exists():
            return ResumeListResponse(resumes=[], total=0)
        
        resumes = []
        for file_path in upload_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.pdf', '.doc', '.docx']:
                # Extract original filename from stored filename (after the uuid prefix)
                stored_filename = file_path.name
                original_filename = stored_filename[9:] if len(stored_filename) > 9 and stored_filename[8] == '_' else stored_filename
                
                resumes.append(ResumeUploadResponse(
                    filename=original_filename,
                    stored_filename=stored_filename,
                    file_path=str(file_path),
                    file_size=file_path.stat().st_size
                ))
        
        return ResumeListResponse(resumes=resumes, total=len(resumes))
        
    except Exception as e:
        logger.error(f"Failed to list resumes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list resumes: {str(e)}"
        )
