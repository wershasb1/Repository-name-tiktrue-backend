"""
Integration tests for model encryption with key management
Tests the enhanced model encryption system with hardware-bound keys
"""

import unittest
import asyncio
import tempfile
import shutil
import os
from pathlib import Path

from key_manager import KeyManager
from models.model_encryption import ModelEncryption


class EnhancedModelEncryption(ModelEncryption):
    """
    Enhanced ModelEncryption that integrates with KeyManager
    """
    
    def __init__(self, storage_dir: str = "assets/encryption", key_manager: KeyManager = None):
        super().__init__(storage_dir)
        self.key_manager = key_manager or KeyManager(storage_dir=str(Path(storage_dir) / "keys"))
    
    def generate_hardware_bound_encryption_key(self, model_id: str, license_key: str, 
                                             key_id: str = None, key_lifetime_days: int = None):
        """
        Generate hardware-bound encryption key using KeyManager
        
        Args:
            model_id: ID of the model
            license_key: License key for hardware binding
            key_id: Optional key ID
            key_lifetime_days: Key lifetime in days
            
        Returns:
            Generated managed key
        """
        return self.key_manager.generate_hardware_bound_key(
            license_key=license_key,
            model_id=model_id,
            key_lifetime_days=key_lifetime_days
        )
    
    def get_encryption_key(self, key_id: str):
        """
        Override to get keys from KeyManager first, then fallback to parent
        
        Args:
            key_id: Key ID
            
        Returns:
            Encryption key or None if not found
        """
        # Try to get from KeyManager first
        managed_key = self.key_manager.get_key(key_id)
        if managed_key:
            # Validate hardware binding
            if not self.key_manager.validate_hardware_binding(key_id):
                raise ValueError(f"Hardware binding validation failed for key: {key_id}")
            
            # Convert ManagedKey to EncryptionKey format
            from models.model_encryption import EncryptionKey
            return EncryptionKey(
                key_id=managed_key.key_id,
                algorithm=managed_key.algorithm,
                key_data=managed_key.key_data,
                created_at=managed_key.created_at,
                expires_at=managed_key.expires_at,
                metadata=managed_key.metadata
            )
        
        # Fallback to parent implementation
        return super().get_encryption_key(key_id)
    
    async def rotate_encryption_key(self, old_key_id: str, license_key: str, 
                                  notify_clients: list = None):
        """
        Rotate encryption key using KeyManager
        
        Args:
            old_key_id: ID of key to rotate
            license_key: License key for new key generation
            notify_clients: List of client node IDs to notify
            
        Returns:
            New managed key or None if rotation failed
        """
        return await self.key_manager.rotate_key(
            old_key_id=old_key_id,
            license_key=license_key,
            notify_clients=notify_clients
        )
    
    async def revoke_encryption_key(self, key_id: str, reason: str = "manual_revocation"):
        """
        Revoke encryption key using KeyManager
        
        Args:
            key_id: Key ID to revoke
            reason: Reason for revocation
            
        Returns:
            True if revocation successful
        """
        return await self.key_manager.revoke_key(key_id, reason)


