"""
Demo Script for Multi-Network Service Management

This script demonstrates the comprehensive multi-network service management
capabilities of the TikTrue Distributed LLM Platform, including:

- Multiple network creation and management
- Resource allocation and monitoring
- Client assignment and load balancing
- Network dashboard functionality
- Performance monitoring and analytics

Usage:
    python demo_multi_network_service.py [--gui] [--duration SECONDS]
"""

import asyncio
import argparse
import logging
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Import multi-network service components
from multi_network_service import (
    MultiNetworkService, NetworkDashboard, NetworkPriority,
    get_network_resource_recommendations
)
from core.network_manager import NetworkType
from license_models import SubscriptionTier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MultiNetworkDemo")


class MultiNetworkDemo:
    """
    Demonstration class for multi-network service functionality
    """
    
    def __init__(self, storage_dir: str = None):
        """
        Initialize demo
        
        Args:
            storage_dir: Directory for network storage
        """
        self.storage_dir = storage_dir or "demo_networks"
        self.service = MultiNetworkService(
            storage_dir=self.storage_dir,
            node_id="demo_admin_node"
        )
        self.dashboard = NetworkDashboard(self.service)
        
        # Demo state
        self.demo_networks = []
        self.demo_clients = []
        
        logger.info(f"MultiNetworkDemo initialized with storage: {self.storage_dir}")
    
    async def run_demo(self, duration: int = 60, show_gui: bool = False):
        """
        Run complete multi-network service demonstration
        
        Args:
            duration: Demo duration in seconds
            show_gui: Whether to show GUI dashboard
        """
        try:
            logger.info("Starting Multi-Network Service Demo")
            logger.info("=" * 50)
            
            # 1. Start services
            await self._start_services()
            
            # 2. Show initial system status
            await self._show_system_status()
            
            # 3. Create multiple networks
            await self._create_demo_networks()
            
            # 4. Show resource allocation
            await self._show_resource_allocation()
            
            # 5. Simulate client connections
            await self._simulate_client_connections()
            
            # 6. Monitor performance
            await self._monitor_performance(duration // 3)
            
            # 7. Demonstrate load balancing
            await self._demonstrate_load_balancing()
            
            # 8. Show dashboard data
            await self._show_dashboard_data()
            
            # 9. Test network management operations
            await self._test_network_management()
            
            # 10. Show final statistics
            await self._show_final_statistics()
            
            # 11. Show GUI if requested
            if show_gui:
                await self._show_gui_dashboard()
            
            logger.info("Demo completed successfully!")
            
        except Exception as e:
            logger.error(f"Demo failed: {e}", exc_info=True)
        finally:
            await self._cleanup()
    
    async def _start_services(self):
        """Start multi-network service and dashboard"""
        logger.info("1. Starting Multi-Network Service...")
        
        # Mock license for demo
        self._setup_demo_license()
        
        # Start service
        success = await self.service.start_service()
        if not success:
            raise RuntimeError("Failed to start multi-network service")
        
        # Start dashboard
        success = self.dashboard.start_dashboard()
        if not success:
            raise RuntimeError("Failed to start dashboard")
        
        logger.info("✓ Services started successfully")
        await asyncio.sleep(1)
    
    async def _show_system_status(self):
        """Show initial system status"""
        logger.info("2. System Status Check...")
        
        stats = self.service.get_service_statistics()
        system_resources = stats.get('system_resources', {}).get('system', {})
        
        logger.info(f"   CPU Cores: {system_resources.get('cpu_cores', 'Unknown')}")
        logger.info(f"   Total Memory: {system_resources.get('memory_total_gb', 0):.1f} GB")
        logger.info(f"   Available Memory: {system_resources.get('memory_available_gb', 0):.1f} GB")
        logger.info(f"   GPU Count: {system_resources.get('gpu_count', 0)}")
        
        logger.info("✓ System status checked")
        await asyncio.sleep(1)
    
    async def _create_demo_networks(self):
        """Create multiple demo networks"""
        logger.info("3. Creating Demo Networks...")
        
        # Network configurations for demo
        network_configs = [
            {
                'name': 'Production Llama Network',
                'model': 'llama3_1_8b_fp16',
                'type': NetworkType.ENTERPRISE,
                'priority': NetworkPriority.HIGH,
                'max_clients': 20,
                'description': 'High-priority production network for Llama 3.1 8B model'
            },
            {
                'name': 'Development Mistral Network',
                'model': 'mistral_7b_int4',
                'type': NetworkType.PRIVATE,
                'priority': NetworkPriority.NORMAL,
                'max_clients': 10,
                'description': 'Development network for Mistral 7B model testing'
            },
            {
                'name': 'Public Demo Network',
                'model': 'llama3_1_8b_fp16',
                'type': NetworkType.PUBLIC,
                'priority': NetworkPriority.LOW,
                'max_clients': 5,
                'description': 'Public demo network with limited resources'
            }
        ]
        
        for config in network_configs:
            logger.info(f"   Creating: {config['name']}")
            
            # Show resource recommendations
            recommendations = get_network_resource_recommendations(
                config['model'], config['max_clients']
            )
            logger.info(f"     Recommended CPU: {recommendations['cpu_percent']:.1f}%")
            logger.info(f"     Recommended Memory: {recommendations['memory_gb']:.1f} GB")
            
            # Create network
            network_info = await self.service.create_network(
                network_name=config['name'],
                model_id=config['model'],
                network_type=config['type'],
                max_clients=config['max_clients'],
                priority=config['priority'],
                description=config['description']
            )
            
            if network_info:
                self.demo_networks.append(network_info)
                logger.info(f"     ✓ Created: {network_info.network_id}")
            else:
                logger.error(f"     ✗ Failed to create: {config['name']}")
            
            await asyncio.sleep(0.5)
        
        logger.info(f"✓ Created {len(self.demo_networks)} networks")
    
    async def _show_resource_allocation(self):
        """Show resource allocation across networks"""
        logger.info("4. Resource Allocation Summary...")
        
        resource_summary = self.service.resource_manager.get_system_resource_summary()
        allocation_info = resource_summary.get('allocation', {})
        
        logger.info(f"   Total Networks: {allocation_info.get('networks_count', 0)}")
        logger.info(f"   Total CPU Allocated: {allocation_info.get('total_allocated_cpu_percent', 0):.1f}%")
        logger.info(f"   Total Memory Allocated: {allocation_info.get('total_allocated_memory_mb', 0):.0f} MB")
        logger.info(f"   CPU Overcommit Ratio: {allocation_info.get('cpu_overcommit_ratio', 0):.2f}")
        
        # Show per-network allocation
        for network in self.demo_networks:
            allocation = self.service.resource_manager.network_allocations.get(network.network_id)
            if allocation:
                logger.info(f"   {network.network_name}:")
                logger.info(f"     CPU: {allocation.cpu_limit_percent:.1f}%")
                logger.info(f"     Memory: {allocation.memory_limit_mb:.0f} MB")
                logger.info(f"     Priority: {allocation.priority.value}")
        
        logger.info("✓ Resource allocation displayed")
        await asyncio.sleep(2)
    
    async def _simulate_client_connections(self):
        """Simulate client connections to networks"""
        logger.info("5. Simulating Client Connections...")
        
        # Create demo clients
        client_assignments = [
            ('client_prod_1', 'Production Llama Network'),
            ('client_prod_2', 'Production Llama Network'),
            ('client_prod_3', 'Production Llama Network'),
            ('client_dev_1', 'Development Mistral Network'),
            ('client_dev_2', 'Development Mistral Network'),
            ('client_demo_1', 'Public Demo Network'),
            ('client_demo_2', 'Public Demo Network')
        ]
        
        for client_id, network_name in client_assignments:
            # Find network by name
            target_network = None
            for network in self.demo_networks:
                if network.network_name == network_name:
                    target_network = network
                    break
            
            if target_network:
                logger.info(f"   Assigning {client_id} to {network_name}")
                success = await self.service.assign_client_to_network(
                    client_id=client_id,
                    network_id=target_network.network_id
                )
                
                if success:
                    self.demo_clients.append(client_id)
                    logger.info(f"     ✓ Assigned successfully")
                    
                    # Simulate client activity
                    self.service.client_assignment_manager.update_client_activity(client_id)
                else:
                    logger.error(f"     ✗ Assignment failed")
            
            await asyncio.sleep(0.3)
        
        logger.info(f"✓ Simulated {len(self.demo_clients)} client connections")
    
    async def _monitor_performance(self, duration: int):
        """Monitor performance for specified duration"""
        logger.info(f"6. Monitoring Performance for {duration} seconds...")
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Get current statistics
            stats = self.service.get_service_statistics()
            service_info = stats.get('service', {})
            
            logger.info(f"   Active Networks: {service_info.get('active_networks', 0)}")
            logger.info(f"   Total Clients: {service_info.get('total_clients', 0)}")
            logger.info(f"   Active Clients: {service_info.get('active_clients', 0)}")
            
            # Show network-specific metrics
            networks = self.service.get_network_list()
            for network in networks:
                resource_alloc = network.get('resource_allocation', {})
                current_usage = resource_alloc.get('current_usage', {})
                
                logger.info(f"   {network['network_name']}:")
                logger.info(f"     Clients: {network['current_clients']}/{network['max_clients']}")
                if current_usage:
                    logger.info(f"     CPU Usage: {current_usage.get('cpu_usage_percent', 0):.1f}%")
                    logger.info(f"     Memory Usage: {current_usage.get('memory_usage_mb', 0):.0f} MB")
            
            await asyncio.sleep(5)
        
        logger.info("✓ Performance monitoring completed")
    
    async def _demonstrate_load_balancing(self):
        """Demonstrate load balancing capabilities"""
        logger.info("7. Demonstrating Load Balancing...")
        
        # Find the production network (should have highest priority)
        prod_network = None
        for network in self.demo_networks:
            if "Production" in network.network_name:
                prod_network = network
                break
        
        if prod_network:
            # Try to add more clients to test capacity limits
            logger.info(f"   Testing capacity limits for {prod_network.network_name}")
            
            for i in range(5):
                client_id = f"load_test_client_{i}"
                success = await self.service.assign_client_to_network(
                    client_id=client_id,
                    network_id=prod_network.network_id
                )
                
                if success:
                    logger.info(f"     ✓ Added {client_id}")
                    self.demo_clients.append(client_id)
                else:
                    logger.info(f"     ✗ Network at capacity, rejected {client_id}")
                
                await asyncio.sleep(0.2)
        
        # Show assignment statistics
        assignment_stats = self.service.client_assignment_manager.get_assignment_statistics()
        logger.info(f"   Total Assignments: {assignment_stats.get('total_assignments', 0)}")
        logger.info(f"   Active Assignments: {assignment_stats.get('active_assignments', 0)}")
        
        for network_id, network_stats in assignment_stats.get('networks', {}).items():
            network_name = "Unknown"
            for network in self.demo_networks:
                if network.network_id == network_id:
                    network_name = network.network_name
                    break
            
            logger.info(f"   {network_name}: {network_stats['active_clients']}/{network_stats['total_clients']} clients")
        
        logger.info("✓ Load balancing demonstration completed")
        await asyncio.sleep(1)
    
    async def _show_dashboard_data(self):
        """Show dashboard data"""
        logger.info("8. Dashboard Data Summary...")
        
        dashboard_data = self.dashboard.get_dashboard_data()
        overview = dashboard_data.get('overview', {})
        
        logger.info(f"   System Health: {overview.get('system_health', 'unknown')}")
        logger.info(f"   CPU Usage: {overview.get('cpu_usage_percent', 0):.1f}%")
        logger.info(f"   Memory Usage: {overview.get('memory_usage_percent', 0):.1f}%")
        logger.info(f"   Total Networks: {overview.get('total_networks', 0)}")
        logger.info(f"   Total Clients: {overview.get('total_clients', 0)}")
        logger.info(f"   Active Clients: {overview.get('active_clients', 0)}")
        
        # Show performance metrics for each network
        for network in self.demo_networks:
            metrics = self.dashboard.get_network_performance_metrics(network.network_id, 10)
            summary = metrics.get('summary', {})
            
            if summary:
                logger.info(f"   {network.network_name} Performance (last 10 min):")
                logger.info(f"     Avg CPU: {summary.get('cpu_avg', 0):.1f}%")
                logger.info(f"     Avg Memory: {summary.get('memory_avg', 0):.0f} MB")
                logger.info(f"     Data Points: {summary.get('data_points', 0)}")
        
        logger.info("✓ Dashboard data displayed")
        await asyncio.sleep(2)
    
    async def _test_network_management(self):
        """Test network management operations"""
        logger.info("9. Testing Network Management Operations...")
        
        # Test network details retrieval
        for network in self.demo_networks:
            details = self.service.get_network_details(network.network_id)
            if details:
                logger.info(f"   {network.network_name} Details:")
                logger.info(f"     Network ID: {network.network_id}")
                logger.info(f"     Model: {details['network_info']['model_id']}")
                logger.info(f"     Clients: {len(details['clients'])}")
                logger.info(f"     Created: {details['network_info']['created_at']}")
        
        # Test client reassignment
        if len(self.demo_clients) >= 2 and len(self.demo_networks) >= 2:
            client_to_move = self.demo_clients[0]
            target_network = self.demo_networks[1]
            
            logger.info(f"   Reassigning {client_to_move} to {target_network.network_name}")
            
            success = await self.service.assign_client_to_network(
                client_id=client_to_move,
                network_id=target_network.network_id
            )
            
            if success:
                logger.info(f"     ✓ Reassignment successful")
            else:
                logger.info(f"     ✗ Reassignment failed")
        
        logger.info("✓ Network management operations tested")
        await asyncio.sleep(1)
    
    async def _show_final_statistics(self):
        """Show final comprehensive statistics"""
        logger.info("10. Final Statistics Summary...")
        
        # Service statistics
        stats = self.service.get_service_statistics()
        
        logger.info("   Service Statistics:")
        service_info = stats.get('service', {})
        for key, value in service_info.items():
            logger.info(f"     {key}: {value}")
        
        # Resource utilization
        logger.info("   Resource Utilization:")
        system_resources = stats.get('system_resources', {})
        if 'system' in system_resources:
            system_info = system_resources['system']
            logger.info(f"     CPU Usage: {system_info.get('cpu_usage_percent', 0):.1f}%")
            logger.info(f"     Memory Used: {system_info.get('memory_used_gb', 0):.1f} GB")
            logger.info(f"     Memory Available: {system_info.get('memory_available_gb', 0):.1f} GB")
        
        if 'allocation' in system_resources:
            allocation_info = system_resources['allocation']
            logger.info(f"     Networks: {allocation_info.get('networks_count', 0)}")
            logger.info(f"     CPU Allocated: {allocation_info.get('total_allocated_cpu_percent', 0):.1f}%")
            logger.info(f"     Memory Allocated: {allocation_info.get('total_allocated_memory_mb', 0):.0f} MB")
        
        # Network summary
        logger.info("   Network Summary:")
        networks = self.service.get_network_list()
        for network in networks:
            logger.info(f"     {network['network_name']}:")
            logger.info(f"       ID: {network['network_id']}")
            logger.info(f"       Model: {network['model_id']}")
            logger.info(f"       Type: {network['network_type']}")
            logger.info(f"       Status: {network['status']}")
            logger.info(f"       Clients: {network['current_clients']}/{network['max_clients']}")
        
        logger.info("✓ Final statistics displayed")
    
    async def _show_gui_dashboard(self):
        """Show GUI dashboard if available"""
        logger.info("11. Launching GUI Dashboard...")
        
        try:
            from network_dashboard import NetworkDashboardWidget
            import sys
            
            # Check if PyQt6 is available
            try:
                from PyQt6.QtWidgets import QApplication
                
                app = QApplication(sys.argv)
                dashboard_widget = NetworkDashboardWidget(self.service)
                dashboard_widget.show()
                
                logger.info("   GUI Dashboard launched - close window to continue")
                
                # Run for a short time to show the dashboard
                await asyncio.sleep(5)
                
            except ImportError:
                logger.warning("   PyQt6 not available - GUI dashboard cannot be displayed")
                
        except Exception as e:
            logger.error(f"   Failed to launch GUI dashboard: {e}")
    
    async def _cleanup(self):
        """Clean up demo resources"""
        logger.info("Cleaning up demo resources...")
        
        try:
            # Remove all client assignments
            for client_id in self.demo_clients:
                self.service.client_assignment_manager.remove_client_assignment(client_id)
            
            # Delete all demo networks
            for network in self.demo_networks:
                await self.service.delete_network(network.network_id)
            
            # Stop services
            self.dashboard.stop_dashboard()
            await self.service.stop_service()
            
            logger.info("✓ Cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def _setup_demo_license(self):
        """Setup demo license for testing"""
        from unittest.mock import Mock
        
        # Create mock license
        mock_license = Mock()
        mock_license.plan = SubscriptionTier.ENT  # Enterprise for unlimited networks
        mock_license.max_clients = -1  # Unlimited clients
        
        # Create mock license enforcer
        mock_enforcer = Mock()
        mock_enforcer.get_license_status.return_value = {'valid': True, 'status': 'active'}
        mock_enforcer.current_license = mock_license
        mock_enforcer.check_model_access_allowed.return_value = True
        
        # Replace license enforcer
        self.service.license_enforcer = mock_enforcer
        
        logger.info("✓ Demo license configured (Enterprise tier)")


async def main():
    """Main demo function"""
    parser = argparse.ArgumentParser(description="Multi-Network Service Demo")
    parser.add_argument('--gui', action='store_true', help='Show GUI dashboard')
    parser.add_argument('--duration', type=int, default=60, help='Demo duration in seconds')
    parser.add_argument('--storage', type=str, help='Storage directory for networks')
    
    args = parser.parse_args()
    
    # Create and run demo
    demo = MultiNetworkDemo(storage_dir=args.storage)
    
    try:
        await demo.run_demo(duration=args.duration, show_gui=args.gui)
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run demo
    asyncio.run(main())