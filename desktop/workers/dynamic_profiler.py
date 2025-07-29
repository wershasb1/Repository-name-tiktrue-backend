"""
Dynamic Profiler - Simple implementation for testing
"""

import asyncio
import time
import logging
from typing import Dict, Any

logger = logging.getLogger("DynamicProfiler")


class DynamicProfiler:
    """Simple dynamic profiler for testing"""
    
    def __init__(self):
        self.running = False
        self.metrics = {
            'cpu': {'performance_factor': 0.8, 'available': True},
            'gpu': {'performance_factor': 0.7, 'available': True, 'type': 'nvidia'},
            'memory': {'usage_percent': 45.0, 'available_gb': 8.0}
        }
        logger.info("Dynamic profiler initialized (simple implementation)")
    
    async def start_monitoring(self):
        """Start monitoring"""
        self.running = True
        logger.info("Dynamic profiler monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Dynamic profiler monitoring stopped")
    
    async def get_system_performance_factor(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        return self.metrics
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics