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

### Build for Production

```bash
npm run build
```

This creates a `build` folder with optimized production files.

### Deploy to Static Hosting

The build folder can be deployed to any static hosting service:

- **Netlify**: Drag and drop the build folder
- **Vercel**: Connect GitHub repository
- **GitHub Pages**: Use gh-pages package
- **Liara**: Upload build folder to static hosting

### Deploy to Liara (Static)

1. Build the project: `npm run build`
2. Create a new static app in Liara
3. Upload the `build` folder
4. Configure custom domain if needed

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