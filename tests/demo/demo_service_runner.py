"""
Demonstration of Multi-Network Service Runner
Shows how to use the enhanced service runner for managing multiple networks
"""

import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from core.service_runner import MultiNetworkServiceRunner, ServiceStatus
from api_client import NetworkConfig


def demo_service_runner_overview():
    """Demonstrate service runner overview and capabilities"""
    print("=== Multi-Network Service Runner Overview ===")
    print()
    print("The Multi-Network Service Runner provides:")
    print("• Simultaneous management of multiple network configurations")
    print("• License-based network limits and validation")
    print("• Automatic service health monitoring and recovery")
    print("• Heartbeat monitoring for network connectivity")
    print("• Graceful startup and shutdown of all services")
    print("• Comprehensive status reporting and statistics")
    print("• Resource allocation based on subscription tiers")
    print()


async def demo_service_configuration():
    """Demonstrate service configuration and network discovery"""
    print("=== Service Configuration Demo ===")
    
    # Create temporary network configurations for demonstration
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create sample network configurations
        network_configs = [
            {
                "network_id": "llama_production",
                "model_id": "llama3_1_8b_fp16",
                "nodes": {"primary": {"host": "localhost", "port": 8701}},
                "model_chain_order": ["block_1", "block_2", "block_3"],
                "paths": {"model_dir": "/models/llama"}
            },
            {
                "network_id": "mistral_development",
                "model_id": "mistral_7b_int4",
                "nodes": {"primary": {"host": "localhost", "port": 8702}},
                "model_chain_order": ["block_1", "block_2"],
                "paths": {"model_dir": "/models/mistral"}
            },
            {
                "network_id": "backup_network",
                "model_id": "llama_7b_base",
                "nodes": {"primary": {"host": "localhost", "port": 8703}},
                "model_chain_order": ["block_1"],
                "paths": {"model_dir": "/models/backup"}
            }
        ]
        
        # Write configuration files
        config_files = []
        for i, config in enumerate(network_configs):
            config_path = Path(temp_dir) / f"demo_network_{i}.json"
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            config_files.append(config_path)
            print(f"Created config: {config['network_id']} ({config['model_id']})")
        
        # Create service runner
        runner = MultiNetworkServiceRunner(
            config_pattern=str(Path(temp_dir) / "demo_network_*.json"),
            max_networks=3,
            heartbeat_interval=30.0,
            health_check_interval=60.0
        )
        
        # Discover networks
        discovered = runner.discover_network_configs()
        print(f"\nDiscovered {len(discovered)} network configurations:")
        for config in discovered:
            print(f"  - {config.network_id}: {config.model_id} @ {config.host}:{config.port}")
        
        print()
        return runner


async def demo_license_integration():
    """Demonstrate license integration and network limits"""
    print("=== License Integration Demo ===")
    
    # Create service runner (will use default license handling)
    runner = MultiNetworkServiceRunner(max_networks=2)
    
    print(f"License Plan: {runner.current_license.plan.value if runner.current_license else 'None'}")
    print(f"Maximum Networks: {runner.max_networks}")
    
    # Test license validation for different scenarios
    test_configs = [
        NetworkConfig("allowed_network", "llama-7b", "localhost", 8701, [], {}, {}),
        NetworkConfig("premium_network", "gpt4", "localhost", 8702, [], {}, {}),
        NetworkConfig("enterprise_network", "custom_model", "localhost", 8703, [], {}, {})
    ]
    
    print("\nLicense validation results:")
    for config in test_configs:
        is_valid = runner.validate_network_license(config)
        print(f"  {config.network_id} ({config.model_id}): {'✓ Allowed' if is_valid else '✗ Denied'}")
    
    print()


