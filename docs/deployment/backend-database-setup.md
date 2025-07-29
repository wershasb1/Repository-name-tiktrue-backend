# Backend Database Configuration and Setup

## Overview

This document provides comprehensive guidance for setting up and managing the PostgreSQL database for the TikTrue Django backend on Liara platform.

## Database Architecture

### Database Service on Liara

**Database Type**: PostgreSQL 13+
**Connection**: Automatic via DATABASE_URL environment variable
**Backup**: Automatic daily backups by Liara
**SSL**: Enabled by default

### Django Database Configuration

The Django settings are configured to automatically use PostgreSQL in production:

```python
# Database configuration in settings.py
if os.environ.get('DATABASE_URL'):
    # Production database (PostgreSQL on Liara)
    import dj_database_url
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

**Configuration Features**:
- **Connection Pooling**: `conn_max_age=600` (10 minutes)
- **Health Checks**: `conn_health_checks=True`
- **Automatic Fallback**: SQLite for development

## Database Setup Process

### 1. Create Database Service in Liara

**Via Liara Dashboard**:
1. Login to Liara dashboard
2. Go to "Databases" section
3. Click "Create Database"
4. Select PostgreSQL
5. Choose plan and region
6. Set database name: `tiktrue_db`
7. Create database

**Via Liara CLI**:
```bash
# Create PostgreSQL database
liara database create --name tiktrue-db --type postgresql --plan small

# Get database connection info
liara database list
```

### 2. Connect Database to Django App

**In Liara Dashboard**:
1. Go to your Django app settings
2. Navigate to "Environment Variables"
3. DATABASE_URL should be automatically set
4. If not, add it manually from database connection info

**Manual DATABASE_URL Format**:
```bash
DATABASE_URL=postgres://username:password@host:port/database_name
```

### 3. Run Database Setup

**Method 1: Using Setup Script**
```bash
# SSH into your Liara app
liara shell --app your-backend-app

# Run the database setup script
python setup_database.py
```

**Method 2: Using Django Management Commands**
```bash
# SSH into your Liara app
liara shell --app your-backend-app

# Run production setup command
python manage.py setup_production

# Or run individual commands
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

**Method 3: Manual Setup**
```bash
# Create and run migrations
python manage.py makemigrations accounts
python manage.py makemigrations licenses
python manage.py makemigrations models_api
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser
```

## Database Schema

### Core Tables

**Django System Tables**:
- `django_migrations` - Migration history
- `django_admin_log` - Admin actions log
- `django_content_type` - Content types
- `auth_permission` - Permissions
- `auth_group` - User groups

**Authentication Tables**:
- `accounts_user` - Custom user model
- `auth_user_groups` - User group relationships
- `auth_user_user_permissions` - User permissions

**Application Tables**:
- `licenses_license` - License management
- `models_api_model` - Model information
- `django_session` - User sessions

### Custom User Model

```python
# accounts/models.py
class User(AbstractUser):
    email = models.EmailField(unique=True)
    subscription_plan = models.CharField(max_length=20, default='free')
    max_clients = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Key Features**:
- Email-based authentication
- Subscription plan tracking
- Client limit management
- Timestamp tracking

## Database Management

### Health Checks

**Using Management Command**:
```bash
# Basic health check
python manage.py check_database

# Detailed health check
python manage.py check_database --detailed
```

**Using Health Endpoint**:
```bash
curl https://api.yourdomain.com/health/
```

**Expected Response**:
```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    }
  },
  "response_time_ms": 45.2
}
```

### Migrations Management

**Creating Migrations**:
```bash
# Create migrations for specific app
python manage.py makemigrations accounts

# Create migrations for all apps
python manage.py makemigrations

# Show migration status
python manage.py showmigrations
```

**Running Migrations**:
```bash
# Run all pending migrations
python manage.py migrate

# Run migrations for specific app
python manage.py migrate accounts

# Fake migration (mark as applied without running)
python manage.py migrate --fake accounts 0001
```

**Migration Best Practices**:
1. Always create migrations in development first
2. Test migrations on staging environment
3. Backup database before major migrations
4. Review migration SQL before applying

### Database Backup and Recovery

**Liara Automatic Backups**:
- Daily automatic backups
- 7-day retention period
- Point-in-time recovery available

**Manual Backup**:
```bash
# Create manual backup
liara database backup --name tiktrue-db

# List available backups
liara database backup list --name tiktrue-db

# Restore from backup
liara database restore --name tiktrue-db --backup backup-id
```

**Database Export/Import**:
```bash
# Export database
pg_dump $DATABASE_URL > backup.sql

