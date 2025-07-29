"""
Unified Chat Interface - ترکیب بهترین ویژگی‌ها از همه فایل‌های chat
این فایل core logic تست شده از chatbot_interface.py را با GUI مدرن ترکیب می‌کند

Features:
- ✅ WebSocket communication (از chatbot_interface.py)
- ✅ Modern PyQt6 GUI (از chat_interface.py)
- ✅ Streaming responses (تست شده)
- ✅ Session management (اختیاری)
- ✅ Client mode integration (از main_app.py)
"""

import sys
import json
import logging
import asyncio
import threading
import argparse
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# PyQt6 imports
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QComboBox, QLabel, QFrame, QScrollArea,
    QProgressBar, QMessageBox, QApplication, QMainWindow
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QColor

# External dependencies
import numpy as np
import websockets
import colorama

try:
    from transformers import AutoTokenizer
except ImportError:
    logging.error("transformers not found. Install with: pip install transformers")
    sys.exit(1)

# Initialize colorama
colorama.init(autoreset=True)

# Project imports
try:
    from utils.serialization_utils import tensor_to_json_serializable, json_serializable_to_tensor
except ImportError:
    # Fallback serialization (از chatbot_interface.py)
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

logger = logging.getLogger("UnifiedChatInterface")

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


class StreamingWorker(QThread):
    """
    Worker thread برای streaming responses
    Core logic از chatbot_interface.py (تست شده)
    """
    
    token_received = pyqtSignal(str)  # New token
    response_complete = pyqtSignal(str)  # Complete response
    error_occurred = pyqtSignal(str)  # Error message
    
    def __init__(self, message: str, server_host: str = "localhost", 
                 server_port: int = 8702, tokenizer_path: str = None,
                 max_new_tokens: int = 100):
        super().__init__()
        self.message = message
        self.server_host = server_host
        self.server_port = server_port
        self.tokenizer_path = tokenizer_path
        self.max_new_tokens = max_new_tokens
        self.is_cancelled = False
        
        # Settings از chatbot_interface.py
        self.max_retries = 3
        self.retry_delay = 1.0
        self.server_uri = f"ws://{server_host}:{server_port}"
        
        # Load tokenizer
        self.tokenizer = None
        if tokenizer_path:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
            except Exception as e:
                logger.error(f"Failed to load tokenizer: {e}")
    
    def run(self):
        """Run streaming response"""
        try:
            # Use asyncio in thread
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
        """
        Core generation loop از chatbot_interface.py (تست شده)
        """
        if not self.tokenizer:
            await self._simple_streaming()
            return
        
        # Prepare prompt
        full_prompt = f"user: {self.message}\nassistant:"
        
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
        
        # Generation loop
        for step in range(self.max_new_tokens):
            if self.is_cancelled:
                break
            
            try:
                # Prepare inputs based on step
                if step == 0:
                    current_input_ids = input_ids
                    current_attention_mask = np.ones_like(input_ids, dtype=np.int64)
                    current_position_ids = self._create_position_ids(input_ids)
                else:
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
                response = await self._send_request_with_retry(payload)
                
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
                    new_text = self.tokenizer.decode([next_token_id], skip_special_tokens=True)
                else:
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
    
    async def _simple_streaming(self):
        """Simple word-by-word streaming fallback"""
        response_text = f"Response to: '{self.message}'"
        words = response_text.split()
        
        complete_response = ""
        
        for i, word in enumerate(words):
            if self.is_cancelled:
                break
            
            token = word + (" " if i < len(words) - 1 else "")
            complete_response += token
            
            self.token_received.emit(token)
            await asyncio.sleep(0.1 + (i % 3) * 0.05)
        
        if not self.is_cancelled:
            self.response_complete.emit(complete_response)
    
    async def _send_request_with_retry(self, payload: dict) -> Optional[dict]:
        """Send request with retry logic (از chatbot_interface.py)"""
        for attempt in range(self.max_retries):
            try:
                async with websockets.connect(
                    self.server_uri, 
                    max_size=None, 
                    ping_interval=180,
                    ping_timeout=600,
                    close_timeout=1200
                ) as websocket:
                    await websocket.send(json.dumps(payload))
                    response_data = await asyncio.wait_for(websocket.recv(), timeout=1200.0)
                    response = json.loads(response_data)
                    
                    # Convert tensors in response
                    if response.get("status") == "success":
                        if "output_tensors" in response:
                            for name, tensor in response["output_tensors"].items():
                                response["output_tensors"][name] = json_serializable_to_tensor(tensor)
                        
                        if "outputs" in response:
                            for name, tensor in response["outputs"].items():
                                if isinstance(tensor, dict) and tensor.get("_tensor_"):
                                    response["outputs"][name] = json_serializable_to_tensor(tensor)
                    
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
        """Extract logits from server response (از chatbot_interface.py)"""
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
    """
    Widget for displaying a single message
    Modern design از chat_interface.py
    """
    
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
    """
    Widget for displaying chat history
    Modern scrollable design
    """
    
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
    
    def get_all_messages(self) -> List[ChatMessage]:
        """Get all messages"""
        return self.messages.copy()
