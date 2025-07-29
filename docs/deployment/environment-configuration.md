# Environment Configuration Guide for TikTrue Platform

This comprehensive guide covers all environment variables, configuration templates, and database setup for both frontend and backend deployments on Liara.

## Overview

The TikTrue platform requires specific environment configurations for:
- **Backend (Django)**: Database connections, security settings, CORS configuration
- **Frontend (React)**: API endpoints, build settings, feature flags
- **Database (PostgreSQL)**: Connection strings, performance settings

## Backend Environment Configuration

### Required Environment Variables

#### Core Django Settings

| Variable | Description | Required | Example Value |
|----------|-------------|----------|---------------|
| `SECRET_KEY` | Django cryptographic signing key | ✅ | `django-insecure-abc123...` |
| `DEBUG` | Debug mode (False for production) | ✅ | `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | ✅ | `api.tiktrue.com,tiktrue-backend.liara.run` |
| `DATABASE_URL` | PostgreSQL connection string | ✅ | `postgresql://user:pass@host:5432/db` |

#### CORS Configuration

| Variable | Description | Required | Example Value |
|----------|-------------|----------|---------------|
| `CORS_ALLOWED_ORIGINS` | Frontend domains for CORS | ✅ | `https://tiktrue.com,https://www.tiktrue.com` |
| `CORS_ALLOW_CREDENTIALS` | Allow credentials in CORS | ⚠️ | `True` |
| `CORS_ALLOW_ALL_ORIGINS` | Allow all origins (dev only) | ❌ | `False` |

#### Security Settings

| Variable | Description | Required | Example Value |
|----------|-------------|----------|---------------|
| `SECURE_SSL_REDIRECT` | Force HTTPS redirect | ⚠️ | `True` |
| `SECURE_HSTS_SECONDS` | HSTS max-age in seconds | ⚠️ | `31536000` |
| `SESSION_COOKIE_SECURE` | Secure session cookies | ⚠️ | `True` |
| `CSRF_COOKIE_SECURE` | Secure CSRF cookies | ⚠️ | `True` |

#### Optional Settings

| Variable | Description | Required | Example Value |
|----------|-------------|----------|---------------|
| `DJANGO_LOG_LEVEL` | Logging level | ❌ | `INFO` |
| `EMAIL_HOST` | SMTP server for emails | ❌ | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | ❌ | `587` |
| `EMAIL_USE_TLS` | Use TLS for email | ❌ | `True` |
| `EMAIL_HOST_USER` | SMTP username | ❌ | `noreply@tiktrue.com` |
| `EMAIL_HOST_PASSWORD` | SMTP password | ❌ | `app-password` |

### Backend Environment Templates

#### Production Environment (.env.production)

```bash
# Django Core Settings
SECRET_KEY=your-production-secret-key-here
DEBUG=False
ALLOWED_HOSTS=api.tiktrue.com,tiktrue-backend.liara.run

# Database Configuration (automatically provided by Liara)
DATABASE_URL=postgresql://username:password@host:port/database_name

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://tiktrue.com,https://www.tiktrue.com
CORS_ALLOW_CREDENTIALS=True

# Security Settings
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Logging
DJANGO_LOG_LEVEL=INFO

# Email Configuration (Optional)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@tiktrue.com
EMAIL_HOST_PASSWORD=your-app-password

# Static Files
STATIC_ROOT=/app/staticfiles
STATIC_URL=/static/
```

#### Development Environment (.env.development)

```bash
# Django Core Settings
SECRET_KEY=django-insecure-development-key-only
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# Database Configuration (Local PostgreSQL or SQLite)
DATABASE_URL=postgresql://postgres:password@localhost:5432/tiktrue_dev
# Or for SQLite: DATABASE_URL=sqlite:///db.sqlite3

# CORS Configuration (Allow local development)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_CREDENTIALS=True
CORS_ALLOW_ALL_ORIGINS=False

# Security Settings (Relaxed for development)
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# Logging
DJANGO_LOG_LEVEL=DEBUG

# Email Configuration (Console backend for development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

#### Testing Environment (.env.testing)

```bash
# Django Core Settings
SECRET_KEY=django-insecure-testing-key-only
DEBUG=False
ALLOWED_HOSTS=testserver,localhost

