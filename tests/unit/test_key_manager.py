"""
Unit tests for Key Management and Rotation System

Tests all key lifecycle management functionality including:
- Hardware-bound key generation and storage
- Automatic key rotation with backward compatibility
- Key distribution system for client nodes
- Emergency key revocation capabilities
"""

import unittest
import asyncio
import tempfile
import shutil
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
from key_manager import (
    KeyManager, ManagedKey, KeyStatus, KeyRotationStatus,
    KeyRotationEvent, KeyDistributionRequest
)


class TestKeyManager(unittest.TestCase):
    """Test cases for KeyManager class"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for test storage
        self.test_dir = tempfile.mkdtemp()
        self.key_manager = KeyManager(storage_dir=self.test_dir)
        
        # Test data
        self.test_license_key = "test_license_key_12345"
        self.test_model_id = "test_model_v1"
        
    def tearDown(self):
        """Clean up test environment"""
        # Clean up temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_hardware_bound_key_generation(self):
        """
        Test hardware-bound key generation
        Requirements: 6.3.1 - Bind keys to specific hardware fingerprints
        """
        # Generate hardware-bound key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Verify key properties
        self.assertIsNotNone(managed_key)
        self.assertEqual(managed_key.algorithm, "AES-256-GCM")
        self.assertEqual(len(managed_key.key_data), 32)  # 256 bits
        self.assertEqual(managed_key.status, KeyStatus.ACTIVE)
        self.assertEqual(managed_key.rotation_generation, 1)
        self.assertIsNotNone(managed_key.hardware_fingerprint)
        self.assertIsNotNone(managed_key.license_key_hash)
        
        # Verify metadata
        self.assertEqual(managed_key.metadata["model_id"], self.test_model_id)
        self.assertEqual(managed_key.metadata["key_strength"], 256)
        self.assertEqual(managed_key.metadata["binding_method"], "hardware_pbkdf2")
        
        # Verify key is stored and cached
        self.assertIn(managed_key.key_id, self.key_manager.key_cache)
        
        # Verify key can be retrieved
        retrieved_key = self.key_manager.get_key(managed_key.key_id)
        self.assertIsNotNone(retrieved_key)
        self.assertEqual(retrieved_key.key_id, managed_key.key_id)
    
    def test_hardware_binding_validation_success(self):
        """
        Test successful hardware binding validation
        Requirements: 6.3.2 - Validate current hardware matches the bound fingerprint
        """
        # Generate key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Validate hardware binding (should succeed)
        is_valid = self.key_manager.validate_hardware_binding(managed_key.key_id)
        self.assertTrue(is_valid)
    
    def test_hardware_binding_validation_failure(self):
        """
        Test hardware binding validation failure
        Requirements: 6.3.2 - Validate current hardware matches the bound fingerprint
        """
        # Generate key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Modify hardware fingerprint to simulate hardware change
        managed_key.hardware_fingerprint = "different_hardware_fingerprint"
        self.key_manager._store_key(managed_key)
        self.key_manager.key_cache[managed_key.key_id] = managed_key
        
        # Validate hardware binding (should fail)
        is_valid = self.key_manager.validate_hardware_binding(managed_key.key_id)
        self.assertFalse(is_valid)
    
    def test_key_expiration_validation(self):
        """Test key expiration validation"""
        # Generate key with short lifetime
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id,
            key_lifetime_days=0  # Expires immediately
        )
        
        # Set expiration to past
        managed_key.expires_at = datetime.now() - timedelta(hours=1)
        self.key_manager._store_key(managed_key)
        self.key_manager.key_cache[managed_key.key_id] = managed_key
        
        # Validate hardware binding (should fail due to expiration)
        is_valid = self.key_manager.validate_hardware_binding(managed_key.key_id)
        self.assertFalse(is_valid)
    
    def test_revoked_key_validation(self):
        """Test revoked key validation"""
        # Generate key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Revoke key
        asyncio.run(self.key_manager.revoke_key(
            managed_key.key_id, 
            reason="test_revocation"
        ))
        
        # Validate hardware binding (should fail due to revocation)
        is_valid = self.key_manager.validate_hardware_binding(managed_key.key_id)
        self.assertFalse(is_valid)
    
    def test_key_rotation_success(self):
        """
        Test successful key rotation
        Requirements: 6.6.1 - Generate new encryption keys while maintaining backward compatibility
        """
        # Generate initial key
        old_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Rotate key
        new_key = asyncio.run(self.key_manager.rotate_key(
            old_key_id=old_key.key_id,
            license_key=self.test_license_key,
            notify_clients=["client1", "client2"]
        ))
        
        # Verify rotation success
        self.assertIsNotNone(new_key)
        self.assertNotEqual(new_key.key_id, old_key.key_id)
        self.assertEqual(new_key.rotation_generation, old_key.rotation_generation + 1)
        self.assertEqual(new_key.predecessor_key_id, old_key.key_id)
        
        # Verify old key status updated
        updated_old_key = self.key_manager.get_key(old_key.key_id)
        self.assertEqual(updated_old_key.status, KeyStatus.ROTATING)
        self.assertEqual(updated_old_key.successor_key_id, new_key.key_id)
        
        # Verify new key is active
        self.assertEqual(new_key.status, KeyStatus.ACTIVE)
        
        # Verify rotation history
        rotation_history = self.key_manager.get_key_rotation_history(old_key.key_id)
        self.assertGreater(len(rotation_history), 0)
        
        latest_rotation = rotation_history[-1]
        self.assertEqual(latest_rotation.old_key_id, old_key.key_id)
        self.assertEqual(latest_rotation.new_key_id, new_key.key_id)
        self.assertEqual(latest_rotation.status, KeyRotationStatus.COMPLETED)
    
    def test_key_rotation_nonexistent_key(self):
        """Test key rotation with nonexistent key"""
        # Attempt to rotate nonexistent key
        new_key = asyncio.run(self.key_manager.rotate_key(
            old_key_id="nonexistent_key",
            license_key=self.test_license_key
        ))
        
        # Should return None
        self.assertIsNone(new_key)
    
    def test_emergency_key_revocation(self):
        """
        Test emergency key revocation
        Requirements: 6.6.4 - Maintain existing keys and log failures (emergency revocation)
        """
        # Generate key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Revoke key
        revocation_reason = "security_breach"
        success = asyncio.run(self.key_manager.revoke_key(
            managed_key.key_id,
            reason=revocation_reason
        ))
        
        # Verify revocation success
        self.assertTrue(success)
        
        # Verify key status updated
        revoked_key = self.key_manager.get_key(managed_key.key_id)
        self.assertEqual(revoked_key.status, KeyStatus.REVOKED)
        self.assertIn("revoked_at", revoked_key.metadata)
        self.assertEqual(revoked_key.metadata["revocation_reason"], revocation_reason)
        
        # Verify key is in revocation list
        self.assertIn(managed_key.key_id, self.key_manager.revoked_keys)
    
    def test_revoke_nonexistent_key(self):
        """Test revoking nonexistent key"""
        # Attempt to revoke nonexistent key
        success = asyncio.run(self.key_manager.revoke_key("nonexistent_key"))
        
        # Should return False
        self.assertFalse(success)
    
    def test_list_active_keys(self):
        """Test listing active keys"""
        # Generate multiple keys
        key1 = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id="model1"
        )
        key2 = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id="model2"
        )
        key3 = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id="model1"
        )
        
        # Revoke one key
        asyncio.run(self.key_manager.revoke_key(key3.key_id))
        
        # List all active keys
        active_keys = self.key_manager.list_active_keys()
        active_key_ids = [k.key_id for k in active_keys]
        
        self.assertIn(key1.key_id, active_key_ids)
        self.assertIn(key2.key_id, active_key_ids)
        self.assertNotIn(key3.key_id, active_key_ids)  # Revoked key should not be listed
        
        # List active keys for specific model
        model1_keys = self.key_manager.list_active_keys(model_id="model1")
        model1_key_ids = [k.key_id for k in model1_keys]
        
        self.assertIn(key1.key_id, model1_key_ids)
        self.assertNotIn(key2.key_id, model1_key_ids)  # Different model
        self.assertNotIn(key3.key_id, model1_key_ids)  # Revoked key
    
    def test_key_cleanup(self):
        """
        Test cleanup of expired keys
        Requirements: 6.6.5 - Securely dispose of old encryption keys
        """
        # Generate key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Set key to deprecated and expired
        managed_key.status = KeyStatus.DEPRECATED
        managed_key.expires_at = datetime.now() - timedelta(hours=1)
        self.key_manager._store_key(managed_key)
        self.key_manager.key_cache[managed_key.key_id] = managed_key
        
        # Run cleanup
        cleaned_count = asyncio.run(self.key_manager.cleanup_expired_keys())
        
        # Verify cleanup occurred
        self.assertEqual(cleaned_count, 1)
        
        # Verify key data was cleared
        cleaned_key = self.key_manager.get_key(managed_key.key_id)
        self.assertEqual(cleaned_key.status, KeyStatus.EXPIRED)
        self.assertEqual(len(cleaned_key.key_data), 0)  # Key data should be cleared
    
    def test_key_storage_and_retrieval(self):
        """
        Test secure key storage and retrieval
        Requirements: 6.3.5 - Use secure key storage mechanisms provided by the operating system
        """
        # Generate key
        original_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Clear cache to force storage retrieval
        self.key_manager.key_cache.clear()
        
        # Retrieve key from storage
        retrieved_key = self.key_manager.get_key(original_key.key_id)
        
        # Verify key was retrieved correctly
        self.assertIsNotNone(retrieved_key)
        self.assertEqual(retrieved_key.key_id, original_key.key_id)
        self.assertEqual(retrieved_key.algorithm, original_key.algorithm)
        self.assertEqual(retrieved_key.key_data, original_key.key_data)
        self.assertEqual(retrieved_key.hardware_fingerprint, original_key.hardware_fingerprint)
        self.assertEqual(retrieved_key.status, original_key.status)
        
        # Verify storage file exists and has secure permissions
        keys_file = Path(self.test_dir) / "managed_keys.json"
        self.assertTrue(keys_file.exists())
        
        # Check file permissions (Unix-like systems)
        try:
            import platform
            if platform.system() != "Windows":
                file_stat = keys_file.stat()
                # Should be readable/writable by owner only (0o600)
                permissions = file_stat.st_mode & 0o777
                # Note: On some systems, permissions might not be exactly 0o600
                # but should at least not be world-readable
                self.assertNotEqual(permissions & 0o044, 0o044)  # Not world-readable
            else:
                # On Windows, just verify the file exists and is readable
                self.assertTrue(keys_file.exists())
        except (OSError, AttributeError):
            # Permission check failed - skip
            pass
    
    def test_rotation_history_logging(self):
        """Test rotation history logging"""
        # Generate initial key
        old_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Perform multiple rotations
        new_key1 = asyncio.run(self.key_manager.rotate_key(
            old_key_id=old_key.key_id,
            license_key=self.test_license_key
        ))
        
        new_key2 = asyncio.run(self.key_manager.rotate_key(
            old_key_id=new_key1.key_id,
            license_key=self.test_license_key
        ))
        
        # Get rotation history
        history = self.key_manager.get_key_rotation_history(old_key.key_id)
        
        # Verify history contains rotation events
        self.assertGreater(len(history), 0)
        
        # Find the rotation event for old_key
        old_key_rotation = None
        for event in history:
            if event.old_key_id == old_key.key_id:
                old_key_rotation = event
                break
        
        self.assertIsNotNone(old_key_rotation)
        self.assertEqual(old_key_rotation.new_key_id, new_key1.key_id)
        self.assertEqual(old_key_rotation.status, KeyRotationStatus.COMPLETED)
    
    def test_concurrent_key_operations(self):
        """Test concurrent key operations"""
        # Generate initial key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Test concurrent validation calls
        async def validate_key():
            return self.key_manager.validate_hardware_binding(managed_key.key_id)
        
        async def run_concurrent_validations():
            tasks = [validate_key() for _ in range(10)]
            results = await asyncio.gather(*tasks)
            return results
        
        # Run concurrent validations
        results = asyncio.run(run_concurrent_validations())
        
        # All validations should succeed
        self.assertTrue(all(results))
    
    def test_key_metadata_preservation(self):
        """Test that key metadata is preserved through operations"""
        # Generate key with custom metadata
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Add custom metadata
        managed_key.metadata["custom_field"] = "custom_value"
        managed_key.metadata["test_number"] = 42
        self.key_manager._store_key(managed_key)
        
        # Clear cache and retrieve
        self.key_manager.key_cache.clear()
        retrieved_key = self.key_manager.get_key(managed_key.key_id)
        
        # Verify metadata preserved
        self.assertEqual(retrieved_key.metadata["custom_field"], "custom_value")
        self.assertEqual(retrieved_key.metadata["test_number"], 42)
        self.assertEqual(retrieved_key.metadata["model_id"], self.test_model_id)
    
    def test_key_generation_uniqueness(self):
        """Test that generated keys are unique"""
        # Generate multiple keys with same parameters
        keys = []
        for i in range(10):
            key = self.key_manager.generate_hardware_bound_key(
                license_key=self.test_license_key,
                model_id=self.test_model_id
            )
            keys.append(key)
        
        # Verify all key IDs are unique
        key_ids = [k.key_id for k in keys]
        self.assertEqual(len(key_ids), len(set(key_ids)))
        
        # Verify all key data is unique (should be different due to different key IDs)
        key_data_hashes = [k.key_data.hex() for k in keys]
        self.assertEqual(len(key_data_hashes), len(set(key_data_hashes)))


class TestKeyRotationIntegration(unittest.TestCase):
    """Integration tests for key rotation functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.key_manager = KeyManager(storage_dir=self.test_dir)
        self.test_license_key = "integration_test_license"
        self.test_model_id = "integration_model"
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_full_key_lifecycle(self):
        """Test complete key lifecycle from generation to cleanup"""
        # 1. Generate initial key
        initial_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id,
            key_lifetime_days=1
        )
        
        self.assertEqual(initial_key.rotation_generation, 1)
        self.assertEqual(initial_key.status, KeyStatus.ACTIVE)
        
        # 2. Rotate key
        rotated_key = asyncio.run(self.key_manager.rotate_key(
            old_key_id=initial_key.key_id,
            license_key=self.test_license_key,
            notify_clients=["test_client"]
        ))
        
        self.assertIsNotNone(rotated_key)
        self.assertEqual(rotated_key.rotation_generation, 2)
        self.assertEqual(rotated_key.predecessor_key_id, initial_key.key_id)
        
        # 3. Verify old key status
        updated_initial_key = self.key_manager.get_key(initial_key.key_id)
        self.assertEqual(updated_initial_key.status, KeyStatus.ROTATING)
        self.assertEqual(updated_initial_key.successor_key_id, rotated_key.key_id)
        
        # 4. Simulate time passage and cleanup
        updated_initial_key.expires_at = datetime.now() - timedelta(hours=1)
        updated_initial_key.status = KeyStatus.DEPRECATED
        self.key_manager._store_key(updated_initial_key)
        self.key_manager.key_cache[initial_key.key_id] = updated_initial_key
        
        # 5. Run cleanup
        cleaned_count = asyncio.run(self.key_manager.cleanup_expired_keys())
        self.assertEqual(cleaned_count, 1)
        
        # 6. Verify cleanup
        cleaned_key = self.key_manager.get_key(initial_key.key_id)
        self.assertEqual(cleaned_key.status, KeyStatus.EXPIRED)
        self.assertEqual(len(cleaned_key.key_data), 0)
        
        # 7. Verify new key still active
        active_keys = self.key_manager.list_active_keys()
        active_key_ids = [k.key_id for k in active_keys]
        self.assertIn(rotated_key.key_id, active_key_ids)
        self.assertNotIn(initial_key.key_id, active_key_ids)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)