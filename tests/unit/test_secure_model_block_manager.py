"""
Integration tests for secure model block management with key rotation
Tests the integration between KeyManager and ModelEncryption systems
"""

import unittest
import asyncio
import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime, timedelta

from key_manager import KeyManager, KeyStatus
from models.model_encryption import ModelEncryption, EncryptedBlock


class TestSecureModelBlockManager(unittest.TestCase):
    """Integration tests for secure model block management"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary directories
        self.test_dir = tempfile.mkdtemp()
        self.key_storage_dir = Path(self.test_dir) / "keys"
        self.encryption_storage_dir = Path(self.test_dir) / "encryption"
        
        # Initialize systems
        self.key_manager = KeyManager(storage_dir=str(self.key_storage_dir))
        self.model_encryption = ModelEncryption(storage_dir=str(self.encryption_storage_dir))
        
        # Test data
        self.test_license_key = "integration_license_key_12345"
        self.test_model_id = "integration_model_v1"
        self.test_block_data = b"This is test model block data for encryption testing" * 100
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_hardware_bound_encryption_key_integration(self):
        """
        Test integration between hardware-bound key generation and model encryption
        Requirements: 6.3.1, 6.3.2 - Hardware-bound keys with model encryption
        """
        # Generate hardware-bound key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Validate hardware binding
        self.assertTrue(self.key_manager.validate_hardware_binding(managed_key.key_id))
        
        # Use the key for model block encryption
        encrypted_block = self.models.model_encryption.encrypt_model_block(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            key_id=managed_key.key_id
        )
        
        # Verify encryption succeeded
        self.assertIsNotNone(encrypted_block)
        self.assertEqual(encrypted_block.key_id, managed_key.key_id)
        self.assertEqual(encrypted_block.model_id, self.test_model_id)
        self.assertEqual(encrypted_block.original_size, len(self.test_block_data))
        
        # Decrypt and verify
        decrypted_data = self.models.model_encryption.decrypt_model_block(encrypted_block)
        self.assertEqual(decrypted_data, self.test_block_data)
    
    def test_key_rotation_with_model_blocks(self):
        """
        Test key rotation with existing encrypted model blocks
        Requirements: 6.6.1, 6.6.2 - Key rotation with backward compatibility
        """
        # Generate initial key and encrypt blocks
        initial_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Create multiple encrypted blocks with initial key
        encrypted_blocks = []
        for i in range(3):
            block_data = f"Block {i} data: {self.test_block_data.decode()}".encode()
            encrypted_block = self.models.model_encryption.encrypt_model_block(
                model_id=self.test_model_id,
                block_data=block_data,
                block_index=i,
                key_id=initial_key.key_id
            )
            encrypted_blocks.append(encrypted_block)
        
        # Verify all blocks can be decrypted with initial key
        for i, block in enumerate(encrypted_blocks):
            decrypted_data = self.models.model_encryption.decrypt_model_block(block)
            expected_data = f"Block {i} data: {self.test_block_data.decode()}".encode()
            self.assertEqual(decrypted_data, expected_data)
        
        # Rotate key
        new_key = asyncio.run(self.key_manager.rotate_key(
            old_key_id=initial_key.key_id,
            license_key=self.test_license_key
        ))
        
        self.assertIsNotNone(new_key)
        
        # Verify old blocks can still be decrypted (backward compatibility)
        for i, block in enumerate(encrypted_blocks):
            decrypted_data = self.models.model_encryption.decrypt_model_block(block)
            expected_data = f"Block {i} data: {self.test_block_data.decode()}".encode()
            self.assertEqual(decrypted_data, expected_data)
        
        # Create new blocks with new key
        new_block_data = b"New block data after rotation"
        new_encrypted_block = self.models.model_encryption.encrypt_model_block(
            model_id=self.test_model_id,
            block_data=new_block_data,
            block_index=3,
            key_id=new_key.key_id
        )
        
        # Verify new block can be decrypted
        decrypted_new_data = self.models.model_encryption.decrypt_model_block(new_encrypted_block)
        self.assertEqual(decrypted_new_data, new_block_data)
    
    def test_revoked_key_encryption_failure(self):
        """
        Test that revoked keys cannot be used for encryption/decryption
        Requirements: 6.6.4 - Emergency key revocation
        """
        # Generate key and encrypt block
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        encrypted_block = self.models.model_encryption.encrypt_model_block(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            key_id=managed_key.key_id
        )
        
        # Verify encryption and decryption work initially
        decrypted_data = self.models.model_encryption.decrypt_model_block(encrypted_block)
        self.assertEqual(decrypted_data, self.test_block_data)
        
        # Revoke the key
        revocation_success = asyncio.run(self.key_manager.revoke_key(
            managed_key.key_id,
            reason="test_revocation"
        ))
        self.assertTrue(revocation_success)
        
        # Verify hardware binding validation fails for revoked key
        self.assertFalse(self.key_manager.validate_hardware_binding(managed_key.key_id))
        
        # Attempt to encrypt new block with revoked key should fail
        with self.assertRaises(ValueError):
            self.models.model_encryption.encrypt_model_block(
                model_id=self.test_model_id,
                block_data=b"New data with revoked key",
                block_index=1,
                key_id=managed_key.key_id
            )
    
    def test_hardware_fingerprint_mismatch_protection(self):
        """
        Test protection against hardware fingerprint mismatches
        Requirements: 6.3.2 - Validate current hardware matches bound fingerprint
        """
        # Generate hardware-bound key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Encrypt block
        encrypted_block = self.models.model_encryption.encrypt_model_block(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            key_id=managed_key.key_id
        )
        
        # Simulate hardware change by modifying fingerprint
        original_fingerprint = managed_key.hardware_fingerprint
        managed_key.hardware_fingerprint = "different_hardware_fingerprint"
        self.key_manager._store_key(managed_key)
        self.key_manager.key_cache[managed_key.key_id] = managed_key
        
        # Verify hardware binding validation fails
        self.assertFalse(self.key_manager.validate_hardware_binding(managed_key.key_id))
        
        # Restore original fingerprint
        managed_key.hardware_fingerprint = original_fingerprint
        self.key_manager._store_key(managed_key)
        self.key_manager.key_cache[managed_key.key_id] = managed_key
        
        # Verify validation succeeds again
        self.assertTrue(self.key_manager.validate_hardware_binding(managed_key.key_id))
    
    def test_key_expiration_handling(self):
        """
        Test handling of expired keys
        Requirements: 6.6.5 - Secure disposal of old encryption keys
        """
        # Generate key with short lifetime
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id,
            key_lifetime_days=1
        )
        
        # Encrypt block
        encrypted_block = self.models.model_encryption.encrypt_model_block(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            key_id=managed_key.key_id
        )
        
        # Manually expire the key
        managed_key.expires_at = datetime.now() - timedelta(hours=1)
        self.key_manager._store_key(managed_key)
        self.key_manager.key_cache[managed_key.key_id] = managed_key
        
        # Verify hardware binding validation fails for expired key
        self.assertFalse(self.key_manager.validate_hardware_binding(managed_key.key_id))
        
        # Set key to deprecated for cleanup
        managed_key.status = KeyStatus.DEPRECATED
        self.key_manager._store_key(managed_key)
        self.key_manager.key_cache[managed_key.key_id] = managed_key
        
        # Run cleanup
        cleaned_count = asyncio.run(self.key_manager.cleanup_expired_keys())
        self.assertEqual(cleaned_count, 1)
        
        # Verify key data was securely disposed
        cleaned_key = self.key_manager.get_key(managed_key.key_id)
        self.assertEqual(cleaned_key.status, KeyStatus.EXPIRED)
        self.assertEqual(len(cleaned_key.key_data), 0)
    
    def test_multiple_model_key_management(self):
        """
        Test key management for multiple models
        """
        models = ["model_a", "model_b", "model_c"]
        model_keys = {}
        
        # Generate keys for multiple models
        for model_id in models:
            key = self.key_manager.generate_hardware_bound_key(
                license_key=self.test_license_key,
                model_id=model_id
            )
            model_keys[model_id] = key
        
        # Verify each model has its own key
        self.assertEqual(len(model_keys), 3)
        key_ids = [key.key_id for key in model_keys.values()]
        self.assertEqual(len(key_ids), len(set(key_ids)))  # All unique
        
        # Test model-specific key listing
        for model_id in models:
            model_specific_keys = self.key_manager.list_active_keys(model_id=model_id)
            self.assertEqual(len(model_specific_keys), 1)
            self.assertEqual(model_specific_keys[0].metadata["model_id"], model_id)
        
        # Encrypt blocks for each model
        for model_id, key in model_keys.items():
            block_data = f"Data for {model_id}".encode()
            encrypted_block = self.models.model_encryption.encrypt_model_block(
                model_id=model_id,
                block_data=block_data,
                block_index=0,
                key_id=key.key_id
            )
            
            # Verify decryption
            decrypted_data = self.models.model_encryption.decrypt_model_block(encrypted_block)
            self.assertEqual(decrypted_data, block_data)
    
    def test_key_rotation_chain(self):
        """
        Test multiple key rotations forming a chain
        Requirements: 6.6.1 - Maintain backward compatibility through rotation chain
        """
        # Generate initial key
        key_gen1 = self.key_manager.generate_hardware_bound_key(
            license_key=self.test_license_key,
            model_id=self.test_model_id
        )
        
        # Rotate key twice
        key_gen2 = asyncio.run(self.key_manager.rotate_key(
            old_key_id=key_gen1.key_id,
            license_key=self.test_license_key
        ))
        
        key_gen3 = asyncio.run(self.key_manager.rotate_key(
            old_key_id=key_gen2.key_id,
            license_key=self.test_license_key
        ))
        
        # Verify rotation chain
        self.assertEqual(key_gen1.rotation_generation, 1)
        self.assertEqual(key_gen2.rotation_generation, 2)
        self.assertEqual(key_gen3.rotation_generation, 3)
        
        self.assertEqual(key_gen2.predecessor_key_id, key_gen1.key_id)
        self.assertEqual(key_gen3.predecessor_key_id, key_gen2.key_id)
        
        self.assertEqual(key_gen1.successor_key_id, key_gen2.key_id)
        self.assertEqual(key_gen2.successor_key_id, key_gen3.key_id)
        
        # Verify rotation history
        history = self.key_manager.get_key_rotation_history(key_gen1.key_id)
        self.assertGreaterEqual(len(history), 1)
        
        # Create blocks with different generation keys
        blocks = []
        for i, key in enumerate([key_gen1, key_gen2, key_gen3]):
            if key.status in [KeyStatus.ACTIVE, KeyStatus.ROTATING]:
                block_data = f"Generation {i+1} block data".encode()
                encrypted_block = self.models.model_encryption.encrypt_model_block(
                    model_id=self.test_model_id,
                    block_data=block_data,
                    block_index=i,
                    key_id=key.key_id
                )
                blocks.append((encrypted_block, block_data))
        
        # Verify all blocks can be decrypted (backward compatibility)
        for encrypted_block, original_data in blocks:
            decrypted_data = self.models.model_encryption.decrypt_model_block(encrypted_block)
            self.assertEqual(decrypted_data, original_data)


if __name__ == '__main__':
    unittest.main(verbosity=2)