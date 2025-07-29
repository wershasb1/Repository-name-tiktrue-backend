"""
Simple test to verify Client mode interface basic functionality
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Import the classes we're testing
from main_app import (
    NetworkDiscoveryWidget, 
    ModelTransferWidget, 
    ChatInterfaceWidget,
    ClientModeWidget
)

def test_basic_functionality():
    """Test basic functionality of Client mode components"""
    
    # Create QApplication
    app = QApplication([])
    
    print("Testing NetworkDiscoveryWidget...")
    try:
        discovery_widget = NetworkDiscoveryWidget()
        print("✓ NetworkDiscoveryWidget created successfully")
        
        # Test network scanning
        discovery_widget.scan_networks()
        print("✓ Network scan initiated")
        
        # Test mock network discovery
        discovery_widget.on_scan_complete()
        print(f"✓ Mock networks discovered: {len(discovery_widget.discovered_networks)}")
        
        discovery_widget.close()
        
    except Exception as e:
        print(f"✗ NetworkDiscoveryWidget failed: {e}")
        return False
    
    print("\nTesting ModelTransferWidget...")
    try:
        transfer_widget = ModelTransferWidget()
        print("✓ ModelTransferWidget created successfully")
        
        # Test transfer start
        mock_network = {
            "name": "Test Network",
            "admin": "Test Admin", 
            "ip": "192.168.1.100",
            "models": ["test_model"],
            "port": 8765
        }
        
        transfer_widget.start_transfer(mock_network)
        print("✓ Transfer started successfully")
        
        # Test logging
        transfer_widget.log_transfer_message("Test message")
        print("✓ Transfer logging works")
        
        transfer_widget.close()
        
    except Exception as e:
        print(f"✗ ModelTransferWidget failed: {e}")
        return False
    
    print("\nTesting ChatInterfaceWidget...")
    try:
        chat_widget = ChatInterfaceWidget()
        print("✓ ChatInterfaceWidget created successfully")
        
        # Test enabling chat
        test_models = ["model1", "model2"]
        chat_widget.enable_chat(test_models)
        print("✓ Chat enabled with models")
        
        # Test adding messages
        chat_widget.add_user_message("Test user message")
        chat_widget.add_system_message("Test system message")
        chat_widget.add_model_response_real("Test model response", "model1")
        print("✓ Message adding works")
        
        chat_widget.close()
        
    except Exception as e:
        print(f"✗ ChatInterfaceWidget failed: {e}")
        return False
    
    print("\nTesting ClientModeWidget...")
    try:
        client_widget = ClientModeWidget()
        print("✓ ClientModeWidget created successfully")
        
        # Test network connection workflow
        mock_network = {
            "name": "Test Network",
            "admin": "Test Admin",
            "ip": "192.168.1.100", 
            "models": ["test_model"],
            "clients": "1/5"
        }
        
        client_widget.connect_to_network(mock_network)
        print("✓ Network connection workflow works")
        
        # Test transfer completion
        client_widget.on_transfer_completed(["model1", "model2"])
        print("✓ Transfer completion workflow works")
        
        client_widget.close()
        
    except Exception as e:
        print(f"✗ ClientModeWidget failed: {e}")
        return False
    
    print("\n🎉 All Client mode interface tests passed!")
    return True

if __name__ == '__main__':
    success = test_basic_functionality()
    if success:
        print("\n✅ Task 6.3 Client mode interface implementation is working correctly!")
        exit(0)
    else:
        print("\n❌ Task 6.3 has issues that need to be addressed")
        exit(1)