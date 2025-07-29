"""
Hardware Fingerprinting Module for TikTrue License System

This module provides utilities for generating and validating hardware fingerprints
to bind licenses to specific hardware configurations.
"""

import hashlib
import json
import platform
import uuid
from typing import Dict, Any, Optional


class HardwareFingerprintGenerator:
    """Generate hardware fingerprints for license binding"""
    
    @staticmethod
    def generate_system_fingerprint() -> str:
        """
        Generate a hardware fingerprint based on system characteristics
        
        Returns:
            str: A unique hardware fingerprint hash
        """
        system_info = HardwareFingerprintGenerator._collect_system_info()
        
        # Create a stable string representation
        fingerprint_data = json.dumps(system_info, sort_keys=True)
        
        # Generate SHA-256 hash
        fingerprint_hash = hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()
        
        return fingerprint_hash
    
    @staticmethod
    def _collect_system_info() -> Dict[str, Any]:
        """
        Collect system information for fingerprinting
        
        Returns:
            Dict[str, Any]: System information dictionary
        """
        try:
            system_info = {
                'platform': platform.platform(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'node': platform.node(),
                'mac_address': HardwareFingerprintGenerator._get_mac_address(),
            }
            
            # Add Windows-specific information
            if platform.system() == 'Windows':
                system_info.update(HardwareFingerprintGenerator._get_windows_info())
            
            # Add Linux-specific information
            elif platform.system() == 'Linux':
                system_info.update(HardwareFingerprintGenerator._get_linux_info())
                
            # Add macOS-specific information
            elif platform.system() == 'Darwin':
                system_info.update(HardwareFingerprintGenerator._get_macos_info())
                
        except Exception as e:
            # Fallback to basic information if detailed collection fails
            system_info = {
                'platform': platform.platform(),
                'system': platform.system(),
                'machine': platform.machine(),
                'fallback': True,
                'error': str(e)
            }
            
        return system_info
    
    @staticmethod
    def _get_mac_address() -> str:
        """Get MAC address of the primary network interface"""
        try:
            mac = uuid.getnode()
            return ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
        except:
            return 'unknown'
    
    @staticmethod
    def _get_windows_info() -> Dict[str, Any]:
        """Get Windows-specific system information"""
        windows_info = {}
        
        try:
            import winreg
            
            # Get Windows product ID
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                              r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                try:
                    product_id = winreg.QueryValueEx(key, "ProductId")[0]
                    windows_info['product_id'] = product_id
                except:
                    pass
                    
                try:
                    install_date = winreg.QueryValueEx(key, "InstallDate")[0]
                    windows_info['install_date'] = install_date
                except:
                    pass
                    
        except ImportError:
            # winreg not available (not Windows)
            pass
        except Exception:
            # Other errors in accessing registry
            pass
            
        return windows_info
    
    @staticmethod
    def _get_linux_info() -> Dict[str, Any]:
        """Get Linux-specific system information"""
        linux_info = {}
        
        try:
            # Try to read machine ID
            with open('/etc/machine-id', 'r') as f:
                linux_info['machine_id'] = f.read().strip()
        except:
            try:
                with open('/var/lib/dbus/machine-id', 'r') as f:
                    linux_info['machine_id'] = f.read().strip()
            except:
                pass
                
        try:
            # Try to read OS release info
            with open('/etc/os-release', 'r') as f:
                os_release = {}
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os_release[key] = value.strip('"')
                linux_info['os_release'] = os_release
        except:
            pass
            
        return linux_info
    
    @staticmethod
    def _get_macos_info() -> Dict[str, Any]:
        """Get macOS-specific system information"""
        macos_info = {}
        
        try:
            import subprocess
            
            # Get hardware UUID
            result = subprocess.run(['system_profiler', 'SPHardwareDataType'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Hardware UUID' in line:
                        uuid_value = line.split(':')[1].strip()
                        macos_info['hardware_uuid'] = uuid_value
                        break
                        
        except:
            pass
            
        return macos_info


class HardwareFingerprintValidator:
    """Validate hardware fingerprints for license enforcement"""
    
    @staticmethod
    def validate_fingerprint(stored_fingerprint: str, 
                           current_fingerprint: str,
                           tolerance: float = 0.0) -> bool:
        """
        Validate if current hardware fingerprint matches stored fingerprint
        
        Args:
            stored_fingerprint: Previously stored fingerprint
            current_fingerprint: Current system fingerprint
            tolerance: Tolerance level for minor hardware changes (0.0 = exact match)
            
        Returns:
            bool: True if fingerprints match within tolerance
        """
        if not stored_fingerprint or not current_fingerprint:
            return False
            
        # For exact matching (default)
        if tolerance == 0.0:
            return stored_fingerprint == current_fingerprint
            
        # For fuzzy matching (future enhancement)
        return HardwareFingerprintValidator._fuzzy_match(
            stored_fingerprint, current_fingerprint, tolerance
        )
    
    @staticmethod
    def _fuzzy_match(fingerprint1: str, fingerprint2: str, tolerance: float) -> bool:
        """
        Perform fuzzy matching between fingerprints
        
        Args:
            fingerprint1: First fingerprint
            fingerprint2: Second fingerprint
            tolerance: Tolerance level (0.0 to 1.0)
            
        Returns:
            bool: True if fingerprints match within tolerance
        """
        # Simple implementation - can be enhanced with more sophisticated algorithms
        if len(fingerprint1) != len(fingerprint2):
            return False
            
        matches = sum(c1 == c2 for c1, c2 in zip(fingerprint1, fingerprint2))
        similarity = matches / len(fingerprint1)
        
        return similarity >= (1.0 - tolerance)
    
    @staticmethod
    def is_fingerprint_format_valid(fingerprint: str) -> bool:
        """
        Check if fingerprint has valid format
        
        Args:
            fingerprint: Hardware fingerprint to validate
            
        Returns:
            bool: True if format is valid
        """
        if not fingerprint or not isinstance(fingerprint, str):
            return False
            
        # Check if it's a valid SHA-256 hash (64 hex characters)
        if len(fingerprint) == 64:
            try:
                int(fingerprint, 16)
                return True
            except ValueError:
                return False
                
        return False


class LicenseHardwareBinding:
    """Handle license-hardware binding operations"""
    
    @staticmethod
    def bind_license_to_hardware(license_obj, hardware_fingerprint: str) -> bool:
        """
        Bind a license to specific hardware
        
        Args:
            license_obj: License model instance
            hardware_fingerprint: Hardware fingerprint to bind to
            
        Returns:
            bool: True if binding successful
        """
        try:
            if not HardwareFingerprintValidator.is_fingerprint_format_valid(hardware_fingerprint):
                return False
                
            # Update user's hardware fingerprint
            license_obj.user.hardware_fingerprint = hardware_fingerprint
            license_obj.user.save()
            
            # Mark license as hardware bound
            license_obj.hardware_bound = True
            license_obj.save()
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def validate_license_hardware(license_obj, current_fingerprint: str) -> bool:
        """
        Validate if license can be used on current hardware
        
        Args:
            license_obj: License model instance
            current_fingerprint: Current hardware fingerprint
            
        Returns:
            bool: True if license is valid for current hardware
        """
        # If license is not hardware bound, allow usage
        if not license_obj.hardware_bound:
            return True
            
        # If no stored fingerprint, bind to current hardware
        stored_fingerprint = license_obj.user.hardware_fingerprint
        if not stored_fingerprint:
            return LicenseHardwareBinding.bind_license_to_hardware(
                license_obj, current_fingerprint
            )
            
        # Validate against stored fingerprint
        return HardwareFingerprintValidator.validate_fingerprint(
            stored_fingerprint, current_fingerprint
        )
    
    @staticmethod
    def get_hardware_info_summary(fingerprint: str) -> Dict[str, Any]:
        """
        Get a summary of hardware information from fingerprint
        
        Args:
            fingerprint: Hardware fingerprint
            
        Returns:
            Dict[str, Any]: Hardware information summary
        """
        return {
            'fingerprint': fingerprint,
            'format_valid': HardwareFingerprintValidator.is_fingerprint_format_valid(fingerprint),
            'length': len(fingerprint) if fingerprint else 0,
            'type': 'SHA-256 Hash' if fingerprint and len(fingerprint) == 64 else 'Unknown',
            'generated_at': 'Unknown',  # Could be enhanced to store generation timestamp
        }


# Utility functions for easy access
def generate_hardware_fingerprint() -> str:
    """Generate hardware fingerprint for current system"""
    return HardwareFingerprintGenerator.generate_system_fingerprint()

def validate_hardware_fingerprint(stored: str, current: str) -> bool:
    """Validate hardware fingerprint match"""
    return HardwareFingerprintValidator.validate_fingerprint(stored, current)

def bind_license_to_current_hardware(license_obj):
    """Bind license to current hardware"""
    current_fingerprint = generate_hardware_fingerprint()
    return LicenseHardwareBinding.bind_license_to_hardware(license_obj, current_fingerprint)