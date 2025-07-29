"""
Unit Tests for Windows Service Integration
Tests service installation, configuration, monitoring, and lifecycle management

Requirements addressed:
- 13.2: Windows service registration and management
- 13.3: Automatic startup configuration
- Service monitoring and health checks
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from windows_service import TikTrueLLMService, ServiceManager
from service_installer import EnhancedServiceInstaller, ServiceDependencyManager, ServiceConfigurationManager
from service_monitor import ServiceMonitor, HealthChecker, HealthStatus
from core.service_runner import TikTrueServiceRunner, ServiceMode


class TestWindowsService(unittest.TestCase):
    """Test Windows service wrapper functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create test configuration
        self.test_config = {
            "service_name": "TestTikTrueLLMService",
            "display_name": "Test TikTrue Service",
            "description": "Test service",
            "auto_start": True,
            "main_script": "test_service_runner.py",
            "python_executable": sys.executable,
            "working_directory": self.temp_dir
        }
        
        # Create test service runner script
        with open("test_service_runner.py", "w") as f:
            f.write("# Test service runner\nprint('Test service running')\n")
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('windows_service.WINDOWS_SERVICE_AVAILABLE', False)
    def test_service_initialization_without_windows_modules(self):
        """Test service initialization when Windows modules are not available"""
        service = TikTrueLLMService([])
        
        self.assertIsNotNone(service)
        self.assertEqual(service._svc_name_, "TikTrueLLMService")
        self.assertFalse(service.is_running)
    
    def test_service_config_loading(self):
        """Test service configuration loading and validation"""
        # Create test config file
        config_file = "test_service_config.json"
        with open(config_file, "w") as f:
            json.dump(self.test_config, f)
        
        service = TikTrueLLMService([])
        service.config_file = config_file
        
        config = service._load_service_config()
        
        self.assertEqual(config["service_name"], "TestTikTrueLLMService")
        self.assertEqual(config["auto_start"], True)
        self.assertTrue(Path(config_file).exists())
    
    def test_service_config_default_creation(self):
        """Test default configuration creation when no config exists"""
        service = TikTrueLLMService([])
        service.config_file = "nonexistent_config.json"
        
        config = service._load_service_config()
        
        self.assertIn("service_name", config)
        self.assertIn("auto_start", config)
        self.assertTrue(Path("nonexistent_config.json").exists())
    
    @patch('subprocess.Popen')
    def test_start_main_process(self, mock_popen):
        """Test starting the main application process"""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        service = TikTrueLLMService([])
        service.service_config = self.test_config
        
        success = service._start_main_process()
        
        self.assertTrue(success)
        self.assertEqual(service.main_process, mock_process)
        mock_popen.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_start_main_process_failure(self, mock_popen):
        """Test handling of main process start failure"""
        mock_popen.side_effect = Exception("Process start failed")
        
        service = TikTrueLLMService([])
        service.service_config = self.test_config
        
        success = service._start_main_process()
        
        self.assertFalse(success)
        self.assertIsNone(service.main_process)
    
    def test_get_service_status(self):
        """Test service status reporting"""
        service = TikTrueLLMService([])
        service.is_running = True
        
        status = service.get_service_status()
        
        self.assertIn("service_name", status)
        self.assertIn("is_running", status)
        self.assertTrue(status["is_running"])
        self.assertIn("timestamp", status)


class TestServiceManager(unittest.TestCase):
    """Test service management utilities"""
    
    @patch('windows_service.WINDOWS_SERVICE_AVAILABLE', False)
    def test_service_operations_without_windows_modules(self):
        """Test service operations when Windows modules are not available"""
        self.assertFalse(ServiceManager.install_service())
        self.assertFalse(ServiceManager.uninstall_service())
        self.assertFalse(ServiceManager.start_service())
        self.assertFalse(ServiceManager.stop_service())
    
    @patch('windows_service.WINDOWS_SERVICE_AVAILABLE', True)
    @patch('windows_service.win32serviceutil')
    def test_install_service(self, mock_serviceutil):
        """Test service installation"""
        mock_serviceutil.InstallService = Mock()
        
        result = ServiceManager.install_service()
        
        self.assertTrue(result)
        mock_serviceutil.InstallService.assert_called_once()
    
    @patch('windows_service.WINDOWS_SERVICE_AVAILABLE', True)
    @patch('windows_service.win32serviceutil')
    def test_install_service_failure(self, mock_serviceutil):
        """Test service installation failure handling"""
        mock_serviceutil.InstallService.side_effect = Exception("Installation failed")
        
        result = ServiceManager.install_service()
        
        self.assertFalse(result)


