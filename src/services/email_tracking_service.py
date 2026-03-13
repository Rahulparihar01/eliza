"""
Email Tracking Service

Service for tracking email opens, clicks, and replies.
Handles user agent parsing, device detection, and IP geolocation.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
import re
import uuid

from src.models.email_tracking import (
    OutreachEmail,
    EmailOpen,
    EmailClick,
    EmailReply,
    EmailLink
)
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class EmailTrackingService:
    """Service for tracking email engagement metrics."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def parse_user_agent(self, user_agent: Optional[str]) -> Dict[str, Optional[str]]:
        """
        Parse user agent string to extract device and email client info.
        
        Returns:
            Dict with device_type, email_client
        """
        if not user_agent:
            return {"device_type": None, "email_client": None}
        
        user_agent_lower = user_agent.lower()
        
        # Detect email client
        email_client = None
        if "gmail" in user_agent_lower:
            email_client = "gmail"
        elif "outlook" in user_agent_lower or "microsoft" in user_agent_lower:
            email_client = "outlook"
        elif "applewebkit" in user_agent_lower and "mobile" in user_agent_lower:
            email_client = "apple_mail"
        elif "thunderbird" in user_agent_lower:
            email_client = "thunderbird"
        elif "yahoo" in user_agent_lower:
            email_client = "yahoo"
        
        # Detect device type
        device_type = None
        if "mobile" in user_agent_lower or "android" in user_agent_lower or "iphone" in user_agent_lower:
            device_type = "mobile"
        elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
            device_type = "tablet"
        else:
            device_type = "desktop"
        
        return {
            "device_type": device_type,
            "email_client": email_client
        }
    
    def get_ip_location(self, ip_address: Optional[str]) -> Dict[str, Optional[str]]:
        """
        Get location from IP address (basic implementation).
        
        Note: For production, consider using a geolocation service like MaxMind GeoIP2.
        For now, we'll return None values and can enhance later.
        
        Returns:
            Dict with location_country, location_city
        """
        # TODO: Implement IP geolocation using a service
        # For now, return None values
        return {
            "location_country": None,
            "location_city": None
        }
    
    def record_email_open(
        self,
        email_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> EmailOpen:
        """
        Record an email open event.
        
        Args:
            email_id: Unique email identifier
            ip_address: IP address of the opener
            user_agent: User agent string
            
        Returns:
            EmailOpen record
        """
        # Get the email record
        email = self.db.query(OutreachEmail).filter(
            OutreachEmail.email_id == email_id
        ).first()
        
        if not email:
            logger.warning(
                "email_not_found_for_open_tracking",
                email_id=email_id
            )
            raise ValueError(f"Email not found: {email_id}")
        
        # Parse user agent
        ua_info = self.parse_user_agent(user_agent)
        
        # Get location (basic for now)
        location_info = self.get_ip_location(ip_address)
        
        # Check if this is the first open
        existing_opens = self.db.query(EmailOpen).filter(
            EmailOpen.email_id == email_id
        ).count()
        
        is_unique = existing_opens == 0
        
        # Create open record
        email_open = EmailOpen(
            email_id=email_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=ua_info["device_type"],
            email_client=ua_info["email_client"],
            location_country=location_info["location_country"],
            location_city=location_info["location_city"],
            is_unique=is_unique,
            opened_at=datetime.now(timezone.utc)
        )
        
        self.db.add(email_open)
        
        # Update email metrics
        email.open_count = email.open_count + 1
        if is_unique:
            email.first_opened_at = datetime.now(timezone.utc)
        email.last_opened_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(email_open)
        
        logger.info(
            "email_opened",
            email_id=email_id,
            is_unique=is_unique,
            device_type=ua_info["device_type"],
            email_client=ua_info["email_client"],
            open_count=email.open_count
        )
        
        return email_open
    
    def record_email_click(
        self,
        email_id: str,
        link_url: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> EmailClick:
        """
        Record an email link click event.
        
        Args:
            email_id: Unique email identifier
            link_url: Original destination URL
            ip_address: IP address of the clicker
            user_agent: User agent string
            
        Returns:
            EmailClick record
        """
        # Get the email record
        email = self.db.query(OutreachEmail).filter(
            OutreachEmail.email_id == email_id
        ).first()
        
        if not email:
            logger.warning(
                "email_not_found_for_click_tracking",
                email_id=email_id
            )
            raise ValueError(f"Email not found: {email_id}")
        
        # Find the link record
        email_link = self.db.query(EmailLink).filter(
            and_(
                EmailLink.email_id == email_id,
                EmailLink.original_url == link_url
            )
        ).first()
        
        # Parse user agent
        ua_info = self.parse_user_agent(user_agent)
        
        # Get location
        location_info = self.get_ip_location(ip_address)
        
        # Check if this is the first click for this link
        existing_clicks = self.db.query(EmailClick).filter(
            and_(
                EmailClick.email_id == email_id,
                EmailClick.link_url == link_url
            )
        ).count()
        
        is_unique = existing_clicks == 0
        
        # Create click record
        email_click = EmailClick(
            email_id=email_id,
            link_url=link_url,
            link_text=email_link.link_text if email_link else None,
            link_position=email_link.link_position if email_link else None,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=ua_info["device_type"],
            location_country=location_info["location_country"],
            location_city=location_info["location_city"],
            is_unique=is_unique,
            clicked_at=datetime.now(timezone.utc)
        )
        
        self.db.add(email_click)
        
        # Update email metrics
        email.click_count = email.click_count + 1
        
        # Update link metrics if link record exists
        if email_link:
            email_link.click_count = email_link.click_count + 1
            if is_unique:
                email_link.unique_click_count = email_link.unique_click_count + 1
                email_link.first_clicked_at = datetime.now(timezone.utc)
            email_link.last_clicked_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(email_click)
        
        logger.info(
            "email_clicked",
            email_id=email_id,
            link_url=link_url,
            is_unique=is_unique,
            click_count=email.click_count
        )
        
        return email_click
    
    def create_outreach_email(
        self,
        customer_id: str,
        candidate_id: str,
        candidate_name: str,
        candidate_email: str,
        subject: str,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
        talent_analysis_id: Optional[str] = None,
        user_id: Optional[int] = None,
        sent_via: str = "gmail_compose",
        gmail_message_id: Optional[str] = None,
        gmail_thread_id: Optional[str] = None,
        scheduled_for: Optional[datetime] = None
    ) -> OutreachEmail:
        """
        Create a new outreach email record.
        
        Returns:
            OutreachEmail record with generated email_id
        """
        # Generate unique email ID for tracking
        email_id = str(uuid.uuid4()).replace("-", "")[:32]
        
        # Determine status
        status = "pending" if scheduled_for else "sent"
        
        outreach_email = OutreachEmail(
            email_id=email_id,
            customer_id=customer_id,
            user_id=user_id,
            talent_analysis_id=talent_analysis_id,
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            sent_via=sent_via,
            gmail_message_id=gmail_message_id,
            gmail_thread_id=gmail_thread_id,
            status=status,
            scheduled_for=scheduled_for,
            sent_at=datetime.now(timezone.utc) if not scheduled_for else None
        )
        
        self.db.add(outreach_email)
        self.db.commit()
        self.db.refresh(outreach_email)
        
        logger.info(
            "outreach_email_created",
            email_id=email_id,
            candidate_email=candidate_email,
            status=status
        )
        
        return outreach_email
    
    def extract_and_store_links(
        self,
        email_id: str,
        body_html: str,
        base_url: str
    ) -> list[EmailLink]:
        """
        Extract all links from email HTML and store them for tracking.
        
        Args:
            email_id: Unique email identifier
            body_html: HTML content of the email
            base_url: Base URL for the API (e.g., "https://api.example.com")
            
        Returns:
            List of EmailLink records
        """
        # Find all links in HTML
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
        matches = re.finditer(link_pattern, body_html, re.IGNORECASE)
        
        email_links = []
        for idx, match in enumerate(matches, start=1):
            url = match.group(1)
            link_text = match.group(2).strip()
            
            # Skip mailto: links and tracking URLs
            if url.startswith("mailto:") or url.startswith("tel:"):
                continue
            
            # Generate absolute tracking URL
            tracking_url = f"{base_url}/api/v1/outreach/track/click/{email_id}/{idx}?url={url}"
            
            email_link = EmailLink(
                email_id=email_id,
                original_url=url,
                tracking_url=tracking_url,
                link_text=link_text,
                link_position=idx
            )
            
            self.db.add(email_link)
            email_links.append(email_link)
        
        self.db.commit()
        
        logger.info(
            "email_links_extracted",
            email_id=email_id,
            link_count=len(email_links)
        )
        
        return email_links
    
    def inject_tracking_pixel(self, body_html: str, email_id: str, base_url: str) -> str:
        """
        Inject tracking pixel into email HTML.
        
        Args:
            body_html: Original HTML content
            email_id: Unique email identifier
            base_url: Base URL for the API (e.g., "https://api.example.com")
            
        Returns:
            HTML with tracking pixel injected
        """
        # Create absolute tracking pixel URL
        tracking_url = f"{base_url}/api/v1/outreach/track/open/{email_id}"
        
        # Create 1x1 transparent pixel
        tracking_pixel = f'<img src="{tracking_url}" width="1" height="1" style="display:none;" alt="" />'
        
        # Inject before closing body tag, or at end if no body tag
        if "</body>" in body_html.lower():
            body_html = body_html.replace("</body>", f"{tracking_pixel}</body>")
        else:
            body_html = body_html + tracking_pixel
        
        return body_html
    
    def inject_tracking_links(self, body_html: str, email_id: str, base_url: str) -> str:
        """
        Replace all links in email HTML with tracking URLs.
        
        Args:
            body_html: Original HTML content
            email_id: Unique email identifier
            base_url: Base URL for the API (e.g., "https://api.example.com")
            
        Returns:
            HTML with tracking links injected
        """
        # First, extract and store links
        email_links = self.extract_and_store_links(email_id, body_html, base_url)
        
        # Replace links with tracking URLs
        for link in email_links:
            # Escape special regex characters in URL
            escaped_url = re.escape(link.original_url)
            # Replace href attribute
            pattern = f'href=["\']{escaped_url}["\']'
            replacement = f'href="{link.tracking_url}"'
            body_html = re.sub(pattern, replacement, body_html, flags=re.IGNORECASE)
        
        return body_html
    
    def extract_and_store_links(
        self,
        email_id: str,
        body_html: str,
        base_url: str
    ) -> list[EmailLink]:
        """
        Extract all links from email HTML and store them for tracking.
        
        Args:
            email_id: Unique email identifier
            body_html: HTML content of the email
            base_url: Base URL for the API (e.g., "https://api.example.com")
            
        Returns:
            List of EmailLink records
        """
        # Find all links in HTML
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
        matches = re.finditer(link_pattern, body_html, re.IGNORECASE)
        
        email_links = []
        for idx, match in enumerate(matches, start=1):
            url = match.group(1)
            link_text = match.group(2).strip()
            
            # Skip mailto: links and tracking URLs
            if url.startswith("mailto:") or url.startswith("tel:"):
                continue
            
            # Generate absolute tracking URL
            tracking_url = f"{base_url}/api/v1/outreach/track/click/{email_id}/{idx}?url={url}"
            
            email_link = EmailLink(
                email_id=email_id,
                original_url=url,
                tracking_url=tracking_url,
                link_text=link_text,
                link_position=idx
            )
            
            self.db.add(email_link)
            email_links.append(email_link)
        
        self.db.commit()
        
        logger.info(
            "email_links_extracted",
            email_id=email_id,
            link_count=len(email_links)
        )
        
        return email_links

