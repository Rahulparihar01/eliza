# Northflank Deployment Diagnosis - December 23, 2025

## Issue Summary
**Error:** 503 Service Unavailable on `/v1/auth/login:1` endpoint  
**Frontend URL:** `https://caylent.elizaplatform.com`  
**Backend URL:** `https://p01--app--sf6snl685jbp.code.run`

## Current Configuration Analysis

### ✅ What's Working
1. **App Service Status:** COMPLETED and running
2. **Health Checks:** Passing (200 OK on `/health/ready`)
3. **Database:** Successfully initialized
4. **Migrations:** Completed successfully
5. **Admin User:** Created (admin@eliza.com / admin123)
6. **Container Startup:** Clean startup with no errors

### ❌ The Problem: 503 Error on Login

Based on the error screenshot and logs, here's the diagnosis:

## Root Cause Analysis

### 1. **CORS Configuration Issue**
Your current environment variables show:
```bash
ALLOWED_ORIGINS=https://p01--frontend--sf6snl685jbp.code.run,http://localhost:3000,https://*.elizaplatform.com
```

**Problem:** The frontend is accessing from `https://caylent.elizaplatform.com` but the wildcard `https://*.elizaplatform.com` may not be working correctly in FastAPI's CORS middleware.

### 2. **Host Header Validation**
Your current configuration:
```bash
ALLOWED_HOSTS=p01--frontend--sf6snl685jbp.code.run,p01--app--sf6snl685jbp.code.run,app,localhost,127.0.0.1
```

**Problem:** The backend URL `p01--app--sf6snl685jbp.code.run` is in ALLOWED_HOSTS, but the actual request might be coming through a different hostname or proxy.

### 3. **Service Routing**
The 503 error suggests that:
- The request is reaching Northflank's load balancer
- But it's not being properly routed to your app container
- OR the app is rejecting the request due to CORS/Host validation

## Detailed Findings

### App Service Configuration
- **Service ID:** `app`
- **Project:** `eliza-platform`
- **Status:** COMPLETED (running)
- **Last Deployment:** 2025-12-23T22:47:19.226Z
- **Container:** `app-56f78688-528v8` (active)
- **Port:** 5001 (internal)

### Environment Variables (From Logs)
```json
{
  "environment": "production",
  "customer_id": "eliza",
  "log_level": "INFO",
  "logstash_enabled": true
}
```

### Recent Activity
- App restarted at 22:47:19 UTC
- Previous container (`app-5cf9444574-2ntrr`) shut down cleanly
- New container started successfully
- Health checks passing every 30-60 seconds

## Recommended Fixes

### Fix #1: Update ALLOWED_ORIGINS (CRITICAL)
The wildcard pattern might not work. Use explicit domains:

```bash
ALLOWED_ORIGINS=https://caylent.elizaplatform.com,https://p01--frontend--sf6snl685jbp.code.run,http://localhost:3000
```

### Fix #2: Update ALLOWED_HOSTS
Add the actual domain being used:

```bash
ALLOWED_HOSTS=caylent.elizaplatform.com,p01--app--sf6snl685jbp.code.run,app,localhost,127.0.0.1
```

### Fix #3: Check Frontend API URL Configuration
The frontend needs to point to the correct backend URL. Based on your Northflank setup:

**Frontend Environment Variable:**
```bash
REACT_APP_API_URL=https://p01--app--sf6snl685jbp.code.run
```

OR if you have a custom domain for the API:
```bash
REACT_APP_API_URL=https://api.caylent.elizaplatform.com
```

### Fix #4: Verify Port Mapping
Ensure the Northflank service is exposing port 5001 correctly:
- Internal port: 5001
- External port: 443 (HTTPS)
- Protocol: HTTP/HTTPS

## Testing Steps

### 1. Test Health Endpoint
```bash
curl -v https://p01--app--sf6snl685jbp.code.run/health/ready
```
Expected: 200 OK

### 2. Test Login Endpoint Directly
```bash
curl -v -X POST https://p01--app--sf6snl685jbp.code.run/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "Origin: https://caylent.elizaplatform.com" \
  -d '{"email":"admin@eliza.com","password":"admin123"}'
```
Expected: 200 OK with JWT token

### 3. Test CORS Preflight
```bash
curl -v -X OPTIONS https://p01--app--sf6snl685jbp.code.run/v1/auth/login \
  -H "Origin: https://caylent.elizaplatform.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type"
```
Expected: 200 OK with CORS headers

## Next Steps

1. **Update Environment Variables** (Highest Priority)
   - Fix ALLOWED_ORIGINS to include explicit domain
   - Fix ALLOWED_HOSTS to include frontend domain
   
2. **Verify Frontend Configuration**
   - Check REACT_APP_API_URL points to correct backend
   - Rebuild frontend if needed

3. **Check Northflank Routing**
   - Verify domain mappings
   - Check if custom domains are properly configured
   - Ensure SSL certificates are valid

4. **Monitor Logs**
   - Watch for CORS errors
   - Check for authentication failures
   - Look for routing issues

## Additional Information Needed

To complete the diagnosis, we need:

1. **Frontend Environment Variables**
   - What is REACT_APP_API_URL set to?
   
2. **Northflank Domain Configuration**
   - Is `caylent.elizaplatform.com` mapped to the frontend service?
   - Is there a custom domain for the API?
   
3. **Network Path**
   - Browser → `caylent.elizaplatform.com` (frontend)
   - Frontend → ??? (backend API URL)
   
4. **Browser Console Errors**
   - Full error message from browser console
   - Network tab showing the failing request

## Quick Fix Command

If you want to test immediately, update these environment variables in Northflank:

```bash
# For app service
ALLOWED_ORIGINS=https://caylent.elizaplatform.com,https://p01--frontend--sf6snl685jbp.code.run,http://localhost:3000
ALLOWED_HOSTS=caylent.elizaplatform.com,p01--app--sf6snl685jbp.code.run,app,localhost,127.0.0.1

# For frontend service (if not already set)
REACT_APP_API_URL=https://p01--app--sf6snl685jbp.code.run
```

Then restart both services.

## Summary

**The 503 error is most likely caused by:**
1. CORS configuration not allowing requests from `caylent.elizaplatform.com`
2. Wildcard pattern in ALLOWED_ORIGINS not working as expected
3. Possible mismatch between frontend API URL and actual backend URL

**The fix is straightforward:**
- Update environment variables with explicit domains
- Restart services
- Test the login flow again

**Confidence Level:** High - This is a classic CORS/routing configuration issue, not an application code problem.

