# Global Token Expiration Handling - Application Wide
**Date:** October 19, 2025, 12:21 AM  
**Status:** ✅ Complete

## Summary
Implemented application-wide token expiration handling that automatically redirects users to login when their JWT tokens expire, with clear session expiration messages.

## Problem
- When JWT tokens expired, API calls would fail with 401/403 errors
- Users would see generic errors or stuck loading states
- No automatic redirect to login page
- Poor user experience - users didn't know they needed to log back in

## Solution
Implemented a **centralized authentication interceptor** in the axios client that:
1. Catches 401 (Unauthorized) and 403 (Forbidden) errors globally
2. Attempts to refresh the token if a refresh token exists
3. If refresh fails or token is invalid, clears auth state and redirects to login
4. Displays a clear "Your session has expired" message on the login page

---

## Implementation Details

### 1. Updated Axios Interceptor (`frontend/src/services/api-client.ts`)

**Added 403 Handling:**
```typescript
// Handle 403 (Forbidden) - token invalid or expired
if (status === 403 && error.response?.data?.message?.includes?.('Authentication failed')) {
  // Clear auth and redirect to login
  localStorage.removeItem('auth_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  window.location.href = '/login?message=Your session has expired. Please log in again.';
}
```

**Improved 401 Handling:**
```typescript
// Handle 401 (Unauthorized) - try to refresh token
if (status === 401 && !isRefreshing) {
  isRefreshing = true;
  try {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      // Try to refresh token...
    } else {
      // No refresh token - clear auth and redirect
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      window.location.href = '/login?message=Your session has expired. Please log in again.';
    }
  } catch (refreshError) {
    // Refresh failed - logout and redirect
    window.location.href = '/login?message=Your session has expired. Please log in again.';
  }
}
```

**Key Features:**
- ✅ Catches all API errors in one place
- ✅ Tries token refresh first (if refresh token exists)
- ✅ Falls back to logout + redirect if refresh fails
- ✅ Prevents infinite refresh loops with `isRefreshing` flag
- ✅ Clears all auth-related localStorage items
- ✅ Passes session expiration message via URL query param

---

### 2. Updated Login Page (`frontend/src/pages/auth/LoginPage.tsx`)

**Display Session Expiration Message:**
```typescript
const [searchParams] = useSearchParams();

useEffect(() => {
  const message = searchParams.get('message');
  if (message) {
    setLoginError(message);  // Display in error banner
  }
}, [searchParams]);
```

**User Experience:**
- When redirected to login, user sees: "Your session has expired. Please log in again."
- Message displayed in the same error banner as login errors
- Clear, user-friendly explanation of why they were logged out

---

### 3. Updated SSE Hook (`frontend/src/hooks/useAnalysisStream.ts`)

**Added Navigation on 403:**
```typescript
eventSource.onerror = (err) => {
  // Check if this is an authentication error (403)
  fetch(`${apiUrl}/api/talent/analysis/${analysisId}/stream?token=${token}`, {
    method: 'HEAD'
  }).then(response => {
    if (response.status === 403) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      eventSource.close();
      navigate('/login', { 
        state: { message: 'Your session has expired. Please log in again.' }
      });
    }
  });
};
```

**Note:** This is a fallback for SSE connections since EventSource doesn't provide status codes. The main handling is done by the axios interceptor for regular API calls.

---

## How It Works

### For Regular API Calls (via Axios)
```
1. User makes API request
2. Token expired → API returns 401/403
3. Axios interceptor catches error
4. IF refresh_token exists:
   → Try to refresh token
   → If success: retry original request
   → If fail: logout + redirect
5. IF no refresh_token:
   → Clear localStorage
   → Redirect to /login?message=...
```

### For SSE Connections (EventSource)
```
1. User opens SSE connection
2. Token expired → SSE fails with error
3. useAnalysisStream hook checks status
4. If 403:
   → Clear localStorage
   → Navigate to /login with message
```

---

## Benefits

### 1. Consistent Behavior
- **All API endpoints** use the same token expiration logic
- No need to implement error handling in every component
- DRY principle - single source of truth for auth errors

