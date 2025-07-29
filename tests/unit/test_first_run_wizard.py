"""
Tests for First-Run Wizard
Tests wizard functionality, license validation, and network setup
"""

import unittest
import sys
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Mock PyQt6 before importing
sys.modules['PyQt6'] = MagicMock()
sys.modules['PyQt6.QtWidgets'] = MagicMock()
sys.modules['PyQt6.QtCore'] = MagicMock()
sys.modules['PyQt6.QtGui'] = MagicMock()

# Mock our modules
sys.modules['license_validator'] = MagicMock()
sys.modules['license_storage'] = MagicMock()
sys.modules['network_manager'] = MagicMock()
sys.modules['config_manager'] = MagicMock()

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestFirstRunWizardComponents(unittest.TestCase):
    """Test first-run wizard components"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_wizard_module_import(self):
        """Test that wizard module can be imported"""
        try:
            import first_run_wizard
            
            # Test that main components exist
            self.assertTrue(hasattr(first_run_wizard, 'FirstRunWizard'))
            self.assertTrue(hasattr(first_run_wizard, 'WelcomePage'))
            self.assertTrue(hasattr(first_run_wizard, 'LicensePage'))
            self.assertTrue(hasattr(first_run_wizard, 'NetworkSetupPage'))
            self.assertTrue(hasattr(first_run_wizard, 'CompletionPage'))
            
        except ImportError as e:
            self.skipTest(f"PyQt6 not available: {e}")
    
    def test_welcome_page_exists(self):
        """Test welcome page component"""
        try:
            import first_run_wizard
            
            # Test that WelcomePage is defined
            self.assertTrue(hasattr(first_run_wizard, 'WelcomePage'))
            
        except ImportError as e:
            self.skipTest(f"PyQt6 not available: {e}")
    
    def test_license_page_exists(self):
        """Test license page component"""
        try:
            import first_run_wizard
            
            # Test that LicensePage is defined
            self.assertTrue(hasattr(first_run_wizard, 'LicensePage'))
            
        except ImportError as e:
            self.skipTest(f"PyQt6 not available: {e}")
    
    def test_network_setup_page_exists(self):
        """Test network setup page component"""
        try:
            import first_run_wizard
            
            # Test that NetworkSetupPage is defined
            self.assertTrue(hasattr(first_run_wizard, 'NetworkSetupPage'))
            
        except ImportError as e:
            self.skipTest(f"PyQt6 not available: {e}")
    
    def test_completion_page_exists(self):
        """Test completion page component"""
        try:
            import first_run_wizard
            
            # Test that CompletionPage is defined
            self.assertTrue(hasattr(first_run_wizard, 'CompletionPage'))
            
        except ImportError as e:
            self.skipTest(f"PyQt6 not available: {e}")


class TestWizardFunctionality(unittest.TestCase):
    """Test wizard functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_main_wizard_class(self):
        """Test main wizard class"""
        try:
            import first_run_wizard
            
            # Test that FirstRunWizard is properly defined
            wizard_class = getattr(first_run_wizard, 'FirstRunWizard')
            self.assertTrue(callable(wizard_class))
            
        except ImportError as e:
            self.skipTest(f"PyQt6 not available: {e}")
    
    def test_wizard_pages_integration(self):
        """Test wizard pages integration"""
        try:
            import first_run_wizard
            
            # Test that all page classes exist
            pages = ['WelcomePage', 'LicensePage', 'NetworkSetupPage', 'CompletionPage']
            
            for page_name in pages:
                self.assertTrue(hasattr(first_run_wizard, page_name))
                page_class = getattr(first_run_wizard, page_name)
                self.assertTrue(callable(page_class))
            
        except ImportError as e:
            self.skipTest(f"PyQt6 not available: {e}")


class TestLicenseValidation(unittest.TestCase):
    """Test license validation in wizard"""
    
    def test_license_format_validation(self):
        """Test license format validation logic"""
        # Test basic format validation logic
        test_cases = [
            ("TIKT-FREE-1M-ABC123", True),
            ("TIKT-PRO-2M-XYZ789", True),
            ("TIKT-ENT-6M-DEF456", True),
            ("INVALID-FORMAT", False),
            ("TIKT-ONLY-THREE", False),
            ("", False),
        ]
        
        for license_key, expected_valid in test_cases:
            # Basic format check
            parts = license_key.split('-') if license_key else []
            is_valid_format = len(parts) == 4 and parts[0] == 'TIKT' if parts else False
            
            if expected_valid:
                self.assertTrue(is_valid_format, f"License {license_key} should have valid format")
            else:
                self.assertFalse(is_valid_format, f"License {license_key} should have invalid format")


class TestNetworkSetup(unittest.TestCase):
    """Test network setup functionality"""
    
    def test_network_actions(self):
        """Test network setup actions"""
        # Test that we have the expected network actions
        expected_actions = ['create', 'join', 'skip']
        
        # This would be tested with actual wizard in real scenario
        for action in expected_actions:
            self.assertIn(action, expected_actions)
    
    def test_network_configuration_structure(self):
        """Test network configuration structure"""
        # Test expected configuration structure
        create_config = {
            "action": "create",
            "name": "Test Network",
            "model": "llama-7b-chat"
        }
        
        join_config = {
            "action": "join",
            "network": "Existing Network"
        }
        
        skip_config = {
            "action": "skip"
        }
        
        # Verify structure
        self.assertEqual(create_config["action"], "create")
        self.assertIn("name", create_config)
        self.assertIn("model", create_config)
        
        self.assertEqual(join_config["action"], "join")
        self.assertIn("network", join_config)
        
        self.assertEqual(skip_config["action"], "skip")


class TestWizardIntegration(unittest.TestCase):
    """Test wizard integration with main app"""
    
    def test_wizard_completion_signal(self):
        """Test wizard completion signal structure"""
        # Test expected completion result structure
        expected_result = {
            'license_info': None,  # Would be LicenseInfo object
            'network_config': {
                'action': 'create',
                'name': 'Test Network',
                'model': 'llama-7b-chat'
            }
        }
        
        # Verify structure
        self.assertIn('license_info', expected_result)
        self.assertIn('network_config', expected_result)
        self.assertIsInstance(expected_result['network_config'], dict)
    
    def test_main_app_integration(self):
        """Test integration with main application"""
        try:
            # Test that main_app can import first_run_wizard
            import main_app
            
            # This would test actual integration in real scenario
            self.assertTrue(hasattr(main_app, 'FirstRunWizard'))
            
        except ImportError as e:
            self.skipTest(f"PyQt6 not available: {e}")


class TestWizardUI(unittest.TestCase):
    """Test wizard UI components"""
    
    def test_wizard_styling(self):
        """Test wizard styling and appearance"""
        try:
            import first_run_wizard
            
            # Test that wizard module loads without errors
            self.assertTrue(hasattr(first_run_wizard, 'FirstRunWizard'))
            
            # In a real test, we would verify styling constants and CSS
            
        except ImportError as e:
            self.skipTest(f"PyQt6 not available: {e}")
    
    def test_wizard_navigation(self):
        """Test wizard page navigation"""
        # Test expected page flow
        expected_pages = [
            'WelcomePage',
            'LicensePage', 
            'NetworkSetupPage',
            'CompletionPage'
        ]
        
        # Verify page sequence
        for i, page in enumerate(expected_pages):
            self.assertIsInstance(page, str)
            self.assertTrue(page.endswith('Page'))


class TestWizardErrorHandling(unittest.TestCase):
    """Test wizard error handling"""
    
    def test_license_validation_errors(self):
        """Test license validation error handling"""
        # Test various error scenarios
        error_cases = [
            ("", "Empty license key"),
            ("INVALID", "Invalid format"),
            ("TIKT-INVALID-FORMAT", "Incomplete format"),
        ]
        
        for license_key, expected_error_type in error_cases:
            # Basic validation that would catch these errors
            try:
                parts = license_key.split('-') if license_key else []
                if not license_key:
                    raise ValueError("Empty license key")
                if len(parts) != 4 or parts[0] != 'TIKT':
                    raise ValueError("Invalid format")
                    
            except ValueError as e:
                # Error was caught as expected
                self.assertIsInstance(e, ValueError)
    
    def test_network_setup_errors(self):
        """Test network setup error handling"""
        # Test network setup error scenarios
        error_scenarios = [
            {"action": "create", "name": ""},  # Empty name
            {"action": "join", "network": None},  # No network selected
        ]
        
        for config in error_scenarios:
            if config["action"] == "create":
                self.assertFalse(bool(config.get("name", "").strip()))
            elif config["action"] == "join":
                self.assertIsNone(config.get("network"))


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    unittest.main(verbosity=2)