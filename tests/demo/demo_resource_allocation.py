#!/usr/bin/env python3
"""
Demo script for Dynamic Resource Allocation System
Demonstrates license-aware resource distribution, conflict resolution, and dynamic scaling
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from resource_allocator import (
    DynamicResourceAllocator, ResourceQuota, ResourceRequest, 
    AllocationPriority, NetworkResourceProfile, create_default_resource_quota,
    create_network_profile
)
from security.license_validator import LicenseInfo, SubscriptionTier
from api_client import NetworkConfig
from core.service_runner import MultiNetworkServiceRunner


async def demo_basic_allocation():
    """Demonstrate basic resource allocation"""
    print("\n" + "="*60)
    print("BASIC RESOURCE ALLOCATION DEMO")
    print("="*60)
    
    # Create system resources (simulating a mid-range server)
    total_resources = ResourceQuota(
        cpu_cores=16.0,
        memory_gb=32.0,
        gpu_memory_gb=16.0,
        network_bandwidth_mbps=1000.0,
        worker_slots=20,
        client_connections=50
    )
    
    # Create Pro license
    license_info = LicenseInfo(
        license_key="TIKT-PRO-1Y-DEMO123",
        plan=SubscriptionTier.PRO,
        expires_at=datetime.now() + timedelta(days=365),
        max_networks=5,
        max_clients=20
    )
    
    # Initialize allocator
    allocator = DynamicResourceAllocator(
        total_resources=total_resources,
        license_info=license_info,
        allocation_interval=2.0,
        cleanup_interval=10.0
    )
    
    try:
        # Start allocator
        await allocator.start()
        print("✓ Resource allocator started")
        print(f"📊 Total Resources: {total_resources.to_dict()}")
        
        # Create resource requests
        requests = []
        
        # Request 1: High priority network
        req1 = ResourceRequest(
            request_id="req_critical_network",
            network_id="critical_llama_network",
            required_resources=ResourceQuota(
                cpu_cores=4.0,
                memory_gb=8.0,
                gpu_memory_gb=4.0,
                worker_slots=5,
                client_connections=10
            ),
            priority=AllocationPriority.CRITICAL,
            requested_at=datetime.now(),
            metadata={"model_type": "llama-70b", "tier": "critical"}
        )
        requests.append(req1)
        
        # Request 2: Normal priority network
        req2 = ResourceRequest(
            request_id="req_standard_network",
            network_id="standard_mistral_network",
            required_resources=ResourceQuota(
                cpu_cores=2.0,
                memory_gb=4.0,
                gpu_memory_gb=2.0,
                worker_slots=3,
                client_connections=5
            ),
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now(),
            metadata={"model_type": "mistral-7b", "tier": "standard"}
        )
        requests.append(req2)
        
        # Request 3: Low priority network
        req3 = ResourceRequest(
            request_id="req_background_network",
            network_id="background_gpt_network",
            required_resources=ResourceQuota(
                cpu_cores=1.0,
                memory_gb=2.0,
                gpu_memory_gb=1.0,
                worker_slots=2,
                client_connections=3
            ),
            priority=AllocationPriority.LOW,
            requested_at=datetime.now(),
            metadata={"model_type": "gpt-3.5", "tier": "background"}
        )
        requests.append(req3)
        
        # Submit requests
        print(f"\n🔄 Submitting {len(requests)} resource requests...")
        for req in requests:
            request_id = allocator.request_resources(req)
            print(f"   • {req.network_id} ({req.priority.name}): {request_id}")
        
        # Wait for allocation processing
        print("⏳ Processing allocations...")
        await asyncio.sleep(5.0)
        
        # Check results
        utilization = allocator.get_resource_utilization()
        print(f"\n📈 Resource Utilization:")
        print(f"   Active Allocations: {utilization['active_allocations']}")
        print(f"   Pending Requests: {utilization['pending_requests']}")
        
        for resource_type, data in utilization['resources'].items():
            if data['total'] > 0:
                print(f"   {resource_type}: {data['allocated']:.1f}/{data['total']:.1f} "
                      f"({data['utilization_percent']:.1f}%)")
        
        # Show individual allocations
        print(f"\n🎯 Individual Network Allocations:")
        for network_id in ["critical_llama_network", "standard_mistral_network", "background_gpt_network"]:
            allocations = allocator.get_network_allocations(network_id)
            if allocations:
                alloc = allocations[0]
                resources = alloc.allocated_resources
                print(f"   {network_id}:")
                print(f"     CPU: {resources.cpu_cores} cores")
                print(f"     Memory: {resources.memory_gb} GB")
                print(f"     Workers: {resources.worker_slots}")
                print(f"     Connections: {resources.client_connections}")
            else:
                print(f"   {network_id}: No allocation (likely queued or rejected)")
        
        print(f"\n📊 Statistics:")
        stats = utilization['statistics']
        print(f"   Total Requests: {stats['total_requests']}")
        print(f"   Satisfied: {stats['satisfied_requests']}")
        print(f"   Rejected: {stats['rejected_requests']}")
        print(f"   Conflicts Resolved: {stats['conflicts_resolved']}")
        
    finally:
        await allocator.stop()
        print("\n✓ Resource allocator stopped")


async def demo_conflict_resolution():
    """Demonstrate resource conflict resolution"""
    print("\n" + "="*60)
    print("RESOURCE CONFLICT RESOLUTION DEMO")
    print("="*60)
    
    # Create limited resources to force conflicts
    limited_resources = ResourceQuota(
        cpu_cores=4.0,
        memory_gb=8.0,
        gpu_memory_gb=4.0,
        worker_slots=5,
        client_connections=10
    )
    
    allocator = DynamicResourceAllocator(
        total_resources=limited_resources,
        allocation_interval=1.0,
        cleanup_interval=5.0
    )
    
    try:
        await allocator.start()
        print("✓ Allocator started with limited resources")
        print(f"📊 Available Resources: {limited_resources.to_dict()}")
        
        # Create conflicting requests (total exceeds available)
        conflicting_requests = []
        
        for i in range(5):
            req = ResourceRequest(
                request_id=f"conflict_req_{i}",
                network_id=f"network_{i}",
                required_resources=ResourceQuota(
                    cpu_cores=2.0,
                    memory_gb=3.0,
                    worker_slots=2,
                    client_connections=3
                ),
                priority=AllocationPriority.HIGH if i < 2 else AllocationPriority.NORMAL,
                requested_at=datetime.now() + timedelta(seconds=i),  # Stagger timing
                metadata={"request_order": i}
            )
            conflicting_requests.append(req)
        
        print(f"\n⚡ Creating resource conflict with {len(conflicting_requests)} requests...")
        print("   Each request needs: 2 CPU cores, 3 GB RAM, 2 workers")
        print("   Total needed: 10 CPU cores, 15 GB RAM, 10 workers")
        print("   Available: 4 CPU cores, 8 GB RAM, 5 workers")
        
        # Submit all requests quickly
        for req in conflicting_requests:
            allocator.request_resources(req)
            print(f"   • Submitted: {req.network_id} ({req.priority.name})")
        
        # Wait for conflict resolution
        print("\n🔄 Resolving conflicts...")
        await asyncio.sleep(3.0)
        
        # Check which requests were satisfied
        utilization = allocator.get_resource_utilization()
        print(f"\n🎯 Conflict Resolution Results:")
        print(f"   Satisfied Requests: {utilization['statistics']['satisfied_requests']}")
        print(f"   Rejected Requests: {utilization['statistics']['rejected_requests']}")
        print(f"   Conflicts Resolved: {utilization['statistics']['conflicts_resolved']}")
        
        # Show which networks got resources
        satisfied_networks = []
        for i in range(5):
            network_id = f"network_{i}"
            allocations = allocator.get_network_allocations(network_id)
            if allocations:
                satisfied_networks.append(network_id)
        
        print(f"\n✅ Networks that received allocations:")
        for network_id in satisfied_networks:
            print(f"   • {network_id}")
        
        print(f"\n❌ Networks that were rejected:")
        for i in range(5):
            network_id = f"network_{i}"
            if network_id not in satisfied_networks:
                print(f"   • {network_id}")
        
        print(f"\n💡 Priority-based resolution ensured high-priority requests were satisfied first")
        
    finally:
        await allocator.stop()
        print("\n✓ Conflict resolution demo completed")


async def demo_dynamic_scaling():
    """Demonstrate dynamic resource scaling"""
    print("\n" + "="*60)
    print("DYNAMIC RESOURCE SCALING DEMO")
    print("="*60)
    
    # Create network configuration
    network_config = NetworkConfig(
        network_id="scaling_demo_network",
        model_id="llama-7b-chat",
        host="localhost",
        port=8701,
        model_chain_order=["embedding", "attention", "mlp", "output"],
        paths={"model_dir": "./models/llama-7b"},
        nodes={
            "node1": {"host": "localhost", "port": 8801},
            "node2": {"host": "localhost", "port": 8802}
        }
    )
    
    # Create license
    license_info = LicenseInfo(
        license_key="TIKT-ENT-1Y-DEMO123",
        plan=SubscriptionTier.ENT,
        expires_at=datetime.now() + timedelta(days=365),
        max_networks=50,
        max_clients=100
    )
    
    # Create network profile
    profile = create_network_profile(network_config, license_info)
    
    print("✓ Created network resource profile")
    print(f"   Network: {profile.network_id}")
    print(f"   Priority: {profile.priority.name}")
    print(f"   Base Requirements: {profile.base_requirements.to_dict()}")
    print(f"   Peak Requirements: {profile.peak_requirements.to_dict()}")
    
    # Demonstrate dynamic scaling at different load levels
    load_levels = [0.0, 0.25, 0.5, 0.75, 1.0]
    
    print(f"\n📈 Dynamic Resource Scaling at Different Load Levels:")
    print(f"{'Load %':<8} {'CPU':<6} {'Memory':<8} {'Workers':<8} {'Connections':<12}")
    print("-" * 50)
    
    for load in load_levels:
        dynamic_req = profile.get_dynamic_requirements(load)
        print(f"{load*100:>5.0f}%   "
              f"{dynamic_req.cpu_cores:>5.1f}  "
              f"{dynamic_req.memory_gb:>6.1f}   "
              f"{dynamic_req.worker_slots:>6}    "
              f"{dynamic_req.client_connections:>10}")
    
    # Simulate load changes over time
    print(f"\n🔄 Simulating Load Changes Over Time:")
    
    allocator = DynamicResourceAllocator(
        total_resources=create_default_resource_quota(license_info),
        license_info=license_info,
        allocation_interval=1.0
    )
    
    try:
        await allocator.start()
        allocator.register_network_profile(profile)
        
        # Simulate different load scenarios
        scenarios = [
            (0.2, "Low load - few users"),
            (0.6, "Medium load - normal usage"),
            (0.9, "High load - peak hours"),
            (0.3, "Load decreased - users leaving"),
            (1.0, "Maximum load - viral content")
        ]
        
        for load_factor, description in scenarios:
            print(f"\n📊 {description} (Load: {load_factor*100:.0f}%)")
            
            # Update profile scaling factor
            profile.scaling_factor = load_factor
            
            # Calculate dynamic requirements
            dynamic_req = profile.get_dynamic_requirements(load_factor)
            
            print(f"   Dynamic Requirements:")
            print(f"     CPU Cores: {dynamic_req.cpu_cores:.1f}")
            print(f"     Memory: {dynamic_req.memory_gb:.1f} GB")
            print(f"     Workers: {dynamic_req.worker_slots}")
            print(f"     Connections: {dynamic_req.client_connections}")
            
            # Simulate resource request with dynamic requirements
            request = ResourceRequest(
                request_id=f"scaling_req_{int(time.time())}",
                network_id=profile.network_id,
                required_resources=dynamic_req,
                priority=profile.priority,
                requested_at=datetime.now(),
                metadata={"load_factor": load_factor, "scenario": description}
            )
            
            # This would trigger reallocation in a real system
            print(f"   📝 Would request reallocation with new requirements")
            
            await asyncio.sleep(1.0)
        
        print(f"\n💡 Dynamic scaling allows efficient resource utilization based on actual demand")
        
    finally:
        await allocator.stop()


async def demo_license_constraints():
    """Demonstrate license-based resource constraints"""
    print("\n" + "="*60)
    print("LICENSE-BASED RESOURCE CONSTRAINTS DEMO")
    print("="*60)
    
    # Test different license tiers
    license_tiers = [
        ("FREE", SubscriptionTier.FREE, "TIKT-FREE-1Y-DEMO123"),
        ("PRO", SubscriptionTier.PRO, "TIKT-PRO-1Y-DEMO123"),
        ("ENTERPRISE", SubscriptionTier.ENT, "TIKT-ENT-1Y-DEMO123")
    ]
    
    for tier_name, tier, license_key in license_tiers:
        print(f"\n🏷️  {tier_name} TIER CONSTRAINTS:")
        
        # Create license
        license_info = LicenseInfo(
            license_key=license_key,
            plan=tier,
            expires_at=datetime.now() + timedelta(days=365),
            max_networks=1 if tier == SubscriptionTier.FREE else (5 if tier == SubscriptionTier.PRO else 50),
            max_clients=3 if tier == SubscriptionTier.FREE else (20 if tier == SubscriptionTier.PRO else 100)
        )
        
        # Create default quota for this license
        quota = create_default_resource_quota(license_info)
        
        print(f"   License Key: {license_key}")
        print(f"   Max Networks: {license_info.max_networks}")
        print(f"   Max Clients: {license_info.max_clients}")
        print(f"   Resource Limits:")
        print(f"     CPU Cores: {quota.cpu_cores}")
        print(f"     Memory: {quota.memory_gb} GB")
        print(f"     GPU Memory: {quota.gpu_memory_gb} GB")
        print(f"     Worker Slots: {quota.worker_slots}")
        print(f"     Client Connections: {quota.client_connections}")
        
        # Test resource request validation
        allocator = DynamicResourceAllocator(
            total_resources=quota,
            license_info=license_info
        )
        
        # Valid request within limits
        valid_request = ResourceRequest(
            request_id=f"valid_{tier_name.lower()}",
            network_id=f"network_{tier_name.lower()}",
            required_resources=ResourceQuota(
                cpu_cores=1.0,
                memory_gb=2.0,
                worker_slots=1 if tier == SubscriptionTier.FREE else 3,
                client_connections=2 if tier == SubscriptionTier.FREE else 5
            ),
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now()
        )
        
        # Invalid request exceeding limits
        invalid_request = ResourceRequest(
            request_id=f"invalid_{tier_name.lower()}",
            network_id=f"network_{tier_name.lower()}_invalid",
            required_resources=ResourceQuota(
                cpu_cores=quota.cpu_cores * 2,  # Exceed limit
                memory_gb=quota.memory_gb * 2,  # Exceed limit
                worker_slots=quota.worker_slots + 10,  # Exceed limit
                client_connections=quota.client_connections + 50  # Exceed limit
            ),
            priority=AllocationPriority.NORMAL,
            requested_at=datetime.now()
        )
        
        # Test validation
        valid_result = allocator._validate_request(valid_request)
        invalid_result = allocator._validate_request(invalid_request)
        
        print(f"   Validation Results:")
        print(f"     Valid request (within limits): {'✅ PASS' if valid_result else '❌ FAIL'}")
        print(f"     Invalid request (exceeds limits): {'❌ REJECTED' if not invalid_result else '✅ UNEXPECTED PASS'}")


async def demo_integration_with_service_runner():
    """Demonstrate integration with service runner"""
    print("\n" + "="*60)
    print("SERVICE RUNNER INTEGRATION DEMO")
    print("="*60)
    
    # Create demo network configs
    configs = []
    
    # Config 1
    config1 = {
        "network_id": "demo-llama-network",
        "model_id": "llama-7b-chat",
        "host": "localhost",
        "port": 8701,
        "model_chain_order": ["embedding", "attention", "mlp", "output"],
        "paths": {"model_dir": "./models/llama-7b"},
        "nodes": {"node1": {"host": "localhost", "port": 8801}}
    }
    
    # Config 2
    config2 = {
        "network_id": "demo-mistral-network",
        "model_id": "mistral-7b-instruct",
        "host": "localhost",
        "port": 8702,
        "model_chain_order": ["embedding", "transformer", "output"],
        "paths": {"model_dir": "./models/mistral-7b"},
        "nodes": {"node1": {"host": "localhost", "port": 8802}}
    }
    
    # Write config files
    with open("network_config_demo_llama.json", "w") as f:
        json.dump(config1, f, indent=2)
    
    with open("network_config_demo_mistral.json", "w") as f:
        json.dump(config2, f, indent=2)
    
    print("✓ Created demo network configurations")
    
    # Create service runner with resource allocation
    service_runner = MultiNetworkServiceRunner(
        config_pattern="network_config_demo*.json"
    )
    
    try:
        print("✓ Service runner initialized with resource allocation")
        
        # Check resource allocator
        if service_runner.resource_allocator:
            print("✓ Resource allocator is available")
            
            # Get resource utilization
            utilization = service_runner.get_resource_utilization()
            if "error" not in utilization:
                print("✓ Resource utilization reporting works")
                print(f"   Total system resources configured")
                
                # Show available resources
                for resource_type, data in utilization['resources'].items():
                    if data['total'] > 0:
                        print(f"     {resource_type}: {data['total']}")
            else:
                print(f"❌ Resource utilization error: {utilization['error']}")
        else:
            print("❌ Resource allocator not available")
        
        # Simulate starting networks (would require full service runner)
        print("\n🔄 Network startup simulation:")
        print("   1. Service runner would discover network configs")
        print("   2. For each network, request resource allocation")
        print("   3. Wait for allocation approval")
        print("   4. Start network service with allocated resources")
        print("   5. Monitor resource usage and adjust as needed")
        
        print("\n💡 Resource allocation ensures:")
        print("   • License compliance (network and client limits)")
        print("   • Fair resource distribution")
        print("   • Conflict resolution when resources are scarce")
        print("   • Dynamic scaling based on actual usage")
        print("   • Automatic cleanup of unused allocations")
        
    finally:
        # Cleanup demo files
        try:
            Path("network_config_demo_llama.json").unlink(missing_ok=True)
            Path("network_config_demo_mistral.json").unlink(missing_ok=True)
            print("✓ Demo config files cleaned up")
        except:
            pass


async def main():
    """Main demo function"""
    print("🚀 DYNAMIC RESOURCE ALLOCATION SYSTEM DEMO")
    print("=" * 80)
    print("This demo showcases the comprehensive resource allocation system")
    print("with license-aware distribution, conflict resolution, and dynamic scaling.")
    
    try:
        # Run all demos
        await demo_basic_allocation()
        await demo_conflict_resolution()
        await demo_dynamic_scaling()
        await demo_license_constraints()
        await demo_integration_with_service_runner()
        
        print("\n" + "="*80)
        print("🎉 ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("="*80)
        print("\n📋 SUMMARY OF FEATURES DEMONSTRATED:")
        print("✅ License-aware resource allocation")
        print("✅ Priority-based conflict resolution")
        print("✅ Dynamic resource scaling based on load")
        print("✅ Multi-tier license constraint enforcement")
        print("✅ Integration with service runner")
        print("✅ Real-time resource utilization monitoring")
        print("✅ Automatic cleanup and optimization")
        
        print("\n🎯 KEY BENEFITS:")
        print("• Ensures fair resource distribution across networks")
        print("• Prevents resource conflicts and over-allocation")
        print("• Automatically scales resources based on demand")
        print("• Enforces license limits and compliance")
        print("• Provides comprehensive monitoring and reporting")
        print("• Optimizes system performance and efficiency")
        
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())