"""
Test script for model management functionality after moving files to models folder
"""

import logging
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ModelManagementTest")

def test_model_management():
    """Test model management functionality"""
    try:
        logger.info("Testing model management functionality...")
        
        # Test model verification
        from models.model_verification import ModelVerifier, VerificationStatus
        verifier = ModelVerifier()
        logger.info("✓ Model verifier instance created")
        
        # Test model encryption
        from models.model_encryption import ModelEncryption, create_model_encryption
        encryption = create_model_encryption()
        logger.info("✓ Model encryption instance created")
        
        # Test model downloader
        from models.model_downloader import ModelDownloader, ModelTier, ModelInfo
        downloader = ModelDownloader()
        logger.info("✓ Model downloader instance created")
        
        # Test model registration
        test_model = ModelInfo(
            model_id="test-model-1",
            model_name="Test Model",
            model_version="1.0.0",
            model_size=1024 * 1024,  # 1MB
            required_tier=ModelTier.FREE,
            download_url="https://example.com/test-model.bin",
            checksum="0123456789abcdef0123456789abcdef",
            description="Test model for verification",
            tags=["test", "small"],
            created_at=datetime.now()
        )
        
        success = downloader.register_model(test_model)
        if success:
            logger.info(f"✓ Test model registered: {test_model.model_id}")
        
        # Get available models
        models = downloader.get_available_models()
        logger.info(f"✓ Found {len(models)} available models")
        
        logger.info("All model management tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"Model management test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_model_management()
    sys.exit(0 if success else 1)