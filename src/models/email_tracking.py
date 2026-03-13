"""
Email Tracking Models

Models for tracking candidate outreach emails, opens, clicks, and replies.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

from src.models.database import BaseModel, Base


class EmailStatus(str, Enum):
    """Email status values."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


class DeliveryStatus(str, Enum):
    """Delivery status values."""
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    DEFERRED = "deferred"
    FAILED = "failed"


class SentVia(str, Enum):
    """How email was sent."""
    GMAIL_COMPOSE = "gmail_compose"
    GMAIL_API = "gmail_api"
    SMTP = "smtp"


class OutreachEmail(BaseModel):
    """
    Stores each email sent to a candidate.
    
    Tracks email content, delivery status, and engagement metrics.
    """
    __tablename__ = "outreach_emails"
    __table_args__ = (
        Index('idx_outreach_emails_customer', 'customer_id'),
        Index('idx_outreach_emails_analysis', 'talent_analysis_id'),
        Index('idx_outreach_emails_status', 'status'),
        Index('idx_outreach_emails_sent_at', 'sent_at'),
        Index('idx_outreach_emails_email_id', 'email_id', unique=True),
        Index('idx_outreach_emails_candidate_email', 'candidate_email'),
        Index('idx_outreach_emails_gmail_thread', 'gmail_thread_id'),
        {'extend_existing': True}
    )
    
    email_id = Column(String(100), unique=True, nullable=False, index=True)  # UUID for tracking URLs
    customer_id = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Who sent it
    talent_analysis_id = Column(String(100), ForeignKey('talent_analyses.analysis_id'), nullable=True)
    candidate_id = Column(String(255), nullable=False)  # Reference to candidate
    candidate_name = Column(String(255), nullable=True)
    candidate_email = Column(String(255), nullable=False, index=True)
    
    # Email content
    subject = Column(Text, nullable=False)
    body_html = Column(Text, nullable=True)  # HTML version with tracking pixels/links
    body_text = Column(Text, nullable=True)  # Plain text version
    email_template_id = Column(Integer, nullable=True)  # If using template
    
    # Sending metadata
    sent_via = Column(String(50), nullable=False, server_default='gmail_compose')
    gmail_message_id = Column(String(255), nullable=True)  # Gmail API message ID if sent via API
    gmail_thread_id = Column(String(255), nullable=True, index=True)  # Gmail thread ID for reply tracking
    
    # Status tracking
    status = Column(String(50), nullable=False, server_default='pending')
    delivery_status = Column(String(50), nullable=True)
    delivery_error = Column(Text, nullable=True)
    
    # Timing
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    first_opened_at = Column(DateTime(timezone=True), nullable=True)
    last_opened_at = Column(DateTime(timezone=True), nullable=True)
    
    # Engagement metrics (denormalized for quick queries)
    open_count = Column(Integer, nullable=False, server_default='0')
    click_count = Column(Integer, nullable=False, server_default='0')
    reply_count = Column(Integer, nullable=False, server_default='0')
    is_replied = Column(Boolean, nullable=False, server_default='false')
    last_reply_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional metadata (using email_metadata to avoid SQLAlchemy reserved name conflict)
    email_metadata = Column(JSONB, nullable=True)  # Additional data
    
    # Relationships
    opens = relationship("EmailOpen", back_populates="email", cascade="all, delete-orphan")
    clicks = relationship("EmailClick", back_populates="email", cascade="all, delete-orphan")
    replies = relationship("EmailReply", back_populates="email", cascade="all, delete-orphan")
    links = relationship("EmailLink", back_populates="email", cascade="all, delete-orphan")


