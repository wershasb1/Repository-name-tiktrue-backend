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
        self.assertIsNotNone(hardware_info.cpu_id)
        self.assertIsNotNone(hardware_info.mac_address)
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
        self.assertTrue(self.hardware_fp.validate_current_hardware(fingerprint))
        
        # Should not validate against different fingerprint
        fake_fingerprint = "a" * 64
        self.assertFalse(self.hardware_fp.validate_current_hardware(fake_fingerprint))
    
    def test_hardware_change_detection(self):
        """Test hardware change detection"""
        current_fingerprint = self.hardware_fp.generate_fingerprint()
        fake_old_fingerprint = "b" * 64
        
        changes = self.hardware_fp.detect_hardware_changes(fake_old_fingerprint)
        
        self.assertIsInstance(changes, list)
        if changes:  # Changes detected
            self.assertIsInstance(changes[0], HardwareChange)
    
    def test_hardware_summary(self):
        """Test hardware summary generation"""
        summary = self.hardware_fp.get_hardware_summary()
        
        self.assertIsInstance(summary, dict)
        self.assertIn("Platform", summary)
        self.assertIn("Architecture", summary)


if __name__ == '__main__':
    unittest.main()