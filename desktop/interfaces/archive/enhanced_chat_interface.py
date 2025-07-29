"""
Enhanced Chat Interface with Session Management
Extends the existing chat interface with comprehensive session management capabilities
"""

import sys
import json
import logging
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

# PyQt6 imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QComboBox, QLabel, QFrame, QScrollArea,
    QSplitter, QListWidget, QListWidgetItem, QGroupBox,
    QProgressBar, QMessageBox, QMenu, QToolButton, QSpacerItem,
    QSizePolicy, QApplication, QMainWindow, QMenuBar, QStatusBar
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation,
    QEasingCurve, QRect, QSize, QObject
)
from PyQt6.QtGui import (
    QFont, QTextCursor, QTextCharFormat, QColor, QPalette,
    QAction, QIcon, QPixmap, QTextDocument, QSyntaxHighlighter
)

# Import our modules
from interfaces.chat_interface import AdvancedChatInterface, ChatMessage, MessageType
from session_manager import SessionManager, Session, get_session_manager
from interfaces.session_ui import SessionListWidget, SessionManagementDialog, SessionInfoWidget
from security.license_validator import LicenseInfo, SubscriptionTier
from license_storage import LicenseStorage

logger = logging.getLogger("EnhancedChatInterface")


class SessionAwareChatInterface(AdvancedChatInterface):
    """Enhanced chat interface with session management"""
    
    # Signals
    session_changed = pyqtSignal(Session)  # Emitted when active session changes
    session_saved = pyqtSignal(Session)    # Emitted when session is saved
    
    def __init__(self, parent=None):
        # Initialize session management first
        self.session_manager = get_session_manager()
        self.current_session: Optional[Session] = None
        self.license_info: Optional[LicenseInfo] = None
        self.auto_save_enabled = True
        self.auto_save_timer = QTimer()
        
        # Initialize parent
        super().__init__(parent)
        
        # Load license info
        self.load_license_info()
        
        # Setup session management
        self.setup_session_management()
        
        # Setup auto-save
        self.setup_auto_save()
    
    def load_license_info(self):
        """Load license information"""
        try:
            license_storage = LicenseStorage()
            self.license_info = license_storage.load_license_info()
            
            if self.license_info and self.license_info.is_valid:
                logger.info(f"Loaded license: {self.license_info.tier.value}")
            else:
                logger.warning("No valid license found")
                
        except Exception as e:
            logger.error(f"Failed to load license info: {e}")
    
    def setup_session_management(self):
        """Setup session management components"""
        # Create or load default session
        if not self.session_manager.get_all_sessions():
            # Create first session
            self.current_session = self.session_manager.create_session("New Chat")
        else:
            # Load the most recent session
            sessions = self.session_manager.get_all_sessions()
            self.current_session = sessions[0] if sessions else None
            if self.current_session:
                self.session_manager.set_active_session(self.current_session.session_id)
        
        # Load session messages into chat history
        if self.current_session:
            self.load_session_messages()
    
    def setup_auto_save(self):
        """Setup automatic session saving"""
        self.auto_save_timer.timeout.connect(self.auto_save_session)
        self.auto_save_timer.setSingleShot(True)
    
    def init_ui(self):
        """Initialize enhanced UI with session management"""
        # Call parent init_ui first
        super().init_ui()
        
        # Get the main layout
        main_layout = self.layout()
        
        # Create session management panel
        self.create_session_panel()
        
        # Insert session panel at the top
        main_layout.insertWidget(0, self.session_panel)
        
        # Add session menu to existing header
        self.add_session_controls()
    
    def create_session_panel(self):
        """Create session management panel"""
        self.session_panel = QFrame()
        self.session_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        self.session_panel.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        
        layout = QHBoxLayout(self.session_panel)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Session info
        self.session_info_label = QLabel("No session")
        self.session_info_label.setStyleSheet("font-weight: bold; color: #495057;")
        layout.addWidget(self.session_info_label)
        
        layout.addStretch()
        
        # Session controls
        self.new_session_btn = QToolButton()
        self.new_session_btn.setText("New")
        self.new_session_btn.setToolTip("New Session")
        self.new_session_btn.clicked.connect(self.create_new_session)
        layout.addWidget(self.new_session_btn)
        
        self.save_session_btn = QToolButton()
        self.save_session_btn.setText("Save")
        self.save_session_btn.setToolTip("Save Session")
        self.save_session_btn.clicked.connect(self.save_current_session)
        layout.addWidget(self.save_session_btn)
        
        self.manage_sessions_btn = QToolButton()
        self.manage_sessions_btn.setText("Manage")
        self.manage_sessions_btn.setToolTip("Manage Sessions")
        self.manage_sessions_btn.clicked.connect(self.show_session_management)
        layout.addWidget(self.manage_sessions_btn)
        
        # Update session info
        self.update_session_info()
    
    def add_session_controls(self):
        """Add session controls to existing header"""
        # This would integrate with the existing header layout
        # For now, we use the session panel above
        pass
    
    def update_session_info(self):
        """Update session information display"""
        if self.current_session:
            message_count = len(self.current_session.messages)
            self.session_info_label.setText(
                f"{self.current_session.name} ({message_count} messages)"
            )
            
            # Check message limits
            if self.license_info:
                can_add, current, limit = self.session_manager.check_message_limits(
                    self.current_session, self.license_info
                )
                
                if not can_add:
                    self.session_info_label.setStyleSheet(
                        "font-weight: bold; color: #dc3545;"
                    )
                    self.session_info_label.setToolTip(
                        f"Message limit reached ({current}/{limit})"
                    )
                else:
                    self.session_info_label.setStyleSheet(
                        "font-weight: bold; color: #495057;"
                    )
                    self.session_info_label.setToolTip("")
        else:
            self.session_info_label.setText("No session")
            self.session_info_label.setStyleSheet("font-weight: bold; color: #6c757d;")
    
    def create_new_session(self):
        """Create a new session"""
        try:
            # Check session limits
            if self.license_info:
                can_add, current, limit = self.session_manager.check_session_limits(self.license_info)
                if not can_add:
                    QMessageBox.warning(
                        self,
                        "Session Limit Reached",
                        f"You have reached the maximum number of sessions ({limit}) "
                        f"for your {self.license_info.tier.value} subscription.\n\n"
                        f"Please delete some sessions or upgrade your subscription."
                    )
                    return
            
            # Save current session first
            if self.current_session:
                self.save_current_session()
            
            # Create new session
            session_name = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            new_session = self.session_manager.create_session(session_name)
            
            # Switch to new session
            self.switch_to_session(new_session)
            
            logger.info(f"Created new session: {new_session.name}")
            
        except Exception as e:
            logger.error(f"Failed to create new session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create new session: {e}")
    
    def switch_to_session(self, session: Session):
        """Switch to a different session"""
        try:
            # Save current session first
            if self.current_session:
                self.save_current_session()
            
            # Switch to new session
            self.current_session = session
            self.session_manager.set_active_session(session.session_id)
            
            # Clear current chat history
            self.chat_history.clear_messages()
            
            # Load session messages
            self.load_session_messages()
            
            # Update UI
            self.update_session_info()
            
            # Emit signal
            self.session_changed.emit(session)
            
            logger.info(f"Switched to session: {session.name}")
            
        except Exception as e:
            logger.error(f"Failed to switch to session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to switch to session: {e}")
    
    def load_session_messages(self):
        """Load messages from current session into chat history"""
        if not self.current_session:
            return
        
        try:
            # Convert session messages to ChatMessage objects
            for msg_data in self.current_session.messages:
                try:
                    # Convert session message format to ChatMessage
                    message = ChatMessage(
                        id=f"{msg_data.get('role', 'unknown')}_{datetime.now().timestamp()}",
                        type=MessageType.USER if msg_data.get('role') == 'user' else MessageType.ASSISTANT,
                        content=msg_data.get('content', ''),
                        timestamp=datetime.now(),  # Use current time if not stored
                        metadata=msg_data.get('metadata', {})
                    )
                    
                    self.chat_history.add_message(message)
                    
                except Exception as e:
                    logger.error(f"Failed to load message: {e}")
                    continue
            
            logger.info(f"Loaded {len(self.current_session.messages)} messages")
            
        except Exception as e:
            logger.error(f"Failed to load session messages: {e}")
    
    def save_current_session(self):
        """Save the current session"""
        if not self.current_session:
            return
        
        try:
            # Get current messages from chat history
            current_messages = []
            
            # Convert ChatMessage objects back to session format
            for message in self.chat_history.get_all_messages():
                msg_data = {
                    'role': 'user' if message.type == MessageType.USER else 'assistant',
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'metadata': message.metadata or {}
                }
                current_messages.append(msg_data)
            
            # Update session messages
            self.current_session.messages = current_messages
            
            # Save to disk
            if self.session_manager.save_session(self.current_session):
                logger.info(f"Saved session: {self.current_session.name}")
                self.session_saved.emit(self.current_session)
            else:
                logger.error("Failed to save session")
                
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def auto_save_session(self):
        """Auto-save the current session"""
        if self.auto_save_enabled and self.current_session:
            self.save_current_session()
    
    def schedule_auto_save(self):
        """Schedule an auto-save"""
        if self.auto_save_enabled:
            self.auto_save_timer.start(5000)  # 5 seconds delay
    
    def show_session_management(self):
        """Show session management dialog"""
        try:
            dialog = SessionManagementDialog(
                self.session_manager,
                self.license_info,
                self
            )
            
            # Connect signals
            dialog.session_widget.session_selected.connect(self.switch_to_session)
            
            dialog.exec()
            
            # Update current session info after dialog closes
            self.update_session_info()
            
        except Exception as e:
            logger.error(f"Failed to show session management: {e}")
            QMessageBox.critical(self, "Error", f"Failed to show session management: {e}")
    
    def on_message_sent(self, message: str):
        """Override parent method to add session management"""
        # Check message limits
        if self.license_info and self.current_session:
            can_add, current, limit = self.session_manager.check_message_limits(
                self.current_session, self.license_info
            )
            
            if not can_add:
                QMessageBox.warning(
                    self,
                    "Message Limit Reached",
                    f"You have reached the maximum number of messages ({limit}) "
                    f"for your {self.license_info.tier.value} subscription in this session.\n\n"
                    f"Please start a new session or upgrade your subscription."
                )
                return
        
        # Call parent method
        super().on_message_sent(message)
        
        # Schedule auto-save
        self.schedule_auto_save()
        
        # Update session info
        self.update_session_info()
    
    def on_response_received(self, response: str):
        """Handle response received (override if parent has this method)"""
        # Schedule auto-save after receiving response
        self.schedule_auto_save()
        
        # Update session info
        self.update_session_info()
    
    def closeEvent(self, event):
        """Handle close event"""
        try:
            # Save current session before closing
            if self.current_session:
                self.save_current_session()
            
            # Call parent close event
            super().closeEvent(event)
            
        except Exception as e:
            logger.error(f"Error during close: {e}")
            event.accept()  # Close anyway


