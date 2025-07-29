"""
Tests for Dynamic Resource Allocation System
Tests resource allocation, conflict resolution, and integration with service runner
"""

import asyncio
import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from resource_allocator import (
    DynamicResourceAllocator, ResourceQuota, ResourceRequest, ResourceAllocation,
    AllocationPriority, NetworkResourceProfile, ResourceConflictResolver,
    create_default_resource_quota, create_network_profile
)
from security.license_validator import LicenseInfo, SubscriptionTier
from api_client import NetworkConfig


class TestResourceQuota(unittest.TestCase):
    """Test ResourceQuota functionality"""
    
    def test_resource_quota_creation(self):
        """Test resource quota creation"""
        quota = ResourceQuota(
            cpu_cores=4.0,
            memory_gb=8.0,
            gpu_memory_gb=4.0,
            network_bandwidth_mbps=1000.0,
            worker_slots=5,
            client_connections=10
        )
        
        self.assertEqual(quota.cpu_cores, 4.0)
        self.assertEqual(quota.memory_gb, 8.0)
        self.assertEqual(quota.gpu_memory_gb, 4.0)
        self.assertEqual(quota.network_bandwidth_mbps, 1000.0)
        self.assertEqual(quota.worker_slots, 5)
        self.assertEqual(quota.client_connections, 10)
        
        print("✓ Resource quota creation")
    
    def test_resource_quota_arithmetic(self):
        """Test resource quota arithmetic operations"""
        quota1 = ResourceQuota(cpu_cores=2.0, memory_gb=4.0, worker_slots=2)
        quota2 = ResourceQuota(cpu_cores=1.0, memory_gb=2.0, worker_slots=1)
        
        # Addition
        sum_quota = quota1 + quota2
        self.assertEqual(sum_quota.cpu_cores, 3.0)
        self.assertEqual(sum_quota.memory_gb, 6.0)
        self.assertEqual(sum_quota.worker_slots, 3)
        
        # Subtraction
        diff_quota = quota1 - quota2
        self.assertEqual(diff_quota.cpu_cores, 1.0)
        self.assertEqual(diff_quota.memory_gb, 2.0)
        self.assertEqual(diff_quota.worker_slots, 1)
        
        # Subtraction with negative result (should clamp to 0)
        diff_quota2 = quota2 - quota1
        self.assertEqual(diff_quota2.cpu_cores, 0.0)
        self.assertEqual(diff_quota2.memory_gb, 0.0)
        self.assertEqual(diff_quota2.worker_slots, 0)
        
        print("✓ Resource quota arithmetic")
    
    def test_resource_quota_can_satisfy(self):
        """Test resource quota satisfaction check"""
        available = ResourceQuota(cpu_cores=4.0, memory_gb=8.0, worker_slots=5)
        
        # Can satisfy smaller request
        small_request = ResourceQuota(cpu_cores=2.0, memory_gb=4.0, worker_slots=2)
        self.assertTrue(available.can_satisfy(small_request))
        
        # Cannot satisfy larger request
        large_request = ResourceQuota(cpu_cores=8.0, memory_gb=16.0, worker_slots=10)
        self.assertFalse(available.can_satisfy(large_request))
        
        # Can satisfy exact request
        exact_request = ResourceQuota(cpu_cores=4.0, memory_gb=8.0, worker_slots=5)
        self.assertTrue(available.can_satisfy(exact_request))
        
        print("✓ Resource quota satisfaction check")