# Database Configuration (In-memory SQLite)
DATABASE_URL=sqlite:///:memory:

# CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:3000
CORS_ALLOW_CREDENTIALS=True

# Security Settings (Disabled for testing)
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# Logging
DJANGO_LOG_LEVEL=WARNING

# Email Configuration (Locmem backend for testing)
EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend
```

### Liara Environment Variables Setup

#### Via Liara Dashboard

1. Go to [Liara Console](https://console.liara.ir/)
2. Navigate to your backend app: `tiktrue-backend`
3. Go to **Settings** → **Environment Variables**
4. Add each variable individually:

```
SECRET_KEY = your-generated-secret-key
DEBUG = False
ALLOWED_HOSTS = api.tiktrue.com,tiktrue-backend.liara.run
CORS_ALLOWED_ORIGINS = https://tiktrue.com,https://www.tiktrue.com
DJANGO_LOG_LEVEL = INFO
```

#### Via Liara CLI

```bash
# Set individual environment variables
liara env set SECRET_KEY="your-secret-key" --app tiktrue-backend
liara env set DEBUG="False" --app tiktrue-backend
liara env set ALLOWED_HOSTS="api.tiktrue.com,tiktrue-backend.liara.run" --app tiktrue-backend
liara env set CORS_ALLOWED_ORIGINS="https://tiktrue.com,https://www.tiktrue.com" --app tiktrue-backend

# List all environment variables
liara env --app tiktrue-backend

# Remove an environment variable
liara env unset VARIABLE_NAME --app tiktrue-backend
```

#### Via liara.json

```json
{
  "platform": "django",
  "app": "tiktrue-backend",
  "environments": {
    "SECRET_KEY": "REQUIRED",
    "DEBUG": "False",
    "ALLOWED_HOSTS": "api.tiktrue.com,tiktrue-backend.liara.run",
    "CORS_ALLOWED_ORIGINS": "https://tiktrue.com,https://www.tiktrue.com",
    "DJANGO_LOG_LEVEL": "INFO"
  }
}
```

**Note**: `DATABASE_URL` is automatically provided by Liara when you add a PostgreSQL database.

## Frontend Environment Configuration

### Required Environment Variables

#### API Configuration

| Variable | Description | Required | Example Value |
|----------|-------------|----------|---------------|
| `REACT_APP_API_BASE_URL` | Backend API base URL | ✅ | `https://api.tiktrue.com/api/v1` |
| `REACT_APP_BACKEND_URL` | Backend base URL | ✅ | `https://api.tiktrue.com` |
| `REACT_APP_FRONTEND_URL` | Frontend URL | ✅ | `https://tiktrue.com` |

#### Build Configuration

| Variable | Description | Required | Example Value |
|----------|-------------|----------|---------------|
| `GENERATE_SOURCEMAP` | Generate source maps | ⚠️ | `false` (production) |
| `INLINE_RUNTIME_CHUNK` | Inline runtime chunk | ⚠️ | `false` |
| `CI` | Continuous Integration mode | ❌ | `false` |

#### Application Settings

| Variable | Description | Required | Example Value |
|----------|-------------|----------|---------------|
| `REACT_APP_ENVIRONMENT` | Environment identifier | ⚠️ | `production` |
| `REACT_APP_DEBUG` | Debug mode | ❌ | `false` |
| `REACT_APP_VERSION` | App version | ❌ | `1.0.0` |

#### Optional Features

| Variable | Description | Required | Example Value |
|----------|-------------|----------|---------------|
| `REACT_APP_ENABLE_ANALYTICS` | Enable analytics | ❌ | `true` |
| `REACT_APP_API_TIMEOUT` | API timeout (ms) | ❌ | `10000` |
| `REACT_APP_DEFAULT_THEME` | Default theme | ❌ | `light` |
| `REACT_APP_ENABLE_DARK_MODE` | Enable dark mode | ❌ | `true` |

### Frontend Environment Templates

#### Production Environment (.env.production)

