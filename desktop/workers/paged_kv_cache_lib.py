# networked_distributed_inference/paged_kv_cache_lib.py
import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from collections import OrderedDict

# تغییر در import: چون custom_logging.py در همان پوشه است و ما model_node.py را مستقیم اجرا می‌کنیم
from custom_logging import NODE_ID_FOR_LOGGING_HOLDER # <--- نقطه اول حذف شد


# --- BEGIN Paged KV Cache Class Definitions ---
# این بخش شامل تمام کدهای کلاس‌های KV Cache شماست که از model_node.py منتقل می‌شود.

class KVCachePage:
    def __init__(self, page_id: int, capacity_tokens: int, num_heads: int, head_dim: int, dtype: np.dtype, batch_size: int = 1):
        self.page_id = page_id
        self.capacity_tokens = capacity_tokens
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.dtype = dtype
        self.batch_size = batch_size
        self.num_tokens_filled = 0
        self.key_data = np.zeros((batch_size, num_heads, capacity_tokens, head_dim), dtype=self.dtype)
        self.value_data = np.zeros((batch_size, num_heads, capacity_tokens, head_dim), dtype=self.dtype)

        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "KVPageNodeUnset")
        current_session_id = NODE_ID_FOR_LOGGING_HOLDER.get("current_session_id", "N/A_KV_Page_Ctx")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        logging.debug(
            f"KVCachePage {self.page_id}: Initialized.",
            extra={"custom_extra_fields": {
                "event_type": "KV_PAGE_CREATED",
                "node_id": current_node_id,
                "session_id": current_session_id,
                "step": current_step,
                "data": {
                    "kv_page_id": self.page_id,
                    "kv_page_capacity_tokens": self.capacity_tokens,
                    "kv_page_num_heads": self.num_heads,
                    "kv_page_head_dim": self.head_dim,
                    "kv_page_dtype": str(self.dtype),
                    "kv_page_batch_size": self.batch_size
                }
            }}
        )

    def is_full(self) -> bool:
        return self.num_tokens_filled >= self.capacity_tokens

    def get_remaining_capacity(self) -> int:
        return self.capacity_tokens - self.num_tokens_filled

    def reset(self):
        prev_filled_tokens = self.num_tokens_filled
        self.num_tokens_filled = 0
        self.key_data.fill(0)
        self.value_data.fill(0)

        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "KVPageNodeUnset")
        current_session_id = NODE_ID_FOR_LOGGING_HOLDER.get("current_session_id", "N/A_KV_Page_Ctx")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        logging.debug(
            f"KVCachePage {self.page_id}: Reset.",
            extra={"custom_extra_fields": {
                "event_type": "KV_PAGE_RESET",
                "node_id": current_node_id,
                "session_id": current_session_id,
                "step": current_step,
                "data": {
                    "kv_page_id": self.page_id,
                    "kv_tokens_filled_before_reset": prev_filled_tokens
                }
            }}
        )

    def append_kv_data(self, key_tokens_segment: np.ndarray, value_tokens_segment: np.ndarray) -> int:
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "KVPageNodeUnset")
        current_session_id = NODE_ID_FOR_LOGGING_HOLDER.get("current_session_id", "N/A_KV_Page_Ctx")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        if self.is_full():
            return 0

        num_tokens_to_append = key_tokens_segment.shape[2] 
        tokens_can_fit = min(num_tokens_to_append, self.get_remaining_capacity())

        if tokens_can_fit <= 0:
            return 0
        
        logging.debug(
            f"KVCachePage {self.page_id}: Attempting to append {tokens_can_fit} tokens (requested: {num_tokens_to_append}).",
            extra={"custom_extra_fields": {
                "event_type": "KV_PAGE_APPEND_ATTEMPT",
                "node_id": current_node_id,
                "session_id": current_session_id,
                "step": current_step,
                "data": {
                    "kv_page_id": self.page_id,
                    "kv_page_current_filled_tokens": self.num_tokens_filled,
                    "kv_page_remaining_capacity_tokens": self.get_remaining_capacity(),
                    "kv_append_requested_tokens_count": num_tokens_to_append,
                    "kv_append_can_fit_tokens_count": tokens_can_fit,
                    "kv_key_segment_shape": list(key_tokens_segment.shape),
                    "kv_value_segment_shape": list(value_tokens_segment.shape),
                    "kv_key_segment_dtype": str(key_tokens_segment.dtype),
                    "kv_value_segment_dtype": str(value_tokens_segment.dtype)
                }
            }}
        )

        target_slice = slice(self.num_tokens_filled, self.num_tokens_filled + tokens_can_fit)
        source_slice = slice(0, tokens_can_fit)

        key_to_store = key_tokens_segment[:, :, source_slice, :]
        if key_to_store.dtype != self.dtype:
            key_to_store = key_to_store.astype(self.dtype, copy=False)

        value_to_store = value_tokens_segment[:, :, source_slice, :]
        if value_to_store.dtype != self.dtype:
            value_to_store = value_to_store.astype(self.dtype, copy=False)

        self.key_data[:, :, target_slice, :] = key_to_store
        self.value_data[:, :, target_slice, :] = value_to_store
        self.num_tokens_filled += tokens_can_fit

        logging.debug(
            f"KVCachePage {self.page_id}: Appended {tokens_can_fit} tokens. Now filled: {self.num_tokens_filled}/{self.capacity_tokens}.",
            extra={"custom_extra_fields": {
                "event_type": "KV_PAGE_APPEND_SUCCESS",
                "node_id": current_node_id,
                "session_id": current_session_id,
                "step": current_step,
                "data": {
                    "kv_page_id": self.page_id,
                    "kv_tokens_appended_count": tokens_can_fit,
                    "kv_page_tokens_filled_after_append": self.num_tokens_filled,
                    "kv_page_total_capacity_tokens": self.capacity_tokens
                }
            }}
        )
        return tokens_can_fit


