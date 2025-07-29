"""
Demonstration of Standardized WebSocket Protocol Usage
Shows how to use the new protocol for TikTrue distributed LLM platform
"""

import json
import time
from typing import Dict, Any

from core.protocol_spec import (
    InferenceRequest, InferenceResponse, HeartbeatRequest, HeartbeatResponse,
    ErrorResponse, ProtocolValidator, MessageType, ResponseStatus,
    LicenseStatus, create_inference_request, create_inference_response
)


def demo_inference_request():
    """Demonstrate creating and validating inference requests"""
    print("=== Inference Request Demo ===")
    
    # Create inference request using utility function
    request = create_inference_request(
        session_id="demo_session_001",
        network_id="llama_7b_network",
        license_hash="1234567890abcdef",
        input_tensors={
            "input_ids": [[1, 2, 3, 4, 5]],
            "attention_mask": [[1, 1, 1, 1, 1]]
        },
        step=0,
        model_id="llama-7b-chat",
        metadata={
            "temperature": 0.7,
            "max_tokens": 100,
            "top_p": 0.9
        }
    )
    
    print(f"Created request: {request.session_id}")
    print(f"Network: {request.network_id}")
    print(f"Model: {request.model_id}")
    print(f"License hash: {request.license_hash}")
    print(f"Message ID: {request.message_id}")
    print(f"Timestamp: {request.timestamp}")
    
    # Validate request
    errors = request.validate()
    if errors:
        print(f"Validation errors: {errors}")
    else:
        print("✓ Request validation passed")
    
    # Convert to JSON
    json_str = request.to_json()
    print(f"JSON size: {len(json_str)} bytes")
    
    # Parse back from JSON
    parsed = ProtocolValidator.parse_message(json_str)
    if isinstance(parsed, InferenceRequest):
        print("✓ JSON parsing successful")
        print(f"Parsed session: {parsed.session_id}")
    else:
        print(f"✗ JSON parsing failed: {parsed.error}")
    
    print()


def demo_inference_response():
    """Demonstrate creating and validating inference responses"""
    print("=== Inference Response Demo ===")
    
    # Create successful response
    response = create_inference_response(
        session_id="demo_session_001",
        network_id="llama_7b_network",
        step=0,
        status=ResponseStatus.SUCCESS.value,
        license_status=LicenseStatus.VALID.value,
        outputs={
            "logits": [[0.1, 0.2, 0.3, 0.4, 0.5]],
            "generated_text": "Hello, how can I help you today?"
        },
        processing_time=1.25,
        worker_id="worker_gpu_001"
    )
    
    print(f"Response for session: {response.session_id}")
    print(f"Status: {response.status}")
    print(f"License status: {response.license_status}")
    print(f"Processing time: {response.processing_time}s")
    print(f"Worker: {response.worker_id}")
    
    # Validate response
    errors = response.validate()
    if errors:
        print(f"Validation errors: {errors}")
    else:
        print("✓ Response validation passed")
    
    # Create error response
    error_response = ProtocolValidator.create_error_response(
        error_message="Model not found",
        error_code="MODEL_NOT_FOUND",
        license_status=LicenseStatus.VALID.value,
        details={"requested_model": "llama-13b", "available_models": ["llama-7b"]}
    )
    
    print(f"\nError response: {error_response.error}")
    print(f"Error code: {error_response.error_code}")
    print(f"Details: {error_response.details}")
    
    print()


def demo_heartbeat_messages():
    """Demonstrate heartbeat messages for connection monitoring"""
    print("=== Heartbeat Messages Demo ===")
    
    # Create heartbeat request
    heartbeat_req = HeartbeatRequest(
        network_id="llama_7b_network",
        license_hash="1234567890abcdef",
        node_id="worker_001"
    )
    
    print(f"Heartbeat request from node: {heartbeat_req.node_id}")
    print(f"Network: {heartbeat_req.network_id}")
    
    # Create heartbeat response
    heartbeat_resp = HeartbeatResponse(
        network_id="llama_7b_network",
        status=ResponseStatus.SUCCESS.value,
        license_status=LicenseStatus.VALID.value
    )
    
    print(f"Heartbeat response status: {heartbeat_resp.status}")
    print(f"Server time: {heartbeat_resp.server_time}")
    
    print()


def demo_protocol_validation():
    """Demonstrate protocol validation capabilities"""
    print("=== Protocol Validation Demo ===")
    
    # Test valid message
    valid_message = {
        "message_type": MessageType.INFERENCE_REQUEST.value,
        "session_id": "test_session",
        "network_id": "test_network",
        "license_hash": "1234567890abcdef",
        "step": 0,
        "input_tensors": {"input": "data"}
    }
    
    errors = ProtocolValidator.validate_message(valid_message)
    print(f"Valid message errors: {len(errors)}")
    
    # Test invalid message
    invalid_message = {
        "message_type": MessageType.INFERENCE_REQUEST.value,
        "session_id": "",  # Invalid - empty
        "network_id": "",  # Invalid - empty
        "license_hash": "invalid",  # Invalid - wrong format
        "step": -1,  # Invalid - negative
        "input_tensors": "not_dict"  # Invalid - not dict
    }
    
    errors = ProtocolValidator.validate_message(invalid_message)
    print(f"Invalid message errors: {len(errors)}")
    for error in errors[:3]:  # Show first 3 errors
        print(f"  - {error}")
    
    # Test parsing invalid JSON
    invalid_json = '{"invalid": json}'
    parsed = ProtocolValidator.parse_message(invalid_json)
    if isinstance(parsed, ErrorResponse):
        print(f"JSON parsing error handled: {parsed.error_code}")
    
    print()


