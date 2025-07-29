# Liara React Frontend Deployment Best Practices

## Overview

This document outlines the best practices for deploying React applications on Liara's static platform, based on official documentation and current project analysis.

## Liara Static Platform Configuration

### Required Files for React Deployment

**1. liara.json Configuration**
```json
{
  "platform": "static",
  "app": "your-app-name",
  "build": {
    "command": "npm run build",
    "output": "build"
  },
  "static": {
    "spa": true,
    "gzip": true,
    "cache": {
      "static": "1y",
      "html": "0"
    }
  },
  "port": 80
}
```

**Configuration Options Explained**:
- `platform`: Must be "static" for React apps
- `app`: Your application name on Liara
- `build.command`: Command to build the React app
- `build.output`: Directory containing built files
- `static.spa`: Enable Single Page Application routing
- `static.gzip`: Enable gzip compression
- `static.cache`: Cache control headers
- `port`: Port for the application (80 for HTTP, 443 for HTTPS)

**2. package.json Configuration**
```json
{
  "name": "your-react-app",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "browserslist": {
    "production": [
      ">0.2%",
      "not dead",
      "not op_mini all"
    ],
    "development": [
      "last 1 chrome version",
      "last 1 firefox version",
      "last 1 safari version"
    ]
  }
}
```

**Essential Scripts**:
- `build`: Must generate production-ready files
- Build output should go to `build/` directory by default
- Ensure all dependencies are in `dependencies`, not `devDependencies`

## Environment Variables Configuration

### Production Environment Variables

**File**: `.env.production`
```bash
# API Configuration
REACT_APP_API_BASE_URL=https://api.yourdomain.com/api/v1
REACT_APP_BACKEND_URL=https://api.yourdomain.com
REACT_APP_FRONTEND_URL=https://yourdomain.com

# Build Configuration
GENERATE_SOURCEMAP=false
INLINE_RUNTIME_CHUNK=false

# Performance
REACT_APP_ENABLE_ANALYTICS=true
REACT_APP_SENTRY_DSN=your-sentry-dsn
```

### Development Environment Variables

**File**: `.env.development`
```bash
# Local Development API
REACT_APP_API_BASE_URL=http://localhost:8000/api/v1
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_FRONTEND_URL=http://localhost:3000

# Development Settings
GENERATE_SOURCEMAP=true
REACT_APP_ENABLE_ANALYTICS=false
```

### Environment Variables Best Practices

