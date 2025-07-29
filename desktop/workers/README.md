# Worker Components

این پوشه شامل فایل‌های مربوط به worker ها، scheduler و سیستم‌های پردازش است.

## فایل‌ها:
- `worker_lib.py` - پیاده‌سازی CPU و GPU worker ها
- `scheduler_lib.py` - زمان‌بندی و تقسیم کار
- `homf_lib.py` - مدیریت cache مدل‌ها
- `dynamic_profiler.py` - profiling دینامیک سیستم
- `static_profiler.py` - profiling استاتیک
- `paged_kv_cache_lib.py` - مدیریت KV cache
- `sequential_gpu_worker_lib.py` - worker های GPU متوالی

## هدف:
مدیریت پردازش، تقسیم کار و بهینه‌سازی عملکرد سیستم.