# Liara Django Backend Deployment Best Practices

## Overview

This document outlines the best practices for deploying Django applications on Liara platform, based on official documentation and current project analysis.

## Liara Django Platform Configuration

### Required Files for Django Deployment

**1. liara.json Configuration**
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

**Configuration Options Explained**:
- `mirror`: Use Iranian mirror for faster package downloads (recommended for Iranian servers)
- `pythonVersion`: Specify exact Python version (must match runtime.txt)
- `timezone`: Server timezone (should match Django TIME_ZONE setting)
- `compileMessages`: Set to true if using Django internationalization
- `modifySettings`: Allow Liara to modify Django settings for production
- `geospatial`: Enable if using GeoDjango features
- `collectStatic`: Automatically run collectstatic during deployment

**2. runtime.txt**
```
python-3.10.0
```
- Must specify exact Python version
- Should match pythonVersion in liara.json
- Supported versions: 3.8, 3.9, 3.10, 3.11

**3. requirements.txt**
```
Django==4.2.7
djangorestframework==3.14.0
djangorestframework-simplejwt==5.3.0
django-cors-headers==4.3.1
dj-database-url==2.1.0
psycopg2-binary==2.9.9
whitenoise==6.6.0
gunicorn==21.2.0
```

**Essential Dependencies**:
- `dj-database-url`: For DATABASE_URL parsing
- `psycopg2-binary`: PostgreSQL adapter
- `whitenoise`: Static file serving
- `gunicorn`: WSGI server for production

## Django Settings Configuration for Liara

### Database Configuration Best Practices

```python
import os
import dj_database_url
from pathlib import Path

# Database configuration
if os.environ.get('DATABASE_URL'):
    # Production database (PostgreSQL on Liara)
    DATABASES = {
        'default': dj_database_url.parse(
            os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Development database (SQLite)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
```

**Best Practices**:
- Always use `DATABASE_URL` environment variable for production
- Add connection pooling with `conn_max_age`
- Enable health checks for better reliability
- Keep SQLite fallback for development

### Environment Variables Configuration

```python
import os

# Security settings
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")

DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Allowed hosts
ALLOWED_HOSTS = []
if os.environ.get('ALLOWED_HOSTS'):
    ALLOWED_HOSTS.extend(os.environ.get('ALLOWED_HOSTS').split(','))

# Add Liara subdomain
ALLOWED_HOSTS.extend([
    'your-app-name.liara.run',
    'your-custom-domain.com',
])
```

**Required Environment Variables**:
- `SECRET_KEY`: Django secret key (generate with `django.core.management.utils.get_random_secret_key()`)
- `DEBUG`: Should be False in production
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `DATABASE_URL`: Automatically provided by Liara

### Static Files Configuration

```python
import os

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Middleware configuration
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Must be after SecurityMiddleware
    # ... other middleware
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

**Best Practices**:
- Use WhiteNoise for static file serving
- Enable compression with CompressedManifestStaticFilesStorage
- Place WhiteNoise middleware after SecurityMiddleware
- Set proper STATIC_ROOT for collectstatic

### Security Configuration for Production

```python
import os

# Security settings for production
if not DEBUG:
    # SSL/HTTPS settings
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # HSTS settings
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Cookie security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Content security
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
```

**Security Best Practices**:
- Enable SSL redirect in production
- Configure proper proxy headers for Liara
- Set HSTS headers for security
- Secure cookies and prevent XSS

### CORS Configuration

```python
# CORS settings for API access
CORS_ALLOWED_ORIGINS = []
if os.environ.get('CORS_ALLOWED_ORIGINS'):
    CORS_ALLOWED_ORIGINS.extend(
        os.environ.get('CORS_ALLOWED_ORIGINS').split(',')
    )

# Default allowed origins for development
CORS_ALLOWED_ORIGINS.extend([
    "http://localhost:3000",
    "http://127.0.0.1:3000",
])

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False  # Never set to True in production

# CORS headers
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

**CORS Best Practices**:
- Never use CORS_ALLOW_ALL_ORIGINS = True in production
- Specify exact origins in CORS_ALLOWED_ORIGINS
- Use environment variables for different environments
- Include necessary headers for API functionality

## Liara-Specific Configuration

### Environment Variables in Liara Dashboard

**Required Variables**:
```bash
SECRET_KEY=your-generated-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-app.liara.run,your-domain.com
CORS_ALLOWED_ORIGINS=https://your-frontend.com,https://www.your-frontend.com
```

**Setting Environment Variables**:
1. Go to Liara dashboard
2. Select your Django app
3. Go to Settings → Environment Variables
4. Add each variable with proper values

### Database Setup on Liara

**Creating Database**:
1. Go to Liara dashboard
2. Create new database (PostgreSQL recommended)
3. Note the connection details
4. DATABASE_URL is automatically provided to Django app

