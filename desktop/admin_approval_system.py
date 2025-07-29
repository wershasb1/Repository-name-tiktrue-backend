"""
Admin Approval System for Network Joining
Implements approval request/response protocol with security validation
"""

import asyncio
import json
import logging
import time
import uuid
import hashlib
import hmac
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Set
from threading import Lock

from license_enforcer import get_license_enforcer
from security.license_validator import SubscriptionTier
from core.network_manager import NetworkInfo

logger = logging.getLogger("AdminApproval")


class ApprovalStatus(Enum):
    """Approval request status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalPriority(Enum):
    """Priority levels for approval requests"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ApprovalRequest:
    """Network joining approval request"""
    request_id: str
    requester_node_id: str
    requester_address: str
    network_id: str
    network_name: str
    license_tier: str
    license_hash: str
    requested_at: datetime
    expires_at: datetime
    status: ApprovalStatus
    priority: ApprovalPriority
    requester_info: Dict[str, Any]
    security_token: str
    admin_notes: str = ""
    processed_by: str = ""
    processed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        data['requested_at'] = self.requested_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat()
        if self.processed_at:
            data['processed_at'] = self.processed_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ApprovalRequest':
        """Create from dictionary"""
        data['status'] = ApprovalStatus(data['status'])
        data['priority'] = ApprovalPriority(data['priority'])
        data['requested_at'] = datetime.fromisoformat(data['requested_at'])
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        if data.get('processed_at'):
            data['processed_at'] = datetime.fromisoformat(data['processed_at'])
        return cls(**data)


@dataclass
class ApprovalResponse:
    """Response to approval request"""
    request_id: str
    status: ApprovalStatus
    admin_id: str
    admin_notes: str
    processed_at: datetime
    network_config: Optional[Dict[str, Any]] = None
    security_token: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['processed_at'] = self.processed_at.isoformat()
        return data


