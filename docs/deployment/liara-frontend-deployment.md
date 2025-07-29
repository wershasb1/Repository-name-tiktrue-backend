# TikTrue Frontend Deployment Guide for Liara

This comprehensive guide covers deploying the TikTrue React frontend to Liara platform as a static Single Page Application (SPA).

## Prerequisites

### Required Tools
- [Liara CLI](https://docs.liara.ir/cli/install) installed and configured
- Node.js 16+ and npm for local testing
- Git for version control

### Required Accounts
- Liara account with sufficient credits
- Domain registrar access (for custom domain setup)

## Pre-Deployment Preparation

### 1. Local Environment Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Verify all dependencies are installed
npm audit
```

### 2. Environment Configuration

Create production environment file:

```bash
# Copy example environment file
cp .env.example .env.production

# Edit with production values
# REACT_APP_API_BASE_URL=https://api.tiktrue.com/api/v1
# REACT_APP_BACKEND_URL=https://api.tiktrue.com
# REACT_APP_FRONTEND_URL=https://tiktrue.com
```

### 3. Pre-Deployment Testing

```bash
# Test development build
npm start
# Verify app loads at http://localhost:3000

# Test production build
npm run build

# Serve production build locally
npx serve -s build -l 3000
# Verify app works correctly

# Run tests (if available)
npm test

# Check for security vulnerabilities
npm audit --audit-level moderate
```

### 4. Build Optimization

```bash
# Analyze bundle size
npm run build

# Check build output
ls -la build/
# Should see: index.html, static/css/, static/js/

# Verify environment variables are embedded
grep -r "REACT_APP" build/static/js/
```

## Liara Deployment Process

### Step 1: Login to Liara

```bash
# Login to Liara CLI
liara login

# Verify login
liara account
```

### Step 2: Create Liara App

```bash
# Create new static app
liara create --name tiktrue-frontend --platform static

# Or use existing app
liara app list
```

### Step 3: Configure liara.json

Ensure your `frontend/liara.json` contains:

```json
{
  "platform": "react",
  "app": "tiktrue-frontend",
  "port": 3000,
  "nodeVersion": "22",
  "environments": {
    "REACT_APP_API_BASE_URL": "https://api.tiktrue.com/api/v1",
    "REACT_APP_BACKEND_URL": "https://api.tiktrue.com",
    "REACT_APP_FRONTEND_URL": "https://tiktrue.com",
    "GENERATE_SOURCEMAP": "false",
    "REACT_APP_ENVIRONMENT": "production"
  }
}
```

**Important Configuration Notes**:
- `platform: "react"` - Uses React-optimized build process
- `port: 3000` - Standard React development port
- `nodeVersion: "22"` - Ensures compatible Node.js version
- Environment variables are embedded at build time

### Step 4: Configure Build Process

Liara will automatically:
1. Run `npm install`
2. Run `npm run build`
3. Serve files from `build/` directory
4. Configure SPA routing for React Router

### Step 5: Deploy Application

```bash
# Deploy from frontend directory
cd frontend
liara deploy

# Monitor deployment
liara logs --follow
```

### Step 6: Verify Deployment

```bash
# Check app status
liara app list

# Test default Liara URL
curl -I https://tiktrue-frontend.liara.run

# Check build logs
liara logs --app tiktrue-frontend
```

## Domain Configuration

### Step 1: Add Custom Domain

```bash
# Add custom domain
liara domain add tiktrue.com --app tiktrue-frontend

# Add www subdomain
liara domain add www.tiktrue.com --app tiktrue-frontend

# Verify domain status
liara domain list --app tiktrue-frontend
```

### Step 2: DNS Configuration

In your domain registrar (e.g., Namecheap, GoDaddy):

#### For Root Domain (tiktrue.com):
1. Add A record:
   - **Name**: `@` (or leave empty)
   - **Value**: `185.231.115.209` (Liara's IP)
   - **TTL**: 300 (5 minutes)

#### For WWW Subdomain:
1. Add CNAME record:
   - **Name**: `www`
   - **Value**: `tiktrue-frontend.liara.run`
   - **TTL**: 300 (5 minutes)

#### Alternative: CNAME for Root Domain
If your registrar supports CNAME for root domain:
1. Add CNAME record:
   - **Name**: `@`
   - **Value**: `tiktrue-frontend.liara.run`
   - **TTL**: 300 (5 minutes)

### Step 3: Verify Domain Setup

```bash
# Test domain resolution
nslookup tiktrue.com
nslookup www.tiktrue.com

# Test HTTP access (should redirect to HTTPS)
curl -I http://tiktrue.com

# Test HTTPS access
curl -I https://tiktrue.com
```

## SSL Certificate Setup

### Automatic SSL (Recommended)

Liara automatically provides SSL certificates for custom domains:

1. SSL certificate is automatically issued after domain verification
2. Certificate auto-renewal is handled by Liara
3. HTTPS redirect is automatically configured
4. HTTP/2 is enabled by default

### Configure Security Headers

Add security headers in `liara.json`:

```json
{
  "platform": "react",
  "app": "tiktrue-frontend",
  "port": 3000,
  "nodeVersion": "22",
  "static": {
    "headers": {
      "/*": {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cross-Origin-Opener-Policy": "same-origin"
      }
    },
    "redirects": [
      {
        "source": "http://tiktrue.com/*",
        "destination": "https://tiktrue.com/:splat",
        "permanent": true
      },
      {
        "source": "http://www.tiktrue.com/*",
        "destination": "https://tiktrue.com/:splat",
        "permanent": true
      },
      {
        "source": "https://www.tiktrue.com/*",
        "destination": "https://tiktrue.com/:splat",
        "permanent": true
      }
    ]
  },
  "environments": {
    "REACT_APP_API_BASE_URL": "https://api.tiktrue.com/api/v1",
    "REACT_APP_BACKEND_URL": "https://api.tiktrue.com",
    "REACT_APP_FRONTEND_URL": "https://tiktrue.com",
    "GENERATE_SOURCEMAP": "false",
    "REACT_APP_ENVIRONMENT": "production"
  }
}
```

### Verify SSL Configuration

```bash
# Test SSL certificate
curl -I https://tiktrue.com

# Check certificate details
openssl s_client -connect tiktrue.com:443 -servername tiktrue.com

# Test security headers
curl -I https://tiktrue.com | grep -E "(Strict-Transport|X-Content|X-Frame)"
```

## SPA Routing Configuration

### React Router Setup

Ensure your React app uses `BrowserRouter`:

```javascript
// src/App.js
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        {/* Other routes */}
      </Routes>
    </Router>
  );
}
```

### Liara SPA Configuration

Liara automatically configures SPA routing for React apps, but you can explicitly configure it:

```json
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

