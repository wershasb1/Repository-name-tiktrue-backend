# Liara Frontend-Backend Connectivity Best Practices

## Overview

This document outlines the best practices for connecting React frontend applications to Django backend APIs on Liara platform, covering CORS configuration, domain setup, SSL certificates, and API communication patterns.

## Architecture Overview

### Typical Liara Deployment Architecture

```
┌─────────────────────┐    HTTPS    ┌─────────────────────┐
│   React Frontend    │ ──────────► │   Django Backend    │
│  (Static Platform)  │             │ (Django Platform)   │
│                     │             │                     │
│ yourdomain.com      │             │ api.yourdomain.com  │
│ your-app.liara.run  │             │ your-api.liara.run  │
└─────────────────────┘             └─────────────────────┘
                                              │
                                              ▼
                                    ┌─────────────────────┐
                                    │   PostgreSQL DB     │
                                    │  (Database Service) │
                                    └─────────────────────┘
```

### Communication Flow

1. **User visits frontend** → React app loads from static platform
2. **Frontend makes API calls** → Axios requests to Django backend
3. **Backend processes requests** → Django REST API handles requests
4. **Database operations** → Django ORM interacts with PostgreSQL
5. **Response sent back** → JSON response to frontend
6. **Frontend updates UI** → React components re-render with data

## Domain Configuration Best Practices

### Recommended Domain Structure

**Option 1: Subdomain Approach (Recommended)**
```
Frontend: https://yourdomain.com
Backend:  https://api.yourdomain.com
```

**Option 2: Path-based Approach**
```
Frontend: https://yourdomain.com
Backend:  https://yourdomain.com/api
```

**Option 3: Separate Domains**
```
Frontend: https://app.yourdomain.com
Backend:  https://api.yourdomain.com
```

### DNS Configuration

**For Subdomain Approach**:
```dns
# Frontend (yourdomain.com)
Type: A
Name: @
Value: [Liara Static IP]

Type: CNAME
Name: www
Value: yourdomain.com

# Backend (api.yourdomain.com)
Type: CNAME
Name: api
Value: your-backend-app.liara.run
```

**For Path-based Approach** (requires reverse proxy):
```dns
# Single domain with reverse proxy
Type: A
Name: @
Value: [Liara Reverse Proxy IP]
```

## CORS Configuration

### Django Backend CORS Setup

**Install django-cors-headers**:
```bash
pip install django-cors-headers
```

**settings.py Configuration**:
```python
import os

# Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ... other apps
    'corsheaders',
]

# Add to MIDDLEWARE (must be at the top)
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # ... other middleware
]

# CORS Configuration
CORS_ALLOWED_ORIGINS = []

# Add allowed origins from environment variable
if os.environ.get('CORS_ALLOWED_ORIGINS'):
    CORS_ALLOWED_ORIGINS.extend(
        os.environ.get('CORS_ALLOWED_ORIGINS').split(',')
    )

# Default origins for development
CORS_ALLOWED_ORIGINS.extend([
    "http://localhost:3000",
    "http://127.0.0.1:3000",
])

# CORS settings
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False  # Never True in production

# Allowed headers
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Allowed methods
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Preflight cache
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours
```

### Environment Variables for CORS

