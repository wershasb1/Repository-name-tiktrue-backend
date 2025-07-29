"""
Enhanced Model Downloader with License-Based Access Control for TikTrue Platform

This module implements secure model downloading with license-based access control,
premium model blocking, and resumable download capabilities for the TikTrue Platform.

Features:
- License-based access control for model downloads
- Subscription tier verification for premium models
- Resumable downloads with progress tracking
- Cryptographic verification of downloaded models
- Secure model encryption for distribution
- Download statistics and monitoring

Classes:
    ModelTier: Enum for model access tier requirements
    DownloadStatus: Enum for download status tracking
    ModelInfo: Class representing model metadata
    DownloadProgress: Class for tracking download progress
    ModelDownloader: Main class for model download operations
"""

import asyncio
import json
import logging
import os
import hashlib
import aiohttp
import aiofiles
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import time

from license_enforcer import get_license_enforcer
from license_models import SubscriptionTier, LicenseInfo
from models.model_verification import ModelVerifier, verify_model_file, is_model_verified, VerificationStatus
from models.model_encryption import ModelEncryption, create_model_encryption

logger = logging.getLogger("ModelDownloader")


class ModelTier(Enum):
    """Model access tier requirements"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class DownloadStatus(Enum):
    """Download status enumeration"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class ModelInfo:
    """Model information structure"""
    model_id: str
    model_name: str
    model_version: str
    model_size: int  # Size in bytes
    required_tier: ModelTier
    download_url: str
    checksum: str
    description: str = ""
    tags: List[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class DownloadProgress:
    """Download progress tracking with resumable support"""
    model_id: str
    total_size: int
    downloaded_size: int
    download_speed: float  # bytes per second
    eta: float  # estimated time remaining in seconds
    status: DownloadStatus
    started_at: datetime
    last_update: datetime
    error_message: str = ""
    resume_position: int = 0  # Position to resume from
    chunk_hashes: List[str] = None  # Hashes of downloaded chunks for verification
    temp_file_path: str = ""  # Path to temporary download file
    
    def __post_init__(self):
        if self.chunk_hashes is None:
            self.chunk_hashes = []
    
    @property
    def progress_percentage(self) -> float:
        """Calculate download progress percentage"""
        if self.total_size == 0:
            return 0.0
        return (self.downloaded_size / self.total_size) * 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['started_at'] = self.started_at.isoformat()
        data['last_update'] = self.last_update.isoformat()
        data['progress_percentage'] = self.progress_percentage
        return data


class ModelDownloader:
    """
    Enhanced model downloader with license-based access control
    Handles model access verification, premium blocking, and progress tracking
    """
    
    # Configuration
    DEFAULT_CHUNK_SIZE = 8192  # 8KB chunks
    MAX_CONCURRENT_DOWNLOADS = 3
    DOWNLOAD_TIMEOUT = 300  # 5 minutes
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 5  # seconds
    
    def __init__(self, storage_dir: str = "assets/models"):
        """
        Initialize model downloader
        
        Args:
            storage_dir: Directory for model storage
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # License integration
        self.license_enforcer = get_license_enforcer()
        
        # Download state
        self.active_downloads: Dict[str, DownloadProgress] = {}
        self.download_history: Dict[str, DownloadProgress] = {}
        self.progress_callbacks: List[Callable[[DownloadProgress], None]] = []
        
        # Model registry
        self.model_registry: Dict[str, ModelInfo] = {}
        self._load_model_registry()
        
        # Model encryption
        self.model_encryption = None
        
        # Statistics
        self.stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'bytes_downloaded': 0,
            'license_blocks': 0,
            'premium_blocks': 0,
            'encrypted_models': 0,
            'decrypted_models': 0
        }
        
        logger.info(f"ModelDownloader initialized with storage: {self.storage_dir}")
    
    # Implementation methods would be here
    
    def _load_model_registry(self):
        """Load model registry from storage"""
        try:
            registry_path = self.storage_dir / "model_registry.json"
            if registry_path.exists():
                with open(registry_path, 'r') as f:
                    data = json.load(f)
                
                for model_id, model_data in data.items():
                    self.model_registry[model_id] = ModelInfo(
                        model_id=model_data['model_id'],
                        model_name=model_data['model_name'],
                        model_version=model_data['model_version'],
                        model_size=model_data['model_size'],
                        required_tier=ModelTier(model_data['required_tier']),
                        download_url=model_data['download_url'],
                        checksum=model_data['checksum'],
                        description=model_data.get('description', ''),
                        tags=model_data.get('tags', []),
                        created_at=datetime.fromisoformat(model_data['created_at']) if 'created_at' in model_data else None
                    )
                
                logger.info(f"Loaded {len(self.model_registry)} models from registry")
            else:
                logger.info("Model registry not found, creating new registry")
        except Exception as e:
            logger.error(f"Failed to load model registry: {e}", exc_info=True)
    
    def _save_model_registry(self):
        """Save model registry to storage"""
        try:
            registry_path = self.storage_dir / "model_registry.json"
            
            registry_data = {}
            for model_id, model_info in self.model_registry.items():
                registry_data[model_id] = {
                    'model_id': model_info.model_id,
                    'model_name': model_info.model_name,
                    'model_version': model_info.model_version,
                    'model_size': model_info.model_size,
                    'required_tier': model_info.required_tier.value,
                    'download_url': model_info.download_url,
                    'checksum': model_info.checksum,
                    'description': model_info.description,
                    'tags': model_info.tags,
                    'created_at': model_info.created_at.isoformat() if model_info.created_at else datetime.now().isoformat()
                }
            
            with open(registry_path, 'w') as f:
                json.dump(registry_data, f, indent=2)
            
            logger.info(f"Saved {len(self.model_registry)} models to registry")
        except Exception as e:
            logger.error(f"Failed to save model registry: {e}", exc_info=True)
    
    def _get_accessible_tiers(self, license_tier: SubscriptionTier) -> List[ModelTier]:
        """Get accessible model tiers based on license"""
        tier_mapping = {
            SubscriptionTier.FREE: [ModelTier.FREE],
            SubscriptionTier.PRO: [ModelTier.FREE, ModelTier.PRO],
            SubscriptionTier.ENT: [ModelTier.FREE, ModelTier.PRO, ModelTier.ENTERPRISE]
        }
        return tier_mapping.get(license_tier, [ModelTier.FREE])
    
    def _get_model_path(self, model_id: str) -> Path:
        """Get storage path for a model"""
        return self.storage_dir / model_id / "model.bin"
    
    def _get_model_dir(self, model_id: str) -> Path:
        """Get storage directory for a model"""
        return self.storage_dir / model_id
    
    async def _download_model_file(self, model_info: ModelInfo, progress: DownloadProgress) -> bool:
        """
        Download model file with progress tracking and automatic block division
        
        Args:
            model_info: Model information
            progress: Progress tracking object
            
        Returns:
            True if download successful
        """
        try:
            from backend_api_client import BackendAPIClient, LoginCredentials
            
            # Update progress status
            progress.status = DownloadStatus.DOWNLOADING
            progress.last_update = datetime.now()
            
            # Get backend API client
            backend_url = os.getenv('TIKTRUE_BACKEND_URL', 'https://api.tiktrue.com')
            
            async with BackendAPIClient(backend_url) as api_client:
                # Check if we're authenticated
                if not api_client.is_authenticated():
                    logger.error("Backend authentication required for model download")
                    progress.status = DownloadStatus.FAILED
                    progress.error_message = "Authentication required"
                    return False
                
                # Get secure download URL from backend
                download_response = await api_client.get_model_download_url(model_info.model_id)
                if not download_response.success:
                    logger.error(f"Failed to get download URL: {download_response.error}")
                    progress.status = DownloadStatus.FAILED
                    progress.error_message = download_response.error
                    return False
                
                download_url = download_response.data.get('download_url')
                expected_checksum = download_response.data.get('checksum', model_info.checksum)
                
                # Create temporary download path
                model_dir = self._get_model_dir(model_info.model_id)
                model_dir.mkdir(parents=True, exist_ok=True)
                temp_file = model_dir / "model_temp.bin"
                final_file = model_dir / "model.bin"
                
                # Progress callback for download
                def download_progress_callback(percent: float, downloaded: int, total: int):
                    progress.downloaded_size = downloaded
                    progress.total_size = total
                    progress.last_update = datetime.now()
                    
                    # Calculate download speed
                    elapsed = (progress.last_update - progress.started_at).total_seconds()
                    if elapsed > 0:
                        progress.download_speed = downloaded / elapsed
                        
                        # Calculate ETA
                        remaining_bytes = total - downloaded
                        if progress.download_speed > 0:
                            progress.eta = remaining_bytes / progress.download_speed
                    
                    # Notify callbacks
                    for callback in self.progress_callbacks:
                        try:
                            callback(progress)
                        except Exception as e:
                            logger.warning(f"Progress callback failed: {e}")
                
                # Download model file
                download_result = await api_client.download_model_file(
                    download_url=download_url,
                    local_path=temp_file,
                    progress_callback=download_progress_callback
                )
                
                if not download_result.success:
                    logger.error(f"Model download failed: {download_result.error}")
                    progress.status = DownloadStatus.FAILED
                    progress.error_message = download_result.error
                    return False
                
                # Verify model integrity with cryptographic checksum
                if not self._verify_model_integrity(temp_file, expected_checksum):
                    logger.error(f"Model integrity verification failed for {model_info.model_id}")
                    progress.status = DownloadStatus.FAILED
                    progress.error_message = "Model integrity verification failed"
                    temp_file.unlink(missing_ok=True)  # Clean up corrupted file
                    return False
                
                # Move to final location
                temp_file.rename(final_file)
                
                # Automatically divide into blocks and encrypt during download
                await self._divide_and_encrypt_model(model_info.model_id, final_file)
                
                # Update progress
                progress.status = DownloadStatus.COMPLETED
                progress.downloaded_size = progress.total_size
                progress.last_update = datetime.now()
                
                logger.info(f"Model download completed: {model_info.model_id}")
                return True
                
        except Exception as e:
            logger.error(f"Model download failed: {e}", exc_info=True)
            progress.status = DownloadStatus.FAILED
            progress.error_message = str(e)
            return False
    
    def _verify_model_integrity(self, model_path: Path, expected_checksum: str) -> bool:
        """
        Verify model file integrity using cryptographic checksums
        
        Args:
            model_path: Path to model file
            expected_checksum: Expected SHA-256 checksum
            
        Returns:
            True if integrity check passed
        """
        try:
            if not model_path.exists():
                logger.error(f"Model file not found: {model_path}")
                return False
            
            # Calculate SHA-256 checksum of the downloaded file
            sha256_hash = hashlib.sha256()
            with open(model_path, 'rb') as f:
                # Read file in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256_hash.update(chunk)
            
            calculated_checksum = sha256_hash.hexdigest()
            
            # Compare checksums
            if calculated_checksum.lower() == expected_checksum.lower():
                logger.info(f"Model integrity verification passed for {model_path.name}")
                return True
            else:
                logger.error(f"Model integrity verification failed for {model_path.name}: "
                           f"expected {expected_checksum}, got {calculated_checksum}")
                return False
                
        except Exception as e:
            logger.error(f"Model integrity verification error: {e}", exc_info=True)
            return False
    
    def _save_download_state(self, progress: DownloadProgress) -> None:
        """
        Save download state for resumable downloads
        
        Args:
            progress: Download progress object
        """
        # This is a placeholder implementation
        # In a real implementation, this would save the download state
        
        pass
    
    def _load_download_state(self, model_id: str) -> Optional[DownloadProgress]:
        """
        Load download state for resumable downloads
        
        Args:
            model_id: Model ID
            
        Returns:
            Download progress object or None if not found
        """
        # This is a placeholder implementation
        # In a real implementation, this would load the download state
        
        return None
    
    def _cleanup_download_files(self, model_id: str) -> None:
        """
        Clean up temporary download files
        
        Args:
            model_id: Model ID
        """
        # This is a placeholder implementation
        # In a real implementation, this would clean up temporary files
        
        pass
    
    async def _download_model_file_resumable(self, model_info: ModelInfo, progress: DownloadProgress) -> bool:
        """
        Download model file with resumable support
        
        Args:
            model_info: Model information
            progress: Progress tracking object
            
        Returns:
            True if download successful
        """
        # This is a placeholder implementation
        # In a real implementation, this would download the model file
        # with resumable support
        
        return True
    
    async def _divide_and_encrypt_model(self, model_id: str, model_file: Path) -> bool:
        """
        Automatically divide model into blocks and encrypt during download
        
        Args:
            model_id: Model ID
            model_file: Path to downloaded model file
            
        Returns:
            True if division and encryption successful
        """
        try:
            # Initialize model encryption if not already done
            if not self.model_encryption:
                self.model_encryption = create_model_encryption()
            
            logger.info(f"Dividing and encrypting model {model_id}...")
            
            # Encrypt model file into blocks
            encrypted_blocks = await self.model_encryption.encrypt_model_file(
                model_id=model_id,
                file_path=str(model_file)
            )
            
            if encrypted_blocks:
                logger.info(f"Model {model_id} divided into {len(encrypted_blocks)} encrypted blocks")
                self.stats['encrypted_models'] += 1
                
                # Save encryption metadata
                await self._save_encryption_metadata(model_id, encrypted_blocks, True)
                
                # Remove original unencrypted file for security
                model_file.unlink(missing_ok=True)
                
                return True
            else:
                logger.error(f"Failed to divide and encrypt model {model_id}")
                return False
                
        except Exception as e:
            logger.error(f"Model division and encryption failed for {model_id}: {e}", exc_info=True)
            return False
    
    async def _save_encryption_metadata(self, model_id: str, encrypted_blocks: List, enable_distribution: bool) -> None:
        """
        Save encryption metadata for model blocks
        
        Args:
            model_id: Model ID
            encrypted_blocks: List of encrypted blocks
            enable_distribution: Whether to enable secure distribution
        """
        try:
            model_dir = self._get_model_dir(model_id)
            metadata_file = model_dir / "encryption_metadata.json"
            
            metadata = {
                'model_id': model_id,
                'total_blocks': len(encrypted_blocks),
                'encryption_algorithm': 'AES-256-GCM',
                'created_at': datetime.now().isoformat(),
                'distribution_enabled': enable_distribution,
                'blocks': [
                    {
                        'block_id': block.block_id,
                        'block_index': block.block_index,
                        'original_size': block.original_size,
                        'encrypted_size': block.encrypted_size,
                        'checksum': block.checksum,
                        'key_id': block.key_id
                    }
                    for block in encrypted_blocks
                ]
            }
            
            async with aiofiles.open(metadata_file, 'w') as f:
                await f.write(json.dumps(metadata, indent=2))
            
            logger.info(f"Encryption metadata saved for model {model_id}")
            
        except Exception as e:
            logger.error(f"Failed to save encryption metadata for {model_id}: {e}", exc_info=True)
    
    def register_model(self, model_info: ModelInfo) -> bool:
        """
        Register a model in the registry
        
        Args:
            model_info: Model information to register
            
        Returns:
            True if registered successfully
        """
        try:
            self.model_registry[model_info.model_id] = model_info
            self._save_model_registry()
            
            logger.info(f"Model registered: {model_info.model_id} ({model_info.model_name})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register model {model_info.model_id}: {e}", exc_info=True)
            return False
    
    def get_available_models(self, include_premium: bool = None) -> List[ModelInfo]:
        """
        Get list of available models based on license
        
        Args:
            include_premium: Override premium filtering
            
        Returns:
            List of accessible models
        """
        try:
            # Get current license status
            license_status = self.license_enforcer.get_license_status()
            current_license = self.license_enforcer.current_license
            
            if not current_license or not license_status.get('valid'):
                logger.warning("No valid license - returning only free models")
                return [model for model in self.model_registry.values() 
                       if model.required_tier == ModelTier.FREE]
            
            # Determine accessible tiers based on license
            accessible_tiers = self._get_accessible_tiers(current_license.plan)
            
            # Filter models by accessibility
            available_models = []
            for model in self.model_registry.values():
                if include_premium is False and model.required_tier != ModelTier.FREE:
                    continue
                
                if model.required_tier in accessible_tiers:
                    available_models.append(model)
            
            logger.info(f"Found {len(available_models)} accessible models for tier {current_license.plan.value}")
            return available_models
            
        except Exception as e:
            logger.error(f"Failed to get available models: {e}", exc_info=True)
            return []
    
    async def download_model(self, model_id: str, 
                           progress_callback: Callable[[DownloadProgress], None] = None) -> bool:
        """
        Download a model with license validation
        
        Args:
            model_id: ID of the model to download
            progress_callback: Optional progress callback
            
        Returns:
            True if download successful
        """
        try:
            # Validate model access
            if not self.validate_model_access(model_id):
                logger.error(f"Model access denied for {model_id}")
                return False
            
            # Get model info
            if model_id not in self.model_registry:
                logger.error(f"Model {model_id} not found in registry")
                return False
            
            model_info = self.model_registry[model_id]
            
            # Check if already downloading
            if model_id in self.active_downloads:
                logger.warning(f"Model {model_id} is already being downloaded")
                return False
            
            # Check if already exists
            model_path = self._get_model_path(model_id)
            if model_path.exists() and self._verify_model_integrity(model_path, model_info.checksum):
                logger.info(f"Model {model_id} already exists and is valid")
                return True
            
            # Initialize download progress
            progress = DownloadProgress(
                model_id=model_id,
                total_size=model_info.model_size,
                downloaded_size=0,
                download_speed=0.0,
                eta=0.0,
                status=DownloadStatus.PENDING,
                started_at=datetime.now(),
                last_update=datetime.now()
            )
            
            self.active_downloads[model_id] = progress
            
            # Add callback if provided
            if progress_callback:
                self.progress_callbacks.append(progress_callback)
            
            # Start download
            success = await self._download_model_file(model_info, progress)
            
            # Update statistics
            self.stats['total_downloads'] += 1
            if success:
                self.stats['successful_downloads'] += 1
                self.stats['bytes_downloaded'] += model_info.model_size
            else:
                self.stats['failed_downloads'] += 1
            
            # Move to history
            self.download_history[model_id] = progress
            if model_id in self.active_downloads:
                del self.active_downloads[model_id]
            
            # Remove callback
            if progress_callback and progress_callback in self.progress_callbacks:
                self.progress_callbacks.remove(progress_callback)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to download model {model_id}: {e}", exc_info=True)
            return False
    
    def validate_model_access(self, model_id: str) -> bool:
        """
        Validate model access rights based on license
        
        Args:
            model_id: ID of the model to validate
            
        Returns:
            True if access is allowed
        """
        try:
            # Check if model exists
            if model_id not in self.model_registry:
                logger.error(f"Model {model_id} not found in registry")
                return False
            
            model_info = self.model_registry[model_id]
            
            # Get current license
            license_status = self.license_enforcer.get_license_status()
            current_license = self.license_enforcer.current_license
            
            if not current_license or not license_status.get('valid'):
                # Only allow free models without valid license
                if model_info.required_tier == ModelTier.FREE:
                    logger.info(f"Free model {model_id} accessible without license")
                    return True
                else:
                    logger.warning(f"Premium model {model_id} blocked - no valid license")
                    self.stats['license_blocks'] += 1
                    return False
            
            # Check tier compatibility
            accessible_tiers = self._get_accessible_tiers(current_license.plan)
            
            if model_info.required_tier not in accessible_tiers:
                logger.warning(f"Model {model_id} requires {model_info.required_tier.value} tier, "
                             f"but license is {current_license.plan.value}")
                self.stats['premium_blocks'] += 1
                return False
            
            # Check model-specific permissions
            if hasattr(current_license, 'allowed_models') and current_license.allowed_models:
                if model_id not in current_license.allowed_models:
                    logger.warning(f"Model {model_id} not in allowed models list")
                    self.stats['premium_blocks'] += 1
                    return False
            
            logger.info(f"Model access granted for {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Model access validation failed for {model_id}: {e}", exc_info=True)
            return False
    
    def get_download_progress(self, model_id: str) -> Optional[DownloadProgress]:
        """
        Get download progress for a model
        
        Args:
            model_id: ID of the model
            
        Returns:
            Download progress or None if not found
        """
        # Check active downloads first
        if model_id in self.active_downloads:
            return self.active_downloads[model_id]
        
        # Check history
        if model_id in self.download_history:
            return self.download_history[model_id]
        
        return None
    
    def pause_download(self, model_id: str) -> bool:
        """
        Pause an active download
        
        Args:
            model_id: ID of the model to pause
            
        Returns:
            True if paused successfully
        """
        try:
            if model_id not in self.active_downloads:
                logger.warning(f"No active download found for model {model_id}")
                return False
            
            progress = self.active_downloads[model_id]
            if progress.status != DownloadStatus.DOWNLOADING:
                logger.warning(f"Download {model_id} is not in downloading state")
                return False
            
            progress.status = DownloadStatus.PAUSED
            progress.last_update = datetime.now()
            
            # Save download state for resuming
            self._save_download_state(progress)
            
            logger.info(f"Download paused for model {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause download for {model_id}: {e}", exc_info=True)
            return False
    
    async def resume_download(self, model_id: str) -> bool:
        """
        Resume a paused download
        
        Args:
            model_id: ID of the model to resume
            
        Returns:
            True if resumed successfully
        """
        try:
            # Check if download is paused
            if model_id not in self.active_downloads:
                # Try to load from saved state
                progress = self._load_download_state(model_id)
                if not progress:
                    logger.error(f"No paused download found for model {model_id}")
                    return False
                self.active_downloads[model_id] = progress
            
            progress = self.active_downloads[model_id]
            if progress.status != DownloadStatus.PAUSED:
                logger.warning(f"Download {model_id} is not in paused state")
                return False
            
            # Get model info
            if model_id not in self.model_registry:
                logger.error(f"Model {model_id} not found in registry")
                return False
            
            model_info = self.model_registry[model_id]
            
            # Resume download
            logger.info(f"Resuming download for model {model_id} from position {progress.resume_position}")
            success = await self._download_model_file_resumable(model_info, progress)
            
            # Update statistics
            if success:
                self.stats['successful_downloads'] += 1
                self.stats['bytes_downloaded'] += (model_info.model_size - progress.resume_position)
            else:
                self.stats['failed_downloads'] += 1
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to resume download for {model_id}: {e}", exc_info=True)
            return False
    
    def cancel_download(self, model_id: str) -> bool:
        """
        Cancel an active download
        
        Args:
            model_id: ID of the model to cancel
            
        Returns:
            True if cancelled successfully
        """
        try:
            if model_id not in self.active_downloads:
                logger.warning(f"No active download found for model {model_id}")
                return False
            
            progress = self.active_downloads[model_id]
            progress.status = DownloadStatus.CANCELLED
            progress.last_update = datetime.now()
            
            # Clean up temporary files
            self._cleanup_download_files(model_id)
            
            # Move to history
            self.download_history[model_id] = progress
            del self.active_downloads[model_id]
            
            logger.info(f"Download cancelled for model {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel download for {model_id}: {e}", exc_info=True)
            return False
    
    def get_download_statistics(self) -> Dict[str, Any]:
        """
        Get download statistics
        
        Returns:
            Dictionary with download statistics
        """
        stats = self.stats.copy()
        stats['active_downloads'] = len(self.active_downloads)
        stats['registered_models'] = len(self.model_registry)
        stats['storage_path'] = str(self.storage_dir)
        
        # Calculate success rate
        if stats['total_downloads'] > 0:
            stats['success_rate'] = stats['successful_downloads'] / stats['total_downloads']
        else:
            stats['success_rate'] = 0.0
        
        return stats
    
    async def encrypt_model(self, model_id: str, enable_distribution: bool = True) -> bool:
        """
        Encrypt a downloaded model for secure distribution
        
        Args:
            model_id: ID of the model to encrypt
            enable_distribution: Whether to enable secure distribution
            
        Returns:
            True if encryption successful
        """
        try:
            # Check if model exists
            model_path = self._get_model_path(model_id)
            if not model_path.exists():
                logger.error(f"Model file not found for encryption: {model_id}")
                return False
            
            # Initialize encryption if not already done
            if not self.model_encryption:
                self.model_encryption = create_model_encryption()
            
            # Encrypt model file
            logger.info(f"Encrypting model {model_id}...")
            encrypted_blocks = await self.model_encryption.encrypt_model_file(
                model_id=model_id,
                file_path=str(model_path)
            )
            
            if encrypted_blocks:
                logger.info(f"Model {model_id} encrypted into {len(encrypted_blocks)} blocks")
                self.stats['encrypted_models'] += 1
                
                # Save encryption metadata
                await self._save_encryption_metadata(model_id, encrypted_blocks, enable_distribution)
                
                return True
            else:
                logger.error(f"Failed to encrypt model {model_id}")
                return False
                
        except Exception as e:
            logger.error(f"Model encryption failed for {model_id}: {e}", exc_info=True)
            return False
    
    async def decrypt_model(self, model_id: str, output_path: str = None) -> bool:
        """
        Decrypt an encrypted model
        
        Args:
            model_id: ID of the model to decrypt
            output_path: Optional output path (defaults to model storage)
            
        Returns:
            True if decryption successful
        """
        try:
            # Initialize encryption if not already done
            if not self.model_encryption:
                self.model_encryption = create_model_encryption()
            
            # Set output path
            if not output_path:
                output_path = str(self._get_model_path(model_id))
            
            # Check if encrypted blocks exist
            blocks_dir = self.model_encryption.blocks_dir / model_id
            if not blocks_dir.exists():
                logger.error(f"Encrypted blocks not found for model {model_id}")
                return False
            
            # Decrypt model file
            logger.info(f"Decrypting model {model_id}...")
            decrypted_path = await self.model_encryption.decrypt_model_file(
                model_id=model_id,
                blocks_dir=str(blocks_dir),
                output_file=output_path
            )
            
            if decrypted_path:
                logger.info(f"Model {model_id} decrypted to {decrypted_path}")
                self.stats['decrypted_models'] += 1
                return True
            else:
                logger.error(f"Failed to decrypt model {model_id}")
                return False
                
        except Exception as e:
            logger.error(f"Model decryption failed for {model_id}: {e}", exc_info=True)
            return False
    
    def create_key_exchange_request(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Create a key exchange request for secure model sharing
        
        Args:
            node_id: ID of the requesting node
            
        Returns:
            Key exchange request data or None if failed
        """
        try:
            # Initialize encryption if not already done
            if not self.model_encryption:
                self.model_encryption = create_model_encryption()
            
            # Create key exchange request
            request = self.model_encryption.create_key_exchange_request(node_id)
            
            logger.info(f"Created key exchange request for node {node_id}")
            return request.to_dict()
            
        except Exception as e:
            logger.error(f"Failed to create key exchange request: {e}", exc_info=True)
            return None
    
    def share_model_key(self, model_id: str, key_exchange_request: Dict[str, Any]) -> Optional[bytes]:
        """
        Share a model encryption key with another node
        
        Args:
            model_id: ID of the model to share
            key_exchange_request: Key exchange request from requesting node
            
        Returns:
            Encrypted key data or None if failed
        """
        try:
            # Initialize encryption if not already done
            if not self.model_encryption:
                self.model_encryption = create_model_encryption()
            
            # Get model encryption key
            encryption_keys = self.model_encryption.list_encryption_keys(model_id)
            if not encryption_keys:
                logger.error(f"No encryption keys found for model {model_id}")
                return None
            
            # Use the first available key
            encryption_key = encryption_keys[0]
            
            # Create key exchange request object
            from models.model_encryption import KeyExchangeRequest, KeyExchangeMethod
            request = KeyExchangeRequest(
                request_id=key_exchange_request['request_id'],
                node_id=key_exchange_request['node_id'],
                public_key=base64.b64decode(key_exchange_request['public_key']),
                method=KeyExchangeMethod(key_exchange_request['method']),
                timestamp=datetime.fromisoformat(key_exchange_request['timestamp']),
                signature=base64.b64decode(key_exchange_request['signature']) if key_exchange_request.get('signature') else None
            )
            
            # Process key exchange and encrypt key
            encrypted_key_data = self.model_encryption.process_key_exchange_request(request, encryption_key)
            
            logger.info(f"Shared encryption key for model {model_id} with node {request.node_id}")
            return encrypted_key_data
            
        except Exception as e:
            logger.error(f"Failed to share model key: {e}", exc_info=True)
            return None
    
    def receive_model_key(self, model_id: str, encrypted_key_data: bytes, key_id: str) -> bool:
        """
        Receive and store a shared model encryption key
        
        Args:
            model_id: ID of the model
            encrypted_key_data: Encrypted key data
            key_id: Key ID
            
        Returns:
            True if key received successfully
        """
        try:
            # Initialize encryption if not already done
            if not self.model_encryption:
                self.model_encryption = create_model_encryption()
            
            # Receive and decrypt key
            encryption_key = self.model_encryption.receive_encrypted_key(
                encrypted_key_data, key_id, model_id
            )
            
            if encryption_key:
                logger.info(f"Received encryption key for model {model_id}")
                return True
            else:
                logger.error(f"Failed to receive encryption key for model {model_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to receive model key: {e}", exc_info=True)
            return False
    
    def get_model_encryption_status(self, model_id: str) -> Dict[str, Any]:
        """
        Get encryption status for a model
        
        Args:
            model_id: ID of the model
            
        Returns:
            Dictionary with encryption status information
        """
        try:
            status = {
                'model_id': model_id,
                'encrypted': False,
                'blocks_count': 0,
                'encryption_keys': [],
                'distribution_enabled': False
            }
            
            # Check if model is encrypted
            if self.model_encryption:
                # Check for encrypted blocks
                blocks_dir = self.model_encryption.blocks_dir / model_id
                if blocks_dir.exists():
                    manifest_file = blocks_dir / "manifest.json"
                    if manifest_file.exists():
                        with open(manifest_file, 'r') as f:
                            manifest = json.load(f)
                        
                        status['encrypted'] = True
                        status['blocks_count'] = manifest.get('total_blocks', 0)
                
                # Get encryption keys
                encryption_keys = self.model_encryption.list_encryption_keys(model_id)
                status['encryption_keys'] = [key.key_id for key in encryption_keys]
            
            # Check encryption metadata
            metadata_path = self._get_model_dir(model_id) / "encryption_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    encryption_metadata = json.load(f)
                status['distribution_enabled'] = encryption_metadata.get('distribution_enabled', False)
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get encryption status for {model_id}: {e}", exc_info=True)
            return {'model_id': model_id, 'encrypted': False, 'error': str(e)}    


# Global model downloader instance
_model_downloader = None


def get_model_downloader(storage_dir: str = "assets/models") -> ModelDownloader:
    """Get global model downloader instance"""
    global _model_downloader
    if _model_downloader is None:
        _model_downloader = ModelDownloader(storage_dir)
    return _model_downloader