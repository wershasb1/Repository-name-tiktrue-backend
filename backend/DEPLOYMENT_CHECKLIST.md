# Backend Deployment Checklist

## Pre-Deployment Checklist

### Environment Variables
- [ ] `SECRET_KEY` - Generate a secure secret key for production
- [ ] `DEBUG` - Set to `False` for production
- [ ] `ALLOWED_HOSTS` - Include Liara subdomain and custom domain
- [ ] `CORS_ALLOWED_ORIGINS` - Include frontend domains
- [ ] `DATABASE_URL` - Verify it's automatically provided by Liara

### Configuration Files
- [ ] `liara.json` - Verify Django platform configuration
- [ ] `runtime.txt` - Ensure Python version matches liara.json
- [ ] `requirements.txt` - All dependencies included and up to date
- [ ] `settings.py` - Production settings configured

### Code Quality
- [ ] Run `python manage.py check --deploy` for security checks
- [ ] All migrations created and tested
- [ ] Static files collection works (`python manage.py collectstatic`)
- [ ] No hardcoded secrets or sensitive data in code

## Deployment Process

### 1. Deploy to Liara
```bash
# Install Liara CLI if not already installed
npm install -g @liara/cli

# Login to Liara
liara login

# Deploy the application
liara deploy --app your-backend-app --platform django
```

### 2. Set Environment Variables
In Liara dashboard:
1. Go to your Django app
2. Navigate to Settings → Environment Variables
3. Add all required environment variables from `.env.example`

### 3. Database Setup
```bash
# Access app console
liara shell --app your-backend-app

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser (optional)
python manage.py createsuperuser
```

## Post-Deployment Verification

### Health Checks
- [ ] Health endpoint responds: `GET /health/`
- [ ] Admin panel accessible: `/admin/`
- [ ] API endpoints respond correctly

### API Endpoint Tests
- [ ] `POST /api/v1/auth/register/` - User registration
- [ ] `POST /api/v1/auth/login/` - User authentication
- [ ] `GET /api/v1/auth/profile/` - User profile (authenticated)
- [ ] `GET /api/v1/models/available/` - Available models
- [ ] `GET /api/v1/license/info/` - License information

### CORS Verification
- [ ] Preflight requests work from frontend domain
- [ ] Credentials are properly handled
- [ ] No CORS errors in browser console

### Security Verification
- [ ] HTTPS redirect works
- [ ] Security headers present
- [ ] No sensitive data exposed in responses
- [ ] Authentication required for protected endpoints

## Troubleshooting

### Common Issues

**Application won't start:**
- Check environment variables are set correctly
- Verify SECRET_KEY is not empty
- Check database connection

**Static files not loading:**
- Verify `collectStatic: true` in liara.json
- Check WhiteNoise middleware configuration
- Run `python manage.py collectstatic` manually

**CORS errors:**
- Verify CORS_ALLOWED_ORIGINS includes frontend domain
- Check middleware order (CorsMiddleware first)
- Test with browser network tab

**Database errors:**
- Verify DATABASE_URL is set
- Check database service is running
- Run migrations: `python manage.py migrate`

### Useful Commands
```bash
# Check deployment logs
liara logs --app your-backend-app --tail

# Access app console
liara shell --app your-backend-app

# Restart application
liara restart --app your-backend-app

# Check environment variables
liara env --app your-backend-app
```

## Rollback Procedure

If deployment fails:
1. Check logs: `liara logs --app your-backend-app`
2. Fix issues in code
3. Redeploy: `liara deploy --app your-backend-app`
4. If critical, rollback to previous version (if available)

## Monitoring

### Health Monitoring
- Set up monitoring for `/health/` endpoint
- Monitor response times and error rates
- Set up alerts for application downtime

### Log Monitoring
- Monitor application logs for errors
- Set up log aggregation if needed
- Monitor database query performance

### Security Monitoring
- Monitor for failed authentication attempts
- Check for unusual API usage patterns
- Monitor CORS errors and blocked requests