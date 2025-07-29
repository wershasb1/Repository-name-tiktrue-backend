import os
import sys
import time
import threading
import json
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import OrderedDict
import asyncio
import re
import gc
import numpy as np
import collections
# psutil for memory logging on errors
try:
    import psutil
except ImportError:
    psutil = None

try:
    import onnx
    from onnx import numpy_helper, mapping as onnx_mapping
except ImportError as e_onnx_homf:
    logging.error(f"HOMF: onnx library not found, install it: pip install onnx. Error: {e_onnx_homf}")
    raise

try:
    import onnxruntime as ort
    from onnxruntime import OrtValue, SessionOptions, GraphOptimizationLevel, InferenceSession
except ImportError as e_ort_homf:
    logging.error(f"HOMF: Error importing onnxruntime: {e_ort_homf}")
    raise

logger = logging.getLogger("HOMF_Library")

# Temporary workaround if initialize_homf_globals is missing
try:
    from networked_distributed_inference.homf_lib import initialize_homf_globals
except ImportError:
    def initialize_homf_globals(model_chain_order_list):
        import logging
        logger = logging.getLogger("HOMF_Library")
        logger.info(f"Using temporary initialize_homf_globals with {len(model_chain_order_list)} blocks")

# Helper function to get dtype from metadata
def get_dtype_from_metadata(block_id: str, input_name: str, metadata: Dict[str, Any]) -> np.dtype:
    """Get numpy dtype for an input based on metadata"""
    expected_dtypes = metadata.get("expected_dtypes", {})
    block_io_details = metadata.get("block_io_details", {})

    block_meta = block_io_details.get(block_id, {})
    for input_spec in block_meta.get("inputs", []):
        if input_spec.get("name") == input_name:
            if "dtype" in input_spec:
                dtype_str = input_spec["dtype"]
                if dtype_str == "int32": return np.int32
                elif dtype_str == "int64": return np.int64
                elif dtype_str == "float32": return np.float32
                elif dtype_str == "float16": return np.float16

    if input_name in expected_dtypes:
        dtype_str = expected_dtypes[input_name]
        try:
            return np.dtype(dtype_str)
        except TypeError:
            logger.warning(f"Could not convert dtype string '{dtype_str}' to np.dtype for input '{input_name}'.")

    # Fallback rules
    if block_id == "block_1" and "input_ids" in input_name:
        return np.int32
    if "input_ids" in input_name or "attention_mask" in input_name or "position_ids" in input_name:
        return np.int64
    if "past_key_values" in input_name or ".key" in input_name or ".value" in input_name:
        return np.float32

    return np.float32  # Default fallback

