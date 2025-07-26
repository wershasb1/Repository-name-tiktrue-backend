# Backend API Client Guide

## Overview

The Backend API Client is a comprehensive HTTP-based client for communicating with the TikTrue backend server. It provides authenticated access to user management, license validation, model downloads, and payment processing.

## Features

- **Async/Await Support**: Full asynchronous operation using aiohttp
- **Authentication Management**: JWT token handling with automatic refresh
- **License Integration**: Hardware-bound license validation and management
- **Model Operations**: Secure model download and metadata retrieval
- **Payment Processing**: Subscription and payment management
- **Error Handling**: Comprehensive error handling with retry mechanisms
- **SSL Security**: Secure HTTPS connections with certificate validation

## Quick Start

### Basic Usage

```python
import asyncio
from backend_api_client import BackendAPIClient, LoginCredentials

async def main():
    # Create client
    async with BackendAPIClient("https://api.tiktrue.com") as client:
        # Test connection
        connection_result = await client.test_connection()
        print(f"Connected: {connection_result.success}")
        
        # Login
        credentials = LoginCredentials(
            username="user@example.com",
            password="your_password",
            hardware_fingerprint="hw_fingerprint_123"
        )
        
        login_result = await client.login(credentials)
        if login_result.success:
            print("Login successful!")
            
            # Get available models
            models = await client.get_available_models()
            print(f"Available models: {models.data}")

asyncio.run(main())
```

### Using Convenience Functions

```python
from backend_api_client import create_api_client, test_backend_connection

# Quick connection test
is_connected = await test_backend_connection("https://api.tiktrue.com")

# Create and initialize client
client = await create_api_client("https://api.tiktrue.com")
```

## API Reference

### BackendAPIClient Class

#### Constructor

```python
BackendAPIClient(base_url: str, timeout: int = 30, max_retries: int = 3)
```

**Parameters:**
- `base_url`: Backend server base URL (e.g., "https://api.tiktrue.com")
- `timeout`: Request timeout in seconds (default: 30)
- `max_retries`: Maximum retry attempts for failed requests (default: 3)

#### Authentication Methods

##### login(credentials: LoginCredentials) -> APIResponse

Authenticate user with backend server.

```python
credentials = LoginCredentials(
    username="user@example.com",
    password="password123",
    hardware_fingerprint="hw_abc123"
)

result = await client.login(credentials)
if result.success:
    print(f"Access token: {client.access_token}")
```

##### logout() -> APIResponse

Logout and invalidate tokens.

```python
result = await client.logout()
print(f"Logout successful: {result.success}")
```

##### is_authenticated() -> bool

Check if client is currently authenticated.

```python
if client.is_authenticated():
    print("Client is authenticated")
```

#### License Methods

##### validate_license(hardware_fingerprint: str) -> APIResponse

Validate user license with backend server.

```python
result = await client.validate_license("hw_fingerprint_123")
if result.success:
    print(f"License valid: {result.data['valid']}")
```

##### get_license_info() -> APIResponse

Get detailed license information.

```python
result = await client.get_license_info()
if result.success:
    license_info = result.data
    print(f"Plan: {license_info['plan']}")
    print(f"Expires: {license_info['expires_at']}")
```

##### renew_license(payment_token: str) -> APIResponse

Renew license with payment.

```python
result = await client.renew_license("payment_token_123")
if result.success:
    print("License renewed successfully")
```

#### Model Methods

##### get_available_models() -> APIResponse

Get list of models available to user based on license.

```python
result = await client.get_available_models()
if result.success:
    models = result.data['models']
    for model in models:
        print(f"Model: {model['name']} ({model['model_id']})")
```

##### get_model_metadata(model_id: str) -> APIResponse

Get metadata for specific model.

```python
result = await client.get_model_metadata("llama3_1_8b_fp16")
if result.success:
    metadata = result.data
    print(f"Size: {metadata['size_mb']} MB")
    print(f"Blocks: {metadata['blocks_count']}")
```

##### get_model_download_url(model_id: str) -> APIResponse

Get secure download URL for model.

```python
result = await client.get_model_download_url("llama3_1_8b_fp16")
if result.success:
    download_url = result.data['download_url']
    print(f"Download URL: {download_url}")
```

##### download_model_file(download_url: str, local_path: Path, progress_callback: callable = None) -> APIResponse

Download model file from secure URL.

```python
from pathlib import Path

def progress_callback(progress, downloaded, total):
    print(f"Progress: {progress:.1f}% ({downloaded}/{total} bytes)")

result = await client.download_model_file(
    download_url="https://secure.download.url/model.bin",
    local_path=Path("./models/model.bin"),
    progress_callback=progress_callback
)

if result.success:
    print(f"Downloaded to: {result.data['local_path']}")
```

