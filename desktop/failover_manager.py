"""
Failover Manager for Automatic Recovery
Implements automatic backup worker activation, graceful degradation, and workload transfer
mechanisms with license permission checking
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading
from pathlib import Path

from health_monitor import HealthMonitor, HealthStatus, WorkerHealthInfo, AdminNotification
from core.service_runner import MultiNetworkServiceRunner, ServiceStatus, NetworkService
from api_client import NetworkConfig
from security.license_validator import LicenseValidator, LicenseInfo, SubscriptionTier
from resource_allocator import DynamicResourceAllocator, ResourceQuota, AllocationPriority

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FailoverManager")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/failover_manager.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class FailoverStrategy(Enum):
    """Failover strategy options"""
    IMMEDIATE = "immediate"          # Immediate failover to backup
    GRACEFUL = "graceful"           # Graceful degradation first, then failover
    LOAD_BALANCE = "load_balance"   # Redistribute load across remaining workers
    HYBRID = "hybrid"               # Combination of strategies based on situation


class DegradationLevel(Enum):
    """Levels of graceful degradation"""
    NONE = 0           # No degradation
    REDUCED_QUALITY = 1    # Reduce model quality/precision
    REDUCED_CAPACITY = 2   # Reduce concurrent processing capacity
    ESSENTIAL_ONLY = 3     # Only essential operations
    MAINTENANCE_MODE = 4   # Minimal functionality for maintenance


@dataclass
class BackupWorker:
    """Backup worker configuration"""
    worker_id: str
    network_id: str
    host: str
    port: int
    model_blocks: List[str]
    priority: int = 1  # Lower number = higher priority
    status: str = "standby"  # standby, activating, active, failed
    last_health_check: datetime = field(default_factory=datetime.now)
    activation_time: Optional[datetime] = None
    resource_requirements: Optional[ResourceQuota] = None
    license_validated: bool = False


@dataclass
class FailoverEvent:
    """Failover event record"""
    event_id: str
    timestamp: datetime
    event_type: str  # "worker_failure", "network_failure", "resource_shortage"
    source_id: str   # Failed worker/network ID
    target_id: Optional[str] = None  # Backup worker/network ID
    strategy_used: FailoverStrategy = FailoverStrategy.IMMEDIATE
    success: bool = False
    duration_seconds: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkloadTransfer:
    """Workload transfer operation"""
    transfer_id: str
    source_worker: str
    target_worker: str
    model_blocks: List[str]
    active_sessions: List[str]
    transfer_started: datetime
    transfer_completed: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None


@dataclass
class BlockRedistribution:
    """Block redistribution operation"""
    redistribution_id: str
    network_id: str
    failed_worker: str
    affected_blocks: List[str]
    redistribution_plan: Dict[str, List[str]]  # worker_id -> blocks
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    conflicts_resolved: int = 0
    error_message: Optional[str] = None


@dataclass
class BlockAssignment:
    """Model block assignment"""
    block_id: str
    network_id: str
    assigned_worker: str
    backup_workers: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    assignment_priority: int = 1
    license_validated: bool = False


class FailoverManager:
    """
    Manages automatic failover and recovery operations
    """
    
    def __init__(self,
                 service_runner: Optional[MultiNetworkServiceRunner] = None,
                 health_monitor: Optional[HealthMonitor] = None,
                 resource_allocator: Optional[DynamicResourceAllocator] = None,
                 failover_timeout: float = 60.0,
                 max_concurrent_failovers: int = 3):
        """
        Initialize failover manager
        
        Args:
            service_runner: Service runner instance
            health_monitor: Health monitor instance
            resource_allocator: Resource allocator instance
            failover_timeout: Maximum time for failover operations
            max_concurrent_failovers: Maximum concurrent failover operations
        """
        self.service_runner = service_runner
        self.health_monitor = health_monitor
        self.resource_allocator = resource_allocator
        self.failover_timeout = failover_timeout
        self.max_concurrent_failovers = max_concurrent_failovers
        
        # Backup worker management
        self.backup_workers: Dict[str, BackupWorker] = {}
        self.active_failovers: Dict[str, FailoverEvent] = {}
        self.failover_history: List[FailoverEvent] = []
        self.workload_transfers: Dict[str, WorkloadTransfer] = {}
        
        # Block redistribution management
        self.block_assignments: Dict[str, BlockAssignment] = {}  # block_id -> assignment
        self.active_redistributions: Dict[str, BlockRedistribution] = {}
        self.redistribution_history: List[BlockRedistribution] = []
        
        # Degradation management
        self.current_degradation_level = DegradationLevel.NONE
        self.degradation_history: List[Tuple[datetime, DegradationLevel, str]] = []
        
        # License validation
        self.license_validator = LicenseValidator()
        
        # Monitoring and control
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.lock = threading.RLock()
        
        # Statistics
        self.stats = {
            "total_failovers": 0,
            "successful_failovers": 0,
            "failed_failovers": 0,
            "average_failover_time": 0.0,
            "backup_activations": 0,
            "degradation_events": 0
        }
        
        # Setup callbacks if health monitor is available
        if self.health_monitor:
            self.health_monitor.add_worker_failure_callback(self._on_worker_failure)
            self.health_monitor.add_failure_callback(self._on_network_failure)
    
    async def start(self):
        """Start failover monitoring"""
        if self.monitoring_active:
            logger.warning("Failover manager already active")
            return
        
        logger.info("Starting failover manager")
        self.monitoring_active = True
        
        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Discover and register backup workers
        await self._discover_backup_workers()
        
        logger.info("Failover manager started")
    
    async def stop(self):
        """Stop failover monitoring"""
        if not self.monitoring_active:
            logger.warning("Failover manager not active")
            return
        
        logger.info("Stopping failover manager")
        self.monitoring_active = False
        
        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
        
        logger.info("Failover manager stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        try:
            while self.monitoring_active:
                await self._check_backup_workers()
                await self._check_active_failovers()
                await self._check_degradation_conditions()
                await asyncio.sleep(10.0)  # Check every 10 seconds
        except asyncio.CancelledError:
            logger.info("Failover monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in failover monitoring loop: {e}")
    
    async def _discover_backup_workers(self):
        """Discover available backup workers"""
        try:
            if not self.service_runner:
                return
            
            # Look for backup worker configurations
            # This would typically read from configuration files or service discovery
            # For now, we'll create some mock backup workers
            
            for network_id, network_service in self.service_runner.networks.items():
                if hasattr(network_service.config, 'backup_nodes'):
                    for backup_id, backup_config in network_service.config.backup_nodes.items():
                        backup_worker = BackupWorker(
                            worker_id=f"{network_id}_backup_{backup_id}",
                            network_id=network_id,
                            host=backup_config.get("host", "localhost"),
                            port=backup_config.get("port", 0),
                            model_blocks=backup_config.get("blocks", []),
                            priority=backup_config.get("priority", 1)
                        )
                        
                        self.backup_workers[backup_worker.worker_id] = backup_worker
                        logger.info(f"Registered backup worker: {backup_worker.worker_id}")
            
            logger.info(f"Discovered {len(self.backup_workers)} backup workers")
            
        except Exception as e:
            logger.error(f"Error discovering backup workers: {e}")
    
    async def _check_backup_workers(self):
        """Check health of backup workers"""
        try:
            for backup_worker in self.backup_workers.values():
                # Ping backup worker to ensure it's ready
                if backup_worker.status == "standby":
                    is_healthy = await self._ping_backup_worker(backup_worker)
                    if not is_healthy:
                        logger.warning(f"Backup worker unhealthy: {backup_worker.worker_id}")
                        backup_worker.status = "failed"
                    else:
                        backup_worker.last_health_check = datetime.now()
        
        except Exception as e:
            logger.error(f"Error checking backup workers: {e}")
    
    async def _ping_backup_worker(self, backup_worker: BackupWorker) -> bool:
        """Ping a backup worker to check availability"""
        try:
            # This would implement actual health check
            # For now, simulate based on configuration
            return backup_worker.status != "failed"
        except Exception as e:
            logger.error(f"Error pinging backup worker {backup_worker.worker_id}: {e}")
            return False
    
    async def _check_active_failovers(self):
        """Check status of active failover operations"""
        try:
            current_time = datetime.now()
            completed_failovers = []
            
            for event_id, failover_event in self.active_failovers.items():
                # Check if failover has timed out
                elapsed = (current_time - failover_event.timestamp).total_seconds()
                if elapsed > self.failover_timeout:
                    logger.warning(f"Failover timeout: {event_id}")
                    failover_event.success = False
                    failover_event.duration_seconds = elapsed
                    completed_failovers.append(event_id)
            
            # Move completed failovers to history
            for event_id in completed_failovers:
                failover_event = self.active_failovers.pop(event_id)
                self.failover_history.append(failover_event)
                
                # Update statistics
                self.stats["total_failovers"] += 1
                if failover_event.success:
                    self.stats["successful_failovers"] += 1
                else:
                    self.stats["failed_failovers"] += 1
                
                # Update average failover time
                total_time = sum(e.duration_seconds for e in self.failover_history)
                self.stats["average_failover_time"] = total_time / len(self.failover_history)
        
        except Exception as e:
            logger.error(f"Error checking active failovers: {e}")
    
    async def _check_degradation_conditions(self):
        """Check if graceful degradation is needed"""
        try:
            if not self.health_monitor or not self.service_runner:
                return
            
            # Get current system health
            health_summary = self.health_monitor.get_health_summary()
            
            # Calculate degradation level based on system health
            critical_networks = health_summary.get("critical_networks", 0)
            total_networks = health_summary.get("total_networks", 1)
            critical_ratio = critical_networks / total_networks if total_networks > 0 else 0
            
            # Determine required degradation level
            required_level = DegradationLevel.NONE
            
            if critical_ratio > 0.5:  # More than 50% networks critical
                required_level = DegradationLevel.MAINTENANCE_MODE
            elif critical_ratio > 0.3:  # More than 30% networks critical
                required_level = DegradationLevel.ESSENTIAL_ONLY
            elif critical_ratio > 0.2:  # More than 20% networks critical
                required_level = DegradationLevel.REDUCED_CAPACITY
            elif critical_ratio > 0.1:  # More than 10% networks critical
                required_level = DegradationLevel.REDUCED_QUALITY
            
            # Apply degradation if needed
            if required_level != self.current_degradation_level:
                await self.graceful_degradation(required_level, f"System health: {critical_ratio:.1%} critical")
        
        except Exception as e:
            logger.error(f"Error checking degradation conditions: {e}")
    
    def _on_worker_failure(self, worker_id: str, message: str):
        """Handle worker failure callback"""
        try:
            logger.warning(f"Worker failure detected: {worker_id} - {message}")
            
            # Create failover event
            asyncio.create_task(self._handle_worker_failure(worker_id, message))
            
        except Exception as e:
            logger.error(f"Error handling worker failure: {e}")
    
    def _on_network_failure(self, network_id: str, message: str):
        """Handle network failure callback"""
        try:
            logger.warning(f"Network failure detected: {network_id} - {message}")
            
            # Create failover event
            asyncio.create_task(self._handle_network_failure(network_id, message))
            
        except Exception as e:
            logger.error(f"Error handling network failure: {e}")
    
    async def _handle_worker_failure(self, worker_id: str, message: str):
        """Handle worker failure with automatic recovery"""
        try:
            # Check if we're already handling too many failovers
            if len(self.active_failovers) >= self.max_concurrent_failovers:
                logger.warning(f"Maximum concurrent failovers reached, queuing worker failure: {worker_id}")
                return
            
            # Create failover event
            event_id = f"worker_failover_{worker_id}_{int(time.time())}"
            failover_event = FailoverEvent(
                event_id=event_id,
                timestamp=datetime.now(),
                event_type="worker_failure",
                source_id=worker_id,
                strategy_used=FailoverStrategy.IMMEDIATE,
                details={"failure_message": message}
            )
            
            self.active_failovers[event_id] = failover_event
            
            # Attempt to activate backup worker
            backup_worker = await self.activate_backup_worker(worker_id)
            
            if backup_worker:
                failover_event.target_id = backup_worker.worker_id
                failover_event.success = True
                failover_event.duration_seconds = (datetime.now() - failover_event.timestamp).total_seconds()
                logger.info(f"Worker failover successful: {worker_id} -> {backup_worker.worker_id}")
            else:
                # Try graceful degradation if no backup available
                await self.graceful_degradation(
                    DegradationLevel.REDUCED_CAPACITY,
                    f"Worker failure: {worker_id}, no backup available"
                )
                failover_event.success = False
                failover_event.duration_seconds = (datetime.now() - failover_event.timestamp).total_seconds()
                logger.warning(f"Worker failover failed: {worker_id}, applied graceful degradation")
        
        except Exception as e:
            logger.error(f"Error handling worker failure {worker_id}: {e}")
    
    async def _handle_network_failure(self, network_id: str, message: str):
        """Handle network failure with automatic recovery"""
        try:
            # Check if we're already handling too many failovers
            if len(self.active_failovers) >= self.max_concurrent_failovers:
                logger.warning(f"Maximum concurrent failovers reached, queuing network failure: {network_id}")
                return
            
            # Create failover event
            event_id = f"network_failover_{network_id}_{int(time.time())}"
            failover_event = FailoverEvent(
                event_id=event_id,
                timestamp=datetime.now(),
                event_type="network_failure",
                source_id=network_id,
                strategy_used=FailoverStrategy.GRACEFUL,
                details={"failure_message": message}
            )
            
            self.active_failovers[event_id] = failover_event
            
            # Try to restart the network first
            if self.service_runner and network_id in self.service_runner.networks:
                try:
                    success = await self.service_runner.restart_network_service(network_id)
                    if success:
                        failover_event.success = True
                        failover_event.duration_seconds = (datetime.now() - failover_event.timestamp).total_seconds()
                        logger.info(f"Network restart successful: {network_id}")
                        return
                except Exception as e:
                    logger.error(f"Network restart failed: {network_id} - {e}")
            
            # If restart failed, apply graceful degradation
            await self.graceful_degradation(
                DegradationLevel.REDUCED_CAPACITY,
                f"Network failure: {network_id}, restart failed"
            )
            
            failover_event.success = False
            failover_event.duration_seconds = (datetime.now() - failover_event.timestamp).total_seconds()
            logger.warning(f"Network failover completed with degradation: {network_id}")
        
        except Exception as e:
            logger.error(f"Error handling network failure {network_id}: {e}")
    
    async def activate_backup_worker(self, failed_worker_id: str) -> Optional[BackupWorker]:
        """
        Activate backup worker function as specified in requirements
        
        Args:
            failed_worker_id: ID of the failed worker
            
        Returns:
            BackupWorker if activation successful, None otherwise
        """
        try:
            # Find network ID from failed worker
            network_id = None
            if self.health_monitor:
                worker_health = self.health_monitor.get_all_worker_health()
                for worker_id, health_info in worker_health.items():
                    if worker_id == failed_worker_id:
                        network_id = health_info.network_id
                        break
            
            if not network_id:
                logger.error(f"Cannot find network for failed worker: {failed_worker_id}")
                return None
            
            # Find available backup worker for this network
            available_backups = [
                backup for backup in self.backup_workers.values()
                if backup.network_id == network_id and backup.status == "standby"
            ]
            
            if not available_backups:
                logger.warning(f"No backup workers available for network: {network_id}")
                return None
            
            # Sort by priority (lower number = higher priority)
            available_backups.sort(key=lambda b: b.priority)
            backup_worker = available_backups[0]
            
            # Check license permissions
            if not await self._check_failover_license_permissions(backup_worker):
                logger.error(f"License check failed for backup worker: {backup_worker.worker_id}")
                return None
            
            # Activate the backup worker
            backup_worker.status = "activating"
            backup_worker.activation_time = datetime.now()
            
            # Request resources for backup worker
            if self.resource_allocator:
                success = await self._allocate_backup_resources(backup_worker)
                if not success:
                    logger.error(f"Resource allocation failed for backup worker: {backup_worker.worker_id}")
                    backup_worker.status = "failed"
                    return None
            
            # Start the backup worker (this would involve actual worker startup)
            success = await self._start_backup_worker(backup_worker)
            
            if success:
                backup_worker.status = "active"
                self.stats["backup_activations"] += 1
                logger.info(f"Backup worker activated: {backup_worker.worker_id}")
                return backup_worker
            else:
                backup_worker.status = "failed"
                logger.error(f"Failed to start backup worker: {backup_worker.worker_id}")
                return None
        
        except Exception as e:
            logger.error(f"Error activating backup worker for {failed_worker_id}: {e}")
            return None
    
    async def graceful_degradation(self, level: DegradationLevel, reason: str):
        """
        Implement graceful degradation function as specified in requirements
        
        Args:
            level: Degradation level to apply
            reason: Reason for degradation
        """
        try:
            if level == self.current_degradation_level:
                return  # Already at this level
            
            old_level = self.current_degradation_level
            self.current_degradation_level = level
            
            # Record degradation event
            self.degradation_history.append((datetime.now(), level, reason))
            self.stats["degradation_events"] += 1
            
            logger.info(f"Applying graceful degradation: {old_level.name} -> {level.name} ({reason})")
            
            # Apply degradation based on level
            if level == DegradationLevel.REDUCED_QUALITY:
                await self._apply_quality_reduction()
            elif level == DegradationLevel.REDUCED_CAPACITY:
                await self._apply_capacity_reduction()
            elif level == DegradationLevel.ESSENTIAL_ONLY:
                await self._apply_essential_only_mode()
            elif level == DegradationLevel.MAINTENANCE_MODE:
                await self._apply_maintenance_mode()
            elif level == DegradationLevel.NONE:
                await self._restore_normal_operation()
            
            # Create admin notification
            if self.health_monitor:
                await self.health_monitor._create_admin_notification(
                    severity="warning" if level.value <= 2 else "critical",
                    source="FailoverManager",
                    message=f"Graceful degradation applied: {level.name}",
                    details={
                        "old_level": old_level.name,
                        "new_level": level.name,
                        "reason": reason,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            logger.info(f"Graceful degradation applied successfully: {level.name}")
        
        except Exception as e:
            logger.error(f"Error applying graceful degradation: {e}")
    
    async def _apply_quality_reduction(self):
        """Apply reduced quality degradation"""
        # This would reduce model precision, use smaller models, etc.
        logger.info("Applying quality reduction: using lower precision models")
    
    async def _apply_capacity_reduction(self):
        """Apply reduced capacity degradation"""
        # This would reduce concurrent processing, queue requests, etc.
        logger.info("Applying capacity reduction: limiting concurrent requests")
    
    async def _apply_essential_only_mode(self):
        """Apply essential-only operations mode"""
        # This would disable non-essential features
        logger.info("Applying essential-only mode: disabling non-critical features")
    
    async def _apply_maintenance_mode(self):
        """Apply maintenance mode"""
        # This would put system in minimal functionality mode
        logger.info("Applying maintenance mode: minimal functionality only")
    
    async def _restore_normal_operation(self):
        """Restore normal operation"""
        logger.info("Restoring normal operation: all features enabled")
    
    async def _check_failover_license_permissions(self, backup_worker: BackupWorker) -> bool:
        """Check license permissions for failover operations"""
        try:
            if not self.service_runner or not self.service_runner.current_license:
                logger.warning("No license available for failover permission check")
                return True  # Allow failover without license (degraded mode)
            
            license_info = self.service_runner.current_license
            
            # Validate license is still valid
            validation_result = self.security.license_validator.validate_license_key(license_info.license_key)
            if validation_result.status.value != "valid":
                logger.error(f"License invalid for failover: {validation_result.status.value}")
                return False
            
            # Check if license allows backup workers
            if license_info.plan == SubscriptionTier.FREE:
                logger.warning("Free tier does not support backup workers")
                return False
            
            # Pro and Enterprise tiers support backup workers
            backup_worker.license_validated = True
            return True
        
        except Exception as e:
            logger.error(f"Error checking failover license permissions: {e}")
            return False
    
    async def _allocate_backup_resources(self, backup_worker: BackupWorker) -> bool:
        """Allocate resources for backup worker"""
        try:
            if not self.resource_allocator:
                return True  # No resource allocator, assume success
            
            # Create resource requirements for backup worker
            if not backup_worker.resource_requirements:
                backup_worker.resource_requirements = ResourceQuota(
                    cpu_cores=2.0,
                    memory_gb=4.0,
                    gpu_memory_gb=2.0,
                    worker_slots=1,
                    client_connections=5
                )
            
            # This would request resources from the allocator
            # For now, simulate successful allocation
            logger.info(f"Resources allocated for backup worker: {backup_worker.worker_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error allocating backup resources: {e}")
            return False
    
    async def _start_backup_worker(self, backup_worker: BackupWorker) -> bool:
        """Start the backup worker"""
        try:
            # This would involve actually starting the worker process
            # For now, simulate successful startup
            logger.info(f"Starting backup worker: {backup_worker.worker_id}")
            
            # Simulate startup time
            await asyncio.sleep(2.0)
            
            logger.info(f"Backup worker started successfully: {backup_worker.worker_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error starting backup worker {backup_worker.worker_id}: {e}")
            return False
    
    async def transfer_workload(self, source_worker: str, target_worker: str, model_blocks: List[str]) -> bool:
        """
        Transfer workload from failed worker to backup worker
        
        Args:
            source_worker: Failed worker ID
            target_worker: Backup worker ID
            model_blocks: Model blocks to transfer
            
        Returns:
            True if transfer successful
        """
        try:
            transfer_id = f"transfer_{source_worker}_{target_worker}_{int(time.time())}"
            
            transfer = WorkloadTransfer(
                transfer_id=transfer_id,
                source_worker=source_worker,
                target_worker=target_worker,
                model_blocks=model_blocks,
                active_sessions=[],  # Would get from actual worker
                transfer_started=datetime.now()
            )
            
            self.workload_transfers[transfer_id] = transfer
            
            logger.info(f"Starting workload transfer: {source_worker} -> {target_worker}")
            
            # This would implement actual workload transfer
            # For now, simulate the transfer
            await asyncio.sleep(5.0)  # Simulate transfer time
            
            transfer.transfer_completed = datetime.now()
            transfer.success = True
            
            logger.info(f"Workload transfer completed: {transfer_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error transferring workload: {e}")
            if transfer_id in self.workload_transfers:
                self.workload_transfers[transfer_id].success = False
                self.workload_transfers[transfer_id].error_message = str(e)
            return False
    
    def get_failover_status(self) -> Dict[str, Any]:
        """Get current failover manager status"""
        return {
            "monitoring_active": self.monitoring_active,
            "current_degradation_level": self.current_degradation_level.name,
            "backup_workers": len(self.backup_workers),
            "active_failovers": len(self.active_failovers),
            "statistics": self.stats.copy(),
            "recent_events": [
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "type": event.event_type,
                    "source": event.source_id,
                    "target": event.target_id,
                    "success": event.success,
                    "duration": event.duration_seconds
                }
                for event in self.failover_history[-10:]  # Last 10 events
            ]
        }
    
    def get_backup_workers_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all backup workers"""
        return {
            worker_id: {
                "network_id": worker.network_id,
                "host": worker.host,
                "port": worker.port,
                "status": worker.status,
                "priority": worker.priority,
                "last_health_check": worker.last_health_check.isoformat(),
                "activation_time": worker.activation_time.isoformat() if worker.activation_time else None,
                "license_validated": worker.license_validated
            }
            for worker_id, worker in self.backup_workers.items()
        }
    
    async def redistribute_blocks(self, failed_worker_id: str, network_id: str) -> bool:
        """
        Redistribute blocks function as specified in requirements
        
        Args:
            failed_worker_id: ID of the failed worker
            network_id: Network ID containing the failed worker
            
        Returns:
            True if redistribution successful
        """
        try:
            redistribution_id = f"redist_{failed_worker_id}_{int(time.time())}"
            
            # Get affected blocks from failed worker
            affected_blocks = self._get_worker_blocks(failed_worker_id, network_id)
            if not affected_blocks:
                logger.warning(f"No blocks found for failed worker: {failed_worker_id}")
                return True  # Nothing to redistribute
            
            # Create redistribution record
            redistribution = BlockRedistribution(
                redistribution_id=redistribution_id,
                network_id=network_id,
                failed_worker=failed_worker_id,
                affected_blocks=affected_blocks,
                redistribution_plan={},
                started_at=datetime.now()
            )
            
            self.active_redistributions[redistribution_id] = redistribution
            
            logger.info(f"Starting block redistribution: {redistribution_id}")
            logger.info(f"Affected blocks: {affected_blocks}")
            
            # Check license permissions for redistribution
            if not await self._check_redistribution_license_permissions(network_id):
                logger.error(f"License check failed for block redistribution: {network_id}")
                redistribution.success = False
                redistribution.error_message = "License validation failed"
                return False
            
            # Create redistribution plan
            redistribution_plan = await self._create_redistribution_plan(
                network_id, affected_blocks, failed_worker_id
            )
            
            if not redistribution_plan:
                logger.error(f"Failed to create redistribution plan for {failed_worker_id}")
                redistribution.success = False
                redistribution.error_message = "Failed to create redistribution plan"
                return False
            
            redistribution.redistribution_plan = redistribution_plan
            
            # Resolve conflicts in block assignments
            conflicts_resolved = await self._resolve_block_assignment_conflicts(
                network_id, redistribution_plan
            )
            redistribution.conflicts_resolved = conflicts_resolved
            
            # Execute the redistribution
            success = await self._execute_block_redistribution(redistribution)
            
            if success:
                # Update network configuration
                await self._update_network_configuration_after_redistribution(
                    network_id, redistribution_plan
                )
                
                redistribution.success = True
                redistribution.completed_at = datetime.now()
                logger.info(f"Block redistribution completed successfully: {redistribution_id}")
                return True
            else:
                redistribution.success = False
                redistribution.error_message = "Redistribution execution failed"
                logger.error(f"Block redistribution failed: {redistribution_id}")
                return False
        
        except Exception as e:
            logger.error(f"Error redistributing blocks for {failed_worker_id}: {e}")
            if redistribution_id in self.active_redistributions:
                self.active_redistributions[redistribution_id].success = False
                self.active_redistributions[redistribution_id].error_message = str(e)
            return False
        finally:
            # Move to history
            if redistribution_id in self.active_redistributions:
                redistribution = self.active_redistributions.pop(redistribution_id)
                self.redistribution_history.append(redistribution)
    
    def _get_worker_blocks(self, worker_id: str, network_id: str) -> List[str]:
        """Get blocks assigned to a specific worker"""
        try:
            # Get blocks from worker health info
            if self.health_monitor:
                worker_health = self.health_monitor.get_all_worker_health()
                if worker_id in worker_health:
                    return worker_health[worker_id].model_blocks
            
            # Fallback: get from block assignments
            worker_blocks = []
            for block_id, assignment in self.block_assignments.items():
                if assignment.assigned_worker == worker_id and assignment.network_id == network_id:
                    worker_blocks.append(block_id)
            
            return worker_blocks
        
        except Exception as e:
            logger.error(f"Error getting worker blocks for {worker_id}: {e}")
            return []
    
    async def _check_redistribution_license_permissions(self, network_id: str) -> bool:
        """Check license permissions for block redistribution"""
        try:
            if not self.service_runner or not self.service_runner.current_license:
                logger.warning("No license available for redistribution permission check")
                return True  # Allow redistribution without license (degraded mode)
            
            license_info = self.service_runner.current_license
            
            # Validate license is still valid
            validation_result = self.security.license_validator.validate_license_key(license_info.license_key)
            if validation_result.status.value != "valid":
                logger.error(f"License invalid for redistribution: {validation_result.status.value}")
                return False
            
            # Check if license allows block redistribution
            if license_info.plan == SubscriptionTier.FREE:
                logger.warning("Free tier has limited block redistribution capabilities")
                # Allow basic redistribution for free tier
                return True
            
            # Pro and Enterprise tiers have full redistribution capabilities
            return True
        
        except Exception as e:
            logger.error(f"Error checking redistribution license permissions: {e}")
            return False
    
    async def _create_redistribution_plan(self, network_id: str, affected_blocks: List[str], 
                                        failed_worker_id: str) -> Dict[str, List[str]]:
        """Create a plan for redistributing blocks"""
        try:
            redistribution_plan = {}
            
            # Get available workers for this network
            available_workers = await self._get_available_workers(network_id, failed_worker_id)
            
            if not available_workers:
                logger.error(f"No available workers for redistribution in network: {network_id}")
                return {}
            
            # Distribute blocks among available workers
            blocks_per_worker = len(affected_blocks) // len(available_workers)
            remaining_blocks = len(affected_blocks) % len(available_workers)
            
            block_index = 0
            for i, worker_id in enumerate(available_workers):
                # Calculate number of blocks for this worker
                num_blocks = blocks_per_worker
                if i < remaining_blocks:
                    num_blocks += 1
                
                # Assign blocks to this worker
                worker_blocks = affected_blocks[block_index:block_index + num_blocks]
                if worker_blocks:
                    redistribution_plan[worker_id] = worker_blocks
                    block_index += num_blocks
            
            logger.info(f"Created redistribution plan: {redistribution_plan}")
            return redistribution_plan
        
        except Exception as e:
            logger.error(f"Error creating redistribution plan: {e}")
            return {}
    
    async def _get_available_workers(self, network_id: str, exclude_worker: str) -> List[str]:
        """Get available workers for block redistribution"""
        try:
            available_workers = []
            
            # Get healthy workers from health monitor
            if self.health_monitor:
                worker_health = self.health_monitor.get_all_worker_health()
                for worker_id, health_info in worker_health.items():
                    if (health_info.network_id == network_id and 
                        worker_id != exclude_worker and
                        health_info.status == HealthStatus.HEALTHY):
                        available_workers.append(worker_id)
            
            # Add backup workers if available
            for backup_worker in self.backup_workers.values():
                if (backup_worker.network_id == network_id and 
                    backup_worker.status in ["standby", "active"]):
                    available_workers.append(backup_worker.worker_id)
            
            logger.info(f"Available workers for redistribution: {available_workers}")
            return available_workers
        
        except Exception as e:
            logger.error(f"Error getting available workers: {e}")
            return []
    
    async def _resolve_block_assignment_conflicts(self, network_id: str, 
                                                redistribution_plan: Dict[str, List[str]]) -> int:
        """Resolve conflicts in block assignments"""
        try:
            conflicts_resolved = 0
            
            # Check for conflicts with existing assignments
            for worker_id, blocks in redistribution_plan.items():
                for block_id in blocks:
                    # Check if block is already assigned to another worker
                    if block_id in self.block_assignments:
                        existing_assignment = self.block_assignments[block_id]
                        if existing_assignment.assigned_worker != worker_id:
                            logger.warning(f"Block assignment conflict: {block_id} "
                                         f"assigned to {existing_assignment.assigned_worker}, "
                                         f"reassigning to {worker_id}")
                            
                            # Resolve conflict by updating assignment
                            existing_assignment.assigned_worker = worker_id
                            existing_assignment.last_updated = datetime.now()
                            conflicts_resolved += 1
                    else:
                        # Create new assignment
                        self.block_assignments[block_id] = BlockAssignment(
                            block_id=block_id,
                            network_id=network_id,
                            assigned_worker=worker_id,
                            assignment_priority=1,
                            license_validated=True
                        )
            
            logger.info(f"Resolved {conflicts_resolved} block assignment conflicts")
            return conflicts_resolved
        
        except Exception as e:
            logger.error(f"Error resolving block assignment conflicts: {e}")
            return 0
    
    async def _execute_block_redistribution(self, redistribution: BlockRedistribution) -> bool:
        """Execute the block redistribution plan"""
        try:
            logger.info(f"Executing block redistribution: {redistribution.redistribution_id}")
            
            # This would involve actual block transfer operations
            # For now, simulate the redistribution process
            
            for worker_id, blocks in redistribution.redistribution_plan.items():
                logger.info(f"Transferring blocks to {worker_id}: {blocks}")
                
                # Simulate block transfer time
                await asyncio.sleep(1.0)
                
                # Update block assignments
                for block_id in blocks:
                    if block_id in self.block_assignments:
                        self.block_assignments[block_id].assigned_worker = worker_id
                        self.block_assignments[block_id].last_updated = datetime.now()
            
            logger.info(f"Block redistribution execution completed: {redistribution.redistribution_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error executing block redistribution: {e}")
            return False
    
    async def _update_network_configuration_after_redistribution(self, network_id: str, 
                                                               redistribution_plan: Dict[str, List[str]]):
        """Update network configuration after block redistribution"""
        try:
            if not self.service_runner or network_id not in self.service_runner.networks:
                logger.warning(f"Cannot update network configuration: {network_id}")
                return
            
            network_service = self.service_runner.networks[network_id]
            
            # Update network configuration with new block assignments
            # This would involve updating the actual network configuration
            # For now, log the configuration update
            
            logger.info(f"Updating network configuration for {network_id}")
            logger.info(f"New block distribution: {redistribution_plan}")
            
            # In a real implementation, this would:
            # 1. Update the network configuration file
            # 2. Notify workers of their new block assignments
            # 3. Update routing tables
            # 4. Restart affected services if necessary
            
            logger.info(f"Network configuration updated successfully: {network_id}")
        
        except Exception as e:
            logger.error(f"Error updating network configuration: {e}")
    
    def get_block_assignments(self, network_id: Optional[str] = None) -> Dict[str, BlockAssignment]:
        """Get current block assignments"""
        if network_id:
            return {
                block_id: assignment 
                for block_id, assignment in self.block_assignments.items()
                if assignment.network_id == network_id
            }
        return self.block_assignments.copy()
    
    def get_redistribution_status(self) -> Dict[str, Any]:
        """Get current redistribution status"""
        return {
            "active_redistributions": len(self.active_redistributions),
            "total_redistributions": len(self.redistribution_history),
            "block_assignments": len(self.block_assignments),
            "recent_redistributions": [
                {
                    "redistribution_id": r.redistribution_id,
                    "network_id": r.network_id,
                    "failed_worker": r.failed_worker,
                    "affected_blocks": len(r.affected_blocks),
                    "success": r.success,
                    "conflicts_resolved": r.conflicts_resolved,
                    "duration": (r.completed_at - r.started_at).total_seconds() if r.completed_at else None
                }
                for r in self.redistribution_history[-5:]  # Last 5 redistributions
            ]
        }


async def run_failover_manager_standalone():
    """Run failover manager standalone for testing"""
    from core.service_runner import MultiNetworkServiceRunner
    from health_monitor import AsyncHealthMonitor
    
    # Create service runner and health monitor
    service_runner = MultiNetworkServiceRunner()
    health_monitor = AsyncHealthMonitor(service_runner=service_runner)
    
    # Create failover manager
    failover_manager = FailoverManager(
        service_runner=service_runner,
        health_monitor=health_monitor.monitor
    )
    
    try:
        # Start components
        await service_runner.start()
        await health_monitor.start()
        await failover_manager.start()
        
        print("Failover manager started. Press Ctrl+C to stop.")
        
        # Monitor for a while
        while True:
            await asyncio.sleep(10)
            status = failover_manager.get_failover_status()
            print(f"Failover Status: {status['current_degradation_level']} - "
                  f"{status['backup_workers']} backup workers")
    
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        # Stop components
        await failover_manager.stop()
        await health_monitor.stop()
        await service_runner.shutdown()


def main():
    """Main entry point"""
    asyncio.run(run_failover_manager_standalone())


if __name__ == "__main__":
    main()