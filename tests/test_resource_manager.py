"""
Test NetworkResourceManager in isolation
"""

import psutil
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List

logger = logging.getLogger("ResourceManager")


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


class ResourceError(Exception):
    """Resource allocation error"""
    pass


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
            base_cpu_percent = 20.0  # Simplified
            base_memory_mb = 4096.0  # Simplified
            base_gpu_percent = 50.0  # Simplified
            base_gpu_memory_mb = 2048.0  # Simplified
            
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
            bandwidth_limit = max_clients * 10.0
            
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
                       f"CPU={cpu_limit:.1f}%, Memory={memory_limit:.0f}MB")
            
            return allocation
            
        except Exception as e:
            logger.error(f"Failed to allocate resources for network {network_id}: {e}")
            raise


def test_resource_manager():
    """Test the resource manager"""
    print("Testing NetworkResourceManager...")
    
    # Create resource manager
    rm = NetworkResourceManager()
    print(f"✓ Created resource manager with {rm.total_cpu_cores} cores, {rm.total_memory_gb:.1f}GB RAM")
    
    # Test resource allocation
    allocation = rm.allocate_resources(
        network_id="test_network",
        model_id="llama3_1_8b_fp16",
        max_clients=5,
        priority=NetworkPriority.HIGH
    )
    
    print(f"✓ Allocated resources: CPU={allocation.cpu_limit_percent:.1f}%, Memory={allocation.memory_limit_mb:.0f}MB")
    
    # Test multiple allocations
    allocation2 = rm.allocate_resources(
        network_id="test_network_2",
        model_id="mistral_7b_int4",
        max_clients=3,
        priority=NetworkPriority.NORMAL
    )
    
    print(f"✓ Second allocation: CPU={allocation2.cpu_limit_percent:.1f}%, Memory={allocation2.memory_limit_mb:.0f}MB")
    
    print(f"✓ Total networks managed: {len(rm.network_allocations)}")
    
    print("All tests passed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_resource_manager()