#### Payment Methods

##### create_payment_session(plan: str, duration_months: int) -> APIResponse

Create payment session for license purchase/renewal.

```python
result = await client.create_payment_session("PRO", 12)
if result.success:
    session_data = result.data
    print(f"Payment URL: {session_data['payment_url']}")
```

##### get_payment_history() -> APIResponse

Get user's payment history.

```python
result = await client.get_payment_history()
if result.success:
    payments = result.data['payments']
    for payment in payments:
        print(f"Payment: {payment['amount']} on {payment['date']}")
```

#### Utility Methods

##### test_connection() -> APIResponse

Test connection to backend server.

```python
result = await client.test_connection()
if result.success:
    print("Backend server is reachable")
else:
    print(f"Connection failed: {result.error}")
```

## Data Classes

### APIResponse

Standard response structure for all API operations.

```python
@dataclass
class APIResponse:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    status_code: int = 200
```

### LoginCredentials

Login credentials structure.

```python
@dataclass
class LoginCredentials:
    username: str
    password: str
    hardware_fingerprint: Optional[str] = None
```

### LicenseInfo

License information from backend.

```python
@dataclass
class LicenseInfo:
    license_key: str
    plan: str
    expires_at: str
    max_clients: int
    allowed_models: List[str]
    allowed_features: List[str]
    status: str
```

### ModelInfo

Model information from backend.

```python
@dataclass
class ModelInfo:
    model_id: str
    name: str
    description: str
    size_mb: int
    blocks_count: int
    download_url: str
    checksum: str
```

## Error Handling

### Error Types

The client handles various error types gracefully:

- **Network Errors**: Connection timeouts, DNS failures, SSL errors
- **Authentication Errors**: Invalid credentials, expired tokens
- **Authorization Errors**: Insufficient permissions, license violations
- **Server Errors**: Internal server errors, service unavailable
- **Client Errors**: Invalid requests, malformed data

### Error Response Structure

```python
# Example error response
{
    "success": False,
    "error": "Invalid credentials",
    "error_code": "INVALID_CREDENTIALS",
    "status_code": 401
}
```

### Retry Mechanism

The client automatically retries failed requests with exponential backoff:

- **Maximum Retries**: Configurable (default: 3)
- **Backoff Strategy**: Exponential (2^attempt seconds)
- **Retryable Errors**: Network timeouts, temporary server errors
- **Non-Retryable Errors**: Authentication failures, client errors

### Example Error Handling

```python
try:
    result = await client.login(credentials)
    if not result.success:
        if result.error_code == "INVALID_CREDENTIALS":
            print("Please check your username and password")
        elif result.error_code == "NETWORK_ERROR":
            print("Network connection failed, please try again")
        else:
            print(f"Login failed: {result.error}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Configuration

### Environment Variables

The client can be configured using environment variables:

```bash
# Backend server URL
export BACKEND_URL="https://api.tiktrue.com"

# Test credentials (for testing only)
export TEST_USERNAME="test@example.com"
export TEST_PASSWORD="test_password"
export TEST_HW_FINGERPRINT="test_hw_fingerprint"
```

### SSL Configuration

The client uses secure SSL connections by default:

- **Certificate Validation**: Enabled using certifi
- **TLS Version**: TLS 1.2 or higher
- **Cipher Suites**: Strong ciphers only
- **HSTS**: Supported

## Performance Considerations

### Connection Pooling

The client uses connection pooling for optimal performance:

- **Pool Size**: 10 connections total, 5 per host
- **Keep-Alive**: Enabled with DNS caching
- **Timeout**: Configurable per request

### Memory Management

- **Session Cleanup**: Automatic session cleanup on context exit
- **Response Streaming**: Large downloads use streaming
- **Memory Limits**: Configurable response size limits

### Best Practices

1. **Use Context Managers**: Always use `async with` for automatic cleanup
2. **Reuse Clients**: Create one client instance per application
3. **Handle Errors**: Always check `result.success` before using data
4. **Monitor Performance**: Use built-in timing and statistics
5. **Secure Credentials**: Never hardcode credentials in source code

## Testing

### Unit Tests

Run unit tests with pytest:

```bash
python -m pytest tests/unit/test_backend_api_client.py -v
```

### Integration Tests

Run integration tests (requires backend server):

```bash
export BACKEND_URL="https://api.test.tiktrue.com"
python -m pytest tests/integration/test_backend_api_integration.py -v -m integration
```

### Demo Scripts

Run demo scripts to see the client in action:

```bash
python tests/demo/demo_backend_api_client.py
```

## Troubleshooting

### Common Issues

#### Connection Errors

```python
# Error: Cannot connect to host
# Solution: Check network connectivity and server URL
result = await client.test_connection()
if not result.success:
    print(f"Connection failed: {result.error}")
