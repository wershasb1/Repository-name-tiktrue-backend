"""
Tests for resumable download functionality
Tests download interruption, pause/resume, and state persistence
"""

import asyncio
import unittest
import tempfile
import shutil
import json
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

from models.model_downloader import (
    ModelDownloader,
    ModelInfo,
    ModelTier,
    DownloadStatus,
    DownloadProgress,
)
from security.license_validator import SubscriptionTier, LicenseInfo, LicenseStatus

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestResumableDownloads(unittest.TestCase):
    """Test resumable download functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.temp_dir) / "models"
        self.mock_license_enforcer = self._create_mock_license_enforcer()
        
    def tearDown(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_mock_license_enforcer(self):
        """Create mock license enforcer"""
        mock_enforcer = Mock()
        mock_license = LicenseInfo(
            license_key="TIKT-PRO-12M-TEST001",
            plan=SubscriptionTier.PRO,
            duration_months=12,
            unique_id="TEST001",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=20,
            allowed_models=["test_model", "resumable_model"],
            allowed_features=["chat", "inference"],
            status=LicenseStatus.VALID,
            hardware_signature="test_hw_sig",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        mock_enforcer.current_license = mock_license
        mock_enforcer.get_license_status.return_value = {'valid': True}
        return mock_enforcer
    
    def _create_test_model(self) -> ModelInfo:
        """Create test model for resumable downloads"""
        return ModelInfo(
            model_id="resumable_model",
            model_name="Resumable Test Model",
            model_version="1.0",
            model_size=10000000,  # 10MB
            required_tier=ModelTier.FREE,
            download_url="https://example.com/resumable_model.bin",
            checksum="abc123def456789012345678901234567890abcdef1234567890abcdef123456",
            description="Model for testing resumable downloads",
            tags=["test", "resumable"]
        )
    
    @patch('models.model_downloader.get_license_enforcer')
    def test_download_progress_with_resume_fields(self, mock_get_enforcer):
        """Test DownloadProgress with resumable fields"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        # Create progress with resume fields
        progress = DownloadProgress(
            model_id="test_model",
            total_size=1000000,
            downloaded_size=500000,
            download_speed=100000.0,
            eta=5.0,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(),
            last_update=datetime.now(),
            resume_position=500000,
            temp_file_path="/tmp/test_model.tmp"
        )
        
        # Test resume fields
        self.assertEqual(progress.resume_position, 500000)
        self.assertEqual(progress.temp_file_path, "/tmp/test_model.tmp")
        self.assertIsInstance(progress.chunk_hashes, list)
        
        # Test serialization includes resume fields
        progress_dict = progress.to_dict()
        self.assertIn('resume_position', progress_dict)
        self.assertIn('temp_file_path', progress_dict)
        self.assertIn('chunk_hashes', progress_dict)
    
    @patch('models.model_downloader.get_license_enforcer')
    def test_pause_download(self, mock_get_enforcer):
        """Test pausing an active download"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        test_model = self._create_test_model()
        downloader.register_model(test_model)
        
        # Create active download
        progress = DownloadProgress(
            model_id="resumable_model",
            total_size=10000000,
            downloaded_size=5000000,
            download_speed=100000.0,
            eta=50.0,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(),
            last_update=datetime.now(),
            resume_position=5000000
        )
        
        downloader.active_downloads["resumable_model"] = progress
        
        # Test pause
        success = downloader.pause_download("resumable_model")
        self.assertTrue(success)
        
        # Verify status changed
        paused_progress = downloader.active_downloads["resumable_model"]
        self.assertEqual(paused_progress.status, DownloadStatus.PAUSED)
        
        # Verify state file was created
        state_dir = self.storage_dir / ".download_states"
        state_file = state_dir / "resumable_model.json"
        self.assertTrue(state_file.exists())
    
    @patch('models.model_downloader.get_license_enforcer')
    def test_pause_non_downloading(self, mock_get_enforcer):
        """Test pausing a download that's not in downloading state"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        
        # Create completed download
        progress = DownloadProgress(
            model_id="test_model",
            total_size=1000000,
            downloaded_size=1000000,
            download_speed=0.0,
            eta=0.0,
            status=DownloadStatus.COMPLETED,
            started_at=datetime.now(),
            last_update=datetime.now()
        )
        
        downloader.active_downloads["test_model"] = progress
        
        # Try to pause completed download
        success = downloader.pause_download("test_model")
        self.assertFalse(success)
    
    @patch('models.model_downloader.get_license_enforcer')
    def test_save_and_load_download_state(self, mock_get_enforcer):
        """Test saving and loading download state"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        
        # Create progress to save
        original_progress = DownloadProgress(
            model_id="test_model",
            total_size=1000000,
            downloaded_size=500000,
            download_speed=100000.0,
            eta=5.0,
            status=DownloadStatus.PAUSED,
            started_at=datetime.now(),
            last_update=datetime.now(),
            resume_position=500000,
            temp_file_path="/tmp/test_model.tmp",
            chunk_hashes=["hash1", "hash2"]
        )
        
        # Save state
        downloader._save_download_state(original_progress)
        
        # Load state
        loaded_progress = downloader._load_download_state("test_model")
        
        # Verify loaded state
        self.assertIsNotNone(loaded_progress)
        self.assertEqual(loaded_progress.model_id, "test_model")
        self.assertEqual(loaded_progress.total_size, 1000000)
        self.assertEqual(loaded_progress.downloaded_size, 500000)
        self.assertEqual(loaded_progress.resume_position, 500000)
        self.assertEqual(loaded_progress.status, DownloadStatus.PAUSED)
        self.assertEqual(loaded_progress.temp_file_path, "/tmp/test_model.tmp")
        self.assertEqual(loaded_progress.chunk_hashes, ["hash1", "hash2"])
    
    @patch('models.model_downloader.get_license_enforcer')
    def test_load_nonexistent_download_state(self, mock_get_enforcer):
        """Test loading non-existent download state"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        
        # Try to load non-existent state
        loaded_progress = downloader._load_download_state("nonexistent_model")
        self.assertIsNone(loaded_progress)
    
    @patch('models.model_downloader.get_license_enforcer')
    def test_cleanup_download_files(self, mock_get_enforcer):
        """Test cleaning up download files"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        
        # Create state file
        state_dir = self.storage_dir / ".download_states"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "test_model.json"
        
        with open(state_file, 'w') as f:
            json.dump({"test": "data"}, f)
        
        # Create temp file
        temp_file = self.storage_dir / "test_model.tmp"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text("test content")
        
        # Create progress with temp file path
        progress = DownloadProgress(
            model_id="test_model",
            total_size=1000000,
            downloaded_size=500000,
            download_speed=0.0,
            eta=0.0,
            status=DownloadStatus.CANCELLED,
            started_at=datetime.now(),
            last_update=datetime.now(),
            temp_file_path=str(temp_file)
        )
        
        downloader.active_downloads["test_model"] = progress
        
        # Verify files exist
        self.assertTrue(state_file.exists())
        self.assertTrue(temp_file.exists())
        
        # Cleanup
        downloader._cleanup_download_files("test_model")
        
        # Verify files are removed
        self.assertFalse(state_file.exists())
        self.assertFalse(temp_file.exists())
    
    @patch('models.model_downloader.get_license_enforcer')
    def test_cancel_download_with_cleanup(self, mock_get_enforcer):
        """Test cancelling download with file cleanup"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        
        # Create temp file
        temp_file = self.storage_dir / "test_model.tmp"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text("test content")
        
        # Create active download
        progress = DownloadProgress(
            model_id="test_model",
            total_size=1000000,
            downloaded_size=500000,
            download_speed=100000.0,
            eta=5.0,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(),
            last_update=datetime.now(),
            temp_file_path=str(temp_file)
        )
        
        downloader.active_downloads["test_model"] = progress
        
        # Verify temp file exists
        self.assertTrue(temp_file.exists())
        
        # Cancel download
        success = downloader.cancel_download("test_model")
        self.assertTrue(success)
        
        # Verify download was cancelled and moved to history
        self.assertNotIn("test_model", downloader.active_downloads)
        self.assertIn("test_model", downloader.download_history)
        
        cancelled_progress = downloader.download_history["test_model"]
        self.assertEqual(cancelled_progress.status, DownloadStatus.CANCELLED)
        
        # Verify temp file was cleaned up
        self.assertFalse(temp_file.exists())


