"""
Enhanced Network Manager for TikTrue Distributed LLM Platform
Handles network discovery, creation, and management with license integration
"""

import asyncio
import json
import logging
import socket
import struct
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import threading

from license_enforcer import get_license_enforcer, validate_client_connection
from license_models import SubscriptionTier, ValidationStatus

logger = logging.getLogger("NetworkManager")


class NetworkType(Enum):
    """Network type definitions"""
    PUBLIC = "public"
    PRIVATE = "private"
    ENTERPRISE = "enterprise"


class NetworkStatus(Enum):
    """Network status definitions"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    RESTRICTED = "restricted"


@dataclass
class NetworkInfo:
    """Network information structure"""
    network_id: str
    network_name: str
    network_type: NetworkType
    admin_node_id: str
    admin_host: str
    admin_port: int
    model_id: str
    model_name: str
    required_license_tier: SubscriptionTier
    max_clients: int
    current_clients: int
    status: NetworkStatus
    created_at: datetime
    last_seen: datetime
    description: str = ""
    version: str = "1.0"


@dataclass
class JoinRequest:
    """Network join request structure"""
    request_id: str
    client_id: str
    client_host: str
    client_port: int
    network_id: str
    license_tier: SubscriptionTier
    requested_at: datetime
    message: str = ""


@dataclass
class JoinResponse:
    """Network join response structure"""
    request_id: str
    approved: bool
    network_config: Optional[Dict[str, Any]]
    reason: str = ""
    admin_message: str = ""


class NetworkManager:
    """
    Enhanced network management with license integration
    Handles network discovery, creation, joining, and management
    """
    
    # Network discovery constants
    DISCOVERY_PORT = 8700
    DISCOVERY_MULTICAST_GROUP = "239.255.255.250"
    DISCOVERY_TIMEOUT = 5.0
    DISCOVERY_RETRY_COUNT = 3
    
    # Network protocol constants
    PROTOCOL_VERSION = "1.0"
    MESSAGE_TYPES = {
        "DISCOVERY_REQUEST": "discovery_request",
        "DISCOVERY_RESPONSE": "discovery_response", 
        "JOIN_REQUEST": "join_request",
        "JOIN_RESPONSE": "join_response",
        "HEARTBEAT": "heartbeat"
    }
    
    def __init__(self, storage_dir: Optional[str] = None, node_id: Optional[str] = None):
        """
        Initialize network manager
        
        Args:
            storage_dir: Directory for network configuration storage
            node_id: Unique node identifier
        """
        self.storage_dir = Path(storage_dir) if storage_dir else Path.cwd()
        self.node_id = node_id or f"node_{uuid.uuid4().hex[:8]}"
        
        # License integration
        self.license_enforcer = get_license_enforcer()
        
        # Network state
        self.discovered_networks: Dict[str, NetworkInfo] = {}
        self.joined_networks: Dict[str, Dict[str, Any]] = {}
        self.pending_join_requests: Dict[str, JoinRequest] = {}
        self.managed_networks: Dict[str, NetworkInfo] = {}  # Networks we admin
        
        # Discovery state
        self.discovery_socket: Optional[socket.socket] = None
        self.discovery_running = False
        self.discovery_thread: Optional[threading.Thread] = None
        
        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing network configurations
        self._load_joined_networks()
        
        logger.info(f"NetworkManager initialized for node {self.node_id}")
    
    def create_network(self, network_name: str, model_id: str, 
                      network_type: NetworkType = NetworkType.PUBLIC,
                      description: str = "") -> Optional[NetworkInfo]:
        """
        Create a new network with license validation
        
        Args:
            network_name: Name for the new network
            model_id: Model to use for this network
            network_type: Type of network (public/private/enterprise)
            description: Optional network description
            
        Returns:
            NetworkInfo if successful, None otherwise
        """
        try:
            logger.info(f"Creating network: {network_name} with model {model_id}")
            
            # === LICENSE VALIDATION ===
            
            # 1. Check if license is valid
            license_status = self.license_enforcer.get_license_status()
            if not license_status.get('valid', False):
                logger.error(f"Network creation denied: Invalid license ({license_status.get('status')})")
                return None
            
            # 2. Validate model access
            if not self.license_enforcer.check_model_access_allowed(model_id):
                logger.error(f"Network creation denied: Model access denied for {model_id}")
                return None
            
            # 3. Check network creation permissions based on license tier
            current_license = self.license_enforcer.current_license
            if not current_license:
                logger.error("Network creation denied: No license information")
                return None
            
            # Determine required license tier based on network type
            if network_type == NetworkType.ENTERPRISE and current_license.plan != SubscriptionTier.ENT:
                logger.error("Network creation denied: Enterprise networks require ENT license")
                return None
            
            # 4. Check if we can manage another network (ENT = unlimited, PRO = 5, FREE = 1)
            network_limits = {
                SubscriptionTier.FREE: 1,
                SubscriptionTier.PRO: 5,
                SubscriptionTier.ENT: -1  # Unlimited
            }
            
            current_managed = len(self.managed_networks)
            max_networks = network_limits.get(current_license.plan, 0)
            
            if max_networks != -1 and current_managed >= max_networks:
                logger.error(f"Network creation denied: Network limit reached ({current_managed}/{max_networks})")
                return None
            
            # === END LICENSE VALIDATION ===
            
            # Generate network configuration
            network_id = f"net_{uuid.uuid4().hex[:12]}"
            
            # Determine client limits based on license
            max_clients = min(current_license.max_clients, 100) if current_license.max_clients != -1 else 100
            
            # Create network info
            network_info = NetworkInfo(
                network_id=network_id,
                network_name=network_name,
                network_type=network_type,
                admin_node_id=self.node_id,
                admin_host="localhost",  # Will be updated with actual host
                admin_port=8702,  # Default port, should be configurable
                model_id=model_id,
                model_name=model_id,  # Could be enhanced with actual model name
                required_license_tier=current_license.plan,
                max_clients=max_clients,
                current_clients=0,
                status=NetworkStatus.ACTIVE,
                created_at=datetime.now(),
                last_seen=datetime.now(),
                description=description
            )
            
            # Create network configuration file
            network_config = self._create_network_config(network_info, model_id)
            
            # Save network configuration
            config_file = self.storage_dir / f"network_config_{network_id}.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(network_config, f, indent=2, default=str)
            
            # Add to managed networks
            self.managed_networks[network_id] = network_info
            
            logger.info(f"Network created successfully: {network_name} ({network_id})")
            logger.info(f"Network config saved: {config_file}")
            
            return network_info
            
        except Exception as e:
            logger.error(f"Failed to create network: {e}", exc_info=True)
            return None
    
    async def discover_networks(self, timeout: float = 5.0) -> List[NetworkInfo]:
        """
        Discover available networks with license-aware filtering
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            List of compatible networks
        """
        try:
            logger.info("Starting network discovery...")
            
            # Clear previous discoveries
            self.discovered_networks.clear()
            
            # Start discovery process
            await self._send_discovery_request()
            
            # Wait for responses
            await asyncio.sleep(timeout)
            
            # Filter networks based on license compatibility
            compatible_networks = self._filter_compatible_networks()
            
            logger.info(f"Discovered {len(compatible_networks)} compatible networks")
            return compatible_networks
            
        except Exception as e:
            logger.error(f"Network discovery failed: {e}", exc_info=True)
            return [] 
   
    async def join_network(self, network_id: str, message: str = "") -> bool:
        """
        Join a network with admin approval workflow
        
        Args:
            network_id: Network to join
            message: Optional message to admin
            
        Returns:
            True if join was successful, False otherwise
        """
        try:
            logger.info(f"Attempting to join network: {network_id}")
            
            # === LICENSE VALIDATION ===
            
            # 1. Check license validity
            license_status = self.license_enforcer.get_license_status()
            if not license_status.get('valid', False):
                logger.error(f"Network join denied: Invalid license ({license_status.get('status')})")
                return False
            
            # 2. Get network info
            if network_id not in self.discovered_networks:
                logger.error(f"Network join denied: Network {network_id} not found in discovered networks")
                return False
            
            network_info = self.discovered_networks[network_id]
            current_license = self.license_enforcer.current_license
            
            # 3. Check license tier compatibility
            if not self._is_license_compatible_with_network(current_license.plan, network_info):
                logger.error(f"Network join denied: License tier {current_license.plan.value} not compatible with network requiring {network_info.required_license_tier.value}")
                return False
            
            # 4. Check model access
            if not self.license_enforcer.check_model_access_allowed(network_info.model_id):
                logger.error(f"Network join denied: Model access denied for {network_info.model_id}")
                return False
            
            # === END LICENSE VALIDATION ===
            
            # Create join request
            request_id = f"req_{uuid.uuid4().hex[:8]}"
            join_request = JoinRequest(
                request_id=request_id,
                client_id=self.node_id,
                client_host="localhost",  # Should be actual host
                client_port=8702,  # Should be actual port
                network_id=network_id,
                license_tier=current_license.plan,
                requested_at=datetime.now(),
                message=message
            )
            
            # Send join request to admin
            success = await self._send_join_request(network_info, join_request)
            
            if success:
                # Add to pending requests
                self.pending_join_requests[request_id] = join_request
                logger.info(f"Join request sent for network {network_id}, waiting for admin approval")
                
                # Wait for response (in real implementation, this would be handled by a callback)
                response = await self._wait_for_join_response(request_id, timeout=30.0)
                
                if response and response.approved:
                    # Save network configuration
                    if response.network_config:
                        config_file = self.storage_dir / f"network_config_{network_id}.json"
                        with open(config_file, 'w', encoding='utf-8') as f:
                            json.dump(response.network_config, f, indent=2, default=str)
                        
                        # Add to joined networks
                        self.joined_networks[network_id] = response.network_config
                        
                        logger.info(f"Successfully joined network: {network_id}")
                        return True
                    else:
                        logger.error("Join approved but no network config received")
                        return False
                else:
                    reason = response.reason if response else "No response received"
                    logger.error(f"Join request denied: {reason}")
                    return False
            else:
                logger.error("Failed to send join request")
                return False
                
        except Exception as e:
            logger.error(f"Failed to join network: {e}", exc_info=True)
            return False
    
    def list_joined_networks(self) -> List[Dict[str, Any]]:
        """
        List all joined networks with license status
        
        Returns:
            List of network configurations with license compatibility info
        """
        try:
            networks_with_status = []
            license_status = self.license_enforcer.get_license_status()
            
            for network_id, config in self.joined_networks.items():
                network_status = {
                    "network_id": network_id,
                    "network_name": config.get("network_name", "Unknown"),
                    "model_id": config.get("model_id", "Unknown"),
                    "status": "active" if license_status.get('valid') else "license_invalid",
                    "license_compatible": self._is_current_license_compatible_with_config(config),
                    "config_file": str(self.storage_dir / f"network_config_{network_id}.json"),
                    "joined_at": config.get("joined_at", "Unknown")
                }
                networks_with_status.append(network_status)
            
            logger.info(f"Listed {len(networks_with_status)} joined networks")
            return networks_with_status
            
        except Exception as e:
            logger.error(f"Failed to list joined networks: {e}", exc_info=True)
            return []
    
    def approve_join_request(self, request_id: str, approved: bool, 
                           admin_message: str = "") -> bool:
        """
        Approve or deny a join request (for admin nodes)
        
        Args:
            request_id: Request to approve/deny
            approved: Whether to approve the request
            admin_message: Optional message to requester
            
        Returns:
            True if response was sent successfully
        """
        try:
            if request_id not in self.pending_join_requests:
                logger.error(f"Join request not found: {request_id}")
                return False
            
            join_request = self.pending_join_requests[request_id]
            network_id = join_request.network_id
            
            if network_id not in self.managed_networks:
                logger.error(f"Cannot approve request for unmanaged network: {network_id}")
                return False
            
            network_info = self.managed_networks[network_id]
            
            # Create response
            response = JoinResponse(
                request_id=request_id,
                approved=approved,
                network_config=None,
                reason="Approved by admin" if approved else "Denied by admin",
                admin_message=admin_message
            )
            
            if approved:
                # Check if network has capacity
                if network_info.current_clients >= network_info.max_clients:
                    response.approved = False
                    response.reason = "Network at capacity"
                    logger.warning(f"Join request denied: Network {network_id} at capacity")
                else:
                    # Generate network config for client
                    response.network_config = self._create_client_network_config(network_info)
                    
                    # Update client count
                    network_info.current_clients += 1
                    
                    logger.info(f"Join request approved for network {network_id}")
            
            # Send response (in real implementation)
            success = self._send_join_response(join_request, response)
            
            # Clean up request
            del self.pending_join_requests[request_id]
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to process join request: {e}", exc_info=True)
            return False
    
    def get_pending_join_requests(self) -> List[Dict[str, Any]]:
        """
        Get pending join requests for admin review
        
        Returns:
            List of pending join requests
        """
        try:
            requests = []
            for request_id, join_request in self.pending_join_requests.items():
                request_info = {
                    "request_id": request_id,
                    "client_id": join_request.client_id,
                    "network_id": join_request.network_id,
                    "license_tier": join_request.license_tier.value,
                    "requested_at": join_request.requested_at.isoformat(),
                    "message": join_request.message,
                    "client_host": join_request.client_host
                }
                requests.append(request_info)
            
            return requests
            
        except Exception as e:
            logger.error(f"Failed to get pending requests: {e}", exc_info=True)
            return []
    
    def start_discovery_service(self) -> bool:
        """
        Start network discovery service
        
        Returns:
            True if service started successfully
        """
        try:
            if self.discovery_running:
                logger.warning("Discovery service already running")
                return True
            
            # Create UDP socket for discovery
            self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.discovery_socket.bind(('', self.DISCOVERY_PORT))
            
            # Join multicast group
            mreq = struct.pack("4sl", socket.inet_aton(self.DISCOVERY_MULTICAST_GROUP), socket.INADDR_ANY)
            self.discovery_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            # Start discovery thread
            self.discovery_running = True
            self.discovery_thread = threading.Thread(target=self._discovery_service_loop, daemon=True)
            self.discovery_thread.start()
            
            logger.info("Network discovery service started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start discovery service: {e}", exc_info=True)
            return False
    
    def stop_discovery_service(self) -> None:
        """Stop network discovery service"""
        try:
            self.discovery_running = False
            
            if self.discovery_socket:
                self.discovery_socket.close()
                self.discovery_socket = None
            
            if self.discovery_thread:
                self.discovery_thread.join(timeout=5.0)
                self.discovery_thread = None
            
            logger.info("Network discovery service stopped")
            
        except Exception as e:
            logger.error(f"Error stopping discovery service: {e}", exc_info=True)
    
    def get_network_statistics(self) -> Dict[str, Any]:
        """
        Get network management statistics
        
        Returns:
            Dictionary with network statistics
        """
        license_status = self.license_enforcer.get_license_status()
        
        return {
            "node_id": self.node_id,
            "license_status": license_status,
            "discovered_networks": len(self.discovered_networks),
            "joined_networks": len(self.joined_networks),
            "managed_networks": len(self.managed_networks),
            "pending_requests": len(self.pending_join_requests),
            "discovery_running": self.discovery_running,
            "storage_directory": str(self.storage_dir)
        }
    
    # === PRIVATE METHODS ===
    
    def _load_joined_networks(self) -> None:
        """Load existing network configurations from storage"""
        try:
            config_files = list(self.storage_dir.glob("network_config_*.json"))
            
            for config_file in config_files:
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    network_id = config.get("network_id")
                    if network_id:
                        self.joined_networks[network_id] = config
                        logger.debug(f"Loaded network config: {network_id}")
                
                except Exception as e:
                    logger.warning(f"Failed to load config file {config_file}: {e}")
            
            logger.info(f"Loaded {len(self.joined_networks)} network configurations")
            
        except Exception as e:
            logger.error(f"Failed to load network configurations: {e}", exc_info=True)
    
    def _create_network_config(self, network_info: NetworkInfo, model_id: str) -> Dict[str, Any]:
        """Create network configuration dictionary"""
        return {
            "network_id": network_info.network_id,
            "network_name": network_info.network_name,
            "network_type": network_info.network_type.value,
            "model_id": model_id,
            "model_chain_order": self._get_model_chain_order(model_id),
            "admin_node": {
                "node_id": network_info.admin_node_id,
                "host": network_info.admin_host,
                "port": network_info.admin_port
            },
            "license_requirements": {
                "required_tier": network_info.required_license_tier.value,
                "max_clients": network_info.max_clients
            },
            "created_at": network_info.created_at.isoformat(),
            "version": network_info.version,
            "description": network_info.description
        }
    
    def _create_client_network_config(self, network_info: NetworkInfo) -> Dict[str, Any]:
        """Create network configuration for joining clients"""
        config = self._create_network_config(network_info, network_info.model_id)
        config["joined_at"] = datetime.now().isoformat()
        config["client_role"] = "worker"
        return config
    
    def _get_model_chain_order(self, model_id: str) -> List[str]:
        """Get model chain order for a specific model"""
        # This would typically come from model metadata
        # For now, return a default chain
        if "llama" in model_id.lower():
            return [f"block_{i}" for i in range(1, 34)]  # 33 blocks for Llama
        elif "mistral" in model_id.lower():
            return [f"block_{i}" for i in range(1, 33)]  # 32 blocks for Mistral
        else:
            return [f"block_{i}" for i in range(1, 25)]  # Default 24 blocks
    
    def _filter_compatible_networks(self) -> List[NetworkInfo]:
        """Filter discovered networks based on license compatibility"""
        compatible = []
        current_license = self.license_enforcer.current_license
        
        if not current_license:
            return compatible
        
        for network_info in self.discovered_networks.values():
            if self._is_license_compatible_with_network(current_license.plan, network_info):
                # Check model access
                if self.license_enforcer.check_model_access_allowed(network_info.model_id):
                    compatible.append(network_info)
                else:
                    logger.debug(f"Network {network_info.network_id} filtered out: Model access denied")
            else:
                logger.debug(f"Network {network_info.network_id} filtered out: License incompatible")
        
        return compatible
    
    def _is_license_compatible_with_network(self, license_tier: SubscriptionTier, 
                                          network_info: NetworkInfo) -> bool:
        """Check if license tier is compatible with network requirements"""
        # License tier hierarchy: FREE < PRO < ENT
        tier_levels = {
            SubscriptionTier.FREE: 1,
            SubscriptionTier.PRO: 2,
            SubscriptionTier.ENT: 3
        }
        
        user_level = tier_levels.get(license_tier, 0)
        required_level = tier_levels.get(network_info.required_license_tier, 3)
        
        return user_level >= required_level
    
    def _is_current_license_compatible_with_config(self, config: Dict[str, Any]) -> bool:
        """Check if current license is compatible with network config"""
        try:
            license_reqs = config.get("license_requirements", {})
            required_tier_str = license_reqs.get("required_tier", "ENT")
            required_tier = SubscriptionTier(required_tier_str)
            
            current_license = self.license_enforcer.current_license
            if not current_license:
                return False
            
            return self._is_license_compatible_with_network(current_license.plan, 
                                                          type('NetworkInfo', (), {'required_license_tier': required_tier})())
        except Exception:
            return False  
  
    async def _send_discovery_request(self) -> None:
        """Send network discovery request via UDP multicast"""
        try:
            # Create discovery request
            request = {
                "message_type": self.MESSAGE_TYPES["DISCOVERY_REQUEST"],
                "protocol_version": self.PROTOCOL_VERSION,
                "node_id": self.node_id,
                "timestamp": datetime.now().isoformat(),
                "license_tier": self.license_enforcer.current_license.plan.value if self.license_enforcer.current_license else "NONE"
            }
            
            # Send multicast request
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            
            message = json.dumps(request).encode('utf-8')
            sock.sendto(message, (self.DISCOVERY_MULTICAST_GROUP, self.DISCOVERY_PORT))
            sock.close()
            
            logger.debug("Discovery request sent")
            
        except Exception as e:
            logger.error(f"Failed to send discovery request: {e}", exc_info=True)
    
    async def _send_join_request(self, network_info: NetworkInfo, join_request: JoinRequest) -> bool:
        """Send join request to network admin"""
        try:
            # Create join request message
            request_message = {
                "message_type": self.MESSAGE_TYPES["JOIN_REQUEST"],
                "protocol_version": self.PROTOCOL_VERSION,
                "request_data": asdict(join_request),
                "timestamp": datetime.now().isoformat()
            }
            
            # In a real implementation, this would send via TCP to the admin node
            # For now, we'll simulate the request
            logger.info(f"Sending join request to {network_info.admin_host}:{network_info.admin_port}")
            
            # Simulate network communication delay
            await asyncio.sleep(0.1)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send join request: {e}", exc_info=True)
            return False
    
    async def _wait_for_join_response(self, request_id: str, timeout: float = 30.0) -> Optional[JoinResponse]:
        """Wait for join response from admin"""
        try:
            # In a real implementation, this would wait for actual network response
            # For now, we'll simulate an approval for testing
            await asyncio.sleep(1.0)
            
            # Simulate admin approval (in real implementation, this would come from network)
            if request_id in self.pending_join_requests:
                join_request = self.pending_join_requests[request_id]
                network_id = join_request.network_id
                
                if network_id in self.discovered_networks:
                    network_info = self.discovered_networks[network_id]
                    
                    # Simulate approval
                    response = JoinResponse(
                        request_id=request_id,
                        approved=True,
                        network_config=self._create_client_network_config(network_info),
                        reason="Simulated approval",
                        admin_message="Welcome to the network!"
                    )
                    
                    return response
            
            return None
            
        except Exception as e:
            logger.error(f"Error waiting for join response: {e}", exc_info=True)
            return None
    
    def _send_join_response(self, join_request: JoinRequest, response: JoinResponse) -> bool:
        """Send join response to requesting client"""
        try:
            # Create response message
            response_message = {
                "message_type": self.MESSAGE_TYPES["JOIN_RESPONSE"],
                "protocol_version": self.PROTOCOL_VERSION,
                "response_data": asdict(response),
                "timestamp": datetime.now().isoformat()
            }
            
            # In a real implementation, this would send via TCP to the requesting client
            logger.info(f"Sending join response to {join_request.client_host}:{join_request.client_port}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send join response: {e}", exc_info=True)
            return False
    
    def _discovery_service_loop(self) -> None:
        """Main discovery service loop (runs in separate thread)"""
        logger.info("Discovery service loop started")
        
        while self.discovery_running:
            try:
                if not self.discovery_socket:
                    break
                
                # Set socket timeout to allow periodic checks
                self.discovery_socket.settimeout(1.0)
                
                try:
                    data, addr = self.discovery_socket.recvfrom(4096)
                    self._handle_discovery_message(data, addr)
                except socket.timeout:
                    continue  # Normal timeout, continue loop
                
            except Exception as e:
                if self.discovery_running:  # Only log if we're supposed to be running
                    logger.error(f"Discovery service error: {e}", exc_info=True)
                break
        
        logger.info("Discovery service loop ended")
    
    def _handle_discovery_message(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle incoming discovery messages"""
        try:
            message = json.loads(data.decode('utf-8'))
            message_type = message.get("message_type")
            
            if message_type == self.MESSAGE_TYPES["DISCOVERY_REQUEST"]:
                self._handle_discovery_request(message, addr)
            elif message_type == self.MESSAGE_TYPES["DISCOVERY_RESPONSE"]:
                self._handle_discovery_response(message, addr)
            else:
                logger.debug(f"Unknown discovery message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling discovery message: {e}", exc_info=True)
    
    def _handle_discovery_request(self, message: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle discovery request from other nodes"""
        try:
            requesting_node = message.get("node_id")
            if requesting_node == self.node_id:
                return  # Ignore our own requests
            
            logger.debug(f"Discovery request from {requesting_node} at {addr}")
            
            # Send response with our managed networks
            if self.managed_networks:
                response = {
                    "message_type": self.MESSAGE_TYPES["DISCOVERY_RESPONSE"],
                    "protocol_version": self.PROTOCOL_VERSION,
                    "node_id": self.node_id,
                    "networks": [asdict(network) for network in self.managed_networks.values()],
                    "timestamp": datetime.now().isoformat()
                }
                
                # Send response
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                response_data = json.dumps(response, default=str).encode('utf-8')
                sock.sendto(response_data, addr)
                sock.close()
                
                logger.debug(f"Discovery response sent to {addr}")
            
        except Exception as e:
            logger.error(f"Error handling discovery request: {e}", exc_info=True)
    
    def _handle_discovery_response(self, message: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle discovery response from other nodes"""
        try:
            responding_node = message.get("node_id")
            networks = message.get("networks", [])
            
            logger.debug(f"Discovery response from {responding_node} with {len(networks)} networks")
            
            # Process discovered networks
            for network_data in networks:
                try:
                    # Convert dict back to NetworkInfo
                    network_data['network_type'] = NetworkType(network_data['network_type'])
                    network_data['required_license_tier'] = SubscriptionTier(network_data['required_license_tier'])
                    network_data['status'] = NetworkStatus(network_data['status'])
                    network_data['created_at'] = datetime.fromisoformat(network_data['created_at'])
                    network_data['last_seen'] = datetime.now()  # Update last seen
                    
                    network_info = NetworkInfo(**network_data)
                    self.discovered_networks[network_info.network_id] = network_info
                    
                    logger.debug(f"Discovered network: {network_info.network_name} ({network_info.network_id})")
                    
                except Exception as e:
                    logger.warning(f"Error processing network data: {e}")
            
        except Exception as e:
            logger.error(f"Error handling discovery response: {e}", exc_info=True)


# Convenience functions for easy integration

def create_network_manager(storage_dir: Optional[str] = None, node_id: Optional[str] = None) -> NetworkManager:
    """
    Create a network manager instance
    
    Args:
        storage_dir: Optional storage directory
        node_id: Optional node identifier
        
    Returns:
        NetworkManager instance
    """
    return NetworkManager(storage_dir, node_id)


async def discover_available_networks(manager: Optional[NetworkManager] = None, 
                                    timeout: float = 5.0) -> List[NetworkInfo]:
    """
    Convenience function to discover networks
    
    Args:
        manager: Optional NetworkManager instance
        timeout: Discovery timeout
        
    Returns:
        List of discovered networks
    """
    if manager is None:
        manager = NetworkManager()
    
    return await manager.discover_networks(timeout)


def get_joined_networks(manager: Optional[NetworkManager] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to get joined networks
    
    Args:
        manager: Optional NetworkManager instance
        
    Returns:
        List of joined networks
    """
    if manager is None:
        manager = NetworkManager()
    
    return manager.list_joined_networks()


if __name__ == "__main__":
    # Example usage and testing
    import tempfile
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    
    async def test_network_manager():
        """Test network manager functionality"""
        print("=== Testing Network Manager ===")
        
        # Create network manager with temporary storage
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = NetworkManager(temp_dir, "test_node_1")
            
            # Install test license first
            success = manager.license_enforcer.install_license("TIKT-PRO-6M-XYZ789")
            print(f"License installed: {success}")
            
            if success:
                # Test network creation
                print(f"\n--- Creating Network ---")
                network_info = manager.create_network(
                    network_name="Test Network",
                    model_id="llama3_1_8b_fp16",
                    network_type=NetworkType.PUBLIC,
                    description="Test network for demonstration"
                )
                
                if network_info:
                    print(f"Network created: {network_info.network_name}")
                    print(f"Network ID: {network_info.network_id}")
                    print(f"Max clients: {network_info.max_clients}")
                    print(f"Required tier: {network_info.required_license_tier.value}")
                
                # Test network discovery
                print(f"\n--- Network Discovery ---")
                manager.start_discovery_service()
                
                # Wait a moment for service to start
                await asyncio.sleep(0.5)
                
                discovered = await manager.discover_networks(timeout=2.0)
                print(f"Discovered {len(discovered)} networks")
                
                for network in discovered:
                    print(f"  - {network.network_name} ({network.network_id})")
                
                # Test joined networks list
                print(f"\n--- Joined Networks ---")
                joined = manager.list_joined_networks()
                print(f"Joined networks: {len(joined)}")
                
                # Test statistics
                print(f"\n--- Statistics ---")
                stats = manager.get_network_statistics()
                for key, value in stats.items():
                    if key != "license_status":  # Skip detailed license status
                        print(f"  {key}: {value}")
                
                # Stop discovery service
                manager.stop_discovery_service()
            
            print(f"\n=== Test Complete ===")
    
    # Run test
    asyncio.run(test_network_manager())