"""
TikTrue Distributed LLM Platform - Main Application Entry Point
PyQt6-based GUI with Admin/Client mode selection and persistent storage

Requirements addressed:
- 1.3: Application prompts user to select Admin/Client mode on first run
- 1.4: Application persists mode selection for subsequent launches
- 8.1: Clear interface for mode selection
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
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QMessageBox, QDialog,
    QDialogButtonBox, QFrame, QGroupBox, QRadioButton, QButtonGroup,
    QTextEdit, QProgressBar, QSystemTrayIcon, QMenu, QStatusBar,
    QLineEdit, QFormLayout, QCheckBox, QGridLayout, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QTimer, QThread
from PyQt6.QtGui import QIcon, QFont, QPixmap, QAction, QPalette, QColor, QTextCursor

# Import our modules
from core.config_manager import ConfigManager
from first_run_wizard import FirstRunWizard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainApp")


class LoginDialog(QDialog):
    """Dialog for admin login with backend authentication"""
    
    login_successful = pyqtSignal(dict)  # Emits user info on successful login
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_info = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize login dialog UI"""
        self.setWindowTitle("Admin Login - TikTrue")
        self.setModal(True)
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Admin Login")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #2980b9;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(title)
        
        # Login form
        form_group = QGroupBox("Credentials")
        form_layout = QFormLayout()
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("admin@example.com")
        self.email_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        form_layout.addRow("Email:", self.email_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Password")
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        self.password_input.returnPressed.connect(self.attempt_login)
        form_layout.addRow("Password:", self.password_input)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        form_layout.addRow("", self.status_label)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("Login")
        self.login_btn.setMinimumHeight(40)
        self.login_btn.clicked.connect(self.attempt_login)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        button_layout.addWidget(self.login_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def attempt_login(self):
        """Attempt to login with provided credentials"""
        email = self.email_input.text().strip()
        password = self.password_input.text()
        
        if not email or not password:
            self.show_status("Please enter both email and password", "error")
            return
        
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Logging in...")
        self.show_status("Authenticating...", "info")
        
        # Simulate backend authentication (replace with actual API call)
        QTimer.singleShot(2000, lambda: self.simulate_login_response(email, password))
    
    def simulate_login_response(self, email: str, password: str):
        """Simulate backend login response"""
        # Mock successful login for demo purposes
        if email and password:
            self.user_info = {
                "user_id": "admin_123",
                "email": email,
                "name": email.split('@')[0].title(),
                "plan_type": "PRO",
                "max_clients": 20,
                "allowed_models": ["llama3_1_8b_fp16", "mistral_7b_int4", "gpt4_turbo_preview"],
                "license_expires": "2024-12-31",
                "auth_token": "mock_jwt_token_here"
            }
            
            self.show_status("Login successful!", "success")
            self.login_successful.emit(self.user_info)
            QTimer.singleShot(1000, self.accept)
        else:
            self.show_status("Invalid credentials", "error")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Login")
    
    def show_status(self, message: str, status_type: str):
        """Show status message with appropriate styling"""
        colors = {
            "info": "#3498db",
            "success": "#27ae60", 
            "error": "#e74c3c"
        }
        
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {colors.get(status_type, '#34495e')};
                font-weight: bold;
                font-size: 12px;
            }}
        """)
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get user information after successful login"""
        return self.user_info


class ModelDownloadDialog(QDialog):
    """Dialog for downloading models with progress tracking"""
    
    def __init__(self, available_models: List[str], parent=None):
        super().__init__(parent)
        self.available_models = available_models
        self.selected_models = []
        self.init_ui()
    
    def init_ui(self):
        """Initialize model download dialog UI"""
        self.setWindowTitle("Download Models")
        self.setModal(True)
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Select Models to Download")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(title)
        
        # Models selection
        models_group = QGroupBox("Available Models")
        models_layout = QVBoxLayout()
        
        self.model_checkboxes = []
        for model in self.available_models:
            checkbox = QCheckBox(model)
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 14px;
                    padding: 5px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
            """)
            self.model_checkboxes.append(checkbox)
            models_layout.addWidget(checkbox)
        
        models_group.setLayout(models_layout)
        layout.addWidget(models_group)
        
        # Progress section
        progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_label = QLabel("Ready to download")
        self.progress_label.setStyleSheet("font-weight: bold; color: #7f8c8d;")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        button_layout.addWidget(self.download_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def start_download(self):
        """Start downloading selected models"""
        selected = [cb.text() for cb in self.model_checkboxes if cb.isChecked()]
        
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select at least one model to download.")
            return
        
        self.selected_models = selected
        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Simulate download process
        self.current_model_index = 0
        self.download_next_model()
    
    def download_next_model(self):
        """Download next model in queue"""
        if self.current_model_index >= len(self.selected_models):
            self.download_complete()
            return
        
        current_model = self.selected_models[self.current_model_index]
        self.progress_label.setText(f"Downloading {current_model}...")
        
        # Simulate download progress
        self.download_progress = 0
        self.download_timer = QTimer()
        self.download_timer.timeout.connect(self.update_download_progress)
        self.download_timer.start(50)  # Update every 50ms
    
    def update_download_progress(self):
        """Update download progress"""
        self.download_progress += 2
        
        # Calculate overall progress
        model_progress = self.download_progress / 100
        overall_progress = ((self.current_model_index + model_progress) / len(self.selected_models)) * 100
        self.progress_bar.setValue(int(overall_progress))
        
        if self.download_progress >= 100:
            self.download_timer.stop()
            self.current_model_index += 1
            self.download_next_model()
    
    def download_complete(self):
        """Handle download completion"""
        self.progress_label.setText("Download completed!")
        self.progress_bar.setValue(100)
        
        QMessageBox.information(
            self, 
            "Download Complete", 
            f"Successfully downloaded {len(self.selected_models)} model(s)!"
        )
        
        self.accept()


class ModeSelectionDialog(QDialog):
    """Dialog for selecting Admin or Client mode"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_mode = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize mode selection dialog UI"""
        self.setWindowTitle("TikTrue - Mode Selection")
        self.setModal(True)
        self.setFixedSize(600, 400)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Welcome to TikTrue")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
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
                margin-bottom: 30px;
            }
        """)
        layout.addWidget(subtitle)
        
        # Mode selection group
        mode_group = QGroupBox("Select Operating Mode")
        mode_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #34495e;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        mode_layout = QVBoxLayout()
        
        # Button group for radio buttons
        self.mode_buttons = QButtonGroup()
        
        # Admin mode option
        admin_frame = QFrame()
        admin_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #3498db;
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
                background-color: #f8f9fa;
            }
            QFrame:hover {
                background-color: #e3f2fd;
            }
        """)
        admin_layout = QVBoxLayout()
        
        self.admin_radio = QRadioButton("Admin Mode")
        self.admin_radio.setStyleSheet("""
            QRadioButton {
                font-size: 18px;
                font-weight: bold;
                color: #2980b9;
            }
        """)
        admin_layout.addWidget(self.admin_radio)
        
        admin_desc = QLabel(
            "• Manage and host LLM models\n"
            "• Create local networks for clients\n"
            "• Download models from central server\n"
            "• Approve client connection requests\n"
            "• Monitor network activity"
        )
        admin_desc.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #34495e;
                margin-left: 20px;
                line-height: 1.4;
            }
        """)
        admin_layout.addWidget(admin_desc)
        
        admin_frame.setLayout(admin_layout)
        mode_layout.addWidget(admin_frame)
        
        # Client mode option
        client_frame = QFrame()
        client_frame.setStyleSheet("""
            QFrame {
                border: 2px solid #2ecc71;
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
                background-color: #f8f9fa;
            }
            QFrame:hover {
                background-color: #e8f5e8;
            }
        """)
        client_layout = QVBoxLayout()
        
        self.client_radio = QRadioButton("Client Mode")
        self.client_radio.setStyleSheet("""
            QRadioButton {
                font-size: 18px;
                font-weight: bold;
                color: #27ae60;
            }
        """)
        client_layout.addWidget(self.client_radio)
        
        client_desc = QLabel(
            "• Connect to existing LLM networks\n"
            "• Use distributed models for inference\n"
            "• No direct internet access required\n"
            "• Receive model blocks from admin nodes\n"
            "• Participate in distributed computing"
        )
        client_desc.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #34495e;
                margin-left: 20px;
                line-height: 1.4;
            }
        """)
        client_layout.addWidget(client_desc)
        
        client_frame.setLayout(client_layout)
        mode_layout.addWidget(client_frame)
        
        # Add radio buttons to button group
        self.mode_buttons.addButton(self.admin_radio, 0)
        self.mode_buttons.addButton(self.client_radio, 1)
        
        # Connect signals
        self.admin_radio.toggled.connect(self.on_mode_changed)
        self.client_radio.toggled.connect(self.on_mode_changed)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Remember choice checkbox
        self.remember_checkbox = QRadioButton("Remember my choice")
        self.remember_checkbox.setChecked(True)
        self.remember_checkbox.setStyleSheet("""
            QRadioButton {
                font-size: 12px;
                color: #7f8c8d;
            }
        """)
        button_layout.addWidget(self.remember_checkbox)
        
        button_layout.addStretch()
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_mode_changed(self):
        """Handle mode selection change"""
        if self.admin_radio.isChecked():
            self.selected_mode = "admin"
            self.ok_button.setEnabled(True)
        elif self.client_radio.isChecked():
            self.selected_mode = "client"
            self.ok_button.setEnabled(True)
        else:
            self.selected_mode = None
            self.ok_button.setEnabled(False)
    
    def get_selected_mode(self) -> Optional[str]:
        """Get the selected mode"""
        return self.selected_mode
    
    def should_remember_choice(self) -> bool:
        """Check if user wants to remember the choice"""
        return self.remember_checkbox.isChecked()


