"""
Test Enhanced WebSocket Handler
Tests the enhanced handler that adds protocol support to model_node.py
"""

import asyncio
import json
import unittest
from datetime import datetime, timedelta
import uuid
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# Add current directory to path
sys.path.insert(0, os.getcwd())

# Import required modules
from core.protocol_spec import (
    ProtocolManager, MessageType, ErrorCode, InferenceRequest
)
from license_models import LicenseInfo, SubscriptionTier, ValidationStatus
from security.license_validator import LicenseValidator
from network.enhanced_websocket_handler import ProtocolEnhancedHandler, get_enhanced_handler


class TestProtocolEnhancedHandler(unittest.TestCase):
    """Test protocol enhanced handler functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.handler = ProtocolEnhancedHandler()
        self.protocol_manager = ProtocolManager()
        
        # Create test license
        self.test_license = LicenseInfo(
            license_key="test_enhanced_key_12345",
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
    
    def test_handler_initialization(self):
        """Test handler initialization"""
        self.assertIsInstance(self.handler.protocol_manager, ProtocolManager)
        self.assertEqual(self.handler.legacy_requests, 0)
        self.assertEqual(self.handler.protocol_requests, 0)
        self.assertEqual(self.handler.total_requests, 0)
    
    def test_protocol_message_detection(self):
        """Test protocol message detection"""
        # Test standard protocol message
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
        
        self.assertTrue(self.handler.is_standard_protocol_message(standard_message))
        
        # Test legacy message
        legacy_message = {
            "session_id": "test_session",
            "step": 0,
            "input_tensors": {"input_ids": [1, 2, 3]}
        }
        
        self.assertFalse(self.handler.is_standard_protocol_message(legacy_message))
        
        # Test invalid message
        invalid_message = {
            "random_field": "value"
        }
        
        self.assertFalse(self.handler.is_standard_protocol_message(invalid_message))
    
    def test_get_stats(self):
        """Test statistics collection"""
        # Initial stats
        stats = self.handler.get_stats()
        self.assertEqual(stats["total_requests"], 0)
        self.assertEqual(stats["legacy_requests"], 0)
        self.assertEqual(stats["protocol_requests"], 0)
        self.assertEqual(stats["protocol_percentage"], 0)
        
        # Simulate some requests
        self.handler.total_requests = 10
        self.handler.legacy_requests = 6
        self.handler.protocol_requests = 4
        
        stats = self.handler.get_stats()
        self.assertEqual(stats["total_requests"], 10)
        self.assertEqual(stats["legacy_requests"], 6)
        self.assertEqual(stats["protocol_requests"], 4)
        self.assertEqual(stats["protocol_percentage"], 40.0)
    
    def test_global_handler_instance(self):
        """Test global handler instance"""
        handler1 = get_enhanced_handler()
        handler2 = get_enhanced_handler()
        
        # Should be the same instance
        self.assertIs(handler1, handler2)
        self.assertIsInstance(handler1, ProtocolEnhancedHandler)


class TestProtocolEnhancedHandlerAsync(unittest.IsolatedAsyncioTestCase):
    """Test async functionality of enhanced handler"""
    
    async def asyncSetUp(self):
        """Set up async test environment"""
        self.handler = ProtocolEnhancedHandler()
        self.mock_websocket = Mock()
        self.mock_websocket.send = AsyncMock()
        
        # Mock execute_pipeline function
        self.mock_execute_pipeline = AsyncMock(return_value={
            "status": "success",
            "output_tensors": "Test response output",
            "processing_time": 0.1
        })
    
    async def test_process_legacy_message(self):
        """Test processing legacy message"""
        legacy_message = json.dumps({
            "session_id": "test_session",
            "step": 0,
            "input_tensors": {"input_ids": [1, 2, 3]}
        })
        
        # Should return False (not handled by protocol handler)
        handled = await self.handler.process_message(
            self.mock_websocket, 
            legacy_message, 
            self.mock_execute_pipeline
        )
        
        self.assertFalse(handled)
        self.assertEqual(self.handler.legacy_requests, 1)
        self.assertEqual(self.handler.protocol_requests, 0)
    
    async def test_process_protocol_message(self):
        """Test processing standard protocol message"""
        protocol_message = json.dumps({
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.INFERENCE_REQUEST.value,
                "protocol_version": "2.0",
                "timestamp": datetime.now().isoformat()
            },
            "model_id": "test_model",
            "prompt": "Test prompt"
        })
        
        # Should return True (handled by protocol handler)
        handled = await self.handler.process_message(
            self.mock_websocket, 
            protocol_message, 
            self.mock_execute_pipeline
        )
        
        self.assertTrue(handled)
        self.assertEqual(self.handler.legacy_requests, 0)
        self.assertEqual(self.handler.protocol_requests, 1)
        
        # Should have called execute_pipeline
        self.mock_execute_pipeline.assert_called_once()
        
        # Should have sent response
        self.mock_websocket.send.assert_called_once()
    
    async def test_process_invalid_json(self):
        """Test processing invalid JSON"""
        invalid_json = "{ invalid json }"
        
        # Should return False (let legacy handler deal with it)
        handled = await self.handler.process_message(
            self.mock_websocket, 
            invalid_json, 
            self.mock_execute_pipeline
        )
        
        self.assertFalse(handled)
    
    async def test_handle_heartbeat(self):
        """Test heartbeat message handling"""
        heartbeat_message = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.HEARTBEAT.value,
                "protocol_version": "2.0",
                "timestamp": datetime.now().isoformat()
            },
            "worker_id": "test_worker"
        }
        
        await self.handler._handle_heartbeat(self.mock_websocket, heartbeat_message)
        
        # Should have sent heartbeat response
        self.mock_websocket.send.assert_called_once()
        
        # Verify response format
        sent_data = self.mock_websocket.send.call_args[0][0]
        response_dict = json.loads(sent_data)
        
        self.assertIn("header", response_dict)
        self.assertEqual(response_dict["header"]["message_type"], "heartbeat")
        self.assertIn("worker_id", response_dict)
        self.assertIn("status", response_dict)
    
    async def test_handle_authentication(self):
        """Test authentication message handling"""
        auth_message = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.AUTHENTICATION.value,
                "protocol_version": "2.0",
                "timestamp": datetime.now().isoformat()
            },
            "license_key": "test_license_key"
        }
        
        # Mock license validation
        with patch.object(self.handler.license_validator, 'validate_license') as mock_validate:
            mock_license = Mock()
            mock_license.status = ValidationStatus.VALID
            mock_validate.return_value = mock_license
            
            await self.handler._handle_authentication(self.mock_websocket, auth_message)
            
            # Should have sent success response
            self.mock_websocket.send.assert_called_once()
            mock_validate.assert_called_once_with("test_license_key", "test_hardware")
    
    async def test_handle_authentication_failure(self):
        """Test authentication failure handling"""
        auth_message = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.AUTHENTICATION.value,
                "protocol_version": "2.0",
                "timestamp": datetime.now().isoformat()
            },
            "license_key": "invalid_license_key"
        }
        
        # Mock license validation failure
        with patch.object(self.handler.license_validator, 'validate_license') as mock_validate:
            mock_license = Mock()
            mock_license.status = ValidationStatus.INVALID
            mock_validate.return_value = mock_license
            
            await self.handler._handle_authentication(self.mock_websocket, auth_message)
            
            # Should have sent error response
            self.mock_websocket.send.assert_called_once()
            
            # Verify error response format
            sent_data = self.mock_websocket.send.call_args[0][0]
            response_dict = json.loads(sent_data)
            
            self.assertEqual(response_dict["header"]["message_type"], "error")
            self.assertEqual(response_dict["error_code"], ErrorCode.AUTHENTICATION_FAILED.value)
    
    async def test_protocol_inference_request(self):
        """Test protocol inference request handling"""
        inference_message = {
            "header": {
                "message_id": str(uuid.uuid4()),
                "message_type": MessageType.INFERENCE_REQUEST.value,
                "protocol_version": "2.0",
                "timestamp": datetime.now().isoformat()
            },
            "model_id": "test_model",
            "prompt": "Hello, world!",
            "max_tokens": 50,
            "temperature": 0.8
        }
        
        await self.handler._handle_protocol_inference_request(
            self.mock_websocket, 
            inference_message, 
            self.mock_execute_pipeline
        )
        
        # Should have called execute_pipeline with converted parameters
        self.mock_execute_pipeline.assert_called_once()
        call_args = self.mock_execute_pipeline.call_args
        
        self.assertIn("session_id", call_args.kwargs)
        self.assertEqual(call_args.kwargs["step"], 0)
        self.assertIn("initial_inputs", call_args.kwargs)
        
        # Check converted input_tensors
        input_tensors = call_args.kwargs["initial_inputs"]
        self.assertEqual(input_tensors["input_ids"], "Hello, world!")
        self.assertEqual(input_tensors["model_id"], "test_model")
        self.assertEqual(input_tensors["max_tokens"], 50)
        self.assertEqual(input_tensors["temperature"], 0.8)
        
        # Should have sent protocol response
        self.mock_websocket.send.assert_called_once()
        
        # Verify response format
        sent_data = self.mock_websocket.send.call_args[0][0]
        response_dict = json.loads(sent_data)
        
        self.assertIn("header", response_dict)
        self.assertEqual(response_dict["header"]["message_type"], "inference_response")
        self.assertIn("generated_text", response_dict)
        self.assertIn("processing_time_ms", response_dict)


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility with existing model_node.py"""
    
    def test_enhanced_handler_import(self):
        """Test that enhanced handler can be imported without issues"""
        from network.enhanced_websocket_handler import enhanced_websocket_handler, get_enhanced_handler
        
        # Should be able to import without errors
        self.assertTrue(callable(enhanced_websocket_handler))
        self.assertIsInstance(get_enhanced_handler(), ProtocolEnhancedHandler)
    
    def test_handler_function_signature(self):
        """Test that enhanced handler has compatible signature"""
        from network.enhanced_websocket_handler import enhanced_websocket_handler
        import inspect
        
        # Should accept websocket and optional path parameter
        sig = inspect.signature(enhanced_websocket_handler)
        params = list(sig.parameters.keys())
        
        self.assertIn("websocket", params)
        self.assertIn("path", params)
        
        # path should be optional
        path_param = sig.parameters["path"]
        self.assertEqual(path_param.default, None)


if __name__ == "__main__":
    print("Running Enhanced WebSocket Handler Tests...")
    unittest.main(verbosity=2)