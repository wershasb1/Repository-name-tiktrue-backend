"""
License Integration for model_node.py
This module provides enhanced WebSocket handler with license validation
"""

import json
import logging
import time
from typing import Dict, Any, Optional

from license_enforcer import (
    get_license_enforcer, validate_client_connection, register_client_disconnect,
    validate_model_access, get_current_license_status
)

logger = logging.getLogger("ModelNodeLicenseIntegration")


async def enhanced_websocket_handler(websocket, path=None):
    """
    Enhanced WebSocket handler with license validation
    This replaces the original handler in model_node.py
    """
    # Import globals from model_node (these would be available in the actual integration)
    # global CPU_WORKER, GPU_WORKER, EXECUTION_PLAN, MODEL_CHAIN_ORDER, NODE_ID
    
    # For demo purposes, we'll simulate these
    handler_node_id = "demo_node"  # Would be NODE_ID
    peer_address_str = str(websocket.remote_address) if hasattr(websocket, 'remote_address') else "unknown"
    connection_id = f"conn_{id(websocket)}"
    
    # Get license enforcer
    license_enforcer = get_license_enforcer()
    client_id = None
    
    logger.info(
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
                network_id = data.get('network_id', 'default')
                license_hash = data.get('license_hash', '')
                
                # Generate client ID if not set
                if client_id is None:
                    client_id = f"{peer_address_str}_{session_id}"
                
                # === LICENSE VALIDATION ===
                
                # 1. Check license status
                license_status = get_current_license_status()
                if not license_status.get('valid', False):
                    error_response = {
                        "status": "license_error",
                        "message": f"Invalid license: {license_status.get('status', 'unknown')}",
                        "license_status": license_status.get('status', 'invalid'),
                        "session_id": session_id,
                        "step": step,
                        "network_id": network_id
                    }
                    await websocket.send(json.dumps(error_response, default=str))
                    continue
                
                # 2. Validate client connection
                connection_allowed = await validate_client_connection(client_id, network_id)
                if not connection_allowed:
                    error_response = {
                        "status": "license_error",
                        "message": "Client connection limit exceeded",
                        "license_status": "client_limit_exceeded",
                        "session_id": session_id,
                        "step": step,
                        "network_id": network_id,
                        "max_clients": license_status.get('max_clients', 'unknown'),
                        "current_clients": license_status.get('current_clients', 'unknown')
                    }
                    await websocket.send(json.dumps(error_response, default=str))
                    continue
                
                # 3. Validate model access (if model_id is specified)
                model_id = data.get('model_id')
                if model_id and not validate_model_access(model_id):
                    error_response = {
                        "status": "license_error",
                        "message": f"Model access denied: {model_id}",
                        "license_status": "model_access_denied",
                        "session_id": session_id,
                        "step": step,
                        "network_id": network_id,
                        "model_id": model_id
                    }
                    await websocket.send(json.dumps(error_response, default=str))
                    continue
                
                # === END LICENSE VALIDATION ===
                
                # Log received request with license info
                logger.info(
                    f"Processing pipeline request (license validated)",
                    extra={"custom_extra_fields": {
                        "event_type": "PIPELINE_REQUEST_RECEIVED",
                        "node_id": handler_node_id,
                        "session_id": session_id,
                        "step": step,
                        "data": {
                            "input_keys": list(data.get('input_tensors', {}).keys()),
                            "message_size": len(message_str),
                            "connection_id": connection_id,
                            "client_id": client_id,
                            "network_id": network_id,
                            "license_plan": license_status.get('plan', 'unknown'),
                            "model_id": model_id
                        }
                    }}
                )
                
                # Validate request structure
                if not data.get('input_tensors'):
                    error_response = {
                        "status": "error",
                        "message": "Missing input_tensors in request",
                        "session_id": session_id,
                        "step": step,
                        "network_id": network_id,
                        "license_status": "valid"
                    }
                    await websocket.send(json.dumps(error_response, default=str))
                    continue
                
                # Execute pipeline (this would call the actual execute_pipeline function)
                # For demo purposes, we'll simulate a successful response
                pipeline_result = await simulate_pipeline_execution(
                    session_id=session_id,
                    step=step,
                    initial_inputs=data.get('input_tensors', {}),
                    network_id=network_id,
                    model_id=model_id
                )
                
                # Add license status to response
                pipeline_result['license_status'] = 'valid'
                pipeline_result['network_id'] = network_id
                
                # Send response
                response_json = json.dumps(pipeline_result, default=str)
                await websocket.send(response_json)
                
                message_total_time = time.time() - message_start_time
                
                # Enhanced response logging with license info
                logger.info(
                    f"Pipeline response sent (license validated)",
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
                            "connection_id": connection_id,
                            "client_id": client_id,
                            "network_id": network_id,
                            "license_plan": license_status.get('plan', 'unknown')
                        }
                    }}
                )
                
            except json.JSONDecodeError as e:
                error_response = {
                    "status": "error",
                    "message": f"Invalid JSON: {str(e)}",
                    "license_status": "valid"  # JSON error is not a license issue
                }
                await websocket.send(json.dumps(error_response, default=str))
                
            except PermissionError as e:
                # License-related permission error
                error_response = {
                    "status": "license_error",
                    "message": str(e),
                    "license_status": "permission_denied",
                    "session_id": data.get('session_id', 'unknown'),
                    "step": data.get('step', 0),
                    "network_id": data.get('network_id', 'default')
                }
                await websocket.send(json.dumps(error_response, default=str))
                
            except Exception as e:
                logger.error(f"Handler error: {e}", exc_info=True)
                error_response = {
                    "status": "error",
                    "message": f"Internal server error: {str(e)}",
                    "license_status": "valid"  # Internal error is not a license issue
                }
                await websocket.send(json.dumps(error_response, default=str))
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}", exc_info=True)
    
    finally:
        # Clean up client connection
        if client_id:
            await register_client_disconnect(client_id)
            logger.info(f"Client disconnected and cleaned up: {client_id}")


