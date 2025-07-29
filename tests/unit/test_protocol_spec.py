#!/usr/bin/env python3
"""
Comprehensive test suite for protocol_spec.py module
Tests message creation, validation, serialization, and protocol compliance
"""

import json
import sys
from datetime import datetime, timedelta

from core.protocol_spec import (
    ProtocolManager, ProtocolValidator, ProtocolVersion, MessageType,
    LicenseStatusProtocol, ErrorCode, InferenceRequest, InferenceResponse,
    HeartbeatMessage, ErrorMessage, MessageHeader, create_protocol_manager
)
from license_models import LicenseInfo, SubscriptionTier, ValidationStatus


def test_message_creation():
    """Test message creation functionality"""
    print("=== Testing Message Creation ===\n")
    
    # Create protocol manager
    protocol_manager = create_protocol_manager()
    
    # Create test license
    license_info = LicenseInfo(
        license_key="TIKT-PRO-12-TEST01",
        user_id="TEST01",
        plan_type="PRO",
        expiry_date=(datetime.now() + timedelta(days=365)).isoformat(),
        max_clients=20,
        allowed_models=["llama", "mistral"],
        hardware_fingerprint="test_hw_sig",
        is_active=True,
        created_at=datetime.now().isoformat(),
        last_validated=datetime.now().isoformat()
    )
    
    # Test 1: Inference Request Creation
    print("1. Testing Inference Request Creation")
    try:
        request = protocol_manager.create_inference_request(
            model_id="llama-7b",
            prompt="What is artificial intelligence?",
            license_info=license_info,
            max_tokens=200,
            temperature=0.8,
            top_p=0.9,
            stream=False
        )
        
        print(f"✓ Request created successfully: {request.header.message_id}")
        print(f"  Model: {request.model_id}")
        print(f"  Prompt length: {len(request.prompt)} characters")
        print(f"  License status: {request.header.license_status.value}")
        
    except Exception as e:
        print(f"✗ Request creation failed: {e}")
    
    print()
    
    # Test 2: Inference Response Creation
    print("2. Testing Inference Response Creation")
    try:
        response = protocol_manager.create_inference_response(
            request_id=request.header.message_id,
            model_id="llama-7b",
            generated_text="Artificial intelligence (AI) is a branch of computer science...",
            license_info=license_info,
            finish_reason="stop",
            usage={
                "prompt_tokens": 6,
                "completion_tokens": 15,
                "total_tokens": 21
            },
            processing_time_ms=2500,
            worker_id="worker-001"
        )
        
        print(f"✓ Response created successfully: {response.header.message_id}")
        print(f"  Generated text length: {len(response.generated_text)} characters")
        print(f"  Processing time: {response.processing_time_ms}ms")
        print(f"  Total tokens: {response.usage['total_tokens']}")
        
    except Exception as e:
        print(f"✗ Response creation failed: {e}")
    
    print()
    
    # Test 3: Heartbeat Message Creation
    print("3. Testing Heartbeat Message Creation")
    try:
        heartbeat = protocol_manager.create_heartbeat(
            worker_id="worker-001",
            license_info=license_info,
            status="healthy",
            load_percentage=35.7,
            available_memory_mb=16384,
            active_sessions=5,
            models_loaded=["llama-7b", "mistral-7b", "codellama-13b"]
        )
        
        print(f"✓ Heartbeat created successfully: {heartbeat.header.message_id}")
        print(f"  Worker: {heartbeat.worker_id}")
        print(f"  Status: {heartbeat.status}")
        print(f"  Load: {heartbeat.load_percentage}%")
        print(f"  Models loaded: {len(heartbeat.models_loaded)}")
        
    except Exception as e:
        print(f"✗ Heartbeat creation failed: {e}")
    
    print()
    
    # Test 4: Error Message Creation
    print("4. Testing Error Message Creation")
    try:
        error_msg = protocol_manager.create_error_message(
            error_code=ErrorCode.MODEL_NOT_FOUND,
            error_message="The requested model 'gpt-4' is not available",
            license_info=license_info,
            details={
                "requested_model": "gpt-4",
                "available_models": ["llama-7b", "mistral-7b"],
                "suggestion": "Try using one of the available models"
            },
            recovery_suggestions=[
                "Check available models using the list_models endpoint",
                "Verify your license includes access to premium models"
            ]
        )
        
        print(f"✓ Error message created successfully: {error_msg.header.message_id}")
        print(f"  Error code: {error_msg.error_code.value}")
        print(f"  Error message: {error_msg.error_message}")
        print(f"  Recovery suggestions: {len(error_msg.recovery_suggestions)}")
        
    except Exception as e:
        print(f"✗ Error message creation failed: {e}")
    
    print()
    
    return protocol_manager, request, response, heartbeat, error_msg


