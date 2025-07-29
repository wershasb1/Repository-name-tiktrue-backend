"""
TikTrue Platform Configuration Management System

This module provides centralized configuration management with JSON schema validation,
dynamic path resolution, and support for development, production, and portable modes.

Requirements addressed:
- 12.1: JSON-based configuration files
- 12.2: Dynamic path resolution
- 12.3: Development, production, and portable mode support
- 12.5: Configuration schema validation
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime

# Configuration for structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentMode(Enum):
    """Deployment mode enumeration"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    PORTABLE = "portable"


@dataclass
class NetworkConfig:
    """Network configuration structure"""
    network_id: str
    network_name: str
    admin_node_id: str
    max_clients: int
    allowed_models: List[str]
    encryption_enabled: bool
    discovery_port: int
    communication_port: int


@dataclass
class PathConfig:
    """Path configuration for different deployment modes"""
    models_dir: str
    logs_dir: str
    sessions_dir: str
    data_dir: str
    config_dir: str
    temp_dir: str


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    encryption_key_rotation_days: int
    max_login_attempts: int
    session_timeout_minutes: int
    hardware_fingerprint_enabled: bool
    audit_logging_enabled: bool


@dataclass
class SystemConfig:
    """Main system configuration"""
    deployment_mode: str
    paths: PathConfig
    network: NetworkConfig
    security: SecurityConfig
    version: str
    created_at: str


class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass


