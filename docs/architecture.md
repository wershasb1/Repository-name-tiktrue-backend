# معماری پروژه TikTrue Platform

## مقدمه

این سند معماری پروژه TikTrue Platform را توضیح می‌دهد. هدف از این سند، ارائه یک نمای کلی از ساختار پروژه، ارتباط بین ماژول‌ها و نحوه سازماندهی فایل‌ها است.

## ساختار پوشه‌ها

ساختار پوشه‌های پروژه به صورت زیر سازماندهی شده است:

```
TikTrue_Platform/
├── core/                    # فایل‌های اصلی سیستم
│   ├── model_node.py        # هسته اصلی سیستم استنتاج
│   ├── network_manager.py   # مدیریت شبکه و ارتباطات
│   ├── config_manager.py    # مدیریت تنظیمات
│   ├── protocol_spec.py     # مشخصات پروتکل ارتباطی
│   ├── service_runner.py    # اجرا کننده سرویس
│   └── README.md            # توضیحات پوشه core
│
├── workers/                 # فایل‌های worker و scheduler
│   ├── worker_lib.py        # کتابخانه worker
│   ├── scheduler_lib.py     # کتابخانه scheduler
│   ├── homf_lib.py          # کتابخانه HOMF
│   ├── dynamic_profiler.py  # پروفایلر پویا
│   ├── static_profiler.py   # پروفایلر ایستا
│   ├── paged_kv_cache_lib.py # کتابخانه KV Cache
│   └── README.md            # توضیحات پوشه workers
│
├── interfaces/              # رابط‌های کاربری
│   ├── chatbot_interface.py # رابط چت‌بات
│   ├── chat_interface.py    # رابط چت
│   ├── enhanced_chat_interface.py # رابط چت پیشرفته
│   ├── session_ui.py        # رابط مدیریت جلسات
│   └── README.md            # توضیحات پوشه interfaces
│
├── network/                 # فایل‌های شبکه و ارتباطات
│   ├── websocket_server.py  # سرور WebSocket
│   ├── unified_websocket_server.py # سرور WebSocket یکپارچه
│   ├── enhanced_websocket_handler.py # هندلر WebSocket پیشرفته
│   ├── network_discovery.py # کشف شبکه
│   └── README.md            # توضیحات پوشه network
│
├── security/                # فایل‌های امنیتی
│   ├── license_validator.py # اعتبارسنجی لایسنس
│   ├── auth_manager.py      # مدیریت احراز هویت
│   ├── crypto_layer.py      # لایه رمزنگاری
│   ├── hardware_fingerprint.py # اثر انگشت سخت‌افزاری
│   └── README.md            # توضیحات پوشه security
│
├── models/                  # مدیریت مدل‌ها
│   ├── model_downloader.py  # دانلود کننده مدل
│   ├── model_encryption.py  # رمزنگاری مدل
│   ├── model_verification.py # اعتبارسنجی مدل
│   └── README.md            # توضیحات پوشه models
│
├── config/                  # فایل‌های کانفیگ
│   ├── network_config.json  # تنظیمات شبکه
│   ├── portable_config.json # تنظیمات قابل حمل
│   ├── performance_profile.json # پروفایل عملکرد
│   └── README.md            # توضیحات پوشه config
│
├── tests/                   # تمام فایل‌های تست
│   ├── unit/                # تست‌های واحد
│   ├── integration/         # تست‌های یکپارچگی
│   ├── demo/                # دموها
│   └── README.md            # توضیحات پوشه tests
│
├── build/                   # فایل‌های build و installer
│   ├── Build-Installer.ps1  # اسکریپت ساخت نصب‌کننده
│   ├── build_installer_complete.py # اسکریپت کامل ساخت نصب‌کننده
│   ├── installer.nsi        # اسکریپت NSIS
│   ├── validate_installer_build.py # اعتبارسنجی نصب‌کننده
│   └── README.md            # توضیحات پوشه build
│
├── docs/                    # مستندات
│   ├── README_SETUP.md      # راهنمای نصب
│   ├── PRODUCTION_READY.md  # آمادگی برای تولید
│   ├── architecture.md      # معماری سیستم (این فایل)
│   ├── KEY_MANAGEMENT_IMPLEMENTATION_SUMMARY.md # خلاصه پیاده‌سازی مدیریت کلید
│   ├── ENHANCED_WEBSOCKET_INTEGRATION.md # ادغام WebSocket پیشرفته
│   ├── Data_Full_Project_V1.md # مستندات کامل پروژه
│   └── README.md            # توضیحات پوشه docs
│
├── utils/                   # ابزارهای کمکی
│   ├── setup_validator.py   # اعتبارسنج نصب
│   ├── serialization_utils.py # ابزارهای سریالیزاسیون
│   └── README.md            # توضیحات پوشه utils
│
├── assets/                  # دارایی‌ها
│   ├── encryption/          # فایل‌های رمزنگاری
│   ├── models/              # فایل‌های مدل
│   ├── verification/        # فایل‌های اعتبارسنجی
│   └── README.md            # توضیحات پوشه assets
│
├── logs/                    # لاگ‌ها
│   └── README.md            # توضیحات پوشه logs
│
├── sessions/                # جلسات
│   └── README.md            # توضیحات پوشه sessions
│
├── data/                    # داده‌ها
│   └── README.md            # توضیحات پوشه data
│
├── static/                  # فایل‌های استاتیک
│   ├── css/                 # فایل‌های CSS
│   ├── js/                  # فایل‌های JavaScript
│   └── README.md            # توضیحات پوشه static
│
├── templates/               # قالب‌ها
│   └── README.md            # توضیحات پوشه templates
│
└── README.md                # توضیحات اصلی پروژه
```

