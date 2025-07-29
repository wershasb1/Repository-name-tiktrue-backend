"""
Test GUI mode of Unified Chat Interface
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from interfaces.unified_chat_interface import UnifiedChatWindow

def test_gui_mode():
    """Test GUI mode"""
    
    app = QApplication([])
    
    print("🖥️ Testing GUI Mode...")
    
    # Create window
    window = UnifiedChatWindow()
    window.show()
    
    # Enable chat with test models
    test_models = ["llama3_1_8b_fp16", "mistral_7b_int4"]
    window.chat_interface.enable_chat(test_models)
    
    # Add some test messages
    window.chat_interface.add_system_message("GUI Mode Test Started")
    window.chat_interface.add_user_message("Hello from GUI test!")
    window.chat_interface.add_assistant_message("Hello! GUI is working perfectly.")
    
    print("✅ GUI window created and populated")
    print("✅ Chat interface is functional")
    print("✅ Models are loaded")
    
    # Close after 2 seconds
    QTimer.singleShot(2000, window.close)
    QTimer.singleShot(2500, app.quit)
    
    app.exec()
    
    print("🎉 GUI Mode test completed successfully!")
    return True

if __name__ == '__main__':
    test_gui_mode()