"""
Configuration Synchronization System for Distributed LLM Platform
Implements network-wide configuration updates, conflict resolution, and license compatibility validation
"""

import asyncio
import json
import logging
import hashlib
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import threading
from collections import defaultdict

from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus
from core.protocol_spec import ProtocolManager, MessageType, ErrorCode

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConfigSync")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/config_sync.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class ConfigChangeType(Enum):
    """Configuration change types"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MERGE = "merge"


class ConflictResolutionStrategy(Enum):
    """Conflict resolution strategies"""
    TIMESTAMP_WINS = "timestamp_wins"
    VERSION_WINS = "version_wins"
    MANUAL_RESOLUTION = "manual_resolution"
    CONSENSUS_VOTE = "consensus_vote"
    LICENSE_PRIORITY = "license_priority"


class ConfigScope(Enum):
    """Configuration scope levels"""
    GLOBAL = "global"
    NETWORK = "network"
    WORKER = "worker"
    USER = "user"


@dataclass
class ConfigurationItem:
    """Configuration item data structure"""
    key: str
    value: Any
    scope: ConfigScope
    version: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    author: str = "system"
    license_requirements: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    
    def __post_init__(self):
        """Calculate checksum after initialization"""
        if not self.checksum:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate configuration item checksum"""
        data = f"{self.key}:{json.dumps(self.value, sort_keys=True)}:{self.version}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class ConfigurationChange:
    """Configuration change record"""
    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    change_type: ConfigChangeType = ConfigChangeType.UPDATE
    config_item: ConfigurationItem = None
    old_value: Any = None
    new_value: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    node_id: str = ""
    license_hash: Optional[str] = None
    applied: bool = False
    conflicts: List[str] = field(default_factory=list)


@dataclass
class ConfigConflict:
    """Configuration conflict data structure"""
    conflict_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config_key: str = ""
    conflicting_changes: List[ConfigurationChange] = field(default_factory=list)
    resolution_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.TIMESTAMP_WINS
    resolved: bool = False
    resolution_result: Optional[ConfigurationItem] = None
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None


