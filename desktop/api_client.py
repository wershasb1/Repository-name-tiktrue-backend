"""
Enhanced API Client with License Integration
Provides WebSocket-based API client with comprehensive license validation and monitoring
"""

import json
import logging
import asyncio
import time
import hashlib
import glob
import os
from typing import Dict, Any, Optional, List, Callable, Union, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
try:
    import websockets
    from websockets.exceptions import ConnectionClosed, WebSocketException
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    # Fallback for when websockets is not available
    WEBSOCKETS_AVAILABLE = False
    
    class ConnectionClosed(Exception):
        pass
    
    class WebSocketException(Exception):
        pass

# Import our modules
from security.license_validator import LicenseValidator
from license_models import LicenseInfo, SubscriptionTier, ValidationStatus
from license_storage import LicenseStorage
from core.protocol_spec import (
    InferenceRequest, InferenceResponse, HeartbeatRequest, HeartbeatResponse,
    ErrorResponse, ProtocolValidator, MessageType, ResponseStatus,
    LicenseStatusProtocol as ProtocolLicenseStatus, create_inference_request, create_inference_response
)
try:
    from utils.serialization_utils import tensor_to_json_serializable, json_serializable_to_tensor
    SERIALIZATION_AVAILABLE = True
except ImportError:
    SERIALIZATION_AVAILABLE = False
    # Fallback serialization functions
    def tensor_to_json_serializable(tensor):
        return tensor  # Pass through for demo
    
    def json_serializable_to_tensor(data):
        return data  # Pass through for demo

logger = logging.getLogger("APIClient")


