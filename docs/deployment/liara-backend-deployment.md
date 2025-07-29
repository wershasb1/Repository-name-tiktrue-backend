# TikTrue Backend Deployment Guide for Liara

This comprehensive guide covers deploying the TikTrue Django backend to Liara platform with PostgreSQL database.

## Prerequisites

### Required Tools
- [Liara CLI](https://docs.liara.ir/cli/install) installed and configured
- Python 3.11+ for local testing
- Git for version control

### Required Accounts
- Liara account with sufficient credits
- Domain registrar access (for custom domain setup)

## Pre-Deployment Preparation

### 1. Local Environment Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables Preparation

Create a secure Django secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Save this key for later use in Liara environment variables.

### 3. Pre-Deployment Testing

```bash
# Run security checks
python manage.py check --deploy

# Test migrations
python manage.py makemigrations --dry-run
python manage.py migrate --run-syncdb

# Collect static files
python manage.py collectstatic --noinput

# Run tests (if available)
python manage.py test
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
# Create new Django app
liara create --name tiktrue-backend --platform django

# Or use existing app
liara app list
```

### Step 3: Configure liara.json

Ensure your `backend/liara.json` contains:

```json
{
  "platform": "django",
  "app": "tiktrue-backend",
  "django": {
    "mirror": true,
    "pythonVersion": "3.11",
    "timezone": "Asia/Tehran",
    "compileMessages": false,
    "modifySettings": true,
    "geospatial": false,
    "collectStatic": true
  },
  "build": {
    "buildCommand": "pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate --noinput"
  },
  "healthCheck": {
    "path": "/health/",
    "timeout": 30
  },
  "port": 8000,
  "environments": {
    "SECRET_KEY": "REQUIRED",
    "DEBUG": "False",
    "DATABASE_URL": "REQUIRED",
    "CORS_ALLOWED_ORIGINS": "https://tiktrue.com,https://www.tiktrue.com",
    "ALLOWED_HOSTS": "api.tiktrue.com,tiktrue-backend.liara.run"
  }
}
```

### Step 4: Set Environment Variables

In Liara dashboard:

1. Go to your app: https://console.liara.ir/apps/tiktrue-backend
2. Navigate to **Settings** → **Environment Variables**
3. Add the following variables:

```env
SECRET_KEY=your-generated-secret-key-from-step-2
DEBUG=False
ALLOWED_HOSTS=api.tiktrue.com,tiktrue-backend.liara.run
CORS_ALLOWED_ORIGINS=https://tiktrue.com,https://www.tiktrue.com
DJANGO_LOG_LEVEL=INFO
```

**Note**: `DATABASE_URL` will be automatically provided by Liara when you add a PostgreSQL database.

### Step 5: Add PostgreSQL Database

1. In Liara dashboard, go to your app
2. Navigate to **Databases** tab
3. Click **Add Database**
4. Select **PostgreSQL**
5. Choose appropriate plan (e.g., "Small" for development)
6. Wait for database creation (2-3 minutes)
7. The `DATABASE_URL` will be automatically added to your environment variables

### Step 6: Deploy Application

```bash
# Deploy from backend directory
cd backend
liara deploy

# Monitor deployment
liara logs --follow
```

### Step 7: Post-Deployment Setup

```bash
# Access app shell
liara shell --app tiktrue-backend

# Run migrations (if not done in build)
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files (if needed)
python manage.py collectstatic --noinput

# Exit shell
exit
```

## Domain Configuration

### Step 1: Add Custom Domain

```bash
# Add custom domain
liara domain add api.tiktrue.com --app tiktrue-backend

# Verify domain status
liara domain list --app tiktrue-backend
```

### Step 2: DNS Configuration

In your domain registrar (e.g., Namecheap, GoDaddy):

1. Add CNAME record:
   - **Name**: `api`
   - **Value**: `tiktrue-backend.liara.run`
   - **TTL**: 300 (5 minutes)

2. Wait for DNS propagation (5-30 minutes)

### Step 3: Verify Domain Setup

```bash
# Test domain resolution
nslookup api.tiktrue.com

# Test HTTPS access
curl -I https://api.tiktrue.com/health/
```

## SSL Certificate Setup

### Automatic SSL (Recommended)

Liara automatically provides SSL certificates for custom domains:

1. SSL certificate is automatically issued after domain verification
2. Certificate auto-renewal is handled by Liara
3. HTTPS redirect is automatically configured

### Verify SSL Configuration

```bash
# Test SSL certificate
curl -I https://api.tiktrue.com

# Check certificate details
openssl s_client -connect api.tiktrue.com:443 -servername api.tiktrue.com
```

## Post-Deployment Verification

### 1. Health Check

```bash
# Test health endpoint
curl https://api.tiktrue.com/health/

# Expected response:
# {"status": "healthy", "timestamp": "..."}
```

### 2. Admin Panel Access

```bash
# Test admin panel
curl -I https://api.tiktrue.com/admin/

# Should return 200 or 302 (redirect to login)
```

### 3. API Endpoints Testing

```bash
# Test API root
curl https://api.tiktrue.com/api/v1/

# Test authentication endpoint
curl -X POST https://api.tiktrue.com/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{}'

# Should return 400 (validation error) - endpoint is working
```

### 4. CORS Verification

```bash
# Test CORS preflight
curl -X OPTIONS https://api.tiktrue.com/api/v1/auth/login/ \
  -H "Origin: https://tiktrue.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type,Authorization"

# Should return CORS headers
```

### 5. Database Connection Test

```bash
# Access app shell
liara shell --app tiktrue-backend

# Test database connection
python manage.py dbshell
\dt  # List tables
\q   # Quit

# Test Django ORM
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.count()
>>> exit()
```

## Monitoring and Maintenance

### View Logs

```bash
# View recent logs
liara logs --app tiktrue-backend

# Follow logs in real-time
liara logs --app tiktrue-backend --follow

# View specific number of lines
liara logs --app tiktrue-backend --lines 100
```

### App Management

```bash
# Check app status
liara app list

# Restart application
liara restart --app tiktrue-backend

# Scale application (if needed)
liara scale --app tiktrue-backend --replicas 2
```

### Database Management

```bash
# Access database shell
liara shell --app tiktrue-backend
python manage.py dbshell

# Create database backup
liara db backup create --app tiktrue-backend

# List backups
liara db backup list --app tiktrue-backend
```

## Troubleshooting

### Common Issues

#### 1. Application Won't Start

**Symptoms**: App shows as "Crashed" in dashboard

**Solutions**:
```bash
# Check logs for errors
liara logs --app tiktrue-backend

# Common fixes:
# - Verify SECRET_KEY is set
# - Check DATABASE_URL is available
# - Ensure all required environment variables are set
```

#### 2. Database Connection Errors

**Symptoms**: "Database connection failed" in logs

**Solutions**:
```bash
# Verify database is running
liara db list --app tiktrue-backend

# Check DATABASE_URL format
liara env --app tiktrue-backend | grep DATABASE_URL

# Restart database if needed
liara db restart --app tiktrue-backend
```

#### 3. Static Files Not Loading

**Symptoms**: CSS/JS files return 404

**Solutions**:
```bash
# Recollect static files
liara shell --app tiktrue-backend
python manage.py collectstatic --clear --noinput

# Verify WhiteNoise configuration in settings.py
```

#### 4. CORS Errors

**Symptoms**: Frontend can't access API

**Solutions**:
```bash
# Check CORS configuration
liara env --app tiktrue-backend | grep CORS

# Update CORS_ALLOWED_ORIGINS
liara env set CORS_ALLOWED_ORIGINS="https://tiktrue.com,https://www.tiktrue.com" --app tiktrue-backend

# Restart app
liara restart --app tiktrue-backend
```

#### 5. SSL Certificate Issues

**Symptoms**: HTTPS not working or certificate errors

**Solutions**:
```bash
# Check domain status
liara domain list --app tiktrue-backend

# Verify DNS configuration
nslookup api.tiktrue.com

# Wait for certificate issuance (can take up to 24 hours)
```

### Performance Optimization

#### 1. Database Optimization

```bash
# Access database shell
liara shell --app tiktrue-backend
python manage.py dbshell

# Analyze slow queries
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;

# Create database indexes if needed
python manage.py dbshell
CREATE INDEX idx_user_email ON accounts_user(email);
```

#### 2. Application Optimization

```python
# In settings.py, add caching
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}

# Create cache table
python manage.py createcachetable
```

#### 3. Static Files Optimization

```python
# In settings.py, configure static files compression
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Enable gzip compression
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
```

## Security Best Practices

### 1. Environment Variables Security

- Never commit `.env` files to version control
- Use strong, unique SECRET_KEY for production
- Regularly rotate sensitive credentials
- Use environment-specific configurations

### 2. Database Security

- Use strong database passwords
- Enable database backups
- Monitor database access logs
- Implement proper user permissions

### 3. Application Security

```python
# In settings.py, ensure security settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### 4. API Security

- Implement rate limiting
- Use proper authentication and authorization
- Validate all input data
- Log security events

## Backup and Recovery

### 1. Database Backups

```bash
# Create manual backup
liara db backup create --app tiktrue-backend

# Schedule automatic backups (in Liara dashboard)
# Go to Database → Backups → Schedule Backup
```

### 2. Application Backups

```bash
# Backup application code (Git)
git push origin main

# Backup environment variables
liara env --app tiktrue-backend > backup-env-vars.txt

# Backup static files (if needed)
liara shell --app tiktrue-backend
tar -czf static-backup.tar.gz staticfiles/
```

### 3. Recovery Procedures

```bash
# Restore from database backup
liara db backup restore <backup-id> --app tiktrue-backend

# Redeploy application
liara deploy --app tiktrue-backend

# Restore environment variables
# (Manually add from backup-env-vars.txt)
```

## Scaling and Performance

### 1. Horizontal Scaling

```bash
# Scale to multiple replicas
liara scale --app tiktrue-backend --replicas 3

# Monitor performance
liara metrics --app tiktrue-backend
```

### 2. Vertical Scaling

```bash
# Upgrade to larger plan
liara plan change --app tiktrue-backend --plan large

# Monitor resource usage
liara logs --app tiktrue-backend | grep "Memory\|CPU"
```

### 3. Database Scaling

```bash
# Upgrade database plan
liara db plan change --app tiktrue-backend --plan medium

# Monitor database performance
liara db metrics --app tiktrue-backend
```

## Maintenance Schedule

### Daily
- Monitor application logs
- Check error rates
- Verify backup completion

### Weekly
- Review performance metrics
- Update dependencies (if needed)
- Check security alerts

### Monthly
- Review and rotate credentials
- Update SSL certificates (if manual)
- Performance optimization review
- Backup verification

## Support and Resources

### Liara Documentation
- [Django Deployment Guide](https://docs.liara.ir/app-deploy/django/)
- [Database Management](https://docs.liara.ir/databases/postgresql/)
- [Domain Configuration](https://docs.liara.ir/domains/)

### TikTrue Specific Resources
- Backend README: `backend/README.md`
- Deployment Checklist: `backend/DEPLOYMENT_CHECKLIST.md`
- Environment Template: `backend/.env.example`

### Emergency Contacts
- Liara Support: https://liara.ir/support
- Project Repository: [GitHub Repository URL]
- Development Team: [Team Contact Information]

---

**Last Updated**: [Current Date]
**Version**: 1.0
**Maintainer**: TikTrue Development Team