"""
SOW (Statement of Work) API Routes

API endpoints for SOW extraction and generation.
"""
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.middleware.authorization import require_permission
from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory

from src.api.schemas.sow import (
    SowExtractionResponse,
    SowFieldResponse,
    SowAnswerResponse,
    SowUpdateFieldRequest,
    SowUpdateFieldResponse,
    SowGenerateResponse,
    SowDialogueRequest,
    SowDialogueResponse,
    SowSessionResponse,
    SowTemplateListResponse,
)
from src.services.sow import SowService, ExtractedAnswer

logger = get_logger(__name__, LogCategory.API)
settings = get_settings()

router = APIRouter(prefix="/v1/sow", tags=["SOW Generation"])

# In-memory session storage (for MVP - could be moved to Redis later)
_sessions: Dict[str, Dict[str, Any]] = {}

# Default template path
DEFAULT_TEMPLATE_PATH = Path(__file__).parent.parent.parent.parent / "sow-eliza" / "eliza-sow-new.docx"
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "sow-eliza" / "output"


def _ensure_output_dir():
    """Ensure output directory exists."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@router.post(
    "/extract",
    response_model=SowExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract SOW fields from transcript",
    description="Upload a meeting transcript (Fathom JSON or plain text) to extract SOW fields."
)
async def extract_sow_fields(
    transcript: UploadFile = File(..., description="Meeting transcript file (JSON or TXT)"),
    template: Optional[UploadFile] = File(None, description="Optional custom template"),
    db: Session = Depends(get_db),
    current_user = Depends(require_permission(["assistant:access"]))
):
    """
    Extract SOW fields from an uploaded transcript.
    
    Returns a session_id that can be used for interactive review and document generation.
    """
    logger.info(
        "sow_extraction_started",
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        transcript_filename=transcript.filename
    )
    
    try:
        # Read transcript content
        transcript_content = (await transcript.read()).decode("utf-8")
        
        # Determine template path
        if template:
            # Save uploaded template temporarily
            _ensure_output_dir()
            template_bytes = await template.read()
            template_path = OUTPUT_DIR / f"template_{uuid.uuid4().hex[:8]}.docx"
            template_path.write_bytes(template_bytes)
        else:
            template_path = DEFAULT_TEMPLATE_PATH
            if not template_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Default SOW template not found"
                )
        
        # Create service and extract
        service = SowService(db=db, customer_id=current_user.customer_id)
        session_id, fields, answers = service.extract_from_transcript(
            transcript_content=transcript_content,
            transcript_filename=transcript.filename or "transcript.txt",
            template_path=template_path,
        )
        
        # Get meeting info from first answer's context if available
        meeting_title = None
        meeting_date = None
        
        # Store session for later use
        _sessions[session_id] = {
            "template_path": str(template_path),
            "answers": answers,
            "field_status": {tag: "pending" for tag in answers.keys()},
            "fields": fields,
            "meeting_title": meeting_title,
            "meeting_date": meeting_date,
            "created_at": datetime.now(),
            "user_id": current_user.user_id,
            "customer_id": current_user.customer_id,
        }
        
        # Build response
        field_responses = [
            SowFieldResponse(
                tag=f.tag,
                question=f.question,
                source="template"
            )
            for f in fields
            if f.tag != "HIGHLIGHTED_GREEN_TEXTS"
        ]
        
        answer_responses = [
            SowAnswerResponse(
                tag=a.tag,
                value=a.value,
                value_rendered=a.value_rendered,
                confidence=a.confidence,
                reasoning=a.reasoning,
                citations=a.citations,
                followup_question=a.followup_question,
                needs_review=a.needs_review or a.confidence < 0.7,
                status="pending",
            )
            for a in answers.values()
        ]
        
        logger.info(
            "sow_extraction_complete",
            user_id=current_user.user_id,
            session_id=session_id[:8],
            fields_count=len(field_responses),
            answers_count=len(answer_responses)
        )
        
        return SowExtractionResponse(
            session_id=session_id,
            fields=field_responses,
            answers=answer_responses,
            meeting_title=meeting_title,
            meeting_date=meeting_date,
        )
        
    except ValueError as e:
        logger.error(f"SOW extraction failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"SOW extraction error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/update-field",
    response_model=SowUpdateFieldResponse,
    summary="Update a field value",
    description="Update the value and status of an extracted field."
)
async def update_field(
    request: SowUpdateFieldRequest,
    current_user = Depends(require_permission(["assistant:access"]))
):
    """Update a field value in a session."""
    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found. Please run extraction again."
        )
    
    # Verify user owns the session
    if session.get("user_id") != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session"
        )
    
    answer = session["answers"].get(request.tag)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{request.tag}' not found"
        )
    
    # Update the answer
    answer.value = request.value
    answer.value_rendered = request.value
    session["field_status"][request.tag] = request.status
    
    logger.info(
        "sow_field_updated",
        user_id=current_user.user_id,
        session_id=request.session_id[:8],
        field=request.tag,
        status=request.status
    )
    
    return SowUpdateFieldResponse(
        success=True,
        tag=request.tag,
        new_value=request.value,
        status=request.status,
    )


@router.post(
    "/generate/{session_id}",
    response_model=SowGenerateResponse,
    summary="Generate SOW document",
    description="Generate the final SOW document from the reviewed fields."
)
async def generate_document(
    session_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission(["assistant:access"]))
):
    """Generate the final SOW document."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Verify user owns the session
    if session.get("user_id") != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session"
        )
    
    _ensure_output_dir()
    
    template_path = Path(session["template_path"])
    if not template_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template file not found"
        )
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"sow_{session_id[:8]}_{timestamp}.docx"
    
    try:
        service = SowService(db=db, customer_id=current_user.customer_id)
        service.generate_document(
            template_path=template_path,
            answers=session["answers"],
            output_path=output_path,
        )
        
        logger.info(
            "sow_document_generated",
            user_id=current_user.user_id,
            session_id=session_id[:8],
            output_path=str(output_path)
        )
        
        return SowGenerateResponse(
            output_path=str(output_path),
            download_url=f"/v1/sow/download/{output_path.name}",
        )
        
    except Exception as e:
        logger.error(f"Document generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate document: {str(e)}"
        )


