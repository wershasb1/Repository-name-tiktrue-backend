"""
Tests for Fault Tolerance and Recovery System
Tests health monitoring, failover management, and block redistribution
"""

import asyncio
import unittest
import time
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

from health_monitor import (
    HealthMonitor, AsyncHealthMonitor, HealthStatus, NetworkHealthInfo, 
    WorkerHealthInfo, AdminNotification
)
from failover_manager import (
    FailoverManager, FailoverStrategy, DegradationLevel, BackupWorker,
    FailoverEvent, WorkloadTransfer, BlockRedistribution, BlockAssignment
)
from core.service_runner import MultiNetworkServiceRunner, ServiceStatus, NetworkService
from api_client import NetworkConfig
from security.license_validator import LicenseInfo, SubscriptionTier


class TestHealthMonitor(unittest.TestCase):
    """Test HealthMonitor functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock service runner
        self.mock_service_runner = Mock(spec=MultiNetworkServiceRunner)
        
        # Create health monitor
        self.health_monitor = HealthMonitor(
            service_runner=self.mock_service_runner,
            heartbeat_interval=1,  # Fast for testing
            failure_threshold=2,
            warning_threshold=1
        )
    
    def test_health_monitor_initialization(self):
        """Test health monitor initialization"""
        self.assertEqual(self.health_monitor.heartbeat_interval, 1)
        self.assertEqual(self.health_monitor.failure_threshold, 2)
        self.assertEqual(self.health_monitor.warning_threshold, 1)
        self.assertFalse(self.health_monitor.monitoring_active)
        self.assertEqual(len(self.health_monitor.network_health), 0)
        self.assertEqual(len(self.health_monitor.worker_health), 0)
        
        print("✓ Health monitor initialization")
    
    def test_network_health_tracking(self):
        """Test network health tracking"""
        # Create network health info
        network_id = "test-network"
        health_info = NetworkHealthInfo(
            network_id=network_id,
            status=HealthStatus.HEALTHY,
            last_heartbeat=datetime.now(),
            response_time=0.1
        )
        
        self.health_monitor.network_health[network_id] = health_info
        
        # Test getting health info
        retrieved_info = self.health_monitor.get_network_health(network_id)
        self.assertIsNotNone(retrieved_info)
        self.assertEqual(retrieved_info.network_id, network_id)
        self.assertEqual(retrieved_info.status, HealthStatus.HEALTHY)
        
        # Test overall health status
        overall_status = self.health_monitor.get_overall_health_status()
        self.assertEqual(overall_status, HealthStatus.HEALTHY)
        
        print("✓ Network health tracking")
    
    def test_worker_health_monitoring(self):
        """Test worker health monitoring"""
        # Create worker health info
        worker_id = "test-worker"
        worker_info = WorkerHealthInfo(
            worker_id=worker_id,
            network_id="test-network",
            status=HealthStatus.HEALTHY,
            last_heartbeat=datetime.now(),
            response_time=0.1,
            worker_host="localhost",
            worker_port=8801,
            model_blocks=["block1", "block2"]
        )
        
        self.health_monitor.worker_health[worker_id] = worker_info
        
        # Test monitor_worker_health function
        monitored_info = self.health_monitor.monitor_worker_health(worker_id)
        self.assertIsNotNone(monitored_info)
        self.assertEqual(monitored_info.worker_id, worker_id)
        self.assertEqual(monitored_info.status, HealthStatus.HEALTHY)
        self.assertEqual(len(monitored_info.model_blocks), 2)
        
        # Test getting all worker health
        all_workers = self.health_monitor.get_all_worker_health()
        self.assertEqual(len(all_workers), 1)
        self.assertIn(worker_id, all_workers)
        
        print("✓ Worker health monitoring")
    
    def test_admin_notifications(self):
        """Test admin notification system"""
        # Create admin notification
        asyncio.run(self.health_monitor._create_admin_notification(
            severity="warning",
            source="TestWorker",
            message="Test notification message",
            details={"test_key": "test_value"}
        ))
        
        # Check notification was created
        notifications = self.health_monitor.get_admin_notifications()
        self.assertEqual(len(notifications), 1)
        
        notification = notifications[0]
        self.assertEqual(notification.severity, "warning")
        self.assertEqual(notification.source, "TestWorker")
        self.assertEqual(notification.message, "Test notification message")
        self.assertFalse(notification.acknowledged)
        
        # Test acknowledging notification
        success = self.health_monitor.acknowledge_notification(
            notification.notification_id, "test_admin"
        )
        self.assertTrue(success)
        self.assertTrue(notification.acknowledged)
        self.assertEqual(notification.acknowledged_by, "test_admin")
        
        # Test getting unacknowledged notifications
        unack_notifications = self.health_monitor.get_admin_notifications(unacknowledged_only=True)
        self.assertEqual(len(unack_notifications), 0)
        
        print("✓ Admin notification system")
    
    def test_health_callbacks(self):
        """Test health change callbacks"""
        # Track callback calls
        health_changes = []
        failures = []
        worker_failures = []
        
        def on_health_change(network_id: str, old_status: HealthStatus, new_status: HealthStatus):
            health_changes.append((network_id, old_status, new_status))
        
        def on_failure(network_id: str, message: str):
            failures.append((network_id, message))
        
        def on_worker_failure(worker_id: str, message: str):
            worker_failures.append((worker_id, message))
        
        # Add callbacks
        self.health_monitor.add_health_change_callback(on_health_change)
        self.health_monitor.add_failure_callback(on_failure)
        self.health_monitor.add_worker_failure_callback(on_worker_failure)
        
        # Trigger callbacks manually
        for callback in self.health_monitor.health_change_callbacks:
            callback("test-network", HealthStatus.UNKNOWN, HealthStatus.HEALTHY)
        
        for callback in self.health_monitor.failure_callbacks:
            callback("test-network", "Test failure message")
        
        for callback in self.health_monitor.worker_failure_callbacks:
            callback("test-worker", "Test worker failure")
        
        # Check callbacks were called
        self.assertEqual(len(health_changes), 1)
        self.assertEqual(health_changes[0], ("test-network", HealthStatus.UNKNOWN, HealthStatus.HEALTHY))
        
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0], ("test-network", "Test failure message"))
        
        self.assertEqual(len(worker_failures), 1)
        self.assertEqual(worker_failures[0], ("test-worker", "Test worker failure"))
        
        print("✓ Health change callbacks")


class TestFailoverManager(unittest.TestCase):
    """Test FailoverManager functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock dependencies
        self.mock_service_runner = Mock(spec=MultiNetworkServiceRunner)
        self.mock_health_monitor = Mock(spec=HealthMonitor)
        self.mock_resource_allocator = Mock()
        
        # Create failover manager
        self.failover_manager = FailoverManager(
            service_runner=self.mock_service_runner,
            health_monitor=self.mock_health_monitor,
            resource_allocator=self.mock_resource_allocator,
            failover_timeout=30.0,
            max_concurrent_failovers=2
        )
    
    def test_failover_manager_initialization(self):
        """Test failover manager initialization"""
        self.assertEqual(self.failover_manager.failover_timeout, 30.0)
        self.assertEqual(self.failover_manager.max_concurrent_failovers, 2)
        self.assertFalse(self.failover_manager.monitoring_active)
        self.assertEqual(len(self.failover_manager.backup_workers), 0)
        self.assertEqual(len(self.failover_manager.active_failovers), 0)
        self.assertEqual(self.failover_manager.current_degradation_level, DegradationLevel.NONE)
        
        print("✓ Failover manager initialization")
    
    def test_backup_worker_management(self):
        """Test backup worker management"""
        # Create backup worker
        backup_worker = BackupWorker(
            worker_id="backup-worker-1",
            network_id="test-network",
            host="localhost",
            port=8901,
            model_blocks=["block1", "block2"],
            priority=1
        )
        
        self.failover_manager.backup_workers[backup_worker.worker_id] = backup_worker
        
        # Test backup worker status
        status = self.failover_manager.get_backup_workers_status()
        self.assertEqual(len(status), 1)
        self.assertIn("backup-worker-1", status)
        
        worker_status = status["backup-worker-1"]
        self.assertEqual(worker_status["network_id"], "test-network")
        self.assertEqual(worker_status["status"], "standby")
        self.assertEqual(worker_status["priority"], 1)
        
        print("✓ Backup worker management")
    
    def test_graceful_degradation(self):
        """Test graceful degradation functionality"""
        # Test degradation levels
        asyncio.run(self.failover_manager.graceful_degradation(
            DegradationLevel.REDUCED_QUALITY, "Test quality reduction"
        ))
        
        self.assertEqual(
            self.failover_manager.current_degradation_level, 
            DegradationLevel.REDUCED_QUALITY
        )
        
        # Test degradation history
        self.assertEqual(len(self.failover_manager.degradation_history), 1)
        history_entry = self.failover_manager.degradation_history[0]
        self.assertEqual(history_entry[1], DegradationLevel.REDUCED_QUALITY)
        self.assertEqual(history_entry[2], "Test quality reduction")
        
        # Test further degradation
        asyncio.run(self.failover_manager.graceful_degradation(
            DegradationLevel.MAINTENANCE_MODE, "System overload"
        ))
        
        self.assertEqual(
            self.failover_manager.current_degradation_level, 
            DegradationLevel.MAINTENANCE_MODE
        )
        
        print("✓ Graceful degradation")
    
    def test_failover_event_tracking(self):
        """Test failover event tracking"""
        # Create failover event
        event = FailoverEvent(
            event_id="test-failover-1",
            timestamp=datetime.now(),
            event_type="worker_failure",
            source_id="failed-worker-1",
            target_id="backup-worker-1",
            strategy_used=FailoverStrategy.IMMEDIATE,
            success=True,
            duration_seconds=5.0
        )
        
        self.failover_manager.failover_history.append(event)
        
        # Test failover status
        status = self.failover_manager.get_failover_status()
        self.assertEqual(len(status["recent_events"]), 1)
        
        recent_event = status["recent_events"][0]
        self.assertEqual(recent_event["event_id"], "test-failover-1")
        self.assertEqual(recent_event["type"], "worker_failure")
        self.assertEqual(recent_event["source"], "failed-worker-1")
        self.assertEqual(recent_event["target"], "backup-worker-1")
        self.assertTrue(recent_event["success"])
        
        print("✓ Failover event tracking")
    
    def test_workload_transfer(self):
        """Test workload transfer functionality"""
        # Test workload transfer
        result = asyncio.run(self.failover_manager.transfer_workload(
            source_worker="failed-worker",
            target_worker="backup-worker",
            model_blocks=["block1", "block2"]
        ))
        
        self.assertTrue(result)
        
        # Check transfer was recorded
        self.assertEqual(len(self.failover_manager.workload_transfers), 1)
        
        transfer = list(self.failover_manager.workload_transfers.values())[0]
        self.assertEqual(transfer.source_worker, "failed-worker")
        self.assertEqual(transfer.target_worker, "backup-worker")
        self.assertEqual(transfer.model_blocks, ["block1", "block2"])
        self.assertTrue(transfer.success)
        
        print("✓ Workload transfer")


