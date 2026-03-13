# Candidate Outreach Metrics - Implementation Plan

**Date**: October 24, 2025  
**Status**: 📋 Planning Phase  
**Feature**: Email tracking and analytics dashboard for candidate outreach

---

## Overview

Build a comprehensive email tracking and analytics system that tracks all emails sent from the candidate outreach feature. This will provide hiring managers with insights into email performance, engagement rates, and candidate response patterns.

---

## Email Tracking Best Practices

### 1. **Tracking Methods**

#### Open Tracking
- **Method**: 1x1 pixel transparent image (tracking pixel)
- **Implementation**: 
  - Generate unique tracking pixel URL per email
  - Embed in email HTML: `<img src="https://api.example.com/track/open/{email_id}" width="1" height="1" />`
  - When image loads, record open event with timestamp
- **Privacy**: Respect email client privacy settings (some block images by default)
- **Accuracy**: ~70-80% accurate (some clients block, some pre-load)

#### Click Tracking
- **Method**: URL redirection through tracking service
- **Implementation**:
  - Replace all links in email with tracking URLs
  - Format: `https://api.example.com/track/click/{email_id}/{link_id}?url={encoded_destination}`
  - When clicked, record click event, then redirect to actual URL
- **Privacy**: Transparent to user (instant redirect)
- **Accuracy**: ~95% accurate

#### Delivery Tracking
- **Method**: Gmail API message status
- **Implementation**:
  - When sending via Gmail API, check message status
  - Track delivery confirmations
  - Detect bounces and failures
- **Accuracy**: ~99% accurate (from Gmail API)

#### Reply Tracking
- **Method**: Gmail API inbox monitoring
- **Implementation**:
  - Monitor inbox for replies to sent emails
  - Match by thread ID or subject line
  - Record reply timestamp and content
- **Accuracy**: ~95% accurate (requires Gmail API access)

### 2. **Privacy & Compliance**

- **GDPR Compliance**: 
  - Only track emails sent with consent
  - Provide opt-out mechanism
  - Store minimal data necessary
  - Allow data deletion requests

- **Email Client Privacy**:
  - Some clients block tracking pixels (Apple Mail, Outlook)
  - Some pre-load images (Gmail)
  - Respect user privacy settings

- **Transparency**:
  - Disclose tracking in email footer
  - Provide privacy policy link
  - Allow opt-out

---

## Database Schema Design

### 1. `outreach_emails` Table

Stores each email sent to a candidate.

```sql
CREATE TABLE outreach_emails (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(100) UNIQUE NOT NULL,  -- UUID for tracking URLs
    customer_id VARCHAR(255) NOT NULL,
    user_id INTEGER REFERENCES users(id),  -- Who sent it
    talent_analysis_id VARCHAR(100) REFERENCES talent_analyses(analysis_id),
    candidate_id VARCHAR(255) NOT NULL,  -- Reference to candidate
    candidate_name VARCHAR(255),
    candidate_email VARCHAR(255) NOT NULL,
    
    -- Email content
    subject TEXT NOT NULL,
    body_html TEXT,  -- HTML version with tracking pixels/links
    body_text TEXT,  -- Plain text version
    email_template_id INTEGER,  -- If using template
    
    -- Sending metadata
    sent_via VARCHAR(50) DEFAULT 'gmail_compose',  -- 'gmail_compose', 'gmail_api', 'smtp'
    gmail_message_id VARCHAR(255),  -- Gmail API message ID if sent via API
    gmail_thread_id VARCHAR(255),  -- Gmail thread ID for reply tracking
    
    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, sent, delivered, bounced, failed
    delivery_status VARCHAR(50),  -- delivered, bounced, deferred, failed
    delivery_error TEXT,  -- Error message if delivery failed
    
    -- Timing
    scheduled_for TIMESTAMPTZ,  -- If scheduled
    sent_at TIMESTAMPTZ,  -- When actually sent
    delivered_at TIMESTAMPTZ,  -- When delivered
    first_opened_at TIMESTAMPTZ,  -- First open timestamp
    last_opened_at TIMESTAMPTZ,  -- Last open timestamp
    
    -- Engagement metrics (denormalized for quick queries)
    open_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    is_replied BOOLEAN DEFAULT FALSE,
    last_reply_at TIMESTAMPTZ,
    
    -- Metadata
    metadata JSONB,  -- Additional data (device, location, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_outreach_emails_customer ON outreach_emails(customer_id);
CREATE INDEX idx_outreach_emails_analysis ON outreach_emails(talent_analysis_id);
CREATE INDEX idx_outreach_emails_status ON outreach_emails(status);
CREATE INDEX idx_outreach_emails_sent_at ON outreach_emails(sent_at);
CREATE INDEX idx_outreach_emails_email_id ON outreach_emails(email_id);
```

