# TikTrue Platform Troubleshooting Guide

This comprehensive guide covers common deployment issues, debugging procedures, and solutions for the TikTrue platform on Liara.

## Quick Diagnosis Checklist

When experiencing issues, run through this quick checklist:

### Backend Issues
- [ ] Check app status: `liara app list`
- [ ] Check logs: `liara logs --app tiktrue-backend --tail`
- [ ] Verify environment variables: `liara env --app tiktrue-backend`
- [ ] Test health endpoint: `curl https://api.tiktrue.com/health/`
- [ ] Check database connection: `liara db list --app tiktrue-backend`

### Frontend Issues
- [ ] Check app status: `liara app list`
- [ ] Check build logs: `liara logs --app tiktrue-frontend`
- [ ] Test website access: `curl -I https://tiktrue.com`
- [ ] Check browser console for errors
- [ ] Verify API connectivity from browser

### Connectivity Issues
- [ ] Test DNS resolution: `nslookup tiktrue.com`
- [ ] Check SSL certificates: `curl -I https://tiktrue.com`
- [ ] Test CORS: Browser network tab
- [ ] Verify domain configuration in Liara dashboard

## Backend Troubleshooting

### 1. Application Won't Start

#### Symptoms
- App shows as "Crashed" in Liara dashboard
- Health endpoint returns 502/503 errors
- Logs show startup errors

#### Common Causes & Solutions

**Missing SECRET_KEY**
```bash
# Error in logs:
# django.core.exceptions.ImproperlyConfigured: The SECRET_KEY setting must not be empty

# Solution:
liara env set SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" --app tiktrue-backend
liara restart --app tiktrue-backend
```

**Database Connection Failed**
```bash
# Error in logs:
# django.db.utils.OperationalError: could not connect to server

# Check database status:
liara db list --app tiktrue-backend

# Verify DATABASE_URL:
liara env --app tiktrue-backend | grep DATABASE_URL

# If database is down, restart it:
liara db restart --app tiktrue-backend
```

**Import Errors**
```bash
# Error in logs:
# ModuleNotFoundError: No module named 'some_module'

# Check requirements.txt:
cat backend/requirements.txt

# Redeploy to reinstall dependencies:
liara deploy --app tiktrue-backend
```

**Settings Configuration Error**
```bash
# Error in logs:
# django.core.exceptions.ImproperlyConfigured

# Check Django settings:
liara shell --app tiktrue-backend
python manage.py check --deploy

# Common fixes:
liara env set DEBUG="False" --app tiktrue-backend
liara env set ALLOWED_HOSTS="api.tiktrue.com,tiktrue-backend.liara.run" --app tiktrue-backend
```

### 2. Database Connection Issues

#### Symptoms
- Database connection timeouts
- "Too many connections" errors
- Slow query performance

#### Debugging Steps

**Check Database Status**
```bash
# List databases
liara db list --app tiktrue-backend

# Check database metrics
liara db metrics --app tiktrue-backend

# Access database shell
liara shell --app tiktrue-backend
python manage.py dbshell
```

**Connection Pool Issues**
```bash
# Check active connections
SELECT count(*) FROM pg_stat_activity;

# Check connection limits
SELECT setting FROM pg_settings WHERE name = 'max_connections';

# Kill idle connections (if needed)
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND state_change < now() - interval '5 minutes';
```

**Solutions**
```python
# In settings.py, optimize connection settings:
DATABASES['default']['OPTIONS'] = {
    'MAX_CONNS': 10,  # Reduce if too many connections
    'MIN_CONNS': 2,
    'CONN_MAX_AGE': 300,  # Reduce connection age
}
```

### 3. Static Files Not Loading

#### Symptoms
- CSS/JS files return 404 errors
- Admin panel has no styling
- Static files not found

#### Solutions

**Recollect Static Files**
```bash
liara shell --app tiktrue-backend
python manage.py collectstatic --clear --noinput
exit

# Or redeploy (collectstatic runs automatically)
liara deploy --app tiktrue-backend
```

**Check WhiteNoise Configuration**
```python
# In settings.py, ensure WhiteNoise is configured:
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Must be here
    # ... other middleware
]

STATIC_ROOT = '/app/staticfiles'
STATIC_URL = '/static/'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

### 4. CORS Errors

#### Symptoms
- Frontend can't access backend API
- Browser console shows CORS errors
- Preflight requests failing

#### Debugging CORS

**Test CORS Configuration**
```bash
# Test preflight request
curl -X OPTIONS https://api.tiktrue.com/api/v1/auth/login/ \
  -H "Origin: https://tiktrue.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type,Authorization" \
  -v

