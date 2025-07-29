"""
Unit tests for main application entry point with mode selection

Tests cover:
- GUI initialization
- Mode selection dialog functionality
- Persistent mode storage
- Admin/Client mode switching
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
from PyQt6.QtCore import QSettings
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt

# Import modules to test
from main_app import (
    TikTrueApplication, MainWindow, ModeSelectionDialog,
    AdminModeWidget, ClientModeWidget
)


class TestModeSelectionDialog(unittest.TestCase):
    """Test mode selection dialog functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test application"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        self.dialog = ModeSelectionDialog()
    
    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'dialog'):
            self.dialog.close()
    
    def test_dialog_initialization(self):
        """Test dialog initializes correctly"""
        self.assertIsNotNone(self.dialog)
        self.assertEqual(self.dialog.windowTitle(), "TikTrue - Mode Selection")
        self.assertTrue(self.dialog.isModal())
        self.assertIsNone(self.dialog.selected_mode)
        self.assertFalse(self.dialog.ok_button.isEnabled())
    
    def test_admin_mode_selection(self):
        """Test admin mode selection"""
        # Simulate clicking admin radio button
        self.dialog.admin_radio.setChecked(True)
        
        # Verify mode is set correctly
        self.assertEqual(self.dialog.selected_mode, "admin")
        self.assertTrue(self.dialog.ok_button.isEnabled())
        self.assertTrue(self.dialog.admin_radio.isChecked())
        self.assertFalse(self.dialog.client_radio.isChecked())
    
    def test_client_mode_selection(self):
        """Test client mode selection"""
        # Simulate clicking client radio button
        self.dialog.client_radio.setChecked(True)
        
        # Verify mode is set correctly
        self.assertEqual(self.dialog.selected_mode, "client")
        self.assertTrue(self.dialog.ok_button.isEnabled())
        self.assertTrue(self.dialog.client_radio.isChecked())
        self.assertFalse(self.dialog.admin_radio.isChecked())
    
    def test_mode_switching(self):
        """Test switching between modes"""
        # Start with admin mode
        self.dialog.admin_radio.setChecked(True)
        self.assertEqual(self.dialog.selected_mode, "admin")
        
        # Switch to client mode
        self.dialog.client_radio.setChecked(True)
        self.assertEqual(self.dialog.selected_mode, "client")
        self.assertFalse(self.dialog.admin_radio.isChecked())
    
    def test_remember_choice_default(self):
        """Test remember choice is checked by default"""
        self.assertTrue(self.dialog.should_remember_choice())
    
    def test_get_selected_mode(self):
        """Test getting selected mode"""
        # No selection initially
        self.assertIsNone(self.dialog.get_selected_mode())
        
        # Select admin mode
        self.dialog.admin_radio.setChecked(True)
        self.assertEqual(self.dialog.get_selected_mode(), "admin")
        
        # Select client mode
        self.dialog.client_radio.setChecked(True)
        self.assertEqual(self.dialog.get_selected_mode(), "client")


