"""
Security module for TikTrue Platform

This package contains security-related modules for authentication, encryption,
license validation, and hardware fingerprinting.
"""

from security.license_validator import LicenseValidator, get_license_validator, validate_current_license, is_license_valid
from security.auth_manager import AuthenticationManager, NodeRole, AuthenticationMethod
from security.crypto_layer import CryptoLayer, CryptographicLayer, EncryptionLevel
from security.hardware_fingerprint import HardwareFingerprint, get_hardware_fingerprint

__all__ = [
    'LicenseValidator', 'get_license_validator', 'validate_current_license', 'is_license_valid',
    'AuthenticationManager', 'NodeRole', 'AuthenticationMethod',
    'CryptoLayer', 'CryptographicLayer', 'EncryptionLevel',
    'HardwareFingerprint', 'get_hardware_fingerprint'
]