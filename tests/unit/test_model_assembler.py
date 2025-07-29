"""
Unit Tests for Model Assembler - TikTrue Platform

Tests for secure model block assembly and loading system for client nodes,
including license validation and metadata management.

Test Coverage:
- Model block assembly from encrypted blocks
- Secure model loading with license validation
- Model metadata management and version tracking
- Block integrity verification during assembly
- Assembly progress tracking and error handling
- License-based access control for model loading
"""

import asyncio
import json
import pytest
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

# Import the classes we're testing
from models.model_assembler import (
    ModelAssembler, ModelMetadata, AssemblyStatus, AssemblyProgress,
    create_model_assembler, assemble_and_load_model
)
from models.model_encryption import EncryptedBlock
from models.model_verification import VerificationStatus, VerificationResult
from license_models import SubscriptionTier, LicenseInfo


class TestModelAssembler:
    """Test suite for ModelAssembler class"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory for tests"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_license_enforcer(self):
        """Mock license enforcer for testing"""
        mock_enforcer = Mock()
        mock_license = LicenseInfo(
            license_key="test_license_key",
            user_id="test_user",
            plan=SubscriptionTier.PRO,
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=10,
            allowed_models=["test_model_1", "test_model_2"],
            is_active=True
        )
        mock_enforcer.current_license = mock_license
        mock_enforcer.get_license_status.return_value = {"valid": True}
        return mock_enforcer
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample model metadata for testing"""
        return ModelMetadata(
            model_id="test_model",
            model_name="Test Model",
            model_version="1.0.0",
            model_type="llama",
            total_blocks=3,
            total_size=3072,  # 3KB total
            block_size=1024,  # 1KB per block
            encryption_algorithm="AES-256-GCM",
            checksum_algorithm="SHA-256",
            created_at=datetime.now(),
            license_requirements={"minimum_tier": "PRO"},
            tags=["test", "small"]
        )
    
    @pytest.fixture
    def sample_encrypted_blocks(self):
        """Sample encrypted blocks for testing"""
        blocks = []
        for i in range(3):
            block = EncryptedBlock(
                block_id=f"test_model_block_{i}",
                model_id="test_model",
                block_index=i,
                encrypted_data=b"encrypted_data_" + str(i).encode() * 100,  # Mock encrypted data
                nonce=b"nonce_" + str(i).encode() * 2,
                tag=b"tag_" + str(i).encode() * 4,
                key_id="test_key",
                original_size=1024,
                encrypted_size=len(b"encrypted_data_" + str(i).encode() * 100),
                checksum=hashlib.sha256(b"original_data_" + str(i).encode() * 100).hexdigest(),
                created_at=datetime.now()
            )
            blocks.append(block)
        return blocks
    
    @pytest.fixture
    def model_assembler(self, temp_storage, mock_license_enforcer):
        """Create ModelAssembler instance for testing"""
        with patch('models.model_assembler.get_license_enforcer', return_value=mock_license_enforcer):
            assembler = ModelAssembler(storage_dir=temp_storage)
            return assembler
    
    def test_initialization(self, model_assembler, temp_storage):
        """Test ModelAssembler initialization"""
        assert model_assembler.storage_dir == Path(temp_storage)
        assert model_assembler.storage_dir.exists()
        assert model_assembler.temp_dir.exists()
        assert isinstance(model_assembler.active_assemblies, dict)
        assert isinstance(model_assembler.assembly_history, dict)
        assert isinstance(model_assembler.loaded_models, dict)
        assert isinstance(model_assembler.metadata_cache, dict)
        assert model_assembler.stats['total_assemblies'] == 0
    
    @pytest.mark.asyncio
    async def test_metadata_operations(self, model_assembler, sample_metadata):
        """Test model metadata save and load operations"""
        # Test metadata saving
        save_result = await model_assembler.save_model_metadata(sample_metadata)
        assert save_result is True
        
        # Verify metadata file exists
        metadata_path = model_assembler._get_metadata_path(sample_metadata.model_id)
        assert metadata_path.exists()
        
        # Test metadata loading
        loaded_metadata = await model_assembler.load_model_metadata(sample_metadata.model_id)
        assert loaded_metadata is not None
        assert loaded_metadata.model_id == sample_metadata.model_id
        assert loaded_metadata.model_name == sample_metadata.model_name
        assert loaded_metadata.total_blocks == sample_metadata.total_blocks
        assert loaded_metadata.license_requirements == sample_metadata.license_requirements
        
        # Test metadata caching
        assert sample_metadata.model_id in model_assembler.metadata_cache
        
        # Test loading non-existent metadata
        non_existent = await model_assembler.load_model_metadata("non_existent_model")
        assert non_existent is None
    
    @pytest.mark.asyncio
    async def test_license_validation(self, model_assembler, sample_metadata, mock_license_enforcer):
        """Test license validation for model loading"""
        # Save metadata first
        await model_assembler.save_model_metadata(sample_metadata)
        
        # Test successful license validation
        result = await model_assembler.validate_license_for_model(sample_metadata.model_id)
        assert result is True
        assert model_assembler.stats['license_validations'] == 1
        
        # Test with invalid license
        mock_license_enforcer.get_license_status.return_value = {"valid": False}
        result = await model_assembler.validate_license_for_model(sample_metadata.model_id)
        assert result is False
        assert model_assembler.stats['license_failures'] == 1
        
        # Test with insufficient tier
        mock_license_enforcer.get_license_status.return_value = {"valid": True}
        mock_license_enforcer.current_license.plan = SubscriptionTier.FREE
        result = await model_assembler.validate_license_for_model(sample_metadata.model_id)
        assert result is False
        assert model_assembler.stats['license_failures'] == 2
        
        # Test with no metadata
        result = await model_assembler.validate_license_for_model("non_existent_model")
        assert result is False
        assert model_assembler.stats['license_failures'] == 3
    
    @pytest.mark.asyncio
    async def test_load_encrypted_blocks(self, model_assembler, sample_metadata, sample_encrypted_blocks):
        """Test loading encrypted blocks from storage"""
        # Setup blocks directory and manifest
        blocks_dir = model_assembler._get_blocks_dir(sample_metadata.model_id)
        blocks_dir.mkdir(parents=True, exist_ok=True)
        
        # Create manifest
        manifest = {
            'model_id': sample_metadata.model_id,
            'total_blocks': len(sample_encrypted_blocks),
            'blocks': [block.to_dict() for block in sample_encrypted_blocks]
        }
        
        manifest_path = blocks_dir / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Create block files
        for i, block in enumerate(sample_encrypted_blocks):
            block_file = blocks_dir / f"block_{i + 1:04d}.enc"
            with open(block_file, 'wb') as f:
                f.write(block.encrypted_data)
        
        # Test loading blocks
        loaded_blocks = await model_assembler.load_encrypted_blocks(sample_metadata.model_id)
        assert len(loaded_blocks) == len(sample_encrypted_blocks)
        assert all(isinstance(block, EncryptedBlock) for block in loaded_blocks)
        assert loaded_blocks[0].block_index == 0
        assert loaded_blocks[-1].block_index == len(sample_encrypted_blocks) - 1
        
        # Test loading with missing manifest
        manifest_path.unlink()
        loaded_blocks = await model_assembler.load_encrypted_blocks(sample_metadata.model_id)
        assert len(loaded_blocks) == 0
        
        # Test loading with missing blocks directory
        blocks_dir.rmdir()
        loaded_blocks = await model_assembler.load_encrypted_blocks(sample_metadata.model_id)
        assert len(loaded_blocks) == 0
    
    def test_block_integrity_verification(self, model_assembler, sample_encrypted_blocks):
        """Test encrypted block integrity verification"""
        # Test valid block
        valid_block = sample_encrypted_blocks[0]
        assert model_assembler._verify_block_integrity(valid_block) is True
        
        # Test block with no encrypted data
        invalid_block = EncryptedBlock(
            block_id="invalid_block",
            model_id="test_model",
            block_index=0,
            encrypted_data=b"",  # Empty data
            nonce=b"nonce",
            tag=b"tag",
            key_id="key",
            original_size=1024,
            encrypted_size=0,
            checksum="hash",
            created_at=datetime.now()
        )
        assert model_assembler._verify_block_integrity(invalid_block) is False
        
        # Test block with size mismatch
        size_mismatch_block = sample_encrypted_blocks[0]
        size_mismatch_block.encrypted_size = 999  # Wrong size
        assert model_assembler._verify_block_integrity(size_mismatch_block) is False
    
    @pytest.mark.asyncio
    async def test_model_assembly_success(self, model_assembler, sample_metadata, sample_encrypted_blocks):
        """Test successful model assembly from encrypted blocks"""
        # Setup metadata and blocks
        await model_assembler.save_model_metadata(sample_metadata)
        
        blocks_dir = model_assembler._get_blocks_dir(sample_metadata.model_id)
        blocks_dir.mkdir(parents=True, exist_ok=True)
        
        # Create manifest and block files
        manifest = {
            'model_id': sample_metadata.model_id,
            'total_blocks': len(sample_encrypted_blocks),
            'blocks': [block.to_dict() for block in sample_encrypted_blocks]
        }
        
        with open(blocks_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f)
        
        for i, block in enumerate(sample_encrypted_blocks):
            block_file = blocks_dir / f"block_{i + 1:04d}.enc"
            with open(block_file, 'wb') as f:
                f.write(block.encrypted_data)
        
        # Mock model encryption for decryption
        mock_encryption = Mock()
        mock_encryption.decrypt_model_block.side_effect = [
            b"decrypted_data_0" * 100,
            b"decrypted_data_1" * 100,
            b"decrypted_data_2" * 100
        ]
        model_assembler.model_encryption = mock_encryption
        
        # Mock model verification
        mock_verifier = AsyncMock()
        mock_verifier.verify_model_file.return_value = VerificationResult(
            model_id=sample_metadata.model_id,
            status=VerificationStatus.VERIFIED
        )
        model_assembler.model_verifier = mock_verifier
        
        # Test assembly
        progress_updates = []
        def progress_callback(progress):
            progress_updates.append(progress.progress_percentage)
        
        result = await model_assembler.assemble_model_from_blocks(
            sample_metadata.model_id, 
            progress_callback=progress_callback
        )
        
        assert result is True
        assert model_assembler.stats['successful_assemblies'] == 1
        assert len(progress_updates) > 0
        assert sample_metadata.model_id in model_assembler.assembly_history
        
        # Verify assembled file exists
        model_path = model_assembler._get_model_path(sample_metadata.model_id)
        assert model_path.exists()
    
    @pytest.mark.asyncio
    async def test_model_assembly_license_failure(self, model_assembler, sample_metadata, mock_license_enforcer):
        """Test model assembly failure due to license validation"""
        await model_assembler.save_model_metadata(sample_metadata)
        
        # Mock license failure
        mock_license_enforcer.get_license_status.return_value = {"valid": False}
        
        result = await model_assembler.assemble_model_from_blocks(sample_metadata.model_id)
        assert result is False
        assert model_assembler.stats['failed_assemblies'] == 1
    
    @pytest.mark.asyncio
    async def test_model_assembly_concurrent_prevention(self, model_assembler, sample_metadata):
        """Test prevention of concurrent assembly of the same model"""
        await model_assembler.save_model_metadata(sample_metadata)
        
        # Simulate active assembly
        progress = AssemblyProgress(
            model_id=sample_metadata.model_id,
            total_blocks=3,
            assembled_blocks=1,
            total_size=3072,
            assembled_size=1024,
            assembly_speed=100.0,
            eta=20.0,
            status=AssemblyStatus.ASSEMBLING,
            started_at=datetime.now(),
            last_update=datetime.now()
        )
        model_assembler.active_assemblies[sample_metadata.model_id] = progress
        
        # Test that second assembly is prevented
        result = await model_assembler.assemble_model_from_blocks(sample_metadata.model_id)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_model_loading_success(self, model_assembler, sample_metadata):
        """Test successful model loading with license validation"""
        # Setup metadata and assembled model file
        await model_assembler.save_model_metadata(sample_metadata)
        
        model_path = model_assembler._get_model_path(sample_metadata.model_id)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create mock assembled model file
        test_content = b"assembled_model_content" * 100
        with open(model_path, 'wb') as f:
            f.write(test_content)
        
        # Mock model verification
        mock_verifier = AsyncMock()
        mock_verifier.verify_model_file.return_value = VerificationResult(
            model_id=sample_metadata.model_id,
            status=VerificationStatus.VERIFIED
        )
        model_assembler.model_verifier = mock_verifier
        
        # Test model loading
        result = await model_assembler.load_model(sample_metadata.model_id)
        assert result is True
        assert model_assembler.stats['models_loaded'] == 1
        assert sample_metadata.model_id in model_assembler.loaded_models
        
        # Test loading already loaded model
        result = await model_assembler.load_model(sample_metadata.model_id)
        assert result is True  # Should succeed but not increment counter
        assert model_assembler.stats['models_loaded'] == 1
    
    @pytest.mark.asyncio
    async def test_model_loading_failures(self, model_assembler, sample_metadata, mock_license_enforcer):
        """Test various model loading failure scenarios"""
        await model_assembler.save_model_metadata(sample_metadata)
        
        # Test license failure
        mock_license_enforcer.get_license_status.return_value = {"valid": False}
        result = await model_assembler.load_model(sample_metadata.model_id)
        assert result is False
        
        # Reset license
        mock_license_enforcer.get_license_status.return_value = {"valid": True}
        
        # Test missing assembled model file
        result = await model_assembler.load_model(sample_metadata.model_id)
        assert result is False
        
        # Test missing metadata
        result = await model_assembler.load_model("non_existent_model")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_model_unloading(self, model_assembler, sample_metadata):
        """Test model unloading functionality"""
        # Setup loaded model
        model_assembler.loaded_models[sample_metadata.model_id] = {
            'model_id': sample_metadata.model_id,
            'loaded_at': datetime.now(),
            'status': 'loaded'
        }
        
        # Test successful unloading
        result = await model_assembler.unload_model(sample_metadata.model_id)
        assert result is True
        assert model_assembler.stats['models_unloaded'] == 1
        assert sample_metadata.model_id not in model_assembler.loaded_models
        
        # Test unloading non-loaded model
        result = await model_assembler.unload_model(sample_metadata.model_id)
        assert result is False
    
    def test_assembly_progress_tracking(self, model_assembler):
        """Test assembly progress tracking functionality"""
        model_id = "test_model"
        
        # Create progress object
        progress = AssemblyProgress(
            model_id=model_id,
            total_blocks=10,
            assembled_blocks=5,
            total_size=10240,
            assembled_size=5120,
            assembly_speed=1024.0,
            eta=5.0,
            status=AssemblyStatus.ASSEMBLING,
            started_at=datetime.now(),
            last_update=datetime.now()
        )
        
        # Test progress percentage calculation
        assert progress.progress_percentage == 50.0
        
        # Test progress serialization
        progress_dict = progress.to_dict()
        assert progress_dict['progress_percentage'] == 50.0
        assert progress_dict['status'] == 'assembling'
        
        # Test progress tracking in assembler
        model_assembler.active_assemblies[model_id] = progress
        retrieved_progress = model_assembler.get_assembly_progress(model_id)
        assert retrieved_progress == progress
        
        # Test progress in history
        model_assembler.assembly_history[model_id] = progress
        del model_assembler.active_assemblies[model_id]
        retrieved_progress = model_assembler.get_assembly_progress(model_id)
        assert retrieved_progress == progress
    
    def test_available_models_detection(self, model_assembler, sample_metadata):
        """Test detection of available models"""
        # Initially no models
        available = model_assembler.get_available_models()
        assert len(available) == 0
        
        # Add a model with metadata
        asyncio.run(model_assembler.save_model_metadata(sample_metadata))
        available = model_assembler.get_available_models()
        assert len(available) == 1
        assert sample_metadata.model_id in available
        
        # Add another model directory without metadata
        fake_model_dir = model_assembler.storage_dir / "fake_model"
        fake_model_dir.mkdir()
        available = model_assembler.get_available_models()
        assert len(available) == 1  # Should still be 1 because fake_model has no metadata
    
    def test_loaded_models_tracking(self, model_assembler):
        """Test loaded models tracking"""
        # Initially no loaded models
        loaded = model_assembler.get_loaded_models()
        assert len(loaded) == 0
        
        # Add loaded model
        model_info = {
            'model_id': 'test_model',
            'loaded_at': datetime.now(),
            'status': 'loaded'
        }
        model_assembler.loaded_models['test_model'] = model_info
        
        loaded = model_assembler.get_loaded_models()
        assert len(loaded) == 1
        assert 'test_model' in loaded
        assert loaded['test_model']['status'] == 'loaded'
    
    def test_assembly_statistics(self, model_assembler):
        """Test assembly statistics tracking"""
        # Initial statistics
        stats = model_assembler.get_assembly_statistics()
        assert stats['total_assemblies'] == 0
        assert stats['successful_assemblies'] == 0
        assert stats['failed_assemblies'] == 0
        assert stats['assembly_success_rate'] == 0.0
        assert stats['license_success_rate'] == 0.0
        
        # Update statistics
        model_assembler.stats['total_assemblies'] = 10
        model_assembler.stats['successful_assemblies'] = 8
        model_assembler.stats['failed_assemblies'] = 2
        model_assembler.stats['license_validations'] = 15
        model_assembler.stats['license_failures'] = 3
        
        stats = model_assembler.get_assembly_statistics()
        assert stats['total_assemblies'] == 10
        assert stats['successful_assemblies'] == 8
        assert stats['failed_assemblies'] == 2
        assert stats['assembly_success_rate'] == 0.8
        assert stats['license_success_rate'] == 0.8  # (15-3)/15
    
    @pytest.mark.asyncio
    async def test_temp_file_cleanup(self, model_assembler):
        """Test temporary file cleanup functionality"""
        # Create some temporary files
        temp_files = []
        for i in range(3):
            temp_file = model_assembler.temp_dir / f"test_temp_{i}.tmp"
            with open(temp_file, 'w') as f:
                f.write(f"temp content {i}")
            temp_files.append(temp_file)
        
        # Make one file old
        old_time = datetime.now() - timedelta(hours=25)
        old_timestamp = old_time.timestamp()
        temp_files[0].touch(times=(old_timestamp, old_timestamp))
        
        # Test cleanup
        cleaned_count = await model_assembler.cleanup_temp_files(max_age_hours=24)
        assert cleaned_count == 1
        assert not temp_files[0].exists()
        assert temp_files[1].exists()
        assert temp_files[2].exists()


