# TikTrue Frontend

Modern React.js frontend for TikTrue Distributed LLM Platform.

## Features

- 🎨 Modern UI with Tailwind CSS
- 🌙 Dark/Light theme support
- 📱 Fully responsive design
- 🔐 JWT authentication
- ⚡ Fast and optimized
- 🎭 Beautiful animations with Framer Motion

## Tech Stack

- **React 18** - Modern React with hooks
- **Tailwind CSS** - Utility-first CSS framework
- **Framer Motion** - Smooth animations
- **React Router** - Client-side routing
- **Axios** - HTTP client
- **React Hook Form** - Form handling
- **React Hot Toast** - Notifications

## Getting Started

### Prerequisites

- Node.js 16+ 
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build
```

### Environment Variables

Create a `.env` file in the root directory:

```env
REACT_APP_API_URL=https://tiktrue.com/api/v1
REACT_APP_SITE_NAME=TikTrue
```

## Available Scripts

- `npm start` - Start development server
- `npm run build` - Build for production
- `npm test` - Run tests
- `npm run eject` - Eject from Create React App

## Deployment

### Liara Platform Deployment

The TikTrue frontend is deployed on Liara using the static platform for React SPA.

**Live Deployment:**
- **Website URL**: https://tiktrue.com
- **Platform**: Static (React SPA) on Liara
- **Build Output**: `build/` directory
- **SPA Routing**: Configured for React Router

**Deployment Process:**

```bash
# 1. Prepare for deployment
cd frontend
npm install

# 2. Set up production environment
cp .env.example .env.production
# Edit .env.production with production settings

# 3. Build for production
npm run build

# 4. Deploy to Liara
liara deploy --platform=static --port=3000

# 5. Verify deployment
curl -I https://tiktrue.com
```

### Environment Configuration

**Required Environment Variables in Liara:**

```env
# API Configuration
REACT_APP_API_BASE_URL=https://api.tiktrue.com/api/v1
REACT_APP_API_URL=https://api.tiktrue.com/api/v1

# Site Configuration
REACT_APP_SITE_NAME=TikTrue
REACT_APP_ENVIRONMENT=production

# Build Configuration
GENERATE_SOURCEMAP=false
CI=false
```

**Local Development Environment (.env):**

```env
# API Configuration (for local development)
REACT_APP_API_BASE_URL=http://localhost:8000/api/v1
REACT_APP_API_URL=http://localhost:8000/api/v1

# Site Configuration
REACT_APP_SITE_NAME=TikTrue
REACT_APP_ENVIRONMENT=development

# Development Settings
GENERATE_SOURCEMAP=true
FAST_REFRESH=true
```

### Build Configuration

**Liara Configuration (liara.json):**

```json
{
  "platform": "static",
  "app": "tiktrue-frontend",
  "port": 3000,
  "build": {
    "commands": [
      "npm install",
      "npm run build"
    ],
    "output": "build"
  },
  "spa": true,
  "gzip": true
}
```

### Deployment Verification

After deployment, verify these features work:

```bash
# Check website loads
curl -I https://tiktrue.com

# Check SPA routing works
curl -I https://tiktrue.com/login
curl -I https://tiktrue.com/register
curl -I https://tiktrue.com/dashboard

# Check API connectivity from browser console:
# fetch('https://api.tiktrue.com/api/v1/auth/')
```

### Troubleshooting Deployment Issues

**Common Problems and Solutions:**

1. **Build Failures:**
   ```bash
   # Check for dependency issues
   npm install --legacy-peer-deps
   
   # Clear cache and rebuild
   npm run build -- --reset-cache
   ```

2. **API Connection Issues:**
   ```bash
   # Verify environment variables
   liara env list --app=tiktrue-frontend
   
   # Check CORS settings on backend
   curl -H "Origin: https://tiktrue.com" https://api.tiktrue.com/api/v1/auth/
   ```

3. **SPA Routing Issues:**
   ```json
   // Ensure liara.json has spa: true
   {
     "platform": "static",
     "spa": true
   }
   ```

4. **Static Files Not Loading:**
   ```bash
   # Check build output
   ls -la build/
   
   # Verify public path in package.json
   "homepage": "https://tiktrue.com"
   ```

### Performance Optimization

**Build Optimization:**

```bash
# Analyze bundle size
npm run build -- --analyze

# Check for unused dependencies
npm audit
npx depcheck
```

**Runtime Optimization:**
- Lazy loading for routes
- Image optimization
- Code splitting
- Service worker caching

### Monitoring and Logs

```bash
# View deployment logs
liara logs --app=tiktrue-frontend

# Check app status
liara app list

# Restart application
liara restart --app=tiktrue-frontend
```

## Project Structure

```
src/
├── components/          # Reusable components
│   ├── Navbar.js
│   └── ProtectedRoute.js
├── contexts/           # React contexts
│   ├── AuthContext.js
│   └── ThemeContext.js
├── pages/              # Page components
│   ├── LandingPage.js
│   ├── LoginPage.js
│   ├── RegisterPage.js
│   ├── DashboardPage.js
│   ├── ForgotPasswordPage.js
│   └── ResetPasswordPage.js
├── App.js              # Main app component
├── index.js            # Entry point
└── index.css           # Global styles
```

## API Integration

The frontend integrates with the TikTrue backend API:

- **Base URL**: `https://tiktrue.com/api/v1`
- **Authentication**: JWT tokens
- **Endpoints**: Auth, License, Models

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

TikTrue Platform - All rights reserved.