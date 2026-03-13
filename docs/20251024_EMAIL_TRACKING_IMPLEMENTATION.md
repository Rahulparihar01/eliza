# Email Tracking System - Implementation Summary

## Overview

Complete email tracking and analytics system for candidate outreach emails. Tracks opens, clicks, and replies with comprehensive metrics and export functionality.

## Components Implemented

### 1. Database Schema (`alembic/versions/h8i9j0k1l2m3_add_email_tracking_tables.py`)
- **outreach_emails**: Main table storing email records
- **email_opens**: Tracks each email open event
- **email_clicks**: Tracks each link click event
- **email_replies**: Tracks replies to sent emails
- **email_links**: Stores all links in emails for click tracking

### 2. SQLAlchemy Models (`src/models/email_tracking.py`)
- `OutreachEmail`: Main email model
- `EmailOpen`: Open tracking model
- `EmailClick`: Click tracking model
- `EmailReply`: Reply tracking model
- `EmailLink`: Link tracking model

### 3. Service Layer (`src/services/email_tracking_service.py`)
- `EmailTrackingService`: Core service for tracking operations
  - `create_outreach_email()`: Create email record
  - `record_email_open()`: Record open events
  - `record_email_click()`: Record click events
  - `inject_tracking_pixel()`: Inject 1x1 tracking pixel
  - `inject_tracking_links()`: Replace links with tracking URLs
  - `parse_user_agent()`: Device and email client detection
  - `get_ip_location()`: IP geolocation (placeholder for future)

### 4. API Endpoints (`src/api/routes/outreach.py`)

#### Public Endpoints (No Auth Required)
- `GET /api/v1/outreach/track/open/{email_id}`: Tracking pixel endpoint
- `GET /api/v1/outreach/track/click/{email_id}/{link_position}`: Click redirect endpoint

#### Authenticated Endpoints
- `POST /api/v1/outreach/emails`: Create email record with tracking injection
- `GET /api/v1/outreach/metrics`: Get metrics summary
- `GET /api/v1/outreach/emails`: List emails with pagination
- `GET /api/v1/outreach/emails/{email_id}`: Get email details
- `GET /api/v1/outreach/metrics/export`: Export metrics to CSV

### 5. Frontend Dashboard (`frontend/src/pages/talent-intelligence/CandidateOutreachMetricsPage.tsx`)
- Metrics summary cards (open rate, click rate, reply rate)
- Email list with engagement data
- Date range filtering
- CSV export functionality
- Pagination support

### 6. Tests (`tests/test_email_tracking.py`)
Comprehensive test suite covering:
- Email creation
- Tracking pixel injection
- Link tracking injection
- Open tracking
- Click tracking
- User agent parsing
- Complete end-to-end flow

## How It Works

### 1. Recording an Email
When an email is sent, call the API endpoint:
```python
POST /api/v1/outreach/emails
{
  "candidate_id": "candidate_123",
  "candidate_name": "John Doe",
  "candidate_email": "john.doe@example.com",
  "subject": "Exciting Opportunity",
  "body_html": "<html>...</html>",
  "body_text": "Plain text version"
}
```

The system automatically:
- Generates a unique `email_id` for tracking
- Injects a 1x1 transparent tracking pixel
- Replaces all links with tracking URLs
- Stores link metadata for click tracking

### 2. Tracking Opens
When the email is opened, the tracking pixel loads:
```
GET /api/v1/outreach/track/open/{email_id}
```
This endpoint:
- Records the open event
- Captures IP address, user agent, device type
- Updates email metrics (open_count, first_opened_at, last_opened_at)
- Returns a 1x1 transparent PNG

### 3. Tracking Clicks
When a link is clicked, the tracking URL redirects:
```
GET /api/v1/outreach/track/click/{email_id}/{link_position}?url={original_url}
```
This endpoint:
- Records the click event
- Captures device and location info
- Updates email and link metrics
- Redirects to the original URL

### 4. Viewing Metrics
Access the dashboard at `/talent/outreach/metrics` to see:
- Overall metrics (open rate, click rate, reply rate)
- List of all sent emails with engagement data
- Detailed view for individual emails
- Export to CSV for analysis

## Running Tests

### Run All Tests
```bash
pytest tests/test_email_tracking.py -v
```

### Run Specific Test
```bash
pytest tests/test_email_tracking.py::test_complete_email_tracking_flow -v
```

### Run Test Directly
```bash
python tests/test_email_tracking.py
```

## Database Migration

To apply the database migration:
```bash
# Run migration
alembic upgrade head

# Verify tables created
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "\dt outreach*"
```

## API Usage Examples

### Create Email Record
```bash
curl -X POST http://localhost:8000/api/v1/outreach/emails \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_id": "candidate_123",
    "candidate_name": "John Doe",
    "candidate_email": "john.doe@example.com",
    "subject": "Exciting Opportunity",
    "body_html": "<html><body><p>Hello!</p><a href=\"https://example.com\">Learn More</a></body></html>"
  }'
```

### Get Metrics Summary
```bash
curl -X GET "http://localhost:8000/api/v1/outreach/metrics" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Export Metrics CSV
```bash
curl -X GET "http://localhost:8000/api/v1/outreach/metrics/export" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o outreach_metrics.csv
```

## Frontend Integration

The metrics dashboard is available at:
- **Route**: `/talent/outreach/metrics`
- **Navigation**: Added to Talent Intelligence section as "Outreach Metrics"

## Next Steps (Future Enhancements)

1. **Gmail API Integration**: Direct email sending via Gmail API (no browser window)
2. **Reply Detection**: Gmail API polling/webhooks for automatic reply detection
3. **Advanced Analytics**: 
   - Sentiment analysis on replies
   - A/B testing capabilities
   - Time-series analysis
4. **Notifications**: Real-time notifications for replies
5. **Scheduled Sending**: Schedule emails for future delivery
6. **IP Geolocation**: Integrate MaxMind GeoIP2 for location tracking

## Notes

- Tracking pixels and links are automatically injected when emails are created via the API
- All tracking endpoints are public (no auth required) to work with email clients
- Metrics endpoints require authentication
- The system tracks both total and unique opens/clicks
- Device type and email client are detected from user agent strings
- CSV export includes all email data with engagement metrics

