"""
Test script for Unified Chat Interface
"""

import sys
import os
from PyQt6.QtWidgets import QApplication

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from interfaces.unified_chat_interface import UnifiedChatInterface, UnifiedChatWindow

def test_unified_chat():
    """Test unified chat interface"""
    
    app = QApplication([])
    
    print("🧪 Testing Unified Chat Interface...")
    
    try:
        # Test basic widget creation
        chat_widget = UnifiedChatInterface()
        print("✅ UnifiedChatInterface created successfully")
        
        # Test enabling chat
        test_models = ["llama3_1_8b_fp16", "mistral_7b_int4"]
        chat_widget.enable_chat(test_models)
        print("✅ Chat enabled with models")
        
        # Test adding messages
        chat_widget.add_user_message("Hello, this is a test message")
        chat_widget.add_system_message("System message test")
        chat_widget.add_assistant_message("Assistant response test")
        print("✅ Message adding works")
        
        # Test main window
        window = UnifiedChatWindow()
        print("✅ UnifiedChatWindow created successfully")
        
        # Test configuration
        chat_widget.set_server_config("localhost", 8702)
        chat_widget.set_max_tokens(50)
        print("✅ Configuration methods work")
        
        # Test clearing
        chat_widget.clear_chat()
        print("✅ Chat clearing works")
        
        chat_widget.close()
        window.close()
        
        print("\n🎉 All Unified Chat Interface tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == '__main__':
    success = test_unified_chat()
    if success:
        print("\n✅ Unified Chat Interface is ready for use!")
        exit(0)
    else:
        print("\n❌ Unified Chat Interface has issues")
        exit(1)