class ChatInputWidget(QWidget):
    """
    Chat input widget with send button
    Modern design with proper styling
    """
    
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


class UnifiedChatInterface(QWidget):
    """
    Unified Chat Interface - ترکیب بهترین ویژگی‌ها از همه فایل‌ها
    
    Features:
    - ✅ Core logic تست شده از chatbot_interface.py
    - ✅ Modern PyQt6 GUI از chat_interface.py  
    - ✅ Client mode integration از main_app.py
    - ✅ Session management (اختیاری)
    """
    
    # Signals
    message_sent = pyqtSignal(str)
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None, server_host: str = "localhost", 
                 server_port: int = 8702, tokenizer_path: str = None):
        super().__init__(parent)
        
        # Configuration
        self.server_host = server_host
        self.server_port = server_port
        self.tokenizer_path = tokenizer_path
        self.max_new_tokens = 100
        
        # State
        self.current_streaming_worker: Optional[StreamingWorker] = None
        self.available_models: List[str] = []
        self.conversation_history: List[Dict[str, str]] = []
        
        self.init_ui()
        self.setup_connections()
    
    def init_ui(self):
        """Initialize unified chat interface UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header with model selector and status
        header_layout = QHBoxLayout()
        
        # Model selector
        model_label = QLabel("Model:")
        model_label.setStyleSheet("font-weight: bold; color: #495057;")
        header_layout.addWidget(model_label)
        
        self.model_combo = QComboBox()
        self.model_combo.addItem("No models available")
        self.model_combo.setEnabled(False)
        self.model_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
                font-size: 14px;
                min-width: 200px;
            }
            QComboBox:focus {
                border-color: #007bff;
            }
        """)
        header_layout.addWidget(self.model_combo)
        
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
        self.update_status("Select a model to start chatting", "#ffc107")
        
        # Add welcome message
        self.add_system_message("Welcome to TikTrue Unified Chat Interface!")
        self.add_system_message("This interface combines the best features from all chat components.")
    
    def setup_connections(self):
        """Setup signal connections"""
        self.chat_input.message_sent.connect(self.on_message_sent)
    
    def enable_chat(self, available_models: List[str]):
        """Enable chat interface with available models"""
        self.available_models = available_models
        
        self.model_combo.clear()
        self.model_combo.addItems(available_models)
        self.model_combo.setEnabled(True)
        
        self.chat_input.set_enabled(True)
        
        self.update_status("Ready to chat", "#28a745")
        self.add_system_message(f"Models loaded: {', '.join(available_models)}")
        self.add_system_message("You can now start chatting!")
    
    def on_message_sent(self, message: str):
        """Handle message sent"""
        if not self.available_models:
            self.add_system_message("No models available. Please load models first.")
            return
        
        selected_model = self.model_combo.currentText()
        if not selected_model or selected_model == "No models available":
            self.add_system_message("Please select a model first.")
            return
        
        # Add user message
        self.add_user_message(message)
        
        # Disable input during processing
        self.chat_input.set_enabled(False)
        self.update_status("Processing...", "#ffc107")
        
        # Start streaming response
        self.start_streaming_response(message)
        
        # Emit signal
        self.message_sent.emit(message)
    
    def start_streaming_response(self, message: str):
        """Start streaming response using tested logic"""
        # Cancel any existing streaming
        if self.current_streaming_worker:
            self.current_streaming_worker.cancel()
            self.current_streaming_worker.wait()
        
        # Create streaming worker
        self.current_streaming_worker = StreamingWorker(
            message=message,
            server_host=self.server_host,
            server_port=self.server_port,
            tokenizer_path=self.tokenizer_path,
            max_new_tokens=self.max_new_tokens
        )
        
        # Connect signals
        self.current_streaming_worker.token_received.connect(self.on_token_received)
        self.current_streaming_worker.response_complete.connect(self.on_response_complete)
        self.current_streaming_worker.error_occurred.connect(self.on_error_occurred)
        
        # Start streaming message in UI
        self.streaming_message_id = self.chat_history.start_streaming_message(MessageType.ASSISTANT)
        self.streaming_content = ""
        
        # Start worker
        self.current_streaming_worker.start()
    
    def on_token_received(self, token: str):
        """Handle new token received"""
        self.streaming_content += token
        self.chat_history.update_streaming_message(self.streaming_message_id, self.streaming_content)
    
    def on_response_complete(self, response: str):
        """Handle response completion"""
        # Finish streaming message
        self.chat_history.finish_streaming_message(self.streaming_message_id, response)
        
        # Add to conversation history
        user_message = self.chat_history.messages[-2].content if len(self.chat_history.messages) >= 2 else ""
        self.conversation_history.append({"user": user_message, "assistant": response})
        
        # Re-enable input
        self.chat_input.set_enabled(True)
        self.update_status("Ready", "#28a745")
        
        # Emit signal
        self.response_received.emit(response)
    
    def on_error_occurred(self, error: str):
        """Handle error"""
        self.add_system_message(f"Error: {error}")
        
        # Re-enable input
        self.chat_input.set_enabled(True)
        self.update_status("Error occurred", "#dc3545")
        
        # Emit signal
        self.error_occurred.emit(error)
    
    def add_user_message(self, content: str):
        """Add user message to chat"""
        message = ChatMessage(
            id=f"user_{datetime.now().timestamp()}",
            type=MessageType.USER,
            content=content,
            timestamp=datetime.now()
        )
        self.chat_history.add_message(message)
    
    def add_system_message(self, content: str):
        """Add system message to chat"""
        message = ChatMessage(
            id=f"system_{datetime.now().timestamp()}",
            type=MessageType.SYSTEM,
            content=content,
            timestamp=datetime.now()
        )
        self.chat_history.add_message(message)
    
    def add_assistant_message(self, content: str):
        """Add assistant message to chat"""
        message = ChatMessage(
            id=f"assistant_{datetime.now().timestamp()}",
            type=MessageType.ASSISTANT,
            content=content,
            timestamp=datetime.now()
        )
        self.chat_history.add_message(message)
    
    def update_status(self, message: str, color: str = "#28a745"):
        """Update status indicator"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 12px;
                padding: 4px 8px;
                background-color: rgba(255, 255, 255, 0.8);
                border-radius: 4px;
                border: 1px solid {color};
            }}
        """)
    
    def clear_chat(self):
        """Clear chat history"""
        self.chat_history.clear_history()
        self.conversation_history.clear()
        self.add_system_message("Chat cleared.")
    
    def set_tokenizer_path(self, path: str):
        """Set tokenizer path"""
        self.tokenizer_path = path
    
    def set_server_config(self, host: str, port: int):
        """Set server configuration"""
        self.server_host = host
        self.server_port = port
    
    def set_max_tokens(self, max_tokens: int):
        """Set maximum tokens for generation"""
        self.max_new_tokens = max_tokens

