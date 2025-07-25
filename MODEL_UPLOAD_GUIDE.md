# راهنمای آپلود مدل‌ها

## مشکل حجم مدل‌ها

مدل‌های LLM حجم بسیار بالایی دارند (چندین گیگابایت) و نمی‌توانند در Git repository قرار بگیرند.

## راه‌حل‌های آپلود مدل

### 1. Cloud Storage (توصیه شده)

**برای production:**
- **ابرآروان Object Storage**
- **لیارا Object Storage** 
- **AWS S3** (اگر دسترسی دارید)

### 2. FTP/SFTP Upload

**برای شروع:**
- مدل‌ها را مستقیماً روی سرور آپلود کنید
- از طریق FTP یا SFTP

### 3. مراحل آپلود

#### مرحله 1: آماده‌سازی مدل‌ها
```bash
# مدل‌های موجود در assets/models/
assets/models/llama3_1_8b_fp16/blocks/
assets/models/mistral_7b_int4/blocks/
```

#### مرحله 2: آپلود به سرور
```bash
# با FTP یا از طریق پنل هاست
# آپلود به: /media/models/
```

#### مرحله 3: به‌روزرسانی database
```bash
python manage.py setup_models
```

## تنظیمات مورد نیاز

### در settings.py:
```python
# Model storage settings
MODEL_STORAGE_TYPE = 'local'  # یا 'cloud'
MODEL_STORAGE_PATH = '/media/models/'
MODEL_BASE_URL = 'https://tiktrue-backend.liara.run/media/models/'
```

### برای Cloud Storage:
```python
# Cloud storage settings
CLOUD_STORAGE_BUCKET = 'tiktrue-models'
CLOUD_STORAGE_URL = 'https://storage.iran.liara.space/tiktrue-models/'
```

## امنیت مدل‌ها

- مدل‌ها باید فقط برای کاربران احراز هویت شده قابل دسترسی باشند
- استفاده از signed URLs برای دانلود امن
- محدودیت دسترسی بر اساس نوع لایسنس

## مراحل بعدی

1. **فعلاً**: مدل‌ها را مستقیماً روی سرور لیارا آپلود کنید
2. **آینده**: انتقال به Object Storage برای مقیاس‌پذیری بهتر

## نکات مهم

⚠️ **هرگز مدل‌ها را در Git commit نکنید**
⚠️ **حجم مدل‌ها را در نظر بگیرید (چندین GB)**
⚠️ **برای دانلود سریع، CDN استفاده کنید**