**Backend Environment Variables**:
```bash
# In Liara dashboard for Django app
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

**Frontend Environment Variables**:
```bash
# .env.production
REACT_APP_API_BASE_URL=https://api.yourdomain.com/api/v1
REACT_APP_FRONTEND_URL=https://yourdomain.com
```

### CORS Troubleshooting

**Common CORS Errors and Solutions**:

1. **"Access to XMLHttpRequest blocked by CORS policy"**
   ```python
   # Ensure origin is in CORS_ALLOWED_ORIGINS
   CORS_ALLOWED_ORIGINS = [
       "https://yourdomain.com",  # Must match exactly
   ]
   ```

2. **"Preflight request doesn't pass access control check"**
   ```python
   # Ensure CorsMiddleware is first
   MIDDLEWARE = [
       'corsheaders.middleware.CorsMiddleware',  # Must be first
       # ... other middleware
   ]
   ```

3. **"Credentials mode 'include' not supported"**
   ```python
   CORS_ALLOW_CREDENTIALS = True
   ```

## SSL/HTTPS Configuration

### Automatic SSL with Liara

**Frontend SSL (Static Platform)**:
```json
{
  "platform": "static",
  "ssl": {
    "enabled": true,
    "redirect": true
  }
}
```

**Backend SSL (Django Platform)**:
```python
# settings.py
if not DEBUG:
    # Force HTTPS
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # HSTS Headers
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
```

### Custom SSL Certificates

**If using custom SSL certificates**:
```json
{
  "ssl": {
    "certificate": "/path/to/certificate.crt",
    "private_key": "/path/to/private.key",
    "certificate_chain": "/path/to/chain.crt"
  }
}
```

### Mixed Content Issues

**Prevent mixed content errors**:
```javascript
// Ensure all API calls use HTTPS in production
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'https://api.yourdomain.com/api/v1'
  : 'http://localhost:8000/api/v1';
```

## API Communication Patterns

### Axios Configuration for Liara

**API Client Setup**:
```javascript
// api/client.js
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
  timeout: 10000,
  withCredentials: true, // Important for CORS with credentials
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    
    if (error.response?.status >= 500) {
      // Handle server errors
      console.error('Server error:', error.response.data);
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;
```

### Error Handling for Network Issues

```javascript
// utils/errorHandler.js
export const handleApiError = (error) => {
  if (error.code === 'NETWORK_ERROR') {
    return {
      message: 'Network connection failed. Please check your internet connection.',
      type: 'network'
    };
  }
  
  if (error.response?.status === 0) {
    return {
      message: 'Cannot connect to server. Please try again later.',
      type: 'connection'
    };
  }
  
  if (error.response?.status >= 500) {
    return {
      message: 'Server error. Please try again later.',
      type: 'server'
    };
  }
  
  return {
    message: error.response?.data?.message || 'An error occurred',
    type: 'api'
  };
};
```

### Retry Logic for Failed Requests

```javascript
// utils/retryLogic.js
import axios from 'axios';

const retryRequest = async (fn, retries = 3, delay = 1000) => {
  try {
    return await fn();
  } catch (error) {
    if (retries > 0 && error.response?.status >= 500) {
      await new Promise(resolve => setTimeout(resolve, delay));
      return retryRequest(fn, retries - 1, delay * 2);
    }
    throw error;
  }
};

// Usage
const fetchUserData = () => retryRequest(() => apiClient.get('/user/profile/'));
```

## Authentication and Authorization

### JWT Token Handling

**Frontend Token Management**:
```javascript
// auth/tokenManager.js
class TokenManager {
  static getToken() {
    return localStorage.getItem('token');
  }
  
  static setToken(token) {
    localStorage.setItem('token', token);
  }
  
  static removeToken() {
    localStorage.removeItem('token');
  }
  
  static isTokenExpired(token) {
    if (!token) return true;
    
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.exp * 1000 < Date.now();
    } catch {
      return true;
    }
  }
  
  static refreshToken() {
    const refreshToken = localStorage.getItem('refreshToken');
    if (!refreshToken) return null;
    
    return apiClient.post('/auth/refresh/', {
      refresh: refreshToken
    });
  }
}

export default TokenManager;
```

**Backend JWT Configuration**:
```python
# settings.py
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}
```

### Protected Routes

```javascript
// components/ProtectedRoute.js
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return <div>Loading...</div>;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

export default ProtectedRoute;
```

## Performance Optimization

### Request Optimization

**Request Batching**:
```javascript
// utils/batchRequests.js
class RequestBatcher {
  constructor(delay = 100) {
    this.delay = delay;
    this.queue = [];
    this.timeout = null;
  }
  