```bash
# API Configuration
REACT_APP_API_BASE_URL=https://api.tiktrue.com/api/v1
REACT_APP_BACKEND_URL=https://api.tiktrue.com
REACT_APP_FRONTEND_URL=https://tiktrue.com

# Build Configuration
GENERATE_SOURCEMAP=false
INLINE_RUNTIME_CHUNK=false
CI=false

# Application Settings
REACT_APP_ENVIRONMENT=production
REACT_APP_DEBUG=false
REACT_APP_VERSION=1.0.0

# Feature Flags
REACT_APP_ENABLE_ANALYTICS=true
REACT_APP_ENABLE_DARK_MODE=true

# Performance Settings
REACT_APP_API_TIMEOUT=10000

# UI Configuration
REACT_APP_DEFAULT_THEME=light
REACT_APP_SITE_NAME=TikTrue
```

#### Development Environment (.env.development)

```bash
# API Configuration (Local backend)
REACT_APP_API_BASE_URL=http://localhost:8000/api/v1
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_FRONTEND_URL=http://localhost:3000

# Build Configuration
GENERATE_SOURCEMAP=true
FAST_REFRESH=true

# Application Settings
REACT_APP_ENVIRONMENT=development
REACT_APP_DEBUG=true
REACT_APP_VERSION=dev

# Feature Flags
REACT_APP_ENABLE_ANALYTICS=false
REACT_APP_ENABLE_DARK_MODE=true

# Development Settings
REACT_APP_API_TIMEOUT=30000
ESLINT_NO_DEV_ERRORS=true
```

#### Staging Environment (.env.staging)

```bash
# API Configuration (Staging backend)
REACT_APP_API_BASE_URL=https://staging-api.tiktrue.com/api/v1
REACT_APP_BACKEND_URL=https://staging-api.tiktrue.com
REACT_APP_FRONTEND_URL=https://staging.tiktrue.com

# Build Configuration
GENERATE_SOURCEMAP=false
INLINE_RUNTIME_CHUNK=false

# Application Settings
REACT_APP_ENVIRONMENT=staging
REACT_APP_DEBUG=false
REACT_APP_VERSION=staging

# Feature Flags
REACT_APP_ENABLE_ANALYTICS=false
REACT_APP_ENABLE_DARK_MODE=true

# Performance Settings
REACT_APP_API_TIMEOUT=15000
```

### Liara Frontend Environment Setup

#### Via liara.json (Recommended)

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
    "REACT_APP_ENVIRONMENT": "production",
    "REACT_APP_DEBUG": "false",
    "REACT_APP_ENABLE_ANALYTICS": "true"
  }
}
```

#### Via Liara CLI

```bash
# Set frontend environment variables
liara env set REACT_APP_API_BASE_URL="https://api.tiktrue.com/api/v1" --app tiktrue-frontend
liara env set REACT_APP_BACKEND_URL="https://api.tiktrue.com" --app tiktrue-frontend
liara env set REACT_APP_FRONTEND_URL="https://tiktrue.com" --app tiktrue-frontend
liara env set GENERATE_SOURCEMAP="false" --app tiktrue-frontend

# List frontend environment variables
liara env --app tiktrue-frontend
```

## Database Configuration

### PostgreSQL Configuration on Liara

#### Database Creation

1. **Via Liara Dashboard**:
   - Go to your backend app in Liara console
   - Navigate to **Databases** tab
   - Click **Add Database**
   - Select **PostgreSQL**
   - Choose plan (Small, Medium, Large)
   - Wait for database creation

2. **Via Liara CLI**:
```bash
# Create PostgreSQL database
liara db create --name tiktrue-db --type postgresql --plan small --app tiktrue-backend

# List databases
liara db list --app tiktrue-backend

# Get database info
liara db info --name tiktrue-db --app tiktrue-backend
```

#### Database Connection Configuration

The `DATABASE_URL` is automatically provided by Liara in this format:
```
postgresql://username:password@host:port/database_name
```

Example:
```
postgresql://tiktrue_user:secure_password@db.liara.ir:5432/tiktrue_production
```

#### Django Database Settings

In `settings.py`, the database is configured using `dj-database-url`:

```python
import dj_database_url