class TestServiceDependencyManager(unittest.TestCase):
    """Test service dependency management"""
    
    def setUp(self):
        """Set up test environment"""
        self.dependency_manager = ServiceDependencyManager()
    
    def test_check_python_version(self):
        """Test Python version checking"""
        valid, version_info = self.dependency_manager.check_python_version()
        
        # Should be valid since we're running the test
        self.assertTrue(valid)
        self.assertIn("Python", version_info)
    
    @patch('subprocess.run')
    def test_install_python_requirements_success(self, mock_run):
        """Test successful Python requirements installation"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        success = self.dependency_manager.install_python_requirements()
        
        self.assertTrue(success)
        self.assertGreater(mock_run.call_count, 0)
    
    @patch('subprocess.run')
    def test_install_python_requirements_failure(self, mock_run):
        """Test Python requirements installation failure"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Installation failed"
        mock_run.return_value = mock_result
        
        success = self.dependency_manager.install_python_requirements()
        
        self.assertFalse(success)
    
    def test_validate_dependencies(self):
        """Test dependency validation"""
        result = self.dependency_manager.validate_dependencies()
        
        self.assertIn("python_version", result)
        self.assertIn("windows_modules", result)
        self.assertIn("required_files", result)
        self.assertIn("overall_valid", result)
        
        # Python version should be valid
        self.assertTrue(result["python_version"]["valid"])


class TestServiceConfigurationManager(unittest.TestCase):
    """Test service configuration management"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        self.config_manager = ServiceConfigurationManager()
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_default_config(self):
        """Test loading default configuration"""
        config = self.config_manager.load_config()
        
        self.assertIn("service_name", config)
        self.assertIn("display_name", config)
        self.assertIn("auto_start", config)
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration"""
        test_config = {
            "service_name": "TestService",
            "display_name": "Test Service",
            "auto_start": False
        }
        
        # Save config
        success = self.config_manager.save_config(test_config)
        self.assertTrue(success)
        
        # Load config
        loaded_config = self.config_manager.load_config()
        self.assertEqual(loaded_config["service_name"], "TestService")
        self.assertFalse(loaded_config["auto_start"])
    
    def test_update_config(self):
        """Test configuration updates"""
        updates = {"auto_start": False, "restart_delay_seconds": 60}
        
        success = self.config_manager.update_config(updates)
        self.assertTrue(success)
        
        config = self.config_manager.load_config()
        self.assertFalse(config["auto_start"])
        self.assertEqual(config["restart_delay_seconds"], 60)
    
    def test_validate_config_valid(self):
        """Test validation of valid configuration"""
        valid_config = {
            "service_name": "TestService",
            "display_name": "Test Service",
            "description": "Test description",
            "main_script": "test_script.py",
            "python_executable": sys.executable,
            "working_directory": self.temp_dir,
            "restart_delay_seconds": 30,
            "max_restart_attempts": 5
        }
        
        # Create the main script file
        with open("test_script.py", "w") as f:
            f.write("# Test script\n")
        
        is_valid, errors = self.config_manager.validate_config(valid_config)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_config_invalid(self):
        """Test validation of invalid configuration"""
        invalid_config = {
            "service_name": "",  # Empty required field
            "main_script": "nonexistent_script.py",  # Non-existent file
            "restart_delay_seconds": -1,  # Invalid value
            "max_restart_attempts": 1000  # Out of range
        }
        
        is_valid, errors = self.config_manager.validate_config(invalid_config)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


