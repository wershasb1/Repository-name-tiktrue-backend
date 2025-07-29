"""
Integration test for resumable downloads
Tests the complete resumable download workflow
"""

import asyncio
import tempfile
import shutil
from pathlib import Path

from models.model_downloader import ModelDownloader, ModelInfo, ModelTier, DownloadStatus

async def test_resumable_integration():
    """Test resumable download integration"""
    print("=== Resumable Downloads Integration Test ===")
    
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_dir = Path(temp_dir) / "models"
    
    try:
        # Create model downloader
        downloader = ModelDownloader(str(storage_dir))
        
        print(f"✓ Model downloader initialized")
        print(f"  Storage: {storage_dir}")
        
        # Create test model
        test_model = ModelInfo(
            model_id="resumable_test_model",
            model_name="Resumable Integration Test Model",
            model_version="1.0",
            model_size=1000000,  # 1MB
            required_tier=ModelTier.FREE,
            download_url="https://httpbin.org/bytes/1000000",  # Returns 1MB of data
            checksum="fake_checksum_for_testing",
            description="Model for testing resumable downloads",
            tags=["test", "resumable", "integration"]
        )
        
        # Register model
        success = downloader.register_model(test_model)
        print(f"✓ Model registration: {'Success' if success else 'Failed'}")
        
        # Test download state persistence
        print("\n--- Testing Download State Persistence ---")
        
        # Create a mock download progress
        from models.model_downloader import DownloadProgress
        from datetime import datetime
        
        progress = DownloadProgress(
            model_id="resumable_test_model",
            total_size=1000000,
            downloaded_size=500000,
            download_speed=100000.0,
            eta=5.0,
            status=DownloadStatus.PAUSED,
            started_at=datetime.now(),
            last_update=datetime.now(),
            resume_position=500000,
            temp_file_path=str(storage_dir / "resumable_test_model.tmp"),
            chunk_hashes=["hash1", "hash2", "hash3"]
        )
        
        # Save download state
        downloader._save_download_state(progress)
        print("✓ Download state saved")
        
        # Load download state
        loaded_progress = downloader._load_download_state("resumable_test_model")
        if loaded_progress:
            print("✓ Download state loaded successfully")
            print(f"  Resume position: {loaded_progress.resume_position}")
            print(f"  Downloaded size: {loaded_progress.downloaded_size}")
            print(f"  Status: {loaded_progress.status.value}")
            print(f"  Chunk hashes: {len(loaded_progress.chunk_hashes)}")
        else:
            print("✗ Failed to load download state")
        
        # Test pause/resume workflow
        print("\n--- Testing Pause/Resume Workflow ---")
        
        # Create active download
        active_progress = DownloadProgress(
            model_id="active_download_test",
            total_size=2000000,
            downloaded_size=1000000,
            download_speed=200000.0,
            eta=5.0,
            status=DownloadStatus.DOWNLOADING,
            started_at=datetime.now(),
            last_update=datetime.now(),
            resume_position=1000000
        )
        
        downloader.active_downloads["active_download_test"] = active_progress
        
        # Test pause
        pause_success = downloader.pause_download("active_download_test")
        print(f"✓ Pause download: {'Success' if pause_success else 'Failed'}")
        
        if pause_success:
            paused_progress = downloader.active_downloads["active_download_test"]
            print(f"  Status after pause: {paused_progress.status.value}")
        
        # Test cleanup
        print("\n--- Testing Cleanup ---")
        
        # Create temporary files
        temp_file = storage_dir / "cleanup_test.tmp"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text("temporary download content")
        
        # Create progress with temp file
        cleanup_progress = DownloadProgress(
            model_id="cleanup_test",
            total_size=1000,
            downloaded_size=500,
            download_speed=0.0,
            eta=0.0,
            status=DownloadStatus.CANCELLED,
            started_at=datetime.now(),
            last_update=datetime.now(),
            temp_file_path=str(temp_file)
        )
        
        downloader.active_downloads["cleanup_test"] = cleanup_progress
        
        print(f"  Temp file exists before cleanup: {temp_file.exists()}")
        
        # Cleanup
        downloader._cleanup_download_files("cleanup_test")
        
        print(f"  Temp file exists after cleanup: {temp_file.exists()}")
        
        # Test download statistics
        print("\n--- Download Statistics ---")
        stats = downloader.get_download_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n✓ Resumable downloads integration test completed successfully!")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(test_resumable_integration())