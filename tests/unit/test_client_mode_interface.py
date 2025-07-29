"""
Unit tests for Client mode interface components
Tests network discovery, model transfer, and chat interface functionality

Requirements addressed:
- 3.1: Client mode interface for network discovery and selection
- 3.2: Network discovery and connection workflow  
- 3.3: Connection request and approval workflow
- 3.4: Model transfer progress display
- 8.3: Chat interface for model interaction
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import the classes we're testing
from main_app import (
    ClientModeWidget, 
    NetworkDiscoveryWidget, 
    ModelTransferWidget, 
    ChatInterfaceWidget
)


class TestNetworkDiscoveryWidget(unittest.TestCase):
    """Test cases for NetworkDiscoveryWidget"""
    
    @classmethod
    def setUpClass(cls):
        """Set up QApplication for testing"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        self.widget = NetworkDiscoveryWidget()
    
    def tearDown(self):
        """Clean up after tests"""
        self.widget.close()
    
    def test_widget_initialization(self):
        """Test widget initializes correctly"""
        self.assertIsNotNone(self.widget)
        self.assertEqual(len(self.widget.discovered_networks), 0)
        self.assertIsNotNone(self.widget.scan_btn)
        self.assertIsNotNone(self.widget.networks_list)
        self.assertIsNotNone(self.widget.connect_btn)
        self.assertFalse(self.widget.connect_btn.isEnabled())
    
    def test_scan_networks_button_state(self):
        """Test scan button state changes during scan"""
        # Initial state
        self.assertTrue(self.widget.scan_btn.isEnabled())
        self.assertEqual(self.widget.scan_btn.text(), "🔍 Scan for Networks")
        
        # Start scan
        self.widget.scan_networks()
        
        # Button should be disabled during scan
        self.assertFalse(self.widget.scan_btn.isEnabled())
        self.assertEqual(self.widget.scan_btn.text(), "🔄 Scanning...")
    
    def test_mock_network_discovery(self):
        """Test mock network discovery functionality"""
        # Trigger scan completion
        self.widget.on_scan_complete()
        
        # Should have discovered mock networks
        self.assertGreater(len(self.widget.discovered_networks), 0)
        self.assertTrue(self.widget.scan_btn.isEnabled())
        self.assertEqual(self.widget.scan_btn.text(), "🔍 Scan for Networks")
        
        # Check network list is populated
        self.assertGreater(self.widget.networks_list.count(), 0)
    
    def test_network_selection(self):
        """Test network selection functionality"""
        # Add mock networks
        self.widget.on_scan_complete()
        
        # Select first network
        self.widget.networks_list.setCurrentRow(0)
        
        # Connect button should be enabled
        self.assertTrue(self.widget.connect_btn.isEnabled())
    
    def test_network_connection_signal(self):
        """Test network selection emits correct signal"""
        # Add mock networks
        self.widget.on_scan_complete()
        
        # Mock signal handler
        signal_received = Mock()
        self.widget.network_selected.connect(signal_received)
        
        # Select and connect to network
        self.widget.networks_list.setCurrentRow(0)
        self.widget.connect_to_selected_network()
        
        # Signal should be emitted
        signal_received.assert_called_once()
    
    def test_auto_scan_toggle(self):
        """Test auto-scan functionality"""
        # Enable auto-scan
        self.widget.toggle_auto_scan(True)
        self.assertTrue(self.widget.auto_scan_timer.isActive())
        
        # Disable auto-scan
        self.widget.toggle_auto_scan(False)
        self.assertFalse(self.widget.auto_scan_timer.isActive())
    
    @patch('main_app.NetworkDiscovery')
    def test_real_network_discovery_integration(self, mock_network_discovery):
        """Test integration with real network discovery module"""
        # Mock network discovery
        mock_instance = Mock()
        mock_network_discovery.return_value = mock_instance
        mock_instance.discover_admin_nodes.return_value = [
            {
                "network_name": "Test Network",
                "admin_name": "Test Admin",
                "ip_address": "192.168.1.100",
                "available_models": ["test_model"],
                "current_clients": 1,
                "max_clients": 5,
                "status": "Active",
                "port": 8765,
                "node_id": "test_node"
            }
        ]
        
        # Create widget with mocked discovery
        widget = NetworkDiscoveryWidget()
        
        # Should have network discovery initialized
        self.assertIsNotNone(widget.network_discovery)


