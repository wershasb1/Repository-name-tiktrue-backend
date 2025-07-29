"""
Integration test for WebSocket communication protocol
Tests end-to-end WebSocket communication with license validation
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
    ProtocolManager, MessageType, ErrorCode, InferenceRequest, 
    InferenceResponse, HeartbeatMessage
)
from license_models import LicenseInfo, SubscriptionTier, ValidationStatus
from security.license_validator import LicenseValidator

# Execute websocket_server.py to get the classes
exec(open('websocket_server.py').read())


class TestWebSocketIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for WebSocket communication"""
    
    async def asyncSetUp(self):
        """Set up test environment"""
        self.license_validator = LicenseValidator()
        self.protocol_manager = ProtocolManager()
        
        # Create test license
        self.test_license = LicenseInfo(
            license_key="test_integration_key_12345",
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
    
    async def test_protocol_message_creation_and_validation(self):
        """Test creating and validating protocol messages"""
        # Test inference request
        request = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Hello, world!",
            license_info=self.test_license,
            max_tokens=50,
            temperature=0.8
        )
        
        self.assertIsInstance(request, InferenceRequest)
        self.assertEqual(request.model_id, "test_model")
        self.assertEqual(request.prompt, "Hello, world!")
        self.assertEqual(request.max_tokens, 50)
        self.assertEqual(request.temperature, 0.8)
        
        # Test serialization
        serialized = self.protocol_manager.serialize_message(request)
        self.assertIsInstance(serialized, str)
        
        # Test deserialization
        deserialized = self.protocol_manager.deserialize_message(serialized)
        self.assertIsInstance(deserialized, dict)
        
        # Test validation
        is_valid, error = self.protocol_manager.validate_message(deserialized)
        self.assertTrue(is_valid, f"Validation failed: {error}")
    
    async def test_inference_response_creation(self):
        """Test creating inference response"""
        request_id = str(uuid.uuid4())
        
        response = self.protocol_manager.create_inference_response(
            request_id=request_id,
            model_id="test_model",
            generated_text="Hello! How can I help you today?",
            license_info=self.test_license,
            processing_time_ms=150
        )
        
        self.assertIsInstance(response, InferenceResponse)
        self.assertEqual(response.request_id, request_id)
        self.assertEqual(response.model_id, "test_model")
        self.assertEqual(response.generated_text, "Hello! How can I help you today?")
        self.assertEqual(response.processing_time_ms, 150)
        
        # Test serialization and validation
        serialized = self.protocol_manager.serialize_message(response)
        deserialized = self.protocol_manager.deserialize_message(serialized)
        is_valid, error = self.protocol_manager.validate_message(deserialized)
        self.assertTrue(is_valid, f"Response validation failed: {error}")
    
    async def test_heartbeat_message_creation(self):
        """Test creating heartbeat message"""
        heartbeat = self.protocol_manager.create_heartbeat(
            worker_id="test_worker_1",
            license_info=self.test_license,
            status="healthy",
            load_percentage=25.5,
            available_memory_mb=2048,
            active_sessions=3
        )
        
        self.assertIsInstance(heartbeat, HeartbeatMessage)
        self.assertEqual(heartbeat.worker_id, "test_worker_1")
        self.assertEqual(heartbeat.status, "healthy")
        self.assertEqual(heartbeat.load_percentage, 25.5)
        self.assertEqual(heartbeat.available_memory_mb, 2048)
        self.assertEqual(heartbeat.active_sessions, 3)
        
        # Test serialization and validation
        serialized = self.protocol_manager.serialize_message(heartbeat)
        deserialized = self.protocol_manager.deserialize_message(serialized)
        is_valid, error = self.protocol_manager.validate_message(deserialized)
        self.assertTrue(is_valid, f"Heartbeat validation failed: {error}")
    
    async def test_error_message_creation(self):
        """Test creating error message"""
        error_msg = self.protocol_manager.create_error_message(
            error_code=ErrorCode.LICENSE_EXPIRED,
            error_message="License has expired",
            license_info=self.test_license,
            details={"expires_at": "2024-01-01T00:00:00"},
            recovery_suggestions=["Renew your license", "Contact support"]
        )
        
        self.assertEqual(error_msg.error_code, ErrorCode.LICENSE_EXPIRED)
        self.assertEqual(error_msg.error_message, "License has expired")
        self.assertIn("expires_at", error_msg.details)
        self.assertEqual(len(error_msg.recovery_suggestions), 2)
        
        # Test serialization and validation
        serialized = self.protocol_manager.serialize_message(error_msg)
        deserialized = self.protocol_manager.deserialize_message(serialized)
        is_valid, error = self.protocol_manager.validate_message(deserialized)
        self.assertTrue(is_valid, f"Error message validation failed: {error}")
    
    async def test_websocket_server_initialization(self):
        """Test WebSocket server initialization"""
        server = WebSocketServer(
            host="localhost",
            port=8705,  # Different port for testing
            license_validator=self.license_validator
        )
        
        self.assertEqual(server.host, "localhost")
        self.assertEqual(server.port, 8705)
        self.assertIsInstance(server.protocol_manager, ProtocolManager)
        self.assertFalse(server.running)
        
        # Test server stats
        stats = server.get_server_stats()
        self.assertIn("running", stats)
        self.assertIn("connected_clients", stats)
        self.assertIn("protocol_stats", stats)
        self.assertFalse(stats["running"])
        self.assertEqual(stats["connected_clients"], 0)
    
    async def test_client_connection_management(self):
        """Test client connection management"""
        from unittest.mock import Mock
        
        # Create mock websocket
        mock_websocket = Mock()
        client_id = str(uuid.uuid4())
        
        # Create client connection
        client = ClientConnection(mock_websocket, client_id)
        
        self.assertEqual(client.client_id, client_id)
        self.assertEqual(client.websocket, mock_websocket)
        self.assertIsInstance(client.connected_at, datetime)
        self.assertEqual(client.request_count, 0)
        self.assertEqual(client.error_count, 0)
        
        # Test heartbeat update
        old_heartbeat = client.last_heartbeat
        await asyncio.sleep(0.01)
        client.update_heartbeat()
        self.assertGreater(client.last_heartbeat, old_heartbeat)
    
    async def test_protocol_validation_edge_cases(self):
        """Test protocol validation with edge cases"""
        # Test empty message
        is_valid, error = self.protocol_manager.validate_message({})
        self.assertFalse(is_valid)
        self.assertIn("header", error.lower())
        
        # Test message with invalid header
        invalid_message = {
            "header": {
                "message_type": "invalid_type"
            }
        }
        is_valid, error = self.protocol_manager.validate_message(invalid_message)
        self.assertFalse(is_valid)
        
        # Test message with missing required fields
        incomplete_message = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.INFERENCE_REQUEST.value,
                "protocol_version": "2.0",
                "timestamp": datetime.now().isoformat()
            }
            # Missing model_id and prompt
        }
        is_valid, error = self.protocol_manager.validate_message(incomplete_message)
        self.assertFalse(is_valid)
    
    async def test_license_integration_in_messages(self):
        """Test license information integration in messages"""
        # Create request with license
        request = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Test with license",
            license_info=self.test_license
        )
        
        # Verify license information is included
        self.assertIsNotNone(request.header.license_hash)
        self.assertEqual(request.header.license_status.value, "valid")
        
        # Test without license
        request_no_license = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Test without license"
        )
        
        self.assertIsNone(request_no_license.header.license_hash)
        self.assertEqual(request_no_license.header.license_status.value, "missing")
    
    async def test_protocol_stats_collection(self):
        """Test protocol statistics collection"""
        # Create some messages to generate stats
        for i in range(5):
            request = self.protocol_manager.create_inference_request(
                model_id=f"model_{i}",
                prompt=f"Test prompt {i}",
                license_info=self.test_license
            )
            
            # Serialize to count as sent message
            self.protocol_manager.serialize_message(request)
        
        # Get stats
        stats = self.protocol_manager.get_protocol_stats()
        
        self.assertIn("current_version", stats)
        self.assertIn("message_stats", stats)
        self.assertIn("validation_stats", stats)
        self.assertEqual(stats["current_version"], "2.0")
        self.assertEqual(stats["message_stats"]["messages_sent"], 5)
    
    async def test_message_type_routing(self):
        """Test message type routing in server"""
        server = WebSocketServer(
            host="localhost",
            port=8706,
            license_validator=self.license_validator
        )
        
        # Verify all expected message handlers are present
        expected_handlers = {
            MessageType.INFERENCE_REQUEST,
            MessageType.HEARTBEAT,
            MessageType.AUTHENTICATION,
            MessageType.LICENSE_CHECK
        }
        
        self.assertEqual(set(server.message_handlers.keys()), expected_handlers)
        
        # Verify handlers are callable
        for message_type, handler in server.message_handlers.items():
            self.assertTrue(callable(handler))