## ماژول‌های اصلی

### 1. Core System
این ماژول شامل فایل‌های اصلی سیستم است که هسته اصلی پلتفرم را تشکیل می‌دهند:
- `model_node.py`: هسته اصلی سیستم استنتاج که مدل‌ها را بارگذاری و اجرا می‌کند
- `network_manager.py`: مدیریت شبکه و ارتباطات بین نودها
- `config_manager.py`: مدیریت تنظیمات سیستم
- `protocol_spec.py`: مشخصات پروتکل ارتباطی
- `service_runner.py`: اجرا کننده سرویس ویندوز

### 2. Workers
این ماژول شامل فایل‌های مرتبط با پردازش و scheduling است:
- `worker_lib.py`: کتابخانه worker برای پردازش بلاک‌های مدل
- `scheduler_lib.py`: کتابخانه scheduler برای زمان‌بندی اجرای بلاک‌ها
- `homf_lib.py`: کتابخانه HOMF برای مدیریت حافظه
- `dynamic_profiler.py`: پروفایلر پویا برای بهینه‌سازی عملکرد
- `static_profiler.py`: پروفایلر ایستا برای بهینه‌سازی عملکرد
- `paged_kv_cache_lib.py`: کتابخانه KV Cache برای مدیریت حافظه کش

### 3. Interfaces
این ماژول شامل فایل‌های مرتبط با رابط کاربری است:
- `chatbot_interface.py`: رابط چت‌بات
- `chat_interface.py`: رابط چت
- `enhanced_chat_interface.py`: رابط چت پیشرفته
- `session_ui.py`: رابط مدیریت جلسات

### 4. Network
این ماژول شامل فایل‌های مرتبط با ارتباطات شبکه است:
- `websocket_server.py`: سرور WebSocket
- `unified_websocket_server.py`: سرور WebSocket یکپارچه
- `enhanced_websocket_handler.py`: هندلر WebSocket پیشرفته
- `network_discovery.py`: کشف شبکه

### 5. Security
این ماژول شامل فایل‌های مرتبط با امنیت و احراز هویت است:
- `license_validator.py`: اعتبارسنجی لایسنس
- `auth_manager.py`: مدیریت احراز هویت
- `crypto_layer.py`: لایه رمزنگاری
- `hardware_fingerprint.py`: اثر انگشت سخت‌افزاری