### 2. `email_opens` Table

Tracks each email open event.

```sql
CREATE TABLE email_opens (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(100) NOT NULL REFERENCES outreach_emails(email_id),
    
    -- Open metadata
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    ip_address VARCHAR(45),  -- IPv4 or IPv6
    user_agent TEXT,
    device_type VARCHAR(50),  -- mobile, desktop, tablet
    email_client VARCHAR(100),  -- gmail, outlook, apple_mail, etc.
    location_country VARCHAR(100),
    location_city VARCHAR(100),
    
    -- Tracking metadata
    is_unique BOOLEAN DEFAULT TRUE,  -- First open for this email
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_email_opens_email_id ON email_opens(email_id);
CREATE INDEX idx_email_opens_opened_at ON email_opens(opened_at);
CREATE INDEX idx_email_opens_unique ON email_opens(email_id, is_unique) WHERE is_unique = TRUE;
```

### 3. `email_clicks` Table

Tracks each link click in emails.

```sql
CREATE TABLE email_clicks (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(100) NOT NULL REFERENCES outreach_emails(email_id),
    
    -- Click metadata
    clicked_at TIMESTAMPTZ DEFAULT NOW(),
    link_url TEXT NOT NULL,  -- Original destination URL
    link_text TEXT,  -- Link text/anchor
    link_position INTEGER,  -- Position in email (1st link, 2nd link, etc.)
    
    -- User metadata
    ip_address VARCHAR(45),
    user_agent TEXT,
    device_type VARCHAR(50),
    location_country VARCHAR(100),
    location_city VARCHAR(100),
    
    -- Tracking metadata
    is_unique BOOLEAN DEFAULT TRUE,  -- First click for this link
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_email_clicks_email_id ON email_clicks(email_id);
CREATE INDEX idx_email_clicks_clicked_at ON email_clicks(clicked_at);
CREATE INDEX idx_email_clicks_unique ON email_clicks(email_id, link_url, is_unique) WHERE is_unique = TRUE;
```

### 4. `email_replies` Table

Tracks replies to sent emails.

```sql
CREATE TABLE email_replies (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(100) NOT NULL REFERENCES outreach_emails(email_id),
    
    -- Reply metadata
    replied_at TIMESTAMPTZ NOT NULL,
    gmail_message_id VARCHAR(255),  -- Gmail API message ID
    gmail_thread_id VARCHAR(255),  -- Gmail thread ID
    subject TEXT,
    body_preview TEXT,  -- First 500 chars
    body_full TEXT,  -- Full reply content
    
    -- Reply analysis
    sentiment VARCHAR(50),  -- positive, neutral, negative (from NLP)
    is_interested BOOLEAN,  -- Detected interest signals
    next_action_suggested TEXT,  -- AI-suggested next action
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_email_replies_email_id ON email_replies(email_id);
CREATE INDEX idx_email_replies_replied_at ON email_replies(replied_at);
```

### 5. `email_links` Table

Stores all links in emails for click tracking.

```sql
CREATE TABLE email_links (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(100) NOT NULL REFERENCES outreach_emails(email_id),
    
    -- Link details
    original_url TEXT NOT NULL,
    tracking_url TEXT NOT NULL,  -- Our tracking URL
    link_text TEXT,
    link_position INTEGER,  -- Order in email
    
    -- Tracking
    click_count INTEGER DEFAULT 0,
    unique_click_count INTEGER DEFAULT 0,
    first_clicked_at TIMESTAMPTZ,
    last_clicked_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_email_links_email_id ON email_links(email_id);
CREATE INDEX idx_email_links_tracking_url ON email_links(tracking_url);
```

---

