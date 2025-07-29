"""
Protocol Specification for Distributed LLM Platform
Defines standardized message formats, validation, and protocol version management
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Literal
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import re
from pathlib import Path

from license_models import LicenseInfo, SubscriptionTier, ValidationStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProtocolSpec")

# Create logs directory if it doesn't exist
Path('logs').mkdir(exist_ok=True)
file_handler = logging.FileHandler('logs/protocol_spec.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class ProtocolVersion(Enum):
    """Protocol version enumeration"""
    V1_0 = "1.0"
    V1_1 = "1.1"
    V2_0 = "2.0"


class MessageType(Enum):
    """Message type enumeration"""
    INFERENCE_REQUEST = "inference_request"
    INFERENCE_RESPONSE = "inference_response"
    HEARTBEAT = "heartbeat"
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    AUTHENTICATION = "authentication"
    LICENSE_CHECK = "license_check"
    NETWORK_DISCOVERY = "network_discovery"
    WORKER_REGISTRATION = "worker_registration"
    MODEL_SYNC = "model_sync"


class LicenseStatusProtocol(Enum):
    """License status for protocol messages"""
    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    MISSING = "missing"
    SUSPENDED = "suspended"


class ErrorCode(Enum):
    """Standard error codes"""
    SUCCESS = 0
    INVALID_REQUEST = 1001
    AUTHENTICATION_FAILED = 1002
    LICENSE_EXPIRED = 1003
    QUOTA_EXCEEDED = 1004
    MODEL_NOT_FOUND = 1005
    WORKER_UNAVAILABLE = 1006
    NETWORK_ERROR = 1007
    INTERNAL_ERROR = 1008
    VALIDATION_ERROR = 1009
    PERMISSION_DENIED = 1010

@dataclass

class MessageHeader:
    """Standard message header for all protocol messages"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.INFERENCE_REQUEST
    protocol_version: ProtocolVersion = ProtocolVersion.V2_0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sender_id: Optional[str] = None
    recipient_id: Optional[str] = None
    correlation_id: Optional[str] = None
    license_hash: Optional[str] = None
    license_status: LicenseStatusProtocol = LicenseStatusProtocol.MISSING
    session_id: Optional[str] = None


@dataclass
class InferenceRequest:
    """Standardized inference request message"""
    header: MessageHeader
    model_id: str
    prompt: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    max_tokens: int = 100
    temperature: float = 0.7
    top_p: float = 0.9
    stop_sequences: List[str] = field(default_factory=list)
    stream: bool = False
    context_window: int = 2048
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate request after initialization"""
        if not self.model_id:
            raise ValueError("model_id is required")
        if not self.prompt:
            raise ValueError("prompt is required")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError("top_p must be between 0.0 and 1.0")


@dataclass
class InferenceResponse:
    """Standardized inference response message"""
    header: MessageHeader
    request_id: str
    model_id: str
    generated_text: str = ""
    finish_reason: Literal["stop", "length", "error"] = "stop"
    usage: Dict[str, int] = field(default_factory=lambda: {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    })
    processing_time_ms: int = 0
    worker_id: Optional[str] = None
    error_code: ErrorCode = ErrorCode.SUCCESS
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate response after initialization"""
        if not self.request_id:
            raise ValueError("request_id is required")
        if not self.model_id:
            raise ValueError("model_id is required")
        if self.processing_time_ms < 0:
            raise ValueError("processing_time_ms must be non-negative")


@dataclass
class HeartbeatMessage:
    """Heartbeat message for worker health monitoring"""
    header: MessageHeader
    worker_id: str
    status: Literal["healthy", "busy", "error", "offline"] = "healthy"
    load_percentage: float = 0.0
    available_memory_mb: int = 0
    active_sessions: int = 0
    models_loaded: List[str] = field(default_factory=list)
    last_activity: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorMessage:
    """Standard error message"""
    header: MessageHeader
    error_code: ErrorCode
    error_message: str
    details: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    recovery_suggestions: List[str] = field(default_factory=list)

