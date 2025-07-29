# TikTrue Backend

Backend server for TikTrue Distributed LLM Platform.

## Features

- User registration and authentication
- License management and validation
- Model file management and secure downloads
- JWT token-based authentication
- Admin panel for management

## API Endpoints

### Authentication
- `POST /api/v1/auth/register/` - User registration
- `POST /api/v1/auth/login/` - User login
- `POST /api/v1/auth/logout/` - User logout
- `GET /api/v1/auth/profile/` - Get user profile
- `POST /api/v1/auth/refresh/` - Refresh JWT token

### License Management
- `GET /api/v1/license/validate/` - Validate license
- `GET /api/v1/license/info/` - Get license information

### Model Management
- `GET /api/v1/models/available/` - Get available models
- `GET /api/v1/models/<id>/metadata/` - Get model metadata
- `POST /api/v1/models/<id>/download/` - Create download token
- `GET /api/v1/models/download/<token>/` - Download model

## Deployment

### Liara Platform Deployment

The TikTrue backend is deployed on Liara using the Django platform with PostgreSQL database.

**Live Deployment:**
- **API URL**: https://api.tiktrue.com
- **Admin Panel**: https://api.tiktrue.com/admin/
- **Platform**: Django on Liara
- **Database**: PostgreSQL (managed by Liara)

**Deployment Process:**

```bash
# 1. Prepare for deployment
cd backend
pip install -r requirements.txt

# 2. Test locally first
python manage.py check --deploy
python manage.py test

# 3. Deploy to Liara
liara deploy --platform=django --port=8000

# 4. Run migrations (if needed)
liara shell --app=tiktrue-backend
python manage.py migrate
python manage.py collectstatic --noinput
```

### Environment Variables

**Required Environment Variables in Liara:**

```env
# Django Core Settings
SECRET_KEY=your-production-secret-key-here
DEBUG=False
ALLOWED_HOSTS=api.tiktrue.com,*.liara.run

# Database Configuration
DATABASE_URL=postgresql://username:password@host:port/database_name

# CORS Configuration for Frontend
CORS_ALLOWED_ORIGINS=https://tiktrue.com,https://www.tiktrue.com
CORS_ALLOW_CREDENTIALS=True

# Security Settings
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Static Files
STATIC_ROOT=/app/staticfiles
STATIC_URL=/static/
```

### Local Development

```bash
# Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your local settings

# Run database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Database Setup and Migration

```bash
# Connect to your app shell on Liara
liara shell --app=tiktrue-backend

# Run database migrations
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Load initial data (if available)
python manage.py loaddata initial_data.json
```

### Deployment Verification

After deployment, verify these endpoints work:

```bash
# Health check
curl https://api.tiktrue.com/admin/

# API endpoints
curl https://api.tiktrue.com/api/v1/auth/
curl https://api.tiktrue.com/api/v1/models/available/

# Check CORS headers
curl -H "Origin: https://tiktrue.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: X-Requested-With" \
     -X OPTIONS https://api.tiktrue.com/api/v1/auth/login/
```

### Troubleshooting Deployment Issues

**Common Problems and Solutions:**

1. **Database Connection Errors:**
   ```bash
   # Check DATABASE_URL format
   # Should be: postgresql://user:password@host:port/dbname
   liara env list --app=tiktrue-backend
   ```

2. **CORS Errors:**
   ```python
   # Verify CORS settings in settings.py
   CORS_ALLOWED_ORIGINS = [
       "https://tiktrue.com",
       "https://www.tiktrue.com",
   ]
   ```

3. **Static Files Not Loading:**
   ```bash
   # Recollect static files
   liara shell --app=tiktrue-backend
   python manage.py collectstatic --clear --noinput
   ```

4. **Migration Issues:**
   ```bash
   # Check migration status
   python manage.py showmigrations
   
   # Apply specific migration
   python manage.py migrate app_name migration_name
   ```

### Monitoring and Logs

```bash
# View application logs
liara logs --app=tiktrue-backend

# Follow logs in real-time
liara logs --app=tiktrue-backend --follow

# Check app status
liara app list

# Restart application
liara restart --app=tiktrue-backend
```

## License

TikTrue Platform - All rights reserved.