# Common Liara Deployment Pitfalls and Solutions

## Overview

This document outlines the most common deployment mistakes and issues encountered when deploying applications on Liara platform, along with their solutions and prevention strategies.

## Django Backend Pitfalls

### 1. Environment Variables Not Set

**Problem**: Application fails to start due to missing environment variables

**Symptoms**:
```
ValueError: SECRET_KEY environment variable is required
ImproperlyConfigured: The SECRET_KEY setting must not be empty
```

**Common Missing Variables**:
- `SECRET_KEY`
- `DEBUG`
- `DATABASE_URL` (usually auto-provided)
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`

**Solution**:
```python
# settings.py - Always validate required environment variables
import os

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")

DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Provide sensible defaults where possible
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',') if os.environ.get('ALLOWED_HOSTS') else []
```

**Prevention**:
1. Create environment variable checklist
2. Use environment variable validation in settings
3. Document all required variables
4. Test with production-like environment variables locally

### 2. Incorrect liara.json Configuration

**Problem**: Build fails or application doesn't start properly

**Common Mistakes**:
```json
{
  "django": {
    "pythonVersion": "3.9",  // ❌ Doesn't match runtime.txt
    "collectStatic": false,  // ❌ Static files won't be collected
    "modifySettings": false  // ❌ Liara can't optimize settings
  }
}
```

**Correct Configuration**:
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

**Prevention**:
- Always match `pythonVersion` with `runtime.txt`
- Enable `collectStatic` for static file serving
- Allow `modifySettings` for Liara optimizations

### 3. Database Migration Issues

**Problem**: Database schema is not up to date after deployment

**Symptoms**:
```
django.db.utils.ProgrammingError: relation "app_model" does not exist
```

**Common Causes**:
- Migrations not run after deployment
- Migration files not included in deployment
- Database connection issues

**Solution**:
```bash
# Run migrations after deployment
liara shell --app your-app-name
python manage.py migrate
python manage.py collectstatic --noinput
```

**Prevention**:
1. Always run migrations after deployment
2. Include migration files in version control
3. Test migrations on staging environment first
4. Use database backup before major migrations

### 4. Static Files Not Serving

**Problem**: CSS, JS, and other static files return 404 errors

**Common Causes**:
- `collectStatic: false` in liara.json
- Incorrect `STATIC_ROOT` configuration
- Missing WhiteNoise middleware
- Incorrect middleware order

**Solution**:
```python
# settings.py
import os

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Must be after SecurityMiddleware
    # ... other middleware
]
```

**Prevention**:
- Always enable `collectStatic` in liara.json
- Use WhiteNoise for static file serving
- Test static files locally with `python manage.py collectstatic`

### 5. CORS Configuration Errors

**Problem**: Frontend cannot access backend API due to CORS errors

**Common Mistakes**:
```python
# ❌ Wrong configurations
CORS_ALLOW_ALL_ORIGINS = True  # Security risk
CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]  # Only localhost
```

**Correct Configuration**:
```python
# ✅ Proper CORS setup
CORS_ALLOWED_ORIGINS = []
if os.environ.get('CORS_ALLOWED_ORIGINS'):
    CORS_ALLOWED_ORIGINS.extend(
        os.environ.get('CORS_ALLOWED_ORIGINS').split(',')
    )

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False

# Ensure middleware is first
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be first
    # ... other middleware
]
```

**Prevention**:
- Never use `CORS_ALLOW_ALL_ORIGINS = True` in production
- Use environment variables for CORS origins
- Test CORS with actual frontend domain

## React Frontend Pitfalls

### 1. Build Process Failures

**Problem**: Build fails during deployment on Liara

**Common Causes**:
- Warnings treated as errors in CI environment
- Missing dependencies
- Environment variables not available during build
- Memory issues during build

**Symptoms**:
```
Treating warnings as errors because process.env.CI = true
npm ERR! code ELIFECYCLE
```

**Solution**:
```json
{
  "build": {
    "command": "CI=false npm run build",
    "output": "build"
  }
}
```

**Alternative Solutions**:
```bash
# Fix warnings instead of ignoring them
npm run build 2>&1 | grep -v "warning"