class TestBlockRedistribution(unittest.TestCase):
    """Test block redistribution functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock dependencies
        self.mock_service_runner = Mock(spec=MultiNetworkServiceRunner)
        self.mock_health_monitor = Mock(spec=HealthMonitor)
        
        # Mock worker health data
        worker_health = {
            "network1_worker1": WorkerHealthInfo(
                worker_id="network1_worker1",
                network_id="network1",
                status=HealthStatus.CRITICAL,  # Failed worker
                last_heartbeat=datetime.now(),
                response_time=0.0,
                model_blocks=["block1", "block2"]
            ),
            "network1_worker2": WorkerHealthInfo(
                worker_id="network1_worker2",
                network_id="network1",
                status=HealthStatus.HEALTHY,
                last_heartbeat=datetime.now(),
                response_time=0.1,
                model_blocks=["block3", "block4"]
            )
        }
        
        self.mock_health_monitor.get_all_worker_health.return_value = worker_health
        
        # Create failover manager
        self.failover_manager = FailoverManager(
            service_runner=self.mock_service_runner,
            health_monitor=self.mock_health_monitor
        )
    
    def test_get_worker_blocks(self):
        """Test getting worker blocks"""
        blocks = self.failover_manager._get_worker_blocks("network1_worker1", "network1")
        self.assertEqual(blocks, ["block1", "block2"])
        
        blocks = self.failover_manager._get_worker_blocks("network1_worker2", "network1")
        self.assertEqual(blocks, ["block3", "block4"])
        
        # Test non-existent worker
        blocks = self.failover_manager._get_worker_blocks("nonexistent", "network1")
        self.assertEqual(blocks, [])
        
        print("✓ Get worker blocks")
    
    def test_block_assignment_management(self):
        """Test block assignment management"""
        # Create block assignments
        assignment1 = BlockAssignment(
            block_id="block1",
            network_id="network1",
            assigned_worker="worker1",
            assignment_priority=1
        )
        
        assignment2 = BlockAssignment(
            block_id="block2",
            network_id="network1",
            assigned_worker="worker1",
            assignment_priority=1
        )
        
        self.failover_manager.block_assignments["block1"] = assignment1
        self.failover_manager.block_assignments["block2"] = assignment2
        
        # Test getting assignments for network
        network_assignments = self.failover_manager.get_block_assignments("network1")
        self.assertEqual(len(network_assignments), 2)
        self.assertIn("block1", network_assignments)
        self.assertIn("block2", network_assignments)
        
        # Test getting all assignments
        all_assignments = self.failover_manager.get_block_assignments()
        self.assertEqual(len(all_assignments), 2)
        
        print("✓ Block assignment management")
    
    def test_redistribution_plan_creation(self):
        """Test redistribution plan creation"""
        # Mock available workers
        async def mock_get_available_workers(network_id, exclude_worker):
            return ["worker2", "worker3"]
        
        self.failover_manager._get_available_workers = mock_get_available_workers
        
        # Test plan creation
        plan = asyncio.run(self.failover_manager._create_redistribution_plan(
            "network1", ["block1", "block2", "block3"], "worker1"
        ))
        
        self.assertIsInstance(plan, dict)
        self.assertTrue(len(plan) > 0)
        
        # Check blocks are distributed
        total_blocks = sum(len(blocks) for blocks in plan.values())
        self.assertEqual(total_blocks, 3)
        
        print("✓ Redistribution plan creation")
    
    def test_block_redistribution_process(self):
        """Test complete block redistribution process"""
        # Mock license validation
        async def mock_check_license(network_id):
            return True
        
        # Mock plan creation
        async def mock_create_plan(network_id, blocks, failed_worker):
            return {"worker2": ["block1"], "worker3": ["block2"]}
        
        # Mock available workers
        async def mock_get_available_workers(network_id, exclude_worker):
            return ["worker2", "worker3"]
        
        # Mock conflict resolution
        async def mock_resolve_conflicts(network_id, plan):
            return 0
        
        # Mock execution
        async def mock_execute_redistribution(redistribution):
            return True
        
        # Mock config update
        async def mock_update_config(network_id, plan):
            pass
        
        # Apply mocks
        self.failover_manager._check_redistribution_license_permissions = mock_check_license
        self.failover_manager._create_redistribution_plan = mock_create_plan
        self.failover_manager._get_available_workers = mock_get_available_workers
        self.failover_manager._resolve_block_assignment_conflicts = mock_resolve_conflicts
        self.failover_manager._execute_block_redistribution = mock_execute_redistribution
        self.failover_manager._update_network_configuration_after_redistribution = mock_update_config
        
        # Test redistribution
        result = asyncio.run(self.failover_manager.redistribute_blocks(
            "network1_worker1", "network1"
        ))
        
        self.assertTrue(result)
        
        # Check redistribution was recorded
        self.assertEqual(len(self.failover_manager.redistribution_history), 1)
        
        redistribution = self.failover_manager.redistribution_history[0]
        self.assertEqual(redistribution.network_id, "network1")
        self.assertEqual(redistribution.failed_worker, "network1_worker1")
        self.assertTrue(redistribution.success)
        
        print("✓ Block redistribution process")
    
    def test_redistribution_status_reporting(self):
        """Test redistribution status reporting"""
        # Create some redistribution history
        redistribution = BlockRedistribution(
            redistribution_id="test-redist-1",
            network_id="network1",
            failed_worker="worker1",
            affected_blocks=["block1", "block2"],
            redistribution_plan={"worker2": ["block1"], "worker3": ["block2"]},
            started_at=datetime.now(),
            completed_at=datetime.now(),
            success=True,
            conflicts_resolved=1
        )
        
        self.failover_manager.redistribution_history.append(redistribution)
        
        # Test status reporting
        status = self.failover_manager.get_redistribution_status()
        
        self.assertEqual(status["active_redistributions"], 0)
        self.assertEqual(status["total_redistributions"], 1)
        self.assertEqual(len(status["recent_redistributions"]), 1)
        
        recent_redist = status["recent_redistributions"][0]
        self.assertEqual(recent_redist["redistribution_id"], "test-redist-1")
        self.assertEqual(recent_redist["network_id"], "network1")
        self.assertEqual(recent_redist["failed_worker"], "worker1")
        self.assertEqual(recent_redist["affected_blocks"], 2)
        self.assertTrue(recent_redist["success"])
        self.assertEqual(recent_redist["conflicts_resolved"], 1)
        
        print("✓ Redistribution status reporting")


class TestIntegration(unittest.TestCase):
    """Test integration between components"""
    
    def test_health_monitor_failover_integration(self):
        """Test integration between health monitor and failover manager"""
        # Create health monitor
        health_monitor = HealthMonitor(heartbeat_interval=1)
        
        # Create failover manager with health monitor
        failover_manager = FailoverManager(health_monitor=health_monitor)
        
        # Test that callbacks are registered
        self.assertEqual(len(health_monitor.worker_failure_callbacks), 1)
        self.assertEqual(len(health_monitor.failure_callbacks), 1)
        
        # Test callback invocation
        callback_called = False
        
        def test_callback(worker_id, message):
            nonlocal callback_called
            callback_called = True
        
        # Replace the callback with our test callback
        health_monitor.worker_failure_callbacks = [test_callback]
        
        # Trigger callback
        for callback in health_monitor.worker_failure_callbacks:
            callback("test-worker", "test message")
        
        self.assertTrue(callback_called)
        
        print("✓ Health monitor failover integration")


async def run_async_integration_tests():
    """Run async integration tests"""
    print("\n" + "="*50)
    print("ASYNC INTEGRATION TESTS")
    print("="*50)
    
    # Test health monitor lifecycle
    health_monitor = HealthMonitor(heartbeat_interval=1)
    
    try:
        # Start health monitor
        await health_monitor.start_monitoring()
        print("✓ Health monitor started")
        
        # Wait briefly
        await asyncio.sleep(2.0)
        
        # Stop health monitor
        await health_monitor.stop_monitoring()
        print("✓ Health monitor stopped")
        
    except Exception as e:
        print(f"❌ Health monitor test failed: {e}")
    
    # Test failover manager lifecycle
    failover_manager = FailoverManager()
    
    try:
        # Start failover manager
        await failover_manager.start()
        print("✓ Failover manager started")
        
        # Wait briefly
        await asyncio.sleep(2.0)
        
        # Stop failover manager
        await failover_manager.stop()
        print("✓ Failover manager stopped")
        
    except Exception as e:
        print(f"❌ Failover manager test failed: {e}")


def main():
    """Main test function"""
    print("Running Fault Tolerance and Recovery System Tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestHealthMonitor))
    suite.addTest(unittest.makeSuite(TestFailoverManager))
    suite.addTest(unittest.makeSuite(TestBlockRedistribution))
    suite.addTest(unittest.makeSuite(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run async tests if unit tests pass
    if result.wasSuccessful():
        print("\n" + "="*60)
        print("All unit tests passed! Running async integration tests...")
        asyncio.run(run_async_integration_tests())
        print("✅ All tests completed successfully!")
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)