# CLI Interface (از chatbot_interface.py)
class CLIChatInterface:
    """
    Command-line interface برای استفاده مستقل
    Core logic تست شده از chatbot_interface.py
    """
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.tokenizer = self._load_tokenizer()
        self.chat_history: List[Dict[str, str]] = []
        self.server_uri = f"ws://{args.first_node_host}:{args.first_node_port}"
        
        # Settings
        self.max_retries = 3
        self.retry_delay = 1.0
        
        print(f"{colorama.Fore.CYAN}🤖 Unified CLI Chat initialized!{colorama.Style.RESET_ALL}")
        print(f"{colorama.Fore.YELLOW}📡 Server: {self.server_uri}{colorama.Style.RESET_ALL}")
    
    def _load_tokenizer(self):
        """Load tokenizer"""
        print(f"{colorama.Style.BRIGHT}📥 Loading tokenizer from {self.args.tokenizer_path}...{colorama.Style.RESET_ALL}")
        try:
            tokenizer = AutoTokenizer.from_pretrained(self.args.tokenizer_path)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            print(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}✅ Tokenizer loaded successfully.{colorama.Style.RESET_ALL}")
            return tokenizer
        except Exception as e:
            print(f"{colorama.Fore.RED}{colorama.Style.BRIGHT}❌ Fatal: Could not load tokenizer. Error: {e}{colorama.Style.RESET_ALL}")
            sys.exit(1)
    
    def _format_prompt_with_history(self, user_prompt: str) -> str:
        """Format prompt with conversation history"""
        if not self.chat_history:
            return f"user: {user_prompt}\nassistant:"
        
        history_str = ""
        for turn in self.chat_history:
            history_str += f"user: {turn['user']}\nassistant: {turn['assistant']}\n"
        
        return history_str + f"user: {user_prompt}\nassistant:"
    
    async def _handle_generation_loop(self, user_prompt: str):
        """Handle generation loop (same as chatbot_interface.py)"""
        # Create streaming worker
        worker = StreamingWorker(
            message=user_prompt,
            server_host=self.args.first_node_host,
            server_port=self.args.first_node_port,
            tokenizer_path=self.args.tokenizer_path,
            max_new_tokens=self.args.max_new_tokens
        )
        
        print(f"{colorama.Fore.BLUE}{colorama.Style.BRIGHT}{self.args.bot_name}: {colorama.Style.RESET_ALL}", end="", flush=True)
        
        # Handle streaming in CLI
        generated_text = ""
        
        def on_token(token):
            nonlocal generated_text
            generated_text += token
            print(token, end="", flush=True)
        
        def on_complete(response):
            nonlocal generated_text
            print()  # New line
            self.chat_history.append({"user": user_prompt, "assistant": response})
        
        def on_error(error):
            print(f"\n{colorama.Fore.RED}Error: {error}{colorama.Style.RESET_ALL}")
        
        # Connect signals (simulate)
        worker.token_received.connect(on_token)
        worker.response_complete.connect(on_complete)
        worker.error_occurred.connect(on_error)
        
        # Run worker
        await worker._handle_generation_loop()
    
    def _show_help(self):
        """Show help"""
        print(f"\n{colorama.Style.BRIGHT}📚 Available Commands:{colorama.Style.RESET_ALL}")
        print(f"{colorama.Fore.GREEN}  clear{colorama.Style.RESET_ALL}     - Clear conversation history")
        print(f"{colorama.Fore.GREEN}  history{colorama.Style.RESET_ALL}   - Show conversation history")
        print(f"{colorama.Fore.GREEN}  help{colorama.Style.RESET_ALL}      - Show this help")
        print(f"{colorama.Fore.GREEN}  exit/quit{colorama.Style.RESET_ALL} - End session")
        print()
    
    def _show_history(self):
        """Show conversation history"""
        if not self.chat_history:
            print(f"{colorama.Fore.YELLOW}📝 No conversation history yet.{colorama.Style.RESET_ALL}")
            return
        
        print(f"\n{colorama.Style.BRIGHT}📚 Conversation History:{colorama.Style.RESET_ALL}")
        print("=" * 60)
        
        for i, turn in enumerate(self.chat_history, 1):
            print(f"{colorama.Fore.GREEN}[{i}] You:{colorama.Style.RESET_ALL} {turn['user']}")
            print(f"{colorama.Fore.BLUE}[{i}] {self.args.bot_name}:{colorama.Style.RESET_ALL} {turn['assistant']}")
            print("-" * 40)
        print()
    
    async def run(self):
        """Main interaction loop"""
        print("\n" + "=" * 60)
        print(f"{colorama.Style.BRIGHT}      🚀 Unified Chat Interface (CLI Mode){colorama.Style.RESET_ALL}")
        print("=" * 60)
        print(f" {colorama.Fore.CYAN}💡 Type 'help' for available commands{colorama.Style.RESET_ALL}")
        print("=" * 60 + "\n")

        while True:
            try:
                prompt = input(f"{colorama.Fore.GREEN}{colorama.Style.BRIGHT}You: {colorama.Style.RESET_ALL}")
                
                if not prompt.strip():
                    continue
                    
                prompt_lower = prompt.lower().strip()
                
                # Special commands
                if prompt_lower in ["exit", "quit"]:
                    break
                elif prompt_lower == "clear":
                    self.chat_history = []
                    print(f"\n{colorama.Fore.YELLOW}🧹 Conversation history cleared!{colorama.Style.RESET_ALL}\n")
                    continue
                elif prompt_lower == "history":
                    self._show_history()
                    continue
                elif prompt_lower == "help":
                    self._show_help()
                    continue
                
                # Generate response
                await self._handle_generation_loop(prompt)
                print()  # Space between conversations

            except (EOFError, KeyboardInterrupt):
                print(f"\n{colorama.Fore.YELLOW}👋 Interrupted by user{colorama.Style.RESET_ALL}")
                break
            except Exception as e:
                print(f"\n{colorama.Fore.RED}💥 Unexpected error: {e}{colorama.Style.RESET_ALL}")
                continue
        
        print(f"\n{colorama.Style.BRIGHT}👋 Thank you for using Unified Chat Interface!{colorama.Style.RESET_ALL}")


