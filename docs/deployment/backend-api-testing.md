# Backend API Testing Guide

## Overview

This document provides comprehensive guidance for testing the TikTrue Django backend API endpoints to ensure proper functionality, authentication, and error handling.

## API Testing Tools

### 1. Automated Test Script

**Location**: `backend/test_api.py`

**Usage**:
```bash
# Test with default URL (https://api.tiktrue.com)
python test_api.py

# Test with custom URL
python test_api.py https://your-backend.liara.run

# Test local development server
python test_api.py http://localhost:8000
```

**Features**:
- Comprehensive endpoint testing
- CORS configuration validation
- Authentication flow testing
- Performance measurement
- Detailed reporting with JSON output

### 2. Manual Testing with cURL

**Health Check**:
```bash
curl -X GET https://api.tiktrue.com/health/ \
  -H "Accept: application/json"
```

**CORS Preflight Test**:
```bash
curl -X OPTIONS https://api.tiktrue.com/api/v1/auth/login/ \
  -H "Origin: https://tiktrue.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type,Authorization" \
  -v
```

**User Registration**:
```bash
curl -X POST https://api.tiktrue.com/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -H "Origin: https://tiktrue.com" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "testpassword123",
    "password_confirm": "testpassword123"
  }'
```

**User Login**:
```bash
curl -X POST https://api.tiktrue.com/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -H "Origin: https://tiktrue.com" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123"
  }'
```

**Authenticated Request**:
```bash
curl -X GET https://api.tiktrue.com/api/v1/auth/profile/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Origin: https://tiktrue.com"
```

## API Endpoints Testing

### 1. Health Check Endpoint

**Endpoint**: `GET /health/`

**Purpose**: Verify backend service health and configuration

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": 1640995200.0,
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "configuration": {
      "status": "healthy",
      "debug_mode": false,
      "secret_key_configured": true,
      "allowed_hosts": true
    },
    "cors": {
      "status": "healthy",
      "origins_configured": true,
      "credentials_allowed": true
    }
  },
  "response_time_ms": 45.2
}
```

**Test Cases**:
- ✅ Returns 200 status code
- ✅ Database connection is healthy
- ✅ Configuration is properly set
- ✅ CORS is configured
- ✅ Response time under 500ms

### 2. Admin Panel

**Endpoint**: `GET /admin/`

**Purpose**: Verify Django admin interface accessibility

**Expected Response**: 
- Status: 200 (login page) or 302 (redirect)
- Content: Django admin login form

**Test Cases**:
- ✅ Admin panel loads without errors
- ✅ Returns proper HTML content
- ✅ Static files (CSS/JS) load correctly

### 3. Authentication Endpoints

#### User Registration

**Endpoint**: `POST /api/v1/auth/register/`

**Request Body**:
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "testpassword123",
  "password_confirm": "testpassword123"
}
```

**Expected Response** (201 Created):
```json
{
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "subscription_plan": "free",
    "max_clients": 1
  },
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }
}
```

**Test Cases**:
- ✅ Valid registration returns 201
- ✅ Returns user data and JWT tokens
- ✅ Duplicate email returns 400
- ✅ Invalid data returns 400 with validation errors
- ✅ Password mismatch returns 400

#### User Login

**Endpoint**: `POST /api/v1/auth/login/`

**Request Body**:
```json
{
  "email": "test@example.com",
  "password": "testpassword123",
  "hardware_fingerprint": "web-browser"
}
```

**Expected Response** (200 OK):
```json
{
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "subscription_plan": "free",
    "max_clients": 1
  },
  "tokens": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }
}
```

**Test Cases**:
- ✅ Valid credentials return 200
- ✅ Returns user data and JWT tokens
- ✅ Invalid credentials return 401
- ✅ Missing fields return 400

#### User Profile

**Endpoint**: `GET /api/v1/auth/profile/`

**Headers**: `Authorization: Bearer JWT_TOKEN`

**Expected Response** (200 OK):
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "subscription_plan": "free",
  "max_clients": 1,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Test Cases**:
- ✅ Valid token returns 200 with user data
- ✅ Invalid token returns 401
- ✅ Missing token returns 401

### 4. Models API Endpoints

#### Available Models

**Endpoint**: `GET /api/v1/models/available/`

**Headers**: `Authorization: Bearer JWT_TOKEN`

**Expected Response** (200 OK):
```json
{
  "models": [
    {
      "id": "llama3_1_8b_fp16",
      "display_name": "Llama 3.1 8B FP16",
      "description": "Meta's Llama 3.1 8B model in FP16 precision",
      "version": "1.0.0",
      "file_size": 16000000000,
      "block_count": 33,
      "available": true
    }
  ]
}
```

**Test Cases**:
- ✅ Authenticated request returns 200
- ✅ Returns list of available models
- ✅ Unauthenticated request returns 401
- ✅ Model data includes all required fields

### 5. License API Endpoints

#### License Information

**Endpoint**: `GET /api/v1/license/info/`

**Headers**: `Authorization: Bearer JWT_TOKEN`