def demo_message_flow():
    """Demonstrate a complete message flow"""
    print("=== Complete Message Flow Demo ===")
    
    # Step 1: Client sends inference request
    print("1. Client sends inference request")
    request = create_inference_request(
        session_id="flow_demo_001",
        network_id="production_network",
        license_hash="abcdef1234567890",
        input_tensors={"prompt": "What is artificial intelligence?"},
        step=0,
        model_id="llama-7b-instruct"
    )
    
    request_json = request.to_json()
    print(f"   Request size: {len(request_json)} bytes")
    
    # Step 2: Server validates request
    print("2. Server validates request")
    parsed_request = ProtocolValidator.parse_message(request_json)
    if isinstance(parsed_request, InferenceRequest):
        validation_errors = parsed_request.validate()
        if not validation_errors:
            print("   ✓ Request validation passed")
        else:
            print(f"   ✗ Request validation failed: {validation_errors}")
            return
    else:
        print(f"   ✗ Request parsing failed: {parsed_request.error}")
        return
    
    # Step 3: Server processes request and sends response
    print("3. Server processes request")
    time.sleep(0.1)  # Simulate processing time
    
    response = create_inference_response(
        session_id=parsed_request.session_id,
        network_id=parsed_request.network_id,
        step=parsed_request.step,
        status=ResponseStatus.SUCCESS.value,
        license_status=LicenseStatus.VALID.value,
        outputs={
            "generated_text": "Artificial intelligence (AI) is a branch of computer science...",
            "tokens_generated": 25,
            "finish_reason": "length"
        },
        processing_time=0.85,
        worker_id="gpu_worker_003"
    )
    
    response_json = response.to_json()
    print(f"   Response size: {len(response_json)} bytes")
    print(f"   Processing time: {response.processing_time}s")
    
    # Step 4: Client receives and validates response
    print("4. Client validates response")
    parsed_response = ProtocolValidator.parse_message(response_json)
    if isinstance(parsed_response, InferenceResponse):
        validation_errors = parsed_response.validate()
        if not validation_errors:
            print("   ✓ Response validation passed")
            print(f"   Generated text: {parsed_response.outputs.get('generated_text', '')[:50]}...")
        else:
            print(f"   ✗ Response validation failed: {validation_errors}")
    else:
        print(f"   ✗ Response parsing failed: {parsed_response.error}")
    
    print()


def demo_license_status_handling():
    """Demonstrate different license status scenarios"""
    print("=== License Status Handling Demo ===")
    
    license_scenarios = [
        (LicenseStatus.VALID.value, "License is valid and active"),
        (LicenseStatus.EXPIRED.value, "License has expired - renewal required"),
        (LicenseStatus.CLIENT_LIMIT_EXCEEDED.value, "Too many clients connected"),
        (LicenseStatus.MODEL_ACCESS_DENIED.value, "Model not available in current plan"),
        (LicenseStatus.HARDWARE_MISMATCH.value, "License bound to different hardware")
    ]
    
    for license_status, description in license_scenarios:
        response = create_inference_response(
            session_id="license_demo",
            network_id="test_network",
            step=0,
            status=ResponseStatus.LICENSE_ERROR.value if license_status != LicenseStatus.VALID.value else ResponseStatus.SUCCESS.value,
            license_status=license_status,
            error=description if license_status != LicenseStatus.VALID.value else None
        )
        
        print(f"License Status: {license_status}")
        print(f"Description: {description}")
        print(f"Response Status: {response.status}")
        if response.error:
            print(f"Error: {response.error}")
        print()


def main():
    """Run all demonstrations"""
    print("TikTrue Standardized WebSocket Protocol Demonstration")
    print("=" * 60)
    print()
    
    demo_inference_request()
    demo_inference_response()
    demo_heartbeat_messages()
    demo_protocol_validation()
    demo_message_flow()
    demo_license_status_handling()
    
    print("=" * 60)
    print("Protocol demonstration completed successfully!")
    print()
    print("Key Features Demonstrated:")
    print("✓ Standardized message formats with validation")
    print("✓ License hash integration in all requests")
    print("✓ License status tracking in all responses")
    print("✓ Comprehensive error handling")
    print("✓ JSON serialization and parsing")
    print("✓ Message validation and protocol compliance")
    print("✓ Heartbeat messages for connection monitoring")
    print("✓ Complete request-response flow")


if __name__ == "__main__":
    main()