class ConfigurationSynchronizer:
    """
    Configuration synchronization system for distributed networks
    """
    
    def __init__(self, 
                 node_id: str,
                 license_info: Optional[LicenseInfo] = None,
                 protocol_manager: Optional[ProtocolManager] = None,
                 config_file: str = "network_config.json"):
        """
        Initialize configuration synchronizer
        
        Args:
            node_id: Unique node identifier
            license_info: License information for validation
            protocol_manager: Protocol manager for communication
            config_file: Configuration file path
        """
        self.node_id = node_id
        self.license_info = license_info
        self.protocol_manager = protocol_manager
        self.config_file = config_file
        
        # Configuration storage
        self.configurations: Dict[str, ConfigurationItem] = {}
        self.pending_changes: Dict[str, ConfigurationChange] = {}
        self.conflicts: Dict[str, ConfigConflict] = {}
        
        # Network nodes and their configurations
        self.network_nodes: Set[str] = set()
        self.node_configurations: Dict[str, Dict[str, ConfigurationItem]] = defaultdict(dict)
        
        # Synchronization state
        self.sync_active = False
        self.sync_thread = None
        self.last_sync_time = datetime.now()
        
        # Statistics
        self.sync_stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "conflicts_resolved": 0,
            "broadcasts_sent": 0,
            "updates_received": 0
        }
        
        # Load existing configuration
        self._load_configuration()
        
        logger.info(f"Configuration synchronizer initialized for node: {node_id}")
    
    def broadcast_config_updates(self, 
                                config_changes: List[ConfigurationChange],
                                target_nodes: Optional[List[str]] = None) -> bool:
        """
        Broadcast configuration updates function as specified in requirements
        
        Args:
            config_changes: List of configuration changes to broadcast
            target_nodes: Specific nodes to target (None for all nodes)
            
        Returns:
            True if broadcast was successful, False otherwise
        """
        try:
            logger.info(f"Broadcasting {len(config_changes)} configuration changes")
            
            # Validate license compatibility for changes
            for change in config_changes:
                if not self._validate_license_compatibility(change):
                    logger.warning(f"License incompatible change rejected: {change.config_item.key}")
                    return False
            
            # Prepare broadcast message
            broadcast_data = {
                "message_type": "config_update_broadcast",
                "sender_node": self.node_id,
                "timestamp": datetime.now().isoformat(),
                "changes": [asdict(change) for change in config_changes],
                "license_hash": self.license_info.checksum if self.license_info else None,
                "version": self._get_configuration_version()
            }
            
            # Determine target nodes
            targets = target_nodes if target_nodes else list(self.network_nodes)
            
            # Send to each target node
            successful_broadcasts = 0
            for target_node in targets:
                try:
                    if self._send_config_message(target_node, broadcast_data):
                        successful_broadcasts += 1
                except Exception as e:
                    logger.error(f"Failed to send config update to {target_node}: {e}")
            
            # Update statistics
            self.sync_stats["broadcasts_sent"] += 1
            
            # Store pending changes
            for change in config_changes:
                self.pending_changes[change.change_id] = change
            
            success = successful_broadcasts > 0
            if success:
                logger.info(f"Configuration broadcast sent to {successful_broadcasts}/{len(targets)} nodes")
            else:
                logger.error("Configuration broadcast failed to all nodes")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to broadcast configuration updates: {e}")
            return False
    
    def handle_config_conflicts(self, 
                               conflicts: List[ConfigConflict],
                               strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.CONSENSUS_VOTE) -> List[ConfigConflict]:
        """
        Handle configuration conflicts function as specified in requirements
        
        Args:
            conflicts: List of configuration conflicts to resolve
            strategy: Conflict resolution strategy to use
            
        Returns:
            List of resolved conflicts
        """
        try:
            logger.info(f"Handling {len(conflicts)} configuration conflicts with strategy: {strategy.value}")
            
            resolved_conflicts = []
            
            for conflict in conflicts:
                try:
                    resolved_conflict = self._resolve_single_conflict(conflict, strategy)
                    if resolved_conflict.resolved:
                        resolved_conflicts.append(resolved_conflict)
                        
                        # Apply resolved configuration
                        if resolved_conflict.resolution_result:
                            self._apply_configuration_change(resolved_conflict.resolution_result)
                        
                        # Update statistics
                        self.sync_stats["conflicts_resolved"] += 1
                        
                        logger.info(f"Conflict resolved for key: {conflict.config_key}")
                    else:
                        logger.warning(f"Failed to resolve conflict for key: {conflict.config_key}")
                        
                except Exception as e:
                    logger.error(f"Error resolving conflict {conflict.conflict_id}: {e}")
            
            # Store resolved conflicts
            for conflict in resolved_conflicts:
                self.conflicts[conflict.conflict_id] = conflict
            
            logger.info(f"Resolved {len(resolved_conflicts)}/{len(conflicts)} conflicts")
            return resolved_conflicts
            
        except Exception as e:
            logger.error(f"Failed to handle configuration conflicts: {e}")
            return []
    
    def _resolve_single_conflict(self, 
                                conflict: ConfigConflict, 
                                strategy: ConflictResolutionStrategy) -> ConfigConflict:
        """Resolve a single configuration conflict"""
        try:
            if strategy == ConflictResolutionStrategy.TIMESTAMP_WINS:
                # Choose the most recent change
                latest_change = max(conflict.conflicting_changes, key=lambda c: c.timestamp)
                conflict.resolution_result = latest_change.config_item
                
            elif strategy == ConflictResolutionStrategy.VERSION_WINS:
                # Choose the highest version
                highest_version_change = max(conflict.conflicting_changes, 
                                           key=lambda c: c.config_item.version)
                conflict.resolution_result = highest_version_change.config_item
                
            elif strategy == ConflictResolutionStrategy.LICENSE_PRIORITY:
                # Prioritize based on license tier
                prioritized_change = self._prioritize_by_license(conflict.conflicting_changes)
                conflict.resolution_result = prioritized_change.config_item if prioritized_change else None
                
            elif strategy == ConflictResolutionStrategy.CONSENSUS_VOTE:
                # Use consensus algorithm
                consensus_result = self._consensus_resolution(conflict.conflicting_changes)
                conflict.resolution_result = consensus_result
                
            else:  # MANUAL_RESOLUTION
                # Mark for manual resolution
                conflict.resolution_result = None
                logger.info(f"Conflict {conflict.conflict_id} marked for manual resolution")
            
            if conflict.resolution_result:
                conflict.resolved = True
                conflict.resolved_at = datetime.now()
            
            return conflict
            
        except Exception as e:
            logger.error(f"Error in single conflict resolution: {e}")
            return conflict
    
    def _prioritize_by_license(self, changes: List[ConfigurationChange]) -> Optional[ConfigurationChange]:
        """Prioritize configuration changes by license tier"""
        try:
            # Define license tier priority (higher number = higher priority)
            tier_priority = {
                SubscriptionTier.FREE: 1,
                SubscriptionTier.PRO: 2,
                SubscriptionTier.ENT: 3
            }
            
            # Get license tier for each change
            prioritized_changes = []
            for change in changes:
                if change.license_hash and self.license_info:
                    # In a real implementation, you'd look up the license info by hash
                    # For now, use current license info
                    priority = tier_priority.get(self.license_info.plan, 0)
                    prioritized_changes.append((change, priority))
                else:
                    prioritized_changes.append((change, 0))
            
            # Sort by priority (highest first)
            prioritized_changes.sort(key=lambda x: x[1], reverse=True)
            
            return prioritized_changes[0][0] if prioritized_changes else None
            
        except Exception as e:
            logger.error(f"Error in license prioritization: {e}")
            return None
    
    def _consensus_resolution(self, changes: List[ConfigurationChange]) -> Optional[ConfigurationItem]:
        """Resolve conflict using consensus algorithm"""
        try:
            # Simple majority consensus based on node votes
            # In a real implementation, this would involve network communication
            
            # Group changes by value
            value_votes = defaultdict(list)
            for change in changes:
                value_key = json.dumps(change.config_item.value, sort_keys=True)
                value_votes[value_key].append(change)
            
            # Find the value with most votes
            if value_votes:
                winning_value = max(value_votes.keys(), key=lambda k: len(value_votes[k]))
                winning_changes = value_votes[winning_value]
                
                # Return the most recent change with the winning value
                return max(winning_changes, key=lambda c: c.timestamp).config_item
            
            return None
            
        except Exception as e:
            logger.error(f"Error in consensus resolution: {e}")
            return None
    
    def _validate_license_compatibility(self, change: ConfigurationChange) -> bool:
        """Validate license compatibility for configuration changes"""
        try:
            if not change.config_item.license_requirements:
                return True  # No license requirements
            
            if not self.license_info:
                logger.warning("No license info available for validation")
                return False
            
            # Check if current license supports required features
            for requirement in change.config_item.license_requirements:
                if requirement not in self.license_info.allowed_features:
                    logger.warning(f"License does not support required feature: {requirement}")
                    return False
            
            # Check subscription tier requirements
            if change.config_item.scope == ConfigScope.GLOBAL:
                # Global changes might require higher tier
                if self.license_info.plan == SubscriptionTier.FREE:
                    logger.warning("Global configuration changes require PRO or ENT license")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating license compatibility: {e}")
            return False
    
    def _send_config_message(self, target_node: str, message_data: Dict[str, Any]) -> bool:
        """Send configuration message to target node"""
        try:
            # In a real implementation, this would use the protocol manager
            # to send messages over the network
            
            if self.protocol_manager:
                # Create protocol message
                message_json = json.dumps(message_data)
                # Send via protocol manager (implementation would depend on transport)
                logger.debug(f"Sending config message to {target_node}: {len(message_json)} bytes")
                return True
            else:
                # Simulate message sending
                logger.debug(f"Simulated config message sent to {target_node}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to send config message to {target_node}: {e}")
            return False
    
    def _apply_configuration_change(self, config_item: ConfigurationItem):
        """Apply a configuration change locally"""
        try:
            # Store configuration
            self.configurations[config_item.key] = config_item
            
            # Save to file
            self._save_configuration()
            
            logger.info(f"Applied configuration change: {config_item.key}")
            
        except Exception as e:
            logger.error(f"Failed to apply configuration change: {e}")
    
    def _load_configuration(self):
        """Load configuration from file"""
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                # Convert to ConfigurationItem objects
                for key, item_data in config_data.items():
                    if isinstance(item_data, dict) and 'key' in item_data:
                        config_item = ConfigurationItem(
                            key=item_data['key'],
                            value=item_data['value'],
                            scope=ConfigScope(item_data.get('scope', 'network')),
                            version=item_data.get('version', 1),
                            timestamp=datetime.fromisoformat(item_data.get('timestamp', datetime.now().isoformat())),
                            author=item_data.get('author', 'system'),
                            license_requirements=item_data.get('license_requirements', []),
                            metadata=item_data.get('metadata', {}),
                            checksum=item_data.get('checksum', '')
                        )
                        self.configurations[key] = config_item
                
                logger.info(f"Loaded {len(self.configurations)} configuration items")
            else:
                logger.info("No existing configuration file found, starting with empty configuration")
                
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
    
    def _save_configuration(self):
        """Save configuration to file"""
        try:
            config_data = {}
            for key, config_item in self.configurations.items():
                config_data[key] = asdict(config_item)
                # Convert datetime to string
                config_data[key]['timestamp'] = config_item.timestamp.isoformat()
                config_data[key]['scope'] = config_item.scope.value
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            
            logger.debug(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
    
    def _get_configuration_version(self) -> str:
        """Get current configuration version"""
        try:
            # Create version hash based on all configuration checksums
            checksums = [item.checksum for item in self.configurations.values()]
            checksums.sort()
            version_data = ''.join(checksums)
            return hashlib.sha256(version_data.encode()).hexdigest()[:16]
        except Exception as e:
            logger.error(f"Failed to get configuration version: {e}")
            return "unknown"   
    def create_configuration_change(self,
                                  key: str,
                                  new_value: Any,
                                  change_type: ConfigChangeType = ConfigChangeType.UPDATE,
                                  scope: ConfigScope = ConfigScope.NETWORK,
                                  license_requirements: List[str] = None) -> ConfigurationChange:
        """Create a new configuration change"""
        try:
            # Get existing configuration item
            old_config = self.configurations.get(key)
            old_value = old_config.value if old_config else None
            
            # Create new configuration item
            new_config = ConfigurationItem(
                key=key,
                value=new_value,
                scope=scope,
                version=(old_config.version + 1) if old_config else 1,
                timestamp=datetime.now(),
                author=self.node_id,
                license_requirements=license_requirements or [],
                metadata={"node_id": self.node_id}
            )
            
            # Create configuration change
            change = ConfigurationChange(
                change_type=change_type,
                config_item=new_config,
                old_value=old_value,
                new_value=new_value,
                timestamp=datetime.now(),
                node_id=self.node_id,
                license_hash=self.license_info.checksum if self.license_info else None
            )
            
            return change
            
        except Exception as e:
            logger.error(f"Failed to create configuration change: {e}")
            raise
    
    def update_configuration(self,
                           key: str,
                           value: Any,
                           broadcast: bool = True,
                           scope: ConfigScope = ConfigScope.NETWORK) -> bool:
        """Update a configuration value"""
        try:
            # Create configuration change
            change = self.create_configuration_change(
                key=key,
                new_value=value,
                change_type=ConfigChangeType.UPDATE,
                scope=scope
            )
            
            # Validate license compatibility
            if not self._validate_license_compatibility(change):
                logger.error(f"License incompatible configuration update rejected: {key}")
                return False
            
            # Apply locally
            self._apply_configuration_change(change.config_item)
            
            # Broadcast to network if requested
            if broadcast:
                return self.broadcast_config_updates([change])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update configuration {key}: {e}")
            return False
    
    def get_configuration(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        try:
            config_item = self.configurations.get(key)
            return config_item.value if config_item else default
        except Exception as e:
            logger.error(f"Failed to get configuration {key}: {e}")
            return default
    
    def delete_configuration(self, key: str, broadcast: bool = True) -> bool:
        """Delete a configuration item"""
        try:
            if key not in self.configurations:
                logger.warning(f"Configuration key not found: {key}")
                return False
            
            # Create delete change
            change = ConfigurationChange(
                change_type=ConfigChangeType.DELETE,
                config_item=self.configurations[key],
                old_value=self.configurations[key].value,
                new_value=None,
                timestamp=datetime.now(),
                node_id=self.node_id,
                license_hash=self.license_info.checksum if self.license_info else None
            )
            
            # Remove locally
            del self.configurations[key]
            self._save_configuration()
            
            # Broadcast to network if requested
            if broadcast:
                return self.broadcast_config_updates([change])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete configuration {key}: {e}")
            return False
    
    def handle_incoming_config_update(self, message_data: Dict[str, Any]) -> bool:
        """Handle incoming configuration update from another node"""
        try:
            sender_node = message_data.get('sender_node')
            changes_data = message_data.get('changes', [])
            
            logger.info(f"Received config update from {sender_node} with {len(changes_data)} changes")
            
            # Convert to ConfigurationChange objects
            incoming_changes = []
            for change_data in changes_data:
                try:
                    # Reconstruct ConfigurationItem
                    config_item_data = change_data['config_item']
                    config_item = ConfigurationItem(
                        key=config_item_data['key'],
                        value=config_item_data['value'],
                        scope=ConfigScope(config_item_data['scope']),
                        version=config_item_data['version'],
                        timestamp=datetime.fromisoformat(config_item_data['timestamp']),
                        author=config_item_data['author'],
                        license_requirements=config_item_data.get('license_requirements', []),
                        metadata=config_item_data.get('metadata', {}),
                        checksum=config_item_data.get('checksum', '')
                    )
                    
                    # Reconstruct ConfigurationChange
                    change = ConfigurationChange(
                        change_id=change_data['change_id'],
                        change_type=ConfigChangeType(change_data['change_type']),
                        config_item=config_item,
                        old_value=change_data.get('old_value'),
                        new_value=change_data.get('new_value'),
                        timestamp=datetime.fromisoformat(change_data['timestamp']),
                        node_id=change_data['node_id'],
                        license_hash=change_data.get('license_hash')
                    )
                    
                    incoming_changes.append(change)
                    
                except Exception as e:
                    logger.error(f"Failed to parse incoming change: {e}")
                    continue
            
            # Process changes and detect conflicts
            conflicts = []
            applied_changes = []
            
            for change in incoming_changes:
                existing_config = self.configurations.get(change.config_item.key)
                
                if existing_config and existing_config.version >= change.config_item.version:
                    # Potential conflict
                    if existing_config.checksum != change.config_item.checksum:
                        conflict = ConfigConflict(
                            config_key=change.config_item.key,
                            conflicting_changes=[
                                ConfigurationChange(
                                    config_item=existing_config,
                                    change_type=ConfigChangeType.UPDATE,
                                    timestamp=existing_config.timestamp,
                                    node_id=self.node_id
                                ),
                                change
                            ]
                        )
                        conflicts.append(conflict)
                    else:
                        # Same configuration, no conflict
                        logger.debug(f"Received duplicate configuration: {change.config_item.key}")
                else:
                    # No conflict, apply change
                    if self._validate_license_compatibility(change):
                        self._apply_configuration_change(change.config_item)
                        applied_changes.append(change)
                    else:
                        logger.warning(f"License incompatible change rejected: {change.config_item.key}")
            
            # Handle conflicts if any
            if conflicts:
                resolved_conflicts = self.handle_config_conflicts(conflicts)
                logger.info(f"Resolved {len(resolved_conflicts)} conflicts")
            
            # Update statistics
            self.sync_stats["updates_received"] += 1
            
            logger.info(f"Applied {len(applied_changes)} configuration changes, resolved {len(conflicts)} conflicts")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle incoming config update: {e}")
            return False
    
    def start_sync_monitoring(self, sync_interval: int = 60):
        """Start continuous configuration synchronization monitoring"""
        try:
            if self.sync_active:
                logger.warning("Configuration sync monitoring is already active")
                return
            
            self.sync_active = True
            self.sync_thread = threading.Thread(target=self._sync_monitor_loop, args=(sync_interval,), daemon=True)
            self.sync_thread.start()
            
            logger.info(f"Configuration sync monitoring started with {sync_interval}s interval")
            
        except Exception as e:
            logger.error(f"Failed to start sync monitoring: {e}")
    
    def stop_sync_monitoring(self):
        """Stop configuration synchronization monitoring"""
        try:
            self.sync_active = False
            
            if self.sync_thread:
                self.sync_thread.join(timeout=5)
            
            logger.info("Configuration sync monitoring stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop sync monitoring: {e}")
    
    def _sync_monitor_loop(self, sync_interval: int):
        """Configuration synchronization monitoring loop"""
        while self.sync_active:
            try:
                # Check for pending changes that need to be retried
                retry_changes = []
                for change_id, change in list(self.pending_changes.items()):
                    if not change.applied and (datetime.now() - change.timestamp).seconds > 300:  # 5 minutes
                        retry_changes.append(change)
                        del self.pending_changes[change_id]
                
                if retry_changes:
                    logger.info(f"Retrying {len(retry_changes)} pending configuration changes")
                    self.broadcast_config_updates(retry_changes)
                
                # Update last sync time
                self.last_sync_time = datetime.now()
                
                time.sleep(sync_interval)
                
            except Exception as e:
                logger.error(f"Error in sync monitoring loop: {e}")
                time.sleep(sync_interval)
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get configuration synchronization status"""
        try:
            return {
                "node_id": self.node_id,
                "sync_active": self.sync_active,
                "last_sync_time": self.last_sync_time.isoformat(),
                "configuration_count": len(self.configurations),
                "pending_changes": len(self.pending_changes),
                "unresolved_conflicts": len([c for c in self.conflicts.values() if not c.resolved]),
                "network_nodes": len(self.network_nodes),
                "configuration_version": self._get_configuration_version(),
                "statistics": self.sync_stats.copy()
            }
        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            return {"error": str(e)}
    
    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration"""
        try:
            exported_config = {}
            for key, config_item in self.configurations.items():
                exported_config[key] = {
                    "value": config_item.value,
                    "scope": config_item.scope.value,
                    "version": config_item.version,
                    "timestamp": config_item.timestamp.isoformat(),
                    "author": config_item.author,
                    "license_requirements": config_item.license_requirements,
                    "metadata": config_item.metadata,
                    "checksum": config_item.checksum
                }
            
            return {
                "node_id": self.node_id,
                "export_timestamp": datetime.now().isoformat(),
                "configuration_version": self._get_configuration_version(),
                "configurations": exported_config
            }
            
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            return {"error": str(e)}


def create_config_synchronizer(node_id: str, 
                             license_info: Optional[LicenseInfo] = None) -> ConfigurationSynchronizer:
    """Create and initialize configuration synchronizer"""
    return ConfigurationSynchronizer(node_id=node_id, license_info=license_info)


def main():
    """Main function for testing configuration synchronization"""
    print("=== Testing Configuration Synchronization ===\n")
    
    # Create test license
    from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus
    
    license_info = LicenseInfo(
        license_key="TIKT-PRO-12-CONFIG",
        plan=SubscriptionTier.PRO,
        duration_months=12,
        unique_id="CONFIG",
        expires_at=datetime.now() + timedelta(days=365),
        max_clients=20,
        allowed_models=["llama", "mistral"],
        allowed_features=["multi_network", "config_sync"],
        status=LicenseStatus.VALID,
        hardware_signature="config_hw",
        created_at=datetime.now(),
        checksum="config_checksum"
    )
    
    # Create configuration synchronizers for two nodes
    node1 = create_config_synchronizer("node-001", license_info)
    node2 = create_config_synchronizer("node-002", license_info)
    
    # Test 1: Basic configuration operations
    print("1. Testing Basic Configuration Operations")
    
    # Update configuration on node1
    success = node1.update_configuration("model_timeout", 30, broadcast=False)
    print(f"✓ Configuration updated on node1: {success}")
    
    # Get configuration value
    timeout_value = node1.get_configuration("model_timeout", 0)
    print(f"✓ Retrieved configuration value: {timeout_value}")
    
    print()
    
    # Test 2: Configuration broadcasting
    print("2. Testing Configuration Broadcasting")
    
    # Add node2 to node1's network
    node1.network_nodes.add("node-002")
    
    # Create configuration change
    change = node1.create_configuration_change(
        key="max_workers",
        new_value=10,
        scope=ConfigScope.GLOBAL,
        license_requirements=["multi_network"]
    )
    
    # Broadcast configuration update
    broadcast_success = node1.broadcast_config_updates([change])
    print(f"✓ Configuration broadcast: {broadcast_success}")
    
    print()
    
    # Test 3: Conflict resolution
    print("3. Testing Conflict Resolution")
    
    # Create conflicting changes
    change1 = node1.create_configuration_change("worker_memory", 8192)
    change2 = node2.create_configuration_change("worker_memory", 16384)
    
    # Create conflict
    conflict = ConfigConflict(
        config_key="worker_memory",
        conflicting_changes=[change1, change2],
        resolution_strategy=ConflictResolutionStrategy.TIMESTAMP_WINS
    )
    
    # Resolve conflicts
    resolved = node1.handle_config_conflicts([conflict])
    print(f"✓ Conflicts resolved: {len(resolved)}")
    
    if resolved:
        result_value = resolved[0].resolution_result.value if resolved[0].resolution_result else None
        print(f"  Resolution result: {result_value}")
    
    print()
    
    # Test 4: License compatibility validation
    print("4. Testing License Compatibility")
    
    # Test valid configuration (within license)
    valid_change = node1.create_configuration_change(
        key="network_discovery",
        new_value=True,
        license_requirements=["multi_network"]
    )
    
    valid = node1._validate_license_compatibility(valid_change)
    print(f"✓ Valid license compatibility: {valid}")
    
    # Test invalid configuration (outside license)
    invalid_change = node1.create_configuration_change(
        key="enterprise_feature",
        new_value=True,
        license_requirements=["enterprise_only"]
    )
    
    invalid = node1._validate_license_compatibility(invalid_change)
    print(f"✓ Invalid license compatibility correctly rejected: {not invalid}")
    
    print()
    
    # Test 5: Configuration synchronization status
    print("5. Testing Synchronization Status")
    
    status = node1.get_sync_status()
    print(f"✓ Sync status retrieved:")
    print(f"  Node ID: {status['node_id']}")
    print(f"  Configuration count: {status['configuration_count']}")
    print(f"  Configuration version: {status['configuration_version']}")
    print(f"  Statistics: {status['statistics']}")
    
    print()
    
    # Test 6: Configuration export
    print("6. Testing Configuration Export")
    
    exported = node1.export_configuration()
    if "error" not in exported:
        print("✓ Configuration exported successfully")
        print(f"  Exported {len(exported['configurations'])} configuration items")
        print(f"  Export timestamp: {exported['export_timestamp']}")
    else:
        print(f"✗ Configuration export failed: {exported['error']}")
    
    print("\n=== Configuration Synchronization Tests Completed ===")


if __name__ == "__main__":
    main()