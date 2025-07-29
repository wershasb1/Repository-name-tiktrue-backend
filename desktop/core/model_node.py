'''
# D:\Tiktrue\tiktrue_mvp\networked_distributed_inference\model_node.py

python model_node.py --node-id physical_node_1 --network-config network_config_llama_single_node.json --log-level INFO --max-warm-homf 5


'''


import websockets
import asyncio
import json
import numpy as np
import onnxruntime as ort # type: ignore
import logging
import sys
import os
import argparse
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import signal
from collections import OrderedDict
from datetime import datetime
from workers.worker_lib import CPUWorker, GPUWorker
from workers.scheduler_lib import StaticSplitScheduler
from workers.sequential_gpu_worker_lib import SequentialGPUWorker
from enum import Enum
from workers.dynamic_profiler import DynamicProfiler
import gc
import threading
import ctypes
import hashlib
import secrets

# --- Configuration Management ---
from core.config_manager import get_config_manager, initialize_config

# --- وارد کردن کتابخانه‌های سفارشی ---
from custom_logging import MainJsonFormatter, NODE_ID_FOR_LOGGING_HOLDER
from utils.serialization_utils import tensor_to_json_serializable, json_serializable_to_tensor
from workers.paged_kv_cache_lib import PagedKVCacheManager, SessionPagedKVCache
from workers.homf_lib import WarmStatePool, initialize_homf_globals

# --- Secure Model Block Management ---
from models.model_encryption import ModelEncryption, EncryptedBlock
from security.license_validator import get_license_validator, ValidationStatus

# --- Secure Memory Management ---
class SecureMemoryManager:
    """
    Secure memory management for decrypted model data
    Implements secure memory allocation, locking, and cleanup
    """
    
    def __init__(self):
        self.allocated_blocks: Dict[str, Any] = {}
        self.memory_lock = threading.Lock()
        self.secure_pages: List[Any] = []
        
    def allocate_secure_memory(self, size: int, block_id: str) -> Optional[Any]:
        """Allocate secure memory for decrypted model block"""
        try:
            with self.memory_lock:
                # Allocate memory
                memory_block = np.zeros(size, dtype=np.uint8)
                
                # Try to lock memory pages (platform dependent)
                try:
                    # Use ctypes to call mlock if available on the platform
                    if hasattr(ctypes, 'CDLL') and os.name == 'posix':
                        try:
                            libc = ctypes.CDLL("libc.so.6")
                            result = libc.mlock(memory_block.ctypes.data, size)
                            if result == 0:
                                self.secure_pages.append((memory_block.ctypes.data, size))
                        except Exception:
                            pass  # mlock not available or failed
                except Exception as e:
                    logging.debug(f"Memory locking not available: {e}")
                
                self.allocated_blocks[block_id] = {
                    'memory': memory_block,
                    'size': size,
                    'allocated_at': time.time(),
                    'locked': True
                }
                
                logging.debug(f"Allocated secure memory for block {block_id}: {size} bytes")
                return memory_block
                
        except Exception as e:
            logging.error(f"Failed to allocate secure memory: {e}")
            return None
    
    def clear_secure_memory(self, block_id: str) -> bool:
        """Clear and deallocate secure memory for a block"""
        try:
            with self.memory_lock:
                if block_id in self.allocated_blocks:
                    block_info = self.allocated_blocks[block_id]
                    memory_block = block_info['memory']
                    
                    # Zero out memory before deallocation
                    memory_block.fill(0)
                    
                    # Unlock memory pages if they were locked
                    try:
                        # Use ctypes to call munlock if available on the platform
                        if hasattr(ctypes, 'CDLL') and os.name == 'posix':
                            try:
                                libc = ctypes.CDLL("libc.so.6")
                                libc.munlock(memory_block.ctypes.data, block_info['size'])
                            except Exception:
                                pass  # munlock not available or failed
                    except Exception as e:
                        logging.debug(f"Memory unlocking not available: {e}")
                    
                    # Remove from tracking
                    del self.allocated_blocks[block_id]
                    
                    logging.debug(f"Cleared secure memory for block {block_id}")
                    return True
                    
        except Exception as e:
            logging.error(f"Failed to clear secure memory: {e}")
            
        return False
    
    def clear_all_secure_memory(self):
        """Clear all allocated secure memory"""
        with self.memory_lock:
            for block_id in list(self.allocated_blocks.keys()):
                self.clear_secure_memory(block_id)
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current secure memory usage statistics"""
        with self.memory_lock:
            total_size = sum(block['size'] for block in self.allocated_blocks.values())
            return {
                'total_blocks': len(self.allocated_blocks),
                'total_size_bytes': total_size,
                'blocks': {bid: {'size': info['size'], 'allocated_at': info['allocated_at']} 
                          for bid, info in self.allocated_blocks.items()}
            }


class SecureModelBlockManager:
    """
    Exclusive interface for secure model block decryption and loading
    Implements requirements 6.4.1 through 6.4.5
    """
    
    def __init__(self):
        self.model_encryption = ModelEncryption()
        self.license_validator = get_license_validator()
        self.memory_manager = SecureMemoryManager()
        self.access_lock = threading.Lock()
        self.authorized_sessions: Dict[str, Dict[str, Any]] = {}
        self.runtime_license_checks: Dict[str, float] = {}  # session_id -> last_check_time
        self.decryption_log: List[Dict[str, Any]] = []
        
        # Runtime license check interval (seconds)
        self.license_check_interval = 300  # 5 minutes
        
        logging.info("SecureModelBlockManager initialized - exclusive decryption interface active")
    
    def _log_security_event(self, event_type: str, session_id: str, block_id: str = None, 
                           success: bool = True, details: Dict[str, Any] = None):
        """Log security events for audit trail"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'session_id': session_id,
            'block_id': block_id,
            'success': success,
            'node_id': NODE_ID,
            'details': details or {}
        }
        
        self.decryption_log.append(event)
        
        # Keep only last 1000 events
        if len(self.decryption_log) > 1000:
            self.decryption_log = self.decryption_log[-1000:]
        
        # Log to system logger
        log_level = logging.INFO if success else logging.WARNING
        logging.log(log_level, f"Security event: {event_type} for session {session_id}", 
                   extra={"custom_extra_fields": {
                       "event_type": "SECURITY_EVENT",
                       "node_id": NODE_ID,
                       "data": event
                   }})
    
    def _perform_runtime_license_check(self, session_id: str, license_key: str) -> bool:
        """Perform runtime license validation check"""
        try:
            current_time = time.time()
            last_check = self.runtime_license_checks.get(session_id, 0)
            
            # Check if we need to validate (based on interval)
            if current_time - last_check < self.license_check_interval:
                return True  # Recently validated
            
            # Perform license validation
            validation_result = self.security.license_validator.validate_license(
                license_key, 
                self.security.license_validator.hardware_fp.generate_fingerprint()
            )
            
            is_valid = validation_result.status == ValidationStatus.VALID
            
            if is_valid:
                self.runtime_license_checks[session_id] = current_time
                self._log_security_event("RUNTIME_LICENSE_CHECK", session_id, 
                                       success=True, details={'validation_status': 'valid'})
            else:
                self._log_security_event("RUNTIME_LICENSE_CHECK", session_id, 
                                       success=False, details={
                                           'validation_status': validation_result.status.value,
                                           'message': validation_result.message
                                       })
            
            return is_valid
            
        except Exception as e:
            logging.error(f"Runtime license check failed: {e}")
            self._log_security_event("RUNTIME_LICENSE_CHECK", session_id, 
                                   success=False, details={'error': str(e)})
            return False
    
    def authorize_session(self, session_id: str, license_key: str) -> bool:
        """Authorize a session for model block access"""
        try:
            with self.access_lock:
                # Validate license
                validation_result = self.security.license_validator.validate_license(
                    license_key,
                    self.security.license_validator.hardware_fp.generate_fingerprint()
                )
                
                if validation_result.status != ValidationStatus.VALID:
                    self._log_security_event("SESSION_AUTHORIZATION", session_id, 
                                           success=False, details={
                                               'reason': 'license_validation_failed',
                                               'status': validation_result.status.value
                                           })
                    return False
                
                # Store authorized session
                self.authorized_sessions[session_id] = {
                    'license_key': license_key,
                    'authorized_at': time.time(),
                    'license_info': validation_result.license_info,
                    'last_activity': time.time()
                }
                
                self.runtime_license_checks[session_id] = time.time()
                
                self._log_security_event("SESSION_AUTHORIZATION", session_id, 
                                       success=True, details={'license_type': validation_result.license_info.plan_type if validation_result.license_info else 'unknown'})
                
                logging.info(f"Session {session_id} authorized for model block access")
                return True
                
        except Exception as e:
            logging.error(f"Session authorization failed: {e}")
            self._log_security_event("SESSION_AUTHORIZATION", session_id, 
                                   success=False, details={'error': str(e)})
            return False
    
    def revoke_session(self, session_id: str):
        """Revoke session authorization and clear associated memory"""
        try:
            with self.access_lock:
                if session_id in self.authorized_sessions:
                    # Clear any allocated memory for this session
                    self._clear_session_memory(session_id)
                    
                    # Remove authorization
                    del self.authorized_sessions[session_id]
                    
                    if session_id in self.runtime_license_checks:
                        del self.runtime_license_checks[session_id]
                    
                    self._log_security_event("SESSION_REVOCATION", session_id, success=True)
                    logging.info(f"Session {session_id} authorization revoked")
                    
        except Exception as e:
            logging.error(f"Session revocation failed: {e}")
            self._log_security_event("SESSION_REVOCATION", session_id, 
                                   success=False, details={'error': str(e)})
    
    def _clear_session_memory(self, session_id: str):
        """Clear all memory allocated for a session"""
        # Find and clear memory blocks associated with this session
        memory_usage = self.memory_manager.get_memory_usage()
        for block_id in list(memory_usage['blocks'].keys()):
            if session_id in block_id:  # Assuming block_id contains session_id
                self.memory_manager.clear_secure_memory(block_id)
    
    def decrypt_model_blocks(self, session_id: str, encrypted_blocks: List[EncryptedBlock]) -> Optional[List[bytes]]:
        """
        Exclusive interface for decrypting model blocks
        Requirement 6.4.1: Only model_node.py component has decryption capabilities
        """
        try:
            with self.access_lock:
                # Verify session authorization
                if session_id not in self.authorized_sessions:
                    self._log_security_event("UNAUTHORIZED_DECRYPTION_ATTEMPT", session_id, 
                                           success=False, details={'reason': 'session_not_authorized'})
                    raise PermissionError("Session not authorized for model block decryption")
                
                session_info = self.authorized_sessions[session_id]
                license_key = session_info['license_key']
                
                # Perform runtime license check (Requirement 6.4.3)
                if not self._perform_runtime_license_check(session_id, license_key):
                    self._log_security_event("DECRYPTION_LICENSE_CHECK_FAILED", session_id, 
                                           success=False, details={'reason': 'runtime_license_check_failed'})
                    # Requirement 6.4.4: Stop inference and clear memory on license expiry
                    self._handle_license_expiry(session_id)
                    raise PermissionError("Runtime license check failed - access denied")
                
                decrypted_blocks = []
                
                for encrypted_block in encrypted_blocks:
                    try:
                        # Log decryption attempt
                        self._log_security_event("BLOCK_DECRYPTION_ATTEMPT", session_id, 
                                               encrypted_block.block_id, success=True)
                        
                        # Decrypt block using model encryption
                        decrypted_data = self.models.model_encryption.decrypt_model_block(encrypted_block)
                        
                        # Allocate secure memory for decrypted data (Requirement 6.4.5)
                        secure_memory = self.memory_manager.allocate_secure_memory(
                            len(decrypted_data), 
                            f"{session_id}_{encrypted_block.block_id}"
                        )
                        
                        if secure_memory is not None:
                            # Copy decrypted data to secure memory
                            secure_memory[:len(decrypted_data)] = np.frombuffer(decrypted_data, dtype=np.uint8)
                            decrypted_blocks.append(decrypted_data)
                        else:
                            logging.error(f"Failed to allocate secure memory for block {encrypted_block.block_id}")
                            raise MemoryError("Failed to allocate secure memory for decrypted block")
                        
                        self._log_security_event("BLOCK_DECRYPTION_SUCCESS", session_id, 
                                               encrypted_block.block_id, success=True,
                                               details={'block_size': len(decrypted_data)})
                        
                    except Exception as e:
                        self._log_security_event("BLOCK_DECRYPTION_FAILED", session_id, 
                                               encrypted_block.block_id, success=False,
                                               details={'error': str(e)})
                        raise
                
                # Update session activity
                session_info['last_activity'] = time.time()
                
                logging.info(f"Successfully decrypted {len(decrypted_blocks)} blocks for session {session_id}")
                return decrypted_blocks
                
        except Exception as e:
            logging.error(f"Model block decryption failed: {e}")
            self._log_security_event("DECRYPTION_OPERATION_FAILED", session_id, 
                                   success=False, details={'error': str(e)})
            raise
    
    def _handle_license_expiry(self, session_id: str):
        """Handle license expiry by stopping inference and clearing memory"""
        try:
            logging.warning(f"Handling license expiry for session {session_id}")
            
            # Clear all decrypted data from memory
            self._clear_session_memory(session_id)
            
            # Revoke session authorization
            self.revoke_session(session_id)
            
            # Force garbage collection to ensure memory cleanup
            gc.collect()
            
            self._log_security_event("LICENSE_EXPIRY_HANDLED", session_id, success=True,
                                   details={'action': 'memory_cleared_session_revoked'})
            
        except Exception as e:
            logging.error(f"Failed to handle license expiry: {e}")
            self._log_security_event("LICENSE_EXPIRY_HANDLING_FAILED", session_id, 
                                   success=False, details={'error': str(e)})
    
    def deny_unauthorized_access(self, attempted_session_id: str, attempted_operation: str):
        """
        Deny access to unauthorized applications
        Requirement 6.4.2: Deny access when other applications attempt to access encrypted blocks
        """
        self._log_security_event("UNAUTHORIZED_ACCESS_DENIED", attempted_session_id, 
                                success=True, details={
                                    'attempted_operation': attempted_operation,
                                    'action': 'access_denied'
                                })
        
        logging.warning(f"Denied unauthorized access attempt: session={attempted_session_id}, operation={attempted_operation}")
        raise PermissionError(f"Unauthorized access denied for operation: {attempted_operation}")
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get current security status and statistics"""
        with self.access_lock:
            return {
                'authorized_sessions': len(self.authorized_sessions),
                'active_sessions': [sid for sid, info in self.authorized_sessions.items() 
                                  if time.time() - info['last_activity'] < 3600],  # Active in last hour
                'memory_usage': self.memory_manager.get_memory_usage(),
                'recent_security_events': self.decryption_log[-10:],  # Last 10 events
                'license_check_interval': self.license_check_interval,
                'total_security_events': len(self.decryption_log)
            }
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions and their associated memory"""
        current_time = time.time()
        expired_sessions = []
        
        with self.access_lock:
            for session_id, session_info in self.authorized_sessions.items():
                # Check if session has been inactive for more than 1 hour
                if current_time - session_info['last_activity'] > 3600:
                    expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            logging.info(f"Cleaning up expired session: {session_id}")
            self.revoke_session(session_id)