class TestModelTransferWidget(unittest.TestCase):
    """Test cases for ModelTransferWidget"""
    
    @classmethod
    def setUpClass(cls):
        """Set up QApplication for testing"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        self.widget = ModelTransferWidget()
        self.mock_network = {
            "name": "Test Network",
            "admin": "Test Admin",
            "ip": "192.168.1.100",
            "models": ["test_model_1", "test_model_2"],
            "port": 8765,
            "node_id": "test_node"
        }
    
    def tearDown(self):
        """Clean up after tests"""
        self.widget.close()
    
    def test_widget_initialization(self):
        """Test widget initializes correctly"""
        self.assertIsNotNone(self.widget)
        self.assertIsNotNone(self.widget.status_label)
        self.assertIsNotNone(self.widget.progress_bar)
        self.assertIsNotNone(self.widget.details_text)
        self.assertFalse(self.widget.progress_bar.isVisible())
    
    def test_start_transfer_ui_changes(self):
        """Test UI changes when transfer starts"""
        self.widget.start_transfer(self.mock_network)
        
        # Progress bar should be visible
        self.assertTrue(self.widget.progress_bar.isVisible())
        self.assertEqual(self.widget.progress_bar.value(), 0)
        
        # Status should be updated
        self.assertIn("Test Network", self.widget.status_label.text())
    
    def test_transfer_progress_simulation(self):
        """Test simulated transfer progress"""
        self.widget.start_transfer(self.mock_network)
        
        # Should start with fallback simulation
        self.assertIsNotNone(self.widget.transfer_timer)
        self.assertTrue(self.widget.transfer_timer.isActive())
    
    def test_transfer_completion_signal(self):
        """Test transfer completion signal emission"""
        # Mock signal handler
        signal_received = Mock()
        self.widget.transfer_completed.connect(signal_received)
        
        # Complete transfer
        self.widget.current_network = self.mock_network
        self.widget.on_real_transfer_complete()
        
        # Signal should be emitted with models list
        signal_received.assert_called_once_with(self.mock_network['models'])
    
    def test_log_transfer_message(self):
        """Test transfer logging functionality"""
        test_message = "Test transfer message"
        initial_text = self.widget.details_text.toPlainText()
        
        self.widget.log_transfer_message(test_message)
        
        updated_text = self.widget.details_text.toPlainText()
        self.assertIn(test_message, updated_text)
        self.assertNotEqual(initial_text, updated_text)
    
    @patch('main_app.SecureBlockTransfer')
    def test_secure_transfer_integration(self, mock_secure_transfer):
        """Test integration with secure transfer module"""
        # Mock secure transfer
        mock_instance = Mock()
        mock_secure_transfer.return_value = mock_instance
        
        # Create widget with mocked transfer
        widget = ModelTransferWidget()
        
        # Should have secure transfer initialized
        self.assertIsNotNone(widget.secure_transfer)


class TestChatInterfaceWidget(unittest.TestCase):
    """Test cases for ChatInterfaceWidget"""
    
    @classmethod
    def setUpClass(cls):
        """Set up QApplication for testing"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        self.widget = ChatInterfaceWidget()
        self.test_models = ["test_model_1", "test_model_2"]
    
    def tearDown(self):
        """Clean up after tests"""
        self.widget.close()
    
    def test_widget_initialization(self):
        """Test widget initializes correctly"""
        self.assertIsNotNone(self.widget)
        self.assertIsNotNone(self.widget.chat_display)
        self.assertIsNotNone(self.widget.message_input)
        self.assertIsNotNone(self.widget.send_btn)
        self.assertIsNotNone(self.widget.model_combo)
        
        # Initially disabled
        self.assertFalse(self.widget.message_input.isEnabled())
        self.assertFalse(self.widget.send_btn.isEnabled())
        self.assertFalse(self.widget.model_combo.isEnabled())
    
    def test_enable_chat_functionality(self):
        """Test enabling chat with available models"""
        self.widget.enable_chat(self.test_models)
        
        # Should be enabled after models are available
        self.assertTrue(self.widget.message_input.isEnabled())
        self.assertTrue(self.widget.send_btn.isEnabled())
        self.assertTrue(self.widget.model_combo.isEnabled())
        
        # Models should be in combo box
        combo_items = [self.widget.model_combo.itemText(i) 
                      for i in range(self.widget.model_combo.count())]
        for model in self.test_models:
            self.assertIn(model, combo_items)
    
    def test_send_message_validation(self):
        """Test message sending validation"""
        # Enable chat first
        self.widget.enable_chat(self.test_models)
        
        # Try to send empty message
        self.widget.message_input.setText("")
        initial_text = self.widget.chat_display.toPlainText()
        
        self.widget.send_message()
        
        # Should not add message for empty input
        self.assertEqual(initial_text, self.widget.chat_display.toPlainText())
    
    def test_add_user_message(self):
        """Test adding user message to chat"""
        test_message = "Hello, this is a test message"
        initial_text = self.widget.chat_display.toPlainText()
        
        self.widget.add_user_message(test_message)
        
        updated_text = self.widget.chat_display.toPlainText()
        self.assertNotEqual(initial_text, updated_text)
        self.assertIn(test_message, updated_text)
    
    def test_add_system_message(self):
        """Test adding system message to chat"""
        test_message = "System test message"
        initial_text = self.widget.chat_display.toPlainText()
        
        self.widget.add_system_message(test_message)
        
        updated_text = self.widget.chat_display.toPlainText()
        self.assertNotEqual(initial_text, updated_text)
        self.assertIn(test_message, updated_text)
    
    def test_add_model_response(self):
        """Test adding model response to chat"""
        test_response = "This is a test model response"
        test_model = "test_model"
        initial_text = self.widget.chat_display.toPlainText()
        
        self.widget.add_model_response_real(test_response, test_model)
        
        updated_text = self.widget.chat_display.toPlainText()
        self.assertNotEqual(initial_text, updated_text)
        self.assertIn(test_response, updated_text)
        self.assertIn(test_model, updated_text)
    
    def test_conversation_history(self):
        """Test conversation history tracking"""
        self.assertEqual(len(self.widget.conversation_history), 0)
        
        # Add some messages
        self.widget.add_user_message("User message")
        self.widget.add_model_response_real("Model response", "test_model")
        
        # Chat display should contain both messages
        chat_text = self.widget.chat_display.toPlainText()
        self.assertIn("User message", chat_text)
        self.assertIn("Model response", chat_text)
    
    @patch('main_app.ModelNode')
    def test_model_node_integration(self, mock_model_node):
        """Test integration with model node for inference"""
        # Mock model node
        mock_instance = Mock()
        mock_model_node.return_value = mock_instance
        
        # Create widget with mocked model node
        widget = ChatInterfaceWidget()
        
        # Should have model node initialized
        self.assertIsNotNone(widget.model_node)


