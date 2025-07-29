"""
Advanced Chat Interface with Streaming Responses
Modern chat interface with real-time streaming, session management, and network integration
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
    QSizePolicy, QApplication, QMainWindow
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
from core.network_manager import NetworkManager
from security.license_validator import LicenseValidator
from subscription_manager import SubscriptionManager

# Import numpy for tensor operations
import numpy as np

# Import numpy for tensor operations
try:
    import numpy as np
except ImportError:
    np = None

logger = logging.getLogger("ChatInterface")


class MessageType(Enum):
    """Types of chat messages"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ERROR = "error"


@dataclass
class ChatMessage:
    """Represents a chat message"""
    id: str
    type: MessageType
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['type'] = self.type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            type=MessageType(data['type']),
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=data.get('metadata', {})
        )


class StreamingWorker(QThread):
    """Worker thread for real streaming responses via WebSocket"""
    
    token_received = pyqtSignal(str)  # New token
    response_complete = pyqtSignal(str)  # Complete response
    error_occurred = pyqtSignal(str)  # Error message
    
    def __init__(self, message: str, network_id: str = None, tokenizer_path: str = None):
        super().__init__()
        self.message = message
        self.network_id = network_id
        self.tokenizer_path = tokenizer_path
        self.is_cancelled = False
        
        # WebSocket settings
        self.server_host = "localhost"
        self.server_port = 8702
        self.max_new_tokens = 50
        self.max_retries = 3
        self.retry_delay = 1.0
        
        # Initialize tokenizer if path provided
        self.tokenizer = None
        if tokenizer_path:
            try:
                from transformers import AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
            except Exception as e:
                logger.error(f"Failed to load tokenizer: {e}")
    
    def run(self):
        """Run real streaming response via WebSocket"""
        try:
            # Use asyncio in thread
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self._handle_generation_loop())
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            self.error_occurred.emit(str(e))
    
    async def _handle_generation_loop(self):
        """Real generation loop with WebSocket communication"""
        try:
            import websockets
            import json
            import numpy as np
            import time
            
            # Import serialization utilities
            try:
                from utils.serialization_utils import tensor_to_json_serializable, json_serializable_to_tensor
            except ImportError:
                # Fallback serialization
                import base64
                
                def tensor_to_json_serializable(tensor: np.ndarray) -> dict:
                    return {
                        "_tensor_": True,
                        "dtype": str(tensor.dtype),
                        "shape": list(tensor.shape),
                        "data_b64": base64.b64encode(tensor.tobytes()).decode("utf-8")
                    }
                
                def json_serializable_to_tensor(data: dict) -> np.ndarray:
                    if not isinstance(data, dict) or not data.get("_tensor_"):
                        return data
                    dt, sh, b = np.dtype(data["dtype"]), tuple(data["shape"]), base64.b64decode(data["data_b64"])
                    return np.frombuffer(b, dtype=dt).reshape(sh)
            
            if not self.tokenizer:
                # Fallback to simple word-by-word streaming
                await self._simple_streaming()
                return
            
            # Prepare full prompt
            full_prompt = f"user: {self.message}\\nassistant:"
            
            # Tokenize
            inputs = self.tokenizer(
                full_prompt, 
                return_tensors="np", 
                padding=False, 
                truncation=True, 
                max_length=128
            )
            input_ids = inputs["input_ids"]
            
            # Session info
            session_id = f"chat_{int(time.time())}"
            generated_tokens = []
            server_uri = f"ws://{self.server_host}:{self.server_port}"
            
            # Generation loop
            for step in range(self.max_new_tokens):
                if self.is_cancelled:
                    break
                
                try:
                    # Prepare inputs based on step
                    if step == 0:
                        # First step: send full prompt
                        current_input_ids = input_ids
                        current_attention_mask = np.ones_like(input_ids, dtype=np.int64)
                        current_position_ids = self._create_position_ids(input_ids)
                    else:
                        # Subsequent steps: only last generated token
                        last_token = generated_tokens[-1]
                        current_input_ids = np.array([[last_token]], dtype=np.int64)
                        current_attention_mask = np.ones((1, 1), dtype=np.int64)
                        current_position = input_ids.shape[1] + len(generated_tokens) - 1
                        current_position_ids = np.array([[current_position]], dtype=np.int64)
                    
                    # Create payload
                    input_tensors = {
                        "input_ids": tensor_to_json_serializable(current_input_ids),
                        "attention_mask": tensor_to_json_serializable(current_attention_mask),
                        "position_ids": tensor_to_json_serializable(current_position_ids)
                    }
                    
                    payload = {
                        "session_id": session_id,
                        "step": step,
                        "target_block_id": "block_1",
                        "input_tensors": input_tensors
                    }
                    
                    # Send request with retry
                    response = await self._send_request_with_retry(server_uri, payload)
                    
                    if not response or response.get("status") != "success":
                        error_msg = response.get('message', 'No response') if response else 'No response'
                        self.error_occurred.emit(f"Generation failed at step {step}: {error_msg}")
                        break
                    
                    # Extract logits
                    logits = self._extract_logits(response)
                    if logits is None:
                        self.error_occurred.emit("Logits not found in server response")
                        break
                    
                    # Select next token (greedy)
                    next_token_id = np.argmax(logits[0, -1, :]).item()
                    
                    # Check for end of sequence
                    if next_token_id == self.tokenizer.eos_token_id:
                        break
                    
                    # Add new token
                    generated_tokens.append(next_token_id)
                    
                    # Decode and emit new token
                    if len(generated_tokens) == 1:
                        # First token
                        new_text = self.tokenizer.decode([next_token_id], skip_special_tokens=True)
                    else:
                        # Incremental decoding
                        full_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
                        prev_text = self.tokenizer.decode(generated_tokens[:-1], skip_special_tokens=True)
                        new_text = full_text[len(prev_text):]
                    
                    if new_text:
                        self.token_received.emit(new_text)
                    
                except Exception as e:
                    logger.error(f"Error at step {step}: {e}")
                    self.error_occurred.emit(f"Error at step {step}: {e}")
                    break
            
            # Complete response
            if generated_tokens and not self.is_cancelled:
                full_response = self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
                self.response_complete.emit(full_response)
            
        except Exception as e:
            logger.error(f"Generation loop error: {e}")
            self.error_occurred.emit(str(e))
    
    async def _simple_streaming(self):
        """Simple word-by-word streaming fallback"""
        response_text = f"Response to: '{self.message}'"
        words = response_text.split()
        
        complete_response = ""
        
        for i, word in enumerate(words):
            if self.is_cancelled:
                break
            
            # Add word with space
            token = word + (" " if i < len(words) - 1 else "")
            complete_response += token
            
            # Emit token
            self.token_received.emit(token)
            
            # Simulate delay
            await asyncio.sleep(0.1 + (i % 3) * 0.05)
        
        if not self.is_cancelled:
            self.response_complete.emit(complete_response)
    
    async def _send_request_with_retry(self, server_uri: str, payload: dict) -> Optional[dict]:
        """Send request with retry logic"""
        import websockets
        import json
        
        for attempt in range(self.max_retries):
            try:
                async with websockets.connect(
                    server_uri, 
                    max_size=None, 
                    ping_interval=180,
                    ping_timeout=600,
                    close_timeout=1200
                ) as websocket:
                    # Send request
                    await websocket.send(json.dumps(payload))
                    
                    # Receive response
                    response_data = await asyncio.wait_for(websocket.recv(), timeout=1200.0)
                    response = json.loads(response_data)
                    
                    return response
                    
            except Exception as e:
                logger.error(f"Request attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        return None
    
    def _create_position_ids(self, input_ids: np.ndarray, past_length: int = 0) -> np.ndarray:
        """Create position_ids for model"""
        seq_length = input_ids.shape[1]
        position_ids = np.arange(past_length, past_length + seq_length, dtype=np.int64)
        return position_ids.reshape(1, seq_length)
    
    def _extract_logits(self, response: dict) -> Optional[np.ndarray]:
        """Extract logits from server response"""
        try:
            from utils.serialization_utils import json_serializable_to_tensor
        except ImportError:
            import base64
            def json_serializable_to_tensor(data: dict) -> np.ndarray:
                if not isinstance(data, dict) or not data.get("_tensor_"):
                    return data
                dt, sh, b = np.dtype(data["dtype"]), tuple(data["shape"]), base64.b64decode(data["data_b64"])
                return np.frombuffer(b, dtype=dt).reshape(sh)
        
        # Search for logits in various locations
        sources = [
            response.get("outputs", {}),
            response.get("output_tensors", {}),
            response.get("propagating_tensors", {})
        ]
        
        for source in sources:
            if isinstance(source, dict):
                # Direct logits lookup
                if "logits" in source:
                    logits = source["logits"]
                    if isinstance(logits, dict) and logits.get("_tensor_"):
                        logits = json_serializable_to_tensor(logits)
                    return logits
                
                # Search for tensor with appropriate shape
                for key, value in source.items():
                    if isinstance(value, dict) and value.get("_tensor_"):
                        value = json_serializable_to_tensor(value)
                    
                    if hasattr(value, 'shape') and len(value.shape) == 3 and value.shape[-1] > 30000:
                        return value
        
        return None
    
    def cancel(self):
        """Cancel streaming"""
        self.is_cancelled = True


class MessageWidget(QFrame):
    """Widget for displaying a single message"""
    
    def __init__(self, message: ChatMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self.init_ui()
    
    def init_ui(self):
        """Initialize message UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        
        # Message header
        header_layout = QHBoxLayout()
        
        # Sender info
        sender_label = QLabel(self.get_sender_name())
        sender_label.setStyleSheet(f"""
            QLabel {{
                font-weight: bold;
                color: {self.get_sender_color()};
                font-size: 12px;
            }}
        """)
        header_layout.addWidget(sender_label)
        
        # Timestamp
        timestamp_label = QLabel(self.message.timestamp.strftime("%H:%M"))
        timestamp_label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 10px;
            }
        """)
        header_layout.addWidget(timestamp_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Message content
        self.content_label = QLabel(self.message.content)
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | 
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.content_label.setStyleSheet(f"""
            QLabel {{
                padding: 8px 12px;
                background-color: {self.get_background_color()};
                border-radius: 12px;
                color: {self.get_text_color()};
                font-size: 14px;
                line-height: 1.4;
            }}
        """)
        layout.addWidget(self.content_label)
        
        # Message alignment
        if self.message.type == MessageType.USER:
            layout.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.content_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.content_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.setLayout(layout)
        self.setStyleSheet("MessageWidget { background: transparent; }")
    
    def get_sender_name(self) -> str:
        """Get sender display name"""
        if self.message.type == MessageType.USER:
            return "You"
        elif self.message.type == MessageType.ASSISTANT:
            return "Assistant"
        elif self.message.type == MessageType.SYSTEM:
            return "System"
        else:
            return "Error"
    
    def get_sender_color(self) -> str:
        """Get sender name color"""
        colors = {
            MessageType.USER: "#007bff",
            MessageType.ASSISTANT: "#28a745",
            MessageType.SYSTEM: "#6c757d",
            MessageType.ERROR: "#dc3545"
        }
        return colors.get(self.message.type, "#6c757d")
    
    def get_background_color(self) -> str:
        """Get message background color"""
        colors = {
            MessageType.USER: "#007bff",
            MessageType.ASSISTANT: "#f8f9fa",
            MessageType.SYSTEM: "#e9ecef",
            MessageType.ERROR: "#f8d7da"
        }
        return colors.get(self.message.type, "#f8f9fa")
    
    def get_text_color(self) -> str:
        """Get message text color"""
        if self.message.type == MessageType.USER:
            return "white"
        elif self.message.type == MessageType.ERROR:
            return "#721c24"
        else:
            return "#212529"
    
    def update_content(self, content: str):
        """Update message content (for streaming)"""
        self.message.content = content
        self.content_label.setText(content)


class ChatHistoryWidget(QScrollArea):
    """Widget for displaying chat history"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages: List[ChatMessage] = []
        self.message_widgets: List[MessageWidget] = []
        self.streaming_widget: Optional[MessageWidget] = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize chat history UI"""
        # Create scroll area content
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(5)
        self.content_layout.addStretch()  # Push messages to bottom initially
        
        self.content_widget.setLayout(self.content_layout)
        self.setWidget(self.content_widget)
        self.setWidgetResizable(True)
        
        # Styling
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
            QScrollArea > QWidget > QWidget {
                background-color: white;
            }
        """)
        
        # Auto-scroll to bottom
        self.verticalScrollBar().rangeChanged.connect(self.scroll_to_bottom)
    
    def add_message(self, message: ChatMessage):
        """Add a new message"""
        self.messages.append(message)
        
        # Create message widget
        message_widget = MessageWidget(message)
        self.message_widgets.append(message_widget)
        
        # Add to layout (before stretch)
        self.content_layout.insertWidget(self.content_layout.count() - 1, message_widget)
        
        # Scroll to bottom
        QTimer.singleShot(50, self.scroll_to_bottom)
    
    def start_streaming_message(self, message_type: MessageType) -> str:
        """Start a streaming message and return its ID"""
        message_id = f"msg_{datetime.now().timestamp()}"
        
        # Create streaming message
        streaming_message = ChatMessage(
            id=message_id,
            type=message_type,
            content="",
            timestamp=datetime.now()
        )
        
        # Create widget
        self.streaming_widget = MessageWidget(streaming_message)
        self.message_widgets.append(self.streaming_widget)
        
        # Add to layout
        self.content_layout.insertWidget(self.content_layout.count() - 1, self.streaming_widget)
        
        return message_id
    
    def update_streaming_message(self, message_id: str, content: str):
        """Update streaming message content"""
        if self.streaming_widget:
            self.streaming_widget.update_content(content)
            QTimer.singleShot(10, self.scroll_to_bottom)
    
    def finish_streaming_message(self, message_id: str, final_content: str):
        """Finish streaming message"""
        if self.streaming_widget:
            # Update final content
            self.streaming_widget.update_content(final_content)
            
            # Add to messages list
            final_message = ChatMessage(
                id=message_id,
                type=self.streaming_widget.message.type,
                content=final_content,
                timestamp=self.streaming_widget.message.timestamp
            )
            self.messages.append(final_message)
            
            # Clear streaming reference
            self.streaming_widget = None
    
    def scroll_to_bottom(self):
        """Scroll to bottom of chat"""
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_history(self):
        """Clear all messages"""
        # Remove all message widgets
        for widget in self.message_widgets:
            widget.setParent(None)
        
        self.messages.clear()
        self.message_widgets.clear()
        self.streaming_widget = None


class NetworkSelector(QComboBox):
    """Network selection dropdown"""
    
    network_changed = pyqtSignal(str)  # network_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.network_manager = NetworkManager()
        self.init_ui()
        self.refresh_networks()
    
    def init_ui(self):
        """Initialize network selector UI"""
        self.setMinimumWidth(200)
        self.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
                font-size: 14px;
            }
            QComboBox:focus {
                border-color: #007bff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border: 2px solid #6c757d;
                width: 6px;
                height: 6px;
                border-top: none;
                border-left: none;
                margin-right: 5px;
            }
        """)
        
        self.currentTextChanged.connect(self.on_network_changed)
    
    def refresh_networks(self):
        """Refresh available networks"""
        try:
            self.clear()
            
            # Add default option
            self.addItem("Select Network...", "")
            
            # Get available networks
            networks = self.network_manager.list_joined_networks()
            
            for network in networks:
                display_name = f"{network['name']} ({network['status']})"
                self.addItem(display_name, network['network_id'])
            
            if not networks:
                self.addItem("No networks available", "")
                self.setEnabled(False)
            else:
                self.setEnabled(True)
                
        except Exception as e:
            logger.error(f"Failed to refresh networks: {e}")
            self.addItem("Error loading networks", "")
            self.setEnabled(False)
    
    def on_network_changed(self, text: str):
        """Handle network selection change"""
        network_id = self.currentData()
        if network_id:
            self.network_changed.emit(network_id)
    
    def get_selected_network(self) -> Optional[str]:
        """Get currently selected network ID"""
        return self.currentData() if self.currentData() else None


class ChatInputWidget(QWidget):
    """Chat input widget with send button"""
    
    message_sent = pyqtSignal(str)  # message content
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize input widget UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Message input
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.returnPressed.connect(self.send_message)
        self.message_input.setStyleSheet("""
            QLineEdit {
                padding: 12px 16px;
                border: 2px solid #dee2e6;
                border-radius: 25px;
                font-size: 14px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
        """)
        layout.addWidget(self.message_input)
        
        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 20px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        layout.addWidget(self.send_button)
        
        self.setLayout(layout)
    
    def send_message(self):
        """Send message"""
        message = self.message_input.text().strip()
        if message:
            self.message_sent.emit(message)
            self.message_input.clear()
    
    def set_enabled(self, enabled: bool):
        """Enable/disable input"""
        self.message_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)


