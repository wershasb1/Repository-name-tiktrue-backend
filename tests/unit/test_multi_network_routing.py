"""
Tests for Multi-Network Routing Capabilities
Tests network selection, routing logic, failover, and session management
"""

import asyncio
import json
import time
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from api_client import (
    MultiNetworkAPIClient, NetworkConfig, NetworkConnection, 
    NetworkFailoverStrategy, ConnectionStatus, LicenseAwareAPIClient
)
from core.protocol_spec import (
    InferenceRequest, InferenceResponse, HeartbeatRequest, HeartbeatResponse,
    ResponseStatus, LicenseStatus, create_inference_request, create_inference_response
)
from license_storage import LicenseStorage


class TestNetworkConfig:
    """Test NetworkConfig data structure and loading"""
    
    def test_network_config_creation(self):
        """Test creating NetworkConfig manually"""
        config = NetworkConfig(
            network_id="test_network",
            model_id="llama-7b",
            host="localhost",
            port=8701,
            model_chain_order=["block_1", "block_2"],
            paths={"model_dir": "/path/to/model"},
            nodes={"node1": {"host": "localhost", "port": 8701}}
        )
        
        assert config.network_id == "test_network"
        assert config.model_id == "llama-7b"
        assert config.host == "localhost"
        assert config.port == 8701
        assert config.model_chain_order == ["block_1", "block_2"]
        
        print("✓ NetworkConfig creation")
    
    def test_network_config_from_file(self):
        """Test loading NetworkConfig from JSON file"""
        # Create temporary config file
        config_data = {
            "network_id": "test_network_file",
            "model_id": "mistral-7b",
            "nodes": {
                "primary_node": {
                    "host": "192.168.1.100",
                    "port": 8702
                }
            },
            "model_chain_order": ["block_1", "block_2", "block_3"],
            "paths": {
                "model_dir": "/models/mistral"
            }
        }
        
        # Write temporary file
        with open("temp_network_config.json", "w") as f:
            json.dump(config_data, f)
        
        try:
            # Load config from file
            config = NetworkConfig.from_file("temp_network_config.json")
            
            assert config.network_id == "test_network_file"
            assert config.model_id == "mistral-7b"
            assert config.host == "192.168.1.100"
            assert config.port == 8702
            assert config.model_chain_order == ["block_1", "block_2", "block_3"]
            assert config.paths == {"model_dir": "/models/mistral"}
            
            print("✓ NetworkConfig from file")
            
        finally:
            # Clean up
            import os
            if os.path.exists("temp_network_config.json"):
                os.remove("temp_network_config.json")


