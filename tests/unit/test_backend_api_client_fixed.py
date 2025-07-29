"""
Fixed Test suite for Backend API Client
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


class TestBackendAPIClientFixed:
    """Fixed test cases for BackendAPIClient class"""
    
    @pytest.fixture
    def api_client(self):
        """Create API client for testing"""
        return BackendAPIClient("https://api.test.com")
    
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
    
    @pytest.mark.asyncio
    async def test_make_request_with_mock(self, api_client):
        """Test API request with proper mocking"""
        # Create a proper mock session
        mock_session = AsyncMock()
        
        # Mock the response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value='{"result": "success"}')
        
        # Mock the context manager properly
        mock_session.request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.request.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Set the mock session
        api_client.session = mock_session
        
        # Make the request
        response = await api_client._make_request(
            method="GET",
            endpoint=APIEndpoint.LICENSE_INFO,
            require_auth=False
        )
        
        # Verify the response
        assert response.success == True
        assert response.data == {"result": "success"}
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_login_with_mock(self, api_client):
        """Test login with proper mocking"""
        # Create a proper mock session
        mock_session = AsyncMock()
        
        # Mock the response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps({
            "access_token": "access_123",
            "refresh_token": "refresh_456",
            "expires_in": 3600,
            "user_info": {"username": "test@example.com"}
        }))
        
        # Mock the context manager properly
        mock_session.request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.request.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Set the mock session
        api_client.session = mock_session
        
        # Create credentials
        credentials = LoginCredentials(
            username="test@example.com",
            password="password123",
            hardware_fingerprint="hw_123"
        )
        
        # Perform login
        response = await api_client.login(credentials)
        
        # Verify the response
        assert response.success == True
        assert api_client.access_token == "access_123"
        assert api_client.refresh_token == "refresh_456"
        assert api_client.token_expires_at is not None


class TestDataClassesFixed:
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


class TestConvenienceFunctionsFixed:
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


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])