# Global secure model block manager instance
SECURE_MODEL_BLOCK_MANAGER: Optional[SecureModelBlockManager] = None

def initialize_secure_model_block_manager():
    """Initialize the global secure model block manager"""
    global SECURE_MODEL_BLOCK_MANAGER
    if SECURE_MODEL_BLOCK_MANAGER is None:
        SECURE_MODEL_BLOCK_MANAGER = SecureModelBlockManager()
        logging.info("Secure model block manager initialized")
    return SECURE_MODEL_BLOCK_MANAGER

def get_secure_model_block_manager() -> SecureModelBlockManager:
    """Get the global secure model block manager instance"""
    if SECURE_MODEL_BLOCK_MANAGER is None:
        return initialize_secure_model_block_manager()
    return SECURE_MODEL_BLOCK_MANAGER

# --- Enhanced Classes for Pipeline Management ---
class WorkerType(Enum):
    CPU = "CPU"
    GPU = "GPU"
    SEQUENTIAL_GPU = "SEQUENTIAL_GPU"

class BlockAssignmentManager:
    """مدیریت پویا تخصیص بلاک‌ها به workerها"""
    
    def __init__(self):
        self.current_assignments: Dict[str, WorkerType] = {}
        self.fallback_history: Dict[str, List[Dict[str, Any]]] = {}
        self.execution_stats: Dict[str, Dict[str, Any]] = {}
    
    def assign_block(self, block_id: str, worker_type: WorkerType, reason: str = "initial"):
        """تخصیص بلاک به worker با ثبت دلیل"""
        previous_assignment = self.current_assignments.get(block_id)
        self.current_assignments[block_id] = worker_type
        
        if block_id not in self.fallback_history:
            self.fallback_history[block_id] = []
        
        fallback_event = {
            "from": previous_assignment.value if previous_assignment else "none",
            "to": worker_type.value,
            "reason": reason,
            "timestamp": time.time()
        }
        self.fallback_history[block_id].append(fallback_event)
        
        return fallback_event
    
    def get_assignment(self, block_id: str) -> Optional[WorkerType]:
        """دریافت تخصیص فعلی بلاک"""
        return self.current_assignments.get(block_id)
    
    def record_execution_stats(self, block_id: str, worker_type: WorkerType, 
                             execution_time: float, status: str, error_details: Optional[str] = None):
        """ثبت آمار اجرای بلاک"""
        if block_id not in self.execution_stats:
            self.execution_stats[block_id] = {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "execution_times": [],
                "errors": []
            }
        
        stats = self.execution_stats[block_id]
        stats["total_executions"] += 1
        stats["execution_times"].append(execution_time)
        
        if status == "success":
            stats["successful_executions"] += 1
        else:
            stats["failed_executions"] += 1
            if error_details:
                stats["errors"].append({
                    "worker_type": worker_type.value,
                    "error": error_details,
                    "timestamp": time.time()
                })

# --- Global Variables ---
GLOBAL_PROFILER = None
ADAPTIVE_SCHEDULING_ENABLED = True
PROFILER_SAMPLING_INTERVAL = 0.5
ADAPTIVE_THRESHOLD_CPU = 0.3  # اگر CPU performance factor کمتر از این باشد
ADAPTIVE_THRESHOLD_GPU = 0.6  # اگر GPU performance factor کمتر از این باشد
HEALTH_MONITOR_TASK = None
MEMORY_INTENSIVE_BLOCKS = ["block_28", "block_29", "block_30", "block_31", "block_32", "block_33"]  # بلاک‌هایی که حافظه زیادی نیاز دارند
FORCE_CPU_BLOCKS = ["block_28", "block_29", "block_30", "block_31", "block_32", "block_33"] # بلاک‌هایی که باید حتماً روی CPU اجرا شوند

# متغیرهای مربوط به HOMF
GLOBAL_HOMF_POOL: Optional[WarmStatePool] = None
MAX_WARM_SESSIONS_HOMF_CONFIG: int = 1
CPU_WORKER: Optional[CPUWorker] = None
GPU_WORKER: Optional[SequentialGPUWorker] = None
EXECUTION_SCHEDULER: Optional[StaticSplitScheduler] = None
EXECUTION_PLAN: Dict[str, str] = {}

# Global Block Assignment Manager
BLOCK_ASSIGNMENT_MANAGER = BlockAssignmentManager()

# متغیرهای مربوط به PagedKVCache
KV_CACHE_STORAGE: OrderedDict[str, SessionPagedKVCache] = OrderedDict()
MAX_CACHED_SESSIONS_KV: int = 10
DEFAULT_PAGE_CAPACITY_TOKENS_KV: int = 16
INITIAL_PAGES_PER_MANAGER_KV: int = 16
KV_CACHE_DTYPE_NP: np.dtype = np.float16
GLOBAL_PAGE_MANAGER: Optional[PagedKVCacheManager] = None

# متغیرهای تنظیمات شبکه و مدل
NODE_ID: Optional[str] = None
NETWORK_CONFIG: Optional[Dict[str, Any]] = None
MODEL_CHAIN_ORDER: Optional[List[str]] = None
ASSIGNED_BLOCK_IDS_IN_ORDER: List[str] = []
BLOCK_IO_DETAILS_FULL: Dict[str, Any] = {}
EXPECTED_DTYPES: Dict[str, Any] = {}
NUM_KV_HEADS: Optional[int] = None
HEAD_DIM: Optional[int] = None

SHUTDOWN_EVENT: Optional[asyncio.Event] = None

# Names for attention mask components
ATTN_MASK_COMP_NAME_1 = "/model/attn_mask_reformat/attn_mask_subgraph/Gather/Cast/output_0"
ATTN_MASK_COMP_NAME_2 = "/model/attn_mask_reformat/attn_mask_subgraph/Sub/Cast/output_0"
HIDDEN_STATE_MLP_OUT_PATTERN = "/model/layers.{}/mlp/down_proj/MatMul/output_0"
HIDDEN_STATE_NORM_OUT_PATTERN = "/model/layers.{}/post_attention_layernorm/output_3"

async def adaptive_worker_selection(
    block_id: str, 
    default_worker: str,
    system_metrics: Dict[str, Any]
) -> str:
    """
    انتخاب هوشمند worker بر اساس وضعیت real-time سیستم
    """
    cpu_pf = system_metrics['cpu']['performance_factor']
    gpu_pf = system_metrics['gpu']['performance_factor']
    gpu_available = system_metrics['gpu']['available']
    memory_usage = system_metrics['memory']['usage_percent']
    
    # بلاک‌های خاص که باید حتماً روی CPU اجرا شوند
    if block_id in FORCE_CPU_BLOCKS:
        logging.info(f"Forcing {block_id} to CPU (memory intensive block requiring 2GB+)")
        return "CPU"
    
    # اگر حافظه تحت فشار شدید است
    if memory_usage > 85 and block_id in MEMORY_INTENSIVE_BLOCKS:
        logging.warning(f"High memory pressure ({memory_usage}%), forcing {block_id} to CPU")
        return "CPU"
    
    # برای Intel GPU، محدودیت‌های بیشتری اعمال کن
    if gpu_available and system_metrics['gpu'].get('type') == 'intel':
        # Intel GPU فقط 1GB VRAM دارد، پس بلاک‌های بزرگ را اجرا نکن
        if block_id in ["block_30", "block_31", "block_32", "block_33"]:
            logging.debug(f"Intel GPU detected, moving {block_id} to CPU (limited VRAM)")
            return "CPU"
    
    # قوانین تطبیقی عادی
    if default_worker == "GPU":
        if not gpu_available:
            return "CPU"
        
        if gpu_pf < ADAPTIVE_THRESHOLD_GPU:
            if cpu_pf > ADAPTIVE_THRESHOLD_CPU:
                logging.info(
                    f"Adaptive: Moving {block_id} from GPU to CPU "
                    f"(GPU_PF={gpu_pf:.2f} < {ADAPTIVE_THRESHOLD_GPU})"
                )
                return "CPU"
        
        if cpu_pf < 0.2:
            return "GPU"
    
    elif default_worker == "CPU":
        # برای Intel GPU، فقط در شرایط خیلی خاص به GPU منتقل کن
        if gpu_available and cpu_pf < ADAPTIVE_THRESHOLD_CPU and gpu_pf > 0.7:
            # اما نه برای بلاک‌های آخر
            if block_id not in ["block_30", "block_31", "block_32", "block_33"]:
                logging.info(
                    f"Adaptive: Moving {block_id} from CPU to GPU "
                    f"(CPU_PF={cpu_pf:.2f} < {ADAPTIVE_THRESHOLD_CPU}, GPU_PF={gpu_pf:.2f})"
                )
                return "GPU"
    
    return default_worker

async def emergency_memory_cleanup():
    """آزادسازی اضطراری حافظه"""
    logging.warning("Running emergency memory cleanup")
    
    # Garbage collection
    collected = gc.collect()
    logging.info(f"Garbage collected {collected} objects")
    
    # Clear any caches if possible
    if hasattr(GLOBAL_HOMF_POOL, 'clear_cache'):
        GLOBAL_HOMF_POOL.clear_cache()
    
    # Wait a moment
    await asyncio.sleep(0.5)
    
    # Report new memory status
    if GLOBAL_PROFILER:
        metrics = await GLOBAL_PROFILER.get_system_performance_factor()
        logging.info(
            f"Memory after cleanup: {metrics['memory']['usage_percent']:.1f}% used, "
            f"{metrics['memory']['available_gb']:.1f}GB available"
        )

async def system_health_monitor():
    """
    وظیفه مانیتورینگ مداوم سلامت سیستم
    """
    global GLOBAL_PROFILER, SHUTDOWN_EVENT, NODE_ID
    
    logging.info("System health monitor started")
    last_stats_time = time.time()
    
    if SHUTDOWN_EVENT is None:
        logging.error("Shutdown event not initialized for health monitor.")
        return

    while not SHUTDOWN_EVENT.is_set():
        try:
            if GLOBAL_PROFILER:
                metrics = await GLOBAL_PROFILER.get_system_performance_factor()
                
                # هشدار در صورت وجود مشکل
                if metrics['recommendation'] in ['cpu_pressure', 'memory_pressure', 'thermal_warning', 'system_overloaded']:
                    logging.warning(
                        f"System alert: {metrics['recommendation']}",
                        extra={"custom_extra_fields": {
                            "event_type": "SYSTEM_HEALTH_WARNING",
                            "node_id": NODE_ID,
                            "data": {
                                "recommendation": metrics['recommendation'],
                                "health_score": metrics['system_health_score'],
                                "cpu_usage": metrics['cpu']['usage_percent'],
                                "memory_usage": metrics['memory']['usage_percent'],
                                "gpu_available": metrics['gpu']['available'],
                                "gpu_type": metrics['gpu'].get('type', 'none')
                            }
                        }}
                    )
                
                # ذخیره آمار هر دقیقه
                current_time = time.time()
                if current_time - last_stats_time >= 60:
                    history = GLOBAL_PROFILER.get_historical_data(minutes=1.0)
                    logging.info(
                        "System health statistics (1 min)",
                        extra={"custom_extra_fields": {
                            "event_type": "SYSTEM_HEALTH_STATS",
                            "node_id": NODE_ID,
                            "data": history.get('statistics', {})
                        }}
                    )
                    last_stats_time = current_time
            
            await asyncio.sleep(10)  # چک هر 10 ثانیه
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Health monitor error: {e}", exc_info=True)
            await asyncio.sleep(30)
    logging.info("System health monitor stopped.")


