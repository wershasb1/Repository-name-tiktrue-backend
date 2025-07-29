"""
Test for Unified WebSocket Server
Tests both legacy and standard protocol support
"""

import asyncio
import json
import unittest
from datetime import datetime, timedelta
import uuid
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

# Import required modules
from core.protocol_spec import (
    ProtocolManager, MessageType, ErrorCode, InferenceRequest
)
from license_models import LicenseInfo, SubscriptionTier, ValidationStatus
from security.license_validator import LicenseValidator

# Import unified websocket server classes
try:
    from network.unified_websocket_server import UnifiedWebSocketServer, UnifiedClientConnection, create_unified_websocket_server
except ImportError:
    # Fallback: execute file but skip main execution
    with open('network/unified_websocket_server.py', 'r') as f:
        code = f.read()
    # Remove the main execution part
    code_lines = code.split('\n')
    filtered_lines = []
    skip_main = False
    for line in code_lines:
        if 'if __name__ == "__main__":' in line:
            skip_main = True
        if not skip_main:
            filtered_lines.append(line)
    
    exec('\n'.join(filtered_lines))


class TestUnifiedWebSocketServer(unittest.TestCase):
    """Test unified WebSocket server functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.license_validator = LicenseValidator()
        self.protocol_manager = ProtocolManager()
        
        # Create test license
        self.test_license = LicenseInfo(
            license_key="test_unified_key_12345",
            user_id="test_user_123",
            plan_type="PRO",
            expiry_date=(datetime.now() + timedelta(days=30)).isoformat(),
            max_clients=10,
            allowed_models=["test_model", "llama3_1_8b"],
            hardware_fingerprint="test_hardware_123",
            is_active=True,
            created_at=datetime.now().isoformat(),
            last_validated=datetime.now().isoformat(),
            status=ValidationStatus.VALID
        )
    
    def test_server_initialization(self):
        """Test unified server initialization"""
        server = UnifiedWebSocketServer(
            host="localhost",
            port=8707,  # Different port for testing
            license_validator=self.license_validator
        )
        
        self.assertEqual(server.host, "localhost")
        self.assertEqual(server.port, 8707)
        self.assertIsInstance(server.protocol_manager, ProtocolManager)
        self.assertFalse(server.running)
        
        # Test server stats
        stats = server.get_server_stats()
        self.assertIn("running", stats)
        self.assertIn("connected_clients", stats)
        self.assertIn("inference_requests", stats)
        self.assertIn("protocol_requests", stats)
        self.assertFalse(stats["running"])
        self.assertEqual(stats["connected_clients"], 0)
    
    def test_client_connection_management(self):
        """Test unified client connection management"""
        from unittest.mock import Mock
        
        # Create mock websocket
        mock_websocket = Mock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)
        client_id = str(uuid.uuid4())
        
        # Create client connection
        client = UnifiedClientConnection(mock_websocket, client_id)
        
        self.assertEqual(client.client_id, client_id)
        self.assertEqual(client.websocket, mock_websocket)
        self.assertIsInstance(client.connected_at, datetime)
        self.assertEqual(client.request_count, 0)
        self.assertEqual(client.error_count, 0)
        self.assertEqual(len(client.inference_sessions), 0)
        self.assertEqual(client.protocol_mode, "auto")
        
        # Test session management
        session_id = "test_session_123"
        client.add_inference_session(session_id)
        self.assertIn(session_id, client.inference_sessions)
        
        client.remove_inference_session(session_id)
        self.assertNotIn(session_id, client.inference_sessions)
    
    def test_protocol_detection(self):
        """Test protocol message detection"""
        server = UnifiedWebSocketServer(
            host="localhost",
            port=8708,
            license_validator=self.license_validator
        )
        
        # Test standard protocol message detection
        standard_message = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.INFERENCE_REQUEST.value,
                "protocol_version": "2.0",
                "timestamp": datetime.now().isoformat()
            },
            "model_id": "test_model",
            "prompt": "Test prompt"
        }
        
        self.assertTrue(server._is_standard_protocol_message(standard_message))
        
        # Test legacy message detection
        legacy_message = {
            "session_id": "test_session",
            "step": 0,
            "input_tensors": {"input_ids": [1, 2, 3]}
        }
        
        self.assertFalse(server._is_standard_protocol_message(legacy_message))
        
        # Test invalid message
        invalid_message = {
            "random_field": "value"
        }
        
        self.assertFalse(server._is_standard_protocol_message(invalid_message))
    
    def test_message_handlers_setup(self):
        """Test message handlers are properly set up"""
        server = UnifiedWebSocketServer(
            host="localhost",
            port=8709,
            license_validator=self.license_validator
        )
        
        expected_handlers = {
            MessageType.INFERENCE_REQUEST,
            MessageType.HEARTBEAT,
            MessageType.AUTHENTICATION,
            MessageType.LICENSE_CHECK
        }
        
        self.assertEqual(set(server.protocol_handlers.keys()), expected_handlers)
        
        # Verify handlers are callable
        for message_type, handler in server.protocol_handlers.items():
            self.assertTrue(callable(handler))
    
    def test_server_load_calculation(self):
        """Test server load calculation"""
        server = UnifiedWebSocketServer(
            host="localhost",
            port=8710,
            license_validator=self.license_validator
        )
        
        # No clients
        self.assertEqual(server._get_server_load(), 0.0)
        
        # Add mock clients
        from unittest.mock import Mock
        for i in range(5):
            client_id = f"client_{i}"
            mock_websocket = Mock()
            mock_websocket.remote_address = ("127.0.0.1", 12345 + i)
            server.clients[client_id] = UnifiedClientConnection(mock_websocket, client_id)
        
        # Should be 5 * 10 = 50%
        self.assertEqual(server._get_server_load(), 50.0)
        
        # Test maximum load (100%)
        for i in range(10):
            client_id = f"client_extra_{i}"
            mock_websocket = Mock()
            mock_websocket.remote_address = ("127.0.0.1", 12355 + i)
            server.clients[client_id] = UnifiedClientConnection(mock_websocket, client_id)
        
        # Should cap at 100%
        self.assertEqual(server._get_server_load(), 100.0)
    
    def test_comprehensive_stats(self):
        """Test comprehensive server statistics"""
        server = UnifiedWebSocketServer(
            host="localhost",
            port=8711,
            license_validator=self.license_validator
        )
        
        # Simulate some activity
        server.total_connections = 10
        server.total_messages = 50
        server.inference_requests = 30
        server.protocol_requests = 20
        server.total_errors = 2
        
        stats = server.get_server_stats()
        
        expected_keys = {
            "running", "host", "port", "uptime_seconds", "connected_clients",
            "active_sessions", "total_connections", "total_messages", 
            "total_errors", "inference_requests", "protocol_requests", "protocol_stats"
        }
        
        self.assertEqual(set(stats.keys()), expected_keys)
        self.assertEqual(stats["total_connections"], 10)
        self.assertEqual(stats["total_messages"], 50)
        self.assertEqual(stats["inference_requests"], 30)
        self.assertEqual(stats["protocol_requests"], 20)
        self.assertEqual(stats["total_errors"], 2)
    
    def test_utility_functions(self):
        """Test utility functions"""
        # Test server creation utility
        server = create_unified_websocket_server(host="test_host", port=9999)
        
        self.assertIsInstance(server, UnifiedWebSocketServer)
        self.assertEqual(server.host, "test_host")
        self.assertEqual(server.port, 9999)
        
        # Test with custom license validator
        from unittest.mock import Mock
        mock_validator = Mock(spec=LicenseValidator)
        server_with_validator = create_unified_websocket_server(license_validator=mock_validator)
        
        self.assertEqual(server_with_validator.license_validator, mock_validator)


class TestProtocolCompatibility(unittest.TestCase):
    """Test protocol compatibility between legacy and standard formats"""
    
    def setUp(self):
        """Set up test environment"""
        self.protocol_manager = ProtocolManager()
    
    def test_legacy_message_format(self):
        """Test legacy message format handling"""
        legacy_message = {
            "session_id": "legacy_session_123",
            "step": 5,
            "input_tensors": {
                "input_ids": [1, 2, 3, 4, 5],
                "attention_mask": [1, 1, 1, 1, 1]
            },
            "network_id": "test_network"
        }
        
        # Should be valid JSON
        json_str = json.dumps(legacy_message)
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed["session_id"], "legacy_session_123")
        self.assertEqual(parsed["step"], 5)
        self.assertIn("input_tensors", parsed)
    
    def test_standard_protocol_message_format(self):
        """Test standard protocol message format"""
        request = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Test prompt for compatibility",
            max_tokens=100,
            temperature=0.8
        )
        
        # Serialize to JSON
        json_str = self.protocol_manager.serialize_message(request)
        parsed = json.loads(json_str)
        
        # Should have standard protocol structure
        self.assertIn("header", parsed)
        self.assertIn("model_id", parsed)
        self.assertIn("prompt", parsed)
        self.assertEqual(parsed["header"]["message_type"], "inference_request")
        self.assertEqual(parsed["header"]["protocol_version"], "2.0")
    
    def test_backward_compatibility(self):
        """Test that both formats can coexist"""
        # Legacy format
        legacy = {
            "session_id": "test",
            "input_tensors": {"data": "legacy"}
        }
        
        # Standard format
        standard = {
            "header": {
                "message_type": "inference_request",
                "protocol_version": "2.0"
            },
            "model_id": "test",
            "prompt": "standard"
        }
        
        # Both should be valid JSON
        legacy_json = json.dumps(legacy)
        standard_json = json.dumps(standard)
        
        self.assertIsInstance(json.loads(legacy_json), dict)
        self.assertIsInstance(json.loads(standard_json), dict)
        
        # Should be distinguishable
        legacy_parsed = json.loads(legacy_json)
        standard_parsed = json.loads(standard_json)
        
        self.assertNotIn("header", legacy_parsed)
        self.assertIn("header", standard_parsed)


if __name__ == "__main__":
    print("Running Unified WebSocket Server Tests...")
    unittest.main(verbosity=2)