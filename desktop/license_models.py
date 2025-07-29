"""
TikTrue Platform License Data Models

This module contains shared data models for the license validation system
to avoid circular imports between modules.
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from enum import Enum


class ValidationStatus(Enum):
    """License validation status enumeration"""
    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    HARDWARE_MISMATCH = "hardware_mismatch"
    NOT_FOUND = "not_found"
    ERROR = "error"


class LicenseType(Enum):
    """License type enumeration"""
    ADMIN = "admin"
    CLIENT = "client"


class SubscriptionTier(Enum):
    """Subscription tier enumeration"""
    FREE = "FREE"
    PRO = "PRO"
    ENT = "ENT"


@dataclass
class LicenseInfo:
    """License information structure"""
    license_key: str
    user_id: str
    plan_type: str  # Free, Pro, Enterprise
    expiry_date: str  # ISO format datetime
    max_clients: int
    allowed_models: List[str]
    hardware_fingerprint: str
    is_active: bool
    created_at: str
    last_validated: str
    status: ValidationStatus = ValidationStatus.VALID


@dataclass
class CachedLicense:
    """Cached license structure for offline validation"""
    license_info: LicenseInfo
    cached_at: str
    hardware_fingerprint: str
    encrypted_data: str
    validation_hash: str
    storage_version: str


@dataclass
class ValidationResult:
    """License validation result"""
    status: ValidationStatus
    message: str
    license_info: Optional[LicenseInfo] = None
    hardware_fingerprint: str = ""
    days_until_expiry: int = 0
    validation_timestamp: str = ""
    errors: Optional[List[str]] = None


@dataclass
class BindingResult:
    """License binding result"""
    success: bool
    message: str
    hardware_fingerprint: str = ""
    binding_timestamp: str = ""


@dataclass
class ExpiryStatus:
    """License expiry status"""
    is_expired: bool
    expiry_date: str
    days_until_expiry: int
    grace_period_active: bool = False
    grace_period_days: int = 0


@dataclass
class ClientLicenseStatus:
    """Client license status for network transfer"""
    is_authorized: bool
    license_type: str
    plan_type: str
    max_clients: int
    allowed_models: List[str]
    expiry_date: str
    admin_node_id: str
    transferred_at: str


@dataclass
class StorageResult:
    """License storage operation result"""
    success: bool
    message: str
    license_path: Optional[str] = None


@dataclass
class UpdateResult:
    """License update operation result"""
    success: bool
    message: str
    updated_fields: List[str]