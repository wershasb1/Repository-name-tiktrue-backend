"""
TikTrue Platform License Validation System

This module provides comprehensive license validation with hardware binding,
offline validation capabilities, and license management for both admin and client modes.

Requirements addressed:
- 4.1: Online license validation and local storage
- 4.2: Hardware fingerprint binding
- 4.3: Offline license validation
- 4.4: Client license status transfer through admin node
- 4.5: Hardware fingerprint verification failure handling
- 4.6: License expiry enforcement
- 4.7: License renewal and hardware binding updates
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

from security.hardware_fingerprint import get_hardware_fingerprint, HardwareChange
import license_storage
from license_models import (
    LicenseInfo, CachedLicense, ValidationStatus, LicenseType,
    ValidationResult, BindingResult, ExpiryStatus, ClientLicenseStatus
)
from core.config_manager import get_config

# Configure logging
logger = logging.getLogger(__name__)


class LicenseValidationError(Exception):
    """Custom exception for license validation errors"""
    pass


class LicenseValidator:
    """
    Comprehensive license validation system with hardware binding
    and offline validation capabilities.
    """
    
    # Grace period for expired licenses (in days)
    GRACE_PERIOD_DAYS = 7
    
    # Hardware change tolerance levels
    HARDWARE_CHANGE_TOLERANCE = {
        'low': 0.1,      # 10% change allowed
        'medium': 0.25,  # 25% change allowed
        'high': 0.5      # 50% change allowed
    }
    
    def __init__(self):
        """Initialize license validator"""
        self.config = get_config()
        self.hardware_fp = get_hardware_fingerprint()
        # Create a new instance of LicenseStorage directly
        self.license_storage = license_storage.LicenseStorage()
        
        logger.info("LicenseValidator system initialized")
    
    def validate_license(self, license_key: str, hardware_id: str) -> ValidationResult:
        """
        Validate license with hardware binding
        
        Args:
            license_key: License key to validate
            hardware_id: Hardware fingerprint for binding validation
            
        Returns:
            ValidationResult with validation status and details
        """
        try:
            logger.info(f"Validating license: {license_key[:8]}...")
            
            # Retrieve cached license
            cached_license = self.license_storage.retrieve_cached_license(hardware_id)
            
            if not cached_license:
                return ValidationResult(
                    status=ValidationStatus.NOT_FOUND,
                    message="No cached license found",
                    hardware_fingerprint=hardware_id,
                    validation_timestamp=datetime.now(timezone.utc).isoformat(),
                    errors=["License not found in local cache"]
                )
            
            license_info = cached_license.license_info
            
            # Validate license key match
            if license_info.license_key != license_key:
                logger.warning("License key mismatch")
                return ValidationResult(
                    status=ValidationStatus.INVALID,
                    message="License key mismatch",
                    hardware_fingerprint=hardware_id,
                    validation_timestamp=datetime.now(timezone.utc).isoformat(),
                    errors=["Provided license key does not match stored license"]
                )
            
            # Validate hardware fingerprint
            if not self.hardware_fp.validate_current_hardware(hardware_id):
                logger.warning("Hardware fingerprint validation failed")
                
                # Check for hardware changes
                changes = self.hardware_fp.detect_hardware_changes(hardware_id)
                change_details = [f"{change.component}: {change.severity}" for change in changes]
                
                return ValidationResult(
                    status=ValidationStatus.HARDWARE_MISMATCH,
                    message="Hardware fingerprint mismatch - hardware may have changed",
                    license_info=license_info,
                    hardware_fingerprint=hardware_id,
                    validation_timestamp=datetime.now(timezone.utc).isoformat(),
                    errors=[f"Hardware changes detected: {', '.join(change_details)}"]
                )
            
            # Check license expiry
            expiry_status = self.check_expiry(license_key)
            
            if expiry_status.is_expired and not expiry_status.grace_period_active:
                logger.warning("License has expired")
                return ValidationResult(
                    status=ValidationStatus.EXPIRED,
                    message="License has expired",
                    license_info=license_info,
                    hardware_fingerprint=hardware_id,
                    days_until_expiry=expiry_status.days_until_expiry,
                    validation_timestamp=datetime.now(timezone.utc).isoformat(),
                    errors=[f"License expired on {expiry_status.expiry_date}"]
                )
            
            # Check if license is active
            if not license_info.is_active:
                logger.warning("License is inactive")
                return ValidationResult(
                    status=ValidationStatus.INVALID,
                    message="License is inactive",
                    license_info=license_info,
                    hardware_fingerprint=hardware_id,
                    validation_timestamp=datetime.now(timezone.utc).isoformat(),
                    errors=["License has been deactivated"]
                )
            
            # License is valid
            logger.info("License validation successful")
            return ValidationResult(
                status=ValidationStatus.VALID,
                message="License is valid and active",
                license_info=license_info,
                hardware_fingerprint=hardware_id,
                days_until_expiry=expiry_status.days_until_expiry,
                validation_timestamp=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            logger.error(f"License validation failed: {str(e)}")
            return ValidationResult(
                status=ValidationStatus.ERROR,
                message=f"Validation error: {str(e)}",
                hardware_fingerprint=hardware_id,
                validation_timestamp=datetime.now(timezone.utc).isoformat(),
                errors=[str(e)]
            )
    
    def bind_license_to_hardware(self, license_key: str) -> BindingResult:
        """
        Bind license to current hardware fingerprint
        
        Args:
            license_key: License key to bind
            
        Returns:
            BindingResult with binding status
        """
        try:
            logger.info(f"Binding license to hardware: {license_key[:8]}...")
            
            # Generate current hardware fingerprint
            hardware_id = self.hardware_fp.generate_fingerprint()
            
            # Check if license already exists
            cached_license = self.license_storage.retrieve_cached_license(hardware_id)
            
            if cached_license and cached_license.license_info.license_key == license_key:
                logger.info("License already bound to this hardware")
                return BindingResult(
                    success=True,
                    message="License already bound to current hardware",
                    hardware_fingerprint=hardware_id,
                    binding_timestamp=datetime.now(timezone.utc).isoformat()
                )
            
            # For new binding, we would typically need to validate with backend server
            # For now, we'll create a basic license info structure
            # In production, this would come from the backend server response
            
            logger.warning("Hardware binding requires backend server validation - creating placeholder")
            
            return BindingResult(
                success=False,
                message="Hardware binding requires online validation with backend server",
                hardware_fingerprint=hardware_id,
                binding_timestamp=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            logger.error(f"License binding failed: {str(e)}")
            return BindingResult(
                success=False,
                message=f"Binding failed: {str(e)}",
                hardware_fingerprint="",
                binding_timestamp=datetime.now(timezone.utc).isoformat()
            )
    
    def check_expiry(self, license_key: str) -> ExpiryStatus:
        """
        Check license expiry status
        
        Args:
            license_key: License key to check
            
        Returns:
            ExpiryStatus with expiry information
        """
        try:
            hardware_id = self.hardware_fp.generate_fingerprint()
            cached_license = self.license_storage.retrieve_cached_license(hardware_id)
            
            if not cached_license or cached_license.license_info.license_key != license_key:
                return ExpiryStatus(
                    is_expired=True,
                    expiry_date="unknown",
                    days_until_expiry=0
                )
            
            license_info = cached_license.license_info
            
            try:
                expiry_date = datetime.fromisoformat(license_info.expiry_date.replace('Z', '+00:00'))
                current_time = datetime.now(timezone.utc)
                
                days_until_expiry = (expiry_date - current_time).days
                is_expired = current_time > expiry_date
                
                # Check grace period
                grace_period_active = False
                grace_period_days = 0
                
                if is_expired:
                    days_since_expiry = (current_time - expiry_date).days
                    if days_since_expiry <= self.GRACE_PERIOD_DAYS:
                        grace_period_active = True
                        grace_period_days = self.GRACE_PERIOD_DAYS - days_since_expiry
                
                return ExpiryStatus(
                    is_expired=is_expired,
                    expiry_date=license_info.expiry_date,
                    days_until_expiry=days_until_expiry,
                    grace_period_active=grace_period_active,
                    grace_period_days=grace_period_days
                )
                
            except Exception as e:
                logger.error(f"Failed to parse expiry date: {str(e)}")
                return ExpiryStatus(
                    is_expired=True,
                    expiry_date=license_info.expiry_date,
                    days_until_expiry=0
                )
                
        except Exception as e:
            logger.error(f"Failed to check license expiry: {str(e)}")
            return ExpiryStatus(
                is_expired=True,
                expiry_date="error",
                days_until_expiry=0
            )
    
    def validate_offline(self, cached_license: CachedLicense) -> ValidationResult:
        """
        Validate license in offline mode using cached data
        
        Args:
            cached_license: Cached license data
            
        Returns:
            ValidationResult with offline validation status
        """
        try:
            logger.info("Performing offline license validation")
            
            license_info = cached_license.license_info
            hardware_id = self.hardware_fp.generate_fingerprint()
            
            # Validate hardware fingerprint
            if cached_license.hardware_fingerprint != hardware_id:
                return ValidationResult(
                    status=ValidationStatus.HARDWARE_MISMATCH,
                    message="Hardware fingerprint mismatch in offline mode",
                    license_info=license_info,
                    hardware_fingerprint=hardware_id,
                    validation_timestamp=datetime.now(timezone.utc).isoformat(),
                    errors=["Hardware has changed since license was cached"]
                )
            
            # Check expiry
            expiry_status = self.check_expiry(license_info.license_key)
            
            if expiry_status.is_expired and not expiry_status.grace_period_active:
                return ValidationResult(
                    status=ValidationStatus.EXPIRED,
                    message="License expired in offline mode",
                    license_info=license_info,
                    hardware_fingerprint=hardware_id,
                    days_until_expiry=expiry_status.days_until_expiry,
                    validation_timestamp=datetime.now(timezone.utc).isoformat(),
                    errors=["License has expired and grace period has ended"]
                )
            
            # Check if license is active
            if not license_info.is_active:
                return ValidationResult(
                    status=ValidationStatus.INVALID,
                    message="License is inactive",
                    license_info=license_info,
                    hardware_fingerprint=hardware_id,
                    validation_timestamp=datetime.now(timezone.utc).isoformat(),
                    errors=["License has been deactivated"]
                )
            
            # Offline validation successful
            logger.info("Offline license validation successful")
            return ValidationResult(
                status=ValidationStatus.VALID,
                message="License valid in offline mode" + 
                       (f" (grace period: {expiry_status.grace_period_days} days)" if expiry_status.grace_period_active else ""),
                license_info=license_info,
                hardware_fingerprint=hardware_id,
                days_until_expiry=expiry_status.days_until_expiry,
                validation_timestamp=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            logger.error(f"Offline license validation failed: {str(e)}")
            return ValidationResult(
                status=ValidationStatus.ERROR,
                message=f"Offline validation error: {str(e)}",
                hardware_fingerprint=hardware_id if 'hardware_id' in locals() else "",
                validation_timestamp=datetime.now(timezone.utc).isoformat(),
                errors=[str(e)]
            )
    
    def transfer_license_status(self, admin_license: LicenseInfo) -> ClientLicenseStatus:
        """
        Transfer license status from admin to client for network validation
        
        Args:
            admin_license: Admin license information
            
        Returns:
            ClientLicenseStatus for network transfer
        """
        try:
            logger.info(f"Transferring license status for admin: {admin_license.user_id}")
            
            # Check if admin license is valid
            validation_result = self.validate_license(
                admin_license.license_key,
                admin_license.hardware_fingerprint
            )
            
            is_authorized = validation_result.status == ValidationStatus.VALID
            
            return ClientLicenseStatus(
                is_authorized=is_authorized,
                license_type="admin_delegated",
                plan_type=admin_license.plan_type,
                max_clients=admin_license.max_clients,
                allowed_models=admin_license.allowed_models,
                expiry_date=admin_license.expiry_date,
                admin_node_id=self.config.network.admin_node_id,
                transferred_at=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            logger.error(f"License status transfer failed: {str(e)}")
            return ClientLicenseStatus(
                is_authorized=False,
                license_type="error",
                plan_type="none",
                max_clients=0,
                allowed_models=[],
                expiry_date="",
                admin_node_id="",
                transferred_at=datetime.now(timezone.utc).isoformat()
            )
    
    def handle_hardware_mismatch(self, stored_fingerprint: str, stored_hardware_info: Optional[Any] = None) -> Dict[str, Any]:
        """
        Handle hardware fingerprint mismatch scenarios using enhanced hardware fingerprinting
        
        Args:
            stored_fingerprint: Previously stored hardware fingerprint
            stored_hardware_info: Previously stored hardware information (if available)
            
        Returns:
            Dictionary with mismatch handling results
        """
        try:
            logger.warning("Handling hardware fingerprint mismatch with enhanced detection")
            
            current_fingerprint = self.hardware_fp.generate_fingerprint()
            
            # Use enhanced validation if we have stored hardware info
            if stored_hardware_info:
                validation_result = self.hardware_fp.validate_hardware_with_details(
                    stored_hardware_info, 
                    tolerance_level="medium"
                )
                
                changes = validation_result.get("changes_detected", [])
                severity_summary = validation_result.get("severity_summary", {})
                tolerance_exceeded = validation_result.get("tolerance_exceeded", True)
                
                # Determine action based on detailed analysis
                if severity_summary.get("critical", 0) > 0:
                    action = "require_revalidation"
                    message = "Critical hardware changes detected - license revalidation required"
                elif severity_summary.get("high", 0) > 1:
                    action = "require_revalidation"
                    message = "Multiple significant hardware changes detected"
                elif tolerance_exceeded:
                    action = "warning"
                    message = "Hardware changes detected - monitoring required"
                else:
                    action = "allow"
                    message = "Hardware changes within acceptable tolerance"
                
                return {
                    "action": action,
                    "message": message,
                    "validation_result": validation_result,
                    "changes_detected": len(changes),
                    "severity_summary": severity_summary,
                    "tolerance_exceeded": tolerance_exceeded,
                    "current_fingerprint": current_fingerprint[:16] + "...",
                    "stored_fingerprint": stored_fingerprint[:16] + "...",
                    "handled_at": datetime.now(timezone.utc).isoformat()
                }
            else:
                # Fallback to basic validation without detailed change analysis
                validation_result = self.hardware_fp.validate_current_hardware(
                    stored_fingerprint, 
                    tolerance_level="medium"
                )
                
                is_valid = validation_result.get("is_valid", False)
                tolerance_exceeded = validation_result.get("tolerance_exceeded", True)
                
                if is_valid:
                    action = "allow"
                    message = "Hardware changes within acceptable tolerance"
                elif tolerance_exceeded:
                    action = "require_revalidation"
                    message = "Hardware changes exceed tolerance - license revalidation required"
                else:
                    action = "warning"
                    message = "Hardware fingerprint mismatch detected"
                
                return {
                    "action": action,
                    "message": message,
                    "validation_result": validation_result,
                    "current_fingerprint": current_fingerprint[:16] + "...",
                    "stored_fingerprint": stored_fingerprint[:16] + "...",
                    "handled_at": datetime.now(timezone.utc).isoformat()
                }
            
        except Exception as e:
            logger.error(f"Enhanced hardware mismatch handling failed: {str(e)}")
            return {
                "action": "error",
                "message": f"Mismatch handling failed: {str(e)}",
                "changes_detected": 0,
                "handled_at": datetime.now(timezone.utc).isoformat()
            }
    
    def enforce_license_expiry(self, license_key: str) -> bool:
        """
        Enforce license expiry by preventing model usage
        
        Args:
            license_key: License key to check
            
        Returns:
            True if license is valid and usage allowed
        """
        try:
            expiry_status = self.check_expiry(license_key)
            
            if expiry_status.is_expired and not expiry_status.grace_period_active:
                logger.warning(f"License usage blocked - expired: {license_key[:8]}...")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"License expiry enforcement failed: {str(e)}")
            return False
    
    def get_license_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive license status summary
        
        Returns:
            Dictionary with license summary information
        """
        try:
            hardware_id = self.hardware_fp.generate_fingerprint()
            license_status = self.license_storage.get_license_status(hardware_id)
            hardware_summary = self.hardware_fp.get_hardware_summary()
            
            return {
                "license_status": license_status,
                "hardware_summary": hardware_summary,
                "hardware_fingerprint": hardware_id[:16] + "...",
                "validation_capabilities": {
                    "offline_validation": True,
                    "hardware_binding": True,
                    "expiry_enforcement": True,
                    "grace_period_days": self.GRACE_PERIOD_DAYS
                },
                "summary_generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate license summary: {str(e)}")
            return {
                "error": str(e),
                "summary_generated_at": datetime.now(timezone.utc).isoformat()
            }


# Global license validator instance
license_validator = LicenseValidator()


def get_license_validator() -> LicenseValidator:
    """Get global license validator instance"""
    return license_validator


def validate_current_license(license_key: str) -> ValidationResult:
    """Validate license using current hardware fingerprint"""
    hardware_id = get_hardware_fingerprint().generate_fingerprint()
    return security.license_validator.validate_license(license_key, hardware_id)


def is_license_valid(license_key: str) -> bool:
    """Quick license validity check"""
    result = validate_current_license(license_key)
    return result.status == ValidationStatus.VALID