class TestModelEncryptionIntegration(unittest.TestCase):
    """Integration tests for enhanced model encryption with key management"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.enhanced_encryption = EnhancedModelEncryption(storage_dir=self.test_dir)
        
        # Test data
        self.test_license_key = "model_encryption_license_12345"
        self.test_model_id = "encrypted_model_v1"
        self.test_block_data = b"Model block data for encryption testing" * 50
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_hardware_bound_model_encryption(self):
        """
        Test model encryption with hardware-bound keys
        Requirements: 6.3.1, 6.3.2 - Hardware-bound encryption keys
        """
        # Generate hardware-bound key
        managed_key = self.enhanced_encryption.generate_hardware_bound_encryption_key(
            model_id=self.test_model_id,
            license_key=self.test_license_key
        )
        
        # Encrypt model block
        encrypted_block = self.enhanced_encryption.encrypt_model_block(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            key_id=managed_key.key_id
        )
        
        # Verify encryption
        self.assertIsNotNone(encrypted_block)
        self.assertEqual(encrypted_block.key_id, managed_key.key_id)
        self.assertEqual(encrypted_block.model_id, self.test_model_id)
        
        # Decrypt and verify
        decrypted_data = self.enhanced_encryption.decrypt_model_block(encrypted_block)
        self.assertEqual(decrypted_data, self.test_block_data)
    
    def test_model_encryption_key_rotation(self):
        """
        Test model encryption with key rotation
        Requirements: 6.6.1, 6.6.2 - Key rotation with backward compatibility
        """
        # Generate initial key and encrypt blocks
        initial_key = self.enhanced_encryption.generate_hardware_bound_encryption_key(
            model_id=self.test_model_id,
            license_key=self.test_license_key
        )
        
        # Create encrypted blocks
        encrypted_blocks = []
        for i in range(3):
            block_data = f"Block {i}: {self.test_block_data.decode()}".encode()
            encrypted_block = self.enhanced_encryption.encrypt_model_block(
                model_id=self.test_model_id,
                block_data=block_data,
                block_index=i,
                key_id=initial_key.key_id
            )
            encrypted_blocks.append((encrypted_block, block_data))
        
        # Rotate key
        new_key = asyncio.run(self.enhanced_encryption.rotate_encryption_key(
            old_key_id=initial_key.key_id,
            license_key=self.test_license_key,
            notify_clients=["client1", "client2"]
        ))
        
        self.assertIsNotNone(new_key)
        
        # Verify old blocks can still be decrypted (backward compatibility)
        for encrypted_block, original_data in encrypted_blocks:
            decrypted_data = self.enhanced_encryption.decrypt_model_block(encrypted_block)
            self.assertEqual(decrypted_data, original_data)
        
        # Create new block with new key
        new_block_data = b"New block after key rotation"
        new_encrypted_block = self.enhanced_encryption.encrypt_model_block(
            model_id=self.test_model_id,
            block_data=new_block_data,
            block_index=3,
            key_id=new_key.key_id
        )
        
        # Verify new block decryption
        decrypted_new_data = self.enhanced_encryption.decrypt_model_block(new_encrypted_block)
        self.assertEqual(decrypted_new_data, new_block_data)
    
    def test_model_encryption_key_revocation(self):
        """
        Test model encryption with key revocation
        Requirements: 6.6.4 - Emergency key revocation
        """
        # Generate key and encrypt block
        managed_key = self.enhanced_encryption.generate_hardware_bound_encryption_key(
            model_id=self.test_model_id,
            license_key=self.test_license_key
        )
        
        encrypted_block = self.enhanced_encryption.encrypt_model_block(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            key_id=managed_key.key_id
        )
        
        # Verify initial decryption works
        decrypted_data = self.enhanced_encryption.decrypt_model_block(encrypted_block)
        self.assertEqual(decrypted_data, self.test_block_data)
        
        # Revoke key
        revocation_success = asyncio.run(self.enhanced_encryption.revoke_encryption_key(
            managed_key.key_id,
            reason="test_revocation"
        ))
        self.assertTrue(revocation_success)
        
        # Attempt to encrypt new block should fail
        with self.assertRaises(ValueError):
            self.enhanced_encryption.encrypt_model_block(
                model_id=self.test_model_id,
                block_data=b"New data with revoked key",
                block_index=1,
                key_id=managed_key.key_id
            )
        
        # Attempt to decrypt existing block should fail
        with self.assertRaises(ValueError):
            self.enhanced_encryption.decrypt_model_block(encrypted_block)
    
    async def test_model_file_encryption_with_hardware_keys(self):
        """
        Test full model file encryption with hardware-bound keys
        Requirements: 6.3.1, 6.3.5 - Hardware-bound keys with secure storage
        """
        # Create test model file
        test_file = Path(self.test_dir) / "test_model.bin"
        test_data = b"This is a test model file content for encryption testing.\n" * 1000
        
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        # Generate hardware-bound key
        managed_key = self.enhanced_encryption.generate_hardware_bound_encryption_key(
            model_id=self.test_model_id,
            license_key=self.test_license_key
        )
        
        # Override the key generation in encrypt_model_file to use our managed key
        original_generate_key = self.enhanced_encryption.generate_encryption_key
        
        def mock_generate_key(model_id, key_id=None, hardware_bound=False, license_key=None):
            # Return our managed key converted to EncryptionKey format
            from models.model_encryption import EncryptionKey
            return EncryptionKey(
                key_id=managed_key.key_id,
                algorithm=managed_key.algorithm,
                key_data=managed_key.key_data,
                created_at=managed_key.created_at,
                expires_at=managed_key.expires_at,
                metadata=managed_key.metadata
            )
        
        self.enhanced_encryption.generate_encryption_key = mock_generate_key
        
        try:
            # Encrypt model file
            encrypted_blocks = await self.enhanced_encryption.encrypt_model_file(
                model_id=self.test_model_id,
                file_path=str(test_file),
                output_dir=str(Path(self.test_dir) / "encrypted")
            )
            
            # Verify encryption
            self.assertGreater(len(encrypted_blocks), 0)
            
            # Decrypt model file
            decrypted_file = str(Path(self.test_dir) / "decrypted_model.bin")
            result_path = await self.enhanced_encryption.decrypt_model_file(
                model_id=self.test_model_id,
                blocks_dir=str(Path(self.test_dir) / "encrypted" / self.test_model_id),
                output_file=decrypted_file
            )
            
            # Verify decryption
            with open(result_path, 'rb') as f:
                decrypted_data = f.read()
            
            self.assertEqual(decrypted_data, test_data)
            
        finally:
            # Restore original method
            self.enhanced_encryption.generate_encryption_key = original_generate_key
    
    def test_multiple_model_encryption_management(self):
        """
        Test encryption management for multiple models
        """
        models = ["model_alpha", "model_beta", "model_gamma"]
        model_keys = {}
        encrypted_blocks = {}
        
        # Generate keys and encrypt blocks for multiple models
        for model_id in models:
            # Generate hardware-bound key
            managed_key = self.enhanced_encryption.generate_hardware_bound_encryption_key(
                model_id=model_id,
                license_key=self.test_license_key
            )
            model_keys[model_id] = managed_key
            
            # Encrypt block
            block_data = f"Data for {model_id}".encode()
            encrypted_block = self.enhanced_encryption.encrypt_model_block(
                model_id=model_id,
                block_data=block_data,
                block_index=0,
                key_id=managed_key.key_id
            )
            encrypted_blocks[model_id] = (encrypted_block, block_data)
        
        # Verify each model has unique keys
        key_ids = [key.key_id for key in model_keys.values()]
        self.assertEqual(len(key_ids), len(set(key_ids)))
        
        # Verify all blocks can be decrypted
        for model_id, (encrypted_block, original_data) in encrypted_blocks.items():
            decrypted_data = self.enhanced_encryption.decrypt_model_block(encrypted_block)
            self.assertEqual(decrypted_data, original_data)
        
        # Test model-specific key listing
        for model_id in models:
            model_keys_list = self.enhanced_encryption.key_manager.list_active_keys(model_id=model_id)
            self.assertEqual(len(model_keys_list), 1)
            self.assertEqual(model_keys_list[0].metadata["model_id"], model_id)
    
    def test_encryption_with_key_expiration(self):
        """
        Test encryption behavior with key expiration
        Requirements: 6.6.5 - Secure disposal of old encryption keys
        """
        # Generate key with short lifetime
        managed_key = self.enhanced_encryption.generate_hardware_bound_encryption_key(
            model_id=self.test_model_id,
            license_key=self.test_license_key,
            key_lifetime_days=1
        )
        
        # Encrypt block
        encrypted_block = self.enhanced_encryption.encrypt_model_block(
            model_id=self.test_model_id,
            block_data=self.test_block_data,
            block_index=0,
            key_id=managed_key.key_id
        )
        
        # Manually expire the key
        from datetime import datetime, timedelta
        managed_key.expires_at = datetime.now() - timedelta(hours=1)
        self.enhanced_encryption.key_manager._store_key(managed_key)
        self.enhanced_encryption.key_manager.key_cache[managed_key.key_id] = managed_key
        
        # Attempt to encrypt new block should fail
        with self.assertRaises(ValueError):
            self.enhanced_encryption.encrypt_model_block(
                model_id=self.test_model_id,
                block_data=b"New data with expired key",
                block_index=1,
                key_id=managed_key.key_id
            )
        
        # Attempt to decrypt existing block should fail
        with self.assertRaises(ValueError):
            self.enhanced_encryption.decrypt_model_block(encrypted_block)


if __name__ == '__main__':
    unittest.main(verbosity=2)