class TestResourceRequest(unittest.TestCase):
    """Test ResourceRequest functionality"""
    
    def test_resource_request_creation(self):
        """Test resource request creation"""
        quota = ResourceQuota(cpu_cores=2.0, memory_gb=4.0, worker_slots=2)
        request = ResourceRequest(
            request_id="test_req_1",
            network_id="test_network",
            required_resources=quota,
            priority=AllocationPriority.HIGH,
            requested_at=datetime.now(),
            timeout_seconds=300.0
        )
        
        self.assertEqual(request.request_id, "test_req_1")
        self.assertEqual(request.network_id, "test_network")
        self.assertEqual(request.priority, AllocationPriority.HIGH)
        self.assertFalse(request.is_expired())
        
        print("✓ Resource request creation")
    
    def test_resource_request_expiry(self):
        """Test resource request expiry"""
        quota = ResourceQuota(cpu_cores=1.0, memory_gb=2.0, worker_slots=1)
        
        # Create expired request
        expired_request = ResourceRequest(
            request_id="expired_req",
            network_id="test_network",
            required_resources=quota,
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now() - timedelta(seconds=400),
            timeout_seconds=300.0
        )
        
        self.assertTrue(expired_request.is_expired())
        
        # Create non-expired request
        fresh_request = ResourceRequest(
            request_id="fresh_req",
            network_id="test_network",
            required_resources=quota,
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now(),
            timeout_seconds=300.0
        )
        
        self.assertFalse(fresh_request.is_expired())
        
        print("✓ Resource request expiry")


