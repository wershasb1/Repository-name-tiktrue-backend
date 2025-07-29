#!/usr/bin/env python3
"""
Demo script for Network Health Monitoring Dashboard
Tests the complete health monitoring system with dashboard interface
"""

import asyncio
import json
import time
import webbrowser
from pathlib import Path

from core.service_runner import MultiNetworkServiceRunner
from network_dashboard import NetworkDashboard
from health_monitor import AsyncHealthMonitor, HealthStatus


async def create_demo_configs():
    """Create demo network configuration files"""
    print("Creating demo network configurations...")
    
    # Demo config 1 - Llama network
    config1 = {
        "network_id": "llama-demo-network",
        "model_id": "llama-7b-chat",
        "host": "localhost",
        "port": 8701,
        "model_chain_order": ["embedding", "attention", "mlp", "output"],
        "paths": {
            "model_dir": "./assets/models/llama-7b-chat",
            "cache_dir": "./cache/llama-demo"
        },
        "nodes": {
            "node1": {
                "host": "localhost",
                "port": 8801,
                "blocks": ["embedding", "attention"]
            },
            "node2": {
                "host": "localhost", 
                "port": 8802,
                "blocks": ["mlp", "output"]
            }
        }
    }
    
    # Demo config 2 - Mistral network
    config2 = {
        "network_id": "mistral-demo-network",
        "model_id": "mistral-7b-instruct",
        "host": "localhost",
        "port": 8702,
        "model_chain_order": ["embedding", "transformer", "output"],
        "paths": {
            "model_dir": "./assets/models/mistral-7b-instruct",
            "cache_dir": "./cache/mistral-demo"
        },
        "nodes": {
            "node1": {
                "host": "localhost",
                "port": 8803,
                "blocks": ["embedding"]
            },
            "node2": {
                "host": "localhost",
                "port": 8804,
                "blocks": ["transformer", "output"]
            }
        }
    }
    
    # Write config files
    with open("network_config_llama_demo.json", "w") as f:
        json.dump(config1, f, indent=2)
    
    with open("network_config_mistral_demo.json", "w") as f:
        json.dump(config2, f, indent=2)
    
    print("✓ Demo configurations created")