# Check CORS headers in response
curl -H "Origin: https://tiktrue.com" https://api.tiktrue.com/api/v1/auth/ -v
```

**Fix CORS Configuration**
```bash
# Update CORS settings
liara env set CORS_ALLOWED_ORIGINS="https://tiktrue.com,https://www.tiktrue.com" --app tiktrue-backend
liara env set CORS_ALLOW_CREDENTIALS="True" --app tiktrue-backend
liara restart --app tiktrue-backend
```

**Verify Django CORS Settings**
```python
# In settings.py:
CORS_ALLOWED_ORIGINS = [
    "https://tiktrue.com",
    "https://www.tiktrue.com",
]
CORS_ALLOW_CREDENTIALS = True

# Ensure CorsMiddleware is first:
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    # ... other middleware
]
```

### 5. SSL/HTTPS Issues

#### Symptoms
- SSL certificate errors
- Mixed content warnings
- HTTPS redirects not working

#### Solutions

**Check SSL Certificate**
```bash
# Test SSL certificate
openssl s_client -connect api.tiktrue.com:443 -servername api.tiktrue.com

# Check certificate expiration
echo | openssl s_client -connect api.tiktrue.com:443 -servername api.tiktrue.com 2>/dev/null | openssl x509 -noout -dates
```

**Fix SSL Configuration**
```python
# In settings.py:
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

**Domain Configuration Issues**
```bash
# Check domain status
liara domain list --app tiktrue-backend

# Verify DNS configuration
nslookup api.tiktrue.com

# If certificate not issued, wait up to 24 hours or contact Liara support
```

## Frontend Troubleshooting

### 1. Build Failures

#### Symptoms
- Deployment fails during build process
- "Build failed" in Liara logs
- npm/yarn errors

#### Common Build Issues

**Dependency Installation Failures**
```bash
# Check build logs
liara logs --app tiktrue-frontend | grep -E "(npm|yarn|install)"

# Common solutions:
# 1. Clear npm cache
npm cache clean --force

# 2. Delete node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# 3. Use legacy peer deps
npm install --legacy-peer-deps
```

**ESLint Errors Blocking Build**
```bash
# Error: Build failed due to ESLint warnings

# Solution 1: Fix ESLint errors
npm run lint

# Solution 2: Disable ESLint errors in CI (temporary)
# Add to liara.json:
{
  "environments": {
    "CI": "false",
    "ESLINT_NO_DEV_ERRORS": "true"
  }
}
```

**Memory Issues During Build**
```bash
# Error: JavaScript heap out of memory

# Solution: Increase Node.js memory limit
# Add to package.json scripts:
{
  "scripts": {
    "build": "NODE_OPTIONS='--max-old-space-size=4096' react-scripts build"
  }
}
```

**Environment Variable Issues**
```bash
# Error: Environment variable not defined

# Check environment variables in liara.json:
{
  "environments": {
    "REACT_APP_API_BASE_URL": "https://api.tiktrue.com/api/v1",
    "REACT_APP_BACKEND_URL": "https://api.tiktrue.com",
    "REACT_APP_FRONTEND_URL": "https://tiktrue.com"
  }
}
```

### 2. SPA Routing Issues

#### Symptoms
- Direct URLs return 404 errors
- Page refresh shows "Not Found"
- React Router not working

#### Solutions

**Configure SPA Routing in Liara**
```json
// In liara.json:
{
  "platform": "react",
  "spa": true,
  "static": {
    "spa": {
      "index": "index.html"
    }
  }
}
```

**Check React Router Configuration**
```javascript
// Ensure using BrowserRouter, not HashRouter
import { BrowserRouter as Router } from 'react-router-dom';

function App() {
  return (
    <Router>
      {/* Your routes */}
    </Router>
  );
}
```

**Test SPA Routing**
```bash
# Test direct URL access
curl -I https://tiktrue.com/login
curl -I https://tiktrue.com/dashboard

# Should return 200, not 404
```

### 3. API Connectivity Issues

#### Symptoms
- API calls fail from frontend
- Network errors in browser console
- CORS errors

#### Debugging API Connectivity