class TestResourceConflictResolver(unittest.TestCase):
    """Test ResourceConflictResolver functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.resolver = ResourceConflictResolver()
        self.available_resources = ResourceQuota(
            cpu_cores=4.0,
            memory_gb=8.0,
            worker_slots=4,
            client_connections=10
        )
    
    def test_priority_based_resolution(self):
        """Test priority-based conflict resolution"""
        # Create requests with different priorities
        high_priority_req = ResourceRequest(
            request_id="high_req",
            network_id="network_high",
            required_resources=ResourceQuota(cpu_cores=2.0, memory_gb=4.0, worker_slots=2),
            priority=AllocationPriority.HIGH,
            requested_at=datetime.now()
        )
        
        low_priority_req = ResourceRequest(
            request_id="low_req",
            network_id="network_low",
            required_resources=ResourceQuota(cpu_cores=3.0, memory_gb=6.0, worker_slots=3),
            priority=AllocationPriority.LOW,
            requested_at=datetime.now()
        )
        
        requests = [low_priority_req, high_priority_req]  # Intentionally out of order
        
        satisfied = self.resolver.resolve_conflict(requests, self.available_resources, "priority_based")
        
        # High priority should be satisfied first
        self.assertEqual(len(satisfied), 1)
        self.assertEqual(satisfied[0].request_id, "high_req")
        
        print("✓ Priority-based conflict resolution")
    
    def test_fair_share_resolution(self):
        """Test fair share conflict resolution"""
        # Create requests that can be satisfied with fair share
        req1 = ResourceRequest(
            request_id="req1",
            network_id="network1",
            required_resources=ResourceQuota(cpu_cores=1.0, memory_gb=2.0, worker_slots=1),
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now()
        )
        
        req2 = ResourceRequest(
            request_id="req2",
            network_id="network2",
            required_resources=ResourceQuota(cpu_cores=1.0, memory_gb=2.0, worker_slots=1),
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now()
        )
        
        requests = [req1, req2]
        
        satisfied = self.resolver.resolve_conflict(requests, self.available_resources, "fair_share")
        
        # Both should be satisfied with fair share
        self.assertEqual(len(satisfied), 2)
        
        print("✓ Fair share conflict resolution")


class TestDynamicResourceAllocator(unittest.TestCase):
    """Test DynamicResourceAllocator functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.total_resources = ResourceQuota(
            cpu_cores=8.0,
            memory_gb=16.0,
            gpu_memory_gb=8.0,
            network_bandwidth_mbps=1000.0,
            worker_slots=10,
            client_connections=20
        )
        
        self.license_info = LicenseInfo(
            license_key="TIKT-PRO-1Y-TEST123",
            plan=SubscriptionTier.PRO,
            expires_at=datetime.now() + timedelta(days=365),
            max_networks=5,
            max_clients=20
        )
        
        self.allocator = DynamicResourceAllocator(
            total_resources=self.total_resources,
            license_info=self.license_info,
            allocation_interval=1.0,  # Fast for testing
            cleanup_interval=5.0
        )
    
    def test_allocator_initialization(self):
        """Test allocator initialization"""
        self.assertEqual(self.allocator.total_resources, self.total_resources)
        self.assertEqual(self.allocator.license_info, self.license_info)
        self.assertEqual(len(self.allocator.pending_requests), 0)
        self.assertEqual(len(self.allocator.active_allocations), 0)
        
        print("✓ Allocator initialization")
    
    def test_resource_request_validation(self):
        """Test resource request validation"""
        # Valid request
        valid_quota = ResourceQuota(cpu_cores=2.0, memory_gb=4.0, worker_slots=5)
        valid_request = ResourceRequest(
            request_id="valid_req",
            network_id="test_network",
            required_resources=valid_quota,
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now()
        )
        
        self.assertTrue(self.allocator._validate_request(valid_request))
        
        # Invalid request (exceeds total resources)
        invalid_quota = ResourceQuota(cpu_cores=16.0, memory_gb=32.0, worker_slots=20)
        invalid_request = ResourceRequest(
            request_id="invalid_req",
            network_id="test_network",
            required_resources=invalid_quota,
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now()
        )
        
        self.assertFalse(self.allocator._validate_request(invalid_request))
        
        print("✓ Resource request validation")
    
    def test_resource_request_and_allocation(self):
        """Test resource request and allocation process"""
        # Create valid request
        quota = ResourceQuota(cpu_cores=2.0, memory_gb=4.0, worker_slots=2)
        request = ResourceRequest(
            request_id="test_req",
            network_id="test_network",
            required_resources=quota,
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now()
        )
        
        # Request resources
        request_id = self.allocator.request_resources(request)
        self.assertEqual(request_id, "test_req")
        self.assertEqual(len(self.allocator.pending_requests), 1)
        
        # Process pending requests
        asyncio.run(self.allocator._process_pending_requests())
        
        # Check allocation was created
        self.assertEqual(len(self.allocator.pending_requests), 0)
        self.assertEqual(len(self.allocator.active_allocations), 1)
        
        # Check resource tracking
        expected_allocated = quota
        self.assertEqual(self.allocator.allocated_resources.cpu_cores, expected_allocated.cpu_cores)
        self.assertEqual(self.allocator.allocated_resources.memory_gb, expected_allocated.memory_gb)
        
        print("✓ Resource request and allocation")
    
    def test_resource_release(self):
        """Test resource release"""
        # First allocate resources
        quota = ResourceQuota(cpu_cores=2.0, memory_gb=4.0, worker_slots=2)
        request = ResourceRequest(
            request_id="test_req",
            network_id="test_network",
            required_resources=quota,
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now()
        )
        
        self.allocator.request_resources(request)
        asyncio.run(self.allocator._process_pending_requests())
        
        # Get allocation ID
        allocations = list(self.allocator.active_allocations.keys())
        self.assertEqual(len(allocations), 1)
        allocation_id = allocations[0]
        
        # Release resources
        success = self.allocator.release_resources(allocation_id)
        self.assertTrue(success)
        
        # Check resources were returned
        self.assertEqual(len(self.allocator.active_allocations), 0)
        self.assertEqual(self.allocator.allocated_resources.cpu_cores, 0.0)
        self.assertEqual(self.allocator.allocated_resources.memory_gb, 0.0)
        
        print("✓ Resource release")
    
    def test_resource_utilization_reporting(self):
        """Test resource utilization reporting"""
        # Allocate some resources
        quota = ResourceQuota(cpu_cores=4.0, memory_gb=8.0, worker_slots=5)
        request = ResourceRequest(
            request_id="test_req",
            network_id="test_network",
            required_resources=quota,
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now()
        )
        
        self.allocator.request_resources(request)
        asyncio.run(self.allocator._process_pending_requests())
        
        # Get utilization
        utilization = self.allocator.get_resource_utilization()
        
        # Check utilization data
        self.assertIn("resources", utilization)
        self.assertIn("cpu_cores", utilization["resources"])
        
        cpu_util = utilization["resources"]["cpu_cores"]
        self.assertEqual(cpu_util["total"], 8.0)
        self.assertEqual(cpu_util["allocated"], 4.0)
        self.assertEqual(cpu_util["available"], 4.0)
        self.assertEqual(cpu_util["utilization_percent"], 50.0)
        
        print("✓ Resource utilization reporting")


