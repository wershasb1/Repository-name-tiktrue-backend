# Maintenance Procedures Documentation

## Overview

This document provides comprehensive procedures for maintaining the TikTrue platform deployed on Liara, including updates, monitoring, health checks, backup, and recovery procedures.

## Table of Contents

1. [Update Procedures](#update-procedures)
2. [Monitoring and Health Checks](#monitoring-and-health-checks)
3. [Backup Procedures](#backup-procedures)
4. [Recovery Procedures](#recovery-procedures)
5. [Performance Optimization](#performance-optimization)
6. [Security Maintenance](#security-maintenance)
7. [Scheduled Maintenance Tasks](#scheduled-maintenance-tasks)

## Update Procedures

### Backend Updates

#### Code Updates
1. **Prepare for Update**
   ```bash
   # Create backup before update
   git tag backup-$(date +%Y%m%d-%H%M%S)
   git push origin --tags
   
   # Test changes locally
   python manage.py test
   python manage.py check --deploy
   ```

2. **Deploy Backend Update**
   ```bash
   # Navigate to backend directory
   cd backend/
   
   # Deploy to Liara
   liara deploy --platform=django --port=8000
   
   # Monitor deployment logs
   liara logs --app=tiktrue-backend --follow
   ```

3. **Post-Update Verification**
   ```bash
   # Run database migrations if needed
   liara shell --app=tiktrue-backend
   python manage.py migrate
   python manage.py collectstatic --noinput
   
   # Test API endpoints
   curl -X GET https://api.tiktrue.com/api/health/
   curl -X GET https://api.tiktrue.com/api/auth/status/
   ```

#### Database Updates
1. **Migration Preparation**
   ```bash
   # Create migration files locally
   python manage.py makemigrations
   
   # Test migration on local database copy
   python manage.py migrate --dry-run
   python manage.py sqlmigrate app_name migration_number
   ```

2. **Production Migration**
   ```bash
   # Access production shell
   liara shell --app=tiktrue-backend
   
   # Backup database before migration
   pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql
   
   # Run migrations
   python manage.py migrate
   
   # Verify migration success
   python manage.py showmigrations
   ```

### Frontend Updates

#### Code Updates
1. **Prepare Frontend Update**
   ```bash
   # Navigate to frontend directory
   cd frontend/
   
   # Install dependencies and test build
   npm install
   npm run build
   npm run test
   ```

2. **Deploy Frontend Update**
   ```bash
   # Deploy to Liara
   liara deploy --platform=static --port=3000
   
   # Monitor deployment
   liara logs --app=tiktrue-frontend --follow
   ```

3. **Post-Update Verification**
   ```bash
   # Test website functionality
   curl -I https://tiktrue.com
   curl -I https://tiktrue.com/login
   curl -I https://tiktrue.com/register
   
   # Test API connectivity from frontend
   # Open browser developer tools and check network requests
   ```

### Environment Variable Updates

1. **Backend Environment Updates**
   ```bash
   # Update environment variables
   liara env:set --app=tiktrue-backend KEY=VALUE
   
   # List current environment variables
   liara env:list --app=tiktrue-backend
   
   # Restart application to apply changes
   liara restart --app=tiktrue-backend
   ```

2. **Frontend Environment Updates**
   ```bash
   # Update frontend environment variables
   liara env:set --app=tiktrue-frontend REACT_APP_KEY=VALUE
   
   # Redeploy frontend to rebuild with new variables
   liara deploy --platform=static --port=3000
   ```

## Monitoring and Health Checks

### Automated Health Checks

#### Backend Health Check Script
```bash
#!/bin/bash
# backend_health_check.sh

BACKEND_URL="https://api.tiktrue.com"
HEALTH_ENDPOINT="$BACKEND_URL/api/health/"
AUTH_ENDPOINT="$BACKEND_URL/api/auth/status/"

echo "Checking backend health..."

# Check health endpoint
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_ENDPOINT)
if [ $HEALTH_STATUS -eq 200 ]; then
    echo "✓ Health endpoint: OK"
else
    echo "✗ Health endpoint: FAILED (HTTP $HEALTH_STATUS)"
    exit 1
fi

# Check auth endpoint
AUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $AUTH_ENDPOINT)
if [ $AUTH_STATUS -eq 200 ]; then
    echo "✓ Auth endpoint: OK"
else
    echo "✗ Auth endpoint: FAILED (HTTP $AUTH_STATUS)"
    exit 1
fi

echo "Backend health check completed successfully"
```

#### Frontend Health Check Script
```bash
#!/bin/bash
# frontend_health_check.sh

FRONTEND_URL="https://tiktrue.com"

echo "Checking frontend health..."

# Check main page
MAIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $FRONTEND_URL)
if [ $MAIN_STATUS -eq 200 ]; then
    echo "✓ Main page: OK"
else
    echo "✗ Main page: FAILED (HTTP $MAIN_STATUS)"
    exit 1
fi

# Check login page
LOGIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL/login")
if [ $LOGIN_STATUS -eq 200 ]; then
    echo "✓ Login page: OK"
else
    echo "✗ Login page: FAILED (HTTP $LOGIN_STATUS)"
    exit 1
fi

echo "Frontend health check completed successfully"
```

### Manual Health Checks

#### Daily Health Check Checklist
- [ ] Website loads correctly at https://tiktrue.com
- [ ] Login functionality works
- [ ] Registration functionality works
- [ ] User dashboard loads properly
- [ ] API endpoints respond correctly
- [ ] Database connections are stable
- [ ] SSL certificates are valid
- [ ] No error messages in application logs

#### Weekly Health Check Checklist
- [ ] Review application logs for errors
- [ ] Check database performance metrics
- [ ] Verify backup procedures are working
- [ ] Test app download functionality
- [ ] Review security logs
- [ ] Check disk space usage
- [ ] Monitor response times

### Monitoring Commands

#### Application Logs
```bash
# View backend logs
liara logs --app=tiktrue-backend --lines=100

# View frontend logs
liara logs --app=tiktrue-frontend --lines=100

# Follow logs in real-time
liara logs --app=tiktrue-backend --follow

# Filter logs by level
liara logs --app=tiktrue-backend | grep ERROR
```

#### Application Status
```bash
# Check application status
liara app:list

# Get detailed app information
liara app:info --app=tiktrue-backend
liara app:info --app=tiktrue-frontend

# Check resource usage
liara metrics --app=tiktrue-backend
liara metrics --app=tiktrue-frontend
```

## Backup Procedures

### Database Backup

#### Automated Daily Backup Script
```bash
#!/bin/bash
# daily_backup.sh

BACKUP_DIR="/backups/$(date +%Y/%m)"
BACKUP_FILE="tiktrue_db_$(date +%Y%m%d_%H%M%S).sql"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create database backup
liara shell --app=tiktrue-backend --command="pg_dump \$DATABASE_URL" > "$BACKUP_DIR/$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_DIR/$BACKUP_FILE"

# Remove backups older than 30 days
find /backups -name "*.sql.gz" -mtime +30 -delete

echo "Database backup completed: $BACKUP_DIR/$BACKUP_FILE.gz"
```

#### Manual Database Backup
```bash
# Access backend shell
liara shell --app=tiktrue-backend

# Create database backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Download backup file (if needed)
# Use liara file management or SCP to download
```

### Code Backup

#### Git Repository Backup
```bash
# Create tagged backup
git tag backup-$(date +%Y%m%d-%H%M%S)
git push origin --tags

# Create archive backup
git archive --format=tar.gz --output=tiktrue_backup_$(date +%Y%m%d).tar.gz HEAD

# Backup to external repository (if configured)
git push backup-remote main --tags
```

### Configuration Backup

#### Environment Variables Backup
```bash
# Backup backend environment variables
liara env:list --app=tiktrue-backend > backend_env_backup_$(date +%Y%m%d).txt

# Backup frontend environment variables
liara env:list --app=tiktrue-frontend > frontend_env_backup_$(date +%Y%m%d).txt
```

## Recovery Procedures

### Database Recovery

#### Full Database Restore
```bash
# Access backend shell
liara shell --app=tiktrue-backend

# Stop application (if needed)
# This should be done through Liara dashboard

# Restore database from backup
psql $DATABASE_URL < backup_file.sql

# Run migrations to ensure schema is current
python manage.py migrate

# Restart application
# Use Liara dashboard to restart
```

#### Partial Data Recovery
```bash
# Access backend shell
liara shell --app=tiktrue-backend

# Connect to database
psql $DATABASE_URL

# Restore specific tables (example)
\copy users FROM 'users_backup.csv' WITH CSV HEADER;
\copy subscriptions FROM 'subscriptions_backup.csv' WITH CSV HEADER;
```

### Application Recovery

#### Backend Recovery
```bash
# Rollback to previous version
git checkout backup-tag-name

# Redeploy backend
cd backend/
liara deploy --platform=django --port=8000

# Verify recovery
curl -X GET https://api.tiktrue.com/api/health/
```

#### Frontend Recovery
```bash
# Rollback to previous version
git checkout backup-tag-name

# Redeploy frontend
cd frontend/
liara deploy --platform=static --port=3000

# Verify recovery
curl -I https://tiktrue.com
```

### Configuration Recovery

#### Environment Variables Recovery
```bash
# Restore backend environment variables
while IFS='=' read -r key value; do
    liara env:set --app=tiktrue-backend "$key=$value"
done < backend_env_backup.txt

# Restore frontend environment variables
while IFS='=' read -r key value; do
    liara env:set --app=tiktrue-frontend "$key=$value"
done < frontend_env_backup.txt

# Restart applications
liara restart --app=tiktrue-backend
liara restart --app=tiktrue-frontend
```

## Performance Optimization

### Database Optimization

#### Regular Maintenance Tasks
```sql
-- Connect to database
psql $DATABASE_URL

-- Analyze database statistics
ANALYZE;

-- Vacuum database
VACUUM;

-- Reindex if needed
REINDEX DATABASE tiktrue;

-- Check for slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

#### Index Optimization
```sql
-- Check for missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation 
FROM pg_stats 
WHERE schemaname = 'public' 
ORDER BY n_distinct DESC;

-- Create indexes for frequently queried columns
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_subscriptions_user_id ON subscriptions(user_id);
```

### Application Optimization

#### Backend Performance Tuning
```python
# Django settings optimization
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'OPTIONS': {
            'MAX_CONNS': 20,
            'CONN_MAX_AGE': 600,
        }
    }
}

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

#### Frontend Performance Optimization
```bash
# Optimize build process
npm run build -- --analyze

# Check bundle size
npm install -g webpack-bundle-analyzer
npx webpack-bundle-analyzer build/static/js/*.js
```

## Security Maintenance

### SSL Certificate Management

#### Certificate Renewal Check
```bash
# Check certificate expiration
echo | openssl s_client -servername tiktrue.com -connect tiktrue.com:443 2>/dev/null | openssl x509 -noout -dates

# Check certificate for API
echo | openssl s_client -servername api.tiktrue.com -connect api.tiktrue.com:443 2>/dev/null | openssl x509 -noout -dates
```

### Security Updates

#### Dependency Updates
```bash
# Backend dependency updates
cd backend/
pip list --outdated
pip install -U package_name

# Frontend dependency updates
cd frontend/
npm audit
npm update
npm audit fix
```

#### Security Scanning
```bash
# Backend security scan
cd backend/
pip install safety
safety check

# Frontend security scan
cd frontend/
npm audit
npm audit fix --force
```

## Scheduled Maintenance Tasks

### Daily Tasks
- [ ] Run automated health checks
- [ ] Create database backup
- [ ] Review error logs
- [ ] Check application status

### Weekly Tasks
- [ ] Review performance metrics
- [ ] Check disk space usage
- [ ] Update dependencies (if needed)
- [ ] Test backup restoration process
- [ ] Review security logs

### Monthly Tasks
- [ ] Full system health assessment
- [ ] Performance optimization review
- [ ] Security audit
- [ ] Documentation updates
- [ ] Disaster recovery testing

### Quarterly Tasks
- [ ] Comprehensive security review
- [ ] Infrastructure assessment
- [ ] Backup strategy review
- [ ] Performance benchmarking
- [ ] Documentation audit

## Emergency Procedures

### Service Outage Response
1. **Immediate Assessment**
   - Check Liara status page
   - Run health check scripts
   - Review recent deployments

2. **Quick Recovery Actions**
   - Restart applications if needed
   - Rollback recent changes if problematic
   - Switch to maintenance mode if necessary

3. **Communication**
   - Notify stakeholders
   - Update status page
   - Document incident

### Data Loss Response
1. **Stop all write operations**
2. **Assess extent of data loss**
3. **Restore from most recent backup**
4. **Verify data integrity**
5. **Resume normal operations**
6. **Post-incident review**

## Maintenance Contacts

### Technical Contacts
- **Primary Developer**: [Contact Information]
- **Database Administrator**: [Contact Information]
- **DevOps Engineer**: [Contact Information]

### Service Providers
- **Liara Support**: support@liara.ir
- **Domain Registrar**: [Contact Information]
- **SSL Certificate Provider**: [Contact Information]

## Maintenance Log Template

```
Date: [YYYY-MM-DD]
Maintenance Type: [Routine/Emergency/Update]
Performed By: [Name]
Duration: [Start Time - End Time]
Services Affected: [Backend/Frontend/Database]

Actions Taken:
- [Action 1]
- [Action 2]
- [Action 3]

Results:
- [Result 1]
- [Result 2]

Issues Encountered:
- [Issue 1 and Resolution]
- [Issue 2 and Resolution]

Next Actions:
- [Follow-up task 1]
- [Follow-up task 2]
```

---

**Note**: This maintenance procedures documentation should be reviewed and updated regularly to reflect changes in the system architecture, deployment processes, and operational requirements.