async def demo_health_monitoring():
    """Demonstrate health monitoring functionality"""
    print("\n" + "="*60)
    print("NETWORK HEALTH MONITORING DASHBOARD DEMO")
    print("="*60)
    
    # Create demo configurations
    await create_demo_configs()
    
    # Create service runner
    print("\nInitializing service runner...")
    service_runner = MultiNetworkServiceRunner(config_pattern="network_config_*demo.json")
    
    # Create dashboard with health monitoring
    print("Creating dashboard with health monitoring...")
    dashboard = NetworkDashboard(
        service_runner=service_runner,
        host="localhost",
        port=5000,
        refresh_interval=5
    )
    
    # Add health monitoring callbacks
    if dashboard.health_monitor:
        def on_health_change(network_id: str, old_status: HealthStatus, new_status: HealthStatus):
            print(f"🔄 Health Status Change: {network_id} - {old_status.value} → {new_status.value}")
        
        def on_failure(network_id: str, message: str):
            print(f"❌ Network Failure: {network_id} - {message}")
        
        dashboard.health_monitor.add_health_change_callback(on_health_change)
        dashboard.health_monitor.add_failure_callback(on_failure)
    
    try:
        # Start service runner
        print("Starting service runner...")
        await service_runner.start()
        print("✓ Service runner started")
        
        # Start dashboard
        print("Starting dashboard server...")
        success = dashboard.start()
        if success:
            print("✓ Dashboard server started")
            print(f"🌐 Dashboard available at: http://localhost:5000")
            
            # Try to open browser
            try:
                webbrowser.open("http://localhost:5000")
                print("✓ Browser opened automatically")
            except:
                print("ℹ️  Please open http://localhost:5000 in your browser")
        else:
            print("❌ Failed to start dashboard server")
            return
        
        # Demonstrate health monitoring features
        print("\n" + "-"*50)
        print("HEALTH MONITORING FEATURES DEMO")
        print("-"*50)
        
        # Wait for initial health checks
        print("⏳ Waiting for initial health checks...")
        await asyncio.sleep(10)
        
        # Show health summary
        if dashboard.health_monitor:
            health_summary = dashboard.health_monitor.get_health_summary()
            print(f"\n📊 Health Summary:")
            print(f"   Overall Status: {health_summary['overall_status']}")
            print(f"   Total Networks: {health_summary['total_networks']}")
            print(f"   Healthy Networks: {health_summary['healthy_networks']}")
            print(f"   Warning Networks: {health_summary['warning_networks']}")
            print(f"   Critical Networks: {health_summary['critical_networks']}")
            print(f"   Average Response Time: {health_summary['average_response_time']:.3f}s")
            
            # Show individual network health
            print(f"\n🔍 Individual Network Health:")
            for network_id, network_health in health_summary['networks'].items():
                print(f"   {network_id}:")
                print(f"     Status: {network_health['status']}")
                print(f"     Response Time: {network_health['response_time']:.3f}s")
                print(f"     Consecutive Failures: {network_health['consecutive_failures']}")
                print(f"     Error Count: {network_health['error_count']}")
                if network_health['recent_errors']:
                    print(f"     Recent Errors: {len(network_health['recent_errors'])}")
        
        # Demonstrate dashboard features
        print(f"\n🎛️  Dashboard Features Available:")
        print(f"   • Real-time network status monitoring")
        print(f"   • Health status indicators with color coding")
        print(f"   • Performance metrics and error tracking")
        print(f"   • Network control (start/stop/restart)")
        print(f"   • Detailed network information modals")
        print(f"   • Error log with timestamps")
        print(f"   • Auto-refresh functionality")
        
        # Show API endpoints
        print(f"\n🔌 Available API Endpoints:")
        print(f"   GET  /api/status           - Overall system status")
        print(f"   GET  /api/networks         - List all networks")
        print(f"   GET  /api/network/<id>     - Network details")
        print(f"   POST /api/control/start/<id>   - Start network")
        print(f"   POST /api/control/stop/<id>    - Stop network")
        print(f"   POST /api/control/restart/<id> - Restart network")
        
        # Monitor for a while
        print(f"\n⏱️  Monitoring networks for 60 seconds...")
        print(f"   (Check the dashboard in your browser)")
        print(f"   Press Ctrl+C to stop early")
        
        for i in range(12):  # 60 seconds / 5 second intervals
            await asyncio.sleep(5)
            
            # Show periodic health updates
            if dashboard.health_monitor and i % 2 == 0:  # Every 10 seconds
                health_summary = dashboard.health_monitor.get_health_summary()
                print(f"   Health Check {i//2 + 1}: {health_summary['overall_status']} - "
                      f"{health_summary['healthy_networks']}/{health_summary['total_networks']} healthy")
        
        print(f"\n✅ Demo completed successfully!")
        print(f"   Dashboard is still running at http://localhost:5000")
        print(f"   Press Ctrl+C to stop")
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        print(f"\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n🧹 Cleaning up...")
        
        # Stop dashboard
        dashboard.stop()
        print("✓ Dashboard stopped")
        
        # Stop service runner
        await service_runner.shutdown()
        print("✓ Service runner stopped")
        
        # Clean up demo config files
        try:
            Path("network_config_llama_demo.json").unlink(missing_ok=True)
            Path("network_config_mistral_demo.json").unlink(missing_ok=True)
            print("✓ Demo config files cleaned up")
        except:
            pass
        
        print("✅ Cleanup completed")


async def test_health_monitor_standalone():
    """Test health monitor standalone functionality"""
    print("\n" + "="*50)
    print("STANDALONE HEALTH MONITOR TEST")
    print("="*50)
    
    # Create service runner
    service_runner = MultiNetworkServiceRunner()
    
    # Create health monitor
    health_monitor = AsyncHealthMonitor(
        service_runner=service_runner,
        heartbeat_interval=10,  # Faster for demo
        failure_threshold=2,
        warning_threshold=1
    )
    
    # Add callbacks
    def on_health_change(network_id: str, old_status: HealthStatus, new_status: HealthStatus):
        print(f"🔄 {network_id}: {old_status.value} → {new_status.value}")
    
    def on_failure(network_id: str, message: str):
        print(f"❌ {network_id}: {message}")
    
    health_monitor.add_health_change_callback(on_health_change)
    health_monitor.add_failure_callback(on_failure)
    
    try:
        # Start service runner
        await service_runner.start()
        print("✓ Service runner started")
        
        # Start health monitoring
        await health_monitor.start()
        print("✓ Health monitoring started")
        
        # Monitor for 30 seconds
        print("⏱️  Monitoring for 30 seconds...")
        for i in range(6):
            await asyncio.sleep(5)
            summary = health_monitor.get_health_summary()
            print(f"   Check {i+1}: {summary['overall_status']} - "
                  f"{summary['total_networks']} networks")
        
        print("✅ Standalone test completed")
    
    except Exception as e:
        print(f"❌ Test error: {e}")
    finally:
        # Stop health monitoring
        await health_monitor.stop()
        print("✓ Health monitoring stopped")
        
        # Stop service runner
        await service_runner.shutdown()
        print("✓ Service runner stopped")


def main():
    """Main demo function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Network Health Monitoring Dashboard Demo")
    parser.add_argument("--test-only", action="store_true", help="Run standalone health monitor test only")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    
    args = parser.parse_args()
    
    if args.test_only:
        asyncio.run(test_health_monitor_standalone())
    else:
        asyncio.run(demo_health_monitoring())


if __name__ == "__main__":
    main()