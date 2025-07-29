"""
Standalone integration tests for secure model block management
Tests the key management system independently with direct encryption/decryption
"""

import unittest
import asyncio
import tempfile
import shutil
import secrets
from pathlib import Path
from datetime import datetime, timedelta

from key_manager import KeyManager, KeyStatus
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import hashlib


class SecureModelBlockManager:
    """
    Integrated secure model block manager that combines KeyManager with direct encryption
    """
    
    def __init__(self, storage_dir: str):
        self.key_manager = KeyManager(storage_dir=storage_dir)
        self.GCM_NONCE_SIZE = 12
    
    def encrypt_block_with_managed_key(self, model_id: str, block_data: bytes, 
                                     block_index: int, license_key: str) -> dict:
        """
        Encrypt a block using a managed hardware-bound key
        
        Returns:
            Dictionary with encrypted block data and metadata
        """
        # Generate or get hardware-bound key
        managed_key = self.key_manager.generate_hardware_bound_key(
            license_key=license_key,
            model_id=model_id
        )
        
        # Validate hardware binding
        if not self.key_manager.validate_hardware_binding(managed_key.key_id):
            raise ValueError(f"Hardware binding validation failed for key: {managed_key.key_id}")
        
        # Generate nonce
        nonce = secrets.token_bytes(self.GCM_NONCE_SIZE)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(managed_key.key_data),
            modes.GCM(nonce),
            backend=default_backend()
        )
        
        # Encrypt data
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(block_data) + encryptor.finalize()
        tag = encryptor.tag
        
        # Calculate checksum
        checksum = hashlib.sha256(block_data).hexdigest()
        
        return {
            'block_id': f"{model_id}_block_{block_index}_{secrets.token_hex(4)}",
            'model_id': model_id,
            'block_index': block_index,
            'encrypted_data': encrypted_data,
            'nonce': nonce,
            'tag': tag,
            'key_id': managed_key.key_id,
            'original_size': len(block_data),
            'encrypted_size': len(encrypted_data),
            'checksum': checksum,
            'created_at': datetime.now()
        }
    
    def decrypt_block_with_managed_key(self, encrypted_block: dict) -> bytes:
        """
        Decrypt a block using a managed key
        
        Args:
            encrypted_block: Dictionary with encrypted block data
            
        Returns:
            Decrypted block data
        """
        # Get managed key
        managed_key = self.key_manager.get_key(encrypted_block['key_id'])
        if not managed_key:
            raise ValueError(f"Managed key not found: {encrypted_block['key_id']}")
        
        # Validate hardware binding
        if not self.key_manager.validate_hardware_binding(managed_key.key_id):
            raise ValueError(f"Hardware binding validation failed for key: {managed_key.key_id}")
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(managed_key.key_data),
            modes.GCM(encrypted_block['nonce'], encrypted_block['tag']),
            backend=default_backend()
        )
        
        # Decrypt data
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_block['encrypted_data']) + decryptor.finalize()
        
        # Verify integrity
        calculated_checksum = hashlib.sha256(decrypted_data).hexdigest()
        if calculated_checksum != encrypted_block['checksum']:
            raise ValueError("Block integrity verification failed: checksum mismatch")
        
        return decrypted_data


