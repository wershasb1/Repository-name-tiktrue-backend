"""
Access Control System
Implements role-based permission system, license-based feature access control,
and resource access management based on subscription tier
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from security.license_validator import LicenseInfo, SubscriptionTier


class UserRole(Enum):
    """User role enumeration for role-based access control"""
    ADMIN = "admin"         # Full system administration
    OPERATOR = "operator"   # Network and worker management
    DEVELOPER = "developer" # API access and development
    CLIENT = "client"       # Basic client access
    GUEST = "guest"         # Read-only guest access


class Permission(Enum):
    """Specific permission enumeration"""
    # Network permissions
    NETWORK_VIEW = "network_view"
    NETWORK_MODIFY = "network_modify"
    NETWORK_CREATE = "network_create"
    
    # Worker permissions
    WORKER_VIEW = "worker_view"
    WORKER_MANAGE = "worker_manage"
    
    # Model permissions
    MODEL_VIEW = "model_view"
    MODEL_UPLOAD = "model_upload"
    MODEL_DELETE = "model_delete"
    
    # API permissions
    API_INFERENCE = "api_inference"
    
    # System permissions
    SYSTEM_ADMIN = "system_admin"
    SYSTEM_MONITOR = "system_monitor"
    SYSTEM_BACKUP = "system_backup"
    
    # User permissions
    USER_VIEW = "user_view"
    USER_MANAGE = "user_manage"


@dataclass
class User:
    """User information for access control"""
    user_id: str
    username: str
    email: str
    password_hash: str
    salt: str
    roles: Set[UserRole] = field(default_factory=set)
    permissions: Set[Permission] = field(default_factory=set)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuthenticationManager:
    """Placeholder for authentication manager - would be imported from security.auth_manager.py in full implementation"""
    pass


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AccessControl")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/access_control.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class ResourceType(Enum):
    """Resource type enumeration"""
    NETWORK = "network"
    WORKER = "worker"
    MODEL = "model"
    API_ENDPOINT = "api_endpoint"
    SYSTEM_CONFIG = "system_config"
    USER_DATA = "user_data"
    LICENSE = "license"
    BACKUP = "backup"
    MONITORING = "monitoring"


class AccessLevel(Enum):
    """Access level enumeration"""
    NONE = "none"           # No access
    READ = "read"           # Read-only access
    WRITE = "write"         # Read and write access
    EXECUTE = "execute"     # Execute operations
    ADMIN = "admin"         # Full administrative access
    OWNER = "owner"         # Resource ownership


class FeatureFlag(Enum):
    """Feature flags based on license tier"""
    # Basic features (available to all tiers)
    BASIC_INFERENCE = "basic_inference"
    SINGLE_NETWORK = "single_network"
    LOCAL_MODELS = "local_models"
    
    # Professional features
    MULTI_NETWORK = "multi_network"
    REMOTE_MODELS = "remote_models"
    API_ACCESS = "api_access"
    BASIC_MONITORING = "basic_monitoring"
    
    # Enterprise features
    ADVANCED_MONITORING = "advanced_monitoring"
    BACKUP_RESTORE = "backup_restore"
    CUSTOM_ENCRYPTION = "custom_encryption"
    PRIORITY_SUPPORT = "priority_support"
    UNLIMITED_WORKERS = "unlimited_workers"
    ADVANCED_ANALYTICS = "advanced_analytics"


# License tier to feature mapping
TIER_FEATURES = {
    SubscriptionTier.FREE: {
        FeatureFlag.BASIC_INFERENCE,
        FeatureFlag.SINGLE_NETWORK,
        FeatureFlag.LOCAL_MODELS
    },
    SubscriptionTier.PRO: {
        FeatureFlag.BASIC_INFERENCE,
        FeatureFlag.SINGLE_NETWORK,
        FeatureFlag.LOCAL_MODELS,
        FeatureFlag.MULTI_NETWORK,
        FeatureFlag.REMOTE_MODELS,
        FeatureFlag.API_ACCESS,
        FeatureFlag.BASIC_MONITORING
    },
    SubscriptionTier.ENT: {
        FeatureFlag.BASIC_INFERENCE,
        FeatureFlag.SINGLE_NETWORK,
        FeatureFlag.LOCAL_MODELS,
        FeatureFlag.MULTI_NETWORK,
        FeatureFlag.REMOTE_MODELS,
        FeatureFlag.API_ACCESS,
        FeatureFlag.BASIC_MONITORING,
        FeatureFlag.ADVANCED_MONITORING,
        FeatureFlag.BACKUP_RESTORE,
        FeatureFlag.CUSTOM_ENCRYPTION,
        FeatureFlag.PRIORITY_SUPPORT,
        FeatureFlag.UNLIMITED_WORKERS,
        FeatureFlag.ADVANCED_ANALYTICS
    }
}

# Role-based resource access permissions
ROLE_RESOURCE_PERMISSIONS = {
    UserRole.ADMIN: {
        ResourceType.NETWORK: AccessLevel.ADMIN,
        ResourceType.WORKER: AccessLevel.ADMIN,
        ResourceType.MODEL: AccessLevel.ADMIN,
        ResourceType.API_ENDPOINT: AccessLevel.ADMIN,
        ResourceType.SYSTEM_CONFIG: AccessLevel.ADMIN,
        ResourceType.USER_DATA: AccessLevel.ADMIN,
        ResourceType.LICENSE: AccessLevel.ADMIN,
        ResourceType.BACKUP: AccessLevel.ADMIN,
        ResourceType.MONITORING: AccessLevel.ADMIN
    },
    UserRole.OPERATOR: {
        ResourceType.NETWORK: AccessLevel.WRITE,
        ResourceType.WORKER: AccessLevel.WRITE,
        ResourceType.MODEL: AccessLevel.READ,
        ResourceType.API_ENDPOINT: AccessLevel.READ,
        ResourceType.SYSTEM_CONFIG: AccessLevel.READ,
        ResourceType.USER_DATA: AccessLevel.READ,
        ResourceType.LICENSE: AccessLevel.READ,
        ResourceType.BACKUP: AccessLevel.EXECUTE,
        ResourceType.MONITORING: AccessLevel.READ
    },
    UserRole.DEVELOPER: {
        ResourceType.NETWORK: AccessLevel.READ,
        ResourceType.WORKER: AccessLevel.READ,
        ResourceType.MODEL: AccessLevel.READ,
        ResourceType.API_ENDPOINT: AccessLevel.EXECUTE,
        ResourceType.SYSTEM_CONFIG: AccessLevel.READ,
        ResourceType.USER_DATA: AccessLevel.READ,
        ResourceType.LICENSE: AccessLevel.READ,
        ResourceType.BACKUP: AccessLevel.NONE,
        ResourceType.MONITORING: AccessLevel.READ
    },
    UserRole.CLIENT: {
        ResourceType.NETWORK: AccessLevel.READ,
        ResourceType.WORKER: AccessLevel.NONE,
        ResourceType.MODEL: AccessLevel.READ,
        ResourceType.API_ENDPOINT: AccessLevel.EXECUTE,
        ResourceType.SYSTEM_CONFIG: AccessLevel.NONE,
        ResourceType.USER_DATA: AccessLevel.READ,
        ResourceType.LICENSE: AccessLevel.NONE,
        ResourceType.BACKUP: AccessLevel.NONE,
        ResourceType.MONITORING: AccessLevel.NONE
    },
    UserRole.GUEST: {
        ResourceType.NETWORK: AccessLevel.READ,
        ResourceType.WORKER: AccessLevel.NONE,
        ResourceType.MODEL: AccessLevel.READ,
        ResourceType.API_ENDPOINT: AccessLevel.NONE,
        ResourceType.SYSTEM_CONFIG: AccessLevel.NONE,
        ResourceType.USER_DATA: AccessLevel.NONE,
        ResourceType.LICENSE: AccessLevel.NONE,
        ResourceType.BACKUP: AccessLevel.NONE,
        ResourceType.MONITORING: AccessLevel.NONE
    }
}


@dataclass
class AccessRequest:
    """Access request information"""
    user_id: str
    resource_type: ResourceType
    resource_id: str
    access_level: AccessLevel
    timestamp: datetime = field(default_factory=datetime.now)
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessResult:
    """Access control result"""
    granted: bool
    reason: str
    access_level: AccessLevel = AccessLevel.NONE
    restrictions: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceQuota:
    """Resource quota information"""
    resource_type: ResourceType
    max_count: int
    current_count: int = 0
    max_size_mb: Optional[int] = None
    current_size_mb: int = 0
    reset_period_hours: int = 24
    last_reset: datetime = field(default_factory=datetime.now)


class AccessControlManager:
    """
    Access control and authorization manager
    """
    
    def __init__(self, 
                 license_info: Optional[LicenseInfo] = None,
                 auth_manager: Optional[AuthenticationManager] = None,
                 quotas_file: str = "data/resource_quotas.json"):
        """
        Initialize access control manager
        
        Args:
            license_info: License information for feature access control
            auth_manager: Authentication manager instance
            quotas_file: Path to resource quotas file
        """
        self.license_info = license_info
        self.auth_manager = auth_manager
        self.quotas_file = quotas_file
        
        # Resource quotas based on license tier
        self.resource_quotas: Dict[str, ResourceQuota] = {}
        
        # Access cache for performance
        self.access_cache: Dict[str, Tuple[AccessResult, datetime]] = {}
        self.cache_ttl_minutes = 5
        
        # Access audit log
        self.access_log: List[Dict[str, Any]] = []
        self.max_log_entries = 10000
        
        # Initialize quotas based on license
        self._initialize_quotas()
        
        # Load existing quotas
        self._load_quotas()
        
        logger.info("Access control manager initialized")
    
    def _initialize_quotas(self):
        """Initialize resource quotas based on license tier"""
        try:
            if not self.license_info:
                # Default quotas for no license
                self.resource_quotas = {
                    "networks": ResourceQuota(ResourceType.NETWORK, max_count=1),
                    "workers": ResourceQuota(ResourceType.WORKER, max_count=3),
                    "models": ResourceQuota(ResourceType.MODEL, max_count=2, max_size_mb=1024),
                    "api_calls": ResourceQuota(ResourceType.API_ENDPOINT, max_count=100, reset_period_hours=1)
                }
                return
            
            # Set quotas based on subscription tier
            if self.license_info.plan == SubscriptionTier.FREE:
                self.resource_quotas = {
                    "networks": ResourceQuota(ResourceType.NETWORK, max_count=1),
                    "workers": ResourceQuota(ResourceType.WORKER, max_count=3),
                    "models": ResourceQuota(ResourceType.MODEL, max_count=3, max_size_mb=2048),
                    "api_calls": ResourceQuota(ResourceType.API_ENDPOINT, max_count=1000, reset_period_hours=24)
                }
            elif self.license_info.plan == SubscriptionTier.PRO:
                self.resource_quotas = {
                    "networks": ResourceQuota(ResourceType.NETWORK, max_count=5),
                    "workers": ResourceQuota(ResourceType.WORKER, max_count=20),
                    "models": ResourceQuota(ResourceType.MODEL, max_count=10, max_size_mb=10240),
                    "api_calls": ResourceQuota(ResourceType.API_ENDPOINT, max_count=10000, reset_period_hours=24)
                }
            else:  # ENTERPRISE
                self.resource_quotas = {
                    "networks": ResourceQuota(ResourceType.NETWORK, max_count=-1),  # Unlimited
                    "workers": ResourceQuota(ResourceType.WORKER, max_count=-1),   # Unlimited
                    "models": ResourceQuota(ResourceType.MODEL, max_count=-1, max_size_mb=-1),  # Unlimited
                    "api_calls": ResourceQuota(ResourceType.API_ENDPOINT, max_count=-1, reset_period_hours=24)  # Unlimited
                }
            
            logger.info(f"Initialized quotas for tier: {self.license_info.plan.value}")
            
        except Exception as e:
            logger.error(f"Error initializing quotas: {e}")
    
    def _load_quotas(self):
        """Load resource quotas from file"""
        try:
            if os.path.exists(self.quotas_file):
                with open(self.quotas_file, "r") as f:
                    quotas_data = json.load(f)
                
                for quota_name, quota_data in quotas_data.items():
                    if quota_name in self.resource_quotas:
                        quota = self.resource_quotas[quota_name]
                        quota.current_count = quota_data.get("current_count", 0)
                        quota.current_size_mb = quota_data.get("current_size_mb", 0)
                        
                        if quota_data.get("last_reset"):
                            quota.last_reset = datetime.fromisoformat(quota_data["last_reset"])
                
                logger.info(f"Loaded quotas from {self.quotas_file}")
        
        except Exception as e:
            logger.error(f"Error loading quotas: {e}")
    
    def _save_quotas(self):
        """Save resource quotas to file"""
        try:
            quotas_data = {}
            
            for quota_name, quota in self.resource_quotas.items():
                quotas_data[quota_name] = {
                    "current_count": quota.current_count,
                    "current_size_mb": quota.current_size_mb,
                    "last_reset": quota.last_reset.isoformat()
                }
            
            os.makedirs(os.path.dirname(self.quotas_file), exist_ok=True)
            
            with open(self.quotas_file, "w") as f:
                json.dump(quotas_data, f, indent=2)
            
            logger.info(f"Saved quotas to {self.quotas_file}")
            
        except Exception as e:
            logger.error(f"Error saving quotas: {e}")
    
    def check_access(self, user: User, resource_type: ResourceType, 
                    resource_id: str, access_level: AccessLevel,
                    client_ip: Optional[str] = None,
                    user_agent: Optional[str] = None) -> AccessResult:
        """
        Check if user has access to a resource
        
        Args:
            user: User object
            resource_type: Type of resource
            resource_id: Resource identifier
            access_level: Required access level
            client_ip: Client IP address
            user_agent: Client user agent
            
        Returns:
            AccessResult object
        """
        try:
            # Create cache key
            cache_key = f"{user.user_id}:{resource_type.value}:{resource_id}:{access_level.value}"
            
            # Check cache first
            if cache_key in self.access_cache:
                cached_result, cached_time = self.access_cache[cache_key]
                if datetime.now() - cached_time < timedelta(minutes=self.cache_ttl_minutes):
                    return cached_result
            
            # Check if user is active
            if not user.is_active:
                result = AccessResult(
                    granted=False,
                    reason="User account is inactive",
                    access_level=AccessLevel.NONE
                )
                self._log_access_attempt(user, resource_type, resource_id, access_level, result, client_ip, user_agent)
                return result
            
            # Check license-based feature access
            feature_check = self._check_feature_access(resource_type, access_level)
            if not feature_check.granted:
                self._log_access_attempt(user, resource_type, resource_id, access_level, feature_check, client_ip, user_agent)
                return feature_check
            
            # Check role-based permissions
            role_check = self._check_role_permissions(user, resource_type, access_level)
            if not role_check.granted:
                self._log_access_attempt(user, resource_type, resource_id, access_level, role_check, client_ip, user_agent)
                return role_check
            
            # Check specific permissions
            permission_check = self._check_specific_permissions(user, resource_type, access_level)
            if not permission_check.granted:
                self._log_access_attempt(user, resource_type, resource_id, access_level, permission_check, client_ip, user_agent)
                return permission_check
            
            # Check resource quotas
            quota_check = self._check_resource_quotas(resource_type, access_level)
            if not quota_check.granted:
                self._log_access_attempt(user, resource_type, resource_id, access_level, quota_check, client_ip, user_agent)
                return quota_check
            
            # Access granted
            result = AccessResult(
                granted=True,
                reason="Access granted",
                access_level=access_level,
                expires_at=datetime.now() + timedelta(minutes=self.cache_ttl_minutes)
            )
            
            # Cache result
            self.access_cache[cache_key] = (result, datetime.now())
            
            # Log successful access
            self._log_access_attempt(user, resource_type, resource_id, access_level, result, client_ip, user_agent)
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking access: {e}")
            return AccessResult(
                granted=False,
                reason=f"Access check error: {str(e)}",
                access_level=AccessLevel.NONE
            )
    
    def _check_feature_access(self, resource_type: ResourceType, access_level: AccessLevel) -> AccessResult:
        """Check license-based feature access"""
        try:
            if not self.license_info:
                # No license - only basic features
                if resource_type in [ResourceType.NETWORK, ResourceType.MODEL] and access_level == AccessLevel.READ:
                    return AccessResult(granted=True, reason="Basic feature access")
                else:
                    return AccessResult(
                        granted=False,
                        reason="Feature requires valid license",
                        restrictions=["License required for this feature"]
                    )
            
            # Get available features for license tier
            available_features = TIER_FEATURES.get(self.license_info.plan, set())
            
            # Check specific feature requirements
            required_features = []
            
            if resource_type == ResourceType.NETWORK:
                if access_level in [AccessLevel.WRITE, AccessLevel.ADMIN]:
                    required_features.append(FeatureFlag.MULTI_NETWORK)
                else:
                    required_features.append(FeatureFlag.SINGLE_NETWORK)
            
            elif resource_type == ResourceType.API_ENDPOINT:
                required_features.append(FeatureFlag.API_ACCESS)
            
            elif resource_type == ResourceType.MONITORING:
                if access_level == AccessLevel.ADMIN:
                    required_features.append(FeatureFlag.ADVANCED_MONITORING)
                else:
                    required_features.append(FeatureFlag.BASIC_MONITORING)
            
            elif resource_type == ResourceType.BACKUP:
                required_features.append(FeatureFlag.BACKUP_RESTORE)
            
            # Check if all required features are available
            missing_features = []
            for feature in required_features:
                if feature not in available_features:
                    missing_features.append(feature.value)
            
            if missing_features:
                return AccessResult(
                    granted=False,
                    reason=f"License tier does not support required features: {', '.join(missing_features)}",
                    restrictions=[f"Upgrade to access: {', '.join(missing_features)}"]
                )
            
            return AccessResult(granted=True, reason="Feature access granted")
            
        except Exception as e:
            logger.error(f"Error checking feature access: {e}")
            return AccessResult(granted=False, reason=f"Feature check error: {str(e)}")
    
    def _check_role_permissions(self, user: User, resource_type: ResourceType, access_level: AccessLevel) -> AccessResult:
        """Check role-based permissions"""
        try:
            # Get the highest access level from user's roles
            max_access_level = AccessLevel.NONE
            
            for role in user.roles:
                role_permissions = ROLE_RESOURCE_PERMISSIONS.get(role, {})
                role_access_level = role_permissions.get(resource_type, AccessLevel.NONE)
                
                # Compare access levels (higher is better)
                if self._compare_access_levels(role_access_level, max_access_level) > 0:
                    max_access_level = role_access_level
            
            # Check if user's access level is sufficient
            if self._compare_access_levels(max_access_level, access_level) >= 0:
                return AccessResult(
                    granted=True,
                    reason=f"Role-based access granted (level: {max_access_level.value})",
                    access_level=max_access_level
                )
            else:
                return AccessResult(
                    granted=False,
                    reason=f"Insufficient role permissions (required: {access_level.value}, available: {max_access_level.value})",
                    access_level=max_access_level,
                    restrictions=[f"Role with {access_level.value} access required"]
                )
            
        except Exception as e:
            logger.error(f"Error checking role permissions: {e}")
            return AccessResult(granted=False, reason=f"Role check error: {str(e)}")
    
    def _check_specific_permissions(self, user: User, resource_type: ResourceType, access_level: AccessLevel) -> AccessResult:
        """Check specific user permissions"""
        try:
            # Map resource types to required permissions
            permission_map = {
                (ResourceType.NETWORK, AccessLevel.READ): Permission.NETWORK_VIEW,
                (ResourceType.NETWORK, AccessLevel.WRITE): Permission.NETWORK_MODIFY,
                (ResourceType.NETWORK, AccessLevel.ADMIN): Permission.NETWORK_CREATE,
                (ResourceType.WORKER, AccessLevel.READ): Permission.WORKER_VIEW,
                (ResourceType.WORKER, AccessLevel.WRITE): Permission.WORKER_MANAGE,
                (ResourceType.MODEL, AccessLevel.READ): Permission.MODEL_VIEW,
                (ResourceType.MODEL, AccessLevel.WRITE): Permission.MODEL_UPLOAD,
                (ResourceType.MODEL, AccessLevel.ADMIN): Permission.MODEL_DELETE,
                (ResourceType.API_ENDPOINT, AccessLevel.EXECUTE): Permission.API_INFERENCE,
                (ResourceType.SYSTEM_CONFIG, AccessLevel.ADMIN): Permission.SYSTEM_ADMIN,
                (ResourceType.USER_DATA, AccessLevel.READ): Permission.USER_VIEW,
                (ResourceType.USER_DATA, AccessLevel.ADMIN): Permission.USER_MANAGE,
                (ResourceType.MONITORING, AccessLevel.READ): Permission.SYSTEM_MONITOR,
                (ResourceType.BACKUP, AccessLevel.EXECUTE): Permission.SYSTEM_BACKUP
            }
            
            # Get required permission
            required_permission = permission_map.get((resource_type, access_level))
            
            if not required_permission:
                # No specific permission required
                return AccessResult(granted=True, reason="No specific permission required")
            
            # Check if user has the required permission
            if required_permission in user.permissions:
                return AccessResult(
                    granted=True,
                    reason=f"Specific permission granted: {required_permission.value}"
                )
            else:
                return AccessResult(
                    granted=False,
                    reason=f"Missing required permission: {required_permission.value}",
                    restrictions=[f"Permission required: {required_permission.value}"]
                )
            
        except Exception as e:
            logger.error(f"Error checking specific permissions: {e}")
            return AccessResult(granted=False, reason=f"Permission check error: {str(e)}")
    
    def _check_resource_quotas(self, resource_type: ResourceType, access_level: AccessLevel) -> AccessResult:
        """Check resource quotas"""
        try:
            # Only check quotas for write/create operations
            if access_level not in [AccessLevel.WRITE, AccessLevel.ADMIN]:
                return AccessResult(granted=True, reason="Read access - no quota check needed")
            
            # Find relevant quota
            quota_name = None
            if resource_type == ResourceType.NETWORK:
                quota_name = "networks"
            elif resource_type == ResourceType.WORKER:
                quota_name = "workers"
            elif resource_type == ResourceType.MODEL:
                quota_name = "models"
            elif resource_type == ResourceType.API_ENDPOINT:
                quota_name = "api_calls"
            
            if not quota_name or quota_name not in self.resource_quotas:
                return AccessResult(granted=True, reason="No quota defined for resource type")
            
            quota = self.resource_quotas[quota_name]
            
            # Check if quota needs reset
            self._reset_quota_if_needed(quota)
            
            # Check if unlimited (-1)
            if quota.max_count == -1:
                return AccessResult(granted=True, reason="Unlimited quota")
            
            # Check if quota exceeded
            if quota.current_count >= quota.max_count:
                return AccessResult(
                    granted=False,
                    reason=f"Resource quota exceeded ({quota.current_count}/{quota.max_count})",
                    restrictions=[f"Quota limit reached for {resource_type.value}"]
                )
            
            return AccessResult(granted=True, reason="Quota check passed")
            
        except Exception as e:
            logger.error(f"Error checking resource quotas: {e}")
            return AccessResult(granted=False, reason=f"Quota check error: {str(e)}")
    
    def _reset_quota_if_needed(self, quota: ResourceQuota):
        """Reset quota if reset period has elapsed"""
        try:
            now = datetime.now()
            time_since_reset = now - quota.last_reset
            
            if time_since_reset.total_seconds() >= quota.reset_period_hours * 3600:
                quota.current_count = 0
                quota.current_size_mb = 0
                quota.last_reset = now
                self._save_quotas()
                logger.info(f"Reset quota for {quota.resource_type.value}")
        
        except Exception as e:
            logger.error(f"Error resetting quota: {e}")
    
    def _compare_access_levels(self, level1: AccessLevel, level2: AccessLevel) -> int:
        """Compare access levels (returns 1 if level1 > level2, 0 if equal, -1 if level1 < level2)"""
        level_order = {
            AccessLevel.NONE: 0,
            AccessLevel.READ: 1,
            AccessLevel.WRITE: 2,
            AccessLevel.EXECUTE: 3,
            AccessLevel.ADMIN: 4,
            AccessLevel.OWNER: 5
        }
        
        order1 = level_order.get(level1, 0)
        order2 = level_order.get(level2, 0)
        
        if order1 > order2:
            return 1
        elif order1 == order2:
            return 0
        else:
            return -1
    
    def _log_access_attempt(self, user: User, resource_type: ResourceType, 
                           resource_id: str, access_level: AccessLevel,
                           result: AccessResult, client_ip: Optional[str] = None,
                           user_agent: Optional[str] = None):
        """Log access attempt for audit purposes"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user.user_id,
                "username": user.username,
                "resource_type": resource_type.value,
                "resource_id": resource_id,
                "access_level": access_level.value,
                "granted": result.granted,
                "reason": result.reason,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "restrictions": result.restrictions
            }
            
            self.access_log.append(log_entry)
            
            # Trim log if too large
            if len(self.access_log) > self.max_log_entries:
                self.access_log = self.access_log[-self.max_log_entries:]
            
            # Log to file for important events
            if not result.granted or access_level in [AccessLevel.ADMIN, AccessLevel.OWNER]:
                if result.granted:
                    logger.info(f"Access granted: {user.username} -> {resource_type.value}:{resource_id} ({access_level.value})")
                else:
                    logger.warning(f"Access denied: {user.username} -> {resource_type.value}:{resource_id} ({access_level.value}) - {result.reason}")
        
        except Exception as e:
            logger.error(f"Error logging access attempt: {e}")
    
    def consume_quota(self, resource_type: ResourceType, count: int = 1, size_mb: int = 0) -> bool:
        """
        Consume resource quota
        
        Args:
            resource_type: Type of resource
            count: Number of resources to consume
            size_mb: Size in MB to consume
            
        Returns:
            True if quota consumed successfully, False if quota exceeded
        """
        try:
            # Find relevant quota
            quota_name = None
            if resource_type == ResourceType.NETWORK:
                quota_name = "networks"
            elif resource_type == ResourceType.WORKER:
                quota_name = "workers"
            elif resource_type == ResourceType.MODEL:
                quota_name = "models"
            elif resource_type == ResourceType.API_ENDPOINT:
                quota_name = "api_calls"
            
            if not quota_name or quota_name not in self.resource_quotas:
                return True  # No quota defined
            
            quota = self.resource_quotas[quota_name]
            
            # Check if quota needs reset
            self._reset_quota_if_needed(quota)
            
            # Check if unlimited
            if quota.max_count == -1:
                return True
            
            # Check if consumption would exceed quota
            if quota.current_count + count > quota.max_count:
                return False
            
            if quota.max_size_mb and quota.max_size_mb != -1:
                if quota.current_size_mb + size_mb > quota.max_size_mb:
                    return False
            
            # Consume quota
            quota.current_count += count
            quota.current_size_mb += size_mb
            
            # Save quotas
            self._save_quotas()
            
            logger.info(f"Consumed quota: {resource_type.value} +{count} (total: {quota.current_count}/{quota.max_count})")
            return True
            
        except Exception as e:
            logger.error(f"Error consuming quota: {e}")
            return False
    
    def release_quota(self, resource_type: ResourceType, count: int = 1, size_mb: int = 0) -> bool:
        """
        Release resource quota
        
        Args:
            resource_type: Type of resource
            count: Number of resources to release
            size_mb: Size in MB to release
            
        Returns:
            True if quota released successfully
        """
        try:
            # Find relevant quota
            quota_name = None
            if resource_type == ResourceType.NETWORK:
                quota_name = "networks"
            elif resource_type == ResourceType.WORKER:
                quota_name = "workers"
            elif resource_type == ResourceType.MODEL:
                quota_name = "models"
            elif resource_type == ResourceType.API_ENDPOINT:
                quota_name = "api_calls"
            
            if not quota_name or quota_name not in self.resource_quotas:
                return True  # No quota defined
            
            quota = self.resource_quotas[quota_name]
            
            # Release quota
            quota.current_count = max(0, quota.current_count - count)
            quota.current_size_mb = max(0, quota.current_size_mb - size_mb)
            
            # Save quotas
            self._save_quotas()
            
            logger.info(f"Released quota: {resource_type.value} -{count} (total: {quota.current_count}/{quota.max_count})")
            return True
            
        except Exception as e:
            logger.error(f"Error releasing quota: {e}")
            return False
    
    def has_feature(self, feature: FeatureFlag) -> bool:
        """
        Check if a feature is available based on license
        
        Args:
            feature: Feature to check
            
        Returns:
            True if feature is available
        """
        try:
            if not self.license_info:
                # No license - only basic features
                return feature in TIER_FEATURES.get(SubscriptionTier.FREE, set())
            
            available_features = TIER_FEATURES.get(self.license_info.plan, set())
            return feature in available_features
            
        except Exception as e:
            logger.error(f"Error checking feature availability: {e}")
            return False
    
    def get_available_features(self) -> Set[FeatureFlag]:
        """Get all available features based on license"""
        try:
            if not self.license_info:
                return TIER_FEATURES.get(SubscriptionTier.FREE, set())
            
            return TIER_FEATURES.get(self.license_info.plan, set())
            
        except Exception as e:
            logger.error(f"Error getting available features: {e}")
            return set()
    
    def get_resource_quotas(self) -> Dict[str, Dict[str, Any]]:
        """Get current resource quota status"""
        try:
            quotas_status = {}
            
            for quota_name, quota in self.resource_quotas.items():
                # Reset quota if needed
                self._reset_quota_if_needed(quota)
                
                quotas_status[quota_name] = {
                    "resource_type": quota.resource_type.value,
                    "max_count": quota.max_count,
                    "current_count": quota.current_count,
                    "max_size_mb": quota.max_size_mb,
                    "current_size_mb": quota.current_size_mb,
                    "usage_percentage": (quota.current_count / quota.max_count * 100) if quota.max_count > 0 else 0,
                    "reset_period_hours": quota.reset_period_hours,
                    "last_reset": quota.last_reset.isoformat(),
                    "next_reset": (quota.last_reset + timedelta(hours=quota.reset_period_hours)).isoformat()
                }
            
            return quotas_status
            
        except Exception as e:
            logger.error(f"Error getting resource quotas: {e}")
            return {}
    
    def get_access_log(self, limit: int = 100, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get access log entries
        
        Args:
            limit: Maximum number of entries to return
            user_id: Filter by specific user ID
            
        Returns:
            List of access log entries
        """
        try:
            log_entries = self.access_log
            
            # Filter by user if specified
            if user_id:
                log_entries = [entry for entry in log_entries if entry.get("user_id") == user_id]
            
            # Return most recent entries
            return log_entries[-limit:] if limit > 0 else log_entries
            
        except Exception as e:
            logger.error(f"Error getting access log: {e}")
            return []
    
    def clear_access_cache(self):
        """Clear the access cache"""
        self.access_cache.clear()
        logger.info("Access cache cleared")
    
    def get_user_access_summary(self, user: User) -> Dict[str, Any]:
        """
        Get access summary for a user
        
        Args:
            user: User object
            
        Returns:
            Dictionary with user's access summary
        """
        try:
            summary = {
                "user_id": user.user_id,
                "username": user.username,
                "roles": [role.value for role in user.roles],
                "permissions": [perm.value for perm in user.permissions],
                "is_active": user.is_active,
                "resource_access": {},
                "available_features": [feature.value for feature in self.get_available_features()],
                "license_tier": self.license_info.plan.value if self.license_info else "none"
            }
            
            # Check access to each resource type
            for resource_type in ResourceType:
                for access_level in AccessLevel:
                    if access_level == AccessLevel.NONE:
                        continue
                    
                    result = self.check_access(user, resource_type, "test", access_level)
                    
                    if resource_type.value not in summary["resource_access"]:
                        summary["resource_access"][resource_type.value] = {}
                    
                    summary["resource_access"][resource_type.value][access_level.value] = result.granted
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting user access summary: {e}")
            return {}


def create_access_control_manager(license_info: Optional[LicenseInfo] = None,
                                 auth_manager: Optional[AuthenticationManager] = None) -> AccessControlManager:
    """Create and initialize access control manager"""
    return AccessControlManager(license_info=license_info, auth_manager=auth_manager)


def main():
    """Main function for testing"""
    from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus
    
    # Create test license
    license_info = LicenseInfo(
        license_key="TIKT-PRO-12-ABC123",
        plan=SubscriptionTier.PRO,
        duration_months=12,
        unique_id="ABC123",
        expires_at=datetime.now() + timedelta(days=365),
        max_clients=20,
        allowed_models=["llama", "mistral"],
        allowed_features=["multi_network", "api_access", "monitoring"],
        status=LicenseStatus.VALID,
        hardware_signature="test_hw_sig",
        created_at=datetime.now(),
        checksum="test_checksum"
    )
    
    # Create access control manager
    access_manager = create_access_control_manager(license_info)
    
    # Create test user
    test_user = User(
        user_id="test_user",
        username="testuser",
        email="test@example.com",
        password_hash="hash",
        salt="salt",
        roles=[UserRole.DEVELOPER],
        permissions={Permission.NETWORK_VIEW, Permission.API_INFERENCE, Permission.MODEL_VIEW}
    )
    
    # Test access checks
    print("Testing access control...")
    
    # Test network read access
    result = access_manager.check_access(test_user, ResourceType.NETWORK, "network_1", AccessLevel.READ)
    print(f"Network read access: {result.granted} - {result.reason}")
    
    # Test network write access (should be denied for developer)
    result = access_manager.check_access(test_user, ResourceType.NETWORK, "network_1", AccessLevel.WRITE)
    print(f"Network write access: {result.granted} - {result.reason}")
    
    # Test API access
    result = access_manager.check_access(test_user, ResourceType.API_ENDPOINT, "inference", AccessLevel.EXECUTE)
    print(f"API access: {result.granted} - {result.reason}")
    
    # Test feature availability
    print(f"Multi-network feature available: {access_manager.has_feature(FeatureFlag.MULTI_NETWORK)}")
    print(f"Advanced monitoring available: {access_manager.has_feature(FeatureFlag.ADVANCED_MONITORING)}")
    
    # Test quota consumption
    print(f"Consume network quota: {access_manager.consume_quota(ResourceType.NETWORK, 1)}")
    print(f"Consume API quota: {access_manager.consume_quota(ResourceType.API_ENDPOINT, 10)}")
    
    # Get quota status
    quotas = access_manager.get_resource_quotas()
    print(f"Current quotas: {quotas}")
    
    # Get user access summary
    summary = access_manager.get_user_access_summary(test_user)
    print(f"User access summary: {summary}")


if __name__ == "__main__":
    main()