**Running Migrations**:
```bash
# In Liara console or during deployment
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser  # Optional
```

### Custom Domain Configuration

**Steps for Custom Domain**:
1. Add domain in Liara dashboard
2. Configure DNS records:
   ```
   Type: CNAME
   Name: api (for api.yourdomain.com)
   Value: your-app.liara.run
   ```
3. Update ALLOWED_HOSTS in Django settings
4. Configure SSL certificate (automatic with Liara)

## Deployment Process Best Practices

### Pre-Deployment Checklist

- [ ] Verify all required files are present (liara.json, runtime.txt, requirements.txt)
- [ ] Test application locally with production-like settings
- [ ] Ensure all environment variables are documented
- [ ] Run security checks (`python manage.py check --deploy`)
- [ ] Test database migrations
- [ ] Verify static files collection works

### Deployment Commands

```bash
# Install Liara CLI
npm install -g @liara/cli

# Login to Liara
liara login

# Deploy application
liara deploy --app your-app-name --platform django

# Check deployment logs
liara logs --app your-app-name

# Access app console
liara shell --app your-app-name
```

### Post-Deployment Tasks

1. **Run Migrations**:
   ```bash
   python manage.py migrate
   ```

2. **Collect Static Files**:
   ```bash
   python manage.py collectstatic --noinput
   ```

3. **Create Superuser** (if needed):
   ```bash
   python manage.py createsuperuser
   ```

4. **Test API Endpoints**:
   - Test health check endpoint
   - Test authentication endpoints
   - Verify CORS configuration

## Performance Optimization

### Database Optimization

```python
# Database connection pooling
DATABASES = {
    'default': {
        # ... database config
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'MAX_CONNS': 20,
            'MIN_CONNS': 5,
        }
    }
}
```

### Caching Configuration

```python
# Redis caching (if Redis is available)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Session storage
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

### Static Files Optimization

```python
# Compression and caching
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# WhiteNoise settings
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True if DEBUG else False
WHITENOISE_MAX_AGE = 31536000  # 1 year
```

## Monitoring and Logging

### Logging Configuration

```python
import os

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
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
```

### Health Check Endpoint

```python
# views.py
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return JsonResponse({
            'status': 'healthy',
            'database': 'connected'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)
```

## Common Issues and Solutions

### Issue 1: Static Files Not Loading

**Problem**: CSS/JS files return 404 errors

**Solution**:
```python
# Ensure WhiteNoise is properly configured
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Must be here
    # ... other middleware
]

# Run collectstatic
python manage.py collectstatic --noinput
```

### Issue 2: Database Connection Errors

**Problem**: Can't connect to PostgreSQL database

**Solution**:
1. Verify DATABASE_URL environment variable is set
2. Check database service is running in Liara
3. Ensure psycopg2-binary is in requirements.txt
4. Run migrations after database setup

### Issue 3: CORS Errors

**Problem**: Frontend can't access API due to CORS

**Solution**:
```python
# Proper CORS configuration
CORS_ALLOWED_ORIGINS = [
    "https://your-frontend-domain.com",
]
CORS_ALLOW_CREDENTIALS = True

# Ensure corsheaders is first in middleware
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    # ... other middleware
]
```

### Issue 4: SSL/HTTPS Issues

**Problem**: Mixed content or SSL errors

**Solution**:
```python
# Proper SSL configuration for Liara
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_TLS = True
```

## Security Best Practices

### Environment Variables Security

- Never commit sensitive data to version control
- Use strong, randomly generated SECRET_KEY
- Rotate secrets regularly
- Use different secrets for different environments

### Database Security

- Use strong database passwords
- Enable SSL for database connections
- Regularly backup database
- Monitor database access logs

### API Security

- Implement proper authentication and authorization
- Use HTTPS for all API endpoints
- Validate all input data
- Implement rate limiting
- Log security events

## Maintenance and Updates

### Regular Maintenance Tasks

1. **Update Dependencies**:
   ```bash
   pip list --outdated
   pip install -U package-name
   ```

2. **Security Updates**:
   ```bash
   python manage.py check --deploy
   ```

3. **Database Maintenance**:
   ```bash
   python manage.py dbshell
   # Run VACUUM, ANALYZE, etc.
   ```

4. **Log Monitoring**:
   ```bash
   liara logs --app your-app-name --tail
   ```

### Backup Procedures

1. **Database Backup**:
   - Use Liara database backup features
   - Implement automated backup scripts
   - Test restore procedures regularly

2. **Static Files Backup**:
   - Backup media files regularly
   - Use cloud storage for media files
   - Implement CDN for static assets

This comprehensive guide covers all aspects of deploying Django applications on Liara platform with best practices for security, performance, and maintenance.