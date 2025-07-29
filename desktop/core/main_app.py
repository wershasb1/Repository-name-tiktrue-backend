"""
TikTrue Distributed LLM Platform - Main GUI Application
Modern GUI application with PyQt6 for managing distributed LLM networks
"""

import sys
import os
import json
import logging
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QPushButton, QTextEdit, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QTabWidget,
    QGroupBox, QFormLayout, QProgressBar, QSystemTrayIcon,
    QMenu, QMessageBox, QDialog, QDialogButtonBox, QGridLayout,
    QSplitter, QFrame, QScrollArea, QCheckBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QStatusBar
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSettings, QSize,
    QPropertyAnimation, QEasingCurve, QRect, QPoint
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QFont, QPalette, QColor, QAction,
    QTextCursor, QTextCharFormat, QSyntaxHighlighter
)

# Import our modules
from core.config_manager import ConfigManager
from security.license_validator import LicenseValidator, SubscriptionTier
from license_storage import LicenseStorage
from core.network_manager import NetworkManager
from models.model_downloader import ModelDownloader
from first_run_wizard import FirstRunWizard
from interfaces.chat_interface import AdvancedChatInterface

logger = logging.getLogger("MainApp")


class WelcomeWidget(QWidget):
    """Welcome screen for first-time users"""
    
    create_network_requested = pyqtSignal()
    join_network_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize welcome screen UI"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(30)
        
        # Welcome title
        title = QLabel("Welcome to TikTrue")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 32px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Distributed LLM Inference Platform")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #7f8c8d;
                margin-bottom: 40px;
            }
        """)
        layout.addWidget(subtitle)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        # Create network button
        create_btn = QPushButton("Create New Network")
        create_btn.setMinimumSize(200, 50)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        create_btn.clicked.connect(self.create_network_requested.emit)
        button_layout.addWidget(create_btn)
        
        # Join network button
        join_btn = QPushButton("Join Existing Network")
        join_btn.setMinimumSize(200, 50)
        join_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        join_btn.clicked.connect(self.join_network_requested.emit)
        button_layout.addWidget(join_btn)
        
        layout.addLayout(button_layout)
        
        # Info text
        info_text = QLabel(
            "Create a new distributed network to share your computing resources,\\n"
            "or join an existing network to contribute to distributed inference."
        )
        info_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_text.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #95a5a6;
                margin-top: 30px;
            }
        """)
        layout.addWidget(info_text)
        
        self.setLayout(layout)


