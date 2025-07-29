"""
Demo Session Management UI
Simple demo to test the session management UI components
"""

import sys
import logging
import tempfile
import shutil
from datetime import datetime, timedelta

# PyQt6 imports
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt

# Import our modules
from session_manager import SessionManager, Session
from session_ui import SessionListWidget, SessionManagementDialog
from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SessionUIDemo")


def create_test_license(tier: SubscriptionTier = SubscriptionTier.PRO) -> LicenseInfo:
    """Create a test license for demo purposes"""
    return LicenseInfo(
        license_key=f"TIKT-{tier.value}-1M-DEMO123",
        plan=tier,
        duration_months=1,
        unique_id="DEMO123",
        expires_at=datetime.now() + timedelta(days=30),
        max_clients=20 if tier == SubscriptionTier.PRO else 3,
        allowed_models=["llama-7b", "llama-13b", "mistral-7b"] if tier == SubscriptionTier.PRO else ["llama-7b"],
        allowed_features=["advanced_chat", "session_management", "multi_network"] if tier == SubscriptionTier.PRO else ["basic_chat"],
        status=LicenseStatus.VALID,
        hardware_signature="demo_signature",
        created_at=datetime.now(),
        checksum="demo_checksum"
    )


def create_sample_sessions(session_manager: SessionManager) -> None:
    """Create some sample sessions for demo"""
    
    # Session 1: General Chat
    session1 = session_manager.create_session("General Chat")
    session1.add_message({"role": "user", "content": "Hello! How are you today?"})
    session1.add_message({"role": "assistant", "content": "Hello! I'm doing well, thank you for asking. How can I help you today?"})
    session1.add_message({"role": "user", "content": "Can you explain what artificial intelligence is?"})
    session1.add_message({"role": "assistant", "content": "Artificial Intelligence (AI) refers to the simulation of human intelligence in machines that are programmed to think and learn like humans. It encompasses various technologies including machine learning, natural language processing, computer vision, and robotics."})
    session_manager.save_session(session1)
    
    # Session 2: Programming Help
    session2 = session_manager.create_session("Python Programming Help")
    session2.add_message({"role": "user", "content": "How do I create a list in Python?"})
    session2.add_message({"role": "assistant", "content": "You can create a list in Python using square brackets. Here are some examples:\n\n```python\n# Empty list\nmy_list = []\n\n# List with items\nfruits = ['apple', 'banana', 'orange']\n\n# List with numbers\nnumbers = [1, 2, 3, 4, 5]\n\n# Mixed types\nmixed = [1, 'hello', 3.14, True]\n```"})
    session2.add_message({"role": "user", "content": "How do I add items to a list?"})
    session2.add_message({"role": "assistant", "content": "You can add items to a list using several methods:\n\n```python\n# Using append() to add one item\nmy_list = [1, 2, 3]\nmy_list.append(4)  # [1, 2, 3, 4]\n\n# Using extend() to add multiple items\nmy_list.extend([5, 6])  # [1, 2, 3, 4, 5, 6]\n\n# Using insert() to add at specific position\nmy_list.insert(0, 0)  # [0, 1, 2, 3, 4, 5, 6]\n```"})
    session_manager.save_session(session2)
    
    # Session 3: Math Questions
    session3 = session_manager.create_session("Math & Science")
    session3.add_message({"role": "user", "content": "What is calculus?"})
    session3.add_message({"role": "assistant", "content": "Calculus is a branch of mathematics that deals with rates of change (differential calculus) and accumulation of quantities (integral calculus). It was developed independently by Isaac Newton and Gottfried Wilhelm Leibniz in the 17th century."})
    session3.add_message({"role": "user", "content": "Can you give me an example of a derivative?"})
    session3.add_message({"role": "assistant", "content": "Sure! Here's a simple example:\n\nIf f(x) = x², then the derivative f'(x) = 2x\n\nThis means:\n- At x = 1: f'(1) = 2(1) = 2 (slope is 2)\n- At x = 3: f'(3) = 2(3) = 6 (slope is 6)\n\nThe derivative tells us how fast the function is changing at any given point."})
    session_manager.save_session(session3)
    
    # Session 4: Short conversation
    session4 = session_manager.create_session("Quick Questions")
    session4.add_message({"role": "user", "content": "What's the weather like?"})
    session4.add_message({"role": "assistant", "content": "I don't have access to real-time weather data, but I'd be happy to help you find weather information or discuss weather-related topics!"})
    session_manager.save_session(session4)
    
    logger.info(f"Created {len(session_manager.get_all_sessions())} sample sessions")


class SessionUIDemo(QMainWindow):
    """Demo window for session management UI"""
    
    def __init__(self):
        super().__init__()
        self.temp_dir = tempfile.mkdtemp()
        self.session_manager = SessionManager(self.temp_dir)
        self.license_info = create_test_license(SubscriptionTier.PRO)
        
        self.init_ui()
        self.create_sample_data()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Session Management UI Demo")
        self.setMinimumSize(800, 600)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        
        # Create session list widget
        self.session_widget = SessionListWidget(self.session_manager, self.license_info)
        layout.addWidget(self.session_widget)
        
        # Connect signals
        self.session_widget.session_selected.connect(self.on_session_selected)
        self.session_widget.session_created.connect(self.on_session_created)
        self.session_widget.session_deleted.connect(self.on_session_deleted)
        self.session_widget.session_renamed.connect(self.on_session_renamed)
        
        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Session Management Demo - Ready")
    
    def create_sample_data(self):
        """Create sample sessions"""
        create_sample_sessions(self.session_manager)
        self.session_widget.refresh_sessions()
    
    def on_session_selected(self, session):
        """Handle session selection"""
        self.status_bar.showMessage(f"Selected: {session.name} ({len(session.messages)} messages)")
        logger.info(f"Selected session: {session.name}")
    
    def on_session_created(self, session):
        """Handle session creation"""
        self.status_bar.showMessage(f"Created: {session.name}")
        logger.info(f"Created session: {session.name}")
    
    def on_session_deleted(self, session_id):
        """Handle session deletion"""
        self.status_bar.showMessage(f"Deleted session: {session_id}")
        logger.info(f"Deleted session: {session_id}")
    
    def on_session_renamed(self, session):
        """Handle session rename"""
        self.status_bar.showMessage(f"Renamed session: {session.name}")
        logger.info(f"Renamed session: {session.name}")
    
    def closeEvent(self, event):
        """Handle close event"""
        try:
            # Clean up temporary directory
            shutil.rmtree(self.temp_dir)
            logger.info("Cleaned up temporary directory")
        except Exception as e:
            logger.error(f"Failed to clean up: {e}")
        
        event.accept()


def main():
    """Main function"""
    app = QApplication(sys.argv)
    
    # Create and show demo window
    demo = SessionUIDemo()
    demo.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()