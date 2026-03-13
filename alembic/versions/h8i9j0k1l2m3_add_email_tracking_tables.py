"""add email tracking tables

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2025-10-24 20:00:00.000000

Adds tables for candidate outreach email tracking and analytics:
- outreach_emails: Stores each email sent to candidates
- email_opens: Tracks email open events
- email_clicks: Tracks link click events
- email_replies: Tracks replies to sent emails
- email_links: Stores all links in emails for click tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'h8i9j0k1l2m3'
down_revision = 'g7h8i9j0k1l2'
branch_labels = None
depends_on = None
tags = ["content"]


def upgrade():
    """Create email tracking tables."""
    
    # 1. outreach_emails table - Stores each email sent
    op.create_table(
        'outreach_emails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.String(length=100), nullable=False, unique=True),  # UUID for tracking URLs
        sa.Column('customer_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),  # Who sent it
        sa.Column('talent_analysis_id', sa.String(length=100), sa.ForeignKey('talent_analyses.analysis_id'), nullable=True),
        sa.Column('candidate_id', sa.String(length=255), nullable=False),  # Reference to candidate
        sa.Column('candidate_name', sa.String(length=255), nullable=True),
        sa.Column('candidate_email', sa.String(length=255), nullable=False),
        
        # Email content
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=True),  # HTML version with tracking pixels/links
        sa.Column('body_text', sa.Text(), nullable=True),  # Plain text version
        sa.Column('email_template_id', sa.Integer(), nullable=True),  # If using template
        
        # Sending metadata
        sa.Column('sent_via', sa.String(length=50), nullable=False, server_default='gmail_compose'),  # 'gmail_compose', 'gmail_api', 'smtp'
        sa.Column('gmail_message_id', sa.String(length=255), nullable=True),  # Gmail API message ID if sent via API
        sa.Column('gmail_thread_id', sa.String(length=255), nullable=True),  # Gmail thread ID for reply tracking
        
        # Status tracking
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),  # pending, sent, delivered, bounced, failed
        sa.Column('delivery_status', sa.String(length=50), nullable=True),  # delivered, bounced, deferred, failed
        sa.Column('delivery_error', sa.Text(), nullable=True),  # Error message if delivery failed
        
        # Timing
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),  # If scheduled
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),  # When actually sent
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),  # When delivered
        sa.Column('first_opened_at', sa.DateTime(timezone=True), nullable=True),  # First open timestamp
        sa.Column('last_opened_at', sa.DateTime(timezone=True), nullable=True),  # Last open timestamp
        
        # Engagement metrics (denormalized for quick queries)
        sa.Column('open_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('click_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reply_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_replied', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_reply_at', sa.DateTime(timezone=True), nullable=True),
        
        # Additional metadata (using email_metadata to avoid SQLAlchemy reserved name conflict)
        sa.Column('email_metadata', postgresql.JSONB(), nullable=True),  # Additional data
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for outreach_emails
    op.create_index('idx_outreach_emails_customer', 'outreach_emails', ['customer_id'])
    op.create_index('idx_outreach_emails_analysis', 'outreach_emails', ['talent_analysis_id'])
    op.create_index('idx_outreach_emails_status', 'outreach_emails', ['status'])
    op.create_index('idx_outreach_emails_sent_at', 'outreach_emails', ['sent_at'])
    op.create_index('idx_outreach_emails_email_id', 'outreach_emails', ['email_id'], unique=True)
    op.create_index('idx_outreach_emails_candidate_email', 'outreach_emails', ['candidate_email'])
    op.create_index('idx_outreach_emails_gmail_thread', 'outreach_emails', ['gmail_thread_id'])
    
    # 2. email_opens table - Tracks each email open event
    op.create_table(
        'email_opens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.String(length=100), sa.ForeignKey('outreach_emails.email_id', ondelete='CASCADE'), nullable=False),
        
        # Open metadata
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),  # IPv4 or IPv6
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('device_type', sa.String(length=50), nullable=True),  # mobile, desktop, tablet
        sa.Column('email_client', sa.String(length=100), nullable=True),  # gmail, outlook, apple_mail, etc.
        sa.Column('location_country', sa.String(length=100), nullable=True),
        sa.Column('location_city', sa.String(length=100), nullable=True),
        
        # Tracking metadata
        sa.Column('is_unique', sa.Boolean(), nullable=False, server_default='true'),  # First open for this email
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for email_opens
    op.create_index('idx_email_opens_email_id', 'email_opens', ['email_id'])
    op.create_index('idx_email_opens_opened_at', 'email_opens', ['opened_at'])
    op.create_index('idx_email_opens_unique', 'email_opens', ['email_id', 'is_unique'], postgresql_where=sa.text('is_unique = true'))
    
    # 3. email_clicks table - Tracks each link click in emails
    op.create_table(
        'email_clicks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.String(length=100), sa.ForeignKey('outreach_emails.email_id', ondelete='CASCADE'), nullable=False),
        
        # Click metadata
        sa.Column('clicked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('link_url', sa.Text(), nullable=False),  # Original destination URL
        sa.Column('link_text', sa.Text(), nullable=True),  # Link text/anchor
        sa.Column('link_position', sa.Integer(), nullable=True),  # Position in email (1st link, 2nd link, etc.)
        
        # User metadata
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('device_type', sa.String(length=50), nullable=True),
        sa.Column('location_country', sa.String(length=100), nullable=True),
        sa.Column('location_city', sa.String(length=100), nullable=True),
        
        # Tracking metadata
        sa.Column('is_unique', sa.Boolean(), nullable=False, server_default='true'),  # First click for this link
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for email_clicks
    op.create_index('idx_email_clicks_email_id', 'email_clicks', ['email_id'])
    op.create_index('idx_email_clicks_clicked_at', 'email_clicks', ['clicked_at'])
    op.create_index('idx_email_clicks_unique', 'email_clicks', ['email_id', 'link_url', 'is_unique'], postgresql_where=sa.text('is_unique = true'))
    
    # 4. email_replies table - Tracks replies to sent emails
    op.create_table(
        'email_replies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.String(length=100), sa.ForeignKey('outreach_emails.email_id', ondelete='CASCADE'), nullable=False),
        
        # Reply metadata
        sa.Column('replied_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('gmail_message_id', sa.String(length=255), nullable=True),  # Gmail API message ID
        sa.Column('gmail_thread_id', sa.String(length=255), nullable=True),  # Gmail thread ID
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('body_preview', sa.Text(), nullable=True),  # First 500 chars
        sa.Column('body_full', sa.Text(), nullable=True),  # Full reply content
        
        # Reply analysis (for future use)
        sa.Column('is_interested', sa.Boolean(), nullable=True),  # Detected interest signals
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for email_replies
    op.create_index('idx_email_replies_email_id', 'email_replies', ['email_id'])
    op.create_index('idx_email_replies_replied_at', 'email_replies', ['replied_at'])
    op.create_index('idx_email_replies_gmail_thread', 'email_replies', ['gmail_thread_id'])
    
    # 5. email_links table - Stores all links in emails for click tracking
    op.create_table(
        'email_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.String(length=100), sa.ForeignKey('outreach_emails.email_id', ondelete='CASCADE'), nullable=False),
        
        # Link details
        sa.Column('original_url', sa.Text(), nullable=False),
        sa.Column('tracking_url', sa.Text(), nullable=False),  # Our tracking URL
        sa.Column('link_text', sa.Text(), nullable=True),
        sa.Column('link_position', sa.Integer(), nullable=True),  # Order in email
        
        # Tracking
        sa.Column('click_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unique_click_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_clicked_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for email_links
    op.create_index('idx_email_links_email_id', 'email_links', ['email_id'])
    op.create_index('idx_email_links_tracking_url', 'email_links', ['tracking_url'])


def downgrade():
    """Drop email tracking tables."""
    op.drop_table('email_links')
    op.drop_table('email_replies')
    op.drop_table('email_clicks')
    op.drop_table('email_opens')
    op.drop_table('outreach_emails')

