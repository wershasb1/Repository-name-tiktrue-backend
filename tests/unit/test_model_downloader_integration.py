"""
Integration test for model downloader with real license system
"""

import asyncio
import tempfile
import shutil
from pathlib import Path

from models.model_downloader import ModelDownloader, ModelInfo, ModelTier
from security.license_validator import validate_license
from license_storage import LicenseStorage

async def test_integration():
    """Test model downloader with real license integration"""
    print("=== Model Downloader Integration Test ===")
    
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_dir = Path(temp_dir) / "models"
    
    try:
        # Create model downloader
        downloader = ModelDownloader(str(storage_dir))
        
        print(f"✓ Model downloader initialized")
        print(f"  Storage: {storage_dir}")
        
        # Test without license
        print("\n--- Testing without license ---")
        available_models = downloader.get_available_models()
        print(f"Available models without license: {len(available_models)}")
        
        for model in available_models:
            print(f"  - {model.model_name} ({model.required_tier.value})")
            access = downloader.validate_model_access(model.model_id)
            print(f"    Access: {'✓' if access else '✗'}")
        
        # Test with fake PRO license
        print("\n--- Testing with fake PRO license ---")
        
        # Create a fake license for testing
        fake_license_key = "TIKT-PRO-12M-TEST01"
        
        try:
            license_info = validate_license(fake_license_key)
            print(f"License validation: {license_info.status.value}")
        except Exception as e:
            print(f"License validation failed (expected): {e}")
        
        # Test model registration
        print("\n--- Testing model registration ---")
        
        test_model = ModelInfo(
            model_id="test_integration_model",
            model_name="Integration Test Model",
            model_version="1.0",
            model_size=1000000,  # 1MB
            required_tier=ModelTier.FREE,
            download_url="https://example.com/test.bin",
            checksum="abc123def456",
            description="Model for integration testing",
            tags=["test", "integration"]
        )
        
        success = downloader.register_model(test_model)
        print(f"Model registration: {'✓' if success else '✗'}")
        
        # Test model access
        access = downloader.validate_model_access("test_integration_model")
        print(f"Test model access: {'✓' if access else '✗'}")
        
        # Test download attempt (will fail due to fake URL)
        print("\n--- Testing download attempt ---")
        try:
            success = await downloader.download_model("test_integration_model")
            print(f"Download result: {'✓' if success else '✗'}")
        except Exception as e:
            print(f"Download failed (expected): {e}")
        
        # Show statistics
        print("\n--- Final Statistics ---")
        stats = downloader.get_download_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n✓ Integration test completed successfully!")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(test_integration())