class TestMainWindow(unittest.TestCase):
    """Test main window functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test application"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary settings for testing
        self.temp_dir = tempfile.mkdtemp()
        self.settings_file = os.path.join(self.temp_dir, "test_settings.ini")
        
        # Mock QSettings to use temporary file
        self.settings_patcher = patch('main_app.QSettings')
        self.mock_settings_class = self.settings_patcher.start()
        self.mock_settings = Mock()
        self.mock_settings_class.return_value = self.mock_settings
        
        # Mock ConfigManager
        self.config_patcher = patch('main_app.ConfigManager')
        self.mock_config_manager = self.config_patcher.start()
        
        # Create main window
        self.window = MainWindow()
    
    def tearDown(self):
        """Clean up after tests"""
        self.settings_patcher.stop()
        self.config_patcher.stop()
        
        if hasattr(self, 'window'):
            self.window.close()
        
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_window_initialization(self):
        """Test main window initializes correctly"""
        self.assertIsNotNone(self.window)
        self.assertEqual(self.window.windowTitle(), "TikTrue - Distributed LLM Platform")
        self.assertIsNotNone(self.window.content_stack)
        self.assertIsNotNone(self.window.admin_widget)
        self.assertIsNotNone(self.window.client_widget)
        self.assertIsNone(self.window.current_mode)
    
    def test_set_admin_mode(self):
        """Test setting admin mode"""
        self.window.set_mode("admin")
        
        self.assertEqual(self.window.current_mode, "admin")
        self.assertEqual(self.window.windowTitle(), "TikTrue - Admin Mode")
        self.assertEqual(
            self.window.content_stack.currentWidget(), 
            self.window.admin_widget
        )
    
    def test_set_client_mode(self):
        """Test setting client mode"""
        self.window.set_mode("client")
        
        self.assertEqual(self.window.current_mode, "client")
        self.assertEqual(self.window.windowTitle(), "TikTrue - Client Mode")
        self.assertEqual(
            self.window.content_stack.currentWidget(), 
            self.window.client_widget
        )
    
    @patch('main_app.ModeSelectionDialog')
    def test_mode_selection_with_stored_mode(self, mock_dialog_class):
        """Test mode selection when mode is already stored"""
        # Mock stored mode
        self.mock_settings.value.return_value = "admin"
        
        # Create new window to trigger mode check
        window = MainWindow()
        
        # Verify stored mode is used
        self.assertEqual(window.current_mode, "admin")
        # Dialog should not be shown
        mock_dialog_class.assert_not_called()
        
        window.close()
    
    @patch('main_app.ModeSelectionDialog')
    def test_mode_selection_without_stored_mode(self, mock_dialog_class):
        """Test mode selection when no mode is stored"""
        # Mock no stored mode
        self.mock_settings.value.return_value = None
        
        # Mock dialog
        mock_dialog = Mock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.get_selected_mode.return_value = "client"
        mock_dialog.should_remember_choice.return_value = True
        mock_dialog_class.return_value = mock_dialog
        
        # Create new window to trigger mode selection
        window = MainWindow()
        
        # Verify dialog was shown
        mock_dialog_class.assert_called_once()
        mock_dialog.exec.assert_called_once()
        
        # Verify mode was set and stored
        self.assertEqual(window.current_mode, "client")
        self.mock_settings.setValue.assert_called_with("selected_mode", "client")
        
        window.close()
    
    def test_persistent_mode_storage(self):
        """Test that mode selection is stored persistently"""
        # Mock dialog to return admin mode with remember checked
        with patch('main_app.ModeSelectionDialog') as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_selected_mode.return_value = "admin"
            mock_dialog.should_remember_choice.return_value = True
            mock_dialog_class.return_value = mock_dialog
            
            # Show mode selection
            self.window.show_mode_selection()
            
            # Verify mode was stored
            self.mock_settings.setValue.assert_called_with("selected_mode", "admin")
    
    def test_mode_not_stored_when_remember_unchecked(self):
        """Test that mode is not stored when remember is unchecked"""
        # Mock dialog to return client mode without remember
        with patch('main_app.ModeSelectionDialog') as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_selected_mode.return_value = "client"
            mock_dialog.should_remember_choice.return_value = False
            mock_dialog_class.return_value = mock_dialog
            
            # Show mode selection
            self.window.show_mode_selection()
            
            # Verify mode was not stored
            self.mock_settings.setValue.assert_not_called()
            # But mode should still be set
            self.assertEqual(self.window.current_mode, "client")


class TestModeWidgets(unittest.TestCase):
    """Test mode-specific widgets"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test application"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def test_admin_widget_initialization(self):
        """Test admin widget initializes correctly"""
        widget = AdminModeWidget()
        
        self.assertIsNotNone(widget)
        self.assertIsNotNone(widget.layout())
        
        widget.close()
    
    def test_client_widget_initialization(self):
        """Test client widget initializes correctly"""
        widget = ClientModeWidget()
        
        self.assertIsNotNone(widget)
        self.assertIsNotNone(widget.layout())
        
        widget.close()