**Check API Configuration**
```javascript
// In browser console, check environment variables:
console.log(process.env.REACT_APP_API_BASE_URL);
console.log(process.env.REACT_APP_BACKEND_URL);

// Test API connectivity:
fetch(process.env.REACT_APP_API_BASE_URL + '/auth/')
  .then(response => console.log('API Status:', response.status))
  .catch(error => console.error('API Error:', error));
```

**Test API from Command Line**
```bash
# Test API endpoints
curl https://api.tiktrue.com/api/v1/auth/
curl https://api.tiktrue.com/health/

# Test CORS
curl -X OPTIONS https://api.tiktrue.com/api/v1/auth/login/ \
  -H "Origin: https://tiktrue.com" \
  -H "Access-Control-Request-Method: POST"
```

**Fix API Configuration**
```bash
# Update frontend environment variables
liara env set REACT_APP_API_BASE_URL="https://api.tiktrue.com/api/v1" --app tiktrue-frontend
liara env set REACT_APP_BACKEND_URL="https://api.tiktrue.com" --app tiktrue-frontend

# Redeploy frontend
liara deploy --app tiktrue-frontend
```

### 4. Performance Issues

#### Symptoms
- Slow page loading
- Large bundle sizes
- Poor performance scores

#### Solutions

**Analyze Bundle Size**
```bash
# Install bundle analyzer
npm install -g webpack-bundle-analyzer

# Analyze build
npm run build
npx webpack-bundle-analyzer build/static/js/*.js
```

**Optimize Bundle Size**
```javascript
// Implement code splitting
const LazyComponent = React.lazy(() => import('./LazyComponent'));

// Use lazy loading for routes
const Dashboard = React.lazy(() => import('./pages/DashboardPage'));

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </Suspense>
  );
}
```

**Enable Compression**
```json
// In liara.json:
{
  "static": {
    "gzip": true,
    "headers": {
      "/static/*": {
        "Cache-Control": "public, max-age=31536000, immutable"
      }
    }
  }
}
```

## Connectivity Troubleshooting

### 1. DNS Issues

#### Symptoms
- Domain doesn't resolve
- Wrong IP address returned
- Intermittent connectivity

#### Debugging DNS

**Check DNS Resolution**
```bash
# Check DNS resolution
nslookup tiktrue.com
nslookup api.tiktrue.com
nslookup www.tiktrue.com

# Check from different DNS servers
dig tiktrue.com @8.8.8.8
dig tiktrue.com @1.1.1.1

# Check DNS propagation
# Use online tools: dnschecker.org, whatsmydns.net
```

**Common DNS Issues**

**DNS Not Propagating**
```bash
# Check TTL values (should be low during setup)
dig tiktrue.com | grep -i ttl

# Clear local DNS cache
# Windows:
ipconfig /flushdns

# macOS:
sudo dscacheutil -flushcache

# Linux:
sudo systemctl restart systemd-resolved
```

**Wrong DNS Configuration**
```bash
# Verify DNS records at registrar:
# A record: @ -> 185.231.115.209
# CNAME: www -> tiktrue-frontend.liara.run
# CNAME: api -> tiktrue-backend.liara.run

# Check current DNS records
dig tiktrue.com A
dig www.tiktrue.com CNAME
dig api.tiktrue.com CNAME
```

### 2. SSL Certificate Issues

#### Symptoms
- Certificate warnings in browser
- SSL handshake failures
- Mixed content errors

#### SSL Troubleshooting

**Check Certificate Status**
```bash
# Test SSL connection
curl -I https://tiktrue.com
curl -I https://api.tiktrue.com

# Check certificate details
openssl s_client -connect tiktrue.com:443 -servername tiktrue.com

# Check certificate chain
openssl s_client -connect tiktrue.com:443 -servername tiktrue.com -showcerts
```

**Certificate Not Issued**
```bash
# Check domain verification in Liara dashboard
liara domain list --app tiktrue-frontend
liara domain list --app tiktrue-backend

# Verify DNS is correctly configured
nslookup tiktrue.com
nslookup api.tiktrue.com

# Wait for certificate issuance (up to 24 hours)
# If still not issued, contact Liara support
```

**Mixed Content Issues**
```bash
# Check for HTTP resources in HTTPS pages
curl -s https://tiktrue.com | grep -i "http://"

# Fix by updating all URLs to HTTPS or relative URLs
# In React components:
// Bad: http://api.tiktrue.com/api/v1/
// Good: https://api.tiktrue.com/api/v1/
// Better: /api/v1/ (if same domain)
```

### 3. CORS Configuration Issues

