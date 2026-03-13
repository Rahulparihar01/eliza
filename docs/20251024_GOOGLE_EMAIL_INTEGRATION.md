# Google Email Integration Feature

**Date**: October 24, 2025  
**Status**: ✅ Implementation Complete  
**Feature**: Google SSO connector for email composition in candidate outreach

## Overview

Implemented Google email integration that allows users to compose emails directly in Gmail with pre-filled content from the candidate outreach screen. This provides a seamless workflow where clicking "Send Email" opens Gmail compose window with the candidate's email, subject, and body pre-populated.

---

## Features Implemented

### 1. Backend API Endpoints

**File**: `src/api/routes/settings.py`

Added three new endpoints for Google email configuration:

#### GET `/v1/settings/google-email/config`
- Returns current Google OAuth configuration
- Masks client secret for security
- Shows connection status and connected email

#### PUT `/v1/settings/google-email/config`
- Updates Google OAuth credentials (Client ID, Client Secret, Redirect URI)
- Supports partial updates (only provided fields are updated)
- Stores credentials securely in system settings

#### POST `/v1/settings/google-email/disconnect`
- Disconnects the connected Google account
- Removes stored connection information

**Security**:
- All endpoints require `settings:read` or `settings:write` permissions
- Client secrets are masked in responses
- Credentials stored as private settings (not public)

---

### 2. Admin Settings UI

**File**: `frontend/src/pages/admin/AdminSettingsPage.tsx`

Added a new "Google Email Integration" section with:

- **Connection Status Display**
  - Shows if Google account is connected
  - Displays connected email address
  - Shows current Client ID and Redirect URI

- **Configuration Form**
  - Input fields for:
    - Google OAuth Client ID
    - Google OAuth Client Secret (password field, masked)
    - Redirect URI (auto-filled with default)
  - Setup instructions with link to Google Cloud Console
  - Save/Cancel buttons

- **Disconnect Functionality**
  - Button to disconnect Google account
  - Confirmation dialog before disconnecting

**User Experience**:
- Clear visual indicators for connection status
- Helpful setup instructions
- Form validation and error handling
- Success/error toast notifications

---

### 3. Candidate Outreach Integration

**File**: `frontend/src/pages/talent-intelligence/CandidateOutreachPage.tsx`

Updated email sending functionality:

#### Single Email Send (`handleSendEmail`)
- Builds Gmail compose URL with pre-filled:
  - To: Candidate email address
  - Subject: Pre-written email subject
  - Body: Pre-written email body
- Opens Gmail compose window in new tab
- Updates candidate status to "sent"
- Shows success notification

#### Bulk Email Send (`handleSendAllPending`)
- Opens Gmail compose windows for all pending candidates
- Uses staggered delays (200ms) to avoid popup blocker
- Updates all candidates to "sent" status

**Gmail Compose URL Format**:
```
https://mail.google.com/mail/?view=cm&fs=1&to={email}&su={subject}&body={body}
```

**URL Encoding**:
- All parameters are properly URL-encoded using `encodeURIComponent()`
- Handles special characters in email addresses, subjects, and body text

---

## Technical Details

### Data Storage

Google OAuth credentials are stored in the `system_settings` table:

- `google_email_client_id` - OAuth Client ID
- `google_email_client_secret` - OAuth Client Secret (encrypted)
- `google_email_redirect_uri` - OAuth redirect URI
- `google_email_connected_email` - Connected email address (for display)

### Security Considerations

1. **Client Secret Masking**: Secrets are never returned in API responses (shown as `••••••••••••••••`)
2. **Permission-Based Access**: All endpoints require admin permissions
3. **Private Settings**: Credentials stored as non-public settings
4. **URL Encoding**: All user-provided data is properly encoded to prevent injection

### Browser Compatibility

- Gmail compose URLs work in all modern browsers
- Requires user to be logged into Gmail account
- Opens in new tab/window (respects browser popup settings)

---

## Setup Instructions

### For Administrators

1. **Google Cloud Console Setup**:
   - Navigate to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select existing
   - Enable Gmail API:
     - Go to "APIs & Services" → "Library"
     - Search for "Gmail API"
     - Click "Enable"
   - Create OAuth 2.0 credentials:
     - Go to "APIs & Services" → "Credentials"
     - Click "Create Credentials" → "OAuth client ID"
     - Choose "Web application"
     - Add authorized redirect URI: `https://your-domain.com/auth/google/callback`
     - Copy Client ID and Client Secret

2. **Configure in Admin Settings**:
   - Navigate to Admin Settings page
   - Find "Google Email Integration" section
   - Click "Connect Google Account"
   - Enter Client ID, Client Secret, and Redirect URI
   - Click "Save Configuration"

3. **Test**:
   - Go to Candidate Outreach page
   - Select a candidate
   - Click "Send Email"
   - Verify Gmail compose window opens with pre-filled content

---

## Future Enhancements

### Phase 2: Direct Email Sending via Gmail API
- Implement OAuth flow to obtain access tokens
- Use Gmail API `messages.send` to send emails directly
- No need to open browser window
- Track email delivery status

### Phase 3: Email Tracking
- Track email opens (using tracking pixels)
- Track email replies
- Update candidate status automatically
- Analytics dashboard for outreach metrics

### Phase 4: Scheduling
- Schedule emails for specific times
- Timezone-aware scheduling
- Background job processing with Celery
- Email queue management

---

## Files Modified

### Backend
- `src/api/routes/settings.py` - Added Google email configuration endpoints

### Frontend
- `frontend/src/pages/admin/AdminSettingsPage.tsx` - Added Google Email Integration section
- `frontend/src/pages/talent-intelligence/CandidateOutreachPage.tsx` - Updated email sending to use Gmail compose URLs

---

## Testing Checklist

- [ ] Admin can configure Google OAuth credentials
- [ ] Client secret is masked in API responses
- [ ] Configuration can be updated without re-entering secret
- [ ] Google account can be disconnected
- [ ] Single email opens Gmail compose with correct content
- [ ] Bulk email opens multiple Gmail compose windows
- [ ] URL encoding handles special characters correctly
- [ ] Candidate status updates after sending
- [ ] Error handling works for invalid configurations

---

## Notes

- The current implementation uses Gmail compose URLs, which requires users to manually send emails
- This approach doesn't require OAuth token management, making it simpler to implement
- Future phases can add direct API sending for fully automated email delivery
- The Google SSO connector section in Admin Settings prepares for future OAuth flow implementation

