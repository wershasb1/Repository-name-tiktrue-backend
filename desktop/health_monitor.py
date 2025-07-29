"""
Network Health Monitoring System
Provides comprehensive health monitoring for all active networks with heartbeat mechanism,
automatic failure detection, and network status reporting
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import websockets
from pathlib import Path

from core.service_runner import MultiNetworkServiceRunner, ServiceStatus, NetworkService
from api_client import NetworkConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HealthMonitor")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/health_monitor.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class NetworkHealthInfo:
    """Network health information"""
    network_id: str
    status: HealthStatus
    last_heartbeat: datetime
    response_time: float
    error_count: int = 0
    consecutive_failures: int = 0
    uptime_seconds: float = 0.0
    client_connections: int = 0
    request_count: int = 0
    recent_errors: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerHealthInfo:
    """Worker node health information"""
    worker_id: str
    network_id: str
    status: HealthStatus
    last_heartbeat: datetime
    response_time: float
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    gpu_usage: float = 0.0
    error_count: int = 0
    consecutive_failures: int = 0
    worker_host: str = "localhost"
    worker_port: int = 0
    model_blocks: List[str] = field(default_factory=list)
    license_valid: bool = True
    last_license_check: datetime = field(default_factory=datetime.now)


@dataclass
class AdminNotification:
    """Admin notification for system events"""
    notification_id: str
    timestamp: datetime
    severity: str  # "info", "warning", "error", "critical"
    source: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


class HealthMonitor:
    """Network health monitoring system"""
    
    def __init__(self, 
                 service_runner: Optional[MultiNetworkServiceRunner] = None,
                 heartbeat_interval: int = 30,
                 failure_threshold: int = 3,
                 warning_threshold: int = 2):
        """
        Initialize health monitor
        
        Args:
            service_runner: MultiNetworkServiceRunner instance
            heartbeat_interval: Heartbeat check interval in seconds
            failure_threshold: Number of consecutive failures before marking as critical
            warning_threshold: Number of consecutive failures before marking as warning
        """
        self.service_runner = service_runner
        self.heartbeat_interval = heartbeat_interval
        self.failure_threshold = failure_threshold
        self.warning_threshold = warning_threshold
        
        # Health tracking
        self.network_health: Dict[str, NetworkHealthInfo] = {}
        self.worker_health: Dict[str, WorkerHealthInfo] = {}
        
        # Monitoring state
        self.monitoring_active = False
        self.monitoring_task = None
        self.worker_monitoring_task = None
        
        # Event callbacks
        self.health_change_callbacks: List[Callable[[str, HealthStatus, HealthStatus], None]] = []
        self.failure_callbacks: List[Callable[[str, str], None]] = []
        self.worker_failure_callbacks: List[Callable[[str, str], None]] = []
        
        # Admin notifications
        self.admin_notifications: List[AdminNotification] = []
        self.notification_callbacks: List[Callable[[AdminNotification], None]] = []
        
        # Performance tracking
        self.start_time = datetime.now()
        
        # License validator for worker license checks
        from security.license_validator import LicenseValidator
        self.license_validator = LicenseValidator()
    
    def add_health_change_callback(self, callback: Callable[[str, HealthStatus, HealthStatus], None]):
        """Add callback for health status changes"""
        self.health_change_callbacks.append(callback)
    
    def add_failure_callback(self, callback: Callable[[str, str], None]):
        """Add callback for network failures"""
        self.failure_callbacks.append(callback)
    
    async def start_monitoring(self):
        """Start health monitoring"""
        if self.monitoring_active:
            logger.warning("Health monitoring already active")
            return
        
        logger.info("Starting health monitoring")
        self.monitoring_active = True
        self.start_time = datetime.now()
        
        # Start monitoring tasks
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.worker_monitoring_task = asyncio.create_task(self._worker_monitoring_loop())
        
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        if not self.monitoring_active:
            logger.warning("Health monitoring not active")
            return
        
        logger.info("Stopping health monitoring")
        self.monitoring_active = False
        
        # Cancel monitoring tasks
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
        
        if self.worker_monitoring_task:
            self.worker_monitoring_task.cancel()
            try:
                await self.worker_monitoring_task
            except asyncio.CancelledError:
                pass
            self.worker_monitoring_task = None
        
        logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        try:
            while self.monitoring_active:
                await self._check_all_networks()
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
    
    async def _check_all_networks(self):
        """Check health of all networks"""
        if not self.service_runner:
            return
        
        # Get current networks
        current_networks = set(self.service_runner.networks.keys())
        
        # Remove health info for networks that no longer exist
        for network_id in list(self.network_health.keys()):
            if network_id not in current_networks:
                del self.network_health[network_id]
        
        # Check each network
        for network_id, network_service in self.service_runner.networks.items():
            await self._check_network_health(network_id, network_service)
    
    async def _check_network_health(self, network_id: str, network_service: NetworkService):
        """Check health of a specific network"""
        start_time = time.time()
        
        try:
            # Get or create health info
            if network_id not in self.network_health:
                self.network_health[network_id] = NetworkHealthInfo(
                    network_id=network_id,
                    status=HealthStatus.UNKNOWN,
                    last_heartbeat=datetime.now(),
                    response_time=0.0
                )
            
            health_info = self.network_health[network_id]
            old_status = health_info.status
            
            # Check network status
            if network_service.status == ServiceStatus.RUNNING:
                # Try to ping the network
                success, response_time = await self._ping_network(network_service.config)
                
                if success:
                    # Network is healthy
                    health_info.consecutive_failures = 0
                    health_info.last_heartbeat = datetime.now()
                    health_info.response_time = response_time
                    health_info.status = HealthStatus.HEALTHY
                    
                    # Update performance metrics
                    await self._update_performance_metrics(network_id, network_service, health_info)
                else:
                    # Network ping failed
                    health_info.consecutive_failures += 1
                    health_info.error_count += 1
                    
                    # Determine status based on failure count
                    if health_info.consecutive_failures >= self.failure_threshold:
                        health_info.status = HealthStatus.CRITICAL
                    elif health_info.consecutive_failures >= self.warning_threshold:
                        health_info.status = HealthStatus.WARNING
                    else:
                        health_info.status = HealthStatus.HEALTHY
                    
                    # Add error to recent errors
                    error_msg = f"Network ping failed (attempt {health_info.consecutive_failures})"
                    health_info.recent_errors.append(f"{datetime.now().isoformat()}: {error_msg}")
                    
                    # Keep only last 10 errors
                    if len(health_info.recent_errors) > 10:
                        health_info.recent_errors.pop(0)
            
            elif network_service.status == ServiceStatus.STARTING:
                health_info.status = HealthStatus.WARNING
            elif network_service.status == ServiceStatus.STOPPED:
                health_info.status = HealthStatus.CRITICAL
            else:
                health_info.status = HealthStatus.CRITICAL
            
            # Calculate uptime
            health_info.uptime_seconds = (datetime.now() - self.start_time).total_seconds()
            
            # Notify callbacks if status changed
            if old_status != health_info.status:
                for callback in self.health_change_callbacks:
                    try:
                        callback(network_id, old_status, health_info.status)
                    except Exception as e:
                        logger.error(f"Error in health change callback: {e}")
                
                # Notify failure callbacks for critical status
                if health_info.status == HealthStatus.CRITICAL:
                    for callback in self.failure_callbacks:
                        try:
                            callback(network_id, f"Network {network_id} is in critical state")
                        except Exception as e:
                            logger.error(f"Error in failure callback: {e}")
        
        except Exception as e:
            logger.error(f"Error checking network {network_id} health: {e}")
            
            # Mark as unknown on error
            if network_id in self.network_health:
                self.network_health[network_id].status = HealthStatus.UNKNOWN
    
    async def _ping_network(self, config: NetworkConfig) -> tuple[bool, float]:
        """Ping a network to check if it's responsive"""
        start_time = time.time()
        
        try:
            # Try WebSocket connection
            uri = f"ws://{config.host}:{config.port}/ws"
            
            async with websockets.connect(uri, timeout=10) as websocket:
                # Send ping message
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(ping_message))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)
                
                # Check if it's a valid pong response
                if response_data.get("type") == "pong":
                    response_time = time.time() - start_time
                    return True, response_time
                else:
                    return False, 0.0
        
        except Exception as e:
            logger.debug(f"Network ping failed for {config.network_id}: {e}")
            return False, 0.0
    
    async def _update_performance_metrics(self, network_id: str, network_service: NetworkService, health_info: NetworkHealthInfo):
        """Update performance metrics for a network"""
        try:
            # Get service status
            service_status = self.service_runner.get_service_status()
            
            if "networks" in service_status and network_id in service_status["networks"]:
                network_status = service_status["networks"][network_id]
                
                # Update metrics
                health_info.client_connections = network_status.get("client_connections", 0)
                health_info.request_count = network_status.get("request_count", 0)
                
                # Update performance metrics
                health_info.performance_metrics.update({
                    "requests_per_minute": self._calculate_requests_per_minute(network_id),
                    "average_response_time": health_info.response_time,
                    "error_rate": self._calculate_error_rate(network_id),
                    "uptime_percentage": self._calculate_uptime_percentage(network_id)
                })
        
        except Exception as e:
            logger.error(f"Error updating performance metrics for {network_id}: {e}")
    
    def _calculate_requests_per_minute(self, network_id: str) -> float:
        """Calculate requests per minute for a network"""
        # This is a simplified calculation
        # In a real implementation, you'd track request timestamps
        if network_id in self.network_health:
            health_info = self.network_health[network_id]
            uptime_minutes = health_info.uptime_seconds / 60.0
            if uptime_minutes > 0:
                return health_info.request_count / uptime_minutes
        return 0.0
    
    def _calculate_error_rate(self, network_id: str) -> float:
        """Calculate error rate for a network"""
        if network_id in self.network_health:
            health_info = self.network_health[network_id]
            if health_info.request_count > 0:
                return (health_info.error_count / health_info.request_count) * 100.0
        return 0.0
    
    def _calculate_uptime_percentage(self, network_id: str) -> float:
        """Calculate uptime percentage for a network"""
        if network_id in self.network_health:
            health_info = self.network_health[network_id]
            total_time = (datetime.now() - self.start_time).total_seconds()
            if total_time > 0:
                # Simplified calculation - in reality you'd track downtime
                failure_time = health_info.consecutive_failures * self.heartbeat_interval
                uptime = max(0, total_time - failure_time)
                return (uptime / total_time) * 100.0
        return 0.0
    
    def get_network_health(self, network_id: str) -> Optional[NetworkHealthInfo]:
        """Get health information for a specific network"""
        return self.network_health.get(network_id)
    
    def get_all_network_health(self) -> Dict[str, NetworkHealthInfo]:
        """Get health information for all networks"""
        return self.network_health.copy()
    
    def get_overall_health_status(self) -> HealthStatus:
        """Get overall health status of all networks"""
        if not self.network_health:
            return HealthStatus.UNKNOWN
        
        statuses = [health.status for health in self.network_health.values()]
        
        # If any network is critical, overall is critical
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        
        # If any network has warning, overall is warning
        if HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        
        # If all networks are healthy, overall is healthy
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        
        return HealthStatus.UNKNOWN
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary for dashboard"""
        summary = {
            "overall_status": self.get_overall_health_status().value,
            "total_networks": len(self.network_health),
            "healthy_networks": sum(1 for h in self.network_health.values() if h.status == HealthStatus.HEALTHY),
            "warning_networks": sum(1 for h in self.network_health.values() if h.status == HealthStatus.WARNING),
            "critical_networks": sum(1 for h in self.network_health.values() if h.status == HealthStatus.CRITICAL),
            "total_requests": sum(h.request_count for h in self.network_health.values()),
            "total_errors": sum(h.error_count for h in self.network_health.values()),
            "total_connections": sum(h.client_connections for h in self.network_health.values()),
            "average_response_time": self._calculate_average_response_time(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "networks": {}
        }
        
        # Add individual network details
        for network_id, health_info in self.network_health.items():
            summary["networks"][network_id] = {
                "status": health_info.status.value,
                "last_heartbeat": health_info.last_heartbeat.isoformat(),
                "response_time": health_info.response_time,
                "error_count": health_info.error_count,
                "consecutive_failures": health_info.consecutive_failures,
                "uptime_seconds": health_info.uptime_seconds,
                "client_connections": health_info.client_connections,
                "request_count": health_info.request_count,
                "recent_errors": health_info.recent_errors[-5:],  # Last 5 errors
                "performance_metrics": health_info.performance_metrics
            }
        
        return summary
    
    def _calculate_average_response_time(self) -> float:
        """Calculate average response time across all networks"""
        if not self.network_health:
            return 0.0
        
        total_time = sum(h.response_time for h in self.network_health.values())
        return total_time / len(self.network_health)
    
    async def _worker_monitoring_loop(self):
        """Worker monitoring loop"""
        try:
            while self.monitoring_active:
                await self._check_all_workers()
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:
            logger.info("Worker monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in worker monitoring loop: {e}")
    
    async def _check_all_workers(self):
        """Check health of all worker nodes"""
        if not self.service_runner:
            return
        
        # Get current workers from all networks
        current_workers = set()
        for network_id, network_service in self.service_runner.networks.items():
            if hasattr(network_service.config, 'nodes') and network_service.config.nodes:
                for node_id, node_config in network_service.config.nodes.items():
                    worker_id = f"{network_id}_{node_id}"
                    current_workers.add(worker_id)
                    await self._check_worker_health(worker_id, network_id, node_config)
        
        # Remove health info for workers that no longer exist
        for worker_id in list(self.worker_health.keys()):
            if worker_id not in current_workers:
                del self.worker_health[worker_id]
    
    async def _check_worker_health(self, worker_id: str, network_id: str, node_config: Dict[str, Any]):
        """Check health of a specific worker node"""
        start_time = time.time()
        
        try:
            # Get or create worker health info
            if worker_id not in self.worker_health:
                self.worker_health[worker_id] = WorkerHealthInfo(
                    worker_id=worker_id,
                    network_id=network_id,
                    status=HealthStatus.UNKNOWN,
                    last_heartbeat=datetime.now(),
                    response_time=0.0,
                    worker_host=node_config.get("host", "localhost"),
                    worker_port=node_config.get("port", 0),
                    model_blocks=node_config.get("blocks", [])
                )
            
            worker_info = self.worker_health[worker_id]
            old_status = worker_info.status
            
            # Ping worker node
            success, response_time = await self._ping_worker(worker_info)
            
            if success:
                # Worker is healthy
                worker_info.consecutive_failures = 0
                worker_info.last_heartbeat = datetime.now()
                worker_info.response_time = response_time
                worker_info.status = HealthStatus.HEALTHY
                
                # Check license validity
                await self._check_worker_license(worker_info)
                
                # Update performance metrics
                await self._update_worker_metrics(worker_info)
            else:
                # Worker ping failed
                worker_info.consecutive_failures += 1
                worker_info.error_count += 1
                
                # Determine status based on failure count
                if worker_info.consecutive_failures >= self.failure_threshold:
                    worker_info.status = HealthStatus.CRITICAL
                elif worker_info.consecutive_failures >= self.warning_threshold:
                    worker_info.status = HealthStatus.WARNING
                else:
                    worker_info.status = HealthStatus.HEALTHY
            
            # Notify callbacks if status changed
            if old_status != worker_info.status:
                # Create admin notification for worker status changes
                await self._create_admin_notification(
                    severity="warning" if worker_info.status == HealthStatus.WARNING else "critical" if worker_info.status == HealthStatus.CRITICAL else "info",
                    source=f"Worker {worker_id}",
                    message=f"Worker status changed from {old_status.value} to {worker_info.status.value}",
                    details={
                        "worker_id": worker_id,
                        "network_id": network_id,
                        "old_status": old_status.value,
                        "new_status": worker_info.status.value,
                        "consecutive_failures": worker_info.consecutive_failures,
                        "response_time": worker_info.response_time
                    }
                )
                
                # Notify worker failure callbacks for critical status
                if worker_info.status == HealthStatus.CRITICAL:
                    for callback in self.worker_failure_callbacks:
                        try:
                            callback(worker_id, f"Worker {worker_id} is in critical state")
                        except Exception as e:
                            logger.error(f"Error in worker failure callback: {e}")
        
        except Exception as e:
            logger.error(f"Error checking worker {worker_id} health: {e}")
            
            # Mark as unknown on error
            if worker_id in self.worker_health:
                self.worker_health[worker_id].status = HealthStatus.UNKNOWN
    
    async def _ping_worker(self, worker_info: WorkerHealthInfo) -> tuple[bool, float]:
        """Ping a worker node to check if it's responsive"""
        start_time = time.time()
        
        try:
            # Try WebSocket connection to worker
            uri = f"ws://{worker_info.worker_host}:{worker_info.worker_port}/ws"
            
            async with websockets.connect(uri, timeout=10) as websocket:
                # Send heartbeat ping
                heartbeat_message = {
                    "type": "heartbeat",
                    "worker_id": worker_info.worker_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(heartbeat_message))
                
                # Wait for response with 30-second timeout as specified
                response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                response_data = json.loads(response)
                
                # Check if it's a valid heartbeat response
                if response_data.get("type") == "heartbeat_response":
                    response_time = time.time() - start_time
                    return True, response_time
                else:
                    return False, 0.0
        
        except Exception as e:
            logger.debug(f"Worker ping failed for {worker_info.worker_id}: {e}")
            return False, 0.0
    
    async def _check_worker_license(self, worker_info: WorkerHealthInfo):
        """Check license validity for a worker"""
        try:
            # Check if license check is needed (every 5 minutes)
            if (datetime.now() - worker_info.last_license_check).total_seconds() < 300:
                return
            
            # Get current license from service runner
            if self.service_runner and self.service_runner.current_license:
                license_info = self.service_runner.current_license
                
                # Validate license
                validation_result = self.security.license_validator.validate_license_key(license_info.license_key)
                
                worker_info.license_valid = validation_result.status.value == "valid"
                worker_info.last_license_check = datetime.now()
                
                # Create notification if license becomes invalid
                if not worker_info.license_valid:
                    await self._create_admin_notification(
                        severity="critical",
                        source=f"Worker {worker_info.worker_id}",
                        message=f"License validation failed for worker",
                        details={
                            "worker_id": worker_info.worker_id,
                            "network_id": worker_info.network_id,
                            "license_status": validation_result.status.value,
                            "validation_message": validation_result.message
                        }
                    )
            else:
                worker_info.license_valid = False
                
        except Exception as e:
            logger.error(f"Error checking worker license for {worker_info.worker_id}: {e}")
            worker_info.license_valid = False
    
    async def _update_worker_metrics(self, worker_info: WorkerHealthInfo):
        """Update performance metrics for a worker"""
        try:
            # This would typically query the worker for its current metrics
            # For now, we'll simulate some basic metrics
            
            # In a real implementation, you would send a metrics request to the worker
            # and parse the response to get actual CPU, memory, and GPU usage
            
            # Simulate metrics based on response time and status
            base_cpu = 20.0  # Base CPU usage
            base_memory = 30.0  # Base memory usage
            base_gpu = 40.0  # Base GPU usage
            
            # Adjust based on response time (higher response time = higher usage)
            response_factor = min(2.0, worker_info.response_time / 0.1)  # Normalize to 100ms baseline
            
            worker_info.cpu_usage = min(100.0, base_cpu * response_factor)
            worker_info.memory_usage = min(100.0, base_memory * response_factor)
            worker_info.gpu_usage = min(100.0, base_gpu * response_factor)
            
        except Exception as e:
            logger.error(f"Error updating worker metrics for {worker_info.worker_id}: {e}")
    
    async def _create_admin_notification(self, severity: str, source: str, message: str, details: Dict[str, Any] = None):
        """Create an admin notification"""
        try:
            notification = AdminNotification(
                notification_id=f"notif_{int(time.time() * 1000)}_{len(self.admin_notifications)}",
                timestamp=datetime.now(),
                severity=severity,
                source=source,
                message=message,
                details=details or {}
            )
            
            self.admin_notifications.append(notification)
            
            # Keep only last 100 notifications
            if len(self.admin_notifications) > 100:
                self.admin_notifications = self.admin_notifications[-100:]
            
            # Notify callbacks
            for callback in self.notification_callbacks:
                try:
                    callback(notification)
                except Exception as e:
                    logger.error(f"Error in notification callback: {e}")
            
            logger.info(f"Admin notification created: {severity.upper()} - {message}")
            
        except Exception as e:
            logger.error(f"Error creating admin notification: {e}")
    
    def monitor_worker_health(self, worker_id: str) -> Optional[WorkerHealthInfo]:
        """
        Monitor worker health function as specified in requirements
        
        Args:
            worker_id: ID of the worker to monitor
            
        Returns:
            WorkerHealthInfo if worker exists, None otherwise
        """
        return self.worker_health.get(worker_id)
    
    def get_all_worker_health(self) -> Dict[str, WorkerHealthInfo]:
        """Get health information for all workers"""
        return self.worker_health.copy()
    
    def get_admin_notifications(self, unacknowledged_only: bool = False) -> List[AdminNotification]:
        """Get admin notifications"""
        if unacknowledged_only:
            return [n for n in self.admin_notifications if not n.acknowledged]
        return self.admin_notifications.copy()
    
    def acknowledge_notification(self, notification_id: str, acknowledged_by: str = "admin") -> bool:
        """Acknowledge an admin notification"""
        try:
            for notification in self.admin_notifications:
                if notification.notification_id == notification_id:
                    notification.acknowledged = True
                    notification.acknowledged_at = datetime.now()
                    notification.acknowledged_by = acknowledged_by
                    logger.info(f"Notification acknowledged: {notification_id} by {acknowledged_by}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error acknowledging notification {notification_id}: {e}")
            return False
    
    def add_worker_failure_callback(self, callback: Callable[[str, str], None]):
        """Add callback for worker failures"""
        self.worker_failure_callbacks.append(callback)
    
    def add_notification_callback(self, callback: Callable[[AdminNotification], None]):
        """Add callback for admin notifications"""
        self.notification_callbacks.append(callback)


