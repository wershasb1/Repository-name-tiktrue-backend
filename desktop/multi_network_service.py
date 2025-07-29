"""
Multi-Network Service Management for TikTrue Distributed LLM Platform

This module implements comprehensive multi-network management capabilities,
allowing admin nodes to create, manage, and monitor multiple distinct LLM networks
with different models, configurations, and client assignments.

Features:
- Multiple network creation and lifecycle management
- Resource allocation and monitoring across networks
- Client assignment and load balancing
- Network dashboard with real-time status monitoring
- Performance metrics and analytics
- Network isolation and security boundaries

Classes:
    NetworkResourceManager: Manages resource allocation across networks
    MultiNetworkService: Main service for multi-network management
    NetworkDashboard: Monitoring and analytics dashboard
    ClientAssignmentManager: Handles client-to-network assignments
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Callable
import psutil

from core.network_manager import NetworkManager, NetworkInfo, NetworkType, NetworkStatus
from license_enforcer import get_license_enforcer
from license_models import SubscriptionTier

logger = logging.getLogger("MultiNetworkService")


class ResourceType(Enum):
    """Resource type definitions"""
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    NETWORK_BANDWIDTH = "network_bandwidth"
    STORAGE = "storage"


class NetworkPriority(Enum):
    """Network priority levels for resource allocation"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResourceMetrics:
    """Resource usage metrics"""
    cpu_usage_percent: float
    memory_usage_mb: float
    gpu_usage_percent: float
    gpu_memory_mb: float
    network_bandwidth_mbps: float
    storage_usage_mb: float
    timestamp: datetime


@dataclass
class NetworkResourceAllocation:
    """Resource allocation for a specific network"""
    network_id: str
    cpu_limit_percent: float
    memory_limit_mb: float
    gpu_limit_percent: float
    gpu_memory_limit_mb: float
    bandwidth_limit_mbps: float
    priority: NetworkPriority
    current_usage: ResourceMetrics
    allocated_at: datetime


@dataclass
class ClientAssignment:
    """Client assignment to network"""
    client_id: str
    network_id: str
    assigned_at: datetime
    last_activity: datetime
    resource_usage: ResourceMetrics
    status: str  # active, idle, disconnected


@dataclass
class NetworkStatistics:
    """Network performance statistics"""
    network_id: str
    total_clients: int
    active_clients: int
    total_requests: int
    requests_per_second: float
    average_response_time_ms: float
    error_rate_percent: float
    uptime_seconds: float
    resource_utilization: ResourceMetrics
    last_updated: datetime


