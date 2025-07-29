# Liara Platform Best Practices Research Summary

## Overview

This document summarizes comprehensive research on Liara platform best practices for deploying Django backend and React frontend applications, including connectivity patterns, common pitfalls, and recommended solutions.

## Research Findings Summary

### Django Backend Deployment Best Practices

**Key Configuration Requirements**:
- **liara.json**: Must specify correct Python version, enable static collection, and allow settings modification
- **Environment Variables**: SECRET_KEY, DEBUG, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS are critical
- **Database**: Use DATABASE_URL with dj-database-url for PostgreSQL connection
- **Static Files**: WhiteNoise middleware required for static file serving
- **Security**: Proper SSL, HSTS, and security headers configuration essential

**Critical Success Factors**:
1. Environment variable validation in Django settings
2. Proper middleware ordering (CORS first, WhiteNoise after Security)
3. Database migrations run after deployment
4. Static files collection enabled in build process
5. Security settings configured for production

### React Frontend Deployment Best Practices

**Key Configuration Requirements**:
- **liara.json**: Static platform with SPA routing enabled
- **Environment Variables**: All custom variables must start with REACT_APP_
- **Build Process**: Must handle CI environment and memory constraints
- **Performance**: Code splitting and bundle optimization recommended
- **Caching**: Proper cache headers for static assets

**Critical Success Factors**:
1. SPA routing configuration for React Router
2. Environment variables available at build time
3. Build process handles warnings and memory limits
4. API connectivity properly configured
5. Bundle size optimized for performance

### Frontend-Backend Connectivity Best Practices

**Architecture Patterns**:
- **Subdomain Approach**: frontend.com + api.frontend.com (recommended)
- **CORS Configuration**: Specific origins, never allow all origins
- **SSL/HTTPS**: Consistent HTTPS usage across all services
- **Authentication**: JWT tokens with proper refresh mechanisms
- **Error Handling**: Comprehensive error handling and retry logic

**Critical Success Factors**:
1. Proper DNS configuration for custom domains
2. CORS middleware first in Django middleware stack
3. SSL certificates properly configured
4. API client with interceptors for auth and errors
5. Health checks for monitoring connectivity

### Common Pitfalls and Prevention

**Most Critical Pitfalls**:
1. **Environment Variables**: Missing or incorrectly configured
2. **CORS Issues**: Improper configuration blocking API access
3. **Static Files**: Not serving correctly due to configuration errors
4. **SPA Routing**: Direct URL access failing without proper configuration
5. **Build Failures**: CI environment treating warnings as errors

**Prevention Strategies**:
1. Comprehensive pre-deployment checklists
2. Staging environment testing
3. Automated testing and validation
4. Proper monitoring and alerting
5. Documentation of all configurations

## Recommended Implementation Approach

### Phase 1: Backend Configuration
1. **Environment Variables Setup**
   - Generate secure SECRET_KEY
   - Configure DEBUG=False for production
   - Set ALLOWED_HOSTS with all domains
   - Configure CORS_ALLOWED_ORIGINS

2. **Django Settings Optimization**
   - Implement environment variable validation
   - Configure proper middleware ordering
   - Set up WhiteNoise for static files
   - Configure security headers

3. **Database Setup**
   - Verify DATABASE_URL configuration
   - Run migrations after deployment
   - Test database connectivity

### Phase 2: Frontend Configuration
1. **Build Process Setup**
   - Configure liara.json for static platform
   - Enable SPA routing
   - Set up proper environment variables
   - Test build process locally

2. **API Integration**
   - Configure axios with proper base URL
   - Implement request/response interceptors
   - Add error handling and retry logic
   - Test API connectivity

3. **Performance Optimization**
   - Implement code splitting
   - Optimize bundle size
   - Configure proper caching headers
   - Test loading performance

### Phase 3: Connectivity and Security
1. **Domain Configuration**
   - Set up DNS records properly
   - Configure SSL certificates
   - Test domain accessibility
   - Verify HTTPS enforcement

2. **CORS Configuration**
   - Configure specific allowed origins
   - Test preflight requests
   - Verify credentials handling
   - Monitor CORS errors

3. **Security Implementation**
   - Implement proper authentication
   - Configure security headers
   - Validate input data
   - Monitor security events

## Configuration Templates

### Django Backend Template

**liara.json**:
```json
{
  "django": {
    "mirror": true,
    "pythonVersion": "3.10",
    "timezone": "Asia/Tehran",
    "compileMessages": false,
    "modifySettings": true,
    "geospatial": false,
    "collectStatic": true
  },
  "build": {
    "buildCommand": "python manage.py collectstatic --noinput"
  }
}
```

