# Windows Service Integration Documentation
## TikTrue Distributed LLM Platform

### نسخه: 1.0.0
### تاریخ: 02/04/1404

---

## 📋 فهرست مطالب

1. [مقدمه](#مقدمه)
2. [معماری سیستم](#معماری-سیستم)
3. [User Journey Compliance](#user-journey-compliance)
4. [اجزای پیاده‌سازی شده](#اجزای-پیاده‌سازی-شده)
5. [نحوه عملکرد](#نحوه-عملکرد)
6. [مدیریت سرویس](#مدیریت-سرویس)
7. [نظارت و مانیتورینگ](#نظارت-و-مانیتورینگ)
8. [تست و اعتبارسنجی](#تست-و-اعتبارسنجی)
9. [عیب‌یابی](#عیب‌یابی)

---

## 🎯 مقدمه

Windows Service Integration برای TikTrue Platform یک سیستم جامع برای اجرای پلتفرم به صورت Windows Service است که **بدون وابستگی به فایل‌های مدل** عمل می‌کند و کاملاً طبق User Journey طراحی شده است.

### ویژگی‌های کلیدی:
- ✅ **بدون مدل**: installer فقط core platform را نصب می‌کند
- ✅ **User Journey Compliant**: مدل‌ها بعد از نصب دانلود می‌شوند
- ✅ **Auto-start**: راه‌اندازی خودکار با Windows
- ✅ **Health Monitoring**: نظارت مداوم بر سلامت سیستم
- ✅ **Dual Mode Support**: پشتیبانی از Admin/Client modes
- ✅ **No Conflicts**: بدون تداخل با کدهای موجود

---

## 🏗️ معماری سیستم

```
TikTrue Windows Service Architecture

┌─────────────────────────────────────────────────────────────┐
│                    Windows Service Layer                    │
├─────────────────────────────────────────────────────────────┤
│  windows_service.py     │  service_installer.py            │
│  - Service Wrapper      │  - Installation Management       │
│  - Lifecycle Management │  - Dependency Validation         │
│  - Process Monitoring   │  - Configuration Management      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Core Service Runner                       │
├─────────────────────────────────────────────────────────────┤
│  core/service_runner.py                                     │
│  - Main Application Logic (NO MODELS)                      │
│  - Network Discovery & Communication                       │
│  - License Validation                                       │
│  - Admin/Client/Discovery Modes                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Service Monitoring                         │
├─────────────────────────────────────────────────────────────┤
│  service_monitor.py                                         │
│  - Health Checks (CPU, Memory, Disk, Network)              │
│  - Metrics Collection                                       │
│  - Alert System                                             │
│  - Report Generation                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 User Journey Compliance

### مطابقت کامل با User Journey:

#### 1. **نصب اولیه (Installation)**
```
✅ Installer فقط core platform را نصب می‌کند
✅ هیچ فایل مدلی در installer وجود ندارد
✅ Service به صورت خودکار نصب و راه‌اندازی می‌شود
```

#### 2. **اولین اجرا (First Run)**
```
✅ Application از کاربر می‌پرسد: Admin یا Client mode؟
✅ Admin mode: نیاز به login آنلاین دارد
✅ Client mode: بدون نیاز به login آنلاین
```

#### 3. **Admin Mode Flow**
```
✅ Login آنلاین با backend server
✅ License validation و دریافت اطلاعات plan
✅ دانلود مدل‌های مجاز از server
✅ ذخیره local و رمزنگاری مدل‌ها
✅ عملکرد offline بعد از دانلود
```

#### 4. **Client Mode Flow**
```
✅ جستجوی شبکه‌های محلی
✅ درخواست اتصال به admin
✅ دریافت model blocks از admin node
✅ عملکرد offline بعد از دریافت
```

---

## 🔧 اجزای پیاده‌سازی شده

### 1. **Windows Service Wrapper** (`windows_service.py`)

```python
class TikTrueLLMService(win32serviceutil.ServiceFramework):
    """
    Windows Service wrapper که:
    - Service lifecycle را مدیریت می‌کند
    - core/service_runner.py را به عنوان main process اجرا می‌کند
    - Auto-restart در صورت خرابی
    - Graceful shutdown
    """
```

**ویژگی‌ها:**
- ✅ Service lifecycle management
- ✅ Process monitoring و restart
- ✅ Configuration management
- ✅ Windows Event Log integration
- ✅ Graceful shutdown handling

### 2. **Service Runner** (`core/service_runner.py`)

```python
class TikTrueServiceRunner:
    """
    Main service logic که:
    - بدون مدل عمل می‌کند
    - Network discovery و communication
    - License validation (بدون مدل)
    - Admin/Client/Discovery modes
    """
```

**ویژگی‌ها:**
- ✅ **NO MODEL DEPENDENCIES**: هیچ وابستگی به فایل مدل
- ✅ Network discovery service
- ✅ WebSocket communication
- ✅ License validation
- ✅ Background task management
- ✅ Health monitoring integration

### 3. **Service Monitor** (`service_monitor.py`)

```python
class ServiceMonitor:
    """
    System monitoring که:
    - Health checks (CPU, Memory, Disk, Network)
    - Metrics collection
    - Alert system
    - Report generation
    """
```

**ویژگی‌ها:**
- ✅ Real-time health monitoring
- ✅ Configurable alert thresholds
- ✅ Historical metrics storage
- ✅ JSON report export
- ✅ Custom health checks support

### 4. **Service Installer** (`service_installer.py`)

```python
class EnhancedServiceInstaller:
    """
    Advanced installer که:
    - Dependency validation
    - Service configuration
    - Management scripts creation
    - Installation validation
    """
```

**ویژگی‌ها:**
- ✅ Pre-installation validation
- ✅ Dependency management
- ✅ Service configuration
- ✅ Management scripts generation
- ✅ Installation status tracking

---

## ⚙️ نحوه عملکرد

### Service Startup Sequence:

```
1. Windows Service Manager
   ↓
2. TikTrueLLMService.SvcDoRun()
   ↓
3. Start core/service_runner.py
   ↓
4. TikTrueServiceRunner.start_service()
   ↓
5. Initialize components:
   - ConfigManager (NO MODELS)
   - NetworkDiscovery
   - WebSocket Server
   - LicenseValidator
   - ServiceMonitor
   ↓
6. Start background tasks:
   - License validation
   - Network scanning
   - Health monitoring
   ↓
7. Service ready (NO MODELS LOADED)
```

### Service Modes:

#### **Discovery Mode** (Default)
```python
service_mode = ServiceMode.DISCOVERY
# - Network discovery active
# - WebSocket server listening
# - License validation
# - NO model loading
```

#### **Admin Mode**
```python
service_mode = ServiceMode.ADMIN
# - Network announcement
# - Client management
# - Model download (after login)
# - License enforcement
```

#### **Client Mode**
```python
service_mode = ServiceMode.CLIENT
# - Network discovery
# - Connection requests
# - Model block reception
# - Distributed inference
```

---

## 🛠️ مدیریت سرویس

### نصب سرویس:
```batch
# Method 1: Using installer
python service_installer.py --install

# Method 2: Using batch script
scripts\install_service.bat

# Method 3: Direct service command
python windows_service.py install
```

### مدیریت سرویس:
```batch
# Start service
python windows_service.py start
net start TikTrueLLMService

# Stop service
python windows_service.py stop
net stop TikTrueLLMService

# Service status
python windows_service.py status
sc query TikTrueLLMService

# Restart service
python windows_service.py restart
```

### حذف سرویس:
```batch
# Method 1: Using installer
python service_installer.py --uninstall

# Method 2: Using batch script
scripts\uninstall_service.bat

# Method 3: Direct service command
python windows_service.py remove
```

---

## 📊 نظارت و مانیتورینگ

### Health Checks:

#### **System Resources**
```python
def _check_system_resources(self):
    # CPU usage monitoring
    # Memory usage monitoring
    # Alert thresholds: CPU > 80%, Memory > 85%
```

#### **Disk Space**
```python
def _check_disk_space(self):
    # Disk usage monitoring
    # Alert threshold: Disk > 90%
```

#### **Network Connectivity**
```python
def _check_network_connectivity(self):
    # Active network interfaces
    # Established connections
    # Network health status
```

#### **Service Process**
```python
def _check_service_process(self):
    # Process status monitoring
    # Memory usage tracking
    # Thread count monitoring
```

### Metrics Collection:
```python
@dataclass
class ServiceMetrics:
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_usage_percent: float
    network_connections: int
    uptime_seconds: float
    timestamp: datetime
```

### Health Status API:
```python
# Get current health status
status = get_health_status()

# Export health report
report_path = monitor.export_health_report()
```

---

## 🧪 تست و اعتبارسنجی

### Unit Tests (`tests/unit/test_windows_service.py`):

#### **Service Lifecycle Tests**
```python
def test_service_initialization()
def test_start_stop_service()
def test_service_config_loading()
def test_main_process_management()
```

#### **Configuration Tests**
```python
def test_config_validation()
def test_config_updates()
def test_dependency_validation()
```

#### **Monitoring Tests**
```python
def test_health_checks()
def test_metrics_collection()
def test_alert_system()
```

### Integration Tests:
```python
def test_service_runner_initialization()
def test_network_discovery_integration()
def test_license_validation_integration()
```

### اجرای تست‌ها:
```bash
# Run all service tests
python -m pytest tests/unit/test_windows_service.py -v

# Run specific test
python tests/unit/test_windows_service.py
```

---

## 🔍 عیب‌یابی

### Log Files:
```
logs/
├── windows_service.log      # Service wrapper logs
├── service_runner.log       # Main application logs
├── service_monitor.log      # Health monitoring logs
└── service_installer.log    # Installation logs
```

### Common Issues:

#### **Service Won't Start**
```
1. Check logs: logs/windows_service.log
2. Verify Python path in service_config.json
3. Check dependencies: python service_installer.py --check-deps
4. Validate configuration: python service_installer.py --status
```

#### **License Validation Fails**
```
1. Check license file exists and valid
2. Verify hardware fingerprint
3. Check network connectivity for online validation
4. Review logs: logs/service_runner.log
```

#### **Network Discovery Issues**
```
1. Check firewall settings (ports 8765, 8766)
2. Verify network interfaces are active
3. Check service_config.json network settings
4. Review network logs in service_runner.log
```

#### **High Resource Usage**
```
1. Check health status: python service_monitor.py status
2. Review metrics: python service_monitor.py report
3. Adjust monitoring intervals in service_config.json
4. Check for memory leaks in logs
```

### Debug Mode:
```bash
# Run service in debug mode (console)
python windows_service.py debug

# Monitor service health
python service_monitor.py start

# Get detailed status
python service_installer.py --status
```

---

## 📝 Configuration Files

### `service_config.json`:
```json
{
  "service_mode": "discovery",
  "websocket_host": "0.0.0.0",
  "websocket_port": 8765,
  "enable_discovery": true,
  "enable_monitoring": true,
  "license_check_interval": 3600,
  "network_scan_interval": 300,
  "health_check_interval": 60,
  "main_script": "core/service_runner.py",
  "auto_start": true,
  "restart_on_failure": true
}
```

---

## ✅ خلاصه مطابقت با User Journey

### ✅ **نصب (Installation Phase)**
- Installer فقط core platform (بدون مدل)
- Service نصب و راه‌اندازی خودکار
- هیچ فایل مدلی در installer نیست

### ✅ **اجرای اولیه (First Run Phase)**
- Service در حالت Discovery اجرا می‌شود
- Application از کاربر mode selection می‌پرسد
- هیچ مدلی لود نمی‌شود

### ✅ **Admin Mode Flow**
- Login آنلاین الزامی
- License validation
- Model download از backend
- Local storage و encryption
- Offline operation بعد از setup

### ✅ **Client Mode Flow**
- بدون نیاز به login آنلاین
- Network discovery
- Model block reception از admin
- Offline operation بعد از setup

### ✅ **Service Operation**
- Background service بدون UI
- Health monitoring مداوم
- Auto-restart در صورت خرابی
- Graceful shutdown

---

## 🔒 امنیت و License Management

### License Integration:
- Hardware-bound license validation
- Runtime license checks
- Model access control
- Network permission management

### Security Features:
- Encrypted configuration storage
- Secure communication protocols
- Hardware fingerprinting
- Audit logging

---

**این مستندات نشان می‌دهد که Windows Service Integration کاملاً طبق User Journey پیاده‌سازی شده و هیچ تداخلی با کدهای موجود ندارد.**