class NetworkResourceManager:
    """
    Manages resource allocation and monitoring across multiple networks
    """
    
    def __init__(self, total_cpu_cores: int = None, total_memory_gb: int = None):
        """
        Initialize resource manager
        
        Args:
            total_cpu_cores: Total CPU cores available (auto-detected if None)
            total_memory_gb: Total memory in GB (auto-detected if None)
        """
        self.total_cpu_cores = total_cpu_cores or psutil.cpu_count()
        self.total_memory_gb = total_memory_gb or (psutil.virtual_memory().total / (1024**3))
        
        # Resource allocations by network
        self.network_allocations: Dict[str, NetworkResourceAllocation] = {}
        
        # Resource monitoring
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.resource_history: Dict[str, List[ResourceMetrics]] = {}
        
        # Resource limits and thresholds
        self.cpu_overcommit_ratio = 1.5  # Allow 150% CPU allocation
        self.memory_overcommit_ratio = 1.2  # Allow 120% memory allocation
        self.resource_check_interval = 5.0  # seconds
        
        logger.info(f"ResourceManager initialized: {self.total_cpu_cores} cores, {self.total_memory_gb:.1f}GB RAM")
    
    def allocate_resources(self, network_id: str, model_id: str, 
                          max_clients: int, priority: NetworkPriority = NetworkPriority.NORMAL) -> NetworkResourceAllocation:
        """
        Allocate resources for a network based on model requirements and client capacity
        
        Args:
            network_id: Network identifier
            model_id: Model being served
            max_clients: Maximum expected clients
            priority: Network priority level
            
        Returns:
            NetworkResourceAllocation object
        """
        try:
            # Calculate base resource requirements
            base_cpu_percent = self._calculate_base_cpu_requirement(model_id, max_clients)
            base_memory_mb = self._calculate_base_memory_requirement(model_id, max_clients)
            base_gpu_percent = self._calculate_base_gpu_requirement(model_id)
            base_gpu_memory_mb = self._calculate_base_gpu_memory_requirement(model_id)
            
            # Apply priority multipliers
            priority_multipliers = {
                NetworkPriority.LOW: 0.7,
                NetworkPriority.NORMAL: 1.0,
                NetworkPriority.HIGH: 1.3,
                NetworkPriority.CRITICAL: 1.5
            }
            
            multiplier = priority_multipliers[priority]
            
            # Calculate final allocations
            cpu_limit = min(base_cpu_percent * multiplier, 100.0)
            memory_limit = base_memory_mb * multiplier
            gpu_limit = min(base_gpu_percent * multiplier, 100.0)
            gpu_memory_limit = base_gpu_memory_mb * multiplier
            bandwidth_limit = self._calculate_bandwidth_requirement(max_clients)
            
            # Validate resource availability
            if not self._validate_resource_availability(cpu_limit, memory_limit, gpu_limit, gpu_memory_limit):
                raise ResourceError(f"Insufficient resources for network {network_id}")
            
            # Create allocation
            allocation = NetworkResourceAllocation(
                network_id=network_id,
                cpu_limit_percent=cpu_limit,
                memory_limit_mb=memory_limit,
                gpu_limit_percent=gpu_limit,
                gpu_memory_limit_mb=gpu_memory_limit,
                bandwidth_limit_mbps=bandwidth_limit,
                priority=priority,
                current_usage=ResourceMetrics(0, 0, 0, 0, 0, 0, datetime.now()),
                allocated_at=datetime.now()
            )
            
            # Store allocation
            self.network_allocations[network_id] = allocation
            
            logger.info(f"Resources allocated for network {network_id}: "
                       f"CPU={cpu_limit:.1f}%, Memory={memory_limit:.0f}MB, "
                       f"GPU={gpu_limit:.1f}%, Priority={priority.value}")
            
            return allocation
            
        except Exception as e:
            logger.error(f"Failed to allocate resources for network {network_id}: {e}")
            raise
    
    def deallocate_resources(self, network_id: str) -> bool:
        """
        Deallocate resources for a network
        
        Args:
            network_id: Network identifier
            
        Returns:
            True if successful
        """
        try:
            if network_id in self.network_allocations:
                del self.network_allocations[network_id]
                
                # Clean up resource history
                if network_id in self.resource_history:
                    del self.resource_history[network_id]
                
                logger.info(f"Resources deallocated for network {network_id}")
                return True
            else:
                logger.warning(f"No resource allocation found for network {network_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to deallocate resources for network {network_id}: {e}")
            return False
    
    def get_resource_usage(self, network_id: str) -> Optional[ResourceMetrics]:
        """
        Get current resource usage for a network
        
        Args:
            network_id: Network identifier
            
        Returns:
            ResourceMetrics if available
        """
        try:
            if network_id not in self.network_allocations:
                return None
            
            # Get system-wide metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # Get GPU metrics if available
            gpu_percent = 0
            gpu_memory_mb = 0
            try:
                # Try to import GPUtil for GPU monitoring
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]  # Use first GPU
                    gpu_percent = gpu.load * 100
                    gpu_memory_mb = gpu.memoryUsed
            except ImportError:
                pass  # GPU monitoring not available
            except Exception:
                pass  # GPU monitoring failed
            
            # Calculate network-specific usage (simplified)
            allocation = self.network_allocations[network_id]
            network_cpu = cpu_percent * (allocation.cpu_limit_percent / 100)
            network_memory = memory.used / (1024**2) * (allocation.memory_limit_mb / (self.total_memory_gb * 1024))
            
            metrics = ResourceMetrics(
                cpu_usage_percent=network_cpu,
                memory_usage_mb=network_memory,
                gpu_usage_percent=gpu_percent * (allocation.gpu_limit_percent / 100),
                gpu_memory_mb=gpu_memory_mb * (allocation.gpu_memory_limit_mb / 8192),  # Assume 8GB GPU
                network_bandwidth_mbps=0,  # Would need network monitoring
                storage_usage_mb=0,  # Would need storage monitoring
                timestamp=datetime.now()
            )
            
            # Update allocation
            allocation.current_usage = metrics
            
            # Store in history
            if network_id not in self.resource_history:
                self.resource_history[network_id] = []
            
            self.resource_history[network_id].append(metrics)
            
            # Keep only last 1000 entries
            if len(self.resource_history[network_id]) > 1000:
                self.resource_history[network_id] = self.resource_history[network_id][-1000:]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get resource usage for network {network_id}: {e}")
            return None
    
    def get_system_resource_summary(self) -> Dict[str, Any]:
        """
        Get system-wide resource summary
        
        Returns:
            Dictionary with resource information
        """
        try:
            # CPU information
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # Memory information
            memory = psutil.virtual_memory()
            
            # GPU information
            gpu_info = []
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                for gpu in gpus:
                    gpu_info.append({
                        'id': gpu.id,
                        'name': gpu.name,
                        'load': gpu.load * 100,
                        'memory_used': gpu.memoryUsed,
                        'memory_total': gpu.memoryTotal,
                        'temperature': gpu.temperature
                    })
            except ImportError:
                pass
            except Exception:
                pass
            
            # Calculate allocated resources
            total_allocated_cpu = sum(alloc.cpu_limit_percent for alloc in self.network_allocations.values())
            total_allocated_memory = sum(alloc.memory_limit_mb for alloc in self.network_allocations.values())
            
            return {
                'system': {
                    'cpu_cores': cpu_count,
                    'cpu_usage_percent': cpu_percent,
                    'memory_total_gb': memory.total / (1024**3),
                    'memory_used_gb': memory.used / (1024**3),
                    'memory_available_gb': memory.available / (1024**3),
                    'gpu_count': len(gpu_info),
                    'gpu_info': gpu_info
                },
                'allocation': {
                    'networks_count': len(self.network_allocations),
                    'total_allocated_cpu_percent': total_allocated_cpu,
                    'total_allocated_memory_mb': total_allocated_memory,
                    'cpu_overcommit_ratio': total_allocated_cpu / 100.0,
                    'memory_overcommit_ratio': total_allocated_memory / (self.total_memory_gb * 1024)
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system resource summary: {e}")
            return {}
    
    def start_monitoring(self) -> bool:
        """
        Start resource monitoring thread
        
        Returns:
            True if started successfully
        """
        try:
            if self.monitoring_active:
                logger.warning("Resource monitoring already active")
                return True
            
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                name="ResourceMonitoring",
                daemon=True
            )
            self.monitoring_thread.start()
            
            logger.info("Resource monitoring started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start resource monitoring: {e}")
            return False
    
    def stop_monitoring(self) -> None:
        """Stop resource monitoring"""
        try:
            self.monitoring_active = False
            
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5.0)
            
            logger.info("Resource monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping resource monitoring: {e}")
    
    # Private methods
    
    def _calculate_base_cpu_requirement(self, model_id: str, max_clients: int) -> float:
        """Calculate base CPU requirement for model and client count"""
        # Model-specific CPU requirements (simplified)
        model_cpu_base = {
            'llama3_1_8b_fp16': 20.0,
            'mistral_7b_int4': 15.0,
            'default': 25.0
        }
        
        base_cpu = model_cpu_base.get(model_id, model_cpu_base['default'])
        
        # Scale with client count (diminishing returns)
        client_scaling = min(max_clients * 5.0, 50.0)
        
        return min(base_cpu + client_scaling, 90.0)
    
    def _calculate_base_memory_requirement(self, model_id: str, max_clients: int) -> float:
        """Calculate base memory requirement in MB"""
        # Model-specific memory requirements
        model_memory_base = {
            'llama3_1_8b_fp16': 8192.0,  # 8GB
            'mistral_7b_int4': 4096.0,   # 4GB
            'default': 6144.0            # 6GB
        }
        
        base_memory = model_memory_base.get(model_id, model_memory_base['default'])
        
        # Add memory for client connections (100MB per client)
        client_memory = max_clients * 100.0
        
        return base_memory + client_memory
    
    def _calculate_base_gpu_requirement(self, model_id: str) -> float:
        """Calculate base GPU requirement percentage"""
        # GPU usage depends on model size and type
        model_gpu_usage = {
            'llama3_1_8b_fp16': 60.0,
            'mistral_7b_int4': 40.0,
            'default': 50.0
        }
        
        return model_gpu_usage.get(model_id, model_gpu_usage['default'])
    
    def _calculate_base_gpu_memory_requirement(self, model_id: str) -> float:
        """Calculate base GPU memory requirement in MB"""
        model_gpu_memory = {
            'llama3_1_8b_fp16': 6144.0,  # 6GB
            'mistral_7b_int4': 3072.0,   # 3GB
            'default': 4096.0            # 4GB
        }
        
        return model_gpu_memory.get(model_id, model_gpu_memory['default'])
    
    def _calculate_bandwidth_requirement(self, max_clients: int) -> float:
        """Calculate network bandwidth requirement in Mbps"""
        # Estimate 10 Mbps per active client
        return max_clients * 10.0
    
    def _validate_resource_availability(self, cpu_percent: float, memory_mb: float, 
                                      gpu_percent: float, gpu_memory_mb: float) -> bool:
        """Validate if requested resources are available"""
        # Check CPU availability
        total_allocated_cpu = sum(alloc.cpu_limit_percent for alloc in self.network_allocations.values())
        if total_allocated_cpu + cpu_percent > 100.0 * self.cpu_overcommit_ratio:
            logger.warning(f"CPU overcommit exceeded: {total_allocated_cpu + cpu_percent:.1f}%")
            return False
        
        # Check memory availability
        total_allocated_memory = sum(alloc.memory_limit_mb for alloc in self.network_allocations.values())
        max_memory_mb = self.total_memory_gb * 1024
        if total_allocated_memory + memory_mb > max_memory_mb * self.memory_overcommit_ratio:
            logger.warning(f"Memory overcommit exceeded: {(total_allocated_memory + memory_mb)/1024:.1f}GB")
            return False
        
        return True
    
    def _monitoring_loop(self) -> None:
        """Resource monitoring loop"""
        logger.info("Resource monitoring loop started")
        
        while self.monitoring_active:
            try:
                # Update resource usage for all networks
                for network_id in list(self.network_allocations.keys()):
                    self.get_resource_usage(network_id)
                
                # Sleep until next check
                time.sleep(self.resource_check_interval)
                
            except Exception as e:
                if self.monitoring_active:
                    logger.error(f"Resource monitoring error: {e}")
                time.sleep(1.0)
        
        logger.info("Resource monitoring loop stopped")


