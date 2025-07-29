"""
Demonstration of Multi-Network Routing Capabilities
Shows how to use the enhanced API client with multiple networks, failover, and routing
"""

import asyncio
import json
import time
from typing import Dict, Any

from api_client import (
    MultiNetworkAPIClient, NetworkConfig, NetworkFailoverStrategy, 
    ConnectionStatus, LicenseAwareAPIClient
)
from core.protocol_spec import (
    InferenceRequest, InferenceResponse, ResponseStatus, LicenseStatus,
    create_inference_request, create_inference_response
)


def demo_network_discovery():
    """Demonstrate network discovery from configuration files"""
    print("=== Network Discovery Demo ===")
    
    client = MultiNetworkAPIClient()
    
    # Discover networks from config files
    networks = client.discover_networks("network_config*.json")
    
    print(f"Discovered {len(networks)} networks:")
    for network in networks:
        print(f"  - {network.network_id}: {network.model_id} @ {network.host}:{network.port}")
    
    print()
    return networks


async def demo_multi_network_setup():
    """Demonstrate setting up multiple networks"""
    print("=== Multi-Network Setup Demo ===")
    
    client = MultiNetworkAPIClient(
        failover_strategy=NetworkFailoverStrategy.PRIORITY_BASED,
        heartbeat_interval=30.0,
        max_error_count=3
    )
    
    # Create sample network configurations
    networks = [
        NetworkConfig(
            network_id="llama_network",
            model_id="llama-7b-chat",
            host="localhost",
            port=8701,
            model_chain_order=["block_1", "block_2", "block_3"],
            paths={"model_dir": "/models/llama"},
            nodes={"node1": {"host": "localhost", "port": 8701}}
        ),
        NetworkConfig(
            network_id="mistral_network",
            model_id="mistral-7b-instruct",
            host="localhost",
            port=8702,
            model_chain_order=["block_1", "block_2", "block_3"],
            paths={"model_dir": "/models/mistral"},
            nodes={"node1": {"host": "localhost", "port": 8702}}
        ),
        NetworkConfig(
            network_id="backup_network",
            model_id="llama-7b-base",
            host="localhost",
            port=8703,
            model_chain_order=["block_1", "block_2"],
            paths={"model_dir": "/models/backup"},
            nodes={"node1": {"host": "localhost", "port": 8703}}
        )
    ]
    
    # Add networks to client
    for i, network in enumerate(networks):
        success = await client.add_network(network, set_as_primary=(i == 0))
        print(f"Added network {network.network_id}: {'✓' if success else '✗'}")
    
    print(f"Primary network: {client.primary_network}")
    print(f"Total networks: {len(client.networks)}")
    
    print()
    return client


def demo_failover_strategies():
    """Demonstrate different failover strategies"""
    print("=== Failover Strategies Demo ===")
    
    strategies = [
        NetworkFailoverStrategy.PRIORITY_BASED,
        NetworkFailoverStrategy.ROUND_ROBIN,
        NetworkFailoverStrategy.LOAD_BALANCED,
        NetworkFailoverStrategy.FASTEST_RESPONSE
    ]
    
    for strategy in strategies:
        client = MultiNetworkAPIClient(failover_strategy=strategy)
        
        # Add mock networks with different characteristics
        for i in range(3):
            network_id = f"network_{i}"
            client.networks[network_id] = type('MockConnection', (), {
                'status': ConnectionStatus.CONNECTED,
                'error_count': 0
            })()
            client.active_networks.add(network_id)
            client.network_stats[network_id] = {
                "requests": i * 10,
                "successes": i * 8,
                "failures": i * 2,
                "avg_response_time": 1.0 + i * 0.3
            }
        
        client.primary_network = "network_0"
        
        # Test network selection
        selected = client.select_network_for_request()
        print(f"{strategy.value}: Selected {selected}")
    
    print()


async def demo_session_management():
    """Demonstrate session management across networks"""
    print("=== Session Management Demo ===")
    
    client = MultiNetworkAPIClient()
    
    # Add mock networks
    for i in range(2):
        network_id = f"session_network_{i}"
        client.networks[network_id] = type('MockConnection', (), {
            'status': ConnectionStatus.CONNECTED,
            'error_count': 0
        })()
        client.active_networks.add(network_id)
        client.network_stats[network_id] = {"requests": 0, "successes": 0, "failures": 0, "avg_response_time": 1.0}
        client.network_sessions[network_id] = set()
    
    client.primary_network = "session_network_0"
    
    # Simulate session creation and tracking
    sessions = ["user_session_1", "user_session_2", "user_session_3"]
    
    for session_id in sessions:
        # Simulate session assignment to networks
        selected_network = client.select_network_for_request()
        
        # Track session
        client.sessions[session_id] = {
            "created_at": time.time(),
            "last_network": selected_network,
            "request_count": 1
        }
        client.network_sessions[selected_network].add(session_id)
        
        print(f"Session {session_id} assigned to {selected_network}")
    
    # Show session distribution
    for network_id in client.networks:
        session_count = len(client.network_sessions.get(network_id, set()))
        print(f"Network {network_id}: {session_count} active sessions")
    
    print()


