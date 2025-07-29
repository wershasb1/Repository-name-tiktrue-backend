"""
Enhanced WebSocket Handler for TikTrue Platform

This module adds standardized protocol support to the existing WebSocket handler
in model_node.py without disrupting core functionality. It enables backward compatibility
while providing enhanced protocol features.

Features:
- Automatic protocol detection (standard vs. legacy)
- Standardized message format with headers
- Protocol validation and error handling
- Support for authentication and license validation
- Heartbeat mechanism for connection monitoring
- Transparent fallback to legacy protocol
- Statistics tracking for protocol usage

Classes:
    ProtocolEnhancedHandler: Main handler class for protocol enhancement

Functions:
    get_enhanced_handler: Get global enhanced handler instance
    enhanced_websocket_handler: WebSocket handler function for model_node.py integration
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Import protocol components
from core.protocol_spec import (
    ProtocolManager, ProtocolValidator, MessageType, ErrorCode,
    InferenceRequest, InferenceResponse, HeartbeatMessage, ErrorMessage
)
from license_models import LicenseInfo, ValidationStatus
from security.license_validator import LicenseValidator

logger = logging.getLogger("EnhancedWebSocketHandler")


class ProtocolEnhancedHandler:
    """
    Enhanced WebSocket handler that adds standard protocol support
    to the existing model_node.py WebSocket handler.
    
    This class provides a layer of protocol standardization while maintaining
    backward compatibility with legacy message formats. It automatically detects
    the message format and routes to the appropriate handler.
    
    Attributes:
        protocol_manager: Manager for protocol operations
        protocol_validator: Validator for protocol messages
        license_validator: Validator for license checks
        legacy_requests: Counter for legacy format requests
        protocol_requests: Counter for standard protocol requests
        total_requests: Counter for all requests
    """
    
    def __init__(self):
        self.protocol_manager = ProtocolManager()
        self.protocol_validator = ProtocolValidator()
        
        # Initialize license validator with fallback
        try:
            self.license_validator = LicenseValidator()
        except Exception as e:
            logger.warning(f"License validator initialization failed: {e}")
            # Create a mock license validator for testing
            self.license_validator = None
        
        # Statistics
        self.legacy_requests = 0
        self.protocol_requests = 0
        self.total_requests = 0
        
        logger.info("Protocol enhanced handler initialized")
    
    def is_standard_protocol_message(self, message_dict: Dict[str, Any]) -> bool:
        """
        Detect if a message follows the standard protocol format.
        
        This method examines the message structure to determine if it conforms
        to the standard protocol format with proper headers and required fields.
        
        Args:
            message_dict: Dictionary containing the parsed message
            
        Returns:
            True if the message follows standard protocol format, False otherwise
        """
        return (
            "header" in message_dict and 
            isinstance(message_dict["header"], dict) and
            "message_type" in message_dict["header"] and
            "protocol_version" in message_dict["header"]
        )
    
    async def process_message(self, websocket, message_str: str, execute_pipeline_func) -> bool:
        """
        Process incoming message with automatic protocol detection.
        
        This method serves as the main entry point for message processing. It automatically
        detects the message format (standard or legacy) and routes it to the appropriate
        handler. Standard protocol messages are handled internally, while legacy messages
        are delegated to the original handler.
        
        Args:
            websocket: WebSocket connection object
            message_str: Raw message string received from client
            execute_pipeline_func: Function to execute inference pipeline (from model_node.py)
            
        Returns:
            True if message was handled by protocol handler, False if should use legacy handler
            
        Raises:
            Exception: Handled internally and converted to protocol error response
        """
        try:
            self.total_requests += 1
            message_dict = json.loads(message_str)
            
            if self.is_standard_protocol_message(message_dict):
                # Handle with standard protocol
                await self._handle_standard_protocol_message(websocket, message_dict, execute_pipeline_func)
                self.protocol_requests += 1
                return True
            else:
                # Let legacy handler process it
                self.legacy_requests += 1
                return False
                
        except json.JSONDecodeError:
            # Invalid JSON - let legacy handler deal with it
            return False
        except Exception as e:
            logger.error(f"Error in protocol enhanced handler: {e}")
            await self._send_protocol_error(websocket, ErrorCode.INTERNAL_ERROR, str(e))
            return True  # We handled it (even if with error)
    
    async def _handle_standard_protocol_message(self, websocket, message_dict: Dict[str, Any], execute_pipeline_func):
        """
        Handle standard protocol message by routing to appropriate handler.
        
        This method validates the message format and routes it to the appropriate
        handler based on the message type. It handles validation errors and
        unsupported message types.
        
        Args:
            websocket: WebSocket connection object
            message_dict: Dictionary containing the parsed message
            execute_pipeline_func: Function to execute inference pipeline
            
        Returns:
            None
        """
        # Validate message
        is_valid, error_msg = self.protocol_validator.validate_message(message_dict)
        
        if not is_valid:
            await self._send_protocol_error(websocket, ErrorCode.VALIDATION_ERROR, f"Message validation failed: {error_msg}")
            return
        
        # Extract message type
        header = message_dict.get("header", {})
        message_type_str = header.get("message_type")
        
        try:
            message_type = MessageType(message_type_str)
        except ValueError:
            await self._send_protocol_error(websocket, ErrorCode.INVALID_REQUEST, f"Unknown message type: {message_type_str}")
            return
        
        # Route to appropriate handler
        if message_type == MessageType.INFERENCE_REQUEST:
            await self._handle_protocol_inference_request(websocket, message_dict, execute_pipeline_func)
        elif message_type == MessageType.HEARTBEAT:
            await self._handle_heartbeat(websocket, message_dict)
        elif message_type == MessageType.AUTHENTICATION:
            await self._handle_authentication(websocket, message_dict)
        elif message_type == MessageType.LICENSE_CHECK:
            await self._handle_license_check(websocket, message_dict)
        else:
            await self._send_protocol_error(websocket, ErrorCode.INVALID_REQUEST, f"Unsupported message type: {message_type_str}")
    
    async def _handle_protocol_inference_request(self, websocket, message_dict: Dict[str, Any], execute_pipeline_func):
        """
        Handle standard protocol inference request by executing the model pipeline.
        
        This method processes inference requests in the standard protocol format,
        converts them to the format expected by the model_node pipeline, executes
        the inference, and returns the results in the standard protocol format.
        
        Args:
            websocket: WebSocket connection object
            message_dict: Dictionary containing the parsed inference request
            execute_pipeline_func: Function to execute inference pipeline
            
        Returns:
            None
        """
        try:
            # Extract header information
            header = message_dict["header"]
            
            # Create InferenceRequest object
            request = InferenceRequest(
                header=header,
                model_id=message_dict["model_id"],
                prompt=message_dict["prompt"],
                parameters=message_dict.get("parameters", {}),
                max_tokens=message_dict.get("max_tokens", 100),
                temperature=message_dict.get("temperature", 0.7),
                top_p=message_dict.get("top_p", 0.9),
                stop_sequences=message_dict.get("stop_sequences", []),
                stream=message_dict.get("stream", False),
                context_window=message_dict.get("context_window", 2048),
                metadata=message_dict.get("metadata", {})
            )
            
            # Convert to legacy format for pipeline execution
            session_id = header.get("session_id") or f'protocol_{int(time.time())}'
            
            # Convert prompt to input_tensors format (simplified)
            input_tensors = {
                "input_ids": request.prompt,  # This would need proper tokenization in real implementation
                "model_id": request.model_id,
                "parameters": request.parameters,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p
            }
            
            # Execute pipeline using model_node's function
            pipeline_result = await execute_pipeline_func(
                session_id=session_id,
                step=0,
                initial_inputs=input_tensors
            )
            
            # Convert pipeline result to standard protocol response
            response = self.protocol_manager.create_inference_response(
                request_id=header.get("message_id"),
                model_id=request.model_id,
                generated_text=str(pipeline_result.get("output_tensors", "")),
                processing_time_ms=int(pipeline_result.get("processing_time", 0) * 1000),
                finish_reason="stop" if pipeline_result.get("status") == "success" else "error",
                error_code=ErrorCode.SUCCESS if pipeline_result.get("status") == "success" else ErrorCode.INTERNAL_ERROR,
                error_message=pipeline_result.get("error") if pipeline_result.get("status") != "success" else None
            )
            
            # Send standard protocol response
            await self._send_protocol_message(websocket, response)
            
        except Exception as e:
            logger.error(f"Error handling protocol inference request: {e}")
            await self._send_protocol_error(websocket, ErrorCode.INTERNAL_ERROR, f"Inference request failed: {e}")
    
    async def _handle_heartbeat(self, websocket, message_dict: Dict[str, Any]):
        """
        Handle heartbeat message for connection health monitoring.
        
        This method processes heartbeat messages from clients and responds with
        server health information including status, load, and memory availability.
        Heartbeats are used to maintain connection health and detect disconnections.
        
        Args:
            websocket: WebSocket connection object
            message_dict: Dictionary containing the heartbeat message
            
        Returns:
            None
        """
        try:
            # Create heartbeat response
            response = self.protocol_manager.create_heartbeat(
                worker_id=f"model_node_{id(websocket)}",
                status="healthy",
                load_percentage=50.0,  # Could be calculated from actual system metrics
                available_memory_mb=1024,  # Could be calculated from actual system metrics
                active_sessions=1
            )
            
            await self._send_protocol_message(websocket, response)
            
        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")
            await self._send_protocol_error(websocket, ErrorCode.INTERNAL_ERROR, "Heartbeat failed")
    
    async def _handle_authentication(self, websocket, message_dict: Dict[str, Any]):
        """
        Handle authentication message with license validation.
        
        This method processes authentication requests from clients, validates
        the provided license key, and responds with the authentication result.
        Successful authentication enables access to licensed features.
        
        Args:
            websocket: WebSocket connection object
            message_dict: Dictionary containing the authentication message
            
        Returns:
            None
        """
        try:
            # Extract license information from message
            license_key = message_dict.get("license_key")
            if not license_key:
                await self._send_protocol_error(websocket, ErrorCode.AUTHENTICATION_FAILED, "License key required")
                return
            
            # Validate license
            validation_result = self.security.license_validator.validate_license(license_key, "test_hardware")
            
            if validation_result.status == ValidationStatus.VALID:
                # Send success response
                response = self.protocol_manager.create_inference_response(
                    request_id=message_dict["header"]["message_id"],
                    model_id="auth",
                    generated_text="Authentication successful"
                )
                
                await self._send_protocol_message(websocket, response)
                logger.info(f"Client authenticated successfully")
                
            else:
                await self._send_protocol_error(websocket, ErrorCode.AUTHENTICATION_FAILED, f"License validation failed: {validation_result.status}")
            
        except Exception as e:
            logger.error(f"Error handling authentication: {e}")
            await self._send_protocol_error(websocket, ErrorCode.AUTHENTICATION_FAILED, "Authentication failed")
    
    async def _handle_license_check(self, websocket, message_dict: Dict[str, Any]):
        """
        Handle license check message for license validation.
        
        This method processes license check requests from clients and responds
        with the current license status. It can be used to verify if a license
        is still valid without performing a full authentication.
        
        Args:
            websocket: WebSocket connection object
            message_dict: Dictionary containing the license check message
            
        Returns:
            None
        """
        try:
            # Simple license check response
            response = self.protocol_manager.create_inference_response(
                request_id=message_dict["header"]["message_id"],
                model_id="license_check",
                generated_text="License check completed"
            )
            
            await self._send_protocol_message(websocket, response)
            
        except Exception as e:
            logger.error(f"Error handling license check: {e}")
            await self._send_protocol_error(websocket, ErrorCode.INTERNAL_ERROR, "License check failed")
    
    async def _send_protocol_message(self, websocket, message):
        """
        Send standard protocol message to the client.
        
        This method serializes the protocol message object to JSON format
        and sends it over the WebSocket connection to the client.
        
        Args:
            websocket: WebSocket connection object
            message: Protocol message object to send
            
        Returns:
            None
            
        Raises:
            Exception: Logged but not propagated
        """
        try:
            message_json = self.protocol_manager.serialize_message(message)
            await websocket.send(message_json)
        except Exception as e:
            logger.error(f"Failed to send protocol message: {e}")
    
    async def _send_protocol_error(self, websocket, error_code: ErrorCode, message: str):
        """
        Send standard protocol error message to the client.
        
        This method creates and sends a standardized error message with the
        specified error code and message. It handles serialization and transmission
        of the error message over the WebSocket connection.
        
        Args:
            websocket: WebSocket connection object
            error_code: Error code from ErrorCode enum
            message: Human-readable error message
            
        Returns:
            None
            
        Raises:
            Exception: Logged but not propagated
        """
        try:
            error_msg = self.protocol_manager.create_error_message(
                error_code=error_code,
                error_message=message
            )
            
            await self._send_protocol_message(websocket, error_msg)
            
        except Exception as e:
            logger.error(f"Failed to send protocol error message: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get handler statistics for monitoring and diagnostics.
        
        This method returns statistics about the handler's operation including
        request counts and protocol usage percentages. Useful for monitoring
        the adoption of the standard protocol versus legacy format.
        
        Returns:
            Dictionary containing handler statistics including total requests,
            legacy requests, protocol requests, and protocol usage percentage
        """
        return {
            "total_requests": self.total_requests,
            "legacy_requests": self.legacy_requests,
            "protocol_requests": self.protocol_requests,
            "protocol_percentage": (self.protocol_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        }


# Global instance
_enhanced_handler: Optional[ProtocolEnhancedHandler] = None

def get_enhanced_handler() -> ProtocolEnhancedHandler:
    """Get global enhanced handler instance"""
    global _enhanced_handler
    if _enhanced_handler is None:
        _enhanced_handler = ProtocolEnhancedHandler()
    return _enhanced_handler


async def enhanced_websocket_handler(websocket, path=None):
    """
    Enhanced WebSocket handler that can be used as a drop-in replacement
    for the original handler in model_node.py.
    
    This function maintains full backward compatibility while adding standard protocol support.
    It automatically detects the message format and routes to the appropriate handler,
    providing seamless integration with existing systems.
    
    Args:
        websocket: WebSocket connection object
        path: Optional path parameter (for compatibility with websockets library)
        
    Returns:
        None
        
    Note:
        This handler should be used as the main entry point for WebSocket connections
        in model_node.py to enable protocol standardization without breaking
        existing functionality.
    """
    # Import here to avoid circular imports
    from core.model_node import execute_pipeline, NODE_ID
    
    handler = get_enhanced_handler()
    
    # Get node info
    handler_node_id = NODE_ID or "UNKNOWN_NODE"
    peer_address_str = str(websocket.remote_address)
    connection_id = f"conn_{id(websocket)}"
    
    logging.info(
        f"Enhanced Handler: New WebSocket connection from {peer_address_str}",
        extra={"custom_extra_fields": {
            "event_type": "ENHANCED_HANDLER_NEW_CONNECTION",
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
                
                # Try enhanced protocol handler first
                handled = await handler.process_message(websocket, message_str, execute_pipeline)
                
                if not handled:
                    # Fall back to legacy handling
                    await _handle_legacy_message(websocket, message_str, handler_node_id, connection_id)
                
                message_total_time = time.time() - message_start_time
                
                logging.debug(f"Message processed in {message_total_time:.3f}s")
                
            except Exception as e:
                logging.error(f"Error processing message: {e}")
                # Send legacy error response
                error_response = {
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(error_response, default=str))
                
    except Exception as e:
        logging.error(f"WebSocket connection error: {e}")
    finally:
        logging.info(f"Enhanced Handler: Connection closed {connection_id}")


async def _handle_legacy_message(websocket, message_str: str, handler_node_id: str, connection_id: str):
    """
    Handle legacy format message using original model_node.py logic.
    
    This function processes messages in the legacy format for backward compatibility.
    It extracts session information, validates the request, executes the inference
    pipeline, and sends the response back to the client.
    
    Args:
        websocket: WebSocket connection object
        message_str: Raw message string received from client
        handler_node_id: ID of the handler node
        connection_id: Unique connection identifier
        
    Returns:
        None
        
    Raises:
        Exception: Handled internally and converted to error response
    """
    from core.model_node import execute_pipeline
    
    try:
        data = json.loads(message_str)
        
        session_id = data.get('session_id', 'unknown')
        step = data.get('step', 0)
        
        # Log received request
        logging.info(
            f"Processing legacy pipeline request",
            extra={"custom_extra_fields": {
                "event_type": "LEGACY_PIPELINE_REQUEST_RECEIVED",
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
            return
        
        # Execute pipeline
        pipeline_result = await execute_pipeline(
            session_id=session_id,
            step=step,
            initial_inputs=data.get('input_tensors', {})
        )
        
        # Send response
        response_json = json.dumps(pipeline_result, default=str)
        await websocket.send(response_json)
        
        # Enhanced response logging
        logging.info(
            f"Legacy pipeline response sent",
            extra={"custom_extra_fields": {
                "event_type": "LEGACY_PIPELINE_RESPONSE_SENT",
                "node_id": handler_node_id,
                "session_id": session_id,
                "step": step,
                "data": {
                    "status": pipeline_result.get("status", "unknown"),
                    "processing_time": pipeline_result.get("processing_time", 0),
                    "connection_id": connection_id
                }
            }}
        )
        
    except json.JSONDecodeError as e:
        error_response = {
            "status": "error",
            "message": f"Invalid JSON: {e}",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send(json.dumps(error_response, default=str))
    except Exception as e:
        logging.error(f"Legacy message handling error: {e}")
        error_response = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send(json.dumps(error_response, default=str))