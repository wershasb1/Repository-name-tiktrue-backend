"""
Unit tests for License Storage Module
Tests secure storage, encryption, and hardware binding
"""

import unittest
import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from license_storage import (
    LicenseStorage, save_license, load_license, 
    is_valid_license_stored, delete_stored_license
)
from security.license_validator import (
    LicenseValidator, LicenseInfo, SubscriptionTier, LicenseStatus
)


class TestLicenseStorage(unittest.TestCase):
    """Test cases for LicenseStorage class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.storage = LicenseStorage(self.temp_dir)
        
        # Create test license info
        self.test_license = LicenseInfo(
            license_key="TIKT-PRO-6M-XYZ789",
            plan=SubscriptionTier.PRO,
            duration_months=6,
            unique_id="XYZ789",
            expires_at=datetime.now() + timedelta(days=180),
            max_clients=20,
            allowed_models=['llama3_1_8b_fp16', 'mistral_7b_int4'],
            allowed_features=['advanced_chat', 'session_save'],
            status=LicenseStatus.VALID,
            hardware_signature="test_hardware_signature",
            created_at=datetime.now() - timedelta(days=1),
            checksum="test_checksum"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_storage_directory_creation(self):
        """Test storage directory creation"""
        # Directory should be created during initialization
        self.assertTrue(Path(self.temp_dir).exists())
        self.assertTrue(Path(self.temp_dir).is_dir())
    
    def test_hardware_signature_generation(self):
        """Test hardware signature generation"""
        signature1 = self.storage._generate_hardware_signature()
        signature2 = self.storage._generate_hardware_signature()
        
        # Should be consistent
        self.assertEqual(signature1, signature2)
        self.assertIsInstance(signature1, str)
        self.assertGreater(len(signature1), 0)
    
    def test_hardware_signature_verification(self):
        """Test hardware signature verification"""
        current_signature = self.storage.get_hardware_signature()
        
        # Same signature should verify
        self.assertTrue(self.storage._verify_hardware_signature(current_signature))
        
        # Different signature should fail
        self.assertFalse(self.storage._verify_hardware_signature("different_signature"))
        
        # Empty signature should pass (no binding)
        self.assertTrue(self.storage._verify_hardware_signature(""))
    
    def test_encryption_and_decryption(self):
        """Test license data encryption and decryption"""
        test_data = {
            "license_key": "TIKT-PRO-6M-XYZ789",
            "plan": "PRO",
            "test_field": "test_value"
        }
        
        # Encrypt data
        encrypted_data = self.storage._encrypt_license_data(test_data)
        self.assertIsInstance(encrypted_data, bytes)
        self.assertGreater(len(encrypted_data), 0)
        
        # Decrypt data
        decrypted_data = self.storage._decrypt_license_data(encrypted_data)
        self.assertEqual(decrypted_data, test_data)
    
    def test_save_and_load_license(self):
        """Test saving and loading license"""
        # Save license
        success = self.storage.save_license_locally(self.test_license)
        self.assertTrue(success)
        
        # Check file exists
        self.assertTrue(self.storage.license_file.exists())
        
        # Load license
        loaded_license = self.storage.load_license_info()
        self.assertIsNotNone(loaded_license)
        
        # Verify loaded data
        self.assertEqual(loaded_license.license_key, self.test_license.license_key)
        self.assertEqual(loaded_license.plan, self.test_license.plan)
        self.assertEqual(loaded_license.max_clients, self.test_license.max_clients)
        self.assertEqual(loaded_license.allowed_models, self.test_license.allowed_models)
        self.assertEqual(loaded_license.allowed_features, self.test_license.allowed_features)
    
    def test_license_validity_check(self):
        """Test license validity checking"""
        # No license stored initially
        self.assertFalse(self.storage.is_license_valid())
        
        # Save valid license
        self.storage.save_license_locally(self.test_license)
        
        # Should be valid now (assuming hardware signature matches)
        with patch.object(self.storage, '_verify_hardware_signature', return_value=True):
            self.assertTrue(self.storage.is_license_valid())
        
        # Test with expired license
        expired_license = LicenseInfo(
            license_key="TIKT-PRO-6M-EXPIRED",
            plan=SubscriptionTier.PRO,
            duration_months=6,
            unique_id="EXPIRED",
            expires_at=datetime.now() - timedelta(days=1),  # Expired
            max_clients=20,
            allowed_models=[],
            allowed_features=[],
            status=LicenseStatus.VALID,
            hardware_signature=self.storage.get_hardware_signature(),
            created_at=datetime.now() - timedelta(days=180),
            checksum="test_checksum"
        )
        
        self.storage.save_license_locally(expired_license)
        self.assertFalse(self.storage.is_license_valid())
    
    def test_license_backup_and_restore(self):
        """Test license backup and restore functionality"""
        # Save original license
        self.storage.save_license_locally(self.test_license)
        
        # Create backup
        backup_success = self.storage.backup_license()
        self.assertTrue(backup_success)
        
        # Verify backup file exists
        backup_file = self.storage.license_file.with_suffix('.bak')
        self.assertTrue(backup_file.exists())
        
        # Modify original license (save different license)
        modified_license = LicenseInfo(
            license_key="TIKT-FREE-1M-MODIFIED",
            plan=SubscriptionTier.FREE,
            duration_months=1,
            unique_id="MODIFIED",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=3,
            allowed_models=[],
            allowed_features=[],
            status=LicenseStatus.VALID,
            hardware_signature=self.storage.get_hardware_signature(),
            created_at=datetime.now(),
            checksum="modified_checksum"
        )
        
        self.storage.save_license_locally(modified_license)
        
        # Verify modified license is loaded
        loaded_license = self.storage.load_license_info()
        self.assertEqual(loaded_license.license_key, "TIKT-FREE-1M-MODIFIED")
        
        # Restore from backup
        restore_success = self.storage.restore_license_from_backup()
        self.assertTrue(restore_success)
        
        # Verify original license is restored
        restored_license = self.storage.load_license_info()
        self.assertEqual(restored_license.license_key, self.test_license.license_key)
        self.assertEqual(restored_license.plan, self.test_license.plan)
    
    def test_license_deletion(self):
        """Test license deletion"""
        # Save license
        self.storage.save_license_locally(self.test_license)
        self.assertTrue(self.storage.license_file.exists())
        
        # Delete license
        delete_success = self.storage.delete_license()
        self.assertTrue(delete_success)
        
        # Verify file is deleted
        self.assertFalse(self.storage.license_file.exists())
        
        # Should not be able to load license
        loaded_license = self.storage.load_license_info()
        self.assertIsNone(loaded_license)
    
    def test_storage_info(self):
        """Test storage information retrieval"""
        # Get info when no license exists
        info = self.storage.get_license_storage_info()
        self.assertFalse(info['license_file_exists'])
        self.assertEqual(info['license_file_size'], 0)
        self.assertFalse(info['backup_exists'])
        
        # Save license and get info
        self.storage.save_license_locally(self.test_license)
        info = self.storage.get_license_storage_info()
        
        self.assertTrue(info['license_file_exists'])
        self.assertGreater(info['license_file_size'], 0)
        self.assertIn('license_file_modified', info)
        self.assertIn('hardware_signature', info)
        self.assertEqual(info['storage_directory'], str(self.storage.storage_dir))
    
    def test_error_handling(self):
        """Test error handling in various scenarios"""
        # Test loading non-existent license
        empty_storage = LicenseStorage(tempfile.mkdtemp())
        loaded_license = empty_storage.load_license_info()
        self.assertIsNone(loaded_license)
        
        # Test backup when no license exists
        backup_success = empty_storage.backup_license()
        self.assertFalse(backup_success)
        
        # Test restore when no backup exists
        restore_success = empty_storage.restore_license_from_backup()
        self.assertFalse(restore_success)
        
        # Clean up
        shutil.rmtree(empty_storage.storage_dir, ignore_errors=True)
    
    @patch('license_storage.platform.system')
    def test_storage_directory_selection(self, mock_platform):
        """Test storage directory selection for different platforms"""
        # Test Windows
        mock_platform.return_value = "Windows"
        with patch.dict(os.environ, {'APPDATA': 'C:\\Users\\Test\\AppData\\Roaming'}):
            storage = LicenseStorage()
            expected_path = Path("C:\\Users\\Test\\AppData\\Roaming\\TikTrue\\licenses")
            self.assertEqual(storage.storage_dir, expected_path)
        
        # Test macOS
        mock_platform.return_value = "Darwin"
        with patch('license_storage.Path.home', return_value=Path('/Users/test')):
            storage = LicenseStorage()
            expected_path = Path("/Users/test/Library/Application Support/TikTrue/licenses")
            self.assertEqual(storage.storage_dir, expected_path)
        
        # Test Linux
        mock_platform.return_value = "Linux"
        with patch('license_storage.Path.home', return_value=Path('/home/test')):
            storage = LicenseStorage()
            expected_path = Path("/home/test/.config/tiktrue/licenses")
            self.assertEqual(storage.storage_dir, expected_path)
    
    def test_hardware_signature_consistency(self):
        """Test hardware signature consistency across instances"""
        storage1 = LicenseStorage(tempfile.mkdtemp())
        storage2 = LicenseStorage(tempfile.mkdtemp())
        
        # Hardware signatures should be the same
        self.assertEqual(storage1.get_hardware_signature(), storage2.get_hardware_signature())
        
        # Clean up
        shutil.rmtree(storage1.storage_dir, ignore_errors=True)
        shutil.rmtree(storage2.storage_dir, ignore_errors=True)


class TestLicenseStorageConvenienceFunctions(unittest.TestCase):
    """Test convenience functions for license storage"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test license
        self.test_license = LicenseInfo(
            license_key="TIKT-PRO-6M-XYZ789",
            plan=SubscriptionTier.PRO,
            duration_months=6,
            unique_id="XYZ789",
            expires_at=datetime.now() + timedelta(days=180),
            max_clients=20,
            allowed_models=['llama3_1_8b_fp16'],
            allowed_features=['advanced_chat'],
            status=LicenseStatus.VALID,
            hardware_signature="test_signature",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_license_convenience_function(self):
        """Test save_license convenience function"""
        success = save_license(self.test_license, self.temp_dir)
        self.assertTrue(success)
        
        # Verify file exists
        license_file = Path(self.temp_dir) / "license.enc"
        self.assertTrue(license_file.exists())
    
    def test_load_license_convenience_function(self):
        """Test load_license convenience function"""
        # Save license first
        save_license(self.test_license, self.temp_dir)
        
        # Load using convenience function
        loaded_license = load_license(self.temp_dir)
        self.assertIsNotNone(loaded_license)
        self.assertEqual(loaded_license.license_key, self.test_license.license_key)
    
    def test_is_valid_license_stored_convenience_function(self):
        """Test is_valid_license_stored convenience function"""
        # No license initially
        self.assertFalse(is_valid_license_stored(self.temp_dir))
        
        # Save valid license
        save_license(self.test_license, self.temp_dir)
        
        # Should be valid now
        with patch('license_storage.LicenseStorage._verify_hardware_signature', return_value=True):
            self.assertTrue(is_valid_license_stored(self.temp_dir))
    
    def test_delete_stored_license_convenience_function(self):
        """Test delete_stored_license convenience function"""
        # Save license first
        save_license(self.test_license, self.temp_dir)
        
        # Verify it exists
        self.assertTrue(is_valid_license_stored(self.temp_dir))
        
        # Delete using convenience function
        success = delete_stored_license(self.temp_dir)
        self.assertTrue(success)
        
        # Verify it's gone
        self.assertFalse(is_valid_license_stored(self.temp_dir))


class TestLicenseStorageIntegration(unittest.TestCase):
    """Integration tests for license storage with license validator"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.validator = LicenseValidator()
        self.storage = LicenseStorage(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_license_workflow(self):
        """Test complete license workflow from validation to storage"""
        # Create license using validator
        test_license_key = "TIKT-PRO-6M-XYZ789"
        license_info = self.validator.extract_license_info(test_license_key)
        
        # Save license
        save_success = self.storage.save_license_locally(license_info)
        self.assertTrue(save_success)
        
        # Load and verify
        loaded_license = self.storage.load_license_info()
        self.assertIsNotNone(loaded_license)
        self.assertEqual(loaded_license.license_key, test_license_key)
        self.assertEqual(loaded_license.plan, SubscriptionTier.PRO)
        
        # Test validation of loaded license
        with patch.object(self.storage, '_verify_hardware_signature', return_value=True):
            validated_license = self.validator.validate_license_key(loaded_license.license_key)
            # Note: This would need the validator to be enhanced to work with stored licenses
    
    def test_multiple_license_storage_instances(self):
        """Test multiple storage instances accessing same directory"""
        # Create license with first instance
        storage1 = LicenseStorage(self.temp_dir)
        test_license = self.validator.extract_license_info("TIKT-PRO-6M-XYZ789")
        
        storage1.save_license_locally(test_license)
        
        # Access with second instance
        storage2 = LicenseStorage(self.temp_dir)
        loaded_license = storage2.load_license_info()
        
        self.assertIsNotNone(loaded_license)
        self.assertEqual(loaded_license.license_key, test_license.license_key)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)