class TestClientModeWidget(unittest.TestCase):
    """Test cases for ClientModeWidget integration"""
    
    @classmethod
    def setUpClass(cls):
        """Set up QApplication for testing"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        self.widget = ClientModeWidget()
    
    def tearDown(self):
        """Clean up after tests"""
        self.widget.close()
    
    def test_widget_initialization(self):
        """Test client mode widget initializes correctly"""
        self.assertIsNotNone(self.widget)
        self.assertIsNotNone(self.widget.discovery_widget)
        self.assertIsNotNone(self.widget.transfer_widget)
        self.assertIsNotNone(self.widget.chat_widget)
        self.assertIsNotNone(self.widget.tab_widget)
        self.assertIsNone(self.widget.connected_network)
    
    def test_tab_structure(self):
        """Test tab widget structure"""
        # Should have 3 tabs
        self.assertEqual(self.widget.tab_widget.count(), 3)
        
        # Check tab titles
        tab_titles = [self.widget.tab_widget.tabText(i) 
                     for i in range(self.widget.tab_widget.count())]
        self.assertIn("Network Discovery", tab_titles[0])
        self.assertIn("Model Transfer", tab_titles[1])
        self.assertIn("Chat Interface", tab_titles[2])
    
    def test_network_selection_workflow(self):
        """Test network selection workflow"""
        mock_network = {
            "name": "Test Network",
            "admin": "Test Admin",
            "ip": "192.168.1.100",
            "models": ["test_model"],
            "clients": "1/5"
        }
        
        # Simulate network selection
        self.widget.on_network_selected(mock_network)
        
        # Should show confirmation dialog (mocked in real test)
        # For unit test, we can test the connect_to_network method directly
        self.widget.connect_to_network(mock_network)
        
        # Should set connected network
        self.assertEqual(self.widget.connected_network, mock_network)
    
    def test_transfer_completion_workflow(self):
        """Test transfer completion workflow"""
        test_models = ["model1", "model2"]
        
        # Mock transfer completion
        self.widget.on_transfer_completed(test_models)
        
        # Should enable chat interface
        self.assertTrue(self.widget.chat_widget.message_input.isEnabled())
        self.assertTrue(self.widget.chat_widget.send_btn.isEnabled())
    
    def test_connection_status_updates(self):
        """Test connection status updates"""
        mock_network = {
            "name": "Test Network",
            "admin": "Test Admin",
            "ip": "192.168.1.100",
            "models": ["test_model"],
            "clients": "1/5"
        }
        
        # Initial status
        self.assertEqual(self.widget.connection_status.text(), "Not Connected")
        
        # Connect to network
        self.widget.connect_to_network(mock_network)
        
        # Status should be updated
        self.assertIn("Test Network", self.widget.connection_status.text())


class TestClientModeIntegration(unittest.TestCase):
    """Integration tests for Client mode components"""
    
    @classmethod
    def setUpClass(cls):
        """Set up QApplication for testing"""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()
    
    def test_end_to_end_workflow(self):
        """Test complete client mode workflow"""
        client_widget = ClientModeWidget()
        
        # 1. Network discovery
        client_widget.discovery_widget.on_scan_complete()
        networks = client_widget.discovery_widget.discovered_networks
        self.assertGreater(len(networks), 0)
        
        # 2. Network selection
        test_network = networks[0]
        client_widget.connect_to_network(test_network)
        self.assertEqual(client_widget.connected_network, test_network)
        
        # 3. Model transfer completion
        client_widget.on_transfer_completed(test_network['models'])
        
        # 4. Chat should be enabled
        self.assertTrue(client_widget.chat_widget.message_input.isEnabled())
        
        client_widget.close()
    
    def test_signal_connections(self):
        """Test signal connections between components"""
        client_widget = ClientModeWidget()
        
        # Test network selection signal
        mock_handler = Mock()
        client_widget.discovery_widget.network_selected.connect(mock_handler)
        
        # Trigger network selection
        client_widget.discovery_widget.on_scan_complete()
        client_widget.discovery_widget.networks_list.setCurrentRow(0)
        client_widget.discovery_widget.connect_to_selected_network()
        
        mock_handler.assert_called_once()
        
        # Test transfer completion signal
        transfer_handler = Mock()
        client_widget.transfer_widget.transfer_completed.connect(transfer_handler)
        
        # Trigger transfer completion
        test_models = ["test_model"]
        client_widget.transfer_widget.current_network = {"models": test_models}
        client_widget.transfer_widget.on_real_transfer_complete()
        
        transfer_handler.assert_called_once_with(test_models)
        
        client_widget.close()


if __name__ == '__main__':
    # Run tests
    unittest.main()