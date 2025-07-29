"""
Test suite for Backend API Client
Tests all functionality of the backend API communication module
"""

import asyncio
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# Import the module we're testing
from backend_api_client import (
    BackendAPIClient, APIResponse, LoginCredentials, LicenseInfo, ModelInfo,
    APIEndpoint, create_api_client, test_backend_connection
)


class TestBackendAPIClient:
    """Test cases for BackendAPIClient class"""
    
    @pytest.fixture
    def api_client(self):
        """Create API client for testing"""
        return BackendAPIClient("https://api.test.com")
    
    @pytest.fixture
    def mock_session(self):
        """Mock aiohttp session"""
        session = AsyncMock()
        session.closed = False
        return session
    
    def test_initialization(self):
        """Test API client initialization"""
        client = BackendAPIClient("https://api.test.com", timeout=60, max_retries=5)
        
        assert client.base_url == "https://api.test.com"
        assert client.timeout == 60
        assert client.max_retries == 5
        assert client.session is None
        assert client.access_token is None
        assert client.refresh_token is None
    
    def test_base_url_normalization(self):
        """Test base URL normalization (removes trailing slash)"""
        client = BackendAPIClient("https://api.test.com/")
        assert client.base_url == "https://api.test.com"
    
    @pytest.mark.asyncio
    async def test_session_management(self, api_client):
        """Test HTTP session creation and cleanup"""
        # Test session creation
        await api_client.start_session()
        assert api_client.session is not None
        
        # Test session cleanup
        await api_client.close_session()
        # Note: We can't easily test if session is actually closed without mocking
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality"""
        async with BackendAPIClient("https://api.test.com") as client:
            assert client.session is not None
        # Session should be closed after context exit
    
    def test_auth_headers(self, api_client):
        """Test authentication header generation"""
        # No token
        headers = api_client._get_auth_headers()
        assert headers == {}
        
        # With token
        api_client.access_token = "test_token_123"
        headers = api_client._get_auth_headers()
        assert headers == {"Authorization": "Bearer test_token_123"}
    
    @pytest.mark.asyncio
    async def test_token_needs_refresh(self, api_client):
        """Test token refresh logic"""
        # No token
        assert await api_client._token_needs_refresh() == True
        
        # Token expires soon
        api_client.access_token = "test_token"
        api_client.token_expires_at = datetime.now() + timedelta(minutes=2)
        assert await api_client._token_needs_refresh() == True
        
        # Token valid for longer
        api_client.token_expires_at = datetime.now() + timedelta(hours=1)
        assert await api_client._token_needs_refresh() == False
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, api_client, mock_session):
        """Test successful API request"""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value='{"result": "success"}')
        
        # Properly mock the async context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context_manager
        
        api_client.session = mock_session
        
        response = await api_client._make_request(
            method="GET",
            endpoint=APIEndpoint.LICENSE_INFO,
            require_auth=False
        )
        
        assert response.success == True
        assert response.data == {"result": "success"}
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_make_request_error(self, api_client, mock_session):
        """Test API request with error response"""
        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value='{"error": "Bad request", "error_code": "BAD_REQUEST"}')
        
        # Properly mock the async context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context_manager
        
        api_client.session = mock_session
        
        response = await api_client._make_request(
            method="POST",
            endpoint=APIEndpoint.LOGIN,
            require_auth=False
        )
        
        assert response.success == False
        assert response.error == "Bad request"
        assert response.error_code == "BAD_REQUEST"
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_login_success(self, api_client, mock_session):
        """Test successful login"""
        # Mock successful login response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps({
            "access_token": "access_123",
            "refresh_token": "refresh_456",
            "expires_in": 3600,
            "user_info": {"username": "test@example.com"}
        }))
        
        # Properly mock the async context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context_manager
        
        api_client.session = mock_session
        
        credentials = LoginCredentials(
            username="test@example.com",
            password="password123",
            hardware_fingerprint="hw_123"
        )
        
        response = await api_client.login(credentials)
        
        assert response.success == True
        assert api_client.access_token == "access_123"
        assert api_client.refresh_token == "refresh_456"
        assert api_client.token_expires_at is not None
    
    @pytest.mark.asyncio
    async def test_login_failure(self, api_client, mock_session):
        """Test failed login"""
        # Mock failed login response
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value='{"error": "Invalid credentials", "error_code": "INVALID_CREDENTIALS"}')
        
        # Properly mock the async context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context_manager
        
        api_client.session = mock_session
        
        credentials = LoginCredentials(
            username="test@example.com",
            password="wrong_password"
        )
        
        response = await api_client.login(credentials)
        
        assert response.success == False
        assert response.error == "Invalid credentials"
        assert api_client.access_token is None
    
    @pytest.mark.asyncio
    async def test_logout(self, api_client, mock_session):
        """Test logout functionality"""
        # Set up authenticated state
        api_client.access_token = "test_token"
        api_client.refresh_token = "refresh_token"
        api_client.token_expires_at = datetime.now() + timedelta(hours=1)
        
        # Mock logout response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value='{"result": "logged_out"}')
        
        # Properly mock the async context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context_manager
        
        api_client.session = mock_session
        
        response = await api_client.logout()
        
        # Tokens should be cleared regardless of response
        assert api_client.access_token is None
        assert api_client.refresh_token is None
        assert api_client.token_expires_at is None
    
    @pytest.mark.asyncio
    async def test_get_available_models(self, api_client, mock_session):
        """Test getting available models"""
        # Mock models response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps({
            "models": [
                {
                    "model_id": "llama3_1_8b_fp16",
                    "name": "Llama 3.1 8B FP16",
                    "description": "High-quality model",
                    "size_mb": 15000,
                    "blocks_count": 33
                }
            ]
        }))
        
        # Properly mock the async context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context_manager
        api_client.session = mock_session
        api_client.access_token = "valid_token"
        api_client.token_expires_at = datetime.now() + timedelta(hours=1)
        
        response = await api_client.get_available_models()
        
        assert response.success == True
        assert "models" in response.data
        assert len(response.data["models"]) == 1
    
    @pytest.mark.asyncio
    async def test_download_model_file(self, api_client, mock_session):
        """Test model file download"""
        # Create temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            # Mock download response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-length': '1024'}
            
            # Mock content chunks
            test_content = b"test model data" * 64  # 1024 bytes
            chunks = [test_content[i:i+256] for i in range(0, len(test_content), 256)]
            mock_response.content.iter_chunked.return_value = chunks.__iter__()
            
            # Properly mock the async context manager for download
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context_manager.__aexit__ = AsyncMock(return_value=None)
            mock_session.get.return_value = mock_context_manager
            
            api_client.session = mock_session
            
            # Track progress
            progress_calls = []
            def progress_callback(progress, downloaded, total):
                progress_calls.append((progress, downloaded, total))
            
            response = await api_client.download_model_file(
                download_url="https://secure.download.url/model.bin",
                local_path=temp_path,
                progress_callback=progress_callback
            )
            
            assert response.success == True
            assert response.data["local_path"] == str(temp_path)
            assert response.data["size_bytes"] == 1024
            assert len(progress_calls) > 0  # Progress callback was called
            
        finally:
            # Clean up
            if temp_path.exists():
                temp_path.unlink()
    
    @pytest.mark.asyncio
    async def test_validate_license(self, api_client, mock_session):
        """Test license validation"""
        # Mock license validation response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps({
            "valid": True,
            "license_info": {
                "plan": "PRO",
                "expires_at": "2024-12-31T23:59:59",
                "max_clients": 20
            }
        }))
        
        # Properly mock the async context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_context_manager
        api_client.session = mock_session
        api_client.access_token = "valid_token"
        api_client.token_expires_at = datetime.now() + timedelta(hours=1)
        
        response = await api_client.validate_license("hw_fingerprint_123")
        
        assert response.success == True
        assert response.data["valid"] == True
    
    def test_is_authenticated(self, api_client):
        """Test authentication status check"""
        # Not authenticated
        assert api_client.is_authenticated() == False
        
        # Authenticated with valid token
        api_client.access_token = "valid_token"
        api_client.token_expires_at = datetime.now() + timedelta(hours=1)
        assert api_client.is_authenticated() == True
        
        # Token expired
        api_client.token_expires_at = datetime.now() - timedelta(hours=1)
        assert api_client.is_authenticated() == False
    
    @pytest.mark.asyncio
    async def test_connection_test(self, api_client, mock_session):
        """Test backend connection testing"""
        # Mock health check response
        mock_response = AsyncMock()
        mock_response.status = 200
        
        # Properly mock the async context manager
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.get.return_value = mock_context_manager
        
        api_client.session = mock_session
        
        response = await api_client.test_connection()
        
        assert response.success == True
        assert response.data["status"] == "connected"


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @pytest.mark.asyncio
    async def test_create_api_client(self):
        """Test API client creation function"""
        with patch('backend_api_client.BackendAPIClient.start_session') as mock_start:
            client = await create_api_client("https://api.test.com")
            assert isinstance(client, BackendAPIClient)
            mock_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_test_backend_connection(self):
        """Test backend connection test function"""
        with patch('backend_api_client.BackendAPIClient.test_connection') as mock_test:
            mock_test.return_value = APIResponse(success=True)
            
            result = await test_backend_connection("https://api.test.com")
            assert result == True
            
            mock_test.return_value = APIResponse(success=False)
            result = await test_backend_connection("https://api.test.com")
            assert result == False


class TestDataClasses:
    """Test data classes"""
    
    def test_api_response(self):
        """Test APIResponse data class"""
        # Success response
        response = APIResponse(success=True, data={"key": "value"})
        assert response.success == True
        assert response.data == {"key": "value"}
        assert response.error is None
        
        # Error response
        response = APIResponse(
            success=False,
            error="Something went wrong",
            error_code="ERROR_CODE",
            status_code=400
        )
        assert response.success == False
        assert response.error == "Something went wrong"
        assert response.error_code == "ERROR_CODE"
        assert response.status_code == 400
    
    def test_login_credentials(self):
        """Test LoginCredentials data class"""
        credentials = LoginCredentials(
            username="test@example.com",
            password="password123",
            hardware_fingerprint="hw_123"
        )
        
        assert credentials.username == "test@example.com"
        assert credentials.password == "password123"
        assert credentials.hardware_fingerprint == "hw_123"
    
    def test_license_info(self):
        """Test LicenseInfo data class"""
        license_info = LicenseInfo(
            license_key="TIKT-PRO-12M-ABC123",
            plan="PRO",
            expires_at="2024-12-31T23:59:59",
            max_clients=20,
            allowed_models=["llama3_1_8b_fp16"],
            allowed_features=["advanced_chat"],
            status="active"
        )
        
        assert license_info.plan == "PRO"
        assert license_info.max_clients == 20
        assert len(license_info.allowed_models) == 1
    
    def test_model_info(self):
        """Test ModelInfo data class"""
        model_info = ModelInfo(
            model_id="llama3_1_8b_fp16",
            name="Llama 3.1 8B FP16",
            description="High-quality model",
            size_mb=15000,
            blocks_count=33,
            download_url="https://secure.url",
            checksum="abc123"
        )
        
        assert model_info.model_id == "llama3_1_8b_fp16"
        assert model_info.blocks_count == 33
        assert model_info.size_mb == 15000


# Integration test (requires actual backend server)
@pytest.mark.integration
class TestIntegration:
    """Integration tests - require actual backend server"""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow with real backend"""
        # This test would require a real backend server
        # Skip if BACKEND_URL environment variable is not set
        import os
        backend_url = os.getenv('BACKEND_URL')
        
        if not backend_url:
            pytest.skip("BACKEND_URL not set - skipping integration test")
        
        async with BackendAPIClient(backend_url) as client:
            # Test connection
            connection_result = await client.test_connection()
            assert connection_result.success == True
            
            # Additional integration tests would go here
            # (login with test credentials, download test model, etc.)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])