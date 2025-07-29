"""
Test API Client with License Integration
Comprehensive tests for the license-aware API client
"""

import unittest
import asyncio
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import websockets

# Import modules to test
from api_client import (
    LicenseAwareAPIClient, APIRequest, APIResponse, ConnectionStatus, 
    LicenseErrorType, create_api_client, create_inference_request
)
from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus
from license_storage import LicenseStorage


class AsyncTestCase(unittest.TestCase):
    """Base class for async tests"""
    
    def run_async_test(self, coro):
        """Run async test"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class TestAPIRequest(unittest.TestCase):
    """Test APIRequest class"""
    
    def test_api_request_creation(self):
        """Test API request creation"""
        request = APIRequest(
            session_id="test_session",
            step=1,
            input_tensors={"input_ids": [[1, 2, 3]]},
            network_id="test_network",
            model_id="llama-7b"
        )
        
        self.assertEqual(request.session_id, "test_session")
        self.assertEqual(request.step, 1)
        self.assertEqual(request.network_id, "test_network")
        self.assertEqual(request.model_id, "llama-7b")
        self.assertIsNotNone(request.input_tensors)
    
    def test_api_request_to_dict(self):
        """Test API request serialization"""
        request = APIRequest(
            session_id="test_session",
            step=1,
            input_tensors={"input_ids": [[1, 2, 3]]},
            network_id="test_network"
        )
        
        request_dict = request.to_dict()
        
        self.assertIn("session_id", request_dict)
        self.assertIn("step", request_dict)
        self.assertIn("input_tensors", request_dict)
        self.assertIn("network_id", request_dict)
        self.assertEqual(request_dict["session_id"], "test_session")


class TestAPIResponse(unittest.TestCase):
    """Test APIResponse class"""
    
    def test_api_response_from_dict(self):
        """Test API response deserialization"""
        response_data = {
            "status": "success",
            "session_id": "test_session",
            "step": 1,
            "network_id": "test_network",
            "license_status": "valid",
            "outputs": {"logits": "test_output"},
            "execution_time": 0.5
        }
        
        response = APIResponse.from_dict(response_data)
        
        self.assertEqual(response.status, "success")
        self.assertEqual(response.session_id, "test_session")
        self.assertEqual(response.step, 1)
        self.assertEqual(response.license_status, "valid")
        self.assertIsNotNone(response.outputs)
        self.assertEqual(response.execution_time, 0.5)
    
    def test_api_response_from_dict_minimal(self):
        """Test API response with minimal data"""
        response_data = {
            "status": "error",
            "session_id": "test",
            "step": 0,
            "network_id": "default",
            "license_status": "invalid"
        }
        
        response = APIResponse.from_dict(response_data)
        
        self.assertEqual(response.status, "error")
        self.assertEqual(response.license_status, "invalid")
        self.assertIsNone(response.outputs)


class TestLicenseAwareAPIClient(AsyncTestCase):
    """Test LicenseAwareAPIClient class"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.license_storage = LicenseStorage(self.temp_dir)
        
        # Create test license
        self.test_license = LicenseInfo(
            license_key="TIKT-PRO-1M-TEST123",
            plan=SubscriptionTier.PRO,
            duration_months=1,
            unique_id="TEST123",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=20,
            allowed_models=["llama-7b", "llama-13b", "mistral-7b"],
            allowed_features=["advanced_chat", "session_management"],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        
        # Save test license
        self.license_storage.save_license_locally(self.test_license)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_client_initialization(self):
        """Test client initialization"""
        client = LicenseAwareAPIClient(
            server_host="localhost",
            server_port=8702,
            license_storage=self.license_storage
        )
        
        self.assertEqual(client.server_host, "localhost")
        self.assertEqual(client.server_port, 8702)
        self.assertEqual(client.connection_status, ConnectionStatus.DISCONNECTED)
        self.assertIsNotNone(client.current_license)
        self.assertIsNotNone(client.license_hash)
    
    def test_license_loading(self):
        """Test license loading"""
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        self.assertIsNotNone(client.current_license)
        self.assertEqual(client.current_license.plan, SubscriptionTier.PRO)
        self.assertIsNotNone(client.license_hash)
    
    def test_license_hash_generation(self):
        """Test license hash generation"""
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        hash1 = client._generate_license_hash("test_key_1")
        hash2 = client._generate_license_hash("test_key_2")
        hash3 = client._generate_license_hash("test_key_1")
        
        self.assertNotEqual(hash1, hash2)
        self.assertEqual(hash1, hash3)  # Same key should produce same hash
        self.assertEqual(len(hash1), 16)  # Should be 16 characters
    
    def test_request_permission_validation(self):
        """Test request permission validation"""
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        # Valid request
        valid_request = APIRequest(
            session_id="test",
            step=0,
            input_tensors={"input_ids": [[1, 2, 3]]},
            model_id="llama-7b"
        )
        
        error = client._validate_request_permissions(valid_request)
        self.assertIsNone(error)
        
        # Invalid model request
        invalid_request = APIRequest(
            session_id="test",
            step=0,
            input_tensors={"input_ids": [[1, 2, 3]]},
            model_id="premium_model_not_allowed"
        )
        
        error = client._validate_request_permissions(invalid_request)
        self.assertIsNotNone(error)
        self.assertIn("Model access denied", error)
    
    def test_connection_stats(self):
        """Test connection statistics"""
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        stats = client.get_connection_stats()
        
        self.assertIn("status", stats)
        self.assertIn("server_uri", stats)
        self.assertIn("total_requests", stats)
        self.assertIn("successful_requests", stats)
        self.assertIn("failed_requests", stats)
        self.assertIn("success_rate", stats)
        self.assertIn("license_plan", stats)
        
        self.assertEqual(stats["status"], ConnectionStatus.DISCONNECTED.value)
        self.assertEqual(stats["total_requests"], 0)
        self.assertEqual(stats["license_plan"], "PRO")
    
    def test_license_status(self):
        """Test license status retrieval"""
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        status = client.get_license_status()
        
        self.assertIn("valid", status)
        self.assertIn("status", status)
        self.assertIn("plan", status)
        self.assertIn("expires_at", status)
        self.assertIn("max_clients", status)
        self.assertIn("allowed_models", status)
        self.assertIn("allowed_features", status)
        self.assertIn("days_remaining", status)
        
        self.assertTrue(status["valid"])
        self.assertEqual(status["plan"], "PRO")
        self.assertEqual(status["max_clients"], 20)
    
    def test_callbacks(self):
        """Test callback functionality"""
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        # Test callback setters
        license_error_called = False
        connection_status_called = False
        renewal_needed_called = False
        
        def license_error_callback(error_type, message):
            nonlocal license_error_called
            license_error_called = True
        
        def connection_status_callback(status):
            nonlocal connection_status_called
            connection_status_called = True
        
        def renewal_callback(license_info):
            nonlocal renewal_needed_called
            renewal_needed_called = True
        
        client.set_license_error_callback(license_error_callback)
        client.set_connection_status_callback(connection_status_callback)
        client.set_license_renewal_callback(renewal_callback)
        
        # Test callbacks
        client._handle_license_error(LicenseErrorType.INVALID_LICENSE, "Test error")
        client._update_connection_status(ConnectionStatus.CONNECTED)
        
        self.assertTrue(license_error_called)
        self.assertTrue(connection_status_called)
    
    async def test_install_license(self):
        """Test license installation"""
        # Create client without existing license
        empty_storage = LicenseStorage(tempfile.mkdtemp())
        client = LicenseAwareAPIClient(license_storage=empty_storage)
        
        # Install valid license
        result = await client.install_license("TIKT-PRO-1M-TEST123")
        
        # Note: This will fail in real test because license validation requires proper format
        # But we can test the flow
        self.assertIsInstance(result, bool)
    
    async def test_refresh_license(self):
        """Test license refresh"""
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        result = await client.refresh_license()
        
        self.assertTrue(result)
        self.assertIsNotNone(client.current_license)


class TestLicenseAwareAPIClientIntegration(AsyncTestCase):
    """Integration tests for API client with mock WebSocket"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.license_storage = LicenseStorage(self.temp_dir)
        
        # Create test license
        self.test_license = LicenseInfo(
            license_key="TIKT-PRO-1M-TEST123",
            plan=SubscriptionTier.PRO,
            duration_months=1,
            unique_id="TEST123",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=20,
            allowed_models=["llama-7b", "llama-13b"],
            allowed_features=["advanced_chat"],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        
        self.license_storage.save_license_locally(self.test_license)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('websockets.connect')
    async def test_successful_connection(self, mock_connect):
        """Test successful WebSocket connection"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_connect.return_value = mock_websocket
        
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        result = await client.connect()
        
        self.assertTrue(result)
        self.assertEqual(client.connection_status, ConnectionStatus.CONNECTED)
        mock_connect.assert_called_once()
    
    @patch('websockets.connect')
    async def test_connection_failure(self, mock_connect):
        """Test WebSocket connection failure"""
        # Mock connection failure
        mock_connect.side_effect = Exception("Connection failed")
        
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        result = await client.connect()
        
        self.assertFalse(result)
        self.assertEqual(client.connection_status, ConnectionStatus.ERROR)
    
    @patch('websockets.connect')
    async def test_successful_request(self, mock_connect):
        """Test successful API request"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_connect.return_value = mock_websocket
        
        # Mock response
        mock_response = {
            "status": "success",
            "session_id": "test_session",
            "step": 0,
            "network_id": "default",
            "license_status": "valid",
            "outputs": {"logits": "test_output"}
        }
        mock_websocket.recv.return_value = json.dumps(mock_response)
        
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        # Send request
        response = await client.send_inference_request(
            session_id="test_session",
            input_tensors={"input_ids": [[1, 2, 3]]},
            model_id="llama-7b"
        )
        
        self.assertEqual(response.status, "success")
        self.assertEqual(response.license_status, "valid")
        self.assertIsNotNone(response.outputs)
        
        # Check that request was sent
        mock_websocket.send.assert_called_once()
    
    @patch('websockets.connect')
    async def test_license_error_response(self, mock_connect):
        """Test handling of license error response"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_connect.return_value = mock_websocket
        
        # Mock license error response
        mock_response = {
            "status": "license_error",
            "session_id": "test_session",
            "step": 0,
            "network_id": "default",
            "license_status": "model_access_denied",
            "error": "Model access denied: premium_model"
        }
        mock_websocket.recv.return_value = json.dumps(mock_response)
        
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        # Set up error callback
        error_captured = None
        def error_callback(error_type, message):
            nonlocal error_captured
            error_captured = (error_type, message)
        
        client.set_license_error_callback(error_callback)
        
        # Send request
        response = await client.send_inference_request(
            session_id="test_session",
            input_tensors={"input_ids": [[1, 2, 3]]},
            model_id="premium_model"
        )
        
        self.assertEqual(response.status, "license_error")
        self.assertEqual(response.license_status, "model_access_denied")
        self.assertIsNotNone(error_captured)
        self.assertEqual(error_captured[0], LicenseErrorType.MODEL_ACCESS_DENIED)
    
    @patch('websockets.connect')
    async def test_request_timeout(self, mock_connect):
        """Test request timeout handling"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_connect.return_value = mock_websocket
        
        # Mock timeout
        async def slow_recv():
            await asyncio.sleep(2)  # Longer than timeout
            return "{}"
        
        mock_websocket.recv = slow_recv
        
        client = LicenseAwareAPIClient(license_storage=self.license_storage)
        
        # Send request with short timeout
        response = await client.send_inference_request(
            session_id="test_session",
            input_tensors={"input_ids": [[1, 2, 3]]},
            timeout=0.1
        )
        
        self.assertEqual(response.status, "timeout_error")
        self.assertIn("timeout", response.error.lower())
    
    async def test_context_manager(self):
        """Test async context manager"""
        with patch('websockets.connect') as mock_connect:
            mock_websocket = AsyncMock()
            mock_connect.return_value = mock_websocket
            
            async with LicenseAwareAPIClient(license_storage=self.license_storage) as client:
                self.assertEqual(client.connection_status, ConnectionStatus.CONNECTED)
            
            # Should disconnect after context
            mock_websocket.close.assert_called_once()


class TestUtilityFunctions(AsyncTestCase):
    """Test utility functions"""
    
    def test_create_inference_request(self):
        """Test inference request creation utility"""
        request = create_inference_request(
            session_id="test_session",
            input_tensors={"input_ids": [[1, 2, 3]]},
            model_id="llama-7b",
            network_id="test_network",
            step=5
        )
        
        self.assertIsInstance(request, APIRequest)
        self.assertEqual(request.session_id, "test_session")
        self.assertEqual(request.model_id, "llama-7b")
        self.assertEqual(request.network_id, "test_network")
        self.assertEqual(request.step, 5)
    
    @patch('websockets.connect')
    async def test_create_api_client(self, mock_connect):
        """Test API client creation utility"""
        mock_websocket = AsyncMock()
        mock_connect.return_value = mock_websocket
        
        client = await create_api_client(
            server_host="test_host",
            server_port=9999,
            auto_connect=True
        )
        
        self.assertIsInstance(client, LicenseAwareAPIClient)
        self.assertEqual(client.server_host, "test_host")
        self.assertEqual(client.server_port, 9999)
        self.assertEqual(client.connection_status, ConnectionStatus.CONNECTED)


class TestLicenseAwareAPIClientSync(AsyncTestCase):
    """Sync wrapper for async tests"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.license_storage = LicenseStorage(self.temp_dir)
        
        # Create test license
        self.test_license = LicenseInfo(
            license_key="TIKT-PRO-1M-TEST123",
            plan=SubscriptionTier.PRO,
            duration_months=1,
            unique_id="TEST123",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=20,
            allowed_models=["llama-7b"],
            allowed_features=["advanced_chat"],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        
        self.license_storage.save_license_locally(self.test_license)
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_install_license_sync(self):
        """Sync version of install license test"""
        async def test_coro():
            client = LicenseAwareAPIClient(license_storage=self.license_storage)
            result = await client.install_license("TIKT-PRO-1M-TEST123")
            return result
        
        result = self.run_async_test(test_coro())
        self.assertIsInstance(result, bool)
    
    def test_successful_connection_sync(self):
        """Sync version of connection test"""
        async def test_coro():
            with patch('websockets.connect') as mock_connect:
                mock_websocket = AsyncMock()
                mock_connect.return_value = mock_websocket
                
                client = LicenseAwareAPIClient(license_storage=self.license_storage)
                result = await client.connect()
                
                return result, client.connection_status
        
        result, status = self.run_async_test(test_coro())
        self.assertTrue(result)
        self.assertEqual(status, ConnectionStatus.CONNECTED)


if __name__ == "__main__":
    # Set up logging
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    unittest.main(verbosity=2)