class TestWebSocketProtocolCompliance(unittest.TestCase):
    """Test WebSocket protocol compliance"""
    
    def setUp(self):
        """Set up test environment"""
        self.protocol_manager = ProtocolManager()
    
    def test_message_id_uniqueness(self):
        """Test that message IDs are unique"""
        message_ids = set()
        
        for i in range(100):
            request = self.protocol_manager.create_inference_request(
                model_id="test_model",
                prompt=f"Test {i}"
            )
            message_ids.add(request.header.message_id)
        
        # All message IDs should be unique
        self.assertEqual(len(message_ids), 100)
    
    def test_timestamp_format(self):
        """Test timestamp format compliance"""
        request = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Test timestamp"
        )
        
        # Should be valid ISO format
        timestamp = request.header.timestamp
        try:
            parsed_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            self.assertIsInstance(parsed_time, datetime)
        except ValueError:
            self.fail(f"Invalid timestamp format: {timestamp}")
    
    def test_protocol_version_consistency(self):
        """Test protocol version consistency"""
        request = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Test version"
        )
        
        response = self.protocol_manager.create_inference_response(
            request_id=request.header.message_id,
            model_id="test_model",
            generated_text="Test response"
        )
        
        # Both should have same protocol version
        self.assertEqual(
            request.header.protocol_version,
            response.header.protocol_version
        )
    
    def test_error_code_coverage(self):
        """Test error code coverage"""
        # Verify all error codes can be used
        for error_code in ErrorCode:
            error_msg = self.protocol_manager.create_error_message(
                error_code=error_code,
                error_message=f"Test error: {error_code.name}"
            )
            
            self.assertEqual(error_msg.error_code, error_code)
            self.assertIn(error_code.name.lower(), error_msg.error_message.lower())


if __name__ == "__main__":
    print("Running WebSocket Integration Tests...")
    unittest.main(verbosity=2)