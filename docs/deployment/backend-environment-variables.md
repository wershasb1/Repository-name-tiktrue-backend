# Backend Environment Variables Configuration

## Overview

This document provides comprehensive guidance for configuring environment variables for the TikTrue Django backend deployment on Liara.

## Required Environment Variables

### 1. SECRET_KEY (Critical)

**Purpose**: Django secret key used for cryptographic signing

**Generation**:
```python
# Generate a secure secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Example**:
```bash
SECRET_KEY=django-insecure-your-generated-secret-key-here-with-50-characters
```

**Security Notes**:
- Must be unique and unpredictable
- Never use the default development key in production
- Keep this value secret and secure
- Changing this will invalidate all sessions and signed data

### 2. DEBUG (Critical)

**Purpose**: Controls Django debug mode

**Value**: `False` (must be False in production)

**Example**:
```bash
DEBUG=False
```

**Security Notes**:
- Never set to True in production
- Debug mode exposes sensitive information
- Affects error handling and static file serving

### 3. ALLOWED_HOSTS (Critical)

**Purpose**: List of allowed host/domain names for the Django application

**Format**: Comma-separated list of domains

**Example**:
```bash
ALLOWED_HOSTS=tiktrue-backend.liara.run,api.tiktrue.com,tiktrue.com,www.tiktrue.com
```

**Required Domains**:
- Your Liara subdomain: `your-app.liara.run`
- Your custom API domain: `api.yourdomain.com`
- Your main domain: `yourdomain.com`
- WWW variant: `www.yourdomain.com`

### 4. CORS_ALLOWED_ORIGINS (Critical)

**Purpose**: List of allowed origins for Cross-Origin Resource Sharing

**Format**: Comma-separated list of full URLs

**Example**:
```bash
CORS_ALLOWED_ORIGINS=https://tiktrue.com,https://www.tiktrue.com,https://tiktrue-frontend.liara.run
```

**Required Origins**:
- Your main frontend domain: `https://yourdomain.com`
- WWW variant: `https://www.yourdomain.com`
- Liara frontend subdomain: `https://your-frontend.liara.run`

**Security Notes**:
- Must use HTTPS in production
- Never include `http://` origins in production
- Be specific - avoid wildcards

## Optional Environment Variables

### 5. DATABASE_URL (Auto-provided)

**Purpose**: PostgreSQL database connection string

**Note**: Automatically provided by Liara when you create a database

**Format**:
```bash
DATABASE_URL=postgres://username:password@host:port/database_name
```

**Manual Configuration** (if needed):
```bash
DATABASE_URL=postgres://user:pass@localhost:5432/tiktrue_db
```

### 6. DJANGO_LOG_LEVEL (Optional)

**Purpose**: Controls Django logging verbosity

**Default**: `INFO`

**Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Example**:
```bash
DJANGO_LOG_LEVEL=INFO
```

### 7. Email Configuration (Optional)

**Purpose**: Email sending for password reset functionality

**Variables**:
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

**Gmail Setup**:
1. Enable 2-factor authentication
2. Generate an app-specific password
3. Use the app password, not your regular password

## Setting Environment Variables in Liara

### Method 1: Liara Dashboard