class TestServiceMonitor(unittest.TestCase):
    """Test service monitoring functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.monitor_config = {
            "monitoring_interval": 1,
            "health_check_interval": 1,
            "max_history_size": 10,
            "enabled_checks": ["system_resources"]
        }
        self.monitor = ServiceMonitor(self.monitor_config)
    
    def tearDown(self):
        """Clean up test environment"""
        if self.monitor.is_running:
            self.monitor.stop_monitoring()
    
    def test_monitor_initialization(self):
        """Test service monitor initialization"""
        self.assertIsNotNone(self.monitor)
        self.assertFalse(self.monitor.is_running)
        self.assertEqual(len(self.monitor.health_checkers), 1)  # system_resources check
    
    def test_add_custom_health_check(self):
        """Test adding custom health check"""
        def custom_check():
            return {"status": HealthStatus.HEALTHY, "message": "Custom check OK"}
        
        self.monitor.add_health_check("custom_check", custom_check, 5)
        
        self.assertIn("custom_check", self.monitor.health_checkers)
        self.assertEqual(self.monitor.health_checkers["custom_check"].interval_seconds, 5)
    
    def test_remove_health_check(self):
        """Test removing health check"""
        def test_check():
            return {"status": HealthStatus.HEALTHY, "message": "Test"}
        
        self.monitor.add_health_check("test_check", test_check)
        self.assertIn("test_check", self.monitor.health_checkers)
        
        self.monitor.remove_health_check("test_check")
        self.assertNotIn("test_check", self.monitor.health_checkers)
    
    def test_get_health_status(self):
        """Test getting health status"""
        status = self.monitor.get_health_status()
        
        self.assertIn("overall_status", status)
        self.assertIn("health_checks", status)
        self.assertIn("monitoring_active", status)
        self.assertIn("last_updated", status)
    
    def test_export_health_report(self):
        """Test exporting health report"""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            report_path = self.monitor.export_health_report(f.name)
        
        self.assertTrue(Path(report_path).exists())
        
        # Verify report content
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        self.assertIn("report_timestamp", report)
        self.assertIn("service_info", report)
        self.assertIn("current_status", report)
        
        # Clean up
        Path(report_path).unlink()


class TestTikTrueServiceRunner(unittest.TestCase):
    """Test service runner functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create minimal config file
        config = {
            "network_config": {
                "discovery_port": 8888,
                "websocket_port": 8765
            }
        }
        with open("network_config.json", "w") as f:
            json.dump(config, f)
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('core.service_runner.ConfigManager')
    @patch('core.service_runner.NetworkManager')
    @patch('core.service_runner.NetworkDiscovery')
    @patch('core.service_runner.UnifiedWebSocketServer')
    @patch('core.service_runner.LicenseValidator')
    def test_service_runner_initialization(self, mock_license, mock_websocket, 
                                         mock_discovery, mock_network, mock_config):
        """Test service runner initialization"""
        # Mock the imports
        mock_config.return_value = Mock()
        mock_network.return_value = Mock()
        mock_discovery.return_value = Mock()
        mock_websocket.return_value = Mock()
        mock_license.return_value = Mock()
        
        runner = TikTrueServiceRunner("network_config.json")
        
        self.assertIsNotNone(runner)
        self.assertEqual(runner.service_mode, ServiceMode.DISCOVERY)
        self.assertFalse(runner.is_running)
    
    def test_load_service_config(self):
        """Test loading service configuration"""
        # Create service config
        service_config = {
            "service_mode": ServiceMode.ADMIN,
            "websocket_port": 9999
        }
        with open("service_config.json", "w") as f:
            json.dump(service_config, f)
        
        with patch('core.service_runner.ConfigManager'), \
             patch('core.service_runner.NetworkManager'), \
             patch('core.service_runner.NetworkDiscovery'), \
             patch('core.service_runner.UnifiedWebSocketServer'), \
             patch('core.service_runner.LicenseValidator'):
            
            runner = TikTrueServiceRunner()
            config = runner._load_service_config()
            
            self.assertEqual(config["service_mode"], ServiceMode.ADMIN)
            self.assertEqual(config["websocket_port"], 9999)
    
    def test_service_mode_detection(self):
        """Test service mode detection and configuration"""
        test_modes = [ServiceMode.ADMIN, ServiceMode.CLIENT, ServiceMode.DISCOVERY]
        
        for mode in test_modes:
            service_config = {"service_mode": mode}
            with open("service_config.json", "w") as f:
                json.dump(service_config, f)
            
            with patch('core.service_runner.ConfigManager'), \
                 patch('core.service_runner.NetworkManager'), \
                 patch('core.service_runner.NetworkDiscovery'), \
                 patch('core.service_runner.UnifiedWebSocketServer'), \
                 patch('core.service_runner.LicenseValidator'):
                
                runner = TikTrueServiceRunner()
                self.assertEqual(runner.service_mode, mode)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestWindowsService,
        TestServiceManager,
        TestServiceDependencyManager,
        TestServiceConfigurationManager,
        TestServiceMonitor,
        TestTikTrueServiceRunner
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)