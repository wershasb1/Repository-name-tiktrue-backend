"""
Scheduler Library for Distributed Model Inference
Implements scheduling algorithms for optimal CPU/GPU task distribution
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import time

logger = logging.getLogger("SchedulerLib")


class StaticSplitScheduler:
    """
    Static scheduler that finds the optimal split point between CPU and GPU execution
    to minimize total pipeline execution time.
    """
    
    def __init__(self, profile_path: str, block_order: List[str]):
        """
        Initialize the static split scheduler.
        
        Args:
            profile_path: Path to performance_profile.json file
            block_order: List of block IDs in execution order
        """
        self.profile_path = Path(profile_path)
        self.block_order = block_order
        self.performance_profile = {}
        self.optimal_split_point = None
        self.optimal_pipeline_time = float('inf')
        
        # Load performance profile
        self._load_performance_profile()
        
        logger.info(
            f"Initialized StaticSplitScheduler with {len(block_order)} blocks",
            extra={"custom_extra_fields": {
                "event_type": "SCHEDULER_INITIALIZED",
                "data": {
                    "profile_path": str(self.profile_path),
                    "num_blocks": len(block_order),
                    "blocks": block_order
                }
            }}
        )
    
    def _load_performance_profile(self):
        """Load and validate the performance profile from JSON file"""
        try:
            if not self.profile_path.exists():
                raise FileNotFoundError(f"Performance profile not found: {self.profile_path}")
            
            with open(self.profile_path, 'r', encoding='utf-8') as f:
                self.performance_profile = json.load(f)
            
            # Validate that all blocks in block_order exist in profile
            missing_blocks = []
            for block_id in self.block_order:
                if block_id not in self.performance_profile:
                    missing_blocks.append(block_id)
            
            if missing_blocks:
                logger.warning(
                    f"Missing performance data for blocks: {missing_blocks}",
                    extra={"custom_extra_fields": {
                        "event_type": "SCHEDULER_MISSING_PROFILE_DATA",
                        "data": {
                            "missing_blocks": missing_blocks
                        }
                    }}
                )
            
            logger.info(
                f"Loaded performance profile with data for {len(self.performance_profile)} blocks",
                extra={"custom_extra_fields": {
                    "event_type": "SCHEDULER_PROFILE_LOADED",
                    "data": {
                        "profile_blocks": len(self.performance_profile),
                        "profile_path": str(self.profile_path)
                    }
                }}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to load performance profile: {e}",
                exc_info=True,
                extra={"custom_extra_fields": {
                    "event_type": "SCHEDULER_PROFILE_LOAD_ERROR",
                    "data": {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "profile_path": str(self.profile_path)
                    }
                }}
            )
            raise
    
    def _get_execution_time(self, block_id: str, provider: str) -> float:
        """
        Get execution time for a block on a specific provider.
        
        Args:
            block_id: Block identifier
            provider: Either 'CPUExecutionProvider' or 'DmlExecutionProvider'
            
        Returns:
            Execution time in milliseconds
        """
        if block_id not in self.performance_profile:
            # Return a default high value if profile data is missing
            logger.warning(f"No profile data for {block_id}, using default time")
            return 1000.0  # 1 second default
        
        block_profile = self.performance_profile[block_id]
        
        if provider not in block_profile:
            # Return a default high value if provider data is missing
            logger.warning(f"No {provider} data for {block_id}, using default time")
            return 1000.0
        
        # Use mean_ms if available, otherwise calculate from raw data
        provider_data = block_profile[provider]
        if 'mean_ms' in provider_data:
            return provider_data['mean_ms']
        elif 'measurements_ms' in provider_data and provider_data['measurements_ms']:
            # Calculate mean from raw measurements
            measurements = provider_data['measurements_ms']
            return sum(measurements) / len(measurements)
        else:
            logger.warning(f"No timing data for {block_id} on {provider}, using default")
            return 1000.0
    
    def generate_execution_plan(self) -> Dict[str, str]:
        """
        Generate the optimal execution plan by finding the best split point.
        
        The algorithm tests all possible split points k where:
        - Blocks 0 to k-1 run on CPU
        - Blocks k to end run on GPU
        
        Returns:
            Dictionary mapping block_id to worker type ("CPU" or "GPU")
        """
        num_blocks = len(self.block_order)
        best_k = 0
        best_pipeline_time = float('inf')
        
        # Store detailed analysis for logging
        split_analysis = []
        
        logger.info(
            f"Starting optimal split point search for {num_blocks} blocks",
            extra={"custom_extra_fields": {
                "event_type": "SCHEDULER_SPLIT_SEARCH_START",
                "data": {
                    "num_blocks": num_blocks,
                    "block_order": self.block_order
                }
            }}
        )
        
        # Test all possible split points (k from 0 to num_blocks)
        for k in range(num_blocks + 1):
            # Split blocks
            cpu_tasks = self.block_order[:k]  # Blocks 0 to k-1
            gpu_tasks = self.block_order[k:]  # Blocks k to end
            
            # Calculate total time for each worker
            total_cpu_time = 0.0
            for block_id in cpu_tasks:
                cpu_time = self._get_execution_time(block_id, 'CPUExecutionProvider')
                total_cpu_time += cpu_time
            
            total_gpu_time = 0.0
            for block_id in gpu_tasks:
                gpu_time = self._get_execution_time(block_id, 'DmlExecutionProvider')
                total_gpu_time += gpu_time
            
            # Pipeline time is the maximum of the two (they run in parallel)
            pipeline_time = max(total_cpu_time, total_gpu_time)
            
            # Store analysis
            split_analysis.append({
                'k': k,
                'cpu_blocks': len(cpu_tasks),
                'gpu_blocks': len(gpu_tasks),
                'cpu_time_ms': round(total_cpu_time, 2),
                'gpu_time_ms': round(total_gpu_time, 2),
                'pipeline_time_ms': round(pipeline_time, 2),
                'time_difference_ms': round(abs(total_cpu_time - total_gpu_time), 2)
            })
            
            # Check if this is the best split
            if pipeline_time < best_pipeline_time:
                best_pipeline_time = pipeline_time
                best_k = k
            
            logger.debug(
                f"Split point k={k}: CPU blocks={len(cpu_tasks)}, "
                f"GPU blocks={len(gpu_tasks)}, pipeline_time={pipeline_time:.2f}ms",
                extra={"custom_extra_fields": {
                    "event_type": "SCHEDULER_SPLIT_POINT_ANALYSIS",
                    "data": split_analysis[-1]
                }}
            )
        
        # Store optimal split information
        self.optimal_split_point = best_k
        self.optimal_pipeline_time = best_pipeline_time
        
        # Generate execution plan based on optimal split
        execution_plan = {}
        for i, block_id in enumerate(self.block_order):
            if i < best_k:
                execution_plan[block_id] = "CPU"
            else:
                execution_plan[block_id] = "GPU"
        
        # Log the optimal solution
        optimal_analysis = split_analysis[best_k]
        logger.info(
            f"Found optimal split point: k={best_k} with pipeline time={best_pipeline_time:.2f}ms",
            extra={"custom_extra_fields": {
                "event_type": "SCHEDULER_OPTIMAL_SPLIT_FOUND",
                "data": {
                    "optimal_k": best_k,
                    "optimal_pipeline_time_ms": round(best_pipeline_time, 2),
                    "cpu_blocks": self.block_order[:best_k],
                    "gpu_blocks": self.block_order[best_k:],
                    "cpu_time_ms": optimal_analysis['cpu_time_ms'],
                    "gpu_time_ms": optimal_analysis['gpu_time_ms'],
                    "time_balance_ms": optimal_analysis['time_difference_ms'],
                    "execution_plan_summary": {
                        "total_blocks": num_blocks,
                        "cpu_blocks_count": best_k,
                        "gpu_blocks_count": num_blocks - best_k
                    }
                }
            }}
        )
        
        # Log top 3 best splits for comparison
        sorted_analysis = sorted(split_analysis, key=lambda x: x['pipeline_time_ms'])
        logger.info(
            "Top 3 split points by pipeline time",
            extra={"custom_extra_fields": {
                "event_type": "SCHEDULER_TOP_SPLITS",
                "data": {
                    "top_splits": sorted_analysis[:3]
                }
            }}
        )
        
        return execution_plan
    
    def get_worker_for_block(self, block_id: str) -> str:
        """
        Get the assigned worker type for a specific block.
        
        Args:
            block_id: Block identifier
            
        Returns:
            Worker type ("CPU" or "GPU")
        """
        if not hasattr(self, '_execution_plan'):
            self._execution_plan = self.generate_execution_plan()
        
        return self._execution_plan.get(block_id, "CPU")  # Default to CPU if not found
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the execution plan.
        
        Returns:
            Dictionary with execution plan statistics
        """
        if not hasattr(self, '_execution_plan'):
            self._execution_plan = self.generate_execution_plan()
        
        cpu_blocks = [b for b, w in self._execution_plan.items() if w == "CPU"]
        gpu_blocks = [b for b, w in self._execution_plan.items() if w == "GPU"]
        
        # Calculate expected times
        cpu_time = sum(self._get_execution_time(b, 'CPUExecutionProvider') for b in cpu_blocks)
        gpu_time = sum(self._get_execution_time(b, 'DmlExecutionProvider') for b in gpu_blocks)
        
        return {
            "total_blocks": len(self.block_order),
            "cpu_blocks": cpu_blocks,
            "gpu_blocks": gpu_blocks,
            "cpu_blocks_count": len(cpu_blocks),
            "gpu_blocks_count": len(gpu_blocks),
            "expected_cpu_time_ms": round(cpu_time, 2),
            "expected_gpu_time_ms": round(gpu_time, 2),
            "expected_pipeline_time_ms": round(max(cpu_time, gpu_time), 2),
            "time_balance_difference_ms": round(abs(cpu_time - gpu_time), 2),
            "optimal_split_point": self.optimal_split_point
        }


