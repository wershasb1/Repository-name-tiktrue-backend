"""
Comprehensive Error Handling and Logging System for TikTrue Distributed LLM Platform

This module implements structured JSON logging, error classification, recovery strategies,
and user-friendly error messages as specified in requirements 10.4, 6.5.1-6.5.5.

Features:
- Structured JSON logging for all components
- Error classification and recovery strategies
- User-friendly error messages and notifications
- Security event logging and monitoring
- Error aggregation and analysis
- Automatic error reporting and alerting

Classes:
    ErrorSeverity: Enum for error severity levels
    ErrorCategory: Enum for error categories
    ErrorCode: Enum for standardized error codes
    ErrorContext: Data class for error context information
    StructuredLogger: Enhanced logger with JSON formatting
    ErrorHandler: Main error handling and recovery system
"""

import json
import logging
import logging.handlers
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import threading
import queue
import time
import hashlib

# Setup base logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ErrorHandling")


class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SECURITY = "security"


class ErrorCategory(Enum):
    """Error category classifications"""
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    ENCRYPTION = "encryption"
    LICENSE = "license"
    MODEL_LOADING = "model_loading"
    INFERENCE = "inference"
    STORAGE = "storage"
    CONFIGURATION = "configuration"
    SYSTEM_RESOURCE = "system_resource"
    PROTOCOL = "protocol"
    VALIDATION = "validation"
    HARDWARE = "hardware"
    SERVICE = "service"
    USER_INPUT = "user_input"


class ErrorCode(Enum):
    """Standardized error codes"""
    # Network errors (1000-1099)
    NETWORK_CONNECTION_FAILED = 1001
    NETWORK_TIMEOUT = 1002
    NETWORK_UNREACHABLE = 1003
    NETWORK_PROTOCOL_ERROR = 1004
    NETWORK_DNS_RESOLUTION_FAILED = 1005
    
    # Authentication errors (1100-1199)
    AUTH_INVALID_CREDENTIALS = 1101
    AUTH_TOKEN_EXPIRED = 1102
    AUTH_TOKEN_INVALID = 1103
    AUTH_PERMISSION_DENIED = 1104
    AUTH_ACCOUNT_LOCKED = 1105
    
    # License errors (1200-1299)
    LICENSE_EXPIRED = 1201
    LICENSE_INVALID = 1202
    LICENSE_HARDWARE_MISMATCH = 1203
    LICENSE_QUOTA_EXCEEDED = 1204
    LICENSE_MODEL_ACCESS_DENIED = 1205
    
    # Encryption errors (1300-1399)
    ENCRYPTION_KEY_GENERATION_FAILED = 1301
    ENCRYPTION_DECRYPTION_FAILED = 1302
    ENCRYPTION_KEY_NOT_FOUND = 1303
    ENCRYPTION_INTEGRITY_CHECK_FAILED = 1304
    ENCRYPTION_HARDWARE_BINDING_FAILED = 1305
    
    # Model errors (1400-1499)
    MODEL_NOT_FOUND = 1401
    MODEL_LOADING_FAILED = 1402
    MODEL_CORRUPTION_DETECTED = 1403
    MODEL_INCOMPATIBLE_VERSION = 1404
    MODEL_INSUFFICIENT_MEMORY = 1405
    
    # Inference errors (1500-1599)
    INFERENCE_REQUEST_INVALID = 1501
    INFERENCE_PROCESSING_FAILED = 1502
    INFERENCE_TIMEOUT = 1503
    INFERENCE_RESOURCE_EXHAUSTED = 1504
    INFERENCE_MODEL_UNAVAILABLE = 1505
    
    # Storage errors (1600-1699)
    STORAGE_FILE_NOT_FOUND = 1601
    STORAGE_PERMISSION_DENIED = 1602
    STORAGE_DISK_FULL = 1603
    STORAGE_CORRUPTION_DETECTED = 1604
    STORAGE_IO_ERROR = 1605
    
    # Configuration errors (1700-1799)
    CONFIG_FILE_NOT_FOUND = 1701
    CONFIG_INVALID_FORMAT = 1702
    CONFIG_VALIDATION_FAILED = 1703
    CONFIG_MISSING_REQUIRED_FIELD = 1704
    CONFIG_VALUE_OUT_OF_RANGE = 1705
    
    # System resource errors (1800-1899)
    SYSTEM_OUT_OF_MEMORY = 1801
    SYSTEM_CPU_OVERLOAD = 1802
    SYSTEM_GPU_UNAVAILABLE = 1803
    SYSTEM_DISK_SPACE_LOW = 1804
    SYSTEM_PROCESS_LIMIT_REACHED = 1805
    
    # Generic errors (9000-9999)
    UNKNOWN_ERROR = 9000
    INTERNAL_ERROR = 9001
    VALIDATION_ERROR = 9002
    TIMEOUT_ERROR = 9003
    CANCELLED_ERROR = 9004