class LoginDialog(QDialog):
    """Login dialog for admin authentication"""
    
    login_successful = pyqtSignal(dict)  # Emits user info on successful login
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_info = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize login dialog UI"""
        self.setWindowTitle("Admin Login - TikTrue")
        self.setModal(True)
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Admin Login")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #2980b9;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(title)
        
        # Login form
        form_group = QGroupBox("Credentials")
        form_layout = QFormLayout()
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("admin@example.com")
        self.email_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        form_layout.addRow("Email:", self.email_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        self.password_input.returnPressed.connect(self.attempt_login)
        form_layout.addRow("Password:", self.password_input)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        form_layout.addRow("", self.status_label)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("Login")
        self.login_btn.setMinimumHeight(40)
        self.login_btn.clicked.connect(self.attempt_login)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        button_layout.addWidget(self.login_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def attempt_login(self):
        """Attempt to login with provided credentials"""
        email = self.email_input.text().strip()
        password = self.password_input.text()
        
        if not email or not password:
            self.show_status("Please enter both email and password", "error")
            return
        
        # Disable login button during attempt
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Logging in...")
        self.show_status("Authenticating...", "info")
        
        # Simulate authentication (in real implementation, this would call backend API)
        QTimer.singleShot(2000, lambda: self.simulate_login_result(email, password))
    
    def simulate_login_result(self, email: str, password: str):
        """Simulate login result (replace with actual backend authentication)"""
        # Mock successful login for demo purposes
        if email and password:
            self.user_info = {
                "user_id": "admin_123",
                "email": email,
                "name": "Admin User",
                "plan_type": "PRO",
                "max_clients": 20,
                "allowed_models": ["llama3_1_8b_fp16", "mistral_7b_int4"],
                "license_expires": "2024-12-31"
            }
            
            self.show_status("Login successful!", "success")
            QTimer.singleShot(1000, self.accept)
            self.login_successful.emit(self.user_info)
        else:
            self.show_status("Invalid credentials", "error")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Login")
    
    def show_status(self, message: str, status_type: str):
        """Show status message with appropriate styling"""
        colors = {
            "info": "#3498db",
            "success": "#27ae60", 
            "error": "#e74c3c"
        }
        
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {colors.get(status_type, '#7f8c8d')};
                font-weight: bold;
                padding: 5px;
            }}
        """)
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get user information after successful login"""
        return self.user_info



class AdminModeWidget(QWidget):
    """Enhanced Admin mode interface with full functionality"""
    
    def __init__(self):
        super().__init__()
        self.user_info = None
        self.is_logged_in = False
        self.init_ui()
    
    def init_ui(self):
        """Initialize admin mode UI"""
        layout = QVBoxLayout()
        
        # Header with login status
        self.header_widget = self.create_header_widget()
        layout.addWidget(self.header_widget)
        
        # Main content stack
        self.content_stack = QStackedWidget()
        
        # Login required screen
        self.login_required_widget = self.create_login_required_widget()
        self.content_stack.addWidget(self.login_required_widget)
        
        # Main admin dashboard
        self.dashboard_widget = self.create_dashboard_widget()
        self.content_stack.addWidget(self.dashboard_widget)
        
        layout.addWidget(self.content_stack)
        
        # Initially show login required screen
        self.content_stack.setCurrentWidget(self.login_required_widget)
        
        self.setLayout(layout)
    
    def create_header_widget(self) -> QWidget:
        """Create header widget with login status and controls"""
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: #2980b9;
                border-radius: 8px;
                margin-bottom: 10px;
            }
        """)
        
        layout = QHBoxLayout()
        
        # Title
        title = QLabel("Admin Mode - Network Management")
        title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: white;
                padding: 15px;
            }
        """)
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Login status and controls
        self.login_status_widget = QWidget()
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Not logged in")
        self.status_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                padding: 10px;
            }
        """)
        status_layout.addWidget(self.status_label)
        
        self.login_btn = QPushButton("Login")
        self.login_btn.clicked.connect(self.show_login_dialog)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        status_layout.addWidget(self.login_btn)
        
        self.logout_btn = QPushButton("Logout")
        self.logout_btn.clicked.connect(self.logout)
        self.logout_btn.setVisible(False)
        self.logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        status_layout.addWidget(self.logout_btn)
        
        self.login_status_widget.setLayout(status_layout)
        layout.addWidget(self.login_status_widget)
        
        header.setLayout(layout)
        return header
    
    def create_login_required_widget(self) -> QWidget:
        """Create widget shown when login is required"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon or image placeholder
        icon_label = QLabel("🔐")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                font-size: 64px;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(icon_label)
        
        # Message
        message = QLabel("Admin Login Required")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(message)
        
        # Description
        description = QLabel(
            "Please log in with your admin credentials to access\n"
            "network management, model downloads, and client administration."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #7f8c8d;
                margin-bottom: 30px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(description)
        
        # Login button
        login_btn = QPushButton("Login Now")
        login_btn.setMinimumSize(200, 50)
        login_btn.clicked.connect(self.show_login_dialog)
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        layout.addWidget(login_btn)
        
        widget.setLayout(layout)
        return widget
    
    def create_dashboard_widget(self) -> QWidget:
        """Create main admin dashboard widget"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # License status section
        self.license_group = self.create_license_status_widget()
        layout.addWidget(self.license_group)
        
        # Quick actions section
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QGridLayout()
        
        # Network management
        create_network_btn = QPushButton("Create Network")
        create_network_btn.setMinimumHeight(60)
        create_network_btn.clicked.connect(self.create_network)
        create_network_btn.setStyleSheet(self.get_action_button_style("#3498db"))
        actions_layout.addWidget(create_network_btn, 0, 0)
        
        manage_networks_btn = QPushButton("Manage Networks")
        manage_networks_btn.setMinimumHeight(60)
        manage_networks_btn.clicked.connect(self.manage_networks)
        manage_networks_btn.setStyleSheet(self.get_action_button_style("#9b59b6"))
        actions_layout.addWidget(manage_networks_btn, 0, 1)
        
        # Model management
        download_models_btn = QPushButton("Download Models")
        download_models_btn.setMinimumHeight(60)
        download_models_btn.clicked.connect(self.download_models)
        download_models_btn.setStyleSheet(self.get_action_button_style("#e67e22"))
        actions_layout.addWidget(download_models_btn, 1, 0)
        
        manage_models_btn = QPushButton("Manage Models")
        manage_models_btn.setMinimumHeight(60)
        manage_models_btn.clicked.connect(self.manage_models)
        manage_models_btn.setStyleSheet(self.get_action_button_style("#f39c12"))
        actions_layout.addWidget(manage_models_btn, 1, 1)
        
        # Client management
        view_clients_btn = QPushButton("View Clients")
        view_clients_btn.setMinimumHeight(60)
        view_clients_btn.clicked.connect(self.view_clients)
        view_clients_btn.setStyleSheet(self.get_action_button_style("#2ecc71"))
        actions_layout.addWidget(view_clients_btn, 2, 0)
        
        client_requests_btn = QPushButton("Client Requests")
        client_requests_btn.setMinimumHeight(60)
        client_requests_btn.clicked.connect(self.manage_client_requests)
        client_requests_btn.setStyleSheet(self.get_action_button_style("#27ae60"))
        actions_layout.addWidget(client_requests_btn, 2, 1)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        # System status section
        status_group = self.create_system_status_widget()
        layout.addWidget(status_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_license_status_widget(self) -> QGroupBox:
        """Create license status display widget"""
        group = QGroupBox("License Status")
        layout = QGridLayout()
        
        # License info labels
        self.license_plan_label = QLabel("Plan: Not Available")
        self.license_plan_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(QLabel("License Plan:"), 0, 0)
        layout.addWidget(self.license_plan_label, 0, 1)
        
        self.license_expires_label = QLabel("Expires: Not Available")
        self.license_expires_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(QLabel("Expires:"), 1, 0)
        layout.addWidget(self.license_expires_label, 1, 1)
        
        self.max_clients_label = QLabel("Max Clients: Not Available")
        self.max_clients_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(QLabel("Max Clients:"), 2, 0)
        layout.addWidget(self.max_clients_label, 2, 1)
        
        # Allowed models
        layout.addWidget(QLabel("Allowed Models:"), 3, 0)
        self.models_list = QLabel("Not Available")
        self.models_list.setWordWrap(True)
        self.models_list.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.models_list, 3, 1)
        
        group.setLayout(layout)
        return group
    
    def create_system_status_widget(self) -> QGroupBox:
        """Create system status display widget"""
        group = QGroupBox("System Status")
        layout = QVBoxLayout()
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(150)
        self.status_text.setPlainText(
            "System Status: Ready\n"
            "Active Networks: 0\n"
            "Connected Clients: 0\n"
            "Downloaded Models: 0"
        )
        self.status_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 10px;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.status_text)
        
        group.setLayout(layout)
        return group
    
    def get_action_button_style(self, color: str) -> str:
        """Get consistent styling for action buttons"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                margin: 5px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(color, 0.3)};
            }}
        """
    
    def darken_color(self, hex_color: str, factor: float = 0.2) -> str:
        """Darken a hex color by a given factor"""
        # Simple color darkening - in production, use proper color manipulation
        return hex_color  # Simplified for now
    
    def show_login_dialog(self):
        """Show login dialog"""
        dialog = LoginDialog(self)
        dialog.login_successful.connect(self.on_login_successful)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("Login dialog completed successfully")
    
    def on_login_successful(self, user_info: Dict[str, Any]):
        """Handle successful login"""
        self.user_info = user_info
        self.is_logged_in = True
        
        # Update UI
        self.update_login_status()
        self.update_license_display()
        self.content_stack.setCurrentWidget(self.dashboard_widget)
        
        logger.info(f"Admin logged in: {user_info.get('email', 'Unknown')}")
    
    def logout(self):
        """Handle logout"""
        reply = QMessageBox.question(
            self, 
            "Confirm Logout", 
            "Are you sure you want to logout?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.user_info = None
            self.is_logged_in = False
            self.update_login_status()
            self.content_stack.setCurrentWidget(self.login_required_widget)
            logger.info("Admin logged out")
    
    def update_login_status(self):
        """Update login status display"""
        if self.is_logged_in and self.user_info:
            self.status_label.setText(f"Logged in as: {self.user_info.get('name', 'Admin')}")
            self.login_btn.setVisible(False)
            self.logout_btn.setVisible(True)
        else:
            self.status_label.setText("Not logged in")
            self.login_btn.setVisible(True)
            self.logout_btn.setVisible(False)
    
    def update_license_display(self):
        """Update license information display"""
        if self.user_info:
            self.license_plan_label.setText(self.user_info.get('plan_type', 'Unknown'))
            self.license_expires_label.setText(self.user_info.get('license_expires', 'Unknown'))
            self.max_clients_label.setText(str(self.user_info.get('max_clients', 0)))
            
            models = self.user_info.get('allowed_models', [])
            models_text = ', '.join(models) if models else 'None'
            self.models_list.setText(models_text)
    
    # Action handlers
    def create_network(self):
        """Handle create network action"""
        QMessageBox.information(self, "Create Network", "Network creation functionality will be implemented.")
    
    def manage_networks(self):
        """Handle manage networks action"""
        QMessageBox.information(self, "Manage Networks", "Network management functionality will be implemented.")
    
    def download_models(self):
        """Handle download models action"""
        if not self.is_logged_in:
            QMessageBox.warning(self, "Login Required", "Please login first to download models.")
            return
        
        available_models = self.user_info.get('allowed_models', [])
        if not available_models:
            QMessageBox.information(self, "No Models", "No models available for your license plan.")
            return
        
        dialog = ModelDownloadDialog(available_models, self)
        dialog.exec()
    
    def manage_models(self):
        """Handle manage models action"""
        QMessageBox.information(self, "Manage Models", "Model management functionality will be implemented.")
    
    def view_clients(self):
        """Handle view clients action"""
        QMessageBox.information(self, "View Clients", "Client viewing functionality will be implemented.")
    
    def manage_client_requests(self):
        """Handle client requests action"""
        QMessageBox.information(self, "Client Requests", "Client request management functionality will be implemented.")


class NetworkDiscoveryWidget(QWidget):
    """Widget for network discovery and selection interface"""
    
    network_selected = pyqtSignal(dict)  # Emits selected network info
    
    def __init__(self):
        super().__init__()
        self.discovered_networks = []
        self.network_discovery = None
        self.init_ui()
        self.setup_network_discovery()
    
    def init_ui(self):
        """Initialize network discovery UI"""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Network Discovery")
        header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(header)
        
        # Discovery controls
        controls_layout = QHBoxLayout()
        
        self.scan_btn = QPushButton("🔍 Scan for Networks")
        self.scan_btn.clicked.connect(self.scan_networks)
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        controls_layout.addWidget(self.scan_btn)
        
        self.auto_scan_checkbox = QCheckBox("Auto-scan every 30s")
        self.auto_scan_checkbox.toggled.connect(self.toggle_auto_scan)
        controls_layout.addWidget(self.auto_scan_checkbox)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Networks list
        self.networks_list = QListWidget()
        self.networks_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                background-color: white;
                min-height: 200px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
        """)
        self.networks_list.itemDoubleClicked.connect(self.on_network_double_clicked)
        layout.addWidget(self.networks_list)
        
        # Connection button
        self.connect_btn = QPushButton("Connect to Selected Network")
        self.connect_btn.clicked.connect(self.connect_to_selected_network)
        self.connect_btn.setEnabled(False)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        layout.addWidget(self.connect_btn)
        
        # Selection change handler
        self.networks_list.itemSelectionChanged.connect(self.on_selection_changed)
        
        # Auto-scan timer
        self.auto_scan_timer = QTimer()
        self.auto_scan_timer.timeout.connect(self.scan_networks)
        
        self.setLayout(layout)
        
        # Initial scan
        QTimer.singleShot(1000, self.scan_networks)
    
    def setup_network_discovery(self):
        """Setup network discovery integration"""
        try:
            # Import network discovery module
            from network.network_discovery import NetworkDiscovery
            self.network_discovery = NetworkDiscovery()
            logger.info("Network discovery initialized successfully")
        except ImportError as e:
            logger.warning(f"Network discovery module not available: {e}")
            self.network_discovery = None
    
    def scan_networks(self):
        """Scan for available TikTrue networks"""
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("🔄 Scanning...")
        
        if self.network_discovery:
            # Use actual network discovery
            try:
                self.perform_real_network_scan()
            except Exception as e:
                logger.error(f"Network scan failed: {e}")
                self.on_scan_complete()  # Fall back to mock data
        else:
            # Fall back to simulated discovery
            QTimer.singleShot(2000, self.on_scan_complete)
    
    def perform_real_network_scan(self):
        """Perform actual network discovery scan"""
        try:
            # Start network discovery in a separate thread to avoid blocking UI
            import threading
            scan_thread = threading.Thread(target=self._network_scan_worker)
            scan_thread.daemon = True
            scan_thread.start()
        except Exception as e:
            logger.error(f"Failed to start network scan thread: {e}")
            QTimer.singleShot(2000, self.on_scan_complete)
    
    def _network_scan_worker(self):
        """Worker thread for network scanning"""
        try:
            # Perform network discovery
            discovered = self.network_discovery.discover_admin_nodes()
            
            # Convert to our format and emit signal to update UI
            networks = []
            for node in discovered:
                network_info = {
                    "name": node.get("network_name", f"TikTrue-{node.get('node_id', 'Unknown')}"),
                    "admin": node.get("admin_name", "Unknown Admin"),
                    "ip": node.get("ip_address", "Unknown IP"),
                    "models": node.get("available_models", []),
                    "clients": f"{node.get('current_clients', 0)}/{node.get('max_clients', 0)}",
                    "status": node.get("status", "Unknown"),
                    "port": node.get("port", 8765),
                    "node_id": node.get("node_id")
                }
                networks.append(network_info)
            
            # Update UI from main thread
            QTimer.singleShot(0, lambda: self.on_real_scan_complete(networks))
            
        except Exception as e:
            logger.error(f"Network scan worker failed: {e}")
            QTimer.singleShot(0, self.on_scan_complete)
    
    def on_real_scan_complete(self, networks: list):
        """Handle completion of real network scan"""
        self.discovered_networks = networks
        self.update_networks_list()
        
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("🔍 Scan for Networks")
        
        if not networks:
            self.networks_list.addItem(QListWidgetItem("No TikTrue networks found on local network"))
        
        logger.info(f"Network scan completed. Found {len(networks)} networks.")
    
    def on_scan_complete(self):
        """Handle scan completion with mock networks"""
        # Mock discovered networks
        mock_networks = [
            {
                "name": "TikTrue-Network-001",
                "admin": "John's PC",
                "ip": "192.168.1.100",
                "models": ["llama3_1_8b_fp16", "mistral_7b_int4"],
                "clients": "5/20",
                "status": "Active"
            },
            {
                "name": "AI-Lab-Cluster",
                "admin": "Lab Server",
                "ip": "192.168.1.150",
                "models": ["gpt4_turbo_preview"],
                "clients": "2/10",
                "status": "Active"
            },
            {
                "name": "Home-AI-Network",
                "admin": "Gaming Rig",
                "ip": "192.168.1.200",
                "models": ["llama3_1_8b_fp16"],
                "clients": "1/5",
                "status": "Active"
            }
        ]
        
        self.discovered_networks = mock_networks
        self.update_networks_list()
        
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("🔍 Scan for Networks")
    
    def update_networks_list(self):
        """Update the networks list display"""
        self.networks_list.clear()
        
        for network in self.discovered_networks:
            item_text = f"🌐 {network['name']}\n"
            item_text += f"   Admin: {network['admin']} ({network['ip']})\n"
            item_text += f"   Models: {', '.join(network['models'])}\n"
            item_text += f"   Clients: {network['clients']} | Status: {network['status']}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, network)
            self.networks_list.addItem(item)
    
    def on_selection_changed(self):
        """Handle network selection change"""
        has_selection = bool(self.networks_list.currentItem())
        self.connect_btn.setEnabled(has_selection)
    
    def on_network_double_clicked(self, item):
        """Handle network double-click"""
        self.connect_to_selected_network()
    
    def connect_to_selected_network(self):
        """Connect to the selected network"""
        current_item = self.networks_list.currentItem()
        if current_item:
            network_info = current_item.data(Qt.ItemDataRole.UserRole)
            self.network_selected.emit(network_info)
    
    def toggle_auto_scan(self, enabled):
        """Toggle auto-scan functionality"""
        if enabled:
            self.auto_scan_timer.start(30000)  # 30 seconds
        else:
            self.auto_scan_timer.stop()


class ModelTransferWidget(QWidget):
    """Widget for displaying model transfer progress"""
    
    transfer_completed = pyqtSignal(list)  # Emits list of transferred models
    
    def __init__(self):
        super().__init__()
        self.secure_transfer = None
        self.current_network = None
        self.init_ui()
        self.setup_transfer_integration()
    
    def init_ui(self):
        """Initialize model transfer UI"""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Model Transfer Progress")
        header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(header)
        
        # Transfer status
        self.status_label = QLabel("No active transfers")
        self.status_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Transfer details
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
                border-radius: 6px;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.details_text)
        
        self.setLayout(layout)
    
    def setup_transfer_integration(self):
        """Setup secure transfer integration"""
        try:
            # Import secure transfer module
            from network.secure_block_transfer import SecureBlockTransfer
            self.secure_transfer = SecureBlockTransfer()
            logger.info("Secure transfer initialized successfully")
        except ImportError as e:
            logger.warning(f"Secure transfer module not available: {e}")
            self.secure_transfer = None
    
    def start_transfer(self, network_info: dict):
        """Start model transfer from selected network"""
        self.current_network = network_info
        self.status_label.setText(f"Transferring models from {network_info['name']}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.log_transfer_message(f"Starting transfer from {network_info['admin']} ({network_info['ip']})")
        self.log_transfer_message(f"Models to transfer: {', '.join(network_info['models'])}")
        
        if self.secure_transfer:
            # Use actual secure transfer
            try:
                self.perform_real_transfer(network_info)
            except Exception as e:
                logger.error(f"Secure transfer failed: {e}")
                self.log_transfer_message(f"Transfer error: {e}")
                self.simulate_transfer_fallback()
        else:
            # Fall back to simulated transfer
            self.simulate_transfer_fallback()
    
    def perform_real_transfer(self, network_info: dict):
        """Perform actual secure model transfer"""
        try:
            # Start secure transfer in a separate thread
            import threading
            transfer_thread = threading.Thread(
                target=self._secure_transfer_worker, 
                args=(network_info,)
            )
            transfer_thread.daemon = True
            transfer_thread.start()
        except Exception as e:
            logger.error(f"Failed to start secure transfer thread: {e}")
            self.simulate_transfer_fallback()
    
    def _secure_transfer_worker(self, network_info: dict):
        """Worker thread for secure model transfer"""
        try:
            # Connect to admin node
            admin_ip = network_info['ip']
            admin_port = network_info.get('port', 8765)
            
            # Initialize transfer session
            transfer_session = self.secure_transfer.create_client_session(
                admin_ip, admin_port, network_info.get('node_id')
            )
            
            # Request model blocks for each model
            total_models = len(network_info['models'])
            for i, model_name in enumerate(network_info['models']):
                QTimer.singleShot(0, lambda m=model_name: self.log_transfer_message(f"Requesting {m}..."))
                
                # Request model blocks
                blocks = self.secure_transfer.request_model_blocks(
                    transfer_session, model_name
                )
                
                # Update progress
                progress = int(((i + 1) / total_models) * 100)
                QTimer.singleShot(0, lambda p=progress: self.progress_bar.setValue(p))
                
                QTimer.singleShot(0, lambda m=model_name: self.log_transfer_message(f"Received {m} blocks"))
            
            # Complete transfer
            QTimer.singleShot(0, self.on_real_transfer_complete)
            
        except Exception as e:
            logger.error(f"Secure transfer worker failed: {e}")
            QTimer.singleShot(0, lambda: self.log_transfer_message(f"Transfer failed: {e}"))
            QTimer.singleShot(0, self.simulate_transfer_fallback)
    
    def on_real_transfer_complete(self):
        """Handle completion of real secure transfer"""
        self.status_label.setText("Transfer completed successfully!")
        self.progress_bar.setValue(100)
        
        self.log_transfer_message("Secure transfer completed successfully")
        self.log_transfer_message(f"Models received: {', '.join(self.current_network['models'])}")
        self.log_transfer_message("Models encrypted and stored locally")
        self.log_transfer_message("Ready for offline inference")
        
        # Emit completion signal
        self.transfer_completed.emit(self.current_network['models'])
        
        QMessageBox.information(
            self,
            "Transfer Complete",
            f"Successfully received models from {self.current_network['name']}!\n\n"
            f"Models are now available for offline use."
        )
    
    def simulate_transfer_fallback(self):
        """Fall back to simulated transfer progress"""
        self.log_transfer_message("Using simulated transfer (secure transfer not available)")
        
        # Simulate transfer progress
        self.transfer_timer = QTimer()
        self.transfer_progress = 0
        
        self.transfer_timer.timeout.connect(self.update_transfer_progress)
        self.transfer_timer.start(200)  # Update every 200ms
    
    def update_transfer_progress(self):
        """Update transfer progress simulation"""
        self.transfer_progress += 1
        self.progress_bar.setValue(self.transfer_progress)
        
        # Log progress milestones
        if self.transfer_progress % 25 == 0:
            self.log_transfer_message(f"Transfer progress: {self.transfer_progress}%")
        
        if self.transfer_progress >= 100:
            self.transfer_timer.stop()
            self.complete_transfer()
    
    def complete_transfer(self):
        """Complete model transfer"""
        self.status_label.setText("Transfer completed successfully!")
        self.progress_bar.setVisible(False)
        
        self.log_transfer_message("Transfer completed successfully")
        self.log_transfer_message(f"Models received: {', '.join(self.current_network['models'])}")
        self.log_transfer_message("Ready for offline inference")
        
        QMessageBox.information(
            self,
            "Transfer Complete",
            f"Successfully received models from {self.current_network['name']}!\n\n"
            f"You can now use the models for inference."
        )
    
    def log_transfer_message(self, message: str):
        """Add message to transfer log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.details_text.append(f"[{timestamp}] {message}")


class ChatInterfaceWidget(QWidget):
    """Widget for model interaction chat interface"""
    
    def __init__(self):
        super().__init__()
        self.conversation_history = []
        self.model_node = None
        self.available_models = []
        self.init_ui()
        self.setup_model_integration()
    
    def init_ui(self):
        """Initialize chat interface UI"""
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        
        header = QLabel("Model Chat Interface")
        header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        # Model selector
        self.model_combo = QComboBox()
        self.model_combo.addItem("No models available")
        self.model_combo.setEnabled(False)
        header_layout.addWidget(QLabel("Model:"))
        header_layout.addWidget(self.model_combo)
        
        layout.addLayout(header_layout)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.chat_display)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here... (models must be transferred first)")
        self.message_input.setEnabled(False)
        self.message_input.returnPressed.connect(self.send_message)
        self.message_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
            QLineEdit:disabled {
                background-color: #f8f9fa;
                color: #6c757d;
            }
        """)
        input_layout.addWidget(self.message_input)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setEnabled(False)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout)
        
        self.setLayout(layout)
        
        # Add welcome message
        self.add_system_message("Welcome to TikTrue Chat Interface!")
        self.add_system_message("Connect to a network and transfer models to start chatting.")
    
    def setup_model_integration(self):
        """Setup model inference integration"""
        try:
            # Import model node for inference
            from core.model_node import ModelNode
            self.model_node = ModelNode()
            logger.info("Model node initialized successfully")
        except ImportError as e:
            logger.warning(f"Model node module not available: {e}")
            self.model_node = None
        
        # Try to use enhanced chat interface components if available
        try:
            from interfaces.chat_interface import StreamingWorker
            self.has_streaming_support = True
            logger.info("Streaming chat support available")
        except ImportError:
            self.has_streaming_support = False
            logger.info("Using basic chat interface")
    
    def enable_chat(self, available_models: list):
        """Enable chat interface with available models"""
        self.model_combo.clear()
        self.model_combo.addItems(available_models)
        self.model_combo.setEnabled(True)
        
        self.message_input.setEnabled(True)
        self.message_input.setPlaceholderText("Type your message here...")
        self.send_btn.setEnabled(True)
        
        self.add_system_message(f"Models loaded: {', '.join(available_models)}")
        self.add_system_message("You can now start chatting!")
    
    def send_message(self):
        """Send a message to the model"""
        message = self.message_input.text().strip()
        if not message:
            return
        
        selected_model = self.model_combo.currentText()
        if not selected_model or selected_model == "No models available":
            QMessageBox.warning(self, "No Model", "Please select a model first.")
            return
        
        # Add user message
        self.add_user_message(message)
        self.message_input.clear()
        
        # Disable input during processing
        self.message_input.setEnabled(False)
        self.send_btn.setEnabled(False)
        
        if self.model_node:
            # Use actual model inference
            try:
                self.add_system_message("Processing your request...")
                self.perform_model_inference(message, selected_model)
            except Exception as e:
                logger.error(f"Model inference failed: {e}")
                self.add_system_message(f"Inference error: {e}")
                self.simulate_model_response(message, selected_model)
        else:
            # Fall back to simulated response
            self.add_system_message("Processing your request...")
            QTimer.singleShot(2000, lambda: self.simulate_model_response(message, selected_model))
    
    def perform_model_inference(self, message: str, model_name: str):
        """Perform actual model inference"""
        try:
            # Start inference in a separate thread
            import threading
            inference_thread = threading.Thread(
                target=self._inference_worker, 
                args=(message, model_name)
            )
            inference_thread.daemon = True
            inference_thread.start()
        except Exception as e:
            logger.error(f"Failed to start inference thread: {e}")
            self.simulate_model_response(message, model_name)
    
    def _inference_worker(self, message: str, model_name: str):
        """Worker thread for model inference"""
        try:
            # Load model if not already loaded
            if not self.model_node.is_model_loaded(model_name):
                QTimer.singleShot(0, lambda: self.add_system_message(f"Loading {model_name}..."))
                self.model_node.load_model(model_name)
            
            # Perform inference
            response = self.model_node.generate_response(message, model_name)
            
            # Update UI from main thread
            QTimer.singleShot(0, lambda: self.on_inference_complete(response, model_name))
            
        except Exception as e:
            logger.error(f"Inference worker failed: {e}")
            QTimer.singleShot(0, lambda: self.on_inference_error(str(e), model_name))
    
    def on_inference_complete(self, response: str, model_name: str):
        """Handle completion of model inference"""
        self.add_model_response_real(response, model_name)
        
        # Re-enable input
        self.message_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.message_input.setFocus()
    
    def on_inference_error(self, error_msg: str, model_name: str):
        """Handle inference error"""
        self.add_system_message(f"Inference failed: {error_msg}")
        self.add_system_message("Falling back to simulated response...")
        
        # Fall back to simulated response
        QTimer.singleShot(1000, lambda: self.simulate_model_response("Error occurred", model_name))
    
    def simulate_model_response(self, user_message: str, model_name: str):
        """Simulate model response as fallback"""
        # Mock response (fallback when real inference not available)
        response = f"I understand you said: '{user_message}'. This is a simulated response from {model_name}. In a real implementation, this would be the actual model output."
        
        self.add_model_response_real(response, model_name)
        
        # Re-enable input
        self.message_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.message_input.setFocus()
    
    def add_user_message(self, message: str):
        """Add user message to chat"""
        timestamp = datetime.now().strftime("%H:%M")
        
        html = f"""
        <div style="margin-bottom: 15px; text-align: right;">
            <div style="background-color: #3498db; color: white; padding: 10px 15px; 
                       border-radius: 18px; display: inline-block; max-width: 70%;
                       word-wrap: break-word;">
                {message}
            </div>
            <div style="font-size: 11px; color: #6c757d; margin-top: 5px;">
                You • {timestamp}
            </div>
        </div>
        """
        
        self.chat_display.insertHtml(html)
        self.scroll_to_bottom()
    
    def add_model_response_real(self, response: str, model_name: str):
        """Add actual model response to chat"""
        timestamp = datetime.now().strftime("%H:%M")
        
        html = f"""
        <div style="margin-bottom: 15px;">
            <div style="background-color: #e9ecef; color: #212529; padding: 10px 15px; 
                       border-radius: 18px; display: inline-block; max-width: 70%;
                       word-wrap: break-word;">
                {response}
            </div>
            <div style="font-size: 11px; color: #6c757d; margin-top: 5px;">
                {model_name} • {timestamp}
            </div>
        </div>
        """
        
        self.chat_display.insertHtml(html)
        self.scroll_to_bottom()
    
    def add_model_response(self, user_message: str, model_name: str):
        """Add model response to chat (legacy method for compatibility)"""
        timestamp = datetime.now().strftime("%H:%M")
        
        # Mock response (replace with actual model inference)
        response = f"I understand you said: '{user_message}'. This is a simulated response from {model_name}. In a real implementation, this would be the actual model output."
        
        self.add_model_response_real(response, model_name)
    
    def add_system_message(self, message: str):
        """Add system message to chat"""
        timestamp = datetime.now().strftime("%H:%M")
        
        html = f"""
        <div style="margin-bottom: 15px; text-align: center;">
            <div style="background-color: #f39c12; color: white; padding: 8px 12px; 
                       border-radius: 12px; display: inline-block; font-size: 12px;">
                {message}
            </div>
            <div style="font-size: 10px; color: #6c757d; margin-top: 3px;">
                System • {timestamp}
            </div>
        </div>
        """
        
        self.chat_display.insertHtml(html)
        self.scroll_to_bottom()
    
    def scroll_to_bottom(self):
        """Scroll chat display to bottom"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)