# Increase memory for build
NODE_OPTIONS="--max-old-space-size=4096" npm run build
```

**Prevention**:
- Fix all ESLint warnings before deployment
- Test build process locally
- Monitor build logs for memory issues

### 2. Environment Variables Not Working

**Problem**: Environment variables are undefined in React app

**Common Mistakes**:
- Variables don't start with `REACT_APP_`
- Variables set after build process
- Variables not available in production environment

**Symptoms**:
```javascript
console.log(process.env.API_BASE_URL); // undefined
console.log(process.env.REACT_APP_API_BASE_URL); // works
```

**Solution**:
```bash
# .env.production - All variables must start with REACT_APP_
REACT_APP_API_BASE_URL=https://api.yourdomain.com/api/v1
REACT_APP_FRONTEND_URL=https://yourdomain.com
```

**Prevention**:
- Always prefix custom variables with `REACT_APP_`
- Test environment variables in build process
- Document all required environment variables

### 3. SPA Routing Issues

**Problem**: Direct URL access returns 404 errors

**Symptoms**:
- Homepage loads fine
- Navigation within app works
- Direct access to `/dashboard` returns 404
- Browser refresh on any route except `/` fails

**Common Cause**: Missing SPA configuration

**Solution**:
```json
{
  "static": {
    "spa": true,
    "errorDocument": "index.html"
  }
}
```

**Prevention**:
- Always set `spa: true` for React Router apps
- Test direct URL access after deployment
- Use `BrowserRouter` instead of `HashRouter`

### 4. API Connection Failures

**Problem**: Frontend cannot connect to backend API

**Common Causes**:
- Incorrect API URLs in environment variables
- CORS not configured on backend
- HTTPS/HTTP protocol mismatch
- Network connectivity issues

**Symptoms**:
```javascript
// Network errors in browser console
Failed to load resource: net::ERR_NAME_NOT_RESOLVED
Access to XMLHttpRequest blocked by CORS policy
```

**Solution**:
```javascript
// Ensure correct API configuration
const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
  timeout: 10000,
  withCredentials: true,
});

// Add error handling
apiClient.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);
```

**Prevention**:
- Test API connectivity before deployment
- Verify CORS configuration on backend
- Use HTTPS consistently in production

### 5. Large Bundle Size Issues

**Problem**: Application loads slowly due to large bundle size

**Symptoms**:
- Slow initial page load
- High bandwidth usage
- Poor performance on mobile devices

**Common Causes**:
- No code splitting implemented
- Large dependencies included in main bundle
- Unused code not tree-shaken
- Large images not optimized

**Solution**:
```javascript
// Implement code splitting
import { lazy, Suspense } from 'react';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Profile = lazy(() => import('./pages/Profile'));

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/profile" element={<Profile />} />
      </Routes>
    </Suspense>
  );
}
```

**Prevention**:
- Implement code splitting from the start
- Regularly analyze bundle size
- Optimize images and assets
- Remove unused dependencies

## General Liara Platform Pitfalls

### 1. Domain Configuration Issues

**Problem**: Custom domain not working or SSL certificate issues

**Common Mistakes**:
- Incorrect DNS configuration
- CNAME pointing to wrong target
- SSL certificate not properly configured
- Mixed HTTP/HTTPS content

**DNS Configuration Errors**:
```dns
# ❌ Wrong
Type: A
Name: api
Value: 192.168.1.1  # Random IP

# ✅ Correct
Type: CNAME
Name: api
Value: your-backend-app.liara.run
```

**Solution**:
1. Verify DNS configuration with DNS lookup tools
2. Wait for DNS propagation (up to 48 hours)
3. Check SSL certificate status in Liara dashboard
4. Test domain accessibility from different locations

**Prevention**:
- Use DNS testing tools before going live
- Document DNS configuration
- Monitor SSL certificate expiration

### 2. Resource Limit Exceeded

**Problem**: Application crashes or becomes unresponsive due to resource limits

**Symptoms**:
```
Error: Process killed due to memory limit
Application restarted due to resource constraints
```

**Common Causes**:
- Memory leaks in application
- Inefficient database queries
- Large file uploads
- High concurrent user load

**Solution**:
```python
# Django - Optimize database queries
from django.db import connection

def debug_queries():
    print(f"Number of queries: {len(connection.queries)}")
    for query in connection.queries:
        print(query['sql'])

# React - Optimize memory usage
useEffect(() => {
  return () => {
    // Cleanup subscriptions, timers, etc.
  };
}, []);
```

**Prevention**:
- Monitor resource usage regularly
- Implement proper cleanup in components
- Optimize database queries
- Use pagination for large datasets

### 3. Deployment Rollback Issues

**Problem**: Need to rollback deployment but no proper rollback strategy

**Common Scenarios**:
- New deployment breaks production
- Database migration fails
- Critical bug discovered after deployment

**Solution**:
```bash
# Liara CLI rollback (if available)
liara rollback --app your-app-name --version previous

# Manual rollback process
git revert HEAD
git push origin main
liara deploy --app your-app-name
```

**Prevention**:
1. Always test in staging environment first
2. Keep database backups before migrations
3. Implement feature flags for gradual rollouts
4. Monitor application health after deployment

### 4. Log Management Issues

**Problem**: Cannot debug issues due to insufficient logging

**Common Issues**:
- Logs not accessible or searchable
- Important information not logged
- Log retention period too short
- No structured logging format

**Solution**:
```python
# Django - Proper logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'myapp': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

**Prevention**:
- Implement structured logging from the start
- Log important business events
- Use appropriate log levels
- Regularly review and clean up logs

## Security Pitfalls

### 1. Exposed Sensitive Information

