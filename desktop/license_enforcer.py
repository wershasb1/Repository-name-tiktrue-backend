"""
License Enforcement Module for TikTrue Distributed LLM Platform
Integrates license validation and enforcement throughout the system
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from functools import wraps
from dataclasses import dataclass

from security.license_validator import LicenseValidator
from license_models import LicenseInfo, SubscriptionTier, ValidationStatus
from license_storage import LicenseStorage

logger = logging.getLogger("LicenseEnforcer")


@dataclass
class ClientConnection:
    """Represents a client connection"""
    client_id: str
    network_id: str
    connected_at: datetime
    last_activity: datetime
    session_count: int = 0


class LicenseEnforcer:
    """
    Central license enforcement system
    Manages license validation and enforcement across all system components
    """
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize license enforcer
        
        Args:
            storage_dir: Optional custom storage directory for licenses
        """
        self.validator = LicenseValidator()
        self.storage = LicenseStorage()
        
        # Current license information
        self.current_license: Optional[LicenseInfo] = None
        self.license_loaded_at: Optional[datetime] = None
        
        # Client connection tracking
        self.active_clients: Dict[str, ClientConnection] = {}
        self.client_lock = asyncio.Lock()
        
        # Model access tracking
        self.accessed_models: Set[str] = set()
        
        # Feature usage tracking
        self.used_features: Set[str] = set()
        
        # License check intervals
        self.license_check_interval = 300  # 5 minutes
        self.last_license_check = datetime.now()
        
        # Load license on initialization
        self._load_license()
        
        logger.info("LicenseEnforcer initialized")
    
    def _load_license(self) -> bool:
        """
        Load license from storage
        
        Returns:
            True if license loaded successfully, False otherwise
        """
        try:
            self.current_license = self.storage.load_license_info()
            if self.current_license:
                self.license_loaded_at = datetime.now()
                logger.info(f"License loaded: {self.current_license.plan.value} tier, "
                          f"expires {self.current_license.expires_at}")
                return True
            else:
                logger.warning("No license found in storage")
                return False
        except Exception as e:
            logger.error(f"Failed to load license: {e}")
            return False
    
    def install_license(self, license_key: str) -> bool:
        """
        Install a new license key
        
        Args:
            license_key: License key to install
            
        Returns:
            True if license installed successfully, False otherwise
        """
        try:
            logger.info(f"Installing license: {license_key[:20]}...")
            
            # Validate license key
            license_info = self.validator.validate_license_key(license_key)
            
            if license_info.status != ValidationStatus.VALID:
                logger.error(f"License validation failed: {license_info.status}")
                return False
            
            # Save license to storage
            if not self.storage.save_license_locally(license_info):
                logger.error("Failed to save license to storage")
                return False
            
            # Update current license
            self.current_license = license_info
            self.license_loaded_at = datetime.now()
            
            logger.info(f"License installed successfully: {license_info.plan.value} tier")
            return True
            
        except Exception as e:
            logger.error(f"Failed to install license: {e}")
            return False
    
    def get_license_status(self) -> Dict[str, Any]:
        """
        Get current license status information
        
        Returns:
            Dictionary with license status details
        """
        if not self.current_license:
            return {
                "status": "no_license",
                "message": "No license installed",
                "valid": False
            }
        
        # Check if license needs revalidation
        if self._should_recheck_license():
            self._revalidate_license()
        
        now = datetime.now()
        days_remaining = (self.current_license.expires_at - now).days if self.current_license.expires_at > now else 0
        
        return {
            "status": self.current_license.status.value,
            "plan": self.current_license.plan.value,
            "expires_at": self.current_license.expires_at.isoformat(),
            "days_remaining": days_remaining,
            "max_clients": self.current_license.max_clients if self.current_license.max_clients != -1 else "Unlimited",
            "current_clients": len(self.active_clients),
            "allowed_models": len(self.current_license.allowed_models),
            "allowed_features": len(self.current_license.allowed_features),
            "valid": self.current_license.status == ValidationStatus.VALID and days_remaining > 0,
            "hardware_bound": bool(self.current_license.hardware_signature)
        }
    
    async def check_client_connection_allowed(self, client_id: str, network_id: str) -> bool:
        """
        Check if a client connection is allowed
        
        Args:
            client_id: Unique client identifier
            network_id: Network identifier
            
        Returns:
            True if connection is allowed, False otherwise
        """
        async with self.client_lock:
            if not self._is_license_valid():
                logger.warning(f"Client connection denied for {client_id}: Invalid license")
                return False
            
            # Check if client is already connected
            if client_id in self.active_clients:
                # Update last activity
                self.active_clients[client_id].last_activity = datetime.now()
                return True
            
            # Check client limit
            current_clients = len(self.active_clients)
            if not self.validator.enforce_subscription_limits(
                "client_connect", self.current_license, current_clients
            ):
                logger.warning(f"Client connection denied for {client_id}: Client limit reached")
                return False
            
            # Add client to active connections
            self.active_clients[client_id] = ClientConnection(
                client_id=client_id,
                network_id=network_id,
                connected_at=datetime.now(),
                last_activity=datetime.now()
            )
            
            logger.info(f"Client connected: {client_id} on network {network_id} "
                       f"({len(self.active_clients)}/{self.current_license.max_clients if self.current_license.max_clients != -1 else 'unlimited'})")
            return True
    
    async def register_client_disconnect(self, client_id: str) -> None:
        """
        Register client disconnection
        
        Args:
            client_id: Client identifier that disconnected
        """
        async with self.client_lock:
            if client_id in self.active_clients:
                network_id = self.active_clients[client_id].network_id
                del self.active_clients[client_id]
                logger.info(f"Client disconnected: {client_id} from network {network_id} "
                           f"({len(self.active_clients)} remaining)")
    
    def check_model_access_allowed(self, model_id: str) -> bool:
        """
        Check if model access is allowed
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if access is allowed, False otherwise
        """
        if not self._is_license_valid():
            logger.warning(f"Model access denied for {model_id}: Invalid license")
            return False
        
        allowed = self.validator.enforce_subscription_limits(
            "model_access", self.current_license, model_id=model_id
        )
        
        if allowed:
            self.accessed_models.add(model_id)
            logger.debug(f"Model access granted: {model_id}")
        else:
            logger.warning(f"Model access denied: {model_id}")
        
        return allowed
    
    def check_feature_access_allowed(self, feature: str) -> bool:
        """
        Check if feature access is allowed
        
        Args:
            feature: Feature identifier
            
        Returns:
            True if access is allowed, False otherwise
        """
        if not self._is_license_valid():
            logger.warning(f"Feature access denied for {feature}: Invalid license")
            return False
        
        allowed = self.validator.enforce_subscription_limits(
            "feature_access", self.current_license, feature=feature
        )
        
        if allowed:
            self.used_features.add(feature)
            logger.debug(f"Feature access granted: {feature}")
        else:
            logger.warning(f"Feature access denied: {feature}")
        
        return allowed
    
    async def cleanup_inactive_clients(self, timeout_minutes: int = 30) -> int:
        """
        Clean up inactive client connections
        
        Args:
            timeout_minutes: Timeout in minutes for inactive clients
            
        Returns:
            Number of clients cleaned up
        """
        async with self.client_lock:
            now = datetime.now()
            timeout_threshold = now - timedelta(minutes=timeout_minutes)
            
            inactive_clients = [
                client_id for client_id, client in self.active_clients.items()
                if client.last_activity < timeout_threshold
            ]
            
            for client_id in inactive_clients:
                logger.info(f"Cleaning up inactive client: {client_id}")
                del self.active_clients[client_id]
            
            return len(inactive_clients)
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        Get license usage statistics
        
        Returns:
            Dictionary with usage statistics
        """
        return {
            "active_clients": len(self.active_clients),
            "client_details": [
                {
                    "client_id": client.client_id,
                    "network_id": client.network_id,
                    "connected_at": client.connected_at.isoformat(),
                    "last_activity": client.last_activity.isoformat(),
                    "session_count": client.session_count
                }
                for client in self.active_clients.values()
            ],
            "accessed_models": list(self.accessed_models),
            "used_features": list(self.used_features),
            "license_loaded_at": self.license_loaded_at.isoformat() if self.license_loaded_at else None
        }
    
    def _is_license_valid(self) -> bool:
        """
        Check if current license is valid
        
        Returns:
            True if license is valid, False otherwise
        """
        if not self.current_license:
            return False
        
        if self.current_license.status != ValidationStatus.VALID:
            return False
        
        if datetime.now() >= self.current_license.expires_at:
            return False
        
        return True
    
    def _should_recheck_license(self) -> bool:
        """
        Check if license should be rechecked
        
        Returns:
            True if license should be rechecked
        """
        if not self.last_license_check:
            return True
        
        return (datetime.now() - self.last_license_check).seconds > self.license_check_interval
    
    def _revalidate_license(self) -> None:
        """
        Revalidate current license
        """
        try:
            if self.current_license:
                # Re-validate the license key
                revalidated_license = self.validator.validate_license_key(self.current_license.license_key)
                
                if revalidated_license.status != self.current_license.status:
                    logger.warning(f"License status changed: {self.current_license.status} -> {revalidated_license.status}")
                    self.current_license = revalidated_license
                
                self.last_license_check = datetime.now()
                
        except Exception as e:
            logger.error(f"License revalidation failed: {e}")


# Global license enforcer instance
_global_enforcer: Optional[LicenseEnforcer] = None


def get_license_enforcer(storage_dir: Optional[str] = None) -> LicenseEnforcer:
    """
    Get global license enforcer instance
    
    Args:
        storage_dir: Optional custom storage directory
        
    Returns:
        LicenseEnforcer instance
    """
    global _global_enforcer
    
    if _global_enforcer is None:
        _global_enforcer = LicenseEnforcer(storage_dir)
    
    return _global_enforcer


def require_license(operation: str = "general"):
    """
    Decorator to require valid license for function execution
    
    Args:
        operation: Operation type for logging
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            enforcer = get_license_enforcer()
            if not enforcer._is_license_valid():
                logger.error(f"Operation {operation} denied: Invalid license")
                raise PermissionError(f"Valid license required for {operation}")
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            enforcer = get_license_enforcer()
            if not enforcer._is_license_valid():
                logger.error(f"Operation {operation} denied: Invalid license")
                raise PermissionError(f"Valid license required for {operation}")
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def require_model_access(model_id: str):
    """
    Decorator to require model access permission
    
    Args:
        model_id: Model identifier
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            enforcer = get_license_enforcer()
            if not enforcer.check_model_access_allowed(model_id):
                raise PermissionError(f"Model access denied: {model_id}")
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            enforcer = get_license_enforcer()
            if not enforcer.check_model_access_allowed(model_id):
                raise PermissionError(f"Model access denied: {model_id}")
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def require_feature_access(feature: str):
    """
    Decorator to require feature access permission
    
    Args:
        feature: Feature identifier
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            enforcer = get_license_enforcer()
            if not enforcer.check_feature_access_allowed(feature):
                raise PermissionError(f"Feature access denied: {feature}")
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            enforcer = get_license_enforcer()
            if not enforcer.check_feature_access_allowed(feature):
                raise PermissionError(f"Feature access denied: {feature}")
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Convenience functions for integration

