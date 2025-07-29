"""
Unit tests for TikTrue Platform Hardware Fingerprinting System

Tests cover:
- Hardware information collection
- Fingerprint generation
- Fingerprint validation
- Hardware change detection
"""

import unittest
import tempfile
import json
import os
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from security.hardware_fingerprint import HardwareFingerprint, HardwareInfo, HardwareChange


class TestHardwareFingerprint(unittest.TestCase):
    """Test cases for HardwareFingerprint class"""
    
    def setUp(self):
        """Set up test environment"""
        self.hardware_fp = HardwareFingerprint()
    
    def test_hardware_info_collection(self):
        """Test hardware information collection"""
        hardware_info = self.hardware_fp.get_hardware_info()
        
        self.assertIsInstance(hardware_info, HardwareInfo)
        self.assertIsInstance(hardware_info.cpu_info, dict)
        self.assertIsInstance(hardware_info.motherboard_info, dict)
        self.assertIsInstance(hardware_info.disk_info, list)
        self.assertIsInstance(hardware_info.network_interfaces, list)
        self.assertIsInstance(hardware_info.component_hashes, dict)
        self.assertIsNotNone(hardware_info.system_uuid)
    
    def test_fingerprint_generation(self):
        """Test hardware fingerprint generation"""
        fingerprint1 = self.hardware_fp.generate_fingerprint()
        fingerprint2 = self.hardware_fp.generate_fingerprint()
        
        # Fingerprints should be consistent
        self.assertEqual(fingerprint1, fingerprint2)
        self.assertIsInstance(fingerprint1, str)
        self.assertEqual(len(fingerprint1), 64)  # SHA-256 hex length
    
    def test_fingerprint_validation(self):
        """Test hardware fingerprint validation"""
        fingerprint = self.hardware_fp.generate_fingerprint()
        
        # Should validate against itself
        result = self.hardware_fp.validate_current_hardware(fingerprint)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("is_valid", False))
        
        # Should not validate against different fingerprint
        fake_fingerprint = "a" * 64
        result = self.hardware_fp.validate_current_hardware(fake_fingerprint)
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("is_valid", True))
    
    def test_hardware_change_detection(self):
        """Test hardware change detection"""
        # Get current hardware info
        current_info = self.hardware_fp.get_hardware_info()
        
        # Create a copy and modify it to simulate hardware changes
        import copy
        modified_info = copy.deepcopy(current_info)
        
        # Modify CPU info to simulate a change
        if modified_info.cpu_info:
            modified_info.cpu_info["model_name"] = "Modified Test CPU"
            # Update the component hash to reflect the change
            modified_info.component_hashes["cpu_info"] = self.hardware_fp._generate_component_hash("cpu_info", modified_info.cpu_info)
        
        # Detect changes
        changes = self.hardware_fp.detect_hardware_changes(modified_info)
        
        # Verify changes were detected
        self.assertIsInstance(changes, list)
        if modified_info.cpu_info:
            # Should detect at least one change
            self.assertGreater(len(changes), 0)
            # Check if CPU change was detected
            cpu_changes = [c for c in changes if "cpu" in c.subcomponent.lower()]
            self.assertGreater(len(cpu_changes), 0)
    
    @patch('security.hardware_fingerprint.platform.platform', return_value='Test Platform')
    @patch('security.hardware_fingerprint.platform.architecture', return_value=('64bit', ''))
    def test_hardware_summary(self, mock_arch, mock_platform):
        """Test hardware summary generation"""
        summary = self.hardware_fp.get_hardware_summary()
        
        self.assertIsInstance(summary, dict)
        self.assertIn("Platform", summary)
        self.assertIn("Architecture", summary)
        self.assertIn("CPU", summary)
        self.assertIn("Memory", summary)


if __name__ == '__main__':
    unittest.main()