**Problem**: Sensitive data exposed in logs, environment variables, or client-side code

**Common Mistakes**:
- API keys in React environment variables
- Database credentials in logs
- Debug mode enabled in production
- Sensitive data in error messages

**Prevention**:
```python
# Django - Never expose sensitive data
if not DEBUG:
    # Hide sensitive information in production
    LOGGING['loggers']['django']['level'] = 'WARNING'
    
# Never put secrets in React environment variables
# ❌ Wrong
REACT_APP_SECRET_KEY=your-secret-key

# ✅ Correct - handle on backend
REACT_APP_API_BASE_URL=https://api.yourdomain.com
```

### 2. Insufficient Input Validation

**Problem**: Application vulnerable to injection attacks

**Common Issues**:
- No input sanitization
- SQL injection vulnerabilities
- XSS vulnerabilities
- CSRF protection disabled

**Solution**:
```python
# Django - Use built-in protections
from django.utils.html import escape
from django.core.validators import validate_email

def clean_input(data):
    return escape(data)

# React - Sanitize user input
import DOMPurify from 'dompurify';

const sanitizeHtml = (html) => {
  return DOMPurify.sanitize(html);
};
```

**Prevention**:
- Always validate and sanitize user input
- Use parameterized queries
- Enable CSRF protection
- Implement proper authentication and authorization

## Performance Pitfalls

### 1. Database Performance Issues

**Problem**: Slow database queries affecting application performance

**Common Causes**:
- N+1 query problems
- Missing database indexes
- Inefficient query patterns
- No query optimization

**Solution**:
```python
# Django - Optimize queries
from django.db import models

class PostQuerySet(models.QuerySet):
    def with_author(self):
        return self.select_related('author')
    
    def with_comments(self):
        return self.prefetch_related('comments')

class Post(models.Model):
    objects = PostQuerySet.as_manager()
    
# Usage
posts = Post.objects.with_author().with_comments()
```

**Prevention**:
- Use Django Debug Toolbar in development
- Monitor database query performance
- Add appropriate database indexes
- Use select_related and prefetch_related

### 2. Frontend Performance Issues

**Problem**: Slow frontend performance affecting user experience

**Common Causes**:
- Large bundle sizes
- Unnecessary re-renders
- No image optimization
- Blocking JavaScript

**Solution**:
```javascript
// React - Optimize performance
import { memo, useMemo, useCallback } from 'react';

const ExpensiveComponent = memo(({ data }) => {
  const processedData = useMemo(() => {
    return data.map(item => processItem(item));
  }, [data]);
  
  const handleClick = useCallback((id) => {
    // Handle click
  }, []);
  
  return (
    <div>
      {processedData.map(item => (
        <Item key={item.id} data={item} onClick={handleClick} />
      ))}
    </div>
  );
});
```

**Prevention**:
- Implement React.memo for expensive components
- Use useMemo and useCallback appropriately
- Optimize images and assets
- Implement lazy loading

## Troubleshooting Checklist

### Pre-Deployment Checklist

**Backend (Django)**:
- [ ] All environment variables documented and set
- [ ] Database migrations tested
- [ ] Static files collection works
- [ ] CORS configuration tested
- [ ] Security settings configured
- [ ] Health check endpoint implemented

**Frontend (React)**:
- [ ] Build process works locally
- [ ] Environment variables properly prefixed
- [ ] SPA routing configured
- [ ] API connectivity tested
- [ ] Bundle size optimized
- [ ] Error boundaries implemented

### Post-Deployment Checklist

**Immediate Checks**:
- [ ] Application starts without errors
- [ ] Health check endpoint responds
- [ ] Database connectivity works
- [ ] Static files serve correctly
- [ ] API endpoints accessible
- [ ] CORS working properly

**Extended Checks**:
- [ ] User registration and login work
- [ ] All major user flows function
- [ ] Performance is acceptable
- [ ] Error handling works properly
- [ ] Monitoring and logging active

### Common Debugging Commands

```bash
# Check application logs
liara logs --app your-app-name --tail

# Access application shell
liara shell --app your-app-name

# Check environment variables
liara env --app your-app-name

# Restart application
liara restart --app your-app-name

# Check deployment status
liara status --app your-app-name
```

## Prevention Strategies

### 1. Staging Environment

- Always test in staging before production
- Use production-like data and configuration
- Test all deployment procedures in staging
- Validate performance under load

### 2. Monitoring and Alerting

- Implement health checks
- Monitor application performance
- Set up error tracking
- Monitor resource usage

### 3. Documentation

- Document all configuration settings
- Maintain deployment procedures
- Keep troubleshooting guides updated
- Document all environment variables

### 4. Automated Testing

- Implement unit and integration tests
- Test deployment procedures
- Validate configuration changes
- Test rollback procedures

This comprehensive guide helps avoid the most common pitfalls when deploying applications on Liara platform and provides solutions for when issues do occur.