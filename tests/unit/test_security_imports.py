"""
Test script to verify security module imports after file reorganization
"""

import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SecurityImportTest")

def test_imports():
    """Test importing security modules"""
    try:
        logger.info("Testing security module imports...")
        
        # Import license validator
        from security.license_validator import LicenseValidator, get_license_validator
        logger.info("✓ Successfully imported license_validator")
        
        # Import auth manager
        from security.auth_manager import AuthenticationManager, NodeRole
        logger.info("✓ Successfully imported auth_manager")
        
        # Import crypto layer
        from security.crypto_layer import CryptoLayer, EncryptionLevel, CryptographicLayer
        logger.info("✓ Successfully imported crypto_layer")
        
        # Import hardware fingerprint
        from security.hardware_fingerprint import HardwareFingerprint, get_hardware_fingerprint
        logger.info("✓ Successfully imported hardware_fingerprint")
        
        logger.info("All security modules imported successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Import test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)