### Test SPA Routing

```bash
# Test direct URL access
curl -I https://tiktrue.com/login
curl -I https://tiktrue.com/register
curl -I https://tiktrue.com/dashboard

# All should return 200 and serve index.html
```

## Post-Deployment Verification

### 1. Basic Functionality Test

```bash
# Test homepage
curl https://tiktrue.com

# Should return HTML with React app
```

### 2. SPA Routing Test

```bash
# Test React Router routes
curl -I https://tiktrue.com/login
curl -I https://tiktrue.com/register
curl -I https://tiktrue.com/dashboard

# All should return 200 status
```

### 3. Static Assets Test

```bash
# Test CSS loading
curl -I https://tiktrue.com/static/css/main.[hash].css

# Test JavaScript loading
curl -I https://tiktrue.com/static/js/main.[hash].js

# Should return 200 with proper caching headers
```

### 4. API Connectivity Test

Open browser console at https://tiktrue.com and test:

```javascript
// Test API connectivity
fetch('https://api.tiktrue.com/api/v1/auth/')
  .then(response => console.log('API Status:', response.status))
  .catch(error => console.error('API Error:', error));

// Test CORS
fetch('https://api.tiktrue.com/api/v1/auth/login/', {
  method: 'OPTIONS',
  headers: {
    'Origin': 'https://tiktrue.com',
    'Access-Control-Request-Method': 'POST'
  }
}).then(response => console.log('CORS Status:', response.status));
```