class PagedKVCacheManager:
    def __init__(self, initial_pages: int, page_capacity: int, num_kv_heads: int, head_dim: int, dtype: np.dtype, batch_size: int = 1):
        self.page_capacity = page_capacity
        self.num_kv_heads = num_kv_heads
        self.head_dim = head_dim
        self.dtype = dtype
        self.batch_size = batch_size
        self._free_pages_pool: List[KVCachePage] = []
        self._allocated_pages_map: Dict[int, KVCachePage] = {}
        self._next_page_id_counter = 0
        
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "MgrNodeUnsetOnInit")
        init_session_id = "N/A_Mgr_Global_Init"
        init_step = -1

        for i in range(initial_pages):
            self._add_new_page_to_pool_internal(page_id_override=i)
        self._next_page_id_counter = initial_pages 
        
        logging.info(
            f"PagedKVCacheManager: Initialized. Free pages in pool: {len(self._free_pages_pool)}.",
            extra={"custom_extra_fields": {
                "event_type": "KV_PAGE_MANAGER_INITIALIZED",
                "node_id": current_node_id,
                "session_id": init_session_id,
                "step": init_step,
                "data": {
                    "kv_initial_free_pages_count": len(self._free_pages_pool),
                    "kv_page_capacity_tokens_config": self.page_capacity,
                    "kv_num_heads_config": self.num_kv_heads,
                    "kv_head_dim_config": self.head_dim,
                    "kv_dtype_config": str(self.dtype),
                    "kv_batch_size_config": self.batch_size,
                    "kv_next_page_id_to_be_assigned": self._next_page_id_counter
                }
            }}
        )

    def _add_new_page_to_pool_internal(self, page_id_override: Optional[int] = None):
        pid_to_create = page_id_override if page_id_override is not None else self._next_page_id_counter
        if page_id_override is None:
            self._next_page_id_counter += 1
        
        new_page = KVCachePage(
            pid_to_create, self.page_capacity, self.num_kv_heads,
            self.head_dim, self.dtype, self.batch_size
        )
        self._free_pages_pool.append(new_page)

    def allocate_page(self) -> Optional[KVCachePage]:
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "MgrNodeUnsetOnAlloc")
        current_session_id = NODE_ID_FOR_LOGGING_HOLDER.get("current_session_id", "N/A_Mgr_Alloc_Ctx")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)
        
        base_alloc_data = {
            "kv_mgr_free_pages_before_alloc": len(self._free_pages_pool),
            "kv_mgr_allocated_pages_count_before_alloc": len(self._allocated_pages_map),
        }

        if not self._free_pages_pool:
            page_id_attempting_dynamic_alloc = self._next_page_id_counter
            logging.warning(
                f"PagedKVCacheManager: Pool empty. Attempting dynamic allocation for new page ID {page_id_attempting_dynamic_alloc}.",
                extra={"custom_extra_fields": {
                    "event_type": "KV_MANAGER_POOL_EMPTY_DYNAMIC_ALLOC_ATTEMPT",
                    "node_id": current_node_id,
                    "session_id": current_session_id,
                    "step": current_step,
                    "data": {**base_alloc_data, "kv_page_id_to_create_dynamically": page_id_attempting_dynamic_alloc}
                }}
            )
            self._add_new_page_to_pool_internal() 
            if not self._free_pages_pool:
                logging.error(
                    "PagedKVCacheManager: CRITICAL - Dynamic allocation FAILED. Pool remains empty.",
                    extra={"custom_extra_fields": {
                        "event_type": "KV_MANAGER_DYNAMIC_ALLOC_FAILURE_CRITICAL",
                        "node_id": current_node_id,
                        "session_id": current_session_id,
                        "step": current_step,
                        "data": base_alloc_data
                    }}
                )
                return None
        
        page_to_allocate = self._free_pages_pool.pop(0)
        page_to_allocate.reset() 
        self._allocated_pages_map[page_to_allocate.page_id] = page_to_allocate
        
        logging.debug(
            f"PagedKVCacheManager: Allocated page {page_to_allocate.page_id}. Pool size after: {len(self._free_pages_pool)}.",
            extra={"custom_extra_fields": {
                "event_type": "KV_MANAGER_PAGE_ALLOCATED_SUCCESS",
                "node_id": current_node_id,
                "session_id": current_session_id,
                "step": current_step,
                "data": {
                    **base_alloc_data, 
                    "kv_allocated_page_id": page_to_allocate.page_id,
                    "kv_mgr_free_pages_after_alloc": len(self._free_pages_pool),
                    "kv_mgr_total_allocated_pages_after_alloc": len(self._allocated_pages_map)
                }
            }}
        )
        return page_to_allocate

    def free_page(self, page_id: int):
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "MgrNodeUnsetOnFree")
        current_session_id = NODE_ID_FOR_LOGGING_HOLDER.get("current_session_id", "N/A_Mgr_Free_Ctx")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        base_free_data = {
            "kv_page_id_to_free": page_id,
            "kv_mgr_free_pages_before_free": len(self._free_pages_pool),
            "kv_mgr_allocated_pages_count_before_free": len(self._allocated_pages_map),
        }

        if page_id in self._allocated_pages_map:
            page_to_free = self._allocated_pages_map.pop(page_id)
            page_to_free.reset() 
            self._free_pages_pool.append(page_to_free)
            logging.debug(
                f"PagedKVCacheManager: Freed page {page_id}. Pool size after: {len(self._free_pages_pool)}.",
                extra={"custom_extra_fields": {
                    "event_type": "KV_MANAGER_PAGE_FREED_SUCCESS",
                    "node_id": current_node_id,
                    "session_id": current_session_id,
                    "step": current_step,
                    "data": {
                        **base_free_data,
                        "kv_mgr_free_pages_after_free": len(self._free_pages_pool),
                        "kv_mgr_total_allocated_pages_after_free": len(self._allocated_pages_map)
                    }
                }}
            )
        else:
            logging.warning(
                f"PagedKVCacheManager: Attempted to free non-allocated or unknown page_id {page_id}.",
                extra={"custom_extra_fields": {
                    "event_type": "KV_MANAGER_FREE_UNKNOWN_PAGE_WARNING",
                    "node_id": current_node_id,
                    "session_id": current_session_id,
                    "step": current_step,
                    "data": base_free_data
                }}
            )

    def get_physical_page(self, page_id: int) -> Optional[KVCachePage]:
        return self._allocated_pages_map.get(page_id)