class ConfigManager:
    """
    Centralized configuration management system with JSON schema validation
    and dynamic path resolution for different deployment modes.
    """
    
    # Configuration schema for validation
    CONFIG_SCHEMA = {
        "type": "object",
        "required": ["deployment_mode", "paths", "network", "security", "version"],
        "properties": {
            "deployment_mode": {
                "type": "string",
                "enum": ["development", "production", "portable"]
            },
            "paths": {
                "type": "object",
                "required": ["models_dir", "logs_dir", "sessions_dir", "data_dir", "config_dir", "temp_dir"],
                "properties": {
                    "models_dir": {"type": "string"},
                    "logs_dir": {"type": "string"},
                    "sessions_dir": {"type": "string"},
                    "data_dir": {"type": "string"},
                    "config_dir": {"type": "string"},
                    "temp_dir": {"type": "string"}
                }
            },
            "network": {
                "type": "object",
                "required": ["network_id", "network_name", "admin_node_id", "max_clients", 
                           "allowed_models", "encryption_enabled", "discovery_port", "communication_port"],
                "properties": {
                    "network_id": {"type": "string"},
                    "network_name": {"type": "string"},
                    "admin_node_id": {"type": "string"},
                    "max_clients": {"type": "integer", "minimum": 1, "maximum": 100},
                    "allowed_models": {"type": "array", "items": {"type": "string"}},
                    "encryption_enabled": {"type": "boolean"},
                    "discovery_port": {"type": "integer", "minimum": 1024, "maximum": 65535},
                    "communication_port": {"type": "integer", "minimum": 1024, "maximum": 65535}
                }
            },
            "security": {
                "type": "object",
                "required": ["encryption_key_rotation_days", "max_login_attempts", 
                           "session_timeout_minutes", "hardware_fingerprint_enabled", "audit_logging_enabled"],
                "properties": {
                    "encryption_key_rotation_days": {"type": "integer", "minimum": 1, "maximum": 365},
                    "max_login_attempts": {"type": "integer", "minimum": 1, "maximum": 10},
                    "session_timeout_minutes": {"type": "integer", "minimum": 5, "maximum": 1440},
                    "hardware_fingerprint_enabled": {"type": "boolean"},
                    "audit_logging_enabled": {"type": "boolean"}
                }
            },
            "version": {"type": "string"}
        }
    }
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager
        
        Args:
            config_file: Optional path to configuration file
        """
        self._config: Optional[SystemConfig] = None
        self._config_file = config_file or self._detect_config_file()
        self._deployment_mode = self._detect_deployment_mode()
        
        # Add project_root attribute
        from pathlib import Path
        self.project_root = str(Path(__file__).parent.resolve())
        
        logger.info(f"ConfigManager initialized with mode: {self._deployment_mode}")
    
    def _detect_deployment_mode(self) -> DeploymentMode:
        """Detect deployment mode based on environment and file system"""
        # Check environment variable first
        env_mode = os.getenv('TIKTRUE_DEPLOYMENT_MODE')
        if env_mode:
            try:
                return DeploymentMode(env_mode.lower())
            except ValueError:
                logger.warning(f"Invalid deployment mode in environment: {env_mode}")
        
        # Check if running from executable (production/portable)
        if getattr(sys, 'frozen', False):
            # Check if portable config exists
            portable_config = Path(sys.executable).parent / "portable_config.json"
            if portable_config.exists():
                return DeploymentMode.PORTABLE
            return DeploymentMode.PRODUCTION
        
        # Default to development mode
        return DeploymentMode.DEVELOPMENT
    
    def _detect_config_file(self) -> str:
        """Detect appropriate configuration file based on deployment mode"""
        mode = self._detect_deployment_mode()
        
        if mode == DeploymentMode.PORTABLE:
            # Portable mode: config next to executable
            if getattr(sys, 'frozen', False):
                return str(Path(sys.executable).parent / "portable_config.json")
            return "portable_config.json"
        
        elif mode == DeploymentMode.PRODUCTION:
            # Production mode: system-wide config
            return "network_config.json"
        
        else:
            # Development mode: local config
            return "network_config.json"
    
    def _get_default_paths(self, mode: DeploymentMode) -> PathConfig:
        """Generate default paths based on deployment mode"""
        if mode == DeploymentMode.PORTABLE:
            # Portable mode: all paths relative to executable
            base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path.cwd()
            return PathConfig(
                models_dir=str(base_dir / "assets" / "models"),
                logs_dir=str(base_dir / "logs"),
                sessions_dir=str(base_dir / "sessions"),
                data_dir=str(base_dir / "data"),
                config_dir=str(base_dir),
                temp_dir=str(base_dir / "temp")
            )
        
        elif mode == DeploymentMode.PRODUCTION:
            # Production mode: system-wide paths
            app_data = Path(os.getenv('APPDATA', '')) / "TikTrue" if os.name == 'nt' else Path.home() / ".tiktrue"
            return PathConfig(
                models_dir=str(app_data / "models"),
                logs_dir=str(app_data / "logs"),
                sessions_dir=str(app_data / "sessions"),
                data_dir=str(app_data / "data"),
                config_dir=str(app_data / "config"),
                temp_dir=str(app_data / "temp")
            )
        
        else:
            # Development mode: local relative paths
            return PathConfig(
                models_dir="assets/models",
                logs_dir="logs",
                sessions_dir="sessions",
                data_dir="data",
                config_dir=".",
                temp_dir="temp"
            )
    
    def _create_default_config(self) -> SystemConfig:
        """Create default configuration for current deployment mode"""
        paths = self._get_default_paths(self._deployment_mode)
        
        network = NetworkConfig(
            network_id="default_network",
            network_name="TikTrue Network",
            admin_node_id="admin_node_1",
            max_clients=10,
            allowed_models=["llama3_1_8b_fp16", "mistral_7b_int4"],
            encryption_enabled=True,
            discovery_port=8765,
            communication_port=8766
        )
        
        security = SecurityConfig(
            encryption_key_rotation_days=30,
            max_login_attempts=3,
            session_timeout_minutes=60,
            hardware_fingerprint_enabled=True,
            audit_logging_enabled=True
        )
        
        return SystemConfig(
            deployment_mode=self._deployment_mode.value,
            paths=paths,
            network=network,
            security=security,
            version="1.0.0",
            created_at=datetime.now().isoformat()
        )
    
    def _validate_config_schema(self, config_data: Dict[str, Any]) -> bool:
        """
        Validate configuration against schema
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            True if valid, raises ConfigurationError if invalid
        """
        try:
            # Basic type checking (simplified schema validation)
            required_keys = ["deployment_mode", "paths", "network", "security", "version"]
            for key in required_keys:
                if key not in config_data:
                    raise ConfigurationError(f"Missing required configuration key: {key}")
            
            # Validate deployment mode
            if config_data["deployment_mode"] not in ["development", "production", "portable"]:
                raise ConfigurationError(f"Invalid deployment mode: {config_data['deployment_mode']}")
            
            # Validate network ports
            network = config_data.get("network", {})
            for port_key in ["discovery_port", "communication_port"]:
                port = network.get(port_key, 0)
                if not isinstance(port, int) or port < 1024 or port > 65535:
                    raise ConfigurationError(f"Invalid {port_key}: {port}")
            
            # Validate max_clients
            max_clients = network.get("max_clients", 0)
            if not isinstance(max_clients, int) or max_clients < 1 or max_clients > 100:
                raise ConfigurationError(f"Invalid max_clients: {max_clients}")
            
            logger.info("Configuration schema validation passed")
            return True
            
        except Exception as e:
            raise ConfigurationError(f"Configuration validation failed: {str(e)}")
    
    def load_config(self) -> SystemConfig:
        """
        Load configuration from file or create default
        
        Returns:
            SystemConfig object
        """
        try:
            config_path = Path(self._config_file)
            
            if config_path.exists():
                logger.info(f"Loading configuration from: {config_path}")
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Validate configuration
                self._validate_config_schema(config_data)
                
                # Convert to SystemConfig object
                paths = PathConfig(**config_data["paths"])
                network = NetworkConfig(**config_data["network"])
                security = SecurityConfig(**config_data["security"])
                
                self._config = SystemConfig(
                    deployment_mode=config_data["deployment_mode"],
                    paths=paths,
                    network=network,
                    security=security,
                    version=config_data["version"],
                    created_at=config_data.get("created_at", datetime.now().isoformat())
                )
                
                logger.info("Configuration loaded successfully")
                
            else:
                logger.info("Configuration file not found, creating default configuration")
                self._config = self._create_default_config()
                self.save_config()
            
            # Ensure directories exist
            self._ensure_directories()
            
            return self._config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise ConfigurationError(f"Configuration loading failed: {str(e)}")
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        if not self._config:
            raise ConfigurationError("No configuration to save")
        
        try:
            config_path = Path(self._config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dictionary for JSON serialization
            config_dict = asdict(self._config)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration saved to: {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            raise ConfigurationError(f"Configuration saving failed: {str(e)}")
    
    def _ensure_directories(self) -> None:
        """Ensure all configured directories exist"""
        if not self._config:
            return
        
        paths_to_create = [
            self._config.paths.models_dir,
            self._config.paths.logs_dir,
            self._config.paths.sessions_dir,
            self._config.paths.data_dir,
            self._config.paths.config_dir,
            self._config.paths.temp_dir
        ]
        
        for path_str in paths_to_create:
            try:
                path = Path(path_str)
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {path}")
            except Exception as e:
                logger.warning(f"Failed to create directory {path_str}: {str(e)}")
    
    def get_config(self) -> SystemConfig:
        """Get current configuration, loading if necessary"""
        if not self._config:
            return self.load_config()
        return self._config
    
    def update_config(self, **kwargs) -> None:
        """
        Update configuration values
        
        Args:
            **kwargs: Configuration values to update
        """
        if not self._config:
            self.load_config()
        
        # Update configuration fields
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
                logger.info(f"Updated configuration: {key} = {value}")
            else:
                logger.warning(f"Unknown configuration key: {key}")
        
        # Save updated configuration
        self.save_config()
    
    def resolve_path(self, relative_path: str) -> str:
        """
        Resolve relative path based on current deployment mode
        
        Args:
            relative_path: Relative path to resolve
            
        Returns:
            Absolute path string
        """
        if not self._config:
            self.load_config()
        
        # If already absolute, return as-is
        path = Path(relative_path)
        if path.is_absolute():
            return str(path)
        
        # Resolve relative to appropriate base directory
        if self._deployment_mode == DeploymentMode.PORTABLE:
            base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path.cwd()
        elif self._deployment_mode == DeploymentMode.PRODUCTION:
            base_dir = Path(self._config.paths.config_dir)
        else:
            base_dir = Path.cwd()
        
        resolved_path = base_dir / relative_path
        return str(resolved_path.resolve())
    
    def get_model_path(self, model_name: str) -> str:
        """Get full path to model directory"""
        if not self._config:
            self.load_config()
        
        model_path = Path(self._config.paths.models_dir) / model_name
        return str(model_path)
    
    def get_log_path(self, log_name: str) -> str:
        """Get full path to log file"""
        if not self._config:
            self.load_config()
        
        log_path = Path(self._config.paths.logs_dir) / log_name
        return str(log_path)
    
    @property
    def deployment_mode(self) -> DeploymentMode:
        """Get current deployment mode"""
        return self._deployment_mode
    
    @property
    def is_portable(self) -> bool:
        """Check if running in portable mode"""
        return self._deployment_mode == DeploymentMode.PORTABLE
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self._deployment_mode == DeploymentMode.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self._deployment_mode == DeploymentMode.DEVELOPMENT


# Global configuration manager instance
config_manager = ConfigManager()


def get_config() -> SystemConfig:
    """Get global configuration instance"""
    return config_manager.get_config()


def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance"""
    return config_manager


def initialize_config(config_file: str, model_id: Optional[str] = None) -> ConfigManager:
    """
    Initialize configuration with specific config file
    
    Args:
        config_file: Path to configuration file
        model_id: Optional model ID to use
        
    Returns:
        ConfigManager instance
    """
    global config_manager
    config_manager = ConfigManager(config_file)
    
    # Load network configuration
    import json
    with open(config_file, 'r') as f:
        network_config = json.load(f)
    
    # Add network config to manager
    config_manager.network_config = network_config
    
    # Add selected model info (simplified)
    if model_id:
        config_manager.selected_model = {
            'id': model_id,
            'name': model_id,
            'stats': {'has_tokenizer': True}
        }
    else:
        # Default model info
        config_manager.selected_model = {
            'id': 'llama3_1_8b_fp16',
            'name': 'Llama 3.1 8B FP16',
            'stats': {'has_tokenizer': True}
        }
    
    return config_manager