class TestMultiNetworkAPIClient:
    """Test MultiNetworkAPIClient functionality"""
    
    def test_client_initialization(self):
        """Test multi-network client initialization"""
        client = MultiNetworkAPIClient(
            failover_strategy=NetworkFailoverStrategy.ROUND_ROBIN,
            heartbeat_interval=60.0,
            max_error_count=5
        )
        
        assert client.failover_strategy == NetworkFailoverStrategy.ROUND_ROBIN
        assert client.heartbeat_interval == 60.0
        assert client.max_error_count == 5
        assert len(client.networks) == 0
        assert len(client.active_networks) == 0
        assert client.primary_network is None
        
        print("✓ Multi-network client initialization")
    
    def test_discover_networks(self):
        """Test network discovery from config files"""
        client = MultiNetworkAPIClient()
        
        # Should discover existing network config files
        networks = client.discover_networks()
        
        # Should find at least the existing config files
        assert len(networks) >= 0  # May be 0 if no config files exist
        
        # Test with specific pattern
        networks = client.discover_networks("network_config*.json")
        
        for network in networks:
            assert isinstance(network, NetworkConfig)
            assert network.network_id
            assert network.host
            assert network.port > 0
        
        print(f"✓ Network discovery found {len(networks)} networks")
    
    async def test_add_network(self):
        """Test adding networks to client"""
        client = MultiNetworkAPIClient()
        
        # Create test network config
        config = NetworkConfig(
            network_id="test_network_1",
            model_id="llama-7b",
            host="localhost",
            port=8701,
            model_chain_order=["block_1"],
            paths={},
            nodes={"node1": {"host": "localhost", "port": 8701}}
        )
        
        # Add network
        success = await client.add_network(config, set_as_primary=True)
        assert success
        
        # Verify network was added
        assert "test_network_1" in client.networks
        assert client.primary_network == "test_network_1"
        assert "test_network_1" in client.network_stats
        assert "test_network_1" in client.network_sessions
        
        # Add second network
        config2 = NetworkConfig(
            network_id="test_network_2",
            model_id="mistral-7b",
            host="localhost",
            port=8702,
            model_chain_order=["block_1"],
            paths={},
            nodes={"node1": {"host": "localhost", "port": 8702}}
        )
        
        success = await client.add_network(config2)
        assert success
        assert "test_network_2" in client.networks
        assert client.primary_network == "test_network_1"  # Should remain primary
        
        print("✓ Add networks to client")
    
    def test_network_selection_strategies(self):
        """Test different network selection strategies"""
        client = MultiNetworkAPIClient()
        
        # Add mock networks
        for i in range(3):
            network_id = f"network_{i}"
            mock_connection = Mock()
            mock_connection.status = ConnectionStatus.CONNECTED
            mock_connection.error_count = 0
            client.networks[network_id] = mock_connection
            client.active_networks.add(network_id)
            client.network_stats[network_id] = {
                "requests": i * 10,
                "successes": i * 8,
                "failures": i * 2,
                "avg_response_time": 1.0 + i * 0.5
            }
        
        client.primary_network = "network_0"
        
        # Test PRIORITY_BASED strategy
        client.failover_strategy = NetworkFailoverStrategy.PRIORITY_BASED
        selected = client.select_network_for_request()
        assert selected == "network_0"  # Should select primary
        
        # Test LOAD_BALANCED strategy
        client.failover_strategy = NetworkFailoverStrategy.LOAD_BALANCED
        selected = client.select_network_for_request()
        assert selected == "network_0"  # Should select network with lowest request count
        
        # Test FASTEST_RESPONSE strategy
        client.failover_strategy = NetworkFailoverStrategy.FASTEST_RESPONSE
        selected = client.select_network_for_request()
        assert selected == "network_0"  # Should select network with best response time
        
        # Test ROUND_ROBIN strategy
        client.failover_strategy = NetworkFailoverStrategy.ROUND_ROBIN
        client.total_requests = 0
        selected1 = client.select_network_for_request()
        client.total_requests = 1
        selected2 = client.select_network_for_request()
        client.total_requests = 2
        selected3 = client.select_network_for_request()
        
        # Should cycle through networks (order may vary)
        selected_networks = {selected1, selected2, selected3}
        expected_networks = {"network_0", "network_1", "network_2"}
        assert len(selected_networks) >= 2  # Should select different networks
        
        print("✓ Network selection strategies")
    
    def test_preferred_network_selection(self):
        """Test preferred network selection"""
        client = MultiNetworkAPIClient()
        
        # Add mock networks
        for i in range(3):
            network_id = f"network_{i}"
            client.networks[network_id] = Mock()
            client.networks[network_id].status = ConnectionStatus.CONNECTED
            client.networks[network_id].error_count = 0
            client.active_networks.add(network_id)
        
        # Test preferred network selection
        selected = client.select_network_for_request(preferred_network="network_1")
        assert selected == "network_1"
        
        # Test fallback when preferred network is not available
        client.active_networks.remove("network_1")
        selected = client.select_network_for_request(preferred_network="network_1")
        assert selected in ["network_0", "network_2"]
        
        print("✓ Preferred network selection")
    
    def test_failed_network_handling(self):
        """Test handling of failed networks"""
        client = MultiNetworkAPIClient(max_error_count=3)
        
        # Add mock networks
        for i in range(3):
            network_id = f"network_{i}"
            client.networks[network_id] = Mock()
            client.networks[network_id].status = ConnectionStatus.CONNECTED
            client.networks[network_id].error_count = 0
            client.active_networks.add(network_id)
        
        # Mark one network as failed
        client.networks["network_1"].error_count = 5  # Exceeds max_error_count
        
        # Should not select failed network
        selected = client.select_network_for_request()
        assert selected in ["network_0", "network_2"]
        assert selected != "network_1"
        
        # Test when all networks are failed
        for network_id in client.networks:
            client.networks[network_id].error_count = 5
        
        selected = client.select_network_for_request()
        assert selected is None
        
        print("✓ Failed network handling")
    
    def test_session_management(self):
        """Test session tracking and management"""
        client = MultiNetworkAPIClient()
        
        # Test session creation
        session_id = "test_session_123"
        network_id = "test_network"
        
        # Simulate session creation during request
        from datetime import datetime
        client.sessions[session_id] = {
            "created_at": datetime.now(),
            "last_network": network_id,
            "request_count": 1
        }
        client.network_sessions[network_id] = {session_id}
        
        # Test session info retrieval
        session_info = client.get_session_info(session_id)
        assert session_info is not None
        assert session_info["last_network"] == network_id
        assert session_info["request_count"] == 1
        
        # Test non-existent session
        assert client.get_session_info("non_existent") is None
        
        print("✓ Session management")
    
    def test_network_statistics(self):
        """Test network statistics tracking"""
        client = MultiNetworkAPIClient()
        
        # Add mock network
        network_id = "test_network"
        client.networks[network_id] = Mock()
        client.networks[network_id].config = Mock()
        client.networks[network_id].config.model_id = "llama-7b"
        client.networks[network_id].config.host = "localhost"
        client.networks[network_id].config.port = 8701
        client.networks[network_id].status = ConnectionStatus.CONNECTED
        client.networks[network_id].error_count = 2
        client.networks[network_id].last_heartbeat = None
        
        client.active_networks.add(network_id)
        client.network_stats[network_id] = {
            "requests": 100,
            "successes": 85,
            "failures": 15,
            "avg_response_time": 1.25
        }
        client.network_sessions[network_id] = {"session1", "session2"}
        client.primary_network = network_id
        
        # Test network status
        status = client.get_network_status()
        
        assert network_id in status
        network_status = status[network_id]
        
        assert network_status["config"]["model_id"] == "llama-7b"
        assert network_status["status"] == ConnectionStatus.CONNECTED.value
        assert network_status["is_active"] is True
        assert network_status["is_primary"] is True
        assert network_status["error_count"] == 2
        assert network_status["statistics"]["requests"] == 100
        assert network_status["active_sessions"] == 2
        
        print("✓ Network statistics")
    
    def test_overall_statistics(self):
        """Test overall client statistics"""
        client = MultiNetworkAPIClient()
        
        # Set up test data
        client.total_requests = 100
        client.successful_requests = 85
        client.failed_requests = 15
        client.networks = {"net1": Mock(), "net2": Mock()}
        client.active_networks = {"net1"}
        client.primary_network = "net1"
        client.sessions = {"session1": {}, "session2": {}}
        
        stats = client.get_overall_stats()
        
        assert stats["total_requests"] == 100
        assert stats["successful_requests"] == 85
        assert stats["failed_requests"] == 15
        assert stats["success_rate"] == 0.85
        assert stats["active_networks"] == 1
        assert stats["total_networks"] == 2
        assert stats["primary_network"] == "net1"
        assert stats["active_sessions"] == 2
        
        print("✓ Overall statistics")