## API Endpoints Design

### 1. Email Tracking Endpoints (Public - No Auth Required)

These endpoints are called by email clients and tracking pixels.

#### `GET /api/v1/outreach/track/open/{email_id}`
- **Purpose**: Tracking pixel endpoint
- **Auth**: None (public endpoint)
- **Response**: 1x1 transparent PNG image
- **Behavior**:
  - Record open event in `email_opens` table
  - Update `outreach_emails.open_count` and `first_opened_at`
  - Return transparent 1x1 PNG
- **Privacy**: Log IP, user agent, but don't store PII

#### `GET /api/v1/outreach/track/click/{email_id}/{link_id}`
- **Purpose**: Click tracking redirect
- **Auth**: None (public endpoint)
- **Query Params**: `url` (encoded destination URL)
- **Response**: HTTP 302 redirect to actual URL
- **Behavior**:
  - Record click event in `email_clicks` table
  - Update `email_links.click_count`
  - Update `outreach_emails.click_count`
  - Redirect to destination URL
- **Privacy**: Log minimal data, instant redirect

### 2. Metrics & Analytics Endpoints (Authenticated)

#### `GET /api/v1/outreach/metrics`
- **Purpose**: Get aggregated metrics
- **Auth**: Required (user must be authenticated)
- **Query Params**:
  - `talent_analysis_id` (optional): Filter by analysis
  - `date_from` (optional): Start date
  - `date_to` (optional): End date
  - `group_by` (optional): day, week, month
- **Response**:
```json
{
  "summary": {
    "total_sent": 150,
    "total_delivered": 148,
    "total_opened": 95,
    "total_clicked": 42,
    "total_replied": 18,
    "delivery_rate": 0.987,
    "open_rate": 0.642,
    "click_rate": 0.284,
    "reply_rate": 0.122
  },
  "over_time": [
    {
      "date": "2025-10-24",
      "sent": 10,
      "opened": 7,
      "clicked": 3,
      "replied": 1
    }
  ],
  "by_analysis": [
    {
      "analysis_id": "abc123",
      "analysis_name": "ML Engineer Q4 2025",
      "sent": 25,
      "open_rate": 0.68,
      "reply_rate": 0.16
    }
  ]
}
```

#### `GET /api/v1/outreach/emails`
- **Purpose**: List all sent emails with status
- **Auth**: Required
- **Query Params**:
  - `talent_analysis_id` (optional)
  - `status` (optional): sent, delivered, bounced
  - `has_reply` (optional): true/false
  - `page` (optional): Pagination
  - `limit` (optional): Results per page
- **Response**:
```json
{
  "emails": [
    {
      "id": "email-uuid-123",
      "candidate_name": "John Doe",
      "candidate_email": "john@example.com",
      "subject": "ML Engineer Opportunity",
      "sent_at": "2025-10-24T10:00:00Z",
      "status": "delivered",
      "open_count": 3,
      "click_count": 1,
      "is_replied": true,
      "first_opened_at": "2025-10-24T14:30:00Z",
      "last_reply_at": "2025-10-25T09:15:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 150,
    "total_pages": 3
  }
}
```

#### `GET /api/v1/outreach/emails/{email_id}`
- **Purpose**: Get detailed metrics for specific email
- **Auth**: Required
- **Response**:
```json
{
  "email": {
    "id": "email-uuid-123",
    "candidate_name": "John Doe",
    "candidate_email": "john@example.com",
    "subject": "ML Engineer Opportunity",
    "body_preview": "Hi John,...",
    "sent_at": "2025-10-24T10:00:00Z",
    "delivered_at": "2025-10-24T10:00:05Z",
    "status": "delivered",
    "metrics": {
      "open_count": 3,
      "unique_opens": 2,
      "click_count": 1,
      "unique_clicks": 1,
      "is_replied": true,
      "reply_count": 1
    },
    "opens": [
      {
        "opened_at": "2025-10-24T14:30:00Z",
        "device_type": "mobile",
        "email_client": "gmail",
        "location_city": "San Francisco"
      }
    ],
    "clicks": [
      {
        "clicked_at": "2025-10-24T15:00:00Z",
        "link_url": "https://company.com/careers",
        "device_type": "desktop"
      }
    ],
    "replies": [
      {
        "replied_at": "2025-10-25T09:15:00Z",
        "body_preview": "Hi, thanks for reaching out...",
        "sentiment": "positive",
        "is_interested": true
      }
    ]
  }
}
```