### 6. Models
این ماژول شامل فایل‌های مرتبط با مدیریت مدل‌ها است:
- `model_downloader.py`: دانلود کننده مدل
- `model_encryption.py`: رمزنگاری مدل
- `model_verification.py`: اعتبارسنجی مدل

### 7. Config
این ماژول شامل فایل‌های تنظیمات است:
- `network_config.json`: تنظیمات شبکه
- `portable_config.json`: تنظیمات قابل حمل
- `performance_profile.json`: پروفایل عملکرد

### 8. Tests
این ماژول شامل فایل‌های تست است:
- `unit/`: تست‌های واحد
- `integration/`: تست‌های یکپارچگی
- `demo/`: دموها

### 9. Build
این ماژول شامل فایل‌های مرتبط با ساخت و نصب است:
- `Build-Installer.ps1`: اسکریپت ساخت نصب‌کننده
- `build_installer_complete.py`: اسکریپت کامل ساخت نصب‌کننده
- `installer.nsi`: اسکریپت NSIS
- `validate_installer_build.py`: اعتبارسنجی نصب‌کننده

### 10. Docs
این ماژول شامل مستندات پروژه است:
- `README_SETUP.md`: راهنمای نصب
- `PRODUCTION_READY.md`: آمادگی برای تولید
- `architecture.md`: معماری سیستم (این فایل)
- `KEY_MANAGEMENT_IMPLEMENTATION_SUMMARY.md`: خلاصه پیاده‌سازی مدیریت کلید
- `ENHANCED_WEBSOCKET_INTEGRATION.md`: ادغام WebSocket پیشرفته
- `Data_Full_Project_V1.md`: مستندات کامل پروژه

### 11. Utils
این ماژول شامل ابزارهای کمکی است:
- `setup_validator.py`: اعتبارسنج نصب
- `serialization_utils.py`: ابزارهای سریالیزاسیون

## جریان داده

جریان داده در سیستم به صورت زیر است:

1. **ورودی کاربر**:
   - کاربر از طریق `interfaces/chatbot_interface.py` یا `interfaces/enhanced_chat_interface.py` با سیستم تعامل می‌کند.
   - درخواست‌ها به صورت WebSocket به سرور ارسال می‌شوند.

2. **پردازش درخواست**:
   - درخواست‌ها توسط `network/enhanced_websocket_handler.py` دریافت و پردازش می‌شوند.
   - درخواست‌ها به `core/model_node.py` ارسال می‌شوند.

3. **استنتاج مدل**:
   - `core/model_node.py` با استفاده از `workers/worker_lib.py` و `workers/scheduler_lib.py` بلاک‌های مدل را اجرا می‌کند.
   - نتایج به کاربر برگردانده می‌شوند.

4. **مدیریت جلسات**:
   - جلسات توسط `interfaces/session_ui.py` مدیریت می‌شوند.
   - داده‌های جلسه در پوشه `sessions/` ذخیره می‌شوند.

5. **امنیت و احراز هویت**:
   - احراز هویت توسط `security/auth_manager.py` انجام می‌شود.
   - رمزنگاری توسط `security/crypto_layer.py` انجام می‌شود.
   - اعتبارسنجی لایسنس توسط `security/license_validator.py` انجام می‌شود.

6. **مدیریت مدل‌ها**:
   - دانلود مدل‌ها توسط `models/model_downloader.py` انجام می‌شود.
   - رمزنگاری مدل‌ها توسط `models/model_encryption.py` انجام می‌شود.
   - اعتبارسنجی مدل‌ها توسط `models/model_verification.py` انجام می‌شود.

## نتیجه‌گیری

ساختار جدید پروژه TikTrue Platform به صورت منطقی و سازمان‌یافته طراحی شده است. این ساختار به توسعه‌دهندگان کمک می‌کند تا به راحتی فایل‌های مورد نیاز خود را پیدا کنند و با سیستم کار کنند. همچنین، این ساختار به مدیریت بهتر کد، کاهش وابستگی‌ها و افزایش قابلیت نگهداری کمک می‌کند.