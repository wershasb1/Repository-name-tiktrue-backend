#!/usr/bin/env python3
"""
Demo script for Fault Tolerance and Recovery System
Demonstrates health monitoring, failover management, and block redistribution
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from health_monitor import (
    HealthMonitor, AsyncHealthMonitor, HealthStatus, NetworkHealthInfo, 
    WorkerHealthInfo, AdminNotification
)
from failover_manager import (
    FailoverManager, FailoverStrategy, DegradationLevel, BackupWorker,
    FailoverEvent, BlockRedistribution, BlockAssignment
)
from core.service_runner import MultiNetworkServiceRunner
from security.license_validator import LicenseInfo, SubscriptionTier


async def demo_health_monitoring():
    """Demonstrate health monitoring capabilities"""
    print("\n" + "="*60)
    print("HEALTH MONITORING SYSTEM DEMO")
    print("="*60)
    
    # Create health monitor
    health_monitor = HealthMonitor(
        heartbeat_interval=2,  # Fast for demo
        failure_threshold=2,
        warning_threshold=1
    )
    
    print("✓ Health monitor created")
    print(f"   Heartbeat interval: {health_monitor.heartbeat_interval}s")
    print(f"   Warning threshold: {health_monitor.warning_threshold} failures")
    print(f"   Critical threshold: {health_monitor.failure_threshold} failures")
    
    # Add some mock network health data
    networks = {
        "llama-network": NetworkHealthInfo(
            network_id="llama-network",
            status=HealthStatus.HEALTHY,
            last_heartbeat=datetime.now(),
            response_time=0.1,
            request_count=1000,
            error_count=5,
            client_connections=3
        ),
        "mistral-network": NetworkHealthInfo(
            network_id="mistral-network",
            status=HealthStatus.WARNING,
            last_heartbeat=datetime.now() - timedelta(seconds=30),
            response_time=0.5,
            request_count=500,
            error_count=25,
            client_connections=1
        ),
        "gpt-network": NetworkHealthInfo(
            network_id="gpt-network",
            status=HealthStatus.CRITICAL,
            last_heartbeat=datetime.now() - timedelta(minutes=2),
            response_time=2.0,
            request_count=100,
            error_count=50,
            client_connections=0
        )
    }
    
    health_monitor.network_health = networks
    
    # Add some mock worker health data
    workers = {
        "llama-network_worker1": WorkerHealthInfo(
            worker_id="llama-network_worker1",
            network_id="llama-network",
            status=HealthStatus.HEALTHY,
            last_heartbeat=datetime.now(),
            response_time=0.08,
            cpu_usage=45.0,
            memory_usage=60.0,
            gpu_usage=70.0,
            worker_host="localhost",
            worker_port=8801,
            model_blocks=["embedding", "attention"]
        ),
        "llama-network_worker2": WorkerHealthInfo(
            worker_id="llama-network_worker2",
            network_id="llama-network",
            status=HealthStatus.HEALTHY,
            last_heartbeat=datetime.now(),
            response_time=0.12,
            cpu_usage=50.0,
            memory_usage=55.0,
            gpu_usage=65.0,
            worker_host="localhost",
            worker_port=8802,
            model_blocks=["mlp", "output"]
        ),
        "mistral-network_worker1": WorkerHealthInfo(
            worker_id="mistral-network_worker1",
            network_id="mistral-network",
            status=HealthStatus.WARNING,
            last_heartbeat=datetime.now() - timedelta(seconds=45),
            response_time=0.8,
            cpu_usage=85.0,
            memory_usage=90.0,
            gpu_usage=95.0,
            worker_host="localhost",
            worker_port=8803,
            model_blocks=["transformer", "output"],
            consecutive_failures=1
        )
    }
    
    health_monitor.worker_health = workers
    
    print(f"\n📊 Network Health Summary:")
    for network_id, health_info in networks.items():
        status_icon = {"healthy": "✅", "warning": "⚠️", "critical": "❌", "unknown": "❓"}
        print(f"   {status_icon.get(health_info.status.value, '❓')} {network_id}:")
        print(f"     Status: {health_info.status.value.upper()}")
        print(f"     Response Time: {health_info.response_time:.3f}s")
        print(f"     Requests: {health_info.request_count}")
        print(f"     Errors: {health_info.error_count}")
        print(f"     Connections: {health_info.client_connections}")
    
    print(f"\n🔧 Worker Health Summary:")
    for worker_id, worker_info in workers.items():
        status_icon = {"healthy": "✅", "warning": "⚠️", "critical": "❌", "unknown": "❓"}
        print(f"   {status_icon.get(worker_info.status.value, '❓')} {worker_id}:")
        print(f"     Status: {worker_info.status.value.upper()}")
        print(f"     Response Time: {worker_info.response_time:.3f}s")
        print(f"     CPU: {worker_info.cpu_usage:.1f}%")
        print(f"     Memory: {worker_info.memory_usage:.1f}%")
        print(f"     GPU: {worker_info.gpu_usage:.1f}%")
        print(f"     Model Blocks: {worker_info.model_blocks}")
        if worker_info.consecutive_failures > 0:
            print(f"     Consecutive Failures: {worker_info.consecutive_failures}")
    
    # Test overall health status
    overall_status = health_monitor.get_overall_health_status()
    print(f"\n🎯 Overall System Health: {overall_status.value.upper()}")
    
    # Test health summary
    summary = health_monitor.get_health_summary()
    print(f"\n📈 Health Summary:")
    print(f"   Total Networks: {summary['total_networks']}")
    print(f"   Healthy: {summary['healthy_networks']}")
    print(f"   Warning: {summary['warning_networks']}")
    print(f"   Critical: {summary['critical_networks']}")
    print(f"   Average Response Time: {summary['average_response_time']:.3f}s")
    
    # Demonstrate admin notifications
    print(f"\n📢 Creating Admin Notifications...")
    await health_monitor._create_admin_notification(
        severity="warning",
        source="mistral-network_worker1",
        message="Worker showing high resource usage and slow response times",
        details={
            "cpu_usage": 85.0,
            "memory_usage": 90.0,
            "response_time": 0.8,
            "consecutive_failures": 1
        }
    )
    
    await health_monitor._create_admin_notification(
        severity="critical",
        source="gpt-network",
        message="Network has been unresponsive for over 2 minutes",
        details={
            "last_heartbeat": (datetime.now() - timedelta(minutes=2)).isoformat(),
            "status": "critical",
            "client_connections": 0
        }
    )
    
    notifications = health_monitor.get_admin_notifications()
    print(f"   Created {len(notifications)} notifications:")
    
    for notification in notifications:
        severity_icon = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
        print(f"   {severity_icon.get(notification.severity, 'ℹ️')} {notification.severity.upper()}: {notification.message}")
        print(f"     Source: {notification.source}")
        print(f"     Time: {notification.timestamp.strftime('%H:%M:%S')}")
        print(f"     Acknowledged: {'Yes' if notification.acknowledged else 'No'}")
    
    print(f"\n💡 Health monitoring provides:")
    print(f"   • Real-time network and worker health tracking")
    print(f"   • Configurable failure thresholds and alerting")
    print(f"   • Performance metrics collection")
    print(f"   • Admin notification system")
    print(f"   • License validity monitoring")


async def demo_failover_management():
    """Demonstrate failover management capabilities"""
    print("\n" + "="*60)
    print("FAILOVER MANAGEMENT SYSTEM DEMO")
    print("="*60)
    
    # Create failover manager
    failover_manager = FailoverManager(
        failover_timeout=30.0,
        max_concurrent_failovers=3
    )
    
    print("✓ Failover manager created")
    print(f"   Failover timeout: {failover_manager.failover_timeout}s")
    print(f"   Max concurrent failovers: {failover_manager.max_concurrent_failovers}")
    
    # Add some backup workers
    backup_workers = {
        "llama-backup-1": BackupWorker(
            worker_id="llama-backup-1",
            network_id="llama-network",
            host="localhost",
            port=8901,
            model_blocks=["embedding", "attention"],
            priority=1,
            status="standby"
        ),
        "llama-backup-2": BackupWorker(
            worker_id="llama-backup-2",
            network_id="llama-network",
            host="localhost",
            port=8902,
            model_blocks=["mlp", "output"],
            priority=2,
            status="standby"
        ),
        "mistral-backup-1": BackupWorker(
            worker_id="mistral-backup-1",
            network_id="mistral-network",
            host="localhost",
            port=8903,
            model_blocks=["transformer", "output"],
            priority=1,
            status="standby"
        )
    }
    
    failover_manager.backup_workers = backup_workers
    
    print(f"\n🔄 Backup Workers Available:")
    for worker_id, worker in backup_workers.items():
        print(f"   • {worker_id}:")
        print(f"     Network: {worker.network_id}")
        print(f"     Status: {worker.status}")
        print(f"     Priority: {worker.priority}")
        print(f"     Blocks: {worker.model_blocks}")
    
    # Demonstrate graceful degradation
    print(f"\n📉 Demonstrating Graceful Degradation:")
    
    degradation_scenarios = [
        (DegradationLevel.NONE, "Normal operation - all systems healthy"),
        (DegradationLevel.REDUCED_QUALITY, "10% of networks showing issues - reducing model precision"),
        (DegradationLevel.REDUCED_CAPACITY, "25% of networks critical - limiting concurrent requests"),
        (DegradationLevel.ESSENTIAL_ONLY, "40% of networks down - essential operations only"),
        (DegradationLevel.MAINTENANCE_MODE, "60% of networks failed - entering maintenance mode")
    ]
    
    for level, reason in degradation_scenarios:
        await failover_manager.graceful_degradation(level, reason)
        print(f"   📊 {level.name}: {reason}")
        await asyncio.sleep(1.0)  # Brief pause for demo
    
    # Show degradation history
    print(f"\n📜 Degradation History:")
    for timestamp, level, reason in failover_manager.degradation_history:
        print(f"   {timestamp.strftime('%H:%M:%S')} - {level.name}: {reason}")
    
    # Demonstrate backup worker activation
    print(f"\n🚀 Demonstrating Backup Worker Activation:")
    
    # Mock health monitor for activation
    class MockHealthMonitor:
        def get_all_worker_health(self):
            return {
                "llama-network_worker1": type('obj', (object,), {
                    'network_id': 'llama-network',
                    'status': HealthStatus.CRITICAL
                })()
            }
    
    failover_manager.health_monitor = MockHealthMonitor()
    
    # Mock license validation
    async def mock_license_check(backup_worker):
        return True
    
    async def mock_allocate_resources(backup_worker):
        return True
    
    async def mock_start_worker(backup_worker):
        return True
    
    failover_manager._check_failover_license_permissions = mock_license_check
    failover_manager._allocate_backup_resources = mock_allocate_resources
    failover_manager._start_backup_worker = mock_start_worker
    
    # Activate backup worker
    backup_worker = await failover_manager.activate_backup_worker("llama-network_worker1")
    
    if backup_worker:
        print(f"   ✅ Successfully activated backup worker: {backup_worker.worker_id}")
        print(f"     Status: {backup_worker.status}")
        print(f"     Activation time: {backup_worker.activation_time.strftime('%H:%M:%S')}")
    else:
        print(f"   ❌ Failed to activate backup worker")
    
    # Demonstrate workload transfer
    print(f"\n📦 Demonstrating Workload Transfer:")
    
    transfer_success = await failover_manager.transfer_workload(
        source_worker="llama-network_worker1",
        target_worker="llama-backup-1",
        model_blocks=["embedding", "attention"]
    )
    
    if transfer_success:
        print(f"   ✅ Workload transfer completed successfully")
        
        # Show transfer details
        transfer = list(failover_manager.workload_transfers.values())[0]
        print(f"     Transfer ID: {transfer.transfer_id}")
        print(f"     Source: {transfer.source_worker}")
        print(f"     Target: {transfer.target_worker}")
        print(f"     Blocks: {transfer.model_blocks}")
        print(f"     Duration: {(transfer.transfer_completed - transfer.transfer_started).total_seconds():.1f}s")
    else:
        print(f"   ❌ Workload transfer failed")
    
    # Show failover statistics
    print(f"\n📊 Failover Statistics:")
    stats = failover_manager.stats
    print(f"   Backup Activations: {stats['backup_activations']}")
    print(f"   Degradation Events: {stats['degradation_events']}")
    print(f"   Total Failovers: {stats['total_failovers']}")
    print(f"   Successful Failovers: {stats['successful_failovers']}")
    
    print(f"\n💡 Failover management provides:")
    print(f"   • Automatic backup worker activation")
    print(f"   • Graceful degradation under load")
    print(f"   • Workload transfer mechanisms")
    print(f"   • License-aware failover operations")
    print(f"   • Comprehensive event tracking")


async def demo_block_redistribution():
    """Demonstrate block redistribution capabilities"""
    print("\n" + "="*60)
    print("BLOCK REDISTRIBUTION SYSTEM DEMO")
    print("="*60)
    
    # Create failover manager for block redistribution
    failover_manager = FailoverManager()
    
    # Set up initial block assignments
    initial_assignments = {
        "block1": BlockAssignment(
            block_id="block1",
            network_id="llama-network",
            assigned_worker="worker1",
            assignment_priority=1
        ),
        "block2": BlockAssignment(
            block_id="block2",
            network_id="llama-network",
            assigned_worker="worker1",
            assignment_priority=1
        ),
        "block3": BlockAssignment(
            block_id="block3",
            network_id="llama-network",
            assigned_worker="worker2",
            assignment_priority=1
        ),
        "block4": BlockAssignment(
            block_id="block4",
            network_id="llama-network",
            assigned_worker="worker2",
            assignment_priority=1
        )
    }
    
    failover_manager.block_assignments = initial_assignments
    
    print(f"📋 Initial Block Assignments:")
    for block_id, assignment in initial_assignments.items():
        print(f"   {block_id} → {assignment.assigned_worker}")
    
    # Mock health monitor with worker failure
    class MockHealthMonitor:
        def get_all_worker_health(self):
            return {
                "worker1": type('obj', (object,), {
                    'network_id': 'llama-network',
                    'model_blocks': ['block1', 'block2'],
                    'status': HealthStatus.CRITICAL
                })(),
                "worker2": type('obj', (object,), {
                    'network_id': 'llama-network',
                    'model_blocks': ['block3', 'block4'],
                    'status': HealthStatus.HEALTHY
                })()
            }
    
    failover_manager.health_monitor = MockHealthMonitor()
    
    # Mock available workers
    async def mock_get_available_workers(network_id, exclude_worker):
        return ["worker2", "worker3", "backup-worker1"]
    
    # Mock license check
    async def mock_license_check(network_id):
        return True
    
    # Mock conflict resolution
    async def mock_resolve_conflicts(network_id, plan):
        return 1  # One conflict resolved
    
    # Mock execution
    async def mock_execute_redistribution(redistribution):
        return True
    
    # Mock config update
    async def mock_update_config(network_id, plan):
        pass
    
    # Apply mocks
    failover_manager._get_available_workers = mock_get_available_workers
    failover_manager._check_redistribution_license_permissions = mock_license_check
    failover_manager._resolve_block_assignment_conflicts = mock_resolve_conflicts
    failover_manager._execute_block_redistribution = mock_execute_redistribution
    failover_manager._update_network_configuration_after_redistribution = mock_update_config
    
    print(f"\n⚠️  Worker Failure Detected: worker1 (blocks: block1, block2)")
    print(f"🔄 Starting Block Redistribution...")
    
    # Perform block redistribution
    success = await failover_manager.redistribute_blocks("worker1", "llama-network")
    
    if success:
        print(f"   ✅ Block redistribution completed successfully")
        
        # Show redistribution results
        if failover_manager.redistribution_history:
            redistribution = failover_manager.redistribution_history[0]
            print(f"\n📊 Redistribution Details:")
            print(f"   Redistribution ID: {redistribution.redistribution_id}")
            print(f"   Failed Worker: {redistribution.failed_worker}")
            print(f"   Affected Blocks: {redistribution.affected_blocks}")
            print(f"   Conflicts Resolved: {redistribution.conflicts_resolved}")
            print(f"   Success: {redistribution.success}")
            
            print(f"\n📋 New Block Distribution:")
            for worker_id, blocks in redistribution.redistribution_plan.items():
                print(f"   {worker_id} → {blocks}")
    else:
        print(f"   ❌ Block redistribution failed")
    
    # Show current block assignments
    print(f"\n📋 Updated Block Assignments:")
    assignments = failover_manager.get_block_assignments("llama-network")
    for block_id, assignment in assignments.items():
        print(f"   {block_id} → {assignment.assigned_worker} (updated: {assignment.last_updated.strftime('%H:%M:%S')})")
    
    # Show redistribution status
    status = failover_manager.get_redistribution_status()
    print(f"\n📈 Redistribution Status:")
    print(f"   Active Redistributions: {status['active_redistributions']}")
    print(f"   Total Redistributions: {status['total_redistributions']}")
    print(f"   Block Assignments: {status['block_assignments']}")
    
    print(f"\n💡 Block redistribution provides:")
    print(f"   • Automatic block reallocation on worker failure")
    print(f"   • License-aware redistribution permissions")
    print(f"   • Conflict resolution for block assignments")
    print(f"   • Network configuration updates")
    print(f"   • Comprehensive redistribution tracking")


async def demo_integration_scenario():
    """Demonstrate complete fault tolerance scenario"""
    print("\n" + "="*60)
    print("COMPLETE FAULT TOLERANCE SCENARIO")
    print("="*60)
    
    print("🎬 Scenario: Production system with multiple networks experiencing failures")
    
    # Create integrated system
    health_monitor = HealthMonitor(heartbeat_interval=2)
    failover_manager = FailoverManager(health_monitor=health_monitor)
    
    # Set up initial healthy state
    print(f"\n1️⃣  Initial System State:")
    print(f"   • 3 networks running (llama, mistral, gpt)")
    print(f"   • 6 workers total (2 per network)")
    print(f"   • 3 backup workers on standby")
    print(f"   • All systems healthy")
    
    # Simulate gradual system degradation
    print(f"\n2️⃣  System Degradation Begins:")
    
    # First failure - worker becomes unresponsive
    print(f"   ⚠️  T+00:30 - Worker llama_worker1 becomes unresponsive")
    await health_monitor._create_admin_notification(
        severity="warning",
        source="llama_worker1",
        message="Worker not responding to heartbeat pings"
    )
    
    # Trigger failover
    print(f"   🔄 T+01:00 - Activating backup worker for llama_worker1")
    await failover_manager.graceful_degradation(
        DegradationLevel.REDUCED_QUALITY,
        "Single worker failure - reducing quality to maintain performance"
    )
    
    # Second failure - network issues
    print(f"   ❌ T+02:30 - Mistral network experiencing high error rates")
    await health_monitor._create_admin_notification(
        severity="error",
        source="mistral-network",
        message="Network error rate exceeded 20% - investigating connectivity issues"
    )
    
    # More aggressive degradation
    print(f"   📉 T+03:00 - Applying capacity reduction")
    await failover_manager.graceful_degradation(
        DegradationLevel.REDUCED_CAPACITY,
        "Multiple network issues - reducing concurrent request capacity"
    )
    
    # Critical failure - entire network down
    print(f"   🚨 T+05:00 - GPT network completely unresponsive")
    await health_monitor._create_admin_notification(
        severity="critical",
        source="gpt-network",
        message="Network completely down - all workers unresponsive"
    )
    
    # Block redistribution needed
    print(f"   📦 T+05:30 - Redistributing blocks from failed GPT workers")
    
    # Emergency degradation
    print(f"   🔴 T+06:00 - Entering maintenance mode")
    await failover_manager.graceful_degradation(
        DegradationLevel.MAINTENANCE_MODE,
        "Critical system failures - entering maintenance mode for stability"
    )
    
    print(f"\n3️⃣  Recovery Actions Taken:")
    print(f"   ✅ Backup workers activated automatically")
    print(f"   ✅ Model blocks redistributed to healthy workers")
    print(f"   ✅ System degraded gracefully to maintain core functionality")
    print(f"   ✅ Admin notifications sent for all critical events")
    print(f"   ✅ License compliance maintained throughout")
    
    print(f"\n4️⃣  System Recovery:")
    print(f"   🔧 T+10:00 - Infrastructure issues resolved")
    print(f"   🔄 T+12:00 - Workers coming back online")
    print(f"   📈 T+15:00 - Gradually restoring normal operation")
    
    # Gradual recovery
    await failover_manager.graceful_degradation(
        DegradationLevel.REDUCED_CAPACITY,
        "Infrastructure restored - gradually increasing capacity"
    )
    
    await asyncio.sleep(1.0)
    
    await failover_manager.graceful_degradation(
        DegradationLevel.REDUCED_QUALITY,
        "Most systems recovered - restoring quality levels"
    )
    
    await asyncio.sleep(1.0)
    
    await failover_manager.graceful_degradation(
        DegradationLevel.NONE,
        "All systems healthy - normal operation restored"
    )
    
    print(f"   ✅ T+20:00 - Full system recovery completed")
    
    # Show final statistics
    notifications = health_monitor.get_admin_notifications()
    print(f"\n📊 Final Statistics:")
    print(f"   Admin Notifications: {len(notifications)}")
    print(f"   Degradation Events: {len(failover_manager.degradation_history)}")
    print(f"   Current Status: {failover_manager.current_degradation_level.name}")
    
    print(f"\n🎯 Key Benefits Demonstrated:")
    print(f"   • Automatic failure detection and response")
    print(f"   • Graceful degradation prevents total system failure")
    print(f"   • Block redistribution maintains model availability")
    print(f"   • Admin notifications provide visibility")
    print(f"   • License compliance maintained under stress")
    print(f"   • System recovers automatically as issues resolve")


async def main():
    """Main demo function"""
    print("🚀 FAULT TOLERANCE AND RECOVERY SYSTEM DEMO")
    print("=" * 80)
    print("This demo showcases the comprehensive fault tolerance system")
    print("with health monitoring, failover management, and block redistribution.")
    
    try:
        # Run all demos
        await demo_health_monitoring()
        await demo_failover_management()
        await demo_block_redistribution()
        await demo_integration_scenario()
        
        print("\n" + "="*80)
        print("🎉 ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("="*80)
        print("\n📋 SUMMARY OF FEATURES DEMONSTRATED:")
        print("✅ Real-time health monitoring for networks and workers")
        print("✅ Automatic failure detection with configurable thresholds")
        print("✅ Admin notification system for critical events")
        print("✅ Backup worker activation and management")
        print("✅ Graceful degradation under system stress")
        print("✅ Automatic workload transfer mechanisms")
        print("✅ Block redistribution on worker failures")
        print("✅ License-aware failover operations")
        print("✅ Network configuration updates")
        print("✅ Comprehensive event tracking and statistics")
        
        print("\n🎯 KEY BENEFITS:")
        print("• Prevents total system failure through graceful degradation")
        print("• Maintains service availability during component failures")
        print("• Automatically redistributes workload to healthy components")
        print("• Provides comprehensive visibility into system health")
        print("• Ensures license compliance during failover operations")
        print("• Enables rapid recovery when issues are resolved")
        
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())