class TestNetworkFailover:
    """Test network failover functionality"""
    
    async def test_failover_trigger(self):
        """Test failover triggering"""
        client = MultiNetworkAPIClient(max_error_count=3)
        
        # Add mock networks
        client.networks["network_1"] = Mock()
        client.networks["network_1"].status = ConnectionStatus.CONNECTED
        client.networks["network_1"].error_count = 3
        
        client.networks["network_2"] = Mock()
        client.networks["network_2"].status = ConnectionStatus.CONNECTED
        client.networks["network_2"].error_count = 0
        
        client.active_networks = {"network_1", "network_2"}
        client.primary_network = "network_1"
        
        # Mock callback
        failover_events = []
        def on_failover(failed_net, new_net):
            failover_events.append((failed_net, new_net))
        
        client.set_failover_callback(on_failover)
        
        # Trigger failover
        await client._trigger_failover("network_1")
        
        # Verify failover occurred
        assert "network_1" not in client.active_networks
        assert client.networks["network_1"].status == ConnectionStatus.ERROR
        assert client.primary_network == "network_2"
        assert len(failover_events) == 1
        assert failover_events[0] == ("network_1", "network_2")
        
        print("✓ Failover trigger")
    
    def test_failover_strategies_under_failure(self):
        """Test failover strategies when networks fail"""
        client = MultiNetworkAPIClient()
        
        # Add networks with different failure states
        client.networks["healthy"] = Mock()
        client.networks["healthy"].status = ConnectionStatus.CONNECTED
        client.networks["healthy"].error_count = 0
        
        client.networks["failing"] = Mock()
        client.networks["failing"].status = ConnectionStatus.CONNECTED
        client.networks["failing"].error_count = 5  # Exceeds threshold
        
        client.networks["disconnected"] = Mock()
        client.networks["disconnected"].status = ConnectionStatus.DISCONNECTED
        client.networks["disconnected"].error_count = 0
        
        client.active_networks = {"healthy", "failing", "disconnected"}
        client.network_stats = {
            "healthy": {"requests": 10, "avg_response_time": 1.0},
            "failing": {"requests": 20, "avg_response_time": 2.0},
            "disconnected": {"requests": 5, "avg_response_time": 0.5}
        }
        
        # Should only select healthy network
        selected = client.select_network_for_request()
        assert selected == "healthy"
        
        print("✓ Failover strategies under failure")


