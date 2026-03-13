# Authentication API

**Base Path:** `/auth`

## Overview

The authentication system provides:
- JWT-based authentication with access and refresh tokens
- Session management with device fingerprinting
- Role-Based Access Control (RBAC)
- User profile management
- Multi-factor authentication support (future)

## Authentication Flow

```
1. User logs in → Receives access token + refresh token
2. Use access token for API requests
3. When access token expires → Use refresh token to get new tokens
4. When refresh token expires → User must login again
```

## Endpoints

### POST /auth/login

Authenticate user and create session.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password",
  "remember_me": false
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "jsmith",
    "full_name": "John Smith",
    "is_active": true,
    "is_superuser": false,
    "roles": ["analyst", "user"],
    "permissions": ["bi:read", "bi:write", "documents:read"],
    "primary_role": "analyst",
    "last_login_at": "2024-01-15T10:30:00Z",
    "created_at": "2023-06-01T09:00:00Z"
  }
}
```

**Errors:**
- `401` - Invalid credentials
- `400` - Invalid request format

---

### POST /auth/refresh

Refresh access token using refresh token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "new_access_token...",
  "refresh_token": "new_refresh_token...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {...}
}
```

**Errors:**
- `401` - Invalid or expired refresh token

---

### POST /auth/logout

Logout user and invalidate session.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "message": "Successfully logged out"
}
```

---

### GET /auth/me

Get current user profile.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "jsmith",
  "full_name": "John Smith",
  "is_active": true,
  "is_superuser": false,
  "roles": ["analyst", "user"],
  "permissions": ["bi:read", "bi:write", "documents:read"],
  "primary_role": "analyst",
  "last_login_at": "2024-01-15T10:30:00Z",
  "created_at": "2023-06-01T09:00:00Z"
}
```

**Errors:**
- `401` - Unauthorized (invalid token)

---

### POST /auth/check-permissions

Check if current user has specific permissions.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "permissions": ["bi:write", "documents:read"],
  "require_all": true
}
```

**Parameters:**
- `permissions` (array, required) - List of permissions to check
- `require_all` (boolean, default: false) - If true, user must have ALL permissions; if false, user needs ANY one permission

**Response:** `200 OK`
```json
{
  "has_permission": true,
  "missing_permissions": []
}
```

Or if permissions are missing:
```json
{
  "has_permission": false,
  "missing_permissions": ["documents:write"]
}
```

---

### POST /auth/users

Create new user account.

**Requires Permission:** `users:create`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "secure_password",
  "first_name": "Jane",
  "last_name": "Doe",
  "roles": ["analyst"]
}
```

**Response:** `200 OK`
```json
{
  "id": 2,
  "email": "newuser@example.com",
  "username": "jdoe",
  "full_name": "Jane Doe",
  "is_active": true,
  "is_superuser": false,
  "roles": ["analyst"],
  "permissions": ["bi:read", "documents:read"],
  "primary_role": "analyst",
  "created_at": "2024-01-15T11:00:00Z"
}
```

**Errors:**
- `400` - Invalid request or email already exists
- `403` - Insufficient permissions

---

### PUT /auth/me/password

Change current user's password.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "current_password": "old_password",
  "new_password": "new_secure_password"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password changed successfully"
}
```

**Errors:**
- `400` - Current password is incorrect
- `401` - Unauthorized

---

### GET /auth/sessions

Get all active sessions for the current user.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "sessions": [
    {
      "session_token": "abc12345...",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "device_fingerprint": "def67890...",
      "created_at": "2024-01-15T09:00:00Z",
      "last_activity_at": "2024-01-15T11:30:00Z",
      "expires_at": "2024-01-16T09:00:00Z",
      "is_current": true
    },
    {
      "session_token": "xyz98765...",
      "ip_address": "10.0.0.5",
      "user_agent": "curl/7.68.0",
      "device_fingerprint": "ghi54321...",
      "created_at": "2024-01-14T14:00:00Z",
      "last_activity_at": "2024-01-15T10:00:00Z",
      "expires_at": "2024-01-15T14:00:00Z",
      "is_current": false
    }
  ],
  "total_count": 2
}
```

---

### DELETE /auth/sessions/{session_token}

Terminate a specific session.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Parameters:**
- `session_token` (string, required) - Session token to terminate