class SessionAwareChatWindow(QMainWindow):
    """Main window with session-aware chat interface"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setup_menu()
        self.setup_status_bar()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Distributed LLM Platform - Chat")
        self.setMinimumSize(1000, 700)
        
        # Create central widget
        self.chat_interface = SessionAwareChatInterface()
        self.setCentralWidget(self.chat_interface)
        
        # Connect signals
        self.chat_interface.session_changed.connect(self.on_session_changed)
        self.chat_interface.session_saved.connect(self.on_session_saved)
    
    def setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        
        # Session menu
        session_menu = menubar.addMenu("Session")
        
        new_action = QAction("New Session", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.chat_interface.create_new_session)
        session_menu.addAction(new_action)
        
        save_action = QAction("Save Session", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.chat_interface.save_current_session)
        session_menu.addAction(save_action)
        
        session_menu.addSeparator()
        
        manage_action = QAction("Manage Sessions...", self)
        manage_action.triggered.connect(self.chat_interface.show_session_management)
        session_menu.addAction(manage_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        toggle_session_panel = QAction("Toggle Session Panel", self)
        toggle_session_panel.setCheckable(True)
        toggle_session_panel.setChecked(True)
        toggle_session_panel.triggered.connect(self.toggle_session_panel)
        view_menu.addAction(toggle_session_panel)
    
    def setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Add session info to status bar
        self.session_status_label = QLabel("No session")
        self.status_bar.addPermanentWidget(self.session_status_label)
    
    def toggle_session_panel(self, checked: bool):
        """Toggle session panel visibility"""
        self.chat_interface.session_panel.setVisible(checked)
    
    def on_session_changed(self, session):
        """Handle session change"""
        self.session_status_label.setText(f"Session: {session.name}")
        self.status_bar.showMessage(f"Switched to session: {session.name}", 3000)
    
    def on_session_saved(self, session):
        """Handle session saved"""
        self.status_bar.showMessage(f"Session saved: {session.name}", 2000)


# Test application
if __name__ == "__main__":
    import sys
    import tempfile
    import shutil
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Create main window
    window = SessionAwareChatWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec())