"""
Demo script to showcase Client mode interface functionality
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from main_app import ClientModeWidget

def demo_client_mode():
    """Demonstrate Client mode interface functionality"""
    
    app = QApplication([])
    
    print("🚀 Starting Client Mode Interface Demo...")
    print("=" * 50)
    
    # Create client widget
    client_widget = ClientModeWidget()
    client_widget.show()
    
    print("✓ Client mode interface launched")
    print("✓ Network Discovery tab active")
    print("✓ Model Transfer tab ready")
    print("✓ Chat Interface tab ready")
    
    # Simulate network discovery
    print("\n🔍 Simulating network discovery...")
    client_widget.discovery_widget.on_scan_complete()
    networks = client_widget.discovery_widget.discovered_networks
    print(f"✓ Found {len(networks)} available networks:")
    
    for i, network in enumerate(networks, 1):
        print(f"  {i}. {network['name']} ({network['admin']}) - {network['ip']}")
        print(f"     Models: {', '.join(network['models'])}")
        print(f"     Clients: {network['clients']}")
    
    # Simulate network connection
    print(f"\n🔗 Simulating connection to '{networks[0]['name']}'...")
    client_widget.connect_to_network(networks[0])
    print("✓ Connection established")
    print("✓ Model transfer initiated")
    
    # Simulate transfer completion
    print("\n📦 Simulating model transfer completion...")
    client_widget.on_transfer_completed(networks[0]['models'])
    print("✓ Models transferred successfully")
    print("✓ Chat interface enabled")
    
    # Demonstrate chat functionality
    print("\n💬 Demonstrating chat functionality...")
    chat_widget = client_widget.chat_widget
    
    # Add sample conversation
    chat_widget.add_user_message("Hello! Can you help me with a Python question?")
    chat_widget.add_model_response_real(
        "Hello! I'd be happy to help you with Python. What specific question do you have?", 
        networks[0]['models'][0]
    )
    
    chat_widget.add_user_message("How do I create a list comprehension?")
    chat_widget.add_model_response_real(
        "List comprehensions in Python follow this syntax: [expression for item in iterable if condition]. "
        "For example: squares = [x**2 for x in range(10)] creates a list of squares from 0 to 81.",
        networks[0]['models'][0]
    )
    
    print("✓ Sample conversation added to chat")
    
    print("\n" + "=" * 50)
    print("🎉 Client Mode Interface Demo Complete!")
    print("\nFeatures demonstrated:")
    print("✓ Network discovery and selection")
    print("✓ Connection workflow")
    print("✓ Model transfer progress")
    print("✓ Chat interface with model interaction")
    print("✓ Tab-based navigation")
    print("✓ Real-time status updates")
    
    print(f"\nClient widget is running. Close the window to exit.")
    
    # Keep the application running
    return app.exec()

if __name__ == '__main__':
    demo_client_mode()