class KVCacheLayerStorage:
    def __init__(self, global_layer_idx: int, page_manager: PagedKVCacheManager, session_id_for_log_context: str):
        self.global_layer_idx = global_layer_idx
        self.page_manager = page_manager
        self.active_page_ids: List[int] = []
        self.total_tokens_stored = 0
        self.log_context_session_id = session_id_for_log_context

        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "LayerStoreNodeUnset")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        logging.debug(
            f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id}: Initialized.",
            extra={"custom_extra_fields": {
                "event_type": "KV_LAYER_STORAGE_INITIALIZED",
                "node_id": current_node_id,
                "session_id": self.log_context_session_id,
                "step": current_step,
                "data": {
                    "kv_layer_idx": self.global_layer_idx,
                    "kv_associated_page_manager_instance_id": id(self.page_manager)
                }
            }}
        )

    def reset(self):
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "LayerStoreNodeUnset")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)
        
        pages_to_free_count = len(self.active_page_ids)
        tokens_stored_before_reset = self.total_tokens_stored

        logging.info(
            f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id}: Reset initiated. Freeing {pages_to_free_count} pages.",
            extra={"custom_extra_fields": {
                "event_type": "KV_LAYER_STORAGE_RESET_INITIATED",
                "node_id": current_node_id,
                "session_id": self.log_context_session_id,
                "step": current_step,
                "data": {
                    "kv_layer_idx": self.global_layer_idx,
                    "kv_active_pages_count_before_reset": pages_to_free_count,
                    "kv_total_tokens_stored_before_reset": tokens_stored_before_reset
                }
            }}
        )

        for page_id in self.active_page_ids:
            self.page_manager.free_page(page_id)
        self.active_page_ids.clear()
        self.total_tokens_stored = 0

        logging.info(
            f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id}: Reset completed. Tokens stored: {self.total_tokens_stored}.",
            extra={"custom_extra_fields": {
                "event_type": "KV_LAYER_STORAGE_RESET_COMPLETED",
                "node_id": current_node_id,
                "session_id": self.log_context_session_id,
                "step": current_step,
                "data": {
                    "kv_layer_idx": self.global_layer_idx,
                    "kv_freed_pages_count": pages_to_free_count,
                    "kv_total_tokens_stored_after_reset": self.total_tokens_stored
                }
            }}
        )

    def store_kv_tokens(self, key_tensor_to_add: np.ndarray, value_tensor_to_add: np.ndarray):
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "LayerStoreNodeUnset")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        num_tokens_requested_to_store = key_tensor_to_add.shape[2]
        
        base_store_data = {
            "kv_layer_idx": self.global_layer_idx,
            "kv_input_tokens_to_store_count": num_tokens_requested_to_store,
            "kv_key_input_shape": list(key_tensor_to_add.shape),
            "kv_value_input_shape": list(value_tensor_to_add.shape),
            "kv_key_input_dtype": str(key_tensor_to_add.dtype),
            "kv_value_input_dtype": str(value_tensor_to_add.dtype),
            "kv_layer_tokens_before_store": self.total_tokens_stored,
            "kv_layer_active_pages_before_store": len(self.active_page_ids)
        }

        logging.debug(
            f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id} St:{current_step}: store_kv_tokens called for {num_tokens_requested_to_store} tokens.",
            extra={"custom_extra_fields": {
                "event_type": "KV_LAYER_STORAGE_STORE_CALLED",
                "node_id": current_node_id,
                "session_id": self.log_context_session_id,
                "step": current_step,
                "data": base_store_data
            }}
        )

        if num_tokens_requested_to_store == 0:
            logging.debug(
                f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id} St:{current_step}: store_kv_tokens called with 0 tokens to store. No operation.",
                extra={"custom_extra_fields": {"event_type": "KV_LAYER_STORAGE_STORE_NO_TOKENS", "node_id": current_node_id, "session_id": self.log_context_session_id, "step": current_step, "data": base_store_data}}
            )
            return

        tokens_remaining_to_write_from_input = num_tokens_requested_to_store
        current_source_tensor_offset = 0
        pages_newly_allocated_count = 0
        
        if self.active_page_ids:
            last_page_id_in_layer = self.active_page_ids[-1]
            page_instance_to_fill = self.page_manager.get_physical_page(last_page_id_in_layer)
            if page_instance_to_fill and not page_instance_to_fill.is_full():
                tokens_can_append_to_existing = min(tokens_remaining_to_write_from_input, page_instance_to_fill.get_remaining_capacity())
                if tokens_can_append_to_existing > 0:
                    key_segment = key_tensor_to_add[:, :, current_source_tensor_offset : current_source_tensor_offset + tokens_can_append_to_existing, :]
                    value_segment = value_tensor_to_add[:, :, current_source_tensor_offset : current_source_tensor_offset + tokens_can_append_to_existing, :]
                    appended_count_val = page_instance_to_fill.append_kv_data(key_segment, value_segment)
                    current_source_tensor_offset += appended_count_val
                    tokens_remaining_to_write_from_input -= appended_count_val
        
        safety_loop_iterations = 0
        max_loops_safety_break = num_tokens_requested_to_store + 5 

        while tokens_remaining_to_write_from_input > 0 and safety_loop_iterations < max_loops_safety_break:
            safety_loop_iterations += 1
            new_page_instance = self.page_manager.allocate_page()
            if not new_page_instance:
                logging.error(
                    f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id} St:{current_step}: CRITICAL - PageManager FAILED to allocate page.",
                    extra={"custom_extra_fields": {
                        "event_type": "KV_LAYER_STORAGE_STORE_ALLOC_PAGE_FAILURE",
                        "node_id": current_node_id, "session_id": self.log_context_session_id, "step": current_step,
                        "data": {**base_store_data, "kv_tokens_remaining_unwritten_at_fail": tokens_remaining_to_write_from_input}
                    }}
                )
                break 
            
            self.active_page_ids.append(new_page_instance.page_id)
            pages_newly_allocated_count += 1
            tokens_can_append_to_new_page = min(tokens_remaining_to_write_from_input, new_page_instance.capacity_tokens)
            
            key_segment_new = key_tensor_to_add[:, :, current_source_tensor_offset : current_source_tensor_offset + tokens_can_append_to_new_page, :]
            value_segment_new = value_tensor_to_add[:, :, current_source_tensor_offset : current_source_tensor_offset + tokens_can_append_to_new_page, :]
            appended_count_new_val = new_page_instance.append_kv_data(key_segment_new, value_segment_new)
            current_source_tensor_offset += appended_count_new_val
            tokens_remaining_to_write_from_input -= appended_count_new_val

        tokens_actually_written_this_call = num_tokens_requested_to_store - tokens_remaining_to_write_from_input
        self.total_tokens_stored += tokens_actually_written_this_call
        
        event_type_final = "KV_LAYER_STORAGE_STORE_SUCCESS"
        if tokens_remaining_to_write_from_input > 0:
            event_type_final = "KV_LAYER_STORAGE_STORE_INCOMPLETE"
            logging.warning(
                f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id} St:{current_step}: Store incomplete. {tokens_remaining_to_write_from_input} tokens remained unwritten.",
                extra={"custom_extra_fields": {
                    "event_type": "KV_LAYER_STORAGE_STORE_INCOMPLETE_DETAILS",
                    "node_id": current_node_id, "session_id": self.log_context_session_id, "step": current_step,
                    "data": {**base_store_data, "kv_tokens_unwritten_count": tokens_remaining_to_write_from_input, "kv_tokens_written_count": tokens_actually_written_this_call}
                }}
            )

        logging.debug(
            f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id} St:{current_step}: Store finished. Stored: {tokens_actually_written_this_call}. Total in layer: {self.total_tokens_stored}.",
            extra={"custom_extra_fields": {
                "event_type": event_type_final,
                "node_id": current_node_id,
                "session_id": self.log_context_session_id,
                "step": current_step,
                "data": {
                    **base_store_data,
                    "kv_tokens_actually_stored_this_call": tokens_actually_written_this_call,
                    "kv_layer_total_tokens_after_store": self.total_tokens_stored,
                    "kv_layer_active_pages_after_store": len(self.active_page_ids),
                    "kv_pages_newly_allocated_this_call": pages_newly_allocated_count,
                    "kv_tokens_remaining_unwritten_at_end": tokens_remaining_to_write_from_input
                }
            }}
        )

    def retrieve_kv_tensors(self, length_to_retrieve: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "LayerStoreNodeUnset")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        effective_length_to_retrieve: int
        if length_to_retrieve is None: 
            effective_length_to_retrieve = self.total_tokens_stored
        elif length_to_retrieve == 0: 
            effective_length_to_retrieve = 0
        else: 
            effective_length_to_retrieve = min(length_to_retrieve, self.total_tokens_stored)

        base_retrieve_data = {
            "kv_layer_idx": self.global_layer_idx,
            "kv_retrieve_requested_length_str": str(length_to_retrieve),
            "kv_retrieve_effective_length": effective_length_to_retrieve,
            "kv_layer_total_tokens_at_retrieve_time": self.total_tokens_stored,
            "kv_layer_active_pages_count_at_retrieve_time": len(self.active_page_ids)
        }
        logging.debug(
            f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id} St:{current_step}: retrieve_kv_tensors called. ReqLen: {length_to_retrieve}, EffLen: {effective_length_to_retrieve}.",
            extra={"custom_extra_fields": {
                "event_type": "KV_LAYER_STORAGE_RETRIEVE_CALLED",
                "node_id": current_node_id,
                "session_id": self.log_context_session_id,
                "step": current_step,
                "data": base_retrieve_data
            }}
        )

        pm_batch_size = self.page_manager.batch_size
        pm_num_heads = self.page_manager.num_kv_heads
        pm_head_dim = self.page_manager.head_dim
        pm_dtype = self.page_manager.dtype 

        if effective_length_to_retrieve == 0:
            empty_key = np.empty((pm_batch_size, pm_num_heads, 0, pm_head_dim), dtype=pm_dtype)
            empty_value = np.empty((pm_batch_size, pm_num_heads, 0, pm_head_dim), dtype=pm_dtype)
            logging.debug(
                f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id} St:{current_step}: Retrieving 0 tokens, returning empty tensors.",
                extra={"custom_extra_fields": {
                    "event_type": "KV_LAYER_STORAGE_RETRIEVE_EMPTY_SUCCESS",
                    "node_id": current_node_id, "session_id": self.log_context_session_id, "step": current_step,
                    "data": {**base_retrieve_data, "kv_key_output_shape": list(empty_key.shape), "kv_value_output_shape": list(empty_value.shape)}
                }}
            )
            return empty_key, empty_value

        key_parts_list: List[np.ndarray] = []
        value_parts_list: List[np.ndarray] = []
        tokens_gathered_count = 0

        for page_id_val in self.active_page_ids:
            if tokens_gathered_count >= effective_length_to_retrieve:
                break 
            
            page_instance = self.page_manager.get_physical_page(page_id_val)
            if not page_instance or page_instance.num_tokens_filled == 0:
                continue

            tokens_to_get_from_this_page_val = min(page_instance.num_tokens_filled, effective_length_to_retrieve - tokens_gathered_count)
            if tokens_to_get_from_this_page_val <= 0:
                continue
            
            key_segment_from_page = page_instance.key_data[:, :, :tokens_to_get_from_this_page_val, :]
            if key_segment_from_page.dtype != pm_dtype: key_segment_from_page = key_segment_from_page.astype(pm_dtype, copy=False)
            key_parts_list.append(key_segment_from_page)

            value_segment_from_page = page_instance.value_data[:, :, :tokens_to_get_from_this_page_val, :]
            if value_segment_from_page.dtype != pm_dtype: value_segment_from_page = value_segment_from_page.astype(pm_dtype, copy=False)
            value_parts_list.append(value_segment_from_page)
            
            tokens_gathered_count += tokens_to_get_from_this_page_val

        final_retrieved_key = np.concatenate(key_parts_list, axis=2) if key_parts_list else np.empty((pm_batch_size, pm_num_heads, 0, pm_head_dim), dtype=pm_dtype)
        final_retrieved_value = np.concatenate(value_parts_list, axis=2) if value_parts_list else np.empty((pm_batch_size, pm_num_heads, 0, pm_head_dim), dtype=pm_dtype)

        event_type_final_retrieve = "KV_LAYER_STORAGE_RETRIEVE_SUCCESS"
        if tokens_gathered_count != effective_length_to_retrieve:
            event_type_final_retrieve = "KV_LAYER_STORAGE_RETRIEVE_LENGTH_MISMATCH"
            logging.warning(
                f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id} St:{current_step}: Retrieve length mismatch. Gathered {tokens_gathered_count}, expected {effective_length_to_retrieve}.",
                extra={"custom_extra_fields": {
                    "event_type": "KV_LAYER_STORAGE_RETRIEVE_MISMATCH_DETAILS",
                    "node_id": current_node_id, "session_id": self.log_context_session_id, "step": current_step,
                    "data": {**base_retrieve_data, "kv_tokens_actually_gathered_count": tokens_gathered_count}
                }}
            )
        
        logging.debug(
            f"KVCacheLayerStorage L{self.global_layer_idx} S:{self.log_context_session_id} St:{current_step}: Retrieve finished. Gathered {tokens_gathered_count} tokens. Key shape: {final_retrieved_key.shape}.",
            extra={"custom_extra_fields": {
                "event_type": event_type_final_retrieve,
                "node_id": current_node_id,
                "session_id": self.log_context_session_id,
                "step": current_step,
                "data": {
                    **base_retrieve_data,
                    "kv_tokens_actually_gathered_count": tokens_gathered_count,
                    "kv_key_output_shape": list(final_retrieved_key.shape),
                    "kv_value_output_shape": list(final_retrieved_value.shape),
                    "kv_retrieved_tensors_dtype": str(final_retrieved_key.dtype)
                }
            }}
        )
        return final_retrieved_key, final_retrieved_value


