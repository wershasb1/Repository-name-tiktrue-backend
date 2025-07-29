"""
Integration tests for network discovery using UDP broadcast
Tests the complete discovery workflow including license filtering
"""

import asyncio
import json
import logging
import socket
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any

from network.network_discovery import (
    NetworkDiscoveryService, 
    DiscoveryMessageType,
    DiscoveryRequest,
    DiscoveryResponse,
    create_discovery_service,
    quick_network_discovery
)
from core.network_manager import NetworkInfo, NetworkType, NetworkStatus
from license_models import SubscriptionTier, LicenseInfo

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestNetworkDiscovery(unittest.TestCase):
    """Test network discovery functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.node_id = "test_node_001"
        self.test_networks = self._create_test_networks()
        self.mock_license = self._create_mock_license()
        
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def _create_test_networks(self) -> Dict[str, NetworkInfo]:
        """Create test network configurations"""
        networks = {}
        
        # Public network for FREE tier
        networks["net_001"] = NetworkInfo(
            network_id="net_001",
            network_name="Public Test Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="admin_001",
            admin_host="192.168.1.100",
            admin_port=8080,
            model_id="llama-7b",
            model_name="Llama 7B",
            required_license_tier=SubscriptionTier.FREE,
            max_clients=10,
            current_clients=2,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        # Private network for PRO tier
        networks["net_002"] = NetworkInfo(
            network_id="net_002",
            network_name="Private Test Network",
            network_type=NetworkType.PRIVATE,
            admin_node_id="admin_002",
            admin_host="192.168.1.101",
            admin_port=8080,
            model_id="llama-13b",
            model_name="Llama 13B",
            required_license_tier=SubscriptionTier.PRO,
            max_clients=20,
            current_clients=4,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        # Enterprise network for ENT tier
        networks["net_003"] = NetworkInfo(
            network_id="net_003",
            network_name="Enterprise Test Network",
            network_type=NetworkType.ENTERPRISE,
            admin_node_id="admin_003",
            admin_host="192.168.1.102",
            admin_port=8080,
            model_id="gpt-4",
            model_name="GPT-4",
            required_license_tier=SubscriptionTier.ENT,
            max_clients=100,
            current_clients=8,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        return networks
    
    def _create_mock_license(self) -> LicenseInfo:
        """Create mock license for testing"""
        return LicenseInfo(
            license_key="TIKT-PRO-12M-TEST001",
            user_id="test_user_001",
            plan_type="PRO",
            expiry_date=datetime.now().isoformat(),
            max_clients=20,
            allowed_models=["llama-7b", "llama-13b"],
            hardware_fingerprint="test_hw_sig",
            is_active=True,
            created_at=datetime.now().isoformat(),
            last_validated=datetime.now().isoformat()
        )
    
    @patch('network_discovery.get_license_enforcer')
    def test_discovery_service_initialization(self, mock_get_enforcer):
        """Test discovery service initialization"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_get_enforcer.return_value = mock_enforcer
        
        # Create discovery service
        discovery = NetworkDiscoveryService(self.node_id, self.test_networks)
        
        # Verify initialization
        self.assertEqual(discovery.node_id, self.node_id)
        self.assertEqual(len(discovery.managed_networks), 3)
        self.assertFalse(discovery.running)
        self.assertEqual(discovery.stats['discovery_requests_sent'], 0)
    
    @patch('network_discovery.get_license_enforcer')
    def test_discovery_message_creation(self, mock_get_enforcer):
        """Test discovery message creation and serialization"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_get_enforcer.return_value = mock_enforcer
        
        # Create discovery request
        request = DiscoveryRequest(
            node_id=self.node_id,
            license_tier="PRO",
            requested_network_types=["public", "private"],
            supported_models=["llama-7b", "llama-13b"]
        )
        
        # Test serialization
        request_dict = request.to_dict()
        self.assertEqual(request_dict['message_type'], "discovery_request")
        self.assertEqual(request_dict['node_id'], self.node_id)
        self.assertEqual(request_dict['license_tier'], "PRO")
        self.assertIn("public", request_dict['requested_network_types'])
        self.assertIn("private", request_dict['requested_network_types'])
        
        # Test JSON serialization
        json_data = json.dumps(request_dict, default=str)
        self.assertIsInstance(json_data, str)
        
        # Test deserialization
        parsed_data = json.loads(json_data)
        self.assertEqual(parsed_data['message_type'], "discovery_request")
    
    @patch('network_discovery.get_license_enforcer')
    def test_license_compatibility_filtering(self, mock_get_enforcer):
        """Test license-based network filtering"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_enforcer.current_license = self.mock_license
        mock_get_enforcer.return_value = mock_enforcer
        
        discovery = NetworkDiscoveryService(self.node_id, self.test_networks)
        
        # Test FREE tier compatibility (should only see public networks)
        free_compatible = discovery._is_license_compatible(
            self.test_networks["net_001"], "FREE"
        )
        self.assertTrue(free_compatible)
        
        pro_compatible_for_free = discovery._is_license_compatible(
            self.test_networks["net_002"], "FREE"
        )
        self.assertFalse(pro_compatible_for_free)
        
        # Test PRO tier compatibility (should see public and private)
        pro_public_compatible = discovery._is_license_compatible(
            self.test_networks["net_001"], "PRO"
        )
        self.assertTrue(pro_public_compatible)
        
        pro_private_compatible = discovery._is_license_compatible(
            self.test_networks["net_002"], "PRO"
        )
        self.assertTrue(pro_private_compatible)
        
        ent_compatible_for_pro = discovery._is_license_compatible(
            self.test_networks["net_003"], "PRO"
        )
        self.assertFalse(ent_compatible_for_pro)
    
    @patch('network_discovery.get_license_enforcer')
    def test_network_accessibility_check(self, mock_get_enforcer):
        """Test network accessibility validation"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_get_enforcer.return_value = mock_enforcer
        
        discovery = NetworkDiscoveryService(self.node_id)
        
        # Test active network accessibility
        active_network = self.test_networks["net_001"]
        self.assertTrue(discovery._is_network_accessible(active_network))
        
        # Test inactive network accessibility
        inactive_network = NetworkInfo(
            network_id="net_inactive",
            network_name="Inactive Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="admin_inactive",
            admin_host="192.168.1.200",
            admin_port=8080,
            model_id="test-model",
            model_name="Test Model",
            required_license_tier=SubscriptionTier.FREE,
            max_clients=0,
            current_clients=0,
            status=NetworkStatus.INACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        self.assertFalse(discovery._is_network_accessible(inactive_network))
    
    @patch('network_discovery.get_license_enforcer')
    def test_node_capabilities_generation(self, mock_get_enforcer):
        """Test node capabilities information generation"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_enforcer.current_license = self.mock_license
        mock_enforcer.get_license_status.return_value = {
            'valid': True,
            'can_create_networks': True,
            'can_join_networks': True
        }
        mock_get_enforcer.return_value = mock_enforcer
        
        discovery = NetworkDiscoveryService(self.node_id)
        capabilities = discovery._get_node_capabilities()
        
        # Verify capabilities structure
        self.assertIn('license_tier', capabilities)
        self.assertIn('license_valid', capabilities)
        self.assertIn('max_clients', capabilities)
        self.assertIn('allowed_models', capabilities)
        self.assertIn('can_create_networks', capabilities)
        self.assertIn('can_join_networks', capabilities)
        self.assertIn('discovery_version', capabilities)
        
        # Verify values
        self.assertEqual(capabilities['license_tier'], 'PRO')
        self.assertTrue(capabilities['license_valid'])
        self.assertEqual(capabilities['max_clients'], 20)
        self.assertIn('llama-7b', capabilities['allowed_models'])
        self.assertTrue(capabilities['can_create_networks'])
        self.assertTrue(capabilities['can_join_networks'])
    
    @patch('network_discovery.get_license_enforcer')
    def test_network_serialization(self, mock_get_enforcer):
        """Test network information serialization and deserialization"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_get_enforcer.return_value = mock_enforcer
        
        discovery = NetworkDiscoveryService(self.node_id)
        
        # Test network to dict conversion
        network = self.test_networks["net_001"]
        network_dict = discovery._network_to_dict(network)
        
        # Verify serialization
        self.assertEqual(network_dict['network_id'], "net_001")
        self.assertEqual(network_dict['network_name'], "Public Test Network")
        self.assertEqual(network_dict['model_id'], "llama-7b")
        self.assertEqual(network_dict['network_type'], "public")
        self.assertEqual(network_dict['required_license_tier'], "FREE")
        self.assertEqual(network_dict['status'], "active")
        
        # Test dict to network conversion
        reconstructed_network = discovery._dict_to_network_info(network_dict)
        
        # Verify deserialization
        self.assertIsNotNone(reconstructed_network)
        self.assertEqual(reconstructed_network.network_id, "net_001")
        self.assertEqual(reconstructed_network.network_name, "Public Test Network")
        self.assertEqual(reconstructed_network.model_id, "llama-7b")
        self.assertEqual(reconstructed_network.network_type, NetworkType.PUBLIC)
        self.assertEqual(reconstructed_network.required_license_tier, SubscriptionTier.FREE)
        self.assertEqual(reconstructed_network.status, NetworkStatus.ACTIVE)
    
    @patch('network_discovery.get_license_enforcer')
    def test_discovery_statistics(self, mock_get_enforcer):
        """Test discovery service statistics tracking"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_get_enforcer.return_value = mock_enforcer
        
        discovery = NetworkDiscoveryService(self.node_id, self.test_networks)
        
        # Get initial statistics
        stats = discovery.get_discovery_statistics()
        
        # Verify statistics structure
        self.assertIn('discovery_requests_sent', stats)
        self.assertIn('discovery_responses_received', stats)
        self.assertIn('discovery_responses_sent', stats)
        self.assertIn('heartbeats_sent', stats)
        self.assertIn('heartbeats_received', stats)
        self.assertIn('networks_discovered', stats)
        self.assertIn('nodes_discovered', stats)
        self.assertIn('service_running', stats)
        self.assertIn('discovered_networks_count', stats)
        self.assertIn('discovered_nodes_count', stats)
        self.assertIn('managed_networks_count', stats)
        
        # Verify initial values
        self.assertEqual(stats['discovery_requests_sent'], 0)
        self.assertEqual(stats['discovery_responses_received'], 0)
        self.assertEqual(stats['managed_networks_count'], 3)
        self.assertFalse(stats['service_running'])
    
    def test_utility_functions(self):
        """Test utility functions"""
        # Test create_discovery_service function
        discovery = create_discovery_service("test_node", self.test_networks)
        self.assertIsInstance(discovery, NetworkDiscoveryService)
        self.assertEqual(discovery.node_id, "test_node")
        self.assertEqual(len(discovery.managed_networks), 3)
    
    @patch('network_discovery.get_license_enforcer')
    async def test_discovery_timeout_handling(self, mock_get_enforcer):
        """Test discovery timeout and retry mechanisms"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_enforcer.current_license = self.mock_license
        mock_enforcer.get_license_status.return_value = {'valid': True}
        mock_get_enforcer.return_value = mock_enforcer
        
        discovery = NetworkDiscoveryService(self.node_id)
        
        # Mock socket operations to simulate timeout
        with patch.object(discovery, '_send_multicast_message', return_value=True):
            start_time = time.time()
            
            # Test discovery with short timeout
            networks = await discovery.discover_networks(timeout=1.0)
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            # Verify timeout was respected (allow some margin for processing)
            self.assertLess(elapsed, 2.0)
            self.assertIsInstance(networks, list)
    
    @patch('network_discovery.get_license_enforcer')
    def test_message_size_validation(self, mock_get_enforcer):
        """Test message size validation for UDP packets"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_get_enforcer.return_value = mock_enforcer
        
        discovery = NetworkDiscoveryService(self.node_id)
        
        # Create a large message that exceeds buffer size
        large_message = {
            "message_type": "test",
            "large_data": "x" * (discovery.BUFFER_SIZE + 1000)
        }
        
        # Mock socket to test size validation
        with patch.object(discovery, 'discovery_socket', Mock()):
            result = discovery._send_multicast_message(large_message)
            self.assertFalse(result)  # Should fail due to size limit
        
        # Test normal-sized message
        normal_message = {
            "message_type": "test",
            "data": "normal sized data"
        }
        
        with patch.object(discovery, 'discovery_socket', Mock()) as mock_socket:
            mock_socket.sendto = Mock()
            result = discovery._send_multicast_message(normal_message)
            # Should succeed (though socket operations are mocked)
            mock_socket.sendto.assert_called_once()


