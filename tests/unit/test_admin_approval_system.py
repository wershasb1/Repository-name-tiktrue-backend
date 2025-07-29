"""
Tests for admin approval system for network joining
Tests approval workflow, security validation, and queue management
"""

import asyncio
import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any

from admin_approval_system import (
    AdminApprovalSystem,
    ApprovalStatus,
    ApprovalPriority,
    ApprovalRequest,
    ApprovalResponse,
    create_approval_system,
    auto_cleanup_service
)
from core.network_manager import NetworkInfo, NetworkType, NetworkStatus
from security.license_validator import SubscriptionTier, LicenseInfo

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestAdminApprovalSystem(unittest.TestCase):
    """Test admin approval system functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.admin_id = "admin_test_001"
        self.test_networks = self._create_test_networks()
        self.mock_license_enforcer = self._create_mock_license_enforcer()
        
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def _create_test_networks(self) -> Dict[str, NetworkInfo]:
        """Create test network configurations"""
        networks = {}
        
        # PRO tier network
        networks["net_pro"] = NetworkInfo(
            network_id="net_pro",
            network_name="PRO Test Network",
            model_id="llama-13b",
            network_type=NetworkType.PRIVATE,
            required_license_tier=SubscriptionTier.PRO,
            status=NetworkStatus.ACTIVE,
            admin_address="192.168.1.100",
            admin_port=8080,
            worker_count=4,
            max_clients=20,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        # FREE tier network
        networks["net_free"] = NetworkInfo(
            network_id="net_free",
            network_name="FREE Test Network",
            model_id="llama-7b",
            network_type=NetworkType.PUBLIC,
            required_license_tier=SubscriptionTier.FREE,
            status=NetworkStatus.ACTIVE,
            admin_address="192.168.1.101",
            admin_port=8080,
            worker_count=2,
            max_clients=10,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        return networks
    
    def _create_mock_license_enforcer(self):
        """Create mock license enforcer"""
        mock_enforcer = Mock()
        mock_license = LicenseInfo(
            license_key="TIKT-PRO-12M-TEST001",
            plan=SubscriptionTier.PRO,
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=20,
            allowed_models=["llama-7b", "llama-13b"],
            allowed_features=["chat", "inference"],
            status="active",
            hardware_signature="test_hw_sig"
        )
        mock_enforcer.current_license = mock_license
        mock_enforcer.get_license_status.return_value = {'valid': True}
        return mock_enforcer
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_approval_system_initialization(self, mock_get_enforcer):
        """Test approval system initialization"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Verify initialization
        self.assertEqual(approval_system.admin_node_id, self.admin_id)
        self.assertEqual(len(approval_system.managed_networks), 2)
        self.assertEqual(len(approval_system.pending_requests), 0)
        self.assertEqual(len(approval_system.processed_requests), 0)
        self.assertEqual(approval_system.stats['requests_received'], 0)
        self.assertIsNotNone(approval_system.security_key)
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_create_approval_request(self, mock_get_enforcer):
        """Test creating approval requests"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Create approval request
        requester_info = {
            'license_tier': 'PRO',
            'license_key': 'TIKT-PRO-12M-TEST001',
            'node_capabilities': ['inference', 'storage']
        }
        
        request = approval_system.create_approval_request(
            requester_node_id="requester_001",
            requester_address="192.168.1.200",
            network_id="net_pro",
            requester_info=requester_info,
            priority=ApprovalPriority.HIGH
        )
        
        # Verify request creation
        self.assertIsNotNone(request)
        self.assertEqual(request.requester_node_id, "requester_001")
        self.assertEqual(request.requester_address, "192.168.1.200")
        self.assertEqual(request.network_id, "net_pro")
        self.assertEqual(request.network_name, "PRO Test Network")
        self.assertEqual(request.license_tier, "PRO")
        self.assertEqual(request.status, ApprovalStatus.PENDING)
        self.assertEqual(request.priority, ApprovalPriority.HIGH)
        self.assertIsNotNone(request.security_token)
        self.assertIsNotNone(request.license_hash)
        
        # Verify system state
        self.assertEqual(len(approval_system.pending_requests), 1)
        self.assertEqual(approval_system.stats['requests_received'], 1)
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_create_request_invalid_network(self, mock_get_enforcer):
        """Test creating request for non-existent network"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        requester_info = {'license_tier': 'PRO'}
        
        # Should raise ValueError for invalid network
        with self.assertRaises(ValueError) as context:
            approval_system.create_approval_request(
                requester_node_id="requester_001",
                requester_address="192.168.1.200",
                network_id="invalid_network",
                requester_info=requester_info
            )
        
        self.assertIn("not managed by this admin", str(context.exception))
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_process_approval_request_approve(self, mock_get_enforcer):
        """Test processing approval request with approval"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Create request
        requester_info = {
            'license_tier': 'PRO',
            'license_key': 'TIKT-PRO-12M-TEST001'
        }
        
        request = approval_system.create_approval_request(
            requester_node_id="requester_001",
            requester_address="192.168.1.200",
            network_id="net_pro",
            requester_info=requester_info
        )
        
        # Process request with approval
        response = approval_system.process_approval_request(
            request.request_id,
            self.admin_id,
            approve=True,
            admin_notes="Approved for testing"
        )
        
        # Verify response
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(response.status, ApprovalStatus.APPROVED)
        self.assertEqual(response.admin_id, self.admin_id)
        self.assertEqual(response.admin_notes, "Approved for testing")
        self.assertIsNotNone(response.network_config)
        self.assertIsNotNone(response.security_token)
        
        # Verify network config
        config = response.network_config
        self.assertEqual(config['network_id'], "net_pro")
        self.assertEqual(config['network_name'], "PRO Test Network")
        self.assertEqual(config['model_id'], "llama-13b")
        self.assertIn('requester_permissions', config)
        
        # Verify system state
        self.assertEqual(len(approval_system.pending_requests), 0)
        self.assertEqual(len(approval_system.processed_requests), 1)
        self.assertEqual(approval_system.stats['requests_approved'], 1)
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_process_approval_request_reject(self, mock_get_enforcer):
        """Test processing approval request with rejection"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Create request
        requester_info = {'license_tier': 'FREE'}
        
        request = approval_system.create_approval_request(
            requester_node_id="requester_001",
            requester_address="192.168.1.200",
            network_id="net_free",
            requester_info=requester_info
        )
        
        # Process request with rejection
        response = approval_system.process_approval_request(
            request.request_id,
            self.admin_id,
            approve=False,
            admin_notes="Rejected for security reasons"
        )
        
        # Verify response
        self.assertEqual(response.status, ApprovalStatus.REJECTED)
        self.assertEqual(response.admin_notes, "Rejected for security reasons")
        self.assertIsNone(response.network_config)
        
        # Verify system state
        self.assertEqual(approval_system.stats['requests_rejected'], 1)
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_license_compatibility_validation(self, mock_get_enforcer):
        """Test license compatibility validation"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Test FREE license trying to access PRO network
        free_request = ApprovalRequest(
            request_id="test_req",
            requester_node_id="requester_001",
            requester_address="192.168.1.200",
            network_id="net_pro",
            network_name="PRO Test Network",
            license_tier="FREE",
            license_hash="test_hash",
            requested_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            status=ApprovalStatus.PENDING,
            priority=ApprovalPriority.NORMAL,
            requester_info={},
            security_token="test_token"
        )
        
        # Should fail compatibility check
        compatible = approval_system._validate_license_compatibility(free_request)
        self.assertFalse(compatible)
        
        # Test PRO license accessing PRO network
        pro_request = ApprovalRequest(
            request_id="test_req_2",
            requester_node_id="requester_002",
            requester_address="192.168.1.201",
            network_id="net_pro",
            network_name="PRO Test Network",
            license_tier="PRO",
            license_hash="test_hash_2",
            requested_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
            status=ApprovalStatus.PENDING,
            priority=ApprovalPriority.NORMAL,
            requester_info={},
            security_token="test_token_2"
        )
        
        # Should pass compatibility check
        compatible = approval_system._validate_license_compatibility(pro_request)
        self.assertTrue(compatible)
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_get_pending_requests_filtering(self, mock_get_enforcer):
        """Test getting pending requests with filtering"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Create multiple requests with different priorities and networks
        requests_data = [
            ("net_pro", ApprovalPriority.HIGH),
            ("net_pro", ApprovalPriority.NORMAL),
            ("net_free", ApprovalPriority.URGENT),
            ("net_free", ApprovalPriority.LOW)
        ]
        
        created_requests = []
        for network_id, priority in requests_data:
            request = approval_system.create_approval_request(
                requester_node_id=f"requester_{len(created_requests)}",
                requester_address=f"192.168.1.{200 + len(created_requests)}",
                network_id=network_id,
                requester_info={'license_tier': 'PRO'},
                priority=priority
            )
            created_requests.append(request)
        
        # Test getting all pending requests
        all_pending = approval_system.get_pending_requests()
        self.assertEqual(len(all_pending), 4)
        
        # Test filtering by network
        pro_requests = approval_system.get_pending_requests(network_id="net_pro")
        self.assertEqual(len(pro_requests), 2)
        
        free_requests = approval_system.get_pending_requests(network_id="net_free")
        self.assertEqual(len(free_requests), 2)
        
        # Test filtering by priority
        high_priority = approval_system.get_pending_requests(priority=ApprovalPriority.HIGH)
        self.assertEqual(len(high_priority), 1)
        
        urgent_priority = approval_system.get_pending_requests(priority=ApprovalPriority.URGENT)
        self.assertEqual(len(urgent_priority), 1)
        
        # Test priority sorting (URGENT should be first)
        self.assertEqual(all_pending[0].priority, ApprovalPriority.URGENT)
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_cancel_approval_request(self, mock_get_enforcer):
        """Test cancelling approval requests"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Create request
        request = approval_system.create_approval_request(
            requester_node_id="requester_001",
            requester_address="192.168.1.200",
            network_id="net_pro",
            requester_info={'license_tier': 'PRO'}
        )
        
        # Cancel request
        success = approval_system.cancel_approval_request(
            request.request_id,
            reason="User requested cancellation"
        )
        
        # Verify cancellation
        self.assertTrue(success)
        self.assertEqual(len(approval_system.pending_requests), 0)
        self.assertEqual(len(approval_system.processed_requests), 1)
        self.assertEqual(approval_system.stats['requests_cancelled'], 1)
        
        # Verify cancelled request
        cancelled_request = approval_system.processed_requests[request.request_id]
        self.assertEqual(cancelled_request.status, ApprovalStatus.CANCELLED)
        self.assertIn("User requested cancellation", cancelled_request.admin_notes)
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_cleanup_expired_requests(self, mock_get_enforcer):
        """Test cleanup of expired requests"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Create request with short expiry
        request = approval_system.create_approval_request(
            requester_node_id="requester_001",
            requester_address="192.168.1.200",
            network_id="net_pro",
            requester_info={'license_tier': 'PRO'},
            expiry_hours=0  # Expires immediately
        )
        
        # Manually set expiry to past
        approval_system.pending_requests[request.request_id].expires_at = datetime.now() - timedelta(hours=1)
        
        # Run cleanup
        cleaned = approval_system.cleanup_expired_requests()
        
        # Verify cleanup
        self.assertEqual(cleaned, 1)
        self.assertEqual(len(approval_system.pending_requests), 0)
        self.assertEqual(len(approval_system.processed_requests), 1)
        self.assertEqual(approval_system.stats['requests_expired'], 1)
        
        # Verify expired request
        expired_request = list(approval_system.processed_requests.values())[0]
        self.assertEqual(expired_request.status, ApprovalStatus.EXPIRED)
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_security_token_generation(self, mock_get_enforcer):
        """Test security token generation and validation"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Generate tokens for different requests
        token1 = approval_system._generate_security_token("node1", "net1")
        token2 = approval_system._generate_security_token("node2", "net1")
        token3 = approval_system._generate_security_token("node1", "net2")
        
        # Verify tokens are different
        self.assertNotEqual(token1, token2)
        self.assertNotEqual(token1, token3)
        self.assertNotEqual(token2, token3)
        
        # Verify token length
        self.assertEqual(len(token1), approval_system.SECURITY_TOKEN_LENGTH)
        self.assertEqual(len(token2), approval_system.SECURITY_TOKEN_LENGTH)
        self.assertEqual(len(token3), approval_system.SECURITY_TOKEN_LENGTH)
    
    @patch('admin_approval_system.get_license_enforcer')
    def test_approval_statistics(self, mock_get_enforcer):
        """Test approval system statistics"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Create and process multiple requests
        for i in range(3):
            request = approval_system.create_approval_request(
                requester_node_id=f"requester_{i}",
                requester_address=f"192.168.1.{200 + i}",
                network_id="net_pro",
                requester_info={'license_tier': 'PRO'}
            )
            
            # Approve 2, reject 1
            approve = i < 2
            approval_system.process_approval_request(
                request.request_id,
                self.admin_id,
                approve=approve,
                admin_notes=f"Test processing {i}"
            )
        
        # Get statistics
        stats = approval_system.get_approval_statistics()
        
        # Verify statistics
        self.assertEqual(stats['requests_received'], 3)
        self.assertEqual(stats['requests_approved'], 2)
        self.assertEqual(stats['requests_rejected'], 1)
        self.assertEqual(stats['pending_requests_count'], 0)
        self.assertEqual(stats['processed_requests_count'], 3)
        self.assertEqual(stats['managed_networks_count'], 2)
        self.assertAlmostEqual(stats['approval_rate'], 2/3, places=2)
    
    def test_utility_functions(self):
        """Test utility functions"""
        # Test create_approval_system function
        approval_system = create_approval_system("test_admin", self.test_networks)
        self.assertIsInstance(approval_system, AdminApprovalSystem)
        self.assertEqual(approval_system.admin_node_id, "test_admin")
        self.assertEqual(len(approval_system.managed_networks), 2)
    
    @patch('admin_approval_system.get_license_enforcer')
    async def test_auto_cleanup_service(self, mock_get_enforcer):
        """Test automatic cleanup service"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        approval_system = AdminApprovalSystem(self.admin_id, self.test_networks)
        
        # Create expired request
        request = approval_system.create_approval_request(
            requester_node_id="requester_001",
            requester_address="192.168.1.200",
            network_id="net_pro",
            requester_info={'license_tier': 'PRO'}
        )
        
        # Set expiry to past
        approval_system.pending_requests[request.request_id].expires_at = datetime.now() - timedelta(hours=1)
        
        # Mock cleanup method to track calls
        original_cleanup = approval_system.cleanup_expired_requests
        cleanup_calls = []
        
        def mock_cleanup():
            result = original_cleanup()
            cleanup_calls.append(result)
            return result
        
        approval_system.cleanup_expired_requests = mock_cleanup
        
        # Start cleanup service with short interval
        cleanup_task = asyncio.create_task(
            auto_cleanup_service(approval_system, interval=0.1)
        )
        
        # Wait for cleanup to run
        await asyncio.sleep(0.2)
        
        # Cancel cleanup service
        cleanup_task.cancel()
        
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        
        # Verify cleanup was called
        self.assertGreater(len(cleanup_calls), 0)
        self.assertEqual(cleanup_calls[0], 1)  # Should have cleaned 1 expired request


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)