class WarmStatePool:
    def __init__(self, max_warm_sessions=10, prefer_homf_format=True,
                 project_root_path=None, network_config_global=None,
                 model_metadata_global=None, enable_detailed_logging=False,
                 execution_providers=None):
        self.max_warm_sessions = max_warm_sessions if max_warm_sessions > 0 else 1
        self.prefer_homf_format = prefer_homf_format
        self.enable_detailed_logging = enable_detailed_logging
        self.execution_providers = execution_providers or ['CPUExecutionProvider']
        self.project_root_path = Path(project_root_path) if project_root_path else None
        self.network_config_global = network_config_global
        self.model_metadata_global = model_metadata_global

        # Use OrderedDict for LRU eviction
        self.warm_sessions: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.warm_states: Dict[str, Dict[str, Any]] = {}
        self.session_metadata_store: Dict[str, Dict[str, Any]] = {}
        self.shared_inputs_cache: Dict[str, np.ndarray] = {}

        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'failed_loads': 0,
            'warmup_successes': 0,
            'warmup_failures': 0,
            'session_executions': 0,
            'session_execution_failures': 0,
            'cache_evictions': 0,
        }

        self._lock = threading.RLock()

        self.is_shutting_down = False

        logger.info(f"Initialized WarmStatePool: max_sessions={self.max_warm_sessions}, "
                    f"prefer_homf={self.prefer_homf_format}, detailed_logging={self.enable_detailed_logging}")

    def shutdown(self):
        """
        این متد WarmStatePool را به صورت صحیح و مرحله به مرحله خاموش می‌کند و منابع را آزاد می‌کند.
        """
        if self.is_shutting_down:
            return # قبلاً در حال خاموش شدن است

        self.is_shutting_down = True
        logging.info("WarmStatePool: The shutdown process has begun.")
        # اینجا هر منطق پاکسازی خاصی برای pool خود را اضافه کنید.
        # مثلاً اگر session های فعال رو مدیریت می‌کنه، ممکنه بخواهید اون‌ها رو ببندید.
        # self._cleanup_sessions() # مثال: فراخوانی متد پاکسازی session ها

        logging.info("WarmStatePool: خاموش شدن کامل شد.")
    
    
    def _log_event(self, event_type: str, data: Dict[str, Any] = None, level: str = "INFO"):
        """Log structured events for HOMF operations compatible with MainJsonFormatter"""
        if data is None:
            data = {}
        
        log_message_summary = f"HOMF Event: {event_type}"
        data_for_extra = data.copy()
        
        # Add system info if detailed logging is enabled
        if getattr(self, 'enable_detailed_logging', False) and psutil:
            try:
                process = psutil.Process()
                memory_usage_mb = process.memory_info().rss / (1024 * 1024)
                thread_count = threading.active_count()
                with self._lock:
                    pool_sessions_count = len(self.warm_sessions)
                    shared_cache_keys_count = len(self.shared_inputs_cache)
                    warm_states_count = len(self.warm_states)

                data_for_extra['_homf_system_info_'] = {
                    'memory_usage_mb': round(memory_usage_mb, 2),
                    'thread_count': thread_count,
                    'pool_sessions_count': pool_sessions_count,
                    'warm_states_count': warm_states_count,
                    'shared_cache_keys_count': shared_cache_keys_count,
                    'max_warm_sessions_limit': self.max_warm_sessions
                }
            except Exception as e:
                logger.debug(f"Failed to collect system info for logging: {e}")

        custom_extra_content = {"event_type": f"HOMF_{event_type.upper()}", "data": data_for_extra}
        level_upper = level.upper()
        log_func = getattr(logger, level_upper.lower(), logger.info)
        log_func(log_message_summary, extra={"custom_extra_fields": custom_extra_content})

    def _determine_onnx_path(self, block_id: str) -> Path:
        """Determine the path to the original ONNX file for a given block_id"""
        if not self.project_root_path:
            raise ValueError("project_root_path is not initialized in WarmStatePool")
        if not self.network_config_global:
            raise ValueError("network_config_global is not initialized in WarmStatePool")
        if not self.model_metadata_global:
            raise ValueError("model_metadata_global is not initialized in WarmStatePool")

        try:
            onnx_blocks_dir_str = self.network_config_global["paths"]["onnx_blocks_dir"]
        except KeyError as e:
            raise ValueError(f"Missing 'onnx_blocks_dir' in network_config['paths']: {e}")

        try:
            block_file_name = self.model_metadata_global["block_io_details"][block_id]["file_path"]
        except KeyError as e:
            available_blocks = list(self.model_metadata_global.get("block_io_details", {}).keys())
            raise ValueError(f"Block '{block_id}' not found or 'file_path' missing in model_metadata. Available: {available_blocks}. Error: {e}")

        # جستجو برای فایل‌های مختلف با اولویت
        base_path = self.project_root_path / onnx_blocks_dir_str
        
        # الگوهای مختلف نام‌گذاری فایل‌ها
        possible_patterns = [
            block_file_name,  # نام اصلی از metadata
            f"{block_id}_skeleton.optimized.onnx",  # فایل بهینه‌سازی شده
            f"{block_id}_skeleton_with_zeros.onnx",  # فایل با zeros
            f"{block_id}.onnx",  # نام ساده
            f"{block_id}_optimized.onnx",  # نام بهینه‌سازی شده
        ]
        
        complete_onnx_path = None
        for pattern in possible_patterns:
            candidate_path = base_path / pattern
            if candidate_path.exists() and candidate_path.is_file():
                complete_onnx_path = candidate_path
                logger.debug(f"Found ONNX file for block '{block_id}' using pattern '{pattern}': {complete_onnx_path}")
                break
        
        if not complete_onnx_path:
            # اگر هیچ فایل پیدا نشد، لیست فایل‌های موجود را نمایش بده
            available_files = list(base_path.glob("*.onnx")) if base_path.exists() else []
            available_names = [f.name for f in available_files]
            raise FileNotFoundError(
                f"ONNX file not found for block '{block_id}'. "
                f"Searched patterns: {possible_patterns}. "
                f"Available files: {available_names[:10]}{'...' if len(available_names) > 10 else ''}"
            )
        
        logger.debug(f"Determined ONNX path for block '{block_id}': {complete_onnx_path}")
        return complete_onnx_path

    def _get_homf_optimized_asset_paths(self, block_id: str) -> Dict[str, Optional[Path]]:
        """
        Get paths for HOMF optimized assets based on block_id.
        This method returns paths for multiple possible formats:
        1. Optimized graph with external data (e.g., block_1_skeleton.optimized.onnx)
        2. Zero skeleton for mmap loading (e.g., block_1_skeleton_with_zeros.onnx)
        3. Weights folder and metadata
        """
        try:
            original_onnx_path = self._determine_onnx_path(block_id)
        except (ValueError, FileNotFoundError) as e:
            logger.error(f"[{block_id}] Could not determine original ONNX path: {e}")
            return {
                'original_onnx': None,
                'optimized_graph_path': None,
                'skeleton_path': None,
                'weights_folder_path': None,
                'weights_metadata_path': None
            }
        
        original_parent_dir = original_onnx_path.parent
        original_stem = original_onnx_path.stem
        
        # Build all possible paths
        # 1. Optimized graph path (with graph optimization and external data references)
        optimized_graph_path = original_parent_dir / f"{original_stem}_skeleton.optimized.onnx"
        
        # 2. Zero skeleton path (for mmap weight injection)
        skeleton_path = original_parent_dir / f"{original_stem}_skeleton_with_zeros.onnx"
        
        # 3. Weights folder (shared by both methods)
        weights_folder_path = original_parent_dir / f"{original_stem}_weights"
        
        # 4. Weights metadata
        weights_metadata_path = weights_folder_path / "weights_metadata.json"
        
        asset_paths = {
            'original_onnx': original_onnx_path,
            'optimized_graph_path': optimized_graph_path,  # For optimized external data loading
            'skeleton_path': skeleton_path,                # For mmap zero-skeleton loading
            'weights_folder_path': weights_folder_path,    # Shared weights folder
            'weights_metadata_path': weights_metadata_path # Metadata for mmap loading
        }
        
        # Log detailed path information
        logger.debug(f"[{block_id}] HOMF asset paths determined:")
        logger.debug(f"[{block_id}]   Original ONNX: {original_onnx_path} (Exists: {original_onnx_path.exists()})")
        logger.debug(f"[{block_id}]   Optimized graph: {optimized_graph_path} (Exists: {optimized_graph_path.exists()})")
        logger.debug(f"[{block_id}]   Zero skeleton: {skeleton_path} (Exists: {skeleton_path.exists()})")
        logger.debug(f"[{block_id}]   Weights folder: {weights_folder_path} (Exists: {weights_folder_path.exists()}, IsDir: {weights_folder_path.is_dir() if weights_folder_path.exists() else False})")
        logger.debug(f"[{block_id}]   Weights metadata: {weights_metadata_path} (Exists: {weights_metadata_path.exists() if weights_folder_path.exists() else False})")
        
        return asset_paths

    def _load_session_with_mmap_weights(
    self,
    block_id: str,
    skeleton_model_path: Path,
    weights_metadata_path: Path,
    weights_dir_path: Path
    ) -> Tuple[Optional[ort.InferenceSession], float]:
        """
        Load ONNX session using skeleton model with zero placeholders and mmap weight injection.
        This method uses the proven approach: load mmap, copy to numpy array, create OrtValue, add_initializer.
        """
        start_time = time.perf_counter()

        self._log_event(
            "HOMF_LOAD_MMAP_ZEROSKEL_START",
            {
                'block_id': block_id,
                'skeleton_path': str(skeleton_model_path),
                'weights_dir': str(weights_dir_path)
            }
        )

        loaded_mmap_weights = {}  # Keep references to mmap objects

        try:
            # Check paths exist
            if not skeleton_model_path.exists():
                raise FileNotFoundError(f"Skeleton model not found: {skeleton_model_path}")
            if not weights_metadata_path.exists():
                raise FileNotFoundError(f"Weights metadata not found: {weights_metadata_path}")
            if not weights_dir_path.exists() or not weights_dir_path.is_dir():
                raise FileNotFoundError(f"Weights directory not found or not a directory: {weights_dir_path}")

            # Load weights metadata
            with open(weights_metadata_path, 'r') as f:
                weights_metadata = json.load(f)

            logger.info(f"[{block_id}] Loaded weights metadata with {len(weights_metadata)} weights")

            # Create session options
            sess_options = ort.SessionOptions()
            if block_id in ["block_33"]:
                sess_options.add_session_config_entry(
                    "session.use_env_allocators", "1"
                )
                # محدود کردن حافظه arena
                sess_options.add_session_config_entry(
                    "cpu_arena_shrink_strategy", "1"  # Aggressive shrinking
                )
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC

            # ===== تنظیمات جدید برای کاهش مصرف حافظه =====
            sess_options.enable_cpu_mem_arena = False    # غیرفعال کردن memory arena
            sess_options.enable_mem_pattern = False      # غیرفعال کردن memory pattern optimization
            sess_options.enable_mem_reuse = False       # فعال کردن استفاده مجدد از حافظه
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL  # اجرای ترتیبی
            # ==============================================

            # Process each weight
            weights_loaded_count = 0
            # Process each weight
            weights_loaded_count = 0
            total_weights_size_bytes = 0

            for weight_name, weight_info in weights_metadata.items():
                try:
                    # Get weight file path
                    weight_file_relative = weight_info.get('file_path') or weight_info.get('safe_filename')
                    if not weight_file_relative:
                        logger.warning(f"[{block_id}] No file path found for weight '{weight_name}', skipping")
                        continue

                    # Build full path to weight file
                    weight_file_path = weights_dir_path / weight_file_relative
                    if not weight_file_path.exists():
                        logger.warning(f"[{block_id}] Weight file not found: {weight_file_path}, skipping")
                        continue

                    # Get shape and dtype
                    shape = weight_info['shape']
                    dtype_str = weight_info['dtype']

                    # Convert dtype string to numpy dtype
                    dtype_map = {
                        'float32': np.float32, 'float': np.float32,
                        'float16': np.float16, 'fp16': np.float16,
                        'int64': np.int64, 'long': np.int64,
                        'int32': np.int32, 'int': np.int32,
                        'int8': np.int8, 'uint8': np.uint8,
                        'bool': np.bool_, 'double': np.float64
                    }
                    np_dtype = dtype_map.get(dtype_str.lower(), np.float32)

                    logger.debug(f"[{block_id}] Loading weight '{weight_name}': shape={shape}, dtype={np_dtype}, file={weight_file_path.name}")

                    # Memory map the weight file
                    mmap_array = np.memmap(weight_file_path, dtype=np_dtype, mode='r', shape=tuple(shape))
                    loaded_mmap_weights[weight_name] = mmap_array  # Keep reference

                    # Create a copy of the mmap array (this is the critical step that works)
                    copied_array = np.array(mmap_array, copy=True)

                    # Create OrtValue from the copied array
                    ort_value_weight = OrtValue.ortvalue_from_numpy(copied_array, 'cpu', 0)

                    # Add the initializer to session options
                    sess_options.add_initializer(weight_name, ort_value_weight)

                    weights_loaded_count += 1
                    total_weights_size_bytes += copied_array.nbytes

                    logger.debug(f"[{block_id}] Successfully added initializer for '{weight_name}' (size: {copied_array.nbytes:,} bytes)")

                except Exception as e:
                    logger.error(f"[{block_id}] Failed to load weight '{weight_name}': {e}", exc_info=True)
                    continue

            logger.info(f"[{block_id}] Loaded {weights_loaded_count}/{len(weights_metadata)} weights, total size: {total_weights_size_bytes:,} bytes")

            # Create the inference session with the skeleton model and injected weights
            # این خط رو تغییر بدید:
            session = ort.InferenceSession(
                str(skeleton_model_path),
                sess_options,
                providers=self.execution_providers  # <--- این خط رو اضافه کنید
            )

            # Attach mmap references to session to keep them alive
            setattr(session, '_homf_mmap_references', loaded_mmap_weights)

            load_time = time.perf_counter() - start_time

            # Get session info
            input_names = [inp.name for inp in session.get_inputs()]
            output_names = [out.name for out in session.get_outputs()]

            # Store metadata
            self.session_metadata_store[block_id] = {
                'load_time': load_time,
                'input_names': input_names,
                'output_names': output_names,
                'load_method': 'mmap_zeroskel_addinit',
                'load_format': 'onnx_zeroskel_mmap_weights',
                'skeleton_path': str(skeleton_model_path),
                'weights_loaded': weights_loaded_count,
                'total_weights_size': total_weights_size_bytes
            }

            self._log_event(
                "HOMF_LOAD_MMAP_ZEROSKEL_SUCCESS",
                {
                    'block_id': block_id,
                    'load_time': load_time,
                    'weights_loaded': weights_loaded_count,
                    'total_size_bytes': total_weights_size_bytes
                }
            )

            logger.info(f"[{block_id}] Successfully loaded session with mmap weights in {load_time:.3f}s")
            return session, load_time

        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            self.stats['failed_loads'] += 1

            logger.error(
                f"[{block_id}] Failed to load session with mmap weights: {type(e).__name__} - {str(e)}",
                exc_info=True
            )

            # Log memory info on failure
            if psutil:
                try:
                    virtual_mem = psutil.virtual_memory()
                    logger.error(
                        f"[{block_id}] Memory at mmap load failure: "
                        f"Available={virtual_mem.available / (1024**2):.2f}MB, "
                        f"Total={virtual_mem.total / (1024**2):.2f}MB, "
                        f"UsedPercent={virtual_mem.percent}%"
                    )
                except Exception as e_psutil:
                    logger.warning(f"[{block_id}] Could not get memory info: {e_psutil}")

            self._log_event(
                "HOMF_LOAD_MMAP_ZEROSKEL_FAILURE",
                {
                    'block_id': block_id,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'elapsed_time': elapsed_time
                },
                level="ERROR"
            )

            # Clean up any loaded mmap objects
            for mmap_obj in loaded_mmap_weights.values():
                try:
                    del mmap_obj
                except:
                    pass

            return None, elapsed_time
    def _load_session_from_optimized_external_data(
        self,
        block_id: str,
        optimized_graph_path: Path,
        external_data_base_dir: Path
    ) -> Tuple[Optional[ort.InferenceSession], float]:
        """
        Load ONNX session using optimized graph with external data references.
        This is for loading pre-optimized graphs (e.g., block_1_skeleton.optimized.onnx)
        that reference external weight files.
        """
        start_time = time.perf_counter()
        
        self._log_event(
            "LOAD_OPTIMIZED_EXTERNAL_START",
            {
                'block_id': block_id,
                'optimized_graph_path': str(optimized_graph_path),
                'external_data_base_dir': str(external_data_base_dir)
            }
        )
        
        try:
            if not optimized_graph_path.exists():
                raise FileNotFoundError(f"Optimized graph not found: {optimized_graph_path}")
            
            logger.info(f"[{block_id}] Loading optimized external session from: {optimized_graph_path}")
            logger.debug(f"[{block_id}] External data base directory: {external_data_base_dir}")
            
            # Create session options
            sess_options = ort.SessionOptions()
            # Disable optimization since the graph is already optimized
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
            
            # ===== تنظیمات جدید برای کاهش مصرف حافظه =====
            sess_options.enable_cpu_mem_arena = False    # غیرفعال کردن memory arena
            sess_options.enable_mem_pattern = False      # غیرفعال کردن memory pattern optimization
            sess_options.enable_mem_reuse = False       # فعال کردن استفاده مجدد از حافظه
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL  # اجرای ترتیبی
            # ==============================================
            
            # Enable verbose logging for debugging
            if self.enable_detailed_logging:
                sess_options.log_severity_level = 0  # Verbose
            
            # Load the session
            # ONNX Runtime will automatically resolve external data paths relative to the model file
            session = ort.InferenceSession(
                str(optimized_graph_path),
                sess_options,
                providers=self.execution_providers  
            )
            
            load_time = time.perf_counter() - start_time
            
            # Get session info
            input_names = [inp.name for inp in session.get_inputs()]
            output_names = [out.name for out in session.get_outputs()]
            file_size = optimized_graph_path.stat().st_size
            
            # Store metadata
            self.session_metadata_store[block_id] = {
                'load_time': load_time,
                'input_names': input_names,
                'output_names': output_names,
                'load_method': 'optimized_external_data',
                'load_format': 'optimized_onnx_external',
                'optimized_graph_path': str(optimized_graph_path),
                'file_size': file_size
            }
            
            self._log_event(
                "LOAD_OPTIMIZED_EXTERNAL_SUCCESS",
                {
                    'block_id': block_id,
                    'load_time': load_time,
                    'file_size': file_size,
                    'input_count': len(input_names),
                    'output_count': len(output_names)
                }
            )
            
            logger.info(f"[{block_id}] Successfully loaded optimized external session in {load_time:.3f}s")
            return session, load_time
            
        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            self.stats['failed_loads'] += 1
            
            logger.error(
                f"[{block_id}] Failed to load optimized external session: {type(e).__name__} - {str(e)}",
                exc_info=True
            )
            
            # Log memory info on failure
            if psutil:
                try:
                    virtual_mem = psutil.virtual_memory()
                    logger.error(
                        f"[{block_id}] Memory at optimized external load failure: "
                        f"Available={virtual_mem.available / (1024**2):.2f}MB, "
                        f"UsedPercent={virtual_mem.percent}%"
                    )
                except:
                    pass
            
            self._log_event(
                "LOAD_OPTIMIZED_EXTERNAL_FAILURE",
                {
                    'block_id': block_id,
                    'optimized_graph_path': str(optimized_graph_path),
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'elapsed_time': elapsed_time
                },
                level="ERROR"
            )
            
            return None, elapsed_time
            
        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            self.stats['failed_loads'] += 1
            
            logger.error(
                f"[{block_id}] Failed to load optimized external session: {type(e).__name__} - {str(e)}",
                exc_info=True
            )
            
            # Log memory info on failure
            if psutil:
                try:
                    virtual_mem = psutil.virtual_memory()
                    logger.error(
                        f"[{block_id}] Memory at optimized external load failure: "
                        f"Available={virtual_mem.available / (1024**2):.2f}MB, "
                        f"UsedPercent={virtual_mem.percent}%"
                    )
                except:
                    pass
            
            self._log_event(
                "LOAD_OPTIMIZED_EXTERNAL_FAILURE",
                {
                    'block_id': block_id,
                    'optimized_graph_path': str(optimized_graph_path),
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'elapsed_time': elapsed_time
                },
                level="ERROR"
            )
            
            return None, elapsed_time

    def _load_session_standard_onnx(self, block_id: str) -> Tuple[Optional[ort.InferenceSession], float]:
        """Fallback method to load standard ONNX session"""
        start_time = time.perf_counter()
        onnx_path_str = "N/A"
        
        try:
            onnx_path = self._determine_onnx_path(block_id)
            onnx_path_str = str(onnx_path)

            if not onnx_path.exists():
                logger.error(f"[{block_id}] Standard ONNX file not found at: {onnx_path_str}")
                return None, time.perf_counter() - start_time

            logger.info(f"[{block_id}] Loading standard ONNX session from: {onnx_path_str}")
            
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
            
            # ===== تنظیمات جدید برای کاهش مصرف حافظه =====
            sess_options.enable_cpu_mem_arena = False    # غیرفعال کردن memory arena
            sess_options.enable_mem_pattern = False      # غیرفعال کردن memory pattern optimization
            sess_options.enable_mem_reuse = False       # فعال کردن استفاده مجدد از حافظه
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL  # اجرای ترتیبی
            # ==============================================
            
            session = ort.InferenceSession(
                onnx_path_str,
                sess_options,
                providers=self.execution_providers
            )

            load_time = time.perf_counter() - start_time

            input_names = [inp.name for inp in session.get_inputs()]
            output_names = [out.name for out in session.get_outputs()]
            file_size = onnx_path.stat().st_size

            self.session_metadata_store[block_id] = {
                'load_time': load_time,
                'input_names': input_names,
                'output_names': output_names,
                'load_method': 'standard_onnx',
                'load_format': 'onnx_standard',
                'onnx_path': onnx_path_str,
                'file_size': file_size
            }
            
            logger.info(f"[{block_id}] Successfully loaded standard ONNX session in {load_time:.3f}s")
            self._log_event(
                "LOAD_STANDARD_ONNX_SUCCESS",
                {'block_id': block_id, 'path': onnx_path_str, 'load_time': load_time}
            )
            
            return session, load_time

        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            self.stats['failed_loads'] += 1
            
            logger.error(
                f"[{block_id}] Failed to load standard ONNX session: {type(e).__name__} - {str(e)}",
                exc_info=True
            )
            
            if psutil:
                try:
                    virtual_mem = psutil.virtual_memory()
                    logger.error(
                        f"[{block_id}] Memory at standard load failure: "
                        f"Available={virtual_mem.available / (1024**2):.2f}MB, "
                        f"UsedPercent={virtual_mem.percent}%"
                    )
                except:
                    pass

            self._log_event(
                "LOAD_STANDARD_ONNX_FAILURE",
                {
                    'block_id': block_id,
                    'onnx_path': onnx_path_str,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'elapsed_time': elapsed_time
                },
                level="ERROR"
            )
            
            return None, elapsed_time

        except Exception as e:
            elapsed_time = time.perf_counter() - start_time
            self.stats['failed_loads'] += 1
            
            logger.error(
                f"[{block_id}] Failed to load standard ONNX session: {type(e).__name__} - {str(e)}",
                exc_info=True
            )
            
            if psutil:
                try:
                    virtual_mem = psutil.virtual_memory()
                    logger.error(
                        f"[{block_id}] Memory at standard load failure: "
                        f"Available={virtual_mem.available / (1024**2):.2f}MB, "
                        f"UsedPercent={virtual_mem.percent}%"
                    )
                except:
                    pass

            self._log_event(
                "LOAD_STANDARD_ONNX_FAILURE",
                {
                    'block_id': block_id,
                    'onnx_path': onnx_path_str,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'elapsed_time': elapsed_time
                },
                level="ERROR"
            )
            
            return None, elapsed_time

    def _evict_oldest_session(self) -> Optional[str]:
        """Evicts the oldest session (FIFO with OrderedDict) from warm_sessions"""
        if not self.warm_sessions:
            return None

        # Get the oldest key (first inserted)
        evicted_block_id = next(iter(self.warm_sessions))
        
        logger.info(f"Evicting oldest session for block_id: '{evicted_block_id}'")

        # Remove from all caches
        self.warm_sessions.pop(evicted_block_id, None)
        self.warm_states.pop(evicted_block_id, None)
        self.session_metadata_store.pop(evicted_block_id, None)

        self.stats['cache_evictions'] += 1

        self._log_event(
            "HOMF_CACHE_EVICTION",
            {
                'evicted_block_id': evicted_block_id,
                'remaining_sessions': len(self.warm_sessions)
            }
        )

        # Optionally trigger garbage collection
        if self.enable_detailed_logging:
            gc.collect()
            
        return evicted_block_id

    def get_session_ultra_fast(self, block_id: str) -> Tuple[Optional[ort.InferenceSession], float, Dict[str, Any]]:
        """Get session with ultra-fast loading, with detailed logging for debugging"""
        
        # Initialize method_info and variables
        method_info = {'method': 'unknown', 'attempted_methods': [], 'load_time_sec': 0.0, 'load_format': 'unknown'}
        session_object = None
        actual_load_time = 0.0
        
        # 1. Initial logging
        logger.info(f"[{block_id}] === Starting get_session_ultra_fast ===")
        logger.info(f"[{block_id}] Input block_id: '{block_id}', prefer_homf_format: {self.prefer_homf_format}")
        
        # Check warm cache first
        with self._lock:
            if block_id in self.warm_sessions:
                # --- Warm Cache Hit ---
                time_before_cache_access = time.perf_counter() # زمان دقیق قبل از دسترسی
                
                session_data_from_cache = self.warm_sessions[block_id]
                session_object_from_cache = session_data_from_cache.get('session')
                
                # انتقال آیتم به انتهای OrderedDict برای حفظ ترتیب LRU
                self.warm_sessions.move_to_end(block_id) 
                
                time_taken_for_cache_access_sec = time.perf_counter() - time_before_cache_access
                
                # اطلاعات از زمانی که سشن برای اولین بار (با cold load) به کش اضافه شد
                original_load_time_sec = session_data_from_cache.get('load_time_sec_on_cold_load', 0.0)
                original_load_method = session_data_from_cache.get('load_method_on_cold_load', 'unknown_cached_method')
                original_load_format = session_data_from_cache.get('load_format_on_cold_load', 'unknown_cached_format')

                method_info.update({
                    'method': 'warm_cache_hit',
                    'load_format': 'memory_warm', # نشان می‌دهد از حافظه خوانده شده
                    'load_time_sec': time_taken_for_cache_access_sec, # زمان واقعی دسترسی به کش
                    'original_cold_load_time_sec': original_load_time_sec, # زمان بارگذاری سرد اولیه
                    'original_cold_load_method': original_load_method, # متد بارگذاری سرد اولیه
                    'original_cold_load_format': original_load_format  # فرمت بارگذاری سرد اولیه
                })
                
                self.stats['cache_hits'] = self.stats.get('cache_hits', 0) + 1 # یا 'warm_hits_count'

                logger.info(f"[{block_id}] ✓ HOMF Cache HIT! Method: {method_info['method']}, AccessTime: {time_taken_for_cache_access_sec*1000:.4f}ms, OriginalLoad: {original_load_method} ({original_load_time_sec*1000:.2f}ms)")
                self._log_event(
                    "SESSION_CACHE_HIT", 
                    data={ # کلید data باید باشد
                        'block_id': block_id, 
                        'access_time_ms': round(time_taken_for_cache_access_sec * 1000, 4),
                        'retrieved_session_info': method_info # ارسال کل method_info
                    }
                )
                logger.debug(f"[{block_id}] Final method_info for warm_cache_hit: {method_info}")
                return session_object_from_cache, time_taken_for_cache_access_sec, method_info
        
        # 2. Post-cache check logging
        self.stats['cache_misses'] += 1
        logger.info(f"[{block_id}] Cache miss. prefer_homf_format is {self.prefer_homf_format}. Will attempt optimized load if true.")
        self._log_event("SESSION_CACHE_MISS", {'block_id': block_id, 'prefer_homf': self.prefer_homf_format})
        
        # 3. Try optimized loading if preferred
        if self.prefer_homf_format:
            logger.info(f"[{block_id}] Entering prefer_homf_format branch (prefer_homf_format=True)")
            
            # Get optimized asset paths
            asset_paths = self._get_homf_optimized_asset_paths(block_id)
            
            # Log complete asset_paths content
            logger.debug(f"[{block_id}] asset_paths returned by _get_homf_optimized_asset_paths:")
            for key, value in asset_paths.items():
                logger.debug(f"[{block_id}]   {key}: {value}")
            
            # Check for optimized external data format (skeleton.optimized.onnx with external weights)
            optimized_graph_path = asset_paths.get('optimized_graph_path')
            weights_folder_path = asset_paths.get('weights_folder_path')
            
            # Log the condition check explicitly
            optimized_assets_exist = (
                optimized_graph_path and 
                optimized_graph_path.exists() and 
                weights_folder_path and 
                weights_folder_path.exists() and 
                weights_folder_path.is_dir()
            )
            
            logger.info(f"[{block_id}] Checking for optimized assets: Found all necessary files = {optimized_assets_exist}")
            logger.debug(f"[{block_id}]   optimized_graph_path exists: {optimized_graph_path.exists() if optimized_graph_path else False}")
            logger.debug(f"[{block_id}]   weights_folder_path exists and is_dir: {weights_folder_path.exists() and weights_folder_path.is_dir() if weights_folder_path else False}")
            
            if optimized_assets_exist:
                # Try loading with optimized external data
                logger.info(f"[{block_id}] ✓ Optimized assets found!")
                logger.info(f"[{block_id}] Attempting to load with _load_session_from_optimized_external_data using optimized_graph_path: {optimized_graph_path}")
                
                method_info['attempted_methods'].append('optimized_external_data')
                
                session_candidate, specific_load_time = self._load_session_from_optimized_external_data(
                    block_id, optimized_graph_path, weights_folder_path
                )
                
                logger.info(f"[{block_id}] Result from _load_session_from_optimized_external_data: session={'Valid' if session_candidate else 'None'}, load_time={specific_load_time:.3f}s")
                
                if session_candidate:
                    session_object = session_candidate
                    actual_load_time = specific_load_time
                    method_info.update({
                        'method': 'cold_load_optimized_external',
                        'load_format': 'optimized_onnx_external',
                        'load_time_sec': actual_load_time,
                        'optimized_graph_path': str(optimized_graph_path)
                    })
                    logger.info(f"[{block_id}] ✓ Successfully loaded with optimized external data method")
            else:
                logger.warning(f"[{block_id}] ✗ Optimized HOMF assets not found or incomplete. Skipping _load_session_from_optimized_external_data.")
            
            # 4. Fallback to mmap zero-skeleton if optimized failed or not found
            if session_object is None:
                logger.info(f"[{block_id}] Optimized external data load not successful, checking for mmap zero-skeleton fallback")
                
                # Check for mmap zero-skeleton format
                skeleton_path = asset_paths.get('skeleton_path')
                weights_metadata_path = asset_paths.get('weights_metadata_path')
                
                # Log the condition check for mmap assets
                mmap_assets_exist = (
                    skeleton_path and 
                    skeleton_path.exists() and 
                    weights_folder_path and 
                    weights_folder_path.exists() and 
                    weights_folder_path.is_dir() and
                    weights_metadata_path and 
                    weights_metadata_path.exists()
                )
                
                logger.info(f"[{block_id}] Checking for mmap zero-skeleton assets: Found all necessary files = {mmap_assets_exist}")
                logger.debug(f"[{block_id}]   skeleton_path exists: {skeleton_path.exists() if skeleton_path else False}")
                logger.debug(f"[{block_id}]   weights_metadata_path exists: {weights_metadata_path.exists() if weights_metadata_path else False}")
                
                if mmap_assets_exist:
                    logger.info(f"[{block_id}] ✓ Mmap zero-skeleton assets found!")
                    logger.info(f"[{block_id}] Attempting mmap zero-skeleton load with skeleton_path: {skeleton_path}")
                    
                    method_info['attempted_methods'].append('mmap_zeroskel')
                    
                    session_candidate, specific_load_time = self._load_session_with_mmap_weights(
                        block_id, skeleton_path, weights_metadata_path, weights_folder_path
                    )
                    
                    logger.info(f"[{block_id}] Result from _load_session_with_mmap_weights: session={'Valid' if session_candidate else 'None'}, load_time={specific_load_time:.3f}s")
                    
                    if session_candidate:
                        session_object = session_candidate
                        actual_load_time = specific_load_time
                        method_info.update({
                            'method': 'cold_load_mmap_zeroskel',
                            'load_format': 'onnx_zeroskel_mmap_weights',
                            'load_time_sec': actual_load_time,
                            'skeleton_path': str(skeleton_path)
                        })
                        logger.info(f"[{block_id}] ✓ Successfully loaded with mmap zero-skeleton method")
                else:
                    logger.warning(f"[{block_id}] ✗ Mmap zero-skeleton assets not found or incomplete.")
        else:
            logger.info(f"[{block_id}] prefer_homf_format is False, skipping optimized methods")
        
        # 5. Final fallback to standard ONNX if needed
        if session_object is None:
            logger.info(f"[{block_id}] All optimized methods failed or skipped.")
            logger.info(f"[{block_id}] Fallback: Attempting to load with _load_session_standard_onnx.")
            
            method_info['attempted_methods'].append('standard_onnx')
            
            session_candidate, specific_load_time = self._load_session_standard_onnx(block_id)
            
            logger.info(f"[{block_id}] Result from _load_session_standard_onnx: session={'Valid' if session_candidate else 'None'}, load_time={specific_load_time:.3f}s")
            
            if session_candidate:
                session_object = session_candidate
                actual_load_time = specific_load_time
                method_info.update({
                    'method': 'cold_load_standard_onnx',
                    'load_format': 'standard_onnx',
                    'load_time_sec': actual_load_time
                })
                logger.info(f"[{block_id}] ✓ Successfully loaded with standard ONNX method")
            else:
                method_info.update({
                    'method': 'failed_all_load_attempts',
                    'load_format': 'none'
                })
                logger.error(f"[{block_id}] ✗ Failed to load session using ANY method!")
                self._log_event("SESSION_LOAD_FAILURE_ALL_METHODS", {'block_id': block_id}, level="CRITICAL")
        
        # Add to cache if successful
        if session_object:
            with self._lock:
                # Eviction logic before adding
                while len(self.warm_sessions) >= self.max_warm_sessions and self.max_warm_sessions > 0:
                    evicted_id = self._evict_oldest_session()
                    if not evicted_id:
                        break
                
                # Add new session
                self.warm_sessions[block_id] = {
                    'session': session_object,
                    'load_time': actual_load_time,
                    'method': method_info['method'],
                    'load_format': method_info.get('load_format', 'unknown'),
                    'timestamp': time.time()
                }
                
                logger.info(f"[{block_id}] Added session to warm cache (size: {len(self.warm_sessions)})")
                
                self._log_event(
                    "SESSION_ADDED_TO_WARM_CACHE",
                    {
                        'block_id': block_id,
                        'load_method': method_info['method'],
                        'load_format': method_info.get('load_format', 'unknown'),
                        'load_time_sec': actual_load_time,
                        'warm_cache_size': len(self.warm_sessions)
                    }
                )
        
        # 6. Log final method_info before return
        logger.info(f"[{block_id}] === Completed get_session_ultra_fast ===")
        logger.info(f"[{block_id}] Final result: session={'Valid' if session_object else 'None'}, load_time={actual_load_time:.3f}s")
        logger.debug(f"[{block_id}] Final method_info: {method_info}")
        
        return session_object, actual_load_time, method_info

    def execute_session_with_homf_cache(
        self,
        session_to_run: ort.InferenceSession,
        block_id_for_run: str,
        input_feed_dict_from_caller: Dict[str, np.ndarray],
        requested_output_names: Optional[List[str]]
    ) -> Tuple[Optional[List[np.ndarray]], float]:
        """Execute session with HOMF cache support"""
        inference_duration_sec = -1.0
        outputs_list = None
        shared_inputs_added_to_feed = []
        final_input_feed_for_onnx_run = {}

        start_run_time = time.perf_counter()

        try:
            final_input_feed_for_onnx_run = input_feed_dict_from_caller.copy()
            
            # Add shared inputs from cache if available
            if hasattr(self, 'shared_inputs_cache') and self.shared_inputs_cache:
                required_input_names_for_block = set()
                try:
                    if (self.model_metadata_global and 
                        "block_io_details" in self.model_metadata_global and
                        block_id_for_run in self.model_metadata_global["block_io_details"] and
                        "inputs" in self.model_metadata_global["block_io_details"][block_id_for_run]):
                        
                        for input_spec in self.model_metadata_global["block_io_details"][block_id_for_run]["inputs"]:
                            if isinstance(input_spec, dict) and "name" in input_spec:
                                required_input_names_for_block.add(input_spec["name"])
                except Exception:
                    logger.warning(f"Could not get required inputs for {block_id_for_run}")

                for shared_name, shared_tensor in self.shared_inputs_cache.items():
                    if shared_name in required_input_names_for_block:
                        if shared_name not in final_input_feed_for_onnx_run:
                            final_input_feed_for_onnx_run[shared_name] = shared_tensor
                            shared_inputs_added_to_feed.append(shared_name)
                            logger.debug(f"Block '{block_id_for_run}': Added '{shared_name}' from shared_inputs_cache")
            
            # Execute the session
            outputs_list = session_to_run.run(requested_output_names, final_input_feed_for_onnx_run)
            inference_duration_sec = time.perf_counter() - start_run_time
            self.stats['session_executions'] += 1

            self._log_event(
                "HOMF_SESSION_EXECUTION_SUCCESS",
                {
                    'block_id': block_id_for_run,
                    'inference_time_sec': round(inference_duration_sec, 5),
                    'num_inputs': len(final_input_feed_for_onnx_run),
                    'shared_inputs_added': shared_inputs_added_to_feed,
                    'num_outputs': len(outputs_list) if outputs_list else 0
                }
            )
            
            logger.debug(f"Block '{block_id_for_run}': Session execution successful in {inference_duration_sec:.4f}s")

        except Exception as e:
            inference_duration_sec = time.perf_counter() - start_run_time
            self.stats['session_execution_failures'] += 1
            outputs_list = None
            
            self._log_event(
                "HOMF_SESSION_EXECUTION_FAILURE",
                {
                    'block_id': block_id_for_run,
                    'error_message': str(e),
                    'exception_type': type(e).__name__,
                    'inference_time_at_error_sec': round(inference_duration_sec, 5)
                },
                level="ERROR"
            )
            
            logger.error(f"Block '{block_id_for_run}': Session execution failed: {e}", exc_info=True)
            
        return outputs_list, inference_duration_sec

    def _create_dummy_inputs_for_warmup(self, session: ort.InferenceSession, block_id: str) -> Dict[str, np.ndarray]:
        """Create dummy inputs for session warmup with correct shapes and dtypes"""
        dummy_inputs = {}
        
        for inp in session.get_inputs():
            input_name = inp.name
            input_name_lower = input_name.lower()
            onnx_input_shape = inp.shape
            onnx_input_type_str = str(inp.type).lower()
            
            logger.debug(f"[{block_id}] Processing input '{input_name}' with type: '{inp.type}' and shape: {onnx_input_shape}")
            
            # Determine dtype
            np_dtype_to_use = None
            
            # Known input names
            if any(known in input_name_lower for known in ["input_ids", "attention_mask", "position_ids"]):
                np_dtype_to_use = np.int64
            elif any(pattern in input_name_lower for pattern in ["past_key_values", ".key", ".value", "cache"]):
                if "float16" in onnx_input_type_str:
                    np_dtype_to_use = np.float16
                else:
                    np_dtype_to_use = np.float32
            else:
                # Parse from type string
                dtype_mapping = {
                    "int64": np.int64, "int32": np.int32,
                    "float32": np.float32, "float16": np.float16,
                    "float": np.float32, "fp16": np.float16
                }
                
                for type_key, numpy_dtype in dtype_mapping.items():
                    if type_key in onnx_input_type_str:
                        np_dtype_to_use = numpy_dtype
                        break
                
                if np_dtype_to_use is None:
                    np_dtype_to_use = np.float32
            
            # Process shape
            processed_shape = []
            for dim_idx, dim_val in enumerate(onnx_input_shape):
                if isinstance(dim_val, int) and dim_val > 0:
                    processed_shape.append(dim_val)
                else:
                    # Dynamic dimension
                    if dim_idx == 0:  # Usually batch dimension
                        processed_shape.append(1)
                    elif "past" in input_name_lower and (dim_idx == 2 or "sequence" in str(dim_val).lower()):
                        processed_shape.append(0)  # Empty past sequence
                    else:
                        processed_shape.append(1)  # Default size
            
            if not processed_shape:
                processed_shape = [1]
            
            # Create appropriate dummy values
            try:
                if "input_ids" in input_name_lower:
                    dummy_array = np.ones(processed_shape, dtype=np_dtype_to_use)
                elif "attention_mask" in input_name_lower:
                    dummy_array = np.ones(processed_shape, dtype=np_dtype_to_use)
                elif "position_ids" in input_name_lower:
                    if len(processed_shape) >= 2:
                        dummy_array = np.zeros(processed_shape, dtype=np_dtype_to_use)
                        dummy_array[..., :] = np.arange(processed_shape[-1], dtype=np_dtype_to_use)
                    else:
                        dummy_array = np.zeros(processed_shape, dtype=np_dtype_to_use)
                elif any(pattern in input_name_lower for pattern in ["past_key_values", ".key", ".value", "cache"]):
                    dummy_array = np.zeros(processed_shape, dtype=np_dtype_to_use)
                else:
                    if np.issubdtype(np_dtype_to_use, np.integer):
                        dummy_array = np.ones(processed_shape, dtype=np_dtype_to_use)
                    else:
                        dummy_array = np.random.uniform(0.01, 0.1, processed_shape).astype(np_dtype_to_use)
                
                dummy_inputs[input_name] = dummy_array
                logger.debug(f"[{block_id}] Created dummy input '{input_name}' with shape {dummy_array.shape} and dtype {dummy_array.dtype}")
                
            except Exception as e:
                logger.error(f"[{block_id}] Error creating dummy input for '{input_name}': {e}")
                # Fallback
                try:
                    dummy_inputs[input_name] = np.zeros([1] * len(processed_shape), dtype=np.float32)
                except:
                    raise
        
        logger.info(f"[{block_id}] Created dummy inputs for {len(dummy_inputs)} inputs")
        return dummy_inputs

    async def warm_up_session_async(self, block_id: str) -> bool:
        """Asynchronously warm up a session for the given block_id"""
        def warm_worker_internal() -> bool:
            """Internal synchronous function to perform the actual warmup work"""
            session_warmed_up = None
            overall_load_block_time_sec = 0.0
            specific_load_duration_sec = 0.0
            avg_warmup_run_time_sec = 0.0
            load_method_used = "unknown"
            load_format_used = "unknown"
            successful_runs = 0

            try:
                # Step 1: Load the session using get_session_ultra_fast
                load_start_time = time.perf_counter()
                
                session_candidate, load_time, method_info = self.get_session_ultra_fast(block_id)
                
                if not session_candidate:
                    self.stats['warmup_failures'] += 1
                    self._log_event(
                        "WARMUP_ASYNC_FAILURE_LOAD_SESSION",
                        {"block_id": block_id, "error": "Failed to load session"},
                        level="ERROR"
                    )
                    return False
                
                session_warmed_up = session_candidate
                overall_load_block_time_sec = time.perf_counter() - load_start_time
                specific_load_duration_sec = load_time
                load_method_used = method_info.get('method', 'unknown')
                load_format_used = method_info.get('load_format', 'unknown')
                
                logger.info(f"[{block_id}] Warmup: Session loaded successfully using {load_method_used}")
                
                # Step 2: Create dummy inputs
                logger.info(f"[{block_id}] Warmup: Creating dummy inputs")
                dummy_inputs_for_warmup = self._create_dummy_inputs_for_warmup(session_warmed_up, block_id)
                
                if not dummy_inputs_for_warmup:
                    logger.error(f"[{block_id}] Warmup: Failed to create dummy inputs")
                    self.stats['warmup_failures'] += 1
                    return False

                # Step 3: Perform warmup runs
                num_warmup_runs = 3
                warmup_run_times = []
                
                logger.info(f"[{block_id}] Warmup: Starting {num_warmup_runs} inference runs")
                for i in range(num_warmup_runs):
                    try:
                        run_start = time.perf_counter()
                        _ = session_warmed_up.run(None, dummy_inputs_for_warmup)
                        run_duration = time.perf_counter() - run_start
                        warmup_run_times.append(run_duration)
                        successful_runs += 1
                        logger.debug(f"[{block_id}] Warmup run {i+1}/{num_warmup_runs} completed in {run_duration:.4f}s")
                    except Exception as e:
                        logger.warning(f"[{block_id}] Warmup run {i+1}/{num_warmup_runs} failed: {e}")
                
                if successful_runs == 0:
                    self.stats['warmup_failures'] += 1
                    self._log_event(
                        "WARMUP_ASYNC_FAILURE_RUN",
                        {"block_id": block_id, "error": f"All {num_warmup_runs} warmup runs failed"},
                        level="ERROR"
                    )
                    return False
                
                avg_warmup_run_time_sec = sum(warmup_run_times) / len(warmup_run_times) if warmup_run_times else 0.0

                # Step 4: Store the warmed state
                with self._lock:
                    current_timestamp = time.time()
                    self.warm_states[block_id] = {
                        "session": session_warmed_up,
                        "load_time_sec": overall_load_block_time_sec,
                        "specific_model_load_time_sec": specific_load_duration_sec,
                        "avg_warmup_run_time_sec": avg_warmup_run_time_sec,
                        "load_method_used": load_method_used,
                        "load_format_used": load_format_used,
                        "timestamp": current_timestamp,
                        "warmup_runs_completed": successful_runs
                    }
                
                self.stats['warmup_successes'] += 1
                self._log_event(
                    "WARMUP_ASYNC_SUCCESS",
                    {
                        "block_id": block_id,
                        "overall_load_block_time_sec": round(overall_load_block_time_sec, 5),
                        "specific_model_load_time_sec": round(specific_load_duration_sec, 5),
                        "avg_warmup_run_time_sec": round(avg_warmup_run_time_sec, 5),
                        "load_method_used": load_method_used,
                        "load_format_used": load_format_used,
                        "num_warmup_runs_completed": successful_runs
                    }
                )
                
                logger.info(
                    f"[{block_id}] Warmup completed successfully. "
                    f"OverallLoad: {overall_load_block_time_sec:.3f}s, "
                    f"ModelLoad: {specific_load_duration_sec:.3f}s, "
                    f"AvgRun: {avg_warmup_run_time_sec:.4f}s, "
                    f"Method: {load_method_used}, Format: {load_format_used}"
                )
                return True

            except Exception as e:
                logger.error(f"[{block_id}] Unexpected error in warmup: {type(e).__name__} - {e}", exc_info=True)
                self.stats['warmup_failures'] += 1
                self._log_event(
                    "WARMUP_ASYNC_FAILURE_UNEXPECTED",
                    {
                        "block_id": block_id,
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    level="CRITICAL"
                )
                return False

        # Execute the warmup worker asynchronously
        try:
            if hasattr(asyncio, 'to_thread'):
                return await asyncio.to_thread(warm_worker_internal)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, warm_worker_internal)
        except Exception as e:
            logger.error(f"[{block_id}] Error launching async warmup task: {e}", exc_info=True)
            self.stats['warmup_failures'] += 1
            return False