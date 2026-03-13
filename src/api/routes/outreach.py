"""
Candidate Outreach API Routes

API endpoints for tracking email engagement and managing outreach emails.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import Response, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import base64
import csv
import io

from src.models import get_db
from src.models.email_tracking import OutreachEmail, EmailOpen, EmailClick, EmailReply
from src.models.connector import ConnectorConfiguration
from src.models.candidate import Candidate, CandidateAnalysisScore, CandidateScoreFeedback
from src.services.email_tracking_service import EmailTrackingService
from src.services.greenhouse_profile_service import GreenhouseProfileService
from src.services.candidate_service import CandidateService
from src.services.email_generation_service import EmailGenerationService
from src.middleware.authorization import AuthorizationMiddleware
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.API)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/api/v1/outreach", tags=["Candidate Outreach"])


# 1x1 transparent PNG pixel for email open tracking
TRACKING_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@router.get(
    "/track/open/{email_id}",
    summary="Track email open",
    description="Public endpoint for tracking email opens via 1x1 pixel image. Returns transparent PNG.",
    response_class=Response
)
async def track_email_open(
    email_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Track email open event.
    
    This endpoint is called when an email is opened (via tracking pixel).
    Returns a 1x1 transparent PNG image.
    """
    try:
        # Get client IP address
        ip_address = request.client.host if request.client else None
        # Check for forwarded IP (common in production)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        
        # Get user agent
        user_agent = request.headers.get("User-Agent")
        
        # Record the open
        tracking_service = EmailTrackingService(db)
        tracking_service.record_email_open(
            email_id=email_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Return 1x1 transparent PNG
        return Response(
            content=TRACKING_PIXEL,
            media_type="image/png",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    
    except ValueError as e:
        # Email not found - still return pixel to avoid breaking email rendering
        logger.warning(
            "email_open_tracking_failed",
            email_id=email_id,
            error=str(e)
        )
        return Response(
            content=TRACKING_PIXEL,
            media_type="image/png"
        )
    except Exception as e:
        logger.error(
            "email_open_tracking_error",
            email_id=email_id,
            error=str(e),
            exc_info=True
        )
        # Still return pixel to avoid breaking email rendering
        return Response(
            content=TRACKING_PIXEL,
            media_type="image/png"
        )


@router.get(
    "/track/click/{email_id}/{link_position}",
    summary="Track email link click",
    description="Public endpoint for tracking email link clicks. Redirects to original URL.",
    response_class=RedirectResponse
)
async def track_email_click(
    email_id: str,
    link_position: int,
    url: str = Query(..., description="Original destination URL"),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Track email link click event.
    
    This endpoint is called when a link in an email is clicked.
    Records the click and redirects to the original URL.
    """
    try:
        # Get client IP address
        ip_address = request.client.host if request.client else None
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        
        # Get user agent
        user_agent = request.headers.get("User-Agent")
        
        # Record the click
        tracking_service = EmailTrackingService(db)
        tracking_service.record_email_click(
            email_id=email_id,
            link_url=url,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Redirect to original URL
        return RedirectResponse(url=url, status_code=302)
    
    except ValueError as e:
        # Email not found - still redirect
        logger.warning(
            "email_click_tracking_failed",
            email_id=email_id,
            error=str(e)
        )
        return RedirectResponse(url=url, status_code=302)
    except Exception as e:
        logger.error(
            "email_click_tracking_error",
            email_id=email_id,
            error=str(e),
            exc_info=True
        )
        # Still redirect to avoid breaking user experience
        return RedirectResponse(url=url, status_code=302)


# ============================================================================
# AUTHENTICATED ENDPOINTS
# ============================================================================

class CreateOutreachEmailRequest(BaseModel):
    """Request to create an outreach email record."""
    candidate_id: str = Field(..., description="Candidate identifier")
    candidate_name: str = Field(..., description="Candidate name")
    candidate_email: str = Field(..., description="Candidate email address")
    subject: str = Field(..., description="Email subject")
    body_html: Optional[str] = Field(None, description="HTML email body")
    body_text: Optional[str] = Field(None, description="Plain text email body")
    talent_analysis_id: Optional[str] = Field(None, description="Associated talent analysis ID")
    sent_via: str = Field(default="gmail_compose", description="How email was sent")
    gmail_message_id: Optional[str] = Field(None, description="Gmail API message ID")
    gmail_thread_id: Optional[str] = Field(None, description="Gmail thread ID")
    scheduled_for: Optional[datetime] = Field(None, description="Scheduled send time")


class OutreachEmailResponse(BaseModel):
    """Response model for outreach email."""
    email_id: str
    candidate_id: str
    candidate_name: str
    candidate_email: str
    subject: str
    status: str
    sent_at: Optional[datetime]
    open_count: int
    click_count: int
    reply_count: int
    is_replied: bool
    
    class Config:
        from_attributes = True


@router.post(
    "/emails",
    response_model=OutreachEmailResponse,
    summary="Create outreach email record",
    description="Record an email that was sent to a candidate. Automatically injects tracking pixels and links."
)
async def create_outreach_email(
    request_data: CreateOutreachEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Create a new outreach email record.
    
    This endpoint should be called when an email is sent to a candidate.
    It will inject tracking pixels and replace links with tracking URLs.
    """
    try:
        # Get base URL for tracking URLs
        base_url = str(request.base_url).rstrip("/")
        
        tracking_service = EmailTrackingService(db)
        
        # Create email record
        outreach_email = tracking_service.create_outreach_email(
            customer_id=current_user.customer_id,
            candidate_id=request_data.candidate_id,
            candidate_name=request_data.candidate_name,
            candidate_email=request_data.candidate_email,
            subject=request_data.subject,
            body_html=request_data.body_html,
            body_text=request_data.body_text,
            talent_analysis_id=request_data.talent_analysis_id,
            user_id=current_user.id,
            sent_via=request_data.sent_via,
            gmail_message_id=request_data.gmail_message_id,
            gmail_thread_id=request_data.gmail_thread_id,
            scheduled_for=request_data.scheduled_for
        )
        
        # Inject tracking if HTML body exists
        if request_data.body_html:
            # Inject tracking pixel
            body_html_with_tracking = tracking_service.inject_tracking_pixel(
                request_data.body_html,
                outreach_email.email_id,
                base_url
            )
            
            # Inject tracking links
            body_html_with_tracking = tracking_service.inject_tracking_links(
                body_html_with_tracking,
                outreach_email.email_id,
                base_url
            )
            
            # Update email with tracking-enabled HTML
            outreach_email.body_html = body_html_with_tracking
            db.commit()
            db.refresh(outreach_email)
        
        logger.info(
            "outreach_email_recorded",
            email_id=outreach_email.email_id,
            candidate_email=request_data.candidate_email,
            user_id=current_user.id,
            customer_id=current_user.customer_id
        )
        
        return OutreachEmailResponse(
            email_id=outreach_email.email_id,
            candidate_id=outreach_email.candidate_id,
            candidate_name=outreach_email.candidate_name,
            candidate_email=outreach_email.candidate_email,
            subject=outreach_email.subject,
            status=outreach_email.status,
            sent_at=outreach_email.sent_at,
            open_count=outreach_email.open_count,
            click_count=outreach_email.click_count,
            reply_count=outreach_email.reply_count,
            is_replied=outreach_email.is_replied
        )
    
    except IntegrityError as e:
        logger.error(
            "outreach_email_creation_integrity_error",
            candidate_email=request_data.candidate_email,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email record creation failed due to data integrity issue"
        )
    except ValueError as e:
        logger.error(
            "outreach_email_creation_validation_error",
            candidate_email=request_data.candidate_email,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "outreach_email_creation_error",
            candidate_email=request_data.candidate_email,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create outreach email: {str(e)}"
        )


# ============================================================================
# METRICS ENDPOINTS
# ============================================================================

class MetricsSummaryResponse(BaseModel):
    """Overall metrics summary."""
    total_emails: int
    total_opens: int
    total_clicks: int
    total_replies: int
    open_rate: float  # Percentage
    click_rate: float  # Percentage
    reply_rate: float  # Percentage
    unique_opens: int
    unique_clicks: int
    avg_opens_per_email: float
    avg_clicks_per_email: float


class EmailListResponse(BaseModel):
    """Paginated list of emails."""
    emails: List[OutreachEmailResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EmailDetailResponse(OutreachEmailResponse):
    """Detailed email response with engagement data."""
    first_opened_at: Optional[datetime]
    last_opened_at: Optional[datetime]
    last_reply_at: Optional[datetime]
    opens_by_device: dict
    clicks_by_link: List[dict]
    recent_opens: List[dict]
    recent_clicks: List[dict]


@router.get(
    "/metrics",
    response_model=MetricsSummaryResponse,
    summary="Get outreach metrics summary",
    description="Get overall email engagement metrics for the current customer."
)
async def get_metrics_summary(
    start_date: Optional[datetime] = Query(None, description="Filter emails sent after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter emails sent before this date"),
    talent_analysis_id: Optional[str] = Query(None, description="Filter by talent analysis ID"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """Get overall metrics summary."""
    try:
        # Build query
        query = db.query(OutreachEmail).filter(
            OutreachEmail.customer_id == current_user.customer_id
        )
        
        if start_date:
            query = query.filter(OutreachEmail.sent_at >= start_date)
        if end_date:
            query = query.filter(OutreachEmail.sent_at <= end_date)
        if talent_analysis_id:
            query = query.filter(OutreachEmail.talent_analysis_id == talent_analysis_id)
        
        emails = query.all()
        total_emails = len(emails)
        
        if total_emails == 0:
            return MetricsSummaryResponse(
                total_emails=0,
                total_opens=0,
                total_clicks=0,
                total_replies=0,
                open_rate=0.0,
                click_rate=0.0,
                reply_rate=0.0,
                unique_opens=0,
                unique_clicks=0,
                avg_opens_per_email=0.0,
                avg_clicks_per_email=0.0
            )
        
        # Calculate metrics
        total_opens = sum(e.open_count for e in emails)
        total_clicks = sum(e.click_count for e in emails)
        total_replies = sum(e.reply_count for e in emails)
        
        # Count unique opens (emails that were opened at least once)
        unique_opens = sum(1 for e in emails if e.open_count > 0)
        
        # Count unique clicks (emails that had at least one click)
        unique_clicks = sum(1 for e in emails if e.click_count > 0)
        
        # Calculate rates
        open_rate = (unique_opens / total_emails * 100) if total_emails > 0 else 0.0
        click_rate = (unique_clicks / total_emails * 100) if total_emails > 0 else 0.0
        reply_rate = (total_replies / total_emails * 100) if total_emails > 0 else 0.0
        
        avg_opens_per_email = total_opens / total_emails if total_emails > 0 else 0.0
        avg_clicks_per_email = total_clicks / total_emails if total_emails > 0 else 0.0
        
        return MetricsSummaryResponse(
            total_emails=total_emails,
            total_opens=total_opens,
            total_clicks=total_clicks,
            total_replies=total_replies,
            open_rate=round(open_rate, 2),
            click_rate=round(click_rate, 2),
            reply_rate=round(reply_rate, 2),
            unique_opens=unique_opens,
            unique_clicks=unique_clicks,
            avg_opens_per_email=round(avg_opens_per_email, 2),
            avg_clicks_per_email=round(avg_clicks_per_email, 2)
        )
    
    except Exception as e:
        logger.error(
            "metrics_summary_error",
            customer_id=current_user.customer_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )


@router.get(
    "/emails",
    response_model=EmailListResponse,
    summary="List outreach emails",
    description="List outreach emails with pagination and filtering."
)
async def list_outreach_emails(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    start_date: Optional[datetime] = Query(None, description="Filter emails sent after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter emails sent before this date"),
    talent_analysis_id: Optional[str] = Query(None, description="Filter by talent analysis ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """List outreach emails with pagination."""
    try:
        offset = (page - 1) * page_size
        
        # Build query
        query = db.query(OutreachEmail).filter(
            OutreachEmail.customer_id == current_user.customer_id
        )
        
        if start_date:
            query = query.filter(OutreachEmail.sent_at >= start_date)
        if end_date:
            query = query.filter(OutreachEmail.sent_at <= end_date)
        if talent_analysis_id:
            query = query.filter(OutreachEmail.talent_analysis_id == talent_analysis_id)
        if status:
            query = query.filter(OutreachEmail.status == status)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        emails = query.order_by(OutreachEmail.sent_at.desc()).offset(offset).limit(page_size).all()
        
        total_pages = (total + page_size - 1) // page_size
        
        email_responses = [
            OutreachEmailResponse(
                email_id=e.email_id,
                candidate_id=e.candidate_id,
                candidate_name=e.candidate_name,
                candidate_email=e.candidate_email,
                subject=e.subject,
                status=e.status,
                sent_at=e.sent_at,
                open_count=e.open_count,
                click_count=e.click_count,
                reply_count=e.reply_count,
                is_replied=e.is_replied
            )
            for e in emails
        ]
        
        return EmailListResponse(
            emails=email_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    
    except Exception as e:
        logger.error(
            "email_list_error",
            customer_id=current_user.customer_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list emails: {str(e)}"
        )


@router.get(
    "/emails/{email_id}",
    response_model=EmailDetailResponse,
    summary="Get email details",
    description="Get detailed information about a specific outreach email."
)
async def get_email_details(
    email_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """Get detailed email information."""
    try:
        email = db.query(OutreachEmail).filter(
            and_(
                OutreachEmail.email_id == email_id,
                OutreachEmail.customer_id == current_user.customer_id
            )
        ).first()
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Get opens by device
        opens_by_device = {}
        opens = db.query(EmailOpen).filter(EmailOpen.email_id == email_id).all()
        for open_event in opens:
            device = open_event.device_type or "unknown"
            opens_by_device[device] = opens_by_device.get(device, 0) + 1
        
        # Get clicks by link
        clicks_by_link = []
        clicks = db.query(EmailClick).filter(EmailClick.email_id == email_id).all()
        link_clicks = {}
        for click in clicks:
            link_url = click.link_url
            if link_url not in link_clicks:
                link_clicks[link_url] = {
                    "url": link_url,
                    "count": 0,
                    "unique_count": 0
                }
            link_clicks[link_url]["count"] += 1
            if click.is_unique:
                link_clicks[link_url]["unique_count"] += 1
        clicks_by_link = list(link_clicks.values())
        
        # Get recent opens (last 10)
        recent_opens = db.query(EmailOpen).filter(
            EmailOpen.email_id == email_id
        ).order_by(EmailOpen.opened_at.desc()).limit(10).all()
        
        recent_opens_data = [
            {
                "opened_at": o.opened_at.isoformat() if o.opened_at else None,
                "device_type": o.device_type,
                "email_client": o.email_client,
                "location": f"{o.location_city or ''}, {o.location_country or ''}".strip(", ")
            }
            for o in recent_opens
        ]
        
        # Get recent clicks (last 10)
        recent_clicks = db.query(EmailClick).filter(
            EmailClick.email_id == email_id
        ).order_by(EmailClick.clicked_at.desc()).limit(10).all()
        
        recent_clicks_data = [
            {
                "clicked_at": c.clicked_at.isoformat() if c.clicked_at else None,
                "link_url": c.link_url,
                "device_type": c.device_type,
                "location": f"{c.location_city or ''}, {c.location_country or ''}".strip(", ")
            }
            for c in recent_clicks
        ]
        
        return EmailDetailResponse(
            email_id=email.email_id,
            candidate_id=email.candidate_id,
            candidate_name=email.candidate_name,
            candidate_email=email.candidate_email,
            subject=email.subject,
            status=email.status,
            sent_at=email.sent_at,
            open_count=email.open_count,
            click_count=email.click_count,
            reply_count=email.reply_count,
            is_replied=email.is_replied,
            first_opened_at=email.first_opened_at,
            last_opened_at=email.last_opened_at,
            last_reply_at=email.last_reply_at,
            opens_by_device=opens_by_device,
            clicks_by_link=clicks_by_link,
            recent_opens=recent_opens_data,
            recent_clicks=recent_clicks_data
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "email_details_error",
            email_id=email_id,
            customer_id=current_user.customer_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve email details: {str(e)}"
        )


@router.get(
    "/metrics/export",
    summary="Export metrics to CSV",
    description="Export email metrics to CSV format."
)
async def export_metrics_csv(
    start_date: Optional[datetime] = Query(None, description="Filter emails sent after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter emails sent before this date"),
    talent_analysis_id: Optional[str] = Query(None, description="Filter by talent analysis ID"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """Export metrics to CSV."""
    try:
        # Build query
        query = db.query(OutreachEmail).filter(
            OutreachEmail.customer_id == current_user.customer_id
        )
        
        if start_date:
            query = query.filter(OutreachEmail.sent_at >= start_date)
        if end_date:
            query = query.filter(OutreachEmail.sent_at <= end_date)
        if talent_analysis_id:
            query = query.filter(OutreachEmail.talent_analysis_id == talent_analysis_id)
        
        emails = query.order_by(OutreachEmail.sent_at.desc()).all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Email ID",
            "Candidate Name",
            "Candidate Email",
            "Subject",
            "Status",
            "Sent At",
            "Open Count",
            "Click Count",
            "Reply Count",
            "Is Replied",
            "First Opened At",
            "Last Opened At",
            "Last Reply At"
        ])
        
        # Write data
        for email in emails:
            writer.writerow([
                email.email_id,
                email.candidate_name or "",
                email.candidate_email,
                email.subject,
                email.status,
                email.sent_at.isoformat() if email.sent_at else "",
                email.open_count,
                email.click_count,
                email.reply_count,
                "Yes" if email.is_replied else "No",
                email.first_opened_at.isoformat() if email.first_opened_at else "",
                email.last_opened_at.isoformat() if email.last_opened_at else "",
                email.last_reply_at.isoformat() if email.last_reply_at else ""
            ])
        
        output.seek(0)
        
        # Generate filename
        filename = f"outreach_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        logger.error(
            "metrics_export_error",
            customer_id=current_user.customer_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export metrics: {str(e)}"
        )


# Greenhouse Profile URL Endpoints

class GreenhouseProfileUrlRequest(BaseModel):
    """Request to fetch Greenhouse profile URL."""
    candidate_email: str = Field(..., description="Candidate email address")
    greenhouse_candidate_id: Optional[int] = Field(None, description="Greenhouse candidate ID if known")


class GreenhouseProfileUrlResponse(BaseModel):
    """Response with Greenhouse profile URL."""
    greenhouse_candidate_id: Optional[int] = Field(None, description="Greenhouse candidate ID")
    greenhouse_profile_url: Optional[str] = Field(None, description="Direct link to candidate profile in Greenhouse")
    found: bool = Field(..., description="Whether candidate was found in Greenhouse")


@router.post(
    "/greenhouse/profile-url",
    response_model=GreenhouseProfileUrlResponse,
    summary="Get Greenhouse profile URL for candidate",
    description="Fetch Greenhouse candidate profile URL by email or candidate ID. Helps HR managers navigate between tools."
)
async def get_greenhouse_profile_url(
    request: GreenhouseProfileUrlRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Get Greenhouse profile URL for a candidate.
    
    Searches Greenhouse for the candidate by email or uses provided candidate ID
    to fetch the profile URL. This enables HR managers to quickly navigate to
    candidate profiles in Greenhouse from the outreach page.
    """
    try:
        profile_service = GreenhouseProfileService(db, current_user.customer_id)
        
        # Try to get profile URL
        profile_url = None
        candidate_id = request.greenhouse_candidate_id
        
        if candidate_id:
            # Use provided candidate ID
            profile_url = profile_service.get_candidate_profile_url(candidate_id)
        elif request.candidate_email:
            # Search by email
            candidate_data = profile_service.find_candidate_by_email(request.candidate_email)
            if candidate_data:
                candidate_id = candidate_data.get("id")
                profile_url = candidate_data.get("profile_url")
        
        found = profile_url is not None
        
        logger.info(
            "greenhouse_profile_url_fetched",
            customer_id=current_user.customer_id,
            candidate_email=request.candidate_email,
            greenhouse_candidate_id=candidate_id,
            found=found
        )
        
        return GreenhouseProfileUrlResponse(
            greenhouse_candidate_id=candidate_id,
            greenhouse_profile_url=profile_url,
            found=found
        )
    
    except Exception as e:
        logger.error(
            "greenhouse_profile_url_error",
            customer_id=current_user.customer_id,
            candidate_email=request.candidate_email,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Greenhouse profile URL: {str(e)}"
        )


# Greenhouse Candidates for Outreach

class GreenhouseCandidateResponse(BaseModel):
    """Response model for Greenhouse candidate."""
    id: str = Field(..., description="Candidate ID")
    greenhouse_candidate_id: int = Field(..., description="Greenhouse candidate ID")
    name: str = Field(..., description="Candidate full name")
    email: str = Field(..., description="Candidate email")
    phone: Optional[str] = Field(None, description="Candidate phone number")
    linkedin: Optional[str] = Field(None, description="LinkedIn URL")
    location: Optional[str] = Field(None, description="Location")
    current_title: Optional[str] = Field(None, description="Current job title")
    current_company: Optional[str] = Field(None, description="Current company")
    greenhouse_profile_url: Optional[str] = Field(None, description="Direct link to Greenhouse profile")
    applications: List[Dict[str, Any]] = Field(default_factory=list, description="List of applications")
    created_at: Optional[str] = Field(None, description="When candidate was created in Greenhouse")
    previous_job_title: Optional[str] = Field(None, description="Job title from previous application")
    previous_application_status: Optional[str] = Field(None, description="Status of previous application (e.g., rejected, active)")
    previous_stage_name: Optional[str] = Field(None, description="Stage name where candidate was at")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection if applicable")
    rejected_at: Optional[str] = Field(None, description="Date when candidate was rejected")
    applied_at: Optional[str] = Field(None, description="Date when candidate applied")


class GreenhouseCandidatesListResponse(BaseModel):
    """Response model for list of Greenhouse candidates."""
    candidates: List[GreenhouseCandidateResponse] = Field(..., description="List of candidates")
    total: int = Field(..., description="Total number of candidates")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")
    has_next: bool = Field(..., description="Whether there are more pages")


@router.get(
    "/greenhouse/candidates",
    response_model=GreenhouseCandidatesListResponse,
    summary="Get Greenhouse candidates for outreach",
    description="Fetch candidates from Greenhouse to populate the outreach page. Returns candidates with their profile URLs."
)
async def get_greenhouse_candidates_for_outreach(
    connector_id: Optional[str] = Query(None, description="Greenhouse connector ID (optional, uses first active connector if not provided)"),
    job_id: Optional[int] = Query(None, description="Filter by specific job ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Candidates per page"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Get Greenhouse candidates for the outreach page.
    
    Fetches candidates from Greenhouse and formats them for display on the outreach page.
    Automatically fetches profile URLs for each candidate.
    """
    try:
        from src.services.ingestion.connector_service import ConnectorService
        from src.services.greenhouse_profile_service import GreenhouseProfileService
        import requests
        
        # Get connector configuration
        connector_service = ConnectorService(db)
        
        if connector_id:
            config = connector_service.get_configuration(connector_id, current_user.customer_id)
        else:
            # Find first active Greenhouse connector
            configs = db.query(ConnectorConfiguration).filter(
                ConnectorConfiguration.customer_id == current_user.customer_id,
                ConnectorConfiguration.connector_type == "greenhouse",
                ConnectorConfiguration.is_enabled == True
            ).all()
            
            if not configs:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No active Greenhouse connector found. Please configure a Greenhouse connector first."
                )
            config = configs[0]
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Greenhouse connector not found"
            )
        
        if config.connector_type != "greenhouse":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector is not a Greenhouse connector"
            )
        
        # Get credentials
        credentials = connector_service.get_credentials(config)
        api_key = credentials.get("api_key")
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Greenhouse API key not found in connector credentials"
            )
        
        # Create auth headers directly (don't rely on GreenhouseProfileService for this)
        import base64
        credential = base64.b64encode(f"{api_key}:".encode()).decode()
        headers = {
            "Authorization": f"Basic {credential}",
            "Content-Type": "application/json"
        }
        
        # Fetch applications directly from Greenhouse API
        base_url = "https://harvest.greenhouse.io/v1"
        
        # Fetch applications (fetch more to increase chances of finding candidates with emails)
        # Increase per_page to search through more candidates
        params = {"per_page": min(page_size * 20, 100), "page": page}  # Fetch 20x more to find candidates with emails
        if job_id:
            params["job_id"] = job_id
        
        response = requests.get(
            f"{base_url}/applications",
            headers=headers,
            params=params,
            timeout=30
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Greenhouse API error: {response.status_code} - {response.text[:200]}"
            )
        
        applications_data = response.json()
        
        # Debug: Log what we got from Greenhouse
        logger.info(
            "greenhouse_applications_received",
            customer_id=current_user.customer_id,
            applications_count=len(applications_data),
            page=page
        )
        
        # Process candidates and extract unique candidates
        candidates_map = {}
        profile_service = GreenhouseProfileService(db, current_user.customer_id)
        
        # Process all applications we fetched to find candidates with complete data
        # Stop once we have enough candidates (page_size)
        processed_count = 0
        skipped_no_id = 0
        skipped_no_email = 0
        skipped_duplicate = 0
        
        for app in applications_data:
            # Stop if we have enough candidates
            if len(candidates_map) >= page_size:
                break
            
            candidate_data = app.get("candidate", {})
            candidate_id = candidate_data.get("id")
            
            if not candidate_id:
                skipped_no_id += 1
                logger.debug(
                    "candidate_skipped_no_id",
                    application_id=app.get("id"),
                    candidate_data_keys=list(candidate_data.keys()) if candidate_data else []
                )
                continue
            
            if candidate_id in candidates_map:
                skipped_duplicate += 1
                continue  # Skip if already processed
            
            # Extract email - try multiple sources
            email = None
            if candidate_data.get("email_addresses"):
                email_addresses = candidate_data["email_addresses"]
                if isinstance(email_addresses, list) and len(email_addresses) > 0:
                    email = email_addresses[0].get("value")
            
            # If no email in email_addresses, try the top-level email field
            if not email and candidate_data.get("email"):
                email = candidate_data.get("email")
            
            # For demo purposes, if still no email, skip this candidate
            if not email:
                skipped_no_email += 1
                logger.debug(
                    "candidate_skipped_no_email",
                    candidate_id=candidate_id,
                    candidate_name=f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip(),
                    email_addresses=candidate_data.get("email_addresses", []),
                    top_level_email=candidate_data.get("email")
                )
                continue
            
            processed_count += 1
            
            # Extract phone
            phone = None
            if candidate_data.get("phone_numbers"):
                phone = candidate_data["phone_numbers"][0].get("value")
            
            # Extract LinkedIn
            linkedin = None
            if candidate_data.get("social_media_addresses"):
                for sm in candidate_data["social_media_addresses"]:
                    if sm.get("type") == "LinkedIn":
                        linkedin = sm.get("value")
                        break
            
            # Extract location
            location = None
            if candidate_data.get("addresses"):
                addr = candidate_data["addresses"][0]
                location_parts = []
                if addr.get("city"):
                    location_parts.append(addr["city"])
                if addr.get("state"):
                    location_parts.append(addr["state"])
                if addr.get("country"):
                    location_parts.append(addr["country"])
                location = ", ".join(location_parts) if location_parts else None
            
            # Get current employment
            current_title = None
            current_company = None
            if candidate_data.get("employments"):
                latest_employment = candidate_data["employments"][0]
                current_title = latest_employment.get("title")
                current_company = latest_employment.get("company_name")
            
            # Get profile URL from application or fetch it
            profile_url = None
            if app.get("profile_url"):
                profile_url = app["profile_url"]
            else:
                # Try to fetch profile URL
                profile_url = profile_service.get_candidate_profile_url(candidate_id, email)
            
            # Extract application/job information
            previous_job_title = None
            if app.get("jobs") and len(app["jobs"]) > 0:
                previous_job_title = app["jobs"][0].get("name")
            
            # Extract application status and stage
            previous_application_status = app.get("status")  # e.g., "rejected", "active", "hired"
            previous_stage_name = None
            if app.get("current_stage"):
                previous_stage_name = app["current_stage"].get("name")
            
            # Extract rejection information
            rejection_reason = None
            rejected_at = None
            if app.get("rejection_reason"):
                rejection_reason_obj = app["rejection_reason"]
                if isinstance(rejection_reason_obj, dict):
                    rejection_reason = rejection_reason_obj.get("name") or rejection_reason_obj.get("type")
                elif isinstance(rejection_reason_obj, str):
                    rejection_reason = rejection_reason_obj
            
            if app.get("rejected_at"):
                rejected_at = app["rejected_at"]
            
            # Extract application date
            applied_at = app.get("applied_at")
            
            # Get all applications for this candidate
            candidate_applications = [app] if app.get("id") else []
            
            candidates_map[candidate_id] = GreenhouseCandidateResponse(
                id=f"gh_{candidate_id}",
                greenhouse_candidate_id=candidate_id,
                name=f"{candidate_data.get('first_name', '')} {candidate_data.get('last_name', '')}".strip(),
                email=email,
                phone=phone,
                linkedin=linkedin,
                location=location,
                current_title=current_title,
                current_company=current_company,
                greenhouse_profile_url=profile_url,
                applications=candidate_applications,
                created_at=candidate_data.get("created_at"),
                previous_job_title=previous_job_title,
                previous_application_status=previous_application_status,
                previous_stage_name=previous_stage_name,
                rejection_reason=rejection_reason,
                rejected_at=rejected_at,
                applied_at=applied_at
            )
        
        candidates_list = list(candidates_map.values())
        
        # Estimate total (we don't have exact count without another API call)
        # For now, assume there might be more if we got a full page
        has_next = len(applications_data) == page_size
        
        logger.info(
            "greenhouse_candidates_fetched",
            customer_id=current_user.customer_id,
            connector_id=config.connector_id,
            count=len(candidates_list),
            page=page,
            processed_count=processed_count,
            skipped_no_id=skipped_no_id,
            skipped_no_email=skipped_no_email,
            skipped_duplicate=skipped_duplicate
        )
        
        return GreenhouseCandidatesListResponse(
            candidates=candidates_list,
            total=len(candidates_list),  # Approximate
            page=page,
            page_size=page_size,
            has_next=has_next
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "greenhouse_candidates_fetch_error",
            customer_id=current_user.customer_id,
            connector_id=connector_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Greenhouse candidates: {str(e)}"
        )


# ============================================================================
# SCORED CANDIDATES FROM ANALYSES
# ============================================================================

class ScoredCandidateResponse(BaseModel):
    """A scored candidate from a completed analysis"""
    id: str = Field(..., description="Unique candidate ID")
    analysis_id: str = Field(..., description="Analysis this candidate came from")
    analysis_name: str = Field(..., description="Name/description of the analysis")
    analysis_date: str = Field(..., description="When the analysis was run")
    name: str = Field(..., description="Candidate name")
    email: Optional[str] = Field(None, description="Candidate email")
    phone: Optional[str] = Field(None, description="Candidate phone")
    linkedin: Optional[str] = Field(None, description="LinkedIn URL")
    location: Optional[str] = Field(None, description="Location")
    current_title: Optional[str] = Field(None, description="Current job title")
    current_company: Optional[str] = Field(None, description="Current company")
    score: float = Field(..., description="Overall match score (0-100)")
    rank: int = Field(..., description="Rank within the analysis")
    source: str = Field(..., description="Source: 'applicant', 'market', or 'previous_candidate'")
    highlights: List[str] = Field(default_factory=list, description="Key highlights/strengths")
    score_breakdown: Optional[Dict[str, Any]] = Field(None, description="Detailed score breakdown")
    confidence: Optional[float] = Field(None, description="Confidence score")
    outreach_status: str = Field(default="pending", description="Outreach status")
    greenhouse_id: Optional[int] = Field(None, description="Greenhouse candidate ID for building profile URL")
    greenhouse_profile_url: Optional[str] = Field(None, description="Greenhouse profile URL if available")


class ScoredCandidatesListResponse(BaseModel):
    """Response for scored candidates list"""
    candidates: List[ScoredCandidateResponse]
    total: int
    analysis_count: int = Field(..., description="Number of analyses included")
    page: int
    page_size: int
    has_next: bool


@router.get(
    "/scored-candidates",
    response_model=ScoredCandidatesListResponse,
    summary="Get scored candidates from analyses",
    description="Fetch scored candidates from completed talent analyses for the outreach page"
)
async def get_scored_candidates_for_outreach(
    analysis_id: Optional[str] = Query(None, description="Filter by specific analysis ID"),
    source: Optional[str] = Query(None, description="Filter by source: 'applicant', 'market', or 'previous_candidate'"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum score threshold"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Candidates per page"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Get scored candidates from completed talent analyses.
    
    Returns candidates that have been scored through the talent analysis pipeline,
    ready for outreach. Includes both applicant and market candidates.
    
    Uses normalized candidates and candidate_analysis_scores tables for accurate data.
    """
    try:
        from sqlalchemy import text
        import json
        
        # First, try to get candidates from the normalized tables
        # This is the preferred source as it has accurate greenhouse_id and other data
        all_candidates = []
        analysis_count = 0
        seen_analysis_ids = set()
        
        # Build query for normalized candidate scores
        query = db.query(CandidateAnalysisScore, Candidate).join(
            Candidate, CandidateAnalysisScore.candidate_id == Candidate.id
        ).filter(
            Candidate.customer_id == current_user.customer_id
        )
        
        if analysis_id:
            query = query.filter(CandidateAnalysisScore.analysis_id == analysis_id)
        
        if source:
            query = query.filter(CandidateAnalysisScore.source == source)
        
        if min_score:
            query = query.filter(CandidateAnalysisScore.overall_score >= min_score)
        
        query = query.order_by(CandidateAnalysisScore.overall_score.desc())
        
        # Get all results from normalized tables
        normalized_results = query.all()
        
        # Get analysis metadata for display names
        analysis_metadata = {}
        if normalized_results:
            analysis_ids = list(set(score.analysis_id for score, _ in normalized_results))
            analysis_query = db.execute(
                text("""
                    SELECT analysis_id, job_description, created_at 
                    FROM talent_analyses 
                    WHERE analysis_id = ANY(:analysis_ids)
                """),
                {"analysis_ids": analysis_ids}
            )
            for row in analysis_query.fetchall():
                analysis_metadata[row.analysis_id] = {
                    "name": row.job_description[:100] + "..." if row.job_description and len(row.job_description) > 100 else (row.job_description or "Talent Analysis"),
                    "date": row.created_at.strftime("%Y-%m-%d") if row.created_at else ""
                }
        
        # Process normalized results
        for score, candidate in normalized_results:
            seen_analysis_ids.add(score.analysis_id)
            
            # Get analysis metadata
            analysis_meta = analysis_metadata.get(score.analysis_id, {"name": "Talent Analysis", "date": ""})
            
            # Build highlights from score breakdown dimensions
            highlights = []
            score_breakdown = score.score_breakdown or {}
            dimensions = score_breakdown.get("dimensions", [])
            for dim in dimensions:
                if dim.get("score", 0) >= 70:
                    highlights.append(f"{dim.get('dimension', 'Unknown')}: {dim.get('score', 0):.0f}")
            
            # Build greenhouse URL if we have the ID
            greenhouse_url = None
            if candidate.greenhouse_id:
                greenhouse_url = f"https://app4.greenhouse.io/people/{candidate.greenhouse_id}"
            
            all_candidates.append(ScoredCandidateResponse(
                id=str(candidate.id),
                analysis_id=score.analysis_id,
                analysis_name=analysis_meta["name"],
                analysis_date=analysis_meta["date"],
                name=candidate.full_name or candidate.email or "Unknown",
                email=candidate.email,
                phone=candidate.phone,
                linkedin=candidate.linkedin_url,
                location=candidate.location,
                current_title=candidate.current_title,
                current_company=candidate.current_company,
                score=round(score.overall_score or 0, 1),
                rank=score.rank_in_source or 0,
                source=score.source or "applicant",
                highlights=highlights[:4],
                score_breakdown=score_breakdown,
                confidence=score_breakdown.get("confidence"),
                outreach_status=score.outreach_status or "pending",
                greenhouse_id=candidate.greenhouse_id,
                greenhouse_profile_url=greenhouse_url
            ))
        
        analysis_count = len(seen_analysis_ids)
        
        # If no results from normalized tables, fall back to legacy JSON column
        if not all_candidates:
            logger.info("No candidates in normalized tables, falling back to legacy JSON")
            
            # Build query for completed analyses
            legacy_query = """
                SELECT 
                    analysis_id,
                    job_description,
                    ideal_candidate_description,
                    candidates,
                    created_at,
                    candidate_count
                FROM talent_analyses
                WHERE customer_id = :customer_id
                AND status = 'completed'
                AND candidates IS NOT NULL
            """
            params = {"customer_id": current_user.customer_id}
            
            if analysis_id:
                legacy_query += " AND analysis_id = :analysis_id"
                params["analysis_id"] = analysis_id
            
            legacy_query += " ORDER BY created_at DESC"
            
            result = db.execute(text(legacy_query), params)
            analyses = result.fetchall()
            
            for analysis in analyses:
                analysis_count += 1
                candidates_json = analysis.candidates
                if not candidates_json:
                    continue
                
                # Parse candidates JSON
                if isinstance(candidates_json, str):
                    candidates_data = json.loads(candidates_json)
                else:
                    candidates_data = candidates_json
                
                # Get analysis description for display
                analysis_name = analysis.job_description[:100] + "..." if analysis.job_description and len(analysis.job_description) > 100 else (analysis.job_description or "Talent Analysis")
                analysis_date = analysis.created_at.strftime("%Y-%m-%d") if analysis.created_at else ""
                
                # Process applicant candidates
                applicant_candidates = candidates_data.get("applicant_candidates", [])
                for idx, candidate in enumerate(applicant_candidates):
                    if source and source != "applicant":
                        continue
                    
                    candidate_score = candidate.get("overall_score", 0)
                    if min_score and candidate_score < min_score:
                        continue
                    
                    # Extract candidate info
                    candidate_id = candidate.get("candidate_id", f"app_{analysis.analysis_id}_{idx}")
                    
                    # Build highlights from dimensions
                    highlights = []
                    for dim in candidate.get("dimensions", []):
                        if dim.get("score", 0) >= 70:
                            highlights.append(f"{dim.get('dimension', 'Unknown')}: {dim.get('score', 0):.0f}")
                    
                    # Extract profile data from stored candidate
                    candidate_name = candidate.get("full_name")
                    candidate_email = candidate.get("email")
                    if not candidate_email:
                        candidate_email = candidate_id if "@" in str(candidate_id) else None
                    
                    greenhouse_id = candidate.get("greenhouse_id")
                    greenhouse_url = f"https://app4.greenhouse.io/people/{greenhouse_id}" if greenhouse_id else None
                    
                    # Final fallback for name
                    if not candidate_name:
                        candidate_name = candidate_id.split("@")[0].replace(".", " ").replace("_", " ").title() if "@" in str(candidate_id) else str(candidate_id)
                    
                    all_candidates.append(ScoredCandidateResponse(
                        id=str(candidate_id),
                        analysis_id=analysis.analysis_id,
                        analysis_name=analysis_name,
                        analysis_date=analysis_date,
                        name=candidate_name,
                        email=candidate_email,
                        phone=candidate.get("phone"),
                        linkedin=candidate.get("linkedin_url"),
                        location=candidate.get("location"),
                        current_title=candidate.get("current_title"),
                        current_company=candidate.get("current_company"),
                        score=round(candidate_score, 1),
                        rank=idx + 1,
                        source="applicant",
                        highlights=highlights[:4],
                        score_breakdown={"dimensions": candidate.get("dimensions", [])},
                        confidence=candidate.get("confidence"),
                        outreach_status="pending",
                        greenhouse_id=greenhouse_id,
                        greenhouse_profile_url=greenhouse_url
                    ))
                
                # Process market candidates
                market_candidates = candidates_data.get("market_candidates", [])
                for idx, candidate in enumerate(market_candidates):
                    if source and source != "market":
                        continue
                    
                    candidate_score = candidate.get("overall_score", 0)
                    if min_score and candidate_score < min_score:
                        continue
                    
                    candidate_id = candidate.get("candidate_id", f"mkt_{analysis.analysis_id}_{idx}")
                    
                    # Build highlights from dimensions
                    highlights = []
                    for dim in candidate.get("dimensions", []):
                        if dim.get("score", 0) >= 70:
                            highlights.append(f"{dim.get('dimension', 'Unknown')}: {dim.get('score', 0):.0f}")
                    
                    # Market candidates typically come from PDL and have full_name
                    candidate_name = candidate.get("full_name") or candidate.get("candidate_name")
                    if not candidate_name:
                        candidate_name = candidate_id if "@" not in str(candidate_id) else candidate_id.split("@")[0].replace(".", " ").title()
                    
                    candidate_email = candidate.get("email")
                    if not candidate_email:
                        candidate_email = candidate_id if "@" in str(candidate_id) else None
                    
                    all_candidates.append(ScoredCandidateResponse(
                        id=str(candidate_id),
                        analysis_id=analysis.analysis_id,
                        analysis_name=analysis_name,
                        analysis_date=analysis_date,
                        name=candidate_name,
                        email=candidate_email,
                        phone=candidate.get("phone"),
                        linkedin=candidate.get("linkedin_url"),
                        location=candidate.get("location"),
                        current_title=candidate.get("current_title"),
                        current_company=candidate.get("current_company"),
                        score=round(candidate_score, 1),
                        rank=idx + 1,
                        source="market",
                        highlights=highlights[:4],
                        score_breakdown={"dimensions": candidate.get("dimensions", [])},
                        confidence=candidate.get("confidence"),
                        outreach_status="pending",
                        greenhouse_id=None,
                        greenhouse_profile_url=None
                    ))
        
        # Sort by score descending
        all_candidates.sort(key=lambda x: x.score, reverse=True)
        
        # Re-rank after sorting
        for idx, candidate in enumerate(all_candidates):
            candidate.rank = idx + 1
        
        # Paginate
        total = len(all_candidates)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = all_candidates[start_idx:end_idx]
        has_next = end_idx < total
        
        logger.info(
            "scored_candidates_fetched",
            customer_id=current_user.customer_id,
            total=total,
            analysis_count=analysis_count,
            page=page,
            returned=len(paginated)
        )
        
        return ScoredCandidatesListResponse(
            candidates=paginated,
            total=total,
            analysis_count=analysis_count,
            page=page,
            page_size=page_size,
            has_next=has_next
        )
    
    except Exception as e:
        logger.error(
            "scored_candidates_fetch_error",
            customer_id=current_user.customer_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch scored candidates: {str(e)}"
        )


# ============================================================================
# NORMALIZED CANDIDATE ENDPOINTS (NEW ARCHITECTURE)
# ============================================================================

class CandidateProfileResponse(BaseModel):
    """Response model for a candidate profile from the candidates table."""
    id: int = Field(..., description="Candidate database ID")
    email: Optional[str] = Field(None, description="Candidate email")
    full_name: Optional[str] = Field(None, description="Full name")
    phone: Optional[str] = Field(None, description="Phone number")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn URL")
    github_url: Optional[str] = Field(None, description="GitHub URL")
    location: Optional[str] = Field(None, description="Location")
    current_title: Optional[str] = Field(None, description="Current job title")
    current_company: Optional[str] = Field(None, description="Current company")
    greenhouse_id: Optional[int] = Field(None, description="Greenhouse candidate ID")
    pdl_id: Optional[str] = Field(None, description="PDL ID")
    source: Optional[str] = Field(None, description="Source: greenhouse, pdl, upload, manual")
    skills: Optional[List[str]] = Field(None, description="Skills list")
    load_date: Optional[str] = Field(None, description="When candidate was first loaded")
    last_verified_at: Optional[str] = Field(None, description="When profile was last verified")
    
    class Config:
        from_attributes = True


class CandidateScoreResponse(BaseModel):
    """Response model for a candidate's score in a specific analysis."""
    id: int = Field(..., description="Score record ID")
    analysis_id: str = Field(..., description="Analysis ID")
    overall_score: float = Field(..., description="Overall match score (0-100)")
    rank_overall: Optional[int] = Field(None, description="Overall rank")
    rank_in_source: Optional[int] = Field(None, description="Rank within source type")
    source: str = Field(..., description="Source: applicant, market, or previous_candidate")
    confidence: Optional[float] = Field(None, description="Confidence score")
    score_breakdown: Dict[str, Any] = Field(..., description="Detailed score breakdown")
    patterns_matched: Optional[List[str]] = Field(None, description="Matched patterns")
    outreach_status: str = Field(default="pending", description="Outreach status")
    email_template_id: Optional[int] = Field(None, description="Template used for email")
    generated_email_subject: Optional[str] = Field(None, description="Generated email subject")
    generated_email_body: Optional[str] = Field(None, description="Generated email body")
    email_generated_at: Optional[str] = Field(None, description="When email was generated")
    scored_at: Optional[str] = Field(None, description="When candidate was scored")
    has_feedback: bool = Field(default=False, description="Whether user has submitted feedback for this score")
    
    class Config:
        from_attributes = True


class CandidateWithScoreResponse(BaseModel):
    """Combined candidate profile with their analysis score."""
    candidate: CandidateProfileResponse
    score: CandidateScoreResponse
    greenhouse_profile_url: Optional[str] = Field(None, description="Greenhouse profile URL")


class CandidatesWithScoresListResponse(BaseModel):
    """Response for candidates with scores list."""
    candidates: List[CandidateWithScoreResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


@router.get(
    "/v2/candidates",
    response_model=CandidatesWithScoresListResponse,
    summary="Get candidates with scores (new architecture)",
    description="Fetch candidates from the normalized candidates table with their analysis scores"
)
async def get_candidates_v2(
    analysis_id: Optional[str] = Query(None, description="Filter by specific analysis ID"),
    source: Optional[str] = Query(None, description="Filter by source: 'applicant', 'market', or 'previous_candidate'"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum score threshold"),
    outreach_status: Optional[str] = Query(None, description="Filter by outreach status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Candidates per page"),
    auto_generate_emails: bool = Query(True, description="Auto-generate emails using default template for candidates without one"),
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Get candidates from the normalized candidates table with their analysis scores.
    
    This is the new architecture that separates candidate profiles from analysis scores,
    allowing the same candidate to be scored in multiple analyses.
    
    If auto_generate_emails is True (default), candidates without generated emails will
    have emails generated using the default template before being returned.
    """
    try:
        # Build query joining candidates with their scores
        query = db.query(CandidateAnalysisScore).join(Candidate).filter(
            Candidate.customer_id == current_user.customer_id
        )
        
        if analysis_id:
            query = query.filter(CandidateAnalysisScore.analysis_id == analysis_id)
        if source:
            query = query.filter(CandidateAnalysisScore.source == source)
        if min_score is not None:
            query = query.filter(CandidateAnalysisScore.overall_score >= min_score)
        if outreach_status:
            query = query.filter(CandidateAnalysisScore.outreach_status == outreach_status)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        offset = (page - 1) * page_size
        scores = query.order_by(
            CandidateAnalysisScore.overall_score.desc()
        ).offset(offset).limit(page_size).all()
        
        # Initialize email generation service if auto-generating
        email_service = None
        if auto_generate_emails:
            email_service = EmailGenerationService(db, current_user.customer_id)
        
        # Build response
        results = []
        for score in scores:
            candidate = score.candidate
            
            # Auto-generate email if needed
            generated_subject = score.generated_email_subject
            generated_body = score.generated_email_body
            email_generated_at = score.email_generated_at
            email_template_id = score.email_template_id
            
            if auto_generate_emails and not generated_subject and not generated_body:
                # Try to generate email using default template
                try:
                    # Determine category based on source
                    if score.source == 'applicant':
                        category = 'applicant_followup'
                    elif score.source == 'previous_candidate':
                        category = 'previous_candidate_outreach'
                    else:
                        category = 'market_outreach'
                    
                    # Build candidate data for email generation
                    candidate_data = {
                        'id': str(candidate.id),
                        'full_name': candidate.full_name,
                        'name': candidate.full_name,
                        'first_name': candidate.full_name.split()[0] if candidate.full_name else '',
                        'email': candidate.email,
                        'location_name': candidate.location,
                        'location': candidate.location,
                        'job_title': candidate.current_title,
                        'role_title': candidate.current_title,
                        'current_title': candidate.current_title,
                        'job_company_name': candidate.current_company,
                        'current_company': candidate.current_company,
                        'skills': candidate.skills or [],
                    }
                    
                    generated_email = await email_service.generate_email_with_default_template(
                        candidate_data=candidate_data,
                        category=category,
                        talent_analysis_id=score.analysis_id,
                        candidate_db_id=candidate.id
                    )
                    
                    if generated_email:
                        # Update the score record with generated email
                        score.generated_email_subject = generated_email.subject
                        score.generated_email_body = generated_email.body
                        score.email_template_id = generated_email.template_id
                        score.email_generated_at = generated_email.created_at
                        db.commit()
                        
                        # Use generated values for response
                        generated_subject = generated_email.subject
                        generated_body = generated_email.body
                        email_generated_at = generated_email.created_at
                        email_template_id = generated_email.template_id
                        
                        logger.info(
                            "auto_generated_email_for_candidate",
                            candidate_id=candidate.id,
                            analysis_id=score.analysis_id,
                            template_id=generated_email.template_id
                        )
                except Exception as e:
                    logger.warning(
                        "auto_email_generation_failed",
                        candidate_id=candidate.id,
                        analysis_id=score.analysis_id,
                        error=str(e)
                    )
                    # Continue without email - frontend will show fallback
            
            # Build Greenhouse URL if we have the ID
            greenhouse_url = None
            if candidate.greenhouse_id:
                greenhouse_url = f"https://app4.greenhouse.io/people/{candidate.greenhouse_id}"
            
            # Check if user has already submitted feedback for this score
            has_feedback = db.query(CandidateScoreFeedback).filter(
                CandidateScoreFeedback.candidate_analysis_score_id == score.id,
                CandidateScoreFeedback.user_id == current_user.user_id
            ).first() is not None
            
            results.append(CandidateWithScoreResponse(
                candidate=CandidateProfileResponse(
                    id=candidate.id,
                    email=candidate.email,
                    full_name=candidate.full_name,
                    phone=candidate.phone,
                    linkedin_url=candidate.linkedin_url,
                    github_url=candidate.github_url,
                    location=candidate.location,
                    current_title=candidate.current_title,
                    current_company=candidate.current_company,
                    greenhouse_id=candidate.greenhouse_id,
                    pdl_id=candidate.pdl_id,
                    source=candidate.source,
                    skills=candidate.skills,
                    load_date=candidate.load_date.isoformat() if candidate.load_date else None,
                    last_verified_at=candidate.last_verified_at.isoformat() if candidate.last_verified_at else None
                ),
                score=CandidateScoreResponse(
                    id=score.id,
                    analysis_id=score.analysis_id,
                    overall_score=score.overall_score,
                    rank_overall=score.rank_overall,
                    rank_in_source=score.rank_in_source,
                    source=score.source,
                    confidence=score.confidence,
                    score_breakdown=score.score_breakdown or {},
                    patterns_matched=score.patterns_matched,
                    outreach_status=score.outreach_status,
                    email_template_id=email_template_id,
                    generated_email_subject=generated_subject,
                    generated_email_body=generated_body,
                    email_generated_at=email_generated_at.isoformat() if email_generated_at else None,
                    scored_at=score.scored_at.isoformat() if score.scored_at else None,
                    has_feedback=has_feedback
                ),
                greenhouse_profile_url=greenhouse_url
            ))
        
        has_next = offset + page_size < total
        
        logger.info(
            "candidates_v2_fetched",
            customer_id=current_user.customer_id,
            total=total,
            page=page,
            returned=len(results)
        )
        
        return CandidatesWithScoresListResponse(
            candidates=results,
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next
        )
    
    except Exception as e:
        logger.error(
            "candidates_v2_fetch_error",
            customer_id=current_user.customer_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch candidates: {str(e)}"
        )


class SaveGeneratedEmailRequest(BaseModel):
    """Request to save a generated email for a candidate in an analysis."""
    candidate_id: int = Field(..., description="Candidate database ID")
    analysis_id: str = Field(..., description="Analysis ID")
    email_template_id: int = Field(..., description="Email template ID used")
    subject: str = Field(..., description="Generated email subject")
    body: str = Field(..., description="Generated email body")


class SaveGeneratedEmailResponse(BaseModel):
    """Response after saving generated email."""
    success: bool
    message: str
    score_id: int


@router.post(
    "/v2/candidates/save-email",
    response_model=SaveGeneratedEmailResponse,
    summary="Save generated email for candidate",
    description="Save the generated email for a candidate in a specific analysis"
)
async def save_generated_email(
    request: SaveGeneratedEmailRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Save a generated email for a candidate in an analysis.
    
    This stores the email subject, body, and template used in the candidate_analysis_scores table.
    """
    try:
        candidate_service = CandidateService(db, current_user.customer_id)
        
        # Verify candidate belongs to this customer
        candidate = candidate_service.get_candidate_by_id(request.candidate_id)
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found"
            )
        
        # Save the generated email
        score = candidate_service.save_generated_email(
            candidate_id=request.candidate_id,
            analysis_id=request.analysis_id,
            email_template_id=request.email_template_id,
            subject=request.subject,
            body=request.body
        )
        
        logger.info(
            "generated_email_saved",
            customer_id=current_user.customer_id,
            candidate_id=request.candidate_id,
            analysis_id=request.analysis_id,
            email_template_id=request.email_template_id
        )
        
        return SaveGeneratedEmailResponse(
            success=True,
            message="Generated email saved successfully",
            score_id=score.id
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "save_generated_email_error",
            customer_id=current_user.customer_id,
            candidate_id=request.candidate_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save generated email: {str(e)}"
        )


class UpdateOutreachStatusRequest(BaseModel):
    """Request to update outreach status for a candidate."""
    candidate_id: int = Field(..., description="Candidate database ID")
    analysis_id: str = Field(..., description="Analysis ID")
    status: str = Field(..., description="New outreach status: pending, sent, replied, etc.")
    notes: Optional[str] = Field(None, description="Optional notes")


@router.post(
    "/v2/candidates/update-status",
    summary="Update candidate outreach status",
    description="Update the outreach status for a candidate in a specific analysis"
)
async def update_candidate_outreach_status(
    request: UpdateOutreachStatusRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Update the outreach status for a candidate in an analysis.
    """
    try:
        candidate_service = CandidateService(db, current_user.customer_id)
        
        score = candidate_service.update_outreach_status(
            candidate_id=request.candidate_id,
            analysis_id=request.analysis_id,
            status=request.status,
            notes=request.notes
        )
        
        logger.info(
            "outreach_status_updated",
            customer_id=current_user.customer_id,
            candidate_id=request.candidate_id,
            analysis_id=request.analysis_id,
            status=request.status
        )
        
        return {
            "success": True,
            "message": f"Outreach status updated to {request.status}",
            "score_id": score.id
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "update_outreach_status_error",
            customer_id=current_user.customer_id,
            candidate_id=request.candidate_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update outreach status: {str(e)}"
        )


@router.get(
    "/v2/candidates/{candidate_id}",
    response_model=CandidateProfileResponse,
    summary="Get candidate profile",
    description="Get a single candidate's profile by ID"
)
async def get_candidate_profile(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Get a candidate's profile by ID.
    """
    try:
        candidate_service = CandidateService(db, current_user.customer_id)
        candidate = candidate_service.get_candidate_by_id(candidate_id)
        
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found"
            )
        
        return CandidateProfileResponse(
            id=candidate.id,
            email=candidate.email,
            full_name=candidate.full_name,
            phone=candidate.phone,
            linkedin_url=candidate.linkedin_url,
            github_url=candidate.github_url,
            location=candidate.location,
            current_title=candidate.current_title,
            current_company=candidate.current_company,
            greenhouse_id=candidate.greenhouse_id,
            pdl_id=candidate.pdl_id,
            source=candidate.source,
            skills=candidate.skills,
            load_date=candidate.load_date.isoformat() if candidate.load_date else None,
            last_verified_at=candidate.last_verified_at.isoformat() if candidate.last_verified_at else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_candidate_profile_error",
            customer_id=current_user.customer_id,
            candidate_id=candidate_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidate profile: {str(e)}"
        )


@router.get(
    "/v2/candidates/{candidate_id}/scores",
    summary="Get all scores for a candidate",
    description="Get all analysis scores for a specific candidate"
)
async def get_candidate_scores(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Get all analysis scores for a candidate.
    
    Returns all analyses where this candidate was scored.
    """
    try:
        candidate_service = CandidateService(db, current_user.customer_id)
        candidate = candidate_service.get_candidate_by_id(candidate_id)
        
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found"
            )
        
        # Get all scores for this candidate
        scores = db.query(CandidateAnalysisScore).filter(
            CandidateAnalysisScore.candidate_id == candidate_id
        ).order_by(CandidateAnalysisScore.scored_at.desc()).all()
        
        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate.full_name,
            "scores": [
                {
                    "id": score.id,
                    "analysis_id": score.analysis_id,
                    "overall_score": score.overall_score,
                    "rank_overall": score.rank_overall,
                    "source": score.source,
                    "confidence": score.confidence,
                    "score_breakdown": score.score_breakdown,
                    "outreach_status": score.outreach_status,
                    "email_generated": score.generated_email_subject is not None,
                    "scored_at": score.scored_at.isoformat() if score.scored_at else None
                }
                for score in scores
            ],
            "total_analyses": len(scores)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_candidate_scores_error",
            customer_id=current_user.customer_id,
            candidate_id=candidate_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidate scores: {str(e)}"
        )


# ============================================================================
# ADD CANDIDATE TO ATS
# ============================================================================

class AddToATSRequest(BaseModel):
    """Request to add a market candidate to the ATS."""
    candidate_id: int = Field(..., description="ID of the candidate to add")
    analysis_id: str = Field(..., description="Analysis ID (used to get the job ID)")
    connector_id: int = Field(..., description="ATS connector ID")
    notes: Optional[str] = Field(None, description="Optional notes to add to the candidate")


class AddToATSResponse(BaseModel):
    """Response from adding a candidate to the ATS."""
    success: bool
    message: str
    greenhouse_candidate_id: Optional[int] = None
    greenhouse_profile_url: Optional[str] = None
    error: Optional[str] = None


@router.post(
    "/v2/candidates/add-to-ats",
    response_model=AddToATSResponse,
    summary="Add market candidate to ATS",
    description="Add a market search candidate to Greenhouse ATS"
)
async def add_candidate_to_ats(
    request: AddToATSRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    Add a market search candidate to Greenhouse.
    
    This endpoint:
    1. Gets the candidate profile from our database
    2. Gets the job ID from the analysis configuration
    3. Finds or creates the Greenhouse user for crediting
    4. Calls Greenhouse API to create the candidate
    5. Updates our database with the Greenhouse ID
    
    Requirements:
    - Candidate must be from 'market' source (not already in ATS)
    - Analysis must have a selected job ID
    - User must have a matching Greenhouse account (by email)
    """
    try:
        from src.services.ingestion.connector_service import ConnectorService
        from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
        from src.models.analysis_config import AnalysisConfig
        from src.models.auth import User
        import asyncio
        
        logger.info(
            "add_to_ats_request",
            customer_id=current_user.customer_id,
            candidate_id=request.candidate_id,
            analysis_id=request.analysis_id,
            connector_id=request.connector_id
        )
        
        # 1. Get the candidate
        candidate_service = CandidateService(db, current_user.customer_id)
        candidate = candidate_service.get_candidate_by_id(request.candidate_id)
        
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found"
            )
        
        # Check if candidate is already in Greenhouse
        if candidate.greenhouse_id:
            return AddToATSResponse(
                success=False,
                message="Candidate is already in Greenhouse",
                greenhouse_candidate_id=candidate.greenhouse_id,
                greenhouse_profile_url=f"https://app.greenhouse.io/people/{candidate.greenhouse_id}"
            )
        
        # Check if candidate is from market source
        # Get the score to check source
        score = db.query(CandidateAnalysisScore).filter(
            CandidateAnalysisScore.candidate_id == request.candidate_id,
            CandidateAnalysisScore.analysis_id == request.analysis_id
        ).first()
        
        if score and score.source not in ['market', 'previous_candidate']:
            return AddToATSResponse(
                success=False,
                message="Only market search or previous candidates can be added to ATS. This candidate is already an applicant.",
                error="invalid_source"
            )
        
        # 2. Get the job ID from the analysis config
        # First try to find the config that ran this analysis
        config = db.query(AnalysisConfig).filter(
            AnalysisConfig.last_analysis_id == request.analysis_id,
            AnalysisConfig.customer_id == current_user.customer_id
        ).first()
        
        if not config:
            # Try to find by analysis_id pattern in name or just get the most recent
            logger.warning(
                "analysis_config_not_found_by_analysis_id",
                analysis_id=request.analysis_id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not find analysis configuration. Please ensure the analysis has a job selected."
            )
        
        job_id = config.selected_job_id
        if not job_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis configuration does not have a job selected. Cannot add candidate without a target job."
            )
        
        # 3. Get the connector and credentials
        connector_service = ConnectorService(db)
        connector_config = connector_service.get_configuration_by_id(request.connector_id)
        
        if not connector_config or connector_config.connector_type != "greenhouse":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or non-Greenhouse connector"
            )
        
        credentials = connector_service.get_credentials(connector_config)
        
        # 4. Get the current user's email to find their Greenhouse user ID
        user = db.query(User).filter(User.id == current_user.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not find user record"
            )
        
        user_email = user.email
        
        # 5. Create connector and find Greenhouse user
        connector = GreenhouseConnector(
            credentials=credentials,
            config={},
            customer_id=current_user.customer_id
        )
        
        # Find the Greenhouse user by email
        greenhouse_user = await connector.find_user_by_email(user_email)
        
        if not greenhouse_user:
            # If no matching user, we'll use a default or raise an error
            logger.warning(
                "greenhouse_user_not_found",
                user_email=user_email
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not find Greenhouse user with email {user_email}. Please ensure your email matches your Greenhouse account."
            )
        
        greenhouse_user_id = greenhouse_user["id"]
        
        # 6. Prepare candidate data
        # Split full name into first and last
        full_name = candidate.full_name or "Unknown"
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Build notes with Eliza context
        notes_text = f"Added from Eliza Platform\n"
        notes_text += f"Analysis ID: {request.analysis_id}\n"
        notes_text += f"Source: Market Search (Eliza People Search)\n"
        notes_text += f"Added by: {user.full_name or user.email}\n"
        if score:
            notes_text += f"Eliza Score: {score.overall_score:.1f}%\n"
        if request.notes:
            notes_text += f"\nNotes: {request.notes}"
        
        # 7. Add candidate to Greenhouse
        result = await connector.add_candidate(
            first_name=first_name,
            last_name=last_name,
            email=candidate.email or f"unknown_{candidate.id}@placeholder.com",
            job_id=int(job_id),
            on_behalf_of_user_id=greenhouse_user_id,
            phone=candidate.phone,
            linkedin_url=candidate.linkedin_url,
            location=candidate.location,
            source_name="Eliza",
            notes=notes_text
        )
        
        if result.get("success"):
            greenhouse_id = result.get("greenhouse_id")
            
            # 8. Update our database with the Greenhouse ID
            candidate.greenhouse_id = greenhouse_id
            candidate.source = "greenhouse"  # Update source since they're now in ATS
            db.commit()
            
            logger.info(
                "candidate_added_to_greenhouse",
                customer_id=current_user.customer_id,
                candidate_id=request.candidate_id,
                greenhouse_id=greenhouse_id,
                job_id=job_id
            )
            
            return AddToATSResponse(
                success=True,
                message=f"Successfully added {full_name} to Greenhouse",
                greenhouse_candidate_id=greenhouse_id,
                greenhouse_profile_url=f"https://app.greenhouse.io/people/{greenhouse_id}"
            )
        else:
            return AddToATSResponse(
                success=False,
                message="Failed to add candidate to Greenhouse",
                error=result.get("error", "Unknown error")
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "add_to_ats_error",
            customer_id=current_user.customer_id,
            candidate_id=request.candidate_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add candidate to ATS: {str(e)}"
        )
