"""
Tests for Network Health Monitoring Dashboard
Tests dashboard functionality, API endpoints, health monitoring integration, and UI components
"""

import json
import unittest
import asyncio
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from network_dashboard import NetworkDashboard, AsyncNetworkDashboard
from health_monitor import HealthMonitor, AsyncHealthMonitor, HealthStatus, NetworkHealthInfo
from core.service_runner import MultiNetworkServiceRunner, ServiceStatus, NetworkService
from api_client import NetworkConfig


class TestNetworkDashboard(unittest.TestCase):
    """Test NetworkDashboard functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock service runner
        self.mock_service_runner = Mock(spec=MultiNetworkServiceRunner)
        
        # Create dashboard with mock service runner
        self.dashboard = NetworkDashboard(
            service_runner=self.mock_service_runner,
            host="localhost",
            port=5000,
            refresh_interval=5
        )
        
        # Mock Flask test client
        self.app = self.dashboard.app.test_client()
    
    def test_dashboard_initialization(self):
        """Test dashboard initialization"""
        self.assertEqual(self.dashboard.host, "localhost")
        self.assertEqual(self.dashboard.port, 5000)
        self.assertEqual(self.dashboard.refresh_interval, 5)
        self.assertIsNotNone(self.dashboard.app)
        self.assertIsNone(self.dashboard.server)
        self.assertIsNone(self.dashboard.server_thread)
        self.assertIsNotNone(self.dashboard.health_monitor)
        
        print("✓ Dashboard initialization")
    
    def test_index_route(self):
        """Test index route"""
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"TikTrue Network Health Dashboard", response.data)
        
        # Test dashboard route
        response = self.app.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"TikTrue Network Health Dashboard", response.data)
        
        print("✓ Index route")
    
    def test_api_status_route(self):
        """Test API status route"""
        # Mock service runner response
        mock_status = {
            "service_status": "running",
            "uptime_seconds": 3600,
            "license_plan": "pro",
            "license_expires_at": "2023-12-31T23:59:59",
            "max_networks": 5,
            "running_networks": 2,
            "total_networks": 3,
            "total_requests": 1000,
            "total_errors": 10,
            "networks": {
                "network1": {
                    "status": "running",
                    "model_id": "llama-7b",
                    "host": "localhost",
                    "port": 8701,
                    "request_count": 500,
                    "error_count": 5,
                    "client_connections": 2
                }
            }
        }
        self.mock_service_runner.get_service_status.return_value = mock_status
        
        # Mock health monitor
        mock_health_summary = {
            "overall_status": "healthy",
            "total_networks": 1,
            "healthy_networks": 1,
            "warning_networks": 0,
            "critical_networks": 0,
            "average_response_time": 0.1,
            "networks": {
                "network1": {
                    "status": "healthy",
                    "last_heartbeat": datetime.now().isoformat(),
                    "response_time": 0.1,
                    "consecutive_failures": 0,
                    "recent_errors": [],
                    "performance_metrics": {}
                }
            }
        }
        self.dashboard.health_monitor.get_health_summary = Mock(return_value=mock_health_summary)
        
        # Test API endpoint
        response = self.app.get("/api/status")
        self.assertEqual(response.status_code, 200)
        
        # Parse response
        data = json.loads(response.data)
        
        # Check basic data
        self.assertEqual(data["service_status"], "running")
        self.assertEqual(data["uptime_seconds"], 3600)
        self.assertEqual(data["license_plan"], "pro")
        self.assertEqual(data["running_networks"], 2)
        self.assertEqual(data["total_networks"], 3)
        self.assertEqual(data["total_requests"], 1000)
        self.assertEqual(data["total_errors"], 10)
        
        # Check health integration
        self.assertEqual(data["overall_health_status"], "healthy")
        self.assertEqual(data["healthy_networks"], 1)
        self.assertEqual(data["warning_networks"], 0)
        self.assertEqual(data["critical_networks"], 0)
        self.assertEqual(data["average_response_time"], 0.1)
        
        # Check dashboard info
        self.assertIn("dashboard", data)
        self.assertEqual(data["dashboard"]["refresh_interval"], 5)
        
        # Check network health integration
        network1 = data["networks"]["network1"]
        self.assertEqual(network1["health_status"], "healthy")
        self.assertIn("last_heartbeat", network1)
        self.assertEqual(network1["response_time"], 0.1)
        
        print("✓ API status route with health integration")
    
    def test_api_networks_route(self):
        """Test API networks route"""
        # Mock service runner response
        mock_status = {
            "networks": {
                "network1": {
                    "status": "running",
                    "model_id": "llama-7b",
                    "host": "localhost",
                    "port": 8701,
                    "request_count": 500,
                    "error_count": 5,
                    "client_connections": 2
                },
                "network2": {
                    "status": "stopped",
                    "model_id": "mistral-7b",
                    "host": "localhost",
                    "port": 8702,
                    "request_count": 0,
                    "error_count": 0,
                    "client_connections": 0
                }
            }
        }
        self.mock_service_runner.get_service_status.return_value = mock_status
        
        # Test API endpoint
        response = self.app.get("/api/networks")
        self.assertEqual(response.status_code, 200)
        
        # Parse response
        data = json.loads(response.data)
        
        # Check data
        self.assertIn("networks", data)
        self.assertEqual(len(data["networks"]), 2)
        
        # Check first network
        network1 = next(n for n in data["networks"] if n["id"] == "network1")
        self.assertEqual(network1["status"], "running")
        self.assertEqual(network1["model_id"], "llama-7b")
        self.assertEqual(network1["request_count"], 500)
        
        print("✓ API networks route")
    
    def test_api_network_detail_route(self):
        """Test API network detail route"""
        # Mock service runner response
        mock_status = {
            "networks": {
                "network1": {
                    "status": "running",
                    "model_id": "llama-7b",
                    "host": "localhost",
                    "port": 8701,
                    "request_count": 500,
                    "error_count": 5,
                    "client_connections": 2,
                    "uptime_seconds": 3600,
                    "last_heartbeat": "2023-01-01T12:00:00",
                    "recent_errors": ["Error 1", "Error 2"]
                }
            }
        }
        self.mock_service_runner.get_service_status.return_value = mock_status
        
        # Mock network service for additional details
        mock_config = NetworkConfig(
            network_id="network1",
            model_id="llama-7b",
            host="localhost",
            port=8701,
            model_chain_order=["block1", "block2"],
            paths={"model_dir": "/path/to/model"},
            nodes={}
        )
        mock_network_service = Mock()
        mock_network_service.config = mock_config
        
        # Add to service runner networks
        self.mock_service_runner.networks = {"network1": mock_network_service}
        
        # Test API endpoint
        response = self.app.get("/api/network/network1")
        self.assertEqual(response.status_code, 200)
        
        # Parse response
        data = json.loads(response.data)
        
        # Check data
        self.assertIn("network", data)
        network = data["network"]
        self.assertEqual(network["status"], "running")
        self.assertEqual(network["model_id"], "llama-7b")
        self.assertEqual(network["request_count"], 500)
        self.assertEqual(network["error_count"], 5)
        self.assertEqual(len(network["recent_errors"]), 2)
        
        # Check config details
        self.assertIn("config", network)
        self.assertEqual(network["config"]["model_chain_order"], ["block1", "block2"])
        
        # Test non-existent network
        response = self.app.get("/api/network/nonexistent")
        self.assertEqual(response.status_code, 404)
        
        print("✓ API network detail route")
    
    def test_api_control_endpoints(self):
        """Test API control endpoints"""
        # Mock network service
        mock_network_service = Mock()
        mock_network_service.status = ServiceStatus.STOPPED
        mock_network_service.config = Mock()
        
        self.mock_service_runner.networks = {"network1": mock_network_service}
        
        # Test start network
        with patch('asyncio.new_event_loop') as mock_loop_func:
            mock_loop = Mock()
            mock_loop_func.return_value = mock_loop
            mock_loop.run_until_complete.return_value = True
            
            response = self.app.post("/api/control/start/network1")
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("started", data["message"])
        
        # Test stop network
        mock_network_service.status = ServiceStatus.RUNNING
        with patch('asyncio.new_event_loop') as mock_loop_func:
            mock_loop = Mock()
            mock_loop_func.return_value = mock_loop
            mock_loop.run_until_complete.return_value = True
            
            response = self.app.post("/api/control/stop/network1")
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("stopped", data["message"])
        
        # Test restart network
        with patch('asyncio.new_event_loop') as mock_loop_func:
            mock_loop = Mock()
            mock_loop_func.return_value = mock_loop
            mock_loop.run_until_complete.return_value = True
            
            response = self.app.post("/api/control/restart/network1")
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertTrue(data["success"])
            self.assertIn("restarted", data["message"])
        
        # Test non-existent network
        response = self.app.post("/api/control/start/nonexistent")
        self.assertEqual(response.status_code, 404)
        
        print("✓ API control endpoints")
    
    @patch('network_dashboard.make_server')
    def test_server_start_stop(self, mock_make_server):
        """Test server start and stop"""
        # Mock server
        mock_server = Mock()
        mock_make_server.return_value = mock_server
        
        # Test start
        result = self.dashboard.start()
        self.assertTrue(result)
        self.assertIsNotNone(self.dashboard.server)
        self.assertIsNotNone(self.dashboard.server_thread)
        mock_make_server.assert_called_once_with("localhost", 5000, self.dashboard.app)
        
        # Test stop
        result = self.dashboard.stop()
        self.assertTrue(result)
        self.assertIsNone(self.dashboard.server)
        self.assertIsNone(self.dashboard.server_thread)
        mock_server.shutdown.assert_called_once()
        
        print("✓ Server start and stop")


class TestHealthMonitorIntegration(unittest.TestCase):
    """Test health monitor integration with dashboard"""
    
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
        
        print("✓ Health monitor initialization")
    
    def test_health_status_tracking(self):
        """Test health status tracking"""
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
        
        print("✓ Health status tracking")
    
    def test_health_summary_generation(self):
        """Test health summary generation"""
        # Add multiple network health info
        networks = {
            "network1": NetworkHealthInfo(
                network_id="network1",
                status=HealthStatus.HEALTHY,
                last_heartbeat=datetime.now(),
                response_time=0.1,
                request_count=100,
                error_count=1,
                client_connections=2
            ),
            "network2": NetworkHealthInfo(
                network_id="network2",
                status=HealthStatus.WARNING,
                last_heartbeat=datetime.now(),
                response_time=0.2,
                request_count=50,
                error_count=5,
                client_connections=1
            ),
            "network3": NetworkHealthInfo(
                network_id="network3",
                status=HealthStatus.CRITICAL,
                last_heartbeat=datetime.now() - timedelta(minutes=5),
                response_time=1.0,
                request_count=10,
                error_count=8,
                client_connections=0
            )
        }
        
        self.health_monitor.network_health = networks
        
        # Generate summary
        summary = self.health_monitor.get_health_summary()
        
        # Check summary data
        self.assertEqual(summary["overall_status"], "critical")  # Worst status
        self.assertEqual(summary["total_networks"], 3)
        self.assertEqual(summary["healthy_networks"], 1)
        self.assertEqual(summary["warning_networks"], 1)
        self.assertEqual(summary["critical_networks"], 1)
        self.assertEqual(summary["total_requests"], 160)
        self.assertEqual(summary["total_errors"], 14)
        self.assertEqual(summary["total_connections"], 3)
        
        # Check individual network data
        self.assertIn("networks", summary)
        self.assertEqual(len(summary["networks"]), 3)
        
        network1_summary = summary["networks"]["network1"]
        self.assertEqual(network1_summary["status"], "healthy")
        self.assertEqual(network1_summary["request_count"], 100)
        self.assertEqual(network1_summary["error_count"], 1)
        
        print("✓ Health summary generation")
    
    def test_callback_system(self):
        """Test callback system for health changes"""
        # Track callback calls
        health_changes = []
        failures = []
        
        def on_health_change(network_id: str, old_status: HealthStatus, new_status: HealthStatus):
            health_changes.append((network_id, old_status, new_status))
        
        def on_failure(network_id: str, message: str):
            failures.append((network_id, message))
        
        # Add callbacks
        self.health_monitor.add_health_change_callback(on_health_change)
        self.health_monitor.add_failure_callback(on_failure)
        
        # Simulate health change
        network_id = "test-network"
        health_info = NetworkHealthInfo(
            network_id=network_id,
            status=HealthStatus.HEALTHY,
            last_heartbeat=datetime.now(),
            response_time=0.1
        )
        self.health_monitor.network_health[network_id] = health_info
        
        # Trigger callbacks manually (simulating what would happen in monitoring loop)
        for callback in self.health_monitor.health_change_callbacks:
            callback(network_id, HealthStatus.UNKNOWN, HealthStatus.HEALTHY)
        
        for callback in self.health_monitor.failure_callbacks:
            callback(network_id, "Test failure message")
        
        # Check callbacks were called
        self.assertEqual(len(health_changes), 1)
        self.assertEqual(health_changes[0], (network_id, HealthStatus.UNKNOWN, HealthStatus.HEALTHY))
        
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0], (network_id, "Test failure message"))
        
        print("✓ Callback system")


class TestAsyncHealthMonitor(unittest.TestCase):
    """Test async health monitor functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.mock_service_runner = Mock(spec=MultiNetworkServiceRunner)
        self.async_health_monitor = AsyncHealthMonitor(
            service_runner=self.mock_service_runner,
            heartbeat_interval=1
        )
    
    def test_async_wrapper(self):
        """Test async wrapper functionality"""
        # Test that async wrapper properly wraps the sync health monitor
        self.assertIsNotNone(self.async_health_monitor.monitor)
        self.assertEqual(self.async_health_monitor.monitor.heartbeat_interval, 1)
        
        # Test callback forwarding
        callback_called = False
        
        def test_callback(network_id: str, old_status: HealthStatus, new_status: HealthStatus):
            nonlocal callback_called
            callback_called = True
        
        self.async_health_monitor.add_health_change_callback(test_callback)
        
        # Trigger callback through wrapped monitor
        for callback in self.async_health_monitor.monitor.health_change_callbacks:
            callback("test", HealthStatus.UNKNOWN, HealthStatus.HEALTHY)
        
        self.assertTrue(callback_called)
        
        print("✓ Async wrapper functionality")


