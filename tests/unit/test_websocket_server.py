"""
Test suite for WebSocket Server Implementation
Tests WebSocket communication protocol with license validation
"""

import asyncio
import json
import unittest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import uuid

# Import modules to test
from network.websocket_server import WebSocketServer, ClientConnection, create_websocket_server
from core.protocol_spec import (
    ProtocolManager, MessageType, ErrorCode, InferenceRequest, 
    InferenceResponse, HeartbeatMessage, ErrorMessage
)
from license_models import LicenseInfo, SubscriptionTier, ValidationStatus
from security.license_validator import LicenseValidator


class TestClientConnection(unittest.TestCase):
    """Test ClientConnection class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_websocket = Mock()
        self.client_id = str(uuid.uuid4())
        self.client = ClientConnection(self.mock_websocket, self.client_id)
    
    def test_client_initialization(self):
        """Test client connection initialization"""
        self.assertEqual(self.client.client_id, self.client_id)
        self.assertEqual(self.client.websocket, self.mock_websocket)
        self.assertIsInstance(self.client.connected_at, datetime)
        self.assertIsInstance(self.client.last_heartbeat, datetime)
        self.assertIsNone(self.client.license_info)
        self.assertEqual(self.client.request_count, 0)
        self.assertEqual(self.client.error_count, 0)
    
    def test_update_heartbeat(self):
        """Test heartbeat update"""
        old_heartbeat = self.client.last_heartbeat
        asyncio.sleep(0.01)  # Small delay
        self.client.update_heartbeat()
        self.assertGreater(self.client.last_heartbeat, old_heartbeat)
    
    @patch('websocket_server.json.dumps')
    async def test_send_message_dict(self, mock_json_dumps):
        """Test sending message with dict object"""
        mock_json_dumps.return_value = '{"test": "message"}'
        self.mock_websocket.send = AsyncMock()
        
        message = {"test": "message"}
        await self.client.send_message(message)
        
        mock_json_dumps.assert_called_once()
        self.mock_websocket.send.assert_called_once_with('{"test": "message"}')
    
    @patch('websocket_server.json.dumps')
    async def test_send_message_object(self, mock_json_dumps):
        """Test sending message with object having __dict__"""
        mock_json_dumps.return_value = '{"attr": "value"}'
        self.mock_websocket.send = AsyncMock()
        
        class TestObject:
            def __init__(self):
                self.attr = "value"
        
        message = TestObject()
        await self.client.send_message(message)
        
        mock_json_dumps.assert_called_once()
        self.mock_websocket.send.assert_called_once_with('{"attr": "value"}')


class TestWebSocketServer(unittest.TestCase):
    """Test WebSocketServer class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_license_validator = Mock(spec=LicenseValidator)
        self.server = WebSocketServer(
            host="localhost",
            port=8703,  # Different port for testing
            license_validator=self.mock_license_validator
        )
    
    def test_server_initialization(self):
        """Test server initialization"""
        self.assertEqual(self.server.host, "localhost")
        self.assertEqual(self.server.port, 8703)
        self.assertEqual(self.server.license_validator, self.mock_license_validator)
        self.assertIsInstance(self.server.protocol_manager, ProtocolManager)
        self.assertFalse(self.server.running)
        self.assertEqual(len(self.server.clients), 0)
        self.assertEqual(len(self.server.active_sessions), 0)
    
    def test_message_handlers_setup(self):
        """Test message handlers are properly set up"""
        expected_handlers = {
            MessageType.INFERENCE_REQUEST,
            MessageType.HEARTBEAT,
            MessageType.AUTHENTICATION,
            MessageType.LICENSE_CHECK
        }
        
        self.assertEqual(set(self.server.message_handlers.keys()), expected_handlers)
    
    def test_get_server_load(self):
        """Test server load calculation"""
        # No clients
        self.assertEqual(self.server._get_server_load(), 0.0)
        
        # Add mock clients
        for i in range(5):
            client_id = f"client_{i}"
            mock_websocket = Mock()
            self.server.clients[client_id] = ClientConnection(mock_websocket, client_id)
        
        # Should be 5 * 10 = 50%
        self.assertEqual(self.server._get_server_load(), 50.0)
        
        # Test maximum load (100%)
        for i in range(10):
            client_id = f"client_extra_{i}"
            mock_websocket = Mock()
            self.server.clients[client_id] = ClientConnection(mock_websocket, client_id)
        
        # Should cap at 100%
        self.assertEqual(self.server._get_server_load(), 100.0)
    
    @patch('websocket_server.psutil')
    def test_get_available_memory_with_psutil(self, mock_psutil):
        """Test memory calculation with psutil available"""
        mock_psutil.virtual_memory.return_value.available = 2048 * 1024 * 1024  # 2GB
        
        memory = self.server._get_available_memory()
        self.assertEqual(memory, 2048)
    
    @patch('websocket_server.psutil', side_effect=ImportError)
    def test_get_available_memory_without_psutil(self, mock_psutil):
        """Test memory calculation without psutil"""
        memory = self.server._get_available_memory()
        self.assertEqual(memory, 1024)  # Default value
    
    def test_get_server_stats_not_running(self):
        """Test server stats when not running"""
        stats = self.server.get_server_stats()
        
        expected_keys = {
            "running", "host", "port", "uptime_seconds", "connected_clients",
            "active_sessions", "total_connections", "total_messages", 
            "total_errors", "protocol_stats"
        }
        
        self.assertEqual(set(stats.keys()), expected_keys)
        self.assertFalse(stats["running"])
        self.assertEqual(stats["host"], "localhost")
        self.assertEqual(stats["port"], 8703)
        self.assertIsNone(stats["uptime_seconds"])
        self.assertEqual(stats["connected_clients"], 0)
    
    def test_get_server_stats_running(self):
        """Test server stats when running"""
        self.server.running = True
        self.server.start_time = datetime.now() - timedelta(seconds=60)
        
        stats = self.server.get_server_stats()
        
        self.assertTrue(stats["running"])
        self.assertIsNotNone(stats["uptime_seconds"])
        self.assertGreater(stats["uptime_seconds"], 50)  # Should be around 60 seconds
    
    def test_set_callbacks(self):
        """Test setting callback functions"""
        mock_inference_handler = Mock()
        mock_connected_callback = Mock()
        mock_disconnected_callback = Mock()
        
        self.server.set_inference_handler(mock_inference_handler)
        self.server.set_client_connected_callback(mock_connected_callback)
        self.server.set_client_disconnected_callback(mock_disconnected_callback)
        
        self.assertEqual(self.server.on_inference_request, mock_inference_handler)
        self.assertEqual(self.server.on_client_connected, mock_connected_callback)
        self.assertEqual(self.server.on_client_disconnected, mock_disconnected_callback)