### 2. Better User Experience
- Clear "session expired" message
- Automatic redirect (no manual action needed)
- User understands why they're back at login
- Can simply log back in and continue

### 3. Security
- Expired tokens are immediately cleared from localStorage
- No lingering invalid tokens
- Clean logout process

### 4. Maintainability
- Centralized logic in `api-client.ts`
- Easy to update behavior for all endpoints
- Clear separation of concerns

---

## Testing

### Test Scenarios
1. **Expired Token on Regular API Call**
   - Navigate to any page that makes API calls
   - Wait for token to expire (or manually invalidate)
   - Make API request
   - ✅ Should auto-redirect to /login with message

2. **Expired Token on SSE Connection**
   - Submit ML Talent analysis
   - Wait for token to expire
   - SSE connection fails
   - ✅ Should redirect to /login with message

3. **Successful Token Refresh**
   - Have valid refresh_token
   - Make API call with expired access token
   - ✅ Should auto-refresh and retry request
   - ✅ User sees no interruption

4. **Failed Token Refresh**
   - Have invalid/expired refresh_token
   - Make API call
   - ✅ Should redirect to /login with message

---

## Files Modified

1. **`frontend/src/services/api-client.ts`**
   - Updated response interceptor
   - Added 403 handling
   - Improved 401 handling with better fallbacks
   - Added session expiration message to redirect URL

2. **`frontend/src/pages/auth/LoginPage.tsx`**
   - Added `useSearchParams` hook
   - Added `useEffect` to read `message` query param
   - Display message in error banner

3. **`frontend/src/hooks/useAnalysisStream.ts`**
   - Added `useNavigate` hook
   - Added 403 detection in `onerror` handler
   - Navigate to login with message on auth failure

---

## Configuration

### Token Expiration Settings
- Default JWT expiration: 8 hours (set in `src/services/auth_service.py`)
- Refresh token: Not currently implemented server-side
- Can be configured via `JWT_EXPIRATION_HOURS` setting

### Frontend Configuration
- No configuration needed - works automatically
- Message can be customized in `api-client.ts`
- Login redirect URL: `/login?message=...`

---

## Future Enhancements

### 1. Implement Refresh Tokens Server-Side
Currently the frontend tries to refresh tokens, but the backend doesn't have a `/v1/auth/refresh` endpoint. Implementing this would allow:
- Longer sessions without re-login
- Seamless token renewal
- Better UX for long-running analyses

### 2. Token Expiration Warning
Show a warning toast 5 minutes before token expires:
- "Your session will expire in 5 minutes"
- "Click here to stay logged in"
- Proactive token refresh on user interaction

### 3. Remember Last Page
Store the current URL before redirecting to login:
- `window.location.href = '/login?message=...&return_to=/current/path'`
- After login, redirect back to where they were
- Better UX for interrupted workflows

### 4. Silent Token Refresh
Refresh tokens proactively in the background:
- Check token expiration on app focus
- Auto-refresh before expiration
- No user interruption

---

## Related Issues Fixed

This implementation solves:
- ✅ SSE connection failing with 403 (Forbidden)
- ✅ "Invalid token" errors not handling properly
- ✅ Users stuck on loading screens when token expires
- ✅ No feedback about why login is required
- ✅ Inconsistent auth error handling across pages

---

## Testing Commands

### Check Token Expiration
```javascript
// In browser console:
const token = localStorage.getItem('auth_token');
const payload = JSON.parse(atob(token.split('.')[1]));
const exp = new Date(payload.exp * 1000);
console.log('Token expires:', exp);
console.log('Time until expiration:', exp - new Date(), 'ms');
```

### Manually Expire Token
```javascript
// In browser console:
localStorage.setItem('auth_token', 'invalid_token');
// Then try to make an API call - should redirect to login
```

### Test Session Message
```
1. Navigate to: http://localhost:3000/login?message=Test session expired
2. Should see "Test session expired" in error banner
```

---

## Related Documentation
- `20251019_001600_SSE_FIX_COMPLETE.md` - SSE streaming implementation
- `20251018_223400_SSE_EVENT_TRACKING.md` - SSE event tracking for ML Talent workflow
- `frontend/src/contexts/AuthContext.tsx` - Main authentication context


