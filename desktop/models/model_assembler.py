"""
Model Block Assembly and Loading System for TikTrue Platform

This module implements secure model block assembly and loading for client nodes,
with license validation and metadata management for the TikTrue Platform.

Features:
- Secure model block assembly from encrypted blocks
- Model loading with license validation at runtime
- Model metadata management and version tracking
- Block integrity verification during assembly
- Memory-efficient streaming assembly for large models
- Automatic cleanup of temporary files

Classes:
    AssemblyStatus: Enum for assembly operation status
    ModelMetadata: Class representing model metadata and version info
    AssemblyProgress: Class for tracking assembly progress
    ModelAssembler: Main class for model assembly and loading operations

Requirements addressed:
- 5.2: Create model block assembly system for client nodes
- 5.5: Implement secure model loading with license validation
- 5.6: Build model metadata management and version tracking
"""

import asyncio
import json
import logging
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import aiofiles

from license_enforcer import get_license_enforcer
from models.model_encryption import ModelEncryption, EncryptedBlock, create_model_encryption
from models.model_verification import ModelVerifier, VerificationStatus

logger = logging.getLogger("ModelAssembler")


class AssemblyStatus(Enum):
    """Model assembly status"""
    PENDING = "pending"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    FAILED = "failed"
    LOADING = "loading"
    LOADED = "loaded"
    UNLOADED = "unloaded"


@dataclass
class ModelMetadata:
    """Model metadata and version information"""
    model_id: str
    model_name: str
    model_version: str
    model_type: str  # e.g., "llama", "mistral", "gpt"
    total_blocks: int
    total_size: int  # Size in bytes
    block_size: int  # Individual block size
    encryption_algorithm: str
    checksum_algorithm: str
    created_at: datetime
    last_verified: Optional[datetime] = None
    license_requirements: Dict[str, Any] = None
    hardware_requirements: Dict[str, Any] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.license_requirements is None:
            self.license_requirements = {}
        if self.hardware_requirements is None:
            self.hardware_requirements = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_verified'] = self.last_verified.isoformat() if self.last_verified else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelMetadata':
        """Create from dictionary"""
        return cls(
            model_id=data['model_id'],
            model_name=data['model_name'],
            model_version=data['model_version'],
            model_type=data['model_type'],
            total_blocks=data['total_blocks'],
            total_size=data['total_size'],
            block_size=data['block_size'],
            encryption_algorithm=data['encryption_algorithm'],
            checksum_algorithm=data['checksum_algorithm'],
            created_at=datetime.fromisoformat(data['created_at']),
            last_verified=datetime.fromisoformat(data['last_verified']) if data.get('last_verified') else None,
            license_requirements=data.get('license_requirements', {}),
            hardware_requirements=data.get('hardware_requirements', {}),
            tags=data.get('tags', [])
        )


@dataclass
class AssemblyProgress:
    """Model assembly progress tracking"""
    model_id: str
    total_blocks: int
    assembled_blocks: int
    total_size: int
    assembled_size: int
    assembly_speed: float  # bytes per second
    eta: float  # estimated time remaining in seconds
    status: AssemblyStatus
    started_at: datetime
    last_update: datetime
    error_message: str = ""
    temp_file_path: str = ""
    
    @property
    def progress_percentage(self) -> float:
        """Calculate assembly progress percentage"""
        if self.total_blocks == 0:
            return 0.0
        return (self.assembled_blocks / self.total_blocks) * 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['started_at'] = self.started_at.isoformat()
        data['last_update'] = self.last_update.isoformat()
        data['progress_percentage'] = self.progress_percentage
        return data


