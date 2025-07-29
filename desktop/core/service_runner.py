"""
Service Runner for TikTrue Distributed LLM Platform
Main entry point for Windows service execution - handles core platform without models

This module provides the service entry point that:
1. Does NOT include model files (following user journey - models downloaded after installation)
2. Handles both Admin and Client mode operations
3. Manages network discovery and communication
4. Provides license validation and management
5. Integrates with service monitoring and health checks

Requirements addressed:
- 13.2: Windows service background operation
- 13.3: Automatic startup configuration
- Service monitoring and health checks integration
"""

import os
import sys
import json
import logging
import asyncio
import signal
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import core modules
try:
    from core.config_manager import ConfigManager
    from core.network_manager import NetworkManager
    from network.network_discovery import NetworkDiscovery
    from network.unified_websocket_server import UnifiedWebSocketServer
    from security.license_validator import LicenseValidator
    from service_monitor import get_service_monitor, start_monitoring, stop_monitoring
    from custom_logging import setup_logging
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    sys.exit(1)

# Setup logging
logger = logging.getLogger("ServiceRunner")


class ServiceMode:
    """Service operation modes"""
    ADMIN = "admin"
    CLIENT = "client"
    DISCOVERY = "discovery"  # Discovery-only mode for service


class TikTrueServiceRunner:
    """
    Main service runner for TikTrue Distributed LLM Platform
    Handles core platform operations without model dependencies
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the service runner"""
        self.config_path = config_path or "network_config.json"
        self.config_manager = None
        self.network_manager = None
        self.network_discovery = None
        self.websocket_server = None
        self.license_validator = None
        
        # Service state
        self.is_running = False
        self.service_mode = ServiceMode.DISCOVERY  # Default to discovery mode
        self.shutdown_event = asyncio.Event()
        
        # Background tasks
        self.background_tasks = []
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize core service components"""
        try:
            logger.info("Initializing service components...")
            
            # Setup logging
            setup_logging()
            
            # Initialize configuration manager
            self.config_manager = ConfigManager(self.config_path)
            
            # Load service configuration
            service_config = self._load_service_config()
            
            # Determine service mode
            self.service_mode = service_config.get("service_mode", ServiceMode.DISCOVERY)
            
            # Initialize license validator
            self.license_validator = LicenseValidator()
            
            # Initialize network components
            self.network_discovery = NetworkDiscovery()
            self.network_manager = NetworkManager(self.config_manager.config)
            
            # Initialize WebSocket server for communication
            websocket_config = {
                "host": service_config.get("websocket_host", "0.0.0.0"),
                "port": service_config.get("websocket_port", 8765),
                "ssl_context": None  # Can be configured for secure connections
            }
            self.websocket_server = UnifiedWebSocketServer(websocket_config)
            
            logger.info(f"Service components initialized in {self.service_mode} mode")
            
        except Exception as e:
            logger.error(f"Failed to initialize service components: {e}")
            raise
    
    def _load_service_config(self) -> Dict[str, Any]:
        """Load service-specific configuration"""
        try:
            service_config_path = "service_config.json"
            
            if Path(service_config_path).exists():
                with open(service_config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded service configuration from {service_config_path}")
                return config
            else:
                # Default service configuration
                default_config = {
                    "service_mode": ServiceMode.DISCOVERY,
                    "websocket_host": "0.0.0.0",
                    "websocket_port": 8765,
                    "enable_discovery": True,
                    "enable_monitoring": True,
                    "auto_detect_mode": True,
                    "license_check_interval": 3600,  # 1 hour
                    "network_scan_interval": 300,   # 5 minutes
                    "health_check_interval": 60,    # 1 minute
                    "log_level": "INFO"
                }
                
                # Save default configuration
                with open(service_config_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                
                logger.info("Created default service configuration")
                return default_config
                
        except Exception as e:
            logger.error(f"Failed to load service configuration: {e}")
            return {}
    
    async def start_service(self):
        """Start the service with all components"""
        try:
            logger.info("Starting TikTrue LLM Service...")
            
            if self.is_running:
                logger.warning("Service is already running")
                return
            
            self.is_running = True
            
            # Start service monitoring
            if self._should_enable_monitoring():
                logger.info("Starting service monitoring...")
                start_monitoring()
            
            # Start network discovery
            if self._should_enable_discovery():
                logger.info("Starting network discovery...")
                await self._start_network_discovery()
            
            # Start WebSocket server
            logger.info("Starting WebSocket server...")
            await self._start_websocket_server()
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Register signal handlers
            self._register_signal_handlers()
            
            logger.info(f"TikTrue LLM Service started successfully in {self.service_mode} mode")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            raise
        finally:
            await self.stop_service()
    
    async def stop_service(self):
        """Stop the service and cleanup resources"""
        try:
            logger.info("Stopping TikTrue LLM Service...")
            
            if not self.is_running:
                logger.warning("Service is not running")
                return
            
            self.is_running = False
            
            # Stop background tasks
            await self._stop_background_tasks()
            
            # Stop WebSocket server
            if self.websocket_server:
                logger.info("Stopping WebSocket server...")
                await self.websocket_server.stop()
            
            # Stop network discovery
            if self.network_discovery:
                logger.info("Stopping network discovery...")
                await self.network_discovery.stop()
            
            # Stop service monitoring
            logger.info("Stopping service monitoring...")
            stop_monitoring()
            
            logger.info("TikTrue LLM Service stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping service: {e}")
    
    def _should_enable_monitoring(self) -> bool:
        """Check if monitoring should be enabled"""
        service_config = self._load_service_config()
        return service_config.get("enable_monitoring", True)
    
    def _should_enable_discovery(self) -> bool:
        """Check if network discovery should be enabled"""
        service_config = self._load_service_config()
        return service_config.get("enable_discovery", True)
    
    async def _start_network_discovery(self):
        """Start network discovery service"""
        try:
            # Configure discovery based on service mode
            if self.service_mode == ServiceMode.ADMIN:
                # Admin mode: announce network availability
                await self.network_discovery.start_announcement()
            elif self.service_mode == ServiceMode.CLIENT:
                # Client mode: discover available networks
                await self.network_discovery.start_discovery()
            else:
                # Discovery mode: both announce and discover
                await self.network_discovery.start_announcement()
                await self.network_discovery.start_discovery()
            
            logger.info(f"Network discovery started in {self.service_mode} mode")
            
        except Exception as e:
            logger.error(f"Failed to start network discovery: {e}")
            raise
    
    async def _start_websocket_server(self):
        """Start WebSocket server for communication"""
        try:
            await self.websocket_server.start()
            logger.info("WebSocket server started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise
    
    async def _start_background_tasks(self):
        """Start background maintenance tasks"""
        try:
            service_config = self._load_service_config()
            
            # License validation task
            if service_config.get("license_check_interval", 0) > 0:
                task = asyncio.create_task(self._license_validation_task(
                    service_config["license_check_interval"]
                ))
                self.background_tasks.append(task)
            
            # Network scanning task
            if service_config.get("network_scan_interval", 0) > 0:
                task = asyncio.create_task(self._network_scan_task(
                    service_config["network_scan_interval"]
                ))
                self.background_tasks.append(task)
            
            # Health monitoring task
            if service_config.get("health_check_interval", 0) > 0:
                task = asyncio.create_task(self._health_monitoring_task(
                    service_config["health_check_interval"]
                ))
                self.background_tasks.append(task)
            
            logger.info(f"Started {len(self.background_tasks)} background tasks")
            
        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")
    
    async def _stop_background_tasks(self):
        """Stop all background tasks"""
        try:
            if self.background_tasks:
                logger.info(f"Stopping {len(self.background_tasks)} background tasks...")
                
                # Cancel all tasks
                for task in self.background_tasks:
                    task.cancel()
                
                # Wait for tasks to complete
                await asyncio.gather(*self.background_tasks, return_exceptions=True)
                
                self.background_tasks.clear()
                logger.info("Background tasks stopped")
            
        except Exception as e:
            logger.error(f"Error stopping background tasks: {e}")
    
    async def _license_validation_task(self, interval_seconds: int):
        """Background task for periodic license validation"""
        while self.is_running:
            try:
                logger.debug("Performing periodic license validation...")
                
                # Validate license
                is_valid = await self._validate_license()
                
                if not is_valid:
                    logger.warning("License validation failed - service may have limited functionality")
                
            except Exception as e:
                logger.error(f"License validation task error: {e}")
            
            # Wait for next check
            await asyncio.sleep(interval_seconds)
    
    async def _network_scan_task(self, interval_seconds: int):
        """Background task for periodic network scanning"""
        while self.is_running:
            try:
                logger.debug("Performing periodic network scan...")
                
                # Refresh network discovery
                if self.network_discovery:
                    await self.network_discovery.refresh_discovery()
                
            except Exception as e:
                logger.error(f"Network scan task error: {e}")
            
            # Wait for next scan
            await asyncio.sleep(interval_seconds)
    
    async def _health_monitoring_task(self, interval_seconds: int):
        """Background task for health monitoring"""
        while self.is_running:
            try:
                logger.debug("Performing health monitoring check...")
                
                # Get service monitor and check health
                monitor = get_service_monitor()
                health_status = monitor.get_health_status()
                
                # Log critical issues
                if health_status.get("overall_status") == "critical":
                    logger.warning(f"Critical health issues detected: {health_status}")
                
            except Exception as e:
                logger.error(f"Health monitoring task error: {e}")
            
            # Wait for next check
            await asyncio.sleep(interval_seconds)
    
    async def _validate_license(self) -> bool:
        """Validate current license status"""
        try:
            if not self.license_validator:
                return False
            
            # Check license validity
            validation_result = self.license_validator.validate_license()
            
            return validation_result.get("valid", False)
            
        except Exception as e:
            logger.error(f"License validation error: {e}")
            return False
    
    def _register_signal_handlers(self):
        """Register signal handlers for graceful shutdown"""
        try:
            def signal_handler(signum, frame):
                logger.info(f"Received signal {signum}, initiating shutdown...")
                asyncio.create_task(self._shutdown_gracefully())
            
            # Register handlers for common shutdown signals
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Windows-specific signals
            if hasattr(signal, 'SIGBREAK'):
                signal.signal(signal.SIGBREAK, signal_handler)
            
            logger.info("Signal handlers registered")
            
        except Exception as e:
            logger.error(f"Failed to register signal handlers: {e}")
    
    async def _shutdown_gracefully(self):
        """Initiate graceful shutdown"""
        logger.info("Initiating graceful shutdown...")
        self.shutdown_event.set()
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status"""
        try:
            # Get service monitor status
            monitor = get_service_monitor()
            health_status = monitor.get_health_status()
            
            # Get license status
            license_status = "unknown"
            if self.license_validator:
                try:
                    validation_result = self.license_validator.validate_license()
                    license_status = "valid" if validation_result.get("valid", False) else "invalid"
                except:
                    license_status = "error"
            
            # Get network status
            network_status = {
                "discovery_active": self.network_discovery and self.network_discovery.is_running if hasattr(self.network_discovery, 'is_running') else False,
                "websocket_active": self.websocket_server and self.websocket_server.is_running if hasattr(self.websocket_server, 'is_running') else False
            }
            
            return {
                "service_running": self.is_running,
                "service_mode": self.service_mode,
                "license_status": license_status,
                "network_status": network_status,
                "health_status": health_status,
                "background_tasks": len(self.background_tasks),
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                "error": str(e),
                "last_updated": datetime.now().isoformat()
            }


async def main():
    """Main entry point for service runner"""
    try:
        # Parse command line arguments
        config_path = None
        if len(sys.argv) > 1:
            config_path = sys.argv[1]
        
        # Create and start service runner
        service_runner = TikTrueServiceRunner(config_path)
        
        logger.info("Starting TikTrue LLM Service Runner...")
        await service_runner.start_service()
        
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service runner error: {e}")
        sys.exit(1)


def run_service():
    """Synchronous entry point for Windows service"""
    try:
        # Set up event loop
        if sys.platform == "win32":
            # Use ProactorEventLoop on Windows for better compatibility
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Run the service
        asyncio.run(main())
        
    except Exception as e:
        logger.error(f"Failed to run service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_service()