  add(request) {
    return new Promise((resolve, reject) => {
      this.queue.push({ request, resolve, reject });
      
      if (this.timeout) {
        clearTimeout(this.timeout);
      }
      
      this.timeout = setTimeout(() => {
        this.flush();
      }, this.delay);
    });
  }
  
  async flush() {
    const batch = this.queue.splice(0);
    
    try {
      const responses = await Promise.all(
        batch.map(({ request }) => request())
      );
      
      batch.forEach(({ resolve }, index) => {
        resolve(responses[index]);
      });
    } catch (error) {
      batch.forEach(({ reject }) => {
        reject(error);
      });
    }
  }
}

export default RequestBatcher;
```

### Caching Strategies

**Response Caching**:
```javascript
// utils/cache.js
class ApiCache {
  constructor(ttl = 300000) { // 5 minutes default
    this.cache = new Map();
    this.ttl = ttl;
  }
  
  get(key) {
    const item = this.cache.get(key);
    if (!item) return null;
    
    if (Date.now() > item.expiry) {
      this.cache.delete(key);
      return null;
    }
    
    return item.data;
  }
  
  set(key, data) {
    this.cache.set(key, {
      data,
      expiry: Date.now() + this.ttl
    });
  }
  
  clear() {
    this.cache.clear();
  }
}

const apiCache = new ApiCache();

// Usage with axios interceptor
apiClient.interceptors.request.use((config) => {
  if (config.method === 'get') {
    const cached = apiCache.get(config.url);
    if (cached) {
      return Promise.resolve({ data: cached });
    }
  }
  return config;
});

apiClient.interceptors.response.use((response) => {
  if (response.config.method === 'get') {
    apiCache.set(response.config.url, response.data);
  }
  return response;
});
```

## Monitoring and Debugging

### Request Logging

```javascript
// utils/requestLogger.js
const requestLogger = {
  log: (config) => {
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, {
      headers: config.headers,
      data: config.data,
      timestamp: new Date().toISOString()
    });
  },
  
  logResponse: (response) => {
    console.log(`[API Response] ${response.status} ${response.config.url}`, {
      data: response.data,
      duration: response.config.metadata?.endTime - response.config.metadata?.startTime,
      timestamp: new Date().toISOString()
    });
  },
  
  logError: (error) => {
    console.error(`[API Error] ${error.config?.url}`, {
      status: error.response?.status,
      message: error.message,
      data: error.response?.data,
      timestamp: new Date().toISOString()
    });
  }
};

// Add to axios interceptors
apiClient.interceptors.request.use((config) => {
  config.metadata = { startTime: Date.now() };
  requestLogger.log(config);
  return config;
});

apiClient.interceptors.response.use(
  (response) => {
    response.config.metadata.endTime = Date.now();
    requestLogger.logResponse(response);
    return response;
  },
  (error) => {
    requestLogger.logError(error);
    return Promise.reject(error);
  }
);
```

### Health Check Implementation

**Backend Health Check**:
```python
# views.py
from django.http import JsonResponse
from django.db import connection
import time

def health_check(request):
    start_time = time.time()
    
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    response_time = (time.time() - start_time) * 1000
    
    return JsonResponse({
        'status': 'healthy' if db_status == 'healthy' else 'unhealthy',
        'database': db_status,
        'response_time_ms': round(response_time, 2),
        'timestamp': time.time()
    })
```

**Frontend Health Check**:
```javascript
// utils/healthCheck.js
export const checkBackendHealth = async () => {
  try {
    const response = await apiClient.get('/health/', { timeout: 5000 });
    return {
      status: 'healthy',
      data: response.data
    };
  } catch (error) {
    return {
      status: 'unhealthy',
      error: error.message
    };
  }
};