class ConnectionStatus(Enum):
    """Connection status enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class LicenseErrorType(Enum):
    """License error types"""
    INVALID_LICENSE = "invalid_license"
    EXPIRED_LICENSE = "expired_license"
    CLIENT_LIMIT_EXCEEDED = "client_limit_exceeded"
    MODEL_ACCESS_DENIED = "model_access_denied"
    FEATURE_ACCESS_DENIED = "feature_access_denied"
    HARDWARE_MISMATCH = "hardware_mismatch"


# Legacy compatibility aliases - these are now handled by protocol_spec.py
# APIRequest and APIResponse are replaced by InferenceRequest and InferenceResponse


@dataclass
class NetworkConfig:
    """Network configuration data structure"""
    network_id: str
    model_id: str
    host: str
    port: int
    model_chain_order: List[str]
    paths: Dict[str, str]
    nodes: Dict[str, Any]
    
    @classmethod
    def from_file(cls, config_path: str) -> 'NetworkConfig':
        """Load network configuration from JSON file"""
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        # Extract primary node information
        primary_node = list(data['nodes'].values())[0]
        
        return cls(
            network_id=data.get('network_id', os.path.basename(config_path).replace('.json', '')),
            model_id=data.get('model_id', 'unknown'),
            host=primary_node.get('host', 'localhost'),
            port=primary_node.get('port', 8702),
            model_chain_order=data.get('model_chain_order', []),
            paths=data.get('paths', {}),
            nodes=data.get('nodes', {})
        )


@dataclass
class NetworkConnection:
    """Individual network connection state"""
    config: NetworkConfig
    client: Optional['LicenseAwareAPIClient'] = None
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    last_heartbeat: Optional[datetime] = None
    error_count: int = 0
    session_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.session_data is None:
            self.session_data = {}


class NetworkFailoverStrategy(Enum):
    """Network failover strategies"""
    ROUND_ROBIN = "round_robin"
    PRIORITY_BASED = "priority_based"
    LOAD_BALANCED = "load_balanced"
    FASTEST_RESPONSE = "fastest_response"


class LicenseAwareAPIClient:
    """
    Enhanced API client with comprehensive license integration
    Handles WebSocket communication with automatic license validation and monitoring
    """
    
    def __init__(self, 
                 server_host: str = "localhost",
                 server_port: int = 8702,
                 license_storage: Optional[LicenseStorage] = None,
                 auto_reconnect: bool = True,
                 max_retries: int = 3,
                 retry_delay: float = 1.0,
                 heartbeat_interval: float = 30.0):
        """
        Initialize API client
        
        Args:
            server_host: WebSocket server host
            server_port: WebSocket server port
            license_storage: License storage instance
            auto_reconnect: Enable automatic reconnection
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries
        """
        self.server_host = server_host
        self.server_port = server_port
        self.server_uri = f"ws://{server_host}:{server_port}"
        
        # License management
        self.license_storage = license_storage or LicenseStorage()
        self.license_validator = LicenseValidator()
        self.current_license: Optional[LicenseInfo] = None
        self.license_hash: Optional[str] = None
        
        # Connection management
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.auto_reconnect = auto_reconnect
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_count = 0
        
        # Monitoring
        self.last_license_check = datetime.now()
        self.license_check_interval = timedelta(minutes=5)
        self.connection_start_time: Optional[datetime] = None
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
        # Callbacks
        self.on_license_error: Optional[Callable[[LicenseErrorType, str], None]] = None
        self.on_connection_status_changed: Optional[Callable[[ConnectionStatus], None]] = None
        self.on_license_renewal_needed: Optional[Callable[[LicenseInfo], None]] = None
        
        # Load initial license
        self.load_license()
    
    def load_license(self) -> bool:
        """
        Load license information from storage
        
        Returns:
            True if license loaded successfully, False otherwise
        """
        try:
            self.current_license = self.license_storage.load_license_info()
            
            if self.current_license:
                # Generate license hash for requests
                self.license_hash = self._generate_license_hash(self.current_license.license_key)
                
                # Validate license
                validation_result = self.security.license_validator.validate_license_key(self.current_license.license_key)
                
                if validation_result.status == ValidationStatus.VALID:
                    logger.info(f"License loaded successfully: {self.current_license.plan_type}")
                    return True
                else:
                    logger.warning(f"Invalid license loaded: {validation_result.status}")
                    self._handle_license_error(LicenseErrorType.INVALID_LICENSE, f"License validation failed: {validation_result.status}")
                    return False
            else:
                logger.warning("No license found in storage")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load license: {e}")
            return False
    
    def _generate_license_hash(self, license_key: str) -> str:
        """Generate hash for license key"""
        return hashlib.sha256(license_key.encode()).hexdigest()[:16]
    
    def _handle_license_error(self, error_type: LicenseErrorType, message: str):
        """Handle license errors"""
        logger.error(f"License error ({error_type.value}): {message}")
        
        if self.on_license_error:
            self.on_license_error(error_type, message)
    
    def _update_connection_status(self, status: ConnectionStatus):
        """Update connection status and notify callbacks"""
        if self.connection_status != status:
            self.connection_status = status
            logger.info(f"Connection status changed: {status.value}")
            
            if self.on_connection_status_changed:
                self.on_connection_status_changed(status)
    
    async def connect(self) -> bool:
        """
        Establish WebSocket connection
        
        Returns:
            True if connected successfully, False otherwise
        """
        if self.connection_status == ConnectionStatus.CONNECTED:
            return True
        
        self._update_connection_status(ConnectionStatus.CONNECTING)
        
        try:
            # Check if websockets is available
            if not WEBSOCKETS_AVAILABLE:
                logger.error("WebSockets library not available. Please install: pip install websockets")
                self._update_connection_status(ConnectionStatus.ERROR)
                return False
            
            # Check license before connecting
            if not self.current_license:
                self._handle_license_error(LicenseErrorType.INVALID_LICENSE, "No license available")
                self._update_connection_status(ConnectionStatus.ERROR)
                return False
            
            # Validate license expiry
            if not self.security.license_validator.check_expiry(self.current_license):
                self._handle_license_error(LicenseErrorType.EXPIRED_LICENSE, "License has expired")
                self._update_connection_status(ConnectionStatus.ERROR)
                return False
            
            # Establish WebSocket connection
            self.websocket = await websockets.connect(
                self.server_uri,
                max_size=None,
                ping_interval=180,
                ping_timeout=600,
                close_timeout=1200
            )
            
            self.connection_start_time = datetime.now()
            self.retry_count = 0
            self._update_connection_status(ConnectionStatus.CONNECTED)
            
            logger.info(f"Connected to {self.server_uri}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.server_uri}: {e}")
            self._update_connection_status(ConnectionStatus.ERROR)
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket server"""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.websocket = None
                self.connection_start_time = None
                self._update_connection_status(ConnectionStatus.DISCONNECTED)
    
    async def _ensure_connected(self) -> bool:
        """Ensure connection is established"""
        if self.connection_status == ConnectionStatus.CONNECTED and self.websocket:
            return True
        
        return await self.connect()
    
    def _check_license_renewal(self):
        """Check if license renewal is needed"""
        if not self.current_license:
            return
        
        now = datetime.now()
        
        # Check if it's time to validate license
        if now - self.last_license_check > self.license_check_interval:
            self.last_license_check = now
            
            # Check expiry
            if not self.security.license_validator.check_expiry(self.current_license):
                self._handle_license_error(LicenseErrorType.EXPIRED_LICENSE, "License has expired")
                return
            
            # Check if renewal is needed soon (within 7 days)
            days_until_expiry = (self.current_license.expires_at - now).days
            if days_until_expiry <= 7 and self.on_license_renewal_needed:
                self.on_license_renewal_needed(self.current_license)
    
    def _validate_request_permissions(self, request: InferenceRequest) -> Optional[str]:
        """
        Validate request permissions against license
        
        Returns:
            Error message if validation fails, None if valid
        """
        if not self.current_license:
            return "No valid license"
        
        # Check model access
        if request.model_id:
            if not self.security.license_validator.enforce_subscription_limits(
                "model_access", self.current_license, model_id=request.model_id
            ):
                return f"Model access denied: {request.model_id}"
        
        return None
    
    async def send_request(self, request: InferenceRequest, timeout: float = 30.0) -> InferenceResponse:
        """
        Send API request with license validation
        
        Args:
            request: API request to send
            timeout: Request timeout in seconds
            
        Returns:
            API response
        """
        self.total_requests += 1
        start_time = time.time()
        
        try:
            # Check license renewal
            self._check_license_renewal()
            
            # Validate request permissions
            permission_error = self._validate_request_permissions(request)
            if permission_error:
                self.failed_requests += 1
                return create_inference_response(
                    session_id=request.session_id,
                    network_id=request.network_id,
                    step=request.step,
                    status=ResponseStatus.LICENSE_ERROR.value,
                    license_status=ProtocolLicenseStatus.PERMISSION_DENIED.value,
                    error=permission_error,
                    processing_time=time.time() - start_time
                )
            
            # Ensure connection
            if not await self._ensure_connected():
                self.failed_requests += 1
                return create_inference_response(
                    session_id=request.session_id,
                    network_id=request.network_id,
                    step=request.step,
                    status=ResponseStatus.CONNECTION_ERROR.value,
                    license_status=ProtocolLicenseStatus.UNKNOWN.value,
                    error="Failed to establish connection",
                    processing_time=time.time() - start_time
                )
            
            # Add license hash to request
            request.license_hash = self.license_hash
            
            # Send request
            request_data = request.to_dict()
            await self.websocket.send(json.dumps(request_data, default=str))
            
            # Wait for response with timeout
            try:
                response_data = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=timeout
                )
                
                # Parse response using standardized protocol
                parsed_message = ProtocolValidator.parse_message(response_data)
                
                if isinstance(parsed_message, ErrorResponse):
                    self.failed_requests += 1
                    return create_inference_response(
                        session_id=request.session_id,
                        network_id=request.network_id,
                        step=request.step,
                        status=ResponseStatus.ERROR.value,
                        license_status=parsed_message.license_status,
                        error=parsed_message.error,
                        processing_time=time.time() - start_time
                    )
                
                if isinstance(parsed_message, InferenceResponse):
                    # Set processing time
                    parsed_message.processing_time = time.time() - start_time
                    
                    # Handle license errors in response
                    if parsed_message.status == ResponseStatus.LICENSE_ERROR.value:
                        self.failed_requests += 1
                        self._handle_license_error_from_response(parsed_message)
                    else:
                        self.successful_requests += 1
                    
                    return parsed_message
                else:
                    # Unexpected message type
                    self.failed_requests += 1
                    return create_inference_response(
                        session_id=request.session_id,
                        network_id=request.network_id,
                        step=request.step,
                        status=ResponseStatus.ERROR.value,
                        license_status=ProtocolLicenseStatus.UNKNOWN.value,
                        error=f"Unexpected response type: {type(parsed_message).__name__}",
                        processing_time=time.time() - start_time
                    )
                
            except asyncio.TimeoutError:
                self.failed_requests += 1
                return create_inference_response(
                    session_id=request.session_id,
                    network_id=request.network_id,
                    step=request.step,
                    status=ResponseStatus.TIMEOUT.value,
                    license_status=ProtocolLicenseStatus.UNKNOWN.value,
                    error=f"Request timeout after {timeout} seconds",
                    processing_time=time.time() - start_time
                )
                
        except ConnectionClosed:
            self.failed_requests += 1
            self._update_connection_status(ConnectionStatus.DISCONNECTED)
            
            # Try to reconnect if auto-reconnect is enabled
            if self.auto_reconnect and self.retry_count < self.max_retries:
                self.retry_count += 1
                await asyncio.sleep(self.retry_delay)
                return await self.send_request(request, timeout)
            
            return create_inference_response(
                session_id=request.session_id,
                network_id=request.network_id,
                step=request.step,
                status=ResponseStatus.CONNECTION_ERROR.value,
                license_status=ProtocolLicenseStatus.UNKNOWN.value,
                error="Connection closed",
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            self.failed_requests += 1
            logger.error(f"Request failed: {e}")
            
            return create_inference_response(
                session_id=request.session_id,
                network_id=request.network_id,
                step=request.step,
                status=ResponseStatus.ERROR.value,
                license_status=ProtocolLicenseStatus.UNKNOWN.value,
                error=str(e),
                processing_time=time.time() - start_time
            )
    
    def _handle_license_error_from_response(self, response: InferenceResponse):
        """Handle license errors from server response"""
        license_status = response.license_status
        
        if license_status == ProtocolLicenseStatus.INVALID.value:
            self._handle_license_error(LicenseErrorType.INVALID_LICENSE, response.error or "Invalid license")
        elif license_status == ProtocolLicenseStatus.EXPIRED.value:
            self._handle_license_error(LicenseErrorType.EXPIRED_LICENSE, response.error or "License expired")
        elif license_status == ProtocolLicenseStatus.CLIENT_LIMIT_EXCEEDED.value:
            self._handle_license_error(LicenseErrorType.CLIENT_LIMIT_EXCEEDED, response.error or "Client limit exceeded")
        elif license_status == ProtocolLicenseStatus.MODEL_ACCESS_DENIED.value:
            self._handle_license_error(LicenseErrorType.MODEL_ACCESS_DENIED, response.error or "Model access denied")
        elif license_status == ProtocolLicenseStatus.HARDWARE_MISMATCH.value:
            self._handle_license_error(LicenseErrorType.HARDWARE_MISMATCH, response.error or "Hardware mismatch")
    
    async def send_inference_request(self, 
                                   session_id: str,
                                   input_tensors: Dict[str, Any],
                                   model_id: Optional[str] = None,
                                   network_id: str = "default",
                                   step: int = 0,
                                   timeout: float = 30.0) -> InferenceResponse:
        """
        Send inference request (convenience method)
        
        Args:
            session_id: Session identifier
            input_tensors: Input tensors for inference
            model_id: Model identifier (optional)
            network_id: Network identifier
            step: Step number
            timeout: Request timeout
            
        Returns:
            Inference response
        """
        request = create_inference_request(
            session_id=session_id,
            network_id=network_id,
            license_hash=self.license_hash or "",
            input_tensors=input_tensors,
            step=step,
            model_id=model_id
        )
        
        return await self.send_request(request, timeout)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        uptime = None
        if self.connection_start_time:
            uptime = (datetime.now() - self.connection_start_time).total_seconds()
        
        success_rate = 0.0
        if self.total_requests > 0:
            success_rate = self.successful_requests / self.total_requests
        
        return {
            "status": self.connection_status.value,
            "server_uri": self.server_uri,
            "uptime_seconds": uptime,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "retry_count": self.retry_count,
            "license_plan": self.current_license.plan.value if self.current_license else None,
            "license_expires_at": self.current_license.expires_at.isoformat() if self.current_license else None
        }
    
    def get_license_status(self) -> Dict[str, Any]:
        """Get current license status"""
        if not self.current_license:
            return {
                "valid": False,
                "status": "no_license",
                "message": "No license loaded"
            }
        
        # Validate current license
        validation_result = self.security.license_validator.validate_license_key(self.current_license.license_key)
        
        return {
            "valid": validation_result.status == ValidationStatus.VALID,
            "status": validation_result.status.value,
            "plan": self.current_license.plan.value,
            "expires_at": self.current_license.expires_at.isoformat(),
            "max_clients": self.current_license.max_clients,
            "allowed_models": self.current_license.allowed_models,
            "allowed_features": self.current_license.allowed_features,
            "days_remaining": (self.current_license.expires_at - datetime.now()).days
        }
    
    async def install_license(self, license_key: str) -> bool:
        """
        Install new license
        
        Args:
            license_key: License key to install
            
        Returns:
            True if license installed successfully, False otherwise
        """
        try:
            # Validate license
            validation_result = self.security.license_validator.validate_license_key(license_key)
            
            if validation_result.status != ValidationStatus.VALID:
                self._handle_license_error(LicenseErrorType.INVALID_LICENSE, f"License validation failed: {validation_result.status}")
                return False
            
            # Save license
            if self.license_storage.save_license_locally(validation_result):
                self.current_license = validation_result
                self.license_hash = self._generate_license_hash(license_key)
                logger.info(f"License installed successfully: {validation_result.plan.value}")
                return True
            else:
                logger.error("Failed to save license to storage")
                return False
                
        except Exception as e:
            logger.error(f"Failed to install license: {e}")
            return False
    
    async def refresh_license(self) -> bool:
        """
        Refresh license from storage
        
        Returns:
            True if license refreshed successfully, False otherwise
        """
        return self.load_license()
    
    def set_license_error_callback(self, callback: Callable[[LicenseErrorType, str], None]):
        """Set callback for license errors"""
        self.on_license_error = callback
    
    def set_connection_status_callback(self, callback: Callable[[ConnectionStatus], None]):
        """Set callback for connection status changes"""
        self.on_connection_status_changed = callback
    
    def set_license_renewal_callback(self, callback: Callable[[LicenseInfo], None]):
        """Set callback for license renewal notifications"""
        self.on_license_renewal_needed = callback
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()


class MultiNetworkAPIClient:
    """
    Multi-network API client with routing capabilities
    Manages multiple network connections simultaneously with failover support
    """
    
    def __init__(self, 
                 license_storage: Optional[LicenseStorage] = None,
                 failover_strategy: NetworkFailoverStrategy = NetworkFailoverStrategy.PRIORITY_BASED,
                 heartbeat_interval: float = 30.0,
                 max_error_count: int = 3):
        """
        Initialize multi-network API client
        
        Args:
            license_storage: License storage instance
            failover_strategy: Strategy for network failover
            heartbeat_interval: Interval for heartbeat checks in seconds
            max_error_count: Maximum errors before marking network as failed
        """
        # License management
        self.license_storage = license_storage or LicenseStorage()
        self.license_validator = LicenseValidator()
        self.current_license: Optional[LicenseInfo] = None
        self.license_hash: Optional[str] = None
        
        # Network management
        self.networks: Dict[str, NetworkConnection] = {}
        self.active_networks: Set[str] = set()
        self.primary_network: Optional[str] = None
        self.failover_strategy = failover_strategy
        self.heartbeat_interval = heartbeat_interval
        self.max_error_count = max_error_count
        
        # Session management
        self.sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> session_data
        self.network_sessions: Dict[str, Set[str]] = {}  # network_id -> set of session_ids
        
        # Monitoring
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.last_license_check = datetime.now()
        self.license_check_interval = timedelta(minutes=5)
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.network_stats: Dict[str, Dict[str, int]] = {}
        
        # Callbacks
        self.on_network_status_changed: Optional[Callable[[str, ConnectionStatus], None]] = None
        self.on_license_error: Optional[Callable[[LicenseErrorType, str], None]] = None
        self.on_failover_triggered: Optional[Callable[[str, str], None]] = None
        
        # Load initial license
        self.load_license()
    
    def load_license(self) -> bool:
        """Load license information from storage"""
        try:
            self.current_license = self.license_storage.load_license_info()
            
            if self.current_license:
                self.license_hash = hashlib.sha256(self.current_license.license_key.encode()).hexdigest()[:16]
                
                validation_result = self.security.license_validator.validate_license_key(self.current_license.license_key)
                
                if validation_result.status == ValidationStatus.VALID:
                    logger.info(f"License loaded successfully: {self.current_license.plan_type}")
                    return True
                else:
                    logger.warning(f"Invalid license loaded: {validation_result.status}")
                    return False
            else:
                logger.warning("No license found in storage")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load license: {e}")
            return False
    
    def discover_networks(self, config_pattern: str = "network_config*.json") -> List[NetworkConfig]:
        """
        Discover available networks from configuration files
        
        Args:
            config_pattern: Glob pattern for network config files
            
        Returns:
            List of discovered network configurations
        """
        networks = []
        
        try:
            config_files = glob.glob(config_pattern)
            
            for config_file in config_files:
                try:
                    network_config = NetworkConfig.from_file(config_file)
                    networks.append(network_config)
                    logger.info(f"Discovered network: {network_config.network_id} ({network_config.model_id})")
                except Exception as e:
                    logger.error(f"Failed to load network config {config_file}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to discover networks: {e}")
        
        return networks
    
    async def add_network(self, network_config: NetworkConfig, set_as_primary: bool = False) -> bool:
        """
        Add a network to the client
        
        Args:
            network_config: Network configuration
            set_as_primary: Set this network as primary
            
        Returns:
            True if network added successfully
        """
        try:
            # Create individual API client for this network
            client = LicenseAwareAPIClient(
                server_host=network_config.host,
                server_port=network_config.port,
                license_storage=self.license_storage,
                auto_reconnect=True
            )
            
            # Create network connection
            connection = NetworkConnection(
                config=network_config,
                client=client,
                status=ConnectionStatus.DISCONNECTED
            )
            
            self.networks[network_config.network_id] = connection
            self.network_stats[network_config.network_id] = {
                "requests": 0,
                "successes": 0,
                "failures": 0,
                "avg_response_time": 0.0
            }
            self.network_sessions[network_config.network_id] = set()
            
            if set_as_primary or self.primary_network is None:
                self.primary_network = network_config.network_id
            
            logger.info(f"Added network: {network_config.network_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add network {network_config.network_id}: {e}")
            return False
    
    async def connect_to_network(self, network_id: str) -> bool:
        """
        Connect to a specific network
        
        Args:
            network_id: Network identifier
            
        Returns:
            True if connected successfully
        """
        if network_id not in self.networks:
            logger.error(f"Network {network_id} not found")
            return False
        
        connection = self.networks[network_id]
        
        try:
            if await connection.client.connect():
                connection.status = ConnectionStatus.CONNECTED
                connection.last_heartbeat = datetime.now()
                connection.error_count = 0
                self.active_networks.add(network_id)
                
                if self.on_network_status_changed:
                    self.on_network_status_changed(network_id, ConnectionStatus.CONNECTED)
                
                logger.info(f"Connected to network: {network_id}")
                return True
            else:
                connection.status = ConnectionStatus.ERROR
                connection.error_count += 1
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to network {network_id}: {e}")
            connection.status = ConnectionStatus.ERROR
            connection.error_count += 1
            return False
    
    async def connect_all_networks(self) -> Dict[str, bool]:
        """
        Connect to all configured networks
        
        Returns:
            Dictionary mapping network_id to connection success status
        """
        results = {}
        
        for network_id in self.networks:
            results[network_id] = await self.connect_to_network(network_id)
        
        # Start heartbeat monitoring if any networks are connected
        if self.active_networks and not self.heartbeat_task:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        
        return results
    
    async def disconnect_from_network(self, network_id: str):
        """Disconnect from a specific network"""
        if network_id not in self.networks:
            return
        
        connection = self.networks[network_id]
        
        try:
            await connection.client.disconnect()
            connection.status = ConnectionStatus.DISCONNECTED
            self.active_networks.discard(network_id)
            
            if self.on_network_status_changed:
                self.on_network_status_changed(network_id, ConnectionStatus.DISCONNECTED)
            
            logger.info(f"Disconnected from network: {network_id}")
            
        except Exception as e:
            logger.error(f"Error disconnecting from network {network_id}: {e}")
    
    async def disconnect_all_networks(self):
        """Disconnect from all networks"""
        # Stop heartbeat monitoring
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None
        
        # Disconnect from all networks
        for network_id in list(self.networks.keys()):
            await self.disconnect_from_network(network_id)
    
    def select_network_for_request(self, preferred_network: Optional[str] = None) -> Optional[str]:
        """
        Select the best network for a request based on failover strategy
        
        Args:
            preferred_network: Preferred network ID
            
        Returns:
            Selected network ID or None if no networks available
        """
        # If preferred network is specified and available, use it
        if preferred_network and preferred_network in self.active_networks:
            connection = self.networks[preferred_network]
            if connection.status == ConnectionStatus.CONNECTED and connection.error_count < self.max_error_count:
                return preferred_network
        
        # Filter available networks
        available_networks = [
            network_id for network_id in self.active_networks
            if self.networks[network_id].status == ConnectionStatus.CONNECTED
            and self.networks[network_id].error_count < self.max_error_count
        ]
        
        if not available_networks:
            return None
        
        # Apply failover strategy
        if self.failover_strategy == NetworkFailoverStrategy.PRIORITY_BASED:
            # Use primary network first, then others
            if self.primary_network and self.primary_network in available_networks:
                return self.primary_network
            return available_networks[0]
        
        elif self.failover_strategy == NetworkFailoverStrategy.ROUND_ROBIN:
            # Simple round-robin selection
            return available_networks[self.total_requests % len(available_networks)]
        
        elif self.failover_strategy == NetworkFailoverStrategy.LOAD_BALANCED:
            # Select network with lowest request count
            return min(available_networks, 
                      key=lambda nid: self.network_stats[nid]["requests"])
        
        elif self.failover_strategy == NetworkFailoverStrategy.FASTEST_RESPONSE:
            # Select network with best average response time
            return min(available_networks,
                      key=lambda nid: self.network_stats[nid]["avg_response_time"])
        
        return available_networks[0]
    
    async def send_inference_request(self,
                                   session_id: str,
                                   input_tensors: Dict[str, Any],
                                   model_id: Optional[str] = None,
                                   preferred_network: Optional[str] = None,
                                   step: int = 0,
                                   timeout: float = 30.0) -> InferenceResponse:
        """
        Send inference request with automatic network selection and failover
        
        Args:
            session_id: Session identifier
            input_tensors: Input tensors for inference
            model_id: Model identifier
            preferred_network: Preferred network ID
            step: Step number
            timeout: Request timeout
            
        Returns:
            Inference response
        """
        self.total_requests += 1
        start_time = time.time()
        
        # Select network for request
        selected_network = self.select_network_for_request(preferred_network)
        
        if not selected_network:
            self.failed_requests += 1
            return create_inference_response(
                session_id=session_id,
                network_id=preferred_network or "unknown",
                step=step,
                status=ResponseStatus.CONNECTION_ERROR.value,
                license_status=ProtocolLicenseStatus.UNKNOWN.value,
                error="No available networks",
                processing_time=time.time() - start_time
            )
        
        # Update session tracking
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "created_at": datetime.now(),
                "last_network": selected_network,
                "request_count": 0
            }
        
        self.sessions[session_id]["request_count"] += 1
        self.sessions[session_id]["last_network"] = selected_network
        self.network_sessions[selected_network].add(session_id)
        
        # Update network stats
        self.network_stats[selected_network]["requests"] += 1
        
        try:
            # Send request to selected network
            connection = self.networks[selected_network]
            response = await connection.client.send_inference_request(
                session_id=session_id,
                input_tensors=input_tensors,
                model_id=model_id,
                network_id=selected_network,
                step=step,
                timeout=timeout
            )
            
            # Update statistics
            processing_time = time.time() - start_time
            
            if response.status == ResponseStatus.SUCCESS.value:
                self.successful_requests += 1
                self.network_stats[selected_network]["successes"] += 1
                connection.error_count = 0  # Reset error count on success
            else:
                self.failed_requests += 1
                self.network_stats[selected_network]["failures"] += 1
                connection.error_count += 1
                
                # Trigger failover if error count exceeds threshold
                if connection.error_count >= self.max_error_count:
                    await self._trigger_failover(selected_network)
            
            # Update average response time
            stats = self.network_stats[selected_network]
            total_requests = stats["requests"]
            current_avg = stats["avg_response_time"]
            stats["avg_response_time"] = ((current_avg * (total_requests - 1)) + processing_time) / total_requests
            
            return response
            
        except Exception as e:
            self.failed_requests += 1
            self.network_stats[selected_network]["failures"] += 1
            
            connection = self.networks[selected_network]
            connection.error_count += 1
            
            logger.error(f"Request failed on network {selected_network}: {e}")
            
            # Try failover to another network
            if connection.error_count >= self.max_error_count:
                await self._trigger_failover(selected_network)
                
                # Retry with different network
                fallback_network = self.select_network_for_request()
                if fallback_network and fallback_network != selected_network:
                    logger.info(f"Retrying request on fallback network: {fallback_network}")
                    return await self.send_inference_request(
                        session_id=session_id,
                        input_tensors=input_tensors,
                        model_id=model_id,
                        preferred_network=fallback_network,
                        step=step,
                        timeout=timeout
                    )
            
            return create_inference_response(
                session_id=session_id,
                network_id=selected_network,
                step=step,
                status=ResponseStatus.ERROR.value,
                license_status=ProtocolLicenseStatus.UNKNOWN.value,
                error=str(e),
                processing_time=time.time() - start_time
            )
    
    async def _trigger_failover(self, failed_network: str):
        """Trigger failover from a failed network"""
        logger.warning(f"Triggering failover from network: {failed_network}")
        
        # Mark network as failed
        if failed_network in self.active_networks:
            self.active_networks.remove(failed_network)
        
        connection = self.networks[failed_network]
        connection.status = ConnectionStatus.ERROR
        
        if self.on_network_status_changed:
            self.on_network_status_changed(failed_network, ConnectionStatus.ERROR)
        
        # Select new primary if needed
        if self.primary_network == failed_network:
            available_networks = [
                nid for nid in self.active_networks
                if self.networks[nid].status == ConnectionStatus.CONNECTED
            ]
            
            if available_networks:
                self.primary_network = available_networks[0]
                logger.info(f"New primary network: {self.primary_network}")
                
                if self.on_failover_triggered:
                    self.on_failover_triggered(failed_network, self.primary_network)
    
    async def _heartbeat_monitor(self):
        """Monitor network health with heartbeat checks"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                for network_id in list(self.active_networks):
                    connection = self.networks[network_id]
                    
                    try:
                        # Send heartbeat request
                        heartbeat_request = HeartbeatRequest(
                            network_id=network_id,
                            license_hash=self.license_hash or "",
                            node_id="client"
                        )
                        
                        # Use the underlying client to send heartbeat
                        if connection.client.websocket:
                            await connection.client.websocket.send(heartbeat_request.to_json())
                            
                            # Wait for response with short timeout
                            try:
                                response_data = await asyncio.wait_for(
                                    connection.client.websocket.recv(),
                                    timeout=5.0
                                )
                                
                                parsed_response = ProtocolValidator.parse_message(response_data)
                                
                                if isinstance(parsed_response, HeartbeatResponse):
                                    connection.last_heartbeat = datetime.now()
                                    connection.error_count = max(0, connection.error_count - 1)  # Reduce error count on successful heartbeat
                                else:
                                    connection.error_count += 1
                                    
                            except asyncio.TimeoutError:
                                connection.error_count += 1
                                logger.warning(f"Heartbeat timeout for network: {network_id}")
                        else:
                            # Connection lost
                            connection.error_count += 1
                            
                    except Exception as e:
                        connection.error_count += 1
                        logger.error(f"Heartbeat failed for network {network_id}: {e}")
                    
                    # Check if network should be marked as failed
                    if connection.error_count >= self.max_error_count:
                        await self._trigger_failover(network_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")
    
    def get_network_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all networks"""
        status = {}
        
        for network_id, connection in self.networks.items():
            stats = self.network_stats.get(network_id, {})
            
            status[network_id] = {
                "config": {
                    "model_id": connection.config.model_id,
                    "host": connection.config.host,
                    "port": connection.config.port
                },
                "status": connection.status.value,
                "is_active": network_id in self.active_networks,
                "is_primary": network_id == self.primary_network,
                "error_count": connection.error_count,
                "last_heartbeat": connection.last_heartbeat.isoformat() if connection.last_heartbeat else None,
                "statistics": stats,
                "active_sessions": len(self.network_sessions.get(network_id, set()))
            }
        
        return status
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific session"""
        if session_id not in self.sessions:
            return None
        
        session_data = self.sessions[session_id].copy()
        session_data["created_at"] = session_data["created_at"].isoformat()
        
        return session_data
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall client statistics"""
        success_rate = 0.0
        if self.total_requests > 0:
            success_rate = self.successful_requests / self.total_requests
        
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "active_networks": len(self.active_networks),
            "total_networks": len(self.networks),
            "primary_network": self.primary_network,
            "failover_strategy": self.failover_strategy.value,
            "active_sessions": len(self.sessions),
            "license_plan": self.current_license.plan.value if self.current_license else None
        }
    
    def set_network_status_callback(self, callback: Callable[[str, ConnectionStatus], None]):
        """Set callback for network status changes"""
        self.on_network_status_changed = callback
    
    def set_license_error_callback(self, callback: Callable[[LicenseErrorType, str], None]):
        """Set callback for license errors"""
        self.on_license_error = callback
    
    def set_failover_callback(self, callback: Callable[[str, str], None]):
        """Set callback for failover events"""
        self.on_failover_triggered = callback
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect_all_networks()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect_all_networks()


