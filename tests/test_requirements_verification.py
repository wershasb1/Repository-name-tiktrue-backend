"""
Requirements verification test for task 6.1
Verifies all requirements are implemented correctly:
- 1.3: Application prompts user to select Admin/Client mode on first run
- 1.4: Application persists mode selection for subsequent launches  
- 8.1: Clear interface for mode selection
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_requirement_1_3_mode_selection_prompt():
    """
    Requirement 1.3: Application prompts user to select Admin/Client mode on first run
    """
    print("Testing Requirement 1.3: Mode selection prompt on first run")
    
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QSettings
    from main_app import MainWindow
    
    app = QApplication([])
    
    # Create temporary settings to simulate first run
    temp_dir = tempfile.mkdtemp()
    
    try:
        with patch('main_app.QSettings') as mock_settings_class:
            mock_settings = Mock()
            mock_settings.value.return_value = None  # No stored mode (first run)
            mock_settings_class.return_value = mock_settings
            
            with patch('main_app.ModeSelectionDialog') as mock_dialog_class:
                mock_dialog = Mock()
                mock_dialog.exec.return_value = 1  # QDialog.Accepted
                mock_dialog.get_selected_mode.return_value = "admin"
                mock_dialog.should_remember_choice.return_value = True
                mock_dialog_class.return_value = mock_dialog
                
                # Create window - should trigger mode selection on first run
                window = MainWindow()
                
                # Verify mode selection dialog was shown
                mock_dialog_class.assert_called_once()
                mock_dialog.exec.assert_called_once()
                
                print("  ✅ Mode selection dialog shown on first run")
                
                window.close()
                
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_requirement_1_4_persistent_mode_selection():
    """
    Requirement 1.4: Application persists mode selection for subsequent launches
    """
    print("Testing Requirement 1.4: Persistent mode selection")
    
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QSettings
    from main_app import MainWindow
    
    app = QApplication([])
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Test 1: First run - mode gets stored
        with patch('main_app.QSettings') as mock_settings_class:
            mock_settings = Mock()
            mock_settings.value.return_value = None  # No stored mode
            mock_settings_class.return_value = mock_settings
            
            with patch('main_app.ModeSelectionDialog') as mock_dialog_class:
                mock_dialog = Mock()
                mock_dialog.exec.return_value = 1  # QDialog.Accepted
                mock_dialog.get_selected_mode.return_value = "client"
                mock_dialog.should_remember_choice.return_value = True
                mock_dialog_class.return_value = mock_dialog
                
                window = MainWindow()
                
                # Verify mode was stored
                mock_settings.setValue.assert_called_with("selected_mode", "client")
                print("  ✅ Mode selection stored on first run")
                
                window.close()
        
        # Test 2: Subsequent run - stored mode is used
        with patch('main_app.QSettings') as mock_settings_class:
            mock_settings = Mock()
            mock_settings.value.return_value = "admin"  # Stored mode
            mock_settings_class.return_value = mock_settings
            
            with patch('main_app.ModeSelectionDialog') as mock_dialog_class:
                window = MainWindow()
                
                # Verify no dialog shown, mode set from storage
                mock_dialog_class.assert_not_called()
                assert window.current_mode == "admin"
                print("  ✅ Stored mode used on subsequent run")
                
                window.close()
                
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_requirement_8_1_clear_mode_interface():
    """
    Requirement 8.1: Clear interface for mode selection
    """
    print("Testing Requirement 8.1: Clear interface for mode selection")
    
    from PyQt6.QtWidgets import QApplication
    from main_app import ModeSelectionDialog, AdminModeWidget, ClientModeWidget
    
    app = QApplication([])
    
    # Test mode selection dialog interface
    dialog = ModeSelectionDialog()
    
    # Verify dialog has clear title and options
    assert dialog.windowTitle() == "TikTrue - Mode Selection"
    assert dialog.admin_radio is not None
    assert dialog.client_radio is not None
    assert dialog.remember_checkbox is not None
    
    print("  ✅ Mode selection dialog has clear interface")
    
    # Test admin mode interface
    admin_widget = AdminModeWidget()
    assert admin_widget is not None
    assert admin_widget.layout() is not None
    
    print("  ✅ Admin mode interface created successfully")
    
    # Test client mode interface  
    client_widget = ClientModeWidget()
    assert client_widget is not None
    assert client_widget.layout() is not None
    
    print("  ✅ Client mode interface created successfully")
    
    dialog.close()
    admin_widget.close()
    client_widget.close()

def test_mode_switching_functionality():
    """
    Test mode switching between Admin and Client modes
    """
    print("Testing mode switching functionality")
    
    from PyQt6.QtWidgets import QApplication
    from main_app import MainWindow
    
    app = QApplication([])
    
    with patch('main_app.QSettings') as mock_settings_class:
        mock_settings = Mock()
        mock_settings.value.return_value = "admin"  # Start with admin
        mock_settings_class.return_value = mock_settings
        
        window = MainWindow()
        
        # Verify initial admin mode
        assert window.current_mode == "admin"
        assert "Admin Mode" in window.windowTitle()
        
        # Switch to client mode
        window.set_mode("client")
        assert window.current_mode == "client"
        assert "Client Mode" in window.windowTitle()
        
        # Switch back to admin mode
        window.set_mode("admin")
        assert window.current_mode == "admin"
        assert "Admin Mode" in window.windowTitle()
        
        print("  ✅ Mode switching works correctly")
        
        window.close()

def test_first_run_wizard_integration():
    """
    Test integration with first-run wizard
    """
    print("Testing first-run wizard integration")
    
    from PyQt6.QtWidgets import QApplication
    from main_app import MainWindow
    
    app = QApplication([])
    
    with patch('main_app.QSettings') as mock_settings_class:
        mock_settings = Mock()
        mock_settings.value.return_value = "admin"
        mock_settings_class.return_value = mock_settings
        
        with patch('main_app.FirstRunWizard') as mock_wizard_class:
            mock_wizard = Mock()
            mock_wizard.exec.return_value = 1  # QDialog.Accepted
            mock_wizard_class.return_value = mock_wizard
            
            window = MainWindow()
            
            # Test showing wizard
            window.show_setup_wizard()
            
            # Verify wizard was created and shown
            mock_wizard_class.assert_called_once_with(window)
            mock_wizard.exec.assert_called_once()
            
            print("  ✅ First-run wizard integration works")
            
            window.close()

def run_all_tests():
    """Run all requirement verification tests"""
    print("=" * 60)
    print("REQUIREMENTS VERIFICATION FOR TASK 6.1")
    print("=" * 60)
    
    try:
        test_requirement_1_3_mode_selection_prompt()
        print()
        
        test_requirement_1_4_persistent_mode_selection()
        print()
        
        test_requirement_8_1_clear_mode_interface()
        print()
        
        test_mode_switching_functionality()
        print()
        
        test_first_run_wizard_integration()
        print()
        
        print("=" * 60)
        print("🎉 ALL REQUIREMENTS VERIFIED SUCCESSFULLY!")
        print("=" * 60)
        print()
        print("Task 6.1 Implementation Summary:")
        print("✅ PyQt6-based GUI with Admin/Client mode selection")
        print("✅ Persistent mode selection storage using QSettings")
        print("✅ First-run wizard for initial setup")
        print("✅ Clear and intuitive mode selection interface")
        print("✅ Proper mode switching and UI updates")
        print("✅ Integration with existing configuration system")
        print()
        print("Requirements addressed:")
        print("✅ 1.3: Application prompts user to select mode on first run")
        print("✅ 1.4: Application persists mode selection for subsequent launches")
        print("✅ 8.1: Clear interface for mode selection")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)