class TestSecureModelBlockStandalone(unittest.TestCase):
    """Standalone integration tests for secure model block management"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.secure_manager = SecureModelBlockManager(storage_dir=self.test_dir)
        
        # Test data
        self.test_license_key = "standalone_license_key_12345"
        self.test_model_id = "standalone_model_v1"
        self.test_block_data = b"This is test model block data for encryption testing" * 100
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_hardware_bound_encryption_integration(self):
        """
        Test integration between hardware-bound key generation and model encryption
        Requirements: 6.3.1, 6.3.2 - Hardware-bound keys with model encryption
        """
        # Encrypt block with hardware-bound key
        encrypted_block = self.secure_manager.encrypt_block_with_managed_key(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            license_key=self.test_license_key
        )
        
        # Verify encryption succeeded
        self.assertIsNotNone(encrypted_block)
        self.assertEqual(encrypted_block['model_id'], self.test_model_id)
        self.assertEqual(encrypted_block['original_size'], len(self.test_block_data))
        self.assertGreater(len(encrypted_block['encrypted_data']), 0)
        
        # Decrypt and verify
        decrypted_data = self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
        self.assertEqual(decrypted_data, self.test_block_data)
    
    def test_key_rotation_with_model_blocks(self):
        """
        Test key rotation with existing encrypted model blocks
        Requirements: 6.6.1, 6.6.2 - Key rotation with backward compatibility
        """
        # Create initial encrypted blocks
        encrypted_blocks = []
        for i in range(3):
            block_data = f"Block {i} data: {self.test_block_data.decode()}".encode()
            encrypted_block = self.secure_manager.encrypt_block_with_managed_key(
                model_id=self.test_model_id,
                block_data=block_data,
                block_index=i,
                license_key=self.test_license_key
            )
            encrypted_blocks.append((encrypted_block, block_data))
        
        # Get the initial key ID
        initial_key_id = encrypted_blocks[0][0]['key_id']
        
        # Verify all blocks can be decrypted initially
        for encrypted_block, original_data in encrypted_blocks:
            decrypted_data = self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
            self.assertEqual(decrypted_data, original_data)
        
        # Rotate key
        new_key = asyncio.run(self.secure_manager.key_manager.rotate_key(
            old_key_id=initial_key_id,
            license_key=self.test_license_key
        ))
        
        self.assertIsNotNone(new_key)
        
        # Verify old blocks can still be decrypted (backward compatibility)
        for encrypted_block, original_data in encrypted_blocks:
            decrypted_data = self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
            self.assertEqual(decrypted_data, original_data)
        
        # Create new block with rotated key (manually set key_id)
        new_block_data = b"New block data after rotation"
        
        # Get the new key and create encrypted block manually
        managed_key = self.secure_manager.key_manager.get_key(new_key.key_id)
        nonce = secrets.token_bytes(self.secure_manager.GCM_NONCE_SIZE)
        
        cipher = Cipher(
            algorithms.AES(managed_key.key_data),
            modes.GCM(nonce),
            backend=default_backend()
        )
        
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(new_block_data) + encryptor.finalize()
        tag = encryptor.tag
        checksum = hashlib.sha256(new_block_data).hexdigest()
        
        new_encrypted_block = {
            'block_id': f"{self.test_model_id}_block_3_{secrets.token_hex(4)}",
            'model_id': self.test_model_id,
            'block_index': 3,
            'encrypted_data': encrypted_data,
            'nonce': nonce,
            'tag': tag,
            'key_id': new_key.key_id,
            'original_size': len(new_block_data),
            'encrypted_size': len(encrypted_data),
            'checksum': checksum,
            'created_at': datetime.now()
        }
        
        # Verify new block can be decrypted
        decrypted_new_data = self.secure_manager.decrypt_block_with_managed_key(new_encrypted_block)
        self.assertEqual(decrypted_new_data, new_block_data)
    
    def test_revoked_key_encryption_failure(self):
        """
        Test that revoked keys cannot be used for encryption/decryption
        Requirements: 6.6.4 - Emergency key revocation
        """
        # Encrypt block
        encrypted_block = self.secure_manager.encrypt_block_with_managed_key(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            license_key=self.test_license_key
        )
        
        # Verify encryption and decryption work initially
        decrypted_data = self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
        self.assertEqual(decrypted_data, self.test_block_data)
        
        # Revoke the key
        key_id = encrypted_block['key_id']
        revocation_success = asyncio.run(self.secure_manager.key_manager.revoke_key(
            key_id,
            reason="test_revocation"
        ))
        self.assertTrue(revocation_success)
        
        # Verify hardware binding validation fails for revoked key
        self.assertFalse(self.secure_manager.key_manager.validate_hardware_binding(key_id))
        
        # Attempt to decrypt with revoked key should fail
        with self.assertRaises(ValueError):
            self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
    
    def test_hardware_fingerprint_mismatch_protection(self):
        """
        Test protection against hardware fingerprint mismatches
        Requirements: 6.3.2 - Validate current hardware matches bound fingerprint
        """
        # Encrypt block
        encrypted_block = self.secure_manager.encrypt_block_with_managed_key(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            license_key=self.test_license_key
        )
        
        # Get the managed key and modify its hardware fingerprint
        key_id = encrypted_block['key_id']
        managed_key = self.secure_manager.key_manager.get_key(key_id)
        original_fingerprint = managed_key.hardware_fingerprint
        
        # Simulate hardware change
        managed_key.hardware_fingerprint = "different_hardware_fingerprint"
        self.secure_manager.key_manager._store_key(managed_key)
        self.secure_manager.key_manager.key_cache[key_id] = managed_key
        
        # Verify hardware binding validation fails
        self.assertFalse(self.secure_manager.key_manager.validate_hardware_binding(key_id))
        
        # Attempt to decrypt should fail
        with self.assertRaises(ValueError):
            self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
        
        # Restore original fingerprint
        managed_key.hardware_fingerprint = original_fingerprint
        self.secure_manager.key_manager._store_key(managed_key)
        self.secure_manager.key_manager.key_cache[key_id] = managed_key
        
        # Verify decryption works again
        decrypted_data = self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
        self.assertEqual(decrypted_data, self.test_block_data)
    
    def test_key_expiration_handling(self):
        """
        Test handling of expired keys
        Requirements: 6.6.5 - Secure disposal of old encryption keys
        """
        # Encrypt block
        encrypted_block = self.secure_manager.encrypt_block_with_managed_key(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            license_key=self.test_license_key
        )
        
        # Get the managed key and expire it
        key_id = encrypted_block['key_id']
        managed_key = self.secure_manager.key_manager.get_key(key_id)
        managed_key.expires_at = datetime.now() - timedelta(hours=1)
        self.secure_manager.key_manager._store_key(managed_key)
        self.secure_manager.key_manager.key_cache[key_id] = managed_key
        
        # Verify hardware binding validation fails for expired key
        self.assertFalse(self.secure_manager.key_manager.validate_hardware_binding(key_id))
        
        # Attempt to decrypt should fail
        with self.assertRaises(ValueError):
            self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
        
        # Set key to deprecated for cleanup
        managed_key.status = KeyStatus.DEPRECATED
        self.secure_manager.key_manager._store_key(managed_key)
        self.secure_manager.key_manager.key_cache[key_id] = managed_key
        
        # Run cleanup
        cleaned_count = asyncio.run(self.secure_manager.key_manager.cleanup_expired_keys())
        self.assertEqual(cleaned_count, 1)
        
        # Verify key data was securely disposed
        cleaned_key = self.secure_manager.key_manager.get_key(key_id)
        self.assertEqual(cleaned_key.status, KeyStatus.EXPIRED)
        self.assertEqual(len(cleaned_key.key_data), 0)
    
    def test_multiple_model_key_management(self):
        """
        Test key management for multiple models
        """
        models = ["model_a", "model_b", "model_c"]
        encrypted_blocks = {}
        
        # Encrypt blocks for multiple models
        for model_id in models:
            block_data = f"Data for {model_id}".encode()
            encrypted_block = self.secure_manager.encrypt_block_with_managed_key(
                model_id=model_id,
                block_data=block_data,
                block_index=0,
                license_key=self.test_license_key
            )
            encrypted_blocks[model_id] = (encrypted_block, block_data)
        
        # Verify each model has its own key
        key_ids = [block[0]['key_id'] for block in encrypted_blocks.values()]
        self.assertEqual(len(key_ids), len(set(key_ids)))  # All unique
        
        # Verify all blocks can be decrypted
        for model_id, (encrypted_block, original_data) in encrypted_blocks.items():
            decrypted_data = self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
            self.assertEqual(decrypted_data, original_data)
        
        # Test model-specific key listing
        for model_id in models:
            model_keys = self.secure_manager.key_manager.list_active_keys(model_id=model_id)
            self.assertEqual(len(model_keys), 1)
            self.assertEqual(model_keys[0].metadata["model_id"], model_id)
    
    def test_key_rotation_chain(self):
        """
        Test multiple key rotations forming a chain
        Requirements: 6.6.1 - Maintain backward compatibility through rotation chain
        """
        # Create initial encrypted block
        encrypted_block = self.secure_manager.encrypt_block_with_managed_key(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            license_key=self.test_license_key
        )
        
        initial_key_id = encrypted_block['key_id']
        
        # Perform multiple rotations
        key_gen2 = asyncio.run(self.secure_manager.key_manager.rotate_key(
            old_key_id=initial_key_id,
            license_key=self.test_license_key
        ))
        
        key_gen3 = asyncio.run(self.secure_manager.key_manager.rotate_key(
            old_key_id=key_gen2.key_id,
            license_key=self.test_license_key
        ))
        
        # Verify rotation chain
        key_gen1 = self.secure_manager.key_manager.get_key(initial_key_id)
        self.assertEqual(key_gen1.rotation_generation, 1)
        self.assertEqual(key_gen2.rotation_generation, 2)
        self.assertEqual(key_gen3.rotation_generation, 3)
        
        self.assertEqual(key_gen2.predecessor_key_id, key_gen1.key_id)
        self.assertEqual(key_gen3.predecessor_key_id, key_gen2.key_id)
        
        # Verify original block can still be decrypted (backward compatibility)
        decrypted_data = self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
        self.assertEqual(decrypted_data, self.test_block_data)
        
        # Verify rotation history
        history = self.secure_manager.key_manager.get_key_rotation_history(initial_key_id)
        self.assertGreaterEqual(len(history), 1)
    
    def test_concurrent_operations(self):
        """Test concurrent encryption/decryption operations"""
        async def encrypt_decrypt_block(block_index: int):
            block_data = f"Concurrent block {block_index} data".encode()
            
            # Encrypt
            encrypted_block = self.secure_manager.encrypt_block_with_managed_key(
                model_id=f"concurrent_model_{block_index}",
                block_data=block_data,
                block_index=block_index,
                license_key=self.test_license_key
            )
            
            # Decrypt
            decrypted_data = self.secure_manager.decrypt_block_with_managed_key(encrypted_block)
            return decrypted_data == block_data
        
        async def run_concurrent_operations():
            tasks = [encrypt_decrypt_block(i) for i in range(5)]
            results = await asyncio.gather(*tasks)
            return results
        
        # Run concurrent operations
        results = asyncio.run(run_concurrent_operations())
        
        # All operations should succeed
        self.assertTrue(all(results))


if __name__ == '__main__':
    unittest.main(verbosity=2)