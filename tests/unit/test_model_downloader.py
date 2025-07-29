"""
Unit Tests for Model Downloader - TikTrue Platform

Tests for secure model downloading with license-based access control,
integrity verification, and automatic block division and encryption.

Test Coverage:
- Authenticated model download from backend server
- Model integrity verification with cryptographic checksums
- Automatic model block division and encryption during download
- License-based access control validation
- Download progress tracking and error handling
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
from models.model_downloader import (
    ModelDownloader, ModelInfo, ModelTier, DownloadStatus, DownloadProgress
)
from license_models import SubscriptionTier, LicenseInfo


class TestModelDownloader:
    """Test suite for ModelDownloader class"""
    
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
    def sample_model_info(self):
        """Sample model information for testing"""
        return ModelInfo(
            model_id="test_model_1",
            model_name="Test Model",
            model_version="1.0.0",
            model_size=1024 * 1024,  # 1MB
            required_tier=ModelTier.PRO,
            download_url="https://api.tiktrue.com/models/test_model_1/download",
            checksum="a" * 64,  # Mock SHA-256 checksum
            description="Test model for unit testing"
        )
    
    @pytest.fixture
    def model_downloader(self, temp_storage, mock_license_enforcer):
        """Create ModelDownloader instance for testing"""
        with patch('models.model_downloader.get_license_enforcer', return_value=mock_license_enforcer):
            downloader = ModelDownloader(storage_dir=temp_storage)
            return downloader
    
    def test_initialization(self, model_downloader, temp_storage):
        """Test ModelDownloader initialization"""
        assert model_downloader.storage_dir == Path(temp_storage)
        assert model_downloader.storage_dir.exists()
        assert isinstance(model_downloader.model_registry, dict)
        assert isinstance(model_downloader.active_downloads, dict)
        assert isinstance(model_downloader.download_history, dict)
        assert model_downloader.stats['total_downloads'] == 0
    
    def test_model_registry_operations(self, model_downloader, sample_model_info):
        """Test model registry registration and persistence"""
        # Test model registration
        result = model_downloader.register_model(sample_model_info)
        assert result is True
        assert sample_model_info.model_id in model_downloader.model_registry
        
        # Test registry persistence
        registry_file = model_downloader.storage_dir / "model_registry.json"
        assert registry_file.exists()
        
        # Test registry loading
        new_downloader = ModelDownloader(storage_dir=str(model_downloader.storage_dir))
        assert sample_model_info.model_id in new_downloader.model_registry
        assert new_downloader.model_registry[sample_model_info.model_id].model_name == sample_model_info.model_name
    
    def test_license_based_access_control(self, model_downloader, mock_license_enforcer):
        """Test license-based model access validation"""
        # Test with PRO license accessing PRO model
        pro_model = ModelInfo(
            model_id="pro_model",
            model_name="Pro Model",
            model_version="1.0.0",
            model_size=1024,
            required_tier=ModelTier.PRO,
            download_url="https://example.com",
            checksum="b" * 64
        )
        model_downloader.register_model(pro_model)
        assert model_downloader.validate_model_access("pro_model") is True
        
        # Test with PRO license accessing ENTERPRISE model
        enterprise_model = ModelInfo(
            model_id="enterprise_model",
            model_name="Enterprise Model",
            model_version="1.0.0",
            model_size=1024,
            required_tier=ModelTier.ENTERPRISE,
            download_url="https://example.com",
            checksum="c" * 64
        )
        model_downloader.register_model(enterprise_model)
        assert model_downloader.validate_model_access("enterprise_model") is False
        
        # Test with no valid license
        mock_license_enforcer.current_license = None
        mock_license_enforcer.get_license_status.return_value = {"valid": False}
        
        free_model = ModelInfo(
            model_id="free_model",
            model_name="Free Model",
            model_version="1.0.0",
            model_size=1024,
            required_tier=ModelTier.FREE,
            download_url="https://example.com",
            checksum="d" * 64
        )
        model_downloader.register_model(free_model)
        assert model_downloader.validate_model_access("free_model") is True
        assert model_downloader.validate_model_access("pro_model") is False
    
    def test_get_available_models(self, model_downloader, mock_license_enforcer):
        """Test getting available models based on license tier"""
        # Register models with different tiers
        models = [
            ModelInfo("free_1", "Free Model 1", "1.0", 1024, ModelTier.FREE, "url", "hash1"),
            ModelInfo("pro_1", "Pro Model 1", "1.0", 1024, ModelTier.PRO, "url", "hash2"),
            ModelInfo("ent_1", "Enterprise Model 1", "1.0", 1024, ModelTier.ENTERPRISE, "url", "hash3")
        ]
        
        for model in models:
            model_downloader.register_model(model)
        
        # Test with PRO license
        available = model_downloader.get_available_models()
        available_ids = [m.model_id for m in available]
        assert "free_1" in available_ids
        assert "pro_1" in available_ids
        assert "ent_1" not in available_ids
        
        # Test with FREE license
        mock_license_enforcer.current_license.plan = SubscriptionTier.FREE
        available = model_downloader.get_available_models()
        available_ids = [m.model_id for m in available]
        assert "free_1" in available_ids
        assert "pro_1" not in available_ids
        assert "ent_1" not in available_ids
    
    def test_model_integrity_verification(self, model_downloader, temp_storage):
        """Test cryptographic model integrity verification"""
        # Create a test file with known content
        test_file = Path(temp_storage) / "test_model.bin"
        test_content = b"This is test model content for integrity verification"
        
        with open(test_file, 'wb') as f:
            f.write(test_content)
        
        # Calculate expected checksum
        expected_checksum = hashlib.sha256(test_content).hexdigest()
        
        # Test successful verification
        assert model_downloader._verify_model_integrity(test_file, expected_checksum) is True
        
        # Test failed verification with wrong checksum
        wrong_checksum = "0" * 64
        assert model_downloader._verify_model_integrity(test_file, wrong_checksum) is False
        
        # Test with non-existent file
        non_existent = Path(temp_storage) / "non_existent.bin"
        assert model_downloader._verify_model_integrity(non_existent, expected_checksum) is False
    
    @pytest.mark.asyncio
    async def test_download_model_success(self, model_downloader, sample_model_info):
        """Test successful model download with mocked backend"""
        # Register the model
        model_downloader.register_model(sample_model_info)
        
        # Mock the backend API client
        mock_api_client = AsyncMock()
        mock_api_client.is_authenticated.return_value = True
        mock_api_client.get_model_download_url.return_value = Mock(
            success=True,
            data={
                'download_url': 'https://example.com/model.bin',
                'checksum': sample_model_info.checksum
            }
        )
        mock_api_client.download_model_file.return_value = Mock(success=True)
        
        # Mock model encryption
        mock_encryption = AsyncMock()
        mock_encryption.encrypt_model_file.return_value = [Mock(block_id="block_1")]
        
        with patch('models.model_downloader.BackendAPIClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_api_client
            
            with patch.object(model_downloader, '_verify_model_integrity', return_value=True):
                with patch.object(model_downloader, '_divide_and_encrypt_model', return_value=True):
                    # Test download
                    result = await model_downloader.download_model(sample_model_info.model_id)
                    assert result is True
                    assert model_downloader.stats['successful_downloads'] == 1
                    assert sample_model_info.model_id in model_downloader.download_history
    
    @pytest.mark.asyncio
    async def test_download_model_authentication_failure(self, model_downloader, sample_model_info):
        """Test model download failure due to authentication"""
        model_downloader.register_model(sample_model_info)
        
        # Mock unauthenticated API client
        mock_api_client = AsyncMock()
        mock_api_client.is_authenticated.return_value = False
        
        with patch('models.model_downloader.BackendAPIClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_api_client
            
            result = await model_downloader.download_model(sample_model_info.model_id)
            assert result is False
            assert model_downloader.stats['failed_downloads'] == 1
    
    @pytest.mark.asyncio
    async def test_download_model_integrity_failure(self, model_downloader, sample_model_info):
        """Test model download failure due to integrity verification"""
        model_downloader.register_model(sample_model_info)
        
        # Mock successful API calls but failed integrity check
        mock_api_client = AsyncMock()
        mock_api_client.is_authenticated.return_value = True
        mock_api_client.get_model_download_url.return_value = Mock(
            success=True,
            data={'download_url': 'https://example.com/model.bin', 'checksum': 'valid_checksum'}
        )
        mock_api_client.download_model_file.return_value = Mock(success=True)
        
        with patch('models.model_downloader.BackendAPIClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_api_client
            
            with patch.object(model_downloader, '_verify_model_integrity', return_value=False):
                result = await model_downloader.download_model(sample_model_info.model_id)
                assert result is False
                assert model_downloader.stats['failed_downloads'] == 1
    
    @pytest.mark.asyncio
    async def test_automatic_block_division_and_encryption(self, model_downloader, temp_storage):
        """Test automatic model block division and encryption during download"""
        # Create a test model file
        model_id = "test_model"
        model_file = Path(temp_storage) / model_id / "model.bin"
        model_file.parent.mkdir(parents=True, exist_ok=True)
        
        test_content = b"Test model content for block division" * 1000  # Make it larger
        with open(model_file, 'wb') as f:
            f.write(test_content)
        
        # Mock model encryption
        mock_encrypted_blocks = [
            Mock(block_id="block_1", block_index=0, original_size=1000, encrypted_size=1016, checksum="hash1", key_id="key1"),
            Mock(block_id="block_2", block_index=1, original_size=1000, encrypted_size=1016, checksum="hash2", key_id="key1")
        ]
        
        mock_encryption = AsyncMock()
        mock_encryption.encrypt_model_file.return_value = mock_encrypted_blocks
        model_downloader.model_encryption = mock_encryption
        
        # Test block division and encryption
        result = await model_downloader._divide_and_encrypt_model(model_id, model_file)
        assert result is True
        
        # Verify encryption was called
        mock_encryption.encrypt_model_file.assert_called_once_with(
            model_id=model_id,
            file_path=str(model_file)
        )
        
        # Verify metadata was saved
        metadata_file = Path(temp_storage) / model_id / "encryption_metadata.json"
        assert metadata_file.exists()
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
            assert metadata['model_id'] == model_id
            assert metadata['total_blocks'] == 2
            assert metadata['encryption_algorithm'] == 'AES-256-GCM'
            assert len(metadata['blocks']) == 2
    
    def test_download_progress_tracking(self, model_downloader):
        """Test download progress tracking functionality"""
        model_id = "test_model"
        
        # Create progress object
        progress = DownloadProgress(
            model_id=model_id,
            total_size=1000,
            downloaded_size=500,
            download_speed=100.0,
            eta=5.0,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(),
            last_update=datetime.now()
        )
        
        # Test progress percentage calculation
        assert progress.progress_percentage == 50.0
        
        # Test progress serialization
        progress_dict = progress.to_dict()
        assert progress_dict['progress_percentage'] == 50.0
        assert progress_dict['status'] == 'downloading'
        
        # Test progress tracking in downloader
        model_downloader.active_downloads[model_id] = progress
        retrieved_progress = model_downloader.get_download_progress(model_id)
        assert retrieved_progress == progress
    
    def test_download_statistics(self, model_downloader):
        """Test download statistics tracking"""
        # Initial statistics
        stats = model_downloader.get_download_statistics()
        assert stats['total_downloads'] == 0
        assert stats['successful_downloads'] == 0
        assert stats['failed_downloads'] == 0
        assert stats['success_rate'] == 0.0
        
        # Update statistics
        model_downloader.stats['total_downloads'] = 10
        model_downloader.stats['successful_downloads'] = 8
        model_downloader.stats['failed_downloads'] = 2
        model_downloader.stats['bytes_downloaded'] = 1024 * 1024 * 100  # 100MB
        
        stats = model_downloader.get_download_statistics()
        assert stats['total_downloads'] == 10
        assert stats['successful_downloads'] == 8
        assert stats['failed_downloads'] == 2
        assert stats['success_rate'] == 0.8
        assert stats['bytes_downloaded'] == 1024 * 1024 * 100
    
    def test_concurrent_download_prevention(self, model_downloader, sample_model_info):
        """Test prevention of concurrent downloads of the same model"""
        model_downloader.register_model(sample_model_info)
        
        # Simulate active download
        progress = DownloadProgress(
            model_id=sample_model_info.model_id,
            total_size=1000,
            downloaded_size=0,
            download_speed=0.0,
            eta=0.0,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(),
            last_update=datetime.now()
        )
        model_downloader.active_downloads[sample_model_info.model_id] = progress
        
        # Test that second download is prevented
        async def test_concurrent():
            result = await model_downloader.download_model(sample_model_info.model_id)
            return result
        
        # This should return False because download is already active
        result = asyncio.run(test_concurrent())
        assert result is False
    
    def test_model_access_validation_edge_cases(self, model_downloader, mock_license_enforcer):
        """Test edge cases in model access validation"""
        # Test with non-existent model
        assert model_downloader.validate_model_access("non_existent_model") is False
        
        # Test with model-specific permissions
        mock_license_enforcer.current_license.allowed_models = ["allowed_model"]
        
        restricted_model = ModelInfo(
            model_id="restricted_model",
            model_name="Restricted Model",
            model_version="1.0.0",
            model_size=1024,
            required_tier=ModelTier.PRO,
            download_url="https://example.com",
            checksum="e" * 64
        )
        model_downloader.register_model(restricted_model)
        
        # Should be blocked because it's not in allowed_models list
        assert model_downloader.validate_model_access("restricted_model") is False
        assert model_downloader.stats['premium_blocks'] > 0


class TestModelDownloaderIntegration:
    """Integration tests for ModelDownloader with other components"""
    
    @pytest.fixture
    def integration_setup(self):
        """Setup for integration tests"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield {
                'storage_dir': temp_dir,
                'backend_url': 'https://test-api.tiktrue.com'
            }
    
    @pytest.mark.asyncio
    async def test_full_download_workflow(self, integration_setup):
        """Test complete download workflow from authentication to encryption"""
        # This would be a more comprehensive integration test
        # that tests the entire flow with mocked backend responses
        pass
    
    def test_error_recovery_mechanisms(self, integration_setup):
        """Test error recovery and retry mechanisms"""
        # Test network failures, timeout handling, etc.
        pass
    
    def test_resumable_download_functionality(self, integration_setup):
        """Test resumable download capabilities"""
        # Test pause/resume functionality
        pass


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])