def demo_network_statistics():
    """Demonstrate network statistics and monitoring"""
    print("=== Network Statistics Demo ===")
    
    client = MultiNetworkAPIClient()
    
    # Add mock networks with different performance characteristics
    network_configs = [
        ("high_performance", {"requests": 1000, "successes": 950, "failures": 50, "avg_response_time": 0.8}),
        ("medium_performance", {"requests": 800, "successes": 720, "failures": 80, "avg_response_time": 1.2}),
        ("low_performance", {"requests": 500, "successes": 400, "failures": 100, "avg_response_time": 2.1})
    ]
    
    for network_id, stats in network_configs:
        # Create mock network
        mock_config = type('MockConfig', (), {
            'model_id': f'model_{network_id}',
            'host': 'localhost',
            'port': 8700 + len(client.networks)
        })()
        
        client.networks[network_id] = type('MockConnection', (), {
            'config': mock_config,
            'status': ConnectionStatus.CONNECTED,
            'error_count': 0,
            'last_heartbeat': None
        })()
        
        client.active_networks.add(network_id)
        client.network_stats[network_id] = stats
        client.network_sessions[network_id] = {f"session_{i}" for i in range(stats["requests"] // 100)}
    
    client.primary_network = "high_performance"
    client.total_requests = 2300
    client.successful_requests = 2070
    client.failed_requests = 230
    
    # Display network status
    network_status = client.get_network_status()
    
    print("Network Status:")
    for network_id, status in network_status.items():
        print(f"\n{network_id}:")
        print(f"  Model: {status['config']['model_id']}")
        print(f"  Status: {status['status']}")
        print(f"  Primary: {'Yes' if status['is_primary'] else 'No'}")
        print(f"  Requests: {status['statistics']['requests']}")
        print(f"  Success Rate: {status['statistics']['successes'] / status['statistics']['requests']:.2%}")
        print(f"  Avg Response Time: {status['statistics']['avg_response_time']:.2f}s")
        print(f"  Active Sessions: {status['active_sessions']}")
    
    # Display overall statistics
    overall_stats = client.get_overall_stats()
    
    print(f"\nOverall Statistics:")
    print(f"  Total Requests: {overall_stats['total_requests']}")
    print(f"  Success Rate: {overall_stats['success_rate']:.2%}")
    print(f"  Active Networks: {overall_stats['active_networks']}/{overall_stats['total_networks']}")
    print(f"  Primary Network: {overall_stats['primary_network']}")
    print(f"  Failover Strategy: {overall_stats['failover_strategy']}")
    print(f"  Active Sessions: {overall_stats['active_sessions']}")
    
    print()


async def demo_failover_simulation():
    """Demonstrate automatic failover when networks fail"""
    print("=== Failover Simulation Demo ===")
    
    client = MultiNetworkAPIClient(max_error_count=2)
    
    # Add mock networks
    networks = ["primary_net", "backup_net", "emergency_net"]
    for network_id in networks:
        client.networks[network_id] = type('MockConnection', (), {
            'status': ConnectionStatus.CONNECTED,
            'error_count': 0
        })()
        client.active_networks.add(network_id)
        client.network_stats[network_id] = {"requests": 0, "successes": 0, "failures": 0, "avg_response_time": 1.0}
    
    client.primary_network = "primary_net"
    
    # Set up callbacks to track failover events
    failover_events = []
    status_changes = []
    
    def on_failover(failed_net, new_net):
        failover_events.append(f"Failover: {failed_net} -> {new_net}")
    
    def on_status_change(network_id, status):
        status_changes.append(f"Status: {network_id} -> {status.value}")
    
    client.set_failover_callback(on_failover)
    client.set_network_status_callback(on_status_change)
    
    print(f"Initial primary network: {client.primary_network}")
    print(f"Active networks: {list(client.active_networks)}")
    
    # Simulate network failures
    print("\nSimulating primary network failure...")
    client.networks["primary_net"].error_count = 3  # Exceed threshold
    await client._trigger_failover("primary_net")
    
    print(f"New primary network: {client.primary_network}")
    print(f"Active networks: {list(client.active_networks)}")
    
    # Simulate another failure
    print("\nSimulating backup network failure...")
    if client.primary_network:
        client.networks[client.primary_network].error_count = 3
        await client._trigger_failover(client.primary_network)
    
    print(f"Final primary network: {client.primary_network}")
    print(f"Active networks: {list(client.active_networks)}")
    
    # Show events
    print("\nFailover Events:")
    for event in failover_events:
        print(f"  {event}")
    
    print("\nStatus Changes:")
    for change in status_changes:
        print(f"  {change}")
    
    print()


async def demo_request_routing():
    """Demonstrate request routing with network preferences"""
    print("=== Request Routing Demo ===")
    
    client = MultiNetworkAPIClient()
    
    # Add mock networks
    networks = {
        "fast_network": {"avg_response_time": 0.5, "model": "llama-7b-fast"},
        "accurate_network": {"avg_response_time": 1.5, "model": "llama-70b-accurate"},
        "backup_network": {"avg_response_time": 2.0, "model": "llama-7b-backup"}
    }
    
    for network_id, props in networks.items():
        client.networks[network_id] = type('MockConnection', (), {
            'status': ConnectionStatus.CONNECTED,
            'error_count': 0
        })()
        client.active_networks.add(network_id)
        client.network_stats[network_id] = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "avg_response_time": props["avg_response_time"]
        }
    
    client.primary_network = "fast_network"
    
    # Test different routing scenarios
    scenarios = [
        ("Default routing", None),
        ("Prefer fast network", "fast_network"),
        ("Prefer accurate network", "accurate_network"),
        ("Prefer unavailable network", "unavailable_network"),  # Should fallback
    ]
    
    for scenario_name, preferred_network in scenarios:
        selected = client.select_network_for_request(preferred_network)
        print(f"{scenario_name}: Selected {selected}")
        
        if selected:
            # Update stats to simulate request
            client.network_stats[selected]["requests"] += 1
    
    print("\nFinal network request counts:")
    for network_id in client.networks:
        count = client.network_stats[network_id]["requests"]
        print(f"  {network_id}: {count} requests")
    
    print()


async def demo_complete_workflow():
    """Demonstrate complete multi-network workflow"""
    print("=== Complete Multi-Network Workflow Demo ===")
    
    # Step 1: Initialize client with specific strategy
    client = MultiNetworkAPIClient(
        failover_strategy=NetworkFailoverStrategy.LOAD_BALANCED,
        heartbeat_interval=60.0,
        max_error_count=3
    )
    
    print("1. Initialized multi-network client")
    
    # Step 2: Discover and add networks
    discovered_networks = client.discover_networks()
    print(f"2. Discovered {len(discovered_networks)} networks")
    
    # Add discovered networks (or create mock ones for demo)
    if not discovered_networks:
        # Create mock networks for demonstration
        mock_networks = [
            NetworkConfig("demo_net_1", "llama-7b", "localhost", 8701, [], {}, {}),
            NetworkConfig("demo_net_2", "mistral-7b", "localhost", 8702, [], {}, {})
        ]
        
        for network in mock_networks:
            await client.add_network(network)
        
        print("2. Added mock networks for demonstration")
    
    # Step 3: Show initial status
    print("3. Initial network status:")
    status = client.get_network_status()
    for net_id in status:
        print(f"   {net_id}: {status[net_id]['status']}")
    
    # Step 4: Simulate some requests and show routing
    print("4. Simulating requests with different preferences:")
    
    request_scenarios = [
        ("General request", None),
        ("Prefer specific network", list(client.networks.keys())[0] if client.networks else None),
        ("Load balanced request", None),
    ]
    
    for scenario, preferred in request_scenarios:
        selected = client.select_network_for_request(preferred)
        print(f"   {scenario}: Routed to {selected}")
    
    # Step 5: Show final statistics
    print("5. Final statistics:")
    overall_stats = client.get_overall_stats()
    print(f"   Strategy: {overall_stats['failover_strategy']}")
    print(f"   Networks: {overall_stats['active_networks']}/{overall_stats['total_networks']}")
    print(f"   Primary: {overall_stats['primary_network']}")
    
    print()


async def main():
    """Run all multi-network routing demonstrations"""
    print("TikTrue Multi-Network Routing Capabilities Demonstration")
    print("=" * 65)
    print()
    
    # Run all demonstrations
    demo_network_discovery()
    await demo_multi_network_setup()
    demo_failover_strategies()
    await demo_session_management()
    demo_network_statistics()
    await demo_failover_simulation()
    await demo_request_routing()
    await demo_complete_workflow()
    
    print("=" * 65)
    print("Multi-network routing demonstration completed successfully!")
    print()
    print("Key Features Demonstrated:")
    print("✓ Network discovery from configuration files")
    print("✓ Multi-network client setup and management")
    print("✓ Multiple failover strategies (Priority, Round-Robin, Load-Balanced, Fastest)")
    print("✓ Session management across networks")
    print("✓ Network statistics and monitoring")
    print("✓ Automatic failover on network failures")
    print("✓ Request routing with network preferences")
    print("✓ Complete multi-network workflow")
    print()
    print("The multi-network routing system provides:")
    print("• High availability through automatic failover")
    print("• Load distribution across multiple networks")
    print("• Session persistence and tracking")
    print("• Comprehensive monitoring and statistics")
    print("• Flexible routing strategies")
    print("• License-aware network operations")


if __name__ == "__main__":
    asyncio.run(main())