**Response:** `200 OK`
```json
{
  "message": "Session terminated successfully"
}
```

**Errors:**
- `404` - Session not found

---

### DELETE /auth/sessions

Terminate all sessions except the current one.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `except_current` (boolean, default: true) - If true, keeps current session active

**Response:** `200 OK`
```json
{
  "message": "Terminated 3 sessions",
  "terminated_count": 3
}
```

---

### GET /auth/health

Health check for authentication service.

**No authentication required**

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "service": "authentication",
  "timestamp": "2024-01-15T12:00:00Z",
  "features": {
    "jwt_auth": true,
    "session_management": true,
    "rbac": true,
    "audit_logging": true,
    "concurrent_session_limits": true,
    "device_fingerprinting": true
  }
}
```

---

## Token Lifetimes

- **Access Token:** 8 hours (28,800 seconds)
- **Refresh Token:** 30 days
- **Session Token:** Tied to refresh token expiry

## Session Management

### Device Fingerprinting

The system creates a device fingerprint from:
- IP address
- User-Agent header
- Accept-Language header
- Accept-Encoding header
- Accept header

This helps detect suspicious login activity.

### Concurrent Sessions

Users can have multiple active sessions (e.g., browser, mobile app, API client). Each session is tracked independently.

## Permission System

### Standard Roles

| Role | Description | Default Permissions |
|------|-------------|---------------------|
| `user` | Basic user | `bi:read`, `documents:read` |
| `analyst` | Business analyst | `bi:read`, `bi:write`, `documents:read`, `documents:write` |
| `talent_manager` | Talent team member | `talent:read`, `talent:write`, `documents:read` |
| `admin` | Administrator | All permissions |

### Available Permissions

**Business Intelligence:**
- `bi:read` - View BI questions and results
- `bi:write` - Submit BI questions
- `bi:admin` - Access admin BI features

**Talent Intelligence:**
- `talent:read` - View talent analyses
- `talent:write` - Create talent analyses

**Documents:**
- `documents:read` - View documents
- `documents:write` - Upload documents
- `documents:delete` - Delete documents

**System:**
- `system:admin` - Full system access
- `users:create` - Create users
- `users:manage` - Manage users

## Security Best Practices

1. **Store tokens securely** - Use httpOnly cookies or secure storage (not localStorage for sensitive apps)
2. **Refresh tokens proactively** - Refresh before expiry, not after
3. **Handle 401 responses** - Implement automatic token refresh logic
4. **Use HTTPS** - Always use HTTPS in production
5. **Implement logout** - Call the logout endpoint when users log out
6. **Session monitoring** - Allow users to view and terminate active sessions

## Example: MCP Server Integration

```typescript
// Authentication flow for MCP server
import axios from 'axios';

class ElizaAPIClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  async login(email: string, password: string) {
    const response = await axios.post(`${this.baseURL}/auth/login`, {
      email,
      password
    });
    
    this.accessToken = response.data.access_token;
    this.refreshToken = response.data.refresh_token;
    
    return response.data.user;
  }

  async refreshAccessToken() {
    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await axios.post(`${this.baseURL}/auth/refresh`, {
      refresh_token: this.refreshToken
    });
    
    this.accessToken = response.data.access_token;
    this.refreshToken = response.data.refresh_token;
  }

  async makeRequest(method: string, path: string, data?: any) {
    try {
      return await axios({
        method,
        url: `${this.baseURL}${path}`,
        headers: {
          Authorization: `Bearer ${this.accessToken}`
        },
        data
      });
    } catch (error: any) {
      if (error.response?.status === 401) {
        // Token expired, refresh and retry
        await this.refreshAccessToken();
        return this.makeRequest(method, path, data);
      }
      throw error;
    }
  }

  async logout() {
    await this.makeRequest('POST', '/auth/logout');
    this.accessToken = null;
    this.refreshToken = null;
  }
}
```

## Troubleshooting

### "Invalid or expired token"

**Cause:** Access token has expired (> 8 hours old)

**Solution:** Use refresh token to get a new access token

### "Session not found"

**Cause:** Session was terminated or expired

**Solution:** User must log in again

### "Insufficient permissions"

**Cause:** User's role doesn't have required permission

**Solution:** Check user's permissions with `/auth/check-permissions`, contact admin to grant permission


