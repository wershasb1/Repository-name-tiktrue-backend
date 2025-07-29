# D:\Tiktrue\tiktrue_mvp\networked_distributed_inference\custom_logging.py
import logging
import json
from datetime import datetime
from typing import Dict, Any # برای type hinting

# این دیکشنری برای نگهداری اطلاعات زمینه‌ای لاگ‌ها استفاده می‌شود.
# سایر ماژول‌ها می‌توانند آن را import کرده و مقادیرش را بخوانند یا (با احتیاط) آپدیت کنند.
NODE_ID_FOR_LOGGING_HOLDER: Dict[str, Any] = {
    "id": "UNINITIALIZED_NODE_CTX",      # شناسه پیش‌فرض برای گره تا زمانی که مقدار واقعی تنظیم شود
    "current_session_id": "N/A_CTX",      # شناسه پیش‌فرض برای سشن
    "current_step": -1                    # شماره گام پیش‌فرض
}

class MainJsonFormatter(logging.Formatter):
    """
    فرمت‌دهنده سفارشی برای ایجاد لاگ‌های JSON.
    این کلاس فیلدهای استاندارد لاگ و همچنین فیلدهای سفارشی ارسال شده
    از طریق پارامتر extra در فراخوانی‌های logging را در خروجی JSON قرار می‌دهد.
    """
    def format(self, record: logging.LogRecord) -> str:
        # ایجاد دیکشنری پایه برای خروجی لاگ با فیلدهای استاندارد
        log_output: Dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z", # زمان به فرمت ISO 8601 UTC
            "level": record.levelname,                                                  # سطح لاگ (DEBUG, INFO, ERROR, ...)
            "message": record.getMessage(),                                             # پیام اصلی لاگ
            "module": record.module,                                                    # نام ماژولی که لاگ از آنجا ثبت شده
            "funcName": record.funcName,                                                # نام تابعی که لاگ از آنجا ثبت شده
            "lineno": record.lineno,                                                    # شماره خطی که لاگ از آنجا ثبت شده
        }

        # استخراج فیلدهای سفارشی از پارامتر 'extra' در فراخوانی logging
        # این فیلدها باید به صورت یک دیکشنری با کلید 'custom_extra_fields' پاس داده شوند
        # مثال: logging.info("پیام", extra={"custom_extra_fields": {"event_type": "MY_EVENT", ...}})
        custom_extra = getattr(record, 'custom_extra_fields', None)

        if isinstance(custom_extra, dict):
            # اگر custom_extra_fields یک دیکشنری معتبر است:
            log_output["event_type"] = custom_extra.get("event_type", "UNKNOWN_EVENT_TYPE_IN_EXTRA")
            
            # برای node_id، ابتدا از مقدار پاس داده شده در extra استفاده کن،
            # اگر نبود، از مقدار موجود در NODE_ID_FOR_LOGGING_HOLDER استفاده کن.
            log_output["node_id"] = NODE_ID_FOR_LOGGING_HOLDER.get("id", "NODE_ID_CTX_FALLBACK_NO_EXTRA")
            log_output["session_id"] = NODE_ID_FOR_LOGGING_HOLDER.get("current_session_id", "SESSION_ID_CTX_FALLBACK_NO_EXTRA")
            log_output["step"] = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1003)            
            session_id_from_extra = custom_extra.get("session_id")
            if session_id_from_extra is not None:
                log_output["session_id"] = session_id_from_extra
            else:
                # اگر session_id در extra نبود، از مقدار holder به عنوان fallback استفاده کن
                log_output["session_id"] = NODE_ID_FOR_LOGGING_HOLDER.get("current_session_id", "SESSION_ID_CTX_FALLBACK_WHEN_MISSING_IN_EXTRA")

            step_from_extra = custom_extra.get("step")
            if step_from_extra is not None:
                log_output["step"] = step_from_extra
            else:
                # اگر step در extra نبود، از مقدار holder به عنوان fallback استفاده کن
                log_output["step"] = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1002) # یک مقدار خاص برای fallback

            # مدیریت فیلد 'data' که می‌تواند حاوی جزئیات بیشتری باشد
            data_field = custom_extra.get("data")
            if isinstance(data_field, dict):
                log_output["data"] = data_field  # اگر 'data' یک دیکشنری است، مستقیماً اضافه شود
            elif data_field is not None:
                # اگر 'data' وجود دارد اما دیکشنری نیست، آن را در یک کلید داخلی قرار بده
                log_output["data"] = {"_raw_custom_data_payload_": data_field}
            # اگر 'data' در custom_extra_fields تعریف نشده باشد، به خروجی اضافه نمی‌شود.

        else:
            # این حالت زمانی رخ می‌دهد که custom_extra_fields پاس داده نشده یا از نوع دیکشنری نیست.
            # این برای لاگ‌های کتابخانه‌های خارجی که از استاندارد ما پیروی نمی‌کنند، محتمل است.
            # در این حالت، از مقادیر موجود در NODE_ID_FOR_LOGGING_HOLDER به عنوان fallback استفاده می‌کنیم.
            log_output["event_type"] = "LOGGING_STANDARD_VIOLATION_NO_VALID_CUSTOM_EXTRA"
            log_output["node_id"] = NODE_ID_FOR_LOGGING_HOLDER.get("id", "NODE_ID_CTX_FALLBACK_NO_EXTRA")
            log_output["session_id"] = NODE_ID_FOR_LOGGING_HOLDER.get("current_session_id", "SESSION_ID_CTX_FALLBACK_NO_EXTRA")
            log_output["step"] = NODE_ID_FOR_LOGGING_HOLDER.get("current_step", -1003) # مقدار خاص برای این حالت

        # مدیریت اطلاعات استثنا (Exception) اگر لاگ خطا باشد (record.exc_info غیر None باشد)
        if record.exc_info:
            # اگر فیلد 'data' قبلاً ایجاد نشده یا از نوع دیکشنری نیست، آن را ایجاد کن
            if "data" not in log_output or not isinstance(log_output.get("data"), dict):
                log_output["data"] = {}
            
            # افزودن جزئیات استثنا به بخش 'data'
            log_output["data"]["exception_traceback_full"] = self.formatException(record.exc_info) # Traceback کامل
            
            # استخراج نوع و مقدار استثنا
            exc_type, exc_value, _ = record.exc_info # _ به traceback object اشاره دارد که قبلاً فرمت شده

            # اضافه کردن نام کلاس استثنا و پیام خطا، اگر قبلاً توسط کد فراخواننده در 'data' تنظیم نشده باشند
            if "exception_class_name" not in log_output["data"]:
                log_output["data"]["exception_class_name"] = exc_type.__name__ if exc_type else "N/A"
            
            if "error_message" not in log_output["data"]: # این نام ('error_message') مطابق با ساختار شماست
                log_output["data"]["error_message"] = str(exc_value) if exc_value else "N/A"
        
        # تبدیل دیکشنری نهایی به رشته JSON
        # ensure_ascii=False برای پشتیبانی از کاراکترهای غیر ASCII (مثل فارسی)
        # default=str برای تبدیل اشیائی که به طور پیش‌فرض قابل سریال‌سازی به JSON نیستند (مثل datetime)
        return json.dumps(log_output, ensure_ascii=False, default=str)