# Database configuration
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Database connection pooling (optional)
DATABASES['default']['OPTIONS'] = {
    'MAX_CONNS': 20,
    'MIN_CONNS': 5,
}
```

#### Database Performance Settings

```python
# In settings.py
DATABASES = {
    'default': {
        # ... other settings
        'OPTIONS': {
            'MAX_CONNS': 20,
            'MIN_CONNS': 5,
            'CONN_MAX_AGE': 600,
            'CONN_HEALTH_CHECKS': True,
            'sslmode': 'require',
        }
    }
}

# Connection pooling with django-db-pool (optional)
# pip install django-db-pool
DATABASES['default']['ENGINE'] = 'django_db_pool.backends.postgresql'
```

### Database Migration and Setup

#### Initial Database Setup

```bash
# Access app shell
liara shell --app tiktrue-backend

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load initial data (if available)
python manage.py loaddata initial_data.json

# Create cache table (if using database caching)
python manage.py createcachetable
```

#### Database Backup Configuration

```bash
# Create manual backup
liara db backup create --app tiktrue-backend

# Schedule automatic backups (via Liara dashboard)
# Go to Database → Backups → Schedule Backup
# Recommended: Daily backups with 7-day retention
```

### Local Development Database

#### PostgreSQL Local Setup

```bash
# Install PostgreSQL locally
# Windows: Download from postgresql.org
# macOS: brew install postgresql
# Ubuntu: sudo apt-get install postgresql postgresql-contrib

# Create local database
createdb tiktrue_dev

# Create user
createuser -P tiktrue_user
# Enter password when prompted

# Grant privileges
psql -c "GRANT ALL PRIVILEGES ON DATABASE tiktrue_dev TO tiktrue_user;"
```

#### Local Environment Configuration

```bash
# .env.development
DATABASE_URL=postgresql://tiktrue_user:password@localhost:5432/tiktrue_dev

# Or use SQLite for simple development
DATABASE_URL=sqlite:///db.sqlite3
```

## Environment Variable Security

### Security Best Practices

1. **Never commit environment files to version control**:
```bash
# Add to .gitignore
.env
.env.local
.env.production
.env.staging
*.env
```

2. **Use strong, unique values**:
```bash
# Generate secure Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Generate secure passwords
openssl rand -base64 32
```

3. **Rotate credentials regularly**:
```bash
# Update secret key periodically
liara env set SECRET_KEY="new-secret-key" --app tiktrue-backend
liara restart --app tiktrue-backend
```

4. **Use environment-specific values**:
```bash
# Different values for different environments
# Production: Strong, secure values
# Development: Convenient, less secure values
# Testing: Minimal, fast values
```

### Environment Variable Validation

#### Backend Validation Script

```python
# validate_env.py
import os
import sys
from django.core.management.utils import get_random_secret_key

