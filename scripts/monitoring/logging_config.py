#!/usr/bin/env python3
"""
TikTrue Platform - Centralized Logging Configuration

This script provides centralized logging configuration for all TikTrue services:
- Structured logging setup
- Log rotation and retention
- Performance logging
- Security event logging
- Distributed logging coordination

Requirements: 3.1 - Centralized logging system
"""

import os
import sys
import json
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading
import queue
import time

class TikTrueFormatter(logging.Formatter):
    """Custom formatter for TikTrue platform logs"""
    
    def __init__(self, include_context: bool = True):
        self.include_context = include_context
        super().__init__()
        
    def format(self, record):
        """Format log record with TikTrue-specific structure"""
        # Base log structure
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add thread information
        if hasattr(record, 'thread') and record.thread:
            log_entry["thread_id"] = record.thread
            log_entry["thread_name"] = getattr(record, 'threadName', 'Unknown')
            
        # Add process information
        if hasattr(record, 'process') and record.process:
            log_entry["process_id"] = record.process
            
        # Add exception information
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None
            }
            
        # Add custom context if available
        if self.include_context and hasattr(record, 'context'):
            log_entry["context"] = record.context
            
        # Add performance metrics if available
        if hasattr(record, 'performance'):
            log_entry["performance"] = record.performance
            
        # Add security context if available
        if hasattr(record, 'security'):
            log_entry["security"] = record.security
            
        return json.dumps(log_entry, ensure_ascii=False)

