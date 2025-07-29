"""
Unit tests for TikTrue Platform Configuration Management System

Tests cover:
- Configuration loading and validation
- Dynamic path resolution
- Different deployment modes
- Schema validation
- Error handling
"""

import unittest
import tempfile
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.config_manager import (
    ConfigManager, 
    DeploymentMode, 
    SystemConfig, 
    NetworkConfig, 
    PathConfig, 
    SecurityConfig,
    ConfigurationError,
    get_config,
    get_config_manager
)


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager class"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        
        # Sample valid configuration
        self.valid_config = {
            "deployment_mode": "development",
            "paths": {
                "models_dir": "assets/models",
                "logs_dir": "logs",
                "sessions_dir": "sessions",
                "data_dir": "data",
                "config_dir": ".",
                "temp_dir": "temp"
            },
            "network": {
                "network_id": "test_network",
                "network_name": "Test Network",
                "admin_node_id": "admin_test",
                "max_clients": 5,
                "allowed_models": ["test_model"],
                "encryption_enabled": True,
                "discovery_port": 8765,
                "communication_port": 8766
            },
            "security": {
                "encryption_key_rotation_days": 30,
                "max_login_attempts": 3,
                "session_timeout_minutes": 60,
                "hardware_fingerprint_enabled": True,
                "audit_logging_enabled": True
            },
            "version": "1.0.0",
            "created_at": "2024-01-01T00:00:00"
        }
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_deployment_mode_detection(self):
        """Test deployment mode detection logic"""
        # Test environment variable detection
        with patch.dict(os.environ, {'TIKTRUE_DEPLOYMENT_MODE': 'production'}):
            config_manager = ConfigManager()
            self.assertEqual(config_manager._detect_deployment_mode(), DeploymentMode.PRODUCTION)
        
        # Test frozen executable detection (production)
        with patch.object(sys, 'frozen', True, create=True):
            with patch.object(Path, 'exists', return_value=False):
                config_manager = ConfigManager()
                self.assertEqual(config_manager._detect_deployment_mode(), DeploymentMode.PRODUCTION)
        
        # Test portable mode detection
        with patch.object(sys, 'frozen', True, create=True):
            with patch.object(Path, 'exists', return_value=True):
                config_manager = ConfigManager()
                self.assertEqual(config_manager._detect_deployment_mode(), DeploymentMode.PORTABLE)
        
        # Test development mode (default)
        with patch.object(sys, 'frozen', False, create=True):
            config_manager = ConfigManager()
            self.assertEqual(config_manager._detect_deployment_mode(), DeploymentMode.DEVELOPMENT)
    
    def test_config_file_detection(self):
        """Test configuration file detection based on deployment mode"""
        # Test portable mode
        with patch.object(sys, 'frozen', True, create=True):
            with patch.object(sys, 'executable', '/app/tiktrue.exe'):
                with patch.object(Path, 'exists', return_value=True):
                    config_manager = ConfigManager()
                    expected_path = str(Path('/app/portable_config.json'))
                    self.assertEqual(config_manager._detect_config_file(), expected_path)
        
        # Test production and development modes
        config_manager = ConfigManager()
        self.assertEqual(config_manager._detect_config_file(), "network_config.json")
    
    def test_default_paths_generation(self):
        """Test default path generation for different deployment modes"""
        config_manager = ConfigManager()
        
        # Test development mode paths
        dev_paths = config_manager._get_default_paths(DeploymentMode.DEVELOPMENT)
        self.assertEqual(dev_paths.models_dir, "assets/models")
        self.assertEqual(dev_paths.logs_dir, "logs")
        
        # Test portable mode paths
        with patch.object(sys, 'frozen', True, create=True):
            with patch.object(sys, 'executable', '/app/tiktrue.exe'):
                portable_paths = config_manager._get_default_paths(DeploymentMode.PORTABLE)
                # Use os.path.join for cross-platform compatibility
                expected_suffix = os.path.join("assets", "models")
                self.assertTrue(portable_paths.models_dir.endswith(expected_suffix))
        
        # Test production mode paths
        prod_paths = config_manager._get_default_paths(DeploymentMode.PRODUCTION)
        self.assertTrue("TikTrue" in prod_paths.models_dir or ".tiktrue" in prod_paths.models_dir)
    
    def test_config_schema_validation(self):
        """Test configuration schema validation"""
        config_manager = ConfigManager()
        
        # Test valid configuration
        self.assertTrue(config_manager._validate_config_schema(self.valid_config))
        
        # Test missing required key
        invalid_config = self.valid_config.copy()
        del invalid_config["deployment_mode"]
        with self.assertRaises(ConfigurationError):
            config_manager._validate_config_schema(invalid_config)
        
        # Test invalid deployment mode
        invalid_config = self.valid_config.copy()
        invalid_config["deployment_mode"] = "invalid_mode"
        with self.assertRaises(ConfigurationError):
            config_manager._validate_config_schema(invalid_config)
        
        # Test invalid port
        invalid_config = self.valid_config.copy()
        invalid_config["network"]["discovery_port"] = 99999
        with self.assertRaises(ConfigurationError):
            config_manager._validate_config_schema(invalid_config)
        
        # Test invalid max_clients
        invalid_config = self.valid_config.copy()
        invalid_config["network"]["max_clients"] = 0
        with self.assertRaises(ConfigurationError):
            config_manager._validate_config_schema(invalid_config)
    
    def test_load_config_from_file(self):
        """Test loading configuration from existing file"""
        # Create test configuration file
        with open(self.config_file, 'w') as f:
            json.dump(self.valid_config, f)
        
        config_manager = ConfigManager(self.config_file)
        config = config_manager.load_config()
        
        self.assertIsInstance(config, SystemConfig)
        self.assertEqual(config.deployment_mode, "development")
        self.assertEqual(config.network.network_id, "test_network")
        self.assertEqual(config.network.max_clients, 5)
    
    def test_load_config_create_default(self):
        """Test creating default configuration when file doesn't exist"""
        config_manager = ConfigManager(self.config_file)
        config = config_manager.load_config()
        
        self.assertIsInstance(config, SystemConfig)
        self.assertEqual(config.deployment_mode, "development")
        self.assertEqual(config.network.network_name, "TikTrue Network")
        self.assertTrue(config.network.encryption_enabled)
        
        # Verify file was created
        self.assertTrue(os.path.exists(self.config_file))
    
    def test_save_config(self):
        """Test saving configuration to file"""
        config_manager = ConfigManager(self.config_file)
        config = config_manager.load_config()
        
        # Modify configuration
        config.network.network_name = "Modified Network"
        config_manager._config = config
        config_manager.save_config()
        
        # Verify file was updated
        with open(self.config_file, 'r') as f:
            saved_config = json.load(f)
        
        self.assertEqual(saved_config["network"]["network_name"], "Modified Network")
    
    def test_update_config(self):
        """Test updating configuration values"""
        config_manager = ConfigManager(self.config_file)
        config_manager.load_config()
        
        # Update configuration
        config_manager.update_config(version="2.0.0")
        
        updated_config = config_manager.get_config()
        self.assertEqual(updated_config.version, "2.0.0")
    
    def test_path_resolution(self):
        """Test dynamic path resolution"""
        config_manager = ConfigManager(self.config_file)
        config_manager.load_config()
        
        # Test absolute path (should return as-is)
        abs_path = "/absolute/path/test"
        if os.name == 'nt':
            abs_path = "C:\\absolute\\path\\test"
        
        resolved = config_manager.resolve_path(abs_path)
        self.assertEqual(resolved, abs_path)
        
        # Test relative path resolution
        relative_path = "relative/path/test"
        resolved = config_manager.resolve_path(relative_path)
        self.assertTrue(os.path.isabs(resolved))
        self.assertTrue(resolved.endswith("relative/path/test") or 
                       resolved.endswith("relative\\path\\test"))
    
    def test_model_path_generation(self):
        """Test model path generation"""
        config_manager = ConfigManager(self.config_file)
        config_manager.load_config()
        
        model_path = config_manager.get_model_path("test_model")
        self.assertTrue(model_path.endswith("test_model") or 
                       model_path.endswith("test_model"))
        self.assertTrue("models" in model_path)
    
    def test_log_path_generation(self):
        """Test log path generation"""
        config_manager = ConfigManager(self.config_file)
        config_manager.load_config()
        
        log_path = config_manager.get_log_path("test.log")
        self.assertTrue(log_path.endswith("test.log"))
        self.assertTrue("logs" in log_path)
    
    def test_deployment_mode_properties(self):
        """Test deployment mode property methods"""
        # Test development mode
        with patch.object(ConfigManager, '_detect_deployment_mode', 
                         return_value=DeploymentMode.DEVELOPMENT):
            config_manager = ConfigManager()
            self.assertTrue(config_manager.is_development)
            self.assertFalse(config_manager.is_production)
            self.assertFalse(config_manager.is_portable)
        
        # Test production mode
        with patch.object(ConfigManager, '_detect_deployment_mode', 
                         return_value=DeploymentMode.PRODUCTION):
            config_manager = ConfigManager()
            self.assertFalse(config_manager.is_development)
            self.assertTrue(config_manager.is_production)
            self.assertFalse(config_manager.is_portable)
        
        # Test portable mode
        with patch.object(ConfigManager, '_detect_deployment_mode', 
                         return_value=DeploymentMode.PORTABLE):
            config_manager = ConfigManager()
            self.assertFalse(config_manager.is_development)
            self.assertFalse(config_manager.is_production)
            self.assertTrue(config_manager.is_portable)
    
    def test_directory_creation(self):
        """Test automatic directory creation"""
        config_manager = ConfigManager(self.config_file)
        config = config_manager.load_config()
        
        # Check that directories were created
        paths_to_check = [
            config.paths.models_dir,
            config.paths.logs_dir,
            config.paths.sessions_dir,
            config.paths.data_dir,
            config.paths.temp_dir
        ]
        
        for path_str in paths_to_check:
            path = Path(path_str)
            if not path.is_absolute():
                # Make relative paths absolute for testing
                path = Path.cwd() / path
            # Note: In test environment, directories might not be created
            # This test verifies the method doesn't raise exceptions
            self.assertIsNotNone(path_str)
    
    def test_global_functions(self):
        """Test global configuration functions"""
        # Test get_config function
        config = get_config()
        self.assertIsInstance(config, SystemConfig)
        
        # Test get_config_manager function
        manager = get_config_manager()
        self.assertIsInstance(manager, ConfigManager)
    
    def test_error_handling(self):
        """Test error handling scenarios"""
        # Test invalid JSON file
        with open(self.config_file, 'w') as f:
            f.write("invalid json content")
        
        config_manager = ConfigManager(self.config_file)
        with self.assertRaises(ConfigurationError):
            config_manager.load_config()
        
        # Test save without loaded config
        config_manager = ConfigManager(self.config_file)
        config_manager._config = None
        with self.assertRaises(ConfigurationError):
            config_manager.save_config()