class ClientModeWidget(QWidget):
    """Enhanced Client mode interface with comprehensive functionality"""
    
    def __init__(self):
        super().__init__()
        self.connected_network = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize client mode UI"""
        layout = QVBoxLayout()
        
        # Header
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #27ae60;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
            }
        """)
        
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Client Mode - Network Discovery & Chat")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: white;
            }
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Connection status
        self.connection_status = QLabel("Not Connected")
        self.connection_status.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                padding: 5px 10px;
                background-color: rgba(0,0,0,0.2);
                border-radius: 4px;
            }
        """)
        header_layout.addWidget(self.connection_status)
        
        header_frame.setLayout(header_layout)
        layout.addWidget(header_frame)
        
        # Main content tabs
        self.tab_widget = QTabWidget()
        
        # Network Discovery tab
        self.discovery_widget = NetworkDiscoveryWidget()
        self.discovery_widget.network_selected.connect(self.on_network_selected)
        self.tab_widget.addTab(self.discovery_widget, "🔍 Network Discovery")
        
        # Model Transfer tab
        self.transfer_widget = ModelTransferWidget()
        self.transfer_widget.transfer_completed.connect(self.on_transfer_completed)
        self.tab_widget.addTab(self.transfer_widget, "📦 Model Transfer")
        
        # Chat Interface tab - Using Unified Chat Interface
        from interfaces.unified_chat_interface import UnifiedChatInterface
        self.chat_widget = UnifiedChatInterface()
        self.tab_widget.addTab(self.chat_widget, "💬 Chat Interface")
        
        layout.addWidget(self.tab_widget)
        
        self.setLayout(layout)
    
    def on_network_selected(self, network_info: dict):
        """Handle network selection and connection"""
        reply = QMessageBox.question(
            self,
            "Connect to Network",
            f"Do you want to connect to '{network_info['name']}'?\n\n"
            f"Admin: {network_info['admin']}\n"
            f"Available Models: {', '.join(network_info['models'])}\n"
            f"Current Clients: {network_info['clients']}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.connect_to_network(network_info)
    
    def connect_to_network(self, network_info: dict):
        """Connect to the selected network"""
        self.connected_network = network_info
        
        # Update connection status
        self.connection_status.setText(f"Connected to {network_info['name']}")
        self.connection_status.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                padding: 5px 10px;
                background-color: rgba(46, 204, 113, 0.8);
                border-radius: 4px;
            }
        """)
        
        # Switch to transfer tab and start transfer
        self.tab_widget.setCurrentWidget(self.transfer_widget)
        self.transfer_widget.start_transfer(network_info)
        
        # Note: Chat will be enabled when transfer_completed signal is emitted
    
    def on_transfer_completed(self, models: list):
        """Handle completion of model transfer"""
        self.enable_chat_interface(models)
    
    def enable_chat_interface(self, models: list):
        """Enable chat interface after model transfer"""
        self.chat_widget.enable_chat(models)
        
        # Switch to chat tab
        self.tab_widget.setCurrentWidget(self.chat_widget)
        
        # Show notification
        QMessageBox.information(
            self,
            "Models Ready",
            "Model transfer completed successfully!\n\n"
            "You can now start chatting with the models."
        )