# Example usage and testing
if __name__ == "__main__":
    # Example performance profile for testing
    test_profile = {
        "block_1": {
            "CPUExecutionProvider": {"mean_ms": 10.5},
            "DmlExecutionProvider": {"mean_ms": 8.2}
        },
        "block_2": {
            "CPUExecutionProvider": {"mean_ms": 15.3},
            "DmlExecutionProvider": {"mean_ms": 9.7}
        },
        "block_3": {
            "CPUExecutionProvider": {"mean_ms": 12.1},
            "DmlExecutionProvider": {"mean_ms": 7.8}
        },
        "block_4": {
            "CPUExecutionProvider": {"mean_ms": 18.7},
            "DmlExecutionProvider": {"mean_ms": 11.2}
        },
        "block_5": {
            "CPUExecutionProvider": {"mean_ms": 14.2},
            "DmlExecutionProvider": {"mean_ms": 8.9}
        }
    }
    
    # Save test profile
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_profile, f)
        test_profile_path = f.name
    
    # Test the scheduler
    block_order = ["block_1", "block_2", "block_3", "block_4", "block_5"]
    scheduler = StaticSplitScheduler(test_profile_path, block_order)
    
    # Generate execution plan
    plan = scheduler.generate_execution_plan()
    print("Execution Plan:", plan)
    
    # Get summary
    summary = scheduler.get_execution_summary()
    print("Execution Summary:", json.dumps(summary, indent=2))
    
    # Clean up
    Path(test_profile_path).unlink()