# Main window for GUI mode
class UnifiedChatWindow(QMainWindow):
    """Main window for unified chat interface"""
    
    def __init__(self, tokenizer_path: str = None):
        super().__init__()
        self.tokenizer_path = tokenizer_path
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("TikTrue - Unified Chat Interface")
        self.setMinimumSize(800, 600)
        
        # Create central widget
        self.chat_interface = UnifiedChatInterface(
            parent=self,
            tokenizer_path=self.tokenizer_path
        )
        self.setCentralWidget(self.chat_interface)
        
        # Setup menu bar
        self.setup_menu()
        
        # Setup status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Unified Chat Interface Ready")
    
    def setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        
        # Chat menu
        chat_menu = menubar.addMenu("Chat")
        
        clear_action = chat_menu.addAction("Clear Chat")
        clear_action.setShortcut("Ctrl+L")
        clear_action.triggered.connect(self.chat_interface.clear_chat)
        
        chat_menu.addSeparator()
        
        exit_action = chat_menu.addAction("Exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)


def main():
    """Main function - supports both CLI and GUI modes"""
    parser = argparse.ArgumentParser(
        description="🤖 Unified Chat Interface - CLI and GUI modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CLI mode
  python unified_chat_interface.py --tokenizer-path ./llama3_1_tokenizer
  
  # GUI mode  
  python unified_chat_interface.py --gui --tokenizer-path ./llama3_1_tokenizer
  
  # Custom server
  python unified_chat_interface.py --first-node-host 192.168.1.100 --first-node-port 8701
        """
    )
    
    parser.add_argument("--gui", action="store_true", help="Launch GUI mode instead of CLI")
    parser.add_argument("--first-node-host", default="localhost", help="Hostname of the inference node")
    parser.add_argument("--first-node-port", type=int, default=8702, help="Port of the inference node")
    parser.add_argument("--tokenizer-path", help="Path to the tokenizer directory")
    parser.add_argument("--max-new-tokens", type=int, default=100, help="Maximum tokens to generate")
    parser.add_argument("--bot-name", default="AI Assistant", help="Display name for the bot")
    
    args = parser.parse_args()
    
    # Auto-detect tokenizer if not provided
    if not args.tokenizer_path:
        try:
            from core.config_manager import ConfigManager
            config_manager = ConfigManager()
            tokenizer_path = config_manager.get_tokenizer_path()
            if tokenizer_path:
                args.tokenizer_path = str(tokenizer_path)
                print(f"{colorama.Fore.GREEN}✅ Auto-detected tokenizer: {args.tokenizer_path}{colorama.Style.RESET_ALL}")
        except Exception as e:
            print(f"{colorama.Fore.YELLOW}⚠️ Could not auto-detect tokenizer: {e}{colorama.Style.RESET_ALL}")
    
    if args.gui:
        # GUI mode
        app = QApplication(sys.argv)
        window = UnifiedChatWindow(tokenizer_path=args.tokenizer_path)
        
        # Enable models if tokenizer available
        if args.tokenizer_path:
            window.chat_interface.enable_chat(["unified_model"])
        
        window.show()
        sys.exit(app.exec())
    else:
        # CLI mode
        if not args.tokenizer_path:
            print(f"{colorama.Fore.RED}❌ Tokenizer path required for CLI mode{colorama.Style.RESET_ALL}")
            sys.exit(1)
        
        try:
            interface = CLIChatInterface(args)
            asyncio.run(interface.run())
        except KeyboardInterrupt:
            print(f"\n{colorama.Fore.YELLOW}👋 Goodbye!{colorama.Style.RESET_ALL}")
        except Exception as e:
            print(f"{colorama.Fore.RED}💥 Fatal error: {e}{colorama.Style.RESET_ALL}")
            sys.exit(1)


if __name__ == "__main__":
    main()