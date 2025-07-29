"""
Simple test for multi-network service components
"""

import unittest
import tempfile
import shutil
from unittest.mock import Mock, patch
from datetime import datetime

# Test basic imports first
def test_imports():
    """Test that we can import required modules"""
    try:
        from core.network_manager import NetworkManager, NetworkInfo, NetworkType, NetworkStatus
        print("✓ Core network manager imports successful")
    except Exception as e:
        print(f"✗ Core network manager import failed: {e}")
        return False
    
    try:
        from license_enforcer import get_license_enforcer
        print("✓ License enforcer import successful")
    except Exception as e:
        print(f"✗ License enforcer import failed: {e}")
        return False
    
    try:
        from license_models import SubscriptionTier
        print("✓ License models import successful")
    except Exception as e:
        print(f"✗ License models import failed: {e}")
        return False
    
    return True

# Test basic functionality without full multi-network service
class TestBasicNetworkManagement(unittest.TestCase):
    """Basic network management tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock license enforcer
        from license_models import SubscriptionTier
        self.mock_license = Mock()
        self.mock_license.plan = SubscriptionTier.PRO
        self.mock_license.max_clients = 50
        
        with patch('core.network_manager.get_license_enforcer') as mock_get_enforcer:
            mock_enforcer = Mock()
            mock_enforcer.get_license_status.return_value = {'valid': True}
            mock_enforcer.current_license = self.mock_license
            mock_enforcer.check_model_access_allowed.return_value = True
            mock_get_enforcer.return_value = mock_enforcer
            
            from core.network_manager import NetworkManager
            self.network_manager = NetworkManager(self.temp_dir, "test_node")
    
    def tearDown(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir)
    
    def test_network_manager_initialization(self):
        """Test network manager initialization"""
        self.assertEqual(self.network_manager.node_id, "test_node")
        self.assertEqual(len(self.network_manager.managed_networks), 0)
    
    def test_network_creation_basic(self):
        """Test basic network creation"""
        from core.network_manager import NetworkType
        
        network_info = self.network_manager.create_network(
            network_name="Test Network",
            model_id="llama3_1_8b_fp16",
            network_type=NetworkType.PUBLIC,
            description="Test network"
        )
        
        self.assertIsNotNone(network_info)
        self.assertEqual(network_info.network_name, "Test Network")
        self.assertEqual(network_info.model_id, "llama3_1_8b_fp16")
        self.assertIn(network_info.network_id, self.network_manager.managed_networks)


if __name__ == '__main__':
    print("Testing Multi-Network Service Components")
    print("=" * 50)
    
    # Test imports first
    if not test_imports():
        print("Import tests failed - cannot proceed")
        exit(1)
    
    print("\nRunning basic functionality tests...")
    unittest.main(verbosity=2)