class AsyncHealthMonitor:
    """Async wrapper for HealthMonitor"""
    
    def __init__(self, 
                 service_runner: Optional[MultiNetworkServiceRunner] = None,
                 heartbeat_interval: int = 30,
                 failure_threshold: int = 3,
                 warning_threshold: int = 2):
        """
        Initialize async health monitor
        
        Args:
            service_runner: MultiNetworkServiceRunner instance
            heartbeat_interval: Heartbeat check interval in seconds
            failure_threshold: Number of consecutive failures before marking as critical
            warning_threshold: Number of consecutive failures before marking as warning
        """
        self.monitor = HealthMonitor(
            service_runner=service_runner,
            heartbeat_interval=heartbeat_interval,
            failure_threshold=failure_threshold,
            warning_threshold=warning_threshold
        )
    
    async def start(self):
        """Start health monitoring"""
        await self.monitor.start_monitoring()
    
    async def stop(self):
        """Stop health monitoring"""
        await self.monitor.stop_monitoring()
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary"""
        return self.monitor.get_health_summary()
    
    def add_health_change_callback(self, callback: Callable[[str, HealthStatus, HealthStatus], None]):
        """Add health change callback"""
        self.monitor.add_health_change_callback(callback)
    
    def add_failure_callback(self, callback: Callable[[str, str], None]):
        """Add failure callback"""
        self.monitor.add_failure_callback(callback)


async def run_health_monitor_standalone():
    """Run health monitor standalone for testing"""
    from core.service_runner import MultiNetworkServiceRunner
    
    # Create service runner
    service_runner = MultiNetworkServiceRunner()
    
    # Create health monitor
    health_monitor = AsyncHealthMonitor(service_runner=service_runner)
    
    # Add callbacks
    def on_health_change(network_id: str, old_status: HealthStatus, new_status: HealthStatus):
        print(f"Network {network_id} status changed: {old_status.value} -> {new_status.value}")
    
    def on_failure(network_id: str, message: str):
        print(f"Network failure: {network_id} - {message}")
    
    health_monitor.add_health_change_callback(on_health_change)
    health_monitor.add_failure_callback(on_failure)
    
    try:
        # Start service runner
        await service_runner.start()
        
        # Start health monitoring
        await health_monitor.start()
        
        print("Health monitoring started. Press Ctrl+C to stop.")
        
        # Print health summary periodically
        while True:
            await asyncio.sleep(10)
            summary = health_monitor.get_health_summary()
            print(f"Health Summary: {summary['overall_status']} - "
                  f"{summary['healthy_networks']}/{summary['total_networks']} networks healthy")
    
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        # Stop health monitoring
        await health_monitor.stop()
        
        # Stop service runner
        await service_runner.shutdown()


def main():
    """Main entry point"""
    asyncio.run(run_health_monitor_standalone())


if __name__ == "__main__":
    main()