async def demo_service_lifecycle():
    """Demonstrate complete service lifecycle"""
    print("=== Service Lifecycle Demo ===")
    
    # Create temporary config for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        config_data = {
            "network_id": "demo_service",
            "model_id": "demo_model",
            "nodes": {"primary": {"host": "localhost", "port": 8701}},
            "model_chain_order": ["block_1"],
            "paths": {"model_dir": "/demo/models"}
        }
        
        config_path = Path(temp_dir) / "demo_service.json"
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        # Create service runner
        runner = MultiNetworkServiceRunner(
            config_pattern=str(Path(temp_dir) / "demo_service*.json"),
            max_networks=1
        )
        
        print("1. Starting service runner...")
        success = await runner.start()
        print(f"   Service started: {'✓' if success else '✗'}")
        
        if success:
            print(f"   Service status: {runner.service_status.value}")
            print(f"   Running networks: {len([n for n in runner.networks.values() if n.status == ServiceStatus.RUNNING])}")
            
            # Get detailed status
            status = runner.get_service_status()
            print(f"   Total requests: {status['total_requests']}")
            print(f"   Total errors: {status['total_errors']}")
            
            # Wait a bit to simulate running
            print("2. Service running... (simulating operation)")
            await asyncio.sleep(1)
            
            # Show network details
            print("3. Network status:")
            for network_id, network_info in status['networks'].items():
                print(f"   {network_id}: {network_info['status']} ({network_info['model_id']})")
            
            print("4. Shutting down service...")
            await runner.shutdown()
            print(f"   Service status: {runner.service_status.value}")
        
        print()


async def demo_network_management():
    """Demonstrate individual network management"""
    print("=== Network Management Demo ===")
    
    runner = MultiNetworkServiceRunner(max_networks=3)
    
    # Create test network configurations
    test_networks = [
        NetworkConfig("network_1", "model_1", "localhost", 8701, [], {}, {}),
        NetworkConfig("network_2", "model_2", "localhost", 8702, [], {}, {}),
        NetworkConfig("network_3", "model_3", "localhost", 8703, [], {}, {})
    ]
    
    print("Starting individual networks:")
    for config in test_networks:
        success = await runner.start_network_service(config)
        print(f"  {config.network_id}: {'✓ Started' if success else '✗ Failed'}")
    
    print(f"\nActive networks: {len(runner.networks)}")
    
    # Test network restart
    print("\nRestarting network_2...")
    restart_success = await runner.restart_network_service("network_2")
    print(f"Restart result: {'✓ Success' if restart_success else '✗ Failed'}")
    
    # Test stopping individual network
    print("\nStopping network_3...")
    stop_success = await runner.stop_network_service("network_3")
    print(f"Stop result: {'✓ Success' if stop_success else '✗ Failed'}")
    
    print(f"Remaining networks: {len([n for n in runner.networks.values() if n.status == ServiceStatus.RUNNING])}")
    
    # Clean up
    await runner.stop_all_networks()
    print()


async def demo_monitoring_and_health():
    """Demonstrate monitoring and health features"""
    print("=== Monitoring and Health Demo ===")
    
    runner = MultiNetworkServiceRunner(
        heartbeat_interval=5.0,  # Fast for demo
        health_check_interval=10.0
    )
    
    # Add mock network
    config = NetworkConfig("monitored_network", "test_model", "localhost", 8701, [], {}, {})
    await runner.start_network_service(config)
    
    print("Network monitoring features:")
    print("• Heartbeat monitoring every 5 seconds")
    print("• Health checks every 10 seconds")
    print("• Automatic restart on failure")
    print("• License expiry monitoring")
    print("• Error count tracking")
    
    # Simulate some network activity
    network_service = runner.networks["monitored_network"]
    network_service.request_count = 150
    network_service.add_error("Simulated timeout error")
    network_service.add_error("Simulated connection error")
    
    # Get monitoring status
    status = runner.get_service_status()
    network_status = status['networks']['monitored_network']
    
    print(f"\nCurrent network status:")
    print(f"  Status: {network_status['status']}")
    print(f"  Requests: {network_status['request_count']}")
    print(f"  Errors: {network_status['error_count']}")
    print(f"  Recent errors: {len(network_status['recent_errors'])}")
    
    # Clean up
    await runner.stop_all_networks()
    print()


async def demo_error_handling():
    """Demonstrate error handling and recovery"""
    print("=== Error Handling and Recovery Demo ===")
    
    runner = MultiNetworkServiceRunner(max_networks=2)
    
    # Test various error scenarios
    print("Testing error scenarios:")
    
    # 1. Invalid network configuration
    print("1. Invalid network configuration:")
    invalid_config = NetworkConfig("", "", "", 0, [], {}, {})  # Invalid config
    success = await runner.start_network_service(invalid_config)
    print(f"   Result: {'✓ Handled' if not success else '✗ Unexpected success'}")
    
    # 2. Duplicate network ID
    print("2. Duplicate network ID:")
    config1 = NetworkConfig("duplicate", "model1", "localhost", 8701, [], {}, {})
    config2 = NetworkConfig("duplicate", "model2", "localhost", 8702, [], {}, {})
    
    await runner.start_network_service(config1)
    success = await runner.start_network_service(config2)
    print(f"   Result: {'✓ Handled' if not success else '✗ Unexpected success'}")
    
    # 3. Network limit exceeded
    print("3. Network limit exceeded:")
    runner.max_networks = 1  # Set low limit
    config3 = NetworkConfig("excess", "model3", "localhost", 8703, [], {}, {})
    success = await runner.start_network_service(config3)
    print(f"   Result: {'✓ Handled' if not success else '✗ Unexpected success'}")
    
    # Show error tracking
    status = runner.get_service_status()
    total_errors = status['total_errors']
    print(f"\nTotal errors tracked: {total_errors}")
    
    # Clean up
    await runner.stop_all_networks()
    print()