class PerformanceLogger:
    """Performance-specific logging utilities"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
    def log_request(self, method: str, endpoint: str, duration_ms: float, 
                   status_code: int, user_id: str = None):
        """Log API request performance"""
        performance_data = {
            "type": "api_request",
            "method": method,
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "status_code": status_code,
            "user_id": user_id
        }
        
        # Create log record with performance context
        record = logging.LogRecord(
            name=self.logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="API Request",
            args=(),
            exc_info=None
        )
        record.performance = performance_data
        
        self.logger.handle(record)
        
    def log_database_query(self, query_type: str, table: str, duration_ms: float, 
                          rows_affected: int = None):
        """Log database query performance"""
        performance_data = {
            "type": "database_query",
            "query_type": query_type,
            "table": table,
            "duration_ms": duration_ms,
            "rows_affected": rows_affected
        }
        
        record = logging.LogRecord(
            name=self.logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Database Query",
            args=(),
            exc_info=None
        )
        record.performance = performance_data
        
        self.logger.handle(record)
        
    def log_model_inference(self, model_id: str, input_tokens: int, 
                           output_tokens: int, duration_ms: float):
        """Log model inference performance"""
        performance_data = {
            "type": "model_inference",
            "model_id": model_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_ms": duration_ms,
            "tokens_per_second": (input_tokens + output_tokens) / (duration_ms / 1000) if duration_ms > 0 else 0
        }
        
        record = logging.LogRecord(
            name=self.logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Model Inference",
            args=(),
            exc_info=None
        )
        record.performance = performance_data
        
        self.logger.handle(record)

class SecurityLogger:
    """Security-specific logging utilities"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
    def log_authentication(self, user_id: str, success: bool, ip_address: str, 
                          user_agent: str = None, failure_reason: str = None):
        """Log authentication attempts"""
        security_data = {
            "type": "authentication",
            "user_id": user_id,
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "failure_reason": failure_reason
        }
        
        level = logging.INFO if success else logging.WARNING
        message = "Authentication Success" if success else "Authentication Failure"
        
        record = logging.LogRecord(
            name=self.logger.name,
            level=level,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        record.security = security_data
        
        self.logger.handle(record)
        
    def log_authorization(self, user_id: str, resource: str, action: str, 
                         granted: bool, reason: str = None):
        """Log authorization decisions"""
        security_data = {
            "type": "authorization",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "granted": granted,
            "reason": reason
        }
        
        level = logging.INFO if granted else logging.WARNING
        message = "Authorization Granted" if granted else "Authorization Denied"
        
        record = logging.LogRecord(
            name=self.logger.name,
            level=level,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        record.security = security_data
        
        self.logger.handle(record)
        
    def log_suspicious_activity(self, user_id: str, activity_type: str, 
                               details: Dict[str, Any], severity: str = "MEDIUM"):
        """Log suspicious activities"""
        security_data = {
            "type": "suspicious_activity",
            "user_id": user_id,
            "activity_type": activity_type,
            "details": details,
            "severity": severity
        }
        
        level = logging.ERROR if severity == "HIGH" else logging.WARNING
        
        record = logging.LogRecord(
            name=self.logger.name,
            level=level,
            pathname="",
            lineno=0,
            msg=f"Suspicious Activity: {activity_type}",
            args=(),
            exc_info=None
        )
        record.security = security_data
        
        self.logger.handle(record)

class AsyncLogHandler(logging.Handler):
    """Asynchronous log handler for high-performance logging"""
    
    def __init__(self, target_handler: logging.Handler, queue_size: int = 1000):
        super().__init__()
        self.target_handler = target_handler
        self.log_queue = queue.Queue(maxsize=queue_size)
        self._stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
    def emit(self, record):
        """Emit log record asynchronously"""
        try:
            self.log_queue.put_nowait(record)
        except queue.Full:
            # Drop log if queue is full to prevent blocking
            pass
            
    def _worker(self):
        """Worker thread to process log records"""
        while not self._stop_event.is_set():
            try:
                record = self.log_queue.get(timeout=1)
                self.target_handler.emit(record)
                self.log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                # Handle errors in worker thread
                print(f"Error in async log worker: {e}", file=sys.stderr)
                
    def close(self):
        """Close the handler and stop worker thread"""
        self._stop_event.set()
        self.worker_thread.join(timeout=5)
        self.target_handler.close()
        super().close()

class TikTrueLoggingConfig:
    """Centralized logging configuration for TikTrue platform"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.project_root = Path(__file__).parent.parent.parent
        self.config = self.load_config(config_file)
        self.loggers: Dict[str, logging.Logger] = {}
        
    def load_config(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        """Load logging configuration"""
        default_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "root_level": "INFO",
            "log_directory": "temp/logs",
            "max_file_size_mb": 50,
            "backup_count": 5,
            "retention_days": 30,
            "loggers": {
                "tiktrue": {
                    "level": "INFO",
                    "handlers": ["file", "console"],
                    "propagate": False
                },
                "tiktrue.api": {
                    "level": "INFO",
                    "handlers": ["api_file", "console"],
                    "propagate": False
                },
                "tiktrue.security": {
                    "level": "WARNING",
                    "handlers": ["security_file", "console"],
                    "propagate": False
                },
                "tiktrue.performance": {
                    "level": "INFO",
                    "handlers": ["performance_file"],
                    "propagate": False
                },
                "tiktrue.model": {
                    "level": "INFO",
                    "handlers": ["model_file", "console"],
                    "propagate": False
                },
                "tiktrue.database": {
                    "level": "WARNING",
                    "handlers": ["database_file", "console"],
                    "propagate": False
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "INFO",
                    "formatter": "json",
                    "filename": "tiktrue.log",
                    "maxBytes": 52428800,  # 50MB
                    "backupCount": 5
                },
                "api_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "INFO",
                    "formatter": "json",
                    "filename": "tiktrue_api.log",
                    "maxBytes": 52428800,
                    "backupCount": 5
                },
                "security_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "WARNING",
                    "formatter": "json",
                    "filename": "tiktrue_security.log",
                    "maxBytes": 52428800,
                    "backupCount": 10  # Keep more security logs
                },
                "performance_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "INFO",
                    "formatter": "json",
                    "filename": "tiktrue_performance.log",
                    "maxBytes": 52428800,
                    "backupCount": 3
                },
                "model_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "INFO",
                    "formatter": "json",
                    "filename": "tiktrue_model.log",
                    "maxBytes": 52428800,
                    "backupCount": 5
                },
                "database_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "WARNING",
                    "formatter": "json",
                    "filename": "tiktrue_database.log",
                    "maxBytes": 52428800,
                    "backupCount": 5
                }
            },
            "formatters": {
                "standard": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S"
                },
                "json": {
                    "class": "scripts.monitoring.logging_config.TikTrueFormatter",
                    "include_context": True
                }
            },
            "features": {
                "async_logging": True,
                "performance_logging": True,
                "security_logging": True,
                "structured_logging": True
            }
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # Merge with default config
                    default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Failed to load config file {config_file}: {e}", file=sys.stderr)
                
        return default_config
        
    def setup_logging(self) -> Dict[str, logging.Logger]:
        """Setup centralized logging configuration"""
        # Create log directory
        log_dir = self.project_root / self.config["log_directory"]
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup formatters
        formatters = {}
        for name, formatter_config in self.config["formatters"].items():
            if formatter_config.get("class") == "scripts.monitoring.logging_config.TikTrueFormatter":
                formatters[name] = TikTrueFormatter(
                    include_context=formatter_config.get("include_context", True)
                )
            else:
                formatters[name] = logging.Formatter(
                    fmt=formatter_config.get("format"),
                    datefmt=formatter_config.get("datefmt")
                )
                
        # Setup handlers
        handlers = {}
        for name, handler_config in self.config["handlers"].items():
            handler_class = handler_config["class"]
            
            if handler_class == "logging.StreamHandler":
                handler = logging.StreamHandler(sys.stdout)
            elif handler_class == "logging.handlers.RotatingFileHandler":
                filename = log_dir / handler_config["filename"]
                handler = logging.handlers.RotatingFileHandler(
                    filename=filename,
                    maxBytes=handler_config.get("maxBytes", 52428800),
                    backupCount=handler_config.get("backupCount", 5),
                    encoding='utf-8'
                )
            else:
                continue  # Skip unknown handler types
                
            # Set handler level and formatter
            handler.setLevel(getattr(logging, handler_config["level"]))
            formatter_name = handler_config.get("formatter", "standard")
            if formatter_name in formatters:
                handler.setFormatter(formatters[formatter_name])
                
            # Wrap with async handler if enabled
            if self.config["features"]["async_logging"]:
                handler = AsyncLogHandler(handler)
                
            handlers[name] = handler
            
        # Setup loggers
        for logger_name, logger_config in self.config["loggers"].items():
            logger = logging.getLogger(logger_name)
            logger.setLevel(getattr(logging, logger_config["level"]))
            
            # Clear existing handlers
            logger.handlers.clear()
            
            # Add configured handlers
            for handler_name in logger_config.get("handlers", []):
                if handler_name in handlers:
                    logger.addHandler(handlers[handler_name])
                    
            # Set propagation
            logger.propagate = logger_config.get("propagate", False)
            
            self.loggers[logger_name] = logger
            
        return self.loggers
        
    def get_logger(self, name: str) -> logging.Logger:
        """Get configured logger by name"""
        if name not in self.loggers:
            # Create logger with default configuration
            logger = logging.getLogger(name)
            logger.setLevel(logging.INFO)
            
            # Add default handler if no handlers exist
            if not logger.handlers:
                handler = logging.StreamHandler(sys.stdout)
                handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
                logger.addHandler(handler)
                
            self.loggers[name] = logger
            
        return self.loggers[name]
        
    def get_performance_logger(self, name: str = "tiktrue.performance") -> PerformanceLogger:
        """Get performance logger instance"""
        logger = self.get_logger(name)
        return PerformanceLogger(logger)
        
    def get_security_logger(self, name: str = "tiktrue.security") -> SecurityLogger:
        """Get security logger instance"""
        logger = self.get_logger(name)
        return SecurityLogger(logger)
        
    def cleanup_old_logs(self):
        """Clean up old log files based on retention policy"""
        log_dir = self.project_root / self.config["log_directory"]
        retention_days = self.config["retention_days"]
        
        if not log_dir.exists():
            return
            
        cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
        
        for log_file in log_dir.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    print(f"Deleted old log file: {log_file}")
            except Exception as e:
                print(f"Failed to delete log file {log_file}: {e}", file=sys.stderr)
                
    def generate_logging_report(self) -> Dict[str, Any]:
        """Generate logging system report"""
        log_dir = self.project_root / self.config["log_directory"]
        
        log_files = []
        total_size = 0
        
        if log_dir.exists():
            for log_file in log_dir.glob("*.log*"):
                try:
                    stat = log_file.stat()
                    log_files.append({
                        "name": log_file.name,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    total_size += stat.st_size
                except Exception:
                    continue
                    
        report = {
            "logging_config": {
                "log_directory": str(log_dir),
                "retention_days": self.config["retention_days"],
                "max_file_size_mb": self.config["max_file_size_mb"],
                "backup_count": self.config["backup_count"]
            },
            "log_files": {
                "count": len(log_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "files": log_files
            },
            "loggers": {
                "configured_count": len(self.loggers),
                "logger_names": list(self.loggers.keys())
            },
            "features": self.config["features"],
            "report_timestamp": datetime.now().isoformat()
        }
        
        return report

# Global logging configuration instance
_logging_config = None

def get_logging_config(config_file: Optional[str] = None) -> TikTrueLoggingConfig:
    """Get global logging configuration instance"""
    global _logging_config
    
    if _logging_config is None:
        _logging_config = TikTrueLoggingConfig(config_file)
        _logging_config.setup_logging()
        
    return _logging_config

def get_logger(name: str) -> logging.Logger:
    """Get configured logger by name"""
    config = get_logging_config()
    return config.get_logger(name)

def get_performance_logger(name: str = "tiktrue.performance") -> PerformanceLogger:
    """Get performance logger instance"""
    config = get_logging_config()
    return config.get_performance_logger(name)

def get_security_logger(name: str = "tiktrue.security") -> SecurityLogger:
    """Get security logger instance"""
    config = get_logging_config()
    return config.get_security_logger(name)

def main():
    """Main entry point for logging configuration testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTrue Logging Configuration")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--test", action="store_true", help="Run logging tests")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old log files")
    parser.add_argument("--report", action="store_true", help="Generate logging report")
    
    args = parser.parse_args()
    
    # Initialize logging configuration
    logging_config = TikTrueLoggingConfig(args.config)
    logging_config.setup_logging()
    
    if args.cleanup:
        print("Cleaning up old log files...")
        logging_config.cleanup_old_logs()
        print("Cleanup completed.")
        
    if args.report:
        print("Generating logging report...")
        report = logging_config.generate_logging_report()
        print(json.dumps(report, indent=2))
        
    if args.test:
        print("Running logging tests...")
        
        # Test basic logging
        logger = logging_config.get_logger("tiktrue.test")
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")
        
        # Test performance logging
        perf_logger = logging_config.get_performance_logger()
        perf_logger.log_request("GET", "/api/v1/test", 150.5, 200, "user123")
        perf_logger.log_database_query("SELECT", "users", 25.3, 1)
        perf_logger.log_model_inference("llama3_8b", 100, 50, 1200.0)
        
        # Test security logging
        sec_logger = logging_config.get_security_logger()
        sec_logger.log_authentication("user123", True, "192.168.1.100", "Mozilla/5.0")
        sec_logger.log_authorization("user123", "/api/v1/models", "download", True)
        sec_logger.log_suspicious_activity("user456", "multiple_failed_logins", 
                                          {"attempts": 5, "ip": "192.168.1.200"}, "HIGH")
        
        print("Logging tests completed.")

if __name__ == "__main__":
    main()