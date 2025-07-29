"""
Session Management UI Components
Provides UI for session management, saving/loading conversations, and session history
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

# PyQt6 imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMenu, QDialog, QLineEdit,
    QFormLayout, QDialogButtonBox, QMessageBox, QFileDialog,
    QFrame, QSplitter, QApplication, QMainWindow, QToolButton,
    QScrollArea, QSizePolicy, QSpacerItem, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QAction, QFont

# Import our modules
from session_manager import SessionManager, Session, format_timestamp
from security.license_validator import LicenseInfo, SubscriptionTier
from license_storage import LicenseStorage

logger = logging.getLogger("SessionUI")


class SessionListItem(QListWidgetItem):
    """Custom list item for sessions"""
    
    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.update_display()
    
    def update_display(self):
        """Update item display"""
        self.setText(self.session.name)
        self.setToolTip(
            f"Created: {self.session.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Updated: {self.session.updated_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Messages: {len(self.session.messages)}"
        )


class SessionListWidget(QWidget):
    """Widget for displaying and managing sessions"""
    
    session_selected = pyqtSignal(Session)  # Emitted when a session is selected
    session_created = pyqtSignal(Session)   # Emitted when a new session is created
    session_deleted = pyqtSignal(str)       # Emitted when a session is deleted (session_id)
    session_renamed = pyqtSignal(Session)   # Emitted when a session is renamed
    
    def __init__(self, session_manager: SessionManager, license_info: Optional[LicenseInfo] = None):
        super().__init__()
        self.session_manager = session_manager
        self.license_info = license_info
        self.init_ui()
        self.refresh_sessions()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Sessions")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # New session button
        self.new_btn = QToolButton()
        self.new_btn.setText("+")
        self.new_btn.setToolTip("New Session")
        self.new_btn.setStyleSheet("""
            QToolButton {
                font-size: 16px;
                font-weight: bold;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
                background-color: #28a745;
                color: white;
            }
            QToolButton:hover {
                background-color: #218838;
            }
        """)
        self.new_btn.clicked.connect(self.create_new_session)
        header_layout.addWidget(self.new_btn)
        
        layout.addLayout(header_layout)
        
        # Session list
        self.session_list = QListWidget()
        self.session_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e9ecef;
                color: #212529;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
        """)
        self.session_list.itemClicked.connect(self.on_session_selected)
        self.session_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.session_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.session_list)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 11px; color: #6c757d;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def refresh_sessions(self):
        """Refresh session list"""
        try:
            self.session_list.clear()
            
            # Get all sessions
            sessions = self.session_manager.get_all_sessions()
            
            # Add to list
            for session in sessions:
                item = SessionListItem(session)
                self.session_list.addItem(item)
            
            # Update status
            self.update_status()
            
        except Exception as e:
            logger.error(f"Failed to refresh sessions: {e}")
    
    def update_status(self):
        """Update status label"""
        try:
            if self.license_info:
                can_add, current, limit = self.session_manager.check_session_limits(self.license_info)
                
                if limit == float('inf'):
                    self.status_label.setText(f"{current} sessions")
                else:
                    self.status_label.setText(f"{current}/{limit} sessions")
                
                # Update new button state
                self.new_btn.setEnabled(can_add)
                
            else:
                self.status_label.setText(f"{len(self.session_manager.get_all_sessions())} sessions")
                
        except Exception as e:
            logger.error(f"Failed to update status: {e}")
    
    def create_new_session(self):
        """Create a new session"""
        try:
            # Check license limits
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
            
            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("New Session")
            dialog.setMinimumWidth(300)
            
            # Layout
            layout = QVBoxLayout(dialog)
            
            # Form
            form_layout = QFormLayout()
            name_input = QLineEdit()
            name_input.setText(f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            form_layout.addRow("Session Name:", name_input)
            layout.addLayout(form_layout)
            
            # Buttons
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            # Show dialog
            if dialog.exec() == QDialog.DialogCode.Accepted:
                session_name = name_input.text().strip()
                if not session_name:
                    session_name = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                
                # Create session
                session = self.session_manager.create_session(session_name)
                
                # Add to list
                item = SessionListItem(session)
                self.session_list.addItem(item)
                self.session_list.setCurrentItem(item)
                
                # Update status
                self.update_status()
                
                # Emit signal
                self.session_created.emit(session)
                
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create session: {e}")
    
    def on_session_selected(self, item: SessionListItem):
        """Handle session selection"""
        try:
            session = item.session
            self.session_manager.set_active_session(session.session_id)
            self.session_selected.emit(session)
            
        except Exception as e:
            logger.error(f"Failed to select session: {e}")
    
    def show_context_menu(self, position):
        """Show context menu for session item"""
        try:
            item = self.session_list.itemAt(position)
            if not item:
                return
            
            session = item.session
            
            # Create menu
            menu = QMenu()
            
            # Rename action
            rename_action = QAction("Rename", self)
            rename_action.triggered.connect(lambda: self.rename_session(session))
            menu.addAction(rename_action)
            
            # Export action
            export_action = QAction("Export", self)
            export_action.triggered.connect(lambda: self.export_session(session))
            menu.addAction(export_action)
            
            menu.addSeparator()
            
            # Delete action
            delete_action = QAction("Delete", self)
            delete_action.triggered.connect(lambda: self.delete_session(session))
            menu.addAction(delete_action)
            
            # Show menu
            menu.exec(self.session_list.mapToGlobal(position))
            
        except Exception as e:
            logger.error(f"Failed to show context menu: {e}")
    
    def rename_session(self, session: Session):
        """Rename a session"""
        try:
            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Rename Session")
            dialog.setMinimumWidth(300)
            
            # Layout
            layout = QVBoxLayout(dialog)
            
            # Form
            form_layout = QFormLayout()
            name_input = QLineEdit()
            name_input.setText(session.name)
            form_layout.addRow("Session Name:", name_input)
            layout.addLayout(form_layout)
            
            # Buttons
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            # Show dialog
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_name = name_input.text().strip()
                if new_name and new_name != session.name:
                    # Rename session
                    if self.session_manager.rename_session(session.session_id, new_name):
                        # Update item
                        for i in range(self.session_list.count()):
                            item = self.session_list.item(i)
                            if item.session.session_id == session.session_id:
                                item.session.name = new_name
                                item.update_display()
                                break
                        
                        # Emit signal
                        self.session_renamed.emit(session)
                        
        except Exception as e:
            logger.error(f"Failed to rename session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to rename session: {e}")
    
    def export_session(self, session: Session):
        """Export a session"""
        try:
            # Get export path
            export_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Session",
                os.path.expanduser(f"~/Documents/{session.name}.json"),
                "JSON Files (*.json)"
            )
            
            if export_path:
                # Export session
                if self.session_manager.export_session(session.session_id, export_path):
                    QMessageBox.information(
                        self,
                        "Export Successful",
                        f"Session '{session.name}' exported successfully."
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Export Failed",
                        f"Failed to export session '{session.name}'."
                    )
                    
        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to export session: {e}")
    
    def delete_session(self, session: Session):
        """Delete a session"""
        try:
            # Confirm deletion
            result = QMessageBox.question(
                self,
                "Delete Session",
                f"Are you sure you want to delete session '{session.name}'?\n\n"
                f"This action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if result == QMessageBox.StandardButton.Yes:
                # Delete session
                if self.session_manager.delete_session(session.session_id):
                    # Remove from list
                    for i in range(self.session_list.count()):
                        item = self.session_list.item(i)
                        if item.session.session_id == session.session_id:
                            self.session_list.takeItem(i)
                            break
                    
                    # Update status
                    self.update_status()
                    
                    # Emit signal
                    self.session_deleted.emit(session.session_id)
                    
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to delete session: {e}")
    
    def import_session(self):
        """Import a session"""
        try:
            # Check license limits
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
            
            # Get import path
            import_path, _ = QFileDialog.getOpenFileName(
                self,
                "Import Session",
                os.path.expanduser("~/Documents"),
                "JSON Files (*.json)"
            )
            
            if import_path:
                # Import session
                session = self.session_manager.import_session(import_path)
                if session:
                    # Add to list
                    item = SessionListItem(session)
                    self.session_list.addItem(item)
                    self.session_list.setCurrentItem(item)
                    
                    # Update status
                    self.update_status()
                    
                    # Emit signal
                    self.session_created.emit(session)
                    
                    QMessageBox.information(
                        self,
                        "Import Successful",
                        f"Session imported successfully as '{session.name}'."
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Import Failed",
                        "Failed to import session. Please check the file format."
                    )
                    
        except Exception as e:
            logger.error(f"Failed to import session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to import session: {e}")
    
    def set_license_info(self, license_info: Optional[LicenseInfo]):
        """Update license information"""
        self.license_info = license_info
        self.update_status()


class SessionManagementDialog(QDialog):
    """Dialog for advanced session management"""
    
    def __init__(self, session_manager: SessionManager, license_info: Optional[LicenseInfo] = None, parent=None):
        super().__init__(parent)
        self.session_manager = session_manager
        self.license_info = license_info
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Session Management")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Session Management")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Import button
        import_btn = QPushButton("Import Session")
        import_btn.clicked.connect(self.import_session)
        header_layout.addWidget(import_btn)
        
        # Backup button
        backup_btn = QPushButton("Backup All")
        backup_btn.clicked.connect(self.backup_sessions)
        header_layout.addWidget(backup_btn)
        
        # Restore button
        restore_btn = QPushButton("Restore")
        restore_btn.clicked.connect(self.restore_sessions)
        header_layout.addWidget(restore_btn)
        
        layout.addLayout(header_layout)
        
        # Session list widget
        self.session_widget = SessionListWidget(self.session_manager, self.license_info)
        layout.addWidget(self.session_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        # Cleanup button
        cleanup_btn = QPushButton("Cleanup Old Sessions")
        cleanup_btn.clicked.connect(self.cleanup_sessions)
        button_layout.addWidget(cleanup_btn)
        
        button_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def import_session(self):
        """Import a session"""
        self.session_widget.import_session()
    
    def backup_sessions(self):
        """Backup all sessions"""
        try:
            # Get backup directory
            backup_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Backup Directory",
                os.path.expanduser("~/Documents")
            )
            
            if backup_dir:
                # Create timestamped backup folder
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(backup_dir, f"session_backup_{timestamp}")
                
                # Backup sessions
                if self.session_manager.backup_sessions(backup_path):
                    QMessageBox.information(
                        self,
                        "Backup Successful",
                        f"Sessions backed up successfully to:\n{backup_path}"
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Backup Failed",
                        "Failed to backup sessions."
                    )
                    
        except Exception as e:
            logger.error(f"Failed to backup sessions: {e}")
            QMessageBox.critical(self, "Error", f"Failed to backup sessions: {e}")
    
    def restore_sessions(self):
        """Restore sessions from backup"""
        try:
            # Confirm restore
            result = QMessageBox.question(
                self,
                "Restore Sessions",
                "Restoring sessions will replace all current sessions.\n\n"
                "Are you sure you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if result == QMessageBox.StandardButton.Yes:
                # Get restore directory
                restore_dir = QFileDialog.getExistingDirectory(
                    self,
                    "Select Restore Directory",
                    os.path.expanduser("~/Documents")
                )
                
                if restore_dir:
                    # Restore sessions
                    count = self.session_manager.restore_sessions(restore_dir)
                    if count > 0:
                        # Refresh UI
                        self.session_widget.refresh_sessions()
                        
                        QMessageBox.information(
                            self,
                            "Restore Successful",
                            f"Successfully restored {count} sessions."
                        )
                    else:
                        QMessageBox.critical(
                            self,
                            "Restore Failed",
                            "Failed to restore sessions or no valid sessions found."
                        )
                        
        except Exception as e:
            logger.error(f"Failed to restore sessions: {e}")
            QMessageBox.critical(self, "Error", f"Failed to restore sessions: {e}")
    
    def cleanup_sessions(self):
        """Cleanup old sessions"""
        try:
            # Create cleanup dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Cleanup Old Sessions")
            dialog.setMinimumWidth(350)
            
            layout = QVBoxLayout(dialog)
            
            # Info label
            info_label = QLabel(
                "This will delete old sessions to free up space.\n"
                "Sessions will be deleted based on age and usage."
            )
            layout.addWidget(info_label)
            
            # Form
            form_layout = QFormLayout()
            
            # Max age
            age_input = QComboBox()
            age_input.addItems(["7 days", "14 days", "30 days", "60 days", "90 days"])
            age_input.setCurrentText("30 days")
            form_layout.addRow("Delete sessions older than:", age_input)
            
            # Keep minimum
            keep_input = QComboBox()
            keep_input.addItems(["3", "5", "10", "15", "20"])
            keep_input.setCurrentText("5")
            form_layout.addRow("Keep at least:", keep_input)
            
            layout.addLayout(form_layout)
            
            # Buttons
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            # Show dialog
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Parse values
                age_text = age_input.currentText()
                max_age_days = int(age_text.split()[0])
                keep_min = int(keep_input.currentText())
                
                # Cleanup sessions
                deleted_count = self.session_manager.cleanup_old_sessions(max_age_days, keep_min)
                
                if deleted_count > 0:
                    # Refresh UI
                    self.session_widget.refresh_sessions()
                    
                    QMessageBox.information(
                        self,
                        "Cleanup Complete",
                        f"Deleted {deleted_count} old sessions."
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Cleanup Complete",
                        "No sessions were deleted."
                    )
                    
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            QMessageBox.critical(self, "Error", f"Failed to cleanup sessions: {e}")


class SessionInfoWidget(QWidget):
    """Widget for displaying session information"""
    
    def __init__(self, session: Optional[Session] = None):
        super().__init__()
        self.session = session
        self.init_ui()
        self.update_session_info()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        self.title_label = QLabel("Session Information")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.title_label)
        
        # Session details
        self.details_layout = QFormLayout()
        
        self.name_label = QLabel("-")
        self.details_layout.addRow("Name:", self.name_label)
        
        self.created_label = QLabel("-")
        self.details_layout.addRow("Created:", self.created_label)
        
        self.updated_label = QLabel("-")
        self.details_layout.addRow("Last Updated:", self.updated_label)
        
        self.messages_label = QLabel("-")
        self.details_layout.addRow("Messages:", self.messages_label)
        
        layout.addLayout(self.details_layout)
        
        # Actions
        actions_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export_session)
        actions_layout.addWidget(self.export_btn)
        
        self.clear_btn = QPushButton("Clear Messages")
        self.clear_btn.clicked.connect(self.clear_messages)
        actions_layout.addWidget(self.clear_btn)
        
        actions_layout.addStretch()
        
        layout.addLayout(actions_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def set_session(self, session: Optional[Session]):
        """Set the session to display"""
        self.session = session
        self.update_session_info()
    
    def update_session_info(self):
        """Update session information display"""
        if self.session:
            self.name_label.setText(self.session.name)
            self.created_label.setText(self.session.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            self.updated_label.setText(format_timestamp(self.session.updated_at))
            self.messages_label.setText(str(len(self.session.messages)))
            
            self.export_btn.setEnabled(True)
            self.clear_btn.setEnabled(len(self.session.messages) > 0)
        else:
            self.name_label.setText("-")
            self.created_label.setText("-")
            self.updated_label.setText("-")
            self.messages_label.setText("-")
            
            self.export_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
    
    def export_session(self):
        """Export the current session"""
        if not self.session:
            return
        
        try:
            # Get export path
            export_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Session",
                os.path.expanduser(f"~/Documents/{self.session.name}.json"),
                "JSON Files (*.json)"
            )
            
            if export_path:
                # Export session
                from session_manager import get_session_manager
                session_manager = get_session_manager()
                if session_manager.export_session(self.session.session_id, export_path):
                    QMessageBox.information(
                        self,
                        "Export Successful",
                        f"Session '{self.session.name}' exported successfully."
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Export Failed",
                        f"Failed to export session '{self.session.name}'."
                    )
                    
        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            QMessageBox.critical(self, "Error", f"Failed to export session: {e}")
    
    def clear_messages(self):
        """Clear all messages in the session"""
        if not self.session:
            return
        
        try:
            # Confirm clear
            result = QMessageBox.question(
                self,
                "Clear Messages",
                f"Are you sure you want to clear all messages in session '{self.session.name}'?\n\n"
                f"This action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if result == QMessageBox.StandardButton.Yes:
                # Clear messages
                from session_manager import get_session_manager
                session_manager = get_session_manager()
                if session_manager.clear_session_messages(self.session.session_id):
                    # Update UI
                    self.session.messages = []
                    self.update_session_info()
                    
                    QMessageBox.information(
                        self,
                        "Messages Cleared",
                        f"All messages in session '{self.session.name}' have been cleared."
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Clear Failed",
                        f"Failed to clear messages in session '{self.session.name}'."
                    )
                    
        except Exception as e:
            logger.error(f"Failed to clear messages: {e}")
            QMessageBox.critical(self, "Error", f"Failed to clear messages: {e}")


# Test application
if __name__ == "__main__":
    import sys
    import tempfile
    import shutil
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Create session manager with temp directory
    temp_dir = tempfile.mkdtemp()
    session_manager = SessionManager(session_dir=temp_dir)
    
    # Create test session
    session = session_manager.create_session("Test Session")
    session.messages = [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you for asking!"},
        {"role": "user", "content": "What can you help me with today?"},
        {"role": "assistant", "content": "I can help you with a variety of tasks..."}
    ]
    session_manager.save_session(session)
    
    # Create dialog
    dialog = SessionManagementDialog(session_manager)
    dialog.exec()
    
    # Clean up
    shutil.rmtree(temp_dir)
    
    # Exit
    sys.exit(0)