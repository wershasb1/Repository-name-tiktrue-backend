"""
Unit tests for Admin mode interface functionality

Tests cover:
- Login/logout interface with backend authentication (Requirement 2.1)
- License status display and management interface (Requirement 8.2)
- Network creation and client management dashboard
- Model management interface with download progress
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# PyQt6 test imports
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt

# Import modules to test
from main_app import (
    LoginDialog, ModelDownloadDialog, AdminModeWidget
)
from PyQt6.QtWidgets import QMessageBox


class TestLoginDialog(unittest.TestCase):
    """Test login dialog functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test application"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        self.dialog = LoginDialog()
    
    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'dialog'):
            self.dialog.close()
    
    def test_dialog_initialization(self):
        """Test dialog initializes correctly"""
        self.assertIsNotNone(self.dialog)
        self.assertEqual(self.dialog.windowTitle(), "Admin Login - TikTrue")
        self.assertTrue(self.dialog.isModal())
        self.assertIsNone(self.dialog.user_info)
        self.assertTrue(self.dialog.login_btn.isEnabled())
    
    def test_empty_credentials_validation(self):
        """Test validation with empty credentials"""
        self.dialog.email_input.setText("")
        self.dialog.password_input.setText("")
        self.dialog.attempt_login()
        
        self.assertIn("Please enter both email and password", self.dialog.status_label.text())
    
    def test_partial_credentials_validation(self):
        """Test validation with partial credentials"""
        # Test email only
        self.dialog.email_input.setText("admin@test.com")
        self.dialog.password_input.setText("")
        self.dialog.attempt_login()
        
        self.assertIn("Please enter both email and password", self.dialog.status_label.text())
        
        # Test password only
        self.dialog.email_input.setText("")
        self.dialog.password_input.setText("password123")
        self.dialog.attempt_login()
        
        self.assertIn("Please enter both email and password", self.dialog.status_label.text())
    
    def test_successful_login_simulation(self):
        """Test successful login simulation"""
        email = "admin@test.com"
        password = "password123"
        
        # Mock the timer to execute immediately
        with patch.object(QTimer, 'singleShot', side_effect=lambda delay, func: func()):
            self.dialog.email_input.setText(email)
            self.dialog.password_input.setText(password)
            self.dialog.attempt_login()
            
            # Check that user info was set
            self.assertIsNotNone(self.dialog.user_info)
            self.assertEqual(self.dialog.user_info["email"], email)
            self.assertIn("plan_type", self.dialog.user_info)
            self.assertIn("max_clients", self.dialog.user_info)
    
    def test_status_message_styling(self):
        """Test status message styling for different types"""
        # Test info status
        self.dialog.show_status("Test info message", "info")
        self.assertIn("#3498db", self.dialog.status_label.styleSheet())
        
        # Test success status
        self.dialog.show_status("Test success message", "success")
        self.assertIn("#27ae60", self.dialog.status_label.styleSheet())
        
        # Test error status
        self.dialog.show_status("Test error message", "error")
        self.assertIn("#e74c3c", self.dialog.status_label.styleSheet())
    
    def test_login_button_state_during_login(self):
        """Test login button state changes during login process"""
        self.dialog.email_input.setText("admin@test.com")
        self.dialog.password_input.setText("password123")
        
        # Start login process
        self.dialog.attempt_login()
        
        # Button should be disabled and text changed
        self.assertFalse(self.dialog.login_btn.isEnabled())
        self.assertEqual(self.dialog.login_btn.text(), "Logging in...")