class TestTikTrueApplication(unittest.TestCase):
    """Test main application class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock sys.argv for testing
        self.original_argv = sys.argv
        sys.argv = ['test_app']
    
    def tearDown(self):
        """Clean up after tests"""
        sys.argv = self.original_argv
    
    @patch('main_app.logging')
    def test_application_initialization(self, mock_logging):
        """Test application initializes correctly"""
        app = TikTrueApplication(['test_app'])
        
        self.assertEqual(app.applicationName(), "TikTrue")
        self.assertEqual(app.applicationVersion(), "1.0.0")
        self.assertEqual(app.organizationName(), "TikTrue")
        self.assertEqual(app.organizationDomain(), "tiktrue.com")
    
    @patch('main_app.MainWindow')
    @patch('main_app.logging')
    def test_create_main_window_success(self, mock_logging, mock_main_window):
        """Test successful main window creation"""
        app = TikTrueApplication(['test_app'])
        mock_window = Mock()
        mock_main_window.return_value = mock_window
        
        result = app.create_main_window()
        
        self.assertEqual(result, mock_window)
        self.assertEqual(app.main_window, mock_window)
    
    @patch('main_app.MainWindow')
    @patch('main_app.QMessageBox')
    @patch('main_app.logging')
    @patch('sys.exit')
    def test_create_main_window_failure(self, mock_exit, mock_logging, mock_msgbox, mock_main_window):
        """Test main window creation failure handling"""
        app = TikTrueApplication(['test_app'])
        mock_main_window.side_effect = Exception("Test error")
        
        app.create_main_window()
        
        # Verify error handling
        mock_msgbox.critical.assert_called_once()
        mock_exit.assert_called_once_with(1)


class TestModeSelectionIntegration(unittest.TestCase):
    """Integration tests for mode selection workflow"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test application"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock settings
        self.settings_patcher = patch('main_app.QSettings')
        self.mock_settings_class = self.settings_patcher.start()
        self.mock_settings = Mock()
        self.mock_settings_class.return_value = self.mock_settings
        
        # Mock config manager
        self.config_patcher = patch('main_app.ConfigManager')
        self.mock_config_manager = self.config_patcher.start()
    
    def tearDown(self):
        """Clean up after tests"""
        self.settings_patcher.stop()
        self.config_patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_first_run_mode_selection_workflow(self):
        """Test complete first-run mode selection workflow"""
        # Mock no stored mode (first run)
        self.mock_settings.value.return_value = None
        
        with patch('main_app.ModeSelectionDialog') as mock_dialog_class:
            # Mock user selecting admin mode with remember
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_selected_mode.return_value = "admin"
            mock_dialog.should_remember_choice.return_value = True
            mock_dialog_class.return_value = mock_dialog
            
            # Create window (triggers mode selection)
            window = MainWindow()
            
            # Verify workflow
            mock_dialog_class.assert_called_once()
            mock_dialog.exec.assert_called_once()
            self.mock_settings.setValue.assert_called_with("selected_mode", "admin")
            self.assertEqual(window.current_mode, "admin")
            
            window.close()
    
    def test_subsequent_run_with_stored_mode(self):
        """Test subsequent run with stored mode"""
        # Mock stored admin mode
        self.mock_settings.value.return_value = "client"
        
        with patch('main_app.ModeSelectionDialog') as mock_dialog_class:
            # Create window
            window = MainWindow()
            
            # Verify no dialog shown, mode set from storage
            mock_dialog_class.assert_not_called()
            self.assertEqual(window.current_mode, "client")
            
            window.close()
    
    def test_mode_change_workflow(self):
        """Test changing mode after initial selection"""
        # Start with stored admin mode
        self.mock_settings.value.return_value = "admin"
        window = MainWindow()
        self.assertEqual(window.current_mode, "admin")
        
        # Mock user changing to client mode
        with patch('main_app.ModeSelectionDialog') as mock_dialog_class:
            mock_dialog = Mock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.get_selected_mode.return_value = "client"
            mock_dialog.should_remember_choice.return_value = True
            mock_dialog_class.return_value = mock_dialog
            
            # Trigger mode change
            window.show_mode_selection()
            
            # Verify mode changed and stored
            self.assertEqual(window.current_mode, "client")
            self.mock_settings.setValue.assert_called_with("selected_mode", "client")
        
        window.close()


if __name__ == '__main__':
    # Create test application if needed
    if not QApplication.instance():
        app = QApplication([])
    
    # Run tests
    unittest.main(verbosity=2)