class ProtocolValidator:
    """Protocol message validator"""
    
    def __init__(self, supported_versions: List[ProtocolVersion] = None):
        """
        Initialize protocol validator
        
        Args:
            supported_versions: List of supported protocol versions
        """
        self.supported_versions = supported_versions or [ProtocolVersion.V2_0, ProtocolVersion.V1_1]
        self.validation_stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "error_counts": {}
        }
        
        logger.info(f"Protocol validator initialized with versions: {[v.value for v in self.supported_versions]}")
    
    def validate_message(self, message: Union[Dict[str, Any], str]) -> tuple[bool, Optional[str]]:
        """
        Validate a protocol message
        
        Args:
            message: Message to validate (dict or JSON string)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.validation_stats["total_validations"] += 1
            
            # Parse JSON if string
            if isinstance(message, str):
                try:
                    message = json.loads(message)
                except json.JSONDecodeError as e:
                    error = f"Invalid JSON format: {e}"
                    self._record_validation_error("json_parse_error")
                    return False, error
            
            # Validate message structure
            if not isinstance(message, dict):
                error = "Message must be a dictionary"
                self._record_validation_error("invalid_structure")
                return False, error
            
            # Validate header
            if "header" not in message:
                error = "Message header is required"
                self._record_validation_error("missing_header")
                return False, error
            
            header = message["header"]
            header_valid, header_error = self._validate_header(header)
            if not header_valid:
                self._record_validation_error("invalid_header")
                return False, f"Header validation failed: {header_error}"
            
            # Validate message type specific fields
            message_type = header.get("message_type")
            type_valid, type_error = self._validate_message_type(message, message_type)
            if not type_valid:
                self._record_validation_error(f"invalid_{message_type}")
                return False, f"Message type validation failed: {type_error}"
            
            # Validate license information
            license_valid, license_error = self._validate_license_info(header)
            if not license_valid:
                self._record_validation_error("invalid_license")
                return False, f"License validation failed: {license_error}"
            
            self.validation_stats["successful_validations"] += 1
            return True, None
            
        except Exception as e:
            error = f"Validation error: {str(e)}"
            self._record_validation_error("validation_exception")
            logger.error(f"Message validation failed: {e}")
            return False, error
    
    def _validate_header(self, header: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate message header"""
        required_fields = ["message_id", "message_type", "protocol_version", "timestamp"]
        
        for field in required_fields:
            if field not in header:
                return False, f"Required header field missing: {field}"
        
        # Validate protocol version
        try:
            version = ProtocolVersion(header["protocol_version"])
            if version not in self.supported_versions:
                return False, f"Unsupported protocol version: {header['protocol_version']}"
        except ValueError:
            return False, f"Invalid protocol version: {header['protocol_version']}"
        
        # Validate message type
        try:
            MessageType(header["message_type"])
        except ValueError:
            return False, f"Invalid message type: {header['message_type']}"
        
        # Validate message ID format (UUID)
        message_id = header["message_id"]
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', message_id, re.IGNORECASE):
            return False, f"Invalid message ID format: {message_id}"
        
        # Validate timestamp format (ISO 8601)
        timestamp = header["timestamp"]
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return False, f"Invalid timestamp format: {timestamp}"
        
        return True, None
    
    def _validate_message_type(self, message: Dict[str, Any], message_type: str) -> tuple[bool, Optional[str]]:
        """Validate message type specific fields"""
        try:
            if message_type == MessageType.INFERENCE_REQUEST.value:
                return self._validate_inference_request(message)
            elif message_type == MessageType.INFERENCE_RESPONSE.value:
                return self._validate_inference_response(message)
            elif message_type == MessageType.HEARTBEAT.value:
                return self._validate_heartbeat(message)
            elif message_type == MessageType.ERROR.value:
                return self._validate_error_message(message)
            else:
                # For other message types, basic validation is sufficient
                return True, None
                
        except Exception as e:
            return False, str(e)
    
    def _validate_inference_request(self, message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate inference request message"""
        required_fields = ["model_id", "prompt"]
        
        for field in required_fields:
            if field not in message:
                return False, f"Required field missing: {field}"
        
        # Validate field types and ranges
        if not isinstance(message["model_id"], str) or not message["model_id"]:
            return False, "model_id must be a non-empty string"
        
        if not isinstance(message["prompt"], str) or not message["prompt"]:
            return False, "prompt must be a non-empty string"
        
        # Validate optional parameters
        if "max_tokens" in message:
            if not isinstance(message["max_tokens"], int) or message["max_tokens"] <= 0:
                return False, "max_tokens must be a positive integer"
        
        if "temperature" in message:
            temp = message["temperature"]
            if not isinstance(temp, (int, float)) or not 0.0 <= temp <= 2.0:
                return False, "temperature must be between 0.0 and 2.0"
        
        if "top_p" in message:
            top_p = message["top_p"]
            if not isinstance(top_p, (int, float)) or not 0.0 <= top_p <= 1.0:
                return False, "top_p must be between 0.0 and 1.0"
        
        return True, None
    
    def _validate_inference_response(self, message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate inference response message"""
        required_fields = ["request_id", "model_id"]
        
        for field in required_fields:
            if field not in message:
                return False, f"Required field missing: {field}"
        
        # Validate finish_reason
        if "finish_reason" in message:
            valid_reasons = ["stop", "length", "error"]
            if message["finish_reason"] not in valid_reasons:
                return False, f"finish_reason must be one of: {valid_reasons}"
        
        # Validate usage statistics
        if "usage" in message:
            usage = message["usage"]
            if not isinstance(usage, dict):
                return False, "usage must be a dictionary"
            
            for key in ["prompt_tokens", "completion_tokens", "total_tokens"]:
                if key in usage and (not isinstance(usage[key], int) or usage[key] < 0):
                    return False, f"usage.{key} must be a non-negative integer"
        
        return True, None
    
    def _validate_heartbeat(self, message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate heartbeat message"""
        if "worker_id" not in message:
            return False, "worker_id is required for heartbeat messages"
        
        if "load_percentage" in message:
            load = message["load_percentage"]
            if not isinstance(load, (int, float)) or not 0.0 <= load <= 100.0:
                return False, "load_percentage must be between 0.0 and 100.0"
        
        return True, None
    
    def _validate_error_message(self, message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate error message"""
        required_fields = ["error_code", "error_message"]
        
        for field in required_fields:
            if field not in message:
                return False, f"Required field missing: {field}"
        
        # Validate error code
        try:
            ErrorCode(message["error_code"])
        except (ValueError, TypeError):
            return False, f"Invalid error code: {message['error_code']}"
        
        return True, None
    
    def _validate_license_info(self, header: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate license information in header"""
        # License information is optional but should be valid if present
        if "license_status" in header:
            try:
                LicenseStatusProtocol(header["license_status"])
            except ValueError:
                return False, f"Invalid license status: {header['license_status']}"
        
        return True, None
    
    def _record_validation_error(self, error_type: str):
        """Record validation error for statistics"""
        self.validation_stats["failed_validations"] += 1
        if error_type not in self.validation_stats["error_counts"]:
            self.validation_stats["error_counts"][error_type] = 0
        self.validation_stats["error_counts"][error_type] += 1
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics"""
        total = self.validation_stats["total_validations"]
        success_rate = (self.validation_stats["successful_validations"] / total * 100) if total > 0 else 0
        
        return {
            **self.validation_stats,
            "success_rate_percentage": round(success_rate, 2)
        }
class ProtocolManager:
    """Protocol management and version handling"""
    
    def __init__(self, current_version: ProtocolVersion = ProtocolVersion.V2_0):
        """
        Initialize protocol manager
        
        Args:
            current_version: Current protocol version
        """
        self.current_version = current_version
        self.validator = ProtocolValidator()
        self.message_stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors_encountered": 0
        }
        
        logger.info(f"Protocol manager initialized with version: {current_version.value}")
    
    def create_inference_request(self, 
                               model_id: str,
                               prompt: str,
                               license_info: Optional[LicenseInfo] = None,
                               **kwargs) -> InferenceRequest:
        """
        Create a standardized inference request
        
        Args:
            model_id: Model identifier
            prompt: Input prompt
            license_info: License information
            **kwargs: Additional parameters
            
        Returns:
            InferenceRequest object
        """
        try:
            # Create header with license information
            header = MessageHeader(
                message_type=MessageType.INFERENCE_REQUEST,
                protocol_version=self.current_version,
                license_hash=license_info.license_key[:16] if license_info else None,
                license_status=self._get_license_status(license_info)
            )
            
            # Create request
            request = InferenceRequest(
                header=header,
                model_id=model_id,
                prompt=prompt,
                **kwargs
            )
            
            self.message_stats["messages_sent"] += 1
            logger.debug(f"Created inference request: {request.header.message_id}")
            
            return request
            
        except Exception as e:
            self.message_stats["errors_encountered"] += 1
            logger.error(f"Failed to create inference request: {e}")
            raise
    
    def create_inference_response(self,
                                request_id: str,
                                model_id: str,
                                generated_text: str = "",
                                license_info: Optional[LicenseInfo] = None,
                                **kwargs) -> InferenceResponse:
        """
        Create a standardized inference response
        
        Args:
            request_id: Original request ID
            model_id: Model identifier
            generated_text: Generated response text
            license_info: License information
            **kwargs: Additional parameters
            
        Returns:
            InferenceResponse object
        """
        try:
            # Create header with license information
            header = MessageHeader(
                message_type=MessageType.INFERENCE_RESPONSE,
                protocol_version=self.current_version,
                correlation_id=request_id,
                license_hash=license_info.license_key[:16] if license_info else None,
                license_status=self._get_license_status(license_info)
            )
            
            # Create response
            response = InferenceResponse(
                header=header,
                request_id=request_id,
                model_id=model_id,
                generated_text=generated_text,
                **kwargs
            )
            
            self.message_stats["messages_sent"] += 1
            logger.debug(f"Created inference response: {response.header.message_id}")
            
            return response
            
        except Exception as e:
            self.message_stats["errors_encountered"] += 1
            logger.error(f"Failed to create inference response: {e}")
            raise
    
    def create_heartbeat(self,
                        worker_id: str,
                        license_info: Optional[LicenseInfo] = None,
                        **kwargs) -> HeartbeatMessage:
        """
        Create a heartbeat message
        
        Args:
            worker_id: Worker identifier
            license_info: License information
            **kwargs: Additional parameters
            
        Returns:
            HeartbeatMessage object
        """
        try:
            header = MessageHeader(
                message_type=MessageType.HEARTBEAT,
                protocol_version=self.current_version,
                sender_id=worker_id,
                license_hash=license_info.license_key[:16] if license_info else None,
                license_status=self._get_license_status(license_info)
            )
            
            heartbeat = HeartbeatMessage(
                header=header,
                worker_id=worker_id,
                **kwargs
            )
            
            self.message_stats["messages_sent"] += 1
            return heartbeat
            
        except Exception as e:
            self.message_stats["errors_encountered"] += 1
            logger.error(f"Failed to create heartbeat: {e}")
            raise
    
    def create_error_message(self,
                           error_code: ErrorCode,
                           error_message: str,
                           license_info: Optional[LicenseInfo] = None,
                           **kwargs) -> ErrorMessage:
        """
        Create an error message
        
        Args:
            error_code: Error code
            error_message: Error description
            license_info: License information
            **kwargs: Additional parameters
            
        Returns:
            ErrorMessage object
        """
        try:
            header = MessageHeader(
                message_type=MessageType.ERROR,
                protocol_version=self.current_version,
                license_hash=license_info.license_key[:16] if license_info else None,
                license_status=self._get_license_status(license_info)
            )
            
            error_msg = ErrorMessage(
                header=header,
                error_code=error_code,
                error_message=error_message,
                **kwargs
            )
            
            self.message_stats["messages_sent"] += 1
            return error_msg
            
        except Exception as e:
            self.message_stats["errors_encountered"] += 1
            logger.error(f"Failed to create error message: {e}")
            raise
    
    def serialize_message(self, message: Any) -> str:
        """
        Serialize a message to JSON
        
        Args:
            message: Message object to serialize
            
        Returns:
            JSON string
        """
        try:
            if hasattr(message, '__dict__'):
                # Convert dataclass to dict
                message_dict = asdict(message)
            else:
                message_dict = message
            
            # Convert enum values to their string representations
            def convert_enums(obj):
                if isinstance(obj, dict):
                    return {k: convert_enums(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_enums(item) for item in obj]
                elif hasattr(obj, 'value'):  # Enum object
                    return obj.value
                else:
                    return obj
            
            message_dict = convert_enums(message_dict)
            return json.dumps(message_dict, indent=2, default=str)
            
        except Exception as e:
            logger.error(f"Failed to serialize message: {e}")
            raise
    
    def deserialize_message(self, json_str: str) -> Dict[str, Any]:
        """
        Deserialize a JSON message
        
        Args:
            json_str: JSON string to deserialize
            
        Returns:
            Message dictionary
        """
        try:
            message = json.loads(json_str)
            self.message_stats["messages_received"] += 1
            return message
            
        except json.JSONDecodeError as e:
            self.message_stats["errors_encountered"] += 1
            logger.error(f"Failed to deserialize message: {e}")
            raise
    
    def validate_message(self, message: Union[Dict[str, Any], str]) -> tuple[bool, Optional[str]]:
        """
        Validate a protocol message
        
        Args:
            message: Message to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        return self.validator.validate_message(message)
    
    def _get_license_status(self, license_info: Optional[LicenseInfo]) -> LicenseStatusProtocol:
        """Get license status for protocol messages"""
        if not license_info:
            return LicenseStatusProtocol.MISSING
        
        if license_info.status == ValidationStatus.VALID:
            return LicenseStatusProtocol.VALID
        elif license_info.status == ValidationStatus.EXPIRED:
            return LicenseStatusProtocol.EXPIRED
        else:
            return LicenseStatusProtocol.INVALID
    
    def get_protocol_stats(self) -> Dict[str, Any]:
        """Get protocol statistics"""
        return {
            "current_version": self.current_version.value,
            "message_stats": self.message_stats,
            "validation_stats": self.validator.get_validation_stats()
        }


def create_protocol_manager(version: ProtocolVersion = ProtocolVersion.V2_0) -> ProtocolManager:
    """Create and initialize protocol manager"""
    return ProtocolManager(current_version=version)


def create_inference_request(session_id: str,
                           network_id: str,
                           license_hash: str,
                           input_tensors: Dict[str, Any],
                           step: int = 0,
                           model_id: Optional[str] = None,
                           **kwargs) -> InferenceRequest:
    """
    Create a standardized inference request (utility function)
    
    Args:
        session_id: Session identifier
        network_id: Network identifier
        license_hash: License hash for validation
        input_tensors: Input tensors for inference
        step: Step number
        model_id: Model identifier (optional)
        **kwargs: Additional parameters
        
    Returns:
        InferenceRequest object
    """
    # Create header
    header = MessageHeader(
        message_type=MessageType.INFERENCE_REQUEST,
        protocol_version=ProtocolVersion.V2_0,
        session_id=session_id,
        license_hash=license_hash,
        license_status=LicenseStatusProtocol.VALID if license_hash else LicenseStatusProtocol.MISSING
    )
    
    # Convert input_tensors to prompt format for compatibility
    if isinstance(input_tensors, dict) and "prompt" in input_tensors:
        prompt = input_tensors["prompt"]
    elif isinstance(input_tensors, dict) and "input_ids" in input_tensors:
        prompt = f"<input_ids>{input_tensors['input_ids']}</input_ids>"
    else:
        prompt = str(input_tensors)
    
    # Create request
    request = InferenceRequest(
        header=header,
        model_id=model_id or "default",
        prompt=prompt,
        **kwargs
    )
    
    # Add custom fields for backward compatibility
    request.session_id = session_id
    request.network_id = network_id
    request.step = step
    request.input_tensors = input_tensors
    request.license_hash = license_hash
    
    return request


def create_inference_response(session_id: str,
                            network_id: str,
                            step: int,
                            status: str,
                            license_status: str,
                            output_tensors: Optional[Dict[str, Any]] = None,
                            error: Optional[str] = None,
                            processing_time: float = 0.0,
                            worker_id: Optional[str] = None,
                            **kwargs) -> InferenceResponse:
    """
    Create a standardized inference response (utility function)
    
    Args:
        session_id: Session identifier
        network_id: Network identifier
        step: Step number
        status: Response status
        license_status: License status
        output_tensors: Output tensors (optional)
        error: Error message (optional)
        processing_time: Processing time in seconds
        worker_id: Worker identifier (optional)
        **kwargs: Additional parameters
        
    Returns:
        InferenceResponse object
    """
    # Create header
    header = MessageHeader(
        message_type=MessageType.INFERENCE_RESPONSE,
        protocol_version=ProtocolVersion.V2_0,
        session_id=session_id,
        license_status=LicenseStatusProtocol(license_status) if license_status else LicenseStatusProtocol.MISSING,
        sender_id=worker_id
    )
    
    # Convert output_tensors to generated_text format
    generated_text = ""
    if output_tensors:
        if isinstance(output_tensors, dict) and "generated_text" in output_tensors:
            generated_text = output_tensors["generated_text"]
        elif isinstance(output_tensors, dict) and "output" in output_tensors:
            generated_text = str(output_tensors["output"])
        else:
            generated_text = str(output_tensors)
    
    # Determine finish reason based on status
    finish_reason = "stop"
    if status in ["error", "license_error"]:
        finish_reason = "error"
    elif status == "timeout":
        finish_reason = "length"
    
    # Create response
    response = InferenceResponse(
        header=header,
        request_id=f"{session_id}_{step}",
        model_id=kwargs.get("model_id", "default"),
        generated_text=generated_text,
        finish_reason=finish_reason,
        processing_time_ms=int(processing_time * 1000),
        worker_id=worker_id,
        error_code=ErrorCode.SUCCESS if status == "success" else ErrorCode.INTERNAL_ERROR,
        error_message=error,
        **{k: v for k, v in kwargs.items() if k not in ["model_id"]}
    )
    
    # Add custom fields for backward compatibility
    response.session_id = session_id
    response.network_id = network_id
    response.step = step
    response.status = status
    response.license_status = license_status
    response.output_tensors = output_tensors
    response.error = error
    response.processing_time = processing_time
    
    return response


def main():
    """Main function for testing protocol specification"""
    print("=== Testing Protocol Specification ===\n")
    
    # Create protocol manager
    protocol_manager = create_protocol_manager()
    
    # Create test license
    from license_models import LicenseInfo, SubscriptionTier, ValidationStatus as LicStatus
    
    license_info = LicenseInfo(
        license_key="TIKT-PRO-12-TEST01",
        plan=SubscriptionTier.PRO,
        duration_months=12,
        unique_id="TEST01",
        expires_at=datetime.now() + timedelta(days=365),
        max_clients=20,
        allowed_models=["llama", "mistral"],
        allowed_features=["multi_network", "api_access"],
        status=LicStatus.VALID,
        hardware_signature="test_hw_sig",
        created_at=datetime.now(),
        checksum="test_checksum"
    )
    
    # Test 1: Create and validate inference request
    print("1. Testing Inference Request")
    request = protocol_manager.create_inference_request(
        model_id="llama-7b",
        prompt="Hello, how are you?",
        license_info=license_info,
        max_tokens=150,
        temperature=0.8
    )
    
    # Serialize and validate
    request_json = protocol_manager.serialize_message(request)
    print(f"Request created: {request.header.message_id}")
    
    is_valid, error = protocol_manager.validate_message(request_json)
    print(f"Validation result: {'✓ VALID' if is_valid else '✗ INVALID'}")
    if error:
        print(f"Error: {error}")
    
    print()
    
    # Test 2: Create and validate inference response
    print("2. Testing Inference Response")
    response = protocol_manager.create_inference_response(
        request_id=request.header.message_id,
        model_id="llama-7b",
        generated_text="Hello! I'm doing well, thank you for asking.",
        license_info=license_info,
        finish_reason="stop",
        usage={"prompt_tokens": 5, "completion_tokens": 12, "total_tokens": 17},
        processing_time_ms=1250
    )
    
    response_json = protocol_manager.serialize_message(response)
    print(f"Response created: {response.header.message_id}")
    
    is_valid, error = protocol_manager.validate_message(response_json)
    print(f"Validation result: {'✓ VALID' if is_valid else '✗ INVALID'}")
    if error:
        print(f"Error: {error}")
    
    print()
    
    # Test 3: Create and validate heartbeat
    print("3. Testing Heartbeat Message")
    heartbeat = protocol_manager.create_heartbeat(
        worker_id="worker-001",
        license_info=license_info,
        status="healthy",
        load_percentage=45.2,
        available_memory_mb=8192,
        active_sessions=3,
        models_loaded=["llama-7b", "mistral-7b"]
    )
    
    heartbeat_json = protocol_manager.serialize_message(heartbeat)
    print(f"Heartbeat created: {heartbeat.header.message_id}")
    
    is_valid, error = protocol_manager.validate_message(heartbeat_json)
    print(f"Validation result: {'✓ VALID' if is_valid else '✗ INVALID'}")
    if error:
        print(f"Error: {error}")
    
    print()
    
    # Test 4: Test invalid message
    print("4. Testing Invalid Message Validation")
    invalid_message = {
        "header": {
            "message_id": "invalid-id-format",  # Invalid UUID format
            "message_type": "invalid_type",     # Invalid message type
            "protocol_version": "3.0",          # Unsupported version
            "timestamp": "invalid-timestamp"    # Invalid timestamp
        },
        "model_id": "",  # Empty model_id
        "prompt": ""     # Empty prompt
    }
    
    is_valid, error = protocol_manager.validate_message(invalid_message)
    print(f"Validation result: {'✓ VALID' if is_valid else '✗ INVALID'}")
    if error:
        print(f"Error: {error}")
    
    print()
    
    # Test 5: Protocol statistics
    print("5. Protocol Statistics")
    stats = protocol_manager.get_protocol_stats()
    print(f"Current version: {stats['current_version']}")
    print(f"Messages sent: {stats['message_stats']['messages_sent']}")
    print(f"Messages received: {stats['message_stats']['messages_received']}")
    print(f"Validation success rate: {stats['validation_stats']['success_rate_percentage']}%")
    
    print("\n=== Protocol Specification Tests Completed ===")


if __name__ == "__main__":
    main()