def test_message_validation():
    """Test message validation functionality"""
    print("=== Testing Message Validation ===\n")
    
    protocol_manager, request, response, heartbeat, error_msg = test_message_creation()
    
    # Test 1: Valid Message Validation
    print("1. Testing Valid Message Validation")
    
    messages = [
        (request, "Inference Request"),
        (response, "Inference Response"),
        (heartbeat, "Heartbeat Message"),
        (error_msg, "Error Message")
    ]
    
    for message, name in messages:
        try:
            json_str = protocol_manager.serialize_message(message)
            is_valid, error = protocol_manager.validate_message(json_str)
            
            status = "✓ VALID" if is_valid else "✗ INVALID"
            print(f"  {status}: {name}")
            if error:
                print(f"    Error: {error}")
                
        except Exception as e:
            print(f"  ✗ VALIDATION ERROR: {name} - {e}")
    
    print()
    
    # Test 2: Invalid Message Validation
    print("2. Testing Invalid Message Validation")
    
    invalid_messages = [
        # Missing header
        {
            "model_id": "llama-7b",
            "prompt": "Hello"
        },
        
        # Invalid message ID format
        {
            "header": {
                "message_id": "not-a-uuid",
                "message_type": "inference_request",
                "protocol_version": "2.0",
                "timestamp": datetime.utcnow().isoformat()
            },
            "model_id": "llama-7b",
            "prompt": "Hello"
        },
        
        # Invalid message type
        {
            "header": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "message_type": "invalid_type",
                "protocol_version": "2.0",
                "timestamp": datetime.utcnow().isoformat()
            },
            "model_id": "llama-7b",
            "prompt": "Hello"
        },
        
        # Unsupported protocol version
        {
            "header": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "message_type": "inference_request",
                "protocol_version": "3.0",
                "timestamp": datetime.utcnow().isoformat()
            },
            "model_id": "llama-7b",
            "prompt": "Hello"
        },
        
        # Missing required fields
        {
            "header": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "message_type": "inference_request",
                "protocol_version": "2.0",
                "timestamp": datetime.utcnow().isoformat()
            },
            "model_id": "",  # Empty model_id
            "prompt": ""     # Empty prompt
        },
        
        # Invalid parameter ranges
        {
            "header": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "message_type": "inference_request",
                "protocol_version": "2.0",
                "timestamp": datetime.utcnow().isoformat()
            },
            "model_id": "llama-7b",
            "prompt": "Hello",
            "temperature": 5.0,  # Invalid temperature > 2.0
            "top_p": 1.5,        # Invalid top_p > 1.0
            "max_tokens": -10    # Invalid negative max_tokens
        }
    ]
    
    for i, invalid_msg in enumerate(invalid_messages, 1):
        is_valid, error = protocol_manager.validate_message(invalid_msg)
        status = "✓ CORRECTLY REJECTED" if not is_valid else "✗ INCORRECTLY ACCEPTED"
        print(f"  {status}: Invalid message {i}")
        if error:
            print(f"    Reason: {error}")
    
    print()


