# Frontend Environment Variables Configuration

## Overview

This document provides comprehensive guidance for configuring environment variables for the TikTrue React frontend deployment on Liara platform.

## Environment Variables Overview

### React Environment Variables Rules

1. **Prefix Requirement**: All custom environment variables must start with `REACT_APP_`
2. **Build-Time Embedding**: Variables are embedded at build time, not runtime
3. **Public Nature**: All React environment variables are publicly accessible in the browser
4. **No Secrets**: Never put sensitive data in React environment variables

### Environment File Priority

React loads environment files in this order (higher priority overrides lower):
1. `.env.local` (loaded in all environments except test)
2. `.env.development`, `.env.production`, etc. (environment-specific)
3. `.env` (default for all environments)

## Required Environment Variables

### 1. REACT_APP_API_BASE_URL (Critical)

**Purpose**: Backend API base URL for all API calls

**Format**: Full URL including protocol and API version path

**Examples**:
```bash
# Production
REACT_APP_API_BASE_URL=https://api.tiktrue.com/api/v1

# Development
REACT_APP_API_BASE_URL=http://localhost:8000/api/v1

# Staging
REACT_APP_API_BASE_URL=https://staging-api.tiktrue.com/api/v1
```

**Usage in Code**:
```javascript
// In AuthContext.js
axios.defaults.baseURL = process.env.REACT_APP_API_BASE_URL || 'https://api.tiktrue.com/api/v1';
```

### 2. REACT_APP_BACKEND_URL (Required)

**Purpose**: Backend base URL without API path (for health checks, admin, etc.)

**Format**: Full URL including protocol, without /api/v1

**Examples**:
```bash
# Production
REACT_APP_BACKEND_URL=https://api.tiktrue.com

# Development
REACT_APP_BACKEND_URL=http://localhost:8000
```

### 3. REACT_APP_FRONTEND_URL (Required)

**Purpose**: Frontend URL for redirects, CORS, and absolute links

**Format**: Full URL including protocol

**Examples**:
```bash
# Production
REACT_APP_FRONTEND_URL=https://tiktrue.com

# Development
REACT_APP_FRONTEND_URL=http://localhost:3000
```

## Build Configuration Variables

### 4. GENERATE_SOURCEMAP (Important)

**Purpose**: Controls source map generation

**Values**: `true` or `false`

**Recommendation**:
```bash
# Development
GENERATE_SOURCEMAP=true

# Production
GENERATE_SOURCEMAP=false
```

**Security Note**: Disable in production to prevent source code exposure

### 5. INLINE_RUNTIME_CHUNK (Optional)

**Purpose**: Controls runtime chunk inlining

**Values**: `true` or `false`

**Recommendation**:
```bash
# Production (better caching)
INLINE_RUNTIME_CHUNK=false
```

## Application Configuration Variables

### 6. REACT_APP_ENVIRONMENT (Recommended)

**Purpose**: Environment identifier for conditional logic

**Values**: `development`, `staging`, `production`

**Usage**:
```javascript
const isDevelopment = process.env.REACT_APP_ENVIRONMENT === 'development';
const isProduction = process.env.REACT_APP_ENVIRONMENT === 'production';
```

### 7. REACT_APP_DEBUG (Recommended)

**Purpose**: Enable/disable debug features

**Values**: `true` or `false`

**Usage**:
```javascript
const isDebugMode = process.env.REACT_APP_DEBUG === 'true';

if (isDebugMode) {
  console.log('Debug information:', data);
}
```

## Optional Configuration Variables

### 8. REACT_APP_ENABLE_ANALYTICS (Optional)

**Purpose**: Enable/disable analytics tracking

**Values**: `true` or `false`

**Usage**:
```javascript
const analyticsEnabled = process.env.REACT_APP_ENABLE_ANALYTICS === 'true';

if (analyticsEnabled) {
  // Initialize analytics
}
```

### 9. REACT_APP_API_TIMEOUT (Optional)

**Purpose**: API request timeout in milliseconds

