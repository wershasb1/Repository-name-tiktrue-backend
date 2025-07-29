"""
Dynamic Resource Allocation System
Implements license-aware resource distribution across networks with dynamic worker allocation,
conflict resolution, and priority-based scheduling
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
from collections import defaultdict, deque
import heapq

from security.license_validator import LicenseInfo, SubscriptionTier
from api_client import NetworkConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ResourceAllocator")


class ResourceType(Enum):
    """Types of resources that can be allocated"""
    CPU_CORES = "cpu_cores"
    MEMORY_GB = "memory_gb"
    GPU_MEMORY_GB = "gpu_memory_gb"
    NETWORK_BANDWIDTH_MBPS = "network_bandwidth_mbps"
    WORKER_SLOTS = "worker_slots"
    CLIENT_CONNECTIONS = "client_connections"


class AllocationPriority(Enum):
    """Priority levels for resource allocation"""
    CRITICAL = 1    # System critical operations
    HIGH = 2        # Premium license holders
    NORMAL = 3      # Standard operations
    LOW = 4         # Background tasks
    MAINTENANCE = 5 # Maintenance operations


@dataclass
class ResourceQuota:
    """Resource quota definition"""
    cpu_cores: float = 0.0
    memory_gb: float = 0.0
    gpu_memory_gb: float = 0.0
    network_bandwidth_mbps: float = 0.0
    worker_slots: int = 0
    client_connections: int = 0
    
    def __add__(self, other: 'ResourceQuota') -> 'ResourceQuota':
        """Add two resource quotas"""
        return ResourceQuota(
            cpu_cores=self.cpu_cores + other.cpu_cores,
            memory_gb=self.memory_gb + other.memory_gb,
            gpu_memory_gb=self.gpu_memory_gb + other.gpu_memory_gb,
            network_bandwidth_mbps=self.network_bandwidth_mbps + other.network_bandwidth_mbps,
            worker_slots=self.worker_slots + other.worker_slots,
            client_connections=self.client_connections + other.client_connections
        )
    
    def __sub__(self, other: 'ResourceQuota') -> 'ResourceQuota':
        """Subtract two resource quotas"""
        return ResourceQuota(
            cpu_cores=max(0, self.cpu_cores - other.cpu_cores),
            memory_gb=max(0, self.memory_gb - other.memory_gb),
            gpu_memory_gb=max(0, self.gpu_memory_gb - other.gpu_memory_gb),
            network_bandwidth_mbps=max(0, self.network_bandwidth_mbps - other.network_bandwidth_mbps),
            worker_slots=max(0, self.worker_slots - other.worker_slots),
            client_connections=max(0, self.client_connections - other.client_connections)
        )
    
    def can_satisfy(self, required: 'ResourceQuota') -> bool:
        """Check if this quota can satisfy the required resources"""
        return (
            self.cpu_cores >= required.cpu_cores and
            self.memory_gb >= required.memory_gb and
            self.gpu_memory_gb >= required.gpu_memory_gb and
            self.network_bandwidth_mbps >= required.network_bandwidth_mbps and
            self.worker_slots >= required.worker_slots and
            self.client_connections >= required.client_connections
        )
    
    def to_dict(self) -> Dict[str, Union[float, int]]:
        """Convert to dictionary"""
        return {
            "cpu_cores": self.cpu_cores,
            "memory_gb": self.memory_gb,
            "gpu_memory_gb": self.gpu_memory_gb,
            "network_bandwidth_mbps": self.network_bandwidth_mbps,
            "worker_slots": self.worker_slots,
            "client_connections": self.client_connections
        }


@dataclass
class ResourceRequest:
    """Resource allocation request"""
    request_id: str
    network_id: str
    required_resources: ResourceQuota
    priority: AllocationPriority
    requested_at: datetime
    timeout_seconds: float = 300.0  # 5 minutes default
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if request has expired"""
        return (datetime.now() - self.requested_at).total_seconds() > self.timeout_seconds
    
    def __lt__(self, other: 'ResourceRequest') -> bool:
        """For priority queue ordering"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.requested_at < other.requested_at


@dataclass
class ResourceAllocation:
    """Active resource allocation"""
    allocation_id: str
    network_id: str
    allocated_resources: ResourceQuota
    allocated_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if allocation has expired"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class NetworkResourceProfile:
    """Resource profile for a network"""
    network_id: str
    base_requirements: ResourceQuota
    peak_requirements: ResourceQuota
    current_usage: ResourceQuota
    priority: AllocationPriority
    scaling_factor: float = 1.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def get_dynamic_requirements(self, load_factor: float = 1.0) -> ResourceQuota:
        """Calculate dynamic resource requirements based on load"""
        # Interpolate between base and peak based on load factor
        factor = min(1.0, max(0.0, load_factor)) * self.scaling_factor
        
        return ResourceQuota(
            cpu_cores=self.base_requirements.cpu_cores + 
                     (self.peak_requirements.cpu_cores - self.base_requirements.cpu_cores) * factor,
            memory_gb=self.base_requirements.memory_gb + 
                     (self.peak_requirements.memory_gb - self.base_requirements.memory_gb) * factor,
            gpu_memory_gb=self.base_requirements.gpu_memory_gb + 
                         (self.peak_requirements.gpu_memory_gb - self.base_requirements.gpu_memory_gb) * factor,
            network_bandwidth_mbps=self.base_requirements.network_bandwidth_mbps + 
                                  (self.peak_requirements.network_bandwidth_mbps - self.base_requirements.network_bandwidth_mbps) * factor,
            worker_slots=int(self.base_requirements.worker_slots + 
                           (self.peak_requirements.worker_slots - self.base_requirements.worker_slots) * factor),
            client_connections=int(self.base_requirements.client_connections + 
                                 (self.peak_requirements.client_connections - self.base_requirements.client_connections) * factor)
        )


class ResourceConflictResolver:
    """Handles resource allocation conflicts"""
    
    def __init__(self):
        self.resolution_strategies = {
            "priority_based": self._resolve_by_priority,
            "fair_share": self._resolve_by_fair_share,
            "first_come_first_serve": self._resolve_by_fcfs,
            "license_tier": self._resolve_by_license_tier
        }
    
    def resolve_conflict(self, 
                        requests: List[ResourceRequest], 
                        available_resources: ResourceQuota,
                        strategy: str = "priority_based") -> List[ResourceRequest]:
        """
        Resolve resource allocation conflicts
        
        Args:
            requests: List of conflicting requests
            available_resources: Available resources
            strategy: Resolution strategy
            
        Returns:
            List of requests that can be satisfied
        """
        if strategy not in self.resolution_strategies:
            strategy = "priority_based"
        
        return self.resolution_strategies[strategy](requests, available_resources)
    
    def _resolve_by_priority(self, 
                           requests: List[ResourceRequest], 
                           available_resources: ResourceQuota) -> List[ResourceRequest]:
        """Resolve conflicts by priority"""
        # Sort by priority and timestamp
        sorted_requests = sorted(requests, key=lambda r: (r.priority.value, r.requested_at))
        
        satisfied_requests = []
        remaining_resources = available_resources
        
        for request in sorted_requests:
            if remaining_resources.can_satisfy(request.required_resources):
                satisfied_requests.append(request)
                remaining_resources = remaining_resources - request.required_resources
        
        return satisfied_requests
    
    def _resolve_by_fair_share(self, 
                             requests: List[ResourceRequest], 
                             available_resources: ResourceQuota) -> List[ResourceRequest]:
        """Resolve conflicts by fair share allocation"""
        if not requests:
            return []
        
        # Calculate fair share per request
        num_requests = len(requests)
        fair_share = ResourceQuota(
            cpu_cores=available_resources.cpu_cores / num_requests,
            memory_gb=available_resources.memory_gb / num_requests,
            gpu_memory_gb=available_resources.gpu_memory_gb / num_requests,
            network_bandwidth_mbps=available_resources.network_bandwidth_mbps / num_requests,
            worker_slots=available_resources.worker_slots // num_requests,
            client_connections=available_resources.client_connections // num_requests
        )
        
        satisfied_requests = []
        for request in requests:
            # Check if request can be satisfied with fair share
            if fair_share.can_satisfy(request.required_resources):
                satisfied_requests.append(request)
        
        return satisfied_requests
    
    def _resolve_by_fcfs(self, 
                        requests: List[ResourceRequest], 
                        available_resources: ResourceQuota) -> List[ResourceRequest]:
        """Resolve conflicts by first-come-first-serve"""
        # Sort by request timestamp
        sorted_requests = sorted(requests, key=lambda r: r.requested_at)
        
        satisfied_requests = []
        remaining_resources = available_resources
        
        for request in sorted_requests:
            if remaining_resources.can_satisfy(request.required_resources):
                satisfied_requests.append(request)
                remaining_resources = remaining_resources - request.required_resources
        
        return satisfied_requests
    
    def _resolve_by_license_tier(self, 
                                requests: List[ResourceRequest], 
                                available_resources: ResourceQuota) -> List[ResourceRequest]:
        """Resolve conflicts by license tier priority"""
        # This would need license information - for now use priority
        return self._resolve_by_priority(requests, available_resources)


class DynamicResourceAllocator:
    """
    Main dynamic resource allocation system
    """
    
    def __init__(self, 
                 total_resources: ResourceQuota,
                 license_info: Optional[LicenseInfo] = None,
                 allocation_interval: float = 10.0,
                 cleanup_interval: float = 60.0):
        """
        Initialize dynamic resource allocator
        
        Args:
            total_resources: Total available system resources
            license_info: Current license information
            allocation_interval: Interval for allocation processing
            cleanup_interval: Interval for cleanup operations
        """
        self.total_resources = total_resources
        self.license_info = license_info
        self.allocation_interval = allocation_interval
        self.cleanup_interval = cleanup_interval
        
        # Resource tracking
        self.allocated_resources = ResourceQuota()
        self.available_resources = total_resources
        
        # Request and allocation tracking
        self.pending_requests: List[ResourceRequest] = []
        self.active_allocations: Dict[str, ResourceAllocation] = {}
        self.network_profiles: Dict[str, NetworkResourceProfile] = {}
        
        # Conflict resolution
        self.conflict_resolver = ResourceConflictResolver()
        
        # Synchronization
        self.lock = threading.RLock()
        
        # Background tasks
        self.allocation_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "satisfied_requests": 0,
            "rejected_requests": 0,
            "conflicts_resolved": 0,
            "allocations_expired": 0
        }
        
        logger.info(f"Resource allocator initialized with {total_resources.to_dict()}")
    
    async def start(self):
        """Start the resource allocator"""
        if self.running:
            logger.warning("Resource allocator already running")
            return
        
        logger.info("Starting dynamic resource allocator")
        self.running = True
        
        # Start background tasks
        self.allocation_task = asyncio.create_task(self._allocation_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Dynamic resource allocator started")
    
    async def stop(self):
        """Stop the resource allocator"""
        if not self.running:
            logger.warning("Resource allocator not running")
            return
        
        logger.info("Stopping dynamic resource allocator")
        self.running = False
        
        # Cancel background tasks
        if self.allocation_task:
            self.allocation_task.cancel()
            try:
                await self.allocation_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Dynamic resource allocator stopped")
    
    def register_network_profile(self, profile: NetworkResourceProfile):
        """Register a network resource profile"""
        with self.lock:
            self.network_profiles[profile.network_id] = profile
            logger.info(f"Registered network profile: {profile.network_id}")
    
    def update_network_profile(self, network_id: str, **kwargs):
        """Update network resource profile"""
        with self.lock:
            if network_id in self.network_profiles:
                profile = self.network_profiles[network_id]
                for key, value in kwargs.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                profile.last_updated = datetime.now()
                logger.debug(f"Updated network profile: {network_id}")
    
    def request_resources(self, request: ResourceRequest) -> str:
        """
        Request resource allocation
        
        Args:
            request: Resource request
            
        Returns:
            Request ID for tracking
        """
        with self.lock:
            # Check if request is reasonable
            if not self._validate_request(request):
                self.stats["rejected_requests"] += 1
                raise ValueError(f"Invalid resource request: {request.request_id}")
            
            # Add to pending requests
            self.pending_requests.append(request)
            self.stats["total_requests"] += 1
            
            logger.info(f"Resource request queued: {request.request_id} for {request.network_id}")
            return request.request_id
    
    def release_resources(self, allocation_id: str) -> bool:
        """
        Release allocated resources
        
        Args:
            allocation_id: Allocation ID to release
            
        Returns:
            True if successfully released
        """
        with self.lock:
            if allocation_id not in self.active_allocations:
                logger.warning(f"Allocation not found: {allocation_id}")
                return False
            
            allocation = self.active_allocations[allocation_id]
            
            # Return resources to available pool
            self.allocated_resources = self.allocated_resources - allocation.allocated_resources
            self.available_resources = self.available_resources + allocation.allocated_resources
            
            # Remove allocation
            del self.active_allocations[allocation_id]
            
            logger.info(f"Resources released: {allocation_id} for {allocation.network_id}")
            return True
    
    def get_allocation_status(self, allocation_id: str) -> Optional[ResourceAllocation]:
        """Get status of a resource allocation"""
        with self.lock:
            return self.active_allocations.get(allocation_id)
    
    def get_network_allocations(self, network_id: str) -> List[ResourceAllocation]:
        """Get all allocations for a network"""
        with self.lock:
            return [alloc for alloc in self.active_allocations.values() 
                   if alloc.network_id == network_id]
    
    def get_resource_utilization(self) -> Dict[str, Any]:
        """Get current resource utilization"""
        with self.lock:
            total_dict = self.total_resources.to_dict()
            allocated_dict = self.allocated_resources.to_dict()
            available_dict = self.available_resources.to_dict()
            
            utilization = {}
            for key in total_dict:
                if total_dict[key] > 0:
                    utilization[key] = {
                        "total": total_dict[key],
                        "allocated": allocated_dict[key],
                        "available": available_dict[key],
                        "utilization_percent": (allocated_dict[key] / total_dict[key]) * 100
                    }
                else:
                    utilization[key] = {
                        "total": 0,
                        "allocated": 0,
                        "available": 0,
                        "utilization_percent": 0
                    }
            
            return {
                "resources": utilization,
                "active_allocations": len(self.active_allocations),
                "pending_requests": len(self.pending_requests),
                "statistics": self.stats.copy()
            }
    
    def _validate_request(self, request: ResourceRequest) -> bool:
        """Validate resource request"""
        # Check if request is within reasonable bounds
        total_dict = self.total_resources.to_dict()
        required_dict = request.required_resources.to_dict()
        
        for key in required_dict:
            if required_dict[key] > total_dict[key]:
                logger.warning(f"Request exceeds total resources: {key} = {required_dict[key]} > {total_dict[key]}")
                return False
        
        # Check license limits
        if self.license_info:
            if self.license_info.plan == SubscriptionTier.FREE:
                # Free tier limitations
                if request.required_resources.worker_slots > 2:
                    logger.warning("Free tier limited to 2 worker slots")
                    return False
                if request.required_resources.client_connections > 3:
                    logger.warning("Free tier limited to 3 client connections")
                    return False
            elif self.license_info.plan == SubscriptionTier.PRO:
                # Pro tier limitations
                if request.required_resources.worker_slots > 10:
                    logger.warning("Pro tier limited to 10 worker slots")
                    return False
                if request.required_resources.client_connections > 20:
                    logger.warning("Pro tier limited to 20 client connections")
                    return False
        
        return True
    
    async def _allocation_loop(self):
        """Main allocation processing loop"""
        try:
            while self.running:
                await self._process_pending_requests()
                await asyncio.sleep(self.allocation_interval)
        except asyncio.CancelledError:
            logger.info("Allocation loop cancelled")
        except Exception as e:
            logger.error(f"Error in allocation loop: {e}")
    
    async def _cleanup_loop(self):
        """Cleanup expired requests and allocations"""
        try:
            while self.running:
                await self._cleanup_expired()
                await asyncio.sleep(self.cleanup_interval)
        except asyncio.CancelledError:
            logger.info("Cleanup loop cancelled")
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}")
    
    async def _process_pending_requests(self):
        """Process pending resource requests"""
        with self.lock:
            if not self.pending_requests:
                return
            
            # Remove expired requests
            current_time = datetime.now()
            valid_requests = [req for req in self.pending_requests if not req.is_expired()]
            expired_count = len(self.pending_requests) - len(valid_requests)
            if expired_count > 0:
                logger.info(f"Removed {expired_count} expired requests")
                self.stats["rejected_requests"] += expired_count
            
            self.pending_requests = valid_requests
            
            if not self.pending_requests:
                return
            
            # Group requests that might conflict
            conflicting_requests = []
            satisfied_requests = []
            
            # Sort requests by priority
            sorted_requests = sorted(self.pending_requests, key=lambda r: (r.priority.value, r.requested_at))
            
            remaining_resources = self.available_resources
            
            for request in sorted_requests:
                if remaining_resources.can_satisfy(request.required_resources):
                    # Can satisfy immediately
                    allocation = self._create_allocation(request)
                    if allocation:
                        satisfied_requests.append(request)
                        remaining_resources = remaining_resources - request.required_resources
                else:
                    # Potential conflict
                    conflicting_requests.append(request)
            
            # Handle conflicts
            if conflicting_requests:
                resolved_requests = self.conflict_resolver.resolve_conflict(
                    conflicting_requests, remaining_resources, "priority_based"
                )
                
                for request in resolved_requests:
                    allocation = self._create_allocation(request)
                    if allocation:
                        satisfied_requests.append(request)
                
                if resolved_requests:
                    self.stats["conflicts_resolved"] += 1
            
            # Remove satisfied requests from pending
            for request in satisfied_requests:
                if request in self.pending_requests:
                    self.pending_requests.remove(request)
                self.stats["satisfied_requests"] += 1
            
            if satisfied_requests:
                logger.info(f"Processed {len(satisfied_requests)} resource requests")
    
    def _create_allocation(self, request: ResourceRequest) -> Optional[ResourceAllocation]:
        """Create resource allocation from request"""
        try:
            allocation_id = f"alloc_{request.network_id}_{int(time.time() * 1000)}"
            
            allocation = ResourceAllocation(
                allocation_id=allocation_id,
                network_id=request.network_id,
                allocated_resources=request.required_resources,
                allocated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24),  # Default 24 hour expiry
                metadata=request.metadata.copy()
            )
            
            # Update resource tracking
            self.allocated_resources = self.allocated_resources + request.required_resources
            self.available_resources = self.available_resources - request.required_resources
            
            # Store allocation
            self.active_allocations[allocation_id] = allocation
            
            logger.info(f"Created allocation: {allocation_id} for {request.network_id}")
            return allocation
            
        except Exception as e:
            logger.error(f"Failed to create allocation: {e}")
            return None
    
    async def _cleanup_expired(self):
        """Clean up expired allocations"""
        with self.lock:
            expired_allocations = []
            
            for allocation_id, allocation in self.active_allocations.items():
                if allocation.is_expired():
                    expired_allocations.append(allocation_id)
            
            for allocation_id in expired_allocations:
                self.release_resources(allocation_id)
                self.stats["allocations_expired"] += 1
            
            if expired_allocations:
                logger.info(f"Cleaned up {len(expired_allocations)} expired allocations")


def create_default_resource_quota(license_info: Optional[LicenseInfo] = None) -> ResourceQuota:
    """Create default resource quota based on license"""
    if not license_info:
        # Default free tier
        return ResourceQuota(
            cpu_cores=2.0,
            memory_gb=4.0,
            gpu_memory_gb=2.0,
            network_bandwidth_mbps=100.0,
            worker_slots=2,
            client_connections=3
        )
    
    if license_info.plan == SubscriptionTier.FREE:
        return ResourceQuota(
            cpu_cores=2.0,
            memory_gb=4.0,
            gpu_memory_gb=2.0,
            network_bandwidth_mbps=100.0,
            worker_slots=2,
            client_connections=3
        )
    elif license_info.plan == SubscriptionTier.PRO:
        return ResourceQuota(
            cpu_cores=8.0,
            memory_gb=16.0,
            gpu_memory_gb=8.0,
            network_bandwidth_mbps=1000.0,
            worker_slots=10,
            client_connections=20
        )
    else:  # ENT
        return ResourceQuota(
            cpu_cores=32.0,
            memory_gb=64.0,
            gpu_memory_gb=32.0,
            network_bandwidth_mbps=10000.0,
            worker_slots=50,
            client_connections=100
        )


def create_network_profile(network_config: NetworkConfig, 
                          license_info: Optional[LicenseInfo] = None) -> NetworkResourceProfile:
    """Create network resource profile from configuration"""
    # Base requirements (minimum needed)
    base_quota = ResourceQuota(
        cpu_cores=1.0,
        memory_gb=2.0,
        gpu_memory_gb=1.0,
        network_bandwidth_mbps=50.0,
        worker_slots=1,
        client_connections=1
    )
    
    # Peak requirements (maximum needed under load)
    peak_quota = ResourceQuota(
        cpu_cores=4.0,
        memory_gb=8.0,
        gpu_memory_gb=4.0,
        network_bandwidth_mbps=500.0,
        worker_slots=len(network_config.nodes) if network_config.nodes else 2,
        client_connections=10
    )
    
    # Adjust based on license
    if license_info:
        if license_info.plan == SubscriptionTier.FREE:
            peak_quota.worker_slots = min(peak_quota.worker_slots, 2)
            peak_quota.client_connections = min(peak_quota.client_connections, 3)
        elif license_info.plan == SubscriptionTier.PRO:
            peak_quota.worker_slots = min(peak_quota.worker_slots, 10)
            peak_quota.client_connections = min(peak_quota.client_connections, 20)
    
    # Determine priority based on license and network type
    priority = AllocationPriority.NORMAL
    if license_info:
        if license_info.plan == SubscriptionTier.ENT:
            priority = AllocationPriority.HIGH
        elif license_info.plan == SubscriptionTier.PRO:
            priority = AllocationPriority.NORMAL
        else:
            priority = AllocationPriority.LOW
    
    return NetworkResourceProfile(
        network_id=network_config.network_id,
        base_requirements=base_quota,
        peak_requirements=peak_quota,
        current_usage=ResourceQuota(),
        priority=priority,
        scaling_factor=1.0
    )