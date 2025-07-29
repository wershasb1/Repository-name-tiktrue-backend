# Frontend-Backend Connectivity Issues Analysis

## Current Connectivity Configuration

### Frontend API Configuration

**Base URL Configuration**:
```javascript
// In AuthContext.js
axios.defaults.baseURL = process.env.REACT_APP_API_BASE_URL || 'https://api.tiktrue.com/api/v1';
```

**Environment Variables**:
```bash
# .env and .env.production (identical)
REACT_APP_API_BASE_URL=https://api.tiktrue.com/api/v1
REACT_APP_FRONTEND_URL=https://tiktrue.com
REACT_APP_BACKEND_URL=https://api.tiktrue.com
```

### Backend CORS Configuration

**Django CORS Settings**:
```python
# In settings.py
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') + [
    "https://tiktrue.com",
    "https://www.tiktrue.com", 
    "https://tiktrue-frontend.liara.run",
]
CORS_ALLOW_CREDENTIALS = True
```

**Middleware Configuration**:
```python
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # First in middleware stack
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ... other middleware
]
```

## Identified Connectivity Issues

### 1. Domain Configuration Problems

**Issue**: Potential domain mismatch between frontend and backend

**Current Setup**:
- Frontend: `tiktrue.com` (expected)
- Backend API: `api.tiktrue.com` (expected)
- Liara Backend: `tiktrue-backend.liara.run` (fallback)
- Liara Frontend: `tiktrue-frontend.liara.run` (fallback)

**Problems**:
1. **DNS Configuration**: Need to verify that `api.tiktrue.com` properly points to the Liara backend
2. **SSL Certificate**: Need to ensure SSL certificates are properly configured for both domains
3. **Domain Propagation**: DNS changes may not have propagated fully

### 2. CORS Configuration Issues

**Potential Issues**:

1. **Environment Variable Not Set**: If `CORS_ALLOWED_ORIGINS` environment variable is not set in Liara, it defaults to localhost only
2. **Origin Mismatch**: Frontend may be sending requests from a domain not in the allowed origins list
3. **Credentials Handling**: CORS_ALLOW_CREDENTIALS is True but may need additional configuration

**Expected CORS Headers**:
```
Access-Control-Allow-Origin: https://tiktrue.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Credentials: true
```

### 3. SSL/HTTPS Configuration Issues

**Backend SSL Settings**:
```python
# Production security settings
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
```

**Potential Issues**:
1. **Mixed Content**: Frontend (HTTPS) trying to access backend (HTTP)
2. **SSL Certificate Validation**: Invalid or expired SSL certificates
3. **Proxy Headers**: Liara proxy headers may not match Django expectations
4. **HSTS Policy**: Strict transport security may be blocking connections

### 4. API Endpoint Accessibility Issues

**Frontend API Calls**:
```javascript
// Authentication endpoints
POST /auth/login/
POST /auth/register/
GET /auth/profile/
POST /auth/forgot-password/
POST /auth/reset-password/

// Dashboard endpoints  
GET /models/available/
GET /license/info/
```

**Backend URL Structure**:
```python
# In urls.py
path('api/v1/auth/', include('accounts.urls')),
path('api/v1/license/', include('licenses.urls')),
path('api/v1/models/', include('models_api.urls')),
path('health/', health_check, name='health_check'),
```

**Potential Issues**:
1. **URL Mismatch**: Frontend expects `/auth/profile/` but backend may have different URL pattern
2. **Missing Endpoints**: Some endpoints called by frontend may not be implemented in backend
3. **Authentication Required**: Endpoints may require authentication but frontend not sending proper tokens
4. **HTTP Methods**: Frontend may be using wrong HTTP methods for certain endpoints

### 5. Authentication Token Issues

**Frontend Token Handling**:
```javascript
// Token storage and header setting
localStorage.setItem('token', tokens.access);
axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
```

**Backend JWT Configuration**:
```python
# JWT settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
}
```

**Potential Issues**:
1. **Token Format**: Backend may expect different token format
2. **Token Expiration**: Tokens may be expiring without proper refresh
3. **Token Validation**: Backend JWT validation may be failing
4. **Header Format**: Authorization header format may be incorrect

## Testing Results Analysis

### Backend API Test Results

**From `backend/test_api.py`**:
- Tests basic endpoint accessibility
- Tests CORS preflight requests
- Tests authentication endpoints

**Expected Test Outcomes**:
- Health endpoint: Should return 200
- Admin panel: Should return 200 or redirect
- API endpoints: Should return 400/401 (working but need data/auth)
- CORS preflight: Should return 200 with proper headers

### Frontend Integration Test Results

**From `frontend/test_integration.js`**:
- Tests frontend-backend connection
- Tests API endpoint responses
- Tests CORS configuration

**Common Failure Patterns**:
1. **Connection Timeout**: Network connectivity issues
2. **404 Not Found**: Endpoint doesn't exist or wrong URL
3. **403 Forbidden**: CORS policy blocking request
4. **500 Internal Server Error**: Backend configuration issues

## Environment-Specific Issues

### Development vs Production Environment