@router.get(
    "/download/{filename}",
    summary="Download generated SOW document",
    description="Download a generated SOW document by filename. Accepts token via query param for browser downloads."
)
async def download_document(
    filename: str,
    token: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Download a generated document.
    
    Supports two authentication methods:
    1. Authorization header (for API calls)
    2. Token query parameter (for browser downloads where headers can't be set)
    """
    from src.services.auth_service import auth_service
    
    # Validate token if provided (browser download)
    if token:
        try:
            payload = await auth_service.verify_token(token)
            # Token is valid, proceed with download
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
    else:
        # No token - this will fail without Authorization header
        # Let FastAPI's security handle it
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide token query parameter or Authorization header."
        )
    
    file_path = OUTPUT_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@router.get(
    "/session/{session_id}",
    response_model=SowSessionResponse,
    summary="Get session state",
    description="Get the current state of a SOW extraction session."
)
async def get_session(
    session_id: str,
    current_user = Depends(require_permission(["assistant:access"]))
):
    """Get session state."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Verify user owns the session
    if session.get("user_id") != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session"
        )
    
    return SowSessionResponse(
        session_id=session_id,
        meeting_title=session.get("meeting_title"),
        meeting_date=session.get("meeting_date"),
        field_status=session.get("field_status", {}),
        answers=[
            SowAnswerResponse(
                tag=a.tag,
                value=a.value,
                value_rendered=a.value_rendered,
                confidence=a.confidence,
                reasoning=a.reasoning,
                citations=a.citations,
                status=session.get("field_status", {}).get(a.tag, "pending"),
            )
            for a in session["answers"].values()
        ],
    )


@router.post(
    "/dialogue",
    response_model=SowDialogueResponse,
    summary="Interactive dialogue about a field",
    description="Chat with AI to refine or clarify a field value."
)
async def field_dialogue(
    request: SowDialogueRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission(["assistant:access"]))
):
    """Interactive dialogue to refine field values."""
    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Verify user owns the session
    if session.get("user_id") != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this session"
        )
    
    answer = session["answers"].get(request.tag)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{request.tag}' not found"
        )
    
    # For MVP, return a simple acknowledgment
    # TODO: Implement full dialogue with LLM
    return SowDialogueResponse(
        response=f"I understand you want to discuss the {request.tag} field. The current value is: {answer.value_rendered or 'Not set'}. How would you like to modify it?",
        suggested_answer=None,
    )


@router.get(
    "/templates",
    response_model=SowTemplateListResponse,
    summary="List available templates",
    description="Get a list of available SOW templates."
)
async def list_templates(
    current_user = Depends(require_permission(["assistant:access"]))
):
    """List available SOW templates."""
    templates = []
    
    # Check for default template
    if DEFAULT_TEMPLATE_PATH.exists():
        templates.append({
            "id": "default",
            "name": "Eliza SOW Template",
            "description": "Default Eliza Statement of Work template",
            "path": str(DEFAULT_TEMPLATE_PATH),
        })
    
    return SowTemplateListResponse(templates=templates)
