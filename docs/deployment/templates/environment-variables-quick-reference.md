# Environment Variables Quick Reference

## Backend (Django) Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `django-insecure-abc123...` |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Allowed hosts | `api.tiktrue.com,tiktrue-backend.liara.run` |
| `DATABASE_URL` | Database connection | `postgresql://user:pass@host:5432/db` |
| `CORS_ALLOWED_ORIGINS` | CORS origins | `https://tiktrue.com,https://www.tiktrue.com` |

### Security Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECURE_SSL_REDIRECT` | Force HTTPS | `True` |
| `SECURE_HSTS_SECONDS` | HSTS max-age | `31536000` |
| `SESSION_COOKIE_SECURE` | Secure cookies | `True` |
| `CSRF_COOKIE_SECURE` | Secure CSRF | `True` |

### Optional Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DJANGO_LOG_LEVEL` | Logging level | `INFO` |
| `EMAIL_HOST` | SMTP server | `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_HOST_USER` | SMTP username | `noreply@tiktrue.com` |
| `EMAIL_HOST_PASSWORD` | SMTP password | `app-password` |

## Frontend (React) Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `REACT_APP_API_BASE_URL` | Backend API URL | `https://api.tiktrue.com/api/v1` |
| `REACT_APP_BACKEND_URL` | Backend base URL | `https://api.tiktrue.com` |
| `REACT_APP_FRONTEND_URL` | Frontend URL | `https://tiktrue.com` |

### Build Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GENERATE_SOURCEMAP` | Generate source maps | `false` |
| `INLINE_RUNTIME_CHUNK` | Inline runtime | `false` |
| `CI` | CI mode | `false` |

### Application Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `REACT_APP_ENVIRONMENT` | Environment | `production` |
| `REACT_APP_DEBUG` | Debug mode | `false` |
| `REACT_APP_VERSION` | App version | `1.0.0` |

### Feature Flags

| Variable | Description | Example |
|----------|-------------|---------|
| `REACT_APP_ENABLE_ANALYTICS` | Enable analytics | `true` |
| `REACT_APP_ENABLE_DARK_MODE` | Dark mode | `true` |
| `REACT_APP_API_TIMEOUT` | API timeout (ms) | `10000` |

## Environment-Specific Values

### Production
```bash
# Backend
SECRET_KEY=production-secret-key
DEBUG=False
ALLOWED_HOSTS=api.tiktrue.com,tiktrue-backend.liara.run
CORS_ALLOWED_ORIGINS=https://tiktrue.com,https://www.tiktrue.com

# Frontend
REACT_APP_API_BASE_URL=https://api.tiktrue.com/api/v1
REACT_APP_BACKEND_URL=https://api.tiktrue.com
REACT_APP_FRONTEND_URL=https://tiktrue.com
GENERATE_SOURCEMAP=false
```

### Development
```bash
# Backend
SECRET_KEY=django-insecure-dev-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Frontend
REACT_APP_API_BASE_URL=http://localhost:8000/api/v1
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_FRONTEND_URL=http://localhost:3000
GENERATE_SOURCEMAP=true
```

### Staging
```bash
# Backend
SECRET_KEY=staging-secret-key
DEBUG=False
ALLOWED_HOSTS=staging-api.tiktrue.com
CORS_ALLOWED_ORIGINS=https://staging.tiktrue.com

# Frontend
REACT_APP_API_BASE_URL=https://staging-api.tiktrue.com/api/v1
REACT_APP_BACKEND_URL=https://staging-api.tiktrue.com
REACT_APP_FRONTEND_URL=https://staging.tiktrue.com
GENERATE_SOURCEMAP=false
```

## Liara Configuration

### Backend liara.json
```json
{
  "platform": "django",
  "app": "tiktrue-backend",
  "environments": {
    "SECRET_KEY": "REQUIRED",
    "DEBUG": "False",
    "ALLOWED_HOSTS": "api.tiktrue.com,tiktrue-backend.liara.run",
    "CORS_ALLOWED_ORIGINS": "https://tiktrue.com,https://www.tiktrue.com"
  }
}
```

### Frontend liara.json
```json
{
  "platform": "react",
  "app": "tiktrue-frontend",
  "environments": {
    "REACT_APP_API_BASE_URL": "https://api.tiktrue.com/api/v1",
    "REACT_APP_BACKEND_URL": "https://api.tiktrue.com",
    "REACT_APP_FRONTEND_URL": "https://tiktrue.com",
    "GENERATE_SOURCEMAP": "false"
  }
}
```

## Common Commands

### Generate Django Secret Key
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Set Liara Environment Variables
```bash
# Backend
liara env set SECRET_KEY="your-secret-key" --app tiktrue-backend
liara env set DEBUG="False" --app tiktrue-backend

# Frontend
liara env set REACT_APP_API_BASE_URL="https://api.tiktrue.com/api/v1" --app tiktrue-frontend
```

### List Environment Variables
```bash
liara env --app tiktrue-backend
liara env --app tiktrue-frontend
```

### Validate Environment
```bash
# Backend
python manage.py check --deploy

# Frontend
npm run build
```

## Security Notes

- ✅ Never commit `.env` files to version control
- ✅ Use strong, unique `SECRET_KEY` for production
- ✅ Set `DEBUG=False` in production
- ✅ Use HTTPS URLs in production
- ✅ Enable security headers (`SECURE_SSL_REDIRECT=True`)
- ❌ Don't put sensitive data in React environment variables (they're public)
- ❌ Don't use development keys in production