class LicenseDialog(QDialog):
    """Dialog for license key entry and validation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.license_validator = LicenseValidator()
        self.license_storage = LicenseStorage()
        self.init_ui()
    
    def init_ui(self):
        """Initialize license dialog UI"""
        self.setWindowTitle("License Key Entry")
        self.setModal(True)
        self.setFixedSize(500, 300)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Enter License Key")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # License key input
        form_layout = QFormLayout()
        
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("TIKT-PLAN-DURATION-UNIQUE")
        self.license_input.textChanged.connect(self.validate_license_format)
        form_layout.addRow("License Key:", self.license_input)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
        form_layout.addRow("", self.status_label)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def validate_license_format(self, text: str):
        """Validate license key format in real-time"""
        if not text:
            self.status_label.setText("")
            self.ok_button.setEnabled(False)
            return
        
        try:
            # Basic format validation
            parts = text.split('-')
            if len(parts) != 4 or parts[0] != 'TIKT':
                raise ValueError("Invalid format")
            
            # Validate with license validator
            license_info = self.security.license_validator.validate_license(text)
            
            if license_info.is_valid:
                self.status_label.setText(f"✓ Valid {license_info.tier.value} license")
                self.status_label.setStyleSheet("color: #27ae60; font-size: 12px;")
                self.ok_button.setEnabled(True)
            else:
                self.status_label.setText("✗ Invalid license key")
                self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
                self.ok_button.setEnabled(False)
                
        except Exception as e:
            self.status_label.setText(f"✗ {str(e)}")
            self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
            self.ok_button.setEnabled(False)
    
    def validate_and_accept(self):
        """Validate license and accept dialog"""
        license_key = self.license_input.text().strip()
        
        try:
            license_info = self.security.license_validator.validate_license(license_key)
            
            if license_info.is_valid:
                # Store license
                self.license_storage.store_license(license_key, license_info)
                self.accept()
            else:
                QMessageBox.warning(self, "Invalid License", "The license key is not valid.")
                
        except Exception as e:
            QMessageBox.critical(self, "License Error", f"Failed to validate license: {e}")
    
    def get_license_key(self) -> Optional[str]:
        """Get the entered license key"""
        return self.license_input.text().strip() if self.result() == QDialog.DialogCode.Accepted else None


class NetworkListWidget(QWidget):
    """Widget for displaying and managing networks"""
    
    network_selected = pyqtSignal(str)  # network_id
    
    def __init__(self):
        super().__init__()
        self.network_manager = NetworkManager()
        self.init_ui()
        self.refresh_networks()
    
    def init_ui(self):
        """Initialize network list UI"""
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Networks")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_networks)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Network list
        self.network_list = QListWidget()
        self.network_list.itemClicked.connect(self.on_network_selected)
        layout.addWidget(self.network_list)
        
        self.setLayout(layout)
    
    def refresh_networks(self):
        """Refresh the network list"""
        try:
            self.network_list.clear()
            
            # Get joined networks
            networks = self.network_manager.list_joined_networks()
            
            for network in networks:
                item = QListWidgetItem()
                item.setText(f"{network['name']} ({network['network_id'][:8]}...)")
                item.setData(Qt.ItemDataRole.UserRole, network['network_id'])
                
                # Add status indicator
                if network.get('status') == 'active':
                    item.setIcon(QIcon())  # Green dot icon would go here
                
                self.network_list.addItem(item)
                
        except Exception as e:
            logger.error(f"Failed to refresh networks: {e}")
    
    def on_network_selected(self, item: QListWidgetItem):
        """Handle network selection"""
        network_id = item.data(Qt.ItemDataRole.UserRole)
        if network_id:
            self.network_selected.emit(network_id)


class ChatWidget(QWidget):
    """Chat interface widget"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize chat UI"""
        layout = QVBoxLayout()
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        layout.addWidget(self.chat_display)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.returnPressed.connect(self.send_message)
        self.message_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                font-size: 14px;
            }
        """)
        input_layout.addWidget(self.message_input)
        
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send_message)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        input_layout.addWidget(send_btn)
        
        layout.addLayout(input_layout)
        
        self.setLayout(layout)
    
    def send_message(self):
        """Send a message"""
        message = self.message_input.text().strip()
        if message:
            self.add_message("You", message)
            self.message_input.clear()
            
            # TODO: Send message to inference engine
            # For now, just echo back
            QTimer.singleShot(1000, lambda: self.add_message("Assistant", f"Echo: {message}"))
    
    def add_message(self, sender: str, message: str):
        """Add a message to the chat display"""
        timestamp = datetime.now().strftime("%H:%M")
        
        if sender == "You":
            html = f"""
            <div style="margin-bottom: 10px; text-align: right;">
                <div style="background-color: #007bff; color: white; padding: 8px 12px; 
                           border-radius: 18px; display: inline-block; max-width: 70%;">
                    {message}
                </div>
                <div style="font-size: 10px; color: #6c757d; margin-top: 2px;">
                    {timestamp}
                </div>
            </div>
            """
        else:
            html = f"""
            <div style="margin-bottom: 10px;">
                <div style="background-color: #e9ecef; color: #212529; padding: 8px 12px; 
                           border-radius: 18px; display: inline-block; max-width: 70%;">
                    {message}
                </div>
                <div style="font-size: 10px; color: #6c757d; margin-top: 2px;">
                    {sender} • {timestamp}
                </div>
            </div>
            """
        
        self.chat_display.insertHtml(html)
        
        # Scroll to bottom
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.license_validator = LicenseValidator()
        self.license_storage = LicenseStorage()
        self.network_manager = NetworkManager()
        
        self.init_ui()
        self.init_system_tray()
        self.check_initial_setup()
    
    def init_ui(self):
        """Initialize main window UI"""
        self.setWindowTitle("TikTrue - Distributed LLM Platform")
        self.setMinimumSize(1200, 800)
        
        # Central widget with stacked layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Content area
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)
        
        # Add content widgets
        self.welcome_widget = WelcomeWidget()
        self.welcome_widget.create_network_requested.connect(self.show_create_network)
        self.welcome_widget.join_network_requested.connect(self.show_join_network)
        self.content_stack.addWidget(self.welcome_widget)
        
        # Use advanced chat interface instead of basic one
        self.chat_widget = AdvancedChatInterface()
        self.content_stack.addWidget(self.chat_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Apply modern styling
        self.apply_modern_style()
    
    def create_sidebar(self) -> QWidget:
        """Create sidebar with navigation"""
        sidebar = QFrame()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border-right: 1px solid #34495e;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo/Title
        title_widget = QWidget()
        title_widget.setFixedHeight(80)
        title_widget.setStyleSheet("background-color: #34495e;")
        
        title_layout = QVBoxLayout()
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel("TikTrue")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 20px;
                font-weight: bold;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(title_label)
        
        title_widget.setLayout(title_layout)
        layout.addWidget(title_widget)
        
        # Navigation buttons
        nav_buttons = [
            ("Dashboard", self.show_dashboard),
            ("Networks", self.show_networks),
            ("Chat", self.show_chat),
            ("Models", self.show_models),
            ("Settings", self.show_settings),
        ]
        
        for text, callback in nav_buttons:
            btn = QPushButton(text)
            btn.setFixedHeight(50)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #bdc3c7;
                    border: none;
                    text-align: left;
                    padding-left: 20px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #34495e;
                    color: white;
                }
                QPushButton:pressed {
                    background-color: #3498db;
                }
            """)
            btn.clicked.connect(callback)
            layout.addWidget(btn)
        
        # Spacer
        layout.addStretch()
        
        # License info
        self.license_info_widget = self.create_license_info_widget()
        layout.addWidget(self.license_info_widget)
        
        sidebar.setLayout(layout)
        return sidebar
    
    def create_license_info_widget(self) -> QWidget:
        """Create license information widget"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #34495e;
                border-top: 1px solid #4a5f7a;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # License status
        self.license_status_label = QLabel("License: Checking...")
        self.license_status_label.setStyleSheet("""
            QLabel {
                color: #bdc3c7;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.license_status_label)
        
        # Update license info
        self.update_license_info()
        
        widget.setLayout(layout)
        return widget
    
    def update_license_info(self):
        """Update license information display"""
        try:
            license_info = self.license_storage.get_stored_license()
            
            if license_info and license_info.is_valid:
                self.license_status_label.setText(f"License: {license_info.tier.value}")
                self.license_status_label.setStyleSheet("color: #27ae60; font-size: 12px;")
            else:
                self.license_status_label.setText("License: Invalid/Expired")
                self.license_status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
                
        except Exception as e:
            logger.error(f"Failed to update license info: {e}")
            self.license_status_label.setText("License: Error")
            self.license_status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
    
    def init_system_tray(self):
        """Initialize system tray icon"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            
            # Create tray menu
            tray_menu = QMenu()
            
            show_action = QAction("Show", self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)
            
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(self.quit_application)
            tray_menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.tray_icon_activated)
            
            # Set icon (would need an actual icon file)
            # self.tray_icon.setIcon(QIcon("icon.png"))
            self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        """Handle system tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()
    
    def check_initial_setup(self):
        """Check if initial setup is needed"""
        try:
            # Check if license exists
            license_info = self.license_storage.get_stored_license()
            
            if not license_info or not license_info.is_valid:
                self.show_first_run_wizard()
                return
            
            # Check if networks exist
            networks = self.network_manager.list_joined_networks()
            
            if not networks:
                # Show welcome screen
                self.content_stack.setCurrentWidget(self.welcome_widget)
            else:
                # Show dashboard
                self.show_dashboard()
                
        except Exception as e:
            logger.error(f"Failed to check initial setup: {e}")
            self.show_first_run_wizard()
    
    def show_first_run_wizard(self):
        """Show first-run wizard"""
        wizard = FirstRunWizard(self)
        wizard.setup_completed.connect(self.on_wizard_completed)
        
        if wizard.exec() == QWizard.DialogCode.Accepted:
            logger.info("First-run wizard completed successfully")
        else:
            # User cancelled wizard
            QMessageBox.information(
                self, 
                "Setup Required", 
                "Initial setup is required to use TikTrue. The application will now exit."
            )
            self.quit_application()
    
    def on_wizard_completed(self, setup_result: Dict[str, Any]):
        """Handle wizard completion"""
        try:
            logger.info(f"Wizard completed with result: {setup_result}")
            
            # Update license info display
            self.update_license_info()
            
            # Handle network configuration
            network_config = setup_result.get('network_config', {})
            
            if network_config.get('action') == 'create':
                self.create_network_from_wizard(network_config)
            elif network_config.get('action') == 'join':
                self.join_network_from_wizard(network_config)
            
            # Show appropriate view
            self.check_initial_setup()
            
        except Exception as e:
            logger.error(f"Failed to handle wizard completion: {e}")
            QMessageBox.warning(self, "Setup Warning", f"Setup completed but with warnings: {e}")
    
    def create_network_from_wizard(self, config: Dict[str, Any]):
        """Create network from wizard configuration"""
        try:
            network_name = config.get('name', 'My Network')
            model_id = config.get('model', 'llama-7b-chat')
            
            # TODO: Implement actual network creation
            logger.info(f"Creating network: {network_name} with model: {model_id}")
            
            # For now, just show a message
            QMessageBox.information(
                self, 
                "Network Created", 
                f"Network '{network_name}' will be created with model '{model_id}'"
            )
            
        except Exception as e:
            logger.error(f"Failed to create network: {e}")
            QMessageBox.warning(self, "Network Creation Failed", f"Failed to create network: {e}")
    
    def join_network_from_wizard(self, config: Dict[str, Any]):
        """Join network from wizard configuration"""
        try:
            network_name = config.get('network', 'Unknown Network')
            
            # TODO: Implement actual network joining
            logger.info(f"Joining network: {network_name}")
            
            # For now, just show a message
            QMessageBox.information(
                self, 
                "Network Join", 
                f"Will attempt to join network: {network_name}"
            )
            
        except Exception as e:
            logger.error(f"Failed to join network: {e}")
            QMessageBox.warning(self, "Network Join Failed", f"Failed to join network: {e}")

    def show_license_dialog(self):
        """Show license entry dialog"""
        dialog = LicenseDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.update_license_info()
            self.check_initial_setup()
        else:
            # User cancelled license entry
            QMessageBox.information(
                self, 
                "License Required", 
                "A valid license is required to use TikTrue. The application will now exit."
            )
            self.quit_application()
    
    def apply_modern_style(self):
        """Apply modern styling to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ecf0f1;
            }
            
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            
            QStackedWidget {
                background-color: white;
                border-radius: 8px;
                margin: 10px;
            }
        """)
    
    # Navigation methods
    def show_dashboard(self):
        """Show dashboard view"""
        self.status_bar.showMessage("Dashboard")
        # TODO: Implement dashboard widget
        pass
    
    def show_networks(self):
        """Show networks view"""
        self.status_bar.showMessage("Networks")
        # TODO: Implement networks widget
        pass
    
    def show_chat(self):
        """Show chat view"""
        self.content_stack.setCurrentWidget(self.chat_widget)
        self.status_bar.showMessage("Chat")
    
    def show_models(self):
        """Show models view"""
        self.status_bar.showMessage("Models")
        # TODO: Implement models widget
        pass
    
    def show_settings(self):
        """Show settings view"""
        self.status_bar.showMessage("Settings")
        # TODO: Implement settings widget
        pass
    
    def show_create_network(self):
        """Show create network dialog"""
        # TODO: Implement create network dialog
        QMessageBox.information(self, "Create Network", "Create network functionality will be implemented.")
    
    def show_join_network(self):
        """Show join network dialog"""
        # TODO: Implement join network dialog
        QMessageBox.information(self, "Join Network", "Join network functionality will be implemented.")
    
    def closeEvent(self, event):
        """Handle window close event"""
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            # Minimize to tray instead of closing
            self.hide()
            event.ignore()
        else:
            event.accept()
    
    def quit_application(self):
        """Quit the application"""
        QApplication.quit()


class TikTrueApplication(QApplication):
    """Main application class"""
    
    def __init__(self, argv):
        super().__init__(argv)
        
        # Set application properties
        self.setApplicationName("TikTrue")
        self.setApplicationVersion("1.0.0")
        self.setOrganizationName("TikTrue")
        self.setOrganizationDomain("tiktrue.com")
        
        # Configure logging
        self.setup_logging()
        
        # Create main window
        self.main_window = MainWindow()
    
    def setup_logging(self):
        """Setup application logging"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / "main_app.log"),
                logging.StreamHandler()
            ]
        )
    
    def run(self):
        """Run the application"""
        try:
            self.main_window.show()
            return self.exec()
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            return 1


def main():
    """Main entry point"""
    try:
        # Create application
        app = TikTrueApplication(sys.argv)
        
        # Run application
        exit_code = app.run()
        
        # Exit
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()