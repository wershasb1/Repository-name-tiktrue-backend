# Frontend Configuration Guide

## Overview

This document provides comprehensive guidance for configuring the TikTrue React frontend for deployment on Liara's static platform.

## Liara Configuration

### Enhanced liara.json Configuration

**File**: `frontend/liara.json`

```json
{
  "platform": "static",
  "app": "tiktrue-frontend",
  "build": {
    "command": "CI=false npm run build",
    "output": "build"
  },
  "static": {
    "spa": true,
    "gzip": true,
    "cache": {
      "static": "1y",
      "html": "0",
      "json": "1h",
      "images": "1M"
    },
    "headers": {
      "X-Frame-Options": "DENY",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "X-XSS-Protection": "1; mode=block"
    }
  },
  "port": 80
}
```

### Configuration Explanation

**Platform Settings**:
- `platform: "static"` - Uses Liara's static hosting platform
- `app: "tiktrue-frontend"` - Application name on Liara

**Build Configuration**:
- `command: "CI=false npm run build"` - Prevents build failures from warnings
- `output: "build"` - Specifies build output directory

**Static Hosting Settings**:
- `spa: true` - Enables Single Page Application routing
- `gzip: true` - Enables gzip compression for better performance

**Caching Strategy**:
- `static: "1y"` - Cache static assets for 1 year
- `html: "0"` - Don't cache HTML files (for updates)
- `json: "1h"` - Cache JSON files for 1 hour
- `images: "1M"` - Cache images for 1 month

**Security Headers**:
- `X-Frame-Options: "DENY"` - Prevents clickjacking
- `X-Content-Type-Options: "nosniff"` - Prevents MIME sniffing
- `Referrer-Policy` - Controls referrer information
- `X-XSS-Protection` - Enables XSS filtering

## Package.json Configuration

### Enhanced Build Scripts

```json
{
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "build:production": "NODE_ENV=production react-scripts build",
    "build:analyze": "npm run build && npx serve -s build -l 3000",
    "test": "react-scripts test",
    "test:coverage": "react-scripts test --coverage --watchAll=false",
    "eject": "react-scripts eject"
  }
}
```

**Script Purposes**:
- `build:production` - Explicit production build
- `build:analyze` - Build and serve locally for testing
- `test:coverage` - Run tests with coverage report

### Dependencies Management

**Production Dependencies**:
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.8.1",
    "react-scripts": "5.0.1",
    "axios": "^1.3.4",
    "react-hook-form": "^7.43.5",
    "react-hot-toast": "^2.4.0",
    "lucide-react": "^0.263.1",
    "framer-motion": "^10.12.4"
  }
}
```

**Development Dependencies**:
```json
{
  "devDependencies": {
    "tailwindcss": "^3.2.7",
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.21"
  }
}
```

**Key Points**:
- All runtime dependencies in `dependencies`
- Build tools in `devDependencies`
- Versions pinned for consistency

## SPA Routing Configuration

### React Router Setup

**File**: `frontend/src/App.js`

```javascript
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/features" element={<FeaturesPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        } />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Router>
  );
}
```

**Key Configuration Points**:
- Use `BrowserRouter` for clean URLs
- Include catch-all route (`*`) for 404 handling
- Implement protected routes for authentication
- Ensure `spa: true` in liara.json for proper routing

### Route Protection

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
```

## Build Process Optimization

### Build Configuration

**Environment Variables for Build**:
```bash
# Disable source maps in production
GENERATE_SOURCEMAP=false

# Disable runtime chunk inlining
INLINE_RUNTIME_CHUNK=false

# Set Node environment
NODE_ENV=production
```

**Build Command Optimization**:
```bash
# Standard build
npm run build

# Production build with explicit environment
NODE_ENV=production npm run build

# Build with CI environment disabled (prevents warnings from failing build)
CI=false npm run build
```

### Bundle Optimization

**Code Splitting Implementation**:
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

**Bundle Analysis**:
```bash
# Analyze bundle size
npm run build:analyze

# Or use webpack-bundle-analyzer
npx webpack-bundle-analyzer build/static/js/*.js
```

## Static File Serving

### File Structure

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

### Caching Strategy

**Cache Headers Configuration**:
```json
{
  "static": {
    "cache": {
      "static": "1y",      // CSS, JS, images with hashes
      "html": "0",         // HTML files (for updates)
      "json": "1h",        // API responses, manifests
      "images": "1M"       // Images without hashes
    }
  }
}
```

**Benefits**:
- Long-term caching for hashed assets
- Immediate updates for HTML files
- Balanced caching for other resources

## Performance Optimization

### Image Optimization

```javascript
// Optimized image loading
const OptimizedImage = ({ src, alt, ...props }) => (
  <img
    src={src}
    alt={alt}
    loading="lazy"
    decoding="async"
    {...props}
  />
);

// WebP support with fallback
const WebPImage = ({ src, alt, ...props }) => (
  <picture>
    <source srcSet={`${src}.webp`} type="image/webp" />
    <img src={`${src}.jpg`} alt={alt} {...props} />
  </picture>
);
```

### CSS Optimization

**Tailwind CSS Configuration**:
```javascript
// tailwind.config.js
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      // Custom configurations
    },
  },
  plugins: [],
}
```

**PostCSS Configuration**:
```javascript
// postcss.config.js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

### JavaScript Optimization

**React Performance**:
```javascript
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

## Security Configuration

### Content Security Policy

```html
<!-- In public/index.html -->
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  connect-src 'self' https://api.tiktrue.com;
  font-src 'self' https://fonts.gstatic.com;
">
```

### Security Headers

**Configured in liara.json**:
```json
{
  "headers": {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "1; mode=block"
  }
}
```

### Input Sanitization

```javascript
// utils/sanitization.js
import DOMPurify from 'dompurify';

export const sanitizeHtml = (html) => {
  return DOMPurify.sanitize(html);
};

export const validateInput = (input) => {
  // Remove potentially dangerous characters
  return input.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
};
```

## Error Handling

### Error Boundaries

```javascript
// components/ErrorBoundary.js
import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-fallback">
          <h2>Something went wrong.</h2>
          <button onClick={() => this.setState({ hasError: false })}>
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

### Global Error Handling

```javascript
// utils/errorHandler.js
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error);
  // Send to error tracking service
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  // Send to error tracking service
});
```

## Testing Configuration

### Test Scripts

```json
{
  "scripts": {
    "test": "react-scripts test",
    "test:coverage": "react-scripts test --coverage --watchAll=false",
    "test:ci": "CI=true react-scripts test --coverage --watchAll=false"
  }
}
```

### Test Configuration

```javascript
// setupTests.js
import '@testing-library/jest-dom';

// Mock environment variables
process.env.REACT_APP_API_BASE_URL = 'http://localhost:8000/api/v1';
```

## Deployment Validation

### Pre-Deployment Checks

```bash
# Build locally
npm run build

# Test build locally
npx serve -s build -l 3000

# Run tests
npm test

# Check for vulnerabilities
npm audit

# Analyze bundle
npm run build:analyze
```

### Post-Deployment Validation

```bash
# Check website loads
curl -I https://tiktrue.com

# Test SPA routing
curl -I https://tiktrue.com/dashboard

# Verify security headers
curl -I https://tiktrue.com | grep -E "(X-Frame-Options|X-Content-Type-Options)"

# Test API connectivity
curl https://tiktrue.com/api/health
```

This comprehensive configuration guide ensures optimal frontend deployment on Liara with proper performance, security, and reliability.