**Development Issues**:
- Frontend and backend both configured for production URLs
- No local development API configuration
- CORS configured for production domains only

**Production Issues**:
- Environment variables may not be set in Liara
- SSL certificates may not be properly configured
- DNS configuration may be incomplete

### Liara Platform-Specific Issues

**Potential Liara Issues**:
1. **App Communication**: Frontend and backend apps may not be able to communicate
2. **Environment Variables**: Required environment variables may not be set
3. **Domain Configuration**: Custom domains may not be properly configured
4. **SSL Certificates**: SSL certificates may not be installed or configured
5. **Database Connection**: Backend may not be able to connect to database

## Database Connectivity Issues

**Database Configuration**:
```python
# Backend database setup
if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.parse(os.environ.get('DATABASE_URL'))
    }
```

**Potential Issues**:
1. **DATABASE_URL Not Set**: Environment variable may not be configured in Liara
2. **Database Not Created**: PostgreSQL database may not be created or accessible
3. **Migrations Not Run**: Django migrations may not have been executed
4. **Connection Permissions**: Database user may not have proper permissions

## Error Patterns and Symptoms

### Common Error Messages

**Frontend Errors**:
```javascript
// Network errors
"Network Error" - Complete connection failure
"timeout of 10000ms exceeded" - Request timeout
"Request failed with status code 404" - Endpoint not found
"Request failed with status code 403" - CORS or permission issue
"Request failed with status code 500" - Backend server error
```

**Backend Errors**:
```python
# Django errors
"DisallowedHost" - Domain not in ALLOWED_HOSTS
"CORS policy" - CORS configuration issue
"Database connection failed" - Database connectivity issue
"Invalid token" - JWT authentication failure
```

### Browser Console Errors

**CORS Errors**:
```
Access to XMLHttpRequest at 'https://api.tiktrue.com/api/v1/auth/login/' 
from origin 'https://tiktrue.com' has been blocked by CORS policy
```

**SSL Errors**:
```
Mixed Content: The page at 'https://tiktrue.com' was loaded over HTTPS, 
but requested an insecure XMLHttpRequest endpoint
```

**Network Errors**:
```
Failed to load resource: net::ERR_NAME_NOT_RESOLVED
Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR
```

## Diagnostic Steps Required

### 1. Domain and DNS Verification
- [ ] Verify `api.tiktrue.com` resolves to correct IP
- [ ] Check DNS propagation status
- [ ] Verify SSL certificate installation
- [ ] Test domain accessibility from different locations

### 2. Liara Configuration Verification
- [ ] Check environment variables in Liara dashboard
- [ ] Verify backend app is running and accessible
- [ ] Check frontend app deployment status
- [ ] Verify database connection and migrations

### 3. CORS Testing
- [ ] Test CORS preflight requests manually
- [ ] Verify CORS headers in browser network tab
- [ ] Check CORS configuration in Django settings
- [ ] Test from different origins

### 4. API Endpoint Testing
- [ ] Test each API endpoint individually
- [ ] Verify request/response formats
- [ ] Check authentication requirements
- [ ] Test with proper authentication tokens

### 5. SSL/HTTPS Testing
- [ ] Verify SSL certificate validity
- [ ] Check for mixed content issues
- [ ] Test HTTPS redirects
- [ ] Verify security headers

## Recommended Fixes

### Immediate Actions Required

1. **Set Environment Variables in Liara**:
   ```bash
   SECRET_KEY=<secure-secret-key>
   DEBUG=False
   CORS_ALLOWED_ORIGINS=https://tiktrue.com,https://www.tiktrue.com
   DATABASE_URL=<postgresql-connection-string>
   ```

2. **Verify Domain Configuration**:
   - Ensure `api.tiktrue.com` points to Liara backend
   - Install SSL certificates for both domains
   - Test domain accessibility

3. **Run Database Migrations**:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

4. **Test API Endpoints**:
   - Run backend API test script
   - Run frontend integration test
   - Check browser network tab for errors

### Configuration Improvements

1. **Add Development Environment**:
   - Create separate .env.development for frontend
   - Configure local backend URL for development
   - Set up proper development CORS configuration

2. **Improve Error Handling**:
   - Add better error messages in frontend
   - Implement proper error boundaries
   - Add request/response interceptors

3. **Add Monitoring**:
   - Set up health check endpoints
   - Add logging for API requests
   - Monitor CORS and SSL issues

### Security Enhancements

1. **Improve CORS Configuration**:
   - Use more specific CORS settings
   - Add proper preflight handling
   - Implement CORS error logging

2. **Enhance SSL Configuration**:
   - Add proper SSL certificate monitoring
   - Implement certificate auto-renewal
   - Add security headers

3. **Token Management**:
   - Implement proper token refresh
   - Add token expiration handling
   - Consider httpOnly cookies for enhanced security

## Next Steps

1. **Immediate Testing**: Run connectivity tests to identify specific failures
2. **Environment Setup**: Configure all required environment variables in Liara
3. **Domain Configuration**: Verify and fix domain/DNS configuration
4. **API Testing**: Test each API endpoint individually
5. **End-to-End Testing**: Test complete user flows from frontend to backend