**Default**: 10000 (10 seconds)

**Usage**:
```javascript
const apiTimeout = parseInt(process.env.REACT_APP_API_TIMEOUT) || 10000;

const apiClient = axios.create({
  timeout: apiTimeout
});
```

### 10. REACT_APP_DEFAULT_THEME (Optional)

**Purpose**: Default UI theme

**Values**: `light`, `dark`

**Usage**:
```javascript
const defaultTheme = process.env.REACT_APP_DEFAULT_THEME || 'light';
```

## Environment File Configurations

### Development Environment

**File**: `frontend/.env.development`

```bash
# Development Environment Variables
REACT_APP_API_BASE_URL=http://localhost:8000/api/v1
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_FRONTEND_URL=http://localhost:3000

# Build settings
GENERATE_SOURCEMAP=true

# Application settings
REACT_APP_ENVIRONMENT=development
REACT_APP_DEBUG=true
REACT_APP_ENABLE_ANALYTICS=false
```

### Production Environment

**File**: `frontend/.env.production`

```bash
# Production Environment Variables
REACT_APP_API_BASE_URL=https://api.tiktrue.com/api/v1
REACT_APP_BACKEND_URL=https://api.tiktrue.com
REACT_APP_FRONTEND_URL=https://tiktrue.com

# Build settings
GENERATE_SOURCEMAP=false
INLINE_RUNTIME_CHUNK=false

# Application settings
REACT_APP_ENVIRONMENT=production
REACT_APP_DEBUG=false
REACT_APP_ENABLE_ANALYTICS=true
```

### Local Development Override

**File**: `frontend/.env.local` (not committed to git)

```bash
# Local development overrides
# This file is ignored by git and can contain developer-specific settings

# Override API URL for local backend testing
REACT_APP_API_BASE_URL=http://localhost:8000/api/v1

# Enable debug mode for local development
REACT_APP_DEBUG=true

# Disable analytics for local development
REACT_APP_ENABLE_ANALYTICS=false
```

## Environment Variable Validation

### Runtime Validation

```javascript
// utils/envValidation.js
export const validateEnvironment = () => {
  const requiredVars = [
    'REACT_APP_API_BASE_URL',
    'REACT_APP_BACKEND_URL',
    'REACT_APP_FRONTEND_URL'
  ];

  const missing = requiredVars.filter(varName => !process.env[varName]);

  if (missing.length > 0) {
    console.error('Missing required environment variables:', missing);
    throw new Error(`Missing environment variables: ${missing.join(', ')}`);
  }

  // Validate URL formats
  try {
    new URL(process.env.REACT_APP_API_BASE_URL);
    new URL(process.env.REACT_APP_BACKEND_URL);
    new URL(process.env.REACT_APP_FRONTEND_URL);
  } catch (error) {
    throw new Error('Invalid URL format in environment variables');
  }

  console.log('✅ Environment variables validated successfully');
};

// Call in index.js or App.js
validateEnvironment();
```

### Build-Time Validation

```javascript
// scripts/validate-env.js
const requiredVars = [
  'REACT_APP_API_BASE_URL',
  'REACT_APP_BACKEND_URL',
  'REACT_APP_FRONTEND_URL'
];

requiredVars.forEach(varName => {
  if (!process.env[varName]) {
    console.error(`❌ Missing required environment variable: ${varName}`);
    process.exit(1);
  }
});

console.log('✅ All required environment variables are set');
```

**Add to package.json**:
```json
{
  "scripts": {
    "prebuild": "node scripts/validate-env.js",
    "build": "react-scripts build"
  }
}
```

## Environment-Specific API Configuration

### API Client Configuration

