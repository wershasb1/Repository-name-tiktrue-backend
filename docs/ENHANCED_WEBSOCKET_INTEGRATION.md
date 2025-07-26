# راهنمای ادغام Enhanced WebSocket Handler

## خلاصه

این راهنما نحوه ادغام `enhanced_websocket_handler.py` با `model_node.py` موجود را توضیح می‌دهد تا پشتیبانی از پروتکل استاندارد WebSocket اضافه شود **بدون اختلال در عملکرد فعلی**.

## مشکل حل شده

### قبل از Enhanced Handler:
- `model_node.py` فقط از پروتکل legacy پشتیبانی می‌کرد
- پیام‌های ساده JSON بدون ساختار استاندارد
- عدم پشتیبانی از انواع مختلف پیام (heartbeat، authentication، etc.)

### بعد از Enhanced Handler:
- ✅ پشتیبانی همزمان از legacy و standard protocol
- ✅ تشخیص خودکار نوع پیام
- ✅ سازگاری کامل با کد موجود
- ✅ پشتیبانی از انواع مختلف پیام

## نحوه ادغام

### گزینه 1: جایگزینی کامل Handler (توصیه شده)

در `model_node.py`، خط 2321 را تغییر دهید:

```python
# قبل:
start_server = websockets.serve(
    handler,  # handler قدیمی
    host,
    port,
    max_size=None,
    compression=None,
    ping_interval=25,
    ping_timeout=30
)

# بعد:
from enhanced_websocket_handler import enhanced_websocket_handler

start_server = websockets.serve(
    enhanced_websocket_handler,  # handler جدید
    host,
    port,
    max_size=None,
    compression=None,
    ping_interval=25,
    ping_timeout=30
)
```

### گزینه 2: استفاده تدریجی

اگر می‌خواهید تدریجی تغییر کنید:

```python
# در model_node.py
from enhanced_websocket_handler import get_enhanced_handler

async def handler(websocket, path=None):
    """WebSocket handler with optional protocol enhancement"""
    enhanced_handler = get_enhanced_handler()
    
    try:
        async for message_raw in websocket:
            # Parse message
            if isinstance(message_raw, bytes):
                message_str = message_raw.decode('utf-8')
            else:
                message_str = message_raw
            
            # Try enhanced handler first
            handled = await enhanced_handler.process_message(
                websocket, message_str, execute_pipeline
            )
            
            if not handled:
                # Fall back to original logic
                # ... کد قدیمی ...
```

## انواع پیام‌های پشتیبانی شده

### 1. Legacy Format (سازگاری با گذشته)
```json
{
  "session_id": "session_123",
  "step": 0,
  "input_tensors": {
    "input_ids": [1, 2, 3],
    "attention_mask": [1, 1, 1]
  }
}
```

### 2. Standard Protocol - Inference Request
```json
{
  "header": {
    "message_id": "uuid-here",
    "message_type": "inference_request",
    "protocol_version": "2.0",
    "timestamp": "2024-01-01T12:00:00Z",
    "license_hash": "abc123"
  },
  "model_id": "llama3_1_8b",
  "prompt": "Hello, world!",
  "max_tokens": 100,
  "temperature": 0.7
}
```

### 3. Standard Protocol - Heartbeat
```json
{
  "header": {
    "message_id": "uuid-here",
    "message_type": "heartbeat",
    "protocol_version": "2.0",
    "timestamp": "2024-01-01T12:00:00Z"
  },
  "worker_id": "model_node_1"
}
```

### 4. Standard Protocol - Authentication
```json
{
  "header": {
    "message_id": "uuid-here",
    "message_type": "authentication",
    "protocol_version": "2.0",
    "timestamp": "2024-01-01T12:00:00Z"
  },
  "license_key": "your-license-key-here"
}
```

## مزایای Enhanced Handler

### 1. سازگاری کامل
- **هیچ تغییری** در کلاینت‌های موجود لازم نیست
- **هیچ تغییری** در API موجود لازم نیست
- کد legacy همچنان کار می‌کند

### 2. قابلیت‌های جدید
- پشتیبانی از پروتکل استاندارد
- اعتبارسنجی پیام‌ها
- مدیریت انواع مختلف پیام
- آمارگیری پیشرفته

### 3. عملکرد بهینه
- تشخیص سریع نوع پیام
- مسیریابی هوشمند
- حداقل overhead

## آمارگیری

Enhanced handler آمارهای مفیدی ارائه می‌دهد:

```python
from enhanced_websocket_handler import get_enhanced_handler

handler = get_enhanced_handler()
stats = handler.get_stats()

print(f"Total requests: {stats['total_requests']}")
print(f"Legacy requests: {stats['legacy_requests']}")
print(f"Protocol requests: {stats['protocol_requests']}")
print(f"Protocol percentage: {stats['protocol_percentage']:.1f}%")
```

## تست و اعتبارسنجی

### اجرای تست‌ها:
```bash
python test_enhanced_handler.py
```

### تست عملکرد:
```python
# تست legacy client
import websockets
import json

async def test_legacy():
    uri = "ws://localhost:8702"
    async with websockets.connect(uri) as websocket:
        message = {
            "session_id": "test",
            "step": 0,
            "input_tensors": {"input_ids": "Hello"}
        }
        await websocket.send(json.dumps(message))
        response = await websocket.recv()
        print("Legacy response:", response)

# تست standard protocol client
async def test_protocol():
    uri = "ws://localhost:8702"
    async with websockets.connect(uri) as websocket:
        message = {
            "header": {
                "message_id": "test-123",
                "message_type": "inference_request",
                "protocol_version": "2.0",
                "timestamp": "2024-01-01T12:00:00Z"
            },
            "model_id": "test_model",
            "prompt": "Hello, world!"
        }
        await websocket.send(json.dumps(message))
        response = await websocket.recv()
        print("Protocol response:", response)
```

## نکات مهم

### 1. عدم تداخل
- Enhanced handler **جایگزین** unified_websocket_server.py است
- **فقط یک WebSocket server** در سیستم وجود دارد
- **هیچ تداخل پورتی** رخ نمی‌دهد

### 2. حفظ عملکرد
- **هیچ تغییری** در pipeline execution نمی‌دهد
- **هیچ تغییری** در model loading نمی‌دهد
- **فقط لایه protocol** اضافه می‌شود

### 3. قابلیت توسعه
- آسان برای اضافه کردن message type جدید
- قابل تنظیم برای نیازهای خاص
- سازگار با تغییرات آینده

## خلاصه

Enhanced WebSocket Handler راه‌حل ایده‌آلی است که:
- ✅ مشکل تداخل WebSocket را حل می‌کند
- ✅ پروتکل استاندارد اضافه می‌کند
- ✅ سازگاری کامل با کد موجود دارد
- ✅ عملکرد سیستم را حفظ می‌کند
- ✅ قابلیت توسعه در آینده دارد

**توصیه:** از گزینه 1 (جایگزینی کامل) استفاده کنید تا بهترین نتیجه را بگیرید.