// Use in app initialization
useEffect(() => {
  checkBackendHealth().then(result => {
    if (result.status === 'unhealthy') {
      console.warn('Backend health check failed:', result.error);
    }
  });
}, []);
```

## Common Connectivity Issues and Solutions

### Issue 1: CORS Preflight Failures

**Problem**: OPTIONS requests failing

**Solution**:
```python
# Ensure CORS middleware is first
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    # ... other middleware
]

# Allow OPTIONS method
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',  # Must be included
    'PATCH',
    'POST',
    'PUT',
]
```

### Issue 2: Authentication Token Issues

**Problem**: Token not being sent or recognized

**Solution**:
```javascript
// Ensure withCredentials is set
const apiClient = axios.create({
  withCredentials: true,
  // ... other config
});

// Ensure token is in correct format
config.headers.Authorization = `Bearer ${token}`;
```

### Issue 3: SSL Certificate Issues

**Problem**: SSL certificate errors

**Solution**:
1. Verify domain DNS configuration
2. Check SSL certificate validity
3. Ensure HTTPS is used consistently
4. Configure proper security headers

### Issue 4: Network Timeouts

**Problem**: Requests timing out

**Solution**:
```javascript
const apiClient = axios.create({
  timeout: 30000, // Increase timeout
  // ... other config
});

// Implement retry logic
const retryConfig = {
  retries: 3,
  retryDelay: (retryCount) => {
    return retryCount * 1000;
  },
  retryCondition: (error) => {
    return error.code === 'ECONNABORTED' || error.response?.status >= 500;
  }
};
```

## Testing Connectivity

### Backend API Testing

```python
# test_connectivity.py
import requests
import json

def test_api_connectivity():
    base_url = "https://api.yourdomain.com"
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health/", timeout=10)
        print(f"Health check: {response.status_code}")
    except Exception as e:
        print(f"Health check failed: {e}")
    
    # Test CORS
    try:
        response = requests.options(
            f"{base_url}/api/v1/auth/login/",
            headers={
                'Origin': 'https://yourdomain.com',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type'
            }
        )
        print(f"CORS preflight: {response.status_code}")
        print(f"CORS headers: {response.headers}")
    except Exception as e:
        print(f"CORS test failed: {e}")

if __name__ == "__main__":
    test_api_connectivity()
```

### Frontend Connectivity Testing

```javascript
// utils/connectivityTest.js
export const testConnectivity = async () => {
  const tests = [];
  
  // Test API health
  try {
    const response = await apiClient.get('/health/');
    tests.push({
      name: 'API Health',
      status: 'pass',
      response: response.data
    });
  } catch (error) {
    tests.push({
      name: 'API Health',
      status: 'fail',
      error: error.message
    });
  }
  
  // Test authentication endpoint
  try {
    const response = await apiClient.post('/auth/login/', {});
    tests.push({
      name: 'Auth Endpoint',
      status: response.status === 400 ? 'pass' : 'fail',
      note: 'Expected 400 for empty data'
    });
  } catch (error) {
    tests.push({
      name: 'Auth Endpoint',
      status: error.response?.status === 400 ? 'pass' : 'fail',
      error: error.message
    });
  }
  
  return tests;
};
```

## Best Practices Summary

### Security Best Practices
1. Always use HTTPS in production
2. Configure CORS properly (never use CORS_ALLOW_ALL_ORIGINS = True)
3. Implement proper authentication and authorization
4. Use secure headers and CSP
5. Validate all input data

### Performance Best Practices
1. Implement request caching
2. Use request batching for multiple calls
3. Implement retry logic for failed requests
4. Optimize bundle size and lazy loading
5. Monitor API response times

### Reliability Best Practices
1. Implement proper error handling
2. Use health checks for monitoring
3. Implement graceful degradation
4. Log all API interactions
5. Test connectivity regularly

### Maintenance Best Practices
1. Monitor SSL certificate expiration
2. Keep dependencies updated
3. Regular security audits
4. Performance monitoring
5. Backup and recovery procedures

This comprehensive guide covers all aspects of connecting React frontend to Django backend on Liara platform with best practices for security, performance, and reliability.