class ClientAssignmentManager:
    """
    Manages client assignments to networks with load balancing
    """
    
    def __init__(self):
        """Initialize client assignment manager"""
        self.client_assignments: Dict[str, ClientAssignment] = {}
        self.network_clients: Dict[str, Set[str]] = {}  # network_id -> set of client_ids
        self.assignment_callbacks: List[Callable[[str, str, str], None]] = []  # client_id, network_id, action
        
        logger.info("ClientAssignmentManager initialized")
    
    def assign_client_to_network(self, client_id: str, network_id: str, 
                                network_info: NetworkInfo) -> bool:
        """
        Assign client to a specific network
        
        Args:
            client_id: Client identifier
            network_id: Target network identifier
            network_info: Network information
            
        Returns:
            True if assignment successful
        """
        try:
            # Check if network has capacity
            current_clients = len(self.network_clients.get(network_id, set()))
            if current_clients >= network_info.max_clients:
                logger.warning(f"Network {network_id} at capacity: {current_clients}/{network_info.max_clients}")
                return False
            
            # Remove client from previous network if assigned
            if client_id in self.client_assignments:
                old_network_id = self.client_assignments[client_id].network_id
                self._remove_client_from_network(client_id, old_network_id)
            
            # Create assignment
            assignment = ClientAssignment(
                client_id=client_id,
                network_id=network_id,
                assigned_at=datetime.now(),
                last_activity=datetime.now(),
                resource_usage=ResourceMetrics(0, 0, 0, 0, 0, 0, datetime.now()),
                status="active"
            )
            
            # Store assignment
            self.client_assignments[client_id] = assignment
            
            # Add to network client set
            if network_id not in self.network_clients:
                self.network_clients[network_id] = set()
            self.network_clients[network_id].add(client_id)
            
            # Notify callbacks
            for callback in self.assignment_callbacks:
                try:
                    callback(client_id, network_id, "assigned")
                except Exception as e:
                    logger.error(f"Assignment callback error: {e}")
            
            logger.info(f"Client {client_id} assigned to network {network_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign client {client_id} to network {network_id}: {e}")
            return False
    
    def remove_client_assignment(self, client_id: str) -> bool:
        """
        Remove client assignment
        
        Args:
            client_id: Client identifier
            
        Returns:
            True if removal successful
        """
        try:
            if client_id not in self.client_assignments:
                logger.warning(f"No assignment found for client {client_id}")
                return False
            
            assignment = self.client_assignments[client_id]
            network_id = assignment.network_id
            
            # Remove from network
            self._remove_client_from_network(client_id, network_id)
            
            # Remove assignment
            del self.client_assignments[client_id]
            
            # Notify callbacks
            for callback in self.assignment_callbacks:
                try:
                    callback(client_id, network_id, "removed")
                except Exception as e:
                    logger.error(f"Assignment callback error: {e}")
            
            logger.info(f"Client {client_id} assignment removed from network {network_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove assignment for client {client_id}: {e}")
            return False
    
    def get_network_clients(self, network_id: str) -> List[ClientAssignment]:
        """
        Get all clients assigned to a network
        
        Args:
            network_id: Network identifier
            
        Returns:
            List of client assignments
        """
        try:
            client_ids = self.network_clients.get(network_id, set())
            assignments = []
            
            for client_id in client_ids:
                if client_id in self.client_assignments:
                    assignments.append(self.client_assignments[client_id])
            
            return assignments
            
        except Exception as e:
            logger.error(f"Failed to get clients for network {network_id}: {e}")
            return []
    
    def get_client_assignment(self, client_id: str) -> Optional[ClientAssignment]:
        """
        Get assignment for a specific client
        
        Args:
            client_id: Client identifier
            
        Returns:
            ClientAssignment if found
        """
        return self.client_assignments.get(client_id)
    
    def update_client_activity(self, client_id: str) -> bool:
        """
        Update client last activity timestamp
        
        Args:
            client_id: Client identifier
            
        Returns:
            True if updated successfully
        """
        try:
            if client_id in self.client_assignments:
                self.client_assignments[client_id].last_activity = datetime.now()
                self.client_assignments[client_id].status = "active"
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to update activity for client {client_id}: {e}")
            return False
    
    def get_assignment_statistics(self) -> Dict[str, Any]:
        """
        Get assignment statistics
        
        Returns:
            Dictionary with statistics
        """
        try:
            total_assignments = len(self.client_assignments)
            active_assignments = sum(1 for a in self.client_assignments.values() if a.status == "active")
            
            network_stats = {}
            for network_id, client_ids in self.network_clients.items():
                network_stats[network_id] = {
                    'total_clients': len(client_ids),
                    'active_clients': sum(1 for cid in client_ids 
                                        if cid in self.client_assignments and 
                                        self.client_assignments[cid].status == "active")
                }
            
            return {
                'total_assignments': total_assignments,
                'active_assignments': active_assignments,
                'networks': network_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get assignment statistics: {e}")
            return {}
    
    def add_assignment_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Add callback for assignment events
        
        Args:
            callback: Function to call on assignment changes
        """
        self.assignment_callbacks.append(callback)
    
    def remove_assignment_callback(self, callback: Callable[[str, str, str], None]) -> None:
        """
        Remove assignment callback
        
        Args:
            callback: Callback function to remove
        """
        if callback in self.assignment_callbacks:
            self.assignment_callbacks.remove(callback)
    
    # Private methods
    
    def _remove_client_from_network(self, client_id: str, network_id: str) -> None:
        """Remove client from network client set"""
        if network_id in self.network_clients:
            self.network_clients[network_id].discard(client_id)
            
            # Clean up empty network sets
            if not self.network_clients[network_id]:
                del self.network_clients[network_id]


class ResourceError(Exception):
    """Resource allocation error"""
    pass


class MultiNetworkService:
    """
    Main service for managing multiple networks with resource allocation and monitoring
    """
    
    def __init__(self, storage_dir: Optional[str] = None, node_id: Optional[str] = None):
        """
        Initialize multi-network service
        
        Args:
            storage_dir: Directory for configuration storage
            node_id: Unique node identifier
        """
        self.storage_dir = Path(storage_dir) if storage_dir else Path.cwd() / "networks"
        self.node_id = node_id or f"multinode_{uuid.uuid4().hex[:8]}"
        
        # Core components
        self.network_manager = NetworkManager(str(self.storage_dir), self.node_id)
        self.resource_manager = NetworkResourceManager()
        self.client_assignment_manager = ClientAssignmentManager()
        
        # License integration
        self.license_enforcer = get_license_enforcer()
        
        # Network tracking
        self.active_networks: Dict[str, NetworkInfo] = {}
        self.network_statistics: Dict[str, NetworkStatistics] = {}
        
        # Service state
        self.service_running = False
        self.monitoring_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.network_callbacks: List[Callable[[str, str], None]] = []  # network_id, action
        
        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"MultiNetworkService initialized for node {self.node_id}")
    
    async def start_service(self) -> bool:
        """
        Start the multi-network service
        
        Returns:
            True if started successfully
        """
        try:
            if self.service_running:
                logger.warning("Multi-network service already running")
                return True
            
            logger.info("Starting multi-network service...")
            
            # Start core components
            if not self.network_manager.start_discovery_service():
                logger.error("Failed to start network discovery service")
                return False
            
            if not self.resource_manager.start_monitoring():
                logger.error("Failed to start resource monitoring")
                return False
            
            # Load existing networks
            await self._load_existing_networks()
            
            # Start service monitoring
            self.service_running = True
            self.monitoring_thread = threading.Thread(
                target=self._service_monitoring_loop,
                name="MultiNetworkMonitoring",
                daemon=True
            )
            self.monitoring_thread.start()
            
            logger.info("Multi-network service started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start multi-network service: {e}")
            await self.stop_service()
            return False
    
    async def stop_service(self) -> None:
        """Stop the multi-network service"""
        try:
            logger.info("Stopping multi-network service...")
            
            self.service_running = False
            
            # Stop monitoring thread
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5.0)
            
            # Stop core components
            self.network_manager.stop_discovery_service()
            self.resource_manager.stop_monitoring()
            
            # Save network states
            await self._save_network_states()
            
            logger.info("Multi-network service stopped")
            
        except Exception as e:
            logger.error(f"Error stopping multi-network service: {e}")
    
    async def create_network(self, network_name: str, model_id: str,
                           network_type: NetworkType = NetworkType.PUBLIC,
                           max_clients: int = None,
                           priority: NetworkPriority = NetworkPriority.NORMAL,
                           description: str = "") -> Optional[NetworkInfo]:
        """
        Create a new network with resource allocation
        
        Args:
            network_name: Name for the network
            model_id: Model to serve
            network_type: Type of network
            max_clients: Maximum clients (auto-calculated if None)
            priority: Network priority for resource allocation
            description: Network description
            
        Returns:
            NetworkInfo if successful
        """
        try:
            logger.info(f"Creating network: {network_name} with model {model_id}")
            
            # Validate license and get limits
            license_status = self.license_enforcer.get_license_status()
            if not license_status.get('valid', False):
                logger.error("Network creation denied: Invalid license")
                return None
            
            current_license = self.license_enforcer.current_license
            if not current_license:
                logger.error("Network creation denied: No license information")
                return None
            
            # Check network creation limits
            network_limits = {
                SubscriptionTier.FREE: 1,
                SubscriptionTier.PRO: 5,
                SubscriptionTier.ENT: -1  # Unlimited
            }
            
            current_managed = len(self.active_networks)
            max_networks = network_limits.get(current_license.plan, 0)
            
            if max_networks != -1 and current_managed >= max_networks:
                logger.error(f"Network creation denied: Network limit reached ({current_managed}/{max_networks})")
                return None
            
            # Determine max clients if not specified
            if max_clients is None:
                max_clients = min(current_license.max_clients, 20) if current_license.max_clients != -1 else 20
            
            # Allocate resources
            try:
                resource_allocation = self.resource_manager.allocate_resources(
                    network_id=f"temp_{uuid.uuid4().hex[:8]}",  # Temporary ID
                    model_id=model_id,
                    max_clients=max_clients,
                    priority=priority
                )
            except ResourceError as e:
                logger.error(f"Resource allocation failed: {e}")
                return None
            
            # Create network using network manager
            network_info = self.network_manager.create_network(
                network_name=network_name,
                model_id=model_id,
                network_type=network_type,
                description=description
            )
            
            if not network_info:
                # Clean up resource allocation
                self.resource_manager.deallocate_resources(resource_allocation.network_id)
                return None
            
            # Update resource allocation with actual network ID
            self.resource_manager.deallocate_resources(resource_allocation.network_id)
            resource_allocation.network_id = network_info.network_id
            self.resource_manager.network_allocations[network_info.network_id] = resource_allocation
            
            # Update network info with actual max clients
            network_info.max_clients = max_clients
            
            # Add to active networks
            self.active_networks[network_info.network_id] = network_info
            
            # Initialize statistics
            self.network_statistics[network_info.network_id] = NetworkStatistics(
                network_id=network_info.network_id,
                total_clients=0,
                active_clients=0,
                total_requests=0,
                requests_per_second=0.0,
                average_response_time_ms=0.0,
                error_rate_percent=0.0,
                uptime_seconds=0.0,
                resource_utilization=ResourceMetrics(0, 0, 0, 0, 0, 0, datetime.now()),
                last_updated=datetime.now()
            )
            
            # Notify callbacks
            for callback in self.network_callbacks:
                try:
                    callback(network_info.network_id, "created")
                except Exception as e:
                    logger.error(f"Network callback error: {e}")
            
            logger.info(f"Network created successfully: {network_name} ({network_info.network_id})")
            return network_info
            
        except Exception as e:
            logger.error(f"Failed to create network: {e}")
            return None
    
    async def delete_network(self, network_id: str) -> bool:
        """
        Delete a network and clean up resources
        
        Args:
            network_id: Network to delete
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Deleting network: {network_id}")
            
            if network_id not in self.active_networks:
                logger.warning(f"Network not found: {network_id}")
                return False
            
            # Remove all client assignments
            clients = self.client_assignment_manager.get_network_clients(network_id)
            for client in clients:
                self.client_assignment_manager.remove_client_assignment(client.client_id)
            
            # Deallocate resources
            self.resource_manager.deallocate_resources(network_id)
            
            # Remove from active networks
            del self.active_networks[network_id]
            
            # Remove statistics
            if network_id in self.network_statistics:
                del self.network_statistics[network_id]
            
            # Clean up configuration files
            config_file = self.storage_dir / f"network_config_{network_id}.json"
            if config_file.exists():
                config_file.unlink()
            
            # Notify callbacks
            for callback in self.network_callbacks:
                try:
                    callback(network_id, "deleted")
                except Exception as e:
                    logger.error(f"Network callback error: {e}")
            
            logger.info(f"Network deleted successfully: {network_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete network {network_id}: {e}")
            return False
    
    def get_network_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all active networks with status
        
        Returns:
            List of network information dictionaries
        """
        try:
            networks = []
            
            for network_id, network_info in self.active_networks.items():
                # Get resource allocation
                resource_allocation = self.resource_manager.network_allocations.get(network_id)
                
                # Get client assignments
                clients = self.client_assignment_manager.get_network_clients(network_id)
                
                # Get statistics
                stats = self.network_statistics.get(network_id)
                
                network_data = {
                    'network_id': network_id,
                    'network_name': network_info.network_name,
                    'model_id': network_info.model_id,
                    'network_type': network_info.network_type.value,
                    'status': network_info.status.value,
                    'max_clients': network_info.max_clients,
                    'current_clients': len(clients),
                    'active_clients': sum(1 for c in clients if c.status == "active"),
                    'created_at': network_info.created_at.isoformat(),
                    'description': network_info.description,
                    'resource_allocation': asdict(resource_allocation) if resource_allocation else None,
                    'statistics': asdict(stats) if stats else None
                }
                
                networks.append(network_data)
            
            return networks
            
        except Exception as e:
            logger.error(f"Failed to get network list: {e}")
            return []
    
    def get_network_details(self, network_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific network
        
        Args:
            network_id: Network identifier
            
        Returns:
            Detailed network information
        """
        try:
            if network_id not in self.active_networks:
                return None
            
            network_info = self.active_networks[network_id]
            resource_allocation = self.resource_manager.network_allocations.get(network_id)
            clients = self.client_assignment_manager.get_network_clients(network_id)
            stats = self.network_statistics.get(network_id)
            
            # Get resource history
            resource_history = self.resource_manager.resource_history.get(network_id, [])
            
            return {
                'network_info': asdict(network_info),
                'resource_allocation': asdict(resource_allocation) if resource_allocation else None,
                'clients': [asdict(client) for client in clients],
                'statistics': asdict(stats) if stats else None,
                'resource_history': [asdict(metric) for metric in resource_history[-100:]],  # Last 100 entries
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get network details for {network_id}: {e}")
            return None
    
    async def assign_client_to_network(self, client_id: str, network_id: str) -> bool:
        """
        Assign a client to a specific network
        
        Args:
            client_id: Client identifier
            network_id: Target network identifier
            
        Returns:
            True if assignment successful
        """
        try:
            if network_id not in self.active_networks:
                logger.error(f"Network not found: {network_id}")
                return False
            
            network_info = self.active_networks[network_id]
            
            success = self.client_assignment_manager.assign_client_to_network(
                client_id=client_id,
                network_id=network_id,
                network_info=network_info
            )
            
            if success:
                # Update network statistics
                self._update_network_statistics(network_id)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to assign client {client_id} to network {network_id}: {e}")
            return False
    
    def get_service_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive service statistics
        
        Returns:
            Dictionary with service statistics
        """
        try:
            # System resources
            system_resources = self.resource_manager.get_system_resource_summary()
            
            # Assignment statistics
            assignment_stats = self.client_assignment_manager.get_assignment_statistics()
            
            # Network statistics
            network_stats = {}
            for network_id, stats in self.network_statistics.items():
                network_stats[network_id] = asdict(stats)
            
            return {
                'service': {
                    'node_id': self.node_id,
                    'service_running': self.service_running,
                    'active_networks': len(self.active_networks),
                    'total_clients': assignment_stats.get('total_assignments', 0),
                    'active_clients': assignment_stats.get('active_assignments', 0)
                },
                'system_resources': system_resources,
                'assignment_statistics': assignment_stats,
                'network_statistics': network_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get service statistics: {e}")
            return {}
    
    def add_network_callback(self, callback: Callable[[str, str], None]) -> None:
        """
        Add callback for network events
        
        Args:
            callback: Function to call on network changes
        """
        self.network_callbacks.append(callback)
    
    def remove_network_callback(self, callback: Callable[[str, str], None]) -> None:
        """
        Remove network callback
        
        Args:
            callback: Callback function to remove
        """
        if callback in self.network_callbacks:
            self.network_callbacks.remove(callback)
    
    # Private methods
    
    async def _load_existing_networks(self) -> None:
        """Load existing network configurations"""
        try:
            config_files = list(self.storage_dir.glob("network_config_*.json"))
            
            for config_file in config_files:
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    network_id = config.get("network_id")
                    if network_id and network_id in self.network_manager.managed_networks:
                        network_info = self.network_manager.managed_networks[network_id]
                        self.active_networks[network_id] = network_info
                        
                        # Initialize statistics
                        self.network_statistics[network_id] = NetworkStatistics(
                            network_id=network_id,
                            total_clients=0,
                            active_clients=0,
                            total_requests=0,
                            requests_per_second=0.0,
                            average_response_time_ms=0.0,
                            error_rate_percent=0.0,
                            uptime_seconds=0.0,
                            resource_utilization=ResourceMetrics(0, 0, 0, 0, 0, 0, datetime.now()),
                            last_updated=datetime.now()
                        )
                        
                        logger.info(f"Loaded existing network: {network_id}")
                
                except Exception as e:
                    logger.warning(f"Failed to load network config {config_file}: {e}")
            
            logger.info(f"Loaded {len(self.active_networks)} existing networks")
            
        except Exception as e:
            logger.error(f"Failed to load existing networks: {e}")
    
    async def _save_network_states(self) -> None:
        """Save current network states"""
        try:
            for network_id, network_info in self.active_networks.items():
                config_file = self.storage_dir / f"network_config_{network_id}.json"
                
                config_data = {
                    'network_id': network_id,
                    'network_name': network_info.network_name,
                    'model_id': network_info.model_id,
                    'network_type': network_info.network_type.value,
                    'status': network_info.status.value,
                    'max_clients': network_info.max_clients,
                    'created_at': network_info.created_at.isoformat(),
                    'description': network_info.description,
                    'saved_at': datetime.now().isoformat()
                }
                
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2)
            
            logger.info(f"Saved {len(self.active_networks)} network states")
            
        except Exception as e:
            logger.error(f"Failed to save network states: {e}")
    
    def _update_network_statistics(self, network_id: str) -> None:
        """Update statistics for a specific network"""
        try:
            if network_id not in self.network_statistics:
                return
            
            stats = self.network_statistics[network_id]
            clients = self.client_assignment_manager.get_network_clients(network_id)
            
            # Update client counts
            stats.total_clients = len(clients)
            stats.active_clients = sum(1 for c in clients if c.status == "active")
            
            # Update resource utilization
            resource_usage = self.resource_manager.get_resource_usage(network_id)
            if resource_usage:
                stats.resource_utilization = resource_usage
            
            # Update timestamp
            stats.last_updated = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to update statistics for network {network_id}: {e}")
    
    def _service_monitoring_loop(self) -> None:
        """Main service monitoring loop"""
        logger.info("Service monitoring loop started")
        
        while self.service_running:
            try:
                # Update statistics for all networks
                for network_id in list(self.active_networks.keys()):
                    self._update_network_statistics(network_id)
                
                # Sleep until next check
                time.sleep(10.0)  # Update every 10 seconds
                
            except Exception as e:
                if self.service_running:
                    logger.error(f"Service monitoring error: {e}")
                time.sleep(1.0)
        
        logger.info("Service monitoring loop stopped")


class NetworkDashboard:
    """
    Network dashboard for monitoring and analytics
    """
    
    def __init__(self, multi_network_service: MultiNetworkService):
        """
        Initialize network dashboard
        
        Args:
            multi_network_service: Multi-network service instance
        """
        self.multi_network_service = multi_network_service
        self.dashboard_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Dashboard state
        self.dashboard_active = False
        self.update_thread: Optional[threading.Thread] = None
        self.update_interval = 5.0  # seconds
        
        logger.info("NetworkDashboard initialized")
    
    def start_dashboard(self) -> bool:
        """
        Start dashboard monitoring
        
        Returns:
            True if started successfully
        """
        try:
            if self.dashboard_active:
                logger.warning("Dashboard already active")
                return True
            
            self.dashboard_active = True
            self.update_thread = threading.Thread(
                target=self._dashboard_update_loop,
                name="DashboardUpdate",
                daemon=True
            )
            self.update_thread.start()
            
            logger.info("Network dashboard started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start dashboard: {e}")
            return False
    
    def stop_dashboard(self) -> None:
        """Stop dashboard monitoring"""
        try:
            self.dashboard_active = False
            
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join(timeout=5.0)
            
            logger.info("Network dashboard stopped")
            
        except Exception as e:
            logger.error(f"Error stopping dashboard: {e}")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data
        
        Returns:
            Dictionary with dashboard information
        """
        try:
            # Get service statistics
            service_stats = self.multi_network_service.get_service_statistics()
            
            # Get network list with details
            networks = self.multi_network_service.get_network_list()
            
            # Calculate aggregate metrics
            total_cpu_allocated = 0
            total_memory_allocated = 0
            total_clients = 0
            total_active_clients = 0
            
            for network in networks:
                if network.get('resource_allocation'):
                    total_cpu_allocated += network['resource_allocation'].get('cpu_limit_percent', 0)
                    total_memory_allocated += network['resource_allocation'].get('memory_limit_mb', 0)
                
                total_clients += network.get('current_clients', 0)
                total_active_clients += network.get('active_clients', 0)
            
            # System health indicators
            system_resources = service_stats.get('system_resources', {}).get('system', {})
            cpu_usage = system_resources.get('cpu_usage_percent', 0)
            memory_usage = system_resources.get('memory_used_gb', 0) / system_resources.get('memory_total_gb', 1) * 100
            
            health_status = "healthy"
            if cpu_usage > 80 or memory_usage > 80:
                health_status = "warning"
            if cpu_usage > 95 or memory_usage > 95:
                health_status = "critical"
            
            return {
                'overview': {
                    'total_networks': len(networks),
                    'total_clients': total_clients,
                    'active_clients': total_active_clients,
                    'system_health': health_status,
                    'cpu_usage_percent': cpu_usage,
                    'memory_usage_percent': memory_usage,
                    'total_cpu_allocated': total_cpu_allocated,
                    'total_memory_allocated_mb': total_memory_allocated
                },
                'networks': networks,
                'service_statistics': service_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {}
    
    def get_network_performance_metrics(self, network_id: str, 
                                      time_range_minutes: int = 60) -> Dict[str, Any]:
        """
        Get performance metrics for a specific network
        
        Args:
            network_id: Network identifier
            time_range_minutes: Time range for metrics in minutes
            
        Returns:
            Performance metrics data
        """
        try:
            network_details = self.multi_network_service.get_network_details(network_id)
            if not network_details:
                return {}
            
            # Get resource history
            resource_history = network_details.get('resource_history', [])
            
            # Filter by time range
            cutoff_time = datetime.now() - timedelta(minutes=time_range_minutes)
            filtered_history = [
                metric for metric in resource_history
                if datetime.fromisoformat(metric['timestamp']) > cutoff_time
            ]
            
            # Calculate metrics
            if not filtered_history:
                return {'network_id': network_id, 'metrics': [], 'summary': {}}
            
            cpu_values = [m['cpu_usage_percent'] for m in filtered_history]
            memory_values = [m['memory_usage_mb'] for m in filtered_history]
            gpu_values = [m['gpu_usage_percent'] for m in filtered_history]
            
            summary = {
                'cpu_avg': sum(cpu_values) / len(cpu_values),
                'cpu_max': max(cpu_values),
                'cpu_min': min(cpu_values),
                'memory_avg': sum(memory_values) / len(memory_values),
                'memory_max': max(memory_values),
                'memory_min': min(memory_values),
                'gpu_avg': sum(gpu_values) / len(gpu_values),
                'gpu_max': max(gpu_values),
                'gpu_min': min(gpu_values),
                'data_points': len(filtered_history),
                'time_range_minutes': time_range_minutes
            }
            
            return {
                'network_id': network_id,
                'metrics': filtered_history,
                'summary': summary,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance metrics for network {network_id}: {e}")
            return {}
    
    def add_dashboard_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Add callback for dashboard updates
        
        Args:
            callback: Function to call on dashboard updates
        """
        self.dashboard_callbacks.append(callback)
    
    def remove_dashboard_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Remove dashboard callback
        
        Args:
            callback: Callback function to remove
        """
        if callback in self.dashboard_callbacks:
            self.dashboard_callbacks.remove(callback)
    
    # Private methods
    
    def _dashboard_update_loop(self) -> None:
        """Dashboard update loop"""
        logger.info("Dashboard update loop started")
        
        while self.dashboard_active:
            try:
                # Get dashboard data
                dashboard_data = self.get_dashboard_data()
                
                # Notify callbacks
                for callback in self.dashboard_callbacks:
                    try:
                        callback(dashboard_data)
                    except Exception as e:
                        logger.error(f"Dashboard callback error: {e}")
                
                # Sleep until next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                if self.dashboard_active:
                    logger.error(f"Dashboard update error: {e}")
                time.sleep(1.0)
        
        logger.info("Dashboard update loop stopped")


# Utility functions for multi-network management

def create_multi_network_service(storage_dir: str = None, node_id: str = None) -> MultiNetworkService:
    """
    Create and initialize a multi-network service instance
    
    Args:
        storage_dir: Directory for network storage
        node_id: Node identifier
        
    Returns:
        MultiNetworkService instance
    """
    return MultiNetworkService(storage_dir=storage_dir, node_id=node_id)


def get_network_resource_recommendations(model_id: str, expected_clients: int) -> Dict[str, Any]:
    """
    Get resource allocation recommendations for a network
    
    Args:
        model_id: Model identifier
        expected_clients: Expected number of clients
        
    Returns:
        Resource recommendations
    """
    # Model-specific recommendations
    model_specs = {
        'llama3_1_8b_fp16': {
            'base_cpu_percent': 20,
            'base_memory_gb': 8,
            'base_gpu_percent': 60,
            'base_gpu_memory_gb': 6
        },
        'mistral_7b_int4': {
            'base_cpu_percent': 15,
            'base_memory_gb': 4,
            'base_gpu_percent': 40,
            'base_gpu_memory_gb': 3
        }
    }
    
    specs = model_specs.get(model_id, {
        'base_cpu_percent': 25,
        'base_memory_gb': 6,
        'base_gpu_percent': 50,
        'base_gpu_memory_gb': 4
    })
    
    # Scale with client count
    client_scaling = min(expected_clients * 0.1, 2.0)  # Max 2x scaling
    
    recommendations = {
        'cpu_percent': min(specs['base_cpu_percent'] * (1 + client_scaling), 90),
        'memory_gb': specs['base_memory_gb'] * (1 + client_scaling * 0.5),
        'gpu_percent': specs['base_gpu_percent'],
        'gpu_memory_gb': specs['base_gpu_memory_gb'],
        'bandwidth_mbps': expected_clients * 10,
        'priority': NetworkPriority.NORMAL.value,
        'model_id': model_id,
        'expected_clients': expected_clients
    }
    
    return recommendations