# Import database
psql $DATABASE_URL < backup.sql
```

## Performance Optimization

### Connection Pooling

**Current Configuration**:
```python
DATABASES = {
    'default': dj_database_url.parse(
        os.environ.get('DATABASE_URL'),
        conn_max_age=600,  # 10 minutes
        conn_health_checks=True,
    )
}
```

**Advanced Connection Pooling** (if needed):
```python
# Using django-db-pool
DATABASES = {
    'default': {
        'ENGINE': 'django_db_pool.backends.postgresql',
        'NAME': 'database_name',
        'USER': 'username',
        'PASSWORD': 'password',
        'HOST': 'host',
        'PORT': 'port',
        'OPTIONS': {
            'MAX_CONNS': 20,
            'MIN_CONNS': 5,
        }
    }
}
```

### Query Optimization

**Database Indexes**:
```python
# In models.py
class User(AbstractUser):
    email = models.EmailField(unique=True, db_index=True)
    subscription_plan = models.CharField(max_length=20, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['subscription_plan', 'created_at']),
        ]
```

**Query Optimization**:
```python
# Use select_related for foreign keys
users = User.objects.select_related('profile').all()

# Use prefetch_related for many-to-many
users = User.objects.prefetch_related('groups').all()

# Use only() to limit fields
users = User.objects.only('email', 'username').all()
```

### Database Monitoring

**Performance Metrics**:
```python
# In views or management commands
from django.db import connection

def get_query_stats():
    return {
        'query_count': len(connection.queries),
        'queries': connection.queries
    }
```

**Slow Query Monitoring**:
```python
# Add to settings.py for development
if DEBUG:
    LOGGING['loggers']['django.db.backends'] = {
        'level': 'DEBUG',
        'handlers': ['console'],
    }
```

## Security Configuration

### Database Security

**Connection Security**:
- SSL/TLS encryption enabled by default
- Connection via secure DATABASE_URL
- No direct database access from outside Liara

**Access Control**:
```python
# Database user permissions
DATABASES = {
    'default': {
        # ... connection settings
        'OPTIONS': {
            'sslmode': 'require',
        }
    }
}
```

**Data Protection**:
```python
# Sensitive data encryption
from django.contrib.auth.hashers import make_password

# Password hashing
password = make_password('user_password')

# Sensitive field encryption (if needed)
from cryptography.fernet import Fernet
key = Fernet.generate_key()
cipher = Fernet(key)
encrypted_data = cipher.encrypt(b"sensitive_data")
```

## Troubleshooting

### Common Database Issues

**1. Connection Refused**
```
django.db.utils.OperationalError: could not connect to server
```
**Solutions**:
- Check DATABASE_URL is set correctly
- Verify database service is running
- Check network connectivity

**2. Migration Errors**
```
django.db.utils.ProgrammingError: relation does not exist
```
**Solutions**:
- Run migrations: `python manage.py migrate`
- Check migration dependencies
- Reset migrations if necessary

**3. Permission Denied**
```
django.db.utils.OperationalError: permission denied for table
```
**Solutions**:
- Check database user permissions
- Verify DATABASE_URL credentials
- Contact Liara support if needed

**4. Too Many Connections**
```
django.db.utils.OperationalError: too many connections
```
**Solutions**:
- Reduce connection pool size
- Check for connection leaks
- Upgrade database plan if needed

### Debugging Commands

**Database Shell Access**:
```bash
# Django database shell
python manage.py dbshell

# Direct PostgreSQL access
psql $DATABASE_URL
```

**Database Inspection**:
```sql
-- List all tables
\dt

-- Describe table structure
\d accounts_user

-- Check table sizes
SELECT schemaname,tablename,attname,n_distinct,correlation FROM pg_stats;

-- Check active connections
SELECT * FROM pg_stat_activity;
```

**Django Database Commands**:
```bash
# Show SQL for migrations
python manage.py sqlmigrate accounts 0001

# Show current database state
python manage.py showmigrations

# Validate models
python manage.py check

# Database shell with Django models
python manage.py shell
```

## Maintenance Procedures

### Regular Maintenance Tasks

**Daily**:
- Monitor database health endpoint
- Check for failed queries in logs
- Verify backup completion

**Weekly**:
- Review slow query logs
- Check database size and growth
- Update statistics and analyze tables

**Monthly**:
- Review and optimize queries
- Check for unused indexes
- Plan for capacity scaling

### Database Scaling

**Vertical Scaling**:
- Upgrade database plan in Liara dashboard
- Monitor performance after upgrade
- Adjust connection pool settings

**Query Optimization**:
- Add database indexes for frequent queries
- Optimize Django ORM usage
- Implement caching where appropriate

### Disaster Recovery

**Backup Strategy**:
1. Automatic daily backups by Liara
2. Manual backups before major changes
3. Export critical data regularly
4. Test restore procedures

**Recovery Procedures**:
1. Identify the issue and scope
2. Stop application if necessary
3. Restore from appropriate backup
4. Verify data integrity
5. Resume application operations

This comprehensive guide ensures proper database setup, management, and maintenance for the TikTrue backend on Liara platform.