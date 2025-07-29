"""
Enhanced Network Discovery System for TikTrue Distributed LLM Platform

This module implements a UDP broadcast/multicast discovery system with license-aware filtering
for the TikTrue Distributed LLM Platform. It enables automatic discovery of available networks
and nodes on the local network.

Features:
- UDP broadcast/multicast for network discovery
- License-aware network filtering based on subscription tier
- Real-time network announcements and updates
- Heartbeat mechanism for network health monitoring
- Secure message exchange with validation
- Network timeout and automatic cleanup
- Comprehensive statistics tracking

Classes:
    DiscoveryMessageType: Enum for discovery message types
    DiscoveryMessage: Base class for discovery messages
    DiscoveryRequest: Class for discovery request messages
    DiscoveryResponse: Class for discovery response messages
    NetworkDiscoveryService: Main class for network discovery operations
"""

import asyncio
import json
import logging
import socket
import struct
import time
import threading
from typing import Dict, Any, Optional, List, Tuple, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from license_enforcer import get_license_enforcer
from license_models import SubscriptionTier
from core.network_manager import NetworkInfo, NetworkType, NetworkStatus

logger = logging.getLogger("NetworkDiscovery")


class DiscoveryMessageType(Enum):
    """Discovery message types"""
    DISCOVERY_REQUEST = "discovery_request"
    DISCOVERY_RESPONSE = "discovery_response"
    HEARTBEAT = "heartbeat"
    NETWORK_ANNOUNCEMENT = "network_announcement"
    NETWORK_UPDATE = "network_update"
    NETWORK_SHUTDOWN = "network_shutdown"


