# utils/serialization_utils.py
"""
Serialization Utilities for TikTrue Platform

This module provides utilities for serializing and deserializing NumPy tensors to JSON-compatible formats.
It handles conversion between NumPy arrays and Base64-encoded JSON objects for network transmission.

Functions:
    tensor_to_json_serializable: Convert NumPy tensor to JSON-serializable format
    json_serializable_to_tensor: Convert JSON-serializable data back to NumPy tensor
"""

import base64
import numpy as np
import logging # برای لاگ کردن خطاهای احتمالی در سریال‌سازی/دی‌سریال‌سازی
from typing import Union, Dict, List, Any



def tensor_to_json_serializable(tensor: np.ndarray) -> dict:
    """
    Convert NumPy array to JSON-serializable format using Base64 encoding.
    
    Args:
        tensor: NumPy array to serialize
        
    Returns:
        Dictionary with tensor metadata and Base64-encoded data
        
    Raises:
        TypeError: If input is not a NumPy array or basic serializable type
        Exception: If serialization fails
    """
    if not isinstance(tensor, np.ndarray):
        if isinstance(tensor, (str, int, float, bool, list, dict, type(None))):
            return tensor # اگر خود داده قابل سریال‌سازی است، آن را برگردان
        logging.error(f"Input must be a NumPy array or basic serializable type, not {type(tensor)}")
        raise TypeError(f"Input must be a NumPy array or basic serializable type, not {type(tensor)}")

    try:
        return {
            '_tensor_': True, # یک شناسه برای تشخیص در زمان دی‌سریال‌سازی
            'dtype': str(tensor.dtype),
            'shape': list(tensor.shape),
            'data_b64': base64.b64encode(tensor.tobytes()).decode('utf-8')
        }
    except Exception as e:
        logging.error(f"Error serializing tensor with shape {tensor.shape} and dtype {tensor.dtype}: {e}", exc_info=True)
        raise

def json_serializable_to_tensor(data: Union[dict, str, int, float, bool, list, None]) -> Union[np.ndarray, str, int, float, bool, list, None]:
    """
    Convert JSON-serializable data back to NumPy array.
    
    Args:
        data: Dictionary containing tensor metadata and Base64-encoded data,
              or a basic Python type (str, int, float, bool, list, None)
              
    Returns:
        NumPy array reconstructed from the serialized data,
        or the original data if it's a basic Python type
        
    Raises:
        ValueError: If data format is invalid or missing required keys
        Exception: If deserialization fails
    """
    if not isinstance(data, dict) or not data.get('_tensor_'):
         if isinstance(data, (str, int, float, bool, list, type(None))):
             return data # ممکن است داده ساده باشد و نه یک تنسور سریال‌شده
         logging.error(f"Invalid format for tensor deserialization. Input data: {data}")
         raise ValueError("Invalid format for tensor deserialization or missing '_tensor_' identifier.")

    try:
        dtype_str = data['dtype']
        shape = tuple(data['shape'])
        data_b64 = data['data_b64']

        dtype = np.dtype(dtype_str)
        tensor_bytes = base64.b64decode(data_b64.encode('utf-8'))

        # اعتبارسنجی طول داده‌ها
        expected_length = 0
        if shape: # اگر shape خالی نباشد (برای اسکالرها prod(shape) معنی ندارد)
            prod_shape = 1
            for dim in shape:
                prod_shape *= dim
            expected_length = prod_shape * dtype.itemsize
        else: # اسکالر
            expected_length = dtype.itemsize
        
        if len(tensor_bytes) != expected_length:
             # اجازه برای تنسور خالی که طول مورد انتظار و طول بایت‌ها صفر است
             if not (expected_length == 0 and len(tensor_bytes) == 0):
                 raise ValueError(f"Data length mismatch for tensor: expected {expected_length} bytes based on shape {shape} and dtype {dtype_str}, got {len(tensor_bytes)} bytes.")

        if expected_length == 0 and not shape: # Scalar zero-byte (e.g. void)
            return np.array(None, dtype=dtype) # Special case, or handle as error
        elif expected_length == 0 and shape: # Empty array
            return np.empty(shape, dtype=dtype)
        else:
            return np.frombuffer(tensor_bytes, dtype=dtype).reshape(shape)

    except KeyError as e:
        logging.error(f"Missing key {e} in serialized tensor data: {data}", exc_info=True)
        raise ValueError(f"Serialized tensor data missing key: {e}")
    except Exception as e:
        logging.error(f"Error deserializing tensor: {e}. Data: {data}", exc_info=True)
        raise
    