async def validate_client_connection(client_id: str, network_id: str) -> bool:
    """
    Validate client connection against license
    
    Args:
        client_id: Client identifier
        network_id: Network identifier
        
    Returns:
        True if connection is allowed
    """
    enforcer = get_license_enforcer()
    return await enforcer.check_client_connection_allowed(client_id, network_id)


async def register_client_disconnect(client_id: str) -> None:
    """
    Register client disconnection
    
    Args:
        client_id: Client identifier
    """
    enforcer = get_license_enforcer()
    await enforcer.register_client_disconnect(client_id)


def validate_model_access(model_id: str) -> bool:
    """
    Validate model access against license
    
    Args:
        model_id: Model identifier
        
    Returns:
        True if access is allowed
    """
    enforcer = get_license_enforcer()
    return enforcer.check_model_access_allowed(model_id)


def validate_feature_access(feature: str) -> bool:
    """
    Validate feature access against license
    
    Args:
        feature: Feature identifier
        
    Returns:
        True if access is allowed
    """
    enforcer = get_license_enforcer()
    return enforcer.check_feature_access_allowed(feature)


def get_current_license_status() -> Dict[str, Any]:
    """
    Get current license status
    
    Returns:
        License status dictionary
    """
    enforcer = get_license_enforcer()
    return enforcer.get_license_status()


