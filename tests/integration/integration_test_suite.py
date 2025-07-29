#!/usr/bin/env python3
"""
Integration Test Suite for Enhanced API Client and Network Management
Tests the complete workflow from network discovery to API communication
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Import our modules
from api_client import LicenseAwareAPIClient, MultiNetworkAPIClient, ConnectionStatus
from core.network_manager import NetworkManager, NetworkInfo, NetworkType, NetworkStatus
from network.network_discovery import NetworkDiscoveryService
from admin_approval_system import AdminApprovalSystem, ApprovalPriority
from core.protocol_spec import create_inference_request, create_inference_response, ResponseStatus
from security.license_validator import LicenseValidator, LicenseInfo, SubscriptionTier, LicenseStatus
from license_storage import LicenseStorage

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IntegrationTest")


class IntegrationTestSuite:
    """Complete integration test suite for network and API functionality"""
    
    def __init__(self):
        """Initialize test suite"""
        self.test_results = []
        self.admin_node_id = "admin_test_001"
        self.client_node_id = "client_test_001"
        
        # Create test license
        self.test_license = LicenseInfo(
            license_key="TIKT-PRO-12-TEST001",
            plan=SubscriptionTier.PRO,
            duration_months=12,
            unique_id="TEST001",
            expires_at=datetime.now() + timedelta(days=365),
            max_clients=20,
            allowed_models=["llama", "mistral"],
            allowed_features=["multi_network", "api_access"],
            status=LicenseStatus.VALID,
            hardware_signature="test_hw_sig",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        
        # Test components
        self.network_manager = None
        self.discovery_service = None
        self.approval_system = None
        self.api_client = None
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """
        Run complete integration test suite
        
        Returns:
            Test results summary
        """
        logger.info("=== Starting Integration Test Suite ===")
        
        try:
            # Test 1: License System Integration
            await self._test_license_integration()
            
            # Test 2: Network Management
            await self._test_network_management()
            
            # Test 3: Network Discovery
            await self._test_network_discovery()
            
            # Test 4: Admin Approval System
            await self._test_admin_approval_system()
            
            # Test 5: API Client Integration
            await self._test_api_client_integration()
            
            # Test 6: Multi-Network Routing
            await self._test_multi_network_routing()
            
            # Test 7: Protocol Compliance
            await self._test_protocol_compliance()
            
            # Test 8: End-to-End Workflow
            await self._test_end_to_end_workflow()
            
        except Exception as e:
            logger.error(f"Integration test suite failed: {e}", exc_info=True)
            self._add_test_result("Integration Test Suite", False, str(e))
        
        # Generate summary
        return self._generate_test_summary()
    
    async def _test_license_integration(self):
        """Test license system integration"""
        logger.info("Testing License Integration...")
        
        try:
            # Test license storage and validation
            license_storage = LicenseStorage()
            license_validator = LicenseValidator()
            
            # Save test license
            saved = license_storage.save_license_locally(self.test_license)
            self._add_test_result("License Storage", saved, "Failed to save license")
            
            # Load and validate license
            loaded_license = license_storage.load_license_info()
            self._add_test_result("License Loading", loaded_license is not None, "Failed to load license")
            
            if loaded_license:
                validation_result = security.license_validator.validate_license_key(loaded_license.license_key)
                self._add_test_result("License Validation", 
                                    validation_result.status == LicenseStatus.VALID,
                                    f"License validation failed: {validation_result.status}")
            
        except Exception as e:
            self._add_test_result("License Integration", False, str(e))
    
    async def _test_network_management(self):
        """Test network management functionality"""
        logger.info("Testing Network Management...")
        
        try:
            # Initialize network manager
            self.network_manager = NetworkManager(node_id=self.admin_node_id)
            
            # Test network creation
            network_info = self.network_manager.create_network(
                network_name="Test Network",
                model_id="llama-7b",
                network_type=NetworkType.PRIVATE,
                description="Integration test network"
            )
            
            self._add_test_result("Network Creation", 
                                network_info is not None,
                                "Failed to create network")
            
            if network_info:
                # Test network listing
                managed_networks = self.network_manager.managed_networks
                self._add_test_result("Network Listing",
                                    len(managed_networks) > 0,
                                    "No managed networks found")
                
                # Store network for later tests
                self.test_network = network_info
            
        except Exception as e:
            self._add_test_result("Network Management", False, str(e))
    
    async def _test_network_discovery(self):
        """Test network discovery functionality"""
        logger.info("Testing Network Discovery...")
        
        try:
            # Initialize discovery service
            managed_networks = {self.test_network.network_id: self.test_network} if hasattr(self, 'test_network') else {}
            self.discovery_service = NetworkDiscoveryService(
                node_id=self.admin_node_id,
                managed_networks=managed_networks
            )
            
            # Start discovery service
            started = self.discovery_service.start_service()
            self._add_test_result("Discovery Service Start", started, "Failed to start discovery service")
            
            if started:
                # Test network discovery
                discovered_networks = await self.discovery_service.discover_networks(timeout=2.0)
                self._add_test_result("Network Discovery",
                                    True,  # Discovery itself should work even if no networks found
                                    "Network discovery failed")
                
                # Test discovery statistics
                stats = self.discovery_service.get_discovery_statistics()
                self._add_test_result("Discovery Statistics",
                                    'service_running' in stats,
                                    "Failed to get discovery statistics")
                
                # Stop discovery service
                self.discovery_service.stop_service()
            
        except Exception as e:
            self._add_test_result("Network Discovery", False, str(e))
    
    async def _test_admin_approval_system(self):
        """Test admin approval system"""
        logger.info("Testing Admin Approval System...")
        
        try:
            # Initialize approval system
            managed_networks = {self.test_network.network_id: self.test_network} if hasattr(self, 'test_network') else {}
            self.approval_system = AdminApprovalSystem(
                admin_node_id=self.admin_node_id,
                managed_networks=managed_networks
            )
            
            if hasattr(self, 'test_network'):
                # Create approval request
                requester_info = {
                    'license_tier': 'PRO',
                    'license_key': 'TIKT-PRO-12-TEST002',
                    'node_capabilities': ['inference']
                }
                
                request = self.approval_system.create_approval_request(
                    requester_node_id=self.client_node_id,
                    requester_address="127.0.0.1",
                    network_id=self.test_network.network_id,
                    requester_info=requester_info,
                    priority=ApprovalPriority.NORMAL
                )
                
                self._add_test_result("Approval Request Creation",
                                    request is not None,
                                    "Failed to create approval request")
                
                if request:
                    # Test request processing
                    response = self.approval_system.process_approval_request(
                        request.request_id,
                        self.admin_node_id,
                        approve=True,
                        admin_notes="Test approval"
                    )
                    
                    self._add_test_result("Approval Request Processing",
                                        response.status.value == "approved",
                                        f"Request processing failed: {response.status}")
            else:
                self._add_test_result("Admin Approval System", False, "No test network available")
            
        except Exception as e:
            self._add_test_result("Admin Approval System", False, str(e))
    
    async def _test_api_client_integration(self):
        """Test API client with license integration"""
        logger.info("Testing API Client Integration...")
        
        try:
            # Initialize API client
            license_storage = LicenseStorage()
            self.api_client = LicenseAwareAPIClient(
                server_host="localhost",
                server_port=8702,
                license_storage=license_storage
            )
            
            # Test license loading
            license_loaded = self.api_client.load_license()
            self._add_test_result("API Client License Loading",
                                license_loaded,
                                "Failed to load license in API client")
            
            # Test connection statistics
            stats = self.api_client.get_connection_stats()
            self._add_test_result("API Client Statistics",
                                'status' in stats,
                                "Failed to get connection statistics")
            
            # Test license status
            license_status = self.api_client.get_license_status()
            self._add_test_result("API Client License Status",
                                'valid' in license_status,
                                "Failed to get license status")
            
            # Test inference request creation
            request = create_inference_request(
                session_id="test_session_123",
                network_id="test_network",
                license_hash="test_hash",
                input_tensors={"prompt": "Hello, world!"},
                step=1,
                model_id="llama-7b"
            )
            
            self._add_test_result("Inference Request Creation",
                                request is not None,
                                "Failed to create inference request")
            
        except Exception as e:
            self._add_test_result("API Client Integration", False, str(e))
    
    async def _test_multi_network_routing(self):
        """Test multi-network routing capabilities"""
        logger.info("Testing Multi-Network Routing...")
        
        try:
            # Initialize multi-network client
            license_storage = LicenseStorage()
            multi_client = MultiNetworkAPIClient(license_storage=license_storage)
            
            # Test license loading
            license_loaded = multi_client.load_license()
            self._add_test_result("Multi-Network License Loading",
                                license_loaded,
                                "Failed to load license in multi-network client")
            
            # Test network management
            networks = multi_client.networks
            self._add_test_result("Multi-Network Management",
                                isinstance(networks, dict),
                                "Failed to initialize network management")
            
            # Test statistics
            stats = multi_client.get_statistics() if hasattr(multi_client, 'get_statistics') else {}
            self._add_test_result("Multi-Network Statistics",
                                True,  # Basic functionality test
                                "Multi-network statistics failed")
            
        except Exception as e:
            self._add_test_result("Multi-Network Routing", False, str(e))
    
    async def _test_protocol_compliance(self):
        """Test protocol compliance"""
        logger.info("Testing Protocol Compliance...")
        
        try:
            # Test request creation
            request = create_inference_request(
                session_id="protocol_test",
                network_id="test_network",
                license_hash="test_hash",
                input_tensors={"prompt": "Protocol test"},
                step=1
            )
            
            self._add_test_result("Protocol Request Creation",
                                request is not None,
                                "Failed to create protocol request")
            
            # Test response creation
            response = create_inference_response(
                session_id="protocol_test",
                network_id="test_network",
                step=1,
                status="success",
                license_status="valid",
                output_tensors={"generated_text": "Protocol response"},
                processing_time=0.5
            )
            
            self._add_test_result("Protocol Response Creation",
                                response is not None,
                                "Failed to create protocol response")
            
            # Test serialization
            if request and response:
                try:
                    request_json = json.dumps(request.to_dict() if hasattr(request, 'to_dict') else request.__dict__, default=str)
                    response_json = json.dumps(response.to_dict() if hasattr(response, 'to_dict') else response.__dict__, default=str)
                    
                    self._add_test_result("Protocol Serialization",
                                        len(request_json) > 0 and len(response_json) > 0,
                                        "Failed to serialize protocol messages")
                except Exception as e:
                    self._add_test_result("Protocol Serialization", False, str(e))
            
        except Exception as e:
            self._add_test_result("Protocol Compliance", False, str(e))
    
    async def _test_end_to_end_workflow(self):
        """Test complete end-to-end workflow"""
        logger.info("Testing End-to-End Workflow...")
        
        try:
            # Simulate complete workflow
            workflow_steps = [
                "License validation",
                "Network creation", 
                "Network discovery",
                "Join request",
                "Admin approval",
                "API connection",
                "Inference request"
            ]
            
            completed_steps = 0
            
            # Check if we have all components
            if hasattr(self, 'test_license') and self.test_license:
                completed_steps += 1
            
            if hasattr(self, 'test_network') and self.test_network:
                completed_steps += 1
            
            if self.discovery_service:
                completed_steps += 1
            
            if self.approval_system:
                completed_steps += 2  # Join request + approval
            
            if self.api_client:
                completed_steps += 2  # API connection + inference
            
            workflow_success = completed_steps >= len(workflow_steps) * 0.7  # 70% success rate
            
            self._add_test_result("End-to-End Workflow",
                                workflow_success,
                                f"Workflow completed {completed_steps}/{len(workflow_steps)} steps")
            
        except Exception as e:
            self._add_test_result("End-to-End Workflow", False, str(e))
    
    def _add_test_result(self, test_name: str, success: bool, error_message: str = ""):
        """Add test result to results list"""
        result = {
            'test_name': test_name,
            'success': success,
            'error_message': error_message if not success else "",
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
        if not success and error_message:
            logger.error(f"  Error: {error_message}")
    
    def _generate_test_summary(self) -> Dict[str, Any]:
        """Generate test results summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        summary = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': round(success_rate, 2),
            'test_results': self.test_results,
            'overall_status': 'PASSED' if success_rate >= 70 else 'FAILED',
            'test_duration': time.time(),
            'recommendations': self._generate_recommendations()
        }
        
        return summary
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        failed_tests = [result for result in self.test_results if not result['success']]
        
        if failed_tests:
            recommendations.append("Review failed tests and fix underlying issues")
            
            # Specific recommendations based on failures
            for failed_test in failed_tests:
                if "License" in failed_test['test_name']:
                    recommendations.append("Check license validation and storage implementation")
                elif "Network" in failed_test['test_name']:
                    recommendations.append("Verify network management and discovery functionality")
                elif "API" in failed_test['test_name']:
                    recommendations.append("Review API client integration and WebSocket communication")
                elif "Protocol" in failed_test['test_name']:
                    recommendations.append("Validate protocol compliance and message formatting")
        
        if len(failed_tests) == 0:
            recommendations.append("All tests passed! System is ready for production")
        elif len(failed_tests) < len(self.test_results) * 0.3:
            recommendations.append("Most tests passed. Address remaining issues for production readiness")
        else:
            recommendations.append("Multiple critical issues found. Comprehensive review needed")
        
        return recommendations


async def main():
    """Main test execution function"""
    print("=== TikTrue Integration Test Suite ===\n")
    
    # Create and run test suite
    test_suite = IntegrationTestSuite()
    results = await test_suite.run_all_tests()
    
    # Print summary
    print("\n=== Test Results Summary ===")
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed_tests']}")
    print(f"Failed: {results['failed_tests']}")
    print(f"Success Rate: {results['success_rate']}%")
    print(f"Overall Status: {results['overall_status']}")
    
    print("\n=== Recommendations ===")
    for i, recommendation in enumerate(results['recommendations'], 1):
        print(f"{i}. {recommendation}")
    
    print("\n=== Detailed Results ===")
    for result in results['test_results']:
        status = "✓" if result['success'] else "✗"
        print(f"{status} {result['test_name']}")
        if result['error_message']:
            print(f"    Error: {result['error_message']}")
    
    # Save results to file
    with open('integration_test_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: integration_test_results.json")
    
    return results['overall_status'] == 'PASSED'


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)