# Utility functions for easy integration

async def create_api_client(server_host: str = "localhost", 
                          server_port: int = 8702,
                          auto_connect: bool = True) -> LicenseAwareAPIClient:
    """
    Create and optionally connect API client
    
    Args:
        server_host: WebSocket server host
        server_port: WebSocket server port
        auto_connect: Automatically connect after creation
        
    Returns:
        API client instance
    """
    client = LicenseAwareAPIClient(server_host, server_port)
    
    if auto_connect:
        await client.connect()
    
    return client


def create_inference_request_legacy(session_id: str,
                                   input_tensors: Dict[str, Any],
                                   model_id: Optional[str] = None,
                                   network_id: str = "default",
                                   step: int = 0) -> InferenceRequest:
    """
    Create inference request (legacy convenience function)
    
    Args:
        session_id: Session identifier
        input_tensors: Input tensors
        model_id: Model identifier
        network_id: Network identifier
        step: Step number
        
    Returns:
        Inference request object
    """
    return create_inference_request(
        session_id=session_id,
        network_id=network_id,
        license_hash="",  # Will be set by client
        input_tensors=input_tensors,
        step=step,
        model_id=model_id
    )


if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def main():
        # Create API client
        client = LicenseAwareAPIClient()
        
        # Set up callbacks
        def on_license_error(error_type: LicenseErrorType, message: str):
            print(f"License Error: {error_type.value} - {message}")
        
        def on_connection_status(status: ConnectionStatus):
            print(f"Connection Status: {status.value}")
        
        client.set_license_error_callback(on_license_error)
        client.set_connection_status_callback(on_connection_status)
        
        try:
            # Connect to server
            if await client.connect():
                print("Connected successfully!")
                
                # Send test request
                response = await client.send_inference_request(
                    session_id="test_session",
                    input_tensors={"input_ids": [[1, 2, 3, 4, 5]]},
                    model_id="llama-7b"
                )
                
                print(f"Response: {response.status}")
                print(f"License Status: {response.license_status}")
                
                # Get stats
                stats = client.get_connection_stats()
                print(f"Connection Stats: {stats}")
                
                license_status = client.get_license_status()
                print(f"License Status: {license_status}")
                
            else:
                print("Failed to connect")
                
        finally:
            await client.disconnect()
    
    # Run example
    asyncio.run(main())