### 5. Performance Test

```bash
# Test page load time
curl -w "@curl-format.txt" -o /dev/null -s https://tiktrue.com

# Create curl-format.txt:
echo "     time_namelookup:  %{time_namelookup}\n     time_connect:     %{time_connect}\n     time_appconnect:  %{time_appconnect}\n     time_pretransfer: %{time_pretransfer}\n     time_redirect:    %{time_redirect}\n     time_starttransfer: %{time_starttransfer}\n                    ----------\n     time_total:       %{time_total}\n" > curl-format.txt
```

## Monitoring and Maintenance

### View Logs

```bash
# View recent logs
liara logs --app tiktrue-frontend

# Follow logs in real-time
liara logs --app tiktrue-frontend --follow

# View build logs
liara logs --app tiktrue-frontend | grep -E "(npm|build)"
```

### App Management

```bash
# Check app status
liara app list

# Restart application
liara restart --app tiktrue-frontend

# View app metrics
liara metrics --app tiktrue-frontend
```

### Update Deployment

```bash
# After making changes to code
cd frontend

# Test locally
npm run build
npx serve -s build

# Deploy updates
liara deploy

# Monitor deployment
liara logs --follow
```

## Troubleshooting

### Common Issues

#### 1. Build Failures

**Symptoms**: Deployment fails during build process

**Solutions**:
```bash
# Check build logs
liara logs --app tiktrue-frontend | grep -E "(npm|build|error)"

# Common fixes:
# - Ensure all dependencies are in package.json
# - Check for ESLint errors (set CI=false if needed)
# - Verify Node.js version compatibility
# - Clear npm cache: npm cache clean --force
```

#### 2. SPA Routing Not Working

**Symptoms**: Direct URLs return 404 or don't load React components

**Solutions**:
```bash
# Verify SPA configuration in liara.json
# Ensure "spa": true is set

# Check React Router configuration
# Ensure BrowserRouter is used, not HashRouter

# Test routing locally
npx serve -s build -l 3000
```

#### 3. API Connection Issues

**Symptoms**: Frontend can't connect to backend API

**Solutions**:
```bash
# Check environment variables
liara env --app tiktrue-frontend

# Verify API URLs are correct
# Test API connectivity manually:
curl https://api.tiktrue.com/api/v1/

# Check CORS configuration on backend
curl -X OPTIONS https://api.tiktrue.com/api/v1/auth/login/ \
  -H "Origin: https://tiktrue.com"
```

#### 4. Static Files Not Loading

**Symptoms**: CSS/JS files return 404 or don't load

**Solutions**:
```bash
# Check build output
ls -la build/static/

# Verify build process completed successfully
liara logs --app tiktrue-frontend | grep "build"

# Check for build errors
npm run build
```

#### 5. SSL Certificate Issues

**Symptoms**: HTTPS not working or certificate errors

**Solutions**:
```bash
# Check domain status
liara domain list --app tiktrue-frontend

# Verify DNS configuration
nslookup tiktrue.com

# Wait for certificate issuance (can take up to 24 hours)
# Check certificate status in Liara dashboard
```

#### 6. Performance Issues

**Symptoms**: Slow page loading or poor performance

**Solutions**:
```bash
# Analyze bundle size
npm run build
ls -lh build/static/js/

# Optimize bundle size:
# - Implement code splitting
# - Use lazy loading for routes
# - Remove unused dependencies

# Enable compression in liara.json:
{
  "static": {
    "gzip": true
  }
}
```

### Performance Optimization

#### 1. Bundle Size Optimization

