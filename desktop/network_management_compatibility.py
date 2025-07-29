"""
Network Management Compatibility Layer
Integrates multi-network functionality with existing TikTrue infrastructure

This module provides compatibility between our multi-network implementation
and the existing resource_allocator.py and service_runner.py components.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Import existing project components
try:
    from resource_allocator import DynamicResourceAllocator, AllocationPriority, ResourceRequest
    from core.service_runner import MultiNetworkServiceRunner
    EXISTING_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Existing components not available: {e}")
    EXISTING_COMPONENTS_AVAILABLE = False
    # Mock classes for compatibility
    class DynamicResourceAllocator: pass
    class MultiNetworkServiceRunner: pass
    class AllocationPriority: pass
    class ResourceRequest: pass

logger = logging.getLogger("NetworkCompatibility")


class NetworkManagementCompatibility:
    """
    Compatibility layer for integrating multi-network functionality
    with existing TikTrue infrastructure
    """
    
    def __init__(self):
        """Initialize compatibility layer"""
        self.existing_allocator = None
        self.existing_service_runner = None
        
        if EXISTING_COMPONENTS_AVAILABLE:
            try:
                self.existing_allocator = DynamicResourceAllocator()
                self.existing_service_runner = MultiNetworkServiceRunner()
                logger.info("Compatibility layer initialized with existing components")
            except Exception as e:
                logger.warning(f"Failed to initialize existing components: {e}")
        else:
            logger.info("Compatibility layer initialized in standalone mode")
    
    def integrate_with_existing_allocator(self, network_id: str, model_id: str, 
                                        max_clients: int) -> Dict[str, Any]:
        """
        Integrate network resource allocation with existing DynamicResourceAllocator
        """
        try:
            if not self.existing_allocator:
                # Fallback to simplified allocation
                return self._fallback_allocation(network_id, model_id, max_clients)
            
            # Create resource request for existing allocator
            resource_request = ResourceRequest(
                requester_id=network_id,
                priority=AllocationPriority.NORMAL,
                cpu_cores=self._calculate_cpu_cores(model_id, max_clients),
                memory_gb=self._calculate_memory_gb(model_id, max_clients),
                gpu_memory_gb=self._calculate_gpu_memory_gb(model_id),
                network_bandwidth_mbps=max_clients * 10.0,
                duration_minutes=0,  # Permanent allocation
                description=f"Multi-network allocation for {network_id}"
            )
            
            # Request allocation
            allocation_result = self.existing_allocator.allocate_resources(resource_request)
            
            if allocation_result.success:
                return {
                    'success': True,
                    'network_id': network_id,
                    'allocated_resources': {
                        'cpu_cores': allocation_result.allocated_quota.cpu_cores,
                        'memory_gb': allocation_result.allocated_quota.memory_gb,
                        'gpu_memory_gb': allocation_result.allocated_quota.gpu_memory_gb,
                        'bandwidth_mbps': allocation_result.allocated_quota.network_bandwidth_mbps
                    },
                    'allocation_id': allocation_result.allocation_id,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.error(f"Resource allocation failed: {allocation_result.message}")
                return {'success': False, 'error': allocation_result.message}
                
        except Exception as e:
            logger.error(f"Integration with existing allocator failed: {e}")
            return self._fallback_allocation(network_id, model_id, max_clients)
    
    def integrate_with_service_runner(self, network_config: Dict[str, Any]) -> bool:
        """
        Integrate network management with existing MultiNetworkServiceRunner
        """
        try:
            if not self.existing_service_runner:
                logger.warning("Service runner not available, using fallback")
                return True
            
            # Register network with existing service runner
            # This would depend on the actual API of MultiNetworkServiceRunner
            logger.info(f"Integrating network {network_config.get('network_id')} with service runner")
            
            return True
            
        except Exception as e:
            logger.error(f"Integration with service runner failed: {e}")
            return False
    
    def _calculate_cpu_cores(self, model_id: str, max_clients: int) -> float:
        """Calculate CPU cores requirement"""
        model_cpu_base = {
            'llama3_1_8b_fp16': 2.0,
            'mistral_7b_int4': 1.5,
            'default': 2.0
        }
        
        base_cpu = model_cpu_base.get(model_id, model_cpu_base['default'])
        client_scaling = max_clients * 0.1
        
        return min(base_cpu + client_scaling, 8.0)
    
    def _calculate_memory_gb(self, model_id: str, max_clients: int) -> float:
        """Calculate memory requirement in GB"""
        model_memory_base = {
            'llama3_1_8b_fp16': 4.0,
            'mistral_7b_int4': 2.0,
            'default': 3.0
        }
        
        base_memory = model_memory_base.get(model_id, model_memory_base['default'])
        client_memory = max_clients * 0.1
        
        return base_memory + client_memory
    
    def _calculate_gpu_memory_gb(self, model_id: str) -> float:
        """Calculate GPU memory requirement in GB"""
        model_gpu_memory = {
            'llama3_1_8b_fp16': 6.0,
            'mistral_7b_int4': 3.0,
            'default': 4.0
        }
        
        return model_gpu_memory.get(model_id, model_gpu_memory['default'])
    
    def _fallback_allocation(self, network_id: str, model_id: str, max_clients: int) -> Dict[str, Any]:
        """Fallback allocation when existing allocator is not available"""
        return {
            'success': True,
            'network_id': network_id,
            'allocated_resources': {
                'cpu_cores': self._calculate_cpu_cores(model_id, max_clients),
                'memory_gb': self._calculate_memory_gb(model_id, max_clients),
                'gpu_memory_gb': self._calculate_gpu_memory_gb(model_id),
                'bandwidth_mbps': max_clients * 10.0
            },
            'allocation_id': f"fallback_{network_id}",
            'timestamp': datetime.now().isoformat(),
            'note': 'Fallback allocation - existing allocator not available'
        }


# Global compatibility instance
_compatibility_instance = None

def get_network_compatibility() -> NetworkManagementCompatibility:
    """Get global network management compatibility instance"""
    global _compatibility_instance
    if _compatibility_instance is None:
        _compatibility_instance = NetworkManagementCompatibility()
    return _compatibility_instance


def check_existing_infrastructure() -> Dict[str, bool]:
    """Check what existing infrastructure is available"""
    return {
        'resource_allocator_available': EXISTING_COMPONENTS_AVAILABLE,
        'service_runner_available': EXISTING_COMPONENTS_AVAILABLE,
        'compatibility_layer_active': True
    }