```javascript
// api/client.js
const getApiConfig = () => {
  const environment = process.env.REACT_APP_ENVIRONMENT || 'production';
  
  const configs = {
    development: {
      baseURL: process.env.REACT_APP_API_BASE_URL,
      timeout: 30000, // Longer timeout for development
      withCredentials: true,
    },
    staging: {
      baseURL: process.env.REACT_APP_API_BASE_URL,
      timeout: 15000,
      withCredentials: true,
    },
    production: {
      baseURL: process.env.REACT_APP_API_BASE_URL,
      timeout: 10000,
      withCredentials: true,
    },
  };
  
  return configs[environment] || configs.production;
};

const apiClient = axios.create(getApiConfig());

export default apiClient;
```

### Environment-Specific Features

```javascript
// utils/features.js
export const getFeatureFlags = () => {
  const environment = process.env.REACT_APP_ENVIRONMENT;
  
  return {
    enableAnalytics: process.env.REACT_APP_ENABLE_ANALYTICS === 'true',
    enableDebugMode: process.env.REACT_APP_DEBUG === 'true',
    enableExperimentalFeatures: environment === 'development' || 
                                process.env.REACT_APP_ENABLE_EXPERIMENTAL_FEATURES === 'true',
    apiTimeout: parseInt(process.env.REACT_APP_API_TIMEOUT) || 10000,
  };
};
```

## Security Best Practices

### What NOT to Put in Environment Variables

❌ **Never include**:
- API keys or secrets
- Database credentials
- Private keys or certificates
- User passwords
- Internal system URLs
- Sensitive business logic

✅ **Safe to include**:
- Public API endpoints
- Feature flags
- UI configuration
- Public analytics IDs
- Build configuration

### Environment Variable Security

```javascript
// Example of secure environment variable usage
const config = {
  // ✅ Safe - public API endpoint
  apiBaseUrl: process.env.REACT_APP_API_BASE_URL,
  
  // ✅ Safe - public configuration
  enableAnalytics: process.env.REACT_APP_ENABLE_ANALYTICS === 'true',
  
  // ❌ Never do this - sensitive data
  // apiKey: process.env.REACT_APP_API_KEY, // This would be visible to users!
};
```

## Troubleshooting

### Common Issues

**1. Environment Variables Not Loading**
```bash
# Check if variables are properly prefixed
REACT_APP_API_URL=... # ✅ Correct
API_URL=...           # ❌ Wrong - missing REACT_APP_ prefix
```

**2. Variables Not Updating**
```bash
# Restart development server after changing variables
npm start
```

**3. Build-Time vs Runtime**
```javascript
// ❌ This won't work - variables are embedded at build time
const apiUrl = process.env['REACT_APP_API_' + 'BASE_URL'];

// ✅ This works - direct reference
const apiUrl = process.env.REACT_APP_API_BASE_URL;
```

**4. Environment File Not Loading**
- Check file naming (`.env.production`, not `.env.prod`)
- Ensure file is in project root
- Check file permissions
- Verify NODE_ENV matches environment file

### Debugging Environment Variables

```javascript
// Debug current environment variables
console.log('Environment Variables:', {
  NODE_ENV: process.env.NODE_ENV,
  REACT_APP_API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
  REACT_APP_ENVIRONMENT: process.env.REACT_APP_ENVIRONMENT,
  // Add other variables you want to check
});

// Check all REACT_APP_ variables
Object.keys(process.env)
  .filter(key => key.startsWith('REACT_APP_'))
  .forEach(key => {
    console.log(`${key}: ${process.env[key]}`);
  });
```

## Deployment Checklist

### Pre-Deployment
- [ ] All required environment variables defined
- [ ] Environment-specific files created
- [ ] Variables validated with validation script
- [ ] No sensitive data in environment variables
- [ ] Build process tested locally

### Liara Deployment
- [ ] Environment files committed to repository
- [ ] Build command configured in liara.json
- [ ] No additional environment variables needed in Liara dashboard
- [ ] Build logs checked for environment variable issues

### Post-Deployment
- [ ] Website loads without environment variable errors
- [ ] API calls use correct URLs
- [ ] Feature flags work as expected
- [ ] Debug mode disabled in production
- [ ] Analytics enabled (if configured)

This comprehensive guide ensures proper environment variable configuration for secure and reliable frontend deployment on Liara platform.