# Frontend Functionality Testing Guide

## Overview

This document provides comprehensive guidance for testing the TikTrue React frontend functionality, including component testing, integration testing, and end-to-end validation.

## Testing Architecture

### Testing Pyramid

```
                    E2E Tests
                   /         \
              Integration Tests
             /                 \
        Component Tests     Unit Tests
```

**Test Categories**:
1. **Unit Tests** - Individual functions and utilities
2. **Component Tests** - React component behavior
3. **Integration Tests** - Frontend-backend connectivity
4. **End-to-End Tests** - Complete user workflows

## Integration Testing

### Comprehensive Integration Test Suite

**Script**: `frontend/test_integration.js`

**Purpose**: Tests frontend-backend connectivity and core functionality

**Test Categories**:
1. **Environment Configuration** - Validates environment variables
2. **Frontend Build** - Checks build output and structure
3. **Backend Connectivity** - Tests API server accessibility
4. **CORS Configuration** - Validates cross-origin requests
5. **API Endpoints** - Tests authentication and data endpoints
6. **User Registration Flow** - Tests complete user signup process
7. **Authenticated Endpoints** - Tests protected resource access

**Usage**:
```bash
# Run integration tests with default URLs
node test_integration.js

# Run with custom URLs
node test_integration.js https://your-backend.com https://your-api.com/api/v1 https://your-frontend.com

# Run with environment variables
REACT_APP_BACKEND_URL=https://api.tiktrue.com \
REACT_APP_API_BASE_URL=https://api.tiktrue.com/api/v1 \
REACT_APP_FRONTEND_URL=https://tiktrue.com \
node test_integration.js
```

**Example Output**:
```
TikTrue Frontend Integration Test Suite
==================================================
Backend URL: https://api.tiktrue.com
API Base URL: https://api.tiktrue.com/api/v1
Frontend URL: https://tiktrue.com
==================================================

✅ Testing environment configuration...
✅ Environment: REACT_APP_API_BASE_URL: PASS
  Set to: https://api.tiktrue.com/api/v1
✅ Environment: REACT_APP_BACKEND_URL: PASS
  Set to: https://api.tiktrue.com
✅ Environment: REACT_APP_FRONTEND_URL: PASS
  Set to: https://tiktrue.com
✅ Environment Configuration: PASS
  All required variables set

✅ Testing frontend build...
✅ Build File: index.html: PASS
  File exists
✅ Build File: static/css: PASS
  File exists
✅ Build File: static/js: PASS
  File exists
✅ Frontend Build: PASS
  All required files present

✅ Testing backend connectivity...
✅ Backend Health Check: PASS
  Status: healthy
  Response time: 156.23ms
✅ Admin Panel Access: PASS
  HTTP 200
  Response time: 234.56ms

✅ Testing CORS configuration...
✅ CORS Preflight: PASS
  Origin: https://tiktrue.com
  Response time: 123.45ms

✅ Testing API endpoints...
✅ POST /auth/register/: PASS
  HTTP 400 (expected)
  Response time: 89.12ms
✅ POST /auth/login/: PASS
  HTTP 400 (expected)
  Response time: 76.34ms

✅ Testing user registration flow...
✅ User Registration: PASS
  User created with tokens
  Response time: 345.67ms

✅ Testing authenticated endpoints...
✅ GET /auth/profile/: PASS
  Data retrieved successfully
  Response time: 123.45ms
⚠️  GET /models/available/: WARNING
  Endpoint not implemented
  Response time: 98.76ms
⚠️  GET /license/info/: WARNING
  Endpoint not implemented
  Response time: 87.65ms

============================================================
FRONTEND INTEGRATION TEST REPORT
============================================================

Test Summary:
Total Tests: 15
Passed: 13
Failed: 0
Warnings: 2
Skipped: 0

⚠️  2 warnings:
  - GET /models/available/: Endpoint not implemented
  - GET /license/info/: Endpoint not implemented

⚠️  Tests completed with warnings - review recommended

Detailed results saved to: integration-test-results.json
============================================================
```

## Component Testing

### React Component Tests

**Testing Framework**: React Testing Library + Jest

**Test Structure**:
```javascript
// __tests__/components/LoginPage.test.js
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../../contexts/AuthContext';
import LoginPage from '../../pages/LoginPage';

const renderWithProviders = (component) => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        {component}
      </AuthProvider>
    </BrowserRouter>
  );
};

describe('LoginPage', () => {
  test('renders login form', () => {
    renderWithProviders(<LoginPage />);
    
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  });

  test('shows validation errors for empty fields', async () => {
    renderWithProviders(<LoginPage />);
    
    const loginButton = screen.getByRole('button', { name: /login/i });
    fireEvent.click(loginButton);

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
  });

  test('submits form with valid data', async () => {
    renderWithProviders(<LoginPage />);
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /login/i });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.click(loginButton);

    await waitFor(() => {
      // Assert API call was made or success state
    });
  });
});
```