# --- Enhanced Helper Functions ---
def ensure_tensor_shape_and_dtype(tensor: np.ndarray, expected_shape: tuple, 
                                 expected_dtype: np.dtype = np.float16, 
                                 name: str = "") -> np.ndarray:
    """اطمینان از shape و dtype صحیح برای DirectML"""
    # تبدیل dtype اگر نیاز است
    if tensor.dtype != expected_dtype:
        tensor = tensor.astype(expected_dtype)
    
    # بررسی و اصلاح shape
    if tensor.shape != expected_shape:
        # اگر scalar است، expand کن
        if tensor.shape == () or tensor.shape == []:
            tensor = np.full(expected_shape, tensor.item(), dtype=expected_dtype)
        else:
            logging.warning(f"Shape mismatch for {name}: got {tensor.shape}, expected {expected_shape}")
    
    # اطمینان از contiguous بودن برای GPU
    if not tensor.flags['C_CONTIGUOUS']:
        tensor = np.ascontiguousarray(tensor)
    
    return tensor

def map_block_outputs_to_next_inputs(current_block_id: int, outputs: Dict[str, np.ndarray], 
                                   global_cache: Dict[str, np.ndarray], 
                                   sequence_length: int) -> Dict[str, np.ndarray]:
    """نگاشت صحیح خروجی‌های یک بلاک به ورودی‌های بلاک بعدی"""
    next_block_id = current_block_id + 1
    mapped_inputs = {}
    
    if current_block_id == 1:
        # ذخیره global patterns با shape صحیح
        if "/model/ScatterND_output_0" in outputs:
            tensor = outputs["/model/ScatterND_output_0"]
            # اطمینان از shape صحیح: [batch_size, 1, total_seq_len, total_seq_len]
            if len(tensor.shape) == 2:  # اگر اشتباه [seq, seq] است
                tensor = tensor.reshape(1, 1, tensor.shape[0], tensor.shape[1])
            global_cache["/model/ScatterND_output_0"] = ensure_tensor_shape_and_dtype(
                tensor, (1, 1, sequence_length, sequence_length), np.float16, "ScatterND_output_0"
            )
        
        # Pattern ها با shape صحیح
        for pattern_name in ["/model/layers.0/self_attn/Unsqueeze_6_output_0", 
                           "/model/layers.0/self_attn/Unsqueeze_7_output_0"]:
            if pattern_name in outputs:
                tensor = outputs[pattern_name]
                # Shape صحیح: [batch_size, 1, total_seq_len, 128]
                MAX_SEQ_LEN = 512
                effective_seq_len = min(sequence_length, MAX_SEQ_LEN)
                expected_shape = (1, 1, effective_seq_len, effective_seq_len)
                global_cache[pattern_name] = ensure_tensor_shape_and_dtype(
                    tensor, expected_shape, np.float16, pattern_name
                )
    
    # آماده‌سازی inputs برای بلاک بعدی
    if 2 <= next_block_id <= 32:
        # Copy global patterns
        for key in ["/model/ScatterND_output_0", 
                   "/model/layers.0/self_attn/Unsqueeze_6_output_0",
                   "/model/layers.0/self_attn/Unsqueeze_7_output_0"]:
            if key in global_cache:
                mapped_inputs[key] = global_cache[key]
        
        # Hidden state از لایه قبلی
        layer_idx = current_block_id - 1
        hidden_state_key = f"/model/layers.{layer_idx}/Add_1_output_0"
        if hidden_state_key in outputs:
            # Shape: [batch_size, sequence_length, 4096]
            effective_seq_len = min(sequence_length, 512)  # محدود کردن
            mapped_inputs[hidden_state_key] = ensure_tensor_shape_and_dtype(
                outputs[hidden_state_key], (1, effective_seq_len, 4096), np.float16, hidden_state_key
            )
    
    elif next_block_id == 33:
        # فقط hidden state آخر
        hidden_state_key = "/model/layers.31/Add_1_output_0"
        effective_seq_len = min(sequence_length, 512)  # محدود کردن
        mapped_inputs[hidden_state_key] = ensure_tensor_shape_and_dtype(
            outputs[hidden_state_key], (1, effective_seq_len, 4096), np.float16, hidden_state_key
        )
            
    return mapped_inputs

def is_tensor_required_by_block(
    logical_block_id: str,
    tensor_name_to_check: str,
    block_io_meta_full: Dict[str, Any],
    session_id_for_log: Optional[str] = "N/A_is_tensor_req_ctx",
    step_for_log: Optional[int] = -1
) -> bool:
    current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "HelperFuncNodeUnset")
    if not block_io_meta_full or logical_block_id not in block_io_meta_full:
        logging.warning(
            f"is_tensor_required_by_block: Metadata for block '{logical_block_id}' not found. Assuming tensor '{tensor_name_to_check}' IS required.",
            extra={"custom_extra_fields": {"event_type": "IS_TENSOR_REQUIRED_METADATA_MISSING_WARN", "node_id": current_node_id, "session_id": session_id_for_log, "step": step_for_log, "data": {"checked_block_id": logical_block_id, "checked_tensor_name": tensor_name_to_check, "metadata_lookup_status": "Block or metadata not found", "fallback_assumption_made": True}}}
        )
        return True
    is_required = any(inp_spec.get('name') == tensor_name_to_check for inp_spec in block_io_meta_full[logical_block_id].get('inputs', []))
    return is_required

async def forward_request_to_next_node_async(
    next_node_uri: str,
    payload_for_next_node: dict,
) -> Optional[dict]:
    """Forward request to next node with enhanced error handling"""
    current_session_id = payload_for_next_node.get("session_id", NODE_ID_FOR_LOGGING_HOLDER.get("current_session_id", "N/A_Fwd_Ctx"))
    current_step = payload_for_next_node.get("step", NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1))
    current_source_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "FwdSrcNodeUnset")
    target_block_id_on_next_node = payload_for_next_node.get('target_block_id', 'UnknownTargetBlock')
    source_block_id_on_this_node = payload_for_next_node.get("source_block_id", "UnknownSourceBlockOnThisNode")
    base_fwd_log_data = { "fwd_source_node_id": current_source_node_id, "fwd_target_node_uri": next_node_uri, "fwd_target_block_id_on_next_node": target_block_id_on_next_node, "fwd_source_block_id_on_this_node": source_block_id_on_this_node, }
    
    logging.info( f"Forwarding request from {current_source_node_id} (Block: {source_block_id_on_this_node}) to {next_node_uri} for target block {target_block_id_on_next_node}.", extra={"custom_extra_fields": { "event_type": "FORWARD_REQUEST_INITIATED", "node_id": current_source_node_id, "session_id": current_session_id, "step": current_step, "data": {**base_fwd_log_data, "fwd_initial_payload_keys": list(payload_for_next_node.keys())} }} )
    
    fwd_cycle_total_start_time = time.perf_counter()
    connect_duration_sec: Optional[float] = None
    payload_serialization_duration_sec: Optional[float] = None
    send_duration_sec: Optional[float] = None
    receive_duration_sec: Optional[float] = None
    response_deserialization_duration_sec: Optional[float] = None
    payload_size_bytes_val: Optional[int] = None
    response_size_bytes_val: Optional[int] = None
    downstream_response_status: Optional[str] = "N/A"
    
    error_response_payload_template = { "status": "error", "session_id": current_session_id, "step": current_step, "message": "Error during forwarding operation.", "error_details_at_forwarder_node": current_source_node_id, "error_target_next_node_uri": next_node_uri, "error_target_block_id": target_block_id_on_next_node }
    
    try:
        connect_start_time = time.perf_counter()
        async with websockets.connect(next_node_uri, max_size=None, open_timeout=30, close_timeout=30, ping_interval=25, ping_timeout=30) as websocket_client: # type: ignore
            connect_duration_sec = time.perf_counter() - connect_start_time
            logging.debug(f"Forward: Connection to {next_node_uri} established in {connect_duration_sec:.4f}s.", extra={"custom_extra_fields": {"event_type": "FORWARD_CONNECTION_ESTABLISHED_SUCCESS", "node_id": current_source_node_id, "session_id": current_session_id, "step": current_step, "data": {**base_fwd_log_data, "connect_duration_sec": round(connect_duration_sec, 5)}}})
            
            payload_ser_start_time = time.perf_counter()
            json_payload_to_send_str = json.dumps(payload_for_next_node, default=str)
            payload_bytes_to_send = json_payload_to_send_str.encode('utf-8')
            payload_serialization_duration_sec = time.perf_counter() - payload_ser_start_time
            payload_size_bytes_val = len(payload_bytes_to_send)
            
            logging.debug(f"Forward: Payload prepared for {next_node_uri}. Size: {payload_size_bytes_val}B, Serialization time: {payload_serialization_duration_sec:.4f}s.", extra={"custom_extra_fields": {"event_type": "FORWARD_PAYLOAD_PREPARED", "node_id": current_source_node_id, "session_id": current_session_id, "step": current_step, "data": {**base_fwd_log_data, "payload_serialization_duration_sec": round(payload_serialization_duration_sec, 5), "payload_size_bytes": payload_size_bytes_val}}})
            
            send_start_time = time.perf_counter()
            await websocket_client.send(payload_bytes_to_send)
            send_duration_sec = time.perf_counter() - send_start_time
            
            logging.info(f"Forward: Payload of {payload_size_bytes_val}B sent to {next_node_uri} in {send_duration_sec:.4f}s. Awaiting response.", extra={"custom_extra_fields": {"event_type": "FORWARD_REQUEST_SENT_SUCCESSFULLY", "node_id": current_source_node_id, "session_id": current_session_id, "step": current_step, "data": {**base_fwd_log_data, "send_duration_sec": round(send_duration_sec, 5), "payload_size_bytes": payload_size_bytes_val}}})
            
            receive_start_time = time.perf_counter()
            response_raw_data_from_downstream = await asyncio.wait_for(websocket_client.recv(), timeout=1200.0)
            receive_duration_sec = time.perf_counter() - receive_start_time
            
            if isinstance(response_raw_data_from_downstream, str):
                response_size_bytes_val = len(response_raw_data_from_downstream.encode('utf-8'))
            elif isinstance(response_raw_data_from_downstream, bytes):
                response_size_bytes_val = len(response_raw_data_from_downstream)
            
            logging.info(f"Forward: Response received from {next_node_uri}. Size: {response_size_bytes_val or 'N/A'}B, Receive time: {receive_duration_sec:.4f}s.", extra={"custom_extra_fields": {"event_type": "FORWARD_RESPONSE_RECEIVED_SUCCESSFULLY", "node_id": current_source_node_id, "session_id": current_session_id, "step": current_step, "data": {**base_fwd_log_data, "receive_duration_sec": round(receive_duration_sec, 5), "response_size_bytes": response_size_bytes_val}}})
            
            response_deser_start_time = time.perf_counter()
            response_json_data_from_downstream = json.loads(response_raw_data_from_downstream) # type: ignore
            response_deserialization_duration_sec = time.perf_counter() - response_deser_start_time
            
            downstream_response_status = response_json_data_from_downstream.get("status", "StatusFieldMissingInResponse")
            
            logging.debug(f"Forward: Response from {next_node_uri} deserialized in {response_deserialization_duration_sec:.4f}s. Downstream status: '{downstream_response_status}'.", extra={"custom_extra_fields": {"event_type": "FORWARD_RESPONSE_DESERIALIZED", "node_id": current_source_node_id, "session_id": current_session_id, "step": current_step, "data": {**base_fwd_log_data, "response_deserialization_duration_sec": round(response_deserialization_duration_sec, 5), "response_status_from_downstream": downstream_response_status}}})
            
            if downstream_response_status == "success":
                fwd_cycle_total_duration_sec = time.perf_counter() - fwd_cycle_total_start_time
                forward_cycle_data = { **base_fwd_log_data, "connect_duration_sec": round(connect_duration_sec, 5) if connect_duration_sec is not None else None, "payload_serialization_duration_sec": round(payload_serialization_duration_sec, 5) if payload_serialization_duration_sec is not None else None, "send_duration_sec": round(send_duration_sec, 5) if send_duration_sec is not None else None, "receive_duration_sec": round(receive_duration_sec, 5) if receive_duration_sec is not None else None, "response_deserialization_duration_sec": round(response_deserialization_duration_sec, 5) if response_deserialization_duration_sec is not None else None, "total_forward_duration_sec": round(fwd_cycle_total_duration_sec, 5), "target_logical_block_id": target_block_id_on_next_node, "response_status_from_downstream": downstream_response_status, "payload_size_bytes_sent_val": payload_size_bytes_val, "response_size_bytes_received_val": response_size_bytes_val }
                logging.info(f"Forward: Cycle to {next_node_uri} (Target block: {target_block_id_on_next_node}) completed successfully in {fwd_cycle_total_duration_sec:.4f}s.", extra={"custom_extra_fields": {"event_type": "FORWARD_CYCLE_COMPLETED_SUCCESS", "node_id": current_source_node_id, "session_id": current_session_id, "step": current_step, "data": forward_cycle_data}})
            
            return response_json_data_from_downstream
            
    except Exception as e_fwd_general:
        exception_class_name_str = type(e_fwd_general).__name__
        error_message_str = str(e_fwd_general)
        fwd_cycle_duration_on_error_sec = time.perf_counter() - fwd_cycle_total_start_time
        block_at_fwd_error_stage = target_block_id_on_next_node
        
        error_forwarding_data = { **base_fwd_log_data, "block_at_error": block_at_fwd_error_stage, "error_message": error_message_str, "exception_class_name": exception_class_name_str, "total_forward_attempt_duration_sec": round(fwd_cycle_duration_on_error_sec, 5), "connect_duration_sec_attempt": round(connect_duration_sec, 5) if connect_duration_sec is not None else None, "payload_serialization_duration_sec_attempt": round(payload_serialization_duration_sec, 5) if payload_serialization_duration_sec is not None else None, "send_duration_sec_attempt": round(send_duration_sec, 5) if send_duration_sec is not None else None, "receive_duration_sec_attempt": round(receive_duration_sec, 5) if receive_duration_sec is not None else None, }
        
        ws_err_code = getattr(e_fwd_general, 'code', None)
        if ws_err_code:
            error_forwarding_data["websocket_error_code"] = ws_err_code
            
        logging.error(f"Forward: Exception during communication with {next_node_uri}. Type: {exception_class_name_str}, Msg: {error_message_str}", exc_info=True, extra={"custom_extra_fields": {"event_type": f"FORWARD_OPERATION_ERROR_{exception_class_name_str.upper()}", "node_id": current_source_node_id, "session_id": current_session_id, "step": current_step, "data": error_forwarding_data}})
        
        final_error_response = {**error_response_payload_template, "message": error_message_str, "exception_class_name": exception_class_name_str}
        return final_error_response