class TestModelDownloadDialog(unittest.TestCase):
    """Test model download dialog functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test application"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        self.models = ["llama3_1_8b_fp16", "mistral_7b_int4", "gpt4_turbo_preview"]
        self.dialog = ModelDownloadDialog(self.models)
    
    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'dialog'):
            self.dialog.close()
    
    def test_dialog_initialization(self):
        """Test dialog initializes correctly"""
        self.assertIsNotNone(self.dialog)
        self.assertEqual(self.dialog.windowTitle(), "Download Models")
        self.assertTrue(self.dialog.isModal())
        self.assertEqual(len(self.dialog.model_checkboxes), len(self.models))
        self.assertFalse(self.dialog.progress_bar.isVisible())
    
    def test_model_checkboxes_creation(self):
        """Test model checkboxes are created correctly"""
        self.assertEqual(len(self.dialog.model_checkboxes), len(self.models))
        
        for i, model in enumerate(self.models):
            checkbox = self.dialog.model_checkboxes[i]
            self.assertEqual(checkbox.text(), model)
            self.assertFalse(checkbox.isChecked())
    
    def test_no_selection_warning(self):
        """Test warning when no models are selected"""
        with patch('main_app.QMessageBox.warning') as mock_warning:
            self.dialog.start_download()
            mock_warning.assert_called_once()
    
    def test_model_selection(self):
        """Test model selection functionality"""
        # Select first two models
        self.dialog.model_checkboxes[0].setChecked(True)
        self.dialog.model_checkboxes[1].setChecked(True)
        
        selected = [cb.text() for cb in self.dialog.model_checkboxes if cb.isChecked()]
        self.assertEqual(len(selected), 2)
        self.assertIn(self.models[0], selected)
        self.assertIn(self.models[1], selected)
    
    def test_download_progress_visibility(self):
        """Test download progress UI visibility"""
        # Initially hidden
        self.assertFalse(self.dialog.progress_bar.isVisible())
        
        # Select a model and start download
        self.dialog.model_checkboxes[0].setChecked(True)
        
        with patch('main_app.QMessageBox.warning'):
            self.dialog.start_download()
            
            # Progress bar should be visible after starting download
            self.assertTrue(self.dialog.progress_bar.isVisible())
    
    def test_download_button_state(self):
        """Test download button state changes"""
        # Initially enabled
        self.assertTrue(self.dialog.download_btn.isEnabled())
        
        # Select a model and start download
        self.dialog.model_checkboxes[0].setChecked(True)
        
        with patch('main_app.QMessageBox.warning'):
            self.dialog.start_download()
            
            # Button should be disabled during download
            self.assertFalse(self.dialog.download_btn.isEnabled())


class TestAdminModeWidget(unittest.TestCase):
    """Test admin mode widget functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test application"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock ConfigManager to avoid file system dependencies
        with patch('main_app.ConfigManager'):
            self.widget = AdminModeWidget()
    
    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'widget'):
            self.widget.close()
    
    def test_widget_initialization(self):
        """Test widget initializes correctly"""
        self.assertIsNotNone(self.widget)
        self.assertFalse(self.widget.is_logged_in)
        self.assertIsNone(self.widget.user_info)
        self.assertIsNotNone(self.widget.content_stack)
    
    def test_initial_login_state(self):
        """Test initial login state display"""
        self.assertFalse(self.widget.is_logged_in)
        self.assertTrue(self.widget.login_btn.isVisible())
        self.assertFalse(self.widget.logout_btn.isVisible())
        self.assertIn("Not logged in", self.widget.status_label.text())
    
    def test_successful_login_handling(self):
        """Test successful login handling"""
        mock_user_info = {
            "email": "admin@test.com",
            "name": "Test Admin",
            "plan_type": "PRO",
            "max_clients": 20,
            "allowed_models": ["llama3_1_8b_fp16", "mistral_7b_int4"],
            "license_expires": "2024-12-31"
        }
        
        self.widget.on_login_successful(mock_user_info)
        
        # Check login state
        self.assertTrue(self.widget.is_logged_in)
        self.assertEqual(self.widget.user_info, mock_user_info)
        
        # Check UI updates
        self.assertFalse(self.widget.login_btn.isVisible())
        self.assertTrue(self.widget.logout_btn.isVisible())
        self.assertIn("Test Admin", self.widget.status_label.text())
    
    def test_license_display_update(self):
        """Test license information display update"""
        mock_user_info = {
            "plan_type": "PRO",
            "max_clients": 20,
            "license_expires": "2024-12-31",
            "allowed_models": ["llama3_1_8b_fp16", "mistral_7b_int4"]
        }
        
        self.widget.user_info = mock_user_info
        self.widget.update_license_display()
        
        # Check license info display
        self.assertEqual(self.widget.license_plan_label.text(), "PRO")
        self.assertEqual(self.widget.max_clients_label.text(), "20")
        self.assertEqual(self.widget.license_expires_label.text(), "2024-12-31")
        self.assertIn("llama3_1_8b_fp16", self.widget.models_list.text())
    
    def test_logout_functionality(self):
        """Test logout functionality"""
        # Set up logged in state
        mock_user_info = {"email": "admin@test.com", "name": "Test Admin"}
        self.widget.on_login_successful(mock_user_info)
        
        # Mock the confirmation dialog
        with patch('main_app.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            self.widget.logout()
            
            # Check logout state
            self.assertFalse(self.widget.is_logged_in)
            self.assertIsNone(self.widget.user_info)
            self.assertTrue(self.widget.login_btn.isVisible())
            self.assertFalse(self.widget.logout_btn.isVisible())
    
    def test_logout_cancellation(self):
        """Test logout cancellation"""
        # Set up logged in state
        mock_user_info = {"email": "admin@test.com", "name": "Test Admin"}
        self.widget.on_login_successful(mock_user_info)
        
        # Mock the confirmation dialog to return No
        with patch('main_app.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            self.widget.logout()
            
            # Should still be logged in
            self.assertTrue(self.widget.is_logged_in)
            self.assertEqual(self.widget.user_info, mock_user_info)
    
    def test_login_dialog_integration(self):
        """Test login dialog integration"""
        with patch('main_app.LoginDialog') as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog_class.return_value = mock_dialog
            
            self.widget.show_login_dialog()
            
            # Verify dialog was created and shown
            mock_dialog_class.assert_called_once_with(self.widget)
            mock_dialog.exec.assert_called_once()
    
    def test_model_download_dialog_integration(self):
        """Test model download dialog integration"""
        # Set up logged in state with models
        mock_user_info = {
            "allowed_models": ["llama3_1_8b_fp16", "mistral_7b_int4"]
        }
        self.widget.user_info = mock_user_info
        self.widget.is_logged_in = True
        
        with patch('main_app.ModelDownloadDialog') as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog_class.return_value = mock_dialog
            
            self.widget.download_models()
            
            # Verify dialog was created with correct models
            mock_dialog_class.assert_called_once_with(
                mock_user_info["allowed_models"], 
                self.widget
            )
            mock_dialog.exec.assert_called_once()
    
    def test_download_models_without_login(self):
        """Test download models action without login"""
        self.widget.is_logged_in = False
        
        with patch('main_app.QMessageBox.warning') as mock_warning:
            self.widget.download_models()
            mock_warning.assert_called_once()
    
    def test_download_models_without_allowed_models(self):
        """Test download models action without allowed models"""
        self.widget.is_logged_in = True
        self.widget.user_info = {"allowed_models": []}
        
        with patch('main_app.QMessageBox.information') as mock_info:
            self.widget.download_models()
            mock_info.assert_called_once()


class TestAdminInterfaceIntegration(unittest.TestCase):
    """Integration tests for admin interface components"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test application"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def test_complete_login_flow(self):
        """Test complete login flow from dialog to widget"""
        with patch('main_app.ConfigManager'):
            widget = AdminModeWidget()
            
            # Mock successful login
            mock_user_info = {
                "email": "admin@test.com",
                "name": "Test Admin",
                "plan_type": "PRO",
                "max_clients": 20,
                "allowed_models": ["llama3_1_8b_fp16"],
                "license_expires": "2024-12-31"
            }
            
            # Simulate login dialog success
            widget.on_login_successful(mock_user_info)
            
            # Verify complete state
            self.assertTrue(widget.is_logged_in)
            self.assertEqual(widget.user_info, mock_user_info)
            self.assertEqual(widget.license_plan_label.text(), "PRO")
            
            widget.close()
    
    def test_model_download_workflow(self):
        """Test complete model download workflow"""
        models = ["llama3_1_8b_fp16", "mistral_7b_int4"]
        dialog = ModelDownloadDialog(models)
        
        # Select models
        dialog.model_checkboxes[0].setChecked(True)
        
        # Mock download process
        with patch.object(dialog, 'simulate_download') as mock_simulate:
            dialog.start_download()
            
            # Verify download was initiated
            mock_simulate.assert_called_once()
            self.assertEqual(dialog.selected_models, [models[0]])
            self.assertFalse(dialog.download_btn.isEnabled())
        
        dialog.close()
    
    def test_requirements_compliance(self):
        """Test compliance with specific requirements"""
        # Requirement 2.1: Login/logout interface with backend authentication
        login_dialog = LoginDialog()
        self.assertIsNotNone(login_dialog.email_input)
        self.assertIsNotNone(login_dialog.password_input)
        self.assertTrue(hasattr(login_dialog, 'attempt_login'))
        login_dialog.close()
        
        # Requirement 8.2: License status display and management interface
        with patch('main_app.ConfigManager'):
            admin_widget = AdminModeWidget()
            self.assertTrue(hasattr(admin_widget, 'license_plan_label'))
            self.assertTrue(hasattr(admin_widget, 'license_expires_label'))
            self.assertTrue(hasattr(admin_widget, 'max_clients_label'))
            admin_widget.close()
        
        # Model management interface with download progress
        models = ["test_model"]
        download_dialog = ModelDownloadDialog(models)
        self.assertIsNotNone(download_dialog.progress_bar)
        self.assertTrue(hasattr(download_dialog, 'start_download'))
        download_dialog.close()


if __name__ == '__main__':
    # Create test application if needed
    if not QApplication.instance():
        app = QApplication([])
    
    # Run tests
    unittest.main(verbosity=2)