### Component Test Categories

**1. Rendering Tests**:
```javascript
test('renders without crashing', () => {
  render(<Component />);
});

test('renders with correct props', () => {
  render(<Component title="Test Title" />);
  expect(screen.getByText('Test Title')).toBeInTheDocument();
});
```

**2. Interaction Tests**:
```javascript
test('handles button click', () => {
  const handleClick = jest.fn();
  render(<Button onClick={handleClick}>Click me</Button>);
  
  fireEvent.click(screen.getByText('Click me'));
  expect(handleClick).toHaveBeenCalledTimes(1);
});
```

**3. Form Tests**:
```javascript
test('validates form input', async () => {
  render(<LoginForm />);
  
  const submitButton = screen.getByRole('button', { name: /submit/i });
  fireEvent.click(submitButton);
  
  await waitFor(() => {
    expect(screen.getByText(/required field/i)).toBeInTheDocument();
  });
});
```

**4. Navigation Tests**:
```javascript
test('navigates to correct route', () => {
  const { container } = render(
    <MemoryRouter initialEntries={['/login']}>
      <App />
    </MemoryRouter>
  );
  
  expect(screen.getByText(/login/i)).toBeInTheDocument();
});
```

## API Integration Testing

### Mock API Testing

**Setup API Mocks**:
```javascript
// __tests__/setup.js
import { setupServer } from 'msw/node';
import { rest } from 'msw';

export const server = setupServer(
  rest.post('/api/v1/auth/login/', (req, res, ctx) => {
    return res(
      ctx.json({
        user: { id: 1, email: 'test@example.com' },
        tokens: { access: 'mock-token', refresh: 'mock-refresh' }
      })
    );
  }),
  
  rest.get('/api/v1/auth/profile/', (req, res, ctx) => {
    const authHeader = req.headers.get('authorization');
    if (!authHeader) {
      return res(ctx.status(401));
    }
    
    return res(
      ctx.json({
        id: 1,
        email: 'test@example.com',
        username: 'testuser'
      })
    );
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

**API Integration Tests**:
```javascript
// __tests__/api/auth.test.js
import { login, getProfile } from '../../api/auth';

describe('Auth API', () => {
  test('login returns user data and tokens', async () => {
    const result = await login('test@example.com', 'password123');
    
    expect(result.success).toBe(true);
    expect(result.user).toHaveProperty('email', 'test@example.com');
    expect(result.tokens).toHaveProperty('access');
  });

  test('getProfile returns user data with valid token', async () => {
    const profile = await getProfile('valid-token');
    
    expect(profile).toHaveProperty('email', 'test@example.com');
    expect(profile).toHaveProperty('username', 'testuser');
  });

  test('getProfile throws error with invalid token', async () => {
    await expect(getProfile('invalid-token')).rejects.toThrow();
  });
});
```

## End-to-End Testing

### E2E Test Setup

**Using Playwright**:
```javascript
// e2e/login.spec.js
import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
  test('user can login successfully', async ({ page }) => {
    await page.goto('/login');
    
    // Fill login form
    await page.fill('[data-testid="email-input"]', 'test@example.com');
    await page.fill('[data-testid="password-input"]', 'password123');
    
    // Submit form
    await page.click('[data-testid="login-button"]');
    
    // Verify redirect to dashboard
    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('[data-testid="user-welcome"]')).toBeVisible();
  });

  test('shows error for invalid credentials', async ({ page }) => {
    await page.goto('/login');
    
    await page.fill('[data-testid="email-input"]', 'invalid@example.com');
    await page.fill('[data-testid="password-input"]', 'wrongpassword');
    await page.click('[data-testid="login-button"]');
    
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
  });
});
```

### E2E Test Categories

**1. User Authentication Flow**:
- Registration process
- Login/logout functionality
- Password reset flow
- Protected route access

**2. Navigation Testing**:
- Page routing
- Menu navigation
- Breadcrumb functionality
- Back/forward browser buttons

**3. Form Interactions**:
- Form validation
- Data submission
- Error handling
- Success feedback

**4. Responsive Design**:
- Mobile viewport testing
- Tablet viewport testing
- Desktop viewport testing
- Touch interactions

## Performance Testing

### Frontend Performance Metrics

**Core Web Vitals Testing**:
```javascript
// utils/performance.js
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

export const measurePerformance = () => {
  getCLS(console.log);
  getFID(console.log);
  getFCP(console.log);
  getLCP(console.log);
  getTTFB(console.log);
};