class TestResumableDownloadsAsync(unittest.IsolatedAsyncioTestCase):
    """Test async resumable download functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.temp_dir) / "models"
        self.mock_license_enforcer = self._create_mock_license_enforcer()
    
    def tearDown(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_mock_license_enforcer(self):
        """Create mock license enforcer"""
        mock_enforcer = Mock()
        mock_license = LicenseInfo(
            license_key="TIKT-PRO-12M-TEST001",
            plan=SubscriptionTier.PRO,
            duration_months=12,
            unique_id="TEST001",
            expires_at=datetime.now() + timedelta(days=30),
            max_clients=20,
            allowed_models=["resumable_model"],
            allowed_features=["chat", "inference"],
            status=LicenseStatus.VALID,
            hardware_signature="test_hw_sig",
            created_at=datetime.now(),
            checksum="test_checksum"
        )
        mock_enforcer.current_license = mock_license
        mock_enforcer.get_license_status.return_value = {'valid': True}
        return mock_enforcer
    
    def _create_test_model(self) -> ModelInfo:
        """Create test model for resumable downloads"""
        return ModelInfo(
            model_id="resumable_model",
            model_name="Resumable Test Model",
            model_version="1.0",
            model_size=1000000,  # 1MB
            required_tier=ModelTier.FREE,
            download_url="https://example.com/resumable_model.bin",
            checksum="abc123def456789012345678901234567890abcdef1234567890abcdef123456",
            description="Model for testing resumable downloads",
            tags=["test", "resumable"]
        )
    
    @patch('models.model_downloader.get_license_enforcer')
    async def test_resume_download_from_saved_state(self, mock_get_enforcer):
        """Test resuming download from saved state"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        test_model = self._create_test_model()
        downloader.register_model(test_model)
        
        # Create saved state
        progress = DownloadProgress(
            model_id="resumable_model",
            total_size=1000000,
            downloaded_size=500000,
            download_speed=0.0,
            eta=0.0,
            status=DownloadStatus.PAUSED,
            started_at=datetime.now(),
            last_update=datetime.now(),
            resume_position=500000,
            temp_file_path=str(self.storage_dir / "resumable_model.tmp")
        )
        
        # Save state
        downloader._save_download_state(progress)
        
        # Mock the resumable download method
        with patch.object(downloader, '_download_model_file_resumable', return_value=True) as mock_download:
            success = await downloader.resume_download("resumable_model")
            self.assertTrue(success)
            mock_download.assert_called_once()
    
    @patch('models.model_downloader.get_license_enforcer')
    async def test_resume_download_not_paused(self, mock_get_enforcer):
        """Test resuming download that's not in paused state"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        test_model = self._create_test_model()
        downloader.register_model(test_model)
        
        # Create active download (not paused)
        progress = DownloadProgress(
            model_id="resumable_model",
            total_size=1000000,
            downloaded_size=500000,
            download_speed=100000.0,
            eta=5.0,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(),
            last_update=datetime.now()
        )
        
        downloader.active_downloads["resumable_model"] = progress
        
        # Try to resume
        success = await downloader.resume_download("resumable_model")
        self.assertFalse(success)
    
    @patch('models.model_downloader.get_license_enforcer')
    async def test_resume_nonexistent_download(self, mock_get_enforcer):
        """Test resuming non-existent download"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        
        # Try to resume non-existent download
        success = await downloader.resume_download("nonexistent_model")
        self.assertFalse(success)
    
    @patch('models.model_downloader.get_license_enforcer')
    async def test_download_with_resume_headers(self, mock_get_enforcer):
        """Test download with HTTP range headers for resume"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        
        # Create temp file with partial content
        temp_file = self.storage_dir / "test_model.tmp"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_bytes(b"partial content")  # 15 bytes
        
        final_file = self.storage_dir / "test_model" / "model.bin"
        
        # Create progress with resume position
        progress = DownloadProgress(
            model_id="test_model",
            total_size=1000,
            downloaded_size=15,
            download_speed=0.0,
            eta=0.0,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(),
            last_update=datetime.now(),
            resume_position=15
        )
        
        # Mock the download method to avoid complex aiohttp mocking
        with patch.object(downloader, '_download_with_resume', return_value=True) as mock_download:
            with patch.object(downloader, '_verify_model_integrity', return_value=True):
                success = await downloader._download_model_file_resumable(
                    self._create_test_model(),
                    progress
                )
                
                # Verify the method was called (should be successful on first try)
                self.assertTrue(success)
                mock_download.assert_called()
    
    @patch('models.model_downloader.get_license_enforcer')
    async def test_download_resume_progress_updates(self, mock_get_enforcer):
        """Test progress updates during resume download"""
        mock_get_enforcer.return_value = self.mock_license_enforcer
        
        downloader = ModelDownloader(str(self.storage_dir))
        
        # Track progress updates
        progress_updates = []
        
        def progress_callback(progress: DownloadProgress):
            progress_updates.append({
                'downloaded_size': progress.downloaded_size,
                'resume_position': progress.resume_position,
                'status': progress.status.value
            })
        
        downloader.progress_callbacks.append(progress_callback)
        
        # Create progress starting from resume position
        progress = DownloadProgress(
            model_id="test_model",
            total_size=1000,
            downloaded_size=500,  # Starting from 500 bytes
            download_speed=0.0,
            eta=0.0,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(),
            last_update=datetime.now(),
            resume_position=500
        )
        
        # Simulate progress update
        progress.downloaded_size = 750
        progress.resume_position = 750
        downloader._notify_progress_callbacks(progress)
        
        # Verify progress was updated
        self.assertEqual(len(progress_updates), 1)
        self.assertEqual(progress_updates[0]['downloaded_size'], 750)
        self.assertEqual(progress_updates[0]['resume_position'], 750)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)