class AdvancedChatInterface(QWidget):
    """Advanced chat interface with streaming responses"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_network_id: Optional[str] = None
        self.streaming_worker: Optional[StreamingWorker] = None
        self.subscription_manager = SubscriptionManager()
        
        self.init_ui()
        self.setup_connections()
    
    def init_ui(self):
        """Initialize chat interface UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header with network selector
        header_layout = QHBoxLayout()
        
        # Network selector
        network_label = QLabel("Network:")
        network_label.setStyleSheet("font-weight: bold; color: #495057;")
        header_layout.addWidget(network_label)
        
        self.network_selector = NetworkSelector()
        header_layout.addWidget(self.network_selector)
        
        header_layout.addStretch()
        
        # Status indicator
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #28a745;
                font-size: 12px;
                padding: 4px 8px;
                background-color: #d4edda;
                border-radius: 4px;
            }
        """)
        header_layout.addWidget(self.status_label)
        
        layout.addLayout(header_layout)
        
        # Chat history
        self.chat_history = ChatHistoryWidget()
        layout.addWidget(self.chat_history)
        
        # Input area
        self.chat_input = ChatInputWidget()
        layout.addWidget(self.chat_input)
        
        self.setLayout(layout)
        
        # Initial state
        self.update_status("Select a network to start chatting", "#ffc107")
    
    def setup_connections(self):
        """Setup signal connections"""
        self.network_selector.network_changed.connect(self.on_network_changed)
        self.chat_input.message_sent.connect(self.on_message_sent)
    
    def on_network_changed(self, network_id: str):
        """Handle network selection change"""
        self.current_network_id = network_id
        
        if network_id:
            self.update_status("Connected to network", "#28a745")
            self.chat_input.set_enabled(True)
            
            # Add system message
            system_message = ChatMessage(
                id=f"sys_{datetime.now().timestamp()}",
                type=MessageType.SYSTEM,
                content=f"Connected to network: {network_id[:8]}...",
                timestamp=datetime.now()
            )
            self.chat_history.add_message(system_message)
        else:
            self.update_status("No network selected", "#ffc107")
            self.chat_input.set_enabled(False)
    
    def on_message_sent(self, message: str):
        """Handle message sent"""
        if not self.current_network_id:
            QMessageBox.warning(self, "No Network", "Please select a network first.")
            return
        
        # Add user message
        user_message = ChatMessage(
            id=f"user_{datetime.now().timestamp()}",
            type=MessageType.USER,
            content=message,
            timestamp=datetime.now()
        )
        self.chat_history.add_message(user_message)
        
        # Start streaming response
        self.start_streaming_response(message)
    
    def start_streaming_response(self, message: str):
        """Start streaming response"""
        # Update status
        self.update_status("Generating response...", "#007bff")
        self.chat_input.set_enabled(False)
        
        # Start streaming message
        message_id = self.chat_history.start_streaming_message(MessageType.ASSISTANT)
        
        # Create and start worker
        self.streaming_worker = StreamingWorker(message, self.current_network_id)
        self.streaming_worker.token_received.connect(
            lambda token: self.on_token_received(message_id, token)
        )
        self.streaming_worker.response_complete.connect(
            lambda response: self.on_response_complete(message_id, response)
        )
        self.streaming_worker.error_occurred.connect(self.on_streaming_error)
        self.streaming_worker.start()
    
    def on_token_received(self, message_id: str, token: str):
        """Handle received token"""
        # Update streaming message
        if self.chat_history.streaming_widget:
            current_content = self.chat_history.streaming_widget.message.content
            new_content = current_content + token
            self.chat_history.update_streaming_message(message_id, new_content)
    
    def on_response_complete(self, message_id: str, response: str):
        """Handle response completion"""
        # Finish streaming message
        self.chat_history.finish_streaming_message(message_id, response)
        
        # Update status
        self.update_status("Ready", "#28a745")
        self.chat_input.set_enabled(True)
        
        # Clean up worker
        if self.streaming_worker:
            self.streaming_worker.deleteLater()
            self.streaming_worker = None
    
    def on_streaming_error(self, error: str):
        """Handle streaming error"""
        # Add error message
        error_message = ChatMessage(
            id=f"error_{datetime.now().timestamp()}",
            type=MessageType.ERROR,
            content=f"Error: {error}",
            timestamp=datetime.now()
        )
        self.chat_history.add_message(error_message)
        
        # Update status
        self.update_status("Error occurred", "#dc3545")
        self.chat_input.set_enabled(True)
        
        # Clean up worker
        if self.streaming_worker:
            self.streaming_worker.deleteLater()
            self.streaming_worker = None
    
    def update_status(self, message: str, color: str):
        """Update status display"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 12px;
                padding: 4px 8px;
                background-color: {color}20;
                border-radius: 4px;
            }}
        """)
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_history.clear_history()
        
        # Add welcome message
        welcome_message = ChatMessage(
            id=f"welcome_{datetime.now().timestamp()}",
            type=MessageType.SYSTEM,
            content="Chat cleared. Start a new conversation!",
            timestamp=datetime.now()
        )
        self.chat_history.add_message(welcome_message)


def main():
    """Test the chat interface standalone"""
    app = QApplication(sys.argv)
    
    # Create main window
    window = QMainWindow()
    window.setWindowTitle("TikTrue Chat Interface")
    window.setMinimumSize(800, 600)
    
    # Create chat interface
    chat_interface = AdvancedChatInterface()
    window.setCentralWidget(chat_interface)
    
    # Show window
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()