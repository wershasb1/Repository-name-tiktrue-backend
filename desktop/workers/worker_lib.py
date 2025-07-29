"""
Worker Library for Distributed Model Inference
Implements CPU and GPU workers using asyncio and Actor Model pattern
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import numpy as np
import onnxruntime as ort

# Import from your existing modules
from workers.homf_lib import WarmStatePool

logger = logging.getLogger("WorkerLib")


class BaseWorker:
    """Base worker class implementing the Actor Model pattern"""
    
    def __init__(self, 
                 name: str,
                 execution_providers: List[str],
                 homf_pool: WarmStatePool,  # به جای ساختن، از بیرون دریافت می‌کنیم
                 max_executor_threads: int = 2):
        """
        Initialize base worker
        
        Args:
            name: Worker name for identification
            execution_providers: ONNX Runtime execution providers
            homf_pool: Shared HOMF pool instance (از model_node)
            max_executor_threads: Maximum threads for ThreadPoolExecutor
        """
        self.name = name
        self.execution_providers = execution_providers
        
        # Create inbox queue for receiving jobs
        self.inbox: asyncio.Queue = asyncio.Queue()
        
        # Thread pool for CPU-bound operations
        self.executor = ThreadPoolExecutor(
            max_workers=max_executor_threads,
            thread_name_prefix=f"{name}_executor"
        )
        
        # استفاده از HOMF pool مشترک به جای ساختن یکی جدید
        self.homf_pool = homf_pool
        
        # Statistics
        self.stats = {
            'jobs_processed': 0,
            'jobs_failed': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0
        }
        
        self._running = False
        
        logger.info(
            f"Initialized {name} with providers: {execution_providers}",
            extra={"custom_extra_fields": {
                "event_type": "WORKER_INITIALIZED",
                "worker_name": name,
                "data": {
                    "execution_providers": execution_providers,
                    "max_executor_threads": max_executor_threads,
                    "uses_shared_homf_pool": True  # نشان می‌دهد از pool مشترک استفاده می‌کند
                }
            }}
        )
    
    # بقیه متدها بدون تغییر...
    
    async def shutdown(self):
        """Gracefully shutdown the worker"""
        logger.info(f"Shutting down {self.name}")
        self._running = False
        
        # Send shutdown signal to inbox
        await self.inbox.put(None)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # حذف شد: self.homf_pool.shutdown()
        # چون HOMF pool مشترک است و نباید توسط worker بسته شود
        
        logger.info(
            f"{self.name} shutdown complete. Stats: {self.stats}",
            extra={"custom_extra_fields": {
                "event_type": "WORKER_SHUTDOWN_COMPLETE",
                "worker_name": self.name,
                "data": self.stats
            }}
        )
    
    async def run(self):
        """Main worker loop - runs indefinitely processing jobs from inbox"""
        self._running = True
        logger.info(
            f"{self.name} starting main loop",
            extra={"custom_extra_fields": {
                "event_type": "WORKER_LOOP_START",
                "worker_name": self.name,
                "data": {}
            }}
        )
        
        while self._running:
            try:
                # Wait for a job from the inbox
                job = await self.inbox.get()
                
                if job is None:  # Shutdown signal
                    logger.info(f"{self.name} received shutdown signal")
                    break
                
                # Process the job
                await self._process_job(job)
                
            except asyncio.CancelledError:
                logger.info(f"{self.name} cancelled")
                break
            except Exception as e:
                logger.error(
                    f"{self.name} error in main loop: {e}",
                    exc_info=True,
                    extra={"custom_extra_fields": {
                        "event_type": "WORKER_LOOP_ERROR",
                        "worker_name": self.name,
                        "data": {
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    }}
                )
        
        logger.info(f"{self.name} main loop ended")
        self._running = False
    
    async def _process_job(self, job: Dict[str, Any]):
        """
        Process a single job
        
        Job format:
        {
            'job_id': str,
            'block_id': str,
            'input_data': Dict[str, np.ndarray],
            'requested_outputs': Optional[List[str]],
            'reply_queue': asyncio.Queue,
            'session_id': str,
            'step': int
        }
        """
        job_id = job.get('job_id', 'unknown')
        block_id = job.get('block_id')
        reply_queue = job.get('reply_queue')
        
        start_time = time.perf_counter()
        
        logger.debug(
            f"{self.name} processing job {job_id} for block {block_id}",
            extra={"custom_extra_fields": {
                "event_type": "WORKER_JOB_START",
                "worker_name": self.name,
                "data": {
                    "job_id": job_id,
                    "block_id": block_id,
                    "session_id": job.get('session_id'),
                    "step": job.get('step')
                }
            }}
        )
        
        result = {
            'job_id': job_id,
            'worker_name': self.name,
            'status': 'error',
            'error': None,
            'outputs': None,
            'processing_time': 0.0,
            'homf_access_time': 0.0,
            'inference_time': 0.0
        }
        
        try:
            # Get ONNX session from HOMF pool
            session_tuple = self.homf_pool.get_session_ultra_fast(block_id)
            session, homf_access_time, method_info = session_tuple
            
            result['homf_access_time'] = homf_access_time
            
            if session is None:
                raise RuntimeError(f"Failed to get session for block {block_id}")
            
            # Prepare inputs
            input_data = job.get('input_data', {})
            requested_outputs = job.get('requested_outputs')
            
            # Run inference in executor to avoid blocking event loop
            inference_start = time.perf_counter()
            
            # Use run_in_executor for the blocking ONNX inference
            loop = asyncio.get_event_loop()
            outputs = await loop.run_in_executor(
                self.executor,
                session.run,
                requested_outputs,
                input_data
            )
            
            inference_time = time.perf_counter() - inference_start
            result['inference_time'] = inference_time
            
            # Package results
            result['status'] = 'success'
            result['outputs'] = outputs
            result['method_info'] = method_info
            
            # Update statistics
            self.stats['jobs_processed'] += 1
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['error_type'] = type(e).__name__
            
            self.stats['jobs_failed'] += 1
            
            logger.error(
                f"{self.name} failed to process job {job_id}: {e}",
                exc_info=True,
                extra={"custom_extra_fields": {
                    "event_type": "WORKER_JOB_ERROR",
                    "worker_name": self.name,
                    "data": {
                        "job_id": job_id,
                        "block_id": block_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                }}
            )
        
        finally:
            # Calculate total processing time
            processing_time = time.perf_counter() - start_time
            result['processing_time'] = processing_time
            
            # Update statistics
            self.stats['total_processing_time'] += processing_time
            total_jobs = self.stats['jobs_processed'] + self.stats['jobs_failed']
            if total_jobs > 0:
                self.stats['average_processing_time'] = (
                    self.stats['total_processing_time'] / total_jobs
                )
            
            # Send result back via reply queue
            if reply_queue:
                await reply_queue.put(result)
            
            logger.debug(
                f"{self.name} completed job {job_id} in {processing_time:.3f}s",
                extra={"custom_extra_fields": {
                    "event_type": "WORKER_JOB_COMPLETE",
                    "worker_name": self.name,
                    "data": {
                        "job_id": job_id,
                        "block_id": block_id,
                        "status": result['status'],
                        "processing_time": round(processing_time, 3),
                        "inference_time": round(result['inference_time'], 3),
                        "homf_access_time": round(result['homf_access_time'], 3)
                    }
                }}
            )
    
    async def shutdown(self):
        """Gracefully shutdown the worker"""
        logger.info(f"Shutting down {self.name}")
        self._running = False
        
        # Send shutdown signal to inbox
        await self.inbox.put(None)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Shutdown HOMF pool if it has a shutdown method
        if hasattr(self.homf_pool, 'shutdown'):
            self.homf_pool.shutdown()
        
        logger.info(
            f"{self.name} shutdown complete. Stats: {self.stats}",
            extra={"custom_extra_fields": {
                "event_type": "WORKER_SHUTDOWN_COMPLETE",
                "worker_name": self.name,
                "data": self.stats
            }}
        )


class CPUWorker(BaseWorker):
    """CPU-specific worker using CPUExecutionProvider"""
    
    def __init__(self, 
                 name: str = "CPUWorker",
                 homf_pool: WarmStatePool = None,  # دریافت از بیرون
                 max_executor_threads: int = 2):
        
        super().__init__(
            name=name,
            execution_providers=['CPUExecutionProvider'],
            homf_pool=homf_pool,  # پاس دادن به base class
            max_executor_threads=max_executor_threads
        )


class GPUWorker(BaseWorker):
    """GPU-specific worker using DmlExecutionProvider with CPU fallback"""
    
    def __init__(self, 
                 name: str = "GPUWorker",
                 homf_pool: WarmStatePool = None,  # دریافت از بیرون
                 max_executor_threads: int = 1):  # Usually 1 for GPU
        
        # Check available providers
        available_providers = ort.get_available_providers()
        
        # Determine GPU provider based on availability
        gpu_providers = []
        if 'DmlExecutionProvider' in available_providers:
            gpu_providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
        elif 'CUDAExecutionProvider' in available_providers:
            gpu_providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        else:
            logger.warning(
                f"No GPU providers available. Available: {available_providers}. "
                f"Falling back to CPU for {name}"
            )
            gpu_providers = ['CPUExecutionProvider']
        
        super().__init__(
            name=name,
            execution_providers=gpu_providers,
            homf_pool=homf_pool,  # پاس دادن به base class
            max_executor_threads=max_executor_threads
        )