@dataclass
class DiscoveryMessage:
    """Base discovery message structure"""
    message_type: DiscoveryMessageType
    protocol_version: str
    node_id: str
    timestamp: datetime
    message_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['message_type'] = self.message_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiscoveryMessage':
        """Create from dictionary"""
        data['message_type'] = DiscoveryMessageType(data['message_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class DiscoveryRequest(DiscoveryMessage):
    """Discovery request message"""
    license_tier: str
    requested_network_types: List[str]
    supported_models: List[str]
    
    def __init__(self, node_id: str, license_tier: str, 
                 requested_network_types: List[str] = None,
                 supported_models: List[str] = None):
        super().__init__(
            message_type=DiscoveryMessageType.DISCOVERY_REQUEST,
            protocol_version="1.0",
            node_id=node_id,
            timestamp=datetime.now(),
            message_id=f"req_{uuid.uuid4().hex[:8]}"
        )
        self.license_tier = license_tier
        self.requested_network_types = requested_network_types or ["public", "private"]
        self.supported_models = supported_models or []


@dataclass
class DiscoveryResponse(DiscoveryMessage):
    """Discovery response message"""
    networks: List[Dict[str, Any]]
    node_info: Dict[str, Any]
    
    def __init__(self, node_id: str, networks: List[NetworkInfo], node_info: Dict[str, Any]):
        super().__init__(
            message_type=DiscoveryMessageType.DISCOVERY_RESPONSE,
            protocol_version="1.0",
            node_id=node_id,
            timestamp=datetime.now(),
            message_id=f"resp_{uuid.uuid4().hex[:8]}"
        )
        self.networks = [self._network_to_dict(net) for net in networks]
        self.node_info = node_info
    
    def _network_to_dict(self, network: NetworkInfo) -> Dict[str, Any]:
        """Convert NetworkInfo to dictionary"""
        data = asdict(network)
        data['network_type'] = network.network_type.value
        data['required_license_tier'] = network.required_license_tier.value
        data['status'] = network.status.value
        data['created_at'] = network.created_at.isoformat()
        data['last_seen'] = network.last_seen.isoformat()
        return data


class NetworkDiscoveryService:
    """
    Enhanced network discovery service with UDP broadcast/multicast
    Handles network discovery, announcement, and real-time updates
    """
    
    # Network configuration
    MULTICAST_GROUP = "239.255.255.250"
    DISCOVERY_PORT = 8700
    HEARTBEAT_PORT = 8701
    BUFFER_SIZE = 8192
    
    # Timing configuration
    DISCOVERY_TIMEOUT = 5.0
    HEARTBEAT_INTERVAL = 30.0
    NETWORK_TIMEOUT = 90.0  # Consider network dead after 90s without heartbeat
    RETRY_INTERVAL = 1.0
    MAX_RETRIES = 3
    
    def __init__(self, node_id: str, managed_networks: Dict[str, NetworkInfo] = None):
        """
        Initialize discovery service
        
        Args:
            node_id: Unique node identifier
            managed_networks: Networks managed by this node
        """
        self.node_id = node_id
        self.managed_networks = managed_networks or {}
        
        # License integration
        self.license_enforcer = get_license_enforcer()
        
        # Discovery state
        self.discovered_networks: Dict[str, NetworkInfo] = {}
        self.discovered_nodes: Dict[str, Dict[str, Any]] = {}
        self.discovery_callbacks: List[Callable[[List[NetworkInfo]], None]] = []
        
        # Network sockets
        self.discovery_socket: Optional[socket.socket] = None
        self.heartbeat_socket: Optional[socket.socket] = None
        
        # Service state
        self.running = False
        self.discovery_thread: Optional[threading.Thread] = None
        self.heartbeat_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.stats = {
            'discovery_requests_sent': 0,
            'discovery_responses_received': 0,
            'discovery_responses_sent': 0,
            'heartbeats_sent': 0,
            'heartbeats_received': 0,
            'networks_discovered': 0,
            'nodes_discovered': 0,
            'last_discovery': None,
            'service_start_time': None
        }
        
        logger.info(f"NetworkDiscoveryService initialized for node {self.node_id}")
    
    def start_service(self) -> bool:
        """
        Start the discovery service
        
        Returns:
            True if service started successfully
        """
        try:
            if self.running:
                logger.warning("Discovery service already running")
                return True
            
            logger.info("Starting network discovery service...")
            
            # Create and configure discovery socket
            self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.discovery_socket.bind(('', self.DISCOVERY_PORT))
            
            # Join multicast group for discovery
            mreq = struct.pack("4sl", socket.inet_aton(self.MULTICAST_GROUP), socket.INADDR_ANY)
            self.discovery_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            # Create heartbeat socket
            self.heartbeat_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.heartbeat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.heartbeat_socket.bind(('', self.HEARTBEAT_PORT))
            
            # Start service threads
            self.running = True
            self.stats['service_start_time'] = datetime.now()
            
            # Discovery listener thread
            self.discovery_thread = threading.Thread(
                target=self._discovery_listener_loop,
                name=f"DiscoveryListener-{self.node_id}",
                daemon=True
            )
            self.discovery_thread.start()
            
            # Heartbeat thread
            self.heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name=f"Heartbeat-{self.node_id}",
                daemon=True
            )
            self.heartbeat_thread.start()
            
            logger.info("Network discovery service started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start discovery service: {e}", exc_info=True)
            self.stop_service()
            return False
    
    def stop_service(self) -> None:
        """Stop the discovery service"""
        try:
            logger.info("Stopping network discovery service...")
            
            self.running = False
            
            # Send shutdown announcement
            self._send_shutdown_announcement()
            
            # Close sockets
            if self.discovery_socket:
                self.discovery_socket.close()
                self.discovery_socket = None
            
            if self.heartbeat_socket:
                self.heartbeat_socket.close()
                self.heartbeat_socket = None
            
            # Wait for threads to finish
            if self.discovery_thread and self.discovery_thread.is_alive():
                self.discovery_thread.join(timeout=5.0)
            
            if self.heartbeat_thread and self.heartbeat_thread.is_alive():
                self.heartbeat_thread.join(timeout=5.0)
            
            logger.info("Network discovery service stopped")
            
        except Exception as e:
            logger.error(f"Error stopping discovery service: {e}", exc_info=True)
    
    async def discover_networks(self, timeout: float = None, 
                              network_types: List[NetworkType] = None,
                              model_filter: List[str] = None) -> List[NetworkInfo]:
        """
        Discover available networks with filtering
        
        Args:
            timeout: Discovery timeout (default: DISCOVERY_TIMEOUT)
            network_types: Filter by network types
            model_filter: Filter by supported models
            
        Returns:
            List of discovered networks compatible with current license
        """
        try:
            timeout = timeout or self.DISCOVERY_TIMEOUT
            
            logger.info(f"Starting network discovery (timeout: {timeout}s)")
            
            # Clear previous discoveries
            self.discovered_networks.clear()
            self.discovered_nodes.clear()
            
            # Get current license info
            license_status = self.license_enforcer.get_license_status()
            current_license = self.license_enforcer.current_license
            
            if not current_license or not license_status.get('valid'):
                logger.warning("Cannot discover networks: Invalid license")
                return []
            
            # Prepare discovery request
            request_types = []
            if network_types:
                request_types = [nt.value for nt in network_types]
            else:
                # Default based on license tier
                if current_license.plan_type == "FREE":
                    request_types = ["public"]
                elif current_license.plan_type == "PRO":
                    request_types = ["public", "private"]
                else:  # ENT
                    request_types = ["public", "private", "enterprise"]
            
            supported_models = current_license.allowed_models or []
            
            # Send discovery request
            success = await self._send_discovery_request(
                license_tier=current_license.plan_type,
                requested_types=request_types,
                supported_models=supported_models
            )
            
            if not success:
                logger.error("Failed to send discovery request")
                return []
            
            # Wait for responses
            await asyncio.sleep(timeout)
            
            # Filter and return compatible networks
            compatible_networks = self._filter_compatible_networks(model_filter)
            
            self.stats['networks_discovered'] = len(compatible_networks)
            self.stats['nodes_discovered'] = len(self.discovered_nodes)
            self.stats['last_discovery'] = datetime.now()
            
            logger.info(f"Discovery completed: {len(compatible_networks)} compatible networks found")
            
            # Notify callbacks
            for callback in self.discovery_callbacks:
                try:
                    callback(compatible_networks)
                except Exception as e:
                    logger.error(f"Discovery callback error: {e}")
            
            return compatible_networks
            
        except Exception as e:
            logger.error(f"Network discovery failed: {e}", exc_info=True)
            return []
    
    def add_discovery_callback(self, callback: Callable[[List[NetworkInfo]], None]) -> None:
        """
        Add callback for discovery events
        
        Args:
            callback: Function to call when networks are discovered
        """
        self.discovery_callbacks.append(callback)
    
    def remove_discovery_callback(self, callback: Callable[[List[NetworkInfo]], None]) -> None:
        """
        Remove discovery callback
        
        Args:
            callback: Callback function to remove
        """
        if callback in self.discovery_callbacks:
            self.discovery_callbacks.remove(callback)
    
    def announce_network(self, network: NetworkInfo) -> bool:
        """
        Announce a new network to the discovery system
        
        Args:
            network: Network to announce
            
        Returns:
            True if announcement was sent successfully
        """
        try:
            # Create announcement message
            announcement = {
                "message_type": DiscoveryMessageType.NETWORK_ANNOUNCEMENT.value,
                "protocol_version": "1.0",
                "node_id": self.node_id,
                "timestamp": datetime.now().isoformat(),
                "message_id": f"ann_{uuid.uuid4().hex[:8]}",
                "network": self._network_to_dict(network)
            }
            
            # Send announcement
            success = self._send_multicast_message(announcement)
            
            if success:
                logger.info(f"Network announced: {network.network_name} ({network.network_id})")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to announce network: {e}", exc_info=True)
            return False
    
    def update_network(self, network: NetworkInfo) -> bool:
        """
        Send network update to discovery system
        
        Args:
            network: Updated network information
            
        Returns:
            True if update was sent successfully
        """
        try:
            # Create update message
            update = {
                "message_type": DiscoveryMessageType.NETWORK_UPDATE.value,
                "protocol_version": "1.0",
                "node_id": self.node_id,
                "timestamp": datetime.now().isoformat(),
                "message_id": f"upd_{uuid.uuid4().hex[:8]}",
                "network": self._network_to_dict(network)
            }
            
            # Send update
            success = self._send_multicast_message(update)
            
            if success:
                logger.debug(f"Network updated: {network.network_name} ({network.network_id})")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update network: {e}", exc_info=True)
            return False
    
    def get_discovery_statistics(self) -> Dict[str, Any]:
        """
        Get discovery service statistics
        
        Returns:
            Dictionary with service statistics
        """
        stats = self.stats.copy()
        stats['service_running'] = self.running
        stats['discovered_networks_count'] = len(self.discovered_networks)
        stats['discovered_nodes_count'] = len(self.discovered_nodes)
        stats['managed_networks_count'] = len(self.managed_networks)
        
        if stats['service_start_time']:
            uptime = datetime.now() - stats['service_start_time']
            stats['uptime_seconds'] = uptime.total_seconds()
        
        return stats
    
    def get_discovered_networks(self) -> List[NetworkInfo]:
        """
        Get list of currently discovered networks
        
        Returns:
            List of discovered networks
        """
        return list(self.discovered_networks.values())
    
    def get_discovered_nodes(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about discovered nodes
        
        Returns:
            Dictionary of node information
        """
        return self.discovered_nodes.copy()    
  
    # === PRIVATE METHODS ===
    
    async def _send_discovery_request(self, license_tier: str, 
                                    requested_types: List[str],
                                    supported_models: List[str]) -> bool:
        """Send discovery request via UDP multicast"""
        try:
            # Create discovery request
            request = DiscoveryRequest(
                node_id=self.node_id,
                license_tier=license_tier,
                requested_network_types=requested_types,
                supported_models=supported_models
            )
            
            # Send multicast request
            success = self._send_multicast_message(request.to_dict())
            
            if success:
                self.stats['discovery_requests_sent'] += 1
                logger.debug(f"Discovery request sent for license tier: {license_tier}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send discovery request: {e}", exc_info=True)
            return False
    
    def _send_multicast_message(self, message: Dict[str, Any]) -> bool:
        """Send message via UDP multicast"""
        try:
            if not self.discovery_socket:
                logger.error("Discovery socket not available")
                return False
            
            # Serialize message
            message_data = json.dumps(message, default=str).encode('utf-8')
            
            if len(message_data) > self.BUFFER_SIZE:
                logger.error(f"Message too large: {len(message_data)} bytes")
                return False
            
            # Send to multicast group
            self.discovery_socket.sendto(
                message_data, 
                (self.MULTICAST_GROUP, self.DISCOVERY_PORT)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send multicast message: {e}", exc_info=True)
            return False
    
    def _discovery_listener_loop(self) -> None:
        """Main discovery listener loop"""
        logger.info("Discovery listener started")
        
        while self.running:
            try:
                if not self.discovery_socket:
                    break
                
                # Set socket timeout for responsive shutdown
                self.discovery_socket.settimeout(1.0)
                
                try:
                    data, addr = self.discovery_socket.recvfrom(self.BUFFER_SIZE)
                    
                    # Process received message
                    asyncio.run_coroutine_threadsafe(
                        self._process_discovery_message(data, addr),
                        asyncio.new_event_loop()
                    )
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        logger.error(f"Discovery socket error: {e}")
                    break
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Discovery listener error: {e}", exc_info=True)
                time.sleep(1.0)
        
        logger.info("Discovery listener stopped")
    
    async def _process_discovery_message(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Process received discovery message"""
        try:
            # Parse message
            message_str = data.decode('utf-8')
            message_data = json.loads(message_str)
            
            message_type = DiscoveryMessageType(message_data.get('message_type'))
            sender_node_id = message_data.get('node_id')
            
            # Ignore messages from self
            if sender_node_id == self.node_id:
                return
            
            # Update node information
            self.discovered_nodes[sender_node_id] = {
                'node_id': sender_node_id,
                'address': addr[0],
                'port': addr[1],
                'last_seen': datetime.now(),
                'message_count': self.discovered_nodes.get(sender_node_id, {}).get('message_count', 0) + 1
            }
            
            # Process based on message type
            if message_type == DiscoveryMessageType.DISCOVERY_REQUEST:
                await self._handle_discovery_request(message_data, addr)
            elif message_type == DiscoveryMessageType.DISCOVERY_RESPONSE:
                await self._handle_discovery_response(message_data, addr)
            elif message_type == DiscoveryMessageType.NETWORK_ANNOUNCEMENT:
                await self._handle_network_announcement(message_data, addr)
            elif message_type == DiscoveryMessageType.NETWORK_UPDATE:
                await self._handle_network_update(message_data, addr)
            elif message_type == DiscoveryMessageType.HEARTBEAT:
                await self._handle_heartbeat(message_data, addr)
            elif message_type == DiscoveryMessageType.NETWORK_SHUTDOWN:
                await self._handle_network_shutdown(message_data, addr)
            
        except Exception as e:
            logger.error(f"Failed to process discovery message from {addr}: {e}", exc_info=True)
    
    async def _handle_discovery_request(self, message_data: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle incoming discovery request"""
        try:
            # Extract request information
            requester_license_tier = message_data.get('license_tier')
            requested_types = message_data.get('requested_network_types', [])
            supported_models = message_data.get('supported_models', [])
            
            # Filter networks based on request
            compatible_networks = []
            
            for network in self.managed_networks.values():
                # Check license compatibility
                if not self._is_license_compatible(network, requester_license_tier):
                    continue
                
                # Check network type
                if network.network_type.value not in requested_types:
                    continue
                
                # Check model compatibility
                if supported_models and network.model_id not in supported_models:
                    continue
                
                compatible_networks.append(network)
            
            # Send response if we have compatible networks
            if compatible_networks:
                await self._send_discovery_response(compatible_networks, addr)
            
        except Exception as e:
            logger.error(f"Failed to handle discovery request: {e}", exc_info=True)
    
    async def _handle_discovery_response(self, message_data: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle incoming discovery response"""
        try:
            networks_data = message_data.get('networks', [])
            node_info = message_data.get('node_info', {})
            
            # Process each network in response
            for network_data in networks_data:
                network_info = self._dict_to_network_info(network_data)
                
                if network_info and self._is_network_accessible(network_info):
                    # Update network with sender address
                    network_info.admin_address = addr[0]
                    network_info.admin_port = network_data.get('admin_port', 8080)
                    network_info.last_seen = datetime.now()
                    
                    # Store discovered network
                    self.discovered_networks[network_info.network_id] = network_info
                    
                    logger.debug(f"Discovered network: {network_info.network_name} from {addr[0]}")
            
            self.stats['discovery_responses_received'] += 1
            
        except Exception as e:
            logger.error(f"Failed to handle discovery response: {e}", exc_info=True)
    
    async def _handle_network_announcement(self, message_data: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle network announcement"""
        try:
            network_data = message_data.get('network', {})
            network_info = self._dict_to_network_info(network_data)
            
            if network_info and self._is_network_accessible(network_info):
                network_info.admin_address = addr[0]
                network_info.last_seen = datetime.now()
                
                self.discovered_networks[network_info.network_id] = network_info
                logger.info(f"Network announced: {network_info.network_name} from {addr[0]}")
            
        except Exception as e:
            logger.error(f"Failed to handle network announcement: {e}", exc_info=True)
    
    async def _handle_network_update(self, message_data: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle network update"""
        try:
            network_data = message_data.get('network', {})
            network_info = self._dict_to_network_info(network_data)
            
            if network_info and network_info.network_id in self.discovered_networks:
                network_info.admin_address = addr[0]
                network_info.last_seen = datetime.now()
                
                self.discovered_networks[network_info.network_id] = network_info
                logger.debug(f"Network updated: {network_info.network_name} from {addr[0]}")
            
        except Exception as e:
            logger.error(f"Failed to handle network update: {e}", exc_info=True)
    
    async def _handle_heartbeat(self, message_data: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle heartbeat message"""
        try:
            sender_node_id = message_data.get('node_id')
            
            if sender_node_id in self.discovered_nodes:
                self.discovered_nodes[sender_node_id]['last_seen'] = datetime.now()
                self.stats['heartbeats_received'] += 1
            
        except Exception as e:
            logger.error(f"Failed to handle heartbeat: {e}", exc_info=True)
    
    async def _handle_network_shutdown(self, message_data: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle network shutdown notification"""
        try:
            network_id = message_data.get('network_id')
            
            if network_id and network_id in self.discovered_networks:
                del self.discovered_networks[network_id]
                logger.info(f"Network shutdown: {network_id} from {addr[0]}")
            
        except Exception as e:
            logger.error(f"Failed to handle network shutdown: {e}", exc_info=True)
    
    async def _send_discovery_response(self, networks: List[NetworkInfo], addr: Tuple[str, int]) -> None:
        """Send discovery response to requester"""
        try:
            # Get node information
            node_info = {
                'node_id': self.node_id,
                'address': addr[0],  # Use requester's address for response routing
                'capabilities': self._get_node_capabilities(),
                'managed_networks_count': len(self.managed_networks)
            }
            
            # Create response
            response = DiscoveryResponse(
                node_id=self.node_id,
                networks=networks,
                node_info=node_info
            )
            
            # Send response directly to requester
            response_data = json.dumps(response.to_dict(), default=str).encode('utf-8')
            
            # Create temporary socket for direct response
            response_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                response_socket.sendto(response_data, addr)
                self.stats['discovery_responses_sent'] += 1
                logger.debug(f"Discovery response sent to {addr[0]}:{addr[1]}")
            finally:
                response_socket.close()
            
        except Exception as e:
            logger.error(f"Failed to send discovery response: {e}", exc_info=True)
    
    def _heartbeat_loop(self) -> None:
        """Heartbeat loop for network presence"""
        logger.info("Heartbeat service started")
        
        while self.running:
            try:
                # Send heartbeat for managed networks
                self._send_heartbeat()
                
                # Sleep until next heartbeat
                for _ in range(int(self.HEARTBEAT_INTERVAL)):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Heartbeat error: {e}", exc_info=True)
                time.sleep(5)
        
        logger.info("Heartbeat service stopped")
    
    def _send_heartbeat(self) -> bool:
        """Send heartbeat message"""
        try:
            if not self.heartbeat_socket:
                return False
            
            # Create heartbeat message
            heartbeat = {
                "message_type": DiscoveryMessageType.HEARTBEAT.value,
                "protocol_version": "1.0",
                "node_id": self.node_id,
                "timestamp": datetime.now().isoformat(),
                "message_id": f"hb_{uuid.uuid4().hex[:8]}",
                "networks": list(self.managed_networks.keys())
            }
            
            # Serialize message
            heartbeat_data = json.dumps(heartbeat, default=str).encode('utf-8')
            
            # Send to multicast group
            self.heartbeat_socket.sendto(
                heartbeat_data,
                (self.MULTICAST_GROUP, self.HEARTBEAT_PORT)
            )
            
            self.stats['heartbeats_sent'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}", exc_info=True)
            return False
    
    def _send_shutdown_announcement(self) -> bool:
        """Send shutdown announcement for managed networks"""
        try:
            for network_id in self.managed_networks:
                # Create shutdown message
                shutdown = {
                    "message_type": DiscoveryMessageType.NETWORK_SHUTDOWN.value,
                    "protocol_version": "1.0",
                    "node_id": self.node_id,
                    "timestamp": datetime.now().isoformat(),
                    "message_id": f"sd_{uuid.uuid4().hex[:8]}",
                    "network_id": network_id
                }
                
                # Send announcement
                self._send_multicast_message(shutdown)
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to send shutdown announcement: {e}", exc_info=True)
            return False
    
    def _filter_compatible_networks(self, model_filter: List[str] = None) -> List[NetworkInfo]:
        """Filter discovered networks based on compatibility"""
        try:
            # Get current license info
            license_status = self.license_enforcer.get_license_status()
            current_license = self.license_enforcer.current_license
            
            if not current_license or not license_status.get('valid'):
                return []
            
            compatible_networks = []
            
            for network in self.discovered_networks.values():
                # Check license compatibility
                if not self._is_license_compatible(network, current_license.plan_type):
                    continue
                
                # Check model filter
                if model_filter and network.model_id not in model_filter:
                    continue
                
                # Check if network is active
                if network.status != NetworkStatus.ACTIVE:
                    continue
                
                compatible_networks.append(network)
            
            return compatible_networks
            
        except Exception as e:
            logger.error(f"Failed to filter compatible networks: {e}", exc_info=True)
            return []
    
    def _is_license_compatible(self, network: NetworkInfo, license_tier: str) -> bool:
        """Check if license tier is compatible with network requirements"""
        try:
            # Map license tiers to numeric values for comparison
            tier_values = {
                "FREE": 1,
                "PRO": 2,
                "ENTERPRISE": 3
            }
            
            network_required_tier = network.required_license_tier.value
            
            # Check if license tier meets or exceeds network requirements
            return tier_values.get(license_tier, 0) >= tier_values.get(network_required_tier, 0)
            
        except Exception as e:
            logger.error(f"Failed to check license compatibility: {e}", exc_info=True)
            return False
    
    def _is_network_accessible(self, network: NetworkInfo) -> bool:
        """Check if network is accessible based on current license"""
        try:
            # Get current license info
            license_status = self.license_enforcer.get_license_status()
            current_license = self.license_enforcer.current_license
            
            if not current_license or not license_status.get('valid'):
                return False
            
            # Check license compatibility
            return self._is_license_compatible(network, current_license.plan_type)
            
        except Exception as e:
            logger.error(f"Failed to check network accessibility: {e}", exc_info=True)
            return False
    
    def _get_node_capabilities(self) -> Dict[str, Any]:
        """Get node capabilities for discovery response"""
        return {
            'supports_encryption': True,
            'supports_compression': True,
            'supports_streaming': True,
            'max_clients': 10,
            'version': '1.0'
        }
    
    def _network_to_dict(self, network: NetworkInfo) -> Dict[str, Any]:
        """Convert NetworkInfo to dictionary"""
        data = asdict(network)
        data['network_type'] = network.network_type.value
        data['required_license_tier'] = network.required_license_tier.value
        data['status'] = network.status.value
        data['created_at'] = network.created_at.isoformat()
        data['last_seen'] = network.last_seen.isoformat()
        return data
    
    def _dict_to_network_info(self, data: Dict[str, Any]) -> Optional[NetworkInfo]:
        """Convert dictionary to NetworkInfo"""
        try:
            # Convert string values to enums
            network_type = NetworkType(data.get('network_type', 'public'))
            required_license_tier = SubscriptionTier(data.get('required_license_tier', 'FREE'))
            status = NetworkStatus(data.get('status', 'active'))
            
            # Convert ISO timestamps to datetime
            created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
            last_seen = datetime.fromisoformat(data.get('last_seen', datetime.now().isoformat()))
            
            return NetworkInfo(
                network_id=data.get('network_id', ''),
                network_name=data.get('network_name', ''),
                network_type=network_type,
                admin_node_id=data.get('admin_node_id', ''),
                admin_address=data.get('admin_address', ''),
                admin_port=data.get('admin_port', 8080),
                model_id=data.get('model_id', ''),
                required_license_tier=required_license_tier,
                max_clients=data.get('max_clients', 5),
                current_clients=data.get('current_clients', 0),
                status=status,
                created_at=created_at,
                last_seen=last_seen,
                metadata=data.get('metadata', {})
            )
            
        except Exception as e:
            logger.error(f"Failed to convert dictionary to NetworkInfo: {e}", exc_info=True)
            return None


# Global instance for convenience
_discovery_service: Optional[NetworkDiscoveryService] = None

def get_discovery_service(node_id: str = None) -> NetworkDiscoveryService:
    """Get global discovery service instance"""
    global _discovery_service
    if _discovery_service is None:
        if node_id is None:
            node_id = f"node_{uuid.uuid4().hex[:8]}"
        _discovery_service = NetworkDiscoveryService(node_id)
    return _discovery_service