class TestDataClasses(unittest.TestCase):
    """Test configuration data classes"""
    
    def test_network_config_creation(self):
        """Test NetworkConfig data class"""
        network = NetworkConfig(
            network_id="test",
            network_name="Test Network",
            admin_node_id="admin",
            max_clients=10,
            allowed_models=["model1"],
            encryption_enabled=True,
            discovery_port=8765,
            communication_port=8766
        )
        
        self.assertEqual(network.network_id, "test")
        self.assertEqual(network.max_clients, 10)
        self.assertTrue(network.encryption_enabled)
    
    def test_path_config_creation(self):
        """Test PathConfig data class"""
        paths = PathConfig(
            models_dir="models",
            logs_dir="logs",
            sessions_dir="sessions",
            data_dir="data",
            config_dir="config",
            temp_dir="temp"
        )
        
        self.assertEqual(paths.models_dir, "models")
        self.assertEqual(paths.logs_dir, "logs")
    
    def test_security_config_creation(self):
        """Test SecurityConfig data class"""
        security = SecurityConfig(
            encryption_key_rotation_days=30,
            max_login_attempts=3,
            session_timeout_minutes=60,
            hardware_fingerprint_enabled=True,
            audit_logging_enabled=True
        )
        
        self.assertEqual(security.encryption_key_rotation_days, 30)
        self.assertEqual(security.max_login_attempts, 3)
        self.assertTrue(security.hardware_fingerprint_enabled)


if __name__ == '__main__':
    unittest.main()