1. **Prefix Requirement**: All custom environment variables must start with `REACT_APP_`
2. **No Secrets**: Never put sensitive data in React environment variables (they're public)
3. **Environment Separation**: Use different files for different environments
4. **Build-Time Variables**: React environment variables are embedded at build time

## Build Process Optimization

### Build Configuration

**Optimized package.json scripts**:
```json
{
  "scripts": {
    "build": "react-scripts build",
    "build:analyze": "npm run build && npx bundle-analyzer build/static/js/*.js",
    "build:production": "NODE_ENV=production npm run build"
  }
}
```

### Build Output Structure

```
build/
├── static/
│   ├── css/
│   │   ├── main.[hash].css
│   │   └── main.[hash].css.map
│   ├── js/
│   │   ├── main.[hash].js
│   │   ├── main.[hash].js.map
│   │   └── [chunk].[hash].js
│   └── media/
│       └── [assets with hashes]
├── index.html
├── manifest.json
├── robots.txt
└── favicon.ico
```

**Build Optimization Settings**:
```javascript
// In package.json or build script
{
  "build": {
    "productionSourceMap": false,
    "generateSWPrecacheFile": true
  }
}
```

## Single Page Application (SPA) Configuration

### Router Configuration

**React Router Setup**:
```javascript
// App.js
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Router>
  );
}
```

### SPA Configuration in liara.json

```json
{
  "static": {
    "spa": true,
    "errorDocument": "index.html"
  }
}
```

**SPA Best Practices**:
- Always set `spa: true` for React Router applications
- Use `BrowserRouter` instead of `HashRouter` for clean URLs
- Handle 404 errors properly with catch-all routes
- Ensure all routes serve `index.html` for client-side routing

## Performance Optimization

### Code Splitting

```javascript
// Lazy loading components
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

### Bundle Optimization

**webpack-bundle-analyzer** (for Create React App):
```bash
npm install --save-dev webpack-bundle-analyzer
npx webpack-bundle-analyzer build/static/js/*.js
```

### Image Optimization

```javascript
// Optimized image imports
import heroImage from '../assets/hero.webp';

// Lazy loading images
const LazyImage = ({ src, alt, ...props }) => {
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      {...props}
    />
  );
};
```

## Static File Serving Configuration

### Cache Control Headers

```json
{
  "static": {
    "cache": {
      "static": "1y",      // Cache static assets for 1 year
      "html": "0",         // Don't cache HTML files
      "json": "1h",        // Cache JSON files for 1 hour
      "images": "1M"       // Cache images for 1 month
    }
  }
}
```

### Compression Settings

```json
{
  "static": {
    "gzip": true,
    "brotli": true,
    "compression": {
      "level": 6,
      "threshold": 1024
    }
  }
}
```

### Custom Headers

```json
{
  "static": {
    "headers": {
      "X-Frame-Options": "DENY",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
    }
  }
}
```

## API Integration Best Practices

### Axios Configuration

```javascript
// api/client.js
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
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
  (error) => Promise.reject(error)
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

### Environment-Specific API Configuration

```javascript
// config/api.js
const getApiConfig = () => {
  const environment = process.env.NODE_ENV;
  
  const configs = {
    development: {
      baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api/v1',
      timeout: 30000, // Longer timeout for development
    },
    production: {
      baseURL: process.env.REACT_APP_API_BASE_URL,
      timeout: 10000,
    },
  };
  
  return configs[environment] || configs.production;
};

export default getApiConfig();
```

## Security Best Practices

### Content Security Policy

```javascript
// public/index.html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  connect-src 'self' https://api.yourdomain.com;
  font-src 'self' https://fonts.gstatic.com;
">
```

### Environment Variables Security

```javascript
// Never expose sensitive data
// ❌ Wrong
const API_KEY = process.env.REACT_APP_SECRET_API_KEY; // This is public!

// ✅ Correct - handle sensitive operations on backend
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL; // This is fine
```

### Input Validation

```javascript
// utils/validation.js
export const validateEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

export const sanitizeInput = (input) => {
  return input.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
};
```

## Custom Domain Configuration

### DNS Configuration

**For custom domain (e.g., yourdomain.com)**:
```
Type: CNAME
Name: @ (or www)
Value: your-app-name.liara.run
TTL: 300
```

**For subdomain (e.g., app.yourdomain.com)**:
```
Type: CNAME
Name: app
Value: your-app-name.liara.run
TTL: 300
```

### SSL Certificate Setup

1. **Automatic SSL** (recommended):
   - Liara automatically provides SSL certificates
   - No additional configuration needed
   - Certificates auto-renew

2. **Custom SSL Certificate**:
   ```json
   {
     "ssl": {
       "certificate": "path/to/certificate.crt",
       "private_key": "path/to/private.key"
     }
   }
   ```

## Deployment Process

### Pre-Deployment Checklist

- [ ] Verify build process works locally (`npm run build`)
- [ ] Test production build locally (`npx serve -s build`)
- [ ] Check environment variables are set correctly
- [ ] Verify API endpoints are accessible
- [ ] Test responsive design and cross-browser compatibility
- [ ] Run security audit (`npm audit`)
- [ ] Optimize bundle size and performance

### Deployment Commands

```bash
# Install Liara CLI
npm install -g @liara/cli

# Login to Liara
liara login

# Deploy application
liara deploy --app your-app-name --platform static

# Check deployment status
liara logs --app your-app-name

# Set custom domain
liara domain add your-domain.com --app your-app-name
```

### Automated Deployment with CI/CD

**GitHub Actions Example**:
```yaml
# .github/workflows/deploy.yml
name: Deploy to Liara

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Setup Node.js
      uses: actions/setup-node@v2
      with:
        node-version: '18'
        cache: 'npm'
    
    - name: Install dependencies
      run: npm ci
    
    - name: Build application
      run: npm run build
      env:
        REACT_APP_API_BASE_URL: ${{ secrets.API_BASE_URL }}
    
    - name: Deploy to Liara
      run: |
        npm install -g @liara/cli
        liara deploy --app your-app-name --platform static
      env:
        LIARA_TOKEN: ${{ secrets.LIARA_TOKEN }}
```

## Monitoring and Analytics

### Performance Monitoring

```javascript
// utils/performance.js
export const measurePerformance = () => {
  if ('performance' in window) {
    window.addEventListener('load', () => {
      const perfData = performance.getEntriesByType('navigation')[0];
      console.log('Page Load Time:', perfData.loadEventEnd - perfData.fetchStart);
    });
  }
};

// Web Vitals
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

getCLS(console.log);
getFID(console.log);
getFCP(console.log);
getLCP(console.log);
getTTFB(console.log);
```

### Error Tracking

```javascript
// utils/errorTracking.js
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error);
  // Send to error tracking service
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  // Send to error tracking service
});
```

## Common Issues and Solutions

### Issue 1: Routing Not Working (404 on Refresh)

**Problem**: Direct URL access returns 404

**Solution**:
```json
{
  "static": {
    "spa": true,
    "errorDocument": "index.html"
  }
}
```

### Issue 2: Environment Variables Not Working

**Problem**: Environment variables are undefined

**Solution**:
1. Ensure variables start with `REACT_APP_`
2. Restart development server after adding variables
3. Check `.env` file is in project root
4. Verify build process includes environment variables

### Issue 3: Build Fails on Liara

**Problem**: Build process fails during deployment

**Solution**:
```json
{
  "build": {
    "command": "CI=false npm run build",
    "output": "build"
  }
}
```

### Issue 4: Large Bundle Size

**Problem**: Application loads slowly due to large bundle

**Solution**:
1. Implement code splitting
2. Use lazy loading for components
3. Optimize images and assets
4. Remove unused dependencies

### Issue 5: API Calls Failing

**Problem**: Cannot connect to backend API

**Solution**:
1. Check CORS configuration on backend
2. Verify API URLs in environment variables
3. Ensure HTTPS is used for production
4. Check network tab in browser dev tools

## Performance Best Practices

### Bundle Optimization

```javascript
// webpack.config.js (if ejected)
module.exports = {
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all',
        },
      },
    },
  },
};
```

### Image Optimization

```javascript
// Use WebP format with fallback
const OptimizedImage = ({ src, alt, ...props }) => (
  <picture>
    <source srcSet={`${src}.webp`} type="image/webp" />
    <img src={`${src}.jpg`} alt={alt} {...props} />
  </picture>
);
```

### Caching Strategy

```javascript
// Service Worker for caching
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((registration) => {
        console.log('SW registered: ', registration);
      })
      .catch((registrationError) => {
        console.log('SW registration failed: ', registrationError);
      });
  });
}
```

## Maintenance and Updates

### Regular Maintenance Tasks

1. **Update Dependencies**:
   ```bash
   npm audit
   npm update
   npm outdated
   ```

2. **Performance Monitoring**:
   - Monitor bundle size
   - Check Core Web Vitals
   - Analyze user behavior

3. **Security Updates**:
   ```bash
   npm audit fix
   ```

4. **Build Optimization**:
   ```bash
   npm run build:analyze
   ```

### Backup and Recovery

1. **Source Code**: Use Git for version control
2. **Build Artifacts**: Keep build artifacts for rollback
3. **Environment Variables**: Document all environment variables
4. **Domain Configuration**: Document DNS settings

This comprehensive guide covers all aspects of deploying React applications on Liara's static platform with best practices for performance, security, and maintenance.