1. **Login to Liara Dashboard**
   - Go to [liara.ir](https://liara.ir)
   - Login to your account

2. **Navigate to Your App**
   - Select your Django backend app
   - Go to "Settings" tab

3. **Add Environment Variables**
   - Click "Environment Variables"
   - Add each variable:
     - Name: `SECRET_KEY`
     - Value: `your-generated-secret-key`
   - Click "Add" for each variable

4. **Restart Application**
   - After adding all variables, restart your app
   - Variables take effect after restart

### Method 2: Liara CLI

```bash
# Set individual environment variables
liara env set SECRET_KEY="your-secret-key" --app your-backend-app
liara env set DEBUG="False" --app your-backend-app
liara env set ALLOWED_HOSTS="your-domains" --app your-backend-app

# List current environment variables
liara env list --app your-backend-app

# Remove an environment variable
liara env unset VARIABLE_NAME --app your-backend-app
```

## Environment Variables Validation

### Using the Setup Script

```bash
# Navigate to backend directory
cd backend

# Run the environment setup script
python setup_environment.py
```

**Script Features**:
- Generates secure SECRET_KEY
- Validates current environment variables
- Provides configuration template
- Shows missing or problematic variables

### Manual Validation

**Check Required Variables**:
```python
import os

required_vars = ['SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'CORS_ALLOWED_ORIGINS']
for var in required_vars:
    value = os.environ.get(var)
    if not value:
        print(f"❌ Missing: {var}")
    else:
        print(f"✅ Set: {var}")
```

### Health Check Validation

After setting environment variables, verify using the health check endpoint:

```bash
curl https://api.yourdomain.com/health/
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": 1640995200.0,
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "configuration": {
      "status": "healthy",
      "debug_mode": false,
      "secret_key_configured": true,
      "allowed_hosts": true
    },
    "cors": {
      "status": "healthy",
      "origins_configured": true,
      "credentials_allowed": true
    }
  },
  "response_time_ms": 45.2
}
```

## Security Best Practices

### Secret Key Security

1. **Generate Unique Keys**
   - Never reuse secret keys across environments
   - Generate new key for each deployment

2. **Key Rotation**
   - Rotate secret keys periodically
   - Plan for key rotation without service interruption

3. **Storage Security**
   - Never commit secret keys to version control
   - Use secure environment variable storage
   - Limit access to production environment variables

### Environment Separation

**Development Environment**:
```bash
SECRET_KEY=django-insecure-development-key-only
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

**Production Environment**:
```bash
SECRET_KEY=your-secure-production-key
DEBUG=False
ALLOWED_HOSTS=api.yourdomain.com,yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Access Control

1. **Limit Access**
   - Only authorized personnel should access production environment variables
   - Use role-based access control in Liara dashboard

2. **Audit Trail**
   - Monitor changes to environment variables
   - Log access to sensitive configuration

3. **Backup Configuration**
   - Document all environment variables
   - Keep secure backup of configuration

## Troubleshooting

### Common Issues

**1. Application Won't Start**
```
ValueError: SECRET_KEY environment variable is required
```
**Solution**: Set SECRET_KEY environment variable

**2. CORS Errors**
```
Access to XMLHttpRequest blocked by CORS policy
```
**Solution**: Check CORS_ALLOWED_ORIGINS includes frontend domain

**3. Database Connection Errors**
```
django.db.utils.OperationalError: could not connect to server
```
**Solution**: Verify DATABASE_URL is set and database service is running

**4. Static Files Not Loading**
```
404 errors for CSS/JS files
```
**Solution**: Ensure collectStatic is enabled and WhiteNoise is configured

### Debugging Commands

```bash
# Check environment variables in Liara console
liara shell --app your-backend-app
echo $SECRET_KEY
echo $DEBUG
echo $ALLOWED_HOSTS

# Test Django configuration
python manage.py check --deploy

# Test database connection
python manage.py dbshell

# Check CORS configuration
curl -H "Origin: https://yourdomain.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://api.yourdomain.com/api/v1/auth/login/
```

## Environment Variables Checklist

### Pre-Deployment
- [ ] SECRET_KEY generated and secure
- [ ] DEBUG set to False
- [ ] ALLOWED_HOSTS includes all domains
- [ ] CORS_ALLOWED_ORIGINS includes frontend domains
- [ ] All variables documented and backed up

### Post-Deployment
- [ ] Health check endpoint returns healthy status
- [ ] No environment variable warnings in logs
- [ ] CORS working from frontend
- [ ] Database connection successful
- [ ] Application starts without errors

### Security Audit
- [ ] No secrets in version control
- [ ] Environment variables properly secured
- [ ] Access limited to authorized personnel
- [ ] Regular security reviews scheduled

This comprehensive guide ensures proper configuration of all environment variables for secure and reliable backend deployment on Liara.