class TestNetworkDiscoveryIntegration(unittest.TestCase):
    """Integration tests for network discovery"""
    
    @patch('network_discovery.get_license_enforcer')
    async def test_quick_discovery_function(self, mock_get_enforcer):
        """Test quick discovery utility function"""
        # Mock license enforcer
        mock_enforcer = Mock()
        mock_license = LicenseInfo(
            license_key="TIKT-FREE-12M-TEST001",
            user_id="test_user_002",
            plan_type="FREE",
            expiry_date=datetime.now().isoformat(),
            max_clients=3,
            allowed_models=["llama-7b"],
            hardware_fingerprint="test_hw_sig",
            is_active=True,
            created_at=datetime.now().isoformat(),
            last_validated=datetime.now().isoformat()
        )
        mock_enforcer.current_license = mock_license
        mock_enforcer.get_license_status.return_value = {'valid': True}
        mock_get_enforcer.return_value = mock_enforcer
        
        # Test quick discovery with short timeout
        with patch('network_discovery.NetworkDiscoveryService') as mock_service_class:
            mock_service = Mock()
            mock_service.start_service.return_value = True
            mock_service.discover_networks.return_value = []
            mock_service.stop_service.return_value = None
            mock_service_class.return_value = mock_service
            
            networks = await quick_network_discovery(timeout=1.0)
            
            # Verify service lifecycle
            mock_service.start_service.assert_called_once()
            mock_service.discover_networks.assert_called_once()
            mock_service.stop_service.assert_called_once()
            
            self.assertIsInstance(networks, list)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)