# --- Enhanced Pipeline Management Functions ---
async def send_job_to_worker(worker, job_data: Dict[str, Any], 
                           timeout: float = 1200.0) -> Dict[str, Any]:
    """ارسال job به worker با timeout و error handling"""
    reply_queue = asyncio.Queue()
    job_with_reply = {**job_data, "reply_queue": reply_queue}
    
    start_time = time.time()
    
    try:
        # Put job in worker's inbox
        await worker.inbox.put(job_with_reply)
        
        # Wait for response with timeout
        result = await asyncio.wait_for(reply_queue.get(), timeout=timeout)
        
        execution_time = time.time() - start_time
        
        # Record stats
        block_id = job_data.get('block_id')
        worker_type = WorkerType.CPU if "CPU" in worker.name else (
            WorkerType.SEQUENTIAL_GPU if "Sequential" in worker.name else WorkerType.GPU
        )
        
        status = result.get('status', 'unknown')
        error_details = result.get('error') if status == 'error' else None
        
        BLOCK_ASSIGNMENT_MANAGER.record_execution_stats(
            block_id, worker_type, execution_time, status, error_details
        )
        
        return result
        
    except asyncio.TimeoutError:
        execution_time = time.time() - start_time
        error_msg = f"Worker timeout after {timeout}s"
        
        # Record timeout as failure
        block_id = job_data.get('block_id')
        worker_type = WorkerType.CPU if "CPU" in worker.name else (
            WorkerType.SEQUENTIAL_GPU if "Sequential" in worker.name else WorkerType.GPU
        )
        
        BLOCK_ASSIGNMENT_MANAGER.record_execution_stats(
            block_id, worker_type, execution_time, "timeout", error_msg
        )
        
        return {
            "status": "timeout",
            "error": error_msg,
            "execution_time": execution_time
        }
    
    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = f"Worker communication error: {str(e)}"
        
        # Record communication error
        block_id = job_data.get('block_id')
        worker_type = WorkerType.CPU if "CPU" in worker.name else (
            WorkerType.SEQUENTIAL_GPU if "Sequential" in worker.name else WorkerType.GPU
        )
        
        BLOCK_ASSIGNMENT_MANAGER.record_execution_stats(
            block_id, worker_type, execution_time, "comm_error", error_msg
        )
        
        return {
            "status": "error",
            "error": error_msg,
            "execution_time": execution_time
        }

