"""
Backend API Client for TikTrue Distributed LLM Platform
Handles all communication between desktop application and backend server
"""

import asyncio
import aiohttp
import aiofiles
import json
import logging
import hashlib
import hmac
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import ssl
import certifi

logger = logging.getLogger("BackendAPIClient")


class APIEndpoint(Enum):
    """API endpoint definitions"""
    LOGIN = "/api/v1/auth/login"
    REFRESH = "/api/v1/auth/refresh"
    LOGOUT = "/api/v1/auth/logout"
    LICENSE_VALIDATE = "/api/v1/license/validate"
    LICENSE_INFO = "/api/v1/license/info"
    LICENSE_RENEW = "/api/v1/license/renew"
    MODELS_AVAILABLE = "/api/v1/models/available"
    MODELS_DOWNLOAD = "/api/v1/models/download"
    MODELS_METADATA = "/api/v1/models/metadata"
    PAYMENTS_CREATE = "/api/v1/payments/create"
    PAYMENTS_HISTORY = "/api/v1/payments/history"


@dataclass
class APIResponse:
    """Standard API response structure"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    status_code: int = 200


@dataclass
class LoginCredentials:
    """Login credentials structure"""
    username: str
    password: str
    hardware_fingerprint: Optional[str] = None


@dataclass
class LicenseInfo:
    """License information from backend"""
    license_key: str
    plan: str
    expires_at: str
    max_clients: int
    allowed_models: List[str]
    allowed_features: List[str]
    status: str


@dataclass
class ModelInfo:
    """Model information from backend"""
    model_id: str
    name: str
    description: str
    size_mb: int
    blocks_count: int
    download_url: str
    checksum: str


class BackendAPIClient:
    """
    Backend API client for TikTrue desktop application
    Handles authentication, license validation, and model downloads
    """
    
    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3):
        """
        Initialize API client
        
        Args:
            base_url: Backend server base URL (e.g., "https://api.tiktrue.com")
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        
        # SSL context for secure connections
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        logger.info(f"BackendAPIClient initialized with base URL: {self.base_url}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()
    
    async def start_session(self):
        """Start HTTP session"""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                ssl=self.ssl_context,
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                use_dns_cache=True
            )
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'TikTrue-Desktop/1.0.0',
                    'Content-Type': 'application/json'
                }
            )
            
            logger.debug("HTTP session started")
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("HTTP session closed")
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        headers = {}
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        return headers
    
    async def _make_request(
        self,
        method: str,
        endpoint: APIEndpoint,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        require_auth: bool = True,
        retry_count: int = 0
    ) -> APIResponse:
        """
        Make HTTP request to backend API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint enum
            data: Request body data
            params: URL parameters
            require_auth: Whether authentication is required
            retry_count: Current retry attempt
            
        Returns:
            APIResponse object
        """
        if not self.session:
            await self.start_session()
        
        url = f"{self.base_url}{endpoint.value}"
        headers = {}
        
        if require_auth:
            # Check if token needs refresh
            if await self._token_needs_refresh():
                refresh_result = await self._refresh_access_token()
                if not refresh_result.success:
                    return APIResponse(
                        success=False,
                        error="Authentication required",
                        error_code="AUTH_REQUIRED"
                    )
            
            headers.update(self._get_auth_headers())
        
        try:
            logger.debug(f"Making {method} request to {url}")
            
            async with self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers
            ) as response:
                
                response_text = await response.text()
                
                # Try to parse JSON response
                try:
                    response_data = json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    response_data = {"raw_response": response_text}
                
                if response.status == 200:
                    logger.debug(f"Request successful: {method} {url}")
                    return APIResponse(
                        success=True,
                        data=response_data,
                        status_code=response.status
                    )
                elif response.status == 401 and require_auth and retry_count == 0:
                    # Token might be expired, try to refresh and retry once
                    logger.warning("Received 401, attempting token refresh")
                    refresh_result = await self._refresh_access_token()
                    if refresh_result.success:
                        return await self._make_request(
                            method, endpoint, data, params, require_auth, retry_count + 1
                        )
                
                # Handle error responses
                error_message = response_data.get('error', f'HTTP {response.status}')
                error_code = response_data.get('error_code', f'HTTP_{response.status}')
                
                logger.error(f"Request failed: {method} {url} - {error_message}")
                return APIResponse(
                    success=False,
                    error=error_message,
                    error_code=error_code,
                    status_code=response.status
                )
                
        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {method} {url}")
            if retry_count < self.max_retries:
                logger.info(f"Retrying request ({retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                return await self._make_request(
                    method, endpoint, data, params, require_auth, retry_count + 1
                )
            
            return APIResponse(
                success=False,
                error="Request timeout",
                error_code="TIMEOUT"
            )
            
        except aiohttp.ClientError as e:
            logger.error(f"Client error: {method} {url} - {str(e)}")
            if retry_count < self.max_retries:
                logger.info(f"Retrying request ({retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(2 ** retry_count)
                return await self._make_request(
                    method, endpoint, data, params, require_auth, retry_count + 1
                )
            
            return APIResponse(
                success=False,
                error=f"Network error: {str(e)}",
                error_code="NETWORK_ERROR"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error: {method} {url} - {str(e)}")
            return APIResponse(
                success=False,
                error=f"Unexpected error: {str(e)}",
                error_code="UNEXPECTED_ERROR"
            )
    
    async def _token_needs_refresh(self) -> bool:
        """Check if access token needs refresh"""
        if not self.access_token or not self.token_expires_at:
            return True
        
        # Refresh if token expires in less than 5 minutes
        return datetime.now() + timedelta(minutes=5) >= self.token_expires_at
    
    async def _refresh_access_token(self) -> APIResponse:
        """Refresh access token using refresh token"""
        if not self.refresh_token:
            return APIResponse(
                success=False,
                error="No refresh token available",
                error_code="NO_REFRESH_TOKEN"
            )
        
        response = await self._make_request(
            method="POST",
            endpoint=APIEndpoint.REFRESH,
            data={"refresh_token": self.refresh_token},
            require_auth=False
        )
        
        if response.success and response.data:
            self.access_token = response.data.get('access_token')
            self.refresh_token = response.data.get('refresh_token')
            
            # Parse token expiry
            expires_in = response.data.get('expires_in', 3600)  # Default 1 hour
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info("Access token refreshed successfully")
        
        return response
    
    # Authentication Methods
    
    async def login(self, credentials: LoginCredentials) -> APIResponse:
        """
        Authenticate user with backend server
        
        Args:
            credentials: Login credentials
            
        Returns:
            APIResponse with authentication tokens and user info
        """
        logger.info(f"Attempting login for user: {credentials.username}")
        
        login_data = {
            "username": credentials.username,
            "password": credentials.password,
            "client_type": "desktop",
            "hardware_fingerprint": credentials.hardware_fingerprint
        }
        
        response = await self._make_request(
            method="POST",
            endpoint=APIEndpoint.LOGIN,
            data=login_data,
            require_auth=False
        )
        
        if response.success and response.data:
            # Store authentication tokens
            self.access_token = response.data.get('access_token')
            self.refresh_token = response.data.get('refresh_token')
            
            # Parse token expiry
            expires_in = response.data.get('expires_in', 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info("Login successful")
        else:
            logger.error(f"Login failed: {response.error}")
        
        return response
    
    async def logout(self) -> APIResponse:
        """Logout and invalidate tokens"""
        logger.info("Logging out")
        
        response = await self._make_request(
            method="POST",
            endpoint=APIEndpoint.LOGOUT,
            require_auth=True
        )
        
        # Clear local tokens regardless of response
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        logger.info("Logout completed")
        return response
    
    # License Methods
    
    async def validate_license(self, hardware_fingerprint: str) -> APIResponse:
        """
        Validate user license with backend server
        
        Args:
            hardware_fingerprint: Hardware fingerprint for binding
            
        Returns:
            APIResponse with license validation result
        """
        logger.info("Validating license")
        
        return await self._make_request(
            method="POST",
            endpoint=APIEndpoint.LICENSE_VALIDATE,
            data={"hardware_fingerprint": hardware_fingerprint},
            require_auth=True
        )
    
    async def get_license_info(self) -> APIResponse:
        """
        Get detailed license information
        
        Returns:
            APIResponse with license details
        """
        logger.info("Fetching license information")
        
        return await self._make_request(
            method="GET",
            endpoint=APIEndpoint.LICENSE_INFO,
            require_auth=True
        )
    
    async def renew_license(self, payment_token: str) -> APIResponse:
        """
        Renew license with payment
        
        Args:
            payment_token: Payment processing token
            
        Returns:
            APIResponse with renewal result
        """
        logger.info("Renewing license")
        
        return await self._make_request(
            method="POST",
            endpoint=APIEndpoint.LICENSE_RENEW,
            data={"payment_token": payment_token},
            require_auth=True
        )
    
    # Model Methods
    
    async def get_available_models(self) -> APIResponse:
        """
        Get list of models available to user based on license
        
        Returns:
            APIResponse with available models list
        """
        logger.info("Fetching available models")
        
        return await self._make_request(
            method="GET",
            endpoint=APIEndpoint.MODELS_AVAILABLE,
            require_auth=True
        )
    
    async def get_model_metadata(self, model_id: str) -> APIResponse:
        """
        Get metadata for specific model
        
        Args:
            model_id: Model identifier
            
        Returns:
            APIResponse with model metadata
        """
        logger.info(f"Fetching metadata for model: {model_id}")
        
        return await self._make_request(
            method="GET",
            endpoint=APIEndpoint.MODELS_METADATA,
            params={"model_id": model_id},
            require_auth=True
        )
    
    async def get_model_download_url(self, model_id: str) -> APIResponse:
        """
        Get secure download URL for model
        
        Args:
            model_id: Model identifier
            
        Returns:
            APIResponse with download URL and metadata
        """
        logger.info(f"Getting download URL for model: {model_id}")
        
        return await self._make_request(
            method="GET",
            endpoint=APIEndpoint.MODELS_DOWNLOAD,
            params={"model_id": model_id},
            require_auth=True
        )
    
    async def download_model_file(
        self,
        download_url: str,
        local_path: Path,
        progress_callback: Optional[callable] = None
    ) -> APIResponse:
        """
        Download model file from secure URL
        
        Args:
            download_url: Secure download URL from backend
            local_path: Local file path to save
            progress_callback: Optional progress callback function
            
        Returns:
            APIResponse with download result
        """
        logger.info(f"Downloading model file to: {local_path}")
        
        try:
            if not self.session:
                await self.start_session()
            
            # Create directory if it doesn't exist
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with self.session.get(download_url) as response:
                if response.status != 200:
                    return APIResponse(
                        success=False,
                        error=f"Download failed with status {response.status}",
                        error_code="DOWNLOAD_FAILED"
                    )
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                async with aiofiles.open(local_path, 'wb') as file:
                    async for chunk in response.content.iter_chunked(8192):
                        await file.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(progress, downloaded, total_size)
                
                logger.info(f"Model file downloaded successfully: {local_path}")
                return APIResponse(
                    success=True,
                    data={
                        "local_path": str(local_path),
                        "size_bytes": downloaded
                    }
                )
                
        except Exception as e:
            logger.error(f"Model download failed: {str(e)}")
            return APIResponse(
                success=False,
                error=f"Download error: {str(e)}",
                error_code="DOWNLOAD_ERROR"
            )
    
    # Payment Methods
    
    async def create_payment_session(self, plan: str, duration_months: int) -> APIResponse:
        """
        Create payment session for license purchase/renewal
        
        Args:
            plan: Subscription plan (FREE, PRO, ENT)
            duration_months: Duration in months
            
        Returns:
            APIResponse with payment session details
        """
        logger.info(f"Creating payment session for {plan} plan ({duration_months} months)")
        
        return await self._make_request(
            method="POST",
            endpoint=APIEndpoint.PAYMENTS_CREATE,
            data={
                "plan": plan,
                "duration_months": duration_months
            },
            require_auth=True
        )
    
    async def get_payment_history(self) -> APIResponse:
        """
        Get user's payment history
        
        Returns:
            APIResponse with payment history
        """
        logger.info("Fetching payment history")
        
        return await self._make_request(
            method="GET",
            endpoint=APIEndpoint.PAYMENTS_HISTORY,
            require_auth=True
        )
    
    # Utility Methods
    
    def is_authenticated(self) -> bool:
        """Check if client is authenticated"""
        if not self.access_token or not self.token_expires_at:
            return False
        
        # Check if token expires in less than 5 minutes (same logic as _token_needs_refresh)
        from datetime import datetime, timedelta
        return datetime.now() + timedelta(minutes=5) < self.token_expires_at
    
    async def test_connection(self) -> APIResponse:
        """Test connection to backend server"""
        logger.info("Testing backend connection")
        
        try:
            if not self.session:
                await self.start_session()
            
            # Simple health check - try to access a public endpoint
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    return APIResponse(
                        success=True,
                        data={"status": "connected"}
                    )
                else:
                    return APIResponse(
                        success=False,
                        error=f"Server returned status {response.status}",
                        error_code="CONNECTION_FAILED"
                    )
                    
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return APIResponse(
                success=False,
                error=f"Connection failed: {str(e)}",
                error_code="CONNECTION_ERROR"
            )


# Convenience functions for common operations

async def create_api_client(base_url: str) -> BackendAPIClient:
    """Create and initialize API client"""
    client = BackendAPIClient(base_url)
    await client.start_session()
    return client


async def test_backend_connection(base_url: str) -> bool:
    """Quick test of backend connectivity"""
    async with BackendAPIClient(base_url) as client:
        result = await client.test_connection()
        return result.success


# Example usage
if __name__ == "__main__":
    async def main():
        # Example usage of the API client
        async with BackendAPIClient("https://api.tiktrue.com") as client:
            # Test connection
            connection_test = await client.test_connection()
            print(f"Connection test: {connection_test.success}")
            
            if connection_test.success:
                # Example login
                credentials = LoginCredentials(
                    username="test@example.com",
                    password="password123",
                    hardware_fingerprint="hw_fingerprint_here"
                )
                
                login_result = await client.login(credentials)
                print(f"Login result: {login_result.success}")
                
                if login_result.success:
                    # Get available models
                    models_result = await client.get_available_models()
                    print(f"Available models: {models_result.data}")
    
    # Run example
    asyncio.run(main())