class ModelAssembler:
    """
    Model block assembly and loading system for client nodes
    Handles secure assembly of encrypted blocks and license-validated loading
    """
    
    def __init__(self, storage_dir: str = "assets/models", temp_dir: str = None):
        """
        Initialize model assembler
        
        Args:
            storage_dir: Directory for assembled models
            temp_dir: Temporary directory for assembly operations
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Temporary directory for assembly operations
        if temp_dir:
            self.temp_dir = Path(temp_dir)
        else:
            self.temp_dir = self.storage_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # License integration
        self.license_enforcer = get_license_enforcer()
        
        # Model encryption for block decryption
        self.model_encryption = None
        
        # Model verification
        self.model_verifier = ModelVerifier()
        
        # Assembly state
        self.active_assemblies: Dict[str, AssemblyProgress] = {}
        self.assembly_history: Dict[str, AssemblyProgress] = {}
        
        # Loaded models tracking
        self.loaded_models: Dict[str, Dict[str, Any]] = {}
        
        # Model metadata cache
        self.metadata_cache: Dict[str, ModelMetadata] = {}
        
        # Statistics
        self.stats = {
            'total_assemblies': 0,
            'successful_assemblies': 0,
            'failed_assemblies': 0,
            'models_loaded': 0,
            'models_unloaded': 0,
            'license_validations': 0,
            'license_failures': 0
        }
        
        logger.info(f"ModelAssembler initialized with storage: {self.storage_dir}")
    
    def _get_model_dir(self, model_id: str) -> Path:
        """Get storage directory for a model"""
        return self.storage_dir / model_id
    
    def _get_model_path(self, model_id: str) -> Path:
        """Get assembled model file path"""
        return self._get_model_dir(model_id) / "model.bin"
    
    def _get_metadata_path(self, model_id: str) -> Path:
        """Get model metadata file path"""
        return self._get_model_dir(model_id) / "metadata.json"
    
    def _get_blocks_dir(self, model_id: str) -> Path:
        """Get encrypted blocks directory"""
        return self._get_model_dir(model_id) / "blocks"
    
    async def load_model_metadata(self, model_id: str) -> Optional[ModelMetadata]:
        """
        Load model metadata from storage
        
        Args:
            model_id: Model identifier
            
        Returns:
            ModelMetadata object or None if not found
        """
        try:
            # Check cache first
            if model_id in self.metadata_cache:
                return self.metadata_cache[model_id]
            
            metadata_path = self._get_metadata_path(model_id)
            if not metadata_path.exists():
                logger.warning(f"Metadata not found for model {model_id}")
                return None
            
            async with aiofiles.open(metadata_path, 'r') as f:
                metadata_data = json.loads(await f.read())
            
            metadata = ModelMetadata.from_dict(metadata_data)
            
            # Cache metadata
            self.metadata_cache[model_id] = metadata
            
            logger.info(f"Loaded metadata for model {model_id}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to load metadata for model {model_id}: {e}", exc_info=True)
            return None
    
    async def save_model_metadata(self, metadata: ModelMetadata) -> bool:
        """
        Save model metadata to storage
        
        Args:
            metadata: ModelMetadata object to save
            
        Returns:
            True if saved successfully
        """
        try:
            model_dir = self._get_model_dir(metadata.model_id)
            model_dir.mkdir(parents=True, exist_ok=True)
            
            metadata_path = self._get_metadata_path(metadata.model_id)
            
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata.to_dict(), indent=2))
            
            # Update cache
            self.metadata_cache[metadata.model_id] = metadata
            
            logger.info(f"Saved metadata for model {metadata.model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save metadata for model {metadata.model_id}: {e}", exc_info=True)
            return False
    
    async def validate_license_for_model(self, model_id: str) -> bool:
        """
        Validate license for model loading
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if license allows model loading
        """
        try:
            self.stats['license_validations'] += 1
            
            # Get model metadata
            metadata = await self.load_model_metadata(model_id)
            if not metadata:
                logger.error(f"Cannot validate license: metadata not found for model {model_id}")
                self.stats['license_failures'] += 1
                return False
            
            # Check basic license validity
            license_status = self.license_enforcer.get_license_status()
            if not license_status.get('valid'):
                logger.warning(f"License validation failed for model {model_id}: Invalid license")
                self.stats['license_failures'] += 1
                return False
            
            # Check model-specific license requirements
            if metadata.license_requirements:
                required_tier = metadata.license_requirements.get('minimum_tier')
                if required_tier:
                    current_license = self.license_enforcer.current_license
                    if not current_license:
                        logger.warning(f"License validation failed for model {model_id}: No license found")
                        self.stats['license_failures'] += 1
                        return False
                    
                    # Check tier compatibility (simplified check)
                    tier_hierarchy = {'FREE': 0, 'PRO': 1, 'ENT': 2}
                    current_tier_level = tier_hierarchy.get(current_license.plan.value, 0)
                    required_tier_level = tier_hierarchy.get(required_tier, 0)
                    
                    if current_tier_level < required_tier_level:
                        logger.warning(f"License validation failed for model {model_id}: "
                                     f"Requires {required_tier} tier, have {current_license.plan.value}")
                        self.stats['license_failures'] += 1
                        return False
            
            logger.info(f"License validation passed for model {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"License validation error for model {model_id}: {e}", exc_info=True)
            self.stats['license_failures'] += 1
            return False
    
    async def load_encrypted_blocks(self, model_id: str) -> List[EncryptedBlock]:
        """
        Load encrypted blocks for a model
        
        Args:
            model_id: Model identifier
            
        Returns:
            List of encrypted blocks
        """
        try:
            blocks_dir = self._get_blocks_dir(model_id)
            if not blocks_dir.exists():
                logger.error(f"Blocks directory not found for model {model_id}")
                return []
            
            # Load block manifest
            manifest_path = blocks_dir / "manifest.json"
            if not manifest_path.exists():
                logger.error(f"Block manifest not found for model {model_id}")
                return []
            
            async with aiofiles.open(manifest_path, 'r') as f:
                manifest = json.loads(await f.read())
            
            # Load encrypted blocks from manifest
            encrypted_blocks = []
            for block_data in manifest.get('blocks', []):
                encrypted_block = EncryptedBlock.from_dict(block_data)
                
                # Load encrypted data from file
                block_file = blocks_dir / f"block_{encrypted_block.block_index + 1:04d}.enc"
                if block_file.exists():
                    async with aiofiles.open(block_file, 'rb') as bf:
                        encrypted_block.encrypted_data = await bf.read()
                    encrypted_blocks.append(encrypted_block)
                else:
                    logger.error(f"Block file not found: {block_file}")
                    return []
            
            # Sort blocks by index
            encrypted_blocks.sort(key=lambda b: b.block_index)
            
            logger.info(f"Loaded {len(encrypted_blocks)} encrypted blocks for model {model_id}")
            return encrypted_blocks
            
        except Exception as e:
            logger.error(f"Failed to load encrypted blocks for model {model_id}: {e}", exc_info=True)
            return []
    
    async def assemble_model_from_blocks(self, model_id: str, 
                                       progress_callback: Optional[callable] = None) -> bool:
        """
        Assemble model from encrypted blocks
        
        Args:
            model_id: Model identifier
            progress_callback: Optional progress callback function
            
        Returns:
            True if assembly successful
        """
        try:
            # Validate license first
            if not await self.validate_license_for_model(model_id):
                logger.error(f"License validation failed for model assembly: {model_id}")
                return False
            
            # Load model metadata
            metadata = await self.load_model_metadata(model_id)
            if not metadata:
                logger.error(f"Cannot assemble model: metadata not found for {model_id}")
                return False
            
            # Check if already assembling
            if model_id in self.active_assemblies:
                logger.warning(f"Model {model_id} is already being assembled")
                return False
            
            # Initialize assembly progress
            progress = AssemblyProgress(
                model_id=model_id,
                total_blocks=metadata.total_blocks,
                assembled_blocks=0,
                total_size=metadata.total_size,
                assembled_size=0,
                assembly_speed=0.0,
                eta=0.0,
                status=AssemblyStatus.ASSEMBLING,
                started_at=datetime.now(),
                last_update=datetime.now()
            )
            
            self.active_assemblies[model_id] = progress
            
            # Load encrypted blocks
            encrypted_blocks = await self.load_encrypted_blocks(model_id)
            if not encrypted_blocks:
                progress.status = AssemblyStatus.FAILED
                progress.error_message = "Failed to load encrypted blocks"
                return False
            
            # Initialize model encryption for decryption
            if not self.model_encryption:
                self.model_encryption = create_model_encryption()
            
            # Create temporary assembly file
            temp_file = self.temp_dir / f"{model_id}_assembly_{int(datetime.now().timestamp())}.tmp"
            progress.temp_file_path = str(temp_file)
            
            # Assemble blocks
            async with aiofiles.open(temp_file, 'wb') as output_file:
                for i, encrypted_block in enumerate(encrypted_blocks):
                    try:
                        # Verify block integrity before decryption
                        if not self._verify_block_integrity(encrypted_block):
                            raise ValueError(f"Block integrity verification failed for block {i}")
                        
                        # Decrypt block
                        decrypted_data = self.model_encryption.decrypt_model_block(encrypted_block)
                        
                        # Write decrypted data
                        await output_file.write(decrypted_data)
                        
                        # Update progress
                        progress.assembled_blocks = i + 1
                        progress.assembled_size += len(decrypted_data)
                        progress.last_update = datetime.now()
                        
                        # Calculate assembly speed and ETA
                        elapsed = (progress.last_update - progress.started_at).total_seconds()
                        if elapsed > 0:
                            progress.assembly_speed = progress.assembled_size / elapsed
                            remaining_size = progress.total_size - progress.assembled_size
                            if progress.assembly_speed > 0:
                                progress.eta = remaining_size / progress.assembly_speed
                        
                        # Call progress callback
                        if progress_callback:
                            try:
                                progress_callback(progress)
                            except Exception as e:
                                logger.warning(f"Progress callback failed: {e}")
                        
                        logger.debug(f"Assembled block {i + 1}/{len(encrypted_blocks)} for model {model_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to decrypt block {i} for model {model_id}: {e}")
                        progress.status = AssemblyStatus.FAILED
                        progress.error_message = f"Block decryption failed: {str(e)}"
                        temp_file.unlink(missing_ok=True)
                        return False
            
            # Move assembled file to final location
            final_path = self._get_model_path(model_id)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temp_file.rename(final_path)
            
            # Verify assembled model integrity
            if not await self._verify_assembled_model(model_id, final_path):
                logger.error(f"Assembled model verification failed for {model_id}")
                progress.status = AssemblyStatus.FAILED
                progress.error_message = "Assembled model verification failed"
                final_path.unlink(missing_ok=True)
                return False
            
            # Update progress
            progress.status = AssemblyStatus.COMPLETED
            progress.assembled_blocks = metadata.total_blocks
            progress.assembled_size = metadata.total_size
            progress.last_update = datetime.now()
            
            # Update statistics
            self.stats['total_assemblies'] += 1
            self.stats['successful_assemblies'] += 1
            
            # Move to history
            self.assembly_history[model_id] = progress
            if model_id in self.active_assemblies:
                del self.active_assemblies[model_id]
            
            logger.info(f"Model assembly completed successfully: {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Model assembly failed for {model_id}: {e}", exc_info=True)
            
            # Update progress on failure
            if model_id in self.active_assemblies:
                progress = self.active_assemblies[model_id]
                progress.status = AssemblyStatus.FAILED
                progress.error_message = str(e)
                self.assembly_history[model_id] = progress
                del self.active_assemblies[model_id]
            
            self.stats['total_assemblies'] += 1
            self.stats['failed_assemblies'] += 1
            
            return False
    
    def _verify_block_integrity(self, encrypted_block: EncryptedBlock) -> bool:
        """
        Verify integrity of an encrypted block
        
        Args:
            encrypted_block: Encrypted block to verify
            
        Returns:
            True if integrity check passed
        """
        try:
            # Verify that encrypted data exists and has expected size
            if not encrypted_block.encrypted_data:
                logger.error(f"No encrypted data in block {encrypted_block.block_id}")
                return False
            
            if len(encrypted_block.encrypted_data) != encrypted_block.encrypted_size:
                logger.error(f"Encrypted data size mismatch in block {encrypted_block.block_id}")
                return False
            
            # Additional integrity checks could be added here
            # such as verifying the authentication tag format, etc.
            
            return True
            
        except Exception as e:
            logger.error(f"Block integrity verification failed: {e}", exc_info=True)
            return False
    
    async def _verify_assembled_model(self, model_id: str, model_path: Path) -> bool:
        """
        Verify integrity of assembled model
        
        Args:
            model_id: Model identifier
            model_path: Path to assembled model file
            
        Returns:
            True if verification passed
        """
        try:
            # Load metadata for expected checksum
            metadata = await self.load_model_metadata(model_id)
            if not metadata:
                logger.error(f"Cannot verify assembled model: metadata not found for {model_id}")
                return False
            
            # Use model verifier for comprehensive verification
            verification_result = await self.model_verifier.verify_model_file(
                model_path=str(model_path),
                expected_checksum=None,  # We'll calculate it ourselves for now
                model_id=model_id
            )
            
            if verification_result.status == VerificationStatus.VERIFIED:
                logger.info(f"Assembled model verification passed for {model_id}")
                return True
            else:
                logger.error(f"Assembled model verification failed for {model_id}: {verification_result.status}")
                return False
                
        except Exception as e:
            logger.error(f"Assembled model verification error for {model_id}: {e}", exc_info=True)
            return False
    
    async def load_model(self, model_id: str, load_options: Dict[str, Any] = None) -> bool:
        """
        Load assembled model into memory with license validation
        
        Args:
            model_id: Model identifier
            load_options: Optional loading configuration
            
        Returns:
            True if model loaded successfully
        """
        try:
            # Validate license at runtime
            if not await self.validate_license_for_model(model_id):
                logger.error(f"License validation failed for model loading: {model_id}")
                return False
            
            # Check if model is already loaded
            if model_id in self.loaded_models:
                logger.info(f"Model {model_id} is already loaded")
                return True
            
            # Check if assembled model exists
            model_path = self._get_model_path(model_id)
            if not model_path.exists():
                logger.error(f"Assembled model not found: {model_path}")
                return False
            
            # Load model metadata
            metadata = await self.load_model_metadata(model_id)
            if not metadata:
                logger.error(f"Cannot load model: metadata not found for {model_id}")
                return False
            
            # Verify model before loading
            if not await self._verify_assembled_model(model_id, model_path):
                logger.error(f"Model verification failed before loading: {model_id}")
                return False
            
            # Load model (this would integrate with the actual model loading system)
            # For now, we'll simulate the loading process
            load_info = {
                'model_id': model_id,
                'model_path': str(model_path),
                'metadata': metadata,
                'loaded_at': datetime.now(),
                'load_options': load_options or {},
                'memory_usage': model_path.stat().st_size,  # Approximate
                'status': 'loaded'
            }
            
            self.loaded_models[model_id] = load_info
            self.stats['models_loaded'] += 1
            
            logger.info(f"Model loaded successfully: {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Model loading failed for {model_id}: {e}", exc_info=True)
            return False
    
    async def unload_model(self, model_id: str) -> bool:
        """
        Unload model from memory
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if model unloaded successfully
        """
        try:
            if model_id not in self.loaded_models:
                logger.warning(f"Model {model_id} is not currently loaded")
                return False
            
            # Unload model (this would integrate with the actual model system)
            del self.loaded_models[model_id]
            self.stats['models_unloaded'] += 1
            
            logger.info(f"Model unloaded successfully: {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"Model unloading failed for {model_id}: {e}", exc_info=True)
            return False
    
    def get_assembly_progress(self, model_id: str) -> Optional[AssemblyProgress]:
        """
        Get assembly progress for a model
        
        Args:
            model_id: Model identifier
            
        Returns:
            AssemblyProgress object or None if not found
        """
        # Check active assemblies first
        if model_id in self.active_assemblies:
            return self.active_assemblies[model_id]
        
        # Check history
        if model_id in self.assembly_history:
            return self.assembly_history[model_id]
        
        return None
    
    def get_loaded_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently loaded models
        
        Returns:
            Dictionary of loaded model information
        """
        return self.loaded_models.copy()
    
    def get_available_models(self) -> List[str]:
        """
        Get list of models available for assembly/loading
        
        Returns:
            List of model IDs
        """
        available_models = []
        
        for model_dir in self.storage_dir.iterdir():
            if model_dir.is_dir() and (model_dir / "metadata.json").exists():
                available_models.append(model_dir.name)
        
        return available_models
    
    def get_assembly_statistics(self) -> Dict[str, Any]:
        """
        Get assembly and loading statistics
        
        Returns:
            Dictionary with statistics
        """
        stats = self.stats.copy()
        stats['active_assemblies'] = len(self.active_assemblies)
        stats['loaded_models_count'] = len(self.loaded_models)
        stats['available_models_count'] = len(self.get_available_models())
        stats['storage_path'] = str(self.storage_dir)
        
        # Calculate success rates
        if stats['total_assemblies'] > 0:
            stats['assembly_success_rate'] = stats['successful_assemblies'] / stats['total_assemblies']
        else:
            stats['assembly_success_rate'] = 0.0
        
        if stats['license_validations'] > 0:
            stats['license_success_rate'] = 1.0 - (stats['license_failures'] / stats['license_validations'])
        else:
            stats['license_success_rate'] = 0.0
        
        return stats
    
    async def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old temporary files
        
        Args:
            max_age_hours: Maximum age of temp files to keep
            
        Returns:
            Number of files cleaned up
        """
        try:
            cleanup_count = 0
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            for temp_file in self.temp_dir.glob("*.tmp"):
                try:
                    file_time = datetime.fromtimestamp(temp_file.stat().st_mtime)
                    if file_time < cutoff_time:
                        temp_file.unlink()
                        cleanup_count += 1
                        logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
            
            logger.info(f"Cleaned up {cleanup_count} temporary files")
            return cleanup_count
            
        except Exception as e:
            logger.error(f"Temp file cleanup failed: {e}", exc_info=True)
            return 0


# Convenience functions

def create_model_assembler(storage_dir: str = "assets/models") -> ModelAssembler:
    """Create and initialize model assembler"""
    return ModelAssembler(storage_dir=storage_dir)


async def assemble_and_load_model(model_id: str, assembler: ModelAssembler = None) -> bool:
    """
    Convenience function to assemble and load a model
    
    Args:
        model_id: Model identifier
        assembler: Optional ModelAssembler instance
        
    Returns:
        True if successful
    """
    if not assembler:
        assembler = create_model_assembler()
    
    # Assemble model from blocks
    assembly_success = await assembler.assemble_model_from_blocks(model_id)
    if not assembly_success:
        return False
    
    # Load assembled model
    load_success = await assembler.load_model(model_id)
    return load_success


if __name__ == "__main__":
    # Example usage and testing
    import tempfile
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    
    async def test_model_assembler():
        """Test model assembler functionality"""
        print("=== Testing Model Assembler ===")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            assembler = ModelAssembler(storage_dir=temp_dir)
            
            # Test metadata operations
            print("\n--- Testing Metadata Operations ---")
            metadata = ModelMetadata(
                model_id="test_model",
                model_name="Test Model",
                model_version="1.0.0",
                model_type="llama",
                total_blocks=5,
                total_size=1024 * 1024,
                block_size=1024 * 200,
                encryption_algorithm="AES-256-GCM",
                checksum_algorithm="SHA-256",
                created_at=datetime.now()
            )
            
            save_success = await assembler.save_model_metadata(metadata)
            print(f"Metadata save: {save_success}")
            
            loaded_metadata = await assembler.load_model_metadata("test_model")
            print(f"Metadata load: {loaded_metadata is not None}")
            
            # Test statistics
            print(f"\n--- Assembly Statistics ---")
            stats = assembler.get_assembly_statistics()
            for key, value in stats.items():
                print(f"{key}: {value}")
    
    # Run test
    asyncio.run(test_model_assembler())