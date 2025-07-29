"""
Unit Tests for Multi-Network Service Management

This module contains comprehensive unit tests for the multi-network service
management system, covering resource allocation, client assignment, network
creation/deletion, and dashboard functionality.

Test Categories:
- NetworkResourceManager tests
- ClientAssignmentManager tests  
- MultiNetworkService tests
- NetworkDashboard tests
- Integration tests
- Performance tests
"""

import unittest
import asyncio
import tempfile
import shutil
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

# Import modules to test
from multi_network_service import (
    NetworkResourceManager, ClientAssignmentManager, MultiNetworkService,
    NetworkDashboard, ResourceMetrics, NetworkResourceAllocation,
    ClientAssignment, NetworkStatistics, NetworkPriority, ResourceError,
    get_network_resource_recommendations
)
from core.network_manager import NetworkInfo, NetworkType, NetworkStatus
from license_models import SubscriptionTier


class TestNetworkResourceManager(unittest.TestCase):
    """Test cases for NetworkResourceManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.resource_manager = NetworkResourceManager(
            total_cpu_cores=8,
            total_memory_gb=16
        )
    
    def tearDown(self):
        """Clean up after tests"""
        self.resource_manager.stop_monitoring()
    
    def test_initialization(self):
        """Test resource manager initialization"""
        self.assertEqual(self.resource_manager.total_cpu_cores, 8)
        self.assertEqual(self.resource_manager.total_memory_gb, 16)
        self.assertEqual(len(self.resource_manager.network_allocations), 0)
        self.assertFalse(self.resource_manager.monitoring_active)
    
    def test_allocate_resources_basic(self):
        """Test basic resource allocation"""
        allocation = self.resource_manager.allocate_resources(
            network_id="test_network_1",
            model_id="llama3_1_8b_fp16",
            max_clients=5,
            priority=NetworkPriority.NORMAL
        )
        
        self.assertIsInstance(allocation, NetworkResourceAllocation)
        self.assertEqual(allocation.network_id, "test_network_1")
        self.assertGreater(allocation.cpu_limit_percent, 0)
        self.assertGreater(allocation.memory_limit_mb, 0)
        self.assertEqual(allocation.priority, NetworkPriority.NORMAL)
        
        # Check allocation is stored
        self.assertIn("test_network_1", self.resource_manager.network_allocations)
    
    def test_allocate_resources_different_models(self):
        """Test resource allocation for different models"""
        # Test Llama model
        llama_allocation = self.resource_manager.allocate_resources(
            network_id="llama_network",
            model_id="llama3_1_8b_fp16",
            max_clients=5
        )
        
        # Test Mistral model
        mistral_allocation = self.resource_manager.allocate_resources(
            network_id="mistral_network",
            model_id="mistral_7b_int4",
            max_clients=5
        )
        
        # Llama should require more resources than Mistral
        self.assertGreater(llama_allocation.cpu_limit_percent, mistral_allocation.cpu_limit_percent)
        self.assertGreater(llama_allocation.memory_limit_mb, mistral_allocation.memory_limit_mb)
    
    def test_allocate_resources_priority_scaling(self):
        """Test resource allocation with different priorities"""
        normal_allocation = self.resource_manager.allocate_resources(
            network_id="normal_network",
            model_id="llama3_1_8b_fp16",
            max_clients=5,
            priority=NetworkPriority.NORMAL
        )
        
        high_allocation = self.resource_manager.allocate_resources(
            network_id="high_network",
            model_id="llama3_1_8b_fp16",
            max_clients=5,
            priority=NetworkPriority.HIGH
        )
        
        # High priority should get more resources
        self.assertGreater(high_allocation.cpu_limit_percent, normal_allocation.cpu_limit_percent)
        self.assertGreater(high_allocation.memory_limit_mb, normal_allocation.memory_limit_mb)
    
    def test_deallocate_resources(self):
        """Test resource deallocation"""
        # Allocate resources
        self.resource_manager.allocate_resources(
            network_id="test_network",
            model_id="llama3_1_8b_fp16",
            max_clients=5
        )
        
        self.assertIn("test_network", self.resource_manager.network_allocations)
        
        # Deallocate resources
        success = self.resource_manager.deallocate_resources("test_network")
        
        self.assertTrue(success)
        self.assertNotIn("test_network", self.resource_manager.network_allocations)
    
    def test_deallocate_nonexistent_network(self):
        """Test deallocating resources for non-existent network"""
        success = self.resource_manager.deallocate_resources("nonexistent_network")
        self.assertFalse(success)
    
    def test_resource_overcommit_validation(self):
        """Test resource overcommit validation"""
        # Allocate resources that would exceed limits
        with self.assertRaises(ResourceError):
            for i in range(10):  # Try to create many high-resource networks
                self.resource_manager.allocate_resources(
                    network_id=f"network_{i}",
                    model_id="llama3_1_8b_fp16",
                    max_clients=20,
                    priority=NetworkPriority.HIGH
                )
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_get_resource_usage(self, mock_memory, mock_cpu):
        """Test getting resource usage"""
        # Mock system metrics
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(used=8 * 1024**3)  # 8GB used
        
        # Allocate resources
        self.resource_manager.allocate_resources(
            network_id="test_network",
            model_id="llama3_1_8b_fp16",
            max_clients=5
        )
        
        # Get resource usage
        usage = self.resource_manager.get_resource_usage("test_network")
        
        self.assertIsInstance(usage, ResourceMetrics)
        self.assertGreater(usage.cpu_usage_percent, 0)
        self.assertGreater(usage.memory_usage_mb, 0)
    
    def test_get_system_resource_summary(self):
        """Test getting system resource summary"""
        # Allocate some resources
        self.resource_manager.allocate_resources(
            network_id="test_network",
            model_id="llama3_1_8b_fp16",
            max_clients=5
        )
        
        summary = self.resource_manager.get_system_resource_summary()
        
        self.assertIn('system', summary)
        self.assertIn('allocation', summary)
        self.assertIn('timestamp', summary)
        
        system_info = summary['system']
        self.assertIn('cpu_cores', system_info)
        self.assertIn('memory_total_gb', system_info)
        
        allocation_info = summary['allocation']
        self.assertEqual(allocation_info['networks_count'], 1)
        self.assertGreater(allocation_info['total_allocated_cpu_percent'], 0)
    
    def test_monitoring_start_stop(self):
        """Test resource monitoring start/stop"""
        # Start monitoring
        success = self.resource_manager.start_monitoring()
        self.assertTrue(success)
        self.assertTrue(self.resource_manager.monitoring_active)
        
        # Try to start again (should return True but not start new thread)
        success = self.resource_manager.start_monitoring()
        self.assertTrue(success)
        
        # Stop monitoring
        self.resource_manager.stop_monitoring()
        self.assertFalse(self.resource_manager.monitoring_active)


class TestClientAssignmentManager(unittest.TestCase):
    """Test cases for ClientAssignmentManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.assignment_manager = ClientAssignmentManager()
        
        # Create mock network info
        self.mock_network_info = NetworkInfo(
            network_id="test_network",
            network_name="Test Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="admin_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="llama3_1_8b_fp16",
            model_name="Llama 3.1 8B",
            required_license_tier=SubscriptionTier.FREE,
            max_clients=10,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
    
    def test_assign_client_to_network(self):
        """Test client assignment to network"""
        success = self.assignment_manager.assign_client_to_network(
            client_id="client_1",
            network_id="test_network",
            network_info=self.mock_network_info
        )
        
        self.assertTrue(success)
        self.assertIn("client_1", self.assignment_manager.client_assignments)
        self.assertIn("test_network", self.assignment_manager.network_clients)
        self.assertIn("client_1", self.assignment_manager.network_clients["test_network"])
    
    def test_assign_client_network_at_capacity(self):
        """Test client assignment when network is at capacity"""
        # Fill network to capacity
        for i in range(self.mock_network_info.max_clients):
            self.assignment_manager.assign_client_to_network(
                client_id=f"client_{i}",
                network_id="test_network",
                network_info=self.mock_network_info
            )
        
        # Try to assign one more client
        success = self.assignment_manager.assign_client_to_network(
            client_id="client_overflow",
            network_id="test_network",
            network_info=self.mock_network_info
        )
        
        self.assertFalse(success)
        self.assertNotIn("client_overflow", self.assignment_manager.client_assignments)
    
    def test_reassign_client_to_different_network(self):
        """Test reassigning client to different network"""
        # Create second network
        network_2_info = NetworkInfo(
            network_id="test_network_2",
            network_name="Test Network 2",
            network_type=NetworkType.PUBLIC,
            admin_node_id="admin_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="mistral_7b_int4",
            model_name="Mistral 7B",
            required_license_tier=SubscriptionTier.FREE,
            max_clients=10,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        # Assign client to first network
        self.assignment_manager.assign_client_to_network(
            client_id="client_1",
            network_id="test_network",
            network_info=self.mock_network_info
        )
        
        # Reassign to second network
        success = self.assignment_manager.assign_client_to_network(
            client_id="client_1",
            network_id="test_network_2",
            network_info=network_2_info
        )
        
        self.assertTrue(success)
        
        # Check client is only in second network
        assignment = self.assignment_manager.get_client_assignment("client_1")
        self.assertEqual(assignment.network_id, "test_network_2")
        
        # Check client removed from first network
        self.assertNotIn("client_1", self.assignment_manager.network_clients.get("test_network", set()))
    
    def test_remove_client_assignment(self):
        """Test removing client assignment"""
        # Assign client
        self.assignment_manager.assign_client_to_network(
            client_id="client_1",
            network_id="test_network",
            network_info=self.mock_network_info
        )
        
        # Remove assignment
        success = self.assignment_manager.remove_client_assignment("client_1")
        
        self.assertTrue(success)
        self.assertNotIn("client_1", self.assignment_manager.client_assignments)
        self.assertNotIn("client_1", self.assignment_manager.network_clients.get("test_network", set()))
    
    def test_remove_nonexistent_client(self):
        """Test removing non-existent client assignment"""
        success = self.assignment_manager.remove_client_assignment("nonexistent_client")
        self.assertFalse(success)
    
    def test_get_network_clients(self):
        """Test getting clients for a network"""
        # Assign multiple clients
        for i in range(3):
            self.assignment_manager.assign_client_to_network(
                client_id=f"client_{i}",
                network_id="test_network",
                network_info=self.mock_network_info
            )
        
        clients = self.assignment_manager.get_network_clients("test_network")
        
        self.assertEqual(len(clients), 3)
        self.assertIsInstance(clients[0], ClientAssignment)
    
    def test_update_client_activity(self):
        """Test updating client activity"""
        # Assign client
        self.assignment_manager.assign_client_to_network(
            client_id="client_1",
            network_id="test_network",
            network_info=self.mock_network_info
        )
        
        # Update activity
        success = self.assignment_manager.update_client_activity("client_1")
        
        self.assertTrue(success)
        
        assignment = self.assignment_manager.get_client_assignment("client_1")
        self.assertEqual(assignment.status, "active")
    
    def test_get_assignment_statistics(self):
        """Test getting assignment statistics"""
        # Assign clients to different networks
        self.assignment_manager.assign_client_to_network(
            client_id="client_1",
            network_id="test_network",
            network_info=self.mock_network_info
        )
        
        stats = self.assignment_manager.get_assignment_statistics()
        
        self.assertIn('total_assignments', stats)
        self.assertIn('active_assignments', stats)
        self.assertIn('networks', stats)
        self.assertEqual(stats['total_assignments'], 1)
        self.assertEqual(stats['active_assignments'], 1)
    
    def test_assignment_callbacks(self):
        """Test assignment callbacks"""
        callback_calls = []
        
        def test_callback(client_id, network_id, action):
            callback_calls.append((client_id, network_id, action))
        
        # Add callback
        self.assignment_manager.add_assignment_callback(test_callback)
        
        # Assign client
        self.assignment_manager.assign_client_to_network(
            client_id="client_1",
            network_id="test_network",
            network_info=self.mock_network_info
        )
        
        # Remove client
        self.assignment_manager.remove_client_assignment("client_1")
        
        # Check callbacks were called
        self.assertEqual(len(callback_calls), 2)
        self.assertEqual(callback_calls[0], ("client_1", "test_network", "assigned"))
        self.assertEqual(callback_calls[1], ("client_1", "test_network", "removed"))
        
        # Remove callback
        self.assignment_manager.remove_assignment_callback(test_callback)


class TestMultiNetworkService(unittest.TestCase):
    """Test cases for MultiNetworkService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.service = MultiNetworkService(
            storage_dir=self.temp_dir,
            node_id="test_node"
        )
        
        # Mock license enforcer
        self.mock_license = Mock()
        self.mock_license.plan = SubscriptionTier.PRO
        self.mock_license.max_clients = 50
        
        with patch('multi_network_service.get_license_enforcer') as mock_get_enforcer:
            mock_enforcer = Mock()
            mock_enforcer.get_license_status.return_value = {'valid': True}
            mock_enforcer.current_license = self.mock_license
            mock_enforcer.check_model_access_allowed.return_value = True
            mock_get_enforcer.return_value = mock_enforcer
            
            self.service.license_enforcer = mock_enforcer
    
    def tearDown(self):
        """Clean up after tests"""
        asyncio.run(self.service.stop_service())
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test service initialization"""
        self.assertEqual(self.service.node_id, "test_node")
        self.assertEqual(str(self.service.storage_dir), self.temp_dir)
        self.assertFalse(self.service.service_running)
        self.assertEqual(len(self.service.active_networks), 0)
    
    async def test_start_stop_service(self):
        """Test starting and stopping service"""
        # Mock network manager methods
        self.service.network_manager.start_discovery_service = Mock(return_value=True)
        self.service.network_manager.stop_discovery_service = Mock()
        
        # Start service
        success = await self.service.start_service()
        self.assertTrue(success)
        self.assertTrue(self.service.service_running)
        
        # Stop service
        await self.service.stop_service()
        self.assertFalse(self.service.service_running)
    
    async def test_create_network(self):
        """Test network creation"""
        # Mock network manager create_network
        mock_network_info = NetworkInfo(
            network_id="test_network_123",
            network_name="Test Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="test_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="llama3_1_8b_fp16",
            model_name="Llama 3.1 8B",
            required_license_tier=SubscriptionTier.PRO,
            max_clients=10,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        self.service.network_manager.create_network = Mock(return_value=mock_network_info)
        
        # Create network
        network_info = await self.service.create_network(
            network_name="Test Network",
            model_id="llama3_1_8b_fp16",
            network_type=NetworkType.PUBLIC,
            max_clients=10,
            description="Test network"
        )
        
        self.assertIsNotNone(network_info)
        self.assertEqual(network_info.network_name, "Test Network")
        self.assertIn(network_info.network_id, self.service.active_networks)
        self.assertIn(network_info.network_id, self.service.network_statistics)
    
    async def test_create_network_license_limit(self):
        """Test network creation with license limits"""
        # Set license to FREE (limit 1 network)
        self.mock_license.plan = SubscriptionTier.FREE
        
        # Mock successful network creation
        mock_network_info = NetworkInfo(
            network_id="test_network_1",
            network_name="Test Network 1",
            network_type=NetworkType.PUBLIC,
            admin_node_id="test_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="llama3_1_8b_fp16",
            model_name="Llama 3.1 8B",
            required_license_tier=SubscriptionTier.FREE,
            max_clients=10,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        self.service.network_manager.create_network = Mock(return_value=mock_network_info)
        
        # Create first network (should succeed)
        network_1 = await self.service.create_network(
            network_name="Test Network 1",
            model_id="llama3_1_8b_fp16"
        )
        self.assertIsNotNone(network_1)
        
        # Try to create second network (should fail due to license limit)
        network_2 = await self.service.create_network(
            network_name="Test Network 2",
            model_id="llama3_1_8b_fp16"
        )
        self.assertIsNone(network_2)
    
    async def test_delete_network(self):
        """Test network deletion"""
        # Create network first
        mock_network_info = NetworkInfo(
            network_id="test_network_123",
            network_name="Test Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="test_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="llama3_1_8b_fp16",
            model_name="Llama 3.1 8B",
            required_license_tier=SubscriptionTier.PRO,
            max_clients=10,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        self.service.network_manager.create_network = Mock(return_value=mock_network_info)
        
        network_info = await self.service.create_network(
            network_name="Test Network",
            model_id="llama3_1_8b_fp16"
        )
        
        network_id = network_info.network_id
        
        # Delete network
        success = await self.service.delete_network(network_id)
        
        self.assertTrue(success)
        self.assertNotIn(network_id, self.service.active_networks)
        self.assertNotIn(network_id, self.service.network_statistics)
    
    def test_get_network_list(self):
        """Test getting network list"""
        # Add mock network to active networks
        mock_network_info = NetworkInfo(
            network_id="test_network_123",
            network_name="Test Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="test_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="llama3_1_8b_fp16",
            model_name="Llama 3.1 8B",
            required_license_tier=SubscriptionTier.PRO,
            max_clients=10,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        self.service.active_networks["test_network_123"] = mock_network_info
        
        networks = self.service.get_network_list()
        
        self.assertEqual(len(networks), 1)
        self.assertEqual(networks[0]['network_id'], "test_network_123")
        self.assertEqual(networks[0]['network_name'], "Test Network")
    
    def test_get_network_details(self):
        """Test getting network details"""
        # Add mock network
        mock_network_info = NetworkInfo(
            network_id="test_network_123",
            network_name="Test Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="test_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="llama3_1_8b_fp16",
            model_name="Llama 3.1 8B",
            required_license_tier=SubscriptionTier.PRO,
            max_clients=10,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        self.service.active_networks["test_network_123"] = mock_network_info
        
        details = self.service.get_network_details("test_network_123")
        
        self.assertIsNotNone(details)
        self.assertIn('network_info', details)
        self.assertIn('clients', details)
        self.assertIn('timestamp', details)
    
    async def test_assign_client_to_network(self):
        """Test client assignment to network"""
        # Add mock network
        mock_network_info = NetworkInfo(
            network_id="test_network_123",
            network_name="Test Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="test_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="llama3_1_8b_fp16",
            model_name="Llama 3.1 8B",
            required_license_tier=SubscriptionTier.PRO,
            max_clients=10,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        self.service.active_networks["test_network_123"] = mock_network_info
        
        # Assign client
        success = await self.service.assign_client_to_network(
            client_id="client_1",
            network_id="test_network_123"
        )
        
        self.assertTrue(success)
        
        # Check assignment
        assignment = self.service.client_assignment_manager.get_client_assignment("client_1")
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.network_id, "test_network_123")
    
    def test_get_service_statistics(self):
        """Test getting service statistics"""
        stats = self.service.get_service_statistics()
        
        self.assertIn('service', stats)
        self.assertIn('system_resources', stats)
        self.assertIn('assignment_statistics', stats)
        self.assertIn('network_statistics', stats)
        self.assertIn('timestamp', stats)
        
        service_info = stats['service']
        self.assertEqual(service_info['node_id'], "test_node")
        self.assertIn('service_running', service_info)
    
    def test_network_callbacks(self):
        """Test network event callbacks"""
        callback_calls = []
        
        def test_callback(network_id, action):
            callback_calls.append((network_id, action))
        
        # Add callback
        self.service.add_network_callback(test_callback)
        
        # Simulate network creation
        for callback in self.service.network_callbacks:
            callback("test_network", "created")
        
        # Check callback was called
        self.assertEqual(len(callback_calls), 1)
        self.assertEqual(callback_calls[0], ("test_network", "created"))
        
        # Remove callback
        self.service.remove_network_callback(test_callback)


class TestNetworkDashboard(unittest.TestCase):
    """Test cases for NetworkDashboard"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.service = MultiNetworkService(
            storage_dir=self.temp_dir,
            node_id="test_node"
        )
        self.dashboard = NetworkDashboard(self.service)
    
    def tearDown(self):
        """Clean up after tests"""
        self.dashboard.stop_dashboard()
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test dashboard initialization"""
        self.assertEqual(self.dashboard.multi_network_service, self.service)
        self.assertFalse(self.dashboard.dashboard_active)
        self.assertEqual(len(self.dashboard.dashboard_callbacks), 0)
    
    def test_start_stop_dashboard(self):
        """Test starting and stopping dashboard"""
        # Start dashboard
        success = self.dashboard.start_dashboard()
        self.assertTrue(success)
        self.assertTrue(self.dashboard.dashboard_active)
        
        # Try to start again (should return True)
        success = self.dashboard.start_dashboard()
        self.assertTrue(success)
        
        # Stop dashboard
        self.dashboard.stop_dashboard()
        self.assertFalse(self.dashboard.dashboard_active)
    
    def test_get_dashboard_data(self):
        """Test getting dashboard data"""
        data = self.dashboard.get_dashboard_data()
        
        self.assertIn('overview', data)
        self.assertIn('networks', data)
        self.assertIn('service_statistics', data)
        self.assertIn('timestamp', data)
        
        overview = data['overview']
        self.assertIn('total_networks', overview)
        self.assertIn('system_health', overview)
    
    def test_get_network_performance_metrics(self):
        """Test getting network performance metrics"""
        # Add mock network with resource history
        mock_network_info = NetworkInfo(
            network_id="test_network",
            network_name="Test Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="test_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="llama3_1_8b_fp16",
            model_name="Llama 3.1 8B",
            required_license_tier=SubscriptionTier.PRO,
            max_clients=10,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        self.service.active_networks["test_network"] = mock_network_info
        
        # Add mock resource history
        resource_metrics = ResourceMetrics(
            cpu_usage_percent=50.0,
            memory_usage_mb=4096.0,
            gpu_usage_percent=30.0,
            gpu_memory_mb=2048.0,
            network_bandwidth_mbps=100.0,
            storage_usage_mb=1024.0,
            timestamp=datetime.now()
        )
        
        self.service.resource_manager.resource_history["test_network"] = [resource_metrics]
        
        metrics = self.dashboard.get_network_performance_metrics("test_network", 60)
        
        self.assertIn('network_id', metrics)
        self.assertIn('metrics', metrics)
        self.assertIn('summary', metrics)
        self.assertEqual(metrics['network_id'], "test_network")
    
    def test_dashboard_callbacks(self):
        """Test dashboard callbacks"""
        callback_calls = []
        
        def test_callback(data):
            callback_calls.append(data)
        
        # Add callback
        self.dashboard.add_dashboard_callback(test_callback)
        
        # Simulate dashboard update
        test_data = {'test': 'data'}
        for callback in self.dashboard.dashboard_callbacks:
            callback(test_data)
        
        # Check callback was called
        self.assertEqual(len(callback_calls), 1)
        self.assertEqual(callback_calls[0], test_data)
        
        # Remove callback
        self.dashboard.remove_dashboard_callback(test_callback)


class TestUtilityFunctions(unittest.TestCase):
    """Test cases for utility functions"""
    
    def test_get_network_resource_recommendations(self):
        """Test network resource recommendations"""
        # Test Llama model
        llama_recs = get_network_resource_recommendations("llama3_1_8b_fp16", 5)
        
        self.assertIn('cpu_percent', llama_recs)
        self.assertIn('memory_gb', llama_recs)
        self.assertIn('gpu_percent', llama_recs)
        self.assertIn('bandwidth_mbps', llama_recs)
        self.assertEqual(llama_recs['model_id'], "llama3_1_8b_fp16")
        self.assertEqual(llama_recs['expected_clients'], 5)
        
        # Test Mistral model
        mistral_recs = get_network_resource_recommendations("mistral_7b_int4", 5)
        
        # Mistral should require fewer resources than Llama
        self.assertLess(mistral_recs['cpu_percent'], llama_recs['cpu_percent'])
        self.assertLess(mistral_recs['memory_gb'], llama_recs['memory_gb'])
        
        # Test unknown model (should use defaults)
        unknown_recs = get_network_resource_recommendations("unknown_model", 5)
        self.assertIn('cpu_percent', unknown_recs)
        self.assertEqual(unknown_recs['model_id'], "unknown_model")


class TestIntegration(unittest.TestCase):
    """Integration tests for multi-network service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.service = MultiNetworkService(
            storage_dir=self.temp_dir,
            node_id="integration_test_node"
        )
        
        # Mock license enforcer
        self.mock_license = Mock()
        self.mock_license.plan = SubscriptionTier.ENT  # Enterprise for unlimited networks
        self.mock_license.max_clients = -1  # Unlimited clients
        
        with patch('multi_network_service.get_license_enforcer') as mock_get_enforcer:
            mock_enforcer = Mock()
            mock_enforcer.get_license_status.return_value = {'valid': True}
            mock_enforcer.current_license = self.mock_license
            mock_enforcer.check_model_access_allowed.return_value = True
            mock_get_enforcer.return_value = mock_enforcer
            
            self.service.license_enforcer = mock_enforcer
    
    def tearDown(self):
        """Clean up after tests"""
        asyncio.run(self.service.stop_service())
        shutil.rmtree(self.temp_dir)
    
    async def test_full_network_lifecycle(self):
        """Test complete network lifecycle"""
        # Mock network manager
        self.service.network_manager.start_discovery_service = Mock(return_value=True)
        self.service.network_manager.stop_discovery_service = Mock()
        
        mock_network_info = NetworkInfo(
            network_id="integration_test_network",
            network_name="Integration Test Network",
            network_type=NetworkType.PUBLIC,
            admin_node_id="integration_test_node",
            admin_host="localhost",
            admin_port=8080,
            model_id="llama3_1_8b_fp16",
            model_name="Llama 3.1 8B",
            required_license_tier=SubscriptionTier.ENT,
            max_clients=20,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        self.service.network_manager.create_network = Mock(return_value=mock_network_info)
        
        # 1. Start service
        success = await self.service.start_service()
        self.assertTrue(success)
        
        # 2. Create network
        network_info = await self.service.create_network(
            network_name="Integration Test Network",
            model_id="llama3_1_8b_fp16",
            max_clients=20
        )
        self.assertIsNotNone(network_info)
        
        # 3. Assign clients to network
        for i in range(5):
            success = await self.service.assign_client_to_network(
                client_id=f"client_{i}",
                network_id=network_info.network_id
            )
            self.assertTrue(success)
        
        # 4. Check network status
        networks = self.service.get_network_list()
        self.assertEqual(len(networks), 1)
        self.assertEqual(networks[0]['current_clients'], 5)
        
        # 5. Get service statistics
        stats = self.service.get_service_statistics()
        self.assertEqual(stats['service']['active_networks'], 1)
        self.assertEqual(stats['service']['total_clients'], 5)
        
        # 6. Delete network
        success = await self.service.delete_network(network_info.network_id)
        self.assertTrue(success)
        
        # 7. Verify cleanup
        networks = self.service.get_network_list()
        self.assertEqual(len(networks), 0)
        
        # 8. Stop service
        await self.service.stop_service()
        self.assertFalse(self.service.service_running)
    
    async def test_multiple_networks_resource_allocation(self):
        """Test resource allocation across multiple networks"""
        # Mock network manager
        self.service.network_manager.start_discovery_service = Mock(return_value=True)
        self.service.network_manager.create_network = Mock()
        
        # Create multiple networks with different models and priorities
        network_configs = [
            ("Network 1", "llama3_1_8b_fp16", NetworkPriority.HIGH),
            ("Network 2", "mistral_7b_int4", NetworkPriority.NORMAL),
            ("Network 3", "llama3_1_8b_fp16", NetworkPriority.LOW)
        ]
        
        created_networks = []
        
        for i, (name, model, priority) in enumerate(network_configs):
            mock_network_info = NetworkInfo(
                network_id=f"test_network_{i}",
                network_name=name,
                network_type=NetworkType.PUBLIC,
                admin_node_id="integration_test_node",
                admin_host="localhost",
                admin_port=8080,
                model_id=model,
                model_name=model,
                required_license_tier=SubscriptionTier.ENT,
                max_clients=10,
                current_clients=0,
                status=NetworkStatus.ACTIVE,
                created_at=datetime.now(),
                last_seen=datetime.now()
            )
            
            self.service.network_manager.create_network.return_value = mock_network_info
            
            network_info = await self.service.create_network(
                network_name=name,
                model_id=model,
                priority=priority,
                max_clients=10
            )
            
            self.assertIsNotNone(network_info)
            created_networks.append(network_info)
        
        # Check resource allocations
        resource_summary = self.service.resource_manager.get_system_resource_summary()
        self.assertEqual(resource_summary['allocation']['networks_count'], 3)
        
        # High priority network should have more resources than low priority
        high_priority_alloc = self.service.resource_manager.network_allocations[created_networks[0].network_id]
        low_priority_alloc = self.service.resource_manager.network_allocations[created_networks[2].network_id]
        
        self.assertGreater(high_priority_alloc.cpu_limit_percent, low_priority_alloc.cpu_limit_percent)
        self.assertGreater(high_priority_alloc.memory_limit_mb, low_priority_alloc.memory_limit_mb)


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(level=logging.WARNING)
    
    # Run tests
    unittest.main(verbosity=2)