**Expected Response** (200 OK):
```json
{
  "license": {
    "license_key": "lic_1234567890abcdef",
    "subscription_plan": "free",
    "max_clients": 1,
    "created_at": "2024-01-01T00:00:00Z",
    "usage_count": 5,
    "is_active": true
  }
}
```

**Test Cases**:
- ✅ Authenticated request returns 200
- ✅ Returns license information
- ✅ Unauthenticated request returns 401

## CORS Testing

### Preflight Request Testing

**Test CORS Headers**:
```bash
curl -X OPTIONS https://api.tiktrue.com/api/v1/auth/login/ \
  -H "Origin: https://tiktrue.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type,Authorization" \
  -v
```

**Expected Headers**:
```
Access-Control-Allow-Origin: https://tiktrue.com
Access-Control-Allow-Methods: DELETE, GET, OPTIONS, PATCH, POST, PUT
Access-Control-Allow-Headers: accept, accept-encoding, authorization, content-type, dnt, origin, user-agent, x-csrftoken, x-requested-with
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
```

**Test Cases**:
- ✅ Preflight request returns 200
- ✅ Correct CORS headers present
- ✅ Origin matches allowed origins
- ✅ Credentials allowed
- ✅ Required methods allowed

### Cross-Origin Request Testing

**Test from Different Origins**:
```javascript
// Test from browser console on https://tiktrue.com
fetch('https://api.tiktrue.com/api/v1/auth/login/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  credentials: 'include',
  body: JSON.stringify({
    email: 'test@example.com',
    password: 'testpassword123'
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

## Error Handling Testing

### 1. Invalid Endpoints

**Test**: `GET /api/v1/nonexistent/`

**Expected**: 404 Not Found

### 2. Invalid JSON

**Test**: Send malformed JSON to any POST endpoint

**Expected**: 400 Bad Request

### 3. Missing Authentication

**Test**: Access protected endpoint without token

**Expected**: 401 Unauthorized

### 4. Invalid Authentication

**Test**: Access protected endpoint with invalid token

**Expected**: 401 Unauthorized

### 5. Method Not Allowed

**Test**: Use wrong HTTP method for endpoint

**Expected**: 405 Method Not Allowed

## Performance Testing

### Response Time Benchmarks

**Acceptable Response Times**:
- Health check: < 100ms
- Authentication: < 500ms
- Data retrieval: < 1000ms
- Database operations: < 2000ms

**Load Testing**:
```bash
# Using Apache Bench
ab -n 100 -c 10 https://api.tiktrue.com/health/

# Using curl with timing
curl -w "@curl-format.txt" -o /dev/null -s https://api.tiktrue.com/health/
```

**curl-format.txt**:
```
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n
```

## Security Testing

### 1. SQL Injection Testing

**Test**: Send SQL injection payloads in request data

**Expected**: Proper sanitization, no database errors

### 2. XSS Testing

**Test**: Send XSS payloads in request data

**Expected**: Proper escaping, no script execution

### 3. Authentication Bypass

**Test**: Attempt to access protected resources without proper authentication

**Expected**: 401 Unauthorized responses

### 4. CSRF Testing

**Test**: Cross-site request forgery attempts

**Expected**: CSRF protection blocks unauthorized requests

## Automated Testing Integration

### CI/CD Pipeline Integration

**GitHub Actions Example**:
```yaml
name: API Tests

on: [push, pull_request]

jobs:
  api-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install requests
    
    - name: Run API tests
      run: |
        cd backend
        python test_api.py https://api.tiktrue.com
    
    - name: Upload test results
      uses: actions/upload-artifact@v2
      with:
        name: api-test-results
        path: backend/api_test_results.json
```

### Continuous Monitoring

**Health Check Monitoring**:
```bash
#!/bin/bash
# health-monitor.sh

while true; do
  response=$(curl -s -o /dev/null -w "%{http_code}" https://api.tiktrue.com/health/)
  
  if [ $response -eq 200 ]; then
    echo "$(date): API is healthy"
  else
    echo "$(date): API is down (HTTP $response)"
    # Send alert notification
  fi
  
  sleep 60
done
```

## Test Results Analysis

### Success Criteria

**All Tests Pass**:
- Health check returns healthy status
- All API endpoints respond correctly
- CORS configuration works properly
- Authentication flow functions correctly
- Error handling works as expected

**Performance Criteria**:
- Response times within acceptable limits
- No memory leaks or resource issues
- Proper error handling under load

### Failure Investigation

**Common Issues**:
1. **Environment Variables**: Missing or incorrect configuration
2. **Database Connection**: Database service not running or misconfigured
3. **CORS Issues**: Frontend domain not in allowed origins
4. **Authentication**: JWT configuration or token handling issues
5. **Network Issues**: DNS resolution or connectivity problems

**Debugging Steps**:
1. Check application logs: `liara logs --app your-backend-app`
2. Verify environment variables: `liara env list --app your-backend-app`
3. Test database connection: `python manage.py check_database`
4. Verify CORS configuration in Django settings
5. Test individual endpoints with detailed error messages

This comprehensive testing guide ensures thorough validation of all backend API functionality and helps identify and resolve issues quickly.