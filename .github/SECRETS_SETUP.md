# GitHub Secrets Setup Guide

This document provides instructions for setting up all required GitHub Secrets for the TikTrue CI/CD pipeline.

## Required Secrets

### 🔐 Deployment Secrets

#### `LIARA_API_TOKEN`
- **Description**: Liara API authentication token for deployment
- **How to get**: 
  1. Login to [Liara Console](https://console.liara.ir)
  2. Go to Account Settings → API Tokens
  3. Create a new token with deployment permissions
- **Usage**: Used by all deployment workflows
- **Rotation**: Every 90 days

### 🗄️ Backend Environment Variables

#### `SECRET_KEY`
- **Description**: Django secret key for production
- **Format**: Long random string (50+ characters)
- **Generation**: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- **Usage**: Django application security
- **Rotation**: Every 180 days

#### `DATABASE_URL`
- **Description**: Production database connection string
- **Format**: `postgresql://user:password@host:port/database`
- **Example**: `postgresql://tiktrue:password@db.liara.ir:5432/tiktrue_prod`
- **Usage**: Django database connection
- **Rotation**: When database credentials change

#### `CORS_ALLOWED_ORIGINS`
- **Description**: Comma-separated list of allowed CORS origins
- **Format**: `https://domain1.com,https://domain2.com`
- **Example**: `https://tiktrue-frontend.liara.run,https://tiktrue.com,https://www.tiktrue.com`
- **Usage**: Django CORS configuration
- **Rotation**: When domains change

### 🎨 Frontend Environment Variables

#### `REACT_APP_API_BASE_URL`
- **Description**: Backend API base URL for frontend
- **Format**: `https://domain.com/api/v1`
- **Example**: `https://tiktrue-backend.liara.run/api/v1`
- **Usage**: Frontend API calls
- **Rotation**: When backend URL changes

#### `REACT_APP_BACKEND_URL`
- **Description**: Backend application URL
- **Format**: `https://domain.com`
- **Example**: `https://tiktrue-backend.liara.run`
- **Usage**: Frontend backend communication
- **Rotation**: When backend URL changes

#### `REACT_APP_FRONTEND_URL`
- **Description**: Frontend application URL
- **Format**: `https://domain.com`
- **Example**: `https://tiktrue-frontend.liara.run`
- **Usage**: Frontend self-reference
- **Rotation**: When frontend URL changes

### 📢 Optional Notification Secrets

#### `SLACK_WEBHOOK_URL`
- **Description**: Slack webhook URL for notifications
- **Format**: `https://hooks.slack.com/services/...`
- **How to get**: Create webhook in Slack workspace settings
- **Usage**: Deployment notifications to Slack
- **Rotation**: When webhook is regenerated

#### `DISCORD_WEBHOOK_URL`
- **Description**: Discord webhook URL for notifications
- **Format**: `https://discord.com/api/webhooks/...`
- **How to get**: Create webhook in Discord server settings
- **Usage**: Deployment notifications to Discord
- **Rotation**: When webhook is regenerated

## Setup Instructions

### 1. Access GitHub Secrets

1. Go to your GitHub repository
2. Click on **Settings** tab
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**

### 2. Add Required Secrets

For each secret listed above:

1. Click **New repository secret**
2. Enter the **Name** (exactly as shown above)
3. Enter the **Value**
4. Click **Add secret**

### 3. Verify Secrets

After adding all secrets, you should see:

```
✅ LIARA_API_TOKEN
✅ SECRET_KEY
✅ DATABASE_URL
✅ CORS_ALLOWED_ORIGINS
✅ REACT_APP_API_BASE_URL
✅ REACT_APP_BACKEND_URL
✅ REACT_APP_FRONTEND_URL
```

Optional secrets (if using notifications):
```
⚪ SLACK_WEBHOOK_URL
⚪ DISCORD_WEBHOOK_URL
```

## Environment-Specific Configuration

### Production Environment

All secrets listed above are for production deployment.

### Staging Environment (Future)

For staging environment, you would add:
- `STAGING_LIARA_API_TOKEN`
- `STAGING_SECRET_KEY`
- `STAGING_DATABASE_URL`
- etc.

## Security Best Practices

### 🔒 Secret Management

1. **Never commit secrets to code**
2. **Use strong, unique values**
3. **Rotate secrets regularly**
4. **Limit access to secrets**
5. **Monitor secret usage**

### 🔄 Rotation Schedule

| Secret Type | Rotation Frequency | Trigger |
|-------------|-------------------|---------|
| API Tokens | Every 90 days | Calendar |
| Database Credentials | Every 180 days | Security review |
| Application Keys | Every 180 days | Security review |
| Webhook URLs | As needed | Service changes |

### 📊 Monitoring

Monitor secret usage through:
- GitHub Actions logs (redacted)
- Deployment success/failure rates
- Application error logs
- Security audit logs

## Troubleshooting

### Common Issues

#### 1. Deployment Fails with "Secret not found"
- **Cause**: Secret name mismatch or not set
- **Solution**: Verify secret name matches exactly (case-sensitive)

#### 2. Authentication Errors
- **Cause**: Invalid or expired tokens
- **Solution**: Regenerate and update the token

#### 3. CORS Errors in Frontend
- **Cause**: Incorrect CORS_ALLOWED_ORIGINS
- **Solution**: Verify domains are correct and include protocol

#### 4. Database Connection Errors
- **Cause**: Invalid DATABASE_URL format
- **Solution**: Check connection string format and credentials

### Validation Commands

Test secrets locally (never commit these):

```bash
# Test Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print('Valid format')"

# Test database URL format
python -c "import dj_database_url; dj_database_url.parse('$DATABASE_URL'); print('Valid format')"

# Test URL format
python -c "from urllib.parse import urlparse; urlparse('$REACT_APP_API_BASE_URL'); print('Valid format')"
```

## Emergency Procedures

### 🚨 Compromised Secret

If a secret is compromised:

1. **Immediate Actions**:
   - Revoke the compromised secret at source
   - Update GitHub secret with new value
   - Re-run failed deployments

2. **Investigation**:
   - Check access logs
   - Review recent commits
   - Audit team access

3. **Prevention**:
   - Update rotation schedule
   - Review access permissions
   - Enhance monitoring

### 🔄 Bulk Secret Update

For updating multiple secrets:

1. Prepare all new values
2. Update secrets in GitHub
3. Test in staging (if available)
4. Deploy to production
5. Verify all services

## Contact

For secret management issues:
- **DevOps Team**: @devops-team
- **Security Team**: @security-team
- **Emergency**: Create urgent issue with `security` label

---

**⚠️ Important**: Never share secrets through insecure channels (email, chat, etc.). Always use GitHub Secrets or approved secret management tools.