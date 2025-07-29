"""
Simple test script to verify mode selection functionality
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_mode_selection_dialog():
    """Test mode selection dialog without GUI"""
    from main_app import ModeSelectionDialog
    
    # Test dialog creation
    dialog = ModeSelectionDialog()
    
    # Test initial state
    assert dialog.selected_mode is None
    assert dialog.should_remember_choice() == True
    
    # Test admin mode selection
    dialog.admin_radio.setChecked(True)
    assert dialog.get_selected_mode() == "admin"
    
    # Test client mode selection
    dialog.client_radio.setChecked(True)
    assert dialog.get_selected_mode() == "client"
    
    print("✅ Mode selection dialog tests passed")

def test_mode_widgets():
    """Test mode-specific widgets"""
    from main_app import AdminModeWidget, ClientModeWidget
    
    # Test admin widget
    admin_widget = AdminModeWidget()
    assert admin_widget is not None
    
    # Test client widget
    client_widget = ClientModeWidget()
    assert client_widget is not None
    
    print("✅ Mode widgets tests passed")

def test_persistent_storage():
    """Test persistent storage functionality"""
    from PyQt6.QtCore import QSettings
    
    # Create test settings
    settings = QSettings("TikTrue", "TestApp")
    
    # Test storing mode
    settings.setValue("selected_mode", "admin")
    stored_mode = settings.value("selected_mode")
    assert stored_mode == "admin"
    
    # Test changing mode
    settings.setValue("selected_mode", "client")
    stored_mode = settings.value("selected_mode")
    assert stored_mode == "client"
    
    # Clean up
    settings.remove("selected_mode")
    
    print("✅ Persistent storage tests passed")

if __name__ == "__main__":
    print("Running mode selection functionality tests...")
    
    try:
        # Import PyQt6 to initialize
        from PyQt6.QtWidgets import QApplication
        app = QApplication([])
        
        test_mode_selection_dialog()
        test_mode_widgets()
        test_persistent_storage()
        
        print("\n🎉 All tests passed successfully!")
        print("Mode selection functionality is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)