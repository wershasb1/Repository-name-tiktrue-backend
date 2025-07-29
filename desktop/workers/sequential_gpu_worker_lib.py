# Enhanced SequentialGPUWorker Implementation
# بهینه‌سازی شده برای مدیریت خطا و فال‌بک قوی‌تر

import asyncio
import time
import logging
import numpy as np
from pathlib import Path
import onnxruntime as ort
from typing import Dict, Any, Optional, List
import gc
from enum import Enum

class ExecutionProvider(Enum):
    """نوع execution provider"""
    DML = "DmlExecutionProvider"
    CUDA = "CUDAExecutionProvider"
    CPU = "CPUExecutionProvider"

class SessionLoadResult:
    """نتیجه بارگذاری session"""
    def __init__(self, session=None, provider=None, error=None, load_time=0.0):
        self.session = session
        self.provider = provider
        self.error = error
        self.load_time = load_time
        self.success = session is not None

class SequentialGPUWorker:
    """
    Enhanced GPU Worker با pattern Load/Unload و مدیریت خطای قوی
    """
    
    def __init__(self, name: str, project_root_path: Path, 
                 network_config_global: Dict, model_metadata_global: Dict,
                 max_retry_attempts: int = 3,
                 session_timeout: float = 30.0,
                 memory_cleanup_interval: int = 5):
        
        self.name = name
        self.project_root_path = project_root_path
        self.network_config = network_config_global
        self.metadata = model_metadata_global
        self.inbox = asyncio.Queue()
        
        # Configuration
        self.max_retry_attempts = max_retry_attempts
        self.session_timeout = session_timeout
        self.memory_cleanup_interval = memory_cleanup_interval
        
        # State management
        self.current_session = None
        self.current_block_id = None
        self.current_provider = None
        self.blocks_processed = 0
        self.session_load_attempts = {}
        self.provider_failures = {provider.value: 0 for provider in ExecutionProvider}
        
        # Statistics
        self.stats = {
            "total_jobs": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "fallback_to_cpu": 0,
            "session_loads": 0,
            "session_load_failures": 0,
            "memory_cleanups": 0,
            "execution_times": [],
            "load_times": []
        }
        
        # Available providers
        self.available_providers = ort.get_available_providers()
        self.preferred_gpu_provider = self._determine_gpu_provider()
        
        logging.info(
            f"✅ {name} initialized with Sequential GPU pattern",
            extra={"custom_extra_fields": {
                "event_type": "SEQUENTIAL_GPU_WORKER_INIT",
                "worker_name": name,
                "data": {
                    "available_providers": self.available_providers,
                    "preferred_gpu_provider": self.preferred_gpu_provider.value if self.preferred_gpu_provider else None,
                    "max_retry_attempts": max_retry_attempts,
                    "session_timeout": session_timeout
                }
            }}
        )
    
    def _determine_gpu_provider(self) -> Optional[ExecutionProvider]:
        """تعیین بهترین GPU provider موجود"""
        if ExecutionProvider.CUDA.value in self.available_providers:
            return ExecutionProvider.CUDA
        elif ExecutionProvider.DML.value in self.available_providers:
            return ExecutionProvider.DML
        else:
            logging.warning(
                f"No GPU providers available for {self.name}. Available: {self.available_providers}",
                extra={"custom_extra_fields": {
                    "event_type": "NO_GPU_PROVIDERS_AVAILABLE",
                    "worker_name": self.name,
                    "data": {"available_providers": self.available_providers}
                }}
            )
            return None
    
    def _cleanup_current_session(self):
        """پاکسازی کامل session جاری"""
        if self.current_session:
            try:
                del self.current_session
                self.current_session = None
                self.current_block_id = None
                self.current_provider = None
                
                # Force garbage collection
                gc.collect()
                
                logging.debug(
                    f"🧹 Session cleaned up for {self.name}",
                    extra={"custom_extra_fields": {
                        "event_type": "SESSION_CLEANUP",
                        "worker_name": self.name,
                        "data": {"blocks_processed": self.blocks_processed}
                    }}
                )
                
            except Exception as e:
                logging.warning(
                    f"Error during session cleanup: {e}",
                    extra={"custom_extra_fields": {
                        "event_type": "SESSION_CLEANUP_ERROR",
                        "worker_name": self.name,
                        "data": {"error": str(e)}
                    }}
                )
    
    def _load_session_with_provider(self, model_path: Path, provider: ExecutionProvider) -> SessionLoadResult:
        """بارگذاری session با provider مشخص"""
        start_time = time.time()
        
        try:
            logging.debug(
                f"Attempting to load session with {provider.value}",
                extra={"custom_extra_fields": {
                    "event_type": "SESSION_LOAD_ATTEMPT",
                    "worker_name": self.name,
                    "data": {
                        "model_path": str(model_path),
                        "provider": provider.value
                    }
                }}
            )
            
            # Create session options
            sess_options = ort.SessionOptions()
            
            # تنظیمات بهینه برای provider
            if provider == ExecutionProvider.CPU:
                # ===== تنظیمات ویژه CPU برای کاهش حافظه =====
                sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
                sess_options.enable_cpu_mem_arena = False
                sess_options.enable_mem_pattern = False
                sess_options.enable_mem_reuse = True
                sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                sess_options.intra_op_num_threads = 1
                sess_options.inter_op_num_threads = 1
                # ============================================
            else:
                # تنظیمات GPU
                sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
            
            # Create session with specific provider
            session = ort.InferenceSession(
                str(model_path),
                sess_options,
                providers=[provider.value]
            )
            
            load_time = time.time() - start_time
            
            logging.debug(
                f"✅ Session loaded successfully with {provider.value} in {load_time:.3f}s",
                extra={"custom_extra_fields": {
                    "event_type": "SESSION_LOAD_SUCCESS",
                    "worker_name": self.name,
                    "data": {
                        "provider": provider.value,
                        "load_time": load_time,
                        "model_path": str(model_path)
                    }
                }}
            )
            
            return SessionLoadResult(
                session=session,
                provider=provider,
                load_time=load_time
            )
            
        except Exception as e:
            load_time = time.time() - start_time
            error_msg = f"Failed to load with {provider.value}: {str(e)}"
            
            logging.warning(
                error_msg,
                extra={"custom_extra_fields": {
                    "event_type": "SESSION_LOAD_FAILED",
                    "worker_name": self.name,
                    "data": {
                        "provider": provider.value,
                        "error": str(e),
                        "load_time": load_time,
                        "model_path": str(model_path)
                    }
                }}
            )
            
            # Track provider failure
            self.provider_failures[provider.value] += 1
            
            return SessionLoadResult(
                error=error_msg,
                load_time=load_time
            )
            
            
    def _load_session_with_fallback(self, model_path: Path, block_id: str) -> SessionLoadResult:
        """بارگذاری session با fallback cascade"""
        
        # Define provider priority order
        provider_priority = []
        
        # Add preferred GPU provider first
        if self.preferred_gpu_provider:
            provider_priority.append(self.preferred_gpu_provider)
        
        # Add other GPU providers
        for provider in [ExecutionProvider.CUDA, ExecutionProvider.DML]:
            if provider != self.preferred_gpu_provider and provider.value in self.available_providers:
                provider_priority.append(provider)
        
        # Add CPU as final fallback
        if ExecutionProvider.CPU.value in self.available_providers:
            provider_priority.append(ExecutionProvider.CPU)
        
        logging.info(
            f"Loading session for {block_id} with provider cascade: {[p.value for p in provider_priority]}",
            extra={"custom_extra_fields": {
                "event_type": "SESSION_LOAD_CASCADE_START",
                "worker_name": self.name,
                "data": {
                    "block_id": block_id,
                    "provider_cascade": [p.value for p in provider_priority],
                    "model_path": str(model_path)
                }
            }}
        )
        
        # Try each provider in order
        for provider in provider_priority:
            # Skip provider if it has too many recent failures
            if self.provider_failures[provider.value] >= self.max_retry_attempts:
                logging.debug(
                    f"Skipping {provider.value} due to too many failures ({self.provider_failures[provider.value]})",
                    extra={"custom_extra_fields": {
                        "event_type": "PROVIDER_SKIPPED_TOO_MANY_FAILURES",
                        "worker_name": self.name,
                        "data": {
                            "provider": provider.value,
                            "failure_count": self.provider_failures[provider.value]
                        }
                    }}
                )
                continue
            
            result = self._load_session_with_provider(model_path, provider)
            
            if result.success:
                # Reset failure count on success
                self.provider_failures[provider.value] = 0
                return result
            
            # Brief pause before trying next provider
            time.sleep(0.1)
        
        # All providers failed
        return SessionLoadResult(
            error=f"All providers failed for {block_id}. Provider failures: {self.provider_failures}"
        )
    
    async def process_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """پردازش job با مدیریت خطای پیشرفته"""
        
        block_id = job_data.get('block_id')
        input_data = job_data.get('input_data', {})
        session_id = job_data.get('session_id', 'unknown')
        step = job_data.get('step', 0)
        
        job_start_time = time.time()
        self.stats["total_jobs"] += 1
        self.blocks_processed += 1
        
        try:
            logging.debug(
                f"🔥 Processing job for {block_id} (#{self.blocks_processed})",
                extra={"custom_extra_fields": {
                    "event_type": "JOB_PROCESSING_START",
                    "worker_name": self.name,
                    "session_id": session_id,
                    "step": step,
                    "data": {
                        "block_id": block_id,
                        "job_number": self.blocks_processed,
                        "input_keys": list(input_data.keys())
                    }
                }}
            )
            
            # Load session if needed
            if self.current_block_id != block_id:
                # Cleanup previous session
                self._cleanup_current_session()
                
                # Get model path
                model_path = self._get_model_path(block_id)
                
                # Load new session with fallback
                load_result = self._load_session_with_fallback(model_path, block_id)
                
                if not load_result.success:
                    self.stats["failed_jobs"] += 1
                    self.stats["session_load_failures"] += 1
                    
                    return {
                        'status': 'error',
                        'error': f"Failed to load session for {block_id}: {load_result.error}",
                        'block_id': block_id,
                        'worker_info': {
                            'worker_type': 'SequentialGPU',
                            'error_type': 'session_load_failure',
                            'blocks_processed': self.blocks_processed,
                            'provider_failures': self.provider_failures
                        }
                    }
                
                # Update state
                self.current_session = load_result.session
                self.current_block_id = block_id
                self.current_provider = load_result.provider
                self.stats["session_loads"] += 1
                self.stats["load_times"].append(load_result.load_time)
                
                logging.info(
                    f"📥 Loaded fresh session for {block_id} on {load_result.provider.value}",
                    extra={"custom_extra_fields": {
                        "event_type": "SESSION_LOADED",
                        "worker_name": self.name,
                        "session_id": session_id,
                        "step": step,
                        "data": {
                            "block_id": block_id,
                            "provider": load_result.provider.value,
                            "load_time": load_result.load_time,
                            "is_cpu_fallback": load_result.provider == ExecutionProvider.CPU
                        }
                    }}
                )
                
                # Track CPU fallback
                if load_result.provider == ExecutionProvider.CPU:
                    self.stats["fallback_to_cpu"] += 1
            
            # Run inference
            inference_start_time = time.time()
            outputs = self.current_session.run(None, input_data)
            inference_time = time.time() - inference_start_time
            
            # Update statistics
            self.stats["successful_jobs"] += 1
            self.stats["execution_times"].append(inference_time)
            
            # Memory cleanup if needed
            if self.blocks_processed % self.memory_cleanup_interval == 0:
                gc.collect()
                self.stats["memory_cleanups"] += 1
                
                logging.debug(
                    f"🧹 Memory cleanup after {self.blocks_processed} blocks",
                    extra={"custom_extra_fields": {
                        "event_type": "MEMORY_CLEANUP",
                        "worker_name": self.name,
                        "data": {"blocks_processed": self.blocks_processed}
                    }}
                )
            
            job_total_time = time.time() - job_start_time
            
            logging.debug(
                f"⚡ {block_id} completed in {inference_time:.3f}s on {self.current_provider.value}",
                extra={"custom_extra_fields": {
                    "event_type": "JOB_COMPLETED",
                    "worker_name": self.name,
                    "session_id": session_id,
                    "step": step,
                    "data": {
                        "block_id": block_id,
                        "provider": self.current_provider.value,
                        "inference_time": inference_time,
                        "job_total_time": job_total_time,
                        "is_cpu_fallback": self.current_provider == ExecutionProvider.CPU
                    }
                }}
            )
            
            return {
                'status': 'success',
                'outputs': outputs,
                'inference_time': inference_time,
                'job_total_time': job_total_time,
                'worker_info': {
                    'worker_type': 'SequentialGPU',
                    'execution_provider': self.current_provider.value,
                    'blocks_processed': self.blocks_processed,
                    'is_cpu_fallback': self.current_provider == ExecutionProvider.CPU,
                    'provider_failures': self.provider_failures
                }
            }
            
        except Exception as e:
            job_total_time = time.time() - job_start_time
            self.stats["failed_jobs"] += 1
            
            logging.error(
                f"❌ Job processing failed for {block_id}: {str(e)}",
                exc_info=True,
                extra={"custom_extra_fields": {
                    "event_type": "JOB_PROCESSING_FAILED",
                    "worker_name": self.name,
                    "session_id": session_id,
                    "step": step,
                    "data": {
                        "block_id": block_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "job_total_time": job_total_time,
                        "current_provider": self.current_provider.value if self.current_provider else None
                    }
                }}
            )
            
            # Cleanup on error
            self._cleanup_current_session()
            
            return {
                'status': 'error',
                'error': str(e),
                'error_type': type(e).__name__,
                'job_total_time': job_total_time,
                'worker_info': {
                    'worker_type': 'SequentialGPU',
                    'error_at_block': block_id,
                    'blocks_processed': self.blocks_processed,
                    'current_provider': self.current_provider.value if self.current_provider else None,
                    'provider_failures': self.provider_failures
                }
            }
    
    def _get_model_path(self, block_id: str) -> Path:
        """دریافت مسیر مدل برای بلاک"""
        try:
            # Get blocks directory from config
            onnx_dir = self.network_config.get("paths", {}).get("onnx_blocks_dir", "models/original_onnx")
            base_path = self.project_root_path / onnx_dir
            
            # الگوهای مختلف نام‌گذاری فایل‌ها با اولویت
            possible_patterns = [
                f"{block_id}_skeleton.optimized.onnx",  # فایل بهینه‌سازی شده (اولویت اول)
                f"{block_id}_skeleton_with_zeros.onnx",  # فایل با zeros
                f"{block_id}.onnx",  # نام ساده
                f"{block_id}_optimized.onnx",  # نام بهینه‌سازی شده
            ]
            
            # جستجو برای فایل‌ها
            for pattern in possible_patterns:
                candidate_path = base_path / pattern
                if candidate_path.exists() and candidate_path.is_file():
                    logging.debug(f"Found model for {block_id} using pattern '{pattern}': {candidate_path}")
                    return candidate_path
            
            # اگر هیچ فایل پیدا نشد، لیست فایل‌های موجود را نمایش بده
            available_files = list(base_path.glob("*.onnx")) if base_path.exists() else []
            available_names = [f.name for f in available_files]
            
            raise FileNotFoundError(
                f"No model found for {block_id}. "
                f"Searched patterns: {possible_patterns}. "
                f"Available files: {available_names[:10]}{'...' if len(available_names) > 10 else ''}"
            )
            
        except Exception as e:
            logging.error(
                f"Failed to get model path for {block_id}: {e}",
                extra={"custom_extra_fields": {
                    "event_type": "MODEL_PATH_ERROR",
                    "worker_name": self.name,
                    "data": {
                        "block_id": block_id,
                        "error": str(e)
                    }
                }}
            )
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """دریافت وضعیت فعلی worker"""
        return {
            "worker_name": self.name,
            "worker_type": "SequentialGPU",
            "current_block": self.current_block_id,
            "current_provider": self.current_provider.value if self.current_provider else None,
            "blocks_processed": self.blocks_processed,
            "available_providers": self.available_providers,
            "preferred_gpu_provider": self.preferred_gpu_provider.value if self.preferred_gpu_provider else None,
            "provider_failures": self.provider_failures,
            "stats": self.stats
        }
    
    async def run(self):
        """Worker main loop با مدیریت خطای قوی"""
        logging.info(
            f"🚀 {self.name} main loop started",
            extra={"custom_extra_fields": {
                "event_type": "WORKER_LOOP_START",
                "worker_name": self.name,
                "data": self.get_status()
            }}
        )
        
        while True:
            try:
                # Get job from inbox
                job = await self.inbox.get()
                
                # Process job
                result = await self.process_job(job)
                
                # Send result back
                reply_queue = job.get('reply_queue')
                if reply_queue:
                    await reply_queue.put(result)
                
                # Mark job as done
                self.inbox.task_done()
                    
            except Exception as e:
                logging.error(
                    f"❌ {self.name} main loop error: {str(e)}",
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
                
                # Try to send error back if possible
                try:
                    reply_queue = job.get('reply_queue') if 'job' in locals() else None
                    if reply_queue:
                        await reply_queue.put({
                            'status': 'error',
                            'error': f"Worker loop error: {str(e)}",
                            'error_type': type(e).__name__,
                            'worker_info': {
                                'worker_type': 'SequentialGPU',
                                'error_in': 'main_loop'
                            }
                        })
                except Exception as send_error:
                    logging.error(
                        f"Failed to send error response: {send_error}",
                        extra={"custom_extra_fields": {
                            "event_type": "WORKER_SEND_ERROR_FAILED",
                            "worker_name": self.name,
                            "data": {"send_error": str(send_error)}
                        }}
                    )
                
                # Brief pause before continuing
                await asyncio.sleep(0.1)
    
    def shutdown(self):
        """تعطیل worker"""
        logging.info(
            f"🔴 Shutting down {self.name}",
            extra={"custom_extra_fields": {
                "event_type": "WORKER_SHUTDOWN",
                "worker_name": self.name,
                "data": self.get_status()
            }}
        )
        
        # Cleanup current session
        self._cleanup_current_session()
        
        # Reset provider failure counts
        self.provider_failures = {provider.value: 0 for provider in ExecutionProvider}
        
        logging.info(
            f"✅ {self.name} shutdown complete",
            extra={"custom_extra_fields": {
                "event_type": "WORKER_SHUTDOWN_COMPLETE",
                "worker_name": self.name,
                "data": self.stats
            }}
        )