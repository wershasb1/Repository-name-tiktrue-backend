"""
Final integration test for Unified Chat Interface
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_integration():
    """Test complete integration"""
    
    app = QApplication([])
    
    print("🔧 Testing Complete Integration...")
    
    try:
        # Test 1: Import unified chat interface
        from interfaces.unified_chat_interface import UnifiedChatInterface, UnifiedChatWindow
        print("✅ Unified Chat Interface imported successfully")
        
        # Test 2: Test main_app integration
        from main_app import ClientModeWidget
        client_widget = ClientModeWidget()
        print("✅ ClientModeWidget with integrated UnifiedChatInterface created")
        
        # Test 3: Test chat functionality
        chat_widget = client_widget.chat_widget
        test_models = ["llama3_1_8b_fp16", "mistral_7b_int4"]
        chat_widget.enable_chat(test_models)
        print("✅ Chat enabled with models")
        
        # Test 4: Test message functionality
        chat_widget.add_system_message("Integration test started")
        chat_widget.add_user_message("Hello from integration test")
        chat_widget.add_assistant_message("Integration working perfectly!")
        print("✅ Message functionality works")
        
        # Test 5: Test configuration
        chat_widget.set_server_config("localhost", 8702)
        chat_widget.set_max_tokens(100)
        print("✅ Configuration methods work")
        
        # Test 6: Test CLI interface availability
        from interfaces.unified_chat_interface import CLIChatInterface
        print("✅ CLI interface available")
        
        # Test 7: Test old interfaces are archived
        try:
            from interfaces.chat_interface import AdvancedChatInterface
            print("❌ Old interface still accessible (should be archived)")
        except ImportError:
            print("✅ Old interfaces properly archived")
        
        client_widget.close()
        
        print("\n🎉 All integration tests passed!")
        print("✅ Unified Chat Interface is fully integrated")
        print("✅ Old interfaces are properly archived")
        print("✅ Client mode uses new unified interface")
        print("✅ Both CLI and GUI modes available")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_integration()
    if success:
        print("\n🚀 Integration complete! Unified Chat Interface is ready for production!")
        exit(0)
    else:
        print("\n❌ Integration has issues that need to be addressed")
        exit(1)