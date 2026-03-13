# 🔍 Frontend Blank Page Diagnosis Guide

## 🎯 **Problem Summary**
- ✅ **Backend API**: Fully functional (auth, admin dashboard working)
- ✅ **Authentication**: Login works with `admin@ai-enablement.com` / `admin123`
- ❌ **Frontend**: Blank page after login

---

## 🔧 **Step-by-Step Diagnosis**

### **Step 1: Browser Developer Tools (CRITICAL)**

Open your browser to `http://localhost:3000` and:

1. **Open Developer Tools** (F12 or right-click → Inspect)
2. **Go to Console tab** - Look for JavaScript errors
3. **Go to Network tab** - Check API requests
4. **Try to login** with `admin@ai-enablement.com` / `admin123`
5. **Watch for errors** during/after login

**Look for these specific issues:**
```
❌ CORS errors
❌ API request failures 
❌ 404 errors on /v1/auth/login
❌ Network timeout errors
❌ JavaScript runtime errors
```

### **Step 2: API Configuration Issue**

The frontend has **two different API configurations**:

**Development mode** (`frontend/package.json`):
```json
"start": "REACT_APP_API_URL='http://localhost:5001' react-scripts start"
```

**Production mode** (`frontend/nginx.conf`):
```nginx
location /v1/ {
    proxy_pass http://app:5001;
}
```

**🚨 LIKELY ISSUE**: Frontend is trying to call `http://localhost:5001` but should use nginx proxy `/v1/`

---

## 🛠️ **Quick Fixes to Test**

### **Fix 1: Update Frontend API Configuration**

The frontend API service should use relative URLs in production:

```typescript
// In frontend/src/services/api.ts
constructor() {
  // Use relative URL in production (Docker)
  this.baseURL = process.env.NODE_ENV === 'production' 
    ? '' // Use nginx proxy
    : 'http://localhost:5001'; // Development only
}
```

### **Fix 2: Check Environment Variables**

In the Docker container, the frontend should:
- **NOT** set `REACT_APP_API_URL` 
- **USE** the nginx proxy at `/v1/`

---

## 🔍 **Diagnostic Commands**

### **Check Frontend Logs:**
```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform/docker
docker-compose logs frontend -f
```

### **Check API Proxy:**
```bash
# Test if nginx proxy works
curl -X POST http://localhost:3000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@ai-enablement.com", "password": "admin123"}'
```

### **Check Frontend Container Environment:**
```bash
docker-compose exec frontend env | grep -i api
```

---

## 🎯 **Most Likely Root Causes**

### **1. API URL Configuration (90% likely)**
```typescript
// WRONG in production:
baseURL: 'http://localhost:5001' 

// RIGHT in production:
baseURL: '' // Use nginx proxy
```

### **2. CORS Issues (5% likely)**
- Frontend trying to call external API
- CORS headers not allowing cross-origin requests

### **3. Authentication Flow Bug (5% likely)**
- Login succeeds but redirect fails
- Token storage issues
- Route protection logic errors

---

## 📋 **What to Check in Browser DevTools**

### **Console Tab - Look for:**
```
❌ TypeError: Failed to fetch
❌ Network request failed  
❌ CORS policy error
❌ Cannot read property of undefined
❌ Uncaught ReferenceError
```

### **Network Tab - Look for:**
```
❌ POST /v1/auth/login → 404 Not Found
❌ GET http://localhost:5001/v1/auth/login → Failed
❌ OPTIONS requests failing (CORS preflight)
❌ Any red/failed requests
```

### **Application Tab - Check:**
```
✅ localStorage['auth_token'] exists after login
✅ localStorage['refresh_token'] exists
❌ Tokens missing or malformed
```

---

## 🚀 **Expected Working Flow**

1. **User visits** `http://localhost:3000`
2. **Frontend loads** React app from nginx
3. **User logs in** with admin credentials
4. **Frontend makes API call** to `/v1/auth/login` (nginx proxy)
5. **Nginx proxies** request to `http://app:5001/v1/auth/login`
6. **Backend responds** with JWT token
7. **Frontend stores** token and redirects to `/dashboard`
8. **Dashboard loads** with authenticated user

---

## 🎯 **Next Steps**

1. **Open browser DevTools** and check Console/Network tabs
2. **Try login** and watch for errors
3. **Test nginx proxy** with curl command above
4. **Report findings** - what errors do you see?

The backend is working perfectly, so this is definitely a frontend configuration or routing issue! 🎯

---

## 💡 **Quick Test Commands**

```bash
# Test backend directly (should work)
curl -X POST http://localhost:5001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@ai-enablement.com", "password": "admin123"}'

# Test nginx proxy (should also work)  
curl -X POST http://localhost:3000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@ai-enablement.com", "password": "admin123"}'

# If nginx proxy fails, that's the issue!
```