async def simulate_pipeline_execution(session_id: str, step: int, initial_inputs: Dict[str, Any], 
                                    network_id: str, model_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Simulate pipeline execution for demo purposes
    In the actual integration, this would call the real execute_pipeline function
    """
    # Simulate processing time
    import asyncio
    await asyncio.sleep(0.1)
    
    return {
        "status": "success",
        "session_id": session_id,
        "step": step,
        "network_id": network_id,
        "model_id": model_id,
        "outputs": {
            "logits": "simulated_logits_tensor"
        },
        "successful_blocks": [f"block_{i}" for i in range(1, 34)],
        "failed_blocks": [],
        "total_pipeline_time": 0.1,
        "execution_times": {"total": 0.1}
    }


def create_license_aware_worker_factory():
    """
    Create factory functions for license-aware workers
    These would be used to replace the existing worker creation in model_node.py
    """
    
    def create_cpu_worker_with_license(*args, **kwargs):
        """Create CPU worker with license validation"""
        from workers.worker_lib import CPUWorker
        
        # Create original worker
        worker = CPUWorker(*args, **kwargs)
        
        # Enhance with license validation
        original_process_job = worker._process_job
        
        async def license_aware_process_job(job):
            """Enhanced job processing with license validation"""
            block_id = job.get('block_id')
            model_id = job.get('model_id')
            
            # Validate model access if model_id is provided
            if model_id and not validate_model_access(model_id):
                return {
                    'job_id': job.get('job_id', 'unknown'),
                    'worker_name': worker.name,
                    'status': 'license_error',
                    'error': f'Model access denied: {model_id}',
                    'outputs': None,
                    'processing_time': 0.0
                }
            
            # Call original processing
            return await original_process_job(job)
        
        # Replace the method
        worker._process_job = license_aware_process_job
        
        return worker
    
    def create_gpu_worker_with_license(*args, **kwargs):
        """Create GPU worker with license validation"""
        from workers.worker_lib import GPUWorker
        
        # Create original worker
        worker = GPUWorker(*args, **kwargs)
        
        # Enhance with license validation (same as CPU worker)
        original_process_job = worker._process_job
        
        async def license_aware_process_job(job):
            """Enhanced job processing with license validation"""
            block_id = job.get('block_id')
            model_id = job.get('model_id')
            
            # Validate model access if model_id is provided
            if model_id and not validate_model_access(model_id):
                return {
                    'job_id': job.get('job_id', 'unknown'),
                    'worker_name': worker.name,
                    'status': 'license_error',
                    'error': f'Model access denied: {model_id}',
                    'outputs': None,
                    'processing_time': 0.0
                }
            
            # Call original processing
            return await original_process_job(job)
        
        # Replace the method
        worker._process_job = license_aware_process_job
        
        return worker
    
    return create_cpu_worker_with_license, create_gpu_worker_with_license


def integrate_license_validation_into_config_manager():
    """
    Integration points for config_manager.py to validate model access
    """
    
    def validate_model_selection(model_id: str) -> bool:
        """
        Validate if the selected model is allowed by the license
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if model is allowed, False otherwise
        """
        return validate_model_access(model_id)
    
    def get_allowed_models() -> list:
        """
        Get list of models allowed by current license
        
        Returns:
            List of allowed model IDs
        """
        license_status = get_current_license_status()
        if not license_status.get('valid', False):
            return []
        
        # This would need to be enhanced to return actual model list
        # based on license tier
        enforcer = get_license_enforcer()
        if enforcer.current_license:
            return enforcer.current_license.allowed_models
        
        return []
    
    return validate_model_selection, get_allowed_models


# Integration instructions for existing files:

INTEGRATION_INSTRUCTIONS = """
To integrate license validation into the existing codebase:

1. model_node.py:
   - Import: from license_enforcer import get_license_enforcer, validate_client_connection, etc.
   - Replace the handler function with enhanced_websocket_handler
   - Add license validation to worker creation
   - Modify execute_pipeline to include license checks

2. worker_lib.py:
   - Import license validation functions
   - Enhance BaseWorker._process_job with license checks
   - Add model access validation before processing

3. config_manager.py:
   - Add license validation to model selection
   - Filter available models based on license tier
   - Add license status to configuration validation

4. chatbot_interface.py:
   - Add license_hash to request messages
   - Handle license_error responses
   - Display license status in UI

5. start_server.py:
   - Add license validation during startup
   - Display license status information
   - Handle license installation if needed

Example integration code snippets are provided in the functions above.
"""

if __name__ == "__main__":
    print("License Integration Module for TikTrue")
    print("=" * 50)
    print(INTEGRATION_INSTRUCTIONS)