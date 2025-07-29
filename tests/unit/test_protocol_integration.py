"""
Test Protocol Integration with API Client
Tests the integration of standardized protocol with the API client
"""

import json
import asyncio
from typing import Dict, Any

# Import the updated API client and protocol
from api_client import LicenseAwareAPIClient, LicenseErrorType, ConnectionStatus
from core.protocol_spec import (
    InferenceRequest, InferenceResponse, ProtocolValidator,
    MessageType, ResponseStatus, LicenseStatus,
    create_inference_request, create_inference_response
)
from security.license_validator import LicenseValidator, LicenseInfo, SubscriptionTier
from license_storage import LicenseStorage


class TestProtocolIntegration:
    """Test protocol integration with API client"""
    
    def test_inference_request_creation(self):
        """Test creating inference request using new protocol"""
        # Create request using protocol utility
        request = create_inference_request(
            session_id="test_session_123",
            network_id="llama_network",
            license_hash="a1b2c3d4e5f67890",  # Valid 16-char hex
            input_tensors={"input_ids": [[1, 2, 3, 4, 5]]},
            step=0,
            model_id="llama-7b",
            metadata={"temperature": 0.7}
        )
        
        # Validate request structure
        assert isinstance(request, InferenceRequest)
        assert request.session_id == "test_session_123"
        assert request.network_id == "llama_network"
        assert request.license_hash == "a1b2c3d4e5f67890"
        assert request.input_tensors == {"input_ids": [[1, 2, 3, 4, 5]]}
        assert request.step == 0
        assert request.model_id == "llama-7b"
        assert request.metadata == {"temperature": 0.7}
        assert request.message_type == MessageType.INFERENCE_REQUEST.value
        
        # Validate request
        errors = request.validate()
        assert len(errors) == 0, f"Request validation failed: {errors}"
        
        print("✓ Inference request creation and validation")
    
    def test_inference_response_creation(self):
        """Test creating inference response using new protocol"""
        # Create response using protocol utility
        response = create_inference_response(
            session_id="test_session_123",
            network_id="llama_network",
            step=0,
            status=ResponseStatus.SUCCESS.value,
            license_status=LicenseStatus.VALID.value,
            outputs={"logits": [[0.1, 0.2, 0.3, 0.4]]},
            processing_time=1.25,
            worker_id="worker_001"
        )
        
        # Validate response structure
        assert isinstance(response, InferenceResponse)
        assert response.session_id == "test_session_123"
        assert response.network_id == "llama_network"
        assert response.step == 0
        assert response.status == ResponseStatus.SUCCESS.value
        assert response.license_status == LicenseStatus.VALID.value
        assert response.outputs == {"logits": [[0.1, 0.2, 0.3, 0.4]]}
        assert response.processing_time == 1.25
        assert response.worker_id == "worker_001"
        assert response.message_type == MessageType.INFERENCE_RESPONSE.value
        
        # Validate response
        errors = response.validate()
        assert len(errors) == 0, f"Response validation failed: {errors}"
        
        print("✓ Inference response creation and validation")
    
    def test_protocol_serialization(self):
        """Test protocol message serialization and parsing"""
        # Create request
        request = create_inference_request(
            session_id="test_session",
            network_id="test_network",
            license_hash="1234567890abcdef",
            input_tensors={"input": "test_data"},
            step=5,
            model_id="test_model"
        )
        
        # Serialize to JSON
        json_str = request.to_json()
        assert isinstance(json_str, str)
        
        # Parse JSON back
        parsed_data = json.loads(json_str)
        assert parsed_data["message_type"] == MessageType.INFERENCE_REQUEST.value
        assert parsed_data["session_id"] == "test_session"
        assert parsed_data["network_id"] == "test_network"
        assert parsed_data["license_hash"] == "1234567890abcdef"
        
        # Use protocol validator to parse
        parsed_message = ProtocolValidator.parse_message(json_str)
        assert isinstance(parsed_message, InferenceRequest)
        assert parsed_message.session_id == "test_session"
        assert parsed_message.network_id == "test_network"
        assert parsed_message.license_hash == "1234567890abcdef"
        
        print("✓ Protocol serialization and parsing")
    
    def test_api_client_license_integration(self):
        """Test API client license integration with new protocol"""
        # Create mock license storage
        license_storage = LicenseStorage()
        
        # Create API client (without connecting)
        client = LicenseAwareAPIClient(
            server_host="localhost",
            server_port=8702,
            license_storage=license_storage,
            auto_reconnect=False
        )
        
        # Test license hash generation
        test_license_key = "TIKT-PRO-365-ABC123DEF456"
        license_hash = client._generate_license_hash(test_license_key)
        assert isinstance(license_hash, str)
        assert len(license_hash) == 16
        
        # Test request permission validation (without valid license)
        request = create_inference_request(
            session_id="test_session",
            network_id="test_network",
            license_hash="1234567890abcdef",
            input_tensors={"input": "data"},
            step=0,
            model_id="premium_model"
        )
        
        permission_error = client._validate_request_permissions(request)
        assert permission_error is not None  # Should fail without valid license
        assert "No valid license" in permission_error
        
        print("✓ API client license integration")
    
    def test_license_error_handling(self):
        """Test license error handling with new protocol"""
        # Create API client
        client = LicenseAwareAPIClient(auto_reconnect=False)
        
        # Create mock response with license error
        error_response = create_inference_response(
            session_id="test_session",
            network_id="test_network",
            step=0,
            status=ResponseStatus.LICENSE_ERROR.value,
            license_status=LicenseStatus.EXPIRED.value,
            error="License has expired"
        )
        
        # Test error handling
        errors_handled = []
        
        def mock_license_error_handler(error_type: LicenseErrorType, message: str):
            errors_handled.append((error_type, message))
        
        client.set_license_error_callback(mock_license_error_handler)
        client._handle_license_error_from_response(error_response)
        
        assert len(errors_handled) == 1
        assert errors_handled[0][0] == LicenseErrorType.EXPIRED_LICENSE
        assert "License has expired" in errors_handled[0][1]
        
        print("✓ License error handling")
    
    def test_protocol_validation_errors(self):
        """Test protocol validation error handling"""
        # Test invalid message structure
        invalid_message = {
            "message_type": MessageType.INFERENCE_REQUEST.value,
            "session_id": "",  # Invalid - empty
            "network_id": "",  # Invalid - empty
            "license_hash": "invalid",  # Invalid - wrong format
            "step": -1,  # Invalid - negative
            "input_tensors": "not_dict"  # Invalid - not dict
        }
        
        errors = ProtocolValidator.validate_message(invalid_message)
        assert len(errors) > 0
        
        # Test parsing invalid message
        json_str = json.dumps(invalid_message)
        parsed = ProtocolValidator.parse_message(json_str)
        
        # Should return error response
        assert isinstance(parsed, type(ProtocolValidator.create_error_response("test")))
        assert "Message validation failed" in parsed.error
        assert parsed.error_code == "VALIDATION_ERROR"
        
        print("✓ Protocol validation error handling")
    
    def test_message_type_constants(self):
        """Test message type constants are properly defined"""
        # Test all message types are defined
        assert MessageType.INFERENCE_REQUEST.value == "inference_request"
        assert MessageType.INFERENCE_RESPONSE.value == "inference_response"
        assert MessageType.HEARTBEAT_REQUEST.value == "heartbeat_request"
        assert MessageType.HEARTBEAT_RESPONSE.value == "heartbeat_response"
        assert MessageType.ERROR_RESPONSE.value == "error_response"
        
        # Test response status constants
        assert ResponseStatus.SUCCESS.value == "success"
        assert ResponseStatus.ERROR.value == "error"
        assert ResponseStatus.LICENSE_ERROR.value == "license_error"
        assert ResponseStatus.TIMEOUT.value == "timeout"
        
        # Test license status constants
        assert LicenseStatus.VALID.value == "valid"
        assert LicenseStatus.INVALID.value == "invalid"
        assert LicenseStatus.EXPIRED.value == "expired"
        assert LicenseStatus.CLIENT_LIMIT_EXCEEDED.value == "client_limit_exceeded"
        
        print("✓ Message type constants")
    
    def test_backward_compatibility(self):
        """Test backward compatibility with existing code"""
        # Test that the legacy utility function still works
        from api_client import create_inference_request_legacy
        
        legacy_request = create_inference_request_legacy(
            session_id="test_session",
            input_tensors={"input": "data"},
            model_id="test_model",
            network_id="test_network",
            step=5
        )
        
        assert isinstance(legacy_request, InferenceRequest)
        assert legacy_request.session_id == "test_session"
        assert legacy_request.input_tensors == {"input": "data"}
        assert legacy_request.model_id == "test_model"
        assert legacy_request.network_id == "test_network"
        assert legacy_request.step == 5
        
        print("✓ Backward compatibility")


def run_all_tests():
    """Run all integration tests"""
    test_instance = TestProtocolIntegration()
    
    test_methods = [
        test_instance.test_inference_request_creation,
        test_instance.test_inference_response_creation,
        test_instance.test_protocol_serialization,
        test_instance.test_api_client_license_integration,
        test_instance.test_license_error_handling,
        test_instance.test_protocol_validation_errors,
        test_instance.test_message_type_constants,
        test_instance.test_backward_compatibility
    ]
    
    passed = 0
    failed = 0
    
    print("Running Protocol Integration Tests...")
    print("=" * 50)
    
    for test_method in test_methods:
        try:
            test_method()
            passed += 1
        except Exception as e:
            print(f"✗ {test_method.__name__}: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Total: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All integration tests passed! ✓")
        return True
    else:
        print("Some integration tests failed! ✗")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)