def prepare_block_inputs(block_id: str, current_outputs: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    """Prepare inputs for a specific block using enhanced tensor management"""
    try:
        # Extract block number for mapping
        block_num = int(block_id.replace("block_", ""))
        
        # Use existing mapping logic
        if block_num > 1:
            # Get sequence length from current outputs
            seq_len = 1  # Default
            for key, value in current_outputs.items():
                if hasattr(value, 'shape') and len(value.shape) >= 2:
                    seq_len = max(seq_len, value.shape[1])
                    break
            
            # Use existing mapping function
            mapped_inputs = map_block_outputs_to_next_inputs(
                block_num - 1, current_outputs, {}, seq_len
            )
            return mapped_inputs
        else:
            # For first block, return original inputs
            return current_outputs
            
    except Exception as e:
        logging.warning(
            f"Error in prepare_block_inputs for {block_id}: {e}. Using direct mapping.",
            extra={"custom_extra_fields": {
                "event_type": "BLOCK_INPUT_PREPARATION_ERROR",
                "node_id": NODE_ID,
                "session_id": session_id,
                "step": -1,
                "data": {
                    "block_id": block_id,
                    "error": str(e)
                }
            }}
        )
        return current_outputs

def get_pipeline_stats() -> Dict[str, Any]:
    """Get current pipeline statistics"""
    return {
        "assignment_stats": {
            "current_assignments": {k: v.value for k, v in BLOCK_ASSIGNMENT_MANAGER.current_assignments.items()},
            "fallback_events": len([event for events in BLOCK_ASSIGNMENT_MANAGER.fallback_history.values() for event in events]),
            "total_blocks_processed": len(BLOCK_ASSIGNMENT_MANAGER.execution_stats)
        },
        "execution_stats": BLOCK_ASSIGNMENT_MANAGER.execution_stats
    }

# --- Enhanced Pipeline Execution ---
async def execute_pipeline(session_id: str, step: int, initial_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """اجرای pipeline با قابلیت adaptive scheduling و مدیریت KV Cache"""
    
    global CPU_WORKER, GPU_WORKER, EXECUTION_PLAN, GLOBAL_PROFILER
    global NODE_ID_FOR_LOGGING_HOLDER, MODEL_CHAIN_ORDER, BLOCK_IO_DETAILS_FULL
    global ADAPTIVE_SCHEDULING_ENABLED, MEMORY_INTENSIVE_BLOCKS
    global KV_CACHE_STORAGE, GLOBAL_PAGE_MANAGER
    
    # تنظیم logging context
    NODE_ID_FOR_LOGGING_HOLDER["current_session_id"] = session_id
    NODE_ID_FOR_LOGGING_HOLDER["current_step"] = step
    
    # بررسی‌های اولیه
    if not MODEL_CHAIN_ORDER:
        return {
            "status": "error",
            "message": "Model chain order not initialized",
            "session_id": session_id,
            "step": step
        }
    
    if not EXECUTION_PLAN:
        return {
            "status": "error", 
            "message": "Execution plan not initialized",
            "session_id": session_id,
            "step": step
        }
    
    if not (CPU_WORKER or GPU_WORKER):
        return {
            "status": "error",
            "message": "No workers available",
            "session_id": session_id,
            "step": step
        }
    
    # 🔥 **مدیریت KV Cache - اضافه شده**
    if not GLOBAL_PAGE_MANAGER:
        return {
            "status": "error",
            "message": "KV Cache manager not initialized",
            "session_id": session_id,
            "step": step
        }
    
    # دریافت یا ایجاد KV cache برای session
    if session_id not in KV_CACHE_STORAGE:
        # ایجاد KV cache جدید برای همه layers (0-31)
        all_layer_indices = list(range(32))  # layers 0-31
        KV_CACHE_STORAGE[session_id] = SessionPagedKVCache(
            session_id=session_id,
            assigned_global_layer_indices=all_layer_indices,
            page_manager=GLOBAL_PAGE_MANAGER
        )
        logging.info(f"🔄 Created new KV cache for session {session_id}")
    
    session_kv_cache = KV_CACHE_STORAGE[session_id]
    
    # اگر step 0 باشد، cache رو reset کن (prompt جدید)
    if step == 0:
        session_kv_cache.reset_for_new_prompt()
        logging.info(f"🔄 Reset KV cache for session {session_id} (new prompt)")
    
    # Get system metrics if available
    system_metrics = None
    if GLOBAL_PROFILER and ADAPTIVE_SCHEDULING_ENABLED:
        try:
            system_metrics = await GLOBAL_PROFILER.get_system_performance_factor()
            logging.info(
                f"Pipeline starting with system health: {system_metrics['system_health_score']:.2f}",
                extra={"custom_extra_fields": {
                    "event_type": "PIPELINE_ADAPTIVE_START",
                    "node_id": NODE_ID,
                    "session_id": session_id,
                    "step": step,
                    "data": {
                        "cpu_performance": system_metrics['cpu']['performance_factor'],
                        "gpu_performance": system_metrics['gpu']['performance_factor'],
                        "memory_usage": system_metrics['memory']['usage_percent'],
                        "recommendation": system_metrics['recommendation']
                    }
                }}
            )
            
            if system_metrics['recommendation'] == 'system_overloaded':
                logging.warning("System overloaded, applying protective measures")
                await asyncio.sleep(0.5)
        except Exception as e:
            logging.error(f"Error getting system metrics: {e}")
    
    # Pipeline execution start
    pipeline_start_time = time.time()
    
    logging.info(
        f"🚀 Starting pipeline execution for session {session_id}",
        extra={"custom_extra_fields": {
            "event_type": "PIPELINE_EXECUTION_START",
            "node_id": NODE_ID,
            "session_id": session_id,
            "step": step,
            "data": {
                "total_blocks": len(MODEL_CHAIN_ORDER),
                "available_workers": {
                    "cpu": CPU_WORKER is not None,
                    "gpu": GPU_WORKER is not None
                },
                "kv_cache_initialized": session_id in KV_CACHE_STORAGE
            }
        }}
    )
    
    # Initialize propagating tensors
    propagating_tensors = {}
    for key, tensor_data in initial_inputs.items():
        try:
            propagating_tensors[key] = json_serializable_to_tensor(tensor_data)
        except Exception as e:
            logging.warning(f"Failed to deserialize input tensor {key}: {e}")
    
    # Pipeline statistics
    execution_times = {}
    failed_blocks = []
    successful_blocks = []
    fallback_events = []
    
    # Execute each block in the chain
    for block_idx, block_id in enumerate(MODEL_CHAIN_ORDER):
        block_start_time = time.time()
        
        try:
            logging.debug(f"📦 Starting {block_id} (block {block_idx + 1}/{len(MODEL_CHAIN_ORDER)})")
            
            # Memory management for intensive blocks
            if block_id in MEMORY_INTENSIVE_BLOCKS:
                logging.info(f"Running garbage collection before memory-intensive block {block_id}")
                gc.collect()
                await asyncio.sleep(0.1)
                
                if GLOBAL_PROFILER:
                    metrics = await GLOBAL_PROFILER.get_system_performance_factor()
                    logging.info(
                        f"Memory status before {block_id}: {metrics['memory']['usage_percent']:.1f}% used, "
                        f"{metrics['memory']['available_gb']:.1f}GB available"
                    )
            
            # Adaptive worker selection
            assigned_worker = EXECUTION_PLAN.get(block_id, "CPU")
            if ADAPTIVE_SCHEDULING_ENABLED and GLOBAL_PROFILER and system_metrics:
                try:
                    assigned_worker = await adaptive_worker_selection(
                        block_id, 
                        assigned_worker,
                        system_metrics
                    )
                except Exception as e:
                    logging.error(f"Adaptive selection failed: {e}, using default")
            
            # Determine target worker
            if assigned_worker == "GPU" and GPU_WORKER:
                target_worker = GPU_WORKER
                worker_name = "GPU"
            else:
                target_worker = CPU_WORKER
                worker_name = "CPU"
            
            if not target_worker:
                raise Exception(f"No worker available for {block_id}")
            
            # 🔥 **آماده‌سازی ورودی‌ها با KV Cache - اضافه شده**
            block_inputs = prepare_block_inputs_with_kv_cache(
                block_idx, block_id, propagating_tensors, session_kv_cache
            )
            
            # اگر KV cache تابع مشکل داشت، fallback به تابع قدیمی
            if not block_inputs:
                logging.warning(f"KV cache input preparation failed for {block_id}, using fallback")
                block_inputs = prepare_block_inputs(block_idx, block_id, propagating_tensors)
            
            if not block_inputs:
                raise Exception(f"No valid inputs prepared for {block_id}")
            
            # Create and execute job
            job_data = {
                'job_id': f"{session_id}_{step}_{block_id}",
                'block_id': block_id,
                'input_data': block_inputs,
                'requested_outputs': None,
                'session_id': session_id,
                'step': step
            }
            
            logging.debug(f"Sending {block_id} to {worker_name} worker")
            result = await send_job_to_worker(target_worker, job_data, timeout=120.0)
            
            # Handle failure with fallback
            if result and result.get('status') == 'error':
                logging.warning(f"Primary worker ({worker_name}) failed for {block_id}: {result.get('error')}")
                
                # Try fallback
                fallback_worker = GPU_WORKER if target_worker == CPU_WORKER else CPU_WORKER
                fallback_name = "GPU" if target_worker == CPU_WORKER else "CPU"
                
                if fallback_worker:
                    logging.info(f"🔄 Trying fallback {fallback_name} for {block_id}")
                    fallback_result = await send_job_to_worker(fallback_worker, job_data, timeout=120.0)
                    
                    if fallback_result and fallback_result.get('status') == 'success':
                        result = fallback_result
                        worker_name = fallback_name
                        fallback_events.append({
                            "block_id": block_id,
                            "from": assigned_worker,
                            "to": fallback_name,
                            "reason": "primary_worker_failure",
                            "success": True
                        })
            
            # Process result
            block_execution_time = time.time() - block_start_time
            execution_times[block_id] = round(block_execution_time, 3)
            
            if result and result.get('status') == 'success':
                successful_blocks.append(block_id)
                
                # 🔥 **پردازش نتیجه و ذخیره KV Cache - اضافه شده**
                outputs = result.get('outputs', {})
                
                # به‌روزرسانی propagating tensors
                update_propagating_tensors(block_idx, outputs, propagating_tensors)
                
                # ذخیره KV cache برای layers
                store_kv_cache_from_outputs(block_idx, block_id, outputs, session_kv_cache)
                
                logging.info(f"✅ Block {block_id} completed in {block_execution_time:.3f}s")
                
                # Memory cleanup every 5 blocks
                if (block_idx + 1) % 5 == 0:
                    gc.collect()
                    logging.debug(f"🧹 Memory cleanup after {block_id}")
                
            else:
                # Block failed
                error_msg = result.get('error', 'Unknown error') if result else 'No result'
                failed_blocks.append({
                    "block_id": block_id,
                    "error": error_msg,
                    "execution_time": block_execution_time,
                    "worker": worker_name
                })
                
                logging.error(f"💥 Pipeline failed at block {block_id}: {error_msg}")
                
                return {
                    "status": "error",
                    "message": f"Pipeline failed at block {block_id}: {error_msg}",
                    "session_id": session_id,
                    "step": step,
                    "failed_block": block_id,
                    "successful_blocks": successful_blocks,
                    "failed_blocks": failed_blocks,
                    "execution_times": execution_times,
                    "fallback_events": fallback_events
                }
                
        except Exception as e:
            # Handle unexpected errors
            block_execution_time = time.time() - block_start_time
            execution_times[block_id] = round(block_execution_time, 3)
            
            error_msg = str(e)
            
            # Special handling for memory errors
            if "bad allocation" in error_msg.lower() or "allocate memory" in error_msg.lower():
                logging.error(f"Memory allocation failed for {block_id}")
                
                # Try emergency cleanup
                if hasattr(globals(), 'emergency_memory_cleanup'):
                    await emergency_memory_cleanup()
                
                # For non-final blocks, try to continue
                if block_id != "block_33":
                    logging.info(f"Attempting to continue after memory error in {block_id}")
                    continue
            
            # Log and return error
            failed_blocks.append({
                "block_id": block_id,
                "error": error_msg,
                "execution_time": block_execution_time
            })
            
            logging.error(f"💥 Unexpected error in block {block_id}: {error_msg}", exc_info=True)
            
            return {
                "status": "error",
                "message": f"Unexpected error in pipeline at block {block_id}: {error_msg}",
                "session_id": session_id,
                "step": step,
                "failed_block": block_id,
                "error_type": type(e).__name__,
                "successful_blocks": successful_blocks,
                "failed_blocks": failed_blocks,
                "execution_times": execution_times,
                "fallback_events": fallback_events
            }
    
    # Pipeline completed successfully
    pipeline_time = time.time() - pipeline_start_time
    
    # 🔥 **آماده‌سازی خروجی نهایی با KV metadata - اضافه شده**
    final_outputs = {}
    if "logits" in propagating_tensors:
        final_outputs["logits"] = tensor_to_json_serializable(propagating_tensors["logits"])
    
    # اضافه کردن metadata KV cache
    kv_metadata = session_kv_cache.get_lightweight_kv_metadata()
    final_outputs["kv_cache_metadata"] = kv_metadata
    
    # 🔥 **مدیریت حافظه KV Cache - اضافه شده**
    # حذف session های قدیمی اگر تعداد زیاد شده
    if len(KV_CACHE_STORAGE) > MAX_CACHED_SESSIONS_KV:
        # حذف قدیمی‌ترین session
        oldest_session = next(iter(KV_CACHE_STORAGE))
        del KV_CACHE_STORAGE[oldest_session]
        logging.info(f"🗑️ Removed old KV cache for session {oldest_session}")
    
    logging.info(
        f"🎉 Pipeline completed successfully for session {session_id} in {pipeline_time:.3f}s",
        extra={"custom_extra_fields": {
            "event_type": "PIPELINE_COMPLETE",
            "node_id": NODE_ID,
            "session_id": session_id,
            "step": step,
            "data": {
                "total_time": round(pipeline_time, 3),
                "blocks_executed": len(successful_blocks),
                "has_logits": "logits" in final_outputs,
                "kv_cache_tokens": kv_metadata.get("kv_meta_total_tokens_on_node_for_session", 0),
                "kv_cache_pages": kv_metadata.get("kv_meta_total_active_pages_on_node_for_session", 0)
            }
        }}
    )
    
    return {
        "status": "success",
        "message": "Pipeline completed successfully",
        "session_id": session_id,
        "step": step,
        "outputs": final_outputs,
        "successful_blocks": successful_blocks,
        "failed_blocks": failed_blocks,
        "execution_times": execution_times,
        "total_pipeline_time": round(pipeline_time, 3),
        "fallback_events": fallback_events
    }


# 🔥 **توابع کمکی جدید برای KV Cache Management**

def prepare_block_inputs_with_kv_cache(block_idx: int, block_id: str, 
                                      propagating_tensors: Dict[str, Any],
                                      session_kv_cache: SessionPagedKVCache) -> Dict[str, Any]:
    """آماده‌سازی ورودی‌های بلاک با KV Cache"""
    
    block_inputs = {}
    
    # بررسی اولیه
    if not propagating_tensors:
        logging.error(f"No propagating tensors provided for {block_id}")
        return {}
    
    try:
        if block_idx == 0:  # Block 1 - اولین بلاک
            logging.debug(f"Preparing inputs for Block 1 (embedding + layer 0)")
            
            # ورودی‌های اصلی - بررسی None
            input_ids = propagating_tensors.get("input_ids")
            attention_mask = propagating_tensors.get("attention_mask")
            position_ids = propagating_tensors.get("position_ids")
            
            if input_ids is None:
                logging.error("input_ids is None for Block 1")
                return {}
            
            block_inputs["input_ids"] = input_ids
            block_inputs["attention_mask"] = attention_mask if attention_mask is not None else np.ones_like(input_ids, dtype=np.int64)
            block_inputs["position_ids"] = position_ids if position_ids is not None else np.arange(input_ids.shape[1], dtype=np.int64).reshape(1, -1)
            
            # KV cache برای layer 0 (معمولاً خالی در شروع)
            try:
                past_key_0, past_value_0 = session_kv_cache.retrieve_kv_for_layer(0)
                block_inputs["past_key_values.0.key"] = past_key_0
                block_inputs["past_key_values.0.value"] = past_value_0
                
                logging.debug(f"📥 Block 1 KV cache - Layer 0: key={past_key_0.shape}, value={past_value_0.shape}")
            except Exception as e:
                logging.warning(f"Failed to retrieve KV cache for layer 0: {e}")
                # Fallback: خالی
                block_inputs["past_key_values.0.key"] = np.zeros((1, 8, 0, 128), dtype=np.float16)
                block_inputs["past_key_values.0.value"] = np.zeros((1, 8, 0, 128), dtype=np.float16)
            
        elif 1 <= block_idx <= 31:  # Blocks 2-32 - لایه‌های میانی
            current_layer = block_idx  # block 2 -> layer 1, block 3 -> layer 2, etc.
            
            logging.debug(f"Preparing inputs for Block {block_idx + 1} (layer {current_layer})")
            
            # Global attention patterns از block 1 (مشترک برای همه)
            block_inputs["/model/ScatterND_output_0"] = propagating_tensors.get("/model/ScatterND_output_0")
            block_inputs["/model/layers.0/self_attn/Unsqueeze_6_output_0"] = propagating_tensors.get("/model/layers.0/self_attn/Unsqueeze_6_output_0")
            block_inputs["/model/layers.0/self_attn/Unsqueeze_7_output_0"] = propagating_tensors.get("/model/layers.0/self_attn/Unsqueeze_7_output_0")
            
            # Hidden state از layer قبلی
            previous_layer = current_layer - 1
            hidden_state_key = f"/model/layers.{previous_layer}/Add_1_output_0"
            block_inputs[hidden_state_key] = propagating_tensors.get(hidden_state_key)
            
            # KV cache برای layer فعلی
            try:
                past_key, past_value = session_kv_cache.retrieve_kv_for_layer(current_layer)
                block_inputs[f"past_key_values.{current_layer}.key"] = past_key
                block_inputs[f"past_key_values.{current_layer}.value"] = past_value
                
                logging.debug(f"📥 Block {block_idx + 1} KV cache - Layer {current_layer}: key={past_key.shape}, value={past_value.shape}")
            except Exception as e:
                logging.warning(f"Failed to retrieve KV cache for layer {current_layer}: {e}")
                # Fallback: خالی
                block_inputs[f"past_key_values.{current_layer}.key"] = np.zeros((1, 8, 0, 128), dtype=np.float16)
                block_inputs[f"past_key_values.{current_layer}.value"] = np.zeros((1, 8, 0, 128), dtype=np.float16)
            
        elif block_idx == 32:  # Block 33 - خروجی نهایی
            logging.debug(f"Preparing inputs for Block 33 (final output)")
            
            # فقط hidden state آخرین layer
            hidden_state_key = "/model/layers.31/Add_1_output_0"
            hidden_state = propagating_tensors.get(hidden_state_key)
            
            if hidden_state is None:
                logging.error(f"Missing hidden state for Block 33: {hidden_state_key}")
                return {}
            
            block_inputs[hidden_state_key] = hidden_state
        
        # بررسی نهایی
        if not block_inputs:
            logging.error(f"No inputs prepared for {block_id}")
            return {}
            
        # تأیید عدم وجود None values
        for key, value in block_inputs.items():
            if value is None:
                logging.error(f"Input '{key}' is None for {block_id}")
                return {}
        
        return block_inputs
        
    except Exception as e:
        logging.error(f"Error preparing inputs for {block_id}: {e}", exc_info=True)
        return {}


def store_kv_cache_from_outputs(block_idx: int, block_id: str, 
                               outputs: Any,
                               session_kv_cache: SessionPagedKVCache) -> None:
    """ذخیره KV Cache از خروجی‌های بلاک"""
    
    try:
        # بررسی نوع outputs
        if outputs is None:
            logging.warning(f"No outputs to store KV cache for {block_id}")
            return
            
        # اگر outputs یک dict است
        if isinstance(outputs, dict):
            _store_kv_from_dict_outputs(block_idx, block_id, outputs, session_kv_cache)
        
        # اگر outputs یک list یا tuple است
        elif isinstance(outputs, (list, tuple)):
            _store_kv_from_list_outputs(block_idx, block_id, outputs, session_kv_cache)
        
        else:
            logging.warning(f"Unsupported outputs type for KV cache storage: {type(outputs)}")
            
    except Exception as e:
        logging.error(f"Error storing KV cache for {block_id}: {e}", exc_info=True)


def _store_kv_from_dict_outputs(block_idx: int, block_id: str, 
                               outputs: Dict[str, Any],
                               session_kv_cache: SessionPagedKVCache) -> None:
    """ذخیره KV Cache از outputs نوع dict"""
    
    if block_idx == 0:  # Block 1 - layer 0
        layer_idx = 0
        present_key_name = f"present.{layer_idx}.key"
        present_value_name = f"present.{layer_idx}.value"
        
        # بررسی امن وجود کلیدها
        if present_key_name in outputs and present_value_name in outputs:
            present_key = outputs[present_key_name]
            present_value = outputs[present_value_name]
            
            # تبدیل به numpy اگر نیاز باشد
            if hasattr(present_key, 'numpy'):
                present_key = present_key.numpy()
            if hasattr(present_value, 'numpy'):
                present_value = present_value.numpy()
            
            session_kv_cache.store_kv_for_layer(layer_idx, present_key, present_value)
            logging.debug(f"💾 Stored KV cache for layer {layer_idx}: key={present_key.shape}, value={present_value.shape}")
    
    elif 1 <= block_idx <= 31:  # Blocks 2-32 - layers 1-31
        layer_idx = block_idx  # block 2 -> layer 1, etc.
        present_key_name = f"present.{layer_idx}.key"
        present_value_name = f"present.{layer_idx}.value"
        
        # بررسی امن وجود کلیدها
        if present_key_name in outputs and present_value_name in outputs:
            present_key = outputs[present_key_name]
            present_value = outputs[present_value_name]
            
            # تبدیل به numpy اگر نیاز باشد
            if hasattr(present_key, 'numpy'):
                present_key = present_key.numpy()
            if hasattr(present_value, 'numpy'):
                present_value = present_value.numpy()
            
            session_kv_cache.store_kv_for_layer(layer_idx, present_key, present_value)
            logging.debug(f"💾 Stored KV cache for layer {layer_idx}: key={present_key.shape}, value={present_value.shape}")


def _store_kv_from_list_outputs(block_idx: int, block_id: str, 
                               outputs: List[Any],
                               session_kv_cache: SessionPagedKVCache) -> None:
    """ذخیره KV Cache از outputs نوع list/tuple"""
    
    if block_idx == 0:  # Block 1 - layer 0
        layer_idx = 0
        # انتظار: [ScatterND, hidden_state, unsqueeze_6, unsqueeze_7, present_key, present_value]
        if len(outputs) >= 6:
            present_key = outputs[4]  # present.0.key
            present_value = outputs[5]  # present.0.value
            
            # تبدیل به numpy اگر نیاز باشد
            if hasattr(present_key, 'numpy'):
                present_key = present_key.numpy()
            if hasattr(present_value, 'numpy'):
                present_value = present_value.numpy()
            
            session_kv_cache.store_kv_for_layer(layer_idx, present_key, present_value)
            logging.debug(f"💾 Stored KV cache for layer {layer_idx}: key={present_key.shape}, value={present_value.shape}")
        else:
            logging.warning(f"Block 1 outputs length {len(outputs)} < 6, cannot extract KV cache")
    
    elif 1 <= block_idx <= 31:  # Blocks 2-32 - layers 1-31
        layer_idx = block_idx  # block 2 -> layer 1, etc.
        # انتظار: [hidden_state, present_key, present_value]
        if len(outputs) >= 3:
            present_key = outputs[1]  # present.layer.key
            present_value = outputs[2]  # present.layer.value
            
            # تبدیل به numpy اگر نیاز باشد
            if hasattr(present_key, 'numpy'):
                present_key = present_key.numpy()
            if hasattr(present_value, 'numpy'):
                present_value = present_value.numpy()
            
            session_kv_cache.store_kv_for_layer(layer_idx, present_key, present_value)
            logging.debug(f"💾 Stored KV cache for layer {layer_idx}: key={present_key.shape}, value={present_value.shape}")
        else:
            logging.warning(f"Block {block_idx + 1} outputs length {len(outputs)} < 3, cannot extract KV cache")


def update_propagating_tensors(block_idx: int, outputs: Dict[str, Any], 
                              propagating_tensors: Dict[str, Any]) -> None:
    """به‌روزرسانی tensors برای انتقال به بلاک بعدی"""
    
    if isinstance(outputs, dict):
        # اضافه کردن همه outputs به propagating tensors
        propagating_tensors.update(outputs)
        
        # لاگ کردن tensor های مهم
        if block_idx == 0:  # Block 1
            if "/model/ScatterND_output_0" in outputs:
                logging.debug(f"✅ Block 1 - ScatterND pattern: {outputs['/model/ScatterND_output_0'].shape}")
            if "/model/layers.0/Add_1_output_0" in outputs:
                logging.debug(f"✅ Block 1 - Hidden state layer 0: {outputs['/model/layers.0/Add_1_output_0'].shape}")
        
        elif 1 <= block_idx <= 31:  # Blocks 2-32
            layer_idx = block_idx
            hidden_state_key = f"/model/layers.{layer_idx}/Add_1_output_0"
            if hidden_state_key in outputs:
                logging.debug(f"✅ Block {block_idx + 1} - Hidden state layer {layer_idx}: {outputs[hidden_state_key].shape}")
        
        elif block_idx == 32:  # Block 33
            if "logits" in outputs:
                logging.debug(f"✅ Block 33 - Final logits: {outputs['logits'].shape}")
    
    elif isinstance(outputs, (list, tuple)) and len(outputs) > 0:
        # برای سازگاری با فرمت قدیمی
        if block_idx == 0:  # Block 1
            if len(outputs) >= 6:
                propagating_tensors.update({
                    "/model/ScatterND_output_0": outputs[0],
                    "/model/layers.0/Add_1_output_0": outputs[1],
                    "/model/layers.0/self_attn/Unsqueeze_6_output_0": outputs[2],
                    "/model/layers.0/self_attn/Unsqueeze_7_output_0": outputs[3],
                    "present.0.key": outputs[4],
                    "present.0.value": outputs[5]
                })
        
        elif 1 <= block_idx <= 31:  # Blocks 2-32
            layer_idx = block_idx
            if len(outputs) >= 3:
                propagating_tensors.update({
                    f"/model/layers.{layer_idx}/Add_1_output_0": outputs[0],
                    f"present.{layer_idx}.key": outputs[1],
                    f"present.{layer_idx}.value": outputs[2]
                })
        
        elif block_idx == 32:  # Block 33
            if len(outputs) >= 1:
                propagating_tensors["logits"] = outputs[0]

def prepare_block_inputs(block_idx: int, block_id: str, propagating_tensors: Dict[str, Any]) -> Dict[str, Any]:
    """آماده‌سازی ورودی‌های هر بلاک بر اساس شماره و نوع آن"""
    block_inputs = {}
    
    if block_idx == 0:  # Block 1
        # ورودی‌های اصلی
        block_inputs["input_ids"] = propagating_tensors.get("input_ids")
        block_inputs["attention_mask"] = propagating_tensors.get("attention_mask")
        block_inputs["position_ids"] = propagating_tensors.get("position_ids")
        
        # KV cache خالی برای layer 0
        block_inputs["past_key_values.0.key"] = np.zeros((1, 8, 0, 128), dtype=np.float16)
        block_inputs["past_key_values.0.value"] = np.zeros((1, 8, 0, 128), dtype=np.float16)
        
    elif 1 <= block_idx <= 31:  # Blocks 2-32
        current_layer = block_idx
        previous_layer = block_idx - 1
        
        # Global attention patterns از block 1
        block_inputs["/model/ScatterND_output_0"] = propagating_tensors.get("/model/ScatterND_output_0")
        block_inputs["/model/layers.0/self_attn/Unsqueeze_6_output_0"] = propagating_tensors.get("/model/layers.0/self_attn/Unsqueeze_6_output_0")
        block_inputs["/model/layers.0/self_attn/Unsqueeze_7_output_0"] = propagating_tensors.get("/model/layers.0/self_attn/Unsqueeze_7_output_0")
        
        # Hidden state از layer قبلی
        hidden_state_key = f"/model/layers.{previous_layer}/Add_1_output_0"
        block_inputs[hidden_state_key] = propagating_tensors.get(hidden_state_key)
        
        # KV cache خالی برای layer فعلی
        block_inputs[f"past_key_values.{current_layer}.key"] = np.zeros((1, 8, 0, 128), dtype=np.float16)
        block_inputs[f"past_key_values.{current_layer}.value"] = np.zeros((1, 8, 0, 128), dtype=np.float16)
        
    elif block_idx == 32:  # Block 33
        # فقط hidden state از layer 31
        block_inputs["/model/layers.31/Add_1_output_0"] = propagating_tensors.get("/model/layers.31/Add_1_output_0")
    
    # Remove None values
    return {k: v for k, v in block_inputs.items() if v is not None}


def update_propagating_tensors(block_idx: int, outputs: Any, propagating_tensors: Dict[str, Any]):
    """به‌روزرسانی propagating tensors با خروجی‌های هر بلاک"""
    if not outputs:
        return
    
    if isinstance(outputs, list):
        if block_idx == 0 and len(outputs) >= 6:  # Block 1
            propagating_tensors.update({
                "/model/ScatterND_output_0": outputs[0],
                "/model/layers.0/Add_1_output_0": outputs[1],
                "/model/layers.0/self_attn/Unsqueeze_6_output_0": outputs[2],
                "/model/layers.0/self_attn/Unsqueeze_7_output_0": outputs[3],
                "present.0.key": outputs[4],
                "present.0.value": outputs[5]
            })
            
        elif 1 <= block_idx <= 31 and len(outputs) >= 3:  # Blocks 2-32
            layer_num = block_idx
            propagating_tensors.update({
                f"/model/layers.{layer_num}/Add_1_output_0": outputs[0],
                f"present.{layer_num}.key": outputs[1],
                f"present.{layer_num}.value": outputs[2]
            })
            
        elif block_idx == 32 and len(outputs) >= 1:  # Block 33
            propagating_tensors["logits"] = outputs[0]
            
    elif isinstance(outputs, dict):
        propagating_tensors.update(outputs)


# --- WebSocket Handler ---
async def handler(websocket, path=None):
    """WebSocket handler with full pipeline management"""
    global CPU_WORKER, GPU_WORKER, EXECUTION_PLAN, MODEL_CHAIN_ORDER
    
    # Get node info
    handler_node_id = NODE_ID or "UNKNOWN_NODE"
    peer_address_str = str(websocket.remote_address)
    connection_id = f"conn_{id(websocket)}"
    
    logging.info(
        f"Handler: New WebSocket connection from {peer_address_str}",
        extra={"custom_extra_fields": {
            "event_type": "HANDLER_NEW_CONNECTION",
            "node_id": handler_node_id,
            "session_id": "N/A",
            "step": -1,
            "data": {"peer_address": peer_address_str, "connection_id": connection_id}
        }}
    )
    
    try:
        async for message_raw in websocket:
            message_start_time = time.time()
            
            try:
                # Parse message
                if isinstance(message_raw, bytes):
                    message_str = message_raw.decode('utf-8')
                else:
                    message_str = message_raw
                
                data = json.loads(message_str)
                
                session_id = data.get('session_id', 'unknown')
                step = data.get('step', 0)
                
                # Log received request
                logging.info(
                    f"Processing pipeline request",
                    extra={"custom_extra_fields": {
                        "event_type": "PIPELINE_REQUEST_RECEIVED",
                        "node_id": handler_node_id,
                        "session_id": session_id,
                        "step": step,
                        "data": {
                            "input_keys": list(data.get('input_tensors', {}).keys()),
                            "message_size": len(message_str),
                            "connection_id": connection_id
                        }
                    }}
                )
                
                # Validate request
                if not data.get('input_tensors'):
                    error_response = {
                        "status": "error",
                        "message": "Missing input_tensors in request",
                        "session_id": session_id,
                        "step": step
                    }
                    await websocket.send(json.dumps(error_response, default=str))
                    continue
                
                # Execute pipeline
                pipeline_result = await execute_pipeline(
                    session_id=session_id,
                    step=step,
                    initial_inputs=data.get('input_tensors', {})
                )
                
                # Send response
                response_json = json.dumps(pipeline_result, default=str)
                await websocket.send(response_json)
                
                message_total_time = time.time() - message_start_time
                
                # Enhanced response logging
                logging.info(
                    f"Pipeline response sent",
                    extra={"custom_extra_fields": {
                        "event_type": "PIPELINE_RESPONSE_SENT",
                        "node_id": handler_node_id,
                        "session_id": session_id,
                        "step": step,
                        "data": {
                            "status": pipeline_result['status'],
                            "response_size": len(response_json),
                            "total_message_time": message_total_time,
                            "pipeline_time": pipeline_result.get('total_pipeline_time', 0),
                            "connection_id": connection_id
                        }
                    }}
                )
                
            except json.JSONDecodeError as e:
                error_response = {
                    "status": "error",
                    "message": f"Invalid JSON: {str(e)}",
                    "error_type": "json_decode_error"
                }
                await websocket.send(json.dumps(error_response))
                
                logging.error(
                    f"JSON decode error: {str(e)}",
                    extra={"custom_extra_fields": {
                        "event_type": "HANDLER_JSON_DECODE_ERROR",
                        "node_id": handler_node_id,
                        "session_id": "N/A",
                        "step": -1,
                        "data": {
                            "error": str(e),
                            "message_preview": message_str[:100] if 'message_str' in locals() else "N/A",
                            "connection_id": connection_id
                        }
                    }}
                )
                
            except Exception as e:
                logging.error(
                    f"Handler error: {type(e).__name__}: {str(e)}",
                    exc_info=True,
                    extra={"custom_extra_fields": {
                        "event_type": "HANDLER_ERROR",
                        "node_id": handler_node_id,
                        "session_id": data.get('session_id', 'N/A') if 'data' in locals() else "N/A",
                        "step": data.get('step', -1) if 'data' in locals() else -1,
                        "data": {
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "connection_id": connection_id
                        }
                    }}
                )
                
                error_response = {
                    "status": "error",
                    "message": f"Server error: {str(e)}",
                    "error_type": type(e).__name__,
                    "session_id": data.get('session_id', 'unknown') if 'data' in locals() else 'unknown',
                    "step": data.get('step', 0) if 'data' in locals() else 0
                }
                
                try:
                    await websocket.send(json.dumps(error_response))
                except:
                    logging.error(
                        f"Failed to send error response to {peer_address_str}",
                        extra={"custom_extra_fields": {
                            "event_type": "HANDLER_SEND_ERROR_FAILED",
                            "node_id": handler_node_id,
                            "session_id": "N/A",
                            "step": -1,
                            "data": {"connection_id": connection_id}
                        }}
                    )
    
    except websockets.exceptions.ConnectionClosed:
        logging.info(
            f"Connection closed from {peer_address_str}",
            extra={"custom_extra_fields": {
                "event_type": "CONNECTION_CLOSED",
                "node_id": handler_node_id,
                "session_id": "N/A",
                "step": -1,
                "data": {
                    "peer_address": peer_address_str,
                    "connection_id": connection_id
                }
            }}
        )
        
    except Exception as e:
        logging.error(
            f"Unexpected handler error: {type(e).__name__}: {str(e)}",
            exc_info=True,
            extra={"custom_extra_fields": {
                "event_type": "HANDLER_UNEXPECTED_ERROR",
                "node_id": handler_node_id,
                "session_id": "N/A", 
                "step": -1,
                "data": {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "connection_id": connection_id
                }
            }}
        )
        
    finally:
        logging.info(
            f"Handler finished for {peer_address_str}",
            extra={"custom_extra_fields": {
                "event_type": "HANDLER_FINISHED",
                "node_id": handler_node_id,
                "session_id": "N/A",
                "step": -1,
                "data": {
                    "peer_address": peer_address_str,
                    "connection_id": connection_id
                }
            }}
        )

# --- Signal Handling ---
def handle_shutdown_signal(sig, frame, shutdown_event_ref: Optional[asyncio.Event] = None):
    """Handle shutdown signals"""
    signal_name_resolved = signal.Signals(sig).name if hasattr(signal, 'Signals') else str(sig)
    node_id_for_signal_log = NODE_ID_FOR_LOGGING_HOLDER.get("id", "UNKNOWN_NODE_ON_SIGNAL")
    
    logging.warning(
        f"Shutdown signal received (Signal: {signal_name_resolved}). Initiating shutdown for node '{node_id_for_signal_log}'.",
        extra={"custom_extra_fields": {
            "event_type": "NODE_SHUTDOWN_SIGNAL_RECEIVED",
            "node_id": node_id_for_signal_log,
            "session_id": "N/A_Shutdown_Signal",
            "step": -1,
            "data": {
                "signal_number_received": sig,
                "resolved_signal_name": signal_name_resolved
            }
        }}
    )
    
    if shutdown_event_ref and not shutdown_event_ref.is_set():
        shutdown_event_ref.set()


# --- Main Server Function ---
async def main_server(
    node_id_arg: str, 
    network_config_file_path_arg: Path,
    initial_kv_pages_arg: int, 
    kv_page_tokens_arg: int,
    max_warm_sessions_homf_arg: int
):
    """Main server function with enhanced worker management"""
    global GLOBAL_HOMF_POOL, ASSIGNED_BLOCK_IDS_IN_ORDER, BLOCK_IO_DETAILS_FULL, \
           EXPECTED_DTYPES, NUM_KV_HEADS, HEAD_DIM, NODE_ID, NETWORK_CONFIG, MODEL_CHAIN_ORDER, \
           SHUTDOWN_EVENT, GLOBAL_PAGE_MANAGER, KV_CACHE_DTYPE_NP, \
           INITIAL_PAGES_PER_MANAGER_KV, DEFAULT_PAGE_CAPACITY_TOKENS_KV, \
           KV_CACHE_STORAGE, NODE_ID_FOR_LOGGING_HOLDER, MAX_WARM_SESSIONS_HOMF_CONFIG, \
           PROJECT_ROOT, CPU_WORKER, GPU_WORKER, EXECUTION_PLAN, EXECUTION_SCHEDULER, \
           GLOBAL_PROFILER, HEALTH_MONITOR_TASK, ADAPTIVE_SCHEDULING_ENABLED, \
           PROFILER_SAMPLING_INTERVAL, MEMORY_INTENSIVE_BLOCKS, FORCE_CPU_BLOCKS

    # Initialize node
    NODE_ID = node_id_arg
    NODE_ID_FOR_LOGGING_HOLDER["id"] = NODE_ID
    NODE_ID_FOR_LOGGING_HOLDER["current_session_id"] = "N/A_Server_Setup"
    NODE_ID_FOR_LOGGING_HOLDER["current_step"] = -1

    # Apply settings
    INITIAL_PAGES_PER_MANAGER_KV = initial_kv_pages_arg
    DEFAULT_PAGE_CAPACITY_TOKENS_KV = kv_page_tokens_arg
    MAX_WARM_SESSIONS_HOMF_CONFIG = max_warm_sessions_homf_arg

    logging.info(
        f"Initializing node '{NODE_ID}' with parameters",
        extra={"custom_extra_fields": {
            "event_type": "NODE_INITIALIZATION_START",
            "node_id": NODE_ID,
            "session_id": "N/A_Server_Setup",
            "step": -1,
            "data": {
                "max_warm_sessions": max_warm_sessions_homf_arg,
                "initial_kv_pages": initial_kv_pages_arg,
                "kv_page_tokens": kv_page_tokens_arg
            }
        }}
    )
    
    # Initialize core components
    KV_CACHE_STORAGE.clear()
    SHUTDOWN_EVENT = asyncio.Event()
    
    try:
        # 1. Initialize Dynamic Profiler
        await initialize_profiler()
        
        # 2. Setup signal handlers
        setup_signal_handlers()
        
        # 3. Load network configuration
        network_config_data = await load_network_configuration(network_config_file_path_arg)
        
        # 4. Load model metadata
        model_metadata = await load_model_metadata(network_config_data)
        
        # 5. Initialize cache managers
        await initialize_cache_managers(model_metadata)
        
        # 6. Initialize HOMF pool
        await initialize_homf_pool(model_metadata)
        
        # 7. Setup execution plan
        await setup_execution_plan(network_config_data)
        
        # 8. Initialize workers
        worker_tasks = await initialize_workers(model_metadata)
        
        # 9. Start WebSocket server
        server = await start_websocket_server(network_config_data)
        
        logging.info(
            f"🚀 Node '{NODE_ID}' is ready and operational",
            extra={"custom_extra_fields": {
                "event_type": "NODE_READY",
                "node_id": NODE_ID,
                "session_id": "N/A_Server_Ready",
                "step": -1,
                "data": {
                    "workers_initialized": {
                        "cpu": CPU_WORKER is not None,
                        "gpu": GPU_WORKER is not None
                    },
                    "total_blocks": len(MODEL_CHAIN_ORDER),
                    "assigned_blocks": len(ASSIGNED_BLOCK_IDS_IN_ORDER),
                    "adaptive_scheduling": ADAPTIVE_SCHEDULING_ENABLED
                }
            }}
        )

        # Wait for shutdown
        await SHUTDOWN_EVENT.wait()
        
        # Graceful shutdown
        await graceful_shutdown(server)
        
    except Exception as e:
        logging.error(
            f"Critical error in main_server: {str(e)}",
            exc_info=True,
            extra={"custom_extra_fields": {
                "event_type": "NODE_CRITICAL_ERROR",
                "node_id": NODE_ID,
                "session_id": "N/A_Server_Setup",
                "step": -1,
                "data": {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            }}
        )
        raise
    
    finally:
        await cleanup_resources()


# --- Helper Functions ---

async def initialize_profiler():
    """Initialize Dynamic Profiler if enabled"""
    global GLOBAL_PROFILER, HEALTH_MONITOR_TASK, ADAPTIVE_SCHEDULING_ENABLED
    
    if not ADAPTIVE_SCHEDULING_ENABLED:
        logging.info("Adaptive scheduling disabled, skipping profiler initialization")
        return
    
    try:
        GLOBAL_PROFILER = DynamicProfiler(
            sampling_interval=PROFILER_SAMPLING_INTERVAL,
            history_size=1200
        )
        
        await GLOBAL_PROFILER.start_monitoring()
        
        initial_metrics = await GLOBAL_PROFILER.get_system_performance_factor()
        logging.info(
            f"System health score: {initial_metrics['system_health_score']:.2f}",
            extra={"custom_extra_fields": {
                "event_type": "SYSTEM_INITIALIZED",
                "node_id": NODE_ID,
                "data": {
                    "cpu_cores": initial_metrics['cpu']['core_count'],
                    "gpu_available": initial_metrics['gpu']['available'],
                    "gpu_type": initial_metrics['gpu'].get('type', 'none'),
                    "total_memory_gb": initial_metrics['memory']['total_gb']
                }
            }}
        )
        
        HEALTH_MONITOR_TASK = asyncio.create_task(system_health_monitor())
        
    except Exception as e:
        logging.error(f"Failed to initialize Dynamic Profiler: {e}")
        GLOBAL_PROFILER = None
        ADAPTIVE_SCHEDULING_ENABLED = False


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    loop = asyncio.get_running_loop()
    for sig_val in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig_val, 
                lambda s=sig_val: handle_shutdown_signal(s, None, SHUTDOWN_EVENT)
            )
        except (NotImplementedError, RuntimeError) as e:
            logging.warning(f"Could not set signal handler for {signal.Signals(sig_val).name}: {e}")


async def load_network_configuration(config_path: Path) -> Dict[str, Any]:
    """Load and validate network configuration"""
    global NETWORK_CONFIG, ASSIGNED_BLOCK_IDS_IN_ORDER, MODEL_CHAIN_ORDER
    
    logging.info(f"Loading network configuration from: {config_path}")
    
    # Initialize ConfigManager with the specified config file
    config_manager = initialize_config(str(config_path))
    NETWORK_CONFIG = config_manager.network_config
    
    # Validate configuration
    nodes_config = NETWORK_CONFIG.get("nodes", {})
    current_node_config = nodes_config.get(NODE_ID)
    
    if not current_node_config:
        raise ValueError(f"Node '{NODE_ID}' not found in network config")
    
    ASSIGNED_BLOCK_IDS_IN_ORDER = current_node_config.get("assigned_block_ids_ordered_list", [])
    MODEL_CHAIN_ORDER = NETWORK_CONFIG.get("model_chain_order", [])
    
    # Ensure block_33 is in the chain
    if "block_33" not in MODEL_CHAIN_ORDER:
        logging.warning("block_33 not found in model_chain_order, adding it")
        MODEL_CHAIN_ORDER.append("block_33")
    
    # Update FORCE_CPU_BLOCKS if block_33 should run on CPU
    if "block_33" not in FORCE_CPU_BLOCKS:
        FORCE_CPU_BLOCKS.append("block_33")
        logging.info("Added block_33 to FORCE_CPU_BLOCKS due to memory requirements")
    
    return {
        "host": current_node_config.get("host", "localhost"),
        "port": current_node_config.get("port", 8700),
        "node_config": current_node_config,
        "network_config": NETWORK_CONFIG
    }


async def load_model_metadata(network_config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Load model metadata from file"""
    global BLOCK_IO_DETAILS_FULL, EXPECTED_DTYPES, NUM_KV_HEADS, HEAD_DIM
    
    config_manager = get_config_manager()
    metadata_file = Path(config_manager.network_config["paths"]["metadata_file"])
    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_file}")
    
    logging.info(f"Loading model metadata from: {metadata_file}")
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Extract required fields
    BLOCK_IO_DETAILS_FULL = metadata.get('block_io_details', {})
    if not BLOCK_IO_DETAILS_FULL:
        raise ValueError("'block_io_details' missing in metadata")
    
    EXPECTED_DTYPES = {k: np.dtype(v) for k, v in metadata.get('expected_dtypes', {}).items()}
    
    NUM_KV_HEADS = metadata.get('num_key_value_heads')
    HEAD_DIM = metadata.get('head_dim')
    
    if NUM_KV_HEADS is None or HEAD_DIM is None:
        raise ValueError("'num_key_value_heads' or 'head_dim' missing in metadata")
    
    NUM_KV_HEADS = int(NUM_KV_HEADS)
    HEAD_DIM = int(HEAD_DIM)
    
    return metadata


async def initialize_cache_managers(metadata: Dict[str, Any]):
    """Initialize KV cache managers"""
    global GLOBAL_PAGE_MANAGER
    
    GLOBAL_PAGE_MANAGER = PagedKVCacheManager(
        INITIAL_PAGES_PER_MANAGER_KV,
        DEFAULT_PAGE_CAPACITY_TOKENS_KV,
        NUM_KV_HEADS,
        HEAD_DIM,
        KV_CACHE_DTYPE_NP,
        batch_size=1
    )
    
    logging.info("PagedKVCacheManager initialized")


async def initialize_homf_pool(metadata: Dict[str, Any]):
    """Initialize HOMF pool for model caching"""
    global GLOBAL_HOMF_POOL
    
    config_manager = get_config_manager()
    
    GLOBAL_HOMF_POOL = WarmStatePool(
        project_root_path=config_manager.project_root,
        network_config_global=NETWORK_CONFIG,
        model_metadata_global=metadata,
        max_warm_sessions=MAX_WARM_SESSIONS_HOMF_CONFIG,
        prefer_homf_format=True,
        enable_detailed_logging=(logging.getLogger().level <= logging.DEBUG)
    )
    
    if MODEL_CHAIN_ORDER:
        initialize_homf_globals(MODEL_CHAIN_ORDER)
    
    logging.info(f"HOMF WarmStatePool initialized with {MAX_WARM_SESSIONS_HOMF_CONFIG} max sessions")


async def setup_execution_plan(network_config_data: Dict[str, Any]):
    """Setup execution plan and scheduler"""
    global EXECUTION_SCHEDULER, EXECUTION_PLAN
    
    profiling_file = NETWORK_CONFIG.get("profiling_file_path")
    
    if profiling_file and Path(profiling_file).exists():
        try:
            EXECUTION_SCHEDULER = StaticSplitScheduler(
                profiling_file_path=profiling_file,
                model_chain_order=MODEL_CHAIN_ORDER
            )
            EXECUTION_PLAN = EXECUTION_SCHEDULER.generate_execution_plan()
            
            # Override for memory intensive blocks
            for block_id in FORCE_CPU_BLOCKS:
                if block_id in EXECUTION_PLAN:
                    EXECUTION_PLAN[block_id] = "CPU"
                    logging.info(f"Forced {block_id} to CPU due to memory requirements")
            
        except Exception as e:
            logging.error(f"Failed to load profiling data: {e}")
            EXECUTION_PLAN = create_default_execution_plan()
    else:
        EXECUTION_PLAN = create_default_execution_plan()


def create_default_execution_plan() -> Dict[str, str]:
    """Create default execution plan"""
    plan = {}
    for block_id in MODEL_CHAIN_ORDER:
        # Force CPU for memory intensive blocks
        if block_id in FORCE_CPU_BLOCKS:
            plan[block_id] = "CPU"
        else:
            plan[block_id] = "GPU"
    
    logging.info(f"Created default execution plan: {len([v for v in plan.values() if v == 'CPU'])} CPU, {len([v for v in plan.values() if v == 'GPU'])} GPU")
    return plan


async def initialize_workers(metadata: Dict[str, Any]) -> List[asyncio.Task]:
    """Initialize CPU and GPU workers"""
    global CPU_WORKER, GPU_WORKER
    
    tasks = []
    
    # CPU Worker
    try:
        CPU_WORKER = CPUWorker(
            name="CPUWorker",
            homf_pool=GLOBAL_HOMF_POOL,
            max_executor_threads=2
        )
        cpu_task = asyncio.create_task(CPU_WORKER.run(), name="cpu_worker_loop")
        tasks.append(cpu_task)
        logging.info("✅ CPU Worker initialized")
    except Exception as e:
        logging.error(f"Failed to initialize CPU Worker: {e}")
        CPU_WORKER = None
    
    # GPU Worker
    try:
        config_manager = get_config_manager()
        
        GPU_WORKER = SequentialGPUWorker(
            name="SequentialGPUWorker",
            project_root_path=config_manager.project_root,
            network_config_global=NETWORK_CONFIG,
            model_metadata_global=metadata,
            max_retry_attempts=3,
            session_timeout=60.0,
            memory_cleanup_interval=2
        )
        gpu_task = asyncio.create_task(GPU_WORKER.run(), name="gpu_worker_loop")
        tasks.append(gpu_task)
        await asyncio.sleep(0.5)  # Allow GPU worker to initialize
        logging.info("✅ Sequential GPU Worker initialized")
    except Exception as e:
        logging.error(f"Failed to initialize GPU Worker: {e}")
        GPU_WORKER = None
    
    return tasks


async def start_websocket_server(config_data: Dict[str, Any]):
    """Start WebSocket server with enhanced protocol support"""
    host = config_data["host"]
    port = config_data["port"]
    
    logging.info(f"Starting Enhanced WebSocket server on {host}:{port}")
    
    # Import enhanced handler
    try:
        from network.enhanced_websocket_handler import enhanced_websocket_handler
        websocket_handler = enhanced_websocket_handler
        logging.info("Using Enhanced WebSocket Handler with protocol support")
    except ImportError as e:
        logging.warning(f"Enhanced handler not available, using legacy handler: {e}")
        websocket_handler = handler
    
    start_server = websockets.serve(
        websocket_handler,
        host,
        port,
        max_size=None,
        compression=None,
        ping_interval=25,
        ping_timeout=30
    )
    
    return await start_server


async def graceful_shutdown(server):
    """Perform graceful shutdown"""
    logging.info("Starting graceful shutdown...")
    
    server.close()
    await server.wait_closed()
    
    logging.info("WebSocket server closed")


async def cleanup_resources():
    """Clean up all resources"""
    effective_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "UNKNOWN_NODE")
    
    # Stop profiler
    if GLOBAL_PROFILER:
        try:
            await GLOBAL_PROFILER.stop_monitoring()
            logging.info("Dynamic Profiler stopped")
        except Exception as e:
            logging.error(f"Error stopping profiler: {e}")
    
    # Cancel health monitor
    if HEALTH_MONITOR_TASK:
        HEALTH_MONITOR_TASK.cancel()
        try:
            await HEALTH_MONITOR_TASK
        except asyncio.CancelledError:
            pass
        logging.info("Health monitor stopped")
    
    # Shutdown workers
    await shutdown_workers()
    
    # Cleanup HOMF pool
    await cleanup_homf_pool()
    
    # Clear KV cache
    try:
        KV_CACHE_STORAGE.clear()
        logging.info("KV cache cleared")
    except Exception as e:
        logging.error(f"Error clearing KV cache: {e}")
    
    logging.info(f"Node '{effective_node_id}' cleanup completed")


async def shutdown_workers():
    """Shutdown all workers gracefully"""
    if CPU_WORKER:
        try:
            if hasattr(CPU_WORKER, 'shutdown'):
                await CPU_WORKER.shutdown()
            logging.info("CPU Worker shutdown complete")
        except Exception as e:
            logging.error(f"Error shutting down CPU Worker: {e}")
    
    if GPU_WORKER:
        try:
            if hasattr(GPU_WORKER, 'shutdown'):
                GPU_WORKER.shutdown()  # Sequential GPU Worker has sync shutdown
            logging.info("GPU Worker shutdown complete")
        except Exception as e:
            logging.error(f"Error shutting down GPU Worker: {e}")


async def cleanup_homf_pool():
    """Clean up HOMF pool resources"""
    if not GLOBAL_HOMF_POOL:
        return
    
    try:
        if hasattr(GLOBAL_HOMF_POOL, 'is_shutting_down'):
            GLOBAL_HOMF_POOL.is_shutting_down = True
        
        if hasattr(GLOBAL_HOMF_POOL, 'shutdown'):
            GLOBAL_HOMF_POOL.shutdown()
        elif hasattr(GLOBAL_HOMF_POOL, 'warm_sessions'):
            GLOBAL_HOMF_POOL.warm_sessions.clear()
        
        logging.info("HOMF Pool shutdown complete")
    except Exception as e:
        logging.error(f"Error during HOMF Pool shutdown: {e}")

# --- CLI Entry Point ---
if __name__ == "__main__":
    # مقادیر پیش‌فرض CLI
    DEFAULT_INITIAL_KV_PAGES_GLOBAL_CLI = 16
    DEFAULT_KV_PAGE_TOKENS_CAP_CLI = 16
    DEFAULT_LOG_LEVEL_CLI = "INFO"
    DEFAULT_MAX_WARM_SESSIONS_HOMF_CLI = 1

    parser = argparse.ArgumentParser(
        description="Enhanced Distributed LLM Inference Model Node Server with Advanced Error Handling", 
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("--node-id", type=str, required=True, 
                        help="Unique Node ID for this instance.")
    parser.add_argument("--network-config", type=Path, required=True, 
                        help="Path to the network_config.json file.")
    parser.add_argument("--log-file", type=str, default=None, 
                        help="Optional: Path to JSONL log file.")
    parser.add_argument("--log-level", type=str, default=DEFAULT_LOG_LEVEL_CLI, 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], 
                        help="Logging level for the node.")
    parser.add_argument("--max-warm-homf", type=int, default=DEFAULT_MAX_WARM_SESSIONS_HOMF_CLI, 
                        help="Max warm sessions in HOMF Pool.")
    parser.add_argument("--initial-kv-pages", type=int, default=DEFAULT_INITIAL_KV_PAGES_GLOBAL_CLI, 
                        help="Initial pages for PagedKVCacheManager (per-session KV).")
    parser.add_argument("--kv-page-tokens", type=int, default=DEFAULT_KV_PAGE_TOKENS_CAP_CLI, 
                        help="Token capacity per KV cache page.")

    parser.add_argument(
        "--enable-adaptive-scheduling",
        action="store_true",
        default=True,
        help="Enable adaptive scheduling based on system metrics"
    )

    parser.add_argument(
        "--no-adaptive-scheduling",
        action="store_true", 
        help="Disable adaptive scheduling"
    )

    parser.add_argument(
        "--profiler-interval",
        type=float,
        default=0.5,
        help="Sampling interval for system profiler (seconds)"
    )

    parser.add_argument(
    "--force-cpu-blocks",
        type=str,
        nargs='+',
        default=["block_33"],
        help="Blocks that must always run on CPU (e.g., --force-cpu-blocks block_32 block_33)"
    )

    parser.add_argument(
        "--memory-threshold",
        type=float,
        default=85.0,
        help="Memory usage percentage threshold for forcing blocks to CPU"
    )

    

    args = parser.parse_args()

    # در قسمت پردازش arguments:
    FORCE_CPU_BLOCKS = args.force_cpu_blocks
    MEMORY_THRESHOLD = args.memory_threshold

    # Configure enhanced logging
    log_level = getattr(logging, args.log_level.upper())
    
    # Setup JSON formatter for structured logging
    json_formatter = MainJsonFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    console_handler.setLevel(log_level)
    
    if args.no_adaptive_scheduling:
        ADAPTIVE_SCHEDULING_ENABLED = False
    else:
        ADAPTIVE_SCHEDULING_ENABLED = True

    PROFILER_SAMPLING_INTERVAL = args.profiler_interval

    # File handler (if specified)
    file_handler = None
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(json_formatter)
        file_handler.setLevel(log_level)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplication
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add our handlers
    root_logger.addHandler(console_handler)
    if file_handler:
        root_logger.addHandler(file_handler)

    # Log startup information
    startup_info = {
        "node_id": args.node_id,
        "network_config": str(args.network_config),
        "log_level": args.log_level,
        "max_warm_homf": args.max_warm_homf,
        "initial_kv_pages": args.initial_kv_pages,
        "kv_page_tokens": args.kv_page_tokens,
        "log_file": args.log_file
    }
    
    logging.info(
        f"🚀 Starting Enhanced Distributed LLM Inference Node: {args.node_id}",
        extra={"custom_extra_fields": {
            "event_type": "SERVER_STARTUP_INITIATED",
            "node_id": args.node_id,
            "session_id": "N/A_CLI_Startup",
            "step": -1,
            "data": startup_info
        }}
    )

    # Run the main server
    try:
        asyncio.run(main_server(
            node_id_arg=args.node_id,
            network_config_file_path_arg=args.network_config,
            initial_kv_pages_arg=args.initial_kv_pages,
            kv_page_tokens_arg=args.kv_page_tokens,
            max_warm_sessions_homf_arg=args.max_warm_homf
        ))
        
        logging.info(
            f"✅ Server '{args.node_id}' shutdown completed successfully",
            extra={"custom_extra_fields": {
                "event_type": "SERVER_SHUTDOWN_COMPLETED",
                "node_id": args.node_id,
                "session_id": "N/A_CLI_Shutdown",
                "step": -1,
                "data": {}
            }}
        )
        
    except KeyboardInterrupt:
        logging.info(
            f"⛔ Server '{args.node_id}' interrupted by user (Ctrl+C)",
            extra={"custom_extra_fields": {
                "event_type": "SERVER_INTERRUPTED_BY_USER",
                "node_id": args.node_id,
                "session_id": "N/A_CLI_Interrupt",
                "step": -1,
                "data": {}
            }}
        )
        
    except Exception as e:
        logging.error(
            f"💥 Server '{args.node_id}' crashed: {type(e).__name__}: {str(e)}",
            exc_info=True,
            extra={"custom_extra_fields": {
                "event_type": "SERVER_CRASHED",
                "node_id": args.node_id,
                "session_id": "N/A_CLI_Crash",
                "step": -1,
                "data": {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "startup_config": startup_info
                }
            }}
        )
        sys.exit(1)
    
    finally:
        logging.info(
            f"🏁 Server '{args.node_id}' process completed",
            extra={"custom_extra_fields": {
                "event_type": "SERVER_PROCESS_COMPLETED",
                "node_id": args.node_id,
                "session_id": "N/A_CLI_Final",
                "step": -1,
                "data": {}
            }}
        )