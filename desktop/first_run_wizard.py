"""
First Run Wizard for TikTrue Platform
Comprehensive wizard for initial setup, license entry, and network configuration
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# PyQt6 imports
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QTextEdit, QComboBox, QListWidget,
    QGroupBox, QFormLayout, QProgressBar, QCheckBox, QSpinBox,
    QRadioButton, QButtonGroup, QFrame, QScrollArea, QGridLayout,
    QMessageBox, QApplication, QWidget, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QPropertyAnimation
from PyQt6.QtGui import QFont, QPixmap, QIcon, QPalette, QColor

# Import our modules
from security.license_validator import LicenseValidator
from license_models import SubscriptionTier, LicenseInfo
from license_storage import LicenseStorage
from core.network_manager import NetworkManager
from core.config_manager import ConfigManager

logger = logging.getLogger("FirstRunWizard")


class WelcomePage(QWizardPage):
    """Welcome page of the wizard"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome to TikTrue")
        self.setSubTitle("Distributed LLM Inference Platform")
        self.init_ui()
    
    def init_ui(self):
        """Initialize welcome page UI"""
        layout = QVBoxLayout()
        
        # Welcome message
        welcome_text = QLabel(
            "Welcome to TikTrue, the powerful distributed LLM inference platform!\\n\\n"
            "This wizard will help you set up your system in just a few steps:\\n"
            "• Enter your license key\\n"
            "• Configure your subscription\\n"
            "• Set up network connections\\n"
            "• Choose your preferences\\n\\n"
            "Let's get started!"
        )
        welcome_text.setWordWrap(True)
        welcome_text.setStyleSheet("""
            QLabel {
                font-size: 14px;
                line-height: 1.6;
                color: #2c3e50;
                padding: 20px;
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #dee2e6;
            }
        """)
        layout.addWidget(welcome_text)
        
        # Features overview
        features_group = QGroupBox("Key Features")
        features_layout = QVBoxLayout()
        
        features = [
            "🚀 Distributed AI model inference across multiple devices",
            "🔒 Enterprise-grade security and license management", 
            "🌐 Multi-network support for complex deployments",
            "💬 Modern chat interface with session management",
            "📊 Real-time monitoring and performance analytics"
        ]
        
        for feature in features:
            feature_label = QLabel(feature)
            feature_label.setStyleSheet("font-size: 12px; padding: 5px;")
            features_layout.addWidget(feature_label)
        
        features_group.setLayout(features_layout)
        layout.addWidget(features_group)
        
        self.setLayout(layout)