```bash
# Analyze bundle
npm install -g webpack-bundle-analyzer
npx webpack-bundle-analyzer build/static/js/*.js

# Implement code splitting
# In src/App.js:
const LazyComponent = React.lazy(() => import('./LazyComponent'));

# Use lazy loading for routes
const Dashboard = React.lazy(() => import('./pages/DashboardPage'));
```

#### 2. Caching Configuration

```json
{
  "static": {
    "headers": {
      "/static/*": {
        "Cache-Control": "public, max-age=31536000, immutable"
      },
      "/*.html": {
        "Cache-Control": "no-cache"
      }
    }
  }
}
```

#### 3. Image Optimization

```bash
# Optimize images before deployment
npm install -g imagemin-cli
imagemin public/images/* --out-dir=public/images/optimized

# Use WebP format for better compression
# Convert images to WebP format
```

## Security Best Practices

### 1. Environment Variables Security

- Never commit `.env` files to version control
- Use environment-specific configurations
- Avoid sensitive data in React environment variables (they're public)

### 2. Content Security Policy

```json
{
  "static": {
    "headers": {
      "/*": {
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.tiktrue.com"
      }
    }
  }
}
```

### 3. Security Headers

```json
{
  "static": {
    "headers": {
      "/*": {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp"
      }
    }
  }
}
```

### 4. Input Validation

```javascript
// Always validate user input
import DOMPurify from 'dompurify';

const sanitizedInput = DOMPurify.sanitize(userInput);
```

## Backup and Recovery

### 1. Source Code Backup

```bash
# Ensure code is in version control
git push origin main

# Tag releases
git tag -a v1.0.0 -m "Production release v1.0.0"
git push origin v1.0.0
```

### 2. Build Artifacts Backup

```bash
# Backup build directory
tar -czf build-backup-$(date +%Y%m%d).tar.gz build/

# Store in secure location
# Upload to cloud storage or backup server
```

### 3. Configuration Backup

```bash
# Backup environment variables
liara env --app tiktrue-frontend > backup-frontend-env.txt

# Backup liara.json
cp liara.json liara-backup-$(date +%Y%m%d).json
```

### 4. Recovery Procedures

```bash
# Restore from backup
# 1. Restore source code from Git
git checkout v1.0.0

# 2. Restore environment variables
# (Manually add from backup-frontend-env.txt)

# 3. Redeploy
liara deploy --app tiktrue-frontend
```

## Scaling and Performance

### 1. CDN Configuration

Liara provides built-in CDN for static files:

```json
{
  "static": {
    "cdn": true,
    "gzip": true
  }
}
```

### 2. Multiple Regions

```bash
# Deploy to multiple regions (if available)
liara deploy --app tiktrue-frontend --region iran
liara deploy --app tiktrue-frontend --region germany
```

### 3. Performance Monitoring

```javascript
// Add performance monitoring
// In src/index.js:
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

getCLS(console.log);
getFID(console.log);
getFCP(console.log);
getLCP(console.log);
getTTFB(console.log);
```

## Maintenance Schedule

### Daily
- Monitor application logs
- Check error rates in browser console
- Verify website accessibility

### Weekly
- Review performance metrics
- Check for dependency updates
- Monitor security alerts

### Monthly
- Update dependencies
- Review and optimize bundle size
- Performance optimization review
- Security audit

## Support and Resources

### Liara Documentation
- [Static App Deployment](https://docs.liara.ir/app-deploy/static/)
- [React Deployment Guide](https://docs.liara.ir/app-deploy/react/)
- [Domain Configuration](https://docs.liara.ir/domains/)

### TikTrue Specific Resources
- Frontend README: `frontend/README.md`
- Deployment Checklist: `frontend/DEPLOYMENT_CHECKLIST.md`
- Environment Template: `frontend/.env.example`

### Emergency Contacts
- Liara Support: https://liara.ir/support
- Project Repository: [GitHub Repository URL]
- Development Team: [Team Contact Information]

---

**Last Updated**: [Current Date]
**Version**: 1.0
**Maintainer**: TikTrue Development Team