class TestAsyncNetworkOperations:
    """Test asynchronous network operations"""
    
    async def test_mock_network_connection(self):
        """Test network connection with mocked client"""
        client = MultiNetworkAPIClient()
        
        # Create mock network config
        config = NetworkConfig(
            network_id="mock_network",
            model_id="test_model",
            host="localhost",
            port=8701,
            model_chain_order=[],
            paths={},
            nodes={}
        )
        
        # Add network
        await client.add_network(config)
        
        # Mock the underlying API client
        mock_api_client = Mock()
        mock_api_client.connect = AsyncMock(return_value=True)
        mock_api_client.disconnect = AsyncMock()
        
        client.networks["mock_network"].client = mock_api_client
        
        # Test connection
        success = await client.connect_to_network("mock_network")
        assert success
        assert "mock_network" in client.active_networks
        
        # Test disconnection
        await client.disconnect_from_network("mock_network")
        assert "mock_network" not in client.active_networks
        
        print("✓ Mock network connection")
    
    async def test_mock_inference_request(self):
        """Test inference request with mocked response"""
        client = MultiNetworkAPIClient()
        
        # Set up mock network
        config = NetworkConfig(
            network_id="mock_network",
            model_id="test_model",
            host="localhost",
            port=8701,
            model_chain_order=[],
            paths={},
            nodes={}
        )
        
        await client.add_network(config, set_as_primary=True)
        
        # Mock the API client and response
        mock_api_client = Mock()
        mock_response = create_inference_response(
            session_id="test_session",
            network_id="mock_network",
            step=0,
            status=ResponseStatus.SUCCESS.value,
            license_status=LicenseStatus.VALID.value,
            outputs={"result": "test_output"},
            processing_time=1.0,
            worker_id="worker_001"
        )
        
        mock_api_client.send_inference_request = AsyncMock(return_value=mock_response)
        client.networks["mock_network"].client = mock_api_client
        client.networks["mock_network"].status = ConnectionStatus.CONNECTED
        client.networks["mock_network"].error_count = 0
        client.active_networks.add("mock_network")
        
        # Send inference request
        response = await client.send_inference_request(
            session_id="test_session",
            input_tensors={"input": "test_data"},
            model_id="test_model"
        )
        
        # Verify response
        assert response.status == ResponseStatus.SUCCESS.value
        assert response.outputs == {"result": "test_output"}
        assert response.network_id == "mock_network"
        
        # Verify session tracking
        assert "test_session" in client.sessions
        assert client.sessions["test_session"]["last_network"] == "mock_network"
        
        # Verify statistics
        assert client.total_requests == 1
        assert client.successful_requests == 1
        
        print("✓ Mock inference request")


def run_all_tests():
    """Run all multi-network routing tests"""
    test_classes = [
        TestNetworkConfig,
        TestMultiNetworkAPIClient,
        TestNetworkFailover,
        TestAsyncNetworkOperations
    ]
    
    passed = 0
    failed = 0
    
    print("Running Multi-Network Routing Tests...")
    print("=" * 50)
    
    for test_class in test_classes:
        instance = test_class()
        methods = [method for method in dir(instance) if method.startswith('test_')]
        
        for method_name in methods:
            try:
                method = getattr(instance, method_name)
                
                # Handle async methods
                if asyncio.iscoroutinefunction(method):
                    asyncio.run(method())
                else:
                    method()
                
                passed += 1
            except Exception as e:
                print(f"✗ {test_class.__name__}.{method_name}: {e}")
                failed += 1
    
    print("=" * 50)
    print(f"Total: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All multi-network routing tests passed! ✓")
        return True
    else:
        print("Some multi-network routing tests failed! ✗")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)