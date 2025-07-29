# GitHub Actions CI/CD Workflows

This directory contains GitHub Actions workflows for automated testing, building, and deployment of the TikTrue platform.

## Workflows Overview

### Deployment Workflows
- **`backend-deploy.yml`** - Backend Django deployment to Liara
- **`frontend-deploy.yml`** - Frontend React deployment to Liara

### Testing Workflows
- **`test-backend.yml`** - Backend testing and quality checks
- **`test-frontend.yml`** - Frontend testing and quality checks
- **`security-scan.yml`** - Security vulnerability scanning

### Utility Workflows
- **`notify.yml`** - Notification and monitoring workflow

## Required GitHub Secrets

### Liara Deployment
- `LIARA_API_TOKEN` - Liara API authentication token

### Backend Environment Variables
- `SECRET_KEY` - Django secret key for production
- `DATABASE_URL` - Production database connection string
- `CORS_ALLOWED_ORIGINS` - Allowed CORS origins (comma-separated)

### Frontend Environment Variables
- `REACT_APP_API_BASE_URL` - Backend API base URL
- `REACT_APP_BACKEND_URL` - Backend application URL
- `REACT_APP_FRONTEND_URL` - Frontend application URL

### Notification Settings (Optional)
- `SLACK_WEBHOOK_URL` - Slack webhook for notifications
- `DISCORD_WEBHOOK_URL` - Discord webhook for notifications

## Workflow Triggers

### Automatic Triggers
- **Push to main branch** - Triggers deployment workflows
- **Pull requests** - Triggers testing workflows only
- **Schedule** - Security scans run weekly

### Manual Triggers
- **Workflow dispatch** - Manual deployment trigger
- **Emergency rollback** - Manual rollback procedures

## Branch Protection Rules

The following branch protection rules should be configured:

1. **Require pull request reviews** - At least 1 reviewer
2. **Require status checks** - All tests must pass
3. **Require branches to be up to date** - Before merging
4. **Restrict pushes** - Only allow through pull requests
5. **Require signed commits** - For security

## Deployment Process

### Normal Deployment Flow
1. Developer creates pull request
2. Testing workflows run automatically
3. Code review and approval
4. Merge to main branch
5. Deployment workflows trigger automatically
6. Health checks verify deployment
7. Notifications sent on completion

### Emergency Procedures
1. **Rollback** - Use manual workflow dispatch
2. **Hotfix** - Direct push to main (with proper approvals)
3. **Incident Response** - Follow documented procedures

## Monitoring and Alerts

### Success Metrics
- Deployment success rate > 95%
- Build time < 10 minutes
- Test coverage > 80%
- Zero high/critical security vulnerabilities

### Alert Conditions
- Deployment failures
- Test failures on main branch
- Security vulnerabilities detected
- Health check failures

## Troubleshooting

### Common Issues
1. **Build failures** - Check dependency versions and conflicts
2. **Test failures** - Review test logs and fix failing tests
3. **Deployment failures** - Verify Liara configuration and secrets
4. **Health check failures** - Check application logs and database connectivity

### Debug Steps
1. Check workflow logs in GitHub Actions tab
2. Verify all required secrets are configured
3. Test deployment manually using Liara CLI
4. Check application logs in Liara dashboard
5. Verify environment variables and configuration

## Maintenance

### Regular Tasks
- Update dependency versions monthly
- Review and rotate secrets quarterly
- Monitor deployment metrics weekly
- Update documentation as needed

### Security Updates
- Monitor for security advisories
- Update vulnerable dependencies immediately
- Review and update security scanning rules
- Audit access permissions regularly