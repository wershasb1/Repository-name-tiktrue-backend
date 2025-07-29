"""
WebSocket Server Implementation for TikTrue Distributed LLM Platform

This module provides a standardized WebSocket communication protocol with license validation
for the TikTrue Distributed LLM Platform. It handles client connections, message routing,
and protocol enforcement.

Features:
- Standardized message protocol with validation
- License-based authentication and validation
- Message type routing to appropriate handlers
- Heartbeat monitoring for connection health
- Client session management
- Broadcast and targeted messaging capabilities
- Comprehensive statistics tracking

Classes:
    ClientConnection: Class representing a connected client
    WebSocketServer: Main WebSocket server implementation

Functions:
    create_websocket_server: Create and return a WebSocket server instance
    run_websocket_server: Run WebSocket server (convenience function)
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Set, Callable
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebSocketServer")

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, WebSocketException
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.error("WebSockets library not available. Please install: pip install websockets")

from core.protocol_spec import (
    ProtocolManager, ProtocolValidator, MessageType, ErrorCode,
    InferenceRequest, InferenceResponse, HeartbeatMessage, ErrorMessage
)
from license_models import LicenseInfo, ValidationStatus
from security.license_validator import LicenseValidator

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/websocket_server.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class ClientConnection:
    """Represents a connected client"""
    
    def __init__(self, websocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.connected_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self.license_info: Optional[LicenseInfo] = None
        self.session_data: Dict[str, Any] = {}
        self.request_count = 0
        self.error_count = 0
    
    async def send_message(self, message: Any):
        """Send message to client"""
        try:
            if hasattr(message, '__dict__'):
                message_json = json.dumps(message.__dict__, default=str, indent=2)
            else:
                message_json = json.dumps(message, default=str, indent=2)
            
            await self.websocket.send(message_json)
            
        except Exception as e:
            logger.error(f"Failed to send message to client {self.client_id}: {e}")
            raise
    
    def update_heartbeat(self):
        """Update last heartbeat timestamp"""
        self.last_heartbeat = datetime.now()


class WebSocketServer:
    """
    WebSocket server with standardized protocol and license validation
    """
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 8702,
                 license_validator: Optional[LicenseValidator] = None):
        """
        Initialize WebSocket server
        
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
        self.clients: Dict[str, ClientConnection] = {}
        self.active_sessions: Dict[str, str] = {}  # session_id -> client_id
        
        # Server state
        self.server = None
        self.running = False
        self.start_time: Optional[datetime] = None
        
        # Statistics
        self.total_connections = 0
        self.total_messages = 0
        self.total_errors = 0
        
        # Message handlers
        self.message_handlers: Dict[MessageType, Callable] = {
            MessageType.INFERENCE_REQUEST: self._handle_inference_request,
            MessageType.HEARTBEAT: self._handle_heartbeat,
            MessageType.AUTHENTICATION: self._handle_authentication,
            MessageType.LICENSE_CHECK: self._handle_license_check
        }
        
        # Callbacks for external integration
        self.on_inference_request: Optional[Callable[[InferenceRequest, str], InferenceResponse]] = None
        self.on_client_connected: Optional[Callable[[str], None]] = None
        self.on_client_disconnected: Optional[Callable[[str], None]] = None
        
        logger.info(f"WebSocket server initialized on {host}:{port}")
    
    async def start(self):
        """Start the WebSocket server"""
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
            
            logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
            
            # Start background tasks
            asyncio.create_task(self._heartbeat_monitor())
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise
    
    async def stop(self):
        """Stop the WebSocket server"""
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
            
            logger.info("WebSocket server stopped")
    
    async def _handle_client(self, websocket, path):
        """Handle new client connection"""
        client_id = str(uuid.uuid4())
        client = ClientConnection(websocket, client_id)
        
        self.clients[client_id] = client
        self.total_connections += 1
        
        logger.info(f"Client connected: {client_id}")
        
        if self.on_client_connected:
            self.on_client_connected(client_id)
        
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
            if client_id in self.clients:
                del self.clients[client_id]
            
            # Remove from active sessions
            sessions_to_remove = [sid for sid, cid in self.active_sessions.items() if cid == client_id]
            for session_id in sessions_to_remove:
                del self.active_sessions[session_id]
            
            if self.on_client_disconnected:
                self.on_client_disconnected(client_id)
    
    async def _process_message(self, client: ClientConnection, message: str):
        """Process incoming message from client"""
        try:
            self.total_messages += 1
            client.request_count += 1
            
            # Parse and validate message
            message_dict = json.loads(message)
            is_valid, error_msg = self.protocol_validator.validate_message(message_dict)
            
            if not is_valid:
                await self._send_error(client, ErrorCode.VALIDATION_ERROR, f"Message validation failed: {error_msg}")
                return
            
            # Extract message type
            header = message_dict.get("header", {})
            message_type_str = header.get("message_type")
            
            try:
                message_type = MessageType(message_type_str)
            except ValueError:
                await self._send_error(client, ErrorCode.INVALID_REQUEST, f"Unknown message type: {message_type_str}")
                return
            
            # Route to appropriate handler
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](client, message_dict)
            else:
                await self._send_error(client, ErrorCode.INVALID_REQUEST, f"Unsupported message type: {message_type_str}")
            
        except json.JSONDecodeError as e:
            await self._send_error(client, ErrorCode.VALIDATION_ERROR, f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing message from client {client.client_id}: {e}")
            await self._send_error(client, ErrorCode.INTERNAL_ERROR, "Internal server error")
            client.error_count += 1
    
    async def _handle_inference_request(self, client: ClientConnection, message_dict: Dict[str, Any]):
        """Handle inference request"""
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
            
            # Process inference request
            if self.on_inference_request:
                response = await self._call_inference_handler(request, client.client_id)
            else:
                # Default response for testing
                response = self.protocol_manager.create_inference_response(
                    request_id=request.header.message_id,
                    model_id=request.model_id,
                    generated_text="This is a test response from WebSocket server",
                    license_info=client.license_info
                )
            
            # Send response
            await client.send_message(response)
            
        except Exception as e:
            logger.error(f"Error handling inference request: {e}")
            await self._send_error(client, ErrorCode.INTERNAL_ERROR, f"Inference request failed: {e}")
    
    async def _handle_heartbeat(self, client: ClientConnection, message_dict: Dict[str, Any]):
        """Handle heartbeat message"""
        try:
            client.update_heartbeat()
            
            # Create heartbeat response
            response = self.protocol_manager.create_heartbeat(
                worker_id=f"server_{self.host}_{self.port}",
                license_info=client.license_info,
                status="healthy",
                load_percentage=self._get_server_load(),
                available_memory_mb=self._get_available_memory(),
                active_sessions=len(self.active_sessions)
            )
            
            await client.send_message(response)
            
        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")
            await self._send_error(client, ErrorCode.INTERNAL_ERROR, "Heartbeat failed")
    
    async def _handle_authentication(self, client: ClientConnection, message_dict: Dict[str, Any]):
        """Handle authentication message"""
        try:
            # Extract license information from message
            license_key = message_dict.get("license_key")
            if not license_key:
                await self._send_error(client, ErrorCode.AUTHENTICATION_FAILED, "License key required")
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
                await self._send_error(client, ErrorCode.AUTHENTICATION_FAILED, f"License validation failed: {validation_result.status}")
            
        except Exception as e:
            logger.error(f"Error handling authentication: {e}")
            await self._send_error(client, ErrorCode.AUTHENTICATION_FAILED, "Authentication failed")
    
    async def _handle_license_check(self, client: ClientConnection, message_dict: Dict[str, Any]):
        """Handle license check message"""
        try:
            if not client.license_info:
                await self._send_error(client, ErrorCode.LICENSE_EXPIRED, "No license information available")
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
            await self._send_error(client, ErrorCode.INTERNAL_ERROR, "License check failed")
    
    async def _validate_client_license(self, client: ClientConnection, header: Dict[str, Any]) -> bool:
        """Validate client license for request"""
        # Check if license hash is provided
        license_hash = header.get("license_hash")
        if not license_hash:
            await self._send_error(client, ErrorCode.LICENSE_EXPIRED, "License hash required")
            return False
        
        # Check if client has valid license info
        if not client.license_info:
            await self._send_error(client, ErrorCode.LICENSE_EXPIRED, "Client not authenticated")
            return False
        
        # Validate license is still valid
        validation_result = self.security.license_validator.validate_license_key(client.license_info.license_key)
        if validation_result.status != ValidationStatus.VALID:
            await self._send_error(client, ErrorCode.LICENSE_EXPIRED, f"License invalid: {validation_result.status}")
            return False
        
        return True
    
    async def _call_inference_handler(self, request: InferenceRequest, client_id: str) -> InferenceResponse:
        """Call external inference handler"""
        try:
            if asyncio.iscoroutinefunction(self.on_inference_request):
                return await self.on_inference_request(request, client_id)
            else:
                return self.on_inference_request(request, client_id)
        except Exception as e:
            logger.error(f"Inference handler failed: {e}")
            return self.protocol_manager.create_inference_response(
                request_id=request.header.message_id,
                model_id=request.model_id,
                generated_text="",
                error_code=ErrorCode.INTERNAL_ERROR,
                error_message=f"Inference failed: {e}"
            )
    
    async def _send_error(self, client: ClientConnection, error_code: ErrorCode, message: str):
        """Send error message to client"""
        try:
            error_msg = self.protocol_manager.create_error_message(
                error_code=error_code,
                error_message=message,
                license_info=client.license_info
            )
            
            await client.send_message(error_msg)
            
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
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
                        try:
                            await self.clients[client_id].websocket.close()
                        except:
                            pass
                        del self.clients[client_id]
                        logger.info(f"Removed inactive client: {client_id}")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
                await asyncio.sleep(60)
    
    def _get_server_load(self) -> float:
        """Get current server load percentage"""
        # Simple implementation - can be enhanced with actual system metrics
        return min(len(self.clients) * 10.0, 100.0)
    
    def _get_available_memory(self) -> int:
        """Get available memory in MB"""
        # Simple implementation - can be enhanced with actual system metrics
        try:
            import psutil
            return int(psutil.virtual_memory().available / (1024 * 1024))
        except ImportError:
            return 1024  # Default value
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Get server statistics"""
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
            "protocol_stats": self.protocol_manager.get_protocol_stats()
        }
    
    def set_inference_handler(self, handler: Callable[[InferenceRequest, str], InferenceResponse]):
        """Set external inference request handler"""
        self.on_inference_request = handler
    
    def set_client_connected_callback(self, callback: Callable[[str], None]):
        """Set callback for client connection events"""
        self.on_client_connected = callback
    
    def set_client_disconnected_callback(self, callback: Callable[[str], None]):
        """Set callback for client disconnection events"""
        self.on_client_disconnected = callback
    
    async def broadcast_message(self, message: Any, exclude_client: Optional[str] = None):
        """Broadcast message to all connected clients"""
        for client_id, client in self.clients.items():
            if exclude_client and client_id == exclude_client:
                continue
            
            try:
                await client.send_message(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to client {client_id}: {e}")
    
    async def send_to_client(self, client_id: str, message: Any) -> bool:
        """Send message to specific client"""
        if client_id not in self.clients:
            return False
        
        try:
            await self.clients[client_id].send_message(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to client {client_id}: {e}")
            return False


# Utility functions for easy server creation
def create_websocket_server(host: str = "localhost", 
                          port: int = 8702,
                          license_validator: Optional[LicenseValidator] = None) -> WebSocketServer:
    """Create and return a WebSocket server instance"""
    return WebSocketServer(host=host, port=port, license_validator=license_validator)


async def run_websocket_server(host: str = "localhost", 
                             port: int = 8702,
                             license_validator: Optional[LicenseValidator] = None):
    """Run WebSocket server (convenience function)"""
    server = create_websocket_server(host, port, license_validator)
    
    try:
        await server.start()
        logger.info(f"WebSocket server running on ws://{host}:{port}")
        
        # Keep server running
        while server.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        await server.stop()


if __name__ == "__main__":
    # Example usage
    asyncio.run(run_websocket_server())