class SessionPagedKVCache:
    def __init__(self, session_id: str, assigned_global_layer_indices: List[int], page_manager: PagedKVCacheManager):
        self.session_id = session_id
        self.assigned_global_layer_indices = assigned_global_layer_indices
        self.page_manager = page_manager
        
        self.layer_caches: Dict[int, KVCacheLayerStorage] = {
            global_idx: KVCacheLayerStorage(global_idx, self.page_manager, self.session_id)
            for global_idx in self.assigned_global_layer_indices
        }
        
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "SessKVNodeUnset")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1) 

        logging.info(
            f"SessionPagedKVCache S:{self.session_id}: Initialized. Manages layers: {self.assigned_global_layer_indices}.",
            extra={"custom_extra_fields": {
                "event_type": "PAGED_KV_SESSION_CACHE_INITIALIZED",
                "node_id": current_node_id,
                "session_id": self.session_id,
                "step": current_step,
                "data": {
                    "kv_session_assigned_layer_indices": self.assigned_global_layer_indices,
                    "kv_session_num_managed_layers_on_node": len(self.assigned_global_layer_indices),
                    "kv_session_page_manager_instance_id": id(self.page_manager)
                }
            }}
        )

    def store_kv_for_layer(self, global_layer_idx: int, present_key_to_add: np.ndarray, present_value_to_add: np.ndarray):
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "SessKVNodeUnset")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        if global_layer_idx not in self.layer_caches:
            logging.error(
                f"SessionPagedKVCache S:{self.session_id}: Attempt to STORE for unmanaged layer {global_layer_idx}.",
                extra={"custom_extra_fields": {
                    "event_type": "PAGED_KV_SESSION_STORE_UNMANAGED_LAYER_ERROR",
                    "node_id": current_node_id, 
                    "session_id": self.session_id, 
                    "step": current_step,
                    "data": {"requested_layer_idx": global_layer_idx, "kv_session_managed_layer_indices_on_node": self.assigned_global_layer_indices}
                }}
            )
            raise ValueError(f"Layer {global_layer_idx} not managed by SessionPagedKVCache for session {self.session_id} on this node.")
        
        self.layer_caches[global_layer_idx].store_kv_tokens(present_key_to_add, present_value_to_add)

    def retrieve_kv_for_layer(self, global_layer_idx: int, length_to_retrieve: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "SessKVNodeUnset")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        if global_layer_idx not in self.layer_caches:
            logging.warning(
                f"SessionPagedKVCache S:{self.session_id}: Attempt to RETRIEVE for unmanaged layer {global_layer_idx}. Returning empty.",
                extra={"custom_extra_fields": {
                    "event_type": "PAGED_KV_SESSION_RETRIEVE_UNMANAGED_LAYER_WARNING",
                    "node_id": current_node_id, 
                    "session_id": self.session_id, 
                    "step": current_step,
                    "data": {"requested_layer_idx": global_layer_idx, "kv_session_managed_layer_indices_on_node": self.assigned_global_layer_indices, "requested_retrieve_length_str": str(length_to_retrieve)}
                }}
            )
            pm_batch_size = self.page_manager.batch_size
            pm_num_heads = self.page_manager.num_kv_heads
            pm_head_dim = self.page_manager.head_dim
            pm_dtype = self.page_manager.dtype 
            return (np.empty((pm_batch_size, pm_num_heads, 0, pm_head_dim), dtype=pm_dtype), 
                    np.empty((pm_batch_size, pm_num_heads, 0, pm_head_dim), dtype=pm_dtype))
        
        return self.layer_caches[global_layer_idx].retrieve_kv_tensors(length_to_retrieve)

    def get_lightweight_kv_metadata(self) -> Dict[str, Any]:
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "SessKVNodeUnset")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1)

        total_tokens_managed_by_session_on_node = 0
        total_active_pages_for_session_on_node = 0
        
        for layer_idx, layer_cache_instance in self.layer_caches.items():
            if layer_idx in self.assigned_global_layer_indices:
                total_tokens_managed_by_session_on_node += layer_cache_instance.total_tokens_stored
                total_active_pages_for_session_on_node += len(layer_cache_instance.active_page_ids)

        generated_metadata = {
            "kv_meta_source_node_id": current_node_id,
            "kv_meta_session_id": self.session_id,
            "kv_meta_step": current_step,
            "kv_meta_total_tokens_on_node_for_session": total_tokens_managed_by_session_on_node,
            "kv_meta_total_active_pages_on_node_for_session": total_active_pages_for_session_on_node,
        }
        
        logging.debug(
            f"SessionPagedKVCache S:{self.session_id}: Generated lightweight KV metadata. Tokens: {total_tokens_managed_by_session_on_node}, Pages: {total_active_pages_for_session_on_node}.",
            extra={"custom_extra_fields": {
                "event_type": "PAGED_KV_SESSION_METADATA_GENERATED",
                "node_id": current_node_id, 
                "session_id": self.session_id, 
                "step": current_step,
                "data": generated_metadata
            }}
        )
        return generated_metadata

    def reset_for_new_prompt(self):
        current_node_id = NODE_ID_FOR_LOGGING_HOLDER.get("id", "SessKVNodeUnset")
        current_step = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", 0)

        logging.info(
            f"SessionPagedKVCache S:{self.session_id}: Initiating reset for new prompt (Step: {current_step}).",
            extra={"custom_extra_fields": {
                "event_type": "PAGED_KV_SESSION_FULL_RESET_INITIATED",
                "node_id": current_node_id,
                "session_id": self.session_id,
                "step": current_step, 
                "data": {"kv_session_num_layers_to_reset_on_node": len(self.layer_caches), "kv_session_managed_layer_indices_on_node_for_reset": self.assigned_global_layer_indices}
            }}
        )
        for layer_storage_instance in self.layer_caches.values():
            layer_storage_instance.reset()
        
        logging.info(
            f"SessionPagedKVCache S:{self.session_id}: Full reset for new prompt completed.",
            extra={"custom_extra_fields": {
                "event_type": "PAGED_KV_SESSION_FULL_RESET_COMPLETED",
                "node_id": current_node_id,
                "session_id": self.session_id,
                "step": current_step,
                "data": {}
            }}
        )

# --- END Paged KV Cache Class Definitions ---