#### `POST /api/v1/outreach/emails`
- **Purpose**: Record email sent (called when email is sent)
- **Auth**: Required
- **Request Body**:
```json
{
  "talent_analysis_id": "abc123",
  "candidate_id": "cand-001",
  "candidate_name": "John Doe",
  "candidate_email": "john@example.com",
  "subject": "ML Engineer Opportunity",
  "body_html": "<html>...</html>",
  "body_text": "Plain text version",
  "sent_via": "gmail_compose",
  "gmail_message_id": "msg-123",
  "gmail_thread_id": "thread-456",
  "scheduled_for": null
}
```
- **Response**: Created email record with `email_id` for tracking

#### `PUT /api/v1/outreach/emails/{email_id}/status`
- **Purpose**: Update email delivery status (called by Gmail API webhook or polling)
- **Auth**: Required (or webhook secret)
- **Request Body**:
```json
{
  "status": "delivered",
  "delivery_status": "delivered",
  "delivered_at": "2025-10-24T10:00:05Z"
}
```

---

## Frontend Page Design

### Page: "Candidate Outreach Metrics"

**Route**: `/talent/outreach/metrics`

### Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Candidate Outreach Metrics                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Summary Cards (4 cards)                             │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐               │  │
│  │  │ Sent │ │ Open │ │Click │ │Reply │               │  │
│  │  │ 150  │ │ 95   │ │ 42   │ │ 18   │               │  │
│  │  └──────┘ └──────┘ └──────┘ └──────┘               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Filters                                             │  │
│  │  [Analysis ▼] [Date Range] [Status ▼] [Apply]      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Performance Over Time (Chart)                       │  │
│  │  ┌──────────────────────────────────────────────┐   │  │
│  │  │     Line chart: Sent, Opened, Clicked, Replied│   │  │
│  │  └──────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Email Performance Table                             │  │
│  │  ┌──────┬──────────┬────────┬──────┬──────┬──────┐  │  │
│  │  │Name  │Subject   │Sent    │Open  │Click │Reply │  │  │
│  │  ├──────┼──────────┼────────┼──────┼──────┼──────┤  │  │
│  │  │John  │ML Eng... │Oct 24  │3     │1     │✓     │  │  │
│  │  │Jane  │ML Eng... │Oct 24  │1     │0     │      │  │  │
│  │  └──────┴──────────┴────────┴──────┴──────┴──────┘  │  │
│  │  [View Details] [Export]                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Analysis Breakdown                                   │  │
│  │  ┌──────────────┬──────┬──────┬──────┬──────┐       │  │
│  │  │Analysis      │Sent  │Open% │Click%│Reply%│       │  │
│  │  ├──────────────┼──────┼──────┼──────┼──────┤       │  │
│  │  │ML Eng Q4 2025│25    │68%   │28%   │16%   │       │  │
│  │  └──────────────┴──────┴──────┴──────┴──────┘       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Components Needed

1. **SummaryCards** - 4 metric cards (Sent, Opened, Clicked, Replied)
2. **MetricsFilters** - Date range, analysis filter, status filter
3. **PerformanceChart** - Line/bar chart showing metrics over time
4. **EmailPerformanceTable** - Table listing all emails with metrics
5. **EmailDetailModal** - Modal showing detailed metrics for single email
6. **AnalysisBreakdown** - Table showing metrics grouped by analysis

### Key Metrics to Display

1. **Overall Metrics**:
   - Total Sent
   - Total Delivered
   - Total Opened (with unique opens)
   - Total Clicked (with unique clicks)
   - Total Replied
   - Delivery Rate (%)
   - Open Rate (%)
   - Click Rate (%)
   - Reply Rate (%)

2. **Time-Based Metrics**:
   - Metrics over time (daily/weekly/monthly)
   - Trends (increasing/decreasing)

3. **Per-Email Metrics**:
   - Open count and timestamps
   - Click count and which links
   - Reply status and content
   - Device/email client breakdown

