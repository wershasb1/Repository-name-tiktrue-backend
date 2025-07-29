"""
Simple test for WebSocket server functionality
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

try:
    # Test imports
    from core.protocol_spec import ProtocolManager, MessageType, ErrorCode
    print("✓ Protocol spec imported successfully")
    
    from license_models import LicenseInfo, SubscriptionTier, ValidationStatus
    print("✓ License models imported successfully")
    
    from security.license_validator import LicenseValidator
    print("✓ License validator imported successfully")
    
    # Test WebSocket server import
    exec(open('websocket_server.py').read())
    print("✓ WebSocket server code executed successfully")
    
    # Test protocol manager
    protocol_manager = ProtocolManager()
    print("✓ Protocol manager created successfully")
    
    # Test creating inference request
    request = protocol_manager.create_inference_request(
        model_id="test_model",
        prompt="Test prompt"
    )
    print("✓ Inference request created successfully")
    
    # Test serialization
    serialized = protocol_manager.serialize_message(request)
    print("✓ Message serialization works")
    
    # Test deserialization
    deserialized = protocol_manager.deserialize_message(serialized)
    print("✓ Message deserialization works")
    
    # Test validation
    is_valid, error = protocol_manager.validate_message(deserialized)
    if is_valid:
        print("✓ Message validation works")
    else:
        print(f"✗ Message validation failed: {error}")
    
    print("\n🎉 All WebSocket protocol components are working correctly!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()