class TestNetworkResourceProfile(unittest.TestCase):
    """Test NetworkResourceProfile functionality"""
    
    def test_network_profile_creation(self):
        """Test network resource profile creation"""
        base_quota = ResourceQuota(cpu_cores=1.0, memory_gb=2.0, worker_slots=1)
        peak_quota = ResourceQuota(cpu_cores=4.0, memory_gb=8.0, worker_slots=4)
        
        profile = NetworkResourceProfile(
            network_id="test_network",
            base_requirements=base_quota,
            peak_requirements=peak_quota,
            current_usage=ResourceQuota(),
            priority=AllocationPriority.NORMAL
        )
        
        self.assertEqual(profile.network_id, "test_network")
        self.assertEqual(profile.base_requirements, base_quota)
        self.assertEqual(profile.peak_requirements, peak_quota)
        self.assertEqual(profile.priority, AllocationPriority.NORMAL)
        
        print("✓ Network profile creation")
    
    def test_dynamic_requirements_calculation(self):
        """Test dynamic requirements calculation"""
        base_quota = ResourceQuota(cpu_cores=1.0, memory_gb=2.0, worker_slots=1)
        peak_quota = ResourceQuota(cpu_cores=4.0, memory_gb=8.0, worker_slots=4)
        
        profile = NetworkResourceProfile(
            network_id="test_network",
            base_requirements=base_quota,
            peak_requirements=peak_quota,
            current_usage=ResourceQuota(),
            priority=AllocationPriority.NORMAL
        )
        
        # Test with 0% load (should return base requirements)
        dynamic_0 = profile.get_dynamic_requirements(0.0)
        self.assertEqual(dynamic_0.cpu_cores, 1.0)
        self.assertEqual(dynamic_0.memory_gb, 2.0)
        self.assertEqual(dynamic_0.worker_slots, 1)
        
        # Test with 100% load (should return peak requirements)
        dynamic_100 = profile.get_dynamic_requirements(1.0)
        self.assertEqual(dynamic_100.cpu_cores, 4.0)
        self.assertEqual(dynamic_100.memory_gb, 8.0)
        self.assertEqual(dynamic_100.worker_slots, 4)
        
        # Test with 50% load (should return middle)
        dynamic_50 = profile.get_dynamic_requirements(0.5)
        self.assertEqual(dynamic_50.cpu_cores, 2.5)
        self.assertEqual(dynamic_50.memory_gb, 5.0)
        self.assertEqual(dynamic_50.worker_slots, 2)  # Rounded down for int
        
        print("✓ Dynamic requirements calculation")


class TestLicenseIntegration(unittest.TestCase):
    """Test license integration with resource allocation"""
    
    def test_default_quota_creation(self):
        """Test default quota creation based on license"""
        # Free tier
        free_license = LicenseInfo(
            license_key="TIKT-FREE-1Y-TEST123",
            plan=SubscriptionTier.FREE,
            expires_at=datetime.now() + timedelta(days=365),
            max_networks=1,
            max_clients=3
        )
        
        free_quota = create_default_resource_quota(free_license)
        self.assertEqual(free_quota.worker_slots, 2)
        self.assertEqual(free_quota.client_connections, 3)
        
        # Pro tier
        pro_license = LicenseInfo(
            license_key="TIKT-PRO-1Y-TEST123",
            plan=SubscriptionTier.PRO,
            expires_at=datetime.now() + timedelta(days=365),
            max_networks=5,
            max_clients=20
        )
        
        pro_quota = create_default_resource_quota(pro_license)
        self.assertEqual(pro_quota.worker_slots, 10)
        self.assertEqual(pro_quota.client_connections, 20)
        
        # Enterprise tier
        ent_license = LicenseInfo(
            license_key="TIKT-ENT-1Y-TEST123",
            plan=SubscriptionTier.ENT,
            expires_at=datetime.now() + timedelta(days=365),
            max_networks=50,
            max_clients=100
        )
        
        ent_quota = create_default_resource_quota(ent_license)
        self.assertEqual(ent_quota.worker_slots, 50)
        self.assertEqual(ent_quota.client_connections, 100)
        
        print("✓ Default quota creation based on license")
    
    def test_network_profile_creation_with_license(self):
        """Test network profile creation with license constraints"""
        # Create network config
        network_config = NetworkConfig(
            network_id="test_network",
            model_id="llama-7b",
            host="localhost",
            port=8701,
            model_chain_order=["block1", "block2"],
            paths={"model_dir": "/path/to/model"},
            nodes={"node1": {"host": "localhost", "port": 8801}}
        )
        
        # Test with Pro license
        pro_license = LicenseInfo(
            license_key="TIKT-PRO-1Y-TEST123",
            plan=SubscriptionTier.PRO,
            expires_at=datetime.now() + timedelta(days=365),
            max_networks=5,
            max_clients=20
        )
        
        profile = create_network_profile(network_config, pro_license)
        
        self.assertEqual(profile.network_id, "test_network")
        self.assertEqual(profile.priority, AllocationPriority.NORMAL)
        self.assertLessEqual(profile.peak_requirements.worker_slots, 10)  # Pro limit
        self.assertLessEqual(profile.peak_requirements.client_connections, 20)  # Pro limit
        
        print("✓ Network profile creation with license constraints")