class LicensePage(QWizardPage):
    """License entry and validation page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("License Key Entry")
        self.setSubTitle("Enter your TikTrue license key to continue")
        
        self.license_validator = LicenseValidator()
        self.license_storage = LicenseStorage()
        self.current_license_info = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize license page UI"""
        layout = QVBoxLayout()
        
        # License input section
        input_group = QGroupBox("License Key")
        input_layout = QFormLayout()
        
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("TIKT-PLAN-DURATION-UNIQUE")
        self.license_input.textChanged.connect(self.validate_license_realtime)
        self.license_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 14px;
                border: 2px solid #dee2e6;
                border-radius: 8px;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
        """)
        input_layout.addRow("License Key:", self.license_input)
        
        # Status display
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        input_layout.addRow("Status:", self.status_label)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # License info display
        self.info_group = QGroupBox("License Information")
        self.info_layout = QFormLayout()
        self.info_group.setLayout(self.info_layout)
        self.info_group.setVisible(False)
        layout.addWidget(self.info_group)
        
        # Help section
        help_group = QGroupBox("Need Help?")
        help_layout = QVBoxLayout()
        
        help_text = QLabel(
            "• License format: TIKT-[PLAN]-[DURATION]-[UNIQUE]\\n"
            "• Plans: FREE (3 clients), PRO (20 clients), ENT (unlimited)\\n"
            "• Contact support@tiktrue.com for assistance"
        )
        help_text.setStyleSheet("font-size: 12px; color: #6c757d;")
        help_layout.addWidget(help_text)
        
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)
        
        self.setLayout(layout)
    
    def validate_license_realtime(self, text: str):
        """Validate license key in real-time"""
        if not text:
            self.status_label.setText("")
            self.info_group.setVisible(False)
            self.completeChanged.emit()
            return
        
        try:
            # Basic format validation
            parts = text.split('-')
            if len(parts) != 4 or parts[0] != 'TIKT':
                self.status_label.setText("❌ Invalid format")
                self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
                self.info_group.setVisible(False)
                self.current_license_info = None
                self.completeChanged.emit()
                return
            
            # Validate with license validator
            from security.hardware_fingerprint import get_hardware_fingerprint
            from license_models import ValidationStatus
            hardware_id = get_hardware_fingerprint()
            validation_result = self.license_validator.validate_license(text, hardware_id)
            
            if validation_result.status == ValidationStatus.VALID and validation_result.license_info:
                license_info = validation_result.license_info
                self.status_label.setText(f"✅ Valid {license_info.plan_type} license")
                self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
                self.current_license_info = license_info
                self.display_license_info(license_info)
                self.info_group.setVisible(True)
            else:
                self.status_label.setText(f"❌ {validation_result.message}")
                self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
                self.info_group.setVisible(False)
                self.current_license_info = None
                
        except Exception as e:
            self.status_label.setText(f"❌ Error: {str(e)}")
            self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.info_group.setVisible(False)
            self.current_license_info = None
        
        self.completeChanged.emit()
    
    def display_license_info(self, license_info: LicenseInfo):
        """Display detailed license information"""
        # Clear existing layout
        for i in reversed(range(self.info_layout.count())):
            self.info_layout.itemAt(i).widget().setParent(None)
        
        # Add license details
        self.info_layout.addRow("Plan:", QLabel(license_info.plan_type))
        self.info_layout.addRow("Max Clients:", QLabel(str(license_info.max_clients)))
        self.info_layout.addRow("Expires:", QLabel(license_info.expiry_date))
        
        # Models list
        models_text = "\\n".join([f"• {model}" for model in license_info.allowed_models])
        models_label = QLabel(models_text)
        models_label.setStyleSheet("font-size: 11px; color: #495057;")
        self.info_layout.addRow("Models:", models_label)
    
    def isComplete(self) -> bool:
        """Check if page is complete"""
        return self.current_license_info is not None and self.current_license_info.is_active
    
    def get_license_info(self) -> Optional[LicenseInfo]:
        """Get validated license info"""
        return self.current_license_info


class NetworkSetupPage(QWizardPage):
    """Network setup and configuration page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Network Setup")
        self.setSubTitle("Configure your network connections")
        
        self.network_manager = NetworkManager()
        self.selected_action = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize network setup UI"""
        layout = QVBoxLayout()
        
        # Action selection
        action_group = QGroupBox("What would you like to do?")
        action_layout = QVBoxLayout()
        
        self.action_buttons = QButtonGroup()
        
        self.create_radio = QRadioButton("Create a new network")
        self.create_radio.setChecked(True)
        self.create_radio.toggled.connect(self.on_action_changed)
        self.action_buttons.addButton(self.create_radio, 0)
        action_layout.addWidget(self.create_radio)
        
        self.join_radio = QRadioButton("Join an existing network")
        self.join_radio.toggled.connect(self.on_action_changed)
        self.action_buttons.addButton(self.join_radio, 1)
        action_layout.addWidget(self.join_radio)
        
        self.skip_radio = QRadioButton("Skip network setup (configure later)")
        self.skip_radio.toggled.connect(self.on_action_changed)
        self.action_buttons.addButton(self.skip_radio, 2)
        action_layout.addWidget(self.skip_radio)
        
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)
        
        # Stacked widget for different options
        self.options_stack = QStackedWidget()
        
        # Create network options
        self.create_widget = self.create_network_widget()
        self.options_stack.addWidget(self.create_widget)
        
        # Join network options  
        self.join_widget = self.create_join_widget()
        self.options_stack.addWidget(self.join_widget)
        
        # Skip options
        self.skip_widget = self.create_skip_widget()
        self.options_stack.addWidget(self.skip_widget)
        
        layout.addWidget(self.options_stack)
        
        self.setLayout(layout)
        self.on_action_changed()  # Initialize
    
    def create_network_widget(self) -> QWidget:
        """Create widget for network creation options"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        form_group = QGroupBox("Network Configuration")
        form_layout = QFormLayout()
        
        self.network_name_input = QLineEdit()
        self.network_name_input.setPlaceholderText("My TikTrue Network")
        form_layout.addRow("Network Name:", self.network_name_input)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "llama-7b-chat",
            "llama-13b-instruct", 
            "gpt-4-turbo",
            "mistral-7b"
        ])
        form_layout.addRow("Model:", self.model_combo)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_join_widget(self) -> QWidget:
        """Create widget for joining networks"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Discovery section
        discovery_group = QGroupBox("Available Networks")
        discovery_layout = QVBoxLayout()
        
        self.refresh_btn = QPushButton("🔍 Scan for Networks")
        self.refresh_btn.clicked.connect(self.scan_networks)
        discovery_layout.addWidget(self.refresh_btn)
        
        self.networks_list = QListWidget()
        discovery_layout.addWidget(self.networks_list)
        
        discovery_group.setLayout(discovery_layout)
        layout.addWidget(discovery_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_skip_widget(self) -> QWidget:
        """Create widget for skip option"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        info_label = QLabel(
            "You can configure networks later from the main application.\\n\\n"
            "To get started quickly, you can:\\n"
            "• Use the Networks tab in the main interface\\n"
            "• Access network settings from the sidebar\\n"
            "• Run the setup wizard again from Help menu"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                padding: 20px;
                background-color: #e3f2fd;
                border-radius: 8px;
                border: 1px solid #bbdefb;
                color: #1565c0;
            }
        """)
        layout.addWidget(info_label)
        
        widget.setLayout(layout)
        return widget
    
    def on_action_changed(self):
        """Handle action selection change"""
        if self.create_radio.isChecked():
            self.options_stack.setCurrentIndex(0)
            self.selected_action = "create"
        elif self.join_radio.isChecked():
            self.options_stack.setCurrentIndex(1)
            self.selected_action = "join"
        else:
            self.options_stack.setCurrentIndex(2)
            self.selected_action = "skip"
        
        self.completeChanged.emit()
    
    def scan_networks(self):
        """Scan for available networks"""
        self.refresh_btn.setText("🔄 Scanning...")
        self.refresh_btn.setEnabled(False)
        
        try:
            # Simulate network discovery
            QTimer.singleShot(2000, self.on_scan_complete)
            
        except Exception as e:
            logger.error(f"Network scan failed: {e}")
            QMessageBox.warning(self, "Scan Failed", f"Failed to scan networks: {e}")
            self.refresh_btn.setText("🔍 Scan for Networks")
            self.refresh_btn.setEnabled(True)
    
    def on_scan_complete(self):
        """Handle scan completion"""
        self.networks_list.clear()
        
        # Add discovered networks (mock data for now)
        networks = [
            "TikTrue-Network-001 (Admin: John's PC)",
            "AI-Lab-Cluster (Admin: Lab Server)",
            "Home-AI-Network (Admin: Gaming Rig)"
        ]
        
        for network in networks:
            self.networks_list.addItem(network)
        
        self.refresh_btn.setText("🔍 Scan for Networks")
        self.refresh_btn.setEnabled(True)
    
    def isComplete(self) -> bool:
        """Check if page is complete"""
        if self.selected_action == "create":
            return bool(self.network_name_input.text().strip())
        elif self.selected_action == "join":
            return self.networks_list.currentItem() is not None
        else:  # skip
            return True
    
    def get_network_config(self) -> Dict[str, Any]:
        """Get network configuration"""
        if self.selected_action == "create":
            return {
                "action": "create",
                "name": self.network_name_input.text().strip(),
                "model": self.model_combo.currentText()
            }
        elif self.selected_action == "join":
            selected = self.networks_list.currentItem()
            return {
                "action": "join",
                "network": selected.text() if selected else None
            }
        else:
            return {"action": "skip"}


class CompletionPage(QWizardPage):
    """Final completion page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Setup Complete!")
        self.setSubTitle("Your TikTrue platform is ready to use")
        self.init_ui()
    
    def init_ui(self):
        """Initialize completion page UI"""
        layout = QVBoxLayout()
        
        # Success message
        success_label = QLabel("🎉 Congratulations!")
        success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        success_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #28a745;
                margin: 20px;
            }
        """)
        layout.addWidget(success_label)
        
        # Summary
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(200)
        self.summary_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                font-family: monospace;
            }
        """)
        layout.addWidget(self.summary_text)
        
        # Next steps
        next_steps = QLabel(
            "Next Steps:\\n"
            "• The main application will open automatically\\n"
            "• Explore the chat interface to start conversations\\n"
            "• Check the Networks tab to manage connections\\n"
            "• Visit Settings to customize your experience"
        )
        next_steps.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #e8f5e8;
                border-radius: 8px;
                border: 1px solid #c3e6c3;
                color: #155724;
            }
        """)
        layout.addWidget(next_steps)
        
        self.setLayout(layout)
    
    def set_summary(self, license_info: LicenseInfo, network_config: Dict[str, Any]):
        """Set completion summary"""
        summary_lines = [
            "=== Setup Summary ===",
            "",
            f"License: {license_info.plan_type}",
            f"Max Clients: {license_info.max_clients}",
            f"Expires: {license_info.expiry_date}",
            "",
            f"Network Action: {network_config['action'].title()}",
        ]
        
        if network_config['action'] == 'create':
            summary_lines.extend([
                f"Network Name: {network_config['name']}",
                f"Model: {network_config['model']}"
            ])
        elif network_config['action'] == 'join':
            summary_lines.append(f"Target Network: {network_config['network']}")
        
        summary_lines.extend([
            "",
            f"Setup completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ])
        
        self.summary_text.setPlainText("\n".join(summary_lines))


class FirstRunWizard(QWizard):
    """Main first-run wizard"""
    
    setup_completed = pyqtSignal(dict)  # Emits setup results
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.license_info = None
        self.network_config = None
        
        self.init_ui()
        self.init_pages()
    
    def init_ui(self):
        """Initialize wizard UI"""
        self.setWindowTitle("TikTrue Setup Wizard")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(800, 600)
        
        # Apply modern styling
        self.setStyleSheet("""
            QWizard {
                background-color: white;
            }
            QWizard QFrame {
                background-color: #f8f9fa;
            }
            QWizardPage {
                background-color: white;
            }
        """)
    
    def init_pages(self):
        """Initialize wizard pages"""
        # Welcome page
        self.welcome_page = WelcomePage()
        self.addPage(self.welcome_page)
        
        # License page
        self.license_page = LicensePage()
        self.addPage(self.license_page)
        
        # Network setup page
        self.network_page = NetworkSetupPage()
        self.addPage(self.network_page)
        
        # Completion page
        self.completion_page = CompletionPage()
        self.addPage(self.completion_page)
    
    def accept(self):
        """Handle wizard completion"""
        try:
            # Get results
            self.license_info = self.license_page.get_license_info()
            self.network_config = self.network_page.get_network_config()
            
            # Store license
            if self.license_info:
                license_storage = LicenseStorage()
                license_storage.store_license(
                    self.license_page.license_input.text().strip(),
                    self.license_info
                )
            
            # Set completion summary
            self.completion_page.set_summary(self.license_info, self.network_config)
            
            # Emit completion signal
            self.setup_completed.emit({
                'license_info': self.license_info,
                'network_config': self.network_config
            })
            
            super().accept()
            
        except Exception as e:
            logger.error(f"Wizard completion failed: {e}")
            QMessageBox.critical(self, "Setup Error", f"Failed to complete setup: {e}")


def main():
    """Test the wizard standalone"""
    app = QApplication(sys.argv)
    
    wizard = FirstRunWizard()
    wizard.setup_completed.connect(lambda result: print(f"Setup completed: {result}"))
    
    if wizard.exec() == QWizard.DialogCode.Accepted:
        print("Wizard completed successfully!")
    else:
        print("Wizard cancelled")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()