4. **Analysis-Level Metrics**:
   - Performance by talent analysis
   - Which analyses have best engagement

---

## Implementation Phases

### Phase 1: Database & Backend Foundation (Week 1)

1. **Database Migration**
   - Create `outreach_emails` table
   - Create `email_opens` table
   - Create `email_clicks` table
   - Create `email_replies` table
   - Create `email_links` table
   - Add indexes for performance

2. **Backend Models**
   - Create SQLAlchemy models for all tables
   - Add relationships and indexes
   - Add Pydantic schemas for API

3. **Tracking Endpoints**
   - Implement `GET /track/open/{email_id}` (tracking pixel)
   - Implement `GET /track/click/{email_id}/{link_id}` (click redirect)
   - Add IP geolocation service (optional)
   - Add user agent parsing

4. **Email Recording**
   - Update `handleSendEmail` to call API when email sent
   - Generate tracking URLs for emails
   - Inject tracking pixels and link replacements

### Phase 2: Metrics API (Week 1-2)

1. **Metrics Endpoints**
   - Implement `GET /api/v1/outreach/metrics` (aggregated)
   - Implement `GET /api/v1/outreach/emails` (list)
   - Implement `GET /api/v1/outreach/emails/{id}` (detail)
   - Implement `POST /api/v1/outreach/emails` (record sent)
   - Add filtering, pagination, sorting

2. **Analytics Service**
   - Create `EmailAnalyticsService` class
   - Implement aggregation queries
   - Add caching for performance
   - Add time-based grouping

### Phase 3: Frontend Dashboard (Week 2)

1. **Page Setup**
   - Create `CandidateOutreachMetricsPage.tsx`
   - Add route in `App.tsx`
   - Add navigation link

2. **Components**
   - Build SummaryCards component
   - Build MetricsFilters component
   - Build PerformanceChart component (using Chart.js or Recharts)
   - Build EmailPerformanceTable component
   - Build EmailDetailModal component

3. **Data Integration**
   - Connect to metrics API
   - Add real-time updates (optional)
   - Add export functionality

### Phase 4: Email Enhancement (Week 2-3)

1. **Email Content Processing**
   - Inject tracking pixels into HTML emails
   - Replace links with tracking URLs
   - Generate unique email IDs

2. **Gmail API Integration**
   - Update email sending to use Gmail API
   - Store Gmail message IDs
   - Poll for delivery status
   - Monitor for replies

3. **Reply Detection**
   - Implement Gmail API reply monitoring
   - Parse reply content
   - Detect sentiment (optional NLP)
   - Update email status

### Phase 5: Advanced Features (Week 3-4)

1. **Analytics Enhancements**
   - Add device/email client breakdown
   - Add location-based analytics
   - Add time-to-open/click/reply metrics
   - Add A/B testing support (if multiple templates)

2. **Notifications**
   - Email alerts for replies
   - Dashboard notifications
   - Weekly summary emails

3. **Export & Reporting**
   - CSV export
   - PDF reports
   - Scheduled reports

---

## Technical Considerations

### 1. **Tracking Pixel Implementation**

```python
# Backend endpoint
@router.get("/track/open/{email_id}")
async def track_email_open(email_id: str, request: Request):
    # Record open event
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent")
    
    # Parse user agent for device/email client
    device_type = parse_user_agent(user_agent)
    email_client = detect_email_client(user_agent)
    
    # Record in database
    record_email_open(email_id, ip_address, user_agent, device_type, email_client)
    
    # Return 1x1 transparent PNG
    return Response(content=TRANSPARENT_PNG, media_type="image/png")
```

### 2. **Link Replacement**

```python
# When sending email, replace links:
def inject_tracking_links(email_body_html: str, email_id: str) -> str:
    # Find all links
    links = extract_links(email_body_html)
    
    # Replace with tracking URLs
    for link in links:
        tracking_url = f"https://api.example.com/track/click/{email_id}/{link.id}?url={encode(link.url)}"
        email_body_html = email_body_html.replace(link.url, tracking_url)
    
    return email_body_html
```

### 3. **Gmail API Integration**