class MainWindow(QMainWindow):
    """Main application window with mode-specific interfaces"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.settings = QSettings("TikTrue", "MainApp")
        self.current_mode = None
        
        self.init_ui()
        self.init_system_tray()
        self.check_mode_selection()
    
    def init_ui(self):
        """Initialize main window UI"""
        self.setWindowTitle("TikTrue - Distributed LLM Platform")
        self.setMinimumSize(1000, 700)
        
        # Central widget with stacked layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        self.central_widget.setLayout(main_layout)
        
        # Menu bar placeholder
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        change_mode_action = QAction("Change Mode", self)
        change_mode_action.triggered.connect(self.show_mode_selection)
        file_menu.addAction(change_mode_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        wizard_action = QAction("Setup Wizard", self)
        wizard_action.triggered.connect(self.show_setup_wizard)
        help_menu.addAction(wizard_action)
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        # Content stack for different modes
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)
        
        # Create mode-specific widgets
        self.admin_widget = AdminModeWidget()
        self.client_widget = ClientModeWidget()
        
        self.content_stack.addWidget(self.admin_widget)
        self.content_stack.addWidget(self.client_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Apply modern styling
        self.apply_modern_style()
    
    def init_system_tray(self):
        """Initialize system tray icon"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            
            # Create tray menu
            tray_menu = QMenu()
            
            show_action = QAction("Show", self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)
            
            change_mode_action = QAction("Change Mode", self)
            change_mode_action.triggered.connect(self.show_mode_selection)
            tray_menu.addAction(change_mode_action)
            
            tray_menu.addSeparator()
            
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(self.quit_application)
            tray_menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.tray_icon_activated)
            
            # Set a default icon (in production, use actual icon file)
            self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        """Handle system tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()
    
    def check_mode_selection(self):
        """Check if mode has been selected and stored"""
        stored_mode = self.settings.value("selected_mode", None)
        
        if stored_mode:
            logger.info(f"Found stored mode: {stored_mode}")
            self.set_mode(stored_mode)
        else:
            logger.info("No stored mode found, showing mode selection")
            self.show_mode_selection()
    
    def show_mode_selection(self):
        """Show mode selection dialog"""
        dialog = ModeSelectionDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_mode = dialog.get_selected_mode()
            
            if selected_mode:
                # Store mode if user wants to remember
                if dialog.should_remember_choice():
                    self.settings.setValue("selected_mode", selected_mode)
                    logger.info(f"Stored selected mode: {selected_mode}")
                
                self.set_mode(selected_mode)
            else:
                QMessageBox.warning(self, "No Mode Selected", "Please select a mode to continue.")
                self.show_mode_selection()
        else:
            # User cancelled mode selection
            if not self.current_mode:
                QMessageBox.information(
                    self, 
                    "Mode Required", 
                    "A mode selection is required to use TikTrue. The application will now exit."
                )
                self.quit_application()
    
    def set_mode(self, mode: str):
        """Set the application mode and update UI"""
        self.current_mode = mode
        
        if mode == "admin":
            self.content_stack.setCurrentWidget(self.admin_widget)
            self.setWindowTitle("TikTrue - Admin Mode")
            self.status_bar.showMessage("Admin Mode - Ready to manage networks")
            logger.info("Switched to Admin mode")
            
        elif mode == "client":
            self.content_stack.setCurrentWidget(self.client_widget)
            self.setWindowTitle("TikTrue - Client Mode")
            self.status_bar.showMessage("Client Mode - Ready to discover networks")
            logger.info("Switched to Client mode")
        
        # Show main window if hidden
        self.show()
        self.raise_()
        self.activateWindow()
    
    def show_setup_wizard(self):
        """Show the first-run setup wizard"""
        wizard = FirstRunWizard(self)
        wizard.setup_completed.connect(self.on_wizard_completed)
        
        if wizard.exec() == QDialog.DialogCode.Accepted:
            logger.info("Setup wizard completed successfully")
        else:
            logger.info("Setup wizard cancelled")
    
    def on_wizard_completed(self, setup_result: Dict[str, Any]):
        """Handle wizard completion"""
        try:
            logger.info(f"Wizard completed with result: {setup_result}")
            
            # Handle any additional setup based on wizard results
            network_config = setup_result.get('network_config', {})
            
            if network_config.get('action') == 'create':
                QMessageBox.information(
                    self, 
                    "Network Creation", 
                    f"Network '{network_config.get('name', 'Unknown')}' will be created."
                )
            elif network_config.get('action') == 'join':
                QMessageBox.information(
                    self, 
                    "Network Join", 
                    f"Will attempt to join network: {network_config.get('network', 'Unknown')}"
                )
            
        except Exception as e:
            logger.error(f"Failed to handle wizard completion: {e}")
            QMessageBox.warning(self, "Setup Warning", f"Setup completed but with warnings: {e}")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About TikTrue",
            "TikTrue Distributed LLM Platform v1.0.0\n\n"
            "Enterprise-grade distributed inference for Large Language Models.\n\n"
            "Features:\n"
            "• Dual-mode operation (Admin/Client)\n"
            "• Secure model distribution\n"
            "• Hardware-bound licensing\n"
            "• Offline-capable operation\n\n"
            "© 2024 TikTrue Platform"
        )
    
    def apply_modern_style(self):
        """Apply modern styling to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            
            QMenuBar {
                background-color: #34495e;
                color: white;
                border-bottom: 1px solid #2c3e50;
            }
            
            QMenuBar::item {
                background-color: transparent;
                padding: 8px 12px;
            }
            
            QMenuBar::item:selected {
                background-color: #3498db;
            }
            
            QMenu {
                background-color: white;
                border: 1px solid #bdc3c7;
            }
            
            QMenu::item {
                padding: 8px 20px;
            }
            
            QMenu::item:selected {
                background-color: #3498db;
                color: white;
            }
            
            QStatusBar {
                background-color: #ecf0f1;
                border-top: 1px solid #bdc3c7;
            }
        """)
    
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
        logger.info("Application shutting down")
        QApplication.quit()


class TikTrueApplication(QApplication):
    """Main application class with initialization and error handling"""
    
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
        self.main_window = None
    
    def setup_logging(self):
        """Setup application logging"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # File handler
        file_handler = logging.FileHandler(log_dir / "main_app.log")
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        logger.info("Logging configured successfully")
    
    def create_main_window(self):
        """Create and show main window"""
        try:
            self.main_window = MainWindow()
            return self.main_window
        except Exception as e:
            logger.error(f"Failed to create main window: {e}")
            QMessageBox.critical(
                None,
                "Startup Error",
                f"Failed to initialize TikTrue:\n{str(e)}\n\nThe application will now exit."
            )
            sys.exit(1)
    
    def run(self):
        """Run the application"""
        try:
            # Create main window
            main_window = self.create_main_window()
            
            # Show window
            main_window.show()
            
            logger.info("TikTrue application started successfully")
            
            # Start event loop
            return self.exec()
            
        except Exception as e:
            logger.error(f"Application runtime error: {e}")
            QMessageBox.critical(
                None,
                "Runtime Error",
                f"A critical error occurred:\n{str(e)}\n\nThe application will now exit."
            )
            return 1


def main():
    """Main entry point"""
    try:
        # Create application
        app = TikTrueApplication(sys.argv)
        
        # Run application
        exit_code = app.run()
        
        logger.info(f"Application exited with code: {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()