**Environment Variables**:
```bash
SECRET_KEY=your-generated-secret-key
DEBUG=False
ALLOWED_HOSTS=your-app.liara.run,api.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

**Key Settings**:
```python
# Database
DATABASES = {
    'default': dj_database_url.parse(
        os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
} if os.environ.get('DATABASE_URL') else {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# CORS
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
CORS_ALLOW_CREDENTIALS = True

# Security
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
```

### React Frontend Template

**liara.json**:
```json
{
  "platform": "static",
  "app": "your-frontend-app",
  "build": {
    "command": "CI=false npm run build",
    "output": "build"
  },
  "static": {
    "spa": true,
    "gzip": true,
    "cache": {
      "static": "1y",
      "html": "0"
    }
  }
}
```

**Environment Variables**:
```bash
REACT_APP_API_BASE_URL=https://api.yourdomain.com/api/v1
REACT_APP_FRONTEND_URL=https://yourdomain.com
REACT_APP_BACKEND_URL=https://api.yourdomain.com
GENERATE_SOURCEMAP=false
```

**API Client Configuration**:
```javascript
const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
  timeout: 10000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

## Testing and Validation Procedures

### Backend Testing
```python
# test_deployment.py
import requests

def test_backend_deployment():
    base_url = "https://api.yourdomain.com"
    
    # Test health endpoint
    response = requests.get(f"{base_url}/health/")
    assert response.status_code == 200
    
    # Test CORS
    response = requests.options(
        f"{base_url}/api/v1/auth/login/",
        headers={'Origin': 'https://yourdomain.com'}
    )
    assert 'Access-Control-Allow-Origin' in response.headers
    
    # Test API endpoints
    response = requests.post(f"{base_url}/api/v1/auth/login/", json={})
    assert response.status_code == 400  # Expected for empty data
```

### Frontend Testing
```javascript
// test_connectivity.js
export const testFrontendDeployment = async () => {
  const tests = [];
  
  // Test API connectivity
  try {
    const response = await apiClient.get('/health/');
    tests.push({ name: 'API Health', status: 'pass' });
  } catch (error) {
    tests.push({ name: 'API Health', status: 'fail', error: error.message });
  }
  
  // Test authentication endpoint
  try {
    await apiClient.post('/auth/login/', {});
  } catch (error) {
    tests.push({
      name: 'Auth Endpoint',
      status: error.response?.status === 400 ? 'pass' : 'fail'
    });
  }
  
  return tests;
};
```

## Monitoring and Maintenance

### Health Check Implementation
```python
# Django health check
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': time.time()
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)
```

### Performance Monitoring
```javascript
// Frontend performance monitoring
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

const sendToAnalytics = (metric) => {
  console.log(metric);
  // Send to monitoring service
};

getCLS(sendToAnalytics);
getFID(sendToAnalytics);
getFCP(sendToAnalytics);
getLCP(sendToAnalytics);
getTTFB(sendToAnalytics);
```

## Security Considerations

### Backend Security
- Environment variable validation
- Proper CORS configuration
- SSL/HTTPS enforcement
- Security headers implementation
- Input validation and sanitization

### Frontend Security
- No sensitive data in environment variables
- Content Security Policy implementation
- Input sanitization
- Secure token storage
- Error boundary implementation

## Performance Optimization

### Backend Optimization
- Database connection pooling
- Query optimization
- Caching implementation
- Static file compression
- Response time monitoring

### Frontend Optimization
- Code splitting and lazy loading
- Bundle size optimization
- Image optimization
- Caching strategies
- Performance monitoring

## Deployment Workflow

### Pre-Deployment
1. Environment variable validation
2. Local testing with production settings
3. Security audit
4. Performance testing
5. Staging environment validation

### Deployment Process
1. Backend deployment and migration
2. Frontend build and deployment
3. Domain and SSL configuration
4. Connectivity testing
5. Performance validation

### Post-Deployment
1. Health check monitoring
2. Error tracking setup
3. Performance monitoring
4. User acceptance testing
5. Documentation updates

## Key Takeaways

### Critical Success Factors
1. **Environment Variables**: Proper configuration is essential for both platforms
2. **CORS Configuration**: Must be specific and properly ordered in middleware
3. **Static Files**: WhiteNoise configuration critical for Django
4. **SPA Routing**: Essential for React Router functionality
5. **SSL/HTTPS**: Consistent usage across all services

### Most Important Preventive Measures
1. Comprehensive testing in staging environment
2. Environment variable validation
3. Proper error handling and monitoring
4. Regular security audits
5. Performance monitoring and optimization

### Recommended Tools and Libraries
- **Django**: django-cors-headers, whitenoise, dj-database-url
- **React**: axios, react-router-dom, web-vitals
- **Monitoring**: Health check endpoints, error tracking
- **Security**: CSP headers, input validation, secure headers

This research provides a solid foundation for successful deployment of Django and React applications on Liara platform with best practices for security, performance, and reliability.