#### Symptoms
- Preflight requests failing
- CORS policy errors in browser
- API calls blocked

#### CORS Debugging

**Test CORS Configuration**
```bash
# Test preflight request
curl -X OPTIONS https://api.tiktrue.com/api/v1/auth/login/ \
  -H "Origin: https://tiktrue.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type,Authorization" \
  -v

# Expected headers in response:
# Access-Control-Allow-Origin: https://tiktrue.com
# Access-Control-Allow-Methods: POST, OPTIONS
# Access-Control-Allow-Headers: Content-Type, Authorization
# Access-Control-Allow-Credentials: true
```

**Fix CORS Issues**
```python
# Backend settings.py:
CORS_ALLOWED_ORIGINS = [
    "https://tiktrue.com",
    "https://www.tiktrue.com",
]
CORS_ALLOW_CREDENTIALS = True
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
```

## Error Message Reference

### Backend Error Messages

#### Django Errors

**ImproperlyConfigured: The SECRET_KEY setting must not be empty**
```bash
# Cause: SECRET_KEY environment variable not set
# Solution:
liara env set SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" --app tiktrue-backend
```

**OperationalError: could not connect to server**
```bash
# Cause: Database connection failed
# Solutions:
1. Check DATABASE_URL: liara env --app tiktrue-backend | grep DATABASE_URL
2. Restart database: liara db restart --app tiktrue-backend
3. Check database status: liara db list --app tiktrue-backend
```

**DisallowedHost: Invalid HTTP_HOST header**
```bash
# Cause: Domain not in ALLOWED_HOSTS
# Solution:
liara env set ALLOWED_HOSTS="api.tiktrue.com,tiktrue-backend.liara.run" --app tiktrue-backend
```

**CORS Error: Origin not allowed**
```bash
# Cause: Frontend domain not in CORS_ALLOWED_ORIGINS
# Solution:
liara env set CORS_ALLOWED_ORIGINS="https://tiktrue.com,https://www.tiktrue.com" --app tiktrue-backend
```

#### Database Errors

**too many connections for role**
```bash
# Cause: Connection pool exhausted
# Solutions:
1. Reduce connection pool size in Django settings
2. Upgrade database plan
3. Kill idle connections in database
```

**SSL connection required**
```bash
# Cause: Database requires SSL but not configured
# Solution: Add to Django settings:
DATABASES['default']['OPTIONS']['sslmode'] = 'require'
```

### Frontend Error Messages

#### Build Errors

**Module not found: Can't resolve 'module-name'**
```bash
# Cause: Missing dependency
# Solution:
npm install module-name
# Or check if import path is correct
```

**JavaScript heap out of memory**
```bash
# Cause: Insufficient memory during build
# Solution: Increase Node.js memory limit
NODE_OPTIONS='--max-old-space-size=4096' npm run build
```

#### Runtime Errors

**Failed to fetch**
```bash
# Cause: API endpoint not accessible
# Solutions:
1. Check REACT_APP_API_BASE_URL
2. Test API endpoint: curl https://api.tiktrue.com/api/v1/
3. Check CORS configuration
```

**Cannot read property of undefined**
```bash
# Cause: Environment variable not defined
# Solution: Check environment variables in liara.json
console.log(process.env.REACT_APP_API_BASE_URL);
```

## Debugging Procedures

### 1. Systematic Debugging Approach

**Step 1: Identify the Problem**
```bash
# Check app status
liara app list

# Check recent logs
liara logs --app tiktrue-backend --tail
liara logs --app tiktrue-frontend --tail

# Test basic connectivity
curl -I https://tiktrue.com
curl -I https://api.tiktrue.com
```

**Step 2: Isolate the Issue**
```bash
# Test individual components
# Backend health check:
curl https://api.tiktrue.com/health/

# Frontend accessibility:
curl https://tiktrue.com

# Database connectivity:
liara shell --app tiktrue-backend
python manage.py dbshell
```

**Step 3: Check Configuration**
```bash
# Environment variables
liara env --app tiktrue-backend
liara env --app tiktrue-frontend

# Domain configuration
liara domain list --app tiktrue-backend
liara domain list --app tiktrue-frontend

# Database status
liara db list --app tiktrue-backend
```

**Step 4: Test Fixes**
```bash
# Apply fix and test
liara restart --app tiktrue-backend
curl https://api.tiktrue.com/health/

# Monitor logs for errors
liara logs --app tiktrue-backend --follow
```