class EmailOpen(BaseModel):
    """
    Tracks each email open event.
    
    Records when an email is opened, with device and location information.
    """
    __tablename__ = "email_opens"
    __table_args__ = (
        Index('idx_email_opens_email_id', 'email_id'),
        Index('idx_email_opens_opened_at', 'opened_at'),
        Index('idx_email_opens_unique', 'email_id', 'is_unique', postgresql_where=func.text('is_unique = true')),
        {'extend_existing': True}
    )
    
    email_id = Column(String(100), ForeignKey('outreach_emails.email_id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Open metadata
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    device_type = Column(String(50), nullable=True)  # mobile, desktop, tablet
    email_client = Column(String(100), nullable=True)  # gmail, outlook, apple_mail, etc.
    location_country = Column(String(100), nullable=True)
    location_city = Column(String(100), nullable=True)
    
    # Tracking metadata
    is_unique = Column(Boolean, nullable=False, server_default='true')  # First open for this email
    
    # Relationships
    email = relationship("OutreachEmail", back_populates="opens")


class EmailClick(BaseModel):
    """
    Tracks each link click in emails.
    
    Records when a link is clicked, with device and location information.
    """
    __tablename__ = "email_clicks"
    __table_args__ = (
        Index('idx_email_clicks_email_id', 'email_id'),
        Index('idx_email_clicks_clicked_at', 'clicked_at'),
        Index('idx_email_clicks_unique', 'email_id', 'link_url', 'is_unique', postgresql_where=func.text('is_unique = true')),
        {'extend_existing': True}
    )
    
    email_id = Column(String(100), ForeignKey('outreach_emails.email_id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Click metadata
    clicked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    link_url = Column(Text, nullable=False)  # Original destination URL
    link_text = Column(Text, nullable=True)  # Link text/anchor
    link_position = Column(Integer, nullable=True)  # Position in email
    
    # User metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    device_type = Column(String(50), nullable=True)
    location_country = Column(String(100), nullable=True)
    location_city = Column(String(100), nullable=True)
    
    # Tracking metadata
    is_unique = Column(Boolean, nullable=False, server_default='true')  # First click for this link
    
    # Relationships
    email = relationship("OutreachEmail", back_populates="clicks")


class EmailReply(BaseModel):
    """
    Tracks replies to sent emails.
    
    Records when a candidate replies, with reply content.
    """
    __tablename__ = "email_replies"
    __table_args__ = (
        Index('idx_email_replies_email_id', 'email_id'),
        Index('idx_email_replies_replied_at', 'replied_at'),
        Index('idx_email_replies_gmail_thread', 'gmail_thread_id'),
        {'extend_existing': True}
    )
    
    email_id = Column(String(100), ForeignKey('outreach_emails.email_id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Reply metadata
    replied_at = Column(DateTime(timezone=True), nullable=False, index=True)
    gmail_message_id = Column(String(255), nullable=True)  # Gmail API message ID
    gmail_thread_id = Column(String(255), nullable=True, index=True)  # Gmail thread ID
    subject = Column(Text, nullable=True)
    body_preview = Column(Text, nullable=True)  # First 500 chars
    body_full = Column(Text, nullable=True)  # Full reply content
    
    # Reply analysis (for future use)
    is_interested = Column(Boolean, nullable=True)  # Detected interest signals
    
    # Relationships
    email = relationship("OutreachEmail", back_populates="replies")


class EmailLink(BaseModel):
    """
    Stores all links in emails for click tracking.
    
    Tracks which links are in each email and their click performance.
    """
    __tablename__ = "email_links"
    __table_args__ = (
        Index('idx_email_links_email_id', 'email_id'),
        Index('idx_email_links_tracking_url', 'tracking_url'),
        {'extend_existing': True}
    )
    
    email_id = Column(String(100), ForeignKey('outreach_emails.email_id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Link details
    original_url = Column(Text, nullable=False)
    tracking_url = Column(Text, nullable=False, index=True)  # Our tracking URL
    link_text = Column(Text, nullable=True)
    link_position = Column(Integer, nullable=True)  # Order in email
    
    # Tracking
    click_count = Column(Integer, nullable=False, server_default='0')
    unique_click_count = Column(Integer, nullable=False, server_default='0')
    first_clicked_at = Column(DateTime(timezone=True), nullable=True)
    last_clicked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    email = relationship("OutreachEmail", back_populates="links")