```

#### Authentication Failures

```python
# Error: Invalid credentials
# Solution: Verify username, password, and hardware fingerprint
if not client.is_authenticated():
    print("Please login first")
```

#### SSL Certificate Errors

```python
# Error: SSL certificate verification failed
# Solution: Update certifi package or check system certificates
pip install --upgrade certifi
```

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now all HTTP requests will be logged
async with BackendAPIClient("https://api.tiktrue.com") as client:
    result = await client.test_connection()
```

### Performance Issues

Monitor request performance:

```python
import time

start_time = time.time()
result = await client.get_available_models()
end_time = time.time()

print(f"Request took {end_time - start_time:.2f} seconds")
```

## Examples

### Complete Authentication Workflow

```python
import asyncio
from backend_api_client import BackendAPIClient, LoginCredentials

async def authentication_example():
    async with BackendAPIClient("https://api.tiktrue.com") as client:
        # Check initial state
        print(f"Initially authenticated: {client.is_authenticated()}")
        
        # Login
        credentials = LoginCredentials(
            username="user@example.com",
            password="password123",
            hardware_fingerprint="hw_abc123"
        )
        
        login_result = await client.login(credentials)
        if login_result.success:
            print("Login successful!")
            print(f"Access token: {client.access_token[:20]}...")
            print(f"Token expires: {client.token_expires_at}")
            
            # Use authenticated endpoints
            license_result = await client.get_license_info()
            if license_result.success:
                print(f"License plan: {license_result.data['plan']}")
            
            # Logout
            logout_result = await client.logout()
            print(f"Logout successful: {logout_result.success}")
        else:
            print(f"Login failed: {login_result.error}")

asyncio.run(authentication_example())
```

### Model Download Workflow

```python
import asyncio
from pathlib import Path
from backend_api_client import BackendAPIClient, LoginCredentials

async def model_download_example():
    async with BackendAPIClient("https://api.tiktrue.com") as client:
        # Login first
        credentials = LoginCredentials(
            username="user@example.com",
            password="password123",
            hardware_fingerprint="hw_abc123"
        )
        
        login_result = await client.login(credentials)
        if not login_result.success:
            print(f"Login failed: {login_result.error}")
            return
        
        # Get available models
        models_result = await client.get_available_models()
        if not models_result.success:
            print(f"Failed to get models: {models_result.error}")
            return
        
        models = models_result.data['models']
        if not models:
            print("No models available")
            return
        
        # Select first model
        model = models[0]
        model_id = model['model_id']
        print(f"Downloading model: {model['name']}")
        
        # Get download URL
        download_result = await client.get_model_download_url(model_id)
        if not download_result.success:
            print(f"Failed to get download URL: {download_result.error}")
            return
        
        download_url = download_result.data['download_url']
        local_path = Path(f"./models/{model_id}.bin")
        
        # Download with progress tracking
        def progress_callback(progress, downloaded, total):
            print(f"\rProgress: {progress:.1f}% ({downloaded:,}/{total:,} bytes)", end="")
        
        download_result = await client.download_model_file(
            download_url=download_url,
            local_path=local_path,
            progress_callback=progress_callback
        )
        
        if download_result.success:
            print(f"\nDownload completed: {download_result.data['local_path']}")
        else:
            print(f"\nDownload failed: {download_result.error}")

asyncio.run(model_download_example())
```

## API Endpoints Reference

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Desktop application authentication |
| POST | `/api/v1/auth/refresh` | Token refresh |
| POST | `/api/v1/auth/logout` | Session termination |

### License Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/license/validate` | License validation |
| GET | `/api/v1/license/info` | License information |
| POST | `/api/v1/license/renew` | License renewal |

### Model Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/models/available` | Available models for user |
| GET | `/api/v1/models/download/{id}` | Secure download links |
| GET | `/api/v1/models/metadata/{id}` | Model metadata |

### Payment Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/payments/create` | Create payment session |
| POST | `/api/v1/payments/webhook` | Payment gateway webhook |
| GET | `/api/v1/payments/history` | Payment history |

## Contributing

### Development Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Install development dependencies: `pip install pytest pytest-asyncio`
4. Run tests: `python -m pytest tests/ -v`

### Code Style

- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Write comprehensive docstrings for all public methods
- Include unit tests for all new functionality

### Submitting Changes

1. Create a feature branch
2. Make your changes with tests
3. Run the full test suite
4. Submit a pull request with description

## License

This project is licensed under the MIT License. See LICENSE file for details.