def install_license_key(license_key: str) -> bool:
    """
    Install a license key
    
    Args:
        license_key: License key to install
        
    Returns:
        True if installation was successful
    """
    enforcer = get_license_enforcer()
    return enforcer.install_license(license_key)


if __name__ == "__main__":
    # Example usage and testing
    import tempfile
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    
    async def test_license_enforcer():
        """Test license enforcer functionality"""
        print("=== Testing License Enforcer ===")
        
        # Create enforcer with temporary storage
        with tempfile.TemporaryDirectory() as temp_dir:
            enforcer = LicenseEnforcer(temp_dir)
            
            # Test without license
            print(f"\n--- Without License ---")
            status = enforcer.get_license_status()
            print(f"Status: {status['status']}")
            print(f"Valid: {status['valid']}")
            
            # Install test license
            print(f"\n--- Installing License ---")
            test_license = "TIKT-PRO-6M-XYZ789"
            success = enforcer.install_license(test_license)
            print(f"Installation successful: {success}")
            
            if success:
                # Test license status
                print(f"\n--- License Status ---")
                status = enforcer.get_license_status()
                for key, value in status.items():
                    print(f"{key}: {value}")
                
                # Test client connections
                print(f"\n--- Client Connections ---")
                for i in range(3):
                    client_id = f"client_{i}"
                    allowed = await enforcer.check_client_connection_allowed(client_id, "test_network")
                    print(f"Client {client_id} connection allowed: {allowed}")
                
                # Test model access
                print(f"\n--- Model Access ---")
                test_models = ["llama3_1_8b_fp16", "unauthorized_model"]
                for model in test_models:
                    allowed = enforcer.check_model_access_allowed(model)
                    print(f"Model {model} access allowed: {allowed}")
                
                # Test feature access
                print(f"\n--- Feature Access ---")
                test_features = ["session_save", "admin_panel"]
                for feature in test_features:
                    allowed = enforcer.check_feature_access_allowed(feature)
                    print(f"Feature {feature} access allowed: {allowed}")
                
                # Test usage statistics
                print(f"\n--- Usage Statistics ---")
                stats = enforcer.get_usage_statistics()
                print(f"Active clients: {stats['active_clients']}")
                print(f"Accessed models: {stats['accessed_models']}")
                print(f"Used features: {stats['used_features']}")
    
    # Run test
    asyncio.run(test_license_enforcer())