class TestResourceAllocationIntegration(unittest.TestCase):
    """Test integration with service runner"""
    
    @patch('resource_allocator.DynamicResourceAllocator')
    def test_service_runner_integration(self, mock_allocator_class):
        """Test integration with service runner"""
        # Mock allocator
        mock_allocator = Mock()
        mock_allocator_class.return_value = mock_allocator
        
        # Mock successful allocation
        mock_allocator.request_resources.return_value = "test_request_id"
        mock_allocator.get_network_allocations.return_value = [
            Mock(allocation_id="test_allocation_id")
        ]
        
        # Test would require full service runner integration
        # This is a placeholder for integration testing
        
        print("✓ Service runner integration (mocked)")


async def run_async_tests():
    """Run async integration tests"""
    print("\n" + "="*50)
    print("ASYNC INTEGRATION TESTS")
    print("="*50)
    
    # Test allocator lifecycle
    total_resources = ResourceQuota(
        cpu_cores=8.0,
        memory_gb=16.0,
        worker_slots=10,
        client_connections=20
    )
    
    allocator = DynamicResourceAllocator(
        total_resources=total_resources,
        allocation_interval=0.5,  # Fast for testing
        cleanup_interval=2.0
    )
    
    try:
        # Start allocator
        await allocator.start()
        print("✓ Allocator started")
        
        # Create and submit requests
        requests = []
        for i in range(3):
            quota = ResourceQuota(cpu_cores=1.0, memory_gb=2.0, worker_slots=1)
            request = ResourceRequest(
                request_id=f"async_req_{i}",
                network_id=f"network_{i}",
                required_resources=quota,
                priority=AllocationPriority.NORMAL,
                requested_at=datetime.now()
            )
            requests.append(request)
            allocator.request_resources(request)
        
        print(f"✓ Submitted {len(requests)} requests")
        
        # Wait for processing
        await asyncio.sleep(2.0)
        
        # Check allocations
        utilization = allocator.get_resource_utilization()
        active_allocations = utilization.get("active_allocations", 0)
        print(f"✓ Active allocations: {active_allocations}")
        
        # Test cleanup
        await asyncio.sleep(3.0)
        print("✓ Cleanup cycle completed")
        
    finally:
        # Stop allocator
        await allocator.stop()
        print("✓ Allocator stopped")


def main():
    """Main test function"""
    print("Running Dynamic Resource Allocation Tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestResourceQuota))
    suite.addTest(unittest.makeSuite(TestResourceRequest))
    suite.addTest(unittest.makeSuite(TestResourceConflictResolver))
    suite.addTest(unittest.makeSuite(TestDynamicResourceAllocator))
    suite.addTest(unittest.makeSuite(TestNetworkResourceProfile))
    suite.addTest(unittest.makeSuite(TestLicenseIntegration))
    suite.addTest(unittest.makeSuite(TestResourceAllocationIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run async tests if unit tests pass
    if result.wasSuccessful():
        print("\n" + "="*60)
        print("All unit tests passed! Running async integration tests...")
        asyncio.run(run_async_tests())
        print("✅ All tests completed successfully!")
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)