// Call in index.js
measurePerformance();
```

**Bundle Size Analysis**:
```bash
# Analyze bundle size
npm run build:analyze

# Generate bundle report
npx webpack-bundle-analyzer build/static/js/*.js
```

**Performance Benchmarks**:
- **First Contentful Paint (FCP)**: < 1.8s
- **Largest Contentful Paint (LCP)**: < 2.5s
- **First Input Delay (FID)**: < 100ms
- **Cumulative Layout Shift (CLS)**: < 0.1
- **Time to First Byte (TTFB)**: < 600ms

## Accessibility Testing

### Automated Accessibility Testing

**Using jest-axe**:
```javascript
// __tests__/accessibility.test.js
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import App from '../App';

expect.extend(toHaveNoViolations);

test('should not have accessibility violations', async () => {
  const { container } = render(<App />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

**Manual Accessibility Checks**:
- Keyboard navigation
- Screen reader compatibility
- Color contrast ratios
- Focus management
- ARIA labels and roles

## Visual Regression Testing

### Screenshot Testing

**Using Playwright**:
```javascript
// e2e/visual.spec.js
import { test, expect } from '@playwright/test';

test('homepage visual regression', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveScreenshot('homepage.png');
});

test('dashboard visual regression', async ({ page }) => {
  // Login first
  await page.goto('/login');
  await page.fill('[data-testid="email-input"]', 'test@example.com');
  await page.fill('[data-testid="password-input"]', 'password123');
  await page.click('[data-testid="login-button"]');
  
  // Take screenshot of dashboard
  await expect(page).toHaveScreenshot('dashboard.png');
});
```

## Test Automation

### Continuous Integration

**GitHub Actions Workflow**:
```yaml
name: Frontend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Setup Node.js
      uses: actions/setup-node@v2
      with:
        node-version: '18'
        cache: 'npm'
    
    - name: Install dependencies
      run: |
        cd frontend
        npm ci
    
    - name: Run unit tests
      run: |
        cd frontend
        npm test -- --coverage --watchAll=false
    
    - name: Run integration tests
      run: |
        cd frontend
        node test_integration.js
      env:
        REACT_APP_API_BASE_URL: ${{ secrets.API_BASE_URL }}
        REACT_APP_BACKEND_URL: ${{ secrets.BACKEND_URL }}
        REACT_APP_FRONTEND_URL: ${{ secrets.FRONTEND_URL }}
    
    - name: Build application
      run: |
        cd frontend
        npm run build
    
    - name: Run E2E tests
      run: |
        cd frontend
        npx playwright test
    
    - name: Upload test results
      uses: actions/upload-artifact@v2
      if: failure()
      with:
        name: test-results
        path: frontend/test-results/
```

### Test Scripts

**Package.json Scripts**:
```json
{
  "scripts": {
    "test": "react-scripts test",
    "test:coverage": "react-scripts test --coverage --watchAll=false",
    "test:integration": "node test_integration.js",
    "test:e2e": "playwright test",
    "test:all": "npm run test:coverage && npm run test:integration && npm run test:e2e"
  }
}
```

## Testing Checklist

### Pre-Deployment Testing

**Unit Tests**:
- [ ] All components render without errors
- [ ] Form validation works correctly
- [ ] Event handlers function properly
- [ ] State management works as expected

**Integration Tests**:
- [ ] API connectivity established
- [ ] CORS configuration working
- [ ] Authentication flow functional
- [ ] Error handling implemented

**E2E Tests**:
- [ ] User registration works
- [ ] Login/logout functional
- [ ] Navigation works correctly
- [ ] All pages load properly

**Performance Tests**:
- [ ] Bundle size within limits
- [ ] Core Web Vitals meet thresholds
- [ ] Loading times acceptable
- [ ] No memory leaks detected

**Accessibility Tests**:
- [ ] No accessibility violations
- [ ] Keyboard navigation works
- [ ] Screen reader compatible
- [ ] Color contrast sufficient

### Post-Deployment Validation

**Production Testing**:
- [ ] Website loads at production URL
- [ ] All functionality works in production
- [ ] API calls reach production backend
- [ ] Error tracking operational
- [ ] Analytics tracking functional

**Cross-Browser Testing**:
- [ ] Chrome compatibility
- [ ] Firefox compatibility
- [ ] Safari compatibility
- [ ] Edge compatibility

**Device Testing**:
- [ ] Mobile responsiveness
- [ ] Tablet compatibility
- [ ] Desktop functionality
- [ ] Touch interactions

This comprehensive testing guide ensures thorough validation of all frontend functionality before and after deployment to Liara platform.