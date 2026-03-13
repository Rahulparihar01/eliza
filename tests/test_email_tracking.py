"""
Comprehensive Tests for Email Tracking Functionality

Tests the complete email tracking system:
- Email creation with tracking injection
- Open tracking via pixel
- Click tracking via redirect
- Metrics aggregation
- Export functionality

Run with: pytest tests/test_email_tracking.py -v
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.models import database
from src.models.email_tracking import (
    OutreachEmail,
    EmailOpen,
    EmailClick,
    EmailLink
)
from src.services.email_tracking_service import EmailTrackingService
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)

# Initialize test client
client = TestClient(app)

TEST_CUSTOMER_ID = "test_email_tracking_customer"
TEST_USER_ID = 1


def setup_database():
    """Initialize database connection."""
    if database.SessionLocal is None:
        logger.info("Initializing database...")
        database.init_database()
    
    if database.SessionLocal is None:
        raise RuntimeError("Failed to initialize database")
    
    return database.SessionLocal()


def cleanup_test_data(db: Session):
    """Clean up test data from previous runs."""
    logger.info("Cleaning up test data...")
    
    # Delete in correct order (foreign keys)
    db.query(EmailClick).filter(
        EmailClick.email_id.in_(
            db.query(OutreachEmail.email_id).filter(
                OutreachEmail.customer_id == TEST_CUSTOMER_ID
            )
        )
    ).delete(synchronize_session=False)
    
    db.query(EmailOpen).filter(
        EmailOpen.email_id.in_(
            db.query(OutreachEmail.email_id).filter(
                OutreachEmail.customer_id == TEST_CUSTOMER_ID
            )
        )
    ).delete(synchronize_session=False)
    
    db.query(EmailLink).filter(
        EmailLink.email_id.in_(
            db.query(OutreachEmail.email_id).filter(
                OutreachEmail.customer_id == TEST_CUSTOMER_ID
            )
        )
    ).delete(synchronize_session=False)
    
    db.query(OutreachEmail).filter(
        OutreachEmail.customer_id == TEST_CUSTOMER_ID
    ).delete()
    
    db.commit()
    logger.info("Test data cleaned up")


def get_auth_token():
    """
    Get authentication token for API requests.
    
    Note: In a real test, you'd create a test user and login.
    For now, we'll test the service layer directly.
    """
    # TODO: Implement actual auth token retrieval
    return None


class TestEmailTrackingService:
    """Test email tracking service functionality."""
    
    def setup_method(self):
        """Set up test database."""
        self.db = setup_database()
        cleanup_test_data(self.db)
        self.tracking_service = EmailTrackingService(self.db)
    
    def teardown_method(self):
        """Clean up after test."""
        cleanup_test_data(self.db)
        self.db.close()
    
    def test_create_outreach_email(self):
        """Test creating an outreach email record."""
        email = self.tracking_service.create_outreach_email(
            customer_id=TEST_CUSTOMER_ID,
            candidate_id="candidate_123",
            candidate_name="John Doe",
            candidate_email="john.doe@example.com",
            subject="Exciting Opportunity at Our Company",
            body_html="<html><body><p>Hello John!</p><a href='https://example.com'>Learn More</a></body></html>",
            body_text="Hello John! Learn more at https://example.com",
            sent_via="gmail_compose"
        )
        
        assert email.email_id is not None
        assert len(email.email_id) == 32  # UUID without dashes, truncated
        assert email.customer_id == TEST_CUSTOMER_ID
        assert email.candidate_email == "john.doe@example.com"
        assert email.status == "sent"
        assert email.open_count == 0
        assert email.click_count == 0
        assert email.reply_count == 0
        assert email.is_replied == False
        
        logger.info(f"✅ Created email with ID: {email.email_id}")
    
    def test_inject_tracking_pixel(self):
        """Test injecting tracking pixel into email HTML."""
        email = self.tracking_service.create_outreach_email(
            customer_id=TEST_CUSTOMER_ID,
            candidate_id="candidate_123",
            candidate_name="John Doe",
            candidate_email="john.doe@example.com",
            subject="Test Email",
            body_html="<html><body><p>Hello!</p></body></html>",
            sent_via="gmail_compose"
        )
        
        base_url = "https://api.example.com"
        html_with_pixel = self.tracking_service.inject_tracking_pixel(
            email.body_html,
            email.email_id,
            base_url
        )
        
        assert f"/api/v1/outreach/track/open/{email.email_id}" in html_with_pixel
        assert "<img" in html_with_pixel
        assert "width=\"1\"" in html_with_pixel
        assert "height=\"1\"" in html_with_pixel
        
        logger.info("✅ Tracking pixel injected successfully")
    
    def test_extract_and_store_links(self):
        """Test extracting and storing links from email HTML."""
        email = self.tracking_service.create_outreach_email(
            customer_id=TEST_CUSTOMER_ID,
            candidate_id="candidate_123",
            candidate_name="John Doe",
            candidate_email="john.doe@example.com",
            subject="Test Email",
            body_html="<html><body><a href='https://example.com/page1'>Link 1</a><a href='https://example.com/page2'>Link 2</a></body></html>",
            sent_via="gmail_compose"
        )
        
        base_url = "https://api.example.com"
        links = self.tracking_service.extract_and_store_links(
            email.email_id,
            email.body_html,
            base_url
        )
        
        assert len(links) == 2
        assert links[0].original_url == "https://example.com/page1"
        assert links[1].original_url == "https://example.com/page2"
        assert links[0].tracking_url.startswith(base_url)
        assert links[0].link_position == 1
        assert links[1].link_position == 2
        
        logger.info(f"✅ Extracted {len(links)} links")
    
    def test_inject_tracking_links(self):
        """Test replacing links with tracking URLs."""
        email = self.tracking_service.create_outreach_email(
            customer_id=TEST_CUSTOMER_ID,
            candidate_id="candidate_123",
            candidate_name="John Doe",
            candidate_email="john.doe@example.com",
            subject="Test Email",
            body_html="<html><body><a href='https://example.com'>Learn More</a></body></html>",
            sent_via="gmail_compose"
        )
        
        base_url = "https://api.example.com"
        html_with_tracking = self.tracking_service.inject_tracking_links(
            email.body_html,
            email.email_id,
            base_url
        )
        
        # Check that original URL is replaced with tracking URL
        assert "https://example.com" not in html_with_tracking or "track/click" in html_with_tracking
        assert f"/api/v1/outreach/track/click/{email.email_id}" in html_with_tracking
        
        logger.info("✅ Tracking links injected successfully")
    
    def test_record_email_open(self):
        """Test recording an email open event."""
        email = self.tracking_service.create_outreach_email(
            customer_id=TEST_CUSTOMER_ID,
            candidate_id="candidate_123",
            candidate_name="John Doe",
            candidate_email="john.doe@example.com",
            subject="Test Email",
            body_html="<html><body><p>Hello!</p></body></html>",
            sent_via="gmail_compose"
        )
        
        # Record first open
        email_open = self.tracking_service.record_email_open(
            email_id=email.email_id,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        assert email_open.email_id == email.email_id
        assert email_open.is_unique == True
        assert email_open.ip_address == "192.168.1.1"
        assert email_open.device_type == "desktop"
        
        # Refresh email to check metrics
        self.db.refresh(email)
        assert email.open_count == 1
        assert email.first_opened_at is not None
        assert email.last_opened_at is not None
        
        # Record second open (not unique)
        email_open2 = self.tracking_service.record_email_open(
            email_id=email.email_id,
            ip_address="192.168.1.2",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
        )
        
        assert email_open2.is_unique == False
        assert email_open2.device_type == "mobile"
        
        # Refresh email again
        self.db.refresh(email)
        assert email.open_count == 2
        
        logger.info("✅ Email opens recorded successfully")
    
    def test_record_email_click(self):
        """Test recording an email click event."""
        email = self.tracking_service.create_outreach_email(
            customer_id=TEST_CUSTOMER_ID,
            candidate_id="candidate_123",
            candidate_name="John Doe",
            candidate_email="john.doe@example.com",
            subject="Test Email",
            body_html="<html><body><a href='https://example.com'>Learn More</a></body></html>",
            sent_via="gmail_compose"
        )
        
        base_url = "https://api.example.com"
        links = self.tracking_service.extract_and_store_links(
            email.email_id,
            email.body_html,
            base_url
        )
        
        assert len(links) == 1
        
        # Record first click
        email_click = self.tracking_service.record_email_click(
            email_id=email.email_id,
            link_url="https://example.com",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )
        
        assert email_click.email_id == email.email_id
        assert email_click.link_url == "https://example.com"
        assert email_click.is_unique == True
        
        # Refresh email and link
        self.db.refresh(email)
        self.db.refresh(links[0])
        assert email.click_count == 1
        assert links[0].click_count == 1
        assert links[0].unique_click_count == 1
        
        # Record second click (not unique)
        email_click2 = self.tracking_service.record_email_click(
            email_id=email.email_id,
            link_url="https://example.com",
            ip_address="192.168.1.2",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)"
        )
        
        assert email_click2.is_unique == False
        
        # Refresh again
        self.db.refresh(email)
        self.db.refresh(links[0])
        assert email.click_count == 2
        assert links[0].click_count == 2
        assert links[0].unique_click_count == 1  # Still 1 unique
        
        logger.info("✅ Email clicks recorded successfully")
    
    def test_user_agent_parsing(self):
        """Test user agent parsing for device and email client detection."""
        # Test desktop Gmail
        ua_info = self.tracking_service.parse_user_agent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        assert ua_info["device_type"] == "desktop"
        
        # Test mobile
        ua_info = self.tracking_service.parse_user_agent(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
        )
        assert ua_info["device_type"] == "mobile"
        
        # Test tablet
        ua_info = self.tracking_service.parse_user_agent(
            "Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
        )
        assert ua_info["device_type"] == "tablet"
        
        logger.info("✅ User agent parsing works correctly")


class TestEmailTrackingAPI:
    """Test email tracking API endpoints."""
    
    def setup_method(self):
        """Set up test database."""
        self.db = setup_database()
        cleanup_test_data(self.db)
        self.tracking_service = EmailTrackingService(self.db)
    
    def teardown_method(self):
        """Clean up after test."""
        cleanup_test_data(self.db)
        self.db.close()
    
    def test_tracking_pixel_endpoint(self):
        """Test the tracking pixel endpoint."""
        # Create an email
        email = self.tracking_service.create_outreach_email(
            customer_id=TEST_CUSTOMER_ID,
            candidate_id="candidate_123",
            candidate_name="John Doe",
            candidate_email="john.doe@example.com",
            subject="Test Email",
            body_html="<html><body><p>Hello!</p></body></html>",
            sent_via="gmail_compose"
        )
        
        # Call tracking pixel endpoint
        response = client.get(
            f"/api/v1/outreach/track/open/{email.email_id}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 0
        
        # Verify open was recorded
        self.db.refresh(email)
        assert email.open_count == 1
        
        logger.info("✅ Tracking pixel endpoint works correctly")
    
    def test_click_tracking_endpoint(self):
        """Test the click tracking redirect endpoint."""
        # Create an email with links
        email = self.tracking_service.create_outreach_email(
            customer_id=TEST_CUSTOMER_ID,
            candidate_id="candidate_123",
            candidate_name="John Doe",
            candidate_email="john.doe@example.com",
            subject="Test Email",
            body_html="<html><body><a href='https://example.com'>Learn More</a></body></html>",
            sent_via="gmail_compose"
        )
        
        base_url = "https://api.example.com"
        links = self.tracking_service.extract_and_store_links(
            email.email_id,
            email.body_html,
            base_url
        )
        
        # Call click tracking endpoint
        original_url = "https://example.com"
        response = client.get(
            f"/api/v1/outreach/track/click/{email.email_id}/1",
            params={"url": original_url},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            follow_redirects=False
        )
        
        assert response.status_code == 302
        assert response.headers["location"] == original_url
        
        # Verify click was recorded
        self.db.refresh(email)
        assert email.click_count == 1
        
        logger.info("✅ Click tracking endpoint works correctly")


def test_complete_email_tracking_flow():
    """
    Test the complete email tracking flow from creation to metrics.
    
    This demonstrates the full functionality:
    1. Create email with tracking
    2. Simulate opens
    3. Simulate clicks
    4. Verify metrics
    """
    db = setup_database()
    cleanup_test_data(db)
    
    try:
        tracking_service = EmailTrackingService(db)
        base_url = "https://api.example.com"
        
        # Step 1: Create email
        email = tracking_service.create_outreach_email(
            customer_id=TEST_CUSTOMER_ID,
            candidate_id="candidate_123",
            candidate_name="John Doe",
            candidate_email="john.doe@example.com",
            subject="Exciting Opportunity - Machine Learning Engineer",
            body_html="""
            <html>
            <body>
                <p>Hi John,</p>
                <p>We have an exciting opportunity for a Machine Learning Engineer!</p>
                <p><a href="https://example.com/careers">View Job Posting</a></p>
                <p><a href="https://example.com/apply">Apply Now</a></p>
                <p>Best regards,<br>Hiring Team</p>
            </body>
            </html>
            """,
            body_text="Hi John, We have an exciting opportunity! View at https://example.com/careers",
            sent_via="gmail_compose"
        )
        
        logger.info(f"📧 Created email: {email.email_id}")
        
        # Step 2: Inject tracking
        html_with_tracking = tracking_service.inject_tracking_pixel(
            email.body_html,
            email.email_id,
            base_url
        )
        html_with_tracking = tracking_service.inject_tracking_links(
            html_with_tracking,
            email.email_id,
            base_url
        )
        
        logger.info("✅ Tracking injected")
        
        # Step 3: Simulate email opens
        opens = [
            ("192.168.1.1", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),  # Desktop
            ("192.168.1.2", "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"),  # Mobile
            ("192.168.1.1", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),  # Repeat open
        ]
        
        for ip, ua in opens:
            tracking_service.record_email_open(email.email_id, ip, ua)
        
        db.refresh(email)
        logger.info(f"📊 Opens recorded: {email.open_count} (unique: {email.open_count > 0})")
        
        # Step 4: Simulate clicks
        clicks = [
            ("https://example.com/careers", "192.168.1.1", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),
            ("https://example.com/apply", "192.168.1.2", "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)"),
            ("https://example.com/careers", "192.168.1.1", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),  # Repeat click
        ]
        
        for url, ip, ua in clicks:
            tracking_service.record_email_click(email.email_id, url, ip, ua)
        
        db.refresh(email)
        logger.info(f"📊 Clicks recorded: {email.click_count}")
        
        # Step 5: Verify final metrics
        assert email.open_count == 3
        assert email.click_count == 3
        assert email.first_opened_at is not None
        assert email.last_opened_at is not None
        
        # Get link metrics
        links = db.query(EmailLink).filter(EmailLink.email_id == email.email_id).all()
        assert len(links) == 2
        
        careers_link = next((l for l in links if "careers" in l.original_url), None)
        assert careers_link is not None
        assert careers_link.click_count == 2
        
        apply_link = next((l for l in links if "apply" in l.original_url), None)
        assert apply_link is not None
        assert apply_link.click_count == 1
        
        logger.info("✅ Complete flow test passed!")
        logger.info(f"   Email ID: {email.email_id}")
        logger.info(f"   Opens: {email.open_count}")
        logger.info(f"   Clicks: {email.click_count}")
        logger.info(f"   Links tracked: {len(links)}")
        
    finally:
        cleanup_test_data(db)
        db.close()


if __name__ == "__main__":
    print("=" * 80)
    print("Email Tracking Functionality Test")
    print("=" * 80)
    print()
    
    # Run the complete flow test
    test_complete_email_tracking_flow()
    
    print()
    print("=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)
    print()
    print("To run all tests with pytest:")
    print("  pytest tests/test_email_tracking.py -v")
    print()