class AdminApprovalSystem:
    """
    Manages admin approval workflow for network joining
    Handles approval requests, notifications, and security validation
    """
    
    # Configuration
    DEFAULT_EXPIRY_HOURS = 24
    MAX_PENDING_REQUESTS = 100
    SECURITY_TOKEN_LENGTH = 32
    CLEANUP_INTERVAL = 3600  # 1 hour
    
    def __init__(self, admin_node_id: str, managed_networks: Dict[str, NetworkInfo] = None):
        """
        Initialize approval system
        
        Args:
            admin_node_id: ID of the admin node
            managed_networks: Networks managed by this admin
        """
        self.admin_node_id = admin_node_id
        self.managed_networks = managed_networks or {}
        
        # License integration
        self.license_enforcer = get_license_enforcer()
        
        # Approval state
        self.pending_requests: Dict[str, ApprovalRequest] = {}
        self.processed_requests: Dict[str, ApprovalRequest] = {}
        self.approval_callbacks: List[Callable[[ApprovalRequest], None]] = []
        
        # Security
        self.security_key = self._generate_security_key()
        
        # Thread safety
        self._lock = Lock()
        
        # Statistics
        self.stats = {
            'requests_received': 0,
            'requests_approved': 0,
            'requests_rejected': 0,
            'requests_expired': 0,
            'requests_cancelled': 0,
            'average_processing_time': 0.0,
            'last_cleanup': None
        }
        
        logger.info(f"AdminApprovalSystem initialized for admin {admin_node_id}")   
 
    def create_approval_request(self, requester_node_id: str, requester_address: str,
                              network_id: str, requester_info: Dict[str, Any],
                              priority: ApprovalPriority = ApprovalPriority.NORMAL,
                              expiry_hours: int = None) -> ApprovalRequest:
        """
        Create a new approval request
        
        Args:
            requester_node_id: ID of the requesting node
            requester_address: IP address of requester
            network_id: Target network ID
            requester_info: Information about the requester
            priority: Request priority level
            expiry_hours: Hours until request expires
            
        Returns:
            Created approval request
        """
        try:
            with self._lock:
                # Check if network exists
                if network_id not in self.managed_networks:
                    raise ValueError(f"Network {network_id} not managed by this admin")
                
                network = self.managed_networks[network_id]
                
                # Check pending request limits
                if len(self.pending_requests) >= self.MAX_PENDING_REQUESTS:
                    raise ValueError("Too many pending approval requests")
                
                # Generate request ID and security token
                request_id = f"req_{uuid.uuid4().hex[:12]}"
                security_token = self._generate_security_token(requester_node_id, network_id)
                
                # Calculate expiry time
                expiry_hours = expiry_hours or self.DEFAULT_EXPIRY_HOURS
                expires_at = datetime.now() + timedelta(hours=expiry_hours)
                
                # Extract license information
                license_tier = requester_info.get('license_tier', 'UNKNOWN')
                license_hash = self._generate_license_hash(requester_info.get('license_key', ''))
                
                # Create approval request
                request = ApprovalRequest(
                    request_id=request_id,
                    requester_node_id=requester_node_id,
                    requester_address=requester_address,
                    network_id=network_id,
                    network_name=network.network_name,
                    license_tier=license_tier,
                    license_hash=license_hash,
                    requested_at=datetime.now(),
                    expires_at=expires_at,
                    status=ApprovalStatus.PENDING,
                    priority=priority,
                    requester_info=requester_info,
                    security_token=security_token
                )
                
                # Store request
                self.pending_requests[request_id] = request
                self.stats['requests_received'] += 1
                
                logger.info(f"Approval request created: {request_id} for network {network_id}")
                
                # Notify callbacks
                self._notify_approval_callbacks(request)
                
                return request
                
        except Exception as e:
            logger.error(f"Failed to create approval request: {e}", exc_info=True)
            raise    

    def process_approval_request(self, request_id: str, admin_id: str,
                               approve: bool, admin_notes: str = "") -> ApprovalResponse:
        """
        Process an approval request
        
        Args:
            request_id: ID of the request to process
            admin_id: ID of the admin processing the request
            approve: Whether to approve or reject
            admin_notes: Admin notes/comments
            
        Returns:
            Approval response
        """
        try:
            with self._lock:
                # Get pending request
                if request_id not in self.pending_requests:
                    raise ValueError(f"Approval request {request_id} not found")
                
                request = self.pending_requests[request_id]
                
                # Check if request is still valid
                if request.status != ApprovalStatus.PENDING:
                    raise ValueError(f"Request {request_id} is not pending")
                
                if datetime.now() > request.expires_at:
                    request.status = ApprovalStatus.EXPIRED
                    self.stats['requests_expired'] += 1
                    raise ValueError(f"Request {request_id} has expired")
                
                # Validate admin permissions
                if not self._validate_admin_permissions(admin_id, request.network_id):
                    raise ValueError(f"Admin {admin_id} does not have permission for network {request.network_id}")
                
                # Process request
                processed_at = datetime.now()
                processing_time = (processed_at - request.requested_at).total_seconds()
                
                if approve:
                    # Validate license compatibility
                    if not self._validate_license_compatibility(request):
                        raise ValueError("License not compatible with network requirements")
                    
                    request.status = ApprovalStatus.APPROVED
                    self.stats['requests_approved'] += 1
                    
                    # Generate network configuration for approved request
                    network_config = self._generate_network_config(request)
                    
                else:
                    request.status = ApprovalStatus.REJECTED
                    self.stats['requests_rejected'] += 1
                    network_config = None
                
                # Update request
                request.processed_by = admin_id
                request.processed_at = processed_at
                request.admin_notes = admin_notes
                
                # Move to processed requests
                self.processed_requests[request_id] = request
                del self.pending_requests[request_id]
                
                # Update statistics
                self._update_processing_time_stats(processing_time)
                
                # Create response
                response = ApprovalResponse(
                    request_id=request_id,
                    status=request.status,
                    admin_id=admin_id,
                    admin_notes=admin_notes,
                    processed_at=processed_at,
                    network_config=network_config,
                    security_token=request.security_token
                )
                
                logger.info(f"Approval request {request_id} {'approved' if approve else 'rejected'} by {admin_id}")
                
                return response
                
        except Exception as e:
            logger.error(f"Failed to process approval request {request_id}: {e}", exc_info=True)
            raise 
   
    def get_pending_requests(self, network_id: str = None,
                           priority: ApprovalPriority = None) -> List[ApprovalRequest]:
        """
        Get pending approval requests with optional filtering
        
        Args:
            network_id: Filter by network ID
            priority: Filter by priority level
            
        Returns:
            List of pending requests
        """
        try:
            with self._lock:
                requests = list(self.pending_requests.values())
                
                # Apply filters
                if network_id:
                    requests = [r for r in requests if r.network_id == network_id]
                
                if priority:
                    requests = [r for r in requests if r.priority == priority]
                
                # Sort by priority and request time
                priority_order = {
                    ApprovalPriority.URGENT: 4,
                    ApprovalPriority.HIGH: 3,
                    ApprovalPriority.NORMAL: 2,
                    ApprovalPriority.LOW: 1
                }
                
                requests.sort(key=lambda r: (
                    -priority_order.get(r.priority, 0),
                    r.requested_at
                ))
                
                return requests
                
        except Exception as e:
            logger.error(f"Failed to get pending requests: {e}", exc_info=True)
            return []
    
    def get_request_status(self, request_id: str) -> Optional[ApprovalRequest]:
        """
        Get status of a specific request
        
        Args:
            request_id: ID of the request
            
        Returns:
            Request object or None if not found
        """
        try:
            with self._lock:
                # Check pending requests
                if request_id in self.pending_requests:
                    return self.pending_requests[request_id]
                
                # Check processed requests
                if request_id in self.processed_requests:
                    return self.processed_requests[request_id]
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get request status {request_id}: {e}", exc_info=True)
            return None
    
    def cancel_approval_request(self, request_id: str, reason: str = "") -> bool:
        """
        Cancel a pending approval request
        
        Args:
            request_id: ID of the request to cancel
            reason: Cancellation reason
            
        Returns:
            True if cancelled successfully
        """
        try:
            with self._lock:
                if request_id not in self.pending_requests:
                    return False
                
                request = self.pending_requests[request_id]
                request.status = ApprovalStatus.CANCELLED
                request.admin_notes = f"Cancelled: {reason}"
                request.processed_at = datetime.now()
                
                # Move to processed requests
                self.processed_requests[request_id] = request
                del self.pending_requests[request_id]
                
                self.stats['requests_cancelled'] += 1
                
                logger.info(f"Approval request {request_id} cancelled: {reason}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to cancel approval request {request_id}: {e}", exc_info=True)
            return False
    
    def cleanup_expired_requests(self) -> int:
        """
        Clean up expired requests
        
        Returns:
            Number of requests cleaned up
        """
        try:
            with self._lock:
                current_time = datetime.now()
                expired_requests = []
                
                # Find expired pending requests
                for request_id, request in self.pending_requests.items():
                    if current_time > request.expires_at:
                        expired_requests.append(request_id)
                
                # Move expired requests to processed
                for request_id in expired_requests:
                    request = self.pending_requests[request_id]
                    request.status = ApprovalStatus.EXPIRED
                    request.processed_at = current_time
                    
                    self.processed_requests[request_id] = request
                    del self.pending_requests[request_id]
                    
                    self.stats['requests_expired'] += 1
                
                # Clean up old processed requests (keep for 7 days)
                cutoff_time = current_time - timedelta(days=7)
                old_processed = []
                
                for request_id, request in self.processed_requests.items():
                    if request.processed_at and request.processed_at < cutoff_time:
                        old_processed.append(request_id)
                
                for request_id in old_processed:
                    del self.processed_requests[request_id]
                
                total_cleaned = len(expired_requests) + len(old_processed)
                self.stats['last_cleanup'] = current_time
                
                if total_cleaned > 0:
                    logger.info(f"Cleaned up {total_cleaned} requests ({len(expired_requests)} expired, {len(old_processed)} old)")
                
                return total_cleaned
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired requests: {e}", exc_info=True)
            return 0
    
    def get_approval_statistics(self) -> Dict[str, Any]:
        """
        Get approval system statistics
        
        Returns:
            Dictionary with statistics
        """
        try:
            with self._lock:
                stats = self.stats.copy()
                stats['pending_requests_count'] = len(self.pending_requests)
                stats['processed_requests_count'] = len(self.processed_requests)
                stats['managed_networks_count'] = len(self.managed_networks)
                
                # Calculate approval rate
                total_processed = (stats['requests_approved'] + 
                                stats['requests_rejected'] + 
                                stats['requests_expired'] + 
                                stats['requests_cancelled'])
                
                if total_processed > 0:
                    stats['approval_rate'] = stats['requests_approved'] / total_processed
                else:
                    stats['approval_rate'] = 0.0
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get approval statistics: {e}", exc_info=True)
            return {}
    
    # === PRIVATE METHODS ===
    
    def _generate_security_key(self) -> str:
        """Generate security key for token creation"""
        return hashlib.sha256(f"{self.admin_node_id}_{time.time()}".encode()).hexdigest()
    
    def _generate_security_token(self, requester_node_id: str, network_id: str) -> str:
        """Generate security token for request validation"""
        data = f"{requester_node_id}_{network_id}_{time.time()}"
        return hmac.new(
            self.security_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()[:self.SECURITY_TOKEN_LENGTH]
    
    def _generate_license_hash(self, license_key: str) -> str:
        """Generate hash of license key for privacy"""
        if not license_key:
            return ""
        return hashlib.sha256(license_key.encode()).hexdigest()[:16]
    
    def _validate_admin_permissions(self, admin_id: str, network_id: str) -> bool:
        """Validate admin permissions for network"""
        try:
            # Check if admin is the network admin
            if admin_id != self.admin_node_id:
                return False
            
            # Check if network is managed by this admin
            if network_id not in self.managed_networks:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Admin permission validation failed: {e}", exc_info=True)
            return False
    
    def _validate_license_compatibility(self, request: ApprovalRequest) -> bool:
        """Validate license compatibility with network requirements"""
        try:
            network = self.managed_networks.get(request.network_id)
            if not network:
                return False
            
            # Get requester license tier
            requester_tier = SubscriptionTier(request.license_tier)
            required_tier = network.required_license_tier
            
            # Tier hierarchy: FREE < PRO < ENT
            tier_levels = {
                SubscriptionTier.FREE: 1,
                SubscriptionTier.PRO: 2,
                SubscriptionTier.ENT: 3
            }
            
            requester_level = tier_levels.get(requester_tier, 0)
            required_level = tier_levels.get(required_tier, 3)
            
            return requester_level >= required_level
            
        except Exception as e:
            logger.error(f"License compatibility validation failed: {e}", exc_info=True)
            return False
    
    def _generate_network_config(self, request: ApprovalRequest) -> Dict[str, Any]:
        """Generate network configuration for approved request"""
        try:
            network = self.managed_networks.get(request.network_id)
            if not network:
                return {}
            
            # Create network configuration
            config = {
                'network_id': network.network_id,
                'network_name': network.network_name,
                'model_id': network.model_id,
                'admin_host': network.admin_host,
                'admin_port': network.admin_port,
                'worker_nodes': [],  # Will be populated by network manager
                'security_token': request.security_token,
                'approved_at': datetime.now().isoformat(),
                'approved_by': self.admin_node_id,
                'requester_permissions': self._get_requester_permissions(request)
            }
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to generate network config: {e}", exc_info=True)
            return {}
    
    def _get_requester_permissions(self, request: ApprovalRequest) -> Dict[str, Any]:
        """Get permissions for approved requester"""
        try:
            license_tier = SubscriptionTier(request.license_tier)
            
            permissions = {
                'can_inference': True,
                'can_upload_models': license_tier in [SubscriptionTier.PRO, SubscriptionTier.ENT],
                'can_create_sessions': True,
                'max_concurrent_sessions': 1 if license_tier == SubscriptionTier.FREE else 5,
                'priority_level': 'normal' if license_tier == SubscriptionTier.FREE else 'high'
            }
            
            return permissions
            
        except Exception as e:
            logger.error(f"Failed to get requester permissions: {e}", exc_info=True)
            return {}
    
    def _notify_approval_callbacks(self, request: ApprovalRequest) -> None:
        """Notify approval callbacks of new request"""
        for callback in self.approval_callbacks:
            try:
                callback(request)
            except Exception as e:
                logger.error(f"Approval callback error: {e}", exc_info=True)
    
    def _update_processing_time_stats(self, processing_time: float) -> None:
        """Update average processing time statistics"""
        try:
            total_processed = (self.stats['requests_approved'] + 
                             self.stats['requests_rejected'])
            
            if total_processed == 1:
                self.stats['average_processing_time'] = processing_time
            else:
                # Calculate running average
                current_avg = self.stats['average_processing_time']
                self.stats['average_processing_time'] = (
                    (current_avg * (total_processed - 1) + processing_time) / total_processed
                )
                
        except Exception as e:
            logger.error(f"Failed to update processing time stats: {e}", exc_info=True)


# === UTILITY FUNCTIONS ===

def create_approval_system(admin_node_id: str, 
                         managed_networks: Dict[str, NetworkInfo] = None) -> AdminApprovalSystem:
    """
    Create and configure an admin approval system
    
    Args:
        admin_node_id: ID of the admin node
        managed_networks: Networks managed by this admin
        
    Returns:
        Configured AdminApprovalSystem instance
    """
    return AdminApprovalSystem(admin_node_id, managed_networks)


async def auto_cleanup_service(approval_system: AdminApprovalSystem, 
                             interval: int = 3600) -> None:
    """
    Automatic cleanup service for expired requests
    
    Args:
        approval_system: Approval system to clean up
        interval: Cleanup interval in seconds
    """
    logger.info(f"Starting auto-cleanup service with {interval}s interval")
    
    while True:
        try:
            cleaned = approval_system.cleanup_expired_requests()
            if cleaned > 0:
                logger.info(f"Auto-cleanup removed {cleaned} expired requests")
            
            await asyncio.sleep(interval)
            
        except Exception as e:
            logger.error(f"Auto-cleanup service error: {e}", exc_info=True)
            await asyncio.sleep(60)  # Wait 1 minute before retry


if __name__ == "__main__":
    # Example usage and testing
    import asyncio
    from core.network_manager import NetworkInfo, NetworkType, NetworkStatus
    
    async def test_approval_system():
        """Test approval system functionality"""
        print("Testing Admin Approval System...")
        
        # Create test network
        test_network = NetworkInfo(
            network_id="test_net_001",
            network_name="Test Network",
            network_type=NetworkType.PRIVATE,
            admin_node_id="admin_001",
            admin_host="192.168.1.100",
            admin_port=8080,
            model_id="llama-7b",
            model_name="Llama 7B",
            required_license_tier=SubscriptionTier.PRO,
            max_clients=20,
            current_clients=0,
            status=NetworkStatus.ACTIVE,
            created_at=datetime.now(),
            last_seen=datetime.now()
        )
        
        # Create approval system
        admin_id = "admin_001"
        approval_system = AdminApprovalSystem(admin_id, {"test_net_001": test_network})
        
        # Create approval request
        requester_info = {
            'license_tier': 'PRO',
            'license_key': 'TIKT-PRO-12M-TEST001',
            'node_capabilities': ['inference', 'storage']
        }
        
        request = approval_system.create_approval_request(
            requester_node_id="requester_001",
            requester_address="192.168.1.200",
            network_id="test_net_001",
            requester_info=requester_info,
            priority=ApprovalPriority.NORMAL
        )
        
        print(f"Created approval request: {request.request_id}")
        print(f"Status: {request.status.value}")
        print(f"Priority: {request.priority.value}")
        
        # Get pending requests
        pending = approval_system.get_pending_requests()
        print(f"Pending requests: {len(pending)}")
        
        # Process approval request
        response = approval_system.process_approval_request(
            request.request_id,
            admin_id,
            approve=True,
            admin_notes="Approved for testing"
        )
        
        print(f"Request processed: {response.status.value}")
        print(f"Network config provided: {response.network_config is not None}")
        
        # Get statistics
        stats = approval_system.get_approval_statistics()
        print(f"Approval statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    # Run test
    asyncio.run(test_approval_system())