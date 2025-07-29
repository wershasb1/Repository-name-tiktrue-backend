# TikTrue Platform

TikTrue is a comprehensive AI platform that provides both web-based services and desktop applications for distributed Large Language Model (LLM) processing. The platform enables users to register accounts, manage subscriptions, and download desktop applications for distributed AI processing.

## 🌐 Web Platform (Primary Focus)

The web platform consists of a React frontend and Django REST API backend, both deployed on Liara cloud platform with full SSL/HTTPS support.

### Live Deployment

- **Website**: https://tiktrue.com - Main website with user registration and dashboard
- **API**: https://api.tiktrue.com - Django REST API backend
- **Admin Panel**: https://api.tiktrue.com/admin/ - Django admin interface

### Platform Features

- ✅ **User Registration & Authentication** - Complete user account system with JWT tokens
- ✅ **Subscription Management** - Multiple subscription tiers (Free, Pro, Enterprise)
- ✅ **Desktop App Downloads** - Secure download links for desktop applications
- ✅ **License Management** - Software license validation and tracking
- ✅ **Responsive Design** - Mobile-friendly interface with dark/light themes
- ✅ **SSL/HTTPS Security** - Full SSL encryption and security headers

### Quick Start (Development)

**Frontend (React):**
```bash
cd frontend
npm install
cp .env.example .env
npm start
```

**Backend (Django):**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

## 🖥️ Desktop Application

The desktop application provides distributed LLM processing capabilities for local networks.

```bash
cd desktop
python main_app.py
```

## 📁 Project Structure

```
TikTrue_Platform/
├── backend/           # Django REST API backend
├── frontend/          # React web application
├── desktop/           # Desktop application (Python)
├── docs/              # Documentation and guides
├── scripts/           # Deployment and utility scripts
├── tests/             # Test files and reports
├── config/            # Configuration files
├── assets/            # Static assets and models
├── certs/             # SSL certificates
├── data/              # Data files
├── temp/              # Temporary files and logs
└── utils/             # Utility modules
```

## 🚀 Deployment

### Web Deployment (Liara Platform)

The TikTrue platform is deployed on Liara cloud platform with the following configuration:

#### Backend Deployment (Django on Liara)

**Prerequisites:**
- Liara CLI installed and configured
- PostgreSQL database created on Liara
- Environment variables configured

**Deployment Steps:**
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run migrations (if needed)
python manage.py migrate

# Deploy to Liara
liara deploy --platform=django --port=8000
```

**Backend Configuration:**
- **Platform**: Django
- **Domain**: api.tiktrue.com
- **Database**: PostgreSQL (managed by Liara)
- **Environment**: Production settings with DEBUG=False

#### Frontend Deployment (React on Liara)

**Prerequisites:**
- Node.js and npm installed
- Environment variables configured for production

**Deployment Steps:**
```bash
cd frontend

# Install dependencies
npm install

# Build for production
npm run build

# Deploy to Liara
liara deploy --platform=static --port=3000
```

**Frontend Configuration:**
- **Platform**: Static (React SPA)
- **Domain**: tiktrue.com
- **Build Output**: `build/` directory
- **SPA Routing**: Configured for React Router

#### Environment Configuration

**Backend Environment Variables:**
```env
SECRET_KEY=your-production-secret-key
DEBUG=False
DATABASE_URL=postgresql://user:password@host:port/database
CORS_ALLOWED_ORIGINS=https://tiktrue.com,https://www.tiktrue.com
ALLOWED_HOSTS=api.tiktrue.com,*.liara.run
```

**Frontend Environment Variables:**
```env
REACT_APP_API_BASE_URL=https://api.tiktrue.com/api/v1
REACT_APP_SITE_NAME=TikTrue
REACT_APP_ENVIRONMENT=production
```

### Desktop Application Deployment

See `desktop/README.md` for desktop application setup and deployment instructions.

### Deployment Troubleshooting

**Common Issues:**

1. **CORS Errors**: Ensure `CORS_ALLOWED_ORIGINS` includes your frontend domain
2. **Database Connection**: Verify `DATABASE_URL` is correctly configured
3. **Static Files**: Check that `STATIC_ROOT` and `STATIC_URL` are properly set
4. **SSL Issues**: Ensure both frontend and backend use HTTPS

**Useful Commands:**
```bash
# Check deployment logs
liara logs --app=your-app-name

# Check app status
liara app list

# Restart application
liara restart --app=your-app-name
```

## 📚 Documentation

- **Deployment Guides**: `docs/deployment/`
- **API Documentation**: `docs/api/`
- **User Guides**: `docs/user/`
- **Development Guides**: `docs/development/`

## 🧪 Testing

```bash
# Backend API tests
cd backend
python test_api_endpoints.py

# Frontend tests
cd frontend
npm test

# Integration tests
cd tests
python -m pytest
```

## 🔧 Configuration

Configuration files are organized in the `config/` directory:

- `config/development/` - Development environment configs
- `config/production/` - Production environment configs
- `config/templates/` - Configuration templates

## 📄 License

This project is licensed under the terms specified in `LICENSE.txt`.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## 📞 Support

- **Email**: support@tiktrue.com
- **Documentation**: https://docs.tiktrue.com
- **Issues**: Create an issue in this repository

## 🏗️ Architecture

### Web Platform Architecture

```
Frontend (React) → API Gateway → Backend (Django) → Database (PostgreSQL)
     ↓                                    ↓
Static Files (Liara) ←→ Media Files (Liara) ←→ File Storage
```

### Desktop Application Architecture

```
Admin Node ←→ Client Nodes ←→ Model Processing ←→ Distributed Network
     ↓              ↓              ↓                    ↓
License System → Authentication → Model Blocks → Secure Transfer
```

## 🔄 Recent Updates

- ✅ Web platform deployment on Liara
- ✅ Frontend-backend connectivity established
- ✅ SSL/HTTPS configuration completed
- ✅ Desktop app download functionality implemented
- ✅ Project structure reorganized

---

**TikTrue Platform** - Distributed AI Processing Made Simple