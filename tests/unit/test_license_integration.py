"""
Integration tests for license enforcement in the distributed inference system
Tests license validation across all system components
"""

import unittest
import tempfile
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from license_enforcer import LicenseEnforcer, get_license_enforcer
from security.license_validator import LicenseValidator, LicenseInfo, SubscriptionTier, LicenseStatus
from license_storage import LicenseStorage
from model_node_license_integration import enhanced_websocket_handler, simulate_pipeline_execution


class TestLicenseEnforcementIntegration(unittest.TestCase):
    """Test license enforcement integration across system components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.enforcer = LicenseEnforcer(self.temp_dir)
        
        # Create test licenses
        self.valid_pro_license = LicenseInfo(
            license_key="TIKT-PRO-6M-XYZ789",
            plan=SubscriptionTier.PRO,
            duration_months=6,
            unique_id="XYZ789",
            expires_at=datetime.now() + timedelta(days=180),
            max_clients=20,
            allowed_models=['llama3_1_8b_fp16', 'mistral_7b_int4'],
            allowed_features=['advanced_chat', 'session_save'],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        
        self.expired_license = LicenseInfo(
            license_key="TIKT-PRO-6M-EXPIRED",
            plan=SubscriptionTier.PRO,
            duration_months=6,
            unique_id="EXPIRED",
            expires_at=datetime.now() - timedelta(days=1),
            max_clients=20,
            allowed_models=['llama3_1_8b_fp16'],
            allowed_features=['advanced_chat'],
            status=LicenseStatus.EXPIRED,
            hardware_signature="test_signature",
            created_at=datetime.now() - timedelta(days=180),
            checksum="test_checksum"
        )
        
        self.free_license = LicenseInfo(
            license_key="TIKT-FREE-1M-ABC123",
            plan=SubscriptionTier.FREE,
            duration_months=1,
            unique_id="ABC123",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=3,
            allowed_models=['basic_model'],
            allowed_features=['basic_chat'],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_license_enforcer_initialization(self):
        """Test license enforcer initialization and basic functionality"""
        # Test without license
        status = self.enforcer.get_license_status()
        self.assertEqual(status['status'], 'no_license')
        self.assertFalse(status['valid'])
        
        # Install valid license
        self.enforcer.current_license = self.valid_pro_license
        status = self.enforcer.get_license_status()
        self.assertEqual(status['status'], 'valid')
        self.assertEqual(status['plan'], 'PRO')
        self.assertTrue(status['valid'])
    
    async def test_client_connection_limits(self):
        """Test client connection limit enforcement"""
        # Install PRO license (20 clients max)
        self.enforcer.current_license = self.valid_pro_license
        
        # Test successful connections within limit
        for i in range(20):
            client_id = f"client_{i}"
            allowed = await self.enforcer.check_client_connection_allowed(client_id, "test_network")
            self.assertTrue(allowed, f"Client {i} should be allowed")
        
        # Test connection beyond limit
        client_21 = await self.enforcer.check_client_connection_allowed("client_21", "test_network")
        self.assertFalse(client_21, "Client 21 should be denied (over limit)")
        
        # Test with FREE license (3 clients max)
        self.enforcer.current_license = self.free_license
        self.enforcer.active_clients.clear()  # Reset connections
        
        # Allow 3 connections
        for i in range(3):
            client_id = f"free_client_{i}"
            allowed = await self.enforcer.check_client_connection_allowed(client_id, "test_network")
            self.assertTrue(allowed, f"Free client {i} should be allowed")
        
        # Deny 4th connection
        client_4 = await self.enforcer.check_client_connection_allowed("free_client_4", "test_network")
        self.assertFalse(client_4, "4th free client should be denied")
    
    def test_model_access_control(self):
        """Test model access control based on license tier"""
        # Test with PRO license
        self.enforcer.current_license = self.valid_pro_license
        
        # Allowed models
        self.assertTrue(self.enforcer.check_model_access_allowed('llama3_1_8b_fp16'))
        self.assertTrue(self.enforcer.check_model_access_allowed('mistral_7b_int4'))
        
        # Denied models
        self.assertFalse(self.enforcer.check_model_access_allowed('premium_enterprise_model'))
        
        # Test with FREE license
        self.enforcer.current_license = self.free_license
        
        # Only basic model allowed
        self.assertTrue(self.enforcer.check_model_access_allowed('basic_model'))
        self.assertFalse(self.enforcer.check_model_access_allowed('llama3_1_8b_fp16'))
    
    def test_feature_access_control(self):
        """Test feature access control based on license tier"""
        # Test with PRO license
        self.enforcer.current_license = self.valid_pro_license
        
        # Allowed features
        self.assertTrue(self.enforcer.check_feature_access_allowed('advanced_chat'))
        self.assertTrue(self.enforcer.check_feature_access_allowed('session_save'))
        
        # Denied features
        self.assertFalse(self.enforcer.check_feature_access_allowed('admin_panel'))
        
        # Test with FREE license
        self.enforcer.current_license = self.free_license
        
        # Only basic features allowed
        self.assertTrue(self.enforcer.check_feature_access_allowed('basic_chat'))
        self.assertFalse(self.enforcer.check_feature_access_allowed('session_save'))
    
    def test_expired_license_handling(self):
        """Test handling of expired licenses"""
        self.enforcer.current_license = self.expired_license
        
        # All operations should be denied
        self.assertFalse(self.enforcer._is_license_valid())
        self.assertFalse(self.enforcer.check_model_access_allowed('llama3_1_8b_fp16'))
        self.assertFalse(self.enforcer.check_feature_access_allowed('advanced_chat'))
        
        # Status should reflect expiry
        status = self.enforcer.get_license_status()
        self.assertFalse(status['valid'])
        self.assertLessEqual(status['days_remaining'], 0)


class TestWebSocketHandlerIntegration(unittest.TestCase):
    """Test WebSocket handler integration with license validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock WebSocket
        self.mock_websocket = AsyncMock()
        self.mock_websocket.remote_address = ("127.0.0.1", 12345)
        
        # Create test license
        self.valid_license = LicenseInfo(
            license_key="TIKT-PRO-6M-XYZ789",
            plan=SubscriptionTier.PRO,
            duration_months=6,
            unique_id="XYZ789",
            expires_at=datetime.now() + timedelta(days=180),
            max_clients=20,
            allowed_models=['llama3_1_8b_fp16', 'mistral_7b_int4'],
            allowed_features=['advanced_chat', 'session_save'],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_websocket_handler_with_valid_license(self):
        """Test WebSocket handler with valid license"""
        # Install valid license
        enforcer = get_license_enforcer(self.temp_dir)
        enforcer.current_license = self.valid_license
        
        # Create test request
        test_request = {
            "session_id": "test_session",
            "step": 0,
            "network_id": "test_network",
            "model_id": "llama3_1_8b_fp16",
            "input_tensors": {
                "input_ids": [[1, 2, 3, 4, 5]]
            }
        }
        
        # Mock WebSocket messages
        messages = [json.dumps(test_request)]
        self.mock_websocket.__aiter__.return_value = iter(messages)
        
        # Mock send method to capture responses
        sent_responses = []
        async def mock_send(data):
            sent_responses.append(json.loads(data))
        self.mock_websocket.send = mock_send
        
        # Run handler
        await enhanced_websocket_handler(self.mock_websocket)
        
        # Verify response
        self.assertEqual(len(sent_responses), 1)
        response = sent_responses[0]
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['license_status'], 'valid')
        self.assertEqual(response['network_id'], 'test_network')
    
    async def test_websocket_handler_with_invalid_license(self):
        """Test WebSocket handler with invalid license"""
        # No license installed
        enforcer = get_license_enforcer(self.temp_dir)
        enforcer.current_license = None
        
        # Create test request
        test_request = {
            "session_id": "test_session",
            "step": 0,
            "network_id": "test_network",
            "model_id": "llama3_1_8b_fp16",
            "input_tensors": {
                "input_ids": [[1, 2, 3, 4, 5]]
            }
        }
        
        # Mock WebSocket messages
        messages = [json.dumps(test_request)]
        self.mock_websocket.__aiter__.return_value = iter(messages)
        
        # Mock send method to capture responses
        sent_responses = []
        async def mock_send(data):
            sent_responses.append(json.loads(data))
        self.mock_websocket.send = mock_send
        
        # Run handler
        await enhanced_websocket_handler(self.mock_websocket)
        
        # Verify license error response
        self.assertEqual(len(sent_responses), 1)
        response = sent_responses[0]
        self.assertEqual(response['status'], 'license_error')
        self.assertIn('Invalid license', response['message'])
    
    async def test_websocket_handler_model_access_denied(self):
        """Test WebSocket handler with model access denied"""
        # Install license with limited model access
        free_license = LicenseInfo(
            license_key="TIKT-FREE-1M-ABC123",
            plan=SubscriptionTier.FREE,
            duration_months=1,
            unique_id="ABC123",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=3,
            allowed_models=['basic_model'],
            allowed_features=['basic_chat'],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        
        enforcer = get_license_enforcer(self.temp_dir)
        enforcer.current_license = free_license
        
        # Request access to premium model
        test_request = {
            "session_id": "test_session",
            "step": 0,
            "network_id": "test_network",
            "model_id": "llama3_1_8b_fp16",  # Not allowed for FREE tier
            "input_tensors": {
                "input_ids": [[1, 2, 3, 4, 5]]
            }
        }
        
        # Mock WebSocket messages
        messages = [json.dumps(test_request)]
        self.mock_websocket.__aiter__.return_value = iter(messages)
        
        # Mock send method to capture responses
        sent_responses = []
        async def mock_send(data):
            sent_responses.append(json.loads(data))
        self.mock_websocket.send = mock_send
        
        # Run handler
        await enhanced_websocket_handler(self.mock_websocket)
        
        # Verify model access denied response
        self.assertEqual(len(sent_responses), 1)
        response = sent_responses[0]
        self.assertEqual(response['status'], 'license_error')
        self.assertEqual(response['license_status'], 'model_access_denied')
        self.assertIn('Model access denied', response['message'])


class TestWorkerLicenseIntegration(unittest.TestCase):
    """Test worker integration with license validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test license
        self.valid_license = LicenseInfo(
            license_key="TIKT-PRO-6M-XYZ789",
            plan=SubscriptionTier.PRO,
            duration_months=6,
            unique_id="XYZ789",
            expires_at=datetime.now() + timedelta(days=180),
            max_clients=20,
            allowed_models=['llama3_1_8b_fp16', 'mistral_7b_int4'],
            allowed_features=['advanced_chat', 'session_save'],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_worker_model_access_validation(self):
        """Test worker model access validation"""
        from model_node_license_integration import create_license_aware_worker_factory
        
        # Install valid license
        enforcer = get_license_enforcer(self.temp_dir)
        enforcer.current_license = self.valid_license
        
        # Create license-aware worker factory
        create_cpu_worker, create_gpu_worker = create_license_aware_worker_factory()
        
        # This test would need actual worker implementation to be complete
        # For now, we test the factory creation
        self.assertIsNotNone(create_cpu_worker)
        self.assertIsNotNone(create_gpu_worker)


class TestConfigManagerIntegration(unittest.TestCase):
    """Test config manager integration with license validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test license
        self.valid_license = LicenseInfo(
            license_key="TIKT-PRO-6M-XYZ789",
            plan=SubscriptionTier.PRO,
            duration_months=6,
            unique_id="XYZ789",
            expires_at=datetime.now() + timedelta(days=180),
            max_clients=20,
            allowed_models=['llama3_1_8b_fp16', 'mistral_7b_int4'],
            allowed_features=['advanced_chat', 'session_save'],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_model_selection_validation(self):
        """Test model selection validation in config manager"""
        from model_node_license_integration import integrate_license_validation_into_config_manager
        
        # Install valid license
        enforcer = get_license_enforcer(self.temp_dir)
        enforcer.current_license = self.valid_license
        
        # Get integration functions
        validate_model_selection, get_allowed_models = integrate_license_validation_into_config_manager()
        
        # Test model validation
        self.assertTrue(validate_model_selection('llama3_1_8b_fp16'))
        self.assertFalse(validate_model_selection('unauthorized_model'))
        
        # Test allowed models list
        allowed_models = get_allowed_models()
        self.assertIn('llama3_1_8b_fp16', allowed_models)
        self.assertIn('mistral_7b_int4', allowed_models)


class TestLicenseIntegrationEndToEnd(unittest.TestCase):
    """End-to-end integration tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_complete_license_workflow(self):
        """Test complete license workflow from installation to usage"""
        # 1. Install license
        enforcer = LicenseEnforcer(self.temp_dir)
        success = enforcer.install_license("TIKT-PRO-6M-XYZ789")
        self.assertTrue(success)
        
        # 2. Verify license status
        status = enforcer.get_license_status()
        self.assertTrue(status['valid'])
        self.assertEqual(status['plan'], 'PRO')
        
        # 3. Test client connections
        client_allowed = await enforcer.check_client_connection_allowed("test_client", "test_network")
        self.assertTrue(client_allowed)
        
        # 4. Test model access
        model_allowed = enforcer.check_model_access_allowed("llama3_1_8b_fp16")
        self.assertTrue(model_allowed)
        
        # 5. Test feature access
        feature_allowed = enforcer.check_feature_access_allowed("session_save")
        self.assertTrue(feature_allowed)
        
        # 6. Get usage statistics
        stats = enforcer.get_usage_statistics()
        self.assertEqual(stats['active_clients'], 1)
        self.assertIn('llama3_1_8b_fp16', stats['accessed_models'])
        self.assertIn('session_save', stats['used_features'])
    
    def test_license_persistence_across_restarts(self):
        """Test license persistence across system restarts"""
        # Install license with first enforcer instance
        enforcer1 = LicenseEnforcer(self.temp_dir)
        success = enforcer1.install_license("TIKT-PRO-6M-XYZ789")
        self.assertTrue(success)
        
        # Create new enforcer instance (simulating restart)
        enforcer2 = LicenseEnforcer(self.temp_dir)
        
        # License should be loaded automatically
        status = enforcer2.get_license_status()
        self.assertTrue(status['valid'])
        self.assertEqual(status['plan'], 'PRO')


# Async test runner
class AsyncTestCase(unittest.TestCase):
    """Base class for async test cases"""
    
    def run_async_test(self, coro):
        """Run async test"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# Convert async tests to sync
class TestLicenseEnforcementIntegrationSync(TestLicenseEnforcementIntegration, AsyncTestCase):
    """Sync version of async tests"""
    
    def test_client_connection_limits_sync(self):
        """Sync version of client connection limits test"""
        self.run_async_test(self.test_client_connection_limits())


class TestWebSocketHandlerIntegrationSync(TestWebSocketHandlerIntegration, AsyncTestCase):
    """Sync version of async WebSocket tests"""
    
    def test_websocket_handler_with_valid_license_sync(self):
        """Sync version of WebSocket handler test"""
        self.run_async_test(self.test_websocket_handler_with_valid_license())
    
    def test_websocket_handler_with_invalid_license_sync(self):
        """Sync version of WebSocket handler test"""
        self.run_async_test(self.test_websocket_handler_with_invalid_license())
    
    def test_websocket_handler_model_access_denied_sync(self):
        """Sync version of WebSocket handler test"""
        self.run_async_test(self.test_websocket_handler_model_access_denied())


class TestLicenseIntegrationEndToEndSync(TestLicenseIntegrationEndToEnd, AsyncTestCase):
    """Sync version of end-to-end tests"""
    
    def test_complete_license_workflow_sync(self):
        """Sync version of complete workflow test"""
        self.run_async_test(self.test_complete_license_workflow())


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)