def validate_backend_env():
    """Validate backend environment variables"""
    required_vars = [
        'SECRET_KEY',
        'DEBUG',
        'ALLOWED_HOSTS',
        'CORS_ALLOWED_ORIGINS'
    ]
    
    missing_vars = []
    warnings = []
    
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
        elif var == 'SECRET_KEY' and 'django-insecure' in value:
            warnings.append(f"{var}: Using insecure default key")
        elif var == 'DEBUG' and value.lower() == 'true':
            warnings.append(f"{var}: Debug mode enabled in production")
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        return False
    
    if warnings:
        print("⚠️  Environment variable warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    print("✅ Environment variables validated successfully")
    return True

if __name__ == "__main__":
    if not validate_backend_env():
        sys.exit(1)
```

#### Frontend Validation Script

```javascript
// validate-env.js
const requiredEnvVars = [
  'REACT_APP_API_BASE_URL',
  'REACT_APP_BACKEND_URL',
  'REACT_APP_FRONTEND_URL'
];

function validateFrontendEnv() {
  const missing = [];
  const warnings = [];
  
  requiredEnvVars.forEach(varName => {
    const value = process.env[varName];
    if (!value) {
      missing.push(varName);
    } else if (varName.includes('URL') && !value.startsWith('http')) {
      warnings.push(`${varName}: Should start with http:// or https://`);
    }
  });
  
  if (missing.length > 0) {
    console.error('❌ Missing required environment variables:');
    missing.forEach(var => console.error(`  - ${var}`));
    process.exit(1);
  }
  
  if (warnings.length > 0) {
    console.warn('⚠️  Environment variable warnings:');
    warnings.forEach(warning => console.warn(`  - ${warning}`));
  }
  
  console.log('✅ Frontend environment variables validated successfully');
}

validateFrontendEnv();
```

## Environment Configuration Checklist

### Pre-Deployment Checklist

#### Backend Environment
- [ ] `SECRET_KEY` generated and secure
- [ ] `DEBUG` set to `False` for production
- [ ] `ALLOWED_HOSTS` includes all domains
- [ ] `CORS_ALLOWED_ORIGINS` includes frontend domains
- [ ] `DATABASE_URL` configured (auto-provided by Liara)
- [ ] Security settings enabled (`SECURE_SSL_REDIRECT`, etc.)
- [ ] Email configuration (if needed)
- [ ] Logging level appropriate for environment

#### Frontend Environment
- [ ] `REACT_APP_API_BASE_URL` points to correct backend
- [ ] `REACT_APP_BACKEND_URL` matches backend domain
- [ ] `REACT_APP_FRONTEND_URL` matches frontend domain
- [ ] `GENERATE_SOURCEMAP` set to `false` for production
- [ ] Environment-specific feature flags configured
- [ ] Build optimization settings applied

#### Database Configuration
- [ ] PostgreSQL database created on Liara
- [ ] Database plan appropriate for expected load
- [ ] Backup schedule configured
- [ ] Connection pooling configured (if needed)
- [ ] SSL connection enabled

### Post-Deployment Verification

```bash
# Verify backend environment
liara shell --app tiktrue-backend
python manage.py check --deploy

# Verify frontend environment
curl https://tiktrue.com
# Check browser console for environment-related errors

# Verify database connection
liara shell --app tiktrue-backend
python manage.py dbshell
\dt  # List tables
\q   # Quit
```

## Troubleshooting Environment Issues

### Common Backend Issues

#### 1. SECRET_KEY Not Set
```bash
# Error: SECRET_KEY setting must not be empty
# Solution:
liara env set SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" --app tiktrue-backend
```

#### 2. Database Connection Failed
```bash
# Error: could not connect to server
# Check DATABASE_URL:
liara env --app tiktrue-backend | grep DATABASE_URL

# Verify database is running:
liara db list --app tiktrue-backend
```

#### 3. CORS Errors
```bash
# Error: CORS policy blocks request
# Check CORS configuration:
liara env --app tiktrue-backend | grep CORS

# Update CORS origins:
liara env set CORS_ALLOWED_ORIGINS="https://tiktrue.com,https://www.tiktrue.com" --app tiktrue-backend
```

### Common Frontend Issues

#### 1. API Calls Failing
```bash
# Check API URL configuration:
liara env --app tiktrue-frontend | grep REACT_APP_API

# Test API connectivity:
curl https://api.tiktrue.com/api/v1/
```

#### 2. Build Failures
```bash
# Check for missing environment variables:
liara logs --app tiktrue-frontend | grep -i "env\|environment"

# Verify all REACT_APP_ variables are set:
liara env --app tiktrue-frontend
```

#### 3. Runtime Errors
```bash
# Check browser console for environment-related errors
# Common issues:
# - Undefined environment variables
# - Incorrect API URLs
# - Missing feature flags
```

## Support and Resources

### Documentation Links
- [Django Environment Variables](https://docs.djangoproject.com/en/4.2/topics/settings/)
- [React Environment Variables](https://create-react-app.dev/docs/adding-custom-environment-variables/)
- [Liara Environment Variables](https://docs.liara.ir/app-deploy/environment-variables/)
- [PostgreSQL Configuration](https://docs.liara.ir/databases/postgresql/)

### Tools and Utilities
- [Django Secret Key Generator](https://djecrety.ir/)
- [Environment Variable Validator](https://github.com/theskumar/python-dotenv)
- [Database URL Parser](https://github.com/jacobian/dj-database-url)

### Emergency Contacts
- Liara Support: https://liara.ir/support
- Database Issues: [Database Administrator Contact]
- Development Team: [Team Contact Information]

---

**Last Updated**: [Current Date]
**Version**: 1.0
**Maintainer**: TikTrue Development Team