class TestModelAssemblerIntegration:
    """Integration tests for ModelAssembler with other components"""
    
    @pytest.fixture
    def integration_setup(self):
        """Setup for integration tests"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield {
                'storage_dir': temp_dir,
                'model_id': 'integration_test_model'
            }
    
    @pytest.mark.asyncio
    async def test_full_assembly_and_loading_workflow(self, integration_setup):
        """Test complete workflow from blocks to loaded model"""
        storage_dir = integration_setup['storage_dir']
        model_id = integration_setup['model_id']
        
        # Create assembler
        assembler = create_model_assembler(storage_dir)
        
        # This would be a more comprehensive integration test
        # that tests the entire flow with real encrypted blocks
        pass
    
    def test_error_recovery_mechanisms(self, integration_setup):
        """Test error recovery during assembly"""
        # Test recovery from corrupted blocks, network failures, etc.
        pass
    
    def test_memory_management_large_models(self, integration_setup):
        """Test memory-efficient assembly for large models"""
        # Test streaming assembly without loading entire model into memory
        pass


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_create_model_assembler(self):
        """Test model assembler creation function"""
        with tempfile.TemporaryDirectory() as temp_dir:
            assembler = create_model_assembler(temp_dir)
            assert isinstance(assembler, ModelAssembler)
            assert assembler.storage_dir == Path(temp_dir)
    
    @pytest.mark.asyncio
    async def test_assemble_and_load_model(self):
        """Test convenience function for assembly and loading"""
        with tempfile.TemporaryDirectory() as temp_dir:
            assembler = create_model_assembler(temp_dir)
            
            # Mock the assembly and loading methods
            with patch.object(assembler, 'assemble_model_from_blocks', return_value=True):
                with patch.object(assembler, 'load_model', return_value=True):
                    result = await assemble_and_load_model('test_model', assembler)
                    assert result is True
            
            # Test with assembly failure
            with patch.object(assembler, 'assemble_model_from_blocks', return_value=False):
                result = await assemble_and_load_model('test_model', assembler)
                assert result is False


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])