```python
# When sending via Gmail API:
def send_email_via_gmail(email_data):
    # Send email
    message = gmail_service.users().messages().send(
        userId='me',
        body=message_body
    ).execute()
    
    # Store Gmail IDs
    gmail_message_id = message['id']
    gmail_thread_id = message['threadId']
    
    # Record in database
    record_email_sent(email_data, gmail_message_id, gmail_thread_id)
```

### 4. **Reply Monitoring**

```python
# Poll Gmail API for replies
def check_for_replies():
    # Get all sent emails with Gmail thread IDs
    sent_emails = get_sent_emails_with_threads()
    
    for email in sent_emails:
        # Check thread for new messages
        thread = gmail_service.users().threads().get(
            userId='me',
            id=email.gmail_thread_id
        ).execute()
        
        # Check if new reply
        if has_new_reply(thread, email.last_checked_at):
            # Record reply
            record_email_reply(email.email_id, thread)
```

---

## Privacy & Compliance

### Email Footer

Add to all emails:
```
---
This email was sent via [Company Name] candidate outreach system.
Email tracking is used to improve our communication. 
Privacy Policy: [link] | Unsubscribe: [link]
```

### Data Retention

- Store email data for 2 years (configurable)
- Allow data deletion requests
- Anonymize IP addresses after 90 days
- Comply with GDPR/CCPA requirements

---

## Product Decisions ✅

### Tracking Scope
- ✅ **Track all emails automatically** - No opt-in required
- ✅ **No explicit consent needed** - Tracking is automatic for all emails

### Reply Detection
- ✅ **Use Gmail API polling initially** - Check hourly for replies
- 📝 **Future Enhancement**: Gmail Push Notifications via Pub/Sub (requires Google Cloud setup)
  - Gmail API supports push notifications via Google Cloud Pub/Sub
  - Requires: Google Cloud project, Pub/Sub topic, webhook endpoint
  - More efficient than polling, but requires additional infrastructure
  - Will implement polling first, add push notifications in Phase 5

### Analytics Depth
- ✅ **No sentiment analysis** - Keep it simple for now
- ✅ **Standard device/location tracking** - Basic IP geolocation, user agent parsing
- ✅ **No A/B testing** - Not needed initially

### Notifications
- ✅ **No notifications for now** - Focus on tracking and dashboard
- 📝 **Future**: Can add real-time notifications, weekly summaries, dashboard alerts later

### Export
- ✅ **CSV export** - For data analysis
- ✅ **Excel export** - For reporting
- 📝 **Future**: Scheduled reports can be added later

### Suggestions

1. **Start Simple**: Begin with basic open/click tracking, add reply tracking later
2. **Privacy First**: Make tracking transparent, provide opt-out
3. **Performance**: Cache aggregated metrics, use background jobs for heavy queries
4. **Scalability**: Consider using Redis for tracking events, batch writes to DB
5. **User Experience**: Show metrics in real-time, make dashboard interactive

---

## Next Steps

1. **Review & Approve Plan**: Get stakeholder approval
2. **Create Database Migration**: Start with Phase 1
3. **Build Tracking Endpoints**: Implement pixel and click tracking
4. **Update Email Sending**: Inject tracking into emails
5. **Build Metrics API**: Create aggregation endpoints
6. **Build Frontend Dashboard**: Create metrics page
7. **Test End-to-End**: Verify tracking works correctly
8. **Deploy & Monitor**: Launch and monitor performance

---

## Success Metrics

- **Tracking Accuracy**: >90% of opens/clicks tracked
- **API Performance**: <200ms response time for metrics endpoints
- **User Adoption**: >80% of users view metrics dashboard
- **Data Quality**: <1% duplicate tracking events

---

## Estimated Timeline

- **Phase 1**: 3-5 days (Database + Tracking endpoints)
- **Phase 2**: 3-5 days (Metrics API)
- **Phase 3**: 5-7 days (Frontend Dashboard)
- **Phase 4**: 5-7 days (Gmail API Integration)
- **Phase 5**: 5-7 days (Advanced Features)

**Total**: ~4-5 weeks for full implementation

---

## Dependencies

- Gmail API access (for delivery/reply tracking)
- IP Geolocation service (optional, for location tracking)
- Charting library (Chart.js, Recharts, or similar)
- Background job system (Celery) for reply monitoring
- Redis (optional, for caching and event queuing)

