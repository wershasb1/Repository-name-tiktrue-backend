"""
Mock hardware fingerprinting module for testing
"""

import hashlib
import platform
import uuid
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

# Configure logging
logger = logging.getLogger("HardwareFingerprint")


@dataclass
class HardwareInfo:
    """Hardware information structure"""
    cpu_info: Dict[str, str]
    motherboard_info: Dict[str, str]
    disk_info: List[Dict[str, str]]
    network_interfaces: List[Dict[str, str]]
    system_uuid: str
    bios_info: Dict[str, str]
    memory_info: Dict[str, str]
    component_hashes: Dict[str, str]
    collection_timestamp: str
    collection_method: Dict[str, str]


@dataclass
class HardwareChange:
    """Hardware change detection result"""
    component: str
    subcomponent: str
    old_value: str
    new_value: str
    severity: str  # critical, high, medium, low
    timestamp: datetime
    change_type: str  # added, removed, modified


class HardwareFingerprintError(Exception):
    """Custom exception for hardware fingerprinting errors"""
    pass


class HardwareFingerprint:
    """
    Mock hardware fingerprinting system for testing
    """
    
    def __init__(self):
        """Initialize hardware fingerprinting system"""
        self._cached_info = None
        self._cache_timestamp = None
        logger.info("Mock HardwareFingerprint system initialized")
    
    def generate_fingerprint(self) -> str:
        """
        Generate a hardware fingerprint for the current device
        
        Returns:
            Hardware fingerprint as hex string
        """
        # Create a simple fingerprint based on platform info
        system_info = f"{platform.node()}-{platform.system()}-{platform.machine()}"
        try:
            mac = uuid.getnode()
        except:
            mac = 0
            
        fingerprint = f"{system_info}-{mac}"
        result = hashlib.sha256(fingerprint.encode()).hexdigest()
        
        logger.info(f"Generated mock hardware fingerprint: {result[:8]}...")
        return result
    
    def get_hardware_info(self) -> HardwareInfo:
        """
        Get detailed hardware information
        
        Returns:
            Hardware information object
        """
        # Create mock hardware info
        hw_info = HardwareInfo(
            cpu_info={
                "model_name": "Mock CPU",
                "cores": "4",
                "threads": "8",
                "vendor_id": "MockVendor"
            },
            motherboard_info={
                "manufacturer": "Mock Manufacturer",
                "product": "Mock Motherboard",
                "serial_number": "MOCK-SERIAL-123"
            },
            disk_info=[{
                "model": "Mock Disk",
                "size": "1000000000",
                "serial": "MOCK-DISK-123"
            }],
            network_interfaces=[{
                "name": "eth0",
                "mac": "00:11:22:33:44:55"
            }],
            system_uuid="00000000-0000-0000-0000-000000000000",
            bios_info={
                "vendor": "Mock BIOS",
                "version": "1.0"
            },
            memory_info={
                "total": "16GB"
            },
            component_hashes={
                "cpu": "0000000000000000",
                "motherboard": "1111111111111111",
                "disk": "2222222222222222"
            },
            collection_timestamp=datetime.now().isoformat(),
            collection_method={
                "cpu": "mock",
                "motherboard": "mock",
                "disk": "mock"
            }
        )
        
        return hw_info
    
    def validate_current_hardware(self, stored_fingerprint: str) -> bool:
        """
        Validate if current hardware matches stored fingerprint
        
        Args:
            stored_fingerprint: Previously generated fingerprint
            
        Returns:
            True if hardware matches, False otherwise
        """
        current_fingerprint = self.generate_fingerprint()
        return current_fingerprint == stored_fingerprint
    
    def detect_hardware_changes(self) -> List[HardwareChange]:
        """
        Detect hardware changes since last check
        
        Returns:
            List of hardware changes
        """
        # Return empty list for mock implementation
        return []