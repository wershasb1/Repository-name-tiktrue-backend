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

This project is configured for deployment on Liara.ir platform.

### Environment Variables

- `SECRET_KEY` - Django secret key
- `DEBUG` - Debug mode (False for production)
- `DATABASE_URL` - PostgreSQL database URL

### Local Development

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## License

TikTrue Platform - All rights reserved.