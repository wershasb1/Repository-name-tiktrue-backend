"""
Secure Model Storage System
Handles encrypted storage and retrieval of model files and blocks
"""

import os
import hashlib
import secrets
import json
from typing import Dict, List, Optional, Tuple, BinaryIO
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)

class SecureModelStorage:
    """
    Secure storage system for model files with encryption and access control
    """
    
    def __init__(self):
        self.storage_root = getattr(settings, 'MODEL_STORAGE_ROOT', 
                                  os.path.join(settings.BASE_DIR.parent, 'assets', 'models'))
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for model storage"""
        key_file = os.path.join(settings.BASE_DIR, 'model_storage_key.key')
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
            return key
    
    def _generate_storage_path(self, model_name: str, file_type: str, 
                              block_id: Optional[int] = None) -> str:
        """Generate secure storage path for model files"""
        if block_id is not None:
            return os.path.join(self.storage_root, model_name, 'blocks', 
                              f'{file_type}_{block_id}.encrypted')
        else:
            return os.path.join(self.storage_root, model_name, 
                              f'{file_type}.encrypted')
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file for integrity verification"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def store_model_block(self, model_name: str, block_id: int, 
                         block_data: bytes, metadata: Dict) -> Dict:
        """
        Store encrypted model block with metadata
        
        Args:
            model_name: Name of the model
            block_id: Block identifier
            block_data: Raw block data
            metadata: Block metadata
            
        Returns:
            Dict with storage information
        """
        try:
            # Create storage directory
            storage_path = self._generate_storage_path(model_name, 'block', block_id)
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            
            # Encrypt block data
            encrypted_data = self.cipher_suite.encrypt(block_data)
            
            # Store encrypted block
            with open(storage_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Calculate hash for integrity
            file_hash = self._calculate_file_hash(storage_path)
            
            # Store metadata
            metadata_path = storage_path.replace('.encrypted', '_metadata.json')
            block_metadata = {
                'model_name': model_name,
                'block_id': block_id,
                'file_hash': file_hash,
                'file_size': len(encrypted_data),
                'original_size': len(block_data),
                'stored_at': datetime.now().isoformat(),
                'metadata': metadata
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(block_metadata, f, indent=2)
            
            logger.info(f"Stored encrypted block {block_id} for model {model_name}")
            
            return {
                'success': True,
                'storage_path': storage_path,
                'file_hash': file_hash,
                'encrypted_size': len(encrypted_data),
                'original_size': len(block_data)
            }
            
        except Exception as e:
            logger.error(f"Failed to store model block {block_id} for {model_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def retrieve_model_block(self, model_name: str, block_id: int, 
                           verify_integrity: bool = True) -> Optional[bytes]:
        """
        Retrieve and decrypt model block
        
        Args:
            model_name: Name of the model
            block_id: Block identifier
            verify_integrity: Whether to verify file integrity
            
        Returns:
            Decrypted block data or None if not found
        """
        try:
            storage_path = self._generate_storage_path(model_name, 'block', block_id)
            metadata_path = storage_path.replace('.encrypted', '_metadata.json')
            
            if not os.path.exists(storage_path):
                logger.warning(f"Block {block_id} not found for model {model_name}")
                return None
            
            # Verify integrity if requested
            if verify_integrity and os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                current_hash = self._calculate_file_hash(storage_path)
                if current_hash != metadata.get('file_hash'):
                    logger.error(f"Integrity check failed for block {block_id} of {model_name}")
                    return None
            
            # Read and decrypt block
            with open(storage_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            
            logger.info(f"Retrieved block {block_id} for model {model_name}")
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Failed to retrieve block {block_id} for {model_name}: {e}")
            return None
    
    def store_model_metadata(self, model_name: str, metadata: Dict) -> bool:
        """Store model metadata securely"""
        try:
            storage_path = self._generate_storage_path(model_name, 'metadata')
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            
            # Encrypt metadata
            metadata_json = json.dumps(metadata, indent=2).encode('utf-8')
            encrypted_metadata = self.cipher_suite.encrypt(metadata_json)
            
            with open(storage_path, 'wb') as f:
                f.write(encrypted_metadata)
            
            logger.info(f"Stored metadata for model {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store metadata for {model_name}: {e}")
            return False
    
    def retrieve_model_metadata(self, model_name: str) -> Optional[Dict]:
        """Retrieve model metadata"""
        try:
            storage_path = self._generate_storage_path(model_name, 'metadata')
            
            if not os.path.exists(storage_path):
                return None
            
            with open(storage_path, 'rb') as f:
                encrypted_metadata = f.read()
            
            decrypted_metadata = self.cipher_suite.decrypt(encrypted_metadata)
            metadata = json.loads(decrypted_metadata.decode('utf-8'))
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to retrieve metadata for {model_name}: {e}")
            return None
    
    def list_model_blocks(self, model_name: str) -> List[Dict]:
        """List all blocks for a model with their metadata"""
        blocks = []
        model_path = os.path.join(self.storage_root, model_name, 'blocks')
        
        if not os.path.exists(model_path):
            return blocks
        
        try:
            for filename in os.listdir(model_path):
                if filename.endswith('_metadata.json'):
                    metadata_path = os.path.join(model_path, filename)
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    blocks.append(metadata)
            
            # Sort by block_id
            blocks.sort(key=lambda x: x.get('block_id', 0))
            return blocks
            
        except Exception as e:
            logger.error(f"Failed to list blocks for {model_name}: {e}")
            return []
    
    def delete_model(self, model_name: str) -> bool:
        """Delete all files for a model"""
        try:
            model_path = os.path.join(self.storage_root, model_name)
            
            if os.path.exists(model_path):
                import shutil
                shutil.rmtree(model_path)
                logger.info(f"Deleted model {model_name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete model {model_name}: {e}")
            return False
    
    def get_storage_stats(self, model_name: str) -> Dict:
        """Get storage statistics for a model"""
        try:
            model_path = os.path.join(self.storage_root, model_name)
            
            if not os.path.exists(model_path):
                return {'exists': False}
            
            total_size = 0
            block_count = 0
            
            for root, dirs, files in os.walk(model_path):
                for file in files:
                    if file.endswith('.encrypted'):
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)
                        if 'block_' in file:
                            block_count += 1
            
            return {
                'exists': True,
                'total_size': total_size,
                'block_count': block_count,
                'storage_path': model_path
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage stats for {model_name}: {e}")
            return {'exists': False, 'error': str(e)}


class AuthenticatedDownloadManager:
    """
    Manages authenticated download URLs with expiration and access control
    """
    
    def __init__(self):
        self.storage = SecureModelStorage()
        self.download_tokens = {}  # In production, use Redis or database
    
    def create_download_url(self, user, model_name: str, block_id: Optional[int] = None,
                           expires_in: int = 3600) -> Optional[str]:
        """
        Create authenticated download URL with expiration
        
        Args:
            user: User requesting download
            model_name: Name of the model
            block_id: Optional block ID for specific block
            expires_in: Expiration time in seconds
            
        Returns:
            Secure download token or None
        """
        try:
            # Generate secure token
            token = secrets.token_urlsafe(32)
            
            # Store token with metadata
            self.download_tokens[token] = {
                'user_id': user.id,
                'model_name': model_name,
                'block_id': block_id,
                'created_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(seconds=expires_in),
                'ip_address': None,  # Set when used
                'used': False
            }
            
            logger.info(f"Created download token for user {user.id}, model {model_name}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create download URL: {e}")
            return None
    
    def validate_download_token(self, token: str, user_id: int, 
                               ip_address: str) -> Optional[Dict]:
        """
        Validate download token and return metadata
        
        Args:
            token: Download token
            user_id: User ID making request
            ip_address: Client IP address
            
        Returns:
            Token metadata if valid, None otherwise
        """
        try:
            token_data = self.download_tokens.get(token)
            
            if not token_data:
                logger.warning(f"Invalid download token: {token}")
                return None
            
            # Check expiration
            if datetime.now() > token_data['expires_at']:
                logger.warning(f"Expired download token: {token}")
                del self.download_tokens[token]
                return None
            
            # Check user
            if token_data['user_id'] != user_id:
                logger.warning(f"Token user mismatch: {token}")
                return None
            
            # Update usage info
            token_data['ip_address'] = ip_address
            token_data['used'] = True
            
            return token_data
            
        except Exception as e:
            logger.error(f"Failed to validate download token: {e}")
            return None
    
    def serve_model_block(self, token: str, user_id: int, 
                         ip_address: str) -> Optional[Tuple[bytes, str]]:
        """
        Serve model block using authenticated token
        
        Returns:
            Tuple of (block_data, content_type) or None
        """
        try:
            token_data = self.validate_download_token(token, user_id, ip_address)
            
            if not token_data:
                return None
            
            model_name = token_data['model_name']
            block_id = token_data['block_id']
            
            if block_id is not None:
                # Serve specific block
                block_data = self.storage.retrieve_model_block(model_name, block_id)
                if block_data:
                    return block_data, 'application/octet-stream'
            else:
                # Serve model metadata
                metadata = self.storage.retrieve_model_metadata(model_name)
                if metadata:
                    metadata_json = json.dumps(metadata, indent=2).encode('utf-8')
                    return metadata_json, 'application/json'
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to serve model block: {e}")
            return None
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens from memory"""
        try:
            current_time = datetime.now()
            expired_tokens = [
                token for token, data in self.download_tokens.items()
                if current_time > data['expires_at']
            ]
            
            for token in expired_tokens:
                del self.download_tokens[token]
            
            if expired_tokens:
                logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")


# Global instances
secure_storage = SecureModelStorage()
download_manager = AuthenticatedDownloadManager()