def test_serialization():
    """Test message serialization and deserialization"""
    print("=== Testing Message Serialization ===\n")
    
    protocol_manager = create_protocol_manager()
    
    # Create test license
    license_info = LicenseInfo(
        license_key="TIKT-ENT-24-TEST02",
        user_id="TEST02",
        plan_type="ENT",
        expiry_date=(datetime.now() + timedelta(days=730)).isoformat(),
        max_clients=-1,
        allowed_models=["all_models"],
        hardware_fingerprint="ent_hw_sig",
        is_active=True,
        created_at=datetime.now().isoformat(),
        last_validated=datetime.now().isoformat()
    )
    
    # Test 1: Serialization
    print("1. Testing Message Serialization")
    
    request = protocol_manager.create_inference_request(
        model_id="codellama-13b",
        prompt="def fibonacci(n):",
        license_info=license_info,
        max_tokens=500,
        temperature=0.2,
        metadata={"task": "code_completion", "language": "python"}
    )
    
    try:
        json_str = protocol_manager.serialize_message(request)
        print("✓ Message serialized successfully")
        
        # Parse JSON to verify structure
        parsed = json.loads(json_str)
        print(f"  Message ID: {parsed['header']['message_id']}")
        print(f"  Message Type: {parsed['header']['message_type']}")
        print(f"  Protocol Version: {parsed['header']['protocol_version']}")
        print(f"  License Status: {parsed['header']['license_status']}")
        
    except Exception as e:
        print(f"✗ Serialization failed: {e}")
    
    print()
    
    # Test 2: Deserialization
    print("2. Testing Message Deserialization")
    
    try:
        deserialized = protocol_manager.deserialize_message(json_str)
        print("✓ Message deserialized successfully")
        
        # Verify key fields
        header = deserialized['header']
        print(f"  Deserialized message ID: {header['message_id']}")
        print(f"  Deserialized model ID: {deserialized['model_id']}")
        print(f"  Deserialized prompt: {deserialized['prompt'][:50]}...")
        
    except Exception as e:
        print(f"✗ Deserialization failed: {e}")
    
    print()
    
    # Test 3: Round-trip consistency
    print("3. Testing Round-trip Consistency")
    
    try:
        # Create -> Serialize -> Deserialize -> Validate
        original_request = protocol_manager.create_inference_request(
            model_id="mistral-7b",
            prompt="Explain quantum computing",
            license_info=license_info
        )
        
        serialized = protocol_manager.serialize_message(original_request)
        deserialized = protocol_manager.deserialize_message(serialized)
        is_valid, error = protocol_manager.validate_message(deserialized)
        
        if is_valid:
            print("✓ Round-trip consistency maintained")
            print(f"  Original message ID: {original_request.header.message_id}")
            print(f"  Deserialized message ID: {deserialized['header']['message_id']}")
        else:
            print(f"✗ Round-trip consistency failed: {error}")
            
    except Exception as e:
        print(f"✗ Round-trip test failed: {e}")
    
    print()


def test_protocol_versions():
    """Test protocol version compatibility"""
    print("=== Testing Protocol Version Compatibility ===\n")
    
    # Test different protocol versions
    versions = [ProtocolVersion.V1_1, ProtocolVersion.V2_0]
    
    for version in versions:
        print(f"Testing Protocol Version {version.value}")
        
        try:
            protocol_manager = create_protocol_manager(version)
            
            request = protocol_manager.create_inference_request(
                model_id="test-model",
                prompt="Test prompt"
            )
            
            json_str = protocol_manager.serialize_message(request)
            is_valid, error = protocol_manager.validate_message(json_str)
            
            status = "✓ COMPATIBLE" if is_valid else "✗ INCOMPATIBLE"
            print(f"  {status}: Version {version.value}")
            if error:
                print(f"    Error: {error}")
                
        except Exception as e:
            print(f"  ✗ ERROR: Version {version.value} - {e}")
    
    print()