async def demo_complete_workflow():
    """Demonstrate complete multi-network workflow"""
    print("=== Complete Multi-Network Workflow Demo ===")
    
    # Create comprehensive demo environment
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple network configurations
        networks = [
            {"id": "production_llama", "model": "llama3_1_8b_fp16", "port": 8701},
            {"id": "development_mistral", "model": "mistral_7b_int4", "port": 8702},
            {"id": "testing_backup", "model": "llama_7b_base", "port": 8703}
        ]
        
        # Write config files
        for network in networks:
            config_data = {
                "network_id": network["id"],
                "model_id": network["model"],
                "nodes": {"primary": {"host": "localhost", "port": network["port"]}},
                "model_chain_order": ["block_1", "block_2"],
                "paths": {"model_dir": f"/models/{network['model']}"}
            }
            
            config_path = Path(temp_dir) / f"{network['id']}.json"
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
        
        print("Step 1: Initialize service runner")
        runner = MultiNetworkServiceRunner(
            config_pattern=str(Path(temp_dir) / "*.json"),
            max_networks=3,
            heartbeat_interval=30.0
        )
        
        print("Step 2: Start all networks")
        success = await runner.start()
        print(f"Service started: {'✓' if success else '✗'}")
        
        if success:
            print("Step 3: Monitor service status")
            status = runner.get_service_status()
            print(f"  Running networks: {status['running_networks']}/{status['total_networks']}")
            print(f"  License plan: {status['license_plan']}")
            print(f"  Max networks: {status['max_networks']}")
            
            print("Step 4: Network details")
            for network_id, network_info in status['networks'].items():
                print(f"  {network_id}:")
                print(f"    Status: {network_info['status']}")
                print(f"    Model: {network_info['model_id']}")
                print(f"    Endpoint: {network_info['host']}:{network_info['port']}")
            
            print("Step 5: Simulate some activity")
            # Simulate network activity
            for network_service in runner.networks.values():
                network_service.request_count += 50
                if network_service.config.network_id == "development_mistral":
                    network_service.add_error("Development environment timeout")
            
            # Get updated status
            updated_status = runner.get_service_status()
            print(f"  Total requests: {updated_status['total_requests']}")
            print(f"  Total errors: {updated_status['total_errors']}")
            
            print("Step 6: Graceful shutdown")
            await runner.shutdown()
            print(f"  Final status: {runner.service_status.value}")
        
        print()


async def main():
    """Run all service runner demonstrations"""
    print("TikTrue Multi-Network Service Runner Demonstration")
    print("=" * 60)
    print()
    
    # Run all demonstrations
    demo_service_runner_overview()
    await demo_service_configuration()
    await demo_license_integration()
    await demo_service_lifecycle()
    await demo_network_management()
    await demo_monitoring_and_health()
    await demo_error_handling()
    await demo_complete_workflow()
    
    print("=" * 60)
    print("Multi-Network Service Runner demonstration completed successfully!")
    print()
    print("Key Features Demonstrated:")
    print("✓ Multi-network configuration discovery and management")
    print("✓ License-based network limits and validation")
    print("✓ Complete service lifecycle (start, monitor, shutdown)")
    print("✓ Individual network management (start, stop, restart)")
    print("✓ Health monitoring and heartbeat checks")
    print("✓ Error handling and recovery mechanisms")
    print("✓ Comprehensive status reporting and statistics")
    print("✓ Resource allocation based on subscription tiers")
    print()
    print("The Multi-Network Service Runner provides:")
    print("• Enterprise-grade service management")
    print("• High availability through monitoring and recovery")
    print("• License-aware resource allocation")
    print("• Scalable multi-network architecture")
    print("• Comprehensive logging and error tracking")
    print("• Graceful startup and shutdown procedures")


if __name__ == "__main__":
    asyncio.run(main())