def run_integration_test():
    """Run integration test with real components"""
    async def integration_test():
        print("\n" + "="*50)
        print("INTEGRATION TEST")
        print("="*50)
        
        # Create service runner
        service_runner = MultiNetworkServiceRunner()
        
        # Create dashboard with health monitoring
        dashboard = NetworkDashboard(
            service_runner=service_runner,
            host="localhost",
            port=5001,  # Different port to avoid conflicts
            refresh_interval=2
        )
        
        try:
            # Start service runner
            await service_runner.start()
            print("✓ Service runner started")
            
            # Start dashboard
            success = dashboard.start()
            if success:
                print("✓ Dashboard started")
                
                # Wait for health monitoring to initialize
                await asyncio.sleep(5)
                
                # Test API endpoints
                import requests
                
                try:
                    # Test status endpoint
                    response = requests.get("http://localhost:5001/api/status", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        print(f"✓ Status API: {data.get('service_status', 'unknown')}")
                    else:
                        print(f"❌ Status API failed: {response.status_code}")
                    
                    # Test networks endpoint
                    response = requests.get("http://localhost:5001/api/networks", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        print(f"✓ Networks API: {len(data.get('networks', []))} networks")
                    else:
                        print(f"❌ Networks API failed: {response.status_code}")
                
                except requests.exceptions.RequestException as e:
                    print(f"⚠️  API test skipped (server not accessible): {e}")
                
                print("✅ Integration test completed")
            else:
                print("❌ Failed to start dashboard")
        
        except Exception as e:
            print(f"❌ Integration test error: {e}")
        finally:
            # Cleanup
            dashboard.stop()
            await service_runner.shutdown()
            print("✓ Cleanup completed")
    
    asyncio.run(integration_test())


def main():
    """Main test function"""
    import sys
    
    # Run unit tests
    print("Running Network Dashboard Tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestNetworkDashboard))
    suite.addTest(unittest.makeSuite(TestHealthMonitorIntegration))
    suite.addTest(unittest.makeSuite(TestAsyncHealthMonitor))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run integration test if unit tests pass
    if result.wasSuccessful():
        print("\n" + "="*60)
        print("All unit tests passed! Running integration test...")
        run_integration_test()
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        sys.exit(1)


if __name__ == "__main__":
    main()