@dataclass
class ErrorContext:
    """Error context information"""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    error_code: ErrorCode
    message: str
    component: str
    function_name: str
    line_number: int
    user_message: str
    technical_details: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    hardware_fingerprint: Optional[str] = None
    license_hash: Optional[str] = None
    recovery_suggestions: List[str] = field(default_factory=list)
    related_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['severity'] = self.severity.value
        data['category'] = self.category.value
        data['error_code'] = self.error_code.value
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str, indent=2)


class StructuredLogger:
    """Enhanced logger with structured JSON formatting"""
    
    def __init__(self, name: str, log_dir: str = "logs", max_file_size: int = 10*1024*1024):
        """
        Initialize structured logger
        
        Args:
            name: Logger name
            log_dir: Directory for log files
            max_file_size: Maximum log file size in bytes
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create rotating file handler for JSON logs
        json_log_file = self.log_dir / f"{name}.json.log"
        json_handler = logging.handlers.RotatingFileHandler(
            json_log_file,
            maxBytes=max_file_size,
            backupCount=5
        )
        json_handler.setFormatter(self._create_json_formatter())
        json_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(json_handler)
        
        # Create rotating file handler for human-readable logs
        text_log_file = self.log_dir / f"{name}.log"
        text_handler = logging.handlers.RotatingFileHandler(
            text_log_file,
            maxBytes=max_file_size,
            backupCount=5
        )
        text_handler.setFormatter(self._create_text_formatter())
        text_handler.setLevel(logging.INFO)
        self.logger.addHandler(text_handler)
        
        # Create console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self._create_console_formatter())
        console_handler.setLevel(logging.WARNING)
        self.logger.addHandler(console_handler)
    
    def _create_json_formatter(self):
        """Create JSON formatter"""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno,
                    'thread': record.thread,
                    'process': record.process
                }
                
                # Add exception info if present
                if record.exc_info:
                    log_entry['exception'] = self.formatException(record.exc_info)
                
                # Add extra fields
                for key, value in record.__dict__.items():
                    if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                                  'filename', 'module', 'lineno', 'funcName', 'created',
                                  'msecs', 'relativeCreated', 'thread', 'threadName',
                                  'processName', 'process', 'exc_info', 'exc_text', 'stack_info']:
                        log_entry[key] = value
                
                return json.dumps(log_entry, default=str)
        
        return JSONFormatter()
    
    def _create_text_formatter(self):
        """Create human-readable text formatter"""
        return logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
    
    def _create_console_formatter(self):
        """Create console formatter"""
        return logging.Formatter('%(levelname)s - %(name)s - %(message)s')
    
    def log_error_context(self, error_context: ErrorContext):
        """Log error context with structured data"""
        extra_data = {
            'error_id': error_context.error_id,
            'error_code': error_context.error_code.value,
            'category': error_context.category.value,
            'component': error_context.component,
            'user_id': error_context.user_id,
            'session_id': error_context.session_id,
            'request_id': error_context.request_id,
            'technical_details': error_context.technical_details,
            'recovery_suggestions': error_context.recovery_suggestions
        }
        
        # Log based on severity
        if error_context.severity == ErrorSeverity.DEBUG:
            self.logger.debug(error_context.message, extra=extra_data)
        elif error_context.severity == ErrorSeverity.INFO:
            self.logger.info(error_context.message, extra=extra_data)
        elif error_context.severity == ErrorSeverity.WARNING:
            self.logger.warning(error_context.message, extra=extra_data)
        elif error_context.severity == ErrorSeverity.ERROR:
            self.logger.error(error_context.message, extra=extra_data)
        elif error_context.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.SECURITY]:
            self.logger.critical(error_context.message, extra=extra_data)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(message, extra=kwargs)


class ErrorHandler:
    """
    Comprehensive error handling and recovery system
    Implements requirements 10.4, 6.5.1-6.5.5
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize error handler
        
        Args:
            log_dir: Directory for log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create structured loggers for different components
        self.loggers = {
            'main': StructuredLogger('main', log_dir),
            'network': StructuredLogger('network', log_dir),
            'security': StructuredLogger('security', log_dir),
            'model': StructuredLogger('model', log_dir),
            'inference': StructuredLogger('inference', log_dir),
            'license': StructuredLogger('license', log_dir),
            'storage': StructuredLogger('storage', log_dir),
            'system': StructuredLogger('system', log_dir)
        }
        
        # Error tracking
        self.error_history: List[ErrorContext] = []
        self.error_counts: Dict[str, int] = {}
        self.error_patterns: Dict[str, List[datetime]] = {}
        
        # Recovery strategies
        self.recovery_strategies: Dict[ErrorCode, Callable] = {}
        self.error_callbacks: Dict[ErrorSeverity, List[Callable]] = {
            severity: [] for severity in ErrorSeverity
        }
        
        # User message templates
        self.user_message_templates = self._initialize_user_messages()
        
        # Statistics
        self.stats = {
            'total_errors': 0,
            'errors_by_severity': {severity.value: 0 for severity in ErrorSeverity},
            'errors_by_category': {category.value: 0 for category in ErrorCategory},
            'errors_by_code': {},
            'recovery_attempts': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0
        }
        
        # Background processing
        self.processing_queue = queue.Queue()
        self.processing_thread = threading.Thread(target=self._process_errors, daemon=True)
        self.processing_thread.start()
        
        logger.info("ErrorHandler initialized")
    
    def handle_error(self,
                    error_code: ErrorCode,
                    message: str,
                    component: str,
                    severity: ErrorSeverity = ErrorSeverity.ERROR,
                    category: Optional[ErrorCategory] = None,
                    exception: Optional[Exception] = None,
                    user_id: Optional[str] = None,
                    session_id: Optional[str] = None,
                    request_id: Optional[str] = None,
                    technical_details: Optional[Dict[str, Any]] = None,
                    auto_recover: bool = True) -> ErrorContext:
        """
        Handle an error with comprehensive logging and recovery
        
        Args:
            error_code: Standardized error code
            message: Technical error message
            component: Component where error occurred
            severity: Error severity level
            category: Error category (auto-detected if not provided)
            exception: Exception object if available
            user_id: User identifier
            session_id: Session identifier
            request_id: Request identifier
            technical_details: Additional technical details
            auto_recover: Whether to attempt automatic recovery
            
        Returns:
            ErrorContext object
        """
        try:
            # Generate unique error ID
            error_id = f"err_{uuid.uuid4().hex[:8]}"
            
            # Auto-detect category if not provided
            if category is None:
                category = self._detect_error_category(error_code)
            
            # Get caller information
            import inspect
            frame = inspect.currentframe().f_back
            function_name = frame.f_code.co_name
            line_number = frame.f_lineno
            
            # Create error context
            error_context = ErrorContext(
                error_id=error_id,
                timestamp=datetime.now(),
                severity=severity,
                category=category,
                error_code=error_code,
                message=message,
                component=component,
                function_name=function_name,
                line_number=line_number,
                user_message=self._generate_user_message(error_code, message),
                technical_details=technical_details or {},
                user_id=user_id,
                session_id=session_id,
                request_id=request_id
            )
            
            # Add exception information
            if exception:
                error_context.stack_trace = traceback.format_exc()
                error_context.technical_details['exception_type'] = type(exception).__name__
                error_context.technical_details['exception_message'] = str(exception)
            
            # Add recovery suggestions
            error_context.recovery_suggestions = self._get_recovery_suggestions(error_code)
            
            # Queue for background processing
            self.processing_queue.put(('handle_error', error_context, auto_recover))
            
            return error_context
            
        except Exception as e:
            # Fallback error handling
            fallback_logger = logging.getLogger('error_handler_fallback')
            fallback_logger.critical(f"Error in error handler: {e}")
            
            # Create minimal error context
            return ErrorContext(
                error_id=f"fallback_{int(time.time())}",
                timestamp=datetime.now(),
                severity=ErrorSeverity.CRITICAL,
                category=ErrorCategory.SYSTEM_RESOURCE,
                error_code=ErrorCode.INTERNAL_ERROR,
                message=f"Error handler failure: {e}",
                component="error_handler",
                function_name="handle_error",
                line_number=0,
                user_message="An internal error occurred. Please contact support."
            )
    
    def log_security_event(self,
                          event_type: str,
                          message: str,
                          component: str,
                          severity: ErrorSeverity = ErrorSeverity.SECURITY,
                          user_id: Optional[str] = None,
                          hardware_fingerprint: Optional[str] = None,
                          license_hash: Optional[str] = None,
                          details: Optional[Dict[str, Any]] = None) -> ErrorContext:
        """
        Log security-related events with enhanced tracking
        Implements requirement 6.5.1-6.5.5 for security event logging
        
        Args:
            event_type: Type of security event
            message: Security event message
            component: Component where event occurred
            severity: Event severity
            user_id: User identifier
            hardware_fingerprint: Hardware fingerprint
            license_hash: Hashed license key
            details: Additional event details
            
        Returns:
            ErrorContext object
        """
        # Determine appropriate error code based on event type
        error_code_map = {
            'license_violation': ErrorCode.LICENSE_INVALID,
            'decryption_failure': ErrorCode.ENCRYPTION_DECRYPTION_FAILED,
            'hardware_mismatch': ErrorCode.LICENSE_HARDWARE_MISMATCH,
            'unauthorized_access': ErrorCode.AUTH_PERMISSION_DENIED,
            'integrity_violation': ErrorCode.ENCRYPTION_INTEGRITY_CHECK_FAILED
        }
        
        error_code = error_code_map.get(event_type, ErrorCode.UNKNOWN_ERROR)
        
        # Create enhanced technical details
        technical_details = details or {}
        technical_details.update({
            'event_type': event_type,
            'hardware_fingerprint': hardware_fingerprint,
            'license_hash': license_hash,
            'security_context': True
        })
        
        return self.handle_error(
            error_code=error_code,
            message=message,
            component=component,
            severity=severity,
            category=ErrorCategory.AUTHENTICATION if 'auth' in event_type else ErrorCategory.ENCRYPTION,
            user_id=user_id,
            technical_details=technical_details,
            auto_recover=False  # Security events typically don't auto-recover
        )
    
    def register_recovery_strategy(self, error_code: ErrorCode, strategy: Callable):
        """Register a recovery strategy for a specific error code"""
        self.recovery_strategies[error_code] = strategy
        logger.info(f"Recovery strategy registered for error code: {error_code.value}")
    
    def register_error_callback(self, severity: ErrorSeverity, callback: Callable):
        """Register a callback for specific error severity"""
        self.error_callbacks[severity].append(callback)
        logger.info(f"Error callback registered for severity: {severity.value}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics"""
        stats = self.stats.copy()
        
        # Add recent error patterns
        recent_errors = [e for e in self.error_history if 
                        (datetime.now() - e.timestamp).total_seconds() < 3600]  # Last hour
        
        stats['recent_errors_count'] = len(recent_errors)
        stats['error_rate_per_hour'] = len(recent_errors)
        
        # Top error codes
        error_code_counts = {}
        for error in recent_errors:
            code = error.error_code.value
            error_code_counts[code] = error_code_counts.get(code, 0) + 1
        
        stats['top_error_codes'] = sorted(error_code_counts.items(), 
                                        key=lambda x: x[1], reverse=True)[:10]
        
        return stats
    
    def get_recent_errors(self, limit: int = 50, 
                         severity: Optional[ErrorSeverity] = None,
                         category: Optional[ErrorCategory] = None) -> List[ErrorContext]:
        """Get recent errors with optional filtering"""
        filtered_errors = self.error_history
        
        if severity:
            filtered_errors = [e for e in filtered_errors if e.severity == severity]
        
        if category:
            filtered_errors = [e for e in filtered_errors if e.category == category]
        
        return sorted(filtered_errors, key=lambda e: e.timestamp, reverse=True)[:limit]
    
    def _process_errors(self):
        """Background error processing thread"""
        while True:
            try:
                item = self.processing_queue.get(timeout=1.0)
                if item is None:  # Shutdown signal
                    break
                
                action, error_context, auto_recover = item
                
                if action == 'handle_error':
                    self._process_error_context(error_context, auto_recover)
                
                self.processing_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in background processing: {e}")
    
    def _process_error_context(self, error_context: ErrorContext, auto_recover: bool):
        """Process error context in background thread"""
        try:
            # Update statistics
            self.stats['total_errors'] += 1
            self.stats['errors_by_severity'][error_context.severity.value] += 1
            self.stats['errors_by_category'][error_context.category.value] += 1
            
            code_key = str(error_context.error_code.value)
            self.stats['errors_by_code'][code_key] = self.stats['errors_by_code'].get(code_key, 0) + 1
            
            # Add to history
            self.error_history.append(error_context)
            
            # Limit history size
            if len(self.error_history) > 10000:
                self.error_history = self.error_history[-5000:]  # Keep last 5000
            
            # Track error patterns
            error_key = f"{error_context.component}:{error_context.error_code.value}"
            if error_key not in self.error_patterns:
                self.error_patterns[error_key] = []
            
            self.error_patterns[error_key].append(error_context.timestamp)
            
            # Clean old patterns (keep last 24 hours)
            cutoff = datetime.now() - timedelta(hours=24)
            self.error_patterns[error_key] = [
                ts for ts in self.error_patterns[error_key] if ts > cutoff
            ]
            
            # Log the error
            component_logger = self.loggers.get(
                error_context.category.value, 
                self.loggers['main']
            )
            component_logger.log_error_context(error_context)
            
            # Trigger callbacks
            for callback in self.error_callbacks.get(error_context.severity, []):
                try:
                    callback(error_context)
                except Exception as e:
                    logger.error(f"Error callback failed: {e}")
            
            # Attempt recovery if enabled
            if auto_recover and error_context.error_code in self.recovery_strategies:
                self._attempt_recovery(error_context)
            
        except Exception as e:
            logger.error(f"Error processing error context: {e}")
    
    def _attempt_recovery(self, error_context: ErrorContext):
        """Attempt automatic recovery for an error"""
        try:
            self.stats['recovery_attempts'] += 1
            
            recovery_strategy = self.recovery_strategies[error_context.error_code]
            
            # Execute recovery strategy
            success = recovery_strategy(error_context)
            
            if success:
                self.stats['successful_recoveries'] += 1
                logger.info(f"Recovery successful for error: {error_context.error_id}")
            else:
                self.stats['failed_recoveries'] += 1
                logger.warning(f"Recovery failed for error: {error_context.error_id}")
            
        except Exception as e:
            self.stats['failed_recoveries'] += 1
            logger.error(f"Recovery attempt failed for error {error_context.error_id}: {e}")
    
    def _detect_error_category(self, error_code: ErrorCode) -> ErrorCategory:
        """Auto-detect error category based on error code"""
        code_value = error_code.value
        
        if 1000 <= code_value < 1100:
            return ErrorCategory.NETWORK
        elif 1100 <= code_value < 1200:
            return ErrorCategory.AUTHENTICATION
        elif 1200 <= code_value < 1300:
            return ErrorCategory.LICENSE
        elif 1300 <= code_value < 1400:
            return ErrorCategory.ENCRYPTION
        elif 1400 <= code_value < 1500:
            return ErrorCategory.MODEL_LOADING
        elif 1500 <= code_value < 1600:
            return ErrorCategory.INFERENCE
        elif 1600 <= code_value < 1700:
            return ErrorCategory.STORAGE
        elif 1700 <= code_value < 1800:
            return ErrorCategory.CONFIGURATION
        elif 1800 <= code_value < 1900:
            return ErrorCategory.SYSTEM_RESOURCE
        else:
            return ErrorCategory.SERVICE
    
    def _generate_user_message(self, error_code: ErrorCode, technical_message: str) -> str:
        """Generate user-friendly error message"""
        template = self.user_message_templates.get(error_code)
        if template:
            return template
        
        # Fallback to generic message based on category
        category = self._detect_error_category(error_code)
        generic_messages = {
            ErrorCategory.NETWORK: "Network connection issue. Please check your internet connection and try again.",
            ErrorCategory.AUTHENTICATION: "Authentication failed. Please check your credentials and try again.",
            ErrorCategory.LICENSE: "License validation issue. Please check your subscription status.",
            ErrorCategory.ENCRYPTION: "Security validation failed. Please contact support if this persists.",
            ErrorCategory.MODEL_LOADING: "Model loading issue. Please try again or contact support.",
            ErrorCategory.INFERENCE: "Processing request failed. Please try again with different parameters.",
            ErrorCategory.STORAGE: "File access issue. Please check file permissions and available disk space.",
            ErrorCategory.CONFIGURATION: "Configuration issue. Please check your settings and try again.",
            ErrorCategory.SYSTEM_RESOURCE: "System resource issue. Please close other applications and try again."
        }
        
        return generic_messages.get(category, "An unexpected error occurred. Please try again or contact support.")
    
    def _get_recovery_suggestions(self, error_code: ErrorCode) -> List[str]:
        """Get recovery suggestions for an error code"""
        suggestions_map = {
            ErrorCode.NETWORK_CONNECTION_FAILED: [
                "Check your internet connection",
                "Verify firewall settings",
                "Try connecting to a different network",
                "Contact your network administrator"
            ],
            ErrorCode.LICENSE_EXPIRED: [
                "Renew your subscription",
                "Contact support for license assistance",
                "Check your account status online"
            ],
            ErrorCode.MODEL_LOADING_FAILED: [
                "Restart the application",
                "Check available disk space",
                "Verify model file integrity",
                "Re-download the model if necessary"
            ],
            ErrorCode.SYSTEM_OUT_OF_MEMORY: [
                "Close other applications",
                "Restart the application",
                "Reduce batch size or model parameters",
                "Add more RAM to your system"
            ]
        }
        
        return suggestions_map.get(error_code, ["Try again", "Contact support if the issue persists"])
    
    def _initialize_user_messages(self) -> Dict[ErrorCode, str]:
        """Initialize user-friendly error message templates"""
        return {
            ErrorCode.NETWORK_CONNECTION_FAILED: "Unable to connect to the server. Please check your internet connection.",
            ErrorCode.NETWORK_TIMEOUT: "The connection timed out. Please try again.",
            ErrorCode.AUTH_INVALID_CREDENTIALS: "Invalid username or password. Please try again.",
            ErrorCode.AUTH_TOKEN_EXPIRED: "Your session has expired. Please log in again.",
            ErrorCode.LICENSE_EXPIRED: "Your license has expired. Please renew your subscription.",
            ErrorCode.LICENSE_INVALID: "Invalid license. Please check your subscription status.",
            ErrorCode.LICENSE_HARDWARE_MISMATCH: "License is not valid for this device. Please contact support.",
            ErrorCode.MODEL_NOT_FOUND: "The requested model is not available. Please try a different model.",
            ErrorCode.MODEL_LOADING_FAILED: "Failed to load the model. Please try again.",
            ErrorCode.INFERENCE_REQUEST_INVALID: "Invalid request parameters. Please check your input.",
            ErrorCode.INFERENCE_PROCESSING_FAILED: "Failed to process your request. Please try again.",
            ErrorCode.STORAGE_FILE_NOT_FOUND: "Required file not found. Please reinstall the application.",
            ErrorCode.STORAGE_DISK_FULL: "Insufficient disk space. Please free up space and try again.",
            ErrorCode.CONFIG_FILE_NOT_FOUND: "Configuration file missing. Please reinstall the application.",
            ErrorCode.SYSTEM_OUT_OF_MEMORY: "Insufficient memory. Please close other applications and try again."
        }


# Global error handler instance
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get global error handler instance"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def handle_error(error_code: ErrorCode, message: str, component: str, **kwargs) -> ErrorContext:
    """Convenience function for error handling"""
    return get_error_handler().handle_error(error_code, message, component, **kwargs)


def log_security_event(event_type: str, message: str, component: str, **kwargs) -> ErrorContext:
    """Convenience function for security event logging"""
    return get_error_handler().log_security_event(event_type, message, component, **kwargs)


if __name__ == "__main__":
    # Example usage and testing
    def test_error_handling():
        """Test error handling functionality"""
        print("Testing Error Handling System...")
        
        # Create error handler
        error_handler = ErrorHandler()
        
        # Test various error scenarios
        error_handler.handle_error(
            ErrorCode.NETWORK_CONNECTION_FAILED,
            "Connection to server failed",
            "network_client",
            severity=ErrorSeverity.ERROR,
            user_id="test_user",
            session_id="test_session"
        )
        
        error_handler.log_security_event(
            "license_violation",
            "Invalid license detected",
            "license_validator",
            user_id="test_user",
            hardware_fingerprint="test_fingerprint"
        )
        
        # Wait for background processing
        time.sleep(2)
        
        # Print statistics
        stats = error_handler.get_error_statistics()
        print(f"Error Statistics: {json.dumps(stats, indent=2, default=str)}")
        
        print("Error Handling test completed")
    
    # Run test
    test_error_handling()