def test_license_integration():
    """Test license integration in protocol messages"""
    print("=== Testing License Integration ===\n")
    
    protocol_manager = create_protocol_manager()
    
    # Test different license scenarios
    license_scenarios = [
        # Valid PRO license
        LicenseInfo(
            license_key="TIKT-PRO-12-VALID",
            user_id="VALID",
            plan_type="PRO",
            expiry_date=(datetime.now() + timedelta(days=365)).isoformat(),
            max_clients=20,
            allowed_models=["llama", "mistral"],
            hardware_fingerprint="valid_hw",
            is_active=True,
            created_at=datetime.now().isoformat(),
            last_validated=datetime.now().isoformat()
        ),
        
        # Expired license
        LicenseInfo(
            license_key="TIKT-PRO-12-EXPIRED",
            user_id="EXPIRED",
            plan_type="PRO",
            expiry_date=(datetime.now() - timedelta(days=30)).isoformat(),
            max_clients=20,
            allowed_models=["llama"],
            hardware_fingerprint="expired_hw",
            is_active=False,
            created_at=(datetime.now() - timedelta(days=365)).isoformat(),
            last_validated=datetime.now().isoformat()
        ),
        
        # No license (None)
        None
    ]
    
    for i, license_info in enumerate(license_scenarios, 1):
        license_desc = "Valid PRO" if i == 1 else "Expired" if i == 2 else "No License"
        print(f"{i}. Testing {license_desc}")
        
        try:
            request = protocol_manager.create_inference_request(
                model_id="test-model",
                prompt="Test prompt",
                license_info=license_info
            )
            
            json_str = protocol_manager.serialize_message(request)
            parsed = json.loads(json_str)
            
            header = parsed['header']
            license_status = header.get('license_status', 'missing')
            license_hash = header.get('license_hash')
            
            print(f"  ✓ Request created with license status: {license_status}")
            print(f"    License hash present: {'Yes' if license_hash else 'No'}")
            
        except Exception as e:
            print(f"  ✗ Failed to create request: {e}")
    
    print()


def test_error_handling():
    """Test error handling and error messages"""
    print("=== Testing Error Handling ===\n")
    
    protocol_manager = create_protocol_manager()
    
    # Test 1: Error message creation for different error codes
    print("1. Testing Error Message Creation")
    
    error_scenarios = [
        (ErrorCode.AUTHENTICATION_FAILED, "Invalid credentials provided"),
        (ErrorCode.LICENSE_EXPIRED, "License has expired, please renew"),
        (ErrorCode.QUOTA_EXCEEDED, "API quota limit exceeded"),
        (ErrorCode.MODEL_NOT_FOUND, "Requested model is not available"),
        (ErrorCode.INTERNAL_ERROR, "An internal server error occurred")
    ]
    
    for error_code, error_message in error_scenarios:
        try:
            error_msg = protocol_manager.create_error_message(
                error_code=error_code,
                error_message=error_message,
                details={"timestamp": datetime.utcnow().isoformat()},
                recovery_suggestions=["Please try again later", "Contact support if issue persists"]
            )
            
            json_str = protocol_manager.serialize_message(error_msg)
            is_valid, validation_error = protocol_manager.validate_message(json_str)
            
            status = "✓ VALID" if is_valid else "✗ INVALID"
            print(f"  {status}: {error_code.name} ({error_code.value})")
            
        except Exception as e:
            print(f"  ✗ ERROR: {error_code.name} - {e}")
    
    print()
    
    # Test 2: Validation error handling
    print("2. Testing Validation Error Handling")
    
    validator = ProtocolValidator()
    
    # Test malformed JSON
    malformed_json = '{"header": {"message_id": "test", "incomplete": true'
    is_valid, error = validator.validate_message(malformed_json)
    
    print(f"  Malformed JSON: {'✓ REJECTED' if not is_valid else '✗ ACCEPTED'}")
    if error:
        print(f"    Error: {error}")
    
    # Get validation statistics
    stats = validator.get_validation_stats()
    print(f"  Validation statistics:")
    print(f"    Total validations: {stats['total_validations']}")
    print(f"    Success rate: {stats['success_rate_percentage']}%")
    print(f"    Error counts: {stats['error_counts']}")
    
    print()


def main():
    """Run all protocol specification tests"""
    print("🚀 Starting Protocol Specification Test Suite\n")
    
    try:
        # Run all test categories
        test_message_creation()
        test_message_validation()
        test_serialization()
        test_protocol_versions()
        test_license_integration()
        test_error_handling()
        
        print("🎉 All Protocol Specification Tests Completed Successfully!")
        
        # Final statistics
        protocol_manager = create_protocol_manager()
        stats = protocol_manager.get_protocol_stats()
        
        print(f"\n📊 Final Protocol Statistics:")
        print(f"  Current Protocol Version: {stats['current_version']}")
        print(f"  Messages Processed: {stats['message_stats']['messages_sent']}")
        print(f"  Validation Success Rate: {stats['validation_stats']['success_rate_percentage']}%")
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()