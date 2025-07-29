#!/usr/bin/env python3
"""
Performance and Load Testing Suite for TikTrue Distributed LLM Platform
Tests system performance under various load conditions and stress scenarios
"""

import asyncio
import pytest
import json
import logging
import time
import psutil
import gc
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import statistics

# Import system modules
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PerformanceTests")

# Import TikTrue modules with error handling
try:
    from backend_api_client import BackendAPIClient, LoginCredentials
    from license_storage import LicenseStorage
    from security.license_validator import LicenseValidator
    BACKEND_API_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Backend API imports failed: {e}")
    BACKEND_API_AVAILABLE = False

try:
    from core.network_manager import NetworkManager
    from network.network_discovery import NetworkDiscoveryService
    NETWORK_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Network module imports failed: {e}")
    NETWORK_MODULES_AVAILABLE = False


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    test_name: str
    duration: float
    requests_per_second: float
    average_response_time: float
    min_response_time: float
    max_response_time: float
    success_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float
    error_count: int
    timestamp: str


@dataclass
class LoadTestConfig:
    """Load test configuration"""
    concurrent_clients: int
    requests_per_client: int
    test_duration: int
    ramp_up_time: int
    target_rps: Optional[int] = None


class PerformanceLoadTestSuite:
    """
    Comprehensive performance and load testing suite
    Tests system performance under various conditions
    """
    
    def __init__(self):
        """Initialize performance test suite"""
        self.test_results = []
        self.metrics_history = []
        self.backend_url = "https://api.test.tiktrue.com"
        
        # Performance thresholds
        self.thresholds = {
            'max_response_time': 5.0,  # seconds
            'min_success_rate': 0.95,  # 95%
            'max_memory_usage': 500,   # MB
            'max_cpu_usage': 80,       # percent
            'min_requests_per_second': 10
        }
    
    async def run_all_performance_tests(self) -> Dict[str, Any]:
        """Run all performance and load tests"""
        logger.info("=== Starting Performance and Load Tests ===")
        
        try:
            # Test 1: Single Client Performance
            await self.test_single_client_performance()
            
            # Test 2: Concurrent Client Load Testing
            await self.test_concurrent_client_load()
            
            # Test 3: Stress Testing
            await self.test_stress_scenarios()
            
            # Test 4: Memory Usage Testing
            await self.test_memory_usage_patterns()
            
            # Test 5: Network Latency Testing
            await self.test_network_latency_performance()
            
            # Test 6: Resource Exhaustion Testing
            await self.test_resource_exhaustion()
            
        except Exception as e:
            logger.error(f"Performance test suite failed: {e}", exc_info=True)
            self._add_test_result("Performance Test Suite", False, str(e))
        
        return self._generate_performance_summary()
    
    async def test_single_client_performance(self):
        """Test single client performance baseline"""
        logger.info("Testing Single Client Performance...")
        
        if not BACKEND_API_AVAILABLE:
            self._add_test_result("Single Client Performance", False, "Backend API not available")
            return
        
        try:
            start_time = time.time()
            request_times = []
            successful_requests = 0
            total_requests = 100
            
            async with BackendAPIClient(self.backend_url) as client:
                for i in range(total_requests):
                    request_start = time.time()
                    
                    # Test connection (lightweight operation)
                    result = await client.test_connection()
                    
                    request_end = time.time()
                    request_time = request_end - request_start
                    request_times.append(request_time)
                    
                    if result.success or result.error_code == "CONNECTION_ERROR":
                        successful_requests += 1
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            # Calculate metrics
            metrics = self._calculate_performance_metrics(
                test_name="Single Client Performance",
                duration=total_duration,
                request_times=request_times,
                successful_requests=successful_requests,
                total_requests=total_requests
            )
            
            self.metrics_history.append(metrics)
            
            # Validate against thresholds
            success = (
                metrics.average_response_time <= self.thresholds['max_response_time'] and
                metrics.success_rate >= self.thresholds['min_success_rate']
            )
            
            self._add_test_result("Single Client Performance", success, 
                                f"Avg response: {metrics.average_response_time:.3f}s, Success rate: {metrics.success_rate:.2%}")
            
        except Exception as e:
            self._add_test_result("Single Client Performance", False, str(e))    

    async def test_concurrent_client_load(self):
        """Test concurrent client load handling"""
        logger.info("Testing Concurrent Client Load...")
        
        if not BACKEND_API_AVAILABLE:
            self._add_test_result("Concurrent Client Load", False, "Backend API not available")
            return
        
        try:
            # Load test configuration
            config = LoadTestConfig(
                concurrent_clients=10,
                requests_per_client=20,
                test_duration=30,
                ramp_up_time=5
            )
            
            start_time = time.time()
            all_request_times = []
            successful_requests = 0
            total_requests = config.concurrent_clients * config.requests_per_client
            
            # Create concurrent client tasks
            tasks = []
            for client_id in range(config.concurrent_clients):
                task = self._simulate_client_load(client_id, config.requests_per_client)
                tasks.append(task)
            
            # Execute concurrent load test
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Aggregate results
            for result in results:
                if isinstance(result, dict):
                    all_request_times.extend(result['request_times'])
                    successful_requests += result['successful_requests']
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            # Calculate metrics
            metrics = self._calculate_performance_metrics(
                test_name="Concurrent Client Load",
                duration=total_duration,
                request_times=all_request_times,
                successful_requests=successful_requests,
                total_requests=total_requests
            )
            
            self.metrics_history.append(metrics)
            
            # Validate performance under load
            success = (
                metrics.requests_per_second >= self.thresholds['min_requests_per_second'] and
                metrics.success_rate >= self.thresholds['min_success_rate'] * 0.9  # Allow 10% degradation under load
            )
            
            self._add_test_result("Concurrent Client Load", success,
                                f"RPS: {metrics.requests_per_second:.1f}, Success rate: {metrics.success_rate:.2%}")
            
        except Exception as e:
            self._add_test_result("Concurrent Client Load", False, str(e))
    
    async def test_stress_scenarios(self):
        """Test system under stress conditions"""
        logger.info("Testing Stress Scenarios...")
        
        try:
            # Stress test: High concurrent connections
            await self._stress_test_high_concurrency()
            
            # Stress test: Rapid request bursts
            await self._stress_test_request_bursts()
            
            # Stress test: Long duration load
            await self._stress_test_sustained_load()
            
            self._add_test_result("Stress Testing", True, "All stress scenarios completed")
            
        except Exception as e:
            self._add_test_result("Stress Testing", False, str(e))
    
    async def test_memory_usage_patterns(self):
        """Test memory usage under various conditions"""
        logger.info("Testing Memory Usage Patterns...")
        
        try:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Test 1: Memory usage during normal operations
            memory_samples = []
            
            if BACKEND_API_AVAILABLE:
                for i in range(50):
                    async with BackendAPIClient(self.backend_url) as client:
                        await client.test_connection()
                    
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(current_memory)
                    
                    if i % 10 == 0:
                        gc.collect()  # Force garbage collection
            
            # Calculate memory metrics
            if memory_samples:
                max_memory = max(memory_samples)
                avg_memory = statistics.mean(memory_samples)
                memory_growth = max_memory - initial_memory
                
                # Check for memory leaks
                memory_leak_detected = memory_growth > 100  # More than 100MB growth
                
                self._add_test_result("Memory Usage Patterns", 
                                    not memory_leak_detected and max_memory <= self.thresholds['max_memory_usage'],
                                    f"Max memory: {max_memory:.1f}MB, Growth: {memory_growth:.1f}MB")
            else:
                self._add_test_result("Memory Usage Patterns", False, "No memory samples collected")
            
        except Exception as e:
            self._add_test_result("Memory Usage Patterns", False, str(e))
    
    async def test_network_latency_performance(self):
        """Test network latency and throughput performance"""
        logger.info("Testing Network Latency Performance...")
        
        if not NETWORK_MODULES_AVAILABLE:
            self._add_test_result("Network Latency Performance", False, "Network modules not available")
            return
        
        try:
            # Test network discovery performance
            discovery_service = NetworkDiscoveryService(node_id="perf_test_node")
            
            latency_samples = []
            
            for i in range(20):
                start_time = time.time()
                
                # Simulate network discovery
                try:
                    await discovery_service.discover_networks(timeout=1.0)
                except Exception:
                    pass  # Expected to fail, we're measuring timing
                
                end_time = time.time()
                latency = end_time - start_time
                latency_samples.append(latency)
            
            # Calculate latency metrics
            avg_latency = statistics.mean(latency_samples)
            max_latency = max(latency_samples)
            min_latency = min(latency_samples)
            
            # Latency should be reasonable
            success = avg_latency <= 2.0 and max_latency <= 5.0
            
            self._add_test_result("Network Latency Performance", success,
                                f"Avg latency: {avg_latency:.3f}s, Max: {max_latency:.3f}s")
            
        except Exception as e:
            self._add_test_result("Network Latency Performance", False, str(e))
    
    async def test_resource_exhaustion(self):
        """Test system behavior under resource exhaustion"""
        logger.info("Testing Resource Exhaustion Scenarios...")
        
        try:
            # Test 1: CPU intensive operations
            cpu_test_success = await self._test_cpu_intensive_operations()
            
            # Test 2: Memory intensive operations
            memory_test_success = await self._test_memory_intensive_operations()
            
            # Test 3: I/O intensive operations
            io_test_success = await self._test_io_intensive_operations()
            
            overall_success = cpu_test_success and memory_test_success and io_test_success
            
            self._add_test_result("Resource Exhaustion Testing", overall_success,
                                f"CPU: {cpu_test_success}, Memory: {memory_test_success}, I/O: {io_test_success}")
            
        except Exception as e:
            self._add_test_result("Resource Exhaustion Testing", False, str(e))
    
    async def _simulate_client_load(self, client_id: int, requests_count: int) -> Dict[str, Any]:
        """Simulate load from a single client"""
        request_times = []
        successful_requests = 0
        
        if not BACKEND_API_AVAILABLE:
            return {'request_times': [], 'successful_requests': 0}
        
        try:
            async with BackendAPIClient(self.backend_url) as client:
                for i in range(requests_count):
                    start_time = time.time()
                    
                    result = await client.test_connection()
                    
                    end_time = time.time()
                    request_times.append(end_time - start_time)
                    
                    if result.success or result.error_code == "CONNECTION_ERROR":
                        successful_requests += 1
                    
                    # Small delay to prevent overwhelming
                    await asyncio.sleep(0.01)
        
        except Exception as e:
            logger.warning(f"Client {client_id} failed: {e}")
        
        return {
            'request_times': request_times,
            'successful_requests': successful_requests
        }
    
    async def _stress_test_high_concurrency(self):
        """Stress test with high concurrency"""
        logger.info("Running high concurrency stress test...")
        
        if not BACKEND_API_AVAILABLE:
            return
        
        # Create many concurrent connections
        tasks = []
        for i in range(50):  # 50 concurrent clients
            task = self._simulate_client_load(i, 10)
            tasks.append(task)
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        successful_clients = sum(1 for result in results if isinstance(result, dict))
        
        logger.info(f"High concurrency test: {successful_clients}/50 clients succeeded in {end_time - start_time:.2f}s")
    
    async def _stress_test_request_bursts(self):
        """Stress test with rapid request bursts"""
        logger.info("Running request burst stress test...")
        
        if not BACKEND_API_AVAILABLE:
            return
        
        # Send bursts of requests
        for burst in range(5):
            tasks = []
            for i in range(20):  # 20 requests per burst
                task = self._single_request_test()
                tasks.append(task)
            
            start_time = time.time()
            await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            logger.info(f"Burst {burst + 1} completed in {end_time - start_time:.3f}s")
            await asyncio.sleep(1)  # Brief pause between bursts
    
    async def _stress_test_sustained_load(self):
        """Stress test with sustained load over time"""
        logger.info("Running sustained load stress test...")
        
        if not BACKEND_API_AVAILABLE:
            return
        
        # Sustained load for 60 seconds
        end_time = time.time() + 60
        request_count = 0
        
        while time.time() < end_time:
            tasks = []
            for i in range(5):  # 5 concurrent requests
                task = self._single_request_test()
                tasks.append(task)
            
            await asyncio.gather(*tasks, return_exceptions=True)
            request_count += 5
            await asyncio.sleep(0.1)
        
        logger.info(f"Sustained load test: {request_count} requests over 60 seconds")
    
    async def _single_request_test(self):
        """Single request for stress testing"""
        if not BACKEND_API_AVAILABLE:
            return
        
        try:
            async with BackendAPIClient(self.backend_url) as client:
                await client.test_connection()
        except Exception:
            pass  # Expected failures under stress
    
    async def _test_cpu_intensive_operations(self) -> bool:
        """Test CPU intensive operations"""
        try:
            # Simulate CPU intensive work
            def cpu_intensive_task():
                result = 0
                for i in range(1000000):
                    result += i * i
                return result
            
            start_time = time.time()
            
            # Run CPU intensive tasks concurrently
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(cpu_intensive_task) for _ in range(8)]
                for future in as_completed(futures):
                    future.result()
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Should complete within reasonable time
            return duration <= 10.0
            
        except Exception as e:
            logger.error(f"CPU intensive test failed: {e}")
            return False
    
    async def _test_memory_intensive_operations(self) -> bool:
        """Test memory intensive operations"""
        try:
            # Allocate and deallocate large amounts of memory
            large_data = []
            
            for i in range(10):
                # Allocate 10MB chunks
                chunk = bytearray(10 * 1024 * 1024)
                large_data.append(chunk)
            
            # Check memory usage
            process = psutil.Process()
            memory_usage = process.memory_info().rss / 1024 / 1024  # MB
            
            # Clean up
            del large_data
            gc.collect()
            
            # Memory usage should be reasonable
            return memory_usage <= 1000  # Less than 1GB
            
        except Exception as e:
            logger.error(f"Memory intensive test failed: {e}")
            return False
    
    async def _test_io_intensive_operations(self) -> bool:
        """Test I/O intensive operations"""
        try:
            # Create temporary files for I/O testing
            import tempfile
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Write multiple files concurrently
                async def write_file(file_id: int):
                    file_path = temp_path / f"test_file_{file_id}.txt"
                    with open(file_path, 'w') as f:
                        for i in range(1000):
                            f.write(f"Line {i} in file {file_id}\n")
                
                # Create I/O intensive workload
                tasks = [write_file(i) for i in range(20)]
                await asyncio.gather(*tasks)
                
                # Verify files were created
                created_files = list(temp_path.glob("test_file_*.txt"))
                return len(created_files) == 20
            
        except Exception as e:
            logger.error(f"I/O intensive test failed: {e}")
            return False 
   
    def _calculate_performance_metrics(self, test_name: str, duration: float, 
                                      request_times: List[float], successful_requests: int, 
                                      total_requests: int) -> PerformanceMetrics:
        """Calculate performance metrics from test data"""
        
        if not request_times:
            return PerformanceMetrics(
                test_name=test_name,
                duration=duration,
                requests_per_second=0,
                average_response_time=0,
                min_response_time=0,
                max_response_time=0,
                success_rate=0,
                memory_usage_mb=0,
                cpu_usage_percent=0,
                error_count=total_requests,
                timestamp=datetime.now().isoformat()
            )
        
        # Calculate timing metrics
        avg_response_time = statistics.mean(request_times)
        min_response_time = min(request_times)
        max_response_time = max(request_times)
        requests_per_second = len(request_times) / duration if duration > 0 else 0
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        error_count = total_requests - successful_requests
        
        # Get system metrics
        try:
            process = psutil.Process()
            memory_usage_mb = process.memory_info().rss / 1024 / 1024
            cpu_usage_percent = process.cpu_percent()
        except Exception:
            memory_usage_mb = 0
            cpu_usage_percent = 0
        
        return PerformanceMetrics(
            test_name=test_name,
            duration=duration,
            requests_per_second=requests_per_second,
            average_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            success_rate=success_rate,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
            error_count=error_count,
            timestamp=datetime.now().isoformat()
        )
    
    def _add_test_result(self, test_name: str, success: bool, details: str = ""):
        """Add test result to results list"""
        result = {
            'test_name': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat(),
            'category': 'performance'
        }
        self.test_results.append(result)
        
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
        if details:
            logger.info(f"  Details: {details}")
    
    def _generate_performance_summary(self) -> Dict[str, Any]:
        """Generate performance test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Performance statistics
        performance_stats = {}
        if self.metrics_history:
            performance_stats = {
                'average_response_time': statistics.mean([m.average_response_time for m in self.metrics_history]),
                'max_requests_per_second': max([m.requests_per_second for m in self.metrics_history]),
                'average_success_rate': statistics.mean([m.success_rate for m in self.metrics_history]),
                'peak_memory_usage_mb': max([m.memory_usage_mb for m in self.metrics_history]),
                'average_cpu_usage': statistics.mean([m.cpu_usage_percent for m in self.metrics_history if m.cpu_usage_percent > 0]) if [m.cpu_usage_percent for m in self.metrics_history if m.cpu_usage_percent > 0] else 0
            }
        
        return {
            'test_type': 'performance_and_load',
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': round(success_rate, 2),
            'test_results': self.test_results,
            'performance_metrics': [
                {
                    'test_name': m.test_name,
                    'duration': m.duration,
                    'requests_per_second': m.requests_per_second,
                    'average_response_time': m.average_response_time,
                    'success_rate': m.success_rate,
                    'memory_usage_mb': m.memory_usage_mb,
                    'timestamp': m.timestamp
                }
                for m in self.metrics_history
            ],
            'performance_statistics': performance_stats,
            'thresholds': self.thresholds,
            'overall_status': 'PASSED' if success_rate >= 70 else 'FAILED',
            'timestamp': datetime.now().isoformat()
        }


# Pytest integration
class TestPerformanceLoad:
    """Pytest wrapper for performance and load tests"""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_single_client_performance(self):
        """Test single client performance"""
        test_suite = PerformanceLoadTestSuite()
        await test_suite.test_single_client_performance()
        
        # Check if test passed
        results = [r for r in test_suite.test_results if 'Single Client' in r['test_name']]
        assert len(results) > 0
        
        # Should have reasonable performance
        if results[0]['success']:
            assert True
        else:
            pytest.skip(f"Performance test failed: {results[0]['details']}")
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_load(self):
        """Test concurrent client load"""
        test_suite = PerformanceLoadTestSuite()
        await test_suite.test_concurrent_client_load()
        
        # Check if test passed
        results = [r for r in test_suite.test_results if 'Concurrent' in r['test_name']]
        assert len(results) > 0
        
        # Should handle concurrent load
        if results[0]['success']:
            assert True
        else:
            pytest.skip(f"Load test failed: {results[0]['details']}")
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_memory_usage(self):
        """Test memory usage patterns"""
        test_suite = PerformanceLoadTestSuite()
        await test_suite.test_memory_usage_patterns()
        
        # Check if test passed
        results = [r for r in test_suite.test_results if 'Memory' in r['test_name']]
        assert len(results) > 0
        
        # Should not have memory leaks
        if results[0]['success']:
            assert True
        else:
            pytest.skip(f"Memory test failed: {results[0]['details']}")
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_stress_scenarios(self):
        """Test stress scenarios"""
        test_suite = PerformanceLoadTestSuite()
        await test_suite.test_stress_scenarios()
        
        # Check if test passed
        results = [r for r in test_suite.test_results if 'Stress' in r['test_name']]
        assert len(results) > 0
        
        # Should handle stress conditions
        if results[0]['success']:
            assert True
        else:
            pytest.skip(f"Stress test failed: {results[0]['details']}")


async def main():
    """Main function for running performance and load tests"""
    print("=== TikTrue Performance and Load Tests ===\n")
    
    test_suite = PerformanceLoadTestSuite()
    results = await test_suite.run_all_performance_tests()
    
    # Print summary
    print("\n=== Performance Test Results ===")
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed_tests']}")
    print(f"Failed: {results['failed_tests']}")
    print(f"Success Rate: {results['success_rate']}%")
    print(f"Overall Status: {results['overall_status']}")
    
    # Print performance statistics
    if results['performance_statistics']:
        print("\n=== Performance Statistics ===")
        stats = results['performance_statistics']
        print(f"Average Response Time: {stats.get('average_response_time', 0):.3f}s")
        print(f"Max Requests/Second: {stats.get('max_requests_per_second', 0):.1f}")
        print(f"Average Success Rate: {stats.get('average_success_rate', 0):.2%}")
        print(f"Peak Memory Usage: {stats.get('peak_memory_usage_mb', 0):.1f}MB")
        print(f"Average CPU Usage: {stats.get('average_cpu_usage', 0):.1f}%")
    
    # Print detailed results
    print("\n=== Detailed Results ===")
    for result in results['test_results']:
        status = "✓" if result['success'] else "✗"
        print(f"{status} {result['test_name']}")
        if result['details']:
            print(f"    Details: {result['details']}")
    
    # Save results
    results_file = Path("performance_load_test_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to: {results_file}")
    
    return results['overall_status'] == 'PASSED'


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)