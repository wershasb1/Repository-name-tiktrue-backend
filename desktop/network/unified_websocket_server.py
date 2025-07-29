"""
Unified WebSocket Server for TikTrue Platform

This module combines model inference capabilities with standardized protocol management
in a unified WebSocket server implementation for the TikTrue Distributed LLM Platform.

Features:
- Automatic protocol detection between standard and legacy formats
- Seamless integration with model_node.py inference pipeline
- License validation and authentication
- Session management and tracking
- Heartbeat monitoring for connection health
- Comprehensive statistics and monitoring
- Graceful fallbacks for missing dependencies

Classes:
    UnifiedClientConnection: Enhanced client connection with protocol support
    UnifiedWebSocketServer: Main unified WebSocket server implementation

Functions:
    create_unified_websocket_server: Create and return a unified server instance
    run_unified_websocket_server: Run unified WebSocket server (convenience function)
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Set, Callable
from pathlib import Path

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, WebSocketException
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logging.error("WebSockets library not available. Please install: pip install websockets")

# Import protocol and license management
from core.protocol_spec import (
    ProtocolManager, ProtocolValidator, MessageType, ErrorCode,
    InferenceRequest, InferenceResponse, HeartbeatMessage, ErrorMessage
)
from license_models import LicenseInfo, ValidationStatus
from security.license_validator import LicenseValidator

# Setup logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UnifiedWebSocketServer")

# Import model node functionality (with fallback)
try:
    from core.model_node import (
        execute_pipeline, get_secure_model_block_manager,
        NODE_ID, NETWORK_CONFIG
    )
    MODEL_NODE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Model node functionality not available: {e}")
    MODEL_NODE_AVAILABLE = False
    
    # Fallback implementations
    async def execute_pipeline(session_id: str, step: int, initial_inputs: dict):
        """Fallback pipeline execution"""
        return {
            "status": "success",
            "output_tensors": f"Mock response for session {session_id}",
            "processing_time": 0.1
        }
    
    def get_secure_model_block_manager():
        """Fallback secure manager"""
        class MockSecureManager:
            def authorize_session(self, session_id: str, license_key: str) -> bool:
                return True
            def revoke_session(self, session_id: str):
                pass
        return MockSecureManager()
    
    NODE_ID = "fallback_node"
    NETWORK_CONFIG = {}

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UnifiedWebSocketServer")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/unified_websocket_server.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class UnifiedClientConnection:
    """Enhanced client connection with protocol and inference support"""
    
    def __init__(self, websocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.connected_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self.license_info: Optional[LicenseInfo] = None
        self.session_data: Dict[str, Any] = {}
        self.request_count = 0
        self.error_count = 0
        self.inference_sessions: Set[str] = set()  # Track inference sessions
        self.protocol_mode = "auto"  # auto, legacy, standard
    
    async def send_message(self, message: Any):
        """Send message to client with protocol detection"""
        try:
            if isinstance(message, dict):
                # Legacy format for backward compatibility
                message_json = json.dumps(message, default=str)
            elif hasattr(message, '__dict__'):
                # Standard protocol format
                message_json = json.dumps(message.__dict__, default=str, indent=2)
            else:
                message_json = json.dumps(message, default=str)
            
            await self.websocket.send(message_json)
            
        except Exception as e:
            logger.error(f"Failed to send message to client {self.client_id}: {e}")
            raise
    
    def update_heartbeat(self):
        """Update last heartbeat timestamp"""
        self.last_heartbeat = datetime.now()
    
    def add_inference_session(self, session_id: str):
        """Add inference session to tracking"""
        self.inference_sessions.add(session_id)
    
    def remove_inference_session(self, session_id: str):
        """Remove inference session from tracking"""
        self.inference_sessions.discard(session_id)


class UnifiedWebSocketServer:
    """
    Unified WebSocket server combining protocol management with inference capabilities
    """
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 8702,
                 license_validator: Optional[LicenseValidator] = None):
        """
        Initialize unified WebSocket server
        
        Args:
            host: Server host address
            port: Server port
            license_validator: License validator instance
        """
        self.host = host
        self.port = port
        self.license_validator = license_validator or LicenseValidator()
        
        # Protocol management
        self.protocol_manager = ProtocolManager()
        self.protocol_validator = ProtocolValidator()
        
        # Client management
        self.clients: Dict[str, UnifiedClientConnection] = {}
        self.active_sessions: Dict[str, str] = {}  # session_id -> client_id
        
        # Server state
        self.server = None
        self.running = False
        self.start_time: Optional[datetime] = None
        
        # Statistics
        self.total_connections = 0
        self.total_messages = 0
        self.total_errors = 0
        self.inference_requests = 0
        self.protocol_requests = 0
        
        # Message handlers for standard protocol
        self.protocol_handlers: Dict[MessageType, Callable] = {
            MessageType.INFERENCE_REQUEST: self._handle_protocol_inference_request,
            MessageType.HEARTBEAT: self._handle_heartbeat,
            MessageType.AUTHENTICATION: self._handle_authentication,
            MessageType.LICENSE_CHECK: self._handle_license_check
        }
        
        # Secure model block manager
        self.secure_manager = get_secure_model_block_manager()
        
        logger.info(f"Unified WebSocket server initialized on {host}:{port}")
    
    async def start(self):
        """Start the unified WebSocket server"""
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("WebSockets library not available. Please install: pip install websockets")
        
        try:
            self.server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port,
                max_size=None,
                ping_interval=180,
                ping_timeout=600,
                close_timeout=1200
            )
            
            self.running = True
            self.start_time = datetime.now()
            
            logger.info(f"Unified WebSocket server started on ws://{self.host}:{self.port}")
            
            # Start background tasks
            asyncio.create_task(self._heartbeat_monitor())
            
        except Exception as e:
            logger.error(f"Failed to start unified WebSocket server: {e}")
            raise
    
    async def stop(self):
        """Stop the unified WebSocket server"""
        if self.server:
            self.running = False
            self.server.close()
            await self.server.wait_closed()
            
            # Disconnect all clients
            for client in list(self.clients.values()):
                try:
                    await client.websocket.close()
                except:
                    pass
            
            self.clients.clear()
            self.active_sessions.clear()
            
            logger.info("Unified WebSocket server stopped")
    
    async def _handle_client(self, websocket, path):
        """Handle new client connection with protocol detection"""
        client_id = str(uuid.uuid4())
        client = UnifiedClientConnection(websocket, client_id)
        
        self.clients[client_id] = client
        self.total_connections += 1
        
        logger.info(f"Client connected: {client_id} from {websocket.remote_address}")
        
        try:
            async for message in websocket:
                await self._process_message(client, message)
                
        except ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
            self.total_errors += 1
        finally:
            # Clean up client
            await self._cleanup_client(client)
    
    async def _cleanup_client(self, client: UnifiedClientConnection):
        """Clean up client resources"""
        client_id = client.client_id
        
        # Revoke any inference sessions
        for session_id in list(client.inference_sessions):
            try:
                self.secure_manager.revoke_session(session_id)
            except Exception as e:
                logger.error(f"Error revoking session {session_id}: {e}")
        
        # Remove from tracking
        if client_id in self.clients:
            del self.clients[client_id]
        
        # Remove from active sessions
        sessions_to_remove = [sid for sid, cid in self.active_sessions.items() if cid == client_id]
        for session_id in sessions_to_remove:
            del self.active_sessions[session_id]
    
    async def _process_message(self, client: UnifiedClientConnection, message: str):
        """Process incoming message with protocol detection"""
        try:
            self.total_messages += 1
            client.request_count += 1
            
            # Parse message
            if isinstance(message, bytes):
                message_str = message.decode('utf-8')
            else:
                message_str = message
            
            message_dict = json.loads(message_str)
            
            # Detect message format
            if self._is_standard_protocol_message(message_dict):
                # Standard protocol message
                await self._handle_standard_protocol_message(client, message_dict)
                self.protocol_requests += 1
            else:
                # Legacy inference message
                await self._handle_legacy_inference_message(client, message_dict)
                self.inference_requests += 1
            
        except json.JSONDecodeError as e:
            await self._send_error_response(client, f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing message from client {client.client_id}: {e}")
            await self._send_error_response(client, "Internal server error")
            client.error_count += 1
    
    def _is_standard_protocol_message(self, message_dict: Dict[str, Any]) -> bool:
        """Detect if message follows standard protocol format"""
        return (
            "header" in message_dict and 
            isinstance(message_dict["header"], dict) and
            "message_type" in message_dict["header"] and
            "protocol_version" in message_dict["header"]
        )
    
    async def _handle_standard_protocol_message(self, client: UnifiedClientConnection, message_dict: Dict[str, Any]):
        """Handle standard protocol message"""
        # Validate message
        is_valid, error_msg = self.protocol_validator.validate_message(message_dict)
        
        if not is_valid:
            await self._send_protocol_error(client, ErrorCode.VALIDATION_ERROR, f"Message validation failed: {error_msg}")
            return
        
        # Extract message type
        header = message_dict.get("header", {})
        message_type_str = header.get("message_type")
        
        try:
            message_type = MessageType(message_type_str)
        except ValueError:
            await self._send_protocol_error(client, ErrorCode.INVALID_REQUEST, f"Unknown message type: {message_type_str}")
            return
        
        # Route to appropriate handler
        if message_type in self.protocol_handlers:
            await self.protocol_handlers[message_type](client, message_dict)
        else:
            await self._send_protocol_error(client, ErrorCode.INVALID_REQUEST, f"Unsupported message type: {message_type_str}")
    
    async def _handle_legacy_inference_message(self, client: UnifiedClientConnection, message_dict: Dict[str, Any]):
        """Handle legacy inference message (backward compatibility)"""
        try:
            session_id = message_dict.get('session_id', f'legacy_{client.client_id}_{int(time.time())}')
            step = message_dict.get('step', 0)
            input_tensors = message_dict.get('input_tensors', {})
            
            if not input_tensors:
                await client.send_message({
                    "status": "error",
                    "message": "Missing input_tensors in request",
                    "session_id": session_id,
                    "step": step
                })
                return
            
            # Track inference session
            client.add_inference_session(session_id)
            
            # Authorize session if license is available
            if client.license_info:
                self.secure_manager.authorize_session(session_id, client.license_info.license_key)
            
            # Execute pipeline using model_node functionality
            pipeline_result = await execute_pipeline(
                session_id=session_id,
                step=step,
                initial_inputs=input_tensors
            )
            
            # Send legacy format response
            await client.send_message(pipeline_result)
            
            logger.info(f"Legacy inference request processed for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error handling legacy inference request: {e}")
            await client.send_message({
                "status": "error",
                "message": str(e),
                "session_id": session_id,
                "step": step
            })
    
    async def _handle_protocol_inference_request(self, client: UnifiedClientConnection, message_dict: Dict[str, Any]):
        """Handle standard protocol inference request"""
        try:
            # Create InferenceRequest object
            request = InferenceRequest(
                header=message_dict["header"],
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
            
            # Validate license if present
            license_valid = await self._validate_client_license(client, request.header)
            if not license_valid:
                return  # Error already sent
            
            # Convert to legacy format for pipeline execution
            session_id = request.header.session_id or f'protocol_{client.client_id}_{int(time.time())}'
            
            # Simple prompt to tensor conversion (can be enhanced)
            input_tensors = {
                "input_ids": request.prompt,  # Simplified conversion
                "model_id": request.model_id,
                "parameters": request.parameters
            }
            
            # Track inference session
            client.add_inference_session(session_id)
            
            # Execute pipeline
            pipeline_result = await execute_pipeline(
                session_id=session_id,
                step=0,
                initial_inputs=input_tensors
            )
            
            # Convert pipeline result to standard protocol response
            response = self.protocol_manager.create_inference_response(
                request_id=request.header.message_id,
                model_id=request.model_id,
                generated_text=str(pipeline_result.get("output_tensors", "")),
                license_info=client.license_info,
                processing_time_ms=int(pipeline_result.get("processing_time", 0) * 1000),
                finish_reason="stop" if pipeline_result.get("status") == "success" else "error"
            )
            
            # Send standard protocol response
            await client.send_message(response)
            
        except Exception as e:
            logger.error(f"Error handling protocol inference request: {e}")
            await self._send_protocol_error(client, ErrorCode.INTERNAL_ERROR, f"Inference request failed: {e}")
    
    async def _handle_heartbeat(self, client: UnifiedClientConnection, message_dict: Dict[str, Any]):
        """Handle heartbeat message"""
        try:
            client.update_heartbeat()
            
            # Create heartbeat response
            response = self.protocol_manager.create_heartbeat(
                worker_id=f"unified_server_{self.host}_{self.port}",
                license_info=client.license_info,
                status="healthy",
                load_percentage=self._get_server_load(),
                available_memory_mb=self._get_available_memory(),
                active_sessions=len(client.inference_sessions)
            )
            
            await client.send_message(response)
            
        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")
            await self._send_protocol_error(client, ErrorCode.INTERNAL_ERROR, "Heartbeat failed")
    
    async def _handle_authentication(self, client: UnifiedClientConnection, message_dict: Dict[str, Any]):
        """Handle authentication message"""
        try:
            # Extract license information from message
            license_key = message_dict.get("license_key")
            if not license_key:
                await self._send_protocol_error(client, ErrorCode.AUTHENTICATION_FAILED, "License key required")
                return
            
            # Validate license
            validation_result = self.security.license_validator.validate_license_key(license_key)
            
            if validation_result.status == ValidationStatus.VALID:
                client.license_info = validation_result
                
                # Send success response
                response = self.protocol_manager.create_inference_response(
                    request_id=message_dict["header"]["message_id"],
                    model_id="auth",
                    generated_text="Authentication successful",
                    license_info=validation_result
                )
                
                await client.send_message(response)
                logger.info(f"Client {client.client_id} authenticated successfully")
                
            else:
                await self._send_protocol_error(client, ErrorCode.AUTHENTICATION_FAILED, f"License validation failed: {validation_result.status}")
            
        except Exception as e:
            logger.error(f"Error handling authentication: {e}")
            await self._send_protocol_error(client, ErrorCode.AUTHENTICATION_FAILED, "Authentication failed")
    
    async def _handle_license_check(self, client: UnifiedClientConnection, message_dict: Dict[str, Any]):
        """Handle license check message"""
        try:
            if not client.license_info:
                await self._send_protocol_error(client, ErrorCode.LICENSE_EXPIRED, "No license information available")
                return
            
            # Re-validate license
            validation_result = self.security.license_validator.validate_license_key(client.license_info.license_key)
            
            response = self.protocol_manager.create_inference_response(
                request_id=message_dict["header"]["message_id"],
                model_id="license_check",
                generated_text=f"License status: {validation_result.status.value}",
                license_info=validation_result if validation_result.status == ValidationStatus.VALID else None
            )
            
            await client.send_message(response)
            
        except Exception as e:
            logger.error(f"Error handling license check: {e}")
            await self._send_protocol_error(client, ErrorCode.INTERNAL_ERROR, "License check failed")
    
    async def _validate_client_license(self, client: UnifiedClientConnection, header: Dict[str, Any]) -> bool:
        """Validate client license for request"""
        # Check if license hash is provided
        license_hash = header.get("license_hash")
        if not license_hash:
            await self._send_protocol_error(client, ErrorCode.LICENSE_EXPIRED, "License hash required")
            return False
        
        # Check if client has valid license info
        if not client.license_info:
            await self._send_protocol_error(client, ErrorCode.LICENSE_EXPIRED, "Client not authenticated")
            return False
        
        # Validate license is still valid
        validation_result = self.security.license_validator.validate_license_key(client.license_info.license_key)
        if validation_result.status != ValidationStatus.VALID:
            await self._send_protocol_error(client, ErrorCode.LICENSE_EXPIRED, f"License invalid: {validation_result.status}")
            return False
        
        return True
    
    async def _send_protocol_error(self, client: UnifiedClientConnection, error_code: ErrorCode, message: str):
        """Send standard protocol error message"""
        try:
            error_msg = self.protocol_manager.create_error_message(
                error_code=error_code,
                error_message=message,
                license_info=client.license_info
            )
            
            await client.send_message(error_msg)
            
        except Exception as e:
            logger.error(f"Failed to send protocol error message: {e}")
    
    async def _send_error_response(self, client: UnifiedClientConnection, message: str):
        """Send legacy format error response"""
        try:
            error_response = {
                "status": "error",
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
            await client.send_message(error_response)
            
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")
    
    async def _heartbeat_monitor(self):
        """Monitor client heartbeats and remove inactive clients"""
        while self.running:
            try:
                current_time = datetime.now()
                inactive_clients = []
                
                for client_id, client in self.clients.items():
                    # Check if client hasn't sent heartbeat in 5 minutes
                    if (current_time - client.last_heartbeat).total_seconds() > 300:
                        inactive_clients.append(client_id)
                
                # Remove inactive clients
                for client_id in inactive_clients:
                    if client_id in self.clients:
                        client = self.clients[client_id]
                        try:
                            await client.websocket.close()
                        except:
                            pass
                        await self._cleanup_client(client)
                        logger.info(f"Removed inactive client: {client_id}")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
                await asyncio.sleep(60)
    
    def _get_server_load(self) -> float:
        """Get current server load percentage"""
        return min(len(self.clients) * 10.0, 100.0)
    
    def _get_available_memory(self) -> int:
        """Get available memory in MB"""
        try:
            import psutil
            return int(psutil.virtual_memory().available / (1024 * 1024))
        except ImportError:
            return 1024  # Default value
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Get comprehensive server statistics"""
        uptime = None
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "running": self.running,
            "host": self.host,
            "port": self.port,
            "uptime_seconds": uptime,
            "connected_clients": len(self.clients),
            "active_sessions": len(self.active_sessions),
            "total_connections": self.total_connections,
            "total_messages": self.total_messages,
            "total_errors": self.total_errors,
            "inference_requests": self.inference_requests,
            "protocol_requests": self.protocol_requests,
            "protocol_stats": self.protocol_manager.get_protocol_stats()
        }


# Utility functions
def create_unified_websocket_server(host: str = "localhost", 
                                  port: int = 8702,
                                  license_validator: Optional[LicenseValidator] = None) -> UnifiedWebSocketServer:
    """Create and return a unified WebSocket server instance"""
    return UnifiedWebSocketServer(host=host, port=port, license_validator=license_validator)


async def run_unified_websocket_server(host: str = "localhost", 
                                     port: int = 8702,
                                     license_validator: Optional[LicenseValidator] = None):
    """Run unified WebSocket server (convenience function)"""
    server = create_unified_websocket_server(host, port, license_validator)
    
    try:
        await server.start()
        logger.info(f"Unified WebSocket server running on ws://{host}:{port}")
        
        # Keep server running
        while server.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        await server.stop()


if __name__ == "__main__":
    # Example usage
    asyncio.run(run_unified_websocket_server())