class TestWebSocketServerMessageHandling(unittest.IsolatedAsyncioTestCase):
    """Test WebSocket server message handling"""
    
    async def asyncSetUp(self):
        """Set up async test fixtures"""
        self.mock_license_validator = Mock(spec=LicenseValidator)
        self.server = WebSocketServer(
            host="localhost",
            port=8704,
            license_validator=self.mock_license_validator
        )
        
        # Create mock client
        self.mock_websocket = Mock()
        self.client_id = str(uuid.uuid4())
        self.client = ClientConnection(self.mock_websocket, self.client_id)
        self.client.send_message = AsyncMock()
        
        # Add client to server
        self.server.clients[self.client_id] = self.client
    
    async def test_process_message_invalid_json(self):
        """Test processing invalid JSON message"""
        invalid_json = "{ invalid json }"
        
        with patch.object(self.server, '_send_error', new_callable=AsyncMock) as mock_send_error:
            await self.server._process_message(self.client, invalid_json)
            
            mock_send_error.assert_called_once()
            args = mock_send_error.call_args[0]
            self.assertEqual(args[0], self.client)
            self.assertEqual(args[1], ErrorCode.VALIDATION_ERROR)
            self.assertIn("Invalid JSON", args[2])
    
    async def test_process_message_validation_failure(self):
        """Test processing message that fails validation"""
        invalid_message = json.dumps({"invalid": "message"})
        
        with patch.object(self.server.protocol_validator, 'validate_message', return_value=(False, "Validation error")):
            with patch.object(self.server, '_send_error', new_callable=AsyncMock) as mock_send_error:
                await self.server._process_message(self.client, invalid_message)
                
                mock_send_error.assert_called_once()
                args = mock_send_error.call_args[0]
                self.assertEqual(args[1], ErrorCode.VALIDATION_ERROR)
                self.assertIn("Message validation failed", args[2])
    
    async def test_process_message_unknown_type(self):
        """Test processing message with unknown type"""
        message = {
            "header": {
                "message_type": "unknown_type",
                "message_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat()
            }
        }
        
        with patch.object(self.server.protocol_validator, 'validate_message', return_value=(True, None)):
            with patch.object(self.server, '_send_error', new_callable=AsyncMock) as mock_send_error:
                await self.server._process_message(self.client, json.dumps(message))
                
                mock_send_error.assert_called_once()
                args = mock_send_error.call_args[0]
                self.assertEqual(args[1], ErrorCode.INVALID_REQUEST)
                self.assertIn("Unknown message type", args[2])
    
    async def test_handle_inference_request_success(self):
        """Test successful inference request handling"""
        # Create valid license info
        license_info = LicenseInfo(
            license_key="test_key",
            plan=SubscriptionTier.PRO,
            status=ValidationStatus.VALID,
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=10,
            allowed_models=["test_model"],
            allowed_features=["inference"]
        )
        self.client.license_info = license_info
        
        # Create inference request message
        message_dict = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.INFERENCE_REQUEST.value,
                "license_hash": "test_hash"
            },
            "model_id": "test_model",
            "prompt": "Test prompt"
        }
        
        # Mock license validation
        with patch.object(self.server, '_validate_client_license', return_value=True):
            # Mock inference handler
            mock_response = Mock()
            self.server.on_inference_request = AsyncMock(return_value=mock_response)
            
            await self.server._handle_inference_request(self.client, message_dict)
            
            # Verify inference handler was called
            self.server.on_inference_request.assert_called_once()
            
            # Verify response was sent
            self.client.send_message.assert_called_once_with(mock_response)
    
    async def test_handle_inference_request_no_handler(self):
        """Test inference request with no external handler"""
        # Create valid license info
        license_info = LicenseInfo(
            license_key="test_key",
            plan=SubscriptionTier.PRO,
            status=ValidationStatus.VALID,
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=10,
            allowed_models=["test_model"],
            allowed_features=["inference"]
        )
        self.client.license_info = license_info
        
        message_dict = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.INFERENCE_REQUEST.value,
                "license_hash": "test_hash"
            },
            "model_id": "test_model",
            "prompt": "Test prompt"
        }
        
        with patch.object(self.server, '_validate_client_license', return_value=True):
            await self.server._handle_inference_request(self.client, message_dict)
            
            # Should send default test response
            self.client.send_message.assert_called_once()
            sent_response = self.client.send_message.call_args[0][0]
            self.assertIn("test response", sent_response.generated_text)
    
    async def test_handle_heartbeat(self):
        """Test heartbeat message handling"""
        message_dict = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.HEARTBEAT.value
            },
            "worker_id": "test_worker"
        }
        
        old_heartbeat = self.client.last_heartbeat
        await asyncio.sleep(0.01)  # Small delay
        
        await self.server._handle_heartbeat(self.client, message_dict)
        
        # Verify heartbeat was updated
        self.assertGreater(self.client.last_heartbeat, old_heartbeat)
        
        # Verify response was sent
        self.client.send_message.assert_called_once()
    
    async def test_handle_authentication_success(self):
        """Test successful authentication"""
        license_info = LicenseInfo(
            license_key="test_key",
            plan=SubscriptionTier.PRO,
            status=ValidationStatus.VALID,
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=10,
            allowed_models=["test_model"],
            allowed_features=["inference"]
        )
        
        message_dict = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.AUTHENTICATION.value
            },
            "license_key": "test_key"
        }
        
        # Mock successful license validation
        self.mock_security.license_validator.validate_license_key.return_value = license_info
        
        await self.server._handle_authentication(self.client, message_dict)
        
        # Verify license was set on client
        self.assertEqual(self.client.license_info, license_info)
        
        # Verify success response was sent
        self.client.send_message.assert_called_once()
    
    async def test_handle_authentication_failure(self):
        """Test failed authentication"""
        invalid_license = LicenseInfo(
            license_key="invalid_key",
            plan=SubscriptionTier.FREE,
            status=ValidationStatus.INVALID,
            expires_at=datetime.now() - timedelta(days=1),
            max_clients=1,
            allowed_models=[],
            allowed_features=[]
        )
        
        message_dict = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.AUTHENTICATION.value
            },
            "license_key": "invalid_key"
        }
        
        # Mock failed license validation
        self.mock_security.license_validator.validate_license_key.return_value = invalid_license
        
        with patch.object(self.server, '_send_error', new_callable=AsyncMock) as mock_send_error:
            await self.server._handle_authentication(self.client, message_dict)
            
            # Verify error was sent
            mock_send_error.assert_called_once()
            args = mock_send_error.call_args[0]
            self.assertEqual(args[1], ErrorCode.AUTHENTICATION_FAILED)
    
    async def test_validate_client_license_missing_hash(self):
        """Test license validation with missing hash"""
        header = {"message_type": MessageType.INFERENCE_REQUEST.value}
        
        with patch.object(self.server, '_send_error', new_callable=AsyncMock) as mock_send_error:
            result = await self.server._validate_client_license(self.client, header)
            
            self.assertFalse(result)
            mock_send_error.assert_called_once()
    
    async def test_validate_client_license_no_client_info(self):
        """Test license validation with no client license info"""
        header = {
            "message_type": MessageType.INFERENCE_REQUEST.value,
            "license_hash": "test_hash"
        }
        
        # Ensure client has no license info
        self.client.license_info = None
        
        with patch.object(self.server, '_send_error', new_callable=AsyncMock) as mock_send_error:
            result = await self.server._validate_client_license(self.client, header)
            
            self.assertFalse(result)
            mock_send_error.assert_called_once()
    
    async def test_validate_client_license_expired(self):
        """Test license validation with expired license"""
        expired_license = LicenseInfo(
            license_key="expired_key",
            plan=SubscriptionTier.PRO,
            status=ValidationStatus.EXPIRED,
            expires_at=datetime.now() - timedelta(days=1),
            max_clients=10,
            allowed_models=["test_model"],
            allowed_features=["inference"]
        )
        self.client.license_info = expired_license
        
        header = {
            "message_type": MessageType.INFERENCE_REQUEST.value,
            "license_hash": "test_hash"
        }
        
        # Mock expired license validation
        self.mock_security.license_validator.validate_license_key.return_value = expired_license
        
        with patch.object(self.server, '_send_error', new_callable=AsyncMock) as mock_send_error:
            result = await self.server._validate_client_license(self.client, header)
            
            self.assertFalse(result)
            mock_send_error.assert_called_once()


class TestWebSocketServerUtilities(unittest.TestCase):
    """Test utility functions"""
    
    def test_create_websocket_server(self):
        """Test server creation utility"""
        server = create_websocket_server(host="test_host", port=9999)
        
        self.assertIsInstance(server, WebSocketServer)
        self.assertEqual(server.host, "test_host")
        self.assertEqual(server.port, 9999)
    
    def test_create_websocket_server_with_validator(self):
        """Test server creation with custom license validator"""
        mock_validator = Mock(spec=LicenseValidator)
        server = create_websocket_server(license_validator=mock_validator)
        
        self.assertEqual(server.license_validator, mock_validator)


if __name__ == "__main__":
    # Run tests
    unittest.main()