### 2. Log Analysis

**Backend Log Analysis**
```bash
# Get recent logs
liara logs --app tiktrue-backend --lines 100

# Filter for errors
liara logs --app tiktrue-backend | grep -i error

# Filter for specific issues
liara logs --app tiktrue-backend | grep -E "(database|cors|ssl)"

# Follow logs in real-time
liara logs --app tiktrue-backend --follow
```

**Frontend Log Analysis**
```bash
# Check build logs
liara logs --app tiktrue-frontend | grep -E "(build|error|fail)"

# Check deployment logs
liara logs --app tiktrue-frontend --lines 50

# Browser console errors (check manually in browser)
```

### 3. Performance Debugging

**Backend Performance**
```bash
# Check response times
curl -w "@curl-format.txt" -o /dev/null -s https://api.tiktrue.com/health/

# Create curl-format.txt:
echo "     time_namelookup:  %{time_namelookup}\n     time_connect:     %{time_connect}\n     time_appconnect:  %{time_appconnect}\n     time_pretransfer: %{time_pretransfer}\n     time_redirect:    %{time_redirect}\n     time_starttransfer: %{time_starttransfer}\n                    ----------\n     time_total:       %{time_total}\n" > curl-format.txt

# Check database performance
liara shell --app tiktrue-backend
python manage.py dbshell
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

**Frontend Performance**
```bash
# Check bundle size
npm run build
ls -lh build/static/js/

# Test page load time
curl -w "Total time: %{time_total}s\n" -o /dev/null -s https://tiktrue.com

# Use browser dev tools for detailed analysis
```

## Emergency Procedures

### 1. Service Down Emergency

**Immediate Actions**
```bash
# Check service status
liara app list

# Check for obvious errors
liara logs --app tiktrue-backend --tail
liara logs --app tiktrue-frontend --tail

# Restart services
liara restart --app tiktrue-backend
liara restart --app tiktrue-frontend

# Check health endpoints
curl https://api.tiktrue.com/health/
curl -I https://tiktrue.com
```

**If Restart Doesn't Help**
```bash
# Rollback to previous deployment (if available)
# Check deployment history in Liara dashboard

# Check database status
liara db list --app tiktrue-backend
liara db restart --app tiktrue-backend

# Contact Liara support if infrastructure issue
```

### 2. Database Emergency

**Database Connection Lost**
```bash
# Check database status
liara db list --app tiktrue-backend

# Restart database
liara db restart --app tiktrue-backend

# Check database metrics
liara db metrics --app tiktrue-backend

# If database is corrupted, restore from backup
liara db backup list --app tiktrue-backend
liara db backup restore <backup-id> --app tiktrue-backend
```

### 3. Security Incident

**SSL Certificate Compromised**
```bash
# Revoke current certificate (contact Liara support)
# Generate new certificate
# Update all references
# Monitor for unauthorized usage
```

**Unauthorized Access**
```bash
# Change all passwords immediately
# Rotate SECRET_KEY
liara env set SECRET_KEY="new-secret-key" --app tiktrue-backend

# Check access logs
liara logs --app tiktrue-backend | grep -E "(login|auth|admin)"

# Enable additional security measures
```

## Support Resources

### Liara Support
- **Support Portal**: https://liara.ir/support
- **Documentation**: https://docs.liara.ir/
- **Status Page**: https://status.liara.ir/
- **Community Forum**: https://community.liara.ir/

### Debugging Tools
- **SSL Labs**: https://www.ssllabs.com/ssltest/
- **DNS Checker**: https://dnschecker.org/
- **What's My DNS**: https://whatsmydns.net/
- **CORS Test**: https://cors-test.codehappy.dev/

### Emergency Contacts
- **Liara Support**: support@liara.ir
- **Development Team**: [Team Contact Information]
- **Database Administrator**: [DBA Contact]
- **Security Team**: [Security Contact]

### Escalation Procedures

**Level 1: Self-Service**
- Check this troubleshooting guide
- Review logs and error messages
- Try common solutions

**Level 2: Community Support**
- Search Liara community forum
- Ask questions in community
- Check documentation

**Level 3: Liara Support**
- Create support ticket
- Provide detailed error information
- Include relevant logs and configurations

**Level 4: Emergency**
- Contact Liara emergency support
- Escalate to development team
- Implement emergency procedures

---

**Last Updated**: [Current Date]
**Version**: 1.0
**Maintainer**: TikTrue Development Team