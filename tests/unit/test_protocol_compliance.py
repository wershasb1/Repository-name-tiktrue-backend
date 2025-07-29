"""
Test WebSocket Protocol Compliance
Tests the core protocol functionality without complex imports
"""

import unittest
import json
import uuid
from datetime import datetime, timedelta

# Import required modules
from core.protocol_spec import (
    ProtocolManager, ProtocolValidator, MessageType, ErrorCode,
    InferenceRequest, InferenceResponse, HeartbeatMessage, ErrorMessage
)
from license_models import LicenseInfo, SubscriptionTier, ValidationStatus
from security.license_validator import LicenseValidator


class TestProtocolCompliance(unittest.TestCase):
    """Test WebSocket protocol compliance"""
    
    def setUp(self):
        """Set up test environment"""
        self.protocol_manager = ProtocolManager()
        self.protocol_validator = ProtocolValidator()
        self.license_validator = LicenseValidator()
        
        # Create test license
        self.test_license = LicenseInfo(
            license_key="test_protocol_key_12345",
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
    
    def test_inference_request_creation_and_validation(self):
        """Test creating and validating inference requests"""
        # Create inference request
        request = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Hello, world!",
            license_info=self.test_license,
            max_tokens=50,
            temperature=0.8,
            top_p=0.9
        )
        
        # Verify request structure
        self.assertIsInstance(request, InferenceRequest)
        self.assertEqual(request.model_id, "test_model")
        self.assertEqual(request.prompt, "Hello, world!")
        self.assertEqual(request.max_tokens, 50)
        self.assertEqual(request.temperature, 0.8)
        self.assertEqual(request.top_p, 0.9)
        
        # Verify header
        self.assertIsNotNone(request.header.message_id)
        self.assertEqual(request.header.message_type, MessageType.INFERENCE_REQUEST)
        self.assertIsNotNone(request.header.timestamp)
        self.assertIsNotNone(request.header.license_hash)
        
        # Test serialization
        serialized = self.protocol_manager.serialize_message(request)
        self.assertIsInstance(serialized, str)
        
        # Test deserialization
        deserialized = self.protocol_manager.deserialize_message(serialized)
        self.assertIsInstance(deserialized, dict)
        
        # Test validation
        is_valid, error = self.protocol_validator.validate_message(deserialized)
        self.assertTrue(is_valid, f"Validation failed: {error}")
    
    def test_inference_response_creation_and_validation(self):
        """Test creating and validating inference responses"""
        request_id = str(uuid.uuid4())
        
        # Create inference response
        response = self.protocol_manager.create_inference_response(
            request_id=request_id,
            model_id="test_model",
            generated_text="Hello! How can I help you today?",
            license_info=self.test_license,
            processing_time_ms=150,
            finish_reason="stop"
        )
        
        # Verify response structure
        self.assertIsInstance(response, InferenceResponse)
        self.assertEqual(response.request_id, request_id)
        self.assertEqual(response.model_id, "test_model")
        self.assertEqual(response.generated_text, "Hello! How can I help you today?")
        self.assertEqual(response.processing_time_ms, 150)
        self.assertEqual(response.finish_reason, "stop")
        
        # Test serialization and validation
        serialized = self.protocol_manager.serialize_message(response)
        deserialized = self.protocol_manager.deserialize_message(serialized)
        is_valid, error = self.protocol_validator.validate_message(deserialized)
        self.assertTrue(is_valid, f"Response validation failed: {error}")
    
    def test_heartbeat_message_creation_and_validation(self):
        """Test creating and validating heartbeat messages"""
        # Create heartbeat message
        heartbeat = self.protocol_manager.create_heartbeat(
            worker_id="test_worker_1",
            license_info=self.test_license,
            status="healthy",
            load_percentage=25.5,
            available_memory_mb=2048,
            active_sessions=3
        )
        
        # Verify heartbeat structure
        self.assertIsInstance(heartbeat, HeartbeatMessage)
        self.assertEqual(heartbeat.worker_id, "test_worker_1")
        self.assertEqual(heartbeat.status, "healthy")
        self.assertEqual(heartbeat.load_percentage, 25.5)
        self.assertEqual(heartbeat.available_memory_mb, 2048)
        self.assertEqual(heartbeat.active_sessions, 3)
        
        # Test serialization and validation
        serialized = self.protocol_manager.serialize_message(heartbeat)
        deserialized = self.protocol_manager.deserialize_message(serialized)
        is_valid, error = self.protocol_validator.validate_message(deserialized)
        self.assertTrue(is_valid, f"Heartbeat validation failed: {error}")
    
    def test_error_message_creation_and_validation(self):
        """Test creating and validating error messages"""
        # Create error message
        error_msg = self.protocol_manager.create_error_message(
            error_code=ErrorCode.LICENSE_EXPIRED,
            error_message="License has expired",
            license_info=self.test_license,
            details={"expires_at": "2024-01-01T00:00:00"},
            recovery_suggestions=["Renew your license", "Contact support"]
        )
        
        # Verify error message structure
        self.assertIsInstance(error_msg, ErrorMessage)
        self.assertEqual(error_msg.error_code, ErrorCode.LICENSE_EXPIRED)
        self.assertEqual(error_msg.error_message, "License has expired")
        self.assertIn("expires_at", error_msg.details)
        self.assertEqual(len(error_msg.recovery_suggestions), 2)
        
        # Test serialization and validation
        serialized = self.protocol_manager.serialize_message(error_msg)
        deserialized = self.protocol_manager.deserialize_message(serialized)
        is_valid, error = self.protocol_validator.validate_message(deserialized)
        self.assertTrue(is_valid, f"Error message validation failed: {error}")
    
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
    
    def test_timestamp_format_compliance(self):
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
    
    def test_license_integration_in_messages(self):
        """Test license information integration in messages"""
        # Create request with license
        request_with_license = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Test with license",
            license_info=self.test_license
        )
        
        # Verify license information is included
        self.assertIsNotNone(request_with_license.header.license_hash)
        self.assertEqual(request_with_license.header.license_status.value, "valid")
        
        # Test without license
        request_no_license = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Test without license"
        )
        
        self.assertIsNone(request_no_license.header.license_hash)
        self.assertEqual(request_no_license.header.license_status.value, "missing")
    
    def test_protocol_validation_edge_cases(self):
        """Test protocol validation with edge cases"""
        # Test empty message
        is_valid, error = self.protocol_validator.validate_message({})
        self.assertFalse(is_valid)
        self.assertIn("header", error.lower())
        
        # Test message with invalid header
        invalid_message = {
            "header": {
                "message_type": "invalid_type"
            }
        }
        is_valid, error = self.protocol_validator.validate_message(invalid_message)
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
        is_valid, error = self.protocol_validator.validate_message(incomplete_message)
        self.assertFalse(is_valid)
    
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
    
    def test_protocol_stats_collection(self):
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
    
    def test_json_serialization_compatibility(self):
        """Test JSON serialization compatibility"""
        # Create complex message with all fields
        request = self.protocol_manager.create_inference_request(
            model_id="test_model",
            prompt="Complex test prompt",
            license_info=self.test_license,
            max_tokens=100,
            temperature=0.7,
            top_p=0.9,
            stop_sequences=["<|end|>", "\n\n"],
            stream=False,
            context_window=2048,
            metadata={"test": "value", "number": 42}
        )
        
        # Serialize to JSON
        json_str = self.protocol_manager.serialize_message(request)
        
        # Should be valid JSON
        try:
            parsed_json = json.loads(json_str)
            self.assertIsInstance(parsed_json, dict)
        except json.JSONDecodeError:
            self.fail("Serialized message is not valid JSON")
        
        # Should deserialize back correctly
        deserialized = self.protocol_manager.deserialize_message(json_str)
        self.assertEqual(deserialized["model_id"], "test_model")
        self.assertEqual(deserialized["prompt"], "Complex test prompt")
        self.assertEqual(deserialized["max_tokens"], 100)
        self.assertEqual(len(deserialized["stop_sequences"]), 2)
        self.assertIn("test", deserialized["metadata"])


if __name__ == "__main__":
    print("Running WebSocket Protocol Compliance Tests...")
    unittest.main(verbosity=2)