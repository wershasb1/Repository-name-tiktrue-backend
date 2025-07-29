# User Interface Components

این پوشه شامل فایل‌های رابط کاربری و تعامل با کاربر است.

## فایل‌های فعال:
- `unified_chat_interface.py` - **رابط چت یکپارچه (اصلی)** ✅
  - ترکیب بهترین ویژگی‌ها از همه فایل‌های chat
  - پشتیبانی از CLI و GUI
  - WebSocket communication تست شده
  - Streaming responses
  - Modern PyQt6 interface

- `chatbot_interface.py` - رابط چت CLI (تست شده با model_node) ✅
- `session_ui.py` - مدیریت جلسات کاربری

## فایل‌های آرشیو شده:
- `archive/chat_interface.py` - کامپوننت‌های چت قدیمی (جایگزین شده)
- `archive/enhanced_chat_interface.py` - رابط چت پیشرفته قدیمی (جایگزین شده)

## استفاده:

### GUI Mode:
```bash
python interfaces/unified_chat_interface.py --gui --tokenizer-path ./tokenizer
```

### CLI Mode:
```bash
python interfaces/unified_chat_interface.py --tokenizer-path ./tokenizer
```

### Integration در کد:
```python
from interfaces.unified_chat_interface import UnifiedChatInterface

# Create widget
chat_widget = UnifiedChatInterface(
    server_host="localhost",
    server_port=8702,
    tokenizer_path="./tokenizer"
)

# Enable with models
chat_